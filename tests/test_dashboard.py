"""Tests for Dashboard routes and auth (core/dashboard/).

Tests covering dashboard authentication, session management, rate limiting,
language detection, translations, and utility functions.
"""

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from core.dashboard.auth import DashboardAuth, DashboardSession
from core.dashboard.routes import (
    DASHBOARD_TRANSLATIONS,
    PLUGIN_DISPLAY_NAMES,
    detect_language,
    get_plugin_display_name,
    get_translations,
)

# --- Plugin Display Names ---


class TestPluginDisplayNames:
    """Test plugin name formatting."""

    def test_known_plugins(self):
        """Should return proper display names for known plugins."""
        assert get_plugin_display_name("wordpress") == "WordPress"
        assert get_plugin_display_name("woocommerce") == "WooCommerce"
        assert get_plugin_display_name("n8n") == "n8n"
        assert get_plugin_display_name("gitea") == "Gitea"
        assert get_plugin_display_name("supabase") == "Supabase"
        assert get_plugin_display_name("openpanel") == "OpenPanel"
        assert get_plugin_display_name("appwrite") == "Appwrite"
        assert get_plugin_display_name("directus") == "Directus"

    def test_wordpress_advanced(self):
        """Should handle underscore-separated names."""
        assert get_plugin_display_name("wordpress_advanced") == "WordPress Advanced"

    def test_unknown_plugin_titlecased(self):
        """Should title-case unknown plugin types."""
        assert get_plugin_display_name("my_custom_plugin") == "My Custom Plugin"

    def test_all_nine_plugins_mapped(self):
        """All 9 plugin types should be in the display names map."""
        expected = {
            "wordpress",
            "woocommerce",
            "wordpress_advanced",
            "gitea",
            "n8n",
            "supabase",
            "openpanel",
            "appwrite",
            "directus",
        }
        assert expected == set(PLUGIN_DISPLAY_NAMES.keys())


# --- Language Detection ---


class TestLanguageDetection:
    """Test language detection from query params (default English)."""

    def test_default_english(self):
        """Should default to English."""
        assert detect_language(None) == "en"

    def test_header_ignored(self):
        """Accept-Language header should be ignored (always default to English)."""
        assert detect_language("fa-IR,fa;q=0.9,en;q=0.8") == "en"

    def test_query_param_farsi(self):
        """Should detect Farsi from explicit query parameter."""
        assert detect_language("en-US", query_lang="fa") == "fa"

    def test_query_param_english(self):
        """Should respect English query parameter."""
        assert detect_language("fa-IR", query_lang="en") == "en"

    def test_invalid_query_lang_ignored(self):
        """Invalid query lang should be ignored, default to English."""
        assert detect_language("fa-IR", query_lang="de") == "en"

    def test_english_header(self):
        """Should return English for English header."""
        assert detect_language("en-US,en;q=0.9") == "en"


# --- Translations ---


class TestTranslations:
    """Test translation system."""

    def test_english_translations_exist(self):
        """English translations should be available."""
        trans = get_translations("en")
        assert trans["dashboard"] == "Dashboard"
        assert trans["projects"] == "Projects"
        assert trans["login_title"] == "Dashboard Login"

    def test_farsi_translations_exist(self):
        """Farsi translations should be available."""
        trans = get_translations("fa")
        assert trans["dashboard"] == "داشبورد"
        assert trans["projects"] == "پروژه‌ها"
        assert trans["login_title"] == "ورود به داشبورد"

    def test_unknown_lang_falls_back_to_english(self):
        """Unknown language should fall back to English."""
        trans = get_translations("de")
        assert trans["dashboard"] == "Dashboard"

    def test_both_languages_have_same_keys(self):
        """English and Farsi should have the same translation keys."""
        en_keys = set(DASHBOARD_TRANSLATIONS["en"].keys())
        fa_keys = set(DASHBOARD_TRANSLATIONS["fa"].keys())
        assert (
            en_keys == fa_keys
        ), f"Missing keys in fa: {en_keys - fa_keys}, extra in fa: {fa_keys - en_keys}"

    def test_no_empty_translations(self):
        """No translation value should be empty."""
        for lang, translations in DASHBOARD_TRANSLATIONS.items():
            for key, value in translations.items():
                assert value.strip() != "", f"Empty translation: {lang}.{key}"


# --- Dashboard Auth ---


class TestDashboardAuthInit:
    """Test DashboardAuth initialization."""

    def test_init_with_explicit_key(self):
        """Should use explicit secret key."""
        auth = DashboardAuth(secret_key="test-secret", master_api_key="sk-master")
        assert auth.secret_key == "test-secret"
        assert auth.master_api_key == "sk-master"

    def test_init_generates_random_key(self, monkeypatch):
        """Should generate random key when none provided."""
        monkeypatch.delenv("DASHBOARD_SESSION_SECRET", raising=False)
        monkeypatch.delenv("OAUTH_JWT_SECRET_KEY", raising=False)
        auth = DashboardAuth(master_api_key="sk-master")
        assert auth.secret_key is not None
        assert len(auth.secret_key) == 64  # hex of 32 bytes

    def test_default_session_expiry(self):
        """Default session expiry should be 24 hours."""
        auth = DashboardAuth(secret_key="test", master_api_key="sk-master")
        assert auth.session_expiry_hours == 24

    def test_custom_session_expiry(self, monkeypatch):
        """Should respect DASHBOARD_SESSION_EXPIRY_HOURS env var."""
        monkeypatch.setenv("DASHBOARD_SESSION_EXPIRY_HOURS", "48")
        auth = DashboardAuth(secret_key="test", master_api_key="sk-master")
        assert auth.session_expiry_hours == 48


class TestDashboardAuthValidation:
    """Test API key validation for dashboard login."""

    @pytest.fixture
    def auth(self):
        return DashboardAuth(secret_key="test-secret-key", master_api_key="sk-master-key-123")

    def test_valid_master_key(self, auth):
        """Should accept valid master API key."""
        is_valid, user_type, key_id = auth.validate_api_key("sk-master-key-123")
        assert is_valid is True
        assert user_type == "master"
        assert key_id is None

    def test_invalid_key_rejected(self, auth):
        """Should reject invalid API key."""
        is_valid, user_type, key_id = auth.validate_api_key("wrong-key")
        assert is_valid is False
        assert user_type == ""

    def test_empty_key_rejected(self, auth):
        """Should reject empty API key."""
        is_valid, user_type, key_id = auth.validate_api_key("")
        assert is_valid is False

    def test_none_key_rejected(self, auth):
        """Should reject None API key."""
        is_valid, user_type, key_id = auth.validate_api_key(None)
        assert is_valid is False


class TestDashboardRateLimiting:
    """Test login rate limiting."""

    @pytest.fixture
    def auth(self):
        return DashboardAuth(
            secret_key="test-secret",
            master_api_key="sk-master",
        )

    def test_within_limit(self, auth):
        """Should allow requests within rate limit."""
        assert auth.check_rate_limit("192.168.1.1") is True

    def test_exceeds_limit(self, auth):
        """Should block after exceeding rate limit."""
        ip = "192.168.1.100"
        # Record max_login_attempts (default 5)
        for _ in range(auth.max_login_attempts):
            auth.record_login_attempt(ip)
        assert auth.check_rate_limit(ip) is False

    def test_different_ips_independent(self, auth):
        """Different IPs should have independent rate limits."""
        ip1 = "10.0.0.1"
        ip2 = "10.0.0.2"
        for _ in range(auth.max_login_attempts):
            auth.record_login_attempt(ip1)
        assert auth.check_rate_limit(ip1) is False
        assert auth.check_rate_limit(ip2) is True

    def test_attempts_expire(self, auth):
        """Old attempts should expire after 1 minute window."""
        ip = "10.0.0.50"
        # Manually add old timestamps
        old_time = datetime.now(UTC) - timedelta(minutes=2)
        auth._login_attempts[ip] = [old_time] * 10
        # Old attempts should be cleaned up
        assert auth.check_rate_limit(ip) is True


class TestDashboardSessionManagement:
    """Test session creation and validation."""

    @pytest.fixture
    def auth(self):
        return DashboardAuth(secret_key="test-session-secret", master_api_key="sk-master")

    def test_create_session_returns_token(self, auth):
        """Should create a JWT session token."""
        token = auth.create_session("master")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_validate_valid_session(self, auth):
        """Should validate a freshly created session."""
        token = auth.create_session("master")
        session = auth.validate_session(token)
        assert session is not None
        assert isinstance(session, DashboardSession)
        assert session.user_type == "master"
        assert session.session_id is not None

    def test_session_contains_key_id(self, auth):
        """API key sessions should include key_id."""
        token = auth.create_session("api_key", key_id="key_abc123")
        session = auth.validate_session(token)
        assert session.key_id == "key_abc123"

    def test_master_session_no_key_id(self, auth):
        """Master sessions should have no key_id."""
        token = auth.create_session("master")
        session = auth.validate_session(token)
        assert session.key_id is None

    def test_expired_session_rejected(self, auth):
        """Should reject expired sessions."""
        # Create a token that's already expired
        now = datetime.now(UTC)
        payload = {
            "sid": "test-session",
            "type": "master",
            "iat": (now - timedelta(hours=48)).timestamp(),
            "exp": (now - timedelta(hours=1)).timestamp(),
        }
        token = jwt.encode(payload, auth.secret_key, algorithm="HS256")
        session = auth.validate_session(token)
        assert session is None

    def test_invalid_token_rejected(self, auth):
        """Should reject malformed tokens."""
        assert auth.validate_session("not-a-jwt-token") is None

    def test_wrong_secret_rejected(self, auth):
        """Should reject tokens signed with different secret."""
        token = jwt.encode(
            {"sid": "x", "type": "master", "iat": time.time(), "exp": time.time() + 3600},
            "wrong-secret",
            algorithm="HS256",
        )
        assert auth.validate_session(token) is None

    def test_empty_token_rejected(self, auth):
        """Should handle empty token."""
        assert auth.validate_session("") is None
        assert auth.validate_session(None) is None

    def test_session_expiry_matches_config(self, auth):
        """Session expiry should match configured hours."""
        token = auth.create_session("master")
        session = auth.validate_session(token)
        # validate_session uses datetime.fromtimestamp() which returns local time (naive)
        # So we compare with local datetime.now() (also naive)
        expected_expiry = datetime.now() + timedelta(hours=24)
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 5


class TestDashboardCookieManagement:
    """Test session cookie handling."""

    @pytest.fixture
    def auth(self):
        return DashboardAuth(secret_key="cookie-secret", master_api_key="sk-master")

    def test_set_session_cookie(self, auth):
        """Should set httpOnly cookie on response."""
        from starlette.responses import Response

        response = Response("OK")
        token = auth.create_session("master")
        auth.set_session_cookie(response, token)

        # Verify cookie was set (check raw headers)
        cookie_header = None
        for key, value in response.raw_headers:
            if key == b"set-cookie":
                cookie_header = value.decode()
                break
        assert cookie_header is not None
        assert "mcp_dashboard_session=" in cookie_header
        assert "httponly" in cookie_header.lower()

    def test_clear_session_cookie(self, auth):
        """Should clear session cookie."""
        from starlette.responses import Response

        response = Response("OK")
        auth.clear_session_cookie(response)

        cookie_header = None
        for key, value in response.raw_headers:
            if key == b"set-cookie":
                cookie_header = value.decode()
                break
        assert cookie_header is not None
        assert "mcp_dashboard_session=" in cookie_header
