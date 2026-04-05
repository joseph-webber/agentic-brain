#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 19: Store Manager Dashboard Chatbot

An AI assistant for store managers:
- Daily sales summaries ("How did we do today?")
- Staff performance ("Who's the top picker?")
- Inventory alerts ("Any stock issues?")
- Order status ("Where's order #12345?")
- Customer insights ("Top customers this week?")
- Supplier status ("When's the TechSupply Co order arriving?")

This example shows how to build a management dashboard chatbot
that aggregates data from multiple sources.

Key patterns demonstrated:
- Multi-source data aggregation
- Natural language metrics queries
- Trend analysis and comparisons
- Alert prioritization

Usage:
    python examples/19_store_manager.py

Requirements:
    pip install agentic-brain
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class OrderStatus(Enum):
    """Order lifecycle status."""

    PENDING = "pending"
    PAID = "paid"
    PICKING = "picking"
    PACKING = "packing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    REFUNDED = "refunded"
    FAILED = "failed"


class AlertPriority(Enum):
    """Alert priority levels."""

    CRITICAL = "critical"  # Needs immediate action
    HIGH = "high"  # Today
    MEDIUM = "medium"  # This week
    LOW = "low"  # FYI


@dataclass
class DailySales:
    """Daily sales summary."""

    date: datetime
    total_orders: int
    total_revenue: float
    avg_order_value: float
    unique_customers: int
    new_customers: int
    returning_customers: int
    top_products: list[tuple[str, int]]  # (name, quantity)

    @property
    def formatted_revenue(self) -> str:
        return f"${self.total_revenue:,.2f}"


@dataclass
class StaffMetrics:
    """Staff performance metrics."""

    name: str
    orders_picked: int
    orders_packed: int
    avg_pick_time_mins: float
    avg_pack_time_mins: float
    errors: int

    @property
    def total_orders(self) -> int:
        return self.orders_picked + self.orders_packed

    @property
    def error_rate(self) -> float:
        if self.total_orders == 0:
            return 0.0
        return (self.errors / self.total_orders) * 100


@dataclass
class SupplierOrder:
    """Order placed with supplier."""

    supplier: str
    order_number: str
    ordered_date: datetime
    expected_date: datetime
    items: list[tuple[str, int]]  # (product, quantity)
    status: str  # ordered, shipped, received
    tracking: str = ""


@dataclass
class Alert:
    """System alert."""

    id: str
    priority: AlertPriority
    category: str
    message: str
    created_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATED DATABASE
# ══════════════════════════════════════════════════════════════════════════════


class ManagerDB:
    """Simulated management database with aggregated data."""

    def __init__(self):
        # Generate sample data
        self._generate_sample_data()

    def _generate_sample_data(self):
        """Generate realistic sample data."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Daily sales (last 7 days)
        self.daily_sales = {}
        for i in range(7):
            date = today - timedelta(days=i)
            orders = random.randint(15, 45)
            revenue = orders * random.uniform(80, 150)
            self.daily_sales[date.strftime("%Y-%m-%d")] = DailySales(
                date=date,
                total_orders=orders,
                total_revenue=revenue,
                avg_order_value=revenue / orders,
                unique_customers=int(orders * 0.85),
                new_customers=int(orders * 0.25),
                returning_customers=int(orders * 0.60),
                top_products=[
                    ("Ergonomic Keyboard Pro", random.randint(5, 15)),
                    ("27-inch HD Monitor", random.randint(3, 8)),
                    ("USB Hub 4-Port", random.randint(8, 20)),
                ],
            )

        # Staff metrics
        self.staff = {
            "Sam": StaffMetrics("Sam", 45, 38, 4.2, 6.5, 1),
            "Alex": StaffMetrics("Alex", 52, 41, 3.8, 5.9, 0),
            "Jordan": StaffMetrics("Jordan", 38, 35, 5.1, 7.2, 2),
            "Casey": StaffMetrics("Casey", 41, 44, 4.5, 6.1, 1),
        }

        # Pending orders by status
        self.orders_by_status = {
            OrderStatus.PENDING: random.randint(2, 8),
            OrderStatus.PAID: random.randint(5, 15),
            OrderStatus.PICKING: random.randint(3, 8),
            OrderStatus.PACKING: random.randint(2, 6),
            OrderStatus.SHIPPED: random.randint(20, 40),
            OrderStatus.FAILED: random.randint(0, 3),
        }

        # Sample specific orders for lookup
        self.orders = {
            "12345": {
                "status": OrderStatus.SHIPPED,
                "tracking": "AUS123456789",
                "customer": "John Smith",
                "shipped_date": today - timedelta(days=1),
            },
            "12346": {
                "status": OrderStatus.PACKING,
                "tracking": "",
                "customer": "Jane Doe",
                "shipped_date": None,
            },
            "12347": {
                "status": OrderStatus.DELIVERED,
                "tracking": "AUS987654321",
                "customer": "Bob Wilson",
                "shipped_date": today - timedelta(days=3),
            },
        }

        # Supplier orders
        self.supplier_orders = [
            SupplierOrder(
                supplier="TechSupply Co",
                order_number="KB-2024-001",
                ordered_date=today - timedelta(days=5),
                expected_date=today + timedelta(days=3),
                items=[
                    ("Keyboard Pro", 50),
                    ("Mouse 500", 30),
                    ("USB Hub 4-Port", 100),
                ],
                status="shipped",
                tracking="USPS12345",
            ),
            SupplierOrder(
                supplier="DisplayTech",
                order_number="MON-2024-015",
                ordered_date=today - timedelta(days=2),
                expected_date=today + timedelta(days=10),
                items=[("27-inch HD Monitor", 10), ("24-inch Standard Monitor", 10)],
                status="ordered",
            ),
        ]

        # Low stock items
        self.low_stock = [
            {
                "sku": "MS-WL500",
                "name": "Wireless Mouse 500",
                "qty": 8,
                "threshold": 15,
            },
            {
                "sku": "MON-24ST",
                "name": "24-inch Standard Monitor",
                "qty": 3,
                "threshold": 5,
            },
            {"sku": "CBL-HDMI2", "name": "HDMI Cable 2m", "qty": 0, "threshold": 10},
        ]

        # Active alerts
        self.alerts = [
            Alert(
                "A001",
                AlertPriority.CRITICAL,
                "Stock",
                "CBL-HDMI2 is OUT OF STOCK - 2 orders pending",
            ),
            Alert(
                "A002",
                AlertPriority.HIGH,
                "Payment",
                "3 failed orders in last 24 hours",
            ),
            Alert(
                "A003",
                AlertPriority.MEDIUM,
                "Supplier",
                "TechSupply Co order arriving in 3 days - prepare receiving area",
            ),
            Alert(
                "A004",
                AlertPriority.LOW,
                "Performance",
                "Record sales day yesterday: $4,521",
            ),
        ]

        # Top customers
        self.top_customers = [
            {
                "name": "John Smith",
                "orders": 12,
                "revenue": 2340.50,
                "last_order": today - timedelta(days=1),
            },
            {
                "name": "Tech Wholesale",
                "orders": 5,
                "revenue": 4500.00,
                "last_order": today - timedelta(days=3),
            },
            {"name": "Jane Doe", "orders": 8, "revenue": 1890.00, "last_order": today},
        ]

    def get_today_sales(self) -> Optional[DailySales]:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.daily_sales.get(today)

    def get_sales_comparison(self) -> dict:
        """Compare today vs yesterday vs last week."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        today_sales = self.daily_sales.get(today.strftime("%Y-%m-%d"))
        yesterday_sales = self.daily_sales.get(
            (today - timedelta(days=1)).strftime("%Y-%m-%d")
        )
        last_week_sales = self.daily_sales.get(
            (today - timedelta(days=7)).strftime("%Y-%m-%d")
        )

        return {
            "today": today_sales,
            "yesterday": yesterday_sales,
            "last_week": last_week_sales,
        }

    def get_top_staff(self) -> StaffMetrics:
        """Get top performing staff member."""
        return max(self.staff.values(), key=lambda s: s.total_orders)

    def get_order(self, order_id: str) -> Optional[dict]:
        return self.orders.get(order_id)


# ══════════════════════════════════════════════════════════════════════════════
# STORE MANAGER ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class StoreManagerAssistant:
    """AI-powered store manager dashboard assistant."""

    def __init__(self, db: ManagerDB):
        self.db = db

    async def process_message(self, message: str) -> str:
        """Process user message and return response."""
        message_lower = message.lower().strip()

        # Morning briefing / overview
        if any(
            phrase in message_lower
            for phrase in [
                "morning",
                "briefing",
                "overview",
                "status",
                "what's happening",
            ]
        ):
            return await self._morning_briefing()

        # Sales queries
        if any(
            phrase in message_lower
            for phrase in ["sales", "revenue", "how did we do", "money", "orders today"]
        ):
            return await self._sales_summary()

        # Staff performance
        if any(
            phrase in message_lower
            for phrase in ["staff", "team", "picker", "packer", "performance", "who"]
        ):
            return await self._staff_performance()

        # Inventory / stock
        if any(
            phrase in message_lower
            for phrase in ["stock", "inventory", "low", "out of", "reorder"]
        ):
            return await self._stock_status()

        # Specific order lookup
        if "order" in message_lower:
            return await self._order_lookup(message)

        # Supplier queries
        if any(
            phrase in message_lower
            for phrase in ["supplier", "dynavap", "storz", "arriving", "delivery"]
        ):
            return await self._supplier_status()

        # Customer queries
        if any(
            phrase in message_lower
            for phrase in ["customer", "top buyer", "vip", "frequent"]
        ):
            return await self._top_customers()

        # Alerts
        if any(
            phrase in message_lower
            for phrase in ["alert", "issue", "problem", "urgent", "critical"]
        ):
            return await self._show_alerts()

        return self._help_message()

    async def _morning_briefing(self) -> str:
        """Generate morning briefing."""
        today = self.db.get_today_sales()
        comparison = self.db.get_sales_comparison()
        critical_alerts = [
            a for a in self.db.alerts if a.priority == AlertPriority.CRITICAL
        ]

        lines = [
            "☀️ MORNING BRIEFING",
            "=" * 50,
            "",
        ]

        # Critical alerts first
        if critical_alerts:
            lines.append("🚨 CRITICAL ALERTS:")
            for alert in critical_alerts:
                lines.append(f"   • {alert.message}")
            lines.append("")

        # Yesterday's performance
        yesterday = comparison.get("yesterday")
        if yesterday:
            lines.append(
                f"📊 YESTERDAY: {yesterday.formatted_revenue} ({yesterday.total_orders} orders)"
            )

            last_week = comparison.get("last_week")
            if last_week:
                change = (
                    (yesterday.total_revenue - last_week.total_revenue)
                    / last_week.total_revenue
                ) * 100
                arrow = "↑" if change > 0 else "↓"
                lines.append(f"   vs last week: {arrow} {abs(change):.1f}%")

        # Pending work
        lines.append("")
        lines.append("📦 PENDING WORK:")
        pending = self.db.orders_by_status.get(OrderStatus.PAID, 0)
        picking = self.db.orders_by_status.get(OrderStatus.PICKING, 0)
        packing = self.db.orders_by_status.get(OrderStatus.PACKING, 0)
        lines.append(f"   • {pending} orders to pick")
        lines.append(f"   • {picking} being picked")
        lines.append(f"   • {packing} ready to pack")

        # Stock alerts
        out_of_stock = [s for s in self.db.low_stock if s["qty"] == 0]
        low = [s for s in self.db.low_stock if s["qty"] > 0]

        if out_of_stock or low:
            lines.append("")
            lines.append("⚠️ STOCK ALERTS:")
            for item in out_of_stock:
                lines.append(f"   🔴 {item['name']} - OUT OF STOCK")
            for item in low:
                lines.append(f"   🟡 {item['name']} - {item['qty']} left")

        # Incoming shipments
        incoming = [o for o in self.db.supplier_orders if o.status == "shipped"]
        if incoming:
            lines.append("")
            lines.append("📬 INCOMING:")
            for order in incoming:
                days = (order.expected_date - datetime.now()).days
                lines.append(f"   • {order.supplier}: {days} days away")

        return "\n".join(lines)

    async def _sales_summary(self) -> str:
        """Show sales summary."""
        comparison = self.db.get_sales_comparison()

        lines = [
            "💰 SALES SUMMARY",
            "=" * 50,
        ]

        for period, data in [
            ("Today", comparison.get("today")),
            ("Yesterday", comparison.get("yesterday")),
            ("Last week same day", comparison.get("last_week")),
        ]:
            if data:
                lines.append(f"\n{period}:")
                lines.append(f"  Revenue: {data.formatted_revenue}")
                lines.append(f"  Orders: {data.total_orders}")
                lines.append(f"  Avg order: ${data.avg_order_value:.2f}")
                lines.append(f"  New customers: {data.new_customers}")

        # Top products
        yesterday = comparison.get("yesterday")
        if yesterday and yesterday.top_products:
            lines.append("\n🏆 TOP PRODUCTS (Yesterday):")
            for name, qty in yesterday.top_products:
                lines.append(f"   • {name}: {qty} sold")

        return "\n".join(lines)

    async def _staff_performance(self) -> str:
        """Show staff performance."""
        staff = sorted(
            self.db.staff.values(), key=lambda s: s.total_orders, reverse=True
        )

        lines = [
            "👥 STAFF PERFORMANCE (This Week)",
            "=" * 50,
        ]

        for i, member in enumerate(staff, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "

            lines.append(f"\n{medal} {member.name}")
            lines.append(
                f"   Orders: {member.total_orders} (picked: {member.orders_picked}, packed: {member.orders_packed})"
            )
            lines.append(f"   Avg pick time: {member.avg_pick_time_mins:.1f} min")
            lines.append(f"   Avg pack time: {member.avg_pack_time_mins:.1f} min")

            if member.errors > 0:
                lines.append(f"   ⚠️ Errors: {member.errors} ({member.error_rate:.1f}%)")

        top = staff[0]
        lines.append(f"\n🌟 Top performer: {top.name} with {top.total_orders} orders!")

        return "\n".join(lines)

    async def _stock_status(self) -> str:
        """Show stock status and alerts."""
        lines = [
            "📦 STOCK STATUS",
            "=" * 50,
        ]

        out_of_stock = [s for s in self.db.low_stock if s["qty"] == 0]
        low = [s for s in self.db.low_stock if s["qty"] > 0]

        if out_of_stock:
            lines.append("\n🔴 OUT OF STOCK:")
            for item in out_of_stock:
                lines.append(f"   • {item['name']} ({item['sku']})")

        if low:
            lines.append("\n🟡 LOW STOCK:")
            for item in low:
                lines.append(
                    f"   • {item['name']}: {item['qty']} left (threshold: {item['threshold']})"
                )

        if not out_of_stock and not low:
            lines.append("\n✅ All stock levels healthy!")

        # Incoming orders
        lines.append("\n📬 INCOMING STOCK:")
        for order in self.db.supplier_orders:
            days = (order.expected_date - datetime.now()).days
            status_emoji = "🚚" if order.status == "shipped" else "📝"
            lines.append(
                f"   {status_emoji} {order.supplier}: {len(order.items)} items in {days} days"
            )
            for item, qty in order.items[:3]:  # Show first 3
                lines.append(f"      • {item}: {qty}")

        return "\n".join(lines)

    async def _order_lookup(self, message: str) -> str:
        """Look up specific order."""
        import re

        match = re.search(r"#?(\d{4,})", message)

        if not match:
            # Show order status summary
            lines = [
                "📋 ORDER PIPELINE",
                "=" * 50,
            ]
            for status, count in self.db.orders_by_status.items():
                if count > 0:
                    emoji = {
                        OrderStatus.PENDING: "⏳",
                        OrderStatus.PAID: "💳",
                        OrderStatus.PICKING: "🛒",
                        OrderStatus.PACKING: "📦",
                        OrderStatus.SHIPPED: "🚚",
                        OrderStatus.FAILED: "❌",
                    }.get(status, "•")
                    lines.append(f"   {emoji} {status.value.title()}: {count}")

            lines.append("\nSay 'order #12345' for specific order.")
            return "\n".join(lines)

        order_id = match.group(1)
        order = self.db.get_order(order_id)

        if not order:
            return f"Order #{order_id} not found."

        status_emoji = {
            OrderStatus.SHIPPED: "🚚",
            OrderStatus.DELIVERED: "✅",
            OrderStatus.PACKING: "📦",
            OrderStatus.PICKING: "🛒",
        }.get(order["status"], "•")

        lines = [
            f"📋 ORDER #{order_id}",
            "=" * 50,
            f"Customer: {order['customer']}",
            f"Status: {status_emoji} {order['status'].value.title()}",
        ]

        if order.get("tracking"):
            lines.append(f"Tracking: {order['tracking']}")

        if order.get("shipped_date"):
            lines.append(f"Shipped: {order['shipped_date'].strftime('%Y-%m-%d')}")

        return "\n".join(lines)

    async def _supplier_status(self) -> str:
        """Show supplier order status."""
        lines = [
            "🏭 SUPPLIER ORDERS",
            "=" * 50,
        ]

        for order in self.db.supplier_orders:
            days = (order.expected_date - datetime.now()).days
            status_emoji = "🚚" if order.status == "shipped" else "📝"

            lines.append(f"\n{status_emoji} {order.supplier} - {order.order_number}")
            lines.append(f"   Status: {order.status.title()}")
            lines.append(
                f"   Arriving: {order.expected_date.strftime('%Y-%m-%d')} ({days} days)"
            )

            if order.tracking:
                lines.append(f"   Tracking: {order.tracking}")

            lines.append("   Items:")
            for item, qty in order.items:
                lines.append(f"      • {item}: {qty}")

        return "\n".join(lines)

    async def _top_customers(self) -> str:
        """Show top customers."""
        lines = [
            "👑 TOP CUSTOMERS (30 Days)",
            "=" * 50,
        ]

        for i, customer in enumerate(self.db.top_customers, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "

            lines.append(f"\n{medal} {customer['name']}")
            lines.append(f"   Orders: {customer['orders']}")
            lines.append(f"   Revenue: ${customer['revenue']:,.2f}")
            days_ago = (datetime.now() - customer["last_order"]).days
            lines.append(f"   Last order: {days_ago} days ago")

        return "\n".join(lines)

    async def _show_alerts(self) -> str:
        """Show active alerts."""
        lines = [
            "🔔 ACTIVE ALERTS",
            "=" * 50,
        ]

        # Group by priority
        for priority in [
            AlertPriority.CRITICAL,
            AlertPriority.HIGH,
            AlertPriority.MEDIUM,
            AlertPriority.LOW,
        ]:
            alerts = [a for a in self.db.alerts if a.priority == priority]
            if alerts:
                emoji = {
                    AlertPriority.CRITICAL: "🚨",
                    AlertPriority.HIGH: "🔴",
                    AlertPriority.MEDIUM: "🟡",
                    AlertPriority.LOW: "🟢",
                }[priority]

                lines.append(f"\n{emoji} {priority.value.upper()}:")
                for alert in alerts:
                    lines.append(f"   [{alert.category}] {alert.message}")

        return "\n".join(lines)

    def _help_message(self) -> str:
        """Return help text."""
        return """📊 Store Manager Dashboard

• "Morning briefing" - Full overview
• "Sales today" - Revenue and orders
• "Staff performance" - Team metrics
• "Stock status" - Inventory alerts
• "Order #12345" - Specific order
• "Supplier status" - Incoming orders
• "Top customers" - VIP list
• "Alerts" - Issues to address

Just ask naturally!"""


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    """Demo the store manager assistant."""
    print("=" * 60)
    print("📊 STORE MANAGER DASHBOARD")
    print("=" * 60)
    print()

    db = ManagerDB()
    assistant = StoreManagerAssistant(db)

    # Demo queries
    demo_messages = [
        "Morning briefing",
        "How did we do on sales?",
        "Who's the top picker?",
        "Any stock issues?",
        "Where's order #12345?",
    ]

    for message in demo_messages:
        print(f"👤 {message}")
        response = await assistant.process_message(message)
        print(f"🤖 {response}")
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())
