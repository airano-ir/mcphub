from __future__ import annotations

import json
from typing import Any

import pytest

from plugins.wordpress.handlers.reports import ReportsHandler


class FakeWooClient:
    def __init__(self, responses: list[Any]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def get(self, endpoint: str, params: dict | None = None, use_woocommerce: bool = False):
        self.calls.append(
            {
                "endpoint": endpoint,
                "params": params or {},
                "use_woocommerce": use_woocommerce,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _order_with_pii() -> dict[str, Any]:
    return {
        "id": 501,
        "number": "501",
        "status": "completed",
        "currency": "USD",
        "billing": {"email": "customer@example.com", "first_name": "Ada"},
        "transaction_id": "txn_secret",
        "line_items": [
            {
                "id": 1,
                "name": "Canvas Tote",
                "product_id": 10,
                "variation_id": 0,
                "quantity": 2,
                "total": "36.00",
                "sku": "BAG-10",
            },
            {
                "id": 2,
                "name": "Sticker Pack",
                "product_id": 11,
                "quantity": "3",
                "total": "9",
            },
        ],
    }


@pytest.mark.asyncio
async def test_top_sellers_uses_native_report_when_non_empty():
    client = FakeWooClient([[{"product_id": 7, "title": "Notebook", "quantity": 4}]])
    handler = ReportsHandler(client)

    raw = await handler.get_top_sellers(
        period="month",
        date_min="2026-06-01",
        date_max="2026-06-30",
    )
    out = json.loads(raw)

    assert out["source"] == "reports/top_sellers"
    assert out["privacy"] == "aggregate_no_pii"
    assert out["top_sellers"] == [
        {"product_id": 7, "variation_id": None, "title": "Notebook", "quantity": 4}
    ]
    assert [call["endpoint"] for call in client.calls] == ["reports/top_sellers"]


@pytest.mark.asyncio
async def test_top_sellers_falls_back_to_order_aggregation_when_report_empty():
    client = FakeWooClient([[], [_order_with_pii()], []])
    handler = ReportsHandler(client)

    raw = await handler.get_top_sellers(
        period="month",
        date_min="2026-06-01",
        date_max="2026-06-30",
        statuses=["processing", "completed"],
    )
    out = json.loads(raw)

    assert out["source"] == "orders_fallback"
    assert out["privacy"] == "aggregate_no_pii"
    assert out["diagnostic"]["reports_endpoint"]["status"] == "empty"
    assert out["diagnostic"]["orders_checked"] == 1
    assert out["total_products"] == 2
    assert out["top_sellers"][0]["product_id"] == 11
    assert out["top_sellers"][0]["quantity"] == 3
    assert out["top_sellers"][1]["product_id"] == 10
    assert out["top_sellers"][1]["revenue"] == "36.00"
    dumped = json.dumps(out)
    assert "customer@example.com" not in dumped
    assert "txn_secret" not in dumped


@pytest.mark.asyncio
async def test_top_sellers_falls_back_when_report_endpoint_unavailable():
    client = FakeWooClient([RuntimeError("404 not found"), [_order_with_pii()]])
    handler = ReportsHandler(client)

    raw = await handler.get_top_sellers(
        period="month",
        date_min="2026-06-01",
        date_max="2026-06-30",
        statuses=["completed"],
    )
    out = json.loads(raw)

    assert out["source"] == "orders_fallback"
    assert out["diagnostic"]["reports_endpoint"]["status"] == "unavailable"
    assert out["top_sellers"]


@pytest.mark.asyncio
async def test_top_sellers_empty_fallback_returns_diagnostic_not_bare_empty():
    client = FakeWooClient([[], []])
    handler = ReportsHandler(client)

    raw = await handler.get_top_sellers(
        period="month",
        date_min="2026-06-01",
        date_max="2026-06-30",
        statuses=["completed"],
    )
    out = json.loads(raw)

    assert out["source"] == "orders_fallback"
    assert out["total_products"] == 0
    assert out["top_sellers"] == []
    assert out["diagnostic"]["warnings"]
    assert out["date_range"] == {
        "after": "2026-06-01T00:00:00",
        "before": "2026-06-30T23:59:59",
        "timezone": "UTC",
    }
