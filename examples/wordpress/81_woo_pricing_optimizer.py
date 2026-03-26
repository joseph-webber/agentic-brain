#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WooCommerce Pricing Optimizer - Example 81

Dynamic pricing rules, margin analysis, and pricing automation.

Features:
- Dynamic pricing rules engine
- Competitor price monitoring (conceptual)
- Bundle pricing suggestions
- Volume discount management
- Seasonal pricing automation
- Clearance sale automation
- Margin analysis and optimization
- Price elasticity concepts

Usage:
    python 81_woo_pricing_optimizer.py --demo
    python 81_woo_pricing_optimizer.py --interactive
    python 81_woo_pricing_optimizer.py --analyze-margins
    python 81_woo_pricing_optimizer.py --optimize --min-margin 25
"""

import argparse
import json
import random
from datetime import datetime, timedelta
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics
import math

# =============================================================================
# DOMAIN MODELS
# =============================================================================


class PricingStrategy(Enum):
    """Pricing strategy types."""

    COST_PLUS = "cost_plus"
    COMPETITIVE = "competitive"
    VALUE_BASED = "value_based"
    DYNAMIC = "dynamic"
    PENETRATION = "penetration"
    SKIMMING = "skimming"
    BUNDLE = "bundle"
    PSYCHOLOGICAL = "psychological"


class ProductCategory(Enum):
    """Electronics product categories."""

    SMARTPHONES = "Smartphones"
    LAPTOPS = "Laptops"
    TABLETS = "Tablets"
    AUDIO = "Audio & Headphones"
    WEARABLES = "Wearables"
    GAMING = "Gaming"
    CAMERAS = "Cameras"
    ACCESSORIES = "Accessories"
    HOME_AUTOMATION = "Home Automation"
    CABLES_CHARGERS = "Cables & Chargers"


class PriceChangeReason(Enum):
    """Reasons for price changes."""

    COMPETITOR_MATCH = "competitor_match"
    MARGIN_OPTIMIZATION = "margin_optimization"
    INVENTORY_CLEARANCE = "inventory_clearance"
    SEASONAL = "seasonal"
    PROMOTION = "promotion"
    COST_CHANGE = "cost_change"
    DEMAND_BASED = "demand_based"
    BUNDLE_PRICING = "bundle_pricing"
    VOLUME_DISCOUNT = "volume_discount"
    MANUAL = "manual"


class DiscountType(Enum):
    """Discount types."""

    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    BUY_X_GET_Y = "buy_x_get_y"
    TIERED = "tiered"
    BUNDLE = "bundle"


class SeasonType(Enum):
    """Seasonal periods."""

    CHRISTMAS = "christmas"
    BLACK_FRIDAY = "black_friday"
    CYBER_MONDAY = "cyber_monday"
    BACK_TO_SCHOOL = "back_to_school"
    EOFY = "eofy"  # End of Financial Year
    BOXING_DAY = "boxing_day"
    REGULAR = "regular"


@dataclass
class Product:
    """Product with pricing data."""

    id: int
    sku: str
    name: str
    category: ProductCategory
    cost: float
    price: float
    msrp: float  # Manufacturer's suggested retail price
    map_price: float  # Minimum advertised price
    stock_quantity: int
    units_sold_30d: int = 0
    views_30d: int = 0
    is_featured: bool = False
    supplier_id: int = 1
    weight: float = 0.5
    days_in_stock: int = 30
    last_price_change: Optional[datetime] = None

    @property
    def margin(self) -> float:
        """Profit margin percentage."""
        if self.price > 0:
            return ((self.price - self.cost) / self.price) * 100
        return 0.0

    @property
    def markup(self) -> float:
        """Markup percentage over cost."""
        if self.cost > 0:
            return ((self.price - self.cost) / self.cost) * 100
        return 0.0

    @property
    def profit(self) -> float:
        """Profit per unit."""
        return self.price - self.cost

    @property
    def conversion_rate(self) -> float:
        """View to purchase conversion rate."""
        if self.views_30d > 0:
            return (self.units_sold_30d / self.views_30d) * 100
        return 0.0

    @property
    def stock_velocity(self) -> float:
        """Units sold per day."""
        return self.units_sold_30d / 30 if self.units_sold_30d > 0 else 0

    @property
    def days_of_stock(self) -> int:
        """Estimated days until stockout."""
        if self.stock_velocity > 0:
            return int(self.stock_quantity / self.stock_velocity)
        return 999  # Effectively infinite


@dataclass
class Competitor:
    """Competitor store information."""

    id: int
    name: str
    website: str
    price_position: str  # "premium", "value", "discount"
    reliability: float  # Price data reliability 0-1
    shipping_cost: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class CompetitorPrice:
    """Competitor price data point."""

    competitor: Competitor
    product_sku: str
    price: float
    in_stock: bool
    url: str
    last_scraped: datetime

    @property
    def age_hours(self) -> float:
        return (datetime.now() - self.last_scraped).total_seconds() / 3600


@dataclass
class PriceRule:
    """Dynamic pricing rule."""

    id: str
    name: str
    description: str
    priority: int
    is_active: bool
    conditions: dict  # Conditions to trigger rule
    action: dict  # Action to take
    created_at: datetime = field(default_factory=datetime.now)

    def matches(self, product: Product, context: dict = None) -> bool:
        """Check if rule matches product and context."""
        # Simplified matching logic
        return True


@dataclass
class VolumeDiscount:
    """Volume discount tier."""

    min_quantity: int
    max_quantity: Optional[int]
    discount_percent: float
    discount_fixed: float = 0.0


@dataclass
class BundleConfig:
    """Product bundle configuration."""

    id: str
    name: str
    product_ids: list[int]
    bundle_price: float
    individual_total: float
    min_quantity: int = 1
    is_active: bool = True

    @property
    def savings(self) -> float:
        return self.individual_total - self.bundle_price

    @property
    def savings_percent(self) -> float:
        if self.individual_total > 0:
            return (self.savings / self.individual_total) * 100
        return 0.0


@dataclass
class PriceHistory:
    """Price history entry."""

    product_id: int
    old_price: float
    new_price: float
    reason: PriceChangeReason
    changed_at: datetime
    changed_by: str = "system"
    notes: str = ""


@dataclass
class MarginAnalysis:
    """Margin analysis for a product."""

    product: Product
    current_margin: float
    target_margin: float
    margin_gap: float
    recommended_price: float
    competitor_avg: float
    market_position: str
    recommendation: str


@dataclass
class PricingRecommendation:
    """Pricing recommendation."""

    product: Product
    current_price: float
    recommended_price: float
    change_percent: float
    reason: str
    confidence: float
    projected_impact: dict


# =============================================================================
# DEMO DATA GENERATOR
# =============================================================================


class DemoDataGenerator:
    """Generate realistic demo data for electronics store."""

    PRODUCTS = [
        # Smartphones
        {
            "sku": "SP-IP15-256",
            "name": "Smartphone Pro 15 256GB",
            "category": ProductCategory.SMARTPHONES,
            "cost": 1200,
            "price": 1699,
            "msrp": 1799,
            "map": 1599,
        },
        {
            "sku": "SP-IP15-128",
            "name": "Smartphone Pro 15 128GB",
            "category": ProductCategory.SMARTPHONES,
            "cost": 1050,
            "price": 1499,
            "msrp": 1599,
            "map": 1449,
        },
        {
            "sku": "SP-S24-256",
            "name": "Galaxy Smartphone S24 256GB",
            "category": ProductCategory.SMARTPHONES,
            "cost": 950,
            "price": 1349,
            "msrp": 1449,
            "map": 1299,
        },
        {
            "sku": "SP-PX8-128",
            "name": "Pixel Phone 8 128GB",
            "category": ProductCategory.SMARTPHONES,
            "cost": 700,
            "price": 999,
            "msrp": 1099,
            "map": 949,
        },
        {
            "sku": "SP-BUD-MID",
            "name": "Budget Smartphone Pro",
            "category": ProductCategory.SMARTPHONES,
            "cost": 250,
            "price": 399,
            "msrp": 449,
            "map": 379,
        },
        # Laptops
        {
            "sku": "LP-MBP-14",
            "name": "MacBook Pro 14-inch M3",
            "category": ProductCategory.LAPTOPS,
            "cost": 2400,
            "price": 3199,
            "msrp": 3499,
            "map": 3099,
        },
        {
            "sku": "LP-MBP-16",
            "name": "MacBook Pro 16-inch M3",
            "category": ProductCategory.LAPTOPS,
            "cost": 3200,
            "price": 4299,
            "msrp": 4699,
            "map": 4199,
        },
        {
            "sku": "LP-MBA-15",
            "name": "MacBook Air 15-inch M3",
            "category": ProductCategory.LAPTOPS,
            "cost": 1600,
            "price": 2199,
            "msrp": 2399,
            "map": 2099,
        },
        {
            "sku": "LP-DELL-XPS",
            "name": "Dell XPS 15 Laptop",
            "category": ProductCategory.LAPTOPS,
            "cost": 1800,
            "price": 2499,
            "msrp": 2699,
            "map": 2399,
        },
        {
            "sku": "LP-HP-ENVVY",
            "name": "HP Envy 15 Laptop",
            "category": ProductCategory.LAPTOPS,
            "cost": 1100,
            "price": 1599,
            "msrp": 1799,
            "map": 1499,
        },
        # Tablets
        {
            "sku": "TB-IPADPRO",
            "name": "iPad Pro 12.9-inch M2",
            "category": ProductCategory.TABLETS,
            "cost": 1400,
            "price": 1899,
            "msrp": 2099,
            "map": 1849,
        },
        {
            "sku": "TB-IPADAIR",
            "name": "iPad Air 10.9-inch",
            "category": ProductCategory.TABLETS,
            "cost": 650,
            "price": 929,
            "msrp": 999,
            "map": 899,
        },
        {
            "sku": "TB-SAMSUNGS9",
            "name": "Samsung Galaxy Tab S9",
            "category": ProductCategory.TABLETS,
            "cost": 850,
            "price": 1199,
            "msrp": 1299,
            "map": 1149,
        },
        # Audio
        {
            "sku": "AU-APPMAX",
            "name": "AirPods Max",
            "category": ProductCategory.AUDIO,
            "cost": 600,
            "price": 899,
            "msrp": 899,
            "map": 849,
        },
        {
            "sku": "AU-APPPRO2",
            "name": "AirPods Pro 2nd Gen",
            "category": ProductCategory.AUDIO,
            "cost": 260,
            "price": 399,
            "msrp": 399,
            "map": 369,
        },
        {
            "sku": "AU-SONYWH",
            "name": "Sony WH-1000XM5 Headphones",
            "category": ProductCategory.AUDIO,
            "cost": 380,
            "price": 549,
            "msrp": 599,
            "map": 499,
        },
        {
            "sku": "AU-BOSEQC",
            "name": "Bose QuietComfort Ultra",
            "category": ProductCategory.AUDIO,
            "cost": 450,
            "price": 649,
            "msrp": 699,
            "map": 599,
        },
        {
            "sku": "AU-JBLFLIP",
            "name": "JBL Flip 6 Speaker",
            "category": ProductCategory.AUDIO,
            "cost": 85,
            "price": 149,
            "msrp": 169,
            "map": 129,
        },
        # Wearables
        {
            "sku": "WR-AW9-45",
            "name": "Apple Watch Series 9 45mm",
            "category": ProductCategory.WEARABLES,
            "cost": 420,
            "price": 649,
            "msrp": 699,
            "map": 599,
        },
        {
            "sku": "WR-AWULTRA",
            "name": "Apple Watch Ultra 2",
            "category": ProductCategory.WEARABLES,
            "cost": 950,
            "price": 1399,
            "msrp": 1499,
            "map": 1349,
        },
        {
            "sku": "WR-SAMW6",
            "name": "Samsung Galaxy Watch 6",
            "category": ProductCategory.WEARABLES,
            "cost": 310,
            "price": 479,
            "msrp": 529,
            "map": 449,
        },
        {
            "sku": "WR-GARMIN",
            "name": "Garmin Fenix 7X",
            "category": ProductCategory.WEARABLES,
            "cost": 800,
            "price": 1199,
            "msrp": 1299,
            "map": 1149,
        },
        # Gaming
        {
            "sku": "GM-PS5",
            "name": "PlayStation 5 Console",
            "category": ProductCategory.GAMING,
            "cost": 650,
            "price": 799,
            "msrp": 799,
            "map": 799,
        },
        {
            "sku": "GM-XBOXSX",
            "name": "Xbox Series X Console",
            "category": ProductCategory.GAMING,
            "cost": 650,
            "price": 799,
            "msrp": 799,
            "map": 799,
        },
        {
            "sku": "GM-SWITCH",
            "name": "Nintendo Switch OLED",
            "category": ProductCategory.GAMING,
            "cost": 420,
            "price": 539,
            "msrp": 549,
            "map": 529,
        },
        {
            "sku": "GM-STEADK",
            "name": "Steam Deck 512GB",
            "category": ProductCategory.GAMING,
            "cost": 700,
            "price": 899,
            "msrp": 949,
            "map": 879,
        },
        {
            "sku": "GM-HEADSET",
            "name": "Gaming Headset Pro",
            "category": ProductCategory.GAMING,
            "cost": 150,
            "price": 249,
            "msrp": 279,
            "map": 229,
        },
        # Cameras
        {
            "sku": "CM-SONYZV",
            "name": "Sony ZV-E10 Camera",
            "category": ProductCategory.CAMERAS,
            "cost": 750,
            "price": 1049,
            "msrp": 1149,
            "map": 999,
        },
        {
            "sku": "CM-CANON",
            "name": "Canon EOS R50 Mirrorless",
            "category": ProductCategory.CAMERAS,
            "cost": 850,
            "price": 1199,
            "msrp": 1299,
            "map": 1149,
        },
        {
            "sku": "CM-GOPRO",
            "name": "GoPro HERO12 Black",
            "category": ProductCategory.CAMERAS,
            "cost": 450,
            "price": 649,
            "msrp": 699,
            "map": 599,
        },
        {
            "sku": "CM-DJI4PRO",
            "name": "DJI Mavic 3 Pro Drone",
            "category": ProductCategory.CAMERAS,
            "cost": 2200,
            "price": 3099,
            "msrp": 3399,
            "map": 2999,
        },
        # Accessories
        {
            "sku": "AC-LOGIMX",
            "name": "Logitech MX Master 3S",
            "category": ProductCategory.ACCESSORIES,
            "cost": 100,
            "price": 169,
            "msrp": 179,
            "map": 149,
        },
        {
            "sku": "AC-WEBCAM",
            "name": "4K Webcam Pro",
            "category": ProductCategory.ACCESSORIES,
            "cost": 110,
            "price": 199,
            "msrp": 229,
            "map": 179,
        },
        {
            "sku": "AC-MONITOR",
            "name": "27-inch 4K Monitor",
            "category": ProductCategory.ACCESSORIES,
            "cost": 380,
            "price": 549,
            "msrp": 599,
            "map": 499,
        },
        {
            "sku": "AC-USBHUB",
            "name": "USB-C Hub 7-in-1",
            "category": ProductCategory.ACCESSORIES,
            "cost": 45,
            "price": 89,
            "msrp": 99,
            "map": 79,
        },
        # Home Automation
        {
            "sku": "HA-HOMEPOD",
            "name": "HomePod Mini",
            "category": ProductCategory.HOME_AUTOMATION,
            "cost": 95,
            "price": 149,
            "msrp": 149,
            "map": 139,
        },
        {
            "sku": "HA-NESTCAM",
            "name": "Nest Cam Indoor",
            "category": ProductCategory.HOME_AUTOMATION,
            "cost": 110,
            "price": 179,
            "msrp": 199,
            "map": 169,
        },
        {
            "sku": "HA-HUEKIT",
            "name": "Philips Hue Starter Kit",
            "category": ProductCategory.HOME_AUTOMATION,
            "cost": 160,
            "price": 249,
            "msrp": 279,
            "map": 229,
        },
        {
            "sku": "HA-RINGDB",
            "name": "Ring Video Doorbell Pro",
            "category": ProductCategory.HOME_AUTOMATION,
            "cost": 220,
            "price": 329,
            "msrp": 369,
            "map": 309,
        },
        # Cables & Chargers
        {
            "sku": "CC-MAGSAFE",
            "name": "MagSafe Charger",
            "category": ProductCategory.CABLES_CHARGERS,
            "cost": 30,
            "price": 59,
            "msrp": 59,
            "map": 49,
        },
        {
            "sku": "CC-USBCPD",
            "name": "USB-C 100W PD Charger",
            "category": ProductCategory.CABLES_CHARGERS,
            "cost": 40,
            "price": 79,
            "msrp": 89,
            "map": 69,
        },
        {
            "sku": "CC-POWERBNK",
            "name": "Power Bank 20000mAh",
            "category": ProductCategory.CABLES_CHARGERS,
            "cost": 35,
            "price": 79,
            "msrp": 89,
            "map": 69,
        },
        {
            "sku": "CC-WIRELESS",
            "name": "Wireless Charging Pad",
            "category": ProductCategory.CABLES_CHARGERS,
            "cost": 22,
            "price": 49,
            "msrp": 59,
            "map": 39,
        },
    ]

    COMPETITORS = [
        {
            "name": "Amazon AU",
            "website": "amazon.com.au",
            "position": "value",
            "reliability": 0.95,
        },
        {
            "name": "JB Hi-Fi",
            "website": "jbhifi.com.au",
            "position": "value",
            "reliability": 0.90,
        },
        {
            "name": "Harvey Norman",
            "website": "harveynorman.com.au",
            "position": "premium",
            "reliability": 0.85,
        },
        {
            "name": "Officeworks",
            "website": "officeworks.com.au",
            "position": "value",
            "reliability": 0.90,
        },
        {
            "name": "The Good Guys",
            "website": "thegoodguys.com.au",
            "position": "value",
            "reliability": 0.85,
        },
        {
            "name": "Kogan",
            "website": "kogan.com.au",
            "position": "discount",
            "reliability": 0.80,
        },
    ]

    def __init__(self, seed: int = 42):
        """Initialize generator."""
        random.seed(seed)
        self._product_id = 1000
        self._competitor_id = 100

    def create_products(self) -> list[Product]:
        """Create product catalog with pricing data."""
        products = []

        for p in self.PRODUCTS:
            self._product_id += 1

            # Generate realistic sales data
            base_sales = random.randint(5, 100)
            price_factor = 1 / (p["price"] / 500)  # Cheaper items sell more
            units_sold = int(base_sales * price_factor * random.uniform(0.5, 1.5))
            views = int(units_sold / random.uniform(0.02, 0.08))  # 2-8% conversion

            products.append(
                Product(
                    id=self._product_id,
                    sku=p["sku"],
                    name=p["name"],
                    category=p["category"],
                    cost=p["cost"],
                    price=p["price"],
                    msrp=p["msrp"],
                    map_price=p["map"],
                    stock_quantity=random.randint(5, 200),
                    units_sold_30d=units_sold,
                    views_30d=views,
                    is_featured=random.random() < 0.15,
                    days_in_stock=random.randint(10, 180),
                    last_price_change=datetime.now()
                    - timedelta(days=random.randint(1, 60)),
                )
            )

        return products

    def create_competitors(self) -> list[Competitor]:
        """Create competitor list."""
        competitors = []

        for c in self.COMPETITORS:
            self._competitor_id += 1
            competitors.append(
                Competitor(
                    id=self._competitor_id,
                    name=c["name"],
                    website=c["website"],
                    price_position=c["position"],
                    reliability=c["reliability"],
                    shipping_cost=random.choice([0, 9.95, 14.95]),
                    last_updated=datetime.now()
                    - timedelta(hours=random.randint(1, 48)),
                )
            )

        return competitors

    def create_competitor_prices(
        self, products: list[Product], competitors: list[Competitor]
    ) -> list[CompetitorPrice]:
        """Generate competitor price data."""
        prices = []

        for product in products:
            for competitor in competitors:
                # Not all competitors stock all products
                if random.random() < 0.7:  # 70% chance of stocking
                    # Price variance based on competitor position
                    if competitor.price_position == "premium":
                        variance = random.uniform(0.95, 1.10)
                    elif competitor.price_position == "discount":
                        variance = random.uniform(0.85, 0.98)
                    else:  # value
                        variance = random.uniform(0.92, 1.05)

                    comp_price = product.price * variance

                    # Don't go below MAP
                    comp_price = max(comp_price, product.map_price)

                    prices.append(
                        CompetitorPrice(
                            competitor=competitor,
                            product_sku=product.sku,
                            price=round(comp_price, 2),
                            in_stock=random.random() < 0.85,
                            url=f"https://{competitor.website}/p/{product.sku.lower()}",
                            last_scraped=datetime.now()
                            - timedelta(hours=random.randint(1, 24)),
                        )
                    )

        return prices


# =============================================================================
# PRICING RULES ENGINE
# =============================================================================


class PricingRulesEngine:
    """Dynamic pricing rules engine."""

    def __init__(self):
        """Initialize rules engine."""
        self.rules: list[PriceRule] = []
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Set up default pricing rules."""
        # Margin protection rule
        self.rules.append(
            PriceRule(
                id="rule_margin_min",
                name="Minimum Margin Protection",
                description="Ensure products maintain minimum 15% margin",
                priority=100,
                is_active=True,
                conditions={"margin_below": 15},
                action={"adjust_to_margin": 15},
            )
        )

        # Slow-moving inventory rule
        self.rules.append(
            PriceRule(
                id="rule_slow_mover",
                name="Slow Moving Inventory",
                description="Discount items with no sales in 30 days",
                priority=80,
                is_active=True,
                conditions={"units_sold_30d": 0, "days_in_stock_above": 60},
                action={"discount_percent": 15},
            )
        )

        # High stock rule
        self.rules.append(
            PriceRule(
                id="rule_overstock",
                name="Overstock Reduction",
                description="Reduce price when stock exceeds 90 days supply",
                priority=70,
                is_active=True,
                conditions={"days_of_stock_above": 90},
                action={"discount_percent": 10},
            )
        )

        # Competitor undercut rule
        self.rules.append(
            PriceRule(
                id="rule_competitor_match",
                name="Competitor Price Match",
                description="Match lowest competitor price within MAP",
                priority=60,
                is_active=True,
                conditions={"competitor_lower": True},
                action={"match_competitor": True, "respect_map": True},
            )
        )

        # Psychological pricing
        self.rules.append(
            PriceRule(
                id="rule_psychological",
                name="Psychological Pricing",
                description="Adjust prices to end in .99",
                priority=10,
                is_active=True,
                conditions={"always": True},
                action={"round_to_99": True},
            )
        )

    def add_rule(self, rule: PriceRule):
        """Add a pricing rule."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate_product(
        self,
        product: Product,
        competitor_prices: list[CompetitorPrice] = None,
        context: dict = None,
    ) -> Optional[PricingRecommendation]:
        """Evaluate all rules for a product and return recommendation."""
        recommendations = []

        for rule in self.rules:
            if not rule.is_active:
                continue

            rec = self._evaluate_rule(product, rule, competitor_prices, context)
            if rec:
                recommendations.append(rec)

        # Return highest confidence recommendation
        if recommendations:
            return max(recommendations, key=lambda r: r.confidence)
        return None

    def _evaluate_rule(
        self,
        product: Product,
        rule: PriceRule,
        competitor_prices: list[CompetitorPrice],
        context: dict,
    ) -> Optional[PricingRecommendation]:
        """Evaluate a single rule against a product."""
        conditions = rule.conditions
        action = rule.action

        # Check margin condition
        if "margin_below" in conditions:
            if product.margin >= conditions["margin_below"]:
                return None

            target_margin = action.get("adjust_to_margin", conditions["margin_below"])
            # Calculate price needed for target margin
            # margin = (price - cost) / price
            # price = cost / (1 - margin/100)
            new_price = product.cost / (1 - target_margin / 100)

            return PricingRecommendation(
                product=product,
                current_price=product.price,
                recommended_price=round(new_price, 2),
                change_percent=((new_price - product.price) / product.price) * 100,
                reason=f"Margin below {conditions['margin_below']}%, adjusting to {target_margin}%",
                confidence=0.95,
                projected_impact={"margin_improvement": target_margin - product.margin},
            )

        # Check slow mover condition
        if "units_sold_30d" in conditions and conditions["units_sold_30d"] == 0:
            if product.units_sold_30d > 0:
                return None
            if product.days_in_stock < conditions.get("days_in_stock_above", 60):
                return None

            discount = action.get("discount_percent", 10)
            new_price = product.price * (1 - discount / 100)

            # Respect MAP
            new_price = max(new_price, product.map_price)

            return PricingRecommendation(
                product=product,
                current_price=product.price,
                recommended_price=round(new_price, 2),
                change_percent=((new_price - product.price) / product.price) * 100,
                reason=f"No sales in 30 days, applying {discount}% clearance",
                confidence=0.85,
                projected_impact={"expected_velocity_increase": "2-3x"},
            )

        # Check overstock condition
        if "days_of_stock_above" in conditions:
            if product.days_of_stock < conditions["days_of_stock_above"]:
                return None

            discount = action.get("discount_percent", 10)
            new_price = product.price * (1 - discount / 100)
            new_price = max(new_price, product.map_price)

            return PricingRecommendation(
                product=product,
                current_price=product.price,
                recommended_price=round(new_price, 2),
                change_percent=((new_price - product.price) / product.price) * 100,
                reason=f"{product.days_of_stock} days of stock, reducing to improve turnover",
                confidence=0.80,
                projected_impact={"stock_velocity_increase": "1.5-2x"},
            )

        # Check competitor match
        if "competitor_lower" in conditions and competitor_prices:
            product_comp_prices = [
                cp
                for cp in competitor_prices
                if cp.product_sku == product.sku and cp.in_stock
            ]

            if not product_comp_prices:
                return None

            min_comp_price = min(cp.price for cp in product_comp_prices)

            if min_comp_price < product.price:
                new_price = min_comp_price - 1  # Beat by $1

                # Respect MAP if required
                if action.get("respect_map", True):
                    new_price = max(new_price, product.map_price)

                # Don't recommend if no change needed
                if new_price >= product.price:
                    return None

                return PricingRecommendation(
                    product=product,
                    current_price=product.price,
                    recommended_price=round(new_price, 2),
                    change_percent=((new_price - product.price) / product.price) * 100,
                    reason=f"Competitor at ${min_comp_price:.2f}, matching to stay competitive",
                    confidence=0.90,
                    projected_impact={"competitive_position": "improved"},
                )

        # Psychological pricing (always applies last)
        if "round_to_99" in action and action["round_to_99"]:
            # Round to nearest .99
            new_price = math.floor(product.price) + 0.99
            if new_price < product.price:
                new_price = math.ceil(product.price) - 0.01

            if abs(new_price - product.price) > 0.50:
                return None  # Don't change by more than 50 cents

            return PricingRecommendation(
                product=product,
                current_price=product.price,
                recommended_price=new_price,
                change_percent=((new_price - product.price) / product.price) * 100,
                reason="Psychological pricing adjustment",
                confidence=0.60,
                projected_impact={"perception": "better value"},
            )

        return None

    def get_active_rules(self) -> list[PriceRule]:
        """Get all active rules."""
        return [r for r in self.rules if r.is_active]


# =============================================================================
# MARGIN ANALYZER
# =============================================================================


class MarginAnalyzer:
    """Analyze and optimize product margins."""

    def __init__(self, target_margin: float = 25.0):
        """Initialize analyzer."""
        self.target_margin = target_margin

    def analyze_product(
        self, product: Product, competitor_prices: list[CompetitorPrice] = None
    ) -> MarginAnalysis:
        """Analyze margin for a single product."""
        current_margin = product.margin
        margin_gap = current_margin - self.target_margin

        # Calculate price needed for target margin
        recommended_price = product.cost / (1 - self.target_margin / 100)

        # Get competitor average
        competitor_avg = 0
        if competitor_prices:
            product_prices = [
                cp.price
                for cp in competitor_prices
                if cp.product_sku == product.sku and cp.in_stock
            ]
            if product_prices:
                competitor_avg = statistics.mean(product_prices)

        # Determine market position
        if competitor_avg > 0:
            price_diff_pct = ((product.price - competitor_avg) / competitor_avg) * 100
            if price_diff_pct > 5:
                position = "Premium (+{:.1f}%)".format(price_diff_pct)
            elif price_diff_pct < -5:
                position = "Discount ({:.1f}%)".format(price_diff_pct)
            else:
                position = "Market rate"
        else:
            position = "No competitor data"

        # Generate recommendation
        if current_margin < 10:
            recommendation = "CRITICAL: Margin too low, increase price urgently"
        elif current_margin < 20:
            recommendation = "WARNING: Below target, consider price increase"
        elif current_margin < self.target_margin:
            recommendation = "Review pricing, slightly below target"
        elif current_margin > 40:
            recommendation = "High margin - consider if price is competitive"
        else:
            recommendation = "Healthy margin, maintain current pricing"

        return MarginAnalysis(
            product=product,
            current_margin=current_margin,
            target_margin=self.target_margin,
            margin_gap=margin_gap,
            recommended_price=round(recommended_price, 2),
            competitor_avg=round(competitor_avg, 2),
            market_position=position,
            recommendation=recommendation,
        )

    def analyze_catalog(
        self, products: list[Product], competitor_prices: list[CompetitorPrice] = None
    ) -> dict[str, Any]:
        """Analyze entire catalog margins."""
        analyses = [self.analyze_product(p, competitor_prices) for p in products]

        margins = [a.current_margin for a in analyses]
        below_target = [a for a in analyses if a.current_margin < self.target_margin]
        critical = [a for a in analyses if a.current_margin < 10]
        healthy = [a for a in analyses if 20 <= a.current_margin <= 40]

        # Revenue impact if all adjusted to target
        current_revenue = sum(p.price * p.units_sold_30d for p in products)
        potential_revenue = sum(
            a.recommended_price * a.product.units_sold_30d for a in analyses
        )

        return {
            "total_products": len(products),
            "avg_margin": statistics.mean(margins),
            "min_margin": min(margins),
            "max_margin": max(margins),
            "below_target_count": len(below_target),
            "critical_count": len(critical),
            "healthy_count": len(healthy),
            "target_margin": self.target_margin,
            "current_revenue_30d": current_revenue,
            "potential_revenue_30d": potential_revenue,
            "revenue_opportunity": potential_revenue - current_revenue,
            "analyses": analyses,
        }

    def get_margin_distribution(self, products: list[Product]) -> dict[str, int]:
        """Get margin distribution buckets."""
        buckets = {
            "< 10%": 0,
            "10-20%": 0,
            "20-30%": 0,
            "30-40%": 0,
            "40-50%": 0,
            "> 50%": 0,
        }

        for product in products:
            margin = product.margin
            if margin < 10:
                buckets["< 10%"] += 1
            elif margin < 20:
                buckets["10-20%"] += 1
            elif margin < 30:
                buckets["20-30%"] += 1
            elif margin < 40:
                buckets["30-40%"] += 1
            elif margin < 50:
                buckets["40-50%"] += 1
            else:
                buckets["> 50%"] += 1

        return buckets

    def get_category_margins(
        self, products: list[Product]
    ) -> dict[ProductCategory, dict]:
        """Get average margin by category."""
        category_data: dict[ProductCategory, list] = {}

        for product in products:
            if product.category not in category_data:
                category_data[product.category] = []
            category_data[product.category].append(product)

        results = {}
        for category, prods in category_data.items():
            margins = [p.margin for p in prods]
            revenue = sum(p.price * p.units_sold_30d for p in prods)
            profit = sum(p.profit * p.units_sold_30d for p in prods)

            results[category] = {
                "product_count": len(prods),
                "avg_margin": statistics.mean(margins),
                "min_margin": min(margins),
                "max_margin": max(margins),
                "total_revenue": revenue,
                "total_profit": profit,
            }

        return results


# =============================================================================
# VOLUME DISCOUNT MANAGER
# =============================================================================


class VolumeDiscountManager:
    """Manage volume discounts and tiered pricing."""

    def __init__(self):
        """Initialize manager."""
        self.discount_tiers: dict[int, list[VolumeDiscount]] = {}  # Product ID -> tiers
        self.category_tiers: dict[ProductCategory, list[VolumeDiscount]] = {}

        self._setup_default_tiers()

    def _setup_default_tiers(self):
        """Set up default volume discount tiers."""
        # Default category tiers for accessories and cables
        self.category_tiers[ProductCategory.ACCESSORIES] = [
            VolumeDiscount(min_quantity=2, max_quantity=4, discount_percent=5),
            VolumeDiscount(min_quantity=5, max_quantity=9, discount_percent=10),
            VolumeDiscount(min_quantity=10, max_quantity=None, discount_percent=15),
        ]

        self.category_tiers[ProductCategory.CABLES_CHARGERS] = [
            VolumeDiscount(min_quantity=3, max_quantity=5, discount_percent=10),
            VolumeDiscount(min_quantity=6, max_quantity=10, discount_percent=15),
            VolumeDiscount(min_quantity=11, max_quantity=None, discount_percent=20),
        ]

    def set_product_tiers(self, product_id: int, tiers: list[VolumeDiscount]):
        """Set volume discount tiers for a product."""
        self.discount_tiers[product_id] = sorted(tiers, key=lambda t: t.min_quantity)

    def get_discount(self, product: Product, quantity: int) -> Optional[VolumeDiscount]:
        """Get applicable volume discount for a product and quantity."""
        # Check product-specific tiers first
        if product.id in self.discount_tiers:
            tiers = self.discount_tiers[product.id]
        elif product.category in self.category_tiers:
            tiers = self.category_tiers[product.category]
        else:
            return None

        applicable = None
        for tier in tiers:
            if quantity >= tier.min_quantity:
                if tier.max_quantity is None or quantity <= tier.max_quantity:
                    applicable = tier

        return applicable

    def calculate_price(self, product: Product, quantity: int) -> dict[str, Any]:
        """Calculate price with volume discount."""
        base_total = product.price * quantity
        discount = self.get_discount(product, quantity)

        if discount:
            if discount.discount_percent > 0:
                discount_amount = base_total * (discount.discount_percent / 100)
            else:
                discount_amount = discount.discount_fixed * quantity

            final_total = base_total - discount_amount
            unit_price = final_total / quantity
        else:
            discount_amount = 0
            final_total = base_total
            unit_price = product.price

        return {
            "quantity": quantity,
            "base_unit_price": product.price,
            "base_total": base_total,
            "discount_tier": discount,
            "discount_amount": round(discount_amount, 2),
            "final_total": round(final_total, 2),
            "effective_unit_price": round(unit_price, 2),
            "savings_percent": (
                (discount_amount / base_total * 100) if base_total > 0 else 0
            ),
        }

    def generate_tier_table(self, product: Product) -> list[dict]:
        """Generate pricing table for all tiers."""
        table = []

        # Get applicable tiers
        if product.id in self.discount_tiers:
            tiers = self.discount_tiers[product.id]
        elif product.category in self.category_tiers:
            tiers = self.category_tiers[product.category]
        else:
            return table

        # Single unit (no discount)
        table.append(
            {
                "quantity": "1",
                "unit_price": product.price,
                "discount": "0%",
                "total_example": product.price,
            }
        )

        for tier in tiers:
            qty_range = f"{tier.min_quantity}+"
            if tier.max_quantity:
                qty_range = f"{tier.min_quantity}-{tier.max_quantity}"

            discounted_price = product.price * (1 - tier.discount_percent / 100)
            example_qty = tier.min_quantity
            example_total = discounted_price * example_qty

            table.append(
                {
                    "quantity": qty_range,
                    "unit_price": round(discounted_price, 2),
                    "discount": f"{tier.discount_percent}%",
                    "total_example": round(example_total, 2),
                }
            )

        return table


# =============================================================================
# BUNDLE PRICING MANAGER
# =============================================================================


class BundlePricingManager:
    """Manage product bundles and bundle pricing."""

    def __init__(self):
        """Initialize manager."""
        self.bundles: list[BundleConfig] = []
        self._bundle_id = 0

    def create_bundle(
        self, name: str, products: list[Product], discount_percent: float = 10
    ) -> BundleConfig:
        """Create a product bundle."""
        self._bundle_id += 1

        individual_total = sum(p.price for p in products)
        bundle_price = individual_total * (1 - discount_percent / 100)

        bundle = BundleConfig(
            id=f"BUNDLE-{self._bundle_id:04d}",
            name=name,
            product_ids=[p.id for p in products],
            bundle_price=round(bundle_price, 2),
            individual_total=individual_total,
        )

        self.bundles.append(bundle)
        return bundle

    def get_bundle_margin(self, bundle: BundleConfig, products: list[Product]) -> float:
        """Calculate margin for a bundle."""
        bundle_products = [p for p in products if p.id in bundle.product_ids]
        total_cost = sum(p.cost for p in bundle_products)

        if bundle.bundle_price > 0:
            return ((bundle.bundle_price - total_cost) / bundle.bundle_price) * 100
        return 0.0

    def suggest_bundles(self, products: list[Product]) -> list[dict]:
        """Suggest potential product bundles based on common pairings."""
        suggestions = []

        # Phone + case + charger bundles
        phones = [p for p in products if p.category == ProductCategory.SMARTPHONES]
        chargers = [
            p for p in products if p.category == ProductCategory.CABLES_CHARGERS
        ]

        for phone in phones[:3]:  # Top 3 phones
            # Find matching charger
            charger = random.choice(chargers) if chargers else None

            if charger:
                individual = phone.price + charger.price
                bundle_price = individual * 0.92  # 8% bundle discount

                suggestions.append(
                    {
                        "name": f"{phone.name} Bundle",
                        "products": [phone, charger],
                        "individual_total": individual,
                        "bundle_price": round(bundle_price, 2),
                        "savings": round(individual - bundle_price, 2),
                        "savings_percent": 8,
                    }
                )

        # Laptop + accessories bundles
        laptops = [p for p in products if p.category == ProductCategory.LAPTOPS]
        accessories = [p for p in products if p.category == ProductCategory.ACCESSORIES]

        for laptop in laptops[:2]:
            # Find USB hub and mouse
            hub = next((a for a in accessories if "hub" in a.name.lower()), None)
            mouse = next((a for a in accessories if "mouse" in a.name.lower()), None)

            if hub and mouse:
                individual = laptop.price + hub.price + mouse.price
                bundle_price = individual * 0.90  # 10% bundle discount

                suggestions.append(
                    {
                        "name": f"{laptop.name} Productivity Bundle",
                        "products": [laptop, hub, mouse],
                        "individual_total": individual,
                        "bundle_price": round(bundle_price, 2),
                        "savings": round(individual - bundle_price, 2),
                        "savings_percent": 10,
                    }
                )

        # Audio bundles
        headphones = [
            p
            for p in products
            if p.category == ProductCategory.AUDIO and "headphone" in p.name.lower()
        ]

        for hp in headphones[:2]:
            charger = random.choice(chargers) if chargers else None

            if charger:
                individual = hp.price + charger.price
                bundle_price = individual * 0.93  # 7% bundle discount

                suggestions.append(
                    {
                        "name": f"{hp.name} Travel Bundle",
                        "products": [hp, charger],
                        "individual_total": individual,
                        "bundle_price": round(bundle_price, 2),
                        "savings": round(individual - bundle_price, 2),
                        "savings_percent": 7,
                    }
                )

        return suggestions


# =============================================================================
# SEASONAL PRICING MANAGER
# =============================================================================


class SeasonalPricingManager:
    """Manage seasonal pricing and promotions."""

    def __init__(self):
        """Initialize manager."""
        self.seasonal_rules: dict[SeasonType, dict] = self._setup_seasonal_rules()

    def _setup_seasonal_rules(self) -> dict[SeasonType, dict]:
        """Set up seasonal pricing rules."""
        return {
            SeasonType.BLACK_FRIDAY: {
                "discount_range": (20, 40),
                "categories": [
                    ProductCategory.SMARTPHONES,
                    ProductCategory.LAPTOPS,
                    ProductCategory.GAMING,
                ],
                "start_date": datetime(2024, 11, 29),
                "end_date": datetime(2024, 12, 2),
                "name": "Black Friday Sale",
            },
            SeasonType.CYBER_MONDAY: {
                "discount_range": (15, 30),
                "categories": list(ProductCategory),
                "start_date": datetime(2024, 12, 2),
                "end_date": datetime(2024, 12, 3),
                "name": "Cyber Monday Deals",
            },
            SeasonType.CHRISTMAS: {
                "discount_range": (10, 25),
                "categories": [
                    ProductCategory.AUDIO,
                    ProductCategory.WEARABLES,
                    ProductCategory.GAMING,
                ],
                "start_date": datetime(2024, 12, 1),
                "end_date": datetime(2024, 12, 24),
                "name": "Christmas Sale",
            },
            SeasonType.BOXING_DAY: {
                "discount_range": (30, 50),
                "categories": list(ProductCategory),
                "start_date": datetime(2024, 12, 26),
                "end_date": datetime(2024, 12, 31),
                "name": "Boxing Day Clearance",
            },
            SeasonType.EOFY: {
                "discount_range": (20, 40),
                "categories": [ProductCategory.LAPTOPS, ProductCategory.ACCESSORIES],
                "start_date": datetime(2024, 6, 15),
                "end_date": datetime(2024, 6, 30),
                "name": "End of Financial Year Sale",
            },
            SeasonType.BACK_TO_SCHOOL: {
                "discount_range": (10, 20),
                "categories": [
                    ProductCategory.LAPTOPS,
                    ProductCategory.TABLETS,
                    ProductCategory.ACCESSORIES,
                ],
                "start_date": datetime(2025, 1, 15),
                "end_date": datetime(2025, 2, 15),
                "name": "Back to School Sale",
            },
        }

    def get_current_season(self) -> Optional[SeasonType]:
        """Get current active seasonal period."""
        now = datetime.now()

        for season, rules in self.seasonal_rules.items():
            start = rules["start_date"].replace(year=now.year)
            end = rules["end_date"].replace(year=now.year)

            if start <= now <= end:
                return season

        return SeasonType.REGULAR

    def get_seasonal_price(
        self, product: Product, season: SeasonType = None
    ) -> dict[str, Any]:
        """Calculate seasonal price for a product."""
        if season is None:
            season = self.get_current_season()

        if season == SeasonType.REGULAR or season not in self.seasonal_rules:
            return {
                "product": product,
                "season": "Regular",
                "original_price": product.price,
                "seasonal_price": product.price,
                "discount": 0,
                "is_seasonal": False,
            }

        rules = self.seasonal_rules[season]

        # Check if product category is included
        if product.category not in rules["categories"]:
            return {
                "product": product,
                "season": rules["name"],
                "original_price": product.price,
                "seasonal_price": product.price,
                "discount": 0,
                "is_seasonal": False,
            }

        # Calculate discount
        min_discount, max_discount = rules["discount_range"]

        # Higher-priced items get larger discounts
        price_factor = min(product.price / 1000, 1)  # Max factor at $1000
        discount = min_discount + (max_discount - min_discount) * price_factor

        seasonal_price = product.price * (1 - discount / 100)

        # Ensure we don't go below MAP
        seasonal_price = max(seasonal_price, product.map_price)

        # Recalculate actual discount
        actual_discount = ((product.price - seasonal_price) / product.price) * 100

        return {
            "product": product,
            "season": rules["name"],
            "original_price": product.price,
            "seasonal_price": round(seasonal_price, 2),
            "discount": round(actual_discount, 1),
            "is_seasonal": True,
            "sale_ends": rules["end_date"],
        }

    def plan_seasonal_pricing(
        self, products: list[Product], season: SeasonType
    ) -> list[dict]:
        """Plan pricing for an upcoming season."""
        plan = []

        rules = self.seasonal_rules.get(season)
        if not rules:
            return plan

        for product in products:
            seasonal_data = self.get_seasonal_price(product, season)

            if seasonal_data["is_seasonal"]:
                # Calculate projected margin
                new_margin = (
                    (seasonal_data["seasonal_price"] - product.cost)
                    / seasonal_data["seasonal_price"]
                ) * 100

                plan.append(
                    {
                        **seasonal_data,
                        "current_margin": product.margin,
                        "seasonal_margin": round(new_margin, 1),
                        "margin_change": round(new_margin - product.margin, 1),
                    }
                )

        return plan


# =============================================================================
# CLEARANCE AUTOMATION
# =============================================================================


class ClearanceManager:
    """Manage clearance and end-of-life pricing."""

    def __init__(self, min_margin: float = 5.0):
        """Initialize clearance manager."""
        self.min_margin = min_margin
        self.clearance_stages = [
            {"days_threshold": 60, "discount": 15, "label": "Sale"},
            {"days_threshold": 90, "discount": 25, "label": "Clearance"},
            {"days_threshold": 120, "discount": 40, "label": "Final Clearance"},
            {"days_threshold": 180, "discount": 50, "label": "Last Chance"},
        ]

    def identify_clearance_candidates(self, products: list[Product]) -> list[dict]:
        """Identify products that should be on clearance."""
        candidates = []

        for product in products:
            # Check if slow moving and old stock
            if product.units_sold_30d < 3 and product.days_in_stock > 60:
                stage = self._get_clearance_stage(product)

                if stage:
                    discount = stage["discount"]
                    new_price = product.price * (1 - discount / 100)

                    # Ensure minimum margin
                    min_price = product.cost / (1 - self.min_margin / 100)
                    new_price = max(new_price, min_price)

                    # Also respect MAP
                    new_price = max(new_price, product.map_price)

                    # Recalculate actual discount
                    actual_discount = (
                        (product.price - new_price) / product.price
                    ) * 100
                    new_margin = ((new_price - product.cost) / new_price) * 100

                    candidates.append(
                        {
                            "product": product,
                            "current_price": product.price,
                            "clearance_price": round(new_price, 2),
                            "discount": round(actual_discount, 1),
                            "label": stage["label"],
                            "days_in_stock": product.days_in_stock,
                            "current_margin": round(product.margin, 1),
                            "clearance_margin": round(new_margin, 1),
                            "units_in_stock": product.stock_quantity,
                            "potential_revenue": round(
                                new_price * product.stock_quantity, 2
                            ),
                        }
                    )

        return sorted(candidates, key=lambda x: x["days_in_stock"], reverse=True)

    def _get_clearance_stage(self, product: Product) -> Optional[dict]:
        """Get appropriate clearance stage for product."""
        for stage in reversed(self.clearance_stages):
            if product.days_in_stock >= stage["days_threshold"]:
                return stage
        return None

    def calculate_write_off_risk(self, products: list[Product]) -> dict[str, Any]:
        """Calculate potential write-off risk for slow inventory."""
        candidates = self.identify_clearance_candidates(products)

        total_at_risk = sum(
            p.stock_quantity * p.cost for p in [c["product"] for c in candidates]
        )

        by_stage = {}
        for candidate in candidates:
            stage = candidate["label"]
            if stage not in by_stage:
                by_stage[stage] = {"count": 0, "value_at_cost": 0}
            by_stage[stage]["count"] += 1
            by_stage[stage]["value_at_cost"] += (
                candidate["product"].cost * candidate["product"].stock_quantity
            )

        return {
            "total_candidates": len(candidates),
            "total_at_risk_cost": round(total_at_risk, 2),
            "by_stage": by_stage,
            "oldest_days": max([c["days_in_stock"] for c in candidates], default=0),
            "candidates": candidates,
        }


# =============================================================================
# PRICE ELASTICITY ANALYZER
# =============================================================================


class ElasticityAnalyzer:
    """Analyze price elasticity concepts for products."""

    def __init__(self):
        """Initialize analyzer."""
        # Category elasticity estimates (higher = more price sensitive)
        self.category_elasticity = {
            ProductCategory.CABLES_CHARGERS: 2.5,  # Very price sensitive
            ProductCategory.ACCESSORIES: 2.0,
            ProductCategory.HOME_AUTOMATION: 1.8,
            ProductCategory.AUDIO: 1.5,
            ProductCategory.GAMING: 1.3,
            ProductCategory.WEARABLES: 1.2,
            ProductCategory.CAMERAS: 1.0,
            ProductCategory.TABLETS: 0.9,
            ProductCategory.SMARTPHONES: 0.8,  # Less price sensitive (brand loyalty)
            ProductCategory.LAPTOPS: 0.7,
        }

    def estimate_elasticity(self, product: Product) -> float:
        """Estimate price elasticity for a product."""
        base = self.category_elasticity.get(product.category, 1.0)

        # Adjust for price point (expensive items less elastic)
        if product.price > 1000:
            base *= 0.8
        elif product.price < 100:
            base *= 1.2

        # Adjust for conversion rate (popular items less elastic)
        if product.conversion_rate > 5:
            base *= 0.9
        elif product.conversion_rate < 1:
            base *= 1.1

        return round(base, 2)

    def project_demand_change(
        self, product: Product, price_change_percent: float
    ) -> dict[str, Any]:
        """Project demand change based on price change."""
        elasticity = self.estimate_elasticity(product)

        # Demand change = -elasticity * price change
        demand_change_percent = -elasticity * price_change_percent

        new_units = product.units_sold_30d * (1 + demand_change_percent / 100)
        new_units = max(0, new_units)  # Can't be negative

        new_price = product.price * (1 + price_change_percent / 100)

        current_revenue = product.price * product.units_sold_30d
        projected_revenue = new_price * new_units

        current_profit = product.profit * product.units_sold_30d
        projected_profit = (new_price - product.cost) * new_units

        return {
            "product": product.name,
            "elasticity": elasticity,
            "price_change_percent": price_change_percent,
            "current_price": product.price,
            "new_price": round(new_price, 2),
            "demand_change_percent": round(demand_change_percent, 1),
            "current_units": product.units_sold_30d,
            "projected_units": round(new_units, 0),
            "current_revenue_30d": round(current_revenue, 2),
            "projected_revenue_30d": round(projected_revenue, 2),
            "revenue_change": round(projected_revenue - current_revenue, 2),
            "current_profit_30d": round(current_profit, 2),
            "projected_profit_30d": round(projected_profit, 2),
            "profit_change": round(projected_profit - current_profit, 2),
        }

    def find_optimal_price(
        self, product: Product, price_range: tuple[float, float] = None
    ) -> dict[str, Any]:
        """Find optimal price for maximum profit."""
        if price_range is None:
            price_range = (product.map_price, product.msrp)

        min_price, max_price = price_range
        best_profit = 0
        optimal_price = product.price

        scenarios = []

        # Test prices in range
        step = (max_price - min_price) / 20
        current_price = min_price

        while current_price <= max_price:
            price_change = ((current_price - product.price) / product.price) * 100
            projection = self.project_demand_change(product, price_change)

            scenarios.append(
                {
                    "price": round(current_price, 2),
                    "projected_profit": projection["projected_profit_30d"],
                    "projected_units": projection["projected_units"],
                }
            )

            if projection["projected_profit_30d"] > best_profit:
                best_profit = projection["projected_profit_30d"]
                optimal_price = current_price

            current_price += step

        return {
            "product": product.name,
            "current_price": product.price,
            "optimal_price": round(optimal_price, 2),
            "optimal_change_percent": round(
                ((optimal_price - product.price) / product.price) * 100, 1
            ),
            "current_profit_30d": product.profit * product.units_sold_30d,
            "optimal_profit_30d": round(best_profit, 2),
            "profit_improvement": round(
                best_profit - (product.profit * product.units_sold_30d), 2
            ),
            "scenarios": scenarios,
        }


# =============================================================================
# DASHBOARD DISPLAY
# =============================================================================


class PricingDashboard:
    """Display pricing optimizer dashboard."""

    def __init__(
        self,
        rules_engine: PricingRulesEngine,
        margin_analyzer: MarginAnalyzer,
        volume_manager: VolumeDiscountManager,
        bundle_manager: BundlePricingManager,
        seasonal_manager: SeasonalPricingManager,
        clearance_manager: ClearanceManager,
        elasticity_analyzer: ElasticityAnalyzer,
    ):
        """Initialize dashboard."""
        self.rules_engine = rules_engine
        self.margin_analyzer = margin_analyzer
        self.volume_manager = volume_manager
        self.bundle_manager = bundle_manager
        self.seasonal_manager = seasonal_manager
        self.clearance_manager = clearance_manager
        self.elasticity_analyzer = elasticity_analyzer

    def format_currency(self, amount: float) -> str:
        return f"${amount:,.2f}"

    def format_percent(self, value: float) -> str:
        return f"{value:.1f}%"

    def show_overview(
        self, products: list[Product], competitor_prices: list[CompetitorPrice]
    ):
        """Show pricing overview dashboard."""
        print("\n" + "=" * 80)
        print("💰 PRICING OPTIMIZER DASHBOARD - Electronics Store")
        print("=" * 80)

        analysis = self.margin_analyzer.analyze_catalog(products, competitor_prices)

        print("\n" + "-" * 40)
        print("📊 MARGIN OVERVIEW")
        print("-" * 40)
        print(f"   Total Products:     {analysis['total_products']}")
        print(f"   Average Margin:     {self.format_percent(analysis['avg_margin'])}")
        print(f"   Min Margin:         {self.format_percent(analysis['min_margin'])}")
        print(f"   Max Margin:         {self.format_percent(analysis['max_margin'])}")
        print(
            f"   Target Margin:      {self.format_percent(analysis['target_margin'])}"
        )
        print(f"   Below Target:       {analysis['below_target_count']} products")
        print(f"   Critical (<10%):    {analysis['critical_count']} products")

        print("\n" + "-" * 40)
        print("💵 REVENUE METRICS (30 Days)")
        print("-" * 40)
        print(
            f"   Current Revenue:    {self.format_currency(analysis['current_revenue_30d'])}"
        )
        print(
            f"   Optimized Revenue:  {self.format_currency(analysis['potential_revenue_30d'])}"
        )
        print(
            f"   Revenue Opportunity:{self.format_currency(analysis['revenue_opportunity'])}"
        )

        # Active rules
        active_rules = self.rules_engine.get_active_rules()
        print("\n" + "-" * 40)
        print("📋 ACTIVE PRICING RULES")
        print("-" * 40)
        for rule in active_rules:
            print(f"   • {rule.name} (Priority: {rule.priority})")

        # Current season
        season = self.seasonal_manager.get_current_season()
        print("\n" + "-" * 40)
        print("🗓️ SEASONAL STATUS")
        print("-" * 40)
        if season == SeasonType.REGULAR:
            print("   Currently: Regular pricing")
        else:
            rules = self.seasonal_manager.seasonal_rules.get(season, {})
            print(f"   Active: {rules.get('name', season.value)}")
            print(f"   Discount Range: {rules.get('discount_range', (0, 0))}")

        # Clearance
        clearance = self.clearance_manager.calculate_write_off_risk(products)
        print("\n" + "-" * 40)
        print("🏷️ CLEARANCE STATUS")
        print("-" * 40)
        print(f"   Clearance Candidates: {clearance['total_candidates']}")
        print(
            f"   Value at Risk:        {self.format_currency(clearance['total_at_risk_cost'])}"
        )

    def show_margin_distribution(self, products: list[Product]):
        """Show margin distribution."""
        print("\n" + "=" * 80)
        print("📊 MARGIN DISTRIBUTION")
        print("=" * 80)

        distribution = self.margin_analyzer.get_margin_distribution(products)
        total = sum(distribution.values())

        print(f"\n{'Margin Range':<15} {'Count':<10} {'%':<10} {'Visual':<40}")
        print("-" * 75)

        for bucket, count in distribution.items():
            pct = (count / total * 100) if total > 0 else 0
            bar_len = int(pct / 2.5)
            bar = "█" * bar_len
            print(f"{bucket:<15} {count:<10} {pct:.1f}%{'':5} {bar}")

    def show_category_margins(self, products: list[Product]):
        """Show margins by category."""
        print("\n" + "=" * 80)
        print("📁 MARGIN BY CATEGORY")
        print("=" * 80)

        categories = self.margin_analyzer.get_category_margins(products)

        print(
            f"\n{'Category':<25} {'Products':<10} {'Avg Margin':<12} {'Revenue':<15} {'Profit':<15}"
        )
        print("-" * 80)

        sorted_cats = sorted(
            categories.items(), key=lambda x: x[1]["total_profit"], reverse=True
        )

        for category, data in sorted_cats:
            print(
                f"{category.value[:23]:<25} {data['product_count']:<10} {data['avg_margin']:.1f}%{'':6} {self.format_currency(data['total_revenue']):<15} {self.format_currency(data['total_profit']):<15}"
            )

    def show_pricing_recommendations(
        self, products: list[Product], competitor_prices: list[CompetitorPrice]
    ):
        """Show pricing recommendations."""
        print("\n" + "=" * 80)
        print("💡 PRICING RECOMMENDATIONS")
        print("=" * 80)

        recommendations = []
        for product in products:
            rec = self.rules_engine.evaluate_product(product, competitor_prices)
            if rec and abs(rec.change_percent) > 1:  # Only significant changes
                recommendations.append(rec)

        # Sort by impact
        recommendations.sort(key=lambda r: abs(r.change_percent), reverse=True)

        print(f"\n{len(recommendations)} products with pricing recommendations:\n")

        print(
            f"{'Product':<35} {'Current':<12} {'Recommended':<12} {'Change':<10} {'Reason':<35}"
        )
        print("-" * 105)

        for rec in recommendations[:15]:
            change_str = f"{rec.change_percent:+.1f}%"
            reason_short = rec.reason[:33]
            print(
                f"{rec.product.name[:33]:<35} {self.format_currency(rec.current_price):<12} {self.format_currency(rec.recommended_price):<12} {change_str:<10} {reason_short:<35}"
            )

    def show_competitor_comparison(
        self, products: list[Product], competitor_prices: list[CompetitorPrice]
    ):
        """Show competitor price comparison."""
        print("\n" + "=" * 80)
        print("🏪 COMPETITOR PRICE COMPARISON")
        print("=" * 80)

        print(
            f"\n{'Product':<30} {'Our Price':<12} {'Min Comp':<12} {'Avg Comp':<12} {'Max Comp':<12} {'Position':<15}"
        )
        print("-" * 95)

        for product in products[:15]:
            comp_prices = [
                cp
                for cp in competitor_prices
                if cp.product_sku == product.sku and cp.in_stock
            ]

            if comp_prices:
                min_comp = min(cp.price for cp in comp_prices)
                max_comp = max(cp.price for cp in comp_prices)
                avg_comp = statistics.mean(cp.price for cp in comp_prices)

                diff_pct = ((product.price - avg_comp) / avg_comp) * 100
                if diff_pct > 5:
                    position = f"Premium (+{diff_pct:.0f}%)"
                elif diff_pct < -5:
                    position = f"Below ({diff_pct:.0f}%)"
                else:
                    position = "Competitive"

                print(
                    f"{product.name[:28]:<30} {self.format_currency(product.price):<12} {self.format_currency(min_comp):<12} {self.format_currency(avg_comp):<12} {self.format_currency(max_comp):<12} {position:<15}"
                )
            else:
                print(
                    f"{product.name[:28]:<30} {self.format_currency(product.price):<12} {'N/A':<12} {'N/A':<12} {'N/A':<12} {'No data':<15}"
                )

    def show_bundle_suggestions(self, products: list[Product]):
        """Show bundle pricing suggestions."""
        print("\n" + "=" * 80)
        print("📦 BUNDLE PRICING SUGGESTIONS")
        print("=" * 80)

        suggestions = self.bundle_manager.suggest_bundles(products)

        for i, bundle in enumerate(suggestions, 1):
            print(f"\n{i}. {bundle['name']}")
            print(f"   Products: {', '.join(p.name[:20] for p in bundle['products'])}")
            print(
                f"   Individual Total: {self.format_currency(bundle['individual_total'])}"
            )
            print(f"   Bundle Price: {self.format_currency(bundle['bundle_price'])}")
            print(
                f"   Customer Saves: {self.format_currency(bundle['savings'])} ({bundle['savings_percent']}%)"
            )

    def show_clearance_candidates(self, products: list[Product]):
        """Show clearance candidates."""
        print("\n" + "=" * 80)
        print("🏷️ CLEARANCE CANDIDATES")
        print("=" * 80)

        risk = self.clearance_manager.calculate_write_off_risk(products)

        print(f"\n   Total candidates: {risk['total_candidates']}")
        print(
            f"   Total value at risk: {self.format_currency(risk['total_at_risk_cost'])}"
        )

        if risk["by_stage"]:
            print("\n   By Stage:")
            for stage, data in risk["by_stage"].items():
                print(
                    f"      {stage}: {data['count']} products, {self.format_currency(data['value_at_cost'])}"
                )

        if risk["candidates"]:
            print(
                f"\n{'Product':<35} {'Days':<8} {'Stock':<8} {'Current':<12} {'Clearance':<12} {'Discount':<10}"
            )
            print("-" * 90)

            for c in risk["candidates"][:10]:
                print(
                    f"{c['product'].name[:33]:<35} {c['days_in_stock']:<8} {c['units_in_stock']:<8} {self.format_currency(c['current_price']):<12} {self.format_currency(c['clearance_price']):<12} {c['discount']:.0f}%"
                )

    def show_elasticity_analysis(self, products: list[Product]):
        """Show price elasticity analysis."""
        print("\n" + "=" * 80)
        print("📈 PRICE ELASTICITY ANALYSIS")
        print("=" * 80)

        print("\nElasticity by Category (higher = more price sensitive):")
        print("-" * 50)

        sorted_cats = sorted(
            self.elasticity_analyzer.category_elasticity.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for category, elasticity in sorted_cats:
            bar_len = int(elasticity * 10)
            bar = "█" * bar_len
            sensitivity = (
                "Very High"
                if elasticity > 2
                else (
                    "High"
                    if elasticity > 1.5
                    else "Medium" if elasticity > 1 else "Low"
                )
            )
            print(f"   {category.value:<25} {elasticity:.1f} {bar} ({sensitivity})")

        # Show optimization example
        print("\n\nPrice Optimization Example:")
        print("-" * 50)

        sample = random.choice(
            [p for p in products if p.category == ProductCategory.ACCESSORIES]
        )
        optimal = self.elasticity_analyzer.find_optimal_price(sample)

        print(f"   Product: {optimal['product']}")
        print(f"   Current Price: {self.format_currency(optimal['current_price'])}")
        print(
            f"   Optimal Price: {self.format_currency(optimal['optimal_price'])} ({optimal['optimal_change_percent']:+.1f}%)"
        )
        print(
            f"   Current Profit/30d: {self.format_currency(optimal['current_profit_30d'])}"
        )
        print(
            f"   Optimal Profit/30d: {self.format_currency(optimal['optimal_profit_30d'])}"
        )
        print(
            f"   Profit Improvement: {self.format_currency(optimal['profit_improvement'])}"
        )


# =============================================================================
# INTERACTIVE MODE
# =============================================================================


class InteractivePricing:
    """Interactive pricing optimizer interface."""

    def __init__(
        self,
        dashboard: PricingDashboard,
        products: list[Product],
        competitor_prices: list[CompetitorPrice],
    ):
        """Initialize interface."""
        self.dashboard = dashboard
        self.products = products
        self.competitor_prices = competitor_prices

    def show_menu(self):
        """Display main menu."""
        print("\n" + "=" * 60)
        print("💰 PRICING OPTIMIZER - Interactive Mode")
        print("=" * 60)
        print("\nOptions:")
        print("  1. View Dashboard Overview")
        print("  2. View Margin Distribution")
        print("  3. View Category Margins")
        print("  4. View Pricing Recommendations")
        print("  5. View Competitor Comparison")
        print("  6. View Bundle Suggestions")
        print("  7. View Clearance Candidates")
        print("  8. View Elasticity Analysis")
        print("  9. Analyze Specific Product")
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
                    self.dashboard.show_overview(self.products, self.competitor_prices)
                elif choice == "2":
                    self.dashboard.show_margin_distribution(self.products)
                elif choice == "3":
                    self.dashboard.show_category_margins(self.products)
                elif choice == "4":
                    self.dashboard.show_pricing_recommendations(
                        self.products, self.competitor_prices
                    )
                elif choice == "5":
                    self.dashboard.show_competitor_comparison(
                        self.products, self.competitor_prices
                    )
                elif choice == "6":
                    self.dashboard.show_bundle_suggestions(self.products)
                elif choice == "7":
                    self.dashboard.show_clearance_candidates(self.products)
                elif choice == "8":
                    self.dashboard.show_elasticity_analysis(self.products)
                elif choice == "9":
                    self._analyze_product()
                else:
                    print("\n⚠ Invalid choice")

                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break

    def _analyze_product(self):
        """Analyze a specific product."""
        print("\nEnter product SKU or name fragment:")
        query = input("> ").strip().lower()

        matches = [
            p
            for p in self.products
            if query in p.sku.lower() or query in p.name.lower()
        ]

        if not matches:
            print("No products found.")
            return

        if len(matches) > 1:
            print("\nMultiple matches found:")
            for i, p in enumerate(matches[:10], 1):
                print(f"  {i}. {p.sku} - {p.name}")

            try:
                idx = int(input("\nSelect product number: ")) - 1
                product = matches[idx]
            except (ValueError, IndexError):
                print("Invalid selection.")
                return
        else:
            product = matches[0]

        print(f"\n📦 PRODUCT ANALYSIS: {product.name}")
        print("=" * 60)
        print(f"   SKU: {product.sku}")
        print(f"   Category: {product.category.value}")
        print(f"   Cost: ${product.cost:.2f}")
        print(f"   Price: ${product.price:.2f}")
        print(f"   MSRP: ${product.msrp:.2f}")
        print(f"   MAP: ${product.map_price:.2f}")
        print(f"   Margin: {product.margin:.1f}%")
        print(f"   Markup: {product.markup:.1f}%")
        print(f"   Stock: {product.stock_quantity} units")
        print(f"   Sales (30d): {product.units_sold_30d} units")
        print(f"   Views (30d): {product.views_30d}")
        print(f"   Conversion: {product.conversion_rate:.2f}%")
        print(f"   Days of Stock: {product.days_of_stock}")

        # Elasticity analysis
        elasticity = self.dashboard.elasticity_analyzer.estimate_elasticity(product)
        print(f"\n   Price Elasticity: {elasticity}")

        # Pricing recommendation
        rec = self.dashboard.rules_engine.evaluate_product(
            product, self.competitor_prices
        )
        if rec:
            print(f"\n💡 Recommendation:")
            print(f"   Suggested Price: ${rec.recommended_price:.2f}")
            print(f"   Change: {rec.change_percent:+.1f}%")
            print(f"   Reason: {rec.reason}")


# =============================================================================
# MAIN APPLICATION
# =============================================================================


def run_demo():
    """Run demo mode with sample data."""
    print("\n🚀 Initializing Pricing Optimizer...")
    print("   Generating demo data for electronics store...\n")

    # Generate demo data
    generator = DemoDataGenerator()
    products = generator.create_products()
    competitors = generator.create_competitors()
    competitor_prices = generator.create_competitor_prices(products, competitors)

    # Initialize components
    rules_engine = PricingRulesEngine()
    margin_analyzer = MarginAnalyzer(target_margin=25)
    volume_manager = VolumeDiscountManager()
    bundle_manager = BundlePricingManager()
    seasonal_manager = SeasonalPricingManager()
    clearance_manager = ClearanceManager()
    elasticity_analyzer = ElasticityAnalyzer()

    # Create dashboard
    dashboard = PricingDashboard(
        rules_engine,
        margin_analyzer,
        volume_manager,
        bundle_manager,
        seasonal_manager,
        clearance_manager,
        elasticity_analyzer,
    )

    # Show all views
    dashboard.show_overview(products, competitor_prices)
    dashboard.show_margin_distribution(products)
    dashboard.show_category_margins(products)
    dashboard.show_pricing_recommendations(products, competitor_prices)
    dashboard.show_competitor_comparison(products, competitor_prices)
    dashboard.show_bundle_suggestions(products)
    dashboard.show_clearance_candidates(products)
    dashboard.show_elasticity_analysis(products)

    print("\n" + "=" * 80)
    print("✅ Demo Complete!")
    print("=" * 80)


def run_interactive():
    """Run interactive mode."""
    print("\n🚀 Initializing Pricing Optimizer...")
    print("   Loading interactive mode...\n")

    # Generate demo data
    generator = DemoDataGenerator()
    products = generator.create_products()
    competitors = generator.create_competitors()
    competitor_prices = generator.create_competitor_prices(products, competitors)

    # Initialize components
    rules_engine = PricingRulesEngine()
    margin_analyzer = MarginAnalyzer(target_margin=25)
    volume_manager = VolumeDiscountManager()
    bundle_manager = BundlePricingManager()
    seasonal_manager = SeasonalPricingManager()
    clearance_manager = ClearanceManager()
    elasticity_analyzer = ElasticityAnalyzer()

    # Create dashboard
    dashboard = PricingDashboard(
        rules_engine,
        margin_analyzer,
        volume_manager,
        bundle_manager,
        seasonal_manager,
        clearance_manager,
        elasticity_analyzer,
    )

    # Run interactive
    interactive = InteractivePricing(dashboard, products, competitor_prices)
    interactive.run()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WooCommerce Pricing Optimizer - Dynamic pricing and margin analysis"
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
        "--analyze-margins", action="store_true", help="Show margin analysis report"
    )

    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Generate pricing optimization recommendations",
    )

    parser.add_argument(
        "--min-margin",
        type=float,
        default=25,
        help="Target minimum margin percentage (default: 25)",
    )

    parser.add_argument(
        "--export", type=str, metavar="FILE", help="Export recommendations to JSON file"
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.interactive:
        run_interactive()
    elif args.analyze_margins or args.optimize:
        generator = DemoDataGenerator()
        products = generator.create_products()

        margin_analyzer = MarginAnalyzer(target_margin=args.min_margin)
        analysis = margin_analyzer.analyze_catalog(products)

        print(f"\n📊 MARGIN ANALYSIS REPORT")
        print("=" * 50)
        print(f"   Products analyzed: {analysis['total_products']}")
        print(f"   Average margin: {analysis['avg_margin']:.1f}%")
        print(f"   Target margin: {analysis['target_margin']:.1f}%")
        print(f"   Below target: {analysis['below_target_count']}")
        print(f"   Critical: {analysis['critical_count']}")

        if args.export:
            export_data = {
                "generated_at": datetime.now().isoformat(),
                "target_margin": args.min_margin,
                "summary": {
                    "total_products": analysis["total_products"],
                    "avg_margin": analysis["avg_margin"],
                    "below_target": analysis["below_target_count"],
                },
            }
            with open(args.export, "w") as f:
                json.dump(export_data, f, indent=2)
            print(f"\n✅ Exported to {args.export}")
    else:
        run_demo()


if __name__ == "__main__":
    main()
