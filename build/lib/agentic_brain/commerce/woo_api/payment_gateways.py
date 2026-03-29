# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WooCommerce payment gateway configuration endpoints."""

from __future__ import annotations

from typing import Any, Mapping

from .client import WooAPIClient, WooResourceAPI


class PaymentGatewaysAPI(WooResourceAPI):
    """Inspect and update WooCommerce payment gateways."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    async def list(self) -> list[Any]:
        return await self.client.request("GET", "payment_gateways")

    async def retrieve(self, gateway_id: str) -> Mapping[str, Any]:
        return await self.client.request("GET", f"payment_gateways/{gateway_id}")

    async def update(
        self, gateway_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"payment_gateways/{gateway_id}", json_body=payload
        )
