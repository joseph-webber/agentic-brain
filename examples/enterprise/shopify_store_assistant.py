#!/usr/bin/env python3
"""
Shopify Store Assistant - Conversational Commerce Chatbot

A full-featured e-commerce chatbot for Shopify stores that handles:
- Natural language product discovery
- Conversational cart management
- Order tracking and shipping updates
- Checkout initiation and abandoned cart recovery
- Customer service (returns, policies, questions)

Features Australian shipping with Australia Post integration patterns.

Example Conversation:
    User: "I'm looking for a birthday gift for my mum"
    Bot: "I'd love to help! What does your mum enjoy? We have jewellery, homewares, and clothing."
    User: "She likes gardening"
    Bot: "Perfect! Here are our top gardening gifts. The Garden Tool Set is our bestseller at $79."
    User: "Add that one"
    Bot: "Added Garden Tool Set to cart. Your total is $79 + $9.95 shipping. Ready to checkout?"

Technical:
    - Shopify Admin API (GraphQL) for store management
    - Shopify Storefront API for public queries
    - Webhook handling for order updates
    - Australia Post shipping integration

Note: Shopify also offers official MCP (Model Context Protocol) support.
See: https://shopify.dev/docs/api/shopify-mcp

Author: Joseph Webber
Created: 2025
"""

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from agentic_brain import AgenticBrain, Message, Tool

# ============================================================================
# Configuration
# ============================================================================

SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "your-store.myshopify.com")
SHOPIFY_ADMIN_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN", "")
SHOPIFY_STOREFRONT_TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

# Australian shipping defaults
DEFAULT_CURRENCY = "AUD"
DEFAULT_COUNTRY = "AU"
AUSTRALIA_POST_API_KEY = os.getenv("AUSTRALIA_POST_API_KEY", "")


class OrderStatus(Enum):
    """Shopify order fulfillment statuses."""

    PENDING = auto()
    PROCESSING = auto()
    SHIPPED = auto()
    OUT_FOR_DELIVERY = auto()
    DELIVERED = auto()
    CANCELLED = auto()
    RETURNED = auto()


@dataclass
class CartItem:
    """Item in the shopping cart."""

    variant_id: str
    product_id: str
    title: str
    variant_title: Optional[str]
    quantity: int
    price: Decimal
    image_url: Optional[str] = None

    @property
    def line_total(self) -> Decimal:
        return self.price * self.quantity


@dataclass
class ShoppingCart:
    """Customer shopping cart with full cart management."""

    items: List[CartItem] = field(default_factory=list)
    discount_code: Optional[str] = None
    discount_amount: Decimal = Decimal("0")
    note: Optional[str] = None

    @property
    def subtotal(self) -> Decimal:
        return sum(item.line_total for item in self.items)

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    def add_item(self, item: CartItem) -> None:
        """Add item or increase quantity if exists."""
        for existing in self.items:
            if existing.variant_id == item.variant_id:
                existing.quantity += item.quantity
                return
        self.items.append(item)

    def remove_item(self, index: int) -> Optional[CartItem]:
        """Remove item by index (1-based for natural language)."""
        if 1 <= index <= len(self.items):
            return self.items.pop(index - 1)
        return None

    def update_quantity(self, index: int, quantity: int) -> bool:
        """Update quantity for item at index."""
        if 1 <= index <= len(self.items):
            if quantity <= 0:
                self.items.pop(index - 1)
            else:
                self.items[index - 1].quantity = quantity
            return True
        return False

    def clear(self) -> None:
        """Empty the cart."""
        self.items.clear()
        self.discount_code = None
        self.discount_amount = Decimal("0")


@dataclass
class CustomerSession:
    """Customer session with cart and context."""

    customer_id: Optional[str] = None
    email: Optional[str] = None
    cart: ShoppingCart = field(default_factory=ShoppingCart)
    last_viewed_products: List[str] = field(default_factory=list)
    search_context: Optional[Dict[str, Any]] = None
    shipping_postcode: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def remember_product(self, product_id: str) -> None:
        """Track recently viewed products for 'that one' references."""
        if product_id in self.last_viewed_products:
            self.last_viewed_products.remove(product_id)
        self.last_viewed_products.insert(0, product_id)
        self.last_viewed_products = self.last_viewed_products[:10]  # Keep last 10


# ============================================================================
# Shopify API Clients
# ============================================================================


class ShopifyAdminAPI:
    """
    Shopify Admin API client for store management operations.

    Used for:
    - Order management and updates
    - Inventory queries
    - Customer data
    - Fulfillment operations
    """

    def __init__(self, store_domain: str, admin_token: str):
        self.store_domain = store_domain
        self.admin_token = admin_token
        self.api_version = "2024-01"
        self.endpoint = (
            f"https://{store_domain}/admin/api/{self.api_version}/graphql.json"
        )

    async def execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute GraphQL query against Admin API."""
        # In production, use httpx or aiohttp
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         self.endpoint,
        #         json={"query": query, "variables": variables or {}},
        #         headers={"X-Shopify-Access-Token": self.admin_token}
        #     )
        #     return response.json()

        # Mock response for example
        return {"data": {}}

    async def get_order(self, order_id: str) -> Optional[Dict]:
        """Fetch order details by ID."""
        query = """
        query GetOrder($id: ID!) {
            order(id: $id) {
                id
                name
                email
                createdAt
                displayFinancialStatus
                displayFulfillmentStatus
                totalPriceSet {
                    shopMoney { amount currencyCode }
                }
                lineItems(first: 50) {
                    edges {
                        node {
                            title
                            quantity
                            variant { id title }
                        }
                    }
                }
                fulfillments {
                    trackingInfo {
                        company
                        number
                        url
                    }
                    deliveredAt
                    estimatedDeliveryAt
                }
                shippingAddress {
                    city
                    province
                    zip
                    country
                }
            }
        }
        """
        result = await self.execute_query(
            query, {"id": f"gid://shopify/Order/{order_id}"}
        )
        return result.get("data", {}).get("order")

    async def get_orders_by_email(self, email: str, limit: int = 10) -> List[Dict]:
        """Fetch recent orders for a customer email."""
        query = """
        query GetCustomerOrders($email: String!, $first: Int!) {
            customers(first: 1, query: $email) {
                edges {
                    node {
                        orders(first: $first, sortKey: CREATED_AT, reverse: true) {
                            edges {
                                node {
                                    id
                                    name
                                    createdAt
                                    displayFulfillmentStatus
                                    totalPriceSet {
                                        shopMoney { amount currencyCode }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        result = await self.execute_query(query, {"email": email, "first": limit})
        customers = result.get("data", {}).get("customers", {}).get("edges", [])
        if customers:
            orders = customers[0].get("node", {}).get("orders", {}).get("edges", [])
            return [edge["node"] for edge in orders]
        return []

    async def create_return(
        self, order_id: str, line_items: List[Dict], reason: str
    ) -> Dict:
        """Initiate a return request."""
        # In production, use returnCreate mutation
        return {
            "success": True,
            "return_id": f"R{order_id[-6:]}",
            "message": "Return request created. You'll receive return shipping label via email.",
        }


class ShopifyStorefrontAPI:
    """
    Shopify Storefront API client for customer-facing operations.

    Used for:
    - Product browsing and search
    - Cart creation and checkout
    - Public store data
    """

    def __init__(self, store_domain: str, storefront_token: str):
        self.store_domain = store_domain
        self.storefront_token = storefront_token
        self.api_version = "2024-01"
        self.endpoint = f"https://{store_domain}/api/{self.api_version}/graphql.json"

    async def execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute GraphQL query against Storefront API."""
        # Mock for example - use httpx in production
        return {"data": {}}

    async def search_products(
        self, query: str, filters: Optional[Dict] = None, limit: int = 10
    ) -> List[Dict]:
        """
        Search products with natural language query and filters.

        Args:
            query: Search text (e.g., "blue dress", "gardening tools")
            filters: Optional filters like price_max, collection, in_stock
            limit: Maximum results to return
        """

        # Build Shopify search query with filters
        search_query = query
        if filters:
            if filters.get("price_max"):
                search_query += f" price:<{filters['price_max']}"
            if filters.get("price_min"):
                search_query += f" price:>{filters['price_min']}"
            if filters.get("collection"):
                search_query += f" collection:{filters['collection']}"
            if filters.get("in_stock"):
                search_query += " available_for_sale:true"

        # Mock response for example
        return [
            {
                "id": "gid://shopify/Product/123456",
                "title": "Premium Garden Tool Set",
                "description": "Complete 5-piece stainless steel garden tool set",
                "price": "79.00",
                "currency": "AUD",
                "image_url": "https://cdn.shopify.com/garden-tools.jpg",
                "in_stock": True,
                "variants": [
                    {"id": "gid://shopify/ProductVariant/789", "title": "Default"}
                ],
            }
        ]

    async def get_product(self, product_id: str) -> Optional[Dict]:
        """Get full product details by ID."""
        query = """
        query GetProduct($id: ID!) {
            product(id: $id) {
                id
                title
                description
                descriptionHtml
                handle
                productType
                vendor
                tags
                priceRange {
                    minVariantPrice { amount currencyCode }
                }
                images(first: 5) {
                    edges { node { url altText } }
                }
                variants(first: 20) {
                    edges {
                        node {
                            id
                            title
                            price { amount currencyCode }
                            availableForSale
                            quantityAvailable
                            selectedOptions { name value }
                        }
                    }
                }
            }
        }
        """
        result = await self.execute_query(query, {"id": product_id})
        return result.get("data", {}).get("product")

    async def get_collections(self, limit: int = 20) -> List[Dict]:
        """Get store collections for browsing."""
        query = """
        query GetCollections($first: Int!) {
            collections(first: $first) {
                edges {
                    node {
                        id
                        title
                        description
                        handle
                        image { url altText }
                    }
                }
            }
        }
        """
        result = await self.execute_query(query, {"first": limit})
        edges = result.get("data", {}).get("collections", {}).get("edges", [])
        return [edge["node"] for edge in edges]

    async def create_checkout(self, cart: ShoppingCart, email: str) -> Dict:
        """
        Create Shopify checkout from cart.

        Returns checkout URL for customer to complete payment.
        """
        line_items = [
            {"variantId": item.variant_id, "quantity": item.quantity}
            for item in cart.items
        ]


        checkout_input = {"lineItems": line_items, "email": email}

        if cart.discount_code:
            checkout_input["discountCodes"] = [cart.discount_code]

        if cart.note:
            checkout_input["note"] = cart.note

        # Mock response
        return {
            "checkout_id": "Z2lkOi8vc2hvcGlmeS9DaGVja291dC8xMjM0NQ==",
            "checkout_url": f"https://{self.store_domain}/checkout/cn/Z2lkOi8vc2hvcGlmeS9DaGVja291dC8xMjM0NQ==",
            "total": str(cart.subtotal),
            "currency": DEFAULT_CURRENCY,
        }


# ============================================================================
# Australia Post Shipping Integration
# ============================================================================


class AustraliaPostShipping:
    """
    Australia Post shipping calculator and tracking.

    Provides:
    - Shipping rate calculation
    - Parcel tracking
    - Delivery estimates
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://digitalapi.auspost.com.au"

    async def calculate_shipping(
        self,
        from_postcode: str,
        to_postcode: str,
        weight_kg: float,
        length_cm: float = 20,
        width_cm: float = 15,
        height_cm: float = 10,
    ) -> List[Dict]:
        """
        Calculate shipping options and rates.

        Returns list of shipping options with prices and delivery times.
        """
        # Mock shipping options - integrate with AusPost PAC API in production
        options = [
            {
                "service_code": "AUS_PARCEL_REGULAR",
                "service_name": "Australia Post Parcel Post",
                "price": Decimal("9.95"),
                "estimated_days": "3-5 business days",
            },
            {
                "service_code": "AUS_PARCEL_EXPRESS",
                "service_name": "Australia Post Express Post",
                "price": Decimal("14.95"),
                "estimated_days": "1-2 business days",
            },
        ]

        # Adjust for remote areas
        remote_postcodes = ["0800", "0810", "0820"]  # NT examples
        if to_postcode[:4] in remote_postcodes:
            for opt in options:
                opt["price"] += Decimal("5.00")
                opt["estimated_days"] = (
                    opt["estimated_days"].replace("1-2", "2-4").replace("3-5", "5-8")
                )

        return options

    async def track_parcel(self, tracking_number: str) -> Dict:
        """
        Get tracking information for a parcel.

        Returns current status and tracking events.
        """
        # Mock tracking data - use AusPost Track API in production
        return {
            "tracking_number": tracking_number,
            "status": "IN_TRANSIT",
            "status_description": "In transit to delivery facility",
            "estimated_delivery": (datetime.now() + timedelta(days=2)).isoformat(),
            "events": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "location": "Sydney Parcel Facility",
                    "description": "Parcel has departed facility",
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=12)).isoformat(),
                    "location": "Sydney",
                    "description": "Parcel received at facility",
                },
            ],
        }


# ============================================================================
# Shopify Store Assistant Tools
# ============================================================================


def create_shopify_tools(
    admin_api: ShopifyAdminAPI,
    storefront_api: ShopifyStorefrontAPI,
    shipping: AustraliaPostShipping,
    session: CustomerSession,
) -> List[Tool]:
    """Create tools for the Shopify assistant."""

    async def search_products(
        query: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        in_stock_only: bool = True,
    ) -> str:
        """
        Search for products using natural language.

        Args:
            query: What to search for (e.g., "blue dress", "gardening tools")
            max_price: Maximum price filter
            min_price: Minimum price filter
            in_stock_only: Only show available products
        """
        filters = {"in_stock": in_stock_only}
        if max_price:
            filters["price_max"] = max_price
        if min_price:
            filters["price_min"] = min_price

        products = await storefront_api.search_products(query, filters)

        if not products:
            return "I couldn't find any products matching that. Would you like to try different search terms?"

        # Remember products for "that one" references
        for product in products:
            session.remember_product(product["id"])

        session.search_context = {"query": query, "results": products}

        result_lines = [f"Found {len(products)} products:\n"]
        for i, product in enumerate(products, 1):
            price = product.get("price", "N/A")
            stock = "✓ In stock" if product.get("in_stock") else "Out of stock"
            result_lines.append(f"{i}. **{product['title']}** - ${price} AUD ({stock})")
            if product.get("description"):
                result_lines.append(f"   {product['description'][:100]}...")

        return "\n".join(result_lines)

    async def get_product_details(product_id: str) -> str:
        """
        Get detailed information about a specific product.

        Args:
            product_id: Shopify product ID
        """
        product = await storefront_api.get_product(product_id)
        if not product:
            return "Product not found."

        session.remember_product(product_id)

        details = [
            f"**{product['title']}**",
            f"Price: ${product.get('price', 'N/A')} AUD",
            f"\n{product.get('description', 'No description available')}",
        ]

        if product.get("variants"):
            variants = product["variants"]
            if len(variants) > 1:
                details.append(
                    f"\nAvailable in: {', '.join(v['title'] for v in variants)}"
                )

        return "\n".join(details)

    async def add_to_cart(
        product_reference: str, quantity: int = 1, variant: Optional[str] = None
    ) -> str:
        """
        Add a product to the shopping cart.

        Args:
            product_reference: Product ID, number from search, or "that one"
            quantity: How many to add
            variant: Specific variant (size, color, etc.)
        """
        # Handle "that one", "the first one", etc.
        product_id = None

        if product_reference.lower() in ["that", "that one", "it"]:
            if session.last_viewed_products:
                product_id = session.last_viewed_products[0]
        elif product_reference.isdigit():
            # Reference by search result number
            idx = int(product_reference) - 1
            if session.search_context and idx < len(
                session.search_context.get("results", [])
            ):
                product_id = session.search_context["results"][idx]["id"]
        else:
            product_id = product_reference

        if not product_id:
            return "I'm not sure which product you mean. Could you specify the product name or number?"

        # Get product details
        product = await storefront_api.get_product(product_id)
        if not product:
            return "Sorry, I couldn't find that product."

        # Find variant
        variants = product.get("variants", [])
        selected_variant = variants[0] if variants else None

        if variant and len(variants) > 1:
            for v in variants:
                if variant.lower() in v.get("title", "").lower():
                    selected_variant = v
                    break

        if not selected_variant:
            return "Sorry, that variant isn't available."

        if not selected_variant.get("availableForSale", True):
            return f"Sorry, {product['title']} is currently out of stock."

        # Add to cart
        cart_item = CartItem(
            variant_id=selected_variant["id"],
            product_id=product_id,
            title=product["title"],
            variant_title=selected_variant.get("title"),
            quantity=quantity,
            price=Decimal(selected_variant.get("price", "0")),
            image_url=(
                product.get("images", [{}])[0].get("url")
                if product.get("images")
                else None
            ),
        )

        session.cart.add_item(cart_item)

        response = f"Added {quantity}x {product['title']}"
        if cart_item.variant_title and cart_item.variant_title != "Default":
            response += f" ({cart_item.variant_title})"
        response += " to your cart.\n\n"
        response += f"Cart total: ${session.cart.subtotal:.2f} AUD ({session.cart.item_count} items)"

        return response

    async def view_cart() -> str:
        """View current shopping cart contents."""
        if not session.cart.items:
            return "Your cart is empty. Would you like to browse our products?"

        lines = ["**Your Cart:**\n"]
        for i, item in enumerate(session.cart.items, 1):
            variant_info = (
                f" ({item.variant_title})"
                if item.variant_title and item.variant_title != "Default"
                else ""
            )
            lines.append(f"{i}. {item.title}{variant_info}")
            lines.append(
                f"   Qty: {item.quantity} × ${item.price:.2f} = ${item.line_total:.2f}"
            )

        lines.append(f"\n**Subtotal:** ${session.cart.subtotal:.2f} AUD")

        if session.cart.discount_code:
            lines.append(
                f"Discount ({session.cart.discount_code}): -${session.cart.discount_amount:.2f}"
            )

        # Estimate shipping
        if session.shipping_postcode:
            shipping_options = await shipping.calculate_shipping(
                "3000", session.shipping_postcode, 1.0
            )
            if shipping_options:
                cheapest = min(shipping_options, key=lambda x: x["price"])
                lines.append(
                    f"Shipping estimate: ${cheapest['price']:.2f} ({cheapest['estimated_days']})"
                )
        else:
            lines.append("Shipping: Calculated at checkout")

        return "\n".join(lines)

    async def remove_from_cart(item_reference: str) -> str:
        """
        Remove an item from the cart.

        Args:
            item_reference: Item number (1, 2, 3) or "last" or product name
        """
        if not session.cart.items:
            return "Your cart is already empty."

        index = None
        if item_reference.lower() in ["last", "the last one"]:
            index = len(session.cart.items)
        elif item_reference.isdigit():
            index = int(item_reference)
        else:
            # Search by name
            for i, item in enumerate(session.cart.items, 1):
                if item_reference.lower() in item.title.lower():
                    index = i
                    break

        if index is None:
            return "I couldn't find that item in your cart. Say 'view cart' to see your items."

        removed = session.cart.remove_item(index)
        if removed:
            return f"Removed {removed.title} from your cart.\nCart total: ${session.cart.subtotal:.2f} AUD"
        else:
            return "Invalid item number. Please check your cart and try again."

    async def update_cart_quantity(item_number: int, new_quantity: int) -> str:
        """
        Update quantity for a cart item.

        Args:
            item_number: Position in cart (1, 2, 3, etc.)
            new_quantity: New quantity (0 to remove)
        """
        if session.cart.update_quantity(item_number, new_quantity):
            if new_quantity <= 0:
                return "Item removed from cart."
            return f"Updated quantity to {new_quantity}. Cart total: ${session.cart.subtotal:.2f} AUD"
        return "Invalid item number."

    async def apply_discount_code(code: str) -> str:
        """
        Apply a discount code to the cart.

        Args:
            code: Discount code to apply
        """
        # In production, validate with Shopify API
        valid_codes = {"WELCOME10": Decimal("10"), "SAVE20": Decimal("20")}

        code_upper = code.upper()
        if code_upper in valid_codes:
            session.cart.discount_code = code_upper
            session.cart.discount_amount = valid_codes[code_upper]
            return f"Code {code_upper} applied! You'll save ${valid_codes[code_upper]:.2f}."
        else:
            return "Sorry, that discount code isn't valid or has expired."

    async def proceed_to_checkout(email: Optional[str] = None) -> str:
        """
        Create checkout and get payment link.

        Args:
            email: Customer email for order confirmation
        """
        if not session.cart.items:
            return "Your cart is empty. Add some products first!"

        checkout_email = email or session.email
        if not checkout_email:
            return "I'll need your email address to create the checkout. What's your email?"

        checkout = await storefront_api.create_checkout(session.cart, checkout_email)

        return f"""
Your order is ready for payment!

**Order Summary:**
{session.cart.item_count} items totalling ${checkout['total']} {checkout['currency']}

**Checkout Link:**
{checkout['checkout_url']}

Click the link above to complete your purchase securely via Shopify.
The link is valid for 24 hours.

Need help? Just ask!
"""

    async def track_order(
        order_number: Optional[str] = None, email: Optional[str] = None
    ) -> str:
        """
        Track an order status.

        Args:
            order_number: Order number (e.g., #1234)
            email: Email used for the order
        """
        if order_number:
            # Clean order number
            order_id = order_number.replace("#", "").strip()
            order = await admin_api.get_order(order_id)

            if not order:
                return f"I couldn't find order {order_number}. Please check the number and try again."

            status = order.get("displayFulfillmentStatus", "PENDING")

            response = [f"**Order {order.get('name', order_number)}**"]
            response.append(f"Status: {status.replace('_', ' ').title()}")

            if order.get("fulfillments"):
                for fulfillment in order["fulfillments"]:
                    tracking = fulfillment.get("trackingInfo", [])
                    if tracking:
                        track_info = tracking[0]
                        response.append(
                            f"\nTracking: {track_info.get('company', 'Carrier')}"
                        )
                        response.append(f"Number: {track_info.get('number', 'N/A')}")
                        if track_info.get("url"):
                            response.append(f"Track here: {track_info['url']}")

                    if fulfillment.get("estimatedDeliveryAt"):
                        response.append(
                            f"Estimated delivery: {fulfillment['estimatedDeliveryAt']}"
                        )

            return "\n".join(response)

        elif email or session.email:
            # Look up by email
            lookup_email = email or session.email
            orders = await admin_api.get_orders_by_email(lookup_email, limit=5)

            if not orders:
                return f"No orders found for {lookup_email}."

            response = [f"Recent orders for {lookup_email}:\n"]
            for order in orders:
                response.append(
                    f"• {order['name']} - {order['displayFulfillmentStatus']} - ${order['totalPriceSet']['shopMoney']['amount']}"
                )

            response.append("\nTell me an order number for more details.")
            return "\n".join(response)

        else:
            return "Please provide your order number (e.g., #1234) or email address to look up your orders."

    async def get_shipping_estimate(postcode: str) -> str:
        """
        Get shipping cost estimate for an Australian postcode.

        Args:
            postcode: Australian postcode (e.g., 5000 for Adelaide)
        """
        session.shipping_postcode = postcode

        # Assume 1kg average weight
        options = await shipping.calculate_shipping("3000", postcode, 1.0)

        response = [f"**Shipping to {postcode}:**\n"]
        for opt in options:
            response.append(f"• {opt['service_name']}: ${opt['price']:.2f}")
            response.append(f"  Delivery: {opt['estimated_days']}")

        response.append("\nFinal shipping calculated at checkout based on cart weight.")
        return "\n".join(response)

    async def initiate_return(
        order_number: str, reason: str, items: Optional[str] = None
    ) -> str:
        """
        Start a return request.

        Args:
            order_number: Order to return from
            reason: Why returning (damaged, wrong size, changed mind, etc.)
            items: Which items to return (optional, defaults to all)
        """
        order_id = order_number.replace("#", "").strip()

        result = await admin_api.create_return(order_id, [], reason)

        if result["success"]:
            return f"""
Return request created!

**Return ID:** {result['return_id']}

Next steps:
1. You'll receive a return shipping label via email
2. Pack items securely in original packaging if possible
3. Drop off at any Australia Post outlet

Refund will be processed within 5-7 business days of receiving items.

Is there anything else I can help with?
"""
        else:
            return "Sorry, I couldn't process that return. Please contact our support team."

    async def get_store_policy(policy_type: str) -> str:
        """
        Get store policy information.

        Args:
            policy_type: One of: returns, shipping, privacy, terms
        """
        policies = {
            "returns": """
**Returns Policy**

• 30-day returns on all items
• Items must be unused with tags attached
• Free return shipping on faulty items
• Refund to original payment method
• Exchanges available for size/colour

To start a return, just say "I want to return my order" with your order number.
""",
            "shipping": """
**Shipping Policy**

• FREE shipping on orders over $100
• Standard shipping: $9.95 (3-5 business days)
• Express shipping: $14.95 (1-2 business days)
• We ship Australia-wide via Australia Post
• Remote areas may take additional time
• International shipping available on request
""",
            "privacy": """
**Privacy Policy Summary**

• We only collect data needed to process orders
• Payment info is handled securely by Shopify
• We never sell your personal information
• You can request data deletion anytime
• Cookies used for site functionality

Full privacy policy at our website.
""",
            "terms": """
**Terms of Service Summary**

• All prices in AUD, GST inclusive
• Stock subject to availability
• We reserve right to cancel suspicious orders
• Product images are representative only
• Errors in pricing will be corrected

Full terms at our website.
""",
        }

        policy = policies.get(policy_type.lower())
        if policy:
            return policy
        else:
            return "Available policies: returns, shipping, privacy, terms\nWhich would you like to know about?"

    async def get_collections() -> str:
        """Browse available product collections/categories."""
        collections = await storefront_api.get_collections()

        if not collections:
            return "Our store categories aren't loading right now. Try searching for specific products instead."

        response = ["**Shop by Category:**\n"]
        for coll in collections:
            response.append(f"• **{coll['title']}**")
            if coll.get("description"):
                response.append(f"  {coll['description'][:80]}...")

        response.append(
            "\nTell me which category interests you, or describe what you're looking for!"
        )
        return "\n".join(response)

    # Build and return tools
    return [
        Tool(
            name="search_products",
            description="Search for products by description, category, or features. Use for queries like 'show me dresses', 'gardening tools', 'gifts for mum'",
            function=search_products,
        ),
        Tool(
            name="get_product_details",
            description="Get detailed information about a specific product including variants, availability, and full description",
            function=get_product_details,
        ),
        Tool(
            name="add_to_cart",
            description="Add a product to the shopping cart. Handles 'that one', 'the first one', or product numbers from search results",
            function=add_to_cart,
        ),
        Tool(
            name="view_cart",
            description="Show current cart contents with prices and totals",
            function=view_cart,
        ),
        Tool(
            name="remove_from_cart",
            description="Remove an item from the cart by number, name, or 'last'",
            function=remove_from_cart,
        ),
        Tool(
            name="update_cart_quantity",
            description="Change quantity of a cart item",
            function=update_cart_quantity,
        ),
        Tool(
            name="apply_discount_code",
            description="Apply a promotional or discount code to the order",
            function=apply_discount_code,
        ),
        Tool(
            name="proceed_to_checkout",
            description="Create checkout and get secure payment link",
            function=proceed_to_checkout,
        ),
        Tool(
            name="track_order",
            description="Check order status and tracking information",
            function=track_order,
        ),
        Tool(
            name="get_shipping_estimate",
            description="Calculate shipping costs to an Australian postcode",
            function=get_shipping_estimate,
        ),
        Tool(
            name="initiate_return",
            description="Start a return or exchange request for an order",
            function=initiate_return,
        ),
        Tool(
            name="get_store_policy",
            description="Get information about returns, shipping, privacy, or terms policies",
            function=get_store_policy,
        ),
        Tool(
            name="browse_categories",
            description="Show available product categories/collections",
            function=get_collections,
        ),
    ]


# ============================================================================
# Webhook Handler
# ============================================================================


class ShopifyWebhookHandler:
    """
    Handle Shopify webhooks for real-time order updates.

    Useful for:
    - Order status changes
    - Inventory updates
    - Abandoned cart recovery
    """

    def __init__(self, webhook_secret: str):
        self.webhook_secret = webhook_secret

    def verify_webhook(self, data: bytes, hmac_header: str) -> bool:
        """Verify webhook signature from Shopify."""
        digest = hmac.new(
            self.webhook_secret.encode(), data, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, hmac_header)

    async def handle_order_fulfilled(self, payload: Dict) -> None:
        """Handle order fulfillment webhook - send tracking info."""
        order_id = payload.get("id")
        payload.get("email")
        tracking = payload.get("fulfillments", [{}])[0].get("tracking_number")

        # In production, send notification via email/SMS
        print(f"Order {order_id} shipped! Tracking: {tracking}")

    async def handle_abandoned_checkout(self, payload: Dict) -> None:
        """Handle abandoned checkout - trigger recovery flow."""
        checkout_id = payload.get("id")
        payload.get("email")
        cart_value = payload.get("total_price")

        # In production, queue abandoned cart email
        print(f"Abandoned checkout {checkout_id} worth ${cart_value}")


# ============================================================================
# Main Assistant
# ============================================================================

SYSTEM_PROMPT = """You are a friendly shopping assistant for an Australian e-commerce store.

Your personality:
- Warm and helpful, like a knowledgeable friend who works at the store
- Proactive in suggesting products and answering questions
- Mindful of Australian context (AUD, Australia Post, local references)

Guidelines:
1. **Product Discovery**: Help customers find what they need through natural conversation
2. **Cart Management**: Make adding, removing, and modifying cart items easy
3. **Order Support**: Track orders, process returns, answer policy questions
4. **Checkout**: Guide customers smoothly to purchase when ready

When suggesting products:
- Understand the context (gift, personal use, occasion)
- Offer alternatives at different price points
- Highlight bestsellers and customer favourites
- Mention relevant details (shipping time, stock levels)

Keep responses concise but friendly. Use Australian English spelling (colour, favourite, organisation).

Available tools let you search products, manage cart, track orders, and more. Use them proactively to help customers.
"""


async def create_shopify_assistant() -> AgenticBrain:
    """Create and configure the Shopify store assistant."""

    # Initialize API clients
    admin_api = ShopifyAdminAPI(SHOPIFY_STORE_DOMAIN, SHOPIFY_ADMIN_TOKEN)
    storefront_api = ShopifyStorefrontAPI(
        SHOPIFY_STORE_DOMAIN, SHOPIFY_STOREFRONT_TOKEN
    )
    shipping = AustraliaPostShipping(AUSTRALIA_POST_API_KEY)

    # Create customer session
    session = CustomerSession()

    # Create tools
    tools = create_shopify_tools(admin_api, storefront_api, shipping, session)

    # Create brain
    brain = AgenticBrain(
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        model="gpt-4o-mini",  # Cost-effective for commerce
    )

    return brain


async def main():
    """Demo the Shopify assistant."""
    brain = await create_shopify_assistant()

    print("🛒 Shopify Store Assistant")
    print("=" * 50)
    print("I'm your shopping assistant! Ask me about products,")
    print("manage your cart, or get help with orders.")
    print("Type 'quit' to exit.\n")

    # Demo conversation
    demo_messages = [
        "I'm looking for a birthday gift for my mum",
        "She likes gardening",
        "Add the garden tool set to my cart",
        "What's in my cart?",
        "I'm ready to checkout",
    ]

    for user_input in demo_messages:
        print(f"You: {user_input}")
        response = await brain.chat(user_input)
        print(f"Assistant: {response}\n")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
