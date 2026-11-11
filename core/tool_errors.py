"""Machine-readable, safe errors shared by MCP execution paths."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    """Stable error codes exposed to clients."""

    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class ToolErrorPayload(BaseModel):
    """Safe JSON contract for a failed tool request."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    code: ErrorCode
    message: str = Field(min_length=1)
    retryable: bool = False
    correlation_id: str = Field(min_length=1)
    details_safe: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible fields without exception internals."""
        return self.model_dump(mode="json")


_RETRYABLE_CODES = {ErrorCode.UPSTREAM_TIMEOUT, ErrorCode.RATE_LIMITED}


class ToolError(Exception):
    """Exception carrying the shared safe error payload."""

    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        correlation_id: str,
        retryable: bool | None = None,
        details_safe: dict[str, Any] | None = None,
    ) -> None:
        self.payload = ToolErrorPayload(
            code=code,
            message=message,
            retryable=code in _RETRYABLE_CODES if retryable is None else retryable,
            correlation_id=correlation_id,
            details_safe=details_safe or {},
        )
        super().__init__(self.payload.message)

    def to_dict(self) -> dict[str, Any]:
        """Return the safe client-facing error object."""
        return self.payload.to_dict()
