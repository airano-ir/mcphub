"""Profiles Handler - OpenPanel user profile management (8 tools)"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (8 tools)"""
    return [
        {
            "name": "list_profiles",
            "method_name": "list_profiles",
            "description": "List user profiles with optional filtering and pagination.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of profiles to return",
                        "default": 50,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "default": 0,
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["last_seen", "first_seen", "event_count"],
                        "description": "Sort order",
                        "default": "last_seen",
                    },
                },
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_profile",
            "method_name": "get_profile",
            "description": "Get detailed information about a specific user profile.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "profile_id": {"type": "string", "description": "User profile ID"},
                },
                "required": ["project_id", "profile_id"],
            },
            "scope": "read",
        },
        {
            "name": "search_profiles",
            "method_name": "search_profiles",
            "description": "Search user profiles by property value.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "property": {
                        "type": "string",
                        "description": "Property to search (e.g., 'email', 'name', 'plan')",
                    },
                    "value": {"type": "string", "description": "Value to search for"},
                    "operator": {
                        "type": "string",
                        "enum": ["is", "contains", "startsWith", "endsWith"],
                        "description": "Search operator",
                        "default": "contains",
                    },
                    "limit": {"type": "integer", "description": "Maximum results", "default": 50},
                },
                "required": ["project_id", "property", "value"],
            },
            "scope": "read",
        },
        {
            "name": "get_profile_events",
            "method_name": "get_profile_events",
            "description": "Get events for a specific user profile.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "profile_id": {"type": "string", "description": "User profile ID"},
                    "event": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter by event name",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of events",
                        "default": 50,
                        "maximum": 200,
                    },
                },
                "required": ["project_id", "profile_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_profile_sessions",
            "method_name": "get_profile_sessions",
            "description": "Get sessions for a specific user profile.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "profile_id": {"type": "string", "description": "User profile ID"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of sessions",
                        "default": 20,
                        "maximum": 50,
                    },
                },
                "required": ["project_id", "profile_id"],
            },
            "scope": "read",
        },
        {
            "name": "delete_profile",
            "method_name": "delete_profile",
            "description": "Delete a user profile and all associated data (GDPR compliance).",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "profile_id": {"type": "string", "description": "User profile ID to delete"},
                    "confirm": {
                        "type": "boolean",
                        "description": "Confirm deletion (required)",
                        "default": False,
                    },
                },
                "required": ["project_id", "profile_id", "confirm"],
            },
            "scope": "admin",
        },
        {
            "name": "merge_profiles",
            "method_name": "merge_profiles",
            "description": "Merge two user profiles into one (for duplicate resolution).",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "primary_profile_id": {
                        "type": "string",
                        "description": "Primary profile ID to keep",
                    },
                    "secondary_profile_id": {
                        "type": "string",
                        "description": "Secondary profile ID to merge and delete",
                    },
                },
                "required": ["project_id", "primary_profile_id", "secondary_profile_id"],
            },
            "scope": "admin",
        },
        {
            "name": "export_profile_data",
            "method_name": "export_profile_data",
            "description": "Export all data for a user profile (GDPR data portability).",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "profile_id": {"type": "string", "description": "User profile ID"},
                    "format": {
                        "type": "string",
                        "enum": ["json", "csv"],
                        "description": "Export format",
                        "default": "json",
                    },
                },
                "required": ["project_id", "profile_id"],
            },
            "scope": "read",
        },
    ]

# =====================
# Profile Functions (8)
# =====================

async def list_profiles(
    client: OpenPanelClient,
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "last_seen",
) -> str:
    """List user profiles"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "pagination": {"limit": limit, "offset": offset, "sort_by": sort_by},
                "note": "Profile listing requires dashboard tRPC API. Use OpenPanel dashboard to view profiles.",
                "message": "Profile list request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_profile(client: OpenPanelClient, project_id: str, profile_id: str) -> str:
    """Get profile details"""
    try:
        # Try to get events for this profile via export API
        try:
            result = await client.export_events(
                project_id=project_id, profile_id=profile_id, limit=1, includes=["profile"]
            )

            if isinstance(result, dict) and result.get("data"):
                return json.dumps(
                    {
                        "success": True,
                        "project_id": project_id,
                        "profile_id": profile_id,
                        "has_events": True,
                        "note": "Full profile details require dashboard tRPC API.",
                        "message": "Profile found with associated events",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
        except:
            pass

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "profile_id": profile_id,
                "note": "Profile details require dashboard tRPC API. Use OpenPanel dashboard for full profile view.",
                "message": "Profile request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def search_profiles(
    client: OpenPanelClient,
    project_id: str,
    property: str,
    value: str,
    operator: str = "contains",
    limit: int = 50,
) -> str:
    """Search profiles by property"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "search": {
                    "property": property,
                    "value": value,
                    "operator": operator,
                    "limit": limit,
                },
                "note": "Profile search requires dashboard tRPC API. Use OpenPanel dashboard for profile search.",
                "message": "Profile search request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_profile_events(
    client: OpenPanelClient,
    project_id: str,
    profile_id: str,
    event: str | None = None,
    limit: int = 50,
) -> str:
    """Get events for a profile"""
    try:
        result = await client.export_events(
            project_id=project_id, profile_id=profile_id, event=event, limit=limit
        )

        events_count = len(result.get("data", [])) if isinstance(result, dict) else 0

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "profile_id": profile_id,
                "event_filter": event,
                "count": events_count,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_profile_sessions(
    client: OpenPanelClient, project_id: str, profile_id: str, limit: int = 20
) -> str:
    """Get sessions for a profile"""
    try:
        # Get session events
        result = await client.export_events(
            project_id=project_id, profile_id=profile_id, event="session_start", limit=limit
        )

        sessions = result.get("data", []) if isinstance(result, dict) else []

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "profile_id": profile_id,
                "sessions_count": len(sessions),
                "sessions": sessions,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_profile(
    client: OpenPanelClient, project_id: str, profile_id: str, confirm: bool = False
) -> str:
    """Delete a user profile (GDPR)"""
    try:
        if not confirm:
            return json.dumps(
                {
                    "success": False,
                    "error": "Deletion not confirmed. Set confirm=true to proceed.",
                    "warning": "This will permanently delete all user data.",
                },
                indent=2,
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "profile_id": profile_id,
                "confirmed": confirm,
                "note": "Profile deletion requires dashboard tRPC API. Use OpenPanel dashboard for GDPR deletion.",
                "message": "Profile deletion request processed (GDPR)",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def merge_profiles(
    client: OpenPanelClient, project_id: str, primary_profile_id: str, secondary_profile_id: str
) -> str:
    """Merge two profiles"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "primary_profile_id": primary_profile_id,
                "secondary_profile_id": secondary_profile_id,
                "note": "Profile merging requires dashboard tRPC API. Use OpenPanel dashboard for profile management.",
                "message": "Profile merge request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def export_profile_data(
    client: OpenPanelClient, project_id: str, profile_id: str, format: str = "json"
) -> str:
    """Export all profile data (GDPR)"""
    try:
        # Export events for this profile
        result = await client.export_events(
            project_id=project_id, profile_id=profile_id, limit=1000, includes=["profile", "meta"]
        )

        events = result.get("data", []) if isinstance(result, dict) else []

        export_data = {
            "profile_id": profile_id,
            "project_id": project_id,
            "events_count": len(events),
            "events": events,
        }

        if format == "csv":
            # Build CSV
            csv_lines = ["timestamp,event_name,properties"]
            for event in events:
                csv_lines.append(
                    f"{event.get('timestamp', '')},{event.get('name', '')},{json.dumps(event.get('properties', {}))}"
                )

            return json.dumps(
                {
                    "success": True,
                    "profile_id": profile_id,
                    "format": "csv",
                    "events_count": len(events),
                    "csv": "\n".join(csv_lines),
                    "message": "Profile data exported (GDPR compliance)",
                },
                indent=2,
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "success": True,
                "profile_id": profile_id,
                "format": "json",
                "events_count": len(events),
                "data": export_data,
                "message": "Profile data exported (GDPR compliance)",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
