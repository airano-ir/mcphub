"""WooCommerce DELETE tools (issue #75): customer, category, attribute,
variation, media. Each must hit the right REST route with the right force
semantics, be flagged destructive, and never echo deleted personal data."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from core.site_manager import SiteManager
from core.tool_annotations import tool_annotations
from core.tool_generator import ToolGenerator
from plugins.woocommerce.plugin import WooCommercePlugin

pytestmark = pytest.mark.unit

NEW_TOOLS = {
    "delete_customer",
    "delete_product_category",
    "delete_product_attribute",
    "delete_product_variation",
    "delete_media",
}


def _plugin(**extra) -> WooCommercePlugin:
    config = {
        "url": "https://shop.example.com",
        "consumer_key": "ck_test",
        "consumer_secret": "cs_test",
        **extra,
    }
    return WooCommercePlugin(config, project_id="woocommerce_test")


def test_specs_present_write_scoped_and_destructive():
    specs = {s["name"]: s for s in WooCommercePlugin.get_tool_specifications()}
    assert set(specs) >= NEW_TOOLS
    for name in NEW_TOOLS:
        assert specs[name]["scope"] == "write"  # same tier as delete_product/order/coupon
        assert specs[name]["destructive"] is True


def test_generated_annotations_are_destructive():
    tools = ToolGenerator(SiteManager()).generate_tools(WooCommercePlugin, "woocommerce")
    by_name = {t.name: t for t in tools}
    for name in NEW_TOOLS:
        ann = tool_annotations(by_name[f"woocommerce_{name}"])
        assert ann["readOnlyHint"] is False and ann["destructiveHint"] is True


@pytest.mark.parametrize(
    ("method", "kwargs", "endpoint", "params"),
    [
        ("delete_product_category", {"category_id": 7}, "products/categories/7", {"force": "true"}),
        (
            "delete_product_attribute",
            {"attribute_id": 3},
            "products/attributes/3",
            {"force": "true"},
        ),
        (
            "delete_product_variation",
            {"product_id": 10, "variation_id": 11},
            "products/10/variations/11",
            {"force": "false"},
        ),
        (
            "delete_product_variation",
            {"product_id": 10, "variation_id": 11, "force": True},
            "products/10/variations/11",
            {"force": "true"},
        ),
        ("delete_customer", {"customer_id": 5}, "customers/5", {"force": "true"}),
        (
            "delete_customer",
            {"customer_id": 5, "reassign": 1},
            "customers/5",
            {"force": "true", "reassign": "1"},
        ),
    ],
)
async def test_wc_routes_and_force_semantics(method, kwargs, endpoint, params):
    plugin = _plugin()
    plugin.client.delete = AsyncMock(return_value={"id": 1, "email": "jane@example.com"})
    out = json.loads(await getattr(plugin, method)(**kwargs))
    assert out["success"] is True
    plugin.client.delete.assert_awaited_once_with(endpoint, params=params, use_woocommerce=True)


async def test_delete_customer_never_echoes_personal_data():
    plugin = _plugin()
    plugin.client.delete = AsyncMock(
        return_value={"id": 5, "email": "jane@example.com", "billing": {"phone": "0912"}}
    )
    raw = await plugin.delete_customer(customer_id=5)
    assert "jane@example.com" not in raw and "0912" not in raw


async def test_delete_media_requires_wp_credentials_on_wc_keys_site():
    plugin = _plugin()  # consumer keys only -> no WP Application Password
    out = json.loads(await plugin.delete_media(media_id=9))
    assert out["error_code"] == "WP_CREDENTIALS_MISSING"


async def test_delete_media_uses_wp_rest_with_force():
    plugin = _plugin(wp_username="admin", wp_app_password="xxxx xxxx")
    plugin.wp_media_client.delete = AsyncMock(return_value={"deleted": True, "previous": {}})
    out = json.loads(await plugin.delete_media(media_id=9))
    assert out["success"] is True
    plugin.wp_media_client.delete.assert_awaited_once_with("media/9", params={"force": "true"})


async def test_upstream_error_is_reported_not_raised():
    plugin = _plugin()
    plugin.client.delete = AsyncMock(side_effect=Exception("[woocommerce_rest_term_invalid] nope"))
    out = json.loads(await plugin.delete_product_category(category_id=999))
    assert "error" in out and "999" in out["message"]
