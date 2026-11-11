"""Short-lived, session-scoped browser upload tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any


def _secret() -> bytes:
    value = os.environ.get("MCPHUB_UPLOAD_TOKEN_SECRET") or os.environ.get(
        "DASHBOARD_SESSION_SECRET"
    )
    if not value:
        value = secrets.token_urlsafe(32)
        os.environ["MCPHUB_UPLOAD_TOKEN_SECRET"] = value
    return value.encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_upload_token(
    session_id: str,
    *,
    owner: str,
    site_id: str | None = None,
    alias: str | None = None,
    ttl_seconds: int = 900,
) -> str:
    """Issue a bearer token for exactly one upload session and operation."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sid": session_id,
        "owner": owner,
        "op": "media_upload",
        "iat": now,
        "exp": now + max(1, min(ttl_seconds, 3600)),
        "jti": secrets.token_urlsafe(12),
    }
    if site_id:
        payload["site_id"] = site_id
    if alias:
        payload["alias"] = alias
    body = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _encode(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"mup_{body}.{signature}"


def validate_upload_token(
    token: str,
    session_id: str,
    *,
    owner: str | None = None,
) -> dict[str, Any]:
    """Validate signature, expiry, operation, and optionally the owner."""
    try:
        token = token.removeprefix("mup_")
        body, signature = token.split(".", 1)
        expected = _encode(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid upload token")
        payload = json.loads(_decode(body))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid upload token") from exc

    if payload.get("op") != "media_upload":
        raise ValueError("Invalid upload token operation")
    if payload.get("sid") != session_id or (owner is not None and payload.get("owner") != owner):
        raise ValueError("Upload token is not scoped to this session")
    if int(payload.get("exp", 0)) <= int(time.time()):
        raise ValueError("Upload token expired")
    return payload


def upload_token_ttl_seconds() -> int:
    """Return the configured browser-token lifetime, capped by the issuer."""
    try:
        return max(1, min(int(os.environ.get("MCPHUB_UPLOAD_TOKEN_TTL_SEC", "900")), 3600))
    except ValueError:
        return 900
