"""F.5a.7 — Companion upload route selection tests.

Validates `_media_core.wp_raw_upload` behaviour when the
`airano-mcp/v1/upload-limits` probe advertises the companion plugin:

- helper-present + size > advertised limit → POST to companion upload-chunk
- helper-present + size < advertised limit → POST to standard /wp/v2/media
- helper-absent → always POST to /wp/v2/media (no probe = no companion)
- companion 4xx → fall back to /wp/v2/media (never regress default path)
"""

from __future__ import annotations

import base64
import json
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers import _media_core as media_core
from plugins.wordpress.handlers._media_core import wp_raw_upload
from plugins.wordpress.handlers.media_probe import _ProbeCache

# A minimal valid 1x1 PNG.
_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _client() -> WordPressClient:
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


class _FakeResponse:
    def __init__(self, status: int, payload: dict | None, *, text: str | None = None) -> None:
        self.status = status
        self._payload = payload
        self._text = text if text is not None else json.dumps(payload or {})

    async def text(self) -> str:
        return self._text

    async def json(self, content_type=None):  # noqa: D401, ANN001
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):  # noqa: ANN002
        return False


class _RecordingSession:
    """aiohttp.ClientSession stand-in that records every POST target."""

    def __init__(self, responses_by_url: dict[str, _FakeResponse]) -> None:
        self._responses_by_url = responses_by_url
        self.posts: list[str] = []

    def post(self, url, data=None, headers=None):  # noqa: ANN001
        self.posts.append(url)
        resp = self._responses_by_url.get(url)
        if resp is None:
            raise AssertionError(f"unexpected POST to {url!r}")
        return resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):  # noqa: ANN002
        return False


@asynccontextmanager
async def _patched_session(session: _RecordingSession):
    with patch("plugins.wordpress.handlers._media_core.aiohttp.ClientSession") as cls:
        cls.return_value = session
        yield cls


# WP attachment JSON shape (identical across /wp/v2/media and companion route).
_WP_MEDIA_JSON = {
    "id": 101,
    "title": {"rendered": "photo"},
    "mime_type": "image/png",
    "media_type": "image",
    "source_url": "https://wp.example.com/wp-content/uploads/photo.png",
}


def _rest_url() -> str:
    return "https://wp.example.com/wp-json/wp/v2/media"


def _companion_url() -> str:
    return "https://wp.example.com/wp-json/airano-mcp/v1/upload-chunk"


async def _seed_probe_cache(
    client: WordPressClient,
    *,
    companion: bool,
    upload_max_filesize_bytes: int | None = None,
) -> _ProbeCache:
    """Inject a cached probe result so wp_raw_upload sees it synchronously."""
    cache = _ProbeCache(ttl=3600)
    limits = {
        "upload_max_filesize": None,
        "post_max_size": None,
        "memory_limit": None,
        "max_input_time": None,
        "wp_max_upload_size": None,
    }
    if upload_max_filesize_bytes is not None:
        limits["upload_max_filesize"] = upload_max_filesize_bytes  # already bytes
    payload = {
        "site_url": client.site_url,
        "source": "companion" if companion else "rest_index",
        "companion_available": companion,
        "limits": limits,
        "limits_bytes": {
            "upload_max_filesize": upload_max_filesize_bytes,
            "post_max_size": None,
            "wp_max_upload_size": None,
            "effective_ceiling": upload_max_filesize_bytes,
        },
    }
    await cache.set((client.site_url, client.username), payload)
    return cache


@pytest.mark.asyncio
async def test_companion_preferred_when_size_exceeds_limit(monkeypatch):
    client = _client()
    cache = await _seed_probe_cache(
        client, companion=True, upload_max_filesize_bytes=4  # 4 bytes → our 1x1 PNG is larger
    )
    monkeypatch.setattr("plugins.wordpress.handlers.media_probe._cache", cache)

    session = _RecordingSession(
        {_companion_url(): _FakeResponse(201, _WP_MEDIA_JSON)},
    )
    async with _patched_session(session):
        result = await wp_raw_upload(client, _PNG_1x1, filename="photo.png")

    assert session.posts == [_companion_url()]
    assert result["id"] == 101
    assert result.get("_upload_route") == "companion"


@pytest.mark.asyncio
async def test_rest_used_when_size_under_limit(monkeypatch):
    client = _client()
    # Advertise a huge limit so the PNG slips under it.
    cache = await _seed_probe_cache(client, companion=True, upload_max_filesize_bytes=10 * 1024**2)
    monkeypatch.setattr("plugins.wordpress.handlers.media_probe._cache", cache)

    session = _RecordingSession(
        {_rest_url(): _FakeResponse(201, _WP_MEDIA_JSON)},
    )
    async with _patched_session(session):
        result = await wp_raw_upload(client, _PNG_1x1, filename="photo.png")

    assert session.posts == [_rest_url()]
    assert result["id"] == 101
    assert result.get("_upload_route") == "rest"


@pytest.mark.asyncio
async def test_rest_used_when_companion_absent(monkeypatch):
    client = _client()
    cache = await _seed_probe_cache(client, companion=False)
    monkeypatch.setattr("plugins.wordpress.handlers.media_probe._cache", cache)

    session = _RecordingSession(
        {_rest_url(): _FakeResponse(201, _WP_MEDIA_JSON)},
    )
    async with _patched_session(session):
        await wp_raw_upload(client, _PNG_1x1, filename="photo.png")

    assert session.posts == [_rest_url()]


@pytest.mark.asyncio
async def test_rest_used_when_cache_empty(monkeypatch):
    """Cold cache = no companion hint available = take the standard route."""
    client = _client()
    empty_cache = _ProbeCache(ttl=3600)
    monkeypatch.setattr("plugins.wordpress.handlers.media_probe._cache", empty_cache)

    session = _RecordingSession(
        {_rest_url(): _FakeResponse(201, _WP_MEDIA_JSON)},
    )
    async with _patched_session(session):
        await wp_raw_upload(client, _PNG_1x1, filename="photo.png")

    assert session.posts == [_rest_url()]


@pytest.mark.asyncio
async def test_companion_4xx_falls_back_to_rest(monkeypatch):
    client = _client()
    cache = await _seed_probe_cache(client, companion=True, upload_max_filesize_bytes=4)
    monkeypatch.setattr("plugins.wordpress.handlers.media_probe._cache", cache)

    session = _RecordingSession(
        {
            _companion_url(): _FakeResponse(500, None, text='{"code":"sideload_failed"}'),
            _rest_url(): _FakeResponse(201, _WP_MEDIA_JSON),
        }
    )
    async with _patched_session(session):
        result = await wp_raw_upload(client, _PNG_1x1, filename="photo.png")

    # Companion tried first, then the REST fallback.
    assert session.posts == [_companion_url(), _rest_url()]
    assert result["id"] == 101
    assert result.get("_upload_route") == "rest"


@pytest.mark.asyncio
async def test_should_use_companion_is_defensive(monkeypatch):
    """If the probe lookup raises, we must not crash the upload path."""
    client = _client()

    async def boom(_client):
        raise RuntimeError("probe blew up")

    monkeypatch.setattr(
        "plugins.wordpress.handlers.media_probe.get_cached_limits",
        boom,
    )
    assert await media_core._should_use_companion(client, 10 * 1024**2) is False
