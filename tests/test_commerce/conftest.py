from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from agentic_brain.commerce.chatbot.cart_assistant import CartAssistant, CartLine
from agentic_brain.commerce.inventory import InventoryManager
from agentic_brain.commerce.models import WooCategory, WooCoupon, WooProduct
from agentic_brain.commerce.payments import (
    PaymentGateway,
    PaymentMethodReference,
    PaymentProcessor,
    PaymentRequest,
    PaymentResult,
    RefundRequest,
    RefundResult,
)


@dataclass
class GatewayCall:
    operation: str
    payload: Any


class FakeGateway(PaymentGateway):
    """Simple in-memory payment gateway for unit tests."""

    def __init__(
        self,
        *,
        name: str = "fake",
        payment_status: str = "succeeded",
        refund_status: str = "refunded",
        checkout_status: str = "created",
    ) -> None:
        self._name = name
        self.payment_status = payment_status
        self.refund_status = refund_status
        self.checkout_status = checkout_status
        self.calls: list[GatewayCall] = []

    @property
    def name(self) -> str:  # pragma: no cover - trivial
        return self._name

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        self.calls.append(GatewayCall("create_payment", request))
        return PaymentResult(
            gateway=self.name,
            transaction_id=f"tx_{request.order_id}",
            status=self.payment_status,
            amount=request.amount,
            currency=request.currency,
            metadata={"captured": bool(request.capture)},
        )

    def refund_payment(self, request: RefundRequest) -> RefundResult:
        self.calls.append(GatewayCall("refund_payment", request))
        return RefundResult(
            gateway=self.name,
            refund_id=f"rf_{request.transaction_id}",
            status=self.refund_status,
            transaction_id=request.transaction_id,
            amount=request.amount,
            currency=request.currency,
            metadata={},
        )

    def create_checkout(
        self,
        request: PaymentRequest,
        *,
        return_url: str,
        cancel_url: str,
    ) -> PaymentResult:
        self.calls.append(
            GatewayCall(
                "create_checkout",
                {
                    "request": request,
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            )
        )
        return PaymentResult(
            gateway=self.name,
            transaction_id=f"co_{request.order_id}",
            status=self.checkout_status,
            amount=request.amount,
            currency=request.currency,
            checkout_url=return_url,
            metadata={},
        )


@pytest.fixture
def fake_gateway() -> FakeGateway:
    return FakeGateway(name="fake")


@pytest.fixture
def payment_processor(fake_gateway: FakeGateway) -> PaymentProcessor:
    return PaymentProcessor(
        gateways={fake_gateway.name: fake_gateway}, default_gateway="fake"
    )


@pytest.fixture
def payment_method() -> PaymentMethodReference:
    return PaymentMethodReference(token="pm_test_123", brand="visa", last4="4242")


@pytest.fixture
def payment_request(payment_method: PaymentMethodReference) -> PaymentRequest:
    return PaymentRequest(
        amount=Decimal("25.00"),
        currency="usd",
        payment_method=payment_method,
        order_id="order_123",
        customer_id="cust_1",
        description="Test order",
        capture=True,
        metadata={"cart_id": "cart_1"},
    )


@pytest.fixture
def refund_request() -> RefundRequest:
    return RefundRequest(
        transaction_id="tx_order_123",
        amount=Decimal("5.00"),
        currency="USD",
        reason="requested_by_customer",
        metadata={"note": "partial"},
    )


@pytest.fixture
def products() -> list[WooProduct]:
    cat = WooCategory(id=10, name="Accessories")
    return [
        WooProduct(
            id=1, name="Cable", price=Decimal("10.00"), stock=100, categories=[cat]
        ),
        WooProduct(
            id=2, name="Adapter", price=Decimal("15.00"), stock=5, categories=[cat]
        ),
        WooProduct(
            id=3, name="Out of stock", price=Decimal("99.00"), stock=0, categories=[cat]
        ),
    ]


@pytest.fixture
def coupon_percent() -> WooCoupon:
    return WooCoupon(id=1, code="SAVE10", amount=Decimal("10"), discount_type="percent")


@pytest.fixture
def coupon_fixed() -> WooCoupon:
    return WooCoupon(
        id=2, code="FIVEOFF", amount=Decimal("5.00"), discount_type="fixed_cart"
    )


@pytest.fixture
def cart_lines(products: list[WooProduct]) -> list[CartLine]:
    return [
        CartLine(
            product_id=products[0].id,
            name=products[0].name,
            quantity=2,
            unit_price=products[0].price,
        ),
        CartLine(
            product_id=products[1].id,
            name=products[1].name,
            quantity=1,
            unit_price=products[1].price,
        ),
    ]


@pytest.fixture
def cart_assistant() -> CartAssistant:
    return CartAssistant(currency="USD")


@pytest.fixture
def cart_summary(cart_assistant: CartAssistant, cart_lines: list[CartLine]):
    return cart_assistant.build_summary(cart_lines)


@pytest.fixture
def inventory_manager() -> InventoryManager:
    manager = InventoryManager(woo_agent=None)
    # preload local stock for checkout tests
    manager.update_local_stock(
        product_id=1, quantity=10, sku="SKU-1", warehouse_id="default"
    )
    return manager
