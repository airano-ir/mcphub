"""
Gitea Plugin Pydantic Schemas

All validation schemas for Gitea plugin operations.
"""

from .common import (
    ErrorResponse,
    GiteaPermissions,
    GiteaTimestamps,
    GiteaUser,
    PaginationParams,
    Site,
    SuccessResponse,
)
from .issue import (
    Comment,
    CreateCommentRequest,
    CreateIssueRequest,
    CreateLabelRequest,
    CreateMilestoneRequest,
    Issue,
    IssueListFilters,
    Label,
    Milestone,
    UpdateIssueRequest,
)
from .pull_request import (
    CreatePullRequestRequest,
    CreateReviewRequest,
    MergePullRequestRequest,
    PRBranchInfo,
    PRCommit,
    PRFile,
    PRListFilters,
    PRReview,
    PullRequest,
    RequestReviewersRequest,
    UpdatePullRequestRequest,
)
from .repository import (
    Branch,
    CreateBranchRequest,
    CreateFileRequest,
    CreateRepositoryRequest,
    CreateTagRequest,
    FileContent,
    Repository,
    Tag,
    UpdateFileRequest,
    UpdateRepositoryRequest,
)
from .user import (
    Email,
    Organization,
    SearchOrgsRequest,
    SearchUsersRequest,
    Team,
    TeamMember,
    User,
)
from .webhook import (
    CreateWebhookRequest,
    UpdateWebhookRequest,
    Webhook,
    WebhookConfig,
    WebhookTestResult,
)

__all__ = [
    # Common
    "Site",
    "PaginationParams",
    "ErrorResponse",
    "SuccessResponse",
    "GiteaUser",
    "GiteaPermissions",
    "GiteaTimestamps",
    # Repository
    "Repository",
    "Branch",
    "Tag",
    "FileContent",
    "CreateRepositoryRequest",
    "UpdateRepositoryRequest",
    "CreateBranchRequest",
    "CreateTagRequest",
    "CreateFileRequest",
    "UpdateFileRequest",
    # Issue
    "Label",
    "Milestone",
    "Issue",
    "Comment",
    "CreateIssueRequest",
    "UpdateIssueRequest",
    "CreateCommentRequest",
    "CreateLabelRequest",
    "CreateMilestoneRequest",
    "IssueListFilters",
    # Pull Request
    "PRBranchInfo",
    "PullRequest",
    "PRReview",
    "PRCommit",
    "PRFile",
    "CreatePullRequestRequest",
    "UpdatePullRequestRequest",
    "MergePullRequestRequest",
    "CreateReviewRequest",
    "RequestReviewersRequest",
    "PRListFilters",
    # User
    "User",
    "Organization",
    "Team",
    "TeamMember",
    "Email",
    "SearchUsersRequest",
    "SearchOrgsRequest",
    # Webhook
    "Webhook",
    "WebhookConfig",
    "CreateWebhookRequest",
    "UpdateWebhookRequest",
    "WebhookTestResult",
]
