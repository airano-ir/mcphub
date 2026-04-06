"""Service Handler — manages Coolify services (Docker Compose), lifecycle, and env vars."""

import json
from typing import Any

from plugins.coolify.client import CoolifyClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_services",
            "category": "read",
            "method_name": "list_services",
            "description": "List all Coolify services.",
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
        {
            "name": "get_service",
            "category": "read",
            "method_name": "get_service",
            "description": "Get details of a specific Coolify service by UUID.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "create_service",
            "category": "crud",
            "method_name": "create_service",
            "description": (
                "Create a Coolify service from a predefined template. "
                "Requires project_uuid, server_uuid, environment, and service type."
            ),
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
                    "type": {
                        "type": "string",
                        "description": (
                            "Service type from Coolify templates "
                            "(e.g., 'plausible-analytics', 'minio', 'grafana')"
                        ),
                        "minLength": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Service name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Service description",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately after creation",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "type",
                ],
            },
            "scope": "write",
        },
        {
            "name": "update_service",
            "category": "crud",
            "method_name": "update_service",
            "description": "Update a Coolify service settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Service name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Service description",
                    },
                    "docker_compose_raw": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Raw Docker Compose YAML content",
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "delete_service",
            "category": "system",
            "method_name": "delete_service",
            "description": (
                "Delete a Coolify service permanently. "
                "Optionally clean up volumes and Docker resources."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
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
            "name": "start_service",
            "category": "lifecycle",
            "method_name": "start_service",
            "description": "Start a Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "stop_service",
            "category": "lifecycle",
            "method_name": "stop_service",
            "description": "Stop a running Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "restart_service",
            "category": "lifecycle",
            "method_name": "restart_service",
            "description": "Restart a Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "list_service_envs",
            "category": "read_sensitive",
            "sensitivity": "sensitive",
            "method_name": "list_service_envs",
            "description": "List environment variables for a Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "create_service_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "create_service_env",
            "description": "Create an environment variable for a Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                    "key": {
                        "type": "string",
                        "description": "Environment variable key",
                        "minLength": 1,
                    },
                    "value": {
                        "type": "string",
                        "description": "Environment variable value",
                    },
                    "is_preview": {
                        "type": "boolean",
                        "description": "Preview deployment only",
                        "default": False,
                    },
                },
                "required": ["uuid", "key", "value"],
            },
            "scope": "write",
        },
        {
            "name": "update_service_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "update_service_env",
            "description": "Update an environment variable for a Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                    "key": {
                        "type": "string",
                        "description": "Environment variable key",
                        "minLength": 1,
                    },
                    "value": {
                        "type": "string",
                        "description": "New value",
                    },
                    "is_preview": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Preview deployment only",
                    },
                },
                "required": ["uuid", "key", "value"],
            },
            "scope": "write",
        },
        {
            "name": "update_service_envs_bulk",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "update_service_envs_bulk",
            "description": "Bulk update environment variables for a Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                    "data": {
                        "type": "array",
                        "description": "Array of env var objects with key and value",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                                "is_preview": {"type": "boolean"},
                            },
                            "required": ["key", "value"],
                        },
                    },
                },
                "required": ["uuid", "data"],
            },
            "scope": "write",
        },
        {
            "name": "delete_service_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "delete_service_env",
            "description": "Delete an environment variable from a Coolify service.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Service UUID",
                        "minLength": 1,
                    },
                    "env_uuid": {
                        "type": "string",
                        "description": "Environment variable UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid", "env_uuid"],
            },
            "scope": "write",
        },
    ]


# --- Handler Functions ---


async def list_services(client: CoolifyClient) -> str:
    """List all services."""
    services = await client.list_services()
    result = {"success": True, "count": len(services), "services": services}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_service(client: CoolifyClient, uuid: str) -> str:
    """Get service details."""
    service = await client.get_service(uuid)
    result = {"success": True, "service": service}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_service(client: CoolifyClient, **kwargs) -> str:
    """Create a service from template."""
    data = {k: v for k, v in kwargs.items() if v is not None}
    service = await client.create_service(data)
    result = {
        "success": True,
        "message": "Service created successfully",
        "service": service,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_service(client: CoolifyClient, uuid: str, **kwargs) -> str:
    """Update service settings."""
    data = {k: v for k, v in kwargs.items() if v is not None and k != "uuid"}
    service = await client.update_service(uuid, data)
    result = {
        "success": True,
        "message": f"Service '{uuid}' updated successfully",
        "service": service,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_service(
    client: CoolifyClient,
    uuid: str,
    delete_configurations: bool = True,
    delete_volumes: bool = True,
    docker_cleanup: bool = True,
) -> str:
    """Delete a service."""
    result_data = await client.delete_service(
        uuid,
        delete_configurations=delete_configurations,
        delete_volumes=delete_volumes,
        docker_cleanup=docker_cleanup,
    )
    result = {"success": True, "message": f"Service '{uuid}' deleted", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def start_service(client: CoolifyClient, uuid: str) -> str:
    """Start a service."""
    result_data = await client.start_service(uuid)
    result = {"success": True, "message": f"Service '{uuid}' starting", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def stop_service(client: CoolifyClient, uuid: str) -> str:
    """Stop a service."""
    result_data = await client.stop_service(uuid)
    result = {"success": True, "message": f"Service '{uuid}' stopping", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def restart_service(client: CoolifyClient, uuid: str) -> str:
    """Restart a service."""
    result_data = await client.restart_service(uuid)
    result = {"success": True, "message": f"Service '{uuid}' restarting", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def list_service_envs(client: CoolifyClient, uuid: str) -> str:
    """List service environment variables."""
    envs = await client.list_service_envs(uuid)
    result = {"success": True, "count": len(envs), "envs": envs}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_service_env(
    client: CoolifyClient,
    uuid: str,
    key: str,
    value: str,
    is_preview: bool = False,
) -> str:
    """Create service environment variable."""
    data = {"key": key, "value": value, "is_preview": is_preview}
    result_data = await client.create_service_env(uuid, data)
    result = {
        "success": True,
        "message": f"Env var '{key}' created",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_service_env(
    client: CoolifyClient,
    uuid: str,
    key: str,
    value: str,
    is_preview: bool | None = None,
) -> str:
    """Update service environment variable."""
    data = {"key": key, "value": value}
    if is_preview is not None:
        data["is_preview"] = is_preview
    result_data = await client.update_service_env(uuid, data)
    result = {
        "success": True,
        "message": f"Env var '{key}' updated",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_service_envs_bulk(client: CoolifyClient, uuid: str, data: list[dict]) -> str:
    """Bulk update service environment variables."""
    result_data = await client.update_service_envs_bulk(uuid, data)
    result = {
        "success": True,
        "message": f"Bulk update {len(data)} env vars",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_service_env(client: CoolifyClient, uuid: str, env_uuid: str) -> str:
    """Delete service environment variable."""
    await client.delete_service_env(uuid, env_uuid)
    result = {"success": True, "message": f"Env var '{env_uuid}' deleted"}
    return json.dumps(result, indent=2, ensure_ascii=False)
