"""Auth Handler - manages Supabase authentication via GoTrue Admin API"""

import json
from typing import Any

from plugins.supabase.client import SupabaseClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (14 tools)"""
    return [
        {
            "name": "list_users",
            "method_name": "list_users",
            "description": "List all users with pagination. Returns user details including email, phone, metadata, and confirmation status.",
            "schema": {
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": "Page number (1-indexed)",
                        "default": 1,
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Users per page (max 1000)",
                        "default": 50,
                    },
                },
            },
            "scope": "admin",
        },
        {
            "name": "get_user",
            "method_name": "get_user",
            "description": "Get detailed information about a specific user by their ID.",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User UUID"}},
                "required": ["user_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_user",
            "method_name": "create_user",
            "description": "Create a new user with email and password. Can optionally auto-confirm email and set metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "User email address",
                    },
                    "password": {
                        "type": "string",
                        "minLength": 6,
                        "description": "Password (min 6 characters)",
                    },
                    "phone": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Phone number in E.164 format",
                    },
                    "email_confirm": {
                        "type": "boolean",
                        "description": "Auto-confirm email without verification",
                        "default": False,
                    },
                    "user_metadata": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Custom user metadata (name, avatar, etc.)",
                    },
                    "app_metadata": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "App-specific metadata (roles, permissions)",
                    },
                },
                "required": ["email", "password"],
            },
            "scope": "admin",
        },
        {
            "name": "update_user",
            "method_name": "update_user",
            "description": "Update user details including email, password, phone, metadata, or ban status.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User UUID"},
                    "email": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New email address",
                    },
                    "password": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New password",
                    },
                    "phone": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New phone number",
                    },
                    "email_confirm": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Set email confirmation status",
                    },
                    "phone_confirm": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Set phone confirmation status",
                    },
                    "user_metadata": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Update user metadata",
                    },
                    "app_metadata": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Update app metadata",
                    },
                },
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_user",
            "method_name": "delete_user",
            "description": "Permanently delete a user and all their data.",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User UUID to delete"}},
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        {
            "name": "invite_user",
            "method_name": "invite_user",
            "description": "Send an email invitation to a new user. Creates user in 'invited' state.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "Email to invite",
                    },
                    "redirect_to": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "URL to redirect after accepting invitation",
                    },
                    "user_metadata": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Initial user metadata",
                    },
                },
                "required": ["email"],
            },
            "scope": "admin",
        },
        {
            "name": "generate_link",
            "method_name": "generate_link",
            "description": "Generate a magic link, recovery link, or invite link for a user.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email", "description": "User email"},
                    "link_type": {
                        "type": "string",
                        "enum": [
                            "magiclink",
                            "recovery",
                            "invite",
                            "signup",
                            "email_change_new",
                            "email_change_current",
                        ],
                        "description": "Type of link to generate",
                        "default": "magiclink",
                    },
                    "redirect_to": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "URL to redirect after link is used",
                    },
                },
                "required": ["email"],
            },
            "scope": "admin",
        },
        {
            "name": "ban_user",
            "method_name": "ban_user",
            "description": "Ban a user for a specified duration. Banned users cannot sign in.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User UUID"},
                    "duration": {
                        "type": "string",
                        "description": "Ban duration (e.g., '24h', '7d', '1y', 'none' for permanent)",
                        "default": "none",
                    },
                },
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        {
            "name": "unban_user",
            "method_name": "unban_user",
            "description": "Remove ban from a user, allowing them to sign in again.",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User UUID"}},
                "required": ["user_id"],
            },
            "scope": "admin",
        },
        {
            "name": "list_user_factors",
            "method_name": "list_user_factors",
            "description": "List all MFA factors (TOTP, phone) for a user.",
            "schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User UUID"}},
                "required": ["user_id"],
            },
            "scope": "read",
        },
        {
            "name": "delete_user_factor",
            "method_name": "delete_user_factor",
            "description": "Delete an MFA factor from a user.",
            "schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User UUID"},
                    "factor_id": {"type": "string", "description": "Factor UUID to delete"},
                },
                "required": ["user_id", "factor_id"],
            },
            "scope": "admin",
        },
        {
            "name": "get_auth_config",
            "method_name": "get_auth_config",
            "description": "Get current GoTrue authentication configuration.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "search_users",
            "method_name": "search_users",
            "description": "Search users by email or phone number.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (email or phone)"},
                    "page": {"type": "integer", "default": 1},
                    "per_page": {"type": "integer", "default": 50},
                },
                "required": ["query"],
            },
            "scope": "read",
        },
        {
            "name": "get_user_by_email",
            "method_name": "get_user_by_email",
            "description": "Find a user by their email address.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "Email to search for",
                    }
                },
                "required": ["email"],
            },
            "scope": "read",
        },
    ]

# =====================
# Auth Operations (14 tools)
# =====================

async def list_users(client: SupabaseClient, page: int = 1, per_page: int = 50) -> str:
    """List all users with pagination"""
    try:
        result = await client.list_users(page=page, per_page=per_page)

        users = result.get("users", []) if isinstance(result, dict) else result
        result.get("aud", len(users)) if isinstance(result, dict) else len(users)

        return json.dumps(
            {
                "success": True,
                "page": page,
                "per_page": per_page,
                "count": len(users) if isinstance(users, list) else 0,
                "users": users,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_user(client: SupabaseClient, user_id: str) -> str:
    """Get user by ID"""
    try:
        result = await client.get_user(user_id)

        return json.dumps({"success": True, "user": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_user(
    client: SupabaseClient,
    email: str,
    password: str,
    phone: str | None = None,
    email_confirm: bool = False,
    user_metadata: dict | None = None,
    app_metadata: dict | None = None,
) -> str:
    """Create a new user"""
    try:
        result = await client.create_user(
            email=email,
            password=password,
            phone=phone,
            email_confirm=email_confirm,
            user_metadata=user_metadata,
            app_metadata=app_metadata,
        )

        return json.dumps(
            {"success": True, "message": "User created successfully", "user": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_user(
    client: SupabaseClient,
    user_id: str,
    email: str | None = None,
    password: str | None = None,
    phone: str | None = None,
    email_confirm: bool | None = None,
    phone_confirm: bool | None = None,
    user_metadata: dict | None = None,
    app_metadata: dict | None = None,
) -> str:
    """Update user details"""
    try:
        result = await client.update_user(
            user_id=user_id,
            email=email,
            password=password,
            phone=phone,
            email_confirm=email_confirm,
            phone_confirm=phone_confirm,
            user_metadata=user_metadata,
            app_metadata=app_metadata,
        )

        return json.dumps(
            {"success": True, "message": "User updated successfully", "user": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_user(client: SupabaseClient, user_id: str) -> str:
    """Delete a user"""
    try:
        await client.delete_user(user_id)

        return json.dumps(
            {"success": True, "message": f"User {user_id} deleted successfully"},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def invite_user(
    client: SupabaseClient,
    email: str,
    redirect_to: str | None = None,
    user_metadata: dict | None = None,
) -> str:
    """Invite a user by email"""
    try:
        result = await client.generate_link(
            email=email, link_type="invite", redirect_to=redirect_to
        )

        return json.dumps(
            {"success": True, "message": f"Invitation sent to {email}", "result": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def generate_link(
    client: SupabaseClient, email: str, link_type: str = "magiclink", redirect_to: str | None = None
) -> str:
    """Generate auth link (magic link, recovery, invite)"""
    try:
        result = await client.generate_link(
            email=email, link_type=link_type, redirect_to=redirect_to
        )

        return json.dumps(
            {"success": True, "link_type": link_type, "email": email, "result": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def ban_user(client: SupabaseClient, user_id: str, duration: str = "none") -> str:
    """Ban a user"""
    try:
        result = await client.update_user(user_id=user_id, ban_duration=duration)

        return json.dumps(
            {"success": True, "message": f"User {user_id} banned for {duration}", "user": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def unban_user(client: SupabaseClient, user_id: str) -> str:
    """Unban a user"""
    try:
        result = await client.update_user(user_id=user_id, ban_duration="0")

        return json.dumps(
            {"success": True, "message": f"User {user_id} unbanned", "user": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_user_factors(client: SupabaseClient, user_id: str) -> str:
    """List user MFA factors"""
    try:
        result = await client.list_user_factors(user_id)

        return json.dumps(
            {"success": True, "user_id": user_id, "factors": result}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_user_factor(client: SupabaseClient, user_id: str, factor_id: str) -> str:
    """Delete an MFA factor"""
    try:
        await client.delete_user_factor(user_id, factor_id)

        return json.dumps(
            {"success": True, "message": f"Factor {factor_id} deleted from user {user_id}"},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_auth_config(client: SupabaseClient) -> str:
    """Get auth configuration"""
    try:
        # Get health which includes some config info
        result = await client.request("GET", "/auth/v1/health", use_service_role=False)

        return json.dumps({"success": True, "config": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def search_users(
    client: SupabaseClient, query: str, page: int = 1, per_page: int = 50
) -> str:
    """Search users by email or phone"""
    try:
        # Get all users and filter
        result = await client.list_users(page=page, per_page=per_page)

        users = result.get("users", []) if isinstance(result, dict) else result

        # Filter by query
        query_lower = query.lower()
        filtered = [
            u
            for u in users
            if (
                u.get("email", "").lower().find(query_lower) >= 0
                or u.get("phone", "").find(query) >= 0
            )
        ]

        return json.dumps(
            {"success": True, "query": query, "count": len(filtered), "users": filtered},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_user_by_email(client: SupabaseClient, email: str) -> str:
    """Find user by email"""
    try:
        # Get all users and find by email
        result = await client.list_users(page=1, per_page=1000)

        users = result.get("users", []) if isinstance(result, dict) else result

        # Find exact match
        user = next((u for u in users if u.get("email", "").lower() == email.lower()), None)

        if user:
            return json.dumps(
                {"success": True, "found": True, "user": user}, indent=2, ensure_ascii=False
            )
        else:
            return json.dumps(
                {"success": True, "found": False, "message": f"No user found with email: {email}"},
                indent=2,
                ensure_ascii=False,
            )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
