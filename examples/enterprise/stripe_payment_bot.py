#!/usr/bin/env python3
"""
Example: Stripe-Powered Conversational Commerce Chatbot

A complete Stripe payment integration via natural conversation:
- Create checkout sessions (PCI compliant - card handled by Stripe)
- Manage subscriptions ("upgrade", "downgrade", "cancel")
- Query invoices ("show my invoices", "download receipt")
- Process refunds with approval workflow
- Handle webhooks for payment events
- Generate customer portal links

Example Conversation:
╔══════════════════════════════════════════════════════════════════════════════╗
║  User: "I'd like to buy the Pro plan"                                        ║
║  Bot:  "Great! The Pro plan is $29/month. Creating secure checkout..."      ║
║  Bot:  "Here's your secure checkout: https://checkout.stripe.com/pay/xxx"   ║
║  User: "Done! I paid"                                                        ║
║  Bot:  "Payment confirmed! Welcome to Pro. Invoice: INV-2026-0042"          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Security:
- PCI DSS Level 1 compliant (Stripe handles all card data)
- Webhook signature verification (prevent spoofing)
- Idempotency keys (prevent double charges)
- No card data ever touches our servers

Australian Context:
- AUD as default currency
- GST (10%) handling for Australian customers
- Australian Consumer Law refund rights
- ASIC ePayments Code compliance

Usage:
    python examples/enterprise/stripe_payment_bot.py

Requirements:
    pip install agentic-brain stripe
    export STRIPE_SECRET_KEY=sk_test_xxx
    export STRIPE_WEBHOOK_SECRET=whsec_xxx
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Callable

# Configure logging - NEVER log card data
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [STRIPE_BOT] %(message)s"
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# STRIPE SDK MOCK (Replace with real stripe import in production)
# ══════════════════════════════════════════════════════════════════════════════


class MockStripe:
    """
    Mock Stripe SDK for demonstration.
    In production, replace with: import stripe
    """

    class checkout:
        class Session:
            @staticmethod
            def create(**kwargs) -> dict:
                session_id = f"cs_{secrets.token_hex(16)}"
                return {
                    "id": session_id,
                    "url": f"https://checkout.stripe.com/pay/{session_id}",
                    "payment_status": "unpaid",
                    "customer": kwargs.get("customer"),
                    "mode": kwargs.get("mode", "payment"),
                    "success_url": kwargs.get("success_url"),
                    "cancel_url": kwargs.get("cancel_url"),
                    "metadata": kwargs.get("metadata", {}),
                }

            @staticmethod
            def retrieve(session_id: str) -> dict:
                return {
                    "id": session_id,
                    "payment_status": "paid",
                    "payment_intent": f"pi_{secrets.token_hex(16)}",
                    "customer": f"cus_{secrets.token_hex(8)}",
                    "amount_total": 2900,
                    "currency": "aud",
                }

    class Subscription:
        @staticmethod
        def create(**kwargs) -> dict:
            return {
                "id": f"sub_{secrets.token_hex(16)}",
                "customer": kwargs.get("customer"),
                "status": "active",
                "current_period_end": int(
                    (datetime.now() + timedelta(days=30)).timestamp()
                ),
                "items": {
                    "data": [
                        {"price": {"id": kwargs.get("items", [{}])[0].get("price")}}
                    ]
                },
            }

        @staticmethod
        def retrieve(sub_id: str) -> dict:
            return {
                "id": sub_id,
                "status": "active",
                "current_period_end": int(
                    (datetime.now() + timedelta(days=30)).timestamp()
                ),
                "plan": {"id": "price_pro", "amount": 2900, "interval": "month"},
            }

        @staticmethod
        def modify(sub_id: str, **kwargs) -> dict:
            return {
                "id": sub_id,
                "status": "active",
                "items": {
                    "data": [
                        {"price": {"id": kwargs.get("items", [{}])[0].get("price")}}
                    ]
                },
            }

        @staticmethod
        def delete(sub_id: str) -> dict:
            return {"id": sub_id, "status": "canceled"}

        @staticmethod
        def list(**kwargs) -> dict:
            return {"data": []}

    class Invoice:
        @staticmethod
        def list(**kwargs) -> dict:
            return {
                "data": [
                    {
                        "id": "in_abc123",
                        "number": "INV-2026-0042",
                        "amount_paid": 2900,
                        "currency": "aud",
                        "status": "paid",
                        "created": int(datetime.now().timestamp()),
                        "invoice_pdf": "https://stripe.com/invoice/in_abc123/pdf",
                        "hosted_invoice_url": "https://invoice.stripe.com/i/in_abc123",
                    }
                ]
            }

        @staticmethod
        def retrieve(invoice_id: str) -> dict:
            return {
                "id": invoice_id,
                "number": "INV-2026-0042",
                "amount_paid": 2900,
                "currency": "aud",
                "status": "paid",
                "invoice_pdf": f"https://stripe.com/invoice/{invoice_id}/pdf",
            }

    class Refund:
        @staticmethod
        def create(**kwargs) -> dict:
            return {
                "id": f"re_{secrets.token_hex(16)}",
                "amount": kwargs.get("amount"),
                "status": "succeeded",
                "payment_intent": kwargs.get("payment_intent"),
                "reason": kwargs.get("reason", "requested_by_customer"),
            }

    class Customer:
        @staticmethod
        def create(**kwargs) -> dict:
            return {
                "id": f"cus_{secrets.token_hex(8)}",
                "email": kwargs.get("email"),
                "name": kwargs.get("name"),
                "metadata": kwargs.get("metadata", {}),
            }

        @staticmethod
        def retrieve(customer_id: str) -> dict:
            return {"id": customer_id, "email": "customer@example.com"}

    class billing_portal:
        class Session:
            @staticmethod
            def create(**kwargs) -> dict:
                return {
                    "id": f"bps_{secrets.token_hex(8)}",
                    "url": "https://billing.stripe.com/session/xxx",
                    "customer": kwargs.get("customer"),
                }

    class Webhook:
        @staticmethod
        def construct_event(
            payload: bytes, sig_header: str, webhook_secret: str
        ) -> dict:
            # In production, this verifies the webhook signature
            return json.loads(payload)


# Use mock for demo, real stripe in production
try:
    import stripe
except ImportError:
    stripe = MockStripe()


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class PlanTier(Enum):
    """Available subscription plans."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class Plan:
    """Subscription plan details."""

    tier: PlanTier
    name: str
    price_monthly_aud: int  # In cents
    price_yearly_aud: int  # In cents
    stripe_price_id_monthly: str
    stripe_price_id_yearly: str
    features: list[str]

    @property
    def price_display(self) -> str:
        """Human-readable price."""
        return f"${self.price_monthly_aud / 100:.0f}/month"


# Plan catalog
PLANS = {
    PlanTier.FREE: Plan(
        tier=PlanTier.FREE,
        name="Free",
        price_monthly_aud=0,
        price_yearly_aud=0,
        stripe_price_id_monthly="",
        stripe_price_id_yearly="",
        features=["5 projects", "Basic support", "Community access"],
    ),
    PlanTier.STARTER: Plan(
        tier=PlanTier.STARTER,
        name="Starter",
        price_monthly_aud=1900,  # $19 AUD
        price_yearly_aud=19000,  # $190 AUD (save $38)
        stripe_price_id_monthly="price_starter_monthly",
        stripe_price_id_yearly="price_starter_yearly",
        features=["25 projects", "Email support", "API access", "Analytics"],
    ),
    PlanTier.PRO: Plan(
        tier=PlanTier.PRO,
        name="Pro",
        price_monthly_aud=2900,  # $29 AUD
        price_yearly_aud=29000,  # $290 AUD (save $58)
        stripe_price_id_monthly="price_pro_monthly",
        stripe_price_id_yearly="price_pro_yearly",
        features=[
            "Unlimited projects",
            "Priority support",
            "Advanced API",
            "Team features",
        ],
    ),
    PlanTier.ENTERPRISE: Plan(
        tier=PlanTier.ENTERPRISE,
        name="Enterprise",
        price_monthly_aud=9900,  # $99 AUD
        price_yearly_aud=99000,  # $990 AUD
        stripe_price_id_monthly="price_enterprise_monthly",
        stripe_price_id_yearly="price_enterprise_yearly",
        features=[
            "Everything in Pro",
            "SSO/SAML",
            "Dedicated support",
            "SLA guarantee",
            "Custom integrations",
        ],
    ),
}


@dataclass
class RefundRequest:
    """Refund request with approval workflow."""

    id: str
    customer_id: str
    payment_intent: str
    amount_cents: int
    reason: str
    status: str = "pending_approval"
    requested_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


@dataclass
class PaymentAuditLog:
    """Audit log for payment operations (PCI DSS 10.2)."""

    timestamp: datetime
    customer_id: str
    action: str
    resource_type: str
    resource_id: str
    details: str  # Never include card data!
    ip_address: str
    user_agent: str


# ══════════════════════════════════════════════════════════════════════════════
# STRIPE PAYMENT SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class StripePaymentService:
    """
    Stripe payment operations with PCI DSS compliance.

    All card handling is done by Stripe - we never see card data.
    """

    def __init__(self, api_key: str, webhook_secret: str):
        """
        Initialize Stripe service.

        Args:
            api_key: Stripe secret key (sk_test_xxx or sk_live_xxx)
            webhook_secret: Webhook signing secret (whsec_xxx)
        """
        self.api_key = api_key
        self.webhook_secret = webhook_secret

        # Configure stripe SDK
        if hasattr(stripe, "api_key"):
            stripe.api_key = api_key

        # In-memory stores (use database in production)
        self._customers: dict[str, dict] = {}
        self._refund_requests: dict[str, RefundRequest] = {}
        self._audit_logs: list[PaymentAuditLog] = []

        logger.info("Stripe payment service initialized")

    def _audit(
        self,
        customer_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: str,
        ip: str = "127.0.0.1",
    ) -> None:
        """Record audit log entry (PCI DSS 10.2)."""
        log = PaymentAuditLog(
            timestamp=datetime.now(),
            customer_id=customer_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip,
            user_agent="stripe-payment-bot/1.0",
        )
        self._audit_logs.append(log)
        logger.info(
            f"AUDIT: {action} on {resource_type}/{resource_id} by {customer_id}"
        )

    def _generate_idempotency_key(self, customer_id: str, action: str) -> str:
        """Generate idempotency key to prevent duplicate operations."""
        timestamp = datetime.now().strftime("%Y%m%d%H")
        data = f"{customer_id}:{action}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    async def get_or_create_customer(self, email: str, name: str = "") -> dict:
        """Get existing customer or create new one."""
        # Check cache
        for cust in self._customers.values():
            if cust.get("email") == email:
                return cust

        # Create new customer in Stripe
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"source": "stripe_payment_bot"},
        )

        self._customers[customer["id"]] = customer
        self._audit(
            customer["id"],
            "CREATE_CUSTOMER",
            "customer",
            customer["id"],
            f"Created for {email}",
        )

        return customer

    async def create_checkout_session(
        self,
        customer_id: str,
        plan: Plan,
        billing_period: str = "monthly",
        success_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
    ) -> dict:
        """
        Create a Stripe Checkout Session for subscription.

        PCI Compliant: Customer enters card details on Stripe's hosted page.
        """
        price_id = (
            plan.stripe_price_id_monthly
            if billing_period == "monthly"
            else plan.stripe_price_id_yearly
        )

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "plan_tier": plan.tier.value,
                "billing_period": billing_period,
            },
            # Australian tax handling
            automatic_tax={"enabled": True},
            # Idempotency prevents duplicate charges
            idempotency_key=self._generate_idempotency_key(
                customer_id, f"checkout_{plan.tier.value}"
            ),
        )

        self._audit(
            customer_id,
            "CREATE_CHECKOUT",
            "checkout_session",
            session["id"],
            f"Plan: {plan.name}, Period: {billing_period}",
        )

        return session

    async def create_one_time_payment(
        self,
        customer_id: str,
        amount_cents: int,
        description: str,
        success_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
    ) -> dict:
        """Create a one-time payment checkout session."""
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "aud",
                        "unit_amount": amount_cents,
                        "product_data": {"name": description},
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            automatic_tax={"enabled": True},
            idempotency_key=self._generate_idempotency_key(
                customer_id, f"payment_{amount_cents}"
            ),
        )

        self._audit(
            customer_id,
            "CREATE_PAYMENT",
            "checkout_session",
            session["id"],
            f"Amount: ${amount_cents/100:.2f} AUD - {description}",
        )

        return session

    async def check_session_status(self, session_id: str) -> dict:
        """Check if a checkout session has been completed."""
        session = stripe.checkout.Session.retrieve(session_id)
        return {
            "id": session["id"],
            "paid": session.get("payment_status") == "paid",
            "customer": session.get("customer"),
            "amount": session.get("amount_total"),
        }

    async def get_subscriptions(self, customer_id: str) -> list[dict]:
        """Get all subscriptions for a customer."""
        result = stripe.Subscription.list(customer=customer_id)
        self._audit(
            customer_id,
            "VIEW_SUBSCRIPTIONS",
            "subscription",
            "*",
            "Listed subscriptions",
        )
        return result.get("data", [])

    async def upgrade_subscription(self, subscription_id: str, new_plan: Plan) -> dict:
        """Upgrade a subscription to a higher tier."""
        subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{"price": new_plan.stripe_price_id_monthly}],
            proration_behavior="create_prorations",  # Charge difference immediately
        )

        self._audit(
            subscription.get("customer", "unknown"),
            "UPGRADE_SUBSCRIPTION",
            "subscription",
            subscription_id,
            f"Upgraded to {new_plan.name}",
        )

        return subscription

    async def downgrade_subscription(
        self, subscription_id: str, new_plan: Plan
    ) -> dict:
        """Downgrade a subscription to a lower tier."""
        subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{"price": new_plan.stripe_price_id_monthly}],
            proration_behavior="none",  # Apply at next billing cycle
        )

        self._audit(
            subscription.get("customer", "unknown"),
            "DOWNGRADE_SUBSCRIPTION",
            "subscription",
            subscription_id,
            f"Downgraded to {new_plan.name}",
        )

        return subscription

    async def cancel_subscription(
        self, subscription_id: str, immediately: bool = False
    ) -> dict:
        """Cancel a subscription."""
        if immediately:
            result = stripe.Subscription.delete(subscription_id)
        else:
            result = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )

        self._audit(
            result.get("customer", "unknown"),
            "CANCEL_SUBSCRIPTION",
            "subscription",
            subscription_id,
            "Cancelled immediately" if immediately else "Scheduled for end of period",
        )

        return result

    async def get_invoices(self, customer_id: str, limit: int = 10) -> list[dict]:
        """Get customer's invoices."""
        result = stripe.Invoice.list(customer=customer_id, limit=limit)
        self._audit(
            customer_id, "VIEW_INVOICES", "invoice", "*", f"Retrieved {limit} invoices"
        )
        return result.get("data", [])

    async def get_invoice_pdf(self, invoice_id: str, customer_id: str) -> str:
        """Get PDF download URL for an invoice."""
        invoice = stripe.Invoice.retrieve(invoice_id)
        self._audit(
            customer_id,
            "DOWNLOAD_INVOICE",
            "invoice",
            invoice_id,
            "PDF download requested",
        )
        return invoice.get("invoice_pdf", "")

    async def request_refund(
        self,
        customer_id: str,
        payment_intent: str,
        amount_cents: int,
        reason: str,
    ) -> RefundRequest:
        """
        Request a refund (requires approval for amounts > $50).

        Australian Consumer Law: Customers have refund rights for faulty products/services.
        """
        request_id = f"rfnd_req_{secrets.token_hex(8)}"

        # Auto-approve small refunds (< $50 AUD)
        auto_approve = amount_cents < 5000

        request = RefundRequest(
            id=request_id,
            customer_id=customer_id,
            payment_intent=payment_intent,
            amount_cents=amount_cents,
            reason=reason,
            status="approved" if auto_approve else "pending_approval",
        )

        self._refund_requests[request_id] = request

        self._audit(
            customer_id,
            "REQUEST_REFUND",
            "refund",
            request_id,
            f"Amount: ${amount_cents/100:.2f} - Reason: {reason} - Auto-approved: {auto_approve}",
        )

        # Process auto-approved refunds immediately
        if auto_approve:
            await self._process_refund(request)

        return request

    async def _process_refund(self, request: RefundRequest) -> dict:
        """Actually process the refund through Stripe."""
        refund = stripe.Refund.create(
            payment_intent=request.payment_intent,
            amount=request.amount_cents,
            reason="requested_by_customer",
            metadata={"request_id": request.id, "original_reason": request.reason},
        )

        request.status = "completed"

        self._audit(
            request.customer_id,
            "PROCESS_REFUND",
            "refund",
            refund["id"],
            f"Refunded ${request.amount_cents/100:.2f} AUD",
        )

        return refund

    async def approve_refund(self, request_id: str, approver_id: str) -> RefundRequest:
        """Approve a pending refund request."""
        request = self._refund_requests.get(request_id)
        if not request:
            raise ValueError(f"Refund request {request_id} not found")

        request.status = "approved"
        request.approved_by = approver_id
        request.approved_at = datetime.now()

        # Process the refund
        await self._process_refund(request)

        self._audit(
            request.customer_id,
            "APPROVE_REFUND",
            "refund",
            request_id,
            f"Approved by {approver_id}",
        )

        return request

    async def create_customer_portal_session(
        self,
        customer_id: str,
        return_url: str = "https://example.com/account",
    ) -> dict:
        """Create a billing portal session for self-service."""
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        self._audit(
            customer_id,
            "CREATE_PORTAL_SESSION",
            "billing_portal",
            session["id"],
            "Customer portal session created",
        )

        return session

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict:
        """
        Verify webhook signature and parse event.

        CRITICAL: Always verify webhooks to prevent spoofing attacks!
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            logger.info(f"Webhook verified: {event.get('type', 'unknown')}")
            return event
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            raise ValueError("Invalid webhook signature")


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATIONAL INTERFACE
# ══════════════════════════════════════════════════════════════════════════════


class StripePaymentBot:
    """
    Natural language interface for Stripe payments.

    Example conversations:
    - "I want to upgrade to Pro"
    - "Show me my invoices"
    - "Cancel my subscription"
    - "I need a refund for my last payment"
    """

    def __init__(self, payment_service: StripePaymentService):
        self.service = payment_service
        self._customer_cache: dict[str, str] = {}  # session_id -> customer_id

    def _detect_intent(self, message: str) -> tuple[str, dict]:
        """
        Simple intent detection from user message.

        In production, use NLU model (Rasa, Dialogflow, etc.)
        """
        message_lower = message.lower()

        # Purchase/subscribe intents
        if any(
            word in message_lower for word in ["buy", "subscribe", "purchase", "get"]
        ):
            for tier in PlanTier:
                if tier.value in message_lower or tier.name.lower() in message_lower:
                    return "subscribe", {"plan": tier}
            return "subscribe", {"plan": None}

        # Upgrade intent
        if "upgrade" in message_lower:
            for tier in PlanTier:
                if tier.value in message_lower or tier.name.lower() in message_lower:
                    return "upgrade", {"plan": tier}
            return "upgrade", {"plan": None}

        # Downgrade intent
        if "downgrade" in message_lower:
            for tier in PlanTier:
                if tier.value in message_lower or tier.name.lower() in message_lower:
                    return "downgrade", {"plan": tier}
            return "downgrade", {"plan": None}

        # Cancel intent
        if any(
            word in message_lower for word in ["cancel", "stop", "end subscription"]
        ):
            return "cancel", {}

        # Invoice intents
        if any(word in message_lower for word in ["invoice", "receipt", "billing"]):
            if "download" in message_lower or "pdf" in message_lower:
                return "download_invoice", {}
            return "view_invoices", {}

        # Refund intent
        if any(word in message_lower for word in ["refund", "money back", "return"]):
            return "refund", {}

        # Payment status
        if any(word in message_lower for word in ["paid", "confirmed", "done"]):
            return "check_payment", {}

        # Account/portal
        if any(
            word in message_lower
            for word in ["account", "settings", "manage", "portal"]
        ):
            return "portal", {}

        # Plan info
        if any(
            word in message_lower for word in ["plans", "pricing", "prices", "options"]
        ):
            return "show_plans", {}

        return "unknown", {}

    async def process_message(
        self,
        message: str,
        session_id: str,
        customer_email: str = "customer@example.com",
    ) -> str:
        """
        Process a user message and return bot response.

        Args:
            message: User's natural language input
            session_id: Conversation session ID
            customer_email: Customer's email for Stripe

        Returns:
            Bot's response
        """
        intent, params = self._detect_intent(message)

        # Get or create customer
        customer = await self.service.get_or_create_customer(customer_email)
        customer_id = customer["id"]
        self._customer_cache[session_id] = customer_id

        # Route to handler
        handlers = {
            "subscribe": self._handle_subscribe,
            "upgrade": self._handle_upgrade,
            "downgrade": self._handle_downgrade,
            "cancel": self._handle_cancel,
            "view_invoices": self._handle_view_invoices,
            "download_invoice": self._handle_download_invoice,
            "refund": self._handle_refund,
            "check_payment": self._handle_check_payment,
            "portal": self._handle_portal,
            "show_plans": self._handle_show_plans,
            "unknown": self._handle_unknown,
        }

        handler = handlers.get(intent, self._handle_unknown)
        return await handler(customer_id, params, message)

    async def _handle_subscribe(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Handle subscription purchase intent."""
        plan_tier = params.get("plan")

        if not plan_tier:
            return (
                "I'd be happy to help you subscribe! We have these plans:\n\n"
                + self._format_plans()
                + "\n\nWhich plan would you like?"
            )

        plan = PLANS.get(plan_tier)
        if not plan or plan_tier == PlanTier.FREE:
            return "The Free plan doesn't require payment. You're all set!"

        session = await self.service.create_checkout_session(customer_id, plan)

        return (
            f"Great choice! The {plan.name} plan is {plan.price_display}.\n\n"
            f"🔒 Here's your secure checkout link:\n{session['url']}\n\n"
            "Your card details are handled securely by Stripe - we never see them.\n"
            "Let me know once you've completed the payment!"
        )

    async def _handle_upgrade(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Handle subscription upgrade intent."""
        plan_tier = params.get("plan")

        # Get current subscription
        subs = await self.service.get_subscriptions(customer_id)
        if not subs:
            return "You don't have an active subscription. Would you like to subscribe?"

        if not plan_tier:
            return "Which plan would you like to upgrade to?\n\n" + self._format_plans()

        plan = PLANS.get(plan_tier)
        if not plan:
            return (
                "I couldn't find that plan. Here are the available options:\n\n"
                + self._format_plans()
            )

        sub = await self.service.upgrade_subscription(subs[0]["id"], plan)

        return (
            f"✅ You've been upgraded to {plan.name}!\n\n"
            f"The price difference has been prorated and will appear on your next invoice.\n"
            f"New features are available immediately. Enjoy!"
        )

    async def _handle_downgrade(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Handle subscription downgrade intent."""
        plan_tier = params.get("plan")

        subs = await self.service.get_subscriptions(customer_id)
        if not subs:
            return "You don't have an active subscription to downgrade."

        if not plan_tier:
            return "Which plan would you like to change to?\n\n" + self._format_plans()

        plan = PLANS.get(plan_tier)
        if not plan:
            return "I couldn't find that plan."

        sub = await self.service.downgrade_subscription(subs[0]["id"], plan)

        return (
            f"Your subscription will change to {plan.name} at the end of your current billing period.\n"
            "You'll continue to have access to all current features until then."
        )

    async def _handle_cancel(self, customer_id: str, params: dict, message: str) -> str:
        """Handle subscription cancellation."""
        subs = await self.service.get_subscriptions(customer_id)
        if not subs:
            return "You don't have an active subscription to cancel."

        await self.service.cancel_subscription(subs[0]["id"])

        return (
            "I've scheduled your subscription for cancellation at the end of the billing period.\n\n"
            "You'll continue to have full access until then. "
            "If you change your mind, just let me know!"
        )

    async def _handle_view_invoices(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Show customer's invoices."""
        invoices = await self.service.get_invoices(customer_id)

        if not invoices:
            return "You don't have any invoices yet."

        lines = ["Here are your recent invoices:\n"]
        for inv in invoices[:5]:
            amount = inv.get("amount_paid", 0) / 100
            date = datetime.fromtimestamp(inv.get("created", 0)).strftime("%d %b %Y")
            status = inv.get("status", "unknown")
            lines.append(
                f"• {inv.get('number', 'N/A')} - ${amount:.2f} AUD - {date} ({status})"
            )

        lines.append("\nSay 'download invoice' to get a PDF receipt.")
        return "\n".join(lines)

    async def _handle_download_invoice(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Get invoice PDF download link."""
        invoices = await self.service.get_invoices(customer_id, limit=1)

        if not invoices:
            return "You don't have any invoices to download."

        latest = invoices[0]
        pdf_url = await self.service.get_invoice_pdf(latest["id"], customer_id)

        return (
            f"Here's your invoice PDF:\n{pdf_url}\n\n"
            "This link is secure and will expire in 24 hours."
        )

    async def _handle_refund(self, customer_id: str, params: dict, message: str) -> str:
        """Handle refund request."""
        # In production, get actual payment details
        # For demo, create a mock request
        request = await self.service.request_refund(
            customer_id=customer_id,
            payment_intent="pi_mock_123",
            amount_cents=2900,
            reason="Customer requested via chat",
        )

        if request.status == "approved" or request.status == "completed":
            return (
                f"✅ Your refund of ${request.amount_cents/100:.2f} AUD has been processed.\n\n"
                f"Refund ID: {request.id}\n"
                "Please allow 5-10 business days for the funds to appear in your account."
            )
        else:
            return (
                f"Your refund request for ${request.amount_cents/100:.2f} AUD has been submitted.\n\n"
                f"Request ID: {request.id}\n"
                "Our team will review it within 24 hours. We'll email you once it's processed."
            )

    async def _handle_check_payment(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Check if payment was completed."""
        # In production, check actual session
        return (
            "✅ Payment confirmed! Thank you for your purchase.\n\n"
            "Your account has been upgraded and all features are now available.\n"
            "Invoice: INV-2026-0042 (we've emailed you a copy)"
        )

    async def _handle_portal(self, customer_id: str, params: dict, message: str) -> str:
        """Create self-service portal link."""
        session = await self.service.create_customer_portal_session(customer_id)

        return (
            "Here's your account management portal:\n"
            f"{session['url']}\n\n"
            "From there you can:\n"
            "• Update payment method\n"
            "• View billing history\n"
            "• Change subscription\n"
            "• Download invoices"
        )

    async def _handle_show_plans(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Show available plans."""
        return "Here are our available plans:\n\n" + self._format_plans()

    async def _handle_unknown(
        self, customer_id: str, params: dict, message: str
    ) -> str:
        """Handle unknown intent."""
        return (
            "I can help you with:\n"
            "• **Subscribe** to a plan\n"
            "• **Upgrade** or **downgrade** your subscription\n"
            "• **Cancel** your subscription\n"
            "• View your **invoices** and download receipts\n"
            "• Request a **refund**\n"
            "• Access your **account** settings\n\n"
            "What would you like to do?"
        )

    def _format_plans(self) -> str:
        """Format plans for display."""
        lines = []
        for tier, plan in PLANS.items():
            if tier == PlanTier.FREE:
                lines.append(f"• **{plan.name}** - Free forever")
            else:
                lines.append(f"• **{plan.name}** - {plan.price_display}")
            for feature in plan.features[:3]:
                lines.append(f"  ✓ {feature}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK HANDLER
# ══════════════════════════════════════════════════════════════════════════════


class StripeWebhookHandler:
    """
    Handle Stripe webhook events.

    Webhooks notify us of payment events without polling.
    CRITICAL: Always verify webhook signatures!
    """

    def __init__(self, payment_service: StripePaymentService):
        self.service = payment_service
        self._handlers: dict[str, Callable] = {
            "checkout.session.completed": self._on_checkout_completed,
            "invoice.paid": self._on_invoice_paid,
            "invoice.payment_failed": self._on_payment_failed,
            "customer.subscription.updated": self._on_subscription_updated,
            "customer.subscription.deleted": self._on_subscription_deleted,
            "charge.refunded": self._on_refund_completed,
        }

    async def handle(self, payload: bytes, sig_header: str) -> dict:
        """
        Process incoming webhook.

        Args:
            payload: Raw request body
            sig_header: Stripe-Signature header

        Returns:
            Response to send back to Stripe
        """
        # Verify signature (CRITICAL!)
        event = self.service.verify_webhook(payload, sig_header)

        event_type = event.get("type", "unknown")
        handler = self._handlers.get(event_type)

        if handler:
            await handler(event["data"]["object"])
            logger.info(f"Webhook handled: {event_type}")
        else:
            logger.info(f"Webhook ignored (no handler): {event_type}")

        return {"received": True}

    async def _on_checkout_completed(self, session: dict) -> None:
        """Handle successful checkout."""
        customer_id = session.get("customer")
        logger.info(f"Checkout completed for customer {customer_id}")
        # Update your database, send welcome email, etc.

    async def _on_invoice_paid(self, invoice: dict) -> None:
        """Handle paid invoice."""
        logger.info(f"Invoice {invoice.get('number')} paid")
        # Record payment, extend subscription, etc.

    async def _on_payment_failed(self, invoice: dict) -> None:
        """Handle failed payment."""
        customer_id = invoice.get("customer")
        logger.warning(f"Payment failed for customer {customer_id}")
        # Send dunning email, notify support, etc.

    async def _on_subscription_updated(self, subscription: dict) -> None:
        """Handle subscription change."""
        logger.info(f"Subscription {subscription.get('id')} updated")

    async def _on_subscription_deleted(self, subscription: dict) -> None:
        """Handle subscription cancellation."""
        logger.info(f"Subscription {subscription.get('id')} cancelled")
        # Revoke access, send feedback survey, etc.

    async def _on_refund_completed(self, charge: dict) -> None:
        """Handle completed refund."""
        refund_amount = charge.get("amount_refunded", 0) / 100
        logger.info(f"Refund of ${refund_amount:.2f} completed")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo_conversation():
    """Demonstrate a complete payment conversation."""

    print("\n" + "=" * 70)
    print("  STRIPE PAYMENT BOT - CONVERSATIONAL COMMERCE DEMO")
    print("=" * 70 + "\n")

    # Initialize (in production, use real keys from secrets)
    service = StripePaymentService(
        api_key="sk_test_demo",
        webhook_secret="whsec_demo",
    )
    bot = StripePaymentBot(service)

    # Simulate conversation
    conversation = [
        "What plans do you have?",
        "I'd like to buy the Pro plan",
        "Done! I paid",
        "Show me my invoices",
        "I need to access my account settings",
        "Actually, I want to cancel my subscription",
    ]

    session_id = secrets.token_hex(8)

    for user_message in conversation:
        print(f"👤 User: {user_message}")
        response = await bot.process_message(
            message=user_message,
            session_id=session_id,
            customer_email="joseph@example.com",
        )
        print(f"🤖 Bot: {response}\n")
        print("-" * 50 + "\n")

    print("=" * 70)
    print("  Demo complete! In production:")
    print("  - Use real Stripe keys from environment variables")
    print("  - Store customer data in your database")
    print("  - Set up webhook endpoint for real-time events")
    print("  - Use proper NLU for intent detection")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_conversation())
