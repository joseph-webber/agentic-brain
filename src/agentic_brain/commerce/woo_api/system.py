# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""WooCommerce system status endpoints."""

from __future__ import annotations

from typing import Any, Mapping

from .client import WooAPIClient, WooResourceAPI


class SystemAPI(WooResourceAPI):
    """Inspect WooCommerce system status and tools."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    async def status(self) -> Mapping[str, Any]:
        return await self.client.request("GET", "system_status")

    async def tools(self) -> list[Any]:
        return await self.client.request("GET", "system_status/tools")

    async def run_tool(
        self, tool_id: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        return await self.client.request(
            "POST", f"system_status/tools/{tool_id}", json_body=payload or {}
        )
