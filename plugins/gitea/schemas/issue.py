"""
Issue Pydantic Schemas

Validation schemas for Gitea issue operations.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import GiteaUser


class Label(BaseModel):
    """Issue/PR label"""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    color: str
    description: str | None = None
    url: str | None = None


class Milestone(BaseModel):
    """Issue/PR milestone"""

    model_config = ConfigDict(extra="allow")

    id: int
    title: str
    description: str | None = None
    state: str  # "open" or "closed"
    open_issues: int = 0
    closed_issues: int = 0
    created_at: datetime
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    due_on: datetime | None = None


class Issue(BaseModel):
    """Gitea issue model"""

    model_config = ConfigDict(extra="allow")

    id: int
    number: int
    user: GiteaUser
    original_author: str | None = None
    original_author_id: int | None = None
    title: str
    body: str | None = None
    ref: str | None = None
    labels: list[Label] = []
    milestone: Milestone | None = None
    assignee: GiteaUser | None = None
    assignees: list[GiteaUser] = []
    state: str  # "open" or "closed"
    is_locked: bool = False
    comments: int = 0
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    due_date: datetime | None = None
    pull_request: dict | None = None  # Non-null if this is a PR
    repository: dict | None = None
    html_url: str
    url: str


class Comment(BaseModel):
    """Issue/PR comment"""

    model_config = ConfigDict(extra="allow")

    id: int
    html_url: str
    pull_request_url: str | None = None
    issue_url: str | None = None
    user: GiteaUser
    original_author: str | None = None
    original_author_id: int | None = None
    body: str
    created_at: datetime
    updated_at: datetime


class CreateIssueRequest(BaseModel):
    """Request to create an issue"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=255, description="Issue title")
    body: str | None = Field(None, description="Issue body/description")
    assignee: str | None = Field(None, description="Username of assignee")
    assignees: list[str] | None = Field(None, description="List of assignee usernames")
    closed: bool | None = Field(False, description="Create as closed")
    due_date: datetime | None = Field(None, description="Due date")
    labels: list[int] | None = Field(None, description="List of label IDs")
    milestone: int | None = Field(None, description="Milestone ID")
    ref: str | None = Field(None, description="Issue ref")


class UpdateIssueRequest(BaseModel):
    """Request to update an issue"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=255, description="Issue title")
    body: str | None = Field(None, description="Issue body/description")
    assignee: str | None = Field(None, description="Username of assignee")
    assignees: list[str] | None = Field(None, description="List of assignee usernames")
    state: str | None = Field(None, description="State (open/closed)")
    due_date: datetime | None = Field(None, description="Due date")
    labels: list[int] | None = Field(None, description="List of label IDs")
    milestone: int | None = Field(None, description="Milestone ID")
    ref: str | None = Field(None, description="Issue ref")
    unset_due_date: bool | None = Field(None, description="Unset due date")

    @classmethod
    @field_validator("state")
    def validate_state(cls, v):
        if v and v not in ["open", "closed"]:
            raise ValueError("State must be 'open' or 'closed'")
        return v


class CreateCommentRequest(BaseModel):
    """Request to create a comment"""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, description="Comment body")


class CreateLabelRequest(BaseModel):
    """Request to create a label"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=50, description="Label name")
    color: str = Field(..., pattern=r"^[0-9A-Fa-f]{6}$", description="Label color (hex without #)")
    description: str | None = Field(None, max_length=200, description="Label description")


class CreateMilestoneRequest(BaseModel):
    """Request to create a milestone"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=255, description="Milestone title")
    description: str | None = Field(None, description="Milestone description")
    due_on: datetime | None = Field(None, description="Due date")
    state: str | None = Field("open", description="State (open/closed)")

    @classmethod
    @field_validator("state")
    def validate_state(cls, v):
        if v not in ["open", "closed"]:
            raise ValueError("State must be 'open' or 'closed'")
        return v


class IssueListFilters(BaseModel):
    """Filters for listing issues"""

    model_config = ConfigDict(extra="forbid")

    state: str | None = Field("open", description="Filter by state (open/closed/all)")
    labels: str | None = Field(None, description="Comma-separated label IDs")
    q: str | None = Field(None, description="Search query")
    type: str | None = Field(None, description="Filter by type (issues/pulls)")
    milestones: str | None = Field(None, description="Comma-separated milestone names")
    since: datetime | None = Field(None, description="Only show items updated after this time")
    before: datetime | None = Field(None, description="Only show items updated before this time")
    created_by: str | None = Field(None, description="Filter by creator username")
    assigned_by: str | None = Field(None, description="Filter by assignee username")
    mentioned_by: str | None = Field(None, description="Filter by mentioned username")

    @classmethod
    @field_validator("state")
    def validate_state(cls, v):
        if v and v not in ["open", "closed", "all"]:
            raise ValueError("State must be 'open', 'closed', or 'all'")
        return v

    @classmethod
    @field_validator("type")
    def validate_type(cls, v):
        if v and v not in ["issues", "pulls"]:
            raise ValueError("Type must be 'issues' or 'pulls'")
        return v
