"""Admin Handler - manages Supabase database administration via postgres-meta"""

import json
from typing import Any

from plugins.supabase.client import SupabaseClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (12 tools)"""
    return [
        # Extension Management
        {
            "name": "enable_extension",
            "method_name": "enable_extension",
            "description": "Enable a PostgreSQL extension (e.g., pgvector, postgis, uuid-ossp).",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Extension name to enable"},
                    "schema": {
                        "type": "string",
                        "description": "Schema to install extension in",
                        "default": "extensions",
                    },
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        {
            "name": "disable_extension",
            "method_name": "disable_extension",
            "description": "Disable (drop) a PostgreSQL extension.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Extension name to disable"},
                    "cascade": {
                        "type": "boolean",
                        "description": "Drop dependent objects",
                        "default": False,
                    },
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        # RLS Policy Management
        {
            "name": "create_policy",
            "method_name": "create_policy",
            "description": "Create a Row Level Security (RLS) policy on a table.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "name": {"type": "string", "description": "Policy name"},
                    "definition": {
                        "type": "string",
                        "description": "USING clause expression (e.g., 'auth.uid() = user_id')",
                    },
                    "check": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "WITH CHECK clause expression (for INSERT/UPDATE)",
                    },
                    "command": {
                        "type": "string",
                        "enum": ["ALL", "SELECT", "INSERT", "UPDATE", "DELETE"],
                        "description": "Command this policy applies to",
                        "default": "ALL",
                    },
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Roles this policy applies to",
                        "default": ["authenticated"],
                    },
                    "schema": {"type": "string", "default": "public"},
                },
                "required": ["table", "name", "definition"],
            },
            "scope": "admin",
        },
        {
            "name": "update_policy",
            "method_name": "update_policy",
            "description": "Update an existing RLS policy. Drops and recreates the policy.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "name": {"type": "string", "description": "Policy name to update"},
                    "definition": {"type": "string", "description": "New USING clause expression"},
                    "check": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New WITH CHECK clause expression",
                    },
                    "command": {
                        "type": "string",
                        "enum": ["ALL", "SELECT", "INSERT", "UPDATE", "DELETE"],
                        "default": "ALL",
                    },
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["authenticated"],
                    },
                    "schema": {"type": "string", "default": "public"},
                },
                "required": ["table", "name", "definition"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_policy",
            "method_name": "delete_policy",
            "description": "Delete an RLS policy from a table.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "name": {"type": "string", "description": "Policy name to delete"},
                    "schema": {"type": "string", "default": "public"},
                },
                "required": ["table", "name"],
            },
            "scope": "admin",
        },
        # RLS Table Management
        {
            "name": "enable_rls",
            "method_name": "enable_rls",
            "description": "Enable Row Level Security on a table.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "schema": {"type": "string", "default": "public"},
                },
                "required": ["table"],
            },
            "scope": "admin",
        },
        {
            "name": "disable_rls",
            "method_name": "disable_rls",
            "description": "Disable Row Level Security on a table. Warning: This removes all RLS protection.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "schema": {"type": "string", "default": "public"},
                },
                "required": ["table"],
            },
            "scope": "admin",
        },
        # Table Management
        {
            "name": "create_table",
            "method_name": "create_table",
            "description": "Create a new database table with specified columns.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Table name"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "nullable": {"type": "boolean", "default": True},
                                "default": {"type": "string"},
                                "primary_key": {"type": "boolean", "default": False},
                            },
                            "required": ["name", "type"],
                        },
                        "description": "Column definitions",
                    },
                    "schema": {"type": "string", "default": "public"},
                    "enable_rls": {
                        "type": "boolean",
                        "description": "Enable RLS on the new table",
                        "default": True,
                    },
                },
                "required": ["name", "columns"],
            },
            "scope": "admin",
        },
        {
            "name": "drop_table",
            "method_name": "drop_table",
            "description": "Drop (delete) a database table. Warning: This is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Table name to drop"},
                    "schema": {"type": "string", "default": "public"},
                    "cascade": {
                        "type": "boolean",
                        "description": "Drop dependent objects",
                        "default": False,
                    },
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        # Column Management
        {
            "name": "add_column",
            "method_name": "add_column",
            "description": "Add a new column to an existing table.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "column_name": {"type": "string", "description": "New column name"},
                    "column_type": {
                        "type": "string",
                        "description": "PostgreSQL data type (e.g., 'text', 'integer', 'uuid')",
                    },
                    "nullable": {"type": "boolean", "default": True},
                    "default_value": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Default value expression",
                    },
                    "schema": {"type": "string", "default": "public"},
                },
                "required": ["table", "column_name", "column_type"],
            },
            "scope": "admin",
        },
        {
            "name": "drop_column",
            "method_name": "drop_column",
            "description": "Remove a column from a table.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "column_name": {"type": "string", "description": "Column name to drop"},
                    "schema": {"type": "string", "default": "public"},
                    "cascade": {"type": "boolean", "default": False},
                },
                "required": ["table", "column_name"],
            },
            "scope": "admin",
        },
        # Database Stats
        {
            "name": "get_database_size",
            "method_name": "get_database_size",
            "description": "Get the size of the database and tables.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]

# =====================
# Admin Operations (12 tools)
# =====================

async def enable_extension(client: SupabaseClient, name: str, schema: str = "extensions") -> str:
    """Enable a PostgreSQL extension"""
    try:
        query = f'CREATE EXTENSION IF NOT EXISTS "{name}" SCHEMA "{schema}";'
        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"Extension '{name}' enabled in schema '{schema}'",
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def disable_extension(client: SupabaseClient, name: str, cascade: bool = False) -> str:
    """Disable (drop) a PostgreSQL extension"""
    try:
        cascade_sql = "CASCADE" if cascade else ""
        query = f'DROP EXTENSION IF EXISTS "{name}" {cascade_sql};'
        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"Extension '{name}' disabled",
                "cascade": cascade,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_policy(
    client: SupabaseClient,
    table: str,
    name: str,
    definition: str,
    check: str | None = None,
    command: str = "ALL",
    roles: list[str] | None = None,
    schema: str = "public",
) -> str:
    """Create an RLS policy"""
    try:
        if roles is None:
            roles = ["authenticated"]

        roles_sql = ", ".join(roles)
        check_sql = f"WITH CHECK ({check})" if check else ""

        query = f"""
        CREATE POLICY "{name}" ON "{schema}"."{table}"
        FOR {command}
        TO {roles_sql}
        USING ({definition})
        {check_sql};
        """

        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"Policy '{name}' created on table '{table}'",
                "table": f"{schema}.{table}",
                "policy": {
                    "name": name,
                    "command": command,
                    "roles": roles,
                    "using": definition,
                    "check": check,
                },
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_policy(
    client: SupabaseClient,
    table: str,
    name: str,
    definition: str,
    check: str | None = None,
    command: str = "ALL",
    roles: list[str] | None = None,
    schema: str = "public",
) -> str:
    """Update an RLS policy by dropping and recreating"""
    try:
        # First drop the existing policy
        drop_query = f'DROP POLICY IF EXISTS "{name}" ON "{schema}"."{table}";'
        await client.execute_sql(drop_query)

        # Then create the new one
        return await create_policy(
            client=client,
            table=table,
            name=name,
            definition=definition,
            check=check,
            command=command,
            roles=roles,
            schema=schema,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_policy(
    client: SupabaseClient, table: str, name: str, schema: str = "public"
) -> str:
    """Delete an RLS policy"""
    try:
        query = f'DROP POLICY IF EXISTS "{name}" ON "{schema}"."{table}";'
        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"Policy '{name}' deleted from table '{table}'",
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def enable_rls(client: SupabaseClient, table: str, schema: str = "public") -> str:
    """Enable RLS on a table"""
    try:
        query = f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY;'
        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"RLS enabled on table '{schema}.{table}'",
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def disable_rls(client: SupabaseClient, table: str, schema: str = "public") -> str:
    """Disable RLS on a table"""
    try:
        query = f'ALTER TABLE "{schema}"."{table}" DISABLE ROW LEVEL SECURITY;'
        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"RLS disabled on table '{schema}.{table}'",
                "warning": "Table is now accessible without RLS protection",
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_table(
    client: SupabaseClient,
    name: str,
    columns: list[dict],
    schema: str = "public",
    enable_rls: bool = True,
) -> str:
    """Create a new database table"""
    try:
        # Build column definitions
        col_defs = []
        for col in columns:
            col_def = f'"{col["name"]}" {col["type"]}'

            if col.get("primary_key"):
                col_def += " PRIMARY KEY"

            if not col.get("nullable", True):
                col_def += " NOT NULL"

            if "default" in col:
                col_def += f' DEFAULT {col["default"]}'

            col_defs.append(col_def)

        columns_sql = ",\n  ".join(col_defs)

        query = f"""
        CREATE TABLE "{schema}"."{name}" (
          {columns_sql}
        );
        """

        result = await client.execute_sql(query)

        # Enable RLS if requested
        if enable_rls:
            rls_query = f'ALTER TABLE "{schema}"."{name}" ENABLE ROW LEVEL SECURITY;'
            await client.execute_sql(rls_query)

        return json.dumps(
            {
                "success": True,
                "message": f"Table '{schema}.{name}' created",
                "columns": columns,
                "rls_enabled": enable_rls,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def drop_table(
    client: SupabaseClient, name: str, schema: str = "public", cascade: bool = False
) -> str:
    """Drop a database table"""
    try:
        cascade_sql = "CASCADE" if cascade else ""
        query = f'DROP TABLE IF EXISTS "{schema}"."{name}" {cascade_sql};'
        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"Table '{schema}.{name}' dropped",
                "cascade": cascade,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def add_column(
    client: SupabaseClient,
    table: str,
    column_name: str,
    column_type: str,
    nullable: bool = True,
    default_value: str | None = None,
    schema: str = "public",
) -> str:
    """Add a column to a table"""
    try:
        nullable_sql = "" if nullable else "NOT NULL"
        default_sql = f"DEFAULT {default_value}" if default_value else ""

        query = f"""
        ALTER TABLE "{schema}"."{table}"
        ADD COLUMN "{column_name}" {column_type} {nullable_sql} {default_sql};
        """

        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"Column '{column_name}' added to table '{schema}.{table}'",
                "column": {
                    "name": column_name,
                    "type": column_type,
                    "nullable": nullable,
                    "default": default_value,
                },
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def drop_column(
    client: SupabaseClient,
    table: str,
    column_name: str,
    schema: str = "public",
    cascade: bool = False,
) -> str:
    """Drop a column from a table"""
    try:
        cascade_sql = "CASCADE" if cascade else ""
        query = f"""
        ALTER TABLE "{schema}"."{table}"
        DROP COLUMN "{column_name}" {cascade_sql};
        """

        result = await client.execute_sql(query)

        return json.dumps(
            {
                "success": True,
                "message": f"Column '{column_name}' dropped from table '{schema}.{table}'",
                "cascade": cascade,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_database_size(client: SupabaseClient) -> str:
    """Get database and table sizes"""
    try:
        # Get database size
        db_query = """
        SELECT
            pg_database.datname AS database_name,
            pg_size_pretty(pg_database_size(pg_database.datname)) AS size
        FROM pg_database
        WHERE pg_database.datname = current_database();
        """

        db_result = await client.execute_sql(db_query)

        # Get table sizes
        tables_query = """
        SELECT
            schemaname AS schema,
            tablename AS table,
            pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
            pg_size_pretty(pg_relation_size(schemaname || '.' || tablename)) AS data_size,
            pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename) - pg_relation_size(schemaname || '.' || tablename)) AS index_size
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
        LIMIT 20;
        """

        tables_result = await client.execute_sql(tables_query)

        return json.dumps(
            {
                "success": True,
                "database": db_result[0] if db_result else {},
                "top_tables": tables_result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
