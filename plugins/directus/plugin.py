"""
Directus Plugin - Self-Hosted Headless CMS Management

Complete Directus Self-Hosted management through REST APIs.
Provides tools for Items, Collections, Fields, Files, Users,
Roles, Permissions, Flows, Versions, Dashboards, and System.

For Self-Hosted instances deployed on Coolify.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.directus import handlers
from plugins.directus.client import DirectusClient

class DirectusPlugin(BasePlugin):
    """
    Directus Self-Hosted Plugin - Complete CMS management.

    Provides comprehensive Directus management capabilities including:
    - Items operations (CRUD for any collection)
    - Collections & Fields (schema management)
    - Files & Folders (asset management)
    - Users management (CRUD, invite)
    - Access Control (Roles, Permissions, Policies)
    - Automation (Flows, Operations, Webhooks)
    - Content Management (Revisions, Versions, Comments)
    - Dashboards (Dashboards, Panels)
    - System operations (Settings, Server, Schema, Activity)

    Phase J.1: Items (12) + Collections (14) = 26 tools
    Phase J.2: Files (12) + Users (10) = 22 tools
    Phase J.3: Access (12) + Automation (12) = 24 tools
    Phase J.4: Content (10) + Dashboards (8) + System (10) = 28 tools

    Total: 100 tools - Complete!
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "directus"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "token"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize Directus plugin with client.

        Args:
            config: Configuration dictionary containing:
                - url: Directus instance URL (e.g., https://directus.example.com)
                - token: Static admin token
            project_id: Optional MCP project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create Directus API client
        self.client = DirectusClient(base_url=config["url"], token=config["token"])

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

        # Phase J.1: Core (26 tools)
        specs.extend(handlers.items.get_tool_specifications())  # 12 tools
        specs.extend(handlers.collections.get_tool_specifications())  # 14 tools

        # Phase J.2: Assets & Users (22 tools)
        specs.extend(handlers.files.get_tool_specifications())  # 12 tools
        specs.extend(handlers.users.get_tool_specifications())  # 10 tools

        # Phase J.3: Access & Automation (24 tools)
        specs.extend(handlers.access.get_tool_specifications())  # 12 tools
        specs.extend(handlers.automation.get_tool_specifications())  # 12 tools

        # Phase J.4: Advanced (28 tools)
        specs.extend(handlers.content.get_tool_specifications())  # 10 tools
        specs.extend(handlers.dashboards.get_tool_specifications())  # 8 tools
        specs.extend(handlers.system.get_tool_specifications())  # 10 tools

        return specs

    def __getattr__(self, name: str):
        """
        Dynamically delegate method calls to appropriate handlers.

        This allows ToolGenerator to call methods like plugin.list_items()
        without explicitly defining each method.

        Args:
            name: Method name being called

        Returns:
            Handler function from the appropriate handler module
        """
        # Try to find the method in handler modules
        handler_modules = [
            # Phase J.1: Core
            handlers.items,
            handlers.collections,
            # Phase J.2: Assets & Users
            handlers.files,
            handlers.users,
            # Phase J.3: Access & Automation
            handlers.access,
            handlers.automation,
            # Phase J.4: Advanced
            handlers.content,
            handlers.dashboards,
            handlers.system,
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
        Check if Directus instance is accessible (internal use).

        Note: This is named check_health to avoid shadowing the handler's
        health_check function which is exposed as an MCP tool.

        Returns:
            Dict containing health check result
        """
        try:
            result = await self.client.health_check()
            is_healthy = result.get("status") == "ok"
            return {
                "healthy": is_healthy,
                "message": f"Directus instance at {self.client.base_url} is {'accessible' if is_healthy else 'not accessible'}",
            }
        except Exception as e:
            return {"healthy": False, "message": f"Directus health check failed: {str(e)}"}

    async def health_check(self, **kwargs) -> str:
        """
        Override BasePlugin.health_check to use handler function.

        This ensures the MCP tool returns a JSON string, not a Dict.
        """
        return await handlers.system.health_check(self.client)
