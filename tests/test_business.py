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

"""Tests for business entities module."""

from datetime import UTC, datetime, timezone

import pytest

from agentic_brain.business import (
    Category,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductCategory,
)


class TestBusinessImports:
    """Test business module imports."""

    def test_business_module_imports(self):
        """Test business module can be imported."""
        from agentic_brain import business

        assert business is not None

    def test_all_exports(self):
        """Test __all__ exports are importable."""
        from agentic_brain.business import __all__

        for name in __all__:
            assert hasattr(__import__("agentic_brain.business", fromlist=[name]), name)


class TestOrderStatus:
    """Test OrderStatus enum."""

    def test_order_status_values(self):
        """Test OrderStatus has expected values."""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.CONFIRMED.value == "confirmed"
        assert OrderStatus.PROCESSING.value == "processing"
        assert OrderStatus.SHIPPED.value == "shipped"
        assert OrderStatus.DELIVERED.value == "delivered"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.REFUNDED.value == "refunded"

    def test_order_status_comparison(self):
        """Test OrderStatus can be compared."""
        assert OrderStatus.PENDING == OrderStatus.PENDING
        assert OrderStatus.PENDING != OrderStatus.CONFIRMED


class TestProductCategory:
    """Test ProductCategory enum."""

    def test_product_category_values(self):
        """Test ProductCategory has expected values."""
        assert ProductCategory.ELECTRONICS.value == "electronics"
        assert ProductCategory.CLOTHING.value == "clothing"
        assert ProductCategory.BOOKS.value == "books"
        assert ProductCategory.HOME.value == "home"
        assert ProductCategory.SPORTS.value == "sports"
        assert ProductCategory.TOYS.value == "toys"
        assert ProductCategory.FOOD.value == "food"
        assert ProductCategory.OTHER.value == "other"


class TestCategory:
    """Test Category entity."""

    def test_category_creation_minimal(self):
        """Test Category creation with required fields."""
        category = Category(name="Electronics")
        assert category.name == "Electronics"
        assert category.description == ""
        assert category.parent_id is None
        assert category.display_order == 0
        assert category.is_active is True
        assert category.id is not None

    def test_category_creation_full(self):
        """Test Category creation with all fields."""
        category = Category(
            name="Laptops",
            description="Laptop computers",
            parent_id="electronics-id",
            display_order=1,
            is_active=True,
        )
        assert category.name == "Laptops"
        assert category.description == "Laptop computers"
        assert category.parent_id == "electronics-id"
        assert category.display_order == 1

    def test_category_requires_name(self):
        """Test Category raises error without name."""
        with pytest.raises(ValueError, match="Category name is required"):
            Category(name="")

    def test_category_timestamps(self):
        """Test Category has timestamps."""
        category = Category(name="Test")
        assert isinstance(category.created_at, datetime)
        assert isinstance(category.updated_at, datetime)
        assert category.created_at.tzinfo is not None


class TestProduct:
    """Test Product entity."""

    def test_product_creation_minimal(self):
        """Test Product creation with required fields."""
        product = Product(sku="PROD-001", name="Widget")
        assert product.sku == "PROD-001"
        assert product.name == "Widget"
        assert product.price == 0.0
        assert product.stock_quantity == 0
        assert product.is_active is True

    def test_product_creation_full(self):
        """Test Product creation with all fields."""
        product = Product(
            sku="LAPTOP-001",
            name="Gaming Laptop",
            description="High-performance laptop",
            category_id="electronics",
            price=1299.99,
            stock_quantity=50,
            reorder_level=10,
            is_active=True,
            attributes={"brand": "TechCorp", "color": "silver"},
            tags=["gaming", "laptop", "performance"],
        )
        assert product.name == "Gaming Laptop"
        assert product.price == 1299.99
        assert product.stock_quantity == 50
        assert product.attributes["brand"] == "TechCorp"
        assert "gaming" in product.tags

    def test_product_requires_sku(self):
        """Test Product raises error without SKU."""
        with pytest.raises(ValueError, match="Product SKU is required"):
            Product(sku="", name="Widget")

    def test_product_requires_name(self):
        """Test Product raises error without name."""
        with pytest.raises(ValueError, match="Product name is required"):
            Product(sku="PROD-001", name="")

    def test_product_price_cannot_be_negative(self):
        """Test Product raises error with negative price."""
        with pytest.raises(ValueError, match="Product price cannot be negative"):
            Product(sku="PROD-001", name="Widget", price=-10.0)

    def test_product_stock_cannot_be_negative(self):
        """Test Product raises error with negative stock."""
        with pytest.raises(ValueError, match="Stock quantity cannot be negative"):
            Product(sku="PROD-001", name="Widget", stock_quantity=-1)

    def test_product_is_in_stock(self):
        """Test in-stock check."""
        in_stock = Product(sku="PROD-001", name="Widget", stock_quantity=5)
        out_of_stock = Product(sku="PROD-002", name="Gadget", stock_quantity=0)

        assert in_stock.is_in_stock() is True
        assert out_of_stock.is_in_stock() is False

    def test_product_needs_reorder(self):
        """Test reorder level check."""
        product = Product(
            sku="PROD-001", name="Widget", stock_quantity=5, reorder_level=10
        )
        assert product.needs_reorder() is True

        product.stock_quantity = 15
        assert product.needs_reorder() is False

    def test_product_reduce_stock_success(self):
        """Test successful stock reduction."""
        product = Product(sku="PROD-001", name="Widget", stock_quantity=10)
        assert product.reduce_stock(3) is True
        assert product.stock_quantity == 7

    def test_product_reduce_stock_insufficient(self):
        """Test stock reduction with insufficient stock."""
        product = Product(sku="PROD-001", name="Widget", stock_quantity=5)
        assert product.reduce_stock(10) is False
        assert product.stock_quantity == 5  # Unchanged

    def test_product_increase_stock(self):
        """Test stock increase."""
        product = Product(sku="PROD-001", name="Widget", stock_quantity=5)
        product.increase_stock(10)
        assert product.stock_quantity == 15


class TestOrderItem:
    """Test OrderItem entity."""

    def test_order_item_creation_minimal(self):
        """Test OrderItem creation with required fields."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        assert item.order_id == "ord-1"
        assert item.product_sku == "PROD-001"
        assert item.quantity == 1
        assert item.unit_price == 0.0

    def test_order_item_creation_full(self):
        """Test OrderItem creation with all fields."""
        item = OrderItem(
            order_id="ord-1",
            product_sku="PROD-001",
            product_name="Widget",
            quantity=5,
            unit_price=19.99,
            line_total=99.95,
        )
        assert item.quantity == 5
        assert item.unit_price == 19.99
        assert item.line_total == 99.95

    def test_order_item_requires_order_id(self):
        """Test OrderItem requires order ID."""
        with pytest.raises(ValueError, match="Order ID is required"):
            OrderItem(order_id="", product_sku="PROD-001")

    def test_order_item_requires_sku(self):
        """Test OrderItem requires product SKU."""
        with pytest.raises(ValueError, match="Product SKU is required"):
            OrderItem(order_id="ord-1", product_sku="")

    def test_order_item_quantity_minimum(self):
        """Test OrderItem quantity must be at least 1."""
        with pytest.raises(ValueError, match="Quantity must be at least 1"):
            OrderItem(order_id="ord-1", product_sku="PROD-001", quantity=0)

    def test_order_item_price_cannot_be_negative(self):
        """Test OrderItem price cannot be negative."""
        with pytest.raises(ValueError, match="Unit price cannot be negative"):
            OrderItem(order_id="ord-1", product_sku="PROD-001", unit_price=-5.0)

    def test_order_item_auto_calculates_line_total(self):
        """Test OrderItem auto-calculates line total."""
        item = OrderItem(
            order_id="ord-1", product_sku="PROD-001", quantity=5, unit_price=10.0
        )
        assert item.line_total == 50.0

    def test_order_item_recalculate_total(self):
        """Test recalculating line total."""
        item = OrderItem(
            order_id="ord-1",
            product_sku="PROD-001",
            quantity=5,
            unit_price=10.0,
            line_total=0,
        )
        item.quantity = 3
        item.unit_price = 15.0
        item.recalculate_total()
        assert item.line_total == 45.0


class TestCustomer:
    """Test Customer entity."""

    def test_customer_creation_minimal(self):
        """Test Customer creation with required fields."""
        customer = Customer(name="John Doe", email="john@example.com")
        assert customer.name == "John Doe"
        assert customer.email == "john@example.com"
        assert customer.is_active is True

    def test_customer_creation_full(self):
        """Test Customer creation with all fields."""
        customer = Customer(
            name="Jane Smith",
            email="jane@example.com",
            phone="555-1234",
            address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
            country="USA",
            is_active=True,
            metadata={"vip": True, "referrer": "friend"},
        )
        assert customer.name == "Jane Smith"
        assert customer.phone == "555-1234"
        assert customer.city == "Springfield"
        assert customer.metadata["vip"] is True

    def test_customer_requires_name(self):
        """Test Customer requires name."""
        with pytest.raises(ValueError, match="Customer name is required"):
            Customer(name="", email="test@example.com")

    def test_customer_requires_email(self):
        """Test Customer requires email."""
        with pytest.raises(ValueError, match="Customer email is required"):
            Customer(name="John Doe", email="")

    def test_customer_get_full_address(self):
        """Test getting formatted full address."""
        customer = Customer(
            name="John Doe",
            email="john@example.com",
            address="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
            country="USA",
        )
        address = customer.get_full_address()
        assert "123 Main St" in address
        assert "Springfield" in address
        assert "IL" in address

    def test_customer_get_full_address_partial(self):
        """Test formatted address with missing fields."""
        customer = Customer(
            name="John Doe", email="john@example.com", city="Springfield"
        )
        address = customer.get_full_address()
        assert "Springfield" in address
        # Should not include empty fields
        assert address.count(", ") <= 0  # Only city, no extra commas


class TestOrder:
    """Test Order entity."""

    def test_order_creation_minimal(self):
        """Test Order creation with minimal fields."""
        item = OrderItem(
            order_id="ord-1", product_sku="PROD-001", quantity=1, unit_price=10.0
        )
        order = Order(
            customer_id="cust-1", customer_email="test@example.com", items=[item]
        )
        assert order.customer_id == "cust-1"
        assert order.status == OrderStatus.PENDING
        assert len(order.items) == 1

    def test_order_creation_full(self):
        """Test Order creation with all fields."""
        item = OrderItem(
            order_id="ord-1",
            product_sku="PROD-001",
            product_name="Widget",
            quantity=2,
            unit_price=25.0,
            line_total=50.0,
        )
        order = Order(
            customer_id="cust-1",
            customer_email="customer@example.com",
            items=[item],
            status=OrderStatus.CONFIRMED,
            subtotal=50.0,
            tax=4.0,
            shipping=5.0,
            total=59.0,
            shipping_address="123 Main St",
            notes="Rush delivery",
        )
        assert order.total == 59.0
        assert order.shipping_address == "123 Main St"
        assert order.status == OrderStatus.CONFIRMED

    def test_order_requires_customer_id(self):
        """Test Order requires customer ID."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        with pytest.raises(ValueError, match="Customer ID is required"):
            Order(customer_id="", customer_email="test@example.com", items=[item])

    def test_order_requires_customer_email(self):
        """Test Order requires customer email."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        with pytest.raises(ValueError, match="Customer email is required"):
            Order(customer_id="cust-1", customer_email="", items=[item])

    def test_order_requires_items(self):
        """Test Order requires at least one item."""
        with pytest.raises(ValueError, match="Order must contain at least one item"):
            Order(customer_id="cust-1", customer_email="test@example.com", items=[])

    def test_order_item_order_id_enforcement(self):
        """Test Order enforces item order IDs."""
        item = OrderItem(
            order_id="wrong-order", product_sku="PROD-001", quantity=1, unit_price=10.0
        )
        order = Order(
            customer_id="cust-1", customer_email="test@example.com", items=[item]
        )
        # Item's order_id should be updated to match order
        assert order.items[0].order_id == order.id

    def test_order_recalculate_totals(self):
        """Test recalculating order totals."""
        item1 = OrderItem(
            order_id="ord-1", product_sku="PROD-001", quantity=2, unit_price=10.0
        )
        item2 = OrderItem(
            order_id="ord-1", product_sku="PROD-002", quantity=3, unit_price=15.0
        )
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item1, item2],
            tax=5.0,
            shipping=10.0,
        )
        order.recalculate_totals()
        assert order.subtotal == 65.0  # 20 + 45
        assert order.total == 80.0  # 65 + 5 + 10

    def test_order_add_item(self):
        """Test adding item to order."""
        item1 = OrderItem(
            order_id="ord-1", product_sku="PROD-001", quantity=1, unit_price=10.0
        )
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item1],
            tax=0,
            shipping=0,
        )

        item2 = OrderItem(
            order_id="wrong", product_sku="PROD-002", quantity=2, unit_price=15.0
        )
        order.add_item(item2)

        assert len(order.items) == 2
        assert order.items[1].order_id == order.id
        assert order.subtotal == 40.0  # 10 + 30

    def test_order_remove_item(self):
        """Test removing item from order."""
        item1 = OrderItem(
            order_id="ord-1", product_sku="PROD-001", quantity=1, unit_price=10.0
        )
        item2 = OrderItem(
            order_id="ord-1", product_sku="PROD-002", quantity=2, unit_price=15.0
        )
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item1, item2],
            tax=0,
            shipping=0,
        )

        assert order.remove_item("PROD-001") is True
        assert len(order.items) == 1
        assert order.subtotal == 30.0

    def test_order_remove_item_not_found(self):
        """Test removing non-existent item."""
        item = OrderItem(
            order_id="ord-1", product_sku="PROD-001", quantity=1, unit_price=10.0
        )
        order = Order(
            customer_id="cust-1", customer_email="test@example.com", items=[item]
        )

        assert order.remove_item("NONEXISTENT") is False
        assert len(order.items) == 1

    def test_order_get_item_count(self):
        """Test getting total item count."""
        item1 = OrderItem(
            order_id="ord-1", product_sku="PROD-001", quantity=3, unit_price=10.0
        )
        item2 = OrderItem(
            order_id="ord-1", product_sku="PROD-002", quantity=2, unit_price=15.0
        )
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item1, item2],
        )

        assert order.get_item_count() == 5

    def test_order_status_transitions(self):
        """Test valid order status transitions."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item],
            status=OrderStatus.PENDING,
        )

        assert order.can_transition_to(OrderStatus.CONFIRMED) is True
        assert order.can_transition_to(OrderStatus.CANCELLED) is True
        assert order.can_transition_to(OrderStatus.SHIPPED) is False

    def test_order_transition_to(self):
        """Test transitioning order status."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item],
            status=OrderStatus.PENDING,
        )

        assert order.transition_to(OrderStatus.CONFIRMED) is True
        assert order.status == OrderStatus.CONFIRMED

    def test_order_invalid_transition(self):
        """Test invalid status transition."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item],
            status=OrderStatus.PENDING,
        )

        assert order.transition_to(OrderStatus.SHIPPED) is False
        assert order.status == OrderStatus.PENDING

    def test_order_sets_shipped_at(self):
        """Test shipped_at timestamp is set."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item],
            status=OrderStatus.PROCESSING,
        )

        assert order.shipped_at is None
        order.transition_to(OrderStatus.SHIPPED)
        assert order.shipped_at is not None
        assert isinstance(order.shipped_at, datetime)

    def test_order_sets_delivered_at(self):
        """Test delivered_at timestamp is set."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item],
            status=OrderStatus.SHIPPED,
            shipped_at=datetime.now(UTC),
        )

        assert order.delivered_at is None
        order.transition_to(OrderStatus.DELIVERED)
        assert order.delivered_at is not None

    def test_order_is_completed(self):
        """Test checking if order is completed."""
        item = OrderItem(order_id="ord-1", product_sku="PROD-001")
        order = Order(
            customer_id="cust-1",
            customer_email="test@example.com",
            items=[item],
            status=OrderStatus.PENDING,
        )

        assert order.is_completed() is False

        order.status = OrderStatus.DELIVERED
        assert order.is_completed() is True

        order.status = OrderStatus.CANCELLED
        assert order.is_completed() is True

        order.status = OrderStatus.REFUNDED
        assert order.is_completed() is True


class TestBusinessEntitySerialization:
    """Test BusinessEntity serialization methods."""

    def test_to_dict(self):
        """Test converting entity to dictionary."""
        product = Product(sku="PROD-001", name="Widget", price=19.99, stock_quantity=5)
        data = product.to_dict()

        assert data["sku"] == "PROD-001"
        assert data["name"] == "Widget"
        assert data["price"] == 19.99
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

    def test_from_dict(self):
        """Test creating entity from dictionary."""
        data = {
            "id": "test-id",
            "sku": "PROD-001",
            "name": "Widget",
            "price": 19.99,
            "stock_quantity": 5,
            "created_at": datetime.now(UTC).isoformat(),
        }
        product = Product.from_dict(data)

        assert product.id == "test-id"
        assert product.sku == "PROD-001"
        assert product.name == "Widget"
        assert product.price == 19.99

    def test_to_neo4j(self):
        """Test converting entity to Neo4j format."""
        product = Product(
            sku="PROD-001",
            name="Widget",
            price=19.99,
            stock_quantity=5,
            tags=["electronics", "popular"],
        )
        neo4j_data = product.to_neo4j()

        assert neo4j_data["sku"] == "PROD-001"
        assert neo4j_data["name"] == "Widget"
        assert isinstance(neo4j_data["tags"], list)
        assert "created_at" in neo4j_data
        assert neo4j_data["created_at"] is not None

    def test_entity_label(self):
        """Test getting Neo4j entity label."""
        product = Product(sku="PROD-001", name="Widget")
        assert product.entity_label == "Product"

        customer = Customer(name="John", email="john@example.com")
        assert customer.entity_label == "Customer"

    def test_update_timestamp(self):
        """Test updating entity timestamp."""
        from datetime import datetime
        from unittest.mock import patch

        product = Product(sku="PROD-001", name="Widget")
        original_time = product.updated_at

        # Mock datetime to return a future time
        future_time = datetime.now(UTC).replace(year=2030)
        with patch("agentic_brain.business.base.datetime") as mock_dt:
            mock_dt.now.return_value = future_time
            mock_dt.fromisoformat = datetime.fromisoformat
            product.update_timestamp()

        assert product.updated_at > original_time
