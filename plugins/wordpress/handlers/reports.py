"""Reports Handler - manages WooCommerce reporting and analytics"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from plugins.wordpress.client import WordPressClient

DEFAULT_REVENUE_ORDER_STATUSES = ["processing", "completed"]
TOP_SELLERS_ORDER_PAGE_SIZE = 100


def _as_decimal(value: Any) -> Decimal:
    """Parse WooCommerce money strings without leaking raw order data."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _as_quantity(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _money_string(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    return format(normalized, "f")


def _date_start(value: str) -> str:
    if "T" in value:
        return value
    return f"{value}T00:00:00"


def _date_end(value: str) -> str:
    if "T" in value:
        return value
    return f"{value}T23:59:59"


def _period_date_range(
    period: str,
    date_min: str | None,
    date_max: str | None,
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    """Convert report periods into an order-query range for the fallback path."""
    current = now or datetime.now(UTC)
    today = current.date()

    if date_min:
        after = _date_start(date_min)
    elif period == "week":
        after = datetime.combine(today - timedelta(days=7), datetime.min.time()).isoformat()
    elif period == "last_month":
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        after = datetime.combine(last_month_end.replace(day=1), datetime.min.time()).isoformat()
    elif period == "year":
        after = datetime.combine(today.replace(month=1, day=1), datetime.min.time()).isoformat()
    else:
        after = datetime.combine(today.replace(day=1), datetime.min.time()).isoformat()

    if date_max:
        before = _date_end(date_max)
    elif period == "last_month":
        first_this_month = today.replace(day=1)
        before = datetime.combine(
            first_this_month - timedelta(days=1), datetime.max.time()
        ).isoformat()
    else:
        before = current.replace(microsecond=0).isoformat()

    return {"after": after, "before": before, "timezone": "UTC"}


def _clean_statuses(statuses: Iterable[str] | None) -> list[str]:
    cleaned = [str(status).strip() for status in (statuses or []) if str(status).strip()]
    return cleaned or list(DEFAULT_REVENUE_ORDER_STATUSES)


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
            "description": "Get top selling products report. Uses WooCommerce reports when available and falls back to privacy-safe order aggregation when reports are empty/unavailable. Returns aggregate product totals only, never customer PII.",
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
                    "statuses": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "string",
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
                            {"type": "null"},
                        ],
                        "description": "Order statuses to check for the privacy-safe fallback. Defaults to processing + completed.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of products to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "fallback_max_pages": {
                        "type": "integer",
                        "description": "Maximum WooCommerce order pages to scan per status when using the fallback",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
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
        self,
        period: str = "week",
        date_min: str | None = None,
        date_max: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 10,
        fallback_max_pages: int = 10,
    ) -> str:
        """
        Get top selling products report.

        Args:
            period: Report period (week, month, last_month, year)
            date_min: Start date for report (ISO 8601 format)
            date_max: End date for report (ISO 8601 format)
            statuses: Order statuses for the privacy-safe fallback
            limit: Maximum products to return
            fallback_max_pages: Maximum order pages to scan per status

        Returns:
            JSON string with top sellers data
        """
        limit = max(1, min(int(limit or 10), 100))
        fallback_max_pages = max(1, min(int(fallback_max_pages or 10), 20))
        fallback_statuses = _clean_statuses(statuses)
        date_range = _period_date_range(period, date_min, date_max)
        report_state: dict[str, Any] = {"status": "not_attempted"}

        try:
            params = {"period": period}
            if date_min:
                params["date_min"] = date_min
            if date_max:
                params["date_max"] = date_max

            try:
                top_sellers = await self.client.get(
                    "reports/top_sellers", params=params, use_woocommerce=True
                )
                if isinstance(top_sellers, list) and top_sellers:
                    formatted = [
                        {
                            "product_id": item.get("product_id"),
                            "variation_id": item.get("variation_id"),
                            "title": item.get("title") or item.get("name") or "",
                            "quantity": item.get("quantity", 0),
                        }
                        for item in top_sellers[:limit]
                    ]
                    result = {
                        "period": period,
                        "source": "reports/top_sellers",
                        "privacy": "aggregate_no_pii",
                        "date_range": date_range,
                        "total_products": len(top_sellers),
                        "top_sellers": formatted,
                        "diagnostic": {
                            "reports_endpoint": "non_empty",
                            "fallback_used": False,
                        },
                    }
                    return json.dumps(result, indent=2)

                report_state = {
                    "status": "empty" if isinstance(top_sellers, list) else "unexpected_response",
                    "response_type": type(top_sellers).__name__,
                }
            except Exception as report_error:  # noqa: BLE001 - fallback is the important path
                report_state = {
                    "status": "unavailable",
                    "message": str(report_error),
                }

            result = await self._get_top_sellers_from_orders(
                period=period,
                date_range=date_range,
                statuses=fallback_statuses,
                limit=limit,
                max_pages=fallback_max_pages,
                report_state=report_state,
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get top sellers: {str(e)}"}, indent=2
            )

    async def _get_top_sellers_from_orders(
        self,
        *,
        period: str,
        date_range: dict[str, str],
        statuses: list[str],
        limit: int,
        max_pages: int,
        report_state: dict[str, Any],
    ) -> dict[str, Any]:
        orders: list[dict[str, Any]] = []
        order_errors: list[dict[str, str]] = []
        pages_checked = 0

        for status in statuses:
            for page in range(1, max_pages + 1):
                params: dict[str, Any] = {
                    "per_page": TOP_SELLERS_ORDER_PAGE_SIZE,
                    "page": page,
                    "status": status,
                    "after": date_range["after"],
                    "before": date_range["before"],
                }
                try:
                    batch = await self.client.get("orders", params=params, use_woocommerce=True)
                except Exception as exc:  # noqa: BLE001 - diagnostics should not leak order data
                    order_errors.append({"status": status, "message": str(exc)})
                    break

                pages_checked += 1
                if not isinstance(batch, list) or not batch:
                    break

                orders.extend(item for item in batch if isinstance(item, dict))
                if len(batch) < TOP_SELLERS_ORDER_PAGE_SIZE:
                    break

        aggregate = self._aggregate_order_line_items(orders)
        products = sorted(
            aggregate.values(),
            key=lambda item: (-item["quantity"], -_as_decimal(item["revenue"]), item["title"]),
        )
        total_products = len(products)
        top_sellers = products[:limit]

        orders_endpoint = "ok"
        if order_errors and not orders:
            orders_endpoint = "error"
        elif order_errors:
            orders_endpoint = "partial_error"

        warnings = []
        if not top_sellers:
            warnings.append(
                "No revenue-bearing order line items were found in the checked range/statuses."
            )
        if order_errors:
            warnings.append("Some order fallback queries failed; see diagnostic.order_errors.")

        return {
            "period": period,
            "source": "orders_fallback",
            "privacy": "aggregate_no_pii",
            "date_range": date_range,
            "statuses_checked": statuses,
            "total_products": total_products,
            "top_sellers": top_sellers,
            "diagnostic": {
                "reports_endpoint": report_state,
                "orders_endpoint": orders_endpoint,
                "orders_checked": len(orders),
                "order_pages_checked": pages_checked,
                "line_items_checked": sum(len(order.get("line_items", [])) for order in orders),
                "fallback_max_pages_per_status": max_pages,
                "fallback_used": True,
                "warnings": warnings,
                "order_errors": order_errors[:5],
            },
        }

    def _aggregate_order_line_items(
        self, orders: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = {}

        for order in orders:
            currency = order.get("currency") or ""
            for item in order.get("line_items", []):
                if not isinstance(item, dict):
                    continue

                product_id = item.get("product_id")
                variation_id = item.get("variation_id") or None
                title = str(item.get("name") or "").strip()
                sku = str(item.get("sku") or "").strip()
                if not product_id and not title:
                    continue

                key = f"{product_id or 'unknown'}:{variation_id or 0}:{title.lower()}"
                quantity = _as_quantity(item.get("quantity"))
                revenue = _as_decimal(item.get("total", item.get("subtotal")))
                if key not in aggregate:
                    aggregate[key] = {
                        "product_id": product_id,
                        "variation_id": variation_id,
                        "title": title,
                        "sku": sku,
                        "quantity": 0.0,
                        "revenue": "0.00",
                        "currency": currency,
                    }

                aggregate[key]["quantity"] += quantity
                aggregate[key]["revenue"] = _money_string(
                    _as_decimal(aggregate[key]["revenue"]) + revenue
                )
                if not aggregate[key]["sku"] and sku:
                    aggregate[key]["sku"] = sku
                if not aggregate[key]["currency"] and currency:
                    aggregate[key]["currency"] = currency

        for item in aggregate.values():
            quantity = item["quantity"]
            item["quantity"] = int(quantity) if float(quantity).is_integer() else quantity

        return aggregate

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
