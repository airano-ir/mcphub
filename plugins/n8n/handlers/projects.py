"""Projects Handler - manages n8n projects (Enterprise/Pro)"""

import json
from typing import Any

from plugins.n8n.client import N8nClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_projects",
            "method_name": "list_projects",
            "description": "[Enterprise] List all projects. Requires n8n Enterprise/Pro license. All parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 250},
                    "cursor": {"type": "string", "description": "OPTIONAL: Pagination cursor."},
                },
            },
            "scope": "read",
        },
        {
            "name": "get_project",
            "method_name": "get_project",
            "description": "[Enterprise] Get project details by ID. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {"project_id": {"type": "string", "minLength": 1}},
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_project",
            "method_name": "create_project",
            "description": "[Enterprise] Create a new project. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "description": "Project name"}
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        {
            "name": "update_project",
            "method_name": "update_project",
            "description": "[Enterprise] Update project metadata. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1, "description": "New project name"},
                },
                "required": ["project_id", "name"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_project",
            "method_name": "delete_project",
            "description": "[Enterprise] Delete a project. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {"project_id": {"type": "string", "minLength": 1}},
                "required": ["project_id"],
            },
            "scope": "admin",
        },
        {
            "name": "add_project_users",
            "method_name": "add_project_users",
            "description": "[Enterprise] Add users to a project with roles. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "minLength": 1},
                    "users": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "user_id": {"type": "string"},
                                "role": {
                                    "type": "string",
                                    "enum": ["project:admin", "project:editor", "project:viewer"],
                                },
                            },
                            "required": ["user_id", "role"],
                        },
                        "minItems": 1,
                    },
                },
                "required": ["project_id", "users"],
            },
            "scope": "admin",
        },
        {
            "name": "change_project_user_role",
            "method_name": "change_project_user_role",
            "description": "[Enterprise] Change a user's role in a project. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "minLength": 1},
                    "user_id": {"type": "string", "minLength": 1},
                    "role": {
                        "type": "string",
                        "enum": ["project:admin", "project:editor", "project:viewer"],
                    },
                },
                "required": ["project_id", "user_id", "role"],
            },
            "scope": "admin",
        },
        {
            "name": "remove_project_user",
            "method_name": "remove_project_user",
            "description": "[Enterprise] Remove a user from a project. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "minLength": 1},
                    "user_id": {"type": "string", "minLength": 1},
                },
                "required": ["project_id", "user_id"],
            },
            "scope": "admin",
        },
    ]


async def list_projects(client: N8nClient, limit: int = 100, cursor: str | None = None) -> str:
    try:
        response = await client.list_projects(limit=limit, cursor=cursor)
        projects = response.get("data", [])
        result = {
            "success": True,
            "count": len(projects),
            "projects": [{"id": p.get("id"), "name": p.get("name")} for p in projects],
            "next_cursor": response.get("nextCursor"),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_project(client: N8nClient, project_id: str) -> str:
    try:
        project = await client.get_project(project_id)
        return json.dumps(
            {"success": True, "project": {"id": project.get("id"), "name": project.get("name")}},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_project(client: N8nClient, name: str) -> str:
    try:
        project = await client.create_project(name)
        return json.dumps(
            {
                "success": True,
                "message": f"Project '{name}' created",
                "project": {"id": project.get("id"), "name": project.get("name")},
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_project(client: N8nClient, project_id: str, name: str) -> str:
    try:
        project = await client.update_project(project_id, name)
        return json.dumps(
            {
                "success": True,
                "message": f"Project updated to '{name}'",
                "project": {"id": project.get("id"), "name": project.get("name")},
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_project(client: N8nClient, project_id: str) -> str:
    try:
        await client.delete_project(project_id)
        return json.dumps({"success": True, "message": f"Project {project_id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def add_project_users(client: N8nClient, project_id: str, users: list[dict[str, str]]) -> str:
    try:
        relations = [{"userId": u["user_id"], "role": u["role"]} for u in users]
        await client.add_project_users(project_id, relations)
        return json.dumps(
            {"success": True, "message": f"Added {len(users)} user(s) to project {project_id}"},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def change_project_user_role(
    client: N8nClient, project_id: str, user_id: str, role: str
) -> str:
    try:
        await client.change_project_user_role(project_id, user_id, role)
        return json.dumps(
            {
                "success": True,
                "message": f"User {user_id} role changed to {role} in project {project_id}",
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def remove_project_user(client: N8nClient, project_id: str, user_id: str) -> str:
    try:
        await client.remove_project_user(project_id, user_id)
        return json.dumps(
            {"success": True, "message": f"User {user_id} removed from project {project_id}"},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
