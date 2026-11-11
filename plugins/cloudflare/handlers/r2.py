"""R2 bucket handlers — list, get, create, delete (account-scoped)."""

import json
from typing import Any

from plugins.cloudflare.client import CloudflareClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_r2_buckets",
            "category": "read",
            "method_name": "list_r2_buckets",
            "description": (
                "List R2 buckets in the account (requires R2 read permission and Account "
                "ID). Returns bucket names, creation dates and storage class info."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous response.",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Max buckets per page (default 20).",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_r2_bucket",
            "category": "read",
            "method_name": "get_r2_bucket",
            "description": (
                "Fetch R2 bucket metadata by name (requires R2 read permission) — creation "
                "date, storage class, location, object count."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "R2 bucket name.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["bucket_name"],
            },
            "scope": "read",
        },
        {
            "name": "create_r2_bucket",
            "category": "write",
            "method_name": "create_r2_bucket",
            "description": (
                "Create an R2 bucket (requires R2 edit permission). Bucket names must be "
                "3-63 lowercase letters, digits and hyphens, starting/ending with a letter "
                "or digit, unique within the account."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "R2 bucket name.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["bucket_name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_r2_bucket",
            "category": "admin",
            "method_name": "delete_r2_bucket",
            "description": (
                "Delete an R2 bucket and all its objects (requires R2 edit permission). "
                "DESTRUCTIVE — every object in the bucket is permanently lost."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "R2 bucket name.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["bucket_name"],
            },
            "scope": "admin",
        },
    ]


# --- Handler functions ---


async def list_r2_buckets(
    client: CloudflareClient,
    cursor: str | None = None,
    per_page: int | None = None,
    account_id: str | None = None,
) -> str:
    """List R2 buckets.

    Args:
        client: CloudflareClient instance.
        cursor: Pagination cursor.
        per_page: Max buckets per page.
        account_id: Account id override.

    Returns:
        JSON string with buckets and cursor.
    """
    result = await client.list_r2_buckets(cursor=cursor, per_page=per_page, account_id=account_id)
    buckets = result.get("buckets", [])
    summary = [
        {
            "name": b.get("name"),
            "creation_date": b.get("creation_date"),
            "storage_class": b.get("storage_class"),
            "location": b.get("location"),
        }
        for b in buckets
    ]
    return json.dumps(
        {
            "success": True,
            "count": len(summary),
            "buckets": summary,
            "cursor": result.get("cursor"),
        },
        indent=2,
        ensure_ascii=False,
    )


async def get_r2_bucket(
    client: CloudflareClient, bucket_name: str, account_id: str | None = None
) -> str:
    """Fetch R2 bucket metadata.

    Args:
        client: CloudflareClient instance.
        bucket_name: R2 bucket name.
        account_id: Account id override.

    Returns:
        JSON string with bucket details.
    """
    bucket = await client.get_r2_bucket(bucket_name, account_id=account_id)
    return json.dumps({"success": True, "bucket": bucket}, indent=2, ensure_ascii=False)


async def create_r2_bucket(
    client: CloudflareClient, bucket_name: str, account_id: str | None = None
) -> str:
    """Create an R2 bucket.

    Args:
        client: CloudflareClient instance.
        bucket_name: R2 bucket name.
        account_id: Account id override.

    Returns:
        JSON string with the created bucket.
    """
    result = await client.create_r2_bucket(bucket_name, account_id=account_id)
    return json.dumps(
        {"success": True, "bucket_name": bucket_name, "result": result},
        indent=2,
        ensure_ascii=False,
    )


async def delete_r2_bucket(
    client: CloudflareClient, bucket_name: str, account_id: str | None = None
) -> str:
    """Delete an R2 bucket.

    Args:
        client: CloudflareClient instance.
        bucket_name: R2 bucket name.
        account_id: Account id override.

    Returns:
        JSON string with the delete result.
    """
    result = await client.delete_r2_bucket(bucket_name, account_id=account_id)
    return json.dumps(
        {"success": True, "deleted_bucket": bucket_name, "result": result},
        indent=2,
        ensure_ascii=False,
    )
