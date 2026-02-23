"""Tests for User API Key management (core/user_keys.py)."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from core.user_keys import (
    KEY_PREFIX_TAG,
    UserKeyManager,
    get_user_key_manager,
    initialize_user_key_manager,
)

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global UserKeyManager singleton between tests."""
    import core.user_keys as mod

    original = mod._manager
    mod._manager = None
    yield
    mod._manager = original


@pytest.fixture
def mock_db():
    """Create and patch a mock database instance."""
    db = AsyncMock()
    # Default return values for DB methods
    db.create_api_key = AsyncMock(
        return_value={
            "id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "key_hash": "$2b$12$fakehashvalue",
            "key_prefix": "abcdefgh",
            "name": "Claude Desktop",
            "scopes": "read write",
            "created_at": "2026-02-19T12:00:00Z",
            "expires_at": None,
        }
    )
    db.get_api_key_by_prefix = AsyncMock(return_value=None)
    db.get_api_keys_by_user = AsyncMock(
        return_value=[
            {
                "id": "key-uuid-001",
                "name": "Claude Desktop",
                "scopes": "read write",
                "created_at": "2026-02-19T12:00:00Z",
                "expires_at": None,
                "last_used_at": None,
            },
        ]
    )
    db.delete_api_key = AsyncMock(return_value=True)
    db.update_api_key_usage = AsyncMock()
    with patch("core.database.get_database", return_value=db):
        yield db


@pytest.fixture
def key_mgr():
    """Create a fresh UserKeyManager instance."""
    return UserKeyManager()


# ── Key Creation ─────────────────────────────────────────────


class TestKeyCreation:
    """Test API key creation."""

    @pytest.mark.unit
    async def test_create_key_format(self, key_mgr, mock_db):
        """Created key should start with 'mhu_' and have substantial length."""
        result = await key_mgr.create_key("user-uuid-001", "Claude Desktop")
        raw_key = result["key"]
        assert raw_key.startswith(KEY_PREFIX_TAG)
        # mhu_ (4) + urlsafe_b64 of 32 bytes (43 chars) = 47 chars total
        assert len(raw_key) == 47

    @pytest.mark.unit
    async def test_create_key_stores_bcrypt_hash(self, key_mgr, mock_db):
        """The key_hash passed to DB should be a bcrypt hash ($2b$ prefix)."""
        await key_mgr.create_key("user-uuid-001", "Test Key")
        call_kwargs = mock_db.create_api_key.call_args
        key_hash = call_kwargs.kwargs.get("key_hash") or call_kwargs[1].get("key_hash")
        assert key_hash.startswith("$2b$")

    @pytest.mark.unit
    async def test_create_key_returns_metadata(self, key_mgr, mock_db):
        """Create key should return key_id, name, scopes, and timestamps."""
        result = await key_mgr.create_key("user-uuid-001", "Claude Desktop")
        assert "key_id" in result
        assert result["name"] == "Claude Desktop"
        assert result["scopes"] == "read write"
        assert "created_at" in result


# ── Key Validation ───────────────────────────────────────────


class TestKeyValidation:
    """Test API key validation logic."""

    @pytest.mark.unit
    async def test_validate_key_success(self, key_mgr, mock_db):
        """Creating then validating a key should return valid info."""
        import bcrypt

        # Create a key and capture the raw key
        result = await key_mgr.create_key("user-uuid-001", "Test Key")
        raw_key = result["key"]

        # Set up DB to return a matching row with correct bcrypt hash
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        mock_db.get_api_key_by_prefix.return_value = {
            "id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "key_hash": key_hash,
            "scopes": "read write",
            "expires_at": None,
        }

        info = await key_mgr.validate_key(raw_key)
        assert info is not None
        assert info["user_id"] == "user-uuid-001"
        assert info["key_id"] == "key-uuid-001"
        assert info["scopes"] == "read write"

    @pytest.mark.unit
    async def test_validate_key_wrong_key(self, key_mgr, mock_db):
        """A key that doesn't match the bcrypt hash should return None."""
        import bcrypt

        correct_key = "mhu_correctkeyvalue1234567890abcdefghijklmno"
        key_hash = bcrypt.hashpw(correct_key.encode(), bcrypt.gensalt()).decode()

        mock_db.get_api_key_by_prefix.return_value = {
            "id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "key_hash": key_hash,
            "scopes": "read write",
            "expires_at": None,
        }

        wrong_key = "mhu_wrongkeyvalue1234567890abcdefghijklmnopq"
        info = await key_mgr.validate_key(wrong_key)
        assert info is None

    @pytest.mark.unit
    async def test_validate_key_no_prefix(self, key_mgr, mock_db):
        """A key without the 'mhu_' prefix should immediately return None."""
        info = await key_mgr.validate_key("bad_prefix_key")
        assert info is None
        # DB should not even be queried
        mock_db.get_api_key_by_prefix.assert_not_called()

    @pytest.mark.unit
    async def test_validate_key_expired(self, key_mgr, mock_db):
        """A key with expires_at in the past should return None."""
        import bcrypt

        raw_key = "mhu_expiredkeyvalue1234567890abcdefghijklmno"
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

        expired_at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        mock_db.get_api_key_by_prefix.return_value = {
            "id": "key-uuid-002",
            "user_id": "user-uuid-001",
            "key_hash": key_hash,
            "scopes": "read",
            "expires_at": expired_at,
        }

        info = await key_mgr.validate_key(raw_key)
        assert info is None

    @pytest.mark.unit
    async def test_validate_key_cache(self, key_mgr, mock_db):
        """Second validation of the same key should use cache (no DB prefix lookup)."""
        import bcrypt

        result = await key_mgr.create_key("user-uuid-001", "Cache Test")
        raw_key = result["key"]

        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        mock_db.get_api_key_by_prefix.return_value = {
            "id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "key_hash": key_hash,
            "scopes": "read write",
            "expires_at": None,
        }

        # First validation — hits DB
        info1 = await key_mgr.validate_key(raw_key)
        assert info1 is not None
        assert mock_db.get_api_key_by_prefix.call_count == 1

        # Second validation — should use cache
        info2 = await key_mgr.validate_key(raw_key)
        assert info2 is not None
        # get_api_key_by_prefix should NOT be called again
        assert mock_db.get_api_key_by_prefix.call_count == 1

    @pytest.mark.unit
    async def test_validate_key_updates_usage(self, key_mgr, mock_db):
        """Successful validation should call update_api_key_usage."""
        import bcrypt

        result = await key_mgr.create_key("user-uuid-001", "Usage Test")
        raw_key = result["key"]

        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        mock_db.get_api_key_by_prefix.return_value = {
            "id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "key_hash": key_hash,
            "scopes": "read write",
            "expires_at": None,
        }

        await key_mgr.validate_key(raw_key)
        mock_db.update_api_key_usage.assert_called_with("key-uuid-001")


# ── Key Listing ──────────────────────────────────────────────


class TestKeyListing:
    """Test key listing functionality."""

    @pytest.mark.unit
    async def test_list_keys_no_hash(self, key_mgr, mock_db):
        """Listed keys should not contain key_hash field."""
        keys = await key_mgr.list_keys("user-uuid-001")
        assert len(keys) == 1
        assert "key_hash" not in keys[0]
        assert keys[0]["name"] == "Claude Desktop"


# ── Key Deletion ─────────────────────────────────────────────


class TestKeyDeletion:
    """Test key deletion and cache invalidation."""

    @pytest.mark.unit
    async def test_delete_key_clears_cache(self, key_mgr, mock_db):
        """Deleting a key should remove it from the validation cache."""
        # Populate cache manually
        key_mgr._cache["mhu_test_cached_key"] = (
            "key-uuid-001",
            "user-uuid-001",
            "read write",
            time.time(),
        )
        assert "mhu_test_cached_key" in key_mgr._cache

        deleted = await key_mgr.delete_key("key-uuid-001", "user-uuid-001")
        assert deleted is True
        assert "mhu_test_cached_key" not in key_mgr._cache

    @pytest.mark.unit
    async def test_delete_key_not_found(self, key_mgr, mock_db):
        """Deleting a non-existent key should return False."""
        mock_db.delete_api_key.return_value = False
        deleted = await key_mgr.delete_key("nonexistent-key", "user-uuid-001")
        assert deleted is False


# ── Singleton Pattern ────────────────────────────────────────


class TestSingleton:
    """Test module-level singleton pattern."""

    @pytest.mark.unit
    def test_singleton_pattern(self):
        """initialize_user_key_manager should set the singleton retrievable by get."""
        mgr = initialize_user_key_manager()
        assert get_user_key_manager() is mgr

    @pytest.mark.unit
    def test_get_without_init_raises(self):
        """get_user_key_manager before init should raise RuntimeError."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_user_key_manager()
