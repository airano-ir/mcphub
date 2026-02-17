"""Taxonomy Handler - manages WordPress categories, tags, and custom taxonomies"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === CATEGORIES ===
        {
            "name": "list_categories",
            "method_name": "list_categories",
            "description": "List WordPress post categories. Returns hierarchical list of categories with post counts.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of categories per page (1-100)",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "hide_empty": {
                        "type": "boolean",
                        "description": "Hide categories with no posts",
                        "default": False,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "create_category",
            "method_name": "create_category",
            "description": "Create a new WordPress category. Supports hierarchical categories with parent relationships.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Category name", "minLength": 1},
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Category description",
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Parent category ID for hierarchy",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_category",
            "method_name": "update_category",
            "description": "Update an existing WordPress category. Can modify name, description, and parent category.",
            "schema": {
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "integer",
                        "description": "Category ID to update",
                        "minimum": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New category name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New category description",
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "New parent category ID",
                    },
                },
                "required": ["category_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_category",
            "method_name": "delete_category",
            "description": "Delete a WordPress category. Can permanently delete or reassign posts to another category.",
            "schema": {
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "integer",
                        "description": "Category ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force permanent deletion",
                        "default": False,
                    },
                },
                "required": ["category_id"],
            },
            "scope": "write",
        },
        # === TAGS ===
        {
            "name": "list_tags",
            "method_name": "list_tags",
            "description": "List WordPress post tags. Returns all tags with usage counts and metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of tags per page (1-100)",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "hide_empty": {
                        "type": "boolean",
                        "description": "Hide tags with no posts",
                        "default": False,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "create_tag",
            "method_name": "create_tag",
            "description": "Create a new WordPress tag. Tag slug is auto-generated from name if not provided.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tag name", "minLength": 1},
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Tag description",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_tag",
            "method_name": "update_tag",
            "description": "Update an existing WordPress tag. Can modify name and description.",
            "schema": {
                "type": "object",
                "properties": {
                    "tag_id": {"type": "integer", "description": "Tag ID to update", "minimum": 1},
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New tag name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New tag description",
                    },
                },
                "required": ["tag_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_tag",
            "method_name": "delete_tag",
            "description": "Delete a WordPress tag. Permanently removes the tag from all posts.",
            "schema": {
                "type": "object",
                "properties": {
                    "tag_id": {"type": "integer", "description": "Tag ID to delete", "minimum": 1},
                    "force": {
                        "type": "boolean",
                        "description": "Force permanent deletion",
                        "default": False,
                    },
                },
                "required": ["tag_id"],
            },
            "scope": "write",
        },
        # === CUSTOM TAXONOMIES ===
        {
            "name": "list_taxonomies",
            "method_name": "list_taxonomies",
            "description": "List all registered taxonomies including built-in (category, post_tag) and custom taxonomies. Returns configuration and post type associations.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "list_taxonomy_terms",
            "method_name": "list_taxonomy_terms",
            "description": "List terms of a specific taxonomy. Works with any registered taxonomy including categories, tags, and custom taxonomies.",
            "schema": {
                "type": "object",
                "properties": {
                    "taxonomy": {
                        "type": "string",
                        "description": "Taxonomy slug (e.g., 'category', 'post_tag', 'product_cat')",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Number of terms per page",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "hide_empty": {
                        "type": "boolean",
                        "description": "Hide terms with no posts",
                        "default": False,
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Filter by parent term ID (for hierarchical taxonomies)",
                    },
                },
                "required": ["taxonomy"],
            },
            "scope": "read",
        },
        {
            "name": "create_taxonomy_term",
            "method_name": "create_taxonomy_term",
            "description": "Create a new term in a taxonomy. Supports hierarchical taxonomies with parent terms. Works with any registered taxonomy.",
            "schema": {
                "type": "object",
                "properties": {
                    "taxonomy": {
                        "type": "string",
                        "description": "Taxonomy slug (e.g., 'category', 'product_cat')",
                    },
                    "name": {"type": "string", "description": "Term name", "minLength": 1},
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Term description",
                    },
                    "parent": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Parent term ID for hierarchical taxonomies (e.g., subcategories)",
                    },
                },
                "required": ["taxonomy", "name"],
            },
            "scope": "write",
        },
    ]


class TaxonomyHandler:
    """Handle taxonomy-related operations for WordPress"""

    def __init__(self, client: WordPressClient):
        """
        Initialize taxonomy handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    # === CATEGORIES ===

    async def list_categories(
        self, per_page: int = 100, page: int = 1, hide_empty: bool = False
    ) -> str:
        """
        List WordPress post categories.

        Args:
            per_page: Number of categories per page (1-100)
            page: Page number
            hide_empty: Hide categories with no posts

        Returns:
            JSON string with categories list
        """
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",
            }

            categories = await self.client.get("categories", params=params)

            result = {
                "total": len(categories),
                "categories": [
                    {
                        "id": cat["id"],
                        "name": cat["name"],
                        "slug": cat["slug"],
                        "description": cat.get("description", ""),
                        "count": cat.get("count", 0),
                        "parent": cat.get("parent", 0),
                    }
                    for cat in categories
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list categories: {str(e)}"}, indent=2
            )

    async def create_category(
        self, name: str, description: str | None = None, parent: int | None = None
    ) -> str:
        """
        Create a new WordPress category.

        Args:
            name: Category name
            description: Category description
            parent: Parent category ID for hierarchy

        Returns:
            JSON string with created category data
        """
        try:
            data = {"name": name}
            if description:
                data["description"] = description
            if parent:
                data["parent"] = parent

            category = await self.client.post("categories", json_data=data)

            result = {
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "message": f"Category '{name}' created successfully with ID {category['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create category: {str(e)}"}, indent=2
            )

    async def update_category(
        self,
        category_id: int,
        name: str | None = None,
        description: str | None = None,
        parent: int | None = None,
    ) -> str:
        """
        Update an existing WordPress category.

        Args:
            category_id: Category ID to update
            name: New category name
            description: New category description
            parent: New parent category ID

        Returns:
            JSON string with updated category data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if name is not None:
                data["name"] = name
            if description is not None:
                data["description"] = description
            if parent is not None:
                data["parent"] = parent

            category = await self.client.post(f"categories/{category_id}", json_data=data)

            result = {
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "message": f"Category {category_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update category {category_id}: {str(e)}"},
                indent=2,
            )

    async def delete_category(self, category_id: int, force: bool = False) -> str:
        """
        Delete a WordPress category.

        Args:
            category_id: Category ID to delete
            force: Force permanent deletion

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(f"categories/{category_id}", params=params)

            message = f"Category {category_id} deleted successfully"
            return json.dumps({"success": True, "message": message, "result": result}, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete category {category_id}: {str(e)}"},
                indent=2,
            )

    # === TAGS ===

    async def list_tags(self, per_page: int = 100, page: int = 1, hide_empty: bool = False) -> str:
        """
        List WordPress post tags.

        Args:
            per_page: Number of tags per page (1-100)
            page: Page number
            hide_empty: Hide tags with no posts

        Returns:
            JSON string with tags list
        """
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",
            }

            tags = await self.client.get("tags", params=params)

            result = {
                "total": len(tags),
                "tags": [
                    {
                        "id": tag["id"],
                        "name": tag["name"],
                        "slug": tag["slug"],
                        "description": tag.get("description", ""),
                        "count": tag.get("count", 0),
                    }
                    for tag in tags
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list tags: {str(e)}"}, indent=2
            )

    async def create_tag(self, name: str, description: str | None = None) -> str:
        """
        Create a new WordPress tag.

        Args:
            name: Tag name
            description: Tag description

        Returns:
            JSON string with created tag data
        """
        try:
            data = {"name": name}
            if description:
                data["description"] = description

            tag = await self.client.post("tags", json_data=data)

            result = {
                "id": tag["id"],
                "name": tag["name"],
                "slug": tag["slug"],
                "message": f"Tag '{name}' created successfully with ID {tag['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create tag: {str(e)}"}, indent=2
            )

    async def update_tag(
        self, tag_id: int, name: str | None = None, description: str | None = None
    ) -> str:
        """
        Update an existing WordPress tag.

        Args:
            tag_id: Tag ID to update
            name: New tag name
            description: New tag description

        Returns:
            JSON string with updated tag data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if name is not None:
                data["name"] = name
            if description is not None:
                data["description"] = description

            tag = await self.client.post(f"tags/{tag_id}", json_data=data)

            result = {
                "id": tag["id"],
                "name": tag["name"],
                "slug": tag["slug"],
                "message": f"Tag {tag_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update tag {tag_id}: {str(e)}"}, indent=2
            )

    async def delete_tag(self, tag_id: int, force: bool = False) -> str:
        """
        Delete a WordPress tag.

        Args:
            tag_id: Tag ID to delete
            force: Force permanent deletion

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(f"tags/{tag_id}", params=params)

            message = f"Tag {tag_id} deleted successfully"
            return json.dumps({"success": True, "message": message, "result": result}, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete tag {tag_id}: {str(e)}"}, indent=2
            )

    # === CUSTOM TAXONOMIES ===

    async def list_taxonomies(self) -> str:
        """
        List all registered taxonomies.

        Returns list of all taxonomies including built-in (category, post_tag)
        and custom taxonomies (portfolio_category, etc.).

        Returns:
            JSON string with total count and taxonomies list
        """
        try:
            taxonomies_data = await self.client.get("taxonomies")

            # Convert dict to list
            taxonomies = []
            if isinstance(taxonomies_data, dict):
                for slug, data in taxonomies_data.items():
                    taxonomies.append(
                        {
                            "slug": slug,
                            "name": data.get("name", slug),
                            "description": data.get("description", ""),
                            "types": data.get("types", []),
                            "hierarchical": data.get("hierarchical", False),
                            "rest_base": data.get("rest_base", slug),
                        }
                    )

            result = {"total": len(taxonomies), "taxonomies": taxonomies}

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list taxonomies: {str(e)}"}, indent=2
            )

    async def list_taxonomy_terms(
        self,
        taxonomy: str,
        per_page: int = 100,
        page: int = 1,
        hide_empty: bool = False,
        parent: int | None = None,
    ) -> str:
        """
        List terms of a specific taxonomy.

        Args:
            taxonomy: Taxonomy slug (e.g., 'category', 'product_category')
            per_page: Number of terms per page
            page: Page number
            hide_empty: Hide terms with no posts
            parent: Filter by parent term ID

        Returns:
            JSON string with terms list
        """
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",
            }

            if parent is not None:
                params["parent"] = parent

            terms = await self.client.get(taxonomy, params=params)

            result = {
                "total": len(terms) if isinstance(terms, list) else 0,
                "taxonomy": taxonomy,
                "page": page,
                "per_page": per_page,
                "terms": terms,
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to list taxonomy terms for '{taxonomy}': {str(e)}",
                },
                indent=2,
            )

    async def create_taxonomy_term(
        self, taxonomy: str, name: str, description: str | None = None, parent: int | None = None
    ) -> str:
        """
        Create a new term in a taxonomy.

        Args:
            taxonomy: Taxonomy slug (e.g., 'category', 'product_category')
            name: Term name
            description: Term description
            parent: Parent term ID for hierarchical taxonomies

        Returns:
            JSON string with created term details
        """
        try:
            data = {"name": name}

            if description:
                data["description"] = description
            if parent:
                data["parent"] = parent

            term = await self.client.post(taxonomy, json_data=data)

            return json.dumps(term, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to create taxonomy term in '{taxonomy}': {str(e)}",
                },
                indent=2,
            )
