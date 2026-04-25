"""F.18.2 — Tests for wordpress_bulk_update_meta."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.bulk_meta import (
    MAX_BULK_ITEMS,
    BulkMetaHandler,
    _validate_updates,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return BulkMetaHandler(wp_client)


# ---------------------------------------------------------------------------
# Client-side validation: should never hit the network.
# ---------------------------------------------------------------------------


def test_validate_rejects_non_list():
    out = _validate_updates("not a list")
    assert isinstance(out, dict)
    assert out["error"] == "invalid_updates"


def test_validate_rejects_empty_list():
    out = _validate_updates([])
    assert isinstance(out, dict)
    assert out["error"] == "empty_updates"


def test_validate_rejects_too_many_items():
    too_many = [{"post_id": i + 1, "meta": {"k": "v"}} for i in range(MAX_BULK_ITEMS + 1)]
    out = _validate_updates(too_many)
    assert isinstance(out, dict)
    assert out["error"] == "too_many_items"


def test_validate_rejects_non_object_item():
    out = _validate_updates(["not a dict"])
    assert isinstance(out, dict)
    assert out["error"] == "invalid_item"
    assert out["index"] == 0


def test_validate_rejects_non_positive_post_id():
    out = _validate_updates([{"post_id": 0, "meta": {"k": "v"}}])
    assert isinstance(out, dict)
    assert out["error"] == "invalid_post_id"


def test_validate_rejects_non_dict_meta():
    out = _validate_updates([{"post_id": 1, "meta": "not a dict"}])
    assert isinstance(out, dict)
    assert out["error"] == "invalid_meta"


def test_validate_passes_well_formed_input():
    out = _validate_updates(
        [
            {"post_id": 1, "meta": {"a": 1}},
            {"post_id": 2, "meta": {"b": None}},
        ]
    )
    assert isinstance(out, list)
    assert out == [
        {"post_id": 1, "meta": {"a": 1}},
        {"post_id": 2, "meta": {"b": None}},
    ]


# ---------------------------------------------------------------------------
# Handler behaviour: network errors and happy paths.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_side_reject_does_not_hit_network(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)

    out_json = await handler.bulk_update_meta(updates="not a list")
    out = json.loads(out_json)
    assert out["ok"] is False
    assert out["error"] == "invalid_updates"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_companion_unreachable_returns_structured_error(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=RuntimeError("404 Not Found")))
    out = json.loads(await handler.bulk_update_meta(updates=[{"post_id": 1, "meta": {"k": "v"}}]))
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"
    assert "probe_capabilities" in out["hint"]
    assert out["total"] == 1


@pytest.mark.asyncio
async def test_happy_path_passes_updates_as_list(handler, wp_client, monkeypatch):
    companion_response = {
        "total": 2,
        "updated": 2,
        "failed": 0,
        "skipped": 0,
        "results": [
            {"index": 0, "post_id": 1, "status": "ok", "updated_keys": ["a"]},
            {"index": 1, "post_id": 2, "status": "ok", "updated_keys": ["b"]},
        ],
    }
    post_mock = AsyncMock(return_value=companion_response)
    monkeypatch.setattr(wp_client, "post", post_mock)

    updates = [
        {"post_id": 1, "meta": {"a": "1"}},
        {"post_id": 2, "meta": {"b": "2"}},
    ]
    out = json.loads(await handler.bulk_update_meta(updates=updates))
    assert out["ok"] is True
    assert out["total"] == 2
    assert out["updated"] == 2
    assert out["failed"] == 0
    assert len(out["results"]) == 2

    post_mock.assert_called_once_with(
        "airano-mcp/v1/bulk-meta",
        json_data={"updates": updates},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_mixed_success_and_skip_passed_through(handler, wp_client, monkeypatch):
    companion_response = {
        "total": 3,
        "updated": 1,
        "failed": 0,
        "skipped": 2,
        "results": [
            {"index": 0, "post_id": 1, "status": "ok", "updated_keys": ["a"]},
            {"index": 1, "post_id": 999, "status": "not_found", "error": "post_not_found"},
            {"index": 2, "post_id": 2, "status": "forbidden", "error": "cannot_edit_post"},
        ],
    }
    monkeypatch.setattr(wp_client, "post", AsyncMock(return_value=companion_response))

    out = json.loads(
        await handler.bulk_update_meta(
            updates=[
                {"post_id": 1, "meta": {"a": "1"}},
                {"post_id": 999, "meta": {"b": "2"}},
                {"post_id": 2, "meta": {"c": "3"}},
            ]
        )
    )
    assert out["ok"] is True
    assert out["updated"] == 1
    assert out["skipped"] == 2
    assert out["results"][1]["status"] == "not_found"
    assert out["results"][2]["status"] == "forbidden"


@pytest.mark.asyncio
async def test_null_meta_value_survives_payload(handler, wp_client, monkeypatch):
    """null values delete keys in PHP — we must preserve them in the JSON payload."""
    captured: dict = {}

    async def fake_post(endpoint, json_data=None, **kwargs):
        captured["json_data"] = json_data
        return {"total": 1, "updated": 1, "failed": 0, "skipped": 0, "results": []}

    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=fake_post))

    await handler.bulk_update_meta(updates=[{"post_id": 1, "meta": {"rank_math_title": None}}])
    assert captured["json_data"]["updates"][0]["meta"] == {"rank_math_title": None}


def test_tool_spec_is_write_scope():
    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "bulk_update_meta"
    assert specs[0]["scope"] == "write"
    assert "updates" in specs[0]["schema"]["properties"]
