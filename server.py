#!/usr/bin/env python3
"""
Coolify Projects MCP Server

Universal MCP server for managing Coolify projects through plugins.
Supports WordPress, Supabase, Gitea, and custom project types.

Usage:
    # With stdio transport (Claude Desktop)
    python server.py

    # With SSE transport (HTTP server)
    python server.py --transport sse --port 8000

Environment Variables:
    MASTER_API_KEY: Master API key for authentication
    {PLUGIN_TYPE}_{PROJECT_ID}_{CONFIG_KEY}: Project configurations
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
"""

import copy
import logging
import os
import sys
import time
from datetime import UTC, datetime
from typing import Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.templating import Jinja2Templates

# Import core modules
from core import (
    EventType,
    LogLevel,
    ToolGenerator,
    UnifiedToolGenerator,
    get_api_key_manager,
    get_audit_logger,
    get_auth_manager,
    get_project_manager,
    get_rate_limiter,
    # Option B modules (new clean architecture)
    get_site_manager,
    get_site_registry,
    get_tool_registry,
    set_api_key_context,
)
from core.dashboard.routes import (
    dashboard_api_audit_logs,
    dashboard_api_health,
    dashboard_api_keys_create,
    dashboard_api_keys_delete,
    # K.3: API Keys routes
    dashboard_api_keys_list,
    dashboard_api_keys_revoke,
    dashboard_api_project_detail,
    dashboard_api_projects,
    dashboard_api_stats,
    # K.4: Audit Logs routes
    dashboard_audit_logs_list,
    # K.5: Health Monitoring routes
    dashboard_health_page,
    dashboard_health_projects_partial,
    dashboard_home,
    dashboard_login_page,
    dashboard_login_submit,
    dashboard_logout,
    dashboard_oauth_clients_create,
    dashboard_oauth_clients_delete,
    # K.4: OAuth Clients routes
    dashboard_oauth_clients_list,
    dashboard_project_detail,
    dashboard_project_health_check,
    # K.2: Projects routes
    dashboard_projects_list,
    # K.5: Settings routes
    dashboard_settings_page,
)
from core.i18n import detect_language, get_all_translations

# OAuth and CSRF (Phase E)
from core.oauth import get_csrf_manager
from plugins import registry as plugin_registry

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

logger = logging.getLogger(__name__)

# OAuth Authorization Configuration
OAUTH_AUTH_MODE = os.getenv("OAUTH_AUTH_MODE", "trusted_domains").lower()
OAUTH_TRUSTED_DOMAINS = os.getenv(
    "OAUTH_TRUSTED_DOMAINS", "chatgpt.com,chat.openai.com,openai.com,platform.openai.com"
).split(",")
OAUTH_TRUSTED_DOMAINS = [domain.strip() for domain in OAUTH_TRUSTED_DOMAINS]  # Clean whitespace

# ========================================
# DCR (Dynamic Client Registration) Configuration
# ========================================
# Allowlist of redirect_uri patterns for open DCR (without Master API Key)
# These are trusted MCP clients (Claude, ChatGPT, etc.)
# Pattern format: regex patterns matched against redirect_uri
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

# DCR Rate Limiting (per IP)
DCR_RATE_LIMIT_PER_MINUTE = int(os.getenv("DCR_RATE_LIMIT_PER_MINUTE", "10"))
DCR_RATE_LIMIT_PER_HOUR = int(os.getenv("DCR_RATE_LIMIT_PER_HOUR", "30"))

# In-memory DCR rate limit tracking
_dcr_rate_limits: dict = (
    {}
)  # {ip: {"minute": count, "hour": count, "minute_reset": timestamp, "hour_reset": timestamp}}

def is_redirect_uri_allowed_for_open_dcr(redirect_uris: list) -> bool:
    """
    Check if all redirect_uris match the allowlist patterns.

    For open DCR (without Master API Key), all redirect_uris must match
    at least one pattern in DCR_ALLOWED_REDIRECT_PATTERNS.

    Args:
        redirect_uris: List of redirect URIs to check

    Returns:
        True if ALL redirect_uris match at least one allowed pattern
    """
    for uri in redirect_uris:
        uri_allowed = False
        for pattern in DCR_ALLOWED_REDIRECT_PATTERNS:
            if re.match(pattern, uri):
                uri_allowed = True
                break
        if not uri_allowed:
            return False
    return True

def check_dcr_rate_limit(client_ip: str) -> tuple[bool, str]:
    """
    Check if DCR request is within rate limits.

    Args:
        client_ip: Client IP address

    Returns:
        Tuple of (is_allowed, error_message)
    """
    import time

    now = time.time()

    if client_ip not in _dcr_rate_limits:
        _dcr_rate_limits[client_ip] = {
            "minute": 0,
            "hour": 0,
            "minute_reset": now + 60,
            "hour_reset": now + 3600,
        }

    limits = _dcr_rate_limits[client_ip]

    # Reset counters if time expired
    if now > limits["minute_reset"]:
        limits["minute"] = 0
        limits["minute_reset"] = now + 60

    if now > limits["hour_reset"]:
        limits["hour"] = 0
        limits["hour_reset"] = now + 3600

    # Check limits
    if limits["minute"] >= DCR_RATE_LIMIT_PER_MINUTE:
        return (
            False,
            f"DCR rate limit exceeded: {DCR_RATE_LIMIT_PER_MINUTE} registrations per minute",
        )

    if limits["hour"] >= DCR_RATE_LIMIT_PER_HOUR:
        return False, f"DCR rate limit exceeded: {DCR_RATE_LIMIT_PER_HOUR} registrations per hour"

    # Increment counters
    limits["minute"] += 1
    limits["hour"] += 1

    return True, ""

# Validate auth mode
if OAUTH_AUTH_MODE not in ["required", "optional", "trusted_domains"]:
    logger.warning(f"Invalid OAUTH_AUTH_MODE '{OAUTH_AUTH_MODE}'. Defaulting to 'trusted_domains'")
    OAUTH_AUTH_MODE = "trusted_domains"

logger.info(f"OAuth Authorization Mode: {OAUTH_AUTH_MODE}")
if OAUTH_AUTH_MODE == "trusted_domains":
    logger.info(f"OAuth Trusted Domains: {', '.join(OAUTH_TRUSTED_DOMAINS)}")

# Initialize MCP server
mcp = FastMCP("Coolify Projects Manager")

# Initialize Jinja2 templates (Phase E - OAuth Authorization Page)
templates = Jinja2Templates(directory="templates")
logger.info("Jinja2 template engine initialized")

# Initialize managers
auth_manager = get_auth_manager()
api_key_manager = get_api_key_manager()
project_manager = get_project_manager()
audit_logger = get_audit_logger()
csrf_manager = get_csrf_manager()  # Phase E: CSRF protection

# Initialize site registry (legacy - kept for backward compatibility)
site_registry = get_site_registry()
plugin_types = plugin_registry.get_registered_types()
site_registry.discover_sites(plugin_types)

# Initialize unified tool generator (legacy - kept for backward compatibility)
unified_tool_generator = UnifiedToolGenerator(project_manager)

# === Option B Architecture (New Clean Architecture) ===
# Initialize site manager (replacement for SiteRegistry)
site_manager = get_site_manager()
site_manager.discover_sites(plugin_types)

# Initialize tool registry (central tool management)
tool_registry = get_tool_registry()

# Initialize tool generator (replacement for UnifiedToolGenerator)
tool_generator = ToolGenerator(site_manager)

logger.info("=" * 60)
logger.info("Coolify Projects MCP Server - Option B Clean Architecture")
logger.info("=" * 60)
_mk = auth_manager.get_master_key()
logger.info(f"Master API Key: {_mk[:8]}***{_mk[-4:]}")
logger.info(f"Discovered {len(project_manager.projects)} per-site project instances (legacy)")
logger.info(
    f"Discovered {site_manager.get_count()} unique sites across {len(plugin_types)} plugin types"
)
logger.info(f"Site breakdown: {site_manager.get_count_by_type()}")

# Log discovered projects
for full_id, plugin in project_manager.projects.items():
    logger.info(f"  - {full_id} ({plugin.get_plugin_name()})")

# Log discovered sites (Option B)
logger.info("\nDiscovered sites:")
for site_info in site_manager.list_all_sites():
    alias_display = (
        f" (alias: {site_info['alias']})" if site_info["alias"] != site_info["site_id"] else ""
    )
    logger.info(f"  - {site_info['full_id']}{alias_display}")

logger.info("=" * 60)

# === MCP INSTRUCTIONS HELPER ===
# Phase K.2: Auto-discovery of available sites for AI assistants

def generate_mcp_instructions(plugin_type: str = None, site_locked: str = None) -> str:
    """
    Generate MCP server instructions for AI assistants.

    These instructions are shown to AI clients (Claude, ChatGPT) when they connect,
    helping them understand available sites without needing to ask the user.

    Args:
        plugin_type: Optional plugin type to filter sites (e.g., 'wordpress')
                     If None, shows all sites (admin endpoint)
        site_locked: If set, indicates this is a per-project endpoint locked to a specific site

    Returns:
        Instructions string for the MCP server
    """
    if site_locked:
        # Per-project endpoint - site is auto-injected
        return f"""This endpoint is locked to site: {site_locked}

All tools are pre-configured for this site. You do NOT need to pass the 'site' parameter - it is automatically injected.

Just use the tools directly, for example:
- wordpress_list_posts(per_page=10)
- wordpress_get_post(post_id=123)

The site parameter will be automatically set to '{site_locked}'."""

    # Get available sites
    if plugin_type:
        # Plugin-specific endpoint
        sites = site_manager.get_sites_by_type(plugin_type)
        if not sites:
            return f"No {plugin_type} sites configured. Please check environment variables."

        # Phase K.2.5: Improved instructions for single-site vs multi-site
        if len(sites) == 1:
            # Single site - make it very clear
            site = sites[0]
            site_url = site.url if hasattr(site, "url") else ""
            site_name = site.alias or site.site_id

            # OpenPanel-specific instructions for project_id and organization_id
            openpanel_note = ""
            if plugin_type == "openpanel":
                project_id = getattr(site, "project_id", None)
                organization_id = getattr(site, "organization_id", None)
                config_parts = []

                if project_id:
                    config_parts.append(f"📊 Project ID: {project_id}")
                if organization_id:
                    config_parts.append(f"🏢 Organization ID: {organization_id}")

                if project_id:
                    openpanel_note = f"""

{chr(10).join(config_parts)}
These IDs are pre-configured. You do NOT need to pass project_id for export/read tools.
All export tools (get_event_count, get_unique_users, export_events, etc.) will automatically use this project."""
                else:
                    openpanel_note = """

⚠️ OpenPanel Note: No project_id configured.
For export/read operations (get_event_count, export_events, etc.), you need to ask the user for their Project ID.
The user can find it in OpenPanel Dashboard → Project Settings.
Track API operations (identify_user, track_event, etc.) work without project_id."""

            return f"""🔗 SINGLE SITE MODE - Connected to: {site_name}
URL: {site_url}

You are connected to exactly ONE site. The 'site' parameter is OPTIONAL - you can omit it or use any value.

Examples (all equivalent):
- wordpress_list_posts(per_page=10)
- wordpress_list_posts(site="{site_name}", per_page=10)
- wordpress_list_posts(site="default", per_page=10)

Just use the tools directly without asking which site to use.{openpanel_note}"""

        else:
            # Multiple sites - require site selection
            site_list = []
            for site in sites:
                alias_info = (
                    f" (alias: '{site.alias}')" if site.alias and site.alias != site.site_id else ""
                )
                url_info = f" - {site.url}" if hasattr(site, "url") and site.url else ""
                site_list.append(f"  • {site.site_id}{alias_info}{url_info}")

            sites_text = "\n".join(site_list)

            return f"""📋 MULTI-SITE MODE - {len(sites)} sites available:

{sites_text}

When using tools, pass the 'site' parameter with either the site_id or alias.
Example: wordpress_list_posts(site="site1", per_page=10)

Use list_sites() to see all available sites."""

    else:
        # Admin endpoint - show all sites
        all_sites = site_manager.list_all_sites()
        if not all_sites:
            return "No sites configured. Please check environment variables."

        # Group by plugin type
        by_type = {}
        for site in all_sites:
            pt = site["plugin_type"]
            if pt not in by_type:
                by_type[pt] = []
            by_type[pt].append(site)

        sections = []
        for pt, sites in sorted(by_type.items()):
            site_entries = []
            for s in sites:
                alias_info = f" (alias: '{s['alias']}')" if s["alias"] != s["site_id"] else ""
                site_entries.append(f"    • {s['site_id']}{alias_info}")
            sections.append(f"  {pt.title()}: {len(sites)} site(s)\n" + "\n".join(site_entries))

        sites_summary = "\n\n".join(sections)

        return f"""This is the Admin endpoint with access to {len(all_sites)} site(s) across {len(by_type)} plugin type(s):

{sites_summary}

When using tools, pass the 'site' parameter with either the site_id or alias.
Example: wordpress_list_posts(site="myblog", per_page=10)

Use list_projects() to get detailed information about all configured sites.
Use get_endpoints() to see all available MCP endpoints.

If working with a single site, use it directly without asking the user."""

# Set instructions for admin endpoint (after sites are discovered)
mcp.instructions = generate_mcp_instructions()
logger.info("Admin MCP instructions configured with site discovery")

# === AUTHENTICATION MIDDLEWARE ===

def extract_project_from_tool(tool_name: str) -> str:
    """
    Extract project_id from tool name.

    Examples:
        "wordpress_list_posts" -> "*" (unified tool, project via param)
        "list_projects" -> "*" (system tool)
        "get_rate_limit_stats" -> "*" (system tool)

    Returns:
        "*" for now (project is passed as parameter in unified architecture)
    """
    # In unified architecture, project is passed as parameter, not in tool name
    # So we return "*" to indicate "any project" at this stage
    # The actual project will be validated when the tool is executed
    return "*"

def extract_plugin_type_from_tool(tool_name: str) -> str | None:
    """
    Extract plugin type from tool name for tool visibility filtering.

    Phase 5.5: Tool Visibility Filter
    Each API key should only see tools related to its plugin type.

    Examples:
        "wordpress_list_posts" -> "wordpress"
        "wordpress_advanced_wp_db_export" -> "wordpress_advanced"
        "wordpress_advanced_bulk_update_posts" -> "wordpress_advanced"
        "gitea_list_repositories" -> "gitea"
        "list_projects" -> None (system tool)
        "manage_api_keys_list" -> None (system tool)

    Returns:
        Plugin type string or None for system tools
    """
    # Remove MCP namespace prefix if present
    clean_name = tool_name
    if tool_name.startswith("mcp__coolify-projects__"):
        clean_name = tool_name.replace("mcp__coolify-projects__", "")

    # Check for plugin types (order matters - check more specific first)
    # wordpress_advanced must be checked before wordpress
    if clean_name.startswith("wordpress_advanced_"):
        return "wordpress_advanced"
    elif clean_name.startswith("wordpress_") or clean_name.startswith("woocommerce_"):
        return "wordpress"
    elif clean_name.startswith("gitea_"):
        return "gitea"
    elif clean_name.startswith("n8n_"):
        return "n8n"
    elif clean_name.startswith("supabase_"):
        return "supabase"
    elif clean_name.startswith("openpanel_"):
        return "openpanel"
    elif clean_name.startswith("appwrite_"):
        return "appwrite"
    elif clean_name.startswith("directus_"):
        return "directus"
    elif clean_name.startswith("ghost_"):
        return "ghost"

    # System tools (no plugin type)
    return None

def check_tool_visibility(tool_name: str, api_key_project_id: str) -> bool:
    """
    Check if API key has visibility to the requested tool.

    Phase 5.5: Tool Visibility Filter

    Rules:
    - Global API keys (project_id="*") see ALL tools
    - Plugin-specific keys (project_id="wordpress_xxx") see only that plugin's tools
    - System tools are visible to global keys only

    Args:
        tool_name: Name of the tool being accessed
        api_key_project_id: project_id from API key

    Returns:
        True if tool is visible, False otherwise

    Examples:
        >>> check_tool_visibility("wordpress_list_posts", "wordpress_site1")
        True
        >>> check_tool_visibility("wordpress_advanced_wp_db_export", "wordpress_advanced_site1")
        True
        >>> check_tool_visibility("gitea_list_repos", "wordpress_site1")
        False
        >>> check_tool_visibility("list_projects", "wordpress_site1")
        False  # System tools need global key
        >>> check_tool_visibility("wordpress_list_posts", "*")
        True  # Global key sees everything
    """
    # Global keys see everything
    if api_key_project_id == "*":
        return True

    # Extract plugin type from tool name
    tool_plugin_type = extract_plugin_type_from_tool(tool_name)

    # System tools (no plugin type) - only visible to global keys
    if tool_plugin_type is None:
        return False

    # Extract plugin type from API key project_id
    # project_id format: "{plugin_type}_{site_id}" e.g. "wordpress_site1" or "wordpress_advanced_site1"
    # Known plugin types that may contain underscores
    known_plugin_types = ["wordpress_advanced", "wordpress", "gitea", "n8n", "supabase", "ghost"]

    key_plugin_type = None
    for ptype in known_plugin_types:
        if api_key_project_id.startswith(ptype + "_"):
            key_plugin_type = ptype
            break

    if key_plugin_type is None:
        # Fallback: extract first part before underscore
        if "_" in api_key_project_id:
            key_plugin_type = api_key_project_id.split("_")[0]
        else:
            key_plugin_type = api_key_project_id

    # Check if plugin types match
    return tool_plugin_type == key_plugin_type

def determine_required_scope(tool_name: str) -> str:
    """
    Determine required scope for a tool.

    Read operations: list, get, check
    Write operations: create, update, delete, revoke, rotate
    Admin operations: manage keys, system operations

    Returns:
        "read", "write", or "admin"
    """
    tool_lower = tool_name.lower()

    # Admin operations
    if any(x in tool_lower for x in ["manage_api_keys", "reset_rate_limit", "export_"]):
        return "admin"

    # Write operations
    if any(
        x in tool_lower
        for x in ["create", "update", "delete", "revoke", "rotate", "upload", "flush"]
    ):
        return "write"

    # Everything else is read
    return "read"

class UserAuthMiddleware(Middleware):
    """
    Middleware to enforce Bearer token authentication for all MCP tool calls.

    Supports both per-project API keys and master API key.
    - Per-project keys: Validated with scope and project access
    - Master key: Full access to all projects

    Stores authentication metadata in context for audit and rate limiting.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Intercept tool calls to validate authentication.

        Args:
            context: Middleware context containing request information
            call_next: Next middleware or tool handler in the chain

        Returns:
            Result from the tool if authentication succeeds

        Raises:
            ToolError: If authentication fails or token is missing/invalid
        """
        try:
            # Get HTTP headers from the request
            headers = get_http_headers()
            auth_header = headers.get("authorization")

            # Check if Authorization header exists
            if not auth_header:
                logger.warning("Request rejected: Missing Authorization header")
                raise ToolError(
                    "Authentication required. Please provide Authorization header with Bearer token."
                )

            # Check if it follows Bearer token format
            if not auth_header.startswith("Bearer "):
                logger.warning(
                    f"Request rejected: Invalid Authorization format: {auth_header[:20]}..."
                )
                raise ToolError("Invalid Authorization format. Expected: 'Bearer <token>'")

            # Extract token from "Bearer <token>"
            token = auth_header.removeprefix("Bearer ").strip()

            if not token:
                logger.warning("Request rejected: Empty token")
                raise ToolError("Invalid Authorization: Token is empty")

            # Get tool information
            # Extract tool name directly from context.message.name
            # context.message is CallToolRequestParams which has 'name' and 'arguments' attributes
            tool_name = "unknown"
            try:
                if hasattr(context, "message") and hasattr(context.message, "name"):
                    tool_name = context.message.name
                    logger.debug(f"Extracted tool_name: {tool_name}")
            except Exception as e:
                logger.warning(f"Failed to extract tool name: {e}")

            project_id = extract_project_from_tool(tool_name)
            required_scope = determine_required_scope(tool_name)

            # Determine if this is a unified tool (takes site parameter)
            # Unified tools will validate project access at execution time
            # Note: FastMCP adds namespace prefix to tool names

            # Check if this is a system tool first
            SYSTEM_TOOLS = [
                "list_projects",
                "get_project_info",
                "check_all_projects_health",
                "get_project_health",
                "get_system_metrics",
                "get_system_uptime",
                "get_rate_limit_stats",
                "export_health_metrics",
                "manage_api_keys_list",
                "manage_api_keys_get_info",
            ]
            is_system_tool = any(tool_name.endswith(st) for st in SYSTEM_TOOLS)

            # FALLBACK: If extraction fails, assume unified tool for safety
            # This allows per-project API keys to work even if extraction fails
            if tool_name == "unknown":
                is_unified_tool = True
            else:
                # All plugin tools that have a 'site' parameter are unified tools
                # They defer project access check to execution time
                is_unified_tool = (
                    tool_name.startswith("wordpress_")
                    or tool_name.startswith("wordpress_advanced_")
                    or tool_name.startswith("woocommerce_")
                    or tool_name.startswith("gitea_")
                    or tool_name.startswith("mcp__coolify-projects__wordpress_")
                    or tool_name.startswith("mcp__coolify-projects__wordpress_advanced_")
                    or tool_name.startswith("mcp__coolify-projects__woocommerce_")
                    or tool_name.startswith("mcp__coolify-projects__gitea_")
                )

            logger.debug(
                f"Auth check: tool={tool_name}, project={project_id}, "
                f"scope={required_scope}, unified={is_unified_tool}, system={is_system_tool}"
            )

            # Try API key validation first (if it looks like an API key)
            key_id = None
            jwt_payload = None

            if token.startswith("cmp_"):
                # Skip project check for both unified tools AND system tools
                # - Unified tools: will validate at execution time
                # - System tools: will validate below that key is global
                skip_project_check = is_unified_tool or is_system_tool

                key_id = api_key_manager.validate_key(
                    token,
                    project_id=project_id,
                    required_scope=required_scope,
                    skip_project_check=skip_project_check,
                )

            elif not token.startswith("sk-"):  # Not master key format, might be JWT
                # Try OAuth JWT validation
                try:
                    import jwt as pyjwt

                    from core.oauth import get_token_manager

                    token_manager = get_token_manager()
                    jwt_payload = token_manager.validate_access_token(token)

                    # JWT validated successfully
                    logger.debug(f"OAuth JWT validated for tool {tool_name}")

                    # Extract scope from JWT and validate
                    jwt_scopes = jwt_payload.get("scope", "").split()

                    # Check if required scope is granted
                    if required_scope not in jwt_scopes and "admin" not in jwt_scopes:
                        logger.warning(
                            f"JWT scope insufficient: required={required_scope}, granted={jwt_scopes}"
                        )
                        raise ToolError(f"Insufficient scope: '{required_scope}' required")

                    # Store OAuth context (similar to API key context)
                    # Note: OAuth tokens can be scoped to specific projects
                    oauth_project_id = jwt_payload.get("project_id", "*")

                    set_api_key_context(
                        key_id=f"oauth_{jwt_payload.get('client_id')}",
                        project_id=oauth_project_id,
                        scope=" ".join(jwt_scopes),
                        is_global=oauth_project_id == "*",
                    )
                    logger.debug(
                        f"Stored OAuth context: client_id={jwt_payload.get('client_id')}, "
                        f"project_id={oauth_project_id}, scopes={jwt_scopes}"
                    )

                except pyjwt.ExpiredSignatureError:
                    logger.warning("JWT token expired")
                    raise ToolError("Authentication failed: Token expired")
                except pyjwt.InvalidTokenError as e:
                    logger.debug(f"Not a valid JWT token: {e}")
                    # Not a JWT, will try master key below
                    jwt_payload = None
                except Exception as e:
                    logger.warning(f"JWT validation error: {e}")
                    # Not a JWT, will try master key below
                    jwt_payload = None

            if key_id or jwt_payload:
                # API key or JWT validated successfully
                if key_id:
                    logger.debug(
                        f"API key {key_id} validated for tool {tool_name} (scope: {required_scope})"
                    )
                elif jwt_payload:
                    logger.debug(
                        f"OAuth JWT validated for tool {tool_name} (client_id: {jwt_payload.get('client_id')})"
                    )

                # Get full key info for context storage (skip for JWT)
                key = api_key_manager.keys.get(key_id) if key_id else None

                if key:
                    # Phase 5.5: Tool Visibility Filter
                    # Check if API key has visibility to this tool
                    if not check_tool_visibility(tool_name, key.project_id):
                        plugin_type = extract_plugin_type_from_tool(tool_name)
                        logger.warning(
                            f"Tool visibility denied: Key {key_id} (project: {key.project_id}) "
                            f"attempted to access {plugin_type or 'system'} tool: {tool_name}"
                        )
                        raise ToolError(
                            f"Access denied: Your API key does not have access to {plugin_type or 'system'} tools. "
                            f"Please use a global API key or the correct plugin-specific key."
                        )

                    # Additional check for system tools:
                    # System tools require global key (project_id="*")
                    if is_system_tool:
                        # Check if this is a global key
                        if key.project_id != "*":
                            logger.warning(
                                f"Key {key_id} (project: {key.project_id}) "
                                f"attempted to access system tool: {tool_name}"
                            )
                            raise ToolError("System tools require global API key (project_id='*')")

                    # Store API key info in context for unified handlers to check project access
                    # This enables per-project API keys to work correctly with unified tools
                    set_api_key_context(
                        key_id=key_id,
                        project_id=key.project_id,
                        scope=key.scope,
                        is_global=key.project_id == "*",
                    )
                    logger.debug(
                        f"Stored API key context: project_id={key.project_id}, is_global={key.project_id == '*'}"
                    )

            else:
                # Fallback to master key validation
                if not auth_manager.validate_master_key(token):
                    logger.warning("Request rejected: Invalid API key or master key")
                    raise ToolError("Authentication failed: Invalid API key")

                logger.debug(f"Master key validated for tool {tool_name}")

                # Set context for master key (global access)
                set_api_key_context(
                    key_id="master_key", project_id="*", scope="admin", is_global=True
                )
                logger.debug("Stored master key context: project_id=*, is_global=True")

            # Authentication successful - proceed
            return await call_next(context)

        except ToolError:
            # Re-raise ToolError as-is (already has proper message)
            raise
        except Exception as e:
            # Catch any unexpected errors during authentication
            logger.error(f"Authentication error: {e}", exc_info=True)
            raise ToolError(f"Authentication error: {str(e)}")

# Add authentication middleware to MCP server
mcp.add_middleware(UserAuthMiddleware())
logger.info("Authentication middleware enabled")

# === AUDIT LOGGING MIDDLEWARE ===

class AuditLoggingMiddleware(Middleware):
    """
    Middleware to log all tool calls for audit purposes.

    Logs tool name, parameters, duration, and results.
    Runs after authentication to ensure only valid calls are logged.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Log tool calls before and after execution.

        Args:
            context: Middleware context containing tool call information
            call_next: Next middleware or tool handler in the chain

        Returns:
            Result from the tool
        """
        # Access tool information from context.message.params
        tool_name = "unknown"
        tool_args = {}

        try:
            if hasattr(context, "message") and hasattr(context.message, "params"):
                params = context.message.params
                tool_name = params.name if hasattr(params, "name") else "unknown"
                tool_args = params.arguments if hasattr(params, "arguments") else {}
        except Exception as e:
            logger.warning(f"Failed to extract tool info from context: {e}")

        # Extract site info from unified tools
        site = tool_args.get("site") if "site" in tool_args else None

        # Extract project_id from per-site tools
        project_id = None
        if "_site" in tool_name or "_" in tool_name:
            # Per-site tool format: wordpress_site1_get_post
            parts = tool_name.split("_")
            if len(parts) >= 2 and parts[1].startswith("site"):
                project_id = f"{parts[0]}_{parts[1]}"

        start_time = time.time()
        error_msg = None
        result_summary = None

        try:
            # Call the tool
            result = await call_next(context)

            # Extract brief summary from result
            if isinstance(result, str):
                # Limit summary to first 100 characters
                result_summary = result[:100] + "..." if len(result) > 100 else result
            else:
                result_summary = f"Result type: {type(result).__name__}"

            return result

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log the tool call
            try:
                audit_logger.log_tool_call(
                    tool_name=tool_name,
                    site=site,
                    project_id=project_id,
                    params=tool_args,
                    result_summary=result_summary,
                    error=error_msg,
                    duration_ms=duration_ms,
                )
            except Exception as log_error:
                # Don't let logging errors break the tool call
                logger.error(f"Failed to log audit entry: {log_error}", exc_info=True)

# Add audit logging middleware to MCP server
mcp.add_middleware(AuditLoggingMiddleware())
logger.info("Audit logging middleware enabled")

# === RATE LIMITING (Phase 7.3) ===

# Initialize rate limiter
rate_limiter = get_rate_limiter()
logger.info("Rate limiter initialized (Phase 7.3)")

class RateLimitMiddleware(Middleware):
    """
    Middleware to enforce rate limiting for all tool calls (Phase 7.3).

    Uses Token Bucket algorithm to prevent API abuse with multi-level limits:
    - Per minute: 60 requests (default)
    - Per hour: 1000 requests (default)
    - Per day: 10000 requests (default)

    Runs after authentication to use client ID for tracking.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Check rate limits before allowing tool execution.

        Args:
            context: Middleware context containing tool call information
            call_next: Next middleware or tool handler in the chain

        Returns:
            Result from the tool if rate limit allows

        Raises:
            ToolError: If rate limit is exceeded
        """
        # Extract client ID from auth header
        client_id = "unknown"
        try:
            headers = get_http_headers()
            auth_header = headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                # Use the token as client ID (could hash for privacy in production)
                client_id = auth_header.removeprefix("Bearer ").strip()
        except Exception as e:
            logger.warning(f"Failed to extract client ID: {e}")

        # Extract tool information
        tool_name = "unknown"
        plugin_type = None
        try:
            if hasattr(context, "message") and hasattr(context.message, "params"):
                params = context.message.params
                tool_name = params.name if hasattr(params, "name") else "unknown"

                # Determine plugin type from tool name
                if tool_name.startswith("wordpress_") or tool_name.startswith(
                    "mcp__coolify-projects__wordpress_"
                ):
                    plugin_type = "wordpress"
                elif tool_name.startswith("woocommerce_"):
                    plugin_type = "woocommerce"
        except Exception as e:
            logger.warning(f"Failed to extract tool info: {e}")

        # Check rate limit
        allowed, message, retry_after = rate_limiter.check_rate_limit(
            client_id=client_id, tool_name=tool_name, plugin_type=plugin_type
        )

        if not allowed:
            # Log rejection via audit logger
            try:
                audit_logger.log_event(
                    event_type=EventType.SECURITY,
                    level=LogLevel.WARNING,
                    message=f"Rate limit exceeded for client {client_id[:8]}...",
                    metadata={
                        "tool_name": tool_name,
                        "plugin_type": plugin_type,
                        "reason": message,
                        "retry_after_seconds": retry_after,
                    },
                )
            except Exception as log_error:
                logger.error(f"Failed to log rate limit rejection: {log_error}")

            # Return error with retry-after information
            raise ToolError(f"{message}. Please retry after {int(retry_after)} seconds.")

        # Rate limit check passed - proceed with tool execution
        return await call_next(context)

# Add rate limiting middleware to MCP server
mcp.add_middleware(RateLimitMiddleware())
logger.info("Rate limiting middleware enabled (Phase 7.3)")

# === HEALTH MONITORING (Phase 7.2) ===

from core import initialize_health_monitor

# Initialize health monitor
health_monitor = initialize_health_monitor(
    project_manager=project_manager,
    audit_logger=audit_logger,
    metrics_retention_hours=24,
    max_metrics_per_project=1000,
)
logger.info("Health monitor initialized (Phase 7.2)")

class HealthMetricsMiddleware(Middleware):
    """
    Middleware to track health metrics for all tool calls (Phase 7.2).

    Tracks:
    - Response time
    - Success/failure rate
    - Error messages
    - Project-specific metrics
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Track health metrics for tool calls.

        Args:
            context: Middleware context containing tool call information
            call_next: Next middleware or tool handler in the chain

        Returns:
            Result from the tool
        """
        # Extract tool information
        tool_name = "unknown"
        tool_args = {}
        project_id = None

        try:
            if hasattr(context, "message") and hasattr(context.message, "params"):
                params = context.message.params
                tool_name = params.name if hasattr(params, "name") else "unknown"
                tool_args = params.arguments if hasattr(params, "arguments") else {}
        except Exception as e:
            logger.warning(f"Failed to extract tool info: {e}")

        # Extract project_id from unified tools (site parameter)
        if "site" in tool_args:
            site = tool_args["site"]
            # Resolve alias to full_id using site_manager
            try:
                # Try to determine plugin type from tool name
                plugin_type = tool_name.split("_")[0] if "_" in tool_name else "wordpress"
                site_config = site_manager.get_site_config(plugin_type, site)
                project_id = site_config.get_full_id()
            except (ValueError, Exception):
                # Fallback to site value if resolution fails
                pass

        # Extract project_id from per-site tools (tool name)
        if not project_id and "_" in tool_name:
            parts = tool_name.split("_")
            if len(parts) >= 2 and parts[1].startswith("site"):
                project_id = f"{parts[0]}_{parts[1]}"

        # Skip tracking for system tools (no project_id)
        if not project_id:
            return await call_next(context)

        # Track metrics
        start_time = time.time()
        error_msg = None
        success = False

        try:
            result = await call_next(context)
            success = True
            return result

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000

            # Record metric
            try:
                health_monitor.record_request(
                    project_id=project_id,
                    response_time_ms=response_time_ms,
                    success=success,
                    error_message=error_msg,
                )
            except Exception as metric_error:
                # Don't let metrics tracking errors break the tool call
                logger.error(f"Failed to record health metric: {metric_error}", exc_info=True)

# Add health metrics middleware
mcp.add_middleware(HealthMetricsMiddleware())
logger.info("Health metrics middleware enabled (Phase 7.2)")

# === ENDPOINT MIDDLEWARE HELPER ===

def add_endpoint_middleware(endpoint_mcp, endpoint_name: str = "unknown"):
    """
    Add authentication, audit, and rate limiting middleware to an endpoint.

    This ensures all sub-endpoints (plugin type and per-project) have proper
    authentication just like the main /mcp endpoint.

    Args:
        endpoint_mcp: FastMCP instance to add middleware to
        endpoint_name: Name for logging purposes
    """
    endpoint_mcp.add_middleware(UserAuthMiddleware())
    endpoint_mcp.add_middleware(AuditLoggingMiddleware())
    endpoint_mcp.add_middleware(RateLimitMiddleware())
    logger.debug(f"Added auth/audit/rate-limit middleware to {endpoint_name} endpoint")

# === SYSTEM TOOLS ===

# Internal implementation functions (not decorated) for system tools
async def _list_projects_impl() -> str:
    """Internal implementation for listing projects."""
    try:
        projects = project_manager.list_projects()
        result = {"total": len(projects), "projects": projects}
        import json

        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing projects: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def list_projects() -> str:
    """
    List all discovered projects.

    Returns information about all projects that have been configured
    through environment variables.

    Returns:
        JSON string with list of projects
    """
    return await _list_projects_impl()

# Phase K.2.3: Helper for site discovery in plugin endpoints
async def _list_sites_impl(plugin_type: str) -> str:
    """
    Internal implementation for listing available sites for a plugin type.

    Args:
        plugin_type: Type of plugin (wordpress, woocommerce, wordpress_advanced)

    Returns:
        JSON string with list of available sites
    """
    import json

    try:
        # Normalize plugin type (wordpress_advanced -> wordpress for site lookup)
        lookup_type = "wordpress" if plugin_type == "wordpress_advanced" else plugin_type
        sites = site_manager.get_sites_by_type(lookup_type)

        result = {"plugin_type": plugin_type, "total": len(sites), "sites": []}

        for site in sites:
            site_info = {"site": site.alias or site.url, "url": site.url, "alias": site.alias}
            result["sites"].append(site_info)

        if not sites:
            result["message"] = f"No {plugin_type} sites configured. Check environment variables."
        else:
            result["message"] = (
                f"Found {len(sites)} {plugin_type} site(s). Use any 'site' value as the site parameter."
            )

        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing sites for {plugin_type}: {e}", exc_info=True)
        return json.dumps(
            {"error": str(e), "message": f"Failed to list {plugin_type} sites"}, indent=2
        )

@mcp.tool()
async def get_project_info(project_id: str) -> str:
    """
    Get detailed information about a specific project.

    Args:
        project_id: Full project identifier (e.g., 'wordpress_site1')

    Returns:
        JSON string with project information
    """
    try:
        info = project_manager.get_project_info(project_id)

        if info is None:
            return f"Project '{project_id}' not found. Use list_projects to see available projects."

        import json

        return json.dumps(info, indent=2)
    except Exception as e:
        logger.error(f"Error getting project info: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def check_all_projects_health() -> str:
    """
    Check health status of all projects with enhanced metrics (Phase 7.2).

    Performs comprehensive health checks on all configured projects including:
    - Accessibility and response time
    - Error rates and recent failures
    - Alert threshold violations
    - Historical metrics (last hour)

    Returns:
        JSON string with detailed health status and metrics
    """
    try:
        # Use enhanced health monitor
        health_data = await health_monitor.check_all_projects_health(include_metrics=True)

        import json

        return json.dumps(health_data, indent=2)
    except Exception as e:
        logger.error(f"Error checking health: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def get_project_health(project_id: str) -> str:
    """
    Get detailed health information for a specific project (Phase 7.2).

    Args:
        project_id: Full project identifier (e.g., "wordpress_site1")

    Returns:
        JSON string with comprehensive health metrics including:
        - Current health status
        - Response time statistics
        - Error rate (last hour)
        - Recent errors
        - Active alerts
    """
    try:
        status = await health_monitor.check_project_health(project_id, include_metrics=True)

        import json

        return json.dumps(status.to_dict(), indent=2)
    except Exception as e:
        logger.error(f"Error getting project health: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def get_system_metrics() -> str:
    """
    Get overall MCP server metrics and statistics (Phase 7.2).

    Returns system-wide metrics including:
    - Uptime
    - Total requests (success/failure)
    - Average response time
    - Error rate percentage
    - Requests per minute

    Returns:
        JSON string with system metrics
    """
    try:
        metrics = health_monitor.get_system_metrics()

        import json

        return json.dumps(metrics.to_dict(), indent=2)
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def get_system_uptime() -> str:
    """
    Get MCP server uptime information (Phase 7.2).

    Returns:
        JSON string with uptime in various formats (seconds, minutes, hours, days)
    """
    try:
        uptime = health_monitor.get_uptime()

        import json

        return json.dumps(uptime, indent=2)
    except Exception as e:
        logger.error(f"Error getting uptime: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def get_project_metrics(project_id: str, hours: int = 1) -> str:
    """
    Get historical metrics for a specific project (Phase 7.2).

    Args:
        project_id: Full project identifier (e.g., "wordpress_site1")
        hours: Number of hours of history to analyze (default: 1, max: 24)

    Returns:
        JSON string with historical metrics including:
        - Request counts and success/failure rates
        - Response time statistics (min/avg/max)
        - Error rate over time
        - Recent error messages
    """
    try:
        # Limit to 24 hours max
        hours = min(hours, 24)

        metrics = health_monitor.get_project_metrics(project_id, hours=hours)

        import json

        return json.dumps(metrics, indent=2)
    except Exception as e:
        logger.error(f"Error getting project metrics: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def export_health_metrics(output_path: str = "logs/metrics_export.json") -> str:
    """
    Export all health metrics to a JSON file (Phase 7.2).

    Args:
        output_path: Path to output file (default: logs/metrics_export.json)

    Returns:
        Path to exported file
    """
    try:
        exported_path = health_monitor.export_metrics(output_path=output_path, format="json")
        return f"Metrics exported successfully to: {exported_path}"
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}", exc_info=True)
        return f"Error: {str(e)}"

# Internal implementations for rate limiting tools
async def _get_rate_limit_stats_impl(client_id: str = None) -> str:
    """Internal implementation for getting rate limit stats."""
    try:
        import json

        if client_id:
            stats = rate_limiter.get_client_stats(client_id)
            if stats is None:
                return f"No rate limit data found for client: {client_id}"
            return json.dumps(stats, indent=2)
        else:
            stats = rate_limiter.get_all_stats()
            return json.dumps(stats, indent=2)
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {e}", exc_info=True)
        return f"Error: {str(e)}"

async def _reset_rate_limit_impl(client_id: str = None) -> str:
    """Internal implementation for resetting rate limit."""
    try:
        if client_id:
            success = rate_limiter.reset_client(client_id)
            if success:
                return f"Rate limit state reset successfully for client: {client_id[:8]}..."
            else:
                return f"Client not found: {client_id}"
        else:
            count = rate_limiter.reset_all()
            return f"Rate limit state reset successfully for {count} client(s)"
    except Exception as e:
        logger.error(f"Error resetting rate limit: {e}", exc_info=True)
        return f"Error: {str(e)}"

@mcp.tool()
async def get_rate_limit_stats(client_id: str = None) -> str:
    """
    Get rate limiting statistics (Phase 7.3).

    Args:
        client_id: Optional client identifier to get specific client stats.
                   If not provided, returns global statistics for all clients.

    Returns:
        JSON string with rate limit statistics
    """
    return await _get_rate_limit_stats_impl(client_id)

@mcp.tool()
async def reset_rate_limit(client_id: str = None) -> str:
    """
    Reset rate limit state for a client or all clients (Phase 7.3).

    CAUTION: This is an administrative tool. Use with care.

    Args:
        client_id: Optional client identifier to reset.
                   If not provided, resets ALL clients.

    Returns:
        Confirmation message with number of clients reset
    """
    return await _reset_rate_limit_impl(client_id)

# === DYNAMIC TOOL REGISTRATION ===

def create_dynamic_tool(name: str, description: str, handler, input_schema: dict):
    """
    Create a dynamic tool wrapper that works with FastMCP's decorator pattern.

    Args:
        name: Tool name
        description: Tool description
        handler: The async function to call
        input_schema: JSON schema for input parameters

    Returns:
        Wrapped async function compatible with FastMCP
    """
    import inspect

    # Build function signature dynamically from input schema
    # FastMCP requires explicit parameters, not **kwargs

    params = []
    annotations = {}

    if input_schema and "properties" in input_schema:
        required_params = input_schema.get("required", [])

        for param_name, param_info in input_schema["properties"].items():
            # Map JSON schema types to Python types
            param_type = param_info.get("type", "string")

            if param_type == "string":
                py_type = str
            elif param_type == "integer":
                py_type = int
            elif param_type == "boolean":
                py_type = bool
            elif param_type == "array":
                py_type = list
            elif param_type == "object":
                py_type = dict
            else:
                py_type = str  # Default to string

            # If parameter is not required or has a default, make it Optional
            is_required = param_name in required_params
            has_default = "default" in param_info

            if not is_required or has_default:
                annotations[param_name] = Optional[py_type]
                default_value = param_info.get("default", None)
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

    # Create signature
    sig = inspect.Signature(params)

    # Create wrapper function with dynamic signature
    # We need to use exec to create a function with the right signature
    param_names = [p.name for p in params]
    param_str = ", ".join(param_names)

    # Build the function code
    func_code = f"""
async def {name}({param_str}):
    '''
{description}
    '''
    kwargs = {{{', '.join(f'"{p}": {p}' for p in param_names)}}}
    return await handler(**kwargs)
"""

    # Execute the code to create the function
    local_vars = {"handler": handler}
    exec(func_code, local_vars)
    dynamic_wrapper = local_vars[name]

    # Attach the correct signature so FastMCP/Pydantic identify optional parameters.
    # Without this, all parameters appear required because the exec'd function
    # has no default values in its code object.
    dynamic_wrapper.__signature__ = sig

    # Set annotations
    annotations["return"] = str  # All our tools return strings
    dynamic_wrapper.__annotations__ = annotations

    return dynamic_wrapper

def register_project_tools():
    """
    Dynamically register all project tools from plugins.

    This function is called at startup to register all tools
    from all discovered projects.

    Option B Architecture (Phase 3 Complete):
    - Uses ToolRegistry for centralized tool management
    - Uses ToolGenerator for WordPress plugin (refactored in Phase 3)
    - Type-safe with Pydantic models in ToolRegistry
    - Tool specifications from plugin.get_tool_specifications()

    Note: FastMCP requires using the @mcp.tool() decorator or mcp.tool(function)
    for tool registration.
    """
    logger.info("=" * 60)
    logger.info("TOOL REGISTRATION - Option B Architecture (Phase 3)")
    logger.info("=" * 60)

    # Phase 3: Use ToolGenerator for refactored plugins
    logger.info("Generating tools with ToolGenerator...")

    from plugins.wordpress.plugin import WordPressPlugin

    # Generate tools for WordPress (refactored in Phase 3)
    logger.info("Generating WordPress tools from plugin specifications...")
    try:
        wordpress_tools = tool_generator.generate_tools(WordPressPlugin, "wordpress")
        logger.info(f"Generated {len(wordpress_tools)} WordPress tools from ToolGenerator")

        # Register WordPress tools in ToolRegistry
        for tool_def in wordpress_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register WordPress tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate WordPress tools: {e}", exc_info=True)

    # Generate tools for WooCommerce (Phase D.1 - Split from WordPress Core)
    logger.info("Generating WooCommerce tools from plugin specifications...")
    try:
        from plugins.woocommerce.plugin import WooCommercePlugin

        woocommerce_tools = tool_generator.generate_tools(WooCommercePlugin, "woocommerce")
        logger.info(f"Generated {len(woocommerce_tools)} WooCommerce tools from ToolGenerator")

        # Register WooCommerce tools in ToolRegistry
        for tool_def in woocommerce_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register WooCommerce tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate WooCommerce tools: {e}", exc_info=True)

    # Generate tools for WordPress Advanced (Phase D - Separated plugin)
    logger.info("Generating WordPress Advanced tools from plugin specifications...")
    try:
        from plugins.wordpress_advanced.plugin import WordPressAdvancedPlugin

        wordpress_advanced_tools = tool_generator.generate_tools(
            WordPressAdvancedPlugin, "wordpress_advanced"
        )
        logger.info(
            f"Generated {len(wordpress_advanced_tools)} WordPress Advanced tools from ToolGenerator"
        )

        # Register WordPress Advanced tools in ToolRegistry
        for tool_def in wordpress_advanced_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register WordPress Advanced tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate WordPress Advanced tools: {e}", exc_info=True)

    # Generate tools for Gitea (Phase C)
    logger.info("Generating Gitea tools from plugin specifications...")
    try:
        from plugins.gitea.plugin import GiteaPlugin

        gitea_tools = tool_generator.generate_tools(GiteaPlugin, "gitea")
        logger.info(f"Generated {len(gitea_tools)} Gitea tools from ToolGenerator")

        # Register Gitea tools in ToolRegistry
        for tool_def in gitea_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register Gitea tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate Gitea tools: {e}", exc_info=True)

    # Generate tools for n8n (Phase F)
    logger.info("Generating n8n tools from plugin specifications...")
    try:
        from plugins.n8n.plugin import N8nPlugin

        n8n_tools = tool_generator.generate_tools(N8nPlugin, "n8n")
        logger.info(f"Generated {len(n8n_tools)} n8n tools from ToolGenerator")

        # Register n8n tools in ToolRegistry
        for tool_def in n8n_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register n8n tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate n8n tools: {e}", exc_info=True)

    # Generate tools for Supabase (Phase G - Self-Hosted)
    logger.info("Generating Supabase tools from plugin specifications...")
    try:
        from plugins.supabase.plugin import SupabasePlugin

        supabase_tools = tool_generator.generate_tools(SupabasePlugin, "supabase")
        logger.info(f"Generated {len(supabase_tools)} Supabase tools from ToolGenerator")

        # Register Supabase tools in ToolRegistry
        for tool_def in supabase_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register Supabase tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate Supabase tools: {e}", exc_info=True)

    # Generate tools for OpenPanel (Phase H - Product Analytics)
    logger.info("Generating OpenPanel tools from plugin specifications...")
    try:
        from plugins.openpanel.plugin import OpenPanelPlugin

        openpanel_tools = tool_generator.generate_tools(OpenPanelPlugin, "openpanel")
        logger.info(f"Generated {len(openpanel_tools)} OpenPanel tools from ToolGenerator")

        # Register OpenPanel tools in ToolRegistry
        for tool_def in openpanel_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register OpenPanel tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate OpenPanel tools: {e}", exc_info=True)

    # Generate tools for Appwrite (Phase I - Backend-as-a-Service)
    logger.info("Generating Appwrite tools from plugin specifications...")
    try:
        from plugins.appwrite.plugin import AppwritePlugin

        appwrite_tools = tool_generator.generate_tools(AppwritePlugin, "appwrite")
        logger.info(f"Generated {len(appwrite_tools)} Appwrite tools from ToolGenerator")

        # Register Appwrite tools in ToolRegistry
        for tool_def in appwrite_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register Appwrite tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate Appwrite tools: {e}", exc_info=True)

    # Generate tools for Directus (Phase J - Headless CMS)
    logger.info("Generating Directus tools from plugin specifications...")
    try:
        from plugins.directus.plugin import DirectusPlugin

        directus_tools = tool_generator.generate_tools(DirectusPlugin, "directus")
        logger.info(f"Generated {len(directus_tools)} Directus tools from ToolGenerator")

        # Register Directus tools in ToolRegistry
        for tool_def in directus_tools:
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.error(f"Failed to register Directus tool {tool_def.name}: {e}")

    except Exception as e:
        logger.error(f"Failed to generate Directus tools: {e}", exc_info=True)

    logger.info(f"Registered {tool_registry.get_count()} tools in ToolRegistry")

    # Register tools with FastMCP
    logger.info("Registering tools with FastMCP...")
    fastmcp_count = 0

    for tool_def in tool_registry.get_all():
        try:
            # Create a wrapper function compatible with FastMCP
            wrapped_tool = create_dynamic_tool(
                tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
            )

            # Register with FastMCP
            mcp.tool()(wrapped_tool)

            fastmcp_count += 1
            logger.debug(f"Registered tool with FastMCP: {tool_def.name}")

        except Exception as e:
            logger.error(f"Error registering tool {tool_def.name} with FastMCP: {e}", exc_info=True)

    logger.info(f"Registered {fastmcp_count} tools with FastMCP")

    # Tool count breakdown
    tool_counts = tool_registry.get_count_by_plugin()
    logger.info("Tool count by plugin:")
    for plugin_type, count in tool_counts.items():
        logger.info(f"  - {plugin_type}: {count} tools")

    logger.info("=" * 60)

    # System tools count (Phase 7.2 + 7.3 + API Keys):
    # - 10 system/health/rate limit tools
    # - 6 API key management tools
    system_tools_count = 16

    total_tools = tool_registry.get_count() + system_tools_count
    logger.info(
        f"Total tools available: {total_tools} ({tool_registry.get_count()} plugin + {system_tools_count} system)"
    )
    logger.info("🎯 Option B Architecture: Tool count stays constant regardless of site count!")

    return total_tools

# Register all project tools at startup
_total_tool_count = register_project_tools()

# === OAUTH 2.1 ENDPOINTS ===

from urllib.parse import urlencode

from core.oauth import OAuthError, get_oauth_server

oauth_server = get_oauth_server()

def get_oauth_base_url(request: Request) -> str:
    """
    Get the correct base URL for OAuth endpoints.

    Priority: OAUTH_BASE_URL env var > X-Forwarded headers > request.base_url

    This ensures consistency across all OAuth metadata endpoints,
    especially when behind a reverse proxy (like Coolify/Traefik).
    """
    oauth_base_url = os.getenv("OAUTH_BASE_URL")
    if oauth_base_url:
        return oauth_base_url.rstrip("/")

    # Check X-Forwarded headers (for reverse proxy/Coolify)
    x_forwarded_proto = request.headers.get("x-forwarded-proto", "http")
    x_forwarded_host = request.headers.get("x-forwarded-host")

    if x_forwarded_host:
        return f"{x_forwarded_proto}://{x_forwarded_host}"

    return str(request.base_url).rstrip("/")

@mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
async def oauth_metadata(request: Request) -> JSONResponse:
    """
    OAuth 2.0 Authorization Server Metadata (RFC 8414)

    Returns OAuth configuration for client discovery.
    This endpoint allows clients (like Claude Desktop, OpenAI) to discover
    the OAuth implementation and its capabilities.

    Returns:
        JSONResponse with OAuth metadata
    """
    base_url = get_oauth_base_url(request)

    metadata = {
        # RFC 8414 Required Fields
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "registration_endpoint": f"{base_url}/oauth/register",  # RFC 7591 (requires auth)
        # Supported Features
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
        "code_challenge_methods_supported": ["S256"],  # PKCE mandatory
        "scopes_supported": ["read", "write", "admin"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        # Token Configuration
        "revocation_endpoint_auth_methods_supported": ["client_secret_post"],
        "introspection_endpoint_auth_methods_supported": ["client_secret_post"],
        # Additional OAuth 2.1 Features
        "response_modes_supported": ["query"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256", "RS256"],
        # Custom MCP Extensions
        "mcp_version": "1.0",
        "mcp_oauth_enabled": True,
        "service_documentation": f"{base_url}/docs/OAUTH_GUIDE.md",
        # Security Model
        "registration_endpoint_requires_auth": False,  # Open registration
        "authorization_endpoint_auth_mode": OAUTH_AUTH_MODE,  # Current auth mode
        "authorization_endpoint_auth_method": "api_key",  # Query parameter: api_key=xxx
        "authorization_endpoint_auth_param": "api_key",  # Parameter name
        "authorization_endpoint_trusted_domains": (
            OAUTH_TRUSTED_DOMAINS if OAUTH_AUTH_MODE == "trusted_domains" else []
        ),
        "oauth_token_inherits_api_key_scope": True,  # OAuth tokens inherit API Key permissions
    }

    return JSONResponse(metadata)

@mcp.custom_route("/mcp/.well-known/oauth-authorization-server", methods=["GET"])
async def oauth_metadata_mcp_path(request: Request) -> JSONResponse:
    """
    OAuth metadata endpoint for /mcp base path.

    Some clients may look for metadata at /mcp/.well-known/oauth-authorization-server
    when the MCP server is mounted at /mcp.
    """
    return await oauth_metadata(request)

@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def oauth_protected_resource(request: Request) -> JSONResponse:
    """
    OAuth 2.0 Protected Resource Metadata (RFC 9728)

    Returns metadata about this protected resource server.
    Some OAuth clients look for this endpoint.
    """
    base_url = get_oauth_base_url(request)

    metadata = {
        "resource": base_url,
        "authorization_servers": [base_url],
        "scopes_supported": ["read", "write", "admin"],
        "bearer_methods_supported": ["header"],
        "resource_signing_alg_values_supported": ["HS256", "RS256"],
    }

    return JSONResponse(metadata)

async def oauth_protected_resource_path(request: Request) -> JSONResponse:
    """
    OAuth 2.0 Protected Resource Metadata for path-specific requests (RFC 9728)

    Claude MCP client first tries path-specific metadata endpoints like:
    /.well-known/oauth-protected-resource/project/javadpoor/mcp

    This handler catches these requests and returns the same metadata as the root endpoint.
    """
    base_url = get_oauth_base_url(request)

    metadata = {
        "resource": base_url,
        "authorization_servers": [base_url],
        "scopes_supported": ["read", "write", "admin"],
        "bearer_methods_supported": ["header"],
        "resource_signing_alg_values_supported": ["HS256", "RS256"],
    }

    return JSONResponse(metadata)

@mcp.custom_route("/oauth/register", methods=["POST"])
async def oauth_register(request: Request) -> JSONResponse:
    """
    OAuth 2.0 Dynamic Client Registration (RFC 7591)

    🔓 SECURITY MODEL: Open DCR for Trusted Clients (MCP Spec Compliant)

    This endpoint supports Dynamic Client Registration as required by MCP specification.

    **Two Authentication Modes:**

    1. **Open DCR (No Auth Required)**: For trusted MCP clients (Claude, ChatGPT)
       - redirect_uri must match DCR_ALLOWED_REDIRECT_PATTERNS
       - Rate limited per IP address
       - Audit logged

    2. **Protected DCR (Master API Key Required)**: For custom redirect_uris
       - Master API Key in Authorization header
       - No rate limiting
       - Full access

    **Security Layers:**
    - DCR only provides client_id/secret (entry to "waiting room")
    - User must still provide valid API Key in /oauth/authorize
    - OAuth token inherits API Key's permissions (project_id, scope)

    **Flow:**
    1. MCP Client (Claude) → DCR → Gets client_id + secret
    2. User redirected to /oauth/authorize → Enters API Key
    3. API Key validated → Authorization code issued
    4. Token exchange → Token inherits API Key permissions

    Request Body (JSON):
        {
            "client_name": "My Application",
            "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "scope": "read write",
            "token_endpoint_auth_method": "client_secret_post"
        }

    Returns:
        {
            "client_id": "cmp_client_xxx",
            "client_secret": "secret_xxx",
            "client_id_issued_at": 1234567890,
            "client_secret_expires_at": 0,
            "client_name": "My Application",
            "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_method": "client_secret_post"
        }
    """
    try:
        from core.oauth import get_client_registry

        client_ip = request.client.host if request.client else "unknown"

        # ========================================
        # Parse request body FIRST (needed for auth decision)
        # ========================================
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Invalid JSON in request body"},
                status_code=400,
            )

        # Validate required fields
        if "redirect_uris" not in body:
            return JSONResponse(
                {"error": "invalid_redirect_uri", "error_description": "redirect_uris is required"},
                status_code=400,
            )

        redirect_uris = body.get("redirect_uris", [])

        # Validate redirect URIs format
        if not redirect_uris or not isinstance(redirect_uris, list):
            return JSONResponse(
                {
                    "error": "invalid_redirect_uri",
                    "error_description": "redirect_uris must be a non-empty array",
                },
                status_code=400,
            )

        # ========================================
        # SECURITY: Determine Authentication Mode
        # ========================================
        # Check if redirect_uris are in the allowlist for open DCR
        is_open_dcr_allowed = is_redirect_uri_allowed_for_open_dcr(redirect_uris)

        auth_header = request.headers.get("Authorization", "")
        api_key = None

        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        elif "api_key" in request.query_params:
            api_key = request.query_params["api_key"]

        has_valid_master_key = api_key and auth_manager.validate_master_key(api_key)

        # Decide authentication mode
        if is_open_dcr_allowed:
            # ========================================
            # Open DCR Mode (Claude, ChatGPT, etc.)
            # ========================================
            # Check rate limiting
            rate_ok, rate_error = check_dcr_rate_limit(client_ip)
            if not rate_ok:
                logger.warning(f"DCR rate limit exceeded for {client_ip}: {rate_error}")
                return JSONResponse(
                    {"error": "too_many_requests", "error_description": rate_error}, status_code=429
                )

            logger.info(
                f"Open DCR registration from {client_ip} for redirect_uris: {redirect_uris}"
            )

            # Audit log for open DCR
            audit_logger.log_event(
                event_type="oauth_dcr_open",
                details={
                    "client_ip": client_ip,
                    "redirect_uris": redirect_uris,
                    "client_name": body.get("client_name", "Unnamed Client"),
                    "auth_mode": "open_dcr",
                },
            )

        elif has_valid_master_key:
            # ========================================
            # Protected DCR Mode (Master API Key)
            # ========================================
            logger.info(f"Protected DCR registration from {client_ip} with Master API Key")

            # Audit log for protected DCR
            audit_logger.log_event(
                event_type="oauth_dcr_protected",
                details={
                    "client_ip": client_ip,
                    "redirect_uris": redirect_uris,
                    "client_name": body.get("client_name", "Unnamed Client"),
                    "auth_mode": "master_key",
                },
            )

        else:
            # ========================================
            # Unauthorized: redirect_uri not in allowlist AND no Master Key
            # ========================================
            logger.warning(
                f"Unauthorized DCR attempt from {client_ip}: "
                f"redirect_uris {redirect_uris} not in allowlist and no valid Master API Key"
            )
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": (
                        "Dynamic Client Registration requires either: "
                        "1) redirect_uri from trusted MCP clients (Claude, ChatGPT), or "
                        "2) Master API Key in Authorization header. "
                        f"Your redirect_uris {redirect_uris} are not in the allowlist."
                    ),
                },
                status_code=401,
            )

        # ========================================
        # Extract fields with defaults
        # ========================================
        client_name = body.get("client_name", "Unnamed Client")
        grant_types = body.get("grant_types", ["authorization_code", "refresh_token"])
        scope = body.get("scope", "read write")
        token_endpoint_auth_method = body.get("token_endpoint_auth_method", "client_secret_post")

        # Convert scope string to list
        if isinstance(scope, str):
            allowed_scopes = scope.split()
        else:
            allowed_scopes = scope

        logger.info(f"OAuth client registration: {client_name} with redirect_uris: {redirect_uris}")

        # Register client
        client_registry = get_client_registry()

        client_id, client_secret = client_registry.create_client(
            client_name=client_name,
            redirect_uris=redirect_uris,
            grant_types=grant_types,
            allowed_scopes=allowed_scopes,
            metadata={
                "registered_via": "dynamic_client_registration",
                "token_endpoint_auth_method": token_endpoint_auth_method,
            },
        )

        # Get client info
        client_registry.get_client(client_id)

        logger.info(f"Dynamic client registration: {client_id} ({client_name})")

        # Return RFC 7591 compliant response
        import time

        response = {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_id_issued_at": int(time.time()),
            "client_secret_expires_at": 0,  # Never expires
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "grant_types": grant_types,
            "response_types": ["code"],
            "token_endpoint_auth_method": token_endpoint_auth_method,
            "scope": " ".join(allowed_scopes),
        }

        return JSONResponse(response, status_code=201)

    except Exception as e:
        logger.error(f"Error in dynamic client registration: {e}", exc_info=True)
        return JSONResponse({"error": "server_error", "error_description": str(e)}, status_code=500)

@mcp.custom_route("/oauth/authorize", methods=["GET"])
async def oauth_authorize(request: Request):
    """
    OAuth 2.1 authorization endpoint - Phase E Web UI.

    Displays an HTML authorization page where users can enter their API Key.

    Query Parameters:
        client_id: OAuth client ID
        redirect_uri: Callback URI for authorization code
        response_type: Must be "code" (OAuth 2.1)
        code_challenge: PKCE code challenge (S256)
        code_challenge_method: Must be "S256"
        scope: Optional requested scopes (space-separated)
        state: Optional CSRF protection token

    Returns:
        HTML authorization page
    """
    try:
        # Get query parameters
        params = dict(request.query_params)

        # Validate basic OAuth parameters
        required = [
            "client_id",
            "redirect_uri",
            "response_type",
            "code_challenge",
            "code_challenge_method",
        ]
        missing = [p for p in required if p not in params]
        if missing:
            raise OAuthError(
                error="invalid_request",
                error_description=f"Missing parameters: {', '.join(missing)}",
            )

        # Validate authorization request
        validated = oauth_server.validate_authorization_request(
            client_id=params["client_id"],
            redirect_uri=params["redirect_uri"],
            response_type=params["response_type"],
            code_challenge=params["code_challenge"],
            code_challenge_method=params["code_challenge_method"],
            scope=params.get("scope"),
            state=params.get("state"),
        )

        # Generate CSRF token
        csrf_token = csrf_manager.generate_token()

        # Get client info
        from core.oauth import get_client_registry

        client_registry = get_client_registry()
        client = client_registry.get_client(validated["client_id"])
        client_name = client.client_name if client else validated["client_id"]

        # Parse requested scopes
        scopes = validated["scope"].split() if validated["scope"] else []

        # Detect language (Phase E - Multi-language support)
        accept_language = request.headers.get("accept-language")
        query_lang = params.get("lang")
        lang = detect_language(accept_language, query_lang)
        translations = get_all_translations(lang)

        # Render authorization page
        logger.info(
            f"Rendering authorization page for client_id={validated['client_id']}, lang={lang}"
        )

        return templates.TemplateResponse(
            "oauth/authorize.html",
            {
                "request": request,
                "client_id": validated["client_id"],
                "client_name": client_name,
                "redirect_uri": validated["redirect_uri"],
                "response_type": params["response_type"],  # from original params, not validated
                "code_challenge": validated["code_challenge"],
                "code_challenge_method": validated["code_challenge_method"],
                "scope": validated["scope"],
                "scopes": scopes,
                "state": validated.get("state", ""),
                "csrf_token": csrf_token,
                "lang": lang,  # Language code (en/fa)
                "t": translations,  # All translations for this language
            },
        )

    except OAuthError as e:
        # Render error page
        logger.warning(f"OAuth error: {e.error} - {e.error_description}")

        # Detect language for error page
        accept_language = request.headers.get("accept-language")
        query_lang = params.get("lang") if "params" in locals() else None
        lang = detect_language(accept_language, query_lang)
        translations = get_all_translations(lang)

        return templates.TemplateResponse(
            "oauth/error.html",
            {
                "request": request,
                "error": e.error,
                "error_description": e.error_description,
                "redirect_uri": params.get("redirect_uri") if "params" in locals() else None,
                "state": params.get("state") if "params" in locals() else None,
                "lang": lang,
                "t": translations,
            },
            status_code=e.status_code,
        )

    except Exception as e:
        logger.error(f"OAuth authorize error: {e}", exc_info=True)

        # Detect language for error page
        accept_language = request.headers.get("accept-language")
        query_lang = params.get("lang") if "params" in locals() else None
        lang = detect_language(accept_language, query_lang)
        translations = get_all_translations(lang)

        # For unexpected errors, render error page
        return templates.TemplateResponse(
            "oauth/error.html",
            {
                "request": request,
                "error": "server_error",
                "error_description": str(e),
                "redirect_uri": params.get("redirect_uri") if "params" in locals() else None,
                "state": params.get("state") if "params" in locals() else None,
                "lang": lang,
                "t": translations,
            },
            status_code=500,
        )

@mcp.custom_route("/oauth/authorize/confirm", methods=["POST"])
async def oauth_authorize_confirm(request: Request):
    """
    OAuth 2.1 authorization confirmation endpoint - Phase E.

    Handles form submission from the authorization page.
    Validates API Key and creates authorization code.

    Form Parameters:
        client_id, redirect_uri, response_type, code_challenge, code_challenge_method, scope, state
        csrf_token: CSRF protection token
        api_key: User's API Key
        action: "approve" or "deny"

    Returns:
        Redirect to redirect_uri with authorization code or error
    """
    try:
        # Parse form data
        form = await request.form()
        params = dict(form)

        # Validate action
        action = params.get("action")
        if action == "deny":
            # User denied authorization
            error_params = {
                "error": "access_denied",
                "error_description": "User denied authorization",
            }
            if params.get("state"):
                error_params["state"] = params["state"]

            error_url = f"{params['redirect_uri']}?{urlencode(error_params)}"
            logger.info(f"User denied authorization, redirecting to {error_url}")
            return RedirectResponse(url=error_url, status_code=302)

        # Validate CSRF token
        csrf_token = params.get("csrf_token")
        if not csrf_token or not csrf_manager.validate_token(csrf_token, consume=True):
            raise OAuthError(
                error="invalid_request",
                error_description="Invalid or expired CSRF token. Please try again.",
            )

        # Validate basic OAuth parameters
        required = [
            "client_id",
            "redirect_uri",
            "response_type",
            "code_challenge",
            "code_challenge_method",
        ]
        missing = [p for p in required if p not in params]
        if missing:
            raise OAuthError(
                error="invalid_request",
                error_description=f"Missing parameters: {', '.join(missing)}",
            )

        # Validate authorization request
        validated = oauth_server.validate_authorization_request(
            client_id=params["client_id"],
            redirect_uri=params["redirect_uri"],
            response_type=params["response_type"],
            code_challenge=params["code_challenge"],
            code_challenge_method=params["code_challenge_method"],
            scope=params.get("scope"),
            state=params.get("state"),
        )

        # Validate API Key
        api_key = params.get("api_key")
        if not api_key:
            raise OAuthError(error="invalid_request", error_description="API Key is required")

        api_key_id = None
        api_key_project_id = None
        api_key_scope = None
        granted_scope = validated["scope"]

        try:
            # Try as regular API key first
            if api_key.startswith("cmp_"):
                # Validate without project/scope check (we'll use its values)
                key_id = api_key_manager.validate_key(
                    api_key,
                    project_id="*",  # Skip project check
                    required_scope="read",  # Skip scope check
                    skip_project_check=True,
                )
                api_key_info = api_key_manager.keys.get(key_id)
                api_key_id = key_id
                api_key_project_id = api_key_info.project_id
                api_key_scope = api_key_info.scope

            # Try as Master API Key
            elif auth_manager.validate_master_key(api_key):
                # Master key → Full access
                api_key_id = "master"
                api_key_project_id = "*"
                api_key_scope = "read write admin"

            else:
                raise OAuthError(
                    error="access_denied",
                    error_description="Invalid API Key. Please provide a valid API Key.",
                )

            # Limit requested scope to API Key's scope
            requested_scope = validated["scope"].split()
            allowed_scope = (
                api_key_scope.split() if isinstance(api_key_scope, str) else api_key_scope
            )

            # Filter to only allowed scopes
            granted_scope = " ".join([s for s in requested_scope if s in allowed_scope])

            if not granted_scope:
                # If no overlap, grant all API Key scopes
                granted_scope = (
                    api_key_scope if isinstance(api_key_scope, str) else " ".join(api_key_scope)
                )

            logger.info(
                f"OAuth authorization: API Key validated - key_id={api_key_id}, "
                f"project_id={api_key_project_id}, scope={api_key_scope}, "
                f"granted_scope='{granted_scope}'"
            )

        except Exception as e:
            logger.warning(f"OAuth authorization failed: Invalid API Key - {e}")
            raise OAuthError(error="access_denied", error_description="Invalid or expired API Key.")

        # Create authorization code with API Key metadata
        code = oauth_server.create_authorization_code(
            client_id=validated["client_id"],
            redirect_uri=validated["redirect_uri"],
            scope=granted_scope,
            code_challenge=validated["code_challenge"],
            code_challenge_method=validated["code_challenge_method"],
            api_key_id=api_key_id,
            api_key_project_id=api_key_project_id,
            api_key_scope=api_key_scope,
        )

        # Redirect back with authorization code
        callback_params = {"code": code}
        if validated.get("state"):
            callback_params["state"] = validated["state"]

        redirect_url = f"{validated['redirect_uri']}?{urlencode(callback_params)}"

        # Return HTTP 302 redirect to redirect_uri with authorization code
        logger.info(f"Authorization approved, redirecting to {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=302)

    except OAuthError as e:
        # If redirect_uri is available, redirect with error
        redirect_uri = params.get("redirect_uri") if "params" in locals() else None
        if redirect_uri:
            error_params = {"error": e.error, "error_description": e.error_description}
            if params.get("state"):
                error_params["state"] = params["state"]

            error_url = f"{redirect_uri}?{urlencode(error_params)}"
            logger.warning(f"OAuth error, redirecting to {error_url}")
            return RedirectResponse(url=error_url, status_code=302)
        else:
            # No redirect_uri, render error page
            return templates.TemplateResponse(
                "oauth/error.html",
                {"request": request, "error": e.error, "error_description": e.error_description},
                status_code=e.status_code,
            )

    except Exception as e:
        logger.error(f"OAuth authorize confirm error: {e}", exc_info=True)
        # For unexpected errors, try to redirect or render error page
        redirect_uri = params.get("redirect_uri") if "params" in locals() else None
        if redirect_uri:
            error_url = f"{redirect_uri}?error=server_error&error_description={str(e)}"
            return RedirectResponse(url=error_url, status_code=302)
        else:
            return templates.TemplateResponse(
                "oauth/error.html",
                {"request": request, "error": "server_error", "error_description": str(e)},
                status_code=500,
            )

@mcp.custom_route("/oauth/token", methods=["POST"])
async def oauth_token(request: Request) -> JSONResponse:
    """
    OAuth 2.1 token endpoint.

    Handles token grants:
        - authorization_code: Exchange code for tokens (Step 3 of Authorization Code flow)
        - refresh_token: Refresh access token
        - client_credentials: Machine-to-machine authentication

    Request Body (form-urlencoded or JSON):
        grant_type: "authorization_code" | "refresh_token" | "client_credentials"
        client_id: OAuth client ID
        client_secret: Client secret

        For authorization_code:
            code: Authorization code from /authorize
            redirect_uri: Same redirect_uri used in /authorize
            code_verifier: PKCE code verifier

        For refresh_token:
            refresh_token: Current refresh token

        For client_credentials:
            scope: Optional requested scopes

    Returns:
        TokenResponse with access_token (and refresh_token for authorization_code)
    """
    try:
        # Parse request body (support both form and JSON)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
        else:
            # application/x-www-form-urlencoded
            form = await request.form()
            body = dict(form)

        # Validate required parameters
        if "grant_type" not in body:
            raise OAuthError(
                error="invalid_request", error_description="Missing grant_type parameter"
            )

        if "client_id" not in body or "client_secret" not in body:
            raise OAuthError(
                error="invalid_request", error_description="Missing client_id or client_secret"
            )

        grant_type = body["grant_type"]

        # Handle different grant types
        if grant_type == "authorization_code":
            # Authorization Code Grant
            required = ["code", "redirect_uri", "code_verifier"]
            missing = [p for p in required if p not in body]
            if missing:
                raise OAuthError(
                    error="invalid_request",
                    error_description=f"Missing parameters: {', '.join(missing)}",
                )

            token_response = oauth_server.exchange_code_for_tokens(
                client_id=body["client_id"],
                client_secret=body["client_secret"],
                code=body["code"],
                redirect_uri=body["redirect_uri"],
                code_verifier=body["code_verifier"],
            )

        elif grant_type == "refresh_token":
            # Refresh Token Grant
            if "refresh_token" not in body:
                raise OAuthError(
                    error="invalid_request", error_description="Missing refresh_token parameter"
                )

            token_response = oauth_server.handle_refresh_token_grant(
                client_id=body["client_id"],
                client_secret=body["client_secret"],
                refresh_token=body["refresh_token"],
            )

        elif grant_type == "client_credentials":
            # Client Credentials Grant
            token_response = oauth_server.handle_client_credentials_grant(
                client_id=body["client_id"],
                client_secret=body["client_secret"],
                scope=body.get("scope"),
            )

        else:
            raise OAuthError(
                error="unsupported_grant_type",
                error_description=f"Grant type '{grant_type}' is not supported",
            )

        # Return token response
        return JSONResponse(token_response.model_dump())

    except OAuthError as e:
        return JSONResponse(
            {"error": e.error, "error_description": e.error_description}, status_code=e.status_code
        )
    except Exception as e:
        logger.error(f"OAuth token error: {e}", exc_info=True)
        return JSONResponse({"error": "server_error", "error_description": str(e)}, status_code=500)

# === OAUTH CLIENT MANAGEMENT TOOLS ===

# Internal implementation for OAuth register
async def _oauth_register_client_impl(
    client_name: str,
    redirect_uris: str,
    grant_types: str = "authorization_code,refresh_token",
    allowed_scopes: str = "read,write",
    metadata: dict = None,
) -> dict:
    """Internal implementation for registering OAuth client."""
    from core.oauth import get_client_registry

    try:
        client_registry = get_client_registry()
        redirect_uri_list = [uri.strip() for uri in redirect_uris.split(",")]
        grant_type_list = [gt.strip() for gt in grant_types.split(",")]
        scope_list = [s.strip() for s in allowed_scopes.split(",")]
        client_id, client_secret = client_registry.create_client(
            client_name=client_name,
            redirect_uris=redirect_uri_list,
            grant_types=grant_type_list,
            allowed_scopes=scope_list,
            metadata=metadata or {},
        )
        logger.info(f"Registered OAuth client: {client_id} ({client_name})")
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": client_name,
            "redirect_uris": redirect_uri_list,
            "grant_types": grant_type_list,
            "allowed_scopes": scope_list,
            "warning": "Save the client_secret now! It will not be shown again.",
        }
    except Exception as e:
        logger.error(f"Error registering OAuth client: {e}", exc_info=True)
        raise ToolError(f"Failed to register client: {e}")

@mcp.tool()
async def oauth_register_client(
    client_name: str,
    redirect_uris: str,
    grant_types: str = "authorization_code,refresh_token",
    allowed_scopes: str = "read,write",
    metadata: dict = None,
) -> dict:
    """
    Register a new OAuth 2.1 client.

    Args:
        client_name: Human-readable client name (e.g., "My OpenAI GPT")
        redirect_uris: Comma-separated redirect URIs
        grant_types: Comma-separated grant types (default: "authorization_code,refresh_token")
        allowed_scopes: Comma-separated scopes (default: "read,write")
        metadata: Optional metadata dict

    Returns:
        Dict with client_id and client_secret (SAVE THIS - shown only once!)
    """
    return await _oauth_register_client_impl(
        client_name, redirect_uris, grant_types, allowed_scopes, metadata
    )

# Internal implementations for OAuth tools
async def _oauth_list_clients_impl() -> dict:
    """Internal implementation for listing OAuth clients."""
    from core.oauth import get_client_registry

    try:
        client_registry = get_client_registry()
        clients = client_registry.list_clients()
        client_list = [
            {
                "client_id": client.client_id,
                "client_name": client.client_name,
                "redirect_uris": client.redirect_uris,
                "grant_types": client.grant_types,
                "allowed_scopes": client.allowed_scopes,
                "created_at": client.created_at.isoformat(),
                "metadata": client.metadata,
            }
            for client in clients
        ]
        return {"clients": client_list, "count": len(client_list)}
    except Exception as e:
        logger.error(f"Error listing OAuth clients: {e}", exc_info=True)
        raise ToolError(f"Failed to list clients: {e}")

async def _oauth_revoke_client_impl(client_id: str) -> dict:
    """Internal implementation for revoking OAuth client."""
    from core.oauth import get_client_registry

    try:
        client_registry = get_client_registry()
        client = client_registry.get_client(client_id)
        if not client:
            raise ToolError(f"Client not found: {client_id}")
        success = client_registry.delete_client(client_id)
        if success:
            logger.info(f"Revoked OAuth client: {client_id} ({client.client_name})")
            return {
                "success": True,
                "client_id": client_id,
                "client_name": client.client_name,
                "message": f"Client '{client.client_name}' has been revoked",
            }
        else:
            raise ToolError(f"Failed to delete client: {client_id}")
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error revoking OAuth client: {e}", exc_info=True)
        raise ToolError(f"Failed to revoke client: {e}")

async def _oauth_get_client_info_impl(client_id: str) -> dict:
    """Internal implementation for getting OAuth client info."""
    from core.oauth import get_client_registry

    try:
        client_registry = get_client_registry()
        client = client_registry.get_client(client_id)
        if not client:
            return {"success": False, "error": f"Client not found: {client_id}"}
        return {
            "success": True,
            "client": {
                "client_id": client.client_id,
                "client_name": client.client_name,
                "redirect_uris": client.redirect_uris,
                "grant_types": client.grant_types,
                "allowed_scopes": client.allowed_scopes,
                "created_at": client.created_at.isoformat(),
                "metadata": client.metadata,
            },
        }
    except Exception as e:
        logger.error(f"Error getting OAuth client info: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool()
async def oauth_list_clients() -> dict:
    """
    List all registered OAuth clients.

    Returns client information (excluding secrets).

    Returns:
        Dict with list of clients
    """
    return await _oauth_list_clients_impl()

@mcp.tool()
async def oauth_revoke_client(client_id: str) -> dict:
    """
    Revoke (delete) an OAuth client.

    This will delete the client and prevent further authentication.
    Existing tokens will continue to work until they expire.

    Args:
        client_id: Client ID to revoke

    Returns:
        Dict with success status
    """
    return await _oauth_revoke_client_impl(client_id)

@mcp.tool()
async def oauth_get_client_info(client_id: str) -> dict:
    """
    Get detailed information about a specific OAuth client.

    Args:
        client_id: Client ID to query

    Returns:
        Dict with client information (excluding secret)
    """
    return await _oauth_get_client_info_impl(client_id)

# === PHASE X.3: SYSTEM TOOLS ===

# Internal implementations for Phase X.3 system tools
async def _get_endpoints_impl() -> dict:
    """Internal implementation for listing endpoints."""
    try:
        all_sites = site_manager.list_all_sites()
        endpoints = [
            {
                "path": "/mcp",
                "name": "Coolify Admin",
                "description": "Full administrative access to all tools",
                "require_master_key": True,
                "plugin_types": ["all"],
            },
            {
                "path": "/system/mcp",
                "name": "System Manager",
                "description": "System management tools (API keys, OAuth, health, rate limiting)",
                "require_master_key": True,
                "plugin_types": ["system"],
                "tool_count": 16,
            },
            {
                "path": "/wordpress/mcp",
                "name": "WordPress Manager",
                "description": "WordPress content management",
                "require_master_key": False,
                "plugin_types": ["wordpress"],
            },
            {
                "path": "/woocommerce/mcp",
                "name": "WooCommerce Manager",
                "description": "WooCommerce e-commerce tools",
                "require_master_key": False,
                "plugin_types": ["woocommerce"],
            },
            {
                "path": "/wordpress-advanced/mcp",
                "name": "WordPress Advanced",
                "description": "WordPress advanced operations (database, bulk, system)",
                "require_master_key": False,
                "plugin_types": ["wordpress_advanced"],
            },
            {
                "path": "/gitea/mcp",
                "name": "Gitea Manager",
                "description": "Git repository management",
                "require_master_key": False,
                "plugin_types": ["gitea"],
            },
            {
                "path": "/n8n/mcp",
                "name": "n8n Automation",
                "description": "Workflow automation management",
                "require_master_key": False,
                "plugin_types": ["n8n"],
            },
            {
                "path": "/supabase/mcp",
                "name": "Supabase Manager",
                "description": "Supabase self-hosted management",
                "require_master_key": False,
                "plugin_types": ["supabase"],
            },
            {
                "path": "/openpanel/mcp",
                "name": "OpenPanel Analytics",
                "description": "OpenPanel product analytics",
                "require_master_key": False,
                "plugin_types": ["openpanel"],
            },
            {
                "path": "/appwrite/mcp",
                "name": "Appwrite Manager",
                "description": "Appwrite backend management",
                "require_master_key": False,
                "plugin_types": ["appwrite"],
            },
            {
                "path": "/directus/mcp",
                "name": "Directus CMS",
                "description": "Directus headless CMS management",
                "require_master_key": False,
                "plugin_types": ["directus"],
            },
        ]
        project_endpoints = []
        for site_info in all_sites:
            alias = site_info.get("alias")
            full_id = site_info["full_id"]
            path_suffix = alias if alias and alias != site_info["site_id"] else full_id
            project_endpoints.append(
                {
                    "path": f"/project/{path_suffix}/mcp",
                    "name": f"Project: {full_id}",
                    "description": f"Site-locked tools for {full_id}",
                    "require_master_key": False,
                    "plugin_types": [site_info["plugin_type"]],
                    "site_id": site_info["site_id"],
                    "full_id": full_id,
                }
            )
        return {
            "success": True,
            "total_plugin_endpoints": len(endpoints),
            "total_project_endpoints": len(project_endpoints),
            "endpoints": endpoints,
            "project_endpoints": project_endpoints,
        }
    except Exception as e:
        logger.error(f"Error listing endpoints: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def _get_system_info_impl() -> dict:
    """Internal implementation for getting system info."""
    try:
        import platform

        uptime_seconds = int(time.time() - server_start_time)
        return {
            "success": True,
            "server": {
                "name": "MCP Hub",
                "version": "v2.6.0",
                "phase": "X.3 (System Endpoint)",
            },
            "uptime": {
                "seconds": uptime_seconds,
                "formatted": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s",
            },
            "counts": {
                "total_tools": _total_tool_count,
                "total_sites": site_manager.get_count(),
                "sites_by_type": site_manager.get_count_by_type(),
            },
            "environment": {
                "python_version": platform.python_version(),
                "platform": platform.system(),
                "platform_version": platform.release(),
            },
            "oauth": {
                "auth_mode": OAUTH_AUTH_MODE,
                "trusted_domains": (
                    OAUTH_TRUSTED_DOMAINS if OAUTH_AUTH_MODE == "trusted_domains" else []
                ),
            },
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def _get_audit_log_impl(
    limit: int = 50, event_type: str = None, project_id: str = None
) -> dict:
    """Internal implementation for getting audit log."""
    try:
        from core.audit_log import EventType as AuditEventType

        limit = min(limit, 500)

        # Convert string event_type to EventType enum if provided
        audit_event_type = None
        if event_type:
            try:
                audit_event_type = AuditEventType(event_type)
            except ValueError:
                pass  # Invalid event type, ignore filter

        entries = audit_logger.get_logs(
            limit=limit, event_type=audit_event_type, project_id=project_id
        )
        return {
            "success": True,
            "total": len(entries),
            "filters": {"limit": limit, "event_type": event_type, "project_id": project_id},
            "entries": entries,
        }
    except Exception as e:
        logger.error(f"Error getting audit log: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def _set_rate_limit_config_impl(
    requests_per_minute: int = None, requests_per_hour: int = None, requests_per_day: int = None
) -> dict:
    """Internal implementation for setting rate limit config."""
    try:
        current_config = {
            "requests_per_minute": rate_limiter.limits.get("per_minute", 60),
            "requests_per_hour": rate_limiter.limits.get("per_hour", 1000),
            "requests_per_day": rate_limiter.limits.get("per_day", 10000),
        }
        if requests_per_minute is not None:
            rate_limiter.limits["per_minute"] = requests_per_minute
        if requests_per_hour is not None:
            rate_limiter.limits["per_hour"] = requests_per_hour
        if requests_per_day is not None:
            rate_limiter.limits["per_day"] = requests_per_day
        new_config = {
            "requests_per_minute": rate_limiter.limits.get("per_minute", 60),
            "requests_per_hour": rate_limiter.limits.get("per_hour", 1000),
            "requests_per_day": rate_limiter.limits.get("per_day", 10000),
        }
        return {
            "success": True,
            "message": "Rate limit configuration updated",
            "previous_config": current_config,
            "new_config": new_config,
        }
    except Exception as e:
        logger.error(f"Error setting rate limit config: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_endpoints() -> dict:
    """List all available MCP endpoints (Phase X.3)."""
    return await _get_endpoints_impl()

@mcp.tool()
async def get_system_info() -> dict:
    """Get comprehensive system information (Phase X.3)."""
    return await _get_system_info_impl()

@mcp.tool()
async def get_audit_log(limit: int = 50, event_type: str = None, project_id: str = None) -> dict:
    """Get audit log entries (Phase X.3)."""
    return await _get_audit_log_impl(limit, event_type, project_id)

@mcp.tool()
async def set_rate_limit_config(
    requests_per_minute: int = None, requests_per_hour: int = None, requests_per_day: int = None
) -> dict:
    """Configure rate limiting settings (Phase X.3)."""
    return await _set_rate_limit_config_impl(
        requests_per_minute, requests_per_hour, requests_per_day
    )

# === HEALTH CHECK ENDPOINT ===

# Track server start time for uptime calculation
server_start_time = time.time()

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """
    Health check endpoint for container orchestration (Coolify, Docker, Kubernetes).

    Returns JSON with server status, uptime, and project/tool counts.
    This endpoint is used by Docker HEALTHCHECK and container health probes.

    Returns:
        JSONResponse with health status:
        - status: "healthy" if server is running
        - uptime: seconds since server started
        - projects: number of discovered projects
        - tools: total number of registered tools
        - timestamp: current UTC timestamp
    """
    uptime_seconds = int(time.time() - server_start_time)

    return JSONResponse(
        {
            "status": "healthy",
            "uptime": uptime_seconds,
            "projects": len(project_manager.projects),
            "sites": site_manager.get_count(),  # Option B
            "tools": _total_tool_count,  # Total tools (plugin + system)
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
    )

# === API KEYS MANAGEMENT TOOLS ===

# Internal implementation functions (not decorated)
async def _manage_api_keys_create_impl(
    project_id: str, scope: str = "read", expires_in_days: int = None, description: str = None
) -> dict:
    """Internal implementation for creating API keys."""
    try:
        result = api_key_manager.create_key(
            project_id=project_id,
            scope=scope,
            expires_in_days=expires_in_days,
            description=description,
        )
        return {
            "success": True,
            "message": "API key created successfully",
            "warning": "SAVE THIS KEY - It will not be shown again!",
            "key": result["key"],
            "key_id": result["key_id"],
            "project_id": result["project_id"],
            "scope": result["scope"],
            "expires_at": result.get("expires_at"),
            "created_at": datetime.now().isoformat(),
        }
    except ValueError as e:
        logger.error(f"Invalid scope for API key: {e}")
        return {"success": False, "error": f"Invalid scope: {e}"}
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        return {"success": False, "error": str(e)}

async def _manage_api_keys_list_impl(project_id: str = None, include_revoked: bool = False) -> dict:
    """Internal implementation for listing API keys."""
    try:
        keys = api_key_manager.list_keys(project_id=project_id, include_revoked=include_revoked)
        return {"success": True, "total": len(keys), "keys": keys}
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        return {"success": False, "error": str(e)}

async def _manage_api_keys_get_info_impl(key_id: str) -> dict:
    """Internal implementation for getting API key info."""
    try:
        info = api_key_manager.get_key_info(key_id)
        if info is None:
            return {"success": False, "error": f"Key not found: {key_id}"}
        return {"success": True, "key": info}
    except Exception as e:
        logger.error(f"Error getting key info: {e}")
        return {"success": False, "error": str(e)}

async def _manage_api_keys_revoke_impl(key_id: str) -> dict:
    """Internal implementation for revoking API key."""
    try:
        success = api_key_manager.revoke_key(key_id)
        if not success:
            return {"success": False, "error": f"Key not found or already revoked: {key_id}"}
        return {"success": True, "message": f"API key {key_id} revoked successfully"}
    except Exception as e:
        logger.error(f"Error revoking API key: {e}")
        return {"success": False, "error": str(e)}

async def _manage_api_keys_delete_impl(key_id: str) -> dict:
    """Internal implementation for deleting API key."""
    try:
        success = api_key_manager.delete_key(key_id)
        if not success:
            return {"success": False, "error": f"Key not found: {key_id}"}
        return {"success": True, "message": f"API key {key_id} permanently deleted"}
    except Exception as e:
        logger.error(f"Error deleting API key: {e}")
        return {"success": False, "error": str(e)}

async def _manage_api_keys_rotate_impl(project_id: str) -> dict:
    """Internal implementation for rotating API keys."""
    try:
        new_keys = api_key_manager.rotate_keys(project_id)
        return {
            "success": True,
            "message": f"Rotated {len(new_keys)} keys for project {project_id}",
            "warning": "SAVE THESE NEW KEYS - They will not be shown again!",
            "new_keys": new_keys,
            "rotated_count": len(new_keys),
        }
    except Exception as e:
        logger.error(f"Error rotating API keys: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def manage_api_keys_create(
    project_id: str, scope: str = "read", expires_in_days: int = None, description: str = None
) -> dict:
    """
    Create a new API key for a project.

    Args:
        project_id: Project ID or "*" for all projects
        scope: Access scope - single ("read", "write", "admin") or multiple space-separated ("read write admin")
              Examples: "read", "write", "admin", "read write", "read write admin"
        expires_in_days: Optional expiration in days (default: never expires)
        description: Optional description for the key

    Returns:
        dict: Key information including the actual key (SAVE IT - won't be shown again!)

    Examples:
        # Single scope
        manage_api_keys_create(project_id="wordpress_site1", scope="read")

        # Multiple scopes (space-separated)
        manage_api_keys_create(project_id="wordpress_site1", scope="read write admin")

        # All scopes for all projects
        manage_api_keys_create(project_id="*", scope="read write admin")
    """
    return await _manage_api_keys_create_impl(project_id, scope, expires_in_days, description)

@mcp.tool()
async def manage_api_keys_list(project_id: str = None, include_revoked: bool = False) -> dict:
    """
    List API keys with optional filtering.

    **Requires**: Global API key (Master API Key or global admin key)

    **Filtering Behavior**:
    - `project_id=null` (default): Returns ALL keys (global + project-specific)
    - `project_id="*"`: Returns ONLY global keys
    - `project_id="wordpress_site1"`: Returns keys for that project + global keys

    Args:
        project_id: Optional filter by project ID (default: null = all keys)
        include_revoked: Include revoked keys (default: False)

    Returns:
        dict: List of API keys with metadata (without actual key values)

    Examples:
        # List all keys
        manage_api_keys_list()

        # List only global keys
        manage_api_keys_list(project_id="*")

        # List keys for specific project
        manage_api_keys_list(project_id="wordpress_site1")

    Note:
        See docs/API_KEYS_USAGE.md for detailed documentation
    """
    return await _manage_api_keys_list_impl(project_id, include_revoked)

@mcp.tool()
async def manage_api_keys_get_info(key_id: str) -> dict:
    """
    Get detailed information about a specific API key.

    Args:
        key_id: Key ID to query

    Returns:
        dict: Key information (without actual key value)
    """
    return await _manage_api_keys_get_info_impl(key_id)

@mcp.tool()
async def manage_api_keys_revoke(key_id: str) -> dict:
    """
    Revoke an API key (soft delete - can be restored).

    Args:
        key_id: Key ID to revoke

    Returns:
        dict: Success status
    """
    return await _manage_api_keys_revoke_impl(key_id)

@mcp.tool()
async def manage_api_keys_delete(key_id: str) -> dict:
    """
    Permanently delete an API key (cannot be undone).

    Args:
        key_id: Key ID to delete

    Returns:
        dict: Success status
    """
    return await _manage_api_keys_delete_impl(key_id)

@mcp.tool()
async def manage_api_keys_rotate(project_id: str) -> dict:
    """
    Rotate all keys for a project.

    Creates new keys with the same scopes and revokes old ones.
    Use this for security rotation or if keys may be compromised.

    Args:
        project_id: Project ID to rotate keys for

    Returns:
        dict: List of new keys (SAVE THEM - won't be shown again!)
    """
    return await _manage_api_keys_rotate_impl(project_id)

# === SERVER STARTUP ===

# Create separate MCP instances for each endpoint

def create_system_mcp():
    """
    Create System-only MCP instance (Phase X.3).

    Contains only 16 system management tools:
    - API Key Management (6)
    - OAuth Management (3)
    - Rate Limiting (3)
    - Health & Status (4)
    """
    from fastmcp import FastMCP

    system_instructions = """This is the System Management endpoint (17 tools).

Available tools:
• API Key Management: create, list, get_info, revoke, delete, rotate
• OAuth Management: register_client, list_clients, revoke_client, get_client_info
• Rate Limiting: get_stats, reset, set_config
• Health & Status: list_projects, get_endpoints, get_system_info, get_audit_log

Use list_projects() to see all configured sites across all plugin types.
Use get_endpoints() to see all available MCP endpoints."""

    system_mcp = FastMCP("System Manager", instructions=system_instructions)

    # Register system tools with proper wrappers
    # Each tool calls the _impl function directly (not the decorated version)

    @system_mcp.tool()
    async def manage_api_keys_create(
        project_id: str, scope: str = "read", expires_in_days: int = None, description: str = None
    ) -> dict:
        """Create a new API key for a project."""
        return await _manage_api_keys_create_impl(project_id, scope, expires_in_days, description)

    @system_mcp.tool()
    async def manage_api_keys_list(project_id: str = None, include_revoked: bool = False) -> dict:
        """List API keys with optional filtering."""
        return await _manage_api_keys_list_impl(project_id, include_revoked)

    @system_mcp.tool()
    async def manage_api_keys_get_info(key_id: str) -> dict:
        """Get detailed information about a specific API key."""
        return await _manage_api_keys_get_info_impl(key_id)

    @system_mcp.tool()
    async def manage_api_keys_revoke(key_id: str) -> dict:
        """Revoke an API key (soft delete)."""
        return await _manage_api_keys_revoke_impl(key_id)

    @system_mcp.tool()
    async def manage_api_keys_delete(key_id: str) -> dict:
        """Permanently delete an API key."""
        return await _manage_api_keys_delete_impl(key_id)

    @system_mcp.tool()
    async def manage_api_keys_rotate(project_id: str) -> dict:
        """Rotate all keys for a project."""
        return await _manage_api_keys_rotate_impl(project_id)

    @system_mcp.tool()
    async def list_projects() -> str:
        """List all discovered projects."""
        return await _list_projects_impl()

    @system_mcp.tool()
    async def get_endpoints() -> dict:
        """List all available MCP endpoints."""
        return await _get_endpoints_impl()

    @system_mcp.tool()
    async def get_system_info() -> dict:
        """Get comprehensive system information."""
        return await _get_system_info_impl()

    @system_mcp.tool()
    async def get_audit_log(
        limit: int = 50, event_type: str = None, project_id: str = None
    ) -> dict:
        """Get audit log entries."""
        return await _get_audit_log_impl(limit, event_type, project_id)

    @system_mcp.tool()
    async def oauth_register_client(
        client_name: str,
        redirect_uris: str,
        grant_types: str = "authorization_code,refresh_token",
        allowed_scopes: str = "read,write",
        metadata: dict = None,
    ) -> dict:
        """Register a new OAuth 2.1 client."""
        return await _oauth_register_client_impl(
            client_name, redirect_uris, grant_types, allowed_scopes, metadata
        )

    @system_mcp.tool()
    async def oauth_list_clients() -> dict:
        """List all registered OAuth clients."""
        return await _oauth_list_clients_impl()

    @system_mcp.tool()
    async def oauth_revoke_client(client_id: str) -> dict:
        """Revoke (delete) an OAuth client."""
        return await _oauth_revoke_client_impl(client_id)

    @system_mcp.tool()
    async def oauth_get_client_info(client_id: str) -> dict:
        """Get detailed information about a specific OAuth client."""
        return await _oauth_get_client_info_impl(client_id)

    @system_mcp.tool()
    async def get_rate_limit_stats(client_id: str = None) -> str:
        """Get rate limiting statistics."""
        return await _get_rate_limit_stats_impl(client_id)

    @system_mcp.tool()
    async def reset_rate_limit(client_id: str = None) -> str:
        """Reset rate limit state for a client or all clients."""
        return await _reset_rate_limit_impl(client_id)

    @system_mcp.tool()
    async def set_rate_limit_config(
        requests_per_minute: int = None, requests_per_hour: int = None, requests_per_day: int = None
    ) -> dict:
        """Configure rate limiting settings."""
        return await _set_rate_limit_config_impl(
            requests_per_minute, requests_per_hour, requests_per_day
        )

    logger.info("Created System endpoint with 17 tools")
    return system_mcp

def create_wordpress_mcp():
    """Create WordPress-only MCP instance"""
    from fastmcp import FastMCP

    wp_instructions = generate_mcp_instructions(plugin_type="wordpress")
    wp_mcp = FastMCP("WordPress Manager", instructions=wp_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(wp_mcp, "WordPress")

    # Get WordPress tools only (excluding advanced)
    count = 0
    for tool_def in tool_registry.get_all():
        tool_name = tool_def.name
        # Exclude wordpress_advanced_ tools (they go to the advanced endpoint)
        # Advanced tools are named: wordpress_advanced_wp_db_*, wordpress_advanced_bulk_*, etc.
        if tool_name.startswith("wordpress_advanced_"):
            continue

        # Include wordpress_ tools only (woocommerce_ moved to /woocommerce/mcp in Phase D.1)
        if tool_name.startswith("wordpress_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                wp_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @wp_mcp.tool()
    async def list_sites() -> str:
        """
        List all available WordPress sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("wordpress")

    count += 1
    logger.info(f"Created WordPress endpoint with {count} tools (including list_sites)")
    return wp_mcp

def create_wordpress_advanced_mcp():
    """Create WordPress Advanced MCP instance"""
    from fastmcp import FastMCP

    wp_adv_instructions = generate_mcp_instructions(plugin_type="wordpress_advanced")
    wp_adv_mcp = FastMCP("WordPress Advanced", instructions=wp_adv_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(wp_adv_mcp, "WordPress Advanced")

    # Get WordPress Advanced tools only
    # Advanced tools are named: wordpress_advanced_wp_db_*, wordpress_advanced_bulk_*, etc.
    count = 0
    for tool_def in tool_registry.get_all():
        tool_name = tool_def.name
        if tool_name.startswith("wordpress_advanced_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                wp_adv_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @wp_adv_mcp.tool()
    async def list_sites() -> str:
        """
        List all available WordPress sites for advanced operations.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("wordpress_advanced")

    count += 1
    logger.info(f"Created WordPress Advanced endpoint with {count} tools (including list_sites)")
    return wp_adv_mcp

def create_woocommerce_mcp():
    """Create WooCommerce-only MCP instance (Phase D.1)"""
    from fastmcp import FastMCP

    woo_instructions = generate_mcp_instructions(plugin_type="woocommerce")
    woo_mcp = FastMCP("WooCommerce Manager", instructions=woo_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(woo_mcp, "WooCommerce")

    # Get WooCommerce tools only
    count = 0
    for tool_def in tool_registry.get_all():
        if tool_def.name.startswith("woocommerce_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                woo_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @woo_mcp.tool()
    async def list_sites() -> str:
        """
        List all available WooCommerce sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("woocommerce")

    count += 1
    logger.info(f"Created WooCommerce endpoint with {count} tools (including list_sites)")
    return woo_mcp

def create_gitea_mcp():
    """Create Gitea-only MCP instance"""
    from fastmcp import FastMCP

    gitea_instructions = generate_mcp_instructions(plugin_type="gitea")
    gitea_mcp = FastMCP("Gitea Manager", instructions=gitea_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(gitea_mcp, "Gitea")

    # Get Gitea tools only
    count = 0
    for tool_def in tool_registry.get_all():
        if tool_def.name.startswith("gitea_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                gitea_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @gitea_mcp.tool()
    async def list_sites() -> str:
        """
        List all available Gitea sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("gitea")

    count += 1
    logger.info(f"Created Gitea endpoint with {count} tools (including list_sites)")
    return gitea_mcp

def create_openpanel_mcp():
    """Create OpenPanel-only MCP instance"""
    from fastmcp import FastMCP

    openpanel_instructions = generate_mcp_instructions(plugin_type="openpanel")
    openpanel_mcp = FastMCP("OpenPanel Analytics", instructions=openpanel_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(openpanel_mcp, "OpenPanel")

    # Get OpenPanel tools only
    count = 0
    for tool_def in tool_registry.get_all():
        if tool_def.name.startswith("openpanel_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                openpanel_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @openpanel_mcp.tool()
    async def list_sites() -> str:
        """
        List all available OpenPanel sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("openpanel")

    count += 1
    logger.info(f"Created OpenPanel endpoint with {count} tools (including list_sites)")
    return openpanel_mcp

def create_n8n_mcp():
    """Create n8n-only MCP instance"""
    from fastmcp import FastMCP

    n8n_instructions = generate_mcp_instructions(plugin_type="n8n")
    n8n_mcp = FastMCP("n8n Automation", instructions=n8n_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(n8n_mcp, "n8n")

    # Get n8n tools only
    count = 0
    for tool_def in tool_registry.get_all():
        if tool_def.name.startswith("n8n_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                n8n_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @n8n_mcp.tool()
    async def list_sites() -> str:
        """
        List all available n8n sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("n8n")

    count += 1
    logger.info(f"Created n8n endpoint with {count} tools (including list_sites)")
    return n8n_mcp

def create_supabase_mcp():
    """Create Supabase-only MCP instance"""
    from fastmcp import FastMCP

    supabase_instructions = generate_mcp_instructions(plugin_type="supabase")
    supabase_mcp = FastMCP("Supabase Manager", instructions=supabase_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(supabase_mcp, "Supabase")

    # Get Supabase tools only
    count = 0
    for tool_def in tool_registry.get_all():
        if tool_def.name.startswith("supabase_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                supabase_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @supabase_mcp.tool()
    async def list_sites() -> str:
        """
        List all available Supabase sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("supabase")

    count += 1
    logger.info(f"Created Supabase endpoint with {count} tools (including list_sites)")
    return supabase_mcp

def create_appwrite_mcp():
    """Create Appwrite-only MCP instance"""
    from fastmcp import FastMCP

    appwrite_instructions = generate_mcp_instructions(plugin_type="appwrite")
    appwrite_mcp = FastMCP("Appwrite Manager", instructions=appwrite_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(appwrite_mcp, "Appwrite")

    # Get Appwrite tools only
    count = 0
    for tool_def in tool_registry.get_all():
        if tool_def.name.startswith("appwrite_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                appwrite_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @appwrite_mcp.tool()
    async def list_sites() -> str:
        """
        List all available Appwrite sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("appwrite")

    count += 1
    logger.info(f"Created Appwrite endpoint with {count} tools (including list_sites)")
    return appwrite_mcp

def create_directus_mcp():
    """Create Directus-only MCP instance"""
    from fastmcp import FastMCP

    directus_instructions = generate_mcp_instructions(plugin_type="directus")
    directus_mcp = FastMCP("Directus CMS", instructions=directus_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(directus_mcp, "Directus")

    # Get Directus tools only
    count = 0
    for tool_def in tool_registry.get_all():
        if tool_def.name.startswith("directus_"):
            try:
                wrapped = create_dynamic_tool(
                    tool_def.name, tool_def.description, tool_def.handler, tool_def.input_schema
                )
                directus_mcp.tool()(wrapped)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {tool_def.name}: {e}")

    # Phase K.2.3: Add list_sites tool for site discovery
    @directus_mcp.tool()
    async def list_sites() -> str:
        """
        List all available Directus sites.

        Use this tool to discover which sites you can access.
        The returned 'site' values can be used as the site parameter in other tools.

        Returns:
            JSON string with list of available sites
        """
        return await _list_sites_impl("directus")

    count += 1
    logger.info(f"Created Directus endpoint with {count} tools (including list_sites)")
    return directus_mcp

def create_project_mcp(project_id: str, plugin_type: str, site_id: str, alias: str = None):
    """
    Create MCP instance for a specific project with site-locked tools.

    Args:
        project_id: Full project ID (e.g., "wordpress_site1")
        plugin_type: Plugin type (e.g., "wordpress", "wordpress_advanced", "gitea")
        site_id: Site identifier for tool injection
        alias: Optional friendly alias for display name

    Returns:
        FastMCP instance with tools locked to the specific site
    """
    from functools import wraps

    from fastmcp import FastMCP

    display_name = alias or project_id

    # Generate instructions for site-locked endpoint
    project_instructions = generate_mcp_instructions(site_locked=display_name)
    project_mcp = FastMCP(f"Project: {display_name}", instructions=project_instructions)

    # Add authentication middleware (fix: endpoints must have auth)
    add_endpoint_middleware(project_mcp, f"Project:{display_name}")

    # Determine tool prefix based on plugin type
    if plugin_type == "wordpress_advanced":
        tool_prefix = "wordpress_advanced_"
    elif plugin_type == "wordpress":
        tool_prefix = "wordpress_"
    elif plugin_type == "woocommerce":  # Phase D.1
        tool_prefix = "woocommerce_"
    elif plugin_type == "gitea":
        tool_prefix = "gitea_"
    else:
        tool_prefix = f"{plugin_type}_"

    count = 0
    for tool_def in tool_registry.get_all():
        tool_name = tool_def.name

        # For wordpress plugin type, exclude wordpress_advanced_ and woocommerce_ tools
        # (Phase D.1: WooCommerce now has its own endpoint)
        if plugin_type == "wordpress":
            if tool_name.startswith("wordpress_advanced_"):
                continue
            if tool_name.startswith("woocommerce_"):
                continue

        # Check if tool matches this plugin type
        if not tool_name.startswith(tool_prefix):
            continue

        # Create a site-locked wrapper
        original_handler = tool_def.handler

        def make_site_locked_handler(handler, locked_site_id):
            """Create a handler that always injects the locked site_id"""

            @wraps(handler)
            async def site_locked_handler(**kwargs):
                # Always override the site parameter
                kwargs["site"] = locked_site_id
                return await handler(**kwargs)

            return site_locked_handler

        site_locked_handler = make_site_locked_handler(original_handler, site_id)

        # Remove 'site' parameter from schema for per-project endpoints
        # since it's auto-injected by the site_locked_handler
        project_schema = copy.deepcopy(tool_def.input_schema)
        if "properties" in project_schema:
            project_schema["properties"].pop("site", None)
        if "required" in project_schema and "site" in project_schema["required"]:
            project_schema["required"].remove("site")

        try:
            wrapped = create_dynamic_tool(
                tool_def.name, tool_def.description, site_locked_handler, project_schema
            )
            project_mcp.tool()(wrapped)
            count += 1
        except Exception as e:
            logger.error(f"Failed to register {tool_def.name} for project {project_id}: {e}")

    logger.info(f"Created Project endpoint for {project_id} with {count} tools")
    return project_mcp

def create_per_project_endpoints():
    """
    Create MCP endpoints for each discovered site.

    Each site gets its own endpoint at /project/{alias_or_site_id}
    with tools filtered and locked to that specific site.

    Returns:
        List of tuples: (mount_path, mcp_instance, display_name)
    """
    project_endpoints = []

    # Get all discovered sites
    all_sites = site_manager.list_all_sites()

    if not all_sites:
        logger.info("No sites discovered, skipping per-project endpoints")
        return project_endpoints

    logger.info(f"Creating per-project endpoints for {len(all_sites)} sites...")

    for site_info in all_sites:
        plugin_type = site_info["plugin_type"]
        site_id = site_info["site_id"]
        alias = site_info.get("alias")
        full_id = site_info["full_id"]

        # Determine mount path - use alias if different from site_id
        path_suffix = alias if alias and alias != site_id else full_id
        mount_path = f"/project/{path_suffix}"

        try:
            project_mcp = create_project_mcp(
                project_id=full_id, plugin_type=plugin_type, site_id=site_id, alias=alias
            )
            project_endpoints.append((mount_path, project_mcp, full_id))
            logger.info(f"  ✓ {mount_path}/mcp: {full_id} ({plugin_type})")
        except Exception as e:
            logger.error(f"  ✗ Failed to create {mount_path}: {e}")

    logger.info(f"Created {len(project_endpoints)} per-project endpoints")
    return project_endpoints

def create_multi_endpoint_app(transport: str = "streamable-http"):
    """Create Starlette app with multiple MCP endpoints"""
    from contextlib import asynccontextmanager

    from starlette.applications import Starlette
    from starlette.middleware import Middleware as StarletteMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    # ========================================
    # OAuth 401 Middleware for MCP Endpoints
    # ========================================
    # Returns 401 + WWW-Authenticate header for unauthenticated MCP requests
    # This triggers OAuth flow in Claude and other MCP clients
    class OAuthRequiredMiddleware(BaseHTTPMiddleware):
        """
        Middleware to return 401 with WWW-Authenticate header for MCP endpoints.

        This is required by MCP OAuth spec (RFC 9728) to trigger OAuth flow.
        Without this, clients like Claude won't know that OAuth is required
        and will show "Configure" instead of "Connect".
        """

        # Paths that require OAuth (MCP endpoints)
        MCP_PATHS = ["/mcp", "/sse"]

        # Paths that should be excluded from auth check
        EXCLUDED_PATHS = [
            "/.well-known/",
            "/oauth/",
            "/health",
            "/dashboard",
            "/api/dashboard",
            "/static",
        ]

        async def dispatch(self, request: Request, call_next):
            path = request.url.path

            # Check if this is an MCP endpoint that needs OAuth
            is_mcp_endpoint = any(mcp_path in path for mcp_path in self.MCP_PATHS)
            is_excluded = any(path.startswith(excl) for excl in self.EXCLUDED_PATHS)

            if is_mcp_endpoint and not is_excluded:
                # Check for Authorization header
                auth_header = request.headers.get("authorization", "")

                if not auth_header or not auth_header.startswith("Bearer "):
                    # No valid auth header - return 401 with WWW-Authenticate
                    base_url = get_oauth_base_url(request)
                    resource_metadata_url = f"{base_url}/.well-known/oauth-protected-resource"

                    logger.debug(f"MCP OAuth: Returning 401 for {path} (no auth header)")

                    return Response(
                        content='{"error": "unauthorized", "error_description": "Bearer token required"}',
                        status_code=401,
                        media_type="application/json",
                        headers={
                            "WWW-Authenticate": f'Bearer resource_metadata="{resource_metadata_url}"',
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Headers": "Authorization, Content-Type",
                            "Access-Control-Expose-Headers": "WWW-Authenticate",
                        },
                    )

            return await call_next(request)

    # Create MCP instances
    system_mcp = create_system_mcp()  # Phase X.3 - System endpoint
    wp_mcp = create_wordpress_mcp()
    woo_mcp = create_woocommerce_mcp()  # Phase D.1
    wp_adv_mcp = create_wordpress_advanced_mcp()
    gitea_mcp = create_gitea_mcp()
    n8n_mcp = create_n8n_mcp()  # Phase F
    supabase_mcp = create_supabase_mcp()  # Phase G
    openpanel_mcp = create_openpanel_mcp()  # Phase H
    appwrite_mcp = create_appwrite_mcp()  # Phase I
    directus_mcp = create_directus_mcp()  # Phase J

    # Create per-project endpoints
    project_endpoints = create_per_project_endpoints()

    # Get the appropriate app for each transport
    # Use http_app() instead of deprecated streamable_http_app()
    try:
        # Try new API first
        main_app = mcp.http_app()
        system_app = system_mcp.http_app()  # Phase X.3
        wp_app = wp_mcp.http_app()
        woo_app = woo_mcp.http_app()  # Phase D.1
        wp_adv_app = wp_adv_mcp.http_app()
        gitea_app = gitea_mcp.http_app()
        n8n_app = n8n_mcp.http_app()  # Phase F
        supabase_app = supabase_mcp.http_app()  # Phase G
        openpanel_app = openpanel_mcp.http_app()  # Phase H
        appwrite_app = appwrite_mcp.http_app()  # Phase I
        directus_app = directus_mcp.http_app()  # Phase J

        # Get apps for project endpoints
        project_apps = []
        for mount_path, project_mcp, project_id in project_endpoints:
            project_app = project_mcp.http_app()
            project_apps.append((mount_path, project_app, project_id))
    except AttributeError:
        # Fallback to old API
        if transport == "sse":
            main_app = mcp.sse_app()
            system_app = system_mcp.sse_app()  # Phase X.3
            wp_app = wp_mcp.sse_app()
            woo_app = woo_mcp.sse_app()  # Phase D.1
            wp_adv_app = wp_adv_mcp.sse_app()
            gitea_app = gitea_mcp.sse_app()
            n8n_app = n8n_mcp.sse_app()  # Phase F
            supabase_app = supabase_mcp.sse_app()  # Phase G
            openpanel_app = openpanel_mcp.sse_app()  # Phase H
            appwrite_app = appwrite_mcp.sse_app()  # Phase I
            directus_app = directus_mcp.sse_app()  # Phase J

            project_apps = []
            for mount_path, project_mcp, project_id in project_endpoints:
                project_app = project_mcp.sse_app()
                project_apps.append((mount_path, project_app, project_id))
        else:
            main_app = mcp.streamable_http_app()
            system_app = system_mcp.streamable_http_app()  # Phase X.3
            wp_app = wp_mcp.streamable_http_app()
            woo_app = woo_mcp.streamable_http_app()  # Phase D.1
            wp_adv_app = wp_adv_mcp.streamable_http_app()
            gitea_app = gitea_mcp.streamable_http_app()
            n8n_app = n8n_mcp.streamable_http_app()  # Phase F
            supabase_app = supabase_mcp.streamable_http_app()  # Phase G
            openpanel_app = openpanel_mcp.streamable_http_app()  # Phase H
            appwrite_app = appwrite_mcp.streamable_http_app()  # Phase I
            directus_app = directus_mcp.streamable_http_app()  # Phase J

            project_apps = []
            for mount_path, project_mcp, project_id in project_endpoints:
                project_app = project_mcp.streamable_http_app()
                project_apps.append((mount_path, project_app, project_id))

    # Store all sub-apps for lifespan management
    sub_apps = [
        ("main", main_app),
        ("system", system_app),  # Phase X.3
        ("wordpress", wp_app),
        ("woocommerce", woo_app),  # Phase D.1
        ("wordpress-advanced", wp_adv_app),
        ("gitea", gitea_app),
        ("n8n", n8n_app),  # Phase F
        ("supabase", supabase_app),  # Phase G
        ("openpanel", openpanel_app),  # Phase H
        ("appwrite", appwrite_app),  # Phase I
        ("directus", directus_app),  # Phase J
    ]

    # Add project apps to sub_apps for lifespan management
    for _mount_path, project_app, project_id in project_apps:
        sub_apps.append((f"project:{project_id}", project_app))

    # Combined lifespan for all FastMCP http apps
    # This is REQUIRED for FastMCP's StreamableHTTPSessionManager task group
    @asynccontextmanager
    async def combined_lifespan(app):
        """Combine lifespans from all FastMCP http apps"""
        active_contexts = []

        # Enter each sub-app's lifespan context
        for name, sub_app in sub_apps:
            if hasattr(sub_app, "lifespan_handler") and sub_app.lifespan_handler:
                try:
                    ctx = sub_app.lifespan_handler(sub_app)
                    await ctx.__aenter__()
                    active_contexts.append((name, ctx))
                    logger.info(f"Started lifespan for {name} endpoint")
                except Exception as e:
                    logger.warning(f"Failed to start lifespan for {name}: {e}")
            elif hasattr(sub_app, "router") and hasattr(sub_app.router, "lifespan_context"):
                # Starlette app with router
                try:
                    ctx = sub_app.router.lifespan_context(sub_app)
                    await ctx.__aenter__()
                    active_contexts.append((name, ctx))
                    logger.info(f"Started router lifespan for {name} endpoint")
                except Exception as e:
                    logger.warning(f"Failed to start router lifespan for {name}: {e}")

        try:
            yield
        finally:
            # Exit all contexts in reverse order
            for name, ctx in reversed(active_contexts):
                try:
                    await ctx.__aexit__(None, None, None)
                    logger.debug(f"Stopped lifespan for {name}")
                except Exception as e:
                    logger.warning(f"Error during lifespan cleanup for {name}: {e}")

    # Build routes
    # Note: Order matters! More specific routes first
    routes = [
        # Health check
        Route("/health", health_check, methods=["GET"]),
        # Dashboard routes (Phase K.1)
        Route("/dashboard/login", dashboard_login_page, methods=["GET"]),
        Route("/dashboard/login", dashboard_login_submit, methods=["POST"]),
        Route("/dashboard/logout", dashboard_logout, methods=["GET", "POST"]),
        Route("/dashboard", dashboard_home, methods=["GET"]),
        Route("/dashboard/", dashboard_home, methods=["GET"]),
        Route("/api/dashboard/stats", dashboard_api_stats, methods=["GET"]),
        # Dashboard Projects routes (Phase K.2)
        Route("/dashboard/projects", dashboard_projects_list, methods=["GET"]),
        Route("/dashboard/projects/{project_id:path}", dashboard_project_detail, methods=["GET"]),
        Route("/api/dashboard/projects", dashboard_api_projects, methods=["GET"]),
        # Note: health-check route must come BEFORE generic project_id route
        Route(
            "/api/dashboard/projects/{project_id:path}/health-check",
            dashboard_project_health_check,
            methods=["POST"],
        ),
        Route(
            "/api/dashboard/projects/{project_id:path}",
            dashboard_api_project_detail,
            methods=["GET"],
        ),
        # Dashboard API Keys routes (Phase K.3)
        Route("/dashboard/api-keys", dashboard_api_keys_list, methods=["GET"]),
        Route("/api/dashboard/api-keys/create", dashboard_api_keys_create, methods=["POST"]),
        Route(
            "/api/dashboard/api-keys/{key_id}/revoke", dashboard_api_keys_revoke, methods=["POST"]
        ),
        Route("/api/dashboard/api-keys/{key_id}", dashboard_api_keys_delete, methods=["DELETE"]),
        # Dashboard OAuth Clients routes (Phase K.4)
        Route("/dashboard/oauth-clients", dashboard_oauth_clients_list, methods=["GET"]),
        Route(
            "/api/dashboard/oauth-clients/create", dashboard_oauth_clients_create, methods=["POST"]
        ),
        Route(
            "/api/dashboard/oauth-clients/{client_id}",
            dashboard_oauth_clients_delete,
            methods=["DELETE"],
        ),
        # Dashboard Audit Logs routes (Phase K.4)
        Route("/dashboard/audit-logs", dashboard_audit_logs_list, methods=["GET"]),
        Route("/api/dashboard/audit-logs", dashboard_api_audit_logs, methods=["GET"]),
        # Dashboard Health Monitoring routes (Phase K.5)
        Route("/dashboard/health", dashboard_health_page, methods=["GET"]),
        Route("/api/dashboard/health", dashboard_api_health, methods=["GET"]),
        Route("/api/dashboard/health/projects", dashboard_health_projects_partial, methods=["GET"]),
        # Dashboard Settings routes (Phase K.5)
        Route("/dashboard/settings", dashboard_settings_page, methods=["GET"]),
        # OAuth endpoints
        Route("/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"]),
        # Path-specific OAuth protected resource metadata (must come before root)
        # Claude first tries /.well-known/oauth-protected-resource/{path} per RFC 9728
        Route(
            "/.well-known/oauth-protected-resource/{path:path}",
            oauth_protected_resource_path,
            methods=["GET"],
        ),
        Route("/.well-known/oauth-protected-resource", oauth_protected_resource, methods=["GET"]),
        Route("/oauth/register", oauth_register, methods=["POST"]),
        Route("/oauth/authorize", oauth_authorize, methods=["GET"]),
        Route("/oauth/authorize/confirm", oauth_authorize_confirm, methods=["POST"]),
        Route("/oauth/token", oauth_token, methods=["POST"]),
        # Multi-Endpoint MCP (Phase X + D.1 + X.3 + F + G + H + I + J)
        # Mount each FastMCP app - they handle their own /mcp path internally
        Mount("/system", app=system_app, name="mcp_system"),  # Phase X.3
        Mount("/wordpress-advanced", app=wp_adv_app, name="mcp_wordpress_advanced"),
        Mount("/woocommerce", app=woo_app, name="mcp_woocommerce"),  # Phase D.1
        Mount("/wordpress", app=wp_app, name="mcp_wordpress"),
        Mount("/gitea", app=gitea_app, name="mcp_gitea"),
        Mount("/n8n", app=n8n_app, name="mcp_n8n"),  # Phase F
        Mount("/supabase", app=supabase_app, name="mcp_supabase"),  # Phase G
        Mount("/openpanel", app=openpanel_app, name="mcp_openpanel"),  # Phase H
        Mount("/appwrite", app=appwrite_app, name="mcp_appwrite"),  # Phase I
        Mount("/directus", app=directus_app, name="mcp_directus"),  # Phase J
    ]

    # Add per-project routes (before main admin endpoint)
    for mount_path, project_app, project_id in project_apps:
        safe_name = project_id.replace("-", "_").replace(".", "_")
        routes.append(Mount(mount_path, app=project_app, name=f"mcp_project_{safe_name}"))

    # Main admin endpoint (must be last - catches all remaining routes)
    routes.append(Mount("/", app=main_app, name="mcp_admin"))

    # Add OAuth middleware that returns 401 + WWW-Authenticate for MCP endpoints
    middleware = [
        StarletteMiddleware(OAuthRequiredMiddleware),
    ]

    app = Starlette(routes=routes, lifespan=combined_lifespan, middleware=middleware)

    logger.info("=" * 60)
    logger.info("Multi-Endpoint Architecture (Phase K) Active")
    logger.info("=" * 60)
    logger.info("Dashboard: /dashboard")  # Phase K
    logger.info("Endpoints:")
    logger.info("  /mcp                     - Admin (all 589 tools)")
    logger.info("  /system/mcp              - System (17 tools)")
    logger.info("  /wordpress/mcp           - WordPress Core (67 tools)")
    logger.info("  /woocommerce/mcp         - WooCommerce (28 tools)")  # Phase D.1
    logger.info("  /wordpress-advanced/mcp  - WordPress Advanced (22 tools)")
    logger.info("  /gitea/mcp               - Gitea (56 tools)")
    logger.info("  /n8n/mcp                 - n8n Automation (56 tools)")  # Phase F
    logger.info("  /supabase/mcp            - Supabase (70 tools)")  # Phase G
    logger.info("  /openpanel/mcp           - OpenPanel Analytics (73 tools)")  # Phase H
    logger.info("  /appwrite/mcp            - Appwrite Backend (100 tools)")  # Phase I
    logger.info("  /directus/mcp            - Directus CMS (100 tools)")  # Phase J

    # Log per-project endpoints
    if project_apps:
        logger.info("Per-Project Endpoints:")
        for mount_path, _, project_id in project_apps:
            logger.info(f"  {mount_path}/mcp          - {project_id}")

    logger.info("=" * 60)

    # Debug: Log sub-app routes
    for name, sub_app in sub_apps:
        logger.info(f"Sub-app '{name}' type: {type(sub_app)}")
        if hasattr(sub_app, "routes"):
            for route in sub_app.routes:
                logger.info(f"  Route: {route}")
        elif hasattr(sub_app, "router") and hasattr(sub_app.router, "routes"):
            for route in sub_app.router.routes:
                logger.info(f"  Router route: {route}")

    return app

def main():
    """Main entry point for the MCP server."""
    import argparse

    import uvicorn

    # Parse command line arguments for transport configuration
    parser = argparse.ArgumentParser(description="Coolify Projects MCP Server")
    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="Transport protocol to use",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (0.0.0.0 required for containers)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument(
        "--multi-endpoint", action="store_true", help="Enable multi-endpoint architecture (Phase X)"
    )

    args = parser.parse_args()

    logger.info("Starting MCP server...")
    logger.info(f"Transport: {args.transport}")
    if args.transport != "stdio":
        logger.info(f"Host: {args.host}")
        logger.info(f"Port: {args.port}")

    # Check if any projects were discovered
    if len(project_manager.projects) == 0:
        logger.warning("No projects discovered! Check your environment variables.")
        logger.warning("Expected format: {PLUGIN_TYPE}_{PROJECT_ID}_{CONFIG_KEY}=value")
        logger.warning("Example: WORDPRESS_SITE1_URL=https://example.com")

    try:
        if args.transport == "stdio":
            # stdio doesn't support multi-endpoint
            mcp.run(transport="stdio")
        elif args.multi_endpoint or os.getenv("MULTI_ENDPOINT", "true").lower() == "true":
            # Multi-endpoint mode (default for HTTP transports)
            app = create_multi_endpoint_app(args.transport)
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        else:
            # Legacy single endpoint mode
            mcp.run(transport=args.transport, host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
