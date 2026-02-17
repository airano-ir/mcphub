"""
Database Operations Handler

Manages WordPress database operations including:
- Export/Import
- Backup/Restore
- Optimization and Repair
- Search and Query operations

All operations require 'write' or 'admin' scope for security.
"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.wp_cli import WPCLIManager

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # DB Export (already exists in wp_cli.py, documented here for completeness)
        {
            "name": "wp_db_export",
            "method_name": "wp_db_export",
            "description": "Export WordPress database to SQL file. Creates a timestamped backup file in /tmp directory.",
            "schema": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific tables to export (default: all tables)",
                    },
                    "exclude_tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tables to exclude from export",
                    },
                    "add_drop_table": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include DROP TABLE statements",
                    },
                },
            },
            "scope": "write",
        },
        # DB Import
        {
            "name": "wp_db_import",
            "method_name": "wp_db_import",
            "description": "Import database from SQL file. DESTRUCTIVE: replaces current database. Requires admin scope.",
            "schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to SQL file on server"},
                    "url": {"type": "string", "description": "URL to download SQL file from"},
                    "skip_optimization": {
                        "type": "boolean",
                        "default": False,
                        "description": "Skip database optimization after import",
                    },
                },
            },
            "scope": "admin",
        },
        # DB Size Info
        {
            "name": "wp_db_size",
            "method_name": "wp_db_size",
            "description": "Get database size statistics including total size, table sizes, and row counts.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # DB Tables List
        {
            "name": "wp_db_tables",
            "method_name": "wp_db_tables",
            "description": "List all database tables with detailed information (size, engine, rows, collation).",
            "schema": {
                "type": "object",
                "properties": {
                    "prefix_only": {
                        "type": "boolean",
                        "default": True,
                        "description": "Show only WordPress tables (with wp_ prefix)",
                    }
                },
            },
            "scope": "read",
        },
        # DB Search
        {
            "name": "wp_db_search",
            "method_name": "wp_db_search",
            "description": "Search database for specific strings. Useful for finding content, debugging, or data migration.",
            "schema": {
                "type": "object",
                "properties": {
                    "search_string": {"type": "string", "description": "String to search for"},
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific tables to search",
                    },
                    "regex": {
                        "type": "boolean",
                        "default": False,
                        "description": "Use regex pattern matching",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "default": False,
                        "description": "Case-sensitive search",
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000,
                        "description": "Maximum results to return",
                    },
                },
                "required": ["search_string"],
            },
            "scope": "read",
        },
        # DB Query (read-only SELECT)
        {
            "name": "wp_db_query",
            "method_name": "wp_db_query",
            "description": "Execute read-only SQL query (SELECT, SHOW, DESCRIBE only). For advanced users and debugging.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute (SELECT only)",
                    },
                    "max_rows": {
                        "type": "integer",
                        "default": 1000,
                        "minimum": 1,
                        "maximum": 10000,
                        "description": "Maximum rows to return",
                    },
                },
                "required": ["query"],
            },
            "scope": "write",
        },
        # DB Repair
        {
            "name": "wp_db_repair",
            "method_name": "wp_db_repair",
            "description": "Repair corrupted database tables. Runs REPAIR TABLE on all WordPress tables.",
            "schema": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific tables to repair (default: all tables)",
                    }
                },
            },
            "scope": "write",
        },
    ]

class DatabaseHandler:
    """Handles WordPress database operations"""

    def __init__(self, client: WordPressClient, wp_cli: WPCLIManager | None = None):
        """
        Initialize Database Handler

        Args:
            client: WordPress REST API client
            wp_cli: WP-CLI manager (optional, for advanced operations)
        """
        self.client = client
        self.wp_cli = wp_cli
        self.logger = client.logger

    async def wp_db_export(
        self,
        tables: list[str] | None = None,
        exclude_tables: list[str] | None = None,
        add_drop_table: bool = True,
    ) -> dict[str, Any]:
        """
        Export WordPress database to SQL file

        Uses WP-CLI: wp db export
        """
        if not self.wp_cli:
            return {
                "success": False,
                "error": "WP-CLI not available. Container name not configured.",
            }

        try:
            # Build WP-CLI command
            cmd = "db export /tmp/backup-$(date +%Y%m%d-%H%M%S).sql"

            if tables:
                cmd += f" --tables={','.join(tables)}"

            if exclude_tables:
                cmd += f" --exclude_tables={','.join(exclude_tables)}"

            if not add_drop_table:
                cmd += " --no-add-drop-table"

            # Execute export
            result = await self.wp_cli.execute_command(cmd)

            return {
                "success": True,
                "message": "Database exported successfully",
                "file": result.get("output", ""),
                "command": cmd,
            }

        except Exception as e:
            self.logger.error(f"Database export failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def wp_db_import(
        self, file_path: str | None = None, url: str | None = None, skip_optimization: bool = False
    ) -> dict[str, Any]:
        """
        Import database from SQL file

        ⚠️ DESTRUCTIVE OPERATION - Requires admin scope
        """
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        if not file_path and not url:
            return {"success": False, "error": "Either file_path or url is required"}

        try:
            # Download file if URL provided
            if url:
                # Use wget or curl to download
                download_cmd = f"wget -O /tmp/import.sql '{url}'"
                await self.wp_cli.execute_command(f"eval '{download_cmd}'")
                file_path = "/tmp/import.sql"

            # Import database
            cmd = f"db import {file_path}"
            await self.wp_cli.execute_command(cmd)

            # Optimize unless skipped
            if not skip_optimization:
                await self.wp_cli.execute_command("db optimize")

            return {
                "success": True,
                "message": "Database imported successfully",
                "file": file_path,
                "optimized": not skip_optimization,
            }

        except Exception as e:
            self.logger.error(f"Database import failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def wp_db_size(self) -> dict[str, Any]:
        """Get database size statistics"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Get total database size first
            total_query = """
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS total_mb,
                       SUM(table_rows) AS total_rows,
                       COUNT(*) AS table_count
                FROM information_schema.TABLES
                WHERE table_schema = DATABASE()
            """

            total_cmd = f'db query "{total_query}" --skip-column-names'
            total_result = await self.wp_cli.execute_command(total_cmd)

            # Parse tab-separated output
            total_output = total_result.get("output", "0\t0\t0").strip()
            total_parts = total_output.split("\t")

            total_size_mb = (
                float(total_parts[0]) if len(total_parts) > 0 and total_parts[0] else 0.0
            )
            total_rows = int(total_parts[1]) if len(total_parts) > 1 and total_parts[1] else 0
            table_count = int(total_parts[2]) if len(total_parts) > 2 and total_parts[2] else 0

            # Get individual table sizes (top 50 largest tables)
            tables_query = """
                SELECT table_name,
                       ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb,
                       table_rows
                FROM information_schema.TABLES
                WHERE table_schema = DATABASE()
                ORDER BY (data_length + index_length) DESC
                LIMIT 50
            """

            tables_cmd = f'db query "{tables_query}" --skip-column-names'
            tables_result = await self.wp_cli.execute_command(tables_cmd)

            # Parse table results (tab-separated)
            tables_output = tables_result.get("output", "").strip()
            tables = []

            if tables_output:
                for line in tables_output.split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        tables.append(
                            {
                                "table_name": parts[0],
                                "size_mb": float(parts[1]) if parts[1] else 0.0,
                                "table_rows": int(parts[2]) if parts[2] else 0,
                            }
                        )

            return {
                "success": True,
                "total_size_mb": total_size_mb,
                "total_rows": total_rows,
                "table_count": table_count,
                "tables": tables,
                "note": "Showing top 50 largest tables",
            }

        except Exception as e:
            self.logger.error(f"Database size check failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def wp_db_tables(self, prefix_only: bool = True) -> dict[str, Any]:
        """List all database tables with details"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Query for table information
            query = """
                SELECT
                    table_name,
                    engine,
                    table_rows,
                    ROUND((data_length / 1024 / 1024), 2),
                    ROUND((index_length / 1024 / 1024), 2),
                    ROUND(((data_length + index_length) / 1024 / 1024), 2),
                    table_collation
                FROM information_schema.TABLES
                WHERE table_schema = DATABASE()
            """

            if prefix_only:
                # Get WordPress table prefix
                prefix_result = await self.wp_cli.execute_command("config get table_prefix")
                prefix = prefix_result.get("output", "wp_").strip()
                query += f" AND table_name LIKE '{prefix}%'"

            query += " ORDER BY (data_length + index_length) DESC"

            # Use --skip-column-names for MariaDB compatibility (no --format=json)
            cmd = f'db query "{query}" --skip-column-names'
            result = await self.wp_cli.execute_command(cmd)

            # Parse tab-separated output
            tables_output = result.get("output", "").strip()
            tables = []

            if tables_output:
                for line in tables_output.split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        tables.append(
                            {
                                "name": parts[0],
                                "engine": parts[1],
                                "rows": int(parts[2]) if parts[2] and parts[2] != "NULL" else 0,
                                "data_size_mb": (
                                    float(parts[3]) if parts[3] and parts[3] != "NULL" else 0.0
                                ),
                                "index_size_mb": (
                                    float(parts[4]) if parts[4] and parts[4] != "NULL" else 0.0
                                ),
                                "total_size_mb": (
                                    float(parts[5]) if parts[5] and parts[5] != "NULL" else 0.0
                                ),
                                "collation": parts[6] if parts[6] != "NULL" else None,
                            }
                        )

            return {"success": True, "tables": tables, "total": len(tables)}

        except Exception as e:
            self.logger.error(f"Database tables list failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def wp_db_search(
        self,
        search_string: str,
        tables: list[str] | None = None,
        regex: bool = False,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Search database for specific strings"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Build search-replace command in dry-run mode
            cmd = f'search-replace "{search_string}" "{search_string}" --dry-run --format=count'

            if tables:
                cmd += f" {' '.join(tables)}"

            if regex:
                cmd += " --regex"

            if not case_sensitive:
                cmd += " --skip-columns=guid"  # Common practice

            result = await self.wp_cli.execute_command(cmd)

            return {
                "success": True,
                "search_string": search_string,
                "matches_found": result.get("output", "0"),
                "dry_run": True,
            }

        except Exception as e:
            self.logger.error(f"Database search failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def wp_db_query(self, query: str, max_rows: int = 1000) -> dict[str, Any]:
        """
        Execute read-only SQL query

        Security: Only SELECT, SHOW, DESCRIBE queries allowed
        """
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        # Validate query (additional server-side validation)
        query_upper = query.strip().upper()
        allowed_starts = ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")

        if not any(query_upper.startswith(cmd) for cmd in allowed_starts):
            return {
                "success": False,
                "error": "Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries allowed",
            }

        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "REPLACE",
            "GRANT",
            "REVOKE",
        ]

        for keyword in forbidden:
            if keyword in query_upper:
                return {"success": False, "error": f"Forbidden keyword in query: {keyword}"}

        try:
            # Add LIMIT if not present
            if "LIMIT" not in query_upper:
                query = f"{query.rstrip(';')} LIMIT {max_rows}"

            # Execute query with --skip-column-names for MariaDB compatibility
            # First, get column names separately if it's a SELECT
            results = []

            if query_upper.startswith("SELECT"):
                # For SELECT queries, we need to parse the tab-separated output
                cmd = f'db query "{query}" --skip-column-names'
                result = await self.wp_cli.execute_command(cmd)

                # Get output
                output = result.get("output", "").strip()

                if output:
                    # Parse tab-separated values
                    lines = output.split("\n")

                    # For simple queries, try to detect column structure
                    # We'll return as a list of dictionaries with column indices
                    for idx, line in enumerate(lines):
                        values = line.split("\t")
                        # Create a row dict with column indices
                        row = {f"col_{i}": val for i, val in enumerate(values)}
                        results.append(row)

                        # Limit results
                        if idx >= max_rows - 1:
                            break
            else:
                # For SHOW, DESCRIBE, etc., just return raw output
                cmd = f'db query "{query}"'
                result = await self.wp_cli.execute_command(cmd)
                output = result.get("output", "").strip()

                # Return as formatted message
                return {
                    "success": True,
                    "output": output,
                    "query": query,
                    "note": "Results displayed as plain text",
                }

            return {
                "success": True,
                "results": results,
                "row_count": len(results),
                "query": query,
                "note": "Columns are numbered as col_0, col_1, etc. due to MariaDB compatibility mode.",
            }

        except Exception as e:
            self.logger.error(f"Database query failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def wp_db_repair(self, tables: list[str] | None = None) -> dict[str, Any]:
        """Repair corrupted database tables"""
        if not self.wp_cli:
            return {"success": False, "error": "WP-CLI not available"}

        try:
            # Get list of tables to repair
            if not tables:
                # Get all WordPress tables
                table_list = await self.wp_db_tables(prefix_only=True)
                if not table_list.get("success"):
                    return table_list

                tables = [t["name"] for t in table_list.get("tables", [])]

            # Repair each table
            results = []
            for table in tables:
                try:
                    query = f"REPAIR TABLE {table}"
                    cmd = f'db query "{query}" --format=json'
                    result = await self.wp_cli.execute_command(cmd)

                    repair_result = json.loads(result.get("output", "[]"))

                    results.append(
                        {
                            "table": table,
                            "status": "Repaired" if repair_result else "OK",
                            "message": str(repair_result),
                        }
                    )

                except Exception as e:
                    results.append({"table": table, "status": "Failed", "message": str(e)})

            # Count successes/failures
            success_count = sum(1 for r in results if r["status"] != "Failed")
            failed_count = len(results) - success_count

            return {
                "success": True,
                "total_tables": len(results),
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results,
            }

        except Exception as e:
            self.logger.error(f"Database repair failed: {str(e)}")
            return {"success": False, "error": str(e)}
