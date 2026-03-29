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

"""Theme information endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class ThemesAPI(WPBaseEndpoint):
    """WordPress themes endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "themes")

    async def list(self, **params: Any) -> Any:
        return await self.client.get(self.resource, params=self._params(params))

    async def get(self, stylesheet: str, **params: Any) -> Any:
        return await self.client.get(
            self._path(stylesheet), params=self._params(params)
        )

    async def activate(self, stylesheet: str) -> Any:
        return await self.client.post(
            self._path(stylesheet), json_body={"status": "active"}
        )

    async def get_active(self) -> Any:
        themes = await self.list(status="active")
        if isinstance(themes, list):
            return themes[0] if themes else None
        return themes
