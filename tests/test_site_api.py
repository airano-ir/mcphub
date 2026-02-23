"""Tests for Site Management API (core/site_api.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.site_api import (
    MAX_SITES_PER_USER,
    create_user_site,
    delete_user_site,
    get_credential_fields,
    get_user_sites,
    validate_credentials,
    validate_site_connection,
)

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Create and patch a mock database instance."""
    db = AsyncMock()
    db.count_sites_by_user = AsyncMock(return_value=0)
    db.get_site_by_alias = AsyncMock(return_value=None)
    db.get_site = AsyncMock(
        return_value={
            "id": "site-uuid-001",
            "user_id": "user-uuid-001",
            "plugin_type": "wordpress",
            "alias": "myblog",
            "url": "https://myblog.example.com",
            "credentials": b"encrypted-blob",
            "status": "active",
            "status_msg": "Connection verified",
            "created_at": "2026-02-19T12:00:00Z",
        }
    )
    db.get_sites_by_user = AsyncMock(
        return_value=[
            {
                "id": "site-uuid-001",
                "user_id": "user-uuid-001",
                "plugin_type": "wordpress",
                "alias": "myblog",
                "url": "https://myblog.example.com",
                "credentials": b"encrypted-blob",
                "status": "active",
                "created_at": "2026-02-19T12:00:00Z",
            },
        ]
    )
    db.delete_site = AsyncMock(return_value=True)
    db.execute = AsyncMock()
    db.update_site_status = AsyncMock()
    with patch("core.database.get_database", return_value=db):
        yield db


@pytest.fixture
def mock_encryption():
    """Create and patch a mock encryption instance."""
    enc = MagicMock()
    enc.encrypt_credentials = MagicMock(return_value=b"encrypted-blob")
    enc.decrypt_credentials = MagicMock(
        return_value={
            "username": "admin",
            "app_password": "xxxx xxxx xxxx xxxx",
        }
    )
    with patch("core.encryption.get_credential_encryption", return_value=enc):
        yield enc


# ── Credential Field Definitions ─────────────────────────────


class TestCredentialFields:
    """Test credential field definitions and retrieval."""

    @pytest.mark.unit
    def test_get_credential_fields_all_plugins(self):
        """All 9 plugin types should return non-empty credential field lists."""
        expected_plugins = [
            "wordpress",
            "woocommerce",
            "wordpress_advanced",
            "gitea",
            "n8n",
            "supabase",
            "openpanel",
            "appwrite",
            "directus",
        ]
        for plugin_type in expected_plugins:
            fields = get_credential_fields(plugin_type)
            assert len(fields) > 0, f"{plugin_type} returned empty fields"
            for field in fields:
                assert "name" in field
                assert "label" in field
                assert "type" in field
                assert "required" in field

    @pytest.mark.unit
    def test_get_credential_fields_invalid(self):
        """Unknown plugin type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown plugin type"):
            get_credential_fields("nonexistent_plugin")


# ── Credential Validation ────────────────────────────────────


class TestCredentialValidation:
    """Test credential validation logic."""

    @pytest.mark.unit
    def test_validate_credentials_valid(self):
        """Valid WordPress credentials should pass validation."""
        valid, errors = validate_credentials(
            "wordpress",
            {
                "username": "admin",
                "app_password": "xxxx xxxx xxxx xxxx",
            },
        )
        assert valid is True
        assert errors == []

    @pytest.mark.unit
    def test_validate_credentials_missing_required(self):
        """Missing required fields should return errors."""
        valid, errors = validate_credentials(
            "wordpress",
            {
                "username": "admin",
                # app_password is missing
            },
        )
        assert valid is False
        assert len(errors) == 1
        assert "Application Password" in errors[0]

    @pytest.mark.unit
    def test_validate_credentials_optional_field(self):
        """Optional fields (like container) should not cause errors when missing."""
        valid, errors = validate_credentials(
            "wordpress_advanced",
            {
                "username": "admin",
                "app_password": "xxxx xxxx xxxx xxxx",
                # container is optional — should not cause error
            },
        )
        assert valid is True
        assert errors == []

    @pytest.mark.unit
    def test_validate_credentials_empty_string_required(self):
        """Empty string for required field should fail validation."""
        valid, errors = validate_credentials(
            "wordpress",
            {
                "username": "admin",
                "app_password": "   ",  # whitespace only
            },
        )
        assert valid is False
        assert len(errors) == 1


# ── Site Creation ────────────────────────────────────────────


class TestSiteCreation:
    """Test site creation flow."""

    @pytest.mark.unit
    async def test_create_site_success(self, mock_db, mock_encryption):
        """Creating a site with skip_validation should succeed."""
        result = await create_user_site(
            user_id="user-uuid-001",
            plugin_type="wordpress",
            alias="myblog",
            url="https://myblog.example.com",
            credentials={"username": "admin", "app_password": "xxxx xxxx xxxx xxxx"},
            skip_validation=True,
        )
        assert result["alias"] == "myblog"
        assert result["plugin_type"] == "wordpress"
        # Credentials blob should be stripped from the response
        assert "credentials" not in result
        # DB execute should have been called to insert
        mock_db.execute.assert_called_once()
        # Encryption should have been used
        mock_encryption.encrypt_credentials.assert_called_once()

    @pytest.mark.unit
    async def test_create_site_alias_too_short(self, mock_db, mock_encryption):
        """Alias shorter than 2 characters should raise ValueError."""
        with pytest.raises(ValueError, match="2-50 characters"):
            await create_user_site(
                user_id="user-uuid-001",
                plugin_type="wordpress",
                alias="a",
                url="https://example.com",
                credentials={"username": "admin", "app_password": "xxxx"},
                skip_validation=True,
            )

    @pytest.mark.unit
    async def test_create_site_alias_invalid_chars(self, mock_db, mock_encryption):
        """Alias with invalid characters should raise ValueError."""
        with pytest.raises(ValueError, match="letters, numbers, hyphens, and underscores"):
            await create_user_site(
                user_id="user-uuid-001",
                plugin_type="wordpress",
                alias="my blog!",
                url="https://example.com",
                credentials={"username": "admin", "app_password": "xxxx"},
                skip_validation=True,
            )

    @pytest.mark.unit
    async def test_create_site_max_limit(self, mock_db, mock_encryption):
        """Exceeding MAX_SITES_PER_USER should raise ValueError."""
        mock_db.count_sites_by_user.return_value = MAX_SITES_PER_USER
        with pytest.raises(ValueError, match="Site limit reached"):
            await create_user_site(
                user_id="user-uuid-001",
                plugin_type="wordpress",
                alias="toomany",
                url="https://example.com",
                credentials={"username": "admin", "app_password": "xxxx"},
                skip_validation=True,
            )

    @pytest.mark.unit
    async def test_create_site_duplicate_alias(self, mock_db, mock_encryption):
        """Duplicate alias for the same user should raise ValueError."""
        mock_db.get_site_by_alias.return_value = {"id": "existing-site", "alias": "myblog"}
        with pytest.raises(ValueError, match="already in use"):
            await create_user_site(
                user_id="user-uuid-001",
                plugin_type="wordpress",
                alias="myblog",
                url="https://example.com",
                credentials={"username": "admin", "app_password": "xxxx"},
                skip_validation=True,
            )


# ── Site Retrieval and Deletion ──────────────────────────────


class TestSiteRetrievalDeletion:
    """Test site list and delete operations."""

    @pytest.mark.unit
    async def test_get_user_sites(self, mock_db):
        """get_user_sites should return sites without credential blobs."""
        sites = await get_user_sites("user-uuid-001")
        assert len(sites) == 1
        assert sites[0]["alias"] == "myblog"
        # Credentials should be stripped
        assert "credentials" not in sites[0]

    @pytest.mark.unit
    async def test_delete_user_site(self, mock_db):
        """delete_user_site should return True when site exists."""
        deleted = await delete_user_site("site-uuid-001", "user-uuid-001")
        assert deleted is True
        mock_db.delete_site.assert_called_once_with("site-uuid-001", "user-uuid-001")

    @pytest.mark.unit
    async def test_delete_user_site_not_found(self, mock_db):
        """delete_user_site should return False when site doesn't exist."""
        mock_db.delete_site.return_value = False
        deleted = await delete_user_site("nonexistent", "user-uuid-001")
        assert deleted is False


# ── Connection Validation ────────────────────────────────────


class TestConnectionValidation:
    """Test live connection validation with mocked HTTP."""

    @pytest.mark.unit
    async def test_validate_connection_success(self):
        """Successful HTTP response should return (True, 'OK')."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("core.site_api.aiohttp.ClientSession", return_value=mock_session):
            ok, msg = await validate_site_connection(
                "wordpress",
                "https://myblog.example.com",
                {"username": "admin", "app_password": "xxxx"},
            )

        assert ok is True
        assert msg == "OK"

    @pytest.mark.unit
    async def test_validate_connection_timeout(self):
        """Timeout should return (False, message about timeout)."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=TimeoutError("timed out"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("core.site_api.aiohttp.ClientSession", return_value=mock_session):
            ok, msg = await validate_site_connection(
                "wordpress",
                "https://slow-site.example.com",
                {"username": "admin", "app_password": "xxxx"},
            )

        assert ok is False
        assert "timed out" in msg.lower()

    @pytest.mark.unit
    async def test_validate_connection_auth_failure(self):
        """HTTP 401 should return (False, message about authentication)."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("core.site_api.aiohttp.ClientSession", return_value=mock_session):
            ok, msg = await validate_site_connection(
                "wordpress",
                "https://myblog.example.com",
                {"username": "admin", "app_password": "wrong"},
            )

        assert ok is False
        assert "authentication" in msg.lower()
