# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pydantic models for WooCommerce resources."""

from __future__ import annotations

from decimal import Decimal
from email.utils import parseaddr
from typing import Annotated

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

Money = Annotated[Decimal, Field(ge=Decimal("0"))]
Identifier = Annotated[int, Field(ge=0)]


class WooBaseModel(BaseModel):
    """Base model with strict validation defaults for commerce resources."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class WooAddress(WooBaseModel):
    """Postal address used by WooCommerce billing and shipping payloads."""

    first_name: str = Field(default="", description="Recipient first name")
    last_name: str = Field(default="", description="Recipient last name")
    company: str | None = Field(default=None, description="Company name")
    address_1: str = Field(default="", description="Primary street address")
    address_2: str | None = Field(default=None, description="Secondary street address")
    city: str = Field(default="", description="City or suburb")
    state: str | None = Field(default=None, description="State or region")
    postcode: str = Field(default="", description="Postcode or ZIP code")
    country: str = Field(
        default="",
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code",
    )
    email: str | None = Field(default=None, description="Associated email address")
    phone: str | None = Field(default=None, description="Contact phone number")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        """Validate email format without requiring optional email-validator extra."""
        if value is None or value == "":
            return None
        _, parsed = parseaddr(value)
        if "@" not in parsed or parsed.startswith("@") or parsed.endswith("@"):
            raise ValueError("Invalid email address")
        return parsed

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        """Normalize country codes to uppercase two-letter values."""
        if value == "":
            return value
        normalized = value.upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("Country must be a 2-letter ISO code")
        return normalized

    @property
    def full_name(self) -> str:
        """Return the address recipient name."""
        return " ".join(
            part for part in [self.first_name, self.last_name] if part
        ).strip()


class WooCategory(WooBaseModel):
    """WooCommerce product category."""

    id: Identifier
    name: str = Field(..., min_length=1, description="Category name")
    slug: str | None = Field(default=None, description="URL-friendly category slug")
    description: str | None = Field(default=None, description="Category description")
    count: int | None = Field(
        default=None, ge=0, description="Number of products in this category"
    )


class WooTag(WooBaseModel):
    """WooCommerce product tag."""

    id: Identifier
    name: str = Field(..., min_length=1, description="Tag name")
    slug: str | None = Field(default=None, description="URL-friendly tag slug")
    description: str | None = Field(default=None, description="Tag description")
    count: int | None = Field(
        default=None, ge=0, description="Number of products using this tag"
    )


class WooCoupon(WooBaseModel):
    """WooCommerce coupon or discount rule."""

    id: Identifier
    code: str = Field(..., min_length=1, description="Coupon code")
    amount: Money = Field(default=Decimal("0"), description="Coupon discount amount")
    discount_type: str | None = Field(
        default=None, description="Type of discount, such as fixed_cart or percent"
    )
    description: str | None = Field(default=None, description="Coupon description")
    individual_use: bool = Field(
        default=False, description="Whether the coupon can be combined"
    )
    usage_limit: int | None = Field(
        default=None, ge=0, description="Maximum number of uses"
    )


class WooProductImage(WooBaseModel):
    """WooCommerce product image metadata."""

    id: Identifier
    src: AnyHttpUrl = Field(..., description="Absolute image URL")
    name: str | None = Field(default=None, description="Image file name")
    alt: str | None = Field(
        default=None, description="Alternative text for accessibility"
    )


class WooProduct(WooBaseModel):
    """WooCommerce product resource."""

    id: Identifier
    name: str = Field(..., min_length=1, description="Product display name")
    price: Money = Field(default=Decimal("0"), description="Current product price")
    description: str = Field(default="", description="Full product description")
    sku: str | None = Field(default=None, description="Stock keeping unit")
    stock: int = Field(default=0, ge=0, description="Available stock quantity")
    categories: list[WooCategory] = Field(
        default_factory=list, description="Assigned product categories"
    )
    images: list[WooProductImage] = Field(
        default_factory=list, description="Product media gallery"
    )
    tags: list[WooTag] = Field(
        default_factory=list, description="Assigned product tags"
    )
    in_stock: bool | None = Field(
        default=None, description="Whether the product is in stock"
    )

    @model_validator(mode="after")
    def validate_stock_state(self) -> WooProduct:
        """Ensure inventory flags are consistent."""
        if self.in_stock is False and self.stock > 0:
            raise ValueError("stock must be 0 when in_stock is false")
        if self.in_stock is None:
            object.__setattr__(self, "in_stock", self.stock > 0)
        return self


class WooCustomer(WooBaseModel):
    """WooCommerce customer resource."""

    id: Identifier
    email: str = Field(..., description="Customer email address")
    name: str = Field(..., min_length=1, description="Customer display name")
    billing_address: WooAddress = Field(
        default_factory=WooAddress, description="Billing address"
    )
    shipping_address: WooAddress = Field(
        default_factory=WooAddress, description="Shipping address"
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Validate email format without optional dependencies."""
        _, parsed = parseaddr(value)
        if "@" not in parsed or parsed.startswith("@") or parsed.endswith("@"):
            raise ValueError("Invalid email address")
        return parsed


class WooOrderItem(WooBaseModel):
    """Line item attached to a WooCommerce order."""

    id: Identifier | None = Field(
        default=None, description="Order line item identifier"
    )
    product_id: Identifier | None = Field(
        default=None, description="Referenced WooCommerce product id"
    )
    name: str = Field(..., min_length=1, description="Line item name")
    sku: str | None = Field(default=None, description="Product SKU")
    quantity: int = Field(..., gt=0, description="Number of units ordered")
    price: Money = Field(default=Decimal("0"), description="Unit price")
    total: Money = Field(default=Decimal("0"), description="Extended line total")

    @model_validator(mode="after")
    def validate_totals(self) -> WooOrderItem:
        """Ensure line total is not less than a single unit price."""
        minimum_total = self.price * self.quantity
        if self.total < minimum_total:
            raise ValueError("total must be at least price multiplied by quantity")
        return self


class WooOrderTotals(WooBaseModel):
    """Aggregated monetary totals for a WooCommerce order."""

    subtotal: Money = Field(
        default=Decimal("0"), description="Order subtotal before discounts"
    )
    discount_total: Money = Field(
        default=Decimal("0"), description="Discount value applied to the order"
    )
    shipping_total: Money = Field(default=Decimal("0"), description="Shipping total")
    tax_total: Money = Field(default=Decimal("0"), description="Tax total")
    total: Money = Field(default=Decimal("0"), description="Grand total")
    currency: str = Field(
        default="USD", min_length=3, max_length=3, description="ISO 4217 currency code"
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize currency codes to uppercase."""
        normalized = value.upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a 3-letter ISO code")
        return normalized

    @model_validator(mode="after")
    def validate_total_floor(self) -> WooOrderTotals:
        """Ensure grand total is not below the non-discount base amount."""
        base_total = (
            self.subtotal - self.discount_total + self.shipping_total + self.tax_total
        )
        if self.total != base_total:
            raise ValueError(
                "total must equal subtotal - discount_total + shipping_total + tax_total"
            )
        return self


class WooOrder(WooBaseModel):
    """WooCommerce order resource."""

    id: Identifier
    status: str = Field(..., min_length=1, description="Order status")
    customer: WooCustomer | None = Field(
        default=None, description="Customer associated with the order"
    )
    items: list[WooOrderItem] = Field(
        default_factory=list, description="Order line items"
    )
    totals: WooOrderTotals = Field(
        default_factory=WooOrderTotals, description="Monetary totals"
    )
    shipping: WooAddress = Field(
        default_factory=WooAddress, description="Shipping address"
    )
    billing: WooAddress = Field(
        default_factory=WooAddress, description="Billing address"
    )
    coupons: list[WooCoupon] = Field(
        default_factory=list, description="Coupons applied to the order"
    )

    @model_validator(mode="after")
    def validate_order_consistency(self) -> WooOrder:
        """Validate order level totals and address consistency."""
        item_total = sum(item.total for item in self.items)
        expected_subtotal = self.totals.subtotal
        if self.items and item_total != expected_subtotal:
            raise ValueError("totals.subtotal must equal the sum of item totals")

        if self.customer is not None:
            if self.billing.email is None:
                object.__setattr__(self.billing, "email", self.customer.email)
            if (
                self.shipping.full_name == ""
                and self.customer.shipping_address.full_name
            ):
                object.__setattr__(self, "shipping", self.customer.shipping_address)
        return self


__all__ = [
    "WooAddress",
    "WooBaseModel",
    "WooCategory",
    "WooCoupon",
    "WooCustomer",
    "WooOrder",
    "WooOrderItem",
    "WooOrderTotals",
    "WooProduct",
    "WooProductImage",
    "WooTag",
]
