"""Regression contracts for remaining generated-endpoint runtime seams."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.endpoints.middleware import EndpointAuditMiddleware

ROOT = Path(__file__).parents[1]


def _function_source(path: str, class_name: str, function_name: str) -> str:
    source = (ROOT / path).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == function_name
                ):
                    return ast.get_source_segment(source, child) or ""
    raise AssertionError(f"function not found: {path}:{class_name}.{function_name}")


def test_rate_limit_and_health_use_canonical_plugin_resolution() -> None:
    rate_source = _function_source("server.py", "RateLimitMiddleware", "on_call_tool")
    health_source = _function_source("server.py", "HealthMetricsMiddleware", "on_call_tool")

    assert "tool_name.split(" not in rate_source
    assert "tool_name.startswith(" not in rate_source
    assert "tool_name.split(" not in health_source
    assert "tool_name.startswith(" not in health_source


class _AuditRecorder:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def log(self, **kwargs):
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_endpoint_audit_logs_exception_type_without_exception_text() -> None:
    middleware = EndpointAuditMiddleware.__new__(EndpointAuditMiddleware)
    middleware.config = SimpleNamespace(path="/project/test/mcp")
    recorder = _AuditRecorder()
    middleware.audit_logger = recorder
    context = SimpleNamespace(message=SimpleNamespace(name="wordpress_list_posts"))

    async def failing_call(_context):
        raise RuntimeError("secret API response")

    with pytest.raises(RuntimeError, match="secret API response"):
        await middleware.on_call_tool(context, failing_call)

    details = recorder.calls[0]["details"]
    assert details["error_type"] == "RuntimeError"
    assert "error" not in details
    assert "secret API response" not in str(details)


def test_endpoint_audit_source_does_not_log_raw_exception_text() -> None:
    source = _function_source(
        "core/endpoints/middleware.py", "EndpointAuditMiddleware", "on_call_tool"
    )

    assert '"error": str(e)' not in source
    assert "error_type" in source
