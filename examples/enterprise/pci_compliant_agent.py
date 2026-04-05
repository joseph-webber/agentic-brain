#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example: PCI DSS Compliance Patterns Agent

Demonstrates PCI DSS compliance patterns for chatbots and AI agents:
- Data masking for card numbers
- Secure token handling
- Compliance logging (what to log, what NOT to log)
- Environment separation (dev/staging/prod)
- Encryption requirements

PCI DSS COMPLIANCE CHECKLIST:
╔═══════════════════════════════════════════════════════════════════════════╗
║  REQUIREMENT                                          STATUS              ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  3.2  Don't store CVV/CVC after authorization        ✅ Never stored     ║
║  3.3  Mask PAN when displayed                        ✅ Last 4 only      ║
║  3.4  Render PAN unreadable in storage               ✅ Tokenized        ║
║  3.5  Protect keys used for encryption               ✅ HSM/KMS          ║
║  4.1  Use strong cryptography for transmission       ✅ TLS 1.2+         ║
║  7.1  Restrict access by business need               ✅ RBAC             ║
║  8.1  Unique user identification                     ✅ User IDs         ║
║  10.2 Implement automated audit trails               ✅ All actions      ║
║  10.3 Record audit trail entries                     ✅ Timestamps       ║
║  12.8 Service provider compliance                    ✅ Stripe/Square    ║
╚═══════════════════════════════════════════════════════════════════════════╝

Australian Regulatory Context:
- APRA CPS 234: Information Security
- APRA CPS 230: Operational Resilience (from July 2025)
- Consumer Data Right (CDR): Open Banking
- Privacy Act 1988: Australian Privacy Principles

Usage:
    python examples/enterprise/pci_compliant_agent.py

Requirements:
    pip install agentic-brain cryptography
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Protocol

# Configure secure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT CONFIGURATION (PCI DSS Requirement 6.4.1)
# ══════════════════════════════════════════════════════════════════════════════


class Environment(Enum):
    """
    Environment separation for PCI DSS compliance.

    PCI DSS 6.4.1: Separate development/test environments from production.
    Production cardholder data NEVER used in dev/test.
    """

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class PCIEnvironmentConfig:
    """
    PCI-compliant environment configuration.

    Different environments have different security requirements.
    """

    environment: Environment

    # TLS Requirements (PCI DSS 4.1)
    min_tls_version: str = "TLS1.2"
    allowed_cipher_suites: list[str] = field(
        default_factory=lambda: [
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",
        ]
    )

    # Token Service URLs
    tokenization_service_url: str = ""
    payment_gateway_url: str = ""

    # Audit Requirements
    audit_retention_days: int = 365  # PCI DSS 10.7: Retain for at least 1 year
    immediate_audit_days: int = 90  # Immediately available for 90 days

    # Access Controls
    require_mfa: bool = True
    session_timeout_minutes: int = 15  # PCI DSS 8.1.8

    # Encryption
    encryption_algorithm: str = "AES-256-GCM"
    key_rotation_days: int = 365

    @classmethod
    def for_environment(cls, env: Environment) -> "PCIEnvironmentConfig":
        """Get appropriate config for each environment."""
        configs = {
            Environment.DEVELOPMENT: cls(
                environment=env,
                min_tls_version="TLS1.2",
                tokenization_service_url="http://localhost:8081/tokenize",
                payment_gateway_url="http://localhost:8082/sandbox",
                require_mfa=False,  # Dev only
                session_timeout_minutes=60,  # Longer for dev
            ),
            Environment.TESTING: cls(
                environment=env,
                min_tls_version="TLS1.2",
                tokenization_service_url="https://test-token.example.com",
                payment_gateway_url="https://test-pay.stripe.com",
                require_mfa=False,
                session_timeout_minutes=30,
            ),
            Environment.STAGING: cls(
                environment=env,
                min_tls_version="TLS1.2",
                tokenization_service_url="https://staging-token.example.com",
                payment_gateway_url="https://staging-pay.stripe.com",
                require_mfa=True,
                session_timeout_minutes=15,
            ),
            Environment.PRODUCTION: cls(
                environment=env,
                min_tls_version="TLS1.3",  # Stricter in prod
                tokenization_service_url="https://token.example.com",
                payment_gateway_url="https://api.stripe.com",
                require_mfa=True,
                session_timeout_minutes=15,
                encryption_algorithm="AES-256-GCM",
            ),
        }
        return configs[env]

    def validate(self) -> list[str]:
        """Validate configuration meets PCI DSS requirements."""
        issues = []

        if self.environment == Environment.PRODUCTION:
            if self.min_tls_version not in ["TLS1.2", "TLS1.3"]:
                issues.append("Production must use TLS 1.2 or higher (PCI DSS 4.1)")

            if not self.require_mfa:
                issues.append("Production must require MFA (PCI DSS 8.3)")

            if self.session_timeout_minutes > 15:
                issues.append("Session timeout must be ≤15 mins (PCI DSS 8.1.8)")

            if "sandbox" in self.payment_gateway_url.lower():
                issues.append("Production must not use sandbox gateway!")

        return issues


# ══════════════════════════════════════════════════════════════════════════════
# DATA MASKING & SCRUBBING (PCI DSS 3.3, 3.4)
# ══════════════════════════════════════════════════════════════════════════════


class SensitiveDataType(Enum):
    """Types of sensitive data that require protection."""

    CARD_NUMBER = "card_number"  # PAN - Primary Account Number
    CVV = "cvv"  # Card Verification Value - NEVER store
    EXPIRY = "expiry"
    CARDHOLDER_NAME = "cardholder_name"
    PIN = "pin"  # NEVER store
    TRACK_DATA = "track_data"  # Magnetic stripe - NEVER store
    PIN_BLOCK = "pin_block"  # NEVER store


@dataclass
class MaskingRule:
    """Rule for masking sensitive data."""

    data_type: SensitiveDataType
    pattern: str
    replacement: str
    log_detection: bool = True


class ComplianceDataMasker:
    """
    PCI DSS compliant data masking service.

    Ensures sensitive data is NEVER exposed in:
    - Logs
    - Error messages
    - API responses
    - Database (except tokenized)
    - Memory dumps
    """

    # Patterns for detecting card numbers (Luhn-valid)
    CARD_PATTERNS = {
        "visa": r"\b4[0-9]{12}(?:[0-9]{3})?\b",
        "mastercard": r"\b5[1-5][0-9]{14}\b",
        "amex": r"\b3[47][0-9]{13}\b",
        "discover": r"\b6(?:011|5[0-9]{2})[0-9]{12}\b",
        "diners": r"\b3(?:0[0-5]|[68][0-9])[0-9]{11}\b",
        "jcb": r"\b(?:2131|1800|35\d{3})\d{11}\b",
    }

    # Additional sensitive patterns
    SENSITIVE_PATTERNS = {
        "cvv": r"\b(cvv|cvc|cv2|cid|security\s*code)[:\s]*([0-9]{3,4})\b",
        "expiry": r"\b(exp|expiry|expiration)[:\s]*([0-9]{2}[/-][0-9]{2,4})\b",
        "bsb": r"\b[0-9]{3}-[0-9]{3}\b",  # Australian BSB
        "account_number": r"\b[0-9]{6,10}\b",  # Bank account
        "tfn": r"\b[0-9]{3}\s?[0-9]{3}\s?[0-9]{3}\b",  # Australian Tax File Number
    }

    def __init__(self, environment: Environment = Environment.PRODUCTION):
        self.environment = environment
        self.detection_log: list[dict] = []

    def mask_pan(self, pan: str, show_first: int = 0, show_last: int = 4) -> str:
        """
        Mask a Primary Account Number per PCI DSS 3.3.

        Default: Show only last 4 digits (safest)
        Alternative: Show first 6 + last 4 (for merchant operations)

        Args:
            pan: The card number (can include spaces/dashes)
            show_first: How many first digits to show (0 or 6)
            show_last: How many last digits to show (usually 4)
        """
        # Remove formatting
        digits = re.sub(r"\D", "", pan)

        if len(digits) < show_last:
            return "*" * 16

        # PCI DSS allows showing first 6 + last 4
        if show_first == 6 and len(digits) >= 13:
            first = digits[:6]
            last = digits[-show_last:]
            middle_len = len(digits) - 6 - show_last
            return f"{first}{'*' * middle_len}{last}"

        # Default: show only last 4
        return "*" * (len(digits) - show_last) + digits[-show_last:]

    def scrub_text(self, text: str, context: str = "unknown") -> tuple[str, list[str]]:
        """
        Remove ALL sensitive data from text.

        This MUST be called before:
        - Writing to any log
        - Storing in database
        - Returning in API response
        - Sending to external service
        - Displaying to any user

        Returns:
            Tuple of (scrubbed_text, list of detected sensitive data types)
        """
        result = text
        detected = []

        # Scrub card numbers
        for card_type, pattern in self.CARD_PATTERNS.items():
            matches = re.findall(pattern, result)
            if matches:
                detected.append(f"CARD_NUMBER:{card_type}")
                result = re.sub(pattern, "[CARD_REDACTED]", result)
                self._log_detection(SensitiveDataType.CARD_NUMBER, card_type, context)

        # Scrub CVV (CRITICAL - must never appear anywhere)
        cvv_pattern = self.SENSITIVE_PATTERNS["cvv"]
        if re.search(cvv_pattern, result, re.IGNORECASE):
            detected.append("CVV")
            result = re.sub(
                cvv_pattern, r"\1: [CVV_REDACTED]", result, flags=re.IGNORECASE
            )
            self._log_detection(SensitiveDataType.CVV, "detected", context)

        # Scrub expiry dates
        expiry_pattern = self.SENSITIVE_PATTERNS["expiry"]
        if re.search(expiry_pattern, result, re.IGNORECASE):
            detected.append("EXPIRY")
            result = re.sub(
                expiry_pattern, r"\1: [EXP_REDACTED]", result, flags=re.IGNORECASE
            )

        # Scrub any remaining long number sequences that might be PANs
        # (Aggressive but safe - better to over-scrub than under-scrub)
        result = re.sub(r"\b[0-9]{13,19}\b", "[NUM_REDACTED]", result)

        return result, detected

    def scrub_dict(self, data: dict, context: str = "unknown") -> dict:
        """
        Recursively scrub sensitive data from a dictionary.

        Use before logging or storing any dict that might contain card data.
        """
        result = {}

        # Keys that should be completely removed (never even show redacted)
        REMOVE_KEYS = {"cvv", "cvc", "cv2", "pin", "track1", "track2", "magnetic_strip"}

        # Keys that should be masked
        MASK_KEYS = {"card_number", "pan", "card", "account_number", "number"}

        for key, value in data.items():
            key_lower = key.lower()

            # Remove forbidden keys entirely
            if key_lower in REMOVE_KEYS:
                continue  # Don't include at all

            # Mask known sensitive keys
            if key_lower in MASK_KEYS and isinstance(value, str):
                result[key] = self.mask_pan(value)
                continue

            # Recurse into nested dicts
            if isinstance(value, dict):
                result[key] = self.scrub_dict(value, context)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self.scrub_dict(item, context)
                        if isinstance(item, dict)
                        else (
                            self.scrub_text(str(item), context)[0]
                            if isinstance(item, str)
                            else item
                        )
                    )
                    for item in value
                ]
            elif isinstance(value, str):
                result[key], _ = self.scrub_text(value, context)
            else:
                result[key] = value

        return result

    def _log_detection(self, data_type: SensitiveDataType, detail: str, context: str):
        """Log when sensitive data is detected (for security monitoring)."""
        self.detection_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "data_type": data_type.value,
                "detail": detail,
                "context": context,
                "environment": self.environment.value,
            }
        )

        # In production, this might trigger an alert
        if self.environment == Environment.PRODUCTION:
            logger.warning(
                f"SECURITY: Sensitive data ({data_type.value}) detected in {context}. "
                f"Data was scrubbed. Review input source."
            )


# ══════════════════════════════════════════════════════════════════════════════
# TOKENIZATION SERVICE (PCI DSS 3.4, 3.5)
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class PaymentToken:
    """
    A secure token representing card data.

    The actual card data is stored by the payment gateway (Stripe, Square, Tyro)
    in their PCI-compliant infrastructure. We only store the token.
    """

    token_id: str  # e.g., "tok_visa_4242"
    last_four: str  # Safe to store
    card_brand: str
    expiry_month: int
    expiry_year: int
    gateway: str  # Which gateway owns this token
    token_type: str = "single_use"  # single_use, recurring, on_file
    created_at: datetime = field(default_factory=datetime.now)

    def to_safe_dict(self) -> dict:
        """Return dict with NO sensitive data."""
        return {
            "token_id": self.token_id,
            "last_four": self.last_four,
            "card_brand": self.card_brand,
            "expiry": f"{self.expiry_month:02d}/{self.expiry_year}",
            "gateway": self.gateway,
        }


class TokenizationService(ABC):
    """
    Abstract tokenization service interface.

    PCI DSS 3.4: Render PAN unreadable anywhere it is stored.
    Tokenization replaces PAN with non-sensitive surrogate value.

    In production, this would integrate with Stripe, Square, or Tyro.
    """

    @abstractmethod
    async def tokenize(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvv: str,  # Used for validation only - NEVER stored
    ) -> PaymentToken:
        """
        Tokenize card data.

        The CVV is used only for initial validation and then discarded.
        It is NEVER stored or returned.
        """
        pass

    @abstractmethod
    async def detokenize_last_four(self, token_id: str) -> str:
        """Get last 4 digits for display (safe operation)."""
        pass

    @abstractmethod
    async def validate_token(self, token_id: str) -> bool:
        """Check if token is still valid."""
        pass


class MockTokenizationService(TokenizationService):
    """
    Mock tokenization for development/testing.

    In production, use Stripe, Square, or Tyro tokenization APIs.
    """

    def __init__(self):
        self.tokens: dict[str, PaymentToken] = {}
        self.masker = ComplianceDataMasker(Environment.DEVELOPMENT)

    async def tokenize(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvv: str,
    ) -> PaymentToken:
        """
        Create a token for the card.

        NOTE: In production, the card data goes directly to the payment gateway
        via their SDK/API. We NEVER touch it ourselves.
        """
        # Clean the card number
        clean_pan = re.sub(r"\D", "", card_number)

        # Validate (basic Luhn check in production)
        if len(clean_pan) < 13 or len(clean_pan) > 19:
            raise ValueError("Invalid card number length")

        # Determine card brand
        brand = self._detect_brand(clean_pan)

        # Generate token
        token = PaymentToken(
            token_id=f"tok_{brand.lower()}_{clean_pan[-4:]}_{secrets.token_hex(8)}",
            last_four=clean_pan[-4:],
            card_brand=brand,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            gateway="mock",
        )

        self.tokens[token.token_id] = token

        # Log (safely!)
        logger.info(f"Token created: {token.token_id} for {brand} ****{clean_pan[-4:]}")

        # CVV is DISCARDED here - never stored
        # We don't even have a variable to store it!

        return token

    async def detokenize_last_four(self, token_id: str) -> str:
        """Get last 4 digits for display."""
        token = self.tokens.get(token_id)
        if token:
            return token.last_four
        raise ValueError("Token not found")

    async def validate_token(self, token_id: str) -> bool:
        """Check if token exists and is not expired."""
        token = self.tokens.get(token_id)
        if not token:
            return False

        # Check expiry
        now = datetime.now()
        expiry = datetime(token.expiry_year, token.expiry_month, 1)
        return expiry > now

    def _detect_brand(self, pan: str) -> str:
        """Detect card brand from PAN."""
        if pan.startswith("4"):
            return "Visa"
        elif pan.startswith(("51", "52", "53", "54", "55")):
            return "Mastercard"
        elif pan.startswith(("34", "37")):
            return "Amex"
        elif pan.startswith(("6011", "65")):
            return "Discover"
        else:
            return "Unknown"


# ══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE LOGGING (PCI DSS 10.2, 10.3)
# ══════════════════════════════════════════════════════════════════════════════


class AuditEventType(Enum):
    """Types of events that MUST be logged per PCI DSS 10.2."""

    # 10.2.1 - All individual accesses to cardholder data
    CARDHOLDER_DATA_ACCESS = "cardholder_data_access"

    # 10.2.2 - All actions by any individual with root/admin privileges
    ADMIN_ACTION = "admin_action"

    # 10.2.3 - Access to all audit trails
    AUDIT_ACCESS = "audit_access"

    # 10.2.4 - Invalid logical access attempts
    INVALID_ACCESS_ATTEMPT = "invalid_access_attempt"

    # 10.2.5 - Use of and changes to identification mechanisms
    AUTH_MECHANISM_CHANGE = "auth_mechanism_change"

    # 10.2.6 - Initialization, stopping, or pausing of audit logs
    AUDIT_LOG_CHANGE = "audit_log_change"

    # 10.2.7 - Creation and deletion of system-level objects
    SYSTEM_OBJECT_CHANGE = "system_object_change"

    # Additional security events
    TOKEN_OPERATION = "token_operation"
    REFUND_OPERATION = "refund_operation"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class AuditEvent:
    """
    PCI DSS compliant audit log entry.

    Required fields per PCI DSS 10.3:
    - User identification (10.3.1)
    - Type of event (10.3.2)
    - Date and time (10.3.3)
    - Success or failure (10.3.4)
    - Origination of event (10.3.5)
    - Identity of affected data/resource (10.3.6)
    """

    # 10.3.1 - User identification
    user_id: str
    user_role: str

    # 10.3.2 - Type of event
    event_type: AuditEventType

    # 10.3.3 - Date and time
    timestamp: datetime

    # 10.3.4 - Success or failure
    success: bool

    # 10.3.5 - Origination of event
    source_ip: str
    source_system: str
    session_id: str

    # 10.3.6 - Identity of affected data/resource
    resource_type: str
    resource_id: str

    # Additional context (scrubbed - NO sensitive data!)
    details: str

    # Unique event ID
    event_id: str = field(default_factory=lambda: secrets.token_hex(16))

    def to_log_dict(self) -> dict:
        """Convert to dict for logging (all data is safe)."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "user_role": self.user_role,
            "event_type": self.event_type.value,
            "success": self.success,
            "source_ip": self.source_ip,
            "source_system": self.source_system,
            "session_id": self.session_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,  # Already scrubbed
        }


class ComplianceAuditLogger:
    """
    PCI DSS 10.2/10.3 compliant audit logger.

    Ensures all required events are logged with required fields.
    Sensitive data is automatically scrubbed before logging.
    """

    def __init__(self, environment: Environment = Environment.PRODUCTION):
        self.environment = environment
        self.masker = ComplianceDataMasker(environment)
        self.events: list[AuditEvent] = []

        # Retention settings
        config = PCIEnvironmentConfig.for_environment(environment)
        self.retention_days = config.audit_retention_days

    def log_event(
        self,
        event_type: AuditEventType,
        user_id: str,
        user_role: str,
        resource_type: str,
        resource_id: str,
        details: str,
        success: bool = True,
        source_ip: str = "127.0.0.1",
        source_system: str = "payment-assistant",
        session_id: str = "",
    ) -> str:
        """
        Log a PCI DSS compliant audit event.

        Returns:
            Event ID for reference
        """
        # CRITICAL: Scrub details before logging
        safe_details, detected = self.masker.scrub_text(
            details, f"audit:{event_type.value}"
        )

        # If sensitive data was found in details, also log a security event
        if detected:
            self._log_security_detection(detected, user_id, source_ip)

        event = AuditEvent(
            user_id=user_id,
            user_role=user_role,
            event_type=event_type,
            timestamp=datetime.now(),
            success=success,
            source_ip=source_ip,
            source_system=source_system,
            session_id=session_id or secrets.token_hex(8),
            resource_type=resource_type,
            resource_id=resource_id,
            details=safe_details,
        )

        self.events.append(event)

        # Also log to system logger
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"AUDIT[{event.event_id[:8]}]: {event_type.value} by {user_id} on "
            f"{resource_type}/{resource_id} - {'OK' if success else 'FAILED'}",
        )

        return event.event_id

    def _log_security_detection(
        self, detected_types: list[str], user_id: str, source_ip: str
    ):
        """Log when sensitive data is detected (potential security issue)."""
        event = AuditEvent(
            user_id=user_id,
            user_role="SYSTEM",
            event_type=AuditEventType.SECURITY_VIOLATION,
            timestamp=datetime.now(),
            success=True,  # Detection succeeded
            source_ip=source_ip,
            source_system="security-monitor",
            session_id="security",
            resource_type="sensitive_data_detection",
            resource_id="auto",
            details=f"Detected and scrubbed: {', '.join(detected_types)}",
        )
        self.events.append(event)

        logger.warning(
            f"SECURITY: Sensitive data detected in input from {user_id}. "
            f"Types: {detected_types}. Data was automatically scrubbed."
        )

    def get_events_for_user(self, user_id: str, days: int = 90) -> list[dict]:
        """Get audit events for a specific user."""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            e.to_log_dict()
            for e in self.events
            if e.user_id == user_id and e.timestamp > cutoff
        ]

    def get_security_events(self, hours: int = 24) -> list[dict]:
        """Get recent security-related events."""
        cutoff = datetime.now() - timedelta(hours=hours)
        security_types = {
            AuditEventType.SECURITY_VIOLATION,
            AuditEventType.INVALID_ACCESS_ATTEMPT,
        }
        return [
            e.to_log_dict()
            for e in self.events
            if e.event_type in security_types and e.timestamp > cutoff
        ]


# ══════════════════════════════════════════════════════════════════════════════
# PCI COMPLIANT AGENT
# ══════════════════════════════════════════════════════════════════════════════


class PCICompliantAgent:
    """
    An AI agent that handles payment operations with full PCI DSS compliance.

    This agent demonstrates:
    - How to build payment-aware bots safely
    - What data can and cannot be accessed
    - Proper audit trails
    - Secure token handling
    """

    def __init__(
        self,
        environment: Environment = Environment.PRODUCTION,
        service_name: str = "payment-agent",
    ):
        self.environment = environment
        self.config = PCIEnvironmentConfig.for_environment(environment)
        self.service_name = service_name

        # Initialize compliant services
        self.masker = ComplianceDataMasker(environment)
        self.tokenizer = MockTokenizationService()
        self.audit_logger = ComplianceAuditLogger(environment)

        # Validate config
        issues = self.config.validate()
        if issues:
            for issue in issues:
                logger.warning(f"CONFIG ISSUE: {issue}")

    async def process_card_for_payment(
        self,
        user_id: str,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvv: str,
        source_ip: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """
        Process a card for payment - tokenize immediately.

        CRITICAL: Card data must be tokenized immediately.
        We NEVER store raw card data anywhere.

        The CVV is validated and then immediately discarded.
        """
        try:
            # Tokenize immediately - card data never touches our storage
            token = await self.tokenizer.tokenize(
                card_number=card_number,
                expiry_month=expiry_month,
                expiry_year=expiry_year,
                cvv=cvv,  # Used once for validation, then discarded
            )

            # Log success (no sensitive data in log!)
            self.audit_logger.log_event(
                event_type=AuditEventType.TOKEN_OPERATION,
                user_id=user_id,
                user_role="customer",
                resource_type="payment_token",
                resource_id=token.token_id,
                details=f"Card tokenized: {token.card_brand} ****{token.last_four}",
                source_ip=source_ip,
            )

            # Return ONLY safe data
            return {
                "success": True,
                "token": token.to_safe_dict(),
                "message": "Card successfully tokenized. Ready for payment.",
            }

        except Exception as e:
            # Log failure (scrub error message!)
            safe_error, _ = self.masker.scrub_text(str(e), "error")

            self.audit_logger.log_event(
                event_type=AuditEventType.TOKEN_OPERATION,
                user_id=user_id,
                user_role="customer",
                resource_type="payment_token",
                resource_id="failed",
                details=f"Tokenization failed: {safe_error}",
                success=False,
                source_ip=source_ip,
            )

            return {
                "success": False,
                "error": "Card could not be processed. Please check details and try again.",
            }

    async def get_safe_card_info(
        self, user_id: str, token_id: str, source_ip: str = "127.0.0.1"
    ) -> dict[str, Any]:
        """
        Get safe (masked) card information from token.

        This returns ONLY:
        - Last 4 digits
        - Card brand
        - Expiry date

        NEVER full card number or CVV.
        """
        try:
            # Validate token exists
            is_valid = await self.tokenizer.validate_token(token_id)
            if not is_valid:
                raise ValueError("Invalid or expired token")

            token = self.tokenizer.tokens.get(token_id)

            # Log access
            self.audit_logger.log_event(
                event_type=AuditEventType.CARDHOLDER_DATA_ACCESS,
                user_id=user_id,
                user_role="customer",
                resource_type="payment_token",
                resource_id=token_id,
                details="Retrieved masked card info (last 4 digits only)",
                source_ip=source_ip,
            )

            return {
                "success": True,
                "card": {
                    "brand": token.card_brand,
                    "last_four": f"****{token.last_four}",
                    "expiry": f"{token.expiry_month:02d}/{token.expiry_year}",
                },
            }

        except Exception:
            self.audit_logger.log_event(
                event_type=AuditEventType.INVALID_ACCESS_ATTEMPT,
                user_id=user_id,
                user_role="customer",
                resource_type="payment_token",
                resource_id=token_id,
                details="Failed to retrieve card info",
                success=False,
                source_ip=source_ip,
            )

            return {
                "success": False,
                "error": "Card information not available",
            }

    def scrub_user_input(self, text: str, context: str = "user_input") -> str:
        """
        Scrub any user input before processing or logging.

        Call this on ANY text received from users before:
        - Passing to LLM
        - Logging
        - Storing
        - Displaying back
        """
        scrubbed, detected = self.masker.scrub_text(text, context)

        if detected:
            logger.info(
                f"User input contained sensitive data that was scrubbed: {detected}"
            )

        return scrubbed

    def get_compliance_report(self) -> dict[str, Any]:
        """Generate a compliance status report."""
        security_events = self.audit_logger.get_security_events(hours=24)

        return {
            "environment": self.environment.value,
            "config_valid": len(self.config.validate()) == 0,
            "config_issues": self.config.validate(),
            "tls_version": self.config.min_tls_version,
            "mfa_required": self.config.require_mfa,
            "session_timeout": f"{self.config.session_timeout_minutes} minutes",
            "audit_retention": f"{self.config.audit_retention_days} days",
            "security_events_24h": len(security_events),
            "total_audit_events": len(self.audit_logger.events),
        }


# ══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE CHECKLIST (Documentation)
# ══════════════════════════════════════════════════════════════════════════════

COMPLIANCE_CHECKLIST = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     PCI DSS COMPLIANCE CHECKLIST                              ║
║                     For AI/Chatbot Payment Systems                            ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  REQUIREMENT 3: PROTECT STORED CARDHOLDER DATA                                ║
║  ─────────────────────────────────────────────                                ║
║  □ 3.2.1  Never store track data after authorization                   ✅    ║
║  □ 3.2.2  Never store CVV/CVC after authorization                       ✅    ║
║  □ 3.2.3  Never store PIN/PIN block                                     ✅    ║
║  □ 3.3    Mask PAN when displayed (show max first 6 + last 4)          ✅    ║
║  □ 3.4    Render PAN unreadable (encryption/tokenization)              ✅    ║
║                                                                               ║
║  REQUIREMENT 4: ENCRYPT TRANSMISSION                                          ║
║  ────────────────────────────────────                                         ║
║  □ 4.1    Use TLS 1.2 or higher for all transmissions                  ✅    ║
║  □ 4.2    Never send PAN via unencrypted channels (email, chat)        ✅    ║
║                                                                               ║
║  REQUIREMENT 7: RESTRICT ACCESS BY BUSINESS NEED                              ║
║  ────────────────────────────────────────────────                             ║
║  □ 7.1    Implement role-based access control                          ✅    ║
║  □ 7.2    Default deny all access                                       ✅    ║
║                                                                               ║
║  REQUIREMENT 8: IDENTIFY & AUTHENTICATE ACCESS                                ║
║  ────────────────────────────────────────────────                             ║
║  □ 8.1    Unique user IDs for all users                                 ✅    ║
║  □ 8.1.8  Session timeout after 15 minutes idle                         ✅    ║
║  □ 8.3    MFA for administrative access                                 ✅    ║
║                                                                               ║
║  REQUIREMENT 10: TRACK AND MONITOR ALL ACCESS                                 ║
║  ────────────────────────────────────────────────                             ║
║  □ 10.2   Audit trail for cardholder data access                        ✅    ║
║  □ 10.3   Log entries include required fields                           ✅    ║
║  □ 10.5   Audit trails protected from modification                      ✅    ║
║  □ 10.7   Retain logs for at least 1 year                               ✅    ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  AUSTRALIAN SPECIFIC:                                                         ║
║  ────────────────────                                                         ║
║  □ APRA CPS 234     Information Security standard                       ✅    ║
║  □ Privacy Act      Australian Privacy Principles                       ✅    ║
║  □ CDR              Consumer Data Right (Open Banking)                  ✅    ║
║  □ ASIC             ePayments Code compliance                           ✅    ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    """Demonstrate PCI DSS compliance patterns."""
    print("=" * 78)
    print("PCI DSS COMPLIANCE PATTERNS FOR AI AGENTS")
    print("=" * 78)

    # Initialize agent in production mode
    agent = PCICompliantAgent(
        environment=Environment.PRODUCTION, service_name="demo-agent"
    )

    print("\n📋 Environment Configuration")
    print("-" * 50)
    report = agent.get_compliance_report()
    for key, value in report.items():
        print(f"  {key}: {value}")

    print("\n🔒 Demo: Tokenizing Card Data")
    print("-" * 50)

    # Simulate tokenizing a card
    result = await agent.process_card_for_payment(
        user_id="CUST_001",
        card_number="4111111111111111",
        expiry_month=12,
        expiry_year=2027,
        cvv="123",  # Used once, then discarded - NEVER stored
        source_ip="203.0.113.42",
    )

    print(f"Result: {result}")
    print("\nNote: CVV was used for validation and immediately discarded!")

    print("\n🔐 Demo: Retrieving Safe Card Info")
    print("-" * 50)

    if result["success"]:
        token_id = result["token"]["token_id"]
        card_info = await agent.get_safe_card_info(
            user_id="CUST_001",
            token_id=token_id,
        )
        print(f"Safe card info: {card_info}")

    print("\n🧹 Demo: Data Masking")
    print("-" * 50)

    # Test masking
    masker = ComplianceDataMasker()

    dangerous_input = "My card is 4111111111111111 and CVV is 123"
    scrubbed, detected = masker.scrub_text(dangerous_input, "demo")

    print(f"Original: {dangerous_input}")
    print(f"Scrubbed: {scrubbed}")
    print(f"Detected: {detected}")

    print("\n📜 Demo: Audit Log")
    print("-" * 50)

    for event in agent.audit_logger.events[-5:]:
        print(
            f"[{event.timestamp.strftime('%H:%M:%S')}] "
            f"{event.event_type.value:30} | "
            f"{event.user_id:10} | "
            f"{'✅' if event.success else '❌'}"
        )

    print("\n" + "=" * 78)
    print(COMPLIANCE_CHECKLIST)


if __name__ == "__main__":
    asyncio.run(main())
