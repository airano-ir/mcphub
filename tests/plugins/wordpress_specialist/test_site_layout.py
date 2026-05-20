"""F.19.6.B — Tests for the WordPress Specialist site layout handler.

Mocks ``WordPressClient.get`` / ``post`` / ``put`` and asserts:

* tool spec contract: 7 tools split read (4) + settings (3)
* each handler method targets the correct ``airano-mcp/v1/admin/*``
  route with ``use_custom_namespace=True`` and the right HTTP verb
* client-side guards reject bad menu item shapes (S-22 pre-check),
  bad customizer actions, missing menu_id / area_id, and non-list
  items / widgets
* ``wp_widget_set`` strips a caller-side ``kind`` field — area kind
  is determined by the area, not the request
* ``custom`` URL menu items skip the ``object_id`` check client-side
  (S-22 dispatcher honours it server-side)
* server-returned error envelopes (forbidden_object_id 403,
  unsupported_legacy_widget 400, etc.) are relayed untouched — the
  companion is the binding gate
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.site_layout import (
    SiteLayoutHandler,
    _validate_menu_item,
    _validate_post_id,
    get_tool_specifications,
)

# ───── Tool spec contract ────────────────────────────────────────────


def test_tool_specs_count_and_names_match_f196b():
    specs = get_tool_specifications()
    assert len(specs) == 7, "F.19.6.B advertises 4 read + 3 settings"
    names = {s["name"] for s in specs}
    assert names == {
        "wp_menu_list",
        "wp_menu_get",
        "wp_menu_set",
        "wp_widget_areas_list",
        "wp_widget_get",
        "wp_widget_set",
        "wp_customizer_changeset",
    }


def test_read_settings_tier_split():
    """Reads at scope=read, writes (incl. customizer) at scope=settings."""
    specs_by_name = {s["name"]: s for s in get_tool_specifications()}
    expected_scope = {
        "wp_menu_list": "read",
        "wp_menu_get": "read",
        "wp_widget_areas_list": "read",
        "wp_widget_get": "read",
        "wp_menu_set": "settings",
        "wp_widget_set": "settings",
        "wp_customizer_changeset": "settings",
    }
    for name, scope in expected_scope.items():
        assert specs_by_name[name]["scope"] == scope, f"{name} should be scope={scope}"


def test_every_spec_has_the_full_contract():
    for spec in get_tool_specifications():
        assert spec["name"] == spec["method_name"]
        assert spec["description"]
        assert isinstance(spec["schema"], dict)
        assert spec["schema"].get("type") == "object"


def test_required_args_declared_on_setters():
    by_name = {s["name"]: s for s in get_tool_specifications()}
    assert by_name["wp_menu_get"]["schema"]["required"] == ["menu_id"]
    assert set(by_name["wp_menu_set"]["schema"]["required"]) == {"menu_id", "items"}
    assert by_name["wp_widget_get"]["schema"]["required"] == ["area_id"]
    assert set(by_name["wp_widget_set"]["schema"]["required"]) == {"area_id", "widgets"}
    assert by_name["wp_customizer_changeset"]["schema"]["required"] == ["action"]


# ───── Validators ────────────────────────────────────────────────────


@pytest.mark.parametrize("good", [0, 1, 42, 9999])
def test_validate_post_id_accepts(good):
    assert _validate_post_id(good, "x") == good


@pytest.mark.parametrize("bad", [-1, "1", 1.5, None, True, False])
def test_validate_post_id_rejects(bad):
    with pytest.raises(ValueError):
        _validate_post_id(bad, "x")


def test_validate_menu_item_accepts_post_type():
    item = {"type": "post_type", "object": "post", "object_id": 12, "title": "Hi"}
    assert _validate_menu_item(item, 0) is item


def test_validate_menu_item_accepts_taxonomy():
    item = {"type": "taxonomy", "object": "category", "object_id": 5}
    assert _validate_menu_item(item, 0) is item


def test_validate_menu_item_custom_skips_object_id():
    """``custom`` URL items must NOT require object_id (S-22)."""
    item = {"type": "custom", "url": "https://example.com", "title": "Ext"}
    assert _validate_menu_item(item, 0) is item


def test_validate_menu_item_rejects_bad_type():
    with pytest.raises(ValueError, match="type must be one of"):
        _validate_menu_item({"type": "magic", "object_id": 1}, 0)


def test_validate_menu_item_rejects_post_type_without_object_id():
    with pytest.raises(ValueError, match="object_id"):
        _validate_menu_item({"type": "post_type", "object": "post"}, 0)


def test_validate_menu_item_rejects_non_dict():
    with pytest.raises(ValueError, match="must be an object"):
        _validate_menu_item("not a dict", 3)


# ───── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.get = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.post = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.put = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return SiteLayoutHandler(client)


# ───── Menu routing ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_menu_list_calls_route(handler, client):
    await handler.wp_menu_list()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/menus",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_menu_get_calls_route(handler, client):
    await handler.wp_menu_get(menu_id=42)
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/menus/42",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_menu_get_rejects_zero_id(handler, client):
    with pytest.raises(ValueError, match="menu_id"):
        await handler.wp_menu_get(menu_id=0)
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_menu_set_passes_items(handler, client):
    items = [
        {"type": "post_type", "object": "page", "object_id": 7, "title": "About"},
        {"type": "custom", "url": "https://x", "title": "Ext"},
    ]
    await handler.wp_menu_set(menu_id=3, items=items)
    client.put.assert_awaited_once_with(
        "airano-mcp/v1/admin/menus/3",
        json_data={"items": items},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_menu_set_passes_optional_name(handler, client):
    await handler.wp_menu_set(
        menu_id=3, items=[{"type": "custom", "url": "/", "title": "Home"}], name="Footer"
    )
    args, kwargs = client.put.call_args
    assert kwargs["json_data"]["name"] == "Footer"


@pytest.mark.asyncio
async def test_menu_set_rejects_bad_item_shape(handler, client):
    with pytest.raises(ValueError, match="must be one of"):
        await handler.wp_menu_set(menu_id=3, items=[{"type": "weird"}])
    client.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_menu_set_rejects_non_list_items(handler, client):
    with pytest.raises(ValueError, match="items must be a list"):
        await handler.wp_menu_set(menu_id=3, items="not a list")  # type: ignore[arg-type]
    client.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_menu_set_rejects_empty_name(handler, client):
    with pytest.raises(ValueError, match="non-empty"):
        await handler.wp_menu_set(menu_id=3, items=[], name="   ")
    client.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_menu_set_relays_server_forbidden_object_id(handler, client):
    """S-22 enforcement is server-side; client just relays the envelope."""
    client.put = AsyncMock(  # type: ignore[method-assign]
        return_value={"code": "forbidden_object_id", "status": 403}
    )
    handler.client = client
    result = await handler.wp_menu_set(
        menu_id=3,
        items=[{"type": "post_type", "object": "post", "object_id": 999}],
    )
    assert result == {"code": "forbidden_object_id", "status": 403}


# ───── Widget routing ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_widget_areas_list_calls_route(handler, client):
    await handler.wp_widget_areas_list()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/widgets/areas",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_widget_get_calls_route(handler, client):
    await handler.wp_widget_get(area_id="sidebar-1")
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/widgets/sidebar-1",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_widget_get_rejects_empty_area_id(handler, client):
    with pytest.raises(ValueError, match="area_id"):
        await handler.wp_widget_get(area_id="")
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_widget_set_strips_caller_kind(handler, client):
    """Caller-side ``kind`` is ignored — area kind is set by the area."""
    await handler.wp_widget_set(
        area_id="sidebar-1",
        widgets=[
            {
                "type": "block",
                "raw": "<!-- wp:paragraph -->Hi<!-- /wp:paragraph -->",
                "kind": "block",
            }
        ],
    )
    args, kwargs = client.put.call_args
    body = kwargs["json_data"]
    assert "kind" not in body["widgets"][0], "caller kind must not be relayed"
    assert body["widgets"][0]["type"] == "block"
    assert "raw" in body["widgets"][0]


@pytest.mark.asyncio
async def test_widget_set_passes_full_block_widget(handler, client):
    await handler.wp_widget_set(
        area_id="sidebar-1",
        widgets=[{"type": "block", "raw": "<!-- wp:paragraph -->X<!-- /wp:paragraph -->"}],
    )
    client.put.assert_awaited_once_with(
        "airano-mcp/v1/admin/widgets/sidebar-1",
        json_data={
            "widgets": [{"type": "block", "raw": "<!-- wp:paragraph -->X<!-- /wp:paragraph -->"}]
        },
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_widget_set_rejects_non_list_widgets(handler, client):
    with pytest.raises(ValueError, match="widgets must be a list"):
        await handler.wp_widget_set(area_id="sidebar-1", widgets={"wrong": "shape"})  # type: ignore[arg-type]
    client.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_widget_set_relays_unsupported_legacy_widget_envelope(handler, client):
    """Server returns unsupported_legacy_widget; client relays untouched."""
    client.put = AsyncMock(  # type: ignore[method-assign]
        return_value={"code": "unsupported_legacy_widget", "status": 400}
    )
    handler.client = client
    result = await handler.wp_widget_set(
        area_id="legacy-sidebar",
        widgets=[{"type": "recent-posts", "settings": {"title": "Recent"}}],
    )
    assert result == {"code": "unsupported_legacy_widget", "status": 400}


# ───── Customizer routing ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_customizer_get_calls_route(handler, client):
    await handler.wp_customizer_changeset(action="get")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/customizer/changeset",
        json_data={"action": "get"},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_customizer_apply_includes_action_in_body(handler, client):
    await handler.wp_customizer_changeset(action="apply")
    args, kwargs = client.post.call_args
    assert kwargs["json_data"] == {"action": "apply"}


@pytest.mark.asyncio
async def test_customizer_discard_includes_action_in_body(handler, client):
    await handler.wp_customizer_changeset(action="discard")
    args, kwargs = client.post.call_args
    assert kwargs["json_data"] == {"action": "discard"}


@pytest.mark.asyncio
async def test_customizer_rejects_bad_action(handler, client):
    with pytest.raises(ValueError, match="action must be one of"):
        await handler.wp_customizer_changeset(action="apply_now")
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_customizer_relays_s24_forbidden_envelope(handler, client):
    """S-24 customize cap missing — server returns 403; client relays."""
    client.post = AsyncMock(  # type: ignore[method-assign]
        return_value={"code": "rest_forbidden", "status": 403}
    )
    handler.client = client
    result = await handler.wp_customizer_changeset(action="apply")
    assert result == {"code": "rest_forbidden", "status": 403}


@pytest.mark.asyncio
async def test_customizer_relays_empty_changeset_envelope(handler, client):
    """Server maps no-pending-changeset to {status: empty} 200."""
    client.post = AsyncMock(  # type: ignore[method-assign]
        return_value={"status": "empty", "changeset": None}
    )
    handler.client = client
    result = await handler.wp_customizer_changeset(action="get")
    assert result == {"status": "empty", "changeset": None}
