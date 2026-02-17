"""Execution Handler - manages n8n workflow executions"""

import asyncio
import json
from typing import Any

from plugins.n8n.client import N8nClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === LIST EXECUTIONS ===
        {
            "name": "list_executions",
            "method_name": "list_executions",
            "description": "List workflow executions with filters by status, workflow, and date. Returns execution history. All filter parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "OPTIONAL: Filter by workflow ID. Omit for all executions.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["success", "error", "waiting", "running", "new"],
                        "description": "OPTIONAL: Filter by execution status. Omit for all statuses.",
                    },
                    "include_data": {
                        "type": "boolean",
                        "description": "Include full execution data",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 250,
                    },
                    "cursor": {"type": "string", "description": "OPTIONAL: Pagination cursor."},
                },
            },
            "scope": "read",
        },
        # === GET EXECUTION ===
        {
            "name": "get_execution",
            "method_name": "get_execution",
            "description": "Get detailed information about a specific execution including status, timing, and node outputs.",
            "schema": {
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Execution ID",
                        "minLength": 1,
                    },
                    "include_data": {
                        "type": "boolean",
                        "description": "Include full node execution data",
                        "default": True,
                    },
                },
                "required": ["execution_id"],
            },
            "scope": "read",
        },
        # === DELETE EXECUTION ===
        {
            "name": "delete_execution",
            "method_name": "delete_execution",
            "description": "Delete a single execution record. This removes the execution from history.",
            "schema": {
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Execution ID to delete",
                        "minLength": 1,
                    }
                },
                "required": ["execution_id"],
            },
            "scope": "write",
        },
        # === DELETE EXECUTIONS (BULK) ===
        {
            "name": "delete_executions",
            "method_name": "delete_executions",
            "description": "Bulk delete multiple execution records.",
            "schema": {
                "type": "object",
                "properties": {
                    "execution_ids": {
                        "type": "array",
                        "description": "List of execution IDs to delete",
                        "items": {"type": "string"},
                        "minItems": 1,
                    }
                },
                "required": ["execution_ids"],
            },
            "scope": "write",
        },
        # === STOP EXECUTION ===
        {
            "name": "stop_execution",
            "method_name": "stop_execution",
            "description": "Stop a currently running execution.",
            "schema": {
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Execution ID to stop",
                        "minLength": 1,
                    }
                },
                "required": ["execution_id"],
            },
            "scope": "write",
        },
        # === RETRY EXECUTION ===
        {
            "name": "retry_execution",
            "method_name": "retry_execution",
            "description": "Retry a failed execution. Creates a new execution with the same input data.",
            "schema": {
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Execution ID to retry",
                        "minLength": 1,
                    }
                },
                "required": ["execution_id"],
            },
            "scope": "write",
        },
        # === GET EXECUTION DATA ===
        {
            "name": "get_execution_data",
            "method_name": "get_execution_data",
            "description": "Get full execution data including all node inputs and outputs. Useful for debugging.",
            "schema": {
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Execution ID",
                        "minLength": 1,
                    }
                },
                "required": ["execution_id"],
            },
            "scope": "read",
        },
        # === WAIT FOR EXECUTION ===
        {
            "name": "wait_for_execution",
            "method_name": "wait_for_execution",
            "description": "Poll an execution until it completes. Returns final status and output.",
            "schema": {
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Execution ID to wait for",
                        "minLength": 1,
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Maximum seconds to wait",
                        "default": 60,
                        "minimum": 5,
                        "maximum": 300,
                    },
                    "poll_interval": {
                        "type": "integer",
                        "description": "Seconds between status checks",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 30,
                    },
                },
                "required": ["execution_id"],
            },
            "scope": "read",
        },
    ]


# === HANDLER FUNCTIONS ===


async def list_executions(
    client: N8nClient,
    workflow_id: str | None = None,
    status: str | None = None,
    include_data: bool = False,
    limit: int = 20,
    cursor: str | None = None,
) -> str:
    """List workflow executions"""
    try:
        response = await client.list_executions(
            workflow_id=workflow_id,
            status=status,
            include_data=include_data,
            limit=limit,
            cursor=cursor,
        )

        executions = response.get("data", [])
        next_cursor = response.get("nextCursor")

        result = {
            "success": True,
            "count": len(executions),
            "executions": [
                {
                    "id": e.get("id"),
                    "workflow_id": e.get("workflowId"),
                    "workflow_name": e.get("workflowData", {}).get("name"),
                    "status": e.get("status"),
                    "finished": e.get("finished"),
                    "started_at": e.get("startedAt"),
                    "stopped_at": e.get("stoppedAt"),
                    "mode": e.get("mode"),
                }
                for e in executions
            ],
            "next_cursor": next_cursor,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_execution(client: N8nClient, execution_id: str, include_data: bool = True) -> str:
    """Get execution details"""
    try:
        execution = await client.get_execution(execution_id, include_data)

        result = {
            "success": True,
            "execution": {
                "id": execution.get("id"),
                "workflow_id": execution.get("workflowId"),
                "workflow_name": execution.get("workflowData", {}).get("name"),
                "status": execution.get("status"),
                "finished": execution.get("finished"),
                "started_at": execution.get("startedAt"),
                "stopped_at": execution.get("stoppedAt"),
                "mode": execution.get("mode"),
                "retry_of": execution.get("retryOf"),
                "retry_success_id": execution.get("retrySuccessId"),
            },
        }

        # Include node execution data if requested
        if include_data and "data" in execution:
            result["execution"]["node_data"] = execution.get("data")

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_execution(client: N8nClient, execution_id: str) -> str:
    """Delete a single execution"""
    try:
        await client.delete_execution(execution_id)

        result = {"success": True, "message": f"Execution {execution_id} deleted successfully"}

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_executions(client: N8nClient, execution_ids: list[str]) -> str:
    """Bulk delete executions"""
    try:
        deleted = []
        failed = []

        for exec_id in execution_ids:
            try:
                await client.delete_execution(exec_id)
                deleted.append(exec_id)
            except Exception as e:
                failed.append({"id": exec_id, "error": str(e)})

        result = {
            "success": len(failed) == 0,
            "deleted_count": len(deleted),
            "deleted": deleted,
            "failed": failed if failed else None,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def stop_execution(client: N8nClient, execution_id: str) -> str:
    """Stop a running execution"""
    try:
        await client.stop_execution(execution_id)

        result = {"success": True, "message": f"Execution {execution_id} stopped successfully"}

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def retry_execution(client: N8nClient, execution_id: str) -> str:
    """Retry a failed execution"""
    try:
        # Get the original execution to find workflow ID
        original = await client.get_execution(execution_id, include_data=True)

        workflow_id = original.get("workflowId")
        if not workflow_id:
            raise Exception("Cannot find workflow ID from execution")

        # Get input data from original execution
        input_data = None
        exec_data = original.get("data", {})
        if exec_data:
            # Try to get input from first node
            result_data = exec_data.get("resultData", {})
            run_data = result_data.get("runData", {})
            if run_data:
                first_node = list(run_data.keys())[0] if run_data else None
                if first_node:
                    node_data = run_data[first_node]
                    if node_data and len(node_data) > 0:
                        input_data = node_data[0].get("data", {}).get("main", [[]])[0]

        # Execute the workflow again
        new_execution = await client.execute_workflow(workflow_id, data=input_data)

        result = {
            "success": True,
            "message": f"Retrying execution {execution_id}",
            "original_execution_id": execution_id,
            "new_execution": {
                "id": new_execution.get("id"),
                "workflow_id": workflow_id,
                "status": new_execution.get("status", "running"),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_execution_data(client: N8nClient, execution_id: str) -> str:
    """Get full execution data"""
    try:
        execution = await client.get_execution(execution_id, include_data=True)

        exec_data = execution.get("data", {})
        result_data = exec_data.get("resultData", {})

        result = {
            "success": True,
            "execution_id": execution_id,
            "status": execution.get("status"),
            "finished": execution.get("finished"),
            "run_data": result_data.get("runData", {}),
            "last_node_executed": result_data.get("lastNodeExecuted"),
            "error": result_data.get("error"),
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def wait_for_execution(
    client: N8nClient, execution_id: str, timeout_seconds: int = 60, poll_interval: int = 2
) -> str:
    """Wait for execution to complete"""
    try:
        elapsed = 0
        final_status = None
        execution = None

        while elapsed < timeout_seconds:
            execution = await client.get_execution(execution_id, include_data=True)
            status = execution.get("status")
            finished = execution.get("finished")

            if finished or status in ["success", "error", "crashed"]:
                final_status = status
                break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if not final_status:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Timeout after {timeout_seconds} seconds",
                    "execution_id": execution_id,
                    "last_status": execution.get("status") if execution else "unknown",
                },
                indent=2,
            )

        result = {
            "success": True,
            "execution_id": execution_id,
            "final_status": final_status,
            "finished": execution.get("finished"),
            "started_at": execution.get("startedAt"),
            "stopped_at": execution.get("stoppedAt"),
            "duration_seconds": elapsed,
        }

        # Include error if failed
        if final_status == "error":
            exec_data = execution.get("data", {})
            result_data = exec_data.get("resultData", {})
            result["error"] = result_data.get("error")

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
