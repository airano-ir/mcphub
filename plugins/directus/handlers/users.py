"""
Users Handler - User management

Phase J.2: 10 tools
- list_users, get_user, get_current_user
- create_user, update_user, delete_user, delete_users
- invite_user, accept_invite, update_current_user
"""

import json
from typing import Any

from plugins.directus.client import DirectusClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (10 tools)"""
    return [
        {
            "name": "list_users",
            "method_name": "list_users",
            "description": "List all users in Directus with filtering options.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"status": {"_eq": "active"}})',
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields (e.g., ['email'])",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum users to return",
                        "default": 100,
                    },
                    "offset": {"type": "integer", "description": "Users to skip", "default": 0},
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_user",
            "method_name": "get_user",
            "description": "Get user details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "User UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "get_current_user",
            "method_name": "get_current_user",
            "description": "Get the currently authenticated user.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "create_user",
            "method_name": "create_user",
            "description": "Create a new user.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "User email address",
                    },
                    "password": {"type": "string", "minLength": 8, "description": "User password"},
                    "role": {"type": "string", "description": "Role UUID"},
                    "first_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "First name",
                    },
                    "last_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Last name",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["draft", "invited", "active", "suspended", "archived"],
                        "default": "active",
                        "description": "User status",
                    },
                },
                "required": ["email", "password", "role"],
            },
            "scope": "admin",
        },
        {
            "name": "update_user",
            "method_name": "update_user",
            "description": "Update user details.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "User UUID"},
                    "data": {
                        "type": "object",
                        "description": "Fields to update (email, first_name, last_name, role, status, etc.)",
                    },
                },
                "required": ["id", "data"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_user",
            "method_name": "delete_user",
            "description": "Delete a user. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "User UUID to delete"}},
                "required": ["id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_users",
            "method_name": "delete_users",
            "description": "Delete multiple users. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of user UUIDs to delete",
                    }
                },
                "required": ["ids"],
            },
            "scope": "admin",
        },
        {
            "name": "invite_user",
            "method_name": "invite_user",
            "description": "Invite a user by email.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "Email to invite",
                    },
                    "role": {"type": "string", "description": "Role UUID for the invited user"},
                    "invite_url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom invite URL",
                    },
                },
                "required": ["email", "role"],
            },
            "scope": "admin",
        },
        {
            "name": "update_current_user",
            "method_name": "update_current_user",
            "description": "Update the currently authenticated user's profile.",
            "schema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Fields to update (first_name, last_name, language, theme, etc.)",
                    }
                },
                "required": ["data"],
            },
            "scope": "write",
        },
        {
            "name": "get_user_role",
            "method_name": "get_user_role",
            "description": "Get the role of a specific user.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "User UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_users(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
) -> str:
    """List users."""
    try:
        result = await client.list_users(
            filter=filter, sort=sort, limit=limit, offset=offset, search=search
        )
        users = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(users), "users": users}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_user(client: DirectusClient, id: str) -> str:
    """Get user by ID."""
    try:
        result = await client.get_user(id)
        return json.dumps(
            {"success": True, "user": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_current_user(client: DirectusClient) -> str:
    """Get current user."""
    try:
        result = await client.get_current_user()
        return json.dumps(
            {"success": True, "user": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_user(
    client: DirectusClient,
    email: str,
    password: str,
    role: str,
    first_name: str | None = None,
    last_name: str | None = None,
    status: str = "active",
) -> str:
    """Create a new user."""
    try:
        result = await client.create_user(
            email=email,
            password=password,
            role=role,
            first_name=first_name,
            last_name=last_name,
            status=status,
        )
        return json.dumps(
            {"success": True, "message": f"User {email} created", "user": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_user(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update user."""
    try:
        result = await client.update_user(id, data)
        return json.dumps(
            {"success": True, "message": "User updated", "user": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_user(client: DirectusClient, id: str) -> str:
    """Delete a user."""
    try:
        await client.delete_user(id)
        return json.dumps({"success": True, "message": f"User {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_users(client: DirectusClient, ids: list[str]) -> str:
    """Delete multiple users."""
    try:
        await client.delete_users(ids)
        return json.dumps({"success": True, "message": f"Deleted {len(ids)} users"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def invite_user(
    client: DirectusClient, email: str, role: str, invite_url: str | None = None
) -> str:
    """Invite a user."""
    try:
        result = await client.invite_user(email, role, invite_url)
        return json.dumps(
            {
                "success": True,
                "message": f"Invitation sent to {email}",
                "result": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_current_user(client: DirectusClient, data: dict[str, Any]) -> str:
    """Update current user profile."""
    try:
        # Get current user first to get ID
        current = await client.get_current_user()
        user_id = current.get("data", {}).get("id")
        if not user_id:
            return json.dumps(
                {"success": False, "error": "Cannot determine current user"}, indent=2
            )

        result = await client.update_user(user_id, data)
        return json.dumps(
            {"success": True, "message": "Profile updated", "user": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_user_role(client: DirectusClient, id: str) -> str:
    """Get user's role."""
    try:
        result = await client.get_user(id)
        user = result.get("data", {})
        role_id = user.get("role")

        if role_id:
            role_result = await client.get_role(role_id)
            return json.dumps(
                {"success": True, "user_id": id, "role": role_result.get("data")},
                indent=2,
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {
                    "success": True,
                    "user_id": id,
                    "role": None,
                    "message": "User has no role assigned",
                },
                indent=2,
            )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
