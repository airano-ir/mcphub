"""F.18.8 — Reset PHP OPcache via companion plugin.

Wraps ``POST /airano-mcp/v1/opcache-reset`` (companion plugin v2.18.4+).
This gives public, companion-only MCPHub deployments a safe replacement for
restart-based UI deploy loops when ``opcache.validate_timestamps=0``.

Tool: ``wordpress_opcache_reset()``
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.opcache")


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "opcache_reset",
            "method_name": "opcache_reset",
            "description": (
                "Reset PHP OPcache on the WordPress origin via the "
                "airano-mcp-bridge companion plugin (v2.18.4+). Useful after "
                "deploying theme/plugin PHP changes on hosts with "
                "opcache.validate_timestamps disabled. Requires manage_options "
                "on the calling application password."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "admin",
        }
    ]


class OpcacheHandler:
    """OPcache reset via companion plugin."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def opcache_reset(self) -> str:
        try:
            payload = await self.client.post(
                "airano-mcp/v1/opcache-reset",
                json_data={},
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("opcache_reset companion call failed: %s", exc)
            return json.dumps(
                {
                    "ok": False,
                    "error": "companion_unreachable",
                    "message": str(exc),
                    "hint": (
                        "Requires airano-mcp-bridge companion plugin v2.18.4+ "
                        "and manage_options capability. Run "
                        "wordpress_probe_capabilities to verify."
                    ),
                    "install_hint": _companion_install_hint(
                        min_version="2.18.4",
                        required_capability="manage_options",
                        route="airano-mcp/v1/opcache-reset",
                    ),
                },
                indent=2,
            )

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                },
                indent=2,
            )

        result = {
            "ok": bool(payload.get("ok", payload.get("reset", False))),
            "reset": bool(payload.get("reset", payload.get("ok", False))),
            "opcache_available": bool(payload.get("opcache_available", False)),
            "enabled": payload.get("enabled"),
            "validate_timestamps": payload.get("validate_timestamps"),
            "status_before": payload.get("status_before"),
            "status_after": payload.get("status_after"),
            "message": payload.get("message"),
            "plugin_version": payload.get("plugin_version"),
        }
        return json.dumps(result, indent=2)
