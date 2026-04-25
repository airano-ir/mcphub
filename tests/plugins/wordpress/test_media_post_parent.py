"""F.X.fix #6 — get_media / list_media expose post_parent.

Regression: neither endpoint returned the parent post, so MCP clients
had no way to verify "is media X attached to post Y" without a second
round trip. Fix adds ``post_parent`` (int, 0 when unattached).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.handlers.media import MediaHandler


def _make_media(media_id: int, *, post: int = 0) -> dict:
    return {
        "id": media_id,
        "title": {"rendered": f"media-{media_id}"},
        "mime_type": "image/webp",
        "media_type": "image",
        "source_url": f"https://example.com/uploads/{media_id}.webp",
        "date": "2026-04-17T10:00:00",
        "alt_text": "",
        "link": f"https://example.com/?attachment_id={media_id}",
        "post": post,
        "caption": {"rendered": ""},
        "description": {"rendered": ""},
        "media_details": {},
    }


@pytest.fixture
def handler():
    client = AsyncMock()
    return MediaHandler(client), client


class TestGetMediaPostParent:
    @pytest.mark.asyncio
    async def test_get_media_returns_attached_parent(self, handler):
        h, client = handler
        client.get = AsyncMock(return_value=_make_media(77, post=42))
        raw = await h.get_media(media_id=77)
        data = json.loads(raw)
        assert data["post_parent"] == 42

    @pytest.mark.asyncio
    async def test_get_media_returns_zero_when_unattached(self, handler):
        h, client = handler
        client.get = AsyncMock(return_value=_make_media(78, post=0))
        raw = await h.get_media(media_id=78)
        data = json.loads(raw)
        # WP's own REST returns 0 for unattached; we preserve that.
        assert data["post_parent"] == 0

    @pytest.mark.asyncio
    async def test_get_media_handles_missing_post_key(self, handler):
        h, client = handler
        payload = _make_media(79, post=0)
        del payload["post"]  # older WP installs or partial fields=
        client.get = AsyncMock(return_value=payload)
        raw = await h.get_media(media_id=79)
        data = json.loads(raw)
        assert data["post_parent"] == 0


class TestListMediaPostParent:
    @pytest.mark.asyncio
    async def test_list_media_shape_includes_post_parent(self, handler):
        h, client = handler
        client.get = AsyncMock(
            return_value=[
                _make_media(1, post=42),
                _make_media(2, post=0),
                _make_media(3, post=99),
            ]
        )
        raw = await h.list_media()
        data = json.loads(raw)
        parents = [m["post_parent"] for m in data["media"]]
        assert parents == [42, 0, 99]

    @pytest.mark.asyncio
    async def test_list_media_unattached_reports_zero_not_null(self, handler):
        h, client = handler
        item = _make_media(5, post=0)
        item["post"] = None  # Some older WP payloads send null
        client.get = AsyncMock(return_value=[item])
        raw = await h.list_media()
        data = json.loads(raw)
        # MCP consumers expect an int they can compare against; None
        # makes type-strict callers crash. Normalise to 0.
        assert data["media"][0]["post_parent"] == 0
