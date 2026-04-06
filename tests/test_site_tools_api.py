"""Integration tests for the per-site tool visibility API (F.7b).

Exercises the five routes registered in server.py:

* ``GET    /api/sites/{site_id}/tools``
* ``PATCH  /api/sites/{site_id}/tools/{tool_name}``
* ``POST   /api/sites/{site_id}/tools/bulk-toggle``
* ``PATCH  /api/sites/{site_id}/tool-scope``
* ``GET    /api/scope-presets``

Uses the real ``create_multi_endpoint_app()`` so routes wire to the actual
Coolify tool registry. User session auth is stubbed.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import core.dashboard.routes as routes_module
import core.database as db_module
import core.tool_access as tool_access_module
from core.database import Database


@pytest.fixture
async def patched_db(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "api.db"))
    await database.initialize()
    monkeypatch.setattr(db_module, "_database", database)
    yield database
    await database.close()
    monkeypatch.setattr(db_module, "_database", None)


@pytest.fixture
def patched_access(monkeypatch):
    monkeypatch.setattr(tool_access_module, "_manager", None)


@pytest.fixture
async def user_row(patched_db):
    return await patched_db.create_user(
        email="api@example.com",
        name="api",
        provider="github",
        provider_id="gh-api-user",
    )


@pytest.fixture
async def coolify_site(patched_db, user_row):
    return await patched_db.create_site(
        user_id=user_row["id"],
        plugin_type="coolify",
        alias="prod",
        url="https://coolify.example.com",
        credentials=b"x",
    )


@pytest.fixture
async def other_user_site(patched_db):
    """A site belonging to a different user — for ownership-check tests."""
    other = await patched_db.create_user(
        email="other@example.com",
        name="other",
        provider="github",
        provider_id="gh-other",
    )
    return await patched_db.create_site(
        user_id=other["id"],
        plugin_type="coolify",
        alias="theirs",
        url="https://other.example.com",
        credentials=b"x",
    )


@pytest.fixture
def client(monkeypatch, user_row, patched_db, patched_access):
    """Build the Starlette app and patch user session auth.

    Also pre-sets a matching CSRF cookie + default X-CSRF-Token header so that
    mutating requests to ``/api/sites/*`` bypass the Double-Submit CSRF guard
    in ``DashboardCSRFMiddleware``.
    """
    from server import create_multi_endpoint_app

    def fake_require_user_session(_request):
        return {"user_id": user_row["id"], "type": "user"}, None

    monkeypatch.setattr(routes_module, "_require_user_session", fake_require_user_session)

    app = create_multi_endpoint_app()
    tc = TestClient(app)
    tc.cookies.set("dashboard_csrf", "test-csrf-token")
    tc.headers.update({"x-csrf-token": "test-csrf-token"})
    return tc


# ---------------------------------------------------------------------------
# GET /api/sites/{site_id}/tools
# ---------------------------------------------------------------------------


class TestListSiteTools:
    def test_returns_plugin_tools_all_enabled(self, client, coolify_site):
        resp = client.get(f"/api/sites/{coolify_site['id']}/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["site_id"] == coolify_site["id"]
        assert body["plugin_type"] == "coolify"
        assert body["tool_scope"] == "admin"
        tools = body["tools"]
        by_name = {t["name"]: t for t in tools}
        assert "coolify_list_applications" in by_name
        assert "coolify_delete_server" in by_name
        assert all(t["enabled"] for t in tools)

    def test_carries_category_and_sensitivity(self, client, coolify_site):
        tools = client.get(f"/api/sites/{coolify_site['id']}/tools").json()["tools"]
        by_name = {t["name"]: t for t in tools}
        assert by_name["coolify_list_applications"]["category"] == "read"
        assert by_name["coolify_delete_server"]["category"] == "system"
        assert by_name["coolify_get_application_logs"]["sensitivity"] == "sensitive"

    def test_only_own_sites_visible(self, client, other_user_site):
        """A site owned by a different user must 404."""
        resp = client.get(f"/api/sites/{other_user_site['id']}/tools")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/sites/{site_id}/tools/{tool_name}
# ---------------------------------------------------------------------------


class TestPatchSiteTool:
    def test_disable_reflected_in_list(self, client, coolify_site):
        r = client.patch(
            f"/api/sites/{coolify_site['id']}/tools/coolify_list_applications",
            json={"enabled": False, "reason": "not needed"},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        tools = client.get(f"/api/sites/{coolify_site['id']}/tools").json()["tools"]
        by_name = {t["name"]: t["enabled"] for t in tools}
        assert by_name["coolify_list_applications"] is False
        assert by_name["coolify_start_application"] is True

    def test_reenable_round_trip(self, client, coolify_site):
        base = f"/api/sites/{coolify_site['id']}/tools/coolify_list_applications"
        client.patch(base, json={"enabled": False})
        client.patch(base, json={"enabled": True})
        tools = client.get(f"/api/sites/{coolify_site['id']}/tools").json()["tools"]
        by_name = {t["name"]: t["enabled"] for t in tools}
        assert by_name["coolify_list_applications"] is True

    def test_unknown_tool_404(self, client, coolify_site):
        r = client.patch(
            f"/api/sites/{coolify_site['id']}/tools/coolify_nonsense",
            json={"enabled": False},
        )
        assert r.status_code == 404

    def test_wrong_plugin_400(self, client, coolify_site):
        """Tool from another plugin should be rejected."""
        r = client.patch(
            f"/api/sites/{coolify_site['id']}/tools/wordpress_list_posts",
            json={"enabled": False},
        )
        assert r.status_code in (400, 404)

    def test_missing_enabled_400(self, client, coolify_site):
        r = client.patch(
            f"/api/sites/{coolify_site['id']}/tools/coolify_list_applications",
            json={},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/sites/{site_id}/tools/bulk-toggle
# ---------------------------------------------------------------------------


class TestBulkToggle:
    def test_bulk_disable_deploy_scope(self, client, coolify_site):
        r = client.post(
            f"/api/sites/{coolify_site['id']}/tools/bulk-toggle",
            json={"scope": "deploy", "enabled": False},
        )
        assert r.status_code == 200
        assert r.json()["affected"] >= 5

        tools = client.get(f"/api/sites/{coolify_site['id']}/tools").json()["tools"]
        by_name = {t["name"]: t["enabled"] for t in tools}
        assert by_name["coolify_list_applications"] is False
        assert by_name["coolify_start_application"] is False
        assert by_name["coolify_create_application_public"] is True
        assert by_name["coolify_delete_server"] is True

    def test_unknown_scope_400(self, client, coolify_site):
        r = client.post(
            f"/api/sites/{coolify_site['id']}/tools/bulk-toggle",
            json={"scope": "bogus", "enabled": False},
        )
        assert r.status_code == 400

    def test_bad_body_400(self, client, coolify_site):
        r = client.post(
            f"/api/sites/{coolify_site['id']}/tools/bulk-toggle",
            json={"scope": "read"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /api/sites/{site_id}/tool-scope
# ---------------------------------------------------------------------------


class TestSetSiteToolScope:
    def test_set_read_scope(self, client, coolify_site):
        r = client.patch(
            f"/api/sites/{coolify_site['id']}/tool-scope",
            json={"scope": "read"},
        )
        assert r.status_code == 200
        assert r.json()["tool_scope"] == "read"
        listing = client.get(f"/api/sites/{coolify_site['id']}/tools").json()
        assert listing["tool_scope"] == "read"

    def test_invalid_scope_400(self, client, coolify_site):
        r = client.patch(
            f"/api/sites/{coolify_site['id']}/tool-scope",
            json={"scope": "superadmin"},
        )
        assert r.status_code == 400

    def test_accepts_all_known_presets(self, client, coolify_site):
        for scope in ("read", "read:sensitive", "deploy", "write", "admin", "custom"):
            r = client.patch(
                f"/api/sites/{coolify_site['id']}/tool-scope",
                json={"scope": scope},
            )
            assert r.status_code == 200, scope


# ---------------------------------------------------------------------------
# GET /api/scope-presets
# ---------------------------------------------------------------------------


class TestScopePresets:
    def test_returns_all_scopes(self, client):
        body = client.get("/api/scope-presets").json()
        assert "presets" in body
        presets = body["presets"]
        assert set(presets.keys()) == {"read", "read:sensitive", "deploy", "write", "admin"}
        assert "read" in presets["read"]
        assert "system" in presets["admin"]
