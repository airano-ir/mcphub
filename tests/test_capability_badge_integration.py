"""F.7e — dashboard_sites_view renders capability probe into template context.

End-to-end-ish test: builds a real DB + site, stubs the plugin's probe,
and verifies that ``dashboard_sites_view`` injects a ``capability_probe``
context entry with a well-shaped ``fit`` dict. The manage.html template
consumes this entry to render the badge; this test only covers the
context wiring, not the template output (templates are hit in
integration dashboard tests).
"""

from __future__ import annotations

import base64
import os
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    import core.encryption as enc_mod

    monkeypatch.setattr(enc_mod, "_credential_encryption", None)


@pytest.fixture(autouse=True)
def _reset_probe_cache():
    from core.capability_probe import get_probe_cache

    get_probe_cache()._entries.clear()
    yield
    get_probe_cache()._entries.clear()


@pytest.fixture
async def _db_with_wp_site(tmp_path, monkeypatch):
    import core.database as db_mod
    from core.database import initialize_database
    from core.encryption import get_credential_encryption

    monkeypatch.setattr(db_mod, "_database", None)
    db = await initialize_database(str(tmp_path / "badge.db"))

    user = await db.create_user(
        email="badge@example.com",
        name="Badge",
        provider="github",
        provider_id="gh-badge",
    )
    enc = get_credential_encryption()
    creds = enc.encrypt_credentials(
        {"username": "admin", "app_password": "xxxx xxxx"}, "site-badge-1"
    )
    site = await db.create_site(
        user_id=user["id"],
        plugin_type="wordpress",
        alias="bloggy",
        url="https://wp.example.com",
        credentials=creds,
    )
    await db.execute(
        "UPDATE sites SET id = ?, tool_scope = ? WHERE id = ?",
        ("site-badge-1", "admin", site["id"]),
    )
    site = await db.get_site("site-badge-1", user["id"])
    yield db, user, site
    await db.close()
    monkeypatch.setattr(db_mod, "_database", None)


class TestSitesViewInjectsCapabilityProbe:
    @pytest.mark.asyncio
    async def test_admin_tier_with_admin_role_renders_ok(self, _db_with_wp_site, monkeypatch):
        _, user, site = _db_with_wp_site

        async def _probe(self: Any) -> dict[str, Any]:
            return {
                "probe_available": True,
                "granted": ["administrator", "manage_options", "upload_files"],
                "source": "wordpress_companion",
                "roles": ["administrator"],
            }

        from plugins.wordpress.plugin import WordPressPlugin

        monkeypatch.setattr(WordPressPlugin, "probe_credential_capabilities", _probe)

        captured: dict = {}

        def _capture_template(_request, template_name, context, **kwargs):
            captured["template"] = template_name
            captured["context"] = context

            # Return a minimal response object; the test doesn't render HTML.
            class _Resp:
                status_code = 200

            return _Resp()

        from starlette.requests import Request

        from core.dashboard.routes import dashboard_sites_view

        scope = {
            "type": "http",
            "method": "GET",
            "path": f"/dashboard/sites/{site['id']}",
            "path_params": {"id": site["id"]},
            "headers": [],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b""}

        request = Request(scope, receive)

        with (
            patch("core.dashboard.routes.templates") as mock_templates,
            patch(
                "core.dashboard.routes._require_user_session",
                return_value=({"user_id": user["id"]}, None),
            ),
        ):
            mock_templates.TemplateResponse = _capture_template
            await dashboard_sites_view(request)

        assert captured["template"] == "dashboard/sites/manage.html"
        ctx = captured["context"]
        assert "capability_probe" in ctx
        probe = ctx["capability_probe"]
        assert probe["probe_available"] is True
        assert probe["fit"]["status"] == "ok"
        assert probe["fit"]["missing"] == []

    @pytest.mark.asyncio
    async def test_admin_tier_with_editor_role_renders_warning(self, _db_with_wp_site, monkeypatch):
        _, user, site = _db_with_wp_site

        async def _probe(self: Any) -> dict[str, Any]:
            return {
                "probe_available": True,
                "granted": ["editor", "edit_posts", "upload_files"],
                "source": "wordpress_companion",
                "roles": ["editor"],
            }

        from plugins.wordpress.plugin import WordPressPlugin

        monkeypatch.setattr(WordPressPlugin, "probe_credential_capabilities", _probe)

        captured: dict = {}

        def _capture_template(_request, _name, context, **kwargs):
            captured["context"] = context

            class _Resp:
                status_code = 200

            return _Resp()

        from starlette.requests import Request

        from core.dashboard.routes import dashboard_sites_view

        scope = {
            "type": "http",
            "method": "GET",
            "path": f"/dashboard/sites/{site['id']}",
            "path_params": {"id": site["id"]},
            "headers": [],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b""}

        request = Request(scope, receive)

        with (
            patch("core.dashboard.routes.templates") as mock_templates,
            patch(
                "core.dashboard.routes._require_user_session",
                return_value=({"user_id": user["id"]}, None),
            ),
        ):
            mock_templates.TemplateResponse = _capture_template
            await dashboard_sites_view(request)

        probe = captured["context"]["capability_probe"]
        assert probe["fit"]["status"] == "warning"
        assert "manage_options" in probe["fit"]["missing"]

    @pytest.mark.asyncio
    async def test_probe_raises_renders_probe_unavailable(self, _db_with_wp_site, monkeypatch):
        _, user, site = _db_with_wp_site

        async def _probe(self: Any) -> dict[str, Any]:
            raise RuntimeError("no companion")

        from plugins.wordpress.plugin import WordPressPlugin

        monkeypatch.setattr(WordPressPlugin, "probe_credential_capabilities", _probe)

        captured: dict = {}

        def _capture_template(_request, _name, context, **kwargs):
            captured["context"] = context

            class _Resp:
                status_code = 200

            return _Resp()

        from starlette.requests import Request

        from core.dashboard.routes import dashboard_sites_view

        scope = {
            "type": "http",
            "method": "GET",
            "path": f"/dashboard/sites/{site['id']}",
            "path_params": {"id": site["id"]},
            "headers": [],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b""}

        request = Request(scope, receive)

        with (
            patch("core.dashboard.routes.templates") as mock_templates,
            patch(
                "core.dashboard.routes._require_user_session",
                return_value=({"user_id": user["id"]}, None),
            ),
        ):
            mock_templates.TemplateResponse = _capture_template
            await dashboard_sites_view(request)

        probe = captured["context"]["capability_probe"]
        assert probe["probe_available"] is False
        assert probe["fit"]["status"] == "probe_unavailable"
