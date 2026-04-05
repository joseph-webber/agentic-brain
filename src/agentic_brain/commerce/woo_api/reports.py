# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WooCommerce analytics and reporting endpoints."""

from __future__ import annotations

from typing import Any

from .client import WooAPIClient, WooResourceAPI


class ReportsAPI(WooResourceAPI):
    """Retrieve sales, customer, tax, and download reports."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    async def sales(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/sales", params=self._clean(params)
        )

    async def top_sellers(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/top_sellers", params=self._clean(params)
        )

    async def customers(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/customers", params=self._clean(params)
        )

    async def orders_totals(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/orders/totals", params=self._clean(params)
        )

    async def coupons_totals(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/coupons/totals", params=self._clean(params)
        )

    async def taxes(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/taxes", params=self._clean(params)
        )

    async def taxes_totals(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/taxes/totals", params=self._clean(params)
        )

    async def stock(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/stock", params=self._clean(params)
        )

    async def downloads(self, **params: Any) -> list[Any]:
        return await self.client.request(
            "GET", "reports/downloads", params=self._clean(params)
        )
