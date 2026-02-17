"""
Items Handler - CRUD operations for any collection

Phase J.1: 12 tools
- list_items, get_item, create_item, create_items
- update_item, update_items, delete_item, delete_items
- search_items, aggregate_items, export_items, import_items
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
        {
            "name": "list_items",
            "method_name": "list_items",
            "description": "List items from any Directus collection with filtering, sorting, and pagination.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name (e.g., 'posts', 'products')",
                    },
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to return (e.g., ['id', 'title', 'author.*'])",
                    },
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"status": {"_eq": "published"}})',
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields (e.g., ['-date_created', 'title'])",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum items to return",
                        "default": 100,
                    },
                    "offset": {"type": "integer", "description": "Items to skip", "default": 0},
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Full-text search query",
                    },
                },
                "required": ["collection"],
            },
            "scope": "read",
        },
        {
            "name": "get_item",
            "method_name": "get_item",
            "description": "Get a single item by ID from any collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "id": {"type": "string", "description": "Item ID"},
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to return",
                    },
                },
                "required": ["collection", "id"],
            },
            "scope": "read",
        },
        {
            "name": "create_item",
            "method_name": "create_item",
            "description": "Create a new item in any collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "data": {"type": "object", "description": "Item data (field values)"},
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to return in response",
                    },
                },
                "required": ["collection", "data"],
            },
            "scope": "write",
        },
        {
            "name": "create_items",
            "method_name": "create_items",
            "description": "Create multiple items in a collection at once.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of item data objects",
                    },
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to return in response",
                    },
                },
                "required": ["collection", "data"],
            },
            "scope": "write",
        },
        {
            "name": "update_item",
            "method_name": "update_item",
            "description": "Update an existing item by ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "id": {"type": "string", "description": "Item ID"},
                    "data": {"type": "object", "description": "Fields to update"},
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to return in response",
                    },
                },
                "required": ["collection", "id", "data"],
            },
            "scope": "write",
        },
        {
            "name": "update_items",
            "method_name": "update_items",
            "description": "Update multiple items by their IDs.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of item IDs to update",
                    },
                    "data": {
                        "type": "object",
                        "description": "Fields to update (applied to all items)",
                    },
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to return in response",
                    },
                },
                "required": ["collection", "keys", "data"],
            },
            "scope": "write",
        },
        {
            "name": "delete_item",
            "method_name": "delete_item",
            "description": "Delete an item by ID. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "id": {"type": "string", "description": "Item ID to delete"},
                },
                "required": ["collection", "id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_items",
            "method_name": "delete_items",
            "description": "Delete multiple items by their IDs. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of item IDs to delete",
                    },
                },
                "required": ["collection", "keys"],
            },
            "scope": "admin",
        },
        {
            "name": "search_items",
            "method_name": "search_items",
            "description": "Full-text search across items in a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "query": {"type": "string", "description": "Search query"},
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to return",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum items to return",
                        "default": 25,
                    },
                },
                "required": ["collection", "query"],
            },
            "scope": "read",
        },
        {
            "name": "aggregate_items",
            "method_name": "aggregate_items",
            "description": "Perform aggregate operations (count, sum, avg, min, max) on items.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "aggregate": {
                        "type": "object",
                        "description": 'Aggregate functions (e.g., {"count": "*", "sum": "price"})',
                    },
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Filter to apply before aggregation",
                    },
                    "groupBy": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to group by",
                    },
                },
                "required": ["collection", "aggregate"],
            },
            "scope": "read",
        },
        {
            "name": "export_items",
            "method_name": "export_items",
            "description": "Export items from a collection with filtering options.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "fields": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Fields to export",
                    },
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Filter to apply",
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum items to export",
                        "default": 1000,
                    },
                },
                "required": ["collection"],
            },
            "scope": "read",
        },
        {
            "name": "import_items",
            "method_name": "import_items",
            "description": "Import multiple items into a collection.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of items to import",
                    },
                },
                "required": ["collection", "data"],
            },
            "scope": "write",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def list_items(
    client: DirectusClient,
    collection: str,
    fields: list[str] | None = None,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
) -> str:
    """List items from a collection."""
    try:
        # Parse JSON string parameters
        parsed_fields = _parse_json_param(fields, "fields")
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_items(
            collection=collection,
            fields=parsed_fields,
            filter=parsed_filter,
            sort=parsed_sort,
            limit=limit,
            offset=offset,
            search=search,
        )
        items = result.get("data", [])
        return json.dumps(
            {"success": True, "collection": collection, "total": len(items), "items": items},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_item(
    client: DirectusClient, collection: str, id: str, fields: list[str] | None = None
) -> str:
    """Get item by ID."""
    try:
        # Parse JSON string parameter
        parsed_fields = _parse_json_param(fields, "fields")
        result = await client.get_item(collection, id, fields=parsed_fields)
        return json.dumps(
            {"success": True, "item": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_item(
    client: DirectusClient, collection: str, data: dict[str, Any], fields: list[str] | None = None
) -> str:
    """Create a new item."""
    try:
        # Parse JSON string parameters
        parsed_data = _parse_json_param(data, "data")
        parsed_fields = _parse_json_param(fields, "fields")
        result = await client.create_item(collection, parsed_data, fields=parsed_fields)
        return json.dumps(
            {
                "success": True,
                "message": f"Item created in {collection}",
                "item": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_items(
    client: DirectusClient,
    collection: str,
    data: list[dict[str, Any]],
    fields: list[str] | None = None,
) -> str:
    """Create multiple items."""
    try:
        # Parse JSON string parameters
        parsed_data = _parse_json_param(data, "data")
        parsed_fields = _parse_json_param(fields, "fields")
        result = await client.create_items(collection, parsed_data, fields=parsed_fields)
        items = result.get("data", [])
        return json.dumps(
            {
                "success": True,
                "message": f"Created {len(items)} items in {collection}",
                "items": items,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_item(
    client: DirectusClient,
    collection: str,
    id: str,
    data: dict[str, Any],
    fields: list[str] | None = None,
) -> str:
    """Update an item."""
    try:
        # Parse JSON string parameters
        parsed_data = _parse_json_param(data, "data")
        parsed_fields = _parse_json_param(fields, "fields")
        result = await client.update_item(collection, id, parsed_data, fields=parsed_fields)
        return json.dumps(
            {"success": True, "message": f"Item {id} updated", "item": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_items(
    client: DirectusClient,
    collection: str,
    keys: list[str],
    data: dict[str, Any],
    fields: list[str] | None = None,
) -> str:
    """Update multiple items."""
    try:
        # Parse JSON string parameters
        parsed_keys = _parse_json_param(keys, "keys")
        parsed_data = _parse_json_param(data, "data")
        parsed_fields = _parse_json_param(fields, "fields")
        result = await client.update_items(
            collection, parsed_keys, parsed_data, fields=parsed_fields
        )
        items = result.get("data", [])
        return json.dumps(
            {
                "success": True,
                "message": f"Updated {len(items)} items in {collection}",
                "items": items,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_item(client: DirectusClient, collection: str, id: str) -> str:
    """Delete an item."""
    try:
        await client.delete_item(collection, id)
        return json.dumps(
            {"success": True, "message": f"Item {id} deleted from {collection}"}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_items(client: DirectusClient, collection: str, keys: list[str]) -> str:
    """Delete multiple items."""
    try:
        # Parse JSON string parameter
        parsed_keys = _parse_json_param(keys, "keys")
        await client.delete_items(collection, parsed_keys)
        return json.dumps(
            {"success": True, "message": f"Deleted {len(keys)} items from {collection}"}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def search_items(
    client: DirectusClient,
    collection: str,
    query: str,
    fields: list[str] | None = None,
    limit: int = 25,
) -> str:
    """Full-text search items."""
    try:
        # Parse JSON string parameter
        parsed_fields = _parse_json_param(fields, "fields")
        result = await client.list_items(
            collection=collection, fields=parsed_fields, search=query, limit=limit
        )
        items = result.get("data", [])
        return json.dumps(
            {"success": True, "query": query, "total": len(items), "items": items},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def aggregate_items(
    client: DirectusClient,
    collection: str,
    aggregate: dict[str, Any],
    filter: dict | None = None,
    groupBy: list[str] | None = None,
) -> str:
    """Aggregate items."""
    try:
        # Parse JSON string parameters
        parsed_aggregate = _parse_json_param(aggregate, "aggregate")
        parsed_filter = _parse_json_param(filter, "filter")
        _parse_json_param(groupBy, "groupBy")

        result = await client.list_items(
            collection=collection, filter=parsed_filter, aggregate=parsed_aggregate
        )
        return json.dumps(
            {"success": True, "collection": collection, "result": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def export_items(
    client: DirectusClient,
    collection: str,
    fields: list[str] | None = None,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 1000,
) -> str:
    """Export items from a collection."""
    try:
        # Parse JSON string parameters
        parsed_fields = _parse_json_param(fields, "fields")
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_items(
            collection=collection,
            fields=parsed_fields,
            filter=parsed_filter,
            sort=parsed_sort,
            limit=limit,
        )
        items = result.get("data", [])
        return json.dumps(
            {
                "success": True,
                "collection": collection,
                "exported_count": len(items),
                "data": items,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def import_items(client: DirectusClient, collection: str, data: list[dict[str, Any]]) -> str:
    """Import items into a collection."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.create_items(collection, parsed_data)
        items = result.get("data", [])
        return json.dumps(
            {
                "success": True,
                "message": f"Imported {len(items)} items into {collection}",
                "imported_count": len(items),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
