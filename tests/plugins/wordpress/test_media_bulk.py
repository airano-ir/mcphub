"""F.5a.8.3 — Tests for bulk_delete_media + bulk_reassign_media."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.media_bulk import (
    MediaBulkHandler,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return MediaBulkHandler(wp_client)


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------


def test_specs_expose_both_tools():
    specs = get_tool_specifications()
    names = {s["name"] for s in specs}
    assert names == {"bulk_delete_media", "bulk_reassign_media"}

    delete_spec = next(s for s in specs if s["name"] == "bulk_delete_media")
    assert delete_spec["scope"] == "admin"
    assert delete_spec["schema"]["properties"]["media_ids"]["maxItems"] == 100

    reassign_spec = next(s for s in specs if s["name"] == "bulk_reassign_media")
    assert reassign_spec["scope"] == "write"
    assert "target_post" in reassign_spec["schema"]["required"]


# ---------------------------------------------------------------------------
# Input normalization
# ---------------------------------------------------------------------------


def test_normalize_ids_dedupes_and_caps(handler):
    huge = [5, 5, 5] + list(range(1, 200))
    out = handler._normalize_ids(huge)
    assert len(out) == 100
    assert len(out) == len(set(out))


def test_normalize_ids_drops_non_positive_and_garbage(handler):
    out = handler._normalize_ids([1, 0, -5, "abc", None, 2, 3])
    assert out == [1, 2, 3]


# ---------------------------------------------------------------------------
# bulk_delete_media
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_rejects_empty_list(handler, wp_client, monkeypatch):
    delete_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "delete", delete_mock)

    out = json.loads(await handler.bulk_delete_media([]))
    assert out["ok"] is False
    assert out["error"] == "invalid_request"
    delete_mock.assert_not_called()


@pytest.mark.asyncio
async def test_delete_happy_path(handler, wp_client, monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def _delete(path, params=None):
        calls.append((path, params or {}))
        return {"deleted": True}

    monkeypatch.setattr(wp_client, "delete", _delete)

    out = json.loads(await handler.bulk_delete_media([10, 20, 30], force=True))
    assert out["ok"] is True
    assert out["total"] == 3
    assert out["processed"] == 3
    assert out["errors"] == []
    assert out["force"] is True
    assert len(calls) == 3
    # force flag propagated as string
    assert all(c[1].get("force") == "true" for c in calls)
    paths = sorted(c[0] for c in calls)
    assert paths == ["media/10", "media/20", "media/30"]


@pytest.mark.asyncio
async def test_delete_partial_failure(handler, wp_client, monkeypatch):
    async def _delete(path, params=None):
        if path == "media/20":
            raise RuntimeError("HTTP 404 not found")
        return {"deleted": True}

    monkeypatch.setattr(wp_client, "delete", _delete)

    out = json.loads(await handler.bulk_delete_media([10, 20, 30]))
    assert out["ok"] is False
    assert out["total"] == 3
    assert out["processed"] == 2
    assert len(out["errors"]) == 1
    assert out["errors"][0]["id"] == 20
    assert "404" in out["errors"][0]["error"]


@pytest.mark.asyncio
async def test_delete_force_false_moves_to_trash(handler, wp_client, monkeypatch):
    captured: list[dict] = []

    async def _delete(path, params=None):
        captured.append(params or {})
        return {}

    monkeypatch.setattr(wp_client, "delete", _delete)
    await handler.bulk_delete_media([1], force=False)
    assert captured[0]["force"] == "false"


# ---------------------------------------------------------------------------
# bulk_reassign_media
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reassign_rejects_empty_ids(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.bulk_reassign_media([], target_post=5))
    assert out["ok"] is False
    assert out["error"] == "invalid_request"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_reassign_rejects_negative_target(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.bulk_reassign_media([1], target_post=-1))
    assert out["ok"] is False
    assert out["error"] == "invalid_request"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_reassign_rejects_non_integer_target(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)

    out = json.loads(await handler.bulk_reassign_media([1], target_post="abc"))  # type: ignore[arg-type]
    assert out["ok"] is False
    assert out["error"] == "invalid_request"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_reassign_happy_path(handler, wp_client, monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def _post(path, json_data=None, **kw):
        calls.append((path, json_data or {}))
        return {"id": 1, "post": 42}

    monkeypatch.setattr(wp_client, "post", _post)

    out = json.loads(await handler.bulk_reassign_media([1, 2, 3], target_post=42))
    assert out["ok"] is True
    assert out["processed"] == 3
    assert out["total"] == 3
    assert out["target_post"] == 42
    assert len(calls) == 3
    assert all(c[1] == {"post": 42} for c in calls)


@pytest.mark.asyncio
async def test_reassign_detach_target_zero(handler, wp_client, monkeypatch):
    calls: list[dict] = []

    async def _post(path, json_data=None, **kw):
        calls.append(json_data or {})
        return {}

    monkeypatch.setattr(wp_client, "post", _post)
    out = json.loads(await handler.bulk_reassign_media([1, 2], target_post=0))
    assert out["ok"] is True
    assert all(c == {"post": 0} for c in calls)


@pytest.mark.asyncio
async def test_reassign_partial_failure_surfaces_errors(handler, wp_client, monkeypatch):
    async def _post(path, json_data=None, **kw):
        if path == "media/7":
            raise RuntimeError("permission denied")
        return {}

    monkeypatch.setattr(wp_client, "post", _post)
    out = json.loads(await handler.bulk_reassign_media([6, 7, 8], target_post=100))
    assert out["ok"] is False
    assert out["processed"] == 2
    assert len(out["errors"]) == 1
    assert out["errors"][0]["id"] == 7
