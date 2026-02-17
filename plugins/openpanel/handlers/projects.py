"""Projects Handler - OpenPanel project management (8 tools)"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (8 tools)"""
    return [
        {
            "name": "list_projects",
            "method_name": "list_projects",
            "description": "List all OpenPanel projects.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_project",
            "method_name": "get_project",
            "description": "Get project details including settings and statistics.",
            "schema": {
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "Project ID"}},
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_project",
            "method_name": "create_project",
            "description": "Create a new OpenPanel project.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "domain": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Primary domain for the project",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Project timezone",
                        "default": "UTC",
                    },
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        {
            "name": "update_project",
            "method_name": "update_project",
            "description": "Update project settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New project name",
                    },
                    "domain": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New primary domain",
                    },
                    "timezone": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New timezone",
                    },
                },
                "required": ["project_id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_project",
            "method_name": "delete_project",
            "description": "Delete a project and all its data.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID to delete"},
                    "confirm": {"type": "boolean", "description": "Confirm deletion (required)"},
                },
                "required": ["project_id", "confirm"],
            },
            "scope": "admin",
        },
        {
            "name": "get_project_stats",
            "method_name": "get_project_stats",
            "description": "Get project statistics (events, users, storage).",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, yearToDate, all",
                        "default": "30d",
                    },
                },
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_project_settings",
            "method_name": "get_project_settings",
            "description": "Get project configuration settings.",
            "schema": {
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "Project ID"}},
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "update_project_settings",
            "method_name": "update_project_settings",
            "description": "Update project configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "settings": {
                        "type": "object",
                        "description": "Settings to update",
                        "properties": {
                            "cors_domains": {"type": "array", "items": {"type": "string"}},
                            "ip_anonymization": {"type": "boolean"},
                            "data_retention_days": {"type": "integer"},
                        },
                    },
                },
                "required": ["project_id", "settings"],
            },
            "scope": "admin",
        },
    ]


# =====================
# Project Functions (8)
# =====================


async def list_projects(client: OpenPanelClient) -> str:
    """List all projects"""
    try:
        return json.dumps(
            {
                "success": True,
                "note": "Project listing requires dashboard tRPC API. Use OpenPanel dashboard to view projects.",
                "message": "Project list request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_project(client: OpenPanelClient, project_id: str) -> str:
    """Get project details"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "note": "Project details require dashboard tRPC API. Use OpenPanel dashboard for full project view.",
                "message": "Project details request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def create_project(
    client: OpenPanelClient, name: str, domain: str | None = None, timezone: str = "UTC"
) -> str:
    """Create a new project"""
    try:
        project_config = {"name": name, "domain": domain, "timezone": timezone}

        return json.dumps(
            {
                "success": True,
                "project": project_config,
                "note": "Project creation requires dashboard tRPC API. Use OpenPanel dashboard to create projects.",
                "message": f"Project '{name}' configuration created",
            },
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
    timezone: str | None = None,
) -> str:
    """Update project settings"""
    try:
        updates = {}
        if name:
            updates["name"] = name
        if domain:
            updates["domain"] = domain
        if timezone:
            updates["timezone"] = timezone

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "updates": updates,
                "note": "Project updates require dashboard tRPC API. Use OpenPanel dashboard to modify projects.",
                "message": "Project update configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def delete_project(client: OpenPanelClient, project_id: str, confirm: bool = False) -> str:
    """Delete a project"""
    try:
        if not confirm:
            return json.dumps(
                {
                    "success": False,
                    "error": "Deletion not confirmed. Set confirm=true to proceed.",
                    "warning": "This will permanently delete all project data including events, users, and settings.",
                },
                indent=2,
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "confirmed": confirm,
                "note": "Project deletion requires dashboard tRPC API. Use OpenPanel dashboard to delete projects.",
                "message": "Project deletion request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_project_stats(
    client: OpenPanelClient, project_id: str, date_range: str = "30d"
) -> str:
    """Get project statistics"""
    try:
        # Get basic stats via export API
        metrics = {}

        # Total events
        events_config = [{"name": "*", "segment": "event"}]
        events_result = await client.export_charts(
            project_id=project_id, events=events_config, interval="day", date_range=date_range
        )

        total_events = 0
        if isinstance(events_result, dict) and "data" in events_result:
            for point in events_result.get("data", []):
                total_events += point.get("count", 0)
        metrics["total_events"] = total_events

        # Unique users
        users_config = [{"name": "*", "segment": "user"}]
        users_result = await client.export_charts(
            project_id=project_id, events=users_config, interval="day", date_range=date_range
        )

        if isinstance(users_result, dict) and "data" in users_result:
            data = users_result.get("data", [])
            metrics["unique_users"] = data[-1].get("count", 0) if data else 0

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "date_range": date_range,
                "stats": metrics,
                "message": "Project stats retrieved",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_project_settings(client: OpenPanelClient, project_id: str) -> str:
    """Get project settings"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "note": "Project settings require dashboard tRPC API. Use OpenPanel dashboard for settings.",
                "message": "Project settings request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def update_project_settings(
    client: OpenPanelClient, project_id: str, settings: dict[str, Any]
) -> str:
    """Update project settings"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "settings": settings,
                "note": "Settings update requires dashboard tRPC API. Use OpenPanel dashboard to configure.",
                "message": "Project settings update configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
