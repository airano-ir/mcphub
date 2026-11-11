"""Regression tests for canonical identifiers in generated MCP endpoints."""

from __future__ import annotations

from core.endpoints.config import EndpointConfig, EndpointType
from core.endpoints.factory import MCPEndpointFactory


def _factory_without_dependencies() -> MCPEndpointFactory:
    """Build only the pure factory surface used by these tests."""
    return MCPEndpointFactory.__new__(MCPEndpointFactory)


def test_factory_classifies_registered_plugin_names_via_canonical_parser() -> None:
    factory = _factory_without_dependencies()

    assert factory._extract_plugin_type("woocommerce_list_products") == "woocommerce"
    assert (
        factory._extract_plugin_type("mcp__mcp-hub__wordpress_specialist_wp_theme_list")
        == "wordpress_specialist"
    )
    assert factory._extract_plugin_type("unknown_tool") is None


async def test_factory_injects_identifier_suffix_without_underscore_heuristic() -> None:
    factory = _factory_without_dependencies()
    captured: dict[str, str] = {}

    async def handler(**kwargs):
        captured.update(kwargs)
        return "ok"

    config = EndpointConfig(
        path="/project/wp-specialist-site-1",
        name="Project",
        description="Project endpoint",
        endpoint_type=EndpointType.PROJECT,
        plugin_types=["wordpress_specialist"],
        site_filter="wordpress_specialist_site_1",
    )

    wrapped = factory._wrap_handler(handler, "wordpress_specialist_wp_theme_list", config)
    assert await wrapped() == "ok"
    assert captured["site"] == "site_1"
