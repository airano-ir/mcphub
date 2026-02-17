"""
Authentication system

Simple API key based authentication for MCP server.
"""

import logging
import os
import secrets

logger = logging.getLogger(__name__)

class AuthManager:
    """
    Manage authentication for MCP server.

    Currently supports simple API key authentication.
    Future: Can extend to support per-project keys, JWT, etc.
    """

    def __init__(self):
        """Initialize authentication manager."""
        # Load master API key from environment
        self.master_api_key = os.getenv("MASTER_API_KEY")

        if not self.master_api_key:
            # Generate a random key if not provided (dev mode)
            self.master_api_key = secrets.token_urlsafe(32)
            logger.warning(
                "No MASTER_API_KEY environment variable found. "
                f"Generated temporary key: {self.master_api_key[:8]}***{self.master_api_key[-4:]} "
                "(set MASTER_API_KEY in .env for production use)"
            )

        # Project-specific keys (future feature)
        self.project_keys = {}

        logger.info("Authentication manager initialized")

    def validate_master_key(self, api_key: str) -> bool:
        """
        Validate master API key.

        Args:
            api_key: API key to validate

        Returns:
            bool: True if valid
        """
        is_valid = secrets.compare_digest(api_key, self.master_api_key)

        if not is_valid:
            logger.warning("Invalid API key attempt")

        return is_valid

    def validate_project_key(self, project_id: str, api_key: str) -> bool:
        """
        Validate project-specific API key.

        Args:
            project_id: Project identifier
            api_key: API key to validate

        Returns:
            bool: True if valid
        """
        if project_id not in self.project_keys:
            # No project-specific key, fall back to master key
            return self.validate_master_key(api_key)

        project_key = self.project_keys[project_id]
        is_valid = secrets.compare_digest(api_key, project_key)

        if not is_valid:
            logger.warning(f"Invalid project key for {project_id}")

        return is_valid

    def add_project_key(self, project_id: str, api_key: str | None = None) -> str:
        """
        Add or generate a project-specific API key.

        Args:
            project_id: Project identifier
            api_key: Optional pre-defined key, will generate if None

        Returns:
            str: The API key (useful if generated)
        """
        if api_key is None:
            api_key = secrets.token_urlsafe(32)

        self.project_keys[project_id] = api_key
        logger.info(f"Added API key for project: {project_id}")

        return api_key

    def remove_project_key(self, project_id: str) -> None:
        """
        Remove project-specific API key.

        Args:
            project_id: Project identifier
        """
        if project_id in self.project_keys:
            del self.project_keys[project_id]
            logger.info(f"Removed API key for project: {project_id}")

    def get_master_key(self) -> str:
        """Get the master API key (for display/setup purposes)."""
        return self.master_api_key

    def has_project_key(self, project_id: str) -> bool:
        """Check if a project has its own API key."""
        return project_id in self.project_keys

# Global authentication manager instance
_auth_manager: AuthManager | None = None

def get_auth_manager() -> AuthManager:
    """Get the global authentication manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
