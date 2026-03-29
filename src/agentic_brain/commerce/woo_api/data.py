# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WooCommerce data endpoints (countries, currencies, etc.)."""

from __future__ import annotations

from typing import Any, Mapping

from .client import WooAPIClient, WooResourceAPI


class DataAPI(WooResourceAPI):
    """Expose WooCommerce static data helpers."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    async def countries(self) -> list[Any]:
        return await self.client.request("GET", "data/countries")

    async def country(self, code: str) -> Mapping[str, Any]:
        return await self.client.request("GET", f"data/countries/{code}")

    async def country_states(self, code: str) -> list[Any]:
        return await self.client.request("GET", f"data/countries/{code}/states")

    async def currencies(self) -> list[Any]:
        return await self.client.request("GET", "data/currencies")

    async def continents(self) -> list[Any]:
        return await self.client.request("GET", "data/continents")
