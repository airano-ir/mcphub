"""Legacy WordPress admin tool names backed by companion REST routes.

These specs keep a small set of historically exposed ``wordpress_wp_*``
tool names working through Application Password + companion-plugin
transports. Do not add server-shell tools here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import companion_install_hint

logger = logging.getLogger("mcphub.wordpress.legacy_admin")

_ADMIN_NS = "airano-mcp/v1/admin"


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return companion-backed legacy tool specifications."""
    return [
        {
            "name": "wp_cache_flush",
            "method_name": "wp_cache_flush",
            "description": (
                "Flush WordPress caches through the Airano MCP Bridge companion "
                "plugin. Supports object cache, page cache, or both without "
                "server-side shell access."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "Which cache layer to flush.",
                        "enum": ["object", "page", "all"],
                        "default": "all",
                    }
                },
            },
            "scope": "write",
        },
        {
            "name": "wp_transient_delete_all",
            "method_name": "wp_transient_delete_all",
            "description": (
                "Delete expired WordPress transients through the companion "
                "plugin. This mirrors the legacy tool's expired-only cleanup "
                "semantics."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "admin",
        },
        {
            "name": "wp_transient_list",
            "method_name": "wp_transient_list",
            "description": (
                "List WordPress transients through the companion plugin. "
                "Returns names, type, and expiration metadata without reading "
                "transient values."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 100,
                        "description": "Maximum transients to return.",
                    },
                    "include_site_transients": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include multisite site transients when available.",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "wp_db_check",
            "method_name": "wp_db_check",
            "description": (
                "Check WordPress database tables through the companion plugin. "
                "Runs CHECK TABLE only on tables with the current WordPress "
                "table prefix."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_db_optimize",
            "method_name": "wp_db_optimize",
            "description": (
                "Optimize WordPress database tables through the companion "
                "plugin. Runs OPTIMIZE TABLE only on tables with the current "
                "WordPress table prefix."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "admin",
        },
    ]


def _result_json(payload: Any, *, action: str) -> str:
    if not isinstance(payload, dict):
        return json.dumps(
            {
                "ok": False,
                "error": "invalid_response",
                "message": f"companion returned a non-object payload for {action}",
            },
            indent=2,
        )
    return json.dumps({"ok": bool(payload.get("ok", True)), **payload}, indent=2)


def _companion_error_json(exc: Exception, *, action: str, route: str) -> str:
    return json.dumps(
        {
            "ok": False,
            "error": "companion_unreachable",
            "message": str(exc),
            "hint": (
                "Requires airano-mcp-bridge companion plugin v2.18.5+ "
                "and manage_options capability. Run wordpress_probe_capabilities "
                "to verify."
            ),
            "install_hint": companion_install_hint(
                min_version="2.18.5",
                required_capability="manage_options",
                route=route,
            ),
            "action": action,
        },
        indent=2,
    )


class LegacyAdminHandler:
    """Companion-backed replacements for safe legacy admin tool names."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def wp_db_check(self, **_: Any) -> str:
        route = f"{_ADMIN_NS}/db/check"
        try:
            payload = await self.client.get(route, use_custom_namespace=True)
        except Exception as exc:  # noqa: BLE001
            logger.error("legacy wp_db_check companion call failed: %s", exc)
            return _companion_error_json(exc, action="wp_db_check", route=route)
        return _result_json(payload, action="wp_db_check")

    async def wp_db_optimize(self, **_: Any) -> str:
        route = f"{_ADMIN_NS}/db/optimize"
        try:
            payload = await self.client.post(route, json_data={}, use_custom_namespace=True)
        except Exception as exc:  # noqa: BLE001
            logger.error("legacy wp_db_optimize companion call failed: %s", exc)
            return _companion_error_json(exc, action="wp_db_optimize", route=route)
        return _result_json(payload, action="wp_db_optimize")
