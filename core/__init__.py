"""
Core modules for MCP server

Architecture:
- Multi-Endpoint: Separate MCP endpoints for different plugin types
- Tool Registry: Central tool management
- Site Manager: Multi-site configuration
- Middleware: Authentication, rate limiting, audit logging
"""

# Authentication and API Keys
from core.api_keys import APIKeyManager, get_api_key_manager

# Logging and Audit
from core.audit_log import AuditLogger, EventType, LogLevel, get_audit_logger
from core.auth import AuthManager, get_auth_manager

# Context Management
from core.context import clear_api_key_context, get_api_key_context, set_api_key_context

# Multi-Endpoint Architecture (Phase X)
from core.endpoints import (
    EndpointConfig,
    EndpointRegistry,
    EndpointType,
    MCPEndpointFactory,
)

# Health Monitoring
from core.health import (
    AlertThreshold,
    HealthMetric,
    HealthMonitor,
    ProjectHealthStatus,
    SystemMetrics,
    get_health_monitor,
    initialize_health_monitor,
)

# Rate Limiting
from core.rate_limiter import RateLimitConfig, RateLimiter, get_rate_limiter
from core.site_manager import SiteConfig, SiteManager, get_site_manager
from core.tool_generator import ToolGenerator

# Tool Management (Option B architecture)
from core.tool_registry import ToolDefinition, ToolRegistry, get_tool_registry

__all__ = [
    # Authentication
    "AuthManager",
    "get_auth_manager",
    "APIKeyManager",
    "get_api_key_manager",
    # Site Management
    "SiteManager",
    "SiteConfig",
    "get_site_manager",
    # Tool Management
    "ToolRegistry",
    "ToolDefinition",
    "get_tool_registry",
    "ToolGenerator",
    # Multi-Endpoint Architecture
    "EndpointConfig",
    "EndpointType",
    "MCPEndpointFactory",
    "EndpointRegistry",
    # Logging
    "AuditLogger",
    "get_audit_logger",
    "LogLevel",
    "EventType",
    # Context
    "set_api_key_context",
    "get_api_key_context",
    "clear_api_key_context",
    # Health
    "HealthMonitor",
    "HealthMetric",
    "SystemMetrics",
    "ProjectHealthStatus",
    "AlertThreshold",
    "get_health_monitor",
    "initialize_health_monitor",
    # Rate Limiting
    "RateLimiter",
    "get_rate_limiter",
    "RateLimitConfig",
]
