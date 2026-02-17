"""
Order Pydantic Schemas

Validation schemas for WooCommerce orders and related entities.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class OrderLineItem(BaseModel):
    """Schema for order line item"""

    model_config = ConfigDict(extra="allow")

    product_id: int = Field(..., description="Product ID")
    quantity: int = Field(default=1, ge=1, description="Quantity")
    variation_id: int | None = Field(None, description="Variation ID")
    subtotal: str | None = Field(None, description="Line subtotal")
    total: str | None = Field(None, description="Line total")


class ShippingAddress(BaseModel):
    """Schema for shipping address"""

    model_config = ConfigDict(extra="allow")

    first_name: str | None = Field(None, description="First name")
    last_name: str | None = Field(None, description="Last name")
    company: str | None = Field(None, description="Company name")
    address_1: str | None = Field(None, description="Address line 1")
    address_2: str | None = Field(None, description="Address line 2")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    postcode: str | None = Field(None, description="Postal code")
    country: str | None = Field(None, description="Country code (ISO 3166-1 alpha-2)")


class BillingAddress(ShippingAddress):
    """Schema for billing address (extends shipping)"""

    email: EmailStr | None = Field(None, description="Email address")
    phone: str | None = Field(None, description="Phone number")


class OrderBase(BaseModel):
    """Base order schema"""

    status: str | None = Field("pending", description="Order status")
    customer_id: int | None = Field(None, description="Customer user ID")
    billing: BillingAddress | None = Field(None, description="Billing address")
    shipping: ShippingAddress | None = Field(None, description="Shipping address")
    payment_method: str | None = Field(None, description="Payment method ID")
    payment_method_title: str | None = Field(None, description="Payment method title")
    transaction_id: str | None = Field(None, description="Transaction ID")
    customer_note: str | None = Field(None, description="Customer note")
    line_items: list[OrderLineItem] | None = Field(None, description="Order line items")
    shipping_lines: list[dict[str, Any]] | None = Field(None, description="Shipping lines")
    fee_lines: list[dict[str, Any]] | None = Field(None, description="Fee lines")
    coupon_lines: list[dict[str, Any]] | None = Field(None, description="Coupon lines")

    model_config = ConfigDict(extra="allow")

    @classmethod
    @field_validator("status")
    def validate_status(cls, v):
        if v is not None:
            allowed = [
                "pending",
                "processing",
                "on-hold",
                "completed",
                "cancelled",
                "refunded",
                "failed",
                "trash",
            ]
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v


class OrderCreate(OrderBase):
    """Schema for creating a new order"""

    line_items: list[OrderLineItem] = Field(
        ..., min_length=1, description="Order line items (required)"
    )

    model_config = ConfigDict(extra="allow")


class OrderUpdate(OrderBase):
    """Schema for updating an existing order"""

    # All fields optional for updates
    pass


class OrderStatusUpdate(BaseModel):
    """Schema for updating order status"""

    status: str = Field(..., description="New order status")

    @classmethod
    @field_validator("status")
    def validate_status(cls, v):
        allowed = [
            "pending",
            "processing",
            "on-hold",
            "completed",
            "cancelled",
            "refunded",
            "failed",
        ]
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v


class OrderResponse(BaseModel):
    """Schema for order response data"""

    model_config = ConfigDict(extra="allow")

    id: int
    number: str
    status: str
    total: str
    date_created: str
    billing: dict[str, Any]
    shipping: dict[str, Any]
    line_items: list[dict[str, Any]]


class CustomerBase(BaseModel):
    """Base customer schema"""

    model_config = ConfigDict(extra="allow")

    email: EmailStr | None = Field(None, description="Customer email")
    first_name: str | None = Field(None, description="First name")
    last_name: str | None = Field(None, description="Last name")
    username: str | None = Field(None, description="Username")
    billing: BillingAddress | None = Field(None, description="Billing address")
    shipping: ShippingAddress | None = Field(None, description="Shipping address")


class CustomerCreate(CustomerBase):
    """Schema for creating a new customer"""

    email: EmailStr = Field(..., description="Customer email (required)")

    model_config = ConfigDict(extra="allow")


class CustomerUpdate(CustomerBase):
    """Schema for updating an existing customer"""

    # All fields optional for updates
    pass
