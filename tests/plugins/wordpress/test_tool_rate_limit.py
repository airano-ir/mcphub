"""F.5a.6.1 — Per-tool rate limit tests."""

from __future__ import annotations

import json

import pytest

from core.tool_rate_limiter import (
    PerToolRateLimiter,
    ToolRateLimitError,
    set_tool_rate_limiter,
)
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.ai_media import AIMediaHandler


@pytest.fixture(autouse=True)
def _fresh_limiter():
    set_tool_rate_limiter(PerToolRateLimiter())
    yield
    set_tool_rate_limiter(None)


def test_admin_exempt():
    limiter = PerToolRateLimiter({"tool_x": 2})
    for _ in range(10):
        limiter.check("tool_x", None)  # None = admin/env
        limiter.check("tool_x", "")


def test_per_user_limit_enforced():
    limiter = PerToolRateLimiter({"tool_x": 3})
    for _ in range(3):
        limiter.check("tool_x", "alice")
    with pytest.raises(ToolRateLimitError) as exc:
        limiter.check("tool_x", "alice")
    assert exc.value.tool_name == "tool_x"
    assert exc.value.limit_per_hour == 3
    d = exc.value.to_dict()
    assert d["error_code"] == "TOOL_RATE_LIMITED"
    assert d["details"]["tool"] == "tool_x"


def test_different_users_isolated():
    limiter = PerToolRateLimiter({"tool_x": 2})
    limiter.check("tool_x", "alice")
    limiter.check("tool_x", "alice")
    with pytest.raises(ToolRateLimitError):
        limiter.check("tool_x", "alice")
    # Bob still has full quota
    limiter.check("tool_x", "bob")
    limiter.check("tool_x", "bob")


def test_unknown_tool_is_unlimited():
    limiter = PerToolRateLimiter({})
    for _ in range(100):
        limiter.check("whatever", "alice")


@pytest.mark.asyncio
async def test_ai_generate_returns_typed_error_on_11th_call():
    """With cap of 10/hr/user, the 11th AI call yields TOOL_RATE_LIMITED."""
    set_tool_rate_limiter(PerToolRateLimiter({"wordpress_generate_and_upload_image": 10}))
    client = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    handler = AIMediaHandler(client, user_id="alice")

    # Pre-consume 10 tokens for alice
    from core.tool_rate_limiter import get_tool_rate_limiter

    limiter = get_tool_rate_limiter()
    for _ in range(10):
        limiter.check("wordpress_generate_and_upload_image", "alice")

    # 11th call via handler should short-circuit with typed error and not
    # even attempt to call the provider.
    result_json = await handler.generate_and_upload_image(provider="openai", prompt="a cat")
    result = json.loads(result_json)
    assert result["error_code"] == "TOOL_RATE_LIMITED"
    assert result["details"]["tool"] == "wordpress_generate_and_upload_image"


@pytest.mark.asyncio
async def test_ai_generate_another_user_not_rate_limited():
    set_tool_rate_limiter(PerToolRateLimiter({"wordpress_generate_and_upload_image": 2}))
    from core.tool_rate_limiter import get_tool_rate_limiter

    limiter = get_tool_rate_limiter()
    # Burn alice's quota
    for _ in range(2):
        limiter.check("wordpress_generate_and_upload_image", "alice")
    with pytest.raises(ToolRateLimitError):
        limiter.check("wordpress_generate_and_upload_image", "alice")

    # Bob's check still passes (handler isn't invoked — we verify the
    # limiter path, actual provider call is out of scope for this unit).
    limiter.check("wordpress_generate_and_upload_image", "bob")
