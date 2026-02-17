"""
Supabase Plugin - Self-Hosted Database & Backend Management

Complete Supabase Self-Hosted management through Kong gateway APIs.
Provides tools for Database (PostgREST), Auth (GoTrue), Storage,
Edge Functions, and Admin (postgres-meta) operations.

For Self-Hosted instances deployed on Coolify.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.supabase import handlers
from plugins.supabase.client import SupabaseClient

class SupabasePlugin(BasePlugin):
    """
    Supabase Self-Hosted Plugin - Complete backend management.

    Provides comprehensive Supabase management capabilities including:
    - Database operations (PostgREST CRUD, RPC, count)
    - Admin operations (postgres-meta: schemas, tables, extensions, RLS)
    - Auth operations (GoTrue: users, MFA, invitations)
    - Storage operations (buckets, files, public URLs)
    - Edge Functions (invoke, deployment)
    - System operations (health, stats)

    Phase G.1: Database (18) + System (6) = 24 tools ✅
    Phase G.2: Auth (14) + Storage (12) = 26 tools ✅
    Phase G.3: Functions (8) + Admin (12) = 20 tools ✅

    Total: 70 tools - Complete!
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "supabase"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "anon_key", "service_role_key"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize Supabase plugin with client.

        Args:
            config: Configuration dictionary containing:
                - url: Supabase instance URL (Kong gateway)
                - anon_key: Anonymous key (RLS protected)
                - service_role_key: Service role key (bypasses RLS)
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create Supabase API client
        self.client = SupabaseClient(
            base_url=config["url"],
            anon_key=config["anon_key"],
            service_role_key=config["service_role_key"],
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

        # Phase G.1: Core (24 tools)
        specs.extend(handlers.database.get_tool_specifications())  # 18 tools
        specs.extend(handlers.system.get_tool_specifications())  # 6 tools

        # Phase G.2: Auth & Storage (26 tools)
        specs.extend(handlers.auth.get_tool_specifications())  # 14 tools
        specs.extend(handlers.storage.get_tool_specifications())  # 12 tools

        # Phase G.3: Functions & Admin (20 tools)
        specs.extend(handlers.functions.get_tool_specifications())  # 8 tools
        specs.extend(handlers.admin.get_tool_specifications())  # 12 tools

        return specs

    def __getattr__(self, name: str):
        """
        Dynamically delegate method calls to appropriate handlers.

        This allows ToolGenerator to call methods like plugin.query_table()
        without explicitly defining each method.

        Args:
            name: Method name being called

        Returns:
            Handler function from the appropriate handler module
        """
        # Try to find the method in handler modules
        handler_modules = [
            handlers.database,
            handlers.system,
            # Phase G.2
            handlers.auth,
            handlers.storage,
            # Phase G.3
            handlers.functions,
            handlers.admin,
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
        Check if Supabase instance is accessible (internal use).

        Note: This is named check_health to avoid shadowing the handler's
        health_check function which is exposed as an MCP tool.

        Returns:
            Dict containing health check result
        """
        try:
            result = await self.client.health_check()
            return {
                "healthy": result.get("healthy", False),
                "message": f"Supabase instance at {self.client.base_url} is {'accessible' if result.get('healthy') else 'not accessible'}",
            }
        except Exception as e:
            return {"healthy": False, "message": f"Supabase health check failed: {str(e)}"}

    async def health_check(self, **kwargs) -> str:
        """
        Override BasePlugin.health_check to use handler function.

        This ensures the MCP tool returns a JSON string, not a Dict.
        """
        return await handlers.system.health_check(self.client)
