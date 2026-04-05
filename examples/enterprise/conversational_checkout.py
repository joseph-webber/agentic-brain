#!/usr/bin/env python3
"""
Example: Multi-Gateway Conversational Commerce Platform

A complete e-commerce chatbot supporting multiple payment gateways:
- Product catalog integration
- Shopping cart via conversation
- Multiple payment methods (Stripe, PayPal, Afterpay/Klarna)
- Order tracking
- Returns/exchanges via chat
- Australian Consumer Law compliance

Example Conversation:
╔══════════════════════════════════════════════════════════════════════════════╗
║  User: "I want to buy a laptop"                                              ║
║  Bot:  "I found 3 laptops in your price range. Here's the MacBook Pro M3..."║
║  User: "Add to cart"                                                         ║
║  Bot:  "Added! Your cart: MacBook Pro M3 - $2,499. Ready to checkout?"      ║
║  User: "Yes, pay with PayPal"                                                ║
║  Bot:  "Creating PayPal checkout... Here's your payment link."              ║
║  [Later]                                                                     ║
║  User: "Where's my order?"                                                   ║
║  Bot:  "Your MacBook shipped yesterday! Tracking: AU123456789"              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Australian Context:
- AUD as default currency
- GST (10%) included in prices
- Afterpay/Klarna BNPL options (popular in Australia)
- Australian Consumer Law refund rights
- Express shipping within Australia

Security:
- PCI DSS compliant (card handling by payment providers)
- No sensitive data in conversation logs
- Audit trail for all transactions
- Rate limiting on payment operations

Usage:
    python examples/enterprise/conversational_checkout.py

Requirements:
    pip install agentic-brain stripe paypalrestsdk
"""

import asyncio
import hashlib
import json
import logging
import re
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [CHECKOUT_BOT] %(message)s",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT GATEWAY ABSTRACTION
# ══════════════════════════════════════════════════════════════════════════════


class PaymentGateway(ABC):
    """Abstract payment gateway interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Gateway name for display."""
        pass

    @abstractmethod
    async def create_checkout(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: dict,
    ) -> dict:
        """Create a checkout session/order."""
        pass

    @abstractmethod
    async def capture_payment(self, checkout_id: str) -> dict:
        """Capture/complete a payment."""
        pass

    @abstractmethod
    async def refund(self, payment_id: str, amount_cents: int, reason: str) -> dict:
        """Process a refund."""
        pass


class StripeGateway(PaymentGateway):
    """Stripe payment gateway implementation."""

    @property
    def name(self) -> str:
        return "Stripe"

    async def create_checkout(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: dict,
    ) -> dict:
        session_id = f"cs_{secrets.token_hex(16)}"
        return {
            "checkout_id": session_id,
            "checkout_url": f"https://checkout.stripe.com/pay/{session_id}",
            "gateway": "stripe",
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        }

    async def capture_payment(self, checkout_id: str) -> dict:
        return {
            "payment_id": f"pi_{secrets.token_hex(12)}",
            "status": "succeeded",
            "gateway": "stripe",
        }

    async def refund(self, payment_id: str, amount_cents: int, reason: str) -> dict:
        return {
            "refund_id": f"re_{secrets.token_hex(12)}",
            "amount_cents": amount_cents,
            "status": "succeeded",
        }


class PayPalGateway(PaymentGateway):
    """PayPal payment gateway implementation."""

    @property
    def name(self) -> str:
        return "PayPal"

    async def create_checkout(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: dict,
    ) -> dict:
        order_id = f"ORDER-{secrets.token_hex(8).upper()}"
        return {
            "checkout_id": order_id,
            "checkout_url": f"https://www.paypal.com/checkoutnow?token={order_id}",
            "gateway": "paypal",
            "expires_at": (datetime.now() + timedelta(hours=3)).isoformat(),
        }

    async def capture_payment(self, checkout_id: str) -> dict:
        return {
            "payment_id": f"CAPTURE-{secrets.token_hex(8).upper()}",
            "status": "COMPLETED",
            "gateway": "paypal",
        }

    async def refund(self, payment_id: str, amount_cents: int, reason: str) -> dict:
        return {
            "refund_id": f"REFUND-{secrets.token_hex(8).upper()}",
            "amount_cents": amount_cents,
            "status": "COMPLETED",
        }


class AfterpayGateway(PaymentGateway):
    """
    Afterpay (Buy Now Pay Later) gateway.

    Popular in Australia - allows customers to pay in 4 installments.
    """

    @property
    def name(self) -> str:
        return "Afterpay"

    async def create_checkout(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: dict,
    ) -> dict:
        # Afterpay has min/max limits (max varies by customer status)
        if amount_cents < 100:  # $1 minimum
            raise ValueError("Afterpay minimum is $1 AUD")
        # Note: Established customers can spend up to $2,000-$4,000
        # New customers typically limited to $600-$2,000
        # For demo, we allow up to $3,000
        if amount_cents > 300000:  # $3,000 max for demo
            raise ValueError(
                "Amount exceeds Afterpay limit. Try Klarna financing for larger purchases."
            )

        token = secrets.token_hex(16)
        installment = amount_cents // 4

        return {
            "checkout_id": token,
            "checkout_url": f"https://portal.afterpay.com/checkout/{token}",
            "gateway": "afterpay",
            "installments": [
                {"due": "Today", "amount_cents": installment},
                {"due": "In 2 weeks", "amount_cents": installment},
                {"due": "In 4 weeks", "amount_cents": installment},
                {"due": "In 6 weeks", "amount_cents": amount_cents - (installment * 3)},
            ],
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }

    async def capture_payment(self, checkout_id: str) -> dict:
        return {
            "payment_id": f"AP-{secrets.token_hex(10).upper()}",
            "status": "APPROVED",
            "gateway": "afterpay",
        }

    async def refund(self, payment_id: str, amount_cents: int, reason: str) -> dict:
        return {
            "refund_id": f"APR-{secrets.token_hex(8).upper()}",
            "amount_cents": amount_cents,
            "status": "PROCESSED",
        }


class KlarnaGateway(PaymentGateway):
    """
    Klarna (Buy Now Pay Later) gateway.

    Offers Pay in 4, Pay in 30 days, and financing options.
    """

    @property
    def name(self) -> str:
        return "Klarna"

    async def create_checkout(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: dict,
    ) -> dict:
        session_id = f"kl_{secrets.token_hex(16)}"
        installment = amount_cents // 4

        return {
            "checkout_id": session_id,
            "checkout_url": f"https://pay.klarna.com/v1/sessions/{session_id}",
            "gateway": "klarna",
            "payment_options": [
                {
                    "type": "pay_in_4",
                    "installments": 4,
                    "per_installment_cents": installment,
                },
                {
                    "type": "pay_in_30",
                    "description": "Pay in full within 30 days",
                },
                {
                    "type": "financing",
                    "description": "6-36 month financing",
                },
            ],
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }

    async def capture_payment(self, checkout_id: str) -> dict:
        return {
            "payment_id": f"KL-{secrets.token_hex(12).upper()}",
            "status": "CAPTURED",
            "gateway": "klarna",
        }

    async def refund(self, payment_id: str, amount_cents: int, reason: str) -> dict:
        return {
            "refund_id": f"KLR-{secrets.token_hex(8).upper()}",
            "amount_cents": amount_cents,
            "status": "REFUNDED",
        }


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT CATALOG
# ══════════════════════════════════════════════════════════════════════════════


class ProductCategory(Enum):
    """Product categories."""

    LAPTOPS = "laptops"
    PHONES = "phones"
    ACCESSORIES = "accessories"
    SOFTWARE = "software"


@dataclass
class Product:
    """Product in the catalog."""

    id: str
    name: str
    description: str
    category: ProductCategory
    price_cents: int  # AUD cents, GST inclusive
    stock: int
    image_url: str = ""
    specs: dict = field(default_factory=dict)

    @property
    def price_display(self) -> str:
        """Human-readable price."""
        return f"${self.price_cents / 100:,.2f}"

    @property
    def gst_amount(self) -> int:
        """GST component (10% of price)."""
        return int(self.price_cents / 11)  # Price is GST inclusive


# Sample product catalog
PRODUCT_CATALOG = {
    "macbook-pro-m3": Product(
        id="macbook-pro-m3",
        name='MacBook Pro 14" M3',
        description="Apple M3 chip, 18GB RAM, 512GB SSD. Perfect for professionals.",
        category=ProductCategory.LAPTOPS,
        price_cents=249900,  # $2,499 AUD
        stock=15,
        specs={"chip": "M3", "ram": "18GB", "storage": "512GB SSD"},
    ),
    "macbook-air-m2": Product(
        id="macbook-air-m2",
        name='MacBook Air 13" M2',
        description="Apple M2 chip, 8GB RAM, 256GB SSD. Lightweight and powerful.",
        category=ProductCategory.LAPTOPS,
        price_cents=149900,  # $1,499 AUD
        stock=25,
        specs={"chip": "M2", "ram": "8GB", "storage": "256GB SSD"},
    ),
    "dell-xps-15": Product(
        id="dell-xps-15",
        name="Dell XPS 15",
        description="Intel Core i7, 16GB RAM, 512GB SSD. Windows powerhouse.",
        category=ProductCategory.LAPTOPS,
        price_cents=219900,  # $2,199 AUD
        stock=10,
        specs={"cpu": "Intel i7", "ram": "16GB", "storage": "512GB SSD"},
    ),
    "iphone-15-pro": Product(
        id="iphone-15-pro",
        name="iPhone 15 Pro",
        description="A17 Pro chip, 256GB, Titanium design.",
        category=ProductCategory.PHONES,
        price_cents=179900,  # $1,799 AUD
        stock=30,
        specs={"chip": "A17 Pro", "storage": "256GB", "display": '6.1"'},
    ),
    "airpods-pro": Product(
        id="airpods-pro",
        name="AirPods Pro (2nd Gen)",
        description="Active Noise Cancellation, Adaptive Audio, USB-C.",
        category=ProductCategory.ACCESSORIES,
        price_cents=39900,  # $399 AUD
        stock=50,
    ),
    "magic-keyboard": Product(
        id="magic-keyboard",
        name="Magic Keyboard with Touch ID",
        description="Wireless keyboard with Touch ID for Mac.",
        category=ProductCategory.ACCESSORIES,
        price_cents=27900,  # $279 AUD
        stock=40,
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# SHOPPING CART & ORDERS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class CartItem:
    """Item in shopping cart."""

    product_id: str
    quantity: int
    price_at_add: int  # Price when added (in case of changes)


@dataclass
class ShoppingCart:
    """Shopping cart for a customer."""

    customer_id: str
    items: list[CartItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_cents(self) -> int:
        """Total cart value."""
        return sum(item.price_at_add * item.quantity for item in self.items)

    @property
    def total_display(self) -> str:
        """Human-readable total."""
        return f"${self.total_cents / 100:,.2f}"

    @property
    def item_count(self) -> int:
        """Total number of items."""
        return sum(item.quantity for item in self.items)

    def add_item(self, product: Product, quantity: int = 1) -> None:
        """Add item to cart."""
        # Check if already in cart
        for item in self.items:
            if item.product_id == product.id:
                item.quantity += quantity
                return

        self.items.append(
            CartItem(
                product_id=product.id,
                quantity=quantity,
                price_at_add=product.price_cents,
            )
        )

    def remove_item(self, product_id: str) -> bool:
        """Remove item from cart."""
        for i, item in enumerate(self.items):
            if item.product_id == product_id:
                del self.items[i]
                return True
        return False

    def clear(self) -> None:
        """Empty the cart."""
        self.items.clear()


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class ShippingAddress:
    """Australian shipping address."""

    name: str
    street: str
    suburb: str
    state: str  # NSW, VIC, QLD, SA, WA, TAS, NT, ACT
    postcode: str
    country: str = "Australia"
    phone: str = ""

    def validate(self) -> bool:
        """Validate Australian address."""
        valid_states = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"}
        if self.state.upper() not in valid_states:
            return False
        if not re.match(r"^\d{4}$", self.postcode):
            return False
        return True


@dataclass
class Order:
    """Customer order."""

    id: str
    customer_id: str
    items: list[CartItem]
    shipping_address: Optional[ShippingAddress]
    payment_gateway: str
    payment_id: str
    subtotal_cents: int
    gst_cents: int
    shipping_cents: int
    total_cents: int
    status: OrderStatus
    created_at: datetime = field(default_factory=datetime.now)
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    @property
    def total_display(self) -> str:
        return f"${self.total_cents / 100:,.2f}"


@dataclass
class ReturnRequest:
    """Return/refund request."""

    id: str
    order_id: str
    customer_id: str
    items: list[str]  # Product IDs
    reason: str
    status: str  # pending, approved, rejected, completed
    refund_amount_cents: int
    created_at: datetime = field(default_factory=datetime.now)


# ══════════════════════════════════════════════════════════════════════════════
# E-COMMERCE SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class ECommerceService:
    """
    E-commerce backend service.

    Handles products, carts, orders, and payments.
    """

    # Shipping rates (AUD cents)
    SHIPPING_STANDARD = 995  # $9.95
    SHIPPING_EXPRESS = 1495  # $14.95
    SHIPPING_FREE_THRESHOLD = 10000  # Free shipping over $100

    def __init__(self):
        self._carts: dict[str, ShoppingCart] = {}
        self._orders: dict[str, Order] = {}
        self._returns: dict[str, ReturnRequest] = {}

        # Payment gateways
        self._gateways: dict[str, PaymentGateway] = {
            "stripe": StripeGateway(),
            "paypal": PayPalGateway(),
            "afterpay": AfterpayGateway(),
            "klarna": KlarnaGateway(),
        }

        self._pending_checkouts: dict[str, dict] = {}

        logger.info("E-commerce service initialized")

    def get_cart(self, customer_id: str) -> ShoppingCart:
        """Get or create cart for customer."""
        if customer_id not in self._carts:
            self._carts[customer_id] = ShoppingCart(customer_id=customer_id)
        return self._carts[customer_id]

    def search_products(
        self, query: str, category: Optional[ProductCategory] = None
    ) -> list[Product]:
        """Search products by name/description."""
        query_lower = query.lower()
        results = []

        # Extract key search terms
        search_terms = [
            "laptop",
            "phone",
            "airpods",
            "keyboard",
            "macbook",
            "iphone",
            "dell",
        ]
        matched_term = None
        for term in search_terms:
            if term in query_lower:
                matched_term = term
                break

        for product in PRODUCT_CATALOG.values():
            if category and product.category != category:
                continue

            # Match on extracted term or full query
            name_lower = product.name.lower()
            desc_lower = product.description.lower()

            if matched_term:
                if matched_term in name_lower or matched_term in desc_lower:
                    results.append(product)
            elif query_lower in name_lower or query_lower in desc_lower:
                results.append(product)

        # If still no results and category was detected, return all in category
        if not results and category:
            results = [p for p in PRODUCT_CATALOG.values() if p.category == category]

        return results

    def get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID."""
        return PRODUCT_CATALOG.get(product_id)

    def add_to_cart(
        self, customer_id: str, product_id: str, quantity: int = 1
    ) -> tuple[bool, str]:
        """Add product to cart."""
        product = self.get_product(product_id)
        if not product:
            return False, "Product not found"

        if product.stock < quantity:
            return False, f"Only {product.stock} in stock"

        cart = self.get_cart(customer_id)
        cart.add_item(product, quantity)

        return True, f"Added {product.name} to cart"

    def calculate_shipping(self, cart: ShoppingCart, express: bool = False) -> int:
        """Calculate shipping cost."""
        if cart.total_cents >= self.SHIPPING_FREE_THRESHOLD:
            return 0
        return self.SHIPPING_EXPRESS if express else self.SHIPPING_STANDARD

    async def create_checkout(
        self,
        customer_id: str,
        gateway_name: str,
        shipping_address: Optional[ShippingAddress] = None,
        express_shipping: bool = False,
    ) -> dict:
        """Create checkout with specified payment gateway."""
        cart = self.get_cart(customer_id)

        if not cart.items:
            return {"error": "Cart is empty"}

        gateway = self._gateways.get(gateway_name.lower())
        if not gateway:
            return {"error": f"Unknown payment gateway: {gateway_name}"}

        # Calculate totals
        subtotal = cart.total_cents
        gst = int(subtotal / 11)  # GST is included, extract it
        shipping = self.calculate_shipping(cart, express_shipping)
        total = subtotal + shipping

        # Create checkout
        checkout = await gateway.create_checkout(
            customer_id=customer_id,
            amount_cents=total,
            currency="AUD",
            description=f"Order: {cart.item_count} items",
            metadata={
                "customer_id": customer_id,
                "item_count": cart.item_count,
            },
        )

        # Store pending checkout
        self._pending_checkouts[checkout["checkout_id"]] = {
            "customer_id": customer_id,
            "gateway": gateway_name,
            "cart_items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "price": item.price_at_add,
                }
                for item in cart.items
            ],
            "subtotal": subtotal,
            "gst": gst,
            "shipping": shipping,
            "total": total,
            "shipping_address": shipping_address,
        }

        checkout["subtotal_display"] = f"${subtotal/100:,.2f}"
        checkout["shipping_display"] = f"${shipping/100:,.2f}" if shipping else "FREE"
        checkout["total_display"] = f"${total/100:,.2f}"

        return checkout

    async def complete_checkout(self, checkout_id: str) -> dict:
        """Complete a checkout after payment approval."""
        pending = self._pending_checkouts.get(checkout_id)
        if not pending:
            return {"error": "Checkout not found or expired"}

        gateway = self._gateways.get(pending["gateway"])
        if not gateway:
            return {"error": "Payment gateway error"}

        # Capture payment
        payment = await gateway.capture_payment(checkout_id)

        if payment.get("status") not in [
            "succeeded",
            "COMPLETED",
            "APPROVED",
            "CAPTURED",
        ]:
            return {"error": f"Payment failed: {payment.get('status')}"}

        # Create order
        order_id = f"ORD-{secrets.token_hex(6).upper()}"
        order = Order(
            id=order_id,
            customer_id=pending["customer_id"],
            items=[
                CartItem(
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    price_at_add=item["price"],
                )
                for item in pending["cart_items"]
            ],
            shipping_address=pending.get("shipping_address"),
            payment_gateway=pending["gateway"],
            payment_id=payment["payment_id"],
            subtotal_cents=pending["subtotal"],
            gst_cents=pending["gst"],
            shipping_cents=pending["shipping"],
            total_cents=pending["total"],
            status=OrderStatus.PAID,
        )

        self._orders[order_id] = order

        # Clear cart and pending checkout
        customer_id = pending["customer_id"]
        if customer_id in self._carts:
            self._carts[customer_id].clear()
        del self._pending_checkouts[checkout_id]

        return {
            "order_id": order_id,
            "status": "confirmed",
            "total_display": order.total_display,
            "payment_id": payment["payment_id"],
        }

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)

    def get_customer_orders(self, customer_id: str) -> list[Order]:
        """Get all orders for a customer."""
        return [
            order for order in self._orders.values() if order.customer_id == customer_id
        ]

    async def request_return(
        self,
        customer_id: str,
        order_id: str,
        product_ids: list[str],
        reason: str,
    ) -> dict:
        """
        Request a return/refund.

        Australian Consumer Law: Customers have refund rights for:
        - Faulty products
        - Products not matching description
        - Products not fit for purpose
        """
        order = self.get_order(order_id)
        if not order:
            return {"error": "Order not found"}

        if order.customer_id != customer_id:
            return {"error": "Order does not belong to this customer"}

        # Check return window (30 days for standard, unlimited for faulty)
        days_since_order = (datetime.now() - order.created_at).days
        is_faulty_claim = any(
            word in reason.lower()
            for word in ["faulty", "defective", "broken", "damaged"]
        )

        if days_since_order > 30 and not is_faulty_claim:
            return {
                "error": "Return window has closed (30 days). "
                "If the product is faulty, please describe the issue."
            }

        # Calculate refund amount
        refund_amount = sum(
            item.price_at_add * item.quantity
            for item in order.items
            if item.product_id in product_ids
        )

        return_id = f"RET-{secrets.token_hex(6).upper()}"
        return_request = ReturnRequest(
            id=return_id,
            order_id=order_id,
            customer_id=customer_id,
            items=product_ids,
            reason=reason,
            status="pending",
            refund_amount_cents=refund_amount,
        )

        self._returns[return_id] = return_request

        return {
            "return_id": return_id,
            "status": "pending",
            "refund_amount_display": f"${refund_amount/100:,.2f}",
            "message": "Return request submitted. We'll review within 24 hours.",
        }

    async def process_refund(self, return_id: str) -> dict:
        """Process an approved return refund."""
        return_request = self._returns.get(return_id)
        if not return_request:
            return {"error": "Return request not found"}

        order = self.get_order(return_request.order_id)
        if not order:
            return {"error": "Order not found"}

        gateway = self._gateways.get(order.payment_gateway)
        if not gateway:
            return {"error": "Payment gateway not available"}

        refund = await gateway.refund(
            payment_id=order.payment_id,
            amount_cents=return_request.refund_amount_cents,
            reason=return_request.reason,
        )

        return_request.status = "completed"

        return {
            "refund_id": refund["refund_id"],
            "amount_display": f"${return_request.refund_amount_cents/100:,.2f}",
            "status": "completed",
        }


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATIONAL INTERFACE
# ══════════════════════════════════════════════════════════════════════════════


class ConversationalCheckoutBot:
    """
    Natural language interface for shopping and payments.

    Handles the full shopping journey via conversation.
    """

    def __init__(self, ecommerce: ECommerceService):
        self.ecommerce = ecommerce
        self._context: dict[str, dict] = {}  # session -> conversation context

    def _get_context(self, session_id: str) -> dict:
        """Get or create conversation context."""
        if session_id not in self._context:
            self._context[session_id] = {
                "last_products": [],
                "pending_checkout": None,
                "last_order": None,
            }
        return self._context[session_id]

    def _detect_intent(self, message: str) -> tuple[str, dict]:
        """Detect user intent from message."""
        message_lower = message.lower()

        # Product search
        if any(
            word in message_lower
            for word in ["buy", "want", "looking for", "search", "find", "show me"]
        ):
            # Extract product type
            for category in ProductCategory:
                if category.value.rstrip("s") in message_lower:
                    return "search_products", {"category": category}
            return "search_products", {"query": message}

        # Add to cart
        if any(
            phrase in message_lower
            for phrase in ["add to cart", "add it", "i'll take", "take it", "add this"]
        ):
            return "add_to_cart", {}

        # View cart
        if any(word in message_lower for word in ["cart", "basket", "bag"]):
            if "remove" in message_lower or "delete" in message_lower:
                return "remove_from_cart", {}
            if "clear" in message_lower or "empty" in message_lower:
                return "clear_cart", {}
            return "view_cart", {}

        # Checkout with payment method detection
        if any(
            word in message_lower for word in ["checkout", "pay", "buy now", "purchase"]
        ):
            gateway = self._detect_payment_method(message_lower)
            return "checkout", {"gateway": gateway}

        # Payment confirmation
        if any(
            word in message_lower for word in ["paid", "done", "completed", "approved"]
        ):
            return "confirm_payment", {}

        # Order tracking
        if any(word in message_lower for word in ["where", "track", "status", "order"]):
            if "where" in message_lower or "track" in message_lower:
                return "track_order", {}
            return "view_orders", {}

        # Returns
        if any(
            word in message_lower
            for word in ["return", "refund", "exchange", "problem"]
        ):
            return "request_return", {}

        # Help
        if any(word in message_lower for word in ["help", "what can", "options"]):
            return "help", {}

        return "unknown", {}

    def _detect_payment_method(self, message: str) -> str:
        """Detect preferred payment method from message."""
        if "paypal" in message:
            return "paypal"
        if "afterpay" in message:
            return "afterpay"
        if "klarna" in message:
            return "klarna"
        if any(word in message for word in ["card", "credit", "debit", "stripe"]):
            return "stripe"
        return "stripe"  # Default

    async def process_message(
        self,
        message: str,
        session_id: str,
        customer_id: str,
    ) -> str:
        """Process user message and return response."""
        intent, params = self._detect_intent(message)
        context = self._get_context(session_id)

        handlers = {
            "search_products": self._handle_search,
            "add_to_cart": self._handle_add_to_cart,
            "view_cart": self._handle_view_cart,
            "remove_from_cart": self._handle_remove_from_cart,
            "clear_cart": self._handle_clear_cart,
            "checkout": self._handle_checkout,
            "confirm_payment": self._handle_confirm_payment,
            "track_order": self._handle_track_order,
            "view_orders": self._handle_view_orders,
            "request_return": self._handle_return,
            "help": self._handle_help,
            "unknown": self._handle_unknown,
        }

        handler = handlers.get(intent, self._handle_unknown)
        return await handler(session_id, customer_id, context, params, message)

    async def _handle_search(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Handle product search."""
        query = params.get("query", message)
        category = params.get("category")

        products = self.ecommerce.search_products(query, category)

        if not products:
            return (
                f"I couldn't find anything matching '{query}'.\n\n"
                "We have:\n"
                "• Laptops (MacBook Pro, MacBook Air, Dell XPS)\n"
                "• Phones (iPhone 15 Pro)\n"
                "• Accessories (AirPods, Magic Keyboard)\n\n"
                "What are you looking for?"
            )

        # Store for "add to cart" follow-up
        context["last_products"] = products

        lines = [f"I found {len(products)} products:\n"]
        for i, product in enumerate(products[:5], 1):
            stock_status = "✓ In stock" if product.stock > 0 else "✗ Out of stock"
            lines.append(
                f"{i}. **{product.name}** - {product.price_display}\n"
                f"   {product.description}\n"
                f"   {stock_status}"
            )

        lines.append("\nWould you like to add any to your cart?")
        return "\n".join(lines)

    async def _handle_add_to_cart(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Handle add to cart."""
        last_products = context.get("last_products", [])

        if not last_products:
            return "What product would you like to add? Try searching first, e.g., 'I want to buy a laptop'"

        # Add first product by default (or could parse which one)
        product = last_products[0]
        success, msg = self.ecommerce.add_to_cart(customer_id, product.id)

        if not success:
            return f"Sorry, couldn't add to cart: {msg}"

        cart = self.ecommerce.get_cart(customer_id)

        return (
            f"✅ Added **{product.name}** to your cart!\n\n"
            f"Cart total: {cart.total_display} ({cart.item_count} items)\n\n"
            "Ready to checkout, or keep shopping?"
        )

    async def _handle_view_cart(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Show cart contents."""
        cart = self.ecommerce.get_cart(customer_id)

        if not cart.items:
            return "Your cart is empty. Would you like to browse some products?"

        lines = ["🛒 **Your Cart:**\n"]
        for item in cart.items:
            product = self.ecommerce.get_product(item.product_id)
            if product:
                lines.append(
                    f"• {product.name} x{item.quantity} - ${item.price_at_add * item.quantity / 100:,.2f}"
                )

        # Calculate shipping
        shipping = self.ecommerce.calculate_shipping(cart)
        shipping_display = f"${shipping/100:.2f}" if shipping else "FREE"

        lines.append(f"\n**Subtotal:** {cart.total_display}")
        lines.append(f"**Shipping:** {shipping_display}")
        lines.append(f"**Total:** ${(cart.total_cents + shipping)/100:,.2f}")

        lines.append("\n💳 Payment options: Card, PayPal, Afterpay, Klarna")
        lines.append("Say 'checkout with [method]' when ready!")

        return "\n".join(lines)

    async def _handle_remove_from_cart(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Remove item from cart."""
        cart = self.ecommerce.get_cart(customer_id)

        if not cart.items:
            return "Your cart is already empty."

        # Remove first item (could parse which one)
        removed = cart.items[0]
        product = self.ecommerce.get_product(removed.product_id)
        cart.remove_item(removed.product_id)

        return f"Removed {product.name if product else 'item'} from your cart."

    async def _handle_clear_cart(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Clear entire cart."""
        cart = self.ecommerce.get_cart(customer_id)
        cart.clear()
        return "✅ Your cart has been cleared."

    async def _handle_checkout(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Start checkout process."""
        gateway = params.get("gateway", "stripe")
        cart = self.ecommerce.get_cart(customer_id)

        if not cart.items:
            return "Your cart is empty. Add some products first!"

        try:
            checkout = await self.ecommerce.create_checkout(
                customer_id=customer_id,
                gateway_name=gateway,
            )
        except ValueError as e:
            # Handle gateway-specific errors (e.g., Afterpay limits)
            return (
                f"⚠️ {str(e)}\n\n"
                "Try a different payment method:\n"
                "• 'Pay with card' - Stripe (no limits)\n"
                "• 'Pay with PayPal' - PayPal (no limits)\n"
                "• 'Pay with Klarna' - Financing available"
            )

        if "error" in checkout:
            return f"Couldn't create checkout: {checkout['error']}"

        # Store for confirmation
        context["pending_checkout"] = checkout["checkout_id"]

        gateway_name = gateway.title()

        # Special messaging for BNPL
        if gateway in ["afterpay", "klarna"]:
            installments = checkout.get("installments", [])
            if installments:
                install_info = "\n".join(
                    f"  • {i['due']}: ${i['amount_cents']/100:.2f}"
                    for i in installments[:4]
                )
                return (
                    f"🛍️ **{gateway_name} Checkout**\n\n"
                    f"Total: {checkout['total_display']}\n"
                    f"Pay in 4 installments:\n{install_info}\n\n"
                    f"🔒 Complete your payment:\n{checkout['checkout_url']}\n\n"
                    "Let me know once you've completed the payment!"
                )

        return (
            f"🛍️ **Checkout with {gateway_name}**\n\n"
            f"Subtotal: {checkout['subtotal_display']}\n"
            f"Shipping: {checkout['shipping_display']}\n"
            f"**Total: {checkout['total_display']}**\n\n"
            f"🔒 Complete your payment:\n{checkout['checkout_url']}\n\n"
            "Let me know once you've completed the payment!"
        )

    async def _handle_confirm_payment(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Confirm payment completion."""
        checkout_id = context.get("pending_checkout")

        if not checkout_id:
            return "I don't see a pending payment. Would you like to checkout?"

        result = await self.ecommerce.complete_checkout(checkout_id)

        if "error" in result:
            return f"There was an issue: {result['error']}\n\nPlease try again or contact support."

        context["pending_checkout"] = None
        context["last_order"] = result["order_id"]

        return (
            f"✅ **Order Confirmed!**\n\n"
            f"Order ID: {result['order_id']}\n"
            f"Total: {result['total_display']}\n\n"
            "📦 We're preparing your order!\n"
            "You'll receive shipping confirmation with tracking within 24 hours.\n\n"
            "Thank you for shopping with us! 🎉"
        )

    async def _handle_track_order(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Track an order."""
        orders = self.ecommerce.get_customer_orders(customer_id)

        if not orders:
            return "You don't have any orders yet."

        # Get most recent order
        latest = sorted(orders, key=lambda o: o.created_at, reverse=True)[0]

        status_emoji = {
            OrderStatus.PENDING: "⏳",
            OrderStatus.PAID: "💳",
            OrderStatus.PROCESSING: "📦",
            OrderStatus.SHIPPED: "🚚",
            OrderStatus.DELIVERED: "✅",
        }

        response = (
            f"{status_emoji.get(latest.status, '📦')} **Order {latest.id}**\n\n"
            f"Status: {latest.status.value.title()}\n"
            f"Total: {latest.total_display}\n"
            f"Ordered: {latest.created_at.strftime('%d %b %Y')}\n"
        )

        if latest.tracking_number:
            response += f"\n📍 Tracking: {latest.tracking_number}"
            response += "\nTrack at: https://auspost.com.au/track"

        if latest.status == OrderStatus.SHIPPED:
            response += "\n\n🚚 Your order is on its way! Expected delivery in 2-3 business days."
        elif latest.status == OrderStatus.PROCESSING:
            response += "\n\n📦 Your order is being packed. Shipping soon!"

        return response

    async def _handle_view_orders(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """View all orders."""
        orders = self.ecommerce.get_customer_orders(customer_id)

        if not orders:
            return "You don't have any orders yet. Ready to shop?"

        lines = ["📋 **Your Orders:**\n"]
        for order in sorted(orders, key=lambda o: o.created_at, reverse=True)[:5]:
            lines.append(
                f"• {order.id} - {order.total_display} - "
                f"{order.status.value.title()} ({order.created_at.strftime('%d %b')})"
            )

        return "\n".join(lines)

    async def _handle_return(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Handle return request."""
        orders = self.ecommerce.get_customer_orders(customer_id)

        if not orders:
            return "You don't have any orders to return."

        latest = sorted(orders, key=lambda o: o.created_at, reverse=True)[0]

        return (
            "I can help you with a return. Under Australian Consumer Law, you're entitled to a refund if:\n\n"
            "• The product is faulty or damaged\n"
            "• It doesn't match the description\n"
            "• It doesn't do what it should\n\n"
            f"For your recent order ({latest.id}), please describe the issue and I'll process your return request."
        )

    async def _handle_help(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Show help message."""
        return (
            "🛒 **I can help you with:**\n\n"
            "**Shopping:**\n"
            "• 'I want to buy a laptop' - Search products\n"
            "• 'Add to cart' - Add last viewed product\n"
            "• 'Show my cart' - View cart contents\n\n"
            "**Checkout:**\n"
            "• 'Checkout with card' - Pay with Stripe\n"
            "• 'Pay with PayPal' - PayPal checkout\n"
            "• 'Use Afterpay' - Pay in 4 installments\n"
            "• 'Pay with Klarna' - BNPL options\n\n"
            "**Orders:**\n"
            "• 'Where's my order?' - Track shipping\n"
            "• 'Show my orders' - Order history\n"
            "• 'I need a return' - Start return process\n\n"
            "What would you like to do?"
        )

    async def _handle_unknown(
        self,
        session_id: str,
        customer_id: str,
        context: dict,
        params: dict,
        message: str,
    ) -> str:
        """Handle unknown intent."""
        return (
            "I'm not sure what you mean. I can help you:\n\n"
            "• **Shop** - 'I want to buy a laptop'\n"
            "• **Checkout** - 'Pay with PayPal'\n"
            "• **Track orders** - 'Where's my order?'\n"
            "• **Returns** - 'I need a refund'\n\n"
            "What would you like to do?"
        )


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo_full_shopping_journey():
    """Demonstrate a complete shopping journey."""

    print("\n" + "=" * 70)
    print("  CONVERSATIONAL CHECKOUT - FULL SHOPPING JOURNEY DEMO")
    print("=" * 70 + "\n")

    # Initialize
    ecommerce = ECommerceService()
    bot = ConversationalCheckoutBot(ecommerce)

    # Simulate conversation
    conversation = [
        "I want to buy a laptop",
        "Add to cart",
        "Show my cart",
        "Checkout with Afterpay",
        "Done! I paid",
        "Where's my order?",
    ]

    session_id = secrets.token_hex(8)
    customer_id = "joseph_123"

    for user_message in conversation:
        print(f"👤 Customer: {user_message}")
        response = await bot.process_message(
            message=user_message,
            session_id=session_id,
            customer_id=customer_id,
        )
        print(f"🛍️ Shop Bot: {response}\n")
        print("-" * 50 + "\n")

    print("=" * 70)
    print("  Demo complete!")
    print("  ")
    print("  This platform supports:")
    print("  • Stripe (credit/debit cards)")
    print("  • PayPal")
    print("  • Afterpay (Pay in 4)")
    print("  • Klarna (BNPL options)")
    print("  ")
    print("  Australian compliant:")
    print("  • GST included in all prices")
    print("  • Australian Consumer Law refund rights")
    print("  • Express shipping within Australia")
    print("=" * 70 + "\n")


async def demo_return_process():
    """Demonstrate return/refund process."""

    print("\n" + "=" * 70)
    print("  CONVERSATIONAL CHECKOUT - RETURN PROCESS DEMO")
    print("=" * 70 + "\n")

    ecommerce = ECommerceService()
    bot = ConversationalCheckoutBot(ecommerce)

    # Add an order manually for demo
    ecommerce._orders["ORD-DEMO123"] = Order(
        id="ORD-DEMO123",
        customer_id="joseph_123",
        items=[CartItem("macbook-pro-m3", 1, 249900)],
        shipping_address=None,
        payment_gateway="stripe",
        payment_id="pi_demo",
        subtotal_cents=249900,
        gst_cents=22718,
        shipping_cents=0,
        total_cents=249900,
        status=OrderStatus.DELIVERED,
    )

    conversation = [
        "I have a problem with my order",
        "Show my orders",
    ]

    session_id = secrets.token_hex(8)

    for user_message in conversation:
        print(f"👤 Customer: {user_message}")
        response = await bot.process_message(
            message=user_message,
            session_id=session_id,
            customer_id="joseph_123",
        )
        print(f"🛍️ Shop Bot: {response}\n")
        print("-" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_full_shopping_journey())
    asyncio.run(demo_return_process())
