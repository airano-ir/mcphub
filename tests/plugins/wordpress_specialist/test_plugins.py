"""F.19.2.1 — Tests for the WordPress Specialist plugin write handler.

Mocks ``WordPressClient.post`` / ``delete`` and asserts:

* tool spec contract: 6 tools (4 install-tier + 2 admin-tier), with
  the install/admin tier split matching the F.19.2.0 ladder
* each handler method targets the correct ``airano-mcp/v1/admin/*``
  route with ``use_custom_namespace=True``
* client-side guards reject malformed slugs (S-15), oversized zip
  payloads (S-18), and the mutually-exclusive zip_url / zip_base64
  contract on install_from_zip
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.plugins import (
    PluginsHandler,
    _validate_plugin_slug,
    get_tool_specifications,
)

# ───── Tool spec contract ────────────────────────────────────────────


def test_tool_specs_count_and_names_match_f1921():
    specs = get_tool_specifications()
    assert len(specs) == 6, "F.19.2.1 advertises 4 install-tier + 2 admin-tier"
    names = {s["name"] for s in specs}
    assert names == {
        "wp_plugin_install_from_slug",
        "wp_plugin_install_from_zip",
        "wp_plugin_activate",
        "wp_plugin_deactivate",
        "wp_plugin_update",
        "wp_plugin_delete",
    }


def test_install_admin_tier_split_matches_risk_class():
    """install tier = wp.org curated; admin tier = arbitrary zip + delete."""
    specs_by_name = {s["name"]: s for s in get_tool_specifications()}
    expected_scope = {
        "wp_plugin_install_from_slug": "install",
        "wp_plugin_activate": "install",
        "wp_plugin_deactivate": "install",
        "wp_plugin_update": "install",
        "wp_plugin_install_from_zip": "admin",
        "wp_plugin_delete": "admin",
    }
    for name, scope in expected_scope.items():
        assert specs_by_name[name]["scope"] == scope, f"{name} should be scope={scope}"


def test_every_spec_has_the_full_contract():
    for spec in get_tool_specifications():
        assert spec["name"] == spec["method_name"]
        assert spec["description"]
        assert isinstance(spec["schema"], dict)
        assert spec["schema"].get("type") == "object"


# ───── Slug validation (S-15 client-side) ────────────────────────────


@pytest.mark.parametrize(
    "good",
    ["akismet", "woocommerce", "yoast-seo", "wp_super_cache", "P1"],
)
def test_validate_plugin_slug_accepts_well_formed(good):
    assert _validate_plugin_slug(good) == good


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../etc",
        "slug.with.dot",
        "-leading-dash",
        "slug with spaces",
        "x" * 65,
        None,
        42,
    ],
)
def test_validate_plugin_slug_rejects_malformed(bad):
    with pytest.raises(ValueError):
        _validate_plugin_slug(bad)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("woocommerce/woocommerce.php", "woocommerce"),
        ("airano-mcp-bridge/airano-mcp-bridge.php", "airano-mcp-bridge"),
        ("akismet/akismet.php", "akismet"),
        ("  woocommerce/woocommerce.php  ", "woocommerce"),
    ],
)
def test_validate_plugin_slug_normalizes_folder_file_form(raw, expected):
    """Capabilities probe returns ``folder/file.php`` — normalise to folder."""
    assert _validate_plugin_slug(raw) == expected


# ───── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.post = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.delete = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return PluginsHandler(client)


# ───── Install-tier routing ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_install_from_slug_routes_to_install(handler, client):
    await handler.wp_plugin_install_from_slug(slug="akismet", activate=True)
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/plugins/install",
        json_data={"slug": "akismet", "activate": True},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_install_from_slug_rejects_bad_slug(handler, client):
    with pytest.raises(ValueError):
        await handler.wp_plugin_install_from_slug(slug="../etc")
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_activate_calls_activate_route(handler, client):
    await handler.wp_plugin_activate(slug="akismet")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/plugins/akismet/activate",
        json_data={"network_wide": False},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_activate_passes_network_wide_when_true(handler, client):
    await handler.wp_plugin_activate(slug="akismet", network_wide=True)
    args, kwargs = client.post.call_args
    assert kwargs["json_data"]["network_wide"] is True


@pytest.mark.asyncio
async def test_deactivate_calls_deactivate_route(handler, client):
    await handler.wp_plugin_deactivate(slug="akismet")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/plugins/akismet/deactivate",
        json_data={"network_wide": False},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_update_calls_update_route(handler, client):
    await handler.wp_plugin_update(slug="akismet")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/plugins/akismet/update",
        json_data={},
        use_custom_namespace=True,
    )


# ───── Admin-tier routing ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_install_from_zip_url_routes_to_install(handler, client):
    await handler.wp_plugin_install_from_zip(
        zip_url="https://example.com/plugin.zip", activate=True, overwrite=False
    )
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/plugins/install",
        json_data={
            "zip_url": "https://example.com/plugin.zip",
            "activate": True,
            "overwrite": False,
        },
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_install_from_zip_base64_routes_to_install(handler, client):
    payload = base64.b64encode(b"PK\x03\x04 fake plugin zip").decode()
    await handler.wp_plugin_install_from_zip(zip_base64=payload, overwrite=True)
    args, kwargs = client.post.call_args
    assert kwargs["json_data"]["zip_base64"] == payload
    assert kwargs["json_data"]["overwrite"] is True
    assert "zip_url" not in kwargs["json_data"]


@pytest.mark.asyncio
async def test_install_from_zip_requires_one_of_url_or_base64(handler, client):
    with pytest.raises(ValueError, match="zip_url or zip_base64"):
        await handler.wp_plugin_install_from_zip()
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_from_zip_rejects_both_url_and_base64(handler, client):
    with pytest.raises(ValueError, match="not both"):
        await handler.wp_plugin_install_from_zip(
            zip_url="https://example.com/x.zip", zip_base64="aGVsbG8="
        )
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_from_zip_rejects_oversized_payload(handler, client):
    huge = "A" * (70 * 1024 * 1024)  # > 50 MB after b64 decode upper bound
    with pytest.raises(ValueError, match=r"exceeds .* byte cap \(S-18\)"):
        await handler.wp_plugin_install_from_zip(zip_base64=huge)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_calls_delete_route(handler, client):
    await handler.wp_plugin_delete(slug="oldplugin")
    client.delete.assert_awaited_once_with(
        "airano-mcp/v1/admin/plugins/oldplugin",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_delete_rejects_bad_slug(handler, client):
    with pytest.raises(ValueError):
        await handler.wp_plugin_delete(slug="../etc")
    client.delete.assert_not_awaited()
