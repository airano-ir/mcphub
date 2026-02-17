"""
API Key Management System

Comprehensive per-project API key management with scopes, expiration,
and audit trail.
"""

import hashlib
import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Valid scope values
VALID_SCOPES = ["read", "write", "admin"]

# Scope can be single ("read") or multiple space-separated ("read write admin")
Scope = str

def validate_scope(scope: str) -> bool:
    """
    Validate that scope contains only valid scope values.

    Args:
        scope: Single scope ("read") or space-separated scopes ("read write admin")

    Returns:
        True if all scopes are valid, False otherwise
    """
    if not scope:
        return False

    scope_list = scope.split()
    return all(s in VALID_SCOPES for s in scope_list)

def normalize_scope(scope: str) -> str:
    """
    Normalize scope string by removing duplicates and sorting.

    Args:
        scope: Single scope or space-separated scopes

    Returns:
        Normalized scope string (e.g., "admin read write" -> "read write admin")
    """
    scope_list = scope.split()
    # Remove duplicates, sort by priority (read < write < admin)
    unique_scopes = []
    for s in ["read", "write", "admin"]:
        if s in scope_list:
            unique_scopes.append(s)
    return " ".join(unique_scopes)

@dataclass
class APIKey:
    """
    Represents an API key with metadata.

    Fields:
        key_id: Unique identifier for the key
        key_hash: SHA256 hash of the actual key (for storage)
        project_id: Project this key belongs to ("*" for all projects)
        scope: Access scope - single ("read") or multiple space-separated ("read write admin")
        created_at: ISO timestamp when created
        expires_at: Optional ISO timestamp when expires
        last_used_at: Optional ISO timestamp of last use
        usage_count: Number of times used
        description: Optional description
        revoked: Whether the key has been revoked
    """

    key_id: str
    key_hash: str
    project_id: str
    scope: Scope
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None
    usage_count: int = 0
    description: str | None = None
    revoked: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "APIKey":
        """Create from dictionary."""
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if key has expired."""
        if not self.expires_at:
            return False
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now() > expires

    def is_valid(self) -> bool:
        """Check if key is valid (not revoked, not expired)."""
        return not self.revoked and not self.is_expired()

class APIKeyManager:
    """
    Manages per-project API keys with persistence.

    Features:
    - Persistent JSON storage
    - Key creation with scopes
    - Key validation with project and scope checking
    - Key rotation and revocation
    - Usage tracking
    - Expiration support
    """

    def __init__(self, storage_path: str = "data/api_keys.json"):
        """
        Initialize API Key Manager.

        Args:
            storage_path: Path to JSON file for key storage
        """
        self.storage_path = Path(storage_path)
        self.keys: dict[str, APIKey] = {}

        # Ensure storage directory exists (with graceful fallback)
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to /tmp if we can't create in data/
            logger.warning(
                f"Cannot create directory {self.storage_path.parent}, " f"falling back to /tmp"
            )
            self.storage_path = Path("/tmp/api_keys.json")
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing keys
        self._load_keys()

        logger.info(
            f"API Key Manager initialized with {len(self.keys)} keys "
            f"(storage: {self.storage_path})"
        )

    def _load_keys(self) -> None:
        """Load keys from storage file."""
        if not self.storage_path.exists():
            logger.info("No existing keys file found, starting fresh")
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)
                self.keys = {
                    key_id: APIKey.from_dict(key_data) for key_id, key_data in data.items()
                }
            logger.info(f"Loaded {len(self.keys)} keys from storage")
        except Exception as e:
            logger.error(f"Failed to load keys: {e}")
            self.keys = {}

    def _save_keys(self) -> None:
        """Save keys to storage file."""
        try:
            data = {key_id: key.to_dict() for key_id, key in self.keys.items()}
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.keys)} keys to storage")
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")

    def _hash_key(self, api_key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def create_key(
        self,
        project_id: str,
        scope: Scope = "read",
        expires_in_days: int | None = None,
        description: str | None = None,
    ) -> dict[str, str]:
        """
        Create a new API key.

        Args:
            project_id: Project ID ("*" for all projects)
            scope: Access scope - single ("read") or multiple space-separated ("read write admin")
            expires_in_days: Optional expiration in days
            description: Optional description

        Returns:
            dict: {"key": actual_key, "key_id": key_id, "project_id": project_id, "scope": scope}

        Raises:
            ValueError: If scope contains invalid values
        """
        # Validate and normalize scope
        if not validate_scope(scope):
            raise ValueError(
                f"Invalid scope: {scope}. Must contain only: {', '.join(VALID_SCOPES)}"
            )
        normalized_scope = normalize_scope(scope)

        # Generate secure random key
        api_key = f"cmp_{secrets.token_urlsafe(32)}"
        key_id = f"key_{secrets.token_urlsafe(16)}"
        key_hash = self._hash_key(api_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires = datetime.now() + timedelta(days=expires_in_days)
            expires_at = expires.isoformat()

        # Create key object
        key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            project_id=project_id,
            scope=normalized_scope,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at,
            description=description,
        )

        # Store and save
        self.keys[key_id] = key
        self._save_keys()

        logger.info(
            f"Created API key {key_id} for project {project_id} " f"with scope '{normalized_scope}'"
        )

        return {
            "key": api_key,
            "key_id": key_id,
            "scope": normalized_scope,
            "project_id": project_id,
            "expires_at": expires_at,
        }

    def validate_key(
        self,
        api_key: str,
        project_id: str,
        required_scope: Scope = "read",
        skip_project_check: bool = False,
    ) -> str | None:
        """
        Validate API key for project and scope.

        Args:
            api_key: The API key to validate
            project_id: Project to check access for
            required_scope: Minimum required scope
            skip_project_check: Skip project-level validation (for unified tools)

        Returns:
            Optional[str]: key_id if valid, None otherwise
        """
        key_hash = self._hash_key(api_key)

        # Find key by hash
        for key_id, key in self.keys.items():
            if key.key_hash != key_hash:
                continue

            # Check if valid (not revoked, not expired)
            if not key.is_valid():
                logger.warning(
                    f"Key {key_id} is invalid "
                    f"(revoked={key.revoked}, expired={key.is_expired()})"
                )
                return None

            # Check project access (unless skipped for unified tools)
            if not skip_project_check:
                if key.project_id != "*" and key.project_id != project_id:
                    logger.warning(f"Key {key_id} does not have access to project {project_id}")
                    return None

            # Check scope: key must have required_scope or higher
            # Scope hierarchy: admin > write > read
            scope_hierarchy = {"read": 0, "write": 1, "admin": 2}
            key_scopes = key.scope.split()

            # Check if required_scope is directly present
            if required_scope in key_scopes:
                # Update usage tracking
                key.last_used_at = datetime.now().isoformat()
                key.usage_count += 1
                self._save_keys()

                logger.debug(f"Key {key_id} validated successfully (scope: {key.scope})")
                return key_id

            # Check if key has higher scope (e.g., admin covers write and read)
            key_level = max(scope_hierarchy.get(s, 0) for s in key_scopes)
            required_level = scope_hierarchy.get(required_scope, 0)

            if key_level >= required_level:
                # Update usage tracking
                key.last_used_at = datetime.now().isoformat()
                key.usage_count += 1
                self._save_keys()

                logger.debug(f"Key {key_id} validated successfully (scope: {key.scope})")
                return key_id

            logger.warning(
                f"Key {key_id} has insufficient scope "
                f"({key.scope} does not include {required_scope})"
            )
            return None

        logger.warning("No matching API key found")
        return None

    def get_key_by_token(self, api_key: str) -> APIKey | None:
        """
        Get API key object by token (without project validation).

        This method looks up an API key by its raw token value and returns
        the APIKey object if found. Unlike validate_key(), it does not
        validate against a specific project or scope.

        Args:
            api_key: The raw API key token (e.g., "cmp_xxx...")

        Returns:
            Optional[APIKey]: The APIKey object if found, None otherwise
        """
        key_hash = self._hash_key(api_key)

        for key_id, key in self.keys.items():
            if key.key_hash == key_hash:
                logger.debug(f"Found API key {key_id} by token")
                return key

        logger.debug("No API key found for provided token")
        return None

    def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an API key.

        Args:
            key_id: Key ID to revoke

        Returns:
            bool: True if revoked successfully
        """
        if key_id not in self.keys:
            logger.warning(f"Key {key_id} not found")
            return False

        self.keys[key_id].revoked = True
        self._save_keys()

        logger.info(f"Revoked API key {key_id}")
        return True

    def delete_key(self, key_id: str) -> bool:
        """
        Permanently delete an API key.

        Args:
            key_id: Key ID to delete

        Returns:
            bool: True if deleted successfully
        """
        if key_id not in self.keys:
            logger.warning(f"Key {key_id} not found")
            return False

        del self.keys[key_id]
        self._save_keys()

        logger.info(f"Deleted API key {key_id}")
        return True

    def list_keys(self, project_id: str | None = None, include_revoked: bool = False) -> list[dict]:
        """
        List API keys.

        Args:
            project_id: Optional filter by project
            include_revoked: Include revoked keys

        Returns:
            List of key information (without actual keys)
        """
        keys = []

        for key_id, key in self.keys.items():
            # Filter by project
            if project_id and key.project_id != project_id and key.project_id != "*":
                continue

            # Filter revoked
            if not include_revoked and key.revoked:
                continue

            keys.append(
                {
                    "key_id": key_id,
                    "project_id": key.project_id,
                    "scope": key.scope,
                    "created_at": key.created_at,
                    "expires_at": key.expires_at,
                    "last_used_at": key.last_used_at,
                    "usage_count": key.usage_count,
                    "description": key.description,
                    "revoked": key.revoked,
                    "expired": key.is_expired(),
                    "valid": key.is_valid(),
                }
            )

        return keys

    def rotate_keys(self, project_id: str) -> list[dict[str, str]]:
        """
        Rotate all keys for a project.

        Creates new keys with same scopes and revokes old ones.

        Args:
            project_id: Project to rotate keys for

        Returns:
            List of new key information
        """
        old_keys = [
            key for key in self.keys.values() if key.project_id == project_id and key.is_valid()
        ]

        new_keys = []

        for old_key in old_keys:
            # Create new key with same scope
            new_key_data = self.create_key(
                project_id=project_id,
                scope=old_key.scope,
                description=f"Rotated from {old_key.key_id}",
            )
            new_keys.append(new_key_data)

            # Revoke old key
            self.revoke_key(old_key.key_id)

        logger.info(f"Rotated {len(new_keys)} keys for project {project_id}")
        return new_keys

    def get_key_info(self, key_id: str) -> dict | None:
        """
        Get information about a specific key.

        Args:
            key_id: Key ID

        Returns:
            Key information or None
        """
        if key_id not in self.keys:
            return None

        key = self.keys[key_id]
        return {
            "key_id": key_id,
            "project_id": key.project_id,
            "scope": key.scope,
            "created_at": key.created_at,
            "expires_at": key.expires_at,
            "last_used_at": key.last_used_at,
            "usage_count": key.usage_count,
            "description": key.description,
            "revoked": key.revoked,
            "expired": key.is_expired(),
            "valid": key.is_valid(),
        }

# Global instance
_api_key_manager: APIKeyManager | None = None

def get_api_key_manager() -> APIKeyManager:
    """Get the global API Key Manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        storage_path = os.getenv("API_KEYS_STORAGE", "data/api_keys.json")
        _api_key_manager = APIKeyManager(storage_path)
    return _api_key_manager
