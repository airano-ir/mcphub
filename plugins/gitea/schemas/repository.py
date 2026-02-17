"""
Repository Pydantic Schemas

Validation schemas for Gitea repository operations.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import GiteaPermissions, GiteaUser

class Repository(BaseModel):
    """Gitea repository model"""

    model_config = ConfigDict(extra="allow")

    id: int
    owner: GiteaUser
    name: str
    full_name: str
    description: str | None = None
    empty: bool = False
    private: bool = False
    fork: bool = False
    template: bool = False
    parent: Optional["Repository"] = None
    mirror: bool = False
    size: int = 0
    language: str | None = None
    languages_url: str | None = None
    html_url: str
    ssh_url: str
    clone_url: str
    original_url: str | None = None
    website: str | None = None
    stars_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    open_issues_count: int = 0
    open_pr_counter: int = 0
    release_counter: int = 0
    default_branch: str = "main"
    archived: bool = False
    created_at: datetime
    updated_at: datetime
    permissions: GiteaPermissions | None = None
    has_issues: bool = True
    internal_tracker: dict | None = None
    has_wiki: bool = False
    has_pull_requests: bool = True
    has_projects: bool = False
    ignore_whitespace_conflicts: bool = False
    allow_merge_commits: bool = True
    allow_rebase: bool = True
    allow_rebase_explicit: bool = True
    allow_squash_merge: bool = True
    default_merge_style: str = "merge"
    avatar_url: str | None = None

class Branch(BaseModel):
    """Git branch model"""

    model_config = ConfigDict(extra="allow")

    name: str
    commit: dict
    protected: bool = False
    required_approvals: int | None = None
    enable_status_check: bool = False
    status_check_contexts: list[str] | None = None
    user_can_push: bool = False
    user_can_merge: bool = False

class Tag(BaseModel):
    """Git tag model"""

    model_config = ConfigDict(extra="allow")

    name: str
    message: str | None = None
    id: str
    commit: dict
    zipball_url: str | None = None
    tarball_url: str | None = None

class FileContent(BaseModel):
    """File content model"""

    model_config = ConfigDict(extra="allow")

    name: str
    path: str
    sha: str
    size: int
    url: str
    html_url: str
    git_url: str
    download_url: str | None = None
    type: str  # "file" or "dir"
    content: str | None = None  # Base64 encoded
    encoding: str | None = None
    target: str | None = None  # For symlinks
    submodule_git_url: str | None = None

class CreateRepositoryRequest(BaseModel):
    """Request to create a repository"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100, description="Repository name")
    description: str | None = Field(None, max_length=500, description="Repository description")
    private: bool = Field(default=False, description="Make repository private")
    auto_init: bool = Field(default=False, description="Initialize with README")
    gitignores: str | None = Field(None, description="Gitignore template")
    license: str | None = Field(None, description="License template")
    readme: str | None = Field(None, description="Readme template")
    default_branch: str | None = Field(None, description="Default branch name")
    trust_model: str | None = Field(
        None, description="Trust model (default, collaborator, committer, collaboratorcommitter)"
    )

    @classmethod
    @field_validator("name")
    def validate_name(cls, v):
        """Validate repository name"""
        if not v.replace("-", "").replace("_", "").replace(".", "").isalnum():
            raise ValueError(
                "Repository name can only contain alphanumeric characters, hyphens, underscores, and dots"
            )
        return v

class UpdateRepositoryRequest(BaseModel):
    """Request to update a repository"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100, description="New repository name")
    description: str | None = Field(None, max_length=500, description="Repository description")
    website: str | None = Field(None, description="Repository website")
    private: bool | None = Field(None, description="Make repository private")
    archived: bool | None = Field(None, description="Archive repository")
    has_issues: bool | None = Field(None, description="Enable issues")
    has_wiki: bool | None = Field(None, description="Enable wiki")
    default_branch: str | None = Field(None, description="Default branch")
    allow_merge_commits: bool | None = Field(None, description="Allow merge commits")
    allow_rebase: bool | None = Field(None, description="Allow rebase")
    allow_squash_merge: bool | None = Field(None, description="Allow squash merge")

class CreateBranchRequest(BaseModel):
    """Request to create a branch"""

    model_config = ConfigDict(extra="forbid")

    new_branch_name: str = Field(..., min_length=1, description="New branch name")
    old_branch_name: str | None = Field(None, description="Source branch (default: default branch)")
    old_ref_name: str | None = Field(None, description="Source commit SHA or ref")

class CreateTagRequest(BaseModel):
    """Request to create a tag"""

    model_config = ConfigDict(extra="forbid")

    tag_name: str = Field(..., min_length=1, description="Tag name")
    message: str | None = Field(None, description="Tag message")
    target: str | None = Field(None, description="Target commit SHA (default: latest)")

class CreateFileRequest(BaseModel):
    """Request to create a file"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., description="File content (will be Base64 encoded)")
    message: str = Field(..., min_length=1, description="Commit message")
    branch: str | None = Field(None, description="Branch name (default: default branch)")
    author_name: str | None = Field(None, description="Author name")
    author_email: str | None = Field(None, description="Author email")
    committer_name: str | None = Field(None, description="Committer name")
    committer_email: str | None = Field(None, description="Committer email")
    new_branch: str | None = Field(None, description="Create new branch for this commit")

class UpdateFileRequest(BaseModel):
    """Request to update a file"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., description="New file content (will be Base64 encoded)")
    message: str = Field(..., min_length=1, description="Commit message")
    sha: str = Field(..., description="SHA of the file being replaced")
    branch: str | None = Field(None, description="Branch name (default: default branch)")
    author_name: str | None = Field(None, description="Author name")
    author_email: str | None = Field(None, description="Author email")
    committer_name: str | None = Field(None, description="Committer name")
    committer_email: str | None = Field(None, description="Committer email")
    new_branch: str | None = Field(None, description="Create new branch for this commit")
