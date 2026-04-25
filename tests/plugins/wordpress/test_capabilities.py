"""F.18.1 — Tests for wordpress_probe_capabilities."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.capabilities import (
    _EXPECTED_CAPS,
    _EXPECTED_ROUTES,
    CapabilitiesHandler,
    _CapabilitiesCache,
    get_cached_capabilities,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def cache():
    return _CapabilitiesCache(ttl=24 * 3600)


@pytest.fixture
def companion_payload():
    return {
        "plugin_version": "2.1.0",
        "companion": True,
        "user": {
            "id": 1,
            "login": "mcphub",
            "roles": ["administrator"],
            "capabilities": {
                "upload_files": True,
                "edit_posts": True,
                "publish_posts": True,
                "edit_others_posts": True,
                "delete_posts": True,
                "edit_pages": True,
                "publish_pages": True,
                "manage_categories": True,
                "moderate_comments": True,
                "manage_options": True,
                "edit_users": True,
                "list_users": True,
                "manage_woocommerce": False,
                "edit_shop_orders": False,
                "edit_products": False,
            },
        },
        "features": {
            "rank_math": True,
            "yoast": False,
            "woocommerce": False,
            "multisite": False,
        },
        "routes": {
            "seo_meta": True,
            "upload_limits": True,
            "upload_chunk": True,
            "capabilities": True,
            "bulk_meta": False,
            "export": False,
            "cache_purge": False,
            "transient_flush": False,
            "site_health": False,
            "audit_hook": False,
        },
        "wordpress": {
            "version": "6.5.3",
            "php_version": "8.1.27",
            "rest_enabled": True,
        },
    }


@pytest.mark.asyncio
async def test_companion_endpoint_parses_and_caches(
    wp_client, monkeypatch, cache, companion_payload
):
    handler = CapabilitiesHandler(wp_client, cache=cache)
    get_mock = AsyncMock(return_value=companion_payload)
    monkeypatch.setattr(wp_client, "get", get_mock)

    out_json = await handler.probe_capabilities()
    out = json.loads(out_json)

    assert out["companion_available"] is True
    assert out["plugin_version"] == "2.1.0"
    assert out["cached"] is False
    assert out["user"]["login"] == "mcphub"
    assert out["user"]["capabilities"]["upload_files"] is True
    assert out["user"]["capabilities"]["manage_woocommerce"] is False
    assert out["routes"]["upload_chunk"] is True
    assert out["routes"]["bulk_meta"] is False
    assert out["features"]["rank_math"] is True
    assert out["wordpress"]["version"] == "6.5.3"

    get_mock.assert_called_once_with("airano-mcp/v1/capabilities", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_second_call_is_served_from_cache(wp_client, monkeypatch, cache, companion_payload):
    handler = CapabilitiesHandler(wp_client, cache=cache)
    get_mock = AsyncMock(return_value=companion_payload)
    monkeypatch.setattr(wp_client, "get", get_mock)

    await handler.probe_capabilities()
    out2 = json.loads(await handler.probe_capabilities())

    assert out2["cached"] is True
    assert get_mock.call_count == 1


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(wp_client, monkeypatch, companion_payload):
    cache = _CapabilitiesCache(ttl=0.0)
    handler = CapabilitiesHandler(wp_client, cache=cache)
    get_mock = AsyncMock(return_value=companion_payload)
    monkeypatch.setattr(wp_client, "get", get_mock)

    await handler.probe_capabilities()
    await handler.probe_capabilities()
    assert get_mock.call_count == 2


@pytest.mark.asyncio
async def test_companion_missing_returns_false_shape(wp_client, monkeypatch, cache):
    handler = CapabilitiesHandler(wp_client, cache=cache)
    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=RuntimeError("404 Not Found")))

    out = json.loads(await handler.probe_capabilities())
    assert out["companion_available"] is False
    assert out["plugin_version"] is None
    assert out["user"] is None
    assert out["features"] is None
    # All routes default to False so downstream code can still index safely.
    assert all(v is False for v in out["routes"].values())
    assert set(out["routes"].keys()) == set(_EXPECTED_ROUTES)
    assert "companion_unreachable" in out["reason"]


@pytest.mark.asyncio
async def test_non_dict_payload_treated_as_missing(wp_client, monkeypatch, cache):
    handler = CapabilitiesHandler(wp_client, cache=cache)
    monkeypatch.setattr(wp_client, "get", AsyncMock(return_value=["not", "a", "dict"]))

    out = json.loads(await handler.probe_capabilities())
    assert out["companion_available"] is False
    assert out["reason"] == "companion_returned_non_dict"


@pytest.mark.asyncio
async def test_missing_caps_default_to_false(wp_client, monkeypatch, cache):
    """If the plugin drops a cap key (e.g. older plugin build), we fill with False."""
    handler = CapabilitiesHandler(wp_client, cache=cache)
    partial = {
        "plugin_version": "2.1.0",
        "user": {
            "id": 1,
            "login": "x",
            "roles": ["editor"],
            "capabilities": {"upload_files": True, "edit_posts": True},
        },
        "routes": {"upload_limits": True, "upload_chunk": True},
        "features": {"rank_math": False},
        "wordpress": {"version": "6.4"},
    }
    monkeypatch.setattr(wp_client, "get", AsyncMock(return_value=partial))

    out = json.loads(await handler.probe_capabilities())
    assert out["companion_available"] is True
    caps = out["user"]["capabilities"]
    assert caps["upload_files"] is True
    assert caps["manage_options"] is False
    assert set(caps.keys()) == set(_EXPECTED_CAPS)
    routes = out["routes"]
    assert routes["upload_limits"] is True
    assert routes["bulk_meta"] is False
    assert set(routes.keys()) == set(_EXPECTED_ROUTES)


@pytest.mark.asyncio
async def test_extra_caps_preserved_under_extra_key(wp_client, monkeypatch, cache):
    """Caps the plugin sends that aren't in our known list end up under extra_capabilities."""
    handler = CapabilitiesHandler(wp_client, cache=cache)
    payload = {
        "plugin_version": "2.9.0",  # future plugin with more caps
        "user": {
            "id": 1,
            "login": "x",
            "roles": ["administrator"],
            "capabilities": {
                "upload_files": True,
                "some_future_cap": True,
            },
        },
        "routes": {},
        "features": {},
        "wordpress": {},
    }
    monkeypatch.setattr(wp_client, "get", AsyncMock(return_value=payload))

    out = json.loads(await handler.probe_capabilities())
    assert out["user"]["capabilities"]["upload_files"] is True
    assert out["user"]["extra_capabilities"] == {"some_future_cap": True}


@pytest.mark.asyncio
async def test_get_cached_capabilities_returns_none_before_probe(wp_client):
    cache = _CapabilitiesCache(ttl=24 * 3600)
    assert await get_cached_capabilities(wp_client, cache=cache) is None


@pytest.mark.asyncio
async def test_get_cached_capabilities_after_probe(
    wp_client, monkeypatch, cache, companion_payload
):
    handler = CapabilitiesHandler(wp_client, cache=cache)
    monkeypatch.setattr(wp_client, "get", AsyncMock(return_value=companion_payload))
    await handler.probe_capabilities()

    got = await get_cached_capabilities(wp_client, cache=cache)
    assert got is not None
    assert got["companion_available"] is True


def test_tool_spec_is_read_scope():
    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "probe_capabilities"
    assert specs[0]["scope"] == "read"
