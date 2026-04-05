# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
WooCommerce Store API endpoints available to guest (unauthenticated) users.

The WooCommerce Store API provides a session-based cart system that works
without authentication - perfect for guest shopping experiences.

Key Insight (Joseph):
GUEST role should NOT mean "no API access". It should mirror what the
platform allows for unauthenticated users. WooCommerce guests can:
- Browse products
- View product details
- Add to cart (session-based)
- Update cart quantities
- Remove from cart
- Checkout as guest
- View shipping options
- Apply coupons

This is context-dependent - different platforms allow different guest capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..security.api_access import APIAccessController

# WooCommerce Store API endpoints that guests can access
WOOCOMMERCE_GUEST_ENDPOINTS = {
    # Product browsing - public access
    "GET /wp-json/wc/store/products": "List products (guest)",
    "GET /wp-json/wc/store/products/{id}": "Get product details (guest)",
    "GET /wp-json/wc/store/products/categories": "List product categories (guest)",
    "GET /wp-json/wc/store/products/tags": "List product tags (guest)",
    "GET /wp-json/wc/store/products/attributes": "List product attributes (guest)",
    # Cart operations - session-based, no authentication required
    "GET /wp-json/wc/store/cart": "View cart (guest session)",
    "POST /wp-json/wc/store/cart/add-item": "Add item to cart (guest)",
    "POST /wp-json/wc/store/cart/remove-item": "Remove item from cart (guest)",
    "POST /wp-json/wc/store/cart/update-item": "Update cart item quantity (guest)",
    "POST /wp-json/wc/store/cart/apply-coupon": "Apply coupon code (guest)",
    "POST /wp-json/wc/store/cart/remove-coupon": "Remove coupon code (guest)",
    # Checkout - guest checkout without account
    "GET /wp-json/wc/store/checkout": "Get checkout form data (guest)",
    "POST /wp-json/wc/store/checkout": "Process guest checkout (create order)",
    # Shipping and payment
    "GET /wp-json/wc/store/cart/shipping-rates": "Get shipping rates (guest)",
    "POST /wp-json/wc/store/cart/select-shipping-rate": "Select shipping method (guest)",
    "POST /wp-json/wc/store/cart/update-customer": "Update customer details (guest)",
}


@dataclass
class GuestCartItem:
    """An item in a guest cart."""

    product_id: int
    quantity: int
    variation_id: Optional[int] = None
    variation: Optional[Dict[str, Any]] = None

    def to_api_dict(self) -> Dict[str, Any]:
        """Convert to WooCommerce Store API format."""
        data = {
            "id": self.product_id,
            "quantity": self.quantity,
        }

        if self.variation_id:
            data["variation"] = [
                {
                    "attribute": key,
                    "value": value,
                }
                for key, value in (self.variation or {}).items()
            ]

        return data


@dataclass
class GuestCheckoutInfo:
    """Billing and shipping information for guest checkout."""

    # Billing
    billing_first_name: str
    billing_last_name: str
    billing_email: str
    billing_phone: str
    billing_address_1: str
    billing_city: str
    billing_state: str
    billing_postcode: str
    billing_country: str
    billing_address_2: Optional[str] = None

    # Shipping (optional - can use billing)
    shipping_first_name: Optional[str] = None
    shipping_last_name: Optional[str] = None
    shipping_address_1: Optional[str] = None
    shipping_address_2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_postcode: Optional[str] = None
    shipping_country: Optional[str] = None

    def to_api_dict(self) -> Dict[str, Any]:
        """Convert to WooCommerce Store API format."""
        data = {
            "billing_address": {
                "first_name": self.billing_first_name,
                "last_name": self.billing_last_name,
                "email": self.billing_email,
                "phone": self.billing_phone,
                "address_1": self.billing_address_1,
                "city": self.billing_city,
                "state": self.billing_state,
                "postcode": self.billing_postcode,
                "country": self.billing_country,
            }
        }

        if self.billing_address_2:
            data["billing_address"]["address_2"] = self.billing_address_2

        # Add shipping if different from billing
        if self.shipping_first_name:
            data["shipping_address"] = {
                "first_name": self.shipping_first_name,
                "last_name": self.shipping_last_name,
                "address_1": self.shipping_address_1,
                "city": self.shipping_city,
                "state": self.shipping_state,
                "postcode": self.shipping_postcode,
                "country": self.shipping_country,
            }

            if self.shipping_address_2:
                data["shipping_address"]["address_2"] = self.shipping_address_2

        return data


class WooCommerceGuestAPI:
    """
    WooCommerce Store API client for guest (unauthenticated) operations.

    This API uses session-based cart management, allowing guests to shop
    without creating an account. The cart is stored in browser session cookies.

    Key Security Notes:
    - NO authentication required for these endpoints
    - Cart is session-based (stored in cookies)
    - Guest checkout creates order without account
    - Rate limiting still applies
    """

    def __init__(
        self,
        store_url: str,
        api_controller: APIAccessController,
    ):
        """
        Initialize WooCommerce Guest API client.

        Args:
            store_url: WooCommerce store URL (e.g., "https://example.com")
            api_controller: API access controller (for rate limiting)
        """
        self.store_url = store_url.rstrip("/")
        self.api_controller = api_controller
        self.cart_token = None  # Session-based cart token (from cookies)

    # --- Product Browsing (Public) ---

    async def browse_products(
        self,
        per_page: int = 10,
        page: int = 1,
        search: Optional[str] = None,
        category: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Browse products - available to guests.

        Args:
            per_page: Products per page
            page: Page number
            search: Search query
            category: Filter by category ID
            min_price: Minimum price filter
            max_price: Maximum price filter

        Returns:
            List of products
        """
        params = {
            "per_page": per_page,
            "page": page,
        }

        if search:
            params["search"] = search
        if category:
            params["category"] = category
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price

        response = await self.api_controller.call_api(
            "woocommerce_store",
            "GET",
            "/products",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_product(self, product_id: int) -> Dict[str, Any]:
        """
        Get product details - available to guests.

        Args:
            product_id: Product ID

        Returns:
            Product data
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "GET",
            f"/products/{product_id}",
        )
        response.raise_for_status()
        return response.json()

    async def list_categories(self) -> List[Dict[str, Any]]:
        """List product categories - available to guests."""
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "GET",
            "/products/categories",
        )
        response.raise_for_status()
        return response.json()

    # --- Cart Operations (Session-based) ---

    async def get_cart(self) -> Dict[str, Any]:
        """
        Get current cart contents - available to guests.

        Cart is stored in session cookies, no authentication required.

        Returns:
            Cart data including items, totals, shipping
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "GET",
            "/cart",
        )
        response.raise_for_status()
        return response.json()

    async def add_to_cart(
        self,
        product_id: int,
        quantity: int = 1,
        variation_id: Optional[int] = None,
        variation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add product to cart - available to guests.

        Args:
            product_id: Product ID to add
            quantity: Quantity to add
            variation_id: Variation ID (for variable products)
            variation: Variation attributes (e.g., {"color": "red", "size": "M"})

        Returns:
            Updated cart data
        """
        item = GuestCartItem(
            product_id=product_id,
            quantity=quantity,
            variation_id=variation_id,
            variation=variation,
        )

        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/cart/add-item",
            json=item.to_api_dict(),
        )
        response.raise_for_status()
        return response.json()

    async def update_cart_item(
        self,
        cart_item_key: str,
        quantity: int,
    ) -> Dict[str, Any]:
        """
        Update cart item quantity - available to guests.

        Args:
            cart_item_key: Cart item key (from cart response)
            quantity: New quantity

        Returns:
            Updated cart data
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/cart/update-item",
            json={
                "key": cart_item_key,
                "quantity": quantity,
            },
        )
        response.raise_for_status()
        return response.json()

    async def remove_from_cart(self, cart_item_key: str) -> Dict[str, Any]:
        """
        Remove item from cart - available to guests.

        Args:
            cart_item_key: Cart item key (from cart response)

        Returns:
            Updated cart data
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/cart/remove-item",
            json={"key": cart_item_key},
        )
        response.raise_for_status()
        return response.json()

    async def apply_coupon(self, coupon_code: str) -> Dict[str, Any]:
        """
        Apply coupon code to cart - available to guests.

        Args:
            coupon_code: Coupon code to apply

        Returns:
            Updated cart data with discount applied
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/cart/apply-coupon",
            json={"code": coupon_code},
        )
        response.raise_for_status()
        return response.json()

    async def remove_coupon(self, coupon_code: str) -> Dict[str, Any]:
        """
        Remove coupon code from cart - available to guests.

        Args:
            coupon_code: Coupon code to remove

        Returns:
            Updated cart data
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/cart/remove-coupon",
            json={"code": coupon_code},
        )
        response.raise_for_status()
        return response.json()

    # --- Shipping and Customer ---

    async def get_shipping_rates(self) -> Dict[str, Any]:
        """
        Get available shipping rates - available to guests.

        Returns:
            Shipping rates based on cart and destination
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "GET",
            "/cart/shipping-rates",
        )
        response.raise_for_status()
        return response.json()

    async def select_shipping_rate(
        self,
        package_id: str,
        rate_id: str,
    ) -> Dict[str, Any]:
        """
        Select shipping method - available to guests.

        Args:
            package_id: Shipping package ID
            rate_id: Shipping rate ID to select

        Returns:
            Updated cart data
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/cart/select-shipping-rate",
            json={
                "package_id": package_id,
                "rate_id": rate_id,
            },
        )
        response.raise_for_status()
        return response.json()

    async def update_customer(
        self,
        billing_address: Optional[Dict[str, str]] = None,
        shipping_address: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Update customer details for shipping calculation - available to guests.

        Args:
            billing_address: Billing address data
            shipping_address: Shipping address data

        Returns:
            Updated cart data with recalculated shipping
        """
        data = {}

        if billing_address:
            data["billing_address"] = billing_address
        if shipping_address:
            data["shipping_address"] = shipping_address

        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/cart/update-customer",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    # --- Checkout (Guest Checkout) ---

    async def get_checkout_form(self) -> Dict[str, Any]:
        """
        Get checkout form data - available to guests.

        Returns:
            Checkout form fields and requirements
        """
        response = await self.api_controller.call_api(
            "woocommerce_store",
            "GET",
            "/checkout",
        )
        response.raise_for_status()
        return response.json()

    async def checkout_as_guest(
        self,
        checkout_info: GuestCheckoutInfo,
        payment_method: str,
        create_account: bool = False,
        account_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete guest checkout - available to guests.

        Creates an order without requiring account login.

        Args:
            checkout_info: Billing and shipping information
            payment_method: Payment method ID
            create_account: Whether to create account during checkout
            account_password: Password if creating account

        Returns:
            Order data
        """
        data = {
            **checkout_info.to_api_dict(),
            "payment_method": payment_method,
        }

        if create_account:
            data["create_account"] = True
            if account_password:
                data["account_password"] = account_password

        response = await self.api_controller.call_api(
            "woocommerce_store",
            "POST",
            "/checkout",
            json=data,
        )
        response.raise_for_status()
        return response.json()


# Helper function to create guest API client
def create_guest_api_client(
    store_url: str,
    api_controller: APIAccessController,
) -> WooCommerceGuestAPI:
    """
    Create a WooCommerce Guest API client.

    Args:
        store_url: WooCommerce store URL
        api_controller: API access controller (must allow guest APIs)

    Returns:
        Configured WooCommerceGuestAPI client
    """
    return WooCommerceGuestAPI(
        store_url=store_url,
        api_controller=api_controller,
    )
