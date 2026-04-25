"""Tests for F.5a.1 media upload primitives and handler."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._media_core import (
    wp_raw_upload,
    wp_set_featured_media,
    wp_update_media_metadata,
)
from plugins.wordpress.handlers._media_security import (
    ALLOWED_MIMES,
    UploadError,
    content_disposition,
    safe_filename,
    sniff_mime,
    ssrf_check,
    validate_mime,
    validate_size,
)
from plugins.wordpress.handlers.media import MediaHandler

# A minimal valid PNG (1x1, transparent)
_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


# --- Security primitives ----------------------------------------------------


class TestSecurity:
    def test_sniff_mime_detects_png(self):
        assert sniff_mime(_PNG_1x1) == "image/png"

    def test_sniff_mime_falls_back_to_hint(self):
        # Random ASCII with no image/video/audio magic signature. Different
        # libmagic builds disagree on whether short human-readable bytes are
        # "application/octet-stream" (conservative) or "text/plain" (aggressive).
        # Either is acceptable; what matters is that the function doesn't crash
        # and returns *something* usable when the hint can't be trusted.
        result = sniff_mime(b"not a real file", hint="image/png")
        assert result in {
            "image/png",
            "application/octet-stream",
            "text/plain",
        }

    def test_validate_size_empty(self):
        with pytest.raises(UploadError) as e:
            validate_size(b"")
        assert e.value.code == "EMPTY_FILE"

    def test_validate_size_too_large(self):
        with pytest.raises(UploadError) as e:
            validate_size(b"x" * 10, max_bytes=5)
        assert e.value.code == "TOO_LARGE"

    def test_validate_mime_rejects_unknown(self):
        with pytest.raises(UploadError) as e:
            validate_mime("application/x-msdownload")
        assert e.value.code == "MIME_REJECTED"

    def test_validate_mime_allows_jpeg(self):
        validate_mime("image/jpeg")  # no raise

    def test_safe_filename_ascii_preserved(self):
        name, encoded = safe_filename("photo.jpg", mime="image/jpeg")
        assert name == "photo.jpg"
        assert encoded is None

    def test_safe_filename_sanitizes_path(self):
        name, _ = safe_filename("../../etc/passwd.jpg", mime="image/jpeg")
        assert "/" not in name and ".." not in name
        assert name.endswith(".jpg")

    def test_safe_filename_unicode(self):
        name, encoded = safe_filename("عکس.jpg", mime="image/jpeg")
        assert encoded is not None
        assert encoded.startswith("UTF-8''")
        # ASCII filename still has extension
        assert name.endswith(".jpg")

    def test_safe_filename_adds_extension_from_mime(self):
        name, _ = safe_filename("noext", mime="image/png")
        assert name.endswith(".png")

    def test_content_disposition_ascii_only(self):
        h = content_disposition("a.jpg", None)
        assert h == 'attachment; filename="a.jpg"'

    def test_content_disposition_rfc5987(self):
        h = content_disposition("a.jpg", "UTF-8''%D8%B9.jpg")
        assert "filename*=UTF-8''" in h


class TestSSRF:
    def test_blocks_localhost(self):
        r = ssrf_check("http://127.0.0.1/x", allow_http=True)
        assert not r.allowed

    def test_blocks_metadata_host(self):
        r = ssrf_check("http://169.254.169.254/latest/meta-data", allow_http=True)
        assert not r.allowed

    def test_blocks_http_by_default(self):
        r = ssrf_check("http://example.com/x")
        assert not r.allowed

    def test_blocks_bad_scheme(self):
        r = ssrf_check("file:///etc/passwd")
        assert not r.allowed

    def test_blocks_metadata_hostname(self):
        r = ssrf_check("https://metadata.google.internal/")
        assert not r.allowed

    def test_blocks_private_range(self):
        # 10.x resolves without DNS via literal IP
        r = ssrf_check("https://10.0.0.1/x")
        assert not r.allowed


# --- wp_raw_upload ----------------------------------------------------------


class TestRawUpload:
    @pytest.mark.asyncio
    async def test_happy_path_png(self):
        client = _client()
        wp_response = {
            "id": 123,
            "title": {"rendered": "photo"},
            "source_url": "https://wp.example.com/wp-content/uploads/photo.png",
            "mime_type": "image/png",
            "media_type": "image",
        }
        mock_resp = AsyncMock()
        mock_resp.status = 201
        mock_resp.text = AsyncMock(return_value=json.dumps(wp_response))
        mock_resp.json = AsyncMock(return_value=wp_response)

        mock_sess = AsyncMock()
        mock_sess.post = lambda *a, **kw: AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("plugins.wordpress.handlers._media_core.aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_sess),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await wp_raw_upload(client, _PNG_1x1, filename="photo.png")
        assert result["id"] == 123

    @pytest.mark.asyncio
    async def test_413_raises_typed_error(self):
        client = _client()
        mock_resp = AsyncMock()
        mock_resp.status = 413
        mock_resp.text = AsyncMock(return_value="Payload Too Large")

        mock_sess = AsyncMock()
        mock_sess.post = lambda *a, **kw: AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("plugins.wordpress.handlers._media_core.aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(UploadError) as e:
                await wp_raw_upload(client, _PNG_1x1, filename="photo.png")
        assert e.value.code == "WP_413"

    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self):
        client = _client()
        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.text = AsyncMock(return_value='{"code":"invalid_auth"}')

        mock_sess = AsyncMock()
        mock_sess.post = lambda *a, **kw: AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("plugins.wordpress.handlers._media_core.aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_sess),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(UploadError) as e:
                await wp_raw_upload(client, _PNG_1x1, filename="photo.png")
        assert e.value.code == "WP_AUTH"

    @pytest.mark.asyncio
    async def test_rejects_disallowed_mime(self):
        client = _client()
        # Binary that will be sniffed as something unusual; enforce via hint list
        with pytest.raises(UploadError) as e:
            await wp_raw_upload(
                client,
                b"MZ\x90\x00" + b"\x00" * 100,
                filename="evil.exe",
                mime_hint="application/x-msdownload",
                allowed_mimes={"image/png"},
            )
        assert e.value.code == "MIME_REJECTED"


# --- MediaHandler integration ----------------------------------------------


class TestMediaHandler:
    @pytest.mark.asyncio
    async def test_upload_from_base64_happy_path(self):
        handler = MediaHandler(_client())
        wp_media = {
            "id": 42,
            "title": {"rendered": "hi"},
            "source_url": "https://wp.example.com/wp-content/uploads/hi.png",
            "mime_type": "image/png",
            "media_type": "image",
        }
        with (
            patch(
                "plugins.wordpress.handlers.media.wp_raw_upload",
                new=AsyncMock(return_value=wp_media),
            ),
            patch(
                "plugins.wordpress.handlers.media.wp_update_media_metadata",
                new=AsyncMock(return_value={}),
            ),
        ):
            out = await handler.upload_media_from_base64(
                data=base64.b64encode(_PNG_1x1).decode(),
                filename="hi.png",
                alt_text="hi",
            )
        parsed = json.loads(out)
        assert parsed["id"] == 42
        assert parsed["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_upload_from_base64_rejects_bad_payload(self):
        handler = MediaHandler(_client())
        out = await handler.upload_media_from_base64(data="!!!!not-base64", filename="x.png")
        parsed = json.loads(out)
        assert parsed["error_code"] == "BAD_BASE64"

    @pytest.mark.asyncio
    async def test_upload_from_base64_strips_data_url_prefix(self):
        handler = MediaHandler(_client())
        wp_media = {
            "id": 9,
            "title": {"rendered": "x"},
            "source_url": "https://wp.example.com/x.png",
            "mime_type": "image/png",
            "media_type": "image",
        }
        prefixed = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode()
        with (
            patch(
                "plugins.wordpress.handlers.media.wp_raw_upload",
                new=AsyncMock(return_value=wp_media),
            ),
            patch(
                "plugins.wordpress.handlers.media.wp_update_media_metadata",
                new=AsyncMock(return_value={}),
            ),
        ):
            out = await handler.upload_media_from_base64(data=prefixed, filename="x.png")
        assert json.loads(out)["id"] == 9

    @pytest.mark.asyncio
    async def test_upload_from_url_ssrf_blocked(self):
        handler = MediaHandler(_client())
        out = await handler.upload_media_from_url(url="http://127.0.0.1/image.png")
        parsed = json.loads(out)
        assert parsed["error_code"] == "SSRF"

    @pytest.mark.asyncio
    async def test_upload_sets_featured_when_attached(self):
        handler = MediaHandler(_client())
        wp_media = {
            "id": 7,
            "title": {"rendered": "hi"},
            "source_url": "https://wp.example.com/hi.png",
            "mime_type": "image/png",
            "media_type": "image",
        }
        featured_mock = AsyncMock(return_value={"id": 100, "featured_media": 7})
        with (
            patch(
                "plugins.wordpress.handlers.media.wp_raw_upload",
                new=AsyncMock(return_value=wp_media),
            ),
            patch(
                "plugins.wordpress.handlers.media.wp_update_media_metadata",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "plugins.wordpress.handlers.media.wp_set_featured_media",
                new=featured_mock,
            ),
        ):
            await handler.upload_media_from_base64(
                data=base64.b64encode(_PNG_1x1).decode(),
                filename="hi.png",
                attach_to_post=100,
                set_featured=True,
            )
        featured_mock.assert_awaited_once()
        args = featured_mock.await_args
        assert args.args[1] == 100  # post_id
        assert args.args[2] == 7  # media_id


# --- metadata helpers -------------------------------------------------------


class TestMetadataHelpers:
    @pytest.mark.asyncio
    async def test_update_media_metadata_skips_when_nothing_to_update(self):
        client = _client()
        with patch.object(client, "post", new=AsyncMock()) as mock_post:
            result = await wp_update_media_metadata(client, 1)
        assert result == {}
        mock_post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_media_metadata_sends_only_set_fields(self):
        client = _client()
        with patch.object(client, "post", new=AsyncMock(return_value={"id": 1})) as mock_post:
            await wp_update_media_metadata(client, 1, alt_text="hi")
        mock_post.assert_awaited_once()
        call = mock_post.await_args
        assert call.kwargs["json_data"] == {"alt_text": "hi"}

    @pytest.mark.asyncio
    async def test_set_featured_media(self):
        client = _client()
        with patch.object(client, "post", new=AsyncMock(return_value={"id": 5})) as mock_post:
            await wp_set_featured_media(client, 5, 9)
        mock_post.assert_awaited_once_with("posts/5", json_data={"featured_media": 9})


def test_allowed_mimes_includes_common_types():
    for m in ("image/jpeg", "image/png", "image/webp", "application/pdf"):
        assert m in ALLOWED_MIMES
