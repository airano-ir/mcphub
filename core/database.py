"""SQLite database backend for the Live Platform (Track E).

Manages the database connection, schema creation, migrations, and CRUD
operations for the user system. Uses aiosqlite for async SQLite access
with WAL mode and foreign key enforcement.

This module is only for user-registered sites on the Live Platform.
Admin endpoints continue to use env var sites via SiteManager.

Usage:
    db = await initialize_database()
    user = await db.create_user(
        email="user@example.com",
        name="Jane",
        provider="github",
        provider_id="12345",
    )
    await db.close()

    # Or as a context manager:
    async with Database("/tmp/test.db") as db:
        user = await db.get_user_by_id("some-uuid")
"""

import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Default data directory: /app/data in Docker, ./data elsewhere
_DEFAULT_DATA_DIR = "/app/data" if Path("/app").exists() else "./data"

# Schema version — increment when adding migrations
SCHEMA_VERSION = 13

# Initial schema DDL
_SCHEMA_SQL = """\
-- Users (OAuth social login)
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    avatar_url  TEXT,
    provider    TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'user',
    created_at  TEXT NOT NULL,
    last_login  TEXT,
    UNIQUE(provider, provider_id)
);

-- User's registered sites (any plugin type)
CREATE TABLE IF NOT EXISTS sites (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_type TEXT NOT NULL,
    alias       TEXT NOT NULL,
    url         TEXT NOT NULL,
    credentials BLOB NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    status_msg  TEXT,
    last_health TEXT,
    last_tested_at TEXT,
    tool_scope  TEXT NOT NULL DEFAULT 'admin',
    created_at  TEXT NOT NULL,
    UNIQUE(user_id, alias)
);

-- Per-user API keys (for MCP client authentication)
CREATE TABLE IF NOT EXISTS user_api_keys (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash    TEXT NOT NULL,
    key_prefix  TEXT,
    name        TEXT NOT NULL,
    scopes      TEXT NOT NULL DEFAULT 'read write',
    last_used   TEXT,
    use_count   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    expires_at  TEXT,
    site_id     TEXT
);

-- WP plugin connection tokens (short-lived, for MCP Connect plugin)
CREATE TABLE IF NOT EXISTS connection_tokens (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

-- F.7b: per-site tool toggles (scope-based visibility overrides)
CREATE TABLE IF NOT EXISTS site_tool_toggles (
    id          TEXT PRIMARY KEY,
    site_id     TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    tool_name   TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    reason      TEXT,
    updated_at  TEXT NOT NULL,
    UNIQUE(site_id, tool_name)
);
CREATE INDEX IF NOT EXISTS idx_site_tool_toggles_site ON site_tool_toggles(site_id);

-- F.5a.4 user_provider_keys table removed in F.5a.9.x / schema v12 —
-- replaced by site_provider_keys (defined below) which stores AI provider
-- credentials per-site instead of per-user.

-- F.5a.5: chunked-upload sessions (SQLite metadata + disk spill)
CREATE TABLE IF NOT EXISTS upload_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    filename        TEXT NOT NULL,
    total_bytes     INTEGER NOT NULL,
    mime            TEXT,
    sha256          TEXT,
    received_bytes  INTEGER NOT NULL DEFAULT 0,
    next_chunk      INTEGER NOT NULL DEFAULT 0,
    spill_path      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_upload_sessions_user_status
    ON upload_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_upload_sessions_expires
    ON upload_sessions(expires_at);

-- F.5a.9.x: per-site AI provider keys (AES-GCM encrypted, reversible).
-- Replaces the per-user user_provider_keys table with a per-site model so
-- each WordPress/WooCommerce site carries its own OpenAI/Stability/Replicate
-- credential in its Connection Settings. Encryption scope:
--   site_provider:{site_id}:{provider}
CREATE TABLE IF NOT EXISTS site_provider_keys (
    id              TEXT PRIMARY KEY,
    site_id         TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,
    key_ciphertext  BLOB NOT NULL,
    created_at      TEXT NOT NULL,
    last_used       TEXT,
    default_model   TEXT,
    UNIQUE(site_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_site_provider_keys_site
    ON site_provider_keys(site_id);
"""

# Migration registry: version -> SQL string
# Migrations are applied sequentially from the current version + 1 up to SCHEMA_VERSION.
_MIGRATIONS: dict[int, str] = {
    2: (
        "ALTER TABLE user_api_keys ADD COLUMN key_prefix TEXT;\n"
        "CREATE INDEX IF NOT EXISTS idx_user_api_keys_prefix ON user_api_keys(key_prefix);\n"
    ),
    4: "ALTER TABLE sites ADD COLUMN last_tested_at TEXT;\n",
    5: (
        "ALTER TABLE sites ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0;\n"
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_system_site_alias "
        "ON sites(alias) WHERE is_system = 1;\n"
        "CREATE TABLE IF NOT EXISTS settings (\n"
        "    key         TEXT PRIMARY KEY,\n"
        "    value       TEXT NOT NULL,\n"
        "    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))\n"
        ");\n"
    ),
    6: (
        # F.7: per-user tool toggles for scope-based visibility & per-tool disable
        "CREATE TABLE IF NOT EXISTS user_tool_toggles (\n"
        "    id          TEXT PRIMARY KEY,\n"
        "    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n"
        "    tool_name   TEXT NOT NULL,\n"
        "    enabled     INTEGER NOT NULL DEFAULT 1,\n"
        "    reason      TEXT,\n"
        "    updated_at  TEXT NOT NULL,\n"
        "    UNIQUE(user_id, tool_name)\n"
        ");\n"
        "CREATE INDEX IF NOT EXISTS idx_user_tool_toggles_user "
        "ON user_tool_toggles(user_id);\n"
    ),
    7: (
        # F.7b: move tool toggles from per-user to per-site and add a
        # per-site preset column. user_tool_toggles was merged on Phase-1
        # but never populated with real data — safe to drop.
        "DROP TABLE IF EXISTS user_tool_toggles;\n"
        "CREATE TABLE IF NOT EXISTS site_tool_toggles (\n"
        "    id          TEXT PRIMARY KEY,\n"
        "    site_id     TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,\n"
        "    tool_name   TEXT NOT NULL,\n"
        "    enabled     INTEGER NOT NULL DEFAULT 1,\n"
        "    reason      TEXT,\n"
        "    updated_at  TEXT NOT NULL,\n"
        "    UNIQUE(site_id, tool_name)\n"
        ");\n"
        "CREATE INDEX IF NOT EXISTS idx_site_tool_toggles_site "
        "ON site_tool_toggles(site_id);\n"
        "ALTER TABLE sites ADD COLUMN tool_scope TEXT NOT NULL DEFAULT 'admin';\n"
    ),
    8: (
        # F.7c: per-site API keys — allow keys scoped to a single site
        "ALTER TABLE user_api_keys ADD COLUMN site_id TEXT;\n"
    ),
    9: (
        # F.5a.4: per-user AI provider keys (AES-GCM encrypted, reversible —
        # distinct from the bcrypt-hashed user_api_keys which authenticate MCP
        # clients and cannot be used to call outbound provider APIs).
        "CREATE TABLE IF NOT EXISTS user_provider_keys (\n"
        "    id              TEXT PRIMARY KEY,\n"
        "    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n"
        "    provider        TEXT NOT NULL,\n"
        "    key_ciphertext  BLOB NOT NULL,\n"
        "    created_at      TEXT NOT NULL,\n"
        "    last_used       TEXT,\n"
        "    UNIQUE(user_id, provider)\n"
        ");\n"
        "CREATE INDEX IF NOT EXISTS idx_user_provider_keys_user "
        "ON user_provider_keys(user_id);\n"
    ),
    10: (
        # F.5a.5: chunked upload sessions (SQLite metadata + disk spill)
        "CREATE TABLE IF NOT EXISTS upload_sessions (\n"
        "    id              TEXT PRIMARY KEY,\n"
        "    user_id         TEXT NOT NULL,\n"
        "    filename        TEXT NOT NULL,\n"
        "    total_bytes     INTEGER NOT NULL,\n"
        "    mime            TEXT,\n"
        "    sha256          TEXT,\n"
        "    received_bytes  INTEGER NOT NULL DEFAULT 0,\n"
        "    next_chunk      INTEGER NOT NULL DEFAULT 0,\n"
        "    spill_path      TEXT NOT NULL,\n"
        "    status          TEXT NOT NULL DEFAULT 'open',\n"
        "    created_at      TEXT NOT NULL,\n"
        "    expires_at      TEXT NOT NULL\n"
        ");\n"
        "CREATE INDEX IF NOT EXISTS idx_upload_sessions_user_status "
        "ON upload_sessions(user_id, status);\n"
        "CREATE INDEX IF NOT EXISTS idx_upload_sessions_expires "
        "ON upload_sessions(expires_at);\n"
    ),
    11: (
        # F.5a.9.x step 1: add per-site provider keys table. The legacy
        # per-user user_provider_keys table is dropped in migration 12
        # (after the code paths that read it are removed).
        "CREATE TABLE IF NOT EXISTS site_provider_keys (\n"
        "    id              TEXT PRIMARY KEY,\n"
        "    site_id         TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,\n"
        "    provider        TEXT NOT NULL,\n"
        "    key_ciphertext  BLOB NOT NULL,\n"
        "    created_at      TEXT NOT NULL,\n"
        "    last_used       TEXT,\n"
        "    default_model   TEXT,\n"
        "    UNIQUE(site_id, provider)\n"
        ");\n"
        "CREATE INDEX IF NOT EXISTS idx_site_provider_keys_site "
        "ON site_provider_keys(site_id);\n"
    ),
    12: (
        # F.5a.9.x step 2: drop the legacy per-user provider-keys store
        # now that the resolver, dashboard page, and HTTP endpoints have
        # been removed. Confirmed with operator that no users had keys
        # stored on the live instance, so no data migration is needed.
        "DROP INDEX IF EXISTS idx_user_provider_keys_user;\n"
        "DROP TABLE IF EXISTS user_provider_keys;\n"
    ),
    13: (
        # F.X.fix-pass3: per-site default image model. Lets the user
        # pick a discovered OpenRouter model (e.g. google/gemini-2.5-
        # flash-image) as the implicit default for that site, so MCP
        # callers don't have to pass `model=...` every time.
        "ALTER TABLE site_provider_keys ADD COLUMN default_model TEXT;\n"
    ),
}


class Database:
    """Async SQLite database for the Live Platform.

    Manages connections, schema, migrations, and provides CRUD helpers
    for users, sites, API keys, and connection tokens.

    Attributes:
        db_path: Resolved path to the SQLite database file.
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize database configuration.

        Args:
            db_path: Path to the SQLite database file. If not provided,
                reads DATABASE_PATH env var, defaulting to ``data/mcphub.db``.
        """
        if db_path is None:
            db_file = os.getenv("DATABASE_PATH", None)
            if db_file:
                self.db_path = Path(db_file)
            else:
                self.db_path = Path(_DEFAULT_DATA_DIR) / "mcphub.db"
        else:
            self.db_path = Path(db_path)

        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create data directory, connect, and set up schema.

        Enables WAL mode and foreign keys, creates tables if they do
        not exist, and runs any pending migrations.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrent read performance
        await self._conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign key enforcement
        await self._conn.execute("PRAGMA foreign_keys=ON")

        await self._create_schema()
        await self._run_migrations()

        logger.info("Database initialized at %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "Database":
        """Enter async context — initialize and return self."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context — close the connection."""
        await self.close()

    # ------------------------------------------------------------------
    # Low-level query helpers
    # ------------------------------------------------------------------

    def _require_conn(self) -> aiosqlite.Connection:
        """Return the active connection or raise if not initialized."""
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._conn

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        """Execute a single write SQL statement and commit.

        Args:
            sql: SQL statement.
            params: Bind parameters.

        Returns:
            The aiosqlite Cursor.
        """
        conn = self._require_conn()
        cursor = await conn.execute(sql, params)
        await conn.commit()
        return cursor

    async def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> aiosqlite.Cursor:
        """Execute a SQL statement with multiple parameter sets and commit.

        Args:
            sql: SQL statement.
            params_list: List of parameter tuples.

        Returns:
            The aiosqlite Cursor.
        """
        conn = self._require_conn()
        cursor = await conn.executemany(sql, params_list)
        await conn.commit()
        return cursor

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Fetch a single row as a dictionary (read-only, no commit).

        Args:
            sql: SQL query.
            params: Bind parameters.

        Returns:
            Row as a dict, or None if no result.
        """
        conn = self._require_conn()
        cursor = await conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Fetch all rows as a list of dictionaries (read-only, no commit).

        Args:
            sql: SQL query.
            params: Bind parameters.

        Returns:
            List of rows, each as a dict.
        """
        conn = self._require_conn()
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    async def _create_schema(self) -> None:
        """Create all tables if they do not already exist."""
        conn = self._require_conn()

        # Check if it's a completely fresh DB (no users table)
        row = await self.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        is_fresh = row is None

        await conn.executescript(_SCHEMA_SQL)

        if is_fresh:
            # Seed initial schema version
            row = await self.fetchone("SELECT MAX(version) AS v FROM schema_version")
            if row is None or row["v"] is None:
                await self.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _utc_now()),
                )
        else:
            # For existing v1 databases, if schema_version was just created
            row = await self.fetchone("SELECT COUNT(*) as c FROM schema_version")
            if row and row["c"] == 0:
                await self.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (1, _utc_now()),
                )

    async def _run_migrations(self) -> None:
        """Apply any pending migrations sequentially."""
        conn = self._require_conn()
        row = await self.fetchone("SELECT MAX(version) AS v FROM schema_version")
        current = row["v"] if row and row["v"] is not None else 0

        for version in range(current + 1, SCHEMA_VERSION + 1):
            if version == 3:
                logger.info("Applying python migration for version 3")
                # Idempotent repair for v1->v2 upgrade bug (some DBs stamped v2 but missed the column)
                try:
                    await self.execute("ALTER TABLE user_api_keys ADD COLUMN key_prefix TEXT")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        raise
                await self.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_api_keys_prefix ON user_api_keys(key_prefix)"
                )
            else:
                migration_sql = _MIGRATIONS.get(version)
                if migration_sql is not None:
                    logger.info("Applying migration to version %d", version)
                    await conn.executescript(migration_sql)
                    logger.info("Migration to version %d applied", version)
                else:
                    logger.warning(
                        "No migration SQL for version %d, recording version only", version
                    )

            # Always record version to avoid infinite retry
            await self.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, _utc_now()),
            )

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------

    async def create_user(
        self,
        email: str,
        name: str | None,
        provider: str,
        provider_id: str,
        avatar_url: str | None = None,
        role: str = "user",
    ) -> dict[str, Any]:
        """Create a new user.

        Args:
            email: User email (unique).
            name: Display name.
            provider: OAuth provider ('github' or 'google').
            provider_id: Provider's unique user ID.
            avatar_url: URL to user avatar.
            role: User role ('user' or 'admin').

        Returns:
            The created user as a dict.

        Raises:
            aiosqlite.IntegrityError: If email or provider+provider_id already exists.
        """
        user_id = str(uuid.uuid4())
        now = _utc_now()

        await self.execute(
            "INSERT INTO users (id, email, name, avatar_url, provider, provider_id, role, "
            "created_at, last_login) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, email, name, avatar_url, provider, provider_id, role, now, now),
        )

        result = await self.get_user_by_id(user_id)
        if result is None:
            raise RuntimeError(f"Failed to read back created user {user_id}")
        return result

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Get a user by their UUID.

        Args:
            user_id: User UUID.

        Returns:
            User dict, or None if not found.
        """
        return await self.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get a user by their email.

        Args:
            email: User email.

        Returns:
            User dict, or None if not found.
        """
        return await self.fetchone("SELECT * FROM users WHERE email = ?", (email,))

    async def get_user_by_provider(self, provider: str, provider_id: str) -> dict[str, Any] | None:
        """Get a user by OAuth provider and provider ID.

        Args:
            provider: OAuth provider name.
            provider_id: Provider's unique user ID.

        Returns:
            User dict, or None if not found.
        """
        return await self.fetchone(
            "SELECT * FROM users WHERE provider = ? AND provider_id = ?",
            (provider, provider_id),
        )

    async def update_user_last_login(self, user_id: str) -> None:
        """Update a user's last_login timestamp to now.

        Args:
            user_id: User UUID.
        """
        await self.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (_utc_now(), user_id),
        )

    # ------------------------------------------------------------------
    # Site CRUD
    # ------------------------------------------------------------------

    async def create_site(
        self,
        user_id: str,
        plugin_type: str,
        alias: str,
        url: str,
        credentials: bytes,
        status: str = "pending",
        status_msg: str | None = None,
    ) -> dict[str, Any]:
        """Create a new site for a user.

        Args:
            user_id: Owner's UUID.
            plugin_type: Plugin type (e.g. 'wordpress', 'gitea').
            alias: User-chosen friendly name (unique per user).
            url: Site URL.
            credentials: AES-256-GCM encrypted credentials blob.
            status: Initial status ('pending', 'active', 'error', 'disabled').
            status_msg: Optional human-readable status message.

        Returns:
            The created site as a dict.

        Raises:
            aiosqlite.IntegrityError: If alias is duplicated for the same user.
        """
        site_id = str(uuid.uuid4())
        now = _utc_now()

        await self.execute(
            "INSERT INTO sites (id, user_id, plugin_type, alias, url, credentials, "
            "status, status_msg, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (site_id, user_id, plugin_type, alias, url, credentials, status, status_msg, now),
        )

        result = await self.get_site(site_id, user_id)
        if result is None:
            raise RuntimeError(f"Failed to read back created site {site_id}")
        return result

    async def get_sites_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Get all sites belonging to a user.

        Args:
            user_id: Owner's UUID.

        Returns:
            List of site dicts.
        """
        return await self.fetchall(
            "SELECT * FROM sites WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        )

    async def get_site(self, site_id: str, user_id: str) -> dict[str, Any] | None:
        """Get a single site, scoped to a specific user.

        Args:
            site_id: Site UUID.
            user_id: Owner's UUID (for tenant isolation).

        Returns:
            Site dict, or None if not found or not owned by user.
        """
        return await self.fetchone(
            "SELECT * FROM sites WHERE id = ? AND user_id = ?",
            (site_id, user_id),
        )

    async def delete_site(self, site_id: str, user_id: str) -> bool:
        """Delete a site, scoped to a specific user.

        Args:
            site_id: Site UUID.
            user_id: Owner's UUID (for tenant isolation).

        Returns:
            True if a row was deleted, False otherwise.
        """
        cursor = await self.execute(
            "DELETE FROM sites WHERE id = ? AND user_id = ?",
            (site_id, user_id),
        )
        return cursor.rowcount > 0

    async def update_site_status(
        self,
        site_id: str,
        status: str,
        status_msg: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Update a site's status and optional status message.

        Args:
            site_id: Site UUID.
            status: New status ('pending', 'active', 'error', 'disabled').
            status_msg: Optional human-readable status message.
            user_id: Optional user UUID for tenant-scoped update. When provided,
                only updates if the site belongs to this user. When None,
                performs system-level update (e.g., health checks).
        """
        now = _utc_now()
        if user_id is not None:
            await self.execute(
                "UPDATE sites SET status = ?, status_msg = ?, last_tested_at = ?"
                " WHERE id = ? AND user_id = ?",
                (status, status_msg, now, site_id, user_id),
            )
        else:
            await self.execute(
                "UPDATE sites SET status = ?, status_msg = ?, last_tested_at = ?" " WHERE id = ?",
                (status, status_msg, now, site_id),
            )

    async def update_site_credentials(
        self,
        site_id: str,
        user_id: str,
        url: str,
        credentials: bytes,
    ) -> bool:
        """Update URL and credentials for an existing site.

        Args:
            site_id: Site UUID.
            user_id: Owner's UUID (for tenant isolation).
            url: New base URL for the site.
            credentials: New AES-256-GCM encrypted credentials blob.

        Returns:
            True if a row was updated, False if site not found or not owned by user.
        """
        cursor = await self.execute(
            "UPDATE sites SET url = ?, credentials = ?, status = 'pending' WHERE id = ? AND user_id = ?",
            (url, credentials, site_id, user_id),
        )
        return cursor.rowcount > 0

    async def get_site_by_alias(self, user_id: str, alias: str) -> dict[str, Any] | None:
        """Get a site by user ID and alias.

        Args:
            user_id: Owner's UUID.
            alias: Site alias (unique per user).

        Returns:
            Site dict, or None if not found.
        """
        return await self.fetchone(
            "SELECT * FROM sites WHERE user_id = ? AND alias = ?",
            (user_id, alias),
        )

    async def count_sites_by_user(self, user_id: str) -> int:
        """Count the number of sites belonging to a user.

        Args:
            user_id: Owner's UUID.

        Returns:
            Number of sites.
        """
        row = await self.fetchone(
            "SELECT COUNT(*) AS cnt FROM sites WHERE user_id = ?",
            (user_id,),
        )
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # Settings CRUD (Phase 4C.3)
    # ------------------------------------------------------------------

    async def get_setting(self, key: str) -> str | None:
        """Get a setting value by key."""
        row = await self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value (upsert)."""
        await self.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?",
            (key, value, _utc_now(), value, _utc_now()),
        )

    async def delete_setting(self, key: str) -> bool:
        """Delete a setting. Returns True if deleted."""
        cursor = await self.execute("DELETE FROM settings WHERE key = ?", (key,))
        return cursor.rowcount > 0

    async def get_all_settings(self) -> dict[str, str]:
        """Get all settings as a dict."""
        rows = await self.fetchall("SELECT key, value FROM settings")
        return {r["key"]: r["value"] for r in rows}

    # ------------------------------------------------------------------
    # User API Key CRUD
    # ------------------------------------------------------------------

    async def create_api_key(
        self,
        user_id: str,
        key_hash: str,
        key_prefix: str,
        name: str,
        scopes: str = "read write",
        expires_at: str | None = None,
        site_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new user API key.

        Args:
            user_id: Owner's UUID.
            key_hash: bcrypt hash of the API key.
            key_prefix: First 8 chars after ``mhu_`` prefix for fast lookup.
            name: Human label (e.g. "Claude Desktop").
            scopes: Space-separated scopes.
            expires_at: Optional ISO 8601 expiry timestamp.
            site_id: Optional site UUID to scope key to a single site.

        Returns:
            The created API key row as a dict.
        """
        key_id = str(uuid.uuid4())
        now = _utc_now()

        await self.execute(
            "INSERT INTO user_api_keys "
            "(id, user_id, key_hash, key_prefix, name, scopes, created_at, expires_at, site_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key_id, user_id, key_hash, key_prefix, name, scopes, now, expires_at, site_id),
        )

        result = await self.fetchone(
            "SELECT id, user_id, key_prefix, name, scopes, last_used, use_count, "
            "created_at, expires_at, site_id FROM user_api_keys WHERE id = ?",
            (key_id,),
        )
        if result is None:
            raise RuntimeError(f"Failed to read back created API key {key_id}")
        return result

    async def get_api_keys_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Get all API keys for a user (without key_hash).

        Args:
            user_id: Owner's UUID.

        Returns:
            List of API key dicts (key_hash excluded).
        """
        return await self.fetchall(
            "SELECT id, user_id, key_prefix, name, scopes, last_used, use_count, "
            "created_at, expires_at, site_id FROM user_api_keys WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        )

    async def get_api_key_by_prefix(self, key_prefix: str) -> dict[str, Any] | None:
        """Get an API key by its prefix (includes key_hash for verification).

        Args:
            key_prefix: First 8 chars of the key after ``mhu_``.

        Returns:
            API key dict including key_hash, or None.
        """
        return await self.fetchone(
            "SELECT * FROM user_api_keys WHERE key_prefix = ?",
            (key_prefix,),
        )

    async def delete_api_key(self, key_id: str, user_id: str) -> bool:
        """Delete an API key, scoped to a specific user.

        Args:
            key_id: API key UUID.
            user_id: Owner's UUID (for tenant isolation).

        Returns:
            True if a row was deleted, False otherwise.
        """
        cursor = await self.execute(
            "DELETE FROM user_api_keys WHERE id = ? AND user_id = ?",
            (key_id, user_id),
        )
        return cursor.rowcount > 0

    async def update_api_key_usage(self, key_id: str) -> None:
        """Increment use_count and update last_used timestamp for an API key.

        Args:
            key_id: API key UUID.
        """
        await self.execute(
            "UPDATE user_api_keys SET use_count = use_count + 1, last_used = ? WHERE id = ?",
            (_utc_now(), key_id),
        )

    # ------------------------------------------------------------------
    # Site tool toggles & tool_scope (F.7b)
    # ------------------------------------------------------------------

    async def get_site_tool_toggles(self, site_id: str) -> dict[str, bool]:
        """Get explicit tool toggle overrides for a site.

        Only rows where a tool has been explicitly toggled are stored.
        Tools not in the result are implicitly enabled.

        Args:
            site_id: Site UUID.

        Returns:
            Dict mapping ``tool_name`` → ``enabled`` (bool).
        """
        rows = await self.fetchall(
            "SELECT tool_name, enabled FROM site_tool_toggles WHERE site_id = ?",
            (site_id,),
        )
        return {row["tool_name"]: bool(row["enabled"]) for row in rows}

    async def set_site_tool_toggle(
        self,
        site_id: str,
        tool_name: str,
        enabled: bool,
        reason: str | None = None,
    ) -> None:
        """Upsert a single tool toggle for a site.

        Args:
            site_id: Site UUID.
            tool_name: Fully-qualified tool name (e.g. ``coolify_list_applications``).
            enabled: Whether the tool should be visible on this site.
            reason: Optional note.
        """
        toggle_id = str(uuid.uuid4())
        now = _utc_now()
        await self.execute(
            "INSERT INTO site_tool_toggles (id, site_id, tool_name, enabled, reason, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(site_id, tool_name) DO UPDATE SET "
            "enabled = excluded.enabled, reason = excluded.reason, updated_at = excluded.updated_at",
            (toggle_id, site_id, tool_name, 1 if enabled else 0, reason, now),
        )

    async def delete_site_tool_toggle(self, site_id: str, tool_name: str) -> bool:
        """Delete a site's toggle for a tool (reverts to the default).

        Args:
            site_id: Site UUID.
            tool_name: Fully-qualified tool name.

        Returns:
            True if a row was deleted.
        """
        cursor = await self.execute(
            "DELETE FROM site_tool_toggles WHERE site_id = ? AND tool_name = ?",
            (site_id, tool_name),
        )
        return cursor.rowcount > 0

    async def bulk_set_site_tool_toggles(
        self,
        site_id: str,
        toggles: list[tuple[str, bool]],
        reason: str | None = None,
    ) -> int:
        """Upsert multiple tool toggles for a site in one transaction.

        Args:
            site_id: Site UUID.
            toggles: List of ``(tool_name, enabled)`` pairs.
            reason: Optional shared reason applied to every row.

        Returns:
            Number of rows affected.
        """
        if not toggles:
            return 0
        now = _utc_now()
        rows = [
            (str(uuid.uuid4()), site_id, tool_name, 1 if enabled else 0, reason, now)
            for tool_name, enabled in toggles
        ]
        await self.executemany(
            "INSERT INTO site_tool_toggles (id, site_id, tool_name, enabled, reason, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(site_id, tool_name) DO UPDATE SET "
            "enabled = excluded.enabled, reason = excluded.reason, updated_at = excluded.updated_at",
            rows,
        )
        return len(rows)

    async def get_site_tool_scope(self, site_id: str) -> str:
        """Return the site's ``tool_scope`` preset (defaults to ``'admin'``)."""
        row = await self.fetchone("SELECT tool_scope FROM sites WHERE id = ?", (site_id,))
        if row is None:
            return "admin"
        return row["tool_scope"] or "admin"

    # ------------------------------------------------------------------
    # Site provider keys (F.5a.9.x) — per-site AI provider credentials
    # (replaces the F.5a.4 per-user ``*_provider_key`` helpers dropped in v12)
    # ------------------------------------------------------------------

    async def upsert_site_provider_key(
        self,
        site_id: str,
        provider: str,
        key_ciphertext: bytes,
    ) -> dict[str, Any]:
        """Insert or replace a site's API key for a given AI provider.

        Args:
            site_id: Site UUID.
            provider: Provider identifier (``openai``, ``stability``, ``replicate``).
            key_ciphertext: AES-256-GCM encrypted key bytes.

        Returns:
            The stored row (without plaintext).
        """
        key_id = str(uuid.uuid4())
        now = _utc_now()
        await self.execute(
            "INSERT INTO site_provider_keys (id, site_id, provider, key_ciphertext, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(site_id, provider) DO UPDATE SET "
            "key_ciphertext = excluded.key_ciphertext, created_at = excluded.created_at",
            (key_id, site_id, provider, key_ciphertext, now),
        )
        row = await self.fetchone(
            "SELECT id, site_id, provider, created_at, last_used FROM site_provider_keys "
            "WHERE site_id = ? AND provider = ?",
            (site_id, provider),
        )
        if row is None:
            raise RuntimeError(f"Failed to read back site provider key for {site_id}/{provider}")
        return row

    async def get_site_provider_key(self, site_id: str, provider: str) -> dict[str, Any] | None:
        """Return the encrypted provider key row for a site (includes ciphertext)."""
        return await self.fetchone(
            "SELECT * FROM site_provider_keys WHERE site_id = ? AND provider = ?",
            (site_id, provider),
        )

    async def list_site_provider_keys(self, site_id: str) -> list[dict[str, Any]]:
        """List providers a site has keys for (excluding ciphertext)."""
        return await self.fetchall(
            "SELECT id, site_id, provider, created_at, last_used, default_model "
            "FROM site_provider_keys WHERE site_id = ? ORDER BY provider",
            (site_id,),
        )

    async def delete_site_provider_key(self, site_id: str, provider: str) -> bool:
        """Remove a site's provider key. Returns True if a row was deleted."""
        cursor = await self.execute(
            "DELETE FROM site_provider_keys WHERE site_id = ? AND provider = ?",
            (site_id, provider),
        )
        return cursor.rowcount > 0

    async def touch_site_provider_key(self, site_id: str, provider: str) -> None:
        """Update last_used timestamp after a successful provider call."""
        await self.execute(
            "UPDATE site_provider_keys SET last_used = ? WHERE site_id = ? AND provider = ?",
            (_utc_now(), site_id, provider),
        )

    async def set_site_provider_default_model(
        self, site_id: str, provider: str, model: str | None
    ) -> bool:
        """F.X.fix-pass3 — record the per-site default model for a provider.

        ``model=None`` clears the default. Returns ``True`` when a row
        was actually updated (i.e. the site has a key for the provider);
        callers can surface a 404 to the user when the row doesn't exist
        rather than silently writing nothing.
        """
        cursor = await self.execute(
            "UPDATE site_provider_keys SET default_model = ? " "WHERE site_id = ? AND provider = ?",
            (model, site_id, provider),
        )
        return cursor.rowcount > 0

    async def get_site_provider_default_model(self, site_id: str, provider: str) -> str | None:
        """Return the default model id for a site's provider, or None."""
        row = await self.fetchone(
            "SELECT default_model FROM site_provider_keys " "WHERE site_id = ? AND provider = ?",
            (site_id, provider),
        )
        if row is None:
            return None
        value = row.get("default_model")
        if isinstance(value, str) and value:
            return value
        return None

    async def set_site_tool_scope(self, site_id: str, scope: str) -> None:
        """Update the ``tool_scope`` preset for a site.

        Args:
            site_id: Site UUID.
            scope: One of ``read``, ``read:sensitive``, ``deploy``,
                ``write``, ``admin``, ``custom``.
        """
        await self.execute(
            "UPDATE sites SET tool_scope = ? WHERE id = ?",
            (scope, site_id),
        )


# ======================================================================
# Module-level helpers
# ======================================================================


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


# Singleton instance
_database: Database | None = None


def get_database() -> Database:
    """Get the singleton Database instance.

    Returns:
        The Database singleton.

    Raises:
        RuntimeError: If initialize_database() has not been called.
    """
    if _database is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    return _database


async def initialize_database(db_path: str | None = None) -> Database:
    """Create, initialize, and store the singleton Database instance.

    Args:
        db_path: Optional path to the SQLite database file.

    Returns:
        The initialized Database instance.
    """
    global _database
    db = Database(db_path)
    await db.initialize()
    _database = db
    return db
