#!/usr/bin/env python3
"""
Australian Family Law Legal Aid Chatbot
========================================

A comprehensive, accessible chatbot designed to help Australians navigate
the Family Court system. Built with empathy for:

- Fathers who often feel overlooked in family proceedings
- Mothers and children who may be victims of family violence
- People with disabilities who struggle with complex legal processes
- Self-represented litigants who cannot afford legal representation

RAG-Powered Architecture
========================
This chatbot demonstrates how to build a legal aid system using:
- Retrieval Augmented Generation (RAG) for knowledge lookup
- Vector embeddings for semantic search
- LLM routing with fallback chains
- Conversation memory for context
- Document loaders for training data

Legal firms load their OWN training data - this is a FRAMEWORK.

CRITICAL LEGAL DISCLAIMER
=========================
This chatbot provides GENERAL INFORMATION ONLY. It is NOT legal advice.
Every family law matter is unique and depends on specific circumstances.

You MUST consult a qualified family lawyer for advice on your situation.
Free legal help is available through:
- Legal Aid in your state/territory
- Community Legal Centres
- Family Relationship Centres
- Women's Legal Services (for family violence matters)

ACCESSIBILITY
=============
This chatbot is designed for VoiceOver and screen reader compatibility.
All outputs use clear, simple language suitable for audio presentation.

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

Version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

# Configure logging for accessibility - simple, clear messages
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# LEGAL DISCLAIMERS - These are CRITICAL and must be displayed prominently
# =============================================================================

MAIN_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                        IMPORTANT LEGAL DISCLAIMER                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ This chatbot provides GENERAL INFORMATION about Australian family law.       ║
║ It is NOT legal advice and should NOT be relied upon as such.               ║
║                                                                              ║
║ Every family law matter is unique. What applies to one case may not apply   ║
║ to yours. The information provided is general in nature and may not be      ║
║ current or complete.                                                         ║
║                                                                              ║
║ ALWAYS seek advice from a qualified family lawyer before:                    ║
║   • Filing any court documents                                               ║
║   • Attending court hearings                                                 ║
║   • Making decisions about your children                                     ║
║   • Negotiating property settlements                                         ║
║                                                                              ║
║ FREE LEGAL HELP IS AVAILABLE:                                               ║
║   • Legal Aid: 1300 888 529 (National)                                      ║
║   • Family Relationship Advice Line: 1800 050 321                           ║
║   • Community Legal Centres: Find at clcaustralia.org.au                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

VOICE_DISCLAIMER = (
    "Important disclaimer. This chatbot provides general information only, "
    "not legal advice. Every family law matter is unique. Always consult a "
    "qualified family lawyer before making any decisions. Free legal help is "
    "available through Legal Aid on 1300 888 529."
)


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================


class MatterPhase(Enum):
    """Phases of a family law matter through the Federal Circuit and Family Court."""

    INITIAL_CONSULTATION = auto()  # Just starting, gathering information
    PRE_ACTION = auto()  # Before filing - FDR, negotiation
    FDR_PROCESS = auto()  # Family Dispute Resolution
    FILING = auto()  # Initiating Application or Response
    INTERIM = auto()  # Interim hearings (urgent matters)
    COMPLIANCE = auto()  # Compliance and Readiness Hearing
    CONCILIATION = auto()  # Conciliation Conference
    FINAL_HEARING = auto()  # Trial
    POST_ORDERS = auto()  # After final orders made
    CONTRAVENTION = auto()  # Enforcement of orders
    APPEAL = auto()  # Appeals (rare)


class DocumentType(Enum):
    """Types of documents in family law proceedings."""

    INITIATING_APPLICATION = "Initiating Application"
    RESPONSE = "Response to Initiating Application"
    AFFIDAVIT = "Affidavit"
    NOTICE_OF_RISK = "Notice of Child Abuse, Family Violence or Risk"
    CONSENT_ORDERS = "Application for Consent Orders"
    PARENTING_PLAN = "Parenting Plan (not filed)"
    FINANCIAL_STATEMENT = "Financial Statement"
    CONTRAVENTION_APPLICATION = "Contravention Application"
    RECOVERY_ORDER = "Recovery Order Application"
    S60I_CERTIFICATE = "Section 60I Certificate"
    SUBPOENA = "Subpoena"
    CASE_OUTLINE = "Case Outline"
    MINUTE_OF_ORDERS = "Minute of Consent Orders"


class RiskLevel(Enum):
    """Risk assessment levels for safety monitoring."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"  # Immediate danger


class EmotionalState(Enum):
    """Detected emotional states for empathetic responses."""

    CALM = auto()
    ANXIOUS = auto()
    DISTRESSED = auto()
    ANGRY = auto()
    OVERWHELMED = auto()
    HOPELESS = auto()
    CRISIS = auto()


@dataclass
class Deadline:
    """A deadline in family law proceedings."""

    description: str
    due_date: datetime
    document_type: Optional[DocumentType] = None
    court_event: bool = False
    reminder_days: list[int] = field(default_factory=lambda: [7, 3, 1])
    completed: bool = False
    notes: str = ""

    def days_remaining(self) -> int:
        """Calculate days until deadline."""
        delta = self.due_date - datetime.now()
        return delta.days

    def is_overdue(self) -> bool:
        """Check if deadline has passed."""
        return datetime.now() > self.due_date

    def to_voice(self) -> str:
        """Generate VoiceOver-friendly description."""
        days = self.days_remaining()
        if days < 0:
            return f"OVERDUE by {abs(days)} days: {self.description}"
        elif days == 0:
            return f"DUE TODAY: {self.description}"
        elif days == 1:
            return f"Due tomorrow: {self.description}"
        else:
            return f"Due in {days} days: {self.description}"


@dataclass
class FamilyLawCase:
    """Represents a user's family law matter."""

    case_id: str
    created_at: datetime
    matter_type: str  # "parenting", "property", "both"
    phase: MatterPhase = MatterPhase.INITIAL_CONSULTATION

    # Court details
    court_file_number: Optional[str] = None
    court_location: Optional[str] = None
    judge_name: Optional[str] = None

    # Parties
    user_role: str = "applicant"  # "applicant" or "respondent"
    other_party_name: Optional[str] = None
    children_count: int = 0
    children_ages: list[int] = field(default_factory=list)

    # Deadlines and documents
    deadlines: list[Deadline] = field(default_factory=list)
    documents_filed: list[str] = field(default_factory=list)
    documents_needed: list[DocumentType] = field(default_factory=list)

    # Risk and safety
    family_violence_disclosed: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    icl_appointed: bool = False  # Independent Children's Lawyer

    # Notes and history
    notes: list[str] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)

    def add_deadline(
        self,
        description: str,
        due_date: datetime,
        doc_type: Optional[DocumentType] = None,
        court_event: bool = False,
    ) -> Deadline:
        """Add a new deadline to the case."""
        deadline = Deadline(
            description=description,
            due_date=due_date,
            document_type=doc_type,
            court_event=court_event,
        )
        self.deadlines.append(deadline)
        return deadline

    def get_upcoming_deadlines(self, days: int = 30) -> list[Deadline]:
        """Get deadlines within the specified number of days."""
        cutoff = datetime.now() + timedelta(days=days)
        return [d for d in self.deadlines if not d.completed and d.due_date <= cutoff]

    def to_summary(self) -> str:
        """Generate a VoiceOver-friendly case summary."""
        lines = [
            f"Case Summary for matter {self.court_file_number or 'not yet filed'}",
            f"Matter type: {self.matter_type}",
            f"Current phase: {self.phase.name.replace('_', ' ').title()}",
            f"Your role: {self.user_role.title()}",
        ]

        if self.children_count:
            lines.append(f"Children involved: {self.children_count}")

        upcoming = self.get_upcoming_deadlines(14)
        if upcoming:
            lines.append(f"Upcoming deadlines: {len(upcoming)}")
            for d in upcoming[:3]:
                lines.append(f"  - {d.to_voice()}")

        return "\n".join(lines)


# =============================================================================
# SAFETY MONITOR - Critical for family violence detection
# =============================================================================


class SafetyMonitor:
    """
    Monitors conversations for signs of family violence and risk.

    CRITICAL: Family law matters often involve domestic violence.
    This monitor helps identify when users may be in danger and
    provides appropriate resources and support.
    """

    # Keywords and phrases that may indicate violence or risk
    VIOLENCE_INDICATORS = [
        "hit me",
        "hits me",
        "hitting me",
        "hurt me",
        "hurts me",
        "hurting me",
        "threatens",
        "threatened",
        "threatening",
        "scared of",
        "afraid of",
        "fear for",
        "abuse",
        "abusive",
        "abused",
        "control",
        "controlling",
        "controlled",
        "stalk",
        "stalking",
        "stalked",
        "won't let me",
        "doesn't let me",
        "taken the kids",
        "took my children",
        "hiding the children",
        "hiding my kids",
        "kill me",
        "kill myself",
        "end it all",
        "no way out",
        "trapped",
        "strangled",
        "choked",
        "choking",
        "weapon",
        "gun",
        "knife",
        "restraining order",
        "intervention order",
        "avo",
        "dvo",
        "domestic violence order",
        "police",
        "called the cops",
        "bruises",
        "injuries",
        "hospital",
    ]

    CRISIS_INDICATORS = [
        "kill",
        "suicide",
        "die",
        "end my life",
        "can't go on",
        "no point",
        "give up",
        "hurt myself",
        "harm myself",
        "emergency",
        "danger right now",
        "he's here",
        "she's here",
        "they're here",
        "being followed",
        "following me",
        "kidnapped",
        "taken",
        "abducted",
    ]

    EMERGENCY_CONTACTS = {
        "police": "000 (Triple Zero)",
        "lifeline": "13 11 14 (24/7 crisis support)",
        "1800respect": "1800 737 732 (Family violence helpline)",
        "mensline": "1300 78 99 78 (Support for men)",
        "kids_helpline": "1800 55 1800 (For children and young people)",
        "legal_aid": "1300 888 529 (National Legal Aid)",
        "family_relationship": "1800 050 321 (Family Relationship Advice Line)",
    }

    STATE_DV_SERVICES = {
        "NSW": "Domestic Violence Line: 1800 656 463",
        "VIC": "Safe Steps: 1800 015 188",
        "QLD": "DVConnect: 1800 811 811",
        "WA": "Women's Domestic Violence Helpline: 1800 007 339",
        "SA": "Domestic Violence Crisis Line: 1800 800 098",
        "TAS": "Family Violence Counselling Line: 1800 608 122",
        "NT": "Dawn House: 1800 093 081",
        "ACT": "Domestic Violence Crisis Service: (02) 6280 0900",
    }

    def __init__(self):
        """Initialize the safety monitor."""
        self.violence_mentioned = False
        self.risk_level = RiskLevel.LOW
        self.crisis_detected = False
        self.flags: list[str] = []

    def analyze_message(self, message: str) -> dict[str, Any]:
        """
        Analyze a message for safety concerns.

        Returns a dictionary with:
        - risk_level: RiskLevel enum
        - flags: list of concerning phrases found
        - requires_intervention: bool
        - resources: list of relevant resources
        - response_prefix: optional safety message to prepend
        """
        message_lower = message.lower()

        # Check for crisis indicators first (highest priority)
        crisis_flags = [
            indicator
            for indicator in self.CRISIS_INDICATORS
            if indicator in message_lower
        ]

        if crisis_flags:
            self.crisis_detected = True
            self.risk_level = RiskLevel.CRITICAL
            self.flags.extend(crisis_flags)

            return {
                "risk_level": RiskLevel.CRITICAL,
                "flags": crisis_flags,
                "requires_intervention": True,
                "resources": self._get_crisis_resources(),
                "response_prefix": self._get_crisis_response(),
            }

        # Check for violence indicators
        violence_flags = [
            indicator
            for indicator in self.VIOLENCE_INDICATORS
            if indicator in message_lower
        ]

        if violence_flags:
            self.violence_mentioned = True
            # Assess severity based on number and type of flags
            if len(violence_flags) >= 3:
                self.risk_level = RiskLevel.HIGH
            elif len(violence_flags) >= 1:
                self.risk_level = max(self.risk_level, RiskLevel.MODERATE)

            self.flags.extend(violence_flags)

            return {
                "risk_level": self.risk_level,
                "flags": violence_flags,
                "requires_intervention": self.risk_level == RiskLevel.HIGH,
                "resources": self._get_dv_resources(),
                "response_prefix": self._get_safety_message(),
            }

        return {
            "risk_level": self.risk_level,
            "flags": [],
            "requires_intervention": False,
            "resources": [],
            "response_prefix": None,
        }

    def _get_crisis_response(self) -> str:
        """Get immediate crisis intervention response."""
        return """
🚨 I'M CONCERNED ABOUT YOUR SAFETY 🚨

If you are in immediate danger, please call 000 (Triple Zero) right now.

If you are having thoughts of suicide or self-harm, please call:
• Lifeline: 13 11 14 (24 hours, 7 days)
• Beyond Blue: 1300 22 4636

You are not alone. Help is available right now.

Would you like me to continue, or would you prefer to speak with
a crisis counsellor first?
"""

    def _get_safety_message(self) -> str:
        """Get safety-aware message prefix."""
        return """
I hear that you may be experiencing family violence or safety concerns.
Your safety and your children's safety is the most important thing.

If you are in danger, please call 000 immediately.

For support with family violence:
• 1800RESPECT: 1800 737 732 (24/7)

I'll continue to help you with your family law matter, but please
reach out to these services if you need immediate support.

"""

    def _get_crisis_resources(self) -> list[str]:
        """Get crisis support resources."""
        return [
            "Police/Ambulance/Fire: 000",
            "Lifeline (24/7 crisis support): 13 11 14",
            "Suicide Call Back Service: 1300 659 467",
            "1800RESPECT (family violence): 1800 737 732",
        ]

    def _get_dv_resources(self) -> list[str]:
        """Get domestic violence resources."""
        return [
            "1800RESPECT (National DV Helpline): 1800 737 732",
            "MensLine Australia: 1300 78 99 78",
            "Kids Helpline: 1800 55 1800",
            "Legal Aid (free legal help): 1300 888 529",
        ]

    def get_state_resources(self, state: str) -> str:
        """Get state-specific DV resources."""
        state_upper = state.upper()
        if state_upper in self.STATE_DV_SERVICES:
            return self.STATE_DV_SERVICES[state_upper]
        return "Contact 1800RESPECT on 1800 737 732 for your local services."

    def to_voice(self) -> str:
        """Generate VoiceOver-friendly safety summary."""
        if self.crisis_detected:
            return (
                "SAFETY ALERT. Crisis indicators detected. "
                "If you are in immediate danger, call triple zero. "
                "For crisis support, call Lifeline on 13 11 14."
            )
        elif self.violence_mentioned:
            return (
                "Safety note. Family violence concerns noted. "
                "For support, call 1800 RESPECT on 1800 737 732."
            )
        return "No immediate safety concerns detected."


# =============================================================================
# LEGAL KNOWLEDGE BASE - Australian Family Law
# =============================================================================


class LegalKnowledgeBase:
    """
    Australian Family Law knowledge base for RAG integration.

    Covers the Family Law Act 1975 (as amended), Federal Circuit and
    Family Court procedures, and practical guidance for litigants.

    NOTE: This is educational information only, not legal advice.
    """

    def __init__(self):
        """Initialize the legal knowledge base."""
        self.knowledge: dict[str, dict] = {}
        self._load_core_knowledge()

    def _load_core_knowledge(self):
        """Load core Australian family law knowledge."""

        # Family Law Act 1975 - Key Sections
        self.knowledge["family_law_act"] = {
            "title": "Family Law Act 1975 (Cth)",
            "description": "The primary legislation governing family law in Australia",
            "last_updated": "2024",
            "sections": {
                "s60B": {
                    "title": "Objects and Principles - Children",
                    "content": (
                        "Section 60B sets out that children have a right to know "
                        "and be cared for by both parents, to spend time and "
                        "communicate with both parents and other significant people, "
                        "and to be protected from harm. The best interests of the "
                        "child are the paramount consideration."
                    ),
                },
                "s60CA": {
                    "title": "Best Interests of the Child - Paramount",
                    "content": (
                        "Section 60CA establishes that the child's best interests "
                        "are the paramount consideration in making parenting orders. "
                        "This means the child's welfare comes before all other "
                        "considerations, including the wishes of parents."
                    ),
                },
                "s60CC": {
                    "title": "Determining Best Interests",
                    "content": (
                        "Section 60CC sets out how courts determine best interests. "
                        "Primary considerations include: (1) the benefit of having "
                        "a meaningful relationship with both parents, and (2) the "
                        "need to protect the child from harm including family "
                        "violence, abuse, or neglect. Additional considerations "
                        "include the child's views, nature of relationships, and "
                        "practical difficulties."
                    ),
                },
                "s60I": {
                    "title": "Family Dispute Resolution Certificates",
                    "content": (
                        "Section 60I requires parties to attempt Family Dispute "
                        "Resolution (FDR) before filing parenting applications. "
                        "A Section 60I certificate is issued by an FDR practitioner "
                        "and is required to file most parenting applications. "
                        "Exceptions exist for urgency, family violence, and other "
                        "circumstances defined in the regulations."
                    ),
                },
                "s65DAA": {
                    "title": "Parental Responsibility",
                    "content": (
                        "Section 65DAA deals with allocation of parental "
                        "responsibility. Courts can order sole or joint parental "
                        "responsibility for major long-term decisions including "
                        "education, health, religion, and name changes. Day-to-day "
                        "decisions are generally made by the parent with the child."
                    ),
                },
                "s70NAE": {
                    "title": "Contravention - Reasonable Excuse",
                    "content": (
                        "Section 70NAE sets out when a person has a reasonable "
                        "excuse for contravening a parenting order. This includes "
                        "where the person believed the action was necessary to "
                        "protect the child from harm, and where the action was "
                        "reasonable given the circumstances."
                    ),
                },
                "s79": {
                    "title": "Property Settlement Orders",
                    "content": (
                        "Section 79 gives the court power to make property orders. "
                        "The court considers: (1) contributions (financial and "
                        "non-financial, including homemaker/parent), (2) future "
                        "needs (age, health, income, care of children), and "
                        "(3) whether the proposed order is just and equitable."
                    ),
                },
                "s90SM": {
                    "title": "Superannuation Splitting",
                    "content": (
                        "Section 90SM allows superannuation to be split between "
                        "parties on separation. Superannuation is treated as "
                        "property. Orders can split super interests or flag them "
                        "for future payment. Procedural requirements apply."
                    ),
                },
            },
        }

        # Court Procedures
        self.knowledge["court_procedures"] = {
            "title": "Federal Circuit and Family Court Procedures",
            "filing": {
                "initiating_application": (
                    "An Initiating Application starts a family law matter. "
                    "For parenting matters, you need a Section 60I certificate "
                    "(or exemption). File at the Commonwealth Courts Portal. "
                    "Current filing fee is approximately $395 (2024), but fee "
                    "reductions are available for those experiencing financial "
                    "hardship. Response is due within 28 days."
                ),
                "response": (
                    "A Response to Initiating Application must be filed within "
                    "28 days of being served. If you don't respond, the court "
                    "may make orders in your absence. Always file a response "
                    "to protect your rights."
                ),
                "notice_of_risk": (
                    "Form 4 - Notice of Child Abuse, Family Violence or Risk "
                    "MUST be filed with any parenting application if there are "
                    "allegations or concerns about child abuse or family violence. "
                    "This is mandatory. Failure to disclose can be serious."
                ),
                "affidavit": (
                    "An Affidavit is a sworn statement of facts. It must be "
                    "signed in front of a Justice of the Peace, lawyer, or "
                    "other authorised witness. Everything in an affidavit must "
                    "be true - lying in an affidavit is a criminal offence."
                ),
            },
            "hearings": {
                "first_return_date": (
                    "The First Court Date (formerly First Return Date) is an "
                    "initial administrative hearing. The court will give "
                    "directions about what needs to happen next. This is not "
                    "a trial - no evidence is heard."
                ),
                "compliance_and_readiness": (
                    "The Compliance and Readiness Hearing checks that parties "
                    "have complied with court orders and are ready for trial. "
                    "If issues remain, the court may order further steps or "
                    "a Conciliation Conference."
                ),
                "conciliation": (
                    "A Conciliation Conference is a settlement meeting conducted "
                    "by a Registrar. Parties try to reach agreement with the "
                    "help of a judicial officer. If agreement is reached, "
                    "consent orders can be made. If not, the matter proceeds "
                    "to trial."
                ),
                "interim_hearing": (
                    "An Interim Hearing deals with urgent matters that can't "
                    "wait for a final hearing. Common issues include: where "
                    "children will live pending trial, urgent parenting issues, "
                    "and interim property orders. Evidence is usually limited "
                    "to affidavits."
                ),
                "final_hearing": (
                    "The Final Hearing (trial) is where the court makes final "
                    "orders. Both parties present evidence (affidavits and "
                    "oral testimony), cross-examine witnesses, and make "
                    "submissions. A judge then makes a decision."
                ),
            },
            "efiling": {
                "portal": "Commonwealth Courts Portal: comcourts.gov.au",
                "registration": (
                    "To efile, create an account at the Commonwealth Courts "
                    "Portal. You need valid ID and an email address. "
                    "Self-represented litigants can efile most documents."
                ),
                "service": (
                    "After filing, documents must be served on the other party. "
                    "The Initiating Application must be personally served "
                    "(handed to them). Subsequent documents can often be served "
                    "by email if the party has consented."
                ),
            },
        }

        # Family Dispute Resolution
        self.knowledge["fdr"] = {
            "title": "Family Dispute Resolution (FDR)",
            "description": (
                "Family Dispute Resolution is mediation for family disputes. "
                "It is usually required before going to court for parenting "
                "matters. FDR helps families reach agreement without the "
                "cost and stress of court proceedings."
            ),
            "where_to_go": [
                "Family Relationship Centres (government funded, free or low cost)",
                "Private FDR practitioners (fee for service)",
                "Legal Aid mediation services",
                "Community mediation centres",
            ],
            "s60i_certificates": {
                "types": [
                    "All parties participated genuinely",
                    "One party did not participate genuinely",
                    "FDR was inappropriate (e.g., family violence)",
                    "The other party refused to attend",
                ],
                "exemptions": (
                    "You may not need a Section 60I certificate if: "
                    "there has been family violence or child abuse, "
                    "the matter is urgent, one party is unable to participate "
                    "effectively, or other circumstances in the regulations."
                ),
            },
        }

        # Parenting Orders
        self.knowledge["parenting_orders"] = {
            "title": "Parenting Orders",
            "types": {
                "who_lives_with": (
                    "Orders about who a child lives with. A child may live "
                    "primarily with one parent or have shared care arrangements."
                ),
                "time_with": (
                    "Orders about time a child spends with each parent. "
                    "This can range from supervised time to equal shared care."
                ),
                "communication": (
                    "Orders about how a child communicates with a parent they "
                    "don't live with, including phone calls, video calls, etc."
                ),
                "parental_responsibility": (
                    "Orders about who makes major long-term decisions for a child. "
                    "Can be sole (one parent) or joint (both parents together)."
                ),
            },
            "enforcement": (
                "Parenting orders are enforceable by the court. If someone "
                "breaches an order without reasonable excuse, the court can "
                "impose penalties including fines, community service, "
                "imprisonment (in serious cases), or varying the orders."
            ),
        }

        # Consent Orders
        self.knowledge["consent_orders"] = {
            "title": "Consent Orders",
            "description": (
                "Consent Orders are orders made by the court when both parties "
                "agree. They have the same force as orders made after a trial. "
                "Filing consent orders is much cheaper and faster than going "
                "to trial."
            ),
            "process": [
                "1. Negotiate an agreement with the other party",
                "2. Draft a Minute of Consent Orders",
                "3. Both parties sign the application",
                "4. File the Application for Consent Orders (Form 11)",
                "5. A Registrar reviews and may approve without a hearing",
            ],
            "filing_fee": "Approximately $180 (2024) - fee reductions available",
        }

        # Recovery Orders
        self.knowledge["recovery_orders"] = {
            "title": "Recovery Orders (Urgent)",
            "description": (
                "A Recovery Order is an urgent order for the return of a child. "
                "Used when a child has been taken or retained in breach of "
                "parenting orders or where there's no order but the child "
                "has been wrongfully removed."
            ),
            "process": (
                "Recovery orders can be applied for urgently, sometimes without "
                "notice to the other party. The court can order the AFP or "
                "state police to locate and recover the child."
            ),
            "when_to_apply": [
                "Child taken interstate or overseas in breach of orders",
                "Child not returned after agreed time",
                "Serious concern for child's immediate safety",
                "Child abducted or hidden",
            ],
        }

        # Independent Children's Lawyer
        self.knowledge["icl"] = {
            "title": "Independent Children's Lawyer (ICL)",
            "description": (
                "An ICL is a lawyer appointed by the court to represent the "
                "best interests of the children. The ICL is independent of "
                "both parents and focuses on what is best for the child."
            ),
            "when_appointed": [
                "Allegations of child abuse or neglect",
                "Family violence concerns",
                "High conflict between parents",
                "Children have strong views that need representation",
                "Complex or difficult cases",
                "Allegations of alienation",
            ],
            "role": (
                "The ICL gathers evidence, may arrange family reports, "
                "speaks with the children (age-appropriate), and makes "
                "submissions to the court about what is in the children's "
                "best interests. The ICL is not a witness but an officer "
                "of the court."
            ),
        }

        # Property Settlement
        self.knowledge["property"] = {
            "title": "Property Settlement",
            "description": (
                "Property settlement divides assets and liabilities after "
                "separation. The court follows a four-step process to "
                "determine a just and equitable division."
            ),
            "four_step_process": [
                "1. Identify and value the property pool (all assets and debts)",
                "2. Assess contributions (financial, non-financial, homemaker/parent)",
                "3. Consider future needs (Section 75(2) factors)",
                "4. Determine if the result is just and equitable overall",
            ],
            "time_limits": (
                "You must apply within 12 months of divorce (married couples) "
                "or 2 years of separation (de facto couples). Extensions are "
                "possible but not guaranteed."
            ),
            "superannuation": (
                "Superannuation is treated as property and can be split. "
                "You need valuations from the super funds. Splitting orders "
                "are complex - seek legal advice."
            ),
        }

        # Contravention
        self.knowledge["contravention"] = {
            "title": "Contravention Applications",
            "description": (
                "A contravention application is filed when someone breaches "
                "a parenting order without reasonable excuse. The court can "
                "impose penalties and vary orders."
            ),
            "reasonable_excuse": (
                "A person may have a reasonable excuse if they believed on "
                "reasonable grounds that the action was necessary to protect "
                "the child from harm, or the contravention was due to "
                "circumstances beyond their control."
            ),
            "penalties": [
                "Community service",
                "Fine",
                "Compensation for costs",
                "Variation of orders (e.g., more time to make up)",
                "Imprisonment (for serious, repeated breaches)",
            ],
            "before_filing": (
                "Before filing a contravention, consider: Is there a genuine "
                "breach? Was there a reasonable excuse? Have you tried to "
                "resolve it directly? A lawyer can help assess your case."
            ),
        }

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Search the knowledge base for relevant information.

        In a production system, this would use vector embeddings and
        semantic search. For this demo, we use keyword matching.
        """
        query_lower = query.lower()
        results = []

        # Simple keyword matching for demo purposes
        keywords = query_lower.split()

        for category, content in self.knowledge.items():
            score = 0
            matched_content = []

            # Check title
            if isinstance(content, dict) and "title" in content:
                if any(kw in content["title"].lower() for kw in keywords):
                    score += 10

            # Deep search in content
            self._search_recursive(content, keywords, matched_content, score)

            if matched_content:
                results.append(
                    {
                        "category": category,
                        "matches": matched_content,
                        "score": len(matched_content),
                    }
                )

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _search_recursive(
        self, obj: Any, keywords: list[str], results: list, score: int
    ):
        """Recursively search nested structures."""
        if isinstance(obj, str):
            if any(kw in obj.lower() for kw in keywords):
                results.append(obj)
        elif isinstance(obj, dict):
            for _key, value in obj.items():
                self._search_recursive(value, keywords, results, score)
        elif isinstance(obj, list):
            for item in obj:
                self._search_recursive(item, keywords, results, score)

    def get_section(self, section_id: str) -> Optional[dict]:
        """Get a specific section from the Family Law Act."""
        sections = self.knowledge.get("family_law_act", {}).get("sections", {})
        return sections.get(section_id)

    def get_procedure(self, procedure_type: str) -> Optional[dict]:
        """Get information about a court procedure."""
        procedures = self.knowledge.get("court_procedures", {})
        return procedures.get(procedure_type)


# =============================================================================
# CASE MANAGER - Track matters, deadlines, phases
# =============================================================================


class CaseManager:
    """
    Manages family law cases, including deadlines, documents, and phases.

    Provides persistent case tracking across sessions to help users
    stay on top of their family law matters.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the case manager."""
        self.storage_path = storage_path or Path.home() / ".family_law_bot"
        self.storage_path.mkdir(exist_ok=True)
        self.cases: dict[str, FamilyLawCase] = {}
        self._load_cases()

    def _load_cases(self):
        """Load cases from persistent storage."""
        cases_file = self.storage_path / "cases.json"
        if cases_file.exists():
            try:
                with open(cases_file) as f:
                    data = json.load(f)
                    for case_id, case_data in data.items():
                        self.cases[case_id] = self._deserialize_case(case_data)
            except Exception as e:
                logger.warning(f"Could not load cases: {e}")

    def _save_cases(self):
        """Save cases to persistent storage."""
        cases_file = self.storage_path / "cases.json"
        try:
            data = {
                case_id: self._serialize_case(case)
                for case_id, case in self.cases.items()
            }
            with open(cases_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save cases: {e}")

    def _serialize_case(self, case: FamilyLawCase) -> dict:
        """Serialize a case to JSON-compatible dict."""
        return {
            "case_id": case.case_id,
            "created_at": case.created_at.isoformat(),
            "matter_type": case.matter_type,
            "phase": case.phase.name,
            "court_file_number": case.court_file_number,
            "court_location": case.court_location,
            "user_role": case.user_role,
            "other_party_name": case.other_party_name,
            "children_count": case.children_count,
            "children_ages": case.children_ages,
            "family_violence_disclosed": case.family_violence_disclosed,
            "risk_level": case.risk_level.value,
            "icl_appointed": case.icl_appointed,
            "notes": case.notes,
            "deadlines": [
                {
                    "description": d.description,
                    "due_date": d.due_date.isoformat(),
                    "document_type": d.document_type.value if d.document_type else None,
                    "court_event": d.court_event,
                    "completed": d.completed,
                }
                for d in case.deadlines
            ],
            "documents_filed": case.documents_filed,
        }

    def _deserialize_case(self, data: dict) -> FamilyLawCase:
        """Deserialize a case from JSON dict."""
        case = FamilyLawCase(
            case_id=data["case_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            matter_type=data["matter_type"],
        )
        case.phase = MatterPhase[data["phase"]]
        case.court_file_number = data.get("court_file_number")
        case.court_location = data.get("court_location")
        case.user_role = data.get("user_role", "applicant")
        case.other_party_name = data.get("other_party_name")
        case.children_count = data.get("children_count", 0)
        case.children_ages = data.get("children_ages", [])
        case.family_violence_disclosed = data.get("family_violence_disclosed", False)
        case.risk_level = RiskLevel(data.get("risk_level", "low"))
        case.icl_appointed = data.get("icl_appointed", False)
        case.notes = data.get("notes", [])
        case.documents_filed = data.get("documents_filed", [])

        for d_data in data.get("deadlines", []):
            doc_type = None
            if d_data.get("document_type"):
                doc_type = DocumentType(d_data["document_type"])
            deadline = Deadline(
                description=d_data["description"],
                due_date=datetime.fromisoformat(d_data["due_date"]),
                document_type=doc_type,
                court_event=d_data.get("court_event", False),
                completed=d_data.get("completed", False),
            )
            case.deadlines.append(deadline)

        return case

    def create_case(
        self, matter_type: str, user_role: str = "applicant"
    ) -> FamilyLawCase:
        """Create a new case."""
        case_id = hashlib.sha256(
            f"{datetime.now().isoformat()}{matter_type}".encode()
        ).hexdigest()[:12]

        case = FamilyLawCase(
            case_id=case_id,
            created_at=datetime.now(),
            matter_type=matter_type,
            user_role=user_role,
        )

        self.cases[case_id] = case
        self._save_cases()

        return case

    def get_case(self, case_id: str) -> Optional[FamilyLawCase]:
        """Get a case by ID."""
        return self.cases.get(case_id)

    def get_active_cases(self) -> list[FamilyLawCase]:
        """Get all active (non-closed) cases."""
        return [
            case
            for case in self.cases.values()
            if case.phase not in [MatterPhase.POST_ORDERS]
        ]

    def update_phase(self, case_id: str, new_phase: MatterPhase):
        """Update the phase of a case."""
        case = self.get_case(case_id)
        if case:
            case.phase = new_phase
            case.notes.append(f"Phase updated to {new_phase.name} on {datetime.now()}")
            self._save_cases()

    def add_deadline(
        self,
        case_id: str,
        description: str,
        due_date: datetime,
        document_type: Optional[DocumentType] = None,
        court_event: bool = False,
    ) -> Optional[Deadline]:
        """Add a deadline to a case."""
        case = self.get_case(case_id)
        if case:
            deadline = case.add_deadline(
                description, due_date, document_type, court_event
            )
            self._save_cases()
            return deadline
        return None

    def complete_deadline(self, case_id: str, deadline_index: int):
        """Mark a deadline as completed."""
        case = self.get_case(case_id)
        if case and 0 <= deadline_index < len(case.deadlines):
            case.deadlines[deadline_index].completed = True
            self._save_cases()

    def get_upcoming_deadlines(
        self, days: int = 14
    ) -> list[tuple[FamilyLawCase, Deadline]]:
        """Get all upcoming deadlines across all cases."""
        results = []
        for case in self.cases.values():
            for deadline in case.get_upcoming_deadlines(days):
                results.append((case, deadline))

        results.sort(key=lambda x: x[1].due_date)
        return results

    def get_overdue_deadlines(self) -> list[tuple[FamilyLawCase, Deadline]]:
        """Get all overdue deadlines across all cases."""
        results = []
        for case in self.cases.values():
            for deadline in case.deadlines:
                if not deadline.completed and deadline.is_overdue():
                    results.append((case, deadline))

        results.sort(key=lambda x: x[1].due_date)
        return results


# =============================================================================
# DOCUMENT HELPER - Template guidance
# =============================================================================


class DocumentHelper:
    """
    Provides guidance on preparing family law documents.

    NOTE: This does not generate legal documents. It provides
    educational information about what documents contain and
    how to prepare them. Always have a lawyer review documents.
    """

    DOCUMENT_GUIDANCE = {
        DocumentType.INITIATING_APPLICATION: {
            "title": "Initiating Application",
            "form_number": "Form 1",
            "description": (
                "The Initiating Application starts your court case. "
                "It tells the court what orders you are asking for."
            ),
            "key_sections": [
                "Your details (name, address, contact)",
                "Other party's details",
                "Children's details (for parenting matters)",
                "The orders you are seeking",
                "Grounds for the orders",
            ],
            "common_mistakes": [
                "Not being specific about the orders sought",
                "Forgetting to attach required documents",
                "Not filing the Notice of Risk when required",
                "Missing the Section 60I certificate",
            ],
            "filing_fee": "$395 (2024, subject to change)",
            "filing_tips": [
                "File online at comcourts.gov.au",
                "Fee reductions available for financial hardship",
                "Keep copies of everything you file",
            ],
        },
        DocumentType.RESPONSE: {
            "title": "Response to Initiating Application",
            "form_number": "Form 2",
            "description": (
                "The Response is filed by the person who receives an "
                "Initiating Application. You have 28 days to respond."
            ),
            "key_sections": [
                "Your details",
                "Whether you agree or disagree with each order sought",
                "What orders you want instead (cross-application)",
                "Your grounds",
            ],
            "common_mistakes": [
                "Missing the 28-day deadline",
                "Not filing a Notice of Risk when required",
                "Being too aggressive or emotional",
                "Not seeking your own orders",
            ],
            "deadline_warning": (
                "IMPORTANT: You have 28 days from being served to file "
                "your Response. If you miss this deadline, the court may "
                "make orders without hearing from you."
            ),
        },
        DocumentType.AFFIDAVIT: {
            "title": "Affidavit",
            "description": (
                "An Affidavit is your sworn statement of facts. "
                "Everything in it must be true. Lying in an affidavit "
                "is a criminal offence called perjury."
            ),
            "structure": [
                "1. Your personal details",
                "2. Your relationship to the matter",
                "3. Numbered paragraphs stating facts",
                "4. Attach supporting documents as annexures",
                "5. Signature and witness",
            ],
            "rules": [
                "Only state facts you personally know",
                "If relying on what someone told you, say 'X told me...'",
                "Be specific with dates and times",
                "Don't include legal arguments - just facts",
                "Keep it focused and relevant",
            ],
            "witnessing": (
                "Your affidavit must be signed in front of an authorised "
                "witness: a Justice of the Peace, lawyer, or other person "
                "authorised to witness affidavits. Take ID with you."
            ),
        },
        DocumentType.NOTICE_OF_RISK: {
            "title": "Notice of Child Abuse, Family Violence or Risk",
            "form_number": "Form 4",
            "description": (
                "This form MUST be filed with any parenting application "
                "if there are allegations or concerns about child abuse, "
                "family violence, or risk to a child."
            ),
            "when_required": [
                "Any allegation of child abuse (physical, sexual, emotional, neglect)",
                "Family violence (past or present)",
                "Drug or alcohol abuse affecting children",
                "Mental health issues affecting parenting capacity",
                "Any risk of harm to children",
            ],
            "importance": (
                "The Notice of Risk helps the court protect children. "
                "If you have concerns, disclose them. The court takes "
                "non-disclosure seriously. It is better to disclose "
                "concerns and have them investigated than to hide them."
            ),
        },
        DocumentType.CONSENT_ORDERS: {
            "title": "Application for Consent Orders",
            "form_number": "Form 11",
            "description": (
                "Used when both parties have reached an agreement and "
                "want the court to make orders by consent."
            ),
            "process": [
                "1. Negotiate agreement with the other party",
                "2. Draft the proposed orders (Minute of Consent Orders)",
                "3. Both parties sign the Application",
                "4. File at court with the filing fee",
                "5. A Registrar reviews and may approve without a hearing",
            ],
            "benefits": [
                "Much cheaper than going to trial",
                "Faster - often finalised within weeks",
                "Less stressful than court proceedings",
                "You control the outcome",
            ],
            "tips": [
                "Be very specific in the orders",
                "Include provisions for special days (birthdays, holidays)",
                "Consider how handovers will work",
                "Include a dispute resolution clause",
            ],
        },
        DocumentType.FINANCIAL_STATEMENT: {
            "title": "Financial Statement",
            "form_number": "Form 13",
            "description": (
                "Required in property matters. A detailed statement of "
                "your financial situation including income, assets, debts, "
                "and expenses."
            ),
            "sections": [
                "Personal details",
                "Income (from all sources)",
                "Assets (property, vehicles, bank accounts, super, shares)",
                "Liabilities (mortgages, loans, credit cards)",
                "Financial resources (trusts, inheritances expected)",
                "Weekly expenses",
            ],
            "duty_of_disclosure": (
                "You have a DUTY to provide full and frank disclosure. "
                "Hiding assets or income can result in orders being set "
                "aside and costs penalties."
            ),
        },
    }

    def get_guidance(self, doc_type: DocumentType) -> Optional[dict]:
        """Get guidance for a specific document type."""
        return self.DOCUMENT_GUIDANCE.get(doc_type)

    def get_all_documents(self) -> list[DocumentType]:
        """Get list of all document types with guidance."""
        return list(self.DOCUMENT_GUIDANCE.keys())

    def explain_document(self, doc_type: DocumentType) -> str:
        """
        Get a VoiceOver-friendly explanation of a document.

        Returns a clear, spoken explanation suitable for audio output.
        """
        guidance = self.get_guidance(doc_type)
        if not guidance:
            return f"I don't have guidance for {doc_type.value}."

        parts = [
            f"About the {guidance['title']}.",
            guidance["description"],
        ]

        if "key_sections" in guidance:
            parts.append(
                "Key sections include: " + ", ".join(guidance["key_sections"][:3]) + "."
            )

        if "common_mistakes" in guidance:
            parts.append(
                "Common mistakes to avoid: " + guidance["common_mistakes"][0] + "."
            )

        if "deadline_warning" in guidance:
            parts.append(guidance["deadline_warning"])

        return " ".join(parts)


# =============================================================================
# EMOTIONAL SUPPORT HANDLER
# =============================================================================


class EmotionalSupportHandler:
    """
    Provides empathetic responses and emotional support.

    Family law matters are incredibly stressful and often traumatic.
    This handler helps detect emotional distress and provide
    appropriate support and resources.
    """

    DISTRESS_INDICATORS = {
        EmotionalState.ANXIOUS: [
            "worried",
            "anxious",
            "nervous",
            "scared",
            "panic",
            "can't sleep",
            "stressed",
            "overwhelmed",
            "terrified",
        ],
        EmotionalState.ANGRY: [
            "furious",
            "angry",
            "rage",
            "hate",
            "unfair",
            "corrupt",
            "biased",
            "rigged",
        ],
        EmotionalState.HOPELESS: [
            "hopeless",
            "give up",
            "no point",
            "lost cause",
            "never win",
            "what's the point",
            "defeated",
        ],
        EmotionalState.OVERWHELMED: [
            "too much",
            "can't cope",
            "overwhelmed",
            "drowning",
            "impossible",
            "don't understand",
            "confusing",
        ],
        EmotionalState.DISTRESSED: [
            "crying",
            "can't stop",
            "breaking down",
            "falling apart",
            "devastated",
            "destroyed",
            "ruined",
        ],
    }

    SUPPORTIVE_RESPONSES = {
        EmotionalState.ANXIOUS: (
            "I understand this is an anxious time. Family law matters "
            "are stressful for everyone. Taking things one step at a time "
            "can help. Would you like me to break down the next steps "
            "into smaller, manageable pieces?"
        ),
        EmotionalState.ANGRY: (
            "I hear your frustration. The family court system can feel "
            "overwhelming and sometimes unfair. Your feelings are valid. "
            "Let's focus on what you can control - preparing your case "
            "as well as possible."
        ),
        EmotionalState.HOPELESS: (
            "I'm sorry you're feeling this way. Family law matters can "
            "seem insurmountable, but many people get through them. "
            "Small steps add up. Would you like to talk about what "
            "support is available?"
        ),
        EmotionalState.OVERWHELMED: (
            "This is a lot to deal with. You don't have to do everything "
            "at once. Let's break this down into smaller steps. What's "
            "the most immediate thing that needs attention?"
        ),
        EmotionalState.DISTRESSED: (
            "I can hear you're going through a really difficult time. "
            "Your wellbeing matters. Please consider reaching out to "
            "a counsellor. Beyond Blue (1300 22 4636) offers free support. "
            "I'm here to help when you're ready."
        ),
    }

    SELF_CARE_REMINDERS = [
        "Remember to take breaks. This is a marathon, not a sprint.",
        "Have you eaten today? Basic self-care matters.",
        "Consider talking to a counsellor. Family law is emotionally taxing.",
        "You're doing the best you can in a difficult situation.",
        "It's okay to ask for help. You don't have to do this alone.",
        "Try to get some sleep. Things often seem clearer after rest.",
        "Physical exercise can help manage stress. Even a short walk helps.",
    ]

    def detect_emotional_state(self, message: str) -> Optional[EmotionalState]:
        """Detect emotional state from user message."""
        message_lower = message.lower()

        for state, indicators in self.DISTRESS_INDICATORS.items():
            if any(ind in message_lower for ind in indicators):
                return state

        return None

    def get_supportive_response(self, state: EmotionalState) -> str:
        """Get an appropriate supportive response."""
        return self.SUPPORTIVE_RESPONSES.get(state, "")

    def get_self_care_reminder(self) -> str:
        """Get a random self-care reminder."""
        import random

        return random.choice(self.SELF_CARE_REMINDERS)


# =============================================================================
# MAIN CHATBOT CLASS
# =============================================================================


class FamilyLawBot:
    """
    Australian Family Law Legal Aid Chatbot.

    A comprehensive, accessible chatbot designed to help Australians
    navigate the Family Court system. Built with empathy and designed
    for accessibility, including VoiceOver compatibility.

    IMPORTANT: This chatbot provides general information only, not
    legal advice. Users should always consult a qualified family lawyer.
    """

    def __init__(
        self,
        llm_router: Optional[Any] = None,
        memory: Optional[Any] = None,
        voice_output: bool = True,
    ):
        """
        Initialize the Family Law Bot.

        Args:
            llm_router: Optional LLMRouter for generating responses
            memory: Optional memory system for context continuity
            voice_output: Whether to format output for VoiceOver
        """
        self.llm_router = llm_router
        self.memory = memory
        self.voice_output = voice_output

        # Initialize components
        self.knowledge_base = LegalKnowledgeBase()
        self.case_manager = CaseManager()
        self.document_helper = DocumentHelper()
        self.safety_monitor = SafetyMonitor()
        self.emotional_handler = EmotionalSupportHandler()

        # Current session state
        self.current_case: Optional[FamilyLawCase] = None
        self.conversation_history: list[dict] = []
        self.disclaimer_shown = False

        logger.info("FamilyLawBot initialized")

    def start_session(self) -> str:
        """Start a new chat session with welcome message and disclaimer."""
        self.disclaimer_shown = True

        welcome = """
Welcome to the Australian Family Law Legal Aid Chatbot.

I'm here to help you understand family law and navigate the court system.
I can provide information about:

• Parenting orders and arrangements
• Family Dispute Resolution (FDR)
• Filing court documents
• Property settlement
• What to expect at court
• Your rights and responsibilities

Before we begin, please read this important disclaimer:
"""

        return (
            welcome
            + MAIN_DISCLAIMER
            + """

How can I help you today?

(Type 'help' for a list of topics, or describe your situation)
"""
        )

    def process_message(self, message: str) -> str:
        """
        Process a user message and generate a response.

        Args:
            message: The user's input message

        Returns:
            The bot's response, formatted for accessibility
        """
        # Add to conversation history
        self.conversation_history.append(
            {
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Safety check first - highest priority
        safety_result = self.safety_monitor.analyze_message(message)

        if safety_result["requires_intervention"]:
            response = self._handle_safety_intervention(safety_result)
            self._log_response(response)
            return response

        # Check for emotional distress
        emotional_state = self.emotional_handler.detect_emotional_state(message)
        emotional_prefix = ""
        if emotional_state:
            emotional_prefix = (
                self.emotional_handler.get_supportive_response(emotional_state) + "\n\n"
            )

        # Handle commands and queries
        message_lower = message.lower().strip()

        if message_lower == "help":
            response = self._get_help_menu()
        elif message_lower == "disclaimer":
            response = MAIN_DISCLAIMER
        elif message_lower == "safety" or message_lower == "emergency":
            response = self._get_emergency_resources()
        elif message_lower == "my case" or message_lower == "case status":
            response = self._get_case_status()
        elif message_lower == "deadlines":
            response = self._get_deadlines()
        elif message_lower.startswith("new case"):
            response = self._start_new_case(message)
        elif any(x in message_lower for x in ["fdr", "mediation", "60i"]):
            response = self._explain_fdr()
        elif any(x in message_lower for x in ["consent order", "agreement"]):
            response = self._explain_consent_orders()
        elif any(x in message_lower for x in ["contravention", "breach", "breached"]):
            response = self._explain_contravention()
        elif any(x in message_lower for x in ["recovery order", "taken", "abducted"]):
            response = self._explain_recovery_orders()
        elif any(x in message_lower for x in ["property", "assets", "super"]):
            response = self._explain_property()
        elif any(x in message_lower for x in ["icl", "children's lawyer"]):
            response = self._explain_icl()
        elif any(x in message_lower for x in ["file", "filing", "lodge"]):
            response = self._explain_filing()
        elif any(x in message_lower for x in ["affidavit"]):
            response = self._explain_affidavit()
        elif any(x in message_lower for x in ["notice of risk", "form 4"]):
            response = self._explain_notice_of_risk()
        else:
            # Use RAG to find relevant information
            response = self._generate_rag_response(message)

        # Add safety prefix if there are moderate concerns
        if safety_result.get("response_prefix"):
            response = safety_result["response_prefix"] + response

        # Add emotional support prefix
        if emotional_prefix:
            response = emotional_prefix + response

        # Always end with reminder about legal advice
        response += (
            "\n\n_Remember: This is general information only. "
            "For advice specific to your situation, please consult a lawyer._"
        )

        self._log_response(response)
        return response

    def _log_response(self, response: str):
        """Log the response to conversation history."""
        self.conversation_history.append(
            {
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _get_help_menu(self) -> str:
        """Get the help menu."""
        return """
FAMILY LAW BOT - HELP MENU

TOPICS I CAN HELP WITH:

1. PARENTING MATTERS
   - "What is Family Dispute Resolution?" (or "FDR")
   - "How do parenting orders work?"
   - "What is an ICL?" (Independent Children's Lawyer)

2. FILING DOCUMENTS
   - "How do I file an application?"
   - "What is an affidavit?"
   - "Tell me about the Notice of Risk"

3. COURT PROCESS
   - "What happens at court?"
   - "What is an interim hearing?"
   - "How long does this take?"

4. AGREEMENTS
   - "How do consent orders work?"
   - "What is a parenting plan?"

5. ENFORCEMENT
   - "The other party breached the order" (contravention)
   - "My child was taken" (recovery orders)

6. PROPERTY
   - "How does property settlement work?"
   - "What about superannuation?"

7. CASE MANAGEMENT
   - "new case" - Start tracking a new matter
   - "my case" - See your case status
   - "deadlines" - View upcoming deadlines

8. SAFETY
   - "safety" or "emergency" - Get emergency contacts

Type any topic or describe your situation.
"""

    def _get_emergency_resources(self) -> str:
        """Get emergency resources."""
        return """
EMERGENCY RESOURCES

IF YOU ARE IN IMMEDIATE DANGER:
Call 000 (Triple Zero)

FAMILY VIOLENCE SUPPORT:
• 1800RESPECT: 1800 737 732 (24/7)
• MensLine Australia: 1300 78 99 78
• Kids Helpline: 1800 55 1800

MENTAL HEALTH CRISIS:
• Lifeline: 13 11 14 (24/7)
• Beyond Blue: 1300 22 4636
• Suicide Call Back: 1300 659 467

LEGAL HELP:
• Legal Aid: 1300 888 529
• Family Relationship Advice Line: 1800 050 321

STATE DOMESTIC VIOLENCE SERVICES:
• NSW: 1800 656 463
• VIC: 1800 015 188
• QLD: 1800 811 811
• WA: 1800 007 339
• SA: 1800 800 098
• TAS: 1800 608 122
• NT: 1800 093 081
• ACT: (02) 6280 0900

You are not alone. Help is available.
"""

    def _handle_safety_intervention(self, safety_result: dict) -> str:
        """Handle a safety intervention."""
        response = safety_result["response_prefix"]

        if safety_result["resources"]:
            response += "\n\nIMPORTANT CONTACTS:\n"
            for resource in safety_result["resources"]:
                response += f"• {resource}\n"

        return response

    def _get_case_status(self) -> str:
        """Get the current case status."""
        if self.current_case:
            return self.current_case.to_summary()

        active_cases = self.case_manager.get_active_cases()
        if active_cases:
            response = f"You have {len(active_cases)} active case(s):\n\n"
            for case in active_cases:
                response += case.to_summary() + "\n\n"
            return response

        return (
            "You don't have any active cases being tracked.\n"
            "Type 'new case' to start tracking a new matter."
        )

    def _get_deadlines(self) -> str:
        """Get upcoming deadlines."""
        upcoming = self.case_manager.get_upcoming_deadlines(30)
        overdue = self.case_manager.get_overdue_deadlines()

        response = ""

        if overdue:
            response += "⚠️ OVERDUE DEADLINES:\n"
            for _case, deadline in overdue:
                response += f"• {deadline.to_voice()}\n"
            response += "\n"

        if upcoming:
            response += "UPCOMING DEADLINES (next 30 days):\n"
            for _case, deadline in upcoming:
                response += f"• {deadline.to_voice()}\n"
        elif not overdue:
            response = "No upcoming deadlines in the next 30 days."

        return response

    def _start_new_case(self, message: str) -> str:
        """Start tracking a new case."""
        # Determine matter type from message
        message_lower = message.lower()
        if "property" in message_lower and "parenting" in message_lower:
            matter_type = "both"
        elif "property" in message_lower:
            matter_type = "property"
        else:
            matter_type = "parenting"

        case = self.case_manager.create_case(matter_type)
        self.current_case = case

        return f"""
New case created and tracking started.

CASE ID: {case.case_id}
MATTER TYPE: {matter_type}
PHASE: Initial Consultation

Next steps:
1. Have you attempted Family Dispute Resolution (FDR)?
2. Do you have a Section 60I certificate?
3. Are there any family violence or child safety concerns?

Tell me more about your situation, and I'll help you understand
your options and what steps to take.
"""

    def _explain_fdr(self) -> str:
        """Explain Family Dispute Resolution."""
        fdr_info = self.knowledge_base.knowledge.get("fdr", {})

        return f"""
FAMILY DISPUTE RESOLUTION (FDR)

{fdr_info.get('description', '')}

WHERE CAN I DO FDR?
{chr(10).join('• ' + x for x in fdr_info.get('where_to_go', []))}

SECTION 60I CERTIFICATES:
A Section 60I certificate is issued by an FDR practitioner. Types include:
{chr(10).join('• ' + x for x in fdr_info.get('s60i_certificates', {}).get('types', []))}

EXEMPTIONS:
{fdr_info.get('s60i_certificates', {}).get('exemptions', '')}

COST:
Family Relationship Centres offer free or low-cost FDR.
Private practitioners charge fees (often $150-$400 per session).

IMPORTANT: FDR is usually REQUIRED before filing parenting applications.
Call the Family Relationship Advice Line on 1800 050 321 for help
finding an FDR service near you.
"""

    def _explain_consent_orders(self) -> str:
        """Explain consent orders."""
        guidance = self.document_helper.get_guidance(DocumentType.CONSENT_ORDERS)

        return f"""
CONSENT ORDERS

{guidance['description']}

PROCESS:
{chr(10).join(guidance['process'])}

BENEFITS:
{chr(10).join('• ' + x for x in guidance['benefits'])}

TIPS:
{chr(10).join('• ' + x for x in guidance['tips'])}

FILING FEE: Approximately $180 (fee reductions available)

HOW TO FILE:
1. Use the Commonwealth Courts Portal: comcourts.gov.au
2. File Application for Consent Orders (Form 11)
3. Attach Minute of Consent Orders with exact wording
4. Both parties must sign

IMPORTANT: Consent orders have the same legal force as orders
made after a trial. Make sure you're happy with them before signing.
"""

    def _explain_contravention(self) -> str:
        """Explain contravention applications."""
        info = self.knowledge_base.knowledge.get("contravention", {})

        return f"""
CONTRAVENTION APPLICATIONS

{info.get('description', '')}

WHAT IS A REASONABLE EXCUSE?
{info.get('reasonable_excuse', '')}

POSSIBLE PENALTIES:
{chr(10).join('• ' + x for x in info.get('penalties', []))}

BEFORE FILING:
{info.get('before_filing', '')}

IMPORTANT CONSIDERATIONS:
1. Document every breach (dates, times, what happened)
2. Keep communication records (texts, emails)
3. Try to resolve issues directly first if safe
4. Consider if the breach is serious enough to warrant court action
5. Seek legal advice - these applications are complex

COST: Filing fee approximately $395 (fee reductions available)

Remember: The court prefers parties to work things out. Minor
breaches may not succeed. Serious or repeated breaches are
treated more seriously.
"""

    def _explain_recovery_orders(self) -> str:
        """Explain recovery orders."""
        info = self.knowledge_base.knowledge.get("recovery_orders", {})

        return f"""
RECOVERY ORDERS (URGENT)

{info.get('description', '')}

WHEN TO APPLY:
{chr(10).join('• ' + x for x in info.get('when_to_apply', []))}

PROCESS:
{info.get('process', '')}

IF YOUR CHILD HAS BEEN TAKEN:

1. IMMEDIATE STEPS:
   • If in immediate danger, call 000
   • Contact a lawyer urgently (Legal Aid: 1300 888 529)
   • Gather evidence (texts, photos, documents)

2. URGENT COURT APPLICATION:
   • Recovery orders can be heard urgently (sometimes same day)
   • You may not need to give notice to the other party
   • The court can order police to recover the child

3. IF TAKEN OVERSEAS:
   • This may be international child abduction
   • Contact the Attorney-General's Department Central Authority
   • Phone: (02) 6141 6666
   • Time is critical - act immediately

IMPORTANT: Recovery orders are serious. If you're considering
taking your child without proper authority, understand this could
result in recovery orders against you and damage your case.
"""

    def _explain_property(self) -> str:
        """Explain property settlement."""
        info = self.knowledge_base.knowledge.get("property", {})

        return f"""
PROPERTY SETTLEMENT

{info.get('description', '')}

THE FOUR-STEP PROCESS:
{chr(10).join(info.get('four_step_process', []))}

TIME LIMITS:
{info.get('time_limits', '')}

SUPERANNUATION:
{info.get('superannuation', '')}

KEY POINTS:

1. ASSET POOL:
   • Includes property, vehicles, bank accounts, shares
   • Also includes debts (mortgages, loans, credit cards)
   • Superannuation is treated as property

2. CONTRIBUTIONS:
   • Financial (income, savings, inheritances)
   • Non-financial (renovations, business work)
   • Homemaker/parent contributions (valued equally)

3. FUTURE NEEDS:
   • Age and health
   • Income and earning capacity
   • Who has care of children
   • Length of relationship

4. JUST AND EQUITABLE:
   • The final check - is the overall result fair?

NEGOTIATION:
Most property matters settle without trial. Options include:
• Direct negotiation
• Lawyer-assisted negotiation
• Mediation
• Collaborative law

IMPORTANT: Get a lawyer to review any property settlement
before you agree. These decisions are final.
"""

    def _explain_icl(self) -> str:
        """Explain Independent Children's Lawyer."""
        info = self.knowledge_base.knowledge.get("icl", {})

        return f"""
INDEPENDENT CHILDREN'S LAWYER (ICL)

{info.get('description', '')}

WHEN AN ICL MAY BE APPOINTED:
{chr(10).join('• ' + x for x in info.get('when_appointed', []))}

ROLE OF THE ICL:
{info.get('role', '')}

KEY POINTS:

1. The ICL represents the CHILDREN'S BEST INTERESTS
   (Not what the children want, but what's best for them)

2. The ICL gathers evidence:
   • Speaks with both parents
   • May speak with children (age-appropriate)
   • Reviews documents and reports
   • May arrange a family report

3. The ICL makes submissions to the court

4. COST:
   • Usually Legal Aid funded (no cost to you)
   • In some cases, costs may be ordered against parties

5. COMMUNICATION:
   • You can and should communicate with the ICL
   • Provide relevant documents
   • Be honest - they're there for the children

IMPORTANT: The ICL is not on anyone's "side". Their job is to
help the court determine what's best for your children.
"""

    def _explain_filing(self) -> str:
        """Explain how to file documents."""
        return """
FILING COURT DOCUMENTS

HOW TO FILE:

1. ONLINE (RECOMMENDED):
   • Go to comcourts.gov.au
   • Create an account if you don't have one
   • Select 'File a document'
   • Follow the prompts
   • Pay the filing fee online

2. IN PERSON:
   • Go to your local Family Court registry
   • Bring completed forms and copies
   • Pay at the counter

3. BY POST (not recommended - slow):
   • Mail completed forms with filing fee
   • Include return address

FILING FEES (2024, approximate):
• Initiating Application: $395
• Response: No fee
• Consent Orders: $180
• Contravention: $395
• Affidavit: No fee

FEE REDUCTIONS:
If you have a Health Care Card, pension card, or financial
hardship, you may be eligible for reduced or waived fees.
Ask about fee reduction when filing.

REQUIRED DOCUMENTS FOR PARENTING:
• Initiating Application (Form 1)
• Section 60I certificate (or exemption)
• Notice of Risk (Form 4) if any concerns
• Affidavit (your evidence)

AFTER FILING:
• Keep copies of everything
• You must serve documents on the other party
• The Initiating Application must be personally served

IMPORTANT: Check the court's website for current fees and
forms. Forms are updated regularly.
"""

    def _explain_affidavit(self) -> str:
        """Explain affidavits."""
        return self.document_helper.explain_document(DocumentType.AFFIDAVIT)

    def _explain_notice_of_risk(self) -> str:
        """Explain the Notice of Risk."""
        guidance = self.document_helper.get_guidance(DocumentType.NOTICE_OF_RISK)

        return f"""
NOTICE OF CHILD ABUSE, FAMILY VIOLENCE OR RISK (Form 4)

{guidance['description']}

WHEN IT'S REQUIRED:
{chr(10).join('• ' + x for x in guidance['when_required'])}

{guidance['importance']}

WHAT TO INCLUDE:
• All allegations of abuse or violence
• Past and present concerns
• Any protective orders (AVOs, DVOs, intervention orders)
• Child protection involvement
• Police involvement
• Any other risk factors

IMPORTANT POINTS:

1. MUST BE FILED if you have concerns
   Filing an Initiating Application without a required Notice
   of Risk is a breach of the Rules.

2. DISCLOSE EVERYTHING
   The court needs to know about any risks to children.
   Non-disclosure is taken very seriously.

3. THIS IS NOT EVIDENCE
   The Notice of Risk alerts the court to concerns. You still
   need to provide evidence in your Affidavit.

4. BOTH PARTIES FILE
   If you receive an application, you also need to file a
   Notice of Risk if you have any concerns.

5. CONFIDENTIALITY
   The Notice is filed with the court and provided to the
   other party. Consider safety implications.

If you have concerns about child safety or family violence,
please disclose them. The court's priority is protecting children.
"""

    def _generate_rag_response(self, query: str) -> str:
        """Generate a response using RAG (Retrieval-Augmented Generation)."""
        # Search knowledge base
        results = self.knowledge_base.search(query)

        if not results:
            return self._get_fallback_response(query)

        # Build context from results
        context_parts = []
        for result in results[:3]:  # Top 3 results
            for match in result.get("matches", [])[:2]:  # Top 2 matches per result
                if isinstance(match, str):
                    context_parts.append(match)

        if not context_parts:
            return self._get_fallback_response(query)

        # Format response
        response = "Based on my knowledge base:\n\n"
        for i, part in enumerate(context_parts, 1):
            response += f"{i}. {part}\n\n"

        response += (
            "\nFor more detailed information on any of these points, "
            "just ask a specific question."
        )

        return response

    def _get_fallback_response(self, query: str) -> str:
        """Generate a fallback response when no specific information is found."""
        return f"""
I don't have specific information about "{query}" in my knowledge base.

However, I can help with:
• Parenting matters and orders
• Family Dispute Resolution (FDR)
• Court procedures and documents
• Property settlement
• Consent orders
• Enforcement (contravention)
• Recovery orders

For questions outside these areas, I recommend:
• Legal Aid: 1300 888 529
• Family Relationship Advice Line: 1800 050 321
• A consultation with a family lawyer

Would you like information on any of the topics I mentioned?
"""

    def get_voice_summary(self) -> str:
        """Get a VoiceOver-friendly session summary."""
        parts = []

        if self.current_case:
            parts.append(self.current_case.to_summary())

        # Safety summary
        parts.append(self.safety_monitor.to_voice())

        # Upcoming deadlines
        upcoming = self.case_manager.get_upcoming_deadlines(7)
        if upcoming:
            parts.append(f"You have {len(upcoming)} deadlines in the next 7 days.")
            for _, deadline in upcoming[:2]:
                parts.append(deadline.to_voice())

        return " ".join(parts)


# =============================================================================
# ENTRY POINT
# =============================================================================


def main():
    """Run the Family Law Bot in interactive mode."""
    print("\n" + "=" * 70)
    print("AUSTRALIAN FAMILY LAW LEGAL AID CHATBOT")
    print("=" * 70)

    bot = FamilyLawBot(voice_output=True)

    # Show welcome and disclaimer
    print(bot.start_session())

    # Interactive loop
    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\nThank you for using the Family Law Bot.")
                print("Remember: Please seek legal advice for your specific situation.")
                print("Take care of yourself. Goodbye.")
                break

            response = bot.process_message(user_input)
            print(f"\nBot: {response}")

        except KeyboardInterrupt:
            print("\n\nSession ended. Take care.")
            break
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            print("\nI'm sorry, I encountered an error. Please try again.")


if __name__ == "__main__":
    main()
