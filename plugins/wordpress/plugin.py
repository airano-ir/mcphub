"""
WordPress Plugin - Option B Clean Architecture

Complete WordPress content management through REST API and WP-CLI.
Refactored to use modular handlers for better organization and maintainability.

Note: WooCommerce functionality split to separate plugin in Phase D.1.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.wordpress import handlers
from plugins.wordpress.client import WordPressClient


class WordPressPlugin(BasePlugin):
    """
    WordPress project plugin - Option B architecture.

    Provides comprehensive WordPress content management capabilities including:
    - Content (posts, pages, custom post types)
    - Media library
    - Taxonomy (categories, tags, custom taxonomies)
    - Comments
    - Users
    - Site management (plugins, themes, settings)
    - SEO (Yoast, RankMath)
    - Menus and navigation
    - WP-CLI operations (cache, database, updates)
    - Internal link analysis

    Note: WooCommerce functionality moved to separate woocommerce plugin (Phase D.1)
    Total: 67 tools
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "wordpress"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "username", "app_password"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize WordPress plugin with handlers.

        Args:
            config: Configuration dictionary containing:
                - url: WordPress site URL
                - username: WordPress username
                - app_password: WordPress application password
                - container: (Optional) Docker container name for WP-CLI
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create WordPress API client
        self.client = WordPressClient(
            site_url=config["url"], username=config["username"], app_password=config["app_password"]
        )

        # Initialize core WordPress handlers
        self.posts = handlers.PostsHandler(self.client)
        self.media = handlers.MediaHandler(self.client, user_id=config.get("user_id"))
        # F.5a.4 / F.5a.9.x: AI image handler receives user_id AND site_id.
        # site_id is the primary input for resolving per-site provider API
        # keys; user_id is retained for audit / rate-limit context and for
        # the admin/env-fallback path when no site is known.
        self.ai_media = handlers.AIMediaHandler(
            self.client,
            user_id=config.get("user_id"),
            site_id=config.get("site_id"),
        )
        # F.5a.5: chunked media uploads (session store + disk spill)
        self.media_chunked = handlers.MediaChunkedHandler(
            self.client, user_id=config.get("user_id")
        )
        # F.5a.6.3: probe WP upload limits (24h cache)
        self.media_probe = handlers.ProbeHandler(self.client)
        # F.18.1: probe companion-plugin capabilities (24h cache)
        self.capabilities = handlers.CapabilitiesHandler(self.client)
        # F.18.2: batch post_meta writes via companion plugin
        self.bulk_meta = handlers.BulkMetaHandler(self.client)
        # F.18.3: structured JSON export via companion plugin
        self.export = handlers.ExportHandler(self.client)
        # F.18.4: cache purge via companion plugin
        self.cache_purge_handler = handlers.CachePurgeHandler(self.client)
        # F.18.5: native transient flush via companion plugin
        self.transient_flush_handler = handlers.TransientFlushHandler(self.client)
        # F.18.6: unified site-health snapshot via companion plugin
        self.site_health_handler = handlers.SiteHealthHandler(self.client)
        # F.18.7: audit-hook configuration + query
        self.audit_hook_handler = handlers.AuditHookHandler(self.client)
        # F.5a.8.2: regenerate attachment sub-sizes via companion plugin
        self.regenerate_thumbnails_handler = handlers.RegenerateThumbnailsHandler(self.client)
        # F.5a.8.3: bulk delete / reassign attachments via stock WP REST
        self.media_bulk = handlers.MediaBulkHandler(self.client)
        self.taxonomy = handlers.TaxonomyHandler(self.client)
        self.comments = handlers.CommentsHandler(self.client)
        self.users = handlers.UsersHandler(self.client)
        self.site = handlers.SiteHandler(self.client)
        self.seo = handlers.SEOHandler(self.client)
        self.menus = handlers.MenusHandler(self.client)

        # Note: WooCommerce handlers moved to woocommerce plugin (Phase D.1)
        # self.products, self.orders, self.customers, self.reports, self.coupons

        # WP-CLI handler (optional - requires container)
        container_name = config.get("container")
        if container_name:
            from plugins.wordpress.wp_cli import WPCLIManager

            wp_cli_manager = WPCLIManager(container_name)
            self.wp_cli = handlers.WPCLIHandler(wp_cli_manager)
        else:
            self.wp_cli = None

        # Note: Database, Bulk, and System operations moved to wordpress_advanced plugin

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.

        Returns:
            List of tool specification dictionaries (67 tools)
        """
        specs = []

        # Core WordPress handlers
        specs.extend(handlers.get_posts_specs())  # 13 tools
        specs.extend(handlers.get_media_specs())  # 6 tools (F.5a.1: added base64 upload)
        specs.extend(handlers.get_ai_media_specs())  # 1 tool (F.5a.4: generate+upload)
        specs.extend(handlers.get_media_chunked_specs())  # 5 tools (F.5a.5 + F.5a.8.4 status)
        specs.extend(handlers.get_media_probe_specs())  # 1 tool (F.5a.6.3: probe limits)
        specs.extend(handlers.get_capabilities_specs())  # 1 tool (F.18.1: probe capabilities)
        specs.extend(handlers.get_bulk_meta_specs())  # 1 tool (F.18.2: bulk meta write)
        specs.extend(handlers.get_export_specs())  # 1 tool (F.18.3: structured export)
        specs.extend(handlers.get_cache_purge_specs())  # 1 tool (F.18.4: cache purge)
        specs.extend(handlers.get_transient_flush_specs())  # 1 tool (F.18.5: transient flush)
        specs.extend(handlers.get_site_health_specs())  # 1 tool (F.18.6: site health)
        specs.extend(handlers.get_audit_hook_specs())  # 3 tools (F.18.7: audit hook)
        specs.extend(handlers.get_regenerate_thumbnails_specs())  # 1 tool (F.5a.8.2)
        specs.extend(handlers.get_media_bulk_specs())  # 2 tools (F.5a.8.3: bulk delete+reassign)
        specs.extend(handlers.get_taxonomy_specs())  # 11 tools
        specs.extend(handlers.get_comments_specs())  # 5 tools
        specs.extend(handlers.get_users_specs())  # 2 tools
        specs.extend(handlers.get_site_specs())  # 5 tools

        # Advanced content handlers
        specs.extend(handlers.get_seo_specs())  # 4 tools
        specs.extend(handlers.get_menus_specs())  # 5 tools
        specs.extend(handlers.get_wp_cli_specs())  # 15 tools

        # Note: WooCommerce specs moved to woocommerce plugin (Phase D.1)
        # Note: Database, Bulk, and System specs in wordpress_advanced plugin

        return specs

    async def health_check(self) -> dict[str, Any]:
        """
        Check WordPress site health and feature availability.

        Returns:
            Dict with health status, WooCommerce, and SEO plugin availability
        """
        return await self.site.health_check()

    async def probe_credential_capabilities(self) -> dict[str, Any]:
        """F.7e — return the capabilities the saved app_password grants.

        Delegates to the companion-plugin-backed ``CapabilitiesHandler``
        (F.18.1), which reads ``GET /airano-mcp/v1/capabilities`` — the
        WordPress user's effective capability map. When the companion
        isn't installed we return an empty-granted payload marked as
        unavailable so the caller can show a "companion plugin needed"
        hint rather than falsely claim the key is under-privileged.

        F.X.fix #3 — fast-fail on unreachable sites. When the low-level
        client raises :class:`SiteUnreachableError` (DNS/TCP/timeout),
        we short-circuit to a structured ``probe_available=False``
        payload carrying the ``install_hint`` so the dashboard renders
        the "check your URL / install companion" prompt in <10s instead
        of hanging on the 30s total timeout.
        """
        from plugins.wordpress.client import SiteUnreachableError
        from plugins.wordpress.handlers.capabilities import _empty_capabilities_payload

        try:
            payload = await self.capabilities._fetch_capabilities()
        except SiteUnreachableError as exc:
            out: dict[str, Any] = {
                "probe_available": False,
                "granted": [],
                "source": "wordpress_companion",
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
                "source": "wordpress_companion",
                "reason": (payload.get("reason") or "companion_not_installed"),
            }

        user_caps = (payload.get("user") or {}).get("capabilities") or {}
        granted = sorted(k for k, v in user_caps.items() if v)
        roles = list((payload.get("user") or {}).get("roles") or [])
        # F.X.fix-pass3 — surface routes + features so the central
        # tool-prerequisites resolver in core/tool_access can decide
        # which tools to auto-disable (SEO needs Rank Math/Yoast,
        # cache_purge/etc. need the matching companion route, …).
        return {
            "probe_available": True,
            "granted": granted,
            "source": "wordpress_companion",
            "roles": roles,
            "plugin_version": payload.get("plugin_version"),
            "routes": dict(payload.get("routes") or {}),
            "features": dict(payload.get("features") or {}),
        }

    # ========================================
    # Method Delegation to Handlers
    # ========================================
    # All methods delegate to appropriate handlers
    # This maintains backward compatibility with existing code

    # === Posts & Pages ===
    async def list_posts(self, **kwargs):
        return await self.posts.list_posts(**kwargs)

    async def get_post(self, **kwargs):
        return await self.posts.get_post(**kwargs)

    async def create_post(self, **kwargs):
        return await self.posts.create_post(**kwargs)

    async def update_post(self, **kwargs):
        return await self.posts.update_post(**kwargs)

    async def delete_post(self, **kwargs):
        return await self.posts.delete_post(**kwargs)

    async def list_pages(self, **kwargs):
        return await self.posts.list_pages(**kwargs)

    async def create_page(self, **kwargs):
        return await self.posts.create_page(**kwargs)

    async def update_page(self, **kwargs):
        return await self.posts.update_page(**kwargs)

    async def delete_page(self, **kwargs):
        return await self.posts.delete_page(**kwargs)

    async def list_post_types(self, **kwargs):
        return await self.posts.list_post_types(**kwargs)

    async def get_post_type_info(self, **kwargs):
        return await self.posts.get_post_type_info(**kwargs)

    async def list_custom_posts(self, **kwargs):
        return await self.posts.list_custom_posts(**kwargs)

    async def create_custom_post(self, **kwargs):
        return await self.posts.create_custom_post(**kwargs)

    async def get_internal_links(self, **kwargs):
        return await self.posts.get_internal_links(**kwargs)

    # === Media ===
    async def list_media(self, **kwargs):
        return await self.media.list_media(**kwargs)

    async def get_media(self, **kwargs):
        return await self.media.get_media(**kwargs)

    async def upload_media_from_url(self, **kwargs):
        return await self.media.upload_media_from_url(**kwargs)

    async def upload_media_from_base64(self, **kwargs):
        return await self.media.upload_media_from_base64(**kwargs)

    async def update_media(self, **kwargs):
        return await self.media.update_media(**kwargs)

    async def delete_media(self, **kwargs):
        return await self.media.delete_media(**kwargs)

    # === AI Image Generation (F.5a.4) ===
    async def generate_and_upload_image(self, **kwargs):
        return await self.ai_media.generate_and_upload_image(**kwargs)

    # === Chunked Media Upload (F.5a.5) ===
    async def upload_media_chunked_start(self, **kwargs):
        return await self.media_chunked.upload_media_chunked_start(**kwargs)

    async def upload_media_chunked_chunk(self, **kwargs):
        return await self.media_chunked.upload_media_chunked_chunk(**kwargs)

    async def upload_media_chunked_finish(self, **kwargs):
        return await self.media_chunked.upload_media_chunked_finish(**kwargs)

    async def upload_media_chunked_abort(self, **kwargs):
        return await self.media_chunked.upload_media_chunked_abort(**kwargs)

    async def upload_media_chunked_status(self, **kwargs):
        return await self.media_chunked.upload_media_chunked_status(**kwargs)

    # === Probe Upload Limits (F.5a.6.3) ===
    async def probe_upload_limits(self, **kwargs):
        return await self.media_probe.probe_upload_limits(**kwargs)

    # === Probe Companion Capabilities (F.18.1) ===
    async def probe_capabilities(self, **kwargs):
        return await self.capabilities.probe_capabilities(**kwargs)

    # === Bulk Meta Write (F.18.2) ===
    async def bulk_update_meta(self, **kwargs):
        return await self.bulk_meta.bulk_update_meta(**kwargs)

    # === Structured Export (F.18.3) ===
    async def export_content(self, **kwargs):
        return await self.export.export_content(**kwargs)

    # === Cache Purge (F.18.4) ===
    async def cache_purge(self, **kwargs):
        return await self.cache_purge_handler.cache_purge(**kwargs)

    # === Regenerate Thumbnails (F.5a.8.2) ===
    async def regenerate_thumbnails(self, **kwargs):
        return await self.regenerate_thumbnails_handler.regenerate_thumbnails(**kwargs)

    # === Bulk Media Operations (F.5a.8.3) ===
    async def bulk_delete_media(self, **kwargs):
        return await self.media_bulk.bulk_delete_media(**kwargs)

    async def bulk_reassign_media(self, **kwargs):
        return await self.media_bulk.bulk_reassign_media(**kwargs)

    # === Transient Flush (F.18.5) ===
    async def transient_flush(self, **kwargs):
        return await self.transient_flush_handler.transient_flush(**kwargs)

    # === Unified Site Health (F.18.6) ===
    async def site_health(self, **kwargs):
        return await self.site_health_handler.site_health(**kwargs)

    # === Audit Hook (F.18.7) ===
    async def audit_hook_status(self, **kwargs):
        return await self.audit_hook_handler.audit_hook_status(**kwargs)

    async def audit_hook_configure(self, **kwargs):
        return await self.audit_hook_handler.audit_hook_configure(**kwargs)

    async def audit_hook_disable(self, **kwargs):
        return await self.audit_hook_handler.audit_hook_disable(**kwargs)

    # === Taxonomy (Categories & Tags) ===
    async def list_categories(self, **kwargs):
        return await self.taxonomy.list_categories(**kwargs)

    async def create_category(self, **kwargs):
        return await self.taxonomy.create_category(**kwargs)

    async def update_category(self, **kwargs):
        return await self.taxonomy.update_category(**kwargs)

    async def delete_category(self, **kwargs):
        return await self.taxonomy.delete_category(**kwargs)

    async def list_tags(self, **kwargs):
        return await self.taxonomy.list_tags(**kwargs)

    async def create_tag(self, **kwargs):
        return await self.taxonomy.create_tag(**kwargs)

    async def update_tag(self, **kwargs):
        return await self.taxonomy.update_tag(**kwargs)

    async def delete_tag(self, **kwargs):
        return await self.taxonomy.delete_tag(**kwargs)

    async def list_taxonomies(self, **kwargs):
        return await self.taxonomy.list_taxonomies(**kwargs)

    async def list_taxonomy_terms(self, **kwargs):
        return await self.taxonomy.list_taxonomy_terms(**kwargs)

    async def create_taxonomy_term(self, **kwargs):
        return await self.taxonomy.create_taxonomy_term(**kwargs)

    # === Comments ===
    async def list_comments(self, **kwargs):
        return await self.comments.list_comments(**kwargs)

    async def get_comment(self, **kwargs):
        return await self.comments.get_comment(**kwargs)

    async def create_comment(self, **kwargs):
        return await self.comments.create_comment(**kwargs)

    async def update_comment(self, **kwargs):
        return await self.comments.update_comment(**kwargs)

    async def delete_comment(self, **kwargs):
        return await self.comments.delete_comment(**kwargs)

    # === Users ===
    async def list_users(self, **kwargs):
        return await self.users.list_users(**kwargs)

    async def get_current_user(self, **kwargs):
        return await self.users.get_current_user(**kwargs)

    # === Site Management ===
    async def list_plugins(self, **kwargs):
        return await self.site.list_plugins(**kwargs)

    async def list_themes(self, **kwargs):
        return await self.site.list_themes(**kwargs)

    async def get_active_theme(self, **kwargs):
        return await self.site.get_active_theme(**kwargs)

    async def get_settings(self, **kwargs):
        return await self.site.get_settings(**kwargs)

    async def get_site_health(self, **kwargs):
        return await self.site.get_site_health(**kwargs)

    # Note: WooCommerce methods moved to woocommerce plugin (Phase D.1)

    # === SEO ===
    async def get_post_seo(self, **kwargs):
        return await self.seo.get_post_seo(**kwargs)

    async def get_product_seo(self, **kwargs):
        return await self.seo.get_product_seo(**kwargs)

    async def update_post_seo(self, **kwargs):
        return await self.seo.update_post_seo(**kwargs)

    async def update_product_seo(self, **kwargs):
        return await self.seo.update_product_seo(**kwargs)

    # === Menus ===
    async def list_menus(self, **kwargs):
        return await self.menus.list_menus(**kwargs)

    async def get_menu(self, **kwargs):
        return await self.menus.get_menu(**kwargs)

    async def create_menu(self, **kwargs):
        return await self.menus.create_menu(**kwargs)

    async def list_menu_items(self, **kwargs):
        return await self.menus.list_menu_items(**kwargs)

    async def create_menu_item(self, **kwargs):
        return await self.menus.create_menu_item(**kwargs)

    async def update_menu_item(self, **kwargs):
        return await self.menus.update_menu_item(**kwargs)

    # === WP-CLI Operations ===
    async def wp_cache_flush(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_cache_flush(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_cache_type(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_cache_type(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_transient_delete_all(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_transient_delete_all(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_transient_list(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_transient_list(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_db_check(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_db_check(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_db_optimize(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_db_optimize(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_db_export(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_db_export(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_plugin_list_detailed(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_plugin_list_detailed(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_theme_list_detailed(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_theme_list_detailed(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_plugin_verify_checksums(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_plugin_verify_checksums(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_core_verify_checksums(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_core_verify_checksums(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_search_replace_dry_run(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_search_replace_dry_run(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_plugin_update(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_plugin_update(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_theme_update(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_theme_update(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    async def wp_core_update(self, **kwargs):
        if self.wp_cli:
            return await self.wp_cli.wp_core_update(**kwargs)
        return '{"error": "WP-CLI not available. Container not configured."}'

    # Note: Database, Bulk, and System operations moved to wordpress_advanced plugin

    # === Legacy compatibility methods ===
    # These methods are kept for potential backward compatibility
    # but are not exposed as tools in Option B architecture

    async def check_woocommerce(self) -> dict[str, Any]:
        """Check if WooCommerce is available (legacy method)"""
        return await self.client.check_woocommerce()

    async def check_seo_plugins(self) -> dict[str, Any]:
        """Check SEO plugins availability (legacy method)"""
        return await self.seo._check_seo_plugins()
