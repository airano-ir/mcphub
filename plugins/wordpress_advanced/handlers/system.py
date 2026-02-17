"""
System Operations Handler

Manages WordPress system operations including:
- System information (PHP, MySQL, WordPress versions)
- Disk usage statistics
- Cron job management
- Cache operations
- Error log retrieval

Most operations require WP-CLI for advanced functionality.
"""

import json
import re
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.wp_cli import WPCLIManager


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # System Info
        {
            "name": "system_info",
            "method_name": "system_info",
            "description": "Get comprehensive system information including PHP version, MySQL version, WordPress version, server info, memory limits, and more.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # PHP Info
        {
            "name": "system_phpinfo",
            "method_name": "system_phpinfo",
            "description": "Get detailed PHP configuration including loaded extensions, ini settings, and disabled functions.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # Disk Usage
        {
            "name": "system_disk_usage",
            "method_name": "system_disk_usage",
            "description": "Get disk usage statistics including uploads size, plugins size, themes size, and database size.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # Clear All Caches
        {
            "name": "system_clear_all_caches",
            "method_name": "system_clear_all_caches",
            "description": "Clear all caches including object cache, transients, and opcache (if available). Safe to run anytime.",
            "schema": {"type": "object", "properties": {}},
            "scope": "write",
        },
        # Cron List
        {
            "name": "cron_list",
            "method_name": "cron_list",
            "description": "List all scheduled WordPress cron jobs with schedule, next run time, and arguments.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # Cron Run
        {
            "name": "cron_run",
            "method_name": "cron_run",
            "description": "Manually trigger a specific cron job by hook name. Useful for testing or forcing scheduled tasks.",
            "schema": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string", "description": "Cron hook name to execute"},
                    "args": {
                        "type": "array",
                        "items": {},
                        "default": [],
                        "description": "Optional arguments to pass to the hook",
                    },
                },
                "required": ["hook"],
            },
            "scope": "write",
        },
        # Error Log
        {
            "name": "error_log",
            "method_name": "error_log",
            "description": "Get recent PHP error log entries. Useful for debugging issues. Admin scope recommended for security.",
            "schema": {
                "type": "object",
                "properties": {
                    "lines": {
                        "type": "integer",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000,
                        "description": "Number of log lines to retrieve",
                    },
                    "filter": {
                        "type": "string",
                        "description": "Filter logs by keyword (case-insensitive)",
                    },
                    "level": {
                        "type": "string",
                        "enum": ["error", "warning", "notice", "fatal"],
                        "description": "Filter by error level",
                    },
                },
            },
            "scope": "read",
        },
    ]


class SystemHandler:
    """Handles WordPress system operations"""

    def __init__(self, client: WordPressClient, wp_cli: WPCLIManager | None = None):
        """
        Initialize System Handler

        Args:
            client: WordPress REST API client
            wp_cli: WP-CLI manager (optional, for advanced operations)
        """
        self.client = client
        self.wp_cli = wp_cli
        self.logger = client.logger

    async def wp_cli_version(self) -> dict[str, Any]:
        """Get WP-CLI version information"""
        if not self.wp_cli:
            return {"success": False, "version": None, "error": "WP-CLI not available"}

        try:
            result = await self.wp_cli.execute_command("cli version")
            version_output = result.get("output", "").strip()

            # Parse version (e.g., "WP-CLI 2.10.0")
            version = (
                version_output.replace("WP-CLI ", "").strip()
                if "WP-CLI" in version_output
                else version_output
            )

            return {"success": True, "version": version, "full_output": version_output}

        except Exception as e:
            self.logger.error(f"WP-CLI version check failed: {str(e)}")
            return {"success": False, "version": None, "error": str(e)}

    async def system_info(self) -> dict[str, Any]:
        """Get comprehensive system information"""
        if not self.wp_cli:
            return {
                "success": False,
                "error": "WP-CLI not available. Container name not configured.",
            }

        try:
            # Get various system info using WP-CLI
            info_commands = {
                "php_version": "eval 'echo PHP_VERSION;'",
                "wordpress_version": "core version",
                "site_url": "option get siteurl",
                "active_theme": "theme list --status=active --field=name",
                "plugin_count": "plugin list --status=active --format=count",
                "wp_debug": "config get WP_DEBUG",
                "wp_debug_log": "config get WP_DEBUG_LOG",
                "multisite": "config get MULTISITE",
            }

            results = {}
            for key, cmd in info_commands.items():
                try:
                    result = await self.wp_cli.execute_command(cmd)
                    results[key] = result.get("output", "").strip()
                except Exception as e:
                    self.logger.warning(f"Failed to get {key}: {str(e)}")
                    results[key] = "N/A"

            # Get PHP settings
            php_settings_cmd = """eval 'echo json_encode([
                "memory_limit" => ini_get("memory_limit"),
                "max_execution_time" => ini_get("max_execution_time"),
                "upload_max_filesize" => ini_get("upload_max_filesize"),
                "post_max_size" => ini_get("post_max_size"),
                "max_input_vars" => ini_get("max_input_vars")
            ]);'"""

            php_result = await self.wp_cli.execute_command(php_settings_cmd)
            php_settings = json.loads(php_result.get("output", "{}"))

            # Get MySQL version
            mysql_cmd = 'db query "SELECT VERSION()" --skip-column-names'
            mysql_result = await self.wp_cli.execute_command(mysql_cmd)
            mysql_version = mysql_result.get("output", "N/A").strip()

            # Get server software from environment
            server_cmd = 'eval \'echo $_SERVER["SERVER_SOFTWARE"] ?? "Unknown";\''
            server_result = await self.wp_cli.execute_command(server_cmd)
            server_software = server_result.get("output", "Unknown").strip()

            # Get loaded PHP extensions
            ext_cmd = "eval 'echo json_encode(get_loaded_extensions());'"
            ext_result = await self.wp_cli.execute_command(ext_cmd)
            php_extensions = json.loads(ext_result.get("output", "[]"))

            return {
                "success": True,
                "php_version": results.get("php_version", "N/A"),
                "mysql_version": mysql_version,
                "wordpress_version": results.get("wordpress_version", "N/A"),
                "server_software": server_software,
                "memory_limit": php_settings.get("memory_limit", "N/A"),
                "max_execution_time": int(php_settings.get("max_execution_time", 0)),
                "upload_max_filesize": php_settings.get("upload_max_filesize", "N/A"),
                "post_max_size": php_settings.get("post_max_size", "N/A"),
                "max_input_vars": int(php_settings.get("max_input_vars", 0)),
                "php_extensions": php_extensions,
                "wp_debug": results.get("wp_debug", "false") == "true",
                "wp_debug_log": results.get("wp_debug_log", "false") == "true",
                "multisite": results.get("multisite", "false") == "true",
                "active_plugins": int(results.get("plugin_count", 0)),
                "active_theme": results.get("active_theme", "N/A"),
                "site_url": results.get("site_url", "N/A"),
            }

        except Exception as e:
            self.logger.error(f"System info failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def system_phpinfo(self) -> dict[str, Any]:
        """Get detailed PHP configuration"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Get PHP version and SAPI
            version_cmd = "eval 'echo PHP_VERSION;'"
            version_result = await self.wp_cli.execute_command(version_cmd)
            php_version = version_result.get("output", "").strip()

            sapi_cmd = "eval 'echo PHP_SAPI;'"
            sapi_result = await self.wp_cli.execute_command(sapi_cmd)
            php_sapi = sapi_result.get("output", "").strip()

            # Get loaded extensions
            ext_cmd = "eval 'echo json_encode(get_loaded_extensions());'"
            ext_result = await self.wp_cli.execute_command(ext_cmd)
            extensions = json.loads(ext_result.get("output", "[]"))

            # Get important ini settings
            ini_settings_cmd = """eval 'echo json_encode([
                "display_errors" => ini_get("display_errors"),
                "error_reporting" => ini_get("error_reporting"),
                "log_errors" => ini_get("log_errors"),
                "error_log" => ini_get("error_log"),
                "memory_limit" => ini_get("memory_limit"),
                "max_execution_time" => ini_get("max_execution_time"),
                "upload_max_filesize" => ini_get("upload_max_filesize"),
                "post_max_size" => ini_get("post_max_size"),
                "max_input_vars" => ini_get("max_input_vars"),
                "max_input_time" => ini_get("max_input_time"),
                "default_socket_timeout" => ini_get("default_socket_timeout"),
                "allow_url_fopen" => ini_get("allow_url_fopen"),
                "session.save_handler" => ini_get("session.save_handler")
            ]);'"""

            ini_result = await self.wp_cli.execute_command(ini_settings_cmd)
            ini_settings = json.loads(ini_result.get("output", "{}"))

            # Get disabled functions
            disabled_cmd = "eval 'echo ini_get(\"disable_functions\");'"
            disabled_result = await self.wp_cli.execute_command(disabled_cmd)
            disabled_raw = disabled_result.get("output", "").strip()
            disabled_functions = [f.strip() for f in disabled_raw.split(",") if f.strip()]

            return {
                "success": True,
                "version": php_version,
                "sapi": php_sapi,
                "extensions": extensions,
                "ini_settings": ini_settings,
                "disabled_functions": disabled_functions,
            }

        except Exception as e:
            self.logger.error(f"PHP info failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def system_disk_usage(self) -> dict[str, Any]:
        """Get disk usage statistics"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Get WordPress root path
            path_cmd = "eval 'echo ABSPATH;'"
            path_result = await self.wp_cli.execute_command(path_cmd)
            wp_path = path_result.get("output", "").strip()

            # Get directory sizes using du command
            sizes = {}

            # Uploads directory
            uploads_cmd = f"eval 'echo shell_exec(\"du -sm {wp_path}wp-content/uploads 2>/dev/null | cut -f1\");'"
            try:
                uploads_result = await self.wp_cli.execute_command(uploads_cmd)
                upload_size = uploads_result.get("output", "0").strip()
                sizes["uploads_size_mb"] = (
                    float(upload_size) if upload_size and upload_size != "" else 0.0
                )
            except Exception as e:
                self.logger.warning(f"Failed to get uploads size: {e}")
                sizes["uploads_size_mb"] = 0.0

            # Plugins directory
            plugins_cmd = f"eval 'echo shell_exec(\"du -sm {wp_path}wp-content/plugins 2>/dev/null | cut -f1\");'"
            try:
                plugins_result = await self.wp_cli.execute_command(plugins_cmd)
                plugins_size = plugins_result.get("output", "0").strip()
                sizes["plugins_size_mb"] = (
                    float(plugins_size) if plugins_size and plugins_size != "" else 0.0
                )
            except Exception as e:
                self.logger.warning(f"Failed to get plugins size: {e}")
                sizes["plugins_size_mb"] = 0.0

            # Themes directory
            themes_cmd = f"eval 'echo shell_exec(\"du -sm {wp_path}wp-content/themes 2>/dev/null | cut -f1\");'"
            try:
                themes_result = await self.wp_cli.execute_command(themes_cmd)
                themes_size = themes_result.get("output", "0").strip()
                sizes["themes_size_mb"] = (
                    float(themes_size) if themes_size and themes_size != "" else 0.0
                )
            except Exception as e:
                self.logger.warning(f"Failed to get themes size: {e}")
                sizes["themes_size_mb"] = 0.0

            # Total WordPress directory
            total_cmd = f"eval 'echo shell_exec(\"du -sm {wp_path} 2>/dev/null | cut -f1\");'"
            try:
                total_result = await self.wp_cli.execute_command(total_cmd)
                total_size = total_result.get("output", "0").strip()
                sizes["wordpress_size_mb"] = (
                    float(total_size) if total_size and total_size != "" else 0.0
                )
            except Exception as e:
                self.logger.warning(f"Failed to get wordpress total size: {e}")
                sizes["wordpress_size_mb"] = 0.0

            # Database size (from our database handler logic)
            db_query = """
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
                FROM information_schema.TABLES
                WHERE table_schema = DATABASE()
            """
            db_cmd = f'db query "{db_query}" --skip-column-names'
            try:
                db_result = await self.wp_cli.execute_command(db_cmd)
                sizes["database_size_mb"] = float(db_result.get("output", "0").strip())
            except:
                sizes["database_size_mb"] = 0.0

            # Calculate total
            total_size = sum([sizes["wordpress_size_mb"], sizes["database_size_mb"]])

            return {
                "success": True,
                "total_size_mb": round(total_size, 2),
                **sizes,
                "breakdown": {
                    "uploads": sizes["uploads_size_mb"],
                    "plugins": sizes["plugins_size_mb"],
                    "themes": sizes["themes_size_mb"],
                    "database": sizes["database_size_mb"],
                },
            }

        except Exception as e:
            self.logger.error(f"Disk usage check failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def system_clear_all_caches(self) -> dict[str, Any]:
        """Clear all caches"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            cleared = []

            # Clear object cache
            try:
                await self.wp_cli.execute_command("cache flush")
                cleared.append("object_cache")
            except Exception as e:
                self.logger.warning(f"Object cache flush failed: {str(e)}")

            # Clear transients
            try:
                await self.wp_cli.execute_command("transient delete --all")
                cleared.append("transients")
            except Exception as e:
                self.logger.warning(f"Transient delete failed: {str(e)}")

            # Clear OPcache if available
            try:
                opcache_cmd = 'eval \'if (function_exists("opcache_reset")) { opcache_reset(); echo "cleared"; }\''
                opcache_result = await self.wp_cli.execute_command(opcache_cmd)
                if "cleared" in opcache_result.get("output", ""):
                    cleared.append("opcache")
            except Exception as e:
                self.logger.warning(f"OPcache clear failed: {str(e)}")

            return {
                "success": True,
                "message": f"Cleared {len(cleared)} cache types",
                "cleared": cleared,
            }

        except Exception as e:
            self.logger.error(f"Clear all caches failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def cron_list(self) -> dict[str, Any]:
        """List all WordPress cron jobs"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Get cron events
            cmd = "cron event list --format=json"
            result = await self.wp_cli.execute_command(cmd)

            events_data = json.loads(result.get("output", "[]"))

            # Parse events
            events = []
            for event in events_data:
                events.append(
                    {
                        "hook": event.get("hook", ""),
                        "timestamp": int(event.get("time", 0)),
                        "schedule": event.get("recurrence", "single"),
                        "interval": event.get("interval"),
                        "args": event.get("args", []),
                    }
                )

            # Get available schedules
            schedules_cmd = "cron schedule list --format=json"
            try:
                schedules_result = await self.wp_cli.execute_command(schedules_cmd)
                schedules_data = json.loads(schedules_result.get("output", "[]"))
                schedules = {s.get("name"): s for s in schedules_data}
            except:
                schedules = {}

            return {"success": True, "events": events, "total": len(events), "schedules": schedules}

        except Exception as e:
            self.logger.error(f"Cron list failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def cron_run(self, hook: str, args: list[Any] | None = None) -> dict[str, Any]:
        """Manually run a cron job"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Build command
            cmd = f"cron event run {hook}"

            # Execute cron job
            result = await self.wp_cli.execute_command(cmd)

            return {
                "success": True,
                "message": f"Cron job '{hook}' executed",
                "hook": hook,
                "output": result.get("output", ""),
            }

        except Exception as e:
            self.logger.error(f"Cron run failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def error_log(
        self, lines: int = 100, filter: str | None = None, level: str | None = None
    ) -> dict[str, Any]:
        """Get PHP error log entries"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Get error log path
            log_path_cmd = "eval 'echo ini_get(\"error_log\");'"
            log_path_result = await self.wp_cli.execute_command(log_path_cmd)
            log_path = log_path_result.get("output", "").strip()

            if not log_path or log_path == "":
                # Try WordPress debug log
                wp_path_cmd = "eval 'echo WP_CONTENT_DIR;'"
                wp_path_result = await self.wp_cli.execute_command(wp_path_cmd)
                wp_content = wp_path_result.get("output", "").strip()
                log_path = f"{wp_content}/debug.log"

            # Get log file size
            size_cmd = f"eval 'echo filesize(\"{log_path}\") ?? 0;'"
            try:
                size_result = await self.wp_cli.execute_command(size_cmd)
                log_size_bytes = int(size_result.get("output", "0").strip())
                log_size_mb = round(log_size_bytes / 1024 / 1024, 2)
            except:
                log_size_mb = 0.0

            # Read log file (last N lines)
            tail_cmd = f"eval 'exec(\"tail -n {lines} {log_path} 2>&1\");'"
            log_result = await self.wp_cli.execute_command(tail_cmd)
            log_lines = log_result.get("output", "").strip().split("\n")

            # Parse log entries
            entries = []
            for line in log_lines:
                if not line.strip():
                    continue

                # Basic parsing (PHP error log format varies)
                # Format: [timestamp] PHP Error_Type: message in file on line X
                match = re.match(r"\[([^\]]+)\]\s+PHP\s+(\w+):\s+(.+)", line)

                if match:
                    timestamp, error_type, message = match.groups()

                    # Extract file and line if present
                    file_match = re.search(r"in\s+(.+)\s+on\s+line\s+(\d+)", message)
                    file_path = file_match.group(1) if file_match else None
                    line_num = int(file_match.group(2)) if file_match else None

                    entry = {
                        "timestamp": timestamp,
                        "level": error_type.lower(),
                        "message": message,
                        "file": file_path,
                        "line": line_num,
                    }

                    # Apply filters
                    if level and entry["level"] != level.lower():
                        continue

                    if filter and filter.lower() not in message.lower():
                        continue

                    entries.append(entry)
                else:
                    # Unparsed line - include as-is
                    entries.append(
                        {
                            "timestamp": "N/A",
                            "level": "unknown",
                            "message": line,
                            "file": None,
                            "line": None,
                        }
                    )

            return {
                "success": True,
                "entries": entries,
                "total_lines": len(log_lines),
                "filtered_lines": len(entries),
                "log_size_mb": log_size_mb,
                "log_path": log_path,
            }

        except Exception as e:
            self.logger.error(f"Error log retrieval failed: {str(e)}")
            return {"success": False, "error": str(e)}
