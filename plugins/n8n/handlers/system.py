"""System Handler - manages n8n system operations (audit, source control, health)"""

import json
from typing import Any

from plugins.n8n.client import N8nClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "run_security_audit",
            "method_name": "run_security_audit",
            "description": "Run a security audit on the n8n instance. Returns security diagnostics grouped by category. All parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "OPTIONAL: Specific categories to audit. Omit for all categories.",
                    }
                },
            },
            "scope": "admin",
        },
        {
            "name": "source_control_pull",
            "method_name": "source_control_pull",
            "description": "[Enterprise] Pull workflows from source control (Git). Syncs workflows from connected repository. Requires n8n Enterprise/Pro license. All parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "variables": {
                        "type": "object",
                        "description": "OPTIONAL: Variables to set during pull. Omit if not needed.",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force pull even if conflicts exist",
                        "default": False,
                    },
                },
            },
            "scope": "admin",
        },
        {
            "name": "get_instance_info",
            "method_name": "get_instance_info",
            "description": "Get n8n instance information including version and configuration.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "health_check",
            "method_name": "health_check",
            "description": "Check if the n8n instance is healthy and accessible.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]


async def run_security_audit(client: N8nClient, categories: list[str] | None = None) -> str:
    """Run security audit"""
    try:
        result = await client.run_audit(categories)

        # Parse audit results
        audit_data = {"success": True, "audit_results": result}

        # Extract summary if available
        if isinstance(result, dict):
            risk_report = result.get("risk", {})
            if risk_report:
                audit_data["summary"] = {
                    "risk_categories": list(risk_report.keys()),
                    "total_issues": sum(
                        len(issues) if isinstance(issues, list) else 0
                        for issues in risk_report.values()
                    ),
                }

        return json.dumps(audit_data, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def source_control_pull(
    client: N8nClient, variables: dict[str, str] | None = None, force: bool = False
) -> str:
    """Pull from source control"""
    try:
        result = await client.source_control_pull(variables=variables, force=force)

        return json.dumps(
            {"success": True, "message": "Source control pull completed", "result": result},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_instance_info(client: N8nClient) -> str:
    """Get instance information"""
    try:
        # Try multiple endpoints to gather instance info
        info = {}

        # Get version info from settings or health
        try:
            health = await client.health_check()
            info["health"] = health
        except:
            pass

        # Get current user to verify connectivity
        try:
            user = await client.request("GET", "user")
            info["current_user"] = {
                "id": user.get("id"),
                "email": user.get("email"),
                "role": user.get("role"),
            }
        except:
            pass

        info["instance_url"] = client.site_url
        info["api_base"] = client.api_base

        return json.dumps({"success": True, "instance_info": info}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def health_check(client: N8nClient) -> str:
    """Check instance health"""
    try:
        result = await client.health_check()

        return json.dumps(
            {
                "success": True,
                "healthy": result.get("healthy", False),
                "status": result.get("status", "unknown"),
                "instance_url": client.site_url,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"success": False, "healthy": False, "error": str(e), "instance_url": client.site_url},
            indent=2,
        )
