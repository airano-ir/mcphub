#!/usr/bin/env python3
"""
MCP Hub - Multi-Endpoint Server v2.1.0

Multi-Endpoint Architecture (Phase X + D.1):
- /mcp                    → Admin endpoint (all tools, Master API Key required)
- /wordpress/mcp          → WordPress Core tools (64 tools)
- /woocommerce/mcp        → WooCommerce tools (28 tools) ← NEW Phase D.1
- /wordpress-advanced/mcp → WordPress Advanced tools (22 tools)
- /gitea/mcp              → Gitea tools only (55 tools)
- /project/{id}/mcp       → Project-specific tools

Note: FastMCP automatically adds /mcp to the mount path.

Benefits:
- Users only see tools they can access
- Better security and access control
- Optimized context for AI assistants
- Scalable architecture

Usage:
    python server_multi.py --transport sse --port 8000
"""

import inspect
import logging
import os
import sys
import time
from collections.abc import Callable
from typing import Optional

import uvicorn
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from starlette.applications import Starlette
from starlette.middleware import Middleware as StarletteMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.templating import Jinja2Templates

# Import core modules
from core import (
    ToolDefinition,
    ToolGenerator,
    clear_api_key_context,
    get_api_key_manager,
    get_audit_logger,
    get_auth_manager,
    get_project_manager,
    get_rate_limiter,
    get_site_manager,
    get_tool_registry,
    set_api_key_context,
)

# Import endpoint configuration
from core.endpoints import (
    ENDPOINT_CONFIGS,
    EndpointConfig,
    EndpointType,
    create_project_endpoint_config,
)
from core.i18n import detect_language, get_all_translations

# OAuth
from core.oauth import OAuthError, get_csrf_manager, get_oauth_server
from plugins import registry as plugin_registry

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# OAuth Configuration
OAUTH_AUTH_MODE = os.getenv("OAUTH_AUTH_MODE", "required").lower()

# ========================================
# DCR (Dynamic Client Registration) Configuration
# ========================================
# Allowlist of redirect_uri patterns for open DCR (without Master API Key)
import re

DCR_ALLOWED_REDIRECT_PATTERNS = [
    # Claude AI
    r"^https://claude\.ai/.*",
    r"^https://claude\.com/.*",
    # ChatGPT / OpenAI
    r"^https://chatgpt\.com/.*",
    r"^https://chat\.openai\.com/.*",
    r"^https://platform\.openai\.com/.*",
    # Localhost for development
    r"^http://localhost:\d+/.*",
    r"^http://127\.0\.0\.1:\d+/.*",
]

# Load additional patterns from environment
DCR_EXTRA_PATTERNS = os.getenv("DCR_ALLOWED_REDIRECT_PATTERNS", "")
if DCR_EXTRA_PATTERNS:
    for pattern in DCR_EXTRA_PATTERNS.split(","):
        pattern = pattern.strip()
        if pattern:
            DCR_ALLOWED_REDIRECT_PATTERNS.append(pattern)

# DCR Rate Limiting
DCR_RATE_LIMIT_PER_MINUTE = int(os.getenv("DCR_RATE_LIMIT_PER_MINUTE", "10"))
DCR_RATE_LIMIT_PER_HOUR = int(os.getenv("DCR_RATE_LIMIT_PER_HOUR", "30"))
_dcr_rate_limits: dict = {}

def is_redirect_uri_allowed_for_open_dcr(redirect_uris: list) -> bool:
    """Check if all redirect_uris match the allowlist patterns."""
    for uri in redirect_uris:
        uri_allowed = False
        for pattern in DCR_ALLOWED_REDIRECT_PATTERNS:
            if re.match(pattern, uri):
                uri_allowed = True
                break
        if not uri_allowed:
            return False
    return True

def check_dcr_rate_limit(client_ip: str) -> tuple:
    """Check if DCR request is within rate limits."""
    now = time.time()
    if client_ip not in _dcr_rate_limits:
        _dcr_rate_limits[client_ip] = {
            "minute": 0,
            "hour": 0,
            "minute_reset": now + 60,
            "hour_reset": now + 3600,
        }
    limits = _dcr_rate_limits[client_ip]
    if now > limits["minute_reset"]:
        limits["minute"] = 0
        limits["minute_reset"] = now + 60
    if now > limits["hour_reset"]:
        limits["hour"] = 0
        limits["hour_reset"] = now + 3600
    if limits["minute"] >= DCR_RATE_LIMIT_PER_MINUTE:
        return False, f"Rate limit: {DCR_RATE_LIMIT_PER_MINUTE}/min"
    if limits["hour"] >= DCR_RATE_LIMIT_PER_HOUR:
        return False, f"Rate limit: {DCR_RATE_LIMIT_PER_HOUR}/hour"
    limits["minute"] += 1
    limits["hour"] += 1
    return True, ""

# Initialize managers
auth_manager = get_auth_manager()
api_key_manager = get_api_key_manager()
project_manager = get_project_manager()
audit_logger = get_audit_logger()
csrf_manager = get_csrf_manager()
rate_limiter = get_rate_limiter()

# Initialize site manager
site_manager = get_site_manager()
plugin_types = plugin_registry.get_registered_types()
site_manager.discover_sites(plugin_types)

# WooCommerce can fallback to WordPress site configurations if no WOOCOMMERCE_* env vars
# This mapping is only used when woocommerce has no sites configured
from core.tool_generator import PLUGIN_SITE_FALLBACK

for plugin_type, fallback_type in PLUGIN_SITE_FALLBACK.items():
    if fallback_type in site_manager.sites and plugin_type not in site_manager.sites:
        # Copy site configs from fallback type to plugin type
        site_manager.sites[plugin_type] = site_manager.sites[fallback_type].copy()
        logger.info(
            f"Fallback: using {fallback_type} sites for {plugin_type} ({len(site_manager.sites[plugin_type])} sites)"
        )
    elif plugin_type in site_manager.sites:
        logger.info(
            f"{plugin_type} has its own sites configured ({len(site_manager.sites[plugin_type])} sites)"
        )

# Initialize tool registry and generator
tool_registry = get_tool_registry()
tool_generator = ToolGenerator(site_manager)

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# OAuth server
oauth_server = get_oauth_server()

# Server start time
server_start_time = time.time()

# === TOOL GENERATION ===

def generate_all_tools():
    """Generate tools from all plugins into the tool registry"""
    logger.info("=" * 60)
    logger.info("Generating tools from plugins...")
    logger.info("=" * 60)

    # WordPress Core (64 tools)
    try:
        from plugins.wordpress.plugin import WordPressPlugin

        wordpress_tools = tool_generator.generate_tools(WordPressPlugin, "wordpress")
        for tool_def in wordpress_tools:
            tool_registry.register(tool_def)
        logger.info(f"  WordPress Core: {len(wordpress_tools)} tools")
    except Exception as e:
        logger.error(f"Failed to generate WordPress tools: {e}")

    # WooCommerce (28 tools) - Phase D.1
    try:
        from plugins.woocommerce.plugin import WooCommercePlugin

        woocommerce_tools = tool_generator.generate_tools(WooCommercePlugin, "woocommerce")
        for tool_def in woocommerce_tools:
            tool_registry.register(tool_def)
        logger.info(f"  WooCommerce: {len(woocommerce_tools)} tools")
    except Exception as e:
        logger.error(f"Failed to generate WooCommerce tools: {e}")

    # WordPress Advanced (22 tools)
    try:
        from plugins.wordpress_advanced.plugin import WordPressAdvancedPlugin

        wp_adv_tools = tool_generator.generate_tools(WordPressAdvancedPlugin, "wordpress_advanced")
        for tool_def in wp_adv_tools:
            tool_registry.register(tool_def)
        logger.info(f"  WordPress Advanced: {len(wp_adv_tools)} tools")
    except Exception as e:
        logger.error(f"Failed to generate WordPress Advanced tools: {e}")

    # Gitea (55 tools)
    try:
        from plugins.gitea.plugin import GiteaPlugin

        gitea_tools = tool_generator.generate_tools(GiteaPlugin, "gitea")
        for tool_def in gitea_tools:
            tool_registry.register(tool_def)
        logger.info(f"  Gitea: {len(gitea_tools)} tools")
    except Exception as e:
        logger.error(f"Failed to generate Gitea tools: {e}")

    logger.info(f"Total tools in registry: {tool_registry.get_count()}")
    logger.info("=" * 60)

# === ENDPOINT CREATION ===

class EndpointAuthMiddleware(Middleware):
    """Authentication middleware for specific endpoint"""

    def __init__(self, endpoint_config: EndpointConfig):
        self.config = endpoint_config

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = getattr(context.message, "name", "unknown")

        try:
            # Get headers
            try:
                headers = get_http_headers()
            except Exception:
                headers = {}

            auth_header = headers.get("authorization", "")
            headers.get("x-forwarded-for", "unknown")

            # Parse token
            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif auth_header:
                token = auth_header

            # Check authentication
            is_master = False
            key_project_id = None
            key_scope = "read"
            key_id = None

            if token:
                if token.startswith("sk-"):
                    # Master key
                    if auth_manager.validate_master_key(token):
                        is_master = True
                        key_project_id = "*"
                        key_scope = "admin"
                        key_id = "master"
                    else:
                        raise ToolError("Invalid master API key")

                elif token.startswith("cmp_"):
                    # Project API key
                    key = api_key_manager.get_key_by_token(token)
                    if not key:
                        raise ToolError("Invalid API key")
                    if key.revoked:
                        raise ToolError("API key has been revoked")
                    if key.is_expired():
                        raise ToolError("API key has expired")

                    key_id = key.key_id
                    key_project_id = key.project_id
                    key_scope = key.scope

                else:
                    # Try OAuth token
                    try:
                        from core.oauth import get_token_manager

                        token_manager = get_token_manager()
                        payload = token_manager.validate_access_token(token)
                        if payload:
                            key_project_id = payload.get("project_id", "*")
                            key_scope = payload.get("scope", "read")
                            key_id = f"oauth_{payload.get('sub', 'unknown')}"
                        else:
                            # OAuth token validation returned None - invalid token
                            raise ToolError("Invalid OAuth access token")
                    except ToolError:
                        raise
                    except Exception:
                        raise ToolError("Invalid authentication token")

            # Check if endpoint requires master key
            if self.config.require_master_key and not is_master:
                raise ToolError(f"Endpoint {self.config.path} requires master API key")

            # Check if no auth provided - require authentication for all endpoints
            if not token:
                if self.config.require_master_key:
                    raise ToolError(
                        f"Endpoint {self.config.path} requires master API key. "
                        "Please provide Authorization header with Bearer sk-..."
                    )
                else:
                    raise ToolError(
                        "Authentication required. Please provide Authorization header with Bearer token. "
                        "Supported tokens: Master key (sk-...), Project API key (cmp_...), or OAuth token."
                    )

            # Check plugin type access for non-master keys
            if key_project_id and key_project_id != "*":
                if "_" in key_project_id:
                    key_plugin_type = key_project_id.split("_")[0]
                    if self.config.plugin_types and key_plugin_type not in self.config.plugin_types:
                        raise ToolError(
                            f"API key for {key_plugin_type} cannot access {self.config.name}"
                        )

            # Check tool blacklist
            if not self.config.allows_tool(tool_name):
                raise ToolError(f"Access denied to tool: {tool_name}")

            # Set context
            if key_id:
                set_api_key_context(
                    key_id=key_id,
                    project_id=key_project_id or "*",
                    scope=key_scope,
                    is_global=key_project_id == "*",
                )

            # Execute tool
            result = await call_next(context)

            # Clear context
            clear_api_key_context()

            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"Auth error in {tool_name}: {e}")
            raise ToolError(f"Authentication error: {str(e)}")

def create_dynamic_tool(
    name: str, description: str, handler: Callable, input_schema: dict | None = None
) -> Callable:
    """Create a dynamic tool function with proper signature"""

    # Build parameters
    params = []
    annotations = {}

    if input_schema and "properties" in input_schema:
        required = input_schema.get("required", [])

        for param_name, param_info in input_schema["properties"].items():
            param_type = param_info.get("type", "string")
            type_map = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            py_type = type_map.get(param_type, str)

            if param_name not in required:
                default_value = param_info.get("default", None)
                annotations[param_name] = Optional[py_type]
                params.append(
                    inspect.Parameter(
                        param_name,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        default=default_value,
                        annotation=Optional[py_type],
                    )
                )
            else:
                annotations[param_name] = py_type
                params.append(
                    inspect.Parameter(
                        param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=py_type
                    )
                )

    param_names = [p.name for p in params]
    param_str = ", ".join(param_names)

    func_code = f"""
async def {name}({param_str}):
    '''{description}'''
    kwargs = {{{', '.join(f'"{p}": {p}' for p in param_names)}}}
    return await handler(**kwargs)
"""

    local_vars = {"handler": handler}
    exec(func_code, local_vars)
    dynamic_wrapper = local_vars[name]
    annotations["return"] = str
    dynamic_wrapper.__annotations__ = annotations

    return dynamic_wrapper

def get_tools_for_endpoint(config: EndpointConfig) -> list[ToolDefinition]:
    """Get tools that should be registered for a specific endpoint"""
    tools = []

    for tool_def in tool_registry.get_all():
        tool_name = tool_def.name

        # Check plugin type
        # Order matters: check more specific prefixes first
        plugin_type = None
        if tool_name.startswith("wordpress_advanced_"):
            plugin_type = "wordpress_advanced"
        elif tool_name.startswith("woocommerce_"):
            plugin_type = "woocommerce"
        elif tool_name.startswith("wordpress_"):
            plugin_type = "wordpress"
        elif tool_name.startswith("gitea_"):
            plugin_type = "gitea"

        # Filter by plugin type
        if config.plugin_types and plugin_type:
            if plugin_type not in config.plugin_types:
                continue

        # Check blacklist
        if not config.allows_tool(tool_name):
            continue

        tools.append(tool_def)

    return tools

def create_mcp_endpoint(config: EndpointConfig) -> FastMCP:
    """Create a FastMCP instance for a specific endpoint"""
    mcp = FastMCP(config.name)

    # Add authentication middleware
    mcp.add_middleware(EndpointAuthMiddleware(config))

    # Get tools for this endpoint
    tools = get_tools_for_endpoint(config)

    logger.info(f"Creating endpoint {config.path}: {len(tools)} tools")

    # Register tools
    for tool_def in tools:
        try:
            wrapped = create_dynamic_tool(
                tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
            )
            mcp.tool()(wrapped)
        except Exception as e:
            logger.error(f"Failed to register tool {tool_def.name}: {e}")

    return mcp

# === SYSTEM TOOLS (added to admin endpoint) ===

def add_system_tools(mcp: FastMCP):
    """Add system tools to an MCP instance"""

    @mcp.tool()
    async def list_projects() -> str:
        """List all discovered projects across all plugins."""
        projects = []
        for full_id, plugin in project_manager.projects.items():
            projects.append(
                {
                    "id": full_id,
                    "name": plugin.get_plugin_name(),
                    "type": plugin.get_plugin_name().lower(),
                }
            )
        return str({"projects": projects, "total": len(projects)})

    @mcp.tool()
    async def get_system_metrics() -> str:
        """Get system-wide metrics including uptime and request statistics."""
        from core import get_health_monitor

        monitor = get_health_monitor()
        metrics = monitor.get_system_metrics()
        return str(metrics)

    @mcp.tool()
    async def get_rate_limit_stats(client_id: str = None) -> str:
        """Get rate limit statistics."""
        stats = rate_limiter.get_stats(client_id)
        return str(stats)

    @mcp.tool()
    async def list_endpoints() -> str:
        """List all available MCP endpoints including per-project endpoints."""
        endpoints = []

        # Add predefined endpoints
        for _endpoint_type, config in ENDPOINT_CONFIGS.items():
            endpoints.append(
                {
                    "path": config.path,
                    "name": config.name,
                    "description": config.description,
                    "plugin_types": config.plugin_types,
                    "require_master_key": config.require_master_key,
                    "type": "predefined",
                }
            )

        # Add per-project endpoints
        all_sites = site_manager.list_all_sites()
        for site_info in all_sites:
            plugin_type = site_info["plugin_type"]
            site_id = site_info["site_id"]
            alias = site_info.get("alias")
            full_id = site_info["full_id"]

            # Use alias for path if different from site_id
            path_suffix = alias if alias and alias != site_id else full_id
            path = f"/mcp/project/{path_suffix}"

            endpoints.append(
                {
                    "path": path,
                    "name": f"Project: {full_id}",
                    "description": f"Tools scoped to {plugin_type} project {full_id}",
                    "plugin_types": [plugin_type],
                    "require_master_key": False,
                    "type": "project",
                    "project_id": full_id,
                    "alias": alias,
                }
            )

        return str({"endpoints": endpoints, "total": len(endpoints)})

    # API Key management tools
    @mcp.tool()
    async def manage_api_keys_create(
        project_id: str, scope: str = "read", name: str = None, expires_in_days: int = None
    ) -> dict:
        """Create a new API key for a project."""
        try:
            key = api_key_manager.create_key(
                project_id=project_id, scope=scope, name=name, expires_in_days=expires_in_days
            )
            return {
                "success": True,
                "key_id": key.key_id,
                "api_key": key.api_key,
                "project_id": key.project_id,
                "scope": key.scope,
                "warning": "SAVE THIS KEY - It will not be shown again!",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def manage_api_keys_list(project_id: str = None) -> dict:
        """List API keys."""
        try:
            if project_id == "*":
                keys = api_key_manager.list_all_keys()
            elif project_id:
                keys = api_key_manager.list_keys(project_id)
            else:
                keys = api_key_manager.list_all_keys()

            return {
                "success": True,
                "keys": [
                    {
                        "key_id": k.key_id,
                        "project_id": k.project_id,
                        "scope": k.scope,
                        "name": k.name,
                        "revoked": k.revoked,
                    }
                    for k in keys
                ],
                "total": len(keys),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def manage_api_keys_revoke(key_id: str) -> dict:
        """Revoke an API key."""
        try:
            result = api_key_manager.revoke_key(key_id)
            return {"success": result, "key_id": key_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # OAuth tools
    @mcp.tool()
    async def oauth_list_clients() -> dict:
        """List registered OAuth clients."""
        try:
            clients = oauth_server.client_registry.list_clients()
            return {
                "success": True,
                "clients": [
                    {
                        "client_id": c.client_id,
                        "client_name": c.client_name,
                        "redirect_uris": c.redirect_uris,
                    }
                    for c in clients
                ],
                "total": len(clients),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def oauth_revoke_client(client_id: str) -> dict:
        """Revoke an OAuth client."""
        try:
            result = oauth_server.client_registry.revoke_client(client_id)
            return {"success": result, "client_id": client_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

# === HTTP ROUTES ===

async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse(
        {
            "status": "healthy",
            "uptime": int(time.time() - server_start_time),
            "version": "2.1.0",
            "architecture": "multi-endpoint",
            "phase": "D.1 - WooCommerce Split",
            "endpoints": list(ENDPOINT_CONFIGS.keys()),
        }
    )

async def endpoint_info(request: Request) -> JSONResponse:
    """List all available endpoints including per-project endpoints"""
    endpoints = []

    # Add predefined endpoints
    # Note: FastMCP adds /mcp to the mount path automatically
    for _endpoint_type, config in ENDPOINT_CONFIGS.items():
        # Convert mount path to actual MCP path
        if config.path == "/":
            mcp_path = "/mcp"
        else:
            mcp_path = f"{config.path}/mcp"

        endpoints.append(
            {
                "path": mcp_path,
                "mount_path": config.path,
                "name": config.name,
                "description": config.description,
                "plugin_types": config.plugin_types,
                "require_master_key": config.require_master_key,
                "type": "predefined",
            }
        )

    # Add per-project endpoints
    all_sites = site_manager.list_all_sites()
    for site_info in all_sites:
        plugin_type = site_info["plugin_type"]
        site_info["site_id"]
        alias = site_info.get("alias")
        full_id = site_info["full_id"]

        # Use effective path suffix (handles duplicate alias conflicts)
        path_suffix = site_manager.get_effective_path_suffix(full_id)
        mount_path = f"/project/{path_suffix}"
        mcp_path = f"/project/{path_suffix}/mcp"

        endpoints.append(
            {
                "path": mcp_path,
                "mount_path": mount_path,
                "name": f"Project: {full_id}",
                "description": f"Tools scoped to {plugin_type} project {full_id}",
                "plugin_types": [plugin_type],
                "require_master_key": False,
                "type": "project",
                "project_id": full_id,
                "alias": alias,
                "effective_path": path_suffix,
            }
        )

    # Add alias conflicts info
    alias_conflicts = site_manager.get_alias_conflicts()

    return JSONResponse(
        {
            "endpoints": endpoints,
            "total": len(endpoints),
            "alias_conflicts": alias_conflicts if alias_conflicts else None,
        }
    )

# OAuth endpoints (imported from server.py patterns)
async def oauth_metadata(request: Request) -> JSONResponse:
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)"""
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/oauth/authorize",
            "token_endpoint": f"{base_url}/oauth/token",
            "registration_endpoint": f"{base_url}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
            "scopes_supported": ["read", "write", "admin"],
        }
    )

async def oauth_protected_resource(request: Request) -> JSONResponse:
    """OAuth 2.0 Protected Resource Metadata (RFC 9728)"""
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        {
            "resource": base_url,
            "authorization_servers": [base_url],
            "scopes_supported": ["read", "write", "admin"],
            "bearer_methods_supported": ["header"],
        }
    )

async def oauth_register(request: Request) -> JSONResponse:
    """
    Dynamic Client Registration (RFC 7591) - MCP Spec Compliant

    Supports two modes:
    1. Open DCR: For trusted MCP clients (Claude, ChatGPT) - no auth required
    2. Protected DCR: For custom redirect_uris - Master API Key required
    """
    client_ip = request.client.host if request.client else "unknown"

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Invalid JSON"}, status_code=400
        )

    redirect_uris = data.get("redirect_uris", [])
    if not redirect_uris or not isinstance(redirect_uris, list):
        return JSONResponse(
            {"error": "invalid_redirect_uri", "error_description": "redirect_uris required"},
            status_code=400,
        )

    # Check if open DCR is allowed for these redirect_uris
    is_open_dcr_allowed = is_redirect_uri_allowed_for_open_dcr(redirect_uris)

    # Check for Master API Key
    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    has_valid_master_key = token and auth_manager.validate_master_key(token)

    if is_open_dcr_allowed:
        # Open DCR - check rate limiting
        rate_ok, rate_error = check_dcr_rate_limit(client_ip)
        if not rate_ok:
            logger.warning(f"DCR rate limit exceeded for {client_ip}")
            return JSONResponse(
                {"error": "too_many_requests", "error_description": rate_error}, status_code=429
            )
        logger.info(f"Open DCR registration from {client_ip} for {redirect_uris}")
        audit_logger.log_event(
            event_type="oauth_dcr_open",
            details={
                "client_ip": client_ip,
                "redirect_uris": redirect_uris,
                "client_name": data.get("client_name", "Unknown"),
                "auth_mode": "open_dcr",
            },
        )
    elif has_valid_master_key:
        logger.info(f"Protected DCR registration from {client_ip} with Master API Key")
        audit_logger.log_event(
            event_type="oauth_dcr_protected",
            details={
                "client_ip": client_ip,
                "redirect_uris": redirect_uris,
                "client_name": data.get("client_name", "Unknown"),
                "auth_mode": "master_key",
            },
        )
    else:
        logger.warning(
            f"Unauthorized DCR attempt from {client_ip}: {redirect_uris} not in allowlist"
        )
        return JSONResponse(
            {
                "error": "unauthorized",
                "error_description": f"DCR requires trusted redirect_uri (Claude, ChatGPT) or Master API Key. "
                f"Your redirect_uris {redirect_uris} are not allowed.",
            },
            status_code=401,
        )

    try:
        client = oauth_server.register_client(
            client_name=data.get("client_name", "Unknown"),
            redirect_uris=redirect_uris,
            scope=data.get("scope", "read"),
        )
        return JSONResponse(
            {
                "client_id": client.client_id,
                "client_secret": client.client_secret,
                "client_name": client.client_name,
                "redirect_uris": client.redirect_uris,
            },
            status_code=201,
        )
    except Exception as e:
        logger.error(f"DCR error: {e}")
        return JSONResponse({"error": "server_error", "error_description": str(e)}, status_code=400)

async def oauth_authorize(request: Request):
    """OAuth Authorization Endpoint"""
    client_id = request.query_params.get("client_id")
    redirect_uri = request.query_params.get("redirect_uri")
    scope = request.query_params.get("scope", "read")
    state = request.query_params.get("state", "")
    code_challenge = request.query_params.get("code_challenge")

    # Validate client
    client = oauth_server.client_registry.get_client(client_id)
    if not client:
        return HTMLResponse("<h1>Invalid client</h1>", status_code=400)

    # Detect language
    accept_lang = request.headers.get("accept-language", "en")
    lang = detect_language(accept_lang)
    translations = get_all_translations(lang)

    # Generate CSRF token
    csrf_token = csrf_manager.generate_token()

    return templates.TemplateResponse(
        "oauth/authorize.html",
        {
            "request": request,
            "client_name": client.client_name,
            "scope": scope,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "csrf_token": csrf_token,
            "lang": lang,
            **translations,
        },
    )

async def oauth_authorize_confirm(request: Request):
    """Handle OAuth authorization form submission"""
    form = await request.form()
    api_key = form.get("api_key")
    client_id = form.get("client_id")
    redirect_uri = form.get("redirect_uri")
    scope = form.get("scope", "read")
    state = form.get("state", "")
    code_challenge = form.get("code_challenge")
    csrf_token = form.get("csrf_token")
    action = form.get("action")

    # Validate CSRF
    if not csrf_manager.validate_token(csrf_token):
        return HTMLResponse("<h1>Invalid CSRF token</h1>", status_code=400)

    # Check action
    if action == "deny":
        return RedirectResponse(f"{redirect_uri}?error=access_denied&state={state}")

    # Validate API key
    key = api_key_manager.get_key_by_token(api_key)
    if not key:
        return HTMLResponse("<h1>Invalid API key</h1>", status_code=400)

    # Generate authorization code
    try:
        code = oauth_server.create_authorization_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            api_key_id=key.key_id,
            project_id=key.project_id,
        )
        return RedirectResponse(f"{redirect_uri}?code={code}&state={state}")
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {e}</h1>", status_code=400)

async def oauth_token(request: Request) -> JSONResponse:
    """OAuth Token Endpoint"""
    try:
        form = await request.form()
        grant_type = form.get("grant_type")

        if grant_type == "authorization_code":
            code = form.get("code")
            redirect_uri = form.get("redirect_uri")
            code_verifier = form.get("code_verifier")
            client_id = form.get("client_id")
            client_secret = form.get("client_secret")

            tokens = oauth_server.exchange_code(
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
                client_id=client_id,
                client_secret=client_secret,
            )
            return JSONResponse(tokens)

        elif grant_type == "refresh_token":
            refresh_token = form.get("refresh_token")
            tokens = oauth_server.refresh_tokens(refresh_token)
            return JSONResponse(tokens)

        else:
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    except OAuthError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# === MAIN APP CREATION ===

def create_per_project_endpoints() -> dict[str, FastMCP]:
    """
    Create per-project endpoints for each discovered site.

    Each site gets its own endpoint at /mcp/project/{alias_or_site_id}
    with tools filtered and locked to that specific site.

    Handles duplicate alias conflicts by using full_id for conflicting sites.

    Returns:
        Dictionary mapping path to FastMCP instance
    """
    project_endpoints = {}

    # Get all discovered sites
    all_sites = site_manager.list_all_sites()

    if not all_sites:
        logger.info("No sites discovered, skipping per-project endpoints")
        return project_endpoints

    logger.info(f"Creating per-project endpoints for {len(all_sites)} sites...")

    for site_info in all_sites:
        plugin_type = site_info["plugin_type"]
        full_id = site_info["full_id"]

        # Use effective path suffix (handles duplicate alias conflicts)
        path_suffix = site_manager.get_effective_path_suffix(full_id)
        config = create_project_endpoint_config(
            project_id=full_id, plugin_type=plugin_type, site_alias=path_suffix
        )

        # Create the MCP endpoint
        try:
            mcp = create_mcp_endpoint(config)
            project_endpoints[config.path] = mcp
            logger.info(f"  ✓ {config.path}: {config.name} ({plugin_type})")
        except Exception as e:
            logger.error(f"  ✗ Failed to create {config.path}: {e}")

    # Log alias conflicts summary
    alias_conflicts = site_manager.get_alias_conflicts()
    if alias_conflicts:
        logger.warning(f"  ⚠ {len(alias_conflicts)} alias conflict(s) detected - see logs above")

    logger.info(f"Created {len(project_endpoints)} per-project endpoints")
    return project_endpoints

def create_app() -> Starlette:
    """Create the main Starlette application with all endpoints"""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response as StarletteResponse

    # ========================================
    # OAuth 401 Middleware for MCP Endpoints
    # ========================================
    class OAuthRequiredMiddleware(BaseHTTPMiddleware):
        """Returns 401 + WWW-Authenticate for unauthenticated MCP requests."""

        MCP_PATHS = ["/mcp", "/sse"]
        EXCLUDED_PATHS = ["/.well-known/", "/oauth/", "/health", "/endpoints"]

        async def dispatch(self, request, call_next):
            path = request.url.path
            is_mcp = any(p in path for p in self.MCP_PATHS)
            is_excluded = any(path.startswith(e) for e in self.EXCLUDED_PATHS)

            if is_mcp and not is_excluded:
                auth = request.headers.get("authorization", "")
                if not auth or not auth.startswith("Bearer "):
                    base_url = str(request.base_url).rstrip("/")
                    return StarletteResponse(
                        content='{"error": "unauthorized"}',
                        status_code=401,
                        media_type="application/json",
                        headers={
                            "WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"',
                            "Access-Control-Allow-Origin": "*",
                        },
                    )
            return await call_next(request)

    # Generate all tools first
    generate_all_tools()

    # Create MCP endpoints
    endpoints = {}
    for endpoint_type, config in ENDPOINT_CONFIGS.items():
        mcp = create_mcp_endpoint(config)

        # Add system tools to admin endpoint
        if endpoint_type == EndpointType.ADMIN:
            add_system_tools(mcp)

        endpoints[config.path] = mcp

    # Create per-project endpoints (e.g., /mcp/project/myblog, /mcp/project/wordpress_site1)
    project_endpoints = create_per_project_endpoints()
    endpoints.update(project_endpoints)

    # Create routes
    routes = [
        Route("/health", health_check, methods=["GET"]),
        Route("/endpoints", endpoint_info, methods=["GET"]),
        # OAuth routes
        Route("/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", oauth_protected_resource, methods=["GET"]),
        Route("/oauth/register", oauth_register, methods=["POST"]),
        Route("/oauth/authorize", oauth_authorize, methods=["GET"]),
        Route("/oauth/authorize/confirm", oauth_authorize_confirm, methods=["POST"]),
        Route("/oauth/token", oauth_token, methods=["POST"]),
    ]

    # Mount MCP endpoints
    for path, mcp in endpoints.items():
        routes.append(Mount(path, app=mcp.sse_app()))
        logger.info(f"Mounted MCP endpoint: {path}")

    # Create Starlette app with OAuth middleware
    middleware = [StarletteMiddleware(OAuthRequiredMiddleware)]
    app = Starlette(routes=routes, middleware=middleware)

    return app

# === ENTRY POINT ===

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Hub - Multi-Endpoint Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MCP Hub - Multi-Endpoint Architecture v2.1.0")
    logger.info("Phase D.1: WooCommerce Split")
    logger.info("=" * 60)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info("=" * 60)

    app = create_app()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
