"""
Dashboard Authentication - Session-based authentication for Web UI.

Phase K.1: Core Infrastructure
"""

import logging
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

import jwt
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

logger = logging.getLogger(__name__)

# Singleton instance
_dashboard_auth: Optional["DashboardAuth"] = None


@dataclass
class DashboardSession:
    """Dashboard session information."""

    session_id: str
    created_at: datetime
    expires_at: datetime
    user_type: str  # "master" or "api_key"
    key_id: str | None = None  # For API key sessions


class DashboardAuth:
    """
    Dashboard authentication manager.

    Handles session-based authentication using JWT tokens stored in httpOnly cookies.
    """

    COOKIE_NAME = "mcp_dashboard_session"

    def __init__(
        self,
        secret_key: str | None = None,
        session_expiry_hours: int = 24,
        master_api_key: str | None = None,
    ):
        """
        Initialize dashboard authentication.

        Args:
            secret_key: Secret for JWT signing. Generated if not provided.
            session_expiry_hours: Session expiration in hours.
            master_api_key: Master API key for validation.
        """
        self.secret_key = secret_key or os.environ.get(
            "DASHBOARD_SESSION_SECRET", os.environ.get("OAUTH_JWT_SECRET_KEY")
        )
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)
            logger.warning(
                "DASHBOARD_SESSION_SECRET not set. Generated random session secret. "
                "All dashboard sessions will be invalidated on restart. "
                "Set DASHBOARD_SESSION_SECRET in your .env for persistent sessions."
            )
        self.session_expiry_hours = int(
            os.environ.get("DASHBOARD_SESSION_EXPIRY_HOURS", session_expiry_hours)
        )
        self.master_api_key = master_api_key or os.environ.get("MASTER_API_KEY")

        # Rate limiting for login attempts
        self._login_attempts: dict[str, list] = {}  # IP -> list of timestamps
        self.max_login_attempts = int(os.environ.get("DASHBOARD_LOGIN_RATE_LIMIT", 5))

        logger.info(f"DashboardAuth initialized with {self.session_expiry_hours}h session expiry")

    def validate_api_key(self, api_key: str) -> tuple[bool, str, str | None]:
        """
        Validate an API key for dashboard login.

        Args:
            api_key: The API key to validate.

        Returns:
            Tuple of (is_valid, user_type, key_id)
            - user_type: "master" or "api_key"
            - key_id: Key ID for API keys, None for master
        """
        if not api_key:
            return False, "", None

        # Check master API key
        if self.master_api_key and secrets.compare_digest(api_key, self.master_api_key):
            return True, "master", None

        # Check project API keys with admin scope
        try:
            from core.api_keys import get_api_key_manager

            api_key_manager = get_api_key_manager()

            # Dashboard login is not project-specific, so skip project check
            # and require admin scope
            key_id = api_key_manager.validate_key(
                api_key, project_id="*", required_scope="admin", skip_project_check=True
            )
            if key_id:
                return True, "api_key", key_id
        except Exception as e:
            logger.warning(f"Error checking API key: {e}")

        return False, "", None

    def check_rate_limit(self, client_ip: str) -> bool:
        """
        Check if login attempts are within rate limit.

        Args:
            client_ip: Client IP address.

        Returns:
            True if within limit, False if exceeded.
        """
        now = datetime.now(UTC)
        window = timedelta(minutes=1)

        # Clean old attempts
        if client_ip in self._login_attempts:
            self._login_attempts[client_ip] = [
                ts for ts in self._login_attempts[client_ip] if now - ts < window
            ]
        else:
            self._login_attempts[client_ip] = []

        return len(self._login_attempts[client_ip]) < self.max_login_attempts

    def record_login_attempt(self, client_ip: str):
        """Record a login attempt for rate limiting."""
        if client_ip not in self._login_attempts:
            self._login_attempts[client_ip] = []
        self._login_attempts[client_ip].append(datetime.now(UTC))

    def create_session(self, user_type: str, key_id: str | None = None) -> str:
        """
        Create a new dashboard session.

        Args:
            user_type: Type of user ("master" or "api_key").
            key_id: Key ID for API key sessions.

        Returns:
            JWT session token.
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=self.session_expiry_hours)
        session_id = secrets.token_hex(16)

        payload = {
            "sid": session_id,
            "type": user_type,
            "iat": now.timestamp(),
            "exp": expires_at.timestamp(),
        }
        if key_id:
            payload["kid"] = key_id

        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        logger.info(f"Dashboard session created: type={user_type}, expires={expires_at}")

        return token

    def validate_session(self, token: str) -> DashboardSession | None:
        """
        Validate a session token.

        Args:
            token: JWT session token.

        Returns:
            DashboardSession if valid, None otherwise.
        """
        if not token:
            return None

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            return DashboardSession(
                session_id=payload["sid"],
                created_at=datetime.fromtimestamp(payload["iat"]),
                expires_at=datetime.fromtimestamp(payload["exp"]),
                user_type=payload["type"],
                key_id=payload.get("kid"),
            )
        except jwt.ExpiredSignatureError:
            logger.debug("Dashboard session expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid dashboard session token: {e}")
            return None

    def get_session_from_request(self, request: Request) -> DashboardSession | None:
        """
        Extract and validate session from request.

        Args:
            request: Starlette request object.

        Returns:
            DashboardSession if valid session exists, None otherwise.
        """
        token = request.cookies.get(self.COOKIE_NAME)
        if not token:
            return None
        return self.validate_session(token)

    def set_session_cookie(self, response: Response, token: str) -> Response:
        """
        Set session cookie on response.

        Args:
            response: Response object to modify.
            token: Session token to set.

        Returns:
            Modified response.
        """
        response.set_cookie(
            key=self.COOKIE_NAME,
            value=token,
            max_age=self.session_expiry_hours * 3600,
            httponly=True,
            secure=os.environ.get("DASHBOARD_SECURE_COOKIE", "true").lower() == "true",
            samesite="lax",
            path="/",  # Allow cookie for both /dashboard and /api/dashboard
        )
        return response

    def clear_session_cookie(self, response: Response) -> Response:
        """
        Clear session cookie on response.

        Args:
            response: Response object to modify.

        Returns:
            Modified response.
        """
        response.delete_cookie(
            key=self.COOKIE_NAME,
            path="/",  # Match the path used in set_cookie
        )
        return response

    def require_auth(self, request: Request) -> RedirectResponse | None:
        """
        Check if request is authenticated, redirect to login if not.

        Args:
            request: Starlette request object.

        Returns:
            RedirectResponse to login page if not authenticated, None if OK.
        """
        session = self.get_session_from_request(request)
        if not session:
            # Store original URL for redirect after login
            next_url = str(request.url.path)
            if request.url.query:
                next_url += f"?{request.url.query}"
            return RedirectResponse(
                url=f"/dashboard/login?next={next_url}",
                status_code=303,
            )
        return None


def get_dashboard_auth() -> DashboardAuth:
    """Get or create the singleton DashboardAuth instance."""
    global _dashboard_auth
    if _dashboard_auth is None:
        _dashboard_auth = DashboardAuth()
    return _dashboard_auth
