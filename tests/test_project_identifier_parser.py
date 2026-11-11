"""Table-driven tests for canonical project/plugin identifier parsing."""

import pytest

from core.project_identifiers import IdentifierParseError, parse_tool_identifier


@pytest.mark.parametrize(
    ("value", "plugin_type", "identifier"),
    [
        ("wordpress_site1", "wordpress", "site1"),
        ("woocommerce_store_main", "woocommerce", "store_main"),
        ("wordpress_specialist_site_a_b", "wordpress_specialist", "site_a_b"),
    ],
)
def test_parse_longest_registered_plugin_prefix(value, plugin_type, identifier):
    parsed = parse_tool_identifier(value)

    assert parsed.plugin_type == plugin_type
    assert parsed.identifier == identifier


@pytest.mark.parametrize("value", ["", "unknown_site1", "wordpress_"])
def test_parse_rejects_unknown_or_empty_identifiers(value):
    with pytest.raises(IdentifierParseError):
        parse_tool_identifier(value)
