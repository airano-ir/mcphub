"""Users Handler - manages WordPress user operations"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === USERS ===
        {
            "name": "list_users",
            "method_name": "list_users",
            "description": "List WordPress users. Returns paginated list of users with name, username, email, and roles.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of users per page (1-100)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "roles": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Filter by user roles (e.g., ['administrator', 'editor', 'author'])",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_current_user",
            "method_name": "get_current_user",
            "description": "Get information about the currently authenticated user including ID, name, username, email, and roles.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]


class UsersHandler:
    """Handle user-related operations for WordPress"""

    def __init__(self, client: WordPressClient):
        """
        Initialize users handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    # === USERS ===

    async def list_users(
        self, per_page: int = 10, page: int = 1, roles: list[str] | None = None
    ) -> str:
        """
        List WordPress users.

        Args:
            per_page: Number of users per page (1-100)
            page: Page number
            roles: Filter by user roles (e.g., ['administrator', 'editor'])

        Returns:
            JSON string with users list
        """
        try:
            params = {"per_page": per_page, "page": page}
            if roles:
                params["roles"] = ",".join(roles)

            users = await self.client.get("users", params=params)

            # Format response
            result = {
                "total": len(users),
                "page": page,
                "per_page": per_page,
                "users": [
                    {
                        "id": user["id"],
                        "name": user["name"],
                        "username": user["slug"],
                        "email": user.get("email", "N/A"),
                        "roles": user.get("roles", []),
                        "link": user.get("link", ""),
                    }
                    for user in users
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list users: {str(e)}"}, indent=2
            )

    async def get_current_user(self) -> str:
        """
        Get current authenticated user.

        Returns:
            JSON string with current user data
        """
        try:
            user = await self.client.get("users/me")

            result = {
                "id": user["id"],
                "name": user["name"],
                "username": user["slug"],
                "email": user.get("email", "N/A"),
                "roles": user.get("roles", []),
                "capabilities": user.get("capabilities", {}),
                "description": user.get("description", ""),
                "link": user.get("link", ""),
                "registered_date": user.get("registered_date", ""),
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get current user: {str(e)}"}, indent=2
            )
