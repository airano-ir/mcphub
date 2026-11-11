"""Phase 1 contracts for the primary generated FastMCP authorization path."""

from __future__ import annotations

import ast
from pathlib import Path

from core.tool_authorization import is_system_tool_name

ROOT = Path(__file__).parents[1]


def _function_source(function_name: str, class_name: str | None = None) -> str:
    source = (ROOT / "server.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if class_name and not isinstance(node, ast.ClassDef):
            continue
        if class_name and node.name != class_name:
            continue
        candidates = node.body if class_name else [node]
        for candidate in candidates:
            if (
                isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef))
                and candidate.name == function_name
            ):
                return ast.get_source_segment(source, candidate) or ""
    raise AssertionError(f"function not found: {class_name or '<module>'}:{function_name}")


def test_system_tool_classification_is_exact_and_namespace_normalized() -> None:
    assert is_system_tool_name("list_projects") is True
    assert is_system_tool_name("mcp__mcp-hub__list_projects") is True
    assert is_system_tool_name("evil_list_projects") is False
    assert is_system_tool_name("list_projects_suffix") is False


def test_primary_auth_has_no_unknown_or_suffix_fail_open() -> None:
    source = _function_source("on_call_tool", "UserAuthMiddleware")

    assert "any(tool_name.endswith(st) for st in SYSTEM_TOOLS)" not in source
    assert 'if tool_name == "unknown":\n                is_unified_tool = True' not in source
    assert 'raise ToolError(f"Authentication error: {str(e)}")' not in source
    assert 'raise ToolError("Authentication service unavailable")' in source


def test_primary_audit_does_not_forward_raw_call_data() -> None:
    source = _function_source("on_call_tool", "AuditLoggingMiddleware")

    assert "params=tool_args" not in source
    assert "result_summary=result_summary" not in source
    assert "error=error_msg" not in source
    assert "result_summary = result[:100]" not in source
