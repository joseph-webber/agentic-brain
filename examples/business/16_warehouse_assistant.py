#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 16: Warehouse Assistant Chatbot

An AI assistant for warehouse staff handling:
- Stock level queries ("How many Ergonomic Keyboard Pro do we have?")
- Low stock alerts ("What's running low?")
- Location lookups ("Where is the 27-inch HD Monitor stored?")
- Picking assistance ("I need to pick order #12345")
- Receiving goods ("Just received 50 units of...")

This example shows how to build a conversational interface
for warehouse operations using agentic-brain.

Key patterns demonstrated:
- Natural language to database queries
- Context-aware conversations (remembers current task)
- Structured data extraction from speech-like input
- Integration with inventory systems

Usage:
    python examples/16_warehouse_assistant.py

Requirements:
    pip install agentic-brain

Real-world integration points:
    - WooCommerce/ATUM via SSH+MySQL (see Arraz's po_generator.py)
    - Barcode scanners (USB HID input)
    - Label printers (thermal printing)
    - Pick-to-light systems
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import re
import json

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class StockStatus(Enum):
    """Stock level status indicators."""

    OK = "ok"
    LOW = "low"
    CRITICAL = "critical"
    OUT = "out_of_stock"


@dataclass
class Product:
    """Warehouse product with inventory tracking."""

    sku: str
    name: str
    quantity: int
    location: str  # e.g., "A1-03" = Aisle A, Rack 1, Shelf 3
    low_stock_threshold: int = 10
    reorder_quantity: int = 50
    supplier: str = ""
    last_counted: Optional[datetime] = None

    @property
    def status(self) -> StockStatus:
        if self.quantity == 0:
            return StockStatus.OUT
        elif self.quantity <= self.low_stock_threshold // 2:
            return StockStatus.CRITICAL
        elif self.quantity <= self.low_stock_threshold:
            return StockStatus.LOW
        return StockStatus.OK

    def to_dict(self) -> dict:
        return {
            "sku": self.sku,
            "name": self.name,
            "quantity": self.quantity,
            "location": self.location,
            "status": self.status.value,
            "supplier": self.supplier,
        }


@dataclass
class PickItem:
    """Single item in a pick list."""

    product: Product
    quantity_needed: int
    quantity_picked: int = 0

    @property
    def is_complete(self) -> bool:
        return self.quantity_picked >= self.quantity_needed

    @property
    def remaining(self) -> int:
        return max(0, self.quantity_needed - self.quantity_picked)


@dataclass
class PickList:
    """A picking task for an order."""

    order_id: str
    items: list[PickItem] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    picker: str = ""

    @property
    def is_complete(self) -> bool:
        return all(item.is_complete for item in self.items)

    @property
    def progress(self) -> str:
        total = len(self.items)
        done = sum(1 for item in self.items if item.is_complete)
        return f"{done}/{total} items"


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATED INVENTORY DATABASE
# ══════════════════════════════════════════════════════════════════════════════


class InventoryDB:
    """
    Simulated inventory database.

    In production, replace with:
    - WooCommerce/ATUM via SSH+MySQL
    - Direct database connection
    - REST API calls
    """

    def __init__(self):
        # Sample inventory data
        self.products: dict[str, Product] = {
            "KB-ERGO1": Product(
                sku="KB-ERGO1",
                name="Ergonomic Keyboard Pro",
                quantity=45,
                location="A1-02",
                low_stock_threshold=20,
                supplier="TechSupply Co",
            ),
            "MS-WL500": Product(
                sku="MS-WL500",
                name="Wireless Mouse 500",
                quantity=8,  # Low stock!
                location="A1-03",
                low_stock_threshold=15,
                supplier="TechSupply Co",
            ),
            "MON-27HD": Product(
                sku="MON-27HD",
                name="27-inch HD Monitor",
                quantity=12,
                location="B2-01",
                low_stock_threshold=5,
                supplier="DisplayTech",
            ),
            "MON-24ST": Product(
                sku="MON-24ST",
                name="24-inch Standard Monitor",
                quantity=3,  # Critical!
                location="B2-02",
                low_stock_threshold=5,
                supplier="DisplayTech",
            ),
            "UMON-HUB4": Product(
                sku="UMON-HUB4",
                name="USB Hub 4-Port",
                quantity=120,
                location="C3-05",
                low_stock_threshold=30,
                supplier="TechSupply Co",
            ),
            "CBL-HDMI2": Product(
                sku="CBL-HDMI2",
                name="HDMI Cable 2m",
                quantity=0,  # Out of stock!
                location="D1-01",
                low_stock_threshold=10,
                supplier="CableCo",
            ),
        }

        # Simulated orders waiting to be picked
        self.pending_orders: dict[str, list[tuple[str, int]]] = {
            "12345": [("KB-ERGO1", 2), ("UMON-HUB4", 5)],
            "12346": [("MON-27HD", 1)],
            "12347": [("MS-WL500", 1), ("KB-ERGO1", 1), ("MON-24ST", 1)],
        }

    def search_products(self, query: str) -> list[Product]:
        """Fuzzy search products by name or SKU."""
        query_lower = query.lower()
        results = []
        for product in self.products.values():
            if (
                query_lower in product.name.lower()
                or query_lower in product.sku.lower()
            ):
                results.append(product)
        return results

    def get_product(self, sku: str) -> Optional[Product]:
        """Get product by exact SKU."""
        return self.products.get(sku)

    def get_low_stock(self) -> list[Product]:
        """Get all products below their low stock threshold."""
        return [
            p
            for p in self.products.values()
            if p.status in (StockStatus.LOW, StockStatus.CRITICAL, StockStatus.OUT)
        ]

    def get_by_location(self, location_prefix: str) -> list[Product]:
        """Get products in a location (e.g., 'A1' for all of Aisle A Rack 1)."""
        return [
            p for p in self.products.values() if p.location.startswith(location_prefix)
        ]

    def get_pick_list(self, order_id: str) -> Optional[PickList]:
        """Generate pick list for an order."""
        if order_id not in self.pending_orders:
            return None

        pick_list = PickList(order_id=order_id, started_at=datetime.now())
        for sku, qty in self.pending_orders[order_id]:
            product = self.get_product(sku)
            if product:
                pick_list.items.append(PickItem(product=product, quantity_needed=qty))

        # Sort by location for efficient picking
        pick_list.items.sort(key=lambda x: x.product.location)
        return pick_list

    def receive_stock(self, sku: str, quantity: int) -> bool:
        """Add received stock to inventory."""
        if sku in self.products:
            self.products[sku].quantity += quantity
            return True
        return False

    def adjust_stock(self, sku: str, new_quantity: int) -> bool:
        """Set stock to specific quantity (after count)."""
        if sku in self.products:
            self.products[sku].quantity = new_quantity
            self.products[sku].last_counted = datetime.now()
            return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
# WAREHOUSE ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a warehouse assistant helping staff with inventory tasks.

You have access to the inventory system and can help with:
1. Stock queries - "How many X do we have?"
2. Location lookups - "Where is X stored?"
3. Low stock alerts - "What's running low?"
4. Order picking - "Pick order #12345"
5. Receiving goods - "Just received 50 units of X"
6. Stock counts - "Counted 45 units of X"

When responding:
- Be concise and clear (warehouse is noisy)
- Give locations in format "Aisle-Rack-Shelf" (e.g., A1-02)
- For picking, guide through items in location order
- Alert on any stock issues discovered

Current context: {context}

Respond with a JSON object:
{
    "action": "query|pick|receive|count|alert|chat",
    "response": "Your spoken response to the user",
    "data": {} // Any structured data for the action
}
"""


class WarehouseAssistant:
    """
    AI-powered warehouse assistant.

    Integrates with inventory system to provide natural language
    interface for warehouse operations.
    """

    def __init__(self, db: InventoryDB):
        self.db = db
        self.current_pick: Optional[PickList] = None
        self.context: list[str] = []

    async def process_message(self, message: str) -> str:
        """
        Process a natural language message and return response.

        In production, this would call the LLM via agentic-brain's router.
        For this example, we use rule-based matching.
        """
        message_lower = message.lower().strip()

        # Quick pattern matching for common queries
        # In production, the LLM handles this more naturally

        # Stock quantity queries
        if any(
            phrase in message_lower
            for phrase in ["how many", "stock level", "quantity of", "do we have"]
        ):
            return await self._handle_stock_query(message)

        # Location queries
        if any(
            phrase in message_lower
            for phrase in ["where is", "location of", "find the", "stored"]
        ):
            return await self._handle_location_query(message)

        # Low stock queries
        if any(
            phrase in message_lower
            for phrase in ["running low", "low stock", "need to reorder", "what's low"]
        ):
            return await self._handle_low_stock()

        # Order picking
        if "pick order" in message_lower or "pick list" in message_lower:
            return await self._handle_pick_order(message)

        # Continue picking
        if self.current_pick and any(
            phrase in message_lower for phrase in ["next", "done", "picked", "got it"]
        ):
            return await self._handle_pick_progress(message)

        # Receiving goods
        if any(
            phrase in message_lower
            for phrase in ["received", "just got", "delivery of"]
        ):
            return await self._handle_receive(message)

        # Stock count
        if any(
            phrase in message_lower
            for phrase in ["counted", "count is", "actually have"]
        ):
            return await self._handle_count(message)

        # Default: provide help
        return self._help_message()

    async def _handle_stock_query(self, message: str) -> str:
        """Handle stock quantity queries."""
        # Extract product name from message
        products = self._extract_products(message)

        if not products:
            return "I couldn't identify which product you're asking about. Try using the SKU or exact name."

        responses = []
        for product in products:
            status_emoji = {
                StockStatus.OK: "✓",
                StockStatus.LOW: "⚠️",
                StockStatus.CRITICAL: "🔴",
                StockStatus.OUT: "❌",
            }
            responses.append(
                f"{product.name}: {product.quantity} units {status_emoji[product.status]} "
                f"(Location: {product.location})"
            )

        return "\n".join(responses)

    async def _handle_location_query(self, message: str) -> str:
        """Handle product location queries."""
        products = self._extract_products(message)

        if not products:
            return "Which product are you looking for?"

        responses = []
        for product in products:
            responses.append(f"{product.name}: {product.location}")

        return "\n".join(responses)

    async def _handle_low_stock(self) -> str:
        """Report low stock items."""
        low_stock = self.db.get_low_stock()

        if not low_stock:
            return "✓ All stock levels are healthy!"

        # Group by status
        critical = [p for p in low_stock if p.status == StockStatus.CRITICAL]
        out = [p for p in low_stock if p.status == StockStatus.OUT]
        low = [p for p in low_stock if p.status == StockStatus.LOW]

        lines = []
        if out:
            lines.append("❌ OUT OF STOCK:")
            for p in out:
                lines.append(f"   • {p.name} ({p.sku}) - Supplier: {p.supplier}")

        if critical:
            lines.append("🔴 CRITICAL:")
            for p in critical:
                lines.append(
                    f"   • {p.name}: {p.quantity} left (need {p.reorder_quantity})"
                )

        if low:
            lines.append("⚠️ LOW STOCK:")
            for p in low:
                lines.append(f"   • {p.name}: {p.quantity} left")

        return "\n".join(lines)

    async def _handle_pick_order(self, message: str) -> str:
        """Start picking an order."""
        # Extract order ID
        match = re.search(r"#?(\d{4,})", message)
        if not match:
            return "Which order number? Say 'pick order #12345'"

        order_id = match.group(1)
        pick_list = self.db.get_pick_list(order_id)

        if not pick_list:
            return f"Order #{order_id} not found or already picked."

        self.current_pick = pick_list

        # Start with first item
        first_item = pick_list.items[0]
        return (
            f"📦 Order #{order_id} - {len(pick_list.items)} items\n\n"
            f"Go to {first_item.product.location}:\n"
            f"   Pick {first_item.quantity_needed}x {first_item.product.name}\n\n"
            f"Say 'done' when picked, or 'next' to skip."
        )

    async def _handle_pick_progress(self, message: str) -> str:
        """Handle picking progress updates."""
        if not self.current_pick:
            return "No active pick list. Say 'pick order #12345' to start."

        # Find current item (first incomplete)
        current_item = None
        for item in self.current_pick.items:
            if not item.is_complete:
                current_item = item
                break

        if not current_item:
            return self._complete_pick()

        # Mark current as picked
        if any(word in message.lower() for word in ["done", "picked", "got"]):
            current_item.quantity_picked = current_item.quantity_needed

            # Check stock level
            if current_item.product.quantity < current_item.quantity_needed:
                return (
                    f"⚠️ Warning: Only {current_item.product.quantity} available, "
                    f"needed {current_item.quantity_needed}. Partial pick recorded.\n"
                    f"Say 'next' to continue."
                )

        # Find next item
        next_item = None
        for item in self.current_pick.items:
            if not item.is_complete:
                next_item = item
                break

        if not next_item:
            return self._complete_pick()

        return (
            f"✓ Got it! ({self.current_pick.progress})\n\n"
            f"Next: Go to {next_item.product.location}\n"
            f"   Pick {next_item.quantity_needed}x {next_item.product.name}"
        )

    def _complete_pick(self) -> str:
        """Complete the current pick list."""
        if not self.current_pick:
            return "No active pick."

        order_id = self.current_pick.order_id
        self.current_pick.completed_at = datetime.now()
        self.current_pick = None

        return f"✅ Order #{order_id} complete! Ready for packing."

    async def _handle_receive(self, message: str) -> str:
        """Handle receiving goods into inventory."""
        # Extract quantity and product
        qty_match = re.search(r"(\d+)\s*(units?|pcs?|pieces?)?", message)
        if not qty_match:
            return "How many units? Say 'received 50 units of [product]'"

        quantity = int(qty_match.group(1))
        products = self._extract_products(message)

        if not products:
            return "Which product? Say 'received 50 units of TechSupply Co M7'"

        results = []
        for product in products:
            old_qty = product.quantity
            self.db.receive_stock(product.sku, quantity)
            new_qty = product.quantity
            results.append(
                f"✓ {product.name}: {old_qty} → {new_qty} (+{quantity})\n"
                f"   Location: {product.location}"
            )

        return "\n".join(results)

    async def _handle_count(self, message: str) -> str:
        """Handle stock count adjustments."""
        # Extract new quantity
        qty_match = re.search(r"(\d+)", message)
        if not qty_match:
            return "What's the count? Say 'counted 45 of [product]'"

        new_quantity = int(qty_match.group(1))
        products = self._extract_products(message)

        if not products:
            return "Which product? Say 'counted 45 TechSupply Co M7'"

        results = []
        for product in products:
            old_qty = product.quantity
            diff = new_quantity - old_qty
            self.db.adjust_stock(product.sku, new_quantity)

            diff_str = f"+{diff}" if diff > 0 else str(diff)
            results.append(
                f"✓ {product.name}: {old_qty} → {new_quantity} ({diff_str})\n"
                f"   Count recorded at {datetime.now().strftime('%H:%M')}"
            )

        return "\n".join(results)

    def _extract_products(self, message: str) -> list[Product]:
        """Extract product references from message text."""
        # Try to find products by name fragments
        products = []
        for word in message.split():
            # Skip common words
            if word.lower() in (
                "how",
                "many",
                "the",
                "is",
                "do",
                "we",
                "have",
                "of",
                "where",
            ):
                continue

            matches = self.db.search_products(word)
            for match in matches:
                if match not in products:
                    products.append(match)

        return products

    def _help_message(self) -> str:
        """Return help text."""
        return """🏭 Warehouse Assistant - I can help with:

• "How many TechSupply Co M7 do we have?"
• "Where is the 27-inch HD Monitor stored?"
• "What's running low?"
• "Pick order #12345"
• "Received 50 units of USB Hub 4-Port"
• "Counted 45 Wireless Mouse 500"

Just ask naturally!"""


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    """Demo the warehouse assistant."""
    print("=" * 60)
    print("🏭 WAREHOUSE ASSISTANT")
    print("=" * 60)
    print()

    db = InventoryDB()
    assistant = WarehouseAssistant(db)

    # Demo conversations
    demo_messages = [
        "What's running low?",
        "How many Ergonomic Keyboard Pro do we have?",
        "Where is the 27-inch HD Monitor stored?",
        "Pick order #12345",
        "done",
        "got it",
        "Received 20 units of Mouse 500",
        "Counted 50 USB Hub 4-Ports",
    ]

    for message in demo_messages:
        print(f"👤 {message}")
        response = await assistant.process_message(message)
        print(f"🤖 {response}")
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())
