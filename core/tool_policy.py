"""Shared policy vocabulary for capability-aware tool authorization."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolCategory(StrEnum):
    """Stable policy categories used by tool metadata."""

    CONTENT_READ = "content.read"
    CONTENT_WRITE = "content.write"
    COMMERCE_READ = "commerce.read"
    COMMERCE_WRITE = "commerce.write"
    COMMERCE_PII = "commerce.pii"
    PLUGIN_INSTALL = "plugin.install"
    PLUGIN_LIFECYCLE = "plugin.lifecycle"
    PLUGIN_DELETE = "plugin.delete"
    THEME_FILE_WRITE = "theme.file_write"
    DATABASE_READ = "database.read"
    DATABASE_OPTIMIZE = "database.optimize"
    BULK_WRITE = "bulk.write"
    SYSTEM_ADMIN = "system.admin"


class RiskLevel(StrEnum):
    """Operational risk levels for tool calls."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class _PolicyModel(BaseModel):
    """Base model that rejects undeclared fields, including credentials."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Principal(_PolicyModel):
    """Safe identity and authorization boundary for a request principal."""

    authentication_type: str = Field(min_length=1)
    principal_id_safe: str = Field(min_length=1)
    key_id_safe: str | None = Field(default=None, min_length=1)
    granted_scopes: list[str] = Field(default_factory=list)
    project_id: str | None = Field(default=None, min_length=1)
    site_ids: list[str] = Field(default_factory=list)
    is_global: bool = False


class EndpointContext(_PolicyModel):
    """Normalized endpoint boundary used during authorization."""

    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    plugin_types: list[str] = Field(default_factory=list)
    tool_whitelist: list[str] = Field(default_factory=list)
    tool_blacklist: list[str] = Field(default_factory=list)


class SiteContext(_PolicyModel):
    """Normalized site identity and plugin boundary."""

    site_id: str = Field(min_length=1)
    plugin_type: str = Field(min_length=1)
    alias: str | None = Field(default=None, min_length=1)
    tool_scope: str = "admin"
    tool_enabled: bool = True
    capability_available: bool = True


class AuthorizationDecision(_PolicyModel):
    """Complete, auditable result of a policy evaluation."""

    allow: bool
    reason_code: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required_scope: str = Field(min_length=1)
    plugin_type: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    risk: RiskLevel
    category: ToolCategory | str
    principal: Principal
    endpoint: EndpointContext
    site: SiteContext
    details_safe: dict[str, Any] = Field(default_factory=dict)
