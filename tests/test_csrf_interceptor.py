"""Regression tests for the global CSRF interceptor (F.7c).

Background: previously, dashboard pages defined a local ``getCsrf()`` JS helper
that read the dashboard CSRF cookie via ``document.cookie``. The cookie is
``HttpOnly``, so JS could never read it and every non-GET fetch sent an empty
``X-CSRF-Token`` header — leading to 403 errors when toggling tools or
changing the access scope.

The fix moved CSRF handling into a single global interceptor in
``head_assets.html`` that reads from a ``<meta name="csrf-token">`` tag rendered
server-side in ``base.html``. This file pins down the contract so the bug
cannot silently regress:

  1. Every dashboard page renders a non-empty ``<meta name="csrf-token">`` tag.
  2. The global ``htmx:configRequest`` + ``window.fetch`` interceptor is
     present in ``head_assets.html``.
  3. No dashboard template defines its own ``getCsrf()`` helper or sets an
     explicit ``x-csrf-token`` header from JS — those would short-circuit the
     global interceptor again.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

import core.dashboard.routes as routes_module
import core.database as db_module
from core.database import Database

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "core" / "templates"
DASHBOARD_DIR = TEMPLATES_DIR / "dashboard"


# ── Static template checks ──────────────────────────────────────


class TestStaticTemplateContract:
    """Lint-style checks that don't require a running app."""

    def test_head_assets_has_global_csrf_interceptor(self):
        head = (DASHBOARD_DIR / "partials" / "head_assets.html").read_text()
        # The HTMX hook
        assert "htmx:configRequest" in head, "missing global HTMX CSRF hook"
        # The fetch monkey-patch
        assert "window.fetch" in head, "missing global fetch CSRF hook"
        # Both must read from the meta tag — not the cookie
        assert 'meta[name="csrf-token"]' in head, "interceptor must read from meta tag"
        # Sanity: must set the X-CSRF-Token header
        assert "X-CSRF-Token" in head

    def test_base_template_renders_csrf_meta_tag(self):
        base = (DASHBOARD_DIR / "base.html").read_text()
        assert '<meta name="csrf-token"' in base
        assert (
            "request.state.csrf_token" in base
        ), "CSRF meta must be populated from request.state.csrf_token"

    def test_no_dashboard_template_defines_local_getcsrf(self):
        """Local getCsrf() helpers reintroduce the httponly cookie bug."""
        offenders = []
        for path in DASHBOARD_DIR.rglob("*.html"):
            text = path.read_text()
            if "function getCsrf" in text or "const getCsrf =" in text:
                offenders.append(str(path.relative_to(DASHBOARD_DIR)))
        assert not offenders, (
            f"templates must rely on the global CSRF interceptor — "
            f"found local getCsrf() in: {offenders}"
        )

    def test_no_dashboard_template_sets_explicit_csrf_header(self):
        """Explicit ``x-csrf-token`` headers from JS skip the global interceptor.

        Allowed exception: head_assets.html, which IS the interceptor.
        """
        offenders = []
        for path in DASHBOARD_DIR.rglob("*.html"):
            if path.name == "head_assets.html":
                continue
            text = path.read_text().lower()
            if "'x-csrf-token'" in text or '"x-csrf-token"' in text:
                offenders.append(str(path.relative_to(DASHBOARD_DIR)))
        assert not offenders, (
            f"templates must not set X-CSRF-Token explicitly — let the "
            f"global interceptor handle it. Offenders: {offenders}"
        )


# ── Live render check ──────────────────────────────────────────


@pytest.fixture
async def patched_db(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "csrf.db"))
    await database.initialize()
    monkeypatch.setattr(db_module, "_database", database)
    yield database
    await database.close()
    monkeypatch.setattr(db_module, "_database", None)


@pytest.fixture
async def user_row(patched_db):
    return await patched_db.create_user(
        email="csrf@example.com",
        name="csrfuser",
        provider="github",
        provider_id="gh-csrf-user",
    )


@pytest.fixture
def user_client(monkeypatch, user_row, patched_db):
    from server import create_multi_endpoint_app

    def fake_user_session(_request):
        return {"user_id": user_row["id"], "type": "user"}, None

    monkeypatch.setattr(routes_module, "_require_user_session", fake_user_session)

    class FakeAuth:
        def get_session_from_request(self, _r):
            return None

        def get_user_session_from_request(self, _r):
            return {"user_id": user_row["id"], "type": "user"}

    monkeypatch.setattr(routes_module, "get_dashboard_auth", lambda: FakeAuth())

    app = create_multi_endpoint_app()
    return TestClient(app, follow_redirects=False)


class TestRenderedCsrfMeta:
    def test_keys_page_has_non_empty_csrf_meta(self, user_client):
        r = user_client.get("/dashboard/keys")
        assert r.status_code == 200
        # The meta tag must be present *and* populated with a real token.
        assert '<meta name="csrf-token"' in r.text
        # An empty content="" would re-introduce the bug.
        assert 'content=""' not in r.text.split('<meta name="csrf-token"', 1)[1].split(">", 1)[0]
