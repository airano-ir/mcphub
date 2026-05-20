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
import time
from copy import deepcopy
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.tool_registry import ToolDefinition

logger = logging.getLogger(__name__)

# In-memory rate limit tracking: user_id -> list of timestamps
_rate_limits: dict[str, list[float]] = {}


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
            }
        )
    return result


async def _get_visible_tools_for_site(
    site_id: str,
    key_scopes: list[str],
    plugin_type: str,
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
                pass  # DB unavailable — allow through

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
    if _user_record_early:
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
        tools = await _get_visible_tools_for_site(site["id"], key_scopes, site["plugin_type"])
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
            return JSONResponse(_jsonrpc_error(req_id, -32601, f"Tool '{tool_name}' not found"))

        required_scope = tool_def.required_scope
        # key_scopes is set during authentication (both mhu_ and JWT paths)

        # F.7b: enforce category-based scope allowlist in addition to the
        # universal scope tier. A tool is allowed only if BOTH
        #   (a) the universal scope tier grants it (works for every plugin), AND
        #   (b) for plugins with fine-grained categories (Coolify), the
        #       tool's category is in BOTH the key-scope set AND the site's
        #       stored tool_scope set (the narrower layer wins).
        from core.tool_access import (
            KNOWN_CATEGORIES,
            SCOPE_CUSTOM,
            UNIVERSAL_SCOPE_TIERS,
            scopes_to_categories,
        )

        # F.19.5 introduced the ``editor`` tier (between ``read`` and
        # ``write``). The legacy 3-level hierarchy here ({read:1, write:2,
        # admin:3}) silently dropped ``editor`` to level 0, which made
        # every tool call from an editor-scope key fail "Insufficient
        # scope". Use the canonical UNIVERSAL_SCOPE_TIERS map from
        # tool_access so this list stays single-sourced as new tiers
        # land (F.19.2 introduces ``manage`` / ``install`` next).
        allowed_scopes: set[str] = set()
        for s in key_scopes:
            allowed_scopes |= UNIVERSAL_SCOPE_TIERS.get(s.strip(), set())
        legacy_ok = required_scope in allowed_scopes

        plugin_type = tool_def.plugin_type
        # Category check is for plugins with fine-grained categories
        # (currently Coolify only). For other plugins ``tool_def.category``
        # defaults to ``"read"`` which collides with one of Coolify's
        # KNOWN_CATEGORIES — running the check against non-Coolify tools
        # mis-rejected wordpress_specialist + wordpress + gitea tools when
        # the key scope didn't happen to map to category "read".
        if plugin_type == "coolify":
            key_cats = scopes_to_categories(key_scopes)
            key_category_ok = (
                tool_def.category not in KNOWN_CATEGORIES or tool_def.category in key_cats
            )
        else:
            key_category_ok = True

        # Site-level scope check (skipped for "custom" preset).
        site_scope = site.get("tool_scope") or "admin"
        if site_scope and site_scope != SCOPE_CUSTOM:
            if plugin_type == "coolify":
                site_cats = scopes_to_categories([site_scope])
                site_category_ok = (
                    tool_def.category not in KNOWN_CATEGORIES or tool_def.category in site_cats
                )
            else:
                # Non-Coolify plugins use the universal tier at site level
                # too — site_scope is one of ``read`` / ``editor`` / ``write``
                # / ``admin`` / ``custom``, same vocabulary as the key.
                site_allowed = UNIVERSAL_SCOPE_TIERS.get(site_scope, set())
                site_category_ok = required_scope in site_allowed
        else:
            site_category_ok = True

        if not (legacy_ok and key_category_ok and site_category_ok):
            return JSONResponse(
                _jsonrpc_error(
                    req_id,
                    -32600,
                    f"Insufficient scope. Tool '{tool_name}' requires "
                    f"scope '{required_scope}' (category '{tool_def.category}').",
                )
            )

        # F.7b: honour per-site tool toggles — a disabled tool cannot be called
        # even if scopes would otherwise allow it.
        try:
            toggles = await db.get_site_tool_toggles(site["id"])
            if not toggles.get(tool_name, True):
                return JSONResponse(
                    _jsonrpc_error(
                        req_id,
                        -32600,
                        f"Tool '{tool_name}' is disabled for this site.",
                    )
                )
        except Exception as exc:  # non-fatal — fall through on DB errors
            logger.warning("Failed to check site tool toggles for %s: %s", site["id"], exc)

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
