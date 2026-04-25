"""F.18.4 — Cache purge via companion plugin.

Wraps ``POST /airano-mcp/v1/cache-purge`` (companion plugin v2.4.0+).
Auto-detects active cache plugins (LiteSpeed, WP Rocket, W3 Total Cache,
WP Super Cache, WP Fastest Cache, SiteGround Optimizer) and invokes
their purge API. Always flushes the WP object cache. Replaces the
previous Docker-socket + WP-CLI path on managed hosts.

Tool: ``wordpress_cache_purge()``
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.cache_purge")


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "cache_purge",
            "method_name": "cache_purge",
            "description": (
                "Purge all caches on the WordPress site via the "
                "airano-mcp-bridge companion plugin (v2.4.0+). Auto-detects "
                "active cache plugins (LiteSpeed, WP Rocket, W3 Total Cache, "
                "WP Super Cache, WP Fastest Cache, SiteGround Optimizer) and "
                "calls each one's purge API. Always flushes the object cache. "
                "Requires manage_options on the calling application password."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "admin",
        }
    ]


class CachePurgeHandler:
    """Cache purge via companion plugin."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def cache_purge(self) -> str:
        try:
            payload = await self.client.post(
                "airano-mcp/v1/cache-purge",
                json_data={},
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("cache_purge companion call failed: %s", exc)
            return json.dumps(
                {
                    "ok": False,
                    "error": "companion_unreachable",
                    "message": str(exc),
                    "hint": (
                        "Requires airano-mcp-bridge companion plugin v2.4.0+ "
                        "and manage_options capability. Run "
                        "wordpress_probe_capabilities to verify."
                    ),
                    "install_hint": _companion_install_hint(
                        min_version="2.4.0",
                        required_capability="manage_options",
                        route="airano-mcp/v1/cache-purge",
                    ),
                    "detected": [],
                    "purged": [],
                    "errors": [],
                },
                indent=2,
            )

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                    "detected": [],
                    "purged": [],
                    "errors": [],
                },
                indent=2,
            )

        # Pass through + normalise.
        detected = list(payload.get("detected") or [])
        purged = list(payload.get("purged") or [])
        errors = list(payload.get("errors") or [])
        ok = bool(payload.get("ok", not errors))

        result = {
            "ok": ok,
            "detected": detected,
            "purged": purged,
            "skipped": list(payload.get("skipped") or []),
            "errors": errors,
            "plugin_version": payload.get("plugin_version"),
        }
        return json.dumps(result, indent=2)
