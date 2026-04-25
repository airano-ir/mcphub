"""F.5a.8.3 — Bulk media library operations.

Wraps stock ``wp/v2/media`` REST endpoints with two batch tools:

* ``wordpress_bulk_delete_media`` — delete (trash or force-delete) a list of
  attachments in one call, collecting per-item results.
* ``wordpress_bulk_reassign_media`` — change the ``post`` parent of a list
  of attachments in one call (useful for moving media between posts, or
  detaching from a deleted parent).

Both tools use the existing authenticated REST client. They iterate
serially with a small concurrency cap so a large batch doesn't flood a
shared-hosting WP backend, but the whole call returns a single JSON
envelope with ``processed`` / ``errors`` / ``total`` — matching the
shape used by F.18.2 bulk-meta.

Per-call cap: 100 attachment IDs.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient

logger = logging.getLogger("mcphub.wordpress.media_bulk")

_MAX_IDS_PER_CALL = 100
_CONCURRENCY = 4  # parallel in-flight REST calls


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "bulk_delete_media",
            "method_name": "bulk_delete_media",
            "description": (
                "Delete (trash or permanently remove) a list of media "
                "attachments in a single call. Max 100 IDs per request. "
                "Returns processed / errors / total. Uses stock "
                "/wp/v2/media/{id} DELETE so no companion plugin is "
                "required, but issues N requests (with a small concurrency "
                "cap); for 1000+ attachments, paginate client-side."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "media_ids": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1},
                        "minItems": 1,
                        "maxItems": _MAX_IDS_PER_CALL,
                        "description": f"Attachment IDs (max {_MAX_IDS_PER_CALL}).",
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "true = permanently delete (bypass trash). "
                            "false = move to trash. Media in trash > 30 "
                            "days is removed by WP cron by default."
                        ),
                    },
                },
                "required": ["media_ids"],
            },
            "scope": "admin",
        },
        {
            "name": "bulk_reassign_media",
            "method_name": "bulk_reassign_media",
            "description": (
                "Reassign the parent post of a list of media attachments "
                "in a single call. Useful for moving attachments between "
                "posts, or detaching (use target_post=0). Max 100 IDs. "
                "Returns processed / errors / total."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "media_ids": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1},
                        "minItems": 1,
                        "maxItems": _MAX_IDS_PER_CALL,
                        "description": f"Attachment IDs (max {_MAX_IDS_PER_CALL}).",
                    },
                    "target_post": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Post ID to assign as the new parent. " "0 = detach (orphan the media)."
                        ),
                    },
                },
                "required": ["media_ids", "target_post"],
            },
            "scope": "write",
        },
    ]


class MediaBulkHandler:
    """Batch delete + reassign for WP media attachments."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # Input normalization
    # ------------------------------------------------------------------

    def _normalize_ids(self, media_ids: list[Any]) -> list[int]:
        """Dedup, coerce to int, drop non-positive, cap at _MAX_IDS_PER_CALL.

        Order is preserved so the caller can correlate request and response
        by index if they care.
        """
        out: list[int] = []
        seen: set[int] = set()
        for raw in media_ids or []:
            try:
                i = int(raw)
            except (TypeError, ValueError):
                continue
            if i > 0 and i not in seen:
                out.append(i)
                seen.add(i)
            if len(out) >= _MAX_IDS_PER_CALL:
                break
        return out

    # ------------------------------------------------------------------
    # Bulk delete
    # ------------------------------------------------------------------

    async def bulk_delete_media(
        self,
        media_ids: list[int],
        force: bool = False,
    ) -> str:
        ids = self._normalize_ids(media_ids or [])
        if not ids:
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_request",
                    "message": "media_ids must contain at least one positive integer.",
                },
                indent=2,
            )

        params = {"force": "true" if force else "false"}
        sem = asyncio.Semaphore(_CONCURRENCY)

        processed: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        async def _one(mid: int) -> None:
            async with sem:
                try:
                    await self.client.delete(f"media/{mid}", params=params)
                    processed.append({"id": mid})
                except Exception as exc:  # noqa: BLE001
                    errors.append({"id": mid, "error": str(exc)})

        await asyncio.gather(*[_one(i) for i in ids])

        return json.dumps(
            {
                "ok": not errors,
                "total": len(ids),
                "processed": len(processed),
                "errors": errors,
                "force": force,
            },
            indent=2,
        )

    # ------------------------------------------------------------------
    # Bulk reassign
    # ------------------------------------------------------------------

    async def bulk_reassign_media(
        self,
        media_ids: list[int],
        target_post: int,
    ) -> str:
        try:
            target = int(target_post)
        except (TypeError, ValueError):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_request",
                    "message": "target_post must be an integer (0 to detach).",
                },
                indent=2,
            )
        if target < 0:
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_request",
                    "message": "target_post must be >= 0.",
                },
                indent=2,
            )

        ids = self._normalize_ids(media_ids or [])
        if not ids:
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_request",
                    "message": "media_ids must contain at least one positive integer.",
                },
                indent=2,
            )

        sem = asyncio.Semaphore(_CONCURRENCY)
        processed: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        async def _one(mid: int) -> None:
            async with sem:
                try:
                    await self.client.post(
                        f"media/{mid}",
                        json_data={"post": target},
                    )
                    processed.append({"id": mid})
                except Exception as exc:  # noqa: BLE001
                    errors.append({"id": mid, "error": str(exc)})

        await asyncio.gather(*[_one(i) for i in ids])

        return json.dumps(
            {
                "ok": not errors,
                "total": len(ids),
                "processed": len(processed),
                "errors": errors,
                "target_post": target,
            },
            indent=2,
        )
