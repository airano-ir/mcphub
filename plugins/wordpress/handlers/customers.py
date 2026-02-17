"""Customers Handler - manages WooCommerce customers"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_customers",
            "method_name": "list_customers",
            "description": "List WooCommerce customers. Returns paginated customer list with email, orders count, and total spent.",
            "schema": {
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of customers per page (1-100)",
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
                        "description": "Search by name or email",
                    },
                    "email": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter by specific email address",
                    },
                    "role": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter by role (customer, subscriber, etc.)",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_customer",
            "method_name": "get_customer",
            "description": "Get detailed information about a specific WooCommerce customer. Returns customer details, billing, shipping, and order history.",
            "schema": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "Customer ID to retrieve",
                        "minimum": 1,
                    }
                },
                "required": ["customer_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_customer",
            "method_name": "create_customer",
            "description": "Create a new WooCommerce customer. Requires email, optionally includes name, username, password, billing, and shipping address.",
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Customer email address (required)",
                        "minLength": 1,
                    },
                    "first_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Customer first name",
                    },
                    "last_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Customer last name",
                    },
                    "username": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Username (generated from email if not provided)",
                    },
                    "password": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Password (auto-generated if not provided)",
                    },
                    "billing": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Billing address object",
                    },
                    "shipping": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Shipping address object",
                    },
                },
                "required": ["email"],
            },
            "scope": "write",
        },
        {
            "name": "update_customer",
            "method_name": "update_customer",
            "description": "Update an existing WooCommerce customer. Can update name, email, billing, shipping, and other customer fields.",
            "schema": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "Customer ID to update",
                        "minimum": 1,
                    },
                    "first_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Customer first name",
                    },
                    "last_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Customer last name",
                    },
                    "email": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Customer email address",
                    },
                    "billing": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Billing address object",
                    },
                    "shipping": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Shipping address object",
                    },
                },
                "required": ["customer_id"],
            },
            "scope": "write",
        },
    ]

class CustomersHandler:
    """Handle WooCommerce customer operations"""

    def __init__(self, client: WordPressClient):
        """
        Initialize customers handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    async def list_customers(
        self,
        per_page: int = 10,
        page: int = 1,
        search: str | None = None,
        email: str | None = None,
        role: str | None = None,
    ) -> str:
        """
        List WooCommerce customers.

        Args:
            per_page: Number of customers per page (1-100)
            page: Page number
            search: Search by name or email
            email: Filter by specific email
            role: Filter by role (customer, subscriber, etc.)

        Returns:
            JSON string with customers list
        """
        try:
            # Build query parameters
            params = {"per_page": per_page, "page": page}

            # Add optional filters
            if search:
                params["search"] = search
            if email:
                params["email"] = email
            if role:
                params["role"] = role

            # Make request to WooCommerce API
            customers = await self.client.get("customers", params=params, use_woocommerce=True)

            # Format response
            result = {
                "total": len(customers),
                "page": page,
                "per_page": per_page,
                "customers": [
                    {
                        "id": customer["id"],
                        "email": customer["email"],
                        "first_name": customer.get("first_name", ""),
                        "last_name": customer.get("last_name", ""),
                        "username": customer.get("username", ""),
                        "role": customer.get("role", ""),
                        "date_created": customer.get("date_created", ""),
                        "orders_count": customer.get("orders_count", 0),
                        "total_spent": customer.get("total_spent", "0"),
                        "avatar_url": customer.get("avatar_url", ""),
                    }
                    for customer in customers
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list customers: {str(e)}"}, indent=2
            )

    async def get_customer(self, customer_id: int) -> str:
        """
        Get detailed information about a specific customer.

        Args:
            customer_id: Customer ID to retrieve

        Returns:
            JSON string with customer data
        """
        try:
            customer = await self.client.get(f"customers/{customer_id}", use_woocommerce=True)

            # Format detailed response
            result = {
                "id": customer["id"],
                "email": customer["email"],
                "username": customer.get("username", ""),
                "first_name": customer.get("first_name", ""),
                "last_name": customer.get("last_name", ""),
                "role": customer.get("role", ""),
                "date_created": customer.get("date_created", ""),
                "date_modified": customer.get("date_modified", ""),
                "orders_count": customer.get("orders_count", 0),
                "total_spent": customer.get("total_spent", "0"),
                "avatar_url": customer.get("avatar_url", ""),
                "billing": customer.get("billing", {}),
                "shipping": customer.get("shipping", {}),
                "is_paying_customer": customer.get("is_paying_customer", False),
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get customer {customer_id}: {str(e)}"},
                indent=2,
            )

    async def create_customer(
        self,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
        password: str | None = None,
        billing: dict | None = None,
        shipping: dict | None = None,
    ) -> str:
        """
        Create a new WooCommerce customer.

        Args:
            email: Customer email (required)
            first_name: First name
            last_name: Last name
            username: Username (generated from email if not provided)
            password: Password (auto-generated if not provided)
            billing: Billing address dictionary
            shipping: Shipping address dictionary

        Returns:
            JSON string with created customer data
        """
        try:
            # Build customer data
            data = {"email": email}

            if first_name:
                data["first_name"] = first_name
            if last_name:
                data["last_name"] = last_name
            if username:
                data["username"] = username
            if password:
                data["password"] = password
            if billing:
                data["billing"] = billing
            if shipping:
                data["shipping"] = shipping

            # Create customer via WooCommerce API
            customer = await self.client.post("customers", json_data=data, use_woocommerce=True)

            result = {
                "id": customer["id"],
                "email": customer["email"],
                "username": customer.get("username", ""),
                "first_name": customer.get("first_name", ""),
                "last_name": customer.get("last_name", ""),
                "message": f"Customer created successfully with ID {customer['id']}",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to create customer: {str(e)}"}, indent=2
            )

    async def update_customer(
        self,
        customer_id: int,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        billing: dict | None = None,
        shipping: dict | None = None,
    ) -> str:
        """
        Update an existing WooCommerce customer.

        Args:
            customer_id: Customer ID to update
            first_name: First name
            last_name: Last name
            email: Email address
            billing: Billing address dictionary
            shipping: Shipping address dictionary

        Returns:
            JSON string with updated customer data
        """
        try:
            # Build data dict with only provided values
            data = {}
            if first_name is not None:
                data["first_name"] = first_name
            if last_name is not None:
                data["last_name"] = last_name
            if email is not None:
                data["email"] = email
            if billing is not None:
                data["billing"] = billing
            if shipping is not None:
                data["shipping"] = shipping

            # Update customer via WooCommerce API
            customer = await self.client.put(
                f"customers/{customer_id}", json_data=data, use_woocommerce=True
            )

            result = {
                "id": customer["id"],
                "email": customer["email"],
                "first_name": customer.get("first_name", ""),
                "last_name": customer.get("last_name", ""),
                "message": f"Customer {customer_id} updated successfully",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update customer {customer_id}: {str(e)}"},
                indent=2,
            )
