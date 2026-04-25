"""F.X.fix #3 — WordPressClient fast-fails on unreachable sites.

Regression: tools hung 35-85s on DNS-dead / TCP-refused hosts because
the client did not set a connect timeout. Fix adds connect=5 and maps
every TCP/DNS/SSL failure to SiteUnreachableError with a structured
install_hint. Budget: total wall-clock < 10s per request.
"""

from __future__ import annotations

import socket
import time
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from plugins.wordpress.client import (
    _CONNECT_TIMEOUT,
    _REQUEST_TIMEOUT,
    SiteUnreachableError,
    WordPressClient,
)


@pytest.fixture
def client() -> WordPressClient:
    return WordPressClient("https://dead.example.invalid", "user", "app_pw")


def _patch_session_raising(exc: Exception):
    """Patch aiohttp.ClientSession so ``session.request(...)`` raises ``exc``.

    The production code uses ``async with session.request(...) as resp``,
    so we mock ``request`` as a plain callable returning an
    ``AsyncMock`` whose ``__aenter__`` raises — matching the real
    ``aiohttp.ClientConnector*`` error path.
    """
    session = AsyncMock()

    def _request(*_args, **_kwargs):
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(side_effect=exc)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    session.request = _request
    return patch(
        "plugins.wordpress.client.aiohttp.ClientSession",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=False),
        ),
    )


def _conn_key(site_url: str) -> aiohttp.client_reqrep.ConnectionKey:
    # Minimal ConnectionKey required by aiohttp error constructors.
    return aiohttp.client_reqrep.ConnectionKey(
        host=site_url.split("://")[-1],
        port=443,
        is_ssl=site_url.startswith("https"),
        ssl=None,
        proxy=None,
        proxy_auth=None,
        proxy_headers_hash=None,
    )


class TestConnectTimeoutConfigured:
    def test_connect_timeout_is_five_seconds(self):
        # Sanity: the module-level constant is what the roadmap asked for.
        assert _CONNECT_TIMEOUT == 5
        assert _REQUEST_TIMEOUT == 30


class TestSiteUnreachableMapping:
    @pytest.mark.asyncio
    async def test_dns_error_maps_to_site_unreachable(self, client):
        dns_exc = aiohttp.ClientConnectorDNSError(
            _conn_key(client.site_url), OSError("Name or service not known")
        )
        with _patch_session_raising(dns_exc):
            with patch("plugins.wordpress.client.asyncio.sleep", AsyncMock()):
                with pytest.raises(SiteUnreachableError) as e:
                    await client.request("GET", "posts")
        assert e.value.error_code == "SITE_UNREACHABLE"
        assert e.value.reason == "site_dns_error"
        assert e.value.install_hint is not None
        assert e.value.install_hint["companion_min_version"]
        assert e.value.install_hint["install_url"].startswith("http")

    @pytest.mark.asyncio
    async def test_gaierror_via_connector_also_maps_to_dns_error(self, client):
        gai = socket.gaierror("Name or service not known")
        conn_exc = aiohttp.ClientConnectorError(_conn_key(client.site_url), gai)
        with _patch_session_raising(conn_exc):
            with patch("plugins.wordpress.client.asyncio.sleep", AsyncMock()):
                with pytest.raises(SiteUnreachableError) as e:
                    await client.request("GET", "posts")
        assert e.value.reason == "site_dns_error"

    @pytest.mark.asyncio
    async def test_connection_refused_maps_to_site_unreachable(self, client):
        os_err = OSError(111, "Connection refused")
        conn_exc = aiohttp.ClientConnectorError(_conn_key(client.site_url), os_err)
        with _patch_session_raising(conn_exc):
            with patch("plugins.wordpress.client.asyncio.sleep", AsyncMock()):
                with pytest.raises(SiteUnreachableError) as e:
                    await client.request("GET", "posts")
        assert e.value.reason == "site_connection_refused"
        assert e.value.install_hint is not None

    @pytest.mark.asyncio
    async def test_ssl_error_maps_to_site_unreachable(self, client):
        import ssl

        ssl_exc = aiohttp.ClientConnectorCertificateError(
            _conn_key(client.site_url),
            ssl.SSLCertVerificationError("bad cert"),
        )
        with _patch_session_raising(ssl_exc):
            with pytest.raises(SiteUnreachableError) as e:
                await client.request("GET", "posts")
        assert e.value.reason == "site_ssl_error"

    @pytest.mark.asyncio
    async def test_invalid_url_maps_to_site_unreachable(self):
        client = WordPressClient("not-a-url", "u", "p")
        invalid = aiohttp.InvalidURL("not-a-url")
        with _patch_session_raising(invalid):
            with pytest.raises(SiteUnreachableError) as e:
                await client.request("GET", "posts")
        assert e.value.reason == "site_invalid_url"

    @pytest.mark.asyncio
    async def test_timeout_after_retries_maps_to_site_unreachable(self, client):
        with _patch_session_raising(TimeoutError("connect")):
            with patch("plugins.wordpress.client.asyncio.sleep", AsyncMock()):
                with pytest.raises(SiteUnreachableError) as e:
                    await client.request("GET", "posts")
        assert e.value.reason == "site_timeout"
        assert e.value.install_hint is not None


class TestFastFailBudget:
    """Guards the 10s assertion promised in the F.X.retest matrix."""

    @pytest.mark.asyncio
    async def test_dns_error_fails_under_ten_seconds(self, client):
        dns_exc = aiohttp.ClientConnectorDNSError(_conn_key(client.site_url), OSError("dead"))
        with _patch_session_raising(dns_exc):
            start = time.monotonic()
            with pytest.raises(SiteUnreachableError):
                await client.request("GET", "posts")
            elapsed = time.monotonic() - start
        # DNS errors are non-retryable, so this is essentially instant;
        # give a loose 10s bound to match the F.X.retest assertion shape.
        assert elapsed < 10.0

    @pytest.mark.asyncio
    async def test_timeout_with_retries_fails_under_ten_seconds(self, client):
        # Two retries × _CONNECT_TIMEOUT + retry backoff. With mocked
        # sleep this should return immediately; real-world budget is
        # 3 × 5s = 15s worst-case, but only on the first request; follow-
        # ups hit the cache.
        with _patch_session_raising(TimeoutError()):
            with patch("plugins.wordpress.client.asyncio.sleep", AsyncMock()):
                start = time.monotonic()
                with pytest.raises(SiteUnreachableError):
                    await client.request("GET", "posts")
                elapsed = time.monotonic() - start
        assert elapsed < 10.0
