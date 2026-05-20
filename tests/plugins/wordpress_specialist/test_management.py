"""F.19.1 — Tests for the WordPress Specialist read-only management handler.

Mocks ``WordPressClient.get`` and asserts:
  * tool spec shape (name + scope + schema present, no leakage of write
    operations into this iteration)
  * each handler method targets the correct ``airano-mcp/v1/admin/*``
    route with ``use_custom_namespace=True``
  * the option-name client-side guard rejects path-traversal / null-byte
    payloads before any request goes to the wire
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.management import (
    ManagementHandler,
    get_tool_specifications,
)

# ---------- Tool spec contract ----------


def test_tool_specs_are_all_read_scope():
    """F.19.1 + F.19.3.1 ship read-only tools — assert nothing snuck into write/admin."""
    specs = get_tool_specifications()
    assert len(specs) == 9, "F.19.1 (6) + F.19.3.1 ports (3) advertise nine read tools"
    names = {s["name"] for s in specs}
    assert names == {
        # F.19.1
        "wp_plugin_list",
        "wp_theme_list",
        "wp_user_list",
        "wp_option_get",
        "wp_cron_list",
        "wp_maintenance_status",
        # F.19.3.1 system info ports (companion v2.12.0+)
        "wp_system_info",
        "wp_php_info",
        "wp_disk_usage",
    }
    for spec in specs:
        assert spec["scope"] == "read", f"{spec['name']} scope must be read"
        assert spec["method_name"] == spec["name"]
        assert "description" in spec and spec["description"]
        assert "schema" in spec and isinstance(spec["schema"], dict)


def test_user_list_schema_supports_role_search_pagination():
    spec = next(s for s in get_tool_specifications() if s["name"] == "wp_user_list")
    props = spec["schema"]["properties"]
    assert {"role", "search", "page", "per_page"} <= set(props.keys())
    assert props["per_page"]["maximum"] == 200


def test_option_get_schema_requires_name():
    spec = next(s for s in get_tool_specifications() if s["name"] == "wp_option_get")
    assert spec["schema"].get("required") == ["name"]


# ---------- Handler routing ----------


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.get = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return ManagementHandler(client)


@pytest.mark.asyncio
async def test_wp_plugin_list_calls_admin_plugins_route(handler, client):
    await handler.wp_plugin_list()
    client.get.assert_awaited_once_with("airano-mcp/v1/admin/plugins", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_wp_theme_list_calls_admin_themes_route(handler, client):
    await handler.wp_theme_list()
    client.get.assert_awaited_once_with("airano-mcp/v1/admin/themes", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_wp_user_list_passes_pagination_and_filters(handler, client):
    await handler.wp_user_list(role="editor", search="alice", page=2, per_page=25)
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/users",
        params={"page": 2, "per_page": 25, "role": "editor", "search": "alice"},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_wp_user_list_omits_optional_filters_when_unset(handler, client):
    await handler.wp_user_list()
    args, kwargs = client.get.call_args
    assert args[0] == "airano-mcp/v1/admin/users"
    assert kwargs["use_custom_namespace"] is True
    assert kwargs["params"] == {"page": 1, "per_page": 50}


@pytest.mark.asyncio
async def test_wp_option_get_calls_named_route(handler, client):
    await handler.wp_option_get(name="blogname")
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/options/blogname", use_custom_namespace=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_name",
    [
        "../../../etc/passwd",
        "foo/bar",
        "secret\x00key",
    ],
)
async def test_wp_option_get_rejects_suspicious_names_before_wire(handler, client, bad_name):
    with pytest.raises(ValueError, match="suspicious"):
        await handler.wp_option_get(name=bad_name)
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_wp_option_get_requires_non_empty_name(handler, client):
    with pytest.raises(ValueError, match="non-empty"):
        await handler.wp_option_get(name="")
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_wp_cron_list_calls_admin_cron_route(handler, client):
    await handler.wp_cron_list()
    client.get.assert_awaited_once_with("airano-mcp/v1/admin/cron", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_wp_maintenance_status_calls_admin_maintenance_route(handler, client):
    await handler.wp_maintenance_status()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/maintenance", use_custom_namespace=True
    )


# F.19.3.1 system info ports (companion v2.12.0+)


@pytest.mark.asyncio
async def test_wp_system_info_calls_admin_system_info_route(handler, client):
    await handler.wp_system_info()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/system-info", use_custom_namespace=True
    )


@pytest.mark.asyncio
async def test_wp_php_info_calls_admin_phpinfo_route(handler, client):
    await handler.wp_php_info()
    client.get.assert_awaited_once_with("airano-mcp/v1/admin/phpinfo", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_wp_disk_usage_calls_admin_disk_usage_route(handler, client):
    await handler.wp_disk_usage()
    client.get.assert_awaited_once_with("airano-mcp/v1/admin/disk-usage", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_handler_returns_companion_response_unchanged(handler, client):
    payload = {
        "plugins": [{"file": "x/x.php", "name": "X", "active": True}],
        "total": 1,
        "active_count": 1,
        "multisite": False,
    }
    client.get = AsyncMock(return_value=payload)  # type: ignore[method-assign]
    handler.client = client
    result = await handler.wp_plugin_list()
    assert result is payload, "Handler must not reshape the companion payload in F.19.1"
