"""
OAuth 2.1 Integration Tests

Tests the complete OAuth flow end-to-end:
1. Client registration
2. Authorization request
3. Authorization code generation
4. Token exchange
5. Token refresh
6. JWT validation
"""

import os
import tempfile

import pytest

from core.oauth import (
    OAuthError,
    generate_code_challenge,
    generate_code_verifier,
    get_client_registry,
    get_oauth_server,
    get_storage,
    get_token_manager,
)


@pytest.fixture
def temp_storage():
    """Create temporary storage for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set environment for storage
        os.environ["OAUTH_STORAGE_PATH"] = tmpdir
        os.environ["OAUTH_JWT_SECRET_KEY"] = "test_secret_key_for_integration_tests"

        # Reset singletons by clearing them
        from core.oauth import client_registry, server, storage, token_manager

        client_registry._client_registry = None
        token_manager._token_manager = None
        storage._storage = None
        server._oauth_server = None

        yield tmpdir


@pytest.fixture
def oauth_components(temp_storage):
    """Get fresh OAuth components"""
    return {
        "server": get_oauth_server(),
        "client_registry": get_client_registry(),
        "token_manager": get_token_manager(),
        "storage": get_storage(),
    }


@pytest.fixture
def test_client(oauth_components):
    """Create a test OAuth client"""
    client_registry = oauth_components["client_registry"]

    client_id, client_secret = client_registry.create_client(
        client_name="Test Client",
        redirect_uris=["http://localhost:3000/callback"],
        grant_types=["authorization_code", "refresh_token", "client_credentials"],
        allowed_scopes=["read", "write", "admin"],
    )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "http://localhost:3000/callback",
    }


def test_full_authorization_code_flow(oauth_components, test_client):
    """
    Test complete Authorization Code flow with PKCE

    Steps:
        1. Generate PKCE verifier/challenge
        2. Validate authorization request
        3. Create authorization code
        4. Exchange code for tokens
        5. Validate access token
        6. Refresh access token
    """
    server = oauth_components["server"]
    token_manager = oauth_components["token_manager"]

    # Step 1: Generate PKCE
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Step 2: Validate authorization request
    validated = server.validate_authorization_request(
        client_id=test_client["client_id"],
        redirect_uri=test_client["redirect_uri"],
        response_type="code",
        code_challenge=code_challenge,
        code_challenge_method="S256",
        scope="read write",
        state="random_state_token",
    )

    assert validated["client_id"] == test_client["client_id"]
    assert validated["scope"] == "read write"
    assert validated["state"] == "random_state_token"

    # Step 3: Create authorization code
    auth_code = server.create_authorization_code(
        client_id=validated["client_id"],
        redirect_uri=validated["redirect_uri"],
        scope=validated["scope"],
        code_challenge=validated["code_challenge"],
        code_challenge_method=validated["code_challenge_method"],
    )

    assert auth_code.startswith("auth_")

    # Step 4: Exchange code for tokens
    token_response = server.exchange_code_for_tokens(
        client_id=test_client["client_id"],
        client_secret=test_client["client_secret"],
        code=auth_code,
        redirect_uri=test_client["redirect_uri"],
        code_verifier=code_verifier,
    )

    assert token_response.access_token
    assert token_response.refresh_token
    assert token_response.token_type == "Bearer"
    assert token_response.expires_in > 0
    assert token_response.scope == "read write"

    # Step 5: Validate access token
    payload = token_manager.validate_access_token(token_response.access_token)

    assert payload["client_id"] == test_client["client_id"]
    assert payload["scope"] == "read write"
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload

    # Step 6: Refresh access token
    new_tokens = server.handle_refresh_token_grant(
        client_id=test_client["client_id"],
        client_secret=test_client["client_secret"],
        refresh_token=token_response.refresh_token,
    )

    assert new_tokens.access_token != token_response.access_token
    assert new_tokens.refresh_token != token_response.refresh_token
    assert new_tokens.scope == "read write"


def test_client_credentials_flow(oauth_components, test_client):
    """
    Test Client Credentials flow (machine-to-machine)
    """
    server = oauth_components["server"]
    token_manager = oauth_components["token_manager"]

    # Request token with client credentials
    token_response = server.handle_client_credentials_grant(
        client_id=test_client["client_id"], client_secret=test_client["client_secret"], scope="read"
    )

    assert token_response.access_token
    assert token_response.refresh_token is None  # No refresh token for client credentials
    assert token_response.scope == "read"

    # Validate token
    payload = token_manager.validate_access_token(token_response.access_token)

    assert payload["client_id"] == test_client["client_id"]
    assert payload["scope"] == "read"


def test_pkce_validation_failure(oauth_components, test_client):
    """Test that PKCE validation fails with wrong code_verifier"""
    server = oauth_components["server"]

    # Generate PKCE
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Create authorization code
    validated = server.validate_authorization_request(
        client_id=test_client["client_id"],
        redirect_uri=test_client["redirect_uri"],
        response_type="code",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )

    auth_code = server.create_authorization_code(
        client_id=validated["client_id"],
        redirect_uri=validated["redirect_uri"],
        scope=validated["scope"],
        code_challenge=validated["code_challenge"],
        code_challenge_method=validated["code_challenge_method"],
    )

    # Try to exchange with WRONG code_verifier
    wrong_verifier = generate_code_verifier()

    with pytest.raises(OAuthError, match="PKCE validation failed"):
        server.exchange_code_for_tokens(
            client_id=test_client["client_id"],
            client_secret=test_client["client_secret"],
            code=auth_code,
            redirect_uri=test_client["redirect_uri"],
            code_verifier=wrong_verifier,  # WRONG!
        )


def test_authorization_code_reuse_detection(oauth_components, test_client):
    """Test that reusing an authorization code is detected"""
    server = oauth_components["server"]

    # Generate PKCE and authorization code
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    validated = server.validate_authorization_request(
        client_id=test_client["client_id"],
        redirect_uri=test_client["redirect_uri"],
        response_type="code",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )

    auth_code = server.create_authorization_code(
        client_id=validated["client_id"],
        redirect_uri=validated["redirect_uri"],
        scope=validated["scope"],
        code_challenge=validated["code_challenge"],
        code_challenge_method=validated["code_challenge_method"],
    )

    # First exchange - should succeed
    token_response = server.exchange_code_for_tokens(
        client_id=test_client["client_id"],
        client_secret=test_client["client_secret"],
        code=auth_code,
        redirect_uri=test_client["redirect_uri"],
        code_verifier=code_verifier,
    )

    assert token_response.access_token

    # Second exchange with same code - should fail
    with pytest.raises(OAuthError, match="already used"):
        server.exchange_code_for_tokens(
            client_id=test_client["client_id"],
            client_secret=test_client["client_secret"],
            code=auth_code,
            redirect_uri=test_client["redirect_uri"],
            code_verifier=code_verifier,
        )


def test_invalid_client_credentials(oauth_components, test_client):
    """Test that invalid client credentials are rejected"""
    server = oauth_components["server"]

    # Try with wrong client secret
    with pytest.raises(OAuthError, match="Invalid client credentials"):
        server.handle_client_credentials_grant(
            client_id=test_client["client_id"], client_secret="wrong_secret", scope="read"
        )


def test_scope_validation(oauth_components, test_client):
    """Test that invalid scopes are rejected"""
    server = oauth_components["server"]

    # Try to request invalid scope
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    with pytest.raises(OAuthError, match="not allowed"):
        server.validate_authorization_request(
            client_id=test_client["client_id"],
            redirect_uri=test_client["redirect_uri"],
            response_type="code",
            code_challenge=code_challenge,
            code_challenge_method="S256",
            scope="invalid_scope",  # Not in allowed_scopes
        )


def test_redirect_uri_validation(oauth_components, test_client):
    """Test that invalid redirect URIs are rejected"""
    server = oauth_components["server"]

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Try with unregistered redirect_uri
    with pytest.raises(OAuthError, match="Invalid redirect_uri"):
        server.validate_authorization_request(
            client_id=test_client["client_id"],
            redirect_uri="http://evil.com/callback",  # Not registered!
            response_type="code",
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )


def test_expired_token(oauth_components, test_client):
    """Test that expired JWT tokens are rejected"""
    import time

    import jwt as pyjwt

    token_manager = oauth_components["token_manager"]

    # Set very short TTL
    original_ttl = token_manager.access_token_ttl
    token_manager.access_token_ttl = 1  # 1 second

    # Generate token
    access_token = token_manager.generate_access_token(
        client_id=test_client["client_id"], scope="read"
    )

    # Wait for expiration
    time.sleep(2)

    # Try to validate expired token
    with pytest.raises(pyjwt.ExpiredSignatureError):
        token_manager.validate_access_token(access_token)

    # Restore original TTL
    token_manager.access_token_ttl = original_ttl
