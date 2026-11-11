"""SSRF guard for outbound requests to user-supplied destinations.

These tests use real local HTTP servers (no mocked sessions) so they exercise
aiohttp's actual redirect and DNS code paths:

* an "internal" server on 127.0.0.1 that must never receive a request;
* a "public" redirector on 127.0.0.2 (treated as public by patching the IP
  predicate) that 302s to the internal server.

They pin the three bypasses found in review of the first SSRF fix
(pre-flight-only): redirect after a passing check, DNS rebinding between
check and connect, and the tool-call path, which had no guard at all.
"""

from __future__ import annotations

import socket
from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import web

from core import net_guard
from core.net_guard import (
    GuardedResolver,
    SSRFBlockedError,
    allow_private_destinations,
    check_destination,
    client_session,
    guarded_session,
    is_disallowed_ip,
    private_destinations_allowed,
)

pytestmark = [pytest.mark.security]

PUBLIC_TEST_IP = "127.0.0.2"


# ---------------------------------------------------------------- helpers


async def _start(app: web.Application, host: str) -> tuple[web.AppRunner, int]:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, 0)
    try:
        await site.start()
    except OSError as exc:  # pragma: no cover - platform without 127.0.0.2
        await runner.cleanup()
        pytest.skip(f"cannot bind {host}: {exc}")
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    return runner, port


@pytest.fixture
async def internal_server() -> AsyncIterator[dict[str, Any]]:
    hits: list[str] = []

    async def handler(request: web.Request) -> web.Response:
        hits.append(request.path_qs)
        if request.path.startswith("/json"):
            return web.json_response({"internal": True, "db_password": "hunter2"})
        return web.Response(status=500, text="INTERNAL-SECRET: db_password=hunter2")

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    runner, port = await _start(app, "127.0.0.1")
    yield {"port": port, "hits": hits, "base": f"http://127.0.0.1:{port}"}
    await runner.cleanup()


@pytest.fixture
async def redirector(internal_server) -> AsyncIterator[dict[str, Any]]:
    """A 'public' server on 127.0.0.2 whose every path redirects inward."""
    state: dict[str, Any] = {"target": f"{internal_server['base']}/secret"}

    async def handler(request: web.Request) -> web.Response:
        if "wp-json" in request.path:
            raise web.HTTPFound(location=state["target"].replace("/secret", "/json"))
        raise web.HTTPFound(location=state["target"])

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    runner, port = await _start(app, PUBLIC_TEST_IP)
    state.update(port=port, base=f"http://{PUBLIC_TEST_IP}:{port}")
    yield state
    await runner.cleanup()


@pytest.fixture
def treat_test_ip_as_public(monkeypatch):
    """Make 127.0.0.2 count as a public address; everything else is real."""
    real = net_guard.is_disallowed_ip

    def fake(ip):
        return False if str(ip) == PUBLIC_TEST_IP else real(ip)

    monkeypatch.setattr(net_guard, "is_disallowed_ip", fake)
    monkeypatch.delenv("ALLOW_PRIVATE_SITE_URLS", raising=False)


class _FakeInnerResolver:
    """Answers every lookup with fixed addresses (simulates DNS rebinding)."""

    def __init__(self, ips: list[str]):
        self.ips = ips

    async def resolve(self, host, port=0, family=socket.AF_INET):
        return [
            {
                "hostname": host,
                "host": ip,
                "port": port,
                "family": socket.AF_INET6 if ":" in ip else socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
            for ip in self.ips
        ]

    async def close(self):
        return None


# ---------------------------------------------------------------- policy


@pytest.mark.unit
@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.17.0.1",  # Docker bridge
        "192.168.1.10",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # CGNAT / Tailscale
        "0.0.0.0",
        "224.0.0.1",  # multicast
        "::1",
        "fc00::1",  # unique local
        "fe80::1",  # link local
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:10.0.0.1",
        "not-an-ip",
    ],
)
def test_internal_addresses_are_disallowed(ip):
    assert is_disallowed_ip(ip) is True


@pytest.mark.unit
@pytest.mark.parametrize("ip", ["93.184.216.34", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(ip):
    assert is_disallowed_ip(ip) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/",
        "http://[::1]/",
        "http://localhost/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "file:///etc/passwd",
        "gopher://example.com/",
    ],
)
def test_check_destination_rejects(url):
    with pytest.raises(SSRFBlockedError):
        check_destination(url)


@pytest.mark.unit
def test_check_destination_allows_public_hostname_and_ip():
    check_destination("https://example.com/wp-json")
    check_destination("http://93.184.216.34/")


@pytest.mark.unit
def test_allow_private_context_is_scoped(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_SITE_URLS", raising=False)
    assert private_destinations_allowed() is False
    with allow_private_destinations(True):
        assert private_destinations_allowed() is True
        with allow_private_destinations(False):
            assert private_destinations_allowed() is False
        assert private_destinations_allowed() is True
    assert private_destinations_allowed() is False


@pytest.mark.unit
def test_env_flag_allows_private(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_SITE_URLS", "true")
    assert private_destinations_allowed() is True


@pytest.mark.unit
def test_guarded_session_refuses_foreign_connector():
    with pytest.raises(TypeError):
        guarded_session(connector=object())


# ---------------------------------------------------------------- resolver


@pytest.mark.unit
async def test_resolver_filters_private_answers():
    resolver = GuardedResolver(inner=_FakeInnerResolver(["10.0.0.7", "93.184.216.34"]))
    answers = await resolver.resolve("mixed.example", 443)
    assert [a["host"] for a in answers] == ["93.184.216.34"]


@pytest.mark.unit
async def test_resolver_rejects_rebinding_to_loopback():
    resolver = GuardedResolver(inner=_FakeInnerResolver(["127.0.0.1"]))
    with pytest.raises(SSRFBlockedError):
        await resolver.resolve("rebind.example", 80)


@pytest.mark.unit
async def test_resolver_rejects_blocked_hostname_without_lookup():
    resolver = GuardedResolver(inner=_FakeInnerResolver(["93.184.216.34"]))
    with pytest.raises(SSRFBlockedError):
        await resolver.resolve("localhost", 80)


# ---------------------------------------------------------------- real HTTP


async def test_direct_internal_literal_is_blocked(internal_server, monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_SITE_URLS", raising=False)
    with pytest.raises(SSRFBlockedError):
        async with client_session() as s, s.get(f"{internal_server['base']}/secret"):
            pass
    assert internal_server["hits"] == []


async def test_redirect_to_internal_literal_is_blocked(
    internal_server, redirector, treat_test_ip_as_public
):
    with pytest.raises(SSRFBlockedError):
        async with client_session() as s, s.get(f"{redirector['base']}/anything"):
            pass
    assert internal_server["hits"] == []


async def test_redirect_to_internal_hostname_is_blocked(
    internal_server, redirector, treat_test_ip_as_public
):
    redirector["target"] = f"http://localhost:{internal_server['port']}/secret"
    with pytest.raises(SSRFBlockedError):
        async with client_session() as s, s.get(f"{redirector['base']}/anything"):
            pass
    assert internal_server["hits"] == []


async def test_dns_rebinding_is_blocked_at_connect(internal_server, monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_SITE_URLS", raising=False)
    # Whatever answered the pre-flight lookup, the connector now gets 127.0.0.1.
    monkeypatch.setattr(
        net_guard.aiohttp, "ThreadedResolver", lambda: _FakeInnerResolver(["127.0.0.1"])
    )
    url = f"http://rebind.attacker.test:{internal_server['port']}/secret"
    with pytest.raises(SSRFBlockedError):
        async with client_session() as s, s.get(url):
            pass
    assert internal_server["hits"] == []


async def test_admin_context_reaches_private_destination(internal_server, monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_SITE_URLS", raising=False)
    with allow_private_destinations(True):
        async with client_session() as s, s.get(f"{internal_server['base']}/json") as resp:
            assert resp.status == 200
    assert internal_server["hits"] == ["/json"]


async def test_public_redirect_chain_still_works(redirector, treat_test_ip_as_public):
    """Redirects between public hosts must keep working (http->https, www)."""
    hits: list[str] = []

    async def final(request: web.Request) -> web.Response:
        hits.append(request.path)
        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_route("GET", "/final", final)
    runner, port = await _start(app, PUBLIC_TEST_IP)
    try:
        redirector["target"] = f"http://{PUBLIC_TEST_IP}:{port}/final"
        async with client_session() as s, s.get(f"{redirector['base']}/start") as resp:
            assert resp.status == 200
            assert (await resp.json()) == {"ok": True}
    finally:
        await runner.cleanup()
    assert hits == ["/final"]


# ------------------------------------------------- the two real call paths


async def test_site_connection_test_blocks_redirect_inward(
    internal_server, redirector, treat_test_ip_as_public
):
    """Bypass #1 from review: the pre-flight passes, the redirect must not."""
    from core.site_api import validate_site_connection

    ok, msg = await validate_site_connection("n8n", redirector["base"], {"api_key": "x"})
    assert ok is False
    assert "not allowed" in msg.lower()
    assert "hunter2" not in msg
    assert internal_server["hits"] == []


async def test_site_connection_test_allows_private_for_admin(internal_server, monkeypatch):
    from core.site_api import validate_site_connection

    monkeypatch.delenv("ALLOW_PRIVATE_SITE_URLS", raising=False)
    ok, msg = await validate_site_connection(
        "n8n", internal_server["base"], {"api_key": "x"}, allow_private=True
    )
    # The internal server answers 500 to everything except /json; reaching it
    # at all is what proves the admin exemption.
    assert ok is False and "HTTP 500" in msg
    assert len(internal_server["hits"]) == 1


async def test_wordpress_tool_call_cannot_be_redirected_inward(
    internal_server, redirector, treat_test_ip_as_public
):
    """Bypass #3 from review: tool calls had no guard and returned the body."""
    from plugins.wordpress.client import SiteUnreachableError, WordPressClient

    client = WordPressClient(redirector["base"], "user", "app-pass")
    with pytest.raises(SiteUnreachableError) as excinfo:
        await client.request("GET", "posts")
    assert excinfo.value.reason == "site_destination_blocked"
    assert "hunter2" not in str(excinfo.value)
    assert internal_server["hits"] == []
