"""
Gitea Plugin - Clean Architecture

Complete Gitea management through REST API with OAuth support.
Modular handlers for better organization and maintainability.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.gitea import handlers
from plugins.gitea.client import GiteaClient


class GiteaPlugin(BasePlugin):
    """
    Gitea project plugin - Clean architecture.

    Provides comprehensive Gitea management capabilities including:
    - Repository management (CRUD, branches, tags, files)
    - Issue tracking (issues, labels, milestones, comments)
    - Pull requests (PRs, reviews, merges)
    - User and organization management
    - Webhook configuration
    - OAuth integration
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "gitea"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url"]  # Token is optional (can use OAuth)

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize Gitea plugin with handlers.

        Args:
            config: Configuration dictionary containing:
                - url: Gitea instance URL
                - token: (Optional) Personal access token
                - oauth_enabled: (Optional) Whether OAuth is enabled
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create Gitea API client
        self.client = GiteaClient(
            site_url=config["url"],
            token=config.get("token"),
            oauth_enabled=config.get("oauth_enabled", False),
        )

        # No handler instances needed in Option B architecture
        # Tools are delegated directly to handler functions

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.

        Returns:
            List of tool specification dictionaries
        """
        specs = []

        # Collect specifications from all handlers
        specs.extend(handlers.repositories.get_tool_specifications())
        specs.extend(handlers.issues.get_tool_specifications())
        specs.extend(handlers.pull_requests.get_tool_specifications())
        specs.extend(handlers.users.get_tool_specifications())
        specs.extend(handlers.webhooks.get_tool_specifications())

        return specs

    def __getattr__(self, name: str):
        """
        Dynamically delegate method calls to appropriate handlers.

        This allows ToolGenerator to call methods like plugin.list_repositories()
        without explicitly defining each method.

        Args:
            name: Method name being called

        Returns:
            Handler function from the appropriate handler module
        """
        # Try to find the method in handlers modules
        try:
            # Check repositories handlers
            if hasattr(handlers.repositories, name):
                func = getattr(handlers.repositories, name)

                # Create wrapper that passes self.client
                async def wrapper(**kwargs):
                    return await func(self.client, **kwargs)

                return wrapper

            # Check issues handlers
            if hasattr(handlers.issues, name):
                func = getattr(handlers.issues, name)

                async def wrapper(**kwargs):
                    return await func(self.client, **kwargs)

                return wrapper

            # Check pull_requests handlers
            if hasattr(handlers.pull_requests, name):
                func = getattr(handlers.pull_requests, name)

                async def wrapper(**kwargs):
                    return await func(self.client, **kwargs)

                return wrapper

            # Check users handlers
            if hasattr(handlers.users, name):
                func = getattr(handlers.users, name)

                async def wrapper(**kwargs):
                    return await func(self.client, **kwargs)

                return wrapper

            # Check webhooks handlers
            if hasattr(handlers.webhooks, name):
                func = getattr(handlers.webhooks, name)

                async def wrapper(**kwargs):
                    return await func(self.client, **kwargs)

                return wrapper

            # Method not found in any handler
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        except AttributeError:
            raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check if Gitea instance is accessible.

        Returns:
            Dict containing health check result
        """
        try:
            # Try to get user information (requires authentication)
            await self.client.request("GET", "user")
            return {"healthy": True, "message": "Gitea instance is accessible"}
        except Exception as e:
            return {"healthy": False, "message": f"Gitea health check failed: {str(e)}"}
