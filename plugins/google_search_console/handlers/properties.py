"""Property handlers — list accessible Search Console properties and permissions."""

import json
from typing import Any

from plugins.google_search_console.client import GSCClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_properties",
            "category": "read",
            "method_name": "list_properties",
            "description": (
                "List all Search Console properties (sites) the authenticated user has "
                "access to, with their permission levels. Returns property URLs (domain "
                "properties as sc-domain:example.com, URL-prefix properties as "
                "https://example.com/) and permission levels (siteFullUser, siteOwner, "
                "siteRestrictedUser)."
            ),
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
    ]


# --- Handler functions ---


async def list_properties(client: GSCClient) -> str:
    """List all accessible Search Console properties.

    Returns:
        JSON string with property URLs, permission levels, and a summary.
    """
    data = await client.list_sites()
    sites = data.get("siteEntry", [])

    # Enrich with parsed type info
    properties = []
    for site in sites:
        site_url = site.get("siteUrl", "")
        prop_type = "domain" if site_url.startswith("sc-domain:") else "url-prefix"
        properties.append(
            {
                "site_url": site_url,
                "permission_level": site.get("permissionLevel", "unknown"),
                "type": prop_type,
            }
        )

    result = {
        "success": True,
        "count": len(properties),
        "properties": properties,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)
