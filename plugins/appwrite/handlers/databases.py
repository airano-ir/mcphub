"""
Databases Handler - manages Appwrite databases, collections, attributes, and indexes

Phase I.1: 18 tools
- Databases: 5 (list, get, create, update, delete)
- Collections: 5 (list, get, create, update, delete)
- Attributes: 5 (list, create_string, create_integer, create_boolean, delete)
- Indexes: 3 (list, create, delete)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (18 tools)"""
    return [
        # =====================
        # DATABASES (5)
        # =====================
        {
            "name": "list_databases",
            "method_name": "list_databases",
            "description": "List all databases in the Appwrite project. Returns database ID, name, and creation date.",
            "schema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering (e.g., 'limit(25)', 'offset(0)')",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter databases by name",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_database",
            "method_name": "get_database",
            "description": "Get database details by ID.",
            "schema": {
                "type": "object",
                "properties": {"database_id": {"type": "string", "description": "Database ID"}},
                "required": ["database_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_database",
            "method_name": "create_database",
            "description": "Create a new database. Use 'unique()' as database_id to auto-generate a unique ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "Unique database ID. Use 'unique()' for auto-generation",
                    },
                    "name": {"type": "string", "description": "Database name"},
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable or disable the database",
                        "default": True,
                    },
                },
                "required": ["database_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "update_database",
            "method_name": "update_database",
            "description": "Update database name or enabled status.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "name": {"type": "string", "description": "New database name"},
                    "enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable or disable the database",
                    },
                },
                "required": ["database_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_database",
            "method_name": "delete_database",
            "description": "Delete a database and all its collections. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID to delete"}
                },
                "required": ["database_id"],
            },
            "scope": "admin",
        },
        # =====================
        # COLLECTIONS (5)
        # =====================
        {
            "name": "list_collections",
            "method_name": "list_collections",
            "description": "List all collections in a database.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter collections",
                    },
                },
                "required": ["database_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_collection",
            "method_name": "get_collection",
            "description": "Get collection details including attributes and indexes.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                },
                "required": ["database_id", "collection_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_collection",
            "method_name": "create_collection",
            "description": "Create a new collection in a database. Use 'unique()' for auto-generated ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {
                        "type": "string",
                        "description": "Unique collection ID. Use 'unique()' for auto-generation",
                    },
                    "name": {"type": "string", "description": "Collection name"},
                    "permissions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Collection permissions (e.g., 'read(\"any\")', 'write(\"users\")')",
                    },
                    "document_security": {
                        "type": "boolean",
                        "description": "Enable document-level security",
                        "default": True,
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable or disable the collection",
                        "default": True,
                    },
                },
                "required": ["database_id", "collection_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "update_collection",
            "method_name": "update_collection",
            "description": "Update collection settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "name": {"type": "string", "description": "New collection name"},
                    "permissions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "New permissions",
                    },
                    "document_security": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable/disable document-level security",
                    },
                    "enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable/disable the collection",
                    },
                },
                "required": ["database_id", "collection_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_collection",
            "method_name": "delete_collection",
            "description": "Delete a collection and all its documents. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID to delete"},
                },
                "required": ["database_id", "collection_id"],
            },
            "scope": "admin",
        },
        # =====================
        # ATTRIBUTES (5)
        # =====================
        {
            "name": "list_attributes",
            "method_name": "list_attributes",
            "description": "List all attributes (fields/columns) of a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                },
                "required": ["database_id", "collection_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_string_attribute",
            "method_name": "create_string_attribute",
            "description": "Create a string attribute in a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "key": {"type": "string", "description": "Attribute key (field name)"},
                    "size": {
                        "type": "integer",
                        "description": "Maximum string length",
                        "default": 255,
                    },
                    "required": {
                        "type": "boolean",
                        "description": "Is this field required?",
                        "default": False,
                    },
                    "default": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Default value",
                    },
                    "array": {
                        "type": "boolean",
                        "description": "Is this an array attribute?",
                        "default": False,
                    },
                    "encrypt": {
                        "type": "boolean",
                        "description": "Encrypt the attribute value",
                        "default": False,
                    },
                },
                "required": ["database_id", "collection_id", "key"],
            },
            "scope": "write",
        },
        {
            "name": "create_integer_attribute",
            "method_name": "create_integer_attribute",
            "description": "Create an integer attribute in a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "key": {"type": "string", "description": "Attribute key (field name)"},
                    "required": {
                        "type": "boolean",
                        "description": "Is this field required?",
                        "default": False,
                    },
                    "min": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Minimum value",
                    },
                    "max": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum value",
                    },
                    "default": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Default value",
                    },
                    "array": {
                        "type": "boolean",
                        "description": "Is this an array attribute?",
                        "default": False,
                    },
                },
                "required": ["database_id", "collection_id", "key"],
            },
            "scope": "write",
        },
        {
            "name": "create_boolean_attribute",
            "method_name": "create_boolean_attribute",
            "description": "Create a boolean attribute in a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "key": {"type": "string", "description": "Attribute key (field name)"},
                    "required": {
                        "type": "boolean",
                        "description": "Is this field required?",
                        "default": False,
                    },
                    "default": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Default value",
                    },
                    "array": {
                        "type": "boolean",
                        "description": "Is this an array attribute?",
                        "default": False,
                    },
                },
                "required": ["database_id", "collection_id", "key"],
            },
            "scope": "write",
        },
        {
            "name": "delete_attribute",
            "method_name": "delete_attribute",
            "description": "Delete an attribute from a collection. This will remove the field from all documents.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "key": {"type": "string", "description": "Attribute key to delete"},
                },
                "required": ["database_id", "collection_id", "key"],
            },
            "scope": "admin",
        },
        # =====================
        # INDEXES (3)
        # =====================
        {
            "name": "list_indexes",
            "method_name": "list_indexes",
            "description": "List all indexes of a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                },
                "required": ["database_id", "collection_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_index",
            "method_name": "create_index",
            "description": "Create an index on collection attributes for faster queries.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "key": {"type": "string", "description": "Index key (unique name)"},
                    "type": {
                        "type": "string",
                        "enum": ["key", "unique", "fulltext"],
                        "description": "Index type: key (regular), unique, or fulltext",
                    },
                    "attributes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of attribute keys to index",
                    },
                    "orders": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "string", "enum": ["ASC", "DESC"]}},
                            {"type": "null"},
                        ],
                        "description": "Sort order for each attribute (ASC or DESC)",
                    },
                },
                "required": ["database_id", "collection_id", "key", "type", "attributes"],
            },
            "scope": "write",
        },
        {
            "name": "delete_index",
            "method_name": "delete_index",
            "description": "Delete an index from a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "key": {"type": "string", "description": "Index key to delete"},
                },
                "required": ["database_id", "collection_id", "key"],
            },
            "scope": "admin",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_databases(
    client: AppwriteClient, queries: list[str] | None = None, search: str | None = None
) -> str:
    """List all databases."""
    try:
        result = await client.list_databases(queries=queries, search=search)
        databases = result.get("databases", [])

        response = {
            "success": True,
            "total": result.get("total", len(databases)),
            "databases": databases,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_database(client: AppwriteClient, database_id: str) -> str:
    """Get database by ID."""
    try:
        result = await client.get_database(database_id)
        return json.dumps({"success": True, "database": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_database(
    client: AppwriteClient, database_id: str, name: str, enabled: bool = True
) -> str:
    """Create a new database."""
    try:
        result = await client.create_database(database_id=database_id, name=name, enabled=enabled)
        return json.dumps(
            {
                "success": True,
                "message": f"Database '{name}' created successfully",
                "database": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_database(
    client: AppwriteClient, database_id: str, name: str, enabled: bool | None = None
) -> str:
    """Update database."""
    try:
        result = await client.update_database(database_id=database_id, name=name, enabled=enabled)
        return json.dumps(
            {"success": True, "message": "Database updated successfully", "database": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_database(client: AppwriteClient, database_id: str) -> str:
    """Delete database."""
    try:
        await client.delete_database(database_id)
        return json.dumps(
            {"success": True, "message": f"Database '{database_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_collections(
    client: AppwriteClient,
    database_id: str,
    queries: list[str] | None = None,
    search: str | None = None,
) -> str:
    """List collections in a database."""
    try:
        result = await client.list_collections(
            database_id=database_id, queries=queries, search=search
        )
        collections = result.get("collections", [])

        response = {
            "success": True,
            "database_id": database_id,
            "total": result.get("total", len(collections)),
            "collections": collections,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_collection(client: AppwriteClient, database_id: str, collection_id: str) -> str:
    """Get collection details."""
    try:
        result = await client.get_collection(database_id, collection_id)
        return json.dumps({"success": True, "collection": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_collection(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    name: str,
    permissions: list[str] | None = None,
    document_security: bool = True,
    enabled: bool = True,
) -> str:
    """Create a new collection."""
    try:
        result = await client.create_collection(
            database_id=database_id,
            collection_id=collection_id,
            name=name,
            permissions=permissions,
            document_security=document_security,
            enabled=enabled,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Collection '{name}' created successfully",
                "collection": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_collection(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    name: str,
    permissions: list[str] | None = None,
    document_security: bool | None = None,
    enabled: bool | None = None,
) -> str:
    """Update collection."""
    try:
        result = await client.update_collection(
            database_id=database_id,
            collection_id=collection_id,
            name=name,
            permissions=permissions,
            document_security=document_security,
            enabled=enabled,
        )
        return json.dumps(
            {"success": True, "message": "Collection updated successfully", "collection": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_collection(client: AppwriteClient, database_id: str, collection_id: str) -> str:
    """Delete collection."""
    try:
        await client.delete_collection(database_id, collection_id)
        return json.dumps(
            {"success": True, "message": f"Collection '{collection_id}' deleted successfully"},
            indent=2,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_attributes(
    client: AppwriteClient, database_id: str, collection_id: str, queries: list[str] | None = None
) -> str:
    """List collection attributes."""
    try:
        result = await client.list_attributes(
            database_id=database_id, collection_id=collection_id, queries=queries
        )
        attributes = result.get("attributes", [])

        response = {
            "success": True,
            "database_id": database_id,
            "collection_id": collection_id,
            "total": result.get("total", len(attributes)),
            "attributes": attributes,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_string_attribute(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    key: str,
    size: int = 255,
    required: bool = False,
    default: str | None = None,
    array: bool = False,
    encrypt: bool = False,
) -> str:
    """Create string attribute."""
    try:
        result = await client.create_string_attribute(
            database_id=database_id,
            collection_id=collection_id,
            key=key,
            size=size,
            required=required,
            default=default,
            array=array,
            encrypt=encrypt,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"String attribute '{key}' created successfully",
                "attribute": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_integer_attribute(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    key: str,
    required: bool = False,
    min: int | None = None,
    max: int | None = None,
    default: int | None = None,
    array: bool = False,
) -> str:
    """Create integer attribute."""
    try:
        result = await client.create_integer_attribute(
            database_id=database_id,
            collection_id=collection_id,
            key=key,
            required=required,
            min=min,
            max=max,
            default=default,
            array=array,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Integer attribute '{key}' created successfully",
                "attribute": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_boolean_attribute(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    key: str,
    required: bool = False,
    default: bool | None = None,
    array: bool = False,
) -> str:
    """Create boolean attribute."""
    try:
        result = await client.create_boolean_attribute(
            database_id=database_id,
            collection_id=collection_id,
            key=key,
            required=required,
            default=default,
            array=array,
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Boolean attribute '{key}' created successfully",
                "attribute": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_attribute(
    client: AppwriteClient, database_id: str, collection_id: str, key: str
) -> str:
    """Delete attribute."""
    try:
        await client.delete_attribute(database_id, collection_id, key)
        return json.dumps(
            {"success": True, "message": f"Attribute '{key}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_indexes(
    client: AppwriteClient, database_id: str, collection_id: str, queries: list[str] | None = None
) -> str:
    """List collection indexes."""
    try:
        result = await client.list_indexes(
            database_id=database_id, collection_id=collection_id, queries=queries
        )
        indexes = result.get("indexes", [])

        response = {
            "success": True,
            "database_id": database_id,
            "collection_id": collection_id,
            "total": result.get("total", len(indexes)),
            "indexes": indexes,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_index(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    key: str,
    type: str,
    attributes: list[str],
    orders: list[str] | None = None,
) -> str:
    """Create index."""
    try:
        result = await client.create_index(
            database_id=database_id,
            collection_id=collection_id,
            key=key,
            type=type,
            attributes=attributes,
            orders=orders,
        )
        return json.dumps(
            {"success": True, "message": f"Index '{key}' created successfully", "index": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_index(
    client: AppwriteClient, database_id: str, collection_id: str, key: str
) -> str:
    """Delete index."""
    try:
        await client.delete_index(database_id, collection_id, key)
        return json.dumps(
            {"success": True, "message": f"Index '{key}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
