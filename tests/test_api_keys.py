"""
Tests for API Keys Management System
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from core.api_keys import APIKeyManager


@pytest.fixture
def temp_storage():
    """Create temporary storage file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        storage_path = f.name
    yield storage_path
    # Cleanup
    Path(storage_path).unlink(missing_ok=True)


@pytest.fixture
def manager(temp_storage):
    """Create API Key Manager instance for testing."""
    return APIKeyManager(storage_path=temp_storage)


class TestAPIKeyCreation:
    """Test API key creation."""

    def test_create_key_basic(self, manager):
        """Test basic key creation."""
        result = manager.create_key(project_id="wordpress_site1", scope="read")

        assert "key" in result
        assert "key_id" in result
        assert result["key"].startswith("cmp_")
        assert result["scope"] == "read"
        assert result["project_id"] == "wordpress_site1"

    def test_create_key_with_expiration(self, manager):
        """Test key creation with expiration."""
        result = manager.create_key(project_id="wordpress_site1", scope="write", expires_in_days=30)

        assert result["expires_at"] is not None
        expires = datetime.fromisoformat(result["expires_at"])
        now = datetime.now()
        assert expires > now
        assert (expires - now).days <= 30

    def test_create_key_with_description(self, manager):
        """Test key creation with description."""
        result = manager.create_key(
            project_id="wordpress_site1", scope="admin", description="Test key for CI/CD"
        )

        key_id = result["key_id"]
        key_info = manager.get_key_info(key_id)
        assert key_info["description"] == "Test key for CI/CD"

    def test_create_global_key(self, manager):
        """Test creation of global key (all projects)."""
        result = manager.create_key(project_id="*", scope="admin")

        assert result["project_id"] == "*"

    def test_multiple_keys_same_project(self, manager):
        """Test creating multiple keys for same project."""
        manager.create_key("wordpress_site1", "read")
        manager.create_key("wordpress_site1", "write")
        manager.create_key("wordpress_site1", "admin")

        keys = manager.list_keys(project_id="wordpress_site1")
        assert len(keys) == 3

        scopes = {k["scope"] for k in keys}
        assert scopes == {"read", "write", "admin"}


class TestAPIKeyValidation:
    """Test API key validation."""

    def test_validate_key_success(self, manager):
        """Test successful key validation."""
        result = manager.create_key("wordpress_site1", "read")
        api_key = result["key"]

        key_id = manager.validate_key(api_key, project_id="wordpress_site1", required_scope="read")

        assert key_id is not None
        assert key_id == result["key_id"]

    def test_validate_key_wrong_project(self, manager):
        """Test validation fails for wrong project."""
        result = manager.create_key("wordpress_site1", "read")
        api_key = result["key"]

        key_id = manager.validate_key(api_key, project_id="wordpress_site2", required_scope="read")

        assert key_id is None

    def test_validate_key_insufficient_scope(self, manager):
        """Test validation fails with insufficient scope."""
        result = manager.create_key("wordpress_site1", "read")
        api_key = result["key"]

        key_id = manager.validate_key(api_key, project_id="wordpress_site1", required_scope="write")

        assert key_id is None

    def test_validate_key_scope_hierarchy(self, manager):
        """Test scope hierarchy: admin > write > read."""
        # Admin key can do write operations
        admin_result = manager.create_key("wordpress_site1", "admin")
        admin_key = admin_result["key"]

        key_id = manager.validate_key(
            admin_key, project_id="wordpress_site1", required_scope="write"
        )
        assert key_id is not None

        # Write key can do read operations
        write_result = manager.create_key("wordpress_site1", "write")
        write_key = write_result["key"]

        key_id = manager.validate_key(
            write_key, project_id="wordpress_site1", required_scope="read"
        )
        assert key_id is not None

    def test_validate_global_key(self, manager):
        """Test global key works for any project."""
        result = manager.create_key("*", "admin")
        api_key = result["key"]

        # Should work for any project
        key_id = manager.validate_key(api_key, project_id="wordpress_site1", required_scope="read")
        assert key_id is not None

        key_id = manager.validate_key(api_key, project_id="wordpress_site2", required_scope="write")
        assert key_id is not None

    def test_validate_invalid_key(self, manager):
        """Test validation fails for invalid key."""
        key_id = manager.validate_key(
            "cmp_invalid_key", project_id="wordpress_site1", required_scope="read"
        )

        assert key_id is None

    def test_validate_updates_usage(self, manager):
        """Test validation updates usage tracking."""
        result = manager.create_key("wordpress_site1", "read")
        api_key = result["key"]
        key_id = result["key_id"]

        # Initial state
        info = manager.get_key_info(key_id)
        assert info["usage_count"] == 0
        assert info["last_used_at"] is None

        # Use the key
        manager.validate_key(api_key, project_id="wordpress_site1", required_scope="read")

        # Check updated
        info = manager.get_key_info(key_id)
        assert info["usage_count"] == 1
        assert info["last_used_at"] is not None


class TestAPIKeyRevocation:
    """Test API key revocation."""

    def test_revoke_key(self, manager):
        """Test key revocation."""
        result = manager.create_key("wordpress_site1", "read")
        api_key = result["key"]
        key_id = result["key_id"]

        # Key should work before revocation
        validation = manager.validate_key(
            api_key, project_id="wordpress_site1", required_scope="read"
        )
        assert validation is not None

        # Revoke key
        success = manager.revoke_key(key_id)
        assert success is True

        # Key should not work after revocation
        validation = manager.validate_key(
            api_key, project_id="wordpress_site1", required_scope="read"
        )
        assert validation is None

    def test_revoke_nonexistent_key(self, manager):
        """Test revoking non-existent key."""
        success = manager.revoke_key("key_nonexistent")
        assert success is False

    def test_delete_key(self, manager):
        """Test permanent key deletion."""
        result = manager.create_key("wordpress_site1", "read")
        key_id = result["key_id"]

        # Delete key
        success = manager.delete_key(key_id)
        assert success is True

        # Key should not exist
        info = manager.get_key_info(key_id)
        assert info is None


class TestAPIKeyExpiration:
    """Test API key expiration."""

    def test_expired_key_invalid(self, manager):
        """Test expired key is invalid."""
        # Create key that expires immediately
        result = manager.create_key(
            "wordpress_site1", "read", expires_in_days=-1  # Already expired
        )
        api_key = result["key"]

        # Should not validate
        key_id = manager.validate_key(api_key, project_id="wordpress_site1", required_scope="read")
        assert key_id is None

    def test_key_expiration_check(self, manager):
        """Test expiration checking."""
        # Non-expiring key
        result1 = manager.create_key("wordpress_site1", "read")
        key1_id = result1["key_id"]
        info1 = manager.get_key_info(key1_id)
        assert info1["expired"] is False

        # Expired key
        result2 = manager.create_key("wordpress_site1", "read", expires_in_days=-1)
        key2_id = result2["key_id"]
        info2 = manager.get_key_info(key2_id)
        assert info2["expired"] is True


class TestAPIKeyListing:
    """Test API key listing."""

    def test_list_all_keys(self, manager):
        """Test listing all keys."""
        manager.create_key("wordpress_site1", "read")
        manager.create_key("wordpress_site2", "write")
        manager.create_key("wordpress_site3", "admin")

        keys = manager.list_keys()
        assert len(keys) == 3

    def test_list_keys_by_project(self, manager):
        """Test filtering keys by project."""
        manager.create_key("wordpress_site1", "read")
        manager.create_key("wordpress_site1", "write")
        manager.create_key("wordpress_site2", "admin")

        keys = manager.list_keys(project_id="wordpress_site1")
        assert len(keys) == 2

    def test_list_keys_exclude_revoked(self, manager):
        """Test excluding revoked keys from listing."""
        result1 = manager.create_key("wordpress_site1", "read")
        manager.create_key("wordpress_site1", "write")

        # Revoke one key
        manager.revoke_key(result1["key_id"])

        # List without revoked
        keys = manager.list_keys(include_revoked=False)
        assert len(keys) == 1

        # List with revoked
        keys = manager.list_keys(include_revoked=True)
        assert len(keys) == 2


class TestAPIKeyRotation:
    """Test API key rotation."""

    def test_rotate_keys(self, manager):
        """Test key rotation for a project."""
        # Create keys
        manager.create_key("wordpress_site1", "read")
        manager.create_key("wordpress_site1", "write")

        # Rotate
        new_keys = manager.rotate_keys("wordpress_site1")

        assert len(new_keys) == 2

        # All new keys should have different IDs
        new_key_ids = {k["key_id"] for k in new_keys}
        assert len(new_key_ids) == 2

        # Old keys should be revoked
        all_keys = manager.list_keys(project_id="wordpress_site1", include_revoked=True)
        revoked_count = sum(1 for k in all_keys if k["revoked"])
        assert revoked_count == 2

    def test_rotate_preserves_scopes(self, manager):
        """Test rotation preserves scopes."""
        manager.create_key("wordpress_site1", "read", description="Read key")
        manager.create_key("wordpress_site1", "admin", description="Admin key")

        new_keys = manager.rotate_keys("wordpress_site1")

        scopes = {k["scope"] for k in new_keys}
        assert scopes == {"read", "admin"}


class TestAPIKeyPersistence:
    """Test API key persistence."""

    def test_keys_persist_across_instances(self, temp_storage):
        """Test keys are saved and loaded correctly."""
        # Create manager and add key
        manager1 = APIKeyManager(storage_path=temp_storage)
        result = manager1.create_key("wordpress_site1", "read")
        key_id = result["key_id"]

        # Create new manager instance with same storage
        manager2 = APIKeyManager(storage_path=temp_storage)

        # Key should exist
        info = manager2.get_key_info(key_id)
        assert info is not None
        assert info["project_id"] == "wordpress_site1"

    def test_storage_file_format(self, temp_storage):
        """Test storage file is valid JSON."""
        manager = APIKeyManager(storage_path=temp_storage)
        manager.create_key("wordpress_site1", "read")

        # Check file is valid JSON
        with open(temp_storage) as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert len(data) == 1


class TestAPIKeyInfo:
    """Test getting key information."""

    def test_get_key_info(self, manager):
        """Test getting key information."""
        result = manager.create_key("wordpress_site1", "admin", description="Test key")
        key_id = result["key_id"]

        info = manager.get_key_info(key_id)

        assert info is not None
        assert info["key_id"] == key_id
        assert info["project_id"] == "wordpress_site1"
        assert info["scope"] == "admin"
        assert info["description"] == "Test key"
        assert info["valid"] is True

    def test_get_nonexistent_key_info(self, manager):
        """Test getting info for non-existent key."""
        info = manager.get_key_info("key_nonexistent")
        assert info is None


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
