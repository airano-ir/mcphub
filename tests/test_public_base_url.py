"""Tests for ``resolve_public_base_url`` (2026-05-01).

Behaviour matrix that the helper has to cover so the dashboard's
``mcp_url`` rendering never falls back to a host-less path again — the
mcp-test app reproduced this by setting ``PUBLIC_URL=''`` (empty string,
not unset) in its env vars, which silently bypassed the previous
``os.environ.get("PUBLIC_URL", "http://localhost:8000")`` default.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.dashboard.routes import resolve_public_base_url


def _request(headers: dict[str, str], scheme: str = "http", netloc: str = "localhost:8000"):
    """Build the smallest Request stub the helper needs."""
    req = MagicMock()
    req.headers = headers
    req.url = MagicMock()
    req.url.scheme = scheme
    req.url.netloc = netloc
    return req


def test_env_var_wins_when_set_and_non_empty(monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://mcp.example.com")
    req = _request({"host": "internal.fly.dev"}, scheme="http")
    assert resolve_public_base_url(req) == "https://mcp.example.com"


def test_env_var_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://mcp.example.com/")
    req = _request({})
    assert resolve_public_base_url(req) == "https://mcp.example.com"


def test_empty_env_var_falls_back_to_request(monkeypatch):
    """The mcp-test bug — ``PUBLIC_URL=''`` no longer produces a host-less URL."""
    monkeypatch.setenv("PUBLIC_URL", "")
    req = _request({"x-forwarded-proto": "https", "x-forwarded-host": "mcp-test.example.com"})
    assert resolve_public_base_url(req) == "https://mcp-test.example.com"


def test_whitespace_env_var_treated_as_unset(monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "   ")
    req = _request({"x-forwarded-proto": "https", "x-forwarded-host": "wp.example.org"})
    assert resolve_public_base_url(req) == "https://wp.example.org"


def test_unset_env_var_uses_forwarded_headers(monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    req = _request({"x-forwarded-proto": "https", "x-forwarded-host": "mcp.example.com"})
    assert resolve_public_base_url(req) == "https://mcp.example.com"


def test_falls_back_to_host_header_when_no_xfh(monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    req = _request({"host": "mcp.local"}, scheme="https")
    assert resolve_public_base_url(req) == "https://mcp.local"


def test_falls_back_to_request_url_when_no_headers(monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    req = _request({}, scheme="http", netloc="127.0.0.1:8001")
    assert resolve_public_base_url(req) == "http://127.0.0.1:8001"


def test_handles_csv_x_forwarded_proto(monkeypatch):
    """Some upstream proxies append the original scheme: ``https, http``."""
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    req = _request({"x-forwarded-proto": "https, http", "x-forwarded-host": "mcp.example.com"})
    assert resolve_public_base_url(req) == "https://mcp.example.com"


def test_handles_csv_x_forwarded_host(monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    req = _request(
        {"x-forwarded-proto": "https", "x-forwarded-host": "edge1.example.com, internal"}
    )
    assert resolve_public_base_url(req) == "https://edge1.example.com"


@pytest.mark.parametrize(
    "url",
    [
        "https://mcp.example.com",
        "https://mcp.example.com/",
        "https://mcp.example.com//",
    ],
)
def test_no_trailing_slash_in_output(monkeypatch, url):
    monkeypatch.setenv("PUBLIC_URL", url)
    req = _request({})
    assert resolve_public_base_url(req) == "https://mcp.example.com"
