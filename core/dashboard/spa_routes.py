"""
SPA Routes (Track G) — React SPA support on /dashboard/*.

This module exposes:

- ``GET /api/me`` — JSON description of the current session (no redirect side
  effects).  Used by the React SPA to decide whether to show login or dashboard.
- ``GET /api/i18n/{lang}`` — JSON dump of the existing
  ``DASHBOARD_TRANSLATIONS`` so the SPA can reuse the copy without duplication.
- ``GET /dashboard`` and ``GET /dashboard/{path:path}`` — catch-all that
  serves the SPA's compiled ``index.html``.  Static asset handling is wired up
  in ``register_spa_routes`` via a ``StaticFiles`` mount.

Coexistence: the legacy Jinja UI lives at ``/dashboard-legacy/*`` while the
SPA owns ``/dashboard/*``. Old ``/dashboard-v2/*`` links are redirected to the
new prefix by the main Starlette app (see Track G.12 in ROADMAP.md).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles

from .auth import get_dashboard_auth, is_admin_session

logger = logging.getLogger(__name__)

# Path to the Vite build output.  Templates dir lives one level above this file.
_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
SPA_DIST_DIR = os.path.join(_TEMPLATES_DIR, "static", "dist")

# Marker placed just before </head> so the analytics injector has a stable,
# build-tool-agnostic insertion point.
_HEAD_CLOSE = "</head>"


def _spa_index_path() -> str:
    return os.path.join(SPA_DIST_DIR, "index.html")


def _analytics_snippet() -> str:
    """Return analytics <script> tags assembled from env vars.

    Each provider is independent: leaving its env vars unset silently skips
    that block. Returns an empty string when nothing is configured so the
    injection is a no-op.
    """
    parts: list[str] = []

    umami_id = os.environ.get("UMAMI_WEBSITE_ID", "").strip()
    umami_url = os.environ.get("UMAMI_URL", "").strip()
    if umami_id and umami_url:
        parts.append(f'<script defer src="{umami_url}" data-website-id="{umami_id}"></script>')

    op_api = os.environ.get("OPENPANEL_API_URL", "").strip()
    op_client = os.environ.get("OPENPANEL_CLIENT_ID", "").strip()
    if op_api and op_client:
        # OpenPanel ships a small bootstrap that loads their tracker SDK.
        parts.append(
            "<script>"
            "(function(){window.op=window.op||function(){(window.op.q=window.op.q||[]).push(arguments);};"
            f'window.op("init",{{apiUrl:"{op_api}",clientId:"{op_client}"}});'
            "var s=document.createElement('script');s.async=1;"
            f's.src="{op_api.rstrip("/")}/script.js";'
            "document.head.appendChild(s);})();"
            "</script>"
        )

    return "".join(parts)


def _render_spa_index(index_path: str) -> bytes:
    """Read the built index.html and inject analytics tags before </head>.

    Falls back to the unmodified bytes when no provider is configured or
    when the </head> marker is somehow missing (older build).
    """
    with open(index_path, "rb") as fh:
        html = fh.read()
    snippet = _analytics_snippet()
    if not snippet:
        return html
    marker = _HEAD_CLOSE.encode("utf-8")
    if marker not in html:
        return html
    return html.replace(marker, snippet.encode("utf-8") + marker, 1)


def _master_key_login_enabled() -> bool:
    """Return True when admin login by master API key is enabled.

    Mirrors the env semantics used in ``core/dashboard/auth.py`` and
    ``core/dashboard/routes.py``: the env var inverts the meaning, so
    ``DISABLE_MASTER_KEY_LOGIN=true`` → master-key form is hidden.
    """
    return os.environ.get("DISABLE_MASTER_KEY_LOGIN", "false").lower() != "true"


async def _max_sites_per_user() -> int:
    from core.settings import get_setting

    try:
        val = await get_setting("MAX_SITES_PER_USER", "10")
        return max(0, int(val or "10"))
    except (ValueError, TypeError):
        return 10


async def api_me(request: Request) -> Response:
    """Return JSON describing the current session.

    Returns ``{"authenticated": false}`` with status 200 when the caller has no
    valid session, instead of redirecting — this lets the SPA render its public
    pages without round-trips.

    Also exposes the per-request ``csrf_token`` (set by ``DashboardCSRFMiddleware``
    on every request) and the ``master_key_login_enabled`` flag so the SPA can
    submit guarded POSTs and conditionally render the admin-key form. The
    underlying ``dashboard_csrf`` cookie stays HttpOnly; the JSON copy is the
    only path JS has to read it.
    """
    # Lazy import: avoids circular import with .routes (which imports from
    # spa_routes is fine, but other dependents of routes.py shouldn't trigger
    # heavy imports here).
    from .routes import detect_language

    auth = get_dashboard_auth()
    admin_session = auth.get_session_from_request(request)
    user_session = auth.get_user_session_from_request(request)
    session = admin_session or user_session

    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)

    csrf_token = getattr(request.state, "csrf_token", None)
    master_key_login_enabled = _master_key_login_enabled()

    if not session:
        return JSONResponse(
            {
                "authenticated": False,
                "is_admin": False,
                "lang": lang,
                "csrf_token": csrf_token,
                "master_key_login_enabled": master_key_login_enabled,
                "max_sites_per_user": await _max_sites_per_user(),
            }
        )

    # Check is_admin against the *resolved* session, not just `admin_session`.
    # Master-key login intentionally swaps the admin session token for a user
    # session token (so the master admin can access My Sites etc.), which
    # left `admin_session` as None and forced `is_admin` to False even though
    # the user session dict carries role="admin". The SPA's RequireAuth then
    # redirected admin-only routes (Health, OAuth clients, Audit logs) back
    # to /sites for the master admin. Use `is_admin_session(session)` so the
    # check works regardless of which slot the cookie resolved into.
    is_admin = is_admin_session(session)
    user_id = None
    email = None
    name = None
    role = "user"
    sess_type = "oauth_user"

    # Extract fields defensively — DashboardSession and user-session dicts
    # have different shapes.
    if isinstance(session, dict):
        user_id = session.get("user_id") or session.get("uid")
        email = session.get("email")
        name = session.get("name")
        role = session.get("role") or ("admin" if is_admin else "user")
        sess_type = session.get("type") or "oauth_user"
    else:
        # DashboardSession dataclass
        user_id = getattr(session, "user_id", None) or getattr(session, "sid", None)
        email = getattr(session, "email", None)
        name = getattr(session, "name", None)
        role = getattr(session, "role", None) or ("admin" if is_admin else "user")
        sess_type = getattr(session, "type", None) or "master"
        if sess_type in {"master", "api_key"}:
            is_admin = True

    return JSONResponse(
        {
            "authenticated": True,
            "user_id": user_id,
            "email": email,
            "name": name,
            "role": role,
            "type": sess_type,
            "is_admin": bool(is_admin),
            "lang": lang,
            "csrf_token": csrf_token,
            "master_key_login_enabled": master_key_login_enabled,
            "max_sites_per_user": await _max_sites_per_user(),
        }
    )


async def api_i18n(request: Request) -> Response:
    """Return the dashboard translation dictionary for the requested language."""
    from .routes import DASHBOARD_TRANSLATIONS, get_translations

    lang = request.path_params.get("lang", "en")
    if lang not in DASHBOARD_TRANSLATIONS:
        lang = "en"
    return JSONResponse(get_translations(lang))


async def api_plugins(request: Request) -> Response:
    """Return the plugin catalog + per-plugin credential field definitions.

    Used by the SPA's Site Add/Edit dialog to render the correct form
    for the selected plugin without bouncing to the legacy Jinja page.
    Admins see every plugin; user sessions see only the ones flagged
    public by ``ENABLED_PLUGINS``. The shape mirrors the same map that
    the Jinja form binds to so backend validation stays identical.
    """
    auth = get_dashboard_auth()
    admin_session = auth.get_session_from_request(request)
    user_session = auth.get_user_session_from_request(request)
    if admin_session is None and user_session is None:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    from core.site_api import get_user_credential_fields, get_user_plugin_names

    is_admin = is_admin_session(admin_session or user_session)
    fields = get_user_credential_fields(is_admin=is_admin)
    names = get_user_plugin_names(is_admin=is_admin)

    plugins = [
        {"type": ptype, "name": names.get(ptype, ptype), "fields": flds}
        for ptype, flds in fields.items()
    ]
    plugins.sort(key=lambda p: p["name"].lower())
    return JSONResponse({"plugins": plugins})


async def serve_spa(_request: Request, status_code: int = 200) -> Response:
    """Serve the SPA's compiled ``index.html`` for any /dashboard/* path."""
    index = _spa_index_path()
    if not os.path.exists(index):
        # Friendly fallback when running before the first frontend build.
        return Response(
            (
                "<!doctype html><html><body style='font-family:sans-serif;padding:40px'>"
                "<h1>Dashboard SPA not built</h1>"
                "<p>Run <code>cd web && npm install && npm run build</code> to "
                "generate <code>core/templates/static/dist/index.html</code>, "
                "or use the legacy dashboard at "
                "<a href='/dashboard-legacy'>/dashboard-legacy</a>.</p>"
                "</body></html>"
            ),
            status_code=status_code,
            media_type="text/html",
        )
    return Response(
        _render_spa_index(index),
        status_code=status_code,
        media_type="text/html",
    )


async def redirect_dashboard_v2(request: Request) -> Response:
    """308 redirect old /dashboard-v2/* URLs to the new /dashboard/* prefix."""
    suffix = request.path_params.get("path", "")
    target = "/dashboard"
    if suffix:
        target += f"/{suffix}"
    elif request.url.path.endswith("/"):
        target += "/"
    if request.url.query:
        target += f"?{request.url.query}"
    return RedirectResponse(url=target, status_code=308)


def register_spa_routes(mcp: Any) -> None:
    """Register the SPA support routes on a FastMCP instance.

    Mounts:
      - ``/static/dist`` (StaticFiles) for hashed JS/CSS/asset bundles.
      - ``/api/me`` and ``/api/i18n/{lang}`` JSON endpoints.
      - ``/dashboard`` and ``/dashboard/{path:path}`` SPA index serving.
    """
    logger.info("Registering SPA (/dashboard) routes...")

    # JSON helpers
    mcp.custom_route("/api/me", methods=["GET"])(api_me)
    mcp.custom_route("/api/i18n/{lang}", methods=["GET"])(api_i18n)
    mcp.custom_route("/api/plugins", methods=["GET"])(api_plugins)

    # SPA catch-alls.  Both the bare path and any sub-path resolve to index.html
    # so react-router-dom can take over.
    mcp.custom_route("/dashboard", methods=["GET"])(serve_spa)
    mcp.custom_route("/dashboard/", methods=["GET"])(serve_spa)
    mcp.custom_route("/dashboard/{path:path}", methods=["GET"])(serve_spa)
    mcp.custom_route("/dashboard-v2", methods=["GET"])(redirect_dashboard_v2)
    mcp.custom_route("/dashboard-v2/", methods=["GET"])(redirect_dashboard_v2)
    mcp.custom_route("/dashboard-v2/{path:path}", methods=["GET"])(redirect_dashboard_v2)

    # Static assets (JS/CSS bundles) — only mount if dist/ exists, otherwise
    # FastMCP's underlying Starlette app refuses the mount on a missing dir.
    if os.path.isdir(SPA_DIST_DIR):
        try:
            # FastMCP exposes its inner Starlette app via .http_app() in v3+.
            # Fall back to .app if available.
            inner_app = None
            for attr in ("http_app", "app", "_app"):
                candidate = getattr(mcp, attr, None)
                inner_app = candidate() if callable(candidate) else candidate
                if inner_app is not None:
                    break
            if inner_app is not None and hasattr(inner_app, "mount"):
                inner_app.mount(
                    "/static/dist",
                    StaticFiles(directory=SPA_DIST_DIR, check_dir=False),
                    name="spa-dist",
                )
                logger.info("Mounted SPA static at /static/dist -> %s", SPA_DIST_DIR)
            else:
                # If we can't mount, fall back to a per-file route handler so
                # bundles still load.  This is slower but functional.
                async def _serve_dist_file(request: Request) -> Response:
                    rel = request.path_params.get("filename", "")
                    full = os.path.normpath(os.path.join(SPA_DIST_DIR, rel))
                    if not full.startswith(SPA_DIST_DIR) or not os.path.isfile(full):
                        return Response(status_code=404)
                    return FileResponse(full)

                mcp.custom_route("/static/dist/{filename:path}", methods=["GET"])(_serve_dist_file)
                logger.info("Registered fallback /static/dist/{path} route")
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Could not mount SPA static dir: %s", exc)
    else:
        logger.info(
            "SPA dist not present yet (%s); build with `cd web && npm run build`", SPA_DIST_DIR
        )

    logger.info("SPA routes registered successfully")
