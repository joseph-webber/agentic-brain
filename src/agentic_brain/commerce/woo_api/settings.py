# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""WooCommerce store settings endpoints."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .client import WooAPIClient, WooResourceAPI


class SettingsAPI(WooResourceAPI):
    """Read and update WooCommerce settings groups and options."""

    def __init__(self, client: WooAPIClient) -> None:
        super().__init__(client)

    async def list_groups(self) -> list[Any]:
        return await self.client.request("GET", "settings")

    async def retrieve_group(self, group_id: str) -> Mapping[str, Any]:
        return await self.client.request("GET", f"settings/{group_id}")

    async def list_options(self, group_id: str) -> list[Any]:
        return await self.client.request("GET", f"settings/{group_id}/settings")

    async def update_option(
        self,
        group_id: str,
        option_id: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self.client.request(
            "PUT",
            f"settings/{group_id}/settings/{option_id}",
            json_body=payload,
        )

    async def batch_update(
        self,
        group_id: str,
        *,
        update: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        if not update:
            raise ValueError("update payload required")
        return await self.client.batch(
            f"settings/{group_id}/batch",
            {"update": list(update)},
        )
