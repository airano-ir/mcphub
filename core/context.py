"""
Request Context Storage

Stores request-level information using contextvars for thread-safe access
across async operations.
"""

from contextvars import ContextVar
from typing import Any

# Context variable for storing API key info during request processing
# This allows unified handlers to check project access permissions
_api_key_context: ContextVar[dict[str, Any] | None] = ContextVar("api_key_context", default=None)


def set_api_key_context(key_id: str, project_id: str, scope: str, is_global: bool) -> None:
    """
    Store API key information in request context.

    Args:
        key_id: API key identifier
        project_id: Project the key belongs to ('*' for global)
        scope: Access scope (read/write/admin)
        is_global: Whether this is a global key
    """
    _api_key_context.set(
        {"key_id": key_id, "project_id": project_id, "scope": scope, "is_global": is_global}
    )


def get_api_key_context() -> dict[str, Any] | None:
    """
    Retrieve API key information from request context.

    Returns:
        Dict with key_id, project_id, scope, is_global or None
    """
    return _api_key_context.get()


def clear_api_key_context() -> None:
    """Clear API key context (for cleanup)."""
    _api_key_context.set(None)
