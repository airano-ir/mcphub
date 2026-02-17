"""
Appwrite Plugin - Self-Hosted Backend-as-a-Service Management

Complete Appwrite Self-Hosted management through REST APIs.
Provides tools for Databases, Documents, Users, Teams, Storage,
Functions, Messaging, and System operations.

For Self-Hosted instances deployed on Coolify.
"""

from typing import Any

from plugins.appwrite import handlers
from plugins.appwrite.client import AppwriteClient
from plugins.base import BasePlugin


class AppwritePlugin(BasePlugin):
    """
    Appwrite Self-Hosted Plugin - Complete backend management.

    Provides comprehensive Appwrite management capabilities including:
    - Database operations (Databases, Collections, Attributes, Indexes)
    - Document operations (CRUD, Bulk ops, Queries, Search)
    - User management (CRUD, Labels, Sessions, Status)
    - Team management (Teams, Memberships, Roles)
    - Storage operations (Buckets, Files, Image transformation)
    - Functions (Functions, Deployments, Executions)
    - Messaging (Topics, Subscribers, Email/SMS/Push messages)
    - System operations (Health checks, Avatars)

    Phase I.1: Database (18) + Documents (12) + System (8) = 38 tools
    Phase I.2: Users (12) + Teams (10) = 22 tools
    Phase I.3: Storage (14) = 14 tools
    Phase I.4: Functions (14) + Messaging (12) = 26 tools

    Total: 100 tools - Complete!
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "appwrite"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "project_id", "api_key"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize Appwrite plugin with client.

        Args:
            config: Configuration dictionary containing:
                - url: Appwrite instance URL (e.g., https://appwrite.example.com/v1)
                - project_id: Appwrite project ID
                - api_key: API key with appropriate scopes
            project_id: Optional MCP project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create Appwrite API client
        self.client = AppwriteClient(
            base_url=config["url"], project_id=config["project_id"], api_key=config["api_key"]
        )

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

        # Phase I.1: Core (38 tools)
        specs.extend(handlers.databases.get_tool_specifications())  # 18 tools
        specs.extend(handlers.documents.get_tool_specifications())  # 12 tools
        specs.extend(handlers.system.get_tool_specifications())  # 8 tools

        # Phase I.2: Auth & Teams (22 tools)
        specs.extend(handlers.users.get_tool_specifications())  # 12 tools
        specs.extend(handlers.teams.get_tool_specifications())  # 10 tools

        # Phase I.3: Storage (14 tools)
        specs.extend(handlers.storage.get_tool_specifications())  # 14 tools

        # Phase I.4: Functions & Messaging (26 tools)
        specs.extend(handlers.functions.get_tool_specifications())  # 14 tools
        specs.extend(handlers.messaging.get_tool_specifications())  # 12 tools

        return specs

    def __getattr__(self, name: str):
        """
        Dynamically delegate method calls to appropriate handlers.

        This allows ToolGenerator to call methods like plugin.list_databases()
        without explicitly defining each method.

        Args:
            name: Method name being called

        Returns:
            Handler function from the appropriate handler module
        """
        # Try to find the method in handler modules
        handler_modules = [
            # Phase I.1: Core
            handlers.databases,
            handlers.documents,
            handlers.system,
            # Phase I.2: Auth & Teams
            handlers.users,
            handlers.teams,
            # Phase I.3: Storage
            handlers.storage,
            # Phase I.4: Functions & Messaging
            handlers.functions,
            handlers.messaging,
        ]

        for handler_module in handler_modules:
            if hasattr(handler_module, name):
                func = getattr(handler_module, name)

                # Create wrapper that passes self.client
                async def wrapper(_func=func, **kwargs):
                    return await _func(self.client, **kwargs)

                return wrapper

        # Method not found in any handler
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def check_health(self) -> dict[str, Any]:
        """
        Check if Appwrite instance is accessible (internal use).

        Note: This is named check_health to avoid shadowing the handler's
        health_check function which is exposed as an MCP tool.

        Returns:
            Dict containing health check result
        """
        try:
            result = await self.client.health_check()
            is_healthy = result.get("status") == "pass"
            return {
                "healthy": is_healthy,
                "message": f"Appwrite instance at {self.client.base_url} is {'accessible' if is_healthy else 'not accessible'}",
            }
        except Exception as e:
            return {"healthy": False, "message": f"Appwrite health check failed: {str(e)}"}

    async def health_check(self, **kwargs) -> str:
        """
        Override BasePlugin.health_check to use handler function.

        This ensures the MCP tool returns a JSON string, not a Dict.
        """
        return await handlers.system.health_check(self.client)
