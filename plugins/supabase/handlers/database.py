"""Database Handler - manages Supabase database operations via PostgREST and postgres-meta"""

import json
from typing import Any

from plugins.supabase.client import SupabaseClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (18 tools)"""
    return [
        # =====================
        # PostgREST Operations (6)
        # =====================
        {
            "name": "query_table",
            "method_name": "query_table",
            "description": "Query data from a table with filters, sorting, and pagination. Uses PostgREST operators: eq, neq, gt, gte, lt, lte, like, ilike, in, is, cs (contains), cd (contained).",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name to query"},
                    "select": {
                        "type": "string",
                        "description": "Columns to select (default: *). Use * for all, or comma-separated list",
                        "default": "*",
                    },
                    "filters": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "column": {"type": "string"},
                                        "operator": {
                                            "type": "string",
                                            "enum": [
                                                "eq",
                                                "neq",
                                                "gt",
                                                "gte",
                                                "lt",
                                                "lte",
                                                "like",
                                                "ilike",
                                                "in",
                                                "is",
                                                "cs",
                                                "cd",
                                            ],
                                        },
                                        "value": {},
                                    },
                                    "required": ["column", "value"],
                                },
                            },
                            {"type": "null"},
                        ],
                        "description": "Filter conditions. Each filter has column, operator (default: eq), and value",
                    },
                    "order": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Order by clause (e.g., 'created_at.desc' or 'name.asc')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows to return",
                        "default": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of rows to skip for pagination",
                        "default": 0,
                    },
                    "use_service_role": {
                        "type": "boolean",
                        "description": "Use service_role key to bypass RLS policies",
                        "default": False,
                    },
                },
                "required": ["table"],
            },
            "scope": "read",
        },
        {
            "name": "insert_rows",
            "method_name": "insert_rows",
            "description": "Insert one or more rows into a table. Supports upsert mode for insert-or-update operations.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "rows": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of row objects to insert",
                    },
                    "upsert": {
                        "type": "boolean",
                        "description": "Enable upsert mode (insert or update on conflict)",
                        "default": False,
                    },
                    "on_conflict": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Column(s) to check for conflict (for upsert)",
                    },
                    "use_service_role": {
                        "type": "boolean",
                        "description": "Use service_role key to bypass RLS policies",
                        "default": False,
                    },
                },
                "required": ["table", "rows"],
            },
            "scope": "write",
        },
        {
            "name": "update_rows",
            "method_name": "update_rows",
            "description": "Update rows matching filter conditions. Always requires at least one filter to prevent accidental full-table updates.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "data": {"type": "object", "description": "Fields to update with new values"},
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {
                                    "type": "string",
                                    "enum": [
                                        "eq",
                                        "neq",
                                        "gt",
                                        "gte",
                                        "lt",
                                        "lte",
                                        "like",
                                        "ilike",
                                        "in",
                                        "is",
                                    ],
                                },
                                "value": {},
                            },
                            "required": ["column", "value"],
                        },
                        "description": "Filter conditions to match rows for update",
                        "minItems": 1,
                    },
                    "use_service_role": {
                        "type": "boolean",
                        "description": "Use service_role key to bypass RLS policies",
                        "default": False,
                    },
                },
                "required": ["table", "data", "filters"],
            },
            "scope": "write",
        },
        {
            "name": "delete_rows",
            "method_name": "delete_rows",
            "description": "Delete rows matching filter conditions. Always requires at least one filter to prevent accidental full-table deletion.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {
                                    "type": "string",
                                    "enum": [
                                        "eq",
                                        "neq",
                                        "gt",
                                        "gte",
                                        "lt",
                                        "lte",
                                        "like",
                                        "ilike",
                                        "in",
                                        "is",
                                    ],
                                },
                                "value": {},
                            },
                            "required": ["column", "value"],
                        },
                        "description": "Filter conditions to match rows for deletion",
                        "minItems": 1,
                    },
                    "use_service_role": {
                        "type": "boolean",
                        "description": "Use service_role key to bypass RLS policies",
                        "default": False,
                    },
                },
                "required": ["table", "filters"],
            },
            "scope": "write",
        },
        {
            "name": "execute_rpc",
            "method_name": "execute_rpc",
            "description": "Execute a stored procedure or database function via RPC. Functions must be exposed through PostgREST.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the stored procedure/function",
                    },
                    "params": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Parameters to pass to the function",
                    },
                    "use_service_role": {
                        "type": "boolean",
                        "description": "Use service_role key to bypass RLS policies",
                        "default": False,
                    },
                },
                "required": ["function_name"],
            },
            "scope": "write",
        },
        {
            "name": "count_rows",
            "method_name": "count_rows",
            "description": "Count rows in a table, optionally matching filter conditions.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {"type": "string"},
                                "value": {},
                            },
                            "required": ["column", "value"],
                        },
                        "description": "Optional filter conditions (omit for full count)",
                        "default": [],
                    },
                    "use_service_role": {
                        "type": "boolean",
                        "description": "Use service_role key to bypass RLS policies",
                        "default": False,
                    },
                },
                "required": ["table"],
            },
            "scope": "read",
        },
        # =====================
        # Admin Operations via postgres-meta (12)
        # =====================
        {
            "name": "list_tables",
            "method_name": "list_tables",
            "description": "List all tables in the database with pagination. Returns table names, schemas, and basic metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": "Schema to list tables from",
                        "default": "public",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum tables to return (default: 50)",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of tables to skip for pagination",
                        "default": 0,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_table_schema",
            "method_name": "get_table_schema",
            "description": "Get detailed schema information for a table including all columns, data types, constraints, and defaults.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "schema": {"type": "string", "description": "Schema name", "default": "public"},
                },
                "required": ["table"],
            },
            "scope": "read",
        },
        {
            "name": "list_schemas",
            "method_name": "list_schemas",
            "description": "List all database schemas (namespaces).",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "list_extensions",
            "method_name": "list_extensions",
            "description": "List installed PostgreSQL extensions (e.g., pgvector, postgis, uuid-ossp).",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "list_policies",
            "method_name": "list_policies",
            "description": "List Row Level Security (RLS) policies. Can filter by table name.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter policies for specific table",
                    }
                },
            },
            "scope": "read",
        },
        {
            "name": "list_roles",
            "method_name": "list_roles",
            "description": "List all database roles with their attributes and permissions.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "list_triggers",
            "method_name": "list_triggers",
            "description": "List database triggers. Can filter by table name.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter triggers for specific table",
                    }
                },
            },
            "scope": "read",
        },
        {
            "name": "list_functions",
            "method_name": "list_functions",
            "description": "List database functions/stored procedures in a schema with pagination.",
            "schema": {
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": "Schema to list functions from",
                        "default": "public",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum functions to return (default: 50)",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of functions to skip for pagination",
                        "default": 0,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "execute_sql",
            "method_name": "execute_sql",
            "description": "Execute raw SQL query. Use with caution - bypasses RLS. Returns query results.",
            "schema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "SQL query to execute"}},
                "required": ["query"],
            },
            "scope": "admin",
        },
        {
            "name": "get_table_indexes",
            "method_name": "get_table_indexes",
            "description": "Get indexes for a table including primary keys, unique constraints, and custom indexes.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "schema": {"type": "string", "description": "Schema name", "default": "public"},
                },
                "required": ["table"],
            },
            "scope": "read",
        },
        {
            "name": "get_table_constraints",
            "method_name": "get_table_constraints",
            "description": "Get all constraints (primary key, foreign key, unique, check) for a table.",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "schema": {"type": "string", "description": "Schema name", "default": "public"},
                },
                "required": ["table"],
            },
            "scope": "read",
        },
        {
            "name": "get_table_relationships",
            "method_name": "get_table_relationships",
            "description": "Get foreign key relationships for a table (both references to and from this table).",
            "schema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "schema": {"type": "string", "description": "Schema name", "default": "public"},
                },
                "required": ["table"],
            },
            "scope": "read",
        },
    ]

# =====================
# PostgREST Operations (6)
# =====================

async def query_table(
    client: SupabaseClient,
    table: str,
    select: str = "*",
    filters: list[dict] | None = None,
    order: str | None = None,
    limit: int = 100,
    offset: int = 0,
    use_service_role: bool = False,
) -> str:
    """Query data from a table"""
    try:
        result = await client.query_table(
            table=table,
            select=select,
            filters=filters,
            order=order,
            limit=limit,
            offset=offset,
            use_service_role=use_service_role,
        )

        return json.dumps(
            {
                "success": True,
                "table": table,
                "count": len(result) if isinstance(result, list) else 1,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def insert_rows(
    client: SupabaseClient,
    table: str,
    rows: list[dict],
    upsert: bool = False,
    on_conflict: str | None = None,
    use_service_role: bool = False,
) -> str:
    """Insert rows into a table"""
    try:
        result = await client.insert_rows(
            table=table,
            rows=rows,
            upsert=upsert,
            on_conflict=on_conflict,
            use_service_role=use_service_role,
        )

        return json.dumps(
            {
                "success": True,
                "table": table,
                "inserted": len(result) if isinstance(result, list) else 1,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_rows(
    client: SupabaseClient,
    table: str,
    data: dict,
    filters: list[dict],
    use_service_role: bool = False,
) -> str:
    """Update rows in a table"""
    try:
        if not filters:
            return json.dumps(
                {
                    "success": False,
                    "error": "At least one filter is required to prevent accidental full-table updates",
                },
                indent=2,
                ensure_ascii=False,
            )

        result = await client.update_rows(
            table=table, data=data, filters=filters, use_service_role=use_service_role
        )

        return json.dumps(
            {
                "success": True,
                "table": table,
                "updated": len(result) if isinstance(result, list) else 1,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_rows(
    client: SupabaseClient, table: str, filters: list[dict], use_service_role: bool = False
) -> str:
    """Delete rows from a table"""
    try:
        if not filters:
            return json.dumps(
                {
                    "success": False,
                    "error": "At least one filter is required to prevent accidental full-table deletion",
                },
                indent=2,
                ensure_ascii=False,
            )

        result = await client.delete_rows(
            table=table, filters=filters, use_service_role=use_service_role
        )

        return json.dumps(
            {
                "success": True,
                "table": table,
                "deleted": len(result) if isinstance(result, list) else 1,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def execute_rpc(
    client: SupabaseClient,
    function_name: str,
    params: dict | None = None,
    use_service_role: bool = False,
) -> str:
    """Execute a stored procedure/function"""
    try:
        result = await client.execute_rpc(
            function_name=function_name, params=params, use_service_role=use_service_role
        )

        return json.dumps(
            {"success": True, "function": function_name, "result": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def count_rows(
    client: SupabaseClient,
    table: str,
    filters: list[dict] | None = None,
    use_service_role: bool = False,
) -> str:
    """Count rows in a table"""
    try:
        count = await client.count_rows(
            table=table, filters=filters, use_service_role=use_service_role
        )

        return json.dumps(
            {
                "success": True,
                "table": table,
                "count": count,
                "filters_applied": len(filters) if filters else 0,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

# =====================
# Admin Operations via postgres-meta (12)
# =====================

async def list_tables(
    client: SupabaseClient, schema: str = "public", limit: int = 50, offset: int = 0
) -> str:
    """List all tables in the database with pagination"""
    try:
        result = await client.list_tables(schema=schema)

        # Filter by schema if needed
        if isinstance(result, list):
            tables = [t for t in result if t.get("schema") == schema]
        else:
            tables = result if result else []

        # Apply pagination
        total_count = len(tables)
        paginated = tables[offset : offset + limit] if isinstance(tables, list) else tables

        return json.dumps(
            {
                "success": True,
                "schema": schema,
                "total_count": total_count,
                "count": len(paginated) if isinstance(paginated, list) else 0,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
                "tables": paginated,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_table_schema(client: SupabaseClient, table: str, schema: str = "public") -> str:
    """Get table schema/columns"""
    try:
        result = await client.get_table_schema(table=table, schema=schema)

        return json.dumps(
            {
                "success": True,
                "table": table,
                "schema": schema,
                "columns": result.get("columns", []),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_schemas(client: SupabaseClient) -> str:
    """List all database schemas"""
    try:
        result = await client.list_schemas()

        return json.dumps(
            {
                "success": True,
                "count": len(result) if isinstance(result, list) else 0,
                "schemas": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_extensions(client: SupabaseClient) -> str:
    """List installed extensions"""
    try:
        result = await client.list_extensions()

        return json.dumps(
            {
                "success": True,
                "count": len(result) if isinstance(result, list) else 0,
                "extensions": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_policies(client: SupabaseClient, table: str | None = None) -> str:
    """List RLS policies"""
    try:
        result = await client.list_policies(table=table)

        return json.dumps(
            {
                "success": True,
                "table_filter": table,
                "count": len(result) if isinstance(result, list) else 0,
                "policies": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_roles(client: SupabaseClient) -> str:
    """List database roles"""
    try:
        result = await client.list_roles()

        return json.dumps(
            {
                "success": True,
                "count": len(result) if isinstance(result, list) else 0,
                "roles": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_triggers(client: SupabaseClient, table: str | None = None) -> str:
    """List database triggers"""
    try:
        result = await client.list_triggers(table=table)

        return json.dumps(
            {
                "success": True,
                "table_filter": table,
                "count": len(result) if isinstance(result, list) else 0,
                "triggers": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_functions(
    client: SupabaseClient, schema: str = "public", limit: int = 50, offset: int = 0
) -> str:
    """List database functions with pagination"""
    try:
        result = await client.list_functions(schema=schema)

        # Apply pagination
        functions = result if isinstance(result, list) else []
        total_count = len(functions)
        paginated = functions[offset : offset + limit]

        return json.dumps(
            {
                "success": True,
                "schema": schema,
                "total_count": total_count,
                "count": len(paginated),
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
                "functions": paginated,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def execute_sql(client: SupabaseClient, query: str) -> str:
    """Execute raw SQL query"""
    try:
        result = await client.execute_sql(query=query)

        return json.dumps(
            {
                "success": True,
                "query": query[:200] + "..." if len(query) > 200 else query,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_table_indexes(client: SupabaseClient, table: str, schema: str = "public") -> str:
    """Get indexes for a table"""
    try:
        query = f"""
        SELECT
            i.relname AS index_name,
            a.attname AS column_name,
            am.amname AS index_type,
            ix.indisunique AS is_unique,
            ix.indisprimary AS is_primary
        FROM
            pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_am am ON am.oid = i.relam
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
        WHERE
            t.relname = '{table}'
            AND n.nspname = '{schema}'
        ORDER BY i.relname;
        """
        result = await client.execute_sql(query=query)

        return json.dumps(
            {"success": True, "table": table, "schema": schema, "indexes": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_table_constraints(client: SupabaseClient, table: str, schema: str = "public") -> str:
    """Get constraints for a table"""
    try:
        query = f"""
        SELECT
            con.conname AS constraint_name,
            con.contype AS constraint_type,
            CASE con.contype
                WHEN 'p' THEN 'PRIMARY KEY'
                WHEN 'f' THEN 'FOREIGN KEY'
                WHEN 'u' THEN 'UNIQUE'
                WHEN 'c' THEN 'CHECK'
                WHEN 'x' THEN 'EXCLUSION'
            END AS constraint_type_name,
            pg_get_constraintdef(con.oid) AS definition
        FROM
            pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE
            rel.relname = '{table}'
            AND nsp.nspname = '{schema}'
        ORDER BY con.contype;
        """
        result = await client.execute_sql(query=query)

        return json.dumps(
            {"success": True, "table": table, "schema": schema, "constraints": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_table_relationships(
    client: SupabaseClient, table: str, schema: str = "public"
) -> str:
    """Get foreign key relationships for a table"""
    try:
        # Get foreign keys from this table
        outgoing_query = f"""
        SELECT
            con.conname AS constraint_name,
            att.attname AS column_name,
            ref_class.relname AS referenced_table,
            ref_att.attname AS referenced_column
        FROM
            pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
            JOIN pg_class ref_class ON ref_class.oid = con.confrelid
            JOIN pg_attribute ref_att ON ref_att.attrelid = con.confrelid AND ref_att.attnum = ANY(con.confkey)
        WHERE
            con.contype = 'f'
            AND rel.relname = '{table}'
            AND nsp.nspname = '{schema}';
        """

        # Get foreign keys referencing this table
        incoming_query = f"""
        SELECT
            con.conname AS constraint_name,
            src_class.relname AS source_table,
            att.attname AS source_column,
            ref_att.attname AS referenced_column
        FROM
            pg_constraint con
            JOIN pg_class src_class ON src_class.oid = con.conrelid
            JOIN pg_class ref_class ON ref_class.oid = con.confrelid
            JOIN pg_namespace nsp ON nsp.oid = ref_class.relnamespace
            JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
            JOIN pg_attribute ref_att ON ref_att.attrelid = con.confrelid AND ref_att.attnum = ANY(con.confkey)
        WHERE
            con.contype = 'f'
            AND ref_class.relname = '{table}'
            AND nsp.nspname = '{schema}';
        """

        outgoing = await client.execute_sql(query=outgoing_query)
        incoming = await client.execute_sql(query=incoming_query)

        return json.dumps(
            {
                "success": True,
                "table": table,
                "schema": schema,
                "outgoing_references": outgoing,
                "incoming_references": incoming,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
