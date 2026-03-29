# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""High-level entrypoint exposing every WooCommerce REST API surface.

The :class:`WooCommerceAPI` facade wires every resource module together using a
shared :class:`~agentic_brain.commerce.woo_api.client.WooAPIClient` instance.

Example
-------
>>> from agentic_brain.commerce.woo_api import WooCommerceAPI
>>> woo = WooCommerceAPI("https://shop.example", "ck_123", "cs_456")
>>> products = woo.products.sync.list(status="publish")
>>> customers = woo.customers.sync.list(role="subscriber")
"""

from __future__ import annotations

from .client import WooAPIClient, WooAPIError
from .coupons import CouponsAPI
from .customers import CustomersAPI
from .data import DataAPI
from .orders import OrdersAPI
from .payment_gateways import PaymentGatewaysAPI
from .products import ProductsAPI
from .reports import ReportsAPI
from .settings import SettingsAPI
from .shipping import ShippingAPI
from .system import SystemAPI
from .taxes import TaxesAPI
from .webhooks import WebhooksAPI

__all__ = [
    "WooAPIClient",
    "WooAPIError",
    "WooCommerceAPI",
    "ProductsAPI",
    "OrdersAPI",
    "CustomersAPI",
    "CouponsAPI",
    "ReportsAPI",
    "SettingsAPI",
    "ShippingAPI",
    "TaxesAPI",
    "PaymentGatewaysAPI",
    "WebhooksAPI",
    "SystemAPI",
    "DataAPI",
]


class WooCommerceAPI:
    """Facade exposing typed access to every WooCommerce resource collection."""

    def __init__(
        self,
        base_url: str,
        consumer_key: str,
        consumer_secret: str,
        **client_kwargs: object,
    ) -> None:
        client = client_kwargs.pop("client", None)
        if client is not None and not isinstance(client, WooAPIClient):
            raise TypeError("client must be a WooAPIClient instance")
        self.client = client or WooAPIClient(
            base_url,
            consumer_key,
            consumer_secret,
            **client_kwargs,
        )
        self.products = ProductsAPI(self.client)
        self.orders = OrdersAPI(self.client)
        self.customers = CustomersAPI(self.client)
        self.coupons = CouponsAPI(self.client)
        self.reports = ReportsAPI(self.client)
        self.settings = SettingsAPI(self.client)
        self.shipping = ShippingAPI(self.client)
        self.taxes = TaxesAPI(self.client)
        self.payment_gateways = PaymentGatewaysAPI(self.client)
        self.webhooks = WebhooksAPI(self.client)
        self.system = SystemAPI(self.client)
        self.data = DataAPI(self.client)

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self.client.close()

    def close_sync(self) -> None:
        """Synchronously close the HTTP client."""

        self.client.close_sync()
