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

"""Plugin management endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class PluginsAPI(WPBaseEndpoint):
    """WordPress plugin endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "plugins")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, plugin: str, **params: Any) -> Any:
        return await self.client.get(self._path(plugin), params=self._params(params))

    async def activate(self, plugin: str) -> Any:
        return await self.client.post(
            self._path(plugin), json_body={"status": "active"}
        )

    async def deactivate(self, plugin: str) -> Any:
        return await self.client.post(
            self._path(plugin), json_body={"status": "inactive"}
        )

    async def update(self, plugin: str, data: dict[str, Any]) -> Any:
        return await self.client.post(self._path(plugin), json_body=data)

    async def delete(self, plugin: str, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._path(plugin), params={"force": str(force).lower()}
        )
