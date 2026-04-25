"""F.5a.6.4 — media.upload audit-log emission tests."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.media import MediaHandler

# 1x1 PNG — passes magic-byte sniff and size validation.
_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def fake_audit(monkeypatch):
    """Replace the singleton audit logger with a MagicMock."""
    fake = MagicMock()
    fake.log_tool_call = MagicMock()
    monkeypatch.setattr("core.audit_log.get_audit_logger", lambda: fake)
    return fake


def _patch_wp_upload(monkeypatch, *, media_id=42, mime="image/png"):
    """Stub wp_raw_upload at its import site inside media.py."""

    async def fake_upload(client, data, *, filename, mime_hint=None, **kw):
        return {
            "id": media_id,
            "mime_type": mime,
            "media_type": "image",
            "source_url": f"https://wp.example.com/wp-content/uploads/{filename}",
            "title": {"rendered": filename},
            "media_details": {"filesize": len(data)},
        }

    monkeypatch.setattr("plugins.wordpress.handlers.media.wp_raw_upload", fake_upload)


@pytest.mark.asyncio
async def test_base64_upload_emits_one_audit_entry(wp_client, fake_audit, monkeypatch):
    _patch_wp_upload(monkeypatch)
    handler = MediaHandler(wp_client, user_id="alice")

    out = json.loads(
        await handler.upload_media_from_base64(
            data=base64.b64encode(_PNG_1x1).decode(),
            filename="x.png",
            skip_optimize=True,
        )
    )
    assert out["id"] == 42

    assert fake_audit.log_tool_call.call_count == 1
    call = fake_audit.log_tool_call.call_args
    assert call.kwargs["tool_name"] == "media.upload"
    assert call.kwargs["user_id"] == "alice"
    p = call.kwargs["params"]
    assert p["source"] == "base64"
    assert p["mime"] == "image/png"
    assert p["media_id"] == 42
    assert p["size_bytes"] == len(_PNG_1x1)
    assert p["site"] == "https://wp.example.com"
    assert "cost_usd" not in p


@pytest.mark.asyncio
async def test_base64_failure_writes_no_audit_entry(wp_client, fake_audit, monkeypatch):
    """Decode failure short-circuits before upload — no audit entry."""
    handler = MediaHandler(wp_client, user_id="alice")
    out = json.loads(
        await handler.upload_media_from_base64(
            data="!!! not valid base64 !!!",
            filename="x.png",
        )
    )
    assert out["error_code"] == "BAD_BASE64"
    assert fake_audit.log_tool_call.call_count == 0


@pytest.mark.asyncio
async def test_url_upload_emits_one_audit_entry(wp_client, fake_audit, monkeypatch):
    _patch_wp_upload(monkeypatch)
    handler = MediaHandler(wp_client, user_id=None)  # admin/env

    # Bypass SSRF + network: stub fetch_url_bytes.
    async def fake_fetch(url, **kw):
        return _PNG_1x1, "image/png", "remote.png"

    monkeypatch.setattr("plugins.wordpress.handlers.media.fetch_url_bytes", fake_fetch)
    monkeypatch.setattr(
        "plugins.wordpress.handlers.media.ssrf_check",
        lambda url: type("S", (), {"allowed": True, "reason": None})(),
    )

    out = json.loads(
        await handler.upload_media_from_url(url="https://cdn.example.com/x.png", skip_optimize=True)
    )
    assert out["id"] == 42

    assert fake_audit.log_tool_call.call_count == 1
    call = fake_audit.log_tool_call.call_args
    assert call.kwargs["params"]["source"] == "url"
    assert call.kwargs["user_id"] is None  # admin


@pytest.mark.asyncio
async def test_chunked_finish_emits_one_audit_entry(wp_client, fake_audit, monkeypatch):
    """Chunked finish should emit a media.upload entry with source='chunked'."""
    from plugins.wordpress.handlers.media_chunked import MediaChunkedHandler

    _patch_wp_upload(monkeypatch)

    # Stub the chunked store's finalize() to return assembled bytes.
    class _FakeSession:
        filename = "big.png"
        mime = "image/png"

    class _FakeStore:
        async def finalize(self, sid):
            return _FakeSession(), _PNG_1x1

    monkeypatch.setattr(
        "plugins.wordpress.handlers.media_chunked.wp_raw_upload",
        lambda *a, **k: _patch_wp_upload,  # not used; media.wp_raw_upload is patched
    )

    # The chunked handler calls wp_raw_upload imported into media_chunked.py
    async def fake_upload(client, data, *, filename, mime_hint=None, **kw):
        return {
            "id": 99,
            "mime_type": "image/png",
            "media_type": "image",
            "source_url": "https://wp.example.com/wp-content/uploads/big.png",
            "title": {"rendered": "big.png"},
            "media_details": {"filesize": len(data)},
        }

    monkeypatch.setattr("plugins.wordpress.handlers.media_chunked.wp_raw_upload", fake_upload)

    handler = MediaChunkedHandler(wp_client, user_id="bob", store=_FakeStore())
    out = json.loads(
        await handler.upload_media_chunked_finish(session_id="sid", skip_optimize=True)
    )
    assert out["id"] == 99

    assert fake_audit.log_tool_call.call_count == 1
    call = fake_audit.log_tool_call.call_args
    assert call.kwargs["params"]["source"] == "chunked"
    assert call.kwargs["params"]["media_id"] == 99
    assert call.kwargs["user_id"] == "bob"
