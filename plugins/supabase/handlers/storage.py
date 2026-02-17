"""Storage Handler - manages Supabase Storage (buckets and files)"""

import base64
import json
from typing import Any

from plugins.supabase.client import SupabaseClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (12 tools)"""
    return [
        {
            "name": "list_buckets",
            "method_name": "list_buckets",
            "description": "List all storage buckets. Returns bucket names, public/private status, and settings.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_bucket",
            "method_name": "get_bucket",
            "description": "Get detailed information about a specific bucket including settings and limits.",
            "schema": {
                "type": "object",
                "properties": {"bucket_id": {"type": "string", "description": "Bucket name/ID"}},
                "required": ["bucket_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_bucket",
            "method_name": "create_bucket",
            "description": "Create a new storage bucket. Can be public (accessible without auth) or private.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Bucket name (lowercase, no spaces)",
                        "pattern": "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Make bucket publicly accessible",
                        "default": False,
                    },
                    "file_size_limit": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Max file size in bytes (e.g., 52428800 for 50MB)",
                    },
                    "allowed_mime_types": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Allowed MIME types (e.g., ['image/png', 'image/jpeg'])",
                    },
                },
                "required": ["name"],
            },
            "scope": "admin",
        },
        {
            "name": "update_bucket",
            "method_name": "update_bucket",
            "description": "Update bucket settings like public access, file size limit, or allowed MIME types.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket name/ID"},
                    "public": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Set public access",
                    },
                    "file_size_limit": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Max file size in bytes",
                    },
                    "allowed_mime_types": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Allowed MIME types",
                    },
                },
                "required": ["bucket_id"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_bucket",
            "method_name": "delete_bucket",
            "description": "Delete a storage bucket. Bucket must be empty first (use empty_bucket).",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket name/ID to delete"}
                },
                "required": ["bucket_id"],
            },
            "scope": "admin",
        },
        {
            "name": "empty_bucket",
            "method_name": "empty_bucket",
            "description": "Delete all files in a bucket. Use before delete_bucket.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket name/ID to empty"}
                },
                "required": ["bucket_id"],
            },
            "scope": "admin",
        },
        {
            "name": "list_files",
            "method_name": "list_files",
            "description": "List files in a bucket or folder path. Returns file names, sizes, and metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Bucket name"},
                    "path": {
                        "type": "string",
                        "description": "Folder path prefix (empty for root)",
                        "default": "",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max files to return",
                        "default": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "default": 0,
                    },
                },
                "required": ["bucket"],
            },
            "scope": "read",
        },
        {
            "name": "upload_file",
            "method_name": "upload_file",
            "description": "Upload a file to storage. Content should be base64 encoded.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Bucket name"},
                    "path": {
                        "type": "string",
                        "description": "File path including filename (e.g., 'users/123/avatar.png')",
                    },
                    "content_base64": {
                        "type": "string",
                        "description": "File content encoded in base64",
                    },
                    "content_type": {
                        "type": "string",
                        "description": "MIME type (e.g., 'image/png', 'application/pdf')",
                        "default": "application/octet-stream",
                    },
                    "upsert": {
                        "type": "boolean",
                        "description": "Overwrite if file exists",
                        "default": False,
                    },
                },
                "required": ["bucket", "path", "content_base64"],
            },
            "scope": "write",
        },
        {
            "name": "download_file",
            "method_name": "download_file",
            "description": "Download a file from storage. Returns base64 encoded content.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Bucket name"},
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["bucket", "path"],
            },
            "scope": "read",
        },
        {
            "name": "delete_files",
            "method_name": "delete_files",
            "description": "Delete one or more files from a bucket.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Bucket name"},
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to delete",
                    },
                },
                "required": ["bucket", "paths"],
            },
            "scope": "write",
        },
        {
            "name": "move_file",
            "method_name": "move_file",
            "description": "Move or rename a file within the same bucket.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Bucket name"},
                    "from_path": {"type": "string", "description": "Current file path"},
                    "to_path": {"type": "string", "description": "New file path"},
                },
                "required": ["bucket", "from_path", "to_path"],
            },
            "scope": "write",
        },
        {
            "name": "get_public_url",
            "method_name": "get_public_url",
            "description": "Get the public URL for a file. Only works for files in public buckets.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "Bucket name (must be public)"},
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["bucket", "path"],
            },
            "scope": "read",
        },
    ]

# =====================
# Storage Operations (12 tools)
# =====================

async def list_buckets(client: SupabaseClient) -> str:
    """List all storage buckets"""
    try:
        result = await client.list_buckets()

        return json.dumps(
            {
                "success": True,
                "count": len(result) if isinstance(result, list) else 0,
                "buckets": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_bucket(client: SupabaseClient, bucket_id: str) -> str:
    """Get bucket details"""
    try:
        result = await client.get_bucket(bucket_id)

        return json.dumps({"success": True, "bucket": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def create_bucket(
    client: SupabaseClient,
    name: str,
    public: bool = False,
    file_size_limit: int | None = None,
    allowed_mime_types: list[str] | None = None,
) -> str:
    """Create a new bucket"""
    try:
        result = await client.create_bucket(
            name=name,
            public=public,
            file_size_limit=file_size_limit,
            allowed_mime_types=allowed_mime_types,
        )

        return json.dumps(
            {"success": True, "message": f"Bucket '{name}' created successfully", "bucket": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def update_bucket(
    client: SupabaseClient,
    bucket_id: str,
    public: bool | None = None,
    file_size_limit: int | None = None,
    allowed_mime_types: list[str] | None = None,
) -> str:
    """Update bucket settings"""
    try:
        result = await client.update_bucket(
            bucket_id=bucket_id,
            public=public,
            file_size_limit=file_size_limit,
            allowed_mime_types=allowed_mime_types,
        )

        return json.dumps(
            {
                "success": True,
                "message": f"Bucket '{bucket_id}' updated successfully",
                "bucket": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_bucket(client: SupabaseClient, bucket_id: str) -> str:
    """Delete a bucket"""
    try:
        await client.delete_bucket(bucket_id)

        return json.dumps(
            {"success": True, "message": f"Bucket '{bucket_id}' deleted successfully"},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def empty_bucket(client: SupabaseClient, bucket_id: str) -> str:
    """Empty a bucket (delete all files)"""
    try:
        await client.empty_bucket(bucket_id)

        return json.dumps(
            {"success": True, "message": f"Bucket '{bucket_id}' emptied successfully"},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def list_files(
    client: SupabaseClient, bucket: str, path: str = "", limit: int = 100, offset: int = 0
) -> str:
    """List files in bucket/path"""
    try:
        result = await client.list_files(bucket=bucket, path=path, limit=limit, offset=offset)

        return json.dumps(
            {
                "success": True,
                "bucket": bucket,
                "path": path,
                "count": len(result) if isinstance(result, list) else 0,
                "files": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def upload_file(
    client: SupabaseClient,
    bucket: str,
    path: str,
    content_base64: str,
    content_type: str = "application/octet-stream",
    upsert: bool = False,
) -> str:
    """Upload a file"""
    try:
        # Decode base64 content
        try:
            content = base64.b64decode(content_base64)
        except Exception:
            return json.dumps(
                {"success": False, "error": "Invalid base64 content"}, indent=2, ensure_ascii=False
            )

        result = await client.upload_file(
            bucket=bucket, path=path, content=content, content_type=content_type, upsert=upsert
        )

        # Build public URL if bucket is public
        public_url = await client.get_public_url(bucket, path)

        return json.dumps(
            {
                "success": True,
                "message": f"File uploaded to {bucket}/{path}",
                "size": len(content),
                "content_type": content_type,
                "public_url": public_url,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def download_file(client: SupabaseClient, bucket: str, path: str) -> str:
    """Download a file (returns base64)"""
    try:
        result = await client.download_file(bucket, path)

        if isinstance(result, dict) and "data" in result:
            return json.dumps(
                {
                    "success": True,
                    "bucket": bucket,
                    "path": path,
                    "content_type": result.get("content_type", "application/octet-stream"),
                    "size": result.get("size", 0),
                    "data_base64": result.get("data"),
                },
                indent=2,
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": True, "bucket": bucket, "path": path, "result": result},
                indent=2,
                ensure_ascii=False,
            )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def delete_files(client: SupabaseClient, bucket: str, paths: list[str]) -> str:
    """Delete files from bucket"""
    try:
        result = await client.delete_files(bucket, paths)

        return json.dumps(
            {
                "success": True,
                "message": f"Deleted {len(paths)} file(s) from {bucket}",
                "deleted_paths": paths,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def move_file(client: SupabaseClient, bucket: str, from_path: str, to_path: str) -> str:
    """Move/rename a file"""
    try:
        result = await client.move_file(bucket, from_path, to_path)

        return json.dumps(
            {
                "success": True,
                "message": f"File moved from {from_path} to {to_path}",
                "bucket": bucket,
                "from_path": from_path,
                "to_path": to_path,
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_public_url(client: SupabaseClient, bucket: str, path: str) -> str:
    """Get public URL for a file"""
    try:
        url = await client.get_public_url(bucket, path)

        return json.dumps(
            {
                "success": True,
                "bucket": bucket,
                "path": path,
                "public_url": url,
                "note": "URL only works if bucket is public",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
