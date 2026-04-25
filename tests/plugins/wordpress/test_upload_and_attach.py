"""F.5a.8.5 — unified upload+metadata+attach+featured via companion.

Tests the routing layer in ``_media_core.wp_raw_upload``:

* When the cached capability probe advertises ``upload_and_attach`` AND
  the caller supplies metadata/attach intent, we POST to
  ``/airano-mcp/v1/upload-and-attach`` and ``_apply_metadata_and_attach``
  becomes a no-op.
* When the probe doesn't advertise the route, we fall through to the
  legacy 3-step path (upload + PATCH metadata + PATCH featured).
* When the companion call errors, we fall back to the legacy path and
  metadata gets reapplied via the REST calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._media_core import (
    _companion_has_upload_and_attach,
    _companion_upload_and_attach,
    wp_raw_upload,
)
from plugins.wordpress.handlers._media_security import UploadError
from plugins.wordpress.handlers.media import _apply_metadata_and_attach

_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000000500010a2db4b70000"
    "000049454e44ae426082"
)


@pytest.fixture
def client():
    return WordPressClient(site_url="https://wp.example.com", username="admin", app_password="xxxx")


# ---------------------------------------------------------------------------
# Route advertisement check
# ---------------------------------------------------------------------------


class TestCompanionAdvertiseCheck:
    @pytest.mark.asyncio
    async def test_returns_true_when_route_advertised(self, client):
        with patch(
            "plugins.wordpress.handlers.capabilities.get_cached_capabilities",
            AsyncMock(
                return_value={
                    "companion_available": True,
                    "routes": {"upload_and_attach": True, "upload_chunk": True},
                }
            ),
        ):
            assert await _companion_has_upload_and_attach(client) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_route_absent(self, client):
        with patch(
            "plugins.wordpress.handlers.capabilities.get_cached_capabilities",
            AsyncMock(
                return_value={
                    "companion_available": True,
                    "routes": {"upload_chunk": True},  # no upload_and_attach
                }
            ),
        ):
            assert await _companion_has_upload_and_attach(client) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_companion_missing(self, client):
        with patch(
            "plugins.wordpress.handlers.capabilities.get_cached_capabilities",
            AsyncMock(return_value={"companion_available": False}),
        ):
            assert await _companion_has_upload_and_attach(client) is False

    @pytest.mark.asyncio
    async def test_returns_false_on_cold_cache(self, client):
        with patch(
            "plugins.wordpress.handlers.capabilities.get_cached_capabilities",
            AsyncMock(return_value=None),
        ):
            assert await _companion_has_upload_and_attach(client) is False


# ---------------------------------------------------------------------------
# wp_raw_upload routing: unified path when advertised + metadata supplied
# ---------------------------------------------------------------------------


class TestWpRawUploadRouting:
    @pytest.mark.asyncio
    async def test_uses_unified_path_when_advertised_and_metadata_supplied(self, client):
        captured: dict = {}

        async def _fake_unified(
            _client,
            data,
            *,
            sniffed,
            disposition,
            attach_to_post,
            set_featured,
            title,
            alt_text,
            caption,
            description,
            idempotency_key=None,
        ):
            captured["params"] = {
                "attach_to_post": attach_to_post,
                "set_featured": set_featured,
                "title": title,
                "alt_text": alt_text,
                "caption": caption,
                "description": description,
            }
            captured["called"] = True
            return {
                "id": 123,
                "source_url": "https://wp.example.com/out.png",
                "mime_type": "image/png",
                "_upload_and_attach": {
                    "attach_to_post": attach_to_post,
                    "set_featured": set_featured,
                },
            }

        with (
            patch(
                "plugins.wordpress.handlers._media_core._companion_has_upload_and_attach",
                AsyncMock(return_value=True),
            ),
            patch(
                "plugins.wordpress.handlers._media_core._companion_upload_and_attach",
                _fake_unified,
            ),
        ):
            media = await wp_raw_upload(
                client,
                _PNG_1x1,
                filename="hero.png",
                mime_hint="image/png",
                attach_to_post=42,
                set_featured=True,
                title="Hero",
                alt_text="A hero image",
                caption="caption here",
            )

        assert captured.get("called") is True
        assert captured["params"]["attach_to_post"] == 42
        assert captured["params"]["set_featured"] is True
        assert captured["params"]["title"] == "Hero"
        assert media["_upload_route"] == "companion_unified"
        assert media["id"] == 123

    @pytest.mark.asyncio
    async def test_skips_unified_when_no_metadata_intent(self, client):
        """Upload with zero metadata → no reason to use unified route
        even if advertised; fall through to legacy path."""
        unified_called: dict = {"hit": False}

        async def _fake_unified(*_a, **_kw):
            unified_called["hit"] = True
            return {}

        legacy_mock = AsyncMock(return_value={"id": 1, "source_url": "x", "mime_type": "image/png"})
        with (
            patch(
                "plugins.wordpress.handlers._media_core._companion_has_upload_and_attach",
                AsyncMock(return_value=True),
            ),
            patch(
                "plugins.wordpress.handlers._media_core._companion_upload_and_attach",
                _fake_unified,
            ),
            patch(
                "plugins.wordpress.handlers._media_core._should_use_companion",
                AsyncMock(return_value=False),
            ),
            patch("plugins.wordpress.handlers._media_core.aiohttp.ClientSession") as sess_cls,
        ):
            # Bare /wp/v2/media session mock.
            resp = AsyncMock()
            resp.status = 201
            resp.text = AsyncMock(return_value="{}")
            resp.json = AsyncMock(
                return_value={"id": 1, "source_url": "x", "mime_type": "image/png"}
            )
            sess = AsyncMock()
            sess.post = lambda *a, **kw: AsyncMock(
                __aenter__=AsyncMock(return_value=resp),
                __aexit__=AsyncMock(return_value=False),
            )
            sess_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            _ = legacy_mock

            media = await wp_raw_upload(client, _PNG_1x1, filename="x.png", mime_hint="image/png")

        assert unified_called["hit"] is False
        assert media["_upload_route"] == "rest"

    @pytest.mark.asyncio
    async def test_falls_back_when_unified_errors(self, client):
        """Unified call raising UploadError → fall through to legacy
        path, and the caller's metadata gets applied via the REST calls."""

        async def _boom(*_a, **_kw):
            raise UploadError("COMPANION_500", "simulated")

        with (
            patch(
                "plugins.wordpress.handlers._media_core._companion_has_upload_and_attach",
                AsyncMock(return_value=True),
            ),
            patch(
                "plugins.wordpress.handlers._media_core._companion_upload_and_attach",
                _boom,
            ),
            patch(
                "plugins.wordpress.handlers._media_core._should_use_companion",
                AsyncMock(return_value=False),
            ),
            patch("plugins.wordpress.handlers._media_core.aiohttp.ClientSession") as sess_cls,
        ):
            resp = AsyncMock()
            resp.status = 201
            resp.text = AsyncMock(return_value="{}")
            resp.json = AsyncMock(
                return_value={"id": 2, "source_url": "x", "mime_type": "image/png"}
            )
            sess = AsyncMock()
            sess.post = lambda *a, **kw: AsyncMock(
                __aenter__=AsyncMock(return_value=resp),
                __aexit__=AsyncMock(return_value=False),
            )
            sess_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=sess),
                __aexit__=AsyncMock(return_value=False),
            )
            media = await wp_raw_upload(
                client,
                _PNG_1x1,
                filename="x.png",
                mime_hint="image/png",
                attach_to_post=7,
            )

        # Legacy path marker — metadata will be applied via separate calls.
        assert media["_upload_route"] == "rest"
        assert "_upload_and_attach" not in media


# ---------------------------------------------------------------------------
# _apply_metadata_and_attach: skip when unified route marker present
# ---------------------------------------------------------------------------


class TestApplyMetadataSkip:
    @pytest.mark.asyncio
    async def test_unified_marker_short_circuits(self, client):
        # Media response carries the unified marker → no REST calls.
        media = {"id": 55, "_upload_route": "companion_unified"}
        update_mock = AsyncMock()
        featured_mock = AsyncMock()
        with (
            patch(
                "plugins.wordpress.handlers.media.wp_update_media_metadata",
                update_mock,
            ),
            patch(
                "plugins.wordpress.handlers.media.wp_set_featured_media",
                featured_mock,
            ),
        ):
            await _apply_metadata_and_attach(
                client,
                media,
                title="t",
                alt_text="a",
                caption="c",
                attach_to_post=7,
                set_featured=True,
            )
        update_mock.assert_not_called()
        featured_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_marker_runs_metadata_calls(self, client):
        media = {"id": 55, "_upload_route": "rest"}
        update_mock = AsyncMock()
        featured_mock = AsyncMock()
        with (
            patch(
                "plugins.wordpress.handlers.media.wp_update_media_metadata",
                update_mock,
            ),
            patch(
                "plugins.wordpress.handlers.media.wp_set_featured_media",
                featured_mock,
            ),
        ):
            await _apply_metadata_and_attach(
                client,
                media,
                title="t",
                alt_text="a",
                caption="c",
                attach_to_post=7,
                set_featured=True,
            )
        update_mock.assert_awaited_once()
        featured_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# _companion_upload_and_attach: query params + error mapping
# ---------------------------------------------------------------------------


def _build_fake_session(status: int, body_text: str):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=body_text)
    try:
        _parsed = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        _parsed = {}
    resp.json = AsyncMock(return_value=_parsed)
    captured: dict = {}

    def _post(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        captured["headers"] = kwargs.get("headers")
        return AsyncMock(
            __aenter__=AsyncMock(return_value=resp),
            __aexit__=AsyncMock(return_value=False),
        )

    sess = AsyncMock()
    sess.post = _post
    sess_cm = AsyncMock(
        __aenter__=AsyncMock(return_value=sess),
        __aexit__=AsyncMock(return_value=False),
    )
    return sess_cm, captured


class TestCompanionUploadAndAttachClient:
    @pytest.mark.asyncio
    async def test_query_params_encoded_from_metadata(self, client):
        cm, captured = _build_fake_session(
            200,
            json.dumps({"id": 7, "source_url": "x", "mime_type": "image/png"}),
        )
        with patch(
            "plugins.wordpress.handlers._media_core.aiohttp.ClientSession",
            return_value=cm,
        ):
            out = await _companion_upload_and_attach(
                client,
                b"irrelevant",
                sniffed="image/png",
                disposition='attachment; filename="x.png"',
                attach_to_post=42,
                set_featured=True,
                title="T",
                alt_text="A",
                caption="C",
                description="D",
            )
        assert out["id"] == 7
        p = captured["params"]
        assert p["attach_to_post"] == "42"
        assert p["set_featured"] == "true"
        assert p["title"] == "T"
        assert p["alt_text"] == "A"
        assert p["caption"] == "C"
        assert p["description"] == "D"
        assert "airano-mcp/v1/upload-and-attach" in captured["url"]

    @pytest.mark.asyncio
    async def test_set_featured_ignored_without_attach_target(self, client):
        cm, captured = _build_fake_session(
            200, json.dumps({"id": 1, "source_url": "x", "mime_type": "image/png"})
        )
        with patch(
            "plugins.wordpress.handlers._media_core.aiohttp.ClientSession",
            return_value=cm,
        ):
            await _companion_upload_and_attach(
                client,
                b"x",
                sniffed="image/png",
                disposition="attachment",
                attach_to_post=None,
                set_featured=True,  # ignored when no attach_to_post
                title=None,
                alt_text=None,
                caption=None,
                description=None,
            )
        assert "set_featured" not in captured["params"]
        assert "attach_to_post" not in captured["params"]

    @pytest.mark.asyncio
    async def test_500_maps_to_companion_status_error(self, client):
        cm, _ = _build_fake_session(500, "internal error")
        with patch(
            "plugins.wordpress.handlers._media_core.aiohttp.ClientSession",
            return_value=cm,
        ):
            with pytest.raises(UploadError) as e:
                await _companion_upload_and_attach(
                    client,
                    b"x",
                    sniffed="image/png",
                    disposition="attachment",
                    attach_to_post=1,
                    set_featured=False,
                    title=None,
                    alt_text=None,
                    caption=None,
                    description=None,
                )
        assert e.value.code == "COMPANION_500"
