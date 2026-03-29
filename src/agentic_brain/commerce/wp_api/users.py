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

"""Users CRUD endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class UsersAPI(WPBaseEndpoint):
    """WordPress users endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "users")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, user_id: int, **params: Any) -> Any:
        return await self.client.get(self._path(user_id), params=self._params(params))

    async def me(self, **params: Any) -> Any:
        return await self.client.get(self._path("me"), params=self._params(params))

    async def create(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self.resource, json_body=data)

    async def update(self, user_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._path(user_id), json_body=data)

    async def delete(
        self, user_id: int, *, force: bool = False, reassign: int | None = None
    ) -> Any:
        params = {"force": str(force).lower()}
        if reassign is not None:
            params["reassign"] = reassign
        return await self.client.delete(self._path(user_id), params=params)

    async def update_roles(self, user_id: int, roles: list[str]) -> Any:
        return await self.update(user_id, {"roles": roles})

    async def update_capabilities(
        self, user_id: int, capabilities: dict[str, bool]
    ) -> Any:
        return await self.update(user_id, {"capabilities": capabilities})
