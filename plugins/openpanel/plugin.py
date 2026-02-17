"""
OpenPanel Plugin - Product Analytics Management

Complete OpenPanel Self-Hosted management through REST API.
Provides tools for event tracking, data export, and analytics.

For Self-Hosted instances deployed on Coolify.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.openpanel import handlers
from plugins.openpanel.client import OpenPanelClient

class OpenPanelPlugin(BasePlugin):
    """
    OpenPanel Analytics Plugin - Comprehensive product analytics.

    Provides complete OpenPanel management capabilities including:
    - Event tracking (track, identify, increment, decrement)
    - Data export (events, charts, CSV)
    - Analytics reports (page views, referrers, geo, devices)
    - System operations (health, stats)

    Phase H.1: Core (25 tools)
    - Events Handler: 9 tools (alias_user removed - not supported on self-hosted)
    - Export Handler: 10 tools
    - System Handler: 6 tools

    Phase H.2: Analytics (24 tools)
    - Reports Handler: 8 tools
    - Funnels Handler: 8 tools
    - Profiles Handler: 8 tools

    Phase H.3: Management (24 tools)
    - Projects Handler: 8 tools
    - Dashboards Handler: 10 tools
    - Clients Handler: 6 tools

    Total: 73 tools
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
                - project_id: OpenPanel project ID (for Export/Read APIs)
                - organization_id: Organization/Workspace ID (for multi-tenant setups)
            project_id: Optional MCP project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Get OpenPanel project_id and organization_id from config
        openpanel_project_id = config.get("project_id")
        openpanel_organization_id = config.get("organization_id")

        # Get session cookie for tRPC API access (optional)
        # This is needed for analytics queries as tRPC uses session-based auth
        session_cookie = config.get("session_cookie")

        # Create OpenPanel API client
        self.client = OpenPanelClient(
            base_url=config["url"],
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            project_id=openpanel_project_id,
            organization_id=openpanel_organization_id,
            session_cookie=session_cookie,
        )

        # Store for reference
        self.openpanel_project_id = openpanel_project_id
        self.openpanel_organization_id = openpanel_organization_id
        self.has_session = bool(session_cookie)

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.

        Returns:
            List of tool specification dictionaries (26 tools in Phase H.1)
        """
        specs = []

        # Phase H.1: Core (26 tools)
        specs.extend(handlers.events.get_tool_specifications())  # 10 tools
        specs.extend(handlers.export.get_tool_specifications())  # 10 tools
        specs.extend(handlers.system.get_tool_specifications())  # 6 tools

        # Phase H.2: Analytics (24 tools)
        specs.extend(handlers.reports.get_tool_specifications())  # 8 tools
        specs.extend(handlers.funnels.get_tool_specifications())  # 8 tools
        specs.extend(handlers.profiles.get_tool_specifications())  # 8 tools

        # Phase H.3: Management (24 tools)
        specs.extend(handlers.projects.get_tool_specifications())  # 8 tools
        specs.extend(handlers.dashboards.get_tool_specifications())  # 10 tools
        specs.extend(handlers.clients.get_tool_specifications())  # 6 tools

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
            handlers.funnels,
            handlers.profiles,
            handlers.projects,
            handlers.dashboards,
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
