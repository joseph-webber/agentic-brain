#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WooCommerce Marketing Automation - Example 80

Automated marketing campaigns, customer engagement, and promotional tools.

Features:
- Abandoned cart recovery automation
- Email campaign management
- Customer segmentation engine
- Promotional code generation
- Flash sale automation
- Re-engagement campaigns
- Birthday/anniversary offers
- Loyalty program integration

Usage:
    python 80_woo_marketing_automation.py --demo
    python 80_woo_marketing_automation.py --interactive
    python 80_woo_marketing_automation.py --campaign abandoned-cart
    python 80_woo_marketing_automation.py --generate-coupons 10
"""

import argparse
import hashlib
import json
import random
import re
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

# =============================================================================
# DOMAIN MODELS
# =============================================================================


class CampaignType(Enum):
    """Marketing campaign types."""

    ABANDONED_CART = "abandoned_cart"
    WELCOME_SERIES = "welcome_series"
    POST_PURCHASE = "post_purchase"
    RE_ENGAGEMENT = "re_engagement"
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    FLASH_SALE = "flash_sale"
    SEASONAL = "seasonal"
    LOYALTY = "loyalty"
    WIN_BACK = "win_back"
    CROSS_SELL = "cross_sell"
    UPSELL = "upsell"


class CampaignStatus(Enum):
    """Campaign lifecycle status."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CustomerSegment(Enum):
    """Customer segmentation categories."""

    NEW_CUSTOMER = "new_customer"
    REPEAT_BUYER = "repeat_buyer"
    VIP = "vip"
    AT_RISK = "at_risk"
    CHURNED = "churned"
    HIGH_VALUE = "high_value"
    BARGAIN_HUNTER = "bargain_hunter"
    TECH_ENTHUSIAST = "tech_enthusiast"
    CASUAL_BUYER = "casual_buyer"
    LOYAL = "loyal"


class EmailStatus(Enum):
    """Email delivery status."""

    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    SPAM = "spam"


class CouponType(Enum):
    """Coupon discount types."""

    PERCENT = "percent"
    FIXED_CART = "fixed_cart"
    FIXED_PRODUCT = "fixed_product"
    FREE_SHIPPING = "free_shipping"
    BUY_X_GET_Y = "buy_x_get_y"


class TriggerType(Enum):
    """Automation trigger types."""

    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    SEGMENT_ENTRY = "segment_entry"
    SEGMENT_EXIT = "segment_exit"
    CART_ABANDONMENT = "cart_abandonment"
    PURCHASE_COMPLETE = "purchase_complete"
    PRODUCT_VIEW = "product_view"
    WISHLIST_ADD = "wishlist_add"
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"


@dataclass
class Customer:
    """Customer profile for marketing."""

    id: int
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    created_date: datetime
    last_order_date: Optional[datetime]
    total_orders: int
    total_spent: float
    avg_order_value: float
    segments: list[CustomerSegment] = field(default_factory=list)
    birthday: Optional[datetime] = None
    anniversary: Optional[datetime] = None  # First purchase date
    email_opt_in: bool = True
    sms_opt_in: bool = False
    loyalty_points: int = 0
    loyalty_tier: str = "Bronze"
    tags: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def days_since_last_order(self) -> int:
        if self.last_order_date:
            return (datetime.now() - self.last_order_date).days
        return 999


@dataclass
class CartItem:
    """Item in shopping cart."""

    product_id: int
    product_name: str
    sku: str
    quantity: int
    price: float
    image_url: str = ""

    @property
    def total(self) -> float:
        return self.price * self.quantity


@dataclass
class AbandonedCart:
    """Abandoned shopping cart."""

    id: str
    customer: Customer
    items: list[CartItem]
    created_at: datetime
    last_activity: datetime
    recovery_emails_sent: int = 0
    recovered: bool = False
    recovery_order_id: Optional[int] = None
    recovery_coupon: Optional[str] = None

    @property
    def total_value(self) -> float:
        return sum(item.total for item in self.items)

    @property
    def hours_since_abandonment(self) -> float:
        return (datetime.now() - self.last_activity).total_seconds() / 3600


@dataclass
class Coupon:
    """Promotional coupon."""

    code: str
    description: str
    discount_type: CouponType
    amount: float
    minimum_spend: float = 0.0
    maximum_discount: Optional[float] = None
    usage_limit: Optional[int] = None
    usage_count: int = 0
    individual_use: bool = True
    exclude_sale_items: bool = False
    product_ids: list[int] = field(default_factory=list)
    category_ids: list[int] = field(default_factory=list)
    excluded_product_ids: list[int] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    customer_emails: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        now = datetime.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False
        return self.is_active


@dataclass
class EmailTemplate:
    """Email template for campaigns."""

    id: str
    name: str
    subject: str
    preview_text: str
    html_content: str
    text_content: str
    campaign_type: CampaignType
    variables: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class EmailMessage:
    """Email message instance."""

    id: str
    template_id: str
    customer: Customer
    subject: str
    content: str
    status: EmailStatus = EmailStatus.QUEUED
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    campaign_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Campaign:
    """Marketing campaign."""

    id: str
    name: str
    campaign_type: CampaignType
    status: CampaignStatus
    description: str
    target_segments: list[CustomerSegment]
    trigger_type: TriggerType
    trigger_conditions: dict
    email_sequence: list[dict]  # List of {delay_hours, template_id}
    coupon_code: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    # Metrics
    emails_sent: int = 0
    emails_opened: int = 0
    emails_clicked: int = 0
    conversions: int = 0
    revenue_generated: float = 0.0

    @property
    def open_rate(self) -> float:
        return (
            (self.emails_opened / self.emails_sent * 100) if self.emails_sent > 0 else 0
        )

    @property
    def click_rate(self) -> float:
        return (
            (self.emails_clicked / self.emails_sent * 100)
            if self.emails_sent > 0
            else 0
        )

    @property
    def conversion_rate(self) -> float:
        return (
            (self.conversions / self.emails_clicked * 100)
            if self.emails_clicked > 0
            else 0
        )


@dataclass
class FlashSale:
    """Flash sale configuration."""

    id: str
    name: str
    description: str
    discount_percent: float
    product_ids: list[int]
    category_ids: list[int]
    start_time: datetime
    end_time: datetime
    max_redemptions: Optional[int] = None
    redemptions: int = 0
    notify_customers: bool = True
    landing_page_url: str = ""
    countdown_enabled: bool = True

    @property
    def is_active(self) -> bool:
        now = datetime.now()
        return self.start_time <= now <= self.end_time

    @property
    def hours_remaining(self) -> float:
        if not self.is_active:
            return 0
        return max(0, (self.end_time - datetime.now()).total_seconds() / 3600)


@dataclass
class LoyaltyTier:
    """Loyalty program tier."""

    name: str
    min_points: int
    max_points: Optional[int]
    benefits: list[str]
    points_multiplier: float
    exclusive_sales: bool
    free_shipping: bool
    birthday_bonus: int


@dataclass
class LoyaltyProgram:
    """Loyalty program configuration."""

    name: str
    points_per_dollar: int
    tiers: list[LoyaltyTier]
    points_expiry_months: int
    referral_bonus: int
    review_bonus: int
    birthday_bonus: int


# =============================================================================
# DEMO DATA GENERATOR
# =============================================================================


class DemoDataGenerator:
    """Generate realistic demo data for marketing automation."""

    FIRST_NAMES = [
        "Emma",
        "Oliver",
        "Charlotte",
        "James",
        "Amelia",
        "William",
        "Mia",
        "Benjamin",
        "Harper",
        "Elijah",
        "Evelyn",
        "Lucas",
        "Abigail",
        "Mason",
        "Emily",
        "Logan",
        "Elizabeth",
        "Alexander",
        "Sofia",
        "Ethan",
        "Avery",
        "Jacob",
        "Ella",
        "Michael",
        "Madison",
        "Daniel",
        "Scarlett",
        "Henry",
    ]

    LAST_NAMES = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
        "Wilson",
        "Anderson",
        "Taylor",
        "Thomas",
        "Hernandez",
        "Moore",
        "Martin",
        "Jackson",
        "Thompson",
        "White",
    ]

    ELECTRONICS_PRODUCTS = [
        {
            "id": 1001,
            "name": "Smartphone Pro 15 256GB",
            "sku": "SP-IP15-256",
            "price": 1699,
        },
        {
            "id": 1002,
            "name": "MacBook Pro 14-inch M3",
            "sku": "LP-MBP-14",
            "price": 3199,
        },
        {"id": 1003, "name": "AirPods Pro 2nd Gen", "sku": "AU-APPPRO2", "price": 399},
        {"id": 1004, "name": "iPad Air 10.9-inch", "sku": "TB-IPADAIR", "price": 929},
        {"id": 1005, "name": "Apple Watch Series 9", "sku": "WR-AW9-45", "price": 649},
        {"id": 1006, "name": "Sony WH-1000XM5", "sku": "AU-SONYWH", "price": 549},
        {"id": 1007, "name": "PlayStation 5 Console", "sku": "GM-PS5", "price": 799},
        {
            "id": 1008,
            "name": "Samsung Galaxy Tab S9",
            "sku": "TB-SAMSUNGS9",
            "price": 1199,
        },
        {"id": 1009, "name": "GoPro HERO12 Black", "sku": "CM-GOPRO", "price": 649},
        {"id": 1010, "name": "Nintendo Switch OLED", "sku": "GM-SWITCH", "price": 539},
        {
            "id": 1011,
            "name": "Bose QuietComfort Ultra",
            "sku": "AU-BOSEQC",
            "price": 649,
        },
        {"id": 1012, "name": "USB-C Hub 7-in-1", "sku": "AC-USBHUB", "price": 89},
        {"id": 1013, "name": "MagSafe Charger", "sku": "CC-MAGSAFE", "price": 59},
        {"id": 1014, "name": "Power Bank 20000mAh", "sku": "CC-POWERBNK", "price": 79},
        {
            "id": 1015,
            "name": "Wireless Charging Pad",
            "sku": "CC-WIRELESS",
            "price": 49,
        },
    ]

    def __init__(self, seed: int = 42):
        """Initialize generator."""
        random.seed(seed)
        self._customer_id = 5000
        self._cart_id = 0

    def create_customer(self, segments: list[CustomerSegment] = None) -> Customer:
        """Create a random customer."""
        self._customer_id += 1

        created_date = datetime.now() - timedelta(days=random.randint(1, 730))
        last_order = created_date + timedelta(
            days=random.randint(1, (datetime.now() - created_date).days or 1)
        )

        total_orders = random.randint(1, 20)
        total_spent = random.uniform(100, 5000) * (total_orders / 5)

        # Determine segments based on behavior
        if segments is None:
            segments = []
            if total_orders == 1:
                segments.append(CustomerSegment.NEW_CUSTOMER)
            elif total_orders >= 5:
                segments.append(CustomerSegment.REPEAT_BUYER)

            if total_spent > 2000:
                segments.append(CustomerSegment.HIGH_VALUE)
            if total_spent > 5000:
                segments.append(CustomerSegment.VIP)

            if (datetime.now() - last_order).days > 90:
                segments.append(CustomerSegment.AT_RISK)
            if (datetime.now() - last_order).days > 180:
                segments.append(CustomerSegment.CHURNED)

        # Loyalty tier based on spend
        if total_spent > 5000:
            loyalty_tier = "Platinum"
            loyalty_points = int(total_spent * 2)
        elif total_spent > 2000:
            loyalty_tier = "Gold"
            loyalty_points = int(total_spent * 1.5)
        elif total_spent > 500:
            loyalty_tier = "Silver"
            loyalty_points = int(total_spent * 1.2)
        else:
            loyalty_tier = "Bronze"
            loyalty_points = int(total_spent)

        # Random birthday (adult)
        birth_year = datetime.now().year - random.randint(25, 65)
        birthday = datetime(birth_year, random.randint(1, 12), random.randint(1, 28))

        return Customer(
            id=self._customer_id,
            email=f"{random.choice(self.FIRST_NAMES).lower()}.{random.choice(self.LAST_NAMES).lower()}{random.randint(1, 999)}@email.com",
            first_name=random.choice(self.FIRST_NAMES),
            last_name=random.choice(self.LAST_NAMES),
            phone=f"+61 4{random.randint(10, 99)} {random.randint(100, 999)} {random.randint(100, 999)}",
            created_date=created_date,
            last_order_date=last_order,
            total_orders=total_orders,
            total_spent=total_spent,
            avg_order_value=total_spent / total_orders,
            segments=segments,
            birthday=birthday,
            anniversary=created_date,
            email_opt_in=random.random() < 0.85,
            sms_opt_in=random.random() < 0.40,
            loyalty_points=loyalty_points,
            loyalty_tier=loyalty_tier,
            tags=random.sample(
                ["early_adopter", "deal_hunter", "premium", "mobile_shopper"],
                k=random.randint(0, 2),
            ),
        )

    def create_abandoned_cart(self, customer: Customer = None) -> AbandonedCart:
        """Create an abandoned cart."""
        self._cart_id += 1

        if customer is None:
            customer = self.create_customer()

        # Random cart items
        num_items = random.randint(1, 4)
        products = random.sample(self.ELECTRONICS_PRODUCTS, num_items)

        items = []
        for prod in products:
            items.append(
                CartItem(
                    product_id=prod["id"],
                    product_name=prod["name"],
                    sku=prod["sku"],
                    quantity=random.randint(1, 2),
                    price=prod["price"],
                    image_url=f"https://store.example.com/images/{prod['sku']}.jpg",
                )
            )

        # Random abandonment time (1-72 hours ago)
        hours_ago = random.uniform(1, 72)
        abandoned_at = datetime.now() - timedelta(hours=hours_ago)

        return AbandonedCart(
            id=f"CART-{self._cart_id:05d}",
            customer=customer,
            items=items,
            created_at=abandoned_at - timedelta(hours=random.uniform(0.5, 2)),
            last_activity=abandoned_at,
            recovery_emails_sent=0,
            recovered=False,
        )

    def create_customers(self, count: int = 100) -> list[Customer]:
        """Create multiple customers."""
        return [self.create_customer() for _ in range(count)]

    def create_abandoned_carts(
        self, customers: list[Customer], count: int = 20
    ) -> list[AbandonedCart]:
        """Create abandoned carts for random customers."""
        carts = []
        selected_customers = random.sample(customers, min(count, len(customers)))
        for customer in selected_customers:
            carts.append(self.create_abandoned_cart(customer))
        return carts


# =============================================================================
# COUPON GENERATOR
# =============================================================================


class CouponGenerator:
    """Generate promotional coupons."""

    def __init__(self):
        """Initialize generator."""
        self.generated_codes = set()

    def generate_code(
        self,
        prefix: str = "",
        length: int = 8,
        include_numbers: bool = True,
        uppercase: bool = True,
    ) -> str:
        """Generate a unique coupon code."""
        chars = string.ascii_uppercase if uppercase else string.ascii_letters
        if include_numbers:
            chars += string.digits

        while True:
            code = prefix + "".join(random.choices(chars, k=length))
            if code not in self.generated_codes:
                self.generated_codes.add(code)
                return code

    def generate_percent_coupon(
        self,
        discount: float,
        prefix: str = "SAVE",
        minimum_spend: float = 0,
        usage_limit: int = None,
        valid_days: int = 30,
    ) -> Coupon:
        """Generate a percentage discount coupon."""
        code = self.generate_code(prefix=prefix)

        return Coupon(
            code=code,
            description=f"{discount}% off your order",
            discount_type=CouponType.PERCENT,
            amount=discount,
            minimum_spend=minimum_spend,
            maximum_discount=500,  # Cap the discount
            usage_limit=usage_limit,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=valid_days),
        )

    def generate_fixed_coupon(
        self,
        amount: float,
        prefix: str = "OFF",
        minimum_spend: float = 0,
        valid_days: int = 30,
    ) -> Coupon:
        """Generate a fixed amount discount coupon."""
        code = self.generate_code(prefix=prefix)

        return Coupon(
            code=code,
            description=f"${amount:.0f} off your order",
            discount_type=CouponType.FIXED_CART,
            amount=amount,
            minimum_spend=minimum_spend,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=valid_days),
        )

    def generate_free_shipping_coupon(
        self, prefix: str = "SHIP", minimum_spend: float = 50, valid_days: int = 14
    ) -> Coupon:
        """Generate a free shipping coupon."""
        code = self.generate_code(prefix=prefix)

        return Coupon(
            code=code,
            description="Free shipping on your order",
            discount_type=CouponType.FREE_SHIPPING,
            amount=0,
            minimum_spend=minimum_spend,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=valid_days),
        )

    def generate_cart_recovery_coupon(
        self, cart: AbandonedCart, discount: float = 10, valid_hours: int = 48
    ) -> Coupon:
        """Generate a personalized cart recovery coupon."""
        # Create unique code with customer hash
        customer_hash = (
            hashlib.md5(cart.customer.email.encode()).hexdigest()[:4].upper()
        )
        code = f"SAVE{int(discount)}-{customer_hash}-{cart.id[-4:]}"

        return Coupon(
            code=code,
            description=f"{discount}% off to complete your order",
            discount_type=CouponType.PERCENT,
            amount=discount,
            minimum_spend=cart.total_value * 0.5,  # At least half the cart value
            usage_limit=1,
            individual_use=True,
            customer_emails=[cart.customer.email],
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(hours=valid_hours),
        )

    def generate_birthday_coupon(
        self, customer: Customer, discount: float = 20, valid_days: int = 30
    ) -> Coupon:
        """Generate a birthday coupon for customer."""
        code = f"BDAY{int(discount)}-{customer.id}"

        return Coupon(
            code=code,
            description=f"Happy Birthday! {discount}% off your order",
            discount_type=CouponType.PERCENT,
            amount=discount,
            minimum_spend=50,
            usage_limit=1,
            customer_emails=[customer.email],
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=valid_days),
        )

    def generate_loyalty_coupon(
        self, customer: Customer, tier: str, discount: float = None
    ) -> Coupon:
        """Generate a loyalty tier coupon."""
        tier_discounts = {"Bronze": 5, "Silver": 10, "Gold": 15, "Platinum": 20}
        if discount is None:
            discount = tier_discounts.get(tier, 5)

        code = f"LOYAL{tier[:3].upper()}{customer.id}"

        return Coupon(
            code=code,
            description=f"{tier} member exclusive: {discount}% off",
            discount_type=CouponType.PERCENT,
            amount=discount,
            minimum_spend=100,
            usage_limit=1,
            customer_emails=[customer.email],
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=60),
        )

    def generate_batch(
        self,
        count: int,
        coupon_type: str = "percent",
        discount: float = 10,
        prefix: str = "PROMO",
    ) -> list[Coupon]:
        """Generate a batch of coupons."""
        coupons = []
        for _i in range(count):
            if coupon_type == "percent":
                coupon = self.generate_percent_coupon(discount, prefix=prefix)
            elif coupon_type == "fixed":
                coupon = self.generate_fixed_coupon(discount, prefix=prefix)
            else:
                coupon = self.generate_free_shipping_coupon(prefix=prefix)
            coupons.append(coupon)
        return coupons


# =============================================================================
# EMAIL TEMPLATE ENGINE
# =============================================================================


class EmailTemplateEngine:
    """Manage email templates and content generation."""

    def __init__(self):
        """Initialize template engine."""
        self.templates: dict[str, EmailTemplate] = {}
        self._load_default_templates()

    def _load_default_templates(self):
        """Load default email templates."""

        # Abandoned Cart Recovery - Email 1 (1 hour)
        self.templates["cart_recovery_1"] = EmailTemplate(
            id="cart_recovery_1",
            name="Abandoned Cart - First Reminder",
            subject="Did you forget something, {{first_name}}?",
            preview_text="Your cart is waiting for you",
            html_content="""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">Hi {{first_name}},</h2>
    <p>We noticed you left some great items in your cart!</p>

    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h3>Your Cart Contains:</h3>
        {{cart_items}}
        <hr>
        <p style="font-size: 18px;"><strong>Total: {{cart_total}}</strong></p>
    </div>

    <a href="{{checkout_url}}" style="display: inline-block; background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
        Complete Your Purchase
    </a>

    <p style="color: #666; margin-top: 20px;">
        Need help? Reply to this email and our team will assist you.
    </p>
</body>
</html>
            """,
            text_content="""
Hi {{first_name}},

We noticed you left some items in your cart!

Your Cart:
{{cart_items_text}}

Total: {{cart_total}}

Complete your purchase: {{checkout_url}}

Need help? Reply to this email.
            """,
            campaign_type=CampaignType.ABANDONED_CART,
            variables=["first_name", "cart_items", "cart_total", "checkout_url"],
        )

        # Abandoned Cart Recovery - Email 2 (24 hours)
        self.templates["cart_recovery_2"] = EmailTemplate(
            id="cart_recovery_2",
            name="Abandoned Cart - With Incentive",
            subject="{{first_name}}, here's {{discount}}% off to complete your order!",
            preview_text="Limited time offer on your cart items",
            html_content="""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #ff6b35; color: white; padding: 20px; text-align: center; border-radius: 8px;">
        <h1>{{discount}}% OFF</h1>
        <p>Use code: <strong>{{coupon_code}}</strong></p>
    </div>

    <h2 style="color: #333; margin-top: 30px;">Hi {{first_name}},</h2>
    <p>Your cart is still waiting, and we want to help you save!</p>

    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
        {{cart_items}}
        <hr>
        <p><s style="color: #999;">Original: {{cart_total}}</s></p>
        <p style="font-size: 20px; color: #28a745;"><strong>With code: {{discounted_total}}</strong></p>
    </div>

    <a href="{{checkout_url}}?coupon={{coupon_code}}" style="display: inline-block; background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
        Claim Your {{discount}}% Discount
    </a>

    <p style="color: #dc3545; margin-top: 20px;">
        ⏰ Offer expires in 48 hours!
    </p>
</body>
</html>
            """,
            text_content="""
{{discount}}% OFF YOUR ORDER!

Use code: {{coupon_code}}

Hi {{first_name}},

Your cart is still waiting, and we want to help you save!

Your Cart:
{{cart_items_text}}

Original: {{cart_total}}
With discount: {{discounted_total}}

Claim your discount: {{checkout_url}}?coupon={{coupon_code}}

Offer expires in 48 hours!
            """,
            campaign_type=CampaignType.ABANDONED_CART,
            variables=[
                "first_name",
                "discount",
                "coupon_code",
                "cart_items",
                "cart_total",
                "discounted_total",
                "checkout_url",
            ],
        )

        # Welcome Series - Email 1
        self.templates["welcome_1"] = EmailTemplate(
            id="welcome_1",
            name="Welcome - First Email",
            subject="Welcome to ElectroTech, {{first_name}}! 🎉",
            preview_text="Your exclusive welcome offer inside",
            html_content="""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h1 style="color: #007bff;">Welcome to ElectroTech!</h1>

    <p>Hi {{first_name}},</p>
    <p>Thanks for joining our community of tech enthusiasts!</p>

    <div style="background: #f0f7ff; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
        <h2>Your Welcome Gift</h2>
        <p style="font-size: 24px;"><strong>{{discount}}% OFF</strong></p>
        <p>Use code: <strong>{{coupon_code}}</strong></p>
    </div>

    <h3>Why Shop With Us?</h3>
    <ul>
        <li>✅ Genuine products with warranty</li>
        <li>✅ Free shipping on orders over $150</li>
        <li>✅ 30-day easy returns</li>
        <li>✅ Expert customer support</li>
    </ul>

    <a href="{{shop_url}}" style="display: inline-block; background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
        Start Shopping
    </a>
</body>
</html>
            """,
            text_content="""
Welcome to ElectroTech, {{first_name}}!

Thanks for joining our community!

YOUR WELCOME GIFT: {{discount}}% OFF
Use code: {{coupon_code}}

Why Shop With Us?
- Genuine products with warranty
- Free shipping on orders over $150
- 30-day easy returns
- Expert customer support

Start shopping: {{shop_url}}
            """,
            campaign_type=CampaignType.WELCOME_SERIES,
            variables=["first_name", "discount", "coupon_code", "shop_url"],
        )

        # Birthday Email
        self.templates["birthday"] = EmailTemplate(
            id="birthday",
            name="Birthday Celebration",
            subject="🎂 Happy Birthday, {{first_name}}! Here's a gift for you",
            preview_text="Celebrate with {{discount}}% off",
            html_content="""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; text-align: center;">
    <h1 style="font-size: 48px;">🎂</h1>
    <h1 style="color: #e91e63;">Happy Birthday, {{first_name}}!</h1>

    <p>It's your special day, and we're celebrating YOU!</p>

    <div style="background: linear-gradient(135deg, #e91e63, #ff9800); color: white; padding: 30px; border-radius: 12px; margin: 20px 0;">
        <h2>YOUR BIRTHDAY GIFT</h2>
        <p style="font-size: 36px; margin: 10px 0;"><strong>{{discount}}% OFF</strong></p>
        <p>Everything in store!</p>
        <p style="font-size: 20px;">Code: <strong>{{coupon_code}}</strong></p>
    </div>

    <p>Valid for the next 30 days - treat yourself! 🎁</p>

    <a href="{{shop_url}}" style="display: inline-block; background: #e91e63; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0;">
        Shop Your Birthday Sale
    </a>

    <p style="color: #666;">From your friends at ElectroTech</p>
</body>
</html>
            """,
            text_content="""
🎂 Happy Birthday, {{first_name}}!

It's your special day, and we're celebrating YOU!

YOUR BIRTHDAY GIFT: {{discount}}% OFF everything!
Code: {{coupon_code}}

Valid for 30 days - treat yourself!

Shop now: {{shop_url}}

From your friends at ElectroTech
            """,
            campaign_type=CampaignType.BIRTHDAY,
            variables=["first_name", "discount", "coupon_code", "shop_url"],
        )

        # Flash Sale Announcement
        self.templates["flash_sale"] = EmailTemplate(
            id="flash_sale",
            name="Flash Sale Alert",
            subject="⚡ FLASH SALE: {{discount}}% off for {{hours}} hours only!",
            preview_text="Don't miss these limited-time deals",
            html_content="""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #ff0000; color: white; padding: 20px; text-align: center;">
        <h1>⚡ FLASH SALE ⚡</h1>
        <p style="font-size: 24px;"><strong>{{discount}}% OFF</strong></p>
        <p>Ends in {{hours}} hours!</p>
    </div>

    <p style="margin-top: 20px;">Hi {{first_name}},</p>
    <p>The clock is ticking! Get {{discount}}% off select electronics right now.</p>

    <h3>Featured Deals:</h3>
    {{featured_products}}

    <div style="text-align: center; margin: 30px 0;">
        <a href="{{sale_url}}" style="display: inline-block; background: #ff0000; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-size: 18px;">
            SHOP THE SALE
        </a>
    </div>

    <p style="color: #dc3545; font-weight: bold;">
        ⏰ Sale ends: {{end_time}}
    </p>
</body>
</html>
            """,
            text_content="""
⚡ FLASH SALE - {{discount}}% OFF ⚡

Ends in {{hours}} hours!

Hi {{first_name}},

The clock is ticking! Get {{discount}}% off select electronics.

Shop now: {{sale_url}}

Sale ends: {{end_time}}
            """,
            campaign_type=CampaignType.FLASH_SALE,
            variables=[
                "first_name",
                "discount",
                "hours",
                "featured_products",
                "sale_url",
                "end_time",
            ],
        )

        # Re-engagement Campaign
        self.templates["reengagement"] = EmailTemplate(
            id="reengagement",
            name="We Miss You",
            subject="We miss you, {{first_name}}! Here's {{discount}}% off to welcome you back",
            preview_text="It's been a while - come back and save",
            html_content="""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">Hi {{first_name}},</h2>

    <p>It's been {{days_since}} days since your last visit, and we miss you!</p>

    <div style="background: #007bff; color: white; padding: 25px; border-radius: 8px; margin: 20px 0; text-align: center;">
        <h2>WELCOME BACK OFFER</h2>
        <p style="font-size: 32px; margin: 10px 0;"><strong>{{discount}}% OFF</strong></p>
        <p>Your entire order</p>
        <p style="font-size: 18px;">Code: <strong>{{coupon_code}}</strong></p>
    </div>

    <h3>What's New?</h3>
    <ul>
        <li>🆕 Latest smartphones and tablets</li>
        <li>🎧 New audio gear</li>
        <li>🎮 Gaming essentials</li>
        <li>📱 Must-have accessories</li>
    </ul>

    <a href="{{shop_url}}" style="display: inline-block; background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
        Explore What's New
    </a>

    <p style="margin-top: 20px; color: #666;">
        Offer valid for 14 days.
    </p>
</body>
</html>
            """,
            text_content="""
Hi {{first_name}},

It's been {{days_since}} days since your last visit, and we miss you!

WELCOME BACK: {{discount}}% OFF your order
Code: {{coupon_code}}

What's New?
- Latest smartphones and tablets
- New audio gear
- Gaming essentials
- Must-have accessories

Shop now: {{shop_url}}

Offer valid for 14 days.
            """,
            campaign_type=CampaignType.RE_ENGAGEMENT,
            variables=[
                "first_name",
                "days_since",
                "discount",
                "coupon_code",
                "shop_url",
            ],
        )

    def render_template(
        self, template_id: str, variables: dict[str, Any], use_html: bool = True
    ) -> str:
        """Render a template with variables."""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        content = template.html_content if use_html else template.text_content

        # Replace variables
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            content = content.replace(placeholder, str(value))

        return content

    def render_subject(self, template_id: str, variables: dict[str, Any]) -> str:
        """Render template subject line."""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        subject = template.subject
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            subject = subject.replace(placeholder, str(value))

        return subject

    def get_template(self, template_id: str) -> Optional[EmailTemplate]:
        """Get a template by ID."""
        return self.templates.get(template_id)

    def list_templates(self, campaign_type: CampaignType = None) -> list[EmailTemplate]:
        """List all templates, optionally filtered by campaign type."""
        templates = list(self.templates.values())
        if campaign_type:
            templates = [t for t in templates if t.campaign_type == campaign_type]
        return templates


# =============================================================================
# SEGMENTATION ENGINE
# =============================================================================


class SegmentationEngine:
    """Customer segmentation and targeting."""

    def __init__(self):
        """Initialize segmentation rules."""
        self.segment_rules: dict[CustomerSegment, Callable[[Customer], bool]] = {
            CustomerSegment.NEW_CUSTOMER: lambda c: c.total_orders == 1,
            CustomerSegment.REPEAT_BUYER: lambda c: c.total_orders >= 3,
            CustomerSegment.VIP: lambda c: c.total_spent > 5000 or c.total_orders >= 10,
            CustomerSegment.AT_RISK: lambda c: 60 < c.days_since_last_order <= 120,
            CustomerSegment.CHURNED: lambda c: c.days_since_last_order > 180,
            CustomerSegment.HIGH_VALUE: lambda c: c.avg_order_value > 500,
            CustomerSegment.BARGAIN_HUNTER: lambda c: "deal_hunter" in c.tags,
            CustomerSegment.LOYAL: lambda c: c.total_orders >= 5
            and c.days_since_last_order < 60,
            CustomerSegment.CASUAL_BUYER: lambda c: c.total_orders < 3
            and c.avg_order_value < 200,
        }

    def segment_customer(self, customer: Customer) -> list[CustomerSegment]:
        """Determine all applicable segments for a customer."""
        segments = []
        for segment, rule in self.segment_rules.items():
            try:
                if rule(customer):
                    segments.append(segment)
            except Exception:
                pass
        return segments

    def get_segment_customers(
        self, customers: list[Customer], segment: CustomerSegment
    ) -> list[Customer]:
        """Get all customers in a segment."""
        rule = self.segment_rules.get(segment)
        if not rule:
            return []
        return [c for c in customers if rule(c)]

    def analyze_segments(
        self, customers: list[Customer]
    ) -> dict[CustomerSegment, dict]:
        """Analyze segment distribution and metrics."""
        analysis = {}

        for segment in CustomerSegment:
            segment_customers = self.get_segment_customers(customers, segment)

            if segment_customers:
                total_revenue = sum(c.total_spent for c in segment_customers)
                avg_orders = sum(c.total_orders for c in segment_customers) / len(
                    segment_customers
                )
                avg_value = total_revenue / len(segment_customers)

                analysis[segment] = {
                    "count": len(segment_customers),
                    "percentage": len(segment_customers) / len(customers) * 100,
                    "total_revenue": total_revenue,
                    "avg_orders": avg_orders,
                    "avg_customer_value": avg_value,
                    "email_opt_in": sum(1 for c in segment_customers if c.email_opt_in),
                }
            else:
                analysis[segment] = {
                    "count": 0,
                    "percentage": 0,
                    "total_revenue": 0,
                    "avg_orders": 0,
                    "avg_customer_value": 0,
                    "email_opt_in": 0,
                }

        return analysis


# =============================================================================
# ABANDONED CART RECOVERY
# =============================================================================


class AbandonedCartRecovery:
    """Automated abandoned cart recovery system."""

    def __init__(
        self, coupon_generator: CouponGenerator, template_engine: EmailTemplateEngine
    ):
        """Initialize recovery system."""
        self.coupon_generator = coupon_generator
        self.template_engine = template_engine

        # Recovery email schedule (hours after abandonment, template, discount)
        self.recovery_schedule = [
            {"hours": 1, "template": "cart_recovery_1", "discount": 0},
            {"hours": 24, "template": "cart_recovery_2", "discount": 10},
            {"hours": 72, "template": "cart_recovery_2", "discount": 15},
        ]

        self.sent_emails: list[EmailMessage] = []

    def get_recoverable_carts(
        self, carts: list[AbandonedCart], max_age_hours: int = 168  # 7 days
    ) -> list[AbandonedCart]:
        """Get carts eligible for recovery emails."""
        recoverable = []

        for cart in carts:
            if cart.recovered:
                continue
            if not cart.customer.email_opt_in:
                continue
            if cart.hours_since_abandonment > max_age_hours:
                continue

            # Check if next email is due
            next_email_index = cart.recovery_emails_sent
            if next_email_index >= len(self.recovery_schedule):
                continue

            schedule = self.recovery_schedule[next_email_index]
            if cart.hours_since_abandonment >= schedule["hours"]:
                recoverable.append(cart)

        return recoverable

    def format_cart_items(self, items: list[CartItem], html: bool = True) -> str:
        """Format cart items for email."""
        if html:
            rows = []
            for item in items:
                rows.append(
                    f"""
                <div style="display: flex; margin: 10px 0; padding: 10px; border: 1px solid #eee; border-radius: 4px;">
                    <div style="flex: 1;">
                        <strong>{item.product_name}</strong><br>
                        <small>SKU: {item.sku}</small>
                    </div>
                    <div style="text-align: right;">
                        <span>Qty: {item.quantity}</span><br>
                        <strong>${item.total:.2f}</strong>
                    </div>
                </div>
                """
                )
            return "\n".join(rows)
        else:
            lines = []
            for item in items:
                lines.append(
                    f"- {item.product_name} x{item.quantity}: ${item.total:.2f}"
                )
            return "\n".join(lines)

    def prepare_recovery_email(
        self, cart: AbandonedCart
    ) -> tuple[EmailMessage, Optional[Coupon]]:
        """Prepare a recovery email for a cart."""
        email_index = cart.recovery_emails_sent
        schedule = self.recovery_schedule[email_index]

        template_id = schedule["template"]
        discount = schedule["discount"]

        # Generate coupon if discount > 0
        coupon = None
        if discount > 0:
            coupon = self.coupon_generator.generate_cart_recovery_coupon(
                cart, discount=discount
            )
            cart.recovery_coupon = coupon.code

        # Calculate discounted total
        discounted_total = (
            cart.total_value * (1 - discount / 100)
            if discount > 0
            else cart.total_value
        )

        # Prepare variables
        variables = {
            "first_name": cart.customer.first_name,
            "cart_items": self.format_cart_items(cart.items, html=True),
            "cart_items_text": self.format_cart_items(cart.items, html=False),
            "cart_total": f"${cart.total_value:.2f}",
            "discounted_total": f"${discounted_total:.2f}",
            "checkout_url": f"https://store.example.com/checkout?cart={cart.id}",
            "discount": discount,
            "coupon_code": coupon.code if coupon else "",
        }

        # Render email
        subject = self.template_engine.render_subject(template_id, variables)
        content = self.template_engine.render_template(
            template_id, variables, use_html=True
        )

        email = EmailMessage(
            id=f"EMAIL-{cart.id}-{email_index}",
            template_id=template_id,
            customer=cart.customer,
            subject=subject,
            content=content,
            status=EmailStatus.QUEUED,
            scheduled_at=datetime.now(),
            metadata={"cart_id": cart.id, "sequence": email_index},
        )

        return email, coupon

    def process_recovery(self, carts: list[AbandonedCart]) -> dict[str, Any]:
        """Process all eligible cart recovery emails."""
        recoverable = self.get_recoverable_carts(carts)

        results = {
            "processed": 0,
            "emails_queued": 0,
            "coupons_generated": 0,
            "total_cart_value": 0,
            "emails": [],
        }

        for cart in recoverable:
            email, coupon = self.prepare_recovery_email(cart)

            # Simulate sending
            email.status = EmailStatus.SENT
            email.sent_at = datetime.now()

            cart.recovery_emails_sent += 1

            self.sent_emails.append(email)

            results["processed"] += 1
            results["emails_queued"] += 1
            results["total_cart_value"] += cart.total_value
            if coupon:
                results["coupons_generated"] += 1

            results["emails"].append(
                {
                    "cart_id": cart.id,
                    "customer": cart.customer.email,
                    "cart_value": cart.total_value,
                    "email_sequence": cart.recovery_emails_sent,
                    "coupon": coupon.code if coupon else None,
                }
            )

        return results

    def get_recovery_stats(self, carts: list[AbandonedCart]) -> dict[str, Any]:
        """Get cart recovery statistics."""
        total_carts = len(carts)
        recovered = [c for c in carts if c.recovered]
        pending = [c for c in carts if not c.recovered and c.customer.email_opt_in]

        total_value = sum(c.total_value for c in carts)
        recovered_value = sum(c.total_value for c in recovered)
        pending_value = sum(c.total_value for c in pending)

        return {
            "total_carts": total_carts,
            "recovered_carts": len(recovered),
            "pending_carts": len(pending),
            "recovery_rate": (
                (len(recovered) / total_carts * 100) if total_carts > 0 else 0
            ),
            "total_value": total_value,
            "recovered_value": recovered_value,
            "pending_value": pending_value,
            "emails_sent": sum(c.recovery_emails_sent for c in carts),
            "avg_cart_value": total_value / total_carts if total_carts > 0 else 0,
        }


# =============================================================================
# FLASH SALE MANAGER
# =============================================================================


class FlashSaleManager:
    """Manage flash sales and time-limited promotions."""

    def __init__(
        self, coupon_generator: CouponGenerator, template_engine: EmailTemplateEngine
    ):
        """Initialize flash sale manager."""
        self.coupon_generator = coupon_generator
        self.template_engine = template_engine
        self.sales: list[FlashSale] = []

    def create_flash_sale(
        self,
        name: str,
        discount_percent: float,
        duration_hours: int,
        product_ids: list[int] = None,
        category_ids: list[int] = None,
        start_delay_minutes: int = 0,
    ) -> FlashSale:
        """Create a new flash sale."""
        start_time = datetime.now() + timedelta(minutes=start_delay_minutes)
        end_time = start_time + timedelta(hours=duration_hours)

        sale = FlashSale(
            id=f"FLASH-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            name=name,
            description=f"{discount_percent}% off for {duration_hours} hours only!",
            discount_percent=discount_percent,
            product_ids=product_ids or [],
            category_ids=category_ids or [],
            start_time=start_time,
            end_time=end_time,
            notify_customers=True,
            landing_page_url="https://store.example.com/flash-sale",
        )

        self.sales.append(sale)
        return sale

    def get_active_sales(self) -> list[FlashSale]:
        """Get currently active flash sales."""
        return [s for s in self.sales if s.is_active]

    def get_upcoming_sales(self) -> list[FlashSale]:
        """Get upcoming scheduled flash sales."""
        now = datetime.now()
        return [s for s in self.sales if s.start_time > now]

    def prepare_announcement(self, sale: FlashSale, customer: Customer) -> EmailMessage:
        """Prepare flash sale announcement email."""
        hours_duration = (sale.end_time - sale.start_time).total_seconds() / 3600

        # Featured products (mock)
        featured_html = """
        <div style="display: flex; flex-wrap: wrap; gap: 10px;">
            <div style="flex: 1; min-width: 200px; border: 1px solid #eee; padding: 10px; border-radius: 4px;">
                <strong>AirPods Pro 2</strong><br>
                <s>$399</s> <span style="color: #28a745;">$339.15</span>
            </div>
            <div style="flex: 1; min-width: 200px; border: 1px solid #eee; padding: 10px; border-radius: 4px;">
                <strong>Sony WH-1000XM5</strong><br>
                <s>$549</s> <span style="color: #28a745;">$466.65</span>
            </div>
        </div>
        """

        variables = {
            "first_name": customer.first_name,
            "discount": sale.discount_percent,
            "hours": int(hours_duration),
            "featured_products": featured_html,
            "sale_url": sale.landing_page_url,
            "end_time": sale.end_time.strftime("%B %d at %I:%M %p"),
        }

        subject = self.template_engine.render_subject("flash_sale", variables)
        content = self.template_engine.render_template("flash_sale", variables)

        return EmailMessage(
            id=f"FLASH-EMAIL-{sale.id}-{customer.id}",
            template_id="flash_sale",
            customer=customer,
            subject=subject,
            content=content,
            status=EmailStatus.QUEUED,
            campaign_id=sale.id,
        )

    def notify_customers(
        self,
        sale: FlashSale,
        customers: list[Customer],
        segment: CustomerSegment = None,
    ) -> list[EmailMessage]:
        """Send flash sale notifications to customers."""
        emails = []

        # Filter by segment if specified
        if segment:
            engine = SegmentationEngine()
            customers = engine.get_segment_customers(customers, segment)

        # Only email opted-in customers
        customers = [c for c in customers if c.email_opt_in]

        for customer in customers:
            email = self.prepare_announcement(sale, customer)
            email.status = EmailStatus.SENT
            email.sent_at = datetime.now()
            emails.append(email)

        return emails


# =============================================================================
# LOYALTY PROGRAM MANAGER
# =============================================================================


class LoyaltyManager:
    """Manage loyalty program and rewards."""

    def __init__(self, coupon_generator: CouponGenerator):
        """Initialize loyalty manager."""
        self.coupon_generator = coupon_generator

        # Default loyalty program
        self.program = LoyaltyProgram(
            name="ElectroRewards",
            points_per_dollar=1,
            tiers=[
                LoyaltyTier(
                    name="Bronze",
                    min_points=0,
                    max_points=499,
                    benefits=["1 point per $1 spent", "Birthday discount"],
                    points_multiplier=1.0,
                    exclusive_sales=False,
                    free_shipping=False,
                    birthday_bonus=50,
                ),
                LoyaltyTier(
                    name="Silver",
                    min_points=500,
                    max_points=1999,
                    benefits=[
                        "1.2x points",
                        "Early access to sales",
                        "Birthday discount",
                    ],
                    points_multiplier=1.2,
                    exclusive_sales=True,
                    free_shipping=False,
                    birthday_bonus=100,
                ),
                LoyaltyTier(
                    name="Gold",
                    min_points=2000,
                    max_points=4999,
                    benefits=["1.5x points", "Free shipping", "Exclusive offers"],
                    points_multiplier=1.5,
                    exclusive_sales=True,
                    free_shipping=True,
                    birthday_bonus=200,
                ),
                LoyaltyTier(
                    name="Platinum",
                    min_points=5000,
                    max_points=None,
                    benefits=["2x points", "Free express shipping", "VIP support"],
                    points_multiplier=2.0,
                    exclusive_sales=True,
                    free_shipping=True,
                    birthday_bonus=500,
                ),
            ],
            points_expiry_months=24,
            referral_bonus=100,
            review_bonus=25,
            birthday_bonus=50,
        )

    def get_customer_tier(self, customer: Customer) -> LoyaltyTier:
        """Get customer's loyalty tier."""
        for tier in reversed(self.program.tiers):
            if customer.loyalty_points >= tier.min_points:
                return tier
        return self.program.tiers[0]

    def calculate_points(self, customer: Customer, order_total: float) -> int:
        """Calculate points earned from an order."""
        tier = self.get_customer_tier(customer)
        base_points = int(order_total * self.program.points_per_dollar)
        return int(base_points * tier.points_multiplier)

    def get_tier_progress(self, customer: Customer) -> dict:
        """Get customer's progress to next tier."""
        current_tier = self.get_customer_tier(customer)
        tier_index = self.program.tiers.index(current_tier)

        if tier_index >= len(self.program.tiers) - 1:
            # Already at top tier
            return {
                "current_tier": current_tier.name,
                "next_tier": None,
                "points_needed": 0,
                "progress_percent": 100,
            }

        next_tier = self.program.tiers[tier_index + 1]
        points_needed = next_tier.min_points - customer.loyalty_points

        tier_range = next_tier.min_points - current_tier.min_points
        points_in_tier = customer.loyalty_points - current_tier.min_points
        progress = (points_in_tier / tier_range * 100) if tier_range > 0 else 0

        return {
            "current_tier": current_tier.name,
            "next_tier": next_tier.name,
            "points_needed": points_needed,
            "progress_percent": min(progress, 100),
        }

    def generate_tier_reward(self, customer: Customer) -> Optional[Coupon]:
        """Generate a tier-specific reward coupon."""
        tier = self.get_customer_tier(customer)

        tier_discounts = {"Bronze": 5, "Silver": 10, "Gold": 15, "Platinum": 20}

        discount = tier_discounts.get(tier.name, 5)
        return self.coupon_generator.generate_loyalty_coupon(
            customer, tier.name, discount
        )

    def get_program_summary(self, customers: list[Customer]) -> dict:
        """Get loyalty program summary statistics."""
        tier_counts = {"Bronze": 0, "Silver": 0, "Gold": 0, "Platinum": 0}
        total_points = 0

        for customer in customers:
            tier = self.get_customer_tier(customer)
            tier_counts[tier.name] += 1
            total_points += customer.loyalty_points

        return {
            "program_name": self.program.name,
            "total_members": len(customers),
            "tier_distribution": tier_counts,
            "total_points_issued": total_points,
            "avg_points_per_member": total_points / len(customers) if customers else 0,
            "points_value": total_points * 0.01,  # Assuming 1 point = $0.01
        }


# =============================================================================
# CAMPAIGN MANAGER
# =============================================================================


class CampaignManager:
    """Manage marketing campaigns."""

    def __init__(
        self,
        coupon_generator: CouponGenerator,
        template_engine: EmailTemplateEngine,
        segmentation: SegmentationEngine,
    ):
        """Initialize campaign manager."""
        self.coupon_generator = coupon_generator
        self.template_engine = template_engine
        self.segmentation = segmentation
        self.campaigns: list[Campaign] = []

    def create_campaign(
        self,
        name: str,
        campaign_type: CampaignType,
        target_segments: list[CustomerSegment],
        trigger_type: TriggerType,
        email_sequence: list[dict],
        description: str = "",
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Campaign:
        """Create a new marketing campaign."""
        campaign = Campaign(
            id=f"CAMP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.campaigns)}",
            name=name,
            campaign_type=campaign_type,
            status=CampaignStatus.DRAFT,
            description=description,
            target_segments=target_segments,
            trigger_type=trigger_type,
            trigger_conditions={},
            email_sequence=email_sequence,
            start_date=start_date or datetime.now(),
            end_date=end_date,
        )

        self.campaigns.append(campaign)
        return campaign

    def activate_campaign(self, campaign_id: str) -> bool:
        """Activate a campaign."""
        campaign = self.get_campaign(campaign_id)
        if campaign and campaign.status == CampaignStatus.DRAFT:
            campaign.status = CampaignStatus.ACTIVE
            return True
        return False

    def pause_campaign(self, campaign_id: str) -> bool:
        """Pause a campaign."""
        campaign = self.get_campaign(campaign_id)
        if campaign and campaign.status == CampaignStatus.ACTIVE:
            campaign.status = CampaignStatus.PAUSED
            return True
        return False

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get campaign by ID."""
        return next((c for c in self.campaigns if c.id == campaign_id), None)

    def get_active_campaigns(self) -> list[Campaign]:
        """Get all active campaigns."""
        return [c for c in self.campaigns if c.status == CampaignStatus.ACTIVE]

    def get_campaign_recipients(
        self, campaign: Campaign, customers: list[Customer]
    ) -> list[Customer]:
        """Get eligible recipients for a campaign."""
        eligible = []

        for customer in customers:
            if not customer.email_opt_in:
                continue

            # Check if customer matches target segments
            customer_segments = self.segmentation.segment_customer(customer)
            if any(s in campaign.target_segments for s in customer_segments):
                eligible.append(customer)

        return eligible

    def get_campaign_stats(self) -> dict:
        """Get overall campaign statistics."""
        active = [c for c in self.campaigns if c.status == CampaignStatus.ACTIVE]

        total_sent = sum(c.emails_sent for c in self.campaigns)
        total_opened = sum(c.emails_opened for c in self.campaigns)
        total_clicked = sum(c.emails_clicked for c in self.campaigns)
        total_conversions = sum(c.conversions for c in self.campaigns)
        total_revenue = sum(c.revenue_generated for c in self.campaigns)

        return {
            "total_campaigns": len(self.campaigns),
            "active_campaigns": len(active),
            "total_emails_sent": total_sent,
            "avg_open_rate": (total_opened / total_sent * 100) if total_sent > 0 else 0,
            "avg_click_rate": (
                (total_clicked / total_sent * 100) if total_sent > 0 else 0
            ),
            "total_conversions": total_conversions,
            "total_revenue": total_revenue,
            "conversion_rate": (
                (total_conversions / total_clicked * 100) if total_clicked > 0 else 0
            ),
        }


# =============================================================================
# BIRTHDAY/ANNIVERSARY AUTOMATION
# =============================================================================


class SpecialDateAutomation:
    """Automate birthday and anniversary campaigns."""

    def __init__(
        self, coupon_generator: CouponGenerator, template_engine: EmailTemplateEngine
    ):
        """Initialize special date automation."""
        self.coupon_generator = coupon_generator
        self.template_engine = template_engine

    def get_upcoming_birthdays(
        self, customers: list[Customer], days_ahead: int = 7
    ) -> list[Customer]:
        """Get customers with birthdays in the next N days."""
        upcoming = []
        today = datetime.now().date()

        for customer in customers:
            if not customer.birthday or not customer.email_opt_in:
                continue

            # Create this year's birthday
            bday_this_year = customer.birthday.replace(year=today.year)
            if bday_this_year.date() < today:
                bday_this_year = bday_this_year.replace(year=today.year + 1)

            days_until = (bday_this_year.date() - today).days

            if 0 <= days_until <= days_ahead:
                upcoming.append(customer)

        return upcoming

    def get_upcoming_anniversaries(
        self, customers: list[Customer], days_ahead: int = 7
    ) -> list[Customer]:
        """Get customers with purchase anniversaries in the next N days."""
        upcoming = []
        today = datetime.now().date()

        for customer in customers:
            if not customer.anniversary or not customer.email_opt_in:
                continue

            # Anniversary of first purchase
            anni_this_year = customer.anniversary.replace(year=today.year)
            if anni_this_year.date() < today:
                anni_this_year = anni_this_year.replace(year=today.year + 1)

            days_until = (anni_this_year.date() - today).days

            if 0 <= days_until <= days_ahead:
                upcoming.append(customer)

        return upcoming

    def prepare_birthday_email(
        self, customer: Customer, discount: float = 20
    ) -> tuple[EmailMessage, Coupon]:
        """Prepare birthday email with coupon."""
        coupon = self.coupon_generator.generate_birthday_coupon(customer, discount)

        variables = {
            "first_name": customer.first_name,
            "discount": discount,
            "coupon_code": coupon.code,
            "shop_url": "https://store.example.com",
        }

        subject = self.template_engine.render_subject("birthday", variables)
        content = self.template_engine.render_template("birthday", variables)

        email = EmailMessage(
            id=f"BDAY-{customer.id}-{datetime.now().strftime('%Y')}",
            template_id="birthday",
            customer=customer,
            subject=subject,
            content=content,
            status=EmailStatus.QUEUED,
        )

        return email, coupon

    def process_birthdays(
        self, customers: list[Customer], discount: float = 20
    ) -> dict:
        """Process all birthday emails."""
        upcoming = self.get_upcoming_birthdays(customers, days_ahead=1)  # Send day-of

        results = {
            "processed": len(upcoming),
            "emails_sent": 0,
            "coupons_generated": 0,
            "recipients": [],
        }

        for customer in upcoming:
            email, coupon = self.prepare_birthday_email(customer, discount)
            email.status = EmailStatus.SENT
            email.sent_at = datetime.now()

            results["emails_sent"] += 1
            results["coupons_generated"] += 1
            results["recipients"].append(
                {
                    "customer": customer.email,
                    "name": customer.full_name,
                    "coupon": coupon.code,
                }
            )

        return results


# =============================================================================
# DISPLAY AND REPORTING
# =============================================================================


class MarketingDashboard:
    """Display marketing automation dashboard."""

    def __init__(
        self,
        cart_recovery: AbandonedCartRecovery,
        flash_sales: FlashSaleManager,
        loyalty: LoyaltyManager,
        campaigns: CampaignManager,
        segmentation: SegmentationEngine,
    ):
        """Initialize dashboard."""
        self.cart_recovery = cart_recovery
        self.flash_sales = flash_sales
        self.loyalty = loyalty
        self.campaigns = campaigns
        self.segmentation = segmentation

    def format_currency(self, amount: float) -> str:
        return f"${amount:,.2f}"

    def format_percent(self, value: float) -> str:
        return f"{value:.1f}%"

    def show_overview(self, carts: list[AbandonedCart], customers: list[Customer]):
        """Show marketing automation overview."""
        print("\n" + "=" * 80)
        print("📧 MARKETING AUTOMATION DASHBOARD - Electronics Store")
        print("=" * 80)

        # Cart Recovery Stats
        cart_stats = self.cart_recovery.get_recovery_stats(carts)

        print("\n" + "-" * 40)
        print("🛒 ABANDONED CART RECOVERY")
        print("-" * 40)
        print(f"   Active Carts:       {cart_stats['pending_carts']}")
        print(f"   Recovered:          {cart_stats['recovered_carts']}")
        print(
            f"   Recovery Rate:      {self.format_percent(cart_stats['recovery_rate'])}"
        )
        print(
            f"   Pending Value:      {self.format_currency(cart_stats['pending_value'])}"
        )
        print(
            f"   Recovered Value:    {self.format_currency(cart_stats['recovered_value'])}"
        )
        print(f"   Emails Sent:        {cart_stats['emails_sent']}")

        # Campaign Stats
        campaign_stats = self.campaigns.get_campaign_stats()

        print("\n" + "-" * 40)
        print("📬 EMAIL CAMPAIGNS")
        print("-" * 40)
        print(f"   Active Campaigns:   {campaign_stats['active_campaigns']}")
        print(f"   Total Emails Sent:  {campaign_stats['total_emails_sent']:,}")
        print(
            f"   Avg Open Rate:      {self.format_percent(campaign_stats['avg_open_rate'])}"
        )
        print(
            f"   Avg Click Rate:     {self.format_percent(campaign_stats['avg_click_rate'])}"
        )
        print(f"   Conversions:        {campaign_stats['total_conversions']}")
        print(
            f"   Revenue Generated:  {self.format_currency(campaign_stats['total_revenue'])}"
        )

        # Flash Sales
        active_sales = self.flash_sales.get_active_sales()

        print("\n" + "-" * 40)
        print("⚡ FLASH SALES")
        print("-" * 40)
        print(f"   Active Sales:       {len(active_sales)}")
        for sale in active_sales:
            print(
                f"   • {sale.name}: {sale.discount_percent}% off ({sale.hours_remaining:.1f}h remaining)"
            )

        # Loyalty Program
        loyalty_stats = self.loyalty.get_program_summary(customers)

        print("\n" + "-" * 40)
        print("⭐ LOYALTY PROGRAM")
        print("-" * 40)
        print(f"   Program:            {loyalty_stats['program_name']}")
        print(f"   Total Members:      {loyalty_stats['total_members']:,}")
        print(f"   Points Issued:      {loyalty_stats['total_points_issued']:,}")
        print(
            f"   Points Value:       {self.format_currency(loyalty_stats['points_value'])}"
        )
        print("   Tier Distribution:")
        for tier, count in loyalty_stats["tier_distribution"].items():
            print(f"      {tier}: {count}")

    def show_segments(self, customers: list[Customer]):
        """Show customer segmentation analysis."""
        print("\n" + "=" * 80)
        print("👥 CUSTOMER SEGMENTATION")
        print("=" * 80)

        analysis = self.segmentation.analyze_segments(customers)

        print(
            f"\n{'Segment':<25} {'Count':<10} {'%':<8} {'Revenue':<15} {'Avg Value':<12} {'Email Opt-in':<12}"
        )
        print("-" * 85)

        for segment, data in analysis.items():
            if data["count"] > 0:
                print(
                    f"{segment.value:<25} {data['count']:<10} {data['percentage']:.1f}%{'':3} {self.format_currency(data['total_revenue']):<15} {self.format_currency(data['avg_customer_value']):<12} {data['email_opt_in']}"
                )

    def show_recovery_queue(self, carts: list[AbandonedCart]):
        """Show abandoned cart recovery queue."""
        print("\n" + "=" * 80)
        print("🛒 ABANDONED CART RECOVERY QUEUE")
        print("=" * 80)

        recoverable = self.cart_recovery.get_recoverable_carts(carts)

        print(f"\n{len(recoverable)} carts ready for recovery emails\n")

        print(
            f"{'Cart ID':<15} {'Customer':<30} {'Value':<12} {'Hours':<8} {'Emails Sent':<12}"
        )
        print("-" * 80)

        for cart in recoverable[:10]:
            print(
                f"{cart.id:<15} {cart.customer.email[:28]:<30} {self.format_currency(cart.total_value):<12} {cart.hours_since_abandonment:.1f}h{'':3} {cart.recovery_emails_sent}"
            )

        if len(recoverable) > 10:
            print(f"\n... and {len(recoverable) - 10} more carts")

    def show_coupons(self, coupons: list[Coupon]):
        """Show active coupons."""
        print("\n" + "=" * 80)
        print("🎟️ ACTIVE COUPONS")
        print("=" * 80)

        active = [c for c in coupons if c.is_valid]

        print(f"\n{len(active)} active coupons\n")

        print(f"{'Code':<20} {'Type':<15} {'Value':<12} {'Used':<8} {'Expires':<20}")
        print("-" * 80)

        for coupon in active[:15]:
            if coupon.discount_type == CouponType.PERCENT:
                value = f"{coupon.amount}%"
            elif coupon.discount_type == CouponType.FREE_SHIPPING:
                value = "Free Ship"
            else:
                value = f"${coupon.amount}"

            expires = (
                coupon.end_date.strftime("%Y-%m-%d %H:%M")
                if coupon.end_date
                else "Never"
            )
            used = (
                f"{coupon.usage_count}/{coupon.usage_limit}"
                if coupon.usage_limit
                else str(coupon.usage_count)
            )

            print(
                f"{coupon.code:<20} {coupon.discount_type.value:<15} {value:<12} {used:<8} {expires:<20}"
            )


# =============================================================================
# INTERACTIVE MODE
# =============================================================================


class InteractiveMarketing:
    """Interactive marketing automation interface."""

    def __init__(
        self,
        dashboard: MarketingDashboard,
        carts: list[AbandonedCart],
        customers: list[Customer],
    ):
        """Initialize interactive interface."""
        self.dashboard = dashboard
        self.carts = carts
        self.customers = customers
        self.coupons: list[Coupon] = []

    def show_menu(self):
        """Display main menu."""
        print("\n" + "=" * 60)
        print("📧 MARKETING AUTOMATION - Interactive Mode")
        print("=" * 60)
        print("\nOptions:")
        print("  1. View Dashboard Overview")
        print("  2. View Customer Segments")
        print("  3. View Cart Recovery Queue")
        print("  4. Process Cart Recovery Emails")
        print("  5. Generate Coupons")
        print("  6. Create Flash Sale")
        print("  7. View Active Coupons")
        print("  8. Process Birthday Emails")
        print("  0. Exit")
        print("-" * 60)

    def run(self):
        """Run interactive interface."""
        while True:
            self.show_menu()

            try:
                choice = input("\nEnter choice: ").strip()

                if choice == "0":
                    print("\n👋 Goodbye!")
                    break
                elif choice == "1":
                    self.dashboard.show_overview(self.carts, self.customers)
                elif choice == "2":
                    self.dashboard.show_segments(self.customers)
                elif choice == "3":
                    self.dashboard.show_recovery_queue(self.carts)
                elif choice == "4":
                    results = self.dashboard.cart_recovery.process_recovery(self.carts)
                    print(f"\n✅ Processed {results['processed']} carts")
                    print(f"   Emails queued: {results['emails_queued']}")
                    print(f"   Coupons generated: {results['coupons_generated']}")
                    print(
                        f"   Total cart value: {self.dashboard.format_currency(results['total_cart_value'])}"
                    )
                elif choice == "5":
                    self._generate_coupons()
                elif choice == "6":
                    self._create_flash_sale()
                elif choice == "7":
                    self.dashboard.show_coupons(self.coupons)
                elif choice == "8":
                    self._process_birthdays()
                else:
                    print("\n⚠ Invalid choice")

                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break

    def _generate_coupons(self):
        """Generate coupons interactively."""
        print("\n🎟️ GENERATE COUPONS")
        print("-" * 40)

        try:
            count = int(input("How many coupons? [5]: ").strip() or "5")
            discount = float(input("Discount percentage? [10]: ").strip() or "10")
            prefix = input("Code prefix? [PROMO]: ").strip() or "PROMO"

            generator = self.dashboard.cart_recovery.coupon_generator
            new_coupons = generator.generate_batch(count, "percent", discount, prefix)
            self.coupons.extend(new_coupons)

            print(f"\n✅ Generated {count} coupons:")
            for coupon in new_coupons:
                print(f"   {coupon.code} - {coupon.amount}% off")

        except ValueError:
            print("\n⚠ Invalid input")

    def _create_flash_sale(self):
        """Create flash sale interactively."""
        print("\n⚡ CREATE FLASH SALE")
        print("-" * 40)

        try:
            name = input("Sale name: ").strip() or "Flash Sale"
            discount = float(input("Discount percentage? [20]: ").strip() or "20")
            hours = int(input("Duration (hours)? [4]: ").strip() or "4")

            sale = self.dashboard.flash_sales.create_flash_sale(
                name=name, discount_percent=discount, duration_hours=hours
            )

            print(f"\n✅ Flash sale created: {sale.id}")
            print(f"   Discount: {sale.discount_percent}%")
            print(f"   Starts: {sale.start_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"   Ends: {sale.end_time.strftime('%Y-%m-%d %H:%M')}")

        except ValueError:
            print("\n⚠ Invalid input")

    def _process_birthdays(self):
        """Process birthday emails."""
        automation = SpecialDateAutomation(
            self.dashboard.cart_recovery.coupon_generator,
            self.dashboard.cart_recovery.template_engine,
        )

        upcoming = automation.get_upcoming_birthdays(self.customers, days_ahead=7)

        print(f"\n🎂 {len(upcoming)} birthdays in the next 7 days:")
        for customer in upcoming[:10]:
            bday = customer.birthday.strftime("%B %d")
            print(f"   {customer.full_name} - {bday}")

        if upcoming:
            results = automation.process_birthdays(self.customers)
            print(f"\n✅ Sent {results['emails_sent']} birthday emails")


# =============================================================================
# MAIN APPLICATION
# =============================================================================


def run_demo():
    """Run demo mode with sample data."""
    print("\n🚀 Initializing Marketing Automation System...")
    print("   Generating demo data for electronics store...\n")

    # Generate demo data
    generator = DemoDataGenerator()
    customers = generator.create_customers(200)
    carts = generator.create_abandoned_carts(customers, count=50)

    # Initialize components
    coupon_gen = CouponGenerator()
    template_engine = EmailTemplateEngine()
    segmentation = SegmentationEngine()

    cart_recovery = AbandonedCartRecovery(coupon_gen, template_engine)
    flash_sales = FlashSaleManager(coupon_gen, template_engine)
    loyalty = LoyaltyManager(coupon_gen)
    campaigns = CampaignManager(coupon_gen, template_engine, segmentation)

    # Create demo campaigns
    campaigns.create_campaign(
        name="Welcome Series",
        campaign_type=CampaignType.WELCOME_SERIES,
        target_segments=[CustomerSegment.NEW_CUSTOMER],
        trigger_type=TriggerType.SEGMENT_ENTRY,
        email_sequence=[
            {"delay_hours": 0, "template": "welcome_1"},
        ],
    )

    # Create a flash sale
    flash_sales.create_flash_sale(
        name="Weekend Tech Sale", discount_percent=15, duration_hours=48
    )

    # Simulate some campaign metrics
    for campaign in campaigns.campaigns:
        campaign.status = CampaignStatus.ACTIVE
        campaign.emails_sent = random.randint(500, 2000)
        campaign.emails_opened = int(campaign.emails_sent * random.uniform(0.25, 0.35))
        campaign.emails_clicked = int(
            campaign.emails_opened * random.uniform(0.15, 0.25)
        )
        campaign.conversions = int(campaign.emails_clicked * random.uniform(0.05, 0.15))
        campaign.revenue_generated = campaign.conversions * random.uniform(150, 500)

    # Create dashboard
    dashboard = MarketingDashboard(
        cart_recovery, flash_sales, loyalty, campaigns, segmentation
    )

    # Show all views
    dashboard.show_overview(carts, customers)
    dashboard.show_segments(customers)
    dashboard.show_recovery_queue(carts)

    # Process recovery
    print("\n" + "=" * 80)
    print("🔄 PROCESSING CART RECOVERY")
    print("=" * 80)
    results = cart_recovery.process_recovery(carts)
    print(f"\n✅ Processed {results['processed']} abandoned carts")
    print(f"   Emails queued: {results['emails_queued']}")
    print(f"   Coupons generated: {results['coupons_generated']}")
    print(f"   Total cart value: ${results['total_cart_value']:,.2f}")

    if results["emails"]:
        print("\n   Recent emails:")
        for email in results["emails"][:5]:
            print(
                f"   • {email['customer']}: ${email['cart_value']:.2f} (Coupon: {email['coupon']})"
            )

    # Generate sample coupons
    print("\n" + "=" * 80)
    print("🎟️ SAMPLE COUPON GENERATION")
    print("=" * 80)
    coupons = coupon_gen.generate_batch(5, "percent", 15, "DEMO")
    print("\n   Generated coupons:")
    for coupon in coupons:
        print(
            f"   • {coupon.code}: {coupon.amount}% off (valid until {coupon.end_date.strftime('%Y-%m-%d')})"
        )

    print("\n" + "=" * 80)
    print("✅ Demo Complete!")
    print("=" * 80)


def run_interactive():
    """Run interactive mode."""
    print("\n🚀 Initializing Marketing Automation System...")
    print("   Loading interactive mode...\n")

    # Generate demo data
    generator = DemoDataGenerator()
    customers = generator.create_customers(200)
    carts = generator.create_abandoned_carts(customers, count=50)

    # Initialize components
    coupon_gen = CouponGenerator()
    template_engine = EmailTemplateEngine()
    segmentation = SegmentationEngine()

    cart_recovery = AbandonedCartRecovery(coupon_gen, template_engine)
    flash_sales = FlashSaleManager(coupon_gen, template_engine)
    loyalty = LoyaltyManager(coupon_gen)
    campaigns = CampaignManager(coupon_gen, template_engine, segmentation)

    # Create dashboard
    dashboard = MarketingDashboard(
        cart_recovery, flash_sales, loyalty, campaigns, segmentation
    )

    # Run interactive
    interactive = InteractiveMarketing(dashboard, carts, customers)
    interactive.run()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WooCommerce Marketing Automation - Email campaigns and customer engagement"
    )

    parser.add_argument(
        "--demo", action="store_true", help="Run in demo mode with sample data"
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive mode with menu navigation",
    )

    parser.add_argument(
        "--campaign",
        type=str,
        choices=["abandoned-cart", "welcome", "birthday", "flash-sale", "reengagement"],
        help="Run specific campaign type",
    )

    parser.add_argument(
        "--generate-coupons",
        type=int,
        metavar="N",
        help="Generate N promotional coupons",
    )

    parser.add_argument(
        "--discount",
        type=float,
        default=10,
        help="Discount percentage for coupons (default: 10)",
    )

    parser.add_argument(
        "--prefix",
        type=str,
        default="PROMO",
        help="Coupon code prefix (default: PROMO)",
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.interactive:
        run_interactive()
    elif args.generate_coupons:
        coupon_gen = CouponGenerator()
        coupons = coupon_gen.generate_batch(
            args.generate_coupons, "percent", args.discount, args.prefix
        )
        print(f"\n✅ Generated {len(coupons)} coupons:")
        for coupon in coupons:
            print(f"   {coupon.code}: {coupon.amount}% off")
    else:
        # Default to demo
        run_demo()


if __name__ == "__main__":
    main()
