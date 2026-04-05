#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 13: Email Automation with AI Classification

Demonstrates:
- IMAP email processing
- AI-powered spam classification
- Intelligent email routing
- Learning from feedback

This is a simplified version of real-world email automation patterns.
Perfect for business automation use cases like:
- Spam filtering
- Customer inquiry routing
- Order notification processing
- Support ticket triage

Requirements:
- Ollama running with llama3.1:8b (or any model)
- Access to an IMAP email account

Author: agentic-brain
License: MIT
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Agentic Brain imports
from agentic_brain import Agent
from agentic_brain.router import LLMRouter

# ─────────────────────────────────────────────────────────────────────────────
# EMAIL MODELS
# ─────────────────────────────────────────────────────────────────────────────


class EmailCategory(Enum):
    """Email classification categories."""

    SPAM = "spam"
    NEWSLETTER = "newsletter"
    ORDER = "order"
    SUPPORT = "support"
    INVOICE = "invoice"
    PERSONAL = "personal"
    IMPORTANT = "important"


@dataclass
class Email:
    """Represents an email message."""

    uid: str
    sender: str
    subject: str
    body: str
    date: str
    folder: str = "INBOX"


@dataclass
class ClassificationResult:
    """Result of email classification."""

    category: EmailCategory
    confidence: float
    reasoning: str
    suggested_action: str


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL CLASSIFIER AGENT
# ─────────────────────────────────────────────────────────────────────────────


class EmailClassifierAgent:
    """AI-powered email classification agent.

    Uses an LLM to intelligently classify emails into categories
    and suggest actions.
    """

    CLASSIFICATION_PROMPT = """You are an expert email classifier for a business.
Analyze the email and classify it into ONE of these categories:
- spam: Unwanted promotional/scam emails
- newsletter: Subscription-based updates
- order: Purchase confirmations, shipping updates
- support: Customer questions or complaints
- invoice: Bills, invoices, payment requests
- personal: Personal correspondence
- important: Urgent business matters

Respond in this exact format:
CATEGORY: <category>
CONFIDENCE: <0.0-1.0>
REASONING: <brief explanation>
ACTION: <suggested action>

Email to classify:
From: {sender}
Subject: {subject}
Body (first 500 chars):
{body}
"""

    def __init__(self, model: str = "llama3.1:8b"):
        """Initialize the classifier with an LLM model."""
        self.model = model
        self.router: Optional[LLMRouter] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.router = LLMRouter(
            providers=["ollama"],
            default_model=self.model,
        )
        await self.router.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.router:
            await self.router.__aexit__(exc_type, exc_val, exc_tb)

    async def classify(self, email: Email) -> ClassificationResult:
        """Classify an email using AI.

        Args:
            email: The email to classify

        Returns:
            ClassificationResult with category, confidence, and action
        """
        # Build the prompt
        prompt = self.CLASSIFICATION_PROMPT.format(
            sender=email.sender,
            subject=email.subject,
            body=email.body[:500],
        )

        # Get LLM response
        response = await self.router.complete(prompt)

        # Parse the response
        return self._parse_response(response)

    def _parse_response(self, response: str) -> ClassificationResult:
        """Parse LLM response into ClassificationResult."""
        lines = response.strip().split("\n")

        category = EmailCategory.PERSONAL  # default
        confidence = 0.5
        reasoning = ""
        action = "Review manually"

        for line in lines:
            line = line.strip()
            if line.startswith("CATEGORY:"):
                cat_str = line.split(":", 1)[1].strip().lower()
                try:
                    category = EmailCategory(cat_str)
                except ValueError:
                    pass
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("ACTION:"):
                action = line.split(":", 1)[1].strip()

        return ClassificationResult(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            suggested_action=action,
        )


# ─────────────────────────────────────────────────────────────────────────────
# SPAM RULES (Rule-based pre-filtering)
# ─────────────────────────────────────────────────────────────────────────────


SPAM_PATTERNS = [
    # Subject patterns
    r"(?i)free.*money",
    r"(?i)you.*won.*lottery",
    r"(?i)nigerian.*prince",
    r"(?i)urgent.*wire.*transfer",
    r"(?i)claim.*prize.*now",
    # Sender patterns
    r"@.*\.ru$",
    r"no-?reply@.*\.xyz",
]


def is_obvious_spam(email: Email) -> bool:
    """Fast rule-based spam check before AI classification.

    Use simple regex patterns to catch obvious spam
    without invoking the LLM.
    """
    import re

    text = f"{email.sender} {email.subject}"

    return any(re.search(pattern, text) for pattern in SPAM_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL ROUTER (Action handler)
# ─────────────────────────────────────────────────────────────────────────────


class EmailRouter:
    """Routes emails to appropriate folders based on classification."""

    # Map categories to folder names
    FOLDER_MAP = {
        EmailCategory.SPAM: "Junk",
        EmailCategory.NEWSLETTER: "Newsletters",
        EmailCategory.ORDER: "Orders",
        EmailCategory.SUPPORT: "Support",
        EmailCategory.INVOICE: "Invoices",
        EmailCategory.PERSONAL: "INBOX",
        EmailCategory.IMPORTANT: "Important",
    }

    def get_destination_folder(self, result: ClassificationResult, email: Email) -> str:
        """Determine the destination folder for an email.

        Args:
            result: Classification result
            email: Original email

        Returns:
            Folder name to move email to
        """
        # High confidence: use classification
        if result.confidence >= 0.8:
            return self.FOLDER_MAP.get(result.category, "INBOX")

        # Low confidence: leave in inbox for manual review
        return "INBOX"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DEMO
# ─────────────────────────────────────────────────────────────────────────────


async def demo():
    """Demonstrate email automation with AI classification."""

    print("=" * 60)
    print("Email Automation Example")
    print("=" * 60)

    # Sample emails to classify
    sample_emails = [
        Email(
            uid="001",
            sender="support@woocommerce.com",
            subject="Order #12345 Confirmed",
            body="Thank you for your order! Your payment has been processed. "
            "Order details: Widget Pro x2, Shipping to: 123 Main St...",
            date="2026-03-20",
        ),
        Email(
            uid="002",
            sender="newsletter@techcrunch.com",
            subject="TechCrunch Daily: AI News Roundup",
            body="Today's top stories in artificial intelligence: "
            "OpenAI releases new model, Google announces...",
            date="2026-03-20",
        ),
        Email(
            uid="003",
            sender="prince.nigeria@mail.ru",
            subject="URGENT: You Won $10 Million Lottery!!!",
            body="Dear friend, I am prince from Nigeria. You have won "
            "$10 million in lottery. Send bank details to claim...",
            date="2026-03-20",
        ),
        Email(
            uid="004",
            sender="accounts@supplier.com.au",
            subject="TAX INVOICE #INV-2026-0123",
            body="Please find attached invoice for recent order. "
            "Amount due: $1,234.56. Payment terms: 30 days...",
            date="2026-03-20",
        ),
        Email(
            uid="005",
            sender="john.smith@company.com",
            subject="Meeting tomorrow at 10am",
            body="Hi, Can we catch up tomorrow morning to discuss "
            "the project timeline? I have some concerns about...",
            date="2026-03-20",
        ),
    ]

    router = EmailRouter()

    print("\n🔍 Processing emails with AI classification...\n")

    async with EmailClassifierAgent() as classifier:
        for email in sample_emails:
            print(f"📧 From: {email.sender}")
            print(f"   Subject: {email.subject}")

            # Step 1: Quick rule-based check
            if is_obvious_spam(email):
                print("   ⚡ Quick match: SPAM (rule-based)")
                print("   → Move to: Junk")
                print()
                continue

            # Step 2: AI classification
            result = await classifier.classify(email)

            print(f"   🤖 AI Classification: {result.category.value}")
            print(f"   📊 Confidence: {result.confidence:.0%}")
            print(f"   💭 Reasoning: {result.reasoning}")

            # Step 3: Route to folder
            folder = router.get_destination_folder(result, email)
            print(f"   → Move to: {folder}")
            print()

    print("=" * 60)
    print("✅ Email processing complete!")
    print("\nIn production, this would:")
    print("  1. Connect to IMAP server")
    print("  2. Process real emails")
    print("  3. Move emails to folders")
    print("  4. Track UIDs to avoid reprocessing")
    print("  5. Run on schedule (cron/launchd)")


if __name__ == "__main__":
    asyncio.run(demo())
