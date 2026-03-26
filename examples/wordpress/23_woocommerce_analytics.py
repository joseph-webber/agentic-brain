#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 23: WooCommerce Sales Analytics Assistant

A comprehensive analytics chatbot for business owners and managers to get
real-time insights into sales, revenue, customers, and product performance.

Use Cases:
- Daily/weekly/monthly sales reports
- Top-selling products analysis
- Customer insights and segments
- Revenue trends and forecasting
- Inventory turnover metrics
- Marketing campaign performance

This is a "kitchen sink" example showcasing many agentic-brain features:
- Natural language query processing
- Multi-format responses (text, charts, tables)
- Trend analysis and comparisons
- Actionable recommendations
- Export capabilities

Requirements:
- WooCommerce 3.5+ with REST API enabled
- WooCommerce Analytics enabled
- Consumer Key/Secret with read access
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import random


class TimePeriod(Enum):
    """Time periods for reporting."""

    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_QUARTER = "this_quarter"
    THIS_YEAR = "this_year"
    CUSTOM = "custom"


# Demo analytics data - Generic electronics store
DEMO_DAILY_SALES = [
    {
        "date": "2024-03-15",
        "orders": 12,
        "revenue": 1549.87,
        "items_sold": 28,
        "avg_order": 129.16,
    },
    {
        "date": "2024-03-14",
        "orders": 15,
        "revenue": 2105.45,
        "items_sold": 35,
        "avg_order": 140.36,
    },
    {
        "date": "2024-03-13",
        "orders": 9,
        "revenue": 892.30,
        "items_sold": 18,
        "avg_order": 99.14,
    },
    {
        "date": "2024-03-12",
        "orders": 18,
        "revenue": 2890.00,
        "items_sold": 42,
        "avg_order": 160.56,
    },
    {
        "date": "2024-03-11",
        "orders": 14,
        "revenue": 1756.25,
        "items_sold": 31,
        "avg_order": 125.45,
    },
    {
        "date": "2024-03-10",
        "orders": 8,
        "revenue": 645.90,
        "items_sold": 15,
        "avg_order": 80.74,
    },
    {
        "date": "2024-03-09",
        "orders": 6,
        "revenue": 489.50,
        "items_sold": 12,
        "avg_order": 81.58,
    },
]

DEMO_TOP_PRODUCTS = [
    {
        "id": 101,
        "name": "Ergonomic Keyboard Pro",
        "sku": "KB-ERGO1",
        "units_sold": 45,
        "revenue": 4049.55,
        "margin": 0.35,
    },
    {
        "id": 102,
        "name": "Wireless Mouse 500",
        "sku": "MS-WL500",
        "units_sold": 62,
        "revenue": 3099.38,
        "margin": 0.40,
    },
    {
        "id": 103,
        "name": "27-inch HD Monitor",
        "sku": "MON-27HD",
        "units_sold": 12,
        "revenue": 4799.88,
        "margin": 0.25,
    },
    {
        "id": 105,
        "name": "HDMI Cable 2m",
        "sku": "CBL-HDMI2",
        "units_sold": 89,
        "revenue": 1334.11,
        "margin": 0.55,
    },
    {
        "id": 104,
        "name": "USB Hub 4-Port",
        "sku": "USB-HUB4",
        "units_sold": 38,
        "revenue": 1139.62,
        "margin": 0.45,
    },
    {
        "id": 107,
        "name": "Webcam HD 1080p",
        "sku": "CAM-HD1080",
        "units_sold": 28,
        "revenue": 2239.72,
        "margin": 0.30,
    },
    {
        "id": 106,
        "name": "Laptop Stand Adjustable",
        "sku": "STD-LAP1",
        "units_sold": 15,
        "revenue": 899.85,
        "margin": 0.38,
    },
]

DEMO_CATEGORIES = [
    {"name": "Keyboards", "revenue": 5200.50, "units": 58, "growth": 12.5},
    {"name": "Mice", "revenue": 3850.25, "units": 77, "growth": 8.2},
    {"name": "Monitors", "revenue": 6800.00, "units": 17, "growth": -5.3},
    {"name": "Cables", "revenue": 2100.75, "units": 140, "growth": 25.8},
    {"name": "Accessories", "revenue": 3450.00, "units": 115, "growth": 15.4},
    {"name": "Cameras", "revenue": 2800.50, "units": 35, "growth": 45.2},
]

DEMO_CUSTOMERS = [
    {
        "id": 1,
        "name": "TechCorp Industries",
        "type": "business",
        "orders": 15,
        "total_spent": 4520.00,
        "last_order": "2024-03-14",
    },
    {
        "id": 2,
        "name": "Sarah Mitchell",
        "type": "individual",
        "orders": 8,
        "total_spent": 1890.50,
        "last_order": "2024-03-15",
    },
    {
        "id": 3,
        "name": "Digital Solutions Ltd",
        "type": "business",
        "orders": 22,
        "total_spent": 8750.25,
        "last_order": "2024-03-12",
    },
    {
        "id": 4,
        "name": "Home Office Supplies Co",
        "type": "business",
        "orders": 12,
        "total_spent": 3200.00,
        "last_order": "2024-03-10",
    },
    {
        "id": 5,
        "name": "John Peters",
        "type": "individual",
        "orders": 5,
        "total_spent": 650.75,
        "last_order": "2024-03-08",
    },
]

DEMO_CUSTOMER_SEGMENTS = [
    {"segment": "VIP", "count": 15, "revenue_share": 45.2, "avg_order": 285.50},
    {"segment": "Regular", "count": 85, "revenue_share": 38.5, "avg_order": 125.00},
    {"segment": "New", "count": 120, "revenue_share": 12.3, "avg_order": 75.50},
    {"segment": "At Risk", "count": 45, "revenue_share": 4.0, "avg_order": 95.00},
]

DEMO_MONTHLY_TRENDS = [
    {"month": "2024-01", "revenue": 28500.00, "orders": 185, "new_customers": 42},
    {"month": "2024-02", "revenue": 32100.00, "orders": 210, "new_customers": 55},
    {"month": "2024-03", "revenue": 35800.00, "orders": 245, "new_customers": 68},
]

DEMO_CONVERSION_STATS = {
    "visitors": 12500,
    "add_to_cart": 2100,
    "checkout_started": 850,
    "orders_completed": 680,
    "cart_rate": 16.8,
    "checkout_rate": 40.5,
    "conversion_rate": 5.44,
    "abandoned_carts": 170,
    "abandoned_value": 8500.00,
}


@dataclass
class SalesMetrics:
    """Sales metrics for a period."""

    period: str
    revenue: float
    orders: int
    items_sold: int
    avg_order_value: float

    @property
    def formatted_revenue(self) -> str:
        return f"${self.revenue:,.2f}"

    @property
    def formatted_aov(self) -> str:
        return f"${self.avg_order_value:.2f}"


class AnalyticsClient:
    """Client for WooCommerce analytics."""

    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode

    async def get_sales_summary(self, period: str = "this_month") -> dict:
        """Get sales summary for a period."""
        if self.demo_mode:
            # Aggregate demo data
            total_revenue = sum(d["revenue"] for d in DEMO_DAILY_SALES)
            total_orders = sum(d["orders"] for d in DEMO_DAILY_SALES)
            total_items = sum(d["items_sold"] for d in DEMO_DAILY_SALES)

            # Compare to previous period (simulated)
            prev_revenue = total_revenue * 0.88
            growth = ((total_revenue - prev_revenue) / prev_revenue) * 100

            return {
                "period": period,
                "revenue": total_revenue,
                "orders": total_orders,
                "items_sold": total_items,
                "avg_order_value": (
                    total_revenue / total_orders if total_orders > 0 else 0
                ),
                "previous_revenue": prev_revenue,
                "growth_percent": growth,
                "top_day": max(DEMO_DAILY_SALES, key=lambda x: x["revenue"]),
            }
        return {}

    async def get_daily_sales(self, days: int = 7) -> list[dict]:
        """Get daily sales breakdown."""
        if self.demo_mode:
            return DEMO_DAILY_SALES[:days]
        return []

    async def get_top_products(
        self, limit: int = 10, sort_by: str = "revenue"
    ) -> list[dict]:
        """Get top-selling products."""
        if self.demo_mode:
            products = DEMO_TOP_PRODUCTS.copy()
            if sort_by == "units":
                products.sort(key=lambda x: x["units_sold"], reverse=True)
            else:
                products.sort(key=lambda x: x["revenue"], reverse=True)
            return products[:limit]
        return []

    async def get_category_performance(self) -> list[dict]:
        """Get category performance metrics."""
        if self.demo_mode:
            return DEMO_CATEGORIES
        return []

    async def get_customer_insights(self) -> dict:
        """Get customer analytics."""
        if self.demo_mode:
            total_customers = sum(s["count"] for s in DEMO_CUSTOMER_SEGMENTS)
            return {
                "total_customers": total_customers,
                "new_this_month": 68,
                "returning_rate": 42.5,
                "segments": DEMO_CUSTOMER_SEGMENTS,
                "top_customers": DEMO_CUSTOMERS[:5],
                "avg_lifetime_value": 285.50,
            }
        return {}

    async def get_conversion_funnel(self) -> dict:
        """Get conversion funnel stats."""
        if self.demo_mode:
            return DEMO_CONVERSION_STATS
        return {}

    async def get_monthly_trends(self, months: int = 6) -> list[dict]:
        """Get monthly trend data."""
        if self.demo_mode:
            return DEMO_MONTHLY_TRENDS
        return []

    async def get_revenue_by_hour(self) -> list[dict]:
        """Get revenue breakdown by hour of day."""
        if self.demo_mode:
            # Simulate hourly distribution
            hours = []
            peak_hours = [10, 11, 14, 15, 20, 21]
            for hour in range(24):
                base = random.uniform(50, 150)
                if hour in peak_hours:
                    base *= 2.5
                elif hour < 6 or hour > 22:
                    base *= 0.3
                hours.append(
                    {"hour": hour, "revenue": round(base, 2), "orders": int(base / 50)}
                )
            return hours
        return []

    async def get_product_performance(self, sku: str) -> Optional[dict]:
        """Get detailed performance for a specific product."""
        if self.demo_mode:
            for p in DEMO_TOP_PRODUCTS:
                if p["sku"].upper() == sku.upper():
                    return {
                        **p,
                        "views": random.randint(500, 2000),
                        "conversion_rate": round(random.uniform(2.5, 8.5), 2),
                        "refund_rate": round(random.uniform(0.5, 3.0), 2),
                        "avg_rating": round(random.uniform(4.0, 5.0), 1),
                        "review_count": random.randint(10, 100),
                        "trend": random.choice(["up", "stable", "down"]),
                    }
            return None
        return None

    async def get_comparison(self, period1: str, period2: str) -> dict:
        """Compare two time periods."""
        if self.demo_mode:
            return {
                "period1": {"name": period1, "revenue": 10329.27, "orders": 82},
                "period2": {"name": period2, "revenue": 8956.45, "orders": 71},
                "revenue_change": 15.3,
                "orders_change": 15.5,
                "aov_change": -0.2,
            }
        return {}


class AnalyticsAssistant:
    """
    AI assistant for WooCommerce sales analytics.

    This is a comprehensive "kitchen sink" example showcasing:
    - Natural language date parsing
    - Multiple report types
    - Trend analysis
    - Comparisons
    - Actionable insights
    - Export suggestions

    Capabilities:
    - Sales summaries and breakdowns
    - Product performance analysis
    - Customer insights
    - Conversion funnel analysis
    - Trend identification
    - Recommendations
    """

    def __init__(self, demo_mode: bool = True):
        self.client = AnalyticsClient(demo_mode=demo_mode)
        self.conversation_history: list[dict] = []
        self.last_report_data: dict = {}

    async def process_message(self, user_message: str) -> str:
        """Process an analytics query and return insights."""
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
            for word in ["summary", "overview", "dashboard", "how are we doing"]
        ):
            response = await self._handle_sales_summary()
        elif any(word in message_lower for word in ["today", "yesterday", "daily"]):
            response = await self._handle_daily_report(message_lower)
        elif any(
            word in message_lower
            for word in ["top product", "best seller", "selling well"]
        ):
            response = await self._handle_top_products(message_lower)
        elif any(word in message_lower for word in ["category", "categories"]):
            response = await self._handle_category_analysis()
        elif any(word in message_lower for word in ["customer", "buyer", "client"]):
            response = await self._handle_customer_insights()
        elif any(
            word in message_lower
            for word in ["conversion", "funnel", "cart", "checkout"]
        ):
            response = await self._handle_conversion_funnel()
        elif any(
            word in message_lower
            for word in ["trend", "growth", "compare", "vs", "versus"]
        ):
            response = await self._handle_trends()
        elif any(
            word in message_lower for word in ["revenue", "sales", "money", "income"]
        ):
            response = await self._handle_revenue_analysis()
        elif any(
            word in message_lower
            for word in ["recommend", "suggest", "improve", "tips"]
        ):
            response = await self._handle_recommendations()
        elif any(word in message_lower for word in ["export", "download", "report"]):
            response = await self._handle_export()
        elif any(word in message_lower for word in ["product"]) and any(
            w in message_lower for w in ["performance", "how is", "analyze"]
        ):
            response = await self._handle_product_performance(user_message)
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

    async def _handle_sales_summary(self) -> str:
        """Generate comprehensive sales summary."""
        summary = await self.client.get_sales_summary()
        self.last_report_data = summary

        growth_emoji = "📈" if summary["growth_percent"] > 0 else "📉"
        growth_sign = "+" if summary["growth_percent"] > 0 else ""

        lines = [
            "📊 **Sales Dashboard**",
            f"Period: This Month (as of {datetime.now().strftime('%B %d, %Y')})",
            "",
            "═══════════════════════════════════════",
            "",
            f"💰 **Revenue:** ${summary['revenue']:,.2f}",
            f"   {growth_emoji} {growth_sign}{summary['growth_percent']:.1f}% vs last period",
            "",
            f"🛒 **Orders:** {summary['orders']}",
            f"📦 **Items Sold:** {summary['items_sold']}",
            f"💵 **Avg Order Value:** ${summary['avg_order_value']:.2f}",
            "",
            "═══════════════════════════════════════",
            "",
            f"🏆 **Best Day:** {summary['top_day']['date']}",
            f"   ${summary['top_day']['revenue']:,.2f} ({summary['top_day']['orders']} orders)",
            "",
            "**Quick Actions:**",
            "• Say 'top products' for best sellers",
            "• Say 'customer insights' for buyer analysis",
            "• Say 'recommendations' for growth tips",
        ]

        return "\n".join(lines)

    async def _handle_daily_report(self, message: str) -> str:
        """Generate daily sales report."""
        daily_sales = await self.client.get_daily_sales(7)

        lines = [
            "📅 **Daily Sales (Last 7 Days)**",
            "",
            "```",
            "Date        │ Orders │ Revenue    │ Items │ AOV",
            "────────────┼────────┼────────────┼───────┼────────",
        ]

        for day in daily_sales:
            lines.append(
                f"{day['date']} │ {day['orders']:6} │ ${day['revenue']:8,.2f} │ {day['items_sold']:5} │ ${day['avg_order']:.2f}"
            )

        lines.append("```")

        # Add insights
        total_revenue = sum(d["revenue"] for d in daily_sales)
        avg_daily = total_revenue / len(daily_sales)
        best_day = max(daily_sales, key=lambda x: x["revenue"])
        worst_day = min(daily_sales, key=lambda x: x["revenue"])

        lines.extend(
            [
                "",
                "**Insights:**",
                f"• Average daily revenue: ${avg_daily:,.2f}",
                f"• Best day: {best_day['date']} (${best_day['revenue']:,.2f})",
                f"• Slowest day: {worst_day['date']} (${worst_day['revenue']:,.2f})",
            ]
        )

        # Weekend analysis
        lines.append("• 📊 Weekends show lower traffic - consider promotions")

        return "\n".join(lines)

    async def _handle_top_products(self, message: str) -> str:
        """Show top-selling products."""
        sort_by = "units" if "unit" in message or "quantity" in message else "revenue"
        products = await self.client.get_top_products(limit=7, sort_by=sort_by)

        sort_label = "Units Sold" if sort_by == "units" else "Revenue"
        lines = [
            f"🏆 **Top Products by {sort_label}**",
            "",
        ]

        for i, p in enumerate(products, 1):
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
            margin_pct = p["margin"] * 100

            lines.append(f"{medal} **{p['name']}** ({p['sku']})")
            lines.append(
                f"   📦 {p['units_sold']} units │ 💰 ${p['revenue']:,.2f} │ 📊 {margin_pct:.0f}% margin"
            )

        # Calculate totals
        total_units = sum(p["units_sold"] for p in products)
        total_revenue = sum(p["revenue"] for p in products)

        lines.extend(
            [
                "",
                "═══════════════════════════════════════",
                f"**Total:** {total_units} units │ ${total_revenue:,.2f}",
                "",
                "💡 **Tip:** Your top 3 products drive 65% of revenue. Consider bundling!",
            ]
        )

        return "\n".join(lines)

    async def _handle_category_analysis(self) -> str:
        """Analyze category performance."""
        categories = await self.client.get_category_performance()

        lines = [
            "📁 **Category Performance**",
            "",
            "```",
            "Category     │ Revenue    │ Units │ Growth",
            "─────────────┼────────────┼───────┼────────",
        ]

        for cat in sorted(categories, key=lambda x: x["revenue"], reverse=True):
            growth_icon = "↑" if cat["growth"] > 0 else "↓"
            lines.append(
                f"{cat['name']:<12} │ ${cat['revenue']:>8,.2f} │ {cat['units']:>5} │ {growth_icon}{abs(cat['growth']):>5.1f}%"
            )

        lines.append("```")

        # Insights
        growing = [c for c in categories if c["growth"] > 10]
        declining = [c for c in categories if c["growth"] < 0]

        lines.extend(
            [
                "",
                "**Insights:**",
            ]
        )

        if growing:
            lines.append(f"• 📈 Fast growing: {', '.join(c['name'] for c in growing)}")
        if declining:
            lines.append(
                f"• 📉 Needs attention: {', '.join(c['name'] for c in declining)}"
            )

        # Top performer
        top = max(categories, key=lambda x: x["revenue"])
        lines.append(f"• 🏆 Top performer: {top['name']} (${top['revenue']:,.2f})")

        return "\n".join(lines)

    async def _handle_customer_insights(self) -> str:
        """Generate customer analytics."""
        insights = await self.client.get_customer_insights()

        lines = [
            "👥 **Customer Insights**",
            "",
            f"**Total Customers:** {insights['total_customers']}",
            f"**New This Month:** {insights['new_this_month']} 🆕",
            f"**Returning Rate:** {insights['returning_rate']}%",
            f"**Avg Lifetime Value:** ${insights['avg_lifetime_value']:.2f}",
            "",
            "**Customer Segments:**",
            "",
            "```",
            "Segment   │ Count │ Revenue % │ Avg Order",
            "──────────┼───────┼───────────┼──────────",
        ]

        for seg in insights["segments"]:
            lines.append(
                f"{seg['segment']:<9} │ {seg['count']:>5} │ {seg['revenue_share']:>8.1f}% │ ${seg['avg_order']:>7.2f}"
            )

        lines.append("```")

        lines.extend(
            [
                "",
                "**🏆 Top Customers:**",
            ]
        )

        for c in insights["top_customers"][:3]:
            lines.append(
                f"  • {c['name']}: ${c['total_spent']:,.2f} ({c['orders']} orders)"
            )

        lines.extend(
            [
                "",
                "💡 **Recommendations:**",
                "• VIP segment (15 customers) drives 45% of revenue - nurture them!",
                "• 45 at-risk customers haven't ordered in 60+ days - send win-back campaign",
                "• New customer conversion is strong - maintain acquisition efforts",
            ]
        )

        return "\n".join(lines)

    async def _handle_conversion_funnel(self) -> str:
        """Analyze conversion funnel."""
        funnel = await self.client.get_conversion_funnel()

        lines = [
            "🔄 **Conversion Funnel**",
            "",
            "```",
            f"Visitors        │ {funnel['visitors']:,}     │ 100%",
            "       ↓",
            f"Add to Cart     │ {funnel['add_to_cart']:,}      │ {funnel['cart_rate']:.1f}%",
            "       ↓",
            f"Checkout Start  │ {funnel['checkout_started']:,}        │ {funnel['checkout_rate']:.1f}%",
            "       ↓",
            f"Orders Complete │ {funnel['orders_completed']:,}        │ {funnel['conversion_rate']:.2f}%",
            "```",
            "",
            f"⚠️ **Abandoned Carts:** {funnel['abandoned_carts']}",
            f"💸 **Lost Revenue:** ${funnel['abandoned_value']:,.2f}",
            "",
            "**Where Customers Drop Off:**",
            f"• Cart → Checkout: {100 - funnel['checkout_rate']:.1f}% drop",
            f"• Checkout → Purchase: {100 - (funnel['orders_completed']/funnel['checkout_started']*100):.1f}% drop",
            "",
            "💡 **Improvement Tips:**",
            "• Add exit-intent popup for cart abandoners",
            "• Simplify checkout to 1-2 steps",
            "• Send abandoned cart emails within 1 hour",
            "• Offer free shipping threshold messaging",
        ]

        return "\n".join(lines)

    async def _handle_trends(self) -> str:
        """Analyze trends and comparisons."""
        trends = await self.client.get_monthly_trends()
        comparison = await self.client.get_comparison("This Month", "Last Month")

        lines = [
            "📈 **Growth Trends**",
            "",
            "**Monthly Performance:**",
            "",
            "```",
            "Month    │ Revenue    │ Orders │ New Customers",
            "─────────┼────────────┼────────┼──────────────",
        ]

        for t in trends:
            lines.append(
                f"{t['month']} │ ${t['revenue']:>9,.2f} │ {t['orders']:>6} │ {t['new_customers']:>12}"
            )

        lines.append("```")

        # Month-over-month comparison
        growth = comparison["revenue_change"]
        growth_emoji = "📈" if growth > 0 else "📉"
        growth_sign = "+" if growth > 0 else ""

        lines.extend(
            [
                "",
                "**This Month vs Last Month:**",
                f"  {growth_emoji} Revenue: {growth_sign}{growth:.1f}%",
                f"  📦 Orders: {'+' if comparison['orders_change'] > 0 else ''}{comparison['orders_change']:.1f}%",
                "",
                "**Trend Analysis:**",
            ]
        )

        # Calculate MoM growth
        if len(trends) >= 2:
            recent_growth = (
                (trends[-1]["revenue"] - trends[-2]["revenue"]) / trends[-2]["revenue"]
            ) * 100
            if recent_growth > 10:
                lines.append("• 🚀 Strong growth trajectory - you're on fire!")
            elif recent_growth > 0:
                lines.append("• 📈 Steady growth - keep up the momentum")
            else:
                lines.append("• ⚠️ Slight decline - review marketing and pricing")

        lines.extend(
            [
                "",
                "**Forecast:**",
                f"• Projected March revenue: ${trends[-1]['revenue'] * 1.12:,.2f}",
                "• Expected Q2 growth: 15-20% if trends continue",
            ]
        )

        return "\n".join(lines)

    async def _handle_revenue_analysis(self) -> str:
        """Detailed revenue analysis."""
        summary = await self.client.get_sales_summary()
        hourly = await self.client.get_revenue_by_hour()

        lines = [
            "💰 **Revenue Analysis**",
            "",
            f"**Total Revenue (MTD):** ${summary['revenue']:,.2f}",
            f"**Daily Average:** ${summary['revenue'] / 15:,.2f}",  # Assuming mid-month
            f"**Projected Month-End:** ${summary['revenue'] * 2:,.2f}",
            "",
            "**Revenue by Time of Day:**",
            "",
        ]

        # Find peak hours
        peak_hours = sorted(hourly, key=lambda x: x["revenue"], reverse=True)[:5]

        lines.append("🕐 **Peak Hours:**")
        for h in peak_hours:
            hour_str = f"{h['hour']:02d}:00"
            lines.append(f"  • {hour_str}: ${h['revenue']:,.2f} ({h['orders']} orders)")

        lines.extend(
            [
                "",
                "**Revenue Breakdown:**",
                "  • Product Sales: 92%",
                "  • Shipping Fees: 6%",
                "  • Tax Collected: 2%",
                "",
                "💡 **Optimization Tips:**",
                "• Peak hours are 10-11 AM and 8-9 PM - schedule promotions accordingly",
                "• Morning traffic converts better - focus ads on AM hours",
                "• Evening browsers may need nurturing - send follow-up emails",
            ]
        )

        return "\n".join(lines)

    async def _handle_recommendations(self) -> str:
        """Generate actionable recommendations."""
        summary = await self.client.get_sales_summary()
        categories = await self.client.get_category_performance()
        funnel = await self.client.get_conversion_funnel()

        lines = [
            "💡 **Growth Recommendations**",
            "",
            "Based on your data, here are prioritized actions:",
            "",
            "**🚨 HIGH PRIORITY:**",
            "",
            f"1. **Recover Abandoned Carts** (Potential: ${funnel['abandoned_value']:,.2f})",
            "   • Set up automated email sequence (1hr, 24hr, 72hr)",
            "   • Add exit-intent popup with discount",
            "   • Expected recovery: 10-15% = ~$850-1,275",
            "",
        ]

        # Category recommendations
        declining = [c for c in categories if c["growth"] < 0]
        if declining:
            lines.extend(
                [
                    f"2. **Revive {declining[0]['name']} Category** (Down {abs(declining[0]['growth']):.1f}%)",
                    "   • Bundle with popular items",
                    "   • Run flash sale or clearance",
                    "   • Update product photos and descriptions",
                    "",
                ]
            )

        growing = max(categories, key=lambda x: x["growth"])
        lines.extend(
            [
                f"3. **Double Down on {growing['name']}** (Growing {growing['growth']:.1f}%)",
                "   • Increase ad spend on this category",
                "   • Add complementary products",
                "   • Create category-specific landing page",
                "",
                "**📈 GROWTH OPPORTUNITIES:**",
                "",
                "4. **Increase Average Order Value** (Current: ${:.2f})".format(
                    summary["avg_order_value"]
                ),
                "   • Add 'Frequently Bought Together' section",
                "   • Free shipping threshold: $99",
                "   • Volume discounts: Buy 2+ save 10%",
                "",
                "5. **Improve Conversion Rate** (Current: {:.2f}%)".format(
                    funnel["conversion_rate"]
                ),
                "   • Add trust badges to checkout",
                "   • Guest checkout option",
                "   • Multiple payment methods",
                "",
                "**📊 QUICK WINS:**",
                "",
                "• Send 'We Miss You' email to 45 at-risk customers",
                "• Thank top 15 VIP customers with exclusive preview",
                "• Post customer reviews on social media",
                "",
                "**Estimated Impact:** +15-25% revenue growth in 30 days",
            ]
        )

        return "\n".join(lines)

    async def _handle_export(self) -> str:
        """Handle export requests."""
        return """📥 **Export Reports**

Available exports:
• **Sales Report** - Daily/weekly/monthly sales data
• **Product Report** - All products with metrics
• **Customer Report** - Customer list with lifetime value
• **Order Report** - Detailed order history

**Format Options:**
• CSV (Excel compatible)
• PDF (formatted report)
• JSON (for integrations)

**To export:**
Go to WooCommerce → Reports → Export

Or I can generate a summary you can copy:
• Say "export sales CSV" for sales data
• Say "export customers" for customer list

**API Access:**
```
GET /wp-json/wc/v3/reports/sales?period=month
```

Need a custom report? Let me know what data you need!"""

    async def _handle_product_performance(self, message: str) -> str:
        """Analyze specific product performance."""
        import re

        sku_match = re.search(r"([A-Z]{2,}-[A-Z0-9]+)", message.upper())

        if sku_match:
            sku = sku_match.group(1)
            perf = await self.client.get_product_performance(sku)

            if perf:
                trend_emoji = {"up": "📈", "stable": "➡️", "down": "📉"}[perf["trend"]]

                lines = [
                    f"📊 **Product Analysis: {perf['name']}**",
                    f"SKU: {perf['sku']}",
                    "",
                    "**Sales Performance:**",
                    f"  • Units Sold: {perf['units_sold']}",
                    f"  • Revenue: ${perf['revenue']:,.2f}",
                    f"  • Margin: {perf['margin']*100:.0f}%",
                    f"  • Trend: {trend_emoji} {perf['trend'].title()}",
                    "",
                    "**Conversion Metrics:**",
                    f"  • Page Views: {perf['views']:,}",
                    f"  • Conversion Rate: {perf['conversion_rate']}%",
                    f"  • Refund Rate: {perf['refund_rate']}%",
                    "",
                    "**Customer Feedback:**",
                    f"  ⭐ {perf['avg_rating']}/5 ({perf['review_count']} reviews)",
                ]

                return "\n".join(lines)

        # No SKU - show all products
        return await self._handle_top_products(message)

    async def _handle_general(self, message: str) -> str:
        """Handle general queries."""
        return f"""I can help with sales analytics! Here's what I can do:

{self._get_help()}

What would you like to know?"""

    def _get_help(self) -> str:
        """Return help text."""
        return """📊 **Analytics Assistant Commands**

**Sales Reports:**
- "Sales summary" - Dashboard overview
- "Daily sales" - Last 7 days breakdown
- "Revenue analysis" - Detailed revenue insights

**Products:**
- "Top products" - Best sellers by revenue
- "Top products by units" - Best sellers by quantity
- "Analyze product KB-ERGO1" - Specific product

**Customers:**
- "Customer insights" - Buyer analytics
- "Top customers" - VIP list

**Conversion:**
- "Conversion funnel" - Visitor → Purchase flow
- "Abandoned carts" - Recovery opportunities

**Trends:**
- "Show trends" - Growth over time
- "Compare this month vs last month"

**Growth:**
- "Recommendations" - Actionable tips
- "How to improve sales"

**Export:**
- "Export report" - Download options

Just ask naturally - I understand context!"""


async def demo():
    """Run comprehensive demo."""
    print("=" * 60)
    print("WooCommerce Sales Analytics Assistant")
    print("=" * 60)
    print("\nRunning in DEMO MODE - Showcasing all features\n")

    assistant = AnalyticsAssistant(demo_mode=True)

    # Demo all major features
    demo_queries = [
        "Sales summary",
        "Show daily sales",
        "Top products",
        "Category performance",
        "Customer insights",
        "Conversion funnel",
        "Give me recommendations",
    ]

    for query in demo_queries:
        print(f"👤 Manager: {query}")
        print("-" * 50)
        response = await assistant.process_message(query)
        print(f"🤖 Assistant:\n{response}")
        print("=" * 60)
        print()
        await asyncio.sleep(0.5)


async def interactive():
    """Run interactive mode."""
    print("=" * 60)
    print("WooCommerce Sales Analytics Assistant")
    print("=" * 60)
    print("\nType 'quit' to exit, 'help' for commands\n")

    assistant = AnalyticsAssistant(demo_mode=True)

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
