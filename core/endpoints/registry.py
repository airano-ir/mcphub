"""
Endpoint Registry

Central registry for managing all MCP endpoints.
Handles routing requests to the correct endpoint based on path.
"""

import logging
from dataclasses import dataclass

from fastmcp import FastMCP
from starlette.routing import Mount, Route

from .config import (
    ENDPOINT_CONFIGS,
    EndpointConfig,
    EndpointType,
    create_project_endpoint_config,
)
from .factory import MCPEndpointFactory

logger = logging.getLogger(__name__)


@dataclass
class EndpointInfo:
    """Information about a registered endpoint"""

    path: str
    name: str
    description: str
    endpoint_type: EndpointType
    tool_count: int
    plugin_types: list[str]
    require_master_key: bool


class EndpointRegistry:
    """
    Central registry for all MCP endpoints.

    Manages endpoint creation, routing, and discovery.
    """

    def __init__(self, factory: MCPEndpointFactory):
        """
        Initialize the endpoint registry.

        Args:
            factory: Endpoint factory for creating MCP instances
        """
        self.factory = factory
        self._endpoints: dict[str, FastMCP] = {}
        self._configs: dict[str, EndpointConfig] = {}
        self._initialized = False

    def initialize_default_endpoints(self):
        """
        Initialize the default set of endpoints.

        Creates admin, wordpress, wordpress-advanced, and gitea endpoints.
        """
        if self._initialized:
            logger.warning("Endpoints already initialized")
            return

        logger.info("=" * 60)
        logger.info("Initializing Multi-Endpoint Architecture")
        logger.info("=" * 60)

        # Create default endpoints
        for _endpoint_type, config in ENDPOINT_CONFIGS.items():
            try:
                mcp = self.factory.create_endpoint(config)
                self._endpoints[config.path] = mcp
                self._configs[config.path] = config
                logger.info(f"  ✓ {config.path}: {config.name}")
            except Exception as e:
                logger.error(f"  ✗ Failed to create {config.path}: {e}")

        self._initialized = True

        # Log summary
        self._log_summary()

    def create_project_endpoint(
        self, project_id: str, plugin_type: str, site_alias: str | None = None
    ) -> FastMCP:
        """
        Create a dynamic endpoint for a specific project.

        Args:
            project_id: Full project ID
            plugin_type: Plugin type
            site_alias: Optional site alias

        Returns:
            Created FastMCP instance
        """
        config = create_project_endpoint_config(project_id, plugin_type, site_alias)

        # Check if already exists
        if config.path in self._endpoints:
            logger.info(f"Endpoint {config.path} already exists")
            return self._endpoints[config.path]

        mcp = self.factory.create_endpoint(config)
        self._endpoints[config.path] = mcp
        self._configs[config.path] = config

        logger.info(f"Created project endpoint: {config.path}")
        return mcp

    def get_endpoint(self, path: str) -> FastMCP | None:
        """
        Get endpoint by path.

        Args:
            path: Endpoint path

        Returns:
            FastMCP instance or None
        """
        # Exact match
        if path in self._endpoints:
            return self._endpoints[path]

        # Try with trailing slash
        if not path.endswith("/"):
            return self._endpoints.get(path + "/")

        return None

    def get_config(self, path: str) -> EndpointConfig | None:
        """Get endpoint configuration by path"""
        return self._configs.get(path)

    def list_endpoints(self) -> list[EndpointInfo]:
        """
        List all registered endpoints with their info.

        Returns:
            List of EndpointInfo objects
        """
        endpoints = []

        for path, config in self._configs.items():
            mcp = self._endpoints.get(path)
            tool_count = 0

            if mcp:
                # Try to get tool count from FastMCP
                try:
                    tool_count = len(mcp._tool_manager._tools)
                except AttributeError:
                    pass

            endpoints.append(
                EndpointInfo(
                    path=path,
                    name=config.name,
                    description=config.description,
                    endpoint_type=config.endpoint_type,
                    tool_count=tool_count,
                    plugin_types=config.plugin_types,
                    require_master_key=config.require_master_key,
                )
            )

        return endpoints

    def get_routes(self) -> list[Route]:
        """
        Get Starlette routes for all endpoints.

        Returns:
            List of Route objects for mounting
        """
        routes = []

        for path, mcp in self._endpoints.items():
            # Each MCP endpoint needs to handle its own routing
            # FastMCP provides an ASGI app
            routes.append(Mount(path, app=mcp.sse_app(), name=f"mcp_{path.replace('/', '_')}"))

        return routes

    def _log_summary(self):
        """Log a summary of all endpoints"""
        logger.info("-" * 60)
        logger.info("Endpoint Summary:")
        logger.info("-" * 60)

        total_tools = 0
        for info in self.list_endpoints():
            total_tools += info.tool_count
            auth_note = " (Master Key required)" if info.require_master_key else ""
            logger.info(f"  {info.path}: {info.tool_count} tools{auth_note}")

        logger.info("-" * 60)
        logger.info(f"Total: {len(self._endpoints)} endpoints")
        logger.info("=" * 60)


# Singleton instance
_registry: EndpointRegistry | None = None


def get_endpoint_registry() -> EndpointRegistry:
    """Get the global endpoint registry instance"""
    global _registry
    if _registry is None:
        raise RuntimeError(
            "Endpoint registry not initialized. " "Call initialize_endpoint_registry() first."
        )
    return _registry


def initialize_endpoint_registry(factory: MCPEndpointFactory) -> EndpointRegistry:
    """
    Initialize the global endpoint registry.

    Args:
        factory: Endpoint factory to use

    Returns:
        Initialized EndpointRegistry
    """
    global _registry
    _registry = EndpointRegistry(factory)
    return _registry
