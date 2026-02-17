"""
Common Pydantic Schemas

Shared validation schemas used across WordPress handlers.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""

    per_page: int = Field(default=10, ge=1, le=100, description="Number of items per page (1-100)")
    page: int = Field(default=1, ge=1, description="Page number (starts at 1)")

    model_config = ConfigDict(extra="forbid")


class StatusFilter(BaseModel):
    """Status filter for posts/pages/products"""

    status: str = Field(default="any", description="Filter by status")

    @classmethod
    @field_validator("status")
    def validate_status(cls, v):
        allowed = ["publish", "draft", "pending", "private", "any", "future", "trash"]
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v


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
