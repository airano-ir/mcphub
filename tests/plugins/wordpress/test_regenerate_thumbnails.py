"""F.5a.8.2 — Tests for wordpress_regenerate_thumbnails."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.regenerate_thumbnails import (
    RegenerateThumbnailsHandler,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return RegenerateThumbnailsHandler(wp_client)


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------


def test_spec_shape():
    specs = get_tool_specifications()
    assert len(specs) == 1
    s = specs[0]
    assert s["name"] == "regenerate_thumbnails"
    assert s["scope"] == "write"
    props = s["schema"]["properties"]
    assert {"ids", "all", "offset", "limit"} <= set(props.keys())


# ---------------------------------------------------------------------------
# Validation (no round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_neither_ids_nor_all_is_rejected(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.regenerate_thumbnails())
    assert out["ok"] is False
    assert out["error"] == "invalid_request"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_both_ids_and_all_is_rejected(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.regenerate_thumbnails(ids=[1], all=True))
    assert out["ok"] is False
    assert "mutually exclusive" in out["message"]
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_empty_ids_list_is_rejected(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.regenerate_thumbnails(ids=["abc", 0, -1]))
    assert out["ok"] is False
    assert out["error"] == "invalid_request"
    post_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path — ids mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ids_mode_dedupes_and_caps(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def _post(route, json_data=None, use_custom_namespace=False):
        captured["route"] = route
        captured["body"] = json_data
        captured["ns"] = use_custom_namespace
        return {
            "mode": "ids",
            "attempted": 3,
            "processed": 3,
            "skipped": [],
            "errors": [],
            "plugin_version": "2.8.0",
        }

    monkeypatch.setattr(wp_client, "post", _post)

    # 60 ids with duplicates — should be deduped and capped at 50
    ids = [5, 5, 10, 10] + list(range(1, 57))
    out = json.loads(await handler.regenerate_thumbnails(ids=ids))

    assert out["ok"] is True
    assert out["mode"] == "ids"
    assert out["processed"] == 3
    assert out["plugin_version"] == "2.8.0"
    assert captured["route"] == "airano-mcp/v1/regenerate-thumbnails"
    assert captured["ns"] is True
    assert "all" not in captured["body"]
    sent = captured["body"]["ids"]
    assert len(sent) <= 50
    assert len(sent) == len(set(sent))  # deduped


@pytest.mark.asyncio
async def test_all_mode_forwards_offset_and_limit(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def _post(route, json_data=None, use_custom_namespace=False):
        captured["body"] = json_data
        return {
            "mode": "all",
            "attempted": 10,
            "processed": 10,
            "skipped": [],
            "errors": [],
            "offset": 100,
            "limit": 10,
            "has_more": True,
            "next_offset": 110,
            "total": 200,
            "plugin_version": "2.8.0",
        }

    monkeypatch.setattr(wp_client, "post", _post)

    out = json.loads(await handler.regenerate_thumbnails(all=True, offset=100, limit=10))

    assert captured["body"] == {"all": True, "offset": 100, "limit": 10}
    assert out["mode"] == "all"
    assert out["has_more"] is True
    assert out["next_offset"] == 110
    assert out["total"] == 200


@pytest.mark.asyncio
async def test_all_mode_limit_capped_server_side(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def _post(route, json_data=None, use_custom_namespace=False):
        captured["body"] = json_data
        return {"mode": "all", "attempted": 0, "processed": 0}

    monkeypatch.setattr(wp_client, "post", _post)
    await handler.regenerate_thumbnails(all=True, limit=9999)
    assert captured["body"]["limit"] == 50


@pytest.mark.asyncio
async def test_all_mode_negative_offset_clamped(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def _post(route, json_data=None, use_custom_namespace=False):
        captured["body"] = json_data
        return {"mode": "all", "attempted": 0, "processed": 0}

    monkeypatch.setattr(wp_client, "post", _post)
    await handler.regenerate_thumbnails(all=True, offset=-5)
    assert captured["body"]["offset"] == 0


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_companion_unreachable_returns_structured_error(handler, wp_client, monkeypatch):
    async def _boom(*_a, **_kw):
        raise RuntimeError("404 - rest_no_route")

    monkeypatch.setattr(wp_client, "post", _boom)
    out = json.loads(await handler.regenerate_thumbnails(ids=[1, 2]))
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"
    assert "v2.8.0" in out["hint"]


@pytest.mark.asyncio
async def test_non_dict_response_is_rejected(handler, wp_client, monkeypatch):
    async def _weird(*_a, **_kw):
        return ["not", "a", "dict"]

    monkeypatch.setattr(wp_client, "post", _weird)
    out = json.loads(await handler.regenerate_thumbnails(ids=[1]))
    assert out["ok"] is False
    assert out["error"] == "invalid_response"


@pytest.mark.asyncio
async def test_errors_from_companion_surface_through(handler, wp_client, monkeypatch):
    async def _errs(*_a, **_kw):
        return {
            "mode": "ids",
            "attempted": 2,
            "processed": 0,
            "skipped": [{"id": 42, "reason": "not_image"}],
            "errors": [{"id": 99, "error": "file_missing"}],
            "plugin_version": "2.8.0",
        }

    monkeypatch.setattr(wp_client, "post", _errs)
    out = json.loads(await handler.regenerate_thumbnails(ids=[42, 99]))
    # processed=0 with at least one error → not ok
    assert out["ok"] is False
    assert out["errors"] == [{"id": 99, "error": "file_missing"}]
    assert out["skipped"] == [{"id": 42, "reason": "not_image"}]
