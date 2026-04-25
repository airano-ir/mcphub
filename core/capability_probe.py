"""F.7e — per-site credential capability probe.

Each plugin's ``probe_capabilities()`` (defined on ``BasePlugin``) knows
how to ask its upstream service what the saved credential can actually
do. This module wraps those calls with:

* Per-site in-memory TTL cache (default 10 min) so the probe doesn't
  hammer the upstream service on every dashboard page view.
* A thin wrapper that decrypts the site's credentials, instantiates the
  plugin, calls the probe, and normalises the result.
* ``/api/sites/{id}/capabilities`` Starlette handler that the dashboard
  UI consumes (wired in ``core/dashboard/routes.py``).

The cache is process-local and not persisted. Workers start cold and
populate on demand; invalidation happens on cache expiry or explicit
site-credential update.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("mcphub.capability_probe")

# Cache TTL in seconds (default 10 min). Upstream capability rarely
# changes — most drift happens when the operator rotates an
# app_password or changes a Gitea token's scopes, both of which are
# infrequent.
_CACHE_TTL_SECONDS = int(os.environ.get("CAPABILITY_PROBE_TTL", "600"))


class _ProbeCache:
    """Trivial in-memory ``site_id -> (expires_at, payload)`` cache."""

    def __init__(self, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, site_id: str) -> dict[str, Any] | None:
        entry = self._entries.get(site_id)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            self._entries.pop(site_id, None)
            return None
        return payload

    def set(self, site_id: str, payload: dict[str, Any]) -> None:
        self._entries[site_id] = (time.time() + self._ttl, payload)

    def invalidate(self, site_id: str) -> bool:
        return self._entries.pop(site_id, None) is not None


_cache = _ProbeCache()


def get_probe_cache() -> _ProbeCache:
    return _cache


# ---------------------------------------------------------------------------
# F.7e — tier-fit evaluation: compare probe.granted with what the site's
# selected ``tool_scope`` actually needs.
# ---------------------------------------------------------------------------


# Capability names required for each (plugin_type, tier) pair. Tiers come
# from ``core/tool_access.py``. For plugins whose probe doesn't map 1:1
# onto these names (e.g. Gitea scopes use ``read:repository`` rather than
# ``read``) the fit evaluator's ``_aliased_granted`` helper below
# normalises both sides before comparing.
TIER_REQUIREMENTS: dict[str, dict[str, set[str]]] = {
    "wordpress": {
        "read": {"read"},
        "write": {"edit_posts", "upload_files"},
        # WP-admin-tier tools need the same cap as WP's admin area itself.
        "admin": {"manage_options"},
    },
    "woocommerce": {
        "read": {"read_products"},
        "write": {"write_products"},
        "admin": {"write_products"},
    },
    "gitea": {
        "read": {"read:repository"},
        "write": {"write:repository"},
        "admin": {"admin:repo_hook"},
    },
}

# Aliases that plugins may return from their probe which should be
# treated as equivalent to the canonical cap names in TIER_REQUIREMENTS.
# Keeps the adapter implementations honest about what the upstream
# service actually says while letting the evaluator compare sets.
_CAP_ALIASES: dict[str, set[str]] = {
    "manage_options": {"administrator", "manage_options"},
    "edit_posts": {"edit_posts", "editor", "administrator"},
    "upload_files": {"upload_files", "editor", "administrator"},
    "read": {"read", "subscriber", "contributor", "author", "editor", "administrator"},
    "read_products": {"read_products", "read", "read_write"},
    "write_products": {"write_products", "write", "read_write"},
    "read_orders": {"read_orders", "read", "read_write"},
    "write_orders": {"write_orders", "write", "read_write"},
}


def _cap_matches(required: str, granted: set[str]) -> bool:
    """Return True if ``required`` is satisfied by any cap in ``granted``.

    Uses ``_CAP_ALIASES`` to accept role names (WP) and permission
    strings (WC) alongside the canonical capability names.
    """
    if required in granted:
        return True
    aliases = _CAP_ALIASES.get(required, {required})
    return bool(aliases & granted)


def evaluate_tier_fit(
    plugin_type: str,
    tier: str | None,
    probe_payload: dict[str, Any],
) -> dict[str, Any]:
    """Decide whether ``probe.granted`` covers what ``tier`` requires.

    Args:
        plugin_type: e.g. "wordpress", "woocommerce", "gitea".
        tier: the site's selected ``tool_scope`` preset (read / write /
            admin / custom / None).
        probe_payload: the dict returned by ``probe_site_capabilities``
            (must contain ``probe_available`` and ``granted``).

    Returns:
        A dict with:
          * ``status``: one of ``ok`` | ``warning`` | ``probe_unavailable``
            | ``unknown_tier``.
          * ``required``: list[str] of caps the tier needs (empty when
            the tier is ``custom`` / not in the table).
          * ``missing``: list[str] of required caps not present in
            ``granted``.
          * ``reason``: passthrough from the probe when probe is
            unavailable, else ``None``.

    ``custom`` tier always returns ``status='ok'`` because by definition
    the caller picked individual tools — we can't check a tier-level
    contract.
    """
    tier_norm = (tier or "").strip().lower()

    if not probe_payload.get("probe_available", False):
        return {
            "status": "probe_unavailable",
            "required": [],
            "missing": [],
            "reason": probe_payload.get("reason"),
        }

    if tier_norm in {"", "custom"}:
        return {
            "status": "ok",
            "required": [],
            "missing": [],
            "reason": None,
        }

    requirements = (TIER_REQUIREMENTS.get(plugin_type) or {}).get(tier_norm)
    if requirements is None:
        return {
            "status": "unknown_tier",
            "required": [],
            "missing": [],
            "reason": f"no_tier_table_for:{plugin_type}/{tier_norm}",
        }

    # F.X.fix #5: the probe places WP role names under ``roles`` and
    # individual capability strings under ``granted`` — historically we
    # only compared against ``granted``, so the ``read`` tier always
    # reported ``warning: Missing read`` even for admin users, because
    # ``read`` is implied by every role but not emitted as a bare cap
    # in the companion's capability map. Union the two sets so the
    # alias resolver in ``_cap_matches`` can see roles too.
    granted = set(probe_payload.get("granted") or [])
    roles = set(probe_payload.get("roles") or [])
    effective = granted | roles
    missing = sorted(cap for cap in requirements if not _cap_matches(cap, effective))

    return {
        "status": "warning" if missing else "ok",
        "required": sorted(requirements),
        "missing": missing,
        "reason": None,
    }


async def probe_site_capabilities(
    site_id: str,
    user_id: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Return the capability probe payload for a user-owned site.

    Uses a 10-minute per-site TTL cache unless ``force=True``.
    Response shape:

        {
            "site_id": str,
            "plugin_type": str,
            "probe_available": bool,
            "granted": list[str],
            "source": str,
            "reason": str | None,       # only when probe_available=False
            "cached": bool,
            # + any plugin-specific extras (roles, plugin_version, ...)
        }
    """
    from core.database import get_database
    from core.encryption import get_credential_encryption
    from plugins import registry as plugin_registry

    db = get_database()
    site = await db.get_site(site_id, user_id)
    if site is None:
        return {
            "site_id": site_id,
            "plugin_type": None,
            "probe_available": False,
            "granted": [],
            "source": "unavailable",
            "reason": "site_not_found",
            "cached": False,
        }

    if not force:
        cached = _cache.get(site_id)
        if cached is not None:
            out = dict(cached)
            out["cached"] = True
            return out

    plugin_type = site["plugin_type"]
    if not plugin_registry.is_registered(plugin_type):
        return {
            "site_id": site_id,
            "plugin_type": plugin_type,
            "probe_available": False,
            "granted": [],
            "source": "unavailable",
            "reason": f"plugin_not_registered:{plugin_type}",
            "cached": False,
        }

    try:
        encryptor = get_credential_encryption()
        credentials = encryptor.decrypt_credentials(site["credentials"], site_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability_probe: decrypt failed for site %s: %s", site_id, exc)
        return {
            "site_id": site_id,
            "plugin_type": plugin_type,
            "probe_available": False,
            "granted": [],
            "source": "unavailable",
            "reason": "credentials_decrypt_failed",
            "cached": False,
        }

    config_dict: dict[str, Any] = {
        "site_url": site["url"],
        "url": site["url"],
        "alias": site["alias"],
        "user_id": user_id,
        "site_id": site_id,
        **credentials,
    }

    try:
        instance = plugin_registry.create_instance(
            plugin_type,
            project_id=f"probe_{site_id}",
            config=config_dict,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability_probe: plugin instantiation failed for %s: %s", site_id, exc)
        return {
            "site_id": site_id,
            "plugin_type": plugin_type,
            "probe_available": False,
            "granted": [],
            "source": "unavailable",
            "reason": f"plugin_instantiation_failed: {exc}",
            "cached": False,
        }

    try:
        result = await instance.probe_credential_capabilities()
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability_probe: probe call raised for site %s: %s", site_id, exc)
        result = {
            "probe_available": False,
            "granted": [],
            "source": "unavailable",
            "reason": f"probe_call_failed: {exc}",
        }

    payload: dict[str, Any] = {
        "site_id": site_id,
        "plugin_type": plugin_type,
        "probe_available": bool(result.get("probe_available", False)),
        "granted": list(result.get("granted") or []),
        "source": result.get("source") or "unavailable",
    }
    if not payload["probe_available"]:
        payload["reason"] = result.get("reason")
    # F.X.fix #3: propagate install_hint so the dashboard can render
    # the "site unreachable / install companion" prompt without a
    # second probe call.
    # F.X.fix-pass3: also propagate routes + features so the
    # tool-prerequisites resolver in core/tool_access can compute
    # tool availability without a second probe call.
    # F.X.fix-pass5: also propagate wp_credentials_present so the
    # prerequisites resolver can auto-disable WC media tools when
    # the site has no WP Application Password configured.
    for extra in (
        "roles",
        "plugin_version",
        "install_hint",
        "routes",
        "features",
        "wp_credentials_present",
    ):
        if extra in result:
            payload[extra] = result[extra]

    # F.X.fix-pass2 — surface the site's configured AI-provider set so
    # the badge can show a distinct "no AI provider key" warning
    # independent of tier fit. Even an Administrator WP credential
    # can't run the AI image tool without a provider key. Cheap: one
    # SQLite query over site_provider_keys.
    try:
        from core.site_api import list_site_providers_set

        payload["ai_providers_configured"] = sorted(await list_site_providers_set(site_id))
    except Exception as exc:  # noqa: BLE001
        logger.debug("capability_probe: provider-set lookup skipped for %s: %s", site_id, exc)
        payload["ai_providers_configured"] = []

    # Cache everything, including the "probe unavailable" answer — a
    # missing companion plugin is a stable fact until the operator
    # installs it and re-tests the connection.
    _cache.set(site_id, payload)
    payload_out = dict(payload)
    payload_out["cached"] = False
    return payload_out


# ---------------------------------------------------------------------------
# Starlette handler: GET /api/sites/{id}/capabilities
# ---------------------------------------------------------------------------


async def api_site_capabilities(request: Request) -> JSONResponse:
    """Return the capability probe for a user-owned site.

    Auth: same OAuth user session guard as the other site endpoints.
    Query params:
      * ``force=1`` — bypass the 10-minute cache.
    """
    from core.dashboard.routes import _require_user_session

    user_session, redirect = _require_user_session(request)
    if redirect or user_session is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    site_id = (request.path_params.get("id") or "").strip()
    if not site_id:
        return JSONResponse({"ok": False, "error": "invalid_request"}, status_code=400)

    force = request.query_params.get("force") in {"1", "true", "True"}

    payload = await probe_site_capabilities(
        site_id=site_id, user_id=user_session["user_id"], force=force
    )

    if payload.get("reason") == "site_not_found":
        return JSONResponse({"ok": False, "error": "site_not_found"}, status_code=404)

    # F.7e: also evaluate fit against the site's currently-selected
    # tool_scope tier so the UI can render the badge without needing a
    # second request. The caller-supplied ?tier=... query param lets the
    # dashboard preview a tier before save.
    from core.database import get_database

    db = get_database()
    site = await db.get_site(site_id, user_session["user_id"])
    site_tier = (site or {}).get("tool_scope")
    # Allow the caller to override the tier (e.g. preview before save).
    tier_override = request.query_params.get("tier")
    tier = tier_override or site_tier

    fit = evaluate_tier_fit(
        plugin_type=payload.get("plugin_type") or "",
        tier=tier,
        probe_payload=payload,
    )

    return JSONResponse(
        {
            "ok": True,
            **payload,
            "tier": tier,
            "fit": fit,
        }
    )


async def api_site_capabilities_badge(request: Request):
    """F.X.fix #9 — render the capability-badge template fragment.

    Used by the HTMX Re-check button so the badge swaps in place
    instead of forcing a full-page reload. Response is HTML (not JSON)
    — the caller sets ``hx-swap="outerHTML"`` on the badge element.
    """
    from starlette.responses import HTMLResponse

    from core.dashboard.routes import _require_user_session, templates

    user_session, redirect = _require_user_session(request)
    if redirect or user_session is None:
        return HTMLResponse("<div>unauthorized</div>", status_code=401)

    site_id = (request.path_params.get("id") or "").strip()
    if not site_id:
        return HTMLResponse("<div>invalid_request</div>", status_code=400)

    force = request.query_params.get("force") in {"1", "true", "True"}

    payload = await probe_site_capabilities(
        site_id=site_id, user_id=user_session["user_id"], force=force
    )
    if payload.get("reason") == "site_not_found":
        return HTMLResponse("<div>site_not_found</div>", status_code=404)

    from core.database import get_database

    db = get_database()
    site = await db.get_site(site_id, user_session["user_id"])
    if site is None:
        return HTMLResponse("<div>site_not_found</div>", status_code=404)

    tier = request.query_params.get("tier") or site.get("tool_scope")
    fit = evaluate_tier_fit(
        plugin_type=payload.get("plugin_type") or "",
        tier=tier,
        probe_payload=payload,
    )
    capability_probe = {**payload, "tier": tier, "fit": fit}

    # Pull up the companion download URL the same way the page does.
    try:
        from plugins.wordpress.handlers._companion_hint import COMPANION_DOWNLOAD_URL

        companion_download_url: str | None = COMPANION_DOWNLOAD_URL
    except Exception:  # noqa: BLE001
        companion_download_url = None

    lang = request.query_params.get("lang") or request.cookies.get("lang") or "en"
    return templates.TemplateResponse(
        request,
        "dashboard/sites/_capability_badge.html",
        {
            "capability_probe": capability_probe,
            "site": site,
            "lang": lang,
            "companion_download_url": companion_download_url,
        },
    )
