from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from agentic_brain.commerce.payments import (
    FraudRejectedError,
    GatewayType,
    PaymentError,
    PaymentMethodReference,
    PaymentOperationNotSupportedError,
    PaymentProcessor,
    PaymentRequest,
    PaymentSecurityError,
    RefundRequest,
    StripeGateway,
    ValidationError,
)


def test_payment_method_reference_requires_token():
    with pytest.raises(ValidationError):
        PaymentMethodReference(token="")


def test_payment_method_reference_validates_last4():
    with pytest.raises(ValidationError):
        PaymentMethodReference(token="pm", last4="12")


def test_payment_request_rejects_sensitive_metadata(payment_method):
    with pytest.raises(PaymentSecurityError):
        PaymentRequest(
            amount=Decimal("1"),
            currency="USD",
            payment_method=payment_method,
            order_id="order",
            metadata={"card_number": "4242"},
        )


def test_processor_available_gateways_returns_enum_when_possible(payment_processor):
    assert payment_processor.available_gateways() == ["fake"]


def test_processor_get_gateway_unknown_raises(payment_processor):
    with pytest.raises(PaymentError):
        payment_processor.get_gateway("nope")


def test_charge_calls_gateway_and_records_transaction(payment_processor, fake_gateway):
    intent = payment_processor.charge(
        Decimal("12.50"),
        "usd",
        "pm_test_123",
        order_id="order_1",
        description="Hello",
        metadata={"source": "test"},
    )
    assert intent.transaction_id == "tx_order_1"
    assert fake_gateway.calls[-1].operation == "create_payment"
    assert payment_processor.transaction_log[-1].operation == "payment"


def test_charge_supports_authorize_only_capture_false(payment_method, fake_gateway):
    processor = PaymentProcessor(
        gateways={"fake": fake_gateway}, default_gateway="fake"
    )
    request = PaymentRequest(
        amount=Decimal("25"),
        currency="USD",
        payment_method=payment_method,
        order_id="order_2",
        capture=False,
    )
    result = processor.process_payment(request)
    assert result.metadata.get("captured") is False


def test_refund_calls_gateway_and_records(
    payment_processor, refund_request, fake_gateway
):
    result = payment_processor.refund_payment(refund_request)
    assert result.refund_id == "rf_tx_order_123"
    assert fake_gateway.calls[-1].operation == "refund_payment"
    assert payment_processor.transaction_log[-1].operation == "refund"


def test_create_checkout_calls_gateway(
    payment_processor, payment_request, fake_gateway
):
    result = payment_processor.create_checkout(
        payment_request,
        return_url="https://return",
        cancel_url="https://cancel",
    )
    assert result.transaction_id == "co_order_123"
    assert fake_gateway.calls[-1].operation == "create_checkout"


def test_handle_webhook_unsupported_raises(payment_processor, payment_request):
    with pytest.raises(PaymentOperationNotSupportedError):
        payment_processor.handle_webhook(
            "{}",
            signature="sig",
            webhook_secret="secret",
            gateway_name="fake",
        )


def test_fraud_hook_can_reject_and_records_transaction(payment_method, fake_gateway):
    def reject_hook(gateway: str, operation: str, payload):
        return {"allow": False, "reason": "nope"}

    processor = PaymentProcessor(
        gateways={"fake": fake_gateway},
        default_gateway="fake",
        fraud_detection_hooks=[reject_hook],
    )
    request = PaymentRequest(
        amount=Decimal("5"),
        currency="USD",
        payment_method=payment_method,
        order_id="order_fraud",
    )
    with pytest.raises(FraudRejectedError):
        processor.process_payment(request)

    assert processor.transaction_log
    assert processor.transaction_log[-1].status == "rejected"


def test_stripe_gateway_passes_capture_flag_to_client(payment_method):
    calls = {}

    def payment_intents_create(**kwargs):
        calls.update(kwargs)
        return {"id": "pi_1", "status": "succeeded", "client_secret": "secret"}

    client = SimpleNamespace(payment_intents_create=payment_intents_create)
    gateway = StripeGateway(client=client)
    request = PaymentRequest(
        amount=Decimal("10"),
        currency="USD",
        payment_method=payment_method,
        order_id="order_stripe",
        capture=False,
    )
    gateway.create_payment(request)
    assert calls["confirm"] is False
