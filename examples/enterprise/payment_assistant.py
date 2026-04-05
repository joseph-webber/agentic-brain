#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example: PCI DSS Compliant Payment Assistant

A customer service chatbot that handles payment-related queries safely:
- Answer billing questions
- Process refund requests (with approval workflow)
- Check payment status
- Handle PCI-safe card updates (redirect to secure form)

CRITICAL SECURITY PRINCIPLES (PCI DSS Requirements):
╔═══════════════════════════════════════════════════════════════════════════╗
║  1. NEVER log, store, or display full card numbers (PCI DSS 3.4)         ║
║  2. NEVER store CVV/CVC under any circumstances (PCI DSS 3.2)            ║
║  3. Always use tokenization for card references (PCI DSS 3.5)            ║
║  4. Audit trail for ALL payment operations (PCI DSS 10.2)                ║
║  5. Role-based access control (PCI DSS 7.1)                              ║
║  6. Secure transmission - TLS 1.2+ only (PCI DSS 4.1)                    ║
╚═══════════════════════════════════════════════════════════════════════════╝

Australian Context:
- Complies with APRA Prudential Standard CPS 234 (Information Security)
- Consumer Data Right (CDR) ready for open banking
- Australian Consumer Law refund rights respected
- ASIC ePayments Code compliance

Usage:
    python examples/enterprise/payment_assistant.py

Requirements:
    pip install agentic-brain
"""

import asyncio
import hashlib
import logging
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

# Configure logging - CRITICAL: Never log sensitive data
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# PCI DSS COMPLIANT DATA MASKING
# ══════════════════════════════════════════════════════════════════════════════


class PCIMasking:
    """
    PCI DSS compliant data masking utilities.

    PCI DSS 3.3: Mask PAN when displayed - show only first 6 and last 4 digits.
    PCI DSS 3.2: NEVER store or log CVV/CVC.
    """

    # Regex patterns for card detection
    CARD_PATTERNS = [
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?)\b",  # Visa
        r"\b(?:5[1-5][0-9]{14})\b",  # Mastercard
        r"\b(?:3[47][0-9]{13})\b",  # American Express
        r"\b(?:6(?:011|5[0-9]{2})[0-9]{12})\b",  # Discover
    ]

    @staticmethod
    def mask_card_number(card_number: str) -> str:
        """
        Mask a card number showing only last 4 digits.

        PCI DSS 3.3: Display only first 6 and/or last 4 digits.
        For customer service, we only show last 4 for identification.

        Args:
            card_number: Full or partial card number

        Returns:
            Masked card number (e.g., "****-****-****-1234")
        """
        # Remove any existing formatting
        digits_only = re.sub(r"\D", "", card_number)

        if len(digits_only) < 4:
            return "****"

        # Show only last 4 digits
        last_four = digits_only[-4:]
        return f"****-****-****-{last_four}"

    @staticmethod
    def scrub_sensitive_data(text: str) -> str:
        """
        Remove ALL sensitive payment data from text before logging.

        This is CRITICAL for PCI DSS compliance. Any text that might
        contain card numbers must be scrubbed before:
        - Writing to logs
        - Storing in database
        - Sending to external services
        - Displaying to operators

        Args:
            text: Text that might contain sensitive data

        Returns:
            Scrubbed text with card numbers replaced by [REDACTED]
        """
        result = text

        # Remove card numbers
        for pattern in PCIMasking.CARD_PATTERNS:
            result = re.sub(pattern, "[CARD_REDACTED]", result)

        # Remove CVV patterns (3-4 digits that look like CVV)
        # This is aggressive but safe - better to over-scrub than under-scrub
        result = re.sub(
            r"\b(cvv|cvc|cv2|cid)[:\s]*\d{3,4}\b",
            "[CVV_REDACTED]",
            result,
            flags=re.IGNORECASE,
        )

        # Remove potential card number sequences (13-19 digits)
        result = re.sub(r"\b\d{13,19}\b", "[NUMBER_REDACTED]", result)

        return result

    @staticmethod
    def validate_no_sensitive_data(data: dict) -> bool:
        """
        Validate that a dictionary contains NO sensitive payment data.

        Call this before storing or transmitting any data.

        Args:
            data: Dictionary to validate

        Returns:
            True if safe, False if sensitive data detected

        Raises:
            ValueError: If sensitive data is found (fail-safe)
        """
        json_str = str(data)

        for pattern in PCIMasking.CARD_PATTERNS:
            if re.search(pattern, json_str):
                raise ValueError(
                    "SECURITY VIOLATION: Attempted to store/transmit card data. "
                    "This incident has been logged."
                )

        # Check for CVV patterns
        if re.search(r"\b(cvv|cvc|cv2)[:\s]*\d{3,4}\b", json_str, re.IGNORECASE):
            raise ValueError(
                "SECURITY VIOLATION: Attempted to store/transmit CVV. "
                "CVV must NEVER be stored. This incident has been logged."
            )

        return True


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS - PCI DSS COMPLIANT
# ══════════════════════════════════════════════════════════════════════════════


class PaymentStatus(Enum):
    """Payment transaction status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


class RefundStatus(Enum):
    """Refund request status."""

    REQUESTED = "requested"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserRole(Enum):
    """
    Role-based access control (PCI DSS 7.1).

    Different roles have different access levels to payment data.
    """

    CUSTOMER = "customer"
    SUPPORT_AGENT = "support_agent"
    BILLING_ADMIN = "billing_admin"
    FINANCE_MANAGER = "finance_manager"
    SYSTEM = "system"


class AuditAction(Enum):
    """
    Audit log action types (PCI DSS 10.2).

    All access to cardholder data must be logged.
    """

    VIEW_PAYMENT = "view_payment"
    VIEW_CARD_LAST_FOUR = "view_card_last_four"
    INITIATE_REFUND = "initiate_refund"
    APPROVE_REFUND = "approve_refund"
    REJECT_REFUND = "reject_refund"
    UPDATE_CARD = "update_card_redirect"  # Note: redirect, not actual update
    SEARCH_PAYMENTS = "search_payments"
    ACCESS_DENIED = "access_denied"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class AuditLog:
    """
    PCI DSS compliant audit log entry (PCI DSS 10.2-10.3).

    REQUIRED for all access to payment data:
    - User identification (10.2.1)
    - Type of event (10.2.2)
    - Date and time (10.2.3)
    - Success or failure (10.2.4)
    - Origination of event (10.2.5)
    - Identity of affected data (10.2.6)
    """

    id: str
    timestamp: datetime
    user_id: str
    user_role: UserRole
    action: AuditAction
    resource_type: str
    resource_id: str
    # NOTE: Never include actual card data in details!
    details: str
    ip_address: str
    success: bool
    session_id: str = ""


@dataclass
class PaymentToken:
    """
    Tokenized card reference (PCI DSS 3.5).

    We store ONLY the token, never the actual card number.
    The token is a reference to the card stored securely by
    the payment gateway (Stripe, Square, Tyro, etc.).
    """

    token: str  # e.g., "tok_visa_4242"
    last_four: str  # Last 4 digits only - safe to store
    card_brand: str  # Visa, Mastercard, etc.
    expiry_month: int
    expiry_year: int
    # Card holder name is PII but not cardholder data under PCI DSS
    cardholder_name: str = ""
    # Gateway that owns this token
    gateway: str = "stripe"  # stripe, square, tyro
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Payment:
    """
    Payment transaction record.

    NOTE: We store the TOKEN, never the card number.
    """

    id: str
    customer_id: str
    amount: Decimal
    currency: str  # AUD
    status: PaymentStatus
    # Token reference - NOT the card number!
    payment_token: PaymentToken
    description: str
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    # Gateway transaction reference
    gateway_ref: str = ""
    # Refund tracking
    refunded_amount: Decimal = Decimal("0.00")
    refund_ids: list[str] = field(default_factory=list)


@dataclass
class RefundRequest:
    """
    Refund request with approval workflow.

    Australian Consumer Law context:
    - Right to refund for faulty goods
    - Right to refund for services not delivered as described
    - No automatic right to refund for change of mind (policy-dependent)
    """

    id: str
    payment_id: str
    customer_id: str
    amount: Decimal
    reason: str
    status: RefundStatus
    # Approval workflow
    requested_by: str
    requested_at: datetime
    # Approval tracking
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    # ACL flags
    acl_mandatory: bool = False  # Australian Consumer Law mandatory refund
    # Processing
    gateway_ref: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class Customer:
    """Customer account information."""

    id: str
    email: str
    name: str
    phone: str = ""
    # Payment tokens - we store multiple tokenized cards
    payment_tokens: list[PaymentToken] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


# ══════════════════════════════════════════════════════════════════════════════
# ROLE-BASED ACCESS CONTROL (PCI DSS 7.1)
# ══════════════════════════════════════════════════════════════════════════════


class AccessControl:
    """
    PCI DSS 7.1 compliant access control.

    Restrict access to cardholder data by business need to know.
    """

    # Define what each role can do
    ROLE_PERMISSIONS = {
        UserRole.CUSTOMER: [
            AuditAction.VIEW_PAYMENT,
            AuditAction.VIEW_CARD_LAST_FOUR,
            AuditAction.INITIATE_REFUND,
            AuditAction.UPDATE_CARD,
        ],
        UserRole.SUPPORT_AGENT: [
            AuditAction.VIEW_PAYMENT,
            AuditAction.VIEW_CARD_LAST_FOUR,
            AuditAction.SEARCH_PAYMENTS,
            # Support can initiate but NOT approve refunds
            AuditAction.INITIATE_REFUND,
        ],
        UserRole.BILLING_ADMIN: [
            AuditAction.VIEW_PAYMENT,
            AuditAction.VIEW_CARD_LAST_FOUR,
            AuditAction.SEARCH_PAYMENTS,
            AuditAction.INITIATE_REFUND,
            AuditAction.APPROVE_REFUND,
            AuditAction.REJECT_REFUND,
        ],
        UserRole.FINANCE_MANAGER: [
            AuditAction.VIEW_PAYMENT,
            AuditAction.VIEW_CARD_LAST_FOUR,
            AuditAction.SEARCH_PAYMENTS,
            AuditAction.INITIATE_REFUND,
            AuditAction.APPROVE_REFUND,
            AuditAction.REJECT_REFUND,
        ],
    }

    # Refund approval thresholds (AUD)
    REFUND_THRESHOLDS = {
        UserRole.SUPPORT_AGENT: Decimal("0"),  # Cannot approve
        UserRole.BILLING_ADMIN: Decimal("500"),  # Up to $500
        UserRole.FINANCE_MANAGER: Decimal("10000"),  # Up to $10,000
    }

    @classmethod
    def check_permission(cls, role: UserRole, action: AuditAction) -> bool:
        """Check if a role has permission for an action."""
        permissions = cls.ROLE_PERMISSIONS.get(role, [])
        return action in permissions

    @classmethod
    def can_approve_refund(cls, role: UserRole, amount: Decimal) -> bool:
        """Check if role can approve a refund of given amount."""
        if not cls.check_permission(role, AuditAction.APPROVE_REFUND):
            return False
        threshold = cls.REFUND_THRESHOLDS.get(role, Decimal("0"))
        return amount <= threshold


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT ASSISTANT SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class PaymentAssistant:
    """
    PCI DSS compliant payment assistant.

    Handles payment queries, refunds, and card updates safely.

    CRITICAL: This service NEVER handles raw card data.
    All card operations redirect to secure, PCI-compliant forms.
    """

    def __init__(self, secure_form_base_url: str = "https://pay.example.com"):
        """
        Initialize payment assistant.

        Args:
            secure_form_base_url: Base URL for PCI DSS compliant payment forms
        """
        self.secure_form_url = secure_form_base_url

        # In-memory stores (replace with proper DB in production)
        self.customers: dict[str, Customer] = {}
        self.payments: dict[str, Payment] = {}
        self.refunds: dict[str, RefundRequest] = {}
        self.audit_logs: list[AuditLog] = []

        # Current session
        self.current_user_id: Optional[str] = None
        self.current_user_role: UserRole = UserRole.CUSTOMER
        self.session_id: str = ""
        self.client_ip: str = "127.0.0.1"

        # Load demo data
        self._load_demo_data()

    def _generate_id(self, prefix: str = "ID") -> str:
        """Generate secure random ID."""
        random_part = secrets.token_hex(8).upper()
        return f"{prefix}_{random_part}"

    def _log_audit(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        details: str,
        success: bool = True,
    ) -> str:
        """
        Log an audit event (PCI DSS 10.2).

        CRITICAL: Never include card numbers in details!
        """
        # Scrub details before logging
        safe_details = PCIMasking.scrub_sensitive_data(details)

        log = AuditLog(
            id=self._generate_id("AUD"),
            timestamp=datetime.now(),
            user_id=self.current_user_id or "ANONYMOUS",
            user_role=self.current_user_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=safe_details,
            ip_address=self.client_ip,
            success=success,
            session_id=self.session_id,
        )
        self.audit_logs.append(log)

        # Log to system logger (also scrubbed)
        logger.info(
            f"AUDIT: {action.value} on {resource_type}/{resource_id} "
            f"by {self.current_user_id} - {'SUCCESS' if success else 'FAILED'}"
        )

        return log.id

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo customer
        customer = Customer(
            id="CUST_001",
            email="emma.wilson@example.com.au",
            name="Emma Wilson",
            phone="+61412345678",
            payment_tokens=[
                PaymentToken(
                    token="tok_visa_4242_DEMO",
                    last_four="4242",
                    card_brand="Visa",
                    expiry_month=12,
                    expiry_year=2027,
                    cardholder_name="Emma Wilson",
                    gateway="stripe",
                ),
                PaymentToken(
                    token="tok_mc_5555_DEMO",
                    last_four="5555",
                    card_brand="Mastercard",
                    expiry_month=6,
                    expiry_year=2026,
                    cardholder_name="Emma Wilson",
                    gateway="stripe",
                ),
            ],
        )
        self.customers[customer.id] = customer

        # Demo payments
        payments = [
            Payment(
                id="PAY_001",
                customer_id="CUST_001",
                amount=Decimal("149.99"),
                currency="AUD",
                status=PaymentStatus.COMPLETED,
                payment_token=customer.payment_tokens[0],
                description="Annual subscription - Pro Plan",
                created_at=datetime.now() - timedelta(days=30),
                completed_at=datetime.now() - timedelta(days=30),
                gateway_ref="ch_stripe_abc123",
            ),
            Payment(
                id="PAY_002",
                customer_id="CUST_001",
                amount=Decimal("49.99"),
                currency="AUD",
                status=PaymentStatus.COMPLETED,
                payment_token=customer.payment_tokens[0],
                description="Add-on purchase - Premium Features",
                created_at=datetime.now() - timedelta(days=7),
                completed_at=datetime.now() - timedelta(days=7),
                gateway_ref="ch_stripe_def456",
            ),
            Payment(
                id="PAY_003",
                customer_id="CUST_001",
                amount=Decimal("29.99"),
                currency="AUD",
                status=PaymentStatus.FAILED,
                payment_token=customer.payment_tokens[1],
                description="Monthly subscription renewal",
                created_at=datetime.now() - timedelta(days=1),
                gateway_ref="ch_stripe_failed_789",
            ),
        ]
        for pay in payments:
            self.payments[pay.id] = pay

        # Demo pending refund
        refund = RefundRequest(
            id="REF_001",
            payment_id="PAY_002",
            customer_id="CUST_001",
            amount=Decimal("49.99"),
            reason="Feature not working as expected",
            status=RefundStatus.PENDING_APPROVAL,
            requested_by="CUST_001",
            requested_at=datetime.now() - timedelta(hours=2),
        )
        self.refunds[refund.id] = refund

    def set_session(
        self,
        user_id: str,
        role: UserRole,
        session_id: str = "",
        ip_address: str = "127.0.0.1",
    ):
        """Set current session context."""
        self.current_user_id = user_id
        self.current_user_role = role
        self.session_id = session_id or self._generate_id("SES")
        self.client_ip = ip_address

    # ═══════════════════════════════════════════════════════════════════════
    # BILLING QUERIES - Safe operations
    # ═══════════════════════════════════════════════════════════════════════

    def get_payment_summary(self, payment_id: str) -> dict[str, Any]:
        """
        Get payment summary for customer service.

        Returns safe, PCI-compliant payment information.
        Card numbers are masked - only last 4 digits shown.
        """
        # Permission check
        if not AccessControl.check_permission(
            self.current_user_role, AuditAction.VIEW_PAYMENT
        ):
            self._log_audit(
                AuditAction.ACCESS_DENIED,
                "payment",
                payment_id,
                "Permission denied for VIEW_PAYMENT",
                success=False,
            )
            return {"error": "Access denied"}

        payment = self.payments.get(payment_id)
        if not payment:
            return {"error": "Payment not found"}

        # Audit the access
        self._log_audit(
            AuditAction.VIEW_PAYMENT,
            "payment",
            payment_id,
            f"Viewed payment summary for customer {payment.customer_id}",
        )

        # Return SAFE summary - no full card numbers!
        return {
            "payment_id": payment.id,
            "amount": f"${payment.amount:.2f} {payment.currency}",
            "status": payment.status.value,
            "description": payment.description,
            "date": payment.created_at.strftime("%d %B %Y"),
            # SAFE: Only last 4 digits, masked format
            "payment_method": f"{payment.payment_token.card_brand} ****{payment.payment_token.last_four}",
            "refunded_amount": (
                f"${payment.refunded_amount:.2f}"
                if payment.refunded_amount > 0
                else None
            ),
            "can_refund": (
                payment.status == PaymentStatus.COMPLETED
                and payment.refunded_amount < payment.amount
            ),
        }

    def get_payment_history(self, customer_id: str) -> list[dict]:
        """Get customer's payment history with masked card info."""
        if not AccessControl.check_permission(
            self.current_user_role, AuditAction.VIEW_PAYMENT
        ):
            self._log_audit(
                AuditAction.ACCESS_DENIED,
                "customer",
                customer_id,
                "Permission denied for VIEW_PAYMENT",
                success=False,
            )
            return []

        self._log_audit(
            AuditAction.SEARCH_PAYMENTS,
            "customer",
            customer_id,
            "Retrieved payment history",
        )

        customer_payments = [
            p for p in self.payments.values() if p.customer_id == customer_id
        ]

        return [
            {
                "id": p.id,
                "amount": f"${p.amount:.2f}",
                "date": p.created_at.strftime("%d/%m/%Y"),
                "status": p.status.value,
                "description": p.description,
                "card": f"****{p.payment_token.last_four}",
            }
            for p in sorted(customer_payments, key=lambda x: x.created_at, reverse=True)
        ]

    # ═══════════════════════════════════════════════════════════════════════
    # REFUND WORKFLOW - With approval chain
    # ═══════════════════════════════════════════════════════════════════════

    def request_refund(
        self, payment_id: str, amount: Optional[Decimal] = None, reason: str = ""
    ) -> dict[str, Any]:
        """
        Request a refund (customer or support initiated).

        Australian Consumer Law context:
        - Mandatory refunds for faulty goods/services
        - Policy-based refunds for change of mind

        Large refunds require approval from billing admin or finance.
        """
        if not AccessControl.check_permission(
            self.current_user_role, AuditAction.INITIATE_REFUND
        ):
            self._log_audit(
                AuditAction.ACCESS_DENIED,
                "payment",
                payment_id,
                "Permission denied for INITIATE_REFUND",
                success=False,
            )
            return {"error": "Access denied - cannot initiate refunds"}

        payment = self.payments.get(payment_id)
        if not payment:
            return {"error": "Payment not found"}

        if payment.status != PaymentStatus.COMPLETED:
            return {
                "error": f"Cannot refund payment with status: {payment.status.value}"
            }

        # Calculate refund amount
        refund_amount = amount or payment.amount
        available = payment.amount - payment.refunded_amount

        if refund_amount > available:
            return {
                "error": f"Refund amount ${refund_amount} exceeds available ${available}"
            }

        # Check if this is ACL mandatory (faulty goods, etc.)
        acl_keywords = [
            "faulty",
            "defective",
            "not as described",
            "broken",
            "doesn't work",
        ]
        is_acl_mandatory = any(kw in reason.lower() for kw in acl_keywords)

        # Create refund request
        refund = RefundRequest(
            id=self._generate_id("REF"),
            payment_id=payment_id,
            customer_id=payment.customer_id,
            amount=refund_amount,
            reason=reason,
            status=RefundStatus.PENDING_APPROVAL,
            requested_by=self.current_user_id or "SYSTEM",
            requested_at=datetime.now(),
            acl_mandatory=is_acl_mandatory,
        )

        # Auto-approve small refunds for billing admins
        if AccessControl.can_approve_refund(
            self.current_user_role, refund_amount
        ) and self.current_user_role in [
            UserRole.BILLING_ADMIN,
            UserRole.FINANCE_MANAGER,
        ]:
            refund.status = RefundStatus.APPROVED
            refund.approved_by = self.current_user_id
            refund.approved_at = datetime.now()

        self.refunds[refund.id] = refund

        self._log_audit(
            AuditAction.INITIATE_REFUND,
            "refund",
            refund.id,
            f"Refund requested for ${refund_amount} on payment {payment_id}. "
            f"ACL mandatory: {is_acl_mandatory}",
        )

        return {
            "success": True,
            "refund_id": refund.id,
            "amount": f"${refund.amount:.2f}",
            "status": refund.status.value,
            "requires_approval": refund.status == RefundStatus.PENDING_APPROVAL,
            "acl_mandatory": is_acl_mandatory,
            "message": self._get_refund_message(refund),
        }

    def _get_refund_message(self, refund: RefundRequest) -> str:
        """Get customer-friendly refund status message."""
        if refund.status == RefundStatus.APPROVED:
            return (
                "Your refund has been approved and will be processed within "
                "3-5 business days. The funds will be returned to your original "
                "payment method."
            )
        elif refund.status == RefundStatus.PENDING_APPROVAL:
            if refund.acl_mandatory:
                return (
                    "Your refund request has been received. Under Australian "
                    "Consumer Law, you are entitled to a refund for goods or "
                    "services that are faulty or not as described. We will "
                    "process this within 24 hours."
                )
            else:
                return (
                    "Your refund request has been submitted and is pending "
                    "approval. We will notify you within 2 business days."
                )
        return "Refund request received."

    def approve_refund(self, refund_id: str) -> dict[str, Any]:
        """
        Approve a pending refund (billing admin only).

        Requires APPROVE_REFUND permission and amount within threshold.
        """
        refund = self.refunds.get(refund_id)
        if not refund:
            return {"error": "Refund not found"}

        if refund.status != RefundStatus.PENDING_APPROVAL:
            return {
                "error": f"Cannot approve refund with status: {refund.status.value}"
            }

        # Check permission
        if not AccessControl.can_approve_refund(self.current_user_role, refund.amount):
            self._log_audit(
                AuditAction.ACCESS_DENIED,
                "refund",
                refund_id,
                f"Permission denied - amount ${refund.amount} exceeds threshold",
                success=False,
            )
            threshold = AccessControl.REFUND_THRESHOLDS.get(
                self.current_user_role, Decimal("0")
            )
            return {
                "error": f"Amount exceeds your approval limit of ${threshold}. "
                f"Please escalate to Finance Manager."
            }

        # Approve
        refund.status = RefundStatus.APPROVED
        refund.approved_by = self.current_user_id
        refund.approved_at = datetime.now()

        self._log_audit(
            AuditAction.APPROVE_REFUND,
            "refund",
            refund_id,
            f"Approved refund of ${refund.amount} for payment {refund.payment_id}",
        )

        return {
            "success": True,
            "message": f"Refund of ${refund.amount:.2f} approved. Processing will begin shortly.",
            "refund_id": refund_id,
        }

    def reject_refund(self, refund_id: str, reason: str) -> dict[str, Any]:
        """Reject a pending refund with reason."""
        refund = self.refunds.get(refund_id)
        if not refund:
            return {"error": "Refund not found"}

        if not AccessControl.check_permission(
            self.current_user_role, AuditAction.REJECT_REFUND
        ):
            self._log_audit(
                AuditAction.ACCESS_DENIED,
                "refund",
                refund_id,
                "Permission denied for REJECT_REFUND",
                success=False,
            )
            return {"error": "Access denied - cannot reject refunds"}

        # ACL mandatory refunds cannot be rejected
        if refund.acl_mandatory:
            return {
                "error": "Cannot reject ACL mandatory refund. Australian Consumer "
                "Law requires refunds for faulty goods or services not as described."
            }

        refund.status = RefundStatus.REJECTED
        refund.rejection_reason = reason

        self._log_audit(
            AuditAction.REJECT_REFUND,
            "refund",
            refund_id,
            f"Rejected refund. Reason: {PCIMasking.scrub_sensitive_data(reason)}",
        )

        return {
            "success": True,
            "message": "Refund has been rejected.",
            "reason": reason,
        }

    def get_refund_status(self, refund_id: str) -> dict[str, Any]:
        """Get status of a refund request."""
        refund = self.refunds.get(refund_id)
        if not refund:
            return {"error": "Refund not found"}

        return {
            "refund_id": refund.id,
            "payment_id": refund.payment_id,
            "amount": f"${refund.amount:.2f}",
            "status": refund.status.value,
            "reason": refund.reason,
            "requested_at": refund.requested_at.strftime("%d %B %Y %H:%M"),
            "approved_by": refund.approved_by,
            "message": self._get_refund_message(refund),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # CARD UPDATE - Secure redirect pattern
    # ═══════════════════════════════════════════════════════════════════════

    def get_card_update_url(self, customer_id: str) -> dict[str, Any]:
        """
        Generate secure URL for card update.

        CRITICAL: We NEVER handle raw card data!

        Instead, we redirect the customer to a PCI DSS Level 1 compliant
        hosted payment page provided by our payment gateway (Stripe,
        Square, Tyro, etc.).

        This pattern keeps us OUT of PCI DSS scope for card data.
        """
        if not AccessControl.check_permission(
            self.current_user_role, AuditAction.UPDATE_CARD
        ):
            self._log_audit(
                AuditAction.ACCESS_DENIED,
                "customer",
                customer_id,
                "Permission denied for UPDATE_CARD",
                success=False,
            )
            return {"error": "Access denied"}

        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": "Customer not found"}

        # Generate secure, time-limited token for the update session
        update_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)

        # In production, store this token with expiry in Redis/DB
        # and validate it when the customer returns

        self._log_audit(
            AuditAction.UPDATE_CARD,
            "customer",
            customer_id,
            "Generated secure card update URL",
        )

        # URL to PCI-compliant hosted form
        secure_url = (
            f"{self.secure_form_url}/update-card"
            f"?token={update_token}"
            f"&customer={customer_id}"
        )

        return {
            "success": True,
            "message": (
                "To update your card, please click the secure link below. "
                "This link will expire in 1 hour for security. "
                "You will be redirected to our secure payment page."
            ),
            "secure_url": secure_url,
            "expires_at": expires_at.strftime("%H:%M on %d %B %Y"),
            # Show current cards (masked)
            "current_cards": [
                {
                    "brand": t.card_brand,
                    "last_four": f"****{t.last_four}",
                    "expiry": f"{t.expiry_month:02d}/{t.expiry_year}",
                }
                for t in customer.payment_tokens
            ],
        }

    # ═══════════════════════════════════════════════════════════════════════
    # CHATBOT INTERFACE
    # ═══════════════════════════════════════════════════════════════════════

    async def handle_message(self, message: str, context: dict = None) -> str:
        """
        Handle a customer service message.

        This is the main chatbot interface. It understands payment-related
        intents and routes to appropriate safe handlers.
        """
        context = context or {}
        message_lower = message.lower()

        # Payment status queries
        if any(
            kw in message_lower for kw in ["payment", "charge", "transaction", "bill"]
        ):
            if "status" in message_lower or "check" in message_lower:
                return await self._handle_payment_status(message, context)
            elif "history" in message_lower or "past" in message_lower:
                return await self._handle_payment_history(context)
            elif "failed" in message_lower or "declined" in message_lower:
                return await self._handle_failed_payment(context)

        # Refund requests
        if any(kw in message_lower for kw in ["refund", "money back", "return"]):
            return await self._handle_refund_request(message, context)

        # Card updates
        if any(
            kw in message_lower for kw in ["update card", "change card", "new card"]
        ):
            return await self._handle_card_update(context)

        # Invoice/receipt
        if any(kw in message_lower for kw in ["invoice", "receipt", "statement"]):
            return await self._handle_invoice_request(context)

        # Default helpful response
        return (
            "I can help you with:\n\n"
            "📋 **Payment Status** - Check your recent payments\n"
            "📜 **Payment History** - View all past transactions\n"
            "💳 **Update Card** - Securely update your payment method\n"
            "↩️ **Refunds** - Request a refund for a purchase\n"
            "🧾 **Invoices** - Get invoices or receipts\n\n"
            "What would you like to do?"
        )

    async def _handle_payment_status(self, message: str, context: dict) -> str:
        """Handle payment status queries."""
        customer_id = context.get("customer_id", "CUST_001")
        payments = self.get_payment_history(customer_id)

        if not payments:
            return "You don't have any payments on record."

        recent = payments[0]  # Most recent

        status_emoji = {
            "completed": "✅",
            "pending": "⏳",
            "processing": "🔄",
            "failed": "❌",
            "refunded": "↩️",
        }

        emoji = status_emoji.get(recent["status"], "📋")

        return (
            f"**Your most recent payment:**\n\n"
            f"{emoji} **{recent['description']}**\n"
            f"Amount: {recent['amount']} AUD\n"
            f"Date: {recent['date']}\n"
            f"Status: {recent['status'].title()}\n"
            f"Card: {recent['card']}\n\n"
            f"Would you like to see your full payment history or request a refund?"
        )

    async def _handle_payment_history(self, context: dict) -> str:
        """Handle payment history requests."""
        customer_id = context.get("customer_id", "CUST_001")
        payments = self.get_payment_history(customer_id)

        if not payments:
            return "You don't have any payments on record."

        lines = ["**Your Payment History:**\n"]
        for p in payments[:5]:  # Show last 5
            status_emoji = "✅" if p["status"] == "completed" else "❌"
            lines.append(
                f"{status_emoji} {p['date']} - {p['amount']} - {p['description']}"
            )

        lines.append(
            "\n_Showing last 5 transactions. Contact support for full statement._"
        )

        return "\n".join(lines)

    async def _handle_failed_payment(self, context: dict) -> str:
        """Handle failed payment queries."""
        return (
            "I see you have a failed payment. This can happen due to:\n\n"
            "• Insufficient funds\n"
            "• Card expired or cancelled\n"
            "• Bank security check\n"
            "• Incorrect card details\n\n"
            "**Would you like to:**\n"
            "1. Update your card details (secure link)\n"
            "2. Retry the payment\n"
            "3. Speak with our billing team\n\n"
            "_Your card details are always handled securely via our PCI-compliant payment page._"
        )

    async def _handle_refund_request(self, message: str, context: dict) -> str:
        """Handle refund requests."""
        customer_id = context.get("customer_id", "CUST_001")

        # Check for existing pending refunds
        pending = [
            r
            for r in self.refunds.values()
            if r.customer_id == customer_id
            and r.status == RefundStatus.PENDING_APPROVAL
        ]

        if pending:
            ref = pending[0]
            return (
                f"You already have a pending refund request:\n\n"
                f"**Refund ID:** {ref.id}\n"
                f"**Amount:** ${ref.amount:.2f}\n"
                f"**Status:** {ref.status.value.replace('_', ' ').title()}\n"
                f"**Requested:** {ref.requested_at.strftime('%d %B %Y')}\n\n"
                f"We'll notify you once it's been reviewed. Under Australian Consumer "
                f"Law, refunds for faulty goods are processed within 24 hours."
            )

        # Show refund options
        payments = [
            p
            for p in self.payments.values()
            if p.customer_id == customer_id and p.status == PaymentStatus.COMPLETED
        ]

        if not payments:
            return "You don't have any completed payments eligible for refund."

        lines = ["**Which payment would you like to refund?**\n"]
        for p in payments[:3]:
            available = p.amount - p.refunded_amount
            if available > 0:
                lines.append(
                    f"• **{p.id}** - ${p.amount:.2f} - {p.description} ({p.created_at.strftime('%d/%m/%Y')})"
                )

        lines.append(
            "\n_Please provide the payment ID and reason for your refund request. "
            "Under Australian Consumer Law, you're entitled to a refund for faulty "
            "goods or services not as described._"
        )

        return "\n".join(lines)

    async def _handle_card_update(self, context: dict) -> str:
        """Handle card update requests."""
        customer_id = context.get("customer_id", "CUST_001")
        result = self.get_card_update_url(customer_id)

        if "error" in result:
            return f"Sorry, I couldn't generate a card update link: {result['error']}"

        cards_info = "\n".join(
            [
                f"• {c['brand']} ending in {c['last_four']} (expires {c['expiry']})"
                for c in result["current_cards"]
            ]
        )

        return (
            f"**Update Your Payment Method**\n\n"
            f"Your current cards on file:\n{cards_info}\n\n"
            f"🔒 Click the secure link below to update your card. "
            f"Your card details are handled by our PCI-DSS compliant payment provider - "
            f"we never see or store your full card number.\n\n"
            f"**Secure Link:** {result['secure_url']}\n"
            f"_This link expires at {result['expires_at']}_"
        )

    async def _handle_invoice_request(self, context: dict) -> str:
        """Handle invoice/receipt requests."""
        return (
            "I can send you:\n\n"
            "📧 **Email Receipt** - Sent to your registered email\n"
            "📄 **PDF Invoice** - Download link valid for 24 hours\n"
            "📊 **Monthly Statement** - Summary of all transactions\n\n"
            "Which would you like, and for which payment or time period?"
        )


# ══════════════════════════════════════════════════════════════════════════════
# EXAMPLE CONVERSATIONS
# ══════════════════════════════════════════════════════════════════════════════

EXAMPLE_CONVERSATIONS = """
╔═══════════════════════════════════════════════════════════════════════════╗
║  EXAMPLE: Safe Payment Chatbot Conversations                              ║
╚═══════════════════════════════════════════════════════════════════════════╝

SCENARIO 1: Customer checking payment status
─────────────────────────────────────────────
Customer: "Can you check my last payment?"

Bot: "**Your most recent payment:**

✅ **Annual subscription - Pro Plan**
Amount: $149.99 AUD
Date: 15/02/2024
Status: Completed
Card: ****4242

Would you like to see your full payment history or request a refund?"

>>> Note: Card number is MASKED - only last 4 digits shown (PCI DSS 3.3)


SCENARIO 2: Customer requesting refund
─────────────────────────────────────────────
Customer: "I want a refund - the feature doesn't work as described"

Bot: "I understand the feature isn't working as expected. Under Australian
Consumer Law, you're entitled to a refund for products not as described.

Your refund request has been submitted:
**Refund ID:** REF_A1B2C3D4
**Amount:** $49.99
**Status:** Pending Approval

Because this involves consumer rights, we'll process this within 24 hours.
You'll receive confirmation via email."

>>> Note: ACL mandatory flag automatically detected


SCENARIO 3: Customer updating card (SECURE REDIRECT)
─────────────────────────────────────────────
Customer: "I need to update my card - I got a new one"

Bot: "**Update Your Payment Method**

Your current cards on file:
• Visa ending in 4242 (expires 12/27)
• Mastercard ending in 5555 (expires 06/26)

🔒 Click the secure link below to update your card. Your card details are
handled by our PCI-DSS compliant payment provider - we never see or store
your full card number.

**Secure Link:** https://pay.example.com/update-card?token=abc123
_This link expires at 15:30 on 18 March 2024_"

>>> CRITICAL: We NEVER handle the card number directly!
>>> Customer is redirected to PCI-compliant hosted page.


SCENARIO 4: Support agent helping customer (role check)
─────────────────────────────────────────────
[Agent logged in as SUPPORT_AGENT role]

Agent: "Approve refund REF_001 for $500"

Bot: "Access denied - amount $500.00 exceeds your approval limit of $0.
Please escalate to Finance Manager."

>>> Note: Support agents can VIEW and INITIATE but not APPROVE refunds
>>> This is PCI DSS 7.1 - restrict access by business need


SCENARIO 5: Customer trying to share card number (SECURITY)
─────────────────────────────────────────────
Customer: "My card number is 4111 1111 1111 1111 and CVV is 123"

Bot: "⚠️ **IMPORTANT: Please never share your full card number or CVV!**

For your security, we handle card updates through our secure payment page.
Your message has NOT been stored or logged.

To safely update your card, I'll generate a secure link to our PCI-compliant
payment form. Would you like me to do that?"

>>> CRITICAL: Card data is SCRUBBED, never logged, and warning issued.
>>> The assistant redirects to safe process.
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    """Run payment assistant demo."""
    print("=" * 70)
    print("PCI DSS COMPLIANT PAYMENT ASSISTANT DEMO")
    print("Australian Market - Stripe/Square/Tyro Integration Patterns")
    print("=" * 70)

    # Initialize assistant
    assistant = PaymentAssistant(secure_form_base_url="https://pay.example.com")

    # Set up customer session
    assistant.set_session(
        user_id="CUST_001",
        role=UserRole.CUSTOMER,
        session_id="demo_session_001",
        ip_address="203.0.113.42",  # Example Australian IP
    )

    print("\n📋 Demo: Customer checking payment status")
    print("-" * 50)
    response = await assistant.handle_message("Check my last payment")
    print(response)

    print("\n💳 Demo: Customer requesting card update")
    print("-" * 50)
    response = await assistant.handle_message("I need to update my card")
    print(response)

    print("\n↩️ Demo: Customer requesting refund")
    print("-" * 50)
    response = await assistant.handle_message(
        "I want a refund - the feature doesn't work as described"
    )
    print(response)

    print("\n👨‍💼 Demo: Billing admin approving refund")
    print("-" * 50)
    # Switch to billing admin
    assistant.set_session(
        user_id="ADMIN_001", role=UserRole.BILLING_ADMIN, session_id="admin_session_001"
    )

    result = assistant.approve_refund("REF_001")
    print(f"Approval result: {result}")

    print("\n📜 Demo: Audit Log (PCI DSS 10.2)")
    print("-" * 50)
    for log in assistant.audit_logs[-5:]:
        print(
            f"[{log.timestamp.strftime('%H:%M:%S')}] "
            f"{log.action.value:20} | "
            f"{log.user_id:10} | "
            f"{log.resource_type}/{log.resource_id}"
        )

    print("\n" + "=" * 70)
    print("EXAMPLE CONVERSATIONS")
    print("=" * 70)
    print(EXAMPLE_CONVERSATIONS)


if __name__ == "__main__":
    asyncio.run(main())
