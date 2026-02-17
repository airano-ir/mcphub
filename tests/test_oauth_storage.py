import tempfile
from datetime import UTC, datetime, timedelta

import pytest

from core.oauth.schemas import AuthorizationCode, RefreshToken
from core.oauth.storage import JSONStorage


@pytest.fixture
def storage():
    """Create temporary storage for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield JSONStorage(tmpdir)


def test_save_and_get_authorization_code(storage):
    """Test authorization code storage"""
    code = AuthorizationCode(
        code="test_code_123",
        client_id="client_1",
        redirect_uri="http://localhost:3000/callback",
        scope="read write",
        code_challenge="challenge_123",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    # Save
    assert storage.save_authorization_code(code)

    # Get
    retrieved = storage.get_authorization_code("test_code_123")
    assert retrieved is not None
    assert retrieved.code == "test_code_123"
    assert retrieved.client_id == "client_1"


def test_expired_code_auto_cleanup(storage):
    """Test expired code auto-cleanup"""
    code = AuthorizationCode(
        code="expired_code",
        client_id="client_1",
        redirect_uri="http://localhost:3000/callback",
        scope="read",
        code_challenge="challenge",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),  # Expired
    )

    storage.save_authorization_code(code)

    # Should return None and cleanup
    retrieved = storage.get_authorization_code("expired_code")
    assert retrieved is None


def test_refresh_token_revocation(storage):
    """Test refresh token revocation"""
    token = RefreshToken(
        token="refresh_token_123",
        client_id="client_1",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    storage.save_refresh_token(token)

    # Revoke
    assert storage.revoke_refresh_token("refresh_token_123")

    # Should return None
    retrieved = storage.get_refresh_token("refresh_token_123")
    assert retrieved is None
