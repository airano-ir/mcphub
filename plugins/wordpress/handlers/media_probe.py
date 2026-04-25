"""F.5a.6.3 — Probe WordPress upload limits with 24 h cache.

Tries the airano-mcp-bridge companion endpoint first (which can read
PHP ini values directly); falls back to whatever the standard WP REST
index publishes. Results are cached in-memory per site for 24 h.

The cache is keyed by ``(site_url, username)`` so admin and per-user
clients don't poison each other's view.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from plugins.wordpress.client import WordPressClient

logger = logging.getLogger("mcphub.wordpress.media_probe")

CACHE_TTL_SECONDS = 24 * 3600


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "probe_upload_limits",
            "method_name": "probe_upload_limits",
            "description": (
                "Probe a WordPress site for its effective upload limits "
                "(upload_max_filesize, post_max_size, memory_limit, "
                "max_input_time, wp_max_upload_size). Uses the "
                "airano-mcp-bridge companion plugin if present, else "
                "best-effort from the WP REST index. Cached 24 h per site."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        }
    ]


@dataclass
class _CacheEntry:
    fetched_at: float
    data: dict[str, Any]


@dataclass
class _ProbeCache:
    """Process-local TTL cache keyed by (site_url, username)."""

    ttl: float = CACHE_TTL_SECONDS
    _entries: dict[tuple[str, str], _CacheEntry] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(self, key: tuple[str, str]) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if (time.time() - entry.fetched_at) > self.ttl:
                self._entries.pop(key, None)
                return None
            return dict(entry.data)

    async def set(self, key: tuple[str, str], data: dict[str, Any]) -> None:
        async with self._lock:
            self._entries[key] = _CacheEntry(fetched_at=time.time(), data=dict(data))

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()


_cache = _ProbeCache()


def get_probe_cache() -> _ProbeCache:
    return _cache


_LIMIT_KEYS = (
    "upload_max_filesize",
    "post_max_size",
    "memory_limit",
    "max_input_time",
    "wp_max_upload_size",
)

# Byte-valued keys among `_LIMIT_KEYS` — used by F.5a.7 route selection to
# decide whether to prefer the companion upload-chunk route over /wp/v2/media.
_BYTE_VALUED_KEYS = ("upload_max_filesize", "post_max_size", "wp_max_upload_size")


def _empty_limits() -> dict[str, Any]:
    return dict.fromkeys(_LIMIT_KEYS)


def parse_php_size(value: Any) -> int | None:
    """Parse a PHP ``ini_get`` size string like ``"64M"`` to bytes.

    Accepts an already-numeric value (returns it as-is cast to int), a suffix
    of K/M/G/T (both upper- and lower-case), or a bare integer string.
    Returns None if the value can't be parsed or represents "no limit" (``-1``).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return None if value < 0 else value
    if isinstance(value, float):
        return None if value < 0 else int(value)
    s = str(value).strip()
    if not s:
        return None
    if s in {"-1", "0"}:
        return None
    unit = s[-1].upper()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    try:
        if unit in multipliers:
            return int(float(s[:-1]) * multipliers[unit])
        return int(s)
    except (TypeError, ValueError):
        return None


def effective_upload_ceiling(limits: dict[str, Any] | None) -> int | None:
    """Return the smallest relevant size ceiling (in bytes) across the limits.

    For route-selection purposes we take the min of the byte-valued keys that
    are populated. If nothing is populated, returns None (= "unknown, treat
    every upload as small enough for the REST route").
    """
    if not limits:
        return None
    parsed: list[int] = []
    for key in _BYTE_VALUED_KEYS:
        raw = limits.get(key)
        got = parse_php_size(raw)
        if got is not None:
            parsed.append(got)
    return min(parsed) if parsed else None


class ProbeHandler:
    """Read-only probe of a WordPress site's upload limits."""

    def __init__(self, client: WordPressClient, *, cache: _ProbeCache | None = None) -> None:
        self.client = client
        self._cache = cache or _cache

    @property
    def _cache_key(self) -> tuple[str, str]:
        return (self.client.site_url, self.client.username)

    async def probe_upload_limits(self) -> str:
        cached = await self._cache.get(self._cache_key)
        if cached is not None:
            cached["cached"] = True
            return json.dumps(cached, indent=2)

        result = await self._fetch_limits()
        await self._cache.set(self._cache_key, result)
        result_out = dict(result)
        result_out["cached"] = False
        return json.dumps(result_out, indent=2)

    async def _fetch_limits(self) -> dict[str, Any]:
        limits = _empty_limits()
        source = "unknown"
        # Companion plugin first.
        try:
            payload = await self.client.get(
                "airano-mcp/v1/upload-limits",
                use_custom_namespace=True,
            )
            if isinstance(payload, dict):
                for k in _LIMIT_KEYS:
                    if payload.get(k) is not None:
                        limits[k] = payload[k]
                source = "companion"
        except Exception as exc:  # noqa: BLE001
            logger.debug("Companion probe failed (%s); falling back to REST index.", exc)

        # Fallback / supplement: REST index may expose wp_max_upload_size.
        if all(v is None for v in limits.values()):
            try:
                root = await self.client.get("", use_custom_namespace=True)  # /wp-json/
                if isinstance(root, dict):
                    if "wp_max_upload_size" in root:
                        limits["wp_max_upload_size"] = root["wp_max_upload_size"]
                    source = "rest_index"
            except Exception as exc:  # noqa: BLE001
                logger.debug("REST index probe failed: %s", exc)

        # F.5a.7: expose byte-parsed ceiling so _media_core can pick the
        # best upload route without re-parsing PHP ini strings.
        ceiling = effective_upload_ceiling(limits)
        return {
            "site_url": self.client.site_url,
            "source": source,
            "companion_available": source == "companion",
            "limits": limits,
            "limits_bytes": {
                "upload_max_filesize": parse_php_size(limits.get("upload_max_filesize")),
                "post_max_size": parse_php_size(limits.get("post_max_size")),
                "wp_max_upload_size": parse_php_size(limits.get("wp_max_upload_size")),
                "effective_ceiling": ceiling,
            },
        }


async def get_cached_limits(
    client: WordPressClient, *, cache: _ProbeCache | None = None
) -> dict[str, Any] | None:
    """Return the cached limits dict for ``client`` without forcing a probe.

    Used by `_media_core.wp_raw_upload` to decide whether to prefer the
    companion upload-chunk route. Returns None when no probe has been cached
    yet — callers treat that as "no hints available; take the standard path".
    """
    c = cache or _cache
    key = (client.site_url, client.username)
    return await c.get(key)
