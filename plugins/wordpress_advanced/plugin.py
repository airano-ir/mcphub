"""
WordPress Advanced Plugin - Clean Architecture

Advanced WordPress management features requiring elevated permissions.
Provides database operations, bulk operations, and system management.

This plugin is separated from core WordPress plugin for:
- Better security (separate API keys for advanced features)
- Better tool visibility (users see only features they need)
- Granular access control
"""

import json
from typing import Any

from plugins.base import BasePlugin
from plugins.wordpress.client import WordPressClient
from plugins.wordpress_advanced import handlers

class WordPressAdvancedPlugin(BasePlugin):
    """
    WordPress Advanced plugin - separated for security and visibility.

    Provides advanced WordPress management capabilities:
    - Database operations (export, import, search, query, repair)
    - Bulk operations (batch updates/deletes for posts, products, media)
    - System operations (system info, cache, cron, error logs)

    Requires:
    - WordPress site with REST API
    - WP-CLI access (for database and system operations)
    - Docker container name (for WP-CLI execution)
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "wordpress_advanced"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "username", "app_password", "container"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize WordPress Advanced plugin with handlers.

        Args:
            config: Configuration dictionary containing:
                - url: WordPress site URL
                - username: WordPress username
                - app_password: WordPress application password
                - container: Docker container name for WP-CLI (REQUIRED)
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create WordPress API client
        self.client = WordPressClient(
            site_url=config["url"], username=config["username"], app_password=config["app_password"]
        )

        # WP-CLI is REQUIRED for wordpress_advanced
        container_name = config.get("container")
        if not container_name:
            raise ValueError(
                "WordPress Advanced plugin requires 'container' configuration. "
                "Please set WORDPRESS_ADVANCED_SITE1_CONTAINER in environment variables."
            )

        # Import WP-CLI manager
        from plugins.wordpress.wp_cli import WPCLIManager

        wp_cli_manager = WPCLIManager(container_name)

        # Initialize handlers (all require WP-CLI or advanced REST API)
        self.database = handlers.DatabaseHandler(self.client, wp_cli_manager)
        self.bulk = handlers.BulkHandler(self.client)
        self.system = handlers.SystemHandler(self.client, wp_cli_manager)

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.

        Returns:
            List of tool specification dictionaries (22 tools total)
        """
        specs = []

        # Database operations (7 tools)
        specs.extend(handlers.get_database_specs())

        # Bulk operations (8 tools)
        specs.extend(handlers.get_bulk_specs())

        # System operations (7 tools)
        specs.extend(handlers.get_system_specs())

        return specs

    async def health_check(self) -> dict[str, Any]:
        """
        Check WordPress Advanced features availability.

        Returns:
            Dict with health status and WP-CLI availability
        """
        try:
            # Test WP-CLI access (primary requirement for wordpress_advanced)
            wp_cli_version = await self.system.wp_cli_version()
            wp_cli_available = bool(wp_cli_version.get("version"))

            # Test REST API access with a public endpoint
            rest_api_available = False
            try:
                # Use a public endpoint that doesn't require authentication
                site_info = await self.client.get("/")
                rest_api_available = bool(site_info.get("name"))
            except Exception as e:
                self.logger.warning(f"REST API check failed (non-critical): {e}")
                rest_api_available = False

            return {
                "healthy": wp_cli_available,  # Only WP-CLI is critical for wordpress_advanced
                "wp_cli_available": wp_cli_available,
                "rest_api_available": rest_api_available,
                "features": {
                    "database_operations": wp_cli_available,
                    "bulk_operations": rest_api_available,
                    "system_operations": wp_cli_available,
                },
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "wp_cli_available": False,
                "rest_api_available": False,
            }

    # ========================================
    # Method Delegation to Handlers
    # ========================================
    # All methods delegate to appropriate handlers
    # This maintains backward compatibility with existing code

    # === Database Operations (7 tools) ===
    async def wp_db_export(self, **kwargs):
        """Export WordPress database"""
        result = await self.database.wp_db_export(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_import(self, **kwargs):
        """Import WordPress database"""
        result = await self.database.wp_db_import(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_size(self, **kwargs):
        """Get database size"""
        result = await self.database.wp_db_size(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_tables(self, **kwargs):
        """List database tables"""
        result = await self.database.wp_db_tables(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_search(self, **kwargs):
        """Search database"""
        result = await self.database.wp_db_search(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_query(self, **kwargs):
        """Execute read-only database query"""
        result = await self.database.wp_db_query(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def wp_db_repair(self, **kwargs):
        """Repair and optimize database"""
        result = await self.database.wp_db_repair(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # === Bulk Operations (8 tools) ===
    async def bulk_update_posts(self, **kwargs):
        """Bulk update posts"""
        result = await self.bulk.bulk_update_posts(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def bulk_delete_posts(self, **kwargs):
        """Bulk delete posts"""
        result = await self.bulk.bulk_delete_posts(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def bulk_update_products(self, **kwargs):
        """Bulk update products"""
        result = await self.bulk.bulk_update_products(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def bulk_delete_products(self, **kwargs):
        """Bulk delete products"""
        result = await self.bulk.bulk_delete_products(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def bulk_delete_media(self, **kwargs):
        """Bulk delete media"""
        result = await self.bulk.bulk_delete_media(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def bulk_assign_categories(self, **kwargs):
        """Bulk assign categories to posts"""
        result = await self.bulk.bulk_assign_categories(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def bulk_assign_tags(self, **kwargs):
        """Bulk assign tags to posts"""
        result = await self.bulk.bulk_assign_tags(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def bulk_trash_posts(self, **kwargs):
        """Bulk move posts to trash"""
        result = await self.bulk.bulk_trash_posts(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    # === System Operations (7 tools) ===
    async def system_info(self, **kwargs):
        """Get system information"""
        result = await self.system.system_info(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def system_phpinfo(self, **kwargs):
        """Get PHP information"""
        result = await self.system.system_phpinfo(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def system_disk_usage(self, **kwargs):
        """Get disk usage"""
        result = await self.system.system_disk_usage(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def system_clear_all_caches(self, **kwargs):
        """Clear all caches"""
        result = await self.system.system_clear_all_caches(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def cron_list(self, **kwargs):
        """List cron jobs"""
        result = await self.system.cron_list(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def cron_run(self, **kwargs):
        """Run cron job"""
        result = await self.system.cron_run(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result

    async def error_log(self, **kwargs):
        """Get error log"""
        result = await self.system.error_log(**kwargs)
        return json.dumps(result, indent=2) if isinstance(result, dict) else result
