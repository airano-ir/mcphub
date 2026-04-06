"""Application Handler — manages Coolify applications, lifecycle, and env vars."""

import json
from typing import Any

from plugins.coolify.client import CoolifyClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_applications",
            "category": "read",
            "method_name": "list_applications",
            "description": "List all Coolify applications. Optionally filter by tag name.",
            "schema": {
                "type": "object",
                "properties": {
                    "tag": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter by tag name",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_application",
            "category": "read",
            "method_name": "get_application",
            "description": "Get details of a specific Coolify application by UUID.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "create_application_public",
            "category": "crud",
            "method_name": "create_application_public",
            "description": (
                "Create a Coolify application from a public Git repository. "
                "Requires project_uuid, server_uuid, environment, git_repository, "
                "git_branch, build_pack, and ports_exposes."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name (e.g., 'production')",
                    },
                    "git_repository": {
                        "type": "string",
                        "description": "Git repository URL",
                    },
                    "git_branch": {
                        "type": "string",
                        "description": "Git branch name",
                    },
                    "build_pack": {
                        "type": "string",
                        "description": "Build pack type",
                        "enum": ["nixpacks", "static", "dockerfile", "dockercompose"],
                    },
                    "ports_exposes": {
                        "type": "string",
                        "description": "Exposed ports (e.g., '3000')",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
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
                    "git_repository",
                    "git_branch",
                    "build_pack",
                    "ports_exposes",
                ],
            },
            "scope": "write",
        },
        {
            "name": "create_application_dockerfile",
            "category": "crud",
            "method_name": "create_application_dockerfile",
            "description": (
                "Create a Coolify application from a Dockerfile (without git). "
                "Requires project_uuid, server_uuid, environment, and dockerfile content."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name",
                    },
                    "dockerfile": {
                        "type": "string",
                        "description": "Dockerfile content",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "ports_exposes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Exposed ports",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "dockerfile",
                ],
            },
            "scope": "write",
        },
        {
            "name": "create_application_docker_image",
            "category": "crud",
            "method_name": "create_application_docker_image",
            "description": (
                "Create a Coolify application from a Docker image. "
                "Requires project_uuid, server_uuid, environment, "
                "docker_registry_image_name, and ports_exposes."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name",
                    },
                    "docker_registry_image_name": {
                        "type": "string",
                        "description": "Docker image name (e.g., 'nginx')",
                    },
                    "ports_exposes": {
                        "type": "string",
                        "description": "Exposed ports",
                    },
                    "docker_registry_image_tag": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Docker image tag (default: latest)",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "docker_registry_image_name",
                    "ports_exposes",
                ],
            },
            "scope": "write",
        },
        {
            "name": "create_application_compose",
            "category": "crud",
            "method_name": "create_application_compose",
            "description": (
                "Create a Coolify application from Docker Compose. "
                "Note: Deprecated by Coolify — prefer using services instead."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name",
                    },
                    "docker_compose_raw": {
                        "type": "string",
                        "description": "Raw Docker Compose YAML content",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "docker_compose_raw",
                ],
            },
            "scope": "write",
        },
        {
            "name": "update_application",
            "category": "crud",
            "method_name": "update_application",
            "description": (
                "Update a Coolify application settings. Supports name, description, "
                "domains, build settings, health checks, resource limits, and more."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "git_repository": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Git repository URL",
                    },
                    "git_branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Git branch",
                    },
                    "build_pack": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": [
                                    "nixpacks",
                                    "static",
                                    "dockerfile",
                                    "dockercompose",
                                ],
                            },
                            {"type": "null"},
                        ],
                        "description": "Build pack type",
                    },
                    "install_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Install command",
                    },
                    "build_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Build command",
                    },
                    "start_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Start command",
                    },
                    "ports_exposes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Exposed ports",
                    },
                    "is_auto_deploy_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable auto-deploy on push",
                    },
                    "instant_deploy": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Deploy instantly",
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "delete_application",
            "category": "system",
            "method_name": "delete_application",
            "description": (
                "Delete a Coolify application permanently. "
                "Optionally clean up configs, volumes, and networks."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
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
                    "delete_connected_networks": {
                        "type": "boolean",
                        "description": "Delete connected networks",
                        "default": True,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "admin",
        },
        {
            "name": "start_application",
            "category": "lifecycle",
            "method_name": "start_application",
            "description": "Deploy/start a Coolify application. Triggers a new deployment.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force rebuild without cache",
                        "default": False,
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Skip deployment queue",
                        "default": False,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "stop_application",
            "category": "lifecycle",
            "method_name": "stop_application",
            "description": "Stop a running Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "docker_cleanup": {
                        "type": "boolean",
                        "description": "Prune networks and volumes",
                        "default": True,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "restart_application",
            "category": "lifecycle",
            "method_name": "restart_application",
            "description": "Restart a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "get_application_logs",
            "category": "read_sensitive",
            "sensitivity": "sensitive",
            "method_name": "get_application_logs",
            "description": "Get logs for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 10000,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "list_application_envs",
            "category": "read_sensitive",
            "sensitivity": "sensitive",
            "method_name": "list_application_envs",
            "description": "List environment variables for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "create_application_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "create_application_env",
            "description": "Create an environment variable for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
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
                    "is_literal": {
                        "type": "boolean",
                        "description": "Treat as literal (no variable interpolation)",
                        "default": False,
                    },
                    "is_multiline": {
                        "type": "boolean",
                        "description": "Allow multiline value",
                        "default": False,
                    },
                    "is_shown_once": {
                        "type": "boolean",
                        "description": "Show value only once",
                        "default": False,
                    },
                },
                "required": ["uuid", "key", "value"],
            },
            "scope": "write",
        },
        {
            "name": "update_application_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "update_application_env",
            "description": "Update an environment variable for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
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
                    "is_literal": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Treat as literal",
                    },
                    "is_multiline": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Allow multiline",
                    },
                    "is_shown_once": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Show only once",
                    },
                },
                "required": ["uuid", "key", "value"],
            },
            "scope": "write",
        },
        {
            "name": "update_application_envs_bulk",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "update_application_envs_bulk",
            "description": "Bulk update environment variables for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "data": {
                        "type": "array",
                        "description": "Array of env var objects with key, value, and flags",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                                "is_preview": {"type": "boolean"},
                                "is_literal": {"type": "boolean"},
                                "is_multiline": {"type": "boolean"},
                                "is_shown_once": {"type": "boolean"},
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
            "name": "delete_application_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "delete_application_env",
            "description": "Delete an environment variable from a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
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


async def list_applications(client: CoolifyClient, tag: str | None = None) -> str:
    """List all applications."""
    apps = await client.list_applications(tag=tag)
    result = {"success": True, "count": len(apps), "applications": apps}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_application(client: CoolifyClient, uuid: str) -> str:
    """Get application details."""
    app = await client.get_application(uuid)
    result = {"success": True, "application": app}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_public(client: CoolifyClient, **kwargs) -> str:
    """Create application from public repository."""
    app = await client.create_application_public(kwargs)
    result = {
        "success": True,
        "message": "Application created successfully",
        "application": app,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_dockerfile(client: CoolifyClient, **kwargs) -> str:
    """Create application from Dockerfile."""
    app = await client.create_application_dockerfile(kwargs)
    result = {
        "success": True,
        "message": "Application created from Dockerfile",
        "application": app,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_docker_image(client: CoolifyClient, **kwargs) -> str:
    """Create application from Docker image."""
    app = await client.create_application_docker_image(kwargs)
    result = {
        "success": True,
        "message": "Application created from Docker image",
        "application": app,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_compose(client: CoolifyClient, **kwargs) -> str:
    """Create application from Docker Compose."""
    app = await client.create_application_docker_compose(kwargs)
    result = {
        "success": True,
        "message": "Application created from Docker Compose",
        "application": app,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_application(client: CoolifyClient, uuid: str, **kwargs) -> str:
    """Update application settings."""
    data = {k: v for k, v in kwargs.items() if v is not None and k != "uuid"}
    app = await client.update_application(uuid, data)
    result = {
        "success": True,
        "message": f"Application '{uuid}' updated successfully",
        "application": app,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_application(
    client: CoolifyClient,
    uuid: str,
    delete_configurations: bool = True,
    delete_volumes: bool = True,
    docker_cleanup: bool = True,
    delete_connected_networks: bool = True,
) -> str:
    """Delete an application."""
    result_data = await client.delete_application(
        uuid,
        delete_configurations=delete_configurations,
        delete_volumes=delete_volumes,
        docker_cleanup=docker_cleanup,
        delete_connected_networks=delete_connected_networks,
    )
    result = {"success": True, "message": f"Application '{uuid}' deleted", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def start_application(
    client: CoolifyClient,
    uuid: str,
    force: bool = False,
    instant_deploy: bool = False,
) -> str:
    """Deploy/start application."""
    result_data = await client.start_application(uuid, force=force, instant_deploy=instant_deploy)
    result = {
        "success": True,
        "message": f"Application '{uuid}' deployment queued",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def stop_application(client: CoolifyClient, uuid: str, docker_cleanup: bool = True) -> str:
    """Stop application."""
    result_data = await client.stop_application(uuid, docker_cleanup=docker_cleanup)
    result = {"success": True, "message": f"Application '{uuid}' stopping", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def restart_application(client: CoolifyClient, uuid: str) -> str:
    """Restart application."""
    result_data = await client.restart_application(uuid)
    result = {"success": True, "message": f"Application '{uuid}' restarting", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_application_logs(client: CoolifyClient, uuid: str, lines: int = 100) -> str:
    """Get application logs."""
    logs = await client.get_application_logs(uuid, lines=lines)
    result = {"success": True, "logs": logs}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def list_application_envs(client: CoolifyClient, uuid: str) -> str:
    """List application environment variables."""
    envs = await client.list_application_envs(uuid)
    result = {"success": True, "count": len(envs), "envs": envs}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_env(
    client: CoolifyClient,
    uuid: str,
    key: str,
    value: str,
    is_preview: bool = False,
    is_literal: bool = False,
    is_multiline: bool = False,
    is_shown_once: bool = False,
) -> str:
    """Create application environment variable."""
    data = {
        "key": key,
        "value": value,
        "is_preview": is_preview,
        "is_literal": is_literal,
        "is_multiline": is_multiline,
        "is_shown_once": is_shown_once,
    }
    result_data = await client.create_application_env(uuid, data)
    result = {
        "success": True,
        "message": f"Env var '{key}' created",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_application_env(
    client: CoolifyClient,
    uuid: str,
    key: str,
    value: str,
    is_preview: bool | None = None,
    is_literal: bool | None = None,
    is_multiline: bool | None = None,
    is_shown_once: bool | None = None,
) -> str:
    """Update application environment variable."""
    data = {"key": key, "value": value}
    if is_preview is not None:
        data["is_preview"] = is_preview
    if is_literal is not None:
        data["is_literal"] = is_literal
    if is_multiline is not None:
        data["is_multiline"] = is_multiline
    if is_shown_once is not None:
        data["is_shown_once"] = is_shown_once
    result_data = await client.update_application_env(uuid, data)
    result = {
        "success": True,
        "message": f"Env var '{key}' updated",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_application_envs_bulk(client: CoolifyClient, uuid: str, data: list[dict]) -> str:
    """Bulk update application environment variables."""
    result_data = await client.update_application_envs_bulk(uuid, data)
    result = {
        "success": True,
        "message": f"Bulk update {len(data)} env vars",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_application_env(client: CoolifyClient, uuid: str, env_uuid: str) -> str:
    """Delete application environment variable."""
    await client.delete_application_env(uuid, env_uuid)
    result = {"success": True, "message": f"Env var '{env_uuid}' deleted"}
    return json.dumps(result, indent=2, ensure_ascii=False)
