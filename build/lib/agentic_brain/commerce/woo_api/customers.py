# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WooCommerce customer endpoints."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import WooAPIClient, WooResourceAPI


class CustomersAPI(WooResourceAPI):
    """Manage WooCommerce customers and download permissions."""

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
            "customers",
            params=self._clean(filters),
            per_page=per_page,
            max_pages=max_pages,
        )

    async def retrieve(self, customer_id: int, **params: Any) -> Mapping[str, Any]:
        return await self.client.request(
            "GET", f"customers/{customer_id}", params=self._clean(params)
        )

    async def create(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "customers", json_body=payload)

    async def update(
        self, customer_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"customers/{customer_id}", json_body=payload
        )

    async def delete(
        self, customer_id: int, *, force: bool = True
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"customers/{customer_id}", params={"force": force}
        )

    async def batch(
        self,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch("customers/batch", payload)

    async def list_downloads(
        self,
        customer_id: int,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
        **filters: Any,
    ) -> list[Any]:
        return await self.client.paginate(
            f"customers/{customer_id}/downloads",
            params=self._clean(filters),
            per_page=per_page,
            max_pages=max_pages,
        )
