"""Tests for the unified /dashboard/keys page (F.7b session 2)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import core.dashboard.routes as routes_module
import core.database as db_module
from core.database import Database


@pytest.fixture
async def patched_db(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "keys.db"))
    await database.initialize()
    monkeypatch.setattr(db_module, "_database", database)
    yield database
    await database.close()
    monkeypatch.setattr(db_module, "_database", None)


@pytest.fixture
async def user_row(patched_db):
    return await patched_db.create_user(
        email="keys@example.com",
        name="keysuser",
        provider="github",
        provider_id="gh-keys-user",
    )


@pytest.fixture
def user_client(monkeypatch, user_row, patched_db):
    from server import create_multi_endpoint_app

    def fake_user_session(_request):
        return {"user_id": user_row["id"], "type": "user"}, None

    monkeypatch.setattr(routes_module, "_require_user_session", fake_user_session)

    # Also patch auth so dashboard_keys_unified finds the user session
    class FakeAuth:
        def get_session_from_request(self, _r):
            return None  # not admin

        def get_user_session_from_request(self, _r):
            return {"user_id": user_row["id"], "type": "user"}

    monkeypatch.setattr(routes_module, "get_dashboard_auth", lambda: FakeAuth())

    app = create_multi_endpoint_app()
    return TestClient(app, follow_redirects=False)


class TestUnifiedKeysUserView:
    def test_get_keys_page_returns_200(self, user_client):
        r = user_client.get("/dashboard/keys")
        assert r.status_code == 200
        assert "API Key" in r.text or "کلید" in r.text

    def test_old_connect_redirects_301(self, user_client):
        r = user_client.get("/dashboard/connect")
        assert r.status_code == 301
        assert "/dashboard/keys" in r.headers["location"]

    def test_old_api_keys_redirects_301(self, user_client):
        r = user_client.get("/dashboard/api-keys")
        assert r.status_code == 301
        assert "/dashboard/keys" in r.headers["location"]

    def test_user_view_has_full_access_badge(self, user_client):
        r = user_client.get("/dashboard/keys")
        assert r.status_code == 200
        # F.7c: No scope selector — shows "Full Access" badge instead
        assert "Full Access" in r.text or "دسترسی کامل" in r.text

    def test_user_view_shows_create_button(self, user_client):
        r = user_client.get("/dashboard/keys")
        assert r.status_code == 200
        assert "Create" in r.text or "ایجاد" in r.text
