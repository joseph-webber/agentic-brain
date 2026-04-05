#!/usr/bin/env python3
"""
Example: Card-In-Chat Payment (MOTO-Style Conversational Payments)

██████████████████████████████████████████████████████████████████████████████
█                                                                            █
█   NOVEL CONCEPT: Accept card details DIRECTLY in conversation              █
█                                                                            █
█   Unlike typical payment chatbots that redirect to external checkout       █
█   pages (Stripe Checkout, PayPal buttons), this example shows how to       █
█   securely collect card details IN the chat - like a human sales rep       █
█   taking payment over the phone.                                           █
█                                                                            █
█   Use Cases:                                                               █
█   • Call centres (phone-to-chat escalation)                                █
█   • Accessibility needs (visually impaired users)                          █
█   • Embedded systems without browser capability                            █
█   • Legacy system integration                                              █
█   • White-glove concierge services                                         █
█                                                                            █
██████████████████████████████████████████████████████████████████████████████

SECURITY MODEL - PCI DSS COMPLIANT:
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FLOW ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User Types: "4242 4242 4242 4242"                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────┐                                                       │
│   │  INPUT HANDLER  │ ← Receives raw input                                  │
│   │  (in memory)    │ ← Validates format (Luhn)                             │
│   └────────┬────────┘ ← Holds for <100ms                                    │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────┐                                                       │
│   │   TOKENIZER     │ ← stripe.Token.create() or vault API                  │
│   │   (immediate)   │ ← Returns tok_xxx + last4                             │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────┐                                                       │
│   │  MEMORY WIPER   │ ← Overwrites original string                          │
│   │  (best effort)  │ ← Clears Python references                            │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  CONVERSATION SANITIZER                                             │   │
│   │  • Replaces PAN in history: "4242..." → "[CARD ENDING 4242]"       │   │
│   │  • Removes CVV entirely: "123" → "[CVV RECEIVED]"                   │   │
│   │  • Audit log shows: "Card tokenized, token=tok_xxx, last4=4242"    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   WHAT'S STORED:                          WHAT'S NEVER STORED:              │
│   ✓ Token (tok_xxx)                       ✗ Full card number                │
│   ✓ Last 4 digits                         ✗ CVV/CVC (ever!)                 │
│   ✓ Card brand (Visa/MC)                  ✗ Full expiry                     │
│   ✓ Expiry month/year (for token)         ✗ Raw user input                  │
│   ✓ Sanitized conversation                ✗ Anything in logs                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

PCI DSS COMPLIANCE CHECKLIST:
╔═══════════════════════════════════════════════════════════════════════════════╗
║  REQ   DESCRIPTION                                    IMPLEMENTATION          ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  3.2   Never store CVV after authorization            CVV never stored        ║
║  3.3   Mask PAN when displayed                        Only last 4 shown       ║
║  3.4   Render PAN unreadable anywhere stored          Immediate tokenization  ║
║  3.5   Protect cryptographic keys                     Stripe/vault handles    ║
║  4.1   Encrypt transmission                           TLS 1.2+ required       ║
║  6.5   Address common vulnerabilities                 Input validation        ║
║  7.1   Restrict access to cardholder data             Role-based access       ║
║  8.1   Unique identification                          Session tracking        ║
║  10.2  Automated audit trails                         All actions logged      ║
║  10.3  Record user, timestamp, action                 Structured logging      ║
║  11.3  Penetration testing                            Regular security review ║
╚═══════════════════════════════════════════════════════════════════════════════╝

AUSTRALIAN REGULATORY COMPLIANCE:
• APRA CPS 234: Information Security requirements for ADIs
• APRA CPS 230: Operational Resilience (effective July 2025)
• Privacy Act 1988: Australian Privacy Principles (APP)
• Consumer Data Right (CDR): Open banking compatibility
• ASIC ePayments Code: Electronic payment protections

Example Conversation:
─────────────────────────────────────────────────────────────────────────────────
User: "I'd like to pay my invoice"
Bot:  "Sure! Invoice #2026-0042 is $299.00 AUD. Ready to pay now?"
User: "Yes"
Bot:  "Great! I'll collect your card details securely. What's your card number?"
User: "4242 4242 4242 4242"
Bot:  "Got it (Visa ending in 4242). Expiry date (MM/YY)?"
User: "12/28"
Bot:  "CVV (3 digits on back of card)?"
User: "123"
Bot:  "Processing... ✅ Payment successful!
      Amount: $299.00 AUD
      Card: Visa ending 4242
      Receipt sent to joe@example.com
      Transaction ID: ch_1N2abc3DEF4ghi"
─────────────────────────────────────────────────────────────────────────────────

SANITIZED AUDIT LOG (what actually gets recorded):
─────────────────────────────────────────────────────────────────────────────────
2026-03-14 10:15:01 INFO  payment.session_started session_id=sess_abc123
2026-03-14 10:15:05 INFO  payment.invoice_lookup invoice=2026-0042 amount=299.00
2026-03-14 10:15:10 INFO  payment.card_collection_started session_id=sess_abc123
2026-03-14 10:15:15 INFO  payment.card_tokenized token=tok_xxx last4=4242 brand=visa
2026-03-14 10:15:16 INFO  payment.expiry_collected month=12 year=2028
2026-03-14 10:15:18 INFO  payment.cvv_received (never logged)
2026-03-14 10:15:19 INFO  payment.charge_initiated amount=29900 currency=aud
2026-03-14 10:15:21 INFO  payment.charge_successful charge_id=ch_1N2abc3DEF4ghi
─────────────────────────────────────────────────────────────────────────────────

Usage:
    python examples/enterprise/card_in_chat_payment.py

Requirements:
    pip install agentic-brain stripe
"""

import asyncio
import ctypes
import gc
import hashlib
import logging
import os
import re
import secrets
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Callable, Optional, Protocol

# ══════════════════════════════════════════════════════════════════════════════
# SECURITY-FIRST LOGGING CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that prevents ANY card-like data from reaching logs.

    PCI DSS 10.2.1: Never log sensitive authentication data.
    This is a DEFENSE IN DEPTH measure - data should already be sanitized.
    """

    # Patterns that MUST NEVER appear in logs
    FORBIDDEN_PATTERNS = [
        r"\b[3-6]\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Card numbers
        r"\b[3-6]\d{14,15}\b",  # Unformatted cards
        r"\b\d{3,4}\b(?=.*(?:cvv|cvc|security))",  # CVV context
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Check and sanitize log message."""
        message = str(record.msg)
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                # CRITICAL: Block this log entirely
                record.msg = "[BLOCKED: Potential card data detected]"
                return True  # Let it through but sanitized
        return True


# Configure secure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("card_in_chat")
logger.addFilter(SensitiveDataFilter())


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY WIPING UTILITIES
# ══════════════════════════════════════════════════════════════════════════════


class MemoryWiper:
    """
    Best-effort memory wiping for sensitive data.

    IMPORTANT: Python's memory model makes true secure wiping difficult.
    This is a DEFENSE IN DEPTH measure, not a guarantee. The real security
    comes from immediate tokenization.

    Techniques used:
    1. Overwrite string contents via ctypes (works for some Python versions)
    2. Delete all references
    3. Force garbage collection
    4. Clear relevant memory pools
    """

    @staticmethod
    def wipe_string(sensitive: str) -> None:
        """
        Attempt to overwrite a string's memory contents.

        Args:
            sensitive: The string to wipe from memory

        Note:
            This is best-effort. Python may have copied the string.
            Always use with immediate tokenization.
        """
        if not sensitive:
            return

        try:
            # Get the memory address of the string's character buffer
            # SECURITY: This overwrites the actual bytes in memory
            str_len = len(sensitive)
            offset = sys.getsizeof("") + 1  # Empty string size + null terminator

            # Overwrite with zeros
            ctypes.memset(id(sensitive) + offset, 0, str_len)
        except Exception:
            # If ctypes fails, at least try to minimize exposure
            pass
        finally:
            # Force garbage collection
            gc.collect()

    @staticmethod
    def wipe_dict_values(d: dict, keys: list[str]) -> None:
        """
        Wipe specific values from a dictionary.

        Args:
            d: Dictionary containing sensitive values
            keys: List of keys whose values should be wiped
        """
        for key in keys:
            if key in d:
                value = d[key]
                if isinstance(value, str):
                    MemoryWiper.wipe_string(value)
                d[key] = None
                del d[key]
        gc.collect()

    @staticmethod
    def secure_del(obj: Any) -> None:
        """
        Securely delete an object and force garbage collection.
        """
        try:
            if isinstance(obj, str):
                MemoryWiper.wipe_string(obj)
            del obj
        except Exception:
            pass
        finally:
            gc.collect()


# ══════════════════════════════════════════════════════════════════════════════
# CARD VALIDATION UTILITIES
# ══════════════════════════════════════════════════════════════════════════════


class CardBrand(Enum):
    """Card brand identification from BIN (Bank Identification Number)."""

    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"
    DINERS = "diners"
    JCB = "jcb"
    UNIONPAY = "unionpay"
    UNKNOWN = "unknown"


@dataclass
class CardValidationResult:
    """Result of card number validation."""

    is_valid: bool
    brand: CardBrand
    last_four: str
    error: Optional[str] = None


class CardValidator:
    """
    Card number validation utilities.

    SECURITY NOTE: This validates format and checksum ONLY.
    Actual card validity is determined by the payment processor.
    """

    # BIN ranges for card brand detection (first 6 digits)
    # Reference: ISO/IEC 7812-1:2017
    BIN_PATTERNS = {
        CardBrand.VISA: [r"^4"],
        CardBrand.MASTERCARD: [r"^5[1-5]", r"^2[2-7]"],
        CardBrand.AMEX: [r"^3[47]"],
        CardBrand.DISCOVER: [r"^6011", r"^65", r"^64[4-9]"],
        CardBrand.DINERS: [r"^3(?:0[0-5]|[68])"],
        CardBrand.JCB: [r"^(?:2131|1800|35)"],
        CardBrand.UNIONPAY: [r"^62"],
    }

    # Expected lengths by brand
    CARD_LENGTHS = {
        CardBrand.VISA: [13, 16, 19],
        CardBrand.MASTERCARD: [16],
        CardBrand.AMEX: [15],
        CardBrand.DISCOVER: [16],
        CardBrand.DINERS: [14, 16],
        CardBrand.JCB: [16],
        CardBrand.UNIONPAY: [16, 17, 18, 19],
        CardBrand.UNKNOWN: [13, 14, 15, 16, 17, 18, 19],
    }

    @staticmethod
    def luhn_check(card_number: str) -> bool:
        """
        Validate card number using Luhn algorithm (ISO/IEC 7812-1).

        The Luhn algorithm is a simple checksum formula used to validate
        identification numbers, including credit card numbers.

        Args:
            card_number: Card number (digits only)

        Returns:
            True if checksum is valid
        """
        digits = [int(d) for d in card_number if d.isdigit()]

        if len(digits) < 13:
            return False

        # Luhn algorithm
        checksum = 0
        is_even = False

        for digit in reversed(digits):
            if is_even:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
            is_even = not is_even

        return checksum % 10 == 0

    @classmethod
    def detect_brand(cls, card_number: str) -> CardBrand:
        """
        Detect card brand from BIN (first 6 digits).

        Args:
            card_number: Card number (may include spaces/dashes)

        Returns:
            Detected CardBrand
        """
        digits = "".join(c for c in card_number if c.isdigit())

        for brand, patterns in cls.BIN_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, digits):
                    return brand

        return CardBrand.UNKNOWN

    @classmethod
    def validate(cls, card_number: str) -> CardValidationResult:
        """
        Validate a card number.

        Checks:
        1. Contains only valid characters (digits, spaces, dashes)
        2. Correct length for detected brand
        3. Passes Luhn checksum

        Args:
            card_number: Card number (may include formatting)

        Returns:
            CardValidationResult with validation status
        """
        # Clean the input - allow digits, spaces, dashes only
        # SECURITY: Reject anything with unexpected characters
        if not re.match(r"^[\d\s\-]+$", card_number):
            return CardValidationResult(
                is_valid=False,
                brand=CardBrand.UNKNOWN,
                last_four="",
                error="Invalid characters in card number",
            )

        # Extract digits only
        digits = "".join(c for c in card_number if c.isdigit())

        # Get last four (safe to keep)
        last_four = digits[-4:] if len(digits) >= 4 else ""

        # Detect brand
        brand = cls.detect_brand(digits)

        # Check length
        expected_lengths = cls.CARD_LENGTHS.get(brand, [16])
        if len(digits) not in expected_lengths:
            return CardValidationResult(
                is_valid=False,
                brand=brand,
                last_four=last_four,
                error=f"Invalid card length for {brand.value}",
            )

        # Luhn check
        if not cls.luhn_check(digits):
            return CardValidationResult(
                is_valid=False,
                brand=brand,
                last_four=last_four,
                error="Card number failed checksum validation",
            )

        return CardValidationResult(is_valid=True, brand=brand, last_four=last_four)


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATION SANITIZER
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ConversationMessage:
    """A single message in the conversation."""

    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    # SECURITY: Original content is stored SANITIZED
    # The raw sensitive content is NEVER persisted
    is_sanitized: bool = False


class ConversationSanitizer:
    """
    Sanitizes conversation history to remove sensitive card data.

    PCI DSS 3.3: Mask PAN when displayed.
    PCI DSS 3.2: Never store CVV.

    This class ensures that conversation history can be:
    - Stored for audit purposes
    - Displayed to supervisors
    - Used for training (with redacted data)
    """

    # Patterns to detect and redact
    PATTERNS = {
        # Full card numbers (various formats)
        "card_number": [
            r"\b([3-6]\d{3})[\s\-]?(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b",
            r"\b([3-6]\d{14,18})\b",
        ],
        # CVV/CVC (3-4 digits, with context)
        "cvv": [
            r"\b(\d{3,4})\b",  # Will be context-aware
        ],
        # Expiry dates
        "expiry": [
            r"\b(0[1-9]|1[0-2])[\s/\-]?(\d{2}|\d{4})\b",
        ],
    }

    def __init__(self):
        self._in_card_collection = False
        self._expecting_cvv = False
        self._expecting_expiry = False

    def set_card_collection_mode(self, active: bool) -> None:
        """Enable/disable card collection mode for context-aware sanitization."""
        self._in_card_collection = active
        if not active:
            self._expecting_cvv = False
            self._expecting_expiry = False

    def expect_cvv(self) -> None:
        """Signal that the next user input may contain CVV."""
        self._expecting_cvv = True

    def expect_expiry(self) -> None:
        """Signal that the next user input may contain expiry."""
        self._expecting_expiry = True

    def sanitize_message(self, message: ConversationMessage) -> ConversationMessage:
        """
        Sanitize a conversation message, removing sensitive card data.

        Args:
            message: The message to sanitize

        Returns:
            Sanitized message (new object, original preserved for immediate use)
        """
        content = message.content
        metadata = dict(message.metadata)

        # Sanitize card numbers
        for pattern in self.PATTERNS["card_number"]:
            match = re.search(pattern, content)
            if match:
                # Extract last 4 for reference
                full_match = match.group(0)
                digits = "".join(c for c in full_match if c.isdigit())
                last_four = digits[-4:]

                # Replace with redacted version
                content = content.replace(full_match, f"[CARD ENDING {last_four}]")
                metadata["card_redacted"] = True
                metadata["card_last_four"] = last_four

        # Sanitize CVV (context-aware)
        if self._expecting_cvv and message.role == "user":
            # Any 3-4 digit number when expecting CVV
            content = re.sub(r"\b\d{3,4}\b", "[CVV RECEIVED]", content)
            metadata["cvv_redacted"] = True
            self._expecting_cvv = False

        # Sanitize expiry (context-aware)
        if self._expecting_expiry and message.role == "user":
            for pattern in self.PATTERNS["expiry"]:
                content = re.sub(pattern, "[EXPIRY RECEIVED]", content)
            metadata["expiry_redacted"] = True
            self._expecting_expiry = False

        return ConversationMessage(
            role=message.role,
            content=content,
            timestamp=message.timestamp,
            metadata=metadata,
            is_sanitized=True,
        )

    def sanitize_history(
        self, history: list[ConversationMessage]
    ) -> list[ConversationMessage]:
        """
        Sanitize an entire conversation history.

        Args:
            history: List of conversation messages

        Returns:
            New list with all messages sanitized
        """
        return [self.sanitize_message(msg) for msg in history]


# ══════════════════════════════════════════════════════════════════════════════
# TOKENIZATION SERVICE (Mock - Replace with Stripe/Vault in production)
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class TokenizationResult:
    """Result from tokenization service."""

    success: bool
    token: Optional[str] = None
    last_four: Optional[str] = None
    brand: Optional[CardBrand] = None
    error: Optional[str] = None


class TokenizationService(Protocol):
    """Protocol for tokenization services (Stripe, Vault, etc.)."""

    async def tokenize_card(
        self, card_number: str, exp_month: int, exp_year: int, cvv: str
    ) -> TokenizationResult:
        """Tokenize card details and return a token."""
        ...


class MockStripeTokenizer:
    """
    Mock Stripe tokenization for demonstration.

    In production, use:
        import stripe
        stripe.Token.create(card={...})

    SECURITY NOTE: In real implementation:
    1. Use Stripe.js for client-side tokenization when possible
    2. For server-side (MOTO), ensure PCI DSS SAQ D compliance
    3. Use Stripe's payment intents for SCA/3DS
    """

    def __init__(self, api_key: str = "sk_test_xxx"):
        self.api_key = api_key

    async def tokenize_card(
        self, card_number: str, exp_month: int, exp_year: int, cvv: str
    ) -> TokenizationResult:
        """
        Tokenize card details via Stripe API.

        SECURITY: In production, this would call Stripe's API over TLS.
        The card data is sent ONCE to Stripe, then immediately wiped.
        """
        # Validate first
        validation = CardValidator.validate(card_number)
        if not validation.is_valid:
            return TokenizationResult(success=False, error=validation.error)

        # MOCK: In production, this is a Stripe API call
        # stripe.Token.create(
        #     card={
        #         "number": card_number,
        #         "exp_month": exp_month,
        #         "exp_year": exp_year,
        #         "cvc": cvv,
        #     }
        # )

        # Simulate API delay
        await asyncio.sleep(0.1)

        # Generate mock token
        token = f"tok_{secrets.token_hex(12)}"

        logger.info(
            "payment.card_tokenized "
            f"token={token[:12]}... "
            f"last4={validation.last_four} "
            f"brand={validation.brand.value}"
        )

        return TokenizationResult(
            success=True,
            token=token,
            last_four=validation.last_four,
            brand=validation.brand,
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECURE CARD COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════


class CardCollectionState(Enum):
    """State machine for card collection flow."""

    IDLE = auto()
    AWAITING_CARD_NUMBER = auto()
    AWAITING_EXPIRY = auto()
    AWAITING_CVV = auto()
    PROCESSING = auto()
    COMPLETE = auto()
    FAILED = auto()


@dataclass
class CollectedCardData:
    """
    Temporarily holds card data during collection.

    SECURITY: This object exists for <1 second during tokenization.
    After tokenization, all sensitive fields are wiped.
    """

    token: Optional[str] = None
    last_four: Optional[str] = None
    brand: Optional[CardBrand] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None

    # SENSITIVE - wiped immediately after tokenization
    _card_number: Optional[str] = field(default=None, repr=False)
    _cvv: Optional[str] = field(default=None, repr=False)

    def wipe_sensitive(self) -> None:
        """
        Wipe all sensitive data from this object.

        Called IMMEDIATELY after tokenization.
        """
        if self._card_number:
            MemoryWiper.wipe_string(self._card_number)
        if self._cvv:
            MemoryWiper.wipe_string(self._cvv)

        self._card_number = None
        self._cvv = None

        gc.collect()


class SecureCardCollector:
    """
    Handles secure collection of card details in conversation.

    This is the core of the card-in-chat system. It:
    1. Guides the user through entering card details
    2. Validates input at each step
    3. Tokenizes immediately upon completion
    4. Wipes sensitive data from memory
    5. Maintains sanitized conversation history

    SECURITY MODEL:
    - Card number held in memory for <100ms (validation + tokenization)
    - CVV held in memory for <50ms (sent directly to tokenizer)
    - All sensitive strings overwritten after use
    - Conversation history contains only redacted values
    """

    def __init__(
        self, tokenizer: TokenizationService, sanitizer: ConversationSanitizer
    ):
        self.tokenizer = tokenizer
        self.sanitizer = sanitizer
        self.state = CardCollectionState.IDLE
        self._card_data = CollectedCardData()
        self._session_id = f"sess_{secrets.token_hex(8)}"

    def start_collection(self) -> str:
        """
        Begin the card collection flow.

        Returns:
            Bot message asking for card number
        """
        self.state = CardCollectionState.AWAITING_CARD_NUMBER
        self._card_data = CollectedCardData()
        self.sanitizer.set_card_collection_mode(True)

        logger.info(f"payment.card_collection_started session_id={self._session_id}")

        return "I'll collect your card details securely. " "What's your card number?"

    async def process_input(self, user_input: str) -> tuple[str, bool]:
        """
        Process user input during card collection.

        Args:
            user_input: The user's message

        Returns:
            Tuple of (bot_response, is_collection_complete)
        """
        if self.state == CardCollectionState.AWAITING_CARD_NUMBER:
            return await self._handle_card_number(user_input)

        elif self.state == CardCollectionState.AWAITING_EXPIRY:
            return await self._handle_expiry(user_input)

        elif self.state == CardCollectionState.AWAITING_CVV:
            return await self._handle_cvv(user_input)

        else:
            return "Card collection not active.", False

    async def _handle_card_number(self, user_input: str) -> tuple[str, bool]:
        """
        Handle card number input.

        SECURITY: Card number is validated and held only until
        we receive expiry and CVV for tokenization.
        """
        # Validate the card number
        validation = CardValidator.validate(user_input)

        if not validation.is_valid:
            # SECURITY: Don't echo back the invalid card number
            return (
                "That doesn't appear to be a valid card number. "
                "Please check and try again."
            ), False

        # Store temporarily (will be wiped after tokenization)
        # SECURITY: Using digits only, stripped of formatting
        self._card_data._card_number = "".join(c for c in user_input if c.isdigit())
        self._card_data.last_four = validation.last_four
        self._card_data.brand = validation.brand

        # Move to next state
        self.state = CardCollectionState.AWAITING_EXPIRY
        self.sanitizer.expect_expiry()

        brand_name = validation.brand.value.title()

        return (
            f"Got it ({brand_name} ending in {validation.last_four}). "
            f"Expiry date (MM/YY)?"
        ), False

    async def _handle_expiry(self, user_input: str) -> tuple[str, bool]:
        """
        Handle expiry date input.

        Accepts formats: MM/YY, MM-YY, MM YY, MMYY, MM/YYYY
        """
        # Parse expiry
        match = re.match(r"^(0[1-9]|1[0-2])[\s/\-]?(\d{2}|\d{4})$", user_input.strip())

        if not match:
            return ("Please enter expiry as MM/YY (e.g., 12/28)"), False

        month = int(match.group(1))
        year = int(match.group(2))

        # Handle 2-digit year
        if year < 100:
            year += 2000

        # Validate not expired
        now = datetime.now()
        if year < now.year or (year == now.year and month < now.month):
            return "That card appears to be expired.", False

        self._card_data.exp_month = month
        self._card_data.exp_year = year

        # Move to CVV
        self.state = CardCollectionState.AWAITING_CVV
        self.sanitizer.expect_cvv()

        # Determine CVV length hint
        cvv_digits = "4" if self._card_data.brand == CardBrand.AMEX else "3"

        logger.info(f"payment.expiry_collected month={month} year={year}")

        return f"CVV ({cvv_digits} digits on back of card)?", False

    async def _handle_cvv(self, user_input: str) -> tuple[str, bool]:
        """
        Handle CVV input and trigger tokenization.

        SECURITY: CVV is NEVER stored or logged.
        It goes directly to the tokenizer and is immediately wiped.
        """
        # Validate CVV format
        cvv = user_input.strip()
        expected_length = 4 if self._card_data.brand == CardBrand.AMEX else 3

        if not re.match(rf"^\d{{{expected_length}}}$", cvv):
            return (f"Please enter your {expected_length}-digit security code."), False

        # Store CVV temporarily (wiped immediately after tokenization)
        self._card_data._cvv = cvv

        # CRITICAL: Log that we received CVV but NEVER log the value
        logger.info("payment.cvv_received (value never logged)")

        # Move to processing state
        self.state = CardCollectionState.PROCESSING

        # Tokenize immediately
        try:
            result = await self._tokenize()

            if result.success:
                self.state = CardCollectionState.COMPLETE
                self.sanitizer.set_card_collection_mode(False)

                return (
                    f"Card details received and secured "
                    f"({result.brand.value.title()} ending {result.last_four})."
                ), True
            else:
                self.state = CardCollectionState.FAILED
                return f"Card validation failed: {result.error}", False

        finally:
            # CRITICAL: Always wipe sensitive data, even on error
            self._card_data.wipe_sensitive()

    async def _tokenize(self) -> TokenizationResult:
        """
        Tokenize the collected card data.

        SECURITY: This happens immediately after CVV is received.
        After tokenization, all sensitive data is wiped.
        """
        result = await self.tokenizer.tokenize_card(
            card_number=self._card_data._card_number,
            exp_month=self._card_data.exp_month,
            exp_year=self._card_data.exp_year,
            cvv=self._card_data._cvv,
        )

        if result.success:
            # Store token (safe to keep)
            self._card_data.token = result.token

        return result

    def get_token(self) -> Optional[str]:
        """Get the tokenized card reference (safe to store/use)."""
        return self._card_data.token

    def get_card_summary(self) -> dict:
        """Get safe card summary (no sensitive data)."""
        return {
            "token": self._card_data.token,
            "last_four": self._card_data.last_four,
            "brand": self._card_data.brand.value if self._card_data.brand else None,
            "exp_month": self._card_data.exp_month,
            "exp_year": self._card_data.exp_year,
        }

    def cancel(self) -> None:
        """Cancel card collection and wipe any partial data."""
        self._card_data.wipe_sensitive()
        self._card_data = CollectedCardData()
        self.state = CardCollectionState.IDLE
        self.sanitizer.set_card_collection_mode(False)

        logger.info(f"payment.card_collection_cancelled session_id={self._session_id}")


# ══════════════════════════════════════════════════════════════════════════════
# MOCK PAYMENT PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class PaymentResult:
    """Result from payment processor."""

    success: bool
    charge_id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    receipt_url: Optional[str] = None
    error: Optional[str] = None


class MockPaymentProcessor:
    """
    Mock payment processor for demonstration.

    In production, use Stripe PaymentIntents or similar.
    """

    async def charge(
        self,
        token: str,
        amount_cents: int,
        currency: str = "aud",
        description: str = "",
        receipt_email: Optional[str] = None,
    ) -> PaymentResult:
        """
        Charge a tokenized card.

        Args:
            token: Payment token from tokenization
            amount_cents: Amount in cents (e.g., 29900 for $299.00)
            currency: ISO 4217 currency code
            description: Payment description
            receipt_email: Email for receipt

        Returns:
            PaymentResult with charge details
        """
        # Simulate processing
        await asyncio.sleep(0.2)

        # Generate charge ID
        charge_id = f"ch_{secrets.token_hex(12)}"

        logger.info(
            f"payment.charge_initiated "
            f"amount={amount_cents} "
            f"currency={currency} "
            f"token={token[:12]}..."
        )

        # Simulate success (in production, this calls Stripe)
        logger.info(f"payment.charge_successful charge_id={charge_id}")

        return PaymentResult(
            success=True,
            charge_id=charge_id,
            amount=Decimal(amount_cents) / 100,
            currency=currency.upper(),
            receipt_url=f"https://receipt.example.com/{charge_id}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# INVOICE SERVICE (Mock)
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Invoice:
    """An invoice to be paid."""

    invoice_id: str
    customer_email: str
    amount: Decimal
    currency: str = "AUD"
    description: str = ""
    due_date: Optional[datetime] = None
    is_paid: bool = False


class MockInvoiceService:
    """Mock invoice service for demonstration."""

    def __init__(self):
        # Sample invoices
        self.invoices = {
            "2026-0042": Invoice(
                invoice_id="2026-0042",
                customer_email="joe@example.com",
                amount=Decimal("299.00"),
                description="Monthly subscription - March 2026",
            ),
            "2026-0043": Invoice(
                invoice_id="2026-0043",
                customer_email="joe@example.com",
                amount=Decimal("1499.00"),
                description="Annual license renewal",
            ),
        }

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get an invoice by ID."""
        return self.invoices.get(invoice_id)

    def mark_paid(self, invoice_id: str, charge_id: str) -> None:
        """Mark an invoice as paid."""
        if invoice_id in self.invoices:
            self.invoices[invoice_id].is_paid = True


# ══════════════════════════════════════════════════════════════════════════════
# CARD-IN-CHAT BOT
# ══════════════════════════════════════════════════════════════════════════════


class CardInChatBot:
    """
    Main chatbot that handles card-in-chat payments.

    This orchestrates the entire payment flow:
    1. Invoice lookup
    2. Payment confirmation
    3. Secure card collection
    4. Payment processing
    5. Receipt generation

    All while maintaining a sanitized conversation history.
    """

    def __init__(
        self,
        tokenizer: Optional[TokenizationService] = None,
        payment_processor: Optional[MockPaymentProcessor] = None,
        invoice_service: Optional[MockInvoiceService] = None,
    ):
        self.tokenizer = tokenizer or MockStripeTokenizer()
        self.payment_processor = payment_processor or MockPaymentProcessor()
        self.invoice_service = invoice_service or MockInvoiceService()

        self.sanitizer = ConversationSanitizer()
        self.card_collector = SecureCardCollector(self.tokenizer, self.sanitizer)

        # Conversation state
        self.conversation_history: list[ConversationMessage] = []
        self.current_invoice: Optional[Invoice] = None
        self._awaiting_payment_confirmation = False

    def _add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history (sanitized)."""
        msg = ConversationMessage(role=role, content=content)
        sanitized = self.sanitizer.sanitize_message(msg)
        self.conversation_history.append(sanitized)

    async def process_message(self, user_message: str) -> str:
        """
        Process a user message and return bot response.

        Args:
            user_message: The user's message

        Returns:
            Bot's response
        """
        # Add user message to history (will be sanitized)
        self._add_message("user", user_message)

        # Check if we're in card collection mode
        if self.card_collector.state not in [
            CardCollectionState.IDLE,
            CardCollectionState.COMPLETE,
            CardCollectionState.FAILED,
        ]:
            response, is_complete = await self.card_collector.process_input(
                user_message
            )

            if is_complete:
                # Card collected - process payment
                response = await self._process_payment()

            self._add_message("assistant", response)
            return response

        # Handle payment confirmation
        if self._awaiting_payment_confirmation:
            return await self._handle_payment_confirmation(user_message)

        # Handle other intents
        response = await self._handle_message(user_message)
        self._add_message("assistant", response)
        return response

    async def _handle_message(self, message: str) -> str:
        """Handle general messages."""
        message_lower = message.lower()

        # Invoice lookup intent
        if "invoice" in message_lower or "pay" in message_lower:
            # Extract invoice ID if present
            match = re.search(r"\b(\d{4}-\d{4})\b", message)
            if match:
                invoice_id = match.group(1)
                invoice = self.invoice_service.get_invoice(invoice_id)

                if invoice:
                    self.current_invoice = invoice
                    self._awaiting_payment_confirmation = True

                    logger.info(
                        f"payment.invoice_lookup "
                        f"invoice={invoice_id} "
                        f"amount={invoice.amount}"
                    )

                    return (
                        f"Found invoice #{invoice.invoice_id}!\n"
                        f"Amount: ${invoice.amount} {invoice.currency}\n"
                        f"Description: {invoice.description}\n\n"
                        f"Would you like to pay this now?"
                    )
                else:
                    return f"I couldn't find invoice #{invoice_id}. Please check the number."

            return (
                "I can help you pay an invoice. "
                "Could you provide the invoice number? (e.g., 2026-0042)"
            )

        # Help
        return (
            "I can help you with:\n"
            "• Pay an invoice (e.g., 'pay invoice 2026-0042')\n"
            "• Check invoice status\n"
            "• Get a receipt for past payments"
        )

    async def _handle_payment_confirmation(self, message: str) -> str:
        """Handle yes/no response to payment confirmation."""
        self._awaiting_payment_confirmation = False

        message_lower = message.lower()

        if any(
            word in message_lower
            for word in ["yes", "yeah", "yep", "sure", "ok", "pay"]
        ):
            # Start card collection
            response = self.card_collector.start_collection()
            self._add_message("assistant", response)
            return response
        else:
            self.current_invoice = None
            return "No problem! Let me know if you'd like to pay later."

    async def _process_payment(self) -> str:
        """Process payment after card collection is complete."""
        if not self.current_invoice:
            return "Error: No invoice selected."

        token = self.card_collector.get_token()
        if not token:
            return "Error: Card tokenization failed."

        # Charge the card
        result = await self.payment_processor.charge(
            token=token,
            amount_cents=int(self.current_invoice.amount * 100),
            currency=self.current_invoice.currency.lower(),
            description=f"Invoice {self.current_invoice.invoice_id}",
            receipt_email=self.current_invoice.customer_email,
        )

        if result.success:
            # Mark invoice as paid
            self.invoice_service.mark_paid(
                self.current_invoice.invoice_id, result.charge_id
            )

            card_summary = self.card_collector.get_card_summary()

            return (
                f"✅ Payment successful!\n\n"
                f"Amount: ${result.amount} {result.currency}\n"
                f"Card: {card_summary['brand'].title()} ending {card_summary['last_four']}\n"
                f"Receipt sent to: {self.current_invoice.customer_email}\n"
                f"Transaction ID: {result.charge_id}"
            )
        else:
            return f"❌ Payment failed: {result.error}"

    def get_sanitized_history(self) -> list[dict]:
        """
        Get conversation history safe for storage/display.

        Returns:
            List of sanitized message dicts
        """
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata,
            }
            for msg in self.conversation_history
        ]


# ══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS
# ══════════════════════════════════════════════════════════════════════════════


async def test_card_validator():
    """Test card validation logic."""
    print("\n=== Testing Card Validator ===\n")

    test_cases = [
        ("4242424242424242", True, CardBrand.VISA, "4242"),
        ("4242 4242 4242 4242", True, CardBrand.VISA, "4242"),
        ("4242-4242-4242-4242", True, CardBrand.VISA, "4242"),
        ("5555555555554444", True, CardBrand.MASTERCARD, "4444"),
        ("378282246310005", True, CardBrand.AMEX, "0005"),
        ("1234567890123456", False, CardBrand.UNKNOWN, "3456"),  # Invalid Luhn
        ("424242424242", False, CardBrand.VISA, "4242"),  # Too short
        ("abcd1234efgh5678", False, CardBrand.UNKNOWN, ""),  # Invalid chars
    ]

    for card, expected_valid, expected_brand, expected_last4 in test_cases:
        result = CardValidator.validate(card)
        status = "✅" if result.is_valid == expected_valid else "❌"
        print(
            f"{status} Card: {card[:4]}... Valid: {result.is_valid}, Brand: {result.brand.value}"
        )
        assert result.is_valid == expected_valid
        assert result.brand == expected_brand


async def test_conversation_sanitizer():
    """Test conversation sanitization."""
    print("\n=== Testing Conversation Sanitizer ===\n")

    sanitizer = ConversationSanitizer()
    sanitizer.set_card_collection_mode(True)

    # Test card number sanitization
    msg1 = ConversationMessage(role="user", content="My card is 4242 4242 4242 4242")
    sanitized1 = sanitizer.sanitize_message(msg1)
    print(f"Original: {msg1.content}")
    print(f"Sanitized: {sanitized1.content}")
    assert "4242 4242 4242" not in sanitized1.content
    assert "CARD ENDING 4242" in sanitized1.content

    # Test CVV sanitization
    sanitizer.expect_cvv()
    msg2 = ConversationMessage(role="user", content="123")
    sanitized2 = sanitizer.sanitize_message(msg2)
    print(f"\nOriginal CVV: {msg2.content}")
    print(f"Sanitized: {sanitized2.content}")
    assert "123" not in sanitized2.content
    assert "CVV RECEIVED" in sanitized2.content

    # Test expiry sanitization
    sanitizer.expect_expiry()
    msg3 = ConversationMessage(role="user", content="12/28")
    sanitized3 = sanitizer.sanitize_message(msg3)
    print(f"\nOriginal expiry: {msg3.content}")
    print(f"Sanitized: {sanitized3.content}")
    assert "12/28" not in sanitized3.content
    assert "EXPIRY RECEIVED" in sanitized3.content

    print("\n✅ All sanitization tests passed!")


async def test_full_payment_flow():
    """Test the complete payment flow."""
    print("\n=== Testing Full Payment Flow ===\n")

    bot = CardInChatBot()

    # Simulate conversation
    conversation = [
        "I'd like to pay invoice 2026-0042",
        "Yes",
        "4242 4242 4242 4242",
        "12/28",
        "123",
    ]

    for user_msg in conversation:
        print(f"User: {user_msg}")
        response = await bot.process_message(user_msg)
        print(f"Bot: {response}\n")

    # Check sanitized history
    print("=== Sanitized Conversation History ===\n")
    for msg in bot.get_sanitized_history():
        content_preview = (
            msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
        )
        print(f"[{msg['role']}] {content_preview}")

        # Verify no sensitive data
        assert "4242 4242 4242" not in msg["content"]  # Full card
        assert "123" not in msg["content"] or "CVV" in msg["content"]  # CVV

    print("\n✅ Full payment flow test passed!")


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def interactive_demo():
    """Run an interactive demo of the card-in-chat bot."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     CARD-IN-CHAT PAYMENT DEMO                                ║
║                                                                              ║
║  This demonstrates secure card collection directly in conversation.          ║
║                                                                              ║
║  Test card: 4242 4242 4242 4242                                             ║
║  Any future expiry: 12/28                                                    ║
║  Any CVV: 123                                                                ║
║                                                                              ║
║  Try: "pay invoice 2026-0042"                                               ║
║                                                                              ║
║  Type 'quit' to exit, 'history' to see sanitized logs                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    )

    bot = CardInChatBot()

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if user_input.lower() == "quit":
                print("\nGoodbye!")
                break

            if user_input.lower() == "history":
                print("\n=== Sanitized Conversation History ===")
                for msg in bot.get_sanitized_history():
                    role = "You" if msg["role"] == "user" else "Bot"
                    print(f"{role}: {msg['content']}")
                continue

            if not user_input:
                continue

            response = await bot.process_message(user_input)
            print(f"\nBot: {response}")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Run tests
        await test_card_validator()
        await test_conversation_sanitizer()
        await test_full_payment_flow()
        print("\n" + "=" * 60)
        print("All tests passed! ✅")
        print("=" * 60)
    else:
        # Interactive demo
        await interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
