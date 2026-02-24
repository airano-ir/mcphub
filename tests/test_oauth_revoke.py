"""Tests for OAuth 2.0 Token Revocation endpoint (RFC 7009)."""

import base64
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_request(headers=None, body=None, content_type="application/x-www-form-urlencoded"):
    """Create a mock Starlette Request for oauth_revoke."""
    request = AsyncMock()
    request.headers = MagicMock()
    _headers = {"content-type": content_type}
    if headers:
        _headers.update(headers)
    request.headers.get = lambda key, default="": _headers.get(key.lower(), default)

    form_data = body or {}
    form = AsyncMock(return_value=form_data)
    request.form = form

    if "application/json" in content_type:
        request.json = AsyncMock(return_value=form_data)

    return request


def _encode_basic(client_id: str, client_secret: str) -> str:
    """Encode client_id:client_secret as Basic Auth header value."""
    raw = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


@pytest.fixture
def temp_storage():
    """Create temporary storage for OAuth tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["OAUTH_STORAGE_PATH"] = tmpdir
        os.environ["OAUTH_JWT_SECRET_KEY"] = "test_secret_key_for_revoke_tests"

        from core.oauth import client_registry, server, storage, token_manager

        client_registry._client_registry = None
        token_manager._token_manager = None
        storage._storage = None
        server._oauth_server = None

        yield tmpdir

        os.environ.pop("OAUTH_STORAGE_PATH", None)
        os.environ.pop("OAUTH_JWT_SECRET_KEY", None)

        client_registry._client_registry = None
        token_manager._token_manager = None
        storage._storage = None
        server._oauth_server = None


@pytest.fixture
def registered_client(temp_storage):
    """Create a registered OAuth client and return (client_id, client_secret)."""
    from core.oauth import get_client_registry

    registry = get_client_registry()
    client_id, client_secret = registry.create_client(
        client_name="Test Revoke Client",
        redirect_uris=["http://localhost:3000/callback"],
    )
    return client_id, client_secret


async def _call_oauth_revoke(request):
    """Import and call the oauth_revoke endpoint from server.py."""
    from server import oauth_revoke

    return await oauth_revoke(request)


@pytest.mark.unit
class TestOAuthRevoke:
    """Tests for the /oauth/revoke endpoint (RFC 7009)."""

    async def test_valid_token_revocation_returns_200(self, registered_client):
        """Valid token revocation returns 200 with empty body."""
        client_id, client_secret = registered_client

        request = _make_request(
            body={
                "client_id": client_id,
                "client_secret": client_secret,
                "token": "rt_some_refresh_token",
            },
        )

        response = await _call_oauth_revoke(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data == {}

    async def test_missing_token_returns_200(self, registered_client):
        """Per RFC 7009, missing token returns 200 (no-op)."""
        client_id, client_secret = registered_client

        request = _make_request(
            body={
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

        response = await _call_oauth_revoke(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data == {}

    async def test_invalid_client_credentials_returns_401(self, registered_client):
        """Invalid client credentials return 401 with invalid_client error."""
        client_id, _ = registered_client

        request = _make_request(
            body={
                "client_id": client_id,
                "client_secret": "wrong_secret",
                "token": "rt_some_token",
            },
        )

        response = await _call_oauth_revoke(request)

        assert response.status_code == 401
        data = json.loads(response.body)
        assert data["error"] == "invalid_client"
        assert "Invalid client credentials" in data["error_description"]

    async def test_missing_client_credentials_returns_401(self, temp_storage):
        """Missing client credentials return 401 with invalid_client error."""
        request = _make_request(
            body={
                "token": "rt_some_token",
            },
        )

        response = await _call_oauth_revoke(request)

        assert response.status_code == 401
        data = json.loads(response.body)
        assert data["error"] == "invalid_client"
        assert "Client authentication required" in data["error_description"]

    async def test_revocation_with_refresh_token_hint(self, registered_client):
        """Revocation with token_type_hint=refresh_token works correctly."""
        client_id, client_secret = registered_client

        request = _make_request(
            body={
                "client_id": client_id,
                "client_secret": client_secret,
                "token": "some_token_value",
                "token_type_hint": "refresh_token",
            },
        )

        response = await _call_oauth_revoke(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data == {}

    async def test_unknown_token_returns_200(self, registered_client):
        """Per RFC 7009, revoking an unknown/invalid token still returns 200."""
        client_id, client_secret = registered_client

        request = _make_request(
            body={
                "client_id": client_id,
                "client_secret": client_secret,
                "token": "completely_nonexistent_token_xyz",
            },
        )

        response = await _call_oauth_revoke(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data == {}

    async def test_basic_auth_works_for_revocation(self, registered_client):
        """Client authentication via Basic Auth header works on the revoke endpoint."""
        client_id, client_secret = registered_client

        request = _make_request(
            headers={"authorization": _encode_basic(client_id, client_secret)},
            body={
                "token": "rt_some_refresh_token",
            },
        )

        response = await _call_oauth_revoke(request)

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data == {}

    async def test_metadata_includes_revocation_endpoint(self, temp_storage):
        """OAuth metadata includes the revocation_endpoint field."""
        from server import oauth_metadata

        # Create a mock request with a host header
        request = AsyncMock()
        request.headers = MagicMock()
        _headers = {"host": "localhost:8000"}
        request.headers.get = lambda key, default="": _headers.get(key.lower(), default)
        request.url = MagicMock()
        request.url.scheme = "http"

        response = await oauth_metadata(request)

        data = json.loads(response.body)
        assert "revocation_endpoint" in data
        assert data["revocation_endpoint"].endswith("/oauth/revoke")
        assert "client_secret_basic" in data.get("revocation_endpoint_auth_methods_supported", [])
