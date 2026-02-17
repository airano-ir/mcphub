"""
Content Handler - Revisions, Versions, Comments

Phase J.4: 10 tools
- Revisions: list, get (2)
- Versions: list, get, create, update, delete, promote (6)
- Comments: list, create (2)
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
    """Return tool specifications for ToolGenerator (10 tools)"""
    return [
        # =====================
        # REVISIONS (2)
        # =====================
        {
            "name": "list_revisions",
            "method_name": "list_revisions",
            "description": "List revisions (history) of items.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"collection": {"_eq": "posts"}})',
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields (default: ['-activity'])",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum revisions to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_revision",
            "method_name": "get_revision",
            "description": "Get revision details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Revision ID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        # =====================
        # VERSIONS (6)
        # =====================
        {
            "name": "list_versions",
            "method_name": "list_versions",
            "description": "List content versions (drafts).",
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
                        "description": "Maximum versions to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_version",
            "method_name": "get_version",
            "description": "Get version details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Version UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "create_version",
            "method_name": "create_version",
            "description": "Create a new content version (draft).",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Version name"},
                    "collection": {"type": "string", "description": "Collection name"},
                    "item": {"type": "string", "description": "Item ID"},
                    "key": {"type": "string", "description": "Version key (unique identifier)"},
                },
                "required": ["name", "collection", "item", "key"],
            },
            "scope": "write",
        },
        {
            "name": "update_version",
            "method_name": "update_version",
            "description": "Update a version.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Version UUID"},
                    "data": {"type": "object", "description": "Fields to update (name, delta)"},
                },
                "required": ["id", "data"],
            },
            "scope": "write",
        },
        {
            "name": "delete_version",
            "method_name": "delete_version",
            "description": "Delete a version.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Version UUID to delete"}},
                "required": ["id"],
            },
            "scope": "write",
        },
        {
            "name": "promote_version",
            "method_name": "promote_version",
            "description": "Promote a version to main (apply changes to item).",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Version UUID to promote"},
                    "mainHash": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Expected main content hash (for conflict detection)",
                    },
                },
                "required": ["id"],
            },
            "scope": "write",
        },
        # =====================
        # COMMENTS (2)
        # =====================
        {
            "name": "list_comments",
            "method_name": "list_comments",
            "description": "List comments on items.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"collection": {"_eq": "posts"}})',
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum comments to return",
                        "default": 100,
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "create_comment",
            "method_name": "create_comment",
            "description": "Create a comment on an item.",
            "schema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "item": {"type": "string", "description": "Item ID"},
                    "comment": {"type": "string", "description": "Comment text"},
                },
                "required": ["collection", "item", "comment"],
            },
            "scope": "write",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_revisions(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
) -> str:
    """List revisions."""
    try:
        # Parse JSON string parameters
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_revisions(filter=parsed_filter, sort=parsed_sort, limit=limit)
        revisions = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(revisions), "revisions": revisions},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_revision(client: DirectusClient, id: str) -> str:
    """Get revision by ID."""
    try:
        result = await client.get_revision(id)
        return json.dumps(
            {"success": True, "revision": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_versions(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
) -> str:
    """List versions."""
    try:
        # Parse JSON string parameters
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_versions(filter=parsed_filter, sort=parsed_sort, limit=limit)
        versions = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(versions), "versions": versions},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_version(client: DirectusClient, id: str) -> str:
    """Get version by ID."""
    try:
        result = await client.get_version(id)
        return json.dumps(
            {"success": True, "version": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_version(
    client: DirectusClient, name: str, collection: str, item: str, key: str
) -> str:
    """Create a new version."""
    try:
        result = await client.create_version(name=name, collection=collection, item=item, key=key)
        return json.dumps(
            {
                "success": True,
                "message": f"Version '{name}' created",
                "version": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_version(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update version."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.update_version(id, parsed_data)
        return json.dumps(
            {"success": True, "message": "Version updated", "version": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_version(client: DirectusClient, id: str) -> str:
    """Delete a version."""
    try:
        await client.delete_version(id)
        return json.dumps({"success": True, "message": f"Version {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def promote_version(client: DirectusClient, id: str, mainHash: str | None = None) -> str:
    """Promote version to main."""
    try:
        result = await client.promote_version(id, mainHash)
        return json.dumps(
            {
                "success": True,
                "message": f"Version {id} promoted to main",
                "result": result.get("data") if result else None,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_comments(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
) -> str:
    """List comments."""
    try:
        # Parse JSON string parameters
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_comments(filter=parsed_filter, sort=parsed_sort, limit=limit)
        comments = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(comments), "comments": comments},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_comment(client: DirectusClient, collection: str, item: str, comment: str) -> str:
    """Create a comment."""
    try:
        result = await client.create_comment(collection, item, comment)
        return json.dumps(
            {"success": True, "message": "Comment created", "comment": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
