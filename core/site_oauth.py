"""OAuth site-connection flow for the Live Platform.

Manages the OAuth 2.0 authorization-code flow that lets a user connect
external services (Gmail, Google Search Console, etc.) to their MCP Hub
account.  This flow is **separate** from the dashboard login OAuth flow in
``core/user_auth.py`` — it uses ``access_type=offline`` + ``prompt=consent``
to obtain a *refresh token* that is stored encrypted in the site's
credentials blob, and it uses a dedicated callback URL
(``/oauth/site/callback``) distinct from the login callback.

The module is self-contained: it does not modify ``user_auth.py`` and
does not depend on any singleton from it.  The Google client credentials
(``GOOGLE_CLIENT_ID`` / ``GOOGLE_CLIENT_SECRET``) are read from the same
environment variables as the login flow, but are used with different
scopes and ``access_type=offline``.

Usage::

    mgr = get_site_oauth_manager()
    url, state = mgr.get_site_authorization_url("google", "gmail.readonly", site_id, user_id)
    # ... user redirected to Google, callback received ...
    tokens = await mgr.exchange_site_code("google", code, state)
    await mgr.store_site_oauth_credentials(site_id, user_id, tokens)

    # Later — refresh an expired access token:
    new_tokens = await mgr.refresh_site_token("google", refresh_token)

Design notes:
- Pending OAuth states are kept in-memory (``_pending_states``) keyed by
  the random ``state`` token.  Each entry stores ``(site_id, user_id,
  provider, scope, timestamp)``.  States expire after 10 minutes.
- The module is designed to be extensible to other OAuth providers
  (Microsoft, etc.) via the ``OAUTH_PROVIDERS`` config dict.
"""

import logging
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# ── OAuth provider endpoints ──────────────────────────────────

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# State expiry: 10 minutes (same as user_auth.py)
_STATE_EXPIRY_SECONDS = 600

# ── Provider configuration ─────────────────────────────────────

# Each provider entry describes how to build auth URLs and exchange codes.
# ``auth_url`` / ``token_url`` are the provider endpoints.
# ``scopes`` maps a *plugin type* to the OAuth scope(s) that plugin needs.
# ``api_base`` is the base URL for health-check / API calls.
OAUTH_PROVIDERS: dict[str, dict[str, Any]] = {
    "google": {
        "auth_url": _GOOGLE_AUTH_URL,
        "token_url": _GOOGLE_TOKEN_URL,
        # plugin_type -> scope(s)
        "scopes": {
            "gmail": "https://www.googleapis.com/auth/gmail.modify",
            "google_search_console": "https://www.googleapis.com/auth/webmasters.readonly",
        },
        # API base URLs for health checks (mapped per plugin_type in site_api.py)
        "api_base": {
            "google_search_console": "https://www.googleapis.com",
        },
    },
}

# Plugin types that use the OAuth credential model (no static credential
# form).  Used by site_api.py to skip static validation and by the frontend
# to render the "Connect with Google" button instead of credential fields.
# Note: gmail uses manual credentials (bootstrap script), not the OAuth flow.
OAUTH_PLUGIN_TYPES: frozenset[str] = frozenset({"google_search_console"})

# Which OAuth provider a given plugin_type maps to.
PLUGIN_TYPE_TO_PROVIDER: dict[str, str] = {
    "google_search_console": "google",
}


class SiteOAuthManager:
    """OAuth 2.0 site-connection flow manager.

    Manages authorization URL generation, code-for-token exchange, token
    refresh, and encrypted credential storage for sites that use OAuth
    instead of static credentials (e.g. Gmail, Google Search Console).
    """

    def __init__(
        self,
        google_client_id: str | None = None,
        google_client_secret: str | None = None,
        public_url: str | None = None,
    ) -> None:
        """Initialize the site OAuth manager.

        Args:
            google_client_id: Google OAuth client ID.  Falls back to the
                ``GOOGLE_CLIENT_ID`` environment variable.
            google_client_secret: Google OAuth client secret.  Falls back
                to the ``GOOGLE_CLIENT_SECRET`` environment variable.
            public_url: Public-facing URL of the server (for callbacks).
                Falls back to the ``PUBLIC_URL`` environment variable.
        """
        self._google_client_id = google_client_id or os.getenv("GOOGLE_CLIENT_ID")
        self._google_client_secret = google_client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
        self._public_url = (public_url or os.getenv("PUBLIC_URL", "")).rstrip("/")

        # Pending OAuth states: state -> {site_id, user_id, provider, scope, ts}
        self._pending_states: dict[str, dict[str, Any]] = {}

        if self._google_client_id and not self._public_url:
            logger.warning(
                "SiteOAuthManager: GOOGLE_CLIENT_ID is set but PUBLIC_URL is missing. "
                "Site OAuth flows will fail until PUBLIC_URL is configured."
            )

        logger.info(
            "SiteOAuthManager initialized: google=%s, public_url=%s",
            bool(self._google_client_id),
            bool(self._public_url),
        )

    # ── Provider availability ─────────────────────────────────

    def is_configured(self, provider: str) -> bool:
        """Return True if the given provider has client credentials configured.

        Args:
            provider: Provider name (e.g. ``"google"``).

        Returns:
            True if credentials are available, False otherwise.
        """
        if provider == "google":
            return bool(self._google_client_id and self._google_client_secret)
        return False

    def available_providers(self) -> list[str]:
        """Return list of configured OAuth providers.

        Returns:
            List of provider name strings.
        """
        providers: list[str] = []
        if self.is_configured("google"):
            providers.append("google")
        return providers

    # ── Authorization URL generation ────────────────────────────

    def get_site_authorization_url(
        self,
        provider: str,
        scope: str,
        site_id: str,
        user_id: str,
    ) -> tuple[str, str]:
        """Generate an OAuth authorization URL for a site connection.

        Builds the URL with ``access_type=offline`` and ``prompt=consent``
        so Google returns a *refresh token* on the first authorization.
        Stores the pending state so the callback can be matched back to
        the originating site + user.

        Args:
            provider: OAuth provider name (e.g. ``"google"``).
            scope: OAuth scope string for the requested API access.
            site_id: UUID of the site being authorized.
            user_id: UUID of the user who owns the site.

        Returns:
            Tuple of ``(authorization_url, state_token)``.

        Raises:
            ValueError: If the provider is unsupported or not configured,
                or if ``PUBLIC_URL`` is missing.
        """
        if not self._public_url:
            raise ValueError(
                "PUBLIC_URL environment variable must be set for site OAuth to work. "
                "Example: PUBLIC_URL=https://mcp.example.com"
            )

        provider_config = OAUTH_PROVIDERS.get(provider)
        if provider_config is None:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        if not self.is_configured(provider):
            raise ValueError(
                f"OAuth provider '{provider}' is not configured. "
                f"Set the corresponding client ID and secret environment variables."
            )

        state = secrets.token_hex(32)
        self._pending_states[state] = {
            "site_id": site_id,
            "user_id": user_id,
            "provider": provider,
            "scope": scope,
            "ts": time.time(),
        }
        self._cleanup_expired_states()

        callback_url = self._site_callback_url()

        if provider == "google":
            params = {
                "client_id": self._google_client_id,
                "redirect_uri": callback_url,
                "scope": scope,
                "response_type": "code",
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
            }
            auth_url = provider_config["auth_url"]
            return f"{auth_url}?{urlencode(params)}", state

        raise ValueError(f"Unsupported OAuth provider: {provider}")

    # ── State validation ───────────────────────────────────────

    def validate_and_consume_state(self, state: str) -> dict[str, Any] | None:
        """Validate a state token, consume it (one-time use), and return metadata.

        Args:
            state: The state parameter from the OAuth callback.

        Returns:
            Dict with ``site_id``, ``user_id``, ``provider``, ``scope`` if
            valid and not expired, or ``None`` if the state is unknown or
            expired.
        """
        entry = self._pending_states.pop(state, None)
        if entry is None:
            return None
        if time.time() - entry["ts"] > _STATE_EXPIRY_SECONDS:
            return None
        return {
            "site_id": entry["site_id"],
            "user_id": entry["user_id"],
            "provider": entry["provider"],
            "scope": entry["scope"],
        }

    def _cleanup_expired_states(self) -> None:
        """Remove expired state tokens from the pending store."""
        now = time.time()
        expired = [
            s for s, e in self._pending_states.items() if now - e["ts"] > _STATE_EXPIRY_SECONDS
        ]
        for s in expired:
            del self._pending_states[s]

    # ── Token exchange ─────────────────────────────────────────

    async def exchange_site_code(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        """Exchange an authorization code for OAuth tokens.

        Exchanges the code for an access token + refresh token using the
        provider's token endpoint.  The state is validated and consumed
        before the exchange so the callback cannot be replayed.

        Args:
            provider: OAuth provider name (e.g. ``"google"``).
            code: Authorization code from the callback.
            state: State token from the callback (validated and consumed).

        Returns:
            Dict with keys: ``access_token``, ``refresh_token``,
            ``expires_in``, ``token_expires_at`` (ISO timestamp),
            ``scope``, ``provider``.  Also includes ``site_id`` and
            ``user_id`` from the stored state.

        Raises:
            ValueError: If the state is invalid/expired or the token
                exchange fails.
        """
        state_info = self.validate_and_consume_state(state)
        if state_info is None:
            raise ValueError("Invalid or expired OAuth state")

        provider_config = OAUTH_PROVIDERS.get(provider)
        if provider_config is None:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        callback_url = self._site_callback_url()

        if provider == "google":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    provider_config["token_url"],
                    data={
                        "client_id": self._google_client_id,
                        "client_secret": self._google_client_secret,
                        "code": code,
                        "redirect_uri": callback_url,
                        "grant_type": "authorization_code",
                    },
                )
                if resp.status_code != 200:
                    raise ValueError(f"Failed to exchange Google code: {resp.text}")

                token_data = resp.json()

        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"Token exchange returned no access_token: {token_data}")

        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            raise ValueError(
                "Token exchange did not return a refresh_token. "
                "Ensure access_type=offline and prompt=consent are used."
            )

        expires_in = token_data.get("expires_in", 3600)
        token_expires_at = time.time() + expires_in

        from datetime import UTC, datetime

        result = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "token_expires_at": datetime.fromtimestamp(token_expires_at, tz=UTC).isoformat(),
            "scope": token_data.get("scope", state_info["scope"]),
            "provider": provider,
            "site_id": state_info["site_id"],
            "user_id": state_info["user_id"],
        }
        logger.info(
            "Site OAuth: exchanged code for tokens (site=%s user=%s provider=%s)",
            state_info["site_id"],
            state_info["user_id"],
            provider,
        )
        return result

    # ── Token refresh ──────────────────────────────────────────

    async def refresh_site_token(
        self,
        provider: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Refresh an expired access token using a stored refresh token.

        Args:
            provider: OAuth provider name (e.g. ``"google"``).
            refresh_token: The stored refresh token.

        Returns:
            Dict with keys: ``access_token``, ``expires_in``,
            ``token_expires_at`` (ISO timestamp), ``refresh_token`` (the
            same refresh token, or a new one if the provider rotates).

        Raises:
            ValueError: If the refresh fails with ``invalid_grant`` (the
                refresh token has been revoked or expired) or any other
                error.
        """
        provider_config = OAUTH_PROVIDERS.get(provider)
        if provider_config is None:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        if provider == "google":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    provider_config["token_url"],
                    data={
                        "client_id": self._google_client_id,
                        "client_secret": self._google_client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                if resp.status_code != 200:
                    body = (
                        resp.json()
                        if resp.headers.get("content-type", "").startswith("application/json")
                        else {}
                    )
                    error_code = body.get("error", "")
                    if error_code == "invalid_grant":
                        raise InvalidGrantError(
                            "Refresh token is no longer valid (revoked or expired). "
                            "The user must re-authorize this site."
                        )
                    raise ValueError(f"Token refresh failed: {resp.text}")

                token_data = resp.json()

        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"Token refresh returned no access_token: {token_data}")

        expires_in = token_data.get("expires_in", 3600)
        token_expires_at = time.time() + expires_in
        # Google does not rotate refresh tokens by default; reuse the existing one.
        new_refresh_token = token_data.get("refresh_token", refresh_token)

        from datetime import UTC, datetime

        result = {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "expires_in": expires_in,
            "token_expires_at": datetime.fromtimestamp(token_expires_at, tz=UTC).isoformat(),
        }
        logger.info("Site OAuth: refreshed access token (provider=%s)", provider)
        return result

    # ── Credential storage ──────────────────────────────────────

    async def store_site_oauth_credentials(
        self,
        site_id: str,
        user_id: str,
        tokens: dict[str, Any],
    ) -> None:
        """Encrypt and store OAuth tokens into the site's credentials blob.

        Merges the OAuth tokens (``access_token``, ``refresh_token``,
        ``token_expires_at``) into the existing encrypted credentials blob
        for the site, re-encrypts, and persists to the database.

        Args:
            site_id: UUID of the site.
            user_id: UUID of the owner (for tenant isolation).
            tokens: Token dict from :meth:`exchange_site_code` or
                :meth:`refresh_site_token`.  Must include at least
                ``access_token`` and ``refresh_token``.

        Raises:
            ValueError: If the site is not found or the user does not own it.
        """
        from core.database import get_database
        from core.encryption import get_credential_encryption

        db = get_database()
        site = await db.get_site(site_id, user_id)
        if site is None:
            raise ValueError("Site not found")

        encryptor = get_credential_encryption()

        # Decrypt existing credentials to merge (may already have OAuth tokens)
        existing: dict[str, Any] = {}
        try:
            existing = encryptor.decrypt_credentials(site["credentials"], site_id)
        except Exception:
            # If decryption fails, start fresh
            logger.warning(
                "Failed to decrypt existing credentials for site %s, starting fresh", site_id
            )

        # Merge new tokens into existing credentials
        existing["access_token"] = tokens["access_token"]
        existing["refresh_token"] = tokens["refresh_token"]
        if "token_expires_at" in tokens:
            existing["token_expires_at"] = tokens["token_expires_at"]

        encrypted = encryptor.encrypt_credentials(existing, site_id)
        await db.update_site_credentials(site_id, user_id, site["url"], encrypted)

        # Mark site as active
        await db.update_site_status(site_id, "active", "OAuth authorized", user_id=user_id)

        logger.info("Site OAuth: stored tokens for site %s (user %s)", site_id, user_id)

    # ── Helpers ────────────────────────────────────────────────

    def _site_callback_url(self) -> str:
        """Return the OAuth callback URL for site connections.

        This is ``{PUBLIC_URL}/oauth/site/callback`` — distinct from the
        dashboard login callback at ``{PUBLIC_URL}/auth/callback/{provider}``.
        """
        return f"{self._public_url}/oauth/site/callback"

    def get_provider_for_plugin_type(self, plugin_type: str) -> str | None:
        """Return the OAuth provider name for a plugin type, or None.

        Args:
            plugin_type: Plugin type name (e.g. ``"gmail"``).

        Returns:
            Provider name (e.g. ``"google"``) or ``None`` if the plugin
            type does not use OAuth.
        """
        return PLUGIN_TYPE_TO_PROVIDER.get(plugin_type)

    def get_scope_for_plugin_type(self, plugin_type: str) -> str | None:
        """Return the OAuth scope for a plugin type, or None.

        Args:
            plugin_type: Plugin type name (e.g. ``"gmail"``).

        Returns:
            OAuth scope string (e.g. ``"https://mail.google.com/"``) or
            ``None`` if the plugin type does not use OAuth.
        """
        provider = self.get_provider_for_plugin_type(plugin_type)
        if provider is None:
            return None
        provider_config = OAUTH_PROVIDERS.get(provider)
        if provider_config is None:
            return None
        return provider_config["scopes"].get(plugin_type)


class InvalidGrantError(Exception):
    """Raised when a refresh token is no longer valid (revoked or expired).

    The caller should set the site's status to ``reauth_required`` so the
    user is prompted to re-authorize the connection.
    """


# ── Singleton ──────────────────────────────────────────────────

_site_oauth_manager: SiteOAuthManager | None = None


def initialize_site_oauth_manager(
    google_client_id: str | None = None,
    google_client_secret: str | None = None,
    public_url: str | None = None,
) -> SiteOAuthManager:
    """Initialize the global SiteOAuthManager singleton.

    Reads from environment variables if arguments are not provided:
    ``GOOGLE_CLIENT_ID``, ``GOOGLE_CLIENT_SECRET``, ``PUBLIC_URL``.

    Args:
        google_client_id: Google OAuth client ID.
        google_client_secret: Google OAuth client secret.
        public_url: Public-facing URL of the server.

    Returns:
        The initialized SiteOAuthManager instance.
    """
    global _site_oauth_manager
    _site_oauth_manager = SiteOAuthManager(
        google_client_id=google_client_id or os.getenv("GOOGLE_CLIENT_ID"),
        google_client_secret=google_client_secret or os.getenv("GOOGLE_CLIENT_SECRET"),
        public_url=public_url or os.getenv("PUBLIC_URL", ""),
    )
    return _site_oauth_manager


def get_site_oauth_manager() -> SiteOAuthManager:
    """Get the global SiteOAuthManager singleton.

    Returns:
        The SiteOAuthManager singleton instance.

    Raises:
        RuntimeError: If :func:`initialize_site_oauth_manager` has not been
            called.  Falls back to lazy initialization from environment
            variables if available.
    """
    global _site_oauth_manager
    if _site_oauth_manager is None:
        _site_oauth_manager = SiteOAuthManager()
    return _site_oauth_manager
