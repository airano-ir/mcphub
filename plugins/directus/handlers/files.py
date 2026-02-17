"""
Files & Folders Handler - Asset management

Phase J.2: 12 tools
- Files: list, get, update, delete, delete_files, import_url (6)
- Folders: list, get, create, update, delete (5)
- Note: File upload requires multipart form - import_url is the alternative
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
        # FILES (7)
        # =====================
        {
            "name": "list_files",
            "method_name": "list_files",
            "description": "List all files in Directus storage with filtering options.",
            "schema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Filter object (e.g., {"type": {"_contains": "image"}})',
                    },
                    "sort": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Sort fields (e.g., ['-uploaded_on'])",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum files to return",
                        "default": 100,
                    },
                    "offset": {"type": "integer", "description": "Files to skip", "default": 0},
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_file",
            "method_name": "get_file",
            "description": "Get file metadata by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "File UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "update_file",
            "method_name": "update_file",
            "description": "Update file metadata (title, description, tags, folder).",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "File UUID"},
                    "data": {
                        "type": "object",
                        "description": "Fields to update (title, description, tags, folder, etc.)",
                    },
                },
                "required": ["id", "data"],
            },
            "scope": "write",
        },
        {
            "name": "delete_file",
            "method_name": "delete_file",
            "description": "Delete a file. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "File UUID to delete"}},
                "required": ["id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_files",
            "method_name": "delete_files",
            "description": "Delete multiple files. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of file UUIDs to delete",
                    }
                },
                "required": ["ids"],
            },
            "scope": "admin",
        },
        {
            "name": "import_file_url",
            "method_name": "import_file_url",
            "description": "Import a file from a URL into Directus storage.",
            "schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL of the file to import"},
                    "data": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Additional file data (title, description, folder, etc.)",
                    },
                },
                "required": ["url"],
            },
            "scope": "write",
        },
        {
            "name": "get_file_url",
            "method_name": "get_file_url",
            "description": "Get the direct URL to access a file.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "File UUID"},
                    "download": {
                        "type": "boolean",
                        "description": "Whether to force download instead of display",
                        "default": False,
                    },
                },
                "required": ["id"],
            },
            "scope": "read",
        },
        # =====================
        # FOLDERS (5)
        # =====================
        {
            "name": "list_folders",
            "method_name": "list_folders",
            "description": "List all folders in Directus storage.",
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
                        "description": "Maximum folders to return",
                        "default": 100,
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_folder",
            "method_name": "get_folder",
            "description": "Get folder details by ID.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Folder UUID"}},
                "required": ["id"],
            },
            "scope": "read",
        },
        {
            "name": "create_folder",
            "method_name": "create_folder",
            "description": "Create a new folder.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Folder name"},
                    "parent": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Parent folder UUID (null for root)",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_folder",
            "method_name": "update_folder",
            "description": "Update folder name or parent.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Folder UUID"},
                    "data": {"type": "object", "description": "Fields to update (name, parent)"},
                },
                "required": ["id", "data"],
            },
            "scope": "write",
        },
        {
            "name": "delete_folder",
            "method_name": "delete_folder",
            "description": "Delete a folder. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Folder UUID to delete"}},
                "required": ["id"],
            },
            "scope": "admin",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def list_files(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
) -> str:
    """List files."""
    try:
        # Parse JSON string parameters
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_files(
            filter=parsed_filter, sort=parsed_sort, limit=limit, offset=offset, search=search
        )
        files = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(files), "files": files}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_file(client: DirectusClient, id: str) -> str:
    """Get file metadata."""
    try:
        result = await client.get_file(id)
        return json.dumps(
            {"success": True, "file": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_file(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update file metadata."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.update_file(id, parsed_data)
        return json.dumps(
            {"success": True, "message": "File updated", "file": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_file(client: DirectusClient, id: str) -> str:
    """Delete a file."""
    try:
        await client.delete_file(id)
        return json.dumps({"success": True, "message": f"File {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_files(client: DirectusClient, ids: list[str]) -> str:
    """Delete multiple files."""
    try:
        # Parse JSON string parameter
        parsed_ids = _parse_json_param(ids, "ids")
        await client.delete_files(parsed_ids)
        return json.dumps({"success": True, "message": f"Deleted {len(ids)} files"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def import_file_url(client: DirectusClient, url: str, data: dict | None = None) -> str:
    """Import file from URL."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.import_file_url(url, parsed_data)
        return json.dumps(
            {"success": True, "message": "File imported", "file": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_file_url(client: DirectusClient, id: str, download: bool = False) -> str:
    """Get file URL."""
    try:
        base_url = client.base_url
        url = f"{base_url}/assets/{id}"
        if download:
            url += "?download=true"
        return json.dumps({"success": True, "id": id, "url": url, "download": download}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_folders(
    client: DirectusClient,
    filter: dict | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
    search: str | None = None,
) -> str:
    """List folders."""
    try:
        # Parse JSON string parameters
        parsed_filter = _parse_json_param(filter, "filter")
        parsed_sort = _parse_json_param(sort, "sort")

        result = await client.list_folders(
            filter=parsed_filter, sort=parsed_sort, limit=limit, search=search
        )
        folders = result.get("data", [])
        return json.dumps(
            {"success": True, "total": len(folders), "folders": folders},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_folder(client: DirectusClient, id: str) -> str:
    """Get folder details."""
    try:
        result = await client.get_folder(id)
        return json.dumps(
            {"success": True, "folder": result.get("data")}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_folder(client: DirectusClient, name: str, parent: str | None = None) -> str:
    """Create a folder."""
    try:
        result = await client.create_folder(name, parent)
        return json.dumps(
            {"success": True, "message": f"Folder '{name}' created", "folder": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_folder(client: DirectusClient, id: str, data: dict[str, Any]) -> str:
    """Update folder."""
    try:
        # Parse JSON string parameter
        parsed_data = _parse_json_param(data, "data")
        result = await client.update_folder(id, parsed_data)
        return json.dumps(
            {"success": True, "message": "Folder updated", "folder": result.get("data")},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_folder(client: DirectusClient, id: str) -> str:
    """Delete a folder."""
    try:
        await client.delete_folder(id)
        return json.dumps({"success": True, "message": f"Folder {id} deleted"}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
