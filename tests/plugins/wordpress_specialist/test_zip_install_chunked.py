"""Tests for WordPress Specialist chunked install zip staging."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from core.database import Database
from core.upload_sessions import (
    UploadSessionError,
    UploadSessionStore,
    set_upload_session_store,
)
from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers._zip_payload import ZIP_INSTALL_SESSION_MIME
from plugins.wordpress_specialist.handlers.plugins import PluginsHandler
from plugins.wordpress_specialist.handlers.themes import ThemesHandler
from plugins.wordpress_specialist.handlers.zip_install_chunked import (
    _ZIP_INSTALL_MAX_BYTES,
    ZipInstallChunkedHandler,
    get_tool_specifications,
)


@pytest.fixture
async def db(tmp_path: Path):
    d = Database(str(tmp_path / "test.db"))
    await d.initialize()
    try:
        yield d
    finally:
        await d.close()


@pytest.fixture
async def store(tmp_path: Path, db: Database) -> UploadSessionStore:
    s = UploadSessionStore(db=db, spill_dir=tmp_path / "spill")
    set_upload_session_store(s)
    try:
        yield s
    finally:
        set_upload_session_store(None)


@pytest.fixture
def staging_handler(store: UploadSessionStore) -> ZipInstallChunkedHandler:
    return ZipInstallChunkedHandler(user_id="alice", store=store)


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.post = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


def _zip_bytes(filename: str, body: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, body)
    return buf.getvalue()


async def _stage_payload(handler: ZipInstallChunkedHandler, payload: bytes) -> str:
    start = json.loads(
        await handler.wp_zip_install_chunked_start(
            filename="package.zip",
            total_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
    )
    sid = start["session_id"]
    half = len(payload) // 2
    await handler.wp_zip_install_chunked_chunk(
        session_id=sid,
        index=0,
        data_b64=base64.b64encode(payload[:half]).decode("ascii"),
    )
    await handler.wp_zip_install_chunked_chunk(
        session_id=sid,
        index=1,
        data_b64=base64.b64encode(payload[half:]).decode("ascii"),
    )
    return sid


def test_tool_specs_expose_four_admin_tools():
    specs = get_tool_specifications()
    assert len(specs) == 4
    assert {s["name"] for s in specs} == {
        "wp_zip_install_chunked_start",
        "wp_zip_install_chunked_chunk",
        "wp_zip_install_chunked_status",
        "wp_zip_install_chunked_abort",
    }
    assert {s["scope"] for s in specs} == {"admin"}


@pytest.mark.asyncio
async def test_start_creates_wordpress_install_zip_session(
    staging_handler: ZipInstallChunkedHandler,
    store: UploadSessionStore,
):
    out = json.loads(
        await staging_handler.wp_zip_install_chunked_start(
            filename="plugin.zip",
            total_bytes=123,
            sha256="0" * 64,
        )
    )

    sess = await store.get(out["session_id"])
    assert sess is not None
    assert sess.filename == "plugin.zip"
    assert sess.mime == ZIP_INSTALL_SESSION_MIME
    assert out["max_bytes"] == _ZIP_INSTALL_MAX_BYTES
    assert out["recommended_chunk_bytes"] == 1024 * 1024
    assert out["handoff"] == "stream_base64_chunks"


@pytest.mark.asyncio
async def test_start_exposes_http_binary_handoff_for_user_endpoint(
    store: UploadSessionStore,
):
    handler = ZipInstallChunkedHandler(
        user_id="user-uuid-001",
        site_id="site-uuid-001",
        alias="specialist",
        store=store,
    )

    out = json.loads(
        await handler.wp_zip_install_chunked_start(
            filename="plugin.zip",
            total_bytes=123,
            sha256="0" * 64,
        )
    )

    assert out["handoff"] == "http_binary_put"
    assert out["fallback_handoff"] == "stream_base64_chunks"
    assert out["upload"]["method"] == "PUT"
    assert out["upload"]["url"] == (
        f"/u/user-uuid-001/specialist/zip-install-upload/{out['session_id']}"
    )


@pytest.mark.asyncio
async def test_start_uses_public_url_for_external_clients(
    store: UploadSessionStore,
    monkeypatch,
):
    monkeypatch.setenv("PUBLIC_URL", "https://mcp.example.com/")
    handler = ZipInstallChunkedHandler(
        user_id="user-uuid-001",
        site_id="site-uuid-001",
        alias="specialist",
        store=store,
    )

    out = json.loads(
        await handler.wp_zip_install_chunked_start(
            filename="plugin.zip", total_bytes=123, sha256="0" * 64
        )
    )

    assert out["upload"]["url"].startswith("https://mcp.example.com/")


@pytest.mark.asyncio
async def test_start_rejects_paths_non_zip_and_oversized(
    staging_handler: ZipInstallChunkedHandler,
):
    with_path = json.loads(
        await staging_handler.wp_zip_install_chunked_start(
            filename="../plugin.zip",
            total_bytes=10,
        )
    )
    non_zip = json.loads(
        await staging_handler.wp_zip_install_chunked_start(
            filename="plugin.txt",
            total_bytes=10,
        )
    )
    oversized = json.loads(
        await staging_handler.wp_zip_install_chunked_start(
            filename="plugin.zip",
            total_bytes=_ZIP_INSTALL_MAX_BYTES + 1,
        )
    )

    assert with_path["error_code"] == "BAD_FILENAME"
    assert non_zip["error_code"] == "BAD_FILENAME"
    assert oversized["error_code"] == "SESSION_TOO_LARGE"


@pytest.mark.asyncio
async def test_chunk_status_and_abort(
    staging_handler: ZipInstallChunkedHandler,
):
    payload = b"abcdefghij"
    start = json.loads(
        await staging_handler.wp_zip_install_chunked_start(
            filename="plugin.zip",
            total_bytes=len(payload),
        )
    )
    sid = start["session_id"]

    first = json.loads(
        await staging_handler.wp_zip_install_chunked_chunk(
            session_id=sid,
            index=0,
            data_b64=base64.b64encode(payload[:4]).decode("ascii"),
        )
    )
    status = json.loads(await staging_handler.wp_zip_install_chunked_status(session_id=sid))
    abort = json.loads(await staging_handler.wp_zip_install_chunked_abort(session_id=sid))
    gone = json.loads(await staging_handler.wp_zip_install_chunked_status(session_id=sid))

    assert first["received_bytes"] == 4
    assert first["next_chunk"] == 1
    assert status["received_bytes"] == 4
    assert abort["aborted"] is True
    assert gone["error_code"] == "NO_SESSION"


@pytest.mark.asyncio
async def test_bad_base64_chunk_returns_error_json(
    staging_handler: ZipInstallChunkedHandler,
):
    start = json.loads(
        await staging_handler.wp_zip_install_chunked_start(
            filename="plugin.zip",
            total_bytes=10,
        )
    )

    out = json.loads(
        await staging_handler.wp_zip_install_chunked_chunk(
            session_id=start["session_id"],
            index=0,
            data_b64="not base64!",
        )
    )

    assert out["error_code"] == "BAD_BASE64"


@pytest.mark.asyncio
async def test_plugin_install_accepts_staged_zip_session(
    staging_handler: ZipInstallChunkedHandler,
    store: UploadSessionStore,
    client,
):
    payload = _zip_bytes("plugin/plugin.php", "<?php\n/* Plugin Name: Test */\n")
    sid = await _stage_payload(staging_handler, payload)

    await PluginsHandler(client).wp_plugin_install_from_zip(
        zip_session_id=sid,
        activate=True,
        overwrite=True,
    )

    args, kwargs = client.post.call_args
    body = kwargs["json_data"]
    assert args[0] == "airano-mcp/v1/admin/plugins/install"
    assert body["zip_base64"] == base64.b64encode(payload).decode("ascii")
    assert body["activate"] is True
    assert body["overwrite"] is True
    assert "zip_session_id" not in body
    assert "zip_path" not in body
    assert await store.get(sid) is None


@pytest.mark.asyncio
async def test_theme_install_accepts_staged_zip_session(
    staging_handler: ZipInstallChunkedHandler,
    store: UploadSessionStore,
    client,
):
    payload = _zip_bytes("theme/style.css", "/*\nTheme Name: Test\n*/\n")
    sid = await _stage_payload(staging_handler, payload)

    await ThemesHandler(client).wp_theme_install_from_zip(
        zip_session_id=sid,
        activate=True,
    )

    args, kwargs = client.post.call_args
    body = kwargs["json_data"]
    assert args[0] == "airano-mcp/v1/admin/themes/install"
    assert body["zip_base64"] == base64.b64encode(payload).decode("ascii")
    assert body["activate"] is True
    assert body["overwrite"] is False
    assert "zip_session_id" not in body
    assert "zip_path" not in body
    assert await store.get(sid) is None


@pytest.mark.asyncio
async def test_install_rejects_incomplete_staged_zip_session(
    staging_handler: ZipInstallChunkedHandler,
    client,
):
    payload = _zip_bytes("plugin/plugin.php", "<?php\n")
    start = json.loads(
        await staging_handler.wp_zip_install_chunked_start(
            filename="plugin.zip",
            total_bytes=len(payload),
        )
    )
    sid = start["session_id"]
    await staging_handler.wp_zip_install_chunked_chunk(
        session_id=sid,
        index=0,
        data_b64=base64.b64encode(payload[:4]).decode("ascii"),
    )

    with pytest.raises(UploadSessionError) as exc:
        await PluginsHandler(client).wp_plugin_install_from_zip(zip_session_id=sid)

    assert exc.value.code == "INCOMPLETE"
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_rejects_wrong_session_mime(
    store: UploadSessionStore,
    client,
):
    payload = _zip_bytes("plugin/plugin.php", "<?php\n")
    sess = await store.start(
        user_id="alice",
        filename="plugin.zip",
        total_bytes=len(payload),
        mime="application/zip",
    )
    await store.append_chunk(sess.id, 0, payload)

    with pytest.raises(ValueError, match="WordPress install zip session"):
        await PluginsHandler(client).wp_plugin_install_from_zip(zip_session_id=sess.id)

    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_rejects_non_zip_staged_payload(
    staging_handler: ZipInstallChunkedHandler,
    client,
):
    payload = b"not a zip"
    sid = await _stage_payload(staging_handler, payload)

    with pytest.raises(ValueError, match="valid zip archive"):
        await PluginsHandler(client).wp_plugin_install_from_zip(zip_session_id=sid)

    client.post.assert_not_awaited()
