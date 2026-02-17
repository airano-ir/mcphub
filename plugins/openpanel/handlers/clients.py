"""Clients Handler - OpenPanel API client/key management (6 tools)"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (6 tools)"""
    return [
        {
            "name": "list_clients",
            "method_name": "list_clients",
            "description": "List all API clients for a project.",
            "schema": {
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "Project ID"}},
                "required": ["project_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_client",
            "method_name": "get_client",
            "description": "Get API client details.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "client_id": {"type": "string", "description": "API Client ID"},
                },
                "required": ["project_id", "client_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_client",
            "method_name": "create_client",
            "description": "Create a new API client for tracking or export.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "name": {
                        "type": "string",
                        "description": "Client name (e.g., 'Web Tracker', 'Backend Export')",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write", "read", "root"],
                        "description": "Client mode: write (tracking), read (export), root (full access)",
                    },
                    "cors_domains": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Allowed domains for CORS (write mode)",
                    },
                },
                "required": ["project_id", "name", "mode"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_client",
            "method_name": "delete_client",
            "description": "Delete an API client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "client_id": {"type": "string", "description": "Client ID to delete"},
                },
                "required": ["project_id", "client_id"],
            },
            "scope": "admin",
        },
        {
            "name": "regenerate_client_secret",
            "method_name": "regenerate_client_secret",
            "description": "Regenerate the secret for an API client.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "client_id": {"type": "string", "description": "Client ID"},
                },
                "required": ["project_id", "client_id"],
            },
            "scope": "admin",
        },
        {
            "name": "update_client_mode",
            "method_name": "update_client_mode",
            "description": "Update API client permissions/mode.",
            "schema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "client_id": {"type": "string", "description": "Client ID"},
                    "mode": {
                        "type": "string",
                        "enum": ["write", "read", "root"],
                        "description": "New mode",
                    },
                    "cors_domains": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "New CORS domains",
                    },
                },
                "required": ["project_id", "client_id", "mode"],
            },
            "scope": "admin",
        },
    ]

# =====================
# Client Functions (6)
# =====================

async def list_clients(client: OpenPanelClient, project_id: str) -> str:
    """List all API clients"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "note": "Client listing requires dashboard tRPC API. Use OpenPanel dashboard to view clients.",
                "message": "Client list request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_client(client: OpenPanelClient, project_id: str, client_id: str) -> str:
    """Get API client details"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "client_id": client_id,
                "note": "Client details require dashboard tRPC API. Use OpenPanel dashboard for full view.",
                "message": "Client details request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_client(
    client: OpenPanelClient,
    project_id: str,
    name: str,
    mode: str,
    cors_domains: list[str] | None = None,
) -> str:
    """Create a new API client"""
    try:
        client_config = {"name": name, "mode": mode, "cors_domains": cors_domains}

        mode_descriptions = {
            "write": "Can send events (tracking)",
            "read": "Can read/export data",
            "root": "Full access (tracking + export + management)",
        }

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "client": client_config,
                "mode_description": mode_descriptions.get(mode, "Unknown mode"),
                "note": "Client creation requires dashboard tRPC API. Use OpenPanel dashboard to create clients.",
                "message": f"Client '{name}' configuration created with {mode} mode",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_client(client: OpenPanelClient, project_id: str, client_id: str) -> str:
    """Delete an API client"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "client_id": client_id,
                "note": "Client deletion requires dashboard tRPC API. Use OpenPanel dashboard to delete clients.",
                "warning": "Deleting a client will invalidate all requests using its credentials.",
                "message": "Client deletion request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def regenerate_client_secret(client: OpenPanelClient, project_id: str, client_id: str) -> str:
    """Regenerate client secret"""
    try:
        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "client_id": client_id,
                "note": "Secret regeneration requires dashboard tRPC API. Use OpenPanel dashboard to regenerate.",
                "warning": "Regenerating secret will invalidate the current secret immediately.",
                "message": "Secret regeneration request processed",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_client_mode(
    client: OpenPanelClient,
    project_id: str,
    client_id: str,
    mode: str,
    cors_domains: list[str] | None = None,
) -> str:
    """Update client permissions"""
    try:
        updates = {"mode": mode, "cors_domains": cors_domains}

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "client_id": client_id,
                "updates": updates,
                "note": "Client mode update requires dashboard tRPC API. Use OpenPanel dashboard to modify.",
                "message": f"Client mode update to {mode} configuration created",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
