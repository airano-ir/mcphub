"""Reports Handler - manages WooCommerce reporting and analytics"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === WOOCOMMERCE REPORTS ===
        {
            "name": "get_sales_report",
            "method_name": "get_sales_report",
            "description": "Get WooCommerce sales report. Returns sales data with totals and date ranges. Note: WooCommerce v3 API has limited reporting capabilities.",
            "schema": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Report period (week, month, last_month, year)",
                        "enum": ["week", "month", "last_month", "year"],
                        "default": "week",
                    },
                    "date_min": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Start date for report (ISO 8601 format, e.g., '2024-01-01')",
                    },
                    "date_max": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "End date for report (ISO 8601 format, e.g., '2024-12-31')",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_top_sellers",
            "method_name": "get_top_sellers",
            "description": "Get top selling products report. Returns products with highest sales quantities.",
            "schema": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Report period (week, month, last_month, year)",
                        "enum": ["week", "month", "last_month", "year"],
                        "default": "week",
                    },
                    "date_min": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Start date for report (ISO 8601 format)",
                    },
                    "date_max": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "End date for report (ISO 8601 format)",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_customer_report",
            "method_name": "get_customer_report",
            "description": "Get customer statistics report. Returns customer count and spending data. Falls back to customer list if reports endpoint unavailable.",
            "schema": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Report period (week, month, last_month, year)",
                        "enum": ["week", "month", "last_month", "year"],
                        "default": "week",
                    },
                    "date_min": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Start date for report (ISO 8601 format)",
                    },
                    "date_max": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "End date for report (ISO 8601 format)",
                    },
                },
            },
            "scope": "read",
        },
    ]


class ReportsHandler:
    """Handle WooCommerce reporting operations"""

    def __init__(self, client: WordPressClient):
        """
        Initialize reports handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    # === WOOCOMMERCE REPORTS ===

    async def get_sales_report(
        self, period: str = "week", date_min: str | None = None, date_max: str | None = None
    ) -> str:
        """
        Get WooCommerce sales report.

        Args:
            period: Report period (week, month, last_month, year)
            date_min: Start date for report (ISO 8601 format, e.g., '2024-01-01')
            date_max: End date for report (ISO 8601 format, e.g., '2024-12-31')

        Returns:
            JSON string with sales report data

        Note:
            WooCommerce v3 API has limited reporting capabilities.
            For advanced analytics, use WooCommerce Analytics extension.
        """
        try:
            params = {"period": period}
            if date_min:
                params["date_min"] = date_min
            if date_max:
                params["date_max"] = date_max

            report_data = await self.client.get(
                "reports/sales", params=params, use_woocommerce=True
            )

            # Format the response based on what the API returns
            result = {
                "period": period,
                "sales_data": report_data if isinstance(report_data, list) else [report_data],
                "note": "WooCommerce v3 API has limited reporting. For advanced analytics, use WooCommerce Analytics extension.",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            error_msg = str(e)
            # Check if reports endpoint is not available
            if "404" in error_msg or "not found" in error_msg.lower():
                return json.dumps(
                    {
                        "error": "Sales reports endpoint not available",
                        "message": "WooCommerce v3 API has limited reporting capabilities. Consider using WooCommerce Analytics or custom queries.",
                        "details": error_msg,
                    },
                    indent=2,
                )
            return json.dumps(
                {"error": str(e), "message": f"Failed to get sales report: {str(e)}"}, indent=2
            )

    async def get_top_sellers(
        self, period: str = "week", date_min: str | None = None, date_max: str | None = None
    ) -> str:
        """
        Get top selling products report.

        Args:
            period: Report period (week, month, last_month, year)
            date_min: Start date for report (ISO 8601 format)
            date_max: End date for report (ISO 8601 format)

        Returns:
            JSON string with top sellers data
        """
        try:
            params = {"period": period}
            if date_min:
                params["date_min"] = date_min
            if date_max:
                params["date_max"] = date_max

            top_sellers = await self.client.get(
                "reports/top_sellers", params=params, use_woocommerce=True
            )

            result = {
                "period": period,
                "total_products": len(top_sellers) if isinstance(top_sellers, list) else 0,
                "top_sellers": [
                    {
                        "product_id": item.get("product_id"),
                        "title": item.get("title"),
                        "quantity": item.get("quantity", 0),
                    }
                    for item in (top_sellers if isinstance(top_sellers, list) else [])
                ],
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                return json.dumps(
                    {
                        "error": "Top sellers endpoint not available",
                        "message": "WooCommerce v3 API has limited reporting capabilities.",
                        "details": error_msg,
                    },
                    indent=2,
                )
            return json.dumps(
                {"error": str(e), "message": f"Failed to get top sellers: {str(e)}"}, indent=2
            )

    async def get_customer_report(
        self, period: str = "week", date_min: str | None = None, date_max: str | None = None
    ) -> str:
        """
        Get customer statistics report.

        Args:
            period: Report period (week, month, last_month, year)
            date_min: Start date for report (ISO 8601 format)
            date_max: End date for report (ISO 8601 format)

        Returns:
            JSON string with customer report data

        Note:
            Falls back to customer list endpoint if reports endpoint is unavailable.
        """
        try:
            params = {"period": period}
            if date_min:
                params["date_min"] = date_min
            if date_max:
                params["date_max"] = date_max

            try:
                customer_data = await self.client.get(
                    "reports/customers", params=params, use_woocommerce=True
                )

                result = {
                    "period": period,
                    "customer_data": (
                        customer_data if isinstance(customer_data, list) else [customer_data]
                    ),
                    "note": "Customer reporting may be limited in WooCommerce v3 API.",
                }

                return json.dumps(result, indent=2)
            except Exception as report_error:
                # Check if it's a 404 error - use fallback
                if "404" in str(report_error) or "not found" in str(report_error).lower():
                    return await self._get_customer_report_fallback()
                raise report_error

        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get customer report: {str(e)}"}, indent=2
            )

    async def _get_customer_report_fallback(self) -> str:
        """
        Fallback method when customer reports endpoint is not available.

        Uses the customers list endpoint to generate basic statistics.

        Returns:
            JSON string with basic customer statistics
        """
        try:
            # Use customers list to generate basic stats
            customers = await self.client.get(
                "customers", params={"per_page": 100}, use_woocommerce=True
            )

            # Calculate basic stats
            total_customers = len(customers) if isinstance(customers, list) else 0
            total_spent = (
                sum(float(c.get("total_spent", 0)) for c in customers)
                if isinstance(customers, list)
                else 0
            )
            avg_spent = total_spent / total_customers if total_customers > 0 else 0

            result = {
                "total_customers": total_customers,
                "total_spent": f"{total_spent:.2f}",
                "average_spent_per_customer": f"{avg_spent:.2f}",
                "note": "Generated from customer list (fallback method). For detailed analytics, use WooCommerce Analytics.",
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": "Customer report and fallback both unavailable",
                    "details": str(e),
                },
                indent=2,
            )
