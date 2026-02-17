"""Appwrite Plugin Handlers"""

from plugins.appwrite.handlers import (
    databases,
    documents,
    # Phase I.4
    functions,
    messaging,
    # Phase I.3
    storage,
    system,
    teams,
    # Phase I.2
    users,
)

__all__ = [
    "databases",
    "documents",
    "system",
    # Phase I.2
    "users",
    "teams",
    # Phase I.3
    "storage",
    # Phase I.4
    "functions",
    "messaging",
]
