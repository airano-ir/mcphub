"""Single-source, side-effect-free authorization decisions for tool calls."""

from typing import Any
from uuid import uuid4

from core.tool_access import UNIVERSAL_SCOPE_TIERS
from core.tool_policy import (
    AuthorizationDecision,
    EndpointContext,
    Principal,
    RiskLevel,
    SiteContext,
    ToolCategory,
)
from core.tool_registry import ToolDefinition

_SYSTEM_TOOL_SCOPES = {
    # Health and discovery tools.
    "list_projects": "read",
    "get_project_info": "read",
    "check_all_projects_health": "read",
    "get_project_health": "read",
    "get_system_metrics": "read",
    "get_system_uptime": "read",
    "get_project_metrics": "read",
    "get_endpoints": "read",
    "get_system_info": "read",
    # Administrative and mutation-oriented system tools.
    "export_health_metrics": "admin",
    "get_rate_limit_stats": "admin",
    "reset_rate_limit": "admin",
    "set_rate_limit_config": "admin",
    "get_audit_log": "admin",
    "manage_api_keys_create": "admin",
    "manage_api_keys_list": "admin",
    "manage_api_keys_get_info": "admin",
    "manage_api_keys_revoke": "admin",
    "manage_api_keys_delete": "admin",
    "manage_api_keys_rotate": "admin",
    "oauth_register_client": "admin",
    "oauth_list_clients": "admin",
    "oauth_revoke_client": "admin",
    "oauth_get_client_info": "admin",
}


def is_system_tool_name(tool_name: str) -> bool:
    """Return whether a normalized or namespaced name is an exact system tool."""
    from core.project_identifiers import normalize_tool_name

    try:
        return normalize_tool_name(tool_name) in _SYSTEM_TOOL_SCOPES
    except ValueError:
        return False


def resolve_required_scope(tool_name: str) -> str:
    """Resolve required scope from canonical tool metadata only.

    Plugin tools must be registered with explicit ``required_scope`` metadata;
    system tools use the explicit map above because they are not generated from
    plugin definitions. Unknown or malformed names fail closed.
    """
    from core.project_identifiers import normalize_tool_name
    from core.tool_registry import get_tool_registry

    clean_name = normalize_tool_name(tool_name)
    tool_definition = get_tool_registry().get_by_name(clean_name)
    if tool_definition is not None:
        return tool_definition.required_scope
    if clean_name in _SYSTEM_TOOL_SCOPES:
        return _SYSTEM_TOOL_SCOPES[clean_name]
    raise ValueError("tool authorization metadata is unavailable")


def _decision(
    *,
    allow: bool,
    reason_code: str,
    reason: str,
    tool: ToolDefinition,
    principal: Principal,
    endpoint: EndpointContext,
    site: SiteContext,
    correlation_id: str,
    details_safe: dict[str, Any] | None = None,
) -> AuthorizationDecision:
    # Registries created through ToolDefinition always carry these fields, but
    # adapters may receive legacy/custom registry objects.  Never let an
    # arbitrary metadata object (or a mock) cross the typed policy boundary.
    risk = getattr(tool, "risk", None)
    if risk not in {level.value for level in RiskLevel}:
        risk = RiskLevel.HIGH.value

    category = getattr(tool, "category", None)
    if not isinstance(category, str) or not category:
        category = ToolCategory.SYSTEM_ADMIN.value

    return AuthorizationDecision(
        allow=allow,
        reason_code=reason_code,
        reason=reason,
        required_scope=tool.required_scope,
        plugin_type=tool.plugin_type,
        site_id=site.site_id,
        correlation_id=correlation_id,
        risk=risk,
        category=category,
        principal=principal,
        endpoint=endpoint,
        site=site,
        details_safe=details_safe or {},
    )


async def authorize_tool_call(
    *,
    tool_definition: ToolDefinition,
    principal: Principal,
    endpoint: EndpointContext,
    site: SiteContext,
    arguments: dict[str, Any],
    correlation_id: str | None = None,
) -> AuthorizationDecision:
    """Evaluate policy boundaries without instantiating or executing a plugin."""
    del arguments  # Reserved for mutation policy in the next phase.
    correlation_id = correlation_id or uuid4().hex

    checks = (
        (
            endpoint.plugin_types and site.plugin_type not in endpoint.plugin_types,
            "ENDPOINT_PLUGIN_MISMATCH",
            "The endpoint does not allow this plugin type.",
        ),
        (
            tool_definition.plugin_type != site.plugin_type,
            "PLUGIN_MISMATCH",
            "Tool metadata and site plugin type do not match.",
        ),
        (
            bool(endpoint.tool_whitelist) and tool_definition.name not in endpoint.tool_whitelist,
            "TOOL_NOT_ALLOWED",
            "Tool is not present in the endpoint allowlist.",
        ),
        (
            tool_definition.name in endpoint.tool_blacklist,
            "TOOL_NOT_ALLOWED",
            "Tool is denied by the endpoint policy.",
        ),
        (
            not principal.is_global
            and bool(principal.site_ids)
            and site.site_id not in principal.site_ids,
            "SITE_BOUNDARY_VIOLATION",
            "Principal is not authorized for this site.",
        ),
    )
    for failed, code, reason in checks:
        if failed:
            return _decision(
                allow=False,
                reason_code=code,
                reason=reason,
                tool=tool_definition,
                principal=principal,
                endpoint=endpoint,
                site=site,
                correlation_id=correlation_id,
            )

    granted: set[str] = set()
    for scope in principal.granted_scopes:
        granted |= UNIVERSAL_SCOPE_TIERS.get(scope.strip(), set())
    if tool_definition.required_scope not in granted:
        return _decision(
            allow=False,
            reason_code="INSUFFICIENT_SCOPE",
            reason="Principal scope does not grant the tool's required scope.",
            tool=tool_definition,
            principal=principal,
            endpoint=endpoint,
            site=site,
            correlation_id=correlation_id,
        )

    if (
        site.tool_scope != "custom"
        and tool_definition.required_scope not in UNIVERSAL_SCOPE_TIERS.get(site.tool_scope, set())
    ):
        return _decision(
            allow=False,
            reason_code="SITE_SCOPE_DENIED",
            reason="Site scope does not grant the tool's required scope.",
            tool=tool_definition,
            principal=principal,
            endpoint=endpoint,
            site=site,
            correlation_id=correlation_id,
        )
    if not site.tool_enabled:
        return _decision(
            allow=False,
            reason_code="TOOL_DISABLED",
            reason="Tool is disabled for this site.",
            tool=tool_definition,
            principal=principal,
            endpoint=endpoint,
            site=site,
            correlation_id=correlation_id,
        )
    if not site.capability_available:
        return _decision(
            allow=False,
            reason_code="CAPABILITY_UNAVAILABLE",
            reason="Required site capability is unavailable.",
            tool=tool_definition,
            principal=principal,
            endpoint=endpoint,
            site=site,
            correlation_id=correlation_id,
        )

    return _decision(
        allow=True,
        reason_code="ALLOW",
        reason="Tool call authorized.",
        tool=tool_definition,
        principal=principal,
        endpoint=endpoint,
        site=site,
        correlation_id=correlation_id,
    )
