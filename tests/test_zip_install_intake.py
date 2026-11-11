"""Tests for HTTP binary WordPress install-zip intake."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from core.database import Database
from core.upload_sessions import (
    UploadSessionStore,
    make_session_owner_id,
    set_upload_session_store,
)
from core.zip_install_intake import user_zip_install_upload_handler
from core.zip_install_sessions import ZIP_INSTALL_SESSION_MIME


def _make_upload_request(
    session_id: str,
    *,
    body: bytes,
    user_id: str = "user-uuid-001",
    alias: str = "specialist",
    token: str = "mhu_validkey1234567890abcdefghijklmnopqrst",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope_headers = [
        (b"authorization", f"Bearer {token}".encode()),
        (b"content-type", b"application/zip"),
    ]
    if headers:
        scope_headers.extend(headers)

    scope = {
        "type": "http",
        "method": "PUT",
        "path": f"/u/{user_id}/{alias}/zip-install-upload/{session_id}",
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
            "scopes": "read write admin",
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
            "plugin_type": "wordpress_specialist",
            "alias": "specialist",
            "url": "https://wp.example.com",
            "status": "active",
            "tool_scope": "admin",
        }
    )
    db.get_user_by_id = AsyncMock(return_value={"id": "user-uuid-001", "role": "user"})
    db.get_site_tool_toggles = AsyncMock(return_value={})
    with patch("core.database.get_database", return_value=db):
        yield db


@pytest.mark.asyncio
async def test_user_zip_install_upload_handler_appends_raw_bytes(
    store: UploadSessionStore,
    mock_key_mgr,
    mock_db,
):
    payload = b"PK\x03\x04 pretend zip bytes for staging"
    digest = hashlib.sha256(payload).hexdigest()
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "site-uuid-001"),
        filename="plugin.zip",
        total_bytes=len(payload),
        mime=ZIP_INSTALL_SESSION_MIME,
        sha256=digest,
    )
    request = _make_upload_request(
        sess.id,
        body=payload,
        headers=[(b"x-mcphub-chunk-sha256", digest.encode())],
    )

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_zip_install_upload_handler(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["session_id"] == sess.id
    assert body["received_bytes"] == len(payload)
    assert body["ready_to_install"] is True
    assert body["install_tools"] == [
        "wordpress_specialist_wp_plugin_install_from_zip",
        "wordpress_specialist_wp_theme_install_from_zip",
    ]

    _, data = await store.finalize(sess.id)
    assert data == payload


@pytest.mark.asyncio
async def test_user_zip_install_upload_handler_requires_admin_scope(
    store: UploadSessionStore,
    mock_key_mgr,
    mock_db,
):
    mock_key_mgr.validate_key.return_value = {
        "key_id": "key-uuid-001",
        "user_id": "user-uuid-001",
        "scopes": "read write",
        "site_id": None,
    }
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "site-uuid-001"),
        filename="plugin.zip",
        total_bytes=5,
        mime=ZIP_INSTALL_SESSION_MIME,
    )

    response = await user_zip_install_upload_handler(_make_upload_request(sess.id, body=b"12345"))

    assert response.status_code == 403
    body = json.loads(response.body)
    assert body["error_code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_user_zip_install_upload_handler_rejects_wrong_site_owner(
    store: UploadSessionStore,
    mock_key_mgr,
    mock_db,
):
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "other-site"),
        filename="plugin.zip",
        total_bytes=5,
        mime=ZIP_INSTALL_SESSION_MIME,
    )
    request = _make_upload_request(sess.id, body=b"12345")

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_zip_install_upload_handler(request)

    assert response.status_code == 403
    body = json.loads(response.body)
    assert body["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_user_zip_install_upload_handler_rejects_media_session(
    store: UploadSessionStore,
    mock_key_mgr,
    mock_db,
):
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "site-uuid-001"),
        filename="hero.png",
        total_bytes=5,
        mime="image/png",
    )
    request = _make_upload_request(sess.id, body=b"12345")

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_zip_install_upload_handler(request)

    assert response.status_code == 409
    body = json.loads(response.body)
    assert body["error_code"] == "BAD_SESSION_TYPE"


@pytest.mark.asyncio
async def test_user_zip_install_upload_handler_rejects_non_specialist_site(
    store: UploadSessionStore,
    mock_key_mgr,
    mock_db,
):
    mock_db.get_site_by_alias.return_value = {
        "id": "site-uuid-001",
        "user_id": "user-uuid-001",
        "plugin_type": "wordpress",
        "alias": "myblog",
        "url": "https://wp.example.com",
        "status": "active",
        "tool_scope": "admin",
    }
    sess = await store.start(
        user_id=make_session_owner_id("user-uuid-001", "site-uuid-001"),
        filename="plugin.zip",
        total_bytes=5,
        mime=ZIP_INSTALL_SESSION_MIME,
    )

    response = await user_zip_install_upload_handler(_make_upload_request(sess.id, body=b"12345"))

    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error_code"] == "UNSUPPORTED_SITE_TYPE"
