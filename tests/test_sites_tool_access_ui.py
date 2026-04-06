"""Smoke tests for sites edit page Tool Access section and sites view page (F.7b session 2)."""

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


class TestSitesEditToolAccess:
    def test_edit_page_renders_without_500(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}/edit")
        assert r.status_code == 200

    def test_edit_page_contains_tool_access_card(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}/edit")
        assert r.status_code == 200
        assert "tool-access-card" in r.text or "Tool Access" in r.text

    def test_edit_page_has_scope_select(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}/edit")
        assert r.status_code == 200
        assert "tool-scope-select" in r.text


class TestSitesViewPage:
    def test_view_page_renders_without_500(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200

    def test_view_page_shows_mcp_url(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "mcp-url" in r.text
        assert coolify_site["alias"] in r.text

    def test_view_page_has_client_selector(self, client, coolify_site):
        r = client.get(f"/dashboard/sites/{coolify_site['id']}")
        assert r.status_code == 200
        assert "config-client" in r.text

    def test_nonexistent_site_redirects(self, client):
        r = client.get("/dashboard/sites/nonexistent-id")
        assert r.status_code in (302, 303)
