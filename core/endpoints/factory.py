"""
MCP Endpoint Factory

Creates and configures FastMCP instances for different endpoints.
Each endpoint has its own set of tools based on configuration.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from .config import EndpointConfig

if TYPE_CHECKING:
    from core.site_manager import SiteManager
    from core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

class MCPEndpointFactory:
    """
    Factory for creating scoped MCP endpoints.

    Each endpoint is a separate FastMCP instance with only
    the tools relevant to its configuration.
    """

    def __init__(
        self,
        site_manager: "SiteManager",
        tool_registry: "ToolRegistry",
        middleware_classes: list[type] | None = None,
    ):
        """
        Initialize the endpoint factory.

        Args:
            site_manager: Site manager for accessing site configurations
            tool_registry: Central tool registry
            middleware_classes: List of middleware classes to apply to endpoints
        """
        self.site_manager = site_manager
        self.tool_registry = tool_registry
        self.middleware_classes = middleware_classes or []
        self.endpoints: dict[str, FastMCP] = {}
        self._tool_handlers: dict[str, Callable] = {}

    def register_tool_handler(self, tool_name: str, handler: Callable):
        """
        Register a tool handler function.

        Args:
            tool_name: Name of the tool
            handler: Async handler function for the tool
        """
        self._tool_handlers[tool_name] = handler

    def create_endpoint(
        self, config: EndpointConfig, custom_middleware: list[Middleware] | None = None
    ) -> FastMCP:
        """
        Create a new MCP endpoint with scoped tools.

        Args:
            config: Endpoint configuration
            custom_middleware: Additional middleware for this endpoint

        Returns:
            Configured FastMCP instance
        """
        logger.info(f"Creating endpoint: {config.path} ({config.name})")

        # Create FastMCP instance
        mcp = FastMCP(config.name)

        # Get tools for this endpoint
        tools = self._get_tools_for_endpoint(config)

        logger.info(f"  - Registering {len(tools)} tools for {config.path}")

        # Register tools
        for tool_info in tools:
            self._register_tool(mcp, tool_info, config)

        # Apply middleware
        if custom_middleware:
            for middleware in custom_middleware:
                mcp.add_middleware(middleware)

        # Store endpoint
        self.endpoints[config.path] = mcp

        logger.info(f"  - Endpoint {config.path} created successfully")

        return mcp

    def _get_tools_for_endpoint(self, config: EndpointConfig) -> list[dict[str, Any]]:
        """
        Get list of tools that should be available on this endpoint.

        Args:
            config: Endpoint configuration

        Returns:
            List of tool definitions
        """
        tools = []

        # Get all tools from registry
        all_tools = self.tool_registry.get_all()

        for tool_def in all_tools:
            tool_name = tool_def.name

            # Check plugin type filter
            plugin_type = self._extract_plugin_type(tool_name)
            if plugin_type and not config.allows_plugin(plugin_type):
                continue

            # Check tool whitelist/blacklist
            if not config.allows_tool(tool_name):
                continue

            # For project endpoints, filter by site
            if config.site_filter and plugin_type:
                # Tool should work with the specific site
                pass  # Site filtering happens at execution time

            tools.append(
                {
                    "name": tool_name,
                    "description": tool_def.description,
                    "parameters": tool_def.parameters,
                    "handler": tool_def.handler,
                    "plugin_type": plugin_type,
                }
            )

        # Check max tools limit
        if len(tools) > config.max_tools:
            logger.warning(
                f"Endpoint {config.path} has {len(tools)} tools, "
                f"exceeding max_tools={config.max_tools}"
            )

        return tools

    def _extract_plugin_type(self, tool_name: str) -> str | None:
        """
        Extract plugin type from tool name.

        Args:
            tool_name: Name of the tool

        Returns:
            Plugin type or None for system tools
        """
        # Check for wordpress_advanced first (before wordpress_)
        # Tools are named: wordpress_advanced_wp_db_*, wordpress_advanced_bulk_*, wordpress_advanced_system_*
        if tool_name.startswith("wordpress_advanced_"):
            return "wordpress_advanced"

        if tool_name.startswith("wordpress_"):
            return "wordpress"

        elif tool_name.startswith("woocommerce_"):
            return "woocommerce"

        elif tool_name.startswith("gitea_"):
            return "gitea"

        elif tool_name.startswith("n8n_"):
            return "n8n"

        elif tool_name.startswith("supabase_"):
            return "supabase"

        elif tool_name.startswith("openpanel_"):
            return "openpanel"

        elif tool_name.startswith("appwrite_"):
            return "appwrite"

        elif tool_name.startswith("directus_"):
            return "directus"

        # System tools have no plugin type
        return None

    def _register_tool(self, mcp: FastMCP, tool_info: dict[str, Any], config: EndpointConfig):
        """
        Register a single tool with the FastMCP instance.

        Args:
            mcp: FastMCP instance
            tool_info: Tool definition
            config: Endpoint configuration
        """
        tool_name = tool_info["name"]

        # Get handler
        handler = tool_info.get("handler") or self._tool_handlers.get(tool_name)

        if not handler:
            logger.warning(f"No handler found for tool: {tool_name}")
            return

        # Wrap handler with endpoint context
        wrapped_handler = self._wrap_handler(handler, tool_name, config)

        # Register with FastMCP
        # We need to create a function with the correct signature
        mcp.tool()(wrapped_handler)

    def _wrap_handler(self, handler: Callable, tool_name: str, config: EndpointConfig) -> Callable:
        """
        Wrap a tool handler with endpoint-specific logic.

        Args:
            handler: Original handler function
            tool_name: Name of the tool
            config: Endpoint configuration

        Returns:
            Wrapped handler function
        """

        @wraps(handler)
        async def wrapped(*args, **kwargs):
            # For project endpoints, always inject site filter
            # This locks all tools to the specific project's site
            if config.site_filter:
                # Extract site_id from project's site_filter (format: plugin_type_site_id)
                # The site parameter expects just the site identifier (site_id or alias)
                if "_" in config.site_filter:
                    # site_filter is full_id like "wordpress_site1"
                    parts = config.site_filter.split("_", 1)
                    if len(parts) == 2:
                        # Use the site_id part (site1)
                        kwargs["site"] = parts[1]
                    else:
                        kwargs["site"] = config.site_filter
                else:
                    kwargs["site"] = config.site_filter

            # Call original handler
            return await handler(*args, **kwargs)

        # Preserve function metadata
        wrapped.__name__ = tool_name
        wrapped.__doc__ = handler.__doc__

        return wrapped

    def get_endpoint(self, path: str) -> FastMCP | None:
        """
        Get an endpoint by path.

        Args:
            path: Endpoint path

        Returns:
            FastMCP instance or None
        """
        return self.endpoints.get(path)

    def get_all_endpoints(self) -> dict[str, FastMCP]:
        """Get all registered endpoints"""
        return self.endpoints.copy()

    def get_endpoint_info(self) -> list[dict[str, Any]]:
        """
        Get information about all endpoints.

        Returns:
            List of endpoint info dictionaries
        """
        info = []
        for path, mcp in self.endpoints.items():
            # Get tool count
            # Note: This requires accessing FastMCP internals
            tool_count = len(mcp._tool_manager._tools) if hasattr(mcp, "_tool_manager") else 0

            info.append(
                {
                    "path": path,
                    "name": mcp.name,
                    "tool_count": tool_count,
                }
            )
        return info
