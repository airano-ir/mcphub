"""
Collections & Fields Handler - Schema management

Phase J.1: 14 tools
- Collections: list, get, create, update, delete (5)
- Fields: list, get, create, update, delete (5)
- Relations: list, get, create, delete (4)
"""

import json
from typing import Any

from plugins.directus.client import DirectusClient

def _parse_json_param(value: Any, param_name: str = "parameter") -> Any:
    """
    Parse a parameter that may be a JSON string or already a native type.

    MCP tools may receive object/array parameters as JSON strings.
    This function safely converts them to proper Python types.

    Args:
        value: The value to parse (may be string, dict, list, or None)
        param_name: Name of parameter for error messages

    Returns:
        Parsed value (dict, list, or original value if not JSON)
    """
    if value is None:
        return None

    # Already the correct type
    if isinstance(value, (dict, list)):
        return value

    # Try to parse JSON string
    if isinstance(value, str):
        stripped = value.strip()
        # Check if it looks like JSON (starts with { or [)
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in '{param_name}': {e}")

    return value

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (14 tools)"""
    return [
        # =====================
        # COLLECTIONS (5)
        # =====================
        {
            "name": "list_collections",
            "method_name": "list_collections",
            "description": "List all collections (tables) in Directus.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "get_collection",
            "method_name": "get_collection",
            "description": "Get collection details including schema and meta information.",
            "schema": {
                "type": "object",
                "properties": {"collection": {"type": "string", "description": "Collection name"}},
                "required": ["collection"],
            },
            "scope": "read",
        },
        {
            "name": "create_collection",
            "method_name": "create_collection",
            "description": "Create a new collection (table) in Directus.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name (table name)"},
                    "meta": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Collection meta (icon, note, hidden, singleton, etc.)",
                    },
                    "schema": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Schema options (name, comment)",
                    },
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "object"}}, {"type": "null"}],
                        "description": "Initial fields to create with collection",
                    },
                },
                "required": ["collection"],
            },
            "scope": "admin",
        },
        {
            "name": "update_collection",
            "method_name": "update_collection",
            "description": "Update collection meta information.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "meta": {
                        "type": "object",
                        "description": "Meta fields to update (icon, note, hidden, etc.)",
                    },
                },
                "required": ["collection", "meta"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_collection",
            "method_name": "delete_collection",
            "description": "Delete a collection and all its data. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name to delete"}
                },
                "required": ["collection"],
            },
            "scope": "admin",
        },
        # =====================
        # FIELDS (5)
        # =====================
        {
            "name": "list_fields",
            "method_name": "list_fields",
            "description": "List all fields, optionally filtered by collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Collection name (optional, lists all fields if not provided)",
                    }
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_field",
            "method_name": "get_field",
            "description": "Get field details including schema, meta, and type information.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "field": {"type": "string", "description": "Field name"},
                },
                "required": ["collection", "field"],
            },
            "scope": "read",
        },
        {
            "name": "create_field",
            "method_name": "create_field",
            "description": "Create a new field in a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "field": {"type": "string", "description": "Field name"},
                    "type": {
                        "type": "string",
                        "description": "Field type (string, integer, boolean, uuid, datetime, json, etc.)",
                    },
                    "meta": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Field meta (interface, display, options, etc.)",
                    },
                    "schema": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Schema options (is_nullable, default_value, etc.)",
                    },
                },
                "required": ["collection", "field", "type"],
            },
            "scope": "admin",
        },
        {
            "name": "update_field",
            "method_name": "update_field",
            "description": "Update field configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "field": {"type": "string", "description": "Field name"},
                    "meta": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Meta fields to update",
                    },
                    "schema": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Schema fields to update",
                    },
                },
                "required": ["collection", "field"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_field",
            "method_name": "delete_field",
            "description": "Delete a field from a collection. This removes the column and all data.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "field": {"type": "string", "description": "Field name to delete"},
                },
                "required": ["collection", "field"],
            },
            "scope": "admin",
        },
        # =====================
        # RELATIONS (4)
        # =====================
        {
            "name": "list_relations",
            "method_name": "list_relations",
            "description": "List all relations (foreign keys), optionally filtered by collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Collection name (optional)",
                    }
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_relation",
            "method_name": "get_relation",
            "description": "Get relation details.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "field": {"type": "string", "description": "Field name"},
                },
                "required": ["collection", "field"],
            },
            "scope": "read",
        },
        {
            "name": "create_relation",
            "method_name": "create_relation",
            "description": "Create a new relation (foreign key) between collections.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name (many side)"},
                    "field": {"type": "string", "description": "Field name for the relation"},
                    "related_collection": {
                        "type": "string",
                        "description": "Related collection name (one side)",
                    },
                    "meta": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Relation meta (one_field, junction_field, etc.)",
                    },
                    "schema": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Schema options (on_delete, etc.)",
                    },
                },
                "required": ["collection", "field", "related_collection"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_relation",
            "method_name": "delete_relation",
            "description": "Delete a relation.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "field": {"type": "string", "description": "Field name"},
                },
                "required": ["collection", "field"],
            },
            "scope": "admin",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_collections(client: DirectusClient) -> str:
    """List all collections."""
    try:
        result = await client.list_collections()
        collections = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(collections), "collections": collections},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_collection(client: DirectusClient, collection: str) -> str:
    """Get collection details."""
    try:
        result = await client.get_collection(collection)
        return json.dumps(
            {"success": True, "collection": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_collection(
    client: DirectusClient,
    collection: str,
    meta: dict | None = None,
    schema: dict | None = None,
    fields: list[dict] | None = None,
) -> str:
    """Create a new collection."""
    try:
        # Parse JSON string parameters
        parsed_meta = _parse_json_param(meta, "meta")
        parsed_schema = _parse_json_param(schema, "schema")
        parsed_fields = _parse_json_param(fields, "fields")

        # Auto-fill schema.name if schema is provided but missing name
        # This ensures a real database table is created, not just a folder collection
        if parsed_schema is not None:
            if not isinstance(parsed_schema, dict):
                parsed_schema = {}
            if "name" not in parsed_schema:
                parsed_schema["name"] = collection

        result = await client.create_collection(
            collection=collection, meta=parsed_meta, schema=parsed_schema, fields=parsed_fields
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Collection '{collection}' created",
                "collection": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_collection(client: DirectusClient, collection: str, meta: dict) -> str:
    """Update collection meta."""
    try:
        # Parse JSON string parameter
        parsed_meta = _parse_json_param(meta, "meta")
        result = await client.update_collection(collection, parsed_meta)
        return json.dumps(
            {
                "success": True,
                "message": f"Collection '{collection}' updated",
                "collection": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_collection(client: DirectusClient, collection: str) -> str:
    """Delete a collection."""
    try:
        await client.delete_collection(collection)
        return json.dumps(
            {"success": True, "message": f"Collection '{collection}' deleted"}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_fields(client: DirectusClient, collection: str | None = None) -> str:
    """List fields."""
    try:
        result = await client.list_fields(collection)
        fields = result.get("data", [])
        return json.dumps(
            {"success": True, "collection": collection, "total": len(fields), "fields": fields},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_field(client: DirectusClient, collection: str, field: str) -> str:
    """Get field details."""
    try:
        result = await client.get_field(collection, field)
        return json.dumps(
            {"success": True, "field": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_field(
    client: DirectusClient,
    collection: str,
    field: str,
    type: str,
    meta: dict | None = None,
    schema: dict | None = None,
) -> str:
    """Create a new field."""
    try:
        # Parse JSON string parameters
        parsed_meta = _parse_json_param(meta, "meta")
        parsed_schema = _parse_json_param(schema, "schema")

        result = await client.create_field(
            collection=collection, field=field, type=type, meta=parsed_meta, schema=parsed_schema
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Field '{field}' created in {collection}",
                "field": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_field(
    client: DirectusClient,
    collection: str,
    field: str,
    meta: dict | None = None,
    schema: dict | None = None,
) -> str:
    """Update field configuration."""
    try:
        # Parse JSON string parameters
        parsed_meta = _parse_json_param(meta, "meta")
        parsed_schema = _parse_json_param(schema, "schema")

        result = await client.update_field(
            collection=collection, field=field, meta=parsed_meta, schema=parsed_schema
        )
        return json.dumps(
            {"success": True, "message": f"Field '{field}' updated", "field": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_field(client: DirectusClient, collection: str, field: str) -> str:
    """Delete a field."""
    try:
        await client.delete_field(collection, field)
        return json.dumps(
            {"success": True, "message": f"Field '{field}' deleted from {collection}"}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_relations(client: DirectusClient, collection: str | None = None) -> str:
    """List relations."""
    try:
        result = await client.list_relations(collection)
        relations = result.get("data", [])
        return json.dumps(
            {
                "success": True,
                "collection": collection,
                "total": len(relations),
                "relations": relations,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_relation(client: DirectusClient, collection: str, field: str) -> str:
    """Get relation details."""
    try:
        result = await client.get_relation(collection, field)
        return json.dumps(
            {"success": True, "relation": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_relation(
    client: DirectusClient,
    collection: str,
    field: str,
    related_collection: str,
    meta: dict | None = None,
    schema: dict | None = None,
) -> str:
    """Create a new relation."""
    try:
        # Parse JSON string parameters
        parsed_meta = _parse_json_param(meta, "meta")
        parsed_schema = _parse_json_param(schema, "schema")

        result = await client.create_relation(
            collection=collection,
            field=field,
            related_collection=related_collection,
            meta=parsed_meta,
            schema=parsed_schema,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Relation created: {collection}.{field} -> {related_collection}",
                "relation": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_relation(client: DirectusClient, collection: str, field: str) -> str:
    """Delete a relation."""
    try:
        await client.delete_relation(collection, field)
        return json.dumps(
            {"success": True, "message": f"Relation {collection}.{field} deleted"}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
