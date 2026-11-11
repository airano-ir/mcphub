"""Tests for HTTP binary media intake."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from core.database import Database
from core.media_intake import (
    admin_media_browser_page,
    admin_media_upload_handler,
    make_admin_browser_upload_url,
    user_media_upload_handler,
)
from core.upload_sessions import (
    UploadSessionStore,
    make_session_owner_id,
    set_upload_session_store,
)
from core.upload_tokens import validate_upload_token
from plugins.wordpress.handlers.media_chunked import MediaChunkedHandler


def _make_upload_request(
    session_id: str,
    *,
    body: bytes,
    user_id: str = "user-uuid-001",
    alias: str = "myblog",
    token: str = "mhu_validkey1234567890abcdefghijklmnopqrst",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope_headers = [
        (b"authorization", f"Bearer {token}".encode()),
        (b"content-type", b"application/octet-stream"),
    ]
    if headers:
        scope_headers.extend(headers)

    scope = {
        "type": "http",
        "method": "PUT",
        "path": f"/u/{user_id}/{alias}/media-upload/{session_id}",
        "path_params": {
            "user_id": user_id,
            "alias": alias,
            "session_id": session_id,
        },
        "headers": scope_headers,
        "query_string": b"",
    }
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def _make_browser_request(session_id: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/admin/media-upload/{session_id}/browser",
        "path_params": {"session_id": session_id},
        "headers": [],
        "query_string": b"",
    }
    return Request(scope)


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
def mock_key_mgr():
    mgr = AsyncMock()
    mgr.validate_key = AsyncMock(
        return_value={
            "key_id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "scopes": "read write",
            "site_id": None,
        }
    )
    with patch("core.user_keys.get_user_key_manager", return_value=mgr):
        yield mgr


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_site_by_alias = AsyncMock(
        return_value={
            "id": "site-uuid-001",
            "user_id": "user-uuid-001",
            "plugin_type": "wordpress",
            "alias": "myblog",
            "url": "https://myblog.example.com",
            "status": "active",
            "tool_scope": "admin",
        }
    )
    db.get_user_by_id = AsyncMock(return_value={"id": "user-uuid-001", "role": "user"})
    db.get_site_tool_toggles = AsyncMock(return_value={})
    with patch("core.database.get_database", return_value=db):
        yield db


@pytest.mark.asyncio
async def test_user_media_upload_handler_appends_raw_bytes(
    store: UploadSessionStore,
    mock_key_mgr,
    mock_db,
):
    payload = b"binary upload payload"
    digest = hashlib.sha256(payload).hexdigest()
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "site-uuid-001"),
        filename="hero.png",
        total_bytes=len(payload),
        mime="image/png",
        sha256=digest,
    )
    request = _make_upload_request(
        sess.id,
        body=payload,
        headers=[(b"x-mcphub-chunk-sha256", digest.encode())],
    )

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_media_upload_handler(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["session_id"] == sess.id
    assert body["received_bytes"] == len(payload)
    assert body["ready_to_finish"] is True

    _, data = await store.finalize(sess.id)
    assert data == payload


@pytest.mark.asyncio
async def test_user_media_upload_handler_rejects_wrong_site_owner(
    store: UploadSessionStore,
    mock_key_mgr,
    mock_db,
):
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "other-site"),
        filename="hero.png",
        total_bytes=5,
    )
    request = _make_upload_request(sess.id, body=b"12345")

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_media_upload_handler(request)

    assert response.status_code == 403
    body = json.loads(response.body)
    assert body["error_code"] == "FORBIDDEN"


def test_chunked_handoff_uses_absolute_public_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://mcp.example.com/")
    handler = MediaChunkedHandler(
        AsyncMock(), user_id="user-uuid-001", site_id="site-uuid-001", alias="myblog"
    )
    session = type("Session", (), {"id": "session-1", "to_public_dict": lambda self: {}})()

    payload = handler._public_session_payload(session)

    assert payload["upload"]["url"] == (
        "https://mcp.example.com/u/user-uuid-001/myblog/media-upload/session-1"
    )


@pytest.mark.asyncio
async def test_admin_media_upload_handler_accepts_master_key_and_admin_session(
    store: UploadSessionStore,
):
    payload = b"admin binary upload"
    sess = await store.start(user_id="admin", filename="hero.png", total_bytes=len(payload))
    request = _make_upload_request(
        sess.id,
        body=payload,
        token="master-secret",
    )

    with patch("core.auth.get_auth_manager") as auth_factory:
        auth_factory.return_value.validate_master_key.return_value = True
        response = await admin_media_upload_handler(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["session_id"] == sess.id
    assert body["ready_to_finish"] is True
    _, assembled = await store.finalize(sess.id)
    assert assembled == payload


@pytest.mark.asyncio
async def test_admin_media_upload_handler_rejects_non_admin_session(
    store: UploadSessionStore,
):
    sess = await store.start(user_id="user-1", filename="hero.png", total_bytes=3)
    request = _make_upload_request(sess.id, body=b"123", token="master-secret")

    with patch("core.auth.get_auth_manager") as auth_factory:
        auth_factory.return_value.validate_master_key.return_value = True
        response = await admin_media_upload_handler(request)

    assert response.status_code == 403
    assert json.loads(response.body)["error_code"] == "FORBIDDEN"


def test_browser_token_is_scoped_and_not_in_query(monkeypatch):
    monkeypatch.setenv("MCPHUB_UPLOAD_TOKEN_SECRET", "s" * 32)
    url = make_admin_browser_upload_url("session-1")
    assert "#token=mup_" in url
    assert "?token=" not in url
    token = url.split("#token=", 1)[1]
    assert validate_upload_token(token, "session-1", owner="admin")["op"] == "media_upload"
    with pytest.raises(ValueError):
        validate_upload_token(token, "session-2", owner="admin")


@pytest.mark.asyncio
async def test_browser_token_uploads_only_to_its_admin_session(store: UploadSessionStore):
    payload = b"browser bytes"
    sess = await store.start(user_id="admin", filename="hero.png", total_bytes=len(payload))
    url = make_admin_browser_upload_url(sess.id)
    token = url.split("#token=", 1)[1]
    request = _make_upload_request(sess.id, body=payload, token=token)
    response = await admin_media_upload_handler(request)
    assert response.status_code == 200
    assert json.loads(response.body)["ready_to_finish"] is True


@pytest.mark.asyncio
async def test_user_browser_token_uploads_to_user_session(store: UploadSessionStore, mock_db):
    payload = b"user browser bytes"
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "site-uuid-001"),
        filename="hero.png",
        total_bytes=len(payload),
    )
    from core.media_intake import make_browser_upload_url

    url = make_browser_upload_url(
        sess.id,
        owner="user-uuid-001",
        site_id="site-uuid-001",
        alias="myblog",
        upload_path=f"/u/user-uuid-001/myblog/media-upload/{sess.id}",
    )
    token = url.split("#token=", 1)[1]
    request = _make_upload_request(sess.id, body=payload, token=token)
    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_media_upload_handler(request)
    assert response.status_code == 200
    assert json.loads(response.body)["ready_to_finish"] is True


@pytest.mark.asyncio
async def test_admin_browser_page_does_not_echo_secrets(store: UploadSessionStore):
    sess = await store.start(user_id="admin", filename="hero.png", total_bytes=3)
    response = await admin_media_browser_page(_make_browser_request(sess.id))
    assert response.status_code == 200
    body = response.body.decode()
    assert "MASTER_API_KEY" not in body
    assert "Authorization" in body
    assert response.media_type == "text/html"
