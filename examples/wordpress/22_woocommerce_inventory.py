#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 22: WooCommerce Inventory Management Assistant

A chatbot for warehouse staff and inventory managers to track stock levels,
manage reorders, and handle inventory operations.

Use Cases:
- Real-time stock level queries
- Low stock alerts and reorder suggestions
- Stock receiving and adjustments
- Inventory reports and analytics
- Supplier management

Requirements:
- WooCommerce 3.5+ with REST API enabled
- Consumer Key/Secret with read/write access
- HTTPS enabled on the store
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class StockStatus(Enum):
    """Stock status levels."""

    IN_STOCK = "instock"
    LOW_STOCK = "lowstock"
    OUT_OF_STOCK = "outofstock"
    ON_BACKORDER = "onbackorder"


# Demo inventory data - Office supplies store
DEMO_PRODUCTS = [
    {
        "id": 101,
        "name": "Ergonomic Keyboard Pro",
        "sku": "KB-ERGO1",
        "price": "89.99",
        "stock_quantity": 45,
        "stock_status": "instock",
        "low_stock_threshold": 20,
        "categories": [{"name": "Keyboards"}],
        "weight": "0.8",
        "dimensions": {"length": "45", "width": "15", "height": "5"},
        "manage_stock": True,
        "backorders": "no",
        "supplier": "TechSupply Co",
        "supplier_sku": "TS-KB-001",
        "reorder_point": 20,
        "reorder_quantity": 50,
        "lead_time_days": 5,
        "last_restock": "2024-03-01",
        "location": "A-1-3",
    },
    {
        "id": 102,
        "name": "Wireless Mouse 500",
        "sku": "MS-WL500",
        "price": "49.99",
        "stock_quantity": 120,
        "stock_status": "instock",
        "low_stock_threshold": 30,
        "categories": [{"name": "Mice"}],
        "weight": "0.15",
        "dimensions": {"length": "12", "width": "7", "height": "4"},
        "manage_stock": True,
        "backorders": "no",
        "supplier": "TechSupply Co",
        "supplier_sku": "TS-MS-002",
        "reorder_point": 30,
        "reorder_quantity": 100,
        "lead_time_days": 3,
        "last_restock": "2024-03-10",
        "location": "A-2-1",
    },
    {
        "id": 103,
        "name": "27-inch HD Monitor",
        "sku": "MON-27HD",
        "price": "399.99",
        "stock_quantity": 8,
        "stock_status": "lowstock",
        "low_stock_threshold": 10,
        "categories": [{"name": "Monitors"}],
        "weight": "5.5",
        "dimensions": {"length": "65", "width": "45", "height": "20"},
        "manage_stock": True,
        "backorders": "notify",
        "supplier": "DisplayTech",
        "supplier_sku": "DT-MON-27",
        "reorder_point": 10,
        "reorder_quantity": 20,
        "lead_time_days": 7,
        "last_restock": "2024-02-15",
        "location": "B-1-1",
    },
    {
        "id": 104,
        "name": "USB Hub 4-Port",
        "sku": "USB-HUB4",
        "price": "29.99",
        "stock_quantity": 5,
        "stock_status": "lowstock",
        "low_stock_threshold": 15,
        "categories": [{"name": "Accessories"}],
        "weight": "0.1",
        "dimensions": {"length": "10", "width": "5", "height": "2"},
        "manage_stock": True,
        "backorders": "no",
        "supplier": "TechSupply Co",
        "supplier_sku": "TS-USB-004",
        "reorder_point": 15,
        "reorder_quantity": 50,
        "lead_time_days": 3,
        "last_restock": "2024-02-28",
        "location": "A-3-2",
    },
    {
        "id": 105,
        "name": "HDMI Cable 2m",
        "sku": "CBL-HDMI2",
        "price": "14.99",
        "stock_quantity": 200,
        "stock_status": "instock",
        "low_stock_threshold": 50,
        "categories": [{"name": "Cables"}],
        "weight": "0.15",
        "dimensions": {"length": "25", "width": "5", "height": "3"},
        "manage_stock": True,
        "backorders": "no",
        "supplier": "CablePro",
        "supplier_sku": "CP-HDMI-2M",
        "reorder_point": 50,
        "reorder_quantity": 200,
        "lead_time_days": 2,
        "last_restock": "2024-03-05",
        "location": "C-1-1",
    },
    {
        "id": 106,
        "name": "Laptop Stand Adjustable",
        "sku": "STD-LAP1",
        "price": "59.99",
        "stock_quantity": 0,
        "stock_status": "outofstock",
        "low_stock_threshold": 10,
        "categories": [{"name": "Stands"}],
        "weight": "1.2",
        "dimensions": {"length": "30", "width": "25", "height": "5"},
        "manage_stock": True,
        "backorders": "notify",
        "supplier": "OfficePro",
        "supplier_sku": "OP-STD-001",
        "reorder_point": 10,
        "reorder_quantity": 30,
        "lead_time_days": 10,
        "last_restock": "2024-01-20",
        "location": "B-2-3",
        "backorder_date": "2024-03-25",
        "backorder_quantity": 30,
    },
    {
        "id": 107,
        "name": "Webcam HD 1080p",
        "sku": "CAM-HD1080",
        "price": "79.99",
        "stock_quantity": 25,
        "stock_status": "instock",
        "low_stock_threshold": 15,
        "categories": [{"name": "Cameras"}],
        "weight": "0.2",
        "dimensions": {"length": "10", "width": "8", "height": "5"},
        "manage_stock": True,
        "backorders": "no",
        "supplier": "TechSupply Co",
        "supplier_sku": "TS-CAM-001",
        "reorder_point": 15,
        "reorder_quantity": 40,
        "lead_time_days": 5,
        "last_restock": "2024-03-08",
        "location": "A-4-1",
    },
]

DEMO_SUPPLIERS = [
    {
        "id": 1,
        "name": "TechSupply Co",
        "contact": "orders@techsupply.com",
        "phone": "+61 2 9000 1234",
        "lead_time": 3,
        "products": ["KB-ERGO1", "MS-WL500", "USB-HUB4", "CAM-HD1080"],
    },
    {
        "id": 2,
        "name": "DisplayTech",
        "contact": "sales@displaytech.com",
        "phone": "+61 3 9000 5678",
        "lead_time": 7,
        "products": ["MON-27HD"],
    },
    {
        "id": 3,
        "name": "CablePro",
        "contact": "orders@cablepro.com",
        "phone": "+61 2 9000 9999",
        "lead_time": 2,
        "products": ["CBL-HDMI2"],
    },
    {
        "id": 4,
        "name": "OfficePro",
        "contact": "supply@officepro.com",
        "phone": "+61 7 9000 4321",
        "lead_time": 10,
        "products": ["STD-LAP1"],
    },
]

DEMO_STOCK_MOVEMENTS = [
    {
        "date": "2024-03-15",
        "sku": "KB-ERGO1",
        "type": "sale",
        "quantity": -2,
        "note": "Order #1001",
    },
    {
        "date": "2024-03-15",
        "sku": "MS-WL500",
        "type": "sale",
        "quantity": -1,
        "note": "Order #1001",
    },
    {
        "date": "2024-03-14",
        "sku": "MON-27HD",
        "type": "sale",
        "quantity": -1,
        "note": "Order #1002",
    },
    {
        "date": "2024-03-14",
        "sku": "CBL-HDMI2",
        "type": "sale",
        "quantity": -2,
        "note": "Order #1002",
    },
    {
        "date": "2024-03-13",
        "sku": "USB-HUB4",
        "type": "sale",
        "quantity": -3,
        "note": "Order #1000",
    },
    {
        "date": "2024-03-10",
        "sku": "MS-WL500",
        "type": "received",
        "quantity": 50,
        "note": "PO-2024-015",
    },
    {
        "date": "2024-03-08",
        "sku": "CAM-HD1080",
        "type": "received",
        "quantity": 30,
        "note": "PO-2024-014",
    },
]


@dataclass
class Product:
    """Product with inventory details."""

    id: int
    name: str
    sku: str
    price: str
    stock_quantity: int
    stock_status: str
    low_stock_threshold: int
    location: str
    supplier: str
    reorder_point: int
    reorder_quantity: int
    lead_time_days: int

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            id=data["id"],
            name=data["name"],
            sku=data["sku"],
            price=data["price"],
            stock_quantity=data.get("stock_quantity", 0),
            stock_status=data.get("stock_status", "instock"),
            low_stock_threshold=data.get("low_stock_threshold", 10),
            location=data.get("location", "Unknown"),
            supplier=data.get("supplier", "Unknown"),
            reorder_point=data.get("reorder_point", 10),
            reorder_quantity=data.get("reorder_quantity", 50),
            lead_time_days=data.get("lead_time_days", 7),
        )

    @property
    def needs_reorder(self) -> bool:
        """Check if product needs reordering."""
        return self.stock_quantity <= self.reorder_point

    @property
    def days_of_stock(self) -> int:
        """Estimate days of stock remaining based on recent sales."""
        # Simplified: assume 2 units sold per day on average
        daily_sales = 2
        if daily_sales == 0:
            return 999
        return self.stock_quantity // daily_sales


class InventoryClient:
    """Client for inventory operations."""

    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self._products = {p["sku"]: p for p in DEMO_PRODUCTS}

    async def get_all_products(self) -> list[Product]:
        """Get all products with inventory data."""
        return [Product.from_dict(p) for p in DEMO_PRODUCTS]

    async def get_product_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        if sku.upper() in self._products:
            return Product.from_dict(self._products[sku.upper()])
        # Try partial match
        for key, product in self._products.items():
            if sku.upper() in key:
                return Product.from_dict(product)
        return None

    async def get_low_stock_products(self) -> list[Product]:
        """Get products below reorder point."""
        return [
            Product.from_dict(p)
            for p in DEMO_PRODUCTS
            if p["stock_quantity"] <= p.get("reorder_point", 10)
        ]

    async def get_out_of_stock_products(self) -> list[Product]:
        """Get products with zero stock."""
        return [Product.from_dict(p) for p in DEMO_PRODUCTS if p["stock_quantity"] == 0]

    async def get_products_by_location(self, location: str) -> list[Product]:
        """Get products in a specific location."""
        location_upper = location.upper()
        return [
            Product.from_dict(p)
            for p in DEMO_PRODUCTS
            if location_upper in p.get("location", "").upper()
        ]

    async def get_products_by_supplier(self, supplier: str) -> list[Product]:
        """Get products from a specific supplier."""
        supplier_lower = supplier.lower()
        return [
            Product.from_dict(p)
            for p in DEMO_PRODUCTS
            if supplier_lower in p.get("supplier", "").lower()
        ]

    async def adjust_stock(self, sku: str, adjustment: int, reason: str) -> dict:
        """Adjust stock level for a product."""
        if self.demo_mode:
            product = self._products.get(sku.upper())
            if not product:
                return {"success": False, "error": f"Product {sku} not found"}

            old_qty = product["stock_quantity"]
            new_qty = max(0, old_qty + adjustment)

            return {
                "success": True,
                "sku": sku,
                "old_quantity": old_qty,
                "new_quantity": new_qty,
                "adjustment": adjustment,
                "reason": reason,
                "message": f"Stock adjusted: {old_qty} → {new_qty} ({'+' if adjustment > 0 else ''}{adjustment})",
            }
        return {"success": False, "error": "Not implemented"}

    async def receive_stock(self, sku: str, quantity: int, po_number: str) -> dict:
        """Receive stock from supplier."""
        if self.demo_mode:
            product = self._products.get(sku.upper())
            if not product:
                return {"success": False, "error": f"Product {sku} not found"}

            old_qty = product["stock_quantity"]
            new_qty = old_qty + quantity

            return {
                "success": True,
                "sku": sku,
                "product_name": product["name"],
                "received": quantity,
                "old_quantity": old_qty,
                "new_quantity": new_qty,
                "po_number": po_number,
                "location": product.get("location", "Unknown"),
                "message": f"Received {quantity} units of {product['name']}. Stock: {old_qty} → {new_qty}",
            }
        return {"success": False, "error": "Not implemented"}

    async def create_reorder(self, sku: str) -> dict:
        """Create a reorder for a product."""
        if self.demo_mode:
            product = self._products.get(sku.upper())
            if not product:
                return {"success": False, "error": f"Product {sku} not found"}

            po_number = f"PO-2024-{datetime.now().strftime('%j%H%M')}"

            return {
                "success": True,
                "po_number": po_number,
                "sku": sku,
                "product_name": product["name"],
                "quantity": product.get("reorder_quantity", 50),
                "supplier": product.get("supplier", "Unknown"),
                "supplier_sku": product.get("supplier_sku", ""),
                "lead_time_days": product.get("lead_time_days", 7),
                "expected_date": (
                    datetime.now() + timedelta(days=product.get("lead_time_days", 7))
                ).strftime("%Y-%m-%d"),
                "message": f"Purchase order {po_number} created for {product.get('reorder_quantity', 50)} units",
            }
        return {"success": False, "error": "Not implemented"}

    async def get_stock_movements(self, sku: str = None, days: int = 7) -> list[dict]:
        """Get recent stock movements."""
        movements = DEMO_STOCK_MOVEMENTS
        if sku:
            movements = [m for m in movements if m["sku"].upper() == sku.upper()]
        return movements

    async def get_suppliers(self) -> list[dict]:
        """Get all suppliers."""
        return DEMO_SUPPLIERS

    async def get_inventory_value(self) -> dict:
        """Calculate total inventory value."""
        total_value = 0
        total_units = 0

        for p in DEMO_PRODUCTS:
            qty = p.get("stock_quantity", 0)
            price = float(p.get("price", 0))
            total_value += qty * price
            total_units += qty

        return {
            "total_value": round(total_value, 2),
            "total_units": total_units,
            "product_count": len(DEMO_PRODUCTS),
        }


class InventoryAssistant:
    """
    AI assistant for WooCommerce inventory management.

    Capabilities:
    - Stock level queries
    - Low stock alerts
    - Stock receiving
    - Reorder management
    - Inventory reports
    """

    def __init__(self, demo_mode: bool = True):
        self.client = InventoryClient(demo_mode=demo_mode)
        self.conversation_history: list[dict] = []

    async def process_message(self, user_message: str) -> str:
        """Process an inventory message and return a response."""
        message_lower = user_message.lower()

        # Store in history
        self.conversation_history.append(
            {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Route to appropriate handler
        if any(
            word in message_lower
            for word in ["low stock", "reorder", "running low", "need to order"]
        ):
            response = await self._handle_low_stock()
        elif any(
            word in message_lower for word in ["out of stock", "no stock", "zero stock"]
        ):
            response = await self._handle_out_of_stock()
        elif any(
            word in message_lower
            for word in ["stock level", "how many", "quantity", "check stock"]
        ):
            response = await self._handle_stock_check(user_message)
        elif any(
            word in message_lower
            for word in ["receive", "received", "delivery", "shipment"]
        ):
            response = await self._handle_receive_stock(user_message)
        elif any(
            word in message_lower for word in ["adjust", "correction", "count", "cycle"]
        ):
            response = await self._handle_stock_adjustment(user_message)
        elif any(
            word in message_lower for word in ["location", "where", "find", "aisle"]
        ):
            response = await self._handle_location_query(user_message)
        elif any(word in message_lower for word in ["supplier", "vendor"]):
            response = await self._handle_supplier_query(user_message)
        elif any(
            word in message_lower for word in ["report", "summary", "value", "total"]
        ):
            response = await self._handle_inventory_report()
        elif any(word in message_lower for word in ["movement", "history", "activity"]):
            response = await self._handle_movement_history(user_message)
        elif any(
            word in message_lower for word in ["order", "purchase", "po", "reorder"]
        ):
            response = await self._handle_create_order(user_message)
        elif any(word in message_lower for word in ["help", "what can"]):
            response = self._get_help()
        else:
            response = await self._handle_general(user_message)

        # Store response
        self.conversation_history.append(
            {
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return response

    async def _handle_low_stock(self) -> str:
        """Handle low stock queries."""
        low_stock = await self.client.get_low_stock_products()

        if not low_stock:
            return "✅ Great news! All products are above their reorder points. No action needed."

        lines = ["⚠️ **Low Stock Alert**\n"]

        for product in sorted(low_stock, key=lambda p: p.stock_quantity):
            status_emoji = "🔴" if product.stock_quantity == 0 else "🟡"
            lines.append(f"{status_emoji} **{product.name}** ({product.sku})")
            lines.append(
                f"   Stock: {product.stock_quantity} | Reorder Point: {product.reorder_point}"
            )
            lines.append(
                f"   Location: {product.location} | Supplier: {product.supplier}"
            )
            if product.needs_reorder:
                lines.append(
                    f"   📦 Suggested reorder: {product.reorder_quantity} units"
                )
            lines.append("")

        lines.append(f"**Total items needing attention:** {len(low_stock)}")
        lines.append("\nSay 'create order for [SKU]' to generate a purchase order.")

        return "\n".join(lines)

    async def _handle_out_of_stock(self) -> str:
        """Handle out of stock queries."""
        out_of_stock = await self.client.get_out_of_stock_products()

        if not out_of_stock:
            return "✅ No products are currently out of stock!"

        lines = ["🔴 **Out of Stock Products**\n"]

        for product in out_of_stock:
            lines.append(f"❌ **{product.name}** ({product.sku})")
            lines.append(f"   Supplier: {product.supplier}")
            lines.append(f"   Lead Time: {product.lead_time_days} days")
            lines.append(f"   📦 Reorder quantity: {product.reorder_quantity} units")
            lines.append("")

        lines.append(
            "⚡ **Action Required:** Create purchase orders for these items immediately!"
        )
        return "\n".join(lines)

    async def _handle_stock_check(self, message: str) -> str:
        """Handle stock level queries."""
        # Try to extract SKU or product name
        words = message.upper().split()

        for word in words:
            if "-" in word or (len(word) >= 3 and word.isalnum()):
                product = await self.client.get_product_by_sku(word)
                if product:
                    return self._format_stock_details(product)

        # Show all stock levels
        products = await self.client.get_all_products()

        lines = ["📦 **Current Stock Levels**\n"]
        for product in sorted(products, key=lambda p: p.stock_quantity):
            if product.stock_quantity == 0:
                emoji = "🔴"
            elif product.stock_quantity <= product.reorder_point:
                emoji = "🟡"
            else:
                emoji = "🟢"

            lines.append(
                f"{emoji} {product.sku}: {product.stock_quantity} units - {product.name}"
            )

        lines.append("\nSay 'check stock [SKU]' for detailed product info.")
        return "\n".join(lines)

    def _format_stock_details(self, product: Product) -> str:
        """Format detailed stock information."""
        if product.stock_quantity == 0:
            status = "🔴 OUT OF STOCK"
        elif product.stock_quantity <= product.reorder_point:
            status = "🟡 LOW STOCK"
        else:
            status = "🟢 IN STOCK"

        lines = [
            f"📦 **{product.name}**",
            f"SKU: {product.sku}",
            "",
            f"**Status:** {status}",
            f"**Quantity:** {product.stock_quantity} units",
            f"**Location:** {product.location}",
            "",
            f"**Reorder Point:** {product.reorder_point}",
            f"**Reorder Quantity:** {product.reorder_quantity}",
            f"**Supplier:** {product.supplier}",
            f"**Lead Time:** {product.lead_time_days} days",
        ]

        if product.needs_reorder:
            lines.extend(
                [
                    "",
                    "⚠️ **Needs Reorder!**",
                    f"Say 'create order for {product.sku}' to generate PO",
                ]
            )

        return "\n".join(lines)

    async def _handle_receive_stock(self, message: str) -> str:
        """Handle stock receiving."""
        import re

        # Try to extract SKU and quantity
        sku_match = re.search(r"([A-Z]{2,}-[A-Z0-9]+)", message.upper())
        qty_match = re.search(r"(\d+)\s*(units?|pcs?|pieces?)?", message.lower())
        po_match = re.search(r"(PO-?\d+[-\d]*)", message.upper())

        if not sku_match:
            return """📥 **Receive Stock**

To receive stock, please provide:
- **SKU** (e.g., KB-ERGO1)
- **Quantity** received
- **PO Number** (optional)

Example: "Receive 50 units of KB-ERGO1 from PO-2024-015" """

        sku = sku_match.group(1)
        quantity = int(qty_match.group(1)) if qty_match else 1
        po_number = (
            po_match.group(1) if po_match else f"PO-{datetime.now().strftime('%Y%m%d')}"
        )

        result = await self.client.receive_stock(sku, quantity, po_number)

        if result["success"]:
            return f"""✅ **Stock Received**

**Product:** {result['product_name']}
**SKU:** {result['sku']}
**Quantity Received:** {result['received']} units
**PO Number:** {result['po_number']}
**Location:** {result['location']}

📊 Stock Updated: {result['old_quantity']} → {result['new_quantity']}

Put away at location **{result['location']}**."""
        else:
            return f"❌ Error: {result['error']}"

    async def _handle_stock_adjustment(self, message: str) -> str:
        """Handle stock adjustments."""
        import re

        sku_match = re.search(r"([A-Z]{2,}-[A-Z0-9]+)", message.upper())

        if not sku_match:
            return """🔧 **Stock Adjustment**

To adjust stock (cycle count, damage, etc.), provide:
- **SKU** of the product
- **Adjustment** (+/- quantity)
- **Reason** for adjustment

Example: "Adjust KB-ERGO1 by -2 units, damaged in warehouse" """

        # Extract adjustment amount
        adj_match = re.search(r"([+-]?\d+)", message)
        adjustment = int(adj_match.group(1)) if adj_match else 0

        if adjustment == 0:
            return "Please specify the adjustment amount (e.g., +5 or -3 units)"

        sku = sku_match.group(1)
        reason = "Stock adjustment"
        if "damage" in message.lower():
            reason = "Damaged goods"
        elif "count" in message.lower() or "cycle" in message.lower():
            reason = "Cycle count correction"
        elif "return" in message.lower():
            reason = "Customer return"

        result = await self.client.adjust_stock(sku, adjustment, reason)

        if result["success"]:
            return f"""✅ **Stock Adjusted**

**SKU:** {result['sku']}
**Adjustment:** {'+' if adjustment > 0 else ''}{adjustment} units
**Reason:** {reason}

📊 Stock: {result['old_quantity']} → {result['new_quantity']}"""
        else:
            return f"❌ Error: {result['error']}"

    async def _handle_location_query(self, message: str) -> str:
        """Handle location queries."""
        import re

        # Check for specific SKU
        sku_match = re.search(r"([A-Z]{2,}-[A-Z0-9]+)", message.upper())

        if sku_match:
            product = await self.client.get_product_by_sku(sku_match.group(1))
            if product:
                return f"""📍 **Location for {product.name}**

**SKU:** {product.sku}
**Location:** {product.location}
**Stock:** {product.stock_quantity} units

Location format: Aisle-Rack-Shelf"""

        # Check for location search
        loc_match = re.search(r"([A-C])-?\d", message.upper())

        if loc_match:
            location = loc_match.group(0)
            products = await self.client.get_products_by_location(location)

            if products:
                lines = [f"📍 **Products in Location {location}**\n"]
                for p in products:
                    lines.append(f"  • {p.sku}: {p.name} ({p.stock_quantity} units)")
                return "\n".join(lines)

        # Show all locations
        products = await self.client.get_all_products()
        locations = {}
        for p in products:
            loc = p.location.split("-")[0] if "-" in p.location else p.location
            if loc not in locations:
                locations[loc] = []
            locations[loc].append(p)

        lines = ["📍 **Warehouse Locations**\n"]
        for loc in sorted(locations.keys()):
            lines.append(f"**Aisle {loc}:** {len(locations[loc])} products")

        lines.append("\nSay 'where is [SKU]' or 'show aisle A' for details.")
        return "\n".join(lines)

    async def _handle_supplier_query(self, message: str) -> str:
        """Handle supplier queries."""
        suppliers = await self.client.get_suppliers()

        lines = ["📋 **Suppliers**\n"]
        for supplier in suppliers:
            lines.append(f"**{supplier['name']}**")
            lines.append(f"  📧 {supplier['contact']}")
            lines.append(f"  📞 {supplier['phone']}")
            lines.append(f"  ⏱️ Lead time: {supplier['lead_time']} days")
            lines.append(f"  Products: {len(supplier['products'])}")
            lines.append("")

        return "\n".join(lines)

    async def _handle_inventory_report(self) -> str:
        """Generate inventory summary report."""
        products = await self.client.get_all_products()
        inventory_value = await self.client.get_inventory_value()
        low_stock = await self.client.get_low_stock_products()
        out_of_stock = await self.client.get_out_of_stock_products()

        lines = [
            "📊 **Inventory Summary Report**",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "**Overview:**",
            f"  • Total Products: {inventory_value['product_count']}",
            f"  • Total Units: {inventory_value['total_units']:,}",
            f"  • Inventory Value: ${inventory_value['total_value']:,.2f}",
            "",
            "**Stock Status:**",
            f"  🟢 In Stock: {len(products) - len(low_stock)} products",
            f"  🟡 Low Stock: {len(low_stock) - len(out_of_stock)} products",
            f"  🔴 Out of Stock: {len(out_of_stock)} products",
            "",
        ]

        if low_stock:
            lines.append("**⚠️ Needs Attention:**")
            for p in low_stock[:5]:
                lines.append(
                    f"  • {p.sku}: {p.stock_quantity} units (reorder at {p.reorder_point})"
                )

        return "\n".join(lines)

    async def _handle_movement_history(self, message: str) -> str:
        """Handle stock movement history queries."""
        import re

        sku_match = re.search(r"([A-Z]{2,}-[A-Z0-9]+)", message.upper())
        sku = sku_match.group(1) if sku_match else None

        movements = await self.client.get_stock_movements(sku=sku)

        if not movements:
            return "No stock movements found for the specified period."

        title = f"Stock Movement History for {sku}" if sku else "Recent Stock Movements"
        lines = [f"📜 **{title}**\n"]

        for m in movements:
            emoji = "📥" if m["type"] == "received" else "📤"
            sign = "+" if m["quantity"] > 0 else ""
            lines.append(
                f"{emoji} {m['date']} | {m['sku']}: {sign}{m['quantity']} ({m['note']})"
            )

        return "\n".join(lines)

    async def _handle_create_order(self, message: str) -> str:
        """Handle purchase order creation."""
        import re

        sku_match = re.search(r"([A-Z]{2,}-[A-Z0-9]+)", message.upper())

        if not sku_match:
            # Show items that need ordering
            low_stock = await self.client.get_low_stock_products()

            if not low_stock:
                return "✅ No products need reordering at this time."

            lines = ["📋 **Products Ready for Reorder**\n"]
            for p in low_stock:
                lines.append(f"  • {p.sku}: {p.name} (Stock: {p.stock_quantity})")

            lines.append("\nSay 'create order for [SKU]' to generate a purchase order.")
            return "\n".join(lines)

        sku = sku_match.group(1)
        result = await self.client.create_reorder(sku)

        if result["success"]:
            return f"""✅ **Purchase Order Created**

**PO Number:** {result['po_number']}
**Product:** {result['product_name']}
**SKU:** {result['sku']}
**Quantity:** {result['quantity']} units
**Supplier:** {result['supplier']}
**Supplier SKU:** {result['supplier_sku']}

📅 **Expected Delivery:** {result['expected_date']}
⏱️ **Lead Time:** {result['lead_time_days']} days

Email sent to supplier for confirmation."""
        else:
            return f"❌ Error: {result['error']}"

    async def _handle_general(self, message: str) -> str:
        """Handle general queries."""
        return f"""I can help with inventory management! Here are some things you can ask:

{self._get_help()}"""

    def _get_help(self) -> str:
        """Return help text."""
        return """📦 **Inventory Assistant Commands**

**Stock Queries:**
- "Show low stock" - Products needing reorder
- "Check stock KB-ERGO1" - Specific product level
- "What's out of stock?" - Zero inventory items

**Receiving:**
- "Receive 50 units of KB-ERGO1" - Log incoming stock

**Adjustments:**
- "Adjust MS-WL500 by -2, damaged" - Stock corrections

**Locations:**
- "Where is KB-ERGO1?" - Find product location
- "Show aisle A" - Products by location

**Orders:**
- "Create order for MON-27HD" - Generate PO
- "Show suppliers" - Vendor list

**Reports:**
- "Inventory report" - Summary dashboard
- "Stock history for KB-ERGO1" - Movement log

Just ask naturally - I'll understand!"""


async def demo():
    """Run an interactive demo."""
    print("=" * 60)
    print("WooCommerce Inventory Management Assistant")
    print("=" * 60)
    print("\nRunning in DEMO MODE")
    print("Type 'quit' to exit\n")

    assistant = InventoryAssistant(demo_mode=True)

    # Demo queries
    demo_queries = [
        "Show low stock items",
        "Check stock KB-ERGO1",
        "Where is the USB Hub?",
        "Inventory report",
    ]

    print("Running demo queries...\n")

    for query in demo_queries:
        print(f"👤 Manager: {query}")
        print("-" * 40)
        response = await assistant.process_message(query)
        print(f"🤖 Assistant:\n{response}")
        print("=" * 60)
        print()


async def interactive():
    """Run interactive mode."""
    print("=" * 60)
    print("WooCommerce Inventory Management Assistant")
    print("=" * 60)
    print("\nType 'quit' to exit, 'help' for commands\n")

    assistant = InventoryAssistant(demo_mode=True)

    while True:
        try:
            user_input = input("👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit"]:
                print("👋 Goodbye!")
                break

            response = await assistant.process_message(user_input)
            print(f"\n🤖 Assistant:\n{response}\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(demo())
