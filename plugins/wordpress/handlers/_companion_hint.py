"""Shared ``companion_unreachable`` error-hint helper.

Every companion-backed handler (cache_purge, bulk_meta, export,
site_health, transient_flush, audit_hook, regenerate_thumbnails,
capabilities) returns a structured JSON error when the companion
plugin isn't installed / reachable. This module provides a single
helper so the hint message, download URL, and install instructions
stay in sync.

F.20 will swap the download URL constant from the GitHub raw path to
``wordpress.org/plugins/airano-mcp-bridge/`` once the wp.org listing
is live. At that point a single edit here + the dashboard template
(``core/templates/dashboard/sites/manage.html``) covers everything.
"""

from __future__ import annotations

# Single source of truth for the companion download URL. Mirror of the
# constant used in ``core/dashboard/routes.py``. Kept as a plain string
# rather than imported to avoid a core→plugin import cycle.
COMPANION_DOWNLOAD_URL = (
    "https://github.com/airano-ir/mcphub/raw/main/" "wordpress-plugin/airano-mcp-bridge.zip"
)


def companion_install_hint(
    *,
    min_version: str,
    required_capability: str = "manage_options",
    route: str | None = None,
) -> dict[str, str]:
    """Return a ``hint`` dict that every companion-backed handler can
    merge into its ``companion_unreachable`` payload.

    Args:
        min_version: Earliest companion plugin version that exposes the
            route this handler uses (e.g. ``"2.4.0"``). Surfaced in the
            install hint so the user knows what they need.
        required_capability: WordPress capability the calling user needs
            for the companion route. Default ``manage_options``.
        route: Optional route path — included in the hint when set so
            the user can sanity-check by hitting the endpoint directly.

    Returns:
        Dict with ``install_url``, ``install_instructions``, and
        ``required_capability``. Callers merge into their existing
        structured error response alongside ``error`` / ``message``.
    """
    instructions = (
        f"Install the Airano MCP Bridge companion plugin (v{min_version}+) "
        "on the WordPress site. Download the zip, then in the WP admin: "
        "Plugins → Add New → Upload Plugin → select the file → Activate. "
        f"Ensure the Application Password user has the ``{required_capability}`` "
        "capability. Run ``wordpress_probe_capabilities`` to verify the "
        "route is advertised."
    )
    out = {
        "install_url": COMPANION_DOWNLOAD_URL,
        "install_instructions": instructions,
        "required_capability": required_capability,
        "companion_min_version": min_version,
    }
    if route:
        out["route"] = route
    return out
