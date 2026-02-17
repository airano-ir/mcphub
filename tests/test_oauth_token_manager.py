import os
import tempfile

import jwt
import pytest

from core.oauth.token_manager import SecurityError, TokenManager


@pytest.fixture
def token_manager():
    os.environ["OAUTH_JWT_SECRET_KEY"] = "test_secret_key"
    # Use temporary directory for storage
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["OAUTH_STORAGE_PATH"] = tmpdir
        yield TokenManager()


def test_generate_access_token(token_manager):
    """Test access token generation"""
    token = token_manager.generate_access_token(
        client_id="test_client", scope="read write", user_id="user_123"
    )

    # Should be valid JWT
    assert len(token.split(".")) == 3

    # Validate
    payload = token_manager.validate_access_token(token)
    assert payload["client_id"] == "test_client"
    assert payload["scope"] == "read write"
    assert payload["sub"] == "user_123"


def test_access_token_expiry(token_manager):
    """Test expired token"""
    # Generate with short TTL
    token_manager.access_token_ttl = 1
    token = token_manager.generate_access_token("client", "read")

    import time

    time.sleep(2)

    # Should raise
    with pytest.raises(jwt.ExpiredSignatureError):
        token_manager.validate_access_token(token)


def test_refresh_token_rotation(token_manager):
    """Test refresh token rotation"""
    # Generate initial tokens
    access_token = token_manager.generate_access_token("client", "read")
    refresh_token = token_manager.generate_refresh_token("client", access_token)

    # Rotate
    new_tokens = token_manager.rotate_refresh_token(refresh_token, "client")

    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != refresh_token

    # Old token should be revoked - reuse triggers SecurityError
    with pytest.raises(SecurityError, match="reuse detected"):
        token_manager.rotate_refresh_token(refresh_token, "client")


def test_refresh_token_reuse_detection(token_manager):
    """Test reuse detection"""
    access_token = token_manager.generate_access_token("client", "read")
    refresh_token = token_manager.generate_refresh_token("client", access_token)

    # First rotation
    token_manager.rotate_refresh_token(refresh_token, "client")

    # Attempt reuse
    with pytest.raises(SecurityError, match="reuse detected"):
        token_manager.rotate_refresh_token(refresh_token, "client")
