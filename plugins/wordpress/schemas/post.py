"""
Post Pydantic Schemas

Validation schemas for WordPress posts, pages, and custom post types.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

class PostBase(BaseModel):
    """Base post schema with common fields"""

    title: str | None = Field(None, description="Post title")
    content: str | None = Field(None, description="Post content (HTML)")
    excerpt: str | None = Field(None, description="Post excerpt")
    status: str | None = Field("draft", description="Post status")
    slug: str | None = Field(None, description="Post slug (URL-friendly)")
    author: int | None = Field(None, description="Author user ID")
    featured_media: int | None = Field(None, description="Featured image media ID")
    comment_status: str | None = Field(None, description="Comment status (open/closed)")
    ping_status: str | None = Field(None, description="Ping status (open/closed)")
    format: str | None = Field(None, description="Post format")
    meta: dict | None = Field(None, description="Post meta fields")
    sticky: bool | None = Field(None, description="Sticky post flag")
    categories: list[int] | None = Field(None, description="Category IDs")
    tags: list[int] | None = Field(None, description="Tag IDs")

    model_config = ConfigDict(extra="allow")  # Allow additional fields for custom post types

    @classmethod
    @field_validator("status")
    def validate_status(cls, v):
        if v is not None:
            allowed = ["publish", "draft", "pending", "private", "future"]
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v

    @classmethod
    @field_validator("comment_status", "ping_status")
    def validate_comment_ping_status(cls, v):
        if v is not None:
            allowed = ["open", "closed"]
            if v not in allowed:
                raise ValueError("Status must be 'open' or 'closed'")
        return v

class PostCreate(PostBase):
    """Schema for creating a new post"""

    title: str = Field(..., min_length=1, description="Post title (required)")
    content: str = Field(..., description="Post content (required)")

    model_config = ConfigDict(extra="allow")

class PostUpdate(PostBase):
    """Schema for updating an existing post"""

    # All fields optional for updates
    pass

class PostResponse(BaseModel):
    """Schema for post response data"""

    model_config = ConfigDict(extra="allow")

    id: int
    title: str
    content: str
    excerpt: str
    status: str
    slug: str
    link: str
    date: str
    modified: str
    author: int
    featured_media: int
    categories: list[int]
    tags: list[int]

class PageCreate(PostCreate):
    """Schema for creating a new page"""

    parent: int | None = Field(None, description="Parent page ID")
    menu_order: int | None = Field(None, description="Menu order")
    template: str | None = Field(None, description="Page template")

class PageUpdate(PostUpdate):
    """Schema for updating an existing page"""

    parent: int | None = Field(None, description="Parent page ID")
    menu_order: int | None = Field(None, description="Menu order")
    template: str | None = Field(None, description="Page template")

class CustomPostCreate(PostCreate):
    """Schema for creating custom post types"""

    post_type: str = Field(..., description="Custom post type")

class CustomPostUpdate(PostUpdate):
    """Schema for updating custom post types"""

    pass
