"""
OAuth 2.1 Infrastructure for MCP Hub

This module provides OAuth 2.1 compliant authentication and authorization
infrastructure with PKCE support, refresh token rotation, and security best practices.
"""

# Schemas
# Client Registry
from .client_registry import ClientRegistry, get_client_registry

# CSRF Protection (Phase E)
from .csrf import CSRFTokenManager, get_csrf_manager

# PKCE utilities
from .pkce import generate_code_challenge, generate_code_verifier, validate_code_challenge
from .schemas import (
    AccessToken,
    AuthorizationCode,
    OAuthClient,
    RefreshToken,
    TokenRequest,
    TokenResponse,
)

# OAuth Server
from .server import OAuthError, OAuthServer, get_oauth_server

# Storage
from .storage import BaseStorage, JSONStorage, get_storage

# Token Manager
from .token_manager import SecurityError, TokenManager, get_token_manager

__all__ = [
    # Schemas
    "OAuthClient",
    "AuthorizationCode",
    "AccessToken",
    "RefreshToken",
    "TokenRequest",
    "TokenResponse",
    # PKCE
    "generate_code_verifier",
    "generate_code_challenge",
    "validate_code_challenge",
    # Storage
    "BaseStorage",
    "JSONStorage",
    "get_storage",
    # Client Registry
    "ClientRegistry",
    "get_client_registry",
    # Token Manager
    "TokenManager",
    "SecurityError",
    "get_token_manager",
    # OAuth Server
    "OAuthServer",
    "OAuthError",
    "get_oauth_server",
    # CSRF Protection
    "CSRFTokenManager",
    "get_csrf_manager",
]
