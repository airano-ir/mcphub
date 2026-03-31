"""Reports Handler - OpenPanel analytics reports (2 tools).

Uses Insights API for overview stats and live visitors.
"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient
from plugins.openpanel.handlers.utils import get_project_id as _get_project_id


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (2 tools)."""
    return [
        {
            "name": "get_overview_report",
            "method_name": "get_overview_report",
            "description": "Get overview statistics including visitors, page views, sessions, bounce rate, and duration via Insights API.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range (today, 7d, 30d, 6m, 12m, etc.)",
                        "default": "30d",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_realtime_stats",
            "method_name": "get_realtime_stats",
            "description": "Get real-time active visitor count via Insights live API.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    }
                },
                "required": [],
            },
            "scope": "read",
        },
    ]


# =====================
# Report Functions (2)
# =====================


async def get_overview_report(
    client: OpenPanelClient, project_id: str | None = None, date_range: str = "30d"
) -> str:
    """Get overview statistics via Insights metrics API."""
    try:
        pid = _get_project_id(client, project_id)
        result = await client.get_overview_stats(project_id=pid, date_range=date_range)
        return json.dumps(
            {"success": True, "project_id": pid, "date_range": date_range, "stats": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_realtime_stats(client: OpenPanelClient, project_id: str | None = None) -> str:
    """Get real-time active visitor count via Insights live API."""
    try:
        pid = _get_project_id(client, project_id)
        result = await client.get_live_visitors(project_id=pid)
        return json.dumps(
            {"success": True, "project_id": pid, "realtime": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
