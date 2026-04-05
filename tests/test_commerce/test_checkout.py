from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from agentic_brain.commerce.inventory import (
    InsufficientStockError,
    InventoryManager,
    ReservationNotFoundError,
)
from agentic_brain.commerce.models import WooAddress, WooOrderItem, WooOrderTotals
from agentic_brain.commerce.payments import PaymentRequest
from agentic_brain.commerce.woocommerce.agent import WooCommerceAgent


def test_checkout_reserve_stock_holds_quantity(inventory_manager: InventoryManager):
    reservation = inventory_manager.reserve_stock(product_id=1, quantity=2, sku="SKU-1")
    assert reservation.quantity == 2
    assert inventory_manager.get_local_stock(1) == 8


def test_checkout_release_reservation_restores_availability(
    inventory_manager: InventoryManager,
):
    reservation = inventory_manager.reserve_stock(product_id=1, quantity=2, sku="SKU-1")
    inventory_manager.release_reservation(reservation.reservation_id)
    assert inventory_manager.get_local_stock(1) == 10


def test_checkout_release_missing_reservation_raises(
    inventory_manager: InventoryManager,
):
    with pytest.raises(ReservationNotFoundError):
        inventory_manager.release_reservation("missing")


def test_checkout_confirm_reservation_deducts_stock(
    inventory_manager: InventoryManager,
):
    reservation = inventory_manager.reserve_stock(product_id=1, quantity=4, sku="SKU-1")
    inventory_manager.confirm_reservation(reservation.reservation_id)
    assert inventory_manager.get_local_stock(1) == 6


def test_checkout_confirm_missing_reservation_raises(
    inventory_manager: InventoryManager,
):
    with pytest.raises(ReservationNotFoundError):
        inventory_manager.confirm_reservation("missing")


def test_checkout_reserve_insufficient_stock_raises(
    inventory_manager: InventoryManager,
):
    with pytest.raises(InsufficientStockError):
        inventory_manager.reserve_stock(product_id=1, quantity=999, sku="SKU-1")


def test_checkout_prune_expired_reservations(inventory_manager: InventoryManager):
    reservation = inventory_manager.reserve_stock(
        product_id=1, quantity=1, sku="SKU-1", expires_in=timedelta(seconds=1)
    )
    # travel forward
    pruned = inventory_manager.prune_expired_reservations(
        now=reservation.expires_at + timedelta(seconds=1)
    )
    assert pruned == 1


def test_checkout_order_totals_validation():
    totals = WooOrderTotals(
        subtotal=Decimal("20.00"),
        discount_total=Decimal("5.00"),
        shipping_total=Decimal("3.00"),
        tax_total=Decimal("2.00"),
        total=Decimal("20.00"),
        currency="usd",
    )
    assert totals.currency == "USD"


def test_checkout_order_totals_invalid_formula_raises():
    with pytest.raises(ValueError):
        WooOrderTotals(
            subtotal=Decimal("20.00"),
            discount_total=Decimal("5.00"),
            shipping_total=Decimal("3.00"),
            tax_total=Decimal("2.00"),
            total=Decimal("999.00"),
        )


def test_checkout_address_validation_rejects_bad_email():
    with pytest.raises(ValueError):
        WooAddress(email="not-an-email", country="AU")


def test_checkout_order_item_requires_total_floor():
    with pytest.raises(ValueError):
        WooOrderItem(name="Thing", quantity=2, price=Decimal("10"), total=Decimal("5"))


def test_checkout_payment_request_requires_order_id(payment_method):
    with pytest.raises(Exception):
        PaymentRequest(
            amount=Decimal("1"),
            currency="USD",
            payment_method=payment_method,
            order_id="",
        )


def test_checkout_flow_creates_gateway_checkout(
    payment_processor, payment_request, fake_gateway
):
    result = payment_processor.create_checkout(
        payment_request,
        return_url="https://return.example",
        cancel_url="https://cancel.example",
    )
    assert result.checkout_url == "https://return.example"
    assert fake_gateway.calls
    assert fake_gateway.calls[-1].operation == "create_checkout"


def test_order_creation_calls_woocommerce_request(monkeypatch):
    agent = WooCommerceAgent(
        url="https://example.com",
        consumer_key="ck",
        consumer_secret="cs",
        verify_ssl=True,
        timeout=1,
    )
    agent._request = MagicMock(return_value={"id": 123, "status": "processing"})

    payload = {"payment_method": "cod", "status": "pending"}
    order = agent.create_order_sync(payload)

    agent._request.assert_called_once()
    args, kwargs = agent._request.call_args
    assert args[0] == "POST"
    assert args[1] == "orders"
    assert kwargs["json"] == payload
    assert order["id"] == 123


def test_order_update_calls_woocommerce_request(monkeypatch):
    agent = WooCommerceAgent(
        url="https://example.com",
        consumer_key="ck",
        consumer_secret="cs",
        verify_ssl=True,
        timeout=1,
    )
    agent._request = MagicMock(return_value={"id": 123, "status": "completed"})
    updated = agent.update_order_sync(123, {"status": "completed"})
    args, kwargs = agent._request.call_args
    assert args[0] == "PUT"
    assert args[1] == "orders/123"
    assert updated["status"] == "completed"
