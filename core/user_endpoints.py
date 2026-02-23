"""Per-user MCP endpoint handler (Track E.3).

Handles MCP JSON-RPC requests for user-owned sites at
``/u/{user_id}/{alias}/mcp``. Implements the Streamable HTTP transport
protocol directly (no per-user FastMCP instances).

Flow:
    1. Validate user API key (Bearer token)
    2. Look up user's site from SQLite
    3. Decrypt credentials
    4. For tools/list: return plugin tools (without ``site`` param)
    5. For tools/call: create plugin instance, call method, return result

Usage:
    # In server.py route registration:
    from core.user_endpoints import user_mcp_handler
    Route("/u/{user_id}/{alias}/mcp", endpoint=user_mcp_handler, methods=["POST"])
"""

import json
import logging
import os
import time
from copy import deepcopy
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Per-user rate limiting defaults
USER_RATE_LIMIT_PER_MIN = int(os.getenv("USER_RATE_LIMIT_PER_MIN", "30"))
USER_RATE_LIMIT_PER_HR = int(os.getenv("USER_RATE_LIMIT_PER_HR", "500"))

# In-memory rate limit tracking: user_id -> list of timestamps
_rate_limits: dict[str, list[float]] = {}

# Cache for tool schemas per plugin type (computed once)
_tool_schema_cache: dict[str, list[dict[str, Any]]] = {}


def _check_user_rate_limit(user_id: str) -> tuple[bool, str]:
    """Check per-user rate limits.

    Args:
        user_id: User UUID.

    Returns:
        Tuple of (allowed, error_message). error_message is empty if allowed.
    """
    now = time.time()
    timestamps = _rate_limits.setdefault(user_id, [])

    # Prune old entries (older than 1 hour)
    cutoff_hr = now - 3600
    _rate_limits[user_id] = [t for t in timestamps if t > cutoff_hr]
    timestamps = _rate_limits[user_id]

    # Check per-minute limit
    cutoff_min = now - 60
    recent_min = sum(1 for t in timestamps if t > cutoff_min)
    if recent_min >= USER_RATE_LIMIT_PER_MIN:
        return False, f"Rate limit exceeded: {USER_RATE_LIMIT_PER_MIN} requests/minute"

    # Check per-hour limit
    if len(timestamps) >= USER_RATE_LIMIT_PER_HR:
        return False, f"Rate limit exceeded: {USER_RATE_LIMIT_PER_HR} requests/hour"

    timestamps.append(now)
    return True, ""


def _get_tools_for_plugin(plugin_type: str) -> list[dict[str, Any]]:
    """Get MCP tool definitions for a plugin type (cached).

    Returns tool schemas with the ``site`` parameter removed
    (auto-injected for user endpoints).
    """
    if plugin_type in _tool_schema_cache:
        return _tool_schema_cache[plugin_type]

    from core.tool_registry import get_tool_registry

    registry = get_tool_registry()
    tools = registry.get_by_plugin_type(plugin_type)

    result = []
    for tool_def in tools:
        schema = deepcopy(tool_def.input_schema)
        # Remove 'site' parameter (auto-injected)
        if "properties" in schema:
            schema["properties"].pop("site", None)
        if "required" in schema and "site" in schema["required"]:
            schema["required"] = [r for r in schema["required"] if r != "site"]

        result.append(
            {
                "name": tool_def.name,
                "description": tool_def.description,
                "inputSchema": schema,
            }
        )

    _tool_schema_cache[plugin_type] = result
    return result


async def _execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    plugin_type: str,
    config_dict: dict[str, Any],
) -> Any:
    """Execute a tool by creating a plugin instance and calling the method.

    Uses the same pattern as unified_handler in tool_generator.py.
    """
    from plugins import plugin_registry

    if not plugin_registry.is_registered(plugin_type):
        return {"type": "text", "text": f"Error: Unknown plugin type '{plugin_type}'"}

    method_name = tool_name
    # Strip plugin_type prefix: "wordpress_list_posts" → "list_posts"
    prefix = f"{plugin_type}_"
    if method_name.startswith(prefix):
        method_name = method_name[len(prefix) :]

    try:
        plugin_instance = plugin_registry.create_instance(
            plugin_type,
            project_id=f"user_{config_dict.get('alias', 'unknown')}",
            config=config_dict,
        )

        if not hasattr(plugin_instance, method_name):
            return {"type": "text", "text": f"Error: Method '{method_name}' not found"}

        method = getattr(plugin_instance, method_name)

        # Process arguments (parse JSON strings, filter None/empty)
        filtered_args = {}
        for key, value in arguments.items():
            if value is None:
                continue
            if isinstance(value, str):
                stripped = value.strip()
                if stripped == "":
                    continue
                if (stripped.startswith("{") and stripped.endswith("}")) or (
                    stripped.startswith("[") and stripped.endswith("]")
                ):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
            filtered_args[key] = value

        result = await method(**filtered_args)
        return result

    except Exception as e:
        logger.error("Tool execution error %s: %s", tool_name, e, exc_info=True)
        return {"type": "text", "text": f"Error: {type(e).__name__}: {e}"}


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    """Build a JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC success response."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


async def user_mcp_handler(request: Request) -> Response:
    """Handle MCP JSON-RPC requests for user endpoints.

    Route: POST /u/{user_id}/{alias}/mcp

    Validates user API key, looks up the site, and handles MCP protocol
    methods (initialize, tools/list, tools/call).
    """
    user_id = request.path_params.get("user_id", "")
    alias = request.path_params.get("alias", "")

    if not user_id or not alias:
        return JSONResponse(
            _jsonrpc_error(None, -32600, "Invalid endpoint path"),
            status_code=400,
        )

    # --- Authentication ---
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            _jsonrpc_error(None, -32600, "Missing Authorization header"),
            status_code=401,
        )

    api_key = auth_header[7:]  # Strip "Bearer "

    try:
        from core.user_keys import get_user_key_manager

        key_mgr = get_user_key_manager()
        key_info = await key_mgr.validate_key(api_key)
    except RuntimeError:
        return JSONResponse(
            _jsonrpc_error(None, -32600, "Authentication service unavailable"),
            status_code=503,
        )

    if key_info is None:
        return JSONResponse(
            _jsonrpc_error(None, -32600, "Invalid API key"),
            status_code=401,
        )

    # Ensure the API key belongs to the user in the URL
    if key_info["user_id"] != user_id:
        return JSONResponse(
            _jsonrpc_error(None, -32600, "API key does not match user"),
            status_code=403,
        )

    # --- Rate Limiting ---
    allowed, rate_msg = _check_user_rate_limit(user_id)
    if not allowed:
        return JSONResponse(
            _jsonrpc_error(None, -32600, rate_msg),
            status_code=429,
        )

    # --- Look up site ---
    try:
        from core.database import get_database

        db = get_database()
        site = await db.get_site_by_alias(user_id, alias)
    except RuntimeError:
        return JSONResponse(
            _jsonrpc_error(None, -32600, "Database unavailable"),
            status_code=503,
        )

    if site is None:
        return JSONResponse(
            _jsonrpc_error(None, -32600, f"Site '{alias}' not found"),
            status_code=404,
        )

    if site["status"] == "disabled":
        return JSONResponse(
            _jsonrpc_error(None, -32600, "Site is disabled"),
            status_code=403,
        )

    # --- Parse JSON-RPC body ---
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            _jsonrpc_error(None, -32700, "Parse error"),
            status_code=400,
        )

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    # --- Handle MCP methods ---

    if method == "initialize":
        version = "3.1.0"
        return JSONResponse(
            _jsonrpc_result(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": f"mcphub-{alias}",
                        "version": version,
                    },
                },
            )
        )

    elif method == "notifications/initialized":
        # Notification — no response needed
        return Response(status_code=204)

    elif method == "tools/list":
        tools = _get_tools_for_plugin(site["plugin_type"])
        return JSONResponse(_jsonrpc_result(req_id, {"tools": tools}))

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Verify tool belongs to this plugin type
        plugin_prefix = f"{site['plugin_type']}_"
        if not tool_name.startswith(plugin_prefix):
            return JSONResponse(
                _jsonrpc_error(req_id, -32601, f"Tool '{tool_name}' not available for this site")
            )

        # Check required scope
        from core.tool_registry import get_tool_registry
        registry = get_tool_registry()
        tool_def = registry.get_by_name(tool_name)
        if not tool_def:
            return JSONResponse(
                _jsonrpc_error(req_id, -32601, f"Tool '{tool_name}' not found")
            )

        required_scope = tool_def.required_scope
        key_scopes = key_info.get("scopes", "").split()
        
        scope_hierarchy = {"read": 1, "write": 2, "admin": 3}
        required_level = scope_hierarchy.get(required_scope, 0)
        key_level = max([scope_hierarchy.get(s, 0) for s in key_scopes] + [0])
        
        if key_level < required_level:
            return JSONResponse(
                _jsonrpc_error(
                    req_id, 
                    -32600, 
                    f"Insufficient scope. Tool '{tool_name}' requires '{required_scope}' scope."
                )
            )

        # Decrypt credentials
        try:
            from core.encryption import get_credential_encryption

            encryptor = get_credential_encryption()
            credentials = encryptor.decrypt_credentials(site["credentials"], site["id"])
        except Exception as e:
            logger.error("Credential decryption failed for site %s: %s", site["id"], e)
            return JSONResponse(
                _jsonrpc_error(req_id, -32603, "Failed to decrypt site credentials")
            )

        # Build config dict for plugin instantiation
        config_dict = {
            "site_url": site["url"],
            "url": site["url"],
            "alias": alias,
            **credentials,
        }

        result = await _execute_tool(tool_name, arguments, site["plugin_type"], config_dict)

        # Format result as MCP content
        if isinstance(result, str):
            content = [{"type": "text", "text": result}]
        elif isinstance(result, dict) and "type" in result:
            content = [result]
        elif isinstance(result, list):
            content = result
        else:
            content = [{"type": "text", "text": json.dumps(result, default=str)}]

        return JSONResponse(_jsonrpc_result(req_id, {"content": content}))

    else:
        return JSONResponse(_jsonrpc_error(req_id, -32601, f"Method '{method}' not supported"))
