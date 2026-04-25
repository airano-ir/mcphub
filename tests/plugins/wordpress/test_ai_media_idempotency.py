"""F.X.fix #7 — AI image upload sends Idempotency-Key to the companion.

Regression: when the MCP client timed out mid-call the companion had
already created the attachment. The client retried and the companion
created a second ``-2.webp`` orphan, leaving admins to clean up by
hand. Fix: generate a stable key per logical call, send it as an
``Idempotency-Key`` header, and let the companion dedupe.

These tests cover the Python side — the key is deterministic for the
same inputs, differs when any input changes, and is actually put on
the wire when ``_companion_upload_and_attach`` fires.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers import _media_core
from plugins.wordpress.handlers.ai_media import (
    _content_sha,
    _idempotency_key_for,
)


class TestIdempotencyKeyBuilder:
    def test_matches_companion_regex(self):
        key = _idempotency_key_for(
            provider="openrouter",
            model="google/gemini-2.5-flash-image",
            prompt="a cat",
            size="1024x1024",
            attach_to_post=42,
            set_featured=True,
            site_url="https://blog.example.com",
            user_id="user-1",
            content_sha=_content_sha(b"bytes"),
        )
        # Companion PHP validates ^[A-Za-z0-9_-]{1,128}$ before use.
        import re

        assert re.match(r"^[A-Za-z0-9_\-]{1,128}$", key)
        assert 1 <= len(key) <= 128

    def test_deterministic_for_same_inputs(self):
        kwargs = {
            "provider": "openrouter",
            "model": "google/gemini-2.5-flash-image",
            "prompt": "a cat",
            "size": "1024x1024",
            "attach_to_post": 42,
            "set_featured": True,
            "site_url": "https://blog.example.com",
            "user_id": "user-1",
            "content_sha": "abc123",
        }
        assert _idempotency_key_for(**kwargs) == _idempotency_key_for(**kwargs)

    def test_differs_when_prompt_changes(self):
        base = {
            "provider": "openrouter",
            "model": "m",
            "prompt": "cat",
            "size": "1024x1024",
            "attach_to_post": 0,
            "set_featured": False,
            "site_url": "https://x",
            "user_id": None,
            "content_sha": "a",
        }
        other = {**base, "prompt": "dog"}
        assert _idempotency_key_for(**base) != _idempotency_key_for(**other)

    def test_differs_when_attach_to_post_changes(self):
        base = {
            "provider": "openrouter",
            "model": "m",
            "prompt": "x",
            "size": "1024x1024",
            "attach_to_post": None,
            "set_featured": False,
            "site_url": "https://x",
            "user_id": None,
            "content_sha": "a",
        }
        other = {**base, "attach_to_post": 42}
        assert _idempotency_key_for(**base) != _idempotency_key_for(**other)


class TestHeaderPropagation:
    @pytest.mark.asyncio
    async def test_idempotency_key_reaches_companion_route(self):
        """_companion_upload_and_attach must put the key in the header."""
        client = WordPressClient("https://example.com", "u", "app_pw")

        captured: dict = {}

        class _FakeResp:
            status = 200

            async def text(self):
                return "{}"

            async def json(self, content_type=None):
                return {"id": 99, "source_url": "https://example.com/a.png"}

        def _request(url, data=None, headers=None, params=None):
            captured["headers"] = headers
            captured["params"] = params
            return AsyncMock(
                __aenter__=AsyncMock(return_value=_FakeResp()),
                __aexit__=AsyncMock(return_value=False),
            )

        session = AsyncMock()
        session.post = _request
        with patch(
            "plugins.wordpress.handlers._media_core.aiohttp.ClientSession",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ):
            await _media_core._companion_upload_and_attach(
                client,
                b"\x89PNG\r\n\x1a\n",
                sniffed="image/png",
                disposition='attachment; filename="a.png"',
                attach_to_post=42,
                set_featured=True,
                title=None,
                alt_text=None,
                caption=None,
                description=None,
                idempotency_key="mcphub_ai_abc123",
            )

        assert captured["headers"]["Idempotency-Key"] == "mcphub_ai_abc123"

    @pytest.mark.asyncio
    async def test_idempotency_key_absent_header_when_none(self):
        client = WordPressClient("https://example.com", "u", "app_pw")

        captured: dict = {}

        class _FakeResp:
            status = 200

            async def text(self):
                return "{}"

            async def json(self, content_type=None):
                return {"id": 7}

        def _request(url, data=None, headers=None, params=None):
            captured["headers"] = headers
            return AsyncMock(
                __aenter__=AsyncMock(return_value=_FakeResp()),
                __aexit__=AsyncMock(return_value=False),
            )

        session = AsyncMock()
        session.post = _request
        with patch(
            "plugins.wordpress.handlers._media_core.aiohttp.ClientSession",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ):
            await _media_core._companion_upload_and_attach(
                client,
                b"x",
                sniffed="image/png",
                disposition='attachment; filename="a.png"',
                attach_to_post=None,
                set_featured=False,
                title=None,
                alt_text=None,
                caption=None,
                description=None,
                idempotency_key=None,
            )
        # No Idempotency-Key header when the caller didn't supply one;
        # the companion must still handle the request normally.
        assert "Idempotency-Key" not in captured["headers"]
