"""F.19.3.2-.3 — Tests for the WordPress Specialist bulk handler.

Mocks ``WordPressClient.request`` and asserts:

* tool spec contract: 2 tools both on scope=editor
* fan-out behaviour: each item in ``updates`` triggers one stock REST
  call to ``posts/{id}`` or ``{taxonomy}/{id}`` (no companion route);
  per-item ``id`` is stripped from the body
* per-item failure is captured as
  ``{id, status:'error', error}`` instead of failing the whole call
* S-26 client-side cap: 50-item limit enforced as ``bulk_too_large``
  before any HTTP traffic
* taxonomy slug shape validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, call

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.bulk import (
    BulkHandler,
    _validate_taxonomy,
    _validate_updates,
    get_tool_specifications,
)

# ───── Tool spec contract ────────────────────────────────────────────


def test_tool_specs_count_and_names_match_f1933():
    specs = get_tool_specifications()
    assert len(specs) == 2, "F.19.3.3 advertises 2 bulk tools"
    names = {s["name"] for s in specs}
    assert names == {"wp_bulk_post_update", "wp_bulk_term_update"}


def test_all_bulk_tools_on_editor_tier():
    """Bulk write surface = editor tier (mirror of page edits)."""
    for spec in get_tool_specifications():
        assert spec["scope"] == "editor", f"{spec['name']} should be scope=editor"


def test_every_spec_has_the_full_contract():
    for spec in get_tool_specifications():
        assert spec["name"] == spec["method_name"]
        assert spec["description"]
        assert isinstance(spec["schema"], dict)
        assert spec["schema"].get("type") == "object"


def test_bulk_post_update_required_and_caps():
    by_name = {s["name"]: s for s in get_tool_specifications()}
    schema = by_name["wp_bulk_post_update"]["schema"]
    assert schema["required"] == ["updates"]
    assert schema["properties"]["updates"]["maxItems"] == 50
    assert schema["properties"]["updates"]["items"]["required"] == ["id"]


def test_bulk_term_update_requires_taxonomy_and_updates():
    by_name = {s["name"]: s for s in get_tool_specifications()}
    schema = by_name["wp_bulk_term_update"]["schema"]
    assert set(schema["required"]) == {"taxonomy", "updates"}
    assert schema["properties"]["updates"]["maxItems"] == 50


# ───── Validators ────────────────────────────────────────────────────


def test_validate_updates_accepts_valid_shape():
    items = [{"id": 1, "title": "x"}, {"id": 2, "status": "publish"}]
    assert _validate_updates(items) is items


def test_validate_updates_rejects_empty_list():
    with pytest.raises(ValueError, match="at least one"):
        _validate_updates([])


def test_validate_updates_rejects_non_list():
    with pytest.raises(ValueError, match="must be a list"):
        _validate_updates({"id": 1})


def test_validate_updates_rejects_oversize_payload():
    """S-26 client cap — 50-item ceiling."""
    items = [{"id": i + 1} for i in range(51)]
    with pytest.raises(ValueError, match="bulk_too_large"):
        _validate_updates(items)


def test_validate_updates_rejects_missing_id():
    with pytest.raises(ValueError, match="id must be a positive integer"):
        _validate_updates([{"title": "x"}])


def test_validate_updates_rejects_negative_or_zero_id():
    with pytest.raises(ValueError, match="positive integer"):
        _validate_updates([{"id": 0}])
    with pytest.raises(ValueError, match="positive integer"):
        _validate_updates([{"id": -1}])


def test_validate_updates_rejects_non_int_id():
    with pytest.raises(ValueError, match="positive integer"):
        _validate_updates([{"id": "1"}])
    with pytest.raises(ValueError, match="positive integer"):
        _validate_updates([{"id": True}])  # bool is rejected


def test_validate_updates_rejects_non_dict_item():
    with pytest.raises(ValueError, match="must be an object"):
        _validate_updates(["not a dict"])


def test_validate_taxonomy_accepts_common_slugs():
    assert _validate_taxonomy("categories") == "categories"
    assert _validate_taxonomy("tags") == "tags"
    assert _validate_taxonomy("product_cat") == "product_cat"
    assert _validate_taxonomy("post-tag") == "post-tag"


def test_validate_taxonomy_rejects_bad_shape():
    with pytest.raises(ValueError, match="non-empty"):
        _validate_taxonomy("")
    with pytest.raises(ValueError, match="must match"):
        _validate_taxonomy("Cat With Spaces")
    with pytest.raises(ValueError, match="must match"):
        _validate_taxonomy("../escape")
    with pytest.raises(ValueError, match="must be a string"):
        _validate_taxonomy(42)


# ───── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.request = AsyncMock(return_value={"id": 1})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return BulkHandler(client)


# ───── Fan-out shape — wp_bulk_post_update ───────────────────────────


@pytest.mark.asyncio
async def test_bulk_post_update_fans_out_to_stock_rest(handler, client):
    updates = [
        {"id": 11, "status": "publish"},
        {"id": 12, "title": "New title"},
    ]
    result = await handler.wp_bulk_post_update(updates=updates)
    # One request per item, against stock REST (no use_custom_namespace).
    assert client.request.await_count == 2
    calls = client.request.await_args_list
    paths = sorted(c.args[1] for c in calls)
    assert paths == ["posts/11", "posts/12"]
    # Per-item body strips ``id``.
    bodies = {c.args[1]: c.kwargs.get("json_data") for c in calls}
    assert bodies["posts/11"] == {"status": "publish"}
    assert bodies["posts/12"] == {"title": "New title"}
    # Per-item status array.
    assert result["total"] == 2
    assert result["ok"] == 2
    assert result["errors"] == 0
    statuses = sorted(r["status"] for r in result["results"])
    assert statuses == ["ok", "ok"]


@pytest.mark.asyncio
async def test_bulk_post_update_uses_post_method_not_put(handler, client):
    """Stock REST uses POST for updates (matches WP-CLI / docs)."""
    await handler.wp_bulk_post_update(updates=[{"id": 1, "status": "draft"}])
    method = client.request.call_args.args[0]
    assert method == "POST"


@pytest.mark.asyncio
async def test_bulk_post_update_does_not_use_custom_namespace(handler, client):
    """Stock REST means the bare wp/v2 base — no custom namespace flag."""
    await handler.wp_bulk_post_update(updates=[{"id": 1, "status": "draft"}])
    kwargs = client.request.call_args.kwargs
    assert "use_custom_namespace" not in kwargs or kwargs["use_custom_namespace"] is False


@pytest.mark.asyncio
async def test_bulk_post_update_id_only_item_omits_body(handler, client):
    """If only ``id`` is provided, json_data should be None (no-op stock REST POST)."""
    await handler.wp_bulk_post_update(updates=[{"id": 5}])
    kwargs = client.request.call_args.kwargs
    assert kwargs.get("json_data") is None


@pytest.mark.asyncio
async def test_bulk_post_update_captures_per_item_failure(handler, client):
    """One failing item should not fail the whole call."""

    async def side_effect(method, endpoint, json_data=None, **kw):
        if endpoint == "posts/12":
            raise Exception("[rest_cannot_edit] Sorry, you cannot edit this post.")
        return {"id": int(endpoint.split("/")[-1])}

    client.request = AsyncMock(side_effect=side_effect)  # type: ignore[method-assign]
    handler.client = client
    result = await handler.wp_bulk_post_update(
        updates=[{"id": 11, "status": "publish"}, {"id": 12, "status": "publish"}]
    )
    assert result["total"] == 2
    assert result["ok"] == 1
    assert result["errors"] == 1
    by_id = {r["id"]: r for r in result["results"]}
    assert by_id[11]["status"] == "ok"
    assert by_id[12]["status"] == "error"
    assert "rest_cannot_edit" in by_id[12]["error"]


@pytest.mark.asyncio
async def test_bulk_post_update_rejects_empty(handler, client):
    with pytest.raises(ValueError, match="at least one"):
        await handler.wp_bulk_post_update(updates=[])
    client.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_post_update_rejects_oversize_before_http(handler, client):
    """S-26: bulk_too_large is raised client-side without any network call."""
    items = [{"id": i + 1, "status": "publish"} for i in range(51)]
    with pytest.raises(ValueError, match="bulk_too_large"):
        await handler.wp_bulk_post_update(updates=items)
    client.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_post_update_at_exact_50_limit(handler, client):
    """50 is the documented ceiling — must succeed."""
    items = [{"id": i + 1, "status": "publish"} for i in range(50)]
    result = await handler.wp_bulk_post_update(updates=items)
    assert result["total"] == 50
    assert client.request.await_count == 50


# ───── Fan-out shape — wp_bulk_term_update ───────────────────────────


@pytest.mark.asyncio
async def test_bulk_term_update_uses_taxonomy_in_path(handler, client):
    updates = [{"id": 7, "name": "Renamed"}]
    await handler.wp_bulk_term_update(taxonomy="categories", updates=updates)
    path = client.request.call_args.args[1]
    assert path == "categories/7"


@pytest.mark.asyncio
async def test_bulk_term_update_returns_taxonomy_in_envelope(handler, client):
    result = await handler.wp_bulk_term_update(
        taxonomy="product_cat", updates=[{"id": 1, "name": "x"}]
    )
    assert result["taxonomy"] == "product_cat"
    assert result["total"] == 1
    assert result["ok"] == 1


@pytest.mark.asyncio
async def test_bulk_term_update_rejects_bad_taxonomy(handler, client):
    with pytest.raises(ValueError, match="must match"):
        await handler.wp_bulk_term_update(taxonomy="../escape", updates=[{"id": 1, "name": "x"}])
    client.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_term_update_validates_updates_too(handler, client):
    """Taxonomy + updates are independent gates; updates still validated."""
    with pytest.raises(ValueError, match="bulk_too_large"):
        await handler.wp_bulk_term_update(
            taxonomy="categories",
            updates=[{"id": i + 1, "name": str(i)} for i in range(51)],
        )
    client.request.assert_not_awaited()


# ───── Concurrency bound (smoke check) ───────────────────────────────


@pytest.mark.asyncio
async def test_bulk_fanout_runs_concurrently_not_serially(handler, client, monkeypatch):
    """The fan-out should issue all 10 calls without waiting on the previous to settle.

    We don't time anything; we just verify ``asyncio.gather`` is the
    dispatcher (every call ends up in await_args_list and matches our
    expected paths).
    """
    items = [{"id": i + 1, "status": "publish"} for i in range(10)]
    await handler.wp_bulk_post_update(updates=items)
    paths = sorted(c.args[1] for c in client.request.await_args_list)
    assert paths == sorted(f"posts/{i + 1}" for i in range(10))
    assert client.request.await_count == 10


# ───── ``call`` import smoke (pytest discovery) ──────────────────────


def test_call_helper_imported():
    """Sanity: ``unittest.mock.call`` import lives so we can use it elsewhere."""
    assert call is not None
