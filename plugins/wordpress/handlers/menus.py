"""Menus Handler - manages WordPress navigation menus"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_menus",
            "method_name": "list_menus",
            "description": "List all WordPress navigation menus. Returns list of menus with their locations and item counts.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_menu",
            "method_name": "get_menu",
            "description": "Get detailed information about a specific menu including all items. Returns menu details with hierarchical structure of menu items.",
            "schema": {
                "type": "object",
                "properties": {
                    "menu_id": {
                        "type": "integer",
                        "description": "Menu ID to retrieve",
                        "minimum": 1,
                    }
                },
                "required": ["menu_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_menu",
            "method_name": "create_menu",
            "description": "Create a new navigation menu. Can optionally assign to theme locations.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Menu name (displayed in admin)",
                        "minLength": 1,
                    },
                    "slug": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Menu slug (auto-generated from name if not provided)",
                    },
                    "locations": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Theme locations to assign menu to (e.g., ['primary', 'footer'])",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "list_menu_items",
            "method_name": "list_menu_items",
            "description": "List all items in a specific menu. Returns hierarchical list of menu items with links and ordering.",
            "schema": {
                "type": "object",
                "properties": {
                    "menu_id": {
                        "type": "integer",
                        "description": "Menu ID to get items from",
                        "minimum": 1,
                    }
                },
                "required": ["menu_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_menu_item",
            "method_name": "create_menu_item",
            "description": "Add a new item to a menu. Supports linking to posts, pages, categories, or custom URLs.",
            "schema": {
                "type": "object",
                "properties": {
                    "menu_id": {
                        "type": "integer",
                        "description": "Menu ID to add item to",
                        "minimum": 1,
                    },
                    "title": {
                        "type": "string",
                        "description": "Item title/label displayed in menu",
                        "minLength": 1,
                    },
                    "type": {
                        "type": "string",
                        "description": "Item type: 'post_type' (post/page), 'taxonomy' (category/tag), or 'custom' (URL)",
                        "enum": ["post_type", "taxonomy", "custom"],
                    },
                    "object_id": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "ID of linked post/page/term (required for post_type/taxonomy)",
                    },
                    "url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom URL (required for type=custom)",
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Parent item ID for creating sub-menu items",
                    },
                },
                "required": ["menu_id", "title", "type"],
            },
            "scope": "write",
        },
        {
            "name": "update_menu_item",
            "method_name": "update_menu_item",
            "description": "Update an existing menu item. Can change title, URL, parent, or menu order.",
            "schema": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "Menu item ID to update",
                        "minimum": 1,
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New item title",
                    },
                    "url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New URL",
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "New parent item ID (0 for top-level)",
                    },
                    "menu_order": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Position in menu (lower numbers appear first)",
                    },
                },
                "required": ["item_id"],
            },
            "scope": "write",
        },
    ]

class MenusHandler:
    """Handle menu-related operations for WordPress"""

    def __init__(self, client: WordPressClient):
        """
        Initialize menus handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    async def list_menus(self) -> str:
        """
        List all WordPress navigation menus.

        Returns list of all menus with their locations and item counts.

        Returns:
            JSON string with total count and menu list

        Example response:
            {
              "total": 3,
              "menus": [
                {
                  "id": 2,
                  "name": "Primary Menu",
                  "slug": "primary-menu",
                  "locations": ["primary"],
                  "count": 8
                }
              ]
            }
        """
        try:
            # WordPress REST API for menus (requires plugin support)
            # Try custom endpoint first, fallback to standard if not available
            try:
                menus = await self.client.get("menus", use_custom_namespace=True)
            except:
                # Fallback: use wp/v2/navigation endpoint (WP 5.9+)
                menus = await self.client.get("navigation")

            result = {"total": len(menus) if isinstance(menus, list) else 0, "menus": menus}

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list menus: {str(e)}"}, indent=2
            )

    async def get_menu(self, menu_id: int) -> str:
        """
        Get detailed information about a specific menu including all items.

        Args:
            menu_id: Menu ID

        Returns:
            JSON string with menu details and items
        """
        try:
            # Get menu details
            try:
                menu = await self.client.get(f"menus/{menu_id}", use_custom_namespace=True)
            except:
                menu = await self.client.get(f"navigation/{menu_id}")

            # Get menu items
            menu_items = await self.list_menu_items(menu_id)

            result = {
                "menu": menu,
                "items": json.loads(menu_items) if isinstance(menu_items, str) else menu_items,
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get menu {menu_id}: {str(e)}"}, indent=2
            )

    async def create_menu(
        self, name: str, slug: str | None = None, locations: list[str] | None = None
    ) -> str:
        """
        Create a new navigation menu.

        Args:
            name: Menu name
            slug: Menu slug (auto-generated if not provided)
            locations: Theme locations to assign menu to

        Returns:
            JSON string with created menu details
        """
        try:
            data = {"name": name}
            if slug:
                data["slug"] = slug
            if locations:
                data["locations"] = locations

            try:
                menu = await self.client.post("menus", json_data=data, use_custom_namespace=True)
            except:
                # Try navigation endpoint
                menu = await self.client.post("navigation", json_data=data)

            result = {
                "id": menu.get("id"),
                "name": menu.get("name"),
                "slug": menu.get("slug"),
                "message": f"Menu '{name}' created successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create menu: {str(e)}"}, indent=2
            )

    async def list_menu_items(self, menu_id: int) -> str:
        """
        List all items in a specific menu.

        Args:
            menu_id: Menu ID

        Returns:
            JSON string with menu items list
        """
        try:
            params = {"menus": menu_id, "per_page": 100}
            items = await self.client.get("menu-items", params=params)

            result = {
                "total": len(items) if isinstance(items, list) else 0,
                "menu_id": menu_id,
                "items": items,
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to list menu items for menu {menu_id}: {str(e)}",
                },
                indent=2,
            )

    async def create_menu_item(
        self,
        menu_id: int,
        title: str,
        type: str,
        object_id: int | None = None,
        url: str | None = None,
        parent: int | None = None,
    ) -> str:
        """
        Add a new item to a menu.

        Args:
            menu_id: Menu ID to add item to
            title: Item title/label
            type: Item type (post_type, taxonomy, custom)
            object_id: ID of linked post/term (required for post_type/taxonomy)
            url: Custom URL (required for type=custom)
            parent: Parent item ID for creating sub-menu items

        Returns:
            JSON string with created menu item
        """
        try:
            data = {"menus": menu_id, "title": title, "type": type}

            if object_id:
                data["object_id"] = object_id
            if url:
                data["url"] = url
            if parent:
                data["parent"] = parent

            item = await self.client.post("menu-items", json_data=data)

            result = {
                "id": item.get("id"),
                "title": item.get("title", {}).get("rendered", title),
                "type": item.get("type"),
                "url": item.get("url"),
                "message": f"Menu item '{title}' created successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create menu item: {str(e)}"}, indent=2
            )

    async def update_menu_item(
        self,
        item_id: int,
        title: str | None = None,
        url: str | None = None,
        parent: int | None = None,
        menu_order: int | None = None,
    ) -> str:
        """
        Update an existing menu item.

        Args:
            item_id: Menu item ID
            title: New title
            url: New URL
            parent: New parent item ID
            menu_order: Position in menu

        Returns:
            JSON string with updated menu item
        """
        try:
            # Build data dict with only provided values
            data = {}
            if title is not None:
                data["title"] = title
            if url is not None:
                data["url"] = url
            if parent is not None:
                data["parent"] = parent
            if menu_order is not None:
                data["menu_order"] = menu_order

            item = await self.client.put(f"menu-items/{item_id}", json_data=data)

            result = {
                "id": item.get("id"),
                "title": item.get("title", {}).get("rendered", title),
                "url": item.get("url"),
                "menu_order": item.get("menu_order"),
                "message": f"Menu item {item_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update menu item {item_id}: {str(e)}"},
                indent=2,
            )
