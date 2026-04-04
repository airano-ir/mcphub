"""Project & Environment Handler — manages Coolify projects and environments."""

import json
from typing import Any

from plugins.coolify.client import CoolifyClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_projects",
            "method_name": "list_projects",
            "description": "List all Coolify projects.",
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
        {
            "name": "get_project",
            "method_name": "get_project",
            "description": "Get details of a specific Coolify project by UUID.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Project UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "create_project",
            "method_name": "create_project",
            "description": (
                "Create a new Coolify project. "
                "Projects group applications, databases, and services."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Project name",
                        "minLength": 1,
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project description",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_project",
            "method_name": "update_project",
            "description": "Update a Coolify project name or description.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Project UUID",
                        "minLength": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New project name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New project description",
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "delete_project",
            "method_name": "delete_project",
            "description": (
                "Delete a Coolify project permanently. "
                "All resources in the project will be removed."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Project UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "admin",
        },
        {
            "name": "list_environments",
            "method_name": "list_environments",
            "description": "List all environments in a Coolify project.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                        "minLength": 1,
                    },
                },
                "required": ["project_uuid"],
            },
            "scope": "read",
        },
        {
            "name": "get_environment",
            "method_name": "get_environment",
            "description": ("Get details of a specific environment in a Coolify project by name."),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                        "minLength": 1,
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name (e.g., 'production')",
                        "minLength": 1,
                    },
                },
                "required": ["project_uuid", "environment_name"],
            },
            "scope": "read",
        },
        {
            "name": "create_environment",
            "method_name": "create_environment",
            "description": "Create a new environment in a Coolify project.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                        "minLength": 1,
                    },
                    "name": {
                        "type": "string",
                        "description": "Environment name",
                        "minLength": 1,
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Environment description",
                    },
                },
                "required": ["project_uuid", "name"],
            },
            "scope": "write",
        },
    ]


# --- Handler Functions ---


async def list_projects(client: CoolifyClient) -> str:
    """List all projects."""
    projects = await client.list_projects()
    result = {"success": True, "count": len(projects), "projects": projects}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_project(client: CoolifyClient, uuid: str) -> str:
    """Get project details."""
    project = await client.get_project(uuid)
    result = {"success": True, "project": project}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_project(client: CoolifyClient, name: str, description: str | None = None) -> str:
    """Create a new project."""
    data = {"name": name}
    if description is not None:
        data["description"] = description
    project = await client.create_project(data)
    result = {
        "success": True,
        "message": "Project created successfully",
        "project": project,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_project(
    client: CoolifyClient,
    uuid: str,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Update project settings."""
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    project = await client.update_project(uuid, data)
    result = {
        "success": True,
        "message": f"Project '{uuid}' updated successfully",
        "project": project,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_project(client: CoolifyClient, uuid: str) -> str:
    """Delete a project."""
    result_data = await client.delete_project(uuid)
    result = {"success": True, "message": f"Project '{uuid}' deleted", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def list_environments(client: CoolifyClient, project_uuid: str) -> str:
    """List environments in a project."""
    envs = await client.list_environments(project_uuid)
    result = {"success": True, "count": len(envs), "environments": envs}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_environment(client: CoolifyClient, project_uuid: str, environment_name: str) -> str:
    """Get environment details."""
    env = await client.get_environment(project_uuid, environment_name)
    result = {"success": True, "environment": env}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_environment(
    client: CoolifyClient,
    project_uuid: str,
    name: str,
    description: str | None = None,
) -> str:
    """Create a new environment in a project."""
    data = {"name": name}
    if description is not None:
        data["description"] = description
    env = await client.create_environment(project_uuid, data)
    result = {
        "success": True,
        "message": f"Environment '{name}' created",
        "environment": env,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)
