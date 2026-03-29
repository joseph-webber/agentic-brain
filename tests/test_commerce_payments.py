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

"""Tests for secure commerce payment gateway integrations."""

from __future__ import annotations

import hmac
import json
from decimal import Decimal

import pytest

from agentic_brain.commerce.payments import (
    FraudRejectedError,
    PaymentMethodReference,
    PaymentOperationNotSupported,
    PaymentProcessor,
    PaymentRequest,
    PaymentSecurityError,
    PayPalGateway,
    RefundRequest,
    SquareGateway,
    StripeGateway,
    SubscriptionRequest,
)


class FakeStripeClient:
    def __init__(self) -> None:
        self.intent_calls: list[dict] = []
        self.subscription_calls: list[dict] = []
        self.refund_calls: list[dict] = []

    def payment_intents_create(self, **kwargs):
        self.intent_calls.append(kwargs)
        return {
            "id": "pi_123",
            "status": "succeeded",
            "client_secret": "pi_client_secret_123",
        }

    def subscriptions_create(self, **kwargs):
        self.subscription_calls.append(kwargs)
        return {
            "id": "sub_123",
            "latest_invoice": "in_123",
            "status": "active",
        }

    def refunds_create(self, **kwargs):
        self.refund_calls.append(kwargs)
        return {
            "id": "re_123",
            "status": "succeeded",
        }


class FakePayPalClient:
    def __init__(self) -> None:
        self.order_calls: list[dict] = []
        self.refund_calls: list[dict] = []

    def orders_create(self, **kwargs):
        self.order_calls.append(kwargs)
        return {
            "id": "ORDER-123",
            "status": "CREATED",
            "links": [
                {
                    "rel": "approve",
                    "href": "https://paypal.example.test/approve/ORDER-123",
                }
            ],
        }

    def refunds_create(self, **kwargs):
        self.refund_calls.append(kwargs)
        return {
            "id": "RFD-123",
            "status": "COMPLETED",
        }


class FakeSquareClient:
    def __init__(self) -> None:
        self.payment_calls: list[dict] = []
        self.refund_calls: list[dict] = []

    def payments_create(self, **kwargs):
        self.payment_calls.append(kwargs)
        return {
            "payment": {
                "id": "sq_pay_123",
                "status": "COMPLETED",
                "card_details": {"status": "CAPTURED"},
            }
        }

    def refunds_create(self, **kwargs):
        self.refund_calls.append(kwargs)
        return {
            "refund": {
                "id": "sq_ref_123",
                "status": "COMPLETED",
            }
        }


@pytest.fixture
def payment_method() -> PaymentMethodReference:
    return PaymentMethodReference(
        token="pm_tok_123",
        method_type="card",
        brand="visa",
        last4="4242",
        cardholder_name="Joseph Webber",
    )


def test_payment_method_rejects_raw_card_data() -> None:
    with pytest.raises(PaymentSecurityError):
        PaymentMethodReference(
            token="pm_tok_123",
            metadata={"card_number": "4242424242424242"},
        )

    with pytest.raises(PaymentSecurityError):
        PaymentRequest(
            amount="10.00",
            currency="USD",
            payment_method=PaymentMethodReference(token="pm_tok_safe"),
            order_id="ORDER-RAW",
            metadata={"nested": {"cvv": "123"}},
        )


def test_stripe_gateway_supports_payment_intents_subscriptions_refunds_and_webhooks(
    payment_method: PaymentMethodReference,
) -> None:
    client = FakeStripeClient()
    gateway = StripeGateway(client)
    request = PaymentRequest(
        amount="10.50",
        currency="usd",
        payment_method=payment_method,
        order_id="ORDER-100",
        customer_id="cust_123",
        description="Accessible keyboard",
        metadata={"channel": "woocommerce"},
    )

    payment = gateway.create_payment_intent(request)
    assert payment.transaction_id == "pi_123"
    assert payment.status == "succeeded"
    assert payment.client_token == "pi_client_secret_123"
    assert client.intent_calls[0]["amount"] == 1050
    assert client.intent_calls[0]["payment_method"] == "pm_tok_123"

    subscription = gateway.create_subscription(
        SubscriptionRequest(
            customer_id="cust_123",
            price_id="price_monthly",
            payment_method=payment_method,
            metadata={"plan": "premium"},
        )
    )
    assert subscription.subscription_id == "sub_123"
    assert client.subscription_calls[0]["default_payment_method"] == "pm_tok_123"

    refund = gateway.refund_payment(
        RefundRequest(
            transaction_id="pi_123",
            amount="5.25",
            currency="USD",
            reason="requested_by_customer",
        )
    )
    assert refund.refund_id == "re_123"
    assert client.refund_calls[0]["amount"] == 525

    payload = json.dumps(
        {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123"}},
        }
    )
    timestamp = "1712345678"
    secret = "whsec_test"
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{payload}".encode(),
        "sha256",
    ).hexdigest()

    event = gateway.verify_webhook(
        payload,
        signature=f"t={timestamp},v1={signature}",
        webhook_secret=secret,
    )
    assert event.verified is True
    assert event.event_type == "payment_intent.succeeded"

    with pytest.raises(PaymentSecurityError):
        gateway.verify_webhook(
            payload,
            signature="t=1712345678,v1=bad-signature",
            webhook_secret=secret,
        )


def test_paypal_gateway_supports_express_checkout_and_refunds(
    payment_method: PaymentMethodReference,
) -> None:
    client = FakePayPalClient()
    gateway = PayPalGateway(client)
    request = PaymentRequest(
        amount="25.00",
        currency="AUD",
        payment_method=payment_method,
        order_id="ORDER-200",
        customer_id="customer-paypal",
        description="WooCommerce express checkout",
    )

    checkout = gateway.create_express_checkout(
        request,
        return_url="https://shop.example.test/return",
        cancel_url="https://shop.example.test/cancel",
    )
    assert checkout.checkout_url == "https://paypal.example.test/approve/ORDER-123"
    assert client.order_calls[0]["purchase_units"][0]["amount"] == {
        "currency_code": "AUD",
        "value": "25.00",
    }

    refund = gateway.refund_payment(
        RefundRequest(
            transaction_id="CAPTURE-123",
            amount="25.00",
            currency="AUD",
            reason="duplicate",
        )
    )
    assert refund.status == "COMPLETED"
    assert client.refund_calls[0]["capture_id"] == "CAPTURE-123"

    with pytest.raises(PaymentOperationNotSupported):
        gateway.create_payment(request)


def test_square_gateway_supports_retail_payments_and_refunds(
    payment_method: PaymentMethodReference,
) -> None:
    client = FakeSquareClient()
    gateway = SquareGateway(client)
    request = PaymentRequest(
        amount=Decimal("9.99"),
        currency="USD",
        payment_method=payment_method,
        order_id="ORDER-300",
        customer_id="cust-square",
        description="Retail counter payment",
    )

    payment = gateway.create_payment(request)
    assert payment.transaction_id == "sq_pay_123"
    assert client.payment_calls[0]["amount_money"] == {"amount": 999, "currency": "USD"}
    assert len(client.payment_calls[0]["idempotency_key"]) == 32

    refund = gateway.refund_payment(
        RefundRequest(
            transaction_id="sq_pay_123",
            amount="3.00",
            currency="USD",
            reason="partial_return",
        )
    )
    assert refund.refund_id == "sq_ref_123"
    assert client.refund_calls[0]["amount_money"] == {"amount": 300, "currency": "USD"}


def test_payment_processor_selects_gateway_logs_transactions_and_runs_fraud_hooks(
    payment_method: PaymentMethodReference,
) -> None:
    recorded = []
    hook_calls = []

    def logger(record):
        recorded.append(record)

    def fraud_hook(gateway_name, operation, payload):
        hook_calls.append((gateway_name, operation, payload.order_id))
        return {"allow": True, "score": 12}

    processor = PaymentProcessor(
        gateways={"stripe": StripeGateway(FakeStripeClient())},
        transaction_logger=logger,
        fraud_detection_hooks=[fraud_hook],
    )

    result = processor.process_payment(
        PaymentRequest(
            amount="44.00",
            currency="USD",
            payment_method=payment_method,
            order_id="ORDER-400",
            customer_id="cust-processor",
            description="WooCommerce checkout",
        )
    )

    assert result.transaction_id == "pi_123"
    assert hook_calls == [("stripe", "payment", "ORDER-400")]
    assert len(processor.transaction_log) == 1
    record = recorded[0]
    assert record.payment_method["last4"] == "4242"
    assert record.payment_method["token_fingerprint"] != payment_method.token
    assert "client_secret" not in str(record.metadata)
    assert record.metadata["fraud"][0]["score"] == 12


def test_payment_processor_logs_rejected_fraud_decisions(
    payment_method: PaymentMethodReference,
) -> None:
    processor = PaymentProcessor(
        gateways={"stripe": StripeGateway(FakeStripeClient())},
        fraud_detection_hooks=[
            lambda gateway_name, operation, payload: {
                "allow": False,
                "reason": f"blocked {operation} on {gateway_name}",
            }
        ],
    )

    with pytest.raises(FraudRejectedError, match="blocked payment on stripe"):
        processor.process_payment(
            PaymentRequest(
                amount="17.00",
                currency="USD",
                payment_method=payment_method,
                order_id="ORDER-500",
            )
        )

    assert processor.transaction_log[0].status == "rejected"
    assert processor.transaction_log[0].metadata["fraud"][0]["allow"] is False
