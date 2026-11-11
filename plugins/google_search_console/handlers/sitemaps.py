"""Sitemap handlers — list sitemaps and their submission status for a property."""

import json
from typing import Any

from plugins.google_search_console.client import GSCClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_sitemaps",
            "category": "read",
            "method_name": "list_sitemaps",
            "description": (
                "List sitemaps submitted for a Search Console property, including their "
                "submission status, last processed date, errors, and warnings. Use "
                "list_properties first to discover available property URLs."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "site_url": {
                        "type": "string",
                        "description": (
                            "Search Console property URL. Domain properties use the "
                            "format sc-domain:example.com. URL-prefix properties use the "
                            "full URL including trailing slash, e.g. https://example.com/."
                        ),
                        "minLength": 1,
                    },
                    "page_token": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Page token from a previous response for pagination.",
                    },
                },
                "required": ["site_url"],
            },
            "scope": "read",
        },
    ]


# --- Handler functions ---


async def list_sitemaps(
    client: GSCClient,
    site_url: str,
    page_token: str | None = None,
) -> str:
    """List sitemaps for a property.

    Args:
        client: GSC API client.
        site_url: Property URL (e.g. sc-domain:example.com or https://example.com/).
        page_token: Optional pagination token.

    Returns:
        JSON string with sitemap list and summary.
    """
    data = await client.list_sitemaps(site_url, page_token=page_token)
    sitemaps = data.get("sitemap", [])

    # Summarize errors/warnings
    total_errors = sum(s.get("errors", 0) for s in sitemaps)
    total_warnings = sum(s.get("warnings", 0) for s in sitemaps)

    result = {
        "success": True,
        "site_url": site_url,
        "count": len(sitemaps),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "sitemaps": sitemaps,
        "next_page_token": data.get("nextPageToken"),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)
