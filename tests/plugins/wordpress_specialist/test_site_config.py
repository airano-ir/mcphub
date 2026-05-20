"""F.19.6.A — Tests for the WordPress Specialist site config handler.

Mocks ``WordPressClient.get`` / ``post`` and asserts:

* tool spec contract: 6 tools split read (3) + settings (3)
* each handler method targets the correct ``airano-mcp/v1/admin/*``
  route with ``use_custom_namespace=True``
* client-side guards reject bad permalink structure shapes (S-18-style
  cheap pre-check) + bad enum values (show_on_front) + posts_per_page
  out of bounds
* setters refuse calls with no fields supplied (must update at least one)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.site_config import (
    SiteConfigHandler,
    _validate_permalink_structure,
    get_tool_specifications,
)

# ───── Tool spec contract ────────────────────────────────────────────


def test_tool_specs_count_and_names_match_f196a():
    specs = get_tool_specifications()
    assert len(specs) == 6, "F.19.6.A advertises 3 read + 3 settings"
    names = {s["name"] for s in specs}
    assert names == {
        "wp_site_identity_get",
        "wp_site_identity_set",
        "wp_reading_settings_get",
        "wp_reading_settings_set",
        "wp_permalinks_get",
        "wp_permalinks_set",
    }


def test_read_settings_tier_split():
    """Reads at scope=read, writes at scope=settings (the new tier)."""
    specs_by_name = {s["name"]: s for s in get_tool_specifications()}
    expected_scope = {
        "wp_site_identity_get": "read",
        "wp_reading_settings_get": "read",
        "wp_permalinks_get": "read",
        "wp_site_identity_set": "settings",
        "wp_reading_settings_set": "settings",
        "wp_permalinks_set": "settings",
    }
    for name, scope in expected_scope.items():
        assert specs_by_name[name]["scope"] == scope, f"{name} should be scope={scope}"


def test_every_spec_has_the_full_contract():
    for spec in get_tool_specifications():
        assert spec["name"] == spec["method_name"]
        assert spec["description"]
        assert isinstance(spec["schema"], dict)
        assert spec["schema"].get("type") == "object"


# ───── Permalink structure validator ─────────────────────────────────


@pytest.mark.parametrize(
    "good",
    [
        "",  # plain permalinks
        "/%postname%/",
        "/%year%/%monthnum%/%postname%/",
        "/%category%/%postname%/",
        "/blog/%postname%/",
        "/posts/%post_id%-%postname%",
    ],
)
def test_validate_permalink_structure_accepts(good):
    assert _validate_permalink_structure(good) == good


@pytest.mark.parametrize(
    "bad",
    [
        None,
        42,
        "/%postname%/\x00",  # null byte
        "/" + ("a" * 300),  # too long
        "/%postname%/<script>",  # angle brackets
        "/?p=N",  # ? not allowed in our cheap pre-check
    ],
)
def test_validate_permalink_structure_rejects(bad):
    with pytest.raises(ValueError):
        _validate_permalink_structure(bad)


# ───── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.get = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.post = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return SiteConfigHandler(client)


# ───── Identity routing ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_identity_get_calls_identity_route(handler, client):
    await handler.wp_site_identity_get()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/site/identity",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_identity_set_passes_subset(handler, client):
    await handler.wp_site_identity_set(title="Hello", site_icon_id=42)
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/site/identity",
        json_data={"title": "Hello", "site_icon_id": 42},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_identity_set_clears_logo_when_zero(handler, client):
    await handler.wp_site_identity_set(custom_logo_id=0)
    args, kwargs = client.post.call_args
    assert kwargs["json_data"] == {"custom_logo_id": 0}


@pytest.mark.asyncio
async def test_identity_set_rejects_empty_call(handler, client):
    with pytest.raises(ValueError, match="at least one field"):
        await handler.wp_site_identity_set()
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_identity_set_rejects_negative_attachment_id(handler, client):
    with pytest.raises(ValueError, match="non-negative"):
        await handler.wp_site_identity_set(site_icon_id=-1)
    client.post.assert_not_awaited()


# ───── Reading routing ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reading_get_calls_reading_route(handler, client):
    await handler.wp_reading_settings_get()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/site/reading",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_reading_set_passes_subset(handler, client):
    await handler.wp_reading_settings_set(show_on_front="page", page_on_front=12, posts_per_page=20)
    args, kwargs = client.post.call_args
    assert kwargs["json_data"] == {
        "show_on_front": "page",
        "page_on_front": 12,
        "posts_per_page": 20,
    }


@pytest.mark.asyncio
async def test_reading_set_rejects_bad_show_on_front(handler, client):
    with pytest.raises(ValueError, match="show_on_front"):
        await handler.wp_reading_settings_set(show_on_front="archive")
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_reading_set_rejects_oversized_posts_per_page(handler, client):
    with pytest.raises(ValueError, match="between 1 and 100"):
        await handler.wp_reading_settings_set(posts_per_page=500)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_reading_set_passes_blog_public_bool(handler, client):
    await handler.wp_reading_settings_set(blog_public=False)
    args, kwargs = client.post.call_args
    assert kwargs["json_data"] == {"blog_public": False}


@pytest.mark.asyncio
async def test_reading_set_rejects_empty_call(handler, client):
    with pytest.raises(ValueError, match="at least one field"):
        await handler.wp_reading_settings_set()
    client.post.assert_not_awaited()


# ───── Permalinks routing ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_permalinks_get_calls_route(handler, client):
    await handler.wp_permalinks_get()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/permalinks",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_permalinks_set_passes_structure(handler, client):
    await handler.wp_permalinks_set(structure="/%postname%/")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/permalinks",
        json_data={"structure": "/%postname%/"},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_permalinks_set_passes_category_and_tag_base(handler, client):
    await handler.wp_permalinks_set(
        structure="/%postname%/", category_base="topics", tag_base="labels"
    )
    args, kwargs = client.post.call_args
    assert kwargs["json_data"] == {
        "structure": "/%postname%/",
        "category_base": "topics",
        "tag_base": "labels",
    }


@pytest.mark.asyncio
async def test_permalinks_set_accepts_plain_empty_structure(handler, client):
    await handler.wp_permalinks_set(structure="")
    args, kwargs = client.post.call_args
    assert kwargs["json_data"] == {"structure": ""}


@pytest.mark.asyncio
async def test_permalinks_set_rejects_bad_structure(handler, client):
    with pytest.raises(ValueError):
        await handler.wp_permalinks_set(structure="/?p=N")  # ? not allowed
    client.post.assert_not_awaited()
