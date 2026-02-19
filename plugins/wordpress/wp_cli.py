"""
WP-CLI Manager for WordPress Plugin

Provides WP-CLI command execution capabilities for WordPress containers.
Supports cache management, database operations, plugin/theme info, and more.

Security:
- Command validation against whitelist
- Container existence verification
- WP-CLI installation check
- Timeout protection (30s default)
- Graceful error handling
"""

import asyncio
import json
import logging
from typing import Any


class WPCLIManager:
    """
    Manages WP-CLI command execution for WordPress containers.

    This class provides a secure interface to execute WP-CLI commands
    inside WordPress Docker containers via docker exec.

    Attributes:
        container_name: Docker container name (from Coolify)
        logger: Logger instance for this manager
        wp_cli_available: Cached check of WP-CLI availability
    """

    # Whitelist of safe WP-CLI commands (Phase 5.1 + 5.2 + 5.3)
    SAFE_COMMANDS = [
        # Phase 5.1: Cache Management
        "cache flush",
        "cache type",
        "transient delete",
        "transient list",
        # Phase 5.2: Database Operations
        "db check",
        "db optimize",
        "db export",
        # Phase 5.2: Plugin/Theme Info
        "plugin list",
        "theme list",
        "plugin verify-checksums",
        "core verify-checksums",
        # Phase 5.3: Search & Replace (dry-run only)
        "search-replace",
        # Phase 5.3: Update Tools (dry-run mode)
        "plugin update",
        "theme update",
        "core update",
        "core check-update",
    ]

    def __init__(self, container_name: str):
        """
        Initialize WP-CLI Manager.

        Args:
            container_name: Docker container name (e.g., wordpress-xxx-12345)
        """
        self.container_name = container_name
        self.logger = logging.getLogger(f"WPCLIManager.{container_name}")
        self.wp_cli_available: bool | None = None  # Cache WP-CLI check

    async def _check_container_exists(self) -> bool:
        """
        Check if the Docker container exists and is running.

        Returns:
            bool: True if container exists and is running, False otherwise
        """
        try:
            # First, test if we have Docker socket access
            test_cmd = "docker version --format '{{.Server.Version}}'"
            test_process = await asyncio.create_subprocess_shell(
                test_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            test_stdout, test_stderr = await asyncio.wait_for(
                test_process.communicate(), timeout=5.0
            )

            if test_process.returncode != 0:
                error_msg = test_stderr.decode().strip()
                self.logger.warning(
                    f"Docker daemon not accessible for container '{self.container_name}': "
                    f"{error_msg}. WP-CLI features will be unavailable. "
                    f"Mount /var/run/docker.sock to enable WP-CLI."
                )
                return False

            docker_version = test_stdout.decode().strip()
            self.logger.debug(f"Docker access OK - Server version: {docker_version}")

            # Now check for our specific container using exact name match
            # Use --all to include stopped containers and provide better error message
            cmd = f"docker ps --all --filter name=^{self.container_name}$ --format '{{{{.Names}}}}|{{{{.Status}}}}'"

            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

            if process.returncode != 0:
                self.logger.error(f"Docker ps failed: {stderr.decode()}")
                raise Exception(f"Docker ps command failed: {stderr.decode()}")

            # Parse output
            output = stdout.decode().strip()

            if not output:
                # Container not found - get list of available containers for helpful error
                list_cmd = "docker ps --all --format '{{.Names}}' | head -10"
                list_process = await asyncio.create_subprocess_shell(
                    list_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                list_stdout, _ = await list_process.communicate()
                available = list_stdout.decode().strip().split("\n") if list_stdout else []

                raise Exception(
                    f"Container '{self.container_name}' not found or not running. "
                    f"Please verify the container name in your configuration.\n\n"
                    f"Available containers (first 10):\n"
                    + "\n".join(f"  - {name}" for name in available if name)
                )

            # Check container status
            name, status = output.split("|", 1)
            if "Up" not in status:
                raise Exception(
                    f"Container '{self.container_name}' exists but is not running. "
                    f"Status: {status}"
                )

            self.logger.debug(f"Container '{self.container_name}' found and running")
            return True

        except TimeoutError:
            self.logger.warning(
                f"Docker command timed out for container '{self.container_name}'. "
                f"WP-CLI features will be unavailable."
            )
            return False
        except Exception as e:
            self.logger.warning(f"Docker check failed for '{self.container_name}': {e}")
            return False

    async def _check_wp_cli_available(self) -> bool:
        """
        Check if WP-CLI is installed in the container.

        Caches the result to avoid repeated checks.

        Returns:
            bool: True if WP-CLI is available

        Raises:
            Exception: If WP-CLI check fails
        """
        # Return cached result if available
        if self.wp_cli_available is not None:
            return self.wp_cli_available

        try:
            # Try to run wp --version
            cmd = f"docker exec {self.container_name} wp --version --allow-root"

            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

            if process.returncode == 0:
                version = stdout.decode().strip()
                self.logger.info(f"WP-CLI detected: {version}")
                self.wp_cli_available = True
                return True
            else:
                error_msg = stderr.decode().strip()
                self.logger.warning(f"WP-CLI not available: {error_msg}")
                self.wp_cli_available = False
                return False

        except TimeoutError:
            self.logger.error("WP-CLI version check timed out")
            self.wp_cli_available = False
            return False
        except Exception as e:
            self.logger.error(f"Error checking WP-CLI: {e}")
            self.wp_cli_available = False
            return False

    def _is_safe_command(self, command: str) -> bool:
        """
        Validate command against whitelist.

        Args:
            command: WP-CLI command (without 'wp' prefix)

        Returns:
            bool: True if command is in whitelist
        """
        # Check if command starts with any safe command pattern
        return any(command.startswith(safe_cmd) for safe_cmd in self.SAFE_COMMANDS)

    def _parse_wp_cli_output(self, stdout: str, command: str) -> dict[str, Any]:
        """
        Parse WP-CLI command output with consistent structure.

        Attempts to parse JSON output. Falls back to plain text if not JSON.
        ALWAYS returns a dict with consistent keys for handlers to use.

        Args:
            stdout: Command stdout
            command: Original command (for context)

        Returns:
            Dict: Parsed output with consistent structure:
                - "output": text output (for handlers using .get("output"))
                - "data": parsed JSON data (if JSON array/primitive)
                - "raw_output": original stdout
                - "message": message text (for non-JSON)
        """
        stdout = stdout.strip()

        # Try to parse as JSON
        try:
            parsed = json.loads(stdout)

            # Always return a dict with consistent structure
            if isinstance(parsed, dict):
                # If it's already a dict, add output/raw_output if not present
                if "output" not in parsed:
                    parsed["output"] = stdout
                if "raw_output" not in parsed:
                    parsed["raw_output"] = stdout
                return parsed
            elif isinstance(parsed, list):
                # Wrap list in dict - handlers expect dict
                return {"data": parsed, "output": stdout, "raw_output": stdout}
            else:
                # Primitive types (string, number, bool, null)
                return {"data": parsed, "output": str(parsed), "raw_output": stdout}
        except json.JSONDecodeError:
            # Not JSON, return as plain text
            return {"output": stdout, "message": stdout, "raw_output": stdout}

    async def _execute_wp_cli(
        self, command: str, timeout: float = 30.0, force_allow: bool = False
    ) -> dict[str, Any]:
        """
        Execute WP-CLI command in WordPress container.

        Args:
            command: WP-CLI command (without 'wp' prefix)
            timeout: Command timeout in seconds (default: 30s)
            force_allow: Skip safety check (use with caution)

        Returns:
            Dict: Parsed command output

        Raises:
            Exception: On execution errors or validation failures
        """
        # 1. Validate command safety
        if not force_allow and not self._is_safe_command(command):
            raise Exception(
                f"Command '{command}' is not in the safe commands whitelist. "
                f"Allowed: {', '.join(self.SAFE_COMMANDS)}"
            )

        # 2. Check container exists
        if not await self._check_container_exists():
            raise Exception(
                f"Container '{self.container_name}' not found or not running. "
                f"Please verify the container name in your configuration."
            )

        # 3. Check WP-CLI is available
        if not await self._check_wp_cli_available():
            raise Exception(
                f"WP-CLI is not installed in container '{self.container_name}'. "
                f"Please install WP-CLI in your WordPress container."
            )

        # 4. Build docker exec command
        docker_cmd = f"docker exec {self.container_name} wp {command} --allow-root"

        self.logger.info(f"Executing: {docker_cmd}")

        try:
            # 5. Execute command
            process = await asyncio.create_subprocess_shell(
                docker_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            # 6. Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            # 7. Check exit code
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"WP-CLI command failed: {error_msg}")
                raise Exception(f"WP-CLI error: {error_msg}")

            # 8. Parse and return output
            output = stdout.decode()
            result = self._parse_wp_cli_output(output, command)

            self.logger.debug(f"Command succeeded: {command}")
            return result

        except TimeoutError:
            self.logger.error(f"Command timed out after {timeout}s: {command}")
            raise Exception(
                f"WP-CLI command timed out after {timeout} seconds. "
                f"The operation may be taking too long."
            )
        except Exception as e:
            # Re-raise with context
            if "WP-CLI" in str(e) or "Container" in str(e):
                raise  # Already formatted
            else:
                raise Exception(f"Failed to execute WP-CLI command: {str(e)}")

    async def execute_command(
        self, command: str, timeout: float = 30.0, force_allow: bool = True
    ) -> dict[str, Any]:
        """
        Public wrapper for executing WP-CLI commands.

        Used by database and system handlers to execute custom WP-CLI commands.

        Args:
            command: WP-CLI command (without 'wp' prefix)
            timeout: Command timeout in seconds (default: 30s)
            force_allow: Skip safety check (default: True for custom commands)

        Returns:
            Dict with command output and status
        """
        return await self._execute_wp_cli(command, timeout, force_allow)

    # =========================================================================
    # Phase 5.1: Cache Management Tools (4 tools)
    # =========================================================================

    async def wp_cache_flush(self) -> dict[str, Any]:
        """
        Flush WordPress object cache.

        Clears all cached objects from the object cache (Redis, Memcached, or file).
        Safe to run anytime - will not affect database or content.

        Returns:
            Dict with status and message

        Example:
            {"status": "success", "message": "Cache flushed successfully."}
        """
        result = await self._execute_wp_cli("cache flush")

        # WP-CLI cache flush returns plain text message
        return {
            "status": "success",
            "message": result.get("message", "Cache flushed successfully"),
            "container": self.container_name,
        }

    async def wp_cache_type(self) -> dict[str, Any]:
        """
        Get the object cache type being used.

        Shows which caching backend is active (e.g., Redis, Memcached, file-based).

        Returns:
            Dict with cache type information

        Example:
            {"cache_type": "redis", "status": "active"}
        """
        result = await self._execute_wp_cli("cache type")

        # Extract cache type from message
        cache_type = result.get("message", "").strip().lower()

        return {
            "cache_type": cache_type or "file",
            "status": "active",
            "container": self.container_name,
            "raw_output": result.get("message", ""),
        }

    async def wp_transient_delete_all(self) -> dict[str, Any]:
        """
        Delete all expired transients from the database.

        Transients are temporary cached data stored in the WordPress database.
        This command only deletes expired transients, improving database performance.

        Returns:
            Dict with count of deleted transients

        Example:
            {"deleted_count": 145, "status": "success"}
        """
        result = await self._execute_wp_cli("transient delete --all --expired")

        # Parse the output message to extract count
        message = result.get("message", "")
        deleted_count = 0

        # Try to extract number from message like "Deleted 145 transients"
        import re

        match = re.search(r"(\d+)", message)
        if match:
            deleted_count = int(match.group(1))

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": message,
            "container": self.container_name,
        }

    async def wp_transient_list(self) -> dict[str, Any]:
        """
        List transients in the database (limited to first 100).

        Shows transient keys with their expiration times.
        Useful for debugging caching issues.

        Note: Output is limited to 100 transients to avoid overwhelming responses.
        Use wp_transient_delete_all to clean up if there are many expired transients.

        Returns:
            Dict with total count and list of transients (max 100)

        Example:
            {
                "total": 230,
                "showing": 100,
                "transients": [
                    {"key": "feed_abc123", "expiration": "2025-01-11 12:00:00"},
                    ...
                ],
                "note": "Showing first 100 of 230 transients"
            }
        """
        result = await self._execute_wp_cli("transient list --format=json")

        # WP-CLI returns JSON array of transients
        transients = result if isinstance(result, list) else []
        total = len(transients)

        # Limit to first 100 to avoid overwhelming responses
        limited_transients = transients[:100]

        response = {
            "total": total,
            "showing": len(limited_transients),
            "transients": limited_transients,
            "container": self.container_name,
        }

        # Add note if we're showing a limited subset
        if total > 100:
            response["note"] = (
                f"Showing first 100 of {total} transients. Use wp_transient_delete_all to clean up expired ones."
            )

        return response

    # =========================================================================
    # Phase 5.2: Database Operations (3 tools)
    # =========================================================================

    async def wp_db_check(self) -> dict[str, Any]:
        """
        Check WordPress database for errors.

        Runs database integrity checks to ensure tables are healthy.
        Safe to run - read-only operation.

        Returns:
            Dict with health status and tables checked

        Example:
            {"status": "healthy", "tables_checked": 45}
        """
        result = await self._execute_wp_cli("db check")

        # Parse output message
        message = result.get("message", "")

        # Check if there are any errors mentioned
        has_errors = "error" in message.lower() or "corrupt" in message.lower()

        # Try to count tables from message
        import re

        tables_checked = 0
        # Look for patterns like "45 tables" or "Checked 45 tables"
        match = re.search(r"(\d+)\s+table", message, re.IGNORECASE)
        if match:
            tables_checked = int(match.group(1))

        return {
            "status": "issues_found" if has_errors else "healthy",
            "tables_checked": tables_checked,
            "message": message,
            "container": self.container_name,
        }

    async def wp_db_optimize(self) -> dict[str, Any]:
        """
        Optimize WordPress database tables.

        Runs OPTIMIZE TABLE on all WordPress tables to reclaim space
        and improve performance. Safe operation - non-destructive.

        Returns:
            Dict with optimization results

        Example:
            {"optimized_tables": 12, "message": "Database optimized"}
        """
        result = await self._execute_wp_cli("db optimize")

        # Parse output to count optimized tables
        message = result.get("message", "")

        import re

        optimized_count = 0
        # Look for success indicators or table counts
        match = re.search(r"(\d+)", message)
        if match:
            optimized_count = int(match.group(1))

        return {
            "status": "success",
            "optimized_tables": optimized_count,
            "message": message,
            "container": self.container_name,
        }

    async def wp_db_export(self) -> dict[str, Any]:
        """
        Export WordPress database to SQL file in /tmp.

        Creates a database backup in the /tmp directory with timestamp.
        Safe - exports are only saved to /tmp for security.

        Returns:
            Dict with export file path and size

        Example:
            {"file_path": "/tmp/backup-20250110_120000.sql", "size": "15.2 MB"}
        """
        from datetime import datetime

        # Create timestamped filename in /tmp (secure location)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = f"/tmp/backup-{timestamp}.sql"

        # Execute export with 60s timeout (larger databases)
        result = await self._execute_wp_cli(f"db export {export_path}", timeout=60.0)

        message = result.get("message", "")

        # Get file size if export succeeded
        # Try to check file size via docker exec
        try:
            size_cmd = f"docker exec {self.container_name} stat -f %z {export_path} 2>/dev/null || docker exec {self.container_name} stat -c %s {export_path} 2>/dev/null"

            process = await asyncio.create_subprocess_shell(
                size_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5.0)

            if process.returncode == 0:
                size_bytes = int(stdout.decode().strip())
                # Convert to human readable
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = "unknown"
        except (ValueError, IndexError, OSError):
            size_str = "unknown"

        return {
            "status": "success",
            "file_path": export_path,
            "size": size_str,
            "message": message,
            "container": self.container_name,
            "note": "Backup saved in container's /tmp directory. Copy out if needed for long-term storage.",
        }

    # =========================================================================
    # Phase 5.2: Plugin/Theme Info (4 tools)
    # =========================================================================

    async def wp_plugin_list_detailed(self) -> dict[str, Any]:
        """
        List all WordPress plugins with detailed information.

        Shows plugin names, versions, status (active/inactive), and available updates.
        Useful for inventory management and update planning.

        Returns:
            Dict with total count and plugin list

        Example:
            {
                "total": 23,
                "plugins": [
                    {
                        "name": "woocommerce",
                        "status": "active",
                        "version": "8.2.1",
                        "update": "8.3.0"
                    }
                ]
            }
        """
        result = await self._execute_wp_cli("plugin list --format=json")

        # WP-CLI returns JSON array of plugins
        plugins = result if isinstance(result, list) else []

        return {"total": len(plugins), "plugins": plugins, "container": self.container_name}

    async def wp_theme_list_detailed(self) -> dict[str, Any]:
        """
        List all WordPress themes with detailed information.

        Shows theme names, versions, status, and identifies the active theme.
        Useful for theme management and updates.

        Returns:
            Dict with total count, theme list, and active theme

        Example:
            {
                "total": 5,
                "themes": [...],
                "active_theme": "storefront"
            }
        """
        result = await self._execute_wp_cli("theme list --format=json")

        # WP-CLI returns JSON array of themes
        themes = result if isinstance(result, list) else []

        # Find active theme
        active_theme = None
        for theme in themes:
            if theme.get("status") == "active":
                active_theme = theme.get("name")
                break

        return {
            "total": len(themes),
            "themes": themes,
            "active_theme": active_theme,
            "container": self.container_name,
        }

    async def wp_plugin_verify_checksums(self) -> dict[str, Any]:
        """
        Verify plugin file integrity against WordPress.org checksums.

        Checks all plugins against official checksums to detect tampering or corruption.
        Important security tool for detecting malware or unauthorized modifications.

        Note: Only works for plugins from WordPress.org repository.
        Premium/custom plugins will be skipped.

        Returns:
            Dict with verification results (limited output)

        Example:
            {
                "verified": 20,
                "failed": 2,
                "skipped": 3,
                "details": "..."
            }
        """
        result = await self._execute_wp_cli("plugin verify-checksums --all", timeout=60.0)

        message = result.get("message", "")

        # Parse the message to extract counts
        import re

        # Count verified plugins (success lines)
        verified = len(re.findall(r"Success:", message))

        # Count failed plugins (error/warning lines)
        failed = len(re.findall(r"Error:|Warning:|mismatch", message, re.IGNORECASE))

        # Check for skipped plugins
        skipped = len(re.findall(r"skipped|not found|unable to verify", message, re.IGNORECASE))

        # Limit message length to avoid token overflow
        if len(message) > 2000:
            message = message[:2000] + f"...\n[Truncated - original length: {len(message)} chars]"

        return {
            "status": "verified" if failed == 0 else "issues_found",
            "verified": verified,
            "failed": failed,
            "skipped": skipped,
            "details": message,
            "container": self.container_name,
            "note": "Only plugins from WordPress.org can be verified. Premium/custom plugins are skipped.",
        }

    async def wp_core_verify_checksums(self) -> dict[str, Any]:
        """
        Verify WordPress core files against official checksums.

        Checks WordPress core files for tampering, corruption, or unauthorized modifications.
        Critical security tool for ensuring WordPress integrity.

        Returns:
            Dict with verification status and any modified files

        Example:
            {
                "status": "verified",
                "modified_files": [],
                "message": "Success: WordPress installation is verified."
            }
        """
        result = await self._execute_wp_cli("core verify-checksums")

        message = result.get("message", "")

        # Check if verification succeeded
        is_verified = "success" in message.lower() and "error" not in message.lower()

        # Extract modified files if any
        modified_files = []
        import re

        # Look for file paths in error messages
        file_matches = re.findall(r"File should not exist: (.+)", message)
        file_matches.extend(re.findall(r"File doesn\'t verify against checksum: (.+)", message))
        modified_files = file_matches[:50]  # Limit to first 50 files

        # Limit message length
        if len(message) > 2000:
            message = message[:2000] + f"...\n[Truncated - original length: {len(message)} chars]"

        return {
            "status": "verified" if is_verified else "issues_found",
            "modified_files": modified_files,
            "modified_count": len(file_matches),
            "message": message,
            "container": self.container_name,
        }

    # =========================================================================
    # Phase 5.3: Search & Replace + Update Tools (4 tools)
    # =========================================================================

    async def wp_search_replace_dry_run(
        self, old_string: str, new_string: str, tables: list[str] | None = None
    ) -> dict[str, Any]:
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
            Dict with preview of changes

        Example:
            {
                "dry_run": true,
                "tables_affected": 12,
                "replacements": 145,
                "old_string": "old.com",
                "new_string": "new.com",
                "warning": "This is a DRY RUN. No changes were made."
            }
        """
        # Validate inputs
        if not old_string or not new_string:
            raise Exception("Both old_string and new_string are required")

        if len(old_string) > 500 or len(new_string) > 500:
            raise Exception("Search/replace strings must be under 500 characters")

        # Build command - ALWAYS with --dry-run
        # Note: search-replace outputs table format by default, we'll parse it
        cmd_parts = ["search-replace", f"'{old_string}'", f"'{new_string}'", "--dry-run"]

        # Add specific tables if provided
        if tables:
            cmd_parts.extend(tables)

        command = " ".join(cmd_parts)

        # Execute with longer timeout for large databases
        result = await self._execute_wp_cli(command, timeout=60.0)

        # Parse the plain text output
        message = result.get("message", "") if isinstance(result, dict) else str(result)

        # Try to extract statistics from the output
        import re

        tables_affected = 0
        total_replacements = 0

        # Look for patterns like "Success: Made X replacements in Y tables."
        # or count table lines in output
        success_match = re.search(
            r"Success.*?(\d+)\s+replacement.*?(\d+)\s+table", message, re.IGNORECASE
        )
        if success_match:
            total_replacements = int(success_match.group(1))
            tables_affected = int(success_match.group(2))
        else:
            # Count table names in output (each table is usually listed)
            table_lines = re.findall(r"^\s*\w+_\w+", message, re.MULTILINE)
            tables_affected = len(table_lines)

        return {
            "dry_run": True,
            "status": "preview",
            "tables_affected": tables_affected,
            "replacements": total_replacements,
            "old_string": old_string,
            "new_string": new_string,
            "output": message[:1000] if len(message) > 1000 else message,  # Limit output
            "warning": "⚠️ This is a DRY RUN. No changes were made to the database.",
            "note": "To apply these changes, backup your database and use WP-CLI directly.",
            "container": self.container_name,
        }

    async def wp_plugin_update(self, plugin_name: str, dry_run: bool = True) -> dict[str, Any]:
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
            Dict with update information or results

        Example (dry_run=True):
            {
                "plugin": "woocommerce",
                "current_version": "8.2.1",
                "available_version": "8.3.0",
                "update_type": "minor",
                "dry_run": true,
                "status": "update_available"
            }

        Example (dry_run=False):
            {
                "plugin": "woocommerce",
                "old_version": "8.2.1",
                "new_version": "8.3.0",
                "status": "updated"
            }
        """
        # Validate plugin name
        if not plugin_name:
            raise Exception("Plugin name is required")

        if dry_run:
            # Get current plugin info
            plugins_result = await self.wp_plugin_list_detailed()
            plugins = plugins_result.get("plugins", [])

            if plugin_name == "all":
                # Show all plugins with available updates
                updates_available = [
                    p for p in plugins if p.get("update") not in [None, "none", ""]
                ]

                return {
                    "dry_run": True,
                    "status": "preview",
                    "total_plugins": len(plugins),
                    "updates_available": len(updates_available),
                    "plugins": updates_available,
                    "warning": "⚠️ DRY RUN: No updates were applied.",
                    "note": "Set dry_run=false and backup first to apply updates.",
                    "container": self.container_name,
                }
            else:
                # Find specific plugin
                plugin_info = next((p for p in plugins if p.get("name") == plugin_name), None)

                if not plugin_info:
                    raise Exception(f"Plugin '{plugin_name}' not found")

                has_update = plugin_info.get("update") not in [None, "none", ""]

                return {
                    "dry_run": True,
                    "status": "update_available" if has_update else "up_to_date",
                    "plugin": plugin_name,
                    "current_version": plugin_info.get("version"),
                    "available_version": plugin_info.get("update") if has_update else None,
                    "warning": "⚠️ DRY RUN: No updates were applied." if has_update else None,
                    "note": (
                        "Set dry_run=false and backup first to apply update."
                        if has_update
                        else "Plugin is up to date."
                    ),
                    "container": self.container_name,
                }
        else:
            # Actual update - DANGEROUS!
            # Execute update command
            command = f"plugin update {plugin_name} --format=json"
            result = await self._execute_wp_cli(command, timeout=120.0)

            # Parse result
            if isinstance(result, list):
                # Multiple plugins updated
                return {
                    "dry_run": False,
                    "status": "updated",
                    "updated_count": len(result),
                    "plugins": result,
                    "warning": "⚠️ LIVE UPDATE: Changes were applied to production!",
                    "reminder": "Verify site functionality and check for errors.",
                    "container": self.container_name,
                }
            else:
                # Single plugin or message
                return {
                    "dry_run": False,
                    "status": "updated",
                    "message": result.get("message", "Update completed"),
                    "warning": "⚠️ LIVE UPDATE: Changes were applied to production!",
                    "container": self.container_name,
                }

    async def wp_theme_update(self, theme_name: str, dry_run: bool = True) -> dict[str, Any]:
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
            Dict with update information or results

        Example (dry_run=True):
            {
                "theme": "storefront",
                "current_version": "4.3.0",
                "available_version": "4.4.0",
                "is_active": true,
                "dry_run": true,
                "status": "update_available"
            }
        """
        # Validate theme name
        if not theme_name:
            raise Exception("Theme name is required")

        if dry_run:
            # Get current theme info
            themes_result = await self.wp_theme_list_detailed()
            themes = themes_result.get("themes", [])
            active_theme = themes_result.get("active_theme")

            if theme_name == "all":
                # Show all themes with available updates
                updates_available = [
                    {**t, "is_active": t.get("name") == active_theme}
                    for t in themes
                    if t.get("update") not in [None, "none", ""]
                ]

                return {
                    "dry_run": True,
                    "status": "preview",
                    "total_themes": len(themes),
                    "updates_available": len(updates_available),
                    "themes": updates_available,
                    "warning": "⚠️ DRY RUN: No updates were applied.",
                    "note": "Set dry_run=false and backup first to apply updates.",
                    "container": self.container_name,
                }
            else:
                # Find specific theme
                theme_info = next((t for t in themes if t.get("name") == theme_name), None)

                if not theme_info:
                    raise Exception(f"Theme '{theme_name}' not found")

                has_update = theme_info.get("update") not in [None, "none", ""]
                is_active = theme_name == active_theme

                result = {
                    "dry_run": True,
                    "status": "update_available" if has_update else "up_to_date",
                    "theme": theme_name,
                    "current_version": theme_info.get("version"),
                    "available_version": theme_info.get("update") if has_update else None,
                    "is_active": is_active,
                    "container": self.container_name,
                }

                if has_update:
                    if is_active:
                        result["warning"] = (
                            "⚠️ WARNING: This is the ACTIVE theme. Updating may affect site appearance!"
                        )
                    result["note"] = "Set dry_run=false and backup first to apply update."
                else:
                    result["note"] = "Theme is up to date."

                return result
        else:
            # Actual update - DANGEROUS!
            # Execute update command
            command = f"theme update {theme_name} --format=json"
            result = await self._execute_wp_cli(command, timeout=120.0)

            # Parse result
            if isinstance(result, list):
                # Multiple themes updated
                return {
                    "dry_run": False,
                    "status": "updated",
                    "updated_count": len(result),
                    "themes": result,
                    "warning": "⚠️ LIVE UPDATE: Changes were applied to production!",
                    "reminder": "Check site appearance and verify theme functionality.",
                    "container": self.container_name,
                }
            else:
                # Single theme or message
                return {
                    "dry_run": False,
                    "status": "updated",
                    "message": result.get("message", "Update completed"),
                    "warning": "⚠️ LIVE UPDATE: Changes were applied to production!",
                    "container": self.container_name,
                }

    async def wp_core_update(
        self, version: str | None = None, dry_run: bool = True
    ) -> dict[str, Any]:
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
            Dict with update information or results

        Example (dry_run=True):
            {
                "current_version": "6.4.2",
                "available_version": "6.4.3",
                "update_type": "minor",
                "dry_run": true,
                "status": "update_available",
                "warning": "⚠️ CRITICAL: Backup required before core updates!"
            }

        Example (dry_run=False):
            {
                "old_version": "6.4.2",
                "new_version": "6.4.3",
                "update_type": "minor",
                "status": "updated",
                "warning": "⚠️ LIVE UPDATE: WordPress core was updated!"
            }
        """
        if dry_run:
            # Check for available updates
            result = await self._execute_wp_cli("core check-update --format=json")

            # Parse result
            if isinstance(result, list) and len(result) > 0:
                # Updates available
                update_info = result[0]  # First update (usually latest stable)

                current_version = update_info.get("version", "unknown")
                available_version = update_info.get("version", "unknown")
                update_type = update_info.get("update_type", "minor")

                # If version parameter specified, check if it's available
                if version:
                    matching_update = next((u for u in result if u.get("version") == version), None)
                    if matching_update:
                        available_version = matching_update.get("version")
                        update_type = matching_update.get("update_type", "minor")
                    else:
                        return {
                            "dry_run": True,
                            "status": "version_not_found",
                            "requested_version": version,
                            "available_updates": result,
                            "message": f"Version {version} not found in available updates.",
                            "container": self.container_name,
                        }

                # Determine severity
                is_major = update_type == "major"

                response = {
                    "dry_run": True,
                    "status": "update_available",
                    "current_version": current_version,
                    "available_version": available_version,
                    "update_type": update_type,
                    "is_major_update": is_major,
                    "container": self.container_name,
                }

                if is_major:
                    response["warning"] = (
                        "⚠️ CRITICAL: MAJOR VERSION UPDATE! Breaking changes possible!"
                    )
                    response["note"] = (
                        "Test on staging first. Check plugin/theme compatibility. Backup everything!"
                    )
                else:
                    response["warning"] = "⚠️ CRITICAL: Backup required before core updates!"
                    response["note"] = "Set dry_run=false and ensure backups exist to apply update."

                return response
            else:
                # No updates available
                # Get current version from site info
                try:
                    site_cmd = "core version"
                    version_result = await self._execute_wp_cli(site_cmd)
                    current_version = version_result.get("message", "unknown").strip()
                except Exception:
                    current_version = "unknown"

                return {
                    "dry_run": True,
                    "status": "up_to_date",
                    "current_version": current_version,
                    "message": "WordPress is up to date.",
                    "container": self.container_name,
                }
        else:
            # Actual update - EXTREMELY DANGEROUS!
            # Build update command
            if version:
                command = f"core update --version={version} --format=json"
            else:
                command = "core update --format=json"

            # Get current version before update
            try:
                version_result = await self._execute_wp_cli("core version")
                old_version = version_result.get("message", "unknown").strip()
            except Exception:
                old_version = "unknown"

            # Execute update (long timeout for downloads)
            result = await self._execute_wp_cli(command, timeout=180.0)

            # Get new version after update
            try:
                version_result = await self._execute_wp_cli("core version")
                new_version = version_result.get("message", "unknown").strip()
            except Exception:
                new_version = "unknown"

            # Determine update type
            update_type = "minor"
            if old_version != "unknown" and new_version != "unknown":
                old_major = old_version.split(".")[0] if "." in old_version else "0"
                new_major = new_version.split(".")[0] if "." in new_version else "0"
                if old_major != new_major:
                    update_type = "major"

            return {
                "dry_run": False,
                "status": "updated",
                "old_version": old_version,
                "new_version": new_version,
                "update_type": update_type,
                "message": result.get("message", "WordPress core updated successfully."),
                "warning": "⚠️ CRITICAL: WordPress core was UPDATED in production!",
                "reminder": "IMMEDIATELY verify: site loads, admin works, plugins active, theme displays correctly.",
                "container": self.container_name,
            }
