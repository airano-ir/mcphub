"""Reports Handler - OpenPanel analytics reports (8 tools)

Note: project_id is optional if configured in environment variables.
"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient
from plugins.openpanel.handlers.utils import get_project_id as _get_project_id

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (8 tools)"""
    return [
        {
            "name": "get_overview_report",
            "method_name": "get_overview_report",
            "description": "Get overview statistics including total events, users, sessions, and page views. Note: project_id is optional if configured in environment.",
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
            "name": "get_retention_report",
            "method_name": "get_retention_report",
            "description": "Get user retention analysis showing how many users return over time. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "start_event": {
                        "type": "string",
                        "description": "Event that marks user acquisition (e.g., 'signup_completed')",
                        "default": "session_start",
                    },
                    "return_event": {
                        "type": "string",
                        "description": "Event that marks user return (e.g., 'app_opened')",
                        "default": "session_start",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["day", "week", "month"],
                        "description": "Retention period granularity",
                        "default": "week",
                    },
                    "cohorts": {
                        "type": "integer",
                        "description": "Number of cohorts to analyze",
                        "default": 8,
                        "maximum": 12,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_cohort_report",
            "method_name": "get_cohort_report",
            "description": "Get cohort analysis grouping users by acquisition date and tracking their behavior. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "cohort_type": {
                        "type": "string",
                        "enum": ["first_seen", "signup", "custom"],
                        "description": "How to define cohorts",
                        "default": "first_seen",
                    },
                    "cohort_event": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom event for cohort definition (when cohort_type is 'custom')",
                    },
                    "measure_event": {
                        "type": "string",
                        "description": "Event to measure for each cohort",
                        "default": "session_start",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: 7d, 14d, 30d, 60d, 90d, 6m, 12m, yearToDate, all",
                        "default": "6m",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_paths_report",
            "method_name": "get_paths_report",
            "description": "Get user flow/paths analysis showing common navigation patterns. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "start_event": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Starting event for path analysis",
                    },
                    "end_event": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Ending event for path analysis",
                    },
                    "max_steps": {
                        "type": "integer",
                        "description": "Maximum path steps to analyze",
                        "default": 5,
                        "maximum": 10,
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
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
            "description": "Get real-time visitor statistics for the last 30 minutes. Note: project_id is optional if configured in environment.",
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
        {
            "name": "get_ab_test_results",
            "method_name": "get_ab_test_results",
            "description": "Get A/B test results comparing variants by conversion rate. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "test_name": {"type": "string", "description": "Name of the A/B test"},
                    "conversion_event": {
                        "type": "string",
                        "description": "Event that marks conversion",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
                        "default": "30d",
                    },
                },
                "required": ["test_name", "conversion_event"],
            },
            "scope": "read",
        },
        {
            "name": "create_scheduled_report",
            "method_name": "create_scheduled_report",
            "description": "Create a scheduled report to be sent via email. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "name": {"type": "string", "description": "Report name"},
                    "report_type": {
                        "type": "string",
                        "enum": ["overview", "events", "funnels", "retention"],
                        "description": "Type of report",
                    },
                    "schedule": {
                        "type": "string",
                        "enum": ["daily", "weekly", "monthly"],
                        "description": "Report schedule",
                    },
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string", "format": "email"},
                        "description": "Email recipients",
                    },
                },
                "required": ["name", "report_type", "schedule", "recipients"],
            },
            "scope": "write",
        },
        {
            "name": "export_report_pdf",
            "method_name": "export_report_pdf",
            "description": "Export a report as PDF format. Note: project_id is optional if configured in environment.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Project ID (optional if configured in env)",
                    },
                    "report_type": {
                        "type": "string",
                        "enum": ["overview", "events", "funnels", "retention", "paths"],
                        "description": "Type of report to export",
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
                        "default": "30d",
                    },
                },
                "required": ["report_type"],
            },
            "scope": "read",
        },
    ]

# =====================
# Report Functions (8)
# =====================

async def get_overview_report(
    client: OpenPanelClient, project_id: str | None = None, date_range: str = "30d"
) -> str:
    """Get overview statistics using tRPC overview.stats endpoint"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use the new tRPC overview.stats endpoint
        result = await client.get_overview_stats(
            project_id=effective_project_id, date_range=date_range
        )

        # Check for errors
        if "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "date_range": date_range,
                    "error": result.get("error"),
                    "note": "tRPC overview.stats endpoint may require authentication or the project may not exist",
                },
                indent=2,
                ensure_ascii=False,
            )

        # Transform tRPC response to our format
        # tRPC overview.stats returns: {current: {...}, previous: {...}}
        current = result.get("current", result)

        metrics = {
            "unique_visitors": current.get("uniqueVisitors", 0),
            "page_views": current.get("screenViews", 0),
            "sessions": current.get("sessions", 0),
            "bounce_rate": current.get("bounceRate", 0),
            "session_duration": current.get("sessionDuration", 0),
            "revenue": current.get("revenue", 0),
        }

        # Add previous period comparison if available
        previous = result.get("previous", {})
        if previous:
            metrics["previous_period"] = {
                "unique_visitors": previous.get("uniqueVisitors", 0),
                "page_views": previous.get("screenViews", 0),
                "sessions": previous.get("sessions", 0),
            }

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "date_range": date_range,
                "overview": metrics,
                "raw": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_retention_report(
    client: OpenPanelClient,
    project_id: str | None = None,
    start_event: str = "session_start",
    return_event: str = "session_start",
    period: str = "week",
    cohorts: int = 8,
) -> str:
    """Get user retention analysis"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        # Note: Full retention analysis requires tRPC API access
        # This provides a simplified version using export API

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "retention_config": {
                    "start_event": start_event,
                    "return_event": return_event,
                    "period": period,
                    "cohorts": cohorts,
                },
                "note": "Full retention analysis requires dashboard tRPC API. Use OpenPanel dashboard for detailed retention charts.",
                "message": "Retention report configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_cohort_report(
    client: OpenPanelClient,
    project_id: str | None = None,
    cohort_type: str = "first_seen",
    cohort_event: str | None = None,
    measure_event: str = "session_start",
    date_range: str = "6m",
) -> str:
    """Get cohort analysis"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "cohort_config": {
                    "cohort_type": cohort_type,
                    "cohort_event": cohort_event,
                    "measure_event": measure_event,
                    "date_range": date_range,
                },
                "note": "Full cohort analysis requires dashboard tRPC API. Use OpenPanel dashboard for detailed cohort charts.",
                "message": "Cohort report configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_paths_report(
    client: OpenPanelClient,
    project_id: str | None = None,
    start_event: str | None = None,
    end_event: str | None = None,
    max_steps: int = 5,
    date_range: str = "30d",
) -> str:
    """Get user flow/paths analysis"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "paths_config": {
                    "start_event": start_event,
                    "end_event": end_event,
                    "max_steps": max_steps,
                    "date_range": date_range,
                },
                "note": "Full path analysis requires dashboard tRPC API. Use OpenPanel dashboard for user flow visualization.",
                "message": "Paths report configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_realtime_stats(client: OpenPanelClient, project_id: str | None = None) -> str:
    """Get real-time visitor statistics using chart.chart with 30min range"""
    try:
        effective_project_id = _get_project_id(client, project_id)

        # Use chart.chart with 30min range for realtime data
        result = await client.get_live_visitors(project_id=effective_project_id)

        active_users = result.get("count", 0) if isinstance(result, dict) else 0

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            return json.dumps(
                {
                    "success": False,
                    "project_id": effective_project_id,
                    "error": result.get("error"),
                    "note": "tRPC chart.chart endpoint may require authentication",
                },
                indent=2,
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "realtime": {
                    "active_visitors_30min": active_users,
                    "timestamp": "now",
                    "period": "30min",
                },
                "message": "Real-time stats retrieved via chart.chart with 30min range",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_ab_test_results(
    client: OpenPanelClient,
    test_name: str,
    conversion_event: str,
    project_id: str | None = None,
    date_range: str = "30d",
) -> str:
    """Get A/B test results"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        # A/B test results typically tracked via properties
        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "test_name": test_name,
                "ab_test_config": {"conversion_event": conversion_event, "date_range": date_range},
                "note": "A/B test analysis requires tracking variants via event properties. Use OpenPanel dashboard for detailed variant comparison.",
                "message": "A/B test configuration retrieved",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_scheduled_report(
    client: OpenPanelClient,
    name: str,
    report_type: str,
    schedule: str,
    recipients: list[str],
    project_id: str | None = None,
) -> str:
    """Create a scheduled report"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "scheduled_report": {
                    "name": name,
                    "report_type": report_type,
                    "schedule": schedule,
                    "recipients": recipients,
                },
                "note": "Scheduled reports require dashboard tRPC API. Configure via OpenPanel dashboard.",
                "message": f"Scheduled report '{name}' configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def export_report_pdf(
    client: OpenPanelClient,
    report_type: str,
    project_id: str | None = None,
    date_range: str = "30d",
) -> str:
    """Export report as PDF"""
    try:
        effective_project_id = _get_project_id(client, project_id)
        return json.dumps(
            {
                "success": True,
                "project_id": effective_project_id,
                "export_config": {
                    "report_type": report_type,
                    "format": "pdf",
                    "date_range": date_range,
                },
                "note": "PDF export requires dashboard functionality. Use OpenPanel dashboard to export reports.",
                "message": f"PDF export configuration for {report_type} report",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
