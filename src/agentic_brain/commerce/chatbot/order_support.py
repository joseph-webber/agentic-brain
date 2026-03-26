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
"""Order support helpers for chat-based WooCommerce support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Optional

from ..models import WooOrder


@dataclass(frozen=True)
class OrderStatusSummary:
    """Normalised order status with a human-friendly description."""

    order_id: int
    status: str
    is_complete: bool
    is_shipped: bool
    description: str


@dataclass(frozen=True)
class ShippingUpdate:
    """A lightweight description of the current shipping state."""

    order_id: int
    status: str
    message: str


@dataclass(frozen=True)
class ReturnRequest:
    """Represents a request to start a return or refund."""

    order_id: int
    allowed: bool
    reason: str
    notes: str | None = None


@dataclass(frozen=True)
class ModificationRequest:
    """Represents a request to modify an order (address/items)."""

    order_id: int
    allowed: bool
    change_type: str
    notes: str | None = None


@dataclass(frozen=True)
class EtaEstimate:
    """Simple delivery ETA estimate.

    The chatbot can verbalise this and optionally show the date in the UI.
    """

    order_id: int
    eta_date: date
    confidence: str
    message: str


class OrderSupport:
    """Pure helper for order-related chatbot flows."""

    def summarise_status(self, order: WooOrder) -> OrderStatusSummary:
        """Normalise WooCommerce order status into a friendly summary."""

        raw = (order.status or "").lower()
        is_complete = raw in {"completed", "refunded"}
        is_shipped = raw in {"completed", "processing", "on-hold"}

        if raw == "pending":
            desc = "Order received, awaiting payment."
        elif raw == "processing":
            desc = "Payment received, your order is being prepared."
        elif raw == "completed":
            desc = "Order completed. It should have been delivered."
        elif raw == "on-hold":
            desc = "Order is on hold. A team member may need to review it."
        elif raw == "refunded":
            desc = "Order has been refunded."
        elif raw == "cancelled":
            desc = "Order was cancelled."
        elif raw == "failed":
            desc = "Payment failed. You may need to try again."
        else:
            desc = f"Status: {order.status}."

        return OrderStatusSummary(
            order_id=int(order.id),
            status=raw or "unknown",
            is_complete=is_complete,
            is_shipped=is_shipped,
            description=desc,
        )

    def shipping_update(self, order: WooOrder) -> ShippingUpdate:
        """Return a high-level shipping update.

        For now we infer shipping state from the order status only.
        """

        summary = self.summarise_status(order)
        if summary.status in {"pending", "failed"}:
            msg = "Your order has not been shipped yet."
        elif summary.status in {"processing", "on-hold"}:
            msg = "Your order is being prepared for shipment."
        elif summary.status == "completed":
            msg = "Your order should have been delivered."
        elif summary.status == "refunded":
            msg = "This order was refunded and will not be delivered."
        elif summary.status == "cancelled":
            msg = "This order was cancelled and will not be delivered."
        else:
            msg = summary.description

        return ShippingUpdate(
            order_id=summary.order_id, status=summary.status, message=msg
        )

    # ------------------------------------------------------------------
    # Returns & modifications
    # ------------------------------------------------------------------

    def can_return(
        self,
        order: WooOrder,
        *,
        days_since_delivery: int,
        window_days: int = 30,
    ) -> ReturnRequest:
        """Determine whether a return can be initiated."""

        if order.status.lower() not in {"completed", "processing", "on-hold"}:
            return ReturnRequest(
                order_id=int(order.id),
                allowed=False,
                reason="Order is not eligible for return in its current status.",
            )

        if days_since_delivery > window_days:
            return ReturnRequest(
                order_id=int(order.id),
                allowed=False,
                reason=f"Returns are only allowed within {window_days} days of delivery.",
            )

        return ReturnRequest(
            order_id=int(order.id),
            allowed=True,
            reason="Return can be initiated.",
        )

    def request_modification(
        self,
        order: WooOrder,
        *,
        change_type: str,
        hours_since_creation: int,
    ) -> ModificationRequest:
        """Check if an order modification request should be accepted."""

        modifiable = order.status.lower() in {"pending", "processing", "on-hold"}
        if not modifiable:
            return ModificationRequest(
                order_id=int(order.id),
                allowed=False,
                change_type=change_type,
                notes="Order can no longer be modified.",
            )

        if hours_since_creation > 24:
            return ModificationRequest(
                order_id=int(order.id),
                allowed=False,
                change_type=change_type,
                notes="Modifications are only allowed within 24 hours of placing the order.",
            )

        return ModificationRequest(
            order_id=int(order.id),
            allowed=True,
            change_type=change_type,
            notes="Request can be passed to a human agent for processing.",
        )

    # ------------------------------------------------------------------
    # ETA estimation
    # ------------------------------------------------------------------

    def estimate_eta(
        self,
        order: WooOrder,
        *,
        created_at: datetime,
        now: Optional[datetime] = None,
        domestic: bool = True,
    ) -> EtaEstimate:
        """Rough delivery ETA based on creation time.

        This is intentionally simple and deterministic so the chatbot
        can explain what it is doing. Real-world deployments can swap in
        a more advanced estimator that uses carrier tracking data.
        """

        now = now or datetime.now(UTC)
        days = 3 if domestic else 7
        eta_dt = created_at + timedelta(days=days)
        confidence = "medium"

        if order.status.lower() in {"completed", "refunded", "cancelled"}:
            confidence = "low"
        elif order.status.lower() in {"processing", "on-hold"}:
            confidence = "high"

        message = f"Estimated delivery around {eta_dt.date().isoformat()}."

        return EtaEstimate(
            order_id=int(order.id),
            eta_date=eta_dt.date(),
            confidence=confidence,
            message=message,
        )
