"""Tool access manager — site-scoped visibility and per-site toggles (F.7c).

Provides a central pipeline that filters the set of MCP tools presented for
a user endpoint based on:

1. **Universal scope tiers.** A 3-level system (``read`` / ``write`` /
   ``admin``) that works across ALL plugins using the tool's
   ``required_scope`` field.  For Coolify (which has fine-grained
   ``category`` annotations) the legacy category mapping is kept as an
   overlay for the ``custom`` preset.
2. **Per-site tool toggles.** Site owners may explicitly disable specific
   tools via the ``site_tool_toggles`` table.  Only overrides are stored —
   tools without an entry are enabled by default.

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


# ── Universal 3-tier scope system (F.7c) ─────────────────────────────
# Maps a scope tier to the set of ``required_scope`` values it may access.
# Works for ALL plugins because every tool has ``required_scope``.
UNIVERSAL_SCOPE_TIERS: dict[str, set[str]] = {
    "read": {"read"},
    "write": {"read", "write"},
    "admin": {"read", "write", "admin"},
}

# ── Legacy Coolify category mapping (kept for ``custom`` overlay) ─────
# Mapping from scope → set of tool categories that scope may see.
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

# All known Coolify categories.
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

# Plugins that have fine-grained category annotations.
_CATEGORY_PLUGINS: set[str] = {"coolify"}


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


def _scopes_to_required(scopes: list[str]) -> set[str]:
    """Return the union of ``required_scope`` values allowed by universal tiers."""
    allowed: set[str] = set()
    for scope in scopes:
        allowed |= UNIVERSAL_SCOPE_TIERS.get(scope.strip(), set())
    return allowed


def get_scope_presets_for_plugin(plugin_type: str) -> list[dict[str, str]]:
    """Return the appropriate scope presets for a plugin type (F.7d).

    Each preset is a dict with ``value`` (the canonical scope key persisted
    to ``sites.tool_scope``), ``label`` / ``label_fa`` (button title), and
    ``hint`` / ``hint_fa`` (one-line description shown under the title).

    The valid scope values are constrained by ``_VALID_TOOL_SCOPES`` in
    ``core.dashboard.routes`` — currently:
    ``{"read", "read:sensitive", "deploy", "write", "admin", "custom"}``.
    """
    custom = {
        "value": "custom",
        "label": "Custom",
        "label_fa": "سفارشی",
        "hint": "Per-tool toggles",
        "hint_fa": "هر ابزار جداگانه",
    }

    if plugin_type == "coolify":
        # 5 fine-grained Coolify tiers + custom (matches SCOPE_TO_CATEGORIES).
        return [
            {
                "value": "read",
                "label": "Read",
                "label_fa": "خواندن",
                "hint": "List/inspect resources",
                "hint_fa": "مشاهده و فهرست منابع",
            },
            {
                "value": "read:sensitive",
                "label": "Read + Secrets",
                "label_fa": "خواندن + اسرار",
                "hint": "Includes env vars and backups",
                "hint_fa": "شامل متغیرهای محیطی و بکاپ",
            },
            {
                "value": "deploy",
                "label": "Deploy",
                "label_fa": "استقرار",
                "hint": "Read + lifecycle (start/stop/restart)",
                "hint_fa": "مشاهده + راه‌اندازی/توقف/ریستارت",
            },
            {
                "value": "write",
                "label": "Write",
                "label_fa": "نوشتن",
                "hint": "Read + lifecycle + CRUD + env",
                "hint_fa": "مشاهده + لایفسایکل + CRUD + env",
            },
            {
                "value": "admin",
                "label": "Root",
                "label_fa": "روت",
                "hint": "Everything including system commands",
                "hint_fa": "همه چیز شامل دستورات سیستم",
            },
            custom,
        ]

    if plugin_type == "openpanel":
        return [
            {
                "value": "read",
                "label": "Read",
                "label_fa": "خواندن",
                "hint": "Export current project only",
                "hint_fa": "خروجی پروژه فعلی",
            },
            {
                "value": "write",
                "label": "Write",
                "label_fa": "نوشتن",
                "hint": "Default ingestion (track events)",
                "hint_fa": "ارسال رویداد (ingestion)",
            },
            {
                "value": "admin",
                "label": "Root",
                "label_fa": "روت",
                "hint": "Export any project",
                "hint_fa": "خروجی هر پروژه",
            },
            custom,
        ]

    if plugin_type == "woocommerce":
        # WooCommerce has no admin-scope tools (read=14, write=14, admin=0),
        # so Write and "Read + Write" tiers are identical. Present a single
        # full-access tier instead of two duplicates.
        return [
            {
                "value": "read",
                "label": "Read Only",
                "label_fa": "فقط خواندن",
                "hint": "Browse products, orders, customers",
                "hint_fa": "مشاهده محصولات، سفارش‌ها و مشتریان",
            },
            {
                "value": "admin",
                "label": "Read + Write",
                "label_fa": "خواندن + نوشتن",
                "hint": "Full store management (all 28 tools)",
                "hint_fa": "مدیریت کامل فروشگاه (همه ۲۸ ابزار)",
            },
            custom,
        ]

    if plugin_type in {"wordpress", "wordpress_advanced"}:
        # WordPress has no admin-scope tools (read=27, write=40, admin=0).
        # SEO + plugin/theme tools require the Airano MCP SEO Bridge plugin
        # to be installed on the WP site itself. Present 2 tiers + custom.
        return [
            {
                "value": "read",
                "label": "Read Only",
                "label_fa": "فقط خواندن",
                "hint": "View posts, pages, media",
                "hint_fa": "مشاهده نوشته‌ها، صفحات و رسانه",
            },
            {
                "value": "admin",
                "label": "Full Access",
                "label_fa": "دسترسی کامل",
                "hint": "All tools (CRUD + SEO via add-on)",
                "hint_fa": "همه ابزارها (CRUD و SEO با افزونه)",
            },
            custom,
        ]

    if plugin_type == "gitea":
        return [
            {
                "value": "read",
                "label": "Read",
                "label_fa": "خواندن",
                "hint": "Browse repos, issues, users",
                "hint_fa": "مشاهده مخازن، ایشوها، کاربران",
            },
            {
                "value": "write",
                "label": "Read + Write",
                "label_fa": "خواندن + نوشتن",
                "hint": "Create issues, PRs, branches",
                "hint_fa": "ایجاد ایشو، PR و شاخه",
            },
            {
                "value": "admin",
                "label": "Admin",
                "label_fa": "مدیر",
                "hint": "Repo + org + user admin",
                "hint_fa": "مدیریت مخزن، سازمان و کاربر",
            },
            custom,
        ]

    # Universal default for all other plugins.
    return [
        {
            "value": "read",
            "label": "Read",
            "label_fa": "فقط خواندن",
            "hint": "View only",
            "hint_fa": "فقط مشاهده",
        },
        {
            "value": "write",
            "label": "Read + Write",
            "label_fa": "خواندن + نوشتن",
            "hint": "CRUD ops",
            "hint_fa": "عملیات CRUD",
        },
        {
            "value": "admin",
            "label": "Full Access",
            "label_fa": "دسترسی کامل",
            "hint": "All tools",
            "hint_fa": "همه ابزارها",
        },
        custom,
    ]


class ToolAccessManager:
    """Central manager for scope-based visibility and per-site tool toggles."""

    def apply_scope_filter(
        self,
        tools: list[ToolDefinition],
        scopes: list[str],
        plugin_type: str | None = None,
    ) -> list[ToolDefinition]:
        """Drop tools not allowed by the presented scopes.

        For plugins with category annotations (Coolify) the legacy
        category-based filter is used.  For all other plugins the universal
        3-tier filter based on ``required_scope`` is applied.

        Args:
            tools: Candidate tool list.
            scopes: Scopes presented on the API key (or a single-element list
                containing a site's ``tool_scope`` preset).
            plugin_type: Plugin type hint.  When provided and the plugin is
                NOT in ``_CATEGORY_PLUGINS``, the universal tier filter is
                used.

        Returns:
            Filtered tool list.
        """
        # Try universal tiers first (works for all plugins)
        allowed_scopes = _scopes_to_required(scopes)

        if allowed_scopes and (plugin_type is None or plugin_type not in _CATEGORY_PLUGINS):
            # Universal filter: match tool.required_scope against allowed tiers
            return [t for t in tools if t.required_scope in allowed_scopes]

        # Fallback: legacy category-based filter for Coolify / custom scopes
        allowed = scopes_to_categories(scopes)
        if not allowed:
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

        tools = self.apply_scope_filter(tools, key_scopes, plugin_type=plugin_type)

        try:
            db = get_database()
            site_scope = await db.get_site_tool_scope(site_id)
        except RuntimeError:
            site_scope = "admin"

        if site_scope and site_scope != SCOPE_CUSTOM:
            tools = self.apply_scope_filter(tools, [site_scope], plugin_type=plugin_type)

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
