"""MCP tool annotations emitted by the per-user endpoint tools/list.

Verifies that _tools_to_mcp_schema attaches spec-compliant annotations
(title, readOnlyHint, and idempotentHint for write tools) derived from
authoritative ToolDefinition fields — required for AI-client safety hints
and the Claude connector directory.
"""

from __future__ import annotations

import pytest

from core.tool_registry import ToolDefinition
from core.user_endpoints import _tool_annotations, _tools_to_mcp_schema


def _tool(name: str, scope: str, plugin: str = "wordpress", idempotent: bool = False):
    return ToolDefinition(
        name=name,
        description=f"[UNIFIED] {name}",
        input_schema={"type": "object", "properties": {"site": {"type": "string"}}},
        handler=lambda **_: None,
        required_scope=scope,
        plugin_type=plugin,
        idempotent=idempotent,
    )


@pytest.mark.unit
def test_read_tool_is_read_only_with_title():
    ann = _tool_annotations(_tool("wordpress_list_posts", "read"))
    assert ann["readOnlyHint"] is True
    assert ann["title"] == "WordPress: List posts"
    # idempotentHint is only emitted for non-read tools
    assert "idempotentHint" not in ann


@pytest.mark.unit
def test_write_tool_is_not_read_only():
    ann = _tool_annotations(_tool("wordpress_create_post", "write"))
    assert ann["readOnlyHint"] is False
    assert ann["idempotentHint"] is False
    assert ann["title"] == "WordPress: Create post"


@pytest.mark.unit
def test_idempotent_write_tool():
    ann = _tool_annotations(_tool("gitea_update_file", "write", plugin="gitea", idempotent=True))
    assert ann["readOnlyHint"] is False
    assert ann["idempotentHint"] is True
    assert ann["title"] == "Gitea: Update file"


@pytest.mark.unit
def test_specialist_prefix_maps_to_wordpress():
    ann = _tool_annotations(
        _tool("wordpress_specialist_wp_db_size", "read", plugin="wordpress_specialist")
    )
    assert ann["title"].startswith("WordPress:")
    assert ann["readOnlyHint"] is True


@pytest.mark.unit
def test_schema_entries_carry_annotations():
    tools = [
        _tool("wordpress_list_posts", "read"),
        _tool("wordpress_delete_post", "admin"),
    ]
    out = _tools_to_mcp_schema(tools)
    assert all("annotations" in t for t in out)
    assert all({"name", "description", "inputSchema"} <= set(t) for t in out)
    by_name = {t["name"]: t for t in out}
    assert by_name["wordpress_list_posts"]["annotations"]["readOnlyHint"] is True
    assert by_name["wordpress_delete_post"]["annotations"]["readOnlyHint"] is False
    # site param still stripped
    assert "site" not in by_name["wordpress_list_posts"]["inputSchema"].get("properties", {})
