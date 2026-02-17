"""
Functions Handler - manages Appwrite serverless functions

Phase I.4: 14 tools
- Functions: 5 (list, get, create, update, delete)
- Deployments: 5 (list, get, create, delete, activate)
- Executions: 4 (list, get, create, delete)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (14 tools)"""
    return [
        # =====================
        # FUNCTIONS (5)
        # =====================
        {
            "name": "list_functions",
            "method_name": "list_functions",
            "description": "List all serverless functions in the project.",
            "schema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter functions",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_function",
            "method_name": "get_function",
            "description": "Get function details including deployment status and configuration.",
            "schema": {
                "type": "object",
                "properties": {"function_id": {"type": "string", "description": "Function ID"}},
                "required": ["function_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_function",
            "method_name": "create_function",
            "description": "Create a new serverless function.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {
                        "type": "string",
                        "description": "Unique function ID. Use 'unique()' for auto-generation",
                    },
                    "name": {"type": "string", "description": "Function name"},
                    "runtime": {
                        "type": "string",
                        "description": "Runtime (e.g., 'node-18.0', 'python-3.9', 'php-8.0', 'ruby-3.0')",
                        "examples": [
                            "node-18.0",
                            "node-20.0",
                            "python-3.9",
                            "python-3.11",
                            "php-8.0",
                            "php-8.2",
                            "ruby-3.0",
                            "go-1.21",
                            "dart-3.0",
                            "rust-1.70",
                        ],
                    },
                    "execute": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Execution permissions (e.g., ['any', 'users'])",
                    },
                    "events": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Events to trigger function (e.g., ['databases.*.collections.*.documents.*.create'])",
                    },
                    "schedule": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Cron schedule (e.g., '0 * * * *' for every hour)",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Execution timeout in seconds",
                        "default": 15,
                        "minimum": 1,
                        "maximum": 900,
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable function",
                        "default": True,
                    },
                    "logging": {
                        "type": "boolean",
                        "description": "Enable logging",
                        "default": True,
                    },
                    "entrypoint": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Entrypoint file (e.g., 'src/main.js')",
                    },
                    "commands": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Build commands",
                    },
                },
                "required": ["function_id", "name", "runtime"],
            },
            "scope": "write",
        },
        {
            "name": "update_function",
            "method_name": "update_function",
            "description": "Update function configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "name": {"type": "string", "description": "Function name"},
                    "runtime": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New runtime",
                    },
                    "execute": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "New execution permissions",
                    },
                    "events": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "New trigger events",
                    },
                    "schedule": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New cron schedule",
                    },
                    "timeout": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "New timeout",
                    },
                    "enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable/disable function",
                    },
                },
                "required": ["function_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_function",
            "method_name": "delete_function",
            "description": "Delete a function and all its deployments.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID to delete"}
                },
                "required": ["function_id"],
            },
            "scope": "admin",
        },
        # =====================
        # DEPLOYMENTS (5)
        # =====================
        {
            "name": "list_deployments",
            "method_name": "list_deployments",
            "description": "List all deployments of a function.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term",
                    },
                },
                "required": ["function_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_deployment",
            "method_name": "get_deployment",
            "description": "Get deployment details including build status and logs.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "deployment_id": {"type": "string", "description": "Deployment ID"},
                },
                "required": ["function_id", "deployment_id"],
            },
            "scope": "read",
        },
        {
            "name": "delete_deployment",
            "method_name": "delete_deployment",
            "description": "Delete a deployment.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "deployment_id": {"type": "string", "description": "Deployment ID to delete"},
                },
                "required": ["function_id", "deployment_id"],
            },
            "scope": "write",
        },
        {
            "name": "activate_deployment",
            "method_name": "activate_deployment",
            "description": "Activate a deployment (set as the active version for the function).",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "deployment_id": {"type": "string", "description": "Deployment ID to activate"},
                },
                "required": ["function_id", "deployment_id"],
            },
            "scope": "write",
        },
        {
            "name": "get_active_deployment",
            "method_name": "get_active_deployment",
            "description": "Get the currently active deployment for a function.",
            "schema": {
                "type": "object",
                "properties": {"function_id": {"type": "string", "description": "Function ID"}},
                "required": ["function_id"],
            },
            "scope": "read",
        },
        # =====================
        # EXECUTIONS (4)
        # =====================
        {
            "name": "list_executions",
            "method_name": "list_executions",
            "description": "List execution history for a function.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term",
                    },
                },
                "required": ["function_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_execution",
            "method_name": "get_execution",
            "description": "Get execution details including response, logs, and timing.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "execution_id": {"type": "string", "description": "Execution ID"},
                },
                "required": ["function_id", "execution_id"],
            },
            "scope": "read",
        },
        {
            "name": "execute_function",
            "method_name": "execute_function",
            "description": "Execute a function immediately.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "body": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Request body (JSON string)",
                    },
                    "async_execution": {
                        "type": "boolean",
                        "description": "Run asynchronously (don't wait for response)",
                        "default": False,
                    },
                    "path": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom execution path",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                        "description": "HTTP method",
                        "default": "POST",
                    },
                    "headers": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Custom headers",
                    },
                },
                "required": ["function_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_execution",
            "method_name": "delete_execution",
            "description": "Delete an execution log entry.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function ID"},
                    "execution_id": {"type": "string", "description": "Execution ID to delete"},
                },
                "required": ["function_id", "execution_id"],
            },
            "scope": "write",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_functions(
    client: AppwriteClient, queries: list[str] | None = None, search: str | None = None
) -> str:
    """List all functions."""
    try:
        result = await client.list_functions(queries=queries, search=search)
        functions = result.get("functions", [])

        response = {
            "success": True,
            "total": result.get("total", len(functions)),
            "functions": functions,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_function(client: AppwriteClient, function_id: str) -> str:
    """Get function by ID."""
    try:
        result = await client.get_function(function_id)
        return json.dumps({"success": True, "function": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_function(
    client: AppwriteClient,
    function_id: str,
    name: str,
    runtime: str,
    execute: list[str] | None = None,
    events: list[str] | None = None,
    schedule: str | None = None,
    timeout: int = 15,
    enabled: bool = True,
    logging: bool = True,
    entrypoint: str | None = None,
    commands: str | None = None,
) -> str:
    """Create a new function."""
    try:
        result = await client.create_function(
            function_id=function_id,
            name=name,
            runtime=runtime,
            execute=execute,
            events=events,
            schedule=schedule,
            timeout=timeout,
            enabled=enabled,
            logging=logging,
            entrypoint=entrypoint,
            commands=commands,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Function '{name}' created successfully",
                "function": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_function(
    client: AppwriteClient,
    function_id: str,
    name: str,
    runtime: str | None = None,
    execute: list[str] | None = None,
    events: list[str] | None = None,
    schedule: str | None = None,
    timeout: int | None = None,
    enabled: bool | None = None,
) -> str:
    """Update function."""
    try:
        result = await client.update_function(
            function_id=function_id,
            name=name,
            runtime=runtime,
            execute=execute,
            events=events,
            schedule=schedule,
            timeout=timeout,
            enabled=enabled,
        )
        return json.dumps(
            {"success": True, "message": "Function updated successfully", "function": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_function(client: AppwriteClient, function_id: str) -> str:
    """Delete function."""
    try:
        await client.delete_function(function_id)
        return json.dumps(
            {"success": True, "message": f"Function '{function_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_deployments(
    client: AppwriteClient,
    function_id: str,
    queries: list[str] | None = None,
    search: str | None = None,
) -> str:
    """List function deployments."""
    try:
        result = await client.list_deployments(
            function_id=function_id, queries=queries, search=search
        )
        deployments = result.get("deployments", [])

        response = {
            "success": True,
            "function_id": function_id,
            "total": result.get("total", len(deployments)),
            "deployments": deployments,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_deployment(client: AppwriteClient, function_id: str, deployment_id: str) -> str:
    """Get deployment by ID."""
    try:
        result = await client.get_deployment(function_id, deployment_id)
        return json.dumps({"success": True, "deployment": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_deployment(client: AppwriteClient, function_id: str, deployment_id: str) -> str:
    """Delete deployment."""
    try:
        await client.delete_deployment(function_id, deployment_id)
        return json.dumps(
            {"success": True, "message": f"Deployment '{deployment_id}' deleted successfully"},
            indent=2,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def activate_deployment(client: AppwriteClient, function_id: str, deployment_id: str) -> str:
    """Activate deployment."""
    try:
        result = await client.update_deployment(function_id, deployment_id)
        return json.dumps(
            {
                "success": True,
                "message": f"Deployment '{deployment_id}' activated successfully",
                "deployment": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_active_deployment(client: AppwriteClient, function_id: str) -> str:
    """Get active deployment for function."""
    try:
        func = await client.get_function(function_id)
        deployment_id = func.get("deployment")

        if not deployment_id:
            return json.dumps(
                {
                    "success": True,
                    "message": "No active deployment",
                    "function_id": function_id,
                    "active_deployment": None,
                },
                indent=2,
            )

        deployment = await client.get_deployment(function_id, deployment_id)
        return json.dumps(
            {"success": True, "function_id": function_id, "active_deployment": deployment},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_executions(
    client: AppwriteClient,
    function_id: str,
    queries: list[str] | None = None,
    search: str | None = None,
) -> str:
    """List function executions."""
    try:
        result = await client.list_executions(
            function_id=function_id, queries=queries, search=search
        )
        executions = result.get("executions", [])

        response = {
            "success": True,
            "function_id": function_id,
            "total": result.get("total", len(executions)),
            "executions": executions,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_execution(client: AppwriteClient, function_id: str, execution_id: str) -> str:
    """Get execution by ID."""
    try:
        result = await client.get_execution(function_id, execution_id)
        return json.dumps({"success": True, "execution": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def execute_function(
    client: AppwriteClient,
    function_id: str,
    body: str | None = None,
    async_execution: bool = False,
    path: str | None = None,
    method: str = "POST",
    headers: dict[str, str] | None = None,
) -> str:
    """Execute function."""
    try:
        result = await client.create_execution(
            function_id=function_id,
            body=body,
            async_execution=async_execution,
            path=path,
            method=method,
            headers=headers,
        )

        response = {
            "success": True,
            "execution_id": result.get("$id"),
            "status": result.get("status"),
            "status_code": result.get("responseStatusCode"),
            "duration": result.get("duration"),
            "response_body": result.get("responseBody"),
            "logs": result.get("logs"),
            "errors": result.get("errors"),
        }

        if async_execution:
            response["message"] = "Function execution started asynchronously"
        else:
            response["message"] = "Function executed successfully"

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_execution(client: AppwriteClient, function_id: str, execution_id: str) -> str:
    """Delete execution."""
    try:
        await client.delete_execution(function_id, execution_id)
        return json.dumps(
            {"success": True, "message": f"Execution '{execution_id}' deleted successfully"},
            indent=2,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
