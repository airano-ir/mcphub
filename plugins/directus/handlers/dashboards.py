"""
Dashboards Handler - Dashboards & Panels

Phase J.4: 8 tools
- Dashboards: list, get, create, update, delete (5)
- Panels: list, create, delete (3)
"""

import json
from typing import Any

from plugins.directus.client import DirectusClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (8 tools)"""
    return [
        # =====================
        # DASHBOARDS (5)
        # =====================
        {
            "name": "list_dashboards",
            "method_name": "list_dashboards",
            "description": "List all insights dashboards.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Filter object",
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum dashboards to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_dashboard",
            "method_name": "get_dashboard",
            "description": "Get dashboard details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Dashboard UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "create_dashboard",
            "method_name": "create_dashboard",
            "description": "Create a new insights dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Dashboard name"},
                    "icon": {
                        "type": "string",
                        "description": "Material icon",
                        "default": "dashboard",
                    },
                    "note": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Dashboard description",
                    },
                    "color": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Accent color",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_dashboard",
            "method_name": "update_dashboard",
            "description": "Update dashboard settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Dashboard UUID"},
                    "data": {
                        "type": "object",
                        "description": "Fields to update (name, icon, note, color)",
                    },
                },
                "required": ["id", "data"],
            },
            "scope": "write",
        },
        {
            "name": "delete_dashboard",
            "method_name": "delete_dashboard",
            "description": "Delete a dashboard and its panels.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Dashboard UUID to delete"}},
                "required": ["id"],
            },
            "scope": "write",
        },
        # =====================
        # PANELS (3)
        # =====================
        {
            "name": "list_panels",
            "method_name": "list_panels",
            "description": "List all panels, optionally filtered by dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"dashboard": {"_eq": "dashboard-uuid"}})',
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum panels to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "create_panel",
            "method_name": "create_panel",
            "description": "Create a new panel in a dashboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "dashboard": {"type": "string", "description": "Dashboard UUID"},
                    "type": {
                        "type": "string",
                        "description": "Panel type (label, list, metric, time-series, etc.)",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Panel name",
                    },
                    "icon": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Material icon",
                    },
                    "color": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Accent color",
                    },
                    "note": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Panel description",
                    },
                    "width": {
                        "type": "integer",
                        "description": "Panel width (1-12 grid units)",
                        "default": 12,
                    },
                    "height": {
                        "type": "integer",
                        "description": "Panel height (grid units)",
                        "default": 6,
                    },
                    "position_x": {
                        "type": "integer",
                        "description": "X position in dashboard",
                        "default": 0,
                    },
                    "position_y": {
                        "type": "integer",
                        "description": "Y position in dashboard",
                        "default": 0,
                    },
                    "options": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Panel-specific options",
                    },
                },
                "required": ["dashboard", "type"],
            },
            "scope": "write",
        },
        {
            "name": "delete_panel",
            "method_name": "delete_panel",
            "description": "Delete a panel from a dashboard.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Panel UUID to delete"}},
                "required": ["id"],
            },
            "scope": "write",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def list_dashboards(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
) -> str:
    """List dashboards."""
    try:
        result = await client.list_dashboards(filter=filter, sort=sort, limit=limit)
        dashboards = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(dashboards), "dashboards": dashboards},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_dashboard(client: DirectusClient, id: str) -> str:
    """Get dashboard by ID."""
    try:
        result = await client.get_dashboard(id)
        return json.dumps(
            {"success": True, "dashboard": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_dashboard(
    client: DirectusClient,
    name: str,
    icon: str = "dashboard",
    note: str | None = None,
    color: str | None = None,
) -> str:
    """Create a new dashboard."""
    try:
        result = await client.create_dashboard(name=name, icon=icon, note=note, color=color)
        return json.dumps(
            {
                "success": True,
                "message": f"Dashboard '{name}' created",
                "dashboard": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_dashboard(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update dashboard."""
    try:
        result = await client.update_dashboard(id, data)
        return json.dumps(
            {"success": True, "message": "Dashboard updated", "dashboard": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_dashboard(client: DirectusClient, id: str) -> str:
    """Delete a dashboard."""
    try:
        await client.delete_dashboard(id)
        return json.dumps({"success": True, "message": f"Dashboard {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_panels(client: DirectusClient, filter: dict | None = None, limit: int = 100) -> str:
    """List panels."""
    try:
        result = await client.list_panels(filter=filter, limit=limit)
        panels = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(panels), "panels": panels}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_panel(
    client: DirectusClient,
    dashboard: str,
    type: str,
    name: str | None = None,
    icon: str | None = None,
    color: str | None = None,
    note: str | None = None,
    width: int = 12,
    height: int = 6,
    position_x: int = 0,
    position_y: int = 0,
    options: dict | None = None,
) -> str:
    """Create a new panel."""
    try:
        result = await client.create_panel(
            dashboard=dashboard,
            type=type,
            name=name,
            icon=icon,
            color=color,
            note=note,
            width=width,
            height=height,
            position_x=position_x,
            position_y=position_y,
            options=options,
        )
        return json.dumps(
            {"success": True, "message": f"Panel '{type}' created", "panel": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_panel(client: DirectusClient, id: str) -> str:
    """Delete a panel."""
    try:
        await client.delete_panel(id)
        return json.dumps({"success": True, "message": f"Panel {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
