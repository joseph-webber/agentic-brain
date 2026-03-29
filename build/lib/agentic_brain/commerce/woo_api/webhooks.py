# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WooCommerce webhook endpoints."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import WooAPIClient, WooResourceAPI


class WebhooksAPI(WooResourceAPI):
    """Create, update, and monitor WooCommerce webhooks."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    async def list(
        self,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
        **filters: Any,
    ) -> list[Any]:
        return await self.client.paginate(
            "webhooks",
            params=self._clean(filters),
            per_page=per_page,
            max_pages=max_pages,
        )

    async def retrieve(self, webhook_id: int) -> Mapping[str, Any]:
        return await self.client.request("GET", f"webhooks/{webhook_id}")

    async def create(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "webhooks", json_body=payload)

    async def update(
        self, webhook_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"webhooks/{webhook_id}", json_body=payload
        )

    async def delete(self, webhook_id: int, *, force: bool = True) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"webhooks/{webhook_id}", params={"force": force}
        )

    async def batch(
        self,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch("webhooks/batch", payload)

    async def list_deliveries(self, webhook_id: int) -> list[Any]:
        return await self.client.request("GET", f"webhooks/{webhook_id}/deliveries")

    async def retrieve_delivery(
        self, webhook_id: int, delivery_id: int
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "GET", f"webhooks/{webhook_id}/deliveries/{delivery_id}"
        )

    async def redeliver(self, webhook_id: int, delivery_id: int) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", f"webhooks/{webhook_id}/deliveries/{delivery_id}/resend"
        )
