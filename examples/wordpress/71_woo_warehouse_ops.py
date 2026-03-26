#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
WooCommerce Warehouse Operations System
======================================

Comprehensive warehouse management for WooCommerce stores including:
- Warehouse location management (bins, aisles, zones)
- Pick lists generation
- Pack station workflow
- Inventory movement tracking
- Stock take / cycle counting
- Receiving goods workflow
- Putaway optimization
- Barcode/SKU lookup

Australian-focused with realistic warehouse workflows.

Usage:
    python 71_woo_warehouse_ops.py --demo
    python 71_woo_warehouse_ops.py --interactive
"""

import argparse
import asyncio
import json
import random
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from collections import defaultdict

# =============================================================================
# ENUMS
# =============================================================================


class ZoneType(Enum):
    """Warehouse zone types."""

    RECEIVING = "receiving"
    PUTAWAY = "putaway"
    BULK_STORAGE = "bulk_storage"
    PICK_FACE = "pick_face"
    PACKING = "packing"
    DISPATCH = "dispatch"
    RETURNS = "returns"
    QUARANTINE = "quarantine"
    COLD_STORAGE = "cold_storage"
    HIGH_VALUE = "high_value"


class MovementType(Enum):
    """Inventory movement types."""

    RECEIVE = "receive"
    PUTAWAY = "putaway"
    PICK = "pick"
    PACK = "pack"
    SHIP = "ship"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    DAMAGE = "damage"
    CYCLE_COUNT = "cycle_count"


class PickStatus(Enum):
    """Pick list status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class StockTakeStatus(Enum):
    """Stock take status."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VARIANCE_REVIEW = "variance_review"
    APPROVED = "approved"


class PackStatus(Enum):
    """Pack station status."""

    AWAITING_ITEMS = "awaiting_items"
    PACKING = "packing"
    PACKED = "packed"
    LABELLED = "labelled"
    DISPATCHED = "dispatched"


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class WarehouseZone:
    """Warehouse zone definition."""

    zone_id: str
    zone_type: ZoneType
    name: str
    description: str
    temperature_controlled: bool = False
    min_temp_celsius: Optional[float] = None
    max_temp_celsius: Optional[float] = None
    requires_security: bool = False
    max_capacity_cubic_m: float = 0.0
    current_utilization_pct: float = 0.0


@dataclass
class WarehouseAisle:
    """Warehouse aisle definition."""

    aisle_id: str
    zone_id: str
    aisle_number: str
    description: str
    num_bays: int
    levels_per_bay: int
    bins_per_level: int
    aisle_type: str = "standard"  # standard, narrow, wide
    forklift_accessible: bool = True


@dataclass
class WarehouseBin:
    """Individual storage bin/location."""

    bin_id: str
    aisle_id: str
    zone_id: str
    location_code: str  # e.g., A-01-02-03 (Aisle-Bay-Level-Bin)
    bin_type: str = "standard"  # standard, bulk, small_parts, pallet
    max_weight_kg: float = 100.0
    max_volume_cubic_m: float = 0.5
    current_weight_kg: float = 0.0
    current_volume_cubic_m: float = 0.0
    is_active: bool = True
    is_reserved: bool = False
    reserved_for_sku: Optional[str] = None


@dataclass
class Product:
    """Product/SKU definition."""

    sku: str
    barcode: str
    name: str
    description: str
    category: str
    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float
    unit_cost_aud: float
    requires_cold_storage: bool = False
    is_fragile: bool = False
    is_hazardous: bool = False
    is_high_value: bool = False
    min_stock_level: int = 10
    reorder_quantity: int = 50


@dataclass
class InventoryItem:
    """Inventory at a specific location."""

    inventory_id: str
    sku: str
    bin_id: str
    quantity: int
    lot_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    received_date: datetime = field(default_factory=datetime.now)
    last_counted: Optional[datetime] = None


@dataclass
class InventoryMovement:
    """Track inventory movement."""

    movement_id: str
    movement_type: MovementType
    sku: str
    quantity: int
    from_bin_id: Optional[str]
    to_bin_id: Optional[str]
    reference_id: str  # Order ID, PO ID, etc.
    performed_by: str
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""


@dataclass
class PickListItem:
    """Individual item on a pick list."""

    item_id: str
    sku: str
    product_name: str
    quantity_required: int
    quantity_picked: int = 0
    bin_location: str = ""
    picked_by: Optional[str] = None
    picked_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class PickList:
    """Pick list for order fulfillment."""

    pick_list_id: str
    order_ids: list[str]
    status: PickStatus
    priority: int  # 1=highest, 5=lowest
    items: list[PickListItem] = field(default_factory=list)
    assigned_to: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    wave_id: Optional[str] = None


@dataclass
class PackStation:
    """Packing station."""

    station_id: str
    station_name: str
    location: str
    assigned_operator: Optional[str] = None
    current_order_id: Optional[str] = None
    status: PackStatus = PackStatus.AWAITING_ITEMS
    orders_packed_today: int = 0
    avg_pack_time_seconds: float = 0.0


@dataclass
class PackJob:
    """Individual pack job."""

    pack_job_id: str
    order_id: str
    station_id: str
    items: list[dict]  # SKU, quantity, picked
    box_type: str = ""
    box_weight_kg: float = 0.0
    total_weight_kg: float = 0.0
    packing_materials: list[str] = field(default_factory=list)
    status: PackStatus = PackStatus.AWAITING_ITEMS
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    packed_by: Optional[str] = None


@dataclass
class StockTake:
    """Stock take / cycle count."""

    stock_take_id: str
    name: str
    status: StockTakeStatus
    count_type: str  # full, cycle, spot
    zones: list[str]  # Zone IDs to count
    scheduled_date: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    counted_by: list[str] = field(default_factory=list)
    total_items_counted: int = 0
    total_variances: int = 0
    variance_value_aud: float = 0.0


@dataclass
class StockTakeCount:
    """Individual count in a stock take."""

    count_id: str
    stock_take_id: str
    bin_id: str
    sku: str
    expected_quantity: int
    counted_quantity: int
    variance: int = 0
    counted_by: str = ""
    counted_at: datetime = field(default_factory=datetime.now)
    recount_required: bool = False
    notes: str = ""


@dataclass
class ReceivingOrder:
    """Goods receiving order."""

    receiving_id: str
    po_number: str
    supplier_name: str
    expected_date: datetime
    received_date: Optional[datetime] = None
    status: str = "pending"  # pending, in_progress, completed, variance
    items: list[dict] = field(default_factory=list)
    received_by: Optional[str] = None
    dock_door: str = ""
    notes: str = ""


@dataclass
class PutawayTask:
    """Putaway task after receiving."""

    task_id: str
    receiving_id: str
    sku: str
    quantity: int
    from_location: str  # Receiving area
    suggested_bin: str
    actual_bin: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed
    assigned_to: Optional[str] = None
    completed_at: Optional[datetime] = None


# =============================================================================
# WAREHOUSE OPERATIONS SERVICE
# =============================================================================


class WarehouseOpsService:
    """Warehouse operations management service."""

    def __init__(self):
        self.zones: dict[str, WarehouseZone] = {}
        self.aisles: dict[str, WarehouseAisle] = {}
        self.bins: dict[str, WarehouseBin] = {}
        self.products: dict[str, Product] = {}
        self.inventory: dict[str, InventoryItem] = {}
        self.movements: list[InventoryMovement] = []
        self.pick_lists: dict[str, PickList] = {}
        self.pack_stations: dict[str, PackStation] = {}
        self.pack_jobs: dict[str, PackJob] = {}
        self.stock_takes: dict[str, StockTake] = {}
        self.stock_counts: list[StockTakeCount] = []
        self.receiving_orders: dict[str, ReceivingOrder] = {}
        self.putaway_tasks: dict[str, PutawayTask] = {}

        # Index for fast lookups
        self.sku_to_bins: dict[str, list[str]] = defaultdict(list)
        self.barcode_to_sku: dict[str, str] = {}

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
    # Zone Management
    # -------------------------------------------------------------------------

    def create_zone(
        self,
        zone_type: ZoneType,
        name: str,
        description: str,
        temperature_controlled: bool = False,
        min_temp: Optional[float] = None,
        max_temp: Optional[float] = None,
        requires_security: bool = False,
        max_capacity: float = 1000.0,
    ) -> WarehouseZone:
        """Create a warehouse zone."""
        zone = WarehouseZone(
            zone_id=self._generate_id("ZONE"),
            zone_type=zone_type,
            name=name,
            description=description,
            temperature_controlled=temperature_controlled,
            min_temp_celsius=min_temp,
            max_temp_celsius=max_temp,
            requires_security=requires_security,
            max_capacity_cubic_m=max_capacity,
        )
        self.zones[zone.zone_id] = zone
        return zone

    def get_zone(self, zone_id: str) -> Optional[WarehouseZone]:
        """Get zone by ID."""
        return self.zones.get(zone_id)

    def list_zones(self, zone_type: Optional[ZoneType] = None) -> list[WarehouseZone]:
        """List all zones, optionally filtered by type."""
        zones = list(self.zones.values())
        if zone_type:
            zones = [z for z in zones if z.zone_type == zone_type]
        return zones

    # -------------------------------------------------------------------------
    # Aisle Management
    # -------------------------------------------------------------------------

    def create_aisle(
        self,
        zone_id: str,
        aisle_number: str,
        description: str,
        num_bays: int,
        levels_per_bay: int,
        bins_per_level: int,
        aisle_type: str = "standard",
        forklift_accessible: bool = True,
    ) -> WarehouseAisle:
        """Create an aisle in a zone."""
        if zone_id not in self.zones:
            raise ValueError(f"Zone {zone_id} not found")

        aisle = WarehouseAisle(
            aisle_id=self._generate_id("AISLE"),
            zone_id=zone_id,
            aisle_number=aisle_number,
            description=description,
            num_bays=num_bays,
            levels_per_bay=levels_per_bay,
            bins_per_level=bins_per_level,
            aisle_type=aisle_type,
            forklift_accessible=forklift_accessible,
        )
        self.aisles[aisle.aisle_id] = aisle
        return aisle

    def auto_create_bins_for_aisle(self, aisle_id: str) -> list[WarehouseBin]:
        """Auto-create bins for an aisle based on its configuration."""
        aisle = self.aisles.get(aisle_id)
        if not aisle:
            raise ValueError(f"Aisle {aisle_id} not found")

        created_bins = []
        for bay in range(1, aisle.num_bays + 1):
            for level in range(1, aisle.levels_per_bay + 1):
                for bin_num in range(1, aisle.bins_per_level + 1):
                    location_code = (
                        f"{aisle.aisle_number}-{bay:02d}-{level:02d}-{bin_num:02d}"
                    )

                    bin_obj = WarehouseBin(
                        bin_id=self._generate_id("BIN"),
                        aisle_id=aisle_id,
                        zone_id=aisle.zone_id,
                        location_code=location_code,
                        bin_type="standard",
                        max_weight_kg=100.0 if level <= 2 else 50.0,
                        max_volume_cubic_m=0.5 if level <= 2 else 0.25,
                    )
                    self.bins[bin_obj.bin_id] = bin_obj
                    created_bins.append(bin_obj)

        return created_bins

    # -------------------------------------------------------------------------
    # Product / SKU Management
    # -------------------------------------------------------------------------

    def create_product(
        self,
        sku: str,
        barcode: str,
        name: str,
        description: str,
        category: str,
        weight_kg: float,
        length_cm: float,
        width_cm: float,
        height_cm: float,
        unit_cost_aud: float,
        **kwargs,
    ) -> Product:
        """Create a product."""
        product = Product(
            sku=sku,
            barcode=barcode,
            name=name,
            description=description,
            category=category,
            weight_kg=weight_kg,
            length_cm=length_cm,
            width_cm=width_cm,
            height_cm=height_cm,
            unit_cost_aud=unit_cost_aud,
            requires_cold_storage=kwargs.get("requires_cold_storage", False),
            is_fragile=kwargs.get("is_fragile", False),
            is_hazardous=kwargs.get("is_hazardous", False),
            is_high_value=kwargs.get("is_high_value", False),
            min_stock_level=kwargs.get("min_stock_level", 10),
            reorder_quantity=kwargs.get("reorder_quantity", 50),
        )
        self.products[sku] = product
        self.barcode_to_sku[barcode] = sku
        return product

    def lookup_by_barcode(self, barcode: str) -> Optional[Product]:
        """Look up product by barcode."""
        sku = self.barcode_to_sku.get(barcode)
        if sku:
            return self.products.get(sku)
        return None

    def lookup_by_sku(self, sku: str) -> Optional[Product]:
        """Look up product by SKU."""
        return self.products.get(sku)

    def search_products(self, query: str) -> list[Product]:
        """Search products by name or SKU."""
        query_lower = query.lower()
        results = []
        for product in self.products.values():
            if (
                query_lower in product.name.lower()
                or query_lower in product.sku.lower()
                or query_lower in product.description.lower()
            ):
                results.append(product)
        return results

    # -------------------------------------------------------------------------
    # Inventory Management
    # -------------------------------------------------------------------------

    def add_inventory(
        self,
        sku: str,
        bin_id: str,
        quantity: int,
        lot_number: Optional[str] = None,
        expiry_date: Optional[datetime] = None,
    ) -> InventoryItem:
        """Add inventory to a bin."""
        if sku not in self.products:
            raise ValueError(f"Product {sku} not found")
        if bin_id not in self.bins:
            raise ValueError(f"Bin {bin_id} not found")

        inventory = InventoryItem(
            inventory_id=self._generate_id("INV"),
            sku=sku,
            bin_id=bin_id,
            quantity=quantity,
            lot_number=lot_number,
            expiry_date=expiry_date,
        )
        self.inventory[inventory.inventory_id] = inventory
        self.sku_to_bins[sku].append(bin_id)

        # Update bin utilization
        product = self.products[sku]
        volume = (
            (product.length_cm * product.width_cm * product.height_cm)
            / 1000000
            * quantity
        )
        weight = product.weight_kg * quantity
        bin_obj = self.bins[bin_id]
        bin_obj.current_volume_cubic_m += volume
        bin_obj.current_weight_kg += weight

        return inventory

    def get_inventory_for_sku(self, sku: str) -> list[InventoryItem]:
        """Get all inventory records for a SKU."""
        return [inv for inv in self.inventory.values() if inv.sku == sku]

    def get_total_stock(self, sku: str) -> int:
        """Get total stock quantity for a SKU across all locations."""
        return sum(inv.quantity for inv in self.inventory.values() if inv.sku == sku)

    def find_inventory_locations(self, sku: str) -> list[dict]:
        """Find all locations where a SKU is stored."""
        locations = []
        for inv in self.inventory.values():
            if inv.sku == sku and inv.quantity > 0:
                bin_obj = self.bins.get(inv.bin_id)
                locations.append(
                    {
                        "inventory_id": inv.inventory_id,
                        "bin_id": inv.bin_id,
                        "location_code": bin_obj.location_code if bin_obj else "",
                        "quantity": inv.quantity,
                        "lot_number": inv.lot_number,
                        "expiry_date": inv.expiry_date,
                    }
                )
        # Sort by FIFO (received date)
        locations.sort(
            key=lambda x: next(
                (
                    inv.received_date
                    for inv in self.inventory.values()
                    if inv.inventory_id == x["inventory_id"]
                ),
                datetime.now(),
            )
        )
        return locations

    def record_movement(
        self,
        movement_type: MovementType,
        sku: str,
        quantity: int,
        from_bin_id: Optional[str],
        to_bin_id: Optional[str],
        reference_id: str,
        performed_by: str,
        notes: str = "",
    ) -> InventoryMovement:
        """Record an inventory movement."""
        movement = InventoryMovement(
            movement_id=self._generate_id("MOV"),
            movement_type=movement_type,
            sku=sku,
            quantity=quantity,
            from_bin_id=from_bin_id,
            to_bin_id=to_bin_id,
            reference_id=reference_id,
            performed_by=performed_by,
            notes=notes,
        )
        self.movements.append(movement)
        return movement

    def transfer_inventory(
        self,
        sku: str,
        from_bin_id: str,
        to_bin_id: str,
        quantity: int,
        performed_by: str,
        reason: str = "",
    ) -> bool:
        """Transfer inventory between bins."""
        # Find inventory in source bin
        source_inv = None
        for inv in self.inventory.values():
            if (
                inv.sku == sku
                and inv.bin_id == from_bin_id
                and inv.quantity >= quantity
            ):
                source_inv = inv
                break

        if not source_inv:
            return False

        # Reduce source
        source_inv.quantity -= quantity

        # Add to destination (or create new)
        dest_inv = None
        for inv in self.inventory.values():
            if inv.sku == sku and inv.bin_id == to_bin_id:
                dest_inv = inv
                break

        if dest_inv:
            dest_inv.quantity += quantity
        else:
            self.add_inventory(sku, to_bin_id, quantity)

        # Record movement
        self.record_movement(
            MovementType.TRANSFER,
            sku,
            quantity,
            from_bin_id,
            to_bin_id,
            f"TRANSFER-{datetime.now().strftime('%Y%m%d')}",
            performed_by,
            reason,
        )

        return True

    # -------------------------------------------------------------------------
    # Pick List Management
    # -------------------------------------------------------------------------

    def create_pick_list(
        self,
        order_ids: list[str],
        order_items: list[dict],
        priority: int = 3,
        wave_id: Optional[str] = None,
    ) -> PickList:
        """Create a pick list from orders."""
        items = []

        # Consolidate items from orders
        sku_quantities = defaultdict(int)
        for item in order_items:
            sku_quantities[item["sku"]] += item["quantity"]

        for sku, qty in sku_quantities.items():
            product = self.products.get(sku)
            locations = self.find_inventory_locations(sku)

            best_location = locations[0]["location_code"] if locations else "NOT_FOUND"

            pick_item = PickListItem(
                item_id=self._generate_id("PICK"),
                sku=sku,
                product_name=product.name if product else sku,
                quantity_required=qty,
                bin_location=best_location,
            )
            items.append(pick_item)

        # Sort by location for efficient picking
        items.sort(key=lambda x: x.bin_location)

        pick_list = PickList(
            pick_list_id=self._generate_id("PL"),
            order_ids=order_ids,
            status=PickStatus.PENDING,
            priority=priority,
            items=items,
            wave_id=wave_id,
        )
        self.pick_lists[pick_list.pick_list_id] = pick_list
        return pick_list

    def assign_pick_list(self, pick_list_id: str, picker: str) -> bool:
        """Assign a pick list to a picker."""
        pick_list = self.pick_lists.get(pick_list_id)
        if not pick_list or pick_list.status != PickStatus.PENDING:
            return False

        pick_list.assigned_to = picker
        pick_list.status = PickStatus.IN_PROGRESS
        pick_list.started_at = datetime.now()
        return True

    def record_pick(
        self, pick_list_id: str, item_id: str, quantity_picked: int, picker: str
    ) -> bool:
        """Record a pick action."""
        pick_list = self.pick_lists.get(pick_list_id)
        if not pick_list:
            return False

        for item in pick_list.items:
            if item.item_id == item_id:
                item.quantity_picked = quantity_picked
                item.picked_by = picker
                item.picked_at = datetime.now()

                # Record movement
                locations = self.find_inventory_locations(item.sku)
                if locations:
                    from_bin = locations[0]["bin_id"]
                    self.record_movement(
                        MovementType.PICK,
                        item.sku,
                        quantity_picked,
                        from_bin,
                        None,  # Will go to packing
                        pick_list_id,
                        picker,
                    )

                    # Update inventory
                    for inv in self.inventory.values():
                        if inv.bin_id == from_bin and inv.sku == item.sku:
                            inv.quantity -= quantity_picked
                            break

                return True
        return False

    def complete_pick_list(self, pick_list_id: str) -> dict:
        """Complete a pick list."""
        pick_list = self.pick_lists.get(pick_list_id)
        if not pick_list:
            return {"success": False, "error": "Pick list not found"}

        total_required = sum(item.quantity_required for item in pick_list.items)
        total_picked = sum(item.quantity_picked for item in pick_list.items)

        if total_picked == total_required:
            pick_list.status = PickStatus.COMPLETED
        elif total_picked > 0:
            pick_list.status = PickStatus.PARTIAL

        pick_list.completed_at = datetime.now()

        return {
            "success": True,
            "status": pick_list.status.value,
            "total_required": total_required,
            "total_picked": total_picked,
            "completion_rate": (
                (total_picked / total_required * 100) if total_required > 0 else 0
            ),
        }

    def get_pending_pick_lists(self) -> list[PickList]:
        """Get all pending pick lists sorted by priority."""
        pending = [
            pl for pl in self.pick_lists.values() if pl.status == PickStatus.PENDING
        ]
        pending.sort(key=lambda x: (x.priority, x.created_at))
        return pending

    # -------------------------------------------------------------------------
    # Pack Station Management
    # -------------------------------------------------------------------------

    def create_pack_station(self, station_name: str, location: str) -> PackStation:
        """Create a pack station."""
        station = PackStation(
            station_id=self._generate_id("PACK"),
            station_name=station_name,
            location=location,
        )
        self.pack_stations[station.station_id] = station
        return station

    def assign_operator_to_station(self, station_id: str, operator: str) -> bool:
        """Assign an operator to a pack station."""
        station = self.pack_stations.get(station_id)
        if not station:
            return False
        station.assigned_operator = operator
        return True

    def create_pack_job(
        self, order_id: str, station_id: str, items: list[dict]
    ) -> PackJob:
        """Create a pack job."""
        job = PackJob(
            pack_job_id=self._generate_id("JOB"),
            order_id=order_id,
            station_id=station_id,
            items=items,
            status=PackStatus.AWAITING_ITEMS,
        )
        self.pack_jobs[job.pack_job_id] = job
        return job

    def start_packing(self, pack_job_id: str, operator: str) -> bool:
        """Start packing a job."""
        job = self.pack_jobs.get(pack_job_id)
        if not job:
            return False

        job.status = PackStatus.PACKING
        job.started_at = datetime.now()
        job.packed_by = operator

        # Update station
        station = self.pack_stations.get(job.station_id)
        if station:
            station.status = PackStatus.PACKING
            station.current_order_id = job.order_id

        return True

    def recommend_box_size(self, items: list[dict]) -> dict:
        """Recommend box size based on items."""
        total_volume = 0.0
        total_weight = 0.0
        max_length = 0.0
        max_width = 0.0
        has_fragile = False

        for item in items:
            product = self.products.get(item.get("sku"))
            if product:
                qty = item.get("quantity", 1)
                vol = (product.length_cm * product.width_cm * product.height_cm) / 1000
                total_volume += vol * qty
                total_weight += product.weight_kg * qty
                max_length = max(max_length, product.length_cm)
                max_width = max(max_width, product.width_cm)
                has_fragile = has_fragile or product.is_fragile

        # Box recommendations
        boxes = [
            {"type": "SMALL", "internal_vol": 5, "max_weight": 5, "dims": "20x15x10cm"},
            {
                "type": "MEDIUM",
                "internal_vol": 15,
                "max_weight": 15,
                "dims": "30x25x20cm",
            },
            {
                "type": "LARGE",
                "internal_vol": 40,
                "max_weight": 25,
                "dims": "40x35x30cm",
            },
            {
                "type": "XLARGE",
                "internal_vol": 80,
                "max_weight": 30,
                "dims": "50x45x40cm",
            },
        ]

        recommended = None
        for box in boxes:
            if (
                total_volume <= box["internal_vol"] * 0.7
                and total_weight <= box["max_weight"]
            ):
                recommended = box
                break

        if not recommended:
            recommended = boxes[-1]  # Largest box

        packing_materials = ["tape"]
        if has_fragile:
            packing_materials.extend(["bubble_wrap", "packing_peanuts"])
        else:
            packing_materials.append("paper_fill")

        return {
            "recommended_box": recommended["type"],
            "box_dimensions": recommended["dims"],
            "total_item_volume_liters": round(total_volume, 2),
            "total_weight_kg": round(total_weight, 2),
            "packing_materials": packing_materials,
            "fragile_handling": has_fragile,
        }

    def complete_packing(
        self,
        pack_job_id: str,
        box_type: str,
        total_weight_kg: float,
        packing_materials: list[str],
    ) -> bool:
        """Complete a packing job."""
        job = self.pack_jobs.get(pack_job_id)
        if not job:
            return False

        job.status = PackStatus.PACKED
        job.completed_at = datetime.now()
        job.box_type = box_type
        job.total_weight_kg = total_weight_kg
        job.packing_materials = packing_materials

        # Record movements
        for item in job.items:
            self.record_movement(
                MovementType.PACK,
                item.get("sku", ""),
                item.get("quantity", 1),
                None,
                None,
                job.order_id,
                job.packed_by or "system",
            )

        # Update station
        station = self.pack_stations.get(job.station_id)
        if station:
            station.status = PackStatus.AWAITING_ITEMS
            station.current_order_id = None
            station.orders_packed_today += 1

            # Update average pack time
            if job.started_at and job.completed_at:
                pack_seconds = (job.completed_at - job.started_at).total_seconds()
                if station.avg_pack_time_seconds == 0:
                    station.avg_pack_time_seconds = pack_seconds
                else:
                    station.avg_pack_time_seconds = (
                        station.avg_pack_time_seconds * 0.9 + pack_seconds * 0.1
                    )

        return True

    # -------------------------------------------------------------------------
    # Stock Take / Cycle Counting
    # -------------------------------------------------------------------------

    def create_stock_take(
        self, name: str, count_type: str, zones: list[str], scheduled_date: datetime
    ) -> StockTake:
        """Create a stock take."""
        stock_take = StockTake(
            stock_take_id=self._generate_id("ST"),
            name=name,
            status=StockTakeStatus.SCHEDULED,
            count_type=count_type,
            zones=zones,
            scheduled_date=scheduled_date,
        )
        self.stock_takes[stock_take.stock_take_id] = stock_take
        return stock_take

    def start_stock_take(self, stock_take_id: str, counters: list[str]) -> bool:
        """Start a stock take."""
        stock_take = self.stock_takes.get(stock_take_id)
        if not stock_take or stock_take.status != StockTakeStatus.SCHEDULED:
            return False

        stock_take.status = StockTakeStatus.IN_PROGRESS
        stock_take.started_at = datetime.now()
        stock_take.counted_by = counters
        return True

    def get_bins_for_stock_take(self, stock_take_id: str) -> list[dict]:
        """Get bins to count for a stock take."""
        stock_take = self.stock_takes.get(stock_take_id)
        if not stock_take:
            return []

        bins_to_count = []
        for bin_obj in self.bins.values():
            if bin_obj.zone_id in stock_take.zones and bin_obj.is_active:
                # Get expected inventory
                expected_items = []
                for inv in self.inventory.values():
                    if inv.bin_id == bin_obj.bin_id and inv.quantity > 0:
                        expected_items.append(
                            {"sku": inv.sku, "expected_qty": inv.quantity}
                        )

                bins_to_count.append(
                    {
                        "bin_id": bin_obj.bin_id,
                        "location_code": bin_obj.location_code,
                        "expected_items": expected_items,
                    }
                )

        return bins_to_count

    def record_count(
        self,
        stock_take_id: str,
        bin_id: str,
        sku: str,
        expected_qty: int,
        counted_qty: int,
        counter: str,
        notes: str = "",
    ) -> StockTakeCount:
        """Record a count in a stock take."""
        variance = counted_qty - expected_qty
        recount = abs(variance) > 0 and abs(variance) / max(expected_qty, 1) > 0.1

        count = StockTakeCount(
            count_id=self._generate_id("CNT"),
            stock_take_id=stock_take_id,
            bin_id=bin_id,
            sku=sku,
            expected_quantity=expected_qty,
            counted_quantity=counted_qty,
            variance=variance,
            counted_by=counter,
            recount_required=recount,
            notes=notes,
        )
        self.stock_counts.append(count)

        # Update stock take totals
        stock_take = self.stock_takes.get(stock_take_id)
        if stock_take:
            stock_take.total_items_counted += 1
            if variance != 0:
                stock_take.total_variances += 1
                product = self.products.get(sku)
                if product:
                    stock_take.variance_value_aud += (
                        abs(variance) * product.unit_cost_aud
                    )

        return count

    def complete_stock_take(self, stock_take_id: str) -> dict:
        """Complete a stock take and generate summary."""
        stock_take = self.stock_takes.get(stock_take_id)
        if not stock_take:
            return {"success": False, "error": "Stock take not found"}

        counts = [c for c in self.stock_counts if c.stock_take_id == stock_take_id]
        recounts_needed = [c for c in counts if c.recount_required]

        if recounts_needed:
            stock_take.status = StockTakeStatus.VARIANCE_REVIEW
        else:
            stock_take.status = StockTakeStatus.COMPLETED

        stock_take.completed_at = datetime.now()

        return {
            "success": True,
            "stock_take_id": stock_take_id,
            "status": stock_take.status.value,
            "total_counted": stock_take.total_items_counted,
            "total_variances": stock_take.total_variances,
            "variance_value_aud": round(stock_take.variance_value_aud, 2),
            "recounts_required": len(recounts_needed),
            "accuracy_rate": round(
                (stock_take.total_items_counted - stock_take.total_variances)
                / max(stock_take.total_items_counted, 1)
                * 100,
                2,
            ),
        }

    def apply_stock_take_adjustments(self, stock_take_id: str, approved_by: str) -> int:
        """Apply stock take variances to inventory."""
        counts = [
            c
            for c in self.stock_counts
            if c.stock_take_id == stock_take_id and c.variance != 0
        ]

        adjustments_made = 0
        for count in counts:
            # Find and update inventory
            for inv in self.inventory.values():
                if inv.bin_id == count.bin_id and inv.sku == count.sku:
                    old_qty = inv.quantity
                    inv.quantity = count.counted_quantity
                    inv.last_counted = count.counted_at

                    # Record adjustment
                    self.record_movement(
                        MovementType.ADJUSTMENT,
                        count.sku,
                        abs(count.variance),
                        count.bin_id if count.variance < 0 else None,
                        count.bin_id if count.variance > 0 else None,
                        stock_take_id,
                        approved_by,
                        f"Stock take adjustment: {old_qty} -> {count.counted_quantity}",
                    )
                    adjustments_made += 1
                    break

        stock_take = self.stock_takes.get(stock_take_id)
        if stock_take:
            stock_take.status = StockTakeStatus.APPROVED

        return adjustments_made

    # -------------------------------------------------------------------------
    # Receiving Goods
    # -------------------------------------------------------------------------

    def create_receiving_order(
        self,
        po_number: str,
        supplier_name: str,
        expected_date: datetime,
        items: list[dict],
        dock_door: str = "",
    ) -> ReceivingOrder:
        """Create a receiving order."""
        order = ReceivingOrder(
            receiving_id=self._generate_id("RCV"),
            po_number=po_number,
            supplier_name=supplier_name,
            expected_date=expected_date,
            items=items,
            dock_door=dock_door,
        )
        self.receiving_orders[order.receiving_id] = order
        return order

    def start_receiving(self, receiving_id: str, receiver: str, dock_door: str) -> bool:
        """Start receiving goods."""
        order = self.receiving_orders.get(receiving_id)
        if not order or order.status != "pending":
            return False

        order.status = "in_progress"
        order.received_by = receiver
        order.dock_door = dock_door
        order.received_date = datetime.now()
        return True

    def receive_item(
        self,
        receiving_id: str,
        sku: str,
        quantity_received: int,
        lot_number: Optional[str] = None,
        expiry_date: Optional[datetime] = None,
        condition: str = "good",
    ) -> dict:
        """Receive an item from a PO."""
        order = self.receiving_orders.get(receiving_id)
        if not order:
            return {"success": False, "error": "Receiving order not found"}

        # Find the expected item
        expected_item = None
        for item in order.items:
            if item.get("sku") == sku:
                expected_item = item
                break

        if not expected_item:
            return {"success": False, "error": f"SKU {sku} not on this PO"}

        expected_qty = expected_item.get("quantity", 0)
        already_received = expected_item.get("received", 0)

        # Update received quantity
        expected_item["received"] = already_received + quantity_received
        expected_item["lot_number"] = lot_number
        expected_item["condition"] = condition

        # Record movement
        self.record_movement(
            MovementType.RECEIVE,
            sku,
            quantity_received,
            None,
            "RECEIVING",  # Receiving area
            order.po_number,
            order.received_by or "system",
            f"Lot: {lot_number}, Condition: {condition}",
        )

        variance = expected_item["received"] - expected_qty

        return {
            "success": True,
            "sku": sku,
            "expected": expected_qty,
            "received": expected_item["received"],
            "variance": variance,
            "variance_type": (
                "over" if variance > 0 else "under" if variance < 0 else "match"
            ),
        }

    def complete_receiving(self, receiving_id: str) -> dict:
        """Complete receiving and create putaway tasks."""
        order = self.receiving_orders.get(receiving_id)
        if not order:
            return {"success": False, "error": "Receiving order not found"}

        putaway_tasks_created = []
        total_variance = 0

        for item in order.items:
            sku = item.get("sku")
            expected = item.get("quantity", 0)
            received = item.get("received", 0)
            total_variance += received - expected

            if received > 0:
                # Create putaway task
                suggested_bin = self._suggest_putaway_bin(sku)
                task = PutawayTask(
                    task_id=self._generate_id("PUT"),
                    receiving_id=receiving_id,
                    sku=sku,
                    quantity=received,
                    from_location="RECEIVING",
                    suggested_bin=suggested_bin,
                )
                self.putaway_tasks[task.task_id] = task
                putaway_tasks_created.append(task.task_id)

        if total_variance != 0:
            order.status = "variance"
        else:
            order.status = "completed"

        return {
            "success": True,
            "receiving_id": receiving_id,
            "status": order.status,
            "putaway_tasks": putaway_tasks_created,
            "total_variance": total_variance,
        }

    def _suggest_putaway_bin(self, sku: str) -> str:
        """Suggest optimal bin for putaway."""
        product = self.products.get(sku)
        if not product:
            return "A-01-01-01"  # Default

        # Check existing locations for this SKU
        existing = self.sku_to_bins.get(sku, [])
        for bin_id in existing:
            bin_obj = self.bins.get(bin_id)
            if bin_obj and bin_obj.is_active and not bin_obj.is_reserved:
                # Check if there's room
                if bin_obj.current_volume_cubic_m < bin_obj.max_volume_cubic_m * 0.8:
                    return bin_obj.location_code

        # Find empty bin in appropriate zone
        target_zone = None
        if product.is_high_value:
            zones = self.list_zones(ZoneType.HIGH_VALUE)
            if zones:
                target_zone = zones[0].zone_id
        elif product.requires_cold_storage:
            zones = self.list_zones(ZoneType.COLD_STORAGE)
            if zones:
                target_zone = zones[0].zone_id
        else:
            zones = self.list_zones(ZoneType.PICK_FACE)
            if zones:
                target_zone = zones[0].zone_id

        # Find available bin
        for bin_obj in self.bins.values():
            if (
                target_zone
                and bin_obj.zone_id == target_zone
                and bin_obj.is_active
                and not bin_obj.is_reserved
                and bin_obj.current_volume_cubic_m < bin_obj.max_volume_cubic_m * 0.3
            ):
                return bin_obj.location_code

        # Return first available
        for bin_obj in self.bins.values():
            if bin_obj.is_active and not bin_obj.is_reserved:
                return bin_obj.location_code

        return "OVERFLOW-01"

    def complete_putaway(
        self, task_id: str, actual_bin: str, performed_by: str
    ) -> bool:
        """Complete a putaway task."""
        task = self.putaway_tasks.get(task_id)
        if not task or task.status == "completed":
            return False

        # Find bin by location code
        target_bin = None
        for bin_obj in self.bins.values():
            if bin_obj.location_code == actual_bin:
                target_bin = bin_obj
                break

        if not target_bin:
            return False

        # Add inventory to bin
        self.add_inventory(task.sku, target_bin.bin_id, task.quantity)

        # Record movement
        self.record_movement(
            MovementType.PUTAWAY,
            task.sku,
            task.quantity,
            None,
            target_bin.bin_id,
            task.receiving_id,
            performed_by,
        )

        task.status = "completed"
        task.actual_bin = actual_bin
        task.completed_at = datetime.now()

        return True

    def get_pending_putaway_tasks(self) -> list[PutawayTask]:
        """Get all pending putaway tasks."""
        return [t for t in self.putaway_tasks.values() if t.status == "pending"]

    # -------------------------------------------------------------------------
    # Reports and Analytics
    # -------------------------------------------------------------------------

    def get_warehouse_summary(self) -> dict:
        """Get warehouse summary stats."""
        total_inventory_value = 0.0
        total_units = 0
        low_stock_skus = []

        # Calculate by SKU
        for sku, product in self.products.items():
            total_qty = self.get_total_stock(sku)
            total_units += total_qty
            total_inventory_value += total_qty * product.unit_cost_aud

            if total_qty < product.min_stock_level:
                low_stock_skus.append(
                    {
                        "sku": sku,
                        "name": product.name,
                        "current": total_qty,
                        "minimum": product.min_stock_level,
                    }
                )

        return {
            "total_zones": len(self.zones),
            "total_aisles": len(self.aisles),
            "total_bins": len(self.bins),
            "active_bins": len([b for b in self.bins.values() if b.is_active]),
            "total_skus": len(self.products),
            "total_units": total_units,
            "total_inventory_value_aud": round(total_inventory_value, 2),
            "low_stock_count": len(low_stock_skus),
            "low_stock_skus": low_stock_skus[:10],  # Top 10
            "pending_pick_lists": len(self.get_pending_pick_lists()),
            "pending_putaway": len(self.get_pending_putaway_tasks()),
            "active_stock_takes": len(
                [
                    st
                    for st in self.stock_takes.values()
                    if st.status == StockTakeStatus.IN_PROGRESS
                ]
            ),
        }

    def get_movement_history(
        self, sku: Optional[str] = None, days: int = 7
    ) -> list[InventoryMovement]:
        """Get movement history."""
        cutoff = datetime.now() - timedelta(days=days)
        movements = [m for m in self.movements if m.timestamp >= cutoff]
        if sku:
            movements = [m for m in movements if m.sku == sku]
        movements.sort(key=lambda x: x.timestamp, reverse=True)
        return movements

    def get_bin_utilization_report(self) -> list[dict]:
        """Get bin utilization report."""
        zones_util = defaultdict(lambda: {"total": 0, "used_volume": 0, "capacity": 0})

        for bin_obj in self.bins.values():
            if bin_obj.is_active:
                zones_util[bin_obj.zone_id]["total"] += 1
                zones_util[bin_obj.zone_id][
                    "used_volume"
                ] += bin_obj.current_volume_cubic_m
                zones_util[bin_obj.zone_id]["capacity"] += bin_obj.max_volume_cubic_m

        report = []
        for zone_id, data in zones_util.items():
            zone = self.zones.get(zone_id)
            util_pct = (
                (data["used_volume"] / data["capacity"] * 100)
                if data["capacity"] > 0
                else 0
            )
            report.append(
                {
                    "zone_id": zone_id,
                    "zone_name": zone.name if zone else zone_id,
                    "total_bins": data["total"],
                    "utilization_pct": round(util_pct, 1),
                }
            )

        return report


# =============================================================================
# DEMO DATA SETUP
# =============================================================================


def setup_demo_data(service: WarehouseOpsService) -> None:
    """Set up demo warehouse data."""

    # Create zones
    zones = [
        (ZoneType.RECEIVING, "Receiving Dock", "Inbound goods receiving area"),
        (ZoneType.BULK_STORAGE, "Bulk Storage A", "High-density bulk storage"),
        (ZoneType.PICK_FACE, "Pick Face Main", "Primary pick locations"),
        (ZoneType.PACKING, "Pack Stations", "Order packing area"),
        (ZoneType.DISPATCH, "Dispatch Bay", "Outbound shipping area"),
        (
            ZoneType.HIGH_VALUE,
            "Secure Storage",
            "High-value items",
            False,
            None,
            None,
            True,
        ),
        (ZoneType.COLD_STORAGE, "Cold Room", "Temperature controlled", True, 2.0, 8.0),
    ]

    created_zones = []
    for zone_data in zones:
        zone = service.create_zone(*zone_data[:3])
        created_zones.append(zone)

    # Create aisles and bins for pick face
    pick_zone = created_zones[2]
    for aisle_num in ["A", "B", "C"]:
        aisle = service.create_aisle(
            pick_zone.zone_id,
            aisle_num,
            f"Pick Aisle {aisle_num}",
            num_bays=10,
            levels_per_bay=4,
            bins_per_level=2,
        )
        service.auto_create_bins_for_aisle(aisle.aisle_id)

    # Create products (electronics)
    products_data = [
        (
            "MON-27-4K",
            "9312345678901",
            "27-inch 4K Monitor",
            'Professional grade 27" 4K UHD monitor',
            "monitors",
            5.5,
            65,
            45,
            20,
            450.00,
        ),
        (
            "MON-24-FHD",
            "9312345678902",
            "24-inch Full HD Monitor",
            'Budget 24" 1080p monitor',
            "monitors",
            4.2,
            58,
            40,
            18,
            189.00,
        ),
        (
            "MON-32-CURVED",
            "9312345678903",
            "32-inch Curved Monitor",
            "Gaming curved monitor 165Hz",
            "monitors",
            7.8,
            75,
            50,
            25,
            599.00,
        ),
        (
            "CBL-HDMI-2M",
            "9312345678904",
            "HDMI Cable 2m",
            "Premium HDMI 2.1 cable",
            "cables",
            0.15,
            25,
            15,
            3,
            24.95,
        ),
        (
            "CBL-USB-C-1M",
            "9312345678905",
            "USB-C Cable 1m",
            "Fast charging USB-C to USB-C",
            "cables",
            0.08,
            20,
            10,
            2,
            19.95,
        ),
        (
            "CBL-DP-3M",
            "9312345678906",
            "DisplayPort Cable 3m",
            "DisplayPort 1.4 cable",
            "cables",
            0.2,
            30,
            15,
            3,
            34.95,
        ),
        (
            "KB-MECH-RGB",
            "9312345678907",
            "Mechanical RGB Keyboard",
            "Gaming mechanical keyboard",
            "keyboards",
            0.95,
            45,
            15,
            4,
            149.00,
        ),
        (
            "KB-WIRELESS",
            "9312345678908",
            "Wireless Keyboard",
            "Slim wireless keyboard",
            "keyboards",
            0.45,
            42,
            12,
            2,
            79.00,
        ),
        (
            "MS-GAMING",
            "9312345678909",
            "Gaming Mouse",
            "RGB gaming mouse 16000 DPI",
            "mice",
            0.12,
            13,
            7,
            4,
            89.00,
        ),
        (
            "MS-ERGONOMIC",
            "9312345678910",
            "Ergonomic Mouse",
            "Vertical ergonomic mouse",
            "mice",
            0.15,
            12,
            8,
            7,
            69.00,
        ),
        (
            "WC-1080P",
            "9312345678911",
            "Webcam 1080p",
            "HD webcam with microphone",
            "webcams",
            0.18,
            10,
            8,
            5,
            89.00,
        ),
        (
            "WC-4K-PRO",
            "9312345678912",
            "Webcam 4K Pro",
            "Professional 4K webcam",
            "webcams",
            0.25,
            12,
            9,
            6,
            249.00,
        ),
        (
            "HS-WIRELESS",
            "9312345678913",
            "Wireless Headset",
            "Over-ear wireless headset",
            "headsets",
            0.35,
            20,
            18,
            10,
            179.00,
        ),
        (
            "HS-USB",
            "9312345678914",
            "USB Headset",
            "USB stereo headset",
            "headsets",
            0.28,
            18,
            16,
            8,
            59.00,
        ),
        (
            "DOCK-USB-C",
            "9312345678915",
            "USB-C Docking Station",
            "13-in-1 USB-C dock",
            "docks",
            0.45,
            20,
            10,
            3,
            199.00,
        ),
        (
            "HUB-USB-4",
            "9312345678916",
            "USB Hub 4-Port",
            "Powered USB 3.0 hub",
            "hubs",
            0.12,
            10,
            5,
            2,
            39.95,
        ),
        (
            "SSD-1TB",
            "9312345678917",
            "SSD 1TB External",
            "Portable SSD 1TB",
            "storage",
            0.08,
            10,
            6,
            1,
            149.00,
        ),
        (
            "SSD-2TB",
            "9312345678918",
            "SSD 2TB External",
            "Portable SSD 2TB",
            "storage",
            0.09,
            10,
            6,
            1,
            259.00,
        ),
        (
            "PWR-65W",
            "9312345678919",
            "65W USB-C Charger",
            "GaN USB-C charger",
            "power",
            0.18,
            8,
            6,
            3,
            79.00,
        ),
        (
            "PWR-100W",
            "9312345678920",
            "100W USB-C Charger",
            "GaN dual port charger",
            "power",
            0.25,
            9,
            7,
            4,
            119.00,
        ),
    ]

    for prod_data in products_data:
        service.create_product(*prod_data)

    # Add initial inventory
    bins = list(service.bins.values())
    for i, (sku, product) in enumerate(service.products.items()):
        if i < len(bins):
            qty = random.randint(20, 100)
            service.add_inventory(sku, bins[i % len(bins)].bin_id, qty)

    # Create pack stations
    for i in range(1, 5):
        service.create_pack_station(f"Pack Station {i}", f"Packing Area - Bay {i}")

    print("✅ Demo data loaded: 7 zones, 3 aisles, 240 bins, 20 products")


# =============================================================================
# INTERACTIVE MODE
# =============================================================================


async def interactive_mode(service: WarehouseOpsService) -> None:
    """Run interactive warehouse operations mode."""

    print("\n" + "=" * 60)
    print("🏭 WAREHOUSE OPERATIONS SYSTEM - Interactive Mode")
    print("=" * 60)

    while True:
        print("\n📋 MAIN MENU:")
        print("  1. Location Management")
        print("  2. Pick List Operations")
        print("  3. Pack Station")
        print("  4. Stock Take / Cycle Count")
        print("  5. Receiving Goods")
        print("  6. Putaway Tasks")
        print("  7. Barcode/SKU Lookup")
        print("  8. Reports")
        print("  9. Exit")

        choice = input("\nSelect option (1-9): ").strip()

        if choice == "1":
            await location_menu(service)
        elif choice == "2":
            await pick_list_menu(service)
        elif choice == "3":
            await pack_station_menu(service)
        elif choice == "4":
            await stock_take_menu(service)
        elif choice == "5":
            await receiving_menu(service)
        elif choice == "6":
            await putaway_menu(service)
        elif choice == "7":
            await lookup_menu(service)
        elif choice == "8":
            await reports_menu(service)
        elif choice == "9":
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid option")


async def location_menu(service: WarehouseOpsService) -> None:
    """Location management submenu."""
    print("\n📍 LOCATION MANAGEMENT:")
    print("  1. List all zones")
    print("  2. List aisles")
    print("  3. Search bins")
    print("  4. View bin details")
    print("  5. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        zones = service.list_zones()
        print(f"\n📊 Total Zones: {len(zones)}")
        for z in zones:
            print(f"  • {z.name} ({z.zone_type.value}) - {z.description}")

    elif choice == "2":
        for aisle in service.aisles.values():
            zone = service.zones.get(aisle.zone_id)
            print(
                f"  • Aisle {aisle.aisle_number} in {zone.name if zone else 'Unknown'}"
            )
            print(
                f"    {aisle.num_bays} bays × {aisle.levels_per_bay} levels × {aisle.bins_per_level} bins"
            )

    elif choice == "3":
        query = input("Enter location code prefix (e.g., 'A-01'): ").strip()
        matches = [
            b for b in service.bins.values() if query.lower() in b.location_code.lower()
        ]
        print(f"\n Found {len(matches)} bins:")
        for b in matches[:20]:
            print(f"  • {b.location_code} - {b.bin_type}")

    elif choice == "4":
        loc_code = input("Enter full location code: ").strip()
        for b in service.bins.values():
            if b.location_code.lower() == loc_code.lower():
                print(f"\n📦 Bin: {b.location_code}")
                print(f"   Type: {b.bin_type}")
                print(f"   Weight: {b.current_weight_kg:.1f}/{b.max_weight_kg} kg")
                print(
                    f"   Volume: {b.current_volume_cubic_m:.3f}/{b.max_volume_cubic_m} m³"
                )

                # Show inventory
                for inv in service.inventory.values():
                    if inv.bin_id == b.bin_id and inv.quantity > 0:
                        prod = service.products.get(inv.sku)
                        print(
                            f"   └─ {inv.sku}: {inv.quantity} units ({prod.name if prod else ''})"
                        )
                break
        else:
            print("❌ Bin not found")


async def pick_list_menu(service: WarehouseOpsService) -> None:
    """Pick list operations submenu."""
    print("\n📋 PICK LIST OPERATIONS:")
    print("  1. View pending pick lists")
    print("  2. Create new pick list")
    print("  3. Assign pick list")
    print("  4. Process picks")
    print("  5. Complete pick list")
    print("  6. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        pending = service.get_pending_pick_lists()
        print(f"\n📋 Pending Pick Lists: {len(pending)}")
        for pl in pending:
            print(f"  • {pl.pick_list_id} - Priority {pl.priority}")
            print(f"    Orders: {', '.join(pl.order_ids)}")
            print(f"    Items: {len(pl.items)}")

    elif choice == "2":
        order_id = input("Order ID: ").strip() or f"ORD-{random.randint(1000,9999)}"
        # Demo: pick random items
        items = []
        for sku in list(service.products.keys())[:3]:
            items.append({"sku": sku, "quantity": random.randint(1, 3)})

        pl = service.create_pick_list([order_id], items, priority=2)
        print(f"\n✅ Created pick list: {pl.pick_list_id}")
        print(f"   Items to pick: {len(pl.items)}")
        for item in pl.items:
            print(f"   • {item.sku} × {item.quantity_required} @ {item.bin_location}")

    elif choice == "3":
        pl_id = input("Pick list ID: ").strip()
        picker = input("Picker name: ").strip() or "John"
        if service.assign_pick_list(pl_id, picker):
            print(f"✅ Assigned to {picker}")
        else:
            print("❌ Could not assign")

    elif choice == "4":
        pl_id = input("Pick list ID: ").strip()
        pl = service.pick_lists.get(pl_id)
        if not pl:
            print("❌ Pick list not found")
            return

        for item in pl.items:
            if item.quantity_picked == 0:
                print(f"\n📦 Pick: {item.product_name}")
                print(f"   Location: {item.bin_location}")
                print(f"   Quantity: {item.quantity_required}")

                qty = input("   Quantity picked (Enter for all): ").strip()
                qty = int(qty) if qty else item.quantity_required

                service.record_pick(pl_id, item.item_id, qty, "Warehouse Staff")
                print(f"   ✅ Picked {qty}")

    elif choice == "5":
        pl_id = input("Pick list ID: ").strip()
        result = service.complete_pick_list(pl_id)
        if result["success"]:
            print(f"\n✅ Pick list completed")
            print(f"   Status: {result['status']}")
            print(f"   Picked: {result['total_picked']}/{result['total_required']}")
            print(f"   Completion: {result['completion_rate']:.1f}%")
        else:
            print(f"❌ {result.get('error', 'Unknown error')}")


async def pack_station_menu(service: WarehouseOpsService) -> None:
    """Pack station operations submenu."""
    print("\n📦 PACK STATION:")
    print("  1. View pack stations")
    print("  2. Create pack job")
    print("  3. Get box recommendation")
    print("  4. Complete packing")
    print("  5. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        print("\n📊 Pack Stations:")
        for station in service.pack_stations.values():
            print(f"  • {station.station_name} ({station.station_id})")
            print(f"    Location: {station.location}")
            print(f"    Operator: {station.assigned_operator or 'Unassigned'}")
            print(f"    Status: {station.status.value}")
            print(f"    Packed today: {station.orders_packed_today}")

    elif choice == "2":
        order_id = input("Order ID: ").strip() or f"ORD-{random.randint(1000,9999)}"
        station_id = input("Station ID: ").strip()

        # Demo items
        items = []
        for sku in list(service.products.keys())[:2]:
            items.append({"sku": sku, "quantity": 1})

        job = service.create_pack_job(order_id, station_id, items)
        print(f"\n✅ Created pack job: {job.pack_job_id}")

    elif choice == "3":
        items = []
        print("Enter items (empty SKU to finish):")
        while True:
            sku = input("  SKU: ").strip()
            if not sku:
                break
            qty = int(input("  Quantity: ").strip() or "1")
            items.append({"sku": sku, "quantity": qty})

        if items:
            rec = service.recommend_box_size(items)
            print(f"\n📦 Box Recommendation:")
            print(f"   Box: {rec['recommended_box']} ({rec['box_dimensions']})")
            print(f"   Total weight: {rec['total_weight_kg']} kg")
            print(f"   Materials: {', '.join(rec['packing_materials'])}")
            if rec["fragile_handling"]:
                print("   ⚠️  FRAGILE HANDLING REQUIRED")

    elif choice == "4":
        job_id = input("Pack job ID: ").strip()
        box_type = input("Box type used: ").strip() or "MEDIUM"
        weight = float(input("Total weight (kg): ").strip() or "2.0")
        materials = ["tape", "paper_fill"]

        if service.complete_packing(job_id, box_type, weight, materials):
            print("✅ Packing completed!")
        else:
            print("❌ Could not complete packing")


async def stock_take_menu(service: WarehouseOpsService) -> None:
    """Stock take operations submenu."""
    print("\n📊 STOCK TAKE / CYCLE COUNT:")
    print("  1. Create stock take")
    print("  2. Start stock take")
    print("  3. Record counts")
    print("  4. Complete stock take")
    print("  5. Apply adjustments")
    print("  6. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        name = input("Stock take name: ").strip() or "Monthly Cycle Count"
        count_type = input("Type (full/cycle/spot): ").strip() or "cycle"
        zone_ids = list(service.zones.keys())[:2]  # First 2 zones

        st = service.create_stock_take(
            name, count_type, zone_ids, datetime.now() + timedelta(days=1)
        )
        print(f"\n✅ Created: {st.stock_take_id}")
        print(f"   Zones: {len(st.zones)}")

    elif choice == "2":
        st_id = input("Stock take ID: ").strip()
        counters = input("Counter names (comma-separated): ").strip() or "Staff1,Staff2"
        counters = [c.strip() for c in counters.split(",")]

        if service.start_stock_take(st_id, counters):
            bins = service.get_bins_for_stock_take(st_id)
            print(f"\n✅ Stock take started")
            print(f"   Bins to count: {len(bins)}")
        else:
            print("❌ Could not start stock take")

    elif choice == "3":
        st_id = input("Stock take ID: ").strip()
        bins = service.get_bins_for_stock_take(st_id)

        if not bins:
            print("❌ No bins to count")
            return

        for bin_info in bins[:5]:  # Limit to 5 for demo
            print(f"\n📦 Bin: {bin_info['location_code']}")
            for item in bin_info["expected_items"]:
                print(f"   SKU: {item['sku']} - Expected: {item['expected_qty']}")
                counted = input(f"   Actual count: ").strip()
                if counted:
                    service.record_count(
                        st_id,
                        bin_info["bin_id"],
                        item["sku"],
                        item["expected_qty"],
                        int(counted),
                        "Counter1",
                    )
                    print("   ✅ Recorded")

    elif choice == "4":
        st_id = input("Stock take ID: ").strip()
        result = service.complete_stock_take(st_id)

        if result["success"]:
            print(f"\n✅ Stock take completed")
            print(f"   Status: {result['status']}")
            print(f"   Items counted: {result['total_counted']}")
            print(f"   Variances: {result['total_variances']}")
            print(f"   Variance value: ${result['variance_value_aud']:.2f}")
            print(f"   Accuracy: {result['accuracy_rate']:.1f}%")
        else:
            print(f"❌ {result.get('error', 'Unknown error')}")

    elif choice == "5":
        st_id = input("Stock take ID: ").strip()
        approved_by = input("Approved by: ").strip() or "Warehouse Manager"

        adjustments = service.apply_stock_take_adjustments(st_id, approved_by)
        print(f"\n✅ Applied {adjustments} inventory adjustments")


async def receiving_menu(service: WarehouseOpsService) -> None:
    """Receiving goods submenu."""
    print("\n📥 RECEIVING GOODS:")
    print("  1. Create receiving order")
    print("  2. Start receiving")
    print("  3. Receive items")
    print("  4. Complete receiving")
    print("  5. View pending")
    print("  6. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        po_number = input("PO Number: ").strip() or f"PO-{random.randint(1000,9999)}"
        supplier = input("Supplier name: ").strip() or "Electronics Supplier Pty Ltd"

        # Demo items
        items = []
        for sku in list(service.products.keys())[:3]:
            items.append({"sku": sku, "quantity": random.randint(20, 50)})

        order = service.create_receiving_order(
            po_number, supplier, datetime.now() + timedelta(days=2), items
        )
        print(f"\n✅ Created receiving order: {order.receiving_id}")
        print(f"   PO: {po_number}")
        print(f"   Items: {len(items)}")

    elif choice == "2":
        rcv_id = input("Receiving ID: ").strip()
        receiver = input("Receiver name: ").strip() or "Warehouse Staff"
        dock = input("Dock door: ").strip() or "Dock 1"

        if service.start_receiving(rcv_id, receiver, dock):
            print("✅ Receiving started")
        else:
            print("❌ Could not start receiving")

    elif choice == "3":
        rcv_id = input("Receiving ID: ").strip()
        order = service.receiving_orders.get(rcv_id)

        if not order:
            print("❌ Order not found")
            return

        for item in order.items:
            sku = item.get("sku")
            expected = item.get("quantity", 0)
            print(f"\n📦 {sku} - Expected: {expected}")

            qty = input("   Quantity received: ").strip()
            if qty:
                lot = input("   Lot number (optional): ").strip() or None
                result = service.receive_item(rcv_id, sku, int(qty), lot)

                if result["success"]:
                    print(f"   ✅ Received {qty}")
                    if result["variance"] != 0:
                        print(
                            f"   ⚠️  Variance: {result['variance_type']} ({result['variance']})"
                        )
                else:
                    print(f"   ❌ {result['error']}")

    elif choice == "4":
        rcv_id = input("Receiving ID: ").strip()
        result = service.complete_receiving(rcv_id)

        if result["success"]:
            print(f"\n✅ Receiving completed")
            print(f"   Status: {result['status']}")
            print(f"   Putaway tasks created: {len(result['putaway_tasks'])}")
            if result["total_variance"] != 0:
                print(f"   ⚠️  Total variance: {result['total_variance']}")
        else:
            print(f"❌ {result.get('error', 'Unknown error')}")

    elif choice == "5":
        pending = [
            o
            for o in service.receiving_orders.values()
            if o.status in ["pending", "in_progress"]
        ]
        print(f"\n📋 Pending Receiving Orders: {len(pending)}")
        for order in pending:
            print(f"  • {order.receiving_id} - PO: {order.po_number}")
            print(f"    Supplier: {order.supplier_name}")
            print(f"    Status: {order.status}")


async def putaway_menu(service: WarehouseOpsService) -> None:
    """Putaway tasks submenu."""
    print("\n📤 PUTAWAY TASKS:")
    print("  1. View pending tasks")
    print("  2. Complete putaway")
    print("  3. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        tasks = service.get_pending_putaway_tasks()
        print(f"\n📋 Pending Putaway Tasks: {len(tasks)}")
        for task in tasks:
            product = service.products.get(task.sku)
            print(f"  • {task.task_id}")
            print(f"    SKU: {task.sku} ({product.name if product else ''})")
            print(f"    Quantity: {task.quantity}")
            print(f"    Suggested bin: {task.suggested_bin}")

    elif choice == "2":
        task_id = input("Task ID: ").strip()
        actual_bin = input("Actual bin location: ").strip()
        operator = input("Operator: ").strip() or "Warehouse Staff"

        if service.complete_putaway(task_id, actual_bin, operator):
            print("✅ Putaway completed!")
        else:
            print("❌ Could not complete putaway")


async def lookup_menu(service: WarehouseOpsService) -> None:
    """Barcode/SKU lookup submenu."""
    print("\n🔍 BARCODE / SKU LOOKUP:")
    print("  1. Scan barcode")
    print("  2. Search by SKU")
    print("  3. Search by name")
    print("  4. Find inventory locations")
    print("  5. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        barcode = input("Enter barcode: ").strip()
        product = service.lookup_by_barcode(barcode)

        if product:
            print(f"\n✅ Found: {product.name}")
            print(f"   SKU: {product.sku}")
            print(f"   Category: {product.category}")
            print(f"   Weight: {product.weight_kg} kg")
            print(f"   Cost: ${product.unit_cost_aud:.2f}")

            total_stock = service.get_total_stock(product.sku)
            print(f"   Stock: {total_stock} units")
        else:
            print("❌ Product not found")

    elif choice == "2":
        sku = input("Enter SKU: ").strip()
        product = service.lookup_by_sku(sku)

        if product:
            print(f"\n✅ {product.name}")
            print(f"   Barcode: {product.barcode}")
            print(
                f"   Dimensions: {product.length_cm}×{product.width_cm}×{product.height_cm} cm"
            )

            total_stock = service.get_total_stock(product.sku)
            print(f"   Total stock: {total_stock} units")
        else:
            print("❌ Product not found")

    elif choice == "3":
        query = input("Search term: ").strip()
        results = service.search_products(query)

        print(f"\n📊 Found {len(results)} products:")
        for p in results[:10]:
            stock = service.get_total_stock(p.sku)
            print(f"  • {p.sku}: {p.name} ({stock} units)")

    elif choice == "4":
        sku = input("Enter SKU: ").strip()
        locations = service.find_inventory_locations(sku)

        if locations:
            print(f"\n📍 Inventory locations for {sku}:")
            for loc in locations:
                print(f"  • {loc['location_code']}: {loc['quantity']} units")
                if loc.get("lot_number"):
                    print(f"    Lot: {loc['lot_number']}")
        else:
            print("❌ No inventory found")


async def reports_menu(service: WarehouseOpsService) -> None:
    """Reports submenu."""
    print("\n📊 REPORTS:")
    print("  1. Warehouse summary")
    print("  2. Bin utilization")
    print("  3. Movement history")
    print("  4. Low stock report")
    print("  5. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        summary = service.get_warehouse_summary()
        print("\n📊 WAREHOUSE SUMMARY")
        print("=" * 40)
        print(f"Zones: {summary['total_zones']}")
        print(f"Aisles: {summary['total_aisles']}")
        print(f"Bins: {summary['active_bins']}/{summary['total_bins']}")
        print(f"SKUs: {summary['total_skus']}")
        print(f"Total units: {summary['total_units']:,}")
        print(f"Inventory value: ${summary['total_inventory_value_aud']:,.2f}")
        print(f"Low stock items: {summary['low_stock_count']}")
        print(f"Pending pick lists: {summary['pending_pick_lists']}")
        print(f"Pending putaway: {summary['pending_putaway']}")

    elif choice == "2":
        report = service.get_bin_utilization_report()
        print("\n📊 BIN UTILIZATION BY ZONE")
        print("=" * 40)
        for zone in report:
            bar = "█" * int(zone["utilization_pct"] / 5) + "░" * (
                20 - int(zone["utilization_pct"] / 5)
            )
            print(
                f"{zone['zone_name'][:20]:<20} [{bar}] {zone['utilization_pct']:.1f}%"
            )

    elif choice == "3":
        sku = input("SKU (or Enter for all): ").strip() or None
        days = int(input("Days (default 7): ").strip() or "7")

        movements = service.get_movement_history(sku, days)
        print(f"\n📊 Last {days} days - {len(movements)} movements")
        print("=" * 60)
        for m in movements[:20]:
            print(
                f"{m.timestamp.strftime('%Y-%m-%d %H:%M')} | {m.movement_type.value:10} | {m.sku} × {m.quantity}"
            )

    elif choice == "4":
        summary = service.get_warehouse_summary()
        print("\n⚠️  LOW STOCK ITEMS")
        print("=" * 50)
        if summary["low_stock_skus"]:
            for item in summary["low_stock_skus"]:
                print(
                    f"  • {item['sku']}: {item['current']}/{item['minimum']} ({item['name']})"
                )
        else:
            print("  ✅ All items above minimum stock levels")


# =============================================================================
# DEMO MODE
# =============================================================================


async def demo_mode(service: WarehouseOpsService) -> None:
    """Run automated demo."""
    print("\n" + "=" * 60)
    print("🏭 WAREHOUSE OPERATIONS DEMO")
    print("=" * 60)

    # 1. Show warehouse summary
    print("\n📊 1. WAREHOUSE OVERVIEW")
    print("-" * 40)
    summary = service.get_warehouse_summary()
    print(f"   Zones: {summary['total_zones']}")
    print(f"   Bins: {summary['total_bins']}")
    print(f"   SKUs: {summary['total_skus']}")
    print(f"   Inventory value: ${summary['total_inventory_value_aud']:,.2f}")
    await asyncio.sleep(1)

    # 2. Barcode lookup demo
    print("\n🔍 2. BARCODE LOOKUP DEMO")
    print("-" * 40)
    barcode = "9312345678907"  # Keyboard
    product = service.lookup_by_barcode(barcode)
    if product:
        print(f"   Scanned: {barcode}")
        print(f"   Product: {product.name}")
        print(f"   SKU: {product.sku}")
        print(f"   Stock: {service.get_total_stock(product.sku)} units")
    await asyncio.sleep(1)

    # 3. Create and process pick list
    print("\n📋 3. PICK LIST WORKFLOW")
    print("-" * 40)

    # Create order items
    order_items = [
        {"sku": "MON-27-4K", "quantity": 2},
        {"sku": "CBL-HDMI-2M", "quantity": 3},
        {"sku": "KB-MECH-RGB", "quantity": 1},
    ]

    pick_list = service.create_pick_list(["ORD-DEMO-001"], order_items, priority=1)
    print(f"   Created pick list: {pick_list.pick_list_id}")
    print(f"   Items to pick: {len(pick_list.items)}")

    # Assign picker
    service.assign_pick_list(pick_list.pick_list_id, "Demo Picker")
    print("   Assigned to: Demo Picker")

    # Process picks
    for item in pick_list.items:
        print(
            f"   → Picking {item.sku} × {item.quantity_required} from {item.bin_location}"
        )
        service.record_pick(
            pick_list.pick_list_id, item.item_id, item.quantity_required, "Demo Picker"
        )

    # Complete
    result = service.complete_pick_list(pick_list.pick_list_id)
    print(f"   ✅ Pick list completed: {result['completion_rate']:.0f}%")
    await asyncio.sleep(1)

    # 4. Pack station demo
    print("\n📦 4. PACKING WORKFLOW")
    print("-" * 40)

    station = list(service.pack_stations.values())[0]
    pack_job = service.create_pack_job("ORD-DEMO-001", station.station_id, order_items)
    print(f"   Pack job: {pack_job.pack_job_id}")
    print(f"   Station: {station.station_name}")

    # Get box recommendation
    rec = service.recommend_box_size(order_items)
    print(f"   Recommended box: {rec['recommended_box']} ({rec['box_dimensions']})")
    print(f"   Total weight: {rec['total_weight_kg']} kg")
    print(f"   Materials: {', '.join(rec['packing_materials'])}")

    # Complete packing
    service.start_packing(pack_job.pack_job_id, "Demo Packer")
    service.complete_packing(
        pack_job.pack_job_id,
        rec["recommended_box"],
        rec["total_weight_kg"],
        rec["packing_materials"],
    )
    print("   ✅ Packing completed!")
    await asyncio.sleep(1)

    # 5. Receiving demo
    print("\n📥 5. RECEIVING WORKFLOW")
    print("-" * 40)

    receiving = service.create_receiving_order(
        "PO-DEMO-001",
        "Tech Supplies Australia",
        datetime.now(),
        [{"sku": "SSD-1TB", "quantity": 50}, {"sku": "PWR-65W", "quantity": 30}],
    )
    print(f"   Receiving order: {receiving.receiving_id}")
    print(f"   PO: {receiving.po_number}")

    service.start_receiving(receiving.receiving_id, "Demo Receiver", "Dock 1")

    # Receive items
    for item in receiving.items:
        result = service.receive_item(
            receiving.receiving_id,
            item["sku"],
            item["quantity"],
            f"LOT-{random.randint(1000,9999)}",
        )
        print(f"   → Received {item['sku']} × {result['received']}")

    result = service.complete_receiving(receiving.receiving_id)
    print(
        f"   ✅ Receiving completed - {len(result['putaway_tasks'])} putaway tasks created"
    )
    await asyncio.sleep(1)

    # 6. Putaway demo
    print("\n📤 6. PUTAWAY WORKFLOW")
    print("-" * 40)

    putaway_tasks = service.get_pending_putaway_tasks()
    for task in putaway_tasks[:2]:
        print(f"   Task: {task.task_id}")
        print(f"   → {task.sku} × {task.quantity} → {task.suggested_bin}")
        service.complete_putaway(task.task_id, task.suggested_bin, "Demo Staff")
        print("   ✅ Putaway completed")
    await asyncio.sleep(1)

    # 7. Stock take demo
    print("\n📊 7. CYCLE COUNT DEMO")
    print("-" * 40)

    zone_ids = list(service.zones.keys())[:1]
    stock_take = service.create_stock_take(
        "Demo Cycle Count", "cycle", zone_ids, datetime.now()
    )
    print(f"   Stock take: {stock_take.stock_take_id}")

    service.start_stock_take(stock_take.stock_take_id, ["Demo Counter"])

    bins = service.get_bins_for_stock_take(stock_take.stock_take_id)
    counted = 0
    for bin_info in bins[:5]:
        for item in bin_info["expected_items"]:
            # Simulate counting (with occasional variance)
            variance = random.choice([0, 0, 0, 1, -1])
            counted_qty = item["expected_qty"] + variance

            service.record_count(
                stock_take.stock_take_id,
                bin_info["bin_id"],
                item["sku"],
                item["expected_qty"],
                counted_qty,
                "Demo Counter",
            )
            counted += 1

    print(f"   Counted {counted} items")

    result = service.complete_stock_take(stock_take.stock_take_id)
    print(f"   ✅ Stock take completed")
    print(f"      Accuracy: {result['accuracy_rate']:.1f}%")
    print(f"      Variances: {result['total_variances']}")
    await asyncio.sleep(1)

    # 8. Movement history
    print("\n📋 8. MOVEMENT HISTORY (Last 7 days)")
    print("-" * 40)
    movements = service.get_movement_history(days=7)
    print(f"   Total movements: {len(movements)}")

    by_type = {}
    for m in movements:
        by_type[m.movement_type.value] = by_type.get(m.movement_type.value, 0) + 1

    for mov_type, count in sorted(by_type.items()):
        print(f"   • {mov_type}: {count}")

    # Final summary
    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETED")
    print("=" * 60)
    final_summary = service.get_warehouse_summary()
    print(f"   Total units in warehouse: {final_summary['total_units']:,}")
    print(f"   Inventory value: ${final_summary['total_inventory_value_aud']:,.2f}")
    print(f"   Low stock alerts: {final_summary['low_stock_count']}")


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WooCommerce Warehouse Operations System"
    )
    parser.add_argument("--demo", action="store_true", help="Run automated demo")
    parser.add_argument(
        "--interactive", action="store_true", help="Run interactive mode"
    )

    args = parser.parse_args()

    # Initialize service
    service = WarehouseOpsService()
    setup_demo_data(service)

    if args.demo:
        asyncio.run(demo_mode(service))
    elif args.interactive:
        asyncio.run(interactive_mode(service))
    else:
        # Default to demo
        print("Usage: python 71_woo_warehouse_ops.py --demo OR --interactive")
        print("\nRunning demo mode by default...\n")
        asyncio.run(demo_mode(service))


if __name__ == "__main__":
    main()
