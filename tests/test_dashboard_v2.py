"""
Track G.12 — backend tests for SPA support routes.

Covers direct handler contracts for:
  * /api/me
  * /api/i18n/{lang}
  * /dashboard/* SPA serving
  * /dashboard-v2/* -> /dashboard/* redirects
  * /api/dashboard/login
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode

import pytest
from starlette.requests import Request
from starlette.responses import FileResponse

pytestmark = pytest.mark.frontend


def _make_request(
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    query_string: str = "",
    path_params: dict[str, str] | None = None,
    body: bytes | dict | None = None,
) -> Request:
    """Construct a minimal Starlette Request for direct handler tests."""
    body_bytes = body if isinstance(body, bytes) else json.dumps(body).encode() if body else b""
    header_pairs = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "scheme": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string.encode(),
        "headers": header_pairs,
        "path_params": path_params or {},
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope, receive)


def _make_form_request(path: str, body: dict[str, str]) -> Request:
    """Construct a form-encoded POST Request."""
    return _make_request(
        path,
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=urlencode(body).encode(),
    )


class _AnonAuth:
    def get_session_from_request(self, _request):
        return None

    def get_user_session_from_request(self, _request):
        return None


async def test_api_me_unauthenticated_returns_anonymous(monkeypatch):
    from core.dashboard import spa_routes

    monkeypatch.setattr(spa_routes, "get_dashboard_auth", lambda: _AnonAuth())

    request = _make_request("/api/me", headers={"accept-language": "en-US,en;q=0.9"})
    response = await spa_routes.api_me(request)
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["authenticated"] is False
    assert body["is_admin"] is False
    assert body["lang"] in ("en", "fa")
    assert "csrf_token" in body
    assert "master_key_login_enabled" in body


async def test_api_me_master_key_enabled_by_default(monkeypatch):
    from core.dashboard import spa_routes

    monkeypatch.delenv("DISABLE_MASTER_KEY_LOGIN", raising=False)
    monkeypatch.setattr(spa_routes, "get_dashboard_auth", lambda: _AnonAuth())

    response = await spa_routes.api_me(_make_request("/api/me"))
    body = json.loads(response.body)

    assert body["master_key_login_enabled"] is True


async def test_api_me_master_key_disabled_when_env_true(monkeypatch):
    from core.dashboard import spa_routes

    monkeypatch.setenv("DISABLE_MASTER_KEY_LOGIN", "true")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-secret")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(spa_routes, "get_dashboard_auth", lambda: _AnonAuth())

    response = await spa_routes.api_me(_make_request("/api/me"))
    body = json.loads(response.body)

    assert body["master_key_login_enabled"] is False


def test_dashboard_auth_rejects_master_key_when_disabled(monkeypatch):
    from core.dashboard.auth import DashboardAuth

    class FakeApiKeyManager:
        def validate_key(self, *_args, **_kwargs):
            return None

    monkeypatch.setenv("DISABLE_MASTER_KEY_LOGIN", "true")
    monkeypatch.setattr("core.api_keys.get_api_key_manager", lambda: FakeApiKeyManager())

    auth = DashboardAuth(secret_key="test-secret", master_api_key="master-secret")

    assert auth.validate_api_key("master-secret") == (False, "", None)


async def test_api_me_csrf_token_surfaces_when_middleware_sets_it(monkeypatch):
    from core.dashboard import spa_routes

    monkeypatch.setattr(spa_routes, "get_dashboard_auth", lambda: _AnonAuth())

    request = _make_request("/api/me")
    request.state.csrf_token = "csrf-fixture-token-abc"
    response = await spa_routes.api_me(request)
    body = json.loads(response.body)

    assert body["csrf_token"] == "csrf-fixture-token-abc"


async def test_api_i18n_returns_known_keys_for_en():
    from core.dashboard import spa_routes

    response = await spa_routes.api_i18n(_make_request("/api/i18n/en", path_params={"lang": "en"}))
    body = json.loads(response.body)

    assert response.status_code == 200
    assert isinstance(body, dict)
    assert len(body) > 0


async def test_api_i18n_falls_back_to_en_for_unknown_lang():
    from core.dashboard import spa_routes

    en_response = await spa_routes.api_i18n(
        _make_request("/api/i18n/en", path_params={"lang": "en"})
    )
    zz_response = await spa_routes.api_i18n(
        _make_request("/api/i18n/zz", path_params={"lang": "zz"})
    )

    assert zz_response.status_code == 200
    assert json.loads(zz_response.body) == json.loads(en_response.body)


async def test_dashboard_serves_index_or_fallback():
    from core.dashboard import spa_routes

    for path in ("/dashboard", "/dashboard/", "/dashboard/sites", "/dashboard/foo/bar"):
        response = await spa_routes.serve_spa(_make_request(path))
        assert response.status_code == 200
        assert response.media_type == "text/html"
        if isinstance(response, FileResponse):
            assert response.path.endswith("index.html")
        else:
            text = response.body.decode().lower()
            assert "<html" in text or "<!doctype" in text


async def test_dashboard_spa_can_serve_404_status_with_same_shell():
    from core.dashboard import spa_routes

    response = await spa_routes.serve_spa(_make_request("/missing-page"), status_code=404)

    assert response.status_code == 404
    assert response.media_type == "text/html"
    if isinstance(response, FileResponse):
        assert response.path.endswith("index.html")
    else:
        text = response.body.decode().lower()
        assert "<html" in text or "<!doctype" in text


async def test_dashboard_v2_redirects_to_dashboard():
    from core.dashboard import spa_routes

    cases = [
        (_make_request("/dashboard-v2"), "/dashboard"),
        (_make_request("/dashboard-v2/"), "/dashboard/"),
        (
            _make_request(
                "/dashboard-v2/sites",
                path_params={"path": "sites"},
            ),
            "/dashboard/sites",
        ),
        (
            _make_request(
                "/dashboard-v2/foo/bar",
                query_string="x=1",
                path_params={"path": "foo/bar"},
            ),
            "/dashboard/foo/bar?x=1",
        ),
    ]

    for request, expected in cases:
        response = await spa_routes.redirect_dashboard_v2(request)
        assert response.status_code == 308
        assert response.headers["location"] == expected


async def test_site_tools_api_includes_plugin_scope_presets(monkeypatch):
    from core.dashboard import routes

    async def fake_require_owned_site(_request):
        return {
            "id": "site-1",
            "plugin_type": "coolify",
            "tool_scope": "admin",
        }, None

    class FakeAccess:
        async def list_tools_for_site(self, site_id, plugin_type):
            assert site_id == "site-1"
            assert plugin_type == "coolify"
            return []

    async def fake_providers(_site_id):
        return set()

    monkeypatch.setattr(routes, "_require_owned_site", fake_require_owned_site)
    monkeypatch.setattr("core.tool_access.get_tool_access_manager", lambda: FakeAccess())
    monkeypatch.setattr("core.site_api.list_site_providers_set", fake_providers)

    response = await routes.api_list_site_tools(_make_request("/api/sites/site-1/tools"))
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["plugin_type"] == "coolify"
    assert [p["value"] for p in body["scope_presets"]] == [
        "read",
        "read:sensitive",
        "deploy",
        "write",
        "admin",
        "custom",
    ]


async def test_user_key_create_all_sites_keeps_site_id_empty(monkeypatch):
    from core.dashboard import routes

    def fake_require_user_session(_request):
        return {"user_id": "user-1", "type": "oauth_user"}, None

    class FakeKeyManager:
        async def create_key(self, **kwargs):
            assert kwargs["user_id"] == "user-1"
            assert kwargs["name"] == "all-sites"
            assert kwargs["site_id"] is None
            return {
                "key_id": "key-1",
                "key": "mhu_abcdefghijklmnopqrstuv",
                "name": kwargs["name"],
                "scopes": kwargs["scopes"],
                "created_at": "2026-05-17T00:00:00Z",
                "expires_at": None,
                "site_id": kwargs["site_id"],
            }

    monkeypatch.setattr(routes, "_require_user_session", fake_require_user_session)
    monkeypatch.setattr("core.user_keys.get_user_key_manager", lambda: FakeKeyManager())

    response = await routes.api_create_key(
        _make_request("/api/keys", method="POST", body={"name": "all-sites"})
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["site_id"] is None
    assert body["scope"] == "read editor settings install write admin"


async def test_oauth_client_create_uses_name_and_system_scopes(monkeypatch):
    from core.dashboard import routes

    class FakeAuth:
        def get_session_from_request(self, _request):
            return {"type": "master", "role": "admin"}

        def get_user_session_from_request(self, _request):
            return None

    class FakeRegistry:
        def __init__(self):
            self.kwargs = None

        def create_client(self, **kwargs):
            self.kwargs = kwargs
            return "client-1", "secret-1"

    class FakeAudit:
        def log_system_event(self, **_kwargs):
            return None

    registry = FakeRegistry()
    monkeypatch.setattr(routes, "get_dashboard_auth", lambda: FakeAuth())
    monkeypatch.setattr(routes, "is_admin_session", lambda _session: True)
    monkeypatch.setattr("core.oauth.client_registry.get_client_registry", lambda: registry)
    monkeypatch.setattr("core.audit_log.get_audit_logger", lambda: FakeAudit())

    response = await routes.dashboard_oauth_clients_create(
        _make_request(
            "/api/dashboard/oauth-clients/create",
            method="POST",
            body={
                "name": "Claude and ChatGPT",
                "redirect_uris": [
                    "https://chatgpt.com/connector/oauth/jl0vrVeOwbY8",
                    "https://claude.ai/api/mcp/auth_callback",
                ],
                "scope": "read",
            },
        )
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["client_id"] == "client-1"
    assert registry.kwargs["client_name"] == "Claude and ChatGPT"
    assert registry.kwargs["redirect_uris"] == [
        "https://chatgpt.com/connector/oauth/jl0vrVeOwbY8",
        "https://claude.ai/api/mcp/auth_callback",
    ]
    assert registry.kwargs["allowed_scopes"] == [
        "read",
        "read:sensitive",
        "deploy",
        "editor",
        "settings",
        "install",
        "write",
        "admin",
    ]


async def test_dashboard_settings_rejects_invalid_user_limit(monkeypatch):
    from core.dashboard import routes

    monkeypatch.setattr(
        routes, "_require_admin_session", lambda _request: ({"role": "admin"}, None)
    )

    response = await routes.api_save_setting(
        _make_request(
            "/api/dashboard/settings",
            method="POST",
            headers={"content-type": "application/json"},
            body={"key": "MAX_SITES_PER_USER", "value": "0"},
        )
    )

    assert response.status_code == 400
    assert "positive integer" in json.loads(response.body)["error"]


async def test_dashboard_settings_reset_clears_all_managed_settings(monkeypatch):
    from core.dashboard import routes

    deleted: list[str] = []

    async def fake_delete_setting_value(key: str) -> bool:
        deleted.append(key)
        return key != "USER_RATE_LIMIT_PER_HR"

    monkeypatch.setattr(
        routes, "_require_admin_session", lambda _request: ({"role": "admin"}, None)
    )
    monkeypatch.setattr("core.settings.delete_setting_value", fake_delete_setting_value)

    response = await routes.api_reset_settings(
        _make_request("/api/dashboard/settings/reset", method="POST")
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body == {"ok": True, "deleted": 3}
    assert set(deleted) == {
        "ENABLED_PLUGINS",
        "MAX_SITES_PER_USER",
        "USER_RATE_LIMIT_PER_MIN",
        "USER_RATE_LIMIT_PER_HR",
    }


class _DummyDashboardAuth:
    def __init__(self, *, valid: bool = True, rate_limited: bool = False):
        self.valid = valid
        self.rate_limited = rate_limited
        self.recorded_attempts = 0

    def check_rate_limit(self, _ip: str) -> bool:
        return not self.rate_limited

    def record_login_attempt(self, _ip: str) -> None:
        self.recorded_attempts += 1

    def validate_api_key(self, api_key: str):
        if self.valid and api_key == "good-master-key":
            return True, "master", None
        return False, "", None

    def create_session(self, _user_type: str, _key_id):
        return "admin-session-token"

    def set_session_cookie(self, response, token: str) -> None:
        response.set_cookie("mcp_dashboard_session", token)


async def test_dashboard_api_login_json_success_sets_cookie(monkeypatch):
    from core.dashboard.routes import dashboard_api_login

    auth = _DummyDashboardAuth(valid=True)

    async def _fake_ensure_master_key_user(_auth):
        return "user-session-token"

    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: auth)
    monkeypatch.setattr("core.dashboard.routes.get_client_ip", lambda _request: "127.0.0.1")
    monkeypatch.setattr(
        "core.dashboard.routes._ensure_master_key_user", _fake_ensure_master_key_user
    )

    request = _make_request(
        "/api/dashboard/login",
        method="POST",
        headers={"content-type": "application/json"},
        body={"api_key": "good-master-key", "next": "/dashboard/health"},
    )
    response = await dashboard_api_login(request)

    assert response.status_code == 200
    assert json.loads(response.body) == {"ok": True, "next": "/dashboard/health"}
    assert "mcp_dashboard_session=user-session-token" in response.headers.get("set-cookie", "")
    assert auth.recorded_attempts == 1


async def test_dashboard_api_login_json_invalid_key(monkeypatch):
    from core.dashboard.routes import dashboard_api_login

    auth = _DummyDashboardAuth(valid=False)
    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: auth)
    monkeypatch.setattr("core.dashboard.routes.get_client_ip", lambda _request: "127.0.0.1")

    request = _make_request(
        "/api/dashboard/login",
        method="POST",
        headers={"content-type": "application/json"},
        body={"api_key": "wrong-key"},
    )
    response = await dashboard_api_login(request)

    assert response.status_code == 401
    assert json.loads(response.body) == {"ok": False, "error": "invalid"}


async def test_dashboard_api_login_rate_limited(monkeypatch):
    from core.dashboard.routes import dashboard_api_login

    auth = _DummyDashboardAuth(valid=True, rate_limited=True)
    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: auth)
    monkeypatch.setattr("core.dashboard.routes.get_client_ip", lambda _request: "127.0.0.1")

    request = _make_request(
        "/api/dashboard/login",
        method="POST",
        headers={"content-type": "application/json"},
        body={"api_key": "good-master-key"},
    )
    response = await dashboard_api_login(request)

    assert response.status_code == 429
    assert json.loads(response.body) == {"ok": False, "error": "rate_limit"}
    assert auth.recorded_attempts == 0


class _LoggedInAuth(_AnonAuth):
    def get_session_from_request(self, _request):
        return {"type": "master", "role": "admin"}


async def test_dashboard_legacy_login_page_redirects_authenticated_users(monkeypatch):
    from core.dashboard.routes import dashboard_login_page

    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: _LoggedInAuth())

    response = await dashboard_login_page(_make_request("/dashboard-legacy/login"))

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/overview"


async def test_dashboard_legacy_login_page_posts_to_legacy_handler(monkeypatch):
    from core.dashboard.routes import dashboard_login_page

    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: _AnonAuth())

    response = await dashboard_login_page(_make_request("/dashboard-legacy/login"))
    html = response.body.decode()

    assert response.status_code == 200
    assert 'action="/dashboard-legacy/login"' in html
    assert 'action="/dashboard/login"' not in html


async def test_dashboard_legacy_login_submit_success_sets_cookie(monkeypatch):
    from core.dashboard.routes import dashboard_login_submit

    auth = _DummyDashboardAuth(valid=True)

    async def _fake_ensure_master_key_user(_auth):
        return "user-session-token"

    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: auth)
    monkeypatch.setattr("core.dashboard.routes.get_client_ip", lambda _request: "127.0.0.1")
    monkeypatch.setattr(
        "core.dashboard.routes._ensure_master_key_user", _fake_ensure_master_key_user
    )

    response = await dashboard_login_submit(
        _make_form_request(
            "/dashboard-legacy/login",
            {"api_key": "good-master-key", "next": "/dashboard/health"},
        )
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/health"
    assert "mcp_dashboard_session=user-session-token" in response.headers.get("set-cookie", "")


async def test_dashboard_legacy_login_submit_invalid_redirects_back(monkeypatch):
    from core.dashboard.routes import dashboard_login_submit

    auth = _DummyDashboardAuth(valid=False)
    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: auth)
    monkeypatch.setattr("core.dashboard.routes.get_client_ip", lambda _request: "127.0.0.1")

    response = await dashboard_login_submit(
        _make_form_request(
            "/dashboard-legacy/login",
            {"api_key": "wrong-key", "next": "/dashboard/health"},
        )
    )

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "/dashboard-legacy/login?error=invalid&next=/dashboard/health&lang=en"
    )


async def test_dashboard_legacy_login_submit_rate_limited_redirects_back(monkeypatch):
    from core.dashboard.routes import dashboard_login_submit

    auth = _DummyDashboardAuth(valid=True, rate_limited=True)
    monkeypatch.setattr("core.dashboard.routes.get_dashboard_auth", lambda: auth)
    monkeypatch.setattr("core.dashboard.routes.get_client_ip", lambda _request: "127.0.0.1")

    response = await dashboard_login_submit(
        _make_form_request("/dashboard-legacy/login", {"api_key": "good-master-key"})
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard-legacy/login?error=rate_limit&lang=en"
    assert auth.recorded_attempts == 0


def test_spa_dist_dir_exists_as_placeholder():
    """The dist dir must exist (with .gitkeep) so package_data can include it."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dist = os.path.join(repo_root, "core", "templates", "static", "dist")
    assert os.path.isdir(dist), f"SPA dist directory missing: {dist}"


class TestAnalyticsSnippet:
    """_analytics_snippet() — env-var driven analytics tag assembly."""

    def test_returns_empty_when_nothing_configured(self, monkeypatch):
        from core.dashboard import spa_routes

        for key in ("UMAMI_WEBSITE_ID", "UMAMI_URL", "OPENPANEL_API_URL", "OPENPANEL_CLIENT_ID"):
            monkeypatch.delenv(key, raising=False)
        assert spa_routes._analytics_snippet() == ""

    def test_umami_only(self, monkeypatch):
        from core.dashboard import spa_routes

        monkeypatch.setenv("UMAMI_WEBSITE_ID", "abc-123")
        monkeypatch.setenv("UMAMI_URL", "https://umami.example.com/script.js")
        monkeypatch.delenv("OPENPANEL_API_URL", raising=False)
        monkeypatch.delenv("OPENPANEL_CLIENT_ID", raising=False)
        snippet = spa_routes._analytics_snippet()
        assert 'data-website-id="abc-123"' in snippet
        assert "https://umami.example.com/script.js" in snippet
        assert "window.op" not in snippet

    def test_openpanel_only(self, monkeypatch):
        from core.dashboard import spa_routes

        monkeypatch.delenv("UMAMI_WEBSITE_ID", raising=False)
        monkeypatch.delenv("UMAMI_URL", raising=False)
        monkeypatch.setenv("OPENPANEL_API_URL", "https://op.example.com")
        monkeypatch.setenv("OPENPANEL_CLIENT_ID", "client-xyz")
        snippet = spa_routes._analytics_snippet()
        assert 'clientId:"client-xyz"' in snippet
        assert "data-website-id" not in snippet

    def test_partial_umami_config_is_skipped(self, monkeypatch):
        """Setting only WEBSITE_ID without URL must not render half a tag."""
        from core.dashboard import spa_routes

        monkeypatch.setenv("UMAMI_WEBSITE_ID", "abc-123")
        monkeypatch.delenv("UMAMI_URL", raising=False)
        monkeypatch.delenv("OPENPANEL_API_URL", raising=False)
        monkeypatch.delenv("OPENPANEL_CLIENT_ID", raising=False)
        assert spa_routes._analytics_snippet() == ""


class TestRenderSpaIndex:
    """_render_spa_index() — inject analytics tags into the built index.html."""

    def _write_index(self, tmp_path, body: str) -> str:
        path = tmp_path / "index.html"
        path.write_text(body, encoding="utf-8")
        return str(path)

    def test_returns_unmodified_when_no_snippet(self, tmp_path, monkeypatch):
        from core.dashboard import spa_routes

        for key in ("UMAMI_WEBSITE_ID", "UMAMI_URL", "OPENPANEL_API_URL", "OPENPANEL_CLIENT_ID"):
            monkeypatch.delenv(key, raising=False)
        index = self._write_index(tmp_path, "<html><head><title>x</title></head></html>")
        with open(index, "rb") as fh:
            assert spa_routes._render_spa_index(index) == fh.read()

    def test_injects_before_head_close(self, tmp_path, monkeypatch):
        from core.dashboard import spa_routes

        monkeypatch.setenv("UMAMI_WEBSITE_ID", "site-abc")
        monkeypatch.setenv("UMAMI_URL", "https://umami.example.com/s.js")
        monkeypatch.delenv("OPENPANEL_API_URL", raising=False)
        monkeypatch.delenv("OPENPANEL_CLIENT_ID", raising=False)
        index = self._write_index(
            tmp_path, "<html><head><title>x</title></head><body></body></html>"
        )
        rendered = spa_routes._render_spa_index(index).decode("utf-8")
        assert rendered.index("data-website-id") < rendered.index("</head>")
        assert rendered.count("</head>") == 1  # marker not duplicated
