"""Orders Handler - manages WooCommerce orders"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_orders",
            "method_name": "list_orders",
            "description": "List WooCommerce orders. Returns paginated order list with customer details, totals, and status.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of orders per page (1-100)",
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
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": [
                                    "any",
                                    "pending",
                                    "processing",
                                    "on-hold",
                                    "completed",
                                    "cancelled",
                                    "refunded",
                                    "failed",
                                    "trash",
                                ],
                            },
                            {"type": "null"},
                        ],
                        "description": "Filter by order status (optional)",
                    },
                    "customer": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Filter by customer ID",
                    },
                    "after": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter orders after this date (ISO 8601 format)",
                    },
                    "before": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter orders before this date (ISO 8601 format)",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_order",
            "method_name": "get_order",
            "description": "Get detailed information about a specific WooCommerce order. Returns full order details including line items, totals, billing, and shipping.",
            "schema": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to retrieve",
                        "minimum": 1,
                    }
                },
                "required": ["order_id"],
            },
            "scope": "read",
        },
        {
            "name": "update_order_status",
            "method_name": "update_order_status",
            "description": "Update WooCommerce order status. Change order status to pending, processing, completed, etc.",
            "schema": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to update",
                        "minimum": 1,
                    },
                    "status": {
                        "type": "string",
                        "description": "New order status",
                        "enum": [
                            "pending",
                            "processing",
                            "on-hold",
                            "completed",
                            "cancelled",
                            "refunded",
                            "failed",
                        ],
                    },
                },
                "required": ["order_id", "status"],
            },
            "scope": "write",
        },
        {
            "name": "create_order",
            "method_name": "create_order",
            "description": "Create a new WooCommerce order. Supports line items, billing, shipping, and payment method configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Customer ID (optional)",
                    },
                    "line_items": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product_id": {
                                            "type": "integer",
                                            "description": "Product ID",
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "Quantity",
                                            "minimum": 1,
                                        },
                                        "variation_id": {
                                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                                            "description": "Variation ID (for variable products)",
                                        },
                                    },
                                    "required": ["product_id", "quantity"],
                                },
                            },
                            {"type": "null"},
                        ],
                        "description": "Order line items with product IDs and quantities",
                    },
                    "billing": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Billing address object",
                    },
                    "shipping": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Shipping address object",
                    },
                    "payment_method": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Payment method ID (e.g., 'bacs', 'cod', 'paypal')",
                    },
                    "status": {
                        "type": "string",
                        "description": "Order status",
                        "enum": ["pending", "processing", "on-hold", "completed"],
                        "default": "pending",
                    },
                },
            },
            "scope": "write",
        },
        {
            "name": "delete_order",
            "method_name": "delete_order",
            "description": "Delete or trash a WooCommerce order. Can permanently delete or move to trash.",
            "schema": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to delete",
                        "minimum": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Permanently delete (true) or move to trash (false)",
                        "default": False,
                    },
                },
                "required": ["order_id"],
            },
            "scope": "write",
        },
    ]

class OrdersHandler:
    """Handle WooCommerce order-related operations"""

    def __init__(self, client: WordPressClient):
        """
        Initialize orders handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    async def list_orders(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str | None = None,
        customer: int | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> str:
        """
        List WooCommerce orders with filters.

        Args:
            per_page: Number of orders per page (1-100)
            page: Page number
            status: Filter by order status (any, pending, processing, on-hold, completed, cancelled, refunded, failed, trash)
            customer: Filter by customer ID
            after: Filter orders after this date (ISO 8601 format)
            before: Filter orders before this date (ISO 8601 format)

        Returns:
            JSON string with orders list
        """
        try:
            # Build query parameters
            params = {"per_page": per_page, "page": page}

            # Add optional filters
            if status:
                params["status"] = status
            if customer is not None:
                params["customer"] = customer
            if after:
                params["after"] = after
            if before:
                params["before"] = before

            # Make request to WooCommerce API
            orders = await self.client.get("orders", params=params, use_woocommerce=True)

            # Format response
            result = {
                "total": len(orders),
                "page": page,
                "per_page": per_page,
                "orders": [
                    {
                        "id": order["id"],
                        "number": order["number"],
                        "status": order["status"],
                        "date_created": order["date_created"],
                        "date_modified": order.get("date_modified", ""),
                        "total": order["total"],
                        "currency": order["currency"],
                        "customer_id": order["customer_id"],
                        "billing": {
                            "first_name": order["billing"].get("first_name", ""),
                            "last_name": order["billing"].get("last_name", ""),
                            "email": order["billing"].get("email", ""),
                        },
                        "line_items_count": len(order.get("line_items", [])),
                        "payment_method_title": order.get("payment_method_title", ""),
                        "transaction_id": order.get("transaction_id", ""),
                    }
                    for order in orders
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list orders: {str(e)}"}, indent=2
            )

    async def get_order(self, order_id: int) -> str:
        """
        Get detailed information about a specific order.

        Args:
            order_id: Order ID to retrieve

        Returns:
            JSON string with order data
        """
        try:
            order = await self.client.get(f"orders/{order_id}", use_woocommerce=True)

            # Format detailed response
            result = {
                "id": order["id"],
                "number": order["number"],
                "status": order["status"],
                "currency": order["currency"],
                "date_created": order["date_created"],
                "date_modified": order.get("date_modified", ""),
                "discount_total": order["discount_total"],
                "shipping_total": order["shipping_total"],
                "total": order["total"],
                "total_tax": order["total_tax"],
                "customer_id": order["customer_id"],
                "customer_note": order.get("customer_note", ""),
                "billing": order["billing"],
                "shipping": order["shipping"],
                "payment_method": order["payment_method"],
                "payment_method_title": order.get("payment_method_title", ""),
                "transaction_id": order.get("transaction_id", ""),
                "line_items": [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "product_id": item["product_id"],
                        "quantity": item["quantity"],
                        "subtotal": item["subtotal"],
                        "total": item["total"],
                        "sku": item.get("sku", ""),
                    }
                    for item in order.get("line_items", [])
                ],
                "shipping_lines": order.get("shipping_lines", []),
                "fee_lines": order.get("fee_lines", []),
                "coupon_lines": order.get("coupon_lines", []),
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get order {order_id}: {str(e)}"}, indent=2
            )

    async def update_order_status(self, order_id: int, status: str) -> str:
        """
        Update order status.

        Args:
            order_id: Order ID to update
            status: New status (pending, processing, on-hold, completed, cancelled, refunded, failed)

        Returns:
            JSON string with updated order data
        """
        try:
            data = {"status": status}

            order = await self.client.put(
                f"orders/{order_id}", json_data=data, use_woocommerce=True
            )

            result = {
                "id": order["id"],
                "number": order["number"],
                "status": order["status"],
                "message": f"Order #{order['number']} status updated to '{status}'",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update order {order_id} status: {str(e)}"},
                indent=2,
            )

    async def create_order(
        self,
        customer_id: int | None = None,
        line_items: list[dict] | None = None,
        billing: dict | None = None,
        shipping: dict | None = None,
        payment_method: str | None = None,
        status: str = "pending",
    ) -> str:
        """
        Create a new order.

        Args:
            customer_id: Customer ID (optional)
            line_items: List of line items [{"product_id": 123, "quantity": 1}]
            billing: Billing address dictionary
            shipping: Shipping address dictionary
            payment_method: Payment method ID (e.g., 'bacs', 'cod', 'paypal')
            status: Order status (default: pending)

        Returns:
            JSON string with created order data
        """
        try:
            data = {"status": status}

            if customer_id is not None:
                data["customer_id"] = customer_id
            if line_items:
                data["line_items"] = line_items
            if billing:
                data["billing"] = billing
            if shipping:
                data["shipping"] = shipping
            if payment_method:
                data["payment_method"] = payment_method

            order = await self.client.post("orders", json_data=data, use_woocommerce=True)

            result = {
                "id": order["id"],
                "number": order["number"],
                "status": order["status"],
                "total": order["total"],
                "currency": order["currency"],
                "message": f"Order #{order['number']} created successfully with ID {order['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create order: {str(e)}"}, indent=2
            )

    async def delete_order(self, order_id: int, force: bool = False) -> str:
        """
        Delete or trash an order.

        Args:
            order_id: Order ID to delete
            force: Permanently delete (True) or move to trash (False)

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"force": "true" if force else "false"}
            result = await self.client.delete(
                f"orders/{order_id}", params=params, use_woocommerce=True
            )

            message = f"Order {order_id} {'permanently deleted' if force else 'moved to trash'}"
            return json.dumps({"success": True, "message": message, "result": result}, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete order {order_id}: {str(e)}"},
                indent=2,
            )
