"""
Automation Handler - Flows, Operations, Webhooks

Phase J.3: 12 tools
- Flows: list, get, create, update, delete, trigger (6)
- Operations: list, create (2)
- Webhooks: list, create, update, delete (4)
"""

import json
from typing import Any

from plugins.directus.client import DirectusClient


def _parse_json_param(value: Any, param_name: str = "parameter") -> Any:
    """Parse a parameter that may be a JSON string or already a native type."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in '{param_name}': {e}")
    return value


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (12 tools)"""
    return [
        # =====================
        # FLOWS (6)
        # =====================
        {
            "name": "list_flows",
            "method_name": "list_flows",
            "description": "List all automation flows.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Filter object",
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum flows to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_flow",
            "method_name": "get_flow",
            "description": "Get flow details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Flow UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "create_flow",
            "method_name": "create_flow",
            "description": "Create a new automation flow.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Flow name"},
                    "trigger": {
                        "type": "string",
                        "enum": ["event", "schedule", "operation", "webhook", "manual"],
                        "description": "Trigger type",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive"],
                        "default": "active",
                        "description": "Flow status",
                    },
                    "icon": {"type": "string", "description": "Material icon", "default": "bolt"},
                    "options": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Trigger-specific options",
                    },
                    "accountability": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "enum": ["all", "activity", None],
                        "description": "Accountability tracking",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Flow description",
                    },
                },
                "required": ["name", "trigger"],
            },
            "scope": "admin",
        },
        {
            "name": "update_flow",
            "method_name": "update_flow",
            "description": "Update flow settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Flow UUID"},
                    "data": {"type": "object", "description": "Fields to update"},
                },
                "required": ["id", "data"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_flow",
            "method_name": "delete_flow",
            "description": "Delete a flow and its operations.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Flow UUID to delete"}},
                "required": ["id"],
            },
            "scope": "admin",
        },
        {
            "name": "trigger_flow",
            "method_name": "trigger_flow",
            "description": "Manually trigger a flow.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Flow UUID"},
                    "data": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Data to pass to the flow",
                    },
                },
                "required": ["id"],
            },
            "scope": "write",
        },
        # =====================
        # OPERATIONS (2)
        # =====================
        {
            "name": "list_operations",
            "method_name": "list_operations",
            "description": "List all operations in flows.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"flow": {"_eq": "flow-uuid"}})',
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum operations to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "create_operation",
            "method_name": "create_operation",
            "description": "Create a new operation in a flow.",
            "schema": {
                "type": "object",
                "properties": {
                    "flow": {"type": "string", "description": "Flow UUID"},
                    "type": {
                        "type": "string",
                        "description": "Operation type (e.g., 'log', 'mail', 'request', 'item-create')",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Operation name",
                    },
                    "key": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Operation key (for referencing in other operations)",
                    },
                    "options": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Operation-specific options",
                    },
                    "position_x": {
                        "type": "integer",
                        "description": "X position in flow editor",
                        "default": 0,
                    },
                    "position_y": {
                        "type": "integer",
                        "description": "Y position in flow editor",
                        "default": 0,
                    },
                },
                "required": ["flow", "type"],
            },
            "scope": "admin",
        },
        # =====================
        # WEBHOOKS (4)
        # =====================
        {
            "name": "list_webhooks",
            "method_name": "list_webhooks",
            "description": "[DEPRECATED] List all webhooks. Webhooks are deprecated in Directus 10+, use Flows instead.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Filter object",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum webhooks to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "create_webhook",
            "method_name": "create_webhook",
            "description": "[DEPRECATED] Create a new webhook. Use Flows instead in Directus 10+. See create_flow and create_operation for the recommended alternative.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Webhook name"},
                    "url": {"type": "string", "description": "Target URL"},
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Actions to trigger (create, update, delete)",
                    },
                    "collections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Collections to watch",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "default": "POST",
                        "description": "HTTP method",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive"],
                        "default": "active",
                        "description": "Webhook status",
                    },
                    "headers": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Custom headers",
                    },
                },
                "required": ["name", "url", "actions", "collections"],
            },
            "scope": "admin",
        },
        {
            "name": "update_webhook",
            "method_name": "update_webhook",
            "description": "[DEPRECATED] Update webhook settings. Use Flows instead in Directus 10+.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Webhook ID"},
                    "data": {"type": "object", "description": "Fields to update"},
                },
                "required": ["id", "data"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_webhook",
            "method_name": "delete_webhook",
            "description": "[DEPRECATED] Delete a webhook. Use Flows instead in Directus 10+.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Webhook ID to delete"}},
                "required": ["id"],
            },
            "scope": "admin",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def list_flows(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
) -> str:
    """List flows."""
    try:
        # Parse JSON string parameters
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_flows(filter=parsed_filter, sort=parsed_sort, limit=limit)
        flows = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(flows), "flows": flows}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_flow(client: DirectusClient, id: str) -> str:
    """Get flow by ID."""
    try:
        result = await client.get_flow(id)
        return json.dumps(
            {"success": True, "flow": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_flow(
    client: DirectusClient,
    name: str,
    trigger: str,
    status: str = "active",
    icon: str = "bolt",
    options: dict | None = None,
    accountability: str | None = None,
    description: str | None = None,
) -> str:
    """Create a new flow."""
    try:
        # Parse JSON string parameter
        parsed_options = _parse_json_param(options, "options")

        result = await client.create_flow(
            name=name,
            trigger=trigger,
            status=status,
            icon=icon,
            options=parsed_options,
            accountability=accountability,
            description=description,
        )
        return json.dumps(
            {"success": True, "message": f"Flow '{name}' created", "flow": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_flow(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update flow."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.update_flow(id, parsed_data)
        return json.dumps(
            {"success": True, "message": "Flow updated", "flow": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_flow(client: DirectusClient, id: str) -> str:
    """Delete a flow."""
    try:
        await client.delete_flow(id)
        return json.dumps({"success": True, "message": f"Flow {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def trigger_flow(client: DirectusClient, id: str, data: dict | None = None) -> str:
    """Trigger a flow manually."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.trigger_flow(id, parsed_data)
        return json.dumps(
            {
                "success": True,
                "message": f"Flow {id} triggered",
                "result": result.get("data") if result else None,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_operations(
    client: DirectusClient, filter: dict | None = None, limit: int = 100
) -> str:
    """List operations."""
    try:
        # Parse JSON string parameter
        parsed_filter = _parse_json_param(filter, "filter")
        result = await client.list_operations(filter=parsed_filter, limit=limit)
        operations = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(operations), "operations": operations},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_operation(
    client: DirectusClient,
    flow: str,
    type: str,
    name: str | None = None,
    key: str | None = None,
    options: dict | None = None,
    position_x: int = 0,
    position_y: int = 0,
) -> str:
    """Create a new operation."""
    try:
        # Parse JSON string parameter
        parsed_options = _parse_json_param(options, "options")

        result = await client.create_operation(
            flow=flow,
            type=type,
            name=name,
            key=key,
            options=parsed_options,
            position_x=position_x,
            position_y=position_y,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Operation '{type}' created in flow",
                "operation": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_webhooks(
    client: DirectusClient, filter: dict | None = None, limit: int = 100
) -> str:
    """List webhooks. DEPRECATED: Use Flows instead in Directus 10+."""
    try:
        # Parse JSON string parameter
        parsed_filter = _parse_json_param(filter, "filter")
        result = await client.list_webhooks(filter=parsed_filter, limit=limit)
        webhooks = result.get("data", [])
        return json.dumps(
            {
                "success": True,
                "total": len(webhooks),
                "webhooks": webhooks,
                "warning": "DEPRECATED: Webhooks are deprecated in Directus 10+. Use Flows instead.",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_webhook(
    client: DirectusClient,
    name: str,
    url: str,
    actions: list[str],
    collections: list[str],
    method: str = "POST",
    status: str = "active",
    headers: dict | None = None,
) -> str:
    """Create a new webhook. DEPRECATED: Use Flows instead in Directus 10+."""
    try:
        # Parse JSON string parameters
        parsed_actions = _parse_json_param(actions, "actions")
        parsed_collections = _parse_json_param(collections, "collections")
        parsed_headers = _parse_json_param(headers, "headers")

        result = await client.create_webhook(
            name=name,
            url=url,
            actions=parsed_actions,
            collections=parsed_collections,
            method=method,
            status=status,
            headers=parsed_headers,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Webhook '{name}' created",
                "warning": "DEPRECATED: Webhooks are deprecated in Directus 10+. Use Flows instead for better reliability. See create_flow and create_operation tools.",
                "webhook": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        error_msg = str(e)
        return json.dumps(
            {
                "success": False,
                "error": error_msg,
                "hint": "Webhooks are deprecated in Directus 10+. Consider using Flows instead: 1) create_flow with trigger='event', 2) create_operation with type='request' for HTTP calls.",
            },
            indent=2,
        )


async def update_webhook(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update webhook. DEPRECATED: Use Flows instead in Directus 10+."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.update_webhook(id, parsed_data)
        return json.dumps(
            {
                "success": True,
                "message": "Webhook updated",
                "warning": "DEPRECATED: Webhooks are deprecated in Directus 10+. Use Flows instead.",
                "webhook": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "hint": "Webhooks are deprecated in Directus 10+. Consider migrating to Flows.",
            },
            indent=2,
        )


async def delete_webhook(client: DirectusClient, id: str) -> str:
    """Delete a webhook. DEPRECATED: Use Flows instead in Directus 10+."""
    try:
        await client.delete_webhook(id)
        return json.dumps(
            {
                "success": True,
                "message": f"Webhook {id} deleted",
                "note": "Consider using Flows instead of Webhooks in Directus 10+.",
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
