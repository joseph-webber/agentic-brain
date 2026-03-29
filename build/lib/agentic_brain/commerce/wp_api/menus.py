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

"""Navigation menu endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class MenusAPI:
    """WordPress navigation menus endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        self.client = client
        self._menus = WPBaseEndpoint(client, "menus")
        self._menu_items = WPBaseEndpoint(client, "menu-items")
        self._menu_locations = WPBaseEndpoint(client, "menu-locations")

    async def list_menus(self, **params: Any) -> Any:
        return await self.client.get(
            self._menus.resource, params=self._menus._params(params)
        )

    async def get_menu(self, menu_id: int, **params: Any) -> Any:
        return await self.client.get(
            self._menus._path(menu_id), params=self._menus._params(params)
        )

    async def create_menu(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self._menus.resource, json_body=data)

    async def update_menu(self, menu_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._menus._path(menu_id), json_body=data)

    async def delete_menu(self, menu_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._menus._path(menu_id), params={"force": str(force).lower()}
        )

    async def list_menu_items(
        self, *, menu_id: int | None = None, **params: Any
    ) -> Any:
        menu_params = dict(self._menu_items._params(params) or {})
        if menu_id is not None:
            menu_params["menus"] = menu_id
        return await self.client.get(
            self._menu_items.resource, params=menu_params or None
        )

    async def get_menu_item(self, item_id: int, **params: Any) -> Any:
        return await self.client.get(
            self._menu_items._path(item_id), params=self._menu_items._params(params)
        )

    async def create_menu_item(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self._menu_items.resource, json_body=data)

    async def update_menu_item(self, item_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._menu_items._path(item_id), json_body=data)

    async def delete_menu_item(self, item_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._menu_items._path(item_id), params={"force": str(force).lower()}
        )

    async def list_menu_locations(self, **params: Any) -> Any:
        return await self.client.get(
            self._menu_locations.resource, params=self._menu_locations._params(params)
        )
