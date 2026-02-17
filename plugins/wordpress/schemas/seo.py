"""
SEO Pydantic Schemas

Validation schemas for SEO plugin data (Yoast, RankMath, etc.).
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

class SEOData(BaseModel):
    """Schema for SEO data (read)"""

    model_config = ConfigDict(extra="allow")

    title: str | None = Field(None, description="SEO title")
    description: str | None = Field(None, description="Meta description")
    keywords: str | None = Field(None, description="Focus keywords")
    canonical: str | None = Field(None, description="Canonical URL")
    og_title: str | None = Field(None, description="Open Graph title")
    og_description: str | None = Field(None, description="Open Graph description")
    og_image: str | None = Field(None, description="Open Graph image URL")
    twitter_title: str | None = Field(None, description="Twitter card title")
    twitter_description: str | None = Field(None, description="Twitter card description")
    twitter_image: str | None = Field(None, description="Twitter card image URL")
    robots: list[str] | None = Field(None, description="Robots meta tags")

class SEOUpdate(BaseModel):
    """Schema for SEO data updates"""

    title: str | None = Field(
        None, max_length=60, description="SEO title (max 60 chars recommended)"
    )
    description: str | None = Field(
        None, max_length=160, description="Meta description (max 160 chars recommended)"
    )
    keywords: str | None = Field(None, description="Focus keywords (comma-separated)")
    canonical: str | None = Field(None, description="Canonical URL")
    og_title: str | None = Field(None, description="Open Graph title")
    og_description: str | None = Field(None, description="Open Graph description")
    og_image: str | None = Field(None, description="Open Graph image URL")
    twitter_title: str | None = Field(None, description="Twitter card title")
    twitter_description: str | None = Field(None, description="Twitter card description")
    twitter_image: str | None = Field(None, description="Twitter card image URL")
    robots_index: bool | None = Field(None, description="Allow search engines to index")
    robots_follow: bool | None = Field(None, description="Allow search engines to follow links")

    model_config = ConfigDict(extra="allow")

    @classmethod
    @field_validator("title")
    def validate_title_length(cls, v):
        if v and len(v) > 70:
            # Warning, not error - allow but discourage
            pass
        return v

    @classmethod
    @field_validator("description")
    def validate_description_length(cls, v):
        if v and len(v) > 200:
            # Warning, not error - allow but discourage
            pass
        return v

class YoastSEO(SEOData):
    """Yoast SEO specific data"""

    model_config = ConfigDict(extra="allow")

    yoast_wpseo_focuskw: str | None = Field(None, description="Yoast focus keyword")
    yoast_wpseo_metadesc: str | None = Field(None, description="Yoast meta description")
    yoast_wpseo_title: str | None = Field(None, description="Yoast SEO title")

class RankMathSEO(SEOData):
    """RankMath SEO specific data"""

    model_config = ConfigDict(extra="allow")

    rank_math_focus_keyword: str | None = Field(None, description="RankMath focus keyword")
    rank_math_description: str | None = Field(None, description="RankMath meta description")
    rank_math_title: str | None = Field(None, description="RankMath SEO title")
