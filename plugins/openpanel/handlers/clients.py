"""Clients Handler - OpenPanel API client management (5 tools).

Uses Manage API (GET/POST/PATCH/DELETE /manage/clients).
Requires 'root' mode client.
"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (5 tools)."""
    return [
        {
            "name": "list_clients",
            "method_name": "list_clients",
            "description": "List all API clients via Manage API. Requires 'root' mode client.",
            "schema": {"type": "object", "properties": {}},
            "scope": "admin",
        },
        {
            "name": "get_client",
            "method_name": "get_client",
            "description": "Get API client details via Manage API. Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client ID"},
                },
                "required": ["client_id"],
            },
            "scope": "admin",
        },
        {
            "name": "create_client",
            "method_name": "create_client",
            "description": "Create a new API client via Manage API. Modes: 'write' (tracking only), 'read' (export/analytics), 'root' (full access). Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Client name"},
                    "project_id": {"type": "string", "description": "Project to associate with"},
                    "mode": {
                        "type": "string",
                        "enum": ["write", "read", "root"],
                        "description": "Client mode: write (tracking), read (export/analytics), root (full access)",
                        "default": "write",
                    },
                },
                "required": ["name", "project_id"],
            },
            "scope": "admin",
        },
        {
            "name": "update_client",
            "method_name": "update_client",
            "description": "Update an API client via Manage API. Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client ID to update"},
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New client name",
                    },
                    "mode": {
                        "anyOf": [
                            {"type": "string", "enum": ["write", "read", "root"]},
                            {"type": "null"},
                        ],
                        "description": "New client mode",
                    },
                },
                "required": ["client_id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_client",
            "method_name": "delete_client",
            "description": "Delete an API client via Manage API. WARNING: Any integrations using this client will stop working. Requires 'root' mode client.",
            "schema": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client ID to delete"},
                },
                "required": ["client_id"],
            },
            "scope": "admin",
        },
    ]


# =====================
# Client Functions (5)
# =====================


async def list_clients(client: OpenPanelClient) -> str:
    """List all API clients via GET /manage/clients."""
    try:
        result = await client.list_clients()
        clients = (
            result
            if isinstance(result, list)
            else result.get("data", []) if isinstance(result, dict) else []
        )
        return json.dumps(
            {"success": True, "count": len(clients), "clients": clients},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_client(client: OpenPanelClient, client_id: str) -> str:
    """Get client details via GET /manage/clients/:id."""
    try:
        result = await client.get_client(client_id)
        return json.dumps({"success": True, "client": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def create_client(
    client: OpenPanelClient,
    name: str,
    project_id: str,
    mode: str = "write",
) -> str:
    """Create a new API client via POST /manage/clients."""
    try:
        data: dict[str, Any] = {"name": name, "projectId": project_id, "mode": mode}
        result = await client.create_client(data)
        return json.dumps(
            {
                "success": True,
                "message": f"Client '{name}' created with {mode} mode",
                "client": result,
                "note": "Save the client_secret — it cannot be retrieved later.",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def update_client(
    client: OpenPanelClient,
    client_id: str,
    name: str | None = None,
    mode: str | None = None,
) -> str:
    """Update a client via PATCH /manage/clients/:id."""
    try:
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if mode:
            data["mode"] = mode
        if not data:
            return json.dumps(
                {"success": False, "error": "No fields to update. Provide name or mode."},
                indent=2,
                ensure_ascii=False,
            )
        result = await client.update_client(client_id, data)
        return json.dumps(
            {"success": True, "message": f"Client '{client_id}' updated", "client": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def delete_client(client: OpenPanelClient, client_id: str) -> str:
    """Delete a client via DELETE /manage/clients/:id."""
    try:
        result = await client.delete_client(client_id)
        return json.dumps(
            {"success": True, "message": f"Client '{client_id}' deleted", "result": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
