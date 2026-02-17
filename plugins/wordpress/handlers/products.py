"""Products Handler - manages WooCommerce products and related entities"""

import asyncio
import json
import re
from typing import Any

from plugins.wordpress.client import WordPressClient


def _count_words(html_content: str) -> int:
    """Strip HTML tags and count words."""
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split()) if text else 0


def _strip_html(html_content: str, max_chars: int = 500) -> str:
    """Strip HTML tags and return first max_chars characters."""
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


def normalize_id_list(value: Any, field_name: str = "item") -> list[dict[str, Any]]:
    """
    Convert various formats of category/tag IDs to WooCommerce API format.

    Phase K.2.1: Support multiple input formats for better UX
    Phase K.2.2: Also support name-based format for tags

    Supported formats:
        - 62 → [{"id": 62}]
        - "62" → [{"id": 62}]
        - [62, 63] → [{"id": 62}, {"id": 63}]
        - "62,63" → [{"id": 62}, {"id": 63}]
        - [{"id": 62}] → [{"id": 62}] (no change)
        - [{"name": "Tag Name"}] → [{"name": "Tag Name"}] (for tags - WooCommerce creates if not exists)
        - "Tag1, Tag2" (non-numeric) → [{"name": "Tag1"}, {"name": "Tag2"}]

    Args:
        value: Input value in any supported format
        field_name: Name of field for error messages

    Returns:
        List of dicts in WooCommerce format: [{"id": int}, ...] or [{"name": str}, ...]
    """
    if value is None:
        return []

    result = []

    # Case 1: Already in correct format [{"id": x}] or [{"name": x}]
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                if "id" in item:
                    # ID format - convert to int
                    result.append({"id": int(item["id"])})
                elif "name" in item:
                    # Name format - keep as string (WooCommerce will create/find tag)
                    result.append({"name": str(item["name"])})
            elif isinstance(item, (int, float)):
                # List of integers
                result.append({"id": int(item)})
            elif isinstance(item, str):
                item_stripped = item.strip()
                if item_stripped.isdigit():
                    # List of string integers
                    result.append({"id": int(item_stripped)})
                elif item_stripped:
                    # List of string names (for tags)
                    result.append({"name": item_stripped})
        return result

    # Case 2: Single integer
    if isinstance(value, (int, float)):
        return [{"id": int(value)}]

    # Case 3: String (could be "62" or "62,63" or "Tag1, Tag2")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        # Handle comma-separated
        if "," in value:
            for part in value.split(","):
                part = part.strip()
                if part.isdigit():
                    result.append({"id": int(part)})
                elif part:
                    # Non-numeric - treat as name
                    result.append({"name": part})
            return result
        # Single value
        if value.isdigit():
            return [{"id": int(value)}]
        else:
            # Non-numeric single value - treat as name
            return [{"name": value}]

    return result


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === PRODUCTS ===
        {
            "name": "list_products",
            "method_name": "list_products",
            "description": "List WooCommerce products. Returns paginated list with pricing, stock status, and categories. Supports filtering by category, stock status, and search.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of products per page (1-100)",
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
                    "status": {
                        "type": "string",
                        "description": "Filter by product status. Use 'publish' to see only live products with prices. Default 'any' includes drafts.",
                        "enum": ["draft", "pending", "private", "publish", "any"],
                        "default": "any",
                    },
                    "category": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Filter by category ID",
                    },
                    "stock_status": {
                        "anyOf": [
                            {"type": "string", "enum": ["instock", "outofstock", "onbackorder"]},
                            {"type": "null"},
                        ],
                        "description": "Filter by stock status (optional)",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter products",
                    },
                    "search_terms": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Multiple search terms to search in parallel. Results are deduplicated. Overrides 'search' if both provided.",
                    },
                    "include_content": {
                        "type": "boolean",
                        "description": "Include description summary (first 500 chars) and word count in results. Default false to save tokens.",
                        "default": False,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_product",
            "method_name": "get_product",
            "description": "Get detailed information about a specific WooCommerce product by ID. Returns complete product data including pricing, inventory, images, categories, tags, and attributes.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Product ID to retrieve",
                        "minimum": 1,
                    },
                    "fields": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated list of fields to return (e.g., 'id,name,price,status'). Returns all fields if not specified. Use to reduce response size and token usage.",
                    },
                },
                "required": ["product_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_product",
            "method_name": "create_product",
            "description": "Create a new WooCommerce product. Supports simple and variable products with pricing, inventory, categories, tags, and descriptions.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Product name/title", "minLength": 1},
                    "type": {
                        "type": "string",
                        "description": "Product type",
                        "enum": ["simple", "grouped", "external", "variable"],
                        "default": "simple",
                    },
                    "regular_price": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product regular price (e.g., '19.99')",
                    },
                    "sale_price": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product sale price (e.g., '14.99')",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product full description (HTML allowed)",
                    },
                    "short_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product short description/summary",
                    },
                    "status": {
                        "type": "string",
                        "description": "Product status",
                        "enum": ["draft", "pending", "private", "publish"],
                        "default": "draft",
                    },
                    "categories": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Category IDs to assign to product",
                    },
                    "tags": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Tag IDs to assign to product",
                    },
                    "stock_quantity": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Stock quantity (requires manage_stock to be true)",
                    },
                    "manage_stock": {
                        "type": "boolean",
                        "description": "Enable stock management",
                        "default": False,
                    },
                    "stock_status": {
                        "type": "string",
                        "description": "Stock status",
                        "enum": ["instock", "outofstock", "onbackorder"],
                        "default": "instock",
                    },
                    "attributes": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "options": {"type": "array", "items": {"type": "string"}},
                                        "visible": {"type": "boolean"},
                                        "variation": {"type": "boolean"},
                                    },
                                },
                            },
                            {"type": "null"},
                        ],
                        "description": 'Product attributes for variable products (e.g., [{"name": "Color", "options": ["Red", "Blue"], "variation": true}])',
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_product",
            "method_name": "update_product",
            "description": "Update an existing WooCommerce product. Can update any field including name, slug (permalink), pricing, inventory, status, categories, tags, and more.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Product ID to update",
                        "minimum": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product name/title",
                    },
                    "slug": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product slug (SEO-friendly URL path, e.g., 'my-product')",
                    },
                    "regular_price": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product regular price",
                    },
                    "sale_price": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product sale price",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product full description",
                    },
                    "short_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product short description",
                    },
                    "status": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product status",
                        "enum": ["draft", "pending", "private", "publish"],
                    },
                    "categories": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Category IDs to assign to product",
                    },
                    "tags": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Tag IDs to assign to product",
                    },
                    "stock_quantity": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Stock quantity",
                    },
                    "stock_status": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Stock status",
                        "enum": ["instock", "outofstock", "onbackorder"],
                    },
                    "featured": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Featured product flag",
                    },
                    "weight": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product weight",
                    },
                },
                "required": ["product_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_product",
            "method_name": "delete_product",
            "description": "Delete or trash a WooCommerce product. Can permanently delete or move to trash for later restoration.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Product ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Permanently delete (true) or move to trash (false)",
                        "default": False,
                    },
                },
                "required": ["product_id"],
            },
            "scope": "write",
        },
        # === PRODUCT CATEGORIES ===
        {
            "name": "list_product_categories",
            "method_name": "list_product_categories",
            "description": "List WooCommerce product categories. Returns hierarchical category structure with product counts and parent relationships.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of categories per page (1-100)",
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
                    "hide_empty": {
                        "type": "boolean",
                        "description": "Hide categories with no products",
                        "default": False,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "create_product_category",
            "method_name": "create_product_category",
            "description": "Create a new WooCommerce product category. Supports hierarchical categories with parent-child relationships.",
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
                        "description": "Parent category ID for hierarchical structure",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        # === PRODUCT TAGS ===
        {
            "name": "list_product_tags",
            "method_name": "list_product_tags",
            "description": "List WooCommerce product tags. Returns all product tags with usage counts.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of tags per page (1-100)",
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
                    "hide_empty": {
                        "type": "boolean",
                        "description": "Hide tags with no products",
                        "default": False,
                    },
                },
            },
            "scope": "read",
        },
        # === PRODUCT ATTRIBUTES ===
        {
            "name": "list_product_attributes",
            "method_name": "list_product_attributes",
            "description": "List all global WooCommerce product attributes. Attributes are used for product variations (e.g., Size, Color).",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "create_product_attribute",
            "method_name": "create_product_attribute",
            "description": "Create a new global product attribute for use in variable products. Attributes define variation options like Size or Color.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Attribute name (e.g., 'Size', 'Color')",
                        "minLength": 1,
                    },
                    "slug": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Attribute slug (auto-generated if not provided)",
                    },
                    "type": {
                        "type": "string",
                        "description": "Attribute type",
                        "enum": ["select", "text"],
                        "default": "select",
                    },
                    "order_by": {
                        "type": "string",
                        "description": "Default sort order",
                        "enum": ["menu_order", "name", "name_num", "id"],
                        "default": "menu_order",
                    },
                    "has_archives": {
                        "type": "boolean",
                        "description": "Enable archives for this attribute",
                        "default": False,
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        # === PRODUCT VARIATIONS ===
        {
            "name": "list_product_variations",
            "method_name": "list_product_variations",
            "description": "List all variations of a variable product. Returns pricing, stock, and attribute combinations for each variation.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Variable product ID",
                        "minimum": 1,
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Number of variations per page (1-100)",
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
                },
                "required": ["product_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_product_variation",
            "method_name": "create_product_variation",
            "description": "Create a new variation for a variable product. Defines a specific combination of attributes with its own pricing and inventory.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Parent variable product ID",
                        "minimum": 1,
                    },
                    "attributes": {
                        "type": "array",
                        "description": 'Attribute combinations for this variation (e.g., [{"name": "Size", "option": "Large"}])',
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "option": {"type": "string"},
                            },
                        },
                    },
                    "regular_price": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Variation regular price",
                    },
                    "sale_price": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Variation sale price",
                    },
                    "stock_quantity": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Stock quantity for this variation",
                    },
                    "stock_status": {
                        "type": "string",
                        "description": "Stock status",
                        "enum": ["instock", "outofstock", "onbackorder"],
                        "default": "instock",
                    },
                    "manage_stock": {
                        "type": "boolean",
                        "description": "Enable stock management for this variation",
                        "default": False,
                    },
                    "sku": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Stock Keeping Unit (SKU) for this variation",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Variation description",
                    },
                    "image": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Variation image (e.g., {"id": 123})',
                    },
                },
                "required": ["product_id", "attributes"],
            },
            "scope": "write",
        },
    ]


class ProductsHandler:
    """Handle WooCommerce product-related operations"""

    def __init__(self, client: WordPressClient):
        """
        Initialize products handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    # === PRODUCTS ===

    async def list_products(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str = "any",
        category: int | None = None,
        stock_status: str | None = None,
        search: str | None = None,
        search_terms: list[str] | None = None,
        include_content: bool = False,
    ) -> str:
        """
        List WooCommerce products.

        Args:
            per_page: Number of products per page (1-100)
            page: Page number
            status: Product status filter
            category: Filter by category ID
            stock_status: Filter by stock status (instock, outofstock, onbackorder)
            search: Search term to filter products
            search_terms: Multiple search terms for parallel search with deduplication
            include_content: Include description summary and word count in results

        Returns:
            JSON string with products list
        """
        try:
            # Build query parameters
            params = {"per_page": per_page, "page": page, "status": status}

            # Add optional filters
            if category is not None:
                params["category"] = category
            if stock_status:
                params["stock_status"] = stock_status

            # Multi-search: parallel API calls with deduplication
            if search_terms and len(search_terms) > 0:

                async def _search_single(term: str) -> list:
                    p = {**params, "search": term}
                    return await self.client.get("products", params=p, use_woocommerce=True)

                batches = await asyncio.gather(
                    *[_search_single(term) for term in search_terms], return_exceptions=True
                )
                seen_ids: set = set()
                products: list = []
                for batch in batches:
                    if isinstance(batch, Exception):
                        continue
                    for product in batch:
                        if product["id"] not in seen_ids:
                            seen_ids.add(product["id"])
                            products.append(product)
            else:
                if search:
                    params["search"] = search
                products = await self.client.get("products", params=params, use_woocommerce=True)

            # Format response
            def _format_product(p: dict) -> dict:
                item = {
                    "id": p["id"],
                    "name": p["name"],
                    "slug": p["slug"],
                    "type": p["type"],
                    "status": p["status"],
                    "price": p["price"],
                    "regular_price": p["regular_price"],
                    "sale_price": p.get("sale_price", ""),
                    "stock_status": p["stock_status"],
                    "stock_quantity": p.get("stock_quantity"),
                    "categories": [
                        {"id": cat["id"], "name": cat["name"]} for cat in p.get("categories", [])
                    ],
                    "images": [
                        {"id": img["id"], "src": img["src"], "alt": img.get("alt", "")}
                        for img in p.get("images", [])[:1]  # Just first image
                    ],
                    "permalink": p["permalink"],
                }
                if include_content:
                    desc_html = p.get("description", "")
                    item["content_summary"] = _strip_html(desc_html, 500)
                    item["word_count"] = _count_words(desc_html)
                return item

            result = {
                "total": len(products),
                "page": page,
                "per_page": per_page,
                "products": [_format_product(p) for p in products],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list products: {str(e)}"}, indent=2
            )

    async def get_product(self, product_id: int, fields: str | None = None) -> str:
        """
        Get detailed information about a specific product.

        Args:
            product_id: Product ID to retrieve
            fields: Comma-separated list of fields to return (e.g., 'id,name,price,status')

        Returns:
            JSON string with product data
        """
        try:
            product = await self.client.get(f"products/{product_id}", use_woocommerce=True)

            full_result = {
                "id": product["id"],
                "name": product["name"],
                "slug": product["slug"],
                "type": product["type"],
                "status": product["status"],
                "description": product.get("description", ""),
                "short_description": product.get("short_description", ""),
                "price": product["price"],
                "regular_price": product["regular_price"],
                "sale_price": product.get("sale_price", ""),
                "stock_status": product["stock_status"],
                "stock_quantity": product.get("stock_quantity"),
                "manage_stock": product.get("manage_stock", False),
                "categories": [
                    {"id": cat["id"], "name": cat["name"], "slug": cat["slug"]}
                    for cat in product.get("categories", [])
                ],
                "tags": [
                    {"id": tag["id"], "name": tag["name"], "slug": tag["slug"]}
                    for tag in product.get("tags", [])
                ],
                "images": [
                    {"id": img["id"], "src": img["src"], "alt": img.get("alt", "")}
                    for img in product.get("images", [])
                ],
                "permalink": product["permalink"],
                # Phase K.2.3: Include attributes for variable products
                "attributes": [
                    {
                        "id": attr.get("id"),
                        "name": attr.get("name"),
                        "slug": attr.get("slug"),
                        "position": attr.get("position"),
                        "visible": attr.get("visible"),
                        "variation": attr.get("variation"),
                        "options": attr.get("options", []),
                    }
                    for attr in product.get("attributes", [])
                ],
                "word_count": _count_words(product.get("description", "")),
            }

            # Filter to requested fields only
            if fields:
                requested = {f.strip().lower() for f in fields.split(",")}
                requested.add("id")  # Always include id
                result = {k: v for k, v in full_result.items() if k in requested}
            else:
                result = full_result

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get product {product_id}: {str(e)}"},
                indent=2,
            )

    async def create_product(
        self,
        name: str,
        type: str = "simple",
        regular_price: str | None = None,
        sale_price: str | None = None,
        description: str | None = None,
        short_description: str | None = None,
        status: str = "draft",
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        stock_quantity: int | None = None,
        manage_stock: bool = False,
        stock_status: str = "instock",
        attributes: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Create a new WooCommerce product.

        Args:
            name: Product name/title
            type: Product type (simple, grouped, external, variable)
            regular_price: Product regular price
            sale_price: Product sale price
            description: Product full description
            short_description: Product short description
            status: Product status
            categories: Category IDs to assign
            tags: Tag IDs to assign
            stock_quantity: Stock quantity
            manage_stock: Enable stock management
            stock_status: Stock status
            attributes: Product attributes for variable products

        Returns:
            JSON string with created product data
        """
        try:
            # Build product data
            data = {"name": name, "type": type, "status": status}

            # Phase K.2.2: Variable products have different stock handling
            # Stock comes from variations, not the parent product
            if type != "variable":
                data["stock_status"] = stock_status
                data["manage_stock"] = manage_stock
                if regular_price:
                    data["regular_price"] = regular_price
                if sale_price:
                    data["sale_price"] = sale_price
                if stock_quantity is not None and manage_stock:
                    data["stock_quantity"] = stock_quantity

            if description:
                data["description"] = description
            if short_description:
                data["short_description"] = short_description
            # Phase K.2.1: Use normalize_id_list for flexible format support
            if categories:
                normalized_cats = normalize_id_list(categories, "categories")
                if normalized_cats:
                    data["categories"] = normalized_cats
            if tags:
                normalized_tags = normalize_id_list(tags, "tags")
                if normalized_tags:
                    data["tags"] = normalized_tags
            # Phase K.2.1/K.2.2/K.2.3: Add attributes for variable products
            # WooCommerce requires proper attribute format:
            # - For global attributes: use "id" (integer) - this is preferred
            # - For custom attributes: use "name" (string)
            # - Never use both "id" and "name" together
            # - "options" must be an array of strings
            # - For variable products: "variation" must be true
            if attributes:
                processed_attrs = []
                for attr in attributes:
                    if isinstance(attr, dict):
                        attr_clean = {}
                        # Use id for global attributes, name for custom
                        if "id" in attr:
                            attr_clean["id"] = int(attr["id"])
                        elif "name" in attr:
                            attr_clean["name"] = str(attr["name"])
                        else:
                            continue  # Skip invalid attributes

                        # Ensure options is a list of strings
                        if "options" in attr:
                            opts = attr["options"]
                            if isinstance(opts, list):
                                attr_clean["options"] = [str(o) for o in opts]
                            elif isinstance(opts, str):
                                attr_clean["options"] = [opts]

                        # For variable products, always set variation=true
                        if type == "variable":
                            attr_clean["variation"] = True
                            attr_clean["visible"] = True
                        else:
                            if "variation" in attr:
                                attr_clean["variation"] = bool(attr["variation"])
                            if "visible" in attr:
                                attr_clean["visible"] = bool(attr["visible"])

                        processed_attrs.append(attr_clean)
                    else:
                        # String attribute name - create as custom attribute
                        processed_attrs.append(
                            {
                                "name": str(attr),
                                "variation": type == "variable",
                                "visible": True,
                            }
                        )

                if processed_attrs:
                    data["attributes"] = processed_attrs

            product = await self.client.post("products", json_data=data, use_woocommerce=True)

            # Phase K.2.4: Two-step approach for variable products
            # WooCommerce sometimes converts variable to simple on creation
            # If this happens, immediately update to set type=variable
            if type == "variable" and product["type"] != "variable":
                # Try to update the product type to variable
                update_data = {"type": "variable"}
                try:
                    product = await self.client.put(
                        f"products/{product['id']}", json_data=update_data, use_woocommerce=True
                    )
                except Exception:
                    pass  # If update fails, continue with original product

            result = {
                "id": product["id"],
                "name": product["name"],
                "type": product["type"],
                "status": product["status"],
                "price": product.get("price", ""),
                "permalink": product["permalink"],
                "message": f"Product '{name}' created successfully with ID {product['id']}",
            }

            # Phase K.2.2: Include attributes in response for variable products
            if type == "variable":
                result["attributes"] = product.get("attributes", [])
                # Warn if type still couldn't be set to variable
                if product["type"] != "variable":
                    result["warning"] = (
                        f"Product was created as '{product['type']}' instead of 'variable'. "
                        "This may happen if attributes are missing or have invalid format. "
                        "Ensure attributes have 'id' (global attribute ID) and 'options' array."
                    )

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create product: {str(e)}"}, indent=2
            )

    async def update_product(
        self,
        product_id: int,
        name: str | None = None,
        slug: str | None = None,
        regular_price: str | None = None,
        sale_price: str | None = None,
        description: str | None = None,
        short_description: str | None = None,
        status: str | None = None,
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        stock_quantity: int | None = None,
        stock_status: str | None = None,
        featured: bool | None = None,
        weight: str | None = None,
    ) -> str:
        """
        Update an existing WooCommerce product.

        Args:
            product_id: Product ID to update
            name: Product name
            slug: Product slug (SEO-friendly URL path)
            regular_price: Product regular price
            sale_price: Product sale price
            description: Product description
            short_description: Product short description
            status: Product status
            categories: Category IDs to assign
            tags: Tag IDs to assign
            stock_quantity: Stock quantity
            stock_status: Stock status
            featured: Featured product flag
            weight: Product weight

        Returns:
            JSON string with updated product data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if name is not None:
                data["name"] = name
            if slug is not None:
                data["slug"] = slug
            if regular_price is not None:
                data["regular_price"] = regular_price
            if sale_price is not None:
                data["sale_price"] = sale_price
            if description is not None:
                data["description"] = description
            if short_description is not None:
                data["short_description"] = short_description
            if status is not None:
                data["status"] = status
            # Phase K.2.1: Use normalize_id_list for flexible format support
            if categories is not None:
                normalized_cats = normalize_id_list(categories, "categories")
                if normalized_cats:
                    data["categories"] = normalized_cats
            if tags is not None:
                normalized_tags = normalize_id_list(tags, "tags")
                if normalized_tags:
                    data["tags"] = normalized_tags
            if stock_quantity is not None:
                data["stock_quantity"] = stock_quantity
            if stock_status is not None:
                data["stock_status"] = stock_status
            if featured is not None:
                data["featured"] = featured
            if weight is not None:
                data["weight"] = weight

            product = await self.client.put(
                f"products/{product_id}", json_data=data, use_woocommerce=True
            )

            result = {
                "id": product["id"],
                "name": product["name"],
                "slug": product.get("slug", ""),
                "status": product["status"],
                "price": product.get("price", ""),
                "permalink": product.get("permalink", ""),
                "message": f"Product {product_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update product {product_id}: {str(e)}"},
                indent=2,
            )

    async def delete_product(self, product_id: int, force: bool = False) -> str:
        """
        Delete or trash a WooCommerce product.

        Args:
            product_id: Product ID to delete
            force: Permanently delete (True) or move to trash (False)

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(
                f"products/{product_id}", params=params, use_woocommerce=True
            )

            message = f"Product {product_id} {'permanently deleted' if force else 'moved to trash'}"
            return json.dumps({"success": True, "message": message, "result": result}, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete product {product_id}: {str(e)}"},
                indent=2,
            )

    # === PRODUCT CATEGORIES ===

    async def list_product_categories(
        self, per_page: int = 10, page: int = 1, hide_empty: bool = False
    ) -> str:
        """
        List WooCommerce product categories.

        Args:
            per_page: Number of categories per page (1-100)
            page: Page number
            hide_empty: Hide categories with no products

        Returns:
            JSON string with categories list
        """
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",
            }

            categories = await self.client.get(
                "products/categories", params=params, use_woocommerce=True
            )

            result = {
                "total": len(categories),
                "page": page,
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
                {"error": str(e), "message": f"Failed to list product categories: {str(e)}"},
                indent=2,
            )

    async def create_product_category(
        self, name: str, description: str | None = None, parent: int | None = None
    ) -> str:
        """
        Create a new WooCommerce product category.

        Args:
            name: Category name
            description: Category description
            parent: Parent category ID for hierarchical structure

        Returns:
            JSON string with created category data
        """
        try:
            data = {"name": name}
            if description:
                data["description"] = description
            if parent:
                data["parent"] = parent

            category = await self.client.post(
                "products/categories", json_data=data, use_woocommerce=True
            )

            result = {
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "message": f"Product category '{name}' created successfully with ID {category['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create product category: {str(e)}"},
                indent=2,
            )

    # === PRODUCT TAGS ===

    async def list_product_tags(
        self, per_page: int = 10, page: int = 1, hide_empty: bool = False
    ) -> str:
        """
        List WooCommerce product tags.

        Args:
            per_page: Number of tags per page (1-100)
            page: Page number
            hide_empty: Hide tags with no products

        Returns:
            JSON string with tags list
        """
        try:
            params = {
                "per_page": per_page,
                "page": page,
                "hide_empty": "true" if hide_empty else "false",
            }

            tags = await self.client.get("products/tags", params=params, use_woocommerce=True)

            result = {
                "total": len(tags),
                "page": page,
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
                {"error": str(e), "message": f"Failed to list product tags: {str(e)}"}, indent=2
            )

    # === PRODUCT ATTRIBUTES ===

    async def list_product_attributes(self) -> str:
        """
        List all global product attributes.

        Returns:
            JSON string with attributes list
        """
        try:
            attributes = await self.client.get("products/attributes", use_woocommerce=True)

            result = {
                "total": len(attributes),
                "attributes": [
                    {
                        "id": attr["id"],
                        "name": attr["name"],
                        "slug": attr["slug"],
                        "type": attr.get("type", "select"),
                        "order_by": attr.get("order_by", "menu_order"),
                        "has_archives": attr.get("has_archives", False),
                    }
                    for attr in attributes
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list product attributes: {str(e)}"},
                indent=2,
            )

    async def create_product_attribute(
        self,
        name: str,
        slug: str | None = None,
        type: str = "select",
        order_by: str = "menu_order",
        has_archives: bool = False,
    ) -> str:
        """
        Create a new global product attribute.

        Args:
            name: Attribute name (e.g., 'Size', 'Color')
            slug: Attribute slug (auto-generated if not provided)
            type: Attribute type (select or text)
            order_by: Default sort order
            has_archives: Enable archives for this attribute

        Returns:
            JSON string with created attribute data
        """
        try:
            data = {"name": name, "type": type, "order_by": order_by, "has_archives": has_archives}
            if slug:
                data["slug"] = slug

            attribute = await self.client.post(
                "products/attributes", json_data=data, use_woocommerce=True
            )

            result = {
                "id": attribute["id"],
                "name": attribute["name"],
                "slug": attribute["slug"],
                "message": f"Product attribute '{name}' created successfully with ID {attribute['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create product attribute: {str(e)}"},
                indent=2,
            )

    # === PRODUCT VARIATIONS ===

    async def list_product_variations(
        self, product_id: int, per_page: int = 10, page: int = 1
    ) -> str:
        """
        List variations of a variable product.

        Args:
            product_id: Variable product ID
            per_page: Number of variations per page (1-100)
            page: Page number

        Returns:
            JSON string with variations list
        """
        try:
            params = {"per_page": per_page, "page": page}

            variations = await self.client.get(
                f"products/{product_id}/variations", params=params, use_woocommerce=True
            )

            result = {
                "product_id": product_id,
                "total": len(variations),
                "page": page,
                "variations": [
                    {
                        "id": var["id"],
                        "sku": var.get("sku", ""),
                        "regular_price": var.get("regular_price", ""),
                        "sale_price": var.get("sale_price", ""),
                        "stock_status": var.get("stock_status", "instock"),
                        "stock_quantity": var.get("stock_quantity"),
                        "attributes": var.get("attributes", []),
                        "image": var.get("image"),
                        "permalink": var.get("permalink"),
                    }
                    for var in variations
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list product variations: {str(e)}"},
                indent=2,
            )

    async def create_product_variation(
        self,
        product_id: int,
        attributes: list[dict[str, Any]],
        regular_price: str | None = None,
        sale_price: str | None = None,
        stock_quantity: int | None = None,
        stock_status: str = "instock",
        manage_stock: bool = False,
        sku: str | None = None,
        description: str | None = None,
        image: dict[str, int] | None = None,
    ) -> str:
        """
        Create a new variation for a variable product.

        Args:
            product_id: Parent variable product ID
            attributes: Attribute combinations (e.g., [{"name": "Size", "option": "Large"}])
            regular_price: Variation regular price
            sale_price: Variation sale price
            stock_quantity: Stock quantity
            stock_status: Stock status
            manage_stock: Enable stock management
            sku: Stock Keeping Unit
            description: Variation description
            image: Variation image (e.g., {"id": 123})

        Returns:
            JSON string with created variation data
        """
        try:
            # Phase K.2.2: Normalize attributes for variations
            # Ensure attributes have proper format for WooCommerce API
            normalized_attrs = []
            if attributes:
                for attr in attributes:
                    if isinstance(attr, dict):
                        # Ensure both name and option are strings and trimmed
                        attr_item = {}
                        if "id" in attr:
                            attr_item["id"] = int(attr["id"])
                        if "name" in attr:
                            attr_item["name"] = str(attr["name"]).strip()
                        if "option" in attr:
                            attr_item["option"] = str(attr["option"]).strip()
                        if attr_item:
                            normalized_attrs.append(attr_item)

            data = {
                "attributes": normalized_attrs,
                "stock_status": stock_status,
                "manage_stock": manage_stock,
            }

            # Add optional fields
            if regular_price:
                data["regular_price"] = regular_price
            if sale_price:
                data["sale_price"] = sale_price
            if stock_quantity is not None:
                data["stock_quantity"] = stock_quantity
            if sku:
                data["sku"] = sku
            if description:
                data["description"] = description
            if image:
                data["image"] = image

            variation = await self.client.post(
                f"products/{product_id}/variations", json_data=data, use_woocommerce=True
            )

            result = {
                "variation_id": variation["id"],
                "product_id": product_id,
                "attributes": variation["attributes"],
                "regular_price": variation.get("regular_price"),
                "sale_price": variation.get("sale_price"),
                "message": f"Product variation created successfully with ID {variation['id']}",
            }

            # Phase K.2.2: Add warning if attributes were sent but came back empty
            if normalized_attrs and not variation.get("attributes"):
                result["warning"] = (
                    "Attributes were sent but not saved. This usually means: "
                    "1) The parent product doesn't have these attributes defined with 'variation: true', or "
                    "2) The attribute names/options don't match exactly (case-sensitive). "
                    "Make sure to first define attributes on the parent variable product."
                )

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to create product variation: {str(e)}",
                    "hint": "For variation attributes to work, ensure: 1) Parent product has type='variable', "
                    "2) Parent product has attributes with 'variation: true', "
                    "3) Attribute names and options match exactly",
                },
                indent=2,
            )
