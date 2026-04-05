#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 18: Packing Station Assistant

An AI assistant for the packing station:
- Order verification ("Verify order #12345")
- Packing guidance ("What box size for this order?")
- Label printing ("Print label for order #12345")
- Package weight validation
- Fragile item handling reminders
- Batch packing mode for multiple orders

This example shows how to build a packing workflow assistant
that ensures accurate, consistent order fulfillment.

Key patterns demonstrated:
- Weight-based package selection
- Multi-item order consolidation
- Shipping carrier selection
- Compliance checks (dangerous goods, etc.)

Usage:
    python examples/18_packing_assistant.py

Requirements:
    pip install agentic-brain
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class BoxSize(Enum):
    """Standard box sizes."""

    SMALL = "small"  # Up to 500g
    MEDIUM = "medium"  # 500g - 2kg
    LARGE = "large"  # 2kg - 5kg
    XLARGE = "xlarge"  # 5kg+
    TUBE = "tube"  # Long items
    PADDED = "padded"  # Fragile items


class Carrier(Enum):
    """Shipping carriers."""

    AUSPOST_REGULAR = "auspost_regular"
    AUSPOST_EXPRESS = "auspost_express"
    SENDLE = "sendle"
    STARTRACK = "startrack"
    PICKUP = "pickup"


class PackingFlag(Enum):
    """Special packing requirements."""

    FRAGILE = "fragile"
    BATTERY = "battery"
    LIQUID = "liquid"
    ADULT = "adult_signature"
    INSURANCE = "insurance_required"
    GIFT = "gift_wrapped"


@dataclass
class OrderItem:
    """Item in an order."""

    sku: str
    name: str
    quantity: int
    weight_grams: int  # Per unit
    fragile: bool = False
    has_battery: bool = False
    requires_adult_sig: bool = False

    @property
    def total_weight(self) -> int:
        return self.weight_grams * self.quantity


@dataclass
class PackingOrder:
    """An order ready for packing."""

    order_id: str
    items: list[OrderItem]
    customer_name: str
    shipping_address: str
    carrier: Carrier = Carrier.AUSPOST_REGULAR
    flags: list[PackingFlag] = field(default_factory=list)
    packed_at: Optional[datetime] = None
    tracking_number: str = ""
    box_size: Optional[BoxSize] = None
    actual_weight: int = 0

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def estimated_weight(self) -> int:
        return sum(item.total_weight for item in self.items)

    @property
    def needs_fragile(self) -> bool:
        return any(item.fragile for item in self.items)

    @property
    def has_batteries(self) -> bool:
        return any(item.has_battery for item in self.items)


@dataclass
class PackingSession:
    """A packing session (batch mode)."""

    session_id: str
    orders: list[PackingOrder]
    current_index: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    completed_orders: int = 0

    @property
    def current_order(self) -> Optional[PackingOrder]:
        if 0 <= self.current_index < len(self.orders):
            return self.orders[self.current_index]
        return None

    @property
    def progress(self) -> str:
        return f"{self.completed_orders}/{len(self.orders)}"


# ══════════════════════════════════════════════════════════════════════════════
# PACKAGING RULES
# ══════════════════════════════════════════════════════════════════════════════

# Box selection by weight
BOX_WEIGHTS = {
    BoxSize.SMALL: 500,  # Up to 500g
    BoxSize.MEDIUM: 2000,  # Up to 2kg
    BoxSize.LARGE: 5000,  # Up to 5kg
    BoxSize.XLARGE: 22000,  # Up to 22kg (AusPost limit)
}

# Carrier limits
CARRIER_LIMITS = {
    Carrier.AUSPOST_REGULAR: {"max_weight": 22000, "max_value": 5000},
    Carrier.AUSPOST_EXPRESS: {"max_weight": 22000, "max_value": 5000},
    Carrier.SENDLE: {"max_weight": 25000, "max_value": 10000},
    Carrier.STARTRACK: {"max_weight": 70000, "max_value": 50000},
}

# Special handling messages
HANDLING_MESSAGES = {
    PackingFlag.FRAGILE: "🔴 FRAGILE: Use bubble wrap. Handle with care.",
    PackingFlag.BATTERY: "⚡ BATTERY: Must ship ground only. Check lithium label.",
    PackingFlag.LIQUID: "💧 LIQUID: Bag separately. Check for leaks.",
    PackingFlag.ADULT: "🔞 ADULT SIG: Requires adult signature on delivery.",
    PackingFlag.INSURANCE: "💰 INSURED: Double-check tracking is active.",
    PackingFlag.GIFT: "🎁 GIFT: Include gift wrap and message.",
}


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATED DATABASE
# ══════════════════════════════════════════════════════════════════════════════


class PackingDB:
    """Simulated packing database."""

    def __init__(self):
        # Sample product data
        self.products = {
            "KB-ERGO1": {
                "name": "Ergonomic Keyboard Pro",
                "weight": 150,
                "fragile": False,
                "battery": False,
            },
            "MS-WL500": {
                "name": "Wireless Mouse 500",
                "weight": 120,
                "fragile": False,
                "battery": False,
            },
            "MON-27HD": {
                "name": "27-inch HD Monitor",
                "weight": 450,
                "fragile": True,
                "battery": True,
            },
            "MON-24ST": {
                "name": "24-inch Standard Monitor",
                "weight": 380,
                "fragile": True,
                "battery": True,
            },
            "UMON-HUB4": {
                "name": "USB Hub 4-Port",
                "weight": 25,
                "fragile": False,
                "battery": False,
            },
            "CBL-HDMI2": {
                "name": "HDMI Cable 2m",
                "weight": 200,
                "fragile": False,
                "battery": False,
            },
        }

        # Sample orders ready to pack
        self.pending_orders = {
            "12345": PackingOrder(
                order_id="12345",
                items=[
                    OrderItem("KB-ERGO1", "Ergonomic Keyboard Pro", 2, 150),
                    OrderItem("UMON-HUB4", "USB Hub 4-Port", 5, 25),
                ],
                customer_name="John Smith",
                shipping_address="123 Main St, Sydney NSW 2000",
                carrier=Carrier.AUSPOST_REGULAR,
            ),
            "12346": PackingOrder(
                order_id="12346",
                items=[
                    OrderItem(
                        "MON-27HD",
                        "27-inch HD Monitor",
                        1,
                        450,
                        fragile=True,
                        has_battery=True,
                    ),
                ],
                customer_name="Jane Doe",
                shipping_address="456 High St, Melbourne VIC 3000",
                carrier=Carrier.AUSPOST_EXPRESS,
                flags=[PackingFlag.FRAGILE, PackingFlag.BATTERY],
            ),
            "12347": PackingOrder(
                order_id="12347",
                items=[
                    OrderItem("MS-WL500", "Wireless Mouse 500", 1, 120),
                    OrderItem("KB-ERGO1", "Ergonomic Keyboard Pro", 1, 150),
                    OrderItem(
                        "MON-24ST",
                        "24-inch Standard Monitor",
                        1,
                        380,
                        fragile=True,
                        has_battery=True,
                    ),
                ],
                customer_name="Bob Wilson",
                shipping_address="789 Low St, Brisbane QLD 4000",
                carrier=Carrier.SENDLE,
                flags=[PackingFlag.FRAGILE, PackingFlag.BATTERY],
            ),
        }

        self.packed_orders: dict[str, PackingOrder] = {}

    def get_order(self, order_id: str) -> Optional[PackingOrder]:
        return self.pending_orders.get(order_id)

    def get_pending_orders(self) -> list[PackingOrder]:
        return list(self.pending_orders.values())

    def mark_packed(self, order_id: str, box_size: BoxSize, weight: int, tracking: str):
        """Mark order as packed."""
        if order_id in self.pending_orders:
            order = self.pending_orders.pop(order_id)
            order.box_size = box_size
            order.actual_weight = weight
            order.tracking_number = tracking
            order.packed_at = datetime.now()
            self.packed_orders[order_id] = order


# ══════════════════════════════════════════════════════════════════════════════
# PACKING ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class PackingAssistant:
    """AI-powered packing station assistant."""

    def __init__(self, db: PackingDB):
        self.db = db
        self.current_order: Optional[PackingOrder] = None
        self.batch_session: Optional[PackingSession] = None
        self.verified: bool = False

    async def process_message(self, message: str) -> str:
        """Process user message and return response."""
        message_lower = message.lower().strip()

        # Start packing an order
        if any(
            phrase in message_lower
            for phrase in ["pack order", "start order", "verify order"]
        ):
            return await self._start_order(message)

        # Batch mode
        if "batch" in message_lower or "all orders" in message_lower:
            return await self._start_batch()

        # Current order operations
        if self.current_order:
            if (
                "verified" in message_lower
                or "confirmed" in message_lower
                or "check" in message_lower
            ):
                return await self._verify_items()
            elif "box" in message_lower or "size" in message_lower:
                return await self._suggest_box()
            elif (
                "weigh" in message_lower
                or "weight" in message_lower
                or re.search(r"\d+\s*g", message_lower)
            ):
                return await self._record_weight(message)
            elif "label" in message_lower or "print" in message_lower:
                return await self._print_label()
            elif (
                "done" in message_lower
                or "complete" in message_lower
                or "packed" in message_lower
            ):
                return await self._complete_order()
            elif "next" in message_lower:
                return await self._next_order()
            elif "skip" in message_lower:
                return await self._skip_order()

        # What's pending
        if (
            "pending" in message_lower
            or "queue" in message_lower
            or "how many" in message_lower
        ):
            return await self._show_pending()

        return self._help_message()

    async def _start_order(self, message: str) -> str:
        """Start packing an order."""
        match = re.search(r"#?(\d{4,})", message)
        if not match:
            return "Which order? Say 'pack order #12345'"

        order_id = match.group(1)
        order = self.db.get_order(order_id)

        if not order:
            return f"Order #{order_id} not found or already packed."

        self.current_order = order
        self.verified = False

        return self._format_order_summary(order)

    def _format_order_summary(self, order: PackingOrder) -> str:
        """Format order summary for packing."""
        lines = [
            f"📦 ORDER #{order.order_id}",
            "=" * 40,
            f"Customer: {order.customer_name}",
            f"Ship to: {order.shipping_address}",
            f"Carrier: {order.carrier.value}",
            "",
            f"Items ({order.total_items}):",
        ]

        for item in order.items:
            lines.append(f"  □ {item.quantity}x {item.name} ({item.sku})")

        lines.append(f"\nEstimated weight: {order.estimated_weight}g")

        # Special handling alerts
        if order.flags:
            lines.append("\n⚠️ SPECIAL HANDLING:")
            for flag in order.flags:
                lines.append(f"  {HANDLING_MESSAGES.get(flag, flag.value)}")

        lines.append("\nSay 'verified' when all items confirmed.")

        return "\n".join(lines)

    async def _verify_items(self) -> str:
        """Verify all items are present."""
        if not self.current_order:
            return "No active order."

        self.verified = True

        # Check for special handling
        alerts = []
        if self.current_order.needs_fragile:
            alerts.append("🔴 FRAGILE items - use bubble wrap!")
        if self.current_order.has_batteries:
            alerts.append("⚡ BATTERIES - ground shipping only, add lithium label")

        response = "✓ Items verified!\n\n"

        if alerts:
            response += "\n".join(alerts) + "\n\n"

        # Suggest box
        suggested_box = self._calculate_box_size(self.current_order.estimated_weight)
        response += f"Recommended box: {suggested_box.value.upper()}\n"
        response += "Say 'weigh 450g' when package is weighed."

        return response

    def _calculate_box_size(self, weight: int) -> BoxSize:
        """Calculate appropriate box size based on weight."""
        for box, max_weight in BOX_WEIGHTS.items():
            if weight <= max_weight:
                return box
        return BoxSize.XLARGE

    async def _suggest_box(self) -> str:
        """Suggest box size for current order."""
        if not self.current_order:
            return "No active order."

        weight = self.current_order.estimated_weight
        suggested = self._calculate_box_size(weight)

        lines = [
            "📦 BOX SELECTION",
            f"Estimated weight: {weight}g",
            f"Recommended: {suggested.value.upper()}",
            "",
            "Box sizes:",
            f"  SMALL  - up to 500g {'← ✓' if suggested == BoxSize.SMALL else ''}",
            f"  MEDIUM - up to 2kg {'← ✓' if suggested == BoxSize.MEDIUM else ''}",
            f"  LARGE  - up to 5kg {'← ✓' if suggested == BoxSize.LARGE else ''}",
            f"  XLARGE - up to 22kg {'← ✓' if suggested == BoxSize.XLARGE else ''}",
        ]

        if self.current_order.needs_fragile:
            lines.append("\n💡 Consider PADDED box for fragile items")

        return "\n".join(lines)

    async def _record_weight(self, message: str) -> str:
        """Record actual package weight."""
        if not self.current_order:
            return "No active order."

        # Extract weight from message
        match = re.search(r"(\d+)\s*g", message.lower())
        if not match:
            match = re.search(r"(\d+)", message)

        if not match:
            return "Enter weight in grams, e.g., 'weigh 450g'"

        actual_weight = int(match.group(1))
        estimated = self.current_order.estimated_weight
        variance = abs(actual_weight - estimated)
        variance_pct = (variance / estimated * 100) if estimated > 0 else 0

        # Weight variance warning
        if variance_pct > 20:
            return (
                f"⚠️ WEIGHT VARIANCE: {variance_pct:.0f}%\n"
                f"Estimated: {estimated}g\n"
                f"Actual: {actual_weight}g\n\n"
                f"Double-check all items are included!\n"
                f"Say 'confirmed' to proceed anyway."
            )

        self.current_order.actual_weight = actual_weight

        return (
            f"✓ Weight recorded: {actual_weight}g\n"
            f"(Estimated was {estimated}g - {'+' if actual_weight > estimated else ''}{actual_weight - estimated}g)\n\n"
            f"Say 'print label' to generate shipping label."
        )

    async def _print_label(self) -> str:
        """Print shipping label."""
        if not self.current_order:
            return "No active order."

        if not self.verified:
            return "⚠️ Verify items first before printing label."

        # Generate mock tracking number
        import random

        tracking = f"AUS{random.randint(100000000, 999999999)}"
        self.current_order.tracking_number = tracking

        carrier_name = self.current_order.carrier.value.replace("_", " ").title()

        return (
            f"🏷️ PRINTING LABEL\n"
            f"{'=' * 40}\n\n"
            f"Carrier: {carrier_name}\n"
            f"Tracking: {tracking}\n\n"
            f"To: {self.current_order.customer_name}\n"
            f"    {self.current_order.shipping_address}\n\n"
            f"[Label printing to thermal printer...]\n\n"
            f"Attach label and say 'done' when packed."
        )

    async def _complete_order(self) -> str:
        """Complete the current order."""
        if not self.current_order:
            return "No active order."

        order = self.current_order
        box = self._calculate_box_size(order.actual_weight or order.estimated_weight)
        tracking = order.tracking_number or "PENDING"

        self.db.mark_packed(
            order.order_id, box, order.actual_weight or order.estimated_weight, tracking
        )

        response = (
            f"✅ ORDER #{order.order_id} PACKED!\n"
            f"{'=' * 40}\n"
            f"Box: {box.value}\n"
            f"Weight: {order.actual_weight or order.estimated_weight}g\n"
            f"Tracking: {tracking}\n"
        )

        self.current_order = None
        self.verified = False

        # If in batch mode, prompt for next
        if self.batch_session:
            self.batch_session.completed_orders += 1
            self.batch_session.current_index += 1

            if self.batch_session.current_order:
                response += (
                    f"\n📦 NEXT: Order #{self.batch_session.current_order.order_id}"
                )
                response += "\nSay 'next' to continue batch."
            else:
                response += (
                    f"\n🎉 BATCH COMPLETE! {self.batch_session.progress} orders packed."
                )
                self.batch_session = None
        else:
            pending = len(self.db.get_pending_orders())
            response += f"\n{pending} orders still pending."

        return response

    async def _start_batch(self) -> str:
        """Start batch packing mode."""
        pending = self.db.get_pending_orders()

        if not pending:
            return "No pending orders to pack."

        self.batch_session = PackingSession(
            session_id=datetime.now().strftime("%Y%m%d%H%M"),
            orders=pending,
        )

        return (
            f"📦 BATCH MODE STARTED\n"
            f"{'=' * 40}\n"
            f"Orders to pack: {len(pending)}\n\n"
            f"First order: #{pending[0].order_id}\n"
            f"Say 'next' to begin."
        )

    async def _next_order(self) -> str:
        """Move to next order in batch."""
        if self.batch_session and self.batch_session.current_order:
            self.current_order = self.batch_session.current_order
            self.verified = False
            return self._format_order_summary(self.current_order)

        return "No more orders in batch."

    async def _skip_order(self) -> str:
        """Skip current order in batch."""
        if not self.batch_session:
            return "Not in batch mode."

        self.batch_session.current_index += 1
        self.current_order = None
        self.verified = False

        if self.batch_session.current_order:
            return f"Skipped. Next: #{self.batch_session.current_order.order_id}"

        return "No more orders."

    async def _show_pending(self) -> str:
        """Show pending orders."""
        pending = self.db.get_pending_orders()

        if not pending:
            return "✓ All orders packed!"

        lines = [
            f"📋 PENDING ORDERS: {len(pending)}",
            "=" * 40,
        ]

        for order in pending:
            flags = " ".join(
                [
                    "⚠️" if order.needs_fragile else "",
                    "⚡" if order.has_batteries else "",
                ]
            ).strip()
            lines.append(
                f"  #{order.order_id} - {order.total_items} items, "
                f"{order.estimated_weight}g {flags}"
            )

        lines.append("\nSay 'batch' to pack all, or 'pack order #12345'")

        return "\n".join(lines)

    def _help_message(self) -> str:
        """Return help text."""
        return """📦 Packing Assistant - I can help with:

• "Pack order #12345" - Start packing
• "Batch mode" - Pack all pending orders
• "Verified" - Confirm items present
• "Weigh 450g" - Record weight
• "Print label" - Generate shipping label
• "Done" - Complete packing
• "Pending" - Show queue

Just ask naturally!"""


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    """Demo the packing assistant."""
    print("=" * 60)
    print("📦 PACKING ASSISTANT")
    print("=" * 60)
    print()

    db = PackingDB()
    assistant = PackingAssistant(db)

    # Demo single order packing
    demo_messages = [
        "Pending orders?",
        "Pack order #12346",
        "verified",
        "weigh 520g",
        "print label",
        "done",
        "pending",
    ]

    for message in demo_messages:
        print(f"👤 {message}")
        response = await assistant.process_message(message)
        print(f"🤖 {response}")
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())
