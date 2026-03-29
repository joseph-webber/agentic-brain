# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""WooCommerce product endpoints.

Example
-------
>>> api = WooCommerceAPI("https://shop.example", "ck", "cs").products
>>> await api.create({"name": "Notebook", "regular_price": "19.99"})
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import WooAPIClient, WooResourceAPI


class ProductsAPI(WooResourceAPI):
    """Access product, variation, taxonomy, and review endpoints."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    # -- Products -----------------------------------------------------------------

    async def list(
        self,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
        **filters: Any,
    ) -> list[Any]:
        """List products with optional filters."""

        return await self.client.paginate(
            "products",
            params=self._clean(filters),
            per_page=per_page,
            max_pages=max_pages,
        )

    async def retrieve(self, product_id: int, **params: Any) -> Mapping[str, Any]:
        return await self.client.request(
            "GET", f"products/{product_id}", params=self._clean(params)
        )

    async def create(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "products", json_body=payload)

    async def update(
        self, product_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"products/{product_id}", json_body=payload
        )

    async def delete(self, product_id: int, *, force: bool = True) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE",
            f"products/{product_id}",
            params={"force": force},
        )

    async def batch(
        self,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch("products/batch", payload)

    # -- Variations ----------------------------------------------------------------

    async def list_variations(
        self,
        product_id: int,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
        **filters: Any,
    ) -> list[Any]:
        endpoint = f"products/{product_id}/variations"
        return await self.client.paginate(
            endpoint,
            params=self._clean(filters),
            per_page=per_page,
            max_pages=max_pages,
        )

    async def create_variation(
        self,
        product_id: int,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", f"products/{product_id}/variations", json_body=payload
        )

    async def update_variation(
        self,
        product_id: int,
        variation_id: int,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT",
            f"products/{product_id}/variations/{variation_id}",
            json_body=payload,
        )

    async def delete_variation(
        self,
        product_id: int,
        variation_id: int,
        *,
        force: bool = True,
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE",
            f"products/{product_id}/variations/{variation_id}",
            params={"force": force},
        )

    async def batch_variations(
        self,
        product_id: int,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch(
            f"products/{product_id}/variations/batch",
            payload,
        )

    # -- Attributes ----------------------------------------------------------------

    async def list_attributes(self, **filters: Any) -> list[Any]:
        return await self.client.paginate(
            "products/attributes", params=self._clean(filters)
        )

    async def create_attribute(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", "products/attributes", json_body=payload
        )

    async def update_attribute(
        self, attribute_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"products/attributes/{attribute_id}", json_body=payload
        )

    async def delete_attribute(self, attribute_id: int) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"products/attributes/{attribute_id}", params={"force": True}
        )

    async def list_attribute_terms(
        self,
        attribute_id: int,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
        **filters: Any,
    ) -> list[Any]:
        return await self.client.paginate(
            f"products/attributes/{attribute_id}/terms",
            params=self._clean(filters),
            per_page=per_page,
            max_pages=max_pages,
        )

    async def create_attribute_term(
        self, attribute_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", f"products/attributes/{attribute_id}/terms", json_body=payload
        )

    async def update_attribute_term(
        self,
        attribute_id: int,
        term_id: int,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT",
            f"products/attributes/{attribute_id}/terms/{term_id}",
            json_body=payload,
        )

    async def delete_attribute_term(
        self, attribute_id: int, term_id: int
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE",
            f"products/attributes/{attribute_id}/terms/{term_id}",
            params={"force": True},
        )

    # -- Categories ----------------------------------------------------------------

    async def list_categories(self, **filters: Any) -> list[Any]:
        return await self.client.paginate(
            "products/categories", params=self._clean(filters)
        )

    async def create_category(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request(
            "POST", "products/categories", json_body=payload
        )

    async def update_category(
        self, category_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"products/categories/{category_id}", json_body=payload
        )

    async def delete_category(
        self, category_id: int, *, force: bool = True
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE",
            f"products/categories/{category_id}",
            params={"force": force},
        )

    async def batch_categories(
        self,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch("products/categories/batch", payload)

    # -- Tags ----------------------------------------------------------------------

    async def list_tags(self, **filters: Any) -> list[Any]:
        return await self.client.paginate("products/tags", params=self._clean(filters))

    async def create_tag(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "products/tags", json_body=payload)

    async def update_tag(
        self, tag_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"products/tags/{tag_id}", json_body=payload
        )

    async def delete_tag(self, tag_id: int, *, force: bool = True) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"products/tags/{tag_id}", params={"force": force}
        )

    async def batch_tags(
        self,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch("products/tags/batch", payload)

    # -- Reviews -------------------------------------------------------------------

    async def list_reviews(self, **filters: Any) -> list[Any]:
        return await self.client.paginate(
            "products/reviews", params=self._clean(filters)
        )

    async def create_review(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.client.request("POST", "products/reviews", json_body=payload)

    async def update_review(
        self, review_id: int, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT", f"products/reviews/{review_id}", json_body=payload
        )

    async def delete_review(
        self, review_id: int, *, force: bool = True
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "DELETE", f"products/reviews/{review_id}", params={"force": force}
        )

    async def batch_reviews(
        self,
        *,
        create: Sequence[Mapping[str, Any]] | None = None,
        update: Sequence[Mapping[str, Any]] | None = None,
        delete: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        payload = self._build_batch_payload(create=create, update=update, delete=delete)
        return await self.client.batch("products/reviews/batch", payload)
