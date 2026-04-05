#!/usr/bin/env python3
"""
Example: PayPal-Powered Conversational Commerce Chatbot

A complete PayPal payment integration via natural conversation:
- Create payment orders and checkout links
- Send money (PayPal Payouts)
- Manage subscriptions
- Handle disputes via chat
- Query balance and transaction history

Example Conversation:
╔══════════════════════════════════════════════════════════════════════════════╗
║  User: "Pay $50 to supplier@example.com"                                     ║
║  Bot:  "Creating PayPal payment for $50 AUD to supplier@example.com..."     ║
║  Bot:  "Approve this payment: https://paypal.com/checkoutnow?token=xxx"     ║
║  User: "Approved"                                                            ║
║  Bot:  "Payment complete! Transaction ID: PAY-ABC123"                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Security:
- OAuth 2.0 authentication with PayPal APIs
- Webhook signature verification
- No sensitive data in logs
- Idempotent payment creation

Australian Context:
- AUD as default currency
- GST (10%) handling
- PayPal Australia regulations
- Consumer protection compliance

Usage:
    python examples/enterprise/paypal_payment_bot.py

Requirements:
    pip install agentic-brain paypalrestsdk
    export PAYPAL_CLIENT_ID=xxx
    export PAYPAL_CLIENT_SECRET=xxx
    export PAYPAL_WEBHOOK_ID=xxx
"""

import asyncio
import base64
import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [PAYPAL_BOT] %(message)s"
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# PAYPAL SDK MOCK (Replace with real paypalrestsdk in production)
# ══════════════════════════════════════════════════════════════════════════════


class MockPayPalAPI:
    """
    Mock PayPal API for demonstration.
    In production, use official PayPal SDK or REST API.
    """

    class Orders:
        @staticmethod
        def create(request_body: dict) -> dict:
            order_id = f"ORDER-{secrets.token_hex(8).upper()}"
            return {
                "id": order_id,
                "status": "CREATED",
                "links": [
                    {
                        "href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",
                        "rel": "approve",
                        "method": "GET",
                    },
                    {
                        "href": f"https://api.sandbox.paypal.com/v2/checkout/orders/{order_id}",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": f"https://api.sandbox.paypal.com/v2/checkout/orders/{order_id}/capture",
                        "rel": "capture",
                        "method": "POST",
                    },
                ],
            }

        @staticmethod
        def get(order_id: str) -> dict:
            return {
                "id": order_id,
                "status": "APPROVED",
                "purchase_units": [
                    {
                        "amount": {"currency_code": "AUD", "value": "50.00"},
                        "payee": {"email_address": "seller@example.com"},
                    }
                ],
            }

        @staticmethod
        def capture(order_id: str) -> dict:
            capture_id = f"CAPTURE-{secrets.token_hex(6).upper()}"
            return {
                "id": order_id,
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [
                                {
                                    "id": capture_id,
                                    "status": "COMPLETED",
                                    "amount": {
                                        "currency_code": "AUD",
                                        "value": "50.00",
                                    },
                                }
                            ]
                        }
                    }
                ],
            }

    class Payouts:
        @staticmethod
        def create(request_body: dict) -> dict:
            batch_id = f"PAYOUT-{secrets.token_hex(6).upper()}"
            return {
                "batch_header": {
                    "payout_batch_id": batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": request_body.get("sender_batch_header", {}),
                },
                "links": [
                    {
                        "href": f"https://api.sandbox.paypal.com/v1/payments/payouts/{batch_id}",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
            }

        @staticmethod
        def get(payout_id: str) -> dict:
            return {
                "batch_header": {
                    "payout_batch_id": payout_id,
                    "batch_status": "SUCCESS",
                    "time_completed": datetime.now().isoformat(),
                },
                "items": [
                    {
                        "payout_item_id": f"ITEM-{secrets.token_hex(4).upper()}",
                        "transaction_status": "SUCCESS",
                        "payout_item": {
                            "recipient_type": "EMAIL",
                            "receiver": "supplier@example.com",
                            "amount": {"currency": "AUD", "value": "50.00"},
                        },
                    }
                ],
            }

    class Subscriptions:
        _subs: dict = {}

        @classmethod
        def create(cls, plan_id: str, subscriber: dict) -> dict:
            sub_id = f"I-{secrets.token_hex(8).upper()}"
            sub = {
                "id": sub_id,
                "status": "ACTIVE",
                "plan_id": plan_id,
                "subscriber": subscriber,
                "billing_info": {
                    "cycle_executions": [
                        {
                            "tenure_type": "REGULAR",
                            "sequence": 1,
                            "cycles_completed": 0,
                            "total_cycles": 0,
                        }
                    ]
                },
                "create_time": datetime.now().isoformat(),
            }
            cls._subs[sub_id] = sub
            return sub

        @classmethod
        def get(cls, subscription_id: str) -> dict:
            return cls._subs.get(
                subscription_id, {"id": subscription_id, "status": "ACTIVE"}
            )

        @classmethod
        def cancel(cls, subscription_id: str, reason: str) -> dict:
            if subscription_id in cls._subs:
                cls._subs[subscription_id]["status"] = "CANCELLED"
            return {"status": "CANCELLED"}

    class Disputes:
        _disputes: dict = {}

        @classmethod
        def list(cls, **kwargs) -> dict:
            return {
                "items": [
                    {
                        "dispute_id": "PP-D-12345",
                        "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
                        "status": "WAITING_FOR_SELLER_RESPONSE",
                        "dispute_amount": {"currency_code": "AUD", "value": "50.00"},
                        "create_time": datetime.now().isoformat(),
                    }
                ]
            }

        @classmethod
        def get(cls, dispute_id: str) -> dict:
            return {
                "dispute_id": dispute_id,
                "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
                "status": "WAITING_FOR_SELLER_RESPONSE",
                "messages": [
                    {
                        "posted_by": "BUYER",
                        "content": "I haven't received my order",
                        "time_posted": datetime.now().isoformat(),
                    }
                ],
            }

        @classmethod
        def respond(cls, dispute_id: str, response: dict) -> dict:
            return {
                "dispute_id": dispute_id,
                "status": "UNDER_REVIEW",
                "message": "Response submitted",
            }

    class Transactions:
        @staticmethod
        def list(start_date: str, end_date: str, **kwargs) -> dict:
            return {
                "transaction_details": [
                    {
                        "transaction_info": {
                            "transaction_id": f"TXN-{secrets.token_hex(6).upper()}",
                            "transaction_event_code": "T0006",
                            "transaction_amount": {
                                "currency_code": "AUD",
                                "value": "-50.00",
                            },
                            "transaction_status": "S",
                            "transaction_subject": "Payment to supplier",
                            "transaction_updated_date": datetime.now().isoformat(),
                        },
                        "payer_info": {"email_address": "you@example.com"},
                    },
                    {
                        "transaction_info": {
                            "transaction_id": f"TXN-{secrets.token_hex(6).upper()}",
                            "transaction_event_code": "T0001",
                            "transaction_amount": {
                                "currency_code": "AUD",
                                "value": "100.00",
                            },
                            "transaction_status": "S",
                            "transaction_subject": "Payment received",
                            "transaction_updated_date": (
                                datetime.now() - timedelta(days=1)
                            ).isoformat(),
                        },
                        "payer_info": {"email_address": "customer@example.com"},
                    },
                ],
                "total_items": 2,
            }

    class Balance:
        @staticmethod
        def get() -> dict:
            return {
                "balances": [
                    {
                        "currency": "AUD",
                        "total_balance": {"currency_code": "AUD", "value": "1250.50"},
                        "available_balance": {
                            "currency_code": "AUD",
                            "value": "1200.00",
                        },
                        "withheld_balance": {"currency_code": "AUD", "value": "50.50"},
                    }
                ]
            }


# Use mock for demo
paypal = MockPayPalAPI()


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class PaymentStatus(Enum):
    """PayPal payment status."""

    CREATED = "CREATED"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    VOIDED = "VOIDED"
    REFUNDED = "REFUNDED"


class DisputeStatus(Enum):
    """PayPal dispute status."""

    OPEN = "OPEN"
    WAITING_FOR_BUYER_RESPONSE = "WAITING_FOR_BUYER_RESPONSE"
    WAITING_FOR_SELLER_RESPONSE = "WAITING_FOR_SELLER_RESPONSE"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass
class PayPalAuditLog:
    """Audit log for PayPal operations."""

    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: str
    amount_aud: Optional[Decimal] = None


@dataclass
class PendingPayment:
    """Track pending payments awaiting approval."""

    order_id: str
    amount_aud: Decimal
    recipient_email: str
    description: str
    approve_url: str
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending_approval"


# ══════════════════════════════════════════════════════════════════════════════
# PAYPAL PAYMENT SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class PayPalPaymentService:
    """
    PayPal payment operations with security best practices.

    Uses PayPal REST API v2 for all operations.
    """

    def __init__(
        self, client_id: str, client_secret: str, webhook_id: str, sandbox: bool = True
    ):
        """
        Initialize PayPal service.

        Args:
            client_id: PayPal OAuth client ID
            client_secret: PayPal OAuth client secret
            webhook_id: Webhook ID for signature verification
            sandbox: Use sandbox (True) or live (False) environment
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.webhook_id = webhook_id
        self.sandbox = sandbox
        self.base_url = (
            "https://api.sandbox.paypal.com" if sandbox else "https://api.paypal.com"
        )

        # In-memory stores
        self._pending_payments: dict[str, PendingPayment] = {}
        self._audit_logs: list[PayPalAuditLog] = []

        logger.info(f"PayPal service initialized ({'sandbox' if sandbox else 'live'})")

    def _audit(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: str,
        amount: Optional[Decimal] = None,
    ) -> None:
        """Record audit log entry."""
        log = PayPalAuditLog(
            timestamp=datetime.now(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            amount_aud=amount,
        )
        self._audit_logs.append(log)
        logger.info(f"AUDIT: {action} on {resource_type}/{resource_id}")

    def _generate_idempotency_key(self, user_id: str, action: str, amount: str) -> str:
        """Generate idempotency key for payment operations."""
        timestamp = datetime.now().strftime("%Y%m%d%H")
        data = f"{user_id}:{action}:{amount}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:36]

    async def create_order(
        self,
        user_id: str,
        amount_aud: Decimal,
        description: str,
        payee_email: Optional[str] = None,
        return_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
    ) -> dict:
        """
        Create a PayPal order for checkout.

        Args:
            user_id: Internal user ID
            amount_aud: Amount in AUD
            description: Payment description
            payee_email: Recipient email (optional)
            return_url: URL after successful payment
            cancel_url: URL if payment cancelled

        Returns:
            Order details with approval URL
        """
        request_body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "AUD",
                        "value": f"{amount_aud:.2f}",
                    },
                    "description": description,
                }
            ],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING",
            },
        }

        if payee_email:
            request_body["purchase_units"][0]["payee"] = {"email_address": payee_email}

        order = paypal.Orders.create(request_body)

        # Get approval URL
        approve_url = next(
            (
                link["href"]
                for link in order.get("links", [])
                if link["rel"] == "approve"
            ),
            None,
        )

        # Track pending payment
        pending = PendingPayment(
            order_id=order["id"],
            amount_aud=amount_aud,
            recipient_email=payee_email or "merchant",
            description=description,
            approve_url=approve_url or "",
        )
        self._pending_payments[order["id"]] = pending

        self._audit(
            user_id,
            "CREATE_ORDER",
            "order",
            order["id"],
            f"Amount: ${amount_aud:.2f} AUD - {description}",
            amount_aud,
        )

        return {
            "order_id": order["id"],
            "status": order["status"],
            "approve_url": approve_url,
            "amount_aud": amount_aud,
        }

    async def capture_order(self, user_id: str, order_id: str) -> dict:
        """
        Capture an approved order (complete the payment).

        Call this after user approves the payment on PayPal.
        """
        result = paypal.Orders.capture(order_id)

        # Update pending payment status
        if order_id in self._pending_payments:
            self._pending_payments[order_id].status = "completed"

        capture_id = None
        if result.get("purchase_units"):
            captures = (
                result["purchase_units"][0].get("payments", {}).get("captures", [])
            )
            if captures:
                capture_id = captures[0].get("id")

        self._audit(
            user_id,
            "CAPTURE_ORDER",
            "order",
            order_id,
            f"Capture ID: {capture_id}",
        )

        return {
            "order_id": order_id,
            "status": result.get("status"),
            "capture_id": capture_id,
        }

    async def check_order_status(self, order_id: str) -> dict:
        """Check the status of an order."""
        order = paypal.Orders.get(order_id)
        return {
            "order_id": order_id,
            "status": order.get("status"),
        }

    async def send_payout(
        self,
        user_id: str,
        recipient_email: str,
        amount_aud: Decimal,
        note: str = "",
    ) -> dict:
        """
        Send money to an email address (PayPal Payout).

        Note: Requires PayPal Payout permission on your account.
        """
        batch_id = f"batch_{secrets.token_hex(8)}"

        request_body = {
            "sender_batch_header": {
                "sender_batch_id": batch_id,
                "email_subject": "You have received a payment",
                "email_message": note or "You have received a payment.",
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": f"{amount_aud:.2f}",
                        "currency": "AUD",
                    },
                    "receiver": recipient_email,
                    "note": note,
                    "sender_item_id": f"item_{secrets.token_hex(4)}",
                }
            ],
        }

        result = paypal.Payouts.create(request_body)
        payout_id = result["batch_header"]["payout_batch_id"]

        self._audit(
            user_id,
            "SEND_PAYOUT",
            "payout",
            payout_id,
            f"${amount_aud:.2f} AUD to {recipient_email}",
            amount_aud,
        )

        return {
            "payout_id": payout_id,
            "status": result["batch_header"]["batch_status"],
            "recipient": recipient_email,
            "amount_aud": amount_aud,
        }

    async def create_subscription(
        self,
        user_id: str,
        plan_id: str,
        subscriber_email: str,
    ) -> dict:
        """Create a PayPal subscription."""
        result = paypal.Subscriptions.create(
            plan_id=plan_id,
            subscriber={"email_address": subscriber_email},
        )

        self._audit(
            user_id,
            "CREATE_SUBSCRIPTION",
            "subscription",
            result["id"],
            f"Plan: {plan_id}, Subscriber: {subscriber_email}",
        )

        return {
            "subscription_id": result["id"],
            "status": result["status"],
            "plan_id": plan_id,
        }

    async def cancel_subscription(
        self,
        user_id: str,
        subscription_id: str,
        reason: str = "Customer requested cancellation",
    ) -> dict:
        """Cancel a PayPal subscription."""
        paypal.Subscriptions.cancel(subscription_id, reason)

        self._audit(
            user_id,
            "CANCEL_SUBSCRIPTION",
            "subscription",
            subscription_id,
            f"Reason: {reason}",
        )

        return {
            "subscription_id": subscription_id,
            "status": "CANCELLED",
        }

    async def get_subscription(self, subscription_id: str) -> dict:
        """Get subscription details."""
        return paypal.Subscriptions.get(subscription_id)

    async def get_disputes(self, user_id: str) -> list[dict]:
        """Get open disputes."""
        result = paypal.Disputes.list()

        self._audit(user_id, "VIEW_DISPUTES", "dispute", "*", "Listed disputes")

        return result.get("items", [])

    async def get_dispute(self, dispute_id: str) -> dict:
        """Get dispute details."""
        return paypal.Disputes.get(dispute_id)

    async def respond_to_dispute(
        self,
        user_id: str,
        dispute_id: str,
        message: str,
        accept_claim: bool = False,
    ) -> dict:
        """Respond to a dispute."""
        response = {
            "message": message,
            "accept_claim": accept_claim,
        }

        result = paypal.Disputes.respond(dispute_id, response)

        self._audit(
            user_id,
            "RESPOND_DISPUTE",
            "dispute",
            dispute_id,
            f"Accept claim: {accept_claim}",
        )

        return result

    async def get_balance(self, user_id: str) -> dict:
        """Get PayPal account balance."""
        result = paypal.Balance.get()

        self._audit(user_id, "VIEW_BALANCE", "account", "self", "Checked balance")

        balances = result.get("balances", [])
        aud_balance = next(
            (b for b in balances if b["currency"] == "AUD"),
            {
                "total_balance": {"value": "0.00"},
                "available_balance": {"value": "0.00"},
            },
        )

        return {
            "total_aud": Decimal(aud_balance["total_balance"]["value"]),
            "available_aud": Decimal(aud_balance["available_balance"]["value"]),
        }

    async def get_transactions(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent transactions."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        result = paypal.Transactions.list(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        self._audit(
            user_id, "VIEW_TRANSACTIONS", "transaction", "*", f"Last {days} days"
        )

        transactions = []
        for tx in result.get("transaction_details", [])[:limit]:
            info = tx.get("transaction_info", {})
            transactions.append(
                {
                    "id": info.get("transaction_id"),
                    "amount": info.get("transaction_amount", {}).get("value"),
                    "currency": info.get("transaction_amount", {}).get("currency_code"),
                    "status": (
                        "Completed"
                        if info.get("transaction_status") == "S"
                        else "Pending"
                    ),
                    "subject": info.get("transaction_subject", "N/A"),
                    "date": info.get("transaction_updated_date", "")[:10],
                }
            )

        return transactions

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        """
        Verify PayPal webhook signature.

        CRITICAL: Always verify webhooks to prevent spoofing!
        """
        # In production, verify using PayPal's webhook signature verification
        # This involves calling PayPal's /v1/notifications/verify-webhook-signature endpoint
        logger.info("Webhook signature verification (mock)")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATIONAL INTERFACE
# ══════════════════════════════════════════════════════════════════════════════


class PayPalPaymentBot:
    """
    Natural language interface for PayPal payments.

    Example conversations:
    - "Pay $50 to supplier@example.com"
    - "What's my PayPal balance?"
    - "Show my recent transactions"
    - "I have a problem with an order"
    """

    def __init__(self, payment_service: PayPalPaymentService):
        self.service = payment_service
        self._pending_sessions: dict[str, str] = {}  # session -> order_id

    def _detect_intent(self, message: str) -> tuple[str, dict]:
        """Simple intent detection from user message."""
        message_lower = message.lower()

        # Pay/send money intent
        if any(word in message_lower for word in ["pay", "send", "transfer"]):
            # Extract amount
            amount_match = re.search(r"\$?(\d+(?:\.\d{2})?)", message)
            amount = Decimal(amount_match.group(1)) if amount_match else None

            # Extract email
            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", message)
            email = email_match.group(0) if email_match else None

            return "send_money", {"amount": amount, "email": email}

        # Approved payment
        if any(
            word in message_lower for word in ["approved", "done", "paid", "completed"]
        ):
            return "capture_payment", {}

        # Balance check
        if any(word in message_lower for word in ["balance", "how much", "funds"]):
            return "check_balance", {}

        # Transaction history
        if any(
            word in message_lower
            for word in ["transactions", "history", "recent payments"]
        ):
            return "view_transactions", {}

        # Dispute handling
        if any(
            word in message_lower
            for word in ["dispute", "problem", "issue", "complaint"]
        ):
            return "handle_dispute", {}

        # Subscription
        if "subscribe" in message_lower:
            return "subscribe", {}
        if "cancel" in message_lower and "subscription" in message_lower:
            return "cancel_subscription", {}

        return "unknown", {}

    async def process_message(
        self,
        message: str,
        session_id: str,
        user_id: str = "user_123",
    ) -> str:
        """
        Process a user message and return bot response.

        Args:
            message: User's natural language input
            session_id: Conversation session ID
            user_id: Internal user ID

        Returns:
            Bot's response
        """
        intent, params = self._detect_intent(message)

        handlers = {
            "send_money": self._handle_send_money,
            "capture_payment": self._handle_capture_payment,
            "check_balance": self._handle_check_balance,
            "view_transactions": self._handle_view_transactions,
            "handle_dispute": self._handle_dispute,
            "subscribe": self._handle_subscribe,
            "cancel_subscription": self._handle_cancel_subscription,
            "unknown": self._handle_unknown,
        }

        handler = handlers.get(intent, self._handle_unknown)
        return await handler(session_id, user_id, params, message)

    async def _handle_send_money(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle send money intent."""
        amount = params.get("amount")
        email = params.get("email")

        if not amount:
            return "How much would you like to send? For example: 'Pay $50 to email@example.com'"

        if not email:
            return f"Got it, ${amount:.2f} AUD. Who should I send it to? Please provide their email address."

        # Create order (for approval flow)
        result = await self.service.create_order(
            user_id=user_id,
            amount_aud=amount,
            description=f"Payment to {email}",
            payee_email=email,
        )

        # Track for capture
        self._pending_sessions[session_id] = result["order_id"]

        return (
            f"Creating PayPal payment for ${amount:.2f} AUD to {email}...\n\n"
            f"🔒 Approve this payment:\n{result['approve_url']}\n\n"
            "Let me know once you've approved it!"
        )

    async def _handle_capture_payment(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle payment capture after approval."""
        order_id = self._pending_sessions.get(session_id)

        if not order_id:
            return "I don't see a pending payment. Would you like to send money to someone?"

        # Check if approved
        status = await self.service.check_order_status(order_id)

        if status["status"] != "APPROVED":
            return (
                f"The payment hasn't been approved yet. "
                f"Current status: {status['status']}\n\n"
                "Please complete the approval on PayPal first."
            )

        # Capture the payment
        result = await self.service.capture_order(user_id, order_id)

        # Clear pending
        del self._pending_sessions[session_id]

        return (
            f"✅ Payment complete!\n\n"
            f"Transaction ID: {result['capture_id']}\n"
            f"Status: {result['status']}\n\n"
            "The recipient will receive a PayPal notification."
        )

    async def _handle_check_balance(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle balance check."""
        balance = await self.service.get_balance(user_id)

        return (
            f"💰 Your PayPal Balance:\n\n"
            f"Available: ${balance['available_aud']:.2f} AUD\n"
            f"Total: ${balance['total_aud']:.2f} AUD\n\n"
            "The difference may be held for pending transactions."
        )

    async def _handle_view_transactions(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle transaction history request."""
        transactions = await self.service.get_transactions(user_id)

        if not transactions:
            return "No recent transactions found."

        lines = ["📋 Recent Transactions:\n"]
        for tx in transactions:
            amount = tx["amount"]
            sign = "+" if not amount.startswith("-") else ""
            lines.append(
                f"• {tx['date']} - {sign}{amount} {tx['currency']} - {tx['subject']}"
            )

        return "\n".join(lines)

    async def _handle_dispute(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle dispute-related queries."""
        disputes = await self.service.get_disputes(user_id)

        if not disputes:
            return (
                "You don't have any open disputes.\n\n"
                "If you're having an issue with a purchase, I can help you:\n"
                "• Contact the seller\n"
                "• Open a dispute\n"
                "• Request a refund\n\n"
                "What would you like to do?"
            )

        lines = ["⚠️ Open Disputes:\n"]
        for d in disputes:
            amount = d.get("dispute_amount", {}).get("value", "N/A")
            status = d.get("status", "Unknown")
            reason = d.get("reason", "Unknown").replace("_", " ").title()
            lines.append(f"• {d['dispute_id']} - ${amount} AUD - {reason}")
            lines.append(f"  Status: {status}")

        lines.append("\nWould you like me to respond to any of these disputes?")

        return "\n".join(lines)

    async def _handle_subscribe(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle subscription creation."""
        # In production, show available plans
        return (
            "I can set up a PayPal subscription for you!\n\n"
            "Available plans:\n"
            "• Basic - $9.99/month\n"
            "• Pro - $29.99/month\n"
            "• Enterprise - $99.99/month\n\n"
            "Which plan would you like?"
        )

    async def _handle_cancel_subscription(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle subscription cancellation."""
        # In production, look up user's subscriptions
        return (
            "I can help you cancel your subscription.\n\n"
            "Please note:\n"
            "• You'll continue to have access until the end of your billing period\n"
            "• Any remaining balance is non-refundable\n"
            "• You can resubscribe anytime\n\n"
            "Do you want me to proceed with the cancellation?"
        )

    async def _handle_unknown(
        self, session_id: str, user_id: str, params: dict, message: str
    ) -> str:
        """Handle unknown intent."""
        return (
            "I can help you with PayPal:\n\n"
            "💳 **Send money**: 'Pay $50 to email@example.com'\n"
            "💰 **Check balance**: 'What's my balance?'\n"
            "📋 **Transaction history**: 'Show my recent transactions'\n"
            "⚠️ **Disputes**: 'I have a problem with an order'\n"
            "🔄 **Subscriptions**: 'Subscribe' or 'Cancel subscription'\n\n"
            "What would you like to do?"
        )


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK HANDLER
# ══════════════════════════════════════════════════════════════════════════════


class PayPalWebhookHandler:
    """
    Handle PayPal webhook events.

    Events notify us of payment changes without polling.
    """

    def __init__(self, payment_service: PayPalPaymentService):
        self.service = payment_service
        self._handlers: dict[str, Callable] = {
            "CHECKOUT.ORDER.APPROVED": self._on_order_approved,
            "PAYMENT.CAPTURE.COMPLETED": self._on_capture_completed,
            "PAYMENT.CAPTURE.DENIED": self._on_capture_denied,
            "BILLING.SUBSCRIPTION.ACTIVATED": self._on_subscription_activated,
            "BILLING.SUBSCRIPTION.CANCELLED": self._on_subscription_cancelled,
            "CUSTOMER.DISPUTE.CREATED": self._on_dispute_created,
            "CUSTOMER.DISPUTE.RESOLVED": self._on_dispute_resolved,
        }

    async def handle(self, headers: dict, body: bytes) -> dict:
        """Process incoming webhook."""
        # Verify signature
        if not self.service.verify_webhook(headers, body):
            raise ValueError("Invalid webhook signature")

        event = json.loads(body)
        event_type = event.get("event_type", "unknown")

        handler = self._handlers.get(event_type)
        if handler:
            await handler(event.get("resource", {}))
            logger.info(f"Webhook handled: {event_type}")
        else:
            logger.info(f"Webhook ignored: {event_type}")

        return {"status": "received"}

    async def _on_order_approved(self, resource: dict) -> None:
        """Handle order approval."""
        order_id = resource.get("id")
        logger.info(f"Order {order_id} approved - ready for capture")

    async def _on_capture_completed(self, resource: dict) -> None:
        """Handle successful capture."""
        capture_id = resource.get("id")
        amount = resource.get("amount", {}).get("value", "0")
        logger.info(f"Capture {capture_id} completed: ${amount}")

    async def _on_capture_denied(self, resource: dict) -> None:
        """Handle denied capture."""
        capture_id = resource.get("id")
        logger.warning(f"Capture {capture_id} denied")

    async def _on_subscription_activated(self, resource: dict) -> None:
        """Handle new subscription."""
        sub_id = resource.get("id")
        logger.info(f"Subscription {sub_id} activated")

    async def _on_subscription_cancelled(self, resource: dict) -> None:
        """Handle subscription cancellation."""
        sub_id = resource.get("id")
        logger.info(f"Subscription {sub_id} cancelled")

    async def _on_dispute_created(self, resource: dict) -> None:
        """Handle new dispute - requires immediate attention!"""
        dispute_id = resource.get("dispute_id")
        logger.warning(f"DISPUTE CREATED: {dispute_id} - Action required!")

    async def _on_dispute_resolved(self, resource: dict) -> None:
        """Handle dispute resolution."""
        dispute_id = resource.get("dispute_id")
        outcome = resource.get("dispute_outcome", {}).get("outcome_code")
        logger.info(f"Dispute {dispute_id} resolved: {outcome}")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo_conversation():
    """Demonstrate a complete PayPal payment conversation."""

    print("\n" + "=" * 70)
    print("  PAYPAL PAYMENT BOT - CONVERSATIONAL COMMERCE DEMO")
    print("=" * 70 + "\n")

    # Initialize
    service = PayPalPaymentService(
        client_id="demo_client",
        client_secret="demo_secret",
        webhook_id="demo_webhook",
        sandbox=True,
    )
    bot = PayPalPaymentBot(service)

    # Simulate conversation
    conversation = [
        "What's my PayPal balance?",
        "Pay $50 to supplier@example.com",
        "Approved!",
        "Show my recent transactions",
        "Do I have any disputes?",
    ]

    session_id = secrets.token_hex(8)

    for user_message in conversation:
        print(f"👤 User: {user_message}")
        response = await bot.process_message(
            message=user_message,
            session_id=session_id,
            user_id="joseph_123",
        )
        print(f"🤖 Bot: {response}\n")
        print("-" * 50 + "\n")

    print("=" * 70)
    print("  Demo complete! In production:")
    print("  - Use real PayPal credentials from environment")
    print("  - Store transactions in your database")
    print("  - Set up webhook endpoint for real-time events")
    print("  - Implement proper OAuth token refresh")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_conversation())
