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

"""Site settings endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class SettingsAPI(WPBaseEndpoint):
    """WordPress settings endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "settings")

    async def get_settings(self) -> Any:
        return await self.client.get(self.resource)

    async def update_settings(self, data: dict[str, Any]) -> Any:
        return await self.client.post(self.resource, json_body=data)
