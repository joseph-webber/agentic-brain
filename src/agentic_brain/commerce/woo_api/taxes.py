# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""WooCommerce tax classes and rates."""

from __future__ import annotations

from typing import Any, Mapping

from .client import WooAPIClient, WooResourceAPI


class TaxesAPI(WooResourceAPI):
    """Manage WooCommerce tax classes and rates."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    # -- Tax classes ---------------------------------------------------------------

    async def list_classes(self) -> list[Any]:
        return await self.client.request("GET", "taxes/classes")

    async def create_class(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "taxes/classes", json_body=payload)

    async def delete_class(self, class_slug: str) -> Mapping[str, Any]:
        return await self.client.request("DELETE", f"taxes/classes/{class_slug}")

    # -- Tax rates -----------------------------------------------------------------

    async def list_rates(self, **filters: Any) -> list[Any]:
        return await self.client.request("GET", "taxes", params=self._clean(filters))

    async def retrieve_rate(self, rate_id: int) -> Mapping[str, Any]:
        return await self.client.request("GET", f"taxes/{rate_id}")

    async def create_rate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "taxes", json_body=payload)

    async def update_rate(
        self, rate_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request("PUT", f"taxes/{rate_id}", json_body=payload)

    async def delete_rate(self, rate_id: int) -> Mapping[str, Any]:
        return await self.client.request("DELETE", f"taxes/{rate_id}")
