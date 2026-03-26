# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import asyncio
from unittest.mock import AsyncMock

import pytest

from agentic_brain.commerce.woo_api import WooCommerceAPI
from agentic_brain.commerce.woo_api.coupons import CouponsAPI
from agentic_brain.commerce.woo_api.customers import CustomersAPI
from agentic_brain.commerce.woo_api.data import DataAPI
from agentic_brain.commerce.woo_api.orders import OrdersAPI
from agentic_brain.commerce.woo_api.payment_gateways import PaymentGatewaysAPI
from agentic_brain.commerce.woo_api.products import ProductsAPI
from agentic_brain.commerce.woo_api.reports import ReportsAPI
from agentic_brain.commerce.woo_api.settings import SettingsAPI
from agentic_brain.commerce.woo_api.shipping import ShippingAPI
from agentic_brain.commerce.woo_api.system import SystemAPI
from agentic_brain.commerce.woo_api.taxes import TaxesAPI
from agentic_brain.commerce.woo_api.webhooks import WebhooksAPI


class DummyClient:
    def __init__(self) -> None:
        self.request = AsyncMock()
        self.paginate = AsyncMock(return_value=[{"ok": True}])
        self.batch = AsyncMock(return_value={"done": True})

    def run_sync(self, awaitable):
        return asyncio.run(awaitable)


@pytest.fixture()
def dummy_client() -> DummyClient:
    return DummyClient()


@pytest.mark.asyncio
async def test_products_list_uses_paginate(dummy_client: DummyClient) -> None:
    api = ProductsAPI(dummy_client)  # type: ignore[arg-type]
    await api.list(status="publish")
    dummy_client.paginate.assert_called_once()


@pytest.mark.asyncio
async def test_products_batch_calls_batch(dummy_client: DummyClient) -> None:
    api = ProductsAPI(dummy_client)  # type: ignore[arg-type]
    await api.batch(create=[{"name": "A"}])
    dummy_client.batch.assert_called_once()


def test_products_sync_proxy(dummy_client: DummyClient) -> None:
    api = ProductsAPI(dummy_client)  # type: ignore[arg-type]
    result = api.sync.list(status="draft")
    assert result == [{"ok": True}]


@pytest.mark.asyncio
async def test_orders_create_note(dummy_client: DummyClient) -> None:
    api = OrdersAPI(dummy_client)  # type: ignore[arg-type]
    await api.create_note(42, {"note": "Hey"})
    dummy_client.request.assert_called_with(
        "POST", "orders/42/notes", json_body={"note": "Hey"}
    )


@pytest.mark.asyncio
async def test_customers_downloads(dummy_client: DummyClient) -> None:
    api = CustomersAPI(dummy_client)  # type: ignore[arg-type]
    await api.list_downloads(15)
    dummy_client.paginate.assert_called()


@pytest.mark.asyncio
async def test_coupons_batch(dummy_client: DummyClient) -> None:
    api = CouponsAPI(dummy_client)  # type: ignore[arg-type]
    await api.batch(create=[{"code": "SAVE"}])
    dummy_client.batch.assert_called()


@pytest.mark.asyncio
async def test_reports_sales(dummy_client: DummyClient) -> None:
    api = ReportsAPI(dummy_client)  # type: ignore[arg-type]
    await api.sales(date_min="2026-01-01")
    dummy_client.request.assert_called_with(
        "GET", "reports/sales", params={"date_min": "2026-01-01"}
    )


@pytest.mark.asyncio
async def test_shipping_zone_methods(dummy_client: DummyClient) -> None:
    api = ShippingAPI(dummy_client)  # type: ignore[arg-type]
    await api.create_zone_method(1, {"method_id": "flat_rate"})
    dummy_client.request.assert_called_with(
        "POST", "shipping/zones/1/methods", json_body={"method_id": "flat_rate"}
    )


@pytest.mark.asyncio
async def test_taxes_create_class(dummy_client: DummyClient) -> None:
    api = TaxesAPI(dummy_client)  # type: ignore[arg-type]
    await api.create_class({"name": "Luxury"})
    dummy_client.request.assert_called_with(
        "POST", "taxes/classes", json_body={"name": "Luxury"}
    )


@pytest.mark.asyncio
async def test_settings_batch(dummy_client: DummyClient) -> None:
    api = SettingsAPI(dummy_client)  # type: ignore[arg-type]
    await api.batch_update("general", update=[{"id": "currency", "value": "AUD"}])
    dummy_client.batch.assert_called_with(
        "settings/general/batch",
        {"update": [{"id": "currency", "value": "AUD"}]},
    )


@pytest.mark.asyncio
async def test_payment_gateways_update(dummy_client: DummyClient) -> None:
    api = PaymentGatewaysAPI(dummy_client)  # type: ignore[arg-type]
    await api.update("stripe", {"enabled": True})
    dummy_client.request.assert_called_with(
        "PUT", "payment_gateways/stripe", json_body={"enabled": True}
    )


@pytest.mark.asyncio
async def test_webhooks_redeliver(dummy_client: DummyClient) -> None:
    api = WebhooksAPI(dummy_client)  # type: ignore[arg-type]
    await api.redeliver(22, 7)
    dummy_client.request.assert_called_with("POST", "webhooks/22/deliveries/7/resend")


@pytest.mark.asyncio
async def test_system_run_tool(dummy_client: DummyClient) -> None:
    api = SystemAPI(dummy_client)  # type: ignore[arg-type]
    await api.run_tool("clear_transients", {})
    dummy_client.request.assert_called_with(
        "POST", "system_status/tools/clear_transients", json_body={}
    )


@pytest.mark.asyncio
async def test_data_country(dummy_client: DummyClient) -> None:
    api = DataAPI(dummy_client)  # type: ignore[arg-type]
    await api.country("AU")
    dummy_client.request.assert_called_with("GET", "data/countries/AU")


def test_facade_exposes_resources() -> None:
    woo = WooCommerceAPI("https://example.com", "ck", "cs")
    assert hasattr(woo, "products")
    assert hasattr(woo, "orders")
    woo.close_sync()
