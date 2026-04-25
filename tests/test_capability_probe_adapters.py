"""F.7e — WooCommerce + Gitea ``probe_credential_capabilities`` adapters.

Each plugin's override is exercised with a stubbed client / network layer
so the test is purely logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# WooCommerce
# ---------------------------------------------------------------------------


@pytest.fixture
def wc_plugin():
    from plugins.woocommerce.plugin import WooCommercePlugin

    return WooCommercePlugin(
        config={
            "url": "https://shop.example.com",
            "consumer_key": "ck_1234567890abcdefghijklmnopqrstuvwxyzABC",
            "consumer_secret": "cs_1234567890abcdefghijklmnopqrstuvwxyzABC",
        },
        project_id="wc_probe_test",
    )


class TestWooCommerceProbe:
    @pytest.mark.asyncio
    async def test_read_permission_grants_read_only(self, wc_plugin, monkeypatch):
        payload = {
            "security": {
                "rest_api_keys": [
                    {
                        "truncated_key": "wxyzABC",  # last 7 chars of consumer_key
                        "permissions": "read",
                    }
                ]
            }
        }
        monkeypatch.setattr(wc_plugin.client, "get", AsyncMock(return_value=payload))

        out = await wc_plugin.probe_credential_capabilities()
        assert out["probe_available"] is True
        assert out["source"] == "woocommerce_system_status"
        assert out["permissions"] == "read"
        assert set(out["granted"]) == {"read_products", "read_orders"}

    @pytest.mark.asyncio
    async def test_read_write_permission_grants_everything(self, wc_plugin, monkeypatch):
        payload = {
            "security": {
                "rest_api_keys": [{"truncated_key": "wxyzABC", "permissions": "read_write"}]
            }
        }
        monkeypatch.setattr(wc_plugin.client, "get", AsyncMock(return_value=payload))

        out = await wc_plugin.probe_credential_capabilities()
        assert set(out["granted"]) == {
            "read_products",
            "read_orders",
            "write_products",
            "write_orders",
        }

    @pytest.mark.asyncio
    async def test_key_not_listed_falls_back_to_inferred(self, wc_plugin, monkeypatch):
        """F.X.fix-pass3 — when the consumer key isn't in
        system_status (truncated_key mismatch is common across WC
        builds), fall back to ``probe_inferred`` instead of returning
        a misleading probe_unavailable that triggers the badge's
        "install companion plugin" hint (WC has no companion).

        F.X.fix-pass5 — STAY CONSERVATIVE: report read-only on the
        inferred path. The previous pass probed ``settings`` and
        upgraded to write+admin on 200, but ``/wc/v3/settings`` checks
        the WP user's manage_woocommerce capability (not the API key's
        WC permission), so an admin user with a read-only key was
        being over-granted and tier-fit "Read + Write" stayed green.
        Now the badge correctly warns when ck/cs is read-only and
        the user picks Read+Write tier; tools that actually have
        write permission still execute fine.
        """
        payload = {
            "security": {
                "rest_api_keys": [
                    {"truncated_key": "xxxxxxx", "permissions": "read"},
                    {"truncated_key": "yyyyyyy", "permissions": "write"},
                ]
            }
        }

        async def _fake_get(path, **kwargs):
            if path == "system_status":
                return payload
            raise RuntimeError(f"unexpected path {path}")

        monkeypatch.setattr(wc_plugin.client, "get", _fake_get)

        out = await wc_plugin.probe_credential_capabilities()
        assert out["probe_available"] is True
        assert out.get("probe_inferred") is True
        # Conservative: only read perms reported, write withheld.
        assert "read_products" in out["granted"]
        assert "read_orders" in out["granted"]
        assert "write_products" not in out["granted"]
        assert "write_orders" not in out["granted"]
        assert out["source"] == "woocommerce_system_status_inferred"

    @pytest.mark.asyncio
    async def test_single_key_fallback_when_truncation_missing(self, wc_plugin, monkeypatch):
        """Some WC versions omit truncated_key; if there's exactly one
        key listed, fall back to it."""
        payload = {
            "security": {"rest_api_keys": [{"permissions": "read_write"}]}  # no truncated_key
        }
        monkeypatch.setattr(wc_plugin.client, "get", AsyncMock(return_value=payload))

        out = await wc_plugin.probe_credential_capabilities()
        assert out["probe_available"] is True
        assert "write_products" in out["granted"]

    @pytest.mark.asyncio
    async def test_network_failure_returns_probe_false(self, wc_plugin, monkeypatch):
        async def _boom(*_a, **_kw):
            raise RuntimeError("502 bad gateway")

        monkeypatch.setattr(wc_plugin.client, "get", _boom)

        out = await wc_plugin.probe_credential_capabilities()
        assert out["probe_available"] is False
        assert "system_status_unreachable" in out["reason"]

    @pytest.mark.asyncio
    async def test_non_dict_response_returns_probe_false(self, wc_plugin, monkeypatch):
        monkeypatch.setattr(wc_plugin.client, "get", AsyncMock(return_value=["not a dict"]))

        out = await wc_plugin.probe_credential_capabilities()
        assert out["probe_available"] is False
        assert out["reason"] == "non_dict_response"


# ---------------------------------------------------------------------------
# Gitea
# ---------------------------------------------------------------------------


@pytest.fixture
def gitea_plugin():
    from plugins.gitea.plugin import GiteaPlugin

    return GiteaPlugin(
        config={"url": "https://git.example.com", "token": "gta_test"},
        project_id="gitea_probe_test",
    )


def _fake_aiohttp_get(status: int, scopes_header: str, text_body: str = ""):
    """Build an aiohttp.ClientSession mock whose .get() returns a response
    with ``status`` and ``X-OAuth-Scopes`` header."""
    resp = AsyncMock()
    resp.status = status
    resp.headers = {"X-OAuth-Scopes": scopes_header}
    resp.text = AsyncMock(return_value=text_body)

    sess = MagicMock()
    sess.get = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=resp),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    return sess


class TestGiteaProbe:
    @pytest.mark.asyncio
    async def test_happy_path_returns_header_scopes(self, gitea_plugin):
        sess = _fake_aiohttp_get(200, "read:repository, write:repository, admin:repo_hook")
        with patch("plugins.gitea.plugin.aiohttp.ClientSession", return_value=sess):
            out = await gitea_plugin.probe_credential_capabilities()
        assert out["probe_available"] is True
        assert out["source"] == "gitea_oauth_scopes"
        assert out["granted"] == [
            "admin:repo_hook",
            "read:repository",
            "write:repository",
        ]

    @pytest.mark.asyncio
    async def test_empty_header_returns_probe_false(self, gitea_plugin):
        sess = _fake_aiohttp_get(200, "")
        with patch("plugins.gitea.plugin.aiohttp.ClientSession", return_value=sess):
            out = await gitea_plugin.probe_credential_capabilities()
        assert out["probe_available"] is False
        assert out["reason"] == "scopes_header_absent_or_empty"

    @pytest.mark.asyncio
    async def test_http_error_returns_probe_false(self, gitea_plugin):
        sess = _fake_aiohttp_get(401, "", text_body="bad token")
        with patch("plugins.gitea.plugin.aiohttp.ClientSession", return_value=sess):
            out = await gitea_plugin.probe_credential_capabilities()
        assert out["probe_available"] is False
        assert "user_endpoint_http_401" in out["reason"]
        assert "bad token" in out["reason"]

    @pytest.mark.asyncio
    async def test_network_failure_returns_probe_false(self, gitea_plugin):
        with patch(
            "plugins.gitea.plugin.aiohttp.ClientSession",
            side_effect=RuntimeError("dns failure"),
        ):
            out = await gitea_plugin.probe_credential_capabilities()
        assert out["probe_available"] is False
        assert "probe_failed" in out["reason"]

    @pytest.mark.asyncio
    async def test_single_scope_parsed(self, gitea_plugin):
        sess = _fake_aiohttp_get(200, "read:user")
        with patch("plugins.gitea.plugin.aiohttp.ClientSession", return_value=sess):
            out = await gitea_plugin.probe_credential_capabilities()
        assert out["granted"] == ["read:user"]

    @pytest.mark.asyncio
    async def test_whitespace_stripped_from_scopes(self, gitea_plugin):
        sess = _fake_aiohttp_get(200, "  read:user ,  write:repository  ,")
        with patch("plugins.gitea.plugin.aiohttp.ClientSession", return_value=sess):
            out = await gitea_plugin.probe_credential_capabilities()
        assert out["granted"] == ["read:user", "write:repository"]
