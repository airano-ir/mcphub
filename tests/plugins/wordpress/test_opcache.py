"""F.18.8 — Tests for wordpress_opcache_reset."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.opcache import (
    OpcacheHandler,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return OpcacheHandler(wp_client)


@pytest.mark.asyncio
async def test_happy_path(handler, wp_client, monkeypatch):
    companion_response = {
        "ok": True,
        "reset": True,
        "opcache_available": True,
        "enabled": True,
        "validate_timestamps": False,
        "status_before": {"num_cached_scripts": 42},
        "status_after": {"num_cached_scripts": 0},
        "message": "OPcache reset completed.",
        "plugin_version": "2.18.4",
    }
    post_mock = AsyncMock(return_value=companion_response)
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.opcache_reset())
    assert out["ok"] is True
    assert out["reset"] is True
    assert out["opcache_available"] is True
    assert out["validate_timestamps"] is False
    assert out["plugin_version"] == "2.18.4"

    post_mock.assert_called_once_with(
        "airano-mcp/v1/opcache-reset",
        json_data={},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_companion_unreachable(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=RuntimeError("404 Not Found")))

    out = json.loads(await handler.opcache_reset())
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"
    assert "v2.18.4" in out["hint"]


@pytest.mark.asyncio
async def test_non_dict_response(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "post", AsyncMock(return_value="not a dict"))

    out = json.loads(await handler.opcache_reset())
    assert out["ok"] is False
    assert out["error"] == "invalid_response"


@pytest.mark.asyncio
async def test_ok_inferred_from_reset_flag(handler, wp_client, monkeypatch):
    monkeypatch.setattr(
        wp_client,
        "post",
        AsyncMock(
            return_value={
                "reset": True,
                "opcache_available": True,
                "plugin_version": "2.18.4",
            }
        ),
    )

    out = json.loads(await handler.opcache_reset())
    assert out["ok"] is True
    assert out["reset"] is True


def test_tool_spec_is_admin_scope():
    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "opcache_reset"
    assert specs[0]["scope"] == "admin"
    assert specs[0]["schema"]["properties"] == {}
