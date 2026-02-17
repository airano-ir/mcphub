"""
Tool Registry - Central tool management for MCP

Manages tool definitions with type safety and validation.
Part of Option B clean architecture refactoring.
"""

import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ToolDefinition(BaseModel):
    """
    Type-safe tool definition.

    Represents a single MCP tool with all necessary metadata.

    Attributes:
        name: Unique tool identifier (e.g., "wordpress_get_post")
        description: Human-readable tool description
        input_schema: JSON Schema for tool parameters
        handler: Async function that executes the tool
        required_scope: Required API key scope ("read", "write", "admin")
        plugin_type: Plugin type this tool belongs to (e.g., "wordpress")
    """

    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Tool description")
    input_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema for parameters",
    )
    handler: Callable = Field(..., description="Async handler function")
    required_scope: str = Field(
        default="read", description="Required API key scope (read/write/admin)"
    )
    plugin_type: str = Field(..., description="Plugin type (wordpress, gitea, etc)")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow Callable type


class ToolRegistry:
    """
    Central registry for all MCP tools.

    Manages tool registration, retrieval, and validation.
    Ensures unique tool names and provides filtering by plugin type.

    Examples:
        >>> registry = ToolRegistry()
        >>> tool = ToolDefinition(
        ...     name="wordpress_list_posts",
        ...     description="List WordPress posts",
        ...     handler=async_handler_func,
        ...     plugin_type="wordpress"
        ... )
        >>> registry.register(tool)
        >>> all_tools = registry.get_all()
        >>> wp_tools = registry.get_by_plugin_type("wordpress")
    """

    def __init__(self):
        """Initialize empty tool registry."""
        self.tools: dict[str, ToolDefinition] = {}
        self.logger = logging.getLogger("ToolRegistry")
        self.logger.info("ToolRegistry initialized")

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: Tool definition to register

        Raises:
            ValueError: If tool name already exists

        Examples:
            >>> registry.register(tool_definition)
        """
        if tool.name in self.tools:
            raise ValueError(f"Tool '{tool.name}' already registered")

        self.tools[tool.name] = tool
        self.logger.debug(f"Registered tool: {tool.name} ({tool.plugin_type})")

    def register_many(self, tools: list[ToolDefinition]) -> int:
        """
        Register multiple tools at once.

        Args:
            tools: List of tool definitions

        Returns:
            Number of tools successfully registered

        Examples:
            >>> count = registry.register_many([tool1, tool2, tool3])
            >>> print(f"Registered {count} tools")
        """
        count = 0
        for tool in tools:
            try:
                self.register(tool)
                count += 1
            except ValueError as e:
                self.logger.warning(f"Skipped duplicate tool: {e}")
            except Exception as e:
                self.logger.error(f"Failed to register tool: {e}", exc_info=True)

        self.logger.info(f"Registered {count}/{len(tools)} tools")
        return count

    def get_all(self) -> list[ToolDefinition]:
        """
        Get all registered tools.

        Returns:
            List of all tool definitions

        Examples:
            >>> tools = registry.get_all()
            >>> print(f"Total tools: {len(tools)}")
        """
        return list(self.tools.values())

    def get_by_name(self, name: str) -> ToolDefinition | None:
        """
        Get a tool by its name.

        Args:
            name: Tool name

        Returns:
            Tool definition if found, None otherwise

        Examples:
            >>> tool = registry.get_by_name("wordpress_get_post")
            >>> if tool:
            ...     print(f"Found: {tool.description}")
        """
        return self.tools.get(name)

    def get_by_plugin_type(self, plugin_type: str) -> list[ToolDefinition]:
        """
        Get all tools for a specific plugin type.

        Args:
            plugin_type: Plugin type (e.g., "wordpress", "gitea")

        Returns:
            List of tools for the specified plugin type

        Examples:
            >>> wp_tools = registry.get_by_plugin_type("wordpress")
            >>> print(f"WordPress tools: {len(wp_tools)}")
        """
        return [tool for tool in self.tools.values() if tool.plugin_type == plugin_type]

    def get_count(self) -> int:
        """
        Get total number of registered tools.

        Returns:
            Count of registered tools

        Examples:
            >>> count = registry.get_count()
        """
        return len(self.tools)

    def get_count_by_plugin(self) -> dict[str, int]:
        """
        Get tool counts grouped by plugin type.

        Returns:
            Dictionary mapping plugin type to tool count

        Examples:
            >>> counts = registry.get_count_by_plugin()
            >>> print(counts)  # {'wordpress': 95, 'gitea': 50}
        """
        counts = {}
        for tool in self.tools.values():
            plugin_type = tool.plugin_type
            counts[plugin_type] = counts.get(plugin_type, 0) + 1
        return counts

    def clear(self) -> None:
        """
        Clear all registered tools.

        Primarily for testing purposes.

        Examples:
            >>> registry.clear()
            >>> assert registry.get_count() == 0
        """
        self.tools.clear()
        self.logger.info("Tool registry cleared")

    def __repr__(self) -> str:
        """String representation of registry."""
        counts = self.get_count_by_plugin()
        counts_str = ", ".join(f"{k}: {v}" for k, v in counts.items())
        return f"ToolRegistry(total={self.get_count()}, {counts_str})"


# Singleton instance
_tool_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the singleton tool registry instance.

    Returns:
        Global ToolRegistry instance

    Examples:
        >>> registry = get_tool_registry()
        >>> registry.register(tool)
    """
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
