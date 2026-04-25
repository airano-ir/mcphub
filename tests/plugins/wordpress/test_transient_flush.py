"""F.18.5 — Tests for wordpress_transient_flush."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.transient_flush import (
    TransientFlushHandler,
    _validate,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return TransientFlushHandler(wp_client)


# ---------------------------------------------------------------------------
# Client-side validation.
# ---------------------------------------------------------------------------


def test_validate_defaults_to_expired():
    assert _validate(None, None) is None


def test_validate_expired_ok():
    assert _validate("expired", None) is None


def test_validate_all_ok():
    assert _validate("all", None) is None


def test_validate_pattern_requires_pattern():
    err = _validate("pattern", None)
    assert err is not None
    assert err["error"] == "pattern_required"


def test_validate_pattern_with_glob_ok():
    assert _validate("pattern", "rank_math_*") is None


def test_validate_rejects_unknown_scope():
    err = _validate("demolish", None)
    assert err is not None
    assert err["error"] == "invalid_scope"


# ---------------------------------------------------------------------------
# Handler behaviour.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_scope_never_hits_network(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)
    out = json.loads(await handler.transient_flush(scope="demolish"))
    assert out["ok"] is False
    assert out["error"] == "invalid_scope"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_pattern_without_pattern_rejected_client_side(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)
    out = json.loads(await handler.transient_flush(scope="pattern"))
    assert out["ok"] is False
    assert out["error"] == "pattern_required"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_expired_happy_path(handler, wp_client, monkeypatch):
    companion_response = {
        "ok": True,
        "scope": "expired",
        "pattern": None,
        "include_site_transients": True,
        "deleted_count": 42,
        "deleted_sample": ["foo", "bar"],
        "plugin_version": "2.5.0",
    }
    post_mock = AsyncMock(return_value=companion_response)
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.transient_flush())  # default scope
    assert out["ok"] is True
    assert out["scope"] == "expired"
    assert out["deleted_count"] == 42

    call_args = post_mock.call_args
    assert call_args.args[0] == "airano-mcp/v1/transient-flush"
    body = call_args.kwargs["json_data"]
    assert body["scope"] == "expired"
    assert body["include_site_transients"] is True
    assert "pattern" not in body


@pytest.mark.asyncio
async def test_pattern_passes_pattern_through(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def fake_post(endpoint, json_data=None, **kwargs):
        captured["body"] = json_data
        return {
            "ok": True,
            "scope": "pattern",
            "pattern": "rank_math_*",
            "include_site_transients": False,
            "deleted_count": 3,
            "deleted_sample": ["rank_math_a", "rank_math_b", "rank_math_c"],
            "plugin_version": "2.5.0",
        }

    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=fake_post))

    out = json.loads(
        await handler.transient_flush(
            scope="pattern",
            pattern="rank_math_*",
            include_site_transients=False,
        )
    )
    assert out["ok"] is True
    assert out["pattern"] == "rank_math_*"
    assert out["deleted_count"] == 3
    assert captured["body"]["pattern"] == "rank_math_*"
    assert captured["body"]["include_site_transients"] is False


@pytest.mark.asyncio
async def test_include_site_transients_bool_coercion(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def fake_post(endpoint, json_data=None, **kwargs):
        captured["body"] = json_data
        return {"ok": True, "scope": "all", "deleted_count": 0}

    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=fake_post))

    # String "false" should coerce to False.
    await handler.transient_flush(scope="all", include_site_transients="false")
    assert captured["body"]["include_site_transients"] is False

    # Integer 1 should coerce to True.
    await handler.transient_flush(scope="all", include_site_transients=1)
    assert captured["body"]["include_site_transients"] is True

    # None / default → True.
    await handler.transient_flush(scope="all", include_site_transients=None)
    assert captured["body"]["include_site_transients"] is True


@pytest.mark.asyncio
async def test_companion_unreachable(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=RuntimeError("404 Not Found")))
    out = json.loads(await handler.transient_flush(scope="expired"))
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"


@pytest.mark.asyncio
async def test_non_dict_response(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "post", AsyncMock(return_value="bad"))
    out = json.loads(await handler.transient_flush(scope="expired"))
    assert out["ok"] is False
    assert out["error"] == "invalid_response"


def test_tool_spec_is_admin_scope():
    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "transient_flush"
    assert specs[0]["scope"] == "admin"
    assert set(specs[0]["schema"]["properties"]["scope"]["enum"]) == {
        "expired",
        "all",
        "pattern",
    }
