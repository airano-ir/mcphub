"""User authentication system with OAuth Social Login (GitHub + Google).

Handles OAuth 2.0 authorization flows, token exchange, user info fetching,
session creation (JWT cookies), and registration rate limiting.

This module is for user-facing authentication (Track E.2). The existing
admin authentication (core/auth.py, core/dashboard/auth.py) is unchanged.

Usage:
    auth = initialize_user_auth(
        github_client_id="...",
        github_client_secret="...",
        public_url="https://mcp.example.com",
    )
    url, state = auth.get_authorization_url("github")
    # ... user redirected, callback received ...
    user_info = await auth.exchange_code("github", code)
    token = auth.create_user_session(user_id="...", email="...", name="...", role="user")
"""

import logging
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt

logger = logging.getLogger(__name__)

# OAuth provider endpoints
_GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# State expiry: 10 minutes
_STATE_EXPIRY_SECONDS = 600

# Registration rate limit: 3 per IP per hour
_REG_RATE_LIMIT = 3
_REG_RATE_WINDOW = 3600  # 1 hour


class OAuthProvider:
    """OAuth provider constants (for type hints / constants)."""

    GITHUB = "github"
    GOOGLE = "google"


class UserAuth:
    """OAuth Social Login and user session management.

    Manages OAuth authorization URL generation, code-for-token exchange,
    user info fetching, JWT session creation/validation, and registration
    rate limiting.
    """

    def __init__(
        self,
        github_client_id: str | None = None,
        github_client_secret: str | None = None,
        google_client_id: str | None = None,
        google_client_secret: str | None = None,
        public_url: str | None = None,
        session_secret: str | None = None,
        session_expiry_hours: int = 168,  # 7 days
    ) -> None:
        """Initialize user authentication.

        Args:
            github_client_id: GitHub OAuth App client ID.
            github_client_secret: GitHub OAuth App client secret.
            google_client_id: Google OAuth client ID.
            google_client_secret: Google OAuth client secret.
            public_url: Public-facing URL of the server (for callbacks).
            session_secret: Secret key for JWT session signing.
            session_expiry_hours: Session token lifetime in hours.
        """
        self._github_client_id = github_client_id
        self._github_client_secret = github_client_secret
        self._google_client_id = google_client_id
        self._google_client_secret = google_client_secret
        self._public_url = (public_url or "").rstrip("/")

        self._session_secret = session_secret or os.getenv(
            "DASHBOARD_SESSION_SECRET",
            os.getenv("OAUTH_JWT_SECRET_KEY", secrets.token_hex(32)),
        )
        self._session_expiry_hours = int(
            os.getenv("SESSION_EXPIRY_HOURS", str(session_expiry_hours))
        )

        # CSRF state tokens: state -> timestamp
        self._pending_states: dict[str, float] = {}

        # Registration rate limiting: IP -> [timestamps]
        self._registration_records: dict[str, list[float]] = {}

        providers = self.available_providers()
        if providers and not self._public_url:
            logger.warning(
                "OAuth providers configured (%s) but PUBLIC_URL is not set. "
                "OAuth login will fail until PUBLIC_URL is configured.",
                providers,
            )
        logger.info(
            "UserAuth initialized: providers=%s, session_expiry=%dh",
            providers,
            self._session_expiry_hours,
        )

    # ── Provider availability ─────────────────────────────────

    def available_providers(self) -> list[str]:
        """Return list of configured OAuth providers.

        Returns:
            List of provider name strings (e.g. ["github", "google"]).
        """
        providers: list[str] = []
        if self._github_client_id and self._github_client_secret:
            providers.append("github")
        if self._google_client_id and self._google_client_secret:
            providers.append("google")
        return providers

    # ── OAuth URL generation ──────────────────────────────────

    def get_authorization_url(self, provider: str) -> tuple[str, str]:
        """Generate OAuth authorization URL with CSRF state.

        Args:
            provider: "github" or "google".

        Returns:
            Tuple of (authorization_url, state_token).

        Raises:
            ValueError: If provider is unsupported or not configured.
        """
        if not self._public_url:
            raise ValueError(
                "PUBLIC_URL environment variable must be set for OAuth login to work. "
                "Example: PUBLIC_URL=https://mcp.example.com"
            )

        state = secrets.token_hex(32)
        self._pending_states[state] = time.time()
        self._cleanup_expired_states()

        callback_url = f"{self._public_url}/auth/callback/{provider}"

        if provider == "github":
            if not self._github_client_id:
                raise ValueError("GitHub OAuth not configured")
            params = {
                "client_id": self._github_client_id,
                "redirect_uri": callback_url,
                "scope": "read:user user:email",
                "state": state,
            }
            return f"{_GITHUB_AUTH_URL}?{urlencode(params)}", state

        if provider == "google":
            if not self._google_client_id:
                raise ValueError("Google OAuth not configured")
            params = {
                "client_id": self._google_client_id,
                "redirect_uri": callback_url,
                "scope": "openid email profile",
                "response_type": "code",
                "state": state,
                "access_type": "online",
            }
            return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}", state

        raise ValueError(f"Unsupported provider: {provider}")

    # ── State validation ──────────────────────────────────────

    def validate_state(self, state: str) -> bool:
        """Validate and consume an OAuth state token (one-time use).

        Args:
            state: The state parameter from the callback.

        Returns:
            True if valid and not expired, False otherwise.
        """
        timestamp = self._pending_states.pop(state, None)
        if timestamp is None:
            return False
        return not (time.time() - timestamp > _STATE_EXPIRY_SECONDS)

    def _cleanup_expired_states(self) -> None:
        """Remove expired state tokens."""
        now = time.time()
        expired = [s for s, t in self._pending_states.items() if now - t > _STATE_EXPIRY_SECONDS]
        for s in expired:
            del self._pending_states[s]

    # ── Token exchange ────────────────────────────────────────

    async def exchange_code(self, provider: str, code: str) -> dict:
        """Exchange authorization code for user info.

        Args:
            provider: "github" or "google".
            code: Authorization code from callback.

        Returns:
            Dict with keys: provider, provider_id, email, name, avatar_url.

        Raises:
            ValueError: If token exchange or user info fetch fails.
        """
        if provider == "github":
            return await self._exchange_github(code)
        if provider == "google":
            return await self._exchange_google(code)
        raise ValueError(f"Unsupported provider: {provider}")

    async def _exchange_github(self, code: str) -> dict:
        """Exchange GitHub authorization code for user info.

        Args:
            code: GitHub authorization code.

        Returns:
            Dict with provider, provider_id, email, name, avatar_url.
        """
        callback_url = f"{self._public_url}/auth/callback/github"

        async with httpx.AsyncClient() as client:
            # Exchange code for access token
            token_resp = await client.post(
                _GITHUB_TOKEN_URL,
                data={
                    "client_id": self._github_client_id,
                    "client_secret": self._github_client_secret,
                    "code": code,
                    "redirect_uri": callback_url,
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code != 200:
                raise ValueError(f"Failed to exchange GitHub code: {token_resp.text}")

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError(f"Failed to exchange GitHub code: {token_data}")

            # Fetch user info
            user_resp = await client.get(
                _GITHUB_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_data = user_resp.json()

            email = user_data.get("email")
            if not email:
                # Fetch from /user/emails endpoint (private email fallback)
                emails_resp = await client.get(
                    _GITHUB_EMAILS_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if emails_resp.status_code == 200:
                    emails = emails_resp.json()
                    primary = next(
                        (e for e in emails if e.get("primary") and e.get("verified")),
                        None,
                    )
                    if primary:
                        email = primary["email"]
                    elif emails:
                        email = emails[0]["email"]

        return {
            "provider": "github",
            "provider_id": str(user_data["id"]),
            "email": email,
            "name": user_data.get("name") or user_data.get("login"),
            "avatar_url": user_data.get("avatar_url"),
        }

    async def _exchange_google(self, code: str) -> dict:
        """Exchange Google authorization code for user info.

        Args:
            code: Google authorization code.

        Returns:
            Dict with provider, provider_id, email, name, avatar_url.
        """
        callback_url = f"{self._public_url}/auth/callback/google"

        async with httpx.AsyncClient() as client:
            # Exchange code for access token
            token_resp = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "client_id": self._google_client_id,
                    "client_secret": self._google_client_secret,
                    "code": code,
                    "redirect_uri": callback_url,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                raise ValueError(f"Failed to exchange Google code: {token_resp.text}")

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError(f"Failed to exchange Google code: {token_data}")

            # Fetch user info
            user_resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_data = user_resp.json()

        return {
            "provider": "google",
            "provider_id": str(user_data["sub"]),
            "email": user_data.get("email"),
            "name": user_data.get("name"),
            "avatar_url": user_data.get("picture"),
        }

    # ── Registration rate limiting ────────────────────────────

    def check_registration_rate(self, client_ip: str) -> bool:
        """Check if IP is within registration rate limit.

        Allows up to 3 registrations per IP per hour. Expired records
        are cleaned up automatically.

        Args:
            client_ip: Client IP address.

        Returns:
            True if registration is allowed, False if rate limited.
        """
        now = time.time()
        records = self._registration_records.get(client_ip, [])
        # Keep only records within the window
        records = [t for t in records if now - t < _REG_RATE_WINDOW]
        self._registration_records[client_ip] = records
        return len(records) < _REG_RATE_LIMIT

    def record_registration(self, client_ip: str) -> None:
        """Record a registration event for rate limiting.

        Args:
            client_ip: Client IP address.
        """
        if client_ip not in self._registration_records:
            self._registration_records[client_ip] = []
        self._registration_records[client_ip].append(time.time())

    # ── Session management ────────────────────────────────────

    def create_user_session(
        self,
        user_id: str,
        email: str,
        name: str | None,
        role: str,
    ) -> str:
        """Create a JWT session token for an OAuth user.

        Args:
            user_id: User UUID from database.
            email: User email.
            name: User display name.
            role: User role ('user' or 'admin').

        Returns:
            JWT token string.
        """
        now = time.time()
        payload = {
            "uid": user_id,
            "email": email,
            "name": name or "",
            "role": role,
            "type": "oauth_user",
            "iat": now,
            "exp": now + self._session_expiry_hours * 3600,
        }
        return jwt.encode(payload, self._session_secret, algorithm="HS256")

    def validate_user_session(self, token: str) -> dict | None:
        """Validate a user session JWT token.

        Args:
            token: JWT token string.

        Returns:
            Dict with user_id, email, name, role, type -- or None if invalid.
        """
        try:
            payload = jwt.decode(token, self._session_secret, algorithms=["HS256"])
            return {
                "user_id": payload["uid"],
                "email": payload["email"],
                "name": payload.get("name", ""),
                "role": payload.get("role", "user"),
                "type": payload.get("type", "oauth_user"),
            }
        except jwt.ExpiredSignatureError:
            logger.debug("User session expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug("Invalid user session token: %s", e)
            return None


# ── Singleton ─────────────────────────────────────────────────

_user_auth: UserAuth | None = None


def initialize_user_auth(
    github_client_id: str | None = None,
    github_client_secret: str | None = None,
    google_client_id: str | None = None,
    google_client_secret: str | None = None,
    public_url: str | None = None,
    **kwargs,
) -> UserAuth:
    """Initialize the global UserAuth singleton.

    Reads from env vars if arguments are not provided:
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    PUBLIC_URL.

    Args:
        github_client_id: GitHub OAuth App client ID.
        github_client_secret: GitHub OAuth App client secret.
        google_client_id: Google OAuth client ID.
        google_client_secret: Google OAuth client secret.
        public_url: Public-facing URL of the server.
        **kwargs: Additional keyword args passed to UserAuth.

    Returns:
        The initialized UserAuth instance.
    """
    global _user_auth
    _user_auth = UserAuth(
        github_client_id=github_client_id or os.getenv("GITHUB_CLIENT_ID"),
        github_client_secret=github_client_secret or os.getenv("GITHUB_CLIENT_SECRET"),
        google_client_id=google_client_id or os.getenv("GOOGLE_CLIENT_ID"),
        google_client_secret=google_client_secret or os.getenv("GOOGLE_CLIENT_SECRET"),
        public_url=public_url or os.getenv("PUBLIC_URL", ""),
        **kwargs,
    )
    return _user_auth


def get_user_auth() -> UserAuth:
    """Get the global UserAuth singleton.

    Returns:
        The UserAuth singleton instance.

    Raises:
        RuntimeError: If initialize_user_auth() has not been called.
    """
    if _user_auth is None:
        raise RuntimeError("UserAuth not initialized. Call initialize_user_auth() first.")
    return _user_auth
