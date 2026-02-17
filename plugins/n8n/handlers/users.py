"""Users Handler - manages n8n users"""

import json
from typing import Any

from plugins.n8n.client import N8nClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_users",
            "method_name": "list_users",
            "description": "List all users in the n8n instance. All parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 250},
                    "cursor": {"type": "string", "description": "OPTIONAL: Pagination cursor."},
                    "include_role": {"type": "boolean", "default": True},
                },
            },
            "scope": "admin",
        },
        {
            "name": "get_user",
            "method_name": "get_user",
            "description": "Get user details by ID or email.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "minLength": 1,
                        "description": "User ID or email",
                    },
                    "include_role": {"type": "boolean", "default": True},
                },
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        {
            "name": "create_user",
            "method_name": "create_user",
            "description": "Invite/create a new user.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email", "description": "User email"},
                    "role": {
                        "type": "string",
                        "enum": ["global:owner", "global:admin", "global:member"],
                        "default": "global:member",
                    },
                },
                "required": ["email"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_user",
            "method_name": "delete_user",
            "description": "Delete a user from the instance.",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "minLength": 1}},
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        {
            "name": "change_user_role",
            "method_name": "change_user_role",
            "description": "Change a user's global role.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "minLength": 1},
                    "new_role": {
                        "type": "string",
                        "enum": ["global:owner", "global:admin", "global:member"],
                        "description": "New role for the user",
                    },
                },
                "required": ["user_id", "new_role"],
            },
            "scope": "admin",
        },
    ]


async def list_users(
    client: N8nClient, limit: int = 100, cursor: str | None = None, include_role: bool = True
) -> str:
    try:
        response = await client.list_users(limit=limit, cursor=cursor, include_role=include_role)
        users = response.get("data", [])
        result = {
            "success": True,
            "count": len(users),
            "users": [
                {
                    "id": u.get("id"),
                    "email": u.get("email"),
                    "first_name": u.get("firstName"),
                    "last_name": u.get("lastName"),
                    "role": u.get("role"),
                    "is_pending": u.get("isPending"),
                }
                for u in users
            ],
            "next_cursor": response.get("nextCursor"),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_user(client: N8nClient, user_id: str, include_role: bool = True) -> str:
    try:
        user = await client.get_user(user_id, include_role)
        return json.dumps(
            {
                "success": True,
                "user": {
                    "id": user.get("id"),
                    "email": user.get("email"),
                    "first_name": user.get("firstName"),
                    "last_name": user.get("lastName"),
                    "role": user.get("role"),
                    "is_pending": user.get("isPending"),
                },
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_user(client: N8nClient, email: str, role: str = "global:member") -> str:
    try:
        users = [{"email": email, "role": role}]
        response = await client.create_user(users)
        return json.dumps(
            {
                "success": True,
                "message": f"User {email} invited successfully",
                "users": response.get("data", []),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_user(client: N8nClient, user_id: str) -> str:
    try:
        await client.delete_user(user_id)
        return json.dumps({"success": True, "message": f"User {user_id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def change_user_role(client: N8nClient, user_id: str, new_role: str) -> str:
    try:
        await client.change_user_role(user_id, new_role)
        return json.dumps(
            {"success": True, "message": f"User {user_id} role changed to {new_role}"}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
