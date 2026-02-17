"""
Bulk Operations Schemas

Pydantic models for WordPress bulk operations including:
- Bulk updates for posts/products
- Bulk deletions
- Bulk category/tag assignments
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class BulkUpdatePostsParams(BaseModel):
    """Parameters for bulk updating posts"""

    post_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of post IDs to update (max 100)"
    )
    updates: dict[str, Any] = Field(
        ..., description="Fields to update (status, author_id, categories, tags, etc.)"
    )

    @classmethod
    @field_validator("post_ids")
    def validate_post_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All post IDs must be positive integers")
        return v

    @classmethod
    @field_validator("updates")
    def validate_updates(cls, v):
        """Validate update fields are allowed"""
        allowed_fields = {
            "status",
            "title",
            "content",
            "excerpt",
            "author",
            "categories",
            "tags",
            "featured_media",
            "comment_status",
            "ping_status",
            "sticky",
            "format",
            "meta",
        }

        invalid_fields = set(v.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {', '.join(invalid_fields)}")

        return v


class BulkDeletePostsParams(BaseModel):
    """Parameters for bulk deleting posts"""

    post_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of post IDs to delete (max 100)"
    )
    force: bool = Field(default=False, description="Force permanent deletion (bypass trash)")

    @classmethod
    @field_validator("post_ids")
    def validate_post_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All post IDs must be positive integers")
        return v


class BulkUpdateProductsParams(BaseModel):
    """Parameters for bulk updating WooCommerce products"""

    product_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of product IDs to update (max 100)"
    )
    updates: dict[str, Any] = Field(
        ..., description="Fields to update (price, stock_quantity, status, etc.)"
    )

    @classmethod
    @field_validator("product_ids")
    def validate_product_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All product IDs must be positive integers")
        return v

    @classmethod
    @field_validator("updates")
    def validate_updates(cls, v):
        """Validate update fields are allowed"""
        allowed_fields = {
            "name",
            "status",
            "featured",
            "catalog_visibility",
            "description",
            "short_description",
            "sku",
            "price",
            "regular_price",
            "sale_price",
            "stock_quantity",
            "stock_status",
            "manage_stock",
            "categories",
            "tags",
            "images",
            "attributes",
            "meta_data",
        }

        invalid_fields = set(v.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {', '.join(invalid_fields)}")

        return v


class BulkDeleteProductsParams(BaseModel):
    """Parameters for bulk deleting products"""

    product_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of product IDs to delete (max 100)"
    )
    force: bool = Field(default=False, description="Force permanent deletion")

    @classmethod
    @field_validator("product_ids")
    def validate_product_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All product IDs must be positive integers")
        return v


class BulkAssignCategoriesParams(BaseModel):
    """Parameters for bulk assigning categories"""

    item_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of post/product IDs (max 100)"
    )
    category_ids: list[int] = Field(..., min_length=1, description="List of category IDs to assign")
    replace: bool = Field(
        default=False, description="Replace existing categories (true) or append (false)"
    )
    item_type: str = Field(default="post", description="Type of items: 'post' or 'product'")

    @classmethod
    @field_validator("item_ids", "category_ids")
    def validate_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All IDs must be positive integers")
        return v

    @classmethod
    @field_validator("item_type")
    def validate_item_type(cls, v):
        """Validate item type"""
        if v not in ["post", "product"]:
            raise ValueError("item_type must be 'post' or 'product'")
        return v


class BulkAssignTagsParams(BaseModel):
    """Parameters for bulk assigning tags"""

    item_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of post/product IDs (max 100)"
    )
    tag_ids: list[int] = Field(..., min_length=1, description="List of tag IDs to assign")
    replace: bool = Field(
        default=False, description="Replace existing tags (true) or append (false)"
    )
    item_type: str = Field(default="post", description="Type of items: 'post' or 'product'")

    @classmethod
    @field_validator("item_ids", "tag_ids")
    def validate_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All IDs must be positive integers")
        return v

    @classmethod
    @field_validator("item_type")
    def validate_item_type(cls, v):
        """Validate item type"""
        if v not in ["post", "product"]:
            raise ValueError("item_type must be 'post' or 'product'")
        return v


class BulkUpdateMediaParams(BaseModel):
    """Parameters for bulk updating media items"""

    media_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of media IDs to update (max 100)"
    )
    updates: dict[str, Any] = Field(
        ..., description="Fields to update (alt_text, title, caption, description)"
    )

    @classmethod
    @field_validator("media_ids")
    def validate_media_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All media IDs must be positive integers")
        return v

    @classmethod
    @field_validator("updates")
    def validate_updates(cls, v):
        """Validate update fields are allowed"""
        allowed_fields = {"title", "alt_text", "caption", "description", "meta"}

        invalid_fields = set(v.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {', '.join(invalid_fields)}")

        return v


class BulkDeleteMediaParams(BaseModel):
    """Parameters for bulk deleting media items"""

    media_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of media IDs to delete (max 100)"
    )
    force: bool = Field(
        default=True, description="Force permanent deletion (media can't be trashed)"
    )

    @classmethod
    @field_validator("media_ids")
    def validate_media_ids(cls, v):
        """Ensure all IDs are positive"""
        if any(id <= 0 for id in v):
            raise ValueError("All media IDs must be positive integers")
        return v


class BulkOperationResult(BaseModel):
    """Result of a bulk operation"""

    success_count: int = Field(description="Number of successful operations")
    failed_count: int = Field(description="Number of failed operations")
    total: int = Field(description="Total items processed")
    failed_ids: list[int] = Field(default=[], description="IDs that failed to process")
    errors: list[dict[str, Any]] = Field(default=[], description="Detailed error information")
