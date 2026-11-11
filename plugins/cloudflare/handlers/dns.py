"""DNS record handlers — list, get, create, update, delete."""

import json
from typing import Any

from plugins.cloudflare.client import CloudflareClient

_DNS_TYPES = [
    "A",
    "AAAA",
    "CNAME",
    "TXT",
    "MX",
    "SRV",
    "NS",
    "PTR",
    "CAA",
    "HTTPS",
    "SVCB",
    "CERT",
    "DNSKEY",
    "DS",
    "NAPTR",
    "SMIMEA",
    "SSHFP",
    "TLSA",
    "URI",
]


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_dns_records",
            "category": "read",
            "method_name": "list_dns_records",
            "description": (
                "List DNS records for a zone with optional filters (type, name, content) "
                "and pagination. Returns id, type, name, content, TTL, proxied status and "
                "comment for each record."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zone_id": {"type": "string", "description": "Cloudflare zone id."},
                    "type": {
                        "type": "string",
                        "enum": _DNS_TYPES,
                        "description": "Record type filter.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Record name filter (substring match, e.g. www).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Record content filter (substring match).",
                    },
                    "page": {"type": "integer", "description": "Page number."},
                    "per_page": {
                        "type": "integer",
                        "description": "Results per page (max 100).",
                    },
                },
                "required": ["zone_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_dns_record",
            "category": "read",
            "method_name": "get_dns_record",
            "description": "Fetch a single DNS record by id with its full details.",
            "schema": {
                "type": "object",
                "properties": {
                    "zone_id": {"type": "string", "description": "Cloudflare zone id."},
                    "record_id": {"type": "string", "description": "DNS record id."},
                },
                "required": ["zone_id", "record_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_dns_record",
            "category": "write",
            "method_name": "create_dns_record",
            "description": (
                "Create a DNS record (DNS:Edit permission). For a proxied A/AAAA record "
                "set proxied=true; for CNAME to another host keep proxied=false when the "
                "target is outside Cloudflare, or true when both sides are proxied. TTL 1 "
                "means automatic."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zone_id": {"type": "string", "description": "Cloudflare zone id."},
                    "type": {
                        "type": "string",
                        "enum": _DNS_TYPES,
                        "description": "Record type.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Record name (e.g. www.example.com or @ for the root).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Record content (IP address, target host, TXT text, ...).",
                    },
                    "ttl": {
                        "type": "integer",
                        "description": "TTL in seconds, 1 = automatic (default).",
                    },
                    "proxied": {
                        "type": "boolean",
                        "description": "Proxy through Cloudflare (orange cloud). Only for A/AAAA/CNAME.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority for MX and SRV records.",
                    },
                    "comment": {
                        "type": "string",
                        "description": "Free-form comment (max 255 chars).",
                    },
                },
                "required": ["zone_id", "type", "name", "content"],
            },
            "scope": "write",
        },
        {
            "name": "update_dns_record",
            "category": "write",
            "method_name": "update_dns_record",
            "description": (
                "Update an existing DNS record (DNS:Edit permission). Only the provided "
                "fields change; omitted fields keep their current value."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zone_id": {"type": "string", "description": "Cloudflare zone id."},
                    "record_id": {"type": "string", "description": "DNS record id."},
                    "type": {
                        "type": "string",
                        "enum": _DNS_TYPES,
                        "description": "New record type.",
                    },
                    "name": {
                        "type": "string",
                        "description": "New record name.",
                    },
                    "content": {
                        "type": "string",
                        "description": "New record content.",
                    },
                    "ttl": {
                        "type": "integer",
                        "description": "New TTL in seconds (1 = automatic).",
                    },
                    "proxied": {
                        "type": "boolean",
                        "description": "Proxy through Cloudflare.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority for MX/SRV records.",
                    },
                    "comment": {
                        "type": "string",
                        "description": "New comment (max 255 chars).",
                    },
                },
                "required": ["zone_id", "record_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_dns_record",
            "category": "admin",
            "method_name": "delete_dns_record",
            "description": (
                "Delete a DNS record (DNS:Edit permission). DESTRUCTIVE — the record and "
                "its resolution stop working immediately; recreate it with create_dns_record "
                "if needed."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zone_id": {"type": "string", "description": "Cloudflare zone id."},
                    "record_id": {"type": "string", "description": "DNS record id."},
                },
                "required": ["zone_id", "record_id"],
            },
            "scope": "admin",
        },
    ]


# --- Handler functions ---


async def list_dns_records(
    client: CloudflareClient,
    zone_id: str,
    type: str | None = None,
    name: str | None = None,
    content: str | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> str:
    """List DNS records for a zone.

    Args:
        client: CloudflareClient instance.
        zone_id: Cloudflare zone id.
        type: Record type filter.
        name: Record name filter.
        content: Record content filter.
        page: Page number.
        per_page: Results per page.

    Returns:
        JSON string with record summary.
    """
    records = await client.list_dns_records(
        zone_id=zone_id, type=type, name=name, content=content, page=page, per_page=per_page
    )
    summary = [
        {
            "id": r.get("id"),
            "type": r.get("type"),
            "name": r.get("name"),
            "content": r.get("content"),
            "ttl": r.get("ttl"),
            "proxied": r.get("proxied"),
            "priority": r.get("priority"),
            "comment": r.get("comment"),
            "created_on": r.get("created_on"),
        }
        for r in records
    ]
    return json.dumps(
        {"success": True, "count": len(summary), "records": summary},
        indent=2,
        ensure_ascii=False,
    )


async def get_dns_record(client: CloudflareClient, zone_id: str, record_id: str) -> str:
    """Fetch a single DNS record.

    Args:
        client: CloudflareClient instance.
        zone_id: Cloudflare zone id.
        record_id: DNS record id.

    Returns:
        JSON string with the record details.
    """
    record = await client.get_dns_record(zone_id, record_id)
    return json.dumps({"success": True, "record": record}, indent=2, ensure_ascii=False)


async def create_dns_record(
    client: CloudflareClient,
    zone_id: str,
    type: str,
    name: str,
    content: str,
    ttl: int | None = None,
    proxied: bool | None = None,
    priority: int | None = None,
    comment: str | None = None,
) -> str:
    """Create a DNS record.

    Args:
        client: CloudflareClient instance.
        zone_id: Cloudflare zone id.
        type: Record type.
        name: Record name.
        content: Record content.
        ttl: TTL in seconds.
        proxied: Proxy through Cloudflare.
        priority: MX/SRV priority.
        comment: Free-form comment.

    Returns:
        JSON string with the created record.
    """
    record = await client.create_dns_record(
        zone_id=zone_id,
        type=type,
        name=name,
        content=content,
        ttl=ttl,
        proxied=proxied,
        priority=priority,
        comment=comment,
    )
    return json.dumps({"success": True, "record": record}, indent=2, ensure_ascii=False)


async def update_dns_record(
    client: CloudflareClient,
    zone_id: str,
    record_id: str,
    type: str | None = None,
    name: str | None = None,
    content: str | None = None,
    ttl: int | None = None,
    proxied: bool | None = None,
    priority: int | None = None,
    comment: str | None = None,
) -> str:
    """Update a DNS record.

    Args:
        client: CloudflareClient instance.
        zone_id: Cloudflare zone id.
        record_id: DNS record id.
        type: New record type.
        name: New record name.
        content: New record content.
        ttl: New TTL.
        proxied: Proxy through Cloudflare.
        priority: MX/SRV priority.
        comment: New comment.

    Returns:
        JSON string with the updated record.
    """
    record = await client.update_dns_record(
        zone_id=zone_id,
        record_id=record_id,
        type=type,
        name=name,
        content=content,
        ttl=ttl,
        proxied=proxied,
        priority=priority,
        comment=comment,
    )
    return json.dumps({"success": True, "record": record}, indent=2, ensure_ascii=False)


async def delete_dns_record(client: CloudflareClient, zone_id: str, record_id: str) -> str:
    """Delete a DNS record.

    Args:
        client: CloudflareClient instance.
        zone_id: Cloudflare zone id.
        record_id: DNS record id.

    Returns:
        JSON string with the delete result.
    """
    result = await client.delete_dns_record(zone_id, record_id)
    return json.dumps(
        {"success": True, "deleted_record_id": record_id, "result": result},
        indent=2,
        ensure_ascii=False,
    )
