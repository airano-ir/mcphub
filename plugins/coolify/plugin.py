"""
Coolify Plugin — Clean Architecture

AI-driven deployment management for Coolify instances.
Modular handlers for applications, deployments, and servers.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.coolify import handlers
from plugins.coolify.client import CoolifyClient


class CoolifyPlugin(BasePlugin):
    """
    Coolify project plugin — Clean architecture.

    Provides Coolify deployment management capabilities including:
    - Application management (CRUD, lifecycle, env vars, logs)
    - Deployment control (list, cancel, deploy by tag/UUID)
    - Server management (CRUD, resources, domains, validation)
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier."""
        return "coolify"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys."""
        return ["url", "token"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize Coolify plugin with handlers.

        Args:
            config: Configuration dictionary containing:
                - url: Coolify instance URL
                - token: API token for Bearer authentication
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        self.client = CoolifyClient(
            site_url=config["url"],
            token=config["token"],
        )

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        Returns:
            List of tool specification dictionaries
        """
        specs = []

        specs.extend(handlers.applications.get_tool_specifications())
        specs.extend(handlers.deployments.get_tool_specifications())
        specs.extend(handlers.servers.get_tool_specifications())

        return specs

    def __getattr__(self, name: str):
        """
        Dynamically delegate method calls to appropriate handlers.

        Args:
            name: Method name being called

        Returns:
            Handler function from the appropriate handler module
        """
        handler_modules = [
            handlers.applications,
            handlers.deployments,
            handlers.servers,
        ]

        for module in handler_modules:
            if hasattr(module, name):
                func = getattr(module, name)

                async def wrapper(_func=func, **kwargs):
                    return await _func(self.client, **kwargs)

                return wrapper

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def health_check(self) -> dict[str, Any]:
        """
        Check if Coolify instance is accessible.

        Returns:
            Dict containing health check result
        """
        try:
            await self.client.request("GET", "version")
            return {"healthy": True, "message": "Coolify instance is accessible"}
        except Exception as e:
            return {"healthy": False, "message": f"Coolify health check failed: {str(e)}"}
