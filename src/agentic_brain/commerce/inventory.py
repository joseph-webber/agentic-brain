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

"""Stock / inventory management layer on top of WooCommerce."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


@dataclass
class StockLevel:
    """Current stock information for a single product or variation."""

    product_id: int
    sku: str
    name: str
    stock_quantity: int
    stock_status: str  # "instock" | "outofstock" | "onbackorder"
    manage_stock: bool
    low_stock_amount: Optional[int] = None

    @property
    def is_low(self) -> bool:
        threshold = self.low_stock_amount or 0
        return self.manage_stock and self.stock_quantity <= threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.stock_status == "outofstock" or (
            self.manage_stock and self.stock_quantity <= 0
        )


@dataclass
class StockAdjustment:
    """Records a stock quantity change."""

    product_id: int
    sku: str
    previous_quantity: int
    new_quantity: int
    delta: int
    reason: str = ""


@dataclass
class LowStockReport:
    """Summary of products below their low-stock threshold."""

    items: List[StockLevel] = field(default_factory=list)
    out_of_stock: List[StockLevel] = field(default_factory=list)

    @property
    def total_alerts(self) -> int:
        return len(self.items) + len(self.out_of_stock)


class InventoryManager:
    """High-level stock management built on top of a WooCommerce agent.

    Parameters
    ----------
    woo_agent:
        A :class:`~agentic_brain.commerce.woocommerce.WooCommerceAgent`
        instance used to query and update the store.
    low_stock_threshold:
        Default threshold used when a product has no ``low_stock_amount`` set.
    """

    def __init__(
        self,
        woo_agent: Any,
        low_stock_threshold: int = 5,
        allow_backorders: bool = False,
    ) -> None:
        self._woo = woo_agent
        self.low_stock_threshold = low_stock_threshold
        self.allow_backorders = allow_backorders
        # Local, multi-warehouse inventory state (optional)
        self._local_stock: dict[tuple[int, str], LocalStockRecord] = {}
        self._reservations: dict[str, StockReservation] = {}
        self._events: list[StockEvent] = []

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_stock_levels(self, page_size: int = 100) -> List[StockLevel]:
        """Return stock levels for all products in the store (sync)."""
        products: List[Dict[str, Any]] = []
        page = 1
        while True:
            batch = self._woo.get_products_sync(
                params={"per_page": page_size, "page": page}
            )
            if not batch:
                break
            products.extend(batch)
            if len(batch) < page_size:
                break
            page += 1

        return [self._to_stock_level(p) for p in products]

    def get_low_stock_report(self) -> LowStockReport:
        """Return products that are low or out of stock."""
        levels = self.get_stock_levels()
        report = LowStockReport()
        for level in levels:
            if level.is_out_of_stock:
                report.out_of_stock.append(level)
            elif level.is_low:
                report.items.append(level)
        logger.info(
            "Low-stock report: %d low, %d out-of-stock",
            len(report.items),
            len(report.out_of_stock),
        )
        return report

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def set_stock(
        self, product_id: int, quantity: int, reason: str = ""
    ) -> StockAdjustment:
        """Set stock quantity for a product and return a change record."""
        current_raw = self._woo.get_product_sync(product_id)
        previous = int(current_raw.get("stock_quantity") or 0)

        updated = self._woo.update_product_sync(
            product_id,
            {"stock_quantity": quantity, "manage_stock": True},
        )
        new_qty = int(updated.get("stock_quantity") or quantity)

        adj = StockAdjustment(
            product_id=product_id,
            sku=updated.get("sku", ""),
            previous_quantity=previous,
            new_quantity=new_qty,
            delta=new_qty - previous,
            reason=reason,
        )
        logger.info(
            "Stock adjusted for product %d: %d → %d (%s)",
            product_id,
            previous,
            new_qty,
            reason or "no reason",
        )
        return adj

    def adjust_stock(
        self, product_id: int, delta: int, reason: str = ""
    ) -> StockAdjustment:
        """Add or subtract *delta* units from the current stock quantity."""
        current_raw = self._woo.get_product_sync(product_id)
        previous = int(current_raw.get("stock_quantity") or 0)
        return self.set_stock(product_id, previous + delta, reason=reason)

    # ------------------------------------------------------------------
    # Local, multi-warehouse inventory engine
    # ------------------------------------------------------------------

    def _local_key(self, product_id: int, warehouse_id: str) -> tuple[int, str]:
        return product_id, warehouse_id

    def _get_local_record(
        self,
        product_id: int,
        sku: str,
        warehouse_id: str,
        create: bool = True,
    ) -> Optional[LocalStockRecord]:
        key = self._local_key(product_id, warehouse_id)
        record = self._local_stock.get(key)
        if record is None and create:
            record = LocalStockRecord(
                product_id=product_id,
                sku=sku,
                warehouse_id=warehouse_id,
                low_stock_threshold=self.low_stock_threshold,
            )
            self._local_stock[key] = record
        return record

    def _record_event(
        self,
        record: LocalStockRecord,
        *,
        event_type: StockEventType,
        before: int,
        after: int,
        delta: int,
        reserved_delta: int = 0,
        backordered_delta: int = 0,
        message: str = "",
        meta: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._events.append(
            StockEvent(
                product_id=record.product_id,
                sku=record.sku,
                warehouse_id=record.warehouse_id,
                event_type=event_type,
                quantity_before=before,
                quantity_after=after,
                delta=delta,
                reserved_delta=reserved_delta,
                backordered_delta=backordered_delta,
                message=message,
                meta=dict(meta or {}),
            )
        )

    @property
    def stock_history(self) -> List[StockEvent]:
        """Return the in-memory stock event history."""

        return list(self._events)

    def list_warehouses(self) -> List[str]:
        """Return all warehouses that have local stock records."""

        return sorted({wh for _, wh in self._local_stock})

    def update_local_stock(
        self,
        product_id: int,
        quantity: int,
        *,
        sku: str = "",
        warehouse_id: str = "default",
        low_stock_threshold: Optional[int] = None,
        reason: str = "manual_update",
    ) -> LocalStockRecord:
        """Set the absolute stock for a product/warehouse in local memory."""

        if quantity < 0:
            raise ValueError("quantity must be non-negative")

        record = self._get_local_record(product_id, sku, warehouse_id, create=True)
        before = record.quantity
        record.quantity = quantity
        if low_stock_threshold is not None:
            record.low_stock_threshold = low_stock_threshold
        elif record.low_stock_threshold == 0:
            record.low_stock_threshold = self.low_stock_threshold
        record.updated_at = _utcnow()

        delta = record.quantity - before
        if delta != 0:
            self._record_event(
                record,
                event_type=StockEventType.ADJUSTMENT,
                before=before,
                after=record.quantity,
                delta=delta,
                message=reason,
            )
        return record

    def adjust_local_stock(
        self,
        product_id: int,
        delta: int,
        *,
        sku: str = "",
        warehouse_id: str = "default",
        reason: str = "adjustment",
        allow_backorder: Optional[bool] = None,
    ) -> LocalStockRecord:
        """Adjust local stock up or down by ``delta`` units."""

        record = self._get_local_record(product_id, sku, warehouse_id, create=True)
        before = record.quantity

        if delta < 0:
            effective_allow_backorder = (
                allow_backorder
                if allow_backorder is not None
                else self.allow_backorders
            )
            if not effective_allow_backorder and before + delta < record.reserved:
                raise InsufficientStockError(
                    "cannot reduce stock below reserved quantity without backorders",
                )

        record.quantity = max(0, before + delta)
        record.updated_at = _utcnow()
        self._record_event(
            record,
            event_type=StockEventType.ADJUSTMENT,
            before=before,
            after=record.quantity,
            delta=record.quantity - before,
            message=reason,
        )
        return record

    def bulk_update_local_stock(
        self, updates: Iterable[Mapping[str, Any]]
    ) -> List[LocalStockRecord]:
        """Apply a series of local stock updates in one call."""

        results: List[LocalStockRecord] = []
        for item in updates:
            record = self.update_local_stock(
                product_id=int(item["product_id"]),
                quantity=int(item["quantity"]),
                sku=str(item.get("sku", "")),
                warehouse_id=str(item.get("warehouse_id", "default")),
                low_stock_threshold=item.get("low_stock_threshold"),
                reason=str(item.get("reason") or "bulk_update"),
            )
            results.append(record)
        return results

    def get_local_stock(
        self,
        product_id: int,
        *,
        warehouse_id: str = "default",
        include_reserved: bool = False,
    ) -> int:
        """Return the current local stock level for a product/warehouse."""

        record = self._get_local_record(
            product_id, sku="", warehouse_id=warehouse_id, create=False
        )
        if record is None:
            return 0
        return record.quantity if include_reserved else record.available

    def aggregate_local_stock(self, product_id: int) -> Dict[str, int]:
        """Aggregate local stock across all warehouses for a product."""

        total_quantity = 0
        total_reserved = 0
        total_backordered = 0
        for (pid, _), record in self._local_stock.items():
            if pid == product_id:
                total_quantity += record.quantity
                total_reserved += record.reserved
                total_backordered += record.backordered
        return {
            "total_quantity": total_quantity,
            "total_reserved": total_reserved,
            "total_backordered": total_backordered,
        }

    def reserve_stock(
        self,
        product_id: int,
        quantity: int,
        *,
        sku: str = "",
        warehouse_id: str = "default",
        reservation_id: Optional[str] = None,
        expires_in: Optional[timedelta] = None,
        allow_backorder: Optional[bool] = None,
    ) -> StockReservation:
        """Create a local stock reservation for checkout flows."""

        if quantity <= 0:
            raise ValueError("quantity must be positive")

        record = self._get_local_record(product_id, sku, warehouse_id, create=True)
        effective_allow_backorder = (
            allow_backorder if allow_backorder is not None else self.allow_backorders
        )

        available = record.available
        if quantity > available and not effective_allow_backorder:
            raise InsufficientStockError("insufficient available stock for reservation")

        from_stock = min(quantity, available)
        backordered_qty = max(0, quantity - from_stock)

        before = record.quantity
        record.reserved += quantity
        record.backordered += backordered_qty
        record.updated_at = _utcnow()

        rid = reservation_id or str(uuid4())
        expires_at = _utcnow() + expires_in if expires_in is not None else None
        reservation = StockReservation(
            reservation_id=rid,
            product_id=product_id,
            sku=sku,
            warehouse_id=warehouse_id,
            quantity=quantity,
            backordered_quantity=backordered_qty,
            created_at=_utcnow(),
            expires_at=expires_at,
        )
        self._reservations[rid] = reservation

        self._record_event(
            record,
            event_type=StockEventType.RESERVATION_CREATED,
            before=before,
            after=record.quantity,
            delta=0,
            reserved_delta=quantity,
            backordered_delta=backordered_qty,
            message="reservation created",
            meta={"reservation_id": rid},
        )
        return reservation

    def release_reservation(self, reservation_id: str) -> StockReservation:
        """Release a reservation without shipping stock."""

        reservation = self._reservations.pop(reservation_id, None)
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)

        record = self._get_local_record(
            reservation.product_id,
            reservation.sku or "",
            reservation.warehouse_id,
            create=True,
        )
        before = record.quantity
        record.reserved = max(0, record.reserved - reservation.quantity)
        record.backordered = max(
            0, record.backordered - reservation.backordered_quantity
        )
        record.updated_at = _utcnow()

        self._record_event(
            record,
            event_type=StockEventType.RESERVATION_RELEASED,
            before=before,
            after=record.quantity,
            delta=0,
            reserved_delta=-reservation.quantity,
            backordered_delta=-reservation.backordered_quantity,
            message="reservation released",
            meta={"reservation_id": reservation_id},
        )
        return reservation

    def confirm_reservation(self, reservation_id: str) -> StockReservation:
        """Confirm a reservation and deduct local on-hand stock."""

        reservation = self._reservations.pop(reservation_id, None)
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)

        record = self._get_local_record(
            reservation.product_id,
            reservation.sku or "",
            reservation.warehouse_id,
            create=True,
        )
        before = record.quantity
        shippable = min(
            reservation.quantity - reservation.backordered_quantity, record.quantity
        )
        record.quantity = max(0, record.quantity - shippable)
        record.reserved = max(0, record.reserved - reservation.quantity)
        record.updated_at = _utcnow()

        self._record_event(
            record,
            event_type=StockEventType.RESERVATION_CONFIRMED,
            before=before,
            after=record.quantity,
            delta=-shippable,
            reserved_delta=-reservation.quantity,
            backordered_delta=0,
            message="reservation confirmed",
            meta={"reservation_id": reservation_id},
        )
        return reservation

    def prune_expired_reservations(self, *, now: Optional[datetime] = None) -> int:
        """Remove expired reservations from memory and return count pruned."""

        current = now or _utcnow()
        to_delete = [
            rid
            for rid, res in self._reservations.items()
            if res.expires_at and res.expires_at <= current
        ]
        for rid in to_delete:
            self._reservations.pop(rid, None)
        return len(to_delete)

    def get_stock_alerts(self) -> List[StockAlert]:
        """Generate :class:`StockAlert` objects for low / out-of-stock items."""

        alerts: List[StockAlert] = []
        for record in self._local_stock.values():
            threshold = record.low_stock_threshold or self.low_stock_threshold
            if threshold <= 0:
                continue
            qty = record.quantity
            if qty > threshold:
                continue
            status = "out_of_stock" if qty <= 0 else "low_stock"
            severity = (
                AlertSeverity.CRITICAL
                if status == "out_of_stock"
                else AlertSeverity.WARNING
            )
            message = (
                f"{record.sku or record.product_id} in {record.warehouse_id} is {status} "
                f"({qty} <= {threshold})"
            )
            alerts.append(
                StockAlert(
                    product_id=record.product_id,
                    sku=record.sku,
                    warehouse_id=record.warehouse_id,
                    quantity=qty,
                    threshold=threshold,
                    status=status,
                    severity=severity,
                    message=message,
                )
            )
        return alerts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_stock_level(self, product: Dict[str, Any]) -> StockLevel:
        lsa_raw = product.get("low_stock_amount")
        lsa: Optional[int] = (
            int(lsa_raw) if lsa_raw is not None else self.low_stock_threshold
        )
        return StockLevel(
            product_id=int(product.get("id", 0)),
            sku=product.get("sku", ""),
            name=product.get("name", ""),
            stock_quantity=int(product.get("stock_quantity") or 0),
            stock_status=product.get("stock_status", "instock"),
            manage_stock=bool(product.get("manage_stock", False)),
            low_stock_amount=lsa,
        )


# ---------------------------------------------------------------------------
# Local inventory data structures
# ---------------------------------------------------------------------------


class InventoryError(Exception):
    """Base error for inventory operations."""


class InsufficientStockError(InventoryError):
    """Raised when there is not enough available stock for an operation."""


class ReservationNotFoundError(InventoryError):
    """Raised when a reservation cannot be found for a given identifier."""


class StockEventType(StrEnum):
    """Types of stock events recorded in the audit log."""

    ADJUSTMENT = "adjustment"
    RESERVATION_CREATED = "reservation_created"
    RESERVATION_RELEASED = "reservation_released"
    RESERVATION_CONFIRMED = "reservation_confirmed"


@dataclass
class LocalStockRecord:
    """Current stock state for a product at a given warehouse."""

    product_id: int
    sku: str
    warehouse_id: str
    quantity: int = 0
    reserved: int = 0
    backordered: int = 0
    low_stock_threshold: int = 0
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def available(self) -> int:
        """Return available sellable stock (on hand minus reserved)."""

        return max(0, self.quantity - self.reserved)


@dataclass(frozen=True)
class StockEvent:
    """Immutable audit record for a stock operation."""

    product_id: int
    sku: str
    warehouse_id: str
    event_type: StockEventType
    quantity_before: int
    quantity_after: int
    delta: int
    reserved_delta: int = 0
    backordered_delta: int = 0
    message: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StockReservation:
    """Represents a temporary hold on stock during checkout."""

    reservation_id: str
    product_id: int
    sku: str
    warehouse_id: str
    quantity: int
    backordered_quantity: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    expires_at: Optional[datetime] = None


class AlertSeverity(StrEnum):
    """Severity level for stock alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class StockAlert:
    """Low stock or out-of-stock notification for a product/warehouse."""

    product_id: int
    sku: str
    warehouse_id: str
    quantity: int
    threshold: int
    status: str  # low_stock | out_of_stock
    severity: AlertSeverity
    message: str
    created_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Sync helper
# ---------------------------------------------------------------------------


class WooProductClient(Protocol):
    """Minimal protocol for WooCommerce product clients.

    The :class:`InventorySync` helper only needs synchronous methods for unit
    tests and simple agents.  ``WooCommerceAgent`` satisfies this protocol via
    its ``get_product_sync`` and ``update_product_sync`` methods.
    """

    def get_product_sync(self, product_id: int) -> Dict[str, Any]: ...

    def update_product_sync(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]: ...


class InventorySync:
    """Synchronise :class:`InventoryManager` with an external system.

    This helper knows how to translate between WooCommerce-style payloads and
    the local multi-warehouse inventory managed by :class:`InventoryManager`,
    but it does not perform any scheduling itself.
    """

    def __init__(
        self,
        client: WooProductClient,
        manager: Optional[InventoryManager] = None,
        warehouse_id: str = "default",
    ) -> None:
        self.client = client
        self.manager = manager or InventoryManager(woo_agent=client)
        self.warehouse_id = warehouse_id

    def sync_from_remote(
        self, product_id: int, *, warehouse_id: Optional[str] = None
    ) -> LocalStockRecord:
        """Pull stock information from WooCommerce into the local manager."""

        payload = self.client.get_product_sync(product_id)
        raw_qty = payload.get("stock_quantity")
        if raw_qty is None:
            raw_qty = payload.get("stock", 0)
        quantity = int(raw_qty or 0)
        threshold_raw = payload.get("low_stock_threshold") or payload.get(
            "low_stock_amount"
        )
        threshold = int(threshold_raw) if threshold_raw is not None else None
        sku = str(payload.get("sku", ""))
        wh = warehouse_id or self.warehouse_id
        return self.manager.update_local_stock(
            product_id=product_id,
            quantity=quantity,
            sku=sku,
            warehouse_id=wh,
            low_stock_threshold=threshold,
            reason="sync_from_remote",
        )

    def build_remote_payload(self, product_id: int) -> Dict[str, Any]:
        """Build a WooCommerce-compatible stock payload from local state."""

        aggregate = self.manager.aggregate_local_stock(product_id)
        if (
            aggregate["total_quantity"] == 0
            and aggregate["total_reserved"] == 0
            and aggregate["total_backordered"] == 0
        ):
            return {}

        min_threshold: Optional[int] = None
        for (pid, _), record in self.manager._local_stock.items():  # type: ignore[attr-defined]
            if pid == product_id and record.low_stock_threshold:
                min_threshold = (
                    record.low_stock_threshold
                    if min_threshold is None
                    else min(min_threshold, record.low_stock_threshold)
                )

        payload: Dict[str, Any] = {"stock_quantity": aggregate["total_quantity"]}
        if min_threshold is not None:
            payload["low_stock_threshold"] = min_threshold
        payload["manage_stock"] = True
        payload["backorders"] = "notify" if self.manager.allow_backorders else "no"
        return payload

    def push_to_remote(self, product_id: int) -> Dict[str, Any]:
        """Push current local stock to WooCommerce and return the payload used."""

        payload = self.build_remote_payload(product_id)
        if not payload:
            return {}
        self.client.update_product_sync(product_id, payload)
        return payload


__all__ = [
    # Remote-level structures
    "StockLevel",
    "StockAdjustment",
    "LowStockReport",
    "InventoryManager",
    # Local inventory engine
    "InventoryError",
    "InsufficientStockError",
    "ReservationNotFoundError",
    "LocalStockRecord",
    "StockEvent",
    "StockEventType",
    "StockReservation",
    "AlertSeverity",
    "StockAlert",
    # Sync helper
    "WooProductClient",
    "InventorySync",
]
