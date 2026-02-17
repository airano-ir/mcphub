"""Credentials Handler - manages n8n credentials"""

import json
from typing import Any

from plugins.n8n.client import N8nClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "get_credential",
            "method_name": "get_credential",
            "description": "Get credential metadata by ID. Note: Listing all credentials is not supported in n8n Public API.",
            "schema": {
                "type": "object",
                "properties": {"credential_id": {"type": "string", "minLength": 1}},
                "required": ["credential_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_credential",
            "method_name": "create_credential",
            "description": "Create a new credential. Use get_credential_schema to see required fields.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "description": "Credential name"},
                    "type": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Credential type (e.g., 'githubApi')",
                    },
                    "data": {
                        "type": "object",
                        "description": "Credential data matching the type schema",
                    },
                },
                "required": ["name", "type", "data"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_credential",
            "method_name": "delete_credential",
            "description": "Delete a credential.",
            "schema": {
                "type": "object",
                "properties": {"credential_id": {"type": "string", "minLength": 1}},
                "required": ["credential_id"],
            },
            "scope": "admin",
        },
        {
            "name": "get_credential_schema",
            "method_name": "get_credential_schema",
            "description": "Get the schema for a credential type. Shows required fields.",
            "schema": {
                "type": "object",
                "properties": {
                    "credential_type": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Credential type name",
                    }
                },
                "required": ["credential_type"],
            },
            "scope": "read",
        },
        {
            "name": "transfer_credential",
            "method_name": "transfer_credential",
            "description": "[Enterprise] Transfer a credential to another project. Requires n8n Enterprise/Pro license.",
            "schema": {
                "type": "object",
                "properties": {
                    "credential_id": {"type": "string", "minLength": 1},
                    "destination_project_id": {"type": "string", "minLength": 1},
                },
                "required": ["credential_id", "destination_project_id"],
            },
            "scope": "admin",
        },
    ]

# === HANDLER FUNCTIONS ===
# Note: list_credentials is not supported in n8n Public API (GET /credentials returns 405)

async def get_credential(client: N8nClient, credential_id: str) -> str:
    """Get credential metadata"""
    try:
        cred = await client.get_credential(credential_id)
        result = {
            "success": True,
            "credential": {
                "id": cred.get("id"),
                "name": cred.get("name"),
                "type": cred.get("type"),
                "created_at": cred.get("createdAt"),
                "updated_at": cred.get("updatedAt"),
            },
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_credential(client: N8nClient, name: str, type: str, data: dict[str, Any]) -> str:
    """Create a new credential"""
    try:
        cred_data = {"name": name, "type": type, "data": data}
        cred = await client.create_credential(cred_data)
        result = {
            "success": True,
            "message": f"Credential '{name}' created successfully",
            "credential": {
                "id": cred.get("id"),
                "name": cred.get("name"),
                "type": cred.get("type"),
            },
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_credential(client: N8nClient, credential_id: str) -> str:
    """Delete a credential"""
    try:
        await client.delete_credential(credential_id)
        return json.dumps(
            {"success": True, "message": f"Credential {credential_id} deleted"}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_credential_schema(client: N8nClient, credential_type: str) -> str:
    """Get credential type schema"""
    try:
        schema = await client.get_credential_schema(credential_type)
        return json.dumps(
            {"success": True, "credential_type": credential_type, "schema": schema}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def transfer_credential(
    client: N8nClient, credential_id: str, destination_project_id: str
) -> str:
    """Transfer credential to another project"""
    try:
        await client.transfer_credential(credential_id, destination_project_id)
        return json.dumps(
            {
                "success": True,
                "message": f"Credential {credential_id} transferred to project {destination_project_id}",
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
