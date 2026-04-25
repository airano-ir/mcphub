"""F.18.5 — Transient flush via companion plugin.

Wraps ``POST /airano-mcp/v1/transient-flush`` (companion plugin v2.5.0+).
Native PHP transient cleanup. Scopes:

- ``expired`` (default): runs ``delete_expired_transients()``; reports
  the number of expired rows removed.
- ``all``: deletes every ``_transient_%`` row (both regular and
  optionally site transients on multisite).
- ``pattern``: shell-glob match, e.g. ``rank_math_*``.

Tool: ``wordpress_transient_flush(scope="expired", pattern=None, ...)``
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.transient_flush")

_VALID_SCOPES = ("expired", "all", "pattern")


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "transient_flush",
            "method_name": "transient_flush",
            "description": (
                "Flush WordPress transients via the airano-mcp-bridge "
                "companion plugin (v2.5.0+). Scopes: 'expired' (default, "
                "delete_expired_transients), 'all' (every transient), "
                "'pattern' (shell glob like 'rank_math_*'). On multisite, "
                "`include_site_transients=true` also purges "
                "_site_transient_* rows. Requires manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": list(_VALID_SCOPES),
                        "description": "Default 'expired'.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": (
                            "Shell-style glob (e.g. 'rank_math_*'). Required "
                            "when scope='pattern'."
                        ),
                    },
                    "include_site_transients": {
                        "type": "boolean",
                        "description": "Default true. Only relevant on multisite.",
                    },
                },
            },
            "scope": "admin",
        }
    ]


def _validate(scope: str | None, pattern: str | None) -> dict[str, Any] | None:
    if scope is None:
        scope = "expired"
    if scope not in _VALID_SCOPES:
        return {
            "error": "invalid_scope",
            "message": (f"scope must be one of {list(_VALID_SCOPES)}; got {scope!r}."),
        }
    if scope == "pattern" and not pattern:
        return {
            "error": "pattern_required",
            "message": "pattern is required when scope='pattern'.",
        }
    return None


class TransientFlushHandler:
    """Native PHP transient cleanup via companion plugin."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def transient_flush(
        self,
        scope: str | None = "expired",
        pattern: str | None = None,
        include_site_transients: Any = True,
    ) -> str:
        err = _validate(scope, pattern)
        if err is not None:
            return json.dumps(
                {
                    "ok": False,
                    **err,
                    "scope": scope,
                    "pattern": pattern,
                    "deleted_count": 0,
                    "deleted_sample": [],
                },
                indent=2,
            )

        # Normalise include_site_transients to a real bool for the PHP side;
        # WP's parser is lenient but the aiohttp JSON filter elsewhere in
        # the client may drop "false"-y strings.
        include_flag: bool
        if isinstance(include_site_transients, bool):
            include_flag = include_site_transients
        elif isinstance(include_site_transients, (int, float)):
            include_flag = bool(include_site_transients)
        elif isinstance(include_site_transients, str):
            include_flag = include_site_transients.strip().lower() not in {
                "false",
                "0",
                "no",
                "off",
                "",
            }
        else:
            include_flag = True

        body: dict[str, Any] = {
            "scope": scope or "expired",
            "include_site_transients": include_flag,
        }
        if scope == "pattern":
            body["pattern"] = pattern

        try:
            payload = await self.client.post(
                "airano-mcp/v1/transient-flush",
                json_data=body,
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("transient_flush companion call failed: %s", exc)
            return json.dumps(
                {
                    "ok": False,
                    "error": "companion_unreachable",
                    "message": str(exc),
                    "hint": (
                        "Requires airano-mcp-bridge companion plugin v2.5.0+ "
                        "and manage_options capability. Run "
                        "wordpress_probe_capabilities to verify."
                    ),
                    "install_hint": _companion_install_hint(
                        min_version="2.5.0",
                        required_capability="manage_options",
                        route="airano-mcp/v1/transient-flush",
                    ),
                    "scope": scope,
                    "pattern": pattern,
                    "deleted_count": 0,
                    "deleted_sample": [],
                },
                indent=2,
            )

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                    "scope": scope,
                    "pattern": pattern,
                    "deleted_count": 0,
                    "deleted_sample": [],
                },
                indent=2,
            )

        result = {"ok": bool(payload.get("ok", True)), **payload}
        return json.dumps(result, indent=2)
