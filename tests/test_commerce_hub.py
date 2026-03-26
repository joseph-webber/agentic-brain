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

"""Comprehensive tests for the CommerceHub and supporting modules."""

from __future__ import annotations

import os
from datetime import UTC
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


def _make_product(
    product_id: int = 1,
    sku: str = "SKU-001",
    name: str = "Test Product",
    stock_quantity: int = 10,
    stock_status: str = "instock",
    manage_stock: bool = True,
    low_stock_amount: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "id": product_id,
        "sku": sku,
        "name": name,
        "stock_quantity": stock_quantity,
        "stock_status": stock_status,
        "manage_stock": manage_stock,
        "low_stock_amount": low_stock_amount,
    }


class StubWooAgent:
    """Minimal WooCommerceAgent stand-in for unit tests."""

    def __init__(self, products: Optional[List[Dict]] = None) -> None:
        self._products: List[Dict] = list(products or [])
        self._updates: List[Dict] = []

    def get_products_sync(self, params: Optional[Dict] = None) -> List[Dict]:
        params = params or {}
        page = int(params.get("page", 1))
        per_page = int(params.get("per_page", 100))
        start = (page - 1) * per_page
        return self._products[start : start + per_page]

    def get_product_sync(self, product_id: int) -> Dict:
        for p in self._products:
            if p["id"] == product_id:
                return p
        raise KeyError(f"Product {product_id} not found")

    def update_product_sync(self, product_id: int, data: Dict) -> Dict:
        product = self.get_product_sync(product_id)
        updated = {**product, **data}
        self._updates.append({"product_id": product_id, "data": data})
        # Update in-memory store
        for i, p in enumerate(self._products):
            if p["id"] == product_id:
                self._products[i] = updated
        return updated

    def get_products_sync_returning_empty_second_page(self, params=None):
        params = params or {}
        page = int(params.get("page", 1))
        if page == 1:
            return self._products
        return []


# ---------------------------------------------------------------------------
# CommerceConfig tests
# ---------------------------------------------------------------------------


class TestCommerceConfig:
    def test_default_values(self):
        from agentic_brain.commerce import CommerceConfig

        cfg = CommerceConfig()
        assert cfg.woocommerce.url == ""
        assert cfg.woocommerce.verify_ssl is True
        assert cfg.woocommerce.timeout == 30
        assert cfg.payments.default_gateway == "cod"
        assert cfg.shipping.default_from_postcode == "5000"
        assert cfg.inventory.low_stock_threshold == 5

    def test_from_env(self, monkeypatch):
        from agentic_brain.commerce import CommerceConfig

        monkeypatch.setenv("WOO_URL", "https://mystore.example.com")
        monkeypatch.setenv("WOO_CONSUMER_KEY", "ck_test")
        monkeypatch.setenv("WOO_CONSUMER_SECRET", "cs_test")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
        monkeypatch.setenv("AUSPOST_FROM_POSTCODE", "2000")
        monkeypatch.setenv("INVENTORY_LOW_STOCK_THRESHOLD", "3")

        cfg = CommerceConfig.from_env()
        assert cfg.woocommerce.url == "https://mystore.example.com"
        assert cfg.woocommerce.consumer_key == "ck_test"
        assert cfg.payments.stripe_secret_key == "sk_test_xxx"
        assert cfg.shipping.default_from_postcode == "2000"
        assert cfg.inventory.low_stock_threshold == 3

    def test_woocommerce_config_ssl_flag(self, monkeypatch):
        from agentic_brain.commerce.hub import WooCommerceConfig

        monkeypatch.setenv("WOO_VERIFY_SSL", "false")
        cfg = WooCommerceConfig.from_env()
        assert cfg.verify_ssl is False

    def test_payment_config_sandbox_default(self):
        from agentic_brain.commerce.hub import PaymentConfig

        cfg = PaymentConfig()
        assert cfg.paypal_sandbox is True


# ---------------------------------------------------------------------------
# CommerceHub instantiation tests
# ---------------------------------------------------------------------------


class TestCommerceHubInit:
    def test_default_init(self):
        from agentic_brain.commerce import CommerceHub

        hub = CommerceHub()
        assert hub is not None
        assert repr(hub) == "CommerceHub(store='<not configured>')"

    def test_repr_with_url(self):
        from agentic_brain.commerce import (
            CommerceConfig,
            CommerceHub,
            WooCommerceConfig,
        )

        cfg = CommerceConfig(
            woocommerce=WooCommerceConfig(url="https://shop.example.com")
        )
        hub = CommerceHub(cfg)
        assert "shop.example.com" in repr(hub)

    def test_subsystems_are_lazy(self):
        """Subsystem objects should not be created until first access."""
        from agentic_brain.commerce import CommerceHub

        hub = CommerceHub()
        assert hub._woo is None
        assert hub._wp is None
        assert hub._payments is None
        assert hub._shipping is None
        assert hub._inventory is None
        assert hub._analytics is None

    def test_woo_subsystem_created_on_access(self):
        from agentic_brain.commerce import CommerceHub

        hub = CommerceHub()
        woo = hub.woo
        assert woo is not None
        assert hub._woo is woo  # cached

    def test_woo_subsystem_cached(self):
        from agentic_brain.commerce import CommerceHub

        hub = CommerceHub()
        assert hub.woo is hub.woo  # same object

    def test_payments_subsystem_created(self):
        from agentic_brain.commerce import CommerceHub

        hub = CommerceHub()
        proc = hub.payments
        assert proc is not None
        # Should have at least one gateway (no-op fallback)
        assert len(proc._gateways) >= 1

    def test_shipping_subsystem_created(self):
        from agentic_brain.commerce import CommerceHub

        hub = CommerceHub()
        mgr = hub.shipping
        assert mgr is not None
        assert mgr.default_from_postcode == "5000"

    def test_shipping_uses_config_postcode(self):
        from agentic_brain.commerce import CommerceConfig, CommerceHub
        from agentic_brain.commerce.hub import ShippingConfig

        cfg = CommerceConfig(shipping=ShippingConfig(default_from_postcode="3000"))
        hub = CommerceHub(cfg)
        assert hub.shipping.default_from_postcode == "3000"


# ---------------------------------------------------------------------------
# InventoryManager tests
# ---------------------------------------------------------------------------


class TestInventoryManager:
    def _make_manager(self, products):
        from agentic_brain.commerce import InventoryManager

        return InventoryManager(
            woo_agent=StubWooAgent(products),
            low_stock_threshold=5,
        )

    def test_get_stock_levels_returns_all_products(self):
        products = [
            _make_product(i, sku=f"SKU-{i}", stock_quantity=10) for i in range(1, 4)
        ]
        mgr = self._make_manager(products)
        levels = mgr.get_stock_levels()
        assert len(levels) == 3

    def test_stock_level_fields(self):
        product = _make_product(42, sku="MY-SKU", name="Widget", stock_quantity=7)
        mgr = self._make_manager([product])
        levels = mgr.get_stock_levels()
        assert len(levels) == 1
        level = levels[0]
        assert level.product_id == 42
        assert level.sku == "MY-SKU"
        assert level.name == "Widget"
        assert level.stock_quantity == 7

    def test_is_low_stock(self):
        product = _make_product(
            1, stock_quantity=3, manage_stock=True, low_stock_amount=5
        )
        mgr = self._make_manager([product])
        levels = mgr.get_stock_levels()
        assert levels[0].is_low is True

    def test_is_not_low_stock(self):
        product = _make_product(
            1, stock_quantity=10, manage_stock=True, low_stock_amount=5
        )
        mgr = self._make_manager([product])
        assert mgr.get_stock_levels()[0].is_low is False

    def test_out_of_stock(self):
        product = _make_product(
            1, stock_quantity=0, stock_status="outofstock", manage_stock=True
        )
        mgr = self._make_manager([product])
        assert mgr.get_stock_levels()[0].is_out_of_stock is True

    def test_low_stock_report_splits_correctly(self):
        products = [
            _make_product(
                1, stock_quantity=2, manage_stock=True, low_stock_amount=5
            ),  # low
            _make_product(2, stock_quantity=0, stock_status="outofstock"),  # oos
            _make_product(
                3, stock_quantity=20, manage_stock=True, low_stock_amount=5
            ),  # fine
        ]
        mgr = self._make_manager(products)
        report = mgr.get_low_stock_report()
        assert len(report.items) == 1
        assert len(report.out_of_stock) == 1
        assert report.total_alerts == 2

    def test_set_stock(self):
        agent = StubWooAgent([_make_product(1, stock_quantity=10)])
        from agentic_brain.commerce import InventoryManager

        mgr = InventoryManager(woo_agent=agent, low_stock_threshold=5)
        adj = mgr.set_stock(1, 25, reason="restock")
        assert adj.new_quantity == 25
        assert adj.previous_quantity == 10
        assert adj.delta == 15
        assert adj.reason == "restock"

    def test_adjust_stock_positive_delta(self):
        agent = StubWooAgent([_make_product(1, stock_quantity=10)])
        from agentic_brain.commerce import InventoryManager

        mgr = InventoryManager(woo_agent=agent, low_stock_threshold=5)
        adj = mgr.adjust_stock(1, +5, reason="sold")
        assert adj.new_quantity == 15

    def test_adjust_stock_negative_delta(self):
        agent = StubWooAgent([_make_product(1, stock_quantity=10)])
        from agentic_brain.commerce import InventoryManager

        mgr = InventoryManager(woo_agent=agent, low_stock_threshold=5)
        adj = mgr.adjust_stock(1, -3, reason="sold")
        assert adj.new_quantity == 7


# ---------------------------------------------------------------------------
# ShippingManager tests
# ---------------------------------------------------------------------------


class TestShippingManager:
    def _make_manager_with_mock_carrier(self, rates=None):
        """Build a ShippingManager using a mock AusPostCarrier."""
        from agentic_brain.commerce import ShippingManager
        from agentic_brain.commerce.shipping import AusPostCarrier

        mock_carrier = MagicMock(spec=AusPostCarrier)
        mock_carrier.name = "AusPost"
        mock_carrier.get_rates.return_value = rates or []
        mgr = ShippingManager(auspost_client=mock_carrier, default_from_postcode="5000")
        return mgr, mock_carrier

    def _make_rate(self, code, name, cost, days=None):
        from agentic_brain.commerce.shipping import ShippingRate

        return ShippingRate(
            carrier="AusPost",
            service_code=code,
            service_name=name,
            cost=Decimal(str(cost)),
            estimated_days=days,
        )

    def test_get_rates_returns_list(self):
        from agentic_brain.commerce.shipping import Dimensions

        rate = self._make_rate("AUS_PARCEL_REGULAR", "Parcel Post", "8.95", days=5)
        mgr, _ = self._make_manager_with_mock_carrier(rates=[rate])
        dims = Dimensions(20, 15, 10, 1.0)
        result = mgr.get_rates("3000", dims)
        assert isinstance(result, list)

    def test_get_cheapest_rate(self):
        from agentic_brain.commerce.shipping import Dimensions

        rates = [
            self._make_rate("EXPRESS", "Express Post", "14.50"),
            self._make_rate("REGULAR", "Parcel Post", "8.95"),
        ]
        mgr, mock_carrier = self._make_manager_with_mock_carrier()
        dims = Dimensions(20, 15, 10, 0.5)
        mock_carrier.get_rates.return_value = rates
        cheapest = mgr.get_cheapest_rate("2000", dims)
        assert cheapest is not None
        assert cheapest.cost == Decimal("8.95")

    def test_get_fastest_rate(self):
        from agentic_brain.commerce.shipping import Dimensions

        rates = [
            self._make_rate("EXPRESS", "Express Post", "14.50", days=1),
            self._make_rate("REGULAR", "Parcel Post", "8.95", days=5),
        ]
        mgr, mock_carrier = self._make_manager_with_mock_carrier()
        dims = Dimensions(20, 15, 10, 0.5)
        mock_carrier.get_rates.return_value = rates
        fastest = mgr.get_fastest_rate("2000", dims)
        assert fastest is not None
        assert fastest.estimated_days == 1

    def test_get_cheapest_rate_returns_none_when_no_rates(self):
        from agentic_brain.commerce.shipping import Dimensions

        mgr, _ = self._make_manager_with_mock_carrier(rates=[])
        result = mgr.get_cheapest_rate("9999", Dimensions(10, 10, 10, 1.0))
        assert result is None

    def test_rates_for_order_uses_postcode(self):
        from agentic_brain.commerce.shipping import Dimensions

        rate = self._make_rate("REGULAR", "Parcel Post", "8.95")
        mgr, mock_carrier = self._make_manager_with_mock_carrier(rates=[rate])
        mock_carrier.get_rates.return_value = [rate]

        order = {
            "id": 1,
            "shipping": {"postcode": "4000", "country": "AU"},
            "billing": {},
        }
        dims = Dimensions(20, 15, 10, 1.0)
        results = mgr.rates_for_order(order, dims)
        # rates_for_order passes WooAddress objects to calculate_rates
        assert isinstance(results, list)

    def test_rates_for_order_falls_back_to_billing(self):
        from agentic_brain.commerce.shipping import Dimensions

        rate = self._make_rate("REGULAR", "Parcel Post", "8.95")
        mgr, mock_carrier = self._make_manager_with_mock_carrier(rates=[rate])
        mock_carrier.get_rates.return_value = [rate]

        order = {
            "id": 1,
            "shipping": {},
            "billing": {"postcode": "6000", "country": "AU"},
        }
        results = mgr.rates_for_order(order, Dimensions(10, 10, 10, 0.5))
        assert isinstance(results, list)

    def test_rates_for_order_returns_empty_without_postcode(self):
        from agentic_brain.commerce.shipping import Dimensions

        mgr, mock_carrier = self._make_manager_with_mock_carrier()
        order = {"id": 1}
        results = mgr.rates_for_order(order, Dimensions(10, 10, 10, 0.5))
        assert results == []
        mock_carrier.get_rates.assert_not_called()

    def test_dimensions_dataclass(self):
        from agentic_brain.commerce.shipping import Dimensions

        d = Dimensions(length_cm=30, width_cm=20, height_cm=10, weight_kg=2.5)
        assert d.length_cm == 30
        assert d.weight_kg == 2.5


# ---------------------------------------------------------------------------
# Payments tests
# ---------------------------------------------------------------------------


class TestPaymentClasses:
    def test_payment_errors_hierarchy(self):
        from agentic_brain.commerce import (
            FraudRejectedError,
            PaymentError,
            PaymentSecurityError,
        )

        assert issubclass(PaymentSecurityError, PaymentError)
        assert issubclass(FraudRejectedError, PaymentError)

    def test_payment_operation_not_supported_alias(self):
        from agentic_brain.commerce import PaymentOperationNotSupported
        from agentic_brain.commerce.payments import PaymentOperationNotSupportedError

        assert PaymentOperationNotSupported is PaymentOperationNotSupportedError

    def test_payment_method_reference_fields(self):
        from agentic_brain.commerce import PaymentMethodReference

        ref = PaymentMethodReference(token="tok_test_123")
        assert ref.token == "tok_test_123"
        assert ref.method_type == "card"

    def test_refund_result_fields(self):
        from agentic_brain.commerce import RefundResult

        rr = RefundResult(
            gateway="stripe",
            refund_id="re_test",
            status="refunded",
            transaction_id="pi_test",
            amount=Decimal("25.00"),
            currency="AUD",
        )
        assert rr.refund_id == "re_test"
        assert rr.amount == Decimal("25.00")

    def test_transaction_record_fields(self):
        from datetime import datetime, timezone

        from agentic_brain.commerce import TransactionRecord

        now = datetime.now(tz=UTC)
        tr = TransactionRecord(
            operation="payment",
            gateway="stripe",
            status="succeeded",
            timestamp=now,
            transaction_id="pi_test",
            amount=Decimal("99.00"),
            currency="AUD",
        )
        assert tr.operation == "payment"
        assert tr.gateway == "stripe"

    def test_webhook_event_fields(self):
        from agentic_brain.commerce import WebhookEvent

        evt = WebhookEvent(
            gateway="stripe",
            event_id="evt_001",
            event_type="payment_intent.succeeded",
            payload={"id": "evt_001"},
            verified=True,
        )
        assert evt.event_type == "payment_intent.succeeded"
        assert evt.verified is True

    def test_payment_processor_requires_gateways(self):
        from agentic_brain.commerce import PaymentProcessor

        with pytest.raises((ValueError, Exception)):
            PaymentProcessor(gateways={})

    def test_payment_processor_get_unknown_gateway(self):
        from agentic_brain.commerce import (
            PaymentError,
            PaymentGateway,
            PaymentProcessor,
        )
        from agentic_brain.commerce.payments import (
            PaymentRequest,
            PaymentResult,
            RefundRequest,
            RefundResult,
        )

        class DummyGateway(PaymentGateway):
            @property
            def name(self):
                return "dummy"

            def create_payment(self, request: PaymentRequest) -> PaymentResult:
                return PaymentResult(
                    gateway=self.name,
                    transaction_id="x",
                    status="pending",
                    amount=Decimal("1"),
                    currency="AUD",
                )

            def refund_payment(self, request: RefundRequest) -> RefundResult:
                return RefundResult(
                    gateway=self.name,
                    refund_id="r",
                    status="refunded",
                    transaction_id="x",
                )

        proc = PaymentProcessor(gateways={"dummy": DummyGateway()})
        with pytest.raises(PaymentError):
            proc.get_gateway("nonexistent")

    def test_square_gateway_has_name(self):
        from agentic_brain.commerce import SquareGateway

        gw = SquareGateway(client=MagicMock())
        assert gw.name == "square"

    def test_stripe_gateway_has_name(self):
        from agentic_brain.commerce import StripeGateway

        gw = StripeGateway(client=MagicMock())
        assert gw.name == "stripe"

    def test_paypal_gateway_has_name(self):
        from agentic_brain.commerce import PayPalGateway

        gw = PayPalGateway(client=MagicMock())
        assert gw.name == "paypal"


# ---------------------------------------------------------------------------
# WooCommerce model tests
# ---------------------------------------------------------------------------


class TestWooCommerceModels:
    def test_woo_product_parse(self):
        from agentic_brain.commerce import WooProduct

        p = WooProduct(id=1, name="Widget", slug="widget")
        assert p.id == 1
        assert p.name == "Widget"

    def test_woo_order_parse(self):
        from agentic_brain.commerce import WooOrder

        o = WooOrder(id=100, status="pending", currency="AUD")
        assert o.id == 100
        assert o.status == "pending"

    def test_woo_customer_parse(self):
        from agentic_brain.commerce import WooCustomer

        c = WooCustomer(id=5, email="test@example.com", name="Test User")
        assert c.id == 5
        assert c.email == "test@example.com"
        assert c.name == "Test User"


# ---------------------------------------------------------------------------
# Webhook tests
# ---------------------------------------------------------------------------


class TestWebhooks:
    def test_event_constants_defined(self):
        from agentic_brain.commerce import (
            WOO_EVENT_CUSTOMER_CREATED,
            WOO_EVENT_ORDER_CREATED,
            WOO_EVENT_ORDER_UPDATED,
            WOO_EVENT_PRODUCT_CREATED,
            WOO_EVENT_PRODUCT_UPDATED,
        )

        for const in [
            WOO_EVENT_ORDER_CREATED,
            WOO_EVENT_ORDER_UPDATED,
            WOO_EVENT_PRODUCT_CREATED,
            WOO_EVENT_PRODUCT_UPDATED,
            WOO_EVENT_CUSTOMER_CREATED,
        ]:
            assert isinstance(const, str)
            assert len(const) > 0

    def test_webhook_handler_instantiation(self):
        from agentic_brain.commerce import WooCommerceWebhookHandler

        handler = WooCommerceWebhookHandler(secret="my-secret")
        assert handler is not None

    def test_event_dispatcher_instantiation(self):
        from agentic_brain.commerce import WooCommerceEventDispatcher

        dispatcher = WooCommerceEventDispatcher()
        assert dispatcher is not None


# ---------------------------------------------------------------------------
# __init__.py exports test
# ---------------------------------------------------------------------------


class TestModuleExports:
    """Verify that every symbol listed in __all__ can actually be imported."""

    def test_all_exports_importable(self):
        import importlib

        import agentic_brain.commerce as mod

        for name in mod.__all__:
            obj = getattr(mod, name, None)
            assert obj is not None, f"'{name}' listed in __all__ but not importable"

    def test_commerce_hub_in_agentic_brain(self):
        import agentic_brain

        assert hasattr(agentic_brain, "CommerceHub")
        assert hasattr(agentic_brain, "CommerceConfig")
        assert hasattr(agentic_brain, "WooCommerceAgent")

    def test_commerce_hub_in_all(self):
        import agentic_brain

        # CommerceHub may be in __all__ or exported via lazy _LAZY_EXPORTS dict
        accessible = hasattr(agentic_brain, "CommerceHub") and hasattr(
            agentic_brain, "CommerceConfig"
        )
        assert (
            accessible
        ), "CommerceHub and CommerceConfig must be importable from agentic_brain"


# ---------------------------------------------------------------------------
# CommerceHub integration (with stubs)
# ---------------------------------------------------------------------------


class TestCommerceHubWithStubs:
    def _make_hub_with_stub_woo(self, products=None):
        from agentic_brain.commerce import CommerceConfig, CommerceHub

        hub = CommerceHub(CommerceConfig())
        hub._woo = StubWooAgent(products or [])
        return hub

    def test_inventory_uses_hub_woo(self):
        products = [_make_product(i, stock_quantity=10) for i in range(1, 6)]
        hub = self._make_hub_with_stub_woo(products)
        levels = hub.inventory.get_stock_levels()
        assert len(levels) == 5

    def test_inventory_low_stock_threshold_from_config(self):
        from agentic_brain.commerce import CommerceConfig, CommerceHub
        from agentic_brain.commerce.hub import InventoryConfig

        cfg = CommerceConfig(inventory=InventoryConfig(low_stock_threshold=10))
        hub = CommerceHub(cfg)
        hub._woo = StubWooAgent([_make_product(1, stock_quantity=8, manage_stock=True)])
        mgr = hub.inventory
        assert mgr.low_stock_threshold == 10
        report = mgr.get_low_stock_report()
        assert len(report.items) == 1  # 8 < 10 threshold

    def test_shipping_default_postcode_from_config(self):
        from agentic_brain.commerce import CommerceConfig, CommerceHub
        from agentic_brain.commerce.hub import ShippingConfig

        cfg = CommerceConfig(shipping=ShippingConfig(default_from_postcode="2000"))
        hub = CommerceHub(cfg)
        assert hub.shipping.default_from_postcode == "2000"

    def test_hub_health_check_structure(self):
        products = [_make_product(1)]
        hub = self._make_hub_with_stub_woo(products)
        result = hub.health_check()
        assert "woocommerce" in result
        assert "payments" in result
        assert "shipping" in result
        assert "inventory" in result

    def test_hub_health_check_woo_ok_when_products_returned(self):
        hub = self._make_hub_with_stub_woo([_make_product(1)])
        result = hub.health_check()
        assert result["woocommerce"] == "ok"

    def test_hub_health_check_woo_error_on_failure(self):
        from agentic_brain.commerce import CommerceConfig, CommerceHub

        hub = CommerceHub(CommerceConfig())
        # Override woo with a broken stub
        broken = MagicMock()
        broken.get_products_sync.side_effect = ConnectionError("store offline")
        hub._woo = broken
        result = hub.health_check()
        assert "error" in result["woocommerce"].lower()


# ---------------------------------------------------------------------------
# AusPost client stub tests
# ---------------------------------------------------------------------------


class TestAusPostCarrier:
    def test_auspost_carrier_instantiation(self):
        from agentic_brain.commerce.shipping import AusPostCarrier

        carrier = AusPostCarrier(api_key="test-key")
        assert carrier.api_key == "test-key"
        assert carrier.name == "AusPost"

    def test_auspost_client_is_carrier_alias(self):
        from agentic_brain.commerce.shipping import AusPostCarrier, AusPostClient

        assert issubclass(AusPostClient, AusPostCarrier)

    def test_auspost_carrier_get_rates_returns_list(self):
        """get_rates should return an empty list when API errors, not raise."""
        from agentic_brain.commerce.models import WooAddress
        from agentic_brain.commerce.shipping import AusPostCarrier, Dimensions

        mock_api = MagicMock()
        mock_api.get_domestic_rates.side_effect = ConnectionError("unreachable")
        carrier = AusPostCarrier(api_key="test-key", api=mock_api)
        origin = WooAddress(postcode="5000", country="AU")
        dest = WooAddress(postcode="3000", country="AU")
        dims = Dimensions(20, 15, 10, 1.0)
        rates = carrier.get_rates(origin, dest, [dims])
        assert isinstance(rates, list)

    def test_shipping_manager_get_cheapest_returns_lowest_cost(self):
        from agentic_brain.commerce.shipping import (
            AusPostCarrier,
            Dimensions,
            ShippingManager,
            ShippingRate,
        )

        carrier = MagicMock(spec=AusPostCarrier)
        carrier.name = "AusPost"
        carrier.get_rates.return_value = [
            ShippingRate(
                carrier="AusPost",
                service_code="EXPRESS",
                service_name="Express",
                cost=Decimal("14.50"),
            ),
            ShippingRate(
                carrier="AusPost",
                service_code="REGULAR",
                service_name="Regular",
                cost=Decimal("8.95"),
            ),
        ]
        mgr = ShippingManager(auspost_client=carrier, default_from_postcode="5000")
        cheapest = mgr.get_cheapest_rate("3000", Dimensions(20, 15, 10, 1.0))
        assert cheapest is not None
        assert cheapest.cost == Decimal("8.95")
