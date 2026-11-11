"""Workers script handlers — list, get, delete (account-scoped)."""

import json
from typing import Any

from plugins.cloudflare.client import CloudflareClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_workers_scripts",
            "category": "read",
            "method_name": "list_workers_scripts",
            "description": (
                "List Workers scripts in the account (requires Workers Scripts permission "
                "and Account ID). Returns script names, modification dates and sizes."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": (
                            "Account id override — when omitted the site's Account ID or "
                            "auto-discovered account is used."
                        ),
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_workers_script",
            "category": "read",
            "method_name": "get_workers_script",
            "description": (
                "Fetch Workers script metadata (id, name, modified_on, usage model). "
                "Does not return the script body."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "script_name": {
                        "type": "string",
                        "description": "Workers script name.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["script_name"],
            },
            "scope": "read",
        },
        {
            "name": "delete_workers_script",
            "category": "admin",
            "method_name": "delete_workers_script",
            "description": (
                "Delete a Workers script (requires Workers Scripts Edit permission). "
                "DESTRUCTIVE — the script and its routes stop working immediately."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "script_name": {
                        "type": "string",
                        "description": "Workers script name.",
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account id override.",
                    },
                },
                "required": ["script_name"],
            },
            "scope": "admin",
        },
    ]


# --- Handler functions ---


async def list_workers_scripts(client: CloudflareClient, account_id: str | None = None) -> str:
    """List Workers scripts.

    Args:
        client: CloudflareClient instance.
        account_id: Account id override.

    Returns:
        JSON string with the script list.
    """
    scripts = await client.list_workers_scripts(account_id=account_id)
    summary = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "modified_on": s.get("modified_on"),
            "created_on": s.get("created_on"),
            "usage_model": s.get("usage_model"),
        }
        for s in scripts
    ]
    return json.dumps(
        {"success": True, "count": len(summary), "scripts": summary},
        indent=2,
        ensure_ascii=False,
    )


async def get_workers_script(
    client: CloudflareClient, script_name: str, account_id: str | None = None
) -> str:
    """Fetch Workers script metadata.

    Args:
        client: CloudflareClient instance.
        script_name: Workers script name.
        account_id: Account id override.

    Returns:
        JSON string with script metadata.
    """
    script = await client.get_workers_script(script_name, account_id=account_id)
    return json.dumps({"success": True, "script": script}, indent=2, ensure_ascii=False)


async def delete_workers_script(
    client: CloudflareClient, script_name: str, account_id: str | None = None
) -> str:
    """Delete a Workers script.

    Args:
        client: CloudflareClient instance.
        script_name: Workers script name.
        account_id: Account id override.

    Returns:
        JSON string with the delete result.
    """
    result = await client.delete_workers_script(script_name, account_id=account_id)
    return json.dumps(
        {"success": True, "deleted_script": script_name, "result": result},
        indent=2,
        ensure_ascii=False,
    )
