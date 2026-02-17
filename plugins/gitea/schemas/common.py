"""
Common Pydantic Schemas for Gitea Plugin

Shared validation schemas used across Gitea handlers.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Site(BaseModel):
    """Gitea site configuration"""

    model_config = ConfigDict(extra="forbid")

    site_id: str = Field(..., description="Site identifier (e.g., 'site1')")
    url: str = Field(..., description="Gitea instance URL")
    token: str | None = Field(None, description="Personal access token")
    alias: str | None = Field(None, description="Site alias")
    oauth_enabled: bool = Field(default=False, description="Whether OAuth is enabled")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="Page number (starts at 1)")
    limit: int = Field(default=30, ge=1, le=100, description="Number of items per page (1-100)")


class ErrorResponse(BaseModel):
    """Standard error response"""

    error: bool = Field(default=True)
    message: str = Field(..., description="Error message")
    code: str | None = Field(None, description="Error code")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class SuccessResponse(BaseModel):
    """Standard success response"""

    success: bool = Field(default=True)
    message: str = Field(..., description="Success message")
    data: dict[str, Any] | None = Field(None, description="Response data")


class GiteaUser(BaseModel):
    """Gitea user information"""

    model_config = ConfigDict(extra="allow")

    id: int
    login: str
    full_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    is_admin: bool = False


class GiteaPermissions(BaseModel):
    """Repository permissions"""

    model_config = ConfigDict(extra="allow")

    admin: bool = False
    push: bool = False
    pull: bool = False


class GiteaTimestamps(BaseModel):
    """Common timestamp fields"""

    model_config = ConfigDict(extra="allow")

    created_at: datetime | None = None
    updated_at: datetime | None = None
