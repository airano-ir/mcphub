"""Outbound network guard against SSRF for user-controlled destinations.

Every site URL in the hub comes from a dashboard user (OAuth signup is open),
so any HTTP request whose destination host derives from that URL must not be
able to reach the hub's own network: loopback, RFC 1918, link-local / cloud
metadata, CGNAT / Tailscale (``100.64.0.0/10``), unique-local IPv6, and so on.

A pre-flight check of the URL alone is not enough, because the destination can
change after the check:

* **HTTP redirects** — aiohttp follows them by default, so a public site that
  answers ``302 Location: http://127.0.0.1:…`` reaches the internal target.
* **DNS rebinding** — the host resolves to a public IP during the check and to
  a private IP when the real request connects.

This module enforces the policy at connection time instead:

* :class:`GuardedResolver` drops disallowed addresses from every DNS answer the
  connector uses, so rebinding and redirects to *hostnames* are covered.
* Trace hooks reject *IP-literal* destinations on the first hop and on every
  redirect hop (aiohttp does not call the resolver for IP literals).

Use :func:`client_session` wherever a request targets a user-supplied site.
It returns a guarded session unless private destinations are explicitly
allowed — either globally by the operator (``ALLOW_PRIVATE_SITE_URLS=true``,
for self-hosters whose services live on the hub's internal network) or for the
current request via :func:`allow_private_destinations` (used for admin-owned
sites, mirroring the existing admin exemptions from rate and site limits).
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import aiohttp
from aiohttp.abc import AbstractResolver
from yarl import URL

ENV_ALLOW_PRIVATE = "ALLOW_PRIVATE_SITE_URLS"

# Hostnames that must never be contacted even if DNS says otherwise.
_BLOCKED_HOSTNAMES = frozenset({"localhost", "metadata", "metadata.google.internal"})

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

_private_override: ContextVar[bool] = ContextVar("net_guard_private_override", default=False)


class SSRFBlockedError(aiohttp.ClientConnectionError):
    """A request destination was rejected by the SSRF guard.

    Subclasses :class:`aiohttp.ClientConnectionError` so generic network
    error handling still applies, but it is *not* an ``OSError``: aiohttp
    therefore propagates it unchanged instead of wrapping it as a DNS error,
    and callers can tell it apart (it must never be retried).
    """

    def __init__(self, message: str, *, host: str | None = None, ip: str | None = None):
        super().__init__(message)
        self.message = message
        self.host = host
        self.ip = ip

    def __str__(self) -> str:
        return self.message


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------


def _env_allows_private() -> bool:
    return os.getenv(ENV_ALLOW_PRIVATE, "false").strip().lower() in ("1", "true", "yes")


def private_destinations_allowed() -> bool:
    """Whether the current context may contact private/internal addresses."""
    return _env_allows_private() or _private_override.get()


@contextmanager
def allow_private_destinations(enabled: bool = True) -> Iterator[None]:
    """Allow (or explicitly keep blocking) private destinations in this context.

    Context variables are copied into tasks created inside the block, so the
    decision follows the request's own work but never leaks to other requests.
    """
    token = _private_override.set(bool(enabled))
    try:
        yield
    finally:
        _private_override.reset(token)


def is_disallowed_ip(ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if ``ip`` is not a public, unicast, globally routable address.

    IPv4-mapped IPv6 addresses (``::ffff:127.0.0.1``) are judged by the IPv4
    address they map to, independent of the running Python's ``ipaddress``
    version quirks. Unparseable input is treated as disallowed.
    """
    if isinstance(ip, str):
        try:
            ip = ipaddress.ip_address(ip)
        except ValueError:
            return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _literal_ip(host: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not host:
        return None
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def check_destination(url: str | URL) -> None:
    """Raise :class:`SSRFBlockedError` if ``url`` is an obviously bad target.

    Cheap, DNS-free check used on every hop: scheme, blocked hostnames and
    IP-literal hosts. Hostnames are enforced at connect time by
    :class:`GuardedResolver`.
    """
    u = url if isinstance(url, URL) else URL(str(url))
    if u.scheme not in ("http", "https"):
        raise SSRFBlockedError(f"Scheme '{u.scheme}' is not allowed", host=u.raw_host)
    host = (u.raw_host or "").lower().rstrip(".")
    if not host:
        raise SSRFBlockedError("URL has no host")
    if host in _BLOCKED_HOSTNAMES:
        raise SSRFBlockedError(f"Host '{host}' is not allowed", host=host)
    ip = _literal_ip(host)
    if ip is not None and is_disallowed_ip(ip):
        raise SSRFBlockedError(
            f"Destination {ip} is a private or internal address", host=host, ip=str(ip)
        )


# --------------------------------------------------------------------------
# Connection-time enforcement
# --------------------------------------------------------------------------


class GuardedResolver(AbstractResolver):
    """DNS resolver that never returns private/internal addresses.

    Wraps aiohttp's thread-pool resolver (holds no resources, so one per
    session is cheap and needs no explicit close); disallowed addresses are
    filtered out of every answer. If nothing public remains the lookup fails
    with :class:`SSRFBlockedError`, so the connector never opens a socket to
    an internal host — whether the name was the original URL, a redirect
    target, or a rebinding answer.
    """

    def __init__(self, inner: AbstractResolver | None = None) -> None:
        self._inner = inner if inner is not None else aiohttp.ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[Any]:
        name = host.lower().rstrip(".")
        if name in _BLOCKED_HOSTNAMES:
            raise SSRFBlockedError(f"Host '{name}' is not allowed", host=name)
        answers = await self._inner.resolve(host, port, family)
        allowed = [a for a in answers if not is_disallowed_ip(str(a.get("host", "")))]
        if not allowed:
            first = str(answers[0].get("host")) if answers else None
            raise SSRFBlockedError(
                f"Host '{host}' resolves to a private or internal address",
                host=host,
                ip=first,
            )
        return allowed

    async def close(self) -> None:
        await self._inner.close()


async def _on_request_start(
    session: aiohttp.ClientSession, ctx: Any, params: aiohttp.TraceRequestStartParams
) -> None:
    check_destination(params.url)


async def _on_request_redirect(
    session: aiohttp.ClientSession, ctx: Any, params: aiohttp.TraceRequestRedirectParams
) -> None:
    response = params.response
    if response.status not in _REDIRECT_STATUSES:
        return
    location = response.headers.get("Location") or response.headers.get("URI")
    if not location:
        return
    try:
        target = URL(location)
    except ValueError as exc:
        raise SSRFBlockedError(f"Invalid redirect target: {location!r}") from exc
    if not target.is_absolute():
        target = params.url.join(target)
    check_destination(target)


def _guard_trace_config() -> aiohttp.TraceConfig:
    trace = aiohttp.TraceConfig()
    trace.on_request_start.append(_on_request_start)
    trace.on_request_redirect.append(_on_request_redirect)
    return trace


def guarded_session(**kwargs: Any) -> aiohttp.ClientSession:
    """Return an ``aiohttp.ClientSession`` that refuses internal destinations.

    Accepts the usual ``ClientSession`` keyword arguments except ``connector``
    (the guard owns the connector).
    """
    if "connector" in kwargs:
        raise TypeError("guarded_session() manages its own connector")
    trace_configs = list(kwargs.pop("trace_configs", None) or [])
    trace_configs.append(_guard_trace_config())
    connector = aiohttp.TCPConnector(resolver=GuardedResolver())
    return aiohttp.ClientSession(connector=connector, trace_configs=trace_configs, **kwargs)


def client_session(**kwargs: Any) -> aiohttp.ClientSession:
    """Session factory for requests to user-supplied destinations.

    Guarded by default; a plain session only when private destinations are
    allowed for this context (operator env flag or an admin-owned site).
    """
    if private_destinations_allowed():
        return aiohttp.ClientSession(**kwargs)
    return guarded_session(**kwargs)
