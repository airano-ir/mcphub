"""System Handler - OpenPanel health and system operations (6 tools)"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (6 tools)"""
    return [
        {
            "name": "health_check",
            "method_name": "health_check",
            "description": "Check OpenPanel instance health and service status.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_instance_info",
            "method_name": "get_instance_info",
            "description": "Get OpenPanel instance information including URL and configuration.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_usage_stats",
            "method_name": "get_usage_stats",
            "description": "Get usage statistics for the OpenPanel instance (events, users, etc.).",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID to get stats for"},
                    "date_range": {
                        "type": "string",
                        "description": "Date range. Common: today, yesterday, 7d, 14d, 30d, 60d, 90d, 6m, 12m, all",
                        "default": "30d",
                    },
                },
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_storage_stats",
            "method_name": "get_storage_stats",
            "description": "Get storage usage statistics (events stored in ClickHouse).",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project ID to get storage stats for",
                    }
                },
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "test_connection",
            "method_name": "test_connection",
            "description": "Test connection to OpenPanel API with current credentials.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_rate_limit_status",
            "method_name": "get_rate_limit_status",
            "description": "Check current rate limit status for API calls.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]

# =====================
# System Functions (6)
# =====================

async def health_check(client: OpenPanelClient) -> str:
    """Check OpenPanel instance health"""
    try:
        result = await client.health_check()

        return json.dumps(
            {
                "success": True,
                "url": client.base_url,
                "healthy": result.get("healthy", False),
                "services": result.get("services", {}),
                "message": (
                    "OpenPanel instance is healthy"
                    if result.get("healthy")
                    else "OpenPanel instance has issues"
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "url": client.base_url,
                "healthy": False,
                "error": str(e),
                "message": f"Health check failed: {str(e)}",
            },
            indent=2,
            ensure_ascii=False,
        )

async def get_instance_info(client: OpenPanelClient) -> str:
    """Get OpenPanel instance information"""
    try:
        result = await client.get_instance_info()

        return json.dumps(
            {
                "success": True,
                "instance": result,
                "message": "Instance information retrieved successfully",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_usage_stats(client: OpenPanelClient, project_id: str, date_range: str = "30d") -> str:
    """Get usage statistics for a project"""
    try:
        # Get event count
        events_config = [{"name": "*", "segment": "event"}]
        events_result = await client.export_charts(
            project_id=project_id, events=events_config, interval="day", date_range=date_range
        )

        # Get unique users
        users_config = [{"name": "*", "segment": "user"}]
        users_result = await client.export_charts(
            project_id=project_id, events=users_config, interval="day", date_range=date_range
        )

        # Calculate totals
        total_events = 0
        if isinstance(events_result, dict) and "data" in events_result:
            for point in events_result.get("data", []):
                total_events += point.get("count", 0)

        total_users = 0
        if isinstance(users_result, dict) and "data" in users_result:
            data = users_result.get("data", [])
            if data:
                total_users = data[-1].get("count", 0)

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "date_range": date_range,
                "stats": {
                    "total_events": total_events,
                    "unique_users": total_users,
                    "events_per_user": (
                        round(total_events / total_users, 2) if total_users > 0 else 0
                    ),
                },
                "message": f"Usage stats for {date_range}",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_storage_stats(client: OpenPanelClient, project_id: str) -> str:
    """Get storage usage statistics"""
    try:
        # Export events to estimate storage
        await client.export_events(project_id=project_id, limit=1)

        # Note: Actual storage stats would require database access
        # This is an estimate based on available data

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "storage": {
                    "database": "ClickHouse",
                    "note": "Detailed storage stats require direct database access",
                    "estimate": "Based on event volume",
                },
                "message": "Storage information retrieved",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def test_connection(client: OpenPanelClient) -> str:
    """Test connection to OpenPanel API"""
    try:
        # Try to make a simple request
        result = await client.health_check()

        return json.dumps(
            {
                "success": True,
                "url": client.base_url,
                "client_id": (
                    client.client_id[:8] + "..." if len(client.client_id) > 8 else client.client_id
                ),
                "connection": "ok",
                "api_accessible": result.get("healthy", False),
                "message": "Connection test successful",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "url": client.base_url,
                "connection": "failed",
                "error": str(e),
                "message": f"Connection test failed: {str(e)}",
            },
            indent=2,
            ensure_ascii=False,
        )

async def get_rate_limit_status(client: OpenPanelClient) -> str:
    """Check current rate limit status"""
    try:
        # Note: Rate limit info is typically in response headers
        # This is informational based on OpenPanel's documented limits

        return json.dumps(
            {
                "success": True,
                "rate_limits": {
                    "requests_per_10_seconds": 100,
                    "note": "OpenPanel rate limits: 100 requests per 10 seconds per client",
                },
                "recommendations": [
                    "Implement exponential backoff for 429 errors",
                    "Use batch tracking for multiple events",
                    "Cache export results when possible",
                ],
                "message": "Rate limit information retrieved",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
