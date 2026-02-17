"""
CSRF Protection for OAuth Authorization

Implements token-based CSRF protection for the OAuth authorization flow.
Tokens are stored in-memory with 10-minute expiry.

Part of Phase E: Custom OAuth Authorization Page
"""

import secrets
import time

class CSRFTokenManager:
    """
    Manages CSRF tokens for OAuth authorization requests.

    Features:
    - Generates cryptographically secure random tokens
    - In-memory storage with automatic expiry
    - 10-minute token lifetime
    - Automatic cleanup of expired tokens
    """

    def __init__(self, token_lifetime_seconds: int = 600):
        """
        Initialize CSRF token manager.

        Args:
            token_lifetime_seconds: Token lifetime in seconds (default: 600 = 10 minutes)
        """
        self._tokens: dict[str, float] = {}  # token -> expiry_timestamp
        self._token_lifetime = token_lifetime_seconds

    def generate_token(self) -> str:
        """
        Generate a new CSRF token.

        Returns:
            Secure random token (32 bytes, hex-encoded = 64 characters)
        """
        token = secrets.token_hex(32)
        expiry = time.time() + self._token_lifetime
        self._tokens[token] = expiry

        # Cleanup expired tokens (lazy cleanup)
        self._cleanup_expired()

        return token

    def validate_token(self, token: str, consume: bool = True) -> bool:
        """
        Validate a CSRF token.

        Args:
            token: CSRF token to validate
            consume: If True, token is removed after validation (one-time use)

        Returns:
            True if token is valid and not expired, False otherwise
        """
        if not token or token not in self._tokens:
            return False

        expiry = self._tokens[token]
        now = time.time()

        # Check if token is expired
        if now > expiry:
            # Remove expired token
            self._tokens.pop(token, None)
            return False

        # Token is valid
        if consume:
            # Remove token (one-time use)
            self._tokens.pop(token, None)

        return True

    def _cleanup_expired(self):
        """
        Remove expired tokens from storage.

        Called automatically during token generation to prevent memory leaks.
        """
        now = time.time()
        expired_tokens = [token for token, expiry in self._tokens.items() if now > expiry]

        for token in expired_tokens:
            self._tokens.pop(token, None)

    def get_stats(self) -> dict[str, int]:
        """
        Get statistics about stored tokens.

        Returns:
            Dictionary with token statistics
        """
        now = time.time()
        active_tokens = sum(1 for expiry in self._tokens.values() if expiry > now)
        expired_tokens = len(self._tokens) - active_tokens

        return {
            "total_tokens": len(self._tokens),
            "active_tokens": active_tokens,
            "expired_tokens": expired_tokens,
            "token_lifetime_seconds": self._token_lifetime,
        }

# Global CSRF token manager instance
_csrf_manager: CSRFTokenManager | None = None

def get_csrf_manager() -> CSRFTokenManager:
    """
    Get the global CSRF token manager instance.

    Returns:
        Global CSRFTokenManager instance (singleton)
    """
    global _csrf_manager
    if _csrf_manager is None:
        _csrf_manager = CSRFTokenManager()
    return _csrf_manager
