# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Categories, tags, and taxonomy endpoints."""

from __future__ import annotations

from typing import Any, Mapping

from .client import WPAPIClient, WPBaseEndpoint


def _params(params: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    return {key: value for key, value in params.items() if value is not None}


class CategoriesAPI(WPBaseEndpoint):
    """WordPress categories endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "categories")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, category_id: int, **params: Any) -> Any:
        return await self.client.get(
            self._path(category_id), params=self._params(params)
        )

    async def create(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self.resource, json_body=data)

    async def update(self, category_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._path(category_id), json_body=data)

    async def delete(self, category_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._path(category_id), params={"force": str(force).lower()}
        )


class TagsAPI(WPBaseEndpoint):
    """WordPress tags endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "tags")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, tag_id: int, **params: Any) -> Any:
        return await self.client.get(self._path(tag_id), params=self._params(params))

    async def create(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self.resource, json_body=data)

    async def update(self, tag_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._path(tag_id), json_body=data)

    async def delete(self, tag_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._path(tag_id), params={"force": str(force).lower()}
        )


class TaxonomiesAPI:
    """Custom taxonomy endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        self.client = client

    async def list_taxonomies(self, **params: Any) -> Any:
        return await self.client.get("taxonomies", params=_params(params))

    async def get_taxonomy(self, taxonomy: str) -> Any:
        return await self.client.get(f"taxonomies/{taxonomy}")

    async def list_terms(self, taxonomy: str, **params: Any) -> Any:
        return await self.client.get(taxonomy, params=_params(params))

    async def get_term(self, taxonomy: str, term_id: int, **params: Any) -> Any:
        return await self.client.get(f"{taxonomy}/{term_id}", params=_params(params))

    async def create_term(self, taxonomy: str, data: dict[str, Any]) -> Any:
        return await self.client.post(taxonomy, json_body=data)

    async def update_term(
        self, taxonomy: str, term_id: int, data: dict[str, Any]
    ) -> Any:
        return await self.client.post(f"{taxonomy}/{term_id}", json_body=data)

    async def delete_term(
        self, taxonomy: str, term_id: int, *, force: bool = False
    ) -> Any:
        return await self.client.delete(
            f"{taxonomy}/{term_id}", params={"force": str(force).lower()}
        )
