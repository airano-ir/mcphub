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
        # F.X.fix-pass3: filter out tools whose central prerequisites
        # are unmet (no AI provider key, missing companion route,
        # missing SEO plugin) so the live endpoint never advertises a
        # tool that would 100% fail at call time.
        tools = await self.apply_prerequisites_filter(tools, site_id)
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

        F.X.fix #8: each row also carries ``provider_key_required`` and
        ``provider_key_configured`` so the Tool Access template can
        render AI tools greyed + "Configure key" CTA when the site has
        no keys for the required provider, instead of letting the user
        enable a tool that errors at call time with ``NO_PROVIDER_KEY``.

        F.X.fix-pass3: rows also carry ``available`` + ``unavailable_reason``
        derived from a central :data:`_TOOL_PREREQUISITES` resolver so
        the UI can auto-grey/disable tools whose requirements (companion
        route, SEO plugin, AI key) the site doesn't satisfy. This is the
        same data the live MCP endpoint uses to silently filter the
        catalog (see :meth:`get_visible_tools`).

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

        try:
            from core.site_api import list_site_providers_set

            configured_providers = await list_site_providers_set(site_id)
        except Exception:  # noqa: BLE001
            configured_providers = set()

        # F.X.fix-pass3: pull the cached probe payload so we can
        # evaluate prerequisites for SEO / companion-route tools.
        # ``probe_site_capabilities`` reuses its 10-min cache so the
        # cost is one SQLite query in the common path.
        probe_payload: dict[str, Any] | None = None
        try:
            from core.capability_probe import get_probe_cache

            cached = get_probe_cache().get(site_id)
            if cached is not None:
                probe_payload = cached
        except Exception:  # noqa: BLE001
            probe_payload = None

        registry = get_tool_registry()
        tools = registry.get_by_plugin_type(plugin_type)
        rows: list[dict[str, Any]] = []
        for t in tools:
            available, reason = check_tool_prerequisites(
                t.name,
                probe_payload=probe_payload,
                configured_providers=configured_providers,
            )
            rows.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "plugin_type": t.plugin_type,
                    "category": t.category,
                    "sensitivity": t.sensitivity,
                    "required_scope": t.required_scope,
                    "enabled": toggles.get(t.name, True),
                    "provider_key_required": _tool_requires_provider_key(t.name),
                    "provider_key_configured": _tool_has_configured_provider(
                        t.name, configured_providers
                    ),
                    "available": available,
                    "unavailable_reason": reason,
                }
            )
        return rows

    async def apply_prerequisites_filter(
        self,
        tools: list[ToolDefinition],
        site_id: str,
    ) -> list[ToolDefinition]:
        """Drop tools whose central prerequisites are not satisfied.

        Mirrors :meth:`list_tools_for_site` but returns ``ToolDefinition``
        objects so the live MCP endpoint pipeline (``get_visible_tools``)
        can call it inline. Reads the same cached probe + provider-key
        set so a fresh probe never gets triggered from this hot path.
        """
        try:
            from core.site_api import list_site_providers_set

            configured_providers = await list_site_providers_set(site_id)
        except Exception:  # noqa: BLE001
            configured_providers = set()

        probe_payload: dict[str, Any] | None = None
        try:
            from core.capability_probe import get_probe_cache

            cached = get_probe_cache().get(site_id)
            if cached is not None:
                probe_payload = cached
        except Exception:  # noqa: BLE001
            probe_payload = None

        kept: list[ToolDefinition] = []
        for tool in tools:
            available, _ = check_tool_prerequisites(
                tool.name,
                probe_payload=probe_payload,
                configured_providers=configured_providers,
            )
            if available:
                kept.append(tool)
        return kept


# F.X.fix #8 — tools that need a per-site AI provider key to succeed.
# Today only the AI image generator; expand as more AI tools land.
_PROVIDER_KEY_REQUIRED_TOOLS: frozenset[str] = frozenset({"wordpress_generate_and_upload_image"})


def _tool_requires_provider_key(tool_name: str) -> bool:
    return tool_name in _PROVIDER_KEY_REQUIRED_TOOLS


def _tool_has_configured_provider(tool_name: str, configured: set[str]) -> bool:
    """``True`` iff the site has at least one provider key for this tool.

    The AI image tool is happy with ANY supported provider key (the
    caller picks which one at call time via the ``provider`` arg) so
    any non-empty configured set counts.
    """
    if not _tool_requires_provider_key(tool_name):
        return True
    return bool(configured)


# ── F.X.fix-pass3: central tool-prerequisites resolver ───────────────
# Single source of truth for "this tool needs X to work". The resolver
# below decides per-call whether a tool is *available* on a given site
# given the cached probe payload + the site's configured provider keys.
# Three predicate kinds:
#
#   provider_key — site needs at least one of the listed AI provider
#                   keys.
#   companion_route — the companion plugin must advertise the named
#                     route in probe.routes.
#   feature_any  — the WP probe features must include at least one of
#                  the listed feature names (e.g. rank_math / yoast).
#
# The resolver's output (``available`` + ``unavailable_reason``) is
# attached to every tool row in ``list_tools_for_site`` AND used by
# ``apply_prerequisites_filter`` to drop unavailable tools from the
# live MCP endpoint, so models calling the endpoint never see a tool
# that is guaranteed to fail at call time.

_TOOL_PREREQUISITES: dict[str, list[dict[str, Any]]] = {
    # AI image — any provider key is enough; the caller picks at call time.
    "wordpress_generate_and_upload_image": [
        {
            "kind": "provider_key",
            "any_of": ["openai", "stability", "replicate", "openrouter"],
        }
    ],
    # Companion-route-backed WP tools.
    "wordpress_cache_purge": [{"kind": "companion_route", "name": "cache_purge"}],
    "wordpress_bulk_update_meta": [{"kind": "companion_route", "name": "bulk_meta"}],
    "wordpress_export_content": [{"kind": "companion_route", "name": "export"}],
    "wordpress_site_health": [{"kind": "companion_route", "name": "site_health"}],
    "wordpress_transient_flush": [{"kind": "companion_route", "name": "transient_flush"}],
    "wordpress_audit_hook_status": [{"kind": "companion_route", "name": "audit_hook"}],
    "wordpress_audit_hook_configure": [{"kind": "companion_route", "name": "audit_hook"}],
    "wordpress_audit_hook_disable": [{"kind": "companion_route", "name": "audit_hook"}],
    "wordpress_regenerate_thumbnails": [
        {"kind": "companion_route", "name": "regenerate_thumbnails"}
    ],
    "wordpress_bulk_delete_media": [{"kind": "companion_route", "name": "bulk_meta"}],
    "wordpress_bulk_reassign_media": [{"kind": "companion_route", "name": "bulk_meta"}],
    # SEO — needs Rank Math (or Yoast in the future). Probe surfaces
    # both flags; we accept either.
    "wordpress_get_post_seo": [{"kind": "feature_any", "names": ["rank_math", "yoast"]}],
    "wordpress_update_post_seo": [{"kind": "feature_any", "names": ["rank_math", "yoast"]}],
    "wordpress_get_product_seo": [{"kind": "feature_any", "names": ["rank_math", "yoast"]}],
    "wordpress_update_product_seo": [{"kind": "feature_any", "names": ["rank_math", "yoast"]}],
    "wordpress_get_internal_links": [{"kind": "feature_any", "names": ["rank_math", "yoast"]}],
    # F.X.fix-pass5 — WooCommerce media tools hit /wp/v2/media which
    # WC consumer_key + secret can't authenticate. Need a WP App
    # Password (wp_username + wp_app_password fields, or legacy
    # username + app_password single-credential mode).
    "woocommerce_attach_media_to_product": [{"kind": "wp_credentials"}],
    "woocommerce_upload_and_attach_to_product": [{"kind": "wp_credentials"}],
    "woocommerce_set_featured_image": [{"kind": "wp_credentials"}],
    # AI image, exposed on both WP and WC plugins. The WC variant
    # needs both an AI provider key AND WP credentials (to upload
    # /wp/v2/media); the WP variant only needs the provider key
    # since its primary client already uses Application Password.
    "woocommerce_generate_and_upload_image": [
        {"kind": "provider_key", "any_of": ["openai", "stability", "replicate", "openrouter"]},
        {"kind": "wp_credentials"},
    ],
}


def check_tool_prerequisites(
    tool_name: str,
    *,
    probe_payload: dict[str, Any] | None,
    configured_providers: set[str],
) -> tuple[bool, str | None]:
    """Decide whether a tool's prerequisites are satisfied.

    Returns ``(available, unavailable_reason)``. ``unavailable_reason``
    is one of ``provider_key`` | ``companion_route`` | ``feature``
    | ``probe_unknown`` when the tool is unavailable, else ``None``.

    A tool with no prerequisites declared is always available — most
    of the catalog (plain CRUD over WP REST) needs no companion / no
    AI key, so the default of "no entry → True" keeps the rule list
    short.
    """
    rules = _TOOL_PREREQUISITES.get(tool_name)
    if not rules:
        return True, None

    routes = ((probe_payload or {}).get("routes")) or {}
    features = ((probe_payload or {}).get("features")) or {}

    for rule in rules:
        kind = rule.get("kind")
        if kind == "provider_key":
            allowed = set(rule.get("any_of") or [])
            if allowed and not (allowed & configured_providers):
                return False, "provider_key"
        elif kind == "companion_route":
            name = rule.get("name") or ""
            # Probe is authoritative when present; absence of probe data
            # (e.g. companion not installed → companion_available=False)
            # is also treated as "unavailable".
            if not routes.get(name):
                return False, "companion_route"
        elif kind == "feature_any":
            names = list(rule.get("names") or [])
            # WP companion's features dict carries booleans like
            # rank_math: true / yoast: false. WC has no analogous gate.
            if not any(features.get(n) for n in names):
                return False, "feature"
        elif kind == "wp_credentials":
            # F.X.fix-pass5 — WC media tools and the WC AI image tool
            # need a WP Application Password to authenticate
            # /wp/v2/media. The WC plugin probe surfaces a
            # ``wp_credentials_present`` flag; absence is a hard fail.
            if not (probe_payload or {}).get("wp_credentials_present"):
                return False, "wp_credentials"

    return True, None


# Singleton
_manager: ToolAccessManager | None = None


def get_tool_access_manager() -> ToolAccessManager:
    """Return the singleton :class:`ToolAccessManager`."""
    global _manager
    if _manager is None:
        _manager = ToolAccessManager()
    return _manager
