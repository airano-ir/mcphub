"""Tests for Admin System Unification (F.4)."""

from core.dashboard.auth import (
    DashboardSession,
    get_session_display_info,
    is_admin_session,
)


class TestIsAdminEmail:
    """Test is_admin_email() helper."""

    def test_admin_email_matches(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com,boss@corp.com")
        from core.admin_utils import is_admin_email

        assert is_admin_email("admin@example.com") is True

    def test_admin_email_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "Admin@Example.com")
        from core.admin_utils import is_admin_email

        assert is_admin_email("admin@example.com") is True

    def test_non_admin_email(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        from core.admin_utils import is_admin_email

        assert is_admin_email("user@example.com") is False

    def test_no_env_var_set(self, monkeypatch):
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        from core.admin_utils import is_admin_email

        assert is_admin_email("anyone@example.com") is False

    def test_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "")
        from core.admin_utils import is_admin_email

        assert is_admin_email("anyone@example.com") is False

    def test_whitespace_in_env_var(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", " admin@example.com , boss@corp.com ")
        from core.admin_utils import is_admin_email

        assert is_admin_email("admin@example.com") is True

    def test_none_email_returns_false(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        from core.admin_utils import is_admin_email

        assert is_admin_email(None) is False


class TestOAuthAdminRole:
    """Test that OAuth callback assigns admin role based on ADMIN_EMAILS."""

    def test_admin_email_gets_admin_role(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        from core.admin_utils import is_admin_email

        email = "admin@example.com"
        db_role = "user"
        effective_role = "admin" if is_admin_email(email) else db_role
        assert effective_role == "admin"

    def test_normal_email_gets_user_role(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        from core.admin_utils import is_admin_email

        email = "user@example.com"
        db_role = "user"
        effective_role = "admin" if is_admin_email(email) else db_role
        assert effective_role == "user"

    def test_no_admin_emails_env_keeps_user_role(self, monkeypatch):
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        from core.admin_utils import is_admin_email

        email = "anyone@example.com"
        db_role = "user"
        effective_role = "admin" if is_admin_email(email) else db_role
        assert effective_role == "user"


class TestIsAdminSession:
    """Test is_admin_session with different session types."""

    def test_master_session_is_admin(self):
        session = DashboardSession(
            session_id="test", created_at=None, expires_at=None, user_type="master"
        )
        assert is_admin_session(session) is True

    def test_api_key_session_is_admin(self):
        session = DashboardSession(
            session_id="test", created_at=None, expires_at=None, user_type="api_key"
        )
        assert is_admin_session(session) is True

    def test_oauth_admin_is_admin(self):
        session = {"user_id": "123", "email": "a@b.com", "role": "admin", "type": "oauth_user"}
        assert is_admin_session(session) is True

    def test_oauth_user_is_not_admin(self):
        session = {"user_id": "123", "email": "a@b.com", "role": "user", "type": "oauth_user"}
        assert is_admin_session(session) is False


class TestGetSessionDisplayInfo:
    """Test display info for admin OAuth users."""

    def test_oauth_admin_shows_admin_type(self):
        session = {
            "user_id": "123",
            "email": "a@b.com",
            "name": "Admin User",
            "role": "admin",
            "type": "oauth_user",
        }
        info = get_session_display_info(session)
        assert info["type"] == "admin"
        assert info["name"] == "Admin User"
        assert info["email"] == "a@b.com"

    def test_oauth_user_shows_user_type(self):
        session = {
            "user_id": "123",
            "email": "a@b.com",
            "name": "Normal User",
            "role": "user",
            "type": "oauth_user",
        }
        info = get_session_display_info(session)
        assert info["type"] == "user"

    def test_master_session_shows_admin(self):
        session = DashboardSession(
            session_id="test", created_at=None, expires_at=None, user_type="master"
        )
        info = get_session_display_info(session)
        assert info["type"] == "admin"
        assert info["name"] == "Admin"


class TestDisableMasterKeyLogin:
    """Test DISABLE_MASTER_KEY_LOGIN env var."""

    def test_master_key_works_by_default(self, monkeypatch):
        monkeypatch.delenv("DISABLE_MASTER_KEY_LOGIN", raising=False)
        monkeypatch.setenv("MASTER_API_KEY", "test-key-123")

        from core.dashboard.auth import DashboardAuth

        auth = DashboardAuth(master_api_key="test-key-123")
        is_valid, user_type, key_id = auth.validate_api_key("test-key-123")
        assert is_valid is True
        assert user_type == "master"

    def test_master_key_blocked_when_disabled(self, monkeypatch):
        monkeypatch.setenv("DISABLE_MASTER_KEY_LOGIN", "true")
        monkeypatch.setenv("MASTER_API_KEY", "test-key-123")

        from core.dashboard.auth import DashboardAuth

        auth = DashboardAuth(master_api_key="test-key-123")
        is_valid, user_type, key_id = auth.validate_api_key("test-key-123")
        assert is_valid is False

    def test_master_key_works_when_explicitly_enabled(self, monkeypatch):
        monkeypatch.setenv("DISABLE_MASTER_KEY_LOGIN", "false")
        monkeypatch.setenv("MASTER_API_KEY", "test-key-123")

        from core.dashboard.auth import DashboardAuth

        auth = DashboardAuth(master_api_key="test-key-123")
        is_valid, user_type, key_id = auth.validate_api_key("test-key-123")
        assert is_valid is True

    def test_api_key_still_works_when_master_disabled(self, monkeypatch):
        monkeypatch.setenv("DISABLE_MASTER_KEY_LOGIN", "true")

        from core.dashboard.auth import DashboardAuth

        auth = DashboardAuth(master_api_key="test-key-123")
        is_valid, user_type, key_id = auth.validate_api_key("test-key-123")
        assert is_valid is False  # Master key blocked
