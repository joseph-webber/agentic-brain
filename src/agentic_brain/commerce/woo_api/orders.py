# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""WooCommerce orders, notes, and refunds endpoints."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import WooAPIClient, WooResourceAPI


class OrdersAPI(WooResourceAPI):
    """Access WooCommerce order data with helpers for notes and refunds."""

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
            "orders",
            params=self._clean(filters),
            per_page=per_page,
            max_pages=max_pages,
        )

    async def retrieve(self, order_id: int, **params: Any) -> Mapping[str, Any]:
        return await self.client.request(
            "GET", f"orders/{order_id}", params=self._clean(params)
        )

    async def create(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "orders", json_body=payload)

    async def update(
        self, order_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request("PUT", f"orders/{order_id}", json_body=payload)

    async def delete(self, order_id: int, *, force: bool = True) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"orders/{order_id}", params={"force": force}
        )

    async def batch(
        self,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch("orders/batch", payload)

    # -- Order notes ---------------------------------------------------------------

    async def list_notes(self, order_id: int) -> list[Any]:
        return await self.client.request("GET", f"orders/{order_id}/notes")

    async def create_note(
        self,
        order_id: int,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", f"orders/{order_id}/notes", json_body=payload
        )

    async def delete_note(self, order_id: int, note_id: int) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"orders/{order_id}/notes/{note_id}", params={"force": True}
        )

    # -- Refunds -------------------------------------------------------------------

    async def list_refunds(self, order_id: int) -> list[Any]:
        return await self.client.request("GET", f"orders/{order_id}/refunds")

    async def create_refund(
        self,
        order_id: int,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", f"orders/{order_id}/refunds", json_body=payload
        )

    async def retrieve_refund(self, order_id: int, refund_id: int) -> Mapping[str, Any]:
        return await self.client.request(
            "GET", f"orders/{order_id}/refunds/{refund_id}"
        )

    async def delete_refund(
        self, order_id: int, refund_id: int, *, force: bool = True
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE",
            f"orders/{order_id}/refunds/{refund_id}",
            params={"force": force},
        )
