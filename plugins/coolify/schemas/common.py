"""
Common Pydantic Schemas for Coolify Plugin

Shared validation schemas used across Coolify handlers.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Site(BaseModel):
    """Coolify site configuration."""

    model_config = ConfigDict(extra="forbid")

    site_id: str = Field(..., description="Site identifier")
    url: str = Field(..., description="Coolify instance URL")
    token: str = Field(..., description="API token for Bearer authentication")
    alias: str | None = Field(None, description="Site alias")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    model_config = ConfigDict(extra="forbid")

    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    take: int = Field(default=10, ge=1, le=100, description="Number of items to take")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: bool = Field(default=True)
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class SuccessResponse(BaseModel):
    """Standard success response."""

    success: bool = Field(default=True)
    message: str = Field(..., description="Success message")
    data: dict[str, Any] | None = Field(None, description="Response data")


class CoolifyTimestamps(BaseModel):
    """Common timestamp fields."""

    model_config = ConfigDict(extra="allow")

    created_at: datetime | None = None
    updated_at: datetime | None = None
