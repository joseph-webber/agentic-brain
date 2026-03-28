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

"""Search endpoints."""

from __future__ import annotations

from typing import Any

from .client import WPAPIClient, WPBaseEndpoint


class SearchAPI(WPBaseEndpoint):
    """WordPress search endpoints."""

    def __init__(self, client: WPAPIClient) -> None:
        super().__init__(client, "search")

    async def search(self, query: str, **params: Any) -> Any:
        payload = {"search": query}
        payload.update(params)
        return await self.client.get(self.resource, params=self._params(payload))
