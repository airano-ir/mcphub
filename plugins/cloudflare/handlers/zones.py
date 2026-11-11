"""Zone handlers — list zones, zone details, cache purge."""

import json
from typing import Any

from plugins.cloudflare.client import CloudflareClient

_ZONE_STATUSES = ["active", "pending", "development", "deleted", "moved"]


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_zones",
            "category": "read",
            "method_name": "list_zones",
            "description": (
                "List Cloudflare zones the token can access. Supports filtering by exact "
                "zone name and status (active, pending, development, deleted, moved), plus "
                "pagination. Returns zone id, name, status, name servers and plan."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact zone name filter (e.g. example.com).",
                    },
                    "status": {
                        "type": "string",
                        "enum": _ZONE_STATUSES,
                        "description": "Zone status filter.",
                    },
                    "page": {"type": "integer", "description": "Page number."},
                    "per_page": {
                        "type": "integer",
                        "description": "Results per page (max 50).",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_zone",
            "category": "read",
            "method_name": "get_zone",
            "description": (
                "Fetch one Cloudflare zone by id — full details including name servers, "
                "status, plan, SSL and security settings."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "Cloudflare zone id (from list_zones).",
                    },
                },
                "required": ["zone_id"],
            },
            "scope": "read",
        },
        {
            "name": "purge_cache",
            "category": "cache",
            "method_name": "purge_cache",
            "description": (
                "Purge cached content for a zone. Requires the token's Cache Purge "
                "permission. Provide exactly one strategy: purge_everything (all cached "
                "content), files (specific URLs), tags (cache tags), or prefixes (URL "
                "prefixes). Impact is temporary — cache rebuilds on next requests."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "Cloudflare zone id.",
                    },
                    "purge_everything": {
                        "type": "boolean",
                        "description": "Purge ALL cached content for the zone.",
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exact URLs to purge (must be full URLs, max 30).",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cache tags to purge (max 30).",
                    },
                    "prefixes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "URL prefixes to purge (max 15).",
                    },
                },
                "required": ["zone_id"],
            },
            "scope": "write",
        },
    ]


# --- Handler functions ---


async def list_zones(
    client: CloudflareClient,
    name: str | None = None,
    status: str | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> str:
    """List zones.

    Args:
        client: CloudflareClient instance.
        name: Exact zone name filter.
        status: Zone status filter.
        page: Page number.
        per_page: Results per page.

    Returns:
        JSON string with zone summary.
    """
    zones = await client.list_zones(name=name, status=status, page=page, per_page=per_page)
    summary = [
        {
            "id": z.get("id"),
            "name": z.get("name"),
            "status": z.get("status"),
            "name_servers": z.get("name_servers"),
            "plan": (z.get("plan") or {}).get("name"),
            "original_name_servers": z.get("original_name_servers"),
        }
        for z in zones
    ]
    return json.dumps(
        {"success": True, "count": len(summary), "zones": summary},
        indent=2,
        ensure_ascii=False,
    )


async def get_zone(client: CloudflareClient, zone_id: str) -> str:
    """Fetch a zone by id.

    Args:
        client: CloudflareClient instance.
        zone_id: Cloudflare zone id.

    Returns:
        JSON string with zone details.
    """
    zone = await client.get_zone(zone_id)
    summary = {
        "id": zone.get("id"),
        "name": zone.get("name"),
        "status": zone.get("status"),
        "name_servers": zone.get("name_servers"),
        "original_name_servers": zone.get("original_name_servers"),
        "plan": (zone.get("plan") or {}).get("name"),
        "ssl": (zone.get("ssl") or {}).get("status") if isinstance(zone.get("ssl"), dict) else None,
        "paused": zone.get("paused"),
        "type": zone.get("type"),
        "development_mode": zone.get("development_mode"),
    }
    return json.dumps({"success": True, "zone": summary}, indent=2, ensure_ascii=False)


async def purge_cache(
    client: CloudflareClient,
    zone_id: str,
    purge_everything: bool | None = None,
    files: list[str] | None = None,
    tags: list[str] | None = None,
    prefixes: list[str] | None = None,
) -> str:
    """Purge cached content for a zone.

    Args:
        client: CloudflareClient instance.
        zone_id: Cloudflare zone id.
        purge_everything: Purge all cached content.
        files: Specific file URLs to purge.
        tags: Cache-tag based purge.
        prefixes: URL-prefix based purge.

    Returns:
        JSON string with the purge result.
    """
    result = await client.purge_cache(
        zone_id=zone_id,
        purge_everything=bool(purge_everything),
        files=files,
        tags=tags,
        prefixes=prefixes,
    )
    return json.dumps(
        {
            "success": True,
            "purged": "zone cache" if purge_everything else "targeted items",
            "result": result,
        },
        indent=2,
        ensure_ascii=False,
    )
