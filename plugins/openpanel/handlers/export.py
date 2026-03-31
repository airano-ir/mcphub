"""Export Handler - OpenPanel data export and analytics operations (10 tools).

Uses REST APIs:
- Export API (GET /export/events, /export/charts) for raw data export
- Insights API (GET /insights/:projectId/*) for analytics queries

Note: project_id is optional if configured in environment variables.
When not provided, the default project_id from OPENPANEL_SITE1_PROJECT_ID is used.

Requires 'read' or 'root' mode client for Export API.
"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient
from plugins.openpanel.handlers.utils import get_project_id as _get_project_id


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (10 tools)."""
    return [
        {
            "name": "export_events",
            "method_name": "export_events",
            "description": "Export raw event data with filters and pagination. Returns individual event records. Requires 'read' or 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID to export from (optional if configured in env)",
                    },
                    "event": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                            {"type": "null"},
                        ],
                        "description": "Event name(s) to filter (single or array)",
                    },
                    "profile_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter by user/profile ID",
                    },
                    "start": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Start date (YYYY-MM-DD)",
                    },
                    "end": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "End date (YYYY-MM-DD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Events per page",
                        "default": 50,
                        "maximum": 1000,
                    },
                    "page": {"type": "integer", "description": "Page number", "default": 1},
                    "includes": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "profile",
                                        "meta",
                                        "properties",
                                        "region",
                                        "device",
                                        "referrer",
                                        "revenue",
                                    ],
                                },
                            },
                            {"type": "null"},
                        ],
                        "description": "Additional data to include (profile, meta, properties, region, device, referrer, revenue)",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "export_events_csv",
            "method_name": "export_events_csv",
            "description": "Export events as CSV-formatted data for spreadsheet analysis. Requires 'read' or 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID to export from (optional if configured in env)",
                    },
                    "event": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Event name to filter",
                    },
                    "start": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Start date (YYYY-MM-DD)",
                    },
                    "end": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "End date (YYYY-MM-DD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum events to export",
                        "default": 1000,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "export_chart_data",
            "method_name": "export_chart_data",
            "description": "Export aggregated chart data with time series and breakdowns. Requires 'read' or 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Event name"},
                                "segment": {
                                    "type": "string",
                                    "enum": [
                                        "event",
                                        "user",
                                        "session",
                                        "user_average",
                                        "one_event_per_user",
                                        "property_sum",
                                        "property_average",
                                        "property_min",
                                        "property_max",
                                    ],
                                    "description": "Segmentation type",
                                },
                                "property": {
                                    "type": "string",
                                    "description": "Property for property-based segments",
                                },
                                "filters": {"type": "array", "description": "Event filters"},
                            },
                            "required": ["name"],
                        },
                        "description": "Events to include in chart",
                    },
                    "interval": {
                        "type": "string",
                        "enum": ["minute", "hour", "day", "week", "month"],
                        "description": "Time interval for aggregation",
                        "default": "day",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range (30min, today, 7d, 30d, 6m, 12m, etc.)",
                        "default": "30d",
                    },
                    "breakdowns": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "country",
                                        "region",
                                        "city",
                                        "device",
                                        "browser",
                                        "os",
                                        "referrer",
                                        "path",
                                    ],
                                },
                            },
                            {"type": "null"},
                        ],
                        "description": "Breakdown dimensions",
                    },
                    "previous": {
                        "type": "boolean",
                        "description": "Include previous period for comparison",
                        "default": False,
                    },
                },
                "required": ["events"],
            },
            "scope": "read",
        },
        {
            "name": "get_event_count",
            "method_name": "get_event_count",
            "description": "Get total event count with optional filters via Export API.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "event": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Event name to count (all events if not specified)",
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
            "name": "get_unique_users",
            "method_name": "get_unique_users",
            "description": "Get unique user/visitor count for a time period via Insights API.",
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
            "name": "get_page_views",
            "method_name": "get_page_views",
            "description": "Get page view statistics via Insights API.",
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
            "name": "get_top_pages",
            "method_name": "get_top_pages",
            "description": "Get top pages by view count via Insights API.",
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
                    "limit": {
                        "type": "integer",
                        "description": "Number of pages to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_top_referrers",
            "method_name": "get_top_referrers",
            "description": "Get top traffic sources/referrers via Insights API.",
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
                    "limit": {
                        "type": "integer",
                        "description": "Number of referrers to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_geo_data",
            "method_name": "get_geo_data",
            "description": "Get geographic distribution of visitors via Insights API.",
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
                    "breakdown": {
                        "type": "string",
                        "enum": ["country", "region", "city"],
                        "description": "Geographic breakdown level",
                        "default": "country",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of locations to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_device_data",
            "method_name": "get_device_data",
            "description": "Get device/browser/OS breakdown of visitors via Insights API.",
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
                    "breakdown": {
                        "type": "string",
                        "enum": ["device", "browser", "os"],
                        "description": "Device breakdown type",
                        "default": "device",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of items to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
    ]


# =====================
# Export Functions (10)
# =====================


async def export_events(
    client: OpenPanelClient,
    project_id: str | None = None,
    event: str | list[str] | None = None,
    profile_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
    page: int = 1,
    includes: list[str] | None = None,
) -> str:
    """Export raw event data via GET /export/events."""
    try:
        pid = _get_project_id(client, project_id)
        result = await client.export_events(
            project_id=pid,
            event=event,
            profile_id=profile_id,
            start=start,
            end=end,
            page=page,
            limit=limit,
            includes=includes,
        )
        meta = result.get("meta", {}) if isinstance(result, dict) else {}
        data = result.get("data", []) if isinstance(result, dict) else []
        return json.dumps(
            {
                "success": True,
                "project_id": pid,
                "count": len(data),
                "total": meta.get("totalCount", len(data)),
                "page": meta.get("current", page),
                "pages": meta.get("pages", 1),
                "data": data,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def export_events_csv(
    client: OpenPanelClient,
    project_id: str | None = None,
    event: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 1000,
) -> str:
    """Export events as CSV-formatted data."""
    try:
        pid = _get_project_id(client, project_id)
        result = await client.export_events(
            project_id=pid, event=event, start=start, end=end, limit=limit
        )
        events = result.get("data", []) if isinstance(result, dict) else []
        if not events:
            return json.dumps(
                {
                    "success": True,
                    "project_id": pid,
                    "count": 0,
                    "csv": "",
                    "message": "No events found",
                },
                indent=2,
                ensure_ascii=False,
            )
        headers = ["timestamp", "name", "profile_id"]
        csv_lines = [",".join(headers)]
        for ev in events:
            row = [
                str(ev.get("createdAt", ev.get("timestamp", ""))),
                str(ev.get("name", "")),
                str(ev.get("profileId", "")),
            ]
            csv_lines.append(",".join(row))
        return json.dumps(
            {
                "success": True,
                "project_id": pid,
                "count": len(events),
                "format": "csv",
                "csv": "\n".join(csv_lines),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def export_chart_data(
    client: OpenPanelClient,
    events: list[dict[str, Any]],
    project_id: str | None = None,
    interval: str = "day",
    date_range: str = "30d",
    breakdowns: list[str] | None = None,
    previous: bool = False,
) -> str:
    """Export aggregated chart data via GET /export/charts."""
    try:
        pid = _get_project_id(client, project_id)
        bd = [{"name": b} for b in breakdowns] if breakdowns else None
        result = await client.export_charts(
            project_id=pid,
            events=events,
            interval=interval,
            date_range=date_range,
            breakdowns=bd,
            previous=previous,
        )
        return json.dumps(
            {
                "success": True,
                "project_id": pid,
                "events": [e.get("name") for e in events],
                "interval": interval,
                "date_range": date_range,
                "breakdowns": breakdowns,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_event_count(
    client: OpenPanelClient,
    project_id: str | None = None,
    event: str | None = None,
    date_range: str = "30d",
) -> str:
    """Get total event count via Export charts API."""
    try:
        pid = _get_project_id(client, project_id)
        events_config = [{"name": event if event else "*", "segment": "event"}]
        result = await client.export_charts(
            project_id=pid,
            events=events_config,
            interval="day",
            date_range=date_range,
        )
        # Extract total from chart response
        total = 0
        if isinstance(result, dict):
            series = result.get("series", [])
            if series:
                for s in series:
                    for point in s.get("data", []):
                        total += point.get("count", 0)
            # Alternative: check metrics
            metrics = result.get("metrics", {})
            if metrics.get("current", {}).get("value"):
                total = metrics["current"]["value"]
        return json.dumps(
            {
                "success": True,
                "project_id": pid,
                "event": event or "all events",
                "date_range": date_range,
                "total_count": total,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_unique_users(
    client: OpenPanelClient, project_id: str | None = None, date_range: str = "30d"
) -> str:
    """Get unique user count via Insights metrics API."""
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


async def get_page_views(
    client: OpenPanelClient,
    project_id: str | None = None,
    date_range: str = "30d",
) -> str:
    """Get page view statistics via Insights metrics API."""
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


async def get_top_pages(
    client: OpenPanelClient, project_id: str | None = None, date_range: str = "30d", limit: int = 10
) -> str:
    """Get top pages via Insights pages API."""
    try:
        pid = _get_project_id(client, project_id)
        result = await client.get_top_pages(project_id=pid, date_range=date_range, limit=limit)
        return json.dumps(
            {"success": True, "project_id": pid, "date_range": date_range, "data": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_top_referrers(
    client: OpenPanelClient, project_id: str | None = None, date_range: str = "30d", limit: int = 10
) -> str:
    """Get top traffic sources via Insights breakdown API."""
    try:
        pid = _get_project_id(client, project_id)
        result = await client.get_top_sources(project_id=pid, date_range=date_range, limit=limit)
        return json.dumps(
            {"success": True, "project_id": pid, "date_range": date_range, "data": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_geo_data(
    client: OpenPanelClient,
    project_id: str | None = None,
    date_range: str = "30d",
    breakdown: str = "country",
    limit: int = 10,
) -> str:
    """Get geographic distribution via Insights breakdown API."""
    try:
        pid = _get_project_id(client, project_id)
        result = await client.get_top_locations(
            project_id=pid, date_range=date_range, breakdown=breakdown, limit=limit
        )
        return json.dumps(
            {
                "success": True,
                "project_id": pid,
                "date_range": date_range,
                "breakdown": breakdown,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_device_data(
    client: OpenPanelClient,
    project_id: str | None = None,
    date_range: str = "30d",
    breakdown: str = "device",
    limit: int = 10,
) -> str:
    """Get device/browser/OS breakdown via Insights breakdown API."""
    try:
        pid = _get_project_id(client, project_id)
        if breakdown == "browser":
            result = await client.get_top_browsers(
                project_id=pid, date_range=date_range, limit=limit
            )
        elif breakdown == "os":
            result = await client.get_top_os(project_id=pid, date_range=date_range, limit=limit)
        else:
            result = await client.get_top_devices(
                project_id=pid, date_range=date_range, limit=limit
            )
        return json.dumps(
            {
                "success": True,
                "project_id": pid,
                "date_range": date_range,
                "breakdown": breakdown,
                "data": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
