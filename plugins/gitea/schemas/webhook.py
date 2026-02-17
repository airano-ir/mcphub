"""
Webhook Pydantic Schemas

Validation schemas for Gitea webhook operations.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

class Webhook(BaseModel):
    """Gitea webhook model"""

    model_config = ConfigDict(extra="allow")

    id: int
    type: str  # "gitea", "gogs", "slack", "discord", etc.
    config: dict[str, Any]
    events: list[str]
    active: bool
    updated_at: datetime
    created_at: datetime

class WebhookConfig(BaseModel):
    """Webhook configuration"""

    model_config = ConfigDict(extra="allow")

    url: str
    content_type: str = "json"  # "json" or "form"
    secret: str | None = None
    http_method: str | None = "POST"
    branch_filter: str | None = None

class CreateWebhookRequest(BaseModel):
    """Request to create a webhook"""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        default="gitea",
        description="Webhook type (gitea/gogs/slack/discord/dingtalk/telegram/msteams/feishu/wechatwork/packagist)",
    )
    config: dict[str, Any] = Field(..., description="Webhook configuration")
    events: list[str] = Field(..., min_items=1, description="List of events to trigger webhook")
    active: bool = Field(default=True, description="Activate webhook immediately")
    branch_filter: str | None = Field(None, description="Branch filter pattern")

    @classmethod
    @field_validator("type")
    def validate_type(cls, v):
        allowed = [
            "gitea",
            "gogs",
            "slack",
            "discord",
            "dingtalk",
            "telegram",
            "msteams",
            "feishu",
            "wechatwork",
            "packagist",
        ]
        if v not in allowed:
            raise ValueError(f"Webhook type must be one of: {', '.join(allowed)}")
        return v

    @classmethod
    @field_validator("events")
    def validate_events(cls, v):
        allowed_events = [
            "create",
            "delete",
            "fork",
            "push",
            "issues",
            "issue_assign",
            "issue_label",
            "issue_milestone",
            "issue_comment",
            "pull_request",
            "pull_request_assign",
            "pull_request_label",
            "pull_request_milestone",
            "pull_request_comment",
            "pull_request_review_approved",
            "pull_request_review_rejected",
            "pull_request_review_comment",
            "pull_request_sync",
            "wiki",
            "repository",
            "release",
        ]
        for event in v:
            if event not in allowed_events:
                raise ValueError(
                    f"Invalid event: {event}. Must be one of: {', '.join(allowed_events)}"
                )
        return v

    @classmethod
    @field_validator("config")
    def validate_config(cls, v):
        """Validate webhook config has required fields"""
        if "url" not in v:
            raise ValueError("Webhook config must contain 'url'")
        if "content_type" not in v:
            v["content_type"] = "json"
        return v

class UpdateWebhookRequest(BaseModel):
    """Request to update a webhook"""

    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] | None = Field(None, description="Webhook configuration")
    events: list[str] | None = Field(None, description="List of events to trigger webhook")
    active: bool | None = Field(None, description="Activate/deactivate webhook")
    branch_filter: str | None = Field(None, description="Branch filter pattern")

    @classmethod
    @field_validator("events")
    def validate_events(cls, v):
        if v is None:
            return v
        allowed_events = [
            "create",
            "delete",
            "fork",
            "push",
            "issues",
            "issue_assign",
            "issue_label",
            "issue_milestone",
            "issue_comment",
            "pull_request",
            "pull_request_assign",
            "pull_request_label",
            "pull_request_milestone",
            "pull_request_comment",
            "pull_request_review_approved",
            "pull_request_review_rejected",
            "pull_request_review_comment",
            "pull_request_sync",
            "wiki",
            "repository",
            "release",
        ]
        for event in v:
            if event not in allowed_events:
                raise ValueError(f"Invalid event: {event}")
        return v

class WebhookTestResult(BaseModel):
    """Webhook test result"""

    model_config = ConfigDict(extra="allow")

    success: bool
    message: str | None = None
    response_code: int | None = None
    response_body: str | None = None
