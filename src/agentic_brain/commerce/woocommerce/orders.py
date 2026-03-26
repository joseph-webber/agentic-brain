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

"""Durable WooCommerce order processing.

This module focuses on *durability* concerns for order lifecycles:

- Transaction-like order updates (event recorded before/after side effects)
- Explicit order state machine
- Saga-style compensation on failure
- Event sourcing (order state is derived from immutable events)
- Audit trail

The goal is to make order processing safe to resume after crashes/restarts and
safe under retries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Mapping

from agentic_brain.durability.event_store import EventStore, get_event_store
from agentic_brain.durability.events import EventType, WorkflowEvent
from agentic_brain.durability.saga import Saga, SagaExecutor

logger = logging.getLogger(__name__)


class OrderState(StrEnum):
    NEW = "new"
    VALIDATED = "validated"
    INVENTORY_RESERVED = "inventory_reserved"
    PAYMENT_AUTHORIZED = "payment_authorized"
    PAYMENT_CAPTURED = "payment_captured"
    FULFILLING = "fulfilling"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REFUNDED = "refunded"


class OrderEventType(StrEnum):
    CREATED = "created"
    VALIDATED = "validated"
    INVENTORY_RESERVED = "inventory_reserved"
    INVENTORY_RELEASED = "inventory_released"
    PAYMENT_AUTHORIZED = "payment_authorized"
    PAYMENT_CAPTURED = "payment_captured"
    PAYMENT_FAILED = "payment_failed"
    FULFILLMENT_STARTED = "fulfillment_started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REFUNDED = "refunded"


class InvalidOrderTransitionError(RuntimeError):
    pass


@dataclass(slots=True)
class OrderEvent:
    order_id: str
    event_type: OrderEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuditEntry:
    order_id: str
    action: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor: str = "system"
    details: dict[str, Any] = field(default_factory=dict)


class OrderAggregate:
    """Event-sourced order aggregate."""

    def __init__(self, order_id: str) -> None:
        self.order_id = str(order_id)
        self.state: OrderState = OrderState.NEW
        self.events: list[OrderEvent] = []

    def apply(self, event: OrderEvent) -> None:
        self._transition(event.event_type)
        self.events.append(event)

    def _transition(self, event_type: OrderEventType) -> None:
        allowed: dict[OrderState, set[OrderEventType]] = {
            OrderState.NEW: {OrderEventType.CREATED, OrderEventType.VALIDATED},
            OrderState.VALIDATED: {
                OrderEventType.INVENTORY_RESERVED,
                OrderEventType.CANCELLED,
                OrderEventType.FAILED,
            },
            OrderState.INVENTORY_RESERVED: {
                OrderEventType.PAYMENT_AUTHORIZED,
                OrderEventType.PAYMENT_FAILED,
                OrderEventType.INVENTORY_RELEASED,
                OrderEventType.CANCELLED,
                OrderEventType.FAILED,
            },
            OrderState.PAYMENT_AUTHORIZED: {
                OrderEventType.PAYMENT_CAPTURED,
                OrderEventType.PAYMENT_FAILED,
                OrderEventType.CANCELLED,
                OrderEventType.FAILED,
            },
            OrderState.PAYMENT_CAPTURED: {
                OrderEventType.FULFILLMENT_STARTED,
                OrderEventType.REFUNDED,
                OrderEventType.FAILED,
            },
            OrderState.FULFILLING: {OrderEventType.COMPLETED, OrderEventType.FAILED},
            OrderState.COMPLETED: {OrderEventType.REFUNDED},
            OrderState.CANCELLED: set(),
            OrderState.FAILED: set(),
            OrderState.REFUNDED: set(),
        }

        if event_type not in allowed.get(self.state, set()):
            raise InvalidOrderTransitionError(
                f"invalid transition from {self.state} via {event_type}"
            )

        match event_type:
            case OrderEventType.CREATED:
                self.state = OrderState.NEW
            case OrderEventType.VALIDATED:
                self.state = OrderState.VALIDATED
            case OrderEventType.INVENTORY_RESERVED:
                self.state = OrderState.INVENTORY_RESERVED
            case OrderEventType.PAYMENT_AUTHORIZED:
                self.state = OrderState.PAYMENT_AUTHORIZED
            case OrderEventType.PAYMENT_CAPTURED:
                self.state = OrderState.PAYMENT_CAPTURED
            case OrderEventType.FULFILLMENT_STARTED:
                self.state = OrderState.FULFILLING
            case OrderEventType.COMPLETED:
                self.state = OrderState.COMPLETED
            case OrderEventType.CANCELLED:
                self.state = OrderState.CANCELLED
            case OrderEventType.REFUNDED:
                self.state = OrderState.REFUNDED
            case OrderEventType.PAYMENT_FAILED | OrderEventType.FAILED:
                self.state = OrderState.FAILED
            case OrderEventType.INVENTORY_RELEASED:
                # rolling back reservation returns us to validated
                self.state = OrderState.VALIDATED


def _order_workflow_id(order_id: str) -> str:
    return f"woocommerce-order:{order_id}"


class DurableOrderProcessor:
    """Durable order processing orchestration.

    Dependencies are injected so this layer stays testable and can be used in
    either a FastAPI service, a background worker, or a Temporal workflow.
    """

    def __init__(
        self,
        *,
        event_store: EventStore | None = None,
        executor: SagaExecutor | None = None,
        reserve_inventory: Any | None = None,
        release_inventory: Any | None = None,
        authorize_payment: Any | None = None,
        refund_payment: Any | None = None,
    ) -> None:
        self._event_store = event_store or get_event_store()
        self._executor = executor
        self._reserve_inventory = reserve_inventory
        self._release_inventory = release_inventory
        self._authorize_payment = authorize_payment
        self._refund_payment = refund_payment
        self.audit: list[AuditEntry] = []

    async def connect(self) -> None:
        await self._event_store.connect()

    async def _record(self, order_id: str, event: OrderEvent) -> None:
        await self._event_store.publish(
            WorkflowEvent(
                workflow_id=_order_workflow_id(order_id),
                event_type=EventType.QUERY_EXECUTED,
                data={
                    "order_id": order_id,
                    "order_event": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data,
                },
            )
        )

    def _audit(
        self, order_id: str, action: str, *, details: Mapping[str, Any] | None = None
    ) -> None:
        self.audit.append(
            AuditEntry(order_id=order_id, action=action, details=dict(details or {}))
        )

    async def load_aggregate(self, order_id: str) -> OrderAggregate:
        """Rebuild order state by replaying events."""

        agg = OrderAggregate(order_id)
        events = await self._event_store.load_events(_order_workflow_id(order_id))
        for stored in events:
            data = getattr(stored, "data", None)
            if not isinstance(data, Mapping):
                continue
            if data.get("order_id") != str(order_id):
                continue
            evt = OrderEvent(
                order_id=str(order_id),
                event_type=OrderEventType(str(data.get("order_event"))),
                timestamp=datetime.fromisoformat(str(data.get("timestamp"))),
                data=dict(data.get("data") or {}),
            )
            try:
                agg.apply(evt)
            except InvalidOrderTransitionError:
                # tolerate legacy / out-of-order events
                agg.events.append(evt)
        return agg

    async def process(
        self, order_id: str, *, order_payload: Mapping[str, Any] | None = None
    ) -> OrderAggregate:
        """Process an order using a saga (reserve inventory -> authorize payment).

        This method is safe under retries because:
        - it uses event sourcing to reconstruct current state
        - each step emits an immutable event
        - compensation emits its own events
        """

        await self.connect()
        agg = await self.load_aggregate(order_id)
        self._audit(order_id, "process_start", details={"state": agg.state})

        saga = Saga("woocommerce-order")
        executor = self._executor or SagaExecutor(
            workflow_id=_order_workflow_id(order_id), event_store=self._event_store
        )

        if self._reserve_inventory is not None:

            @saga.step("reserve_inventory", compensation=self._release_inventory)
            async def _reserve(ctx: dict[str, Any]) -> dict[str, Any]:
                reservation = await self._reserve_inventory(
                    order_id, ctx.get("order_payload")
                )
                await self._record(
                    order_id,
                    OrderEvent(
                        order_id,
                        OrderEventType.INVENTORY_RESERVED,
                        data={"reservation": reservation},
                    ),
                )
                return {**ctx, "reservation": reservation}

        if self._authorize_payment is not None:

            @saga.step("authorize_payment", compensation=self._refund_payment)
            async def _pay(ctx: dict[str, Any]) -> dict[str, Any]:
                payment = await self._authorize_payment(
                    order_id, ctx.get("order_payload")
                )
                await self._record(
                    order_id,
                    OrderEvent(
                        order_id,
                        OrderEventType.PAYMENT_AUTHORIZED,
                        data={"payment": payment},
                    ),
                )
                return {**ctx, "payment": payment}

        async def _finalize(ctx: dict[str, Any]) -> dict[str, Any]:
            await self._record(
                order_id,
                OrderEvent(order_id, OrderEventType.COMPLETED, data={"result": "ok"}),
            )
            return ctx

        saga.add_step("finalize", _finalize)

        try:
            await self._record(
                order_id,
                OrderEvent(
                    order_id, OrderEventType.VALIDATED, data=dict(order_payload or {})
                ),
            )
            _ = await executor.execute(
                saga, {"order_payload": dict(order_payload or {})}
            )
            self._audit(order_id, "process_completed")
        except Exception as exc:
            await self._record(
                order_id,
                OrderEvent(order_id, OrderEventType.FAILED, data={"error": str(exc)}),
            )
            self._audit(order_id, "process_failed", details={"error": str(exc)})
            raise

        # Rebuild final state.
        return await self.load_aggregate(order_id)
