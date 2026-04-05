#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WooCommerce Sales Dashboard - Example 79

Real-time sales monitoring, analytics, and forecasting for electronics retail.

Features:
- Real-time sales metrics and KPIs
- Revenue analysis by product/category
- Customer acquisition statistics
- Conversion funnel analysis
- Average order value tracking
- Top selling products ranking
- Sales trends and AI-powered forecasts
- Period comparisons (vs last week/month/year)

Usage:
    python 79_woo_sales_dashboard.py --demo
    python 79_woo_sales_dashboard.py --interactive
    python 79_woo_sales_dashboard.py --period today
    python 79_woo_sales_dashboard.py --forecast --days 30
"""

import argparse
import json
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

# =============================================================================
# DOMAIN MODELS
# =============================================================================


class SalesPeriod(Enum):
    """Sales analysis time periods."""

    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_QUARTER = "this_quarter"
    LAST_QUARTER = "last_quarter"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    CUSTOM = "custom"


class ProductCategory(Enum):
    """Electronics product categories."""

    SMARTPHONES = "Smartphones"
    LAPTOPS = "Laptops & Computers"
    TABLETS = "Tablets"
    AUDIO = "Audio & Headphones"
    WEARABLES = "Wearables & Smart Watches"
    GAMING = "Gaming"
    CAMERAS = "Cameras & Photography"
    ACCESSORIES = "Accessories"
    HOME_AUTOMATION = "Home Automation"
    CABLES_CHARGERS = "Cables & Chargers"


class OrderStatus(Enum):
    """WooCommerce order statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    ON_HOLD = "on-hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"


@dataclass
class Product:
    """Product in the catalog."""

    id: int
    sku: str
    name: str
    category: ProductCategory
    price: float
    cost: float
    stock_quantity: int
    weight: float = 0.0
    is_featured: bool = False

    @property
    def margin(self) -> float:
        """Calculate profit margin percentage."""
        if self.price > 0:
            return ((self.price - self.cost) / self.price) * 100
        return 0.0


@dataclass
class OrderItem:
    """Line item in an order."""

    product: Product
    quantity: int
    unit_price: float
    discount: float = 0.0

    @property
    def line_total(self) -> float:
        """Calculate line total after discount."""
        return (self.unit_price * self.quantity) - self.discount

    @property
    def line_cost(self) -> float:
        """Calculate cost for this line."""
        return self.product.cost * self.quantity


@dataclass
class Customer:
    """Customer profile."""

    id: int
    email: str
    first_name: str
    last_name: str
    state: str
    country: str
    created_date: datetime
    total_orders: int = 0
    total_spent: float = 0.0
    is_new: bool = False

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Order:
    """WooCommerce order."""

    id: int
    order_number: str
    customer: Customer
    items: list[OrderItem]
    status: OrderStatus
    created_date: datetime
    completed_date: Optional[datetime]
    payment_method: str
    shipping_method: str
    shipping_cost: float
    discount_total: float = 0.0
    coupon_code: Optional[str] = None
    source: str = "website"

    @property
    def subtotal(self) -> float:
        """Order subtotal before shipping."""
        return sum(item.line_total for item in self.items)

    @property
    def total(self) -> float:
        """Order total including shipping."""
        return self.subtotal + self.shipping_cost

    @property
    def total_cost(self) -> float:
        """Total cost of goods sold."""
        return sum(item.line_cost for item in self.items)

    @property
    def profit(self) -> float:
        """Gross profit on order."""
        return self.subtotal - self.total_cost

    @property
    def item_count(self) -> int:
        """Total items in order."""
        return sum(item.quantity for item in self.items)


@dataclass
class SalesMetrics:
    """Aggregated sales metrics."""

    period_start: datetime
    period_end: datetime
    total_revenue: float = 0.0
    total_cost: float = 0.0
    total_orders: int = 0
    total_items: int = 0
    total_customers: int = 0
    new_customers: int = 0
    returning_customers: int = 0
    refunds: float = 0.0
    discounts_given: float = 0.0
    shipping_revenue: float = 0.0
    avg_order_value: float = 0.0
    avg_items_per_order: float = 0.0
    conversion_rate: float = 0.0

    @property
    def gross_profit(self) -> float:
        return self.total_revenue - self.total_cost

    @property
    def net_revenue(self) -> float:
        return self.total_revenue - self.refunds

    @property
    def profit_margin(self) -> float:
        if self.total_revenue > 0:
            return (self.gross_profit / self.total_revenue) * 100
        return 0.0


@dataclass
class ProductSales:
    """Sales metrics for a single product."""

    product: Product
    units_sold: int = 0
    revenue: float = 0.0
    cost: float = 0.0
    orders_count: int = 0
    avg_discount: float = 0.0
    return_rate: float = 0.0

    @property
    def profit(self) -> float:
        return self.revenue - self.cost


@dataclass
class CategorySales:
    """Sales metrics for a category."""

    category: ProductCategory
    total_revenue: float = 0.0
    total_units: int = 0
    total_orders: int = 0
    product_count: int = 0
    avg_order_value: float = 0.0


@dataclass
class FunnelStage:
    """Conversion funnel stage."""

    name: str
    visitors: int
    conversion_rate: float
    drop_off_rate: float


@dataclass
class SalesForecast:
    """Sales forecast data point."""

    date: datetime
    predicted_revenue: float
    predicted_orders: int
    confidence_low: float
    confidence_high: float
    factors: list[str] = field(default_factory=list)


# =============================================================================
# DEMO DATA GENERATOR
# =============================================================================


class DemoDataGenerator:
    """Generate realistic demo data for electronics store."""

    # Australian states for customer data
    STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]

    # Common first names
    FIRST_NAMES = [
        "James",
        "Emma",
        "Oliver",
        "Charlotte",
        "William",
        "Amelia",
        "Jack",
        "Olivia",
        "Noah",
        "Isla",
        "Lucas",
        "Mia",
        "Ethan",
        "Ava",
        "Liam",
        "Grace",
        "Mason",
        "Sophie",
        "Alexander",
        "Chloe",
        "Henry",
        "Lily",
        "Sebastian",
        "Emily",
        "Thomas",
        "Zoe",
        "Benjamin",
        "Harper",
        "Daniel",
        "Ella",
        "Michael",
        "Ruby",
        "Matthew",
        "Aria",
        "TestUser",
        "Madison",
    ]

    # Common last names
    LAST_NAMES = [
        "Smith",
        "Jones",
        "Williams",
        "Brown",
        "Wilson",
        "Taylor",
        "Johnson",
        "Anderson",
        "Thomas",
        "Walker",
        "Harris",
        "Lee",
        "Martin",
        "Robinson",
        "Clark",
        "Lewis",
        "Young",
        "Hall",
        "Allen",
        "Wright",
        "King",
        "Scott",
        "Green",
        "Adams",
        "Baker",
        "Nelson",
        "Mitchell",
        "Campbell",
        "Roberts",
    ]

    # Electronics products catalog
    PRODUCTS = [
        # Smartphones
        {
            "sku": "SP-IP15-256",
            "name": "Smartphone Pro 15 256GB",
            "category": ProductCategory.SMARTPHONES,
            "price": 1699,
            "cost": 1200,
        },
        {
            "sku": "SP-IP15-128",
            "name": "Smartphone Pro 15 128GB",
            "category": ProductCategory.SMARTPHONES,
            "price": 1499,
            "cost": 1050,
        },
        {
            "sku": "SP-S24-256",
            "name": "Galaxy Smartphone S24 256GB",
            "category": ProductCategory.SMARTPHONES,
            "price": 1349,
            "cost": 950,
        },
        {
            "sku": "SP-PX8-128",
            "name": "Pixel Phone 8 128GB",
            "category": ProductCategory.SMARTPHONES,
            "price": 999,
            "cost": 700,
        },
        {
            "sku": "SP-BUD-MID",
            "name": "Budget Smartphone Pro",
            "category": ProductCategory.SMARTPHONES,
            "price": 399,
            "cost": 250,
        },
        # Laptops
        {
            "sku": "LP-MBP-14",
            "name": "MacBook Pro 14-inch M3",
            "category": ProductCategory.LAPTOPS,
            "price": 3199,
            "cost": 2400,
        },
        {
            "sku": "LP-MBP-16",
            "name": "MacBook Pro 16-inch M3",
            "category": ProductCategory.LAPTOPS,
            "price": 4299,
            "cost": 3200,
        },
        {
            "sku": "LP-MBA-15",
            "name": "MacBook Air 15-inch M3",
            "category": ProductCategory.LAPTOPS,
            "price": 2199,
            "cost": 1600,
        },
        {
            "sku": "LP-DELL-XPS",
            "name": "Dell XPS 15 Laptop",
            "category": ProductCategory.LAPTOPS,
            "price": 2499,
            "cost": 1800,
        },
        {
            "sku": "LP-THINKPAD",
            "name": "ThinkPad X1 Carbon",
            "category": ProductCategory.LAPTOPS,
            "price": 2299,
            "cost": 1700,
        },
        {
            "sku": "LP-HP-ENVVY",
            "name": "HP Envy 15 Laptop",
            "category": ProductCategory.LAPTOPS,
            "price": 1599,
            "cost": 1100,
        },
        {
            "sku": "LP-ASUS-ZEN",
            "name": "Asus ZenBook 14",
            "category": ProductCategory.LAPTOPS,
            "price": 1399,
            "cost": 950,
        },
        # Tablets
        {
            "sku": "TB-IPADPRO",
            "name": "iPad Pro 12.9-inch M2",
            "category": ProductCategory.TABLETS,
            "price": 1899,
            "cost": 1400,
        },
        {
            "sku": "TB-IPADAIR",
            "name": "iPad Air 10.9-inch",
            "category": ProductCategory.TABLETS,
            "price": 929,
            "cost": 650,
        },
        {
            "sku": "TB-SAMSUNGS9",
            "name": "Samsung Galaxy Tab S9",
            "category": ProductCategory.TABLETS,
            "price": 1199,
            "cost": 850,
        },
        {
            "sku": "TB-IPADMINI",
            "name": "iPad Mini 6th Gen",
            "category": ProductCategory.TABLETS,
            "price": 749,
            "cost": 520,
        },
        # Audio
        {
            "sku": "AU-APPMAX",
            "name": "AirPods Max",
            "category": ProductCategory.AUDIO,
            "price": 899,
            "cost": 600,
        },
        {
            "sku": "AU-APPPRO2",
            "name": "AirPods Pro 2nd Gen",
            "category": ProductCategory.AUDIO,
            "price": 399,
            "cost": 260,
        },
        {
            "sku": "AU-SONYWH",
            "name": "Sony WH-1000XM5 Headphones",
            "category": ProductCategory.AUDIO,
            "price": 549,
            "cost": 380,
        },
        {
            "sku": "AU-BOSEQC",
            "name": "Bose QuietComfort Ultra",
            "category": ProductCategory.AUDIO,
            "price": 649,
            "cost": 450,
        },
        {
            "sku": "AU-SENNHD",
            "name": "Sennheiser HD 660S2",
            "category": ProductCategory.AUDIO,
            "price": 799,
            "cost": 550,
        },
        {
            "sku": "AU-JBLFLIP",
            "name": "JBL Flip 6 Speaker",
            "category": ProductCategory.AUDIO,
            "price": 149,
            "cost": 85,
        },
        {
            "sku": "AU-SONOS",
            "name": "Sonos One SL Speaker",
            "category": ProductCategory.AUDIO,
            "price": 279,
            "cost": 180,
        },
        # Wearables
        {
            "sku": "WR-AW9-45",
            "name": "Apple Watch Series 9 45mm",
            "category": ProductCategory.WEARABLES,
            "price": 649,
            "cost": 420,
        },
        {
            "sku": "WR-AWULTRA",
            "name": "Apple Watch Ultra 2",
            "category": ProductCategory.WEARABLES,
            "price": 1399,
            "cost": 950,
        },
        {
            "sku": "WR-SAMW6",
            "name": "Samsung Galaxy Watch 6",
            "category": ProductCategory.WEARABLES,
            "price": 479,
            "cost": 310,
        },
        {
            "sku": "WR-FITBIT",
            "name": "Fitbit Sense 2",
            "category": ProductCategory.WEARABLES,
            "price": 449,
            "cost": 290,
        },
        {
            "sku": "WR-GARMIN",
            "name": "Garmin Fenix 7X",
            "category": ProductCategory.WEARABLES,
            "price": 1199,
            "cost": 800,
        },
        # Gaming
        {
            "sku": "GM-PS5",
            "name": "PlayStation 5 Console",
            "category": ProductCategory.GAMING,
            "price": 799,
            "cost": 650,
        },
        {
            "sku": "GM-XBOXSX",
            "name": "Xbox Series X Console",
            "category": ProductCategory.GAMING,
            "price": 799,
            "cost": 650,
        },
        {
            "sku": "GM-SWITCH",
            "name": "Nintendo Switch OLED",
            "category": ProductCategory.GAMING,
            "price": 539,
            "cost": 420,
        },
        {
            "sku": "GM-STEADK",
            "name": "Steam Deck 512GB",
            "category": ProductCategory.GAMING,
            "price": 899,
            "cost": 700,
        },
        {
            "sku": "GM-PS5CTRL",
            "name": "DualSense Controller",
            "category": ProductCategory.GAMING,
            "price": 109,
            "cost": 65,
        },
        {
            "sku": "GM-HEADSET",
            "name": "Gaming Headset Pro",
            "category": ProductCategory.GAMING,
            "price": 249,
            "cost": 150,
        },
        # Cameras
        {
            "sku": "CM-SONYZV",
            "name": "Sony ZV-E10 Camera",
            "category": ProductCategory.CAMERAS,
            "price": 1049,
            "cost": 750,
        },
        {
            "sku": "CM-CANON",
            "name": "Canon EOS R50 Mirrorless",
            "category": ProductCategory.CAMERAS,
            "price": 1199,
            "cost": 850,
        },
        {
            "sku": "CM-GOPRO",
            "name": "GoPro HERO12 Black",
            "category": ProductCategory.CAMERAS,
            "price": 649,
            "cost": 450,
        },
        {
            "sku": "CM-DJI4PRO",
            "name": "DJI Mavic 3 Pro Drone",
            "category": ProductCategory.CAMERAS,
            "price": 3099,
            "cost": 2200,
        },
        {
            "sku": "CM-INSTAX",
            "name": "Fujifilm Instax Mini 12",
            "category": ProductCategory.CAMERAS,
            "price": 129,
            "cost": 75,
        },
        # Accessories
        {
            "sku": "AC-MSMOUSE",
            "name": "MagicSpeed Mouse",
            "category": ProductCategory.ACCESSORIES,
            "price": 129,
            "cost": 75,
        },
        {
            "sku": "AC-MKEYB",
            "name": "Magic Keyboard with Touch ID",
            "category": ProductCategory.ACCESSORIES,
            "price": 299,
            "cost": 180,
        },
        {
            "sku": "AC-LOGIMX",
            "name": "Logitech MX Master 3S",
            "category": ProductCategory.ACCESSORIES,
            "price": 169,
            "cost": 100,
        },
        {
            "sku": "AC-WEBCAM",
            "name": "4K Webcam Pro",
            "category": ProductCategory.ACCESSORIES,
            "price": 199,
            "cost": 110,
        },
        {
            "sku": "AC-MONITOR",
            "name": "27-inch 4K Monitor",
            "category": ProductCategory.ACCESSORIES,
            "price": 549,
            "cost": 380,
        },
        {
            "sku": "AC-USBHUB",
            "name": "USB-C Hub 7-in-1",
            "category": ProductCategory.ACCESSORIES,
            "price": 89,
            "cost": 45,
        },
        # Home Automation
        {
            "sku": "HA-HOMEPOD",
            "name": "HomePod Mini",
            "category": ProductCategory.HOME_AUTOMATION,
            "price": 149,
            "cost": 95,
        },
        {
            "sku": "HA-ECHOD",
            "name": "Echo Dot 5th Gen",
            "category": ProductCategory.HOME_AUTOMATION,
            "price": 79,
            "cost": 45,
        },
        {
            "sku": "HA-NESTCAM",
            "name": "Nest Cam Indoor",
            "category": ProductCategory.HOME_AUTOMATION,
            "price": 179,
            "cost": 110,
        },
        {
            "sku": "HA-HUEKIT",
            "name": "Philips Hue Starter Kit",
            "category": ProductCategory.HOME_AUTOMATION,
            "price": 249,
            "cost": 160,
        },
        {
            "sku": "HA-RINGDB",
            "name": "Ring Video Doorbell Pro",
            "category": ProductCategory.HOME_AUTOMATION,
            "price": 329,
            "cost": 220,
        },
        # Cables & Chargers
        {
            "sku": "CC-MAGSAFE",
            "name": "MagSafe Charger",
            "category": ProductCategory.CABLES_CHARGERS,
            "price": 59,
            "cost": 30,
        },
        {
            "sku": "CC-USBCPD",
            "name": "USB-C 100W PD Charger",
            "category": ProductCategory.CABLES_CHARGERS,
            "price": 79,
            "cost": 40,
        },
        {
            "sku": "CC-LIGHT2M",
            "name": "Lightning Cable 2m",
            "category": ProductCategory.CABLES_CHARGERS,
            "price": 35,
            "cost": 12,
        },
        {
            "sku": "CC-USBCAB",
            "name": "USB-C Cable 2m Braided",
            "category": ProductCategory.CABLES_CHARGERS,
            "price": 29,
            "cost": 10,
        },
        {
            "sku": "CC-WIRELESS",
            "name": "Wireless Charging Pad",
            "category": ProductCategory.CABLES_CHARGERS,
            "price": 49,
            "cost": 22,
        },
        {
            "sku": "CC-CARCHAR",
            "name": "Car Charger Dual USB-C",
            "category": ProductCategory.CABLES_CHARGERS,
            "price": 45,
            "cost": 18,
        },
        {
            "sku": "CC-POWERBNK",
            "name": "Power Bank 20000mAh",
            "category": ProductCategory.CABLES_CHARGERS,
            "price": 79,
            "cost": 35,
        },
    ]

    PAYMENT_METHODS = [
        "credit_card",
        "paypal",
        "afterpay",
        "zip_pay",
        "apple_pay",
        "google_pay",
        "bank_transfer",
    ]
    SHIPPING_METHODS = ["standard", "express", "next_day", "click_collect"]
    ORDER_SOURCES = ["website", "mobile_app", "phone", "in_store", "marketplace"]
    COUPON_CODES = [
        "SAVE10",
        "WELCOME15",
        "VIP20",
        "FLASH25",
        "STUDENT10",
        "BUNDLE15",
        None,
        None,
        None,
    ]

    def __init__(self, seed: int = 42):
        """Initialize generator with seed for reproducibility."""
        random.seed(seed)
        self._product_id = 1000
        self._customer_id = 5000
        self._order_id = 10000
        self.products = self._create_products()
        self.customers = []
        self.orders = []

    def _create_products(self) -> list[Product]:
        """Create product catalog."""
        products = []
        for p in self.PRODUCTS:
            self._product_id += 1
            products.append(
                Product(
                    id=self._product_id,
                    sku=p["sku"],
                    name=p["name"],
                    category=p["category"],
                    price=p["price"],
                    cost=p["cost"],
                    stock_quantity=random.randint(5, 200),
                    weight=random.uniform(0.1, 5.0),
                    is_featured=random.random() < 0.15,
                )
            )
        return products

    def create_customer(self, created_date: datetime) -> Customer:
        """Create a random customer."""
        self._customer_id += 1
        return Customer(
            id=self._customer_id,
            email=f"{random.choice(self.FIRST_NAMES).lower()}.{random.choice(self.LAST_NAMES).lower()}{random.randint(1,999)}@email.com",
            first_name=random.choice(self.FIRST_NAMES),
            last_name=random.choice(self.LAST_NAMES),
            state=random.choice(self.STATES),
            country="Australia",
            created_date=created_date,
            is_new=random.random() < 0.3,
        )

    def create_order(
        self,
        customer: Customer,
        created_date: datetime,
        status: Optional[OrderStatus] = None,
    ) -> Order:
        """Create a random order."""
        self._order_id += 1

        # Determine order status
        if status is None:
            status_weights = [0.02, 0.08, 0.02, 0.80, 0.03, 0.03, 0.02]
            status = random.choices(list(OrderStatus), weights=status_weights)[0]

        # Create order items (1-5 items per order)
        num_items = random.choices(
            [1, 2, 3, 4, 5], weights=[0.35, 0.30, 0.20, 0.10, 0.05]
        )[0]
        selected_products = random.sample(
            self.products, min(num_items, len(self.products))
        )

        items = []
        for product in selected_products:
            quantity = random.choices([1, 2, 3], weights=[0.7, 0.25, 0.05])[0]
            discount = random.choice(
                [0, 0, 0, product.price * 0.05, product.price * 0.10]
            )
            items.append(
                OrderItem(
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    discount=discount,
                )
            )

        # Shipping cost based on method
        shipping_method = random.choice(self.SHIPPING_METHODS)
        shipping_costs = {
            "standard": 9.95,
            "express": 14.95,
            "next_day": 24.95,
            "click_collect": 0,
        }
        shipping_cost = shipping_costs[shipping_method]

        # Free shipping over $150
        subtotal = sum(item.line_total for item in items)
        if subtotal >= 150:
            shipping_cost = 0

        # Completed date for completed orders
        completed_date = None
        if status == OrderStatus.COMPLETED:
            completed_date = created_date + timedelta(days=random.randint(1, 5))

        return Order(
            id=self._order_id,
            order_number=f"ORD-{self._order_id}",
            customer=customer,
            items=items,
            status=status,
            created_date=created_date,
            completed_date=completed_date,
            payment_method=random.choice(self.PAYMENT_METHODS),
            shipping_method=shipping_method,
            shipping_cost=shipping_cost,
            discount_total=sum(item.discount for item in items),
            coupon_code=random.choice(self.COUPON_CODES),
            source=random.choice(self.ORDER_SOURCES),
        )

    def generate_orders(
        self, days: int = 90, base_orders_per_day: int = 25
    ) -> list[Order]:
        """Generate orders over a time period."""
        orders = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        current_date = start_date
        while current_date <= end_date:
            # Vary orders by day of week (more on weekends)
            day_of_week = current_date.weekday()
            if day_of_week >= 5:  # Weekend
                daily_orders = int(base_orders_per_day * random.uniform(1.3, 1.6))
            else:
                daily_orders = int(base_orders_per_day * random.uniform(0.8, 1.2))

            # Generate orders for this day
            for _ in range(daily_orders):
                # Random time during the day
                order_time = current_date.replace(
                    hour=random.randint(6, 23),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                )

                # Create or reuse customer (70% chance of new customer)
                if self.customers and random.random() < 0.3:
                    customer = random.choice(self.customers)
                else:
                    customer = self.create_customer(order_time)
                    self.customers.append(customer)

                order = self.create_order(customer, order_time)
                orders.append(order)

            current_date += timedelta(days=1)

        self.orders = sorted(orders, key=lambda o: o.created_date)
        return self.orders


# =============================================================================
# SALES ANALYTICS ENGINE
# =============================================================================


class SalesAnalytics:
    """Analyze sales data and compute metrics."""

    def __init__(self, orders: list[Order], products: list[Product]):
        """Initialize with orders and products."""
        self.orders = orders
        self.products = products

    def get_period_dates(self, period: SalesPeriod) -> tuple[datetime, datetime]:
        """Get start and end dates for a period."""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if period == SalesPeriod.TODAY:
            return today_start, now
        elif period == SalesPeriod.YESTERDAY:
            yesterday = today_start - timedelta(days=1)
            return yesterday, today_start
        elif period == SalesPeriod.THIS_WEEK:
            week_start = today_start - timedelta(days=now.weekday())
            return week_start, now
        elif period == SalesPeriod.LAST_WEEK:
            this_week_start = today_start - timedelta(days=now.weekday())
            last_week_start = this_week_start - timedelta(days=7)
            return last_week_start, this_week_start
        elif period == SalesPeriod.THIS_MONTH:
            month_start = today_start.replace(day=1)
            return month_start, now
        elif period == SalesPeriod.LAST_MONTH:
            this_month_start = today_start.replace(day=1)
            last_month_end = this_month_start - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start, this_month_start
        elif period == SalesPeriod.THIS_QUARTER:
            quarter = (now.month - 1) // 3
            quarter_start = today_start.replace(month=quarter * 3 + 1, day=1)
            return quarter_start, now
        elif period == SalesPeriod.THIS_YEAR:
            year_start = today_start.replace(month=1, day=1)
            return year_start, now
        else:
            # Default to last 30 days
            return today_start - timedelta(days=30), now

    def filter_orders(
        self,
        start_date: datetime,
        end_date: datetime,
        status_filter: Optional[list[OrderStatus]] = None,
    ) -> list[Order]:
        """Filter orders by date range and status."""
        filtered = [o for o in self.orders if start_date <= o.created_date <= end_date]

        if status_filter:
            filtered = [o for o in filtered if o.status in status_filter]

        return filtered

    def calculate_metrics(self, period: SalesPeriod, visitors: int = 0) -> SalesMetrics:
        """Calculate sales metrics for a period."""
        start_date, end_date = self.get_period_dates(period)
        orders = self.filter_orders(start_date, end_date)

        # Filter to completed/processing orders for revenue
        revenue_orders = [
            o
            for o in orders
            if o.status in [OrderStatus.COMPLETED, OrderStatus.PROCESSING]
        ]

        # Calculate refunds
        refunded_orders = [o for o in orders if o.status == OrderStatus.REFUNDED]
        refunds = sum(o.total for o in refunded_orders)

        # Customer metrics
        customer_ids = set()
        new_customer_ids = set()
        for order in revenue_orders:
            customer_ids.add(order.customer.id)
            if order.customer.is_new:
                new_customer_ids.add(order.customer.id)

        total_revenue = sum(o.total for o in revenue_orders)
        total_cost = sum(o.total_cost for o in revenue_orders)
        total_items = sum(o.item_count for o in revenue_orders)
        total_orders = len(revenue_orders)
        shipping_revenue = sum(o.shipping_cost for o in revenue_orders)
        discounts = sum(o.discount_total for o in revenue_orders)

        metrics = SalesMetrics(
            period_start=start_date,
            period_end=end_date,
            total_revenue=total_revenue,
            total_cost=total_cost,
            total_orders=total_orders,
            total_items=total_items,
            total_customers=len(customer_ids),
            new_customers=len(new_customer_ids),
            returning_customers=len(customer_ids) - len(new_customer_ids),
            refunds=refunds,
            discounts_given=discounts,
            shipping_revenue=shipping_revenue,
            avg_order_value=total_revenue / total_orders if total_orders > 0 else 0,
            avg_items_per_order=total_items / total_orders if total_orders > 0 else 0,
            conversion_rate=(total_orders / visitors * 100) if visitors > 0 else 0,
        )

        return metrics

    def get_product_sales(
        self, period: SalesPeriod, limit: int = 20
    ) -> list[ProductSales]:
        """Get top selling products for a period."""
        start_date, end_date = self.get_period_dates(period)
        orders = self.filter_orders(
            start_date,
            end_date,
            status_filter=[OrderStatus.COMPLETED, OrderStatus.PROCESSING],
        )

        # Aggregate by product
        product_stats: dict[int, ProductSales] = {}

        for order in orders:
            for item in order.items:
                product_id = item.product.id
                if product_id not in product_stats:
                    product_stats[product_id] = ProductSales(product=item.product)

                stats = product_stats[product_id]
                stats.units_sold += item.quantity
                stats.revenue += item.line_total
                stats.cost += item.line_cost
                stats.orders_count += 1

        # Sort by revenue and return top N
        sorted_products = sorted(
            product_stats.values(), key=lambda p: p.revenue, reverse=True
        )

        return sorted_products[:limit]

    def get_category_sales(self, period: SalesPeriod) -> list[CategorySales]:
        """Get sales breakdown by category."""
        start_date, end_date = self.get_period_dates(period)
        orders = self.filter_orders(
            start_date,
            end_date,
            status_filter=[OrderStatus.COMPLETED, OrderStatus.PROCESSING],
        )

        # Aggregate by category
        category_stats: dict[ProductCategory, CategorySales] = {}

        for order in orders:
            for item in order.items:
                category = item.product.category
                if category not in category_stats:
                    category_stats[category] = CategorySales(category=category)

                stats = category_stats[category]
                stats.total_revenue += item.line_total
                stats.total_units += item.quantity

        # Count orders per category
        for order in orders:
            categories_in_order = set(item.product.category for item in order.items)
            for category in categories_in_order:
                if category in category_stats:
                    category_stats[category].total_orders += 1

        # Calculate average order value
        for stats in category_stats.values():
            if stats.total_orders > 0:
                stats.avg_order_value = stats.total_revenue / stats.total_orders

        return sorted(
            category_stats.values(), key=lambda c: c.total_revenue, reverse=True
        )

    def get_hourly_distribution(self, period: SalesPeriod) -> dict[int, dict]:
        """Get sales distribution by hour of day."""
        start_date, end_date = self.get_period_dates(period)
        orders = self.filter_orders(
            start_date,
            end_date,
            status_filter=[OrderStatus.COMPLETED, OrderStatus.PROCESSING],
        )

        hourly = {hour: {"orders": 0, "revenue": 0} for hour in range(24)}

        for order in orders:
            hour = order.created_date.hour
            hourly[hour]["orders"] += 1
            hourly[hour]["revenue"] += order.total

        return hourly

    def get_daily_trend(self, days: int = 30) -> list[dict]:
        """Get daily sales trend."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        daily = []
        current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        while current < end_date:
            next_day = current + timedelta(days=1)
            day_orders = self.filter_orders(
                current,
                next_day,
                status_filter=[OrderStatus.COMPLETED, OrderStatus.PROCESSING],
            )

            daily.append(
                {
                    "date": current.strftime("%Y-%m-%d"),
                    "orders": len(day_orders),
                    "revenue": sum(o.total for o in day_orders),
                    "items": sum(o.item_count for o in day_orders),
                    "avg_order_value": (
                        sum(o.total for o in day_orders) / len(day_orders)
                        if day_orders
                        else 0
                    ),
                }
            )

            current = next_day

        return daily

    def get_conversion_funnel(self, visitors: int = 10000) -> list[FunnelStage]:
        """Calculate conversion funnel stages."""
        # Simulate funnel data based on orders
        total_orders = len(
            [o for o in self.orders if o.status != OrderStatus.CANCELLED]
        )

        # Typical e-commerce funnel conversion rates
        cart_add_rate = random.uniform(0.08, 0.12)
        checkout_start_rate = random.uniform(0.45, 0.55)
        checkout_complete_rate = random.uniform(0.60, 0.70)

        cart_adds = int(visitors * cart_add_rate)
        checkout_starts = int(cart_adds * checkout_start_rate)
        completed_orders = int(checkout_starts * checkout_complete_rate)

        funnel = [
            FunnelStage(
                name="Visitors",
                visitors=visitors,
                conversion_rate=100.0,
                drop_off_rate=0.0,
            ),
            FunnelStage(
                name="Product Views",
                visitors=int(visitors * 0.65),
                conversion_rate=65.0,
                drop_off_rate=35.0,
            ),
            FunnelStage(
                name="Add to Cart",
                visitors=cart_adds,
                conversion_rate=cart_add_rate * 100,
                drop_off_rate=(1 - cart_add_rate) * 100,
            ),
            FunnelStage(
                name="Checkout Started",
                visitors=checkout_starts,
                conversion_rate=checkout_start_rate * 100,
                drop_off_rate=(1 - checkout_start_rate) * 100,
            ),
            FunnelStage(
                name="Purchase Complete",
                visitors=completed_orders,
                conversion_rate=checkout_complete_rate * 100,
                drop_off_rate=(1 - checkout_complete_rate) * 100,
            ),
        ]

        return funnel

    def compare_periods(
        self, current_period: SalesPeriod, comparison_period: SalesPeriod
    ) -> dict[str, dict]:
        """Compare metrics between two periods."""
        current = self.calculate_metrics(current_period, visitors=10000)
        comparison = self.calculate_metrics(comparison_period, visitors=9500)

        def calc_change(current_val: float, prev_val: float) -> dict:
            if prev_val > 0:
                change = ((current_val - prev_val) / prev_val) * 100
            else:
                change = 100 if current_val > 0 else 0
            return {
                "current": current_val,
                "previous": prev_val,
                "change_percent": round(change, 2),
                "trend": "up" if change > 0 else "down" if change < 0 else "flat",
            }

        return {
            "revenue": calc_change(current.total_revenue, comparison.total_revenue),
            "orders": calc_change(current.total_orders, comparison.total_orders),
            "avg_order_value": calc_change(
                current.avg_order_value, comparison.avg_order_value
            ),
            "customers": calc_change(
                current.total_customers, comparison.total_customers
            ),
            "new_customers": calc_change(
                current.new_customers, comparison.new_customers
            ),
            "profit_margin": calc_change(
                current.profit_margin, comparison.profit_margin
            ),
            "items_sold": calc_change(current.total_items, comparison.total_items),
        }


# =============================================================================
# SALES FORECASTING
# =============================================================================


class SalesForecaster:
    """AI-powered sales forecasting."""

    def __init__(self, analytics: SalesAnalytics):
        """Initialize forecaster with analytics engine."""
        self.analytics = analytics

    def predict_daily_sales(self, days_ahead: int = 30) -> list[SalesForecast]:
        """Predict daily sales for the next N days."""
        # Get historical daily trend
        historical = self.analytics.get_daily_trend(days=60)

        if not historical:
            return []

        # Calculate base statistics
        revenues = [d["revenue"] for d in historical]
        orders = [d["orders"] for d in historical]

        avg_revenue = statistics.mean(revenues)
        std_revenue = (
            statistics.stdev(revenues) if len(revenues) > 1 else avg_revenue * 0.1
        )
        avg_orders = statistics.mean(orders)

        # Weekly pattern (day of week multipliers)
        weekly_pattern = [0.85, 0.90, 0.95, 1.0, 1.1, 1.25, 1.20]  # Mon-Sun

        # Generate forecasts
        forecasts = []
        start_date = datetime.now()

        for day in range(1, days_ahead + 1):
            forecast_date = start_date + timedelta(days=day)
            day_of_week = forecast_date.weekday()

            # Apply weekly pattern and add some randomness for demo
            base_revenue = avg_revenue * weekly_pattern[day_of_week]
            predicted_revenue = base_revenue * random.uniform(0.95, 1.05)

            # Calculate confidence interval
            confidence_low = predicted_revenue - (std_revenue * 1.5)
            confidence_high = predicted_revenue + (std_revenue * 1.5)

            # Determine factors affecting forecast
            factors = []
            if day_of_week >= 5:
                factors.append("Weekend shopping increase")
            if forecast_date.day <= 5:
                factors.append("Start of month - payday effect")
            if 10 <= forecast_date.day <= 15:
                factors.append("Mid-month typical dip")

            forecasts.append(
                SalesForecast(
                    date=forecast_date,
                    predicted_revenue=predicted_revenue,
                    predicted_orders=int(avg_orders * weekly_pattern[day_of_week]),
                    confidence_low=max(0, confidence_low),
                    confidence_high=confidence_high,
                    factors=factors,
                )
            )

        return forecasts

    def predict_category_growth(self) -> dict[ProductCategory, dict]:
        """Predict category growth trends."""
        current = self.analytics.get_category_sales(SalesPeriod.THIS_MONTH)
        previous = self.analytics.get_category_sales(SalesPeriod.LAST_MONTH)

        current_dict = {c.category: c for c in current}
        previous_dict = {c.category: c for c in previous}

        predictions = {}
        for category in ProductCategory:
            curr = current_dict.get(category)
            prev = previous_dict.get(category)

            if curr and prev and prev.total_revenue > 0:
                growth_rate = (
                    curr.total_revenue - prev.total_revenue
                ) / prev.total_revenue
                predicted_next = curr.total_revenue * (1 + growth_rate)
            else:
                growth_rate = 0
                predicted_next = curr.total_revenue if curr else 0

            predictions[category] = {
                "current_revenue": curr.total_revenue if curr else 0,
                "growth_rate": round(growth_rate * 100, 2),
                "predicted_next_month": predicted_next,
                "trend": (
                    "growing"
                    if growth_rate > 0.05
                    else "declining" if growth_rate < -0.05 else "stable"
                ),
            }

        return predictions

    def identify_opportunities(self) -> list[dict]:
        """Identify sales optimization opportunities."""
        opportunities = []

        # Analyze product performance
        products = self.analytics.get_product_sales(SalesPeriod.THIS_MONTH)

        # Find high-margin products with low sales
        for ps in products:
            if ps.product.margin > 40 and ps.units_sold < 10:
                opportunities.append(
                    {
                        "type": "underperforming_high_margin",
                        "product": ps.product.name,
                        "insight": f"High margin ({ps.product.margin:.0f}%) but only {ps.units_sold} units sold",
                        "recommendation": "Consider promotional pricing or featured placement",
                        "potential_impact": "high",
                    }
                )

        # Find products with high velocity
        for ps in products[:5]:
            if ps.units_sold > 50:
                opportunities.append(
                    {
                        "type": "bestseller_opportunity",
                        "product": ps.product.name,
                        "insight": f"Strong performer with {ps.units_sold} units sold",
                        "recommendation": "Ensure adequate stock and consider upsell bundles",
                        "potential_impact": "medium",
                    }
                )

        # Analyze funnel
        funnel = self.analytics.get_conversion_funnel()
        cart_stage = next((s for s in funnel if s.name == "Add to Cart"), None)
        if cart_stage and cart_stage.drop_off_rate > 40:
            opportunities.append(
                {
                    "type": "funnel_optimization",
                    "stage": "Add to Cart",
                    "insight": f"{cart_stage.drop_off_rate:.0f}% drop-off at cart addition",
                    "recommendation": "Implement exit-intent popups or cart reminders",
                    "potential_impact": "high",
                }
            )

        return opportunities


# =============================================================================
# DASHBOARD DISPLAY
# =============================================================================


class SalesDashboard:
    """Display sales dashboard in terminal."""

    def __init__(self, analytics: SalesAnalytics, forecaster: SalesForecaster):
        """Initialize dashboard."""
        self.analytics = analytics
        self.forecaster = forecaster

    def format_currency(self, amount: float) -> str:
        """Format amount as currency."""
        return f"${amount:,.2f}"

    def format_percent(self, value: float) -> str:
        """Format as percentage."""
        return f"{value:.1f}%"

    def format_trend(self, change: float) -> str:
        """Format trend indicator."""
        if change > 0:
            return f"↑ +{change:.1f}%"
        elif change < 0:
            return f"↓ {change:.1f}%"
        return "→ 0%"

    def show_summary(self, period: SalesPeriod = SalesPeriod.THIS_MONTH):
        """Show summary dashboard."""
        print("\n" + "=" * 80)
        print("📊 WOOCOMMERCE SALES DASHBOARD - Electronics Store")
        print("=" * 80)

        metrics = self.analytics.calculate_metrics(period, visitors=15000)

        print(f"\n📅 Period: {period.value.replace('_', ' ').title()}")
        print(f"   From: {metrics.period_start.strftime('%Y-%m-%d')}")
        print(f"   To: {metrics.period_end.strftime('%Y-%m-%d')}")

        print("\n" + "-" * 40)
        print("💰 REVENUE METRICS")
        print("-" * 40)
        print(f"   Total Revenue:      {self.format_currency(metrics.total_revenue)}")
        print(f"   Net Revenue:        {self.format_currency(metrics.net_revenue)}")
        print(f"   Gross Profit:       {self.format_currency(metrics.gross_profit)}")
        print(f"   Profit Margin:      {self.format_percent(metrics.profit_margin)}")
        print(
            f"   Shipping Revenue:   {self.format_currency(metrics.shipping_revenue)}"
        )
        print(f"   Discounts Given:    {self.format_currency(metrics.discounts_given)}")
        print(f"   Refunds:            {self.format_currency(metrics.refunds)}")

        print("\n" + "-" * 40)
        print("📦 ORDER METRICS")
        print("-" * 40)
        print(f"   Total Orders:       {metrics.total_orders:,}")
        print(f"   Total Items:        {metrics.total_items:,}")
        print(f"   Avg Order Value:    {self.format_currency(metrics.avg_order_value)}")
        print(f"   Avg Items/Order:    {metrics.avg_items_per_order:.1f}")

        print("\n" + "-" * 40)
        print("👥 CUSTOMER METRICS")
        print("-" * 40)
        print(f"   Total Customers:    {metrics.total_customers:,}")
        print(f"   New Customers:      {metrics.new_customers:,}")
        print(f"   Returning:          {metrics.returning_customers:,}")
        print(
            f"   New Customer Rate:  {(metrics.new_customers / metrics.total_customers * 100) if metrics.total_customers > 0 else 0:.1f}%"
        )
        print(f"   Conversion Rate:    {self.format_percent(metrics.conversion_rate)}")

    def show_top_products(
        self, period: SalesPeriod = SalesPeriod.THIS_MONTH, limit: int = 10
    ):
        """Show top selling products."""
        print("\n" + "=" * 80)
        print("🏆 TOP SELLING PRODUCTS")
        print("=" * 80)

        products = self.analytics.get_product_sales(period, limit=limit)

        print(
            f"\n{'#':<3} {'Product':<40} {'Units':<8} {'Revenue':<12} {'Profit':<12} {'Margin':<8}"
        )
        print("-" * 85)

        for i, ps in enumerate(products, 1):
            margin = (ps.profit / ps.revenue * 100) if ps.revenue > 0 else 0
            print(
                f"{i:<3} {ps.product.name[:38]:<40} {ps.units_sold:<8} {self.format_currency(ps.revenue):<12} {self.format_currency(ps.profit):<12} {margin:.1f}%"
            )

    def show_category_breakdown(self, period: SalesPeriod = SalesPeriod.THIS_MONTH):
        """Show category breakdown."""
        print("\n" + "=" * 80)
        print("📁 SALES BY CATEGORY")
        print("=" * 80)

        categories = self.analytics.get_category_sales(period)
        total_revenue = sum(c.total_revenue for c in categories)

        print(
            f"\n{'Category':<30} {'Revenue':<14} {'Share':<10} {'Units':<10} {'Orders':<10} {'AOV':<12}"
        )
        print("-" * 90)

        for cat in categories:
            share = (
                (cat.total_revenue / total_revenue * 100) if total_revenue > 0 else 0
            )
            print(
                f"{cat.category.value[:28]:<30} {self.format_currency(cat.total_revenue):<14} {share:.1f}%{'':5} {cat.total_units:<10} {cat.total_orders:<10} {self.format_currency(cat.avg_order_value):<12}"
            )

    def show_conversion_funnel(self):
        """Show conversion funnel."""
        print("\n" + "=" * 80)
        print("🔻 CONVERSION FUNNEL")
        print("=" * 80)

        funnel = self.analytics.get_conversion_funnel(visitors=15000)

        max_visitors = funnel[0].visitors

        for stage in funnel:
            bar_length = int((stage.visitors / max_visitors) * 40)
            bar = "█" * bar_length + "░" * (40 - bar_length)
            print(f"\n{stage.name:<20}")
            print(f"   [{bar}] {stage.visitors:,}")
            if stage.drop_off_rate > 0:
                print(f"   ↓ {stage.drop_off_rate:.1f}% drop-off")

    def show_period_comparison(
        self,
        current: SalesPeriod = SalesPeriod.THIS_WEEK,
        previous: SalesPeriod = SalesPeriod.LAST_WEEK,
    ):
        """Show period comparison."""
        print("\n" + "=" * 80)
        print(
            f"📈 PERIOD COMPARISON: {current.value.replace('_', ' ').title()} vs {previous.value.replace('_', ' ').title()}"
        )
        print("=" * 80)

        comparison = self.analytics.compare_periods(current, previous)

        print(f"\n{'Metric':<25} {'Current':<15} {'Previous':<15} {'Change':<15}")
        print("-" * 70)

        for metric, data in comparison.items():
            metric_name = metric.replace("_", " ").title()

            if metric in ["revenue", "avg_order_value"]:
                current_val = self.format_currency(data["current"])
                prev_val = self.format_currency(data["previous"])
            else:
                current_val = f"{data['current']:,.0f}"
                prev_val = f"{data['previous']:,.0f}"

            trend = self.format_trend(data["change_percent"])
            print(f"{metric_name:<25} {current_val:<15} {prev_val:<15} {trend:<15}")

    def show_daily_trend(self, days: int = 14):
        """Show daily sales trend."""
        print("\n" + "=" * 80)
        print(f"📊 DAILY SALES TREND (Last {days} Days)")
        print("=" * 80)

        trend = self.analytics.get_daily_trend(days=days)

        max_revenue = max(d["revenue"] for d in trend)

        print(f"\n{'Date':<12} {'Revenue':<12} {'Orders':<8} {'AOV':<10} {'Trend':<40}")
        print("-" * 85)

        for day in trend[-days:]:
            bar_length = (
                int((day["revenue"] / max_revenue) * 30) if max_revenue > 0 else 0
            )
            bar = "▓" * bar_length
            print(
                f"{day['date']:<12} {self.format_currency(day['revenue']):<12} {day['orders']:<8} {self.format_currency(day['avg_order_value']):<10} {bar}"
            )

    def show_hourly_distribution(self, period: SalesPeriod = SalesPeriod.THIS_WEEK):
        """Show hourly order distribution."""
        print("\n" + "=" * 80)
        print("🕐 HOURLY ORDER DISTRIBUTION")
        print("=" * 80)

        hourly = self.analytics.get_hourly_distribution(period)
        max_orders = max(h["orders"] for h in hourly.values())

        print(f"\n{'Hour':<8} {'Orders':<8} {'Revenue':<12} {'Distribution':<40}")
        print("-" * 70)

        for hour in range(24):
            data = hourly[hour]
            bar_length = (
                int((data["orders"] / max_orders) * 30) if max_orders > 0 else 0
            )
            bar = "█" * bar_length
            hour_str = f"{hour:02d}:00"
            print(
                f"{hour_str:<8} {data['orders']:<8} {self.format_currency(data['revenue']):<12} {bar}"
            )

    def show_forecast(self, days: int = 14):
        """Show sales forecast."""
        print("\n" + "=" * 80)
        print(f"🔮 SALES FORECAST (Next {days} Days)")
        print("=" * 80)

        forecasts = self.forecaster.predict_daily_sales(days_ahead=days)

        print(
            f"\n{'Date':<12} {'Day':<10} {'Pred Revenue':<14} {'Pred Orders':<12} {'Confidence Range':<25}"
        )
        print("-" * 80)

        for f in forecasts[:days]:
            day_name = f.date.strftime("%a")
            conf_range = f"({self.format_currency(f.confidence_low)} - {self.format_currency(f.confidence_high)})"
            print(
                f"{f.date.strftime('%Y-%m-%d'):<12} {day_name:<10} {self.format_currency(f.predicted_revenue):<14} {f.predicted_orders:<12} {conf_range:<25}"
            )

        # Summary
        total_predicted = sum(f.predicted_revenue for f in forecasts[:days])
        avg_daily = total_predicted / days if days > 0 else 0

        print("\n" + "-" * 40)
        print(f"   Predicted {days}-Day Total: {self.format_currency(total_predicted)}")
        print(f"   Predicted Daily Average:  {self.format_currency(avg_daily)}")

    def show_opportunities(self):
        """Show identified opportunities."""
        print("\n" + "=" * 80)
        print("💡 SALES OPTIMIZATION OPPORTUNITIES")
        print("=" * 80)

        opportunities = self.forecaster.identify_opportunities()

        for i, opp in enumerate(opportunities, 1):
            impact_icon = (
                "🔴"
                if opp["potential_impact"] == "high"
                else "🟡" if opp["potential_impact"] == "medium" else "🟢"
            )

            print(
                f"\n{impact_icon} Opportunity #{i}: {opp['type'].replace('_', ' ').title()}"
            )
            if "product" in opp:
                print(f"   Product: {opp['product']}")
            if "stage" in opp:
                print(f"   Stage: {opp['stage']}")
            print(f"   Insight: {opp['insight']}")
            print(f"   Recommendation: {opp['recommendation']}")
            print(f"   Impact: {opp['potential_impact'].upper()}")


# =============================================================================
# INTERACTIVE MODE
# =============================================================================


class InteractiveDashboard:
    """Interactive dashboard with menu-driven interface."""

    def __init__(self, dashboard: SalesDashboard):
        """Initialize interactive dashboard."""
        self.dashboard = dashboard
        self.current_period = SalesPeriod.THIS_MONTH

    def show_menu(self):
        """Display main menu."""
        print("\n" + "=" * 60)
        print("📊 SALES DASHBOARD - Interactive Mode")
        print("=" * 60)
        print(
            f"\nCurrent Period: {self.current_period.value.replace('_', ' ').title()}"
        )
        print("\nOptions:")
        print("  1. View Summary Dashboard")
        print("  2. View Top Products")
        print("  3. View Category Breakdown")
        print("  4. View Conversion Funnel")
        print("  5. View Period Comparison")
        print("  6. View Daily Trend")
        print("  7. View Hourly Distribution")
        print("  8. View Sales Forecast")
        print("  9. View Opportunities")
        print(" 10. Change Period")
        print("  0. Exit")
        print("-" * 60)

    def change_period(self):
        """Change analysis period."""
        print("\nSelect Period:")
        for i, period in enumerate(SalesPeriod, 1):
            if period != SalesPeriod.CUSTOM:
                print(f"  {i}. {period.value.replace('_', ' ').title()}")

        try:
            choice = int(input("\nEnter choice: "))
            periods = [p for p in SalesPeriod if p != SalesPeriod.CUSTOM]
            if 1 <= choice <= len(periods):
                self.current_period = periods[choice - 1]
                print(
                    f"\n✓ Period changed to: {self.current_period.value.replace('_', ' ').title()}"
                )
        except (ValueError, IndexError):
            print("\n⚠ Invalid choice")

    def run(self):
        """Run interactive dashboard."""
        while True:
            self.show_menu()

            try:
                choice = input("\nEnter choice: ").strip()

                if choice == "0":
                    print("\n👋 Goodbye!")
                    break
                elif choice == "1":
                    self.dashboard.show_summary(self.current_period)
                elif choice == "2":
                    self.dashboard.show_top_products(self.current_period)
                elif choice == "3":
                    self.dashboard.show_category_breakdown(self.current_period)
                elif choice == "4":
                    self.dashboard.show_conversion_funnel()
                elif choice == "5":
                    if self.current_period == SalesPeriod.THIS_WEEK:
                        self.dashboard.show_period_comparison(
                            SalesPeriod.THIS_WEEK, SalesPeriod.LAST_WEEK
                        )
                    else:
                        self.dashboard.show_period_comparison(
                            SalesPeriod.THIS_MONTH, SalesPeriod.LAST_MONTH
                        )
                elif choice == "6":
                    self.dashboard.show_daily_trend()
                elif choice == "7":
                    self.dashboard.show_hourly_distribution(self.current_period)
                elif choice == "8":
                    self.dashboard.show_forecast()
                elif choice == "9":
                    self.dashboard.show_opportunities()
                elif choice == "10":
                    self.change_period()
                else:
                    print("\n⚠ Invalid choice. Please try again.")

                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")


# =============================================================================
# WOO API CLIENT (MOCK/REAL)
# =============================================================================


class WooCommerceClient:
    """WooCommerce REST API client (mock for demo, real for production)."""

    def __init__(
        self, base_url: str = "", consumer_key: str = "", consumer_secret: str = ""
    ):
        """Initialize WooCommerce client."""
        self.base_url = base_url
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.demo_mode = not (base_url and consumer_key and consumer_secret)

        if self.demo_mode:
            self._generator = DemoDataGenerator()
            self._generator.generate_orders(days=90, base_orders_per_day=30)

    def get_orders(
        self,
        per_page: int = 100,
        page: int = 1,
        after: Optional[str] = None,
        before: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """Get orders from WooCommerce API."""
        if self.demo_mode:
            return [self._order_to_dict(o) for o in self._generator.orders]

        # Real API call would go here
        # endpoint = f"{self.base_url}/wp-json/wc/v3/orders"
        # params = {"per_page": per_page, "page": page}
        # ...
        return []

    def get_products(self, per_page: int = 100, page: int = 1) -> list[dict]:
        """Get products from WooCommerce API."""
        if self.demo_mode:
            return [self._product_to_dict(p) for p in self._generator.products]

        return []

    def get_customers(self, per_page: int = 100, page: int = 1) -> list[dict]:
        """Get customers from WooCommerce API."""
        if self.demo_mode:
            return [self._customer_to_dict(c) for c in self._generator.customers]

        return []

    def _order_to_dict(self, order: Order) -> dict:
        """Convert Order to API-like dict."""
        return {
            "id": order.id,
            "number": order.order_number,
            "status": order.status.value,
            "date_created": order.created_date.isoformat(),
            "date_completed": (
                order.completed_date.isoformat() if order.completed_date else None
            ),
            "total": str(order.total),
            "subtotal": str(order.subtotal),
            "shipping_total": str(order.shipping_cost),
            "discount_total": str(order.discount_total),
            "payment_method": order.payment_method,
            "line_items": [
                {
                    "product_id": item.product.id,
                    "name": item.product.name,
                    "quantity": item.quantity,
                    "subtotal": str(item.line_total),
                    "price": str(item.unit_price),
                }
                for item in order.items
            ],
            "customer": self._customer_to_dict(order.customer),
        }

    def _product_to_dict(self, product: Product) -> dict:
        """Convert Product to API-like dict."""
        return {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "price": str(product.price),
            "regular_price": str(product.price),
            "stock_quantity": product.stock_quantity,
            "categories": [{"name": product.category.value}],
        }

    def _customer_to_dict(self, customer: Customer) -> dict:
        """Convert Customer to API-like dict."""
        return {
            "id": customer.id,
            "email": customer.email,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "billing": {"state": customer.state, "country": customer.country},
            "date_created": customer.created_date.isoformat(),
        }

    def get_demo_orders(self) -> list[Order]:
        """Get raw Order objects for demo mode."""
        if self.demo_mode:
            return self._generator.orders
        return []

    def get_demo_products(self) -> list[Product]:
        """Get raw Product objects for demo mode."""
        if self.demo_mode:
            return self._generator.products
        return []


# =============================================================================
# MAIN APPLICATION
# =============================================================================


def run_demo():
    """Run demo mode with sample data."""
    print("\n🚀 Initializing WooCommerce Sales Dashboard...")
    print("   Generating demo data for electronics store...\n")

    # Initialize client in demo mode
    client = WooCommerceClient()

    # Create analytics engine
    analytics = SalesAnalytics(
        orders=client.get_demo_orders(), products=client.get_demo_products()
    )

    # Create forecaster
    forecaster = SalesForecaster(analytics)

    # Create dashboard
    dashboard = SalesDashboard(analytics, forecaster)

    # Show all dashboard views
    dashboard.show_summary(SalesPeriod.THIS_MONTH)
    dashboard.show_top_products(SalesPeriod.THIS_MONTH, limit=10)
    dashboard.show_category_breakdown(SalesPeriod.THIS_MONTH)
    dashboard.show_conversion_funnel()
    dashboard.show_period_comparison(SalesPeriod.THIS_WEEK, SalesPeriod.LAST_WEEK)
    dashboard.show_daily_trend(days=14)
    dashboard.show_hourly_distribution(SalesPeriod.THIS_WEEK)
    dashboard.show_forecast(days=14)
    dashboard.show_opportunities()

    print("\n" + "=" * 80)
    print("✅ Demo Complete!")
    print("=" * 80)


def run_interactive():
    """Run interactive mode."""
    print("\n🚀 Initializing WooCommerce Sales Dashboard...")
    print("   Loading interactive mode...\n")

    # Initialize client in demo mode
    client = WooCommerceClient()

    # Create analytics engine
    analytics = SalesAnalytics(
        orders=client.get_demo_orders(), products=client.get_demo_products()
    )

    # Create forecaster
    forecaster = SalesForecaster(analytics)

    # Create dashboard
    dashboard = SalesDashboard(analytics, forecaster)

    # Run interactive mode
    interactive = InteractiveDashboard(dashboard)
    interactive.run()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WooCommerce Sales Dashboard - Real-time analytics for electronics retail"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode with sample electronics data",
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive dashboard with menu navigation",
    )

    parser.add_argument(
        "--period",
        type=str,
        choices=[
            "today",
            "yesterday",
            "this_week",
            "last_week",
            "this_month",
            "last_month",
        ],
        default="this_month",
        help="Analysis period (default: this_month)",
    )

    parser.add_argument("--forecast", action="store_true", help="Show sales forecast")

    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days for forecast or trend (default: 14)",
    )

    parser.add_argument(
        "--top-products", type=int, metavar="N", help="Show top N products"
    )

    parser.add_argument(
        "--export", type=str, metavar="FILE", help="Export metrics to JSON file"
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.interactive:
        run_interactive()
    else:
        # Quick view mode
        client = WooCommerceClient()
        analytics = SalesAnalytics(
            orders=client.get_demo_orders(), products=client.get_demo_products()
        )
        forecaster = SalesForecaster(analytics)
        dashboard = SalesDashboard(analytics, forecaster)

        period = SalesPeriod(args.period)

        if args.forecast:
            dashboard.show_forecast(days=args.days)
        elif args.top_products:
            dashboard.show_top_products(period, limit=args.top_products)
        else:
            dashboard.show_summary(period)

        if args.export:
            metrics = analytics.calculate_metrics(period, visitors=15000)
            export_data = {
                "period": period.value,
                "generated_at": datetime.now().isoformat(),
                "metrics": {
                    "total_revenue": metrics.total_revenue,
                    "total_orders": metrics.total_orders,
                    "avg_order_value": metrics.avg_order_value,
                    "total_customers": metrics.total_customers,
                    "new_customers": metrics.new_customers,
                    "profit_margin": metrics.profit_margin,
                },
            }
            with open(args.export, "w") as f:
                json.dump(export_data, f, indent=2)
            print(f"\n✅ Metrics exported to {args.export}")


if __name__ == "__main__":
    main()
