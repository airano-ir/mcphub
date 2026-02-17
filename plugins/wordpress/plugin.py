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
        self.media = handlers.MediaHandler(self.client)
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
        specs.extend(handlers.get_media_specs())  # 5 tools
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

    async def update_media(self, **kwargs):
        return await self.media.update_media(**kwargs)

    async def delete_media(self, **kwargs):
        return await self.media.delete_media(**kwargs)

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
