"""Tests for the user authentication system (OAuth Social Login)."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.user_auth import (
    OAuthProvider,
    UserAuth,
    get_user_auth,
    initialize_user_auth,
)

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global UserAuth singleton between tests."""
    import core.user_auth as mod

    mod._user_auth = None
    yield
    mod._user_auth = None


@pytest.fixture
def user_auth():
    """Create a UserAuth instance with test credentials."""
    return UserAuth(
        github_client_id="gh_test_id",
        github_client_secret="gh_test_secret",
        google_client_id="google_test_id",
        google_client_secret="google_test_secret",
        public_url="https://mcp.example.com",
    )


# ── OAuth URL Generation ─────────────────────────────────────


class TestOAuthURLGeneration:
    """Test OAuth authorization URL generation."""

    def test_github_auth_url(self, user_auth):
        """GitHub auth URL should point to correct endpoint."""
        url, state = user_auth.get_authorization_url("github")
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=gh_test_id" in url
        assert "state=" in url
        assert len(state) == 64  # 32 bytes hex

    def test_google_auth_url(self, user_auth):
        """Google auth URL should point to correct endpoint."""
        url, state = user_auth.get_authorization_url("google")
        assert "accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=google_test_id" in url
        assert "state=" in url

    def test_github_callback_url(self, user_auth):
        """GitHub auth URL should include correct callback URL."""
        from urllib.parse import unquote

        url, _ = user_auth.get_authorization_url("github")
        decoded = unquote(url)
        assert "redirect_uri=" in url
        assert "mcp.example.com" in decoded
        assert "/auth/callback/github" in decoded

    def test_google_callback_url(self, user_auth):
        """Google auth URL should include correct callback URL."""
        from urllib.parse import unquote

        url, _ = user_auth.get_authorization_url("google")
        decoded = unquote(url)
        assert "redirect_uri=" in url
        assert "/auth/callback/google" in decoded

    def test_google_scopes(self, user_auth):
        """Google auth URL should request openid, email, and profile scopes."""
        url, _ = user_auth.get_authorization_url("google")
        assert "openid" in url
        assert "email" in url
        assert "profile" in url

    def test_invalid_provider(self, user_auth):
        """Unsupported provider should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            user_auth.get_authorization_url("twitter")


# ── State Validation ──────────────────────────────────────────


class TestStateValidation:
    """Test OAuth state parameter validation (CSRF protection)."""

    def test_valid_state(self, user_auth):
        """A freshly generated state should validate successfully."""
        _, state = user_auth.get_authorization_url("github")
        assert user_auth.validate_state(state) is True

    def test_invalid_state(self, user_auth):
        """An unknown state string should not validate."""
        assert user_auth.validate_state("invalid_state_value") is False

    def test_state_consumed_after_use(self, user_auth):
        """State token should be one-time use (consumed after validation)."""
        _, state = user_auth.get_authorization_url("github")
        assert user_auth.validate_state(state) is True
        assert user_auth.validate_state(state) is False  # Second use fails

    def test_state_expiry(self, user_auth):
        """State token should be rejected after expiry (10 minutes)."""
        _, state = user_auth.get_authorization_url("github")
        # Manually expire the state (11+ minutes ago)
        user_auth._pending_states[state] = time.time() - 700
        assert user_auth.validate_state(state) is False


# ── Token Exchange (Mocked) ──────────────────────────────────


class TestTokenExchange:
    """Test OAuth token exchange with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_github_token_exchange(self, user_auth):
        """GitHub code exchange should return correct user info."""
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "gho_test_token",
        }

        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_token_response)
            mock_client.get = AsyncMock(return_value=mock_user_response)
            mock_client_cls.return_value = mock_client

            user_info = await user_auth.exchange_code("github", "test_code")

        assert user_info["provider"] == "github"
        assert user_info["provider_id"] == "12345"
        assert user_info["email"] == "test@example.com"
        assert user_info["name"] == "Test User"
        assert user_info["avatar_url"] == ("https://avatars.githubusercontent.com/u/12345")

    @pytest.mark.asyncio
    async def test_github_email_fallback(self, user_auth):
        """When primary email is None, fetch from /user/emails endpoint."""
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "gho_test_token",
        }

        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "name": "Test User",
            "email": None,
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        }

        mock_emails_response = MagicMock()
        mock_emails_response.status_code = 200
        mock_emails_response.json.return_value = [
            {
                "email": "secondary@example.com",
                "primary": False,
                "verified": True,
            },
            {
                "email": "primary@example.com",
                "primary": True,
                "verified": True,
            },
        ]

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_token_response)
            mock_client.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])
            mock_client_cls.return_value = mock_client

            user_info = await user_auth.exchange_code("github", "test_code")

        assert user_info["email"] == "primary@example.com"

    @pytest.mark.asyncio
    async def test_google_token_exchange(self, user_auth):
        """Google code exchange should return correct user info."""
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "ya29.test_token",
        }

        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "sub": "google_67890",
            "email": "test@gmail.com",
            "name": "Test Google User",
            "picture": "https://lh3.googleusercontent.com/photo.jpg",
            "email_verified": True,
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_token_response)
            mock_client.get = AsyncMock(return_value=mock_user_response)
            mock_client_cls.return_value = mock_client

            user_info = await user_auth.exchange_code("google", "test_code")

        assert user_info["provider"] == "google"
        assert user_info["provider_id"] == "google_67890"
        assert user_info["email"] == "test@gmail.com"
        assert user_info["name"] == "Test Google User"
        assert user_info["avatar_url"] == ("https://lh3.googleusercontent.com/photo.jpg")

    @pytest.mark.asyncio
    async def test_token_exchange_failure(self, user_auth):
        """Failed token exchange should raise ValueError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {
            "error": "bad_verification_code",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="Failed to exchange"):
                await user_auth.exchange_code("github", "bad_code")

    @pytest.mark.asyncio
    async def test_exchange_unsupported_provider(self, user_auth):
        """Unsupported provider in exchange_code should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            await user_auth.exchange_code("twitter", "code")


# ── Registration Rate Limiting ────────────────────────────────


class TestRegistrationRateLimit:
    """Test registration rate limiting (3 per IP per hour)."""

    def test_under_limit(self, user_auth):
        """IP under the limit should be allowed."""
        assert user_auth.check_registration_rate("1.2.3.4") is True
        user_auth.record_registration("1.2.3.4")
        assert user_auth.check_registration_rate("1.2.3.4") is True

    def test_at_limit(self, user_auth):
        """IP at the limit (3 registrations) should be blocked."""
        for _ in range(3):
            user_auth.record_registration("1.2.3.4")
        assert user_auth.check_registration_rate("1.2.3.4") is False

    def test_different_ips(self, user_auth):
        """Rate limiting should be per-IP."""
        for _ in range(3):
            user_auth.record_registration("1.2.3.4")
        assert user_auth.check_registration_rate("5.6.7.8") is True

    def test_expired_records_cleaned(self, user_auth):
        """Expired records should be cleaned up, allowing new registrations."""
        user_auth.record_registration("1.2.3.4")
        # Manually expire the record (over 1 hour ago)
        user_auth._registration_records["1.2.3.4"] = [time.time() - 3700]
        assert user_auth.check_registration_rate("1.2.3.4") is True


# ── Session Creation ──────────────────────────────────────────


class TestUserSession:
    """Test user session JWT creation and validation."""

    def test_create_user_session(self, user_auth):
        """create_user_session should return a non-empty JWT string."""
        token = user_auth.create_user_session(
            user_id="uuid-123",
            email="test@example.com",
            name="Test",
            role="user",
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_validate_user_session(self, user_auth):
        """validate_user_session should decode a valid token correctly."""
        token = user_auth.create_user_session(
            user_id="uuid-123",
            email="test@example.com",
            name="Test User",
            role="user",
        )
        session = user_auth.validate_user_session(token)
        assert session is not None
        assert session["user_id"] == "uuid-123"
        assert session["email"] == "test@example.com"
        assert session["name"] == "Test User"
        assert session["role"] == "user"
        assert session["type"] == "oauth_user"

    def test_invalid_token(self, user_auth):
        """validate_user_session should return None for garbage tokens."""
        assert user_auth.validate_user_session("garbage.token.here") is None

    def test_expired_token(self, user_auth):
        """validate_user_session should return None for expired tokens."""
        import jwt as pyjwt

        payload = {
            "uid": "uuid-123",
            "email": "test@example.com",
            "name": "Test",
            "role": "user",
            "type": "oauth_user",
            "iat": time.time() - 7200,
            "exp": time.time() - 3600,  # Expired 1 hour ago
        }
        token = pyjwt.encode(payload, user_auth._session_secret, algorithm="HS256")
        assert user_auth.validate_user_session(token) is None

    def test_session_with_none_name(self, user_auth):
        """Session with None name should store empty string."""
        token = user_auth.create_user_session(
            user_id="uuid-456",
            email="noname@example.com",
            name=None,
            role="user",
        )
        session = user_auth.validate_user_session(token)
        assert session is not None
        assert session["name"] == ""


# ── Singleton Pattern ─────────────────────────────────────────


class TestSingleton:
    """Test module-level singleton pattern."""

    def test_initialize_and_get(self):
        """initialize_user_auth should set the singleton retrievable by get."""
        auth = initialize_user_auth(
            github_client_id="gh_id",
            github_client_secret="gh_secret",
            google_client_id="g_id",
            google_client_secret="g_secret",
            public_url="https://example.com",
        )
        assert get_user_auth() is auth

    def test_get_without_init_raises(self):
        """get_user_auth before init should raise RuntimeError."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_user_auth()


# ── Provider Config ───────────────────────────────────────────


class TestProviderConfig:
    """Test provider availability detection."""

    def test_available_providers_both(self, user_auth):
        """Both providers configured should both appear."""
        providers = user_auth.available_providers()
        assert "github" in providers
        assert "google" in providers

    def test_no_github_if_missing_creds(self):
        """Missing GitHub creds should exclude github from providers."""
        auth = UserAuth(
            google_client_id="g_id",
            google_client_secret="g_secret",
            public_url="https://example.com",
        )
        providers = auth.available_providers()
        assert "github" not in providers
        assert "google" in providers

    def test_no_google_if_missing_creds(self):
        """Missing Google creds should exclude google from providers."""
        auth = UserAuth(
            github_client_id="gh_id",
            github_client_secret="gh_secret",
            public_url="https://example.com",
        )
        providers = auth.available_providers()
        assert "github" in providers
        assert "google" not in providers

    def test_no_providers_if_none_configured(self):
        """No credentials at all should return empty providers list."""
        auth = UserAuth(public_url="https://example.com")
        assert auth.available_providers() == []


# ── OAuthProvider Constants ───────────────────────────────────


class TestOAuthProviderConstants:
    """Test OAuthProvider class constants."""

    def test_github_constant(self):
        """OAuthProvider.GITHUB should be 'github'."""
        assert OAuthProvider.GITHUB == "github"

    def test_google_constant(self):
        """OAuthProvider.GOOGLE should be 'google'."""
        assert OAuthProvider.GOOGLE == "google"
