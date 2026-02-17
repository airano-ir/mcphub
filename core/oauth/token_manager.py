"""
OAuth 2.1 Token Manager
JWT generation, validation, and refresh token rotation
"""

import logging
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from .schemas import AccessToken, RefreshToken
from .storage import get_storage

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Security-related error (e.g., token reuse)"""

    pass


class TokenManager:
    """
    OAuth 2.1 Token Manager.

    Features:
        - JWT access tokens (1 hour default)
        - Refresh tokens with rotation (7 days default)
        - Refresh token reuse detection
        - Audit logging
    """

    def __init__(self):
        self.storage = get_storage()

        # JWT Configuration — require explicit secret or generate random fallback
        self.jwt_secret = os.getenv("OAUTH_JWT_SECRET_KEY")
        if not self.jwt_secret:
            self.jwt_secret = secrets.token_urlsafe(64)
            logger.warning(
                "OAUTH_JWT_SECRET_KEY not set. Generated random JWT secret. "
                "All tokens will be invalidated on restart. "
                "Set OAUTH_JWT_SECRET_KEY in your .env for persistent tokens."
            )
        self.jwt_algorithm = os.getenv("OAUTH_JWT_ALGORITHM", "HS256")

        # Token TTLs (seconds)
        self.access_token_ttl = int(os.getenv("OAUTH_ACCESS_TOKEN_TTL", "3600"))  # 1 hour
        self.refresh_token_ttl = int(os.getenv("OAUTH_REFRESH_TOKEN_TTL", "604800"))  # 7 days

    def generate_access_token(
        self, client_id: str, scope: str, user_id: str | None = None, project_id: str = "*"
    ) -> str:
        """
        Generate JWT access token.

        Args:
            client_id: OAuth client ID
            scope: Granted scopes (space-separated)
            user_id: User ID (optional, for user-based auth)
            project_id: Project ID for scoping (default: "*" for global)

        Returns:
            JWT access token
        """
        now = datetime.now(UTC)
        now_ts = int(time.time())
        exp_ts = now_ts + self.access_token_ttl
        expires_at = now + timedelta(seconds=self.access_token_ttl)

        # JWT payload (use time.time() for correct UTC timestamps)
        payload = {
            "client_id": client_id,
            "scope": scope,
            "project_id": project_id,
            "iat": now_ts,
            "exp": exp_ts,
            "nbf": now_ts,  # Not before
            "jti": secrets.token_urlsafe(16),  # JWT ID (unique)
        }

        if user_id:
            payload["sub"] = user_id  # Subject (user ID)

        # Encode JWT
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

        # Store token metadata
        token_data = AccessToken(
            token=token,
            client_id=client_id,
            scope=scope,
            expires_at=expires_at,
            user_id=user_id,
            project_id=project_id,
            issued_at=now,
        )
        self.storage.save_access_token(token_data)

        logger.info(f"Generated access token for client {client_id} (scope: {scope})")

        return token

    def validate_access_token(self, token: str) -> dict[str, Any]:
        """
        Validate JWT access token.

        Args:
            token: JWT access token

        Returns:
            Decoded payload

        Raises:
            jwt.ExpiredSignatureError: Token expired
            jwt.InvalidTokenError: Invalid token
        """
        try:
            # Decode and verify JWT
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                },
            )

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Expired access token")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid access token: {e}")
            raise

    def generate_refresh_token(self, client_id: str, access_token: str) -> str:
        """
        Generate refresh token.

        Args:
            client_id: OAuth client ID
            access_token: Associated access token

        Returns:
            Refresh token (secure random string)
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.refresh_token_ttl)

        # Generate secure random token
        token = f"rt_{secrets.token_urlsafe(32)}"

        # Store refresh token
        token_data = RefreshToken(
            token=token,
            client_id=client_id,
            access_token=access_token,
            expires_at=expires_at,
            revoked=False,
            rotation_count=0,
            issued_at=now,
        )
        self.storage.save_refresh_token(token_data)

        logger.info(f"Generated refresh token for client {client_id}")

        return token

    def rotate_refresh_token(self, refresh_token: str, client_id: str) -> dict[str, Any]:
        """
        Rotate refresh token (OAuth 2.1 best practice).

        Security:
            - Old refresh token is immediately revoked
            - Reuse detection: if old token is used again, revoke all tokens

        Args:
            refresh_token: Current refresh token
            client_id: OAuth client ID

        Returns:
            {
                "access_token": str,
                "refresh_token": str,
                "token_type": "Bearer",
                "expires_in": int,
                "scope": str
            }

        Raises:
            ValueError: Invalid/expired refresh token
            SecurityError: Refresh token reuse detected
        """
        # Get refresh token (include revoked for reuse detection)
        token_data = self.storage.get_refresh_token(refresh_token, include_revoked=True)

        if not token_data:
            raise ValueError("Invalid or expired refresh token")

        # Check if revoked (reuse detection!)
        if token_data.revoked:
            logger.critical(
                f"Refresh token reuse detected for client {client_id}! "
                f"Revoking all tokens for this client."
            )

            # Log security event
            try:
                from core.audit_log import LogLevel, get_audit_logger

                audit_logger = get_audit_logger()
                audit_logger.log_system_event(
                    event=f"SECURITY: Refresh token reuse detected: {client_id}",
                    details={"client_id": client_id, "token": refresh_token[:20] + "..."},
                    level=LogLevel.CRITICAL,
                )
            except (ImportError, Exception):
                # Audit logging not available or failed
                pass

            # Revoke all tokens for this client (TODO: implement)
            # For now, just raise error
            raise SecurityError("Refresh token reuse detected - all tokens revoked")

        # Validate client_id match
        if token_data.client_id != client_id:
            raise ValueError("Client ID mismatch")

        # Get scope from old access token (if available)
        scope = "read"  # Default
        if token_data.access_token:
            try:
                old_payload = self.validate_access_token(token_data.access_token)
                scope = old_payload.get("scope", "read")
            except:
                pass  # Old token might be expired, use default

        # Generate new tokens
        new_access_token = self.generate_access_token(
            client_id=client_id,
            scope=scope,
            user_id=None,  # TODO: get from old token
            project_id="*",
        )

        new_refresh_token = self.generate_refresh_token(
            client_id=client_id, access_token=new_access_token
        )

        # Revoke old refresh token
        self.storage.revoke_refresh_token(refresh_token)

        # Increment rotation count
        token_data.rotation_count += 1

        logger.info(
            f"Rotated refresh token for client {client_id} "
            f"(rotation #{token_data.rotation_count})"
        )

        # Log audit event
        try:
            from core.audit_log import LogLevel, get_audit_logger

            audit_logger = get_audit_logger()
            audit_logger.log_system_event(
                event=f"Refresh token rotated for {client_id}",
                details={"client_id": client_id, "rotation_count": token_data.rotation_count},
                level=LogLevel.INFO,
            )
        except (ImportError, Exception):
            # Audit logging not available or failed
            pass

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "Bearer",
            "expires_in": self.access_token_ttl,
            "scope": scope,
        }

    def revoke_token(self, token: str, token_type: str = "refresh"):
        """
        Revoke token.

        Args:
            token: Token to revoke
            token_type: "refresh" or "access"
        """
        if token_type == "refresh":
            self.storage.revoke_refresh_token(token)
            logger.info("Revoked refresh token")

        # Access tokens cannot be revoked (JWT stateless)
        # They expire naturally after TTL


# Singleton
_token_manager: TokenManager | None = None


def get_token_manager() -> TokenManager:
    """Get singleton TokenManager instance"""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
