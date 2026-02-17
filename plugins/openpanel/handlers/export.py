"""Export Handler - OpenPanel data export operations (10 tools)

Note: project_id is optional if configured in environment variables.
When not provided, the default project_id from OPENPANEL_SITE1_PROJECT_ID is used.
"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient
from plugins.openpanel.handlers.utils import get_project_id as _get_project_id

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (10 tools)"""
    return [
        {
            "name": "export_events",
            "method_name": "export_events",
            "description": "Export raw event data with filters and pagination. Returns individual event records. Note: project_id is optional if configured in environment.",
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
                                "items": {"type": "string", "enum": ["profile", "meta"]},
                            },
                            {"type": "null"},
                        ],
                        "description": "Additional data to include (profile, meta)",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "export_events_csv",
            "method_name": "export_events_csv",
            "description": "Export events as CSV-formatted data for spreadsheet analysis. Note: project_id is optional if configured in environment.",
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
            "description": "Export aggregated chart data with time series and breakdowns. Note: project_id is optional if configured in environment.",
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
                        "description": "Date range. Common values: 30min, lastHour, today, yesterday, 1d, 3d, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, lastMonth, yearToDate, lastYear, all. Can also use custom ranges like '2024-01-01 to 2024-12-31'",
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
            "description": "Get total event count with optional filters. Note: project_id is optional if configured in environment.",
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
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, yearToDate, all",
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
            "description": "Get unique user/visitor count for a time period. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, yearToDate, all",
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
            "description": "Get page view statistics over time. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, yearToDate, all",
                        "default": "30d",
                    },
                    "interval": {
                        "type": "string",
                        "enum": ["hour", "day", "week", "month"],
                        "description": "Time interval",
                        "default": "day",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_top_pages",
            "method_name": "get_top_pages",
            "description": "Get top pages by view count. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, yearToDate, all",
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
            "description": "Get top traffic sources/referrers. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, yearToDate, all",
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
            "description": "Get geographic distribution of users/visitors. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, yearToDate, all",
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
            "description": "Get device/browser/OS breakdown of users. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, monthToDate, yearToDate, all",
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
    """Export raw event data"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        result = await client.export_events(
            project_id=effective_project_id,
            event=event,
            profile_id=profile_id,
            start=start,
            end=end,
            page=page,
            limit=limit,
            includes=includes,
        )

        events_count = len(result.get("data", [])) if isinstance(result, dict) else 0

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "count": events_count,
                "page": page,
                "limit": limit,
                "filters": {"event": event, "profile_id": profile_id, "start": start, "end": end},
                "data": result,
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
    """Export events as CSV-formatted data"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        result = await client.export_events(
            project_id=effective_project_id, event=event, start=start, end=end, limit=limit
        )

        events = result.get("data", []) if isinstance(result, dict) else []

        if not events:
            return json.dumps(
                {
                    "success": True,
                    "project_id": effective_project_id,
                    "count": 0,
                    "csv": "",
                    "message": "No events found",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Build CSV
        headers = ["timestamp", "name", "profile_id"]
        csv_lines = [",".join(headers)]

        for event_data in events:
            row = [
                str(event_data.get("timestamp", "")),
                str(event_data.get("name", "")),
                str(event_data.get("profileId", "")),
            ]
            csv_lines.append(",".join(row))

        csv_content = "\n".join(csv_lines)

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "count": len(events),
                "format": "csv",
                "csv": csv_content,
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
    """Export aggregated chart data"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        result = await client.export_charts(
            project_id=effective_project_id,
            events=events,
            interval=interval,
            date_range=date_range,
            breakdowns=breakdowns,
            previous=previous,
        )

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
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
    """Get total event count"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        events_config = [{"name": event if event else "*", "segment": "event"}]

        result = await client.export_charts(
            project_id=effective_project_id,
            events=events_config,
            interval="day",
            date_range=date_range,
        )

        # Sum up the counts
        total = 0
        if isinstance(result, dict) and "data" in result:
            for point in result.get("data", []):
                total += point.get("count", 0)

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "event": event if event else "all events",
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
    """Get unique user count using tRPC overview.stats"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use overview.stats to get visitor count
        result = await client.get_overview_stats(
            project_id=effective_project_id, date_range=date_range
        )

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "date_range": date_range,
                    "error": result.get("error"),
                    "note": "tRPC overview.stats endpoint may require authentication",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Extract unique visitors from overview stats
        unique_users = 0
        if isinstance(result, dict):
            # Try different possible field names for visitors
            unique_users = (
                result.get("visitors", 0)
                or result.get("uniqueVisitors", 0)
                or result.get("current", {}).get("visitors", 0)
            )

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "date_range": date_range,
                "unique_users": unique_users,
                "raw_stats": result if isinstance(result, dict) else None,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_page_views(
    client: OpenPanelClient,
    project_id: str | None = None,
    date_range: str = "30d",
    interval: str = "day",
) -> str:
    """Get page view statistics using tRPC overview.stats"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use overview.stats to get pageview count
        result = await client.get_overview_stats(
            project_id=effective_project_id, date_range=date_range
        )

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "date_range": date_range,
                    "interval": interval,
                    "error": result.get("error"),
                    "note": "tRPC overview.stats endpoint may require authentication",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Extract pageview count from overview stats
        total_page_views = 0
        if isinstance(result, dict):
            # Try different possible field names for pageviews
            total_page_views = (
                result.get("pageviews", 0)
                or result.get("pageViews", 0)
                or result.get("current", {}).get("pageviews", 0)
            )

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "date_range": date_range,
                "interval": interval,
                "total_page_views": total_page_views,
                "raw_stats": result if isinstance(result, dict) else None,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_top_pages(
    client: OpenPanelClient, project_id: str | None = None, date_range: str = "30d", limit: int = 10
) -> str:
    """Get top pages by view count using tRPC overview.topPages"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use the new tRPC overview.topPages endpoint
        result = await client.get_top_pages(
            project_id=effective_project_id, date_range=date_range, mode="page"
        )

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "date_range": date_range,
                    "error": result.get("error"),
                    "note": "tRPC overview.topPages endpoint may require authentication",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Transform tRPC response to our format
        pages = []
        if isinstance(result, list):
            pages = result[:limit]
        elif isinstance(result, dict) and "data" in result:
            pages = result.get("data", [])[:limit]

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "date_range": date_range,
                "count": len(pages),
                "top_pages": pages,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_top_referrers(
    client: OpenPanelClient, project_id: str | None = None, date_range: str = "30d", limit: int = 10
) -> str:
    """Get top traffic sources using chart.chart with referrer breakdown"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use chart.chart with referrer breakdown
        result = await client.get_top_sources(
            project_id=effective_project_id, date_range=date_range, limit=limit
        )

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "date_range": date_range,
                    "error": result.get("error"),
                    "note": "tRPC chart.chart endpoint may require authentication",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Extract referrers from chart.chart response
        # Response format: {series: [{data: [...], breakdowns: {referrer: [...]}}]}
        referrers = []
        if isinstance(result, dict):
            series = result.get("series", [])
            if series:
                for serie in series:
                    breakdown_data = serie.get("breakdowns", {}).get("referrer", [])
                    for item in breakdown_data[:limit]:
                        referrers.append(
                            {
                                "referrer": item.get("label", item.get("name", "")),
                                "count": item.get("count", 0),
                                "percentage": item.get("percentage", 0),
                            }
                        )

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "date_range": date_range,
                "count": len(referrers),
                "top_referrers": referrers,
            },
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
    """Get geographic distribution using chart.chart with country/city/region breakdown"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use chart.chart with geographic breakdown
        result = await client.get_top_locations(
            project_id=effective_project_id, date_range=date_range, breakdown=breakdown, limit=limit
        )

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "date_range": date_range,
                    "breakdown": breakdown,
                    "error": result.get("error"),
                    "note": "tRPC chart.chart endpoint may require authentication",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Extract locations from chart.chart response
        # Response format: {series: [{data: [...], breakdowns: {country: [...]}}]}
        locations = []
        if isinstance(result, dict):
            series = result.get("series", [])
            if series:
                for serie in series:
                    breakdown_data = serie.get("breakdowns", {}).get(breakdown, [])
                    for item in breakdown_data[:limit]:
                        locations.append(
                            {
                                "location": item.get("label", item.get("name", "")),
                                "count": item.get("count", 0),
                                "percentage": item.get("percentage", 0),
                            }
                        )

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "date_range": date_range,
                "breakdown": breakdown,
                "count": len(locations),
                "locations": locations,
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
    """Get device/browser/OS breakdown using chart.chart with appropriate breakdown"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use appropriate chart.chart breakdown based on breakdown type
        if breakdown == "browser":
            result = await client.get_top_browsers(
                project_id=effective_project_id, date_range=date_range, limit=limit
            )
        elif breakdown == "os":
            result = await client.get_top_os(
                project_id=effective_project_id, date_range=date_range, limit=limit
            )
        else:  # device (default)
            result = await client.get_top_devices(
                project_id=effective_project_id, date_range=date_range, limit=limit
            )

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "date_range": date_range,
                    "breakdown": breakdown,
                    "error": result.get("error"),
                    "note": "tRPC chart.chart endpoint may require authentication",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Extract device data from chart.chart response
        # Response format: {series: [{data: [...], breakdowns: {device: [...]}}]}
        devices = []
        if isinstance(result, dict):
            series = result.get("series", [])
            if series:
                for serie in series:
                    breakdown_data = serie.get("breakdowns", {}).get(breakdown, [])
                    for item in breakdown_data[:limit]:
                        devices.append(
                            {
                                "name": item.get("label", item.get("name", "")),
                                "count": item.get("count", 0),
                                "percentage": item.get("percentage", 0),
                            }
                        )

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "date_range": date_range,
                "breakdown": breakdown,
                "count": len(devices),
                "devices": devices,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
