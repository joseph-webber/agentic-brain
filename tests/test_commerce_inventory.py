# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Unit tests for the WooCommerce inventory engine.

The tests intentionally avoid real HTTP and instead exercise the
in-memory :class:`InventoryManager` and :class:`InventorySync` helpers with
simple stub clients.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from agentic_brain.commerce.inventory import (
    InsufficientStockError,
    InventoryManager,
    InventorySync,
    StockAlert,
)


class StubWooClient:
    """Minimal stub implementing the WooProductClient protocol."""

    def __init__(self) -> None:
        self.updated: list[tuple[int, dict]] = []

    def get_product_sync(self, product_id: int) -> dict:
        return {
            "id": product_id,
            "name": "Braille Keyboard",
            "price": "199.95",
            "description": "Accessible mechanical keyboard",
            "sku": "BK-101",
            "stock_quantity": 7,
            "categories": [],
            "images": [],
            "low_stock_threshold": 2,
        }

    def update_product_sync(self, product_id: int, data: dict) -> dict:
        self.updated.append((product_id, data))
        return {"id": product_id, "payload": data}


def test_basic_stock_tracking_and_bulk_updates():
    manager = InventoryManager(woo_agent=StubWooClient(), low_stock_threshold=10)

    # Single update (local engine)
    manager.update_local_stock(
        product_id=1, sku="SKU-1", warehouse_id="ADL", quantity=20
    )
    assert manager.get_local_stock(product_id=1, warehouse_id="ADL") == 20

    # Bulk update across warehouses
    manager.bulk_update_local_stock(
        [
            {
                "product_id": 1,
                "warehouse_id": "ADL",
                "quantity": 15,
                "reason": "cycle_count",
            },
            {
                "product_id": 1,
                "warehouse_id": "SYD",
                "quantity": 5,
                "low_stock_threshold": 2,
            },
        ]
    )

    assert manager.get_local_stock(product_id=1, warehouse_id="ADL") == 15
    assert manager.get_local_stock(product_id=1, warehouse_id="SYD") == 5

    aggregate = manager.aggregate_local_stock(product_id=1)
    assert aggregate["total_quantity"] == 20


def test_low_stock_alerts_and_multi_warehouse_behaviour():
    manager = InventoryManager(woo_agent=StubWooClient(), low_stock_threshold=5)

    manager.update_local_stock(product_id=2, warehouse_id="ADL", quantity=3)
    manager.update_local_stock(
        product_id=2, warehouse_id="SYD", quantity=0, low_stock_threshold=1
    )

    alerts = manager.get_stock_alerts()
    assert alerts, "expected at least one low stock alert"
    assert all(isinstance(a, StockAlert) for a in alerts)

    statuses = {a.status for a in alerts}
    assert "low_stock" in statuses
    assert "out_of_stock" in statuses


def test_reservations_support_backorders_and_release():
    manager = InventoryManager(
        woo_agent=StubWooClient(), low_stock_threshold=1, allow_backorders=True
    )
    manager.update_local_stock(product_id=3, sku="BK-101", quantity=2)

    reservation = manager.reserve_stock(product_id=3, quantity=3)
    # Local records are keyed per warehouse; default is "default"
    record = manager._get_local_record(3, "BK-101", "default")  # type: ignore[attr-defined]
    assert record is not None
    assert record.reserved == 3
    assert record.backordered == 1
    assert reservation.backordered_quantity == 1

    # Releasing returns to original state
    manager.release_reservation(reservation.reservation_id)
    record_after = manager._get_local_record(3, "BK-101", "default")  # type: ignore[attr-defined]
    assert record_after is not None
    assert record_after.reserved == 0
    assert record_after.backordered == 0


def test_reservations_fail_without_backorders_when_stock_insufficient():
    manager = InventoryManager(woo_agent=StubWooClient(), allow_backorders=False)
    manager.update_local_stock(product_id=9, quantity=1)

    with pytest.raises(InsufficientStockError):
        manager.reserve_stock(product_id=9, quantity=2)


def test_confirm_reservation_reduces_on_hand_stock():
    manager = InventoryManager(woo_agent=StubWooClient())
    manager.update_local_stock(product_id=4, quantity=5)

    reservation = manager.reserve_stock(product_id=4, quantity=2)
    manager.confirm_reservation(reservation.reservation_id)

    assert manager.get_local_stock(product_id=4, include_reserved=True) == 3


def test_history_records_events_for_operations():
    manager = InventoryManager(woo_agent=StubWooClient())
    manager.update_local_stock(product_id=5, quantity=10)
    manager.adjust_local_stock(product_id=5, delta=-2)
    res = manager.reserve_stock(product_id=5, quantity=3)
    manager.confirm_reservation(res.reservation_id)

    history = manager.stock_history
    assert len(history) >= 3
    event_types = {e.event_type for e in history}
    # At minimum we should have adjustments and reservation events
    assert any("ADJUSTMENT" in et.name for et in event_types)
    assert any("RESERVATION" in et.name for et in event_types)


def test_inventory_sync_pulls_and_pushes_stock():
    client = StubWooClient()
    manager = InventoryManager(woo_agent=client)
    sync = InventorySync(client=client, manager=manager)

    # Pull from remote payload into manager
    record = sync.sync_from_remote(product_id=123, warehouse_id="ADL")
    assert record.quantity == 7
    assert manager.get_local_stock(product_id=123, warehouse_id="ADL") == 7

    # Change local quantity and push back to WooCommerce
    manager.update_local_stock(
        product_id=123, warehouse_id="ADL", quantity=1, low_stock_threshold=2
    )
    payload = sync.push_to_remote(product_id=123)
    assert payload["stock_quantity"] == 1
    assert payload["low_stock_threshold"] == 2
    assert client.updated[-1][0] == 123
    assert client.updated[-1][1]["stock_quantity"] == 1


def test_prune_expired_reservations_does_not_change_stock():
    manager = InventoryManager(woo_agent=StubWooClient())
    manager.update_local_stock(product_id=7, quantity=5)

    res = manager.reserve_stock(
        product_id=7, quantity=2, expires_in=timedelta(seconds=0)
    )
    before = manager.get_local_stock(product_id=7, include_reserved=True)
    pruned = manager.prune_expired_reservations()

    assert pruned == 1
    after = manager.get_local_stock(product_id=7, include_reserved=True)
    assert before == after
    # Reservation object is no longer tracked
    with pytest.raises(Exception):
        manager.release_reservation(res.reservation_id)
