"""Tests for SQLite database backend (core/database.py)."""

import asyncio

import aiosqlite
import pytest

from core.database import SCHEMA_VERSION, Database, get_database, initialize_database

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db(tmp_path):
    """Provide an initialized Database using a temp directory."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def user_row(db):
    """Create and return a sample user dict."""
    return await db.create_user(
        email="alice@example.com",
        name="Alice",
        provider="github",
        provider_id="gh-111",
        avatar_url="https://example.com/alice.png",
    )


@pytest.fixture
async def second_user(db):
    """Create and return a second sample user dict."""
    return await db.create_user(
        email="bob@example.com",
        name="Bob",
        provider="google",
        provider_id="gg-222",
    )


@pytest.fixture
async def site_row(db, user_row):
    """Create and return a sample site dict."""
    return await db.create_site(
        user_id=user_row["id"],
        plugin_type="wordpress",
        alias="myblog",
        url="https://myblog.example.com",
        credentials=b"encrypted-blob-data",
    )


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------


class TestSchemaCreation:
    """Test that the database schema is created correctly."""

    @pytest.mark.unit
    async def test_tables_exist(self, db):
        """All expected tables should exist after initialization."""
        rows = await db.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = {row["name"] for row in rows}
        expected = {"users", "sites", "user_api_keys", "connection_tokens", "schema_version"}
        assert expected.issubset(table_names)

    @pytest.mark.unit
    async def test_schema_version_set(self, db):
        """schema_version table should contain version 1 after init."""
        row = await db.fetchone("SELECT MAX(version) AS v FROM schema_version")
        assert row is not None
        assert row["v"] == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


class TestUserCRUD:
    """Test user create, read, and update operations."""

    @pytest.mark.unit
    async def test_create_user(self, db):
        """Should create a user and return a dict with all fields."""
        user = await db.create_user(
            email="test@example.com",
            name="Test User",
            provider="github",
            provider_id="gh-999",
            avatar_url="https://example.com/avatar.png",
        )
        assert user["email"] == "test@example.com"
        assert user["name"] == "Test User"
        assert user["provider"] == "github"
        assert user["provider_id"] == "gh-999"
        assert user["avatar_url"] == "https://example.com/avatar.png"
        assert user["role"] == "user"
        assert user["id"] is not None
        assert user["created_at"] is not None

    @pytest.mark.unit
    async def test_create_user_admin_role(self, db):
        """Should allow creating a user with admin role."""
        user = await db.create_user(
            email="admin@example.com",
            name="Admin",
            provider="github",
            provider_id="gh-admin",
            role="admin",
        )
        assert user["role"] == "admin"

    @pytest.mark.unit
    async def test_get_user_by_id(self, db, user_row):
        """Should retrieve a user by their UUID."""
        fetched = await db.get_user_by_id(user_row["id"])
        assert fetched is not None
        assert fetched["email"] == "alice@example.com"

    @pytest.mark.unit
    async def test_get_user_by_id_not_found(self, db):
        """Should return None for a non-existent user ID."""
        fetched = await db.get_user_by_id("non-existent-uuid")
        assert fetched is None

    @pytest.mark.unit
    async def test_get_user_by_provider(self, db, user_row):
        """Should retrieve a user by provider and provider_id."""
        fetched = await db.get_user_by_provider("github", "gh-111")
        assert fetched is not None
        assert fetched["id"] == user_row["id"]

    @pytest.mark.unit
    async def test_get_user_by_provider_not_found(self, db):
        """Should return None for a non-existent provider combo."""
        fetched = await db.get_user_by_provider("github", "does-not-exist")
        assert fetched is None

    @pytest.mark.unit
    async def test_update_last_login(self, db, user_row):
        """Should update the last_login timestamp."""
        original_login = user_row["last_login"]
        # Small delay so the timestamps differ
        await asyncio.sleep(0.01)
        await db.update_user_last_login(user_row["id"])

        fetched = await db.get_user_by_id(user_row["id"])
        assert fetched is not None
        assert fetched["last_login"] != original_login
        assert fetched["last_login"] > original_login


# ---------------------------------------------------------------------------
# User uniqueness constraints
# ---------------------------------------------------------------------------


class TestUserConstraints:
    """Test UNIQUE constraints on the users table."""

    @pytest.mark.unit
    async def test_duplicate_email_raises(self, db, user_row):
        """Inserting a user with a duplicate email should raise IntegrityError."""
        with pytest.raises(aiosqlite.IntegrityError):
            await db.create_user(
                email="alice@example.com",  # duplicate
                name="Alice Clone",
                provider="google",
                provider_id="gg-unique",
            )

    @pytest.mark.unit
    async def test_duplicate_provider_raises(self, db, user_row):
        """Inserting a user with duplicate provider+provider_id should raise."""
        with pytest.raises(aiosqlite.IntegrityError):
            await db.create_user(
                email="other@example.com",
                name="Other",
                provider="github",  # same provider
                provider_id="gh-111",  # same provider_id
            )


# ---------------------------------------------------------------------------
# Site CRUD
# ---------------------------------------------------------------------------


class TestSiteCRUD:
    """Test site create, read, update, and delete operations."""

    @pytest.mark.unit
    async def test_create_site(self, db, user_row):
        """Should create a site and return a dict with all fields."""
        site = await db.create_site(
            user_id=user_row["id"],
            plugin_type="wordpress",
            alias="testsite",
            url="https://test.example.com",
            credentials=b"encrypted-data",
        )
        assert site["plugin_type"] == "wordpress"
        assert site["alias"] == "testsite"
        assert site["url"] == "https://test.example.com"
        assert site["credentials"] == b"encrypted-data"
        assert site["status"] == "pending"
        assert site["user_id"] == user_row["id"]
        assert site["id"] is not None
        assert site["created_at"] is not None

    @pytest.mark.unit
    async def test_get_sites_by_user(self, db, user_row):
        """Should return all sites for a user."""
        await db.create_site(
            user_id=user_row["id"],
            plugin_type="wordpress",
            alias="site-a",
            url="https://a.example.com",
            credentials=b"cred-a",
        )
        await db.create_site(
            user_id=user_row["id"],
            plugin_type="gitea",
            alias="site-b",
            url="https://b.example.com",
            credentials=b"cred-b",
        )

        sites = await db.get_sites_by_user(user_row["id"])
        assert len(sites) == 2
        aliases = {s["alias"] for s in sites}
        assert aliases == {"site-a", "site-b"}

    @pytest.mark.unit
    async def test_get_sites_by_user_empty(self, db, user_row):
        """Should return empty list when user has no sites."""
        sites = await db.get_sites_by_user(user_row["id"])
        assert sites == []

    @pytest.mark.unit
    async def test_get_site(self, db, user_row, site_row):
        """Should retrieve a site by ID with user scoping."""
        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is not None
        assert fetched["alias"] == "myblog"

    @pytest.mark.unit
    async def test_delete_site(self, db, user_row, site_row):
        """Should delete a site and return True."""
        deleted = await db.delete_site(site_row["id"], user_row["id"])
        assert deleted is True

        # Verify it's gone
        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is None

    @pytest.mark.unit
    async def test_delete_site_not_found(self, db, user_row):
        """Should return False when deleting a non-existent site."""
        deleted = await db.delete_site("no-such-id", user_row["id"])
        assert deleted is False


# ---------------------------------------------------------------------------
# Site isolation
# ---------------------------------------------------------------------------


class TestSiteIsolation:
    """Test that site access is properly scoped to the owning user."""

    @pytest.mark.unit
    async def test_get_site_wrong_user_returns_none(self, db, user_row, second_user, site_row):
        """get_site with wrong user_id should return None."""
        fetched = await db.get_site(site_row["id"], second_user["id"])
        assert fetched is None

    @pytest.mark.unit
    async def test_delete_site_wrong_user_returns_false(self, db, user_row, second_user, site_row):
        """delete_site with wrong user_id should return False and not delete."""
        deleted = await db.delete_site(site_row["id"], second_user["id"])
        assert deleted is False

        # Verify it's still there for the real owner
        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is not None


# ---------------------------------------------------------------------------
# Site alias constraints
# ---------------------------------------------------------------------------


class TestSiteAliasConstraints:
    """Test UNIQUE(user_id, alias) constraint on the sites table."""

    @pytest.mark.unit
    async def test_duplicate_alias_same_user_raises(self, db, user_row, site_row):
        """Duplicate alias for the same user should raise IntegrityError."""
        with pytest.raises(aiosqlite.IntegrityError):
            await db.create_site(
                user_id=user_row["id"],
                plugin_type="gitea",
                alias="myblog",  # duplicate alias for same user
                url="https://other.example.com",
                credentials=b"cred",
            )

    @pytest.mark.unit
    async def test_same_alias_different_users_succeeds(self, db, user_row, second_user):
        """Same alias for different users should succeed."""
        site1 = await db.create_site(
            user_id=user_row["id"],
            plugin_type="wordpress",
            alias="shared-alias",
            url="https://a.example.com",
            credentials=b"cred-a",
        )
        site2 = await db.create_site(
            user_id=second_user["id"],
            plugin_type="wordpress",
            alias="shared-alias",
            url="https://b.example.com",
            credentials=b"cred-b",
        )
        assert site1["id"] != site2["id"]
        assert site1["alias"] == site2["alias"] == "shared-alias"


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """Test that deleting a user cascades to their sites."""

    @pytest.mark.unit
    async def test_delete_user_cascades_sites(self, db, user_row, site_row):
        """Deleting a user should also delete their sites."""
        # Verify site exists
        site = await db.get_site(site_row["id"], user_row["id"])
        assert site is not None

        # Delete the user directly
        await db.execute("DELETE FROM users WHERE id = ?", (user_row["id"],))

        # Site should be gone
        row = await db.fetchone("SELECT * FROM sites WHERE id = ?", (site_row["id"],))
        assert row is None


# ---------------------------------------------------------------------------
# update_site_status
# ---------------------------------------------------------------------------


class TestUpdateSiteStatus:
    """Test site status updates."""

    @pytest.mark.unit
    async def test_update_site_status(self, db, user_row, site_row):
        """Should update status and status_msg."""
        await db.update_site_status(site_row["id"], "active", "Connected successfully")

        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is not None
        assert fetched["status"] == "active"
        assert fetched["status_msg"] == "Connected successfully"

    @pytest.mark.unit
    async def test_update_site_status_to_error(self, db, user_row, site_row):
        """Should allow setting error status with a message."""
        await db.update_site_status(site_row["id"], "error", "Connection refused")

        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is not None
        assert fetched["status"] == "error"
        assert fetched["status_msg"] == "Connection refused"

    @pytest.mark.unit
    async def test_update_site_status_clears_message(self, db, user_row, site_row):
        """Should clear status_msg when set to None."""
        await db.update_site_status(site_row["id"], "active", "All good")
        await db.update_site_status(site_row["id"], "disabled")

        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is not None
        assert fetched["status"] == "disabled"
        assert fetched["status_msg"] is None

    @pytest.mark.unit
    async def test_update_site_status_with_user_id(self, db, user_row, site_row):
        """Should update when user_id matches the site owner."""
        await db.update_site_status(site_row["id"], "active", "OK", user_id=user_row["id"])
        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is not None
        assert fetched["status"] == "active"

    @pytest.mark.unit
    async def test_update_site_status_wrong_user_id_no_effect(self, db, user_row, site_row):
        """Should not update when user_id doesn't match."""
        await db.update_site_status(site_row["id"], "active", "OK", user_id="wrong-user-id")
        fetched = await db.get_site(site_row["id"], user_row["id"])
        assert fetched is not None
        assert fetched["status"] == "pending"  # unchanged


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    """Test async context manager support."""

    @pytest.mark.unit
    async def test_context_manager(self, tmp_path):
        """async with Database(...) as db: should work."""
        db_path = str(tmp_path / "ctx_test.db")
        async with Database(db_path) as db:
            user = await db.create_user(
                email="ctx@example.com",
                name="Context",
                provider="github",
                provider_id="gh-ctx",
            )
            assert user["email"] == "ctx@example.com"

        # After exit, connection should be closed
        assert db._conn is None


# ---------------------------------------------------------------------------
# PRAGMA checks
# ---------------------------------------------------------------------------


class TestPragmas:
    """Test that WAL mode and foreign keys are enabled."""

    @pytest.mark.unit
    async def test_wal_mode_enabled(self, db):
        """PRAGMA journal_mode should be WAL."""
        row = await db.fetchone("PRAGMA journal_mode")
        assert row is not None
        assert row["journal_mode"].lower() == "wal"

    @pytest.mark.unit
    async def test_foreign_keys_enabled(self, db):
        """PRAGMA foreign_keys should be ON (1)."""
        row = await db.fetchone("PRAGMA foreign_keys")
        assert row is not None
        assert row["foreign_keys"] == 1


# ---------------------------------------------------------------------------
# Concurrent access
# ---------------------------------------------------------------------------


class TestConcurrentAccess:
    """Test that two Database instances on the same file don't deadlock."""

    @pytest.mark.unit
    async def test_concurrent_instances(self, tmp_path):
        """Two Database instances on the same file should not deadlock."""
        db_path = str(tmp_path / "concurrent.db")

        async with Database(db_path) as db1, Database(db_path) as db2:
            user1 = await db1.create_user(
                email="user1@example.com",
                name="User 1",
                provider="github",
                provider_id="gh-1",
            )
            user2 = await db2.create_user(
                email="user2@example.com",
                name="User 2",
                provider="google",
                provider_id="gg-2",
            )

            # Both users should be visible from either connection
            fetched1 = await db2.get_user_by_id(user1["id"])
            fetched2 = await db1.get_user_by_id(user2["id"])
            assert fetched1 is not None
            assert fetched2 is not None
            assert fetched1["email"] == "user1@example.com"
            assert fetched2["email"] == "user2@example.com"


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    """Test behavior with empty or non-existent data."""

    @pytest.mark.unit
    async def test_get_user_by_id_nonexistent(self, db):
        """get_user_by_id with a fake UUID should return None."""
        result = await db.get_user_by_id("00000000-0000-0000-0000-000000000000")
        assert result is None

    @pytest.mark.unit
    async def test_get_user_by_provider_nonexistent(self, db):
        """get_user_by_provider with a fake combo should return None."""
        result = await db.get_user_by_provider("unknown_provider", "fake_id")
        assert result is None

    @pytest.mark.unit
    async def test_get_site_nonexistent(self, db):
        """get_site with fake IDs should return None."""
        result = await db.get_site("fake-site-id", "fake-user-id")
        assert result is None

    @pytest.mark.unit
    async def test_get_sites_by_user_nonexistent(self, db):
        """get_sites_by_user with a fake user ID should return empty list."""
        result = await db.get_sites_by_user("fake-user-id")
        assert result == []


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestSiteToolToggles:
    """F.7b: per-site tool toggle and tool_scope helpers."""

    @pytest.mark.unit
    async def test_empty_toggles_by_default(self, db, site_row):
        assert await db.get_site_tool_toggles(site_row["id"]) == {}

    @pytest.mark.unit
    async def test_set_and_get_toggle(self, db, site_row):
        await db.set_site_tool_toggle(
            site_row["id"], "coolify_list_applications", False, reason="not needed"
        )
        toggles = await db.get_site_tool_toggles(site_row["id"])
        assert toggles == {"coolify_list_applications": False}

    @pytest.mark.unit
    async def test_toggle_is_upsert(self, db, site_row):
        await db.set_site_tool_toggle(site_row["id"], "coolify_get_server", False)
        await db.set_site_tool_toggle(site_row["id"], "coolify_get_server", True)
        toggles = await db.get_site_tool_toggles(site_row["id"])
        assert toggles == {"coolify_get_server": True}

    @pytest.mark.unit
    async def test_delete_toggle(self, db, site_row):
        await db.set_site_tool_toggle(site_row["id"], "coolify_get_server", False)
        removed = await db.delete_site_tool_toggle(site_row["id"], "coolify_get_server")
        assert removed is True
        assert await db.get_site_tool_toggles(site_row["id"]) == {}

    @pytest.mark.unit
    async def test_bulk_set(self, db, site_row):
        n = await db.bulk_set_site_tool_toggles(
            site_row["id"],
            [("coolify_list_applications", False), ("coolify_start_application", False)],
            reason="bulk:deploy",
        )
        assert n == 2
        toggles = await db.get_site_tool_toggles(site_row["id"])
        assert toggles == {
            "coolify_list_applications": False,
            "coolify_start_application": False,
        }

    @pytest.mark.unit
    async def test_toggle_cascades_on_site_delete(self, db, user_row, site_row):
        await db.set_site_tool_toggle(site_row["id"], "coolify_get_server", False)
        await db.delete_site(site_row["id"], user_row["id"])
        rows = await db.fetchall(
            "SELECT * FROM site_tool_toggles WHERE site_id = ?", (site_row["id"],)
        )
        assert rows == []

    @pytest.mark.unit
    async def test_default_tool_scope_is_admin(self, db, site_row):
        assert await db.get_site_tool_scope(site_row["id"]) == "admin"

    @pytest.mark.unit
    async def test_set_tool_scope(self, db, site_row):
        await db.set_site_tool_scope(site_row["id"], "read")
        assert await db.get_site_tool_scope(site_row["id"]) == "read"

    @pytest.mark.unit
    async def test_unknown_site_tool_scope_defaults_admin(self, db):
        assert await db.get_site_tool_scope("does-not-exist") == "admin"


class TestSiteProviderKeys:
    """F.5a.9.x: per-site AI provider key CRUD + cascade on site delete."""

    @pytest.mark.unit
    async def test_empty_list_by_default(self, db, site_row):
        assert await db.list_site_provider_keys(site_row["id"]) == []

    @pytest.mark.unit
    async def test_upsert_and_get(self, db, site_row):
        row = await db.upsert_site_provider_key(site_row["id"], "openai", b"ciphertext-bytes")
        assert row["provider"] == "openai"
        assert row["site_id"] == site_row["id"]

        fetched = await db.get_site_provider_key(site_row["id"], "openai")
        assert fetched is not None
        assert fetched["key_ciphertext"] == b"ciphertext-bytes"

    @pytest.mark.unit
    async def test_upsert_replaces_existing(self, db, site_row):
        await db.upsert_site_provider_key(site_row["id"], "openai", b"first")
        await db.upsert_site_provider_key(site_row["id"], "openai", b"second")

        fetched = await db.get_site_provider_key(site_row["id"], "openai")
        assert fetched is not None
        assert fetched["key_ciphertext"] == b"second"

    @pytest.mark.unit
    async def test_list_orders_by_provider(self, db, site_row):
        await db.upsert_site_provider_key(site_row["id"], "stability", b"s")
        await db.upsert_site_provider_key(site_row["id"], "openai", b"o")
        await db.upsert_site_provider_key(site_row["id"], "replicate", b"r")

        rows = await db.list_site_provider_keys(site_row["id"])
        providers = [r["provider"] for r in rows]
        assert providers == ["openai", "replicate", "stability"]
        # list_* excludes ciphertext
        assert all("key_ciphertext" not in r for r in rows)

    @pytest.mark.unit
    async def test_delete(self, db, site_row):
        await db.upsert_site_provider_key(site_row["id"], "openai", b"x")
        deleted = await db.delete_site_provider_key(site_row["id"], "openai")
        assert deleted is True
        assert await db.get_site_provider_key(site_row["id"], "openai") is None

    @pytest.mark.unit
    async def test_delete_missing_returns_false(self, db, site_row):
        assert await db.delete_site_provider_key(site_row["id"], "openai") is False

    @pytest.mark.unit
    async def test_touch_updates_last_used(self, db, site_row):
        await db.upsert_site_provider_key(site_row["id"], "openai", b"x")
        fetched_before = await db.get_site_provider_key(site_row["id"], "openai")
        assert fetched_before is not None
        assert fetched_before["last_used"] is None

        await db.touch_site_provider_key(site_row["id"], "openai")
        fetched_after = await db.get_site_provider_key(site_row["id"], "openai")
        assert fetched_after is not None
        assert fetched_after["last_used"] is not None

    @pytest.mark.unit
    async def test_cascade_delete_on_site(self, db, user_row, site_row):
        await db.upsert_site_provider_key(site_row["id"], "openai", b"x")
        await db.delete_site(site_row["id"], user_row["id"])

        rows = await db.fetchall(
            "SELECT * FROM site_provider_keys WHERE site_id = ?",
            (site_row["id"],),
        )
        assert rows == []

    @pytest.mark.unit
    async def test_two_sites_keys_are_isolated(self, db, user_row):
        s1 = await db.create_site(
            user_id=user_row["id"],
            plugin_type="wordpress",
            alias="a",
            url="https://a.example.com",
            credentials=b"c1",
        )
        s2 = await db.create_site(
            user_id=user_row["id"],
            plugin_type="woocommerce",
            alias="b",
            url="https://b.example.com",
            credentials=b"c2",
        )
        await db.upsert_site_provider_key(s1["id"], "openai", b"A")
        await db.upsert_site_provider_key(s2["id"], "openai", b"B")

        got_a = await db.get_site_provider_key(s1["id"], "openai")
        got_b = await db.get_site_provider_key(s2["id"], "openai")
        assert got_a is not None and got_a["key_ciphertext"] == b"A"
        assert got_b is not None and got_b["key_ciphertext"] == b"B"


class TestModuleHelpers:
    """Test get_database() and initialize_database() helpers."""

    @pytest.mark.unit
    async def test_get_database_before_init_raises(self, monkeypatch):
        """get_database() should raise RuntimeError if not initialized."""
        # Reset the module-level singleton
        import core.database as db_module

        monkeypatch.setattr(db_module, "_database", None)

        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_database()

    @pytest.mark.unit
    async def test_initialize_and_get_database(self, tmp_path, monkeypatch):
        """initialize_database() should set the singleton, get_database() returns it."""
        import core.database as db_module

        monkeypatch.setattr(db_module, "_database", None)

        db_path = str(tmp_path / "singleton_test.db")
        db = await initialize_database(db_path)
        try:
            assert db is get_database()

            # Should be functional
            user = await db.create_user(
                email="singleton@example.com",
                name="Singleton",
                provider="github",
                provider_id="gh-singleton",
            )
            assert user["email"] == "singleton@example.com"
        finally:
            await db.close()
            monkeypatch.setattr(db_module, "_database", None)
