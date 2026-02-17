"""
Product Pydantic Schemas

Validation schemas for WooCommerce products and related entities.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    """Base product schema"""

    name: str | None = Field(None, description="Product name")
    type: str | None = Field("simple", description="Product type")
    status: str | None = Field("draft", description="Product status")
    featured: bool | None = Field(False, description="Featured product flag")
    catalog_visibility: str | None = Field("visible", description="Catalog visibility")
    description: str | None = Field(None, description="Product description (HTML)")
    short_description: str | None = Field(None, description="Short description (HTML)")
    sku: str | None = Field(None, description="Stock Keeping Unit")
    regular_price: str | None = Field(None, description="Regular price")
    sale_price: str | None = Field(None, description="Sale price")
    manage_stock: bool | None = Field(False, description="Manage stock flag")
    stock_quantity: int | None = Field(None, description="Stock quantity")
    stock_status: str | None = Field("instock", description="Stock status")
    weight: str | None = Field(None, description="Product weight")
    length: str | None = Field(None, description="Product length")
    width: str | None = Field(None, description="Product width")
    height: str | None = Field(None, description="Product height")
    categories: list[dict[str, Any]] | None = Field(None, description="Product categories")
    tags: list[dict[str, Any]] | None = Field(None, description="Product tags")
    images: list[dict[str, Any]] | None = Field(None, description="Product images")
    attributes: list[dict[str, Any]] | None = Field(None, description="Product attributes")

    model_config = ConfigDict(extra="allow")

    @classmethod
    @field_validator("type")
    def validate_type(cls, v):
        if v is not None:
            allowed = ["simple", "grouped", "external", "variable", "variation"]
            if v not in allowed:
                raise ValueError(f"Type must be one of: {', '.join(allowed)}")
        return v

    @classmethod
    @field_validator("status")
    def validate_status(cls, v):
        if v is not None:
            allowed = ["draft", "pending", "private", "publish"]
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v

    @classmethod
    @field_validator("catalog_visibility")
    def validate_visibility(cls, v):
        if v is not None:
            allowed = ["visible", "catalog", "search", "hidden"]
            if v not in allowed:
                raise ValueError(f"Visibility must be one of: {', '.join(allowed)}")
        return v

    @classmethod
    @field_validator("stock_status")
    def validate_stock_status(cls, v):
        if v is not None:
            allowed = ["instock", "outofstock", "onbackorder"]
            if v not in allowed:
                raise ValueError(f"Stock status must be one of: {', '.join(allowed)}")
        return v


class ProductCreate(ProductBase):
    """Schema for creating a new product"""

    name: str = Field(..., min_length=1, description="Product name (required)")
    type: str = Field("simple", description="Product type")


class ProductUpdate(ProductBase):
    """Schema for updating an existing product"""

    # All fields optional for updates
    pass


class ProductResponse(BaseModel):
    """Schema for product response data"""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    slug: str
    type: str
    status: str
    featured: bool
    regular_price: str
    sale_price: str
    price: str
    stock_status: str
    permalink: str


class ProductCategory(BaseModel):
    """Schema for product category"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Category name")
    slug: str | None = Field(None, description="Category slug")
    parent: int | None = Field(None, description="Parent category ID")
    description: str | None = Field(None, description="Category description")
    display: str | None = Field("default", description="Display type")
    image: dict[str, Any] | None = Field(None, description="Category image")


class ProductVariation(BaseModel):
    """Schema for product variation"""

    model_config = ConfigDict(extra="allow")

    regular_price: str | None = Field(None, description="Regular price")
    sale_price: str | None = Field(None, description="Sale price")
    description: str | None = Field(None, description="Variation description")
    sku: str | None = Field(None, description="Stock Keeping Unit")
    manage_stock: bool | None = Field(False, description="Manage stock flag")
    stock_quantity: int | None = Field(None, description="Stock quantity")
    stock_status: str | None = Field("instock", description="Stock status")
    weight: str | None = Field(None, description="Variation weight")
    attributes: list[dict[str, Any]] | None = Field(None, description="Variation attributes")
    image: dict[str, Any] | None = Field(None, description="Variation image")


class ProductAttribute(BaseModel):
    """Schema for product attribute"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Attribute name")
    slug: str | None = Field(None, description="Attribute slug")
    type: str | None = Field("select", description="Attribute type")
    order_by: str | None = Field("menu_order", description="Sort order")
    has_archives: bool | None = Field(False, description="Enable archives")
