"""
OAuth 2.1 Pydantic Schemas
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class OAuthClient(BaseModel):
    """OAuth 2.1 Client Model"""

    client_id: str = Field(..., description="Client identifier (e.g., cmp_client_xxx)")
    client_secret_hash: str = Field(..., description="SHA256 hash of client secret")
    client_name: str = Field(..., description="Human-readable client name")
    redirect_uris: list[str] = Field(..., description="Allowed redirect URIs (exact match)")
    grant_types: list[str] = Field(
        default=["authorization_code", "refresh_token"], description="Allowed grant types"
    )
    response_types: list[str] = Field(default=["code"], description="Allowed response types")
    scope: str = Field(default="read", description="Default scope for this client")
    allowed_scopes: list[str] = Field(
        default=["read", "write"], description="All scopes this client can request"
    )
    token_endpoint_auth_method: str = Field(
        default="client_secret_post", description="Token endpoint authentication method"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = Field(default_factory=dict)

    @field_validator("redirect_uris")
    def validate_redirect_uris(cls, v):
        """Validate redirect URIs format"""
        for uri in v:
            if not uri.startswith(("http://", "https://")):
                raise ValueError(f"Invalid redirect URI: {uri}")
        return v

    @field_validator("grant_types")
    def validate_grant_types(cls, v):
        """Validate grant types"""
        allowed = ["authorization_code", "refresh_token", "client_credentials"]
        for grant in v:
            if grant not in allowed:
                raise ValueError(f"Invalid grant type: {grant}")
        return v


class AuthorizationCode(BaseModel):
    """Authorization Code Model"""

    code: str = Field(..., description="Authorization code (token_urlsafe)")
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: str = Field(..., description="PKCE code challenge")
    code_challenge_method: str = Field(default="S256")
    expires_at: datetime
    used: bool = Field(default=False)
    user_id: str | None = None  # If user-based auth

    # API Key-based authorization
    api_key_id: str | None = None  # API Key ID for scope/project inheritance
    api_key_project_id: str | None = None  # Project ID from API Key
    api_key_scope: str | None = None  # Scope from API Key

    def is_expired(self) -> bool:
        """Check if code is expired"""
        now = datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return now > expires

    @field_validator("code_challenge_method")
    def validate_challenge_method(cls, v):
        """OAuth 2.1: Only S256 is allowed"""
        if v != "S256":
            raise ValueError("Only S256 code_challenge_method is supported (OAuth 2.1)")
        return v


class AccessToken(BaseModel):
    """Access Token Model"""

    token: str = Field(..., description="JWT access token")
    client_id: str
    scope: str
    expires_at: datetime
    user_id: str | None = None
    project_id: str = Field(default="*", description="Project ID for scoping")
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self) -> bool:
        """Check if token is expired"""
        now = datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return now > expires


class RefreshToken(BaseModel):
    """Refresh Token Model"""

    token: str = Field(..., description="Refresh token (secure random)")
    client_id: str
    access_token: str | None = None
    expires_at: datetime
    revoked: bool = Field(default=False)
    rotation_count: int = Field(default=0, description="Number of times rotated")
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self) -> bool:
        """Check if token is expired"""
        now = datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return now > expires


class TokenRequest(BaseModel):
    """Token Request Model"""

    grant_type: str = Field(
        ..., description="authorization_code | refresh_token | client_credentials"
    )

    # For authorization_code
    code: str | None = None
    redirect_uri: str | None = None
    code_verifier: str | None = None

    # For refresh_token
    refresh_token: str | None = None

    # Common
    client_id: str
    client_secret: str | None = None
    scope: str | None = None


class TokenResponse(BaseModel):
    """Token Response Model"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    scope: str
