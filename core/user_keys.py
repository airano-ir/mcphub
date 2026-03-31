"""User API Key management for the Live Platform (Track E.3).

Provides bcrypt-hashed API keys for authenticating MCP client connections
to per-user endpoints (``/u/{user_id}/{alias}/mcp``).

Key format: ``mhu_<32 random urlsafe chars>``
Lookup: ``key_prefix`` column (first 8 chars after ``mhu_``) for indexed DB lookup,
then bcrypt verification on the matching row.

Usage:
    from core.user_keys import initialize_user_key_manager, get_user_key_manager

    initialize_user_key_manager()
    mgr = get_user_key_manager()
    result = await mgr.create_key(user_id, "Claude Desktop")
    # result["key"] is shown once to the user
    info = await mgr.validate_key("mhu_...")
"""

import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt

logger = logging.getLogger(__name__)

# Key format constants
KEY_PREFIX_TAG = "mhu_"
KEY_RANDOM_BYTES = 32  # urlsafe_b64 of 32 bytes = 43 chars
KEY_PREFIX_LEN = 8  # chars after "mhu_" stored for fast DB lookup

# Validation cache TTL
_CACHE_TTL_SECONDS = 300  # 5 minutes


class UserKeyManager:
    """Manages per-user API keys with bcrypt hashing.

    Keys are stored in the ``user_api_keys`` SQLite table via
    :class:`core.database.Database`. Each key is bcrypt-hashed;
    a plaintext ``key_prefix`` column enables indexed lookup without
    scanning all rows.

    An in-memory cache avoids repeated bcrypt verification for the
    same key within a 5-minute window.
    """

    def __init__(self) -> None:
        # Cache: raw_key -> (key_id, user_id, scopes, cached_at)
        self._cache: dict[str, tuple[str, str, str, float]] = {}

    async def create_key(
        self,
        user_id: str,
        name: str,
        scopes: str = "read write admin",
        expires_in_days: int | None = None,
    ) -> dict[str, Any]:
        """Create a new API key for a user.

        Args:
            user_id: Owner's UUID.
            name: Human label (e.g. "Claude Desktop").
            scopes: Access scopes (default: "read write admin" for full access).
            expires_in_days: Optional expiry in days from now. None = never.

        Returns:
            Dict with ``key`` (plaintext, shown once), ``key_id``, ``name``,
            ``scopes``, ``created_at``, ``expires_at``.
        """
        from core.database import get_database

        raw_key = KEY_PREFIX_TAG + secrets.token_urlsafe(KEY_RANDOM_BYTES)
        key_prefix = raw_key[len(KEY_PREFIX_TAG) : len(KEY_PREFIX_TAG) + KEY_PREFIX_LEN]
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

        expires_at = None
        if expires_in_days is not None:
            expires_at = (datetime.now(UTC) + timedelta(days=expires_in_days)).isoformat()

        db = get_database()
        row = await db.create_api_key(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
        )

        logger.info("Created user API key %s for user %s", row["id"], user_id)
        return {
            "key": raw_key,  # shown once
            "key_id": row["id"],
            "name": row["name"],
            "scopes": row["scopes"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }

    async def validate_key(self, api_key: str) -> dict[str, Any] | None:
        """Validate an API key and return its metadata.

        Uses an in-memory cache to avoid repeated bcrypt verification.

        Args:
            api_key: The raw API key string (e.g. ``mhu_...``).

        Returns:
            Dict with ``key_id``, ``user_id``, ``scopes`` if valid, else None.
        """
        if not api_key or not api_key.startswith(KEY_PREFIX_TAG):
            return None

        # Check cache first
        cached = self._cache.get(api_key)
        if cached is not None:
            key_id, user_id, scopes, cached_at = cached
            if time.time() - cached_at < _CACHE_TTL_SECONDS:
                # Update usage in background (fire-and-forget via DB)
                try:
                    import asyncio

                    from core.database import get_database

                    db = get_database()
                    asyncio.create_task(db.update_api_key_usage(key_id))
                except Exception:
                    pass  # Non-critical
                return {"key_id": key_id, "user_id": user_id, "scopes": scopes}
            else:
                del self._cache[api_key]

        # Extract prefix for DB lookup
        key_prefix = api_key[len(KEY_PREFIX_TAG) : len(KEY_PREFIX_TAG) + KEY_PREFIX_LEN]

        from core.database import get_database

        db = get_database()
        row = await db.get_api_key_by_prefix(key_prefix)

        if row is None:
            return None

        # Verify bcrypt hash
        if not bcrypt.checkpw(api_key.encode(), row["key_hash"].encode()):
            return None

        # Check expiry
        if row["expires_at"] is not None:
            expires = datetime.fromisoformat(row["expires_at"])
            if expires < datetime.now(UTC):
                return None

        # Update usage
        await db.update_api_key_usage(row["id"])

        # Cache the result
        self._cache[api_key] = (
            row["id"],
            row["user_id"],
            row["scopes"],
            time.time(),
        )

        return {
            "key_id": row["id"],
            "user_id": row["user_id"],
            "scopes": row["scopes"],
        }

    async def list_keys(self, user_id: str) -> list[dict[str, Any]]:
        """List all API keys for a user (without hashes).

        Args:
            user_id: Owner's UUID.

        Returns:
            List of key metadata dicts.
        """
        from core.database import get_database

        db = get_database()
        return await db.get_api_keys_by_user(user_id)

    async def delete_key(self, key_id: str, user_id: str) -> bool:
        """Delete an API key.

        Also invalidates the validation cache for any cached key matching
        this key_id.

        Args:
            key_id: API key UUID.
            user_id: Owner's UUID.

        Returns:
            True if deleted, False if not found.
        """
        from core.database import get_database

        db = get_database()
        deleted = await db.delete_api_key(key_id, user_id)

        if deleted:
            # Purge from cache
            to_remove = [k for k, v in self._cache.items() if v[0] == key_id]
            for k in to_remove:
                del self._cache[k]
            logger.info("Deleted user API key %s for user %s", key_id, user_id)

        return deleted

    def clear_cache(self) -> None:
        """Clear the entire validation cache."""
        self._cache.clear()


# Singleton
_manager: UserKeyManager | None = None


def initialize_user_key_manager() -> UserKeyManager:
    """Create and store the singleton UserKeyManager."""
    global _manager
    _manager = UserKeyManager()
    logger.info("UserKeyManager initialized")
    return _manager


def get_user_key_manager() -> UserKeyManager:
    """Get the singleton UserKeyManager.

    Returns:
        The UserKeyManager singleton.

    Raises:
        RuntimeError: If not initialized.
    """
    if _manager is None:
        raise RuntimeError(
            "UserKeyManager not initialized. Call initialize_user_key_manager() first."
        )
    return _manager
