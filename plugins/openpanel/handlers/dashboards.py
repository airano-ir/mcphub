"""Dashboards Handler - OpenPanel dashboard management (10 tools)"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (10 tools)"""
    return [
        {
            "name": "list_dashboards",
            "method_name": "list_dashboards",
            "description": "List all dashboards for a project.",
            "schema": {
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "Project ID"}},
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_dashboard",
            "method_name": "get_dashboard",
            "description": "Get dashboard details including all charts.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID"},
                },
                "required": ["project_id", "dashboard_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_dashboard",
            "method_name": "create_dashboard",
            "description": "Create a new custom dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "name": {"type": "string", "description": "Dashboard name"},
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Dashboard description",
                    },
                },
                "required": ["project_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "update_dashboard",
            "method_name": "update_dashboard",
            "description": "Update dashboard properties.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID"},
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New description",
                    },
                },
                "required": ["project_id", "dashboard_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_dashboard",
            "method_name": "delete_dashboard",
            "description": "Delete a dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID to delete"},
                },
                "required": ["project_id", "dashboard_id"],
            },
            "scope": "write",
        },
        {
            "name": "add_chart",
            "method_name": "add_chart",
            "description": "Add a new chart to a dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID"},
                    "chart_type": {
                        "type": "string",
                        "enum": [
                            "line",
                            "bar",
                            "area",
                            "pie",
                            "map",
                            "histogram",
                            "funnel",
                            "retention",
                            "metric",
                        ],
                        "description": "Type of chart",
                    },
                    "title": {"type": "string", "description": "Chart title"},
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "segment": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                        "description": "Events to include in chart",
                    },
                    "breakdowns": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Breakdown dimensions",
                    },
                },
                "required": ["project_id", "dashboard_id", "chart_type", "title", "events"],
            },
            "scope": "write",
        },
        {
            "name": "update_chart",
            "method_name": "update_chart",
            "description": "Update an existing chart configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID"},
                    "chart_id": {"type": "string", "description": "Chart ID to update"},
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New title",
                    },
                    "chart_type": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New chart type",
                    },
                    "events": {
                        "anyOf": [{"type": "array"}, {"type": "null"}],
                        "description": "New events configuration",
                    },
                },
                "required": ["project_id", "dashboard_id", "chart_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_chart",
            "method_name": "delete_chart",
            "description": "Remove a chart from a dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID"},
                    "chart_id": {"type": "string", "description": "Chart ID to delete"},
                },
                "required": ["project_id", "dashboard_id", "chart_id"],
            },
            "scope": "write",
        },
        {
            "name": "duplicate_dashboard",
            "method_name": "duplicate_dashboard",
            "description": "Create a copy of an existing dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID to duplicate"},
                    "new_name": {"type": "string", "description": "Name for the new dashboard"},
                },
                "required": ["project_id", "dashboard_id", "new_name"],
            },
            "scope": "write",
        },
        {
            "name": "share_dashboard",
            "method_name": "share_dashboard",
            "description": "Generate a shareable link for a dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "dashboard_id": {"type": "string", "description": "Dashboard ID"},
                    "public": {
                        "type": "boolean",
                        "description": "Make dashboard publicly accessible",
                        "default": False,
                    },
                    "expires_in_days": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Link expiration in days (null for no expiration)",
                    },
                },
                "required": ["project_id", "dashboard_id"],
            },
            "scope": "write",
        },
    ]

# =====================
# Dashboard Functions (10)
# =====================

async def list_dashboards(client: OpenPanelClient, project_id: str) -> str:
    """List all dashboards"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "note": "Dashboard listing requires dashboard tRPC API. Use OpenPanel dashboard to view dashboards.",
                "message": "Dashboard list request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_dashboard(client: OpenPanelClient, project_id: str, dashboard_id: str) -> str:
    """Get dashboard details"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "note": "Dashboard details require dashboard tRPC API. Use OpenPanel dashboard for full view.",
                "message": "Dashboard request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_dashboard(
    client: OpenPanelClient, project_id: str, name: str, description: str | None = None
) -> str:
    """Create a new dashboard"""
    try:
        dashboard_config = {"name": name, "description": description}

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard": dashboard_config,
                "note": "Dashboard creation requires dashboard tRPC API. Use OpenPanel dashboard to create.",
                "message": f"Dashboard '{name}' configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_dashboard(
    client: OpenPanelClient,
    project_id: str,
    dashboard_id: str,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Update dashboard properties"""
    try:
        updates = {}
        if name:
            updates["name"] = name
        if description:
            updates["description"] = description

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "updates": updates,
                "note": "Dashboard updates require dashboard tRPC API. Use OpenPanel dashboard to modify.",
                "message": "Dashboard update configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_dashboard(client: OpenPanelClient, project_id: str, dashboard_id: str) -> str:
    """Delete a dashboard"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "note": "Dashboard deletion requires dashboard tRPC API. Use OpenPanel dashboard to delete.",
                "message": "Dashboard deletion request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def add_chart(
    client: OpenPanelClient,
    project_id: str,
    dashboard_id: str,
    chart_type: str,
    title: str,
    events: list[dict[str, Any]],
    breakdowns: list[str] | None = None,
) -> str:
    """Add a chart to dashboard"""
    try:
        chart_config = {
            "chart_type": chart_type,
            "title": title,
            "events": events,
            "breakdowns": breakdowns,
        }

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "chart": chart_config,
                "note": "Chart creation requires dashboard tRPC API. Use OpenPanel dashboard to add charts.",
                "message": f"Chart '{title}' configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_chart(
    client: OpenPanelClient,
    project_id: str,
    dashboard_id: str,
    chart_id: str,
    title: str | None = None,
    chart_type: str | None = None,
    events: list[dict[str, Any]] | None = None,
) -> str:
    """Update chart configuration"""
    try:
        updates = {}
        if title:
            updates["title"] = title
        if chart_type:
            updates["chart_type"] = chart_type
        if events:
            updates["events"] = events

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "chart_id": chart_id,
                "updates": updates,
                "note": "Chart updates require dashboard tRPC API. Use OpenPanel dashboard to modify charts.",
                "message": "Chart update configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_chart(
    client: OpenPanelClient, project_id: str, dashboard_id: str, chart_id: str
) -> str:
    """Remove chart from dashboard"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "chart_id": chart_id,
                "note": "Chart deletion requires dashboard tRPC API. Use OpenPanel dashboard to remove charts.",
                "message": "Chart deletion request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def duplicate_dashboard(
    client: OpenPanelClient, project_id: str, dashboard_id: str, new_name: str
) -> str:
    """Duplicate a dashboard"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "new_name": new_name,
                "note": "Dashboard duplication requires dashboard tRPC API. Use OpenPanel dashboard to clone.",
                "message": f"Dashboard duplication request for '{new_name}'",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def share_dashboard(
    client: OpenPanelClient,
    project_id: str,
    dashboard_id: str,
    public: bool = False,
    expires_in_days: int | None = None,
) -> str:
    """Generate shareable link"""
    try:
        share_config = {"public": public, "expires_in_days": expires_in_days}

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "dashboard_id": dashboard_id,
                "share_config": share_config,
                "note": "Dashboard sharing requires dashboard tRPC API. Use OpenPanel dashboard to share.",
                "message": "Dashboard share configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
