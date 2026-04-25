"""F.18.2 — Batch post/product meta writes via companion plugin.

Wraps ``POST /airano-mcp/v1/bulk-meta`` (companion plugin v2.2.0+). One
HTTP round-trip updates meta for up to 500 posts/products in a single
REST call; without the companion each post would need its own request.

Tool: ``wordpress_bulk_update_meta(updates=[...])``
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.bulk_meta")

# Matches BULK_META_MAX_ITEMS in airano-mcp-bridge.php so we reject client-side
# before burning a round-trip on a 413.
MAX_BULK_ITEMS = 500


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "bulk_update_meta",
            "method_name": "bulk_update_meta",
            "description": (
                "Batch-update post_meta (posts, pages, WooCommerce products) in a "
                "single REST round-trip via the airano-mcp-bridge companion "
                "plugin (v2.2.0+). Each item is permission-checked in PHP via "
                "current_user_can('edit_post', post_id). Pass a null meta value "
                "to delete that key. Maximum 500 items per call."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "description": (
                            "List of {post_id, meta} objects. `meta` is a dict of "
                            "meta_key => value; null values delete the key."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "post_id": {"type": "integer"},
                                "meta": {"type": "object"},
                            },
                            "required": ["post_id", "meta"],
                        },
                    }
                },
                "required": ["updates"],
            },
            "scope": "write",
        }
    ]


def _validate_updates(updates: Any) -> list[dict[str, Any]] | dict[str, Any]:
    """Validate the updates list. Returns the list on success, or an error dict."""
    if not isinstance(updates, list):
        return {
            "error": "invalid_updates",
            "message": "`updates` must be a list of {post_id, meta} objects.",
        }
    if not updates:
        return {
            "error": "empty_updates",
            "message": "No updates supplied.",
        }
    if len(updates) > MAX_BULK_ITEMS:
        return {
            "error": "too_many_items",
            "message": (
                f"At most {MAX_BULK_ITEMS} items per bulk_update_meta call; " f"got {len(updates)}."
            ),
        }

    cleaned: list[dict[str, Any]] = []
    for idx, item in enumerate(updates):
        if not isinstance(item, dict):
            return {
                "error": "invalid_item",
                "message": f"updates[{idx}] is not an object.",
                "index": idx,
            }
        post_id = item.get("post_id")
        meta = item.get("meta")
        if not isinstance(post_id, int) or post_id <= 0:
            return {
                "error": "invalid_post_id",
                "message": f"updates[{idx}].post_id must be a positive integer.",
                "index": idx,
            }
        if not isinstance(meta, dict):
            return {
                "error": "invalid_meta",
                "message": f"updates[{idx}].meta must be an object.",
                "index": idx,
            }
        cleaned.append({"post_id": post_id, "meta": meta})

    return cleaned


class BulkMetaHandler:
    """Batch meta writes via the companion plugin."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def bulk_update_meta(self, updates: Any) -> str:
        validated = _validate_updates(updates)
        if isinstance(validated, dict):
            # client-side rejection — don't burn a round-trip
            return json.dumps(
                {
                    "ok": False,
                    **validated,
                    "total": len(updates) if isinstance(updates, list) else 0,
                    "updated": 0,
                    "failed": 0,
                    "skipped": 0,
                    "results": [],
                },
                indent=2,
            )

        try:
            payload = await self.client.post(
                "airano-mcp/v1/bulk-meta",
                json_data={"updates": validated},
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("bulk_update_meta companion call failed: %s", exc)
            return json.dumps(
                {
                    "ok": False,
                    "error": "companion_unreachable",
                    "message": str(exc),
                    "hint": (
                        "Requires airano-mcp-bridge companion plugin v2.2.0+; "
                        "install/update it from wordpress-plugin/airano-mcp-bridge.zip "
                        "or run wordpress_probe_capabilities to verify availability."
                    ),
                    "install_hint": _companion_install_hint(
                        min_version="2.2.0",
                        required_capability="manage_options",
                        route="airano-mcp/v1/bulk-meta",
                    ),
                    "total": len(validated),
                    "updated": 0,
                    "failed": 0,
                    "skipped": 0,
                    "results": [],
                },
                indent=2,
            )

        # The companion already returns a well-shaped response — just
        # re-emit with the `ok` flag prepended so callers don't have to
        # infer success from counts.
        result = {
            "ok": True,
            "total": int(payload.get("total", 0)),
            "updated": int(payload.get("updated", 0)),
            "failed": int(payload.get("failed", 0)),
            "skipped": int(payload.get("skipped", 0)),
            "results": payload.get("results", []),
        }
        return json.dumps(result, indent=2)
