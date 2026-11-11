"""Reproducible inventory for the WordPress-family tool surfaces."""

import ast
from collections.abc import Callable
from pathlib import Path

from core.endpoints.config import ENDPOINT_CONFIGS, EndpointType
from core.tool_authorization import _SYSTEM_TOOL_SCOPES
from core.tool_generator import ToolGenerator
from core.tool_registry import ToolDefinition, ToolRegistry
from plugins.woocommerce.plugin import WooCommercePlugin
from plugins.wordpress.plugin import WordPressPlugin
from plugins.wordpress_specialist.plugin import WordPressSpecialistPlugin

TARGET_PLUGINS: dict[str, type] = {
    "wordpress": WordPressPlugin,
    "woocommerce": WooCommercePlugin,
    "wordpress_specialist": WordPressSpecialistPlugin,
}

EXPECTED_COUNTS = {
    "wordpress": 86,
    "woocommerce": 38,
    "wordpress_specialist": 59,
}


def _server_system_tool_names() -> set[str]:
    """Extract the top-level system tools registered by the active server."""
    source = (Path(__file__).parents[1] / "server.py").read_text()
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(ast.unparse(dec).startswith("mcp.tool") for dec in node.decorator_list):
            names.add(node.name)
    return names


class _InventorySiteManager:
    """Minimal site-manager surface needed by ``ToolGenerator``."""

    sites: dict[str, list[dict[str, str]]] = {}

    def list_sites(self, plugin_type: str) -> list[str]:
        return []


def _build_inventory() -> tuple[ToolRegistry, dict[str, list[ToolDefinition]]]:
    registry = ToolRegistry()
    generator = ToolGenerator(_InventorySiteManager())
    generated: dict[str, list[ToolDefinition]] = {}

    for plugin_type, plugin_class in TARGET_PLUGINS.items():
        tools = generator.generate_tools(plugin_class, plugin_type)
        generated[plugin_type] = tools
        registry.register_many(tools)

    return registry, generated


def test_target_plugin_inventory_matches_current_baseline() -> None:
    """Keep the measured target-surface counts reproducible during migration."""
    registry, generated = _build_inventory()

    assert {plugin: len(tools) for plugin, tools in generated.items()} == EXPECTED_COUNTS
    assert registry.get_count() == sum(EXPECTED_COUNTS.values())
    assert registry.get_count_by_plugin() == EXPECTED_COUNTS


def test_target_inventory_has_unique_names_and_known_plugin_types() -> None:
    """Every generated target tool has a complete, unambiguous definition."""
    registry, generated = _build_inventory()
    names = [tool.name for tool in registry.get_all()]

    assert len(names) == len(set(names))
    assert {tool.plugin_type for tool in registry.get_all()} == set(TARGET_PLUGINS)
    for plugin_type, tools in generated.items():
        assert all(tool.plugin_type == plugin_type for tool in tools)
        assert all(isinstance(tool.handler, Callable) for tool in tools)
        assert all(tool.description for tool in tools)
        assert all(tool.input_schema.get("type") == "object" for tool in tools)


def test_target_specs_have_required_source_fields() -> None:
    """The source specs can be converted without silently dropping identity fields."""
    for plugin_type, plugin_class in TARGET_PLUGINS.items():
        specs = plugin_class.get_tool_specifications()
        assert len(specs) == EXPECTED_COUNTS[plugin_type]
        assert all(
            {"name", "method_name", "description", "schema"}.issubset(spec) for spec in specs
        )
        assert len({spec["name"] for spec in specs}) == len(specs)


def test_system_tool_inventory_matches_every_authorization_surface() -> None:
    """All active system tools must be covered by every explicit system map."""
    active = _server_system_tool_names()
    configured = set(ENDPOINT_CONFIGS[EndpointType.SYSTEM].tool_whitelist or set())

    assert active == set(_SYSTEM_TOOL_SCOPES)
    assert active == configured
