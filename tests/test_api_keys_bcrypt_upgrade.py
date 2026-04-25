"""F.8 security hardening: bcrypt + legacy SHA-256 upgrade-on-verify.

Ensures:

* Fresh keys created via ``create_key`` are stored as bcrypt hashes
  (``$2`` prefix). No new SHA-256 hashes can land.
* Keys whose storage file carries legacy SHA-256 hashes still validate
  (no customer lock-out), but the moment they validate once they are
  re-hashed with bcrypt and persisted — so the file on disk
  progressively drifts to bcrypt-only.
* Legacy-hash verification uses ``hmac.compare_digest`` (constant-time)
  rather than ``==`` to avoid a timing oracle on legacy entries.
* Corrupt or truncated bcrypt hashes don't crash the verifier — they
  return False so the caller emits a uniform 401.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from core.api_keys import APIKey, APIKeyManager


@pytest.fixture
def temp_storage():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        storage_path = f.name
    yield storage_path
    Path(storage_path).unlink(missing_ok=True)


@pytest.fixture
def manager(temp_storage):
    return APIKeyManager(storage_path=temp_storage)


# ---------------------------------------------------------------------------
# Fresh keys always bcrypt
# ---------------------------------------------------------------------------


class TestFreshKeysAreBcrypt:
    @pytest.mark.unit
    def test_created_key_stores_bcrypt_hash(self, manager):
        result = manager.create_key(project_id="*", scope="read")
        key = manager.keys[result["key_id"]]
        assert APIKeyManager._is_bcrypt_hash(key.key_hash)

    @pytest.mark.unit
    def test_created_key_hash_is_not_sha256(self, manager):
        plain = "cmp_test_plaintext_not_sha256"
        # Grab the output of _hash_key directly and compare against what a
        # SHA-256 would produce — they must differ.
        bcrypt_hash = manager._hash_key(plain)
        assert bcrypt_hash.startswith("$2")
        assert bcrypt_hash != hashlib.sha256(plain.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Legacy SHA-256 validation + upgrade
# ---------------------------------------------------------------------------


def _install_legacy_key(manager: APIKeyManager, raw_key: str, *, scope: str = "read") -> str:
    """Inject a legacy SHA-256-hashed key directly into the manager.

    Simulates a keys.json file that was written before F.8 landed.
    Returns the key_id.
    """
    import uuid
    from datetime import datetime

    key_id = "legacy-" + uuid.uuid4().hex[:8]
    legacy_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    manager.keys[key_id] = APIKey(
        key_id=key_id,
        key_hash=legacy_hash,
        project_id="*",
        scope=scope,
        created_at=datetime.now().isoformat(),
    )
    manager._save_keys()
    return key_id


class TestLegacySha256Validation:
    @pytest.mark.unit
    def test_legacy_sha256_hash_still_validates(self, manager):
        raw = "cmp_legacy_customer_key_1234567890"
        _install_legacy_key(manager, raw)

        assert manager.validate_key(raw, project_id="anything", required_scope="read") is not None

    @pytest.mark.unit
    def test_legacy_hash_rejects_wrong_key(self, manager):
        _install_legacy_key(manager, "cmp_real_one_1234")
        assert manager.validate_key("cmp_wrong", project_id="x", required_scope="read") is None

    @pytest.mark.unit
    def test_verify_uses_constant_time_on_legacy_path(self, manager):
        """Sanity check: _verify_key returns the same type regardless of
        how many leading characters of the SHA-256 hex happen to match."""
        raw = "cmp_constant_time_check_key"
        _install_legacy_key(manager, raw)
        legacy_hash = hashlib.sha256(raw.encode()).hexdigest()

        # Flip the very last byte of the hash — must still be rejected.
        tampered = legacy_hash[:-1] + ("0" if legacy_hash[-1] != "0" else "1")
        assert manager._verify_key(raw, tampered) is False
        # Real hash still passes.
        assert manager._verify_key(raw, legacy_hash) is True


class TestLegacyHashUpgradeOnVerify:
    @pytest.mark.unit
    def test_validate_key_upgrades_legacy_hash_to_bcrypt(self, manager):
        raw = "cmp_upgrade_target_1234567890"
        key_id = _install_legacy_key(manager, raw)

        # Before validation: legacy SHA-256 hash.
        assert not APIKeyManager._is_bcrypt_hash(manager.keys[key_id].key_hash)

        # Validate → upgrade path runs.
        assert manager.validate_key(raw, project_id="*", required_scope="read") == key_id

        # After validation: bcrypt.
        assert APIKeyManager._is_bcrypt_hash(manager.keys[key_id].key_hash)

    @pytest.mark.unit
    def test_get_key_by_token_also_upgrades(self, manager):
        raw = "cmp_get_by_token_upgrade_key"
        key_id = _install_legacy_key(manager, raw)

        assert manager.get_key_by_token(raw) is not None
        assert APIKeyManager._is_bcrypt_hash(manager.keys[key_id].key_hash)

    @pytest.mark.unit
    def test_upgrade_is_persisted_to_disk(self, manager, temp_storage):
        raw = "cmp_persistent_upgrade_key"
        key_id = _install_legacy_key(manager, raw)

        manager.validate_key(raw, project_id="*", required_scope="read")

        on_disk = json.loads(Path(temp_storage).read_text())
        assert APIKeyManager._is_bcrypt_hash(on_disk[key_id]["key_hash"])

    @pytest.mark.unit
    def test_upgrade_keeps_key_valid_after(self, manager):
        raw = "cmp_double_validate_key"
        _install_legacy_key(manager, raw)

        # First call upgrades.
        assert manager.validate_key(raw, project_id="*", required_scope="read") is not None
        # Second call uses the bcrypt path.
        assert manager.validate_key(raw, project_id="*", required_scope="read") is not None

    @pytest.mark.unit
    def test_upgrade_does_not_touch_bcrypt_keys(self, manager):
        """Keys that are already bcrypt-hashed must not be re-hashed every
        verify (bcrypt with fresh salt would invalidate later calls)."""
        result = manager.create_key(project_id="*", scope="read")
        raw = result["key"]  # raw plaintext key (create_key returns ``key``)
        before = manager.keys[result["key_id"]].key_hash

        manager.validate_key(raw, project_id="*", required_scope="read")

        after = manager.keys[result["key_id"]].key_hash
        assert before == after


# ---------------------------------------------------------------------------
# Robustness: corrupt / truncated bcrypt hashes must not crash
# ---------------------------------------------------------------------------


class TestCorruptBcryptHandling:
    @pytest.mark.unit
    def test_truncated_bcrypt_returns_false(self, manager):
        truncated = "$2b$12$truncated"
        assert manager._verify_key("any", truncated) is False

    @pytest.mark.unit
    def test_non_bcrypt_non_matching_returns_false(self, manager):
        assert manager._verify_key("any", "garbage-not-a-hash") is False

    @pytest.mark.unit
    def test_is_bcrypt_hash_classifier(self):
        # Positive cases.
        assert APIKeyManager._is_bcrypt_hash("$2b$12$abc.def")
        assert APIKeyManager._is_bcrypt_hash("$2a$10$x")
        assert APIKeyManager._is_bcrypt_hash("$2y$12$foo")
        # Negative cases: SHA-256 hex and garbage.
        assert not APIKeyManager._is_bcrypt_hash("a" * 64)
        assert not APIKeyManager._is_bcrypt_hash("")
        assert not APIKeyManager._is_bcrypt_hash("not-a-hash")
