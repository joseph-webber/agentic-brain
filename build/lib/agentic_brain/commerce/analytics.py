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

"""WooCommerce analytics for real e-commerce insights.

This module is intentionally *API-light*:
- It fetches raw WooCommerce resources (orders/products/customers)
- Computes useful analytics locally (revenue, AOV, CLV, funnels)
- Produces dashboard-friendly JSON-ish structures
- Can emit RAG-friendly documents so natural language queries can answer:
    - "What were our top selling products last month?"
    - "Which customers have the highest lifetime value?"

No external analytics stack is required; you can optionally pass session/event
counts (visits, add-to-cart, checkout) for conversion tracking.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


Money = Decimal


@dataclass(frozen=True)
class SalesReport:
    """Aggregated sales for a time range, bucketed by day/week/month."""

    start: datetime
    end: datetime
    granularity: str  # daily|weekly|monthly
    currency: str
    total_orders: int
    gross_revenue: Money
    discounts: Money
    shipping: Money
    tax: Money
    net_revenue: Money
    average_order_value: Money
    buckets: list[dict[str, Any]]  # {label, orders, gross_revenue, net_revenue}


@dataclass(frozen=True)
class ProductPerformance:
    product_id: int
    name: str
    quantity: int
    revenue: Money


@dataclass(frozen=True)
class CustomerLifetimeValue:
    customer_key: str  # customer_id or billing_email
    name: str
    email: str
    orders: int
    lifetime_value: Money
    first_order: Optional[datetime] = None
    last_order: Optional[datetime] = None


@dataclass(frozen=True)
class InventoryAlert:
    product_id: int
    name: str
    stock_status: str
    stock_quantity: Optional[int]
    threshold: int
    severity: str  # low_stock|out_of_stock


@dataclass(frozen=True)
class FunnelReport:
    start: datetime
    end: datetime
    currency: str
    orders_created: int
    orders_paid: int
    orders_completed: int
    orders_cancelled: int
    orders_failed: int
    orders_refunded: int
    completion_rate: float
    payment_rate: float
    sessions: Optional[int] = None
    add_to_cart: Optional[int] = None
    checkout_started: Optional[int] = None
    order_conversion_rate: Optional[float] = None


@dataclass(frozen=True)
class ConversionRateReport:
    start: datetime
    end: datetime
    sessions: int
    orders_completed: int
    conversion_rate: float


class WooCommerceAPI(Protocol):
    """Minimal interface for talking to WooCommerce REST endpoints."""

    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any: ...


class RequestsWooCommerceAPI:
    def __init__(
        self,
        store_url: str,
        consumer_key: str,
        consumer_secret: str,
        api_base: str = "/wp-json/wc/v3",
        timeout_seconds: int = 30,
    ):
        self.store_url = store_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.api_base = api_base
        self.timeout_seconds = timeout_seconds
        self._session = None

    def _ensure_session(self) -> Any:
        if self._session is None:
            import requests

            sess = requests.Session()
            sess.auth = (self.consumer_key, self.consumer_secret)
            sess.headers["Content-Type"] = "application/json"
            self._session = sess
        return self._session

    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        sess = self._ensure_session()
        url = f"{self.store_url}{self.api_base}/{path.lstrip('/')}"
        resp = sess.get(url, params=params or {}, timeout=self.timeout_seconds)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: Any) -> Money:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_wc_datetime(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    v = value
    # Woo dates sometimes come with trailing Z
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _bucket_label(granularity: str, dt: datetime) -> str:
    if granularity == "daily":
        return dt.date().isoformat()
    if granularity == "weekly":
        week_start = dt.date() - timedelta(days=dt.date().weekday())
        return week_start.isoformat()
    if granularity == "monthly":
        return f"{dt.year:04d}-{dt.month:02d}"
    raise ValueError(f"Unknown granularity: {granularity}")


def _safe_currency(orders: Iterable[dict[str, Any]], default: str = "") -> str:
    for o in orders:
        currency = o.get("currency")
        if isinstance(currency, str) and currency.strip():
            return currency
    return default


def _format_money(amount: Money, currency: str) -> str:
    # Keep formatting predictable for dashboards & RAG docs.
    q = amount.quantize(Decimal("0.01"))
    return f"{currency} {q}".strip()


def _date_range_last_month(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    first_of_this_month = datetime(now.year, now.month, 1, tzinfo=UTC)
    last_month_end = first_of_this_month - timedelta(seconds=1)
    last_month_start = datetime(
        last_month_end.year, last_month_end.month, 1, tzinfo=UTC
    )
    return last_month_start, first_of_this_month


# ---------------------------------------------------------------------------
# Main analytics
# ---------------------------------------------------------------------------


class WooCommerceAnalytics:
    """Compute analytics from a WooCommerce store."""

    def __init__(
        self,
        store_url: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        api: Optional[WooCommerceAPI] = None,
        default_currency: str = "",
        included_order_statuses: Optional[list[str]] = None,
    ):
        store_url = (store_url or os.getenv("WOOCOMMERCE_URL", "")).rstrip("/")
        consumer_key = consumer_key or os.getenv("WOOCOMMERCE_CONSUMER_KEY", "")
        consumer_secret = consumer_secret or os.getenv(
            "WOOCOMMERCE_CONSUMER_SECRET", ""
        )

        if api is None:
            if not (store_url and consumer_key and consumer_secret):
                raise ValueError(
                    "WooCommerce credentials missing. Provide store_url/consumer_key/consumer_secret "
                    "or set WOOCOMMERCE_URL, WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET."
                )
            api = RequestsWooCommerceAPI(
                store_url=store_url,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
            )

        self.api = api
        self.default_currency = default_currency
        self.included_order_statuses = included_order_statuses or [
            "processing",
            "completed",
        ]

    # -------------------------
    # Raw fetchers
    # -------------------------

    def fetch_orders(
        self,
        start: datetime,
        end: datetime,
        statuses: Optional[list[str]] = None,
        per_page: int = 100,
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch orders in [start, end).

        Uses WooCommerce REST params: after/before, per_page, page.
        """

        statuses = statuses or self.included_order_statuses
        # Use ISO8601 with timezone.
        after = start.astimezone(UTC).isoformat()
        before = end.astimezone(UTC).isoformat()

        orders: list[dict[str, Any]] = []
        for status in statuses:
            page = 1
            while page <= max_pages:
                params = {
                    "after": after,
                    "before": before,
                    "status": status,
                    "per_page": per_page,
                    "page": page,
                    "orderby": "date",
                    "order": "asc",
                }
                batch = self.api.get("orders", params=params)
                if not isinstance(batch, list) or not batch:
                    break
                orders.extend(batch)
                if len(batch) < per_page:
                    break
                page += 1

        return orders

    def fetch_products(
        self,
        per_page: int = 100,
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        page = 1
        while page <= max_pages:
            batch = self.api.get(
                "products", params={"per_page": per_page, "page": page}
            )
            if not isinstance(batch, list) or not batch:
                break
            products.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return products

    # -------------------------
    # Sales reports
    # -------------------------

    def sales_report(
        self, start: datetime, end: datetime, granularity: str
    ) -> SalesReport:
        orders = self.fetch_orders(start, end)
        currency = _safe_currency(orders, default=self.default_currency)

        bucket_map: dict[str, dict[str, Any]] = {}

        gross = Decimal("0")
        discounts = Decimal("0")
        shipping = Decimal("0")
        tax = Decimal("0")

        for o in orders:
            created = _parse_wc_datetime(
                o.get("date_created_gmt") or o.get("date_created")
            )
            if created is None:
                continue
            label = _bucket_label(granularity, created)
            bucket = bucket_map.setdefault(
                label,
                {
                    "label": label,
                    "orders": 0,
                    "gross_revenue": Decimal("0"),
                    "net_revenue": Decimal("0"),
                },
            )

            total = _to_decimal(o.get("total"))
            disc = _to_decimal(o.get("discount_total"))
            ship = _to_decimal(o.get("shipping_total"))
            t = _to_decimal(o.get("total_tax"))

            bucket["orders"] += 1
            bucket["gross_revenue"] += total
            # "Net" here means revenue after discounts (still includes shipping/tax).
            bucket["net_revenue"] += total - disc

            gross += total
            discounts += disc
            shipping += ship
            tax += t

        total_orders = len(orders)
        net = gross - discounts
        aov = (gross / total_orders) if total_orders else Decimal("0")

        buckets = list(bucket_map.values())
        buckets.sort(key=lambda b: b["label"])

        return SalesReport(
            start=start,
            end=end,
            granularity=granularity,
            currency=currency,
            total_orders=total_orders,
            gross_revenue=gross,
            discounts=discounts,
            shipping=shipping,
            tax=tax,
            net_revenue=net,
            average_order_value=aov,
            buckets=buckets,
        )

    def daily_sales(self, start: datetime, end: datetime) -> SalesReport:
        return self.sales_report(start, end, granularity="daily")

    def weekly_sales(self, start: datetime, end: datetime) -> SalesReport:
        return self.sales_report(start, end, granularity="weekly")

    def monthly_sales(self, start: datetime, end: datetime) -> SalesReport:
        return self.sales_report(start, end, granularity="monthly")

    # -------------------------
    # Top products
    # -------------------------

    def top_products(
        self,
        start: datetime,
        end: datetime,
        limit: int = 10,
        sort_by: str = "revenue",  # revenue|quantity
    ) -> list[ProductPerformance]:
        orders = self.fetch_orders(start, end)

        stats: dict[int, dict[str, Any]] = {}
        for o in orders:
            for li in o.get("line_items", []) or []:
                product_id = _as_int(li.get("product_id")) or 0
                if not product_id:
                    continue
                name = str(li.get("name") or "").strip() or f"product:{product_id}"
                qty = _as_int(li.get("quantity")) or 0
                revenue = _to_decimal(li.get("total"))

                rec = stats.setdefault(
                    product_id,
                    {
                        "product_id": product_id,
                        "name": name,
                        "quantity": 0,
                        "revenue": Decimal("0"),
                    },
                )
                # Keep the latest non-empty name.
                if name and name != rec.get("name"):
                    rec["name"] = name
                rec["quantity"] += qty
                rec["revenue"] += revenue

        results = [
            ProductPerformance(
                product_id=pid,
                name=str(v["name"]),
                quantity=int(v["quantity"]),
                revenue=Money(v["revenue"]),
            )
            for pid, v in stats.items()
        ]

        if sort_by == "quantity":
            results.sort(key=lambda p: (p.quantity, p.revenue), reverse=True)
        else:
            results.sort(key=lambda p: (p.revenue, p.quantity), reverse=True)

        return results[:limit]

    def top_products_by_revenue(
        self, start: datetime, end: datetime, limit: int = 10
    ) -> list[ProductPerformance]:
        return self.top_products(start, end, limit=limit, sort_by="revenue")

    def top_products_by_quantity(
        self, start: datetime, end: datetime, limit: int = 10
    ) -> list[ProductPerformance]:
        return self.top_products(start, end, limit=limit, sort_by="quantity")

    # -------------------------
    # Customer lifetime value
    # -------------------------

    def customer_lifetime_value(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[CustomerLifetimeValue]:
        # If no dates are provided, CLV is calculated for all time by iterating
        # only a bounded number of pages.
        if start is None:
            start = datetime(2000, 1, 1, tzinfo=UTC)
        if end is None:
            end = datetime.now(UTC) + timedelta(days=1)

        orders = self.fetch_orders(start, end)
        currency = _safe_currency(orders, default=self.default_currency)

        agg: dict[str, dict[str, Any]] = {}
        for o in orders:
            total = _to_decimal(o.get("total"))
            disc = _to_decimal(o.get("discount_total"))
            net = total - disc

            created = _parse_wc_datetime(
                o.get("date_created_gmt") or o.get("date_created")
            )

            customer_id = _as_int(o.get("customer_id"))
            billing = o.get("billing") or {}
            email = str(billing.get("email") or "").strip().lower()
            name = (
                f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip()
                or str(o.get("customer_note") or "").strip()
            )

            key = str(customer_id) if customer_id else email
            if not key:
                continue

            rec = agg.setdefault(
                key,
                {
                    "customer_key": key,
                    "name": name,
                    "email": email,
                    "orders": 0,
                    "lifetime_value": Decimal("0"),
                    "first_order": None,
                    "last_order": None,
                },
            )

            rec["orders"] += 1
            rec["lifetime_value"] += net
            if name and not rec.get("name"):
                rec["name"] = name
            if email and not rec.get("email"):
                rec["email"] = email

            if created is not None:
                fo = rec.get("first_order")
                lo = rec.get("last_order")
                if fo is None or created < fo:
                    rec["first_order"] = created
                if lo is None or created > lo:
                    rec["last_order"] = created

        customers = [
            CustomerLifetimeValue(
                customer_key=k,
                name=str(v.get("name") or k),
                email=str(v.get("email") or ""),
                orders=int(v.get("orders") or 0),
                lifetime_value=Money(v.get("lifetime_value") or Decimal("0")),
                first_order=v.get("first_order"),
                last_order=v.get("last_order"),
            )
            for k, v in agg.items()
        ]

        customers.sort(key=lambda c: (c.lifetime_value, c.orders), reverse=True)

        if not currency and self.default_currency:
            # CLV table still needs a currency, even if orders were missing it.
            currency = self.default_currency
        return customers[:limit]

    # -------------------------
    # Inventory alerts
    # -------------------------

    def inventory_alerts(
        self,
        low_stock_threshold: int = 5,
        include_unmanaged_stock: bool = False,
    ) -> list[InventoryAlert]:
        products = self.fetch_products()

        alerts: list[InventoryAlert] = []
        for p in products:
            product_id = _as_int(p.get("id")) or 0
            name = str(p.get("name") or "").strip() or f"product:{product_id}"
            stock_status = str(p.get("stock_status") or "").strip() or "unknown"
            manage_stock = bool(p.get("manage_stock"))
            stock_qty = _as_int(p.get("stock_quantity"))

            if stock_status == "outofstock":
                alerts.append(
                    InventoryAlert(
                        product_id=product_id,
                        name=name,
                        stock_status=stock_status,
                        stock_quantity=stock_qty,
                        threshold=low_stock_threshold,
                        severity="out_of_stock",
                    )
                )
                continue

            if not manage_stock and not include_unmanaged_stock:
                continue

            if stock_qty is not None and stock_qty <= low_stock_threshold:
                alerts.append(
                    InventoryAlert(
                        product_id=product_id,
                        name=name,
                        stock_status=stock_status,
                        stock_quantity=stock_qty,
                        threshold=low_stock_threshold,
                        severity="low_stock",
                    )
                )

        # Out-of-stock first, then lowest stock.
        alerts.sort(
            key=lambda a: (
                0 if a.severity == "out_of_stock" else 1,
                a.stock_quantity if a.stock_quantity is not None else 10**9,
            )
        )
        return alerts

    # -------------------------
    # Funnel analysis
    # -------------------------

    def order_funnel(
        self,
        start: datetime,
        end: datetime,
        sessions: Optional[int] = None,
        add_to_cart: Optional[int] = None,
        checkout_started: Optional[int] = None,
        currency: str = "",
    ) -> FunnelReport:
        all_statuses = [
            "pending",
            "processing",
            "on-hold",
            "completed",
            "cancelled",
            "failed",
            "refunded",
        ]

        # We fetch multiple statuses to build funnel and status breakdown.
        orders = self.fetch_orders(start, end, statuses=all_statuses)
        if not currency:
            currency = _safe_currency(orders, default=self.default_currency)

        counts: dict[str, int] = dict.fromkeys(all_statuses, 0)
        for o in orders:
            st = str(o.get("status") or "").strip().lower()
            if st in counts:
                counts[st] += 1

        orders_created = len(orders)
        orders_paid = counts.get("processing", 0) + counts.get("completed", 0)
        orders_completed = counts.get("completed", 0)

        payment_rate = (orders_paid / orders_created) if orders_created else 0.0
        completion_rate = (orders_completed / orders_created) if orders_created else 0.0

        order_conversion_rate = None
        if sessions and sessions > 0:
            order_conversion_rate = orders_completed / sessions

        return FunnelReport(
            start=start,
            end=end,
            currency=currency,
            orders_created=orders_created,
            orders_paid=orders_paid,
            orders_completed=orders_completed,
            orders_cancelled=counts.get("cancelled", 0),
            orders_failed=counts.get("failed", 0),
            orders_refunded=counts.get("refunded", 0),
            completion_rate=completion_rate,
            payment_rate=payment_rate,
            sessions=sessions,
            add_to_cart=add_to_cart,
            checkout_started=checkout_started,
            order_conversion_rate=order_conversion_rate,
        )

    def conversion_rate(
        self,
        start: datetime,
        end: datetime,
        sessions: int,
    ) -> ConversionRateReport:
        funnel = self.order_funnel(start, end, sessions=sessions)
        return ConversionRateReport(
            start=start,
            end=end,
            sessions=sessions,
            orders_completed=funnel.orders_completed,
            conversion_rate=funnel.order_conversion_rate or 0.0,
        )

    # -------------------------
    # Dashboard formatters
    # -------------------------

    def format_sales_dashboard(self, report: SalesReport) -> dict[str, Any]:
        currency = report.currency
        return {
            "type": "sales",
            "range": {
                "start": report.start.isoformat(),
                "end": report.end.isoformat(),
                "granularity": report.granularity,
            },
            "cards": [
                {
                    "label": "Gross revenue",
                    "value": _format_money(report.gross_revenue, currency),
                },
                {
                    "label": "Net revenue",
                    "value": _format_money(report.net_revenue, currency),
                },
                {"label": "Orders", "value": str(report.total_orders)},
                {
                    "label": "AOV",
                    "value": _format_money(report.average_order_value, currency),
                },
            ],
            "series": {
                "labels": [b["label"] for b in report.buckets],
                "gross_revenue": [
                    str(b["gross_revenue"].quantize(Decimal("0.01")))
                    for b in report.buckets
                ],
                "net_revenue": [
                    str(b["net_revenue"].quantize(Decimal("0.01")))
                    for b in report.buckets
                ],
                "orders": [int(b["orders"]) for b in report.buckets],
            },
            "breakdown": {
                "discounts": _format_money(report.discounts, currency),
                "shipping": _format_money(report.shipping, currency),
                "tax": _format_money(report.tax, currency),
            },
        }

    def format_top_products_dashboard(
        self, products: list[ProductPerformance], currency: str
    ) -> dict[str, Any]:
        return {
            "type": "top_products",
            "table": [
                {
                    "product_id": p.product_id,
                    "name": p.name,
                    "quantity": p.quantity,
                    "revenue": _format_money(p.revenue, currency),
                }
                for p in products
            ],
        }

    def format_customer_clv_dashboard(
        self, customers: list[CustomerLifetimeValue], currency: str
    ) -> dict[str, Any]:
        return {
            "type": "customer_lifetime_value",
            "table": [
                {
                    "customer": c.name or c.customer_key,
                    "email": c.email,
                    "orders": c.orders,
                    "lifetime_value": _format_money(c.lifetime_value, currency),
                    "first_order": c.first_order.isoformat() if c.first_order else None,
                    "last_order": c.last_order.isoformat() if c.last_order else None,
                }
                for c in customers
            ],
        }

    def format_inventory_dashboard(
        self, alerts: list[InventoryAlert]
    ) -> dict[str, Any]:
        return {
            "type": "inventory_alerts",
            "summary": {
                "out_of_stock": sum(1 for a in alerts if a.severity == "out_of_stock"),
                "low_stock": sum(1 for a in alerts if a.severity == "low_stock"),
            },
            "table": [asdict(a) for a in alerts],
        }

    def format_funnel_dashboard(self, funnel: FunnelReport) -> dict[str, Any]:
        return {
            "type": "order_funnel",
            "range": {"start": funnel.start.isoformat(), "end": funnel.end.isoformat()},
            "steps": [
                {"label": "Orders created", "value": funnel.orders_created},
                {
                    "label": "Orders paid",
                    "value": funnel.orders_paid,
                    "rate": funnel.payment_rate,
                },
                {
                    "label": "Orders completed",
                    "value": funnel.orders_completed,
                    "rate": funnel.completion_rate,
                },
            ],
            "status_breakdown": {
                "cancelled": funnel.orders_cancelled,
                "failed": funnel.orders_failed,
                "refunded": funnel.orders_refunded,
            },
            "conversion": {
                "sessions": funnel.sessions,
                "order_conversion_rate": funnel.order_conversion_rate,
                "add_to_cart": funnel.add_to_cart,
                "checkout_started": funnel.checkout_started,
            },
        }

    # -------------------------
    # RAG integration
    # -------------------------

    def build_rag_documents(
        self,
        start: datetime,
        end: datetime,
        top_n: int = 10,
    ) -> list[tuple[str, dict[str, Any], str]]:
        """Return (content, metadata, doc_id) tuples for ingestion into a DocumentStore."""

        sales = self.daily_sales(start, end)
        currency = sales.currency
        top_by_revenue = self.top_products_by_revenue(start, end, limit=top_n)
        clv = self.customer_lifetime_value(start=None, end=None, limit=top_n)

        period = f"{start.date().isoformat()} to {end.date().isoformat()}"

        lines = [
            f"WooCommerce commerce analytics snapshot for {period}.",
            f"Total gross revenue: {_format_money(sales.gross_revenue, currency)}.",
            f"Total net revenue (after discounts): {_format_money(sales.net_revenue, currency)}.",
            f"Total orders: {sales.total_orders}.",
            "",
            "Top selling products (by revenue):",
        ]
        for i, p in enumerate(top_by_revenue, 1):
            lines.append(
                f"{i}. {p.name} (product {p.product_id}) — revenue {_format_money(p.revenue, currency)}, quantity {p.quantity}."
            )

        lines.extend(["", "Customers with highest lifetime value:"])
        for i, c in enumerate(clv, 1):
            lines.append(
                f"{i}. {c.name or c.customer_key} ({c.email}) — lifetime value {_format_money(c.lifetime_value, currency)}, orders {c.orders}."
            )

        content = "\n".join(lines)
        metadata = {
            "source": "commerce_analytics",
            "platform": "woocommerce",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "currency": currency,
            "type": "snapshot",
        }
        doc_id = f"woocommerce_analytics_snapshot_{start.date().isoformat()}_{end.date().isoformat()}"

        # Also add a compact CLV-only doc so queries can be more direct.
        clv_lines = [
            "WooCommerce customer lifetime value leaderboard.",
            "Customers with highest lifetime value:",
        ]
        for i, c in enumerate(clv, 1):
            clv_lines.append(
                f"{i}. {c.name or c.customer_key} ({c.email}) — lifetime value {_format_money(c.lifetime_value, currency)}, orders {c.orders}."
            )

        clv_doc = "\n".join(clv_lines)
        clv_meta = {
            "source": "commerce_analytics",
            "platform": "woocommerce",
            "currency": currency,
            "type": "customer_lifetime_value",
        }
        clv_id = "woocommerce_customer_lifetime_value"

        # And a top-products doc.
        tp_lines = [
            f"WooCommerce top selling products for {period}.",
            "Top selling products (by revenue):",
        ]
        for i, p in enumerate(top_by_revenue, 1):
            tp_lines.append(
                f"{i}. {p.name} (product {p.product_id}) — revenue {_format_money(p.revenue, currency)}, quantity {p.quantity}."
            )
        tp_doc = "\n".join(tp_lines)
        tp_meta = {
            "source": "commerce_analytics",
            "platform": "woocommerce",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "currency": currency,
            "type": "top_products",
        }
        tp_id = f"woocommerce_top_products_{start.date().isoformat()}_{end.date().isoformat()}"

        return [
            (content, metadata, doc_id),
            (clv_doc, clv_meta, clv_id),
            (tp_doc, tp_meta, tp_id),
        ]

    def ingest_into_document_store(
        self,
        document_store: Any,
        start: datetime,
        end: datetime,
        top_n: int = 10,
    ) -> list[str]:
        """Ingest analytics docs into a DocumentStore.

        This enables natural language queries against analytics using the RAG pipeline.
        """

        doc_ids: list[str] = []
        for content, metadata, doc_id in self.build_rag_documents(
            start, end, top_n=top_n
        ):
            document_store.add(content=content, metadata=metadata, doc_id=doc_id)
            doc_ids.append(doc_id)
        return doc_ids

    def ingest_into_rag_pipeline(
        self,
        rag_pipeline: Any,
        start: datetime,
        end: datetime,
        top_n: int = 10,
    ) -> list[str]:
        """Ingest into a RAGPipeline configured with a DocumentStore."""

        doc_ids: list[str] = []
        for content, metadata, doc_id in self.build_rag_documents(
            start, end, top_n=top_n
        ):
            rag_pipeline.add_document(content=content, metadata=metadata, doc_id=doc_id)
            doc_ids.append(doc_id)
        return doc_ids

    # Convenience helper for the common NL query: "last month".
    def ingest_last_month_snapshot(
        self,
        document_store: Any,
        now: Optional[datetime] = None,
        top_n: int = 10,
    ) -> list[str]:
        start, end = _date_range_last_month(now=now)
        return self.ingest_into_document_store(document_store, start, end, top_n=top_n)

    # JSON export (useful for API endpoints)
    def to_json(self, obj: Any) -> str:
        return json.dumps(obj, default=str, indent=2)
