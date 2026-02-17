"""
System Handler - Settings, Server, Schema, Activity, Presets, Notifications

Phase J.4: 10 tools
- Settings: get, update (2)
- Server: info, health, graphql_sdl, openapi_spec (4)
- Schema: snapshot, diff, apply (3)
- Activity: list (1)
"""

import json
from typing import Any

from plugins.directus.client import DirectusClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (10 tools)"""
    return [
        # =====================
        # SETTINGS (2)
        # =====================
        {
            "name": "get_settings",
            "method_name": "get_settings",
            "description": "Get system settings.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "update_settings",
            "method_name": "update_settings",
            "description": "Update system settings (project name, logo, colors, etc.).",
            "schema": {
                "type": "object",
                "properties": {"data": {"type": "object", "description": "Settings to update"}},
                "required": ["data"],
            },
            "scope": "admin",
        },
        # =====================
        # SERVER (4)
        # =====================
        {
            "name": "get_server_info",
            "method_name": "get_server_info",
            "description": "Get Directus server information (version, extensions, etc.).",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "health_check",
            "method_name": "health_check",
            "description": "Check Directus server health status.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "get_graphql_sdl",
            "method_name": "get_graphql_sdl",
            "description": "Get the GraphQL SDL schema.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "get_openapi_spec",
            "method_name": "get_openapi_spec",
            "description": "Get the OpenAPI specification.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        # =====================
        # SCHEMA (3)
        # =====================
        {
            "name": "get_schema_snapshot",
            "method_name": "get_schema_snapshot",
            "description": "Get complete schema snapshot for migration/backup.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "admin",
        },
        {
            "name": "schema_diff",
            "method_name": "schema_diff",
            "description": "Get diff between current schema and provided snapshot.",
            "schema": {
                "type": "object",
                "properties": {
                    "snapshot": {
                        "type": "object",
                        "description": "Schema snapshot to compare against",
                    }
                },
                "required": ["snapshot"],
            },
            "scope": "admin",
        },
        {
            "name": "schema_apply",
            "method_name": "schema_apply",
            "description": "Apply schema diff to database.",
            "schema": {
                "type": "object",
                "properties": {"diff": {"type": "object", "description": "Schema diff to apply"}},
                "required": ["diff"],
            },
            "scope": "admin",
        },
        # =====================
        # ACTIVITY (1)
        # =====================
        {
            "name": "list_activity",
            "method_name": "list_activity",
            "description": "List activity log (all actions performed in Directus).",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"action": {"_eq": "create"}})',
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields (default: ['-timestamp'])",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum activities to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def get_settings(client: DirectusClient) -> str:
    """Get system settings."""
    try:
        result = await client.get_settings()
        return json.dumps(
            {"success": True, "settings": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_settings(client: DirectusClient, data: dict[str, Any]) -> str:
    """Update system settings."""
    try:
        result = await client.update_settings(data)
        return json.dumps(
            {"success": True, "message": "Settings updated", "settings": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_server_info(client: DirectusClient) -> str:
    """Get server info."""
    try:
        result = await client.get_server_info()
        return json.dumps(
            {"success": True, "server": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def health_check(client: DirectusClient) -> str:
    """Check server health."""
    try:
        result = await client.health_check()
        return json.dumps(
            {"success": True, "status": result.get("status", "unknown"), "health": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_graphql_sdl(client: DirectusClient) -> str:
    """Get GraphQL SDL."""
    try:
        result = await client.get_graphql_sdl()
        # GraphQL SDL is usually returned as text
        if isinstance(result, dict):
            sdl = result.get("data", result)
        else:
            sdl = result
        return json.dumps({"success": True, "sdl": sdl}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_openapi_spec(client: DirectusClient) -> str:
    """Get OpenAPI specification."""
    try:
        result = await client.get_openapi_spec()
        return json.dumps({"success": True, "spec": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_schema_snapshot(client: DirectusClient) -> str:
    """Get schema snapshot."""
    try:
        result = await client.get_schema_snapshot()
        return json.dumps(
            {"success": True, "snapshot": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def schema_diff(client: DirectusClient, snapshot: dict[str, Any]) -> str:
    """Get schema diff."""
    try:
        result = await client.schema_diff(snapshot)
        return json.dumps(
            {"success": True, "diff": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def schema_apply(client: DirectusClient, diff: dict[str, Any]) -> str:
    """Apply schema diff."""
    try:
        result = await client.schema_apply(diff)
        return json.dumps(
            {
                "success": True,
                "message": "Schema applied",
                "result": result.get("data") if result else None,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_activity(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
) -> str:
    """List activity log."""
    try:
        result = await client.list_activity(filter=filter, sort=sort, limit=limit)
        activities = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(activities), "activities": activities},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
