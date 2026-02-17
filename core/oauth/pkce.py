"""
PKCE (Proof Key for Code Exchange) Implementation
RFC 7636 - OAuth 2.1 Mandatory
"""

import base64
import hashlib
import secrets
from typing import Literal


def generate_code_verifier(length: int = 64) -> str:
    """
    Generate PKCE code verifier.

    Args:
        length: Length of verifier (43-128 characters)

    Returns:
        URL-safe random string

    OAuth 2.1 Spec:
        - Length: 43-128 characters
        - Character set: [A-Za-z0-9-._~] (unreserved characters)
    """
    if not 43 <= length <= 128:
        raise ValueError("Code verifier length must be between 43-128")

    # Generate random bytes and encode as URL-safe base64
    random_bytes = secrets.token_bytes(length)
    verifier = base64.urlsafe_b64encode(random_bytes).decode("utf-8")

    # Remove padding and truncate to desired length
    verifier = verifier.rstrip("=")[:length]

    return verifier


def generate_code_challenge(code_verifier: str, method: Literal["S256"] = "S256") -> str:
    """
    Generate PKCE code challenge from verifier.

    Args:
        code_verifier: Code verifier string
        method: Challenge method (OAuth 2.1: only S256)

    Returns:
        Base64 URL-encoded SHA256 hash of verifier

    OAuth 2.1 Spec:
        - Only S256 method is allowed (plain is removed)
        - code_challenge = BASE64URL(SHA256(code_verifier))
    """
    if method != "S256":
        raise ValueError("OAuth 2.1 only supports S256 method (plain is removed)")

    if not code_verifier:
        raise ValueError("Code verifier cannot be empty")

    # SHA256 hash
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()

    # Base64 URL encode (no padding)
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    return challenge


def validate_code_challenge(
    code_verifier: str, code_challenge: str, method: Literal["S256"] = "S256"
) -> bool:
    """
    Validate PKCE code verifier against challenge.

    Args:
        code_verifier: Code verifier from client
        code_challenge: Code challenge from authorization request
        method: Challenge method

    Returns:
        True if valid, False otherwise
    """
    if method != "S256":
        raise ValueError("Only S256 method is supported")

    try:
        # Generate challenge from verifier
        expected_challenge = generate_code_challenge(code_verifier, method)

        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(expected_challenge, code_challenge)

    except Exception:
        return False
