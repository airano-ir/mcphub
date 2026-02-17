"""n8n Plugin Handlers"""

from plugins.n8n.handlers import (
    credentials,
    executions,
    projects,
    system,
    tags,
    users,
    variables,
    workflows,
)

__all__ = [
    "workflows",
    "executions",
    "credentials",
    "tags",
    "users",
    "projects",
    "variables",
    "system",
]
