"""Deployment Handler — manages Coolify deployments."""

import json
from typing import Any

from plugins.coolify.client import CoolifyClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_deployments",
            "category": "read",
            "method_name": "list_deployments",
            "description": "List all running deployments on the Coolify instance.",
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
        {
            "name": "get_deployment",
            "category": "read",
            "method_name": "get_deployment",
            "description": "Get details of a specific deployment by UUID.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Deployment UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "cancel_deployment",
            "category": "lifecycle",
            "method_name": "cancel_deployment",
            "description": "Cancel a running deployment.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Deployment UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "deploy",
            "category": "lifecycle",
            "method_name": "deploy",
            "description": (
                "Trigger deployment by tag name or resource UUID. "
                "Can deploy multiple resources at once using comma-separated values."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "tag": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Tag name(s), comma-separated",
                    },
                    "uuid": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Resource UUID(s), comma-separated",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force rebuild without cache",
                        "default": False,
                    },
                },
            },
            "scope": "write",
        },
        {
            "name": "list_app_deployments",
            "category": "read",
            "method_name": "list_app_deployments",
            "description": "List deployment history for a specific application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "skip": {
                        "type": "integer",
                        "description": "Number of deployments to skip",
                        "default": 0,
                        "minimum": 0,
                    },
                    "take": {
                        "type": "integer",
                        "description": "Number of deployments to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
    ]


# --- Handler Functions ---


async def list_deployments(client: CoolifyClient) -> str:
    """List running deployments."""
    deployments = await client.list_deployments()
    result = {"success": True, "count": len(deployments), "deployments": deployments}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_deployment(client: CoolifyClient, uuid: str) -> str:
    """Get deployment details."""
    deployment = await client.get_deployment(uuid)
    result = {"success": True, "deployment": deployment}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def cancel_deployment(client: CoolifyClient, uuid: str) -> str:
    """Cancel a deployment."""
    result_data = await client.cancel_deployment(uuid)
    result = {
        "success": True,
        "message": f"Deployment '{uuid}' cancelled",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def deploy(
    client: CoolifyClient,
    tag: str | None = None,
    uuid: str | None = None,
    force: bool = False,
) -> str:
    """Deploy by tag or UUID."""
    result_data = await client.deploy(tag=tag, uuid=uuid, force=force)
    result = {"success": True, "message": "Deployment triggered", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def list_app_deployments(
    client: CoolifyClient, uuid: str, skip: int = 0, take: int = 10
) -> str:
    """List deployment history for an application."""
    deployments = await client.list_app_deployments(uuid, skip=skip, take=take)
    result = {"success": True, "count": len(deployments), "deployments": deployments}
    return json.dumps(result, indent=2, ensure_ascii=False)
