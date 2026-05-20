"""F.19.3.2-.3 — Bulk fan-out surface (post + term updates).

Stock-REST-backed: each item dispatches to ``wp/v2/posts/{id}`` or
``wp/v2/{taxonomy}/{id}`` — no companion routes are added for these
because the stock REST endpoints already exist and handle their own
permission checks. Per-item permission gating happens at the WP layer
(``edit_post`` / ``manage_terms`` per id), so partial successes are
the expected shape.

Surface map:

* **wp_bulk_post_update** — ``POST wp/v2/posts/{id}`` per item, fanned
  out with concurrency=10 (mirror of the legacy ``wordpress_advanced``
  bulk pattern). 50-item cap.
* **wp_bulk_term_update** — ``POST wp/v2/{taxonomy}/{id}`` per item,
  same shape. 50-item cap. ``taxonomy`` is the REST base
  (``categories`` / ``tags`` / custom rest_base).

Both tools sit on the ``editor`` tier — same risk class as bulk page
edits. Caller needs ``edit_posts`` / ``manage_terms`` (or the
taxonomy-specific cap) on every item; per-item failures are surfaced
in the response, the rest succeed.

Security rules (extending S-1…S-25):

* **S-26** — Bulk operations cap at 50 items per call (mirror of the
  S-14 / S-18 family). Bigger payloads return ``bulk_too_large`` 400
  client-side without any HTTP traffic. Per-item permission checks
  happen one-by-one inside WP REST (``current_user_can('edit_post', $id)``);
  the client doesn't aggregate caps.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from plugins.wordpress.client import WordPressClient

# S-26 cap. Server doesn't add its own check — the cap is purely
# client-side because each request is a separate stock-REST call.
_BULK_MAX_ITEMS = 50

# Stock REST uses POST for create/update on the post / taxonomy
# endpoints. PUT also works in modern WP, but POST is the documented
# pattern and matches what WP-CLI emits.
_UPDATE_METHOD = "POST"

# Acceptable taxonomy slug shape — must look like ``sanitize_key``
# would have produced it server-side. Lowercased, digits, ``_``, ``-``.
_TAXONOMY_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,63}$")

# Concurrency bound for the fan-out. Matches the legacy
# ``wordpress_advanced`` pattern; keeps the WP server from getting
# swamped on shared hosting.
_FANOUT_CONCURRENCY = 10


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.3.2-.3 bulk surface."""
    return [
        {
            "name": "wp_bulk_post_update",
            "method_name": "wp_bulk_post_update",
            "description": (
                "Fan-out update across multiple posts via stock REST "
                "``wp/v2/posts/{id}``. Pass ``updates=[{id, ...fields}]`` "
                "where each item carries the id plus whichever fields "
                "to write (``status``, ``title``, ``content``, ``excerpt``, "
                "``categories``, ``tags``, ``author``, ``featured_media``, "
                "``meta``, etc — anything stock REST accepts on the "
                "``post`` endpoint). Returns "
                "``[{id, status:'ok'|'error', error?}]`` — partial "
                "successes are the expected shape since per-item "
                "``edit_post`` cap checks happen at the WP layer. "
                "S-26: 50-item cap per call; bigger payloads return "
                "``bulk_too_large`` 400 without any HTTP. Concurrency "
                "is bounded to 10 in flight to avoid swamping shared "
                "hosts."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": _BULK_MAX_ITEMS,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "description": "Post id to update.",
                                },
                            },
                            "required": ["id"],
                        },
                        "description": (
                            f"Updates array (1–{_BULK_MAX_ITEMS} items). "
                            "Each item must carry ``id`` plus any "
                            "post fields stock REST accepts."
                        ),
                    },
                },
                "required": ["updates"],
            },
            "scope": "editor",
        },
        {
            "name": "wp_bulk_term_update",
            "method_name": "wp_bulk_term_update",
            "description": (
                "Fan-out update across multiple terms in a single "
                "taxonomy via stock REST ``wp/v2/{taxonomy}/{id}``. "
                "``taxonomy`` is the REST base — ``categories``, "
                "``tags``, or a custom taxonomy's ``rest_base``. "
                "Pass ``updates=[{id, ...fields}]`` where each item "
                "carries the id plus whichever term fields to write "
                "(``name``, ``slug``, ``description``, ``parent``, "
                "``meta``). Returns "
                "``[{id, status:'ok'|'error', error?}]``. Per-item "
                "``manage_terms`` (or the taxonomy-specific edit cap) "
                "is enforced server-side. S-26: 50-item cap per call. "
                "Concurrency is bounded to 10 in flight."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "taxonomy": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64,
                        "description": (
                            "REST base of the taxonomy "
                            "(``categories``, ``tags``, or a custom "
                            "taxonomy's rest_base)."
                        ),
                    },
                    "updates": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": _BULK_MAX_ITEMS,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "description": "Term id to update.",
                                },
                            },
                            "required": ["id"],
                        },
                        "description": (f"Updates array (1–{_BULK_MAX_ITEMS} items)."),
                    },
                },
                "required": ["taxonomy", "updates"],
            },
            "scope": "editor",
        },
    ]


# ─────────────────────────────────────────────────────────────────────
# Client-side validation helpers
# ─────────────────────────────────────────────────────────────────────


def _validate_updates(value: Any) -> list[dict[str, Any]]:
    """Validate the bulk updates array (S-26 client side).

    Each item must be a dict with a positive integer ``id``. Other
    fields are forwarded untouched — stock REST does its own field
    validation. Empty arrays are rejected (no-op), > 50 returns
    ``bulk_too_large``.
    """
    if not isinstance(value, list):
        raise ValueError(f"updates must be a list (got {type(value).__name__})")
    if not value:
        raise ValueError("updates must contain at least one item")
    if len(value) > _BULK_MAX_ITEMS:
        raise ValueError(
            f"bulk_too_large: updates contains {len(value)} items "
            f"(max {_BULK_MAX_ITEMS} per call)"
        )
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"updates[{idx}] must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, int) or isinstance(item_id, bool) or item_id < 1:
            raise ValueError(f"updates[{idx}].id must be a positive integer (got {item_id!r})")
    return value


def _validate_taxonomy(value: Any) -> str:
    """Validate the taxonomy slug shape (cheap pre-check).

    The binding gate is server-side — WP returns 404 for unregistered
    taxonomies. This catches obviously bad input (slashes, spaces,
    etc.) without a round-trip.
    """
    if not isinstance(value, str):
        raise ValueError(f"taxonomy must be a string (got {type(value).__name__})")
    stripped = value.strip()
    if not stripped:
        raise ValueError("taxonomy must be a non-empty string")
    if not _TAXONOMY_RE.match(stripped):
        raise ValueError(f"taxonomy must match [a-z0-9][a-z0-9_-]{{0,63}} (got {stripped!r})")
    return stripped


class BulkHandler:
    """Bulk fan-out surface (F.19.3.2-.3) — post + term updates.

    Each method runs N stock-REST requests in parallel (bounded at
    concurrency=10) and returns the per-item status array. Per-item
    failures don't fail the whole call — the caller gets
    ``{id, status:'error', error}`` for each one and ``status:'ok'``
    for the successes.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def _fanout(
        self,
        endpoint_template: str,
        updates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Run the per-item fan-out with bounded concurrency.

        ``endpoint_template`` is a format string that takes the item id —
        e.g. ``"posts/{id}"`` or ``"categories/{id}"``. Each item's
        non-``id`` fields are forwarded as the JSON body.
        """
        sem = asyncio.Semaphore(_FANOUT_CONCURRENCY)
        results: list[dict[str, Any]] = [None] * len(updates)  # type: ignore[list-item]

        async def one(idx: int, item: dict[str, Any]) -> None:
            item_id = int(item["id"])
            body = {k: v for k, v in item.items() if k != "id"}
            async with sem:
                try:
                    await self.client.request(
                        _UPDATE_METHOD,
                        endpoint_template.format(id=item_id),
                        json_data=body if body else None,
                    )
                    results[idx] = {"id": item_id, "status": "ok"}
                except Exception as exc:  # noqa: BLE001 — relay any per-item failure
                    results[idx] = {
                        "id": item_id,
                        "status": "error",
                        "error": str(exc),
                    }

        await asyncio.gather(*(one(i, u) for i, u in enumerate(updates)))
        return results

    async def wp_bulk_post_update(
        self,
        updates: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        clean = _validate_updates(updates)
        results = await self._fanout("posts/{id}", clean)
        ok = sum(1 for r in results if r["status"] == "ok")
        return {
            "total": len(results),
            "ok": ok,
            "errors": len(results) - ok,
            "results": results,
        }

    async def wp_bulk_term_update(
        self,
        taxonomy: str,
        updates: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        tax = _validate_taxonomy(taxonomy)
        clean = _validate_updates(updates)
        results = await self._fanout(tax + "/{id}", clean)
        ok = sum(1 for r in results if r["status"] == "ok")
        return {
            "taxonomy": tax,
            "total": len(results),
            "ok": ok,
            "errors": len(results) - ok,
            "results": results,
        }
