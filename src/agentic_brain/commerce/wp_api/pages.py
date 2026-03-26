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

"""Pages CRUD endpoints for the WordPress REST API."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class PagesAPI(WPBaseEndpoint):
    """WordPress pages endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "pages")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, page_id: int, **params: Any) -> Any:
        return await self.client.get(self._path(page_id), params=self._params(params))

    async def create(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self.resource, json_body=data)

    async def update(self, page_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._path(page_id), json_body=data)

    async def delete(self, page_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._path(page_id), params={"force": str(force).lower()}
        )

    async def list_revisions(self, page_id: int, **params: Any) -> Any:
        return await self.client.get(
            self._path(page_id, "revisions"), params=self._params(params)
        )

    async def get_revision(self, page_id: int, revision_id: int) -> Any:
        return await self.client.get(self._path(page_id, "revisions", revision_id))

    async def delete_revision(
        self, page_id: int, revision_id: int, *, force: bool = True
    ) -> Any:
        return await self.client.delete(
            self._path(page_id, "revisions", revision_id),
            params={"force": str(force).lower()},
        )

    async def list_autosaves(self, page_id: int, **params: Any) -> Any:
        return await self.client.get(
            self._path(page_id, "autosaves"), params=self._params(params)
        )

    async def get_autosave(self, page_id: int, autosave_id: int) -> Any:
        return await self.client.get(self._path(page_id, "autosaves", autosave_id))

    async def update_meta(self, page_id: int, meta: dict[str, Any]) -> Any:
        return await self.update(page_id, {"meta": meta})

    async def set_featured_media(self, page_id: int, media_id: int) -> Any:
        return await self.update(page_id, {"featured_media": media_id})
