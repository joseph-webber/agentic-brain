# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
WooCommerce REST API integration.

Access WooCommerce through its REST API, not direct database access.
Permissions are controlled by WooCommerce user capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..security.api_access import (
    APIAccessController,
    APIEndpoint,
    APIScope,
    AuthType,
    SecurityViolation,
)
from ..security.roles import SecurityRole


class WooCommerceRole(Enum):
    """WooCommerce user roles with increasing privileges."""

    CUSTOMER = "customer"  # Can view own orders
    SHOP_MANAGER = "shop_manager"  # Can manage products and orders
    ADMINISTRATOR = "administrator"  # Full WooCommerce access


@dataclass
class WooCommerceCapabilities:
    """WooCommerce capabilities based on role."""

    # Orders
    can_view_orders: bool = False
    can_view_own_orders: bool = True  # Customers can always view their own
    can_create_orders: bool = False
    can_edit_orders: bool = False
    can_delete_orders: bool = False

    # Products
    can_view_products: bool = True  # Everyone can view products
    can_create_products: bool = False
    can_edit_products: bool = False
    can_delete_products: bool = False

    # Customers
    can_view_customers: bool = False
    can_create_customers: bool = False
    can_edit_customers: bool = False

    # Reports
    can_view_reports: bool = False

    # Settings
    can_manage_settings: bool = False

    @classmethod
    def from_role(cls, role: WooCommerceRole) -> "WooCommerceCapabilities":
        """Get capabilities for a WooCommerce role."""

        if role == WooCommerceRole.CUSTOMER:
            return cls(
                can_view_own_orders=True,
                can_view_products=True,
            )

        elif role == WooCommerceRole.SHOP_MANAGER:
            return cls(
                can_view_orders=True,
                can_view_own_orders=True,
                can_create_orders=True,
                can_edit_orders=True,
                can_view_products=True,
                can_create_products=True,
                can_edit_products=True,
                can_delete_products=True,
                can_view_customers=True,
                can_view_reports=True,
            )

        elif role == WooCommerceRole.ADMINISTRATOR:
            return cls(
                can_view_orders=True,
                can_view_own_orders=True,
                can_create_orders=True,
                can_edit_orders=True,
                can_delete_orders=True,
                can_view_products=True,
                can_create_products=True,
                can_edit_products=True,
                can_delete_products=True,
                can_view_customers=True,
                can_create_customers=True,
                can_edit_customers=True,
                can_view_reports=True,
                can_manage_settings=True,
            )

        return cls()


class WooCommerceAPI:
    """
    Access WooCommerce through REST API.

    Key security principle: Customers can only see their own orders.
    The API enforces this - we don't bypass it.
    """

    def __init__(
        self,
        site_url: str,
        consumer_key: str,
        consumer_secret: str,
        wc_role: WooCommerceRole,
        api_controller: APIAccessController,
        customer_id: Optional[int] = None,
    ):
        """
        Initialize WooCommerce API client.

        Args:
            site_url: WooCommerce site URL (e.g., "https://example.com")
            consumer_key: WooCommerce API consumer key
            consumer_secret: WooCommerce API consumer secret
            wc_role: WooCommerce role for this user
            api_controller: API access controller (enforces chatbot role)
            customer_id: Customer ID (required for CUSTOMER role)
        """
        self.site_url = site_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.wc_role = wc_role
        self.capabilities = WooCommerceCapabilities.from_role(wc_role)
        self.api_controller = api_controller
        self.customer_id = customer_id

        # Customers must have a customer_id
        if wc_role == WooCommerceRole.CUSTOMER and customer_id is None:
            raise ValueError("customer_id required for CUSTOMER role")

        # Determine allowed API scopes based on WooCommerce role
        scopes = [APIScope.READ]  # Everyone can read products

        if (
            self.capabilities.can_create_orders
            or self.capabilities.can_create_products
            or self.capabilities.can_edit_orders
            or self.capabilities.can_edit_products
        ):
            scopes.append(APIScope.WRITE)

        if self.capabilities.can_delete_orders or self.capabilities.can_delete_products:
            scopes.append(APIScope.DELETE)

        if wc_role == WooCommerceRole.ADMINISTRATOR:
            scopes.append(APIScope.ADMIN)

        # Register WooCommerce API
        endpoint = APIEndpoint(
            name="woocommerce",
            base_url=f"{self.site_url}/wp-json/wc/v3",
            auth_type=AuthType.WOOCOMMERCE,
            allowed_scopes=scopes,
            rate_limit=60,  # 60 requests per minute
            api_role=wc_role.value,
            description=f"WooCommerce REST API ({wc_role.value} role)",
        )

        credentials = {
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
        }

        api_controller.register_api(endpoint, credentials)

    # --- Products ---

    async def list_products(
        self,
        per_page: int = 10,
        page: int = 1,
        search: Optional[str] = None,
        category: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List products.

        Args:
            per_page: Products per page
            page: Page number
            search: Search query
            category: Filter by category ID

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

        response = await self.api_controller.call_api(
            "woocommerce",
            "GET",
            "/products",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_product(self, product_id: int) -> Dict[str, Any]:
        """Get a single product by ID."""
        response = await self.api_controller.call_api(
            "woocommerce",
            "GET",
            f"/products/{product_id}",
        )
        response.raise_for_status()
        return response.json()

    async def create_product(
        self,
        name: str,
        type: str = "simple",
        regular_price: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a new product.

        Args:
            name: Product name
            type: Product type (simple, grouped, external, variable)
            regular_price: Regular price
            **kwargs: Additional product fields

        Returns:
            Created product data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_create_products:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot create products"
            )

        data = {"name": name, "type": type, **kwargs}

        if regular_price:
            data["regular_price"] = regular_price

        response = await self.api_controller.call_api(
            "woocommerce",
            "POST",
            "/products",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    async def update_product(self, product_id: int, **fields) -> Dict[str, Any]:
        """
        Update a product.

        Args:
            product_id: Product ID to update
            **fields: Fields to update

        Returns:
            Updated product data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_edit_products:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot edit products"
            )

        response = await self.api_controller.call_api(
            "woocommerce",
            "PUT",
            f"/products/{product_id}",
            json=fields,
        )
        response.raise_for_status()
        return response.json()

    async def delete_product(
        self, product_id: int, force: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a product.

        Args:
            product_id: Product ID to delete
            force: Bypass trash and force deletion

        Returns:
            Deleted product data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_delete_products:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot delete products"
            )

        params = {"force": force}

        response = await self.api_controller.call_api(
            "woocommerce",
            "DELETE",
            f"/products/{product_id}",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    # --- Orders ---

    async def list_orders(
        self,
        per_page: int = 10,
        page: int = 1,
        status: Optional[str] = None,
        customer: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List orders.

        SECURITY: Customers can only see their own orders.

        Args:
            per_page: Orders per page
            page: Page number
            status: Filter by status
            customer: Filter by customer ID

        Returns:
            List of orders

        Raises:
            SecurityViolation: If customer tries to view other orders
        """
        # CRITICAL: Customers can only view their own orders
        if self.wc_role == WooCommerceRole.CUSTOMER:
            if customer is not None and customer != self.customer_id:
                raise SecurityViolation("Customers can only view their own orders")
            # Force filter to this customer
            customer = self.customer_id

        params = {
            "per_page": per_page,
            "page": page,
        }

        if status:
            params["status"] = status
        if customer:
            params["customer"] = customer

        response = await self.api_controller.call_api(
            "woocommerce",
            "GET",
            "/orders",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_order(self, order_id: int) -> Dict[str, Any]:
        """
        Get a single order by ID.

        SECURITY: Customers can only view their own orders.

        Raises:
            SecurityViolation: If customer tries to view another's order
        """
        # Get the order first
        response = await self.api_controller.call_api(
            "woocommerce",
            "GET",
            f"/orders/{order_id}",
        )
        response.raise_for_status()
        order = response.json()

        # CRITICAL: Verify customer can access this order
        if self.wc_role == WooCommerceRole.CUSTOMER:
            if order.get("customer_id") != self.customer_id:
                raise SecurityViolation("Customers can only view their own orders")

        return order

    async def create_order(
        self,
        line_items: List[Dict[str, Any]],
        customer_id: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a new order.

        Args:
            line_items: List of products to order
            customer_id: Customer ID (optional)
            **kwargs: Additional order fields

        Returns:
            Created order data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_create_orders:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot create orders"
            )

        data = {"line_items": line_items, **kwargs}

        if customer_id:
            data["customer_id"] = customer_id

        response = await self.api_controller.call_api(
            "woocommerce",
            "POST",
            "/orders",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    async def update_order(self, order_id: int, **fields) -> Dict[str, Any]:
        """
        Update an order.

        Args:
            order_id: Order ID to update
            **fields: Fields to update

        Returns:
            Updated order data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_edit_orders:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot edit orders"
            )

        # CRITICAL: Customers cannot edit orders at all
        if self.wc_role == WooCommerceRole.CUSTOMER:
            raise SecurityViolation("Customers cannot edit orders")

        response = await self.api_controller.call_api(
            "woocommerce",
            "PUT",
            f"/orders/{order_id}",
            json=fields,
        )
        response.raise_for_status()
        return response.json()

    # --- Customers ---

    async def list_customers(
        self,
        per_page: int = 10,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        List customers.

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_view_customers:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot view customers"
            )

        params = {
            "per_page": per_page,
            "page": page,
        }

        response = await self.api_controller.call_api(
            "woocommerce",
            "GET",
            "/customers",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_customer(self, customer_id: int) -> Dict[str, Any]:
        """
        Get a single customer by ID.

        Raises:
            SecurityViolation: If user lacks permission
        """
        # Customers can view their own profile
        if self.wc_role == WooCommerceRole.CUSTOMER:
            if customer_id != self.customer_id:
                raise SecurityViolation("Customers can only view their own profile")
        elif not self.capabilities.can_view_customers:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot view customers"
            )

        response = await self.api_controller.call_api(
            "woocommerce",
            "GET",
            f"/customers/{customer_id}",
        )
        response.raise_for_status()
        return response.json()

    # --- Reports ---

    async def get_sales_report(
        self,
        period: str = "week",
        date_min: Optional[str] = None,
        date_max: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get sales report.

        Args:
            period: Report period (week, month, year)
            date_min: Start date (ISO 8601)
            date_max: End date (ISO 8601)

        Returns:
            Sales report data

        Raises:
            SecurityViolation: If user lacks permission
        """
        if not self.capabilities.can_view_reports:
            raise SecurityViolation(
                f"WooCommerce role {self.wc_role.value} cannot view reports"
            )

        params = {"period": period}

        if date_min:
            params["date_min"] = date_min
        if date_max:
            params["date_max"] = date_max

        response = await self.api_controller.call_api(
            "woocommerce",
            "GET",
            "/reports/sales",
            params=params,
        )
        response.raise_for_status()
        return response.json()


# Helper function to create WooCommerce API client
def create_woocommerce_client(
    site_url: str,
    consumer_key: str,
    consumer_secret: str,
    wc_role: WooCommerceRole,
    chatbot_role: SecurityRole,
    customer_id: Optional[int] = None,
) -> WooCommerceAPI:
    """
    Create a WooCommerce API client.

    Args:
        site_url: WooCommerce site URL
        consumer_key: WooCommerce API consumer key
        consumer_secret: WooCommerce API consumer secret
        wc_role: WooCommerce role for this user
        chatbot_role: Chatbot security role (ADMIN, USER, GUEST)
        customer_id: Customer ID (required for CUSTOMER role)

    Returns:
        Configured WooCommerceAPI client
    """
    from ..security.api_access import create_api_controller

    api_controller = create_api_controller(chatbot_role)

    return WooCommerceAPI(
        site_url=site_url,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        wc_role=wc_role,
        api_controller=api_controller,
        customer_id=customer_id,
    )
