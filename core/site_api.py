"""Site management logic for the Live Platform (Track E.3).

Provides site CRUD operations, connection validation, and credential
field definitions for all 9 plugin types. Coordinates between the
database, encryption, and plugin health check layers.

Usage:
    from core.site_api import create_user_site, get_user_sites, validate_site_connection

    ok, msg = await validate_site_connection("wordpress", "https://example.com", creds)
    site = await create_user_site(user_id, "wordpress", "myblog", url, creds)
"""

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# Maximum sites per user (configurable via env var)
MAX_SITES_PER_USER = int(os.getenv("MAX_SITES_PER_USER", "10"))

# Plugin credential field definitions — drives the dynamic "Add Site" form
# and server-side validation. Each field has:
#   name:     form input name (matches credential JSON key)
#   label:    display label
# type: "text" or "password"
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
    "wordpress_advanced": [
        {
            "name": "username",
            "label": "Username",
            "type": "text",
            "required": True,
            "hint": "Your WordPress admin username (HTTP Basic username for every API call).",
        },
        {
            "name": "app_password",
            "label": "Application Password",
            "type": "password",
            "required": True,
            "hint": (
                "WordPress Admin → Users → Profile → Application Passwords. "
                "IS the API credential — no separate API key needed."
            ),
        },
        {
            "name": "container",
            "label": "Docker Container Name",
            "type": "text",
            "required": False,
            "hint": "Docker container running WordPress (for WP-CLI access). Leave empty if unused.",
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
    "appwrite": [
        {
            "name": "project_id",
            "label": "Project ID",
            "type": "text",
            "required": True,
            "hint": "Appwrite Console → Project Settings → Project ID",
        },
        {
            "name": "api_key",
            "label": "API Key",
            "type": "password",
            "required": True,
            "hint": "Appwrite Console → Project Settings → API Keys → Create",
        },
    ],
    "directus": [
        {
            "name": "token",
            "label": "Static Token",
            "type": "password",
            "required": True,
            "hint": "Directus → Settings → User → Static Token",
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
    ],
}

# Plugin display names for UI
PLUGIN_DISPLAY_NAMES: dict[str, str] = {
    "wordpress": "WordPress",
    "woocommerce": "WooCommerce",
    "wordpress_advanced": "WordPress Advanced",
    "gitea": "Gitea",
    "n8n": "n8n",
    "supabase": "Supabase",
    "openpanel": "OpenPanel",
    "appwrite": "Appwrite",
    "directus": "Directus",
    "coolify": "Coolify",
}

# Health check endpoints per plugin type
_HEALTH_ENDPOINTS: dict[str, dict[str, Any]] = {
    "wordpress": {"path": "/wp-json/wp/v2/users/me", "method": "GET"},
    "woocommerce": {"path": "/wp-json/wc/v3/system_status", "method": "GET"},
    "wordpress_advanced": {"path": "/wp-json/wp/v2/users/me", "method": "GET"},
    "gitea": {"path": "/api/v1/user", "method": "GET"},
    "n8n": {"path": "/healthz", "method": "GET"},
    "supabase": {"path": "/rest/v1/", "method": "GET"},
    "openpanel": {"path": "/healthcheck", "method": "GET"},
    "appwrite": {"path": "/v1/health", "method": "GET"},
    "directus": {"path": "/server/health", "method": "GET"},
    "coolify": {"path": "/api/v1/version", "method": "GET"},
}


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


def get_user_credential_fields() -> dict[str, list[dict[str, Any]]]:
    """Get credential fields for public (non-admin) users.

    Only includes plugins enabled via ENABLED_PLUGINS env var.

    Returns:
        Filtered dict of plugin_type -> field definitions.
    """
    from core.plugin_visibility import get_public_plugin_types

    public = get_public_plugin_types()
    return {k: v for k, v in PLUGIN_CREDENTIAL_FIELDS.items() if k in public}


def get_user_plugin_names() -> dict[str, str]:
    """Get plugin display names for public (non-admin) users.

    Only includes plugins enabled via ENABLED_PLUGINS env var.

    Returns:
        Filtered dict of plugin_type -> display name.
    """
    from core.plugin_visibility import get_public_plugin_types

    public = get_public_plugin_types()
    return {k: v for k, v in PLUGIN_DISPLAY_NAMES.items() if k in public}


def validate_credentials(plugin_type: str, credentials: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate that all required credential fields are present and non-empty.

    Args:
        plugin_type: Plugin type name.
        credentials: Dict of credential key→value.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    fields = get_credential_fields(plugin_type)
    errors: list[str] = []

    for field in fields:
        if field["required"]:
            value = credentials.get(field["name"], "").strip()
            if not value:
                errors.append(f"'{field['label']}' is required")

    return (len(errors) == 0, errors)


async def validate_site_connection(
    plugin_type: str, url: str, credentials: dict[str, str]
) -> tuple[bool, str]:
    """Test connectivity to a site using HTTP health check.

    Args:
        plugin_type: Plugin type name.
        url: Site URL.
        credentials: Plaintext credential dict.

    Returns:
        Tuple of (success, message). Message is "OK" on success or
        a human-readable error description.
    """
    endpoint_info = _HEALTH_ENDPOINTS.get(plugin_type)
    if endpoint_info is None:
        return False, f"Unknown plugin type '{plugin_type}'"

    check_url = url.rstrip("/") + endpoint_info["path"]
    method = endpoint_info["method"]

    # Build auth headers per plugin type
    headers: dict[str, str] = {}
    if plugin_type in ("wordpress", "wordpress_advanced"):
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
    elif plugin_type == "appwrite":
        headers["X-Appwrite-Project"] = credentials.get("project_id", "")
        headers["X-Appwrite-Key"] = credentials.get("api_key", "")
    elif plugin_type in ("directus", "coolify"):
        headers["Authorization"] = f"Bearer {credentials.get('token', '')}"
    elif plugin_type == "openpanel":
        headers["openpanel-client-id"] = credentials.get("client_id", "")
        headers["openpanel-client-secret"] = credentials.get("client_secret", "")

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
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

    # Validate required credential fields
    valid, errors = validate_credentials(plugin_type, credentials)
    if not valid:
        raise ValueError(f"Missing credentials: {', '.join(errors)}")

    db = get_database()

    # Check site limit
    count = await db.count_sites_by_user(user_id)
    if count >= MAX_SITES_PER_USER:
        raise ValueError(f"Site limit reached ({MAX_SITES_PER_USER} sites per user)")

    # Check alias uniqueness (DB constraint will also catch this)
    existing = await db.get_site_by_alias(user_id, alias)
    if existing is not None:
        raise ValueError(f"Alias '{alias}' is already in use")

    # Test connection
    status = "active"
    status_msg = "Connection verified"
    if not skip_validation:
        ok, msg = await validate_site_connection(plugin_type, url, credentials)
        if not ok:
            raise ValueError(f"Connection test failed: {msg}")

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
    for key, value in credentials.items():
        # Only override if the new value is non-empty
        if value and value.strip():
            merged[key] = value.strip()
        # Blank value for a non-required field (e.g. meta_url) → explicitly clear it
        else:
            field_defs = {f["name"]: f for f in PLUGIN_CREDENTIAL_FIELDS.get(plugin_type, [])}
            if key in field_defs and not field_defs[key].get("required", True):
                merged[key] = ""

    # Strip empty optional values before storing (keep storage clean)
    merged = {k: v for k, v in merged.items() if v}

    # Validate required fields are still present
    valid, errors = validate_credentials(plugin_type, merged)
    if not valid:
        raise ValueError(f"Missing required credentials: {', '.join(errors)}")

    # Test connection
    if not skip_validation:
        ok, msg = await validate_site_connection(plugin_type, url, merged)
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
    """Return the set of providers that have a key stored for the site."""
    from core.database import get_database

    db = get_database()
    rows = await db.list_site_provider_keys(site_id)
    return {row["provider"] for row in rows}


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


async def test_site_connection(site_id: str, user_id: str) -> tuple[bool, str]:
    """Test connectivity to an existing site.

    Decrypts credentials from the database, runs the health check,
    and updates the site status.

    Args:
        site_id: Site UUID.
        user_id: Owner's UUID.

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

    ok, msg = await validate_site_connection(site["plugin_type"], site["url"], credentials)

    # Update status
    new_status = "active" if ok else "error"
    await db.update_site_status(site_id, new_status, msg, user_id=user_id)

    return ok, msg
