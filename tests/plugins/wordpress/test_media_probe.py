"""F.5a.6.3 — Tests for wordpress_probe_upload_limits."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.media_probe import ProbeHandler, _ProbeCache


@pytest.fixture
def wp_client():
    return WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")


@pytest.fixture
def cache():
    return _ProbeCache(ttl=24 * 3600)


@pytest.mark.asyncio
async def test_companion_endpoint_parses_and_caches(wp_client, monkeypatch, cache):
    handler = ProbeHandler(wp_client, cache=cache)
    payload = {
        "upload_max_filesize": "64M",
        "post_max_size": "128M",
        "memory_limit": "256M",
        "max_input_time": "300",
        "wp_max_upload_size": 67108864,
    }
    get_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(wp_client, "get", get_mock)

    out_json = await handler.probe_upload_limits()
    out = json.loads(out_json)

    assert out["source"] == "companion"
    assert out["limits"] == payload
    assert out["cached"] is False
    # F.5a.7: companion payload exposes byte-parsed limits + companion flag.
    assert out["companion_available"] is True
    assert out["limits_bytes"]["upload_max_filesize"] == 64 * 1024**2
    assert out["limits_bytes"]["post_max_size"] == 128 * 1024**2
    assert out["limits_bytes"]["wp_max_upload_size"] == 67108864
    # The effective ceiling is the smallest of the byte-valued keys.
    assert out["limits_bytes"]["effective_ceiling"] == 64 * 1024**2
    # First call hit the network exactly once.
    assert get_mock.call_count == 1
    get_mock.assert_called_with("airano-mcp/v1/upload-limits", use_custom_namespace=True)


@pytest.mark.asyncio
async def test_second_call_is_served_from_cache(wp_client, monkeypatch, cache):
    handler = ProbeHandler(wp_client, cache=cache)
    payload = {"upload_max_filesize": "64M"}
    get_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(wp_client, "get", get_mock)

    await handler.probe_upload_limits()
    out2 = json.loads(await handler.probe_upload_limits())

    assert out2["cached"] is True
    # Network only hit once across two probe calls.
    assert get_mock.call_count == 1


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(wp_client, monkeypatch):
    cache = _ProbeCache(ttl=0.0)  # immediate expiry
    handler = ProbeHandler(wp_client, cache=cache)
    get_mock = AsyncMock(return_value={"upload_max_filesize": "64M"})
    monkeypatch.setattr(wp_client, "get", get_mock)

    await handler.probe_upload_limits()
    await handler.probe_upload_limits()
    # ttl=0 → both calls re-fetch.
    assert get_mock.call_count == 2


@pytest.mark.asyncio
async def test_companion_failure_falls_back_to_rest_index(wp_client, monkeypatch, cache):
    handler = ProbeHandler(wp_client, cache=cache)

    async def fake_get(endpoint, **kwargs):
        if endpoint == "airano-mcp/v1/upload-limits":
            raise RuntimeError("404")
        if endpoint == "":
            return {"wp_max_upload_size": 4 * 1024 * 1024}
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=fake_get))

    out = json.loads(await handler.probe_upload_limits())
    assert out["source"] == "rest_index"
    assert out["limits"]["wp_max_upload_size"] == 4 * 1024 * 1024


@pytest.mark.asyncio
async def test_total_failure_returns_empty_limits(wp_client, monkeypatch, cache):
    handler = ProbeHandler(wp_client, cache=cache)
    monkeypatch.setattr(wp_client, "get", AsyncMock(side_effect=RuntimeError("totally offline")))
    out = json.loads(await handler.probe_upload_limits())
    assert out["source"] == "unknown"
    assert all(v is None for v in out["limits"].values())


def test_tool_spec_is_read_scope():
    from plugins.wordpress.handlers.media_probe import get_tool_specifications

    specs = get_tool_specifications()
    assert len(specs) == 1
    assert specs[0]["name"] == "probe_upload_limits"
    assert specs[0]["scope"] == "read"


# F.5a.7: byte parser helpers ------------------------------------------------


class TestParsePhpSize:
    @staticmethod
    def _parse(v):
        from plugins.wordpress.handlers.media_probe import parse_php_size

        return parse_php_size(v)

    def test_none(self):
        assert self._parse(None) is None

    def test_empty_string(self):
        assert self._parse("") is None

    def test_bare_integer_string(self):
        assert self._parse("1024") == 1024

    def test_megabytes_upper(self):
        assert self._parse("64M") == 64 * 1024**2

    def test_megabytes_lower(self):
        assert self._parse("8m") == 8 * 1024**2

    def test_gigabytes(self):
        assert self._parse("2G") == 2 * 1024**3

    def test_numeric_int(self):
        assert self._parse(4096) == 4096

    def test_unlimited_minus_one(self):
        # PHP "-1" means no limit; treat as unknown.
        assert self._parse("-1") is None
        assert self._parse(-1) is None

    def test_invalid(self):
        assert self._parse("garbage") is None


class TestEffectiveCeiling:
    def test_returns_min_of_populated(self):
        from plugins.wordpress.handlers.media_probe import effective_upload_ceiling

        limits = {
            "upload_max_filesize": "8M",
            "post_max_size": "64M",
            "memory_limit": "256M",
            "max_input_time": "60",
            "wp_max_upload_size": 8388608,
        }
        # min(8MB, 64MB, 8388608 bytes) = 8388608 bytes
        assert effective_upload_ceiling(limits) == 8 * 1024**2

    def test_none_when_empty(self):
        from plugins.wordpress.handlers.media_probe import effective_upload_ceiling

        assert effective_upload_ceiling({}) is None
        assert effective_upload_ceiling(None) is None
