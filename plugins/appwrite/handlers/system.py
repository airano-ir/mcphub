"""
System Handler - manages Appwrite health checks and system utilities

Phase I.1: 8 tools
- Health: 6 (health_check, health_db, health_cache, health_storage, health_queue, health_time)
- Avatars: 2 (get_avatar_initials, get_qr_code)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (8 tools)"""
    return [
        # =====================
        # HEALTH (6)
        # =====================
        {
            "name": "health_check",
            "method_name": "health_check",
            "description": "Comprehensive health check of all Appwrite services. Returns status of database, cache, storage, and other services.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "health_db",
            "method_name": "health_db",
            "description": "Check database health status. Returns ping time and connection status.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "health_cache",
            "method_name": "health_cache",
            "description": "Check cache (Redis) health status.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "health_storage",
            "method_name": "health_storage",
            "description": "Check storage health status. Verifies local and S3 storage availability.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "health_queue",
            "method_name": "health_queue",
            "description": "Check queue health status. Returns queue sizes and processing status.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        {
            "name": "health_time",
            "method_name": "health_time",
            "description": "Check time synchronization status. Important for security and token validation.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "scope": "read",
        },
        # =====================
        # AVATARS (2)
        # =====================
        {
            "name": "get_avatar_initials",
            "method_name": "get_avatar_initials",
            "description": "Generate an avatar image from name initials. Returns base64 encoded image.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Full name to generate initials from",
                    },
                    "width": {
                        "type": "integer",
                        "description": "Image width in pixels",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 2000,
                    },
                    "height": {
                        "type": "integer",
                        "description": "Image height in pixels",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 2000,
                    },
                    "background": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Background color in hex (without #)",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_qr_code",
            "method_name": "get_qr_code",
            "description": "Generate a QR code image for any text or URL. Returns base64 encoded PNG.",
            "schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text or URL to encode in QR code"},
                    "size": {
                        "type": "integer",
                        "description": "QR code size in pixels (width = height)",
                        "default": 400,
                        "minimum": 100,
                        "maximum": 1000,
                    },
                    "margin": {
                        "type": "integer",
                        "description": "Margin around QR code in modules",
                        "default": 1,
                        "minimum": 0,
                        "maximum": 10,
                    },
                },
                "required": ["text"],
            },
            "scope": "read",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def health_check(client: AppwriteClient) -> str:
    """Comprehensive health check of all services."""
    try:
        result = await client.health_check()

        response = {
            "success": True,
            "healthy": result.get("healthy", False),
            "services": result.get("services", {}),
            "message": (
                "All services operational" if result.get("healthy") else "Some services have issues"
            ),
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "healthy": False, "error": str(e)}, indent=2)


async def health_db(client: AppwriteClient) -> str:
    """Check database health."""
    try:
        result = await client.health_db()

        response = {
            "success": True,
            "service": "database",
            "status": result.get("status", "unknown"),
            "ping": result.get("ping"),
            "message": (
                "Database is healthy" if result.get("status") == "pass" else "Database has issues"
            ),
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {"success": False, "service": "database", "status": "error", "error": str(e)}, indent=2
        )


async def health_cache(client: AppwriteClient) -> str:
    """Check cache health."""
    try:
        result = await client.health_cache()

        response = {
            "success": True,
            "service": "cache",
            "status": result.get("status", "unknown"),
            "ping": result.get("ping"),
            "message": "Cache is healthy" if result.get("status") == "pass" else "Cache has issues",
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {"success": False, "service": "cache", "status": "error", "error": str(e)}, indent=2
        )


async def health_storage(client: AppwriteClient) -> str:
    """Check storage health."""
    try:
        result = await client.health_storage_local()

        response = {
            "success": True,
            "service": "storage",
            "status": result.get("status", "unknown"),
            "ping": result.get("ping"),
            "message": (
                "Storage is healthy" if result.get("status") == "pass" else "Storage has issues"
            ),
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {"success": False, "service": "storage", "status": "error", "error": str(e)}, indent=2
        )


async def health_queue(client: AppwriteClient) -> str:
    """Check queue health."""
    try:
        result = await client.health_queue()

        response = {
            "success": True,
            "service": "queue",
            "status": result.get("status", "unknown"),
            "size": result.get("size"),
            "message": "Queue is healthy" if result.get("status") == "pass" else "Queue has issues",
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {"success": False, "service": "queue", "status": "error", "error": str(e)}, indent=2
        )


async def health_time(client: AppwriteClient) -> str:
    """Check time synchronization."""
    try:
        result = await client.health_time()

        response = {
            "success": True,
            "service": "time",
            "local_time": result.get("localTime"),
            "remote_time": result.get("remoteTime"),
            "diff": result.get("diff"),
            "message": (
                "Time is synchronized"
                if abs(result.get("diff", 999)) < 60
                else "Time drift detected"
            ),
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {"success": False, "service": "time", "status": "error", "error": str(e)}, indent=2
        )


async def get_avatar_initials(
    client: AppwriteClient,
    name: str | None = None,
    width: int = 100,
    height: int = 100,
    background: str | None = None,
) -> str:
    """Generate avatar from initials."""
    try:
        result = await client.get_avatar_initials(
            name=name, width=width, height=height, background=background
        )

        response = {
            "success": True,
            "message": f"Avatar generated for '{name or 'Anonymous'}'",
            "width": width,
            "height": height,
            "content_type": result.get("content_type", "image/png"),
            "size": result.get("size"),
            "data_base64": result.get("data"),
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_qr_code(client: AppwriteClient, text: str, size: int = 400, margin: int = 1) -> str:
    """Generate QR code."""
    try:
        result = await client.get_qr_code(text=text, size=size, margin=margin)

        response = {
            "success": True,
            "message": "QR code generated successfully",
            "text": text,
            "size": size,
            "content_type": result.get("content_type", "image/png"),
            "data_size": result.get("size"),
            "data_base64": result.get("data"),
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
