from __future__ import annotations

import json
from typing import Any

import pytest

from plugins.wordpress.handlers.orders import OrdersHandler


class FakeOrdersClient:
    def __init__(self, orders: list[dict[str, Any]]):
        self.orders = orders
        self.calls: list[dict[str, Any]] = []

    async def get(self, endpoint: str, params: dict | None = None, use_woocommerce: bool = False):
        self.calls.append(
            {
                "endpoint": endpoint,
                "params": params or {},
                "use_woocommerce": use_woocommerce,
            }
        )
        return self.orders


def _order() -> dict[str, Any]:
    return {
        "id": 42,
        "number": "0042",
        "status": "processing",
        "date_created": "2026-06-10T12:00:00",
        "date_modified": "2026-06-10T12:05:00",
        "total": "52.00",
        "currency": "USD",
        "customer_id": 77,
        "customer_note": "Leave at side door",
        "billing": {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "phone": "555-0100",
            "address_1": "1 Main St",
        },
        "shipping": {"address_1": "1 Main St"},
        "payment_method_title": "Visa ending 4242",
        "transaction_id": "txn_123",
        "line_items": [
            {
                "product_id": 10,
                "variation_id": 0,
                "name": "Canvas Tote",
                "sku": "BAG-10",
                "quantity": 2,
                "subtotal": "40.00",
                "total": "36.00",
            }
        ],
    }


@pytest.mark.asyncio
async def test_list_orders_defaults_to_privacy_safe_summary():
    handler = OrdersHandler(FakeOrdersClient([_order()]))

    raw = await handler.list_orders(status="processing")
    out = json.loads(raw)
    order = out["orders"][0]

    assert out["privacy"] == "summary_no_pii"
    assert out["pii_included"] is False
    assert order["id"] == 42
    assert order["line_items_count"] == 1
    assert "billing" not in order
    assert "shipping" not in order
    assert "customer_id" not in order
    assert "payment_method_title" not in order
    assert "transaction_id" not in order
    assert "customer_note" not in json.dumps(out)
    assert "ada@example.com" not in json.dumps(out)


@pytest.mark.asyncio
async def test_list_orders_summary_can_include_safe_line_items_and_anonymize_ids():
    handler = OrdersHandler(FakeOrdersClient([_order()]))

    raw = await handler.list_orders(include_line_items=True, anonymize_ids=True)
    out = json.loads(raw)
    order = out["orders"][0]

    assert "id" not in order
    assert "number" not in order
    assert order["anonymized_ids"] is True
    assert order["line_items"] == [
        {
            "product_id": 10,
            "variation_id": 0,
            "name": "Canvas Tote",
            "sku": "BAG-10",
            "quantity": 2,
            "subtotal": "40.00",
            "total": "36.00",
        }
    ]
    assert "ada@example.com" not in json.dumps(out)
    assert "txn_123" not in json.dumps(out)


@pytest.mark.asyncio
async def test_list_orders_full_mode_remains_available_explicitly():
    handler = OrdersHandler(FakeOrdersClient([_order()]))

    raw = await handler.list_orders(summary=False)
    out = json.loads(raw)
    order = out["orders"][0]

    assert out["privacy"] == "full_order_details"
    assert out["pii_included"] is True
    assert order["billing"]["email"] == "ada@example.com"
    assert order["payment_method_title"] == "Visa ending 4242"
    assert order["transaction_id"] == "txn_123"
