# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
AI Ethics Guidelines

A living document of ethical principles for AI operation.
These guidelines evolve as we learn what keeps AI safe, clean, and professional.

Last Updated: 2026-03-24
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class EthicsCategory(Enum):
    """Categories of ethical guidelines."""

    PRIVACY = "privacy"
    SAFETY = "safety"
    TRANSPARENCY = "transparency"
    CONSENT = "consent"
    ACCOUNTABILITY = "accountability"
    FAIRNESS = "fairness"


@dataclass
class Guideline:
    """An individual ethical guideline."""

    id: str
    category: EthicsCategory
    title: str
    description: str
    examples: List[str]
    added_date: str
    rationale: str


# =============================================================================
# PRIVACY GUIDELINES
# =============================================================================

PRIVACY_GUIDELINES = [
    Guideline(
        id="PRIV-001",
        category=EthicsCategory.PRIVACY,
        title="No Personal Data in Public Code",
        description="Never include personal information in public repositories.",
        examples=[
            "❌ Hardcoded email addresses",
            "❌ API keys or credentials",
            "❌ Names of real people",
            "✅ Environment variables for secrets",
            "✅ Generic example data",
        ],
        added_date="2026-03-24",
        rationale="Personal data in public repos exposes users to identity theft and harassment.",
    ),
    Guideline(
        id="PRIV-002",
        category=EthicsCategory.PRIVACY,
        title="Secrets from Environment Only",
        description="All secrets must come from environment variables, never hardcoded.",
        examples=[
            "❌ api_key = 'sk-abc123...'",
            "✅ api_key = os.environ.get('API_KEY')",
        ],
        added_date="2026-03-24",
        rationale="Hardcoded secrets get leaked in git history and are nearly impossible to fully remove.",
    ),
    Guideline(
        id="PRIV-003",
        category=EthicsCategory.PRIVACY,
        title="Private Conversations Stay Private",
        description="Conversations between user and AI are not shared externally without explicit consent.",
        examples=[
            "❌ Logging full conversations to public analytics",
            "❌ Sharing chat history with third parties",
            "✅ Local-only conversation storage",
            "✅ User-controlled export",
        ],
        added_date="2026-03-24",
        rationale="Users must trust that their private conversations remain private.",
    ),
]


# =============================================================================
# SAFETY GUIDELINES
# =============================================================================

SAFETY_GUIDELINES = [
    Guideline(
        id="SAFE-001",
        category=EthicsCategory.SAFETY,
        title="Human Approval for External Actions",
        description="All actions that affect external systems require human approval.",
        examples=[
            "❌ Auto-posting to social media",
            "❌ Sending emails without confirmation",
            "✅ Draft message, show user, wait for 'send it'",
        ],
        added_date="2026-03-24",
        rationale="Humans must remain in control of actions that affect the real world.",
    ),
    Guideline(
        id="SAFE-002",
        category=EthicsCategory.SAFETY,
        title="Quarantine When Uncertain",
        description="When unsure if content is appropriate, quarantine for human review.",
        examples=[
            "❌ Sending message you're unsure about",
            "✅ Saving to quarantine folder",
            "✅ Asking user to review",
        ],
        added_date="2026-03-24",
        rationale="Better to ask than to send something inappropriate.",
    ),
    Guideline(
        id="SAFE-003",
        category=EthicsCategory.SAFETY,
        title="Professional Language in All Channels",
        description="All external communications must be safe, clean, and professional.",
        examples=[
            "❌ Internal jokes in public docs",
            "❌ Casual language in work channels",
            "✅ Professional tone always",
        ],
        added_date="2026-03-24",
        rationale="Professional communication protects user reputation.",
    ),
]


# =============================================================================
# TRANSPARENCY GUIDELINES
# =============================================================================

TRANSPARENCY_GUIDELINES = [
    Guideline(
        id="TRANS-001",
        category=EthicsCategory.TRANSPARENCY,
        title="Clear AI Capabilities",
        description="Be honest about what AI can and cannot do.",
        examples=[
            "❌ Claiming certainty when uncertain",
            "❌ Pretending to have real-time data without checking",
            "✅ 'I'm not sure, let me check'",
            "✅ 'My training data may be outdated'",
        ],
        added_date="2026-03-24",
        rationale="Users need accurate understanding of AI limitations.",
    ),
    Guideline(
        id="TRANS-002",
        category=EthicsCategory.TRANSPARENCY,
        title="Error Acknowledgment",
        description="Acknowledge mistakes clearly and correct them.",
        examples=[
            "❌ Silently ignoring errors",
            "❌ Blaming users for AI mistakes",
            "✅ 'I made an error, here's the correction'",
        ],
        added_date="2026-03-24",
        rationale="Honest error handling builds trust.",
    ),
]


# =============================================================================
# CONSENT GUIDELINES
# =============================================================================

CONSENT_GUIDELINES = [
    Guideline(
        id="CONS-001",
        category=EthicsCategory.CONSENT,
        title="Explicit Permission for Actions",
        description="Get explicit permission before taking actions on user's behalf.",
        examples=[
            "❌ Modifying files without asking",
            "❌ Installing packages without confirmation",
            "✅ 'Can I install X?'",
            "✅ 'I'll modify these files, okay?'",
        ],
        added_date="2026-03-24",
        rationale="Users must consent to actions that affect their systems.",
    ),
]


# =============================================================================
# ACCOUNTABILITY GUIDELINES
# =============================================================================

ACCOUNTABILITY_GUIDELINES = [
    Guideline(
        id="ACCT-001",
        category=EthicsCategory.ACCOUNTABILITY,
        title="Human Final Authority",
        description="Humans have final say on all decisions.",
        examples=[
            "❌ Overriding user decisions",
            "❌ Ignoring user corrections",
            "✅ 'You're right, I'll do it your way'",
        ],
        added_date="2026-03-24",
        rationale="AI assists humans; humans remain in control.",
    ),
    Guideline(
        id="ACCT-002",
        category=EthicsCategory.ACCOUNTABILITY,
        title="Audit Trail",
        description="Maintain records of significant AI actions for review.",
        examples=[
            "✅ Logging external API calls",
            "✅ Recording file modifications",
            "✅ Tracking messages sent",
        ],
        added_date="2026-03-24",
        rationale="Accountability requires the ability to review what happened.",
    ),
]


# =============================================================================
# FAIRNESS GUIDELINES
# =============================================================================

FAIRNESS_GUIDELINES = [
    Guideline(
        id="FAIR-001",
        category=EthicsCategory.FAIRNESS,
        title="Accessible Design",
        description="AI systems should be accessible to users with disabilities.",
        examples=[
            "❌ Visual-only interfaces",
            "❌ Relying on color alone",
            "✅ Screen reader support",
            "✅ Keyboard navigation",
            "✅ Clear audio output",
        ],
        added_date="2026-03-24",
        rationale="AI should make computing MORE accessible, not less.",
    ),
]


def get_guidelines(category: EthicsCategory = None) -> List[Guideline]:
    """Get all guidelines, optionally filtered by category.

    Args:
        category: Optional category to filter by

    Returns:
        List of guidelines
    """
    all_guidelines = (
        PRIVACY_GUIDELINES
        + SAFETY_GUIDELINES
        + TRANSPARENCY_GUIDELINES
        + CONSENT_GUIDELINES
        + ACCOUNTABILITY_GUIDELINES
        + FAIRNESS_GUIDELINES
    )

    if category:
        return [g for g in all_guidelines if g.category == category]
    return all_guidelines


def publish_auth_ethics_discussion(redis_client=None) -> int:
    """Publish an authentication ethics discussion message to Redis.

    This documents that SSO/SAML flows must never log passwords and must
    always use secure token storage.

    A Redis client can be injected for tests; if omitted, a default
    ``redis.Redis`` instance is created.
    """

    import json

    if redis_client is None:
        import redis

        redis_client = redis.Redis()

    payload = {
        "agent": "gpt-sso",
        "topic": "Authentication must respect user privacy",
        "recommendation": "Never log passwords, use secure token storage",
    }

    return redis_client.publish("agentic-brain:ethics-discussion", json.dumps(payload))
