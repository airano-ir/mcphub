"""Tests for Gitea HTTP binary upload intake."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from starlette.requests import Request

from core.database import Database
from core.gitea_intake import user_gitea_upload_handler
from core.gitea_upload_sessions import get_gitea_upload_metadata
from core.upload_sessions import UploadSessionStore, set_upload_session_store
from plugins.gitea.client import GiteaClient
from plugins.gitea.handlers.uploads import GiteaUploadHandler

USER_ID = "user-uuid-001"
SITE_ID = "site-uuid-001"
ALIAS = "git"
TOKEN = "mhu_validkey1234567890abcdefghijklmnopqrst"


def _make_upload_request(
    session_id: str,
    *,
    body: bytes,
    user_id: str = USER_ID,
    alias: str = ALIAS,
    token: str = TOKEN,
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
        "path": f"/u/{user_id}/{alias}/gitea-upload/{session_id}",
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
def client() -> GiteaClient:
    c = GiteaClient(site_url="https://git.example.com", token="tk")
    c.upload_release_asset_bytes = AsyncMock(return_value={"id": 7, "name": "artifact.zip"})
    return c


@pytest.fixture
def handler(store: UploadSessionStore, client: GiteaClient) -> GiteaUploadHandler:
    return GiteaUploadHandler(
        client,
        user_id=USER_ID,
        site_id=SITE_ID,
        alias=ALIAS,
        store=store,
    )


@pytest.fixture
def mock_key_mgr():
    mgr = AsyncMock()
    mgr.validate_key = AsyncMock(
        return_value={
            "key_id": "key-uuid-001",
            "user_id": USER_ID,
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
            "id": SITE_ID,
            "user_id": USER_ID,
            "plugin_type": "gitea",
            "alias": ALIAS,
            "url": "https://git.example.com",
            "status": "active",
            "tool_scope": "admin",
        }
    )
    db.get_user_by_id = AsyncMock(return_value={"id": USER_ID, "role": "user"})
    db.get_site_tool_toggles = AsyncMock(return_value={})
    with patch("core.database.get_database", return_value=db):
        yield db


async def _start_release_asset(
    handler: GiteaUploadHandler,
    payload: bytes,
    *,
    sha256: str | None = None,
) -> dict:
    out = await handler.upload_start(
        owner="airano",
        repo="mcphub",
        release_id=123,
        filename="artifact.zip",
        total_bytes=len(payload),
        sha256=sha256,
    )
    return json.loads(out)


@pytest.mark.asyncio
async def test_gitea_upload_start_returns_http_upload_url(
    store: UploadSessionStore,
    handler: GiteaUploadHandler,
):
    payload = b"release asset bytes"
    digest = hashlib.sha256(payload).hexdigest()

    body = await _start_release_asset(handler, payload, sha256=digest)

    assert body["handoff"] == "http_binary_put"
    assert body["upload"]["url"] == f"/u/{USER_ID}/{ALIAS}/gitea-upload/{body['session_id']}"
    assert body["kind"] == "release_asset"
    assert body["target"] == {
        "owner": "airano",
        "repo": "mcphub",
        "release_id": 123,
        "filename": "artifact.zip",
    }
    assert body["max_bytes"] > 0


@pytest.mark.asyncio
async def test_gitea_upload_url_uses_public_url_for_external_clients(
    store: UploadSessionStore,
    handler: GiteaUploadHandler,
    monkeypatch,
):
    monkeypatch.setenv("PUBLIC_URL", "https://mcp.example.com/")
    body = await _start_release_asset(handler, b"release asset bytes")

    assert body["upload"]["url"].startswith("https://mcp.example.com/")

    sess = await store.get(body["session_id"])
    assert sess is not None
    meta = await get_gitea_upload_metadata(store.db, body["session_id"])
    assert meta is not None
    assert meta.site_id == SITE_ID
    assert meta.plugin_type == "gitea"


@pytest.mark.asyncio
async def test_gitea_http_endpoint_accepts_raw_bytes(
    store: UploadSessionStore,
    handler: GiteaUploadHandler,
    mock_key_mgr,
    mock_db,
):
    payload = b"asset over http"
    digest = hashlib.sha256(payload).hexdigest()
    started = await _start_release_asset(handler, payload, sha256=digest)
    request = _make_upload_request(
        started["session_id"],
        body=payload,
        headers=[(b"x-mcphub-chunk-sha256", digest.encode())],
    )

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_gitea_upload_handler(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["received_bytes"] == len(payload)
    assert body["ready_to_finish"] is True
    assert body["finish_tool"] == "gitea_upload_finish"

    _, assembled = await store.finalize(started["session_id"])
    assert assembled == payload


@pytest.mark.asyncio
async def test_gitea_upload_finish_sends_original_bytes_to_release_asset(
    handler: GiteaUploadHandler,
    client: GiteaClient,
):
    payload = b"zip\x00bytes"
    digest = hashlib.sha256(payload).hexdigest()
    started = await _start_release_asset(handler, payload, sha256=digest)
    await handler.upload_chunk(
        started["session_id"],
        0,
        base64.b64encode(payload).decode(),
    )

    result = json.loads(await handler.upload_finish(started["session_id"]))

    assert result["success"] is True
    assert result["bytes_uploaded"] == len(payload)
    client.upload_release_asset_bytes.assert_awaited_once_with(
        "airano",
        "mcphub",
        123,
        filename="artifact.zip",
        content=payload,
    )


@pytest.mark.asyncio
async def test_gitea_small_base64_release_asset_tool_still_works(
    client: GiteaClient,
    handler: GiteaUploadHandler,
):
    payload = b"small asset"

    out = json.loads(
        await handler.upload_release_asset(
            owner="airano",
            repo="mcphub",
            release_id=123,
            filename="small.bin",
            content_b64=base64.b64encode(payload).decode(),
        )
    )

    assert out["success"] is True
    client.upload_release_asset_bytes.assert_awaited_once_with(
        "airano",
        "mcphub",
        123,
        filename="small.bin",
        content=payload,
    )


@pytest.mark.asyncio
async def test_gitea_client_upload_release_asset_bytes_uses_multipart(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 201

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def text(self):
            return '{"id": 7, "name": "asset.bin"}'

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def post(self, url, *, params, data, headers):
            captured.update(url=url, params=params, data=data, headers=headers)
            return FakeResponse()

    monkeypatch.setattr("plugins.gitea.client.net_guard.client_session", lambda **_: FakeSession())
    c = GiteaClient(site_url="https://git.example.com", token="tk")

    out = await c.upload_release_asset_bytes(
        "airano",
        "mcphub",
        123,
        filename="asset.bin",
        content=b"bytes",
    )

    assert out["id"] == 7
    assert (
        captured["url"] == "https://git.example.com/api/v1/repos/airano/mcphub/releases/123/assets"
    )
    assert captured["params"] == {"name": "asset.bin"}
    assert isinstance(captured["data"], aiohttp.FormData)
    assert captured["headers"]["Authorization"] == "token tk"


@pytest.mark.asyncio
async def test_gitea_endpoint_rejects_wrong_session_owner(
    handler: GiteaUploadHandler,
    mock_key_mgr,
    mock_db,
):
    other_handler = GiteaUploadHandler(
        handler.client,
        user_id="other-user",
        site_id=SITE_ID,
        alias=ALIAS,
        store=handler.store,
    )
    started = await _start_release_asset(other_handler, b"12345")

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_gitea_upload_handler(
            _make_upload_request(started["session_id"], body=b"12345")
        )

    assert response.status_code == 403
    assert json.loads(response.body)["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_gitea_endpoint_rejects_wrong_plugin_type(
    handler: GiteaUploadHandler,
    mock_key_mgr,
    mock_db,
):
    mock_db.get_site_by_alias.return_value["plugin_type"] = "wordpress"
    started = await _start_release_asset(handler, b"12345")

    response = await user_gitea_upload_handler(
        _make_upload_request(started["session_id"], body=b"12345")
    )

    assert response.status_code == 404
    assert json.loads(response.body)["error_code"] == "UNSUPPORTED_SITE_TYPE"


@pytest.mark.asyncio
async def test_gitea_endpoint_rejects_expired_session(
    store: UploadSessionStore,
    handler: GiteaUploadHandler,
    mock_key_mgr,
    mock_db,
):
    started = await _start_release_asset(handler, b"12345")
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    await store.db.execute(
        "UPDATE upload_sessions SET expires_at = ? WHERE id = ?",
        (past, started["session_id"]),
    )

    with patch("core.plugin_visibility.is_plugin_public", return_value=True):
        response = await user_gitea_upload_handler(
            _make_upload_request(started["session_id"], body=b"12345")
        )

    assert response.status_code == 410
    assert json.loads(response.body)["error_code"] == "EXPIRED"


@pytest.mark.asyncio
async def test_gitea_upload_start_rejects_size_limit(handler: GiteaUploadHandler):
    out = json.loads(
        await handler.upload_start(
            owner="airano",
            repo="mcphub",
            release_id=123,
            filename="too-large.bin",
            total_bytes=handler._max_bytes() + 1,
        )
    )

    assert out["error_code"] == "SESSION_TOO_LARGE"


@pytest.mark.asyncio
async def test_gitea_upload_finish_rejects_sha256_mismatch(handler: GiteaUploadHandler):
    payload = b"actual bytes"
    wrong_digest = hashlib.sha256(b"different").hexdigest()
    started = await _start_release_asset(handler, payload, sha256=wrong_digest)
    await handler.upload_chunk(
        started["session_id"],
        0,
        base64.b64encode(payload).decode(),
    )

    out = json.loads(await handler.upload_finish(started["session_id"]))

    assert out["error_code"] == "CHECKSUM_MISMATCH"


@pytest.mark.asyncio
async def test_gitea_endpoint_rejects_disabled_tool(
    handler: GiteaUploadHandler,
    mock_key_mgr,
    mock_db,
):
    mock_db.get_site_tool_toggles.return_value = {"gitea_upload_chunk": False}
    started = await _start_release_asset(handler, b"12345")

    response = await user_gitea_upload_handler(
        _make_upload_request(started["session_id"], body=b"12345")
    )

    assert response.status_code == 403
    assert json.loads(response.body)["error_code"] == "TOOL_DISABLED"
