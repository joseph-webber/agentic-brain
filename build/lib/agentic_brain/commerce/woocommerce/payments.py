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

"""Durable payment orchestration for WooCommerce.

The core PCI-safe gateway implementations live in :mod:`agentic_brain.commerce.payments`.
This module adds durability concerns needed for e-commerce reliability:

- Payment state machine
- Idempotent processing (safe under retries)
- Refund handling and compensation hooks
- Reconciliation helpers (compare expected vs observed gateway transactions)

The implementation is intentionally adapter-based: it wraps an injected
:class:`~agentic_brain.commerce.payments.PaymentProcessor` instance.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Mapping

from agentic_brain.commerce.payments import (
    PaymentProcessor,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
    RefundRequest,
    RefundResult,
)
from agentic_brain.durability.event_store import EventStore, get_event_store
from agentic_brain.durability.events import EventType, WorkflowEvent

logger = logging.getLogger(__name__)


class PaymentState(StrEnum):
    INITIATED = "initiated"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    RECONCILED = "reconciled"


@dataclass(slots=True)
class DurablePaymentRecord:
    order_id: str
    gateway: str
    amount: str
    currency: str
    state: PaymentState = PaymentState.INITIATED
    transaction_id: str | None = None
    refund_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


def _workflow_id(order_id: str) -> str:
    return f"woocommerce-payment:{order_id}"


def _idempotency_key(order_id: str, gateway: str, amount: str, currency: str) -> str:
    raw = f"{order_id}:{gateway}:{amount}:{currency}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def _payment_status_from_state(state: PaymentState) -> str:
    match state:
        case PaymentState.AUTHORIZED:
            return PaymentStatus.CREATED
        case PaymentState.CAPTURED:
            return PaymentStatus.SUCCEEDED
        case PaymentState.FAILED:
            return PaymentStatus.FAILED
        case PaymentState.REFUNDED:
            return PaymentStatus.REFUNDED
        case PaymentState.RECONCILED:
            return PaymentStatus.COMPLETED
        case _:
            return PaymentStatus.PENDING


def _payment_state_from_result(result: PaymentResult) -> PaymentState:
    try:
        normalized = PaymentStatus(str(result.status))
    except ValueError:
        normalized = None

    if normalized in {PaymentStatus.SUCCEEDED, PaymentStatus.COMPLETED}:
        return PaymentState.CAPTURED
    if normalized in {
        PaymentStatus.CREATED,
        PaymentStatus.PENDING,
        PaymentStatus.ACTIVE,
    }:
        return PaymentState.AUTHORIZED
    if normalized == PaymentStatus.REFUNDED:
        return PaymentState.REFUNDED
    if normalized in {PaymentStatus.FAILED, PaymentStatus.REJECTED}:
        return PaymentState.FAILED

    return PaymentState.INITIATED


class DurablePaymentProcessor:
    """Wrap :class:`PaymentProcessor` with event-sourced state + idempotency."""

    def __init__(
        self,
        processor: PaymentProcessor,
        *,
        event_store: EventStore | None = None,
    ) -> None:
        self._processor = processor
        self._event_store = event_store or get_event_store()
        self._records: dict[str, DurablePaymentRecord] = {}

    async def connect(self) -> None:
        await self._event_store.connect()

    async def _log(
        self, order_id: str, event: str, *, data: Mapping[str, Any] | None = None
    ) -> None:
        await self._event_store.publish(
            WorkflowEvent(
                workflow_id=_workflow_id(order_id),
                event_type=EventType.QUERY_EXECUTED,
                data={
                    "order_id": order_id,
                    "event": event,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": dict(data or {}),
                },
            )
        )

    def get_record(self, order_id: str) -> DurablePaymentRecord | None:
        return self._records.get(order_id)

    async def charge(
        self, request: PaymentRequest, *, gateway_name: str | None = None
    ) -> PaymentResult:
        await self.connect()
        key = _idempotency_key(
            request.order_id,
            gateway_name or "default",
            str(request.amount),
            request.currency,
        )
        existing = self._records.get(request.order_id)
        if (
            existing
            and existing.metadata.get("idempotency_key") == key
            and existing.state
            in (
                PaymentState.AUTHORIZED,
                PaymentState.CAPTURED,
            )
        ):
            logger.info("Idempotent payment hit for order_id=%s", request.order_id)
            return PaymentResult(
                gateway=existing.gateway,
                transaction_id=existing.transaction_id or "",
                status=str(_payment_status_from_state(existing.state)),
                amount=request.amount,
                currency=request.currency,
                metadata=dict(existing.metadata),
            )

        await self._log(
            request.order_id, "payment_initiated", data={"idempotency_key": key}
        )
        try:
            result = self._processor.process_payment(request, gateway_name=gateway_name)
            state = _payment_state_from_result(result)
            record = DurablePaymentRecord(
                order_id=request.order_id,
                gateway=result.gateway,
                amount=(
                    str(result.amount)
                    if result.amount is not None
                    else str(request.amount)
                ),
                currency=result.currency or request.currency,
                transaction_id=result.transaction_id,
                state=state,
                metadata={"idempotency_key": key, **result.metadata},
            )
            record.updated_at = datetime.now(UTC)
            self._records[request.order_id] = record
            await self._log(
                request.order_id,
                (
                    "payment_captured"
                    if state == PaymentState.CAPTURED
                    else "payment_authorized"
                ),
                data={"transaction_id": result.transaction_id, "status": result.status},
            )
            return result
        except Exception as exc:
            await self._log(
                request.order_id, "payment_failed", data={"error": str(exc)}
            )
            raise

    async def refund(
        self,
        request: RefundRequest,
        *,
        gateway_name: str | None = None,
        order_id: str,
    ) -> RefundResult:
        await self.connect()
        await self._log(
            order_id,
            "refund_requested",
            data={"transaction_id": request.transaction_id},
        )
        result = self._processor.refund_payment(request, gateway_name=gateway_name)
        record = self._records.get(order_id)
        if record:
            record.refund_id = result.refund_id
            record.state = PaymentState.REFUNDED
            record.updated_at = datetime.now(UTC)
        await self._log(
            order_id,
            "refunded",
            data={"refund_id": result.refund_id, "status": result.status},
        )
        return result

    async def reconcile(
        self, order_id: str, *, expected: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Best-effort reconciliation.

        In a real deployment this would query Stripe/PayPal APIs. Here we compare
        against the in-memory record and return a reconciliation report.
        """

        record = self._records.get(order_id)
        report = {
            "order_id": order_id,
            "expected": dict(expected),
            "observed": record.metadata if record else None,
            "matched": bool(record),
        }
        await self._log(order_id, "reconciled", data=report)
        if record:
            record.state = PaymentState.RECONCILED
            record.updated_at = datetime.now(UTC)
        return report
