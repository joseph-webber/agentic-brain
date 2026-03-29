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

"""E-commerce and retail business models."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum, StrEnum
from typing import Optional

from .base import BusinessEntity


class OrderStatus(StrEnum):
    """Enumeration of possible order statuses."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class ProductCategory(StrEnum):
    """Common product categories."""

    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"
    HOME = "home"
    SPORTS = "sports"
    TOYS = "toys"
    FOOD = "food"
    OTHER = "other"


@dataclass
class Category(BusinessEntity):
    """
    Product category entity.

    Represents a hierarchical category that can contain products or subcategories.
    """

    name: str = ""
    description: str = ""
    parent_id: Optional[str] = None
    display_order: int = 0
    is_active: bool = True

    def __post_init__(self) -> None:
        """Validate category on initialization."""
        if not self.name:
            raise ValueError("Category name is required")


@dataclass
class Product(BusinessEntity):
    """
    Product entity for retail inventory.

    Represents a physical or digital product available for sale with pricing
    and inventory management.
    """

    sku: str = ""
    name: str = ""
    description: str = ""
    category_id: str = ""
    price: float = 0.0
    stock_quantity: int = 0
    reorder_level: int = 10
    is_active: bool = True
    attributes: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate product on initialization."""
        if not self.sku:
            raise ValueError("Product SKU is required")
        if not self.name:
            raise ValueError("Product name is required")
        if self.price < 0:
            raise ValueError("Product price cannot be negative")
        if self.stock_quantity < 0:
            raise ValueError("Stock quantity cannot be negative")

    def is_in_stock(self) -> bool:
        """Check if product has available stock."""
        return self.stock_quantity > 0

    def needs_reorder(self) -> bool:
        """Check if product stock is below reorder level."""
        return self.stock_quantity <= self.reorder_level

    def reduce_stock(self, quantity: int) -> bool:
        """
        Reduce stock by specified quantity.

        Args:
            quantity: Amount to reduce stock by.

        Returns:
            True if reduction was successful, False if insufficient stock.
        """
        if quantity > self.stock_quantity:
            return False
        self.stock_quantity -= quantity
        self.update_timestamp()
        return True

    def increase_stock(self, quantity: int) -> None:
        """
        Increase stock by specified quantity.

        Args:
            quantity: Amount to increase stock by.
        """
        self.stock_quantity += quantity
        self.update_timestamp()


@dataclass
class OrderItem(BusinessEntity):
    """
    Individual item within an order.

    Represents a specific product quantity and pricing for a single line item
    in an order.
    """

    order_id: str = ""
    product_sku: str = ""
    product_name: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    line_total: float = 0.0

    def __post_init__(self) -> None:
        """Validate order item on initialization."""
        if not self.order_id:
            raise ValueError("Order ID is required")
        if not self.product_sku:
            raise ValueError("Product SKU is required")
        if self.quantity < 1:
            raise ValueError("Quantity must be at least 1")
        if self.unit_price < 0:
            raise ValueError("Unit price cannot be negative")
        # Calculate line total if not provided
        if self.line_total == 0 and self.quantity > 0 and self.unit_price > 0:
            self.line_total = self.quantity * self.unit_price

    def recalculate_total(self) -> None:
        """Recalculate line total from quantity and unit price."""
        self.line_total = self.quantity * self.unit_price


@dataclass
class Customer(BusinessEntity):
    """
    Customer entity for order management.

    Represents an individual or organization that places orders.
    """

    name: str = ""
    email: str = ""
    phone: Optional[str] = None
    address: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    is_active: bool = True
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate customer on initialization."""
        if not self.name:
            raise ValueError("Customer name is required")
        if not self.email:
            raise ValueError("Customer email is required")

    def get_full_address(self) -> str:
        """
        Get formatted full address.

        Returns:
            Formatted address string.
        """
        parts = [self.address, self.city, self.state, self.postal_code, self.country]
        return ", ".join(p for p in parts if p)


@dataclass
class Order(BusinessEntity):
    """
    Order entity for transaction management.

    Represents a customer order containing multiple items with pricing,
    status tracking, and fulfillment information.
    """

    customer_id: str = ""
    customer_email: str = ""
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    subtotal: float = 0.0
    tax: float = 0.0
    shipping: float = 0.0
    total: float = 0.0
    shipping_address: str = ""
    notes: str = ""
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate order on initialization."""
        if not self.customer_id:
            raise ValueError("Customer ID is required")
        if not self.customer_email:
            raise ValueError("Customer email is required")
        if not self.items:
            raise ValueError("Order must contain at least one item")
        # Validate all items belong to this order
        for item in self.items:
            if item.order_id != self.id:
                item.order_id = self.id

    def recalculate_totals(self) -> None:
        """
        Recalculate order totals from line items.

        Recalculates subtotal, and if tax/shipping are not set,
        updates the total.
        """
        self.subtotal = sum(item.line_total for item in self.items)
        self.total = self.subtotal + self.tax + self.shipping

    def add_item(self, item: OrderItem) -> None:
        """
        Add item to order.

        Args:
            item: OrderItem to add.
        """
        item.order_id = self.id
        self.items.append(item)
        self.recalculate_totals()
        self.update_timestamp()

    def remove_item(self, product_sku: str) -> bool:
        """
        Remove item from order by product SKU.

        Args:
            product_sku: SKU of product to remove.

        Returns:
            True if item was removed, False if not found.
        """
        original_count = len(self.items)
        self.items = [item for item in self.items if item.product_sku != product_sku]
        if len(self.items) < original_count:
            self.recalculate_totals()
            self.update_timestamp()
            return True
        return False

    def get_item_count(self) -> int:
        """Get total number of items in order."""
        return sum(item.quantity for item in self.items)

    def can_transition_to(self, new_status: OrderStatus) -> bool:
        """
        Check if order can transition to a new status.

        Args:
            new_status: Target status to transition to.

        Returns:
            True if transition is allowed.
        """
        # Define valid state transitions
        valid_transitions = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
            OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
            OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
            OrderStatus.DELIVERED: [OrderStatus.REFUNDED],
            OrderStatus.CANCELLED: [],
            OrderStatus.REFUNDED: [],
        }
        return new_status in valid_transitions.get(self.status, [])

    def transition_to(self, new_status: OrderStatus) -> bool:
        """
        Attempt to transition order to new status.

        Args:
            new_status: Target status to transition to.

        Returns:
            True if transition was successful, False if not allowed.
        """
        if not self.can_transition_to(new_status):
            return False

        self.status = new_status
        self.update_timestamp()

        # Update timestamp fields based on status
        if new_status == OrderStatus.SHIPPED:
            self.shipped_at = datetime.now(UTC)
        elif new_status == OrderStatus.DELIVERED:
            self.delivered_at = datetime.now(UTC)

        return True

    def is_completed(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in (
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
            OrderStatus.REFUNDED,
        )
