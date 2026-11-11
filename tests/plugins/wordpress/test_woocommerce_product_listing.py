from __future__ import annotations

import json
from typing import Any

import pytest

from plugins.wordpress.handlers.products import ProductsHandler


class FakeProductsClient:
    def __init__(self, products: list[dict[str, Any]]):
        self.products = products
        self.calls: list[dict[str, Any]] = []

    async def get(self, endpoint: str, params: dict | None = None, use_woocommerce: bool = False):
        self.calls.append(
            {
                "endpoint": endpoint,
                "params": params or {},
                "use_woocommerce": use_woocommerce,
            }
        )
        return self.products


def _product() -> dict[str, Any]:
    return {
        "id": 10,
        "name": "Canvas Tote",
        "slug": "canvas-tote",
        "type": "simple",
        "status": "publish",
        "date_created": "2026-06-01T10:00:00",
        "date_modified": "2026-06-09T11:00:00",
        "featured": True,
        "total_sales": 12,
        "price": "18.00",
        "regular_price": "20.00",
        "sale_price": "18.00",
        "on_sale": True,
        "stock_status": "instock",
        "stock_quantity": 8,
        "categories": [{"id": 4, "name": "Bags", "slug": "bags"}],
        "tags": [{"id": 9, "name": "Summer", "slug": "summer"}],
        "images": [
            {
                "id": 90,
                "src": "https://example.com/tote.jpg",
                "alt": "Canvas tote",
                "name": "tote",
            },
            {"id": 91, "src": "https://example.com/tote-2.jpg"},
        ],
        "short_description": "<p>Lightweight <strong>daily</strong> tote.</p>",
        "description": "<p>Long catalog copy.</p>",
        "permalink": "https://example.com/product/canvas-tote/",
    }


@pytest.mark.asyncio
async def test_list_products_adds_editorial_filters_and_compact_fields():
    client = FakeProductsClient([_product()])
    handler = ProductsHandler(client)

    raw = await handler.list_products(
        status="publish",
        stock_status="instock",
        category=4,
        tag=9,
        orderby="modified",
        order="desc",
        after="2026-06-01T00:00:00",
        modified_after="2026-06-05T00:00:00",
        featured=True,
        on_sale=True,
        min_price="10",
        max_price="25",
    )
    out = json.loads(raw)
    params = client.calls[0]["params"]
    product = out["products"][0]

    assert params["category"] == 4
    assert params["tag"] == 9
    assert params["orderby"] == "modified"
    assert params["order"] == "desc"
    assert params["modified_after"] == "2026-06-05T00:00:00"
    assert params["featured"] == "true"
    assert params["on_sale"] == "true"
    assert params["min_price"] == "10"
    assert params["max_price"] == "25"
    assert product["date_modified"] == "2026-06-09T11:00:00"
    assert product["featured"] is True
    assert product["total_sales"] == 12
    assert product["categories"] == [{"id": 4, "name": "Bags", "slug": "bags"}]
    assert product["tags"] == [{"id": 9, "name": "Summer", "slug": "summer"}]
    assert product["images"] == [
        {
            "id": 90,
            "src": "https://example.com/tote.jpg",
            "alt": "Canvas tote",
            "name": "tote",
        }
    ]
    assert product["image_count"] == 2
    assert product["short_description"] == "Lightweight daily tote."
    assert product["price_summary"] == {
        "price": "18.00",
        "regular_price": "20.00",
        "sale_price": "18.00",
        "on_sale": True,
    }
