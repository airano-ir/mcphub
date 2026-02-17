"""Coupons Handler - manages WooCommerce coupons"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_coupons",
            "method_name": "list_coupons",
            "description": "List WooCommerce coupons. Returns paginated coupon list with discount details and usage restrictions.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of coupons per page (1-100)",
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
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter coupons by code",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "create_coupon",
            "method_name": "create_coupon",
            "description": "Create a new WooCommerce coupon. Supports percentage and fixed discounts with usage limits and restrictions.",
            "schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Coupon code (e.g., 'SAVE20')",
                        "minLength": 1,
                    },
                    "amount": {
                        "type": "string",
                        "description": "Discount amount (e.g., '20' for 20% or $20)",
                    },
                    "discount_type": {
                        "type": "string",
                        "description": "Type of discount",
                        "enum": ["percent", "fixed_cart", "fixed_product"],
                        "default": "percent",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Coupon description (internal note)",
                    },
                    "date_expires": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Expiration date in ISO 8601 format (e.g., '2024-12-31T23:59:59')",
                    },
                    "minimum_amount": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Minimum order amount required to use coupon",
                    },
                    "maximum_amount": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Maximum order amount allowed to use coupon",
                    },
                    "individual_use": {
                        "type": "boolean",
                        "description": "If true, coupon cannot be combined with other coupons",
                        "default": False,
                    },
                    "product_ids": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Array of product IDs coupon applies to",
                    },
                    "excluded_product_ids": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Array of product IDs coupon does NOT apply to",
                    },
                    "usage_limit": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum number of times coupon can be used",
                    },
                    "usage_limit_per_user": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum number of times coupon can be used per user",
                    },
                    "limit_usage_to_x_items": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum number of items coupon applies to",
                    },
                    "free_shipping": {
                        "type": "boolean",
                        "description": "If true, grants free shipping",
                        "default": False,
                    },
                },
                "required": ["code", "amount"],
            },
            "scope": "write",
        },
        {
            "name": "update_coupon",
            "method_name": "update_coupon",
            "description": "Update an existing WooCommerce coupon. Can update discount amount, restrictions, and expiration.",
            "schema": {
                "type": "object",
                "properties": {
                    "coupon_id": {
                        "type": "integer",
                        "description": "Coupon ID to update",
                        "minimum": 1,
                    },
                    "code": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Coupon code (e.g., 'SAVE20')",
                    },
                    "discount_type": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Type of discount",
                        "enum": ["percent", "fixed_cart", "fixed_product"],
                    },
                    "amount": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Discount amount",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Coupon description (internal note)",
                    },
                    "date_expires": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Expiration date in ISO 8601 format",
                    },
                    "minimum_amount": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Minimum order amount",
                    },
                    "maximum_amount": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Maximum order amount",
                    },
                    "individual_use": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "If true, coupon cannot be combined with other coupons",
                    },
                    "product_ids": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Array of product IDs coupon applies to",
                    },
                    "excluded_product_ids": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "Array of product IDs coupon does NOT apply to",
                    },
                    "usage_limit": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum number of uses",
                    },
                    "usage_limit_per_user": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum uses per user",
                    },
                    "limit_usage_to_x_items": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum number of items coupon applies to",
                    },
                    "free_shipping": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "If true, grants free shipping",
                    },
                },
                "required": ["coupon_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_coupon",
            "method_name": "delete_coupon",
            "description": "Delete a WooCommerce coupon. Can force delete or move to trash.",
            "schema": {
                "type": "object",
                "properties": {
                    "coupon_id": {
                        "type": "integer",
                        "description": "Coupon ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force permanent delete (bypass trash)",
                        "default": False,
                    },
                },
                "required": ["coupon_id"],
            },
            "scope": "write",
        },
    ]


class CouponsHandler:
    """Handle coupon-related operations for WooCommerce"""

    def __init__(self, client: WordPressClient):
        """
        Initialize coupons handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    async def list_coupons(
        self, per_page: int = 10, page: int = 1, search: str | None = None
    ) -> str:
        """
        List WooCommerce coupons.

        Args:
            per_page: Number of coupons per page (1-100)
            page: Page number
            search: Search term to filter coupons by code

        Returns:
            JSON string with coupons list
        """
        try:
            params = {"per_page": per_page, "page": page}
            if search:
                params["search"] = search

            coupons = await self.client.get("coupons", params=params, use_woocommerce=True)

            result = {
                "total": len(coupons),
                "page": page,
                "per_page": per_page,
                "coupons": [
                    {
                        "id": coupon["id"],
                        "code": coupon["code"],
                        "discount_type": coupon["discount_type"],
                        "amount": coupon["amount"],
                        "description": coupon.get("description", ""),
                        "date_expires": coupon.get("date_expires"),
                        "usage_count": coupon.get("usage_count", 0),
                        "usage_limit": coupon.get("usage_limit"),
                        "individual_use": coupon.get("individual_use", False),
                        "free_shipping": coupon.get("free_shipping", False),
                        "minimum_amount": coupon.get("minimum_amount", "0"),
                        "maximum_amount": coupon.get("maximum_amount", "0"),
                    }
                    for coupon in coupons
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list coupons: {str(e)}"}, indent=2
            )

    async def create_coupon(
        self,
        code: str,
        amount: str,
        discount_type: str = "percent",
        description: str | None = None,
        date_expires: str | None = None,
        minimum_amount: str | None = None,
        maximum_amount: str | None = None,
        individual_use: bool = False,
        product_ids: list[int] | None = None,
        excluded_product_ids: list[int] | None = None,
        usage_limit: int | None = None,
        usage_limit_per_user: int | None = None,
        limit_usage_to_x_items: int | None = None,
        free_shipping: bool = False,
    ) -> str:
        """
        Create a new WooCommerce coupon.

        Args:
            code: Coupon code (e.g., 'SAVE20')
            amount: Discount amount (e.g., '20' for 20% or $20)
            discount_type: Type of discount (percent, fixed_cart, fixed_product)
            description: Coupon description (internal note)
            date_expires: Expiration date in ISO 8601 format
            minimum_amount: Minimum order amount required
            maximum_amount: Maximum order amount allowed
            individual_use: If true, coupon cannot be combined with others
            product_ids: Product IDs coupon applies to
            excluded_product_ids: Product IDs coupon does NOT apply to
            usage_limit: Maximum number of times coupon can be used
            usage_limit_per_user: Maximum uses per user
            limit_usage_to_x_items: Maximum number of items coupon applies to
            free_shipping: If true, grants free shipping

        Returns:
            JSON string with created coupon data
        """
        try:
            data = {
                "code": code,
                "discount_type": discount_type,
                "amount": amount,
                "individual_use": individual_use,
                "free_shipping": free_shipping,
            }

            # Add optional fields
            if description:
                data["description"] = description
            if date_expires:
                data["date_expires"] = date_expires
            if minimum_amount:
                data["minimum_amount"] = minimum_amount
            if maximum_amount:
                data["maximum_amount"] = maximum_amount
            if product_ids:
                data["product_ids"] = product_ids
            if excluded_product_ids:
                data["excluded_product_ids"] = excluded_product_ids
            if usage_limit:
                data["usage_limit"] = usage_limit
            if usage_limit_per_user:
                data["usage_limit_per_user"] = usage_limit_per_user
            if limit_usage_to_x_items:
                data["limit_usage_to_x_items"] = limit_usage_to_x_items

            coupon = await self.client.post("coupons", json_data=data, use_woocommerce=True)

            result = {
                "id": coupon["id"],
                "code": coupon["code"],
                "discount_type": coupon["discount_type"],
                "amount": coupon["amount"],
                "date_expires": coupon.get("date_expires"),
                "message": f"Coupon '{code}' created successfully with ID {coupon['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create coupon: {str(e)}"}, indent=2
            )

    async def update_coupon(
        self,
        coupon_id: int,
        code: str | None = None,
        discount_type: str | None = None,
        amount: str | None = None,
        description: str | None = None,
        date_expires: str | None = None,
        minimum_amount: str | None = None,
        maximum_amount: str | None = None,
        individual_use: bool | None = None,
        product_ids: list[int] | None = None,
        excluded_product_ids: list[int] | None = None,
        usage_limit: int | None = None,
        usage_limit_per_user: int | None = None,
        limit_usage_to_x_items: int | None = None,
        free_shipping: bool | None = None,
    ) -> str:
        """
        Update an existing WooCommerce coupon.

        Args:
            coupon_id: Coupon ID to update
            code: Coupon code
            discount_type: Type of discount
            amount: Discount amount
            description: Coupon description
            date_expires: Expiration date in ISO 8601 format
            minimum_amount: Minimum order amount
            maximum_amount: Maximum order amount
            individual_use: If true, coupon cannot be combined with others
            product_ids: Product IDs coupon applies to
            excluded_product_ids: Product IDs coupon does NOT apply to
            usage_limit: Maximum number of uses
            usage_limit_per_user: Maximum uses per user
            limit_usage_to_x_items: Maximum number of items coupon applies to
            free_shipping: If true, grants free shipping

        Returns:
            JSON string with updated coupon data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if code is not None:
                data["code"] = code
            if discount_type is not None:
                data["discount_type"] = discount_type
            if amount is not None:
                data["amount"] = amount
            if description is not None:
                data["description"] = description
            if date_expires is not None:
                data["date_expires"] = date_expires
            if minimum_amount is not None:
                data["minimum_amount"] = minimum_amount
            if maximum_amount is not None:
                data["maximum_amount"] = maximum_amount
            if individual_use is not None:
                data["individual_use"] = individual_use
            if product_ids is not None:
                data["product_ids"] = product_ids
            if excluded_product_ids is not None:
                data["excluded_product_ids"] = excluded_product_ids
            if usage_limit is not None:
                data["usage_limit"] = usage_limit
            if usage_limit_per_user is not None:
                data["usage_limit_per_user"] = usage_limit_per_user
            if limit_usage_to_x_items is not None:
                data["limit_usage_to_x_items"] = limit_usage_to_x_items
            if free_shipping is not None:
                data["free_shipping"] = free_shipping

            if not data:
                raise Exception("No update data provided")

            coupon = await self.client.put(
                f"coupons/{coupon_id}", json_data=data, use_woocommerce=True
            )

            result = {
                "id": coupon["id"],
                "code": coupon["code"],
                "discount_type": coupon["discount_type"],
                "amount": coupon["amount"],
                "message": f"Coupon ID {coupon_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update coupon {coupon_id}: {str(e)}"},
                indent=2,
            )

    async def delete_coupon(self, coupon_id: int, force: bool = False) -> str:
        """
        Delete a WooCommerce coupon.

        Args:
            coupon_id: Coupon ID to delete
            force: Force permanent delete (True) or move to trash (False)

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(
                f"coupons/{coupon_id}", params=params, use_woocommerce=True
            )

            action = "permanently deleted" if force else "moved to trash"
            return json.dumps(
                {
                    "success": True,
                    "coupon_id": coupon_id,
                    "message": f"Coupon {action} successfully",
                    "result": result,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete coupon {coupon_id}: {str(e)}"},
                indent=2,
            )
