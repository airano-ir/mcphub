"""
Storage Handler - manages Appwrite storage buckets and files

Phase I.3: 14 tools
- Buckets: 5 (list, get, create, update, delete)
- Files: 9 (list, get, create, update, delete, download, preview, view, get_url)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (14 tools)"""
    return [
        # =====================
        # BUCKETS (5)
        # =====================
        {
            "name": "list_buckets",
            "method_name": "list_buckets",
            "description": "List all storage buckets.",
            "schema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter buckets",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_bucket",
            "method_name": "get_bucket",
            "description": "Get bucket details by ID.",
            "schema": {
                "type": "object",
                "properties": {"bucket_id": {"type": "string", "description": "Bucket ID"}},
                "required": ["bucket_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_bucket",
            "method_name": "create_bucket",
            "description": "Create a new storage bucket.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {
                        "type": "string",
                        "description": "Unique bucket ID. Use 'unique()' for auto-generation",
                    },
                    "name": {"type": "string", "description": "Bucket name"},
                    "permissions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Bucket permissions",
                    },
                    "file_security": {
                        "type": "boolean",
                        "description": "Enable file-level security",
                        "default": True,
                    },
                    "enabled": {"type": "boolean", "description": "Enable bucket", "default": True},
                    "maximum_file_size": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum file size in bytes",
                    },
                    "allowed_file_extensions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Allowed file extensions (e.g., ['jpg', 'png', 'pdf'])",
                    },
                    "compression": {
                        "type": "string",
                        "enum": ["none", "gzip", "zstd"],
                        "description": "Compression algorithm",
                        "default": "none",
                    },
                    "encryption": {
                        "type": "boolean",
                        "description": "Enable encryption",
                        "default": True,
                    },
                    "antivirus": {
                        "type": "boolean",
                        "description": "Enable antivirus scanning",
                        "default": True,
                    },
                },
                "required": ["bucket_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "update_bucket",
            "method_name": "update_bucket",
            "description": "Update bucket settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "name": {"type": "string", "description": "Bucket name"},
                    "permissions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "New permissions",
                    },
                    "enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable/disable bucket",
                    },
                    "maximum_file_size": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum file size in bytes",
                    },
                    "allowed_file_extensions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Allowed extensions",
                    },
                },
                "required": ["bucket_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_bucket",
            "method_name": "delete_bucket",
            "description": "Delete a storage bucket. All files in the bucket will be deleted.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID to delete"}
                },
                "required": ["bucket_id"],
            },
            "scope": "admin",
        },
        # =====================
        # FILES (9)
        # =====================
        {
            "name": "list_files",
            "method_name": "list_files",
            "description": "List files in a bucket.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter files by name",
                    },
                },
                "required": ["bucket_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_file",
            "method_name": "get_file",
            "description": "Get file metadata (not content).",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "file_id": {"type": "string", "description": "File ID"},
                },
                "required": ["bucket_id", "file_id"],
            },
            "scope": "read",
        },
        {
            "name": "delete_file",
            "method_name": "delete_file",
            "description": "Delete a file from storage.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "file_id": {"type": "string", "description": "File ID to delete"},
                },
                "required": ["bucket_id", "file_id"],
            },
            "scope": "write",
        },
        {
            "name": "download_file",
            "method_name": "download_file",
            "description": "Download file content. Returns base64 encoded data.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "file_id": {"type": "string", "description": "File ID"},
                },
                "required": ["bucket_id", "file_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_file_preview",
            "method_name": "get_file_preview",
            "description": "Get image preview with transformations (resize, crop, etc.). Only works for image files.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "file_id": {"type": "string", "description": "File ID"},
                    "width": {
                        "anyOf": [
                            {"type": "integer", "minimum": 0, "maximum": 4000},
                            {"type": "null"},
                        ],
                        "description": "Width in pixels (0-4000)",
                    },
                    "height": {
                        "anyOf": [
                            {"type": "integer", "minimum": 0, "maximum": 4000},
                            {"type": "null"},
                        ],
                        "description": "Height in pixels (0-4000)",
                    },
                    "gravity": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": [
                                    "center",
                                    "top",
                                    "top-left",
                                    "top-right",
                                    "left",
                                    "right",
                                    "bottom",
                                    "bottom-left",
                                    "bottom-right",
                                ],
                            },
                            {"type": "null"},
                        ],
                        "description": "Crop gravity",
                    },
                    "quality": {
                        "anyOf": [
                            {"type": "integer", "minimum": 0, "maximum": 100},
                            {"type": "null"},
                        ],
                        "description": "Image quality (0-100)",
                    },
                    "border_width": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Border width in pixels",
                    },
                    "border_color": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Border color (hex without #)",
                    },
                    "border_radius": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Border radius for rounded corners",
                    },
                    "rotation": {
                        "anyOf": [
                            {"type": "integer", "minimum": 0, "maximum": 360},
                            {"type": "null"},
                        ],
                        "description": "Rotation angle (0-360)",
                    },
                    "background": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Background color (hex without #)",
                    },
                    "output": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": ["jpeg", "jpg", "png", "gif", "webp", "avif"],
                            },
                            {"type": "null"},
                        ],
                        "description": "Output format",
                    },
                },
                "required": ["bucket_id", "file_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_file_view",
            "method_name": "get_file_view",
            "description": "Get file content for viewing in browser. Returns base64 encoded data.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "file_id": {"type": "string", "description": "File ID"},
                },
                "required": ["bucket_id", "file_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_file_url",
            "method_name": "get_file_url",
            "description": "Get the public URL for a file (if bucket is public).",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "file_id": {"type": "string", "description": "File ID"},
                    "url_type": {
                        "type": "string",
                        "enum": ["view", "download", "preview"],
                        "description": "Type of URL to generate",
                        "default": "view",
                    },
                },
                "required": ["bucket_id", "file_id"],
            },
            "scope": "read",
        },
        {
            "name": "bulk_delete_files",
            "method_name": "bulk_delete_files",
            "description": "Delete multiple files from a bucket.",
            "schema": {
                "type": "object",
                "properties": {
                    "bucket_id": {"type": "string", "description": "Bucket ID"},
                    "file_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of file IDs to delete",
                    },
                },
                "required": ["bucket_id", "file_ids"],
            },
            "scope": "write",
        },
        {
            "name": "get_bucket_stats",
            "method_name": "get_bucket_stats",
            "description": "Get storage statistics for a bucket (file count and total size).",
            "schema": {
                "type": "object",
                "properties": {"bucket_id": {"type": "string", "description": "Bucket ID"}},
                "required": ["bucket_id"],
            },
            "scope": "read",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_buckets(
    client: AppwriteClient, queries: list[str] | None = None, search: str | None = None
) -> str:
    """List all buckets."""
    try:
        result = await client.list_buckets(queries=queries, search=search)
        buckets = result.get("buckets", [])

        response = {"success": True, "total": result.get("total", len(buckets)), "buckets": buckets}
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_bucket(client: AppwriteClient, bucket_id: str) -> str:
    """Get bucket by ID."""
    try:
        result = await client.get_bucket(bucket_id)
        return json.dumps({"success": True, "bucket": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_bucket(
    client: AppwriteClient,
    bucket_id: str,
    name: str,
    permissions: list[str] | None = None,
    file_security: bool = True,
    enabled: bool = True,
    maximum_file_size: int | None = None,
    allowed_file_extensions: list[str] | None = None,
    compression: str = "none",
    encryption: bool = True,
    antivirus: bool = True,
) -> str:
    """Create a new bucket."""
    try:
        result = await client.create_bucket(
            bucket_id=bucket_id,
            name=name,
            permissions=permissions,
            file_security=file_security,
            enabled=enabled,
            maximum_file_size=maximum_file_size,
            allowed_file_extensions=allowed_file_extensions,
            compression=compression,
            encryption=encryption,
            antivirus=antivirus,
        )
        return json.dumps(
            {"success": True, "message": f"Bucket '{name}' created successfully", "bucket": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_bucket(
    client: AppwriteClient,
    bucket_id: str,
    name: str,
    permissions: list[str] | None = None,
    enabled: bool | None = None,
    maximum_file_size: int | None = None,
    allowed_file_extensions: list[str] | None = None,
) -> str:
    """Update bucket."""
    try:
        result = await client.update_bucket(
            bucket_id=bucket_id,
            name=name,
            permissions=permissions,
            enabled=enabled,
            maximum_file_size=maximum_file_size,
            allowed_file_extensions=allowed_file_extensions,
        )
        return json.dumps(
            {"success": True, "message": "Bucket updated successfully", "bucket": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_bucket(client: AppwriteClient, bucket_id: str) -> str:
    """Delete bucket."""
    try:
        await client.delete_bucket(bucket_id)
        return json.dumps(
            {"success": True, "message": f"Bucket '{bucket_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_files(
    client: AppwriteClient,
    bucket_id: str,
    queries: list[str] | None = None,
    search: str | None = None,
) -> str:
    """List files in bucket."""
    try:
        result = await client.list_files(bucket_id=bucket_id, queries=queries, search=search)
        files = result.get("files", [])

        response = {
            "success": True,
            "bucket_id": bucket_id,
            "total": result.get("total", len(files)),
            "files": files,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_file(client: AppwriteClient, bucket_id: str, file_id: str) -> str:
    """Get file metadata."""
    try:
        result = await client.get_file(bucket_id, file_id)
        return json.dumps({"success": True, "file": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_file(client: AppwriteClient, bucket_id: str, file_id: str) -> str:
    """Delete file."""
    try:
        await client.delete_file(bucket_id, file_id)
        return json.dumps(
            {"success": True, "message": f"File '{file_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def download_file(client: AppwriteClient, bucket_id: str, file_id: str) -> str:
    """Download file content."""
    try:
        result = await client.get_file_download(bucket_id, file_id)
        return json.dumps(
            {
                "success": True,
                "file_id": file_id,
                "content_type": result.get("content_type"),
                "size": result.get("size"),
                "data_base64": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_file_preview(
    client: AppwriteClient,
    bucket_id: str,
    file_id: str,
    width: int | None = None,
    height: int | None = None,
    gravity: str | None = None,
    quality: int | None = None,
    border_width: int | None = None,
    border_color: str | None = None,
    border_radius: int | None = None,
    rotation: int | None = None,
    background: str | None = None,
    output: str | None = None,
) -> str:
    """Get file preview with transformations."""
    try:
        result = await client.get_file_preview(
            bucket_id=bucket_id,
            file_id=file_id,
            width=width,
            height=height,
            gravity=gravity,
            quality=quality,
            border_width=border_width,
            border_color=border_color,
            border_radius=border_radius,
            rotation=rotation,
            background=background,
            output=output,
        )
        return json.dumps(
            {
                "success": True,
                "file_id": file_id,
                "transformations": {
                    "width": width,
                    "height": height,
                    "quality": quality,
                    "output": output,
                },
                "content_type": result.get("content_type"),
                "size": result.get("size"),
                "data_base64": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_file_view(client: AppwriteClient, bucket_id: str, file_id: str) -> str:
    """Get file for viewing."""
    try:
        result = await client.get_file_view(bucket_id, file_id)
        return json.dumps(
            {
                "success": True,
                "file_id": file_id,
                "content_type": result.get("content_type"),
                "size": result.get("size"),
                "data_base64": result.get("data"),
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_file_url(
    client: AppwriteClient, bucket_id: str, file_id: str, url_type: str = "view"
) -> str:
    """Get file URL."""
    try:
        base_url = client.base_url
        if url_type == "download":
            url = f"{base_url}/storage/buckets/{bucket_id}/files/{file_id}/download"
        elif url_type == "preview":
            url = f"{base_url}/storage/buckets/{bucket_id}/files/{file_id}/preview"
        else:
            url = f"{base_url}/storage/buckets/{bucket_id}/files/{file_id}/view"

        return json.dumps(
            {
                "success": True,
                "file_id": file_id,
                "url_type": url_type,
                "url": url,
                "note": "URL requires authentication unless bucket is public",
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def bulk_delete_files(client: AppwriteClient, bucket_id: str, file_ids: list[str]) -> str:
    """Delete multiple files."""
    try:
        results = []
        errors = []

        for file_id in file_ids:
            try:
                await client.delete_file(bucket_id, file_id)
                results.append({"id": file_id, "success": True})
            except Exception as e:
                errors.append({"file_id": file_id, "error": str(e)})

        response = {
            "success": len(errors) == 0,
            "deleted": len(results),
            "failed": len(errors),
            "results": results,
        }
        if errors:
            response["errors"] = errors

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_bucket_stats(client: AppwriteClient, bucket_id: str) -> str:
    """Get bucket statistics."""
    try:
        # Get files without query params to avoid syntax errors
        # Appwrite returns first 25 files by default
        result = await client.list_files(bucket_id=bucket_id)
        files = result.get("files", [])
        total = result.get("total", len(files))

        total_size = sum(f.get("sizeOriginal", 0) for f in files)

        return json.dumps(
            {
                "success": True,
                "bucket_id": bucket_id,
                "stats": {
                    "file_count": total,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "sample_count": len(files),
                },
                "note": (
                    f"Size calculated from {len(files)} sampled files"
                    if total > len(files)
                    else None
                ),
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
