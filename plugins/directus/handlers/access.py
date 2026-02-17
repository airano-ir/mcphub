"""
Access Control Handler - Roles, Permissions, Policies

Phase J.3: 12 tools
- Roles: list, get, create, update, delete (5)
- Permissions: list, get, create, update, delete, get_my (6)
- Policies: list (1)

Note: Directus v10+ uses policies for permissions.
      The 'policy' parameter is required in create_permission.
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
        # ROLES (5)
        # =====================
        {
            "name": "list_roles",
            "method_name": "list_roles",
            "description": "List all roles in Directus.",
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
                        "description": "Maximum roles to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_role",
            "method_name": "get_role",
            "description": "Get role details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Role UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "create_role",
            "method_name": "create_role",
            "description": "Create a new role.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Role name"},
                    "icon": {
                        "type": "string",
                        "description": "Material icon name",
                        "default": "supervised_user_circle",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Role description",
                    },
                    "admin_access": {
                        "type": "boolean",
                        "description": "Full admin access",
                        "default": False,
                    },
                    "app_access": {
                        "type": "boolean",
                        "description": "Access to admin app",
                        "default": True,
                    },
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        {
            "name": "update_role",
            "method_name": "update_role",
            "description": "Update role settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Role UUID"},
                    "data": {
                        "type": "object",
                        "description": "Fields to update (name, icon, description, admin_access, etc.)",
                    },
                },
                "required": ["id", "data"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_role",
            "method_name": "delete_role",
            "description": "Delete a role. Users with this role will have no role.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Role UUID to delete"}},
                "required": ["id"],
            },
            "scope": "admin",
        },
        # =====================
        # PERMISSIONS (6)
        # =====================
        {
            "name": "list_permissions",
            "method_name": "list_permissions",
            "description": "List all permissions.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"role": {"_eq": "role-uuid"}})',
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum permissions to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_permission",
            "method_name": "get_permission",
            "description": "Get permission details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Permission ID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "create_permission",
            "method_name": "create_permission",
            "description": "Create a new permission rule. NOTE: In Directus v10+, 'policy' is required.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "action": {
                        "type": "string",
                        "enum": ["create", "read", "update", "delete", "share"],
                        "description": "Permission action",
                    },
                    "policy": {
                        "type": "string",
                        "description": "Policy UUID (REQUIRED in Directus v10+). Use list_policies to get available policies.",
                    },
                    "role": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Role UUID (null for public) - deprecated in v10+, use policy instead",
                    },
                    "permissions": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Filter rules for this permission",
                    },
                    "validation": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Validation rules for create/update",
                    },
                    "presets": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Default values for create",
                    },
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Allowed fields (* for all)",
                    },
                },
                "required": ["collection", "action", "policy"],
            },
            "scope": "admin",
        },
        {
            "name": "update_permission",
            "method_name": "update_permission",
            "description": "Update a permission rule.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Permission ID"},
                    "data": {"type": "object", "description": "Fields to update"},
                },
                "required": ["id", "data"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_permission",
            "method_name": "delete_permission",
            "description": "Delete a permission rule.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Permission ID to delete"}},
                "required": ["id"],
            },
            "scope": "admin",
        },
        {
            "name": "get_my_permissions",
            "method_name": "get_my_permissions",
            "description": "Get the current user's effective permissions.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        # =====================
        # POLICIES (1)
        # =====================
        {
            "name": "list_policies",
            "method_name": "list_policies",
            "description": "List all access policies.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Filter object",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum policies to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def list_roles(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
) -> str:
    """List roles."""
    try:
        # Parse JSON string parameters
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_roles(filter=parsed_filter, sort=parsed_sort, limit=limit)
        roles = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(roles), "roles": roles}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_role(client: DirectusClient, id: str) -> str:
    """Get role by ID."""
    try:
        result = await client.get_role(id)
        return json.dumps(
            {"success": True, "role": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_role(
    client: DirectusClient,
    name: str,
    icon: str = "supervised_user_circle",
    description: str | None = None,
    admin_access: bool = False,
    app_access: bool = True,
) -> str:
    """Create a new role."""
    try:
        result = await client.create_role(
            name=name,
            icon=icon,
            description=description,
            admin_access=admin_access,
            app_access=app_access,
        )
        return json.dumps(
            {"success": True, "message": f"Role '{name}' created", "role": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_role(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update role."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.update_role(id, parsed_data)
        return json.dumps(
            {"success": True, "message": "Role updated", "role": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_role(client: DirectusClient, id: str) -> str:
    """Delete a role."""
    try:
        await client.delete_role(id)
        return json.dumps({"success": True, "message": f"Role {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_permissions(
    client: DirectusClient, filter: dict | None = None, limit: int = 100
) -> str:
    """List permissions."""
    try:
        # Parse JSON string parameter
        parsed_filter = _parse_json_param(filter, "filter")
        result = await client.list_permissions(filter=parsed_filter, limit=limit)
        permissions = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(permissions), "permissions": permissions},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_permission(client: DirectusClient, id: str) -> str:
    """Get permission by ID."""
    try:
        result = await client.get_permission(id)
        return json.dumps(
            {"success": True, "permission": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_permission(
    client: DirectusClient,
    collection: str,
    action: str,
    policy: str,
    role: str | None = None,
    permissions: dict | None = None,
    validation: dict | None = None,
    presets: dict | None = None,
    fields: list[str] | None = None,
) -> str:
    """Create a new permission. Requires 'policy' in Directus v10+."""
    try:
        # Parse JSON string parameters
        parsed_permissions = _parse_json_param(permissions, "permissions")
        parsed_validation = _parse_json_param(validation, "validation")
        parsed_presets = _parse_json_param(presets, "presets")
        parsed_fields = _parse_json_param(fields, "fields")

        result = await client.create_permission(
            collection=collection,
            action=action,
            policy=policy,
            role=role,
            permissions=parsed_permissions,
            validation=parsed_validation,
            presets=parsed_presets,
            fields=parsed_fields,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Permission created for {collection}.{action}",
                "permission": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_permission(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update permission."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.update_permission(id, parsed_data)
        return json.dumps(
            {"success": True, "message": "Permission updated", "permission": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_permission(client: DirectusClient, id: str) -> str:
    """Delete a permission."""
    try:
        await client.delete_permission(id)
        return json.dumps({"success": True, "message": f"Permission {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_my_permissions(client: DirectusClient) -> str:
    """Get current user's permissions."""
    try:
        result = await client.get_my_permissions()
        return json.dumps(
            {"success": True, "permissions": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_policies(
    client: DirectusClient, filter: dict | None = None, limit: int = 100
) -> str:
    """List policies."""
    try:
        # Parse JSON string parameter
        parsed_filter = _parse_json_param(filter, "filter")
        result = await client.list_policies(filter=parsed_filter, limit=limit)
        policies = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(policies), "policies": policies},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
