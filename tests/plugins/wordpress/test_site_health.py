"""F.18.6 — Tests for wordpress_site_health."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.site_health import (
    SiteHealthHandler,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return SiteHealthHandler(wp_client)


@pytest.fixture
def companion_payload():
    return {
        "ok": True,
        "wordpress": {
            "version": "6.5.3",
            "multisite": False,
            "home_url": "https://wp.example.com",
            "site_url": "https://wp.example.com",
            "language": "en_US",
            "timezone": "UTC",
            "rest_enabled": True,
            "application_passwords_available": True,
            "debug_mode": False,
            "https_home": True,
        },
        "php": {
            "version": "8.1.27",
            "memory_limit": "256M",
            "max_execution_time": "30",
            "upload_max_filesize": "64M",
            "post_max_size": "128M",
            "max_input_vars": 1000,
            "extensions": ["curl", "gd", "json", "mbstring", "xml"],
            "has_mbstring": True,
            "has_curl": True,
            "has_gd": True,
            "has_imagick": False,
            "has_intl": True,
        },
        "server": {
            "software": "nginx/1.25.3",
            "disk_free_bytes": 123456789,
            "disk_total_bytes": 999999999,
        },
        "database": {
            "version": "10.5.15",
            "server_info": "10.5.15-MariaDB",
            "charset": "utf8mb4",
            "collate": "utf8mb4_unicode_ci",
            "prefix": "wp_",
        },
        "plugins": {
            "total_count": 20,
            "active_count": 12,
            "active": [
                {
                    "file": "airano-mcp-bridge/airano-mcp-bridge.php",
                    "name": "Airano MCP Bridge for WordPress",
                    "version": "2.6.0",
                }
            ],
            "must_use_count": 2,
        },
        "theme": {
            "active": {
                "name": "Twenty Twenty-Four",
                "version": "1.1",
                "stylesheet": "twentytwentyfour",
            },
            "parent": None,
            "total_count": 3,
        },
        "checks": {
            "writable_wp_content": True,
            "writable_uploads": True,
            "ssl_enabled": True,
        },
        "companion": {
            "plugin_version": "2.6.0",
            "routes": {
                "seo_meta": True,
                "site_health": True,
                "audit_hook": False,
            },
            "features": {
                "rank_math": True,
                "yoast": False,
                "woocommerce": False,
            },
        },
        "generated_at_gmt": "2026-04-15T09:00:00Z",
        "plugin_version": "2.6.0",
    }


@pytest.mark.asyncio
async def test_happy_path(handler, wp_client, monkeypatch, companion_payload):
    get_mock = AsyncMock(return_value=companion_payload)
    monkeypatch.setattr(wp_client, "get", get_mock)

    out = json.loads(await handler.site_health())
    assert out["ok"] is True
    assert out["companion_available"] is True
    assert out["wordpress"]["version"] == "6.5.3"
    assert out["php"]["version"] == "8.1.27"
    assert out["database"]["charset"] == "utf8mb4"
    assert out["plugins"]["active_count"] == 12
    assert out["theme"]["active"]["name"] == "Twenty Twenty-Four"
    assert out["checks"]["writable_uploads"] is True
    assert out["companion"]["plugin_version"] == "2.6.0"

    get_mock.assert_called_once_with(
        "airano-mcp/v1/site-health",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_companion_unreachable_falls_back(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=RuntimeError("404 Not Found")))

    out = json.loads(await handler.site_health())
    assert out["ok"] is False
    assert out["companion_available"] is False
    assert out["error"] == "companion_unreachable"
    assert "wordpress_get_site_health" in out["hint"]
    assert "manage_options" in out["hint"]


@pytest.mark.asyncio
async def test_non_dict_response(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "get", AsyncMock(return_value=["not", "a", "dict"]))
    out = json.loads(await handler.site_health())
    assert out["ok"] is False
    assert out["error"] == "invalid_response"
    assert out["companion_available"] is False


@pytest.mark.asyncio
async def test_ok_inferred_when_payload_omits_it(handler, wp_client, monkeypatch):
    """Older plugin builds might not set `ok`; derive it from presence/no-error."""
    payload = {
        "wordpress": {"version": "6.4"},
        "php": {"version": "8.0"},
        "plugin_version": "2.6.0",
    }
    monkeypatch.setattr(wp_client, "get", AsyncMock(return_value=payload))

    out = json.loads(await handler.site_health())
    assert out["ok"] is True
    assert out["companion_available"] is True
    assert out["wordpress"]["version"] == "6.4"


def test_tool_spec_is_read_scope():
    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "site_health"
    assert specs[0]["scope"] == "read"
