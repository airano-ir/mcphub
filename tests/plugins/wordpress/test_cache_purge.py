"""F.18.4 — Tests for wordpress_cache_purge."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.cache_purge import (
    CachePurgeHandler,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return CachePurgeHandler(wp_client)


@pytest.mark.asyncio
async def test_happy_path(handler, wp_client, monkeypatch):
    companion_response = {
        "detected": ["wp_rocket", "litespeed"],
        "purged": ["wp_rocket_all", "litespeed_all", "object_cache"],
        "skipped": [],
        "errors": [],
        "ok": True,
        "plugin_version": "2.4.0",
    }
    post_mock = AsyncMock(return_value=companion_response)
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.cache_purge())
    assert out["ok"] is True
    assert out["detected"] == ["wp_rocket", "litespeed"]
    assert "object_cache" in out["purged"]
    assert out["plugin_version"] == "2.4.0"

    post_mock.assert_called_once_with(
        "airano-mcp/v1/cache-purge",
        json_data={},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_no_cache_plugins_detected(handler, wp_client, monkeypatch):
    companion_response = {
        "detected": [],
        "purged": ["object_cache"],
        "skipped": [],
        "errors": [],
        "ok": True,
        "plugin_version": "2.4.0",
    }
    monkeypatch.setattr(wp_client, "post", AsyncMock(return_value=companion_response))

    out = json.loads(await handler.cache_purge())
    assert out["ok"] is True
    assert out["detected"] == []
    # Object cache still flushed unconditionally.
    assert "object_cache" in out["purged"]


@pytest.mark.asyncio
async def test_partial_errors_propagated(handler, wp_client, monkeypatch):
    companion_response = {
        "detected": ["wp_rocket"],
        "purged": ["object_cache"],
        "skipped": [],
        "errors": [{"plugin": "wp_rocket", "message": "rocket_clean_domain exploded"}],
        "ok": False,
        "plugin_version": "2.4.0",
    }
    monkeypatch.setattr(wp_client, "post", AsyncMock(return_value=companion_response))

    out = json.loads(await handler.cache_purge())
    assert out["ok"] is False
    assert len(out["errors"]) == 1
    assert out["errors"][0]["plugin"] == "wp_rocket"


@pytest.mark.asyncio
async def test_companion_unreachable(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=RuntimeError("404 Not Found")))

    out = json.loads(await handler.cache_purge())
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"
    assert "manage_options" in out["hint"]


@pytest.mark.asyncio
async def test_non_dict_response(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "post", AsyncMock(return_value="not a dict"))

    out = json.loads(await handler.cache_purge())
    assert out["ok"] is False
    assert out["error"] == "invalid_response"


@pytest.mark.asyncio
async def test_ok_inferred_from_empty_errors_if_missing(handler, wp_client, monkeypatch):
    """Older companion builds might not emit an `ok` flag; derive from errors list."""
    companion_response = {
        "detected": ["w3_total_cache"],
        "purged": ["w3_total_cache_all", "object_cache"],
        "errors": [],
        "plugin_version": "2.4.0",
    }
    monkeypatch.setattr(wp_client, "post", AsyncMock(return_value=companion_response))

    out = json.loads(await handler.cache_purge())
    assert out["ok"] is True


def test_tool_spec_is_admin_scope():
    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "cache_purge"
    assert specs[0]["scope"] == "admin"
