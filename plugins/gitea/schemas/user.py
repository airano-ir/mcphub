"""
User & Organization Pydantic Schemas

Validation schemas for Gitea user and organization operations.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class User(BaseModel):
    """Gitea user model"""

    model_config = ConfigDict(extra="allow")

    id: int
    login: str
    full_name: str | None = None
    email: str | None = None
    avatar_url: str
    language: str | None = None
    is_admin: bool = False
    last_login: datetime | None = None
    created: datetime
    restricted: bool = False
    active: bool = True
    prohibit_login: bool = False
    location: str | None = None
    website: str | None = None
    description: str | None = None
    visibility: str | None = None
    followers_count: int = 0
    following_count: int = 0
    starred_repos_count: int = 0
    username: str | None = None  # Alias for login

class Organization(BaseModel):
    """Gitea organization model"""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str  # org username
    full_name: str | None = None
    avatar_url: str
    description: str | None = None
    website: str | None = None
    location: str | None = None
    visibility: str  # "public", "limited", "private"
    repo_admin_change_team_access: bool = False
    username: str | None = None  # Alias for name

class Team(BaseModel):
    """Organization team model"""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    description: str | None = None
    organization: Organization | None = None
    permission: str  # "none", "read", "write", "admin", "owner"
    can_create_org_repo: bool = False
    includes_all_repositories: bool = False
    units: list[str] | None = None
    units_map: dict | None = None

class TeamMember(BaseModel):
    """Team member model"""

    model_config = ConfigDict(extra="allow")

    user: User
    role: str | None = None  # Role in team

class Email(BaseModel):
    """User email model"""

    model_config = ConfigDict(extra="allow")

    email: str
    verified: bool
    primary: bool

class SearchUsersRequest(BaseModel):
    """Request to search users"""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(None, description="Search query")
    uid: int | None = Field(None, description="User ID")

class SearchOrgsRequest(BaseModel):
    """Request to search organizations"""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(None, description="Search query")
