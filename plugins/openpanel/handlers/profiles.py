"""Profiles Handler - OpenPanel user profile operations (3 tools).

Uses Export API to retrieve profile events and data.
"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (3 tools)."""
    return [
        {
            "name": "get_profile_events",
            "method_name": "get_profile_events",
            "description": "Get events for a specific user profile via Export API. Requires 'read' or 'root' mode client.",
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
                        "maximum": 1000,
                    },
                },
                "required": ["project_id", "profile_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_profile_sessions",
            "method_name": "get_profile_sessions",
            "description": "Get sessions for a specific user profile via Export API. Requires 'read' or 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "profile_id": {"type": "string", "description": "User profile ID"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of sessions",
                        "default": 20,
                        "maximum": 100,
                    },
                },
                "required": ["project_id", "profile_id"],
            },
            "scope": "read",
        },
        {
            "name": "export_profile_data",
            "method_name": "export_profile_data",
            "description": "Export all data for a user profile (GDPR data portability). Returns events and profile data. Requires 'read' or 'root' mode client.",
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
# Profile Functions (3)
# =====================


async def get_profile_events(
    client: OpenPanelClient,
    project_id: str,
    profile_id: str,
    event: str | None = None,
    limit: int = 50,
) -> str:
    """Get events for a profile via Export API."""
    try:
        result = await client.export_events(
            project_id=project_id, profile_id=profile_id, event=event, limit=limit
        )
        data = result.get("data", []) if isinstance(result, dict) else []
        meta = result.get("meta", {}) if isinstance(result, dict) else {}
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "profile_id": profile_id,
                "event_filter": event,
                "count": len(data),
                "total": meta.get("totalCount", len(data)),
                "data": data,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_profile_sessions(
    client: OpenPanelClient, project_id: str, profile_id: str, limit: int = 20
) -> str:
    """Get sessions for a profile via Export API."""
    try:
        result = await client.export_events(
            project_id=project_id, profile_id=profile_id, event="session_start", limit=limit
        )
        data = result.get("data", []) if isinstance(result, dict) else []
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "profile_id": profile_id,
                "sessions_count": len(data),
                "sessions": data,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def export_profile_data(
    client: OpenPanelClient, project_id: str, profile_id: str, format: str = "json"
) -> str:
    """Export all profile data (GDPR compliance)."""
    try:
        result = await client.export_events(
            project_id=project_id,
            profile_id=profile_id,
            limit=1000,
            includes=["profile", "meta", "properties"],
        )
        events = result.get("data", []) if isinstance(result, dict) else []

        if format == "csv":
            csv_lines = ["timestamp,event_name,properties"]
            for ev in events:
                csv_lines.append(
                    f"{ev.get('createdAt', ev.get('timestamp', ''))},{ev.get('name', '')},"
                    f"{json.dumps(ev.get('properties', {}))}"
                )
            return json.dumps(
                {
                    "success": True,
                    "profile_id": profile_id,
                    "format": "csv",
                    "events_count": len(events),
                    "csv": "\n".join(csv_lines),
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
                "data": {"profile_id": profile_id, "project_id": project_id, "events": events},
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
