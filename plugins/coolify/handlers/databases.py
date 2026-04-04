"""Database Handler — manages Coolify databases, lifecycle, and backups."""

import json
from typing import Any

from plugins.coolify.client import CoolifyClient


def _create_db_spec(db_type: str, description: str) -> dict[str, Any]:
    """Generate a create_* tool spec for a database type."""
    return {
        "name": f"create_{db_type}",
        "method_name": f"create_{db_type}",
        "description": description,
        "schema": {
            "type": "object",
            "properties": {
                "project_uuid": {
                    "type": "string",
                    "description": "Project UUID",
                    "minLength": 1,
                },
                "server_uuid": {
                    "type": "string",
                    "description": "Server UUID",
                    "minLength": 1,
                },
                "environment_name": {
                    "type": "string",
                    "description": "Environment name (e.g., 'production')",
                    "minLength": 1,
                },
                "name": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "description": "Database name",
                },
                "description": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "description": "Database description",
                },
                "instant_deploy": {
                    "type": "boolean",
                    "description": "Deploy immediately after creation",
                    "default": False,
                },
            },
            "required": ["project_uuid", "server_uuid", "environment_name"],
        },
        "scope": "write",
    }


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    specs = [
        {
            "name": "list_databases",
            "method_name": "list_databases",
            "description": "List all Coolify databases.",
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
        {
            "name": "get_database",
            "method_name": "get_database",
            "description": "Get details of a specific Coolify database by UUID.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Database UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "update_database",
            "method_name": "update_database",
            "description": "Update a Coolify database settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Database UUID",
                        "minLength": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Database name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Database description",
                    },
                    "image": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Docker image",
                    },
                    "is_public": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Make database publicly accessible",
                    },
                    "public_port": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Public port number",
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "delete_database",
            "method_name": "delete_database",
            "description": (
                "Delete a Coolify database permanently. "
                "Optionally clean up volumes and Docker resources."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Database UUID",
                        "minLength": 1,
                    },
                    "delete_configurations": {
                        "type": "boolean",
                        "description": "Delete configurations",
                        "default": True,
                    },
                    "delete_volumes": {
                        "type": "boolean",
                        "description": "Delete volumes",
                        "default": True,
                    },
                    "docker_cleanup": {
                        "type": "boolean",
                        "description": "Run Docker cleanup",
                        "default": True,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "admin",
        },
        {
            "name": "start_database",
            "method_name": "start_database",
            "description": "Start a Coolify database.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Database UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "stop_database",
            "method_name": "stop_database",
            "description": "Stop a running Coolify database.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Database UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "restart_database",
            "method_name": "restart_database",
            "description": "Restart a Coolify database.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Database UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
    ]

    # Add create specs for each database type
    db_types = [
        ("postgresql", "Create a PostgreSQL database on Coolify."),
        ("mysql", "Create a MySQL database on Coolify."),
        ("mariadb", "Create a MariaDB database on Coolify."),
        ("mongodb", "Create a MongoDB database on Coolify."),
        ("redis", "Create a Redis database on Coolify."),
        ("clickhouse", "Create a ClickHouse database on Coolify."),
    ]
    for db_type, desc in db_types:
        specs.append(_create_db_spec(db_type, desc))

    # Backup tools
    specs.extend(
        [
            {
                "name": "get_database_backups",
                "method_name": "get_database_backups",
                "description": "Get backup configuration and history for a Coolify database.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "Database UUID",
                            "minLength": 1,
                        },
                    },
                    "required": ["uuid"],
                },
                "scope": "read",
            },
            {
                "name": "create_database_backup",
                "method_name": "create_database_backup",
                "description": "Create a manual backup of a Coolify database.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "Database UUID",
                            "minLength": 1,
                        },
                    },
                    "required": ["uuid"],
                },
                "scope": "write",
            },
            {
                "name": "list_backup_executions",
                "method_name": "list_backup_executions",
                "description": "List all backup executions across all databases.",
                "schema": {
                    "type": "object",
                    "properties": {},
                },
                "scope": "read",
            },
        ]
    )

    return specs


# --- Handler Functions ---


async def list_databases(client: CoolifyClient) -> str:
    """List all databases."""
    databases = await client.list_databases()
    result = {"success": True, "count": len(databases), "databases": databases}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_database(client: CoolifyClient, uuid: str) -> str:
    """Get database details."""
    db = await client.get_database(uuid)
    result = {"success": True, "database": db}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_database(client: CoolifyClient, uuid: str, **kwargs) -> str:
    """Update database settings."""
    data = {k: v for k, v in kwargs.items() if v is not None and k != "uuid"}
    db = await client.update_database(uuid, data)
    result = {
        "success": True,
        "message": f"Database '{uuid}' updated successfully",
        "database": db,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_database(
    client: CoolifyClient,
    uuid: str,
    delete_configurations: bool = True,
    delete_volumes: bool = True,
    docker_cleanup: bool = True,
) -> str:
    """Delete a database."""
    result_data = await client.delete_database(
        uuid,
        delete_configurations=delete_configurations,
        delete_volumes=delete_volumes,
        docker_cleanup=docker_cleanup,
    )
    result = {"success": True, "message": f"Database '{uuid}' deleted", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def start_database(client: CoolifyClient, uuid: str) -> str:
    """Start a database."""
    result_data = await client.start_database(uuid)
    result = {"success": True, "message": f"Database '{uuid}' starting", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def stop_database(client: CoolifyClient, uuid: str) -> str:
    """Stop a database."""
    result_data = await client.stop_database(uuid)
    result = {"success": True, "message": f"Database '{uuid}' stopping", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def restart_database(client: CoolifyClient, uuid: str) -> str:
    """Restart a database."""
    result_data = await client.restart_database(uuid)
    result = {"success": True, "message": f"Database '{uuid}' restarting", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def _create_database(client: CoolifyClient, db_type: str, **kwargs) -> str:
    """Create a database of given type."""
    data = {k: v for k, v in kwargs.items() if v is not None}
    db = await client.create_database(db_type, data)
    result = {
        "success": True,
        "message": f"{db_type.title()} database created successfully",
        "database": db,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_postgresql(client: CoolifyClient, **kwargs) -> str:
    """Create a PostgreSQL database."""
    return await _create_database(client, "postgresql", **kwargs)


async def create_mysql(client: CoolifyClient, **kwargs) -> str:
    """Create a MySQL database."""
    return await _create_database(client, "mysql", **kwargs)


async def create_mariadb(client: CoolifyClient, **kwargs) -> str:
    """Create a MariaDB database."""
    return await _create_database(client, "mariadb", **kwargs)


async def create_mongodb(client: CoolifyClient, **kwargs) -> str:
    """Create a MongoDB database."""
    return await _create_database(client, "mongodb", **kwargs)


async def create_redis(client: CoolifyClient, **kwargs) -> str:
    """Create a Redis database."""
    return await _create_database(client, "redis", **kwargs)


async def create_clickhouse(client: CoolifyClient, **kwargs) -> str:
    """Create a ClickHouse database."""
    return await _create_database(client, "clickhouse", **kwargs)


async def get_database_backups(client: CoolifyClient, uuid: str) -> str:
    """Get database backups."""
    backups = await client.get_database_backups(uuid)
    result = {"success": True, "backups": backups}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_database_backup(client: CoolifyClient, uuid: str) -> str:
    """Create a manual database backup."""
    result_data = await client.create_database_backup(uuid)
    result = {
        "success": True,
        "message": f"Backup created for database '{uuid}'",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def list_backup_executions(client: CoolifyClient) -> str:
    """List all backup executions."""
    executions = await client.list_backup_executions()
    result = {"success": True, "count": len(executions), "executions": executions}
    return json.dumps(result, indent=2, ensure_ascii=False)
