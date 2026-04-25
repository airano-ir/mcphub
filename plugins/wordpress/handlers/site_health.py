"""F.18.6 — Unified site-health snapshot via companion plugin.

Wraps ``GET /airano-mcp/v1/site-health`` (companion plugin v2.6.0+).
Returns WordPress / PHP / server / database / plugins / theme /
writability info in a single JSON envelope. Replaces the existing
``get_site_health`` (which called the stock ``/wp-site-health`` REST
endpoints) with a richer single-round-trip snapshot.

The legacy ``wordpress_get_site_health`` tool (site.py) is left intact;
this adds a new ``wordpress_site_health`` tool that prefers the
companion and gracefully reports ``companion_available: false`` when
the plugin is missing or outdated.

Tool: ``wordpress_site_health()``
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.site_health")


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "site_health",
            "method_name": "site_health",
            "description": (
                "Unified site-health snapshot via the airano-mcp-bridge "
                "companion plugin (v2.6.0+). Single request returns WP + PHP + "
                "MySQL versions, loaded PHP extensions, server software + disk "
                "free, active plugins with versions, active theme, and "
                "writability checks. Falls back to `companion_available: false` "
                "when the plugin is missing. Requires manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        }
    ]


class SiteHealthHandler:
    """Unified site-health snapshot via companion plugin."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def site_health(self) -> str:
        try:
            payload = await self.client.get(
                "airano-mcp/v1/site-health",
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("site_health companion call failed: %s", exc)
            return json.dumps(
                {
                    "ok": False,
                    "companion_available": False,
                    "error": "companion_unreachable",
                    "message": str(exc),
                    "hint": (
                        "Requires airano-mcp-bridge companion plugin v2.6.0+ "
                        "and manage_options capability. Run "
                        "wordpress_probe_capabilities to verify. For the legacy "
                        "path use wordpress_get_site_health (stock WP endpoints)."
                    ),
                    "install_hint": _companion_install_hint(
                        min_version="2.6.0",
                        required_capability="manage_options",
                        route="airano-mcp/v1/site-health",
                    ),
                },
                indent=2,
            )

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "companion_available": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                },
                indent=2,
            )

        result = {
            "ok": bool(payload.get("ok", True)),
            "companion_available": True,
            **payload,
        }
        return json.dumps(result, indent=2)
