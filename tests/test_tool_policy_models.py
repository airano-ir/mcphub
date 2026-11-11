"""Contract tests for the shared authorization policy vocabulary."""

import pytest
from pydantic import ValidationError

from core.tool_policy import (
    AuthorizationDecision,
    EndpointContext,
    Principal,
    RiskLevel,
    SiteContext,
    ToolCategory,
)


def test_policy_models_accept_a_complete_safe_decision() -> None:
    principal = Principal(
        authentication_type="api_key",
        principal_id_safe="client-123",
        key_id_safe="key-456",
        granted_scopes=["read", "write"],
        project_id="project-1",
        site_ids=["site-1"],
    )
    endpoint = EndpointContext(name="/project/site-1/mcp", kind="project")
    site = SiteContext(site_id="site-1", plugin_type="wordpress", alias="blog")

    decision = AuthorizationDecision(
        allow=True,
        reason_code="ALLOWED",
        reason="scope and site policy allow the operation",
        required_scope="read",
        plugin_type="wordpress",
        site_id="site-1",
        correlation_id="corr-123",
        risk=RiskLevel.LOW,
        category=ToolCategory.CONTENT_READ,
        principal=principal,
        endpoint=endpoint,
        site=site,
    )

    assert decision.allow is True
    assert decision.principal.principal_id_safe == "client-123"
    assert decision.model_dump()["category"] == ToolCategory.CONTENT_READ


def test_policy_models_reject_unknown_enum_values() -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(
            allow=False,
            reason_code="DENIED",
            reason="unknown risk",
            required_scope="read",
            plugin_type="wordpress",
            site_id="site-1",
            correlation_id="corr-123",
            risk="critical",
            category="unknown.category",
        )


def test_policy_models_forbid_secrets_and_do_not_serialize_them() -> None:
    with pytest.raises(ValidationError):
        Principal(
            authentication_type="bearer",
            principal_id_safe="client-123",
            granted_scopes=["read"],
            api_key="x",
        )

    principal = Principal(
        authentication_type="bearer",
        principal_id_safe="client-123",
        granted_scopes=["read"],
    )
    serialized = str(principal) + repr(principal) + str(principal.model_dump())
    assert "secret" not in serialized.lower()
    assert "api_key" not in serialized.lower()


def test_context_models_require_nonempty_boundary_identifiers() -> None:
    with pytest.raises(ValidationError):
        EndpointContext(name="", kind="project")

    with pytest.raises(ValidationError):
        SiteContext(site_id="", plugin_type="wordpress")
