"""Static guards against name-derived authorization in primary paths."""

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _function_source(path: str, function_name: str) -> str:
    tree = ast.parse((ROOT / path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_source_segment((ROOT / path).read_text(), node) or ""
    raise AssertionError(f"function not found: {path}:{function_name}")


def test_primary_server_auth_does_not_call_scope_name_heuristic():
    source = _function_source("server.py", "on_call_tool")

    assert "determine_required_scope(" not in source


def test_scope_name_heuristic_is_removed_from_server():
    source = (ROOT / "server.py").read_text()

    assert "def determine_required_scope" not in source
    assert "from core.tool_authorization import" in source
    assert "resolve_required_scope" in source


def test_primary_server_auth_imports_canonical_identifier_parser():
    source = (ROOT / "server.py").read_text()

    assert "core.project_identifiers" in source


def test_endpoint_middleware_does_not_parse_project_with_first_underscore():
    source = (ROOT / "core/endpoints/middleware.py").read_text()

    assert 'project_id.split("_")[0]' not in source
