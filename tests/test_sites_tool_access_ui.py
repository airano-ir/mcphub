"""Smoke tests for unified site management page (F.7c redesign)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import core.dashboard.routes as routes_module
import core.database as db_module
import core.tool_access as tool_access_module
from core.database import Database


@pytest.fixture
async def patched_db(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "ui.db"))
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
        email="ui@example.com",
        name="uitester",
        provider="github",
        provider_id="gh-ui-user",
    )


@pytest.fixture
async def coolify_site(patched_db, user_row):
    return await patched_db.create_site(
        user_id=user_row["id"],
        plugin_type="coolify",
        alias="ui-prod",
        url="https://coolify.example.com",
        credentials=b"x",
    )


@pytest.fixture
def client(monkeypatch, user_row, patched_db, patched_access):
    from server import create_multi_endpoint_app

    def fake_user_session(_request):
        return {"user_id": user_row["id"], "type": "user"}, None

    monkeypatch.setattr(routes_module, "_require_user_session", fake_user_session)

    # Patch auth for dashboard_keys_unified
    class FakeAuth:
        def get_session_from_request(self, _r):
            return None

        def get_user_session_from_request(self, _r):
            return {"user_id": user_row["id"], "type": "user"}

    monkeypatch.setattr(routes_module, "get_dashboard_auth", lambda: FakeAuth())

    app = create_multi_endpoint_app()
    tc = TestClient(app, follow_redirects=False)
    tc.cookies.set("dashboard_csrf", "test-csrf")
    tc.headers.update({"x-csrf-token": "test-csrf"})
    return tc


class TestSitesEditRedirect:
    def test_edit_page_redirects_to_manage(self, client, coolify_site):
        """F.7c: /sites/{id}/edit now redirects to unified /sites/{id}."""
        r = client.get(f"/dashboard/sites/{coolify_site['id']}/edit")
        assert r.status_code == 301
        assert f"/dashboard/sites/{coolify_site['id']}" in r.headers["location"]


class TestUnifiedSiteManagePage:
    def test_manage_page_renders_without_500(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200

    def test_manage_page_has_connection_section(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "connection-section" in r.text

    def test_manage_page_has_tool_access_section(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "tool-access-content" in r.text or "Tool Access" in r.text

    def test_manage_page_has_scope_tiers(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "scope-tiers" in r.text

    def test_manage_page_shows_mcp_url(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "mcp-url" in r.text
        assert coolify_site["alias"] in r.text

    def test_manage_page_has_config_snippets(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "config-client" in r.text

    def test_manage_page_has_quick_key_create(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "quick-key-btn" in r.text

    def test_nonexistent_site_redirects(self, client):
        r = client.get("/dashboard/sites/nonexistent-id")
        assert r.status_code in (302, 303)
