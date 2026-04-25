"""
n8n Plugin - Workflow Automation Management

Complete n8n workflow automation management through REST API.
Provides 56 tools across 8 categories: workflows, executions,
credentials, tags, users, projects, variables, and system.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.n8n import handlers
from plugins.n8n.client import N8nClient


class N8nPlugin(BasePlugin):
    """
    n8n Automation Plugin - Comprehensive workflow management.

    Provides complete n8n management capabilities including:
    - Workflow management (CRUD, activate, deactivate, execute, transfer)
    - Execution monitoring (list, get, delete, retry, wait, project filter)
    - Credential management (get, create, delete, schema, transfer)
    - Tag management (CRUD, bulk delete)
    - User management (CRUD, roles)
    - Project management (CRUD, user assignment) - Enterprise/Pro
    - Variable management (CRUD, bulk set) - Enterprise/Pro
    - System operations (audit, source control, health)

    Total: 57 tools
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "n8n"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "api_key"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize n8n plugin with client.

        Args:
            config: Configuration dictionary containing:
                - url: n8n instance URL
                - api_key: n8n API key
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create n8n API client
        self.client = N8nClient(site_url=config["url"], api_key=config["api_key"])

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.

        Returns:
            List of tool specification dictionaries (56 tools total)
        """
        specs = []

        # Collect specifications from all handlers
        specs.extend(handlers.workflows.get_tool_specifications())  # 15 tools
        specs.extend(handlers.executions.get_tool_specifications())  # 8 tools
        specs.extend(handlers.credentials.get_tool_specifications())  # 5 tools
        specs.extend(handlers.tags.get_tool_specifications())  # 6 tools
        specs.extend(handlers.users.get_tool_specifications())  # 5 tools
        specs.extend(handlers.projects.get_tool_specifications())  # 8 tools [Enterprise]
        specs.extend(handlers.variables.get_tool_specifications())  # 6 tools [Enterprise]
        specs.extend(handlers.system.get_tool_specifications())  # 4 tools

        return specs

    def __getattr__(self, name: str):
        """
        Dynamically delegate method calls to appropriate handlers.

        This allows ToolGenerator to call methods like plugin.list_workflows()
        without explicitly defining each method.

        Args:
            name: Method name being called

        Returns:
            Handler function from the appropriate handler module
        """
        # Try to find the method in handler modules
        handler_modules = [
            handlers.workflows,
            handlers.executions,
            handlers.credentials,
            handlers.tags,
            handlers.users,
            handlers.projects,
            handlers.variables,
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

    async def probe_credential_capabilities(self) -> dict[str, Any]:
        """F.7e — probe the n8n API key's effective permissions.

        Calls ``GET /api/v1/user`` which returns the current user's
        ``globalRole`` (and ``globalScopes`` on enterprise). If the key
        is invalid or the endpoint is unreachable we return a graceful
        fallback so the dashboard can still render a status badge.
        """
        from plugins.n8n.client import N8nAuthError, N8nConnectionError

        try:
            user = await self.client.get_current_user()
        except N8nAuthError as exc:
            return {
                "probe_available": False,
                "granted": [],
                "source": "n8n_api",
                "reason": f"auth_failed: {exc}",
            }
        except (N8nConnectionError, Exception) as exc:  # noqa: BLE001
            return {
                "probe_available": False,
                "granted": [],
                "source": "n8n_api",
                "reason": f"probe_failed: {exc}",
            }

        role_name = ""
        role_obj = user.get("role") or user.get("globalRole") or ""
        if isinstance(role_obj, dict):
            role_name = role_obj.get("name", "")
        elif isinstance(role_obj, str):
            role_name = role_obj
        scopes = user.get("globalScopes") or []

        return {
            "probe_available": True,
            "granted": sorted(scopes) if scopes else [role_name],
            "source": "n8n_api",
            "role": role_name,
            "email": user.get("email", ""),
        }

    async def check_health(self) -> dict[str, Any]:
        """Check if n8n instance is accessible (internal use)."""
        try:
            result = await self.client.health_check()
            return {
                "healthy": result.get("healthy", False),
                "message": (
                    f"n8n instance at {self.client.site_url} is "
                    f"{'accessible' if result.get('healthy') else 'not accessible'}"
                ),
            }
        except Exception as e:
            return {"healthy": False, "message": f"n8n health check failed: {e}"}

    async def health_check(self, **kwargs) -> str:
        """
        Override BasePlugin.health_check to use handler function.

        This ensures the MCP tool returns a JSON string, not a Dict.
        """
        return await handlers.system.health_check(self.client)
