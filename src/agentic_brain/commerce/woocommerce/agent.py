# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WooCommerce API Agent implementation."""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

from ..models import (
    WooCustomer,
    WooOrder,
    WooProduct,
)
from . import requests

logger = logging.getLogger(__name__)


class WooCommerceAgent:
    """
    Agent for interacting with WooCommerce REST API.

    Supports products, orders, and customers CRUD operations.
    Async-first design with synchronous wrappers.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize the WooCommerce Agent.

        Args:
            url: Base URL of the WooCommerce store (e.g., https://example.com)
            consumer_key: WooCommerce Consumer Key
            consumer_secret: WooCommerce Consumer Secret
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        self.url = (url or os.environ.get("WOOCOMMERCE_URL", "")).rstrip("/")
        self.consumer_key = consumer_key or os.environ.get("WOOCOMMERCE_CONSUMER_KEY")
        self.consumer_secret = consumer_secret or os.environ.get(
            "WOOCOMMERCE_CONSUMER_SECRET"
        )
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        if not self.url:
            logger.warning("WooCommerce URL not provided.")
        if not self.consumer_key or not self.consumer_secret:
            logger.warning("WooCommerce credentials not provided.")

        self._session = requests.Session()

        # Configure retry logic
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=[
                "HEAD",
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
                "POST",
            ],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        # Basic Auth is standard for WooCommerce REST API over HTTPS
        self._session.auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        self._session.headers.update(
            {"Content-Type": "application/json", "User-Agent": "AgenticBrain/1.0"}
        )

    def _handle_error(self, response: requests.Response) -> None:
        """Handle API errors."""
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            error_msg = f"WooCommerce API Error: {e}"
            try:
                data = response.json()
                if "message" in data:
                    error_msg += f" - {data['message']}"
            except ValueError:
                pass
            logger.error(error_msg)
            raise requests.HTTPError(error_msg, response=response) from e

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Internal synchronous request method."""
        url = f"{self.url}/wp-json/wc/v3/{endpoint.lstrip('/')}"

        try:
            response = self._session.request(
                method, url, verify=self.verify_ssl, timeout=self.timeout, **kwargs
            )
            self._handle_error(response)
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            raise

    async def _arequest(self, method: str, endpoint: str, **kwargs) -> Any:
        """Internal asynchronous request wrapper."""
        return await asyncio.to_thread(self._request, method, endpoint, **kwargs)

    # --- Products ---

    async def get_products(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of products.

        Args:
            params: Query parameters (page, per_page, search, etc.)
        """
        return await self._arequest("GET", "products", params=params)

    async def get_product(self, product_id: int) -> Dict[str, Any]:
        """Get a single product by ID."""
        return await self._arequest("GET", f"products/{product_id}")

    async def create_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product."""
        return await self._arequest("POST", "products", json=data)

    async def update_product(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a product."""
        return await self._arequest("PUT", f"products/{product_id}", json=data)

    async def delete_product(
        self, product_id: int, force: bool = False
    ) -> Dict[str, Any]:
        """Delete a product."""
        return await self._arequest(
            "DELETE", f"products/{product_id}", params={"force": str(force).lower()}
        )

    # --- Variations ---

    async def get_variations(
        self, product_id: int, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """List variations for a variable product."""
        return await self._arequest(
            "GET", f"products/{product_id}/variations", params=params
        )

    async def get_variation(self, product_id: int, variation_id: int) -> Dict[str, Any]:
        """Get a single variation."""
        return await self._arequest(
            "GET", f"products/{product_id}/variations/{variation_id}"
        )

    async def create_variation(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a variation."""
        return await self._arequest(
            "POST", f"products/{product_id}/variations", json=data
        )

    async def update_variation(
        self, product_id: int, variation_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a variation."""
        return await self._arequest(
            "PUT", f"products/{product_id}/variations/{variation_id}", json=data
        )

    async def delete_variation(
        self, product_id: int, variation_id: int, force: bool = False
    ) -> Dict[str, Any]:
        """Delete a variation."""
        return await self._arequest(
            "DELETE",
            f"products/{product_id}/variations/{variation_id}",
            params={"force": str(force).lower()},
        )

    # --- Orders ---

    async def get_orders(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get a list of orders."""
        return await self._arequest("GET", "orders", params=params)

    async def get_order(self, order_id: int) -> Dict[str, Any]:
        """Get a single order by ID."""
        return await self._arequest("GET", f"orders/{order_id}")

    async def update_order(self, order_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an order."""
        return await self._arequest("PUT", f"orders/{order_id}", json=data)

    async def create_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new order."""
        return await self._arequest("POST", "orders", json=data)

    # --- Customers ---

    async def get_customers(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get a list of customers."""
        return await self._arequest("GET", "customers", params=params)

    async def get_customer(self, customer_id: int) -> Dict[str, Any]:
        """Get a single customer by ID."""
        return await self._arequest("GET", f"customers/{customer_id}")

    async def create_customer(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new customer."""
        return await self._arequest("POST", "customers", json=data)

    # --- RAG Integration ---

    async def sync_products(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[WooProduct]:
        """Fetch and validate remote products into strongly typed models."""
        products = await self.get_products(params=params)
        return [WooProduct.model_validate(product) for product in products]

    async def sync_orders(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[WooOrder]:
        """Fetch and validate remote orders into strongly typed models."""
        orders = await self.get_orders(params=params)
        return [WooOrder.model_validate(order) for order in orders]

    async def sync_customers(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[WooCustomer]:
        """Fetch and validate remote customers into strongly typed models."""
        customers = await self.get_customers(params=params)
        return [WooCustomer.model_validate(customer) for customer in customers]

    async def update_inventory(
        self,
        product_id: int,
        stock: int,
        *,
        in_stock: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update WooCommerce inventory fields for a product."""
        payload = {
            "stock": stock,
            "manage_stock": True,
            "in_stock": stock > 0 if in_stock is None else in_stock,
        }
        return await self.update_product(product_id, payload)

    async def search_products(self, query: str) -> List[Dict[str, Any]]:
        """
        Search products for RAG pipeline.

        Args:
            query: Search term

        Returns:
            List of matching products with relevant fields
        """
        params = {"search": query, "per_page": 10}
        products = await self.get_products(params)
        return products

    # --- Sync Wrappers ---

    def get_products_sync(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self._request("GET", "products", params=params)

    def get_product_sync(self, product_id: int) -> Dict[str, Any]:
        return self._request("GET", f"products/{product_id}")

    def create_product_sync(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "products", json=data)

    def update_product_sync(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._request("PUT", f"products/{product_id}", json=data)

    def delete_product_sync(
        self, product_id: int, force: bool = False
    ) -> Dict[str, Any]:
        return self._request(
            "DELETE", f"products/{product_id}", params={"force": str(force).lower()}
        )

    def get_variations_sync(
        self, product_id: int, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self._request("GET", f"products/{product_id}/variations", params=params)

    def get_variation_sync(self, product_id: int, variation_id: int) -> Dict[str, Any]:
        return self._request("GET", f"products/{product_id}/variations/{variation_id}")

    def create_variation_sync(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._request("POST", f"products/{product_id}/variations", json=data)

    def update_variation_sync(
        self, product_id: int, variation_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._request(
            "PUT", f"products/{product_id}/variations/{variation_id}", json=data
        )

    def delete_variation_sync(
        self, product_id: int, variation_id: int, force: bool = False
    ) -> Dict[str, Any]:
        return self._request(
            "DELETE",
            f"products/{product_id}/variations/{variation_id}",
            params={"force": str(force).lower()},
        )

    def create_order_sync(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "orders", json=data)

    def update_order_sync(self, order_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", f"orders/{order_id}", json=data)

    def sync_products_sync(
        self, params: Optional[Dict[str, Any]] = None
    ) -> List[WooProduct]:
        return [
            WooProduct.model_validate(product)
            for product in self.get_products_sync(params=params)
        ]

    def update_inventory_sync(
        self,
        product_id: int,
        stock: int,
        *,
        in_stock: Optional[bool] = None,
    ) -> Dict[str, Any]:
        payload = {
            "stock": stock,
            "manage_stock": True,
            "in_stock": stock > 0 if in_stock is None else in_stock,
        }
        return self._request("PUT", f"products/{product_id}", json=payload)
