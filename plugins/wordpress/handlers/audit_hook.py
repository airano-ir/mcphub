"""F.18.7 — Manage the companion plugin's audit-hook webhook config.

Wraps ``GET|POST|DELETE /airano-mcp/v1/audit-hook`` (companion plugin
v2.7.0+). Three tools:

- ``wordpress_audit_hook_status`` (read): returns current config + stats.
- ``wordpress_audit_hook_configure`` (admin): upserts endpoint_url / secret /
  enabled / events.
- ``wordpress_audit_hook_disable`` (admin): clears config and stops pushing.

The actual event receiver lives in ``core/companion_audit.py``; this
module only manages the per-site configuration on the WordPress side.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.audit_hook")

SUPPORTED_EVENTS = (
    "transition_post_status",
    "deleted_post",
    "user_register",
    "profile_update",
    "deleted_user",
    "activated_plugin",
    "deactivated_plugin",
    "switch_theme",
)


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "audit_hook_status",
            "method_name": "audit_hook_status",
            "description": (
                "Read the companion plugin's audit-hook configuration "
                "(v2.7.0+): current endpoint_url, whether a secret is set, "
                "enabled flag, event list, last-push timestamp, failure "
                "count. Secret is never returned in full — only the last 4 "
                "characters. Requires manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "audit_hook_configure",
            "method_name": "audit_hook_configure",
            "description": (
                "Configure the companion plugin's audit-hook webhook. Sets "
                "the MCPHub endpoint_url, shared HMAC secret (≥16 chars), "
                "enabled flag, and list of hooked events. Returns the "
                "resulting status. Requires manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "endpoint_url": {
                        "type": "string",
                        "description": (
                            "Full URL to MCPHub's /api/companion-audit "
                            "route (e.g. https://mcp.example.com/api/companion-audit)."
                        ),
                    },
                    "secret": {
                        "type": "string",
                        "description": (
                            "HMAC-SHA256 shared secret (≥16 chars). Store "
                            "the identical value in MCPHub's "
                            "CompanionAuditSecretStore for this site."
                        ),
                    },
                    "enabled": {"type": "boolean"},
                    "events": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(SUPPORTED_EVENTS)},
                        "description": (
                            "List of WP action hooks to forward. Default: " "all supported events."
                        ),
                    },
                },
            },
            "scope": "admin",
        },
        {
            "name": "audit_hook_disable",
            "method_name": "audit_hook_disable",
            "description": (
                "Clear the companion plugin's audit-hook configuration "
                "(endpoint_url, secret, events) and stop forwarding events. "
                "Requires manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "admin",
        },
    ]


def _validate_configure(
    *,
    endpoint_url: str | None,
    secret: str | None,
    enabled: Any,
    events: Any,
) -> dict[str, Any] | None:
    # endpoint_url: allow empty-string to mean "clear" on the PHP side,
    # but reject obviously-broken inputs client-side.
    if (
        endpoint_url is not None
        and endpoint_url
        and not endpoint_url.startswith(("http://", "https://"))
    ):
        return {
            "error": "invalid_endpoint_url",
            "message": "endpoint_url must start with http:// or https://",
        }
    if secret is not None and secret != "" and len(secret) < 16:
        return {
            "error": "secret_too_short",
            "message": "shared secret must be at least 16 characters",
        }
    if events is not None:
        if not isinstance(events, list):
            return {
                "error": "invalid_events",
                "message": "events must be a list of known event names",
            }
        for e in events:
            if not isinstance(e, str) or e not in SUPPORTED_EVENTS:
                return {
                    "error": "unknown_event",
                    "message": f"event {e!r} is not supported",
                    "supported": list(SUPPORTED_EVENTS),
                }
    if enabled is not None and not isinstance(enabled, bool):
        return {
            "error": "invalid_enabled",
            "message": "enabled must be true or false",
        }
    return None


def _unreachable(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "companion_unreachable",
        "message": str(exc),
        "hint": (
            "Requires airano-mcp-bridge companion plugin v2.7.0+ and "
            "manage_options capability. Run wordpress_probe_capabilities "
            "to verify availability."
        ),
        "install_hint": _companion_install_hint(
            min_version="2.7.0",
            required_capability="manage_options",
            route="airano-mcp/v1/audit-hook",
        ),
    }


class AuditHookHandler:
    """Configure + query the companion plugin's audit-hook webhook."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def audit_hook_status(self) -> str:
        try:
            payload = await self.client.get(
                "airano-mcp/v1/audit-hook",
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("audit_hook_status companion call failed: %s", exc)
            return json.dumps(_unreachable(exc), indent=2)

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                },
                indent=2,
            )
        return json.dumps({"ok": True, **payload}, indent=2)

    async def audit_hook_configure(
        self,
        endpoint_url: str | None = None,
        secret: str | None = None,
        enabled: Any = None,
        events: Any = None,
    ) -> str:
        err = _validate_configure(
            endpoint_url=endpoint_url,
            secret=secret,
            enabled=enabled,
            events=events,
        )
        if err is not None:
            return json.dumps({"ok": False, **err}, indent=2)

        body: dict[str, Any] = {}
        if endpoint_url is not None:
            body["endpoint_url"] = endpoint_url
        if secret is not None:
            body["secret"] = secret
        if enabled is not None:
            body["enabled"] = bool(enabled)
        if events is not None:
            body["events"] = list(events)

        if not body:
            return json.dumps(
                {
                    "ok": False,
                    "error": "no_fields",
                    "message": (
                        "Provide at least one of: endpoint_url, secret, " "enabled, events."
                    ),
                },
                indent=2,
            )

        try:
            payload = await self.client.post(
                "airano-mcp/v1/audit-hook",
                json_data=body,
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("audit_hook_configure companion call failed: %s", exc)
            return json.dumps(_unreachable(exc), indent=2)

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                },
                indent=2,
            )
        return json.dumps({"ok": True, **payload}, indent=2)

    async def audit_hook_disable(self) -> str:
        try:
            payload = await self.client.delete(
                "airano-mcp/v1/audit-hook",
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("audit_hook_disable companion call failed: %s", exc)
            return json.dumps(_unreachable(exc), indent=2)

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                },
                indent=2,
            )
        return json.dumps({"ok": True, **payload}, indent=2)
