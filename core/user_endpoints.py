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

from core.tool_annotations import humanize_title, tool_annotations
from core.tool_registry import ToolDefinition

logger = logging.getLogger(__name__)

# In-memory rate limit tracking: user_id -> list of timestamps
_rate_limits: dict[str, list[float]] = {}

# Shared with every FastMCP endpoint so all URLs emit identical hints.
_tool_annotations = tool_annotations


def _server_version() -> str:
    """Hub version reported as serverInfo.version (pyproject, cached)."""
    global _SERVER_VERSION
    if _SERVER_VERSION is None:
        try:
            from core.dashboard.routes import _get_project_version

            _SERVER_VERSION = _get_project_version()
        except Exception:  # noqa: BLE001
            _SERVER_VERSION = "unknown"
    return _SERVER_VERSION


_SERVER_VERSION: str | None = None


def _check_user_rate_limit(user_id: str) -> tuple[bool, str]:
    """Check per-user rate limits using the live cached settings (DB > ENV > default).

    Args:
        user_id: User UUID.

    Returns:
        Tuple of (allowed, error_message). error_message is empty if allowed.
    """
    from core.settings import get_cached_rate_per_hr, get_cached_rate_per_min

    per_min = get_cached_rate_per_min()
    per_hr = get_cached_rate_per_hr()

    now = time.time()
    timestamps = _rate_limits.setdefault(user_id, [])

    # Prune old entries (older than 1 hour)
    cutoff_hr = now - 3600
    _rate_limits[user_id] = [t for t in timestamps if t > cutoff_hr]
    timestamps = _rate_limits[user_id]

    # Check per-minute limit
    cutoff_min = now - 60
    recent_min = sum(1 for t in timestamps if t > cutoff_min)
    if recent_min >= per_min:
        return False, f"Rate limit exceeded: {per_min} requests/minute"

    # Check per-hour limit
    if len(timestamps) >= per_hr:
        return False, f"Rate limit exceeded: {per_hr} requests/hour"

    timestamps.append(now)
    return True, ""


def _tools_to_mcp_schema(
    tools: list[ToolDefinition],
    *,
    configured_providers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Convert ToolDefinition objects into MCP ``tools/list`` response shape.

    Strips the auto-injected ``site`` parameter, since user endpoints bind a
    single site per alias.

    F.X.fix-pass6 — when ``configured_providers`` is given (i.e. the
    site has at least one AI provider key configured), narrow the
    ``provider`` enum on the AI image tool to that subset. The model
    only sees providers that will actually succeed, instead of trying
    OpenAI / Stability / Replicate and getting NO_PROVIDER_KEY when
    only OpenRouter is configured.
    """
    ai_image_tools = {
        "wordpress_generate_and_upload_image",
        "woocommerce_generate_and_upload_image",
    }
    result = []
    for tool_def in tools:
        schema = deepcopy(tool_def.input_schema)
        if "properties" in schema:
            schema["properties"].pop("site", None)
        if "required" in schema and "site" in schema["required"]:
            schema["required"] = [r for r in schema["required"] if r != "site"]

        if (
            configured_providers
            and tool_def.name in ai_image_tools
            and "properties" in schema
            and "provider" in schema["properties"]
        ):
            schema["properties"]["provider"] = {
                **schema["properties"]["provider"],
                "enum": list(configured_providers),
                "description": (
                    "AI provider to use. This site has the following providers "
                    f"configured: {', '.join(configured_providers)}. Add more "
                    "in Connection Settings → AI Image Generation."
                ),
            }

        result.append(
            {
                "name": tool_def.name,
                "description": tool_def.description,
                "inputSchema": schema,
                "title": humanize_title(tool_def),
                "annotations": _tool_annotations(tool_def),
            }
        )
    return result


async def _get_visible_tools_for_site(
    site_id: str,
    key_scopes: list[str],
    plugin_type: str,
    credentials: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return tools/list payload filtered by key scope + site scope + toggles (F.7b).

    F.5a.9.x: additionally hide ``wordpress_generate_and_upload_image`` when
    the site has no provider API key configured — the tool would fail at
    call-time with ``NO_PROVIDER_KEY`` anyway, so hiding it keeps the
    surface honest for AI clients.
    """
    from core.tool_access import get_tool_access_manager

    access = get_tool_access_manager()
    tools = await access.get_visible_tools(
        site_id=site_id, key_scopes=key_scopes, plugin_type=plugin_type
    )

    if plugin_type == "coolify" and credentials:
        from core.coolify_policy import filter_coolify_tools_by_policy

        tools = filter_coolify_tools_by_policy(tools, credentials)

    configured_providers: list[str] = []
    if plugin_type in {"wordpress", "woocommerce"}:
        from core.site_api import list_site_providers_set

        configured = await list_site_providers_set(site_id)
        if not configured:
            tools = [
                t
                for t in tools
                if t.name
                not in {
                    "wordpress_generate_and_upload_image",
                    "woocommerce_generate_and_upload_image",
                }
            ]
        else:
            # F.X.fix-pass6 — pass the configured set so the AI image
            # tool's `provider` enum can be narrowed at /tools/list time.
            configured_providers = sorted(configured)

    return _tools_to_mcp_schema(tools, configured_providers=configured_providers)


async def _execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    plugin_type: str,
    config_dict: dict[str, Any],
) -> Any:
    """Execute a tool by creating a plugin instance and calling the method.

    Uses the same pattern as unified_handler in tool_generator.py.
    """
    from plugins import registry as plugin_registry

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

    # Shared scope tracking — set by whichever auth path succeeds
    key_scopes: list[str] = []

    # Try mhu_ API key first, then fall back to OAuth JWT token
    if api_key.startswith("mhu_"):
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

        if key_info["user_id"] != user_id:
            return JSONResponse(
                _jsonrpc_error(None, -32600, "API key does not match user"),
                status_code=403,
            )

        # Check site-scoped key: if key is scoped to a site, it can only
        # be used for that specific site's alias.
        key_site_id = key_info.get("site_id")
        if key_site_id:
            try:
                from core.database import get_database

                db = get_database()
                site = await db.get_site(key_site_id, user_id)
                if site is None or site.get("alias") != alias:
                    return JSONResponse(
                        _jsonrpc_error(
                            None,
                            -32600,
                            "API key is scoped to a different site",
                        ),
                        status_code=403,
                    )
            except RuntimeError:
                # A site-scoped key cannot be authorized without checking its
                # bound site. Fail closed when the boundary store is unavailable.
                return JSONResponse(
                    _jsonrpc_error(None, -32600, "Authorization service unavailable"),
                    status_code=503,
                )

        key_scopes = key_info.get("scopes", "read").split()
    else:
        # Try OAuth JWT token (issued after consent flow via GitHub/Google login)
        try:
            import jwt as pyjwt

            from core.oauth import get_token_manager

            token_manager = get_token_manager()
            jwt_payload = token_manager.validate_access_token(api_key)

            # sub = "user:{uuid}" — extract actual user_id
            sub = jwt_payload.get("sub", "")
            if not sub.startswith("user:"):
                return JSONResponse(
                    _jsonrpc_error(None, -32600, "Token not authorized for user endpoint"),
                    status_code=403,
                )
            jwt_user_id = sub[len("user:") :]

            if jwt_user_id != user_id:
                return JSONResponse(
                    _jsonrpc_error(None, -32600, "Token user mismatch"),
                    status_code=403,
                )
            key_scopes = jwt_payload.get("scope", "read").split()
        except pyjwt.ExpiredSignatureError:
            return JSONResponse(
                _jsonrpc_error(None, -32600, "Token expired"),
                status_code=401,
            )
        except Exception:
            return JSONResponse(
                _jsonrpc_error(None, -32600, "Invalid token"),
                status_code=401,
            )

    # --- Rate Limiting (admin users are exempt) ---
    # Fetch the user record early so we can check the role; it's also needed
    # for the plugin-visibility check below, so we hoist it here.
    _db_early = None
    _user_record_early: dict | None = None
    try:
        from core.database import get_database

        _db_early = get_database()
        _user_record_early = await _db_early.get_user_by_id(user_id)
    except Exception:
        pass

    _is_admin_user = False
    if isinstance(_user_record_early, dict):
        from core.admin_utils import is_admin_email

        _is_admin_user = (_user_record_early.get("role") == "admin") or is_admin_email(
            _user_record_early.get("email")
        )

    if not _is_admin_user:
        allowed, rate_msg = _check_user_rate_limit(user_id)
        if not allowed:
            return JSONResponse(
                _jsonrpc_error(None, -32600, rate_msg),
                status_code=429,
            )

    # --- Look up site ---
    try:
        from core.database import get_database

        db = _db_early if _db_early is not None else get_database()
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

    # --- Plugin visibility check (admins bypass entirely) ---
    from core.plugin_visibility import is_plugin_public

    if not _is_admin_user and not is_plugin_public(site["plugin_type"]):
        return JSONResponse(
            _jsonrpc_error(
                None,
                -32600,
                f"Plugin '{site['plugin_type']}' is not currently available",
            ),
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
    if not isinstance(params, dict):
        params = {}

    # --- Protocol version (dual-era: legacy initialize + modern 2026-07-28) ---
    from core import mcp_protocol

    server_info = {"name": f"mcphub-{alias}", "version": _server_version()}
    declared = (
        None if method == "initialize" else mcp_protocol.declared_version(params, request.headers)
    )
    if declared is not None and declared not in mcp_protocol.SUPPORTED_VERSIONS:
        return JSONResponse(
            mcp_protocol.unsupported_version_error(req_id, declared), status_code=400
        )
    modern = mcp_protocol.is_modern(declared)

    def _result(payload: dict[str, Any], *, ttl_ms: int | None = None) -> JSONResponse:
        if modern:
            payload = mcp_protocol.decorate_modern_result(payload, server_info, ttl_ms=ttl_ms)
        return JSONResponse(_jsonrpc_result(req_id, payload))

    # --- Handle MCP methods ---

    if method == "initialize":
        return JSONResponse(
            _jsonrpc_result(
                req_id,
                {
                    "protocolVersion": mcp_protocol.negotiate_legacy_version(
                        params.get("protocolVersion")
                    ),
                    "capabilities": {"tools": {}},
                    "serverInfo": server_info,
                },
            )
        )

    elif method == "server/discover":
        return JSONResponse(_jsonrpc_result(req_id, mcp_protocol.discover_result(server_info)))

    elif method == "notifications/initialized":
        # Notification — no response needed
        return Response(status_code=204)

    elif method == "tools/list":
        credentials_for_policy: dict[str, Any] | None = None
        if site["plugin_type"] == "coolify":
            try:
                from core.encryption import get_credential_encryption

                encryptor = get_credential_encryption()
                credentials_for_policy = encryptor.decrypt_credentials(
                    site["credentials"], site["id"]
                )
            except Exception as exc:  # non-fatal — preserve existing list flow
                logger.warning(
                    "Failed to decrypt Coolify credentials for tools/list policy on site %s: %s",
                    site["id"],
                    exc,
                )
        tools = await _get_visible_tools_for_site(
            site["id"], key_scopes, site["plugin_type"], credentials_for_policy
        )
        return _result({"tools": tools}, ttl_ms=mcp_protocol.TOOLS_LIST_TTL_MS)

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        from core.tool_access import get_tool_access_manager

        access = get_tool_access_manager()
        try:
            tool_def, decision = await access.authorize_tool_for_site(
                site_id=site["id"],
                key_scopes=key_scopes,
                plugin_type=site["plugin_type"],
                tool_name=tool_name,
                principal_id_safe=user_id,
                arguments=arguments,
            )
        except LookupError:
            return JSONResponse(
                _jsonrpc_error(
                    req_id,
                    -32601,
                    f"Tool '{tool_name}' is not available for this site",
                )
            )

        if tool_def is None or not decision.allow:
            reason = getattr(decision, "reason", "Tool authorization denied")
            reason_code = getattr(decision, "reason_code", "")
            if reason_code == "INSUFFICIENT_SCOPE":
                message = f"Insufficient scope: {reason}"
            else:
                message = f"Tool not authorized: {reason}"
            return JSONResponse(_jsonrpc_error(req_id, -32003, message))

        # The registry definition, not the request name, is authoritative for
        # plugin ownership and all scope/site/toggle/prerequisite checks.
        plugin_type = tool_def.plugin_type
        if plugin_type != site["plugin_type"]:
            return JSONResponse(
                _jsonrpc_error(req_id, -32601, f"Tool '{tool_name}' not available for this site")
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
        # F.5a.4: pass user_id so plugins can look up per-user secrets.
        # F.5a.9.x: pass site_id so the WP AI-media handler can resolve
        # per-site provider API keys (replaces per-user keys for
        # wordpress_generate_and_upload_image).
        config_dict = {
            "site_url": site["url"],
            "url": site["url"],
            "alias": alias,
            "user_id": user_id,
            "site_id": site["id"],
            **credentials,
        }

        # OAuth-based plugins (google_search_console) store only
        # access_token / refresh_token / token_expires_at in per-site
        # credentials.  The plugin's client needs client_id and
        # client_secret to refresh expired access tokens.  These come from
        # the server-wide GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET env vars
        # — the same pair used by the site OAuth flow itself.
        # Gmail uses manual credentials (client_id/secret/refresh_token
        # entered by the owner), so it is NOT included here.
        if site["plugin_type"] == "google_search_console":
            google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
            google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
            if google_client_id:
                config_dict.setdefault("client_id", google_client_id)
            if google_client_secret:
                config_dict.setdefault("client_secret", google_client_secret)

        if site["plugin_type"] == "coolify":
            from core.coolify_policy import is_coolify_tool_allowed

            allowed_by_policy, deny_reason = is_coolify_tool_allowed(
                tool_def, arguments, credentials
            )
            if not allowed_by_policy:
                return JSONResponse(
                    _jsonrpc_error(
                        req_id,
                        -32600,
                        f"Tool '{tool_name}' is disabled by Coolify site policy: {deny_reason}",
                    )
                )

        # SSRF boundary: every outbound request made while executing this tool
        # targets the user-supplied site URL. Non-admin sites may only reach
        # public addresses — enforced at connect time, so redirects and DNS
        # rebinding are covered too. Admin-owned sites keep private access
        # (same trust boundary as the admin rate-limit/visibility exemptions).
        from core.net_guard import allow_private_destinations

        with allow_private_destinations(_is_admin_user):
            result = await _execute_tool(tool_name, arguments, site["plugin_type"], config_dict)

            if site["plugin_type"] == "coolify":
                from core.coolify_policy import filter_coolify_result_by_policy
                from plugins.coolify.client import CoolifyClient

                policy_client = CoolifyClient(site["url"], credentials["token"])
                policy_cache: dict[str, Any] = {}
                result = await filter_coolify_result_by_policy(
                    tool_name,
                    result,
                    credentials,
                    policy_client,
                    policy_cache,
                )

        # Format result as MCP content
        if isinstance(result, str):
            content = [{"type": "text", "text": result}]
        elif isinstance(result, dict) and "type" in result:
            content = [result]
        elif isinstance(result, list):
            content = result
        else:
            content = [{"type": "text", "text": json.dumps(result, default=str)}]

        return _result({"content": content})

    else:
        return JSONResponse(_jsonrpc_error(req_id, -32601, f"Method '{method}' not supported"))
