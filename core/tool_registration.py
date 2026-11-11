"""Generate and register every plugin's tools in one pass.

Before this module, ``server.register_project_tools`` had one hand-written
``generate_tools`` + register block per plugin. Registering a plugin in
``plugins/__init__.py`` was not enough — a plugin whose block was forgotten
was instantiable for ``tools/call`` but advertised **0 tools** on every
endpoint (this shipped once for Gmail). Looping over the plugin registry
makes registration the single source of truth.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.tool_generator import ToolGenerator
    from core.tool_registry import ToolRegistry
    from plugins.base import PluginRegistry

logger = logging.getLogger(__name__)


def register_all_plugin_tools(
    tool_generator: ToolGenerator,
    tool_registry: ToolRegistry,
    plugin_registry: PluginRegistry,
) -> dict[str, int]:
    """Generate tools for every registered plugin type and register them.

    One plugin failing to generate never blocks the others.

    Returns:
        Mapping of plugin type -> number of tools registered for it.
    """
    counts: dict[str, int] = {}
    for plugin_type in plugin_registry.get_registered_types():
        plugin_class = plugin_registry.get_plugin_class(plugin_type)
        try:
            tools = tool_generator.generate_tools(plugin_class, plugin_type)
        except Exception as e:  # noqa: BLE001 - isolate per-plugin failures
            logger.error("Failed to generate %s tools: %s", plugin_type, e, exc_info=True)
            counts[plugin_type] = 0
            continue

        registered = 0
        for tool_def in tools:
            try:
                tool_registry.register(tool_def)
                registered += 1
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to register %s tool %s: %s", plugin_type, tool_def.name, e)
        counts[plugin_type] = registered
        if registered == 0:
            logger.warning("Plugin %s registered but produced 0 tools", plugin_type)
        else:
            logger.info("Registered %d %s tools", registered, plugin_type)
    return counts
