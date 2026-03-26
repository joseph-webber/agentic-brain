# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""WooCommerce shipping zones, methods, and locations."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import WooAPIClient, WooResourceAPI


class ShippingAPI(WooResourceAPI):
    """Manage WooCommerce shipping configuration."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    # -- Zones --------------------------------------------------------------------

    async def list_zones(self) -> list[Any]:
        return await self.client.request("GET", "shipping/zones")

    async def retrieve_zone(self, zone_id: int) -> Mapping[str, Any]:
        return await self.client.request("GET", f"shipping/zones/{zone_id}")

    async def create_zone(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "shipping/zones", json_body=payload)

    async def update_zone(
        self, zone_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"shipping/zones/{zone_id}", json_body=payload
        )

    async def delete_zone(self, zone_id: int) -> Mapping[str, Any]:
        return await self.client.request("DELETE", f"shipping/zones/{zone_id}")

    # -- Zone locations ------------------------------------------------------------

    async def list_zone_locations(self, zone_id: int) -> list[Any]:
        return await self.client.request("GET", f"shipping/zones/{zone_id}/locations")

    async def update_zone_locations(
        self, zone_id: int, locations: Sequence[Mapping[str, Any]]
    ) -> list[Any]:
        return await self.client.request(
            "PUT",
            f"shipping/zones/{zone_id}/locations",
            json_body=list(locations),
        )

    # -- Zone methods --------------------------------------------------------------

    async def list_zone_methods(self, zone_id: int) -> list[Any]:
        return await self.client.request("GET", f"shipping/zones/{zone_id}/methods")

    async def create_zone_method(
        self, zone_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", f"shipping/zones/{zone_id}/methods", json_body=payload
        )

    async def retrieve_zone_method(
        self, zone_id: int, instance_id: int
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "GET", f"shipping/zones/{zone_id}/methods/{instance_id}"
        )

    async def update_zone_method(
        self,
        zone_id: int,
        instance_id: int,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT",
            f"shipping/zones/{zone_id}/methods/{instance_id}",
            json_body=payload,
        )

    async def delete_zone_method(
        self, zone_id: int, instance_id: int
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"shipping/zones/{zone_id}/methods/{instance_id}"
        )

    # -- Global methods ------------------------------------------------------------

    async def list_global_methods(self) -> list[Any]:
        return await self.client.request("GET", "shipping_methods")
