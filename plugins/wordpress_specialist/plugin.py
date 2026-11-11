"""WordPress Specialist Plugin (F.19) — companion-backed advanced
management for WordPress professionals.

The companion-backed surface that replaced the deprecated
``wordpress_advanced`` plugin (sunset 2026-05-04 in F.19.3.2-.3):

* ``wordpress_specialist`` — plugins / themes / users / options / cron /
  maintenance / page editing / site config + layout / db inspection /
  bulk fan-out via the Airano MCP Bridge companion plugin. Requires
  only ``url`` + ``username`` + ``app_password`` (the WP user needs
  ``manage_options``). No Docker socket dependency.

Tool surface (58 tools across read / editor / install / settings /
admin tiers — see ``get_tool_specifications`` for the per-section
breakdown). Plugin remains admin-only by default — not in
``ENABLED_PLUGINS`` until F.19.4 (companion v3.0 wp.org republish)
closes the certification loop.
"""

from __future__ import annotations

import json
from typing import Any

from plugins.base import BasePlugin
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers import CapabilitiesHandler
from plugins.wordpress_specialist import handlers


class WordPressSpecialistPlugin(BasePlugin):
    """Advanced WordPress management for specialists, companion-backed."""

    @staticmethod
    def get_plugin_name() -> str:
        return "wordpress_specialist"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        # No ``container`` — this plugin never shells into WP-CLI.
        return ["url", "username", "app_password"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None) -> None:
        super().__init__(config, project_id=project_id)

        self.client = WordPressClient(
            site_url=config["url"],
            username=config["username"],
            app_password=config["app_password"],
        )

        # F.19.1: read-only management handler. F.19.2 will introduce
        # additional handlers (e.g. installer.py, users_admin.py) but
        # all will share self.client and stay companion-backed.
        self.management = handlers.ManagementHandler(self.client)
        # F.19.5: page editing handler — Gutenberg blocks + Elementor
        # + Classic. Companion-backed except for the two read paths
        # that go through stock REST.
        self.pages = handlers.PagesHandler(self.client)
        # F.19.7: theme dev surface — install + activate + delete +
        # file CRUD. Companion-backed (Airano MCP Bridge v2.14.0+).
        self.themes = handlers.ThemesHandler(self.client)
        # F.19.2.1: plugin write management — install / activate /
        # deactivate / update / delete. Companion-backed (Airano MCP
        # Bridge v2.15.0+). First handler to use the install + admin
        # tiers introduced by F.19.2.0.
        self.plugins = handlers.PluginsHandler(self.client)
        # F.19.2.2: chunked zip staging for plugin/theme installs when
        # the zip lives in an agent workspace that MCPHub cannot read as
        # a local path.
        self.zip_install_chunked = handlers.ZipInstallChunkedHandler(
            user_id=config.get("user_id"),
            site_id=config.get("site_id"),
            alias=config.get("alias"),
        )
        # F.19.6.A: site config — identity / reading / permalinks.
        # Companion-backed (Airano MCP Bridge v2.16.0+). First consumer
        # of the ``settings`` tier introduced by F.19.2.0.
        self.site_config = handlers.SiteConfigHandler(self.client)
        # F.19.6.B: site layout — menus / widgets / customizer.
        # Companion-backed (Airano MCP Bridge v2.17.0+). Same
        # ``settings`` tier as site config — closes the Settings →
        # Menus + Appearance → Widgets + Customizer gaps.
        self.site_layout = handlers.SiteLayoutHandler(self.client)
        # F.19.3.2-.4: database inspection + bounded maintenance
        # (companion v2.18.0+ / v2.18.5+) — size, tables, search, check,
        # optimize. No Docker/WP-CLI transport.
        self.database = handlers.DatabaseHandler(self.client)
        # F.X — companion capability probe (mirrors WordPressPlugin). Enables
        # probe_credential_capabilities() below so the dashboard + the
        # tool-prerequisites resolver in core/tool_access can auto-enable the
        # admin_db_* companion routes (wp_db_{size,tables,search,check,optimize}).
        # Was missing → tool_access saw empty routes → every companion-gated
        # wp_db_* tool falsely reported "probe_not_implemented / در دسترس نیست".
        self.capabilities = CapabilitiesHandler(self.client)
        # F.19.3.2-.3: bulk fan-out — post + term updates via stock
        # REST batch. No companion route needed; per-item permission
        # checks happen at the WP layer (S-26 caps at 50 items/call).
        self.bulk = handlers.BulkHandler(self.client)

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """Return all tool specs.

        Currently exposes:
          * F.19.1 read surface — 6 tools (plugins/themes/users/options/
            cron/maintenance)
          * F.19.3.1 ports — 3 tools (system_info / phpinfo / disk_usage)
          * F.19.5 page editing — 11 tools (4 Gutenberg + 6 Elementor + 1
            Classic)
          * F.19.7 theme dev surface — 8 tools (3 management + 5 file CRUD)
          * F.19.2.1 plugin write management — 6 tools (4 install-tier +
            2 admin-tier)
          * F.19.2.2 install zip staging — 4 tools (start + chunk + status + abort)
          * F.19.6.A site config — 6 tools (identity + reading + permalinks)
          * F.19.6.B site layout — 7 tools (3 menu + 3 widget + 1 customizer)
          * F.19.3.2-.4 database — 5 tools (size/tables/search/check/optimize)
          * F.19.3.3 bulk fan-out — 2 tools (post + term updates)

        Total: 58 tools.
        """
        return [
            *handlers.get_management_specs(),
            *handlers.get_pages_specs(),
            *handlers.get_themes_specs(),
            *handlers.get_plugins_specs(),
            *handlers.get_zip_install_chunked_specs(),
            *handlers.get_site_config_specs(),
            *handlers.get_site_layout_specs(),
            *handlers.get_database_specs(),
            *handlers.get_bulk_specs(),
        ]

    async def health_check(self) -> dict[str, Any]:
        """Probe the companion's admin namespace via the cheapest route.

        ``GET /admin/maintenance`` is the smallest payload that exercises
        the same auth + capability path the rest of the surface uses.
        Failure surfaces actionable hints: missing companion, missing
        manage_options, or unreachable site.
        """
        try:
            payload = await self.management.wp_maintenance_status()
            return {
                "healthy": True,
                "companion": True,
                "admin_namespace": True,
                "maintenance_enabled": bool(payload.get("enabled", False)),
            }
        except Exception as exc:  # pragma: no cover — surfaced to dashboard
            return {
                "healthy": False,
                "companion": False,
                "error": str(exc),
                "hint": (
                    "Install Airano MCP Bridge v2.11.0+ on this WordPress "
                    "site and ensure the Application Password belongs to a "
                    "user with manage_options."
                ),
            }

    async def probe_credential_capabilities(self) -> dict[str, Any]:
        """Return the capabilities the saved app_password grants.

        Mirrors ``WordPressPlugin.probe_credential_capabilities``: delegates
        to the companion-plugin-backed ``CapabilitiesHandler``
        (``GET /airano-mcp/v1/capabilities``) — the WordPress user's effective
        capability map. When the companion isn't installed we return an
        empty-granted payload marked unavailable so the dashboard shows the
        "Airano MCP Bridge را نصب یا به‌روزرسانی کنید" hint rather than
        falsely claiming the key is under-privileged.

        Surfacing ``routes`` + ``features`` here lets
        ``core/tool_access.check_tool_prerequisites`` auto-enable the
        ``admin_db_{size,tables,search,check,optimize}`` companion routes for
        the ``wordpress_specialist_wp_db_*`` tools — previously every one of
        those tools read "در دسترس نیست" because this override was missing
        and ``probe_payload.routes`` stayed empty.
        """
        from plugins.wordpress.client import SiteUnreachableError
        from plugins.wordpress.handlers.capabilities import _empty_capabilities_payload

        try:
            payload = await self.capabilities._fetch_capabilities()
        except SiteUnreachableError as exc:
            out: dict[str, Any] = {
                "probe_available": False,
                "granted": [],
                "source": "wordpress_specialist",
                "reason": f"site_unreachable: {exc.reason}",
            }
            if exc.install_hint:
                out["install_hint"] = exc.install_hint
            return out
        except Exception as exc:  # noqa: BLE001
            payload = _empty_capabilities_payload(
                self.client.site_url, reason=f"probe_failed: {exc}"
            )

        if not payload.get("companion_available"):
            return {
                "probe_available": False,
                "granted": [],
                "source": "wordpress_specialist",
                "reason": (payload.get("reason") or "companion_not_installed"),
            }

        user_caps = (payload.get("user") or {}).get("capabilities") or {}
        granted = sorted(k for k, v in user_caps.items() if v)
        roles = list((payload.get("user") or {}).get("roles") or [])
        return {
            "probe_available": True,
            "granted": granted,
            "source": "wordpress_specialist",
            "roles": roles,
            "plugin_version": payload.get("plugin_version"),
            "routes": dict(payload.get("routes") or {}),
            "features": dict(payload.get("features") or {}),
        }

    # ----------------------------------------------------------
    # Method delegation — one per tool spec, mirrored to handlers
    # ----------------------------------------------------------

    async def wp_plugin_list(self, **kwargs):
        result = await self.management.wp_plugin_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_list(self, **kwargs):
        result = await self.management.wp_theme_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_user_list(self, **kwargs):
        result = await self.management.wp_user_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_option_get(self, **kwargs):
        result = await self.management.wp_option_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_cron_list(self, **kwargs):
        result = await self.management.wp_cron_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_maintenance_status(self, **kwargs):
        result = await self.management.wp_maintenance_status(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.3.1 — system ports (companion v2.12.0+)
    async def wp_system_info(self, **kwargs):
        result = await self.management.wp_system_info(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_php_info(self, **kwargs):
        result = await self.management.wp_php_info(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_disk_usage(self, **kwargs):
        result = await self.management.wp_disk_usage(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.5 — Page editing (Gutenberg blocks + Elementor + Classic, companion v2.13.0+)
    async def wp_blocks_get(self, **kwargs):
        result = await self.pages.wp_blocks_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_blocks_replace(self, **kwargs):
        result = await self.pages.wp_blocks_replace(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_blocks_insert_at(self, **kwargs):
        result = await self.pages.wp_blocks_insert_at(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_blocks_remove_at(self, **kwargs):
        result = await self.pages.wp_blocks_remove_at(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_elementor_detect(self, **kwargs):
        result = await self.pages.wp_elementor_detect(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_elementor_get(self, **kwargs):
        result = await self.pages.wp_elementor_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_elementor_set(self, **kwargs):
        result = await self.pages.wp_elementor_set(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_elementor_render_css(self, **kwargs):
        result = await self.pages.wp_elementor_render_css(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_elementor_template_list(self, **kwargs):
        result = await self.pages.wp_elementor_template_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_elementor_template_apply(self, **kwargs):
        result = await self.pages.wp_elementor_template_apply(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_classic_html_replace(self, **kwargs):
        result = await self.pages.wp_classic_html_replace(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.2.2 — Chunked install zip staging for plugin/theme installs
    async def wp_zip_install_chunked_start(self, **kwargs):
        return await self.zip_install_chunked.wp_zip_install_chunked_start(**kwargs)

    async def wp_zip_install_chunked_chunk(self, **kwargs):
        return await self.zip_install_chunked.wp_zip_install_chunked_chunk(**kwargs)

    async def wp_zip_install_chunked_status(self, **kwargs):
        return await self.zip_install_chunked.wp_zip_install_chunked_status(**kwargs)

    async def wp_zip_install_chunked_abort(self, **kwargs):
        return await self.zip_install_chunked.wp_zip_install_chunked_abort(**kwargs)

    # F.19.7 — Theme dev surface (install + file CRUD, companion v2.14.0+)
    async def wp_theme_install_from_zip(self, **kwargs):
        result = await self.themes.wp_theme_install_from_zip(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_activate(self, **kwargs):
        result = await self.themes.wp_theme_activate(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_delete(self, **kwargs):
        result = await self.themes.wp_theme_delete(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_file_list(self, **kwargs):
        result = await self.themes.wp_theme_file_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_file_read(self, **kwargs):
        result = await self.themes.wp_theme_file_read(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_file_write(self, **kwargs):
        result = await self.themes.wp_theme_file_write(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_file_patch(self, **kwargs):
        result = await self.themes.wp_theme_file_patch(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_theme_file_delete(self, **kwargs):
        result = await self.themes.wp_theme_file_delete(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.2.1 — Plugin write management (install + admin, companion v2.15.0+)
    async def wp_plugin_install_from_slug(self, **kwargs):
        result = await self.plugins.wp_plugin_install_from_slug(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_plugin_install_from_zip(self, **kwargs):
        result = await self.plugins.wp_plugin_install_from_zip(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_plugin_activate(self, **kwargs):
        result = await self.plugins.wp_plugin_activate(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_plugin_deactivate(self, **kwargs):
        result = await self.plugins.wp_plugin_deactivate(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_plugin_update(self, **kwargs):
        result = await self.plugins.wp_plugin_update(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_plugin_delete(self, **kwargs):
        result = await self.plugins.wp_plugin_delete(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.6.A — Site config (identity + reading + permalinks, companion v2.16.0+)
    async def wp_site_identity_get(self, **kwargs):
        result = await self.site_config.wp_site_identity_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_site_identity_set(self, **kwargs):
        result = await self.site_config.wp_site_identity_set(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_rank_math_sync_identity(self, **kwargs):
        result = await self.site_config.wp_rank_math_sync_identity(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_reading_settings_get(self, **kwargs):
        result = await self.site_config.wp_reading_settings_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_reading_settings_set(self, **kwargs):
        result = await self.site_config.wp_reading_settings_set(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_permalinks_get(self, **kwargs):
        result = await self.site_config.wp_permalinks_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_permalinks_set(self, **kwargs):
        result = await self.site_config.wp_permalinks_set(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.6.B — Site layout (menus + widgets + customizer, companion v2.17.0+)
    async def wp_menu_list(self, **kwargs):
        result = await self.site_layout.wp_menu_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_menu_get(self, **kwargs):
        result = await self.site_layout.wp_menu_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_menu_set(self, **kwargs):
        result = await self.site_layout.wp_menu_set(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_widget_areas_list(self, **kwargs):
        result = await self.site_layout.wp_widget_areas_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_widget_get(self, **kwargs):
        result = await self.site_layout.wp_widget_get(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_widget_set(self, **kwargs):
        result = await self.site_layout.wp_widget_set(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_customizer_changeset(self, **kwargs):
        result = await self.site_layout.wp_customizer_changeset(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.3.2-.4 — Database inspection + bounded maintenance.
    async def wp_db_size(self, **kwargs):
        result = await self.database.wp_db_size(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_tables(self, **kwargs):
        result = await self.database.wp_db_tables(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_search(self, **kwargs):
        result = await self.database.wp_db_search(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_check(self, **kwargs):
        result = await self.database.wp_db_check(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_optimize(self, **kwargs):
        result = await self.database.wp_db_optimize(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # F.19.3.3 — Bulk fan-out (editor tier, stock REST batch)
    async def wp_bulk_post_update(self, **kwargs):
        result = await self.bulk.wp_bulk_post_update(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_bulk_term_update(self, **kwargs):
        result = await self.bulk.wp_bulk_term_update(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result
