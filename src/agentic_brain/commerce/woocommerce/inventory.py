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

"""Durable inventory synchronisation and reservation for WooCommerce.

WooCommerce stock updates are not transactional across multiple products.
To avoid overselling and to support safe retries, this module implements:

- Two-phase reservations (reserve locally -> commit to WooCommerce)
- Conflict detection and resolution (read-modify-write checks)
- Sync state tracking and recovery for partial updates
- Inventory event log via the durability EventStore

This layer is designed to be used by order processing sagas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Mapping

from agentic_brain.durability.event_store import EventStore, get_event_store
from agentic_brain.durability.events import EventType, WorkflowEvent
from agentic_brain.durability.retry import API_RETRY_POLICY, RetryPolicy, with_retry

from .agent import WooCommerceAgent

logger = logging.getLogger(__name__)


class InventoryReservationState(StrEnum):
    PENDING = "pending"
    COMMITTED = "committed"
    RELEASED = "released"
    FAILED = "failed"


class InventoryConflictError(RuntimeError):
    pass


@dataclass(slots=True)
class InventoryItem:
    product_id: int
    quantity: int
    sku: str | None = None


@dataclass(slots=True)
class InventoryReservation:
    reservation_id: str
    order_id: str
    items: list[InventoryItem]
    state: InventoryReservationState = InventoryReservationState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    committed_at: datetime | None = None


def _workflow_id(reservation_id: str) -> str:
    return f"woocommerce-inventory:{reservation_id}"


class DurableInventoryManager:
    """Two-phase reservation and sync layer."""

    def __init__(
        self,
        woo: WooCommerceAgent,
        *,
        event_store: EventStore | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._woo = woo
        self._event_store = event_store or get_event_store()
        self._retry_policy = retry_policy or API_RETRY_POLICY
        self._reservations: dict[str, InventoryReservation] = {}

    async def connect(self) -> None:
        await self._event_store.connect()

    async def _log(
        self,
        reservation: InventoryReservation,
        event: str,
        *,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        await self._event_store.publish(
            WorkflowEvent(
                workflow_id=_workflow_id(reservation.reservation_id),
                event_type=EventType.QUERY_EXECUTED,
                data={
                    "reservation_id": reservation.reservation_id,
                    "order_id": reservation.order_id,
                    "event": event,
                    "state": reservation.state,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": dict(data or {}),
                },
            )
        )

    def reserve(
        self,
        *,
        order_id: str,
        items: list[InventoryItem],
        ttl: timedelta = timedelta(minutes=15),
        reservation_id: str | None = None,
    ) -> InventoryReservation:
        """Phase 1: record a local reservation.

        This does not touch WooCommerce yet.
        """

        rid = (
            reservation_id
            or f"inv_{int(datetime.now(UTC).timestamp())}_{len(self._reservations) + 1}"
        )
        reservation = InventoryReservation(
            reservation_id=rid,
            order_id=str(order_id),
            items=list(items),
            expires_at=datetime.now(UTC) + ttl,
        )
        self._reservations[rid] = reservation
        return reservation

    def get_reservation(self, reservation_id: str) -> InventoryReservation | None:
        return self._reservations.get(reservation_id)

    async def commit(self, reservation_id: str) -> InventoryReservation:
        """Phase 2: apply reservation to WooCommerce stock quantities."""

        await self.connect()
        reservation = self._reservations[reservation_id]
        if reservation.state != InventoryReservationState.PENDING:
            return reservation

        if reservation.expires_at and datetime.now(UTC) > reservation.expires_at:
            reservation.state = InventoryReservationState.FAILED
            await self._log(reservation, "expired")
            raise InventoryConflictError("inventory reservation expired")

        await self._log(reservation, "commit_started")

        @with_retry(self._retry_policy)
        def _update(product_id: int, new_qty: int) -> Mapping[str, Any]:
            return self._woo.update_product_sync(
                product_id,
                {"stock_quantity": new_qty, "manage_stock": True},
            )

        applied: list[tuple[int, int]] = []
        try:
            for item in reservation.items:
                current = self._woo.get_product_sync(item.product_id)
                previous = int(current.get("stock_quantity") or 0)
                if previous < item.quantity:
                    raise InventoryConflictError(
                        f"insufficient stock for product {item.product_id}: {previous} < {item.quantity}"
                    )
                new_qty = previous - item.quantity
                _update(item.product_id, new_qty)
                applied.append((item.product_id, item.quantity))
                await self._log(
                    reservation,
                    "stock_committed",
                    data={
                        "product_id": item.product_id,
                        "previous": previous,
                        "new": new_qty,
                        "quantity": item.quantity,
                    },
                )

            reservation.state = InventoryReservationState.COMMITTED
            reservation.committed_at = datetime.now(UTC)
            await self._log(reservation, "commit_completed")
            return reservation

        except Exception as exc:
            reservation.state = InventoryReservationState.FAILED
            await self._log(reservation, "commit_failed", data={"error": str(exc)})

            # Best-effort recovery: roll back any already-applied decrements.
            for product_id, qty in reversed(applied):
                try:
                    current = self._woo.get_product_sync(product_id)
                    previous = int(current.get("stock_quantity") or 0)
                    _update(product_id, previous + qty)
                    await self._log(
                        reservation,
                        "stock_rolled_back",
                        data={"product_id": product_id, "quantity": qty},
                    )
                except Exception as rollback_exc:  # pragma: no cover
                    logger.warning(
                        "Rollback failed for product %s: %s",
                        product_id,
                        rollback_exc,
                    )
            raise

    async def release(self, reservation_id: str) -> InventoryReservation:
        """Release a reservation.

        If it was committed, this re-adds quantities (compensation).
        """

        await self.connect()
        reservation = self._reservations[reservation_id]

        if reservation.state == InventoryReservationState.RELEASED:
            return reservation

        if reservation.state == InventoryReservationState.COMMITTED:
            for item in reservation.items:
                current = self._woo.get_product_sync(item.product_id)
                previous = int(current.get("stock_quantity") or 0)
                self._woo.update_product_sync(
                    item.product_id,
                    {"stock_quantity": previous + item.quantity, "manage_stock": True},
                )
                await self._log(
                    reservation,
                    "stock_released",
                    data={
                        "product_id": item.product_id,
                        "previous": previous,
                        "new": previous + item.quantity,
                    },
                )

        reservation.state = InventoryReservationState.RELEASED
        await self._log(reservation, "released")
        return reservation
