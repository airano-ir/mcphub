"""User / token handlers — token verification, profile, account discovery."""

import json
from typing import Any

from plugins.cloudflare.client import CloudflareClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "verify_token",
            "category": "read",
            "method_name": "verify_token",
            "description": (
                "Verify that the configured Cloudflare API token is valid and active. "
                "Returns the token id and status. Useful as a self-diagnostic when other "
                "tools fail with permission errors."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_user",
            "category": "read",
            "method_name": "get_user",
            "description": (
                "Fetch the Cloudflare user profile authenticated by the stored API token "
                "(id, email, username). Read-only."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "list_accounts",
            "category": "read",
            "method_name": "list_accounts",
            "description": (
                "List Cloudflare accounts visible to the stored API token (id + name). "
                "Useful to discover the Account ID for Workers/KV/R2 tools when the site "
                "does not pin one."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]


# --- Handler functions ---


async def verify_token(client: CloudflareClient) -> str:
    """Verify the API token.

    Args:
        client: CloudflareClient instance.

    Returns:
        JSON string with token id and status.
    """
    result = await client.verify_token()
    return json.dumps(
        {"success": True, "token_id": result.get("id"), "status": result.get("status")},
        indent=2,
        ensure_ascii=False,
    )


async def get_user(client: CloudflareClient) -> str:
    """Fetch the authenticated user profile.

    Args:
        client: CloudflareClient instance.

    Returns:
        JSON string with the user profile.
    """
    user = await client.get_user()
    summary = {
        "id": user.get("id"),
        "email": user.get("email"),
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "country": user.get("country"),
    }
    return json.dumps({"success": True, "user": summary}, indent=2, ensure_ascii=False)


async def list_accounts(client: CloudflareClient) -> str:
    """List accounts visible to the token.

    Args:
        client: CloudflareClient instance.

    Returns:
        JSON string with the account list.
    """
    accounts = await client.list_accounts()
    summary = [{"id": a.get("id"), "name": a.get("name")} for a in accounts]
    return json.dumps(
        {"success": True, "count": len(summary), "accounts": summary},
        indent=2,
        ensure_ascii=False,
    )
