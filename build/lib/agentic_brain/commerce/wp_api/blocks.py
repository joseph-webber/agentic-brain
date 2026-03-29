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

"""Block types, reusable blocks, and patterns endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class BlocksAPI:
    """WordPress block-related endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        self.client = client
        self._blocks = WPBaseEndpoint(client, "blocks")
        self._block_types = WPBaseEndpoint(client, "block-types")
        self._patterns = WPBaseEndpoint(client, "block-patterns")
        self._pattern_categories = WPBaseEndpoint(client, "block-patterns/categories")
        self._block_directory = WPBaseEndpoint(client, "block-directory/search")

    async def list_block_types(self, **params: Any) -> Any:
        return await self.client.get(
            self._block_types.resource, params=self._block_types._params(params)
        )

    async def get_block_type(self, block_name: str) -> Any:
        return await self.client.get(self._block_types._path(block_name))

    async def list_reusable_blocks(self, **params: Any) -> Any:
        return await self.client.get(
            self._blocks.resource, params=self._blocks._params(params)
        )

    async def get_reusable_block(self, block_id: int, **params: Any) -> Any:
        return await self.client.get(
            self._blocks._path(block_id), params=self._blocks._params(params)
        )

    async def create_reusable_block(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self._blocks.resource, json_body=data)

    async def update_reusable_block(self, block_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._blocks._path(block_id), json_body=data)

    async def delete_reusable_block(self, block_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._blocks._path(block_id), params={"force": str(force).lower()}
        )

    async def list_block_patterns(self, **params: Any) -> Any:
        return await self.client.get(
            self._patterns._path("patterns"), params=self._patterns._params(params)
        )

    async def get_block_pattern(self, pattern_name: str) -> Any:
        return await self.client.get(self._patterns._path("patterns", pattern_name))

    async def list_block_pattern_categories(self, **params: Any) -> Any:
        return await self.client.get(
            self._pattern_categories.resource,
            params=self._pattern_categories._params(params),
        )

    async def search_block_directory(self, **params: Any) -> Any:
        return await self.client.get(
            self._block_directory.resource, params=self._block_directory._params(params)
        )
