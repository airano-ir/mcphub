"""MCP protocol-version handling for the hand-rolled per-user endpoint.

``/u/{user_id}/{alias}/mcp`` is a *dual-era* server (spec 2026-07-28,
"Versioning and Compatibility"):

* **Legacy** clients (``2025-11-25`` and earlier) open with ``initialize``.
  The server MUST answer with the requested version when it supports it,
  otherwise with another supported version — the latest one.
* **Modern** clients (``2026-07-28``) send no handshake: every request
  declares ``_meta["io.modelcontextprotocol/protocolVersion"]`` (and the
  ``MCP-Protocol-Version`` header on HTTP). Unsupported versions get
  ``UnsupportedProtocolVersionError`` (-32022) listing what is supported.
  Results carry ``resultType: "complete"`` and the server identity in
  ``_meta``; list results add the ``ttlMs`` / ``cacheScope`` cache hints.
  ``server/discover`` MUST be implemented.

The tool payloads themselves (name / title / description / inputSchema /
annotations, and content arrays) are valid in every listed version.
"""

from __future__ import annotations

from typing import Any

MODERN_VERSIONS: tuple[str, ...] = ("2026-07-28",)
LEGACY_VERSIONS: tuple[str, ...] = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SUPPORTED_VERSIONS: tuple[str, ...] = MODERN_VERSIONS + LEGACY_VERSIONS
LATEST_LEGACY = LEGACY_VERSIONS[0]

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
HEADER_PROTOCOL_VERSION = "mcp-protocol-version"

UNSUPPORTED_PROTOCOL_VERSION = -32022

# tools/list for a user endpoint depends on the caller's key scopes and the
# site's toggles, so it must never be cached by shared intermediaries.
TOOLS_LIST_TTL_MS = 300_000
DISCOVER_TTL_MS = 3_600_000


def negotiate_legacy_version(requested: Any) -> str:
    """Version to answer a legacy ``initialize`` with."""
    if isinstance(requested, str) and requested in LEGACY_VERSIONS:
        return requested
    return LATEST_LEGACY


def declared_version(params: Any, headers: Any = None) -> str | None:
    """Protocol version declared by a request (``_meta`` first, then header)."""
    if isinstance(params, dict):
        meta = params.get("_meta")
        if isinstance(meta, dict):
            value = meta.get(META_PROTOCOL_VERSION)
            if isinstance(value, str) and value:
                return value
    if headers is not None:
        value = headers.get(HEADER_PROTOCOL_VERSION)
        if value:
            return str(value).strip()
    return None


def is_modern(version: str | None) -> bool:
    return version in MODERN_VERSIONS


def unsupported_version_error(req_id: Any, requested: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": UNSUPPORTED_PROTOCOL_VERSION,
            "message": "Unsupported protocol version",
            "data": {"supported": list(SUPPORTED_VERSIONS), "requested": requested},
        },
    }


def decorate_modern_result(
    result: dict[str, Any], server_info: dict[str, str], *, ttl_ms: int | None = None
) -> dict[str, Any]:
    """Add the fields a 2026-07-28 result must/should carry."""
    out = dict(result)
    out["resultType"] = "complete"
    meta = dict(out.get("_meta") or {})
    meta[META_SERVER_INFO] = server_info
    out["_meta"] = meta
    if ttl_ms is not None:
        out["ttlMs"] = ttl_ms
        out["cacheScope"] = "private"
    return out


def discover_result(server_info: dict[str, str], instructions: str | None = None) -> dict[str, Any]:
    """``server/discover`` result (always in modern form)."""
    result: dict[str, Any] = {
        "supportedVersions": list(SUPPORTED_VERSIONS),
        "capabilities": {"tools": {}},
    }
    if instructions:
        result["instructions"] = instructions
    return decorate_modern_result(result, server_info, ttl_ms=DISCOVER_TTL_MS)
