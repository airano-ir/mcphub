"""URL Inspection handlers — inspect indexing status of a URL within a property."""

import json
from typing import Any

from plugins.google_search_console.client import GSCClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "inspect_url",
            "category": "read",
            "method_name": "inspect_url",
            "description": (
                "Inspect a URL's indexing status within a Search Console property. "
                "Returns the index status (INDEXED, NOT_INDEXED, etc.), crawling data, "
                "mobile usability, rich results, and AMP status. The inspection URL "
                "must be under the property's scope — cross-property inspection is "
                "rejected by the Google API."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "site_url": {
                        "type": "string",
                        "description": (
                            "Search Console property URL. Must be a property the "
                            "authenticated user has access to. Domain properties use "
                            "sc-domain:example.com; URL-prefix properties use the full "
                            "URL including trailing slash."
                        ),
                        "minLength": 1,
                    },
                    "inspection_url": {
                        "type": "string",
                        "description": (
                            "Full URL to inspect. Must be under the property's scope. "
                            "For URL-prefix properties, the URL must start with the "
                            "property's prefix. For domain properties, the URL must be "
                            "on the registered domain (including subdomains)."
                        ),
                        "minLength": 1,
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for the response (e.g. en-US, fa-IR).",
                        "default": "en-US",
                    },
                },
                "required": ["site_url", "inspection_url"],
            },
            "scope": "read",
        },
    ]


# --- Handler functions ---


async def inspect_url(
    client: GSCClient,
    site_url: str,
    inspection_url: str,
    language: str = "en-US",
) -> str:
    """Inspect a URL's indexing status.

    Args:
        client: GSC API client.
        site_url: Property URL.
        inspection_url: URL to inspect (must be under the property's scope).
        language: Language code for the response.

    Returns:
        JSON string with the inspection result.
    """
    data = await client.inspect_url(
        site_url=site_url,
        inspection_url=inspection_url,
        language=language,
    )

    # The inspection result has a nested structure. Extract key fields
    # for a cleaner summary while preserving the full data.
    inspection_result = data.get("inspectionResult", {})
    index_status = inspection_result.get("indexStatusResult", {})

    summary = {
        "success": True,
        "site_url": site_url,
        "inspection_url": inspection_url,
        "verdict": index_status.get("verdict", "unknown"),
        "indexing_state": index_status.get("indexingState", "unknown"),
        "last_crawl_time": index_status.get("lastCrawlTime"),
        "google_canonical": index_status.get("googleCanonical"),
        "user_canonical": index_status.get("userCanonical"),
        "robots_txt_state": index_status.get("robotsTxtState"),
        "page_fetch_state": index_status.get("pageFetchState"),
        "mobile_usability": inspection_result.get("mobileUsabilityResult", {}).get("verdict"),
        "rich_results": inspection_result.get("richResultsResult", {}).get("verdict"),
        "full_result": inspection_result,
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)
