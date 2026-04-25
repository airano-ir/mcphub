"""F.18.3 — Structured JSON export via companion plugin.

Wraps ``GET /airano-mcp/v1/export`` (companion plugin v2.3.0+). Returns
posts (posts, pages, products, custom post types) plus referenced media,
taxonomy terms, and meta in a single JSON envelope, with pagination
hints (``has_more`` + ``next_offset``). Intended for offline processing,
migrations, and content snapshots.

Tool: ``wordpress_export_content(post_type="post", status="publish", ...)``
"""

from __future__ import annotations

import json
import logging
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._companion_hint import (
    companion_install_hint as _companion_install_hint,
)

logger = logging.getLogger("mcphub.wordpress.export")

# Matches EXPORT_MAX_LIMIT in airano-mcp-bridge.php.
EXPORT_MAX_LIMIT = 500
EXPORT_DEFAULT_LIMIT = 100


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "export_content",
            "method_name": "export_content",
            "description": (
                "Export posts/pages/products as structured JSON via the "
                "airano-mcp-bridge companion plugin (v2.3.0+). Includes "
                "referenced media, taxonomy terms, and post_meta. Paginates "
                "via offset/limit; response contains has_more + next_offset. "
                "Not a WXR dump — intended for AI-pipeline processing, not "
                "WP-to-WP import."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "post_type": {
                        "type": "string",
                        "description": (
                            "Comma-separated list of post types "
                            "(e.g. 'post', 'post,page', 'product'). Default 'post'."
                        ),
                    },
                    "status": {
                        "type": "string",
                        "description": (
                            "Comma-separated list of statuses, or 'any'. " "Default 'publish'."
                        ),
                    },
                    "since": {
                        "type": "string",
                        "description": (
                            "Only return posts modified after this ISO8601 " "timestamp. Optional."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (f"1..{EXPORT_MAX_LIMIT}, default {EXPORT_DEFAULT_LIMIT}."),
                    },
                    "offset": {"type": "integer", "description": "Default 0."},
                    "include_media": {
                        "type": "boolean",
                        "description": "Include featured media objects (default true).",
                    },
                    "include_terms": {
                        "type": "boolean",
                        "description": "Include taxonomy terms per post (default true).",
                    },
                    "include_meta": {
                        "type": "boolean",
                        "description": "Include post_meta (default true).",
                    },
                },
            },
            "scope": "read",
        }
    ]


def _normalise_bool(v: Any, default: bool) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "on"}:
        return True
    if s in {"false", "0", "no", "off"}:
        return False
    return default


def _build_query_params(
    *,
    post_type: str | None,
    status: str | None,
    since: str | None,
    limit: int | None,
    offset: int | None,
    include_media: Any,
    include_terms: Any,
    include_meta: Any,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "post_type": post_type or "post",
        "status": status or "publish",
    }
    if since:
        params["since"] = since

    if limit is None:
        params["limit"] = EXPORT_DEFAULT_LIMIT
    else:
        lim = int(limit)
        if lim <= 0:
            lim = EXPORT_DEFAULT_LIMIT
        if lim > EXPORT_MAX_LIMIT:
            lim = EXPORT_MAX_LIMIT
        params["limit"] = lim

    params["offset"] = max(0, int(offset or 0))

    # Pass booleans as "true"/"false" strings so the PHP side's
    # bool_param() helper can parse them uniformly.
    params["include_media"] = "true" if _normalise_bool(include_media, True) else "false"
    params["include_terms"] = "true" if _normalise_bool(include_terms, True) else "false"
    params["include_meta"] = "true" if _normalise_bool(include_meta, True) else "false"

    return params


class ExportHandler:
    """Structured JSON export via the companion plugin."""

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def export_content(
        self,
        post_type: str | None = None,
        status: str | None = None,
        since: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_media: Any = True,
        include_terms: Any = True,
        include_meta: Any = True,
    ) -> str:
        params = _build_query_params(
            post_type=post_type,
            status=status,
            since=since,
            limit=limit,
            offset=offset,
            include_media=include_media,
            include_terms=include_terms,
            include_meta=include_meta,
        )

        try:
            payload = await self.client.get(
                "airano-mcp/v1/export",
                params=params,
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("export_content companion call failed: %s", exc)
            return json.dumps(
                {
                    "ok": False,
                    "error": "companion_unreachable",
                    "message": str(exc),
                    "hint": (
                        "Requires airano-mcp-bridge companion plugin v2.3.0+. "
                        "Run wordpress_probe_capabilities to verify availability."
                    ),
                    "install_hint": _companion_install_hint(
                        min_version="2.3.0",
                        required_capability="edit_posts",
                        route="airano-mcp/v1/export",
                    ),
                    "params": params,
                },
                indent=2,
            )

        if not isinstance(payload, dict):
            return json.dumps(
                {
                    "ok": False,
                    "error": "invalid_response",
                    "message": "companion returned a non-object payload",
                    "params": params,
                },
                indent=2,
            )

        result = {"ok": True, **payload}
        return json.dumps(result, indent=2)
