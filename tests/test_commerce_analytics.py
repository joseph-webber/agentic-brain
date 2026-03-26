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

from __future__ import annotations

from datetime import UTC, datetime, timezone
from decimal import Decimal

import pytest

from agentic_brain.commerce.analytics import WooCommerceAnalytics
from agentic_brain.rag.store import InMemoryDocumentStore


class StubWooAPI:
    def __init__(self, orders_by_status: dict[str, list[dict]], products: list[dict]):
        self._orders_by_status = orders_by_status
        self._products = products

    def get(self, path: str, params=None):
        params = params or {}
        if path == "orders":
            status = params.get("status")
            page = int(params.get("page", 1))
            per_page = int(params.get("per_page", 100))
            batch = list(self._orders_by_status.get(status, []))
            start = (page - 1) * per_page
            end = start + per_page
            return batch[start:end]
        if path == "products":
            page = int(params.get("page", 1))
            per_page = int(params.get("per_page", 100))
            start = (page - 1) * per_page
            end = start + per_page
            return list(self._products)[start:end]
        raise AssertionError(f"Unexpected path: {path}")


@pytest.fixture()
def sample_analytics():
    # Orders are segmented by status because the analytics fetcher requests per-status.
    completed = [
        {
            "id": 1,
            "status": "completed",
            "currency": "USD",
            "date_created_gmt": "2026-02-01T10:00:00",
            "total": "100.00",
            "discount_total": "10.00",
            "shipping_total": "5.00",
            "total_tax": "8.00",
            "customer_id": 10,
            "billing": {
                "email": "a@example.com",
                "first_name": "Alice",
                "last_name": "A",
            },
            "line_items": [
                {"product_id": 111, "name": "Widget", "quantity": 2, "total": "80.00"},
                {"product_id": 222, "name": "Gadget", "quantity": 1, "total": "20.00"},
            ],
        },
        {
            "id": 2,
            "status": "completed",
            "currency": "USD",
            "date_created_gmt": "2026-02-02T10:00:00",
            "total": "50.00",
            "discount_total": "0.00",
            "shipping_total": "0.00",
            "total_tax": "0.00",
            "customer_id": 10,
            "billing": {
                "email": "a@example.com",
                "first_name": "Alice",
                "last_name": "A",
            },
            "line_items": [
                {"product_id": 111, "name": "Widget", "quantity": 1, "total": "50.00"},
            ],
        },
    ]

    processing = [
        {
            "id": 3,
            "status": "processing",
            "currency": "USD",
            "date_created_gmt": "2026-02-02T12:00:00",
            "total": "25.00",
            "discount_total": "5.00",
            "shipping_total": "0.00",
            "total_tax": "0.00",
            "customer_id": 20,
            "billing": {
                "email": "b@example.com",
                "first_name": "Bob",
                "last_name": "B",
            },
            "line_items": [
                {"product_id": 222, "name": "Gadget", "quantity": 1, "total": "25.00"},
            ],
        }
    ]

    cancelled = [
        {
            "id": 4,
            "status": "cancelled",
            "currency": "USD",
            "date_created_gmt": "2026-02-02T14:00:00",
            "total": "99.00",
            "discount_total": "0.00",
            "shipping_total": "0.00",
            "total_tax": "0.00",
            "customer_id": 30,
            "billing": {
                "email": "c@example.com",
                "first_name": "Cara",
                "last_name": "C",
            },
            "line_items": [
                {"product_id": 111, "name": "Widget", "quantity": 1, "total": "99.00"},
            ],
        }
    ]

    products = [
        {
            "id": 111,
            "name": "Widget",
            "stock_status": "instock",
            "manage_stock": True,
            "stock_quantity": 3,
        },
        {
            "id": 222,
            "name": "Gadget",
            "stock_status": "outofstock",
            "manage_stock": True,
            "stock_quantity": 0,
        },
        {
            "id": 333,
            "name": "Thing",
            "stock_status": "instock",
            "manage_stock": False,
            "stock_quantity": None,
        },
    ]

    api = StubWooAPI(
        orders_by_status={
            "completed": completed,
            "processing": processing,
            "pending": [],
            "on-hold": [],
            "cancelled": cancelled,
            "failed": [],
            "refunded": [],
        },
        products=products,
    )

    analytics = WooCommerceAnalytics(api=api, default_currency="USD")
    return analytics


def test_sales_report_daily(sample_analytics: WooCommerceAnalytics):
    start = datetime(2026, 2, 1, tzinfo=UTC)
    end = datetime(2026, 2, 3, tzinfo=UTC)

    report = sample_analytics.daily_sales(start, end)
    assert report.total_orders == 3  # completed + processing
    assert report.currency == "USD"

    assert report.gross_revenue == Decimal("175.00")
    assert report.discounts == Decimal("15.00")
    assert report.net_revenue == Decimal("160.00")
    assert report.average_order_value.quantize(Decimal("0.01")) == Decimal("58.33")

    dashboard = sample_analytics.format_sales_dashboard(report)
    assert dashboard["type"] == "sales"
    assert dashboard["series"]["labels"] == ["2026-02-01", "2026-02-02"]
    assert dashboard["series"]["gross_revenue"] == ["100.00", "75.00"]
    assert dashboard["series"]["net_revenue"] == ["90.00", "70.00"]


def test_top_products_by_revenue(sample_analytics: WooCommerceAnalytics):
    start = datetime(2026, 2, 1, tzinfo=UTC)
    end = datetime(2026, 2, 3, tzinfo=UTC)

    top = sample_analytics.top_products_by_revenue(start, end, limit=5)
    assert top[0].name == "Widget"
    assert top[0].quantity == 3

    dash = sample_analytics.format_top_products_dashboard(top, currency="USD")
    assert dash["type"] == "top_products"
    assert dash["table"][0]["name"] == "Widget"


def test_customer_lifetime_value(sample_analytics: WooCommerceAnalytics):
    clv = sample_analytics.customer_lifetime_value(limit=10)
    assert clv[0].email == "a@example.com"
    assert clv[0].orders == 2

    dash = sample_analytics.format_customer_clv_dashboard(clv, currency="USD")
    assert dash["type"] == "customer_lifetime_value"
    assert dash["table"][0]["email"] == "a@example.com"


def test_inventory_alerts(sample_analytics: WooCommerceAnalytics):
    alerts = sample_analytics.inventory_alerts(low_stock_threshold=5)
    assert any(a.severity == "out_of_stock" for a in alerts)
    assert any(a.severity == "low_stock" for a in alerts)

    dash = sample_analytics.format_inventory_dashboard(alerts)
    assert dash["type"] == "inventory_alerts"
    assert dash["summary"]["out_of_stock"] == 1


def test_funnel_and_conversion(sample_analytics: WooCommerceAnalytics):
    start = datetime(2026, 2, 1, tzinfo=UTC)
    end = datetime(2026, 2, 3, tzinfo=UTC)

    funnel = sample_analytics.order_funnel(start, end, sessions=200)
    assert funnel.orders_created >= funnel.orders_completed
    assert funnel.order_conversion_rate is not None

    dash = sample_analytics.format_funnel_dashboard(funnel)
    assert dash["type"] == "order_funnel"


def test_rag_ingestion_documents(sample_analytics: WooCommerceAnalytics):
    start = datetime(2026, 2, 1, tzinfo=UTC)
    end = datetime(2026, 2, 3, tzinfo=UTC)

    store = InMemoryDocumentStore()
    doc_ids = sample_analytics.ingest_into_document_store(store, start, end, top_n=5)
    assert doc_ids

    # Keyword search should hit the generated insight docs.
    docs = store.search("top selling products last month", top_k=5)
    assert docs
    assert "Top selling products" in docs[0].content

    docs2 = store.search("highest lifetime value", top_k=5)
    assert docs2
    assert "lifetime value" in docs2[0].content.lower()
