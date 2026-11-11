"""Site management logic for the Live Platform (Track E.3).

Provides site CRUD operations, connection validation, and credential
field definitions for supported plugin types. Coordinates between the
database, encryption, and plugin health check layers.

Usage:
    from core.site_api import create_user_site, get_user_sites, validate_site_connection

    ok, msg = await validate_site_connection("wordpress", "https://example.com", creds)
    site = await create_user_site(user_id, "wordpress", "myblog", url, creds)
"""

import asyncio
import json
import logging
import os
from typing import Any

import aiohttp
import httpx

logger = logging.getLogger(__name__)

# Fallback used when the settings DB is unavailable at import time
_MAX_SITES_FALLBACK = int(os.getenv("MAX_SITES_PER_USER", "10"))

# Plugin credential field definitions — drives the dynamic "Add Site" form
# and server-side validation. Each field has:
#   name:     form input name (matches credential JSON key)
#   label:    display label
#   type_:    "text" or "password"
#   required: whether the field is mandatory
PLUGIN_CREDENTIAL_FIELDS: dict[str, list[dict[str, Any]]] = {
    "wordpress": [
        {
            "name": "username",
            "label": "Username",
            "type": "text",
            "required": True,
            "hint": "Your WordPress admin username (used as the HTTP Basic username for every API call).",
        },
        {
            "name": "app_password",
            "label": "Application Password",
            "type": "password",
            "required": True,
            "hint": (
                "WordPress Admin → Users → Profile → Application Passwords. "
                "This IS the API credential — no separate API key is needed. "
                "Paste the value WP shows once after creation (spaces can stay or be removed)."
            ),
        },
    ],
    "woocommerce": [
        {
            "name": "consumer_key",
            "label": "Consumer Key",
            "type": "text",
            "required": True,
            "hint": (
                "WooCommerce → Settings → Advanced → REST API → Add Key. "
                "Read/Write permission. This pair IS the API auth — no extra API key field exists."
            ),
        },
        {
            "name": "consumer_secret",
            "label": "Consumer Secret",
            "type": "password",
            "required": True,
            "hint": (
                "Shown once when the REST API key is created. "
                "Starts with ``cs_``. Save it immediately — WooCommerce will not display it again."
            ),
        },
        # F.X.fix-pass4 — optional WP Application Password, only used by
        # media tools (upload_and_attach_to_product / attach_media_to_
        # product / set_featured_image). WooCommerce's Consumer Key +
        # Secret authenticate ``/wc/v3/*`` but NOT ``/wp/v2/media``;
        # WordPress core REST media uploads require an Application
        # Password from the WP admin user. Leave blank if the store
        # never needs MCP-driven image uploads.
        {
            "name": "wp_username",
            "label": "WordPress Username (for media tools)",
            "type": "text",
            "required": False,
            "advanced": True,
            "hint": (
                "Only required if you want the AI / media tools "
                "(upload_and_attach_to_product, attach_media_to_product, "
                "set_featured_image, generate_and_upload_image with attach_to_post). "
                "Other WC tools work with Consumer Key / Secret alone."
            ),
        },
        {
            "name": "wp_app_password",
            "label": "WordPress Application Password (for media tools)",
            "type": "password",
            "required": False,
            "advanced": True,
            "hint": (
                "WP Admin → Users → Profile → Application Passwords. "
                "WC media uploads hit /wp/v2/media which only accepts "
                "Application Passwords (not Consumer Key / Secret). "
                "Leave empty if you don't use MCP for image uploads."
            ),
        },
    ],
    # F.19.1 WordPress Specialist — companion-backed, no Docker socket.
    # Same auth shape as the basic wordpress plugin (Application Password)
    # but the WP user behind the password must have ``manage_options``,
    # AND Airano MCP Bridge v2.11.0+ must be active on the WP site for
    # the admin namespace to exist.
    "wordpress_specialist": [
        {
            "name": "username",
            "label": "Username",
            "type": "text",
            "required": True,
            "hint": "WordPress admin username (the user that owns the Application Password).",
        },
        {
            "name": "app_password",
            "label": "Application Password",
            "type": "password",
            "required": True,
            "hint": (
                "WordPress Admin → Users → Profile → Application Passwords. "
                "The user MUST have manage_options. Requires Airano MCP "
                "Bridge v2.11.0+ on the WP side — install from "
                "wordpress-plugin/airano-mcp-bridge.zip in the repo."
            ),
        },
    ],
    "gitea": [
        {
            "name": "token",
            "label": "Access Token",
            "type": "password",
            "required": True,
            "hint": "Gitea → Settings → Applications → Generate Token",
        },
    ],
    "n8n": [
        {
            "name": "api_key",
            "label": "API Key",
            "type": "password",
            "required": True,
            "hint": "n8n → Settings → API → Create API Key",
        },
    ],
    "supabase": [
        {
            "name": "service_role_key",
            "label": "Service Role Key",
            "type": "password",
            "required": True,
            "hint": (
                "Supabase Dashboard → Settings → API → service_role key. "
                "Note: On supabase.com cloud, postgres-meta tools "
                "(list_tables, execute_sql, get_table_schema, etc.) are not available — "
                "they only work on self-hosted Supabase."
            ),
        },
        {
            "name": "anon_key",
            "label": "Anon Key (Optional)",
            "type": "password",
            "required": False,
            "advanced": True,
            "hint": (
                "Supabase Dashboard → Settings → API → anon key. "
                "Optional — if omitted, service_role_key is used for all calls. "
                "Only useful for testing RLS policies as a regular user."
            ),
        },
        {
            "name": "meta_url",
            "label": "postgres-meta URL (Optional)",
            "type": "text",
            "required": False,
            "advanced": True,
            "hint": (
                "Only needed if your Supabase setup does not expose /pg/ through Kong. "
                "Most self-hosted installs (including Coolify) work without this. "
                "Example: http://supabase-meta:8080 or https://your-meta.example.com"
            ),
        },
        {
            "name": "meta_auth",
            "label": "postgres-meta Auth (Optional)",
            "type": "password",
            "required": False,
            "advanced": True,
            "hint": (
                "Basic Auth for postgres-meta (format: username:password). "
                "Only needed when postgres-meta is exposed via a public URL."
            ),
        },
    ],
    "openpanel": [
        {
            "name": "client_id",
            "label": "Client ID",
            "type": "text",
            "required": True,
            "hint": "Open your project on dashboard.openpanel.dev → Settings → Clients (URL: dashboard.openpanel.dev/{org}/{project-id}/settings/clients). Create a client in 'root' mode for full access.",
        },
        {
            "name": "client_secret",
            "label": "Client Secret",
            "type": "password",
            "required": True,
            "hint": "Generated with your Client ID",
        },
        {
            "name": "project_id",
            "label": "Project ID",
            "type": "text",
            "required": False,
            "hint": "From dashboard URL: dashboard.openpanel.dev/{org}/{project-id}/ — sets default for Export & Insights tools",
        },
        {
            "name": "organization_id",
            "label": "Organization ID",
            "type": "text",
            "required": False,
            "hint": "From dashboard URL: dashboard.openpanel.dev/{org}/{project-id}/",
            "advanced": True,
        },
    ],
    "coolify": [
        {
            "name": "token",
            "label": "API Token",
            "type": "password",
            "required": True,
            "hint": "Coolify → Keys & Tokens → API tokens → Create",
        },
        {
            "name": "read_only",
            "label": "Read-only mode",
            "type": "checkbox",
            "required": False,
            "advanced": True,
            "hint": "Optional. Hide and block mutating Coolify tools for this site.",
        },
        {
            "name": "project_uuid",
            "label": "Allowed Project UUID",
            "type": "text",
            "required": False,
            "advanced": True,
            "hint": "Optional. Restrict this Coolify site to one project UUID.",
        },
        {
            "name": "allowed_project_uuids",
            "label": "Allowed Project UUIDs",
            "type": "text",
            "required": False,
            "advanced": True,
            "hint": "Optional. Comma-separated Coolify project UUID allowlist for least-privilege agents.",
        },
    ],
    # Gmail — OAuth (gmail.modify). There is no per-site URL; the Gmail API
    # host is fixed. The dashboard's "Add Site" form has a required URL
    # field, so enter https://gmail.googleapis.com there (the plugin
    # ignores it). Credentials are produced by the one-time bootstrap
    # script plugins/gmail/bootstrap/get_refresh_token.py and pasted here.
    "gmail": [
        {
            "name": "client_id",
            "label": "OAuth Client ID",
            "type": "text",
            "required": True,
            "hint": (
                "GCP Console → APIs & Services → Credentials → OAuth client ID "
                "(type: Desktop app). The numeric ID ending in .apps.googleusercontent.com."
            ),
        },
        {
            "name": "client_secret",
            "label": "OAuth Client Secret",
            "type": "password",
            "required": True,
            "hint": "The client secret paired with the Client ID above (GOCSPX-…).",
        },
        {
            "name": "refresh_token",
            "label": "Refresh Token",
            "type": "password",
            "required": True,
            "hint": (
                "Run plugins/gmail/bootstrap/get_refresh_token.py once locally to produce "
                "this. Long-lived (gmail.modify scope). Stored encrypted in MCPHub."
            ),
        },
        {
            "name": "user_email",
            "label": "Account Email (optional)",
            "type": "text",
            "required": False,
            "advanced": True,
            "hint": "Optional. The Gmail account email, for display/diagnostics only.",
        },
    ],
    "google_search_console": [
        {
            "name": "access_token",
            "label": "Access Token",
            "type": "password",
            "required": False,
            "internal": True,
            "hint": "Auto-managed by the OAuth flow — do not edit manually.",
        },
        {
            "name": "refresh_token",
            "label": "Refresh Token",
            "type": "password",
            "required": False,
            "internal": True,
            "hint": "Auto-populated by the OAuth flow — do not edit manually.",
        },
        {
            "name": "token_expires_at",
            "label": "Token Expires At",
            "type": "text",
            "required": False,
            "internal": True,
            "hint": "Auto-managed by the OAuth flow.",
        },
    ],
    # Cloudflare — static API token. There is no per-user URL; the API base
    # is fixed (see FIXED_PLUGIN_URLS) and the dashboard hides the URL field
    # for this plugin type. api_token is required; account_id is optional —
    # when blank the client auto-discovers the first account the token can
    # see (needs Account:Read), otherwise pin it for Workers/KV/R2 tools.
    "cloudflare": [
        {
            "name": "api_token",
            "label": "API Token",
            "type": "password",
            "required": True,
            "hint": (
                "Cloudflare dashboard → My Profile → API Tokens → Create Token. "
                "Use a scoped token with only the permissions you need, e.g. "
                "Zone:DNS:Edit, Zone:Cache Purge, Account:Workers Scripts:Read, "
                "Account:Workers KV Storage:Edit, Account:R2:Edit. Start read-only "
                "and expand as needed."
            ),
        },
        {
            "name": "account_id",
            "label": "Account ID (optional)",
            "type": "text",
            "required": False,
            "advanced": True,
            "hint": (
                "Cloudflare dashboard sidebar → Account ID. Only needed for "
                "Workers/KV/R2 tools (they are account-scoped). If blank, the "
                "plugin tries to discover the first account your token can see "
                "(requires Account:Read on the token)."
            ),
        },
    ],
}

# Plugin types that talk to a fixed third-party API base instead of a
# per-user site URL. The dashboard hides the URL field for these and sends
# the fixed value on create/edit (the plugin ignores it at call time).
FIXED_PLUGIN_URLS: dict[str, str] = {
    "cloudflare": "https://api.cloudflare.com",
}

# Plugin display names for UI
PLUGIN_DISPLAY_NAMES: dict[str, str] = {
    "wordpress": "WordPress",
    "woocommerce": "WooCommerce",
    "wordpress_specialist": "WordPress Specialist",
    "gitea": "Gitea",
    "n8n": "n8n",
    "supabase": "Supabase",
    "openpanel": "OpenPanel",
    "coolify": "Coolify",
    "gmail": "Gmail",
    "google_search_console": "Google Search Console",
    "cloudflare": "Cloudflare",
}

# Health check endpoints per plugin type
_HEALTH_ENDPOINTS: dict[str, dict[str, Any]] = {
    "wordpress": {"path": "/wp-json/wp/v2/users/me", "method": "GET"},
    "woocommerce": {"path": "/wp-json/wc/v3/system_status", "method": "GET"},
    # F.19.1: hits the companion's lightest admin route. Returns 404 if
    # Airano MCP Bridge v2.11.0+ is missing, 403 if the user lacks
    # ``manage_options``, 200 with a small JSON body otherwise. This
    # makes "Test Connection" surface the actual end-to-end requirement
    # instead of just "auth works" (which /users/me would).
    "wordpress_specialist": {"path": "/wp-json/airano-mcp/v1/admin/maintenance", "method": "GET"},
    "gitea": {"path": "/api/v1/user", "method": "GET"},
    "n8n": {"path": "/healthz", "method": "GET"},
    "supabase": {"path": "/rest/v1/", "method": "GET"},
    "openpanel": {"path": "/healthcheck", "method": "GET"},
    "coolify": {"path": "/api/v1/version", "method": "GET"},
    # OAuth-based plugins — health check uses the Google API directly
    # with the stored access token (Bearer auth).  These use absolute
    # URLs, not relative paths appended to the site URL.
    # Gmail has no unauthenticated probe. Test Connection runs a real
    # refresh-token exchange + users.getProfile; see the gmail branch below.
    "gmail": {
        "path": "/gmail/v1/users/me/profile",
        "method": "GET",
        "base_url": "https://gmail.googleapis.com",
        "oauth": True,
        "manual": True,  # credentials entered manually (bootstrap script)
    },
    "google_search_console": {
        "path": "/webmasters/v3/sites",
        "method": "GET",
        "base_url": "https://www.googleapis.com",
        "oauth": True,
    },
    # Cloudflare — static API token against the fixed v4 API. The dedicated
    # _validate_cloudflare_connection branch below does the real check
    # (GET /user/tokens/verify — works with any token, no extra permission).
    "cloudflare": {
        "path": "/user/tokens/verify",
        "method": "GET",
        "base_url": "https://api.cloudflare.com/client/v4",
    },
}


def guard_site_url_ssrf(url: str, *, allow_private: bool = False) -> tuple[bool, str]:
    """Reject user-supplied site URLs that resolve to internal/private hosts.

    The connection test fetches ``url + health_path`` directly, so without
    this guard any authenticated user could point a site at an internal
    address (``http://127.0.0.1:…``, ``http://10.x``, cloud metadata, a
    Docker-network service) and use the "Test Connection" error — which
    reflects the upstream response body — as an SSRF read primitive and
    internal port scanner.

    This is the *pre-flight* half of the defence: it gives an early, friendly
    error. It cannot see redirects or DNS rebinding, so every request to a
    user site must also go through :func:`core.net_guard.client_session`,
    which enforces the same policy at connection time.

    Reuses the ``ssrf_check`` guard already applied to media and AI-provider
    URLs (DNS-resolves the host and rejects any non-public destination).
    ``http`` is permitted because the connection test already accepts
    ``http`` site URLs; only the destination IP is constrained. The lookup is
    blocking — call it via ``asyncio.to_thread`` from async code.

    Private destinations are allowed when the operator sets
    ``ALLOW_PRIVATE_SITE_URLS=true`` (self-hosters whose services live on the
    hub's internal network) or when ``allow_private`` is set (admin-owned
    sites — the same trust boundary as the admin site-limit exemption).

    Returns:
        ``(True, "")`` if allowed, else ``(False, reason)``.
    """
    from core.net_guard import private_destinations_allowed

    if allow_private or private_destinations_allowed():
        return True, ""

    from plugins.wordpress.handlers._media_security import ssrf_check

    result = ssrf_check(url, allow_http=True)
    if not result.allowed:
        return False, result.reason or "URL rejected by SSRF guard"
    return True, ""


def get_credential_fields(plugin_type: str) -> list[dict[str, Any]]:
    """Get credential field definitions for a plugin type.

    Args:
        plugin_type: Plugin type name.

    Returns:
        List of field definition dicts.

    Raises:
        ValueError: If plugin_type is unknown.
    """
    fields = PLUGIN_CREDENTIAL_FIELDS.get(plugin_type)
    if fields is None:
        raise ValueError(
            f"Unknown plugin type '{plugin_type}'. "
            f"Valid: {list(PLUGIN_CREDENTIAL_FIELDS.keys())}"
        )
    return fields


def get_user_credential_fields(is_admin: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Get credential fields for the dashboard's Add/Edit Site forms.

    Admin users see every registered plugin so they can use admin-only
    plugins (wordpress_specialist) without having to add them to
    ``ENABLED_PLUGINS`` for everyone. Public users get only the plugins
    enabled via ``ENABLED_PLUGINS`` env var (Track F.1).

    F.19.1 (2026-05-01) — surfaced when an admin OAuth user added a
    wordpress_specialist site and the manage page rendered an empty
    credential form on revisit because the unfiltered map was being
    filtered for public visibility. The site row exists but the
    template can't render its fields.

    Args:
        is_admin: When True, return every plugin's credential fields.
            Defaults to False for backward compatibility.

    Returns:
        Dict of plugin_type -> field definitions.
    """
    if is_admin:
        return dict(PLUGIN_CREDENTIAL_FIELDS)

    from core.plugin_visibility import get_public_plugin_types

    public = get_public_plugin_types()
    return {k: v for k, v in PLUGIN_CREDENTIAL_FIELDS.items() if k in public}


def get_user_plugin_names(is_admin: bool = False) -> dict[str, str]:
    """Get plugin display names for the dashboard's plugin pickers.

    Admin users see every registered plugin (so the Add Site dropdown
    surfaces ``wordpress_specialist`` etc.); public users get only the
    plugins enabled via ``ENABLED_PLUGINS`` env var.

    Args:
        is_admin: When True, return every plugin's display name.
            Defaults to False for backward compatibility.

    Returns:
        Dict of plugin_type -> display name.
    """
    if is_admin:
        return dict(PLUGIN_DISPLAY_NAMES)

    from core.plugin_visibility import get_public_plugin_types

    public = get_public_plugin_types()
    return {k: v for k, v in PLUGIN_DISPLAY_NAMES.items() if k in public}


def validate_credentials(plugin_type: str, credentials: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate that all required credential fields are present and non-empty.

    OAuth-based plugin types (gmail, google_search_console) have no
    manually-entered required fields — their credentials are auto-populated
    by the OAuth flow.  This function skips validation for those types.

    Args:
        plugin_type: Plugin type name.
        credentials: Dict of credential key→value.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    from core.site_oauth import OAUTH_PLUGIN_TYPES

    # OAuth plugins: no static credential validation — the OAuth flow
    # populates access_token / refresh_token automatically.
    if plugin_type in OAUTH_PLUGIN_TYPES:
        return True, []

    fields = get_credential_fields(plugin_type)
    errors: list[str] = []

    for field in fields:
        # Skip internal fields (auto-managed by OAuth or the system)
        if field.get("internal"):
            continue
        if field["required"]:
            value = _credential_value_to_string(credentials.get(field["name"], "")).strip()
            if not value:
                errors.append(f"'{field['label']}' is required")

    return (len(errors) == 0, errors)


def _credential_value_to_string(value: Any) -> str:
    """Normalize dashboard credential values before validation/storage."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else ""
    return str(value)


def _clean_credentials(plugin_type: str, credentials: dict[str, Any]) -> dict[str, str]:
    """String-normalize credentials and drop empty optional values.

    Internal fields (marked ``internal: True`` in the field definition) are
    preserved even if empty — they may be auto-populated by the OAuth flow
    or the system.
    """
    field_defs = {f["name"]: f for f in PLUGIN_CREDENTIAL_FIELDS.get(plugin_type, [])}
    cleaned: dict[str, str] = {}
    for key, value in credentials.items():
        normalized = _credential_value_to_string(value).strip()
        is_internal = field_defs.get(key, {}).get("internal", False)
        if normalized:
            cleaned[key] = normalized
        elif is_internal:
            # Preserve internal fields as-is (may be empty before OAuth flow)
            cleaned[key] = normalized
        elif field_defs.get(key, {}).get("required", True):
            cleaned[key] = ""
    return cleaned


async def _validate_gmail_connection(credentials: dict[str, str]) -> tuple[bool, str]:
    """Test Gmail access by refreshing the OAuth token and fetching the profile.

    Gmail has no unauthenticated probe, so Test Connection must do a real
    refresh-token exchange (proving client_id/secret/refresh_token are valid
    together) then ``GET users/me/profile`` (proving the gmail.modify scope
    is granted). Returns a clear diagnostic on each failure mode.

    Args:
        credentials: Plaintext credential dict with client_id,
            client_secret, refresh_token.

    Returns:
        Tuple of (success, message).
    """
    client_id = credentials.get("client_id", "")
    client_secret = credentials.get("client_secret", "")
    refresh_token = credentials.get("refresh_token", "")
    if not (client_id and client_secret and refresh_token):
        return False, "Missing client_id / client_secret / refresh_token"

    # 1. Refresh the access token.
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    msg = body.get("error_description") or body.get("error") or str(body)
                    return False, f"Token refresh failed: {msg}"
                access_token = body.get("access_token")
                if not access_token:
                    return False, "Token refresh returned no access_token"
    except aiohttp.ClientConnectorError:
        return False, "Connection failed — cannot reach oauth2.googleapis.com"
    except TimeoutError:
        return False, "Token refresh timed out (15s)"
    except Exception as e:  # noqa: BLE001
        return False, f"Token refresh error: {type(e).__name__}: {e}"

    # 2. Fetch the profile (proves gmail.modify is granted).
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                if resp.status == 200:
                    profile = await resp.json()
                    email = profile.get("emailAddress", "?")
                    return True, f"OK — Gmail account {email} accessible"
                if resp.status == 401:
                    return (
                        False,
                        "Profile fetch auth failed — refresh token may lack gmail.modify scope",
                    )
                if resp.status == 403:
                    return (
                        False,
                        "Profile fetch forbidden — check Gmail API is enabled + scope granted",
                    )
                text = await resp.text()
                return False, f"Profile fetch HTTP {resp.status}: {text[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, f"Profile fetch error: {type(e).__name__}: {e}"


async def _validate_oauth_site_connection(
    plugin_type: str,
    credentials: dict[str, str],
    endpoint_info: dict[str, Any],
) -> tuple[bool, str]:
    """Health-check an OAuth-based site connection.

    Uses the stored ``access_token`` to call the provider's API.  If the
    token is missing or expired, attempts a refresh first.  When the
    refresh fails with ``invalid_grant``, returns a message instructing
    the user to re-authorize.

    Args:
        plugin_type: Plugin type name (e.g. ``"gmail"``).
        credentials: Plaintext credential dict (must contain
            ``access_token`` and optionally ``refresh_token`` +
            ``token_expires_at``).
        endpoint_info: Health endpoint config dict with ``base_url``,
            ``path``, and ``method``.

    Returns:
        Tuple of (success, message).
    """
    import time as _time

    from core.site_oauth import InvalidGrantError, get_site_oauth_manager

    access_token = credentials.get("access_token", "")
    refresh_token = credentials.get("refresh_token", "")
    token_expires_at = credentials.get("token_expires_at", "")

    # Check if the access token is expired (or missing)
    needs_refresh = not access_token
    if token_expires_at:
        try:
            from datetime import datetime

            # Parse ISO timestamp — handle both with and without timezone
            exp_dt = datetime.fromisoformat(token_expires_at.replace("Z", "+00:00"))
            needs_refresh = _time.time() > exp_dt.timestamp()
        except (ValueError, TypeError):
            # If we can't parse the expiry, refresh to be safe
            needs_refresh = True

    if needs_refresh:
        if not refresh_token:
            return False, "No refresh token — re-authorize this site"
        try:
            mgr = get_site_oauth_manager()
            provider = mgr.get_provider_for_plugin_type(plugin_type) or "google"
            new_tokens = await mgr.refresh_site_token(provider, refresh_token)
            access_token = new_tokens["access_token"]
            # Update the credentials dict so the caller can persist the refreshed token
            credentials["access_token"] = access_token
            credentials["token_expires_at"] = new_tokens["token_expires_at"]
        except InvalidGrantError:
            return False, "reauth_required"
        except Exception as e:
            return False, f"Token refresh failed: {type(e).__name__}: {e}"

    base_url = endpoint_info.get("base_url", "")
    check_url = base_url + endpoint_info["path"]
    method = endpoint_info.get("method", "GET")
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if method == "POST":
                resp = await client.post(check_url, headers=headers)
            else:
                resp = await client.get(check_url, headers=headers)
            status_code = resp.status_code
            resp_text = resp.text

        if status_code < 400:
            return True, "OK"
        elif status_code == 401:
            return False, "Authentication failed — access token may be invalid"
        elif status_code == 403:
            # Include Google's error body so the user can see *why* it's 403
            # (e.g. "Request had insufficient authentication scopes" vs
            # "API has not been used in project").
            return False, f"Access forbidden (HTTP 403): {resp_text[:300]}"
        else:
            return False, f"HTTP {status_code}: {resp_text[:200]}"

    except httpx.ConnectError:
        return False, "Connection failed — unable to reach Google API"
    except httpx.TimeoutException:
        return False, "Connection timed out (15s)"
    except Exception as e:
        return False, f"Connection error: {type(e).__name__}: {e}"


async def _validate_cloudflare_connection(credentials: dict[str, str]) -> tuple[bool, str]:
    """Test Cloudflare access by verifying the stored API token.

    Uses ``GET /user/tokens/verify`` — the one Cloudflare endpoint that
    works with any API token regardless of permissions. Success means the
    token is present, valid and active; the returned token id is included
    in the message so the user can confirm which token the site uses.

    Args:
        credentials: Plaintext credential dict (must contain ``api_token``).

    Returns:
        Tuple of (success, message).
    """
    api_token = credentials.get("api_token", "")
    if not api_token:
        return False, "Missing api_token"

    url = "https://api.cloudflare.com/client/v4/user/tokens/verify"
    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                status_code = resp.status
                resp_text = await resp.text()
    except aiohttp.ClientConnectorError:
        return False, "Connection failed — cannot reach api.cloudflare.com"
    except TimeoutError:
        return False, "Connection timed out (15s) — api.cloudflare.com is slow or unreachable"
    except Exception as e:  # noqa: BLE001
        return False, f"Connection error: {type(e).__name__}: {e}"

    try:
        data = json.loads(resp_text)
    except Exception:  # noqa: BLE001
        return False, f"Unexpected response (HTTP {status_code}): {resp_text[:200]}"

    if status_code == 401 or status_code == 403:
        return False, "Authentication failed — API token is invalid or was revoked"
    if status_code == 400 and not data.get("success", False):
        errors = data.get("errors", [])
        detail = "; ".join(e.get("message", str(e)) for e in errors) if errors else resp_text[:200]
        return False, f"Token verification failed: {detail}"
    if status_code >= 400:
        return False, f"Token verification HTTP {status_code}: {resp_text[:200]}"

    result = data.get("result", {})
    status = result.get("status", "unknown")
    token_id = result.get("id", "?")
    if status == "active":
        return True, f"OK — Cloudflare token active (id {token_id})"
    return False, f"Cloudflare token status is '{status}' (id {token_id})"


async def validate_site_connection(
    plugin_type: str,
    url: str,
    credentials: dict[str, str],
    *,
    allow_private: bool = False,
) -> tuple[bool, str]:
    """Test connectivity to a site using HTTP health check.

    For OAuth-based plugins (gmail, google_search_console), the health
    check uses the stored access token with Bearer auth against the
    Google API endpoint.  If the access token is expired, it is refreshed
    automatically before the check.  If the refresh fails with
    ``invalid_grant``, the caller should set the site status to
    ``reauth_required``.

    Args:
        plugin_type: Plugin type name.
        url: Site URL (not used for OAuth plugins — the API base URL is
            derived from the plugin type).
        credentials: Plaintext credential dict.
        allow_private: Permit private/internal destinations (admin-owned
            sites). Non-admin sites must resolve to public addresses, checked
            both before the request and at connect time (redirects included).

    Returns:
        Tuple of (success, message). Message is "OK" on success or
        a human-readable error description.
    """
    from core.site_oauth import OAUTH_PLUGIN_TYPES

    endpoint_info = _HEALTH_ENDPOINTS.get(plugin_type)
    if endpoint_info is None:
        return False, f"Unknown plugin type '{plugin_type}'"

    # Gmail uses manual OAuth credentials (client_id, client_secret,
    # refresh_token entered by the owner via the bootstrap script).
    # It needs a real refresh-token exchange + users.getProfile.
    if plugin_type == "gmail":
        return await _validate_gmail_connection(credentials)

    # Cloudflare uses a static API token against the fixed v4 API base —
    # the generic static path below would append the path to the site URL,
    # which is meaningless here. /user/tokens/verify needs no permission.
    if plugin_type == "cloudflare":
        return await _validate_cloudflare_connection(credentials)

    # ── OAuth-based plugins (site-connection flow) ─────────────
    # GSC and other OAuth-flow plugins use the site OAuth manager.
    if plugin_type in OAUTH_PLUGIN_TYPES or (
        endpoint_info.get("oauth") and not endpoint_info.get("manual")
    ):
        return await _validate_oauth_site_connection(plugin_type, credentials, endpoint_info)

    # ── Static-credential plugins ──────────────────────────────
    # SSRF guard: the destination host comes from the user-supplied site URL,
    # so block internal/private targets before we make the request (pre-flight,
    # off the event loop), then enforce the same policy at connect time so a
    # redirect or a DNS-rebinding answer cannot reach an internal host either.
    ssrf_ok, ssrf_reason = await asyncio.to_thread(
        guard_site_url_ssrf, url, allow_private=allow_private
    )
    if not ssrf_ok:
        return False, f"URL not allowed: {ssrf_reason}"

    check_url = url.rstrip("/") + endpoint_info["path"]
    method = endpoint_info["method"]

    # Build auth headers per plugin type
    headers: dict[str, str] = {}
    if plugin_type in ("wordpress", "wordpress_specialist"):
        import base64

        username = credentials.get("username", "")
        app_password = credentials.get("app_password", "")
        token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    elif plugin_type == "woocommerce":
        import base64

        ck = credentials.get("consumer_key", "")
        cs = credentials.get("consumer_secret", "")
        token = base64.b64encode(f"{ck}:{cs}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    elif plugin_type == "gitea":
        headers["Authorization"] = f"token {credentials.get('token', '')}"
    elif plugin_type == "n8n":
        headers["X-N8N-API-KEY"] = credentials.get("api_key", "")
    elif plugin_type == "supabase":
        headers["apikey"] = credentials.get("service_role_key", "")
        headers["Authorization"] = f"Bearer {credentials.get('service_role_key', '')}"
    elif plugin_type == "coolify":
        headers["Authorization"] = f"Bearer {credentials.get('token', '')}"
    elif plugin_type == "openpanel":
        headers["openpanel-client-id"] = credentials.get("client_id", "")
        headers["openpanel-client-secret"] = credentials.get("client_secret", "")

    from core.net_guard import SSRFBlockedError, allow_private_destinations, client_session

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        with allow_private_destinations(allow_private):
            async with client_session(timeout=timeout) as session:
                if method == "POST":
                    async with session.post(check_url, headers=headers) as resp:
                        status_code = resp.status
                        resp_text = await resp.text()
                else:
                    async with session.get(check_url, headers=headers) as resp:
                        status_code = resp.status
                        resp_text = await resp.text()

        if status_code < 400:
            return True, "OK"
        elif status_code == 401:
            return False, "Authentication failed — check credentials"
        elif status_code == 403:
            return False, "Access forbidden — check permissions or API may be disabled"
        elif status_code == 404:
            return False, f"Endpoint not found at {check_url} — check URL"
        else:
            return False, f"HTTP {status_code}: {resp_text[:200]}"

    except SSRFBlockedError as e:
        # Reached only via a redirect or a DNS answer that changed after the
        # pre-flight check — never follow it, never reflect anything from it.
        return False, f"URL not allowed: {e}"
    except aiohttp.ClientConnectorError:
        return False, "Connection failed — check URL and ensure the site is reachable"
    except TimeoutError:
        return False, "Connection timed out (15s) — site may be slow or unreachable"
    except aiohttp.InvalidURL:
        return False, "Invalid URL protocol — use https:// or http://"
    except Exception as e:
        return False, f"Connection error: {type(e).__name__}: {e}"


async def create_user_site(
    user_id: str,
    plugin_type: str,
    alias: str,
    url: str,
    credentials: dict[str, str],
    skip_validation: bool = False,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Create a new site for a user.

    Validates credentials, tests the connection, encrypts credentials,
    and stores in the database.

    Args:
        user_id: Owner's UUID.
        plugin_type: Plugin type name.
        alias: User-chosen friendly name.
        url: Site URL.
        credentials: Plaintext credential dict.
        skip_validation: If True, skip connection test (for testing).
        is_admin: If True, bypass the MAX_SITES_PER_USER limit and allow the
            site to target private/internal addresses.

    Returns:
        The created site dict (without decrypted credentials).

    Raises:
        ValueError: On validation errors (bad plugin type, missing fields,
            alias taken, site limit reached, connection failed).
    """
    from core.database import get_database
    from core.encryption import get_credential_encryption

    # Validate plugin type
    if plugin_type not in PLUGIN_CREDENTIAL_FIELDS:
        raise ValueError(
            f"Unknown plugin type '{plugin_type}'. "
            f"Valid: {list(PLUGIN_CREDENTIAL_FIELDS.keys())}"
        )

    # Validate alias format
    alias = alias.strip().lower()
    if not alias or len(alias) < 2 or len(alias) > 50:
        raise ValueError("Alias must be 2-50 characters")
    if not alias.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Alias may only contain letters, numbers, hyphens, and underscores")

    credentials = _clean_credentials(plugin_type, credentials)

    from core.site_oauth import OAUTH_PLUGIN_TYPES

    # OAuth plugins: skip static credential validation and connection test —
    # credentials are populated by the OAuth flow after site creation.
    is_oauth = plugin_type in OAUTH_PLUGIN_TYPES

    # Validate required credential fields (skipped for OAuth plugins)
    if not is_oauth:
        valid, errors = validate_credentials(plugin_type, credentials)
        if not valid:
            raise ValueError(f"Missing credentials: {', '.join(errors)}")

    db = get_database()

    # Check site limit (reads DB > ENV > default so dashboard/settings changes take effect)
    # Admin users (via ADMIN_EMAILS or role=admin) are exempt from the limit.
    if not is_admin:
        from core.settings import get_cached_max_sites

        max_sites = get_cached_max_sites()
        count = await db.count_sites_by_user(user_id)
        if count >= max_sites:
            raise ValueError(f"Site limit reached ({max_sites} sites per user)")

    # Check alias uniqueness (DB constraint will also catch this)
    existing = await db.get_site_by_alias(user_id, alias)
    if existing is not None:
        raise ValueError(f"Alias '{alias}' is already in use")

    # Test connection (skipped for OAuth plugins — no credentials yet)
    status = "active"
    status_msg = "Connection verified"
    if not skip_validation and not is_oauth:
        ok, msg = await validate_site_connection(
            plugin_type, url, credentials, allow_private=is_admin
        )
        if not ok:
            raise ValueError(f"Connection test failed: {msg}")
    elif is_oauth:
        status = "pending"
        status_msg = "Awaiting OAuth authorization"

    # Encrypt credentials
    encryptor = get_credential_encryption()
    # We need the site_id for encryption, but we don't have it yet.
    # Use a pre-generated UUID as the site_id.
    import uuid

    site_id = str(uuid.uuid4())
    encrypted = encryptor.encrypt_credentials(credentials, site_id)

    # Store in database — we bypass db.create_site() to use our pre-generated ID
    from core.database import _utc_now

    now = _utc_now()
    await db.execute(
        "INSERT INTO sites (id, user_id, plugin_type, alias, url, credentials, "
        "status, status_msg, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (site_id, user_id, plugin_type, alias, url, encrypted, status, status_msg, now),
    )

    # Return the created site (without credentials blob)
    site = await db.get_site(site_id, user_id)
    if site is None:
        raise RuntimeError(f"Failed to read back created site {site_id}")

    result = dict(site)
    result.pop("credentials", None)
    logger.info("Created site %s (%s) for user %s", alias, plugin_type, user_id)
    return result


async def get_user_sites(user_id: str) -> list[dict[str, Any]]:
    """Get all sites for a user (without credentials).

    Args:
        user_id: Owner's UUID.

    Returns:
        List of site dicts.
    """
    from core.database import get_database

    db = get_database()
    sites = await db.get_sites_by_user(user_id)
    # Strip credentials blob from response
    return [{k: v for k, v in site.items() if k != "credentials"} for site in sites]


async def get_user_site(site_id: str, user_id: str) -> dict[str, Any] | None:
    """Get a single site (without credentials).

    Args:
        site_id: Site UUID.
        user_id: Owner's UUID.

    Returns:
        Site dict or None.
    """
    from core.database import get_database

    db = get_database()
    site = await db.get_site(site_id, user_id)
    if site is None:
        return None
    result = dict(site)
    result.pop("credentials", None)
    return result


async def delete_user_site(site_id: str, user_id: str) -> bool:
    """Delete a user's site.

    Args:
        site_id: Site UUID.
        user_id: Owner's UUID.

    Returns:
        True if deleted, False if not found.
    """
    from core.database import get_database

    db = get_database()
    deleted = await db.delete_site(site_id, user_id)
    if deleted:
        logger.info("Deleted site %s for user %s", site_id, user_id)
    return deleted


async def update_user_site(
    site_id: str,
    user_id: str,
    url: str,
    credentials: dict[str, str],
    skip_validation: bool = False,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Update URL and credentials for an existing site.

    Password fields left blank are preserved from the existing encrypted credentials.
    Re-validates the connection after update.

    Args:
        site_id: Site UUID.
        user_id: Owner's UUID.
        url: New base URL (required).
        credentials: Credential dict — blank password fields keep their current value.
        skip_validation: If True, skip connection test (for testing).
        is_admin: If True, the site may target private/internal addresses.

    Returns:
        The updated site dict (without decrypted credentials).

    Raises:
        ValueError: If site not found, validation fails, or connection test fails.
    """
    from core.database import get_database
    from core.encryption import get_credential_encryption

    db = get_database()

    # Verify site ownership
    existing_site = await db.get_site(site_id, user_id)
    if existing_site is None:
        raise ValueError("Site not found")

    plugin_type = existing_site["plugin_type"]

    # Validate URL
    url = url.strip().rstrip("/")
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")

    # Merge new credentials with existing ones — blank fields keep existing values
    encryptor = get_credential_encryption()
    existing_credentials = encryptor.decrypt_credentials(existing_site["credentials"], site_id)

    merged: dict[str, str] = dict(existing_credentials)
    field_defs = {f["name"]: f for f in PLUGIN_CREDENTIAL_FIELDS.get(plugin_type, [])}
    for key, value in credentials.items():
        normalized = _credential_value_to_string(value).strip()
        # Only override if the new value is non-empty
        if normalized:
            merged[key] = normalized
        # Blank value for a non-required field (e.g. meta_url) → explicitly clear it
        elif key in field_defs and not field_defs[key].get("required", True):
            merged[key] = ""

    # Strip empty optional values before storing (keep storage clean)
    merged = _clean_credentials(plugin_type, merged)

    # Validate required fields are still present
    valid, errors = validate_credentials(plugin_type, merged)
    if not valid:
        raise ValueError(f"Missing required credentials: {', '.join(errors)}")

    # Test connection
    if not skip_validation:
        ok, msg = await validate_site_connection(plugin_type, url, merged, allow_private=is_admin)
        if not ok:
            raise ValueError(f"Connection test failed: {msg}")

    # Encrypt merged credentials
    encrypted = encryptor.encrypt_credentials(merged, site_id)

    # Persist
    updated = await db.update_site_credentials(site_id, user_id, url, encrypted)
    if not updated:
        raise RuntimeError(f"Failed to update site {site_id}")

    # Mark active after successful connection test
    status_msg = "Connection verified" if not skip_validation else "Updated (not tested)"
    await db.update_site_status(site_id, "active", status_msg, user_id=user_id)

    result = await db.get_site(site_id, user_id)
    if result is None:
        raise RuntimeError(f"Failed to read back updated site {site_id}")

    site_dict = dict(result)
    site_dict.pop("credentials", None)
    logger.info("Updated site %s (%s) for user %s", site_id, plugin_type, user_id)
    return site_dict


# ---------------------------------------------------------------------------
# F.5a.9.x: per-site AI provider keys (OpenAI / Stability / Replicate)
# ---------------------------------------------------------------------------

# Only WordPress / WooCommerce sites can host AI image provider keys — the
# only consumer is ``wordpress_generate_and_upload_image``, which uploads into
# a WordPress media library. Other plugin types never surface the section.
PROVIDER_KEYS_ALLOWED_PLUGIN_TYPES: frozenset[str] = frozenset({"wordpress", "woocommerce"})

# Providers supported for per-site keys. Must stay in sync with
# plugins/ai_image/registry.py ``_PROVIDERS`` (order is preserved to
# drive the UI).
SITE_PROVIDERS: tuple[str, ...] = ("openai", "stability", "replicate", "openrouter")

OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"
OPENAI_COMPATIBLE_API_TYPES = frozenset({"openai_compatible", "openai_images", "openai_responses"})


def site_ai_provider_scope(site_id: str, config_id: str) -> str:
    return f"site_ai_provider:{site_id}:{config_id}"


def normalise_openai_compatible_config(
    name: Any, api_type: Any, base_url: Any, model_id: Any = None
) -> dict[str, Any]:
    from urllib.parse import urlparse

    from plugins.wordpress.handlers._media_security import ssrf_check

    clean_name = str(name or "").strip()
    clean_type = str(api_type or OPENAI_COMPATIBLE_PROVIDER).strip().lower().replace("-", "_")
    aliases = {
        "openai compatible": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "chat": "openai_compatible",
        "chat_completions": "openai_compatible",
        "openai images": "openai_images",
        "openai_images": "openai_images",
        "images": "openai_images",
        "image": "openai_images",
        "responses": "openai_responses",
        "response api": "openai_responses",
        "response_api": "openai_responses",
        "openai_responses": "openai_responses",
    }
    clean_type = aliases.get(clean_type, clean_type)
    clean_url = str(base_url or "").strip().rstrip("/")
    parsed = urlparse(clean_url)
    if not clean_name or len(clean_name) > 80:
        raise ValueError("name must be 1-80 characters")
    if clean_type not in OPENAI_COMPATIBLE_API_TYPES:
        raise ValueError("api_type must be OpenAI Compatible, OpenAI Images, or OpenAI Responses")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    ssrf = ssrf_check(
        clean_url, allow_http=os.getenv("ALLOW_HTTP_PROVIDER_URLS", "false").lower() == "true"
    )
    if not ssrf.allowed:
        raise ValueError(
            f"base_url rejected by SSRF guard: {ssrf.reason or 'disallowed destination'}"
        )
    return {
        "name": clean_name,
        "api_type": clean_type,
        "base_url": clean_url,
        "model_id": str(model_id).strip() if model_id and str(model_id).strip() else None,
    }


def site_provider_scope(site_id: str, provider: str) -> str:
    """Return the HKDF scope used for per-site provider-key encryption.

    Format: ``site_provider:{site_id}:{provider}`` — distinct from the
    per-site credentials scope (bare ``site_id``) so the same master key
    never produces the same derived key for both credential types.
    """
    return f"site_provider:{site_id}:{provider}"


def site_supports_provider_keys(plugin_type: str) -> bool:
    """Return True if the plugin type can hold AI provider keys."""
    return plugin_type in PROVIDER_KEYS_ALLOWED_PLUGIN_TYPES


async def set_site_provider_key(
    site_id: str,
    user_id: str,
    provider: str,
    api_key: str,
) -> dict[str, Any]:
    """Encrypt and store an AI provider API key for a user-owned site.

    Args:
        site_id: Site UUID.
        user_id: Owner's UUID (enforces tenant isolation).
        provider: One of :data:`SITE_PROVIDERS`.
        api_key: The plaintext API key to store.

    Returns:
        The stored row (without plaintext).

    Raises:
        ValueError: If the site is not found, the plugin type does not
            support provider keys, the provider is unknown, or the key
            is empty.
    """
    from core.database import get_database
    from core.encryption import get_credential_encryption

    if provider not in SITE_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. " f"Supported: {', '.join(SITE_PROVIDERS)}"
        )
    if not api_key or not api_key.strip():
        raise ValueError("API key must not be empty")

    db = get_database()
    site = await db.get_site(site_id, user_id)
    if site is None:
        raise ValueError("Site not found")

    if not site_supports_provider_keys(site["plugin_type"]):
        raise ValueError(
            f"Plugin type '{site['plugin_type']}' does not support AI "
            f"provider keys (only WordPress/WooCommerce)."
        )

    encryptor = get_credential_encryption()
    ciphertext = encryptor.encrypt_for_scope(
        api_key.strip(), site_provider_scope(site_id, provider)
    )

    row = await db.upsert_site_provider_key(site_id, provider, ciphertext)
    logger.info("Stored %s provider key for site %s (user %s)", provider, site_id, user_id)
    return row


async def get_site_provider_key(
    site_id: str,
    provider: str,
) -> str | None:
    """Return the decrypted AI provider key for a site, or None.

    Caller is responsible for verifying site ownership — this helper is
    also called from the AI tool handler which already trusts the
    resolved site_id.

    Args:
        site_id: Site UUID.
        provider: Provider identifier.

    Returns:
        Decrypted API key string, or None if no key is stored.
    """
    from core.database import get_database
    from core.encryption import get_credential_encryption

    if provider not in SITE_PROVIDERS:
        return None

    db = get_database()
    row = await db.get_site_provider_key(site_id, provider)
    if row is None:
        return None

    encryptor = get_credential_encryption()
    try:
        return encryptor.decrypt_for_scope(
            row["key_ciphertext"], site_provider_scope(site_id, provider)
        )
    except Exception:
        logger.exception(
            "Failed to decrypt site provider key (site=%s provider=%s)",
            site_id,
            provider,
        )
        return None


async def list_site_providers_set(site_id: str) -> set[str]:
    """Return legacy providers plus the public compatible-provider marker."""
    from core.database import get_database

    db = get_database()
    rows = await db.list_site_provider_keys(site_id)
    providers = {row["provider"] for row in rows}
    if await db.list_site_ai_provider_configs(site_id):
        providers.add(OPENAI_COMPATIBLE_PROVIDER)
    return providers


async def delete_site_provider_key(
    site_id: str,
    user_id: str,
    provider: str,
) -> bool:
    """Remove an AI provider key for a site. Returns True if a row was deleted.

    Args:
        site_id: Site UUID.
        user_id: Owner's UUID — enforces tenant isolation before deletion.
        provider: Provider identifier.
    """
    from core.database import get_database

    db = get_database()
    site = await db.get_site(site_id, user_id)
    if site is None:
        return False

    deleted = await db.delete_site_provider_key(site_id, provider)
    if deleted:
        logger.info(
            "Deleted %s provider key for site %s (user %s)",
            provider,
            site_id,
            user_id,
        )
    return deleted


async def create_site_ai_provider_config(
    site_id: str,
    user_id: str,
    name: Any,
    api_type: Any,
    base_url: Any,
    api_key: str,
    model_id: Any = None,
) -> dict[str, Any]:
    import uuid

    from core.database import get_database
    from core.encryption import get_credential_encryption

    if not api_key or not api_key.strip():
        raise ValueError("API key must not be empty")
    config = normalise_openai_compatible_config(name, api_type, base_url, model_id)
    site = await get_database().get_site(site_id, user_id)
    if site is None:
        raise ValueError("Site not found")
    if not site_supports_provider_keys(site["plugin_type"]):
        raise ValueError("Only WordPress and WooCommerce sites support AI providers")
    existing = await get_database().fetchone(
        "SELECT id FROM site_ai_provider_configs WHERE site_id = ? AND name = ?",
        (site_id, config["name"]),
    )
    config_id = str(existing["id"]) if existing else str(uuid.uuid4())
    ciphertext = get_credential_encryption().encrypt_for_scope(
        api_key.strip(), site_ai_provider_scope(site_id, config_id)
    )
    return await get_database().create_site_ai_provider_config(
        config_id=config_id,
        site_id=site_id,
        api_key_ciphertext=ciphertext,
        **config,
    )


async def get_site_ai_provider_secret(
    site_id: str, config_id: str
) -> tuple[dict[str, Any], str] | None:
    from core.database import get_database
    from core.encryption import get_credential_encryption

    row = await get_database().get_site_ai_provider_config(site_id, config_id)
    if row is None:
        return None
    try:
        key = get_credential_encryption().decrypt_for_scope(
            row["api_key_ciphertext"], site_ai_provider_scope(site_id, config_id)
        )
    except Exception:
        logger.exception("Failed to decrypt compatible provider config %s/%s", site_id, config_id)
        return None
    return row, key


async def list_site_ai_provider_configs(site_id: str, user_id: str) -> list[dict[str, Any]]:
    from core.database import get_database

    if await get_database().get_site(site_id, user_id) is None:
        raise ValueError("Site not found")
    return await get_database().list_site_ai_provider_configs(site_id)


async def delete_site_ai_provider_config(site_id: str, user_id: str, config_id: str) -> bool:
    from core.database import get_database

    if await get_database().get_site(site_id, user_id) is None:
        raise ValueError("Site not found")
    return await get_database().delete_site_ai_provider_config(site_id, config_id)


async def test_site_connection(
    site_id: str, user_id: str, *, is_admin: bool = False
) -> tuple[bool, str]:
    """Test connectivity to an existing site.

    Decrypts credentials from the database, runs the health check,
    and updates the site status.

    Args:
        site_id: Site UUID.
        user_id: Owner's UUID.
        is_admin: If True, the site may target private/internal addresses.

    Returns:
        Tuple of (success, message).

    Raises:
        ValueError: If site not found.
    """
    from core.database import get_database
    from core.encryption import get_credential_encryption

    db = get_database()
    site = await db.get_site(site_id, user_id)
    if site is None:
        raise ValueError("Site not found")

    encryptor = get_credential_encryption()
    credentials = encryptor.decrypt_credentials(site["credentials"], site_id)

    ok, msg = await validate_site_connection(
        site["plugin_type"], site["url"], credentials, allow_private=is_admin
    )

    # Update status — handle reauth_required for expired OAuth tokens
    if msg == "reauth_required":
        await db.update_site_status(
            site_id, "reauth_required", "Re-authorization required", user_id=user_id
        )
        return ok, msg

    new_status = "active" if ok else "error"
    await db.update_site_status(site_id, new_status, msg, user_id=user_id)

    # If the OAuth connection was refreshed during validation, persist the new tokens
    from core.site_oauth import OAUTH_PLUGIN_TYPES

    if ok and site["plugin_type"] in OAUTH_PLUGIN_TYPES:
        # Check if credentials were modified (access_token refreshed)
        if credentials.get("access_token") and credentials.get(
            "access_token"
        ) != encryptor.decrypt_credentials(site["credentials"], site_id).get("access_token"):
            encrypted = encryptor.encrypt_credentials(credentials, site_id)
            await db.update_site_credentials(site_id, user_id, site["url"], encrypted)

    return ok, msg
