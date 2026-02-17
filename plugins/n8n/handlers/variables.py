"""Variables Handler - manages n8n environment variables"""

import json
from typing import Any

from plugins.n8n.client import N8nClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_variables",
            "method_name": "list_variables",
            "description": "[Enterprise] List all environment variables. Requires n8n Enterprise/Pro license. All parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 250},
                    "cursor": {"type": "string", "description": "OPTIONAL: Pagination cursor."},
                },
            },
            "scope": "read",
        },
        {
            "name": "get_variable",
            "method_name": "get_variable",
            "description": "[Enterprise] Get variable value by key. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "minLength": 1, "description": "Variable key"}
                },
                "required": ["key"],
            },
            "scope": "read",
        },
        {
            "name": "create_variable",
            "method_name": "create_variable",
            "description": "[Enterprise] Create a new environment variable. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "minLength": 1, "description": "Variable key"},
                    "value": {"type": "string", "description": "Variable value"},
                },
                "required": ["key", "value"],
            },
            "scope": "admin",
        },
        {
            "name": "update_variable",
            "method_name": "update_variable",
            "description": "[Enterprise] Update an existing variable's value. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "minLength": 1},
                    "value": {"type": "string", "description": "New value"},
                },
                "required": ["key", "value"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_variable",
            "method_name": "delete_variable",
            "description": "[Enterprise] Delete an environment variable. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {"key": {"type": "string", "minLength": 1}},
                "required": ["key"],
            },
            "scope": "admin",
        },
        {
            "name": "set_variables",
            "method_name": "set_variables",
            "description": "[Enterprise] Bulk set multiple variables at once. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "variables": {
                        "type": "object",
                        "description": "Key-value pairs of variables to set",
                        "additionalProperties": {"type": "string"},
                    }
                },
                "required": ["variables"],
            },
            "scope": "admin",
        },
    ]


async def list_variables(client: N8nClient, limit: int = 100, cursor: str | None = None) -> str:
    try:
        response = await client.list_variables(limit=limit, cursor=cursor)
        variables = response.get("data", [])
        result = {
            "success": True,
            "count": len(variables),
            "variables": [{"key": v.get("key"), "value": v.get("value")} for v in variables],
            "next_cursor": response.get("nextCursor"),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_variable(client: N8nClient, key: str) -> str:
    try:
        variable = await client.get_variable(key)
        return json.dumps(
            {
                "success": True,
                "variable": {"key": variable.get("key"), "value": variable.get("value")},
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_variable(client: N8nClient, key: str, value: str) -> str:
    try:
        await client.create_variable(key, value)
        return json.dumps(
            {
                "success": True,
                "message": f"Variable '{key}' created",
                "variable": {"key": key, "value": value},
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_variable(client: N8nClient, key: str, value: str) -> str:
    try:
        await client.update_variable(key, value)
        return json.dumps(
            {
                "success": True,
                "message": f"Variable '{key}' updated",
                "variable": {"key": key, "value": value},
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_variable(client: N8nClient, key: str) -> str:
    try:
        await client.delete_variable(key)
        return json.dumps({"success": True, "message": f"Variable '{key}' deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def set_variables(client: N8nClient, variables: dict[str, str]) -> str:
    try:
        created, updated, failed = [], [], []

        for key, value in variables.items():
            try:
                # Try to get existing variable
                try:
                    await client.get_variable(key)
                    # Variable exists, update it
                    await client.update_variable(key, value)
                    updated.append(key)
                except:
                    # Variable doesn't exist, create it
                    await client.create_variable(key, value)
                    created.append(key)
            except Exception as e:
                failed.append({"key": key, "error": str(e)})

        return json.dumps(
            {
                "success": len(failed) == 0,
                "created": created,
                "updated": updated,
                "failed": failed if failed else None,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
