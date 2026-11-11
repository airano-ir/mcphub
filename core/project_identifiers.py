"""Canonical parsing for plugin/project identifiers."""

from dataclasses import dataclass


class IdentifierParseError(ValueError):
    """Raised when a project identifier cannot be normalized safely."""


@dataclass(frozen=True)
class ParsedIdentifier:
    plugin_type: str
    identifier: str


def normalize_tool_name(value: str) -> str:
    """Remove the optional FastMCP namespace from a tool name."""
    if not isinstance(value, str) or not value:
        raise IdentifierParseError("tool name must be a non-empty string")
    if value.startswith("mcp__") and "__" in value[5:]:
        return value.split("__", 2)[-1]
    return value


def _registered_plugin_types() -> tuple[str, ...]:
    from plugins import registry

    return tuple(sorted(registry.get_registered_types(), key=len, reverse=True))


def parse_tool_identifier(value: str) -> ParsedIdentifier:
    """Parse ``{plugin_type}_{identifier}`` using longest-prefix matching."""
    value = normalize_tool_name(value)

    for plugin_type in _registered_plugin_types():
        prefix = f"{plugin_type}_"
        if value.startswith(prefix):
            identifier = value[len(prefix) :]
            if not identifier:
                raise IdentifierParseError("identifier after plugin prefix is empty")
            return ParsedIdentifier(plugin_type=plugin_type, identifier=identifier)

    raise IdentifierParseError(f"unknown plugin type in identifier: {value}")


def plugin_type_for_tool(value: str) -> str | None:
    """Return the registered plugin type for a tool, or ``None`` for system tools."""
    try:
        return parse_tool_identifier(value).plugin_type
    except IdentifierParseError:
        return None
