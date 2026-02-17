"""
Multi-Endpoint Architecture for MCP Hub

This module provides a factory pattern for creating scoped MCP endpoints.
Each endpoint exposes only the tools relevant to its purpose.

Endpoints:
    /mcp              - Admin endpoint (all tools, requires Master API Key)
    /mcp/wordpress    - WordPress tools only (92 tools)
    /mcp/wordpress-advanced - WordPress Advanced tools (22 tools)
    /mcp/gitea        - Gitea tools only (55 tools)
    /mcp/project/{id} - Project-specific tools

Benefits:
    - Better security: Users only see tools they can access
    - Optimized context: Smaller tool lists for AI assistants
    - Scalability: Easy to add new plugin endpoints
    - Clear separation of concerns
"""

from .config import (
    ENDPOINT_CONFIGS,
    EndpointConfig,
    EndpointType,
    create_project_endpoint_config,
    get_endpoint_config,
)
from .factory import MCPEndpointFactory
from .middleware import (
    AuthContext,
    EndpointAuditMiddleware,
    EndpointAuthMiddleware,
    EndpointRateLimitMiddleware,
    create_endpoint_middleware,
)
from .registry import (
    EndpointInfo,
    EndpointRegistry,
    get_endpoint_registry,
    initialize_endpoint_registry,
)

__all__ = [
    # Config
    "EndpointConfig",
    "EndpointType",
    "ENDPOINT_CONFIGS",
    "get_endpoint_config",
    "create_project_endpoint_config",
    # Factory
    "MCPEndpointFactory",
    # Registry
    "EndpointRegistry",
    "EndpointInfo",
    "get_endpoint_registry",
    "initialize_endpoint_registry",
    # Middleware
    "EndpointAuthMiddleware",
    "EndpointRateLimitMiddleware",
    "EndpointAuditMiddleware",
    "create_endpoint_middleware",
    "AuthContext",
]
