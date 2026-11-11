"""Search Analytics handlers — query search performance data with bounded dimensions/date ranges."""

import json
from typing import Any

from plugins.google_search_console.client import GSCClient

# Allowed dimensions for Search Analytics
_ALLOWED_DIMENSIONS = {"query", "page", "country", "device", "date"}

# Allowed search types
_ALLOWED_SEARCH_TYPES = {"web", "image", "video", "news"}

# Maximum rows per request (Google API limit)
_MAX_ROWS = 25000

# Maximum date range (Google API allows ~18 months)
_MAX_DATE_RANGE_DAYS = 548


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "search_analytics",
            "category": "read",
            "method_name": "search_analytics",
            "description": (
                "Query Search Analytics data for a property with bounded dimensions and "
                "date ranges. Returns rows with clicks, impressions, CTR, and position "
                "broken down by the specified dimensions. Date range is limited to 548 "
                "days (~18 months). Maximum 25,000 rows per request."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "site_url": {
                        "type": "string",
                        "description": (
                            "Search Console property URL. Domain properties use "
                            "sc-domain:example.com; URL-prefix properties use the full URL "
                            "including trailing slash."
                        ),
                        "minLength": 1,
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format.",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format.",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    },
                    "dimensions": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": list(_ALLOWED_DIMENSIONS),
                                },
                                "minItems": 0,
                                "maxItems": 5,
                            },
                            {"type": "null"},
                        ],
                        "description": (
                            "Dimensions to break down results by. Allowed: query, page, "
                            'country, device, date. Example: ["query", "page"] to see '
                            "top queries per page."
                        ),
                    },
                    "type_filter": {
                        "type": "string",
                        "enum": list(_ALLOWED_SEARCH_TYPES),
                        "default": "web",
                        "description": "Search type filter (web, image, video, news).",
                    },
                    "rows_limit": {
                        "type": "integer",
                        "description": "Maximum number of rows to return (max 25000).",
                        "default": 1000,
                        "minimum": 1,
                        "maximum": _MAX_ROWS,
                    },
                    "start_row": {
                        "type": "integer",
                        "description": "Zero-based start row for pagination.",
                        "default": 0,
                        "minimum": 0,
                    },
                    "data_state": {
                        "type": "string",
                        "enum": ["final", "all"],
                        "default": "final",
                        "description": (
                            "final for finalized data, all for fresh + final data "
                            "(includes recent data that may still change)."
                        ),
                    },
                },
                "required": ["site_url", "start_date", "end_date"],
            },
            "scope": "read",
        },
    ]


# --- Handler functions ---


async def search_analytics(
    client: GSCClient,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    type_filter: str = "web",
    rows_limit: int = 1000,
    start_row: int = 0,
    data_state: str = "final",
) -> str:
    """Query Search Analytics data for a property.

    Args:
        client: GSC API client.
        site_url: Property URL.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        dimensions: Dimensions to break down by.
        type_filter: Search type (web, image, video, news).
        rows_limit: Maximum rows to return.
        start_row: Pagination start row.
        data_state: final or all.

    Returns:
        JSON string with analytics rows and summary.
    """
    # Validate dimensions
    if dimensions:
        invalid = set(dimensions) - _ALLOWED_DIMENSIONS
        if invalid:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Invalid dimensions: {invalid}. Allowed: {_ALLOWED_DIMENSIONS}",
                },
                indent=2,
                ensure_ascii=False,
            )

    # Validate search type
    if type_filter not in _ALLOWED_SEARCH_TYPES:
        return json.dumps(
            {
                "success": False,
                "error": f"Invalid type_filter: {type_filter}. Allowed: {_ALLOWED_SEARCH_TYPES}",
            },
            indent=2,
            ensure_ascii=False,
        )

    # Clamp rows
    rows_limit = min(rows_limit, _MAX_ROWS)

    data = await client.search_analytics(
        site_url=site_url,
        start_date=start_date,
        end_date=end_date,
        dimensions=dimensions,
        type_filter=type_filter,
        rows_limit=rows_limit,
        start_row=start_row,
        data_state=data_state,
    )

    rows = data.get("rows", [])

    # Build summary
    total_clicks = sum(r.get("clicks", 0) for r in rows)
    total_impressions = sum(r.get("impressions", 0) for r in rows)

    result = {
        "success": True,
        "site_url": site_url,
        "start_date": start_date,
        "end_date": end_date,
        "dimensions": dimensions or [],
        "type_filter": type_filter,
        "data_state": data_state,
        "row_count": len(rows),
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "response": data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)
