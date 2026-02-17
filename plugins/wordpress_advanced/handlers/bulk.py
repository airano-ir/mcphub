"""
Bulk Operations Handler

Manages WordPress bulk operations including:
- Bulk updates for posts/products/media
- Bulk deletions
- Bulk category/tag assignments

All operations use WordPress REST API batch requests for efficiency.
Operations are limited to 100 items per request for performance.
"""

import asyncio
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_advanced.schemas.bulk import (
    BulkOperationResult,
)


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # Bulk Update Posts
        {
            "name": "bulk_update_posts",
            "method_name": "bulk_update_posts",
            "description": "Update multiple posts at once. Supports status, author, categories, tags, and more. Max 100 posts per request.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of post IDs to update",
                    },
                    "updates": {
                        "type": "object",
                        "description": "Fields to update (status, title, content, author, categories, tags, etc.)",
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": ["publish", "draft", "pending", "private"],
                            },
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "excerpt": {"type": "string"},
                            "author": {"type": "integer"},
                            "categories": {"type": "array", "items": {"type": "integer"}},
                            "tags": {"type": "array", "items": {"type": "integer"}},
                            "featured_media": {"type": "integer"},
                            "comment_status": {"type": "string", "enum": ["open", "closed"]},
                            "ping_status": {"type": "string", "enum": ["open", "closed"]},
                            "sticky": {"type": "boolean"},
                        },
                    },
                },
                "required": ["post_ids", "updates"],
            },
            "scope": "write",
        },
        # Bulk Delete Posts
        {
            "name": "bulk_delete_posts",
            "method_name": "bulk_delete_posts",
            "description": "Delete multiple posts at once. Can move to trash or permanently delete. Max 100 posts per request.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of post IDs to delete",
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "Force permanent deletion (bypass trash)",
                    },
                },
                "required": ["post_ids"],
            },
            "scope": "admin",
        },
        # Bulk Update Products
        {
            "name": "bulk_update_products",
            "method_name": "bulk_update_products",
            "description": "Update multiple WooCommerce products at once. Supports price, stock, status, and more. Max 100 products per request.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of product IDs to update",
                    },
                    "updates": {
                        "type": "object",
                        "description": "Fields to update (price, stock, status, etc.)",
                        "properties": {
                            "name": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["draft", "pending", "private", "publish"],
                            },
                            "featured": {"type": "boolean"},
                            "catalog_visibility": {
                                "type": "string",
                                "enum": ["visible", "catalog", "search", "hidden"],
                            },
                            "description": {"type": "string"},
                            "short_description": {"type": "string"},
                            "sku": {"type": "string"},
                            "price": {"type": "string"},
                            "regular_price": {"type": "string"},
                            "sale_price": {"type": "string"},
                            "stock_quantity": {"type": "integer"},
                            "stock_status": {
                                "type": "string",
                                "enum": ["instock", "outofstock", "onbackorder"],
                            },
                            "manage_stock": {"type": "boolean"},
                            "categories": {"type": "array", "items": {"type": "object"}},
                            "tags": {"type": "array", "items": {"type": "object"}},
                        },
                    },
                },
                "required": ["product_ids", "updates"],
            },
            "scope": "write",
        },
        # Bulk Delete Products
        {
            "name": "bulk_delete_products",
            "method_name": "bulk_delete_products",
            "description": "Delete multiple WooCommerce products at once. Permanently deletes products. Max 100 products per request.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of product IDs to delete",
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "Force permanent deletion",
                    },
                },
                "required": ["product_ids"],
            },
            "scope": "admin",
        },
        # Bulk Assign Categories
        {
            "name": "bulk_assign_categories",
            "method_name": "bulk_assign_categories",
            "description": "Assign categories to multiple posts/products at once. Can replace or append categories. Max 100 items per request. IMPORTANT: For posts use 'category' taxonomy IDs, for products use 'product_cat' taxonomy IDs.",
            "schema": {
                "type": "object",
                "properties": {
                    "item_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of post/product IDs",
                    },
                    "category_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "description": "List of category IDs to assign. For posts: use 'category' taxonomy IDs. For products: use 'product_cat' taxonomy IDs.",
                    },
                    "replace": {
                        "type": "boolean",
                        "default": False,
                        "description": "Replace existing categories (true) or append (false)",
                    },
                    "item_type": {
                        "type": "string",
                        "enum": ["post", "product"],
                        "default": "post",
                        "description": "Type of items",
                    },
                },
                "required": ["item_ids", "category_ids"],
            },
            "scope": "write",
        },
        # Bulk Assign Tags
        {
            "name": "bulk_assign_tags",
            "method_name": "bulk_assign_tags",
            "description": "Assign tags to multiple posts/products at once. Can replace or append tags. Max 100 items per request. IMPORTANT: For posts use 'post_tag' taxonomy IDs, for products use 'product_tag' taxonomy IDs.",
            "schema": {
                "type": "object",
                "properties": {
                    "item_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of post/product IDs",
                    },
                    "tag_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "description": "List of tag IDs to assign. For posts: use 'post_tag' taxonomy IDs. For products: use 'product_tag' taxonomy IDs.",
                    },
                    "replace": {
                        "type": "boolean",
                        "default": False,
                        "description": "Replace existing tags (true) or append (false)",
                    },
                    "item_type": {
                        "type": "string",
                        "enum": ["post", "product"],
                        "default": "post",
                        "description": "Type of items",
                    },
                },
                "required": ["item_ids", "tag_ids"],
            },
            "scope": "write",
        },
        # Bulk Update Media
        {
            "name": "bulk_update_media",
            "method_name": "bulk_update_media",
            "description": "Update multiple media items at once. Supports alt_text, title, caption, description. Max 100 items per request.",
            "schema": {
                "type": "object",
                "properties": {
                    "media_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of media IDs to update",
                    },
                    "updates": {
                        "type": "object",
                        "description": "Fields to update",
                        "properties": {
                            "title": {"type": "string"},
                            "alt_text": {"type": "string"},
                            "caption": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
                "required": ["media_ids", "updates"],
            },
            "scope": "write",
        },
        # Bulk Delete Media
        {
            "name": "bulk_delete_media",
            "method_name": "bulk_delete_media",
            "description": "Delete multiple media items at once. Permanently deletes files from server. Max 100 items per request.",
            "schema": {
                "type": "object",
                "properties": {
                    "media_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 100,
                        "description": "List of media IDs to delete",
                    },
                    "force": {
                        "type": "boolean",
                        "default": True,
                        "description": "Force permanent deletion (media can't be trashed)",
                    },
                },
                "required": ["media_ids"],
            },
            "scope": "admin",
        },
    ]


class BulkHandler:
    """Handles WordPress bulk operations"""

    def __init__(self, client: WordPressClient):
        """
        Initialize Bulk Handler

        Args:
            client: WordPress REST API client
        """
        self.client = client
        self.logger = client.logger

    async def _bulk_operation(
        self, endpoint: str, item_ids: list[int], operation: str, data: dict[str, Any] | None = None
    ) -> BulkOperationResult:
        """
        Generic bulk operation executor

        Args:
            endpoint: REST API endpoint (e.g., 'posts', 'products')
            item_ids: List of item IDs to process
            operation: 'update' or 'delete'
            data: Data for update operations

        Returns:
            BulkOperationResult with success/failure counts
        """
        success_count = 0
        failed_count = 0
        failed_ids = []
        errors = []

        # Determine if using WooCommerce API
        use_woocommerce = endpoint == "products"

        # Determine HTTP method for updates
        # WordPress REST API uses POST for media/posts updates, PUT for WooCommerce products
        update_method = "PUT" if use_woocommerce else "POST"

        # Process items in parallel (with limit to avoid overwhelming server)
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        async def process_item(item_id: int):
            nonlocal success_count, failed_count

            async with semaphore:
                try:
                    # Check if this is a WooCommerce endpoint
                    use_custom_namespace = endpoint.startswith("wc/")

                    if operation == "update":
                        await self.client.request(
                            update_method,
                            f"{endpoint}/{item_id}",
                            json_data=data,
                            use_custom_namespace=use_custom_namespace,
                        )
                    elif operation == "delete":
                        params = data or {}
                        await self.client.request(
                            "DELETE",
                            f"{endpoint}/{item_id}",
                            params=params,
                            use_custom_namespace=use_custom_namespace,
                        )

                    success_count += 1
                    return True

                except Exception as e:
                    failed_count += 1
                    failed_ids.append(item_id)
                    errors.append({"id": item_id, "error": str(e)})
                    self.logger.error(f"Bulk {operation} failed for {endpoint}/{item_id}: {str(e)}")
                    return False

        # Execute all operations in parallel
        await asyncio.gather(*[process_item(item_id) for item_id in item_ids])

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(item_ids),
            "failed_ids": failed_ids,
            "errors": errors,
        }

    async def bulk_update_posts(
        self, post_ids: list[int], updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Bulk update posts"""
        try:
            result = await self._bulk_operation(
                endpoint="posts", item_ids=post_ids, operation="update", data=updates
            )

            return {
                "success": True,
                "message": f"Updated {result['success_count']}/{result['total']} posts",
                **result,
            }

        except Exception as e:
            self.logger.error(f"Bulk update posts failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def bulk_delete_posts(self, post_ids: list[int], force: bool = False) -> dict[str, Any]:
        """Bulk delete posts"""
        try:
            result = await self._bulk_operation(
                endpoint="posts", item_ids=post_ids, operation="delete", data={"force": force}
            )

            return {
                "success": True,
                "message": f"Deleted {result['success_count']}/{result['total']} posts",
                "permanent": force,
                **result,
            }

        except Exception as e:
            self.logger.error(f"Bulk delete posts failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def bulk_update_products(
        self, product_ids: list[int], updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Bulk update WooCommerce products"""
        try:
            result = await self._bulk_operation(
                endpoint="wc/v3/products", item_ids=product_ids, operation="update", data=updates
            )

            return {
                "success": True,
                "message": f"Updated {result['success_count']}/{result['total']} products",
                **result,
            }

        except Exception as e:
            self.logger.error(f"Bulk update products failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def bulk_delete_products(
        self, product_ids: list[int], force: bool = False
    ) -> dict[str, Any]:
        """Bulk delete WooCommerce products"""
        try:
            result = await self._bulk_operation(
                endpoint="wc/v3/products",
                item_ids=product_ids,
                operation="delete",
                data={"force": force},
            )

            return {
                "success": True,
                "message": f"Deleted {result['success_count']}/{result['total']} products",
                "permanent": force,
                **result,
            }

        except Exception as e:
            self.logger.error(f"Bulk delete products failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def bulk_assign_categories(
        self,
        item_ids: list[int],
        category_ids: list[int],
        replace: bool = False,
        item_type: str = "post",
    ) -> dict[str, Any]:
        """
        Bulk assign categories to posts/products.

        IMPORTANT:
        - For posts: use category IDs from 'category' taxonomy
        - For products: use category IDs from 'product_cat' taxonomy
        """
        try:
            # Use correct endpoint for posts vs WooCommerce products
            if item_type == "post":
                endpoint = "posts"
            elif item_type == "product":
                endpoint = "wc/v3/products"  # WooCommerce endpoint
            else:
                endpoint = "posts"  # Default to posts

            # Process each item individually to handle append mode
            success_count = 0
            failed_count = 0
            failed_ids = []
            errors = []

            # Determine if using WooCommerce endpoint
            use_custom_namespace = endpoint.startswith("wc/")

            for item_id in item_ids:
                try:
                    # If append mode, get current categories first
                    if not replace:
                        if use_custom_namespace:
                            current_item = await self.client.get(
                                f"{endpoint}/{item_id}", use_custom_namespace=True
                            )
                            current_categories = current_item.get("categories", [])
                            # Extract IDs from current categories
                            current_cat_ids = [
                                cat["id"] for cat in current_categories if "id" in cat
                            ]
                            # Merge with new categories (avoid duplicates)
                            all_cat_ids = list(set(current_cat_ids + category_ids))
                        else:
                            current_item = await self.client.get(f"{endpoint}/{item_id}")
                            current_cat_ids = current_item.get("categories", [])
                            # Merge with new categories (avoid duplicates)
                            all_cat_ids = list(set(current_cat_ids + category_ids))
                    else:
                        # Replace mode: use only new categories
                        all_cat_ids = category_ids

                    # Format categories based on item type
                    if item_type == "product":
                        # WooCommerce requires categories as objects with id
                        updates = {"categories": [{"id": cat_id} for cat_id in all_cat_ids]}
                    else:
                        # WordPress posts use simple category ID array
                        updates = {"categories": all_cat_ids}

                    # Update the item
                    await self.client.request(
                        "PUT" if use_custom_namespace else "POST",
                        f"{endpoint}/{item_id}",
                        json_data=updates,
                        use_custom_namespace=use_custom_namespace,
                    )

                    success_count += 1

                except Exception as e:
                    failed_count += 1
                    failed_ids.append(item_id)
                    errors.append({"id": item_id, "error": str(e)})
                    self.logger.error(
                        f"Failed to assign categories to {item_type} {item_id}: {str(e)}"
                    )

            return {
                "success": True,
                "message": f"Assigned categories to {success_count}/{len(item_ids)} {item_type}s",
                "mode": "replace" if replace else "append",
                "success_count": success_count,
                "failed_count": failed_count,
                "total": len(item_ids),
                "failed_ids": failed_ids,
                "errors": errors,
            }

        except Exception as e:
            self.logger.error(f"Bulk assign categories failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def bulk_assign_tags(
        self,
        item_ids: list[int],
        tag_ids: list[int],
        replace: bool = False,
        item_type: str = "post",
    ) -> dict[str, Any]:
        """
        Bulk assign tags to posts/products.

        IMPORTANT:
        - For posts: use tag IDs from 'post_tag' taxonomy
        - For products: use tag IDs from 'product_tag' taxonomy
        """
        try:
            # Use correct endpoint for posts vs WooCommerce products
            if item_type == "post":
                endpoint = "posts"
            elif item_type == "product":
                endpoint = "wc/v3/products"  # WooCommerce endpoint
            else:
                endpoint = "posts"  # Default to posts

            # Process each item individually to handle append mode
            success_count = 0
            failed_count = 0
            failed_ids = []
            errors = []

            # Determine if using WooCommerce endpoint
            use_custom_namespace = endpoint.startswith("wc/")

            for item_id in item_ids:
                try:
                    # If append mode, get current tags first
                    if not replace:
                        if use_custom_namespace:
                            current_item = await self.client.get(
                                f"{endpoint}/{item_id}", use_custom_namespace=True
                            )
                            current_tags = current_item.get("tags", [])
                            # Extract IDs from current tags
                            current_tag_ids = [tag["id"] for tag in current_tags if "id" in tag]
                            # Merge with new tags (avoid duplicates)
                            all_tag_ids = list(set(current_tag_ids + tag_ids))
                        else:
                            current_item = await self.client.get(f"{endpoint}/{item_id}")
                            current_tag_ids = current_item.get("tags", [])
                            # Merge with new tags (avoid duplicates)
                            all_tag_ids = list(set(current_tag_ids + tag_ids))
                    else:
                        # Replace mode: use only new tags
                        all_tag_ids = tag_ids

                    # Format tags based on item type
                    if item_type == "product":
                        # WooCommerce requires tags as objects with id
                        updates = {"tags": [{"id": tag_id} for tag_id in all_tag_ids]}
                    else:
                        # WordPress posts use simple tag ID array
                        updates = {"tags": all_tag_ids}

                    # Update the item
                    await self.client.request(
                        "PUT" if use_custom_namespace else "POST",
                        f"{endpoint}/{item_id}",
                        json_data=updates,
                        use_custom_namespace=use_custom_namespace,
                    )

                    success_count += 1

                except Exception as e:
                    failed_count += 1
                    failed_ids.append(item_id)
                    errors.append({"id": item_id, "error": str(e)})
                    self.logger.error(f"Failed to assign tags to {item_type} {item_id}: {str(e)}")

            return {
                "success": True,
                "message": f"Assigned tags to {success_count}/{len(item_ids)} {item_type}s",
                "mode": "replace" if replace else "append",
                "success_count": success_count,
                "failed_count": failed_count,
                "total": len(item_ids),
                "failed_ids": failed_ids,
                "errors": errors,
            }

        except Exception as e:
            self.logger.error(f"Bulk assign tags failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def bulk_update_media(
        self, media_ids: list[int], updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Bulk update media items"""
        try:
            result = await self._bulk_operation(
                endpoint="media", item_ids=media_ids, operation="update", data=updates
            )

            return {
                "success": True,
                "message": f"Updated {result['success_count']}/{result['total']} media items",
                **result,
            }

        except Exception as e:
            self.logger.error(f"Bulk update media failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def bulk_delete_media(self, media_ids: list[int], force: bool = True) -> dict[str, Any]:
        """Bulk delete media items"""
        try:
            result = await self._bulk_operation(
                endpoint="media", item_ids=media_ids, operation="delete", data={"force": force}
            )

            return {
                "success": True,
                "message": f"Deleted {result['success_count']}/{result['total']} media items",
                "permanent": force,
                **result,
            }

        except Exception as e:
            self.logger.error(f"Bulk delete media failed: {str(e)}")
            return {"success": False, "error": str(e)}
