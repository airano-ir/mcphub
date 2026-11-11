"""Small review follow-ups: stale-session cookie name, typed SSRF media error."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

pytestmark = pytest.mark.unit


def _json_request(body: dict) -> Request:
    payload = json.dumps(body).encode()

    async def receive():
        return {"type": "http.request", "body": payload}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/sites",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
    }
    return Request(scope, receive)


async def test_stale_session_clears_the_real_session_cookie():
    """The 'Session expired' path must delete mcp_dashboard_session — it used to
    delete a cookie name that does not exist, so the stale cookie stuck."""
    from core.dashboard import routes

    db = MagicMock()
    db.get_user_by_id = AsyncMock(return_value=None)
    with (
        patch.object(routes, "_require_user_session", return_value=({"user_id": "gone"}, None)),
        patch("core.database.get_database", return_value=db),
    ):
        response = await routes.api_create_site(_json_request({}))
    assert response.status_code == 401
    cookie_header = response.headers.get("set-cookie", "")
    assert "mcp_dashboard_session=" in cookie_header
    assert "mcp_user_session" not in cookie_header


async def test_blocked_redirect_in_media_download_is_a_typed_ssrf_error(monkeypatch):
    from core import net_guard
    from plugins.wordpress.handlers import _media_core
    from plugins.wordpress.handlers._media_security import UploadError

    async def blocked(*_a, **_k):
        raise net_guard.SSRFBlockedError("Destination 127.0.0.1 is a private or internal address")

    monkeypatch.setattr(_media_core, "_fetch_guarded", blocked)
    with pytest.raises(UploadError) as excinfo:
        await _media_core.fetch_url_bytes("https://public.example/redirect")
    assert excinfo.value.code == "SSRF"


# ------------------------------------------------ audit redaction (#135)


def test_redaction_recurses_into_lists_and_tuples():
    from core.audit_log import redact_sensitive

    data = {
        "items": [{"password": "hunter2", "name": "a"}, ("ok", {"api_key": "k"})],
        "nested": {"deep": [{"service_role_key": "eyJx"}]},
        "consumer_key": "ck_0123456789abcdef0123456789abcdef01234567",
    }
    out = redact_sensitive(data)
    assert out["items"][0] == {"password": "[REDACTED]", "name": "a"}
    assert out["items"][1][1] == {"api_key": "[REDACTED]"}
    assert out["nested"]["deep"][0]["service_role_key"] == "[REDACTED]"
    assert out["consumer_key"] == "[REDACTED]"


def test_token_shaped_strings_are_scrubbed_anywhere():
    from core.audit_log import redact_sensitive

    msg = (
        "Upstream said: Authorization: Bearer abcdefghijklmnop rejected; "
        "key mhu_abcdefghijklmnopqrstuvwxyz012345 and ghp_ABCDEFGHIJKLMNOPQRSTUVWX12 "
        "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abcdefghijk"
    )
    out = redact_sensitive({"error": msg, "list": [msg]})
    for secret in (
        "abcdefghijklmnop",
        "mhu_abcdefghijklmnopqrstuvwxyz012345",
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWX12",
        "eyJhbGciOiJIUzI1NiJ9",
    ):
        assert secret not in out["error"] and secret not in out["list"][0]
    assert "Upstream said" in out["error"]  # ordinary text survives


def test_audit_logger_uses_recursive_redaction(tmp_path):
    from core.audit_log import AuditLogger

    logger = AuditLogger(log_dir=str(tmp_path))
    filtered = logger._filter_sensitive_data({"rows": [{"token": "t"}], "title": "Hello"})
    assert filtered == {"rows": [{"token": "[REDACTED]"}], "title": "Hello"}
