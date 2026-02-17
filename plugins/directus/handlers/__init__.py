"""
Directus Plugin Handlers

Each handler module provides:
1. Tool specifications (get_tool_specifications)
2. Handler functions for each tool

Phase J.1: items (12) + collections (14) = 26 tools
Phase J.2: files (12) + users (10) = 22 tools
Phase J.3: access (12) + automation (12) = 24 tools
Phase J.4: content (10) + dashboards (8) + system (10) = 28 tools

Total: 100 tools
"""

from plugins.directus.handlers import (
    access,
    automation,
    collections,
    content,
    dashboards,
    files,
    items,
    system,
    users,
)

__all__ = [
    "items",
    "collections",
    "files",
    "users",
    "access",
    "automation",
    "content",
    "dashboards",
    "system",
]
