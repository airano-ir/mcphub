"""
Media Pydantic Schemas

Validation schemas for WordPress media library operations.
"""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class MediaBase(BaseModel):
    """Base media schema"""

    model_config = ConfigDict(extra="allow")

    title: str | None = Field(None, description="Media title")
    alt_text: str | None = Field(None, description="Alternative text")
    caption: str | None = Field(None, description="Media caption")
    description: str | None = Field(None, description="Media description")


class MediaUpload(MediaBase):
    """Schema for uploading media from URL"""

    url: HttpUrl = Field(..., description="Source URL of the media file")
    filename: str | None = Field(None, description="Desired filename")

    @classmethod
    @field_validator("filename")
    def validate_filename(cls, v):
        if v is not None:
            # Basic filename validation
            if "/" in v or "\\" in v:
                raise ValueError("Filename cannot contain path separators")
            if len(v) > 255:
                raise ValueError("Filename too long (max 255 characters)")
        return v


class MediaUpdate(MediaBase):
    """Schema for updating media metadata"""

    # All fields optional for updates
    pass


class MediaResponse(BaseModel):
    """Schema for media response data"""

    model_config = ConfigDict(extra="allow")

    id: int
    title: str
    alt_text: str
    caption: str
    description: str
    mime_type: str
    media_type: str
    source_url: str
    link: str
    date: str
