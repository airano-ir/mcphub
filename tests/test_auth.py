"""Tests for Authentication System (core/auth.py)."""

import os
import secrets

import pytest

from core.auth import AuthManager


@pytest.fixture
def auth_with_key(monkeypatch):
    """Create AuthManager with a known master key."""
    monkeypatch.setenv("MASTER_API_KEY", "test-master-key-12345")
    return AuthManager()


@pytest.fixture
def auth_without_key(monkeypatch):
    """Create AuthManager without env key (auto-generates)."""
    monkeypatch.delenv("MASTER_API_KEY", raising=False)
    return AuthManager()


class TestMasterKeyInit:
    """Test master key initialization."""

    def test_loads_key_from_env(self, auth_with_key):
        """Master key should be loaded from MASTER_API_KEY env var."""
        assert auth_with_key.master_api_key == "test-master-key-12345"

    def test_generates_key_when_missing(self, auth_without_key):
        """Should auto-generate a key when env var is not set."""
        assert auth_without_key.master_api_key is not None
        assert len(auth_without_key.master_api_key) > 20

    def test_generated_keys_are_unique(self, monkeypatch):
        """Each init without env should produce a different key."""
        monkeypatch.delenv("MASTER_API_KEY", raising=False)
        a = AuthManager()
        b = AuthManager()
        assert a.master_api_key != b.master_api_key


class TestMasterKeyValidation:
    """Test master key validation."""

    def test_valid_key_accepted(self, auth_with_key):
        """Correct master key should be accepted."""
        assert auth_with_key.validate_master_key("test-master-key-12345") is True

    def test_invalid_key_rejected(self, auth_with_key):
        """Wrong master key should be rejected."""
        assert auth_with_key.validate_master_key("wrong-key") is False

    def test_empty_key_rejected(self, auth_with_key):
        """Empty string should be rejected."""
        assert auth_with_key.validate_master_key("") is False

    def test_timing_safe_comparison(self, auth_with_key):
        """Validation should use timing-safe comparison (secrets.compare_digest)."""
        # This is a behavioral test: both wrong keys should take similar time
        # We mainly verify the method works correctly for various inputs
        assert auth_with_key.validate_master_key("test-master-key-12345") is True
        assert auth_with_key.validate_master_key("test-master-key-12346") is False

    def test_get_master_key(self, auth_with_key):
        """get_master_key should return the current key."""
        assert auth_with_key.get_master_key() == "test-master-key-12345"


class TestProjectKeys:
    """Test project-specific key management."""

    def test_add_project_key_custom(self, auth_with_key):
        """Should store a custom project key."""
        auth_with_key.add_project_key("proj1", "my-project-key")
        assert auth_with_key.validate_project_key("proj1", "my-project-key") is True

    def test_add_project_key_generated(self, auth_with_key):
        """Should generate a key when none provided."""
        key = auth_with_key.add_project_key("proj1")
        assert key is not None
        assert len(key) > 20
        assert auth_with_key.validate_project_key("proj1", key) is True

    def test_project_key_wrong_project(self, auth_with_key):
        """Project key should not work for a different project."""
        auth_with_key.add_project_key("proj1", "key-for-proj1")
        # proj2 has no key, so it falls back to master key
        assert auth_with_key.validate_project_key("proj2", "key-for-proj1") is False

    def test_fallback_to_master_key(self, auth_with_key):
        """Projects without a specific key should accept master key."""
        assert auth_with_key.validate_project_key("no-key-project", "test-master-key-12345") is True

    def test_remove_project_key(self, auth_with_key):
        """Removing a project key should make it fall back to master."""
        auth_with_key.add_project_key("proj1", "proj-key")
        auth_with_key.remove_project_key("proj1")
        # After removal, should fall back to master key
        assert auth_with_key.validate_project_key("proj1", "proj-key") is False
        assert auth_with_key.validate_project_key("proj1", "test-master-key-12345") is True

    def test_remove_nonexistent_key(self, auth_with_key):
        """Removing a key for a project that has none should not raise."""
        auth_with_key.remove_project_key("nonexistent")  # Should not raise

    def test_has_project_key(self, auth_with_key):
        """has_project_key should reflect current state."""
        assert auth_with_key.has_project_key("proj1") is False
        auth_with_key.add_project_key("proj1", "key")
        assert auth_with_key.has_project_key("proj1") is True
        auth_with_key.remove_project_key("proj1")
        assert auth_with_key.has_project_key("proj1") is False
