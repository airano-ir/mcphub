"""F.18.1 — Probe companion-plugin capabilities for the current credentials.

Calls ``GET /airano-mcp/v1/capabilities`` which returns the exact capability
set of the authenticated user plus the list of routes the installed companion
plugin actually ships (so MCPHub can gracefully degrade if the site is on an
older version). Consumed by F.7e's credential-capability probe.

Results are cached in-memory per ``(site_url, username)`` for 24 h, matching
``media_probe``'s behaviour.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from plugins.wordpress.client import WordPressClient

logger = logging.getLogger("mcphub.wordpress.capabilities")

CACHE_TTL_SECONDS = 24 * 3600


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "probe_capabilities",
            "method_name": "probe_capabilities",
            "description": (
                "Probe the airano-mcp-bridge companion plugin for the effective "
                "capability set of the calling application password plus the list of "
                "companion routes the installed version ships. Returns "
                "`companion_available: false` when the plugin is missing or outdated. "
                "Cached 24 h per (site, user)."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        }
    ]


# The exact capability keys the companion plugin advertises. Keep this list
# in lock-step with ``airano-mcp-bridge.php::get_capabilities()``; anything the
# plugin returns that isn't in this list is preserved as-is under ``extra``.
_EXPECTED_CAPS = (
    "upload_files",
    "edit_posts",
    "publish_posts",
    "edit_others_posts",
    "delete_posts",
    "edit_pages",
    "publish_pages",
    "manage_categories",
    "moderate_comments",
    "manage_options",
    "edit_users",
    "list_users",
    "manage_woocommerce",
    "edit_shop_orders",
    "edit_products",
)

_EXPECTED_ROUTES = (
    "seo_meta",
    "upload_limits",
    "upload_chunk",
    "upload_and_attach",
    "capabilities",
    "bulk_meta",
    "export",
    "cache_purge",
    "transient_flush",
    "site_health",
    "audit_hook",
    "regenerate_thumbnails",
)


@dataclass
class _CacheEntry:
    fetched_at: float
    data: dict[str, Any]


@dataclass
class _CapabilitiesCache:
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


_cache = _CapabilitiesCache()


def get_capabilities_cache() -> _CapabilitiesCache:
    return _cache


def _empty_capabilities_payload(site_url: str, reason: str) -> dict[str, Any]:
    """Stable response shape for the missing-companion case."""
    # Local import avoids a module-import cycle at startup time
    # (capabilities → _companion_hint → capabilities via __init__).
    from plugins.wordpress.handlers._companion_hint import companion_install_hint

    return {
        "site_url": site_url,
        "companion_available": False,
        "reason": reason,
        "plugin_version": None,
        "user": None,
        "features": None,
        "routes": dict.fromkeys(_EXPECTED_ROUTES, False),
        "wordpress": None,
        "install_hint": companion_install_hint(
            min_version="2.1.0",
            required_capability="read",
            route="airano-mcp/v1/capabilities",
        ),
    }


class CapabilitiesHandler:
    """Read-only probe of the companion plugin's capability advertisement."""

    def __init__(self, client: WordPressClient, *, cache: _CapabilitiesCache | None = None) -> None:
        self.client = client
        self._cache = cache or _cache

    @property
    def _cache_key(self) -> tuple[str, str]:
        return (self.client.site_url, self.client.username)

    async def probe_capabilities(self) -> str:
        cached = await self._cache.get(self._cache_key)
        if cached is not None:
            cached["cached"] = True
            return json.dumps(cached, indent=2)

        result = await self._fetch_capabilities()
        await self._cache.set(self._cache_key, result)
        result_out = dict(result)
        result_out["cached"] = False
        return json.dumps(result_out, indent=2)

    async def _fetch_capabilities(self) -> dict[str, Any]:
        try:
            payload = await self.client.get(
                "airano-mcp/v1/capabilities",
                use_custom_namespace=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Capabilities probe failed: %s", exc)
            return _empty_capabilities_payload(
                self.client.site_url, reason=f"companion_unreachable: {exc}"
            )

        if not isinstance(payload, dict):
            return _empty_capabilities_payload(
                self.client.site_url, reason="companion_returned_non_dict"
            )

        # Normalise the shape: fill any missing cap/route with False so
        # downstream consumers can index without KeyError checks.
        caps_raw = (payload.get("user") or {}).get("capabilities") or {}
        caps = {k: bool(caps_raw.get(k, False)) for k in _EXPECTED_CAPS}
        extra_caps = {k: bool(v) for k, v in caps_raw.items() if k not in _EXPECTED_CAPS}

        routes_raw = payload.get("routes") or {}
        routes = {k: bool(routes_raw.get(k, False)) for k in _EXPECTED_ROUTES}

        user = payload.get("user") or {}
        user_out = {
            "id": user.get("id"),
            "login": user.get("login"),
            "roles": list(user.get("roles") or []),
            "capabilities": caps,
            "extra_capabilities": extra_caps,
        }

        return {
            "site_url": self.client.site_url,
            "companion_available": True,
            "plugin_version": payload.get("plugin_version"),
            "user": user_out,
            "features": payload.get("features"),
            "routes": routes,
            "wordpress": payload.get("wordpress"),
        }


async def get_cached_capabilities(
    client: WordPressClient, *, cache: _CapabilitiesCache | None = None
) -> dict[str, Any] | None:
    """Return the cached capability dict for ``client`` without forcing a probe."""
    c = cache or _cache
    key = (client.site_url, client.username)
    return await c.get(key)
