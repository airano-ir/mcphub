"""Projects Handler - OpenPanel project management (5 tools).

Uses Manage API (GET/POST/PATCH/DELETE /manage/projects).
Requires 'root' mode client for write operations.
"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (5 tools)."""
    return [
        {
            "name": "list_projects",
            "method_name": "list_projects",
            "description": "List all projects via Manage API. Requires 'root' mode client.",
            "schema": {"type": "object", "properties": {}},
            "scope": "admin",
        },
        {
            "name": "get_project",
            "method_name": "get_project",
            "description": "Get project details via Manage API. Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                },
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_project",
            "method_name": "create_project",
            "description": "Create a new project via Manage API. Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "domain": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project domain (e.g., 'example.com')",
                    },
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        {
            "name": "update_project",
            "method_name": "update_project",
            "description": "Update a project via Manage API. Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID to update"},
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New project name",
                    },
                    "domain": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New domain",
                    },
                },
                "required": ["project_id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_project",
            "method_name": "delete_project",
            "description": "Delete a project via Manage API. WARNING: Permanently deletes all project data. Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID to delete"},
                },
                "required": ["project_id"],
            },
            "scope": "admin",
        },
    ]


# =====================
# Project Functions (5)
# =====================


async def list_projects(client: OpenPanelClient) -> str:
    """List all projects via GET /manage/projects."""
    try:
        result = await client.list_projects()
        projects = (
            result
            if isinstance(result, list)
            else result.get("data", []) if isinstance(result, dict) else []
        )
        return json.dumps(
            {"success": True, "count": len(projects), "projects": projects},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_project(client: OpenPanelClient, project_id: str) -> str:
    """Get project details via GET /manage/projects/:id."""
    try:
        result = await client.get_project(project_id)
        return json.dumps({"success": True, "project": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def create_project(client: OpenPanelClient, name: str, domain: str | None = None) -> str:
    """Create a new project via POST /manage/projects."""
    try:
        data: dict[str, Any] = {"name": name}
        if domain:
            data["domain"] = domain
        result = await client.create_project(data)
        return json.dumps(
            {"success": True, "message": f"Project '{name}' created", "project": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def update_project(
    client: OpenPanelClient,
    project_id: str,
    name: str | None = None,
    domain: str | None = None,
) -> str:
    """Update a project via PATCH /manage/projects/:id."""
    try:
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if domain:
            data["domain"] = domain
        if not data:
            return json.dumps(
                {"success": False, "error": "No fields to update. Provide name or domain."},
                indent=2,
                ensure_ascii=False,
            )
        result = await client.update_project(project_id, data)
        return json.dumps(
            {"success": True, "message": f"Project '{project_id}' updated", "project": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def delete_project(client: OpenPanelClient, project_id: str) -> str:
    """Delete a project via DELETE /manage/projects/:id."""
    try:
        result = await client.delete_project(project_id)
        return json.dumps(
            {"success": True, "message": f"Project '{project_id}' deleted", "result": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
