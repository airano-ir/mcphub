"""WooCommerce product meta_data stays generic and data-driven."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.handlers.products import ProductsHandler


def _product_payload(product_id: int = 99) -> dict:
    return {
        "id": product_id,
        "name": "Widget",
        "type": "simple",
        "status": "draft",
        "price": "",
        "permalink": f"https://wp.example.com/product/widget-{product_id}/",
    }


@pytest.fixture
def client():
    return SimpleNamespace(post=AsyncMock(), put=AsyncMock())


@pytest.fixture
def handler(client):
    return ProductsHandler(client)


@pytest.mark.asyncio
async def test_create_product_passes_meta_data(handler, client):
    client.post.return_value = _product_payload()

    await handler.create_product(
        name="Widget",
        meta_data=[{"key": "_podcast_guid", "value": "episode-1"}],
    )

    client.post.assert_awaited_once()
    (endpoint,) = client.post.await_args.args
    kwargs = client.post.await_args.kwargs
    assert endpoint == "products"
    assert kwargs["use_woocommerce"] is True
    assert kwargs["json_data"]["meta_data"] == [{"key": "_podcast_guid", "value": "episode-1"}]


@pytest.mark.asyncio
async def test_update_product_passes_meta_data(handler, client):
    client.put.return_value = _product_payload()

    await handler.update_product(
        product_id=99,
        meta_data=[{"key": "_license_key", "value": "abc"}],
    )

    client.put.assert_awaited_once_with(
        "products/99",
        json_data={"meta_data": [{"key": "_license_key", "value": "abc"}]},
        use_woocommerce=True,
    )
