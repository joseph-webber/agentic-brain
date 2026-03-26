"""
AI Ethics Module for Agentic Brain

This module provides guidelines, guardrails, and tools for ethical AI operation.
It is a living document that evolves as we learn what keeps AI safe, clean, 
and professional.

Philosophy:
    Small rules make big differences to safety. By following AI etiquette,
    we build trust between humans and AI systems.

Usage:
    from agentic_brain.ethics import EthicsGuard, check_content, get_guidelines
    
    # Check content before sending
    result = check_content("message to send", channel="email")
    if result.safe:
        send_message(result.content)
    else:
        quarantine(result.content, result.reason)

Categories:
    - Privacy: Protecting personal information
    - Safety: Preventing harm
    - Transparency: Being honest about AI involvement
    - Consent: Respecting user choices
    - Accountability: Human oversight
    - Fairness: Avoiding bias

This module will grow over the lifetime of agentic-brain development.
"""

from .guard import EthicsGuard, ContentCheckResult, check_content
from .guidelines import (
    get_guidelines,
    PRIVACY_GUIDELINES,
    SAFETY_GUIDELINES,
    TRANSPARENCY_GUIDELINES,
    CONSENT_GUIDELINES,
    ACCOUNTABILITY_GUIDELINES,
    FAIRNESS_GUIDELINES,
)
from .quarantine import Quarantine, quarantine_content

__all__ = [
    "EthicsGuard",
    "ContentCheckResult",
    "check_content",
    "get_guidelines",
    "Quarantine",
    "quarantine_content",
    "PRIVACY_GUIDELINES",
    "SAFETY_GUIDELINES",
    "TRANSPARENCY_GUIDELINES",
    "CONSENT_GUIDELINES",
    "ACCOUNTABILITY_GUIDELINES",
    "FAIRNESS_GUIDELINES",
]
