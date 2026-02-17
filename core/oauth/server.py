"""
OAuth 2.1 Authorization Server
Handles OAuth flows: authorization_code, refresh_token, client_credentials
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from .client_registry import get_client_registry
from .pkce import validate_code_challenge
from .schemas import AuthorizationCode, TokenResponse
from .storage import get_storage
from .token_manager import get_token_manager

logger = logging.getLogger(__name__)

class OAuthError(Exception):
    """OAuth error with error code and description"""

    def __init__(self, error: str, error_description: str, status_code: int = 400):
        self.error = error
        self.error_description = error_description
        self.status_code = status_code
        super().__init__(error_description)

class OAuthServer:
    """
    OAuth 2.1 Authorization Server

    Implements:
        - Authorization Code Grant with PKCE (mandatory)
        - Refresh Token Grant with rotation
        - Client Credentials Grant (machine-to-machine)
    """

    def __init__(self):
        self.client_registry = get_client_registry()
        self.token_manager = get_token_manager()
        self.storage = get_storage()

        # Authorization code TTL (5 minutes)
        self.auth_code_ttl = 300

    def validate_authorization_request(
        self,
        client_id: str,
        redirect_uri: str,
        response_type: str,
        code_challenge: str,
        code_challenge_method: str,
        scope: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate OAuth authorization request (Step 1 of Authorization Code flow)

        Args:
            client_id: OAuth client ID
            redirect_uri: Callback URI for authorization code
            response_type: Must be "code" (OAuth 2.1)
            code_challenge: PKCE code challenge
            code_challenge_method: Must be "S256" (OAuth 2.1)
            scope: Requested scopes (space-separated)
            state: Optional state parameter for CSRF protection

        Returns:
            Dict with validated parameters

        Raises:
            OAuthError: If validation fails
        """
        # Validate client
        client = self.client_registry.get_client(client_id)
        if not client:
            raise OAuthError(
                error="invalid_client",
                error_description=f"Client {client_id} not found",
                status_code=401,
            )

        # Validate response_type (OAuth 2.1: only "code" is allowed)
        if response_type != "code":
            raise OAuthError(
                error="unsupported_response_type",
                error_description="Only 'code' response_type is supported (OAuth 2.1)",
            )

        if "authorization_code" not in client.grant_types:
            raise OAuthError(
                error="unauthorized_client",
                error_description="Client not authorized for authorization_code grant",
            )

        # Validate redirect_uri (exact match)
        if redirect_uri not in client.redirect_uris:
            raise OAuthError(
                error="invalid_request", error_description=f"Invalid redirect_uri: {redirect_uri}"
            )

        # Validate PKCE (mandatory in OAuth 2.1)
        if not code_challenge or not code_challenge_method:
            raise OAuthError(
                error="invalid_request",
                error_description="code_challenge and code_challenge_method are required (OAuth 2.1)",
            )

        if code_challenge_method != "S256":
            raise OAuthError(
                error="invalid_request",
                error_description="Only S256 code_challenge_method is supported (OAuth 2.1)",
            )

        # Validate scope
        requested_scopes = scope.split() if scope else ["read"]
        for s in requested_scopes:
            if s not in client.allowed_scopes:
                raise OAuthError(
                    error="invalid_scope",
                    error_description=f"Scope '{s}' not allowed for this client",
                )

        return {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(requested_scopes),
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "state": state,
        }

    def create_authorization_code(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: str,
        code_challenge_method: str = "S256",
        user_id: str | None = None,
        api_key_id: str | None = None,
        api_key_project_id: str | None = None,
        api_key_scope: str | None = None,
    ) -> str:
        """
        Create authorization code (Step 2 of Authorization Code flow)

        Args:
            client_id: OAuth client ID
            redirect_uri: Redirect URI
            scope: Granted scopes
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE method (S256)
            user_id: Optional user ID (for user-based auth)
            api_key_id: Optional API Key ID for scope/project inheritance
            api_key_project_id: Optional project ID from API Key
            api_key_scope: Optional scope from API Key

        Returns:
            Authorization code (valid for 5 minutes)
        """
        # Generate secure random code
        code = f"auth_{secrets.token_urlsafe(32)}"

        # Create authorization code
        auth_code = AuthorizationCode(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.auth_code_ttl),
            used=False,
            user_id=user_id,
            api_key_id=api_key_id,
            api_key_project_id=api_key_project_id,
            api_key_scope=api_key_scope,
        )

        # Save to storage
        self.storage.save_authorization_code(auth_code)

        logger.info(f"Created authorization code for client {client_id}")

        return code

    def exchange_code_for_tokens(
        self, client_id: str, client_secret: str, code: str, redirect_uri: str, code_verifier: str
    ) -> TokenResponse:
        """
        Exchange authorization code for tokens (Step 3 of Authorization Code flow)

        Args:
            client_id: OAuth client ID
            client_secret: Client secret
            code: Authorization code from /authorize
            redirect_uri: Same redirect_uri used in /authorize
            code_verifier: PKCE code verifier

        Returns:
            TokenResponse with access_token and refresh_token

        Raises:
            OAuthError: If validation fails
        """
        # Validate client credentials
        if not self.client_registry.validate_client_secret(client_id, client_secret):
            raise OAuthError(
                error="invalid_client",
                error_description="Invalid client credentials",
                status_code=401,
            )

        # Get authorization code
        auth_code = self.storage.get_authorization_code(code)
        if not auth_code:
            raise OAuthError(
                error="invalid_grant", error_description="Invalid or expired authorization code"
            )

        # Check if already used (prevents replay attacks)
        if auth_code.used:
            # Revoke all tokens for this client (security measure)
            logger.critical(
                f"Authorization code reuse detected for client {client_id}! "
                f"Code: {code[:20]}..."
            )
            raise OAuthError(
                error="invalid_grant", error_description="Authorization code already used"
            )

        # Validate client_id match
        if auth_code.client_id != client_id:
            raise OAuthError(error="invalid_grant", error_description="Client ID mismatch")

        # Validate redirect_uri match
        if auth_code.redirect_uri != redirect_uri:
            raise OAuthError(error="invalid_grant", error_description="Redirect URI mismatch")

        # Validate PKCE code_verifier
        if not validate_code_challenge(
            code_verifier, auth_code.code_challenge, auth_code.code_challenge_method
        ):
            raise OAuthError(
                error="invalid_grant",
                error_description="Invalid code_verifier (PKCE validation failed)",
            )

        # Mark code as used
        auth_code.used = True
        self.storage.update_authorization_code(code, auth_code)

        # Generate tokens with API Key's project and scope
        # If authorization code has API Key metadata, use it for scoping
        project_id = auth_code.api_key_project_id or "*"
        token_scope = auth_code.api_key_scope or auth_code.scope

        access_token = self.token_manager.generate_access_token(
            client_id=client_id,
            scope=token_scope,
            user_id=auth_code.user_id or auth_code.api_key_id,
            project_id=project_id,
        )

        refresh_token = self.token_manager.generate_refresh_token(
            client_id=client_id, access_token=access_token
        )

        logger.info(
            f"Exchanged authorization code for tokens: {client_id} "
            f"(project_id={project_id}, scope={token_scope})"
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=self.token_manager.access_token_ttl,
            refresh_token=refresh_token,
            scope=auth_code.scope,
        )

    def handle_refresh_token_grant(
        self, client_id: str, client_secret: str, refresh_token: str
    ) -> TokenResponse:
        """
        Handle refresh token grant (refresh access token)

        Args:
            client_id: OAuth client ID
            client_secret: Client secret
            refresh_token: Current refresh token

        Returns:
            TokenResponse with new access_token and refresh_token

        Raises:
            OAuthError: If validation fails
        """
        # Validate client credentials
        if not self.client_registry.validate_client_secret(client_id, client_secret):
            raise OAuthError(
                error="invalid_client",
                error_description="Invalid client credentials",
                status_code=401,
            )

        # Check grant type is allowed
        client = self.client_registry.get_client(client_id)
        if "refresh_token" not in client.grant_types:
            raise OAuthError(
                error="unauthorized_client",
                error_description="Client not authorized for refresh_token grant",
            )

        try:
            # Rotate refresh token
            new_tokens = self.token_manager.rotate_refresh_token(
                refresh_token=refresh_token, client_id=client_id
            )

            return TokenResponse(**new_tokens)

        except ValueError as e:
            raise OAuthError(error="invalid_grant", error_description=str(e))
        except Exception as e:
            logger.error(f"Error rotating refresh token: {e}")
            raise OAuthError(
                error="server_error", error_description="Internal server error", status_code=500
            )

    def handle_client_credentials_grant(
        self, client_id: str, client_secret: str, scope: str | None = None
    ) -> TokenResponse:
        """
        Handle client credentials grant (machine-to-machine)

        Args:
            client_id: OAuth client ID
            client_secret: Client secret
            scope: Requested scopes (space-separated)

        Returns:
            TokenResponse with access_token (no refresh_token)

        Raises:
            OAuthError: If validation fails
        """
        # Validate client credentials
        if not self.client_registry.validate_client_secret(client_id, client_secret):
            raise OAuthError(
                error="invalid_client",
                error_description="Invalid client credentials",
                status_code=401,
            )

        # Check grant type is allowed
        client = self.client_registry.get_client(client_id)
        if "client_credentials" not in client.grant_types:
            raise OAuthError(
                error="unauthorized_client",
                error_description="Client not authorized for client_credentials grant",
            )

        # Validate scope
        requested_scopes = scope.split() if scope else [client.scope]
        for s in requested_scopes:
            if s not in client.allowed_scopes:
                raise OAuthError(
                    error="invalid_scope",
                    error_description=f"Scope '{s}' not allowed for this client",
                )

        # Generate access token (no refresh token for client credentials)
        access_token = self.token_manager.generate_access_token(
            client_id=client_id, scope=" ".join(requested_scopes)
        )

        logger.info(f"Generated client credentials token for {client_id}")

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=self.token_manager.access_token_ttl,
            scope=" ".join(requested_scopes),
        )

# Singleton
_oauth_server: OAuthServer | None = None

def get_oauth_server() -> OAuthServer:
    """Get singleton OAuthServer instance"""
    global _oauth_server
    if _oauth_server is None:
        _oauth_server = OAuthServer()
    return _oauth_server
