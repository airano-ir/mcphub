"""Tests for last_tested_at site feature (Phase F.3)."""

import base64
import os

import pytest

from core.database import Database


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch):
    """Ensure ENCRYPTION_KEY is set and singleton is reset for tests."""
    key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # Reset the module-level singleton so it picks up the new key
    import core.encryption as enc_mod

    monkeypatch.setattr(enc_mod, "_credential_encryption", None)


@pytest.fixture
async def db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
async def test_user(db):
    return await db.create_user(
        email="test@example.com",
        name="Test User",
        provider="github",
        provider_id="12345",
    )


class TestLastTestedAt:
    async def test_new_site_has_no_last_tested(self, db, test_user):
        from core.encryption import get_credential_encryption

        enc = get_credential_encryption()
        creds = enc.encrypt_credentials({"username": "admin"}, "test-context")
        site = await db.create_site(
            user_id=test_user["id"],
            plugin_type="wordpress",
            alias="myblog",
            url="https://example.com",
            credentials=creds,
        )
        assert site is not None
        assert site["last_tested_at"] is None

    async def test_update_status_sets_last_tested(self, db, test_user):
        from core.encryption import get_credential_encryption

        enc = get_credential_encryption()
        creds = enc.encrypt_credentials({"username": "admin"}, "test-context-2")
        site = await db.create_site(
            user_id=test_user["id"],
            plugin_type="wordpress",
            alias="testblog",
            url="https://example.com",
            credentials=creds,
        )
        site_id = site["id"]
        await db.update_site_status(site_id, "active", "Connection OK", user_id=test_user["id"])
        updated = await db.get_site(site_id, test_user["id"])
        assert updated["last_tested_at"] is not None

    async def test_schema_version_is_current(self, db):
        from core.database import SCHEMA_VERSION

        row = await db.fetchone("SELECT MAX(version) AS v FROM schema_version")
        assert row["v"] == SCHEMA_VERSION
