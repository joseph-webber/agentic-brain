#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WooCommerce Shipping & Logistics System
======================================

Comprehensive shipping and logistics management including:
- Carrier integration (generic carriers)
- Rate shopping / cheapest carrier selection
- Label generation workflow
- Tracking number management
- Delivery estimates
- International shipping (customs, duties)
- Shipping rules engine
- Bulk shipping processing

Australian-focused with realistic shipping workflows.

Usage:
    python 72_woo_shipping_logistics.py --demo
    python 72_woo_shipping_logistics.py --interactive
"""

import argparse
import asyncio
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

# =============================================================================
# ENUMS
# =============================================================================


class ShipmentStatus(Enum):
    """Shipment status."""

    PENDING = "pending"
    LABEL_CREATED = "label_created"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class CarrierType(Enum):
    """Carrier type."""

    DOMESTIC = "domestic"
    INTERNATIONAL = "international"
    EXPRESS = "express"
    FREIGHT = "freight"
    COURIER = "courier"


class ServiceLevel(Enum):
    """Service level."""

    ECONOMY = "economy"
    STANDARD = "standard"
    EXPRESS = "express"
    OVERNIGHT = "overnight"
    SAME_DAY = "same_day"


class ShippingRuleType(Enum):
    """Shipping rule type."""

    FREE_SHIPPING = "free_shipping"
    FLAT_RATE = "flat_rate"
    WEIGHT_BASED = "weight_based"
    PRICE_BASED = "price_based"
    ZONE_BASED = "zone_based"
    CARRIER_RESTRICTION = "carrier_restriction"
    PRODUCT_RESTRICTION = "product_restriction"


class CustomsContentType(Enum):
    """Customs content type."""

    MERCHANDISE = "merchandise"
    GIFT = "gift"
    SAMPLE = "sample"
    DOCUMENTS = "documents"
    RETURN = "return"


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Carrier:
    """Shipping carrier."""

    carrier_id: str
    name: str
    code: str
    carrier_type: CarrierType
    is_active: bool = True
    services: list[str] = field(default_factory=list)
    supported_countries: list[str] = field(default_factory=list)
    max_weight_kg: float = 30.0
    max_length_cm: float = 100.0
    insurance_available: bool = True
    tracking_url_template: str = ""
    api_endpoint: str = ""
    account_number: str = ""


@dataclass
class ShippingZone:
    """Shipping zone definition."""

    zone_id: str
    name: str
    countries: list[str]
    states: list[str] = field(default_factory=list)
    postcodes: list[str] = field(default_factory=list)
    is_domestic: bool = True


@dataclass
class ShippingRate:
    """Shipping rate."""

    rate_id: str
    carrier_id: str
    service_code: str
    service_name: str
    zone_id: str
    base_rate_aud: float
    per_kg_rate_aud: float = 0.0
    min_weight_kg: float = 0.0
    max_weight_kg: float = 30.0
    estimated_days_min: int = 1
    estimated_days_max: int = 5
    insurance_rate_pct: float = 1.5
    fuel_surcharge_pct: float = 0.0
    is_active: bool = True


@dataclass
class Address:
    """Shipping address."""

    name: str
    company: str = ""
    street1: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    postcode: str = ""
    country: str = "AU"
    phone: str = ""
    email: str = ""
    is_residential: bool = True


@dataclass
class Package:
    """Package for shipping."""

    package_id: str
    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float
    declared_value_aud: float
    description: str = ""
    contains_dangerous_goods: bool = False
    requires_signature: bool = False
    is_fragile: bool = False


@dataclass
class CustomsItem:
    """Customs line item."""

    description: str
    quantity: int
    unit_value_aud: float
    weight_kg: float
    hs_code: str = ""
    country_of_origin: str = "AU"


@dataclass
class CustomsDeclaration:
    """Customs declaration for international."""

    declaration_id: str
    content_type: CustomsContentType
    items: list[CustomsItem]
    total_value_aud: float
    currency: str = "AUD"
    incoterm: str = "DDU"  # Delivered Duty Unpaid
    eori_number: str = ""
    export_licence: str = ""
    notes: str = ""


@dataclass
class ShippingLabel:
    """Shipping label."""

    label_id: str
    carrier_id: str
    tracking_number: str
    service_code: str
    label_format: str = "PDF"  # PDF, ZPL, PNG
    label_data: str = ""  # Base64 encoded
    label_url: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    void_date: Optional[datetime] = None


@dataclass
class TrackingEvent:
    """Tracking event."""

    event_id: str
    tracking_number: str
    timestamp: datetime
    status: ShipmentStatus
    location: str
    description: str
    signed_by: str = ""


@dataclass
class Shipment:
    """Shipment record."""

    shipment_id: str
    order_id: str
    carrier_id: str
    service_code: str
    status: ShipmentStatus
    tracking_number: str = ""
    from_address: Address = None
    to_address: Address = None
    packages: list[Package] = field(default_factory=list)
    customs: Optional[CustomsDeclaration] = None
    label: Optional[ShippingLabel] = None
    shipping_cost_aud: float = 0.0
    insurance_cost_aud: float = 0.0
    total_cost_aud: float = 0.0
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    shipped_at: Optional[datetime] = None
    events: list[TrackingEvent] = field(default_factory=list)


@dataclass
class ShippingRule:
    """Shipping rule."""

    rule_id: str
    name: str
    rule_type: ShippingRuleType
    priority: int
    is_active: bool = True
    conditions: dict = field(default_factory=dict)
    actions: dict = field(default_factory=dict)
    applies_to_zones: list[str] = field(default_factory=list)


@dataclass
class RateQuote:
    """Rate quote from carrier."""

    quote_id: str
    carrier_id: str
    carrier_name: str
    service_code: str
    service_name: str
    base_cost_aud: float
    fuel_surcharge_aud: float
    insurance_aud: float
    gst_aud: float
    total_cost_aud: float
    estimated_days_min: int
    estimated_days_max: int
    estimated_delivery: datetime
    valid_until: datetime
    warnings: list[str] = field(default_factory=list)


@dataclass
class BulkShipment:
    """Bulk shipping batch."""

    batch_id: str
    name: str
    shipments: list[str]  # Shipment IDs
    status: str = "pending"  # pending, processing, completed, partial
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    total_labels: int = 0
    successful_labels: int = 0
    failed_labels: int = 0
    errors: list[dict] = field(default_factory=list)


# =============================================================================
# SHIPPING LOGISTICS SERVICE
# =============================================================================


class ShippingLogisticsService:
    """Shipping and logistics management service."""

    def __init__(self):
        self.carriers: dict[str, Carrier] = {}
        self.zones: dict[str, ShippingZone] = {}
        self.rates: dict[str, ShippingRate] = {}
        self.shipments: dict[str, Shipment] = {}
        self.labels: dict[str, ShippingLabel] = {}
        self.rules: dict[str, ShippingRule] = {}
        self.bulk_batches: dict[str, BulkShipment] = {}
        self.tracking_events: list[TrackingEvent] = []

        # Default warehouse address (Australian)
        self.warehouse_address = Address(
            name="Electronics Warehouse",
            company="Tech Store Pty Ltd",
            street1="123 Industrial Drive",
            city="Melbourne",
            state="VIC",
            postcode="3000",
            country="AU",
            phone="1300 123 456",
            email="shipping@techstore.com.au",
            is_residential=False,
        )

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = (
            hashlib.md5(f"{timestamp}{random.random()}".encode())
            .hexdigest()[:6]
            .upper()
        )
        return f"{prefix}-{timestamp}-{random_suffix}"

    def _generate_tracking_number(self, carrier_code: str) -> str:
        """Generate realistic tracking number."""
        prefix_map = {
            "FASTSHIP": "FS",
            "ECOPOST": "EP",
            "SPEEDEX": "SX",
            "GLOBALFREIGHT": "GF",
            "AUSPOST": "AP",
            "COURIER1": "C1",
        }
        prefix = prefix_map.get(carrier_code, "XX")
        number = "".join([str(random.randint(0, 9)) for _ in range(12)])
        return f"{prefix}{number}AU"

    # -------------------------------------------------------------------------
    # Carrier Management
    # -------------------------------------------------------------------------

    def create_carrier(
        self,
        name: str,
        code: str,
        carrier_type: CarrierType,
        services: list[str],
        supported_countries: list[str],
        max_weight_kg: float = 30.0,
        tracking_url_template: str = "",
    ) -> Carrier:
        """Create a carrier."""
        carrier = Carrier(
            carrier_id=self._generate_id("CAR"),
            name=name,
            code=code,
            carrier_type=carrier_type,
            services=services,
            supported_countries=supported_countries,
            max_weight_kg=max_weight_kg,
            tracking_url_template=tracking_url_template,
        )
        self.carriers[carrier.carrier_id] = carrier
        return carrier

    def get_carrier(self, carrier_id: str) -> Optional[Carrier]:
        """Get carrier by ID."""
        return self.carriers.get(carrier_id)

    def get_carrier_by_code(self, code: str) -> Optional[Carrier]:
        """Get carrier by code."""
        for carrier in self.carriers.values():
            if carrier.code == code:
                return carrier
        return None

    def list_active_carriers(self, country: Optional[str] = None) -> list[Carrier]:
        """List active carriers, optionally filtered by destination country."""
        carriers = [c for c in self.carriers.values() if c.is_active]
        if country:
            carriers = [c for c in carriers if country in c.supported_countries]
        return carriers

    # -------------------------------------------------------------------------
    # Zone Management
    # -------------------------------------------------------------------------

    def create_zone(
        self,
        name: str,
        countries: list[str],
        states: list[str] = None,
        postcodes: list[str] = None,
        is_domestic: bool = True,
    ) -> ShippingZone:
        """Create a shipping zone."""
        zone = ShippingZone(
            zone_id=self._generate_id("ZONE"),
            name=name,
            countries=countries,
            states=states or [],
            postcodes=postcodes or [],
            is_domestic=is_domestic,
        )
        self.zones[zone.zone_id] = zone
        return zone

    def find_zone_for_address(self, address: Address) -> Optional[ShippingZone]:
        """Find the shipping zone for an address."""
        for zone in self.zones.values():
            # Check country
            if address.country not in zone.countries:
                continue

            # Check state if specified
            if zone.states and address.state not in zone.states:
                continue

            # Check postcode if specified
            if zone.postcodes:
                # Check postcode prefix match
                matches = False
                for prefix in zone.postcodes:
                    if address.postcode.startswith(prefix):
                        matches = True
                        break
                if not matches:
                    continue

            return zone

        return None

    # -------------------------------------------------------------------------
    # Rate Management
    # -------------------------------------------------------------------------

    def create_rate(
        self,
        carrier_id: str,
        service_code: str,
        service_name: str,
        zone_id: str,
        base_rate_aud: float,
        per_kg_rate_aud: float = 0.0,
        estimated_days_min: int = 1,
        estimated_days_max: int = 5,
        **kwargs,
    ) -> ShippingRate:
        """Create a shipping rate."""
        rate = ShippingRate(
            rate_id=self._generate_id("RATE"),
            carrier_id=carrier_id,
            service_code=service_code,
            service_name=service_name,
            zone_id=zone_id,
            base_rate_aud=base_rate_aud,
            per_kg_rate_aud=per_kg_rate_aud,
            estimated_days_min=estimated_days_min,
            estimated_days_max=estimated_days_max,
            min_weight_kg=kwargs.get("min_weight_kg", 0.0),
            max_weight_kg=kwargs.get("max_weight_kg", 30.0),
            insurance_rate_pct=kwargs.get("insurance_rate_pct", 1.5),
            fuel_surcharge_pct=kwargs.get("fuel_surcharge_pct", 0.0),
        )
        self.rates[rate.rate_id] = rate
        return rate

    def get_rates_for_zone(
        self, zone_id: str, weight_kg: float = 1.0
    ) -> list[ShippingRate]:
        """Get applicable rates for a zone and weight."""
        applicable = []
        for rate in self.rates.values():
            if rate.zone_id == zone_id and rate.is_active:
                if rate.min_weight_kg <= weight_kg <= rate.max_weight_kg:
                    applicable.append(rate)
        return applicable

    # -------------------------------------------------------------------------
    # Rate Shopping
    # -------------------------------------------------------------------------

    def get_rate_quotes(
        self,
        to_address: Address,
        packages: list[Package],
        include_insurance: bool = False,
    ) -> list[RateQuote]:
        """Get rate quotes from all carriers."""
        zone = self.find_zone_for_address(to_address)
        if not zone:
            return []

        # Calculate totals
        total_weight = sum(p.weight_kg for p in packages)
        total_value = sum(p.declared_value_aud for p in packages)

        quotes = []

        for rate in self.rates.values():
            if rate.zone_id != zone.zone_id or not rate.is_active:
                continue

            if not (rate.min_weight_kg <= total_weight <= rate.max_weight_kg):
                continue

            carrier = self.carriers.get(rate.carrier_id)
            if not carrier or not carrier.is_active:
                continue

            # Calculate costs
            base_cost = rate.base_rate_aud + (total_weight * rate.per_kg_rate_aud)
            fuel_surcharge = base_cost * (rate.fuel_surcharge_pct / 100)
            insurance = 0.0
            if include_insurance:
                insurance = total_value * (rate.insurance_rate_pct / 100)

            subtotal = base_cost + fuel_surcharge + insurance
            gst = subtotal * 0.1  # 10% GST for Australian domestic

            if to_address.country != "AU":
                gst = 0.0  # No GST on exports

            total = subtotal + gst

            # Calculate delivery estimate
            datetime.now() + timedelta(days=rate.estimated_days_min)
            delivery_max = datetime.now() + timedelta(days=rate.estimated_days_max)

            quote = RateQuote(
                quote_id=self._generate_id("QUOTE"),
                carrier_id=rate.carrier_id,
                carrier_name=carrier.name,
                service_code=rate.service_code,
                service_name=rate.service_name,
                base_cost_aud=round(base_cost, 2),
                fuel_surcharge_aud=round(fuel_surcharge, 2),
                insurance_aud=round(insurance, 2),
                gst_aud=round(gst, 2),
                total_cost_aud=round(total, 2),
                estimated_days_min=rate.estimated_days_min,
                estimated_days_max=rate.estimated_days_max,
                estimated_delivery=delivery_max,
                valid_until=datetime.now() + timedelta(hours=24),
            )
            quotes.append(quote)

        # Sort by total cost
        quotes.sort(key=lambda q: q.total_cost_aud)
        return quotes

    def get_cheapest_rate(
        self,
        to_address: Address,
        packages: list[Package],
        max_days: Optional[int] = None,
    ) -> Optional[RateQuote]:
        """Get cheapest rate, optionally with delivery time constraint."""
        quotes = self.get_rate_quotes(to_address, packages)

        if max_days:
            quotes = [q for q in quotes if q.estimated_days_max <= max_days]

        return quotes[0] if quotes else None

    def get_fastest_rate(
        self, to_address: Address, packages: list[Package]
    ) -> Optional[RateQuote]:
        """Get fastest delivery rate."""
        quotes = self.get_rate_quotes(to_address, packages)
        if not quotes:
            return None

        quotes.sort(key=lambda q: q.estimated_days_min)
        return quotes[0]

    # -------------------------------------------------------------------------
    # Shipping Rules Engine
    # -------------------------------------------------------------------------

    def create_rule(
        self,
        name: str,
        rule_type: ShippingRuleType,
        conditions: dict,
        actions: dict,
        priority: int = 10,
        applies_to_zones: list[str] = None,
    ) -> ShippingRule:
        """Create a shipping rule."""
        rule = ShippingRule(
            rule_id=self._generate_id("RULE"),
            name=name,
            rule_type=rule_type,
            priority=priority,
            conditions=conditions,
            actions=actions,
            applies_to_zones=applies_to_zones or [],
        )
        self.rules[rule.rule_id] = rule
        return rule

    def apply_shipping_rules(
        self,
        order_total_aud: float,
        order_weight_kg: float,
        to_address: Address,
        product_categories: list[str] = None,
    ) -> dict:
        """Apply shipping rules to determine shipping method/cost."""
        zone = self.find_zone_for_address(to_address)

        result = {
            "free_shipping": False,
            "flat_rate": None,
            "carrier_restrictions": [],
            "product_restrictions": [],
            "applied_rules": [],
        }

        # Sort rules by priority
        sorted_rules = sorted(
            [r for r in self.rules.values() if r.is_active], key=lambda r: r.priority
        )

        for rule in sorted_rules:
            # Check zone applicability
            if rule.applies_to_zones:
                if not zone or zone.zone_id not in rule.applies_to_zones:
                    continue

            # Evaluate conditions
            conditions_met = True

            if "min_order_value" in rule.conditions:
                if order_total_aud < rule.conditions["min_order_value"]:
                    conditions_met = False

            if "max_order_value" in rule.conditions:
                if order_total_aud > rule.conditions["max_order_value"]:
                    conditions_met = False

            if "max_weight" in rule.conditions:
                if order_weight_kg > rule.conditions["max_weight"]:
                    conditions_met = False

            if "country" in rule.conditions:
                if to_address.country not in rule.conditions["country"]:
                    conditions_met = False

            if "categories" in rule.conditions and product_categories:
                required_cats = rule.conditions["categories"]
                if not any(c in required_cats for c in product_categories):
                    conditions_met = False

            if not conditions_met:
                continue

            # Apply actions
            result["applied_rules"].append(rule.name)

            if rule.rule_type == ShippingRuleType.FREE_SHIPPING:
                result["free_shipping"] = True
                if "carrier" in rule.actions:
                    result["free_shipping_carrier"] = rule.actions["carrier"]

            elif rule.rule_type == ShippingRuleType.FLAT_RATE:
                result["flat_rate"] = rule.actions.get("rate", 0.0)

            elif rule.rule_type == ShippingRuleType.CARRIER_RESTRICTION:
                result["carrier_restrictions"].extend(
                    rule.actions.get("excluded_carriers", [])
                )

            elif rule.rule_type == ShippingRuleType.PRODUCT_RESTRICTION:
                result["product_restrictions"].append(
                    {"rule": rule.name, "restriction": rule.actions}
                )

        return result

    # -------------------------------------------------------------------------
    # Shipment Management
    # -------------------------------------------------------------------------

    def create_shipment(
        self,
        order_id: str,
        carrier_id: str,
        service_code: str,
        to_address: Address,
        packages: list[Package],
        from_address: Address = None,
    ) -> Shipment:
        """Create a shipment."""
        shipment = Shipment(
            shipment_id=self._generate_id("SHIP"),
            order_id=order_id,
            carrier_id=carrier_id,
            service_code=service_code,
            status=ShipmentStatus.PENDING,
            from_address=from_address or self.warehouse_address,
            to_address=to_address,
            packages=packages,
        )
        self.shipments[shipment.shipment_id] = shipment
        return shipment

    def get_shipment(self, shipment_id: str) -> Optional[Shipment]:
        """Get shipment by ID."""
        return self.shipments.get(shipment_id)

    def get_shipments_for_order(self, order_id: str) -> list[Shipment]:
        """Get all shipments for an order."""
        return [s for s in self.shipments.values() if s.order_id == order_id]

    # -------------------------------------------------------------------------
    # International / Customs
    # -------------------------------------------------------------------------

    def create_customs_declaration(
        self, content_type: CustomsContentType, items: list[dict], incoterm: str = "DDU"
    ) -> CustomsDeclaration:
        """Create customs declaration for international shipment."""
        customs_items = []
        total_value = 0.0

        for item in items:
            ci = CustomsItem(
                description=item["description"],
                quantity=item["quantity"],
                unit_value_aud=item["unit_value"],
                weight_kg=item["weight_kg"],
                hs_code=item.get("hs_code", ""),
                country_of_origin=item.get("origin", "AU"),
            )
            customs_items.append(ci)
            total_value += ci.quantity * ci.unit_value_aud

        declaration = CustomsDeclaration(
            declaration_id=self._generate_id("CUST"),
            content_type=content_type,
            items=customs_items,
            total_value_aud=total_value,
            incoterm=incoterm,
        )
        return declaration

    def add_customs_to_shipment(
        self, shipment_id: str, customs: CustomsDeclaration
    ) -> bool:
        """Add customs declaration to shipment."""
        shipment = self.shipments.get(shipment_id)
        if not shipment:
            return False

        shipment.customs = customs
        return True

    def estimate_duties_taxes(
        self,
        destination_country: str,
        total_value_aud: float,
        product_category: str = "electronics",
    ) -> dict:
        """Estimate duties and taxes for international shipment."""
        # Simplified duty rates (real rates vary by country and product)
        duty_rates = {
            "US": {"duty_pct": 0.0, "tax_pct": 0.0, "de_minimis_aud": 1200},
            "UK": {"duty_pct": 2.5, "tax_pct": 20.0, "de_minimis_aud": 200},
            "NZ": {"duty_pct": 0.0, "tax_pct": 15.0, "de_minimis_aud": 600},
            "SG": {"duty_pct": 0.0, "tax_pct": 8.0, "de_minimis_aud": 600},
            "JP": {"duty_pct": 0.0, "tax_pct": 10.0, "de_minimis_aud": 250},
            "DE": {"duty_pct": 2.5, "tax_pct": 19.0, "de_minimis_aud": 200},
            "CA": {"duty_pct": 0.0, "tax_pct": 5.0, "de_minimis_aud": 30},
        }

        rates = duty_rates.get(
            destination_country,
            {"duty_pct": 5.0, "tax_pct": 15.0, "de_minimis_aud": 100},
        )

        result = {
            "destination_country": destination_country,
            "declared_value_aud": total_value_aud,
            "de_minimis_threshold_aud": rates["de_minimis_aud"],
            "duty_rate_pct": rates["duty_pct"],
            "tax_rate_pct": rates["tax_pct"],
            "estimated_duty_aud": 0.0,
            "estimated_tax_aud": 0.0,
            "below_de_minimis": False,
        }

        if total_value_aud <= rates["de_minimis_aud"]:
            result["below_de_minimis"] = True
            result["note"] = "No duties/taxes expected (below de minimis threshold)"
        else:
            result["estimated_duty_aud"] = round(
                total_value_aud * (rates["duty_pct"] / 100), 2
            )
            result["estimated_tax_aud"] = round(
                (total_value_aud + result["estimated_duty_aud"])
                * (rates["tax_pct"] / 100),
                2,
            )
            result["total_duties_taxes_aud"] = round(
                result["estimated_duty_aud"] + result["estimated_tax_aud"], 2
            )

        return result

    # -------------------------------------------------------------------------
    # Label Generation
    # -------------------------------------------------------------------------

    def generate_label(
        self, shipment_id: str, label_format: str = "PDF"
    ) -> Optional[ShippingLabel]:
        """Generate shipping label for a shipment."""
        shipment = self.shipments.get(shipment_id)
        if not shipment:
            return None

        carrier = self.carriers.get(shipment.carrier_id)
        if not carrier:
            return None

        # Generate tracking number
        tracking_number = self._generate_tracking_number(carrier.code)

        # Create label (simulated)
        label = ShippingLabel(
            label_id=self._generate_id("LBL"),
            carrier_id=shipment.carrier_id,
            tracking_number=tracking_number,
            service_code=shipment.service_code,
            label_format=label_format,
            label_data=f"[SIMULATED_LABEL_DATA_{tracking_number}]",
            label_url=f"https://labels.example.com/{tracking_number}.{label_format.lower()}",
        )

        # Update shipment
        shipment.tracking_number = tracking_number
        shipment.label = label
        shipment.status = ShipmentStatus.LABEL_CREATED

        # Calculate shipping cost
        quotes = self.get_rate_quotes(shipment.to_address, shipment.packages)
        matching_quote = None
        for q in quotes:
            if (
                q.carrier_id == shipment.carrier_id
                and q.service_code == shipment.service_code
            ):
                matching_quote = q
                break

        if matching_quote:
            shipment.shipping_cost_aud = matching_quote.total_cost_aud
            shipment.total_cost_aud = matching_quote.total_cost_aud
            shipment.estimated_delivery = matching_quote.estimated_delivery

        self.labels[label.label_id] = label
        return label

    def void_label(self, label_id: str) -> bool:
        """Void a shipping label."""
        label = self.labels.get(label_id)
        if not label or label.void_date:
            return False

        label.void_date = datetime.now()

        # Update associated shipment
        for shipment in self.shipments.values():
            if shipment.label and shipment.label.label_id == label_id:
                shipment.status = ShipmentStatus.CANCELLED
                break

        return True

    # -------------------------------------------------------------------------
    # Tracking
    # -------------------------------------------------------------------------

    def add_tracking_event(
        self,
        tracking_number: str,
        status: ShipmentStatus,
        location: str,
        description: str,
        signed_by: str = "",
    ) -> TrackingEvent:
        """Add tracking event."""
        event = TrackingEvent(
            event_id=self._generate_id("EVT"),
            tracking_number=tracking_number,
            timestamp=datetime.now(),
            status=status,
            location=location,
            description=description,
            signed_by=signed_by,
        )
        self.tracking_events.append(event)

        # Update shipment status
        for shipment in self.shipments.values():
            if shipment.tracking_number == tracking_number:
                shipment.status = status
                shipment.events.append(event)
                if status == ShipmentStatus.DELIVERED:
                    shipment.actual_delivery = event.timestamp
                elif status == ShipmentStatus.PICKED_UP:
                    shipment.shipped_at = event.timestamp
                break

        return event

    def get_tracking_events(self, tracking_number: str) -> list[TrackingEvent]:
        """Get tracking events for a tracking number."""
        events = [
            e for e in self.tracking_events if e.tracking_number == tracking_number
        ]
        events.sort(key=lambda e: e.timestamp)
        return events

    def get_tracking_url(self, shipment_id: str) -> Optional[str]:
        """Get tracking URL for a shipment."""
        shipment = self.shipments.get(shipment_id)
        if not shipment or not shipment.tracking_number:
            return None

        carrier = self.carriers.get(shipment.carrier_id)
        if not carrier or not carrier.tracking_url_template:
            return None

        return carrier.tracking_url_template.replace(
            "{tracking_number}", shipment.tracking_number
        )

    def estimate_delivery(
        self,
        carrier_id: str,
        service_code: str,
        to_postcode: str,
        ship_date: datetime = None,
    ) -> dict:
        """Estimate delivery date."""
        ship_date = ship_date or datetime.now()

        # Find rate for service
        for rate in self.rates.values():
            if rate.carrier_id == carrier_id and rate.service_code == service_code:
                delivery_min = ship_date + timedelta(days=rate.estimated_days_min)
                delivery_max = ship_date + timedelta(days=rate.estimated_days_max)

                # Adjust for weekends
                for dt in [delivery_min, delivery_max]:
                    while dt.weekday() >= 5:  # Saturday or Sunday
                        dt += timedelta(days=1)

                return {
                    "ship_date": ship_date.strftime("%Y-%m-%d"),
                    "estimated_earliest": delivery_min.strftime("%Y-%m-%d"),
                    "estimated_latest": delivery_max.strftime("%Y-%m-%d"),
                    "business_days": f"{rate.estimated_days_min}-{rate.estimated_days_max}",
                }

        return {"error": "Service not found"}

    # -------------------------------------------------------------------------
    # Bulk Shipping
    # -------------------------------------------------------------------------

    def create_bulk_batch(self, name: str, shipment_ids: list[str]) -> BulkShipment:
        """Create a bulk shipping batch."""
        batch = BulkShipment(
            batch_id=self._generate_id("BULK"),
            name=name,
            shipments=shipment_ids,
            total_labels=len(shipment_ids),
        )
        self.bulk_batches[batch.batch_id] = batch
        return batch

    async def process_bulk_batch(self, batch_id: str, progress_callback=None) -> dict:
        """Process bulk shipping batch."""
        batch = self.bulk_batches.get(batch_id)
        if not batch:
            return {"success": False, "error": "Batch not found"}

        batch.status = "processing"

        for i, shipment_id in enumerate(batch.shipments):
            try:
                label = self.generate_label(shipment_id)

                if label:
                    batch.successful_labels += 1
                else:
                    batch.failed_labels += 1
                    batch.errors.append(
                        {
                            "shipment_id": shipment_id,
                            "error": "Failed to generate label",
                        }
                    )

                if progress_callback:
                    progress_callback(i + 1, len(batch.shipments))

                # Simulate API delay
                await asyncio.sleep(0.1)

            except Exception as e:
                batch.failed_labels += 1
                batch.errors.append({"shipment_id": shipment_id, "error": str(e)})

        batch.completed_at = datetime.now()

        if batch.failed_labels == 0:
            batch.status = "completed"
        elif batch.successful_labels > 0:
            batch.status = "partial"
        else:
            batch.status = "failed"

        return {
            "success": True,
            "batch_id": batch_id,
            "status": batch.status,
            "total": batch.total_labels,
            "successful": batch.successful_labels,
            "failed": batch.failed_labels,
            "errors": batch.errors,
        }

    def get_bulk_batch_status(self, batch_id: str) -> Optional[dict]:
        """Get bulk batch status."""
        batch = self.bulk_batches.get(batch_id)
        if not batch:
            return None

        return {
            "batch_id": batch.batch_id,
            "name": batch.name,
            "status": batch.status,
            "total": batch.total_labels,
            "successful": batch.successful_labels,
            "failed": batch.failed_labels,
            "created_at": batch.created_at.isoformat(),
            "completed_at": (
                batch.completed_at.isoformat() if batch.completed_at else None
            ),
        }

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def get_shipping_summary(
        self, start_date: datetime = None, end_date: datetime = None
    ) -> dict:
        """Get shipping summary."""
        start_date = start_date or (datetime.now() - timedelta(days=30))
        end_date = end_date or datetime.now()

        shipments = [
            s for s in self.shipments.values() if start_date <= s.created_at <= end_date
        ]

        by_carrier = defaultdict(lambda: {"count": 0, "cost": 0.0})
        by_status = defaultdict(int)

        for s in shipments:
            carrier = self.carriers.get(s.carrier_id)
            carrier_name = carrier.name if carrier else "Unknown"
            by_carrier[carrier_name]["count"] += 1
            by_carrier[carrier_name]["cost"] += s.total_cost_aud
            by_status[s.status.value] += 1

        return {
            "period": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
            },
            "total_shipments": len(shipments),
            "total_shipping_cost": round(sum(s.total_cost_aud for s in shipments), 2),
            "avg_cost_per_shipment": (
                round(sum(s.total_cost_aud for s in shipments) / len(shipments), 2)
                if shipments
                else 0
            ),
            "by_carrier": dict(by_carrier),
            "by_status": dict(by_status),
            "labels_generated": len([s for s in shipments if s.label]),
            "international_shipments": len(
                [s for s in shipments if s.to_address and s.to_address.country != "AU"]
            ),
        }

    def get_carrier_performance(self) -> list[dict]:
        """Get carrier performance metrics."""
        performance = {}

        for shipment in self.shipments.values():
            carrier_id = shipment.carrier_id
            if carrier_id not in performance:
                carrier = self.carriers.get(carrier_id)
                performance[carrier_id] = {
                    "carrier_id": carrier_id,
                    "carrier_name": carrier.name if carrier else "Unknown",
                    "total_shipments": 0,
                    "delivered": 0,
                    "on_time": 0,
                    "late": 0,
                    "exceptions": 0,
                    "avg_transit_days": [],
                }

            perf = performance[carrier_id]
            perf["total_shipments"] += 1

            if shipment.status == ShipmentStatus.DELIVERED:
                perf["delivered"] += 1

                if shipment.actual_delivery and shipment.estimated_delivery:
                    if shipment.actual_delivery <= shipment.estimated_delivery:
                        perf["on_time"] += 1
                    else:
                        perf["late"] += 1

                if shipment.shipped_at and shipment.actual_delivery:
                    transit = (shipment.actual_delivery - shipment.shipped_at).days
                    perf["avg_transit_days"].append(transit)

            elif shipment.status == ShipmentStatus.EXCEPTION:
                perf["exceptions"] += 1

        results = []
        for perf in performance.values():
            if perf["avg_transit_days"]:
                perf["avg_transit_days"] = round(
                    sum(perf["avg_transit_days"]) / len(perf["avg_transit_days"]), 1
                )
            else:
                perf["avg_transit_days"] = None

            if perf["delivered"] > 0:
                perf["on_time_rate"] = round(
                    perf["on_time"] / perf["delivered"] * 100, 1
                )
            else:
                perf["on_time_rate"] = None

            results.append(perf)

        return results


# =============================================================================
# DEMO DATA SETUP
# =============================================================================


def setup_demo_data(service: ShippingLogisticsService) -> None:
    """Set up demo shipping data."""

    # Create carriers (generic)
    carriers = [
        (
            "FastShip",
            "FASTSHIP",
            CarrierType.DOMESTIC,
            ["STANDARD", "EXPRESS", "OVERNIGHT"],
            ["AU"],
            30.0,
            "https://track.fastship.com.au/?tn={tracking_number}",
        ),
        (
            "EcoPost",
            "ECOPOST",
            CarrierType.DOMESTIC,
            ["ECONOMY", "STANDARD"],
            ["AU"],
            20.0,
            "https://ecopost.com.au/track/{tracking_number}",
        ),
        (
            "SpeedEx Couriers",
            "SPEEDEX",
            CarrierType.EXPRESS,
            ["SAME_DAY", "EXPRESS", "OVERNIGHT"],
            ["AU"],
            25.0,
            "https://speedex.com.au/tracking?ref={tracking_number}",
        ),
        (
            "GlobalFreight",
            "GLOBALFREIGHT",
            CarrierType.INTERNATIONAL,
            ["INT_ECONOMY", "INT_EXPRESS", "INT_PRIORITY"],
            ["AU", "US", "UK", "NZ", "SG", "JP", "DE", "CA"],
            30.0,
            "https://globalfreight.com/track/{tracking_number}",
        ),
        (
            "Courier One",
            "COURIER1",
            CarrierType.COURIER,
            ["LOCAL_COURIER", "METRO_EXPRESS"],
            ["AU"],
            10.0,
            "https://courier1.com.au/track/{tracking_number}",
        ),
    ]

    created_carriers = []
    for name, code, c_type, services, countries, max_weight, track_url in carriers:
        carrier = service.create_carrier(
            name, code, c_type, services, countries, max_weight, track_url
        )
        created_carriers.append(carrier)

    # Create zones
    zones = [
        ("Metro Melbourne", ["AU"], ["VIC"], ["3"], True),
        ("Metro Sydney", ["AU"], ["NSW"], ["2"], True),
        ("Regional Australia", ["AU"], [], [], True),
        ("New Zealand", ["NZ"], [], [], False),
        ("Asia Pacific", ["SG", "JP", "HK"], [], [], False),
        ("USA & Canada", ["US", "CA"], [], [], False),
        ("Europe", ["UK", "DE", "FR", "IT", "ES"], [], [], False),
    ]

    created_zones = {}
    for name, countries, states, postcodes, is_domestic in zones:
        zone = service.create_zone(name, countries, states, postcodes, is_domestic)
        created_zones[name] = zone

    # Create rates
    # FastShip rates
    fs_carrier = created_carriers[0]
    service.create_rate(
        fs_carrier.carrier_id,
        "STANDARD",
        "Standard Delivery",
        created_zones["Metro Melbourne"].zone_id,
        9.95,
        0.0,
        2,
        4,
    )
    service.create_rate(
        fs_carrier.carrier_id,
        "EXPRESS",
        "Express Delivery",
        created_zones["Metro Melbourne"].zone_id,
        14.95,
        0.0,
        1,
        2,
    )
    service.create_rate(
        fs_carrier.carrier_id,
        "OVERNIGHT",
        "Overnight",
        created_zones["Metro Melbourne"].zone_id,
        24.95,
        0.0,
        1,
        1,
    )
    service.create_rate(
        fs_carrier.carrier_id,
        "STANDARD",
        "Standard Delivery",
        created_zones["Regional Australia"].zone_id,
        14.95,
        1.50,
        3,
        7,
    )

    # EcoPost rates
    ep_carrier = created_carriers[1]
    service.create_rate(
        ep_carrier.carrier_id,
        "ECONOMY",
        "Economy Saver",
        created_zones["Metro Melbourne"].zone_id,
        6.95,
        0.0,
        4,
        7,
    )
    service.create_rate(
        ep_carrier.carrier_id,
        "STANDARD",
        "Standard",
        created_zones["Metro Melbourne"].zone_id,
        8.95,
        0.0,
        2,
        5,
    )

    # GlobalFreight international rates
    gf_carrier = created_carriers[3]
    service.create_rate(
        gf_carrier.carrier_id,
        "INT_ECONOMY",
        "International Economy",
        created_zones["New Zealand"].zone_id,
        19.95,
        3.50,
        5,
        10,
    )
    service.create_rate(
        gf_carrier.carrier_id,
        "INT_EXPRESS",
        "International Express",
        created_zones["New Zealand"].zone_id,
        39.95,
        5.00,
        2,
        4,
    )
    service.create_rate(
        gf_carrier.carrier_id,
        "INT_ECONOMY",
        "International Economy",
        created_zones["USA & Canada"].zone_id,
        34.95,
        6.00,
        7,
        14,
    )
    service.create_rate(
        gf_carrier.carrier_id,
        "INT_EXPRESS",
        "International Express",
        created_zones["USA & Canada"].zone_id,
        59.95,
        8.00,
        3,
        5,
    )
    service.create_rate(
        gf_carrier.carrier_id,
        "INT_ECONOMY",
        "International Economy",
        created_zones["Europe"].zone_id,
        39.95,
        7.00,
        10,
        20,
    )
    service.create_rate(
        gf_carrier.carrier_id,
        "INT_EXPRESS",
        "International Express",
        created_zones["Europe"].zone_id,
        79.95,
        10.00,
        4,
        7,
    )

    # Create shipping rules
    service.create_rule(
        "Free shipping over $100",
        ShippingRuleType.FREE_SHIPPING,
        conditions={"min_order_value": 100.00},
        actions={"carrier": "ECOPOST", "service": "STANDARD"},
        priority=1,
    )

    service.create_rule(
        "Flat rate under 1kg",
        ShippingRuleType.FLAT_RATE,
        conditions={"max_weight": 1.0},
        actions={"rate": 5.95},
        priority=5,
    )

    print(
        f"✅ Demo data loaded: {len(created_carriers)} carriers, {len(created_zones)} zones"
    )


# =============================================================================
# INTERACTIVE MODE
# =============================================================================


async def interactive_mode(service: ShippingLogisticsService) -> None:
    """Run interactive shipping mode."""

    print("\n" + "=" * 60)
    print("📦 SHIPPING & LOGISTICS SYSTEM - Interactive Mode")
    print("=" * 60)

    while True:
        print("\n📋 MAIN MENU:")
        print("  1. Rate Shopping")
        print("  2. Create Shipment")
        print("  3. Generate Label")
        print("  4. Track Shipment")
        print("  5. International Shipping")
        print("  6. Shipping Rules")
        print("  7. Bulk Processing")
        print("  8. Reports")
        print("  9. Exit")

        choice = input("\nSelect option (1-9): ").strip()

        if choice == "1":
            await rate_shopping_menu(service)
        elif choice == "2":
            await create_shipment_menu(service)
        elif choice == "3":
            await label_menu(service)
        elif choice == "4":
            await tracking_menu(service)
        elif choice == "5":
            await international_menu(service)
        elif choice == "6":
            await rules_menu(service)
        elif choice == "7":
            await bulk_menu(service)
        elif choice == "8":
            await reports_menu(service)
        elif choice == "9":
            print("\n👋 Goodbye!")
            break


async def rate_shopping_menu(service: ShippingLogisticsService) -> None:
    """Rate shopping submenu."""
    print("\n💰 RATE SHOPPING:")

    # Get destination
    print("\nDestination address:")
    postcode = input("  Postcode: ").strip() or "3000"
    state = input("  State: ").strip() or "VIC"
    country = input("  Country (AU): ").strip() or "AU"

    to_address = Address(
        name="Customer",
        city="Melbourne",
        state=state,
        postcode=postcode,
        country=country,
    )

    # Get package details
    weight = float(input("  Weight (kg): ").strip() or "2.0")
    declared_value = float(input("  Declared value (AUD): ").strip() or "100.00")

    package = Package(
        package_id="PKG-001",
        weight_kg=weight,
        length_cm=30,
        width_cm=20,
        height_cm=15,
        declared_value_aud=declared_value,
    )

    # Get quotes
    quotes = service.get_rate_quotes(to_address, [package], include_insurance=False)

    if not quotes:
        print("\n❌ No rates available for this destination")
        return

    print(f"\n📊 {len(quotes)} rates found:")
    print("-" * 60)

    for i, q in enumerate(quotes, 1):
        print(f"\n  {i}. {q.carrier_name} - {q.service_name}")
        print(f"     Cost: ${q.total_cost_aud:.2f}")
        print(
            f"     Delivery: {q.estimated_days_min}-{q.estimated_days_max} business days"
        )
        print(f"     Est. arrival: {q.estimated_delivery.strftime('%Y-%m-%d')}")

    # Show cheapest and fastest
    cheapest = service.get_cheapest_rate(to_address, [package])
    fastest = service.get_fastest_rate(to_address, [package])

    print("\n" + "-" * 60)
    if cheapest:
        print(
            f"💵 CHEAPEST: {cheapest.carrier_name} {cheapest.service_name} - ${cheapest.total_cost_aud:.2f}"
        )
    if fastest:
        print(
            f"⚡ FASTEST: {fastest.carrier_name} {fastest.service_name} - {fastest.estimated_days_min} days"
        )


async def create_shipment_menu(service: ShippingLogisticsService) -> None:
    """Create shipment submenu."""
    print("\n📦 CREATE SHIPMENT:")

    order_id = input("  Order ID: ").strip() or f"ORD-{random.randint(1000, 9999)}"

    # Destination
    print("\nDestination:")
    name = input("  Recipient name: ").strip() or "John Smith"
    street = input("  Street address: ").strip() or "123 Main Street"
    city = input("  City: ").strip() or "Melbourne"
    state = input("  State: ").strip() or "VIC"
    postcode = input("  Postcode: ").strip() or "3000"

    to_address = Address(
        name=name, street1=street, city=city, state=state, postcode=postcode
    )

    # Package
    weight = float(input("  Package weight (kg): ").strip() or "2.0")
    value = float(input("  Declared value ($): ").strip() or "100.00")

    package = Package(
        package_id=f"PKG-{random.randint(1000, 9999)}",
        weight_kg=weight,
        length_cm=30,
        width_cm=20,
        height_cm=15,
        declared_value_aud=value,
    )

    # Get rates and select
    quotes = service.get_rate_quotes(to_address, [package])

    if not quotes:
        print("❌ No shipping options available")
        return

    print("\nAvailable shipping options:")
    for i, q in enumerate(quotes[:5], 1):
        print(f"  {i}. {q.carrier_name} - {q.service_name} (${q.total_cost_aud:.2f})")

    selection = int(input("\nSelect option (1-5): ").strip() or "1") - 1
    selected_quote = quotes[min(selection, len(quotes) - 1)]

    # Create shipment
    shipment = service.create_shipment(
        order_id=order_id,
        carrier_id=selected_quote.carrier_id,
        service_code=selected_quote.service_code,
        to_address=to_address,
        packages=[package],
    )

    print(f"\n✅ Shipment created: {shipment.shipment_id}")
    print(f"   Order: {order_id}")
    print(f"   Carrier: {selected_quote.carrier_name}")
    print(f"   Service: {selected_quote.service_name}")
    print(f"   Cost: ${selected_quote.total_cost_aud:.2f}")


async def label_menu(service: ShippingLogisticsService) -> None:
    """Label generation submenu."""
    print("\n🏷️ LABEL GENERATION:")
    print("  1. Generate label")
    print("  2. Void label")
    print("  3. List pending shipments")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        shipment_id = input("  Shipment ID: ").strip()
        label = service.generate_label(shipment_id)

        if label:
            print("\n✅ Label generated!")
            print(f"   Label ID: {label.label_id}")
            print(f"   Tracking: {label.tracking_number}")
            print(f"   Format: {label.label_format}")
            print(f"   URL: {label.label_url}")
        else:
            print("❌ Failed to generate label")

    elif choice == "2":
        label_id = input("  Label ID to void: ").strip()
        if service.void_label(label_id):
            print("✅ Label voided")
        else:
            print("❌ Failed to void label")

    elif choice == "3":
        pending = [
            s for s in service.shipments.values() if s.status == ShipmentStatus.PENDING
        ]
        print(f"\n📋 {len(pending)} pending shipments:")
        for s in pending[:10]:
            print(f"  • {s.shipment_id} - Order {s.order_id}")


async def tracking_menu(service: ShippingLogisticsService) -> None:
    """Tracking submenu."""
    print("\n📍 TRACKING:")
    print("  1. Track by number")
    print("  2. Track by shipment ID")
    print("  3. Add tracking event (demo)")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        tracking = input("  Tracking number: ").strip()
        events = service.get_tracking_events(tracking)

        if events:
            print(f"\n📍 Tracking events for {tracking}:")
            for event in events:
                print(f"  {event.timestamp.strftime('%Y-%m-%d %H:%M')}")
                print(f"    Status: {event.status.value}")
                print(f"    Location: {event.location}")
                print(f"    {event.description}")
        else:
            print("❌ No events found")

    elif choice == "2":
        shipment_id = input("  Shipment ID: ").strip()
        shipment = service.get_shipment(shipment_id)

        if shipment:
            print(f"\n📦 Shipment {shipment_id}")
            print(f"   Status: {shipment.status.value}")
            print(f"   Tracking: {shipment.tracking_number or 'N/A'}")
            print(f"   Carrier: {shipment.carrier_id}")

            if shipment.tracking_number:
                url = service.get_tracking_url(shipment_id)
                if url:
                    print(f"   Track URL: {url}")

            if shipment.events:
                print("\n   Events:")
                for event in shipment.events:
                    print(
                        f"   • {event.timestamp.strftime('%m/%d %H:%M')} - {event.description}"
                    )
        else:
            print("❌ Shipment not found")

    elif choice == "3":
        # Demo: add tracking events
        shipment_id = input("  Shipment ID: ").strip()
        shipment = service.get_shipment(shipment_id)

        if not shipment or not shipment.tracking_number:
            print("❌ Shipment not found or no tracking number")
            return

        statuses = [
            (
                ShipmentStatus.PICKED_UP,
                "Melbourne VIC",
                "Package picked up from sender",
            ),
            (
                ShipmentStatus.IN_TRANSIT,
                "Sydney NSW",
                "In transit - arrived at sort facility",
            ),
            (ShipmentStatus.OUT_FOR_DELIVERY, "Brisbane QLD", "Out for delivery"),
            (
                ShipmentStatus.DELIVERED,
                "Brisbane QLD",
                "Delivered - left at front door",
            ),
        ]

        print("\nAdd tracking event:")
        for i, (status, _loc, desc) in enumerate(statuses, 1):
            print(f"  {i}. {status.value} - {desc}")

        selection = int(input("\nSelect (1-4): ").strip() or "1") - 1
        status, location, description = statuses[min(selection, 3)]

        event = service.add_tracking_event(
            shipment.tracking_number, status, location, description
        )
        print(f"\n✅ Event added: {event.description}")


async def international_menu(service: ShippingLogisticsService) -> None:
    """International shipping submenu."""
    print("\n🌍 INTERNATIONAL SHIPPING:")
    print("  1. Estimate duties/taxes")
    print("  2. Create customs declaration")
    print("  3. International rate quotes")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        country = (
            input("  Destination country (US/UK/NZ/etc): ").strip().upper() or "US"
        )
        value = float(input("  Total value (AUD): ").strip() or "500.00")

        estimate = service.estimate_duties_taxes(country, value)

        print(f"\n📋 Duties/Taxes Estimate for {country}:")
        print(f"   Declared value: ${estimate['declared_value_aud']:.2f} AUD")
        print(f"   De minimis threshold: ${estimate['de_minimis_threshold_aud']:.2f}")

        if estimate.get("below_de_minimis"):
            print(f"   ✅ {estimate['note']}")
        else:
            print(f"   Duty rate: {estimate['duty_rate_pct']}%")
            print(f"   Tax rate: {estimate['tax_rate_pct']}%")
            print(f"   Estimated duty: ${estimate['estimated_duty_aud']:.2f}")
            print(f"   Estimated tax: ${estimate['estimated_tax_aud']:.2f}")
            print(f"   Total: ${estimate['total_duties_taxes_aud']:.2f}")

    elif choice == "2":
        print("\nCustoms Declaration:")
        content_type = (
            input("  Content type (merchandise/gift/sample): ").strip() or "merchandise"
        )

        items = []
        while True:
            desc = input("  Item description (empty to finish): ").strip()
            if not desc:
                break
            qty = int(input("  Quantity: ").strip() or "1")
            value = float(input("  Unit value (AUD): ").strip() or "50.00")
            weight = float(input("  Weight (kg): ").strip() or "0.5")

            items.append(
                {
                    "description": desc,
                    "quantity": qty,
                    "unit_value": value,
                    "weight_kg": weight,
                }
            )

        if items:
            customs = service.create_customs_declaration(
                CustomsContentType(content_type), items
            )
            print(f"\n✅ Customs declaration created: {customs.declaration_id}")
            print(f"   Total value: ${customs.total_value_aud:.2f}")
            print(f"   Items: {len(customs.items)}")

    elif choice == "3":
        country = input("  Destination country: ").strip().upper() or "US"

        to_address = Address(
            name="International Customer",
            city="New York",
            state="NY",
            postcode="10001",
            country=country,
        )

        package = Package(
            package_id="INT-PKG-001",
            weight_kg=2.0,
            length_cm=30,
            width_cm=20,
            height_cm=15,
            declared_value_aud=200.00,
        )

        quotes = service.get_rate_quotes(to_address, [package])

        if quotes:
            print(f"\n📊 International rates to {country}:")
            for q in quotes:
                print(f"  • {q.carrier_name} {q.service_name}")
                print(
                    f"    ${q.total_cost_aud:.2f} - {q.estimated_days_min}-{q.estimated_days_max} days"
                )
        else:
            print(f"❌ No rates available to {country}")


async def rules_menu(service: ShippingLogisticsService) -> None:
    """Shipping rules submenu."""
    print("\n📜 SHIPPING RULES:")
    print("  1. List rules")
    print("  2. Test rules")
    print("  3. Create rule")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        print(f"\n📜 {len(service.rules)} shipping rules:")
        for rule in service.rules.values():
            status = "✅" if rule.is_active else "❌"
            print(f"  {status} {rule.name}")
            print(f"     Type: {rule.rule_type.value}")
            print(f"     Priority: {rule.priority}")
            print(f"     Conditions: {rule.conditions}")
            print(f"     Actions: {rule.actions}")

    elif choice == "2":
        order_total = float(input("  Order total ($): ").strip() or "150.00")
        order_weight = float(input("  Order weight (kg): ").strip() or "2.0")
        postcode = input("  Destination postcode: ").strip() or "3000"

        to_address = Address(name="Test", postcode=postcode, state="VIC", country="AU")

        result = service.apply_shipping_rules(order_total, order_weight, to_address)

        print("\n📋 Rules applied:")
        print(f"   Free shipping: {'Yes' if result['free_shipping'] else 'No'}")
        if result.get("flat_rate"):
            print(f"   Flat rate: ${result['flat_rate']:.2f}")
        if result["applied_rules"]:
            print(f"   Rules triggered: {', '.join(result['applied_rules'])}")

    elif choice == "3":
        name = input("  Rule name: ").strip() or "New Rule"

        print(
            "  Rule types: free_shipping, flat_rate, weight_based, carrier_restriction"
        )
        rule_type = input("  Type: ").strip() or "flat_rate"

        min_value = input("  Min order value (or empty): ").strip()
        max_weight = input("  Max weight (or empty): ").strip()

        conditions = {}
        if min_value:
            conditions["min_order_value"] = float(min_value)
        if max_weight:
            conditions["max_weight"] = float(max_weight)

        actions = {}
        if rule_type == "flat_rate":
            rate = input("  Flat rate ($): ").strip() or "9.95"
            actions["rate"] = float(rate)
        elif rule_type == "free_shipping":
            actions["free"] = True

        rule = service.create_rule(
            name, ShippingRuleType(rule_type), conditions, actions
        )
        print(f"\n✅ Rule created: {rule.rule_id}")


async def bulk_menu(service: ShippingLogisticsService) -> None:
    """Bulk processing submenu."""
    print("\n📦 BULK PROCESSING:")
    print("  1. Create bulk batch")
    print("  2. Process batch")
    print("  3. View batch status")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        name = input("  Batch name: ").strip() or "Today's shipments"

        # Create demo shipments
        shipment_ids = []
        for i in range(5):
            to_address = Address(
                name=f"Customer {i+1}",
                street1=f"{100+i} Test Street",
                city="Melbourne",
                state="VIC",
                postcode=f"300{i}",
                country="AU",
            )

            package = Package(
                package_id=f"PKG-BULK-{i}",
                weight_kg=random.uniform(0.5, 5.0),
                length_cm=30,
                width_cm=20,
                height_cm=15,
                declared_value_aud=random.uniform(50, 200),
            )

            carrier = list(service.carriers.values())[0]
            shipment = service.create_shipment(
                f"ORD-BULK-{i+1}", carrier.carrier_id, "STANDARD", to_address, [package]
            )
            shipment_ids.append(shipment.shipment_id)

        batch = service.create_bulk_batch(name, shipment_ids)
        print(f"\n✅ Bulk batch created: {batch.batch_id}")
        print(f"   Shipments: {len(shipment_ids)}")

    elif choice == "2":
        batch_id = input("  Batch ID: ").strip()

        def progress(current, total):
            print(f"   Processing {current}/{total}...", end="\r")

        print("\n⏳ Processing batch...")
        result = await service.process_bulk_batch(batch_id, progress)

        if result["success"]:
            print("\n✅ Batch processing complete!")
            print(f"   Status: {result['status']}")
            print(f"   Successful: {result['successful']}/{result['total']}")
            if result["errors"]:
                print(f"   Errors: {len(result['errors'])}")
        else:
            print(f"\n❌ {result.get('error')}")

    elif choice == "3":
        batch_id = input("  Batch ID: ").strip()
        status = service.get_bulk_batch_status(batch_id)

        if status:
            print(f"\n📊 Batch: {status['name']}")
            print(f"   Status: {status['status']}")
            print(f"   Total: {status['total']}")
            print(f"   Successful: {status['successful']}")
            print(f"   Failed: {status['failed']}")
            print(f"   Created: {status['created_at']}")
        else:
            print("❌ Batch not found")


async def reports_menu(service: ShippingLogisticsService) -> None:
    """Reports submenu."""
    print("\n📊 REPORTS:")
    print("  1. Shipping summary")
    print("  2. Carrier performance")
    print("  3. List all carriers")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        summary = service.get_shipping_summary()

        print("\n📊 SHIPPING SUMMARY (Last 30 days)")
        print("=" * 40)
        print(f"Total shipments: {summary['total_shipments']}")
        print(f"Total cost: ${summary['total_shipping_cost']:.2f}")
        print(f"Avg per shipment: ${summary['avg_cost_per_shipment']:.2f}")
        print(f"Labels generated: {summary['labels_generated']}")
        print(f"International: {summary['international_shipments']}")

        if summary["by_carrier"]:
            print("\nBy Carrier:")
            for carrier, data in summary["by_carrier"].items():
                print(f"  • {carrier}: {data['count']} shipments (${data['cost']:.2f})")

        if summary["by_status"]:
            print("\nBy Status:")
            for status, count in summary["by_status"].items():
                print(f"  • {status}: {count}")

    elif choice == "2":
        performance = service.get_carrier_performance()

        print("\n📊 CARRIER PERFORMANCE")
        print("=" * 40)
        for perf in performance:
            print(f"\n{perf['carrier_name']}:")
            print(f"   Total: {perf['total_shipments']}")
            print(f"   Delivered: {perf['delivered']}")
            if perf["on_time_rate"] is not None:
                print(f"   On-time rate: {perf['on_time_rate']}%")
            if perf["avg_transit_days"] is not None:
                print(f"   Avg transit: {perf['avg_transit_days']} days")
            print(f"   Exceptions: {perf['exceptions']}")

    elif choice == "3":
        print("\n📦 CARRIERS:")
        for carrier in service.carriers.values():
            status = "✅" if carrier.is_active else "❌"
            print(f"  {status} {carrier.name} ({carrier.code})")
            print(f"     Type: {carrier.carrier_type.value}")
            print(f"     Services: {', '.join(carrier.services)}")
            print(f"     Max weight: {carrier.max_weight_kg} kg")


# =============================================================================
# DEMO MODE
# =============================================================================


async def demo_mode(service: ShippingLogisticsService) -> None:
    """Run automated demo."""
    print("\n" + "=" * 60)
    print("📦 SHIPPING & LOGISTICS DEMO")
    print("=" * 60)

    # 1. Show carriers
    print("\n📦 1. AVAILABLE CARRIERS")
    print("-" * 40)
    for carrier in service.carriers.values():
        print(f"   • {carrier.name} ({carrier.code})")
        print(f"     Services: {', '.join(carrier.services)}")
    await asyncio.sleep(1)

    # 2. Rate shopping demo
    print("\n💰 2. RATE SHOPPING DEMO")
    print("-" * 40)

    to_address = Address(
        name="Jane Smith",
        street1="456 Customer Lane",
        city="Sydney",
        state="NSW",
        postcode="2000",
        country="AU",
    )

    package = Package(
        package_id="PKG-DEMO-001",
        weight_kg=3.5,
        length_cm=40,
        width_cm=30,
        height_cm=20,
        declared_value_aud=250.00,
    )

    print(
        f"   Destination: {to_address.city}, {to_address.state} {to_address.postcode}"
    )
    print(f"   Package: {package.weight_kg}kg, ${package.declared_value_aud:.2f} value")

    quotes = service.get_rate_quotes(to_address, [package])
    print(f"\n   📊 {len(quotes)} rates found:")
    for q in quotes[:5]:
        print(
            f"   • {q.carrier_name} {q.service_name}: ${q.total_cost_aud:.2f} ({q.estimated_days_min}-{q.estimated_days_max} days)"
        )

    cheapest = service.get_cheapest_rate(to_address, [package])
    fastest = service.get_fastest_rate(to_address, [package])
    print(f"\n   💵 Cheapest: {cheapest.carrier_name} ${cheapest.total_cost_aud:.2f}")
    print(f"   ⚡ Fastest: {fastest.carrier_name} {fastest.estimated_days_min} days")
    await asyncio.sleep(1)

    # 3. Create shipment
    print("\n📦 3. CREATE SHIPMENT")
    print("-" * 40)

    shipment = service.create_shipment(
        "ORD-DEMO-001",
        cheapest.carrier_id,
        cheapest.service_code,
        to_address,
        [package],
    )
    print(f"   Shipment ID: {shipment.shipment_id}")
    print(f"   Order: {shipment.order_id}")
    print(f"   Status: {shipment.status.value}")
    await asyncio.sleep(1)

    # 4. Generate label
    print("\n🏷️ 4. GENERATE LABEL")
    print("-" * 40)

    label = service.generate_label(shipment.shipment_id)
    print(f"   Label ID: {label.label_id}")
    print(f"   Tracking: {label.tracking_number}")
    print(f"   Format: {label.label_format}")
    print(f"   URL: {label.label_url}")
    await asyncio.sleep(1)

    # 5. Tracking events
    print("\n📍 5. TRACKING SIMULATION")
    print("-" * 40)

    events = [
        (ShipmentStatus.PICKED_UP, "Melbourne VIC", "Picked up from sender"),
        (ShipmentStatus.IN_TRANSIT, "Melbourne Sort", "Arrived at Melbourne facility"),
        (ShipmentStatus.IN_TRANSIT, "Sydney Sort", "Arrived at Sydney facility"),
        (ShipmentStatus.OUT_FOR_DELIVERY, "Sydney NSW", "Out for delivery"),
        (ShipmentStatus.DELIVERED, "Sydney NSW", "Delivered - signed by J.SMITH"),
    ]

    for status, location, description in events:
        service.add_tracking_event(
            shipment.tracking_number,
            status,
            location,
            description,
            "J.SMITH" if status == ShipmentStatus.DELIVERED else "",
        )
        print(f"   ✓ {status.value}: {description}")
        await asyncio.sleep(0.3)

    # 6. International shipping
    print("\n🌍 6. INTERNATIONAL SHIPPING")
    print("-" * 40)

    int_address = Address(
        name="International Customer",
        street1="123 Main St",
        city="Los Angeles",
        state="CA",
        postcode="90001",
        country="US",
    )

    int_quotes = service.get_rate_quotes(int_address, [package])
    if int_quotes:
        print("   Rates to USA:")
        for q in int_quotes:
            print(f"   • {q.service_name}: ${q.total_cost_aud:.2f}")

    # Duties estimate
    duties = service.estimate_duties_taxes("US", package.declared_value_aud)
    print("\n   Duties/Taxes estimate:")
    print(f"   • Value: ${duties['declared_value_aud']:.2f}")
    print(f"   • De minimis: ${duties['de_minimis_threshold_aud']:.2f}")
    if duties.get("below_de_minimis"):
        print(f"   ✅ {duties['note']}")
    await asyncio.sleep(1)

    # 7. Shipping rules
    print("\n📜 7. SHIPPING RULES ENGINE")
    print("-" * 40)

    # Test order that qualifies for free shipping
    rules_result = service.apply_shipping_rules(
        order_total_aud=150.00, order_weight_kg=2.0, to_address=to_address
    )

    print("   Order: $150.00, 2kg to Sydney")
    print(f"   Free shipping: {'Yes' if rules_result['free_shipping'] else 'No'}")
    print(f"   Rules applied: {', '.join(rules_result['applied_rules'])}")
    await asyncio.sleep(1)

    # 8. Bulk processing
    print("\n📦 8. BULK PROCESSING")
    print("-" * 40)

    # Create batch of shipments
    shipment_ids = []
    for i in range(5):
        addr = Address(
            name=f"Customer {i+1}",
            street1=f"{100+i} Test St",
            city="Melbourne",
            state="VIC",
            postcode=f"300{i}",
            country="AU",
        )
        pkg = Package(
            package_id=f"PKG-BATCH-{i}",
            weight_kg=random.uniform(1, 5),
            length_cm=30,
            width_cm=20,
            height_cm=15,
            declared_value_aud=random.uniform(50, 200),
        )

        carrier = list(service.carriers.values())[0]
        s = service.create_shipment(
            f"ORD-BATCH-{i}", carrier.carrier_id, "STANDARD", addr, [pkg]
        )
        shipment_ids.append(s.shipment_id)

    batch = service.create_bulk_batch("Demo Batch", shipment_ids)
    print(f"   Created batch: {batch.batch_id}")
    print(f"   Shipments: {len(shipment_ids)}")

    # Process batch
    print("   Processing...")
    result = await service.process_bulk_batch(batch.batch_id)
    print(f"   ✅ Complete: {result['successful']}/{result['total']} labels generated")
    await asyncio.sleep(1)

    # 9. Summary
    print("\n📊 9. SHIPPING SUMMARY")
    print("-" * 40)

    summary = service.get_shipping_summary()
    print(f"   Total shipments: {summary['total_shipments']}")
    print(f"   Total cost: ${summary['total_shipping_cost']:.2f}")
    print(f"   Labels generated: {summary['labels_generated']}")

    performance = service.get_carrier_performance()
    print("\n   Carrier performance:")
    for perf in performance[:3]:
        print(f"   • {perf['carrier_name']}: {perf['delivered']} delivered")

    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETED")
    print("=" * 60)


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WooCommerce Shipping & Logistics System"
    )
    parser.add_argument("--demo", action="store_true", help="Run automated demo")
    parser.add_argument(
        "--interactive", action="store_true", help="Run interactive mode"
    )

    args = parser.parse_args()

    service = ShippingLogisticsService()
    setup_demo_data(service)

    if args.demo:
        asyncio.run(demo_mode(service))
    elif args.interactive:
        asyncio.run(interactive_mode(service))
    else:
        print("Usage: python 72_woo_shipping_logistics.py --demo OR --interactive")
        print("\nRunning demo mode by default...\n")
        asyncio.run(demo_mode(service))


if __name__ == "__main__":
    main()
