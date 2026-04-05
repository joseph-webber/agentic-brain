#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WooCommerce Multi-Channel Inventory Sync System
================================================

Comprehensive inventory synchronization including:
- Multi-channel inventory sync (WooCommerce + eBay + Amazon style)
- Stock allocation across channels
- Oversell prevention
- Low stock alerts
- Reorder point management
- Supplier integration
- Purchase order generation
- Lead time tracking

Australian-focused with realistic inventory workflows.

Usage:
    python 73_woo_inventory_sync.py --demo
    python 73_woo_inventory_sync.py --interactive
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


class Channel(Enum):
    """Sales channel."""

    WOOCOMMERCE = "woocommerce"
    EBAY = "ebay"
    AMAZON = "amazon"
    RETAIL = "retail"
    WHOLESALE = "wholesale"
    MARKETPLACE = "marketplace"


class SyncStatus(Enum):
    """Sync status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class StockStatus(Enum):
    """Stock status."""

    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    BACKORDERED = "backordered"
    DISCONTINUED = "discontinued"


class AllocationStrategy(Enum):
    """Stock allocation strategy."""

    EQUAL = "equal"  # Equal split across channels
    WEIGHTED = "weighted"  # Based on sales velocity
    PRIORITY = "priority"  # Priority channels first
    BUFFER = "buffer"  # Reserve buffer stock
    DYNAMIC = "dynamic"  # ML-based prediction


class POStatus(Enum):
    """Purchase order status."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class AlertSeverity(Enum):
    """Alert severity level."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Supplier:
    """Supplier record."""

    supplier_id: str
    name: str
    code: str
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    country: str = "AU"
    currency: str = "AUD"
    payment_terms: str = "Net 30"
    lead_time_days: int = 14
    min_order_value_aud: float = 0.0
    is_active: bool = True
    rating: float = 5.0
    notes: str = ""


@dataclass
class Product:
    """Product definition."""

    sku: str
    name: str
    description: str
    category: str
    unit_cost_aud: float
    retail_price_aud: float
    weight_kg: float
    barcode: str = ""
    supplier_id: Optional[str] = None
    supplier_sku: str = ""
    reorder_point: int = 20
    reorder_quantity: int = 50
    safety_stock: int = 10
    lead_time_days: int = 14
    is_active: bool = True
    is_managed: bool = True  # Inventory managed
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ChannelListing:
    """Product listing on a sales channel."""

    listing_id: str
    sku: str
    channel: Channel
    channel_sku: str  # SKU as it appears on that channel
    channel_product_id: str = ""
    title: str = ""
    price_aud: float = 0.0
    quantity_listed: int = 0
    is_active: bool = True
    last_synced: Optional[datetime] = None
    sync_errors: list[str] = field(default_factory=list)


@dataclass
class ChannelConfig:
    """Channel configuration."""

    channel: Channel
    is_enabled: bool = True
    priority: int = 1  # Higher = more priority
    allocation_percentage: float = 100.0
    buffer_stock: int = 0
    sync_interval_minutes: int = 15
    auto_sync: bool = True
    api_credentials: dict = field(default_factory=dict)
    last_sync: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.PENDING


@dataclass
class InventoryLevel:
    """Central inventory level."""

    sku: str
    warehouse_id: str
    total_quantity: int
    available_quantity: int
    reserved_quantity: int = 0
    incoming_quantity: int = 0  # From POs
    committed_quantity: int = 0  # Sold but not shipped
    damaged_quantity: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ChannelInventory:
    """Inventory allocated to a channel."""

    sku: str
    channel: Channel
    allocated_quantity: int
    listed_quantity: int
    reserved_quantity: int = 0
    pending_sync: bool = False
    last_synced: Optional[datetime] = None


@dataclass
class StockAllocation:
    """Stock allocation record."""

    allocation_id: str
    sku: str
    available_stock: int
    allocations: dict[Channel, int]
    strategy: AllocationStrategy
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SyncEvent:
    """Inventory sync event."""

    event_id: str
    channel: Channel
    sku: str
    action: str  # update, list, delist
    old_quantity: int
    new_quantity: int
    status: SyncStatus
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: str = ""
    response_data: dict = field(default_factory=dict)


@dataclass
class StockAlert:
    """Stock alert."""

    alert_id: str
    sku: str
    product_name: str
    alert_type: str  # low_stock, out_of_stock, oversell_risk, reorder_needed
    severity: AlertSeverity
    current_quantity: int
    threshold: int
    channel: Optional[Channel] = None
    message: str = ""
    acknowledged: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: str = ""


@dataclass
class PurchaseOrderLine:
    """Purchase order line item."""

    line_id: str
    sku: str
    product_name: str
    quantity_ordered: int
    quantity_received: int = 0
    unit_cost_aud: float = 0.0
    total_cost_aud: float = 0.0
    expected_date: Optional[datetime] = None


@dataclass
class PurchaseOrder:
    """Purchase order."""

    po_number: str
    supplier_id: str
    supplier_name: str
    status: POStatus
    lines: list[PurchaseOrderLine] = field(default_factory=list)
    subtotal_aud: float = 0.0
    tax_aud: float = 0.0
    shipping_aud: float = 0.0
    total_aud: float = 0.0
    currency: str = "AUD"
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    expected_date: Optional[datetime] = None
    received_date: Optional[datetime] = None
    notes: str = ""


@dataclass
class SupplierProduct:
    """Supplier's product catalog."""

    supplier_id: str
    supplier_sku: str
    internal_sku: str
    name: str
    unit_cost_aud: float
    min_order_qty: int = 1
    pack_size: int = 1
    lead_time_days: int = 14
    is_available: bool = True
    last_price_update: datetime = field(default_factory=datetime.now)


@dataclass
class LeadTimeRecord:
    """Lead time tracking record."""

    record_id: str
    supplier_id: str
    sku: str
    po_number: str
    promised_days: int
    actual_days: int
    variance_days: int
    on_time: bool
    created_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# INVENTORY SYNC SERVICE
# =============================================================================


class InventorySyncService:
    """Multi-channel inventory synchronization service."""

    def __init__(self):
        self.suppliers: dict[str, Supplier] = {}
        self.products: dict[str, Product] = {}
        self.listings: dict[str, ChannelListing] = {}
        self.channels: dict[Channel, ChannelConfig] = {}
        self.inventory: dict[str, InventoryLevel] = {}
        self.channel_inventory: dict[tuple[str, Channel], ChannelInventory] = {}
        self.allocations: list[StockAllocation] = []
        self.sync_events: list[SyncEvent] = []
        self.alerts: dict[str, StockAlert] = {}
        self.purchase_orders: dict[str, PurchaseOrder] = {}
        self.supplier_products: dict[tuple[str, str], SupplierProduct] = {}
        self.lead_time_records: list[LeadTimeRecord] = []

        # Configuration
        self.default_warehouse = "MAIN"
        self.oversell_protection = True
        self.auto_reorder = True

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = (
            hashlib.md5(f"{timestamp}{random.random()}".encode())
            .hexdigest()[:6]
            .upper()
        )
        return f"{prefix}-{timestamp}-{random_suffix}"

    # -------------------------------------------------------------------------
    # Supplier Management
    # -------------------------------------------------------------------------

    def create_supplier(
        self,
        name: str,
        code: str,
        contact_name: str = "",
        email: str = "",
        lead_time_days: int = 14,
        **kwargs,
    ) -> Supplier:
        """Create a supplier."""
        supplier = Supplier(
            supplier_id=self._generate_id("SUP"),
            name=name,
            code=code,
            contact_name=contact_name,
            email=email,
            lead_time_days=lead_time_days,
            **kwargs,
        )
        self.suppliers[supplier.supplier_id] = supplier
        return supplier

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        """Get supplier by ID."""
        return self.suppliers.get(supplier_id)

    def list_suppliers(self, active_only: bool = True) -> list[Supplier]:
        """List suppliers."""
        suppliers = list(self.suppliers.values())
        if active_only:
            suppliers = [s for s in suppliers if s.is_active]
        return suppliers

    def add_supplier_product(
        self,
        supplier_id: str,
        supplier_sku: str,
        internal_sku: str,
        name: str,
        unit_cost_aud: float,
        min_order_qty: int = 1,
        lead_time_days: int = 14,
    ) -> SupplierProduct:
        """Add a product to supplier's catalog."""
        sp = SupplierProduct(
            supplier_id=supplier_id,
            supplier_sku=supplier_sku,
            internal_sku=internal_sku,
            name=name,
            unit_cost_aud=unit_cost_aud,
            min_order_qty=min_order_qty,
            lead_time_days=lead_time_days,
        )
        self.supplier_products[(supplier_id, supplier_sku)] = sp
        return sp

    # -------------------------------------------------------------------------
    # Product Management
    # -------------------------------------------------------------------------

    def create_product(
        self,
        sku: str,
        name: str,
        description: str,
        category: str,
        unit_cost_aud: float,
        retail_price_aud: float,
        weight_kg: float,
        **kwargs,
    ) -> Product:
        """Create a product."""
        product = Product(
            sku=sku,
            name=name,
            description=description,
            category=category,
            unit_cost_aud=unit_cost_aud,
            retail_price_aud=retail_price_aud,
            weight_kg=weight_kg,
            **kwargs,
        )
        self.products[sku] = product

        # Initialize inventory
        self._init_inventory(sku)

        return product

    def _init_inventory(self, sku: str, initial_qty: int = 0) -> None:
        """Initialize inventory for a product."""
        key = f"{sku}:{self.default_warehouse}"
        if key not in self.inventory:
            self.inventory[key] = InventoryLevel(
                sku=sku,
                warehouse_id=self.default_warehouse,
                total_quantity=initial_qty,
                available_quantity=initial_qty,
            )

    def get_product(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        return self.products.get(sku)

    def list_products(self, category: Optional[str] = None) -> list[Product]:
        """List products."""
        products = list(self.products.values())
        if category:
            products = [p for p in products if p.category == category]
        return products

    # -------------------------------------------------------------------------
    # Channel Configuration
    # -------------------------------------------------------------------------

    def configure_channel(
        self,
        channel: Channel,
        is_enabled: bool = True,
        priority: int = 1,
        allocation_percentage: float = 100.0,
        buffer_stock: int = 0,
        sync_interval_minutes: int = 15,
    ) -> ChannelConfig:
        """Configure a sales channel."""
        config = ChannelConfig(
            channel=channel,
            is_enabled=is_enabled,
            priority=priority,
            allocation_percentage=allocation_percentage,
            buffer_stock=buffer_stock,
            sync_interval_minutes=sync_interval_minutes,
        )
        self.channels[channel] = config
        return config

    def get_channel_config(self, channel: Channel) -> Optional[ChannelConfig]:
        """Get channel configuration."""
        return self.channels.get(channel)

    def list_enabled_channels(self) -> list[ChannelConfig]:
        """List enabled channels."""
        return [c for c in self.channels.values() if c.is_enabled]

    # -------------------------------------------------------------------------
    # Channel Listings
    # -------------------------------------------------------------------------

    def create_listing(
        self, sku: str, channel: Channel, channel_sku: str, title: str, price_aud: float
    ) -> ChannelListing:
        """Create a channel listing."""
        product = self.products.get(sku)
        if not product:
            raise ValueError(f"Product {sku} not found")

        listing = ChannelListing(
            listing_id=self._generate_id("LST"),
            sku=sku,
            channel=channel,
            channel_sku=channel_sku,
            title=title or product.name,
            price_aud=price_aud or product.retail_price_aud,
        )
        self.listings[listing.listing_id] = listing

        # Initialize channel inventory
        self._init_channel_inventory(sku, channel)

        return listing

    def _init_channel_inventory(self, sku: str, channel: Channel) -> None:
        """Initialize channel inventory."""
        key = (sku, channel)
        if key not in self.channel_inventory:
            self.channel_inventory[key] = ChannelInventory(
                sku=sku, channel=channel, allocated_quantity=0, listed_quantity=0
            )

    def get_listings_for_sku(self, sku: str) -> list[ChannelListing]:
        """Get all listings for a SKU."""
        return [l for l in self.listings.values() if l.sku == sku]

    def get_listings_for_channel(self, channel: Channel) -> list[ChannelListing]:
        """Get all listings for a channel."""
        return [l for l in self.listings.values() if l.channel == channel]

    # -------------------------------------------------------------------------
    # Inventory Management
    # -------------------------------------------------------------------------

    def get_inventory(
        self, sku: str, warehouse_id: str = None
    ) -> Optional[InventoryLevel]:
        """Get inventory level."""
        warehouse_id = warehouse_id or self.default_warehouse
        key = f"{sku}:{warehouse_id}"
        return self.inventory.get(key)

    def update_inventory(
        self,
        sku: str,
        quantity_change: int,
        reason: str = "manual_adjustment",
        warehouse_id: str = None,
    ) -> InventoryLevel:
        """Update inventory level."""
        warehouse_id = warehouse_id or self.default_warehouse
        key = f"{sku}:{warehouse_id}"

        if key not in self.inventory:
            self._init_inventory(sku)

        inv = self.inventory[key]
        inv.total_quantity += quantity_change
        inv.available_quantity += quantity_change
        inv.last_updated = datetime.now()

        # Check for alerts
        self._check_stock_alerts(sku)

        # Trigger sync if quantity changed
        if quantity_change != 0:
            self._mark_channels_for_sync(sku)

        return inv

    def set_inventory(
        self, sku: str, quantity: int, warehouse_id: str = None
    ) -> InventoryLevel:
        """Set absolute inventory level."""
        warehouse_id = warehouse_id or self.default_warehouse
        key = f"{sku}:{warehouse_id}"

        if key not in self.inventory:
            self._init_inventory(sku)

        inv = self.inventory[key]
        old_qty = inv.total_quantity
        inv.total_quantity = quantity
        inv.available_quantity = (
            quantity - inv.reserved_quantity - inv.committed_quantity
        )
        inv.last_updated = datetime.now()

        # Check alerts and sync
        self._check_stock_alerts(sku)
        if old_qty != quantity:
            self._mark_channels_for_sync(sku)

        return inv

    def reserve_inventory(
        self, sku: str, quantity: int, channel: Channel, order_id: str
    ) -> bool:
        """Reserve inventory for an order."""
        inv = self.get_inventory(sku)
        if not inv or inv.available_quantity < quantity:
            return False

        inv.available_quantity -= quantity
        inv.reserved_quantity += quantity
        inv.last_updated = datetime.now()

        # Update channel inventory
        ch_inv = self.channel_inventory.get((sku, channel))
        if ch_inv:
            ch_inv.reserved_quantity += quantity

        return True

    def commit_inventory(self, sku: str, quantity: int, order_id: str) -> bool:
        """Commit reserved inventory (order confirmed)."""
        inv = self.get_inventory(sku)
        if not inv or inv.reserved_quantity < quantity:
            return False

        inv.reserved_quantity -= quantity
        inv.committed_quantity += quantity

        return True

    def ship_inventory(self, sku: str, quantity: int, order_id: str) -> bool:
        """Ship committed inventory."""
        inv = self.get_inventory(sku)
        if not inv or inv.committed_quantity < quantity:
            return False

        inv.committed_quantity -= quantity
        inv.total_quantity -= quantity
        inv.last_updated = datetime.now()

        # Check alerts and sync
        self._check_stock_alerts(sku)
        self._mark_channels_for_sync(sku)

        return True

    def _mark_channels_for_sync(self, sku: str) -> None:
        """Mark all channels for sync after inventory change."""
        for key, ch_inv in self.channel_inventory.items():
            if key[0] == sku:
                ch_inv.pending_sync = True

    # -------------------------------------------------------------------------
    # Stock Allocation
    # -------------------------------------------------------------------------

    def allocate_stock(
        self, sku: str, strategy: AllocationStrategy = AllocationStrategy.WEIGHTED
    ) -> StockAllocation:
        """Allocate stock across channels."""
        inv = self.get_inventory(sku)
        if not inv:
            raise ValueError(f"No inventory for SKU {sku}")

        available = inv.available_quantity
        product = self.products.get(sku)
        safety_stock = product.safety_stock if product else 0

        # Reserve safety stock
        allocatable = max(0, available - safety_stock)

        # Get enabled channels with listings for this SKU
        channel_listings = {}
        for listing in self.listings.values():
            if listing.sku == sku and listing.is_active:
                config = self.channels.get(listing.channel)
                if config and config.is_enabled:
                    channel_listings[listing.channel] = config

        allocations = {}

        if strategy == AllocationStrategy.EQUAL:
            # Equal split
            if channel_listings:
                per_channel = allocatable // len(channel_listings)
                for channel in channel_listings:
                    allocations[channel] = per_channel

        elif strategy == AllocationStrategy.PRIORITY:
            # Allocate by priority (higher priority first)
            remaining = allocatable
            sorted_channels = sorted(
                channel_listings.items(), key=lambda x: x[1].priority, reverse=True
            )
            for channel, config in sorted_channels:
                # Calculate based on allocation percentage
                alloc = int(remaining * (config.allocation_percentage / 100))
                alloc = max(0, alloc - config.buffer_stock)
                allocations[channel] = alloc
                remaining -= alloc

        elif strategy == AllocationStrategy.WEIGHTED:
            # Weight by allocation percentage
            total_pct = sum(c.allocation_percentage for c in channel_listings.values())
            for channel, config in channel_listings.items():
                if total_pct > 0:
                    alloc = int(
                        allocatable * (config.allocation_percentage / total_pct)
                    )
                    alloc = max(0, alloc - config.buffer_stock)
                    allocations[channel] = alloc
                else:
                    allocations[channel] = 0

        elif strategy == AllocationStrategy.BUFFER:
            # Reserve buffer for each channel
            remaining = allocatable
            for channel, config in channel_listings.items():
                buffer = config.buffer_stock
                alloc = max(0, (remaining // len(channel_listings)) - buffer)
                allocations[channel] = alloc

        # Update channel inventory
        for channel, qty in allocations.items():
            key = (sku, channel)
            if key in self.channel_inventory:
                self.channel_inventory[key].allocated_quantity = qty
                self.channel_inventory[key].pending_sync = True

        # Record allocation
        allocation = StockAllocation(
            allocation_id=self._generate_id("ALLOC"),
            sku=sku,
            available_stock=available,
            allocations=allocations,
            strategy=strategy,
        )
        self.allocations.append(allocation)

        return allocation

    def get_channel_stock(self, sku: str, channel: Channel) -> int:
        """Get allocated stock for a channel."""
        key = (sku, channel)
        ch_inv = self.channel_inventory.get(key)
        return ch_inv.allocated_quantity if ch_inv else 0

    # -------------------------------------------------------------------------
    # Oversell Prevention
    # -------------------------------------------------------------------------

    def check_oversell_risk(self, sku: str) -> dict:
        """Check for oversell risk across channels."""
        inv = self.get_inventory(sku)
        if not inv:
            return {"error": "SKU not found"}

        total_listed = 0
        channel_quantities = {}

        for key, ch_inv in self.channel_inventory.items():
            if key[0] == sku:
                total_listed += ch_inv.listed_quantity
                channel_quantities[key[1].value] = ch_inv.listed_quantity

        available = inv.available_quantity
        oversell_amount = max(0, total_listed - available)

        return {
            "sku": sku,
            "available": available,
            "total_listed": total_listed,
            "oversell_risk": total_listed > available,
            "oversell_amount": oversell_amount,
            "channel_quantities": channel_quantities,
        }

    def prevent_oversell(self, sku: str) -> list[dict]:
        """Automatically adjust quantities to prevent oversell."""
        risk = self.check_oversell_risk(sku)

        if not risk.get("oversell_risk"):
            return []

        adjustments = []
        oversell = risk["oversell_amount"]

        # Sort channels by priority (low to high) to reduce from lowest priority first
        channels_sorted = sorted(
            self.channel_inventory.items(),
            key=lambda x: self.channels.get(
                x[0][1], ChannelConfig(channel=x[0][1])
            ).priority,
        )

        for key, ch_inv in channels_sorted:
            if key[0] != sku or oversell <= 0:
                continue

            # Reduce this channel's allocation
            reduction = min(ch_inv.allocated_quantity, oversell)
            if reduction > 0:
                ch_inv.allocated_quantity -= reduction
                ch_inv.pending_sync = True
                oversell -= reduction

                adjustments.append(
                    {
                        "channel": key[1].value,
                        "old_quantity": ch_inv.allocated_quantity + reduction,
                        "new_quantity": ch_inv.allocated_quantity,
                        "reduction": reduction,
                    }
                )

        return adjustments

    # -------------------------------------------------------------------------
    # Inventory Sync
    # -------------------------------------------------------------------------

    async def sync_channel(self, channel: Channel) -> dict:
        """Sync inventory to a channel."""
        config = self.channels.get(channel)
        if not config or not config.is_enabled:
            return {"success": False, "error": "Channel not enabled"}

        config.sync_status = SyncStatus.IN_PROGRESS

        synced = 0
        failed = 0
        events = []

        # Get all items pending sync for this channel
        for key, ch_inv in self.channel_inventory.items():
            if key[1] != channel or not ch_inv.pending_sync:
                continue

            sku = key[0]

            try:
                # Simulate API call
                await asyncio.sleep(0.05)

                old_qty = ch_inv.listed_quantity
                new_qty = ch_inv.allocated_quantity

                # Record sync event
                event = SyncEvent(
                    event_id=self._generate_id("SYNC"),
                    channel=channel,
                    sku=sku,
                    action="update",
                    old_quantity=old_qty,
                    new_quantity=new_qty,
                    status=SyncStatus.COMPLETED,
                )
                self.sync_events.append(event)
                events.append(event)

                # Update listed quantity
                ch_inv.listed_quantity = new_qty
                ch_inv.pending_sync = False
                ch_inv.last_synced = datetime.now()

                synced += 1

            except Exception as e:
                failed += 1
                event = SyncEvent(
                    event_id=self._generate_id("SYNC"),
                    channel=channel,
                    sku=sku,
                    action="update",
                    old_quantity=ch_inv.listed_quantity,
                    new_quantity=ch_inv.allocated_quantity,
                    status=SyncStatus.FAILED,
                    error_message=str(e),
                )
                self.sync_events.append(event)

        config.last_sync = datetime.now()
        config.sync_status = SyncStatus.COMPLETED if failed == 0 else SyncStatus.PARTIAL

        return {
            "success": True,
            "channel": channel.value,
            "synced": synced,
            "failed": failed,
            "status": config.sync_status.value,
        }

    async def sync_all_channels(self) -> dict:
        """Sync inventory to all enabled channels."""
        results = {}

        for channel in self.list_enabled_channels():
            result = await self.sync_channel(channel.channel)
            results[channel.channel.value] = result

        return results

    async def sync_sku(self, sku: str) -> dict:
        """Sync a specific SKU to all channels."""
        results = {}

        for key, ch_inv in self.channel_inventory.items():
            if key[0] == sku:
                ch_inv.pending_sync = True

        for channel in self.list_enabled_channels():
            result = await self.sync_channel(channel.channel)
            results[channel.channel.value] = result

        return results

    # -------------------------------------------------------------------------
    # Stock Alerts
    # -------------------------------------------------------------------------

    def _check_stock_alerts(self, sku: str) -> list[StockAlert]:
        """Check and create stock alerts."""
        alerts = []
        product = self.products.get(sku)
        inv = self.get_inventory(sku)

        if not product or not inv:
            return alerts

        current_qty = inv.available_quantity

        # Out of stock
        if current_qty <= 0:
            alert = self._create_alert(
                sku,
                product.name,
                "out_of_stock",
                AlertSeverity.CRITICAL,
                current_qty,
                0,
                "Product is out of stock across all channels",
            )
            alerts.append(alert)

        # Low stock
        elif current_qty <= product.reorder_point:
            severity = (
                AlertSeverity.WARNING
                if current_qty > product.safety_stock
                else AlertSeverity.CRITICAL
            )
            alert = self._create_alert(
                sku,
                product.name,
                "low_stock",
                severity,
                current_qty,
                product.reorder_point,
                f"Stock below reorder point ({product.reorder_point})",
            )
            alerts.append(alert)

            # Auto-reorder check
            if self.auto_reorder and current_qty <= product.safety_stock:
                self._suggest_reorder(sku)

        return alerts

    def _create_alert(
        self,
        sku: str,
        product_name: str,
        alert_type: str,
        severity: AlertSeverity,
        current_qty: int,
        threshold: int,
        message: str,
    ) -> StockAlert:
        """Create a stock alert."""
        alert = StockAlert(
            alert_id=self._generate_id("ALERT"),
            sku=sku,
            product_name=product_name,
            alert_type=alert_type,
            severity=severity,
            current_quantity=current_qty,
            threshold=threshold,
            message=message,
        )
        self.alerts[alert.alert_id] = alert
        return alert

    def get_active_alerts(
        self, severity: Optional[AlertSeverity] = None
    ) -> list[StockAlert]:
        """Get active (unacknowledged) alerts."""
        alerts = [a for a in self.alerts.values() if not a.acknowledged]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return False

        alert.acknowledged = True
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = acknowledged_by
        return True

    def create_low_stock_report(self) -> list[dict]:
        """Generate low stock report."""
        report = []

        for sku, product in self.products.items():
            if not product.is_managed:
                continue

            inv = self.get_inventory(sku)
            if not inv:
                continue

            available = inv.available_quantity

            if available <= product.reorder_point:
                status = (
                    StockStatus.OUT_OF_STOCK
                    if available <= 0
                    else StockStatus.LOW_STOCK
                )

                report.append(
                    {
                        "sku": sku,
                        "name": product.name,
                        "category": product.category,
                        "available": available,
                        "reorder_point": product.reorder_point,
                        "safety_stock": product.safety_stock,
                        "reorder_quantity": product.reorder_quantity,
                        "status": status.value,
                        "days_to_stockout": self._estimate_days_to_stockout(sku),
                        "suggested_order_qty": max(
                            0, product.reorder_quantity - available
                        ),
                    }
                )

        report.sort(key=lambda x: x["available"])
        return report

    def _estimate_days_to_stockout(self, sku: str) -> Optional[int]:
        """Estimate days until stockout based on recent sales velocity."""
        # Simplified - in production would analyze sales history
        inv = self.get_inventory(sku)
        if not inv or inv.available_quantity <= 0:
            return 0

        # Assume average 2 units/day velocity
        velocity = 2.0
        return int(inv.available_quantity / velocity) if velocity > 0 else None

    # -------------------------------------------------------------------------
    # Reorder Point Management
    # -------------------------------------------------------------------------

    def _suggest_reorder(self, sku: str) -> Optional[dict]:
        """Suggest reorder for a product."""
        product = self.products.get(sku)
        if not product or not product.supplier_id:
            return None

        supplier = self.suppliers.get(product.supplier_id)
        if not supplier:
            return None

        inv = self.get_inventory(sku)
        current = inv.available_quantity if inv else 0

        return {
            "sku": sku,
            "product_name": product.name,
            "current_stock": current,
            "reorder_point": product.reorder_point,
            "suggested_quantity": product.reorder_quantity,
            "supplier": supplier.name,
            "lead_time_days": product.lead_time_days,
            "unit_cost": product.unit_cost_aud,
            "total_cost": product.unit_cost_aud * product.reorder_quantity,
        }

    def calculate_reorder_point(
        self, sku: str, daily_sales: float, lead_time_days: int, safety_days: int = 7
    ) -> dict:
        """Calculate optimal reorder point."""
        product = self.products.get(sku)
        if not product:
            return {"error": "Product not found"}

        # Reorder point = (Daily sales × Lead time) + Safety stock
        reorder_point = int(
            (daily_sales * lead_time_days) + (daily_sales * safety_days)
        )

        # Economic order quantity (simplified)
        # EOQ = sqrt((2 × Annual demand × Order cost) / Holding cost)
        annual_demand = daily_sales * 365
        order_cost = 50.0  # Assumed fixed order cost
        holding_cost = product.unit_cost_aud * 0.25  # 25% of unit cost

        eoq = (
            int(((2 * annual_demand * order_cost) / holding_cost) ** 0.5)
            if holding_cost > 0
            else 50
        )

        return {
            "sku": sku,
            "daily_sales": daily_sales,
            "lead_time_days": lead_time_days,
            "safety_days": safety_days,
            "calculated_reorder_point": reorder_point,
            "calculated_safety_stock": int(daily_sales * safety_days),
            "economic_order_quantity": eoq,
            "current_reorder_point": product.reorder_point,
            "current_reorder_quantity": product.reorder_quantity,
        }

    def update_reorder_settings(
        self, sku: str, reorder_point: int, reorder_quantity: int, safety_stock: int
    ) -> bool:
        """Update reorder settings for a product."""
        product = self.products.get(sku)
        if not product:
            return False

        product.reorder_point = reorder_point
        product.reorder_quantity = reorder_quantity
        product.safety_stock = safety_stock

        # Re-check alerts
        self._check_stock_alerts(sku)

        return True

    # -------------------------------------------------------------------------
    # Purchase Orders
    # -------------------------------------------------------------------------

    def create_purchase_order(
        self, supplier_id: str, lines: list[dict]
    ) -> PurchaseOrder:
        """Create a purchase order."""
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            raise ValueError(f"Supplier {supplier_id} not found")

        po_lines = []
        subtotal = 0.0

        for line in lines:
            sku = line.get("sku")
            qty = line.get("quantity", 0)
            product = self.products.get(sku)
            unit_cost = line.get("unit_cost") or (
                product.unit_cost_aud if product else 0
            )
            total = unit_cost * qty

            po_line = PurchaseOrderLine(
                line_id=self._generate_id("POL"),
                sku=sku,
                product_name=product.name if product else sku,
                quantity_ordered=qty,
                unit_cost_aud=unit_cost,
                total_cost_aud=total,
            )
            po_lines.append(po_line)
            subtotal += total

        tax = subtotal * 0.1  # 10% GST

        po = PurchaseOrder(
            po_number=f"PO-{datetime.now().strftime('%Y%m%d')}-{random.randint(100, 999)}",
            supplier_id=supplier_id,
            supplier_name=supplier.name,
            status=POStatus.DRAFT,
            lines=po_lines,
            subtotal_aud=round(subtotal, 2),
            tax_aud=round(tax, 2),
            total_aud=round(subtotal + tax, 2),
            expected_date=datetime.now() + timedelta(days=supplier.lead_time_days),
        )
        self.purchase_orders[po.po_number] = po

        return po

    def submit_purchase_order(self, po_number: str) -> bool:
        """Submit a purchase order."""
        po = self.purchase_orders.get(po_number)
        if not po or po.status != POStatus.DRAFT:
            return False

        po.status = POStatus.SUBMITTED
        po.submitted_at = datetime.now()

        # Update incoming quantities
        for line in po.lines:
            inv = self.get_inventory(line.sku)
            if inv:
                inv.incoming_quantity += line.quantity_ordered

        return True

    def confirm_purchase_order(
        self, po_number: str, expected_date: datetime = None
    ) -> bool:
        """Confirm a purchase order from supplier."""
        po = self.purchase_orders.get(po_number)
        if not po or po.status != POStatus.SUBMITTED:
            return False

        po.status = POStatus.CONFIRMED
        if expected_date:
            po.expected_date = expected_date

        return True

    def receive_purchase_order(
        self, po_number: str, received_lines: list[dict]
    ) -> dict:
        """Receive items from a purchase order."""
        po = self.purchase_orders.get(po_number)
        if not po or po.status not in [POStatus.CONFIRMED, POStatus.PARTIALLY_RECEIVED]:
            return {"success": False, "error": "PO not ready for receiving"}

        received_items = []

        for recv in received_lines:
            sku = recv.get("sku")
            qty = recv.get("quantity", 0)

            # Find PO line
            for line in po.lines:
                if line.sku == sku:
                    remaining = line.quantity_ordered - line.quantity_received
                    qty_to_receive = min(qty, remaining)

                    line.quantity_received += qty_to_receive

                    # Update inventory
                    inv = self.get_inventory(sku)
                    if inv:
                        inv.total_quantity += qty_to_receive
                        inv.available_quantity += qty_to_receive
                        inv.incoming_quantity -= qty_to_receive
                        inv.last_updated = datetime.now()

                    received_items.append(
                        {
                            "sku": sku,
                            "received": qty_to_receive,
                            "remaining": remaining - qty_to_receive,
                        }
                    )

                    # Check alerts and sync
                    self._check_stock_alerts(sku)
                    self._mark_channels_for_sync(sku)

                    break

        # Update PO status
        all_received = all(
            line.quantity_received >= line.quantity_ordered for line in po.lines
        )

        if all_received:
            po.status = POStatus.RECEIVED
            po.received_date = datetime.now()

            # Record lead time
            supplier = self.suppliers.get(po.supplier_id)
            if supplier and po.submitted_at:
                actual_days = (datetime.now() - po.submitted_at).days
                self._record_lead_time(
                    supplier.supplier_id,
                    po.po_number,
                    supplier.lead_time_days,
                    actual_days,
                )
        else:
            po.status = POStatus.PARTIALLY_RECEIVED

        return {
            "success": True,
            "po_number": po_number,
            "status": po.status.value,
            "received_items": received_items,
        }

    def auto_generate_pos(self) -> list[PurchaseOrder]:
        """Auto-generate POs for items below reorder point."""
        pos = []
        supplier_items = defaultdict(list)

        # Group items by supplier
        for sku, product in self.products.items():
            if not product.is_managed or not product.supplier_id:
                continue

            inv = self.get_inventory(sku)
            if not inv:
                continue

            if inv.available_quantity <= product.reorder_point:
                supplier_items[product.supplier_id].append(
                    {
                        "sku": sku,
                        "quantity": product.reorder_quantity,
                        "unit_cost": product.unit_cost_aud,
                    }
                )

        # Create PO for each supplier
        for supplier_id, items in supplier_items.items():
            if items:
                po = self.create_purchase_order(supplier_id, items)
                pos.append(po)

        return pos

    # -------------------------------------------------------------------------
    # Lead Time Tracking
    # -------------------------------------------------------------------------

    def _record_lead_time(
        self, supplier_id: str, po_number: str, promised_days: int, actual_days: int
    ) -> LeadTimeRecord:
        """Record lead time for analysis."""
        record = LeadTimeRecord(
            record_id=self._generate_id("LT"),
            supplier_id=supplier_id,
            sku="",  # Could be per-SKU
            po_number=po_number,
            promised_days=promised_days,
            actual_days=actual_days,
            variance_days=actual_days - promised_days,
            on_time=actual_days <= promised_days,
        )
        self.lead_time_records.append(record)
        return record

    def get_supplier_lead_time_stats(self, supplier_id: str) -> dict:
        """Get lead time statistics for a supplier."""
        records = [r for r in self.lead_time_records if r.supplier_id == supplier_id]

        if not records:
            return {"error": "No records found"}

        actual_times = [r.actual_days for r in records]
        on_time_count = sum(1 for r in records if r.on_time)

        return {
            "supplier_id": supplier_id,
            "total_orders": len(records),
            "avg_lead_time_days": round(sum(actual_times) / len(actual_times), 1),
            "min_lead_time_days": min(actual_times),
            "max_lead_time_days": max(actual_times),
            "on_time_rate": round(on_time_count / len(records) * 100, 1),
            "avg_variance_days": round(
                sum(r.variance_days for r in records) / len(records), 1
            ),
        }

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def get_inventory_summary(self) -> dict:
        """Get inventory summary across all channels."""
        total_products = len(self.products)
        total_value = 0.0
        in_stock = 0
        low_stock = 0
        out_of_stock = 0

        for sku, product in self.products.items():
            inv = self.get_inventory(sku)
            if not inv:
                continue

            qty = inv.available_quantity
            total_value += qty * product.unit_cost_aud

            if qty <= 0:
                out_of_stock += 1
            elif qty <= product.reorder_point:
                low_stock += 1
            else:
                in_stock += 1

        return {
            "total_products": total_products,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "total_inventory_value_aud": round(total_value, 2),
            "active_alerts": len(self.get_active_alerts()),
            "pending_pos": len(
                [
                    po
                    for po in self.purchase_orders.values()
                    if po.status
                    in [POStatus.DRAFT, POStatus.SUBMITTED, POStatus.CONFIRMED]
                ]
            ),
            "channels_configured": len(self.channels),
        }

    def get_channel_sync_status(self) -> list[dict]:
        """Get sync status for all channels."""
        status = []

        for channel, config in self.channels.items():
            listings = self.get_listings_for_channel(channel)
            pending_sync = sum(
                1
                for key, ch_inv in self.channel_inventory.items()
                if key[1] == channel and ch_inv.pending_sync
            )

            status.append(
                {
                    "channel": channel.value,
                    "enabled": config.is_enabled,
                    "priority": config.priority,
                    "allocation_pct": config.allocation_percentage,
                    "listings": len(listings),
                    "pending_sync": pending_sync,
                    "last_sync": (
                        config.last_sync.isoformat() if config.last_sync else None
                    ),
                    "sync_status": config.sync_status.value,
                }
            )

        return status


# =============================================================================
# DEMO DATA SETUP
# =============================================================================


def setup_demo_data(service: InventorySyncService) -> None:
    """Set up demo inventory data."""

    # Create suppliers
    suppliers = [
        ("Electronics Direct Australia", "EDA", "John Smith", "orders@eda.com.au", 10),
        ("Tech Wholesale Co", "TWC", "Sarah Jones", "sales@twc.com.au", 14),
        ("Global Components Ltd", "GCL", "Mike Chen", "orders@gcl.com.au", 21),
    ]

    created_suppliers = []
    for name, code, contact, email, lead_time in suppliers:
        supplier = service.create_supplier(name, code, contact, email, lead_time)
        created_suppliers.append(supplier)

    # Configure channels
    service.configure_channel(
        Channel.WOOCOMMERCE, priority=3, allocation_percentage=50.0, buffer_stock=5
    )
    service.configure_channel(
        Channel.EBAY, priority=2, allocation_percentage=30.0, buffer_stock=3
    )
    service.configure_channel(
        Channel.AMAZON, priority=1, allocation_percentage=20.0, buffer_stock=2
    )

    # Create products
    products_data = [
        (
            "MON-27-4K",
            "27-inch 4K Monitor",
            "monitors",
            350.00,
            549.00,
            5.5,
            created_suppliers[0].supplier_id,
            15,
            30,
        ),
        (
            "MON-24-FHD",
            "24-inch Full HD Monitor",
            "monitors",
            120.00,
            199.00,
            4.2,
            created_suppliers[0].supplier_id,
            20,
            50,
        ),
        (
            "CBL-HDMI-2M",
            "HDMI Cable 2m",
            "cables",
            8.00,
            24.95,
            0.15,
            created_suppliers[1].supplier_id,
            50,
            100,
        ),
        (
            "CBL-USB-C-1M",
            "USB-C Cable 1m",
            "cables",
            5.00,
            19.95,
            0.08,
            created_suppliers[1].supplier_id,
            50,
            100,
        ),
        (
            "KB-MECH-RGB",
            "Mechanical RGB Keyboard",
            "keyboards",
            65.00,
            149.00,
            0.95,
            created_suppliers[0].supplier_id,
            20,
            40,
        ),
        (
            "KB-WIRELESS",
            "Wireless Keyboard",
            "keyboards",
            35.00,
            79.00,
            0.45,
            created_suppliers[0].supplier_id,
            25,
            50,
        ),
        (
            "MS-GAMING",
            "Gaming Mouse",
            "mice",
            25.00,
            89.00,
            0.12,
            created_suppliers[1].supplier_id,
            30,
            60,
        ),
        (
            "MS-ERGONOMIC",
            "Ergonomic Mouse",
            "mice",
            30.00,
            69.00,
            0.15,
            created_suppliers[1].supplier_id,
            25,
            50,
        ),
        (
            "WC-1080P",
            "Webcam 1080p",
            "webcams",
            35.00,
            89.00,
            0.18,
            created_suppliers[2].supplier_id,
            20,
            40,
        ),
        (
            "WC-4K-PRO",
            "Webcam 4K Pro",
            "webcams",
            120.00,
            249.00,
            0.25,
            created_suppliers[2].supplier_id,
            10,
            20,
        ),
        (
            "HS-WIRELESS",
            "Wireless Headset",
            "headsets",
            85.00,
            179.00,
            0.35,
            created_suppliers[0].supplier_id,
            15,
            30,
        ),
        (
            "HS-USB",
            "USB Headset",
            "headsets",
            25.00,
            59.00,
            0.28,
            created_suppliers[0].supplier_id,
            30,
            60,
        ),
        (
            "DOCK-USB-C",
            "USB-C Docking Station",
            "docks",
            95.00,
            199.00,
            0.45,
            created_suppliers[2].supplier_id,
            10,
            20,
        ),
        (
            "HUB-USB-4",
            "USB Hub 4-Port",
            "hubs",
            15.00,
            39.95,
            0.12,
            created_suppliers[1].supplier_id,
            40,
            80,
        ),
        (
            "SSD-1TB",
            "SSD 1TB External",
            "storage",
            70.00,
            149.00,
            0.08,
            created_suppliers[2].supplier_id,
            20,
            40,
        ),
    ]

    for (
        sku,
        name,
        cat,
        cost,
        price,
        weight,
        supplier_id,
        reorder_pt,
        reorder_qty,
    ) in products_data:
        product = service.create_product(
            sku,
            name,
            f"High quality {name.lower()}",
            cat,
            cost,
            price,
            weight,
            supplier_id=supplier_id,
            reorder_point=reorder_pt,
            reorder_quantity=reorder_qty,
            safety_stock=reorder_pt // 2,
        )

        # Set initial inventory
        initial_qty = random.randint(10, 100)
        service.set_inventory(sku, initial_qty)

        # Create listings on all channels
        for channel in [Channel.WOOCOMMERCE, Channel.EBAY, Channel.AMAZON]:
            channel_prefix = {"woocommerce": "WC", "ebay": "EB", "amazon": "AZ"}
            service.create_listing(
                sku, channel, f"{channel_prefix[channel.value]}-{sku}", name, price
            )

    # Allocate stock
    for sku in service.products.keys():
        service.allocate_stock(sku, AllocationStrategy.WEIGHTED)

    print(
        f"✅ Demo data loaded: {len(created_suppliers)} suppliers, {len(products_data)} products, 3 channels"
    )


# =============================================================================
# INTERACTIVE MODE
# =============================================================================


async def interactive_mode(service: InventorySyncService) -> None:
    """Run interactive inventory sync mode."""

    print("\n" + "=" * 60)
    print("📦 MULTI-CHANNEL INVENTORY SYNC - Interactive Mode")
    print("=" * 60)

    while True:
        print("\n📋 MAIN MENU:")
        print("  1. Inventory Management")
        print("  2. Channel Sync")
        print("  3. Stock Allocation")
        print("  4. Oversell Prevention")
        print("  5. Alerts & Reorder")
        print("  6. Purchase Orders")
        print("  7. Suppliers")
        print("  8. Reports")
        print("  9. Exit")

        choice = input("\nSelect option (1-9): ").strip()

        if choice == "1":
            await inventory_menu(service)
        elif choice == "2":
            await sync_menu(service)
        elif choice == "3":
            await allocation_menu(service)
        elif choice == "4":
            await oversell_menu(service)
        elif choice == "5":
            await alerts_menu(service)
        elif choice == "6":
            await po_menu(service)
        elif choice == "7":
            await supplier_menu(service)
        elif choice == "8":
            await reports_menu(service)
        elif choice == "9":
            print("\n👋 Goodbye!")
            break


async def inventory_menu(service: InventorySyncService) -> None:
    """Inventory management submenu."""
    print("\n📦 INVENTORY MANAGEMENT:")
    print("  1. View inventory levels")
    print("  2. Update inventory")
    print("  3. Search products")
    print("  4. Reserve inventory")
    print("  5. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        print("\n📊 Inventory Levels:")
        for sku in list(service.products.keys())[:10]:
            inv = service.get_inventory(sku)
            product = service.products[sku]
            if inv:
                status = "✅" if inv.available_quantity > product.reorder_point else "⚠️"
                print(f"  {status} {sku}: {inv.available_quantity} available")
                print(
                    f"      ({inv.reserved_quantity} reserved, {inv.incoming_quantity} incoming)"
                )

    elif choice == "2":
        sku = input("  SKU: ").strip()
        qty_change = int(input("  Quantity change (+/-): ").strip() or "0")
        reason = input("  Reason: ").strip() or "manual_adjustment"

        inv = service.update_inventory(sku, qty_change, reason)
        print(f"\n✅ Updated {sku}: {inv.available_quantity} available")

    elif choice == "3":
        query = input("  Search term: ").strip()
        products = [
            p
            for p in service.products.values()
            if query.lower() in p.name.lower() or query.lower() in p.sku.lower()
        ]

        print(f"\n📊 Found {len(products)} products:")
        for p in products[:10]:
            inv = service.get_inventory(p.sku)
            qty = inv.available_quantity if inv else 0
            print(f"  • {p.sku}: {p.name} ({qty} available)")

    elif choice == "4":
        sku = input("  SKU: ").strip()
        qty = int(input("  Quantity to reserve: ").strip() or "1")
        channel = (
            input("  Channel (woocommerce/ebay/amazon): ").strip() or "woocommerce"
        )

        success = service.reserve_inventory(sku, qty, Channel(channel), "ORD-DEMO")
        if success:
            print(f"✅ Reserved {qty} units of {sku}")
        else:
            print("❌ Insufficient inventory")


async def sync_menu(service: InventorySyncService) -> None:
    """Channel sync submenu."""
    print("\n🔄 CHANNEL SYNC:")
    print("  1. View channel status")
    print("  2. Sync all channels")
    print("  3. Sync specific channel")
    print("  4. Sync specific SKU")
    print("  5. View sync history")
    print("  6. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        status = service.get_channel_sync_status()
        print("\n📊 Channel Status:")
        for ch in status:
            enabled = "✅" if ch["enabled"] else "❌"
            print(f"  {enabled} {ch['channel'].upper()}")
            print(
                f"      Priority: {ch['priority']}, Allocation: {ch['allocation_pct']}%"
            )
            print(
                f"      Listings: {ch['listings']}, Pending sync: {ch['pending_sync']}"
            )
            print(f"      Last sync: {ch['last_sync'] or 'Never'}")

    elif choice == "2":
        print("\n⏳ Syncing all channels...")
        results = await service.sync_all_channels()

        for channel, result in results.items():
            if result["success"]:
                print(f"  ✅ {channel}: {result['synced']} synced")
            else:
                print(f"  ❌ {channel}: {result.get('error')}")

    elif choice == "3":
        channel = input("  Channel (woocommerce/ebay/amazon): ").strip()
        print(f"\n⏳ Syncing {channel}...")
        result = await service.sync_channel(Channel(channel))

        if result["success"]:
            print(f"  ✅ Synced {result['synced']} items")
        else:
            print(f"  ❌ {result.get('error')}")

    elif choice == "4":
        sku = input("  SKU: ").strip()
        print(f"\n⏳ Syncing {sku} to all channels...")
        results = await service.sync_sku(sku)

        for channel, result in results.items():
            status = "✅" if result.get("synced", 0) > 0 else "⚠️"
            print(f"  {status} {channel}")

    elif choice == "5":
        print("\n📋 Recent Sync Events:")
        events = service.sync_events[-10:]
        for event in reversed(events):
            status = "✅" if event.status == SyncStatus.COMPLETED else "❌"
            print(f"  {status} {event.channel.value}: {event.sku}")
            print(f"      {event.old_quantity} → {event.new_quantity}")


async def allocation_menu(service: InventorySyncService) -> None:
    """Stock allocation submenu."""
    print("\n📊 STOCK ALLOCATION:")
    print("  1. View current allocations")
    print("  2. Reallocate SKU")
    print("  3. Reallocate all")
    print("  4. View channel inventory")
    print("  5. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        print("\n📊 Current Allocations (sample):")
        for sku in list(service.products.keys())[:5]:
            inv = service.get_inventory(sku)
            print(f"\n  {sku} (Available: {inv.available_quantity if inv else 0}):")

            for channel in [Channel.WOOCOMMERCE, Channel.EBAY, Channel.AMAZON]:
                ch_inv = service.channel_inventory.get((sku, channel))
                if ch_inv:
                    print(
                        f"    {channel.value}: {ch_inv.allocated_quantity} allocated, {ch_inv.listed_quantity} listed"
                    )

    elif choice == "2":
        sku = input("  SKU: ").strip()
        strategy = (
            input("  Strategy (equal/weighted/priority/buffer): ").strip() or "weighted"
        )

        allocation = service.allocate_stock(sku, AllocationStrategy(strategy))
        print(f"\n✅ Allocated {sku}:")
        for channel, qty in allocation.allocations.items():
            print(f"    {channel.value}: {qty}")

    elif choice == "3":
        strategy = (
            input("  Strategy (equal/weighted/priority/buffer): ").strip() or "weighted"
        )
        print(f"\n⏳ Reallocating all products with {strategy} strategy...")

        for sku in service.products.keys():
            service.allocate_stock(sku, AllocationStrategy(strategy))

        print(f"✅ Reallocated {len(service.products)} products")

    elif choice == "4":
        channel = input("  Channel (woocommerce/ebay/amazon): ").strip()

        print(f"\n📊 Inventory on {channel}:")
        for key, ch_inv in service.channel_inventory.items():
            if key[1] == Channel(channel):
                sync_status = "🔄" if ch_inv.pending_sync else "✅"
                print(
                    f"  {sync_status} {key[0]}: {ch_inv.allocated_quantity} allocated"
                )


async def oversell_menu(service: InventorySyncService) -> None:
    """Oversell prevention submenu."""
    print("\n⚠️ OVERSELL PREVENTION:")
    print("  1. Check oversell risk")
    print("  2. Auto-prevent oversell")
    print("  3. Toggle oversell protection")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        print("\n📊 Oversell Risk Check:")
        at_risk = 0

        for sku in service.products.keys():
            risk = service.check_oversell_risk(sku)
            if risk.get("oversell_risk"):
                at_risk += 1
                print(f"  ⚠️ {sku}:")
                print(
                    f"      Available: {risk['available']}, Listed: {risk['total_listed']}"
                )
                print(f"      Oversell amount: {risk['oversell_amount']}")

        if at_risk == 0:
            print("  ✅ No oversell risks detected")
        else:
            print(f"\n  ⚠️ {at_risk} products at risk of overselling")

    elif choice == "2":
        print("\n⏳ Running oversell prevention...")
        total_adjustments = 0

        for sku in service.products.keys():
            adjustments = service.prevent_oversell(sku)
            if adjustments:
                total_adjustments += len(adjustments)
                print(f"  {sku}:")
                for adj in adjustments:
                    print(
                        f"    {adj['channel']}: {adj['old_quantity']} → {adj['new_quantity']}"
                    )

        if total_adjustments == 0:
            print("  ✅ No adjustments needed")
        else:
            print(f"\n  ✅ Made {total_adjustments} adjustments")

    elif choice == "3":
        current = service.oversell_protection
        service.oversell_protection = not current
        status = "ENABLED" if service.oversell_protection else "DISABLED"
        print(f"\n✅ Oversell protection: {status}")


async def alerts_menu(service: InventorySyncService) -> None:
    """Alerts and reorder submenu."""
    print("\n🔔 ALERTS & REORDER:")
    print("  1. View active alerts")
    print("  2. Low stock report")
    print("  3. Calculate reorder point")
    print("  4. Update reorder settings")
    print("  5. Acknowledge alert")
    print("  6. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        alerts = service.get_active_alerts()
        print(f"\n🔔 Active Alerts: {len(alerts)}")

        for alert in alerts[:10]:
            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}[
                alert.severity.value
            ]
            print(f"\n  {icon} {alert.alert_id}")
            print(f"      {alert.product_name} ({alert.sku})")
            print(f"      {alert.message}")
            print(
                f"      Current: {alert.current_quantity}, Threshold: {alert.threshold}"
            )

    elif choice == "2":
        report = service.create_low_stock_report()
        print(f"\n📊 Low Stock Report: {len(report)} items")

        for item in report:
            status = "🔴" if item["status"] == "out_of_stock" else "🟡"
            print(f"  {status} {item['sku']}: {item['name']}")
            print(
                f"      Available: {item['available']} / Reorder: {item['reorder_point']}"
            )
            print(f"      Suggested order: {item['suggested_order_qty']}")

    elif choice == "3":
        sku = input("  SKU: ").strip()
        daily_sales = float(input("  Daily sales velocity: ").strip() or "5")
        lead_time = int(input("  Lead time (days): ").strip() or "14")

        calc = service.calculate_reorder_point(sku, daily_sales, lead_time)

        print(f"\n📊 Reorder Calculation for {sku}:")
        print(f"   Calculated reorder point: {calc['calculated_reorder_point']}")
        print(f"   Calculated safety stock: {calc['calculated_safety_stock']}")
        print(f"   Economic order quantity: {calc['economic_order_quantity']}")
        print(f"   Current reorder point: {calc['current_reorder_point']}")

    elif choice == "4":
        sku = input("  SKU: ").strip()
        reorder_pt = int(input("  Reorder point: ").strip() or "20")
        reorder_qty = int(input("  Reorder quantity: ").strip() or "50")
        safety = int(input("  Safety stock: ").strip() or "10")

        if service.update_reorder_settings(sku, reorder_pt, reorder_qty, safety):
            print(f"\n✅ Updated reorder settings for {sku}")
        else:
            print("❌ Product not found")

    elif choice == "5":
        alert_id = input("  Alert ID: ").strip()
        if service.acknowledge_alert(alert_id, "User"):
            print("✅ Alert acknowledged")
        else:
            print("❌ Alert not found")


async def po_menu(service: InventorySyncService) -> None:
    """Purchase orders submenu."""
    print("\n📋 PURCHASE ORDERS:")
    print("  1. View POs")
    print("  2. Create PO")
    print("  3. Auto-generate POs")
    print("  4. Submit PO")
    print("  5. Receive PO")
    print("  6. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        print("\n📋 Purchase Orders:")
        for po in service.purchase_orders.values():
            status_icon = {
                "draft": "📝",
                "submitted": "📤",
                "confirmed": "✅",
                "partially_received": "📦",
                "received": "✅",
                "cancelled": "❌",
            }[po.status.value]

            print(f"\n  {status_icon} {po.po_number} - {po.supplier_name}")
            print(f"      Status: {po.status.value}")
            print(f"      Total: ${po.total_aud:.2f}")
            print(f"      Lines: {len(po.lines)}")

    elif choice == "2":
        supplier_id = input("  Supplier ID (or Enter for first): ").strip()
        if not supplier_id:
            supplier_id = list(service.suppliers.keys())[0]

        lines = []
        print("  Add items (empty SKU to finish):")
        while True:
            sku = input("    SKU: ").strip()
            if not sku:
                break
            qty = int(input("    Quantity: ").strip() or "10")
            lines.append({"sku": sku, "quantity": qty})

        if lines:
            po = service.create_purchase_order(supplier_id, lines)
            print(f"\n✅ Created PO: {po.po_number}")
            print(f"   Total: ${po.total_aud:.2f}")

    elif choice == "3":
        print("\n⏳ Auto-generating POs for low stock items...")
        pos = service.auto_generate_pos()

        if pos:
            for po in pos:
                print(f"  ✅ {po.po_number}: {po.supplier_name} (${po.total_aud:.2f})")
        else:
            print("  ✅ No reorders needed")

    elif choice == "4":
        po_number = input("  PO Number: ").strip()
        if service.submit_purchase_order(po_number):
            print("✅ PO submitted")
        else:
            print("❌ Could not submit PO")

    elif choice == "5":
        po_number = input("  PO Number: ").strip()

        po = service.purchase_orders.get(po_number)
        if not po:
            print("❌ PO not found")
            return

        received = []
        print("  Receive items (empty SKU to finish):")
        for line in po.lines:
            remaining = line.quantity_ordered - line.quantity_received
            if remaining > 0:
                print(f"    {line.sku}: {remaining} remaining")
                qty = input("    Quantity received: ").strip()
                if qty:
                    received.append({"sku": line.sku, "quantity": int(qty)})

        if received:
            result = service.receive_purchase_order(po_number, received)
            if result["success"]:
                print(f"\n✅ Received items, PO status: {result['status']}")
            else:
                print(f"❌ {result.get('error')}")


async def supplier_menu(service: InventorySyncService) -> None:
    """Suppliers submenu."""
    print("\n🏢 SUPPLIERS:")
    print("  1. List suppliers")
    print("  2. View lead time stats")
    print("  3. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        print("\n🏢 Suppliers:")
        for supplier in service.suppliers.values():
            status = "✅" if supplier.is_active else "❌"
            print(f"\n  {status} {supplier.name} ({supplier.code})")
            print(f"      Contact: {supplier.contact_name}")
            print(f"      Lead time: {supplier.lead_time_days} days")
            print(f"      Payment: {supplier.payment_terms}")

    elif choice == "2":
        for supplier in service.suppliers.values():
            stats = service.get_supplier_lead_time_stats(supplier.supplier_id)

            if "error" not in stats:
                print(f"\n📊 {supplier.name}:")
                print(f"   Orders: {stats['total_orders']}")
                print(f"   Avg lead time: {stats['avg_lead_time_days']} days")
                print(f"   On-time rate: {stats['on_time_rate']}%")


async def reports_menu(service: InventorySyncService) -> None:
    """Reports submenu."""
    print("\n📊 REPORTS:")
    print("  1. Inventory summary")
    print("  2. Channel sync status")
    print("  3. Low stock report")
    print("  4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        summary = service.get_inventory_summary()

        print("\n📊 INVENTORY SUMMARY")
        print("=" * 40)
        print(f"Total products: {summary['total_products']}")
        print(f"In stock: {summary['in_stock']}")
        print(f"Low stock: {summary['low_stock']}")
        print(f"Out of stock: {summary['out_of_stock']}")
        print(f"Total value: ${summary['total_inventory_value_aud']:,.2f}")
        print(f"Active alerts: {summary['active_alerts']}")
        print(f"Pending POs: {summary['pending_pos']}")

    elif choice == "2":
        status = service.get_channel_sync_status()

        print("\n📊 CHANNEL SYNC STATUS")
        print("=" * 40)
        for ch in status:
            print(f"\n{ch['channel'].upper()}:")
            print(f"  Enabled: {ch['enabled']}")
            print(f"  Priority: {ch['priority']}")
            print(f"  Allocation: {ch['allocation_pct']}%")
            print(f"  Listings: {ch['listings']}")
            print(f"  Pending sync: {ch['pending_sync']}")

    elif choice == "3":
        report = service.create_low_stock_report()

        print("\n📊 LOW STOCK REPORT")
        print("=" * 40)
        print(f"Items needing attention: {len(report)}")

        for item in report[:10]:
            print(f"\n  {item['sku']}: {item['name']}")
            print(f"    Status: {item['status']}")
            print(
                f"    Available: {item['available']} / Reorder: {item['reorder_point']}"
            )
            print(f"    Days to stockout: {item['days_to_stockout']}")


# =============================================================================
# DEMO MODE
# =============================================================================


async def demo_mode(service: InventorySyncService) -> None:
    """Run automated demo."""
    print("\n" + "=" * 60)
    print("📦 MULTI-CHANNEL INVENTORY SYNC DEMO")
    print("=" * 60)

    # 1. Show inventory summary
    print("\n📊 1. INVENTORY OVERVIEW")
    print("-" * 40)
    summary = service.get_inventory_summary()
    print(f"   Products: {summary['total_products']}")
    print(f"   In stock: {summary['in_stock']}")
    print(f"   Low stock: {summary['low_stock']}")
    print(f"   Total value: ${summary['total_inventory_value_aud']:,.2f}")
    await asyncio.sleep(1)

    # 2. Show channel status
    print("\n🔄 2. CHANNEL STATUS")
    print("-" * 40)
    for ch in service.get_channel_sync_status():
        print(
            f"   {ch['channel'].upper()}: {ch['listings']} listings, priority {ch['priority']}"
        )
    await asyncio.sleep(1)

    # 3. Stock allocation demo
    print("\n📊 3. STOCK ALLOCATION DEMO")
    print("-" * 40)

    sku = list(service.products.keys())[0]
    inv = service.get_inventory(sku)
    print(f"   SKU: {sku}")
    print(f"   Available: {inv.available_quantity}")

    allocation = service.allocate_stock(sku, AllocationStrategy.WEIGHTED)
    for channel, qty in allocation.allocations.items():
        print(f"   → {channel.value}: {qty} units")
    await asyncio.sleep(1)

    # 4. Channel sync
    print("\n🔄 4. SYNCING TO CHANNELS")
    print("-" * 40)

    results = await service.sync_all_channels()
    for channel, result in results.items():
        print(f"   ✅ {channel}: {result['synced']} items synced")
    await asyncio.sleep(1)

    # 5. Oversell check
    print("\n⚠️ 5. OVERSELL PREVENTION")
    print("-" * 40)

    # Simulate oversell scenario
    test_sku = list(service.products.keys())[1]
    service.set_inventory(test_sku, 5)  # Low stock

    # Allocate more than available
    for channel in [Channel.WOOCOMMERCE, Channel.EBAY, Channel.AMAZON]:
        key = (test_sku, channel)
        if key in service.channel_inventory:
            service.channel_inventory[key].listed_quantity = 10

    risk = service.check_oversell_risk(test_sku)
    print(
        f"   {test_sku}: Available {risk['available']}, Listed {risk['total_listed']}"
    )
    print(f"   Oversell risk: {'⚠️ YES' if risk['oversell_risk'] else '✅ NO'}")

    if risk["oversell_risk"]:
        adjustments = service.prevent_oversell(test_sku)
        print(f"   Auto-adjustments made: {len(adjustments)}")
    await asyncio.sleep(1)

    # 6. Low stock alerts
    print("\n🔔 6. LOW STOCK ALERTS")
    print("-" * 40)

    # Create low stock scenario
    low_sku = list(service.products.keys())[2]
    service.set_inventory(low_sku, 3)

    alerts = service.get_active_alerts()
    print(f"   Active alerts: {len(alerts)}")
    for alert in alerts[:3]:
        print(f"   • {alert.severity.value.upper()}: {alert.sku} - {alert.alert_type}")
    await asyncio.sleep(1)

    # 7. Auto PO generation
    print("\n📋 7. AUTO PURCHASE ORDER GENERATION")
    print("-" * 40)

    pos = service.auto_generate_pos()
    if pos:
        for po in pos:
            print(f"   ✅ {po.po_number}: {po.supplier_name}")
            print(f"      Items: {len(po.lines)}, Total: ${po.total_aud:.2f}")
    else:
        print("   ✅ No reorders needed")
    await asyncio.sleep(1)

    # 8. PO workflow
    print("\n📦 8. PURCHASE ORDER WORKFLOW")
    print("-" * 40)

    if pos:
        po = pos[0]
        print(f"   PO: {po.po_number}")

        service.submit_purchase_order(po.po_number)
        print("   Status: Submitted ✅")

        service.confirm_purchase_order(po.po_number)
        print("   Status: Confirmed ✅")

        received = [
            {"sku": line.sku, "quantity": line.quantity_ordered} for line in po.lines
        ]
        result = service.receive_purchase_order(po.po_number, received)
        print(f"   Status: {result['status']} ✅")
    await asyncio.sleep(1)

    # 9. Final sync
    print("\n🔄 9. FINAL SYNC")
    print("-" * 40)

    results = await service.sync_all_channels()
    total_synced = sum(r["synced"] for r in results.values())
    print(f"   Total items synced: {total_synced}")

    # Final summary
    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETED")
    print("=" * 60)

    final_summary = service.get_inventory_summary()
    print(f"   Products: {final_summary['total_products']}")
    print(f"   Total value: ${final_summary['total_inventory_value_aud']:,.2f}")
    print(f"   Channels: {final_summary['channels_configured']}")


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WooCommerce Multi-Channel Inventory Sync"
    )
    parser.add_argument("--demo", action="store_true", help="Run automated demo")
    parser.add_argument(
        "--interactive", action="store_true", help="Run interactive mode"
    )

    args = parser.parse_args()

    service = InventorySyncService()
    setup_demo_data(service)

    if args.demo:
        asyncio.run(demo_mode(service))
    elif args.interactive:
        asyncio.run(interactive_mode(service))
    else:
        print("Usage: python 73_woo_inventory_sync.py --demo OR --interactive")
        print("\nRunning demo mode by default...\n")
        asyncio.run(demo_mode(service))


if __name__ == "__main__":
    main()
