"""F.5a.8.2 — Regenerate attachment thumbnails via companion plugin.

Wraps ``POST /airano-mcp/v1/regenerate-thumbnails`` (companion plugin v2.8.0+).
Rebuilds the registered WP image sub-sizes via ``wp_generate_attachment_metadata``
after an upload, a format conversion (F.5a.8.1), or when new sizes are
registered by the active theme. Two modes:

1. ``ids=[...]`` — regenerate a specific list (up to 50 per call).
2. ``all=True`` — iterate over ``image/*`` attachments in ID order with
   ``offset``/``limit`` paging.

Tool: ``wordpress_regenerate_thumbnails``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.regenerate_thumbnails")

_MAX_IDS_PER_CALL = 50


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "regenerate_thumbnails",
            "method_name": "regenerate_thumbnails",
            "description": (
                "Rebuild attachment sub-sizes (the registered WP image sizes "
                "plus any from add_image_size() in the active theme). Use "
                "this after upload_media_from_url / _from_base64 with "
                "convert_to=webp|avif, after a theme switch that adds new "
                "sizes, or for legacy attachments missing thumbnails. Routes "
                "through the airano-mcp-bridge companion plugin v2.8.0+. "
                "Body shapes: either an 'ids' list to target specific "
                f"attachments (max {_MAX_IDS_PER_CALL} per call); or "
                "all=true with offset/limit for paged batch. Returns "
                "has_more + next_offset in batch mode so callers can continue."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "ids": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {"type": "integer", "minimum": 1},
                                "maxItems": _MAX_IDS_PER_CALL,
                            },
                            {"type": "null"},
                        ],
                        "description": (
                            f"Attachment IDs (max {_MAX_IDS_PER_CALL}). "
                            "Mutually exclusive with 'all'."
                        ),
                    },
                    "all": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Batch mode: iterate image attachments in ID order. "
                            "Use with offset/limit for pagination."
                        ),
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Batch offset (for 'all' mode).",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _MAX_IDS_PER_CALL,
                        "default": _MAX_IDS_PER_CALL,
                        "description": (
                            f"Max attachments per batch page (capped at "
                            f"{_MAX_IDS_PER_CALL} server-side)."
                        ),
                    },
                },
            },
            "scope": "write",
        }
    ]


class RegenerateThumbnailsHandler:
    """Rebuild attachment sub-sizes via the companion plugin."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def regenerate_thumbnails(
        self,
        ids: list[int] | None = None,
        all: bool = False,
        offset: int = 0,
        limit: int = _MAX_IDS_PER_CALL,
    ) -> str:
        """Proxy to ``POST /airano-mcp/v1/regenerate-thumbnails``.

        Exactly one of ``ids`` or ``all`` must be truthy. Input is validated
        client-side so obvious errors don't consume a round-trip.
        """
        if not ids and not all:
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_request",
                    "message": (
                        "Provide either 'ids' (list of attachment IDs) or "
                        "'all': true for batch mode."
                    ),
                },
                indent=2,
            )

        if ids and all:
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_request",
                    "message": "'ids' and 'all' are mutually exclusive.",
                },
                indent=2,
            )

        body: dict[str, Any] = {}
        if ids:
            # Deduplicate + cap + coerce.
            uniq: list[int] = []
            seen: set[int] = set()
            for raw in ids:
                try:
                    i = int(raw)
                except (TypeError, ValueError):
                    continue
                if i > 0 and i not in seen:
                    uniq.append(i)
                    seen.add(i)
            body["ids"] = uniq[:_MAX_IDS_PER_CALL]
            if not body["ids"]:
                return json.dumps(
                    {
                        "ok": False,
                        "error": "invalid_request",
                        "message": "'ids' must contain at least one positive integer.",
                    },
                    indent=2,
                )
        else:
            body["all"] = True
            body["offset"] = max(0, int(offset))
            body["limit"] = min(_MAX_IDS_PER_CALL, max(1, int(limit)))

        try:
            payload = await self.client.post(
                "airano-mcp/v1/regenerate-thumbnails",
                json_data=body,
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("regenerate_thumbnails companion call failed: %s", exc)
            return json.dumps(
                {
                    "ok": False,
                    "error": "companion_unreachable",
                    "message": str(exc),
                    "hint": (
                        "Requires airano-mcp-bridge companion plugin v2.8.0+. "
                        "Run wordpress_probe_capabilities to verify the route "
                        "is advertised."
                    ),
                    "install_hint": _companion_install_hint(
                        min_version="2.8.0",
                        required_capability="upload_files",
                        route="airano-mcp/v1/regenerate-thumbnails",
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

        result: dict[str, Any] = {
            "ok": bool(
                (payload.get("processed") or 0) > 0
                or (not payload.get("errors") and not payload.get("attempted"))
            ),
            "mode": payload.get("mode"),
            "attempted": payload.get("attempted", 0),
            "processed": payload.get("processed", 0),
            "skipped": list(payload.get("skipped") or []),
            "errors": list(payload.get("errors") or []),
            "plugin_version": payload.get("plugin_version"),
        }
        if payload.get("mode") == "all":
            result["offset"] = payload.get("offset")
            result["limit"] = payload.get("limit")
            result["has_more"] = bool(payload.get("has_more"))
            result["next_offset"] = payload.get("next_offset")
            result["total"] = payload.get("total")
        return json.dumps(result, indent=2)
