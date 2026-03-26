#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example: Australian Payment Bot

Australia-specific payment handling with compliance for local regulations:
- NPP/PayID integration (New Payments Platform)
- BPAY reference generation and validation
- BSB/Account number validation
- Australian Consumer Law compliance
- GST handling and BAS reporting

AUSTRALIAN PAYMENT LANDSCAPE:
╔═══════════════════════════════════════════════════════════════════════════╗
║  PAYMENT METHOD        SETTLEMENT      USE CASE                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  NPP/PayID            Instant 24/7     Person-to-person, invoices        ║
║  BPAY                 Next business    Bill payments                      ║
║  Direct Debit         1-3 days         Subscriptions, utilities          ║
║  Card (Visa/MC)       Same day         Retail, online                    ║
║  Bank Transfer        1-3 days         Large amounts, business           ║
╚═══════════════════════════════════════════════════════════════════════════╝

REGULATORY COMPLIANCE:
╔═══════════════════════════════════════════════════════════════════════════╗
║  REGULATION                           REQUIREMENT                         ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  PCI DSS 3.4                         Card number tokenization            ║
║  APRA CPS 234                        Information security                ║
║  Privacy Act 1988                    Australian Privacy Principles       ║
║  Australian Consumer Law             Refund rights, cooling-off          ║
║  AML/CTF Act                         Transaction monitoring              ║
║  GST Act 1999                        10% GST on taxable supplies         ║
║  ASIC ePayments Code                 Consumer protections                ║
╚═══════════════════════════════════════════════════════════════════════════╝

Usage:
    python examples/enterprise/australian_payment_bot.py

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
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Optional

# Configure logging - CRITICAL: Never log sensitive data
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# AUSTRALIAN BSB VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


class BSBValidator:
    """
    Australian BSB (Bank-State-Branch) number validator.

    BSB Format: XXX-XXX (6 digits)
    - First 2 digits: Bank code
    - Third digit: State code
    - Last 3 digits: Branch code

    WHY THIS MATTERS:
    Invalid BSB = failed payment = customer frustration.
    Validation prevents 80% of payment errors.
    """

    # Australian bank codes (first 2 digits of BSB)
    BANK_CODES = {
        "01": "ANZ Bank",
        "03": "Westpac",
        "06": "Commonwealth Bank",
        "08": "NAB",
        "10": "BankSA",
        "11": "St.George Bank",
        "12": "Bank of Queensland",
        "14": "Rabobank",
        "15": "Town & Country Bank",
        "17": "Macquarie Bank",
        "18": "Macquarie Bank",
        "19": "Bank of Melbourne",
        "21": "JP Morgan",
        "22": "BNP Paribas",
        "23": "Bank of America",
        "24": "Citibank",
        "25": "BNP Paribas",
        "26": "Bankwest",
        "30": "Bankwest",
        "31": "Bankwest",
        "32": "Bendigo Bank",
        "33": "St.George Bank",
        "34": "HSBC",
        "35": "HSBC",
        "40": "HSBC",
        "41": "HSBC",
        "42": "HSBC",
        "48": "Macquarie Bank",
        "51": "Commonwealth Bank",
        "52": "Commonwealth Bank",
        "53": "Commonwealth Bank",
        "54": "Commonwealth Bank",
        "55": "Commonwealth Bank",
        "56": "Commonwealth Bank",
        "57": "Commonwealth Bank",
        "58": "Commonwealth Bank",
        "59": "Commonwealth Bank",
        "63": "Rabobank",
        "64": "Rabobank",
        "65": "Rabobank",
        "73": "Westpac",
        "76": "Commonwealth Bank",
        "80": "Suncorp-Metway",
        "81": "Suncorp-Metway",
        "91": "Heritage Bank",
        "92": "Adelaide Bank",
        "93": "CBA",
    }

    # State codes (third digit of BSB)
    STATE_CODES = {
        "2": "NSW/ACT",
        "3": "VIC",
        "4": "QLD",
        "5": "SA/NT",
        "6": "WA",
        "7": "TAS",
        "0": "National",
        "1": "National",
    }

    @classmethod
    def validate(cls, bsb: str) -> tuple[bool, str]:
        """
        Validate an Australian BSB number.

        Args:
            bsb: BSB number (with or without hyphen)

        Returns:
            Tuple of (is_valid, message)

        WHY WE VALIDATE:
        - Prevents payment failures at the bank
        - Catches typos before money is sent
        - Improves user experience
        """
        # Remove hyphen and whitespace
        bsb_clean = re.sub(r"[\s-]", "", bsb)

        # Must be exactly 6 digits
        if not re.match(r"^\d{6}$", bsb_clean):
            return False, "BSB must be 6 digits (e.g., 063-123 or 063123)"

        bank_code = bsb_clean[:2]
        state_code = bsb_clean[2]

        # Check bank code
        if bank_code not in cls.BANK_CODES:
            # Don't reject - could be a new/unknown bank
            logger.warning(f"Unknown bank code: {bank_code}")

        # Check state code (informational)
        state = cls.STATE_CODES.get(state_code, "Unknown state")
        bank_name = cls.BANK_CODES.get(bank_code, "Unknown bank")

        return True, f"{bank_name} ({state})"

    @classmethod
    def format(cls, bsb: str) -> str:
        """Format BSB as XXX-XXX."""
        bsb_clean = re.sub(r"[\s-]", "", bsb)
        if len(bsb_clean) == 6:
            return f"{bsb_clean[:3]}-{bsb_clean[3:]}"
        return bsb

    @classmethod
    def mask_account(cls, account: str) -> str:
        """
        Mask account number showing only last 4 digits.

        WHY WE MASK:
        PCI DSS principles apply to ALL sensitive numbers.
        Account numbers should be treated like card numbers.
        """
        digits = re.sub(r"\D", "", account)
        if len(digits) <= 4:
            return "****"
        return f"****{digits[-4:]}"


# ══════════════════════════════════════════════════════════════════════════════
# BPAY REFERENCE HANDLING
# ══════════════════════════════════════════════════════════════════════════════


class BPAYValidator:
    """
    BPAY reference number generator and validator.

    BPAY STRUCTURE:
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  COMPONENT              LENGTH      DESCRIPTION                          ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Biller Code           4-6 digits   Identifies the business/biller       ║
    ║  Customer Reference    Variable     Unique per customer/invoice          ║
    ║  Check Digit           1 digit      Validates reference integrity        ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    WHY BPAY:
    - Most trusted bill payment method in Australia
    - Next business day settlement
    - Automatic reconciliation
    - Consumer protection through BPAY Scheme
    """

    @staticmethod
    def generate_reference(
        customer_id: str, invoice_number: str, prefix: str = ""
    ) -> str:
        """
        Generate a BPAY customer reference number.

        Reference format: [prefix][customer_id][invoice][check_digit]

        Args:
            customer_id: Your customer identifier
            invoice_number: Invoice or account number
            prefix: Optional business prefix

        Returns:
            Valid BPAY reference number with check digit

        WHY CHECK DIGITS:
        - Prevents 90% of data entry errors
        - BPAY validates before processing
        - Invalid references = rejected payments
        """
        # Create base reference (max 20 digits total)
        base = f"{prefix}{customer_id}{invoice_number}"
        base_digits = re.sub(r"\D", "", base)[:19]  # Leave room for check digit

        # Calculate MOD-10 check digit (Luhn algorithm)
        check = BPAYValidator._calculate_check_digit(base_digits)

        return f"{base_digits}{check}"

    @staticmethod
    def _calculate_check_digit(number: str) -> str:
        """
        Calculate MOD-10 (Luhn) check digit.

        LUHN ALGORITHM:
        1. Double every second digit from right
        2. Subtract 9 from any doubled digit > 9
        3. Sum all digits
        4. Check digit = (10 - (sum % 10)) % 10
        """
        digits = [int(d) for d in number]

        # Double every second digit from right (starting at index -2)
        for i in range(len(digits) - 2, -1, -2):
            digits[i] *= 2
            if digits[i] > 9:
                digits[i] -= 9

        total = sum(digits)
        check = (10 - (total % 10)) % 10

        return str(check)

    @staticmethod
    def validate_reference(reference: str) -> tuple[bool, str]:
        """
        Validate a BPAY reference number using MOD-10.

        Returns:
            Tuple of (is_valid, message)
        """
        digits = re.sub(r"\D", "", reference)

        if len(digits) < 2:
            return False, "Reference too short"

        if len(digits) > 20:
            return False, "Reference too long (max 20 digits)"

        # Validate MOD-10 check digit
        expected = BPAYValidator._calculate_check_digit(digits[:-1])
        actual = digits[-1]

        if expected != actual:
            return False, "Invalid check digit - please verify reference"

        return True, "Valid BPAY reference"


# ══════════════════════════════════════════════════════════════════════════════
# NPP / PAYID INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


class PayIDType(Enum):
    """
    PayID identifier types for NPP (New Payments Platform).

    PayID provides memorable identifiers instead of BSB/Account:
    - Instant payments 24/7/365
    - Confirmation of payee name before sending
    - Fraud protection through name matching
    """

    EMAIL = "email"
    PHONE = "phone"
    ABN = "abn"
    ACN = "acn"
    ORG_ID = "org_id"


@dataclass
class PayIDRegistration:
    """
    PayID registration for receiving NPP payments.

    SECURITY NOTE:
    PayID lookup returns the registered name, allowing payers
    to confirm they're paying the right person/business.
    This is a critical anti-fraud feature.
    """

    payid_type: PayIDType
    identifier: str
    display_name: str
    bsb: str
    account_number: str
    created_at: datetime = field(default_factory=datetime.now)
    is_portable: bool = True  # Can transfer to another bank

    def mask_account(self) -> str:
        """Return masked account details for display."""
        return f"BSB: {self.bsb}, Account: ****{self.account_number[-4:]}"


class NPPPaymentHandler:
    """
    New Payments Platform (NPP) payment handler.

    NPP FEATURES:
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  FEATURE              BENEFIT                                            ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Instant Settlement   24/7/365 real-time payments                        ║
    ║  PayID                Memorable aliases (email, phone, ABN)              ║
    ║  Confirmation of      See payee name before confirming                   ║
    ║  Payee (CoP)                                                             ║
    ║  Rich Data            280 characters vs 18 for BECS                      ║
    ║  Request to Pay       Send payment requests to payers                    ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    WHY NPP:
    - Faster than BPAY (instant vs next day)
    - Better than bank transfer (PayID vs BSB/Acc)
    - Modern infrastructure for digital economy
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize NPP handler.

        WHY SECRETS MODULE:
        - secrets.token_urlsafe() is cryptographically secure
        - os.urandom() based, not predictable
        - Required for PCI DSS compliant token generation
        """
        self.api_key = api_key or os.environ.get("NPP_API_KEY")
        self._payid_registry: dict[str, PayIDRegistration] = {}

    def validate_payid(self, payid: str, payid_type: PayIDType) -> tuple[bool, str]:
        """
        Validate PayID format.

        Args:
            payid: The PayID identifier
            payid_type: Type of PayID

        Returns:
            Tuple of (is_valid, message)
        """
        if payid_type == PayIDType.EMAIL:
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", payid):
                return False, "Invalid email format"
            return True, "Valid email PayID"

        elif payid_type == PayIDType.PHONE:
            # Australian mobile: 04XX XXX XXX or +614XX XXX XXX
            phone_clean = re.sub(r"[\s-]", "", payid)
            if not re.match(r"^(?:\+?614|04)\d{8}$", phone_clean):
                return False, "Australian mobile required (04XX XXX XXX)"
            return True, "Valid phone PayID"

        elif payid_type == PayIDType.ABN:
            return self._validate_abn(payid)

        elif payid_type == PayIDType.ACN:
            return self._validate_acn(payid)

        return False, "Unknown PayID type"

    def _validate_abn(self, abn: str) -> tuple[bool, str]:
        """
        Validate Australian Business Number (ABN).

        ABN is 11 digits with a check digit algorithm.

        ALGORITHM:
        1. Subtract 1 from first digit
        2. Multiply each digit by weighting factor
        3. Sum all products
        4. Valid if sum % 89 == 0
        """
        abn_clean = re.sub(r"\D", "", abn)

        if len(abn_clean) != 11:
            return False, "ABN must be 11 digits"

        # ABN weighting factors
        weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]

        digits = [int(d) for d in abn_clean]
        digits[0] -= 1  # Subtract 1 from first digit

        total = sum(d * w for d, w in zip(digits, weights))

        if total % 89 != 0:
            return False, "Invalid ABN - check digit failed"

        return True, "Valid ABN"

    def _validate_acn(self, acn: str) -> tuple[bool, str]:
        """
        Validate Australian Company Number (ACN).

        ACN is 9 digits with MOD-10 check digit.
        """
        acn_clean = re.sub(r"\D", "", acn)

        if len(acn_clean) != 9:
            return False, "ACN must be 9 digits"

        # ACN weighting factors
        weights = [8, 7, 6, 5, 4, 3, 2, 1]

        digits = [int(d) for d in acn_clean]

        # Calculate weighted sum (first 8 digits)
        total = sum(d * w for d, w in zip(digits[:8], weights))

        # Calculate check digit
        remainder = total % 10
        check = (10 - remainder) % 10

        if check != digits[8]:
            return False, "Invalid ACN - check digit failed"

        return True, "Valid ACN"

    async def lookup_payid(self, payid: str, payid_type: PayIDType) -> dict[str, Any]:
        """
        Look up PayID to get registered name (Confirmation of Payee).

        WHY THIS IS CRITICAL:
        Confirmation of Payee prevents misdirected payments.
        User sees "Paying: JOHN SMITH" before confirming.
        Catches wrong email/phone errors BEFORE sending.
        """
        # Validate format first
        is_valid, message = self.validate_payid(payid, payid_type)
        if not is_valid:
            return {"found": False, "error": message}

        # In production, this would call NPP PayID Resolution Service
        # Demo: Return simulated lookup
        await asyncio.sleep(0.1)  # Simulate API call

        return {
            "found": True,
            "payid": payid,
            "payid_type": payid_type.value,
            "display_name": "DEMO USER",  # In production: actual registered name
            "resolution_time": datetime.now().isoformat(),
        }

    async def create_payment_request(
        self,
        amount: Decimal,
        payer_payid: str,
        description: str,
        reference: str,
        due_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Create an NPP Request to Pay.

        REQUEST TO PAY:
        Instead of giving BSB/Account, you send a payment request.
        Customer approves in their banking app.

        BENEFITS:
        - No need to share bank details
        - Customer confirms amount before paying
        - Automatic reconciliation via reference
        - Request can have expiry date
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Generate unique request ID
        request_id = secrets.token_urlsafe(16)

        await asyncio.sleep(0.1)  # Simulate API call

        return {
            "request_id": request_id,
            "amount": str(amount),
            "payer_payid": payer_payid,
            "description": description[:280],  # NPP allows 280 chars
            "reference": reference,
            "due_date": due_date.isoformat() if due_date else None,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# AUSTRALIAN BNPL (BUY NOW PAY LATER) - AFTERPAY, ZIP PAY
# ══════════════════════════════════════════════════════════════════════════════


class BNPLProvider(Enum):
    """
    Australian BNPL (Buy Now Pay Later) providers.

    NOTE: Market has changed significantly 2022-2026:
    - Afterpay acquired by Block/Square (2022)
    - Zip Pay consolidated operations
    - ASIC introduced BNPL regulations (2024)
    - Credit Reporting requirements added
    """

    AFTERPAY = "afterpay"  # Now owned by Block/Square
    ZIP_PAY = "zip_pay"  # Zip Co - ASX:ZIP
    ZIP_MONEY = "zip_money"  # Higher limits, longer terms
    HUMM = "humm"  # Formerly Flexigroup (ASX:HUM)
    KLARNA = "klarna"  # Swedish but operates in AU
    LATITUDE_PAY = "latitude"  # Latitude Financial (ASX:LFS)
    OPENPAY = "openpay"  # Ceased operations 2023
    COMMBANK_STEPAY = "stepay"  # CommBank's BNPL


@dataclass
class BNPLOrder:
    """BNPL order details for payment processing."""

    order_id: str
    provider: BNPLProvider
    amount: Decimal
    currency: str = "AUD"
    instalments: int = 4  # Typical: 4 fortnightly payments
    first_payment: Decimal = Decimal("0")
    merchant_fee_percent: Decimal = Decimal("4.0")  # Typical merchant fee
    customer_id: str = ""
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)


class AfterpayHandler:
    """
    Afterpay (Block/Square) BNPL integration.

    AFTERPAY MODEL (2026):
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  FEATURE                      DETAILS                                     ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Parent Company              Block, Inc (NYSE: SQ) - acquired 2022       ║
    ║  Payment Structure           4 fortnightly instalments                   ║
    ║  Interest to Customer        $0 (if paid on time)                        ║
    ║  Late Fees                   Capped at 25% of order or $68               ║
    ║  Merchant Fee                4-6% + $0.30 per transaction                ║
    ║  Order Limits                $10 - $2,000 (account dependent)            ║
    ║  Eligibility                 18+, Australian debit/credit card           ║
    ║  Credit Check                Soft check only (no credit score impact)    ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    ASIC BNPL REGULATIONS (2024+):
    - Must assess affordability before approving
    - Must report to credit bureaus
    - Hardship arrangements required
    - Clear disclosure of fees
    - External dispute resolution (AFCA) membership

    WHY INTEGRATE BNPL:
    - 30% higher conversion for $100-500 purchases
    - Attracts younger demographic (18-35)
    - Reduces cart abandonment
    - Merchant bears cost, not customer
    """

    # Afterpay API endpoints (sandbox)
    SANDBOX_URL = "https://api-sandbox.afterpay.com/v2"
    PRODUCTION_URL = "https://api.afterpay.com/v2"

    # Australian limits
    MIN_ORDER = Decimal("10.00")
    MAX_ORDER = Decimal("2000.00")
    MERCHANT_FEE = Decimal("0.05")  # 5% typical

    def __init__(self, merchant_id: str, secret_key: str, sandbox: bool = True):
        """
        Initialize Afterpay handler.

        SECURITY:
        - Store secret_key in secure vault (never in code!)
        - Use environment variables for credentials
        - Rotate keys regularly
        """
        self.merchant_id = merchant_id
        self._secret_key = secret_key  # Never log this!
        self.base_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL
        self._audit_log: list[dict] = []

    def _log_audit(self, action: str, details: dict) -> None:
        """Audit log for ASIC compliance."""
        self._audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "details": {
                    k: v
                    for k, v in details.items()
                    if k not in ("card", "secret", "token")
                },
            }
        )

    def validate_order_amount(self, amount: Decimal) -> tuple[bool, str]:
        """
        Validate order is within Afterpay limits.

        BUSINESS LOGIC:
        - Min $10 (too small = not worth processing fees)
        - Max $2000 (risk limit for new customers)
        - Returning customers may have higher limits
        """
        if amount < self.MIN_ORDER:
            return False, f"Minimum order is ${self.MIN_ORDER}"
        if amount > self.MAX_ORDER:
            return (
                False,
                f"Maximum order is ${self.MAX_ORDER}. Consider Zip Money for larger purchases.",
            )
        return True, "Amount valid for Afterpay"

    def calculate_instalments(self, total: Decimal) -> dict:
        """
        Calculate Afterpay payment schedule.

        STRUCTURE:
        - 4 equal fortnightly payments
        - First payment due at checkout
        - Remaining 3 payments every 2 weeks
        """
        instalment = (total / 4).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Handle rounding - first payment absorbs difference
        first_payment = total - (instalment * 3)

        schedule = []
        payment_date = datetime.now()

        for i in range(4):
            amount = first_payment if i == 0 else instalment
            schedule.append(
                {
                    "instalment_number": i + 1,
                    "amount": str(amount),
                    "due_date": payment_date.strftime("%Y-%m-%d"),
                    "status": "due" if i == 0 else "scheduled",
                }
            )
            payment_date += timedelta(days=14)

        return {
            "total": str(total),
            "instalments": 4,
            "schedule": schedule,
            "first_payment_today": str(first_payment),
            "fortnightly_payment": str(instalment),
        }

    async def create_checkout(
        self,
        order_id: str,
        amount: Decimal,
        consumer_email: str,
        items: list[dict],
        redirect_confirm_url: str,
        redirect_cancel_url: str,
    ) -> dict:
        """
        Create Afterpay checkout session.

        FLOW:
        1. Create checkout with order details
        2. Redirect customer to Afterpay
        3. Customer logs in / creates account
        4. Afterpay approves or declines
        5. Customer redirected back with token
        6. Capture payment with token

        Returns:
            Checkout session with redirect URL
        """
        # Validate amount
        is_valid, message = self.validate_order_amount(amount)
        if not is_valid:
            return {"success": False, "error": message}

        self._log_audit(
            "checkout_create",
            {"order_id": order_id, "amount": str(amount), "items_count": len(items)},
        )

        # In production, this calls Afterpay API
        # Demo: simulate response
        await asyncio.sleep(0.1)

        token = secrets.token_urlsafe(32)

        return {
            "success": True,
            "token": token,
            "expires": (datetime.now() + timedelta(hours=1)).isoformat(),
            "redirect_url": f"{self.base_url}/checkout?token={token}",
            "order_id": order_id,
            "amount": str(amount),
            "instalments": self.calculate_instalments(amount),
        }

    async def capture_payment(self, token: str, order_id: str) -> dict:
        """
        Capture Afterpay payment after customer approval.

        CRITICAL: Only call this after customer returns from Afterpay!

        The token is single-use and expires after 1 hour.
        """
        self._log_audit(
            "payment_capture",
            {
                "order_id": order_id,
                "token_prefix": token[:8] + "...",  # Never log full token
            },
        )

        await asyncio.sleep(0.1)

        # Simulate successful capture
        return {
            "success": True,
            "order_id": order_id,
            "afterpay_order_id": f"AP-{secrets.token_hex(8).upper()}",
            "status": "APPROVED",
            "payment_schedule": self.calculate_instalments(Decimal("100.00")),
            "captured_at": datetime.now().isoformat(),
        }

    async def refund(
        self, afterpay_order_id: str, amount: Decimal, reason: str
    ) -> dict:
        """
        Process Afterpay refund.

        REFUND RULES:
        - Full or partial refunds supported
        - Refunds reduce remaining instalments
        - If fully paid, refund to original payment method
        - Merchant fee NOT refunded by Afterpay
        """
        self._log_audit(
            "refund",
            {
                "afterpay_order_id": afterpay_order_id,
                "amount": str(amount),
                "reason": reason,
            },
        )

        await asyncio.sleep(0.1)

        return {
            "success": True,
            "refund_id": f"REF-{secrets.token_hex(8).upper()}",
            "order_id": afterpay_order_id,
            "amount": str(amount),
            "reason": reason,
            "status": "PROCESSED",
            "processed_at": datetime.now().isoformat(),
        }


class ZipPayHandler:
    """
    Zip Pay / Zip Money BNPL integration.

    ZIP CO (ASX: ZIP) PRODUCTS:
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  PRODUCT          LIMIT        TERM          USE CASE                     ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Zip Pay         $350-$1500   Interest-free  Everyday purchases          ║
    ║  Zip Money       $1000-$50K   3-60 months    Larger purchases            ║
    ║  Zip Business    Custom       Flexible       B2B payments                 ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    ZIP PAY vs AFTERPAY:
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  FEATURE              ZIP PAY               AFTERPAY                      ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Credit Limit        Revolving line        Per-purchase                   ║
    ║  Repayments          Min monthly           4 fortnightly fixed           ║
    ║  Interest-Free       3 months              Always (if on time)           ║
    ║  Account Fee         $0-$9.95/month        None                           ║
    ║  Late Fee            $15                   $10 + $7 (capped)             ║
    ║  Merchant Fee        ~3-4%                 ~5-6%                          ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    INTEGRATION NOTES:
    - Uses OAuth 2.0 for authentication
    - Webhook notifications for status changes
    - Supports partial captures and refunds
    """

    SANDBOX_URL = "https://api.sandbox.zip.co/merchant/v1"
    PRODUCTION_URL = "https://api.zip.co/merchant/v1"

    def __init__(self, api_key: str, sandbox: bool = True):
        """Initialize Zip handler."""
        self._api_key = api_key  # Never log!
        self.base_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL
        self._audit_log: list[dict] = []

    def _log_audit(self, action: str, details: dict) -> None:
        """Audit logging for compliance."""
        self._audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "details": {
                    k: v
                    for k, v in details.items()
                    if k not in ("api_key", "token", "secret")
                },
            }
        )

    def calculate_minimum_payment(self, balance: Decimal) -> Decimal:
        """
        Calculate minimum monthly payment for Zip Pay.

        RULE: Higher of $40 or balance (if under $40)
        Plus any overdue amounts or fees.
        """
        min_payment = Decimal("40.00")
        return min(balance, min_payment)

    async def create_charge(
        self,
        order_id: str,
        amount: Decimal,
        customer_email: str,
        items: list[dict],
        redirect_url: str,
    ) -> dict:
        """
        Create Zip Pay charge.

        FLOW:
        1. Create charge request
        2. Redirect to Zip for auth
        3. Customer approves
        4. Webhook notification
        5. Complete charge
        """
        self._log_audit("charge_create", {"order_id": order_id, "amount": str(amount)})

        await asyncio.sleep(0.1)

        checkout_id = secrets.token_urlsafe(24)

        return {
            "success": True,
            "checkout_id": checkout_id,
            "order_id": order_id,
            "amount": str(amount),
            "uri": f"https://checkout.zip.co/v1/{checkout_id}",
            "state": "CREATED",
            "created": datetime.now().isoformat(),
        }

    async def capture_charge(self, checkout_id: str) -> dict:
        """Capture authorized Zip charge."""
        self._log_audit("charge_capture", {"checkout_id": checkout_id})

        await asyncio.sleep(0.1)

        return {
            "success": True,
            "receipt_number": f"ZIP-{secrets.token_hex(8).upper()}",
            "state": "CAPTURED",
            "captured_at": datetime.now().isoformat(),
        }

    async def refund(self, receipt_number: str, amount: Decimal, reason: str) -> dict:
        """Process Zip refund."""
        self._log_audit(
            "refund", {"receipt_number": receipt_number, "amount": str(amount)}
        )

        await asyncio.sleep(0.1)

        return {
            "success": True,
            "refund_id": f"ZREF-{secrets.token_hex(8).upper()}",
            "amount": str(amount),
            "state": "REFUNDED",
            "processed_at": datetime.now().isoformat(),
        }


class AustralianPaymentGateways:
    """
    Major Australian payment gateway integrations.

    AUSTRALIAN GATEWAY LANDSCAPE (2026):
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  GATEWAY             OWNER           BEST FOR                             ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Stripe              Stripe, Inc     Developers, startups, API-first     ║
    ║  Square              Block, Inc      Retail POS, omnichannel             ║
    ║  Tyro                ASX:TYR         SMB, hospitality, healthcare        ║
    ║  Eway                Global Payments Enterprise, recurring billing       ║
    ║  PayWay              Westpac         Enterprise, bank integration        ║
    ║  CommBank Gateway    CBA             CommBank customers, SimplePay       ║
    ║  NAB Transact        NAB             NAB business customers              ║
    ║  ANZ eGate           ANZ             ANZ business customers              ║
    ║  Braintree           PayPal          PayPal integration, mobile          ║
    ║  Adyen               Adyen NV        Enterprise, unified commerce        ║
    ║  Windcave            Windcave        Trans-Tasman (AU/NZ)                ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    CHOOSING A GATEWAY:
    - Startup/SMB: Stripe or Square (easy integration, flat fees)
    - Enterprise: Adyen or Eway (volume discounts, features)
    - Bank customers: Use your bank's gateway (lower fees)
    - Healthcare: Tyro (Medicare claiming, EFTPOS integration)
    - E-commerce: Stripe + Afterpay combination is popular
    """

    @staticmethod
    def get_gateway_fees() -> dict:
        """
        Typical Australian gateway fees (2026).

        NOTE: Fees vary by volume, industry, and negotiation.
        These are typical rates for SMB merchants.
        """
        return {
            "stripe": {
                "domestic_card": "1.75% + $0.30",
                "international_card": "2.9% + $0.30",
                "bnpl_surcharge": "Varies by BNPL",
                "monthly_fee": "$0",
                "pci_compliance": "Included",
            },
            "square": {
                "in_person": "1.6%",
                "online": "2.2%",
                "keyed": "2.2%",
                "monthly_fee": "$0",
                "pos_hardware": "Extra",
            },
            "eway": {
                "domestic_card": "1.5% + $0.20",
                "international_card": "2.5% + $0.20",
                "monthly_fee": "$49",
                "pci_compliance": "$49/year",
            },
            "tyro": {
                "eftpos": "From 0.5%",
                "credit": "From 0.9%",
                "monthly_fee": "$0",
                "medicare_claiming": "Included",
            },
            "commbank_simplify": {
                "domestic": "1.6%",
                "international": "2.6%",
                "monthly_fee": "$0",
                "requires_commbank_account": True,
            },
            "afterpay_merchant": {
                "commission": "4-6%",
                "transaction_fee": "$0.30",
                "monthly_fee": "$0",
                "customer_cost": "$0 (if on time)",
            },
            "zip_merchant": {
                "commission": "3-4%",
                "transaction_fee": "Included",
                "monthly_fee": "$0",
            },
        }

    @staticmethod
    def recommend_gateway(
        monthly_volume: Decimal,
        average_transaction: Decimal,
        has_physical_store: bool,
        needs_bnpl: bool,
        bank: str = "",
    ) -> list[dict]:
        """
        Recommend best gateway(s) based on business profile.

        Returns ranked list of recommendations.
        """
        recommendations = []

        # Low volume: Stripe or Square (no monthly fees)
        if monthly_volume < Decimal("10000"):
            recommendations.append(
                {
                    "gateway": "Stripe",
                    "reason": "Best for low volume - no monthly fees, easy setup",
                    "estimated_monthly_cost": float(monthly_volume * Decimal("0.0175")),
                }
            )

        # Physical store: Square or Tyro
        if has_physical_store:
            recommendations.append(
                {
                    "gateway": (
                        "Square" if average_transaction < Decimal("50") else "Tyro"
                    ),
                    "reason": "Great POS integration for physical stores",
                    "estimated_monthly_cost": float(monthly_volume * Decimal("0.016")),
                }
            )

        # High volume: Negotiate with Eway or Adyen
        if monthly_volume > Decimal("100000"):
            recommendations.append(
                {
                    "gateway": "Eway or Adyen",
                    "reason": "Volume discounts available, enterprise features",
                    "estimated_monthly_cost": "Negotiate custom rates",
                }
            )

        # Bank customer: Use bank gateway for better rates
        bank_gateways = {
            "commbank": "CommBank SimplePay",
            "westpac": "PayWay",
            "nab": "NAB Transact",
            "anz": "ANZ eGate",
        }
        if bank.lower() in bank_gateways:
            recommendations.append(
                {
                    "gateway": bank_gateways[bank.lower()],
                    "reason": f"Your {bank.upper()} account may get preferential rates",
                    "estimated_monthly_cost": "Check with your bank",
                }
            )

        # Add BNPL recommendation if needed
        if needs_bnpl:
            recommendations.append(
                {
                    "gateway": "Afterpay + Zip",
                    "reason": "BNPL increases conversion 20-30% for $50-500 purchases",
                    "estimated_monthly_cost": "4-6% on BNPL transactions only",
                }
            )

        return recommendations


# ══════════════════════════════════════════════════════════════════════════════
# GST (GOODS AND SERVICES TAX) HANDLING
# ══════════════════════════════════════════════════════════════════════════════


class GSTCalculator:
    """
    Australian GST (Goods and Services Tax) calculator.

    GST RULES:
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  RULE                         DETAILS                                    ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Standard Rate               10% on taxable supplies                     ║
    ║  GST-Free                    Exports, basic food, health, education     ║
    ║  Input-Taxed                 Financial services, residential rent       ║
    ║  BAS Reporting               Monthly, quarterly, or annually            ║
    ║  Tax Invoice Threshold       $82.50+ requires tax invoice               ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    WHY ACCURACY MATTERS:
    - BAS reporting errors = ATO penalties
    - Under-reporting = audit risk
    - Over-charging = customer complaints
    """

    GST_RATE = Decimal("0.10")  # 10%
    TAX_INVOICE_THRESHOLD = Decimal("82.50")  # Threshold for tax invoices

    @classmethod
    def add_gst(cls, amount_excl: Decimal) -> tuple[Decimal, Decimal, Decimal]:
        """
        Add GST to an amount (price exclusive of GST).

        Args:
            amount_excl: Amount excluding GST

        Returns:
            Tuple of (amount_excl, gst_amount, amount_incl)
        """
        gst = (amount_excl * cls.GST_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        total = amount_excl + gst

        return amount_excl, gst, total

    @classmethod
    def extract_gst(cls, amount_incl: Decimal) -> tuple[Decimal, Decimal, Decimal]:
        """
        Extract GST from an amount (price inclusive of GST).

        FORMULA:
        GST = Amount × (Rate ÷ (1 + Rate))
        GST = Amount × (0.10 ÷ 1.10)
        GST = Amount ÷ 11

        Args:
            amount_incl: Amount including GST

        Returns:
            Tuple of (amount_excl, gst_amount, amount_incl)
        """
        # GST = total ÷ 11
        gst = (amount_incl / Decimal("11")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        excl = amount_incl - gst

        return excl, gst, amount_incl

    @classmethod
    def requires_tax_invoice(cls, amount: Decimal) -> bool:
        """
        Check if amount requires a tax invoice.

        TAX INVOICE REQUIREMENTS (over $82.50):
        - Words "Tax Invoice" prominently displayed
        - Supplier's ABN
        - Supplier's identity
        - Date of issue
        - Brief description of goods/services
        - GST amount (if any)
        - Total amount

        For amounts OVER $1,000:
        - Also requires buyer's identity/ABN
        """
        return amount >= cls.TAX_INVOICE_THRESHOLD


# ══════════════════════════════════════════════════════════════════════════════
# AUSTRALIAN CONSUMER LAW COMPLIANCE
# ══════════════════════════════════════════════════════════════════════════════


class RefundReason(Enum):
    """Australian Consumer Law refund reasons."""

    FAULTY = "faulty"  # Consumer guarantee - must refund
    NOT_AS_DESCRIBED = "not_as_described"  # Consumer guarantee - must refund
    DOES_NOT_MATCH_SAMPLE = "does_not_match_sample"  # Must refund
    NOT_FIT_FOR_PURPOSE = "not_fit_for_purpose"  # Must refund
    CHANGE_OF_MIND = "change_of_mind"  # At seller's discretion
    COOLING_OFF = "cooling_off"  # 10 days for unsolicited sales
    MAJOR_FAILURE = "major_failure"  # Full refund or replacement
    MINOR_FAILURE = "minor_failure"  # Repair or partial refund


@dataclass
class RefundEligibility:
    """Australian Consumer Law refund eligibility check."""

    is_eligible: bool
    reason: RefundReason
    mandatory: bool  # True if ACL requires refund
    explanation: str
    refund_type: str  # "full", "partial", "repair", "replacement"


class AustralianConsumerLaw:
    """
    Australian Consumer Law compliance for refunds and returns.

    CONSUMER GUARANTEES (CANNOT CONTRACT OUT OF THESE):
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  GUARANTEE                         REMEDY                                ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Acceptable quality                Refund/replacement/repair             ║
    ║  Fit for purpose                   Refund/replacement/repair             ║
    ║  Match description                 Refund/replacement/repair             ║
    ║  Match sample/demo                 Refund/replacement/repair             ║
    ║  Express warranties                As stated in warranty                 ║
    ║  Title and undisturbed possession  Full refund                           ║
    ║  No undisclosed securities         Full refund                           ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    MAJOR VS MINOR FAILURE:
    Major: Consumer would not have bought if they'd known
    Minor: Can be fixed in reasonable time

    WHY THIS MATTERS:
    - Refusing valid ACL claims = $50M+ ACCC fines
    - Clear policies reduce disputes
    - Good refund experience = customer loyalty
    """

    # Cooling-off period for unsolicited sales (doorknock, telemarketing)
    COOLING_OFF_DAYS = 10

    @classmethod
    def check_refund_eligibility(
        cls,
        reason: RefundReason,
        purchase_date: datetime,
        is_unsolicited_sale: bool = False,
    ) -> RefundEligibility:
        """
        Check if refund is required under Australian Consumer Law.

        Args:
            reason: Why customer wants refund
            purchase_date: When product was purchased
            is_unsolicited_sale: True if doorknock/telemarketing sale

        Returns:
            RefundEligibility with mandatory flag and explanation
        """
        days_since_purchase = (datetime.now() - purchase_date).days

        # Cooling-off period for unsolicited sales
        if is_unsolicited_sale and days_since_purchase <= cls.COOLING_OFF_DAYS:
            return RefundEligibility(
                is_eligible=True,
                reason=RefundReason.COOLING_OFF,
                mandatory=True,
                explanation=(
                    f"Under Australian Consumer Law, unsolicited sales have a "
                    f"{cls.COOLING_OFF_DAYS}-day cooling-off period. "
                    f"Customer can cancel for any reason within this period."
                ),
                refund_type="full",
            )

        # Major failure - always entitled to refund
        if reason == RefundReason.MAJOR_FAILURE:
            return RefundEligibility(
                is_eligible=True,
                reason=reason,
                mandatory=True,
                explanation=(
                    "Major failure under ACL. Customer is entitled to: "
                    "1) Full refund, OR "
                    "2) Replacement of equal value. "
                    "The choice is the CUSTOMER'S, not the seller's."
                ),
                refund_type="full",
            )

        # Minor failure - repair first
        if reason == RefundReason.MINOR_FAILURE:
            return RefundEligibility(
                is_eligible=True,
                reason=reason,
                mandatory=True,
                explanation=(
                    "Minor failure under ACL. Seller may offer repair first. "
                    "If repair is not done in reasonable time, customer can then "
                    "request refund or replacement."
                ),
                refund_type="repair",
            )

        # Consumer guarantees - all mandatory
        if reason in [
            RefundReason.FAULTY,
            RefundReason.NOT_AS_DESCRIBED,
            RefundReason.DOES_NOT_MATCH_SAMPLE,
            RefundReason.NOT_FIT_FOR_PURPOSE,
        ]:
            return RefundEligibility(
                is_eligible=True,
                reason=reason,
                mandatory=True,
                explanation=(
                    f"Consumer guarantee breach: {reason.value}. "
                    f"Under Australian Consumer Law, this MUST be remedied. "
                    f"'No refund' signs don't apply to consumer guarantees."
                ),
                refund_type="full",
            )

        # Change of mind - at seller's discretion
        if reason == RefundReason.CHANGE_OF_MIND:
            return RefundEligibility(
                is_eligible=False,  # Not mandatory
                reason=reason,
                mandatory=False,
                explanation=(
                    "Change of mind is NOT covered by Australian Consumer Law. "
                    "Refund is at seller's discretion per their returns policy. "
                    "Check the store's returns policy."
                ),
                refund_type="none",
            )

        return RefundEligibility(
            is_eligible=False,
            reason=reason,
            mandatory=False,
            explanation="Unable to determine eligibility. Please contact support.",
            refund_type="none",
        )


# ══════════════════════════════════════════════════════════════════════════════
# AUSTRALIAN PAYMENT BOT
# ══════════════════════════════════════════════════════════════════════════════


class PaymentMethod(Enum):
    """Australian payment methods."""

    NPP_PAYID = "npp_payid"
    BPAY = "bpay"
    BANK_TRANSFER = "bank_transfer"
    DIRECT_DEBIT = "direct_debit"
    CARD = "card"


@dataclass
class PaymentRequest:
    """Payment request with Australian-specific handling."""

    request_id: str
    amount: Decimal
    gst_amount: Decimal
    method: PaymentMethod
    reference: str
    description: str
    customer_id: str
    created_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    status: str = "pending"

    # Australian-specific fields
    bpay_biller_code: Optional[str] = None
    bpay_reference: Optional[str] = None
    payid: Optional[str] = None
    payid_type: Optional[PayIDType] = None


class AustralianPaymentBot:
    """
    Australian payment bot with NPP, BPAY, and BSB handling.

    AUDIT TRAIL (PCI DSS 10.2):
    Every operation logs:
    - User ID
    - Action type
    - Timestamp
    - Outcome
    - NO sensitive data (no card numbers, no CVV, no PINs)
    """

    def __init__(
        self,
        business_abn: str,
        business_name: str,
        bpay_biller_code: str,
        default_bsb: str,
        default_account: str,
    ):
        self.business_abn = business_abn
        self.business_name = business_name
        self.bpay_biller_code = bpay_biller_code
        self.default_bsb = default_bsb
        self.default_account = default_account

        self.npp_handler = NPPPaymentHandler()
        self._audit_log: list[dict[str, Any]] = []

        # Validate business identifiers on init
        is_valid, msg = self.npp_handler._validate_abn(business_abn)
        if not is_valid:
            logger.warning(f"Business ABN validation: {msg}")

    def _log_audit(
        self,
        action: str,
        user_id: str,
        details: dict[str, Any],
        outcome: str = "success",
    ) -> None:
        """
        Log audit trail entry.

        PCI DSS 10.2 REQUIREMENTS:
        - All actions by individuals with cardholder data access
        - Invalid logical access attempts
        - Use of identification and authentication mechanisms
        - All changes to audit trail data
        - Creation/deletion of system-level objects

        NEVER LOG:
        - Card numbers (full or partial)
        - CVV/CVC
        - PINs
        - Account passwords
        - Encryption keys
        """
        # Sanitize details - remove any sensitive data
        safe_details = self._sanitize_for_logging(details)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": safe_details,
            "outcome": outcome,
        }

        self._audit_log.append(entry)
        logger.info(f"AUDIT: {action} by {user_id} - {outcome}")

    def _sanitize_for_logging(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Remove sensitive data before logging.

        SENSITIVE DATA PATTERNS:
        - Card numbers: 16 digits
        - CVV: 3-4 digits on its own
        - Account numbers: 6-10 digits
        - BSB: 6 digits (okay to log)
        - Tokens: Fine to log (they're designed for this)
        """
        safe = {}

        sensitive_keys = {
            "card_number",
            "cvv",
            "cvc",
            "pin",
            "password",
            "secret",
            "key",
            "token",
            "account_number",
        }

        for key, value in data.items():
            key_lower = key.lower()

            if any(s in key_lower for s in sensitive_keys):
                if "account" in key_lower:
                    # Mask account numbers
                    safe[key] = f"****{str(value)[-4:]}" if value else "****"
                else:
                    safe[key] = "[REDACTED]"
            else:
                safe[key] = value

        return safe

    async def create_bpay_payment(
        self, user_id: str, customer_id: str, amount: Decimal, invoice_number: str
    ) -> PaymentRequest:
        """
        Create a BPAY payment request.

        Returns BPAY details for customer to pay via their bank.
        """
        # Calculate GST
        excl, gst, incl = GSTCalculator.add_gst(amount)

        # Generate BPAY reference
        bpay_ref = BPAYValidator.generate_reference(
            customer_id=customer_id, invoice_number=invoice_number
        )

        request = PaymentRequest(
            request_id=secrets.token_urlsafe(16),
            amount=incl,
            gst_amount=gst,
            method=PaymentMethod.BPAY,
            reference=invoice_number,
            description=f"Invoice {invoice_number}",
            customer_id=customer_id,
            bpay_biller_code=self.bpay_biller_code,
            bpay_reference=bpay_ref,
        )

        self._log_audit(
            action="create_bpay_payment",
            user_id=user_id,
            details={
                "customer_id": customer_id,
                "invoice": invoice_number,
                "amount": str(incl),
                "biller_code": self.bpay_biller_code,
            },
        )

        return request

    async def create_payid_request(
        self,
        user_id: str,
        customer_payid: str,
        payid_type: PayIDType,
        amount: Decimal,
        description: str,
        reference: str,
    ) -> dict[str, Any]:
        """
        Create an NPP Request to Pay via PayID.

        Customer will receive notification in their banking app.
        """
        # Validate PayID
        is_valid, msg = self.npp_handler.validate_payid(customer_payid, payid_type)
        if not is_valid:
            self._log_audit(
                action="create_payid_request",
                user_id=user_id,
                details={"payid_type": payid_type.value, "error": msg},
                outcome="failed",
            )
            return {"success": False, "error": msg}

        # Calculate GST
        excl, gst, incl = GSTCalculator.add_gst(amount)

        # Create NPP request
        request = await self.npp_handler.create_payment_request(
            amount=incl,
            payer_payid=customer_payid,
            description=f"{description} (GST: ${gst})",
            reference=reference,
            due_date=datetime.now() + timedelta(days=14),
        )

        self._log_audit(
            action="create_payid_request",
            user_id=user_id,
            details={
                "payid_type": payid_type.value,
                "amount": str(incl),
                "reference": reference,
            },
        )

        return {
            "success": True,
            "request": request,
            "amount_excl_gst": str(excl),
            "gst": str(gst),
            "total": str(incl),
        }

    async def validate_bank_details(
        self, user_id: str, bsb: str, account_number: str
    ) -> dict[str, Any]:
        """
        Validate Australian bank details (BSB and account).

        BSB VALIDATION:
        - Format check (6 digits)
        - Bank code lookup
        - State code verification

        ACCOUNT VALIDATION:
        - Length check (6-10 digits typically)
        - No format verification possible (bank-specific)
        """
        # Validate BSB
        bsb_valid, bsb_msg = BSBValidator.validate(bsb)

        # Basic account validation
        account_clean = re.sub(r"\D", "", account_number)
        account_valid = 5 <= len(account_clean) <= 10

        result = {
            "bsb": {
                "valid": bsb_valid,
                "formatted": BSBValidator.format(bsb),
                "bank_info": bsb_msg,
            },
            "account": {
                "valid": account_valid,
                "masked": BSBValidator.mask_account(account_number),
            },
            "overall_valid": bsb_valid and account_valid,
        }

        self._log_audit(
            action="validate_bank_details",
            user_id=user_id,
            details={"bsb": BSBValidator.format(bsb), "valid": result["overall_valid"]},
        )

        return result

    async def process_refund_request(
        self,
        user_id: str,
        customer_id: str,
        order_id: str,
        reason: RefundReason,
        purchase_date: datetime,
        amount: Decimal,
        is_unsolicited_sale: bool = False,
    ) -> dict[str, Any]:
        """
        Process refund request with Australian Consumer Law compliance.

        ACL REQUIREMENTS:
        - Cannot refuse statutory rights
        - Must provide remedy for consumer guarantee failures
        - Customer chooses remedy for major failures
        """
        # Check ACL eligibility
        eligibility = AustralianConsumerLaw.check_refund_eligibility(
            reason=reason,
            purchase_date=purchase_date,
            is_unsolicited_sale=is_unsolicited_sale,
        )

        result = {
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": str(amount),
            "reason": reason.value,
            "acl_eligible": eligibility.is_eligible,
            "acl_mandatory": eligibility.mandatory,
            "refund_type": eligibility.refund_type,
            "explanation": eligibility.explanation,
        }

        if eligibility.mandatory:
            result["status"] = "approved_acl"
            result["message"] = (
                "Refund approved under Australian Consumer Law. "
                "Processing within 3-5 business days."
            )
        elif eligibility.is_eligible:
            result["status"] = "pending_approval"
            result["message"] = "Refund request submitted for review."
        else:
            result["status"] = "declined"
            result["message"] = eligibility.explanation

        self._log_audit(
            action="process_refund",
            user_id=user_id,
            details={
                "order_id": order_id,
                "reason": reason.value,
                "amount": str(amount),
                "acl_mandatory": eligibility.mandatory,
                "status": result["status"],
            },
        )

        return result

    def generate_tax_invoice(
        self,
        invoice_number: str,
        customer_name: str,
        items: list[dict[str, Any]],
        customer_abn: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate Australian tax invoice.

        TAX INVOICE REQUIREMENTS:
        - "Tax Invoice" heading
        - Supplier ABN
        - Supplier name
        - Date of issue
        - Description of goods/services
        - GST amounts
        - Total including GST

        For invoices over $1,000:
        - Also requires customer ABN
        """
        subtotal = Decimal("0")
        gst_total = Decimal("0")

        invoice_items = []
        for item in items:
            item_excl = Decimal(str(item.get("amount", 0)))
            _, item_gst, item_incl = GSTCalculator.add_gst(item_excl)

            invoice_items.append(
                {
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", 1),
                    "unit_price": str(item_excl),
                    "gst": str(item_gst),
                    "total": str(item_incl),
                }
            )

            subtotal += item_excl
            gst_total += item_gst

        total = subtotal + gst_total

        invoice = {
            "document_type": "TAX INVOICE",
            "invoice_number": invoice_number,
            "date": datetime.now().strftime("%d/%m/%Y"),
            "supplier": {"name": self.business_name, "abn": self.business_abn},
            "customer": {"name": customer_name, "abn": customer_abn},
            "items": invoice_items,
            "subtotal": str(subtotal),
            "gst": str(gst_total),
            "total": str(total),
            "payment_options": {
                "bpay": {
                    "biller_code": self.bpay_biller_code,
                    "reference": BPAYValidator.generate_reference(
                        customer_id=customer_name[:3].upper(),
                        invoice_number=invoice_number,
                    ),
                },
                "bank_transfer": {
                    "bsb": self.default_bsb,
                    "account": BSBValidator.mask_account(self.default_account),
                    "reference": invoice_number,
                },
            },
            "requires_customer_abn": total > Decimal("1000.00"),
        }

        if invoice["requires_customer_abn"] and not customer_abn:
            invoice["warning"] = "Customer ABN required for invoices over $1,000"

        return invoice


# ══════════════════════════════════════════════════════════════════════════════
# DEMO SCENARIOS
# ══════════════════════════════════════════════════════════════════════════════


async def demo_bsb_validation():
    """Demo BSB validation."""
    print("\n" + "=" * 60)
    print("BSB VALIDATION DEMO")
    print("=" * 60)

    test_bsbs = [
        "063-000",  # CBA NSW
        "012-003",  # ANZ Victoria
        "732-000",  # Westpac NSW
        "999-999",  # Invalid
        "06300",  # Too short
    ]

    for bsb in test_bsbs:
        is_valid, msg = BSBValidator.validate(bsb)
        formatted = BSBValidator.format(bsb)
        print(f"  BSB: {bsb:>10} -> {formatted} | Valid: {is_valid} | {msg}")


async def demo_bpay():
    """Demo BPAY reference generation and validation."""
    print("\n" + "=" * 60)
    print("BPAY DEMO")
    print("=" * 60)

    # Generate reference
    ref = BPAYValidator.generate_reference(customer_id="12345", invoice_number="INV001")
    print(f"  Generated BPAY Reference: {ref}")

    # Validate it
    is_valid, msg = BPAYValidator.validate_reference(ref)
    print(f"  Validation: {msg}")

    # Try invalid reference
    is_valid, msg = BPAYValidator.validate_reference("12345678901")
    print(f"  Invalid ref check: {msg}")


async def demo_payid():
    """Demo PayID validation."""
    print("\n" + "=" * 60)
    print("PAYID VALIDATION DEMO")
    print("=" * 60)

    handler = NPPPaymentHandler()

    test_payids = [
        ("test@example.com", PayIDType.EMAIL),
        ("0412345678", PayIDType.PHONE),
        ("+61412345678", PayIDType.PHONE),
        ("51824753556", PayIDType.ABN),  # Valid ABN
        ("123456789", PayIDType.ACN),  # Test ACN
    ]

    for payid, ptype in test_payids:
        is_valid, msg = handler.validate_payid(payid, ptype)
        print(f"  {ptype.value:8} {payid:20} -> Valid: {is_valid} | {msg}")


async def demo_gst():
    """Demo GST calculations."""
    print("\n" + "=" * 60)
    print("GST CALCULATION DEMO")
    print("=" * 60)

    # Add GST to $100
    excl, gst, incl = GSTCalculator.add_gst(Decimal("100.00"))
    print(f"  Add GST:     $100.00 + ${gst} GST = ${incl}")

    # Extract GST from $110
    excl, gst, incl = GSTCalculator.extract_gst(Decimal("110.00"))
    print(f"  Extract GST: ${incl} total = ${excl} + ${gst} GST")

    # Check tax invoice threshold
    amounts = [Decimal("50.00"), Decimal("82.50"), Decimal("100.00")]
    for amt in amounts:
        requires = GSTCalculator.requires_tax_invoice(amt)
        print(f"  ${amt} requires tax invoice: {requires}")


async def demo_acl_refunds():
    """Demo Australian Consumer Law refund checks."""
    print("\n" + "=" * 60)
    print("AUSTRALIAN CONSUMER LAW REFUND DEMO")
    print("=" * 60)

    test_cases = [
        (RefundReason.FAULTY, datetime.now() - timedelta(days=30), False),
        (RefundReason.CHANGE_OF_MIND, datetime.now() - timedelta(days=5), False),
        (RefundReason.COOLING_OFF, datetime.now() - timedelta(days=5), True),
        (RefundReason.MAJOR_FAILURE, datetime.now() - timedelta(days=60), False),
    ]

    for reason, purchase_date, unsolicited in test_cases:
        result = AustralianConsumerLaw.check_refund_eligibility(
            reason=reason, purchase_date=purchase_date, is_unsolicited_sale=unsolicited
        )
        print(f"\n  Reason: {reason.value}")
        print(f"  Eligible: {result.is_eligible}")
        print(f"  Mandatory (ACL): {result.mandatory}")
        print(f"  Refund type: {result.refund_type}")


async def demo_full_payment_flow():
    """Demo complete payment flow."""
    print("\n" + "=" * 60)
    print("FULL PAYMENT FLOW DEMO")
    print("=" * 60)

    # Initialize bot
    bot = AustralianPaymentBot(
        business_abn="51824753556",  # Demo ABN
        business_name="Demo Pty Ltd",
        bpay_biller_code="12345",
        default_bsb="063-000",
        default_account="12345678",
    )

    print("\n1. Creating BPAY payment request...")
    bpay_request = await bot.create_bpay_payment(
        user_id="agent_001",
        customer_id="CUST001",
        amount=Decimal("99.99"),
        invoice_number="INV-2026-001",
    )
    print(f"   BPAY Biller Code: {bpay_request.bpay_biller_code}")
    print(f"   BPAY Reference: {bpay_request.bpay_reference}")
    print(f"   Amount (inc GST): ${bpay_request.amount}")

    print("\n2. Validating bank details...")
    bank_result = await bot.validate_bank_details(
        user_id="agent_001", bsb="063-000", account_number="12345678"
    )
    print(f"   BSB Valid: {bank_result['bsb']['valid']}")
    print(f"   Bank: {bank_result['bsb']['bank_info']}")
    print(f"   Account (masked): {bank_result['account']['masked']}")

    print("\n3. Processing refund request (ACL - faulty product)...")
    refund_result = await bot.process_refund_request(
        user_id="agent_001",
        customer_id="CUST001",
        order_id="ORD-001",
        reason=RefundReason.FAULTY,
        purchase_date=datetime.now() - timedelta(days=15),
        amount=Decimal("149.99"),
    )
    print(f"   Status: {refund_result['status']}")
    print(f"   ACL Mandatory: {refund_result['acl_mandatory']}")

    print("\n4. Generating tax invoice...")
    invoice = bot.generate_tax_invoice(
        invoice_number="INV-2026-002",
        customer_name="Jane Smith",
        items=[
            {"description": "Widget A", "amount": 50.00, "quantity": 2},
            {"description": "Widget B", "amount": 25.00, "quantity": 1},
        ],
    )
    print(f"   Invoice #: {invoice['invoice_number']}")
    print(f"   Subtotal: ${invoice['subtotal']}")
    print(f"   GST: ${invoice['gst']}")
    print(f"   Total: ${invoice['total']}")
    print(f"   BPAY Ref: {invoice['payment_options']['bpay']['reference']}")

    print("\n5. Audit log entries created:")
    for entry in bot._audit_log[-4:]:
        print(f"   - {entry['action']}: {entry['outcome']}")


async def main():
    """Run all demos."""
    print("=" * 60)
    print("AUSTRALIAN PAYMENT BOT - DEMO")
    print("=" * 60)
    print("\nThis demo shows Australian-specific payment handling:")
    print("- BSB/Account validation")
    print("- BPAY reference generation")
    print("- PayID/NPP integration")
    print("- GST calculations")
    print("- Australian Consumer Law compliance")

    await demo_bsb_validation()
    await demo_bpay()
    await demo_payid()
    await demo_gst()
    await demo_acl_refunds()
    await demo_full_payment_flow()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nKey takeaways:")
    print("✓ Always validate BSB before sending payments")
    print("✓ Use BPAY check digits to prevent data entry errors")
    print("✓ PayID provides instant payments with name confirmation")
    print("✓ GST is 10% and required on most goods/services")
    print("✓ ACL refund rights CANNOT be contracted out of")
    print("✓ Audit everything, but NEVER log sensitive data")


if __name__ == "__main__":
    asyncio.run(main())
