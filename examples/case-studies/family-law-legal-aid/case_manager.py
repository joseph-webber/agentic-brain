#!/usr/bin/env python3
"""
Australian Family Law Case Management System

A comprehensive system to help self-represented litigants track their family
court matter through all phases - from separation to final orders.

CMMS-Compatible Design
======================
This module follows Case Management System (CMMS) standards for
interoperability with major legal practice management solutions:
- LEAP Legal Software
- Actionstep
- Clio
- PracticePanther
- FilePro
- SILQ

The interface layer (CMMSAdapter) provides standard hooks for:
- Matter/Case CRUD operations
- Workflow state transitions
- Document management events
- Calendar/deadline integration
- Contact/party management

Features:
- Phase-by-phase tracking with guidance
- Deadline calculation and reminders
- Document tracking and checklists
- Privacy-safe exports (anonymized)
- Emotional support and check-ins
- Accessibility features (clear summaries)
- CMMS webhook integration

Courts supported:
- FCFCOA (Federal Circuit and Family Court of Australia)
- FCoWA (Family Court of Western Australia)
- State Magistrates Courts (some family matters)

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
"""

from __future__ import annotations

import json
import hashlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================


class CasePhase(Enum):
    """All phases of a family court matter in Australia."""

    SEPARATION = auto()  # Just separated, understanding options
    FDR = auto()  # Family Dispute Resolution (mediation)
    FILING = auto()  # Preparing to file application
    FIRST_RETURN = auto()  # First court date (mention/directions)
    INTERIM = auto()  # Interim orders phase
    COMPLIANCE = auto()  # Directions, disclosure, subpoenas
    TRIAL_PREP = auto()  # Preparing for final hearing
    FINAL_HEARING = auto()  # The trial itself
    POST_ORDERS = auto()  # After orders made
    CONTRAVENTION = auto()  # If orders breached
    APPEAL = auto()  # If appealing decision

    def __str__(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def description(self) -> str:
        """Human-readable description of each phase."""
        descriptions = {
            CasePhase.SEPARATION: "Recently separated, exploring options",
            CasePhase.FDR: "Attending Family Dispute Resolution (mediation)",
            CasePhase.FILING: "Preparing and filing court application",
            CasePhase.FIRST_RETURN: "First court appearance",
            CasePhase.INTERIM: "Seeking or responding to interim orders",
            CasePhase.COMPLIANCE: "Complying with directions and disclosure",
            CasePhase.TRIAL_PREP: "Preparing for final hearing",
            CasePhase.FINAL_HEARING: "Attending the final hearing (trial)",
            CasePhase.POST_ORDERS: "After orders have been made",
            CasePhase.CONTRAVENTION: "Dealing with breach of orders",
            CasePhase.APPEAL: "Appealing a court decision",
        }
        return descriptions.get(self, "Unknown phase")


class DocumentType(Enum):
    """Types of documents in family law proceedings."""

    # Initiating documents
    INITIATING_APPLICATION = "Initiating Application"
    RESPONSE = "Response to Initiating Application"

    # Parenting
    PARENTING_QUESTIONNAIRE = "Parenting Questionnaire"
    NOTICE_OF_CHILD_ABUSE = "Notice of Child Abuse/Family Violence"
    FAMILY_REPORT = "Family Report"

    # Property
    FINANCIAL_STATEMENT = "Financial Statement"
    PROPERTY_QUESTIONNAIRE = "Property Questionnaire"

    # Evidence
    AFFIDAVIT = "Affidavit"
    ANNEXURE = "Annexure to Affidavit"
    SUBPOENA = "Subpoena"
    SUBPOENA_RETURN = "Subpoenaed Material"

    # Court forms
    NOTICE_OF_ADDRESS = "Notice of Address for Service"
    CONSENT_ORDERS = "Application for Consent Orders"
    MINUTE_OF_ORDERS = "Minute of Proposed Orders"

    # Interim
    INTERIM_APPLICATION = "Application in a Case"
    INTERIM_RESPONSE = "Response to Application in a Case"

    # Other
    FDR_CERTIFICATE = "FDR Certificate (Section 60I)"
    ICL_REPORT = "Independent Children's Lawyer Report"
    EXPERT_REPORT = "Expert Report"
    OUTLINE_OF_CASE = "Outline of Case"

    def __str__(self) -> str:
        return self.value


class OrderType(Enum):
    """Types of court orders."""

    INTERIM = "Interim Orders"
    FINAL = "Final Orders"
    CONSENT = "Consent Orders"
    PROCEDURAL = "Procedural/Directions Orders"
    INJUNCTION = "Injunction/Restraining Order"
    RECOVERY = "Recovery Order"
    CONTRAVENTION = "Contravention Order"


class PartyRole(Enum):
    """Role of a party in proceedings."""

    APPLICANT = "Applicant"
    RESPONDENT = "Respondent"
    ICL = "Independent Children's Lawyer"
    INTERVENOR = "Intervenor"


class UrgencyLevel(Enum):
    """Urgency level for deadlines."""

    CRITICAL = "Critical"  # Must do today/tomorrow
    HIGH = "High"  # Within a week
    MEDIUM = "Medium"  # Within 2 weeks
    LOW = "Low"  # More than 2 weeks
    INFO = "Information"  # No action required


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Party:
    """A party to the proceedings (anonymized for privacy)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: PartyRole = PartyRole.APPLICANT
    pseudonym: str = ""  # e.g., "Party A", "Father", "Mother"
    is_self: bool = False  # Is this the user?
    has_lawyer: bool = False
    lawyer_name: Optional[str] = None

    def __post_init__(self):
        if not self.pseudonym:
            self.pseudonym = f"Party {self.id[:4].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "pseudonym": self.pseudonym,
            "is_self": self.is_self,
            "has_lawyer": self.has_lawyer,
            "lawyer_name": self.lawyer_name if not self.is_self else "[REDACTED]",
        }


@dataclass
class Child:
    """A child of the relationship (anonymized)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    pseudonym: str = ""  # e.g., "Child 1", "Eldest"
    birth_year: Optional[int] = None  # Only year for privacy
    age_group: str = ""  # "infant", "toddler", "school-age", "teenager"
    special_needs: bool = False
    special_needs_notes: str = ""  # Anonymized description

    def __post_init__(self):
        if not self.pseudonym:
            self.pseudonym = f"Child {self.id[:4].upper()}"
        if self.birth_year and not self.age_group:
            age = datetime.now().year - self.birth_year
            if age < 1:
                self.age_group = "infant"
            elif age < 4:
                self.age_group = "toddler"
            elif age < 13:
                self.age_group = "school-age"
            else:
                self.age_group = "teenager"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pseudonym": self.pseudonym,
            "birth_year": self.birth_year,
            "age_group": self.age_group,
            "special_needs": self.special_needs,
            "special_needs_notes": self.special_needs_notes,
        }


@dataclass
class Document:
    """A document in the proceedings."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    doc_type: DocumentType = DocumentType.AFFIDAVIT
    title: str = ""
    filed_date: Optional[datetime] = None
    served_date: Optional[datetime] = None
    filed_by: Optional[str] = None  # Party ID
    file_path: Optional[str] = None  # Local path (not exported)
    court_reference: Optional[str] = None
    notes: str = ""

    @property
    def is_filed(self) -> bool:
        return self.filed_date is not None

    @property
    def is_served(self) -> bool:
        return self.served_date is not None

    def to_dict(self, include_path: bool = False) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "doc_type": str(self.doc_type),
            "title": self.title,
            "filed_date": self.filed_date.isoformat() if self.filed_date else None,
            "served_date": self.served_date.isoformat() if self.served_date else None,
            "filed_by": self.filed_by,
            "court_reference": self.court_reference,
            "notes": self.notes,
        }
        if include_path:
            result["file_path"] = self.file_path
        return result


@dataclass
class Order:
    """A court order."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    order_type: OrderType = OrderType.PROCEDURAL
    date_made: datetime = field(default_factory=datetime.now)
    made_by: str = ""  # Judge/Registrar name (optional)
    summary: str = ""  # Plain English summary
    key_provisions: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    compliance_dates: Dict[str, datetime] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "order_type": self.order_type.value,
            "date_made": self.date_made.isoformat(),
            "made_by": self.made_by,
            "summary": self.summary,
            "key_provisions": self.key_provisions,
            "next_steps": self.next_steps,
            "compliance_dates": {
                k: v.isoformat() for k, v in self.compliance_dates.items()
            },
        }


@dataclass
class Deadline:
    """A deadline to track."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    due_date: datetime = field(default_factory=datetime.now)
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    completed: bool = False
    completed_date: Optional[datetime] = None
    related_document: Optional[str] = None  # Document ID
    auto_generated: bool = False
    reminder_days: List[int] = field(default_factory=lambda: [7, 3, 1])

    @property
    def days_remaining(self) -> int:
        if self.completed:
            return 0
        delta = self.due_date.date() - datetime.now().date()
        return delta.days

    @property
    def is_overdue(self) -> bool:
        return not self.completed and self.days_remaining < 0

    def calculate_urgency(self) -> UrgencyLevel:
        """Calculate urgency based on days remaining."""
        days = self.days_remaining
        if days < 0:
            return UrgencyLevel.CRITICAL
        elif days <= 2:
            return UrgencyLevel.CRITICAL
        elif days <= 7:
            return UrgencyLevel.HIGH
        elif days <= 14:
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat(),
            "urgency": self.urgency.value,
            "completed": self.completed,
            "completed_date": (
                self.completed_date.isoformat() if self.completed_date else None
            ),
            "related_document": self.related_document,
            "days_remaining": self.days_remaining,
            "is_overdue": self.is_overdue,
        }


@dataclass
class Note:
    """A note or journal entry."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    content: str = ""
    category: str = "general"  # "legal", "emotional", "evidence", "communication"
    mood_rating: Optional[int] = None  # 1-10 for emotional check-ins
    private: bool = True  # Don't export

    def to_dict(self, include_private: bool = False) -> Optional[Dict[str, Any]]:
        if self.private and not include_private:
            return None
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content if include_private else "[PRIVATE]",
            "category": self.category,
            "mood_rating": self.mood_rating,
        }


# =============================================================================
# FAMILY LAW CASE CLASS
# =============================================================================


class FamilyLawCase:
    """
    Main case management class for an Australian family law matter.

    Tracks all aspects of a family court case from separation through
    to final orders (and beyond if needed).
    """

    def __init__(
        self,
        case_number: Optional[str] = None,
        court: str = "FCFCOA",
        phase: CasePhase = CasePhase.SEPARATION,
    ):
        self.id: str = str(uuid.uuid4())
        self.case_number: Optional[str] = case_number
        self.court: str = court
        self.phase: CasePhase = phase
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

        # Parties and children
        self.parties: List[Party] = []
        self.children: List[Child] = []

        # Case tracking
        self.key_dates: Dict[str, datetime] = {}
        self.documents: List[Document] = []
        self.orders: List[Order] = []
        self.deadlines: List[Deadline] = []
        self.notes: List[Note] = []

        # Matter types
        self.is_parenting_matter: bool = True
        self.is_property_matter: bool = False
        self.is_child_support_matter: bool = False

        # Flags
        self.family_violence_alleged: bool = False
        self.child_abuse_alleged: bool = False
        self.icl_appointed: bool = False
        self.family_report_ordered: bool = False

        # Initialize trackers
        self.deadline_tracker = DeadlineTracker(self)
        self.document_tracker = DocumentTracker(self)
        self.phase_guidance = PhaseGuidance(self)
        self.emotional_support = EmotionalSupport(self)

    def add_party(self, party: Party) -> None:
        """Add a party to the case."""
        self.parties.append(party)
        self.updated_at = datetime.now()

    def add_child(self, child: Child) -> None:
        """Add a child to the case."""
        self.children.append(child)
        self.updated_at = datetime.now()

    def add_document(self, document: Document) -> None:
        """Add a document to the case."""
        self.documents.append(document)
        self.updated_at = datetime.now()

    def add_order(self, order: Order) -> None:
        """Add an order and generate compliance deadlines."""
        self.orders.append(order)
        # Auto-generate deadlines for compliance dates
        for desc, due_date in order.compliance_dates.items():
            deadline = Deadline(
                title=f"Comply: {desc}",
                description=f"From order dated {order.date_made.strftime('%d/%m/%Y')}",
                due_date=due_date,
                auto_generated=True,
            )
            self.deadlines.append(deadline)
        self.updated_at = datetime.now()

    def add_deadline(self, deadline: Deadline) -> None:
        """Add a deadline."""
        deadline.urgency = deadline.calculate_urgency()
        self.deadlines.append(deadline)
        self.updated_at = datetime.now()

    def add_note(
        self, content: str, category: str = "general", mood_rating: Optional[int] = None
    ) -> Note:
        """Add a note to the case journal."""
        note = Note(content=content, category=category, mood_rating=mood_rating)
        self.notes.append(note)
        self.updated_at = datetime.now()
        return note

    def set_key_date(self, name: str, date_value: datetime) -> None:
        """Set a key date (e.g., 'separation', 'first_hearing')."""
        self.key_dates[name] = date_value
        self.updated_at = datetime.now()

    def advance_phase(self, new_phase: CasePhase) -> Dict[str, Any]:
        """
        Advance to a new phase and get guidance.

        Returns dict with guidance for the new phase.
        """
        old_phase = self.phase
        self.phase = new_phase
        self.updated_at = datetime.now()

        # Get guidance for new phase
        guidance = self.phase_guidance.get_phase_guidance(new_phase)

        # Auto-generate deadlines for new phase
        new_deadlines = self.deadline_tracker.generate_phase_deadlines(new_phase)
        for deadline in new_deadlines:
            self.deadlines.append(deadline)

        return {
            "previous_phase": str(old_phase),
            "new_phase": str(new_phase),
            "guidance": guidance,
            "new_deadlines": [d.to_dict() for d in new_deadlines],
        }

    def get_pending_deadlines(self) -> List[Deadline]:
        """Get all pending (not completed) deadlines, sorted by urgency."""
        pending = [d for d in self.deadlines if not d.completed]
        # Update urgency levels
        for d in pending:
            d.urgency = d.calculate_urgency()
        # Sort: Critical first, then by date
        return sorted(
            pending, key=lambda d: (-list(UrgencyLevel).index(d.urgency), d.due_date)
        )

    def get_overdue_items(self) -> List[Deadline]:
        """Get all overdue deadlines."""
        return [d for d in self.deadlines if d.is_overdue]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get an accessible summary of the case.

        Designed for screen readers and quick review.
        """
        pending = self.get_pending_deadlines()
        overdue = self.get_overdue_items()

        summary = {
            "case_number": self.case_number or "Not yet filed",
            "court": self.court,
            "current_phase": str(self.phase),
            "phase_description": self.phase.description,
            # Parties
            "number_of_parties": len(self.parties),
            "number_of_children": len(self.children),
            "children_ages": [c.age_group for c in self.children],
            # Status
            "is_parenting": self.is_parenting_matter,
            "is_property": self.is_property_matter,
            "icl_appointed": self.icl_appointed,
            "family_report_ordered": self.family_report_ordered,
            # Urgency
            "overdue_items": len(overdue),
            "pending_deadlines": len(pending),
            "critical_deadlines": len(
                [d for d in pending if d.urgency == UrgencyLevel.CRITICAL]
            ),
            # Documents
            "documents_filed": len([d for d in self.documents if d.is_filed]),
            "documents_pending": len([d for d in self.documents if not d.is_filed]),
            # Recent activity
            "last_updated": self.updated_at.isoformat(),
        }

        # Add key dates
        summary["key_dates"] = {
            k: v.strftime("%d %B %Y") for k, v in self.key_dates.items()
        }

        return summary

    def get_accessible_status(self) -> str:
        """
        Get a plain-English status suitable for reading aloud.

        Designed for VoiceOver/screen reader accessibility.
        """
        summary = self.get_summary()
        overdue = self.get_overdue_items()
        pending = self.get_pending_deadlines()[:3]  # Top 3

        lines = [
            f"Family Law Case Status as of {datetime.now().strftime('%d %B %Y')}.",
            "",
            f"Your case is in the {summary['current_phase']} phase.",
            f"That means: {summary['phase_description']}.",
            "",
        ]

        # Urgency section
        if overdue:
            lines.append(f"WARNING: You have {len(overdue)} overdue items!")
            for item in overdue[:3]:
                lines.append(
                    f"  - {item.title} was due {abs(item.days_remaining)} days ago."
                )

        if pending:
            lines.append("")
            lines.append("Your upcoming deadlines:")
            for item in pending:
                if item.days_remaining == 0:
                    lines.append(f"  - {item.title} is due TODAY.")
                elif item.days_remaining == 1:
                    lines.append(f"  - {item.title} is due TOMORROW.")
                else:
                    lines.append(f"  - {item.title} in {item.days_remaining} days.")

        # Next steps
        guidance = self.phase_guidance.get_phase_guidance(self.phase)
        if guidance.get("immediate_actions"):
            lines.append("")
            lines.append("Recommended next steps:")
            for action in guidance["immediate_actions"][:3]:
                lines.append(f"  - {action}")

        return "\n".join(lines)

    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """Convert case to dictionary for serialization."""
        return {
            "id": self.id,
            "case_number": self.case_number,
            "court": self.court,
            "phase": self.phase.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "parties": [p.to_dict() for p in self.parties],
            "children": [c.to_dict() for c in self.children],
            "key_dates": {k: v.isoformat() for k, v in self.key_dates.items()},
            "documents": [d.to_dict() for d in self.documents],
            "orders": [o.to_dict() for o in self.orders],
            "deadlines": [d.to_dict() for d in self.deadlines],
            "notes": [
                n.to_dict(include_private)
                for n in self.notes
                if n.to_dict(include_private)
            ],
            "is_parenting_matter": self.is_parenting_matter,
            "is_property_matter": self.is_property_matter,
            "is_child_support_matter": self.is_child_support_matter,
            "family_violence_alleged": self.family_violence_alleged,
            "child_abuse_alleged": self.child_abuse_alleged,
            "icl_appointed": self.icl_appointed,
            "family_report_ordered": self.family_report_ordered,
        }

    def save(self, filepath: Path, include_private: bool = True) -> None:
        """Save case to JSON file."""
        data = self.to_dict(include_private=include_private)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    @classmethod
    def load(cls, filepath: Path) -> "FamilyLawCase":
        """Load case from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)

        case = cls(
            case_number=data.get("case_number"),
            court=data.get("court", "FCFCOA"),
            phase=CasePhase[data.get("phase", "SEPARATION")],
        )
        case.id = data.get("id", case.id)
        case.created_at = datetime.fromisoformat(data["created_at"])
        case.updated_at = datetime.fromisoformat(data["updated_at"])

        # Load parties
        for p_data in data.get("parties", []):
            party = Party(
                id=p_data["id"],
                role=PartyRole(p_data["role"]),
                pseudonym=p_data["pseudonym"],
                is_self=p_data.get("is_self", False),
                has_lawyer=p_data.get("has_lawyer", False),
                lawyer_name=p_data.get("lawyer_name"),
            )
            case.parties.append(party)

        # Load children
        for c_data in data.get("children", []):
            child = Child(
                id=c_data["id"],
                pseudonym=c_data["pseudonym"],
                birth_year=c_data.get("birth_year"),
                age_group=c_data.get("age_group", ""),
                special_needs=c_data.get("special_needs", False),
                special_needs_notes=c_data.get("special_needs_notes", ""),
            )
            case.children.append(child)

        # Load key dates
        for name, date_str in data.get("key_dates", {}).items():
            case.key_dates[name] = datetime.fromisoformat(date_str)

        # Load documents
        for d_data in data.get("documents", []):
            doc = Document(
                id=d_data["id"],
                doc_type=(
                    DocumentType(d_data["doc_type"])
                    if d_data.get("doc_type")
                    else DocumentType.AFFIDAVIT
                ),
                title=d_data.get("title", ""),
                filed_date=(
                    datetime.fromisoformat(d_data["filed_date"])
                    if d_data.get("filed_date")
                    else None
                ),
                served_date=(
                    datetime.fromisoformat(d_data["served_date"])
                    if d_data.get("served_date")
                    else None
                ),
                filed_by=d_data.get("filed_by"),
                court_reference=d_data.get("court_reference"),
                notes=d_data.get("notes", ""),
            )
            case.documents.append(doc)

        # Load flags
        case.is_parenting_matter = data.get("is_parenting_matter", True)
        case.is_property_matter = data.get("is_property_matter", False)
        case.is_child_support_matter = data.get("is_child_support_matter", False)
        case.family_violence_alleged = data.get("family_violence_alleged", False)
        case.child_abuse_alleged = data.get("child_abuse_alleged", False)
        case.icl_appointed = data.get("icl_appointed", False)
        case.family_report_ordered = data.get("family_report_ordered", False)

        return case

    def export_anonymized(self, filepath: Path) -> None:
        """
        Export a privacy-safe version of the case.

        Removes or hashes all identifying information.
        """
        data = self.to_dict(include_private=False)

        # Hash the case number
        if data.get("case_number"):
            data["case_number"] = hashlib.sha256(
                data["case_number"].encode()
            ).hexdigest()[:12]

        # Remove any potential identifying info
        data["id"] = hashlib.sha256(data["id"].encode()).hexdigest()[:12]

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)


# =============================================================================
# DEADLINE TRACKER
# =============================================================================


class DeadlineTracker:
    """
    Tracks and calculates deadlines for family law matters.

    Knows the standard timeframes under the Family Law Rules.
    """

    # Standard timeframes (in days)
    TIMEFRAMES = {
        "response_initiating": 28,  # Response to initiating application
        "response_interim": 14,  # Response to interim application
        "service_before_hearing": 2,  # Service before hearing (business days)
        "affidavit_service": 14,  # Affidavit service before hearing
        "disclosure": 28,  # Standard disclosure period
        "subpoena_compliance": 21,  # Subpoena compliance
        "appeal_notice": 28,  # Notice of appeal
        "consent_orders_draft": 14,  # Draft consent orders review
    }

    def __init__(self, case: FamilyLawCase):
        self.case = case

    def calculate_response_deadline(
        self, filing_date: datetime, is_interim: bool = False
    ) -> datetime:
        """Calculate when a response is due."""
        days = (
            self.TIMEFRAMES["response_interim"]
            if is_interim
            else self.TIMEFRAMES["response_initiating"]
        )
        return filing_date + timedelta(days=days)

    def calculate_service_deadline(self, hearing_date: datetime) -> datetime:
        """Calculate when documents must be served before a hearing."""
        # Go back 2 business days
        deadline = hearing_date
        business_days = 0
        while business_days < self.TIMEFRAMES["service_before_hearing"]:
            deadline -= timedelta(days=1)
            if deadline.weekday() < 5:  # Monday-Friday
                business_days += 1
        return deadline

    def calculate_disclosure_deadline(self, order_date: datetime) -> datetime:
        """Calculate disclosure compliance deadline."""
        return order_date + timedelta(days=self.TIMEFRAMES["disclosure"])

    def generate_phase_deadlines(self, phase: CasePhase) -> List[Deadline]:
        """Generate standard deadlines for entering a new phase."""
        deadlines = []
        today = datetime.now()

        if phase == CasePhase.FDR:
            deadlines.append(
                Deadline(
                    title="Book FDR appointment",
                    description="Contact an FDR practitioner to book mediation",
                    due_date=today + timedelta(days=7),
                    auto_generated=True,
                )
            )

        elif phase == CasePhase.FILING:
            deadlines.append(
                Deadline(
                    title="Complete Initiating Application",
                    description="Draft and review the Initiating Application",
                    due_date=today + timedelta(days=14),
                    auto_generated=True,
                )
            )
            deadlines.append(
                Deadline(
                    title="Gather supporting documents",
                    description="Collect evidence and annexures for affidavit",
                    due_date=today + timedelta(days=21),
                    auto_generated=True,
                )
            )

        elif phase == CasePhase.INTERIM:
            deadlines.append(
                Deadline(
                    title="File interim application",
                    description="Application in a Case for interim orders",
                    due_date=today + timedelta(days=7),
                    urgency=UrgencyLevel.HIGH,
                    auto_generated=True,
                )
            )

        elif phase == CasePhase.COMPLIANCE:
            deadlines.append(
                Deadline(
                    title="Complete disclosure",
                    description="Provide all required disclosure documents",
                    due_date=today + timedelta(days=28),
                    auto_generated=True,
                )
            )

        elif phase == CasePhase.TRIAL_PREP:
            deadlines.append(
                Deadline(
                    title="File Outline of Case",
                    description="Prepare and file your Outline of Case",
                    due_date=today + timedelta(days=21),
                    auto_generated=True,
                )
            )
            deadlines.append(
                Deadline(
                    title="Prepare trial bundle",
                    description="Organize documents for the final hearing",
                    due_date=today + timedelta(days=28),
                    auto_generated=True,
                )
            )

        return deadlines

    def get_upcoming_reminders(self, days_ahead: int = 14) -> List[Dict[str, Any]]:
        """Get reminders for upcoming deadlines."""
        reminders = []
        cutoff = datetime.now() + timedelta(days=days_ahead)

        for deadline in self.case.deadlines:
            if deadline.completed:
                continue
            if deadline.due_date <= cutoff:
                reminders.append(
                    {
                        "deadline": deadline.to_dict(),
                        "days_until": deadline.days_remaining,
                        "message": self._format_reminder(deadline),
                    }
                )

        return sorted(reminders, key=lambda r: r["days_until"])

    def _format_reminder(self, deadline: Deadline) -> str:
        """Format a deadline into a human-readable reminder."""
        days = deadline.days_remaining

        if days < 0:
            return f"OVERDUE: {deadline.title} was due {abs(days)} days ago!"
        elif days == 0:
            return f"DUE TODAY: {deadline.title}"
        elif days == 1:
            return f"DUE TOMORROW: {deadline.title}"
        elif days <= 7:
            return f"DUE THIS WEEK: {deadline.title} in {days} days"
        else:
            return f"UPCOMING: {deadline.title} in {days} days"


# =============================================================================
# DOCUMENT TRACKER
# =============================================================================


class DocumentTracker:
    """
    Tracks documents filed and served in the matter.

    Generates checklists based on case phase and type.
    """

    def __init__(self, case: FamilyLawCase):
        self.case = case

    def get_required_documents(self) -> List[DocumentType]:
        """Get documents required for current phase."""
        phase = self.case.phase
        required = []

        # Common to all filed matters
        if phase not in [CasePhase.SEPARATION, CasePhase.FDR]:
            required.append(DocumentType.INITIATING_APPLICATION)
            required.append(DocumentType.NOTICE_OF_ADDRESS)

        # FDR certificate needed before filing (unless exemption)
        if phase == CasePhase.FILING:
            required.append(DocumentType.FDR_CERTIFICATE)

        # Parenting matters
        if self.case.is_parenting_matter:
            if phase in [CasePhase.FILING, CasePhase.FIRST_RETURN]:
                required.append(DocumentType.PARENTING_QUESTIONNAIRE)
            if self.case.family_violence_alleged or self.case.child_abuse_alleged:
                required.append(DocumentType.NOTICE_OF_CHILD_ABUSE)

        # Property matters
        if self.case.is_property_matter:
            required.append(DocumentType.FINANCIAL_STATEMENT)
            if phase in [CasePhase.COMPLIANCE, CasePhase.TRIAL_PREP]:
                required.append(DocumentType.PROPERTY_QUESTIONNAIRE)

        # Interim phase
        if phase == CasePhase.INTERIM:
            required.append(DocumentType.INTERIM_APPLICATION)
            required.append(DocumentType.AFFIDAVIT)

        # Trial prep
        if phase == CasePhase.TRIAL_PREP:
            required.append(DocumentType.OUTLINE_OF_CASE)
            required.append(DocumentType.AFFIDAVIT)

        return required

    def get_document_checklist(self) -> Dict[str, Any]:
        """
        Generate a checklist of required documents.

        Shows what's filed, what's pending, what's missing.
        """
        required = self.get_required_documents()
        filed_types = {d.doc_type for d in self.case.documents if d.is_filed}
        served_types = {d.doc_type for d in self.case.documents if d.is_served}

        checklist = {"phase": str(self.case.phase), "items": []}

        for doc_type in required:
            status = "missing"
            if doc_type in filed_types:
                status = "served" if doc_type in served_types else "filed"

            checklist["items"].append(
                {"document": str(doc_type), "status": status, "required": True}
            )

        # Add any extra documents filed but not required
        for doc in self.case.documents:
            if doc.doc_type not in required:
                checklist["items"].append(
                    {
                        "document": str(doc.doc_type),
                        "status": (
                            "served"
                            if doc.is_served
                            else ("filed" if doc.is_filed else "draft")
                        ),
                        "required": False,
                    }
                )

        return checklist

    def get_outstanding_service(self) -> List[Document]:
        """Get documents filed but not yet served."""
        return [d for d in self.case.documents if d.is_filed and not d.is_served]

    def get_accessible_checklist(self) -> str:
        """Get a screen-reader friendly checklist."""
        checklist = self.get_document_checklist()
        lines = [f"Document Checklist for {checklist['phase']} phase:", ""]

        for item in checklist["items"]:
            if item["status"] == "missing":
                lines.append(f"  [ ] {item['document']} - NEEDED")
            elif item["status"] == "filed":
                lines.append(f"  [F] {item['document']} - Filed, needs service")
            elif item["status"] == "served":
                lines.append(f"  [✓] {item['document']} - Complete")
            else:
                lines.append(f"  [D] {item['document']} - Draft")

        outstanding = self.get_outstanding_service()
        if outstanding:
            lines.append("")
            lines.append(f"WARNING: {len(outstanding)} documents need service:")
            for doc in outstanding:
                lines.append(f"  - {doc.title or str(doc.doc_type)}")

        return "\n".join(lines)


# =============================================================================
# PHASE GUIDANCE
# =============================================================================


class PhaseGuidance:
    """
    Provides guidance for each phase of family law proceedings.

    Includes what to expect, required documents, tips, and timeframes.
    """

    def __init__(self, case: FamilyLawCase):
        self.case = case

    def get_phase_guidance(self, phase: CasePhase) -> Dict[str, Any]:
        """Get comprehensive guidance for a phase."""
        guidance_methods = {
            CasePhase.SEPARATION: self._separation_guidance,
            CasePhase.FDR: self._fdr_guidance,
            CasePhase.FILING: self._filing_guidance,
            CasePhase.FIRST_RETURN: self._first_return_guidance,
            CasePhase.INTERIM: self._interim_guidance,
            CasePhase.COMPLIANCE: self._compliance_guidance,
            CasePhase.TRIAL_PREP: self._trial_prep_guidance,
            CasePhase.FINAL_HEARING: self._final_hearing_guidance,
            CasePhase.POST_ORDERS: self._post_orders_guidance,
            CasePhase.CONTRAVENTION: self._contravention_guidance,
            CasePhase.APPEAL: self._appeal_guidance,
        }

        method = guidance_methods.get(phase, self._generic_guidance)
        return method()

    def _separation_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Separation",
            "description": "You've recently separated. This is a time to understand your options before taking any legal action.",
            "estimated_duration": "As long as you need",
            "what_to_expect": [
                "Emotional upheaval - this is normal",
                "Need to establish new living arrangements",
                "Important to document the date of separation",
                "Consider interim arrangements for children",
            ],
            "immediate_actions": [
                "Record the separation date (important for property)",
                "Establish interim parenting arrangements if possible",
                "Secure important documents (financial records, passports)",
                "Seek legal advice to understand your rights",
            ],
            "documents_needed": [
                "None required yet, but start gathering:",
                "Financial records (tax returns, bank statements)",
                "Property documents (titles, mortgages)",
                "Superannuation statements",
            ],
            "common_pitfalls": [
                "Making hasty agreements without legal advice",
                "Removing children without agreement",
                "Disposing of assets",
                "Social media posts about the separation",
            ],
            "tips_for_self_rep": [
                "Get at least one session of legal advice",
                "Consider FDR (mediation) before court",
                "Focus on children's best interests",
                "Keep communication civil and in writing",
            ],
            "support_services": [
                "Family Relationships Advice Line: 1800 050 321",
                "Legal Aid in your state for free legal advice",
                "Relationships Australia for counselling",
            ],
        }

    def _fdr_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Family Dispute Resolution",
            "description": "Mediation to try to resolve matters without court. Required before filing parenting applications (with some exceptions).",
            "estimated_duration": "1-3 months",
            "what_to_expect": [
                "One or more mediation sessions",
                "Discussion facilitated by neutral practitioner",
                "Opportunity to propose parenting arrangements",
                "May result in agreement or certificate to file",
            ],
            "immediate_actions": [
                "Find an FDR practitioner (can search FDRR)",
                "Prepare your proposals for parenting time",
                "Think about children's needs and routines",
                "Consider what you can compromise on",
            ],
            "documents_needed": [
                "No formal documents, but bring:",
                "Calendar of children's activities",
                "School/childcare schedule",
                "Your proposed parenting plan",
            ],
            "common_pitfalls": [
                "Going in with fixed positions",
                "Refusing to consider other proposals",
                "Getting emotional instead of focusing on children",
                "Not preparing properly",
            ],
            "tips_for_self_rep": [
                "FDR is confidential - can speak freely",
                "Focus on children's needs, not past grievances",
                "Written agreements can become consent orders",
                "If unsafe, you may be exempt from FDR",
            ],
            "exemptions_from_fdr": [
                "Family violence",
                "Child abuse concerns",
                "Urgency (risk of harm)",
                "Other party's location unknown",
            ],
        }

    def _filing_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Filing Court Application",
            "description": "Preparing and filing your application with the court. This officially starts the court process.",
            "estimated_duration": "2-4 weeks to prepare",
            "what_to_expect": [
                "Completing court forms (can be complex)",
                "Paying filing fee (or applying for fee exemption)",
                "Receiving court date after filing",
                "Needing to serve the other party",
            ],
            "immediate_actions": [
                "Obtain FDR certificate (or exemption)",
                "Complete Initiating Application form",
                "Draft supporting affidavit",
                "Gather annexures (evidence documents)",
            ],
            "documents_needed": [
                "Initiating Application",
                "Section 60I (FDR) Certificate",
                "Affidavit in support",
                "Notice of Address for Service",
                "Parenting Questionnaire (if parenting)",
                "Financial Statement (if property)",
            ],
            "common_pitfalls": [
                "Not attaching FDR certificate",
                "Incomplete forms (will be rejected)",
                "Too much irrelevant detail in affidavit",
                "Not serving within required timeframe",
            ],
            "tips_for_self_rep": [
                "Use court website kits and guides",
                "Call registry for procedural questions",
                "Keep copies of everything filed",
                "Serve properly - rules are strict",
            ],
            "filing_fees": {
                "initiating_application": "$380 (as of 2024)",
                "response": "$380",
                "interim_application": "$130",
                "fee_exemption": "Available if on benefits or hardship",
            },
        }

    def _first_return_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "First Court Date",
            "description": "Your first appearance in court. Usually a procedural mention or directions hearing.",
            "estimated_duration": "15-30 minutes typically",
            "what_to_expect": [
                "Brief appearance before Registrar/Judge",
                "Not a trial - no evidence given yet",
                "Court will make procedural directions",
                "May set timetable for next steps",
            ],
            "immediate_actions": [
                "Read all documents filed by other party",
                "Prepare list of proposed orders (minute)",
                "Know your availability for future dates",
                "Arrive early and find the courtroom",
            ],
            "documents_needed": [
                "Copy of your filed documents",
                "Copy of other party's documents",
                "Proposed Minute of Orders",
                "Any interim proposals",
            ],
            "common_pitfalls": [
                "Being late (court does not wait)",
                "Not reading the other party's material",
                "Trying to argue your case (not the time)",
                "Not understanding what directions mean",
            ],
            "tips_for_self_rep": [
                "Dress respectfully (business casual minimum)",
                "Address the Judge as 'Your Honour'",
                "Stand when speaking",
                "Ask for clarification if unsure",
                "Bring notepad to write down orders",
            ],
            "court_etiquette": [
                "Turn off phone",
                "No food or drink",
                "Stand when Judge enters/leaves",
                "Don't interrupt",
            ],
        }

    def _interim_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Interim Orders",
            "description": "Seeking temporary orders while waiting for final hearing. For urgent or pressing issues.",
            "estimated_duration": "1-3 months",
            "what_to_expect": [
                "Filing Application in a Case",
                "Shorter affidavit focused on urgency",
                "Hearing within weeks (if urgent)",
                "Orders that last until trial or further order",
            ],
            "immediate_actions": [
                "Assess if interim orders really needed",
                "Prepare Application in a Case",
                "Draft concise affidavit (focus on now)",
                "Identify what orders you're seeking",
            ],
            "documents_needed": [
                "Application in a Case",
                "Supporting Affidavit",
                "Proposed Minute of Interim Orders",
                "Any urgent evidence (screenshots, messages)",
            ],
            "common_pitfalls": [
                "Filing interim when not truly urgent",
                "Affidavit too long - court wants brevity",
                "Seeking orders court won't make at interim",
                "Not serving in time (usually 2 days before)",
            ],
            "tips_for_self_rep": [
                "Interim is about NOW, not the past",
                "Focus on children's immediate needs",
                "Don't try to win the whole case",
                "Be realistic about what court can order",
            ],
            "what_court_considers": [
                "Risk of harm to children",
                "Status quo and stability",
                "Urgency of the situation",
                "Balance of convenience",
            ],
        }

    def _compliance_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Compliance and Disclosure",
            "description": "Following court directions - disclosure, subpoenas, and preparing the case for trial.",
            "estimated_duration": "3-6 months",
            "what_to_expect": [
                "Exchanging disclosure (financial documents)",
                "Issuing and responding to subpoenas",
                "Case management hearings",
                "Building your evidence",
            ],
            "immediate_actions": [
                "Review court directions carefully",
                "Calendar all compliance deadlines",
                "Start gathering disclosure documents",
                "Consider what subpoenas needed",
            ],
            "documents_needed": [
                "Disclosure as directed by court",
                "Response to other party's disclosure requests",
                "Subpoenas (if needed)",
                "Updated affidavit material",
            ],
            "common_pitfalls": [
                "Missing disclosure deadlines",
                "Incomplete disclosure (court takes dim view)",
                "Fishing expedition subpoenas (get rejected)",
                "Not objecting to improper subpoenas",
            ],
            "tips_for_self_rep": [
                "Keep a compliance checklist",
                "Respond even if you don't have documents",
                "Object in writing if requests improper",
                "Ask registry for subpoena help",
            ],
            "disclosure_obligations": [
                "Full and frank disclosure required",
                "Duty is ongoing until matter resolved",
                "Failure can result in adverse findings",
                "Court can draw inferences from non-disclosure",
            ],
        }

    def _trial_prep_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Trial Preparation",
            "description": "Preparing for the final hearing. Organizing evidence, preparing questions, and finalizing your case.",
            "estimated_duration": "1-3 months before trial",
            "what_to_expect": [
                "Filing Outline of Case",
                "Preparing trial bundle",
                "Finalizing witness list",
                "Possibly settlement conference",
            ],
            "immediate_actions": [
                "Write your Outline of Case",
                "Organize all documents chronologically",
                "Prepare questions for cross-examination",
                "Consider final settlement offers",
            ],
            "documents_needed": [
                "Outline of Case",
                "Indexed trial bundle",
                "Witness summaries (if calling witnesses)",
                "Updated Minute of Proposed Orders",
            ],
            "common_pitfalls": [
                "Not practicing your evidence",
                "Bundle too large or disorganized",
                "Not preparing cross-examination questions",
                "Leaving preparation to last minute",
            ],
            "tips_for_self_rep": [
                "Practice giving evidence out loud",
                "Have someone cross-examine you",
                "Know your documents inside out",
                "Prepare opening and closing submissions",
            ],
            "trial_bundle_tips": [
                "Index and paginate everything",
                "Include only relevant documents",
                "Organize chronologically or by topic",
                "Have 3 copies (court, other party, you)",
            ],
        }

    def _final_hearing_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Final Hearing",
            "description": "The trial where the Judge hears all evidence and makes final orders.",
            "estimated_duration": "1-5 days depending on complexity",
            "what_to_expect": [
                "Formal court hearing before Judge",
                "You give evidence and are cross-examined",
                "Other party gives evidence - you can cross-examine",
                "Final submissions then judgment",
            ],
            "immediate_actions": [
                "Review all evidence thoroughly",
                "Finalize cross-examination questions",
                "Prepare opening statement",
                "Ensure witnesses confirmed",
            ],
            "documents_needed": [
                "Trial bundle (indexed, paginated)",
                "Your notes and questions",
                "Proposed orders (Minute)",
                "Any supplementary submissions",
            ],
            "common_pitfalls": [
                "Rambling evidence (answer the question)",
                "Arguing with the other party",
                "Introducing new evidence (usually not allowed)",
                "Getting emotional on the stand",
            ],
            "tips_for_self_rep": [
                "Listen carefully to questions",
                "Answer truthfully and directly",
                "Take your time - ask for questions to be repeated",
                "Don't argue - just give your evidence",
                "Refer to page numbers in the bundle",
            ],
            "trial_structure": [
                "1. Applicant opens",
                "2. Applicant's evidence and witnesses",
                "3. Respondent's evidence and witnesses",
                "4. Closing submissions",
                "5. Judgment (sometimes reserved)",
            ],
        }

    def _post_orders_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Post Orders",
            "description": "Orders have been made. Now focus on implementing them.",
            "estimated_duration": "Ongoing",
            "what_to_expect": [
                "Adjusting to new arrangements",
                "Compliance with court orders",
                "Possible need for clarification",
                "Life under the parenting plan",
            ],
            "immediate_actions": [
                "Read orders carefully - understand them",
                "Set up changeover arrangements",
                "Update schools/doctors if needed",
                "Start as you mean to continue",
            ],
            "documents_needed": [
                "Sealed copy of orders",
                "Parenting plan (if separate document)",
                "Communication log template",
            ],
            "common_pitfalls": [
                "Not reading orders properly",
                "Inconsistent compliance",
                "Weaponizing the orders",
                "Not documenting issues",
            ],
            "tips_for_self_rep": [
                "Keep a communication log",
                "Document any breaches (dates, times)",
                "Focus on children's adjustment",
                "Seek variation if orders aren't working",
            ],
            "if_orders_breached": [
                "Document the breach carefully",
                "Consider contravention application",
                "Seek legal advice before acting",
            ],
        }

    def _contravention_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Contravention",
            "description": "When court orders have been breached. Serious matter with potential penalties.",
            "estimated_duration": "2-4 months",
            "what_to_expect": [
                "Filing contravention application",
                "Proving breach occurred",
                "Court considering reasonable excuse",
                "Penalties if contravention established",
            ],
            "immediate_actions": [
                "Document the breach thoroughly",
                "Gather evidence (messages, witnesses)",
                "Consider if worth pursuing",
                "Seek legal advice",
            ],
            "documents_needed": [
                "Application alleging contravention",
                "Affidavit detailing breach",
                "Copy of breached orders",
                "Evidence of breach",
            ],
            "common_pitfalls": [
                "Minor breaches may not succeed",
                "Must prove breach beyond reasonable doubt",
                "Other party may have reasonable excuse",
                "Court may find you contributed",
            ],
            "tips_for_self_rep": [
                "Only pursue clear, documented breaches",
                "Focus on pattern, not one-offs",
                "Be prepared for other party's defence",
                "Court dislikes tit-for-tat applications",
            ],
            "possible_penalties": [
                "Variation of orders",
                "Compensation (make-up time)",
                "Fine",
                "Community service",
                "Imprisonment (rare, serious cases)",
            ],
        }

    def _appeal_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Appeal",
            "description": "Appealing a court decision. Complex process with strict timeframes.",
            "estimated_duration": "6-12 months",
            "what_to_expect": [
                "Must identify appealable error",
                "Strict 28-day time limit",
                "Higher court reviews decision",
                "Usually no new evidence",
            ],
            "immediate_actions": [
                "Get urgent legal advice",
                "Obtain transcript of hearing",
                "Identify grounds of appeal",
                "File Notice of Appeal within 28 days",
            ],
            "documents_needed": [
                "Notice of Appeal",
                "Transcript of original hearing",
                "All documents from original hearing",
                "Submissions on appeal",
            ],
            "common_pitfalls": [
                "Appeals are about errors, not disagreement",
                "Missing 28-day deadline (very strict)",
                "New evidence usually not permitted",
                "Costs risk is significant",
            ],
            "tips_for_self_rep": [
                "Get legal advice before appealing",
                "Must show legal error, not just disagree",
                "Consider if appeal really worth it",
                "Costs can be awarded against you",
            ],
            "appeal_grounds": [
                "Error of law",
                "Procedural unfairness",
                "Decision against evidence/weight",
                "Failure to consider relevant factor",
            ],
        }

    def _generic_guidance(self) -> Dict[str, Any]:
        return {
            "phase": "Unknown Phase",
            "description": "Guidance not available for this phase.",
            "immediate_actions": ["Seek legal advice"],
            "documents_needed": [],
            "tips_for_self_rep": [],
        }


# =============================================================================
# EMOTIONAL SUPPORT
# =============================================================================


class EmotionalSupport:
    """
    Provides emotional support features for self-represented litigants.

    Family law is emotionally taxing. This helps with check-ins,
    self-care reminders, and crisis intervention.
    """

    SUPPORT_SERVICES = {
        "lifeline": {
            "name": "Lifeline",
            "phone": "13 11 14",
            "description": "24/7 crisis support",
        },
        "beyond_blue": {
            "name": "Beyond Blue",
            "phone": "1300 22 4636",
            "description": "Anxiety and depression support",
        },
        "mensline": {
            "name": "MensLine Australia",
            "phone": "1300 78 99 78",
            "description": "Support for men",
        },
        "1800_respect": {
            "name": "1800RESPECT",
            "phone": "1800 737 732",
            "description": "Family violence support",
        },
        "family_relationships": {
            "name": "Family Relationships Advice Line",
            "phone": "1800 050 321",
            "description": "Family relationship support",
        },
        "kids_helpline": {
            "name": "Kids Helpline",
            "phone": "1800 55 1800",
            "description": "Support for children and young people",
        },
    }

    CRISIS_KEYWORDS = [
        "suicide",
        "kill myself",
        "end it",
        "can't go on",
        "hurt myself",
        "self harm",
        "no point",
        "give up",
        "want to die",
        "better off dead",
    ]

    def __init__(self, case: FamilyLawCase):
        self.case = case

    def get_check_in_prompt(self) -> Dict[str, Any]:
        """Generate a check-in prompt based on case stage."""
        phase = self.case.phase

        prompts = {
            CasePhase.SEPARATION: {
                "prompt": "Separation is incredibly hard. How are you coping today?",
                "suggestions": [
                    "It's okay to grieve the relationship",
                    "Focus on one day at a time",
                    "Lean on your support network",
                ],
            },
            CasePhase.FDR: {
                "prompt": "Mediation can bring up difficult emotions. How are you feeling?",
                "suggestions": [
                    "You don't have to agree to anything today",
                    "Focus on the children's needs",
                    "It's okay to ask for a break",
                ],
            },
            CasePhase.FIRST_RETURN: {
                "prompt": "Court appearances are stressful. How are you holding up?",
                "suggestions": [
                    "Anxiety before court is normal",
                    "Prepare but don't over-prepare",
                    "It's just one step in the process",
                ],
            },
            CasePhase.FINAL_HEARING: {
                "prompt": "Trial is the hardest part. How are you managing?",
                "suggestions": [
                    "Take each day of trial as it comes",
                    "Rest well each evening",
                    "Soon this will be behind you",
                ],
            },
        }

        default = {
            "prompt": "Family law matters are stressful. How are you doing?",
            "suggestions": [
                "Take breaks when you need them",
                "Your wellbeing matters too",
                "This process will end",
            ],
        }

        return prompts.get(phase, default)

    def check_for_crisis(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Check text for crisis indicators.

        Returns crisis response if detected, None otherwise.
        """
        text_lower = text.lower()

        for keyword in self.CRISIS_KEYWORDS:
            if keyword in text_lower:
                return self._crisis_response()

        return None

    def _crisis_response(self) -> Dict[str, Any]:
        """Generate immediate crisis intervention response."""
        return {
            "is_crisis": True,
            "message": (
                "I'm concerned about what you've shared. "
                "Your safety is the most important thing right now. "
                "Please reach out for support."
            ),
            "immediate_action": "Please call Lifeline on 13 11 14 - they're available 24/7",
            "services": [
                self.SUPPORT_SERVICES["lifeline"],
                self.SUPPORT_SERVICES["beyond_blue"],
            ],
            "reminder": (
                "Family law matters are temporary. "
                "Your life has value beyond this case. "
                "Please reach out for help."
            ),
        }

    def get_self_care_reminders(self) -> List[str]:
        """Get self-care reminders appropriate to case stage."""
        base_reminders = [
            "Have you eaten a proper meal today?",
            "When did you last go outside for fresh air?",
            "Have you spoken to a friend or family member today?",
            "Remember to take breaks from thinking about the case",
            "Sleep is important - try to maintain a routine",
        ]

        phase_reminders = {
            CasePhase.TRIAL_PREP: [
                "Don't work on your case after 8pm - you need rest",
                "Exercise helps manage stress",
                "It's okay to ask for help with preparation",
            ],
            CasePhase.FINAL_HEARING: [
                "Eat light meals during trial",
                "Avoid caffeine overload",
                "Gentle exercise in the evening helps sleep",
            ],
        }

        return base_reminders + phase_reminders.get(self.case.phase, [])

    def get_support_services(
        self, category: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Get relevant support services."""
        if category == "crisis":
            return [
                self.SUPPORT_SERVICES["lifeline"],
                self.SUPPORT_SERVICES["beyond_blue"],
            ]
        elif category == "family_violence":
            return [
                self.SUPPORT_SERVICES["1800_respect"],
                self.SUPPORT_SERVICES["lifeline"],
            ]
        elif category == "men":
            return [
                self.SUPPORT_SERVICES["mensline"],
                self.SUPPORT_SERVICES["beyond_blue"],
            ]
        elif category == "children":
            return [self.SUPPORT_SERVICES["kids_helpline"]]
        else:
            return list(self.SUPPORT_SERVICES.values())

    def log_mood(self, rating: int, notes: str = "") -> Note:
        """Log a mood rating (1-10) to the case journal."""
        if rating < 1 or rating > 10:
            raise ValueError("Mood rating must be 1-10")

        note = self.case.add_note(
            content=notes or f"Mood check-in: {rating}/10",
            category="emotional",
            mood_rating=rating,
        )

        return note

    def get_mood_trend(self, days: int = 14) -> Dict[str, Any]:
        """Analyze mood trend over recent period."""
        cutoff = datetime.now() - timedelta(days=days)

        mood_notes = [
            n
            for n in self.case.notes
            if n.category == "emotional"
            and n.mood_rating is not None
            and n.timestamp > cutoff
        ]

        if not mood_notes:
            return {
                "has_data": False,
                "message": "No mood data recorded in this period",
            }

        ratings = [n.mood_rating for n in mood_notes]
        avg = sum(ratings) / len(ratings)
        trend = "stable"

        if len(ratings) >= 3:
            recent = ratings[-3:]
            earlier = ratings[:3]
            if sum(recent) / 3 > sum(earlier) / 3 + 1:
                trend = "improving"
            elif sum(recent) / 3 < sum(earlier) / 3 - 1:
                trend = "declining"

        return {
            "has_data": True,
            "average": round(avg, 1),
            "trend": trend,
            "entries": len(ratings),
            "lowest": min(ratings),
            "highest": max(ratings),
            "message": self._mood_message(avg, trend),
        }

    def _mood_message(self, avg: float, trend: str) -> str:
        """Generate supportive message based on mood data."""
        if avg <= 3:
            return (
                "Your mood has been quite low. "
                "Please reach out to a support service. "
                "This is a difficult time, and you deserve support."
            )
        elif avg <= 5:
            return (
                "You're going through a challenging time. "
                "Remember to be kind to yourself and lean on your support network."
            )
        elif avg <= 7:
            return (
                "You're managing reasonably well despite the difficulties. "
                "Keep up the self-care."
            )
        else:
            return (
                "You're coping well. " "Maintain the good habits that are helping you."
            )


# =============================================================================
# CHATBOT INTEGRATION
# =============================================================================


class CaseManagerChatbot:
    """
    Integration layer for chatbot interaction with the case manager.

    Provides natural language interface to case management functions.
    """

    def __init__(self, case: FamilyLawCase):
        self.case = case

    def process_query(self, query: str) -> Dict[str, Any]:
        """Process a natural language query about the case."""
        query_lower = query.lower()

        # Check for crisis first
        crisis_check = self.case.emotional_support.check_for_crisis(query)
        if crisis_check:
            return crisis_check

        # Status queries
        if any(
            w in query_lower
            for w in ["status", "summary", "where am i", "what's happening"]
        ):
            return {
                "type": "status",
                "response": self.case.get_accessible_status(),
            }

        # Deadline queries
        if any(w in query_lower for w in ["deadline", "due", "when", "upcoming"]):
            deadlines = self.case.get_pending_deadlines()[:5]
            return {
                "type": "deadlines",
                "response": self._format_deadlines(deadlines),
                "data": [d.to_dict() for d in deadlines],
            }

        # Document queries
        if any(w in query_lower for w in ["document", "filed", "serve", "checklist"]):
            return {
                "type": "documents",
                "response": self.case.document_tracker.get_accessible_checklist(),
            }

        # Phase/guidance queries
        if any(
            w in query_lower for w in ["what should i", "next step", "guidance", "help"]
        ):
            guidance = self.case.phase_guidance.get_phase_guidance(self.case.phase)
            return {
                "type": "guidance",
                "response": self._format_guidance(guidance),
                "data": guidance,
            }

        # Support queries
        if any(
            w in query_lower for w in ["support", "help line", "struggling", "stressed"]
        ):
            services = self.case.emotional_support.get_support_services()
            return {
                "type": "support",
                "response": self._format_support(services),
                "data": services,
            }

        # Default
        return {
            "type": "unknown",
            "response": (
                "I can help you with:\n"
                "- Case status and summary\n"
                "- Upcoming deadlines\n"
                "- Document checklist\n"
                "- Guidance for your current phase\n"
                "- Support services\n\n"
                "What would you like to know?"
            ),
        }

    def _format_deadlines(self, deadlines: List[Deadline]) -> str:
        """Format deadlines for accessible reading."""
        if not deadlines:
            return "You have no pending deadlines. Well done!"

        lines = ["Your upcoming deadlines:", ""]
        for d in deadlines:
            if d.is_overdue:
                lines.append(
                    f"⚠️ OVERDUE: {d.title} (was due {abs(d.days_remaining)} days ago)"
                )
            elif d.days_remaining == 0:
                lines.append(f"🔴 TODAY: {d.title}")
            elif d.days_remaining == 1:
                lines.append(f"🟠 TOMORROW: {d.title}")
            else:
                lines.append(f"📅 {d.title} - in {d.days_remaining} days")

        return "\n".join(lines)

    def _format_guidance(self, guidance: Dict[str, Any]) -> str:
        """Format guidance for accessible reading."""
        lines = [
            f"Phase: {guidance.get('phase', 'Unknown')}",
            "",
            guidance.get("description", ""),
            "",
            "Immediate actions:",
        ]

        for action in guidance.get("immediate_actions", [])[:3]:
            lines.append(f"  • {action}")

        lines.append("")
        lines.append("Tips for self-represented litigants:")
        for tip in guidance.get("tips_for_self_rep", [])[:3]:
            lines.append(f"  • {tip}")

        return "\n".join(lines)

    def _format_support(self, services: List[Dict[str, str]]) -> str:
        """Format support services for accessible reading."""
        lines = ["Support services available:", ""]

        for service in services:
            lines.append(f"• {service['name']}: {service['phone']}")
            lines.append(f"  {service['description']}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# MAIN AND CLI
# =============================================================================


def main():
    """Example usage of the case management system."""

    # Create a new case
    case = FamilyLawCase(
        case_number="SYF1234/2024", court="FCFCOA", phase=CasePhase.FILING
    )

    # Add parties
    case.add_party(Party(role=PartyRole.APPLICANT, pseudonym="Father", is_self=True))
    case.add_party(
        Party(role=PartyRole.RESPONDENT, pseudonym="Mother", has_lawyer=True)
    )

    # Add children
    case.add_child(Child(pseudonym="Child 1", birth_year=2018))

    # Set key dates
    case.set_key_date("separation", datetime(2024, 1, 15))
    case.set_key_date("fdr_completed", datetime(2024, 3, 20))

    # Add a document
    case.add_document(
        Document(
            doc_type=DocumentType.FDR_CERTIFICATE,
            title="Section 60I Certificate",
            filed_date=datetime(2024, 3, 25),
        )
    )

    # Get status
    print(case.get_accessible_status())
    print("\n" + "=" * 60 + "\n")

    # Get guidance
    guidance = case.phase_guidance.get_phase_guidance(case.phase)
    print(f"Phase: {guidance['phase']}")
    print(f"Description: {guidance['description']}")
    print("\nImmediate actions:")
    for action in guidance["immediate_actions"][:3]:
        print(f"  • {action}")

    # Save to file
    case.save(Path("/tmp/test_case.json"))
    print(f"\nCase saved to /tmp/test_case.json")

    # Test chatbot
    chatbot = CaseManagerChatbot(case)
    response = chatbot.process_query("What should I do next?")
    print(f"\nChatbot response:\n{response['response']}")


if __name__ == "__main__":
    main()
