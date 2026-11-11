"""Registry-driven tool registration + consistent MCP annotations everywhere.

Pins two fixes:

* Registration loops over the plugin registry. Registering a plugin in
  ``plugins/__init__.py`` is enough for its tools to exist — the old
  hand-written per-plugin passes could be forgotten (Gmail once shipped
  advertising 0 tools that way).
* Every FastMCP endpoint emits the same title/readOnly/destructive/idempotent
  hints as the per-user endpoint, from one module.
"""

from __future__ import annotations

import pytest

from core.site_manager import SiteManager
from core.tool_annotations import ADDITIVE_TOOLS, is_destructive, tool_annotations
from core.tool_generator import ToolGenerator
from core.tool_registration import register_all_plugin_tools
from core.tool_registry import ToolDefinition, ToolRegistry
from plugins import registry as plugin_registry
from plugins.base import BasePlugin, PluginRegistry

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def full_registry() -> tuple[ToolRegistry, dict[str, int]]:
    reg = ToolRegistry()
    counts = register_all_plugin_tools(ToolGenerator(SiteManager()), reg, plugin_registry)
    return reg, counts


# ------------------------------------------------------------ registration


def test_every_registered_plugin_produces_tools(full_registry):
    _, counts = full_registry
    assert set(counts) == set(plugin_registry.get_registered_types())
    empty = [p for p, n in counts.items() if n == 0]
    assert empty == [], f"plugins registered but advertising 0 tools: {empty}"


def test_total_matches_sum_of_specs(full_registry):
    reg, counts = full_registry
    assert reg.get_count() == sum(counts.values())
    for plugin_type, n in counts.items():
        specs = plugin_registry.get_plugin_class(plugin_type).get_tool_specifications()
        assert n == len(specs), plugin_type


def test_new_plugin_needs_no_server_change():
    """A newly registered plugin's tools appear with zero extra wiring."""

    class FakePlugin(BasePlugin):
        @staticmethod
        def get_tool_specifications():
            return [
                {
                    "name": "ping",
                    "method_name": "ping",
                    "description": "Ping",
                    "schema": {"type": "object", "properties": {}},
                    "scope": "read",
                }
            ]

    class BrokenPlugin(BasePlugin):
        @staticmethod
        def get_tool_specifications():
            raise RuntimeError("boom")

    preg = PluginRegistry()
    preg.register("broken", BrokenPlugin)
    preg.register("fake", FakePlugin)
    reg = ToolRegistry()
    counts = register_all_plugin_tools(ToolGenerator(SiteManager()), reg, preg)
    assert counts["fake"] == 1
    assert counts["broken"] == 0  # one failing plugin never blocks the others
    assert reg.get_by_name("fake_ping") is not None


def test_get_plugin_class_unknown_raises():
    with pytest.raises(ValueError):
        PluginRegistry().get_plugin_class("nope")


# ------------------------------------------------------------- annotations


def test_additive_allowlist_entries_exist_and_are_writes(full_registry):
    reg, _ = full_registry
    for name in sorted(ADDITIVE_TOOLS):
        tool = reg.get_by_name(name)
        assert tool is not None, f"ADDITIVE_TOOLS lists unknown tool {name}"
        assert tool.required_scope != "read", f"{name} is read-only; remove it from the list"


def test_every_tool_annotation_is_consistent(full_registry):
    reg, _ = full_registry
    for tool in reg.get_all():
        ann = tool_annotations(tool)
        assert ann["title"]
        if tool.required_scope == "read":
            assert ann["readOnlyHint"] is True
            assert "destructiveHint" not in ann
        else:
            assert ann["readOnlyHint"] is False
            assert isinstance(ann["destructiveHint"], bool)
            assert isinstance(ann["idempotentHint"], bool)


def _tool(name: str, scope: str, **extra) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=name,
        input_schema={"type": "object", "properties": {}},
        handler=lambda **_: None,
        required_scope=scope,
        plugin_type=name.split("_", 1)[0],
        **extra,
    )


def test_delete_tools_are_destructive_and_creates_are_not():
    assert is_destructive(_tool("wordpress_delete_post", "admin")) is True
    assert is_destructive(_tool("wordpress_update_post", "write")) is True
    assert is_destructive(_tool("wordpress_create_post", "write")) is False


def test_explicit_spec_value_wins_over_allowlist():
    assert is_destructive(_tool("wordpress_create_post", "write", destructive=True)) is True
    assert is_destructive(_tool("gitea_merge_pull_request", "write", destructive=False)) is False


def test_spec_destructive_flows_through_generator():
    class P:
        @staticmethod
        def get_tool_specifications():
            return [
                {
                    "name": "wipe",
                    "method_name": "wipe",
                    "description": "Wipe",
                    "schema": {"type": "object", "properties": {}},
                    "scope": "admin",
                    "destructive": True,
                }
            ]

    (tool,) = ToolGenerator(SiteManager()).generate_tools(P, "x")
    assert tool.destructive is True
    assert tool_annotations(tool)["destructiveHint"] is True


async def test_fastmcp_endpoints_emit_annotations(full_registry):
    """The FastMCP path (/mcp, /{plugin}/mcp) carries the same hints."""
    from fastmcp import FastMCP
    from server import register_tool_on

    reg, _ = full_registry
    mcp = FastMCP("annotation-test")
    picked = [reg.get_by_name("wordpress_list_posts"), reg.get_by_name("wordpress_delete_post")]
    for tool_def in picked:
        register_tool_on(mcp, tool_def)

    listed = {t.name: t for t in await mcp.list_tools()}
    read = listed["wordpress_list_posts"]
    assert read.annotations.readOnlyHint is True
    assert read.title == "WordPress: List posts"
    delete = listed["wordpress_delete_post"]
    assert delete.annotations.readOnlyHint is False
    assert delete.annotations.destructiveHint is True
