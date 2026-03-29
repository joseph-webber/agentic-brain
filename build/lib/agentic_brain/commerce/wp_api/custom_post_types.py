# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""Custom post types and ACF endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class CustomPostTypesAPI:
    """WordPress custom post type endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        self.client = client
        self._types = WPBaseEndpoint(client, "types")

    async def list_types(self, **params: Any) -> Any:
        return await self.client.get(
            self._types.resource, params=self._types._params(params)
        )

    async def get_type(self, post_type: str, **params: Any) -> Any:
        return await self.client.get(
            self._types._path(post_type), params=self._types._params(params)
        )

    async def list_items(self, post_type: str, **params: Any) -> Any:
        return await self.client.get(post_type, params=self._types._params(params))

    async def get_item(self, post_type: str, item_id: int, **params: Any) -> Any:
        return await self.client.get(
            f"{post_type}/{item_id}", params=self._types._params(params)
        )

    async def create_item(self, post_type: str, data: dict[str, Any]) -> Any:
        return await self.client.post(post_type, json_body=data)

    async def update_item(
        self, post_type: str, item_id: int, data: dict[str, Any]
    ) -> Any:
        return await self.client.post(f"{post_type}/{item_id}", json_body=data)

    async def delete_item(
        self, post_type: str, item_id: int, *, force: bool = False
    ) -> Any:
        return await self.client.delete(
            f"{post_type}/{item_id}", params={"force": str(force).lower()}
        )

    async def get_acf_fields(self, post_type: str, item_id: int) -> Any:
        return await self.client.get(self.client.acf_url(f"{post_type}/{item_id}"))

    async def update_acf_fields(
        self, post_type: str, item_id: int, data: dict[str, Any]
    ) -> Any:
        return await self.client.post(
            self.client.acf_url(f"{post_type}/{item_id}"),
            json_body=data,
        )
