"""F.18.7 — Companion audit-hook receiver + per-site secret store.

The ``airano-mcp-bridge`` companion plugin (v2.7.0+) pushes WordPress
action events (post transitions, user events, plugin activations, etc.)
to MCPHub as HMAC-SHA256-signed webhooks. This module provides:

1. ``CompanionAuditSecretStore`` — file-backed map of ``site_url -> secret``.
2. ``verify_companion_signature`` — constant-time HMAC verification.
3. ``handle_companion_audit_request`` — Starlette handler that validates
   the signature, appends the event to the audit log, and returns 200.

The store is intentionally independent of the SQLite sites DB so the
webhook can land before a dashboard UI exists; the UI (future work) can
replace ``CompanionAuditSecretStore`` with DB-backed storage without
changing the wire format.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("mcphub.companion_audit")


def _parse_timestamp(raw: Any) -> float | None:
    """Coerce the envelope ``timestamp`` field to epoch seconds.

    Accepts either an ISO 8601 string (``2026-04-15T09:00:00Z`` — the
    companion plugin's current format via PHP ``gmdate``) or a numeric
    epoch value (for forward compatibility with other senders).
    Returns None on any parse failure so callers can emit a uniform
    401 without leaking which step failed.
    """
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return float(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        # Python 3.11+ fromisoformat handles "Z" suffix; on older
        # versions we translate it to +00:00 explicitly.
        iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
        try:
            return datetime.fromisoformat(iso).timestamp()
        except ValueError:
            pass
        # Numeric-string fallback (e.g. "1712345678").
        try:
            return float(s)
        except ValueError:
            return None
    return None


# Pre-F.20 security sweep: bound incoming payload so a misconfigured
# (or malicious) companion can't queue up unbounded memory with a
# single request. Real audit events are well under 4 KB; 64 KB is a
# generous ceiling that still fits within Starlette's default limit.
_MAX_BODY_BYTES = int(os.environ.get("COMPANION_AUDIT_MAX_BODY", str(64 * 1024)))

# Replay-protection window (seconds). Events whose ``timestamp`` field
# falls outside ``now ± _REPLAY_WINDOW_SECONDS`` are rejected with 401.
# Set to 0 or negative to disable (not recommended). Default 5 minutes
# balances clock-skew tolerance against replay risk.
_REPLAY_WINDOW_SECONDS = int(os.environ.get("COMPANION_AUDIT_REPLAY_WINDOW", "300"))


def _normalise_url(url: str) -> str:
    return url.rstrip("/").strip().lower()


class CompanionAuditSecretStore:
    """File-backed ``site_url -> shared_secret`` map.

    The file is JSON; keys are normalised (lowercased, trailing slash
    stripped). Access is serialised through a lock to keep reads and
    writes atomic on a single-process server. Multi-process deployments
    (gunicorn workers) can still race on the write path — that's fine
    because the dashboard UI will be the only writer and operates in
    the master process for this MVP.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._cache: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {}
            return self._cache
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                logger.warning(
                    "companion audit secret file %s is not a JSON object; ignoring.",
                    self.path,
                )
                self._cache = {}
            else:
                self._cache = {_normalise_url(str(k)): str(v) for k, v in data.items() if v}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read companion audit secret file %s: %s", self.path, exc)
            self._cache = {}
        return self._cache

    def _save(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        self._cache = dict(data)

    def get(self, site_url: str) -> str | None:
        with self._lock:
            return self._load().get(_normalise_url(site_url))

    def set(self, site_url: str, secret: str) -> None:
        if not secret or len(secret) < 16:
            raise ValueError("companion audit secret must be at least 16 characters")
        with self._lock:
            data = dict(self._load())
            data[_normalise_url(site_url)] = secret
            self._save(data)

    def delete(self, site_url: str) -> bool:
        with self._lock:
            data = dict(self._load())
            key = _normalise_url(site_url)
            if key not in data:
                return False
            del data[key]
            self._save(data)
            return True

    def list_sites(self) -> list[dict[str, Any]]:
        """List sites with secret metadata only — never returns plaintext."""
        with self._lock:
            return [
                {
                    "site_url": site_url,
                    "secret_set": True,
                    "secret_last4": secret[-4:] if len(secret) >= 4 else "",
                }
                for site_url, secret in self._load().items()
            ]


_DEFAULT_STORE_PATH = Path(
    os.environ.get(
        "COMPANION_AUDIT_SECRETS_PATH",
        "/tmp/mcphub-data/companion-audit-secrets.json",
    )
)
_default_store: CompanionAuditSecretStore | None = None


def get_companion_audit_store(
    path: str | Path | None = None,
) -> CompanionAuditSecretStore:
    global _default_store
    if path is not None:
        return CompanionAuditSecretStore(path)
    if _default_store is None:
        _default_store = CompanionAuditSecretStore(_DEFAULT_STORE_PATH)
    return _default_store


def verify_companion_signature(
    body_bytes: bytes, signature_header: str | None, secret: str
) -> bool:
    """Constant-time HMAC-SHA256 verification.

    Accepts the PHP side's ``sha256=HEX`` format and a bare-hex variant.
    Returns False on any shape error so callers can emit 401 uniformly.
    """
    if not signature_header or not secret:
        return False
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig[len("sha256=") :]
    if not sig or not all(c in "0123456789abcdefABCDEF" for c in sig):
        return False
    expected = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), sig.lower())


# Accepted event names — mirror the PHP side. Events outside this list
# are still accepted but tagged so operators can spot rogue sources.
_KNOWN_EVENTS = frozenset(
    {
        "transition_post_status",
        "deleted_post",
        "user_register",
        "profile_update",
        "deleted_user",
        "activated_plugin",
        "deactivated_plugin",
        "switch_theme",
    }
)


async def handle_companion_audit_request(request: Request) -> JSONResponse:
    """Starlette handler for ``POST /api/companion-audit``.

    Validates the HMAC signature using a per-site secret, parses the
    envelope, applies a replay window on the ``timestamp`` field, and
    writes an audit-log entry. Returns 200 on success, 400 on shape
    errors, 401 on signature/replay failure, 413 on oversized body.
    """
    # Pre-F.20 security sweep: bound the incoming body before reading the
    # whole thing. Prefer the framework's Content-Length hint; fall back
    # to reading up to one byte past the ceiling so we can cleanly 413.
    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            content_length = int(content_length_header)
        except ValueError:
            return JSONResponse({"ok": False, "error": "invalid_length"}, status_code=400)
        if content_length > _MAX_BODY_BYTES:
            return JSONResponse(
                {"ok": False, "error": "body_too_large", "max_bytes": _MAX_BODY_BYTES},
                status_code=413,
            )

    # Read raw body — we need the exact bytes for HMAC verification.
    body_bytes = await request.body()
    if len(body_bytes) > _MAX_BODY_BYTES:
        return JSONResponse(
            {"ok": False, "error": "body_too_large", "max_bytes": _MAX_BODY_BYTES},
            status_code=413,
        )
    if not body_bytes:
        return JSONResponse({"ok": False, "error": "empty_body"}, status_code=400)

    site_header = request.headers.get("X-Airano-MCP-Site") or ""
    signature = request.headers.get("X-Airano-MCP-Signature")

    try:
        envelope = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    if not isinstance(envelope, dict):
        return JSONResponse({"ok": False, "error": "invalid_envelope"}, status_code=400)

    site_url = str(envelope.get("site_url") or site_header or "")
    if not site_url:
        return JSONResponse({"ok": False, "error": "missing_site"}, status_code=400)

    store = get_companion_audit_store()
    secret = store.get(site_url)
    if secret is None:
        # Don't leak whether the site exists; same response as a bad sig.
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    if not verify_companion_signature(body_bytes, signature, secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    # Pre-F.20 security sweep: enforce a replay window on the signed
    # timestamp. Captured webhooks replayed outside the window are
    # rejected with 401 (same opaque response as a bad signature to
    # avoid giving attackers a distinguishing oracle).
    if _REPLAY_WINDOW_SECONDS > 0:
        ts = _parse_timestamp(envelope.get("timestamp"))
        if ts is None:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        now = time.time()
        if abs(now - ts) > _REPLAY_WINDOW_SECONDS:
            logger.warning(
                "companion audit replay rejected site=%s skew=%.1fs",
                site_url,
                now - ts,
            )
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    event_name = str(envelope.get("event") or "unknown")
    details = {
        "site_url": site_url,
        "event": event_name,
        "known_event": event_name in _KNOWN_EVENTS,
        "timestamp": envelope.get("timestamp"),
        "wp_user_id": envelope.get("user_id"),
        "plugin_version": envelope.get("plugin_version"),
        "data": envelope.get("data"),
    }

    try:
        # Deferred import — avoid pulling audit_log into the store for tests.
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        audit_logger.log_system_event(
            event=f"companion_audit:{event_name}",
            details=details,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("failed to append companion audit event: %s", exc)
        return JSONResponse(
            {"ok": False, "error": "audit_write_failed"},
            status_code=500,
        )

    return JSONResponse({"ok": True, "event": event_name}, status_code=200)
