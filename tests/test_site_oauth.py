"""Tests for the OAuth site-connection flow (core/site_oauth.py).

Covers:
- Authorization URL generation with correct params (access_type=offline, prompt=consent)
- State validation and consumption (one-time use, expiry)
- Code exchange with mocked Google token endpoint
- Token refresh with valid refresh token
- invalid_grant detection → InvalidGrantError
- Credential storage (encrypt + persist + status update)
- OAuth-aware site connection validation (via site_api.py)
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from core.site_oauth import (
    OAUTH_PLUGIN_TYPES,
    PLUGIN_TYPE_TO_PROVIDER,
    InvalidGrantError,
    SiteOAuthManager,
)

# ── Fixtures ──────────────────────────────────────────────────

_TEST_CLIENT_ID = "test-google-client-id"
_TEST_CLIENT_SECRET = "test-google-client-secret"  # noqa: S105 — test fixture
_TEST_PUBLIC_URL = "https://mcp.test.example.com"


@pytest.fixture
def oauth_mgr() -> SiteOAuthManager:
    """Create a SiteOAuthManager with test credentials."""
    return SiteOAuthManager(
        google_client_id=_TEST_CLIENT_ID,
        google_client_secret=_TEST_CLIENT_SECRET,
        public_url=_TEST_PUBLIC_URL,
    )


@pytest.fixture
def mock_db():
    """Create and patch a mock database instance."""
    import core.database as db_module

    db = AsyncMock()
    db.get_site = AsyncMock(
        return_value={
            "id": "site-uuid-001",
            "user_id": "user-uuid-001",
            "plugin_type": "gmail",
            "alias": "mygmail",
            "url": "",
            "credentials": b"encrypted-blob",
            "status": "pending",
            "status_msg": "Awaiting OAuth authorization",
            "created_at": "2026-02-19T12:00:00Z",
        }
    )
    db.update_site_credentials = AsyncMock()
    db.update_site_status = AsyncMock()
    # Patch get_database on the already-imported module so lazy imports see it
    original = getattr(db_module, "get_database", None)
    db_module.get_database = lambda: db
    try:
        yield db
    finally:
        if original is not None:
            db_module.get_database = original


@pytest.fixture
def mock_encryption():
    """Create and patch a mock encryption instance."""
    enc = MagicMock()
    enc.encrypt_credentials = MagicMock(return_value=b"new-encrypted-blob")
    enc.decrypt_credentials = MagicMock(
        return_value={
            "access_token": "[REDACTED]",
            "refresh_token": "[REDACTED]",
            "token_expires_at": "2026-02-19T13:00:00Z",
        }
    )
    with patch("core.encryption.get_credential_encryption", return_value=enc):
        yield enc


# ── Authorization URL Generation ───────────────────────────────


class TestAuthorizationURL:
    """Test OAuth authorization URL generation."""

    def test_get_auth_url_contains_offline_access_type(self, oauth_mgr: SiteOAuthManager):
        """Auth URL must include access_type=offline for refresh tokens."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["access_type"] == ["offline"]

    def test_get_auth_url_contains_prompt_consent(self, oauth_mgr: SiteOAuthManager):
        """Auth URL must include prompt=consent to force refresh token issuance."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["prompt"] == ["consent"]

    def test_get_auth_url_contains_client_id(self, oauth_mgr: SiteOAuthManager):
        """Auth URL must include the configured client_id."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["client_id"] == [_TEST_CLIENT_ID]

    def test_get_auth_url_contains_redirect_uri(self, oauth_mgr: SiteOAuthManager):
        """Auth URL redirect_uri must point to /oauth/site/callback."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["redirect_uri"] == [f"{_TEST_PUBLIC_URL}/oauth/site/callback"]

    def test_get_auth_url_contains_scope(self, oauth_mgr: SiteOAuthManager):
        """Auth URL must include the requested scope."""
        scope = "https://www.googleapis.com/auth/webmasters.readonly"
        url, state = oauth_mgr.get_site_authorization_url("google", scope, "site-001", "user-001")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["scope"] == [scope]

    def test_get_auth_url_contains_state(self, oauth_mgr: SiteOAuthManager):
        """Auth URL must include a state parameter, and it must be returned."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "state" in params
        assert params["state"][0] == state
        # State should be a reasonably long hex string
        assert len(state) >= 32

    def test_get_auth_url_stores_pending_state(self, oauth_mgr: SiteOAuthManager):
        """get_site_authorization_url must store the state for callback matching."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )
        assert state in oauth_mgr._pending_states
        entry = oauth_mgr._pending_states[state]
        assert entry["site_id"] == "site-001"
        assert entry["user_id"] == "user-001"
        assert entry["provider"] == "google"
        assert entry["scope"] == "https://www.googleapis.com/auth/gmail.modify"

    def test_get_auth_url_raises_without_public_url(self):
        """Manager without PUBLIC_URL must raise ValueError."""
        mgr = SiteOAuthManager(
            google_client_id=_TEST_CLIENT_ID,
            google_client_secret=_TEST_CLIENT_SECRET,
            public_url=None,
        )
        with pytest.raises(ValueError, match="PUBLIC_URL"):
            mgr.get_site_authorization_url("google", "scope", "site-001", "user-001")

    def test_get_auth_url_raises_unsupported_provider(self, oauth_mgr: SiteOAuthManager):
        """Unsupported provider must raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            oauth_mgr.get_site_authorization_url("microsoft", "scope", "site-001", "user-001")

    def test_get_auth_url_raises_unconfigured_provider(self):
        """Provider without credentials must raise ValueError."""
        mgr = SiteOAuthManager(
            google_client_id=None,
            google_client_secret=None,
            public_url=_TEST_PUBLIC_URL,
        )
        with pytest.raises(ValueError, match="not configured"):
            mgr.get_site_authorization_url("google", "scope", "site-001", "user-001")


# ── State Validation ──────────────────────────────────────────


class TestStateValidation:
    """Test OAuth state validation and consumption."""

    def test_validate_state_returns_metadata(self, oauth_mgr: SiteOAuthManager):
        """validate_and_consume_state returns site/user/provider metadata."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )
        info = oauth_mgr.validate_and_consume_state(state)
        assert info is not None
        assert info["site_id"] == "site-001"
        assert info["user_id"] == "user-001"
        assert info["provider"] == "google"
        assert info["scope"] == "https://www.googleapis.com/auth/gmail.modify"

    def test_validate_state_is_one_time_use(self, oauth_mgr: SiteOAuthManager):
        """State must be consumed on first use — second call returns None."""
        url, state = oauth_mgr.get_site_authorization_url("google", "scope", "site-001", "user-001")
        info1 = oauth_mgr.validate_and_consume_state(state)
        assert info1 is not None
        info2 = oauth_mgr.validate_and_consume_state(state)
        assert info2 is None

    def test_validate_unknown_state_returns_none(self, oauth_mgr: SiteOAuthManager):
        """Unknown state must return None."""
        info = oauth_mgr.validate_and_consume_state("nonexistent-state-token")
        assert info is None

    def test_validate_expired_state_returns_none(self, oauth_mgr: SiteOAuthManager):
        """Expired state must return None."""
        url, state = oauth_mgr.get_site_authorization_url("google", "scope", "site-001", "user-001")
        # Simulate expiry by backdating the timestamp
        oauth_mgr._pending_states[state]["ts"] = time.time() - 700  # > 600s expiry
        info = oauth_mgr.validate_and_consume_state(state)
        assert info is None


# ── Code Exchange ─────────────────────────────────────────────


class TestCodeExchange:
    """Test authorization code → token exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_returns_tokens(self, oauth_mgr: SiteOAuthManager):
        """exchange_site_code returns access_token + refresh_token + metadata."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "[REDACTED]",
            "refresh_token": "[REDACTED]",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/gmail.modify",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            tokens = await oauth_mgr.exchange_site_code("google", "auth-code-123", state)

        assert tokens["access_token"] == "[REDACTED]"
        assert tokens["refresh_token"] == "[REDACTED]"
        assert tokens["expires_in"] == 3600
        assert "token_expires_at" in tokens
        assert tokens["provider"] == "google"
        assert tokens["site_id"] == "site-001"
        assert tokens["user_id"] == "user-001"

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state_raises(self, oauth_mgr: SiteOAuthManager):
        """Invalid state must raise ValueError before attempting exchange."""
        with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
            await oauth_mgr.exchange_site_code("google", "code", "bad-state")

    @pytest.mark.asyncio
    async def test_exchange_code_no_refresh_token_raises(self, oauth_mgr: SiteOAuthManager):
        """If Google doesn't return a refresh_token, raise ValueError."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "[REDACTED]",
            # No refresh_token!
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="refresh_token"):
                await oauth_mgr.exchange_site_code("google", "code", state)

    @pytest.mark.asyncio
    async def test_exchange_code_http_error_raises(self, oauth_mgr: SiteOAuthManager):
        """Non-200 response from token endpoint must raise ValueError."""
        url, state = oauth_mgr.get_site_authorization_url(
            "google", "https://www.googleapis.com/auth/gmail.modify", "site-001", "user-001"
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"
        mock_response.json.return_value = {"error": "invalid_grant"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="Failed to exchange"):
                await oauth_mgr.exchange_site_code("google", "bad-code", state)


# ── Token Refresh ─────────────────────────────────────────────


class TestTokenRefresh:
    """Test access token refresh flow."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, oauth_mgr: SiteOAuthManager):
        """refresh_site_token returns a new access_token."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "[REDACTED_NEW]",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await oauth_mgr.refresh_site_token("google", "[REDACTED]")

        assert result["access_token"] == "[REDACTED_NEW]"
        assert result["expires_in"] == 3600
        assert "token_expires_at" in result
        # Google doesn't rotate refresh tokens by default
        assert result["refresh_token"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_grant_raises(self, oauth_mgr: SiteOAuthManager):
        """invalid_grant error must raise InvalidGrantError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_grant"}
        mock_response.text = '{"error": "invalid_grant"}'
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(InvalidGrantError, match="no longer valid"):
                await oauth_mgr.refresh_site_token("google", "expired-refresh-token")

    @pytest.mark.asyncio
    async def test_refresh_token_other_error_raises_value_error(self, oauth_mgr: SiteOAuthManager):
        """Non-invalid_grant errors must raise ValueError (not InvalidGrantError)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "server_error"}
        mock_response.text = "Internal Server Error"
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="Token refresh failed"):
                await oauth_mgr.refresh_site_token("google", "some-refresh-token")


# ── Credential Storage ────────────────────────────────────────


class TestCredentialStorage:
    """Test encrypted credential storage for OAuth tokens."""

    @pytest.mark.asyncio
    async def test_store_credentials_encrypts_and_persists(
        self, oauth_mgr: SiteOAuthManager, mock_db, mock_encryption
    ):
        """store_site_oauth_credentials must encrypt tokens and update the DB."""
        tokens = {
            "access_token": "[REDACTED]",
            "refresh_token": "[REDACTED]",
            "token_expires_at": "2026-02-19T13:00:00Z",
            "provider": "google",
            "site_id": "site-uuid-001",
            "user_id": "user-uuid-001",
        }

        await oauth_mgr.store_site_oauth_credentials("site-uuid-001", "user-uuid-001", tokens)

        # Verify encryption was called
        mock_encryption.encrypt_credentials.assert_called_once()
        # Verify DB was updated with encrypted credentials
        mock_db.update_site_credentials.assert_called_once()
        # Verify site status was set to active
        mock_db.update_site_status.assert_called_once_with(
            "site-uuid-001", "active", "OAuth authorized", user_id="user-uuid-001"
        )

    @pytest.mark.asyncio
    async def test_store_credentials_site_not_found_raises(self, oauth_mgr: SiteOAuthManager):
        """If site doesn't exist, raise ValueError."""
        import core.database as db_module

        mock_db = AsyncMock()
        mock_db.get_site = AsyncMock(return_value=None)
        original = getattr(db_module, "get_database", None)
        db_module.get_database = lambda: mock_db
        try:
            with pytest.raises(ValueError, match="Site not found"):
                await oauth_mgr.store_site_oauth_credentials(
                    "nonexistent", "user-001", {"access_token": "x"}
                )
        finally:
            if original is not None:
                db_module.get_database = original


# ── Plugin Type / Provider Mapping ────────────────────────────


class TestPluginTypeMapping:
    """Test plugin type → provider/scope mapping."""

    def test_gsc_maps_to_google(self):
        """google_search_console plugin type maps to google provider."""
        assert PLUGIN_TYPE_TO_PROVIDER.get("google_search_console") == "google"

    def test_oauth_plugin_types_includes_gsc_only(self):
        """OAUTH_PLUGIN_TYPES frozenset includes google_search_console only.

        Gmail uses manual credentials (bootstrap script), not the OAuth flow.
        """
        assert "gmail" not in OAUTH_PLUGIN_TYPES
        assert "google_search_console" in OAUTH_PLUGIN_TYPES

    def test_wordpress_not_in_oauth_types(self):
        """Static-credential plugins are not in OAUTH_PLUGIN_TYPES."""
        assert "wordpress" not in OAUTH_PLUGIN_TYPES

    def test_get_provider_for_plugin_type(self, oauth_mgr: SiteOAuthManager):
        """get_provider_for_plugin_type returns correct provider."""
        assert oauth_mgr.get_provider_for_plugin_type("google_search_console") == "google"
        assert oauth_mgr.get_provider_for_plugin_type("wordpress") is None

    def test_get_scope_for_gsc(self, oauth_mgr: SiteOAuthManager):
        """get_scope_for_plugin_type returns GSC scope."""
        scope = oauth_mgr.get_scope_for_plugin_type("google_search_console")
        assert scope is not None
        assert "webmasters" in scope

    def test_get_scope_for_non_oauth_plugin(self, oauth_mgr: SiteOAuthManager):
        """get_scope_for_plugin_type returns None for non-OAuth plugins."""
        assert oauth_mgr.get_scope_for_plugin_type("wordpress") is None


# ── Configuration ─────────────────────────────────────────────


class TestConfiguration:
    """Test manager configuration checks."""

    def test_is_configured_true_with_credentials(self, oauth_mgr: SiteOAuthManager):
        """is_configured returns True when client_id+secret are set."""
        assert oauth_mgr.is_configured("google") is True

    def test_is_configured_false_without_credentials(self):
        """is_configured returns False when credentials are missing."""
        mgr = SiteOAuthManager(
            google_client_id=None,
            google_client_secret=None,
            public_url=_TEST_PUBLIC_URL,
        )
        assert mgr.is_configured("google") is False

    def test_is_configured_false_for_unknown_provider(self, oauth_mgr: SiteOAuthManager):
        """is_configured returns False for unsupported providers."""
        assert oauth_mgr.is_configured("microsoft") is False

    def test_available_providers_with_config(self, oauth_mgr: SiteOAuthManager):
        """available_providers returns ['google'] when configured."""
        providers = oauth_mgr.available_providers()
        assert "google" in providers

    def test_available_providers_empty_without_config(self):
        """available_providers returns empty list when not configured."""
        mgr = SiteOAuthManager(
            google_client_id=None,
            google_client_secret=None,
            public_url=_TEST_PUBLIC_URL,
        )
        assert mgr.available_providers() == []


# ── Site API OAuth Integration ────────────────────────────────


class TestSiteApiOAuthIntegration:
    """Test that site_api.py correctly handles OAuth plugin types."""

    def test_validate_credentials_requires_gmail_fields(self):
        """validate_credentials should fail for gmail without required fields.

        Gmail uses manual credentials (client_id, client_secret, refresh_token),
        not the OAuth flow.  Empty credentials should fail validation.
        """
        from core.site_api import validate_credentials

        valid, errors = validate_credentials("gmail", {})
        assert valid is False
        assert len(errors) > 0

    def test_validate_credentials_skips_gsc(self):
        """validate_credentials should pass for GSC without credentials."""
        from core.site_api import validate_credentials

        valid, errors = validate_credentials("google_search_console", {})
        assert valid is True
        assert len(errors) == 0

    def test_plugin_credential_fields_include_gmail_manual(self):
        """PLUGIN_CREDENTIAL_FIELDS should include gmail with manual OAuth fields."""
        from core.site_api import PLUGIN_CREDENTIAL_FIELDS

        assert "gmail" in PLUGIN_CREDENTIAL_FIELDS
        fields = PLUGIN_CREDENTIAL_FIELDS["gmail"]
        field_names = [f["name"] for f in fields]
        assert "client_id" in field_names
        assert "client_secret" in field_names
        assert "refresh_token" in field_names

    def test_plugin_credential_fields_include_gsc(self):
        """PLUGIN_CREDENTIAL_FIELDS should include google_search_console."""
        from core.site_api import PLUGIN_CREDENTIAL_FIELDS

        assert "google_search_console" in PLUGIN_CREDENTIAL_FIELDS

    def test_health_endpoints_include_gmail(self):
        """_HEALTH_ENDPOINTS should include gmail endpoint."""
        from core.site_api import _HEALTH_ENDPOINTS

        assert "gmail" in _HEALTH_ENDPOINTS
        assert "gmail" in _HEALTH_ENDPOINTS["gmail"]["path"]

    def test_health_endpoints_include_gsc(self):
        """_HEALTH_ENDPOINTS should include google_search_console endpoint."""
        from core.site_api import _HEALTH_ENDPOINTS

        assert "google_search_console" in _HEALTH_ENDPOINTS
        assert "webmasters" in _HEALTH_ENDPOINTS["google_search_console"]["path"]

    @pytest.mark.asyncio
    async def test_validate_site_connection_invalid_grant_sets_reauth(self):
        """When OAuth health check returns invalid_grant, status should be reauth_required."""
        from core.site_api import _validate_oauth_site_connection

        # Mock the encryption to return credentials with an expired token
        mock_enc = MagicMock()
        mock_enc.decrypt_credentials = MagicMock(
            return_value={
                "access_token": "[REDACTED_EXPIRED]",
                "refresh_token": "[REDACTED]",
                "token_expires_at": "2020-01-01T00:00:00Z",  # Expired
            }
        )

        mock_oauth_mgr = MagicMock()
        mock_oauth_mgr.get_provider_for_plugin_type = MagicMock(return_value="google")
        mock_oauth_mgr.refresh_site_token = AsyncMock(side_effect=InvalidGrantError("expired"))

        with (
            patch("core.encryption.get_credential_encryption", return_value=mock_enc),
            patch("core.site_oauth.get_site_oauth_manager", return_value=mock_oauth_mgr),
        ):
            # _validate_oauth_site_connection(plugin_type, credentials, endpoint_info)
            credentials = {
                "access_token": "[REDACTED_EXPIRED]",
                "refresh_token": "[REDACTED]",
                "token_expires_at": "2020-01-01T00:00:00Z",
            }
            endpoint_info = {
                "base_url": "https://gmail.googleapis.com",
                "gmail": "/gmail/v1/users/me/profile",
                "method": "GET",
                "oauth": True,
            }
            ok, msg = await _validate_oauth_site_connection("gmail", credentials, endpoint_info)

        assert ok is False
        assert msg == "reauth_required"
