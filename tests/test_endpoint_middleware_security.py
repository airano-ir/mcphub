"""Security contracts for the legacy endpoint middleware stack."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

from core.endpoints.middleware import EndpointAuthMiddleware


@pytest.mark.asyncio
async def test_endpoint_auth_does_not_expose_internal_exception_text(monkeypatch) -> None:
    """Internal failures must not be reflected in client errors or log text."""
    middleware = EndpointAuthMiddleware.__new__(EndpointAuthMiddleware)
    secret = "upstream password=super-secret"
    logged: list[str] = []

    async def fail_auth(_context):
        raise RuntimeError(secret)

    middleware._authenticate = fail_auth
    middleware._log_error = lambda _tool, error, _start: logged.append(error)
    context = SimpleNamespace(message=SimpleNamespace(name="wordpress_list_posts"))

    with pytest.raises(ToolError) as raised:
        await middleware.on_call_tool(context, AsyncMock())

    assert secret not in str(raised.value)
    assert logged == ["RuntimeError"]


@pytest.mark.asyncio
async def test_endpoint_auth_fails_closed_when_headers_are_unavailable(monkeypatch) -> None:
    """A header lookup failure must not silently downgrade the request to anonymous."""
    middleware = EndpointAuthMiddleware.__new__(EndpointAuthMiddleware)
    middleware.config = SimpleNamespace(require_master_key=False)

    def unavailable_headers():
        raise RuntimeError("header backend unavailable")

    monkeypatch.setattr("core.endpoints.middleware.get_http_headers", unavailable_headers)

    with pytest.raises(ToolError, match="Authentication service unavailable"):
        await middleware._authenticate(SimpleNamespace())
