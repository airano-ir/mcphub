"""
Tests for RFC 8707 resource parameter support in OAuth 2.1 flow.

Validates that the resource parameter is:
1. Accepted and stored in authorization codes
2. Passed through to JWT access tokens as aud claim
3. Optional -- existing flows without resource continue to work
"""

import os
import tempfile
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from core.oauth.schemas import AuthorizationCode
from core.oauth.token_manager import TokenManager


@pytest.fixture
def token_manager():
    """Create a fresh TokenManager for tests."""
    os.environ["OAUTH_JWT_SECRET_KEY"] = "test_secret_key_resource"
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["OAUTH_STORAGE_PATH"] = tmpdir
        yield TokenManager()
    os.environ.pop("OAUTH_JWT_SECRET_KEY", None)
    os.environ.pop("OAUTH_STORAGE_PATH", None)


@pytest.fixture
def temp_storage():
    """Create temporary storage for OAuth server tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["OAUTH_STORAGE_PATH"] = tmpdir
        os.environ["OAUTH_JWT_SECRET_KEY"] = "test_secret_key_resource"

        from core.oauth import client_registry, server, storage, token_manager

        client_registry._client_registry = None
        token_manager._token_manager = None
        storage._storage = None
        server._oauth_server = None

        yield tmpdir

        # Teardown
        os.environ.pop("OAUTH_STORAGE_PATH", None)
        os.environ.pop("OAUTH_JWT_SECRET_KEY", None)
        client_registry._client_registry = None
        token_manager._token_manager = None
        storage._storage = None
        server._oauth_server = None


@pytest.fixture
def oauth_components(temp_storage):
    """Get fresh OAuth components."""
    from core.oauth import get_client_registry, get_oauth_server, get_storage, get_token_manager

    return {
        "server": get_oauth_server(),
        "client_registry": get_client_registry(),
        "token_manager": get_token_manager(),
        "storage": get_storage(),
    }


@pytest.fixture
def test_client(oauth_components):
    """Create a test OAuth client."""
    client_registry = oauth_components["client_registry"]

    client_id, client_secret = client_registry.create_client(
        client_name="Resource Test Client",
        redirect_uris=["http://localhost:3000/callback"],
        grant_types=["authorization_code", "refresh_token"],
        allowed_scopes=["read", "write"],
    )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "http://localhost:3000/callback",
    }


# --- AuthorizationCode schema tests ---


def test_authorization_code_accepts_resource():
    """Test that AuthorizationCode model accepts and stores the resource field."""
    auth_code = AuthorizationCode(
        code="auth_test123",
        client_id="test_client",
        redirect_uri="http://localhost:3000/callback",
        scope="read write",
        code_challenge="abc123",
        code_challenge_method="S256",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        resource="https://mcp.example.com",
    )

    assert auth_code.resource == "https://mcp.example.com"


def test_authorization_code_resource_defaults_to_none():
    """Test that AuthorizationCode resource defaults to None when not provided."""
    auth_code = AuthorizationCode(
        code="auth_test456",
        client_id="test_client",
        redirect_uri="http://localhost:3000/callback",
        scope="read",
        code_challenge="xyz789",
        code_challenge_method="S256",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    assert auth_code.resource is None


# --- create_authorization_code tests ---


def test_create_authorization_code_with_resource(oauth_components, test_client):
    """Test that create_authorization_code accepts and stores resource parameter."""
    from core.oauth import generate_code_challenge, generate_code_verifier

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    oauth_server = oauth_components["server"]
    resource_url = "https://mcp.example.com"

    code = oauth_server.create_authorization_code(
        client_id=test_client["client_id"],
        redirect_uri=test_client["redirect_uri"],
        scope="read write",
        code_challenge=code_challenge,
        code_challenge_method="S256",
        resource=resource_url,
    )

    assert code.startswith("auth_")

    # Verify resource is stored in the authorization code
    stored_code = oauth_components["storage"].get_authorization_code(code)
    assert stored_code is not None
    assert stored_code.resource == resource_url


def test_create_authorization_code_without_resource(oauth_components, test_client):
    """Test that create_authorization_code works without resource (backward compat)."""
    from core.oauth import generate_code_challenge, generate_code_verifier

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    oauth_server = oauth_components["server"]

    code = oauth_server.create_authorization_code(
        client_id=test_client["client_id"],
        redirect_uri=test_client["redirect_uri"],
        scope="read write",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )

    assert code.startswith("auth_")

    stored_code = oauth_components["storage"].get_authorization_code(code)
    assert stored_code is not None
    assert stored_code.resource is None


# --- generate_access_token / JWT aud claim tests ---


def test_generate_access_token_with_resource_sets_aud(token_manager):
    """Test that resource parameter flows through to JWT aud claim."""
    resource_url = "https://mcp.example.com"

    token = token_manager.generate_access_token(
        client_id="test_client",
        scope="read write",
        user_id="user_123",
        resource=resource_url,
    )

    # Decode JWT and verify aud claim
    payload = jwt.decode(
        token,
        "test_secret_key_resource",
        algorithms=["HS256"],
        audience=resource_url,
    )
    assert payload["aud"] == resource_url
    assert payload["client_id"] == "test_client"
    assert payload["sub"] == "user_123"


def test_generate_access_token_without_resource_no_aud(token_manager):
    """Test that JWT has no aud claim when resource is not provided."""
    token = token_manager.generate_access_token(
        client_id="test_client",
        scope="read write",
        user_id="user_123",
    )

    payload = jwt.decode(
        token,
        "test_secret_key_resource",
        algorithms=["HS256"],
    )
    assert "aud" not in payload
    assert payload["client_id"] == "test_client"


def test_generate_access_token_resource_none_no_aud(token_manager):
    """Test that resource=None does not add aud claim."""
    token = token_manager.generate_access_token(
        client_id="test_client",
        scope="read",
        resource=None,
    )

    payload = jwt.decode(
        token,
        "test_secret_key_resource",
        algorithms=["HS256"],
    )
    assert "aud" not in payload


def test_generate_access_token_resource_empty_string_no_aud(token_manager):
    """Test that empty string resource does not add aud claim."""
    token = token_manager.generate_access_token(
        client_id="test_client",
        scope="read",
        resource="",
    )

    payload = jwt.decode(
        token,
        "test_secret_key_resource",
        algorithms=["HS256"],
    )
    assert "aud" not in payload


# --- Full flow: resource through code exchange ---


def test_full_flow_resource_to_jwt_aud(oauth_components, test_client):
    """Test that resource flows from auth code creation through to JWT aud claim."""
    from core.oauth import generate_code_challenge, generate_code_verifier

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    oauth_server = oauth_components["server"]
    resource_url = "https://mcp.example.com"

    # Step 1: Create authorization code with resource
    code = oauth_server.create_authorization_code(
        client_id=test_client["client_id"],
        redirect_uri=test_client["redirect_uri"],
        scope="read write",
        code_challenge=code_challenge,
        code_challenge_method="S256",
        api_key_id="master",
        api_key_project_id="*",
        api_key_scope="read write",
        resource=resource_url,
    )

    # Step 2: Exchange code for tokens
    token_response = oauth_server.exchange_code_for_tokens(
        client_id=test_client["client_id"],
        client_secret=test_client["client_secret"],
        code=code,
        redirect_uri=test_client["redirect_uri"],
        code_verifier=code_verifier,
    )

    # Step 3: Verify JWT contains aud claim
    payload = jwt.decode(
        token_response.access_token,
        os.environ["OAUTH_JWT_SECRET_KEY"],
        algorithms=["HS256"],
        audience=resource_url,
    )
    assert payload["aud"] == resource_url


def test_full_flow_without_resource_no_aud(oauth_components, test_client):
    """Test that full flow without resource produces JWT without aud claim."""
    from core.oauth import generate_code_challenge, generate_code_verifier

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    oauth_server = oauth_components["server"]

    # Step 1: Create authorization code WITHOUT resource
    code = oauth_server.create_authorization_code(
        client_id=test_client["client_id"],
        redirect_uri=test_client["redirect_uri"],
        scope="read write",
        code_challenge=code_challenge,
        code_challenge_method="S256",
        api_key_id="master",
        api_key_project_id="*",
        api_key_scope="read write",
    )

    # Step 2: Exchange code for tokens
    token_response = oauth_server.exchange_code_for_tokens(
        client_id=test_client["client_id"],
        client_secret=test_client["client_secret"],
        code=code,
        redirect_uri=test_client["redirect_uri"],
        code_verifier=code_verifier,
    )

    # Step 3: Verify JWT does NOT contain aud claim
    payload = jwt.decode(
        token_response.access_token,
        os.environ["OAUTH_JWT_SECRET_KEY"],
        algorithms=["HS256"],
    )
    assert "aud" not in payload
