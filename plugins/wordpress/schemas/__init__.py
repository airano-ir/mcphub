"""
WordPress Pydantic Schemas

Type-safe validation schemas for WordPress data structures.
Part of Option B clean architecture refactoring.
"""

from plugins.wordpress.schemas.common import (
    ErrorResponse,
    PaginationParams,
    StatusFilter,
    SuccessResponse,
)
from plugins.wordpress.schemas.media import MediaBase, MediaResponse, MediaUpdate, MediaUpload
from plugins.wordpress.schemas.order import (
    OrderBase,
    OrderCreate,
    OrderLineItem,
    OrderResponse,
    OrderUpdate,
)
from plugins.wordpress.schemas.post import PostBase, PostCreate, PostResponse, PostUpdate
from plugins.wordpress.schemas.product import (
    ProductBase,
    ProductCategory,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ProductVariation,
)
from plugins.wordpress.schemas.seo import SEOData, SEOUpdate

# Note: Database, Bulk, and System schemas moved to wordpress_advanced plugin

__all__ = [
    # Common
    "PaginationParams",
    "StatusFilter",
    "ErrorResponse",
    "SuccessResponse",
    # Posts
    "PostBase",
    "PostCreate",
    "PostUpdate",
    "PostResponse",
    # Media
    "MediaBase",
    "MediaUpload",
    "MediaUpdate",
    "MediaResponse",
    # Products
    "ProductBase",
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductCategory",
    "ProductVariation",
    # Orders
    "OrderBase",
    "OrderCreate",
    "OrderUpdate",
    "OrderResponse",
    "OrderLineItem",
    # SEO
    "SEOData",
    "SEOUpdate",
    # Note: Database, Bulk, and System schemas moved to wordpress_advanced plugin
]
