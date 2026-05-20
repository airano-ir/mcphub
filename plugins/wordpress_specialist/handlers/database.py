"""F.19.3.2-.3 — Database inspection surface (db/size + db/tables + db/search).

Closes the database-introspection gap on ``wordpress_specialist`` so the
deprecated ``wordpress_advanced`` (Docker-socket / WP-CLI) plugin can
sunset cleanly. All three tools are read-only (scope=``read``) and
companion-backed via Airano MCP Bridge v2.18.0+.

Surface map:

* **wp_db_size** (``GET /admin/db/size``) — single
  ``information_schema.TABLES`` aggregation. Returns
  ``{database_bytes, table_count, row_count_estimate, database_name,
  table_prefix}``. No SQL exposure: caller doesn't pick the query.
* **wp_db_tables** (``GET /admin/db/tables``) — per-table breakdown
  from the same source. One row per WP table with name / engine /
  rows / data_bytes / index_bytes / total_bytes / collation.
* **wp_db_search** (``POST /admin/db/search``) — search wrapper
  around ``WP_Query`` with ``s=$query``. NEVER raw SQL.

Security rules (extending S-1…S-24):

* **S-25** — ``wp_db_search`` uses ``WP_Query`` with ``s=``, not raw
  SQL. ``query`` is sanitised via ``sanitize_text_field`` server-side
  and length-capped at 200 chars client-side. Refusal to return non-
  readable posts (private/draft from other authors) is enforced by
  ``WP_Query``'s own ``posts_clauses`` filter — the same gate the WP
  search page uses.

All routes gated on ``manage_options`` at the companion level. Pulling
``information_schema.TABLES`` requires the DB user to have access to it
— the standard WordPress install has this for the same MySQL user that
runs WP itself, so this is safe in practice.
"""

from __future__ import annotations

from typing import Any

from plugins.wordpress.client import WordPressClient

# Companion admin namespace — same prefix used by every F.19.* surface.
_ADMIN_NS = "airano-mcp/v1/admin"

# S-25 client-side cap. Server enforces the same limit; this is purely
# a fast-fail before the round-trip.
_QUERY_MAX_LEN = 200

# Limit cap on db/search. Mirrors the server-side ceiling.
_SEARCH_LIMIT_MAX = 100


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.3.2-.3 database surface."""
    return [
        {
            "name": "wp_db_size",
            "method_name": "wp_db_size",
            "description": (
                "Read aggregate database size for the WordPress install. "
                "Returns ``{database_bytes, table_count, "
                "row_count_estimate, database_name, table_prefix}``. "
                "Source is a single ``information_schema.TABLES`` "
                "aggregation scoped to the WP table prefix — no SQL is "
                "exposed to the caller (S-25). InnoDB row counts are "
                "estimates, not exact, mirroring MySQL's own caveat. "
                "Use to answer 'how big is this site?' before deciding "
                "whether to migrate / archive. Requires Airano MCP "
                "Bridge v2.18.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_db_tables",
            "method_name": "wp_db_tables",
            "description": (
                "Read per-table size + row breakdown. Returns "
                "``{database_name, table_prefix, tables: [{name, engine, "
                "rows, data_bytes, index_bytes, total_bytes, collation}]}`` "
                "ordered by total_bytes descending. Same source as "
                "``wp_db_size`` — one row per WP table. Useful for "
                "'which table is the bloat?' debugging (commonly "
                "options, postmeta, comments, or a plugin's log table). "
                "Requires Airano MCP Bridge v2.18.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_db_search",
            "method_name": "wp_db_search",
            "description": (
                "Full-text search across post / product content using "
                "``WP_Query`` with ``s=$query``. NEVER raw SQL (S-25). "
                "Returns ``{query, limit, count, hits: [{id, post_type, "
                "status, title, snippet, url, modified}]}``. Sanitises "
                "``query`` via ``sanitize_text_field`` server-side; "
                "client caps it at 200 chars. ``limit`` defaults to 20, "
                "max 100. Optional ``post_type`` (string or array) and "
                "``status`` (string or array) filters. Non-readable "
                "posts (private / draft from other authors) are filtered "
                "out by ``WP_Query``'s own ``posts_clauses`` — same gate "
                "the WP search page uses. Requires Airano MCP Bridge "
                "v2.18.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": _QUERY_MAX_LEN,
                        "description": (
                            "Search term. Sanitised server-side via "
                            "``sanitize_text_field``; client caps at "
                            f"{_QUERY_MAX_LEN} chars."
                        ),
                    },
                    "post_type": {
                        "description": (
                            "Optional post type filter. String "
                            "(``post``, ``page``, ``product`` ...) or "
                            "array of strings. Defaults to ``any``."
                        ),
                    },
                    "status": {
                        "description": (
                            "Optional post status filter. String "
                            "(``publish``, ``draft`` ...) or array of "
                            "strings. Defaults to ``any``."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _SEARCH_LIMIT_MAX,
                        "default": 20,
                        "description": (
                            f"Max hits to return (1–{_SEARCH_LIMIT_MAX}). " "Defaults to 20."
                        ),
                    },
                },
                "required": ["query"],
            },
            "scope": "read",
        },
    ]


# ─────────────────────────────────────────────────────────────────────
# Client-side validation helpers
# ─────────────────────────────────────────────────────────────────────


def _normalise_query(value: Any) -> str:
    """Validate + length-cap the search query (S-25 client side).

    The server re-runs ``sanitize_text_field`` and applies the same
    length cap; this is a fast-fail before the round-trip. Empty
    queries are rejected — ``WP_Query`` with ``s=''`` matches every
    post and would return a meaningless dump.
    """
    if not isinstance(value, str):
        raise ValueError(f"query must be a string (got {type(value).__name__})")
    stripped = value.strip()
    if not stripped:
        raise ValueError("query must be a non-empty string")
    if len(stripped) > _QUERY_MAX_LEN:
        stripped = stripped[:_QUERY_MAX_LEN]
    return stripped


def _normalise_limit(value: Any) -> int:
    """Cap the search limit at 100 (mirror of the server-side ceiling)."""
    if value is None:
        return 20
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"limit must be an integer (got {type(value).__name__})")
    if value < 1:
        raise ValueError(f"limit must be >= 1 (got {value})")
    if value > _SEARCH_LIMIT_MAX:
        return _SEARCH_LIMIT_MAX
    return value


def _normalise_filter(value: Any, field: str) -> str | list[str] | None:
    """Accept a string or list of strings; reject anything else.

    The server sanitises with ``sanitize_key`` per item; we only check
    structural shape here.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value if value else None
    if isinstance(value, list):
        if not all(isinstance(v, str) for v in value):
            raise ValueError(f"{field} array must contain only strings")
        return value
    raise ValueError(f"{field} must be a string or array of strings")


class DatabaseHandler:
    """Database inspection surface (F.19.3.2-.3) — db/size + db/tables + db/search.

    Each method returns the parsed JSON envelope from the companion.
    The plugin.py wrapper serialises for MCP transport. Server errors
    (500 db_size_query_failed, 400 invalid_query, etc.) are relayed
    untouched — the companion is the binding gate.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def wp_db_size(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/db/size",
            use_custom_namespace=True,
        )

    async def wp_db_tables(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/db/tables",
            use_custom_namespace=True,
        )

    async def wp_db_search(
        self,
        query: str,
        post_type: str | list[str] | None = None,
        status: str | list[str] | None = None,
        limit: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "query": _normalise_query(query),
            "limit": _normalise_limit(limit),
        }
        pt = _normalise_filter(post_type, "post_type")
        if pt is not None:
            body["post_type"] = pt
        st = _normalise_filter(status, "status")
        if st is not None:
            body["status"] = st
        return await self.client.post(
            f"{_ADMIN_NS}/db/search",
            json_data=body,
            use_custom_namespace=True,
        )
