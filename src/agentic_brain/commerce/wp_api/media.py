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

"""Media upload and management endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class MediaAPI(WPBaseEndpoint):
    """WordPress media endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "media")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, media_id: int, **params: Any) -> Any:
        return await self.client.get(self._path(media_id), params=self._params(params))

    async def upload(
        self,
        *,
        file_name: str,
        content: bytes,
        mime_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        files = {"file": (file_name, content, mime_type)}
        headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
        return await self.client.post(
            self.resource,
            data=metadata or {},
            files=files,
            headers=headers,
        )

    async def update(self, media_id: int, data: dict[str, Any]) -> Any:
        return await self.client.post(self._path(media_id), json_body=data)

    async def delete(self, media_id: int, *, force: bool = False) -> Any:
        return await self.client.delete(
            self._path(media_id), params={"force": str(force).lower()}
        )

    async def get_sizes(self, media_id: int) -> dict[str, Any]:
        payload = await self.get(media_id)
        media_details = (
            payload.get("media_details", {}) if isinstance(payload, dict) else {}
        )
        sizes = media_details.get("sizes") if isinstance(media_details, dict) else None
        return sizes or {}
