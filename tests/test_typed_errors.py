"""Contract tests for typed execution errors."""

import pytest
from pydantic import ValidationError

from core.tool_errors import ErrorCode, ToolError, ToolErrorPayload


def test_typed_error_payload_has_machine_readable_contract() -> None:
    payload = ToolErrorPayload(
        code=ErrorCode.INSUFFICIENT_SCOPE,
        message="The requested operation is not permitted.",
        retryable=False,
        correlation_id="corr-123",
        details_safe={"required_scope": "write"},
    )

    assert payload.code == ErrorCode.INSUFFICIENT_SCOPE
    assert payload.model_dump()["retryable"] is False
    assert payload.details_safe == {"required_scope": "write"}


def test_unknown_error_code_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolErrorPayload(
            code="NOT_A_REAL_CODE",
            message="bad",
            retryable=False,
            correlation_id="corr-123",
        )


def test_tool_error_exposes_safe_payload_without_traceback_or_secret() -> None:
    error = ToolError(
        code=ErrorCode.EXECUTION_FAILED,
        message="The upstream operation failed.",
        correlation_id="corr-123",
        details_safe={"upstream": "unavailable"},
    )

    assert error.payload.code == ErrorCode.EXECUTION_FAILED
    assert error.to_dict()["correlation_id"] == "corr-123"
    assert "traceback" not in str(error).lower()
    assert "secret" not in str(error).lower()
