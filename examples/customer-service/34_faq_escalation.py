#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
FAQ Bot with Smart Escalation
=============================

Intelligent FAQ system with:
- Hierarchical FAQ categories
- Fuzzy matching for questions
- Confidence scoring
- Auto-escalate when confidence low
- Learning from escalated cases
- Analytics and reporting

Demo: Office supplies FAQ (paper, ink, furniture)
"""

import asyncio
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Callable, Optional


class MatchConfidence(Enum):
    """Confidence levels for FAQ matching."""

    HIGH = "high"  # > 0.85
    MEDIUM = "medium"  # 0.65 - 0.85
    LOW = "low"  # 0.45 - 0.65
    NONE = "none"  # < 0.45


class EscalationReason(Enum):
    """Reasons for escalating to human."""

    LOW_CONFIDENCE = "low_confidence"
    REPEATED_QUESTION = "repeated_question"
    CUSTOMER_REQUEST = "customer_request"
    SENSITIVE_TOPIC = "sensitive_topic"
    NEGATIVE_FEEDBACK = "negative_feedback"
    NO_MATCH = "no_match"


class FeedbackType(Enum):
    """Types of feedback on answers."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    PARTIAL = "partial"


@dataclass
class FAQEntry:
    """A single FAQ entry."""

    id: str
    category: str
    subcategory: Optional[str]
    question: str
    answer: str
    keywords: list[str]
    related_ids: list[str] = field(default_factory=list)
    views: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def helpfulness_score(self) -> float:
        """Calculate helpfulness ratio."""
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 0.5
        return self.helpful_count / total

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "subcategory": self.subcategory,
            "question": self.question,
            "answer": self.answer,
            "keywords": self.keywords,
            "views": self.views,
            "helpfulness": self.helpfulness_score,
        }


@dataclass
class MatchResult:
    """Result of matching a question to FAQ."""

    faq_entry: Optional[FAQEntry]
    confidence: float
    confidence_level: MatchConfidence
    match_type: str  # exact, fuzzy, keyword, semantic
    alternative_matches: list = field(default_factory=list)

    @property
    def should_escalate(self) -> bool:
        return self.confidence_level in [MatchConfidence.LOW, MatchConfidence.NONE]


@dataclass
class Escalation:
    """An escalated question."""

    id: str
    original_question: str
    matched_faq_id: Optional[str]
    confidence: float
    reason: EscalationReason
    customer_id: str
    created_at: datetime
    resolved: bool = False
    resolution_notes: Optional[str] = None
    new_faq_created: bool = False
    resolved_at: Optional[datetime] = None
    assigned_to: Optional[str] = None


@dataclass
class Session:
    """Customer FAQ session."""

    id: str
    customer_id: str
    questions_asked: list = field(default_factory=list)
    faqs_viewed: list = field(default_factory=list)
    escalations: list = field(default_factory=list)
    feedback_given: dict = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None


class FuzzyMatcher:
    """Fuzzy string matching for FAQ questions."""

    def __init__(self):
        self.stop_words = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "what",
            "which",
            "who",
            "when",
            "where",
            "why",
            "how",
            "this",
            "that",
            "these",
            "those",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "and",
            "but",
            "if",
            "or",
            "because",
            "until",
            "while",
            "my",
            "your",
        }

    def normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def tokenize(self, text: str) -> list[str]:
        """Tokenize and remove stop words."""
        normalized = self.normalize(text)
        words = normalized.split()
        return [w for w in words if w not in self.stop_words and len(w) > 1]

    def sequence_similarity(self, text1: str, text2: str) -> float:
        """Calculate sequence similarity using SequenceMatcher."""
        return SequenceMatcher(
            None, self.normalize(text1), self.normalize(text2)
        ).ratio()

    def token_overlap(self, text1: str, text2: str) -> float:
        """Calculate token overlap ratio."""
        tokens1 = set(self.tokenize(text1))
        tokens2 = set(self.tokenize(text2))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        return len(intersection) / len(union)

    def keyword_match(self, text: str, keywords: list[str]) -> float:
        """Calculate keyword match score."""
        text_lower = text.lower()
        matched = sum(1 for kw in keywords if kw.lower() in text_lower)
        return matched / max(len(keywords), 1)

    def combined_score(
        self, query: str, question: str, keywords: list[str]
    ) -> tuple[float, str]:
        """Calculate combined similarity score.

        Returns:
            Tuple of (score, match_type)
        """
        # Exact match
        if self.normalize(query) == self.normalize(question):
            return 1.0, "exact"

        # Calculate different similarity metrics
        seq_sim = self.sequence_similarity(query, question)
        token_sim = self.token_overlap(query, question)
        keyword_sim = self.keyword_match(query, keywords)

        # Weight the scores
        combined = (seq_sim * 0.4) + (token_sim * 0.35) + (keyword_sim * 0.25)

        # Determine match type
        if keyword_sim > 0.6:
            match_type = "keyword"
        elif token_sim > seq_sim:
            match_type = "token"
        else:
            match_type = "fuzzy"

        return combined, match_type


class FAQKnowledgeBase:
    """FAQ knowledge base with categories."""

    def __init__(self):
        self.entries: dict[str, FAQEntry] = {}
        self.categories: dict[str, list[str]] = defaultdict(list)
        self.matcher = FuzzyMatcher()
        self.entry_counter = 0

    def add_entry(
        self,
        category: str,
        question: str,
        answer: str,
        keywords: list[str],
        subcategory: Optional[str] = None,
        related_ids: Optional[list[str]] = None,
    ) -> FAQEntry:
        """Add a new FAQ entry."""
        self.entry_counter += 1
        entry_id = f"faq_{self.entry_counter:04d}"

        entry = FAQEntry(
            id=entry_id,
            category=category,
            subcategory=subcategory,
            question=question,
            answer=answer,
            keywords=keywords,
            related_ids=related_ids or [],
        )

        self.entries[entry_id] = entry
        self.categories[category].append(entry_id)

        return entry

    def find_match(self, query: str, category: Optional[str] = None) -> MatchResult:
        """Find best matching FAQ for a query."""
        if not self.entries:
            return MatchResult(
                faq_entry=None,
                confidence=0.0,
                confidence_level=MatchConfidence.NONE,
                match_type="none",
            )

        # Filter entries by category if specified
        if category:
            entry_ids = self.categories.get(category, [])
            entries = [self.entries[eid] for eid in entry_ids]
        else:
            entries = list(self.entries.values())

        if not entries:
            return MatchResult(
                faq_entry=None,
                confidence=0.0,
                confidence_level=MatchConfidence.NONE,
                match_type="none",
            )

        # Score all entries
        scored_entries = []
        for entry in entries:
            score, match_type = self.matcher.combined_score(
                query, entry.question, entry.keywords
            )
            scored_entries.append((entry, score, match_type))

        # Sort by score
        scored_entries.sort(key=lambda x: x[1], reverse=True)

        best_entry, best_score, match_type = scored_entries[0]

        # Determine confidence level
        if best_score >= 0.85:
            confidence_level = MatchConfidence.HIGH
        elif best_score >= 0.65:
            confidence_level = MatchConfidence.MEDIUM
        elif best_score >= 0.45:
            confidence_level = MatchConfidence.LOW
        else:
            confidence_level = MatchConfidence.NONE

        # Get alternative matches
        alternatives = [
            {"faq_id": e.id, "question": e.question, "score": s}
            for e, s, _ in scored_entries[1:4]
            if s >= 0.4
        ]

        return MatchResult(
            faq_entry=best_entry if confidence_level != MatchConfidence.NONE else None,
            confidence=best_score,
            confidence_level=confidence_level,
            match_type=match_type,
            alternative_matches=alternatives,
        )

    def get_by_category(self, category: str) -> list[FAQEntry]:
        """Get all entries in a category."""
        entry_ids = self.categories.get(category, [])
        return [self.entries[eid] for eid in entry_ids]

    def get_categories(self) -> list[dict]:
        """Get list of categories with counts."""
        return [
            {"name": cat, "count": len(ids)} for cat, ids in self.categories.items()
        ]

    def record_view(self, faq_id: str):
        """Record a view on an FAQ."""
        if faq_id in self.entries:
            self.entries[faq_id].views += 1

    def record_feedback(self, faq_id: str, feedback: FeedbackType):
        """Record feedback on an FAQ answer."""
        if faq_id in self.entries:
            entry = self.entries[faq_id]
            if feedback == FeedbackType.HELPFUL:
                entry.helpful_count += 1
            elif feedback == FeedbackType.NOT_HELPFUL:
                entry.not_helpful_count += 1
            entry.updated_at = datetime.now()


class FAQBot:
    """FAQ bot with smart escalation."""

    def __init__(self, company_name: str = "OfficeSupply Pro"):
        self.company_name = company_name
        self.kb = FAQKnowledgeBase()
        self.sessions: dict[str, Session] = {}
        self.escalations: dict[str, Escalation] = {}
        self.escalation_counter = 0

        # Configuration
        self.escalation_threshold = 0.65
        self.max_repeated_questions = 2
        self.sensitive_keywords = [
            "complaint",
            "legal",
            "lawyer",
            "sue",
            "refund",
            "fraud",
            "manager",
            "supervisor",
            "corporate",
        ]

        # Metrics
        self.metrics = {
            "total_questions": 0,
            "answered_directly": 0,
            "escalated": 0,
            "helpful_responses": 0,
            "unhelpful_responses": 0,
            "avg_confidence": 0.0,
            "questions_by_category": defaultdict(int),
            "learning_improvements": 0,
        }

        # Callbacks
        self.on_escalation: Optional[Callable] = None
        self.on_answer: Optional[Callable] = None

        self._load_demo_faqs()

    def _load_demo_faqs(self):
        """Load demo FAQ content for office supplies."""
        faqs = [
            # Ordering
            {
                "category": "Ordering",
                "question": "How do I place an order?",
                "answer": "You can place an order through our website by adding items to your cart and proceeding to checkout. For bulk orders over $500, you can also call our sales team at 1-800-555-0123 or email orders@officesupplypro.com.",
                "keywords": ["order", "place", "buy", "purchase", "checkout"],
            },
            {
                "category": "Ordering",
                "question": "What is the minimum order amount?",
                "answer": "There is no minimum order for standard delivery. However, free shipping is available on orders over $50. Business accounts enjoy free shipping on all orders.",
                "keywords": ["minimum", "order", "amount", "limit", "smallest"],
            },
            {
                "category": "Ordering",
                "question": "Can I modify or cancel my order?",
                "answer": "You can modify or cancel your order within 1 hour of placing it by calling 1-800-555-0123. After that, please wait for delivery and initiate a return.",
                "keywords": ["modify", "cancel", "change", "order", "edit"],
            },
            {
                "category": "Ordering",
                "question": "Do you offer bulk discounts?",
                "answer": "Yes! We offer tiered bulk discounts: 10% off orders over $500, 15% off over $1000, and 20% off over $2500. Contact our business sales team for custom pricing on larger orders.",
                "keywords": ["bulk", "discount", "wholesale", "quantity", "volume"],
            },
            # Shipping
            {
                "category": "Shipping",
                "question": "What are your shipping options?",
                "answer": "We offer: Standard shipping (5-7 business days, free over $50), Express shipping (2-3 business days, $12.99), and Next-day delivery ($24.99, order by 2 PM).",
                "keywords": ["shipping", "delivery", "options", "how long", "fast"],
            },
            {
                "category": "Shipping",
                "question": "How do I track my order?",
                "answer": "Once shipped, you'll receive a tracking email with a link. You can also track orders in your account under 'Order History' or enter your order number on our 'Track Order' page.",
                "keywords": ["track", "tracking", "where", "order", "status"],
            },
            {
                "category": "Shipping",
                "question": "Do you ship internationally?",
                "answer": "We currently ship to USA, Canada, and Mexico. International shipping takes 10-14 business days. Contact us for shipping to other countries.",
                "keywords": [
                    "international",
                    "overseas",
                    "foreign",
                    "countries",
                    "abroad",
                ],
            },
            # Returns
            {
                "category": "Returns",
                "question": "What is your return policy?",
                "answer": "We accept returns within 30 days of delivery for unused items in original packaging. Electronics and opened software are non-returnable unless defective. Return shipping is free for defective items.",
                "keywords": ["return", "policy", "refund", "exchange", "send back"],
            },
            {
                "category": "Returns",
                "question": "How do I start a return?",
                "answer": "Log into your account, go to 'Order History', select the item, and click 'Return Item'. Print the prepaid label and drop off at any carrier location. Refunds process within 5-7 business days after receipt.",
                "keywords": ["start", "return", "initiate", "how", "process"],
            },
            {
                "category": "Returns",
                "question": "Can I exchange an item instead of returning it?",
                "answer": "Yes! Select 'Exchange' instead of 'Return' when processing. Choose the new item and we'll ship it once we receive your return. No additional shipping charges for exchanges.",
                "keywords": ["exchange", "swap", "replace", "different", "instead"],
            },
            # Products - Paper
            {
                "category": "Products",
                "subcategory": "Paper",
                "question": "What types of paper do you sell?",
                "answer": "We carry: Copy paper (20-28 lb), Cardstock (65-110 lb), Photo paper (glossy/matte), Colored paper, Recycled options, and Specialty papers. All available in letter, legal, and A4 sizes.",
                "keywords": ["paper", "types", "copy", "cardstock", "options"],
            },
            {
                "category": "Products",
                "subcategory": "Paper",
                "question": "What's the difference between 20lb and 24lb paper?",
                "answer": "20lb paper is standard copy paper, good for everyday printing. 24lb paper is thicker and more opaque, better for double-sided printing and presentations. 28lb is premium weight for important documents.",
                "keywords": ["paper", "weight", "20lb", "24lb", "difference", "thick"],
            },
            # Products - Ink & Toner
            {
                "category": "Products",
                "subcategory": "Ink & Toner",
                "question": "Do you sell compatible ink cartridges?",
                "answer": "Yes, we offer both OEM (original) and compatible cartridges. Compatible cartridges are 40-60% cheaper and include our 100% satisfaction guarantee. Quality is comparable for most uses.",
                "keywords": [
                    "compatible",
                    "ink",
                    "cartridge",
                    "generic",
                    "third-party",
                ],
            },
            {
                "category": "Products",
                "subcategory": "Ink & Toner",
                "question": "How do I find the right ink for my printer?",
                "answer": "Use our Ink Finder tool: enter your printer brand and model, and we'll show compatible options. You can also check your printer's cartridge door for the cartridge number.",
                "keywords": ["find", "ink", "printer", "compatible", "right", "match"],
            },
            {
                "category": "Products",
                "subcategory": "Ink & Toner",
                "question": "Do you offer ink subscription?",
                "answer": "Yes! Our Ink AutoShip program delivers ink automatically when you're running low (works with select printers). Save 10% on every order and never run out.",
                "keywords": [
                    "subscription",
                    "autoship",
                    "automatic",
                    "recurring",
                    "ink",
                ],
            },
            # Products - Furniture
            {
                "category": "Products",
                "subcategory": "Furniture",
                "question": "Do you offer office chair assembly?",
                "answer": "Yes, we offer professional assembly for $49 per item in most metro areas. Select 'Assembly Service' at checkout. Assembly takes 1-2 days after delivery.",
                "keywords": ["assembly", "chair", "furniture", "setup", "build"],
            },
            {
                "category": "Products",
                "subcategory": "Furniture",
                "question": "What is the warranty on office furniture?",
                "answer": "Standard furniture has a 5-year warranty against manufacturing defects. Premium ergonomic chairs have a 10-year warranty. Warranty covers parts and labor but not normal wear.",
                "keywords": ["warranty", "furniture", "guarantee", "coverage", "years"],
            },
            {
                "category": "Products",
                "subcategory": "Furniture",
                "question": "Can I try chairs before buying?",
                "answer": "We have showrooms in major cities where you can try our furniture. For online orders, we offer a 30-day comfort guarantee - return for free if not satisfied.",
                "keywords": ["try", "chair", "test", "showroom", "comfortable"],
            },
            # Account
            {
                "category": "Account",
                "question": "How do I create a business account?",
                "answer": "Click 'Business Account' on our homepage, provide your business info and tax ID. Approval takes 1-2 business days. Benefits include net-30 terms, dedicated rep, and volume pricing.",
                "keywords": ["business", "account", "corporate", "company", "create"],
            },
            {
                "category": "Account",
                "question": "How do I reset my password?",
                "answer": "Click 'Forgot Password' on the login page, enter your email, and we'll send a reset link. For security, links expire in 24 hours. If you don't receive it, check your spam folder.",
                "keywords": ["password", "reset", "forgot", "login", "access"],
            },
            {
                "category": "Account",
                "question": "Can I have multiple users on one account?",
                "answer": "Business accounts support unlimited users with role-based permissions: Admin, Purchaser, and Viewer. Admins can add users from the Account Settings page.",
                "keywords": ["multiple", "users", "team", "permissions", "roles"],
            },
            # Payment
            {
                "category": "Payment",
                "question": "What payment methods do you accept?",
                "answer": "We accept Visa, Mastercard, Amex, Discover, PayPal, and Apple Pay. Business accounts can pay by invoice with net-30 terms. We also accept purchase orders.",
                "keywords": ["payment", "methods", "credit", "card", "pay", "accept"],
            },
            {
                "category": "Payment",
                "question": "Do you offer payment plans?",
                "answer": "Yes, orders over $200 qualify for our Pay in 4 option (4 interest-free payments). Business accounts can request custom payment terms through their account manager.",
                "keywords": ["payment", "plan", "installment", "finance", "pay later"],
            },
            {
                "category": "Payment",
                "question": "Is my payment information secure?",
                "answer": "Absolutely. We use 256-bit SSL encryption and are PCI DSS compliant. We never store full credit card numbers. For extra security, enable two-factor authentication in account settings.",
                "keywords": ["secure", "security", "payment", "safe", "protect", "ssl"],
            },
        ]

        for faq in faqs:
            self.kb.add_entry(
                category=faq["category"],
                question=faq["question"],
                answer=faq["answer"],
                keywords=faq["keywords"],
                subcategory=faq.get("subcategory"),
            )

    def start_session(self, customer_id: str) -> Session:
        """Start a new FAQ session."""
        session = Session(
            id=f"sess_{int(time.time())}_{customer_id}", customer_id=customer_id
        )
        self.sessions[session.id] = session
        return session

    def ask_question(
        self, session_id: str, question: str, category: Optional[str] = None
    ) -> dict:
        """Process a customer question."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        self.metrics["total_questions"] += 1

        # Record question
        session.questions_asked.append(
            {
                "question": question,
                "timestamp": datetime.now().isoformat(),
                "category": category,
            }
        )

        # Check for sensitive keywords
        if self._contains_sensitive(question):
            return self._escalate(
                session, question, None, 0.0, EscalationReason.SENSITIVE_TOPIC
            )

        # Find matching FAQ
        match_result = self.kb.find_match(question, category)

        # Update confidence metrics
        self._update_confidence_metrics(match_result.confidence)

        # Check for repeated questions (frustration indicator)
        if self._is_repeated_question(session, question):
            return self._escalate(
                session,
                question,
                match_result.faq_entry.id if match_result.faq_entry else None,
                match_result.confidence,
                EscalationReason.REPEATED_QUESTION,
            )

        # Check confidence threshold
        if match_result.should_escalate:
            if match_result.confidence_level == MatchConfidence.NONE:
                reason = EscalationReason.NO_MATCH
            else:
                reason = EscalationReason.LOW_CONFIDENCE

            return self._escalate(
                session,
                question,
                match_result.faq_entry.id if match_result.faq_entry else None,
                match_result.confidence,
                reason,
            )

        # Return matched FAQ
        faq = match_result.faq_entry
        self.kb.record_view(faq.id)
        session.faqs_viewed.append(faq.id)
        self.metrics["answered_directly"] += 1
        self.metrics["questions_by_category"][faq.category] += 1

        response = {
            "status": "answered",
            "faq_id": faq.id,
            "question": faq.question,
            "answer": faq.answer,
            "category": faq.category,
            "confidence": match_result.confidence,
            "confidence_level": match_result.confidence_level.value,
            "alternatives": match_result.alternative_matches,
            "related": self._get_related_faqs(faq),
        }

        if self.on_answer:
            self.on_answer(session, response)

        return response

    def _contains_sensitive(self, text: str) -> bool:
        """Check if text contains sensitive keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.sensitive_keywords)

    def _is_repeated_question(self, session: Session, question: str) -> bool:
        """Check if question has been asked repeatedly."""
        recent = session.questions_asked[-5:]
        similar_count = 0

        for prev in recent:
            similarity = self.kb.matcher.sequence_similarity(question, prev["question"])
            if similarity > 0.8:
                similar_count += 1

        return similar_count >= self.max_repeated_questions

    def _escalate(
        self,
        session: Session,
        question: str,
        matched_faq_id: Optional[str],
        confidence: float,
        reason: EscalationReason,
    ) -> dict:
        """Escalate question to human support."""
        self.escalation_counter += 1
        escalation_id = f"esc_{self.escalation_counter:06d}"

        escalation = Escalation(
            id=escalation_id,
            original_question=question,
            matched_faq_id=matched_faq_id,
            confidence=confidence,
            reason=reason,
            customer_id=session.customer_id,
            created_at=datetime.now(),
        )

        self.escalations[escalation_id] = escalation
        session.escalations.append(escalation_id)
        self.metrics["escalated"] += 1

        if self.on_escalation:
            self.on_escalation(session, escalation)

        # Provide partial answer if available
        partial_answer = None
        if matched_faq_id and confidence > 0.4:
            faq = self.kb.entries.get(matched_faq_id)
            if faq:
                partial_answer = {
                    "faq_id": faq.id,
                    "question": faq.question,
                    "answer": faq.answer,
                    "confidence": confidence,
                }

        return {
            "status": "escalated",
            "escalation_id": escalation_id,
            "reason": reason.value,
            "message": self._get_escalation_message(reason),
            "partial_answer": partial_answer,
            "estimated_wait": "5-10 minutes",
        }

    def _get_escalation_message(self, reason: EscalationReason) -> str:
        """Get appropriate escalation message."""
        messages = {
            EscalationReason.LOW_CONFIDENCE: "I want to make sure you get accurate information. Let me connect you with a specialist.",
            EscalationReason.REPEATED_QUESTION: "I notice my previous answer may not have fully addressed your needs. Let me get you to someone who can help better.",
            EscalationReason.CUSTOMER_REQUEST: "Of course! Let me connect you with a member of our support team.",
            EscalationReason.SENSITIVE_TOPIC: "I understand this is an important matter. Let me connect you with a specialist who can assist you.",
            EscalationReason.NO_MATCH: "I don't have information about that in my knowledge base. Let me find someone who can help.",
            EscalationReason.NEGATIVE_FEEDBACK: "I'm sorry my answer wasn't helpful. Let me get you to someone who can better assist you.",
        }
        return messages.get(reason, "Let me connect you with our support team.")

    def _get_related_faqs(self, faq: FAQEntry) -> list[dict]:
        """Get related FAQs."""
        related = []

        # Get explicitly linked FAQs
        for faq_id in faq.related_ids:
            if faq_id in self.kb.entries:
                entry = self.kb.entries[faq_id]
                related.append({"id": entry.id, "question": entry.question})

        # Get FAQs in same subcategory
        if faq.subcategory:
            for entry_id in self.kb.categories.get(faq.category, []):
                entry = self.kb.entries[entry_id]
                if (
                    entry.id != faq.id
                    and entry.subcategory == faq.subcategory
                    and len(related) < 3
                ):
                    related.append({"id": entry.id, "question": entry.question})

        return related[:3]

    def _update_confidence_metrics(self, confidence: float):
        """Update average confidence metric."""
        total = self.metrics["total_questions"]
        current_avg = self.metrics["avg_confidence"]
        self.metrics["avg_confidence"] = (
            current_avg * (total - 1) + confidence
        ) / total

    def provide_feedback(self, session_id: str, faq_id: str, feedback: FeedbackType):
        """Record feedback on an FAQ answer."""
        session = self.sessions.get(session_id)
        if not session:
            return

        self.kb.record_feedback(faq_id, feedback)
        session.feedback_given[faq_id] = feedback.value

        if feedback == FeedbackType.HELPFUL:
            self.metrics["helpful_responses"] += 1
        elif feedback == FeedbackType.NOT_HELPFUL:
            self.metrics["unhelpful_responses"] += 1

            # Consider escalating if unhelpful
            recent_unhelpful = sum(
                1
                for f in list(session.feedback_given.values())[-3:]
                if f == FeedbackType.NOT_HELPFUL.value
            )
            if recent_unhelpful >= 2:
                self._escalate(
                    session,
                    "Multiple unhelpful responses",
                    faq_id,
                    0.5,
                    EscalationReason.NEGATIVE_FEEDBACK,
                )

    def resolve_escalation(
        self, escalation_id: str, resolution_notes: str, new_faq: Optional[dict] = None
    ):
        """Resolve an escalation, optionally creating new FAQ."""
        escalation = self.escalations.get(escalation_id)
        if not escalation:
            return

        escalation.resolved = True
        escalation.resolution_notes = resolution_notes
        escalation.resolved_at = datetime.now()

        # Learn from escalation - create new FAQ
        if new_faq:
            self.kb.add_entry(
                category=new_faq["category"],
                question=new_faq["question"],
                answer=new_faq["answer"],
                keywords=new_faq.get("keywords", []),
                subcategory=new_faq.get("subcategory"),
            )
            escalation.new_faq_created = True
            self.metrics["learning_improvements"] += 1

    def get_categories(self) -> list[dict]:
        """Get list of FAQ categories."""
        return self.kb.get_categories()

    def browse_category(self, category: str) -> list[dict]:
        """Browse FAQs in a category."""
        entries = self.kb.get_by_category(category)
        return [e.to_dict() for e in entries]

    def get_popular_faqs(self, limit: int = 10) -> list[dict]:
        """Get most viewed FAQs."""
        sorted_entries = sorted(
            self.kb.entries.values(), key=lambda e: e.views, reverse=True
        )
        return [e.to_dict() for e in sorted_entries[:limit]]

    def get_metrics(self) -> dict:
        """Get FAQ bot metrics."""
        total = self.metrics["total_questions"]
        answered = self.metrics["answered_directly"]

        return {
            **self.metrics,
            "answer_rate": answered / max(total, 1) * 100,
            "escalation_rate": self.metrics["escalated"] / max(total, 1) * 100,
            "helpfulness_rate": (
                self.metrics["helpful_responses"]
                / max(
                    self.metrics["helpful_responses"]
                    + self.metrics["unhelpful_responses"],
                    1,
                )
                * 100
            ),
            "total_faqs": len(self.kb.entries),
            "categories": len(self.kb.categories),
            "pending_escalations": sum(
                1 for e in self.escalations.values() if not e.resolved
            ),
        }

    def get_learning_report(self) -> dict:
        """Get report on what should be learned from escalations."""
        pending = [e for e in self.escalations.values() if not e.resolved]

        # Group by reason
        by_reason = defaultdict(list)
        for esc in pending:
            by_reason[esc.reason.value].append(
                {
                    "id": esc.id,
                    "question": esc.original_question,
                    "confidence": esc.confidence,
                }
            )

        # Find patterns in questions
        all_questions = [e.original_question for e in pending]
        common_words = defaultdict(int)
        for q in all_questions:
            for word in self.kb.matcher.tokenize(q):
                common_words[word] += 1

        top_words = sorted(common_words.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "pending_escalations": len(pending),
            "by_reason": dict(by_reason),
            "common_topics": [{"word": w, "count": c} for w, c in top_words],
            "recommendations": self._generate_recommendations(by_reason),
        }

    def _generate_recommendations(self, by_reason: dict) -> list[str]:
        """Generate recommendations based on escalation patterns."""
        recs = []

        if len(by_reason.get(EscalationReason.NO_MATCH.value, [])) > 3:
            recs.append("Consider adding FAQs for frequently asked unmatched questions")

        if len(by_reason.get(EscalationReason.LOW_CONFIDENCE.value, [])) > 5:
            recs.append("Review and improve keyword coverage for existing FAQs")

        if len(by_reason.get(EscalationReason.REPEATED_QUESTION.value, [])) > 2:
            recs.append("Some answers may be unclear - review FAQ clarity")

        if len(by_reason.get(EscalationReason.NEGATIVE_FEEDBACK.value, [])) > 3:
            recs.append("Several FAQs receiving negative feedback - update answers")

        return recs


class FAQConsole:
    """Console interface for FAQ demo."""

    def __init__(self, bot: FAQBot):
        self.bot = bot
        self.session: Optional[Session] = None
        self.last_faq_id: Optional[str] = None

        # Wire callbacks
        self.bot.on_answer = self._on_answer
        self.bot.on_escalation = self._on_escalation

    def _on_answer(self, session: Session, response: dict):
        """Handle answer callback."""
        pass

    def _on_escalation(self, session: Session, escalation: Escalation):
        """Handle escalation callback."""
        print(f"\n  🔔 Escalation created: {escalation.id}")

    def print_header(self):
        """Print header."""
        print("\n" + "=" * 60)
        print(f"  📚 {self.bot.company_name} FAQ Center")
        print("=" * 60)
        print("  Ask questions about our products and services")
        print("  Commands: /categories /browse /popular /metrics /quit")
        print("-" * 60)

    def run(self, customer_id: str = "demo_customer"):
        """Run the FAQ console."""
        self.print_header()

        # Start session
        self.session = self.bot.start_session(customer_id)
        print(f"  Session started: {self.session.id}")

        while True:
            try:
                user_input = input("\n  Your question: ").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if self._handle_command(user_input):
                        break
                    continue

                # Check for feedback
                if user_input.lower() in ["yes", "y", "helpful"]:
                    if self.last_faq_id:
                        self.bot.provide_feedback(
                            self.session.id, self.last_faq_id, FeedbackType.HELPFUL
                        )
                        print("  ✅ Thank you for your feedback!")
                    continue
                elif user_input.lower() in ["no", "n", "not helpful"]:
                    if self.last_faq_id:
                        self.bot.provide_feedback(
                            self.session.id, self.last_faq_id, FeedbackType.NOT_HELPFUL
                        )
                        print(
                            "  📝 Thank you for your feedback. Let me find better help."
                        )
                    continue

                # Process question
                response = self.bot.ask_question(self.session.id, user_input)
                self._display_response(response)

            except KeyboardInterrupt:
                print("\n\n  Session ended.")
                break
            except Exception as e:
                print(f"\n  ❌ Error: {e}")

    def _handle_command(self, command: str) -> bool:
        """Handle slash commands. Returns True to exit."""
        cmd = command.lower().strip()

        if cmd == "/quit":
            print("\n  Goodbye!")
            return True

        if cmd == "/categories":
            cats = self.bot.get_categories()
            print("\n  📂 FAQ Categories:")
            for cat in cats:
                print(f"     • {cat['name']} ({cat['count']} FAQs)")
            return False

        if cmd.startswith("/browse"):
            parts = command.split(maxsplit=1)
            if len(parts) < 2:
                print("  Usage: /browse <category>")
                return False

            category = parts[1]
            faqs = self.bot.browse_category(category)

            if not faqs:
                print(f"  No FAQs found in '{category}'")
                return False

            print(f"\n  📖 {category} FAQs:")
            for faq in faqs:
                print(f"     • [{faq['id']}] {faq['question'][:50]}...")
            return False

        if cmd == "/popular":
            popular = self.bot.get_popular_faqs(5)
            print("\n  🔥 Popular FAQs:")
            for faq in popular:
                print(f"     • {faq['question'][:40]}... ({faq['views']} views)")
            return False

        if cmd == "/metrics":
            metrics = self.bot.get_metrics()
            print("\n  📊 FAQ Metrics:")
            print(f"     Total Questions: {metrics['total_questions']}")
            print(f"     Answer Rate: {metrics['answer_rate']:.1f}%")
            print(f"     Escalation Rate: {metrics['escalation_rate']:.1f}%")
            print(f"     Avg Confidence: {metrics['avg_confidence']:.2f}")
            print(f"     Helpfulness: {metrics['helpfulness_rate']:.1f}%")
            print(f"     Learning Improvements: {metrics['learning_improvements']}")
            return False

        if cmd == "/learning":
            report = self.bot.get_learning_report()
            print("\n  🎓 Learning Report:")
            print(f"     Pending Escalations: {report['pending_escalations']}")
            if report["common_topics"]:
                print("     Common Topics:", end=" ")
                print(", ".join(t["word"] for t in report["common_topics"][:5]))
            if report["recommendations"]:
                print("     Recommendations:")
                for rec in report["recommendations"]:
                    print(f"       → {rec}")
            return False

        print(f"  Unknown command: {command}")
        return False

    def _display_response(self, response: dict):
        """Display response from FAQ bot."""
        if response["status"] == "answered":
            print(f"\n  {'─' * 50}")
            print(f"  ❓ {response['question']}")
            print(f"  {'─' * 50}")
            print(f"\n  💡 {response['answer']}")
            print(
                f"\n  📊 Confidence: {response['confidence']:.0%} ({response['confidence_level']})"
            )

            self.last_faq_id = response["faq_id"]

            if response.get("alternatives"):
                print("\n  📝 Related questions:")
                for alt in response["alternatives"][:2]:
                    print(f"     • {alt['question'][:45]}...")

            print("\n  Was this helpful? (yes/no)")

        elif response["status"] == "escalated":
            print(f"\n  {'─' * 50}")
            print(f"  🎯 {response['message']}")
            print(f"  {'─' * 50}")
            print(f"  ⏱️  Estimated wait: {response['estimated_wait']}")

            if response.get("partial_answer"):
                partial = response["partial_answer"]
                print("\n  💭 In the meantime, this might help:")
                print(f"     {partial['answer'][:100]}...")
                print(f"     (Confidence: {partial['confidence']:.0%})")


def demo():
    """Run interactive FAQ demo."""
    bot = FAQBot(company_name="OfficeSupply Pro")
    console = FAQConsole(bot)
    console.run()


def automated_demo():
    """Run automated FAQ demo with various scenarios."""
    print("\n" + "=" * 60)
    print("  FAQ Bot - Automated Demo")
    print("=" * 60)

    bot = FAQBot(company_name="OfficeSupply Pro")

    # Start session
    session = bot.start_session("demo_user")

    # Test cases
    test_cases = [
        ("High confidence match", "What are your shipping options?"),
        ("Medium confidence", "How fast is delivery?"),
        ("Keyword match", "Do you have bulk discount for companies?"),
        ("Low confidence", "Can I get a custom quote for staplers?"),
        ("No match", "Do you sell live animals?"),
        ("Sensitive escalation", "I want to file a complaint with your manager"),
        ("Category specific", "What types of paper do you sell?"),
    ]

    print("\n--- Testing FAQ Matching ---\n")

    for name, question in test_cases:
        print(f"  📝 {name}")
        print(f"     Q: {question}")

        response = bot.ask_question(session.id, question)

        if response["status"] == "answered":
            print(f"     ✅ Matched: {response['question'][:40]}...")
            print(f"     📊 Confidence: {response['confidence']:.0%}")
        else:
            print(f"     🔄 Escalated: {response['reason']}")
            if response.get("partial_answer"):
                print(
                    f"     💭 Partial: {response['partial_answer']['question'][:30]}..."
                )

        print()

    # Test feedback loop
    print("--- Testing Feedback ---\n")

    response = bot.ask_question(session.id, "How do I return items?")
    if response["status"] == "answered":
        print("  Q: How do I return items?")
        print(f"  A: {response['answer'][:60]}...")

        # Simulate helpful feedback
        bot.provide_feedback(session.id, response["faq_id"], FeedbackType.HELPFUL)
        print("  👍 Feedback: Helpful")

    # Final metrics
    print("\n--- Final Metrics ---\n")
    metrics = bot.get_metrics()
    print(f"  Total Questions: {metrics['total_questions']}")
    print(f"  Answer Rate: {metrics['answer_rate']:.1f}%")
    print(f"  Escalation Rate: {metrics['escalation_rate']:.1f}%")
    print(f"  Avg Confidence: {metrics['avg_confidence']:.2f}")

    # Learning report
    print("\n--- Learning Report ---\n")
    report = bot.get_learning_report()
    print(f"  Pending Escalations: {report['pending_escalations']}")
    if report["recommendations"]:
        print("  Recommendations:")
        for rec in report["recommendations"]:
            print(f"    → {rec}")


if __name__ == "__main__":
    import sys

    if "--auto" in sys.argv:
        automated_demo()
    else:
        demo()
