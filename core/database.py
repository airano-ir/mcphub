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
SCHEMA_VERSION = 5

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
    expires_at  TEXT
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
    ) -> dict[str, Any]:
        """Create a new user API key.

        Args:
            user_id: Owner's UUID.
            key_hash: bcrypt hash of the API key.
            key_prefix: First 8 chars after ``mhu_`` prefix for fast lookup.
            name: Human label (e.g. "Claude Desktop").
            scopes: Space-separated scopes.
            expires_at: Optional ISO 8601 expiry timestamp.

        Returns:
            The created API key row as a dict.
        """
        key_id = str(uuid.uuid4())
        now = _utc_now()

        await self.execute(
            "INSERT INTO user_api_keys "
            "(id, user_id, key_hash, key_prefix, name, scopes, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (key_id, user_id, key_hash, key_prefix, name, scopes, now, expires_at),
        )

        result = await self.fetchone(
            "SELECT id, user_id, key_prefix, name, scopes, last_used, use_count, "
            "created_at, expires_at FROM user_api_keys WHERE id = ?",
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
            "created_at, expires_at FROM user_api_keys WHERE user_id = ? ORDER BY created_at",
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
