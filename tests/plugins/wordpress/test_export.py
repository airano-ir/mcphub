"""F.18.3 — Tests for wordpress_export_content."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.export import (
    EXPORT_DEFAULT_LIMIT,
    EXPORT_MAX_LIMIT,
    ExportHandler,
    _build_query_params,
    _normalise_bool,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return ExportHandler(wp_client)


# ---------------------------------------------------------------------------
# Parameter normalisation.
# ---------------------------------------------------------------------------


class TestNormaliseBool:
    def test_none_defaults(self):
        assert _normalise_bool(None, True) is True
        assert _normalise_bool(None, False) is False

    def test_bool_passthrough(self):
        assert _normalise_bool(True, False) is True
        assert _normalise_bool(False, True) is False

    def test_numeric(self):
        assert _normalise_bool(1, False) is True
        assert _normalise_bool(0, True) is False

    def test_strings(self):
        assert _normalise_bool("true", False) is True
        assert _normalise_bool("False", True) is False
        assert _normalise_bool("yes", False) is True
        assert _normalise_bool("no", True) is False
        assert _normalise_bool("garbage", True) is True  # fallback


class TestBuildQueryParams:
    def test_defaults(self):
        out = _build_query_params(
            post_type=None,
            status=None,
            since=None,
            limit=None,
            offset=None,
            include_media=True,
            include_terms=True,
            include_meta=True,
        )
        assert out["post_type"] == "post"
        assert out["status"] == "publish"
        assert out["limit"] == EXPORT_DEFAULT_LIMIT
        assert out["offset"] == 0
        assert out["include_media"] == "true"
        assert out["include_terms"] == "true"
        assert out["include_meta"] == "true"
        assert "since" not in out

    def test_limit_clamped_to_max(self):
        out = _build_query_params(
            post_type=None,
            status=None,
            since=None,
            limit=EXPORT_MAX_LIMIT * 10,
            offset=None,
            include_media=True,
            include_terms=True,
            include_meta=True,
        )
        assert out["limit"] == EXPORT_MAX_LIMIT

    def test_negative_offset_floored_to_zero(self):
        out = _build_query_params(
            post_type=None,
            status=None,
            since=None,
            limit=None,
            offset=-5,
            include_media=True,
            include_terms=True,
            include_meta=True,
        )
        assert out["offset"] == 0

    def test_since_passed_through(self):
        out = _build_query_params(
            post_type="post",
            status="publish",
            since="2026-04-01T00:00:00Z",
            limit=10,
            offset=0,
            include_media=False,
            include_terms=True,
            include_meta=False,
        )
        assert out["since"] == "2026-04-01T00:00:00Z"
        assert out["include_media"] == "false"
        assert out["include_meta"] == "false"
        assert out["limit"] == 10

    def test_comma_separated_types(self):
        out = _build_query_params(
            post_type="post,page,product",
            status="publish,draft",
            since=None,
            limit=None,
            offset=None,
            include_media=True,
            include_terms=True,
            include_meta=True,
        )
        assert out["post_type"] == "post,page,product"
        assert out["status"] == "publish,draft"


# ---------------------------------------------------------------------------
# Handler behaviour.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_forwards_to_companion(handler, wp_client, monkeypatch):
    companion_response = {
        "post_types": ["post"],
        "status": ["publish"],
        "since": None,
        "limit": 100,
        "offset": 0,
        "returned": 2,
        "total_matching": 5,
        "has_more": True,
        "next_offset": 2,
        "include_media": True,
        "include_terms": True,
        "include_meta": True,
        "posts": [
            {"id": 1, "title": "First", "post_type": "post"},
            {"id": 2, "title": "Second", "post_type": "post"},
        ],
        "media": [],
        "exported_at_gmt": "2026-04-15T09:00:00Z",
        "plugin_version": "2.3.0",
    }
    get_mock = AsyncMock(return_value=companion_response)
    monkeypatch.setattr(wp_client, "get", get_mock)

    out = json.loads(await handler.export_content())
    assert out["ok"] is True
    assert out["returned"] == 2
    assert out["has_more"] is True
    assert out["next_offset"] == 2
    assert len(out["posts"]) == 2
    assert out["plugin_version"] == "2.3.0"

    # Verify the endpoint was called with default params.
    call_args = get_mock.call_args
    assert call_args.args[0] == "airano-mcp/v1/export"
    assert call_args.kwargs["use_custom_namespace"] is True
    params = call_args.kwargs["params"]
    assert params["post_type"] == "post"
    assert params["status"] == "publish"
    assert params["limit"] == EXPORT_DEFAULT_LIMIT


@pytest.mark.asyncio
async def test_all_params_forwarded(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def fake_get(endpoint, params=None, **kwargs):
        captured["endpoint"] = endpoint
        captured["params"] = params
        return {"posts": [], "media": [], "returned": 0, "total_matching": 0}

    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=fake_get))

    await handler.export_content(
        post_type="post,page",
        status="publish,draft",
        since="2026-01-01T00:00:00Z",
        limit=50,
        offset=10,
        include_media=False,
        include_terms=False,
        include_meta=True,
    )
    assert captured["params"]["post_type"] == "post,page"
    assert captured["params"]["status"] == "publish,draft"
    assert captured["params"]["since"] == "2026-01-01T00:00:00Z"
    assert captured["params"]["limit"] == 50
    assert captured["params"]["offset"] == 10
    assert captured["params"]["include_media"] == "false"
    assert captured["params"]["include_terms"] == "false"
    assert captured["params"]["include_meta"] == "true"


@pytest.mark.asyncio
async def test_companion_unreachable_returns_structured_error(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=RuntimeError("404")))
    out = json.loads(await handler.export_content(post_type="post"))
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"
    assert "probe_capabilities" in out["hint"]
    assert "params" in out


@pytest.mark.asyncio
async def test_non_dict_companion_response(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "get", AsyncMock(return_value=["not", "a", "dict"]))
    out = json.loads(await handler.export_content())
    assert out["ok"] is False
    assert out["error"] == "invalid_response"


@pytest.mark.asyncio
async def test_limit_clamping_before_network(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def fake_get(endpoint, params=None, **kwargs):
        captured["params"] = params
        return {"posts": [], "media": []}

    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=fake_get))

    await handler.export_content(limit=10_000)
    assert captured["params"]["limit"] == EXPORT_MAX_LIMIT


def test_tool_spec_is_read_scope():
    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "export_content"
    assert specs[0]["scope"] == "read"
    props = specs[0]["schema"]["properties"]
    for key in (
        "post_type",
        "status",
        "since",
        "limit",
        "offset",
        "include_media",
        "include_terms",
        "include_meta",
    ):
        assert key in props
