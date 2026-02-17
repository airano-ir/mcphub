"""
Pull Request Pydantic Schemas

Validation schemas for Gitea pull request operations.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import GiteaUser
from .issue import Label, Milestone


class PRBranchInfo(BaseModel):
    """Pull request branch information"""

    model_config = ConfigDict(extra="allow")

    label: str
    ref: str
    sha: str
    repo_id: int
    repository: dict | None = None


class PullRequest(BaseModel):
    """Gitea pull request model"""

    model_config = ConfigDict(extra="allow")

    id: int
    number: int
    user: GiteaUser
    title: str
    body: str | None = None
    labels: list[Label] = []
    milestone: Milestone | None = None
    assignee: GiteaUser | None = None
    assignees: list[GiteaUser] = []
    requested_reviewers: list[GiteaUser] = []
    state: str  # "open" or "closed"
    is_locked: bool = False
    comments: int = 0
    html_url: str
    diff_url: str
    patch_url: str
    mergeable: bool = False
    merged: bool = False
    merged_at: datetime | None = None
    merge_commit_sha: str | None = None
    merged_by: GiteaUser | None = None
    base: PRBranchInfo
    head: PRBranchInfo
    merge_base: str | None = None
    due_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    allow_maintainer_edit: bool = False
    url: str


class PRReview(BaseModel):
    """Pull request review"""

    model_config = ConfigDict(extra="allow")

    id: int
    user: GiteaUser
    body: str | None = None
    commit_id: str
    state: str  # "PENDING", "APPROVED", "REQUEST_CHANGES", "COMMENT"
    html_url: str
    pull_request_url: str
    submitted_at: datetime


class PRCommit(BaseModel):
    """Pull request commit"""

    model_config = ConfigDict(extra="allow")

    sha: str
    commit: dict
    url: str
    html_url: str
    comments_url: str
    author: GiteaUser | None = None
    committer: GiteaUser | None = None
    parents: list[dict] = []


class PRFile(BaseModel):
    """Pull request file change"""

    model_config = ConfigDict(extra="allow")

    filename: str
    status: str  # "added", "removed", "modified", "renamed"
    additions: int
    deletions: int
    changes: int
    raw_url: str | None = None
    contents_url: str | None = None
    patch: str | None = None
    previous_filename: str | None = None


class CreatePullRequestRequest(BaseModel):
    """Request to create a pull request"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=255, description="PR title")
    head: str = Field(..., description="Source branch")
    base: str = Field(..., description="Target branch")
    body: str | None = Field(None, description="PR description")
    assignee: str | None = Field(None, description="Username of assignee")
    assignees: list[str] | None = Field(None, description="List of assignee usernames")
    labels: list[int] | None = Field(None, description="List of label IDs")
    milestone: int | None = Field(None, description="Milestone ID")
    due_date: datetime | None = Field(None, description="Due date")


class UpdatePullRequestRequest(BaseModel):
    """Request to update a pull request"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=255, description="PR title")
    body: str | None = Field(None, description="PR description")
    assignee: str | None = Field(None, description="Username of assignee")
    assignees: list[str] | None = Field(None, description="List of assignee usernames")
    labels: list[int] | None = Field(None, description="List of label IDs")
    milestone: int | None = Field(None, description="Milestone ID")
    state: str | None = Field(None, description="State (open/closed)")
    due_date: datetime | None = Field(None, description="Due date")
    unset_due_date: bool | None = Field(None, description="Unset due date")
    allow_maintainer_edit: bool | None = Field(None, description="Allow maintainer edit")

    @classmethod
    @field_validator("state")
    def validate_state(cls, v):
        if v and v not in ["open", "closed"]:
            raise ValueError("State must be 'open' or 'closed'")
        return v


class MergePullRequestRequest(BaseModel):
    """Request to merge a pull request"""

    model_config = ConfigDict(extra="forbid")

    Do: str = Field(
        ..., description="Merge method (merge/rebase/rebase-merge/squash/manually-merged)"
    )
    MergeTitleField: str | None = Field(None, description="Merge commit title")
    MergeMessageField: str | None = Field(None, description="Merge commit message")
    delete_branch_after_merge: bool | None = Field(False, description="Delete branch after merge")
    force_merge: bool | None = Field(False, description="Force merge even if not mergeable")
    head_commit_id: str | None = Field(None, description="Expected HEAD commit SHA")
    merge_when_checks_succeed: bool | None = Field(False, description="Auto-merge when checks pass")

    @classmethod
    @field_validator("Do")
    def validate_merge_method(cls, v):
        allowed = ["merge", "rebase", "rebase-merge", "squash", "manually-merged"]
        if v not in allowed:
            raise ValueError(f"Merge method must be one of: {', '.join(allowed)}")
        return v


class CreateReviewRequest(BaseModel):
    """Request to create a review"""

    model_config = ConfigDict(extra="forbid")

    body: str | None = Field(None, description="Review comment")
    event: str = Field(..., description="Review event (APPROVED/REQUEST_CHANGES/COMMENT)")
    comments: list[dict] | None = Field(None, description="Inline review comments")

    @classmethod
    @field_validator("event")
    def validate_event(cls, v):
        allowed = ["APPROVED", "REQUEST_CHANGES", "COMMENT"]
        if v not in allowed:
            raise ValueError(f"Review event must be one of: {', '.join(allowed)}")
        return v


class RequestReviewersRequest(BaseModel):
    """Request reviewers for a pull request"""

    model_config = ConfigDict(extra="forbid")

    reviewers: list[str] = Field(..., min_items=1, description="List of reviewer usernames")
    team_reviewers: list[str] | None = Field(None, description="List of team slugs")


class PRListFilters(BaseModel):
    """Filters for listing pull requests"""

    model_config = ConfigDict(extra="forbid")

    state: str | None = Field("open", description="Filter by state (open/closed/all)")
    sort: str | None = Field(
        "created", description="Sort by (created/updated/comments/recentupdate)"
    )
    labels: str | None = Field(None, description="Comma-separated label IDs")
    milestone: str | None = Field(None, description="Milestone name")

    @classmethod
    @field_validator("state")
    def validate_state(cls, v):
        if v and v not in ["open", "closed", "all"]:
            raise ValueError("State must be 'open', 'closed', or 'all'")
        return v

    @classmethod
    @field_validator("sort")
    def validate_sort(cls, v):
        allowed = ["created", "updated", "comments", "recentupdate"]
        if v and v not in allowed:
            raise ValueError(f"Sort must be one of: {', '.join(allowed)}")
        return v
