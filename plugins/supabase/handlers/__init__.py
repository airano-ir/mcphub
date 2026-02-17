"""Supabase Plugin Handlers"""

from plugins.supabase.handlers import (
    admin,
    # Phase G.2
    auth,
    database,
    # Phase G.3
    functions,
    storage,
    system,
)

__all__ = [
    "database",
    "system",
    # Phase G.2
    "auth",
    "storage",
    # Phase G.3
    "functions",
    "admin",
]
