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

"""Secure payment gateway abstractions for WooCommerce commerce integrations.

This module follows PCI-DSS-aligned patterns:
- only tokenized payment references are accepted
- raw PAN/CVV values are rejected before processing
- transaction logs store hashes/masked summaries rather than payment secrets
- webhook signatures are verified with constant-time comparison
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

FORBIDDEN_PAYMENT_KEYS = frozenset(
    {
        "account_number",
        "card_number",
        "cvc",
        "cvv",
        "expiry",
        "expiry_month",
        "expiry_year",
        "full_track_data",
        "magstripe",
        "pan",
        "pin",
        "security_code",
        "track_data",
    }
)
LOG_REDACTION_KEYS = FORBIDDEN_PAYMENT_KEYS | frozenset(
    {
        "access_token",
        "authorization",
        "bearer_token",
        "client_secret",
        "payment_method",
        "source_id",
        "token",
    }
)
ZERO_DECIMAL_CURRENCIES = frozenset(
    {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "JPY",
        "KMF",
        "KRW",
        "MGA",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }
)


class PaymentError(Exception):
    """Base payment processing error."""


class PaymentSecurityError(PaymentError):
    """Raised when a request violates PCI-DSS-safe input rules."""


class PaymentOperationNotSupportedError(PaymentError):
    """Raised when a gateway does not support a requested operation."""


PaymentOperationNotSupported = PaymentOperationNotSupportedError


class FraudRejectedError(PaymentError):
    """Raised when a fraud detection hook blocks an operation."""


class GatewayType(StrEnum):
    """Supported payment gateway identifiers."""

    STRIPE = "stripe"
    PAYPAL = "paypal"
    SQUARE = "square"
    COD = "cod"


class PaymentStatus(StrEnum):
    """Normalized payment status values."""

    PENDING = "pending"
    CREATED = "created"
    SUCCEEDED = "succeeded"
    COMPLETED = "completed"
    ACTIVE = "active"
    FAILED = "failed"
    REFUNDED = "refunded"
    REJECTED = "rejected"


@dataclass(slots=True)
class PaymentMethodReference:
    """Tokenized payment method reference.

    Raw card data is intentionally unsupported. Callers must pass a vault token,
    provider nonce, or payment method id issued by a PCI-compliant processor.
    """

    token: str
    method_type: str = "card"
    brand: str | None = None
    last4: str | None = None
    cardholder_name: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.token or not self.token.strip():
            raise ValueError("payment method token is required")
        if self.last4 is not None:
            normalized_last4 = self.last4.strip()
            if len(normalized_last4) != 4 or not normalized_last4.isdigit():
                raise ValueError("last4 must contain exactly 4 digits")
            self.last4 = normalized_last4
        self.metadata = dict(
            _validate_no_sensitive_keys(
                self.metadata, context="payment_method.metadata"
            )
        )

    @property
    def token_fingerprint(self) -> str:
        """Stable fingerprint for correlation without storing the token value."""
        return hashlib.sha256(self.token.encode("utf-8")).hexdigest()[:12]

    def masked_summary(self) -> dict[str, str]:
        """Return a safe summary suitable for logs and audit records."""
        summary = {
            "method_type": self.method_type,
            "token_fingerprint": self.token_fingerprint,
        }
        if self.brand:
            summary["brand"] = self.brand
        if self.last4:
            summary["last4"] = self.last4
        if self.cardholder_name:
            summary["cardholder_name"] = self.cardholder_name
        return summary


@dataclass(slots=True)
class PaymentRequest:
    """Generic payment request for tokenized gateway operations."""

    amount: Decimal | str | int | float
    currency: str
    payment_method: PaymentMethodReference
    order_id: str
    customer_id: str | None = None
    description: str | None = None
    capture: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.amount = _normalize_amount(self.amount, field_name="amount")
        self.currency = _normalize_currency(self.currency)
        if not self.order_id:
            raise ValueError("order_id is required")
        self.metadata = _validate_no_sensitive_keys(
            self.metadata, context="payment.metadata"
        )


@dataclass(slots=True)
class SubscriptionRequest:
    """Subscription creation payload."""

    customer_id: str
    price_id: str
    payment_method: PaymentMethodReference
    quantity: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.customer_id:
            raise ValueError("customer_id is required")
        if not self.price_id:
            raise ValueError("price_id is required")
        if self.quantity < 1:
            raise ValueError("quantity must be at least 1")
        self.metadata = _validate_no_sensitive_keys(
            self.metadata, context="subscription.metadata"
        )


@dataclass(slots=True)
class RefundRequest:
    """Refund request payload."""

    transaction_id: str
    amount: Decimal | str | int | float | None = None
    currency: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transaction_id:
            raise ValueError("transaction_id is required")
        if self.amount is not None:
            self.amount = _normalize_amount(self.amount, field_name="refund amount")
        if self.currency is not None:
            self.currency = _normalize_currency(self.currency)
        self.metadata = _validate_no_sensitive_keys(
            self.metadata, context="refund.metadata"
        )


@dataclass(slots=True)
class PaymentResult:
    """Normalized successful payment result."""

    gateway: str
    transaction_id: str
    status: str
    amount: Decimal | None = None
    currency: str | None = None
    client_token: str | None = None
    checkout_url: str | None = None
    subscription_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RefundResult:
    """Normalized refund result."""

    gateway: str
    refund_id: str
    status: str
    transaction_id: str
    amount: Decimal | None = None
    currency: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WebhookEvent:
    """Verified webhook event."""

    gateway: str
    event_id: str | None
    event_type: str | None
    verified: bool
    payload: dict[str, Any]


PaymentIntent = PaymentResult


@dataclass(slots=True)
class TransactionRecord:
    """Sanitized audit trail record for gateway operations."""

    operation: str
    gateway: str
    status: str
    timestamp: datetime
    transaction_id: str | None = None
    order_id: str | None = None
    customer_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    payment_method: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


FraudDecision = bool | Mapping[str, Any]
FraudHook = Callable[[str, str, Any], FraudDecision]
TransactionLogger = Callable[[TransactionRecord], None]


class PaymentGateway(ABC):
    """Abstract payment gateway interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Gateway name used by the processor registry."""

    @abstractmethod
    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """Create a payment using tokenized payment data only."""

    @abstractmethod
    def refund_payment(self, request: RefundRequest) -> RefundResult:
        """Refund a previously captured payment."""

    def create_subscription(self, request: SubscriptionRequest) -> PaymentResult:
        raise PaymentOperationNotSupported(
            f"{self.name} does not support subscription creation"
        )

    def create_checkout(
        self,
        request: PaymentRequest,
        *,
        return_url: str,
        cancel_url: str,
    ) -> PaymentResult:
        raise PaymentOperationNotSupported(
            f"{self.name} does not support checkout sessions"
        )

    def verify_webhook(
        self,
        payload: str | bytes,
        *,
        signature: str,
        webhook_secret: str,
    ) -> WebhookEvent:
        raise PaymentOperationNotSupported(
            f"{self.name} does not support webhook verification"
        )


class StripeGateway(PaymentGateway):
    """Stripe payment gateway wrapper with intents, subscriptions, refunds, and webhooks."""

    def __init__(self, client: Any | None = None, *, api_key: str | None = None):
        self.client = client
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "stripe"

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        payload = _call_client_method(
            self.client,
            [
                "payment_intents_create",
                "payment_intents.create",
                "PaymentIntent.create",
            ],
            amount=_to_minor_units(request.amount, request.currency),
            currency=request.currency.lower(),
            customer=request.customer_id,
            payment_method=request.payment_method.token,
            confirm=request.capture,
            description=request.description,
            metadata=request.metadata,
        )
        data = _ensure_mapping(payload)
        return PaymentResult(
            gateway=self.name,
            transaction_id=str(data["id"]),
            status=str(data.get("status", "requires_confirmation")),
            amount=request.amount,
            currency=request.currency,
            client_token=_safe_string(data.get("client_secret")),
            metadata=_sanitize_for_logging(data),
        )

    def create_payment_intent(self, request: PaymentRequest) -> PaymentResult:
        """Explicit Stripe payment-intent alias."""
        return self.create_payment(request)

    def create_subscription(self, request: SubscriptionRequest) -> PaymentResult:
        payload = _call_client_method(
            self.client,
            ["subscriptions_create", "subscriptions.create", "Subscription.create"],
            customer=request.customer_id,
            items=[{"price": request.price_id, "quantity": request.quantity}],
            default_payment_method=request.payment_method.token,
            metadata=request.metadata,
        )
        data = _ensure_mapping(payload)
        return PaymentResult(
            gateway=self.name,
            transaction_id=str(data.get("latest_invoice", data.get("id"))),
            status=str(data.get("status", "incomplete")),
            subscription_id=str(data["id"]),
            metadata=_sanitize_for_logging(data),
        )

    def refund_payment(self, request: RefundRequest) -> RefundResult:
        kwargs: dict[str, Any] = {
            "payment_intent": request.transaction_id,
            "reason": request.reason,
            "metadata": request.metadata,
        }
        if request.amount is not None:
            kwargs["amount"] = _to_minor_units(
                request.amount,
                request.currency or "USD",
            )
        payload = _call_client_method(
            self.client,
            ["refunds_create", "refunds.create", "Refund.create"],
            **kwargs,
        )
        data = _ensure_mapping(payload)
        return RefundResult(
            gateway=self.name,
            refund_id=str(data["id"]),
            status=str(data.get("status", "pending")),
            transaction_id=request.transaction_id,
            amount=request.amount,
            currency=request.currency,
            metadata=_sanitize_for_logging(data),
        )

    def verify_webhook(
        self,
        payload: str | bytes,
        *,
        signature: str,
        webhook_secret: str,
    ) -> WebhookEvent:
        body = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        signed_body = _verify_stripe_signature(
            body,
            signature_header=signature,
            secret=webhook_secret,
        )
        event = json.loads(signed_body)
        return WebhookEvent(
            gateway=self.name,
            event_id=_safe_string(event.get("id")),
            event_type=_safe_string(event.get("type")),
            verified=True,
            payload=event,
        )


class PayPalGateway(PaymentGateway):
    """PayPal Express Checkout and refund wrapper."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        sandbox: bool = True,
    ):
        self.client = client
        self.client_id = client_id
        self.client_secret = client_secret
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        return "paypal"

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        raise PaymentOperationNotSupported(
            "paypal direct payments are not exposed here; use create_checkout()"
        )

    def create_checkout(
        self,
        request: PaymentRequest,
        *,
        return_url: str,
        cancel_url: str,
    ) -> PaymentResult:
        payload = _call_client_method(
            self.client,
            ["orders_create", "orders.create", "Order.create"],
            intent="CAPTURE",
            purchase_units=[
                {
                    "reference_id": request.order_id,
                    "amount": {
                        "currency_code": request.currency,
                        "value": f"{request.amount:.2f}",
                    },
                    "description": request.description,
                    "custom_id": request.customer_id,
                }
            ],
            payment_source={
                "paypal": {
                    "experience_context": {
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    }
                }
            },
        )
        data = _ensure_mapping(payload)
        checkout_url = _extract_link(data.get("links", []), rel="approve")
        return PaymentResult(
            gateway=self.name,
            transaction_id=str(data["id"]),
            status=str(data.get("status", "CREATED")),
            amount=request.amount,
            currency=request.currency,
            checkout_url=checkout_url,
            metadata=_sanitize_for_logging(data),
        )

    def create_express_checkout(
        self,
        request: PaymentRequest,
        *,
        return_url: str,
        cancel_url: str,
    ) -> PaymentResult:
        """Explicit PayPal Express Checkout alias."""
        return self.create_checkout(
            request,
            return_url=return_url,
            cancel_url=cancel_url,
        )

    def refund_payment(self, request: RefundRequest) -> RefundResult:
        currency = request.currency or "USD"
        kwargs: dict[str, Any] = {
            "capture_id": request.transaction_id,
            "note_to_payer": request.reason,
        }
        if request.amount is not None:
            kwargs["amount"] = {
                "value": f"{request.amount:.2f}",
                "currency_code": currency,
            }
        payload = _call_client_method(
            self.client,
            ["refunds_create", "payments_refund", "refunds.create"],
            **kwargs,
        )
        data = _ensure_mapping(payload)
        return RefundResult(
            gateway=self.name,
            refund_id=str(data["id"]),
            status=str(data.get("status", "COMPLETED")),
            transaction_id=request.transaction_id,
            amount=request.amount,
            currency=currency,
            metadata=_sanitize_for_logging(data),
        )


class SquareGateway(PaymentGateway):
    """Square gateway wrapper for retail and in-person payments."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        access_token: str | None = None,
        location_id: str | None = None,
    ):
        self.client = client
        self.access_token = access_token
        self.location_id = location_id

    @property
    def name(self) -> str:
        return "square"

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        payload = _call_client_method(
            self.client,
            ["payments_create", "payments.create", "PaymentsApi.create_payment"],
            source_id=request.payment_method.token,
            amount_money={
                "amount": _to_minor_units(request.amount, request.currency),
                "currency": request.currency,
            },
            autocomplete=request.capture,
            idempotency_key=_idempotency_key(
                self.name, request.order_id, request.amount
            ),
            note=request.description,
            reference_id=request.order_id,
            customer_id=request.customer_id,
        )
        data = _ensure_mapping(payload)
        payment = _ensure_mapping(data.get("payment", data))
        return PaymentResult(
            gateway=self.name,
            transaction_id=str(payment["id"]),
            status=str(payment.get("status", "PENDING")),
            amount=request.amount,
            currency=request.currency,
            metadata=_sanitize_for_logging(payment),
        )

    def refund_payment(self, request: RefundRequest) -> RefundResult:
        currency = request.currency or "USD"
        payload = _call_client_method(
            self.client,
            [
                "refunds_create",
                "refunds.create",
                "RefundsApi.refund_payment",
            ],
            payment_id=request.transaction_id,
            amount_money=(
                {
                    "amount": _to_minor_units(request.amount, currency),
                    "currency": currency,
                }
                if request.amount is not None
                else None
            ),
            idempotency_key=_idempotency_key(
                self.name,
                request.transaction_id,
                request.amount or Decimal("0.00"),
            ),
            reason=request.reason,
        )
        data = _ensure_mapping(payload)
        refund = _ensure_mapping(data.get("refund", data))
        return RefundResult(
            gateway=self.name,
            refund_id=str(refund["id"]),
            status=str(refund.get("status", "PENDING")),
            transaction_id=request.transaction_id,
            amount=request.amount,
            currency=currency,
            metadata=_sanitize_for_logging(refund),
        )


class CashOnDeliveryGateway(PaymentGateway):
    """Offline cash-on-delivery gateway for WooCommerce compatibility."""

    @property
    def name(self) -> str:
        return GatewayType.COD.value

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            gateway=self.name,
            transaction_id=f"cod_{request.order_id}",
            status=PaymentStatus.PENDING.value,
            amount=request.amount,
            currency=request.currency,
            metadata={
                "collection_method": "cash_on_delivery",
                "instructions": "Collect payment from the customer at fulfilment time.",
            },
        )

    def refund_payment(self, request: RefundRequest) -> RefundResult:
        raise PaymentOperationNotSupported(
            "cash on delivery refunds must be handled outside the payment processor"
        )


class PaymentProcessor:
    """High-level gateway orchestrator with fraud hooks and sanitized audit logging."""

    def __init__(
        self,
        gateways: Mapping[str | GatewayType, PaymentGateway],
        *,
        default_gateway: str | GatewayType | None = None,
        transaction_logger: TransactionLogger | None = None,
        fraud_detection_hooks: Sequence[FraudHook] | None = None,
    ):
        if not gateways:
            raise ValueError("at least one payment gateway is required")
        self._gateways = {
            self._normalize_gateway_name(name): gateway
            for name, gateway in gateways.items()
        }
        self._default_gateway = self._normalize_gateway_name(
            default_gateway or next(iter(self._gateways))
        )
        if self._default_gateway not in self._gateways:
            raise ValueError("default_gateway must exist in gateways")
        self._transaction_logger = transaction_logger
        self._fraud_detection_hooks = list(fraud_detection_hooks or [])
        self.transaction_log: list[TransactionRecord] = []

    @staticmethod
    def _normalize_gateway_name(gateway_name: str | GatewayType) -> str:
        if isinstance(gateway_name, GatewayType):
            return gateway_name.value
        return gateway_name.lower()

    def available_gateways(self) -> list[GatewayType | str]:
        """Return configured gateways in registration order."""
        available: list[GatewayType | str] = []
        for name in self._gateways:
            try:
                available.append(GatewayType(name))
            except ValueError:
                available.append(name)
        return available

    def get_gateway(
        self, gateway_name: str | GatewayType | None = None
    ) -> PaymentGateway:
        """Return the configured gateway by name."""
        selected = self._normalize_gateway_name(gateway_name or self._default_gateway)
        try:
            return self._gateways[selected]
        except KeyError as exc:
            raise PaymentError(f"unknown payment gateway: {selected}") from exc

    def charge(
        self,
        amount: Decimal | str | int | float,
        currency: str,
        payment_method_token: str,
        *,
        order_id: str | int,
        customer_id: str | None = None,
        description: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        gateway_name: str | GatewayType | None = None,
    ) -> PaymentIntent:
        """Backward-compatible convenience wrapper for direct charges."""
        request = PaymentRequest(
            amount=amount,
            currency=currency,
            payment_method=PaymentMethodReference(token=payment_method_token),
            order_id=str(order_id),
            customer_id=customer_id,
            description=description,
            metadata=dict(metadata or {}),
        )
        return self.process_payment(request, gateway_name=gateway_name)

    def process_payment(
        self,
        request: PaymentRequest,
        *,
        gateway_name: str | None = None,
    ) -> PaymentResult:
        gateway = self.get_gateway(gateway_name)
        fraud_metadata = self._run_fraud_checks(gateway.name, "payment", request)
        result = gateway.create_payment(request)
        self._record_transaction(
            operation="payment",
            gateway=gateway.name,
            status=result.status,
            transaction_id=result.transaction_id,
            order_id=request.order_id,
            customer_id=request.customer_id,
            amount=result.amount,
            currency=result.currency,
            payment_method=request.payment_method,
            metadata={**fraud_metadata, **result.metadata},
        )
        return result

    def create_subscription(
        self,
        request: SubscriptionRequest,
        *,
        gateway_name: str | None = None,
    ) -> PaymentResult:
        gateway = self.get_gateway(gateway_name)
        fraud_metadata = self._run_fraud_checks(gateway.name, "subscription", request)
        result = gateway.create_subscription(request)
        self._record_transaction(
            operation="subscription",
            gateway=gateway.name,
            status=result.status,
            transaction_id=result.subscription_id or result.transaction_id,
            customer_id=request.customer_id,
            payment_method=request.payment_method,
            metadata={**fraud_metadata, **result.metadata},
        )
        return result

    def create_checkout(
        self,
        request: PaymentRequest,
        *,
        return_url: str,
        cancel_url: str,
        gateway_name: str | None = None,
    ) -> PaymentResult:
        gateway = self.get_gateway(gateway_name)
        fraud_metadata = self._run_fraud_checks(gateway.name, "checkout", request)
        result = gateway.create_checkout(
            request,
            return_url=return_url,
            cancel_url=cancel_url,
        )
        self._record_transaction(
            operation="checkout",
            gateway=gateway.name,
            status=result.status,
            transaction_id=result.transaction_id,
            order_id=request.order_id,
            customer_id=request.customer_id,
            amount=result.amount,
            currency=result.currency,
            payment_method=request.payment_method,
            metadata={**fraud_metadata, **result.metadata},
        )
        return result

    def refund_payment(
        self,
        request: RefundRequest,
        *,
        gateway_name: str | None = None,
    ) -> RefundResult:
        gateway = self.get_gateway(gateway_name)
        fraud_metadata = self._run_fraud_checks(gateway.name, "refund", request)
        result = gateway.refund_payment(request)
        self._record_transaction(
            operation="refund",
            gateway=gateway.name,
            status=result.status,
            transaction_id=result.refund_id,
            amount=result.amount,
            currency=result.currency,
            metadata={
                "original_transaction_id": request.transaction_id,
                **fraud_metadata,
                **result.metadata,
            },
        )
        return result

    def handle_webhook(
        self,
        payload: str | bytes,
        *,
        signature: str,
        webhook_secret: str,
        gateway_name: str,
    ) -> WebhookEvent:
        gateway = self.get_gateway(gateway_name)
        event = gateway.verify_webhook(
            payload,
            signature=signature,
            webhook_secret=webhook_secret,
        )
        self._record_transaction(
            operation="webhook",
            gateway=gateway.name,
            status="verified" if event.verified else "unverified",
            transaction_id=event.event_id,
            metadata=_sanitize_for_logging(event.payload),
        )
        return event

    def _run_fraud_checks(
        self,
        gateway_name: str,
        operation: str,
        payload: Any,
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        for hook in self._fraud_detection_hooks:
            decision = hook(gateway_name, operation, payload)
            normalized = _normalize_fraud_decision(decision)
            findings.append(normalized)
            if not normalized["allow"]:
                reason = normalized.get("reason") or "fraud hook rejected request"
                self._record_transaction(
                    operation=operation,
                    gateway=gateway_name,
                    status="rejected",
                    transaction_id=getattr(payload, "transaction_id", None),
                    order_id=getattr(payload, "order_id", None),
                    customer_id=getattr(payload, "customer_id", None),
                    amount=getattr(payload, "amount", None),
                    currency=getattr(payload, "currency", None),
                    payment_method=getattr(payload, "payment_method", None),
                    metadata={"fraud": findings},
                )
                raise FraudRejectedError(str(reason))
        return {"fraud": findings} if findings else {}

    def _record_transaction(
        self,
        *,
        operation: str,
        gateway: str,
        status: str,
        transaction_id: str | None = None,
        order_id: str | None = None,
        customer_id: str | None = None,
        amount: Decimal | None = None,
        currency: str | None = None,
        payment_method: PaymentMethodReference | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TransactionRecord:
        record = TransactionRecord(
            operation=operation,
            gateway=gateway,
            status=status,
            transaction_id=transaction_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            timestamp=datetime.now(UTC),
            payment_method=(payment_method.masked_summary() if payment_method else {}),
            metadata=_sanitize_for_logging(metadata or {}),
        )
        self.transaction_log.append(record)
        if self._transaction_logger is not None:
            self._transaction_logger(record)
        logger.info(
            "payment operation=%s gateway=%s status=%s transaction_id=%s",
            operation,
            gateway,
            status,
            transaction_id,
        )
        return record


def _normalize_amount(
    value: Decimal | str | int | float,
    *,
    field_name: str,
) -> Decimal:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= Decimal("0.00"):
        raise ValueError(f"{field_name} must be greater than zero")
    return amount


def _normalize_currency(currency: str) -> str:
    normalized = currency.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("currency must be a 3-letter ISO 4217 code")
    return normalized


def _to_minor_units(amount: Decimal, currency: str) -> int:
    if currency.upper() in ZERO_DECIMAL_CURRENCIES:
        return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _idempotency_key(prefix: str, reference: str, amount: Decimal) -> str:
    source = f"{prefix}:{reference}:{amount:.2f}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]


def _validate_no_sensitive_keys(
    payload: Mapping[str, Any],
    *,
    context: str,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = key.lower()
        if normalized in FORBIDDEN_PAYMENT_KEYS:
            raise PaymentSecurityError(
                f"{context} contains forbidden payment field '{key}'"
            )
        if isinstance(value, Mapping):
            sanitized[key] = _validate_no_sensitive_keys(
                value,
                context=f"{context}.{key}",
            )
        elif isinstance(value, list):
            sanitized[key] = [
                (
                    _validate_no_sensitive_keys(item, context=f"{context}.{key}")
                    if isinstance(item, Mapping)
                    else item
                )
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def _sanitize_for_logging(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized = key.lower()
            if normalized in LOG_REDACTION_KEYS:
                continue
            sanitized[key] = _sanitize_for_logging(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_for_logging(item) for item in value]
    return value


def _call_client_method(client: Any, paths: Sequence[str], **kwargs: Any) -> Any:
    for path in paths:
        target = client
        try:
            for part in path.split("."):
                target = getattr(target, part)
        except AttributeError:
            continue
        if callable(target):
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            return target(**filtered_kwargs)
    raise PaymentError(
        f"client for gateway operation is missing supported method paths: {', '.join(paths)}"
    )


def _ensure_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PaymentError("gateway client returned a non-mapping response")
    return value


def _extract_link(links: Any, *, rel: str) -> str | None:
    if isinstance(links, list):
        for item in links:
            if isinstance(item, Mapping) and item.get("rel") == rel:
                href = item.get("href")
                if isinstance(href, str) and href:
                    return href
    return None


def _safe_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _verify_stripe_signature(
    payload: str,
    *,
    signature_header: str,
    secret: str,
) -> str:
    timestamp: str | None = None
    signature: str | None = None
    for part in signature_header.split(","):
        part = part.strip()
        if part.startswith("t="):
            timestamp = part[2:]
        elif part.startswith("v1="):
            signature = part[3:]

    if timestamp is None or signature is None:
        signature = signature_header.strip()
        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    else:
        signed_payload = f"{timestamp}.{payload}".encode()
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise PaymentSecurityError("invalid webhook signature")
    return payload


def _normalize_fraud_decision(decision: FraudDecision) -> dict[str, Any]:
    if isinstance(decision, Mapping):
        allow = bool(decision.get("allow", True))
        normalized = dict(decision)
        normalized["allow"] = allow
        return normalized
    return {"allow": bool(decision)}


__all__ = [
    "CashOnDeliveryGateway",
    "FraudRejectedError",
    "GatewayType",
    "PayPalGateway",
    "PaymentError",
    "PaymentGateway",
    "PaymentIntent",
    "PaymentMethodReference",
    "PaymentOperationNotSupported",
    "PaymentOperationNotSupportedError",
    "PaymentProcessor",
    "PaymentRequest",
    "PaymentResult",
    "PaymentSecurityError",
    "PaymentStatus",
    "RefundRequest",
    "RefundResult",
    "SquareGateway",
    "StripeGateway",
    "SubscriptionRequest",
    "TransactionRecord",
    "WebhookEvent",
]
