"""F.18.7 — Tests for the companion-audit receiver + secret store."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request

from core.companion_audit import (
    CompanionAuditSecretStore,
    _parse_timestamp,
    handle_companion_audit_request,
    verify_companion_signature,
)

SITE = "https://wp.example.com"
SECRET = "a" * 32


def _now_iso() -> str:
    """Return an ISO 8601 UTC timestamp matching the companion plugin's format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_request(body_bytes: bytes, headers: dict[str, str]) -> Request:
    """Construct a minimal Starlette Request from a body + headers."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/companion-audit",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "query_string": b"",
    }

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    return Request(scope, receive)


# ---------------------------------------------------------------------------
# Signature verification.
# ---------------------------------------------------------------------------


def test_verify_signature_accepts_sha256_prefix():
    body = b'{"hi":1}'
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert verify_companion_signature(body, f"sha256={sig}", SECRET) is True


def test_verify_signature_accepts_bare_hex():
    body = b'{"hi":1}'
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert verify_companion_signature(body, sig, SECRET) is True


def test_verify_signature_rejects_wrong_secret():
    body = b'{"hi":1}'
    sig = hmac.new(b"other_secret_1234", body, hashlib.sha256).hexdigest()
    assert verify_companion_signature(body, f"sha256={sig}", SECRET) is False


def test_verify_signature_rejects_missing_header():
    assert verify_companion_signature(b"x", None, SECRET) is False
    assert verify_companion_signature(b"x", "", SECRET) is False


def test_verify_signature_rejects_non_hex():
    assert verify_companion_signature(b"x", "sha256=NOTHEX!", SECRET) is False


# ---------------------------------------------------------------------------
# Secret store.
# ---------------------------------------------------------------------------


def test_store_set_and_get(tmp_path: Path):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    assert store.get(SITE) == SECRET
    # Normalisation: trailing slash + case should not matter.
    assert store.get(SITE + "/") == SECRET
    assert store.get(SITE.upper()) == SECRET


def test_store_rejects_short_secret(tmp_path: Path):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    with pytest.raises(ValueError):
        store.set(SITE, "short")


def test_store_delete(tmp_path: Path):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    assert store.delete(SITE) is True
    assert store.get(SITE) is None
    assert store.delete(SITE) is False


def test_store_list_sites_masks_secret(tmp_path: Path):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    sites = store.list_sites()
    assert len(sites) == 1
    assert sites[0]["site_url"].lower().startswith("https://wp.example.com")
    assert sites[0]["secret_set"] is True
    assert sites[0]["secret_last4"] == SECRET[-4:]
    assert "secret" not in sites[0]  # never leaks plaintext


def test_store_survives_restart(tmp_path: Path):
    path = tmp_path / "secrets.json"
    store1 = CompanionAuditSecretStore(path)
    store1.set(SITE, SECRET)

    store2 = CompanionAuditSecretStore(path)
    assert store2.get(SITE) == SECRET


def test_store_corrupt_file_treated_as_empty(tmp_path: Path):
    path = tmp_path / "secrets.json"
    path.write_text("not json")
    store = CompanionAuditSecretStore(path)
    assert store.get(SITE) is None


# ---------------------------------------------------------------------------
# Receiver Starlette handler.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_receiver_rejects_empty_body():
    req = _build_request(b"", {})
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_receiver_rejects_invalid_json():
    req = _build_request(b"not json", {"X-Airano-MCP-Site": SITE})
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_receiver_rejects_missing_site(tmp_path: Path):
    body = json.dumps({"event": "x"}).encode()
    req = _build_request(body, {})
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_receiver_unauthorized_when_unknown_site(tmp_path: Path, monkeypatch):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)
    body = json.dumps({"event": "x", "site_url": "https://unknown.example"}).encode()
    req = _build_request(body, {"X-Airano-MCP-Signature": "sha256=deadbeef"})
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_receiver_unauthorized_on_bad_signature(tmp_path: Path, monkeypatch):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)
    body = json.dumps({"event": "x", "site_url": SITE}).encode()
    req = _build_request(
        body,
        {
            "X-Airano-MCP-Site": SITE,
            "X-Airano-MCP-Signature": "sha256=" + "0" * 64,
        },
    )
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_receiver_happy_path(tmp_path: Path, monkeypatch):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)

    envelope = {
        "event": "transition_post_status",
        "site_url": SITE,
        "timestamp": _now_iso(),
        "user_id": 1,
        "data": {"post_id": 42, "new_status": "publish", "old_status": "draft"},
        "plugin_version": "2.7.0",
    }
    body = json.dumps(envelope).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    fake_logger = MagicMock()
    with patch("core.audit_log.get_audit_logger", return_value=fake_logger):
        req = _build_request(
            body,
            {
                "X-Airano-MCP-Site": SITE,
                "X-Airano-MCP-Signature": f"sha256={sig}",
                "Content-Type": "application/json",
            },
        )
        resp = await handle_companion_audit_request(req)

    assert resp.status_code == 200
    fake_logger.log_system_event.assert_called_once()
    call_args = fake_logger.log_system_event.call_args
    assert call_args.kwargs["event"] == "companion_audit:transition_post_status"
    details = call_args.kwargs["details"]
    assert details["site_url"] == SITE
    assert details["known_event"] is True
    assert details["data"]["post_id"] == 42


@pytest.mark.asyncio
async def test_receiver_tags_unknown_events(tmp_path: Path, monkeypatch):
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)

    envelope = {"event": "made_up_event", "site_url": SITE, "timestamp": _now_iso()}
    body = json.dumps(envelope).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    fake_logger = MagicMock()
    with patch("core.audit_log.get_audit_logger", return_value=fake_logger):
        req = _build_request(
            body,
            {
                "X-Airano-MCP-Site": SITE,
                "X-Airano-MCP-Signature": f"sha256={sig}",
            },
        )
        resp = await handle_companion_audit_request(req)

    assert resp.status_code == 200
    details = fake_logger.log_system_event.call_args.kwargs["details"]
    assert details["known_event"] is False


# ---------------------------------------------------------------------------
# Pre-F.20 security sweep: body-size cap + replay window + timestamp parsing.
# ---------------------------------------------------------------------------


def test_parse_timestamp_iso_8601_z_suffix():
    iso = "2026-04-15T09:00:00Z"
    ts = _parse_timestamp(iso)
    assert ts is not None
    # Round-trip: same moment in epoch seconds.
    assert abs(ts - datetime(2026, 4, 15, 9, 0, 0, tzinfo=UTC).timestamp()) < 1


def test_parse_timestamp_numeric_epoch():
    assert _parse_timestamp(1712345678) == 1712345678.0
    assert _parse_timestamp(1712345678.5) == 1712345678.5


def test_parse_timestamp_numeric_string():
    assert _parse_timestamp("1712345678") == 1712345678.0


def test_parse_timestamp_rejects_garbage():
    assert _parse_timestamp("not a date") is None
    assert _parse_timestamp(None) is None
    assert _parse_timestamp("") is None
    assert _parse_timestamp({"not": "a timestamp"}) is None


@pytest.mark.asyncio
async def test_receiver_rejects_oversized_body_via_content_length():
    # Content-Length > cap → 413 before we even read the body.
    req = _build_request(
        b'{"event":"x"}',
        {
            "X-Airano-MCP-Site": SITE,
            "Content-Length": str(1_000_000),
        },
    )
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 413
    body = json.loads(bytes(resp.body))
    assert body["error"] == "body_too_large"


@pytest.mark.asyncio
async def test_receiver_rejects_oversized_body_via_actual_length(monkeypatch):
    # If Content-Length is absent but the body itself exceeds the cap,
    # we still return 413 after the read.
    monkeypatch.setattr("core.companion_audit._MAX_BODY_BYTES", 32)
    big = b"x" * 64
    req = _build_request(big, {"X-Airano-MCP-Site": SITE})
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_receiver_rejects_missing_timestamp(tmp_path: Path, monkeypatch):
    """Signed but timestamp-less envelope: rejected as if sig were bad."""
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)

    envelope = {"event": "transition_post_status", "site_url": SITE}
    body = json.dumps(envelope).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    req = _build_request(
        body,
        {
            "X-Airano-MCP-Site": SITE,
            "X-Airano-MCP-Signature": f"sha256={sig}",
        },
    )
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_receiver_rejects_stale_timestamp(tmp_path: Path, monkeypatch):
    """Valid sig but timestamp outside the replay window → 401."""
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)

    stale = datetime.fromtimestamp(time.time() - 3600, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    envelope = {"event": "transition_post_status", "site_url": SITE, "timestamp": stale}
    body = json.dumps(envelope).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    req = _build_request(
        body,
        {
            "X-Airano-MCP-Site": SITE,
            "X-Airano-MCP-Signature": f"sha256={sig}",
        },
    )
    resp = await handle_companion_audit_request(req)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_receiver_accepts_future_timestamp_within_skew(tmp_path: Path, monkeypatch):
    """Small positive clock skew (server drifted ahead of WP) is tolerated."""
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)

    # +30 s is well inside the default 300 s window.
    skewed = datetime.fromtimestamp(time.time() + 30, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    envelope = {"event": "transition_post_status", "site_url": SITE, "timestamp": skewed}
    body = json.dumps(envelope).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    fake_logger = MagicMock()
    with patch("core.audit_log.get_audit_logger", return_value=fake_logger):
        req = _build_request(
            body,
            {
                "X-Airano-MCP-Site": SITE,
                "X-Airano-MCP-Signature": f"sha256={sig}",
            },
        )
        resp = await handle_companion_audit_request(req)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_receiver_replay_window_disabled(tmp_path: Path, monkeypatch):
    """Setting the window to 0 turns replay protection off."""
    store = CompanionAuditSecretStore(tmp_path / "secrets.json")
    store.set(SITE, SECRET)
    monkeypatch.setattr("core.companion_audit.get_companion_audit_store", lambda: store)
    monkeypatch.setattr("core.companion_audit._REPLAY_WINDOW_SECONDS", 0)

    ancient = "2020-01-01T00:00:00Z"
    envelope = {"event": "transition_post_status", "site_url": SITE, "timestamp": ancient}
    body = json.dumps(envelope).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    fake_logger = MagicMock()
    with patch("core.audit_log.get_audit_logger", return_value=fake_logger):
        req = _build_request(
            body,
            {
                "X-Airano-MCP-Site": SITE,
                "X-Airano-MCP-Signature": f"sha256={sig}",
            },
        )
        resp = await handle_companion_audit_request(req)
    assert resp.status_code == 200
