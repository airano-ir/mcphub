"""
OpenPanel Plugin - Product Analytics Management.

Self-hosted OpenPanel management through public REST APIs.
Provides event tracking, data export, analytics, and project/client management.

APIs used:
- Track API (/track) — Event ingestion (write mode)
- Export API (/export) — Raw data export (read mode)
- Insights API (/insights) — Analytics queries (read mode)
- Manage API (/manage) — Project & client CRUD (root mode)
- Health API (/healthcheck) — Instance health

For Self-Hosted instances deployed on Coolify or Docker.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.openpanel import handlers
from plugins.openpanel.client import OpenPanelClient


class OpenPanelPlugin(BasePlugin):
    """
    OpenPanel Analytics Plugin — 42 tools across 7 handlers.

    All tools use public REST APIs (no tRPC/session dependency).

    Events (11): track, identify, increment, decrement, group, assign_group, batch, revenue
    Export (10): events, charts, CSV, counts, top pages/referrers/geo/devices
    Reports (2): overview stats, realtime visitors
    Profiles (3): profile events, sessions, GDPR export
    Projects (5): list, get, create, update, delete
    Clients (5): list, get, create, update, delete
    System (6): health, instance info, usage stats, storage, connection test, rate limits
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "openpanel"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "client_id", "client_secret"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize OpenPanel plugin with client.

        Args:
            config: Configuration dictionary containing:
                - url: OpenPanel instance URL
                - client_id: Client ID for authentication
                - client_secret: Client Secret for authentication
                - project_id: OpenPanel project ID (for Export/Insights APIs)
                - organization_id: Organization/Workspace ID (optional)
            project_id: Optional MCP project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        openpanel_project_id = config.get("project_id")
        openpanel_organization_id = config.get("organization_id")

        self.client = OpenPanelClient(
            base_url=config["url"],
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            project_id=openpanel_project_id,
            organization_id=openpanel_organization_id,
        )

        self.openpanel_project_id = openpanel_project_id
        self.openpanel_organization_id = openpanel_organization_id

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator (42 tools).

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.
        """
        specs = []
        specs.extend(handlers.events.get_tool_specifications())  # 11 tools
        specs.extend(handlers.export.get_tool_specifications())  # 10 tools
        specs.extend(handlers.system.get_tool_specifications())  # 6 tools
        specs.extend(handlers.reports.get_tool_specifications())  # 2 tools
        specs.extend(handlers.profiles.get_tool_specifications())  # 3 tools
        specs.extend(handlers.projects.get_tool_specifications())  # 5 tools
        specs.extend(handlers.clients.get_tool_specifications())  # 5 tools
        return specs

    def __getattr__(self, name: str):
        """
        Dynamically delegate method calls to appropriate handlers.

        This allows ToolGenerator to call methods like plugin.track_event()
        without explicitly defining each method.

        Args:
            name: Method name being called

        Returns:
            Handler function from the appropriate handler module
        """
        # Try to find the method in handler modules
        handler_modules = [
            handlers.events,
            handlers.export,
            handlers.system,
            handlers.reports,
            handlers.profiles,
            handlers.projects,
            handlers.clients,
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
        Check if OpenPanel instance is accessible (internal use).

        Note: This is named check_health to avoid shadowing the handler's
        health_check function which is exposed as an MCP tool.

        Returns:
            Dict containing health check result
        """
        try:
            result = await self.client.health_check()
            return {
                "healthy": result.get("healthy", False),
                "message": f"OpenPanel instance at {self.client.base_url} is {'accessible' if result.get('healthy') else 'not accessible'}",
            }
        except Exception as e:
            return {"healthy": False, "message": f"OpenPanel health check failed: {str(e)}"}

    async def health_check(self, **kwargs) -> str:
        """
        Override BasePlugin.health_check to use handler function.

        This ensures the MCP tool returns a JSON string, not a Dict.
        """
        return await handlers.system.health_check(self.client)
