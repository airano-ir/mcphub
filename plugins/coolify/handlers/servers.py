"""Server Handler — manages Coolify servers."""

import json
from typing import Any

from plugins.coolify.client import CoolifyClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_servers",
            "method_name": "list_servers",
            "description": "List all servers registered in the Coolify instance.",
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
        {
            "name": "get_server",
            "method_name": "get_server",
            "description": "Get details of a specific server by UUID, including settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Server UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "create_server",
            "method_name": "create_server",
            "description": (
                "Register a new server in Coolify. "
                "Requires name, IP, port, user, and a private key UUID for SSH access."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Server name",
                        "minLength": 1,
                    },
                    "ip": {
                        "type": "string",
                        "description": "Server IP address",
                        "minLength": 1,
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port",
                        "default": 22,
                    },
                    "user": {
                        "type": "string",
                        "description": "SSH user",
                        "default": "root",
                    },
                    "private_key_uuid": {
                        "type": "string",
                        "description": "Private key UUID for SSH authentication",
                        "minLength": 1,
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Server description",
                    },
                    "is_build_server": {
                        "type": "boolean",
                        "description": "Use as build server",
                        "default": False,
                    },
                    "instant_validate": {
                        "type": "boolean",
                        "description": "Validate server immediately after creation",
                        "default": False,
                    },
                    "proxy_type": {
                        "type": "string",
                        "description": "Proxy type for the server",
                        "enum": ["traefik", "caddy", "none"],
                        "default": "traefik",
                    },
                },
                "required": ["name", "ip", "private_key_uuid"],
            },
            "scope": "admin",
        },
        {
            "name": "update_server",
            "method_name": "update_server",
            "description": "Update server configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Server UUID",
                        "minLength": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Server name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Server description",
                    },
                    "ip": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Server IP address",
                    },
                    "port": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "SSH port",
                    },
                    "user": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "SSH user",
                    },
                    "proxy_type": {
                        "anyOf": [
                            {"type": "string", "enum": ["traefik", "caddy", "none"]},
                            {"type": "null"},
                        ],
                        "description": "Proxy type",
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "delete_server",
            "method_name": "delete_server",
            "description": "Delete a server from Coolify. This cannot be undone!",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Server UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "admin",
        },
        {
            "name": "get_server_resources",
            "method_name": "get_server_resources",
            "description": (
                "Get all resources (applications, databases, services) "
                "deployed on a specific server."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Server UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "get_server_domains",
            "method_name": "get_server_domains",
            "description": "Get all domains configured on a specific server.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Server UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "validate_server",
            "method_name": "validate_server",
            "description": "Validate server connectivity and configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Server UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
    ]


# --- Handler Functions ---


async def list_servers(client: CoolifyClient) -> str:
    """List all servers."""
    servers = await client.list_servers()
    result = {"success": True, "count": len(servers), "servers": servers}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_server(client: CoolifyClient, uuid: str) -> str:
    """Get server details."""
    server = await client.get_server(uuid)
    result = {"success": True, "server": server}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_server(client: CoolifyClient, **kwargs) -> str:
    """Create a new server."""
    server = await client.create_server(kwargs)
    result = {
        "success": True,
        "message": "Server created successfully",
        "server": server,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_server(client: CoolifyClient, uuid: str, **kwargs) -> str:
    """Update server configuration."""
    data = {k: v for k, v in kwargs.items() if v is not None and k != "uuid"}
    server = await client.update_server(uuid, data)
    result = {
        "success": True,
        "message": f"Server '{uuid}' updated",
        "server": server,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_server(client: CoolifyClient, uuid: str) -> str:
    """Delete a server."""
    await client.delete_server(uuid)
    result = {"success": True, "message": f"Server '{uuid}' deleted"}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_server_resources(client: CoolifyClient, uuid: str) -> str:
    """Get server resources."""
    resources = await client.get_server_resources(uuid)
    result = {"success": True, "count": len(resources), "resources": resources}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_server_domains(client: CoolifyClient, uuid: str) -> str:
    """Get server domains."""
    domains = await client.get_server_domains(uuid)
    result = {"success": True, "domains": domains}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def validate_server(client: CoolifyClient, uuid: str) -> str:
    """Validate server."""
    result_data = await client.validate_server(uuid)
    result = {
        "success": True,
        "message": "Server validation started",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)
