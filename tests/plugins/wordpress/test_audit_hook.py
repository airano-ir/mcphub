"""F.18.7 — Tests for wordpress audit-hook tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.audit_hook import (
    SUPPORTED_EVENTS,
    AuditHookHandler,
    _validate_configure,
    get_tool_specifications,
)


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def handler(wp_client):
    return AuditHookHandler(wp_client)


class TestValidateConfigure:
    def test_all_none_ok(self):
        assert (
            _validate_configure(endpoint_url=None, secret=None, enabled=None, events=None) is None
        )

    def test_https_ok(self):
        assert (
            _validate_configure(
                endpoint_url="https://mcp.example.com/api/companion-audit",
                secret=None,
                enabled=None,
                events=None,
            )
            is None
        )

    def test_non_url_rejected(self):
        err = _validate_configure(
            endpoint_url="not-a-url",
            secret=None,
            enabled=None,
            events=None,
        )
        assert err is not None
        assert err["error"] == "invalid_endpoint_url"

    def test_short_secret_rejected(self):
        err = _validate_configure(
            endpoint_url=None,
            secret="short",
            enabled=None,
            events=None,
        )
        assert err is not None
        assert err["error"] == "secret_too_short"

    def test_empty_secret_allowed_to_clear(self):
        assert _validate_configure(endpoint_url=None, secret="", enabled=None, events=None) is None

    def test_unknown_event_rejected(self):
        err = _validate_configure(
            endpoint_url=None,
            secret=None,
            enabled=None,
            events=["transition_post_status", "bogus"],
        )
        assert err is not None
        assert err["error"] == "unknown_event"
        assert "supported" in err

    def test_non_list_events_rejected(self):
        err = _validate_configure(
            endpoint_url=None,
            secret=None,
            enabled=None,
            events="not a list",
        )
        assert err is not None
        assert err["error"] == "invalid_events"

    def test_non_bool_enabled_rejected(self):
        err = _validate_configure(
            endpoint_url=None,
            secret=None,
            enabled="yes",
            events=None,
        )
        assert err is not None
        assert err["error"] == "invalid_enabled"


@pytest.mark.asyncio
async def test_status_happy_path(handler, wp_client, monkeypatch):
    companion_response = {
        "enabled": True,
        "endpoint_url": "https://mcp.example.com/api/companion-audit",
        "secret_set": True,
        "secret_last4": "abcd",
        "events": list(SUPPORTED_EVENTS),
        "last_push_gmt": "2026-04-15T09:00:00Z",
        "failure_count": 0,
        "last_error": "",
        "plugin_version": "2.7.0",
    }
    get_mock = AsyncMock(return_value=companion_response)
    monkeypatch.setattr(wp_client, "get", get_mock)

    out = json.loads(await handler.audit_hook_status())
    assert out["ok"] is True
    assert out["enabled"] is True
    assert out["secret_last4"] == "abcd"
    assert out["failure_count"] == 0

    get_mock.assert_called_once_with("airano-mcp/v1/audit-hook", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_status_unreachable(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=RuntimeError("404 Not Found")))
    out = json.loads(await handler.audit_hook_status())
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"


@pytest.mark.asyncio
async def test_configure_happy_path(handler, wp_client, monkeypatch):
    captured: dict = {}

    async def fake_post(endpoint, json_data=None, **kwargs):
        captured["endpoint"] = endpoint
        captured["body"] = json_data
        return {
            "enabled": True,
            "endpoint_url": "https://mcp.example.com/api/companion-audit",
            "secret_set": True,
            "secret_last4": "wxyz",
            "events": ["transition_post_status"],
            "failure_count": 0,
        }

    monkeypatch.setattr(wp_client, "post", AsyncMock(side_effect=fake_post))

    out = json.loads(
        await handler.audit_hook_configure(
            endpoint_url="https://mcp.example.com/api/companion-audit",
            secret="a" * 32,
            enabled=True,
            events=["transition_post_status"],
        )
    )
    assert out["ok"] is True
    assert captured["endpoint"] == "airano-mcp/v1/audit-hook"
    assert captured["body"]["endpoint_url"] == "https://mcp.example.com/api/companion-audit"
    assert captured["body"]["secret"] == "a" * 32
    assert captured["body"]["enabled"] is True
    assert captured["body"]["events"] == ["transition_post_status"]


@pytest.mark.asyncio
async def test_configure_rejects_short_secret_without_network(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)
    out = json.loads(await handler.audit_hook_configure(secret="short"))
    assert out["ok"] is False
    assert out["error"] == "secret_too_short"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_configure_no_fields_rejected(handler, wp_client, monkeypatch):
    post_mock = AsyncMock()
    monkeypatch.setattr(wp_client, "post", post_mock)
    out = json.loads(await handler.audit_hook_configure())
    assert out["ok"] is False
    assert out["error"] == "no_fields"
    post_mock.assert_not_called()


@pytest.mark.asyncio
async def test_disable_calls_delete(handler, wp_client, monkeypatch):
    del_mock = AsyncMock(
        return_value={
            "enabled": False,
            "endpoint_url": "",
            "secret_set": False,
            "cleared": True,
            "plugin_version": "2.7.0",
        }
    )
    monkeypatch.setattr(wp_client, "delete", del_mock)

    out = json.loads(await handler.audit_hook_disable())
    assert out["ok"] is True
    assert out["cleared"] is True

    del_mock.assert_called_once_with("airano-mcp/v1/audit-hook", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_disable_unreachable(handler, wp_client, monkeypatch):
    monkeypatch.setattr(wp_client, "delete", AsyncMock(side_effect=RuntimeError("boom")))
    out = json.loads(await handler.audit_hook_disable())
    assert out["ok"] is False
    assert out["error"] == "companion_unreachable"


def test_tool_specs_shape():
    specs = get_tool_specifications()
    assert len(specs) == 3
    names = {s["name"] for s in specs}
    assert names == {"audit_hook_status", "audit_hook_configure", "audit_hook_disable"}
    scopes = {s["name"]: s["scope"] for s in specs}
    assert scopes["audit_hook_status"] == "read"
    assert scopes["audit_hook_configure"] == "admin"
    assert scopes["audit_hook_disable"] == "admin"
