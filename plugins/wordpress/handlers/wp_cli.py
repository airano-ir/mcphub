"""WP-CLI Handler - manages WordPress WP-CLI operations"""

import json
from typing import Any

from plugins.wordpress.wp_cli import WPCLIManager


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === CACHE MANAGEMENT (4 tools) ===
        {
            "name": "wp_cache_flush",
            "method_name": "wp_cache_flush",
            "description": "Flush WordPress object cache. Clears all cached objects from Redis, Memcached, or file cache. Safe to run anytime.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_cache_type",
            "method_name": "wp_cache_type",
            "description": "Get the object cache type being used (Redis, Memcached, file-based, etc.).",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_transient_delete_all",
            "method_name": "wp_transient_delete_all",
            "description": "Delete all expired transients from the database. Improves database performance by cleaning up temporary cached data.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_transient_list",
            "method_name": "wp_transient_list",
            "description": "List transients in the database (limited to first 100). Shows transient keys with expiration times. Useful for debugging caching issues.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        # === DATABASE OPERATIONS (3 tools) ===
        {
            "name": "wp_db_check",
            "method_name": "wp_db_check",
            "description": "Check WordPress database for errors. Runs integrity checks to ensure tables are healthy. Read-only operation.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_db_optimize",
            "method_name": "wp_db_optimize",
            "description": "Optimize WordPress database tables. Runs OPTIMIZE TABLE on all WordPress tables to reclaim space and improve performance.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_db_export",
            "method_name": "wp_db_export",
            "description": "Export WordPress database to SQL file in /tmp directory. Creates timestamped backup file for database recovery.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        # === PLUGIN/THEME INFO (4 tools) ===
        {
            "name": "wp_plugin_list_detailed",
            "method_name": "wp_plugin_list_detailed",
            "description": "List all WordPress plugins with detailed information including versions, status (active/inactive), and available updates.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_theme_list_detailed",
            "method_name": "wp_theme_list_detailed",
            "description": "List all WordPress themes with detailed information including versions, status, and active theme identification.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_plugin_verify_checksums",
            "method_name": "wp_plugin_verify_checksums",
            "description": "Verify plugin file integrity against WordPress.org checksums. Detects tampering or corruption. Only works for plugins from WordPress.org repository.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        {
            "name": "wp_core_verify_checksums",
            "method_name": "wp_core_verify_checksums",
            "description": "Verify WordPress core files against official checksums. Critical security tool for detecting tampering or unauthorized modifications.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        # === SEARCH & REPLACE + UPDATES (4 tools) ===
        {
            "name": "wp_search_replace_dry_run",
            "method_name": "wp_search_replace_dry_run",
            "description": "Search and replace in database (DRY RUN ONLY). Previews what would be changed. NEVER makes actual changes. Use for migration planning.",
            "schema": {
                "type": "object",
                "properties": {
                    "old_string": {
                        "type": "string",
                        "description": "String to search for in database",
                        "minLength": 1,
                        "maxLength": 500,
                    },
                    "new_string": {
                        "type": "string",
                        "description": "String to replace with",
                        "minLength": 1,
                        "maxLength": 500,
                    },
                    "tables": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Optional list of specific tables to search (default: all tables)",
                    },
                },
                "required": ["old_string", "new_string"],
            },
            "scope": "write",
        },
        {
            "name": "wp_plugin_update",
            "method_name": "wp_plugin_update",
            "description": "Update WordPress plugin(s). Default is DRY RUN mode (shows available updates). Set dry_run=false to apply updates. Always backup first!",
            "schema": {
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "Plugin slug to update, or 'all' for all plugins",
                        "minLength": 1,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, only show available updates without applying them (default: true)",
                        "default": True,
                    },
                },
                "required": ["plugin_name"],
            },
            "scope": "write",
        },
        {
            "name": "wp_theme_update",
            "method_name": "wp_theme_update",
            "description": "Update WordPress theme(s). Default is DRY RUN mode (shows available updates). Set dry_run=false to apply updates. WARNING: Updating active theme can break site appearance!",
            "schema": {
                "type": "object",
                "properties": {
                    "theme_name": {
                        "type": "string",
                        "description": "Theme slug to update, or 'all' for all themes",
                        "minLength": 1,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, only show available updates without applying them (default: true)",
                        "default": True,
                    },
                },
                "required": ["theme_name"],
            },
            "scope": "write",
        },
        {
            "name": "wp_core_update",
            "method_name": "wp_core_update",
            "description": "Update WordPress core. Default is DRY RUN mode (shows available updates). Set dry_run=false to apply updates. CRITICAL: Always backup before core updates!",
            "schema": {
                "type": "object",
                "properties": {
                    "version": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Specific version to update to, or null for latest version",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, only show available updates without applying them (default: true)",
                        "default": True,
                    },
                },
            },
            "scope": "write",
        },
    ]


class WPCLIHandler:
    """Handle WP-CLI operations for WordPress"""

    def __init__(self, wp_cli: WPCLIManager):
        """
        Initialize WP-CLI handler.

        Args:
            wp_cli: WPCLIManager instance for executing WP-CLI commands
        """
        self.wp_cli = wp_cli

    # === CACHE MANAGEMENT ===

    async def wp_cache_flush(self) -> str:
        """
        Flush WordPress object cache.

        Clears all cached objects from the object cache (Redis, Memcached, or file).
        Safe to run anytime - will not affect database or content.

        Returns:
            JSON string with flush status and message
        """
        try:
            result = await self.wp_cli.wp_cache_flush()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to flush cache: {str(e)}"}, indent=2
            )

    async def wp_cache_type(self) -> str:
        """
        Get the object cache type being used.

        Shows which caching backend is active (e.g., Redis, Memcached, file-based).

        Returns:
            JSON string with cache type information
        """
        try:
            result = await self.wp_cli.wp_cache_type()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to get cache type: {str(e)}"}, indent=2
            )

    async def wp_transient_delete_all(self) -> str:
        """
        Delete all expired transients from the database.

        Transients are temporary cached data stored in the WordPress database.
        This command only deletes expired transients, improving database performance.

        Returns:
            JSON string with count of deleted transients
        """
        try:
            result = await self.wp_cli.wp_transient_delete_all()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to delete transients: {str(e)}"}, indent=2
            )

    async def wp_transient_list(self) -> str:
        """
        List transients in the database (limited to first 100).

        Shows transient keys with their expiration times.
        Useful for debugging caching issues.

        Returns:
            JSON string with total count and list of transients (max 100)
        """
        try:
            result = await self.wp_cli.wp_transient_list()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list transients: {str(e)}"}, indent=2
            )

    # === DATABASE OPERATIONS ===

    async def wp_db_check(self) -> str:
        """
        Check WordPress database for errors.

        Runs database integrity checks to ensure tables are healthy.
        Safe to run - read-only operation.

        Returns:
            JSON string with health status and tables checked
        """
        try:
            result = await self.wp_cli.wp_db_check()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to check database: {str(e)}"}, indent=2
            )

    async def wp_db_optimize(self) -> str:
        """
        Optimize WordPress database tables.

        Runs OPTIMIZE TABLE on all WordPress tables to reclaim space
        and improve performance. Safe operation - non-destructive.

        Returns:
            JSON string with optimization results
        """
        try:
            result = await self.wp_cli.wp_db_optimize()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to optimize database: {str(e)}"}, indent=2
            )

    async def wp_db_export(self) -> str:
        """
        Export WordPress database to SQL file in /tmp.

        Creates a database backup in the /tmp directory with timestamp.
        Safe - exports are only saved to /tmp for security.

        Returns:
            JSON string with export file path and size
        """
        try:
            result = await self.wp_cli.wp_db_export()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to export database: {str(e)}"}, indent=2
            )

    # === PLUGIN/THEME INFO ===

    async def wp_plugin_list_detailed(self) -> str:
        """
        List all WordPress plugins with detailed information.

        Shows plugin names, versions, status (active/inactive), and available updates.
        Useful for inventory management and update planning.

        Returns:
            JSON string with total count and plugin list
        """
        try:
            result = await self.wp_cli.wp_plugin_list_detailed()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list plugins: {str(e)}"}, indent=2
            )

    async def wp_theme_list_detailed(self) -> str:
        """
        List all WordPress themes with detailed information.

        Shows theme names, versions, status, and identifies the active theme.
        Useful for theme management and updates.

        Returns:
            JSON string with total count, theme list, and active theme
        """
        try:
            result = await self.wp_cli.wp_theme_list_detailed()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to list themes: {str(e)}"}, indent=2
            )

    async def wp_plugin_verify_checksums(self) -> str:
        """
        Verify plugin file integrity against WordPress.org checksums.

        Checks all plugins against official checksums to detect tampering or corruption.
        Important security tool for detecting malware or unauthorized modifications.

        Note: Only works for plugins from WordPress.org repository.
        Premium/custom plugins will be skipped.

        Returns:
            JSON string with verification results
        """
        try:
            result = await self.wp_cli.wp_plugin_verify_checksums()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to verify plugin checksums: {str(e)}"},
                indent=2,
            )

    async def wp_core_verify_checksums(self) -> str:
        """
        Verify WordPress core files against official checksums.

        Checks WordPress core files for tampering, corruption, or unauthorized modifications.
        Critical security tool for ensuring WordPress integrity.

        Returns:
            JSON string with verification status and any modified files
        """
        try:
            result = await self.wp_cli.wp_core_verify_checksums()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to verify core checksums: {str(e)}"}, indent=2
            )

    # === SEARCH & REPLACE + UPDATES ===

    async def wp_search_replace_dry_run(
        self, old_string: str, new_string: str, tables: list[str] | None = None
    ) -> str:
        """
        Search and replace in database (DRY RUN ONLY - no actual changes).

        Previews what would be changed if you run search-replace.
        ALWAYS runs in dry-run mode - never makes actual changes.

        Security: This tool ONLY shows what would be changed. To make actual
        changes, you must use WP-CLI directly with appropriate backups.

        Args:
            old_string: String to search for
            new_string: String to replace with
            tables: Optional list of specific tables to search (default: all tables)

        Returns:
            JSON string with preview of changes
        """
        try:
            result = await self.wp_cli.wp_search_replace_dry_run(
                old_string=old_string, new_string=new_string, tables=tables
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to run search-replace dry run: {str(e)}"},
                indent=2,
            )

    async def wp_plugin_update(self, plugin_name: str, dry_run: bool = True) -> str:
        """
        Update WordPress plugin(s) - DRY RUN by default.

        Shows available updates or performs actual update.
        Default behavior is DRY RUN for safety.

        Security:
        - Default: dry_run=True (only shows what would be updated)
        - Before actual update: backup database and files
        - Check plugin compatibility before major version updates

        Args:
            plugin_name: Plugin slug or "all" for all plugins
            dry_run: If True, only show available updates (default: True)

        Returns:
            JSON string with update information or results
        """
        try:
            result = await self.wp_cli.wp_plugin_update(plugin_name=plugin_name, dry_run=dry_run)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update plugin: {str(e)}"}, indent=2
            )

    async def wp_theme_update(self, theme_name: str, dry_run: bool = True) -> str:
        """
        Update WordPress theme(s) - DRY RUN by default.

        Shows available updates or performs actual update.
        Default behavior is DRY RUN for safety.

        Security:
        - Default: dry_run=True (only shows what would be updated)
        - Before actual update: backup database and files
        - Test theme compatibility after updates
        - WARNING: Updating active theme can break site appearance

        Args:
            theme_name: Theme slug or "all" for all themes
            dry_run: If True, only show available updates (default: True)

        Returns:
            JSON string with update information or results
        """
        try:
            result = await self.wp_cli.wp_theme_update(theme_name=theme_name, dry_run=dry_run)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update theme: {str(e)}"}, indent=2
            )

    async def wp_core_update(self, version: str | None = None, dry_run: bool = True) -> str:
        """
        Update WordPress core - DRY RUN by default.

        Shows available updates or performs actual core update.
        Default behavior is DRY RUN for safety.

        Security:
        - Default: dry_run=True (only shows what would be updated)
        - CRITICAL: Always backup database and files before core updates
        - Check plugin/theme compatibility before major version updates
        - Test thoroughly on staging environment first
        - Major version updates may have breaking changes

        Args:
            version: Specific version to update to, or None for latest (default: None)
            dry_run: If True, only show available updates (default: True)

        Returns:
            JSON string with update information or results
        """
        try:
            result = await self.wp_cli.wp_core_update(version=version, dry_run=dry_run)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": str(e), "message": f"Failed to update WordPress core: {str(e)}"}, indent=2
            )
