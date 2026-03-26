#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 21: WooCommerce Customer Service Assistant

A chatbot for handling customer inquiries about orders, products, and support.
Integrates with WooCommerce REST API for real-time order and product data.

Use Cases:
- Customer order status inquiries
- Product availability checks
- Return and refund requests
- Shipping information
- Product recommendations

Requirements:
- WooCommerce 3.5+ with REST API enabled
- Consumer Key/Secret with read access
- HTTPS enabled on the store
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class OrderStatus(Enum):
    """WooCommerce order statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    ON_HOLD = "on-hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"
    SHIPPED = "shipped"


# Demo data - Office supplies and electronics store
DEMO_ORDERS = [
    {
        "id": 1001,
        "number": "1001",
        "status": "completed",
        "date_created": "2024-03-10T14:30:00",
        "total": "149.99",
        "customer_id": 5,
        "billing": {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@example.com",
        },
        "shipping": {
            "first_name": "John",
            "last_name": "Smith",
            "address_1": "123 Main St",
            "city": "Adelaide",
            "state": "SA",
            "postcode": "5000",
        },
        "line_items": [
            {
                "name": "Ergonomic Keyboard Pro",
                "quantity": 1,
                "total": "89.99",
                "sku": "KB-ERGO1",
            },
            {
                "name": "Wireless Mouse 500",
                "quantity": 1,
                "total": "49.99",
                "sku": "MS-WL500",
            },
        ],
        "shipping_lines": [{"method_title": "Express Shipping", "total": "10.00"}],
        "tracking_number": "AUS123456789",
        "tracking_url": "https://auspost.com.au/track/AUS123456789",
    },
    {
        "id": 1002,
        "number": "1002",
        "status": "processing",
        "date_created": "2024-03-14T09:15:00",
        "total": "459.99",
        "customer_id": 12,
        "billing": {
            "first_name": "Sarah",
            "last_name": "Jones",
            "email": "sarah@example.com",
        },
        "shipping": {
            "first_name": "Sarah",
            "last_name": "Jones",
            "address_1": "456 Oak Ave",
            "city": "Melbourne",
            "state": "VIC",
            "postcode": "3000",
        },
        "line_items": [
            {
                "name": "27-inch HD Monitor",
                "quantity": 1,
                "total": "399.99",
                "sku": "MON-27HD",
            },
            {
                "name": "HDMI Cable 2m",
                "quantity": 2,
                "total": "29.99",
                "sku": "CBL-HDMI2",
            },
        ],
        "shipping_lines": [{"method_title": "Standard Shipping", "total": "0.00"}],
    },
    {
        "id": 1003,
        "number": "1003",
        "status": "on-hold",
        "date_created": "2024-03-15T16:45:00",
        "total": "89.97",
        "customer_id": 5,
        "billing": {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@example.com",
        },
        "line_items": [
            {
                "name": "USB Hub 4-Port",
                "quantity": 3,
                "total": "89.97",
                "sku": "USB-HUB4",
            },
        ],
        "shipping_lines": [{"method_title": "Standard Shipping", "total": "0.00"}],
        "hold_reason": "Payment verification required",
    },
]

DEMO_PRODUCTS = [
    {
        "id": 101,
        "name": "Ergonomic Keyboard Pro",
        "sku": "KB-ERGO1",
        "price": "89.99",
        "regular_price": "99.99",
        "stock_status": "instock",
        "stock_quantity": 45,
        "categories": [{"name": "Keyboards"}],
        "description": "Premium ergonomic keyboard with split design and palm rest.",
    },
    {
        "id": 102,
        "name": "Wireless Mouse 500",
        "sku": "MS-WL500",
        "price": "49.99",
        "regular_price": "49.99",
        "stock_status": "instock",
        "stock_quantity": 120,
        "categories": [{"name": "Mice"}],
        "description": "Precision wireless mouse with 6 programmable buttons.",
    },
    {
        "id": 103,
        "name": "27-inch HD Monitor",
        "sku": "MON-27HD",
        "price": "399.99",
        "regular_price": "449.99",
        "stock_status": "instock",
        "stock_quantity": 15,
        "categories": [{"name": "Monitors"}],
        "description": "27-inch Full HD IPS display with adjustable stand.",
    },
    {
        "id": 104,
        "name": "USB Hub 4-Port",
        "sku": "USB-HUB4",
        "price": "29.99",
        "regular_price": "29.99",
        "stock_status": "lowstock",
        "stock_quantity": 8,
        "categories": [{"name": "Accessories"}],
        "description": "Compact 4-port USB 3.0 hub with LED indicators.",
    },
    {
        "id": 105,
        "name": "HDMI Cable 2m",
        "sku": "CBL-HDMI2",
        "price": "14.99",
        "regular_price": "14.99",
        "stock_status": "instock",
        "stock_quantity": 200,
        "categories": [{"name": "Cables"}],
        "description": "High-speed HDMI 2.1 cable, 2 meters.",
    },
    {
        "id": 106,
        "name": "Laptop Stand Adjustable",
        "sku": "STD-LAP1",
        "price": "59.99",
        "regular_price": "69.99",
        "stock_status": "outofstock",
        "stock_quantity": 0,
        "categories": [{"name": "Stands"}],
        "description": "Aluminum laptop stand with height adjustment.",
        "backorder_date": "2024-03-25",
    },
]

DEMO_CUSTOMERS = [
    {
        "id": 5,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Smith",
        "orders_count": 5,
        "total_spent": "892.45",
    },
    {
        "id": 12,
        "email": "sarah@example.com",
        "first_name": "Sarah",
        "last_name": "Jones",
        "orders_count": 2,
        "total_spent": "459.99",
    },
]


@dataclass
class WooCommerceConfig:
    """WooCommerce API configuration."""

    site_url: str = "https://demo-store.local"
    consumer_key: str = "ck_xxxxxxxxxxxxxxxx"
    consumer_secret: str = "cs_xxxxxxxxxxxxxxxx"
    version: str = "wc/v3"
    timeout: int = 30


@dataclass
class Order:
    """Order representation."""

    id: int
    number: str
    status: str
    total: str
    date_created: datetime
    customer_name: str
    customer_email: str
    items: list[dict]
    shipping_address: dict
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "Order":
        """Create Order from WooCommerce API response."""
        billing = data.get("billing", {})
        shipping = data.get("shipping", {})

        return cls(
            id=data["id"],
            number=data.get("number", str(data["id"])),
            status=data["status"],
            total=data["total"],
            date_created=datetime.fromisoformat(
                data["date_created"].replace("Z", "+00:00")
            ),
            customer_name=f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
            customer_email=billing.get("email", ""),
            items=data.get("line_items", []),
            shipping_address=shipping,
            tracking_number=data.get("tracking_number"),
            tracking_url=data.get("tracking_url"),
        )


@dataclass
class Product:
    """Product representation."""

    id: int
    name: str
    sku: str
    price: str
    regular_price: str
    stock_status: str
    stock_quantity: int
    categories: list[str]
    description: str

    @classmethod
    def from_api(cls, data: dict) -> "Product":
        """Create Product from WooCommerce API response."""
        return cls(
            id=data["id"],
            name=data["name"],
            sku=data.get("sku", ""),
            price=data["price"],
            regular_price=data.get("regular_price", data["price"]),
            stock_status=data.get("stock_status", "instock"),
            stock_quantity=data.get("stock_quantity", 0) or 0,
            categories=[c["name"] for c in data.get("categories", [])],
            description=data.get("description", ""),
        )

    @property
    def is_on_sale(self) -> bool:
        """Check if product is on sale."""
        try:
            return float(self.price) < float(self.regular_price)
        except (ValueError, TypeError):
            return False

    @property
    def discount_percent(self) -> int:
        """Calculate discount percentage."""
        if not self.is_on_sale:
            return 0
        try:
            regular = float(self.regular_price)
            sale = float(self.price)
            return int((1 - sale / regular) * 100)
        except (ValueError, TypeError, ZeroDivisionError):
            return 0


class WooCommerceClient:
    """Async client for WooCommerce REST API."""

    def __init__(self, config: WooCommerceConfig, demo_mode: bool = True):
        self.config = config
        self.demo_mode = demo_mode
        self.base_url = f"{config.site_url}/wp-json/{config.version}"

    async def get_order(self, order_id: int) -> Optional[Order]:
        """Fetch a single order by ID."""
        if self.demo_mode:
            for o in DEMO_ORDERS:
                if o["id"] == order_id or o["number"] == str(order_id):
                    return Order.from_api(o)
            return None

        # Real API call would go here
        return None

    async def get_orders_by_email(self, email: str) -> list[Order]:
        """Fetch orders for a customer email."""
        if self.demo_mode:
            orders = []
            for o in DEMO_ORDERS:
                if o["billing"]["email"].lower() == email.lower():
                    orders.append(Order.from_api(o))
            return orders

        return []

    async def get_product(
        self, product_id: int = None, sku: str = None
    ) -> Optional[Product]:
        """Fetch a product by ID or SKU."""
        if self.demo_mode:
            for p in DEMO_PRODUCTS:
                if product_id and p["id"] == product_id:
                    return Product.from_api(p)
                if sku and p["sku"].lower() == sku.lower():
                    return Product.from_api(p)
            return None

        return None

    async def search_products(self, query: str) -> list[Product]:
        """Search products by name."""
        if self.demo_mode:
            query_lower = query.lower()
            results = []
            for p in DEMO_PRODUCTS:
                if (
                    query_lower in p["name"].lower()
                    or query_lower in p.get("sku", "").lower()
                ):
                    results.append(Product.from_api(p))
            return results

        return []

    async def get_products_in_stock(self) -> list[Product]:
        """Get all in-stock products."""
        if self.demo_mode:
            return [
                Product.from_api(p)
                for p in DEMO_PRODUCTS
                if p["stock_status"] in ("instock", "lowstock")
            ]

        return []

    async def get_products_on_sale(self) -> list[Product]:
        """Get products currently on sale."""
        if self.demo_mode:
            results = []
            for p in DEMO_PRODUCTS:
                product = Product.from_api(p)
                if product.is_on_sale:
                    results.append(product)
            return results

        return []

    async def create_refund_request(self, order_id: int, reason: str) -> dict:
        """Create a refund request for an order."""
        if self.demo_mode:
            return {
                "success": True,
                "refund_id": 5001,
                "order_id": order_id,
                "status": "pending",
                "message": f"Refund request created for order #{order_id}. Our team will review within 24 hours.",
            }

        return {"success": False, "error": "Not implemented"}


class CustomerServiceAssistant:
    """
    AI assistant for WooCommerce customer service.

    Capabilities:
    - Order status lookup
    - Product availability checks
    - Refund/return requests
    - Shipping information
    - Product recommendations
    """

    def __init__(
        self, config: Optional[WooCommerceConfig] = None, demo_mode: bool = True
    ):
        self.config = config or WooCommerceConfig()
        self.client = WooCommerceClient(self.config, demo_mode=demo_mode)
        self.conversation_history: list[dict] = []
        self.customer_context: dict = {}

    async def process_message(self, user_message: str) -> str:
        """Process a customer message and return a response."""
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
        if any(word in message_lower for word in ["order", "status", "where", "track"]):
            response = await self._handle_order_inquiry(user_message)
        elif any(word in message_lower for word in ["refund", "return", "money back"]):
            response = await self._handle_refund_request(user_message)
        elif any(
            word in message_lower for word in ["product", "available", "stock", "have"]
        ):
            response = await self._handle_product_inquiry(user_message)
        elif any(word in message_lower for word in ["shipping", "delivery", "arrive"]):
            response = await self._handle_shipping_inquiry(user_message)
        elif any(word in message_lower for word in ["sale", "discount", "deal"]):
            response = await self._handle_sale_inquiry()
        elif any(word in message_lower for word in ["recommend", "suggest", "best"]):
            response = await self._handle_recommendation(user_message)
        elif any(word in message_lower for word in ["help", "support", "assist"]):
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

    async def _handle_order_inquiry(self, message: str) -> str:
        """Handle order status inquiries."""
        import re

        # Try to extract order number
        order_match = re.search(r"#?(\d{4,})", message)

        if order_match:
            order_id = int(order_match.group(1))
            order = await self.client.get_order(order_id)

            if order:
                return self._format_order_status(order)
            else:
                return f"I couldn't find order #{order_id}. Please check the order number and try again, or provide your email address to look up your orders."

        # Check if we have customer email in context
        if "email" in self.customer_context:
            orders = await self.client.get_orders_by_email(
                self.customer_context["email"]
            )
            if orders:
                return self._format_order_list(orders)

        return """I'd be happy to help you track your order! 📦

Please provide either:
- Your **order number** (e.g., #1001)
- Your **email address** to look up all your orders

Example: "What's the status of order #1001?" """

    def _format_order_status(self, order: Order) -> str:
        """Format order status response."""
        status_info = {
            "pending": (
                "⏳",
                "Payment pending",
                "We're waiting for your payment to be confirmed.",
            ),
            "processing": (
                "📦",
                "Processing",
                "Your order is being prepared for shipping.",
            ),
            "on-hold": (
                "⏸️",
                "On Hold",
                "Your order is on hold. Our team will contact you shortly.",
            ),
            "completed": ("✅", "Completed", "Your order has been delivered."),
            "shipped": ("🚚", "Shipped", "Your order is on its way!"),
            "cancelled": ("❌", "Cancelled", "This order has been cancelled."),
            "refunded": ("💰", "Refunded", "This order has been refunded."),
        }

        emoji, status_text, description = status_info.get(
            order.status, ("❓", order.status.title(), "")
        )

        lines = [
            f"{emoji} **Order #{order.number}**",
            f"Status: **{status_text}**",
            f"{description}",
            "",
            "**Items:**",
        ]

        for item in order.items:
            lines.append(f"  • {item['name']} x{item['quantity']} - ${item['total']}")

        lines.extend(
            [
                "",
                f"**Total:** ${order.total}",
                f"**Order Date:** {order.date_created.strftime('%B %d, %Y')}",
            ]
        )

        if order.tracking_number:
            lines.extend(
                [
                    "",
                    f"📍 **Tracking:** {order.tracking_number}",
                    f"🔗 Track your package: {order.tracking_url}",
                ]
            )

        return "\n".join(lines)

    def _format_order_list(self, orders: list[Order]) -> str:
        """Format list of orders."""
        lines = ["📋 **Your Orders**\n"]

        for order in orders:
            status_emoji = {
                "completed": "✅",
                "processing": "📦",
                "on-hold": "⏸️",
                "pending": "⏳",
            }.get(order.status, "❓")

            lines.append(f"{status_emoji} **#{order.number}** - {order.status.title()}")
            lines.append(
                f"   ${order.total} | {order.date_created.strftime('%b %d, %Y')}"
            )

        lines.append("\nReply with an order number for more details.")
        return "\n".join(lines)

    async def _handle_refund_request(self, message: str) -> str:
        """Handle refund/return requests."""
        import re

        order_match = re.search(r"#?(\d{4,})", message)

        if not order_match:
            return """I can help you with a refund request! 💰

Please provide:
1. Your **order number** (e.g., #1001)
2. The **reason** for the refund

Our refund policy:
- ✅ 30-day money-back guarantee
- ✅ Free returns on defective items
- ⚠️ Return shipping may apply for change of mind

Example: "I'd like to refund order #1001 because the keyboard doesn't work" """

        order_id = int(order_match.group(1))
        order = await self.client.get_order(order_id)

        if not order:
            return f"I couldn't find order #{order_id}. Please check the order number and try again."

        # Extract reason if provided
        reason = "Customer requested refund"
        if "because" in message.lower():
            reason = message.split("because", 1)[1].strip()
        elif "reason" in message.lower():
            reason = message.split("reason", 1)[1].strip()

        result = await self.client.create_refund_request(order_id, reason)

        if result["success"]:
            return f"""✅ **Refund Request Submitted**

Order: #{order_id}
Status: Pending Review
Reference: REF-{result['refund_id']}

Our team will review your request within **24 hours** and email you at {order.customer_email}.

**What happens next:**
1. We review your request
2. If approved, refund processed within 3-5 business days
3. You'll receive a confirmation email

Need anything else? Just ask!"""
        else:
            return "I'm sorry, there was an issue submitting your refund request. Please contact support@example.com directly."

    async def _handle_product_inquiry(self, message: str) -> str:
        """Handle product availability inquiries."""
        # Search for products mentioned
        products = await self.client.search_products(message)

        if products:
            lines = ["🔍 **Products Found**\n"]
            for product in products:
                stock_emoji = {
                    "instock": "✅",
                    "lowstock": "⚠️",
                    "outofstock": "❌",
                }.get(product.stock_status, "❓")

                sale_badge = (
                    f" 🏷️ **{product.discount_percent}% OFF**"
                    if product.is_on_sale
                    else ""
                )

                lines.append(f"{stock_emoji} **{product.name}**{sale_badge}")
                lines.append(f"   SKU: {product.sku} | ${product.price}")

                if product.stock_status == "instock":
                    lines.append(f"   In Stock ({product.stock_quantity} available)")
                elif product.stock_status == "lowstock":
                    lines.append(
                        f"   ⚠️ Low Stock (only {product.stock_quantity} left!)"
                    )
                else:
                    lines.append("   ❌ Out of Stock - Check back soon!")

                lines.append("")

            return "\n".join(lines)

        # Show all available products
        in_stock = await self.client.get_products_in_stock()

        lines = ["Here are our available products:\n"]
        for product in in_stock[:6]:
            lines.append(f"• **{product.name}** - ${product.price}")

        lines.append("\nWhat are you looking for? I can help you find it!")
        return "\n".join(lines)

    async def _handle_shipping_inquiry(self, message: str) -> str:
        """Handle shipping inquiries."""
        import re

        order_match = re.search(r"#?(\d{4,})", message)

        if order_match:
            order_id = int(order_match.group(1))
            order = await self.client.get_order(order_id)

            if order and order.tracking_number:
                return f"""🚚 **Shipping Information for Order #{order.number}**

**Tracking Number:** {order.tracking_number}
**Carrier:** Australia Post

📍 **Track Your Package:**
{order.tracking_url}

**Shipping Address:**
{order.shipping_address.get('first_name', '')} {order.shipping_address.get('last_name', '')}
{order.shipping_address.get('address_1', '')}
{order.shipping_address.get('city', '')}, {order.shipping_address.get('state', '')} {order.shipping_address.get('postcode', '')}

Estimated delivery: 2-5 business days from shipping."""
            elif order:
                return f"""📦 **Order #{order.number}**

Status: {order.status.title()}

Your order hasn't shipped yet. Once it ships, you'll receive an email with tracking information.

**Estimated Processing:** 1-2 business days
**Shipping Time:** 2-5 business days after dispatch"""

        return """🚚 **Shipping Information**

**Standard Shipping:**
- FREE on orders over $50
- 2-5 business days
- Tracking included

**Express Shipping:**
- $10 flat rate
- 1-2 business days
- Tracking included

Want to check a specific order? Just provide your order number!"""

    async def _handle_sale_inquiry(self) -> str:
        """Handle inquiries about sales and discounts."""
        on_sale = await self.client.get_products_on_sale()

        if not on_sale:
            return "We don't have any active sales right now, but check back soon! Sign up for our newsletter to be the first to know about deals."

        lines = ["🏷️ **Current Deals**\n"]
        for product in on_sale:
            lines.append(f"🔥 **{product.name}**")
            lines.append(
                f"   ~~${product.regular_price}~~ **${product.price}** - Save {product.discount_percent}%!"
            )
            lines.append("")

        lines.append("Limited time offers - get them while they last! 🛒")
        return "\n".join(lines)

    async def _handle_recommendation(self, message: str) -> str:
        """Handle product recommendations."""
        products = await self.client.get_products_in_stock()

        # Simple recommendation based on popularity/price
        lines = ["🌟 **Recommended Products**\n"]

        for product in products[:4]:
            sale_badge = f" **SALE!**" if product.is_on_sale else ""
            lines.append(f"⭐ **{product.name}**{sale_badge}")
            lines.append(
                f"   ${product.price} | {product.categories[0] if product.categories else 'General'}"
            )
            lines.append("")

        lines.append("Need help choosing? Tell me what you're looking for!")
        return "\n".join(lines)

    async def _handle_general(self, message: str) -> str:
        """Handle general queries."""
        return f"""Thanks for reaching out! 😊

I'm here to help with:
{self._get_help()}

How can I assist you today?"""

    def _get_help(self) -> str:
        """Return help text."""
        return """**I can help you with:**

📦 **Orders** - "Where's my order #1001?"
🔍 **Products** - "Do you have keyboards in stock?"
💰 **Refunds** - "I want to return order #1001"
🚚 **Shipping** - "When will my order arrive?"
🏷️ **Sales** - "What's on sale?"
⭐ **Recommendations** - "What do you recommend?"

Just ask your question and I'll help!"""


async def demo():
    """Run an interactive demo."""
    print("=" * 60)
    print("WooCommerce Customer Service Assistant")
    print("=" * 60)
    print("\nRunning in DEMO MODE (simulated store data)")
    print("Type 'quit' to exit\n")

    assistant = CustomerServiceAssistant(demo_mode=True)

    # Demo queries
    demo_queries = [
        "What's the status of order #1001?",
        "Do you have any keyboards in stock?",
        "What's on sale?",
        "I want to refund order #1002 because I changed my mind",
        "help",
    ]

    print("Running demo queries...\n")

    for query in demo_queries:
        print(f"👤 Customer: {query}")
        print("-" * 40)
        response = await assistant.process_message(query)
        print(f"🤖 Assistant:\n{response}")
        print("=" * 60)
        print()


async def interactive():
    """Run interactive mode."""
    print("=" * 60)
    print("WooCommerce Customer Service Assistant")
    print("=" * 60)
    print("\nType 'quit' to exit, 'help' for commands\n")

    assistant = CustomerServiceAssistant(demo_mode=True)

    while True:
        try:
            user_input = input("👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "bye"]:
                print("👋 Thank you for shopping with us!")
                break

            response = await assistant.process_message(user_input)
            print(f"\n🤖 Assistant:\n{response}\n")

        except KeyboardInterrupt:
            print("\n👋 Thank you for shopping with us!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(demo())
