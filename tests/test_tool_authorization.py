"""Focused tests for the shared authorization decision service."""

import pytest

from core.tool_authorization import authorize_tool_call, resolve_required_scope
from core.tool_policy import EndpointContext, Principal, SiteContext
from core.tool_registry import ToolDefinition, ToolRegistry


async def _noop(**_kwargs):
    return None


def _contexts(scope="read"):
    return {
        "principal": Principal(
            authentication_type="bearer",
            principal_id_safe="user-1",
            granted_scopes=[scope],
            site_ids=["site-1"],
        ),
        "endpoint": EndpointContext(name="user", kind="user"),
        "site": SiteContext(site_id="site-1", plugin_type="wordpress", alias="main"),
    }


def test_resolve_required_scope_uses_registry_and_system_map(monkeypatch):
    registry = ToolRegistry()
    tool = ToolDefinition(
        name="wordpress_specialist_wp_theme_activate",
        description="activate",
        handler=_noop,
        plugin_type="wordpress_specialist",
        required_scope="editor",
    )
    registry.register(tool)
    monkeypatch.setattr("core.tool_registry.get_tool_registry", lambda: registry)

    assert (
        resolve_required_scope("mcp__wordpress_specialist__wordpress_specialist_wp_theme_activate")
        == "editor"
    )
    assert resolve_required_scope("get_system_metrics") == "read"


def test_resolve_required_scope_fails_closed_for_unknown_tool(monkeypatch):
    registry = ToolRegistry()
    monkeypatch.setattr("core.tool_registry.get_tool_registry", lambda: registry)

    with pytest.raises(ValueError):
        resolve_required_scope("wordpress_update_posts_but_unknown")


@pytest.mark.asyncio
async def test_authorization_uses_tool_required_scope_not_name_heuristics():
    tool = ToolDefinition(
        name="wordpress_update_posts_but_read_only",
        description="read",
        handler=_noop,
        plugin_type="wordpress",
        required_scope="read",
    )

    decision = await authorize_tool_call(
        tool_definition=tool,
        **_contexts("read"),
        arguments={},
    )

    assert decision.allow is True
    assert decision.required_scope == "read"


@pytest.mark.asyncio
async def test_authorization_denies_plugin_and_site_mismatch():
    tool = ToolDefinition(
        name="wordpress_list_posts",
        description="read",
        handler=_noop,
        plugin_type="woocommerce",
        required_scope="read",
    )
    contexts = _contexts("read")
    contexts["site"] = SiteContext(site_id="site-2", plugin_type="wordpress")

    decision = await authorize_tool_call(
        tool_definition=tool,
        **contexts,
        arguments={},
    )

    assert decision.allow is False
    assert decision.reason_code == "PLUGIN_MISMATCH"
