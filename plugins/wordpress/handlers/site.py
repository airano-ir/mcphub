"""Site Handler - manages WordPress site management operations"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === PLUGINS ===
        {
            "name": "list_plugins",
            "method_name": "list_plugins",
            "description": "List installed WordPress plugins. Shows plugin status (active/inactive), version, and details.",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter plugins by status",
                        "enum": ["active", "inactive", "all"],
                        "default": "all",
                    }
                },
            },
            "scope": "read",
        },
        # === THEMES ===
        {
            "name": "list_themes",
            "method_name": "list_themes",
            "description": "List installed WordPress themes. Returns all themes with their status and metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter themes by status",
                        "enum": ["active", "inactive", "all"],
                        "default": "all",
                    }
                },
            },
            "scope": "read",
        },
        {
            "name": "get_active_theme",
            "method_name": "get_active_theme",
            "description": "Get information about the currently active WordPress theme including name, version, and author.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # === SETTINGS ===
        {
            "name": "get_settings",
            "method_name": "get_settings",
            "description": "Get WordPress site settings. Includes site title, description, URL, email, timezone, and language.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # === HEALTH ===
        {
            "name": "get_site_health",
            "method_name": "get_site_health",
            "description": "Check WordPress site health and accessibility. Returns comprehensive health status including WordPress, WooCommerce, and SEO plugin availability.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]


class SiteHandler:
    """Handle site management operations for WordPress"""

    def __init__(self, client: WordPressClient):
        """
        Initialize site handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    # === PLUGINS ===

    async def list_plugins(self, status: str = "all") -> str:
        """
        List installed WordPress plugins.

        Args:
            status: Filter by plugin status (active, inactive, all)

        Returns:
            JSON string with plugins list
        """
        try:
            # Build endpoint with status filter
            params = {}
            if status != "all":
                params["status"] = status

            plugins = await self.client.get("plugins", params=params)

            result = {
                "total": len(plugins),
                "plugins": [
                    {
                        "plugin": p["plugin"],
                        "name": p["name"],
                        "version": p["version"],
                        "status": p["status"],
                        "description": p.get("description", {}).get("raw", "")[:100],
                    }
                    for p in plugins
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list plugins: {str(e)}"}, indent=2
            )

    # === THEMES ===

    async def list_themes(self, status: str = "all") -> str:
        """
        List installed WordPress themes.

        Args:
            status: Filter by theme status (active, inactive, all)

        Returns:
            JSON string with themes list
        """
        try:
            # Build endpoint with status filter
            params = {}
            if status != "all":
                params["status"] = status

            themes = await self.client.get("themes", params=params)

            result = {
                "total": len(themes),
                "themes": [
                    {
                        "stylesheet": t["stylesheet"],
                        "name": t["name"]["rendered"],
                        "version": t["version"],
                        "status": t["status"],
                    }
                    for t in themes
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list themes: {str(e)}"}, indent=2
            )

    async def get_active_theme(self) -> str:
        """
        Get the currently active WordPress theme.

        Returns:
            JSON string with active theme details
        """
        try:
            themes = await self.client.get("themes", params={"status": "active"})

            if themes:
                theme = themes[0]
                result = {
                    "stylesheet": theme["stylesheet"],
                    "name": theme["name"]["rendered"],
                    "version": theme["version"],
                    "author": theme.get("author", {}).get("raw", "Unknown"),
                }
            else:
                result = {"message": "No active theme found"}

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get active theme: {str(e)}"}, indent=2
            )

    # === SETTINGS ===

    async def get_settings(self) -> str:
        """
        Get WordPress site settings.

        Returns:
            JSON string with site settings including title, description, URL, email, timezone, and language
        """
        try:
            settings = await self.client.get("settings")

            result = {
                "title": settings.get("title", ""),
                "description": settings.get("description", ""),
                "url": settings.get("url", ""),
                "email": settings.get("email", ""),
                "timezone": settings.get("timezone_string", ""),
                "language": settings.get("language", ""),
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get settings: {str(e)}"}, indent=2
            )

    # === HEALTH ===

    async def get_site_health(self) -> str:
        """
        Check WordPress site health and accessibility.

        Returns:
            JSON string with comprehensive health status
        """
        try:
            health = await self.client.check_site_health()
            return json.dumps(health, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get site health: {str(e)}"}, indent=2
            )

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check using client's check_site_health method.

        This method is used internally and returns a dict instead of JSON string.

        Returns:
            Dict with health status information
        """
        return await self.client.check_site_health()
