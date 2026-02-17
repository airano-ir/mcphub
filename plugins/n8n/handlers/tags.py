"""Tags Handler - manages n8n tags"""

import json
from typing import Any

from plugins.n8n.client import N8nClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        {
            "name": "list_tags",
            "method_name": "list_tags",
            "description": "List all tags used for workflow organization. All parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 250},
                    "cursor": {"type": "string", "description": "OPTIONAL: Pagination cursor."},
                },
            },
            "scope": "read",
        },
        {
            "name": "get_tag",
            "method_name": "get_tag",
            "description": "Get tag details by ID.",
            "schema": {
                "type": "object",
                "properties": {"tag_id": {"type": "string", "minLength": 1}},
                "required": ["tag_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_tag",
            "method_name": "create_tag",
            "description": "Create a new tag for workflow organization.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "description": "Tag name"}
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_tag",
            "method_name": "update_tag",
            "description": "Update tag name.",
            "schema": {
                "type": "object",
                "properties": {
                    "tag_id": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1, "description": "New tag name"},
                },
                "required": ["tag_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_tag",
            "method_name": "delete_tag",
            "description": "Delete a tag.",
            "schema": {
                "type": "object",
                "properties": {"tag_id": {"type": "string", "minLength": 1}},
                "required": ["tag_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_tags",
            "method_name": "delete_tags",
            "description": "Bulk delete multiple tags.",
            "schema": {
                "type": "object",
                "properties": {
                    "tag_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}
                },
                "required": ["tag_ids"],
            },
            "scope": "write",
        },
    ]

async def list_tags(client: N8nClient, limit: int = 100, cursor: str | None = None) -> str:
    try:
        response = await client.list_tags(limit=limit, cursor=cursor)
        tags = response.get("data", [])
        result = {
            "success": True,
            "count": len(tags),
            "tags": [{"id": t.get("id"), "name": t.get("name")} for t in tags],
            "next_cursor": response.get("nextCursor"),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_tag(client: N8nClient, tag_id: str) -> str:
    try:
        tag = await client.get_tag(tag_id)
        return json.dumps(
            {"success": True, "tag": {"id": tag.get("id"), "name": tag.get("name")}}, indent=2
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_tag(client: N8nClient, name: str) -> str:
    try:
        tag = await client.create_tag(name)
        return json.dumps(
            {
                "success": True,
                "message": f"Tag '{name}' created",
                "tag": {"id": tag.get("id"), "name": tag.get("name")},
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_tag(client: N8nClient, tag_id: str, name: str) -> str:
    try:
        tag = await client.update_tag(tag_id, name)
        return json.dumps(
            {
                "success": True,
                "message": f"Tag updated to '{name}'",
                "tag": {"id": tag.get("id"), "name": tag.get("name")},
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_tag(client: N8nClient, tag_id: str) -> str:
    try:
        await client.delete_tag(tag_id)
        return json.dumps({"success": True, "message": f"Tag {tag_id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_tags(client: N8nClient, tag_ids: list[str]) -> str:
    try:
        deleted, failed = [], []
        for tid in tag_ids:
            try:
                await client.delete_tag(tid)
                deleted.append(tid)
            except Exception as e:
                failed.append({"id": tid, "error": str(e)})
        return json.dumps(
            {"success": len(failed) == 0, "deleted": deleted, "failed": failed if failed else None},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
