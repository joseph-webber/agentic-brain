#!/usr/bin/env python3
"""
Family Law Chatbot - Multi-Stakeholder Access System
=====================================================

Different users access this chatbot with different needs and permissions:

COURT USERS
-----------
- Judges/Registrars: Case summaries, procedural queries
- Court staff: Filing assistance, deadline tracking
- Registry: Document processing guidance

LEGAL PROFESSIONALS
-------------------
- Applicant's lawyer: Full case access, drafting assistance
- Respondent's lawyer: Full case access, response preparation
- Independent Children's Lawyer (ICL): Child-focused queries
- Barrister: Trial preparation, legal research
- Paralegal: Document preparation, deadline tracking

PARTIES TO PROCEEDINGS
----------------------
- Applicant: Their case, their documents, their deadlines
- Applicant's family: Support role, limited access
- Respondent: Their case, their documents, their deadlines
- Respondent's family: Support role, limited access

SUPPORT SERVICES
----------------
- Family consultant: Child welfare assessment support
- Social worker: Risk assessment, safety planning
- Family dispute resolution practitioner: Mediation support
- Domestic violence support worker: Safety planning

CHILDREN (age-appropriate)
--------------------------
- Older children (14+): Understanding the process
- Through support worker: Explaining what's happening

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# USER ROLES AND PERMISSIONS
# =============================================================================


class UserRole(Enum):
    """All possible user roles in the family law system."""

    # Court users
    JUDGE = "judge"
    REGISTRAR = "registrar"
    COURT_STAFF = "court_staff"
    REGISTRY = "registry"

    # Legal professionals
    APPLICANT_LAWYER = "applicant_lawyer"
    RESPONDENT_LAWYER = "respondent_lawyer"
    ICL = "independent_children_lawyer"
    BARRISTER = "barrister"
    PARALEGAL = "paralegal"
    LAW_CLERK = "law_clerk"

    # Parties
    APPLICANT = "applicant"
    RESPONDENT = "respondent"
    APPLICANT_SUPPORT = "applicant_support"  # Family/friend supporting
    RESPONDENT_SUPPORT = "respondent_support"

    # Support services
    FAMILY_CONSULTANT = "family_consultant"
    SOCIAL_WORKER = "social_worker"
    FDR_PRACTITIONER = "fdr_practitioner"
    DV_SUPPORT_WORKER = "dv_support_worker"
    CHILD_SUPPORT_WORKER = "child_support_worker"

    # Children (through appropriate channels)
    CHILD_DIRECT = "child_direct"  # Older child accessing directly
    CHILD_SUPPORTED = "child_supported"  # Child with support worker

    # System
    ADMIN = "admin"
    ANONYMOUS = "anonymous"  # General public, no case access


class Permission(Enum):
    """Granular permissions for access control."""

    # Case access
    VIEW_OWN_CASE = auto()
    VIEW_OPPOSING_CASE = auto()  # Lawyers see both sides
    VIEW_ALL_CASES = auto()  # Court/admin
    EDIT_OWN_CASE = auto()

    # Documents
    VIEW_FILED_DOCUMENTS = auto()
    VIEW_DRAFT_DOCUMENTS = auto()
    CREATE_DOCUMENTS = auto()
    FILE_DOCUMENTS = auto()

    # Chat features
    GENERAL_QUERIES = auto()
    LEGAL_RESEARCH = auto()
    DRAFTING_ASSISTANCE = auto()
    CASE_STRATEGY = auto()  # Lawyers only

    # Sensitive information
    VIEW_RISK_ASSESSMENT = auto()
    VIEW_DV_DETAILS = auto()
    VIEW_CHILD_DETAILS = auto()

    # Support features
    EMOTIONAL_SUPPORT = auto()
    SAFETY_PLANNING = auto()
    CRISIS_INTERVENTION = auto()

    # Admin
    MANAGE_USERS = auto()
    AUDIT_ACCESS = auto()
    SYSTEM_CONFIG = auto()


# Permission sets for each role
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    # Court users - broad view access
    UserRole.JUDGE: {
        Permission.VIEW_ALL_CASES,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_RISK_ASSESSMENT,
        Permission.VIEW_CHILD_DETAILS,
        Permission.LEGAL_RESEARCH,
        Permission.AUDIT_ACCESS,
    },
    UserRole.REGISTRAR: {
        Permission.VIEW_ALL_CASES,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_RISK_ASSESSMENT,
        Permission.LEGAL_RESEARCH,
        Permission.FILE_DOCUMENTS,
    },
    UserRole.COURT_STAFF: {
        Permission.VIEW_ALL_CASES,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.GENERAL_QUERIES,
    },
    UserRole.REGISTRY: {
        Permission.VIEW_ALL_CASES,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.FILE_DOCUMENTS,
        Permission.GENERAL_QUERIES,
    },
    # Legal professionals - their client's case + opposing
    UserRole.APPLICANT_LAWYER: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_OPPOSING_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_DRAFT_DOCUMENTS,
        Permission.CREATE_DOCUMENTS,
        Permission.FILE_DOCUMENTS,
        Permission.LEGAL_RESEARCH,
        Permission.DRAFTING_ASSISTANCE,
        Permission.CASE_STRATEGY,
        Permission.VIEW_RISK_ASSESSMENT,
    },
    UserRole.RESPONDENT_LAWYER: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_OPPOSING_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_DRAFT_DOCUMENTS,
        Permission.CREATE_DOCUMENTS,
        Permission.FILE_DOCUMENTS,
        Permission.LEGAL_RESEARCH,
        Permission.DRAFTING_ASSISTANCE,
        Permission.CASE_STRATEGY,
        Permission.VIEW_RISK_ASSESSMENT,
    },
    UserRole.ICL: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_OPPOSING_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_DRAFT_DOCUMENTS,
        Permission.CREATE_DOCUMENTS,
        Permission.LEGAL_RESEARCH,
        Permission.DRAFTING_ASSISTANCE,
        Permission.VIEW_CHILD_DETAILS,
        Permission.VIEW_RISK_ASSESSMENT,
    },
    UserRole.BARRISTER: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.LEGAL_RESEARCH,
        Permission.DRAFTING_ASSISTANCE,
        Permission.CASE_STRATEGY,
    },
    UserRole.PARALEGAL: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_DRAFT_DOCUMENTS,
        Permission.CREATE_DOCUMENTS,
        Permission.GENERAL_QUERIES,
        Permission.DRAFTING_ASSISTANCE,
    },
    UserRole.LAW_CLERK: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.GENERAL_QUERIES,
        Permission.LEGAL_RESEARCH,
    },
    # Parties - their own case only
    UserRole.APPLICANT: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_DRAFT_DOCUMENTS,
        Permission.CREATE_DOCUMENTS,
        Permission.GENERAL_QUERIES,
        Permission.DRAFTING_ASSISTANCE,
        Permission.EMOTIONAL_SUPPORT,
        Permission.SAFETY_PLANNING,
        Permission.CRISIS_INTERVENTION,
    },
    UserRole.RESPONDENT: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_DRAFT_DOCUMENTS,
        Permission.CREATE_DOCUMENTS,
        Permission.GENERAL_QUERIES,
        Permission.DRAFTING_ASSISTANCE,
        Permission.EMOTIONAL_SUPPORT,
        Permission.SAFETY_PLANNING,
        Permission.CRISIS_INTERVENTION,
    },
    UserRole.APPLICANT_SUPPORT: {
        Permission.GENERAL_QUERIES,
        Permission.EMOTIONAL_SUPPORT,
    },
    UserRole.RESPONDENT_SUPPORT: {
        Permission.GENERAL_QUERIES,
        Permission.EMOTIONAL_SUPPORT,
    },
    # Support services
    UserRole.FAMILY_CONSULTANT: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_FILED_DOCUMENTS,
        Permission.VIEW_CHILD_DETAILS,
        Permission.VIEW_RISK_ASSESSMENT,
        Permission.GENERAL_QUERIES,
    },
    UserRole.SOCIAL_WORKER: {
        Permission.VIEW_OWN_CASE,
        Permission.VIEW_RISK_ASSESSMENT,
        Permission.VIEW_DV_DETAILS,
        Permission.SAFETY_PLANNING,
        Permission.CRISIS_INTERVENTION,
        Permission.EMOTIONAL_SUPPORT,
    },
    UserRole.FDR_PRACTITIONER: {
        Permission.GENERAL_QUERIES,
        Permission.LEGAL_RESEARCH,
    },
    UserRole.DV_SUPPORT_WORKER: {
        Permission.VIEW_RISK_ASSESSMENT,
        Permission.VIEW_DV_DETAILS,
        Permission.SAFETY_PLANNING,
        Permission.CRISIS_INTERVENTION,
        Permission.EMOTIONAL_SUPPORT,
        Permission.GENERAL_QUERIES,
    },
    UserRole.CHILD_SUPPORT_WORKER: {
        Permission.VIEW_CHILD_DETAILS,
        Permission.EMOTIONAL_SUPPORT,
        Permission.GENERAL_QUERIES,
    },
    # Children
    UserRole.CHILD_DIRECT: {
        Permission.GENERAL_QUERIES,
        Permission.EMOTIONAL_SUPPORT,
    },
    UserRole.CHILD_SUPPORTED: {
        Permission.GENERAL_QUERIES,
        Permission.EMOTIONAL_SUPPORT,
    },
    # System
    UserRole.ADMIN: {p for p in Permission},  # All permissions
    UserRole.ANONYMOUS: {
        Permission.GENERAL_QUERIES,
    },
}


@dataclass
class User:
    """A user of the family law chatbot system."""

    user_id: str
    role: UserRole
    name: str
    email: Optional[str] = None
    organization: Optional[str] = None  # Law firm, court, support service

    # Case associations
    case_ids: List[str] = field(default_factory=list)
    party_side: Optional[str] = None  # "applicant" or "respondent"

    # Session
    session_id: Optional[str] = None
    last_active: datetime = field(default_factory=datetime.now)

    # Preferences
    accessibility_needs: Dict[str, Any] = field(default_factory=dict)
    language: str = "en-AU"

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in ROLE_PERMISSIONS.get(self.role, set())

    def can_access_case(self, case_id: str, case_side: str) -> bool:
        """Check if user can access a specific case."""
        # Admin and court can access all
        if self.has_permission(Permission.VIEW_ALL_CASES):
            return True

        # Own case access
        if case_id in self.case_ids:
            return True

        # Lawyers can see opposing case
        if self.has_permission(Permission.VIEW_OPPOSING_CASE):
            return True

        return False

    def get_greeting(self) -> str:
        """Get role-appropriate greeting."""
        greetings = {
            UserRole.JUDGE: f"Good day, Your Honour",
            UserRole.REGISTRAR: f"Hello Registrar {self.name}",
            UserRole.APPLICANT_LAWYER: f"Hello {self.name}, counsel for the applicant",
            UserRole.RESPONDENT_LAWYER: f"Hello {self.name}, counsel for the respondent",
            UserRole.ICL: f"Hello {self.name}, Independent Children's Lawyer",
            UserRole.APPLICANT: f"Hello {self.name}",
            UserRole.RESPONDENT: f"Hello {self.name}",
            UserRole.CHILD_DIRECT: f"Hi {self.name}",
            UserRole.DV_SUPPORT_WORKER: f"Hello {self.name}",
        }
        return greetings.get(self.role, f"Hello {self.name}")


# =============================================================================
# ROLE-SPECIFIC CHATBOT BEHAVIORS
# =============================================================================


@dataclass
class RoleConfig:
    """Configuration for how the chatbot behaves for each role."""

    role: UserRole

    # Tone and language
    formal_language: bool = True
    legal_terminology: bool = True
    simplified_language: bool = False
    child_friendly: bool = False

    # Features
    show_deadlines: bool = True
    show_documents: bool = True
    offer_drafting: bool = False
    offer_emotional_support: bool = False
    show_safety_resources: bool = False

    # Disclaimers
    show_legal_disclaimer: bool = True
    disclaimer_frequency: str = (
        "every_session"  # "every_session", "every_message", "once"
    )

    # Response style
    max_response_length: int = 500
    include_citations: bool = False
    include_next_steps: bool = True

    # Escalation
    escalate_to_human: bool = False
    escalate_threshold: str = "complex"  # "always", "complex", "never"


# Pre-configured behaviors for each role
ROLE_CONFIGS: Dict[UserRole, RoleConfig] = {
    UserRole.JUDGE: RoleConfig(
        role=UserRole.JUDGE,
        formal_language=True,
        legal_terminology=True,
        include_citations=True,
        show_legal_disclaimer=False,  # Judge knows it's not advice
        escalate_to_human=False,
    ),
    UserRole.APPLICANT_LAWYER: RoleConfig(
        role=UserRole.APPLICANT_LAWYER,
        formal_language=True,
        legal_terminology=True,
        offer_drafting=True,
        include_citations=True,
        show_legal_disclaimer=False,  # Lawyer knows
        max_response_length=1000,
    ),
    UserRole.RESPONDENT_LAWYER: RoleConfig(
        role=UserRole.RESPONDENT_LAWYER,
        formal_language=True,
        legal_terminology=True,
        offer_drafting=True,
        include_citations=True,
        show_legal_disclaimer=False,
        max_response_length=1000,
    ),
    UserRole.ICL: RoleConfig(
        role=UserRole.ICL,
        formal_language=True,
        legal_terminology=True,
        offer_drafting=True,
        include_citations=True,
        show_legal_disclaimer=False,
        max_response_length=1000,
    ),
    UserRole.PARALEGAL: RoleConfig(
        role=UserRole.PARALEGAL,
        formal_language=True,
        legal_terminology=True,
        offer_drafting=True,
        show_legal_disclaimer=True,
        disclaimer_frequency="once",
    ),
    UserRole.APPLICANT: RoleConfig(
        role=UserRole.APPLICANT,
        formal_language=False,
        legal_terminology=False,
        simplified_language=True,
        offer_emotional_support=True,
        show_safety_resources=True,
        show_legal_disclaimer=True,
        disclaimer_frequency="every_session",
        escalate_to_human=True,
        escalate_threshold="complex",
    ),
    UserRole.RESPONDENT: RoleConfig(
        role=UserRole.RESPONDENT,
        formal_language=False,
        legal_terminology=False,
        simplified_language=True,
        offer_emotional_support=True,
        show_safety_resources=True,
        show_legal_disclaimer=True,
        disclaimer_frequency="every_session",
        escalate_to_human=True,
        escalate_threshold="complex",
    ),
    UserRole.DV_SUPPORT_WORKER: RoleConfig(
        role=UserRole.DV_SUPPORT_WORKER,
        formal_language=False,
        show_safety_resources=True,
        offer_emotional_support=True,
        show_legal_disclaimer=True,
    ),
    UserRole.CHILD_DIRECT: RoleConfig(
        role=UserRole.CHILD_DIRECT,
        formal_language=False,
        legal_terminology=False,
        simplified_language=True,
        child_friendly=True,
        offer_emotional_support=True,
        show_safety_resources=True,
        show_legal_disclaimer=True,
        max_response_length=200,
        escalate_to_human=True,
        escalate_threshold="always",
    ),
    UserRole.CHILD_SUPPORTED: RoleConfig(
        role=UserRole.CHILD_SUPPORTED,
        formal_language=False,
        legal_terminology=False,
        simplified_language=True,
        child_friendly=True,
        offer_emotional_support=True,
        show_safety_resources=True,
        max_response_length=200,
    ),
    UserRole.ANONYMOUS: RoleConfig(
        role=UserRole.ANONYMOUS,
        formal_language=False,
        simplified_language=True,
        show_legal_disclaimer=True,
        disclaimer_frequency="every_message",
        show_deadlines=False,
        show_documents=False,
    ),
}


# =============================================================================
# QUERY ROUTER - Routes queries based on user role and intent
# =============================================================================


class QueryIntent(Enum):
    """Types of queries users might make."""

    # General information
    GENERAL_INFO = auto()
    PROCESS_EXPLANATION = auto()
    TERMINOLOGY = auto()

    # Case-specific
    CASE_STATUS = auto()
    DEADLINE_QUERY = auto()
    DOCUMENT_QUERY = auto()

    # Action-oriented
    DRAFTING_REQUEST = auto()
    FILING_GUIDANCE = auto()
    COURT_PREPARATION = auto()

    # Support
    EMOTIONAL_SUPPORT = auto()
    SAFETY_CONCERN = auto()
    CRISIS = auto()

    # Legal research (lawyers)
    LEGAL_RESEARCH = auto()
    CASE_LAW = auto()
    STRATEGY = auto()

    # Children
    CHILD_EXPLANATION = auto()

    # Administrative
    ACCOUNT_HELP = auto()
    ESCALATE_TO_HUMAN = auto()


class QueryRouter:
    """
    Routes queries to appropriate handlers based on user role and intent.

    Example:
        router = QueryRouter()
        handler = router.route(user, "What happens at my court date?")
        response = handler(query, context)
    """

    def __init__(self):
        self.intent_keywords = self._build_intent_keywords()

    def _build_intent_keywords(self) -> Dict[QueryIntent, List[str]]:
        """Build keyword mappings for intent detection."""
        return {
            QueryIntent.GENERAL_INFO: [
                "what is",
                "how does",
                "explain",
                "tell me about",
                "what are",
                "how do i",
                "can you explain",
            ],
            QueryIntent.PROCESS_EXPLANATION: [
                "process",
                "procedure",
                "steps",
                "how long",
                "what happens",
                "timeline",
                "stage",
            ],
            QueryIntent.TERMINOLOGY: [
                "what does",
                "meaning of",
                "define",
                "definition",
                "what's a",
                "what is a",
                "term",
            ],
            QueryIntent.CASE_STATUS: [
                "my case",
                "case status",
                "where is",
                "progress",
                "update on",
                "what's happening",
            ],
            QueryIntent.DEADLINE_QUERY: [
                "deadline",
                "due date",
                "when do i",
                "how long do i have",
                "time limit",
                "filing date",
            ],
            QueryIntent.DOCUMENT_QUERY: [
                "document",
                "form",
                "paperwork",
                "affidavit",
                "application",
                "file",
                "submit",
            ],
            QueryIntent.DRAFTING_REQUEST: [
                "draft",
                "write",
                "prepare",
                "help me write",
                "template",
                "example",
                "sample",
            ],
            QueryIntent.FILING_GUIDANCE: [
                "file",
                "lodge",
                "submit",
                "send to court",
                "how to file",
                "filing",
            ],
            QueryIntent.COURT_PREPARATION: [
                "court date",
                "hearing",
                "what to wear",
                "what to bring",
                "prepare for court",
                "courtroom",
                "judge",
            ],
            QueryIntent.EMOTIONAL_SUPPORT: [
                "scared",
                "worried",
                "anxious",
                "stressed",
                "don't know what to do",
                "overwhelmed",
                "help me",
            ],
            QueryIntent.SAFETY_CONCERN: [
                "safety",
                "scared of",
                "threatened",
                "violence",
                "hurt",
                "danger",
                "protect",
            ],
            QueryIntent.CRISIS: [
                "emergency",
                "urgent",
                "right now",
                "immediately",
                "can't cope",
                "suicidal",
                "harm",
            ],
            QueryIntent.LEGAL_RESEARCH: [
                "case law",
                "precedent",
                "section",
                "act",
                "legislation",
                "rule",
                "authority",
            ],
            QueryIntent.CHILD_EXPLANATION: [
                "tell my child",
                "explain to child",
                "kids understand",
                "children",
                "my son",
                "my daughter",
            ],
            QueryIntent.ESCALATE_TO_HUMAN: [
                "speak to someone",
                "talk to lawyer",
                "real person",
                "human",
                "call me",
                "contact",
            ],
        }

    def detect_intent(self, query: str) -> QueryIntent:
        """Detect the intent of a query."""
        query_lower = query.lower()

        # Check for crisis first (highest priority)
        if any(kw in query_lower for kw in self.intent_keywords[QueryIntent.CRISIS]):
            return QueryIntent.CRISIS

        # Check for safety concerns
        if any(
            kw in query_lower for kw in self.intent_keywords[QueryIntent.SAFETY_CONCERN]
        ):
            return QueryIntent.SAFETY_CONCERN

        # Score other intents
        scores = {}
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[intent] = score

        if scores:
            return max(scores, key=scores.get)

        return QueryIntent.GENERAL_INFO

    def route(
        self,
        user: User,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Route a query to appropriate handling.

        Returns:
            Dict with:
                - intent: Detected intent
                - allowed: Whether user can perform this query
                - handler: Suggested handler name
                - config: Role-specific configuration
                - warnings: Any warnings (e.g., "will escalate to human")
        """
        intent = self.detect_intent(query)
        config = ROLE_CONFIGS.get(user.role, ROLE_CONFIGS[UserRole.ANONYMOUS])

        # Check permissions
        allowed = self._check_permission(user, intent)

        # Determine handler
        handler = self._get_handler(intent, user.role)

        # Build warnings
        warnings = []

        if intent == QueryIntent.CRISIS:
            warnings.append("CRISIS DETECTED - Providing emergency resources")

        if config.escalate_to_human and intent in [
            QueryIntent.LEGAL_RESEARCH,
            QueryIntent.STRATEGY,
            QueryIntent.DRAFTING_REQUEST,
        ]:
            if config.escalate_threshold in ["always", "complex"]:
                warnings.append("This query will be flagged for lawyer review")

        if not allowed:
            warnings.append(
                f"User role {user.role.value} does not have permission for this query type"
            )

        return {
            "intent": intent,
            "allowed": allowed,
            "handler": handler,
            "config": config,
            "warnings": warnings,
            "user_role": user.role,
        }

    def _check_permission(self, user: User, intent: QueryIntent) -> bool:
        """Check if user has permission for this intent."""
        permission_map = {
            QueryIntent.GENERAL_INFO: Permission.GENERAL_QUERIES,
            QueryIntent.LEGAL_RESEARCH: Permission.LEGAL_RESEARCH,
            QueryIntent.DRAFTING_REQUEST: Permission.DRAFTING_ASSISTANCE,
            QueryIntent.STRATEGY: Permission.CASE_STRATEGY,
            QueryIntent.CASE_STATUS: Permission.VIEW_OWN_CASE,
            QueryIntent.DOCUMENT_QUERY: Permission.VIEW_FILED_DOCUMENTS,
            QueryIntent.EMOTIONAL_SUPPORT: Permission.EMOTIONAL_SUPPORT,
            QueryIntent.SAFETY_CONCERN: Permission.SAFETY_PLANNING,
            QueryIntent.CRISIS: Permission.CRISIS_INTERVENTION,
        }

        required = permission_map.get(intent, Permission.GENERAL_QUERIES)
        return user.has_permission(required)

    def _get_handler(self, intent: QueryIntent, role: UserRole) -> str:
        """Get the appropriate handler name for this intent."""
        handlers = {
            QueryIntent.CRISIS: "handle_crisis",
            QueryIntent.SAFETY_CONCERN: "handle_safety",
            QueryIntent.EMOTIONAL_SUPPORT: "handle_emotional_support",
            QueryIntent.DRAFTING_REQUEST: "handle_drafting",
            QueryIntent.LEGAL_RESEARCH: "handle_legal_research",
            QueryIntent.CASE_STATUS: "handle_case_status",
            QueryIntent.DEADLINE_QUERY: "handle_deadline",
            QueryIntent.DOCUMENT_QUERY: "handle_document",
            QueryIntent.COURT_PREPARATION: "handle_court_prep",
            QueryIntent.CHILD_EXPLANATION: "handle_child_explanation",
            QueryIntent.ESCALATE_TO_HUMAN: "handle_escalation",
        }
        return handlers.get(intent, "handle_general_query")


# =============================================================================
# RESPONSE FORMATTER - Format responses for each role
# =============================================================================


class ResponseFormatter:
    """
    Formats responses appropriately for each user role.

    - Lawyers get formal, citation-rich responses
    - Parties get simplified, supportive responses
    - Children get age-appropriate, friendly responses
    """

    def format(
        self,
        response: str,
        user: User,
        config: Optional[RoleConfig] = None,
    ) -> str:
        """Format response for user's role."""
        if config is None:
            config = ROLE_CONFIGS.get(user.role, ROLE_CONFIGS[UserRole.ANONYMOUS])

        # Apply transformations
        formatted = response

        if config.simplified_language:
            formatted = self._simplify_language(formatted)

        if config.child_friendly:
            formatted = self._make_child_friendly(formatted)

        if config.max_response_length and len(formatted) > config.max_response_length:
            formatted = self._truncate_with_summary(
                formatted, config.max_response_length
            )

        # Add disclaimer if required
        if config.show_legal_disclaimer:
            formatted = self._add_disclaimer(formatted, config)

        # Add role-specific footer
        formatted = self._add_footer(formatted, user, config)

        return formatted

    def _simplify_language(self, text: str) -> str:
        """Replace legal jargon with plain English."""
        replacements = {
            "initiating application": "first court form",
            "respondent": "the other parent",
            "applicant": "the parent who started the case",
            "affidavit": "written statement",
            "contravention": "breaking the orders",
            "interim orders": "temporary orders",
            "final orders": "permanent orders",
            "parenting orders": "orders about the children",
            "consent orders": "orders both parents agree to",
            "FDR": "family mediation",
            "ICL": "children's lawyer",
            "registrar": "court official",
        }

        result = text
        for legal_term, plain_term in replacements.items():
            result = result.replace(legal_term, plain_term)
            result = result.replace(legal_term.title(), plain_term)

        return result

    def _make_child_friendly(self, text: str) -> str:
        """Make response appropriate for children."""
        # Shorter sentences, friendlier tone
        text = text.replace("You must", "You need to")
        text = text.replace("It is important that", "It's good to")
        text = text.replace("court", "the place where the judge works")

        # Add reassurance
        if "worried" in text.lower() or "scared" in text.lower():
            text += "\n\nRemember: It's okay to have big feelings about this. The grown-ups are working to help everyone."

        return text

    def _truncate_with_summary(self, text: str, max_length: int) -> str:
        """Truncate long responses with a summary."""
        if len(text) <= max_length:
            return text

        # Find a good break point
        truncated = text[:max_length]
        last_period = truncated.rfind(".")
        if last_period > max_length * 0.7:
            truncated = truncated[: last_period + 1]

        truncated += "\n\n[Response shortened. Ask for more details if needed.]"
        return truncated

    def _add_disclaimer(self, text: str, config: RoleConfig) -> str:
        """Add legal disclaimer based on configuration."""
        disclaimer = (
            "\n\n---\n"
            "ℹ️ This is general information only, not legal advice. "
            "Always consult a qualified lawyer for advice about your situation."
        )
        return text + disclaimer

    def _add_footer(self, text: str, user: User, config: RoleConfig) -> str:
        """Add role-specific footer."""
        footers = {
            UserRole.APPLICANT: "\n\nNeed to speak to someone? Call Legal Aid: 1300 888 529",
            UserRole.RESPONDENT: "\n\nNeed to speak to someone? Call Legal Aid: 1300 888 529",
            UserRole.CHILD_DIRECT: "\n\n💙 If you need to talk to someone, you can call Kids Helpline: 1800 55 1800",
        }

        if config.show_safety_resources and user.role in footers:
            text += footers[user.role]

        return text


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Create users of different types
    applicant = User(
        user_id="u001",
        role=UserRole.APPLICANT,
        name="Sarah",
        case_ids=["FAM-2024-001"],
        party_side="applicant",
        accessibility_needs={"screen_reader": True},
    )

    lawyer = User(
        user_id="u002",
        role=UserRole.APPLICANT_LAWYER,
        name="Jane Smith",
        organization="Smith Family Law",
        case_ids=["FAM-2024-001"],
        party_side="applicant",
    )

    child = User(
        user_id="u003",
        role=UserRole.CHILD_SUPPORTED,
        name="Alex",
        case_ids=["FAM-2024-001"],
    )

    # Route queries
    router = QueryRouter()
    formatter = ResponseFormatter()

    # Applicant asking about court
    print("=== Applicant Query ===")
    route_result = router.route(applicant, "I'm scared about my court date tomorrow")
    print(f"Intent: {route_result['intent']}")
    print(f"Handler: {route_result['handler']}")
    print(f"Warnings: {route_result['warnings']}")

    # Lawyer asking for legal research
    print("\n=== Lawyer Query ===")
    route_result = router.route(
        lawyer, "What does section 60CC say about best interests?"
    )
    print(f"Intent: {route_result['intent']}")
    print(f"Handler: {route_result['handler']}")
    print(f"Allowed: {route_result['allowed']}")

    # Child asking a question
    print("\n=== Child Query ===")
    route_result = router.route(child, "Why do mum and dad have to go to court?")
    print(f"Intent: {route_result['intent']}")
    print(f"Handler: {route_result['handler']}")
    print(f"Config child_friendly: {route_result['config'].child_friendly}")

    # Format a response for child
    sample_response = "The court is where a judge listens to both your parents and helps them make decisions about things like where you'll live and when you'll see each parent."
    formatted = formatter.format(sample_response, child)
    print(f"\nFormatted for child:\n{formatted}")
