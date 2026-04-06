"""Tool access manager — site-scoped visibility and per-site toggles (F.7b).

Provides a central pipeline that filters the set of MCP tools presented for
a user endpoint based on:

1. **Scope → category mapping.** Every ``ToolDefinition`` carries a
   ``category`` field (e.g. ``read``, ``lifecycle``, ``crud``, ``system``).
   An API key's declared scopes **and** the site's stored ``tool_scope``
   preset each map to a set of allowed categories via
   :data:`SCOPE_TO_CATEGORIES`. A tool is visible only if its category is in
   the intersection — the narrower of the two layers wins.
2. **Per-site tool toggles.** Site owners may explicitly disable specific
   tools via the ``site_tool_toggles`` table. Only overrides are stored —
   tools without an entry are enabled by default.

Tools whose ``category`` is not in :data:`KNOWN_CATEGORIES` are **always
visible** (backward compatibility — legacy plugins that have not been
annotated yet default to ``category="read"``, which belongs to the ``read``
scope set anyway, but an unknown value would be preserved).

The ``tool_scope`` value ``"custom"`` is a sentinel meaning "do not apply a
site-level preset filter" — in that case only the per-tool toggles and the
key scope are considered.

Usage::

    from core.tool_access import get_tool_access_manager

    mgr = get_tool_access_manager()
    visible = await mgr.get_visible_tools(
        site_id=site["id"],
        key_scopes=["read"],
        plugin_type="coolify",
    )
"""

from __future__ import annotations

import logging
from typing import Any

from core.tool_registry import ToolDefinition

logger = logging.getLogger(__name__)


# Mapping from scope → set of tool categories that scope may see.
# Used for BOTH API-key scopes and per-site ``tool_scope`` presets.
# Scopes are additive: presenting multiple scopes yields the union.
SCOPE_TO_CATEGORIES: dict[str, set[str]] = {
    "read": {"read"},
    "read:sensitive": {"read", "read_sensitive", "backup"},
    "deploy": {"read", "lifecycle"},
    "write": {"read", "lifecycle", "crud", "env"},
    "admin": {
        "read",
        "read_sensitive",
        "lifecycle",
        "crud",
        "env",
        "backup",
        "system",
    },
}

# All known categories — any tool whose category is outside this set is
# treated as "always visible" for backward compatibility.
KNOWN_CATEGORIES: set[str] = {
    "read",
    "read_sensitive",
    "lifecycle",
    "crud",
    "env",
    "backup",
    "system",
}

# Sentinel meaning "no site-level preset filter — use per-tool toggles only".
SCOPE_CUSTOM = "custom"


def scopes_to_categories(scopes: list[str]) -> set[str]:
    """Return the union of categories allowed by the given scope list.

    Args:
        scopes: List of scope strings as presented on the API key / token.

    Returns:
        Set of category names the scopes collectively allow.
    """
    allowed: set[str] = set()
    for scope in scopes:
        allowed |= SCOPE_TO_CATEGORIES.get(scope.strip(), set())
    return allowed


class ToolAccessManager:
    """Central manager for scope-based visibility and per-site tool toggles."""

    def apply_scope_filter(
        self,
        tools: list[ToolDefinition],
        scopes: list[str],
    ) -> list[ToolDefinition]:
        """Drop tools whose category is not allowed by the presented scopes.

        Tools with an unknown category (e.g. legacy plugins not yet annotated)
        are always kept — backward compatibility.

        Args:
            tools: Candidate tool list.
            scopes: Scopes presented on the API key (or a single-element list
                containing a site's ``tool_scope`` preset).

        Returns:
            Filtered tool list.
        """
        allowed = scopes_to_categories(scopes)
        if not allowed:
            # No recognised scopes — preserve legacy behaviour and return
            # only tools with unknown categories.
            return [t for t in tools if t.category not in KNOWN_CATEGORIES]

        result: list[ToolDefinition] = []
        for tool in tools:
            if tool.category not in KNOWN_CATEGORIES:
                result.append(tool)
                continue
            if tool.category in allowed:
                result.append(tool)
        return result

    async def apply_site_toggles(
        self,
        tools: list[ToolDefinition],
        site_id: str,
    ) -> list[ToolDefinition]:
        """Drop tools the site owner has explicitly disabled.

        Args:
            tools: Candidate tool list.
            site_id: Site UUID.

        Returns:
            Filtered tool list.
        """
        from core.database import get_database

        try:
            db = get_database()
        except RuntimeError:
            return tools

        toggles = await db.get_site_tool_toggles(site_id)
        if not toggles:
            return tools
        return [t for t in tools if toggles.get(t.name, True)]

    async def get_visible_tools(
        self,
        site_id: str,
        key_scopes: list[str],
        plugin_type: str,
    ) -> list[ToolDefinition]:
        """Return the visible tool list for a site on a given plugin.

        Pipeline:
            1. ``ToolRegistry.get_by_plugin_type``
            2. Key-scope filter (API key's declared scopes)
            3. Site-scope filter (site's stored ``tool_scope`` preset,
               skipped when it is ``custom``)
            4. Per-site toggle filter (``site_tool_toggles``)

        Args:
            site_id: Site UUID (the MCP endpoint alias resolves to this).
            key_scopes: Scopes presented on the API key / token.
            plugin_type: Plugin type (e.g. ``coolify``).

        Returns:
            List of visible ``ToolDefinition`` objects.
        """
        from core.database import get_database
        from core.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools = registry.get_by_plugin_type(plugin_type)

        tools = self.apply_scope_filter(tools, key_scopes)

        try:
            db = get_database()
            site_scope = await db.get_site_tool_scope(site_id)
        except RuntimeError:
            site_scope = "admin"

        if site_scope and site_scope != SCOPE_CUSTOM:
            tools = self.apply_scope_filter(tools, [site_scope])

        tools = await self.apply_site_toggles(tools, site_id)
        return tools

    async def toggle_tool(
        self,
        site_id: str,
        tool_name: str,
        enabled: bool,
        reason: str | None = None,
    ) -> None:
        """Enable or disable a single tool for a site.

        Args:
            site_id: Site UUID.
            tool_name: Fully-qualified tool name.
            enabled: True to enable, False to disable.
            reason: Optional note.
        """
        from core.database import get_database

        db = get_database()
        await db.set_site_tool_toggle(site_id, tool_name, enabled, reason)
        logger.info(
            "site %s toggled %s → %s",
            site_id,
            tool_name,
            "enabled" if enabled else "disabled",
        )

    async def bulk_toggle_by_scope(
        self,
        site_id: str,
        scope_name: str,
        enabled: bool,
        plugin_type: str | None = None,
    ) -> int:
        """Toggle every tool whose category belongs to the given scope.

        Only the *exclusive* category set of the scope is affected — i.e.
        the categories explicitly listed under ``SCOPE_TO_CATEGORIES[scope_name]``.
        Tools outside those categories are left unchanged.

        Args:
            site_id: Site UUID.
            scope_name: Scope key (``"read"``, ``"deploy"``, ...).
            enabled: True to enable, False to disable.
            plugin_type: Optional filter — only affect tools from this plugin.
                When ``None`` every plugin's tools in that category are touched.

        Returns:
            Number of tools affected.
        """
        from core.database import get_database
        from core.tool_registry import get_tool_registry

        categories = SCOPE_TO_CATEGORIES.get(scope_name)
        if categories is None:
            raise ValueError(f"Unknown scope '{scope_name}'")

        registry = get_tool_registry()
        candidates = registry.get_all()
        if plugin_type is not None:
            candidates = [t for t in candidates if t.plugin_type == plugin_type]
        affected = [t.name for t in candidates if t.category in categories]

        if not affected:
            return 0

        db = get_database()
        await db.bulk_set_site_tool_toggles(
            site_id,
            [(name, enabled) for name in affected],
            reason=f"bulk:{scope_name}",
        )
        return len(affected)

    async def list_tools_for_site(
        self,
        site_id: str,
        plugin_type: str,
    ) -> list[dict[str, Any]]:
        """Return every tool for a plugin, annotated with per-site toggle state.

        Used by the dashboard API to present the per-site management view.
        Does not apply scope filters — the UI decides what to show.

        Args:
            site_id: Site UUID.
            plugin_type: Plugin type.

        Returns:
            List of dicts with tool metadata + ``enabled`` flag.
        """
        from core.database import get_database
        from core.tool_registry import get_tool_registry

        try:
            db = get_database()
            toggles = await db.get_site_tool_toggles(site_id)
        except RuntimeError:
            toggles = {}

        registry = get_tool_registry()
        tools = registry.get_by_plugin_type(plugin_type)
        return [
            {
                "name": t.name,
                "description": t.description,
                "plugin_type": t.plugin_type,
                "category": t.category,
                "sensitivity": t.sensitivity,
                "required_scope": t.required_scope,
                "enabled": toggles.get(t.name, True),
            }
            for t in tools
        ]


# Singleton
_manager: ToolAccessManager | None = None


def get_tool_access_manager() -> ToolAccessManager:
    """Return the singleton :class:`ToolAccessManager`."""
    global _manager
    if _manager is None:
        _manager = ToolAccessManager()
    return _manager
