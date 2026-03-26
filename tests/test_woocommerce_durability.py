# SPDX-License-Identifier: Apache-2.0
"""Durability tests for the WooCommerce integration."""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from agentic_brain.commerce.payments import PaymentMethodReference, PaymentRequest, PaymentResult
from agentic_brain.commerce.webhooks import WOO_EVENT_ORDER_CREATED
from agentic_brain.commerce.woocommerce.inventory import (
    DurableInventoryManager,
    InventoryItem,
)
from agentic_brain.commerce.woocommerce.orders import (
    InvalidOrderTransition,
    OrderAggregate,
    OrderEvent,
    OrderEventType,
    OrderState,
)
from agentic_brain.commerce.woocommerce.payments import DurablePaymentProcessor
from agentic_brain.commerce.woocommerce.webhooks import (
    DurableWooCommerceWebhookService,
    WebhookDuplicateError,
)
from agentic_brain.durability.event_store import EventStore
from agentic_brain.durability.task_queue import TaskQueue


def _sign(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return base64.b64encode(mac.digest()).decode("utf-8")


@pytest.mark.asyncio
async def test_webhook_processing_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "testsecret"
    body = b'{"id": 123}'

    recorded: list[tuple[str, dict]] = []

    class HooksStub:
        def fire(self, event_type: str, data: dict | None = None) -> None:
            recorded.append((event_type, data or {}))

    store = EventStore()
    queue = TaskQueue("test-webhooks")

    svc = DurableWooCommerceWebhookService(
        secret=secret,
        hooks=HooksStub(),
        event_store=store,
        queue=queue,
    )
    await svc.connect()

    headers = {
        "X-WC-Webhook-Topic": "order.created",
        "X-WC-Webhook-Signature": _sign(body, secret),
        "X-WC-Webhook-Delivery-ID": "delivery-1",
    }

    await svc.ingest(body, headers)
    assert await svc.work_once(timeout=0.01) == 1

    assert recorded
    assert recorded[0][0] == WOO_EVENT_ORDER_CREATED

    # Second delivery with the same id must be rejected as a duplicate.
    with pytest.raises(WebhookDuplicateError):
        await svc.ingest(body, headers)


def test_order_state_machine_transitions() -> None:
    agg = OrderAggregate("42")

    agg.apply(OrderEvent("42", OrderEventType.VALIDATED))
    assert agg.state == OrderState.VALIDATED

    agg.apply(OrderEvent("42", OrderEventType.INVENTORY_RESERVED))
    assert agg.state == OrderState.INVENTORY_RESERVED

    agg.apply(OrderEvent("42", OrderEventType.PAYMENT_AUTHORIZED))
    assert agg.state == OrderState.PAYMENT_AUTHORIZED

    agg.apply(OrderEvent("42", OrderEventType.PAYMENT_CAPTURED))
    assert agg.state == OrderState.PAYMENT_CAPTURED

    agg.apply(OrderEvent("42", OrderEventType.FULFILLMENT_STARTED))
    assert agg.state == OrderState.FULFILLING

    agg.apply(OrderEvent("42", OrderEventType.COMPLETED))
    assert agg.state == OrderState.COMPLETED

    with pytest.raises(InvalidOrderTransition):
        # Can't reserve inventory after completion
        agg.apply(OrderEvent("42", OrderEventType.INVENTORY_RESERVED))


@pytest.mark.asyncio
async def test_inventory_two_phase_reservation_commit_and_release() -> None:
    class WooStub:
        def __init__(self) -> None:
            self.stock: dict[int, int] = {10: 5}

        def get_product_sync(self, product_id: int):
            return {"id": product_id, "stock_quantity": self.stock.get(product_id, 0)}

        def update_product_sync(self, product_id: int, payload: dict):
            self.stock[product_id] = int(payload["stock_quantity"])
            return {"id": product_id, **payload}

    woo = WooStub()
    mgr = DurableInventoryManager(woo)  # type: ignore[arg-type]

    reservation = mgr.reserve(
        order_id="order-1",
        items=[InventoryItem(product_id=10, quantity=2)],
        reservation_id="res-1",
    )

    # Phase 1 doesn't touch remote stock.
    assert woo.stock[10] == 5

    await mgr.commit(reservation.reservation_id)
    assert woo.stock[10] == 3

    await mgr.release(reservation.reservation_id)
    assert woo.stock[10] == 5


@pytest.mark.asyncio
async def test_payment_idempotency_returns_normalized_status() -> None:
    class ProcessorStub:
        def __init__(self) -> None:
            self.calls = 0

        def process_payment(self, request: PaymentRequest, gateway_name: str | None = None):
            self.calls += 1
            return PaymentResult(
                gateway=gateway_name or "stripe",
                transaction_id="tx_123",
                status="succeeded",
                amount=request.amount,
                currency=request.currency,
            )

        def refund_payment(self, request, gateway_name: str | None = None):  # pragma: no cover
            raise NotImplementedError

    processor = DurablePaymentProcessor(ProcessorStub())

    req = PaymentRequest(
        amount="10.00",
        currency="USD",
        payment_method=PaymentMethodReference(token="tok_test"),
        order_id="order-99",
    )

    result1 = await processor.charge(req, gateway_name="stripe")
    result2 = await processor.charge(req, gateway_name="stripe")

    assert result1.transaction_id == result2.transaction_id
    assert result2.status == "succeeded"
    assert processor._processor.calls == 1
