"""
WordPress Advanced Handlers

Modular handlers for WordPress advanced functionality.
Each handler is responsible for a specific domain of WordPress advanced operations.
"""

from plugins.wordpress_advanced.handlers.bulk import BulkHandler
from plugins.wordpress_advanced.handlers.bulk import get_tool_specifications as get_bulk_specs
from plugins.wordpress_advanced.handlers.database import DatabaseHandler
from plugins.wordpress_advanced.handlers.database import (
    get_tool_specifications as get_database_specs,
)
from plugins.wordpress_advanced.handlers.system import SystemHandler
from plugins.wordpress_advanced.handlers.system import get_tool_specifications as get_system_specs

__all__ = [
    # Handlers
    "DatabaseHandler",
    "BulkHandler",
    "SystemHandler",
    # Tool specifications
    "get_database_specs",
    "get_bulk_specs",
    "get_system_specs",
]
