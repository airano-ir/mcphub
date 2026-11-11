"""Tests for companion-backed legacy WordPress admin tool names."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.legacy_admin import LegacyAdminHandler, get_tool_specifications


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return LegacyAdminHandler(wp_client)


def test_specs_are_companion_backed_subset():
    names = {spec["name"] for spec in get_tool_specifications()}
    assert names == {
        "wp_cache_flush",
        "wp_transient_delete_all",
        "wp_transient_list",
        "wp_db_check",
        "wp_db_optimize",
    }


@pytest.mark.asyncio
async def test_wp_db_check_calls_companion_route(handler, wp_client, monkeypatch):
    get_mock = AsyncMock(return_value={"ok": True, "action": "check"})
    monkeypatch.setattr(wp_client, "get", get_mock)

    out = json.loads(await handler.wp_db_check())
    assert out["ok"] is True
    assert out["action"] == "check"
    get_mock.assert_awaited_once_with(
        "airano-mcp/v1/admin/db/check",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_wp_db_optimize_calls_companion_route(handler, wp_client, monkeypatch):
    post_mock = AsyncMock(return_value={"ok": True, "action": "optimize"})
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.wp_db_optimize())
    assert out["ok"] is True
    assert out["action"] == "optimize"
    post_mock.assert_awaited_once_with(
        "airano-mcp/v1/admin/db/optimize",
        json_data={},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_wp_db_check_unreachable_returns_structured_error(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=RuntimeError("404")))

    out = json.loads(await handler.wp_db_check())
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"
    assert out["install_hint"]["companion_min_version"] == "2.18.5"
