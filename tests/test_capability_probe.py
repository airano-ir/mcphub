"""F.7e — tests for the per-site credential capability probe.

Covers:

* ``BasePlugin.probe_credential_capabilities`` default (probe unavailable).
* WordPress override: extracts granted capabilities from the companion
  payload, surfaces roles + plugin_version, and degrades gracefully
  when the companion isn't installed.
* ``probe_site_capabilities`` caches, decrypts credentials safely,
  handles unknown sites, plugin-not-registered, and probe failures.
* ``_ProbeCache`` TTL expiry + explicit invalidation.
* Starlette handler: 401 unauth, 404 unknown site, happy-path body.
"""

from __future__ import annotations

import base64
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.capability_probe import (
    _ProbeCache,
    api_site_capabilities,
    get_probe_cache,
    probe_site_capabilities,
)
from plugins.base import BasePlugin

# ---------------------------------------------------------------------------
# BasePlugin default
# ---------------------------------------------------------------------------


class _DummyPlugin(BasePlugin):
    def get_plugin_name(self) -> str:
        return "dummy"


class TestBasePluginDefault:
    @pytest.mark.asyncio
    async def test_default_reports_probe_unavailable(self):
        p = _DummyPlugin(config={"url": "https://x"}, project_id="dummy_t")
        out = await p.probe_credential_capabilities()
        assert out["probe_available"] is False
        assert out["granted"] == []
        assert out["source"] == "unavailable"
        assert out["reason"] == "probe_not_implemented"


# ---------------------------------------------------------------------------
# WordPress override
# ---------------------------------------------------------------------------


@pytest.fixture
def wp_plugin():
    """Build a WordPress plugin instance with a stubbed client."""
    from plugins.wordpress.plugin import WordPressPlugin

    return WordPressPlugin(
        config={
            "url": "https://wp.example.com",
            "username": "admin",
            "app_password": "xxxx xxxx xxxx",
        },
        project_id="wordpress_probe_test",
    )


class TestWordPressProbe:
    @pytest.mark.asyncio
    async def test_happy_path_extracts_granted_caps(self, wp_plugin, monkeypatch):
        companion_payload = {
            "companion_available": True,
            "plugin_version": "2.8.0",
            "user": {
                "id": 1,
                "login": "admin",
                "roles": ["administrator"],
                "capabilities": {
                    "edit_posts": True,
                    "upload_files": True,
                    "manage_options": True,
                    "read": True,
                    "publish_pages": False,
                },
            },
            "features": {"rank_math": True},
            "routes": {"cache_purge": True},
        }
        monkeypatch.setattr(
            wp_plugin.capabilities,
            "_fetch_capabilities",
            AsyncMock(return_value=companion_payload),
        )

        out = await wp_plugin.probe_credential_capabilities()
        assert out["probe_available"] is True
        assert out["source"] == "wordpress_companion"
        assert set(out["granted"]) == {"edit_posts", "upload_files", "manage_options", "read"}
        assert out["roles"] == ["administrator"]
        assert out["plugin_version"] == "2.8.0"

    @pytest.mark.asyncio
    async def test_companion_unavailable_returns_probe_false(self, wp_plugin, monkeypatch):
        monkeypatch.setattr(
            wp_plugin.capabilities,
            "_fetch_capabilities",
            AsyncMock(
                return_value={
                    "companion_available": False,
                    "reason": "companion_unreachable: 404",
                    "site_url": "https://wp.example.com",
                }
            ),
        )

        out = await wp_plugin.probe_credential_capabilities()
        assert out["probe_available"] is False
        assert out["granted"] == []
        assert "companion_unreachable" in out["reason"]

    @pytest.mark.asyncio
    async def test_probe_call_failure_does_not_raise(self, wp_plugin, monkeypatch):
        async def _boom(*_a, **_kw):
            raise RuntimeError("network collapsed")

        monkeypatch.setattr(wp_plugin.capabilities, "_fetch_capabilities", _boom)

        out = await wp_plugin.probe_credential_capabilities()
        # _empty_capabilities_payload kicks in → probe_available stays False.
        assert out["probe_available"] is False
        assert "reason" in out


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------


class TestProbeCache:
    @pytest.mark.unit
    def test_get_missing_returns_none(self):
        c = _ProbeCache(ttl_seconds=60)
        assert c.get("no-such-id") is None

    @pytest.mark.unit
    def test_set_then_get_round_trip(self):
        c = _ProbeCache(ttl_seconds=60)
        c.set("s1", {"granted": ["read"]})
        assert c.get("s1") == {"granted": ["read"]}

    @pytest.mark.unit
    def test_expiry_evicts(self):
        c = _ProbeCache(ttl_seconds=0)
        c.set("s1", {"granted": ["read"]})
        # ttl=0 → immediately expired.
        assert c.get("s1") is None

    @pytest.mark.unit
    def test_invalidate_removes(self):
        c = _ProbeCache(ttl_seconds=60)
        c.set("s1", {"granted": ["read"]})
        assert c.invalidate("s1") is True
        assert c.get("s1") is None
        # Second invalidate on empty slot returns False.
        assert c.invalidate("s1") is False

    @pytest.mark.unit
    def test_get_probe_cache_is_singleton(self):
        a = get_probe_cache()
        b = get_probe_cache()
        assert a is b


# ---------------------------------------------------------------------------
# probe_site_capabilities (integration with DB + encryption)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_probe_cache():
    cache = get_probe_cache()
    cache._entries.clear()
    yield
    cache._entries.clear()


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    import core.encryption as enc_mod

    monkeypatch.setattr(enc_mod, "_credential_encryption", None)


@pytest.fixture
async def db_with_site(tmp_path, monkeypatch):
    """Initialize a real DB + fixture user and WP site."""
    import core.database as db_mod
    from core.database import initialize_database
    from core.encryption import get_credential_encryption

    monkeypatch.setattr(db_mod, "_database", None)
    database = await initialize_database(str(tmp_path / "probe.db"))
    user = await database.create_user(
        email="probe@example.com",
        name="Probe",
        provider="github",
        provider_id="gh-probe",
    )

    enc = get_credential_encryption()
    creds = enc.encrypt_credentials(
        {"username": "admin", "app_password": "yyyy yyyy yyyy"},
        "site-probe-1",  # any scope string; decrypt uses same
    )
    site = await database.create_site(
        user_id=user["id"],
        plugin_type="wordpress",
        alias="blog",
        url="https://wp.example.com",
        credentials=creds,
    )
    # Force known id so encryption scope matches.
    await database.execute(
        "UPDATE sites SET id = ? WHERE id = ?",
        ("site-probe-1", site["id"]),
    )
    # Re-fetch.
    site = await database.get_site("site-probe-1", user["id"])

    yield database, user, site
    await database.close()
    monkeypatch.setattr(db_mod, "_database", None)


class TestProbeSiteCapabilities:
    @pytest.mark.asyncio
    async def test_unknown_site_returns_structured_error(self, db_with_site):
        _, user, _ = db_with_site
        out = await probe_site_capabilities("no-such", user["id"])
        assert out["reason"] == "site_not_found"
        assert out["probe_available"] is False

    @pytest.mark.asyncio
    async def test_happy_path_caches_result(self, db_with_site, monkeypatch):
        _, user, site = db_with_site

        call_count = {"n": 0}

        async def _fake_probe(self: Any) -> dict[str, Any]:
            call_count["n"] += 1
            return {
                "probe_available": True,
                "granted": ["edit_posts", "upload_files"],
                "source": "wordpress_companion",
                "roles": ["administrator"],
                "plugin_version": "2.8.0",
            }

        from plugins.wordpress.plugin import WordPressPlugin

        monkeypatch.setattr(WordPressPlugin, "probe_credential_capabilities", _fake_probe)

        out1 = await probe_site_capabilities(site["id"], user["id"])
        assert out1["probe_available"] is True
        assert out1["cached"] is False
        assert set(out1["granted"]) == {"edit_posts", "upload_files"}
        assert out1["roles"] == ["administrator"]

        # Second call hits cache.
        out2 = await probe_site_capabilities(site["id"], user["id"])
        assert out2["cached"] is True
        assert call_count["n"] == 1  # only one real probe

        # Force bypass.
        out3 = await probe_site_capabilities(site["id"], user["id"], force=True)
        assert out3["cached"] is False
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    async def test_probe_exception_is_swallowed(self, db_with_site, monkeypatch):
        _, user, site = db_with_site

        async def _boom(self: Any) -> dict[str, Any]:
            raise RuntimeError("no network")

        from plugins.wordpress.plugin import WordPressPlugin

        monkeypatch.setattr(WordPressPlugin, "probe_credential_capabilities", _boom)

        out = await probe_site_capabilities(site["id"], user["id"])
        assert out["probe_available"] is False
        assert "probe_call_failed" in out["reason"]


# ---------------------------------------------------------------------------
# Starlette handler
# ---------------------------------------------------------------------------


def _make_probe_request(site_id: str, force: bool = False):
    from starlette.requests import Request

    query = b"force=1" if force else b""
    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/api/sites/{site_id}/capabilities",
        "path_params": {"id": site_id},
        "headers": [],
        "query_string": query,
    }

    async def receive():
        return {"type": "http.request", "body": b""}

    return Request(scope, receive)


class TestCapabilitiesEndpoint:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self):
        with patch("core.dashboard.routes._require_user_session") as mock_guard:
            mock_guard.return_value = (None, MagicMock())
            resp = await api_site_capabilities(_make_probe_request("s1"))
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_site_returns_404(self, db_with_site):
        _, user, _ = db_with_site
        with patch("core.dashboard.routes._require_user_session") as mock_guard:
            mock_guard.return_value = ({"user_id": user["id"]}, None)
            resp = await api_site_capabilities(_make_probe_request("no-such"))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_happy_path_returns_payload(self, db_with_site, monkeypatch):
        _, user, site = db_with_site

        async def _fake_probe(self: Any) -> dict[str, Any]:
            return {
                "probe_available": True,
                "granted": ["edit_posts", "upload_files"],
                "source": "wordpress_companion",
            }

        from plugins.wordpress.plugin import WordPressPlugin

        monkeypatch.setattr(WordPressPlugin, "probe_credential_capabilities", _fake_probe)

        with patch("core.dashboard.routes._require_user_session") as mock_guard:
            mock_guard.return_value = ({"user_id": user["id"]}, None)
            resp = await api_site_capabilities(_make_probe_request(site["id"]))
        assert resp.status_code == 200
        import json as _json

        body = _json.loads(bytes(resp.body))
        assert body["ok"] is True
        assert body["probe_available"] is True
        assert body["plugin_type"] == "wordpress"
        assert set(body["granted"]) == {"edit_posts", "upload_files"}
