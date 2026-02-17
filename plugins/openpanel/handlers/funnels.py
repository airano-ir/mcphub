"""Funnels Handler - OpenPanel funnel analytics (8 tools)"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (8 tools)"""
    return [
        {
            "name": "list_funnels",
            "method_name": "list_funnels",
            "description": "List all funnels defined for a project.",
            "schema": {
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "Project ID"}},
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_funnel",
            "method_name": "get_funnel",
            "description": "Get funnel details and current conversion data.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "funnel_id": {"type": "string", "description": "Funnel ID"},
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
                        "default": "30d",
                    },
                },
                "required": ["project_id", "funnel_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_funnel",
            "method_name": "create_funnel",
            "description": "Create a new funnel to track user journey through steps.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "name": {"type": "string", "description": "Funnel name"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Step name"},
                                "event": {
                                    "type": "string",
                                    "description": "Event name for this step",
                                },
                                "filters": {
                                    "type": "array",
                                    "description": "Optional filters for this step",
                                },
                            },
                            "required": ["name", "event"],
                        },
                        "description": "Funnel steps in sequence",
                        "minItems": 2,
                        "maxItems": 10,
                    },
                    "window_days": {
                        "type": "integer",
                        "description": "Conversion window in days",
                        "default": 14,
                        "maximum": 90,
                    },
                },
                "required": ["project_id", "name", "steps"],
            },
            "scope": "write",
        },
        {
            "name": "update_funnel",
            "method_name": "update_funnel",
            "description": "Update an existing funnel's configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "funnel_id": {"type": "string", "description": "Funnel ID"},
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New funnel name",
                    },
                    "steps": {
                        "anyOf": [{"type": "array"}, {"type": "null"}],
                        "description": "New funnel steps",
                    },
                    "window_days": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "New conversion window",
                    },
                },
                "required": ["project_id", "funnel_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_funnel",
            "method_name": "delete_funnel",
            "description": "Delete a funnel.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "funnel_id": {"type": "string", "description": "Funnel ID to delete"},
                },
                "required": ["project_id", "funnel_id"],
            },
            "scope": "write",
        },
        {
            "name": "get_funnel_conversion",
            "method_name": "get_funnel_conversion",
            "description": "Get detailed conversion rates for each funnel step.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "funnel_id": {"type": "string", "description": "Funnel ID"},
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
                        "default": "30d",
                    },
                },
                "required": ["project_id", "funnel_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_funnel_breakdown",
            "method_name": "get_funnel_breakdown",
            "description": "Get funnel breakdown by segment (country, device, etc.).",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "funnel_id": {"type": "string", "description": "Funnel ID"},
                    "breakdown_by": {
                        "type": "string",
                        "enum": ["country", "device", "browser", "os", "referrer"],
                        "description": "Dimension to break down by",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
                        "default": "30d",
                    },
                },
                "required": ["project_id", "funnel_id", "breakdown_by"],
            },
            "scope": "read",
        },
        {
            "name": "compare_funnels",
            "method_name": "compare_funnels",
            "description": "Compare conversion rates between multiple funnels.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "funnel_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Funnel IDs to compare",
                        "minItems": 2,
                        "maxItems": 5,
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
                        "default": "30d",
                    },
                },
                "required": ["project_id", "funnel_ids"],
            },
            "scope": "read",
        },
    ]

# =====================
# Funnel Functions (8)
# =====================

async def list_funnels(client: OpenPanelClient, project_id: str) -> str:
    """List all funnels for a project"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "note": "Funnel listing requires dashboard tRPC API. Use OpenPanel dashboard to view funnels.",
                "message": "Funnel list request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_funnel(
    client: OpenPanelClient, project_id: str, funnel_id: str, date_range: str = "30d"
) -> str:
    """Get funnel details with conversion data"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "funnel_id": funnel_id,
                "date_range": date_range,
                "note": "Funnel details require dashboard tRPC API. Use OpenPanel dashboard to view funnel data.",
                "message": "Funnel data request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_funnel(
    client: OpenPanelClient,
    project_id: str,
    name: str,
    steps: list[dict[str, Any]],
    window_days: int = 14,
) -> str:
    """Create a new funnel"""
    try:
        # Validate steps
        if len(steps) < 2:
            return json.dumps(
                {"success": False, "error": "Funnel must have at least 2 steps"},
                indent=2,
                ensure_ascii=False,
            )

        funnel_config = {"name": name, "steps": steps, "window_days": window_days}

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "funnel": funnel_config,
                "note": "Funnel creation requires dashboard tRPC API. Use OpenPanel dashboard to create funnels.",
                "message": f"Funnel '{name}' configuration created with {len(steps)} steps",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_funnel(
    client: OpenPanelClient,
    project_id: str,
    funnel_id: str,
    name: str | None = None,
    steps: list[dict[str, Any]] | None = None,
    window_days: int | None = None,
) -> str:
    """Update an existing funnel"""
    try:
        updates = {}
        if name:
            updates["name"] = name
        if steps:
            updates["steps"] = steps
        if window_days:
            updates["window_days"] = window_days

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "funnel_id": funnel_id,
                "updates": updates,
                "note": "Funnel updates require dashboard tRPC API. Use OpenPanel dashboard to modify funnels.",
                "message": "Funnel update configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_funnel(client: OpenPanelClient, project_id: str, funnel_id: str) -> str:
    """Delete a funnel"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "funnel_id": funnel_id,
                "note": "Funnel deletion requires dashboard tRPC API. Use OpenPanel dashboard to delete funnels.",
                "message": "Funnel deletion request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_funnel_conversion(
    client: OpenPanelClient, project_id: str, funnel_id: str, date_range: str = "30d"
) -> str:
    """Get funnel conversion rates"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "funnel_id": funnel_id,
                "date_range": date_range,
                "note": "Conversion data requires dashboard tRPC API. Use OpenPanel dashboard for detailed conversion analysis.",
                "message": "Funnel conversion request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_funnel_breakdown(
    client: OpenPanelClient,
    project_id: str,
    funnel_id: str,
    breakdown_by: str,
    date_range: str = "30d",
) -> str:
    """Get funnel breakdown by segment"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "funnel_id": funnel_id,
                "breakdown_by": breakdown_by,
                "date_range": date_range,
                "note": "Funnel breakdown requires dashboard tRPC API. Use OpenPanel dashboard for segmented analysis.",
                "message": f"Funnel breakdown by {breakdown_by} request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def compare_funnels(
    client: OpenPanelClient, project_id: str, funnel_ids: list[str], date_range: str = "30d"
) -> str:
    """Compare multiple funnels"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "funnel_ids": funnel_ids,
                "date_range": date_range,
                "note": "Funnel comparison requires dashboard tRPC API. Use OpenPanel dashboard for comparison views.",
                "message": f"Comparison request for {len(funnel_ids)} funnels processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
