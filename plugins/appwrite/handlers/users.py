"""
Users Handler - manages Appwrite user operations

Phase I.2: 12 tools
- User CRUD: 5 (list, get, create, update, delete)
- User Properties: 4 (update_email, update_phone, update_status, update_labels)
- Sessions: 3 (list_sessions, delete_sessions, delete_session)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (12 tools)"""
    return [
        # =====================
        # USER CRUD (5)
        # =====================
        {
            "name": "list_users",
            "method_name": "list_users",
            "description": "List all users in the project with optional filtering and search.",
            "schema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings (e.g., 'limit(25)', 'offset(0)')",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter users by name or email",
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
                "properties": {"user_id": {"type": "string", "description": "User ID"}},
                "required": ["user_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_user",
            "method_name": "create_user",
            "description": "Create a new user. Use 'unique()' for auto-generated user ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Unique user ID. Use 'unique()' for auto-generation",
                    },
                    "email": {
                        "anyOf": [{"type": "string", "format": "email"}, {"type": "null"}],
                        "description": "User email address",
                    },
                    "phone": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User phone number (E.164 format)",
                    },
                    "password": {
                        "anyOf": [{"type": "string", "minLength": 8}, {"type": "null"}],
                        "description": "User password (min 8 characters)",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User display name",
                    },
                },
                "required": ["user_id"],
            },
            "scope": "write",
        },
        {
            "name": "update_user_name",
            "method_name": "update_user_name",
            "description": "Update user display name.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "name": {"type": "string", "description": "New display name"},
                },
                "required": ["user_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_user",
            "method_name": "delete_user",
            "description": "Delete a user. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User ID to delete"}},
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        # =====================
        # USER PROPERTIES (4)
        # =====================
        {
            "name": "update_user_email",
            "method_name": "update_user_email",
            "description": "Update user email address.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "New email address",
                    },
                },
                "required": ["user_id", "email"],
            },
            "scope": "write",
        },
        {
            "name": "update_user_phone",
            "method_name": "update_user_phone",
            "description": "Update user phone number.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "number": {
                        "type": "string",
                        "description": "New phone number (E.164 format, e.g., +14155552671)",
                    },
                },
                "required": ["user_id", "number"],
            },
            "scope": "write",
        },
        {
            "name": "update_user_status",
            "method_name": "update_user_status",
            "description": "Enable or disable a user account.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "status": {
                        "type": "boolean",
                        "description": "True to enable, False to disable",
                    },
                },
                "required": ["user_id", "status"],
            },
            "scope": "admin",
        },
        {
            "name": "update_user_labels",
            "method_name": "update_user_labels",
            "description": "Set user labels for permission management. Labels can be used in permission strings like 'label:admin'.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of label strings (replaces existing labels)",
                    },
                },
                "required": ["user_id", "labels"],
            },
            "scope": "admin",
        },
        # =====================
        # SESSIONS (3)
        # =====================
        {
            "name": "list_user_sessions",
            "method_name": "list_user_sessions",
            "description": "List all active sessions for a user.",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User ID"}},
                "required": ["user_id"],
            },
            "scope": "read",
        },
        {
            "name": "delete_user_sessions",
            "method_name": "delete_user_sessions",
            "description": "Delete all sessions for a user (force logout everywhere).",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User ID"}},
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_user_session",
            "method_name": "delete_user_session",
            "description": "Delete a specific user session.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "session_id": {"type": "string", "description": "Session ID to delete"},
                },
                "required": ["user_id", "session_id"],
            },
            "scope": "admin",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_users(
    client: AppwriteClient, queries: list[str] | None = None, search: str | None = None
) -> str:
    """List all users."""
    try:
        result = await client.list_users(queries=queries, search=search)
        users = result.get("users", [])

        response = {"success": True, "total": result.get("total", len(users)), "users": users}
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_user(client: AppwriteClient, user_id: str) -> str:
    """Get user by ID."""
    try:
        result = await client.get_user(user_id)
        return json.dumps({"success": True, "user": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_user(
    client: AppwriteClient,
    user_id: str,
    email: str | None = None,
    phone: str | None = None,
    password: str | None = None,
    name: str | None = None,
) -> str:
    """Create a new user."""
    try:
        result = await client.create_user(
            user_id=user_id, email=email, phone=phone, password=password, name=name
        )
        return json.dumps(
            {"success": True, "message": "User created successfully", "user": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_user_name(client: AppwriteClient, user_id: str, name: str) -> str:
    """Update user name."""
    try:
        result = await client.update_user_name(user_id=user_id, name=name)
        return json.dumps(
            {"success": True, "message": "User name updated successfully", "user": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_user(client: AppwriteClient, user_id: str) -> str:
    """Delete user."""
    try:
        await client.delete_user(user_id)
        return json.dumps(
            {"success": True, "message": f"User '{user_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_user_email(client: AppwriteClient, user_id: str, email: str) -> str:
    """Update user email."""
    try:
        result = await client.update_user_email(user_id=user_id, email=email)
        return json.dumps(
            {"success": True, "message": "User email updated successfully", "user": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_user_phone(client: AppwriteClient, user_id: str, number: str) -> str:
    """Update user phone."""
    try:
        result = await client.update_user_phone(user_id=user_id, number=number)
        return json.dumps(
            {"success": True, "message": "User phone updated successfully", "user": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_user_status(client: AppwriteClient, user_id: str, status: bool) -> str:
    """Update user status (enable/disable)."""
    try:
        result = await client.update_user_status(user_id=user_id, status=status)
        action = "enabled" if status else "disabled"
        return json.dumps(
            {"success": True, "message": f"User {action} successfully", "user": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_user_labels(client: AppwriteClient, user_id: str, labels: list[str]) -> str:
    """Update user labels."""
    try:
        result = await client.update_user_labels(user_id=user_id, labels=labels)
        return json.dumps(
            {"success": True, "message": f"User labels updated: {labels}", "user": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_user_sessions(client: AppwriteClient, user_id: str) -> str:
    """List user sessions."""
    try:
        result = await client.list_user_sessions(user_id)
        sessions = result.get("sessions", [])

        response = {
            "success": True,
            "user_id": user_id,
            "total": result.get("total", len(sessions)),
            "sessions": sessions,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_user_sessions(client: AppwriteClient, user_id: str) -> str:
    """Delete all user sessions."""
    try:
        await client.delete_user_sessions(user_id)
        return json.dumps(
            {"success": True, "message": f"All sessions for user '{user_id}' deleted"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_user_session(client: AppwriteClient, user_id: str, session_id: str) -> str:
    """Delete a specific session."""
    try:
        await client.delete_user_session(user_id, session_id)
        return json.dumps({"success": True, "message": f"Session '{session_id}' deleted"}, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
