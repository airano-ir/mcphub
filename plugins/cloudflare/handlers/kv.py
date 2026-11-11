"""KV handlers — namespaces and keys (account-scoped)."""

import json
from typing import Any

from plugins.cloudflare.client import CloudflareClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_kv_namespaces",
            "category": "read",
            "method_name": "list_kv_namespaces",
            "description": (
                "List Workers KV namespaces in the account (requires Workers KV Storage "
                "permission and Account ID). Returns each namespace's id and title."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Results per page (max 100).",
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
            "name": "create_kv_namespace",
            "category": "write",
            "method_name": "create_kv_namespace",
            "description": (
                "Create a Workers KV namespace (Workers KV Storage Edit permission). The "
                "title must be unique within the account."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Namespace title (unique per account).",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["title"],
            },
            "scope": "write",
        },
        {
            "name": "delete_kv_namespace",
            "category": "admin",
            "method_name": "delete_kv_namespace",
            "description": (
                "Delete a KV namespace and ALL its keys (Workers KV Storage Edit "
                "permission). DESTRUCTIVE — every key in the namespace is permanently lost."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "namespace_id": {
                        "type": "string",
                        "description": "KV namespace id.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["namespace_id"],
            },
            "scope": "admin",
        },
        {
            "name": "list_kv_keys",
            "category": "read",
            "method_name": "list_kv_keys",
            "description": (
                "List keys in a KV namespace (Workers KV Storage Read permission). Returns "
                "key names + metadata and a cursor for pagination."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "namespace_id": {
                        "type": "string",
                        "description": "KV namespace id.",
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor from a previous response.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max keys per page (default 100).",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["namespace_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_kv_value",
            "category": "read",
            "method_name": "get_kv_value",
            "description": (
                "Read a single KV value by key name (Workers KV Storage Read permission). "
                "Returns the stored value as text."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "namespace_id": {
                        "type": "string",
                        "description": "KV namespace id.",
                    },
                    "key_name": {
                        "type": "string",
                        "description": "Key name.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["namespace_id", "key_name"],
            },
            "scope": "read",
        },
        {
            "name": "put_kv_value",
            "category": "write",
            "method_name": "put_kv_value",
            "description": (
                "Write a KV value for a key (Workers KV Storage Edit permission). Creates "
                "the key if it does not exist. Optionally set expiration (absolute Unix "
                "timestamp) or expiration_ttl (seconds from now)."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "namespace_id": {
                        "type": "string",
                        "description": "KV namespace id.",
                    },
                    "key_name": {
                        "type": "string",
                        "description": "Key name (max 512 bytes).",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to store (max 25 MiB).",
                    },
                    "expiration": {
                        "type": "integer",
                        "description": "Absolute expiration as Unix timestamp.",
                    },
                    "expiration_ttl": {
                        "type": "integer",
                        "description": "Relative expiration in seconds from now.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["namespace_id", "key_name", "value"],
            },
            "scope": "write",
        },
        {
            "name": "delete_kv_key",
            "category": "admin",
            "method_name": "delete_kv_key",
            "description": (
                "Delete a single KV key (Workers KV Storage Edit permission). DESTRUCTIVE "
                "— the value is permanently lost."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "namespace_id": {
                        "type": "string",
                        "description": "KV namespace id.",
                    },
                    "key_name": {
                        "type": "string",
                        "description": "Key name.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["namespace_id", "key_name"],
            },
            "scope": "admin",
        },
    ]


# --- Handler functions ---


async def list_kv_namespaces(
    client: CloudflareClient, per_page: int | None = None, account_id: str | None = None
) -> str:
    """List KV namespaces.

    Args:
        client: CloudflareClient instance.
        per_page: Results per page.
        account_id: Account id override.

    Returns:
        JSON string with the namespace list.
    """
    namespaces = await client.list_kv_namespaces(account_id=account_id, per_page=per_page)
    summary = [{"id": n.get("id"), "title": n.get("title")} for n in namespaces]
    return json.dumps(
        {"success": True, "count": len(summary), "namespaces": summary},
        indent=2,
        ensure_ascii=False,
    )


async def create_kv_namespace(
    client: CloudflareClient, title: str, account_id: str | None = None
) -> str:
    """Create a KV namespace.

    Args:
        client: CloudflareClient instance.
        title: Namespace title.
        account_id: Account id override.

    Returns:
        JSON string with the created namespace.
    """
    namespace = await client.create_kv_namespace(title, account_id=account_id)
    return json.dumps({"success": True, "namespace": namespace}, indent=2, ensure_ascii=False)


async def delete_kv_namespace(
    client: CloudflareClient, namespace_id: str, account_id: str | None = None
) -> str:
    """Delete a KV namespace.

    Args:
        client: CloudflareClient instance.
        namespace_id: KV namespace id.
        account_id: Account id override.

    Returns:
        JSON string with the delete result.
    """
    result = await client.delete_kv_namespace(namespace_id, account_id=account_id)
    return json.dumps(
        {"success": True, "deleted_namespace_id": namespace_id, "result": result},
        indent=2,
        ensure_ascii=False,
    )


async def list_kv_keys(
    client: CloudflareClient,
    namespace_id: str,
    cursor: str | None = None,
    limit: int | None = None,
    account_id: str | None = None,
) -> str:
    """List keys in a KV namespace.

    Args:
        client: CloudflareClient instance.
        namespace_id: KV namespace id.
        cursor: Pagination cursor.
        limit: Max keys per page.
        account_id: Account id override.

    Returns:
        JSON string with keys and cursor.
    """
    result = await client.list_kv_keys(
        namespace_id=namespace_id, cursor=cursor, limit=limit, account_id=account_id
    )
    keys = result.get("keys", [])
    summary = [
        {
            "name": k.get("name"),
            "expiration": k.get("expiration"),
            "metadata": k.get("metadata"),
        }
        for k in keys
    ]
    return json.dumps(
        {
            "success": True,
            "count": len(summary),
            "keys": summary,
            "cursor": result.get("cursor"),
            "list_complete": result.get("list_complete"),
        },
        indent=2,
        ensure_ascii=False,
    )


async def get_kv_value(
    client: CloudflareClient,
    namespace_id: str,
    key_name: str,
    account_id: str | None = None,
) -> str:
    """Read a KV value.

    Args:
        client: CloudflareClient instance.
        namespace_id: KV namespace id.
        key_name: Key name.
        account_id: Account id override.

    Returns:
        JSON string with the value.
    """
    value = await client.get_kv_value(namespace_id, key_name, account_id=account_id)
    return json.dumps(
        {"success": True, "namespace_id": namespace_id, "key": key_name, "value": value},
        indent=2,
        ensure_ascii=False,
    )


async def put_kv_value(
    client: CloudflareClient,
    namespace_id: str,
    key_name: str,
    value: str,
    expiration: int | None = None,
    expiration_ttl: int | None = None,
    account_id: str | None = None,
) -> str:
    """Write a KV value.

    Args:
        client: CloudflareClient instance.
        namespace_id: KV namespace id.
        key_name: Key name.
        value: Value to store.
        expiration: Absolute expiration (Unix ts).
        expiration_ttl: Relative expiration (seconds).
        account_id: Account id override.

    Returns:
        JSON string with the write result.
    """
    result = await client.put_kv_value(
        namespace_id=namespace_id,
        key_name=key_name,
        value=value,
        expiration=expiration,
        expiration_ttl=expiration_ttl,
        account_id=account_id,
    )
    return json.dumps(
        {
            "success": True,
            "namespace_id": namespace_id,
            "key": key_name,
            "written": True,
            "result": result,
        },
        indent=2,
        ensure_ascii=False,
    )


async def delete_kv_key(
    client: CloudflareClient,
    namespace_id: str,
    key_name: str,
    account_id: str | None = None,
) -> str:
    """Delete a KV key.

    Args:
        client: CloudflareClient instance.
        namespace_id: KV namespace id.
        key_name: Key name.
        account_id: Account id override.

    Returns:
        JSON string with the delete result.
    """
    result = await client.delete_kv_value(namespace_id, key_name, account_id=account_id)
    return json.dumps(
        {"success": True, "namespace_id": namespace_id, "deleted_key": key_name, "result": result},
        indent=2,
        ensure_ascii=False,
    )
