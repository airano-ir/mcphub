from datetime import UTC, datetime, timedelta

import pytest

from core.oauth.schemas import AuthorizationCode, OAuthClient


def test_oauth_client_validation():
    """Test OAuth client validation"""
    client = OAuthClient(
        client_id="cmp_client_test",
        client_secret_hash="sha256_hash",
        client_name="Test Client",
        redirect_uris=["http://localhost:3000/callback"],
    )

    assert client.client_id == "cmp_client_test"
    assert "authorization_code" in client.grant_types
    assert "read" in client.allowed_scopes


def test_invalid_redirect_uri():
    """Test invalid redirect URI"""
    with pytest.raises(ValueError, match="Invalid redirect URI"):
        OAuthClient(
            client_id="test",
            client_secret_hash="hash",
            client_name="Test",
            redirect_uris=["invalid-uri"],  # Missing http://
        )


def test_authorization_code_expiry():
    """Test authorization code expiry"""
    code = AuthorizationCode(
        code="test_code",
        client_id="client1",
        redirect_uri="http://localhost:3000/callback",
        scope="read",
        code_challenge="challenge",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),  # Expired
    )

    assert code.is_expired()
