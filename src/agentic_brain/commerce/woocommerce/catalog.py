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

"""Product catalog synchronisation for WooCommerce.

Durability goals
----------------
- Incremental sync via modified timestamps / pagination cursors
- Change detection to avoid redundant updates
- Bulk operations where supported by the store
- Image/media sync
- Variant handling (WooCommerce variations)

This module is a durability-friendly wrapper around :class:`WooCommerceAgent`.
It emits events to :class:`agentic_brain.durability.event_store.EventStore` so
sync progress can be resumed after a crash.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping, Sequence

from agentic_brain.durability.event_store import EventStore, get_event_store
from agentic_brain.durability.events import EventType, WorkflowEvent

from .agent import WooCommerceAgent

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CatalogSyncState:
    """Persistable incremental sync cursor."""

    last_modified_gmt: str | None = None
    last_page: int = 1


def _workflow_id(store_id: str) -> str:
    return f"woocommerce-catalog:{store_id}"


class WooCatalogSync:
    def __init__(
        self,
        woo: WooCommerceAgent,
        *,
        store_id: str = "default",
        event_store: EventStore | None = None,
    ) -> None:
        self._woo = woo
        self._store_id = store_id
        self._event_store = event_store or get_event_store()
        self.state = CatalogSyncState()

    async def connect(self) -> None:
        await self._event_store.connect()

    async def _log(self, event: str, *, data: Mapping[str, Any] | None = None) -> None:
        await self._event_store.publish(
            WorkflowEvent(
                workflow_id=_workflow_id(self._store_id),
                event_type=EventType.QUERY_EXECUTED,
                data={
                    "event": event,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": dict(data or {}),
                },
            )
        )

    async def incremental_sync(
        self, *, page_size: int = 100
    ) -> list[Mapping[str, Any]]:
        """Pull products incrementally.

        The default implementation uses the WooCommerce ``modified_after`` query
        parameter when possible, falling back to paging.
        """

        await self.connect()
        await self._log("sync_started", data={"state": self.state.__dict__})

        params: dict[str, Any] = {"per_page": page_size, "page": self.state.last_page}
        if self.state.last_modified_gmt:
            params["modified_after"] = self.state.last_modified_gmt

        products = await self._woo.get_products(params=params)
        if products:
            # Update cursor using the newest modified_gmt value.
            newest = None
            for product in products:
                modified = product.get("date_modified_gmt")
                if modified and (newest is None or modified > newest):
                    newest = modified
            if newest:
                self.state.last_modified_gmt = newest
            self.state.last_page += 1

        await self._log(
            "sync_page",
            data={"count": len(products), "state": self.state.__dict__},
        )
        return products

    async def bulk_update(
        self, updates: Iterable[Mapping[str, Any]]
    ) -> list[Mapping[str, Any]]:
        """Perform best-effort bulk updates.

        WooCommerce supports batch endpoints on some resources. The core agent
        does not yet wrap those; until it does, we apply updates sequentially.
        """

        await self.connect()
        results: list[Mapping[str, Any]] = []
        for update in updates:
            product_id = int(update.get("id"))
            payload = {k: v for k, v in update.items() if k != "id"}
            results.append(await self._woo.update_product(product_id, payload))
        await self._log("bulk_update", data={"count": len(results)})
        return results

    async def sync_images(
        self, product_id: int, images: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any]:
        """Sync product images.

        WooCommerce stores images as a list of objects with ``src``/``id``.
        This method applies basic change detection to avoid redundant updates.
        """

        await self.connect()
        current = await self._woo.get_product(product_id)
        current_images = list(current.get("images") or [])

        def _fingerprint(items: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
            fp: list[str] = []
            for item in items:
                src = item.get("src")
                if src:
                    fp.append(str(src))
                else:
                    fp.append(str(item.get("id") or ""))
            return tuple(fp)

        if _fingerprint(current_images) == _fingerprint(images):
            await self._log("images_noop", data={"product_id": product_id})
            return current

        updated = await self._woo.update_product(product_id, {"images": list(images)})
        await self._log(
            "images_synced",
            data={"product_id": product_id, "count": len(list(images))},
        )
        return updated

    async def sync_variations(
        self,
        product_id: int,
        variations: Sequence[Mapping[str, Any]],
        *,
        match_key: str = "sku",
    ) -> list[Mapping[str, Any]]:
        """Sync variable product variations.

        Uses the WooCommerce variation endpoints. Change detection is performed
        using either variation id or a stable key (default SKU).
        """

        await self.connect()
        existing = await self._woo.get_variations(product_id)
        by_id = {int(v.get("id")): v for v in existing if v.get("id")}
        by_key = {
            str(v.get(match_key)): v
            for v in existing
            if match_key in v and v.get(match_key)
        }

        results: list[Mapping[str, Any]] = []
        for desired in variations:
            desired_id = desired.get("id")
            payload = dict(desired)

            if desired_id:
                vid = int(desired_id)
                payload.pop("id", None)
                current = by_id.get(vid)
                if current and payload.items() <= dict(current).items():
                    results.append(current)
                    continue
                results.append(await self._woo.update_variation(product_id, vid, payload))
                continue

            key = str(desired.get(match_key) or "")
            current = by_key.get(key) if key else None
            if current and payload.items() <= dict(current).items():
                results.append(current)
                continue

            if current and current.get("id"):
                vid = int(current["id"])
                payload.pop("id", None)
                results.append(await self._woo.update_variation(product_id, vid, payload))
            else:
                payload.pop("id", None)
                results.append(await self._woo.create_variation(product_id, payload))

        await self._log(
            "variations_synced",
            data={"product_id": product_id, "count": len(results)},
        )
        return results
