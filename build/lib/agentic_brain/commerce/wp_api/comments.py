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

"""Comment moderation endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class CommentsAPI(WPBaseEndpoint):
    """WordPress comments endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "comments")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, comment_id: int, **params: Any) -> Any:
        return await self.client.get(
            self._path(comment_id), params=self._params(params)
        )

    async def create(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self.resource, json_body=data)

    async def update(self, comment_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._path(comment_id), json_body=data)

    async def delete(self, comment_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._path(comment_id), params={"force": str(force).lower()}
        )

    async def update_status(self, comment_id: int, status: str) -> Any:
        return await self.update(comment_id, {"status": status})

    async def approve(self, comment_id: int) -> Any:
        return await self.update_status(comment_id, "approve")

    async def hold(self, comment_id: int) -> Any:
        return await self.update_status(comment_id, "hold")

    async def spam(self, comment_id: int) -> Any:
        return await self.update_status(comment_id, "spam")

    async def trash(self, comment_id: int) -> Any:
        return await self.update_status(comment_id, "trash")

    async def untrash(self, comment_id: int) -> Any:
        return await self.update_status(comment_id, "approve")
