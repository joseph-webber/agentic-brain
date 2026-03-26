#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 59: Strata/Body Corporate Assistant

A system for managing strata schemes (body corporate) including owner
communication, levy management, meetings, and common property maintenance.

Features:
- Owner communication portal
- Levy tracking and arrears
- Meeting scheduling and minutes
- By-law management
- Common area maintenance
- Building fund tracking
- AGM preparation
- Document management

Australian-specific:
- Strata Schemes Management Act compliance
- State-specific terminology (Strata/Body Corporate/Owners Corporation)
- Sinking fund vs capital works fund
- State-based strata legislation

Usage:
    python examples/59_strata_manager.py

Requirements:
    pip install agentic-brain

Author: agentic-brain
License: MIT
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
import random
import string

# ══════════════════════════════════════════════════════════════════════════════
# AUSTRALIAN STATE CONFIGURATIONS
# ══════════════════════════════════════════════════════════════════════════════


class AustralianState(Enum):
    """Australian states and territories."""

    NSW = "New South Wales"
    VIC = "Victoria"
    QLD = "Queensland"
    SA = "South Australia"
    WA = "Western Australia"
    TAS = "Tasmania"
    NT = "Northern Territory"
    ACT = "Australian Capital Territory"


@dataclass
class StrataTerminology:
    """State-specific strata terminology."""

    state: AustralianState
    scheme_name: str  # "Strata Plan", "Body Corporate", "Owners Corporation"
    owner_group: str  # "Owners Corporation", "Body Corporate", "Community Association"
    admin_fund: str  # "Administrative Fund", "General Fund"
    capital_fund: str  # "Capital Works Fund", "Sinking Fund", "Reserve Fund"
    manager_title: str  # "Strata Manager", "Body Corporate Manager"

    @classmethod
    def get_terminology(cls, state: AustralianState) -> "StrataTerminology":
        """Get terminology for a specific state."""
        terms = {
            AustralianState.NSW: cls(
                state=AustralianState.NSW,
                scheme_name="Strata Plan",
                owner_group="Owners Corporation",
                admin_fund="Administrative Fund",
                capital_fund="Capital Works Fund",
                manager_title="Strata Manager",
            ),
            AustralianState.VIC: cls(
                state=AustralianState.VIC,
                scheme_name="Owners Corporation",
                owner_group="Owners Corporation",
                admin_fund="Administrative Fund",
                capital_fund="Maintenance Fund",
                manager_title="Owners Corporation Manager",
            ),
            AustralianState.QLD: cls(
                state=AustralianState.QLD,
                scheme_name="Community Titles Scheme",
                owner_group="Body Corporate",
                admin_fund="Administrative Fund",
                capital_fund="Sinking Fund",
                manager_title="Body Corporate Manager",
            ),
            AustralianState.SA: cls(
                state=AustralianState.SA,
                scheme_name="Strata Plan",
                owner_group="Strata Corporation",
                admin_fund="Administrative Fund",
                capital_fund="Sinking Fund",
                manager_title="Strata Manager",
            ),
            AustralianState.WA: cls(
                state=AustralianState.WA,
                scheme_name="Strata Titles Scheme",
                owner_group="Strata Company",
                admin_fund="Administrative Fund",
                capital_fund="Reserve Fund",
                manager_title="Strata Manager",
            ),
        }
        return terms.get(state, terms[AustralianState.NSW])


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════


class LotType(Enum):
    """Types of lots in a strata scheme."""

    RESIDENTIAL = "Residential"
    COMMERCIAL = "Commercial"
    RETAIL = "Retail"
    PARKING = "Parking"
    STORAGE = "Storage"


class LevyStatus(Enum):
    """Status of levy payments."""

    PAID = "Paid"
    DUE = "Due"
    OVERDUE = "Overdue"
    PARTIAL = "Partially Paid"
    ARRANGEMENT = "Payment Arrangement"


class MeetingType(Enum):
    """Types of strata meetings."""

    AGM = "Annual General Meeting"
    EGM = "Extraordinary General Meeting"
    COMMITTEE = "Committee Meeting"
    INFORMAL = "Informal Meeting"


class MotionStatus(Enum):
    """Status of meeting motions."""

    PROPOSED = "Proposed"
    CARRIED = "Carried"
    DEFEATED = "Defeated"
    WITHDRAWN = "Withdrawn"
    DEFERRED = "Deferred"


class ResolutionType(Enum):
    """Types of resolutions."""

    ORDINARY = "Ordinary Resolution"
    SPECIAL = "Special Resolution"
    UNANIMOUS = "Unanimous Resolution"


class ByLawCategory(Enum):
    """Categories of by-laws."""

    NOISE = "Noise & Nuisance"
    PETS = "Keeping of Animals"
    PARKING = "Parking"
    RENOVATIONS = "Renovations & Alterations"
    APPEARANCE = "Appearance of Lot"
    COMMON_PROPERTY = "Use of Common Property"
    BEHAVIOUR = "Behaviour of Occupants"
    MAINTENANCE = "Maintenance Obligations"
    SAFETY = "Safety & Security"
    OTHER = "Other"


class MaintenanceCategory(Enum):
    """Categories for common property maintenance."""

    BUILDING = "Building Exterior"
    ROOF = "Roof"
    LIFT = "Lifts/Elevators"
    POOL = "Pool/Spa"
    GYM = "Gym Equipment"
    GARDEN = "Gardens & Landscaping"
    CARPARK = "Car Park"
    LIGHTING = "Common Lighting"
    INTERCOM = "Intercom/Security"
    PLUMBING = "Common Plumbing"
    ELECTRICAL = "Common Electrical"
    FIRE_SAFETY = "Fire Safety Equipment"
    CLEANING = "Cleaning"
    OTHER = "Other"


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class StrataScheme:
    """Represents a strata scheme/body corporate."""

    scheme_id: str
    name: str  # e.g., "SP12345" or "Harbour View Apartments"
    address: str
    state: AustralianState

    # Scheme details
    total_lots: int
    total_unit_entitlements: int
    year_established: int

    # Financial year
    financial_year_end: str  # "30 June" or "31 December"

    # Management
    manager_name: str
    manager_email: str
    manager_phone: str

    # Funds
    admin_fund_balance: Decimal = Decimal("0")
    capital_fund_balance: Decimal = Decimal("0")

    @property
    def terminology(self) -> StrataTerminology:
        return StrataTerminology.get_terminology(self.state)


@dataclass
class Lot:
    """Represents a lot (unit) in the strata scheme."""

    lot_number: int
    lot_type: LotType
    unit_entitlement: int

    # Owner details
    owner_name: str
    owner_email: str
    owner_phone: str
    owner_postal_address: str

    # Occupancy
    is_owner_occupied: bool = True
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None

    # Committee role
    committee_role: Optional[str] = None  # "Chair", "Secretary", "Treasurer", "Member"

    # Levies
    quarterly_admin_levy: Decimal = Decimal("0")
    quarterly_capital_levy: Decimal = Decimal("0")

    @property
    def total_quarterly_levy(self) -> Decimal:
        return self.quarterly_admin_levy + self.quarterly_capital_levy


@dataclass
class LevyNotice:
    """A levy notice issued to a lot owner."""

    notice_id: str
    lot_number: int
    quarter: str  # "Q1 2026", "Q2 2026", etc.
    issue_date: date
    due_date: date

    # Amounts
    admin_levy: Decimal
    capital_levy: Decimal
    special_levy: Decimal = Decimal("0")
    arrears: Decimal = Decimal("0")
    interest: Decimal = Decimal("0")

    # Payment
    amount_paid: Decimal = Decimal("0")
    status: LevyStatus = LevyStatus.DUE

    @property
    def total_amount(self) -> Decimal:
        return (
            self.admin_levy
            + self.capital_levy
            + self.special_levy
            + self.arrears
            + self.interest
        )

    @property
    def balance_owing(self) -> Decimal:
        return self.total_amount - self.amount_paid


@dataclass
class Meeting:
    """A strata meeting."""

    meeting_id: str
    meeting_type: MeetingType
    scheduled_date: datetime
    location: str

    # Agenda
    agenda_items: list[str] = field(default_factory=list)

    # Attendance
    quorum_required: int = 0
    lots_represented: list[int] = field(default_factory=list)
    proxies_received: list[dict] = field(default_factory=list)

    # Status
    completed: bool = False
    minutes_approved: bool = False

    # Documents
    notice_sent_date: Optional[date] = None
    agenda_document: Optional[str] = None
    minutes_document: Optional[str] = None


@dataclass
class Motion:
    """A motion proposed at a meeting."""

    motion_id: str
    meeting_id: str
    motion_number: int

    # Motion details
    title: str
    description: str
    resolution_type: ResolutionType
    moved_by: int  # Lot number
    seconded_by: Optional[int] = None

    # Voting
    votes_for: int = 0
    votes_against: int = 0
    abstentions: int = 0

    # Status
    status: MotionStatus = MotionStatus.PROPOSED

    @property
    def is_carried(self) -> bool:
        if self.resolution_type == ResolutionType.ORDINARY:
            return self.votes_for > self.votes_against
        elif self.resolution_type == ResolutionType.SPECIAL:
            total = self.votes_for + self.votes_against
            return total > 0 and (self.votes_for / total) >= 0.75
        else:  # Unanimous
            return self.votes_against == 0


@dataclass
class ByLaw:
    """A strata by-law."""

    bylaw_id: str
    number: int  # By-law number
    title: str
    category: ByLawCategory
    content: str

    # Status
    adopted_date: date
    last_amended: Optional[date] = None
    is_active: bool = True

    # Registration
    registered: bool = False
    registration_date: Optional[date] = None


@dataclass
class ByLawBreach:
    """A reported by-law breach."""

    breach_id: str
    bylaw_id: str
    lot_number: int
    reported_date: date

    # Details
    description: str
    reported_by: Optional[int] = None  # Lot number of reporter

    # Resolution
    resolved: bool = False
    resolution_date: Optional[date] = None
    resolution_notes: str = ""

    # Notices
    warning_sent: bool = False
    notice_to_comply_sent: bool = False
    ncat_lodged: bool = False  # NSW Civil & Administrative Tribunal


@dataclass
class MaintenanceWork:
    """Common property maintenance work."""

    work_id: str
    category: MaintenanceCategory
    description: str

    # Financials
    estimated_cost: Decimal
    actual_cost: Optional[Decimal] = None
    fund_source: str = "administrative"  # "administrative" or "capital"

    # Status
    status: str = "planned"  # planned, approved, in_progress, completed
    requires_approval: bool = False
    approved_at_meeting: Optional[str] = None

    # Scheduling
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    contractor: str = ""


@dataclass
class Document:
    """A strata document."""

    document_id: str
    title: str
    category: str  # "minutes", "financials", "bylaws", "insurance", etc.
    filename: str
    upload_date: date
    description: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# STRATA MANAGER
# ══════════════════════════════════════════════════════════════════════════════


class StrataManager:
    """Manages a strata scheme / body corporate."""

    def __init__(self, scheme: StrataScheme):
        """Initialize the strata manager."""
        self.scheme = scheme
        self.terminology = scheme.terminology

        # Data stores
        self.lots: dict[int, Lot] = {}
        self.levy_notices: list[LevyNotice] = []
        self.meetings: list[Meeting] = []
        self.motions: list[Motion] = []
        self.bylaws: list[ByLaw] = []
        self.breaches: list[ByLawBreach] = []
        self.maintenance: list[MaintenanceWork] = []
        self.documents: list[Document] = []

        # Communication log
        self.communications: list[dict] = []

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        random_part = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        return f"{prefix}-{random_part}"

    # ─────────────────────────────────────────────────────────────────────────
    # LOT MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def add_lot(self, lot: Lot) -> int:
        """Add a lot to the scheme."""
        self.lots[lot.lot_number] = lot
        print(f"✅ Added Lot {lot.lot_number}: {lot.owner_name}")
        return lot.lot_number

    def get_lot(self, lot_number: int) -> Optional[Lot]:
        """Get lot by number."""
        return self.lots.get(lot_number)

    def get_committee_members(self) -> list[Lot]:
        """Get all committee members."""
        return [lot for lot in self.lots.values() if lot.committee_role]

    def calculate_entitlement_percentage(self, lot_number: int) -> float:
        """Calculate a lot's percentage of total entitlements."""
        lot = self.lots.get(lot_number)
        if not lot:
            return 0.0
        return (lot.unit_entitlement / self.scheme.total_unit_entitlements) * 100

    def get_roll(self) -> list[dict]:
        """Get the strata roll (list of all owners)."""
        roll = []
        for lot in sorted(self.lots.values(), key=lambda x: x.lot_number):
            roll.append(
                {
                    "lot_number": lot.lot_number,
                    "lot_type": lot.lot_type.value,
                    "unit_entitlement": lot.unit_entitlement,
                    "owner_name": lot.owner_name,
                    "owner_email": lot.owner_email,
                    "is_owner_occupied": lot.is_owner_occupied,
                    "committee_role": lot.committee_role,
                }
            )
        return roll

    # ─────────────────────────────────────────────────────────────────────────
    # LEVY MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def raise_levies(self, quarter: str, due_date: date) -> int:
        """Raise levy notices for all lots."""
        notices_raised = 0

        for lot in self.lots.values():
            notice = LevyNotice(
                notice_id=self._generate_id("LEV"),
                lot_number=lot.lot_number,
                quarter=quarter,
                issue_date=date.today(),
                due_date=due_date,
                admin_levy=lot.quarterly_admin_levy,
                capital_levy=lot.quarterly_capital_levy,
            )

            self.levy_notices.append(notice)
            notices_raised += 1

        print(f"✅ Raised {notices_raised} levy notices for {quarter}")
        return notices_raised

    def record_levy_payment(
        self,
        lot_number: int,
        amount: Decimal,
        payment_date: date,
        reference: str = "",
    ) -> bool:
        """Record a levy payment."""
        # Find most recent unpaid notice for this lot
        lot_notices = [
            n
            for n in self.levy_notices
            if n.lot_number == lot_number and n.status != LevyStatus.PAID
        ]

        if not lot_notices:
            return False

        notice = sorted(lot_notices, key=lambda x: x.due_date)[0]
        notice.amount_paid += amount

        if notice.amount_paid >= notice.total_amount:
            notice.status = LevyStatus.PAID
        elif notice.amount_paid > 0:
            notice.status = LevyStatus.PARTIAL

        print(f"✅ Payment of ${amount} recorded for Lot {lot_number}")
        return True

    def get_arrears_report(self) -> list[dict]:
        """Get report of all lots in arrears."""
        arrears = []

        for lot_number, lot in self.lots.items():
            lot_notices = [
                n
                for n in self.levy_notices
                if n.lot_number == lot_number
                and n.status in [LevyStatus.OVERDUE, LevyStatus.PARTIAL]
            ]

            if lot_notices:
                total_arrears = sum(n.balance_owing for n in lot_notices)
                oldest = min(n.due_date for n in lot_notices)
                days_overdue = (date.today() - oldest).days

                arrears.append(
                    {
                        "lot_number": lot_number,
                        "owner_name": lot.owner_name,
                        "total_arrears": float(total_arrears),
                        "days_overdue": days_overdue,
                        "notices_outstanding": len(lot_notices),
                    }
                )

        return sorted(arrears, key=lambda x: x["total_arrears"], reverse=True)

    def issue_arrears_notice(
        self, lot_number: int, notice_type: str = "reminder"
    ) -> dict:
        """Issue arrears notice to a lot owner."""
        lot = self.lots.get(lot_number)
        if not lot:
            return {"error": "Lot not found"}

        notice_types = {
            "reminder": "Friendly Reminder",
            "first": "First Notice",
            "final": "Final Notice - Legal Action Warning",
            "debt_recovery": "Debt Recovery Notice",
        }

        result = {
            "lot_number": lot_number,
            "owner": lot.owner_name,
            "notice_type": notice_types.get(notice_type, "Reminder"),
            "sent_to": lot.owner_email,
            "date": date.today().isoformat(),
        }

        self.communications.append(
            {
                "type": "arrears_notice",
                "lot_number": lot_number,
                "notice_type": notice_type,
                "date": datetime.now().isoformat(),
            }
        )

        print(f"📤 Arrears notice sent to Lot {lot_number}")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # MEETING MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def schedule_meeting(
        self,
        meeting_type: MeetingType,
        scheduled_date: datetime,
        location: str,
        agenda_items: list[str],
    ) -> str:
        """Schedule a meeting."""
        meeting = Meeting(
            meeting_id=self._generate_id("MTG"),
            meeting_type=meeting_type,
            scheduled_date=scheduled_date,
            location=location,
            agenda_items=agenda_items,
        )

        # Calculate quorum (usually 25% of lots for most states)
        meeting.quorum_required = max(2, len(self.lots) // 4)

        self.meetings.append(meeting)

        print(f"✅ Scheduled {meeting_type.value}")
        print(f"   Date: {scheduled_date.strftime('%d %B %Y at %I:%M %p')}")
        print(f"   Location: {location}")
        print(f"   Quorum required: {meeting.quorum_required} lots")

        return meeting.meeting_id

    def send_meeting_notice(self, meeting_id: str) -> int:
        """Send meeting notices to all owners."""
        meeting = None
        for m in self.meetings:
            if m.meeting_id == meeting_id:
                meeting = m
                break

        if not meeting:
            return 0

        meeting.notice_sent_date = date.today()

        notices_sent = 0
        for lot in self.lots.values():
            # In production, send actual email
            self.communications.append(
                {
                    "type": "meeting_notice",
                    "meeting_id": meeting_id,
                    "lot_number": lot.lot_number,
                    "email": lot.owner_email,
                    "date": datetime.now().isoformat(),
                }
            )
            notices_sent += 1

        print(f"📤 Meeting notices sent to {notices_sent} owners")
        return notices_sent

    def record_attendance(
        self, meeting_id: str, lot_number: int, proxy: bool = False
    ) -> bool:
        """Record attendance at a meeting."""
        for meeting in self.meetings:
            if meeting.meeting_id == meeting_id:
                if lot_number not in meeting.lots_represented:
                    meeting.lots_represented.append(lot_number)
                    if proxy:
                        meeting.proxies_received.append({"lot": lot_number})
                return True
        return False

    def check_quorum(self, meeting_id: str) -> dict:
        """Check if meeting has quorum."""
        for meeting in self.meetings:
            if meeting.meeting_id == meeting_id:
                present = len(meeting.lots_represented)
                has_quorum = present >= meeting.quorum_required

                return {
                    "meeting_id": meeting_id,
                    "lots_present": present,
                    "quorum_required": meeting.quorum_required,
                    "has_quorum": has_quorum,
                    "proxies": len(meeting.proxies_received),
                }
        return {"error": "Meeting not found"}

    def add_motion(
        self,
        meeting_id: str,
        title: str,
        description: str,
        resolution_type: ResolutionType,
        moved_by: int,
        seconded_by: Optional[int] = None,
    ) -> str:
        """Add a motion to a meeting."""
        # Get next motion number for this meeting
        existing = [m for m in self.motions if m.meeting_id == meeting_id]
        motion_number = len(existing) + 1

        motion = Motion(
            motion_id=self._generate_id("MOT"),
            meeting_id=meeting_id,
            motion_number=motion_number,
            title=title,
            description=description,
            resolution_type=resolution_type,
            moved_by=moved_by,
            seconded_by=seconded_by,
        )

        self.motions.append(motion)

        print(f"📋 Motion {motion_number} added: {title}")
        return motion.motion_id

    def record_vote(
        self,
        motion_id: str,
        votes_for: int,
        votes_against: int,
        abstentions: int = 0,
    ) -> dict:
        """Record vote on a motion."""
        for motion in self.motions:
            if motion.motion_id == motion_id:
                motion.votes_for = votes_for
                motion.votes_against = votes_against
                motion.abstentions = abstentions

                motion.status = (
                    MotionStatus.CARRIED if motion.is_carried else MotionStatus.DEFEATED
                )

                return {
                    "motion_id": motion_id,
                    "title": motion.title,
                    "votes_for": votes_for,
                    "votes_against": votes_against,
                    "abstentions": abstentions,
                    "status": motion.status.value,
                }
        return {"error": "Motion not found"}

    # ─────────────────────────────────────────────────────────────────────────
    # BY-LAW MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def add_bylaw(self, bylaw: ByLaw) -> str:
        """Add a by-law to the scheme."""
        self.bylaws.append(bylaw)
        print(f"✅ Added By-law {bylaw.number}: {bylaw.title}")
        return bylaw.bylaw_id

    def get_bylaws(self, category: Optional[ByLawCategory] = None) -> list[ByLaw]:
        """Get by-laws, optionally filtered by category."""
        if category:
            return [b for b in self.bylaws if b.category == category and b.is_active]
        return [b for b in self.bylaws if b.is_active]

    def report_breach(
        self,
        bylaw_number: int,
        lot_number: int,
        description: str,
        reported_by: Optional[int] = None,
    ) -> str:
        """Report a by-law breach."""
        # Find the by-law
        bylaw = None
        for b in self.bylaws:
            if b.number == bylaw_number:
                bylaw = b
                break

        if not bylaw:
            raise ValueError(f"By-law {bylaw_number} not found")

        breach = ByLawBreach(
            breach_id=self._generate_id("BRH"),
            bylaw_id=bylaw.bylaw_id,
            lot_number=lot_number,
            reported_date=date.today(),
            description=description,
            reported_by=reported_by,
        )

        self.breaches.append(breach)

        print(f"⚠️ By-law breach reported: {breach.breach_id}")
        print(f"   By-law: {bylaw.title}")
        print(f"   Lot: {lot_number}")

        return breach.breach_id

    def issue_breach_notice(self, breach_id: str, notice_type: str = "warning") -> bool:
        """Issue a breach notice."""
        for breach in self.breaches:
            if breach.breach_id == breach_id:
                if notice_type == "warning":
                    breach.warning_sent = True
                elif notice_type == "notice_to_comply":
                    breach.notice_to_comply_sent = True

                lot = self.lots.get(breach.lot_number)
                if lot:
                    self.communications.append(
                        {
                            "type": f"breach_{notice_type}",
                            "breach_id": breach_id,
                            "lot_number": breach.lot_number,
                            "email": lot.owner_email,
                            "date": datetime.now().isoformat(),
                        }
                    )

                print(f"📤 Breach {notice_type} sent for {breach_id}")
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # COMMON PROPERTY MAINTENANCE
    # ─────────────────────────────────────────────────────────────────────────

    def create_maintenance_work(
        self,
        category: MaintenanceCategory,
        description: str,
        estimated_cost: Decimal,
        fund_source: str = "administrative",
        requires_approval: bool = False,
    ) -> str:
        """Create a maintenance work order."""
        work = MaintenanceWork(
            work_id=self._generate_id("MNT"),
            category=category,
            description=description,
            estimated_cost=estimated_cost,
            fund_source=fund_source,
            requires_approval=requires_approval,
        )

        self.maintenance.append(work)

        print(f"✅ Created maintenance work: {work.work_id}")
        print(f"   Category: {category.value}")
        print(f"   Estimated: ${estimated_cost}")

        return work.work_id

    def approve_maintenance(self, work_id: str, meeting_id: str) -> bool:
        """Approve maintenance work at a meeting."""
        for work in self.maintenance:
            if work.work_id == work_id:
                work.status = "approved"
                work.approved_at_meeting = meeting_id
                print(f"✅ Maintenance approved: {work_id}")
                return True
        return False

    def complete_maintenance(
        self,
        work_id: str,
        actual_cost: Decimal,
        contractor: str,
    ) -> bool:
        """Mark maintenance as complete."""
        for work in self.maintenance:
            if work.work_id == work_id:
                work.status = "completed"
                work.actual_cost = actual_cost
                work.completed_date = date.today()
                work.contractor = contractor

                # Deduct from appropriate fund
                if work.fund_source == "administrative":
                    self.scheme.admin_fund_balance -= actual_cost
                else:
                    self.scheme.capital_fund_balance -= actual_cost

                print(f"✅ Maintenance completed: {work_id}")
                print(f"   Cost: ${actual_cost}")
                return True
        return False

    def get_maintenance_summary(self) -> dict:
        """Get summary of maintenance works."""
        planned = [w for w in self.maintenance if w.status == "planned"]
        approved = [w for w in self.maintenance if w.status == "approved"]
        in_progress = [w for w in self.maintenance if w.status == "in_progress"]
        completed = [w for w in self.maintenance if w.status == "completed"]

        return {
            "planned": len(planned),
            "approved": len(approved),
            "in_progress": len(in_progress),
            "completed": len(completed),
            "total_planned_cost": float(
                sum(w.estimated_cost for w in planned + approved)
            ),
            "total_spent_ytd": float(
                sum(w.actual_cost or Decimal("0") for w in completed)
            ),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # FINANCIAL REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    def get_financial_summary(self) -> dict:
        """Get financial summary of the scheme."""
        # Calculate total levies raised this FY
        fy_start = date(
            date.today().year if date.today().month >= 7 else date.today().year - 1,
            7,
            1,
        )

        fy_notices = [n for n in self.levy_notices if n.issue_date >= fy_start]
        total_raised = sum(n.total_amount for n in fy_notices)
        total_collected = sum(n.amount_paid for n in fy_notices)

        arrears = self.get_arrears_report()
        total_arrears = sum(a["total_arrears"] for a in arrears)

        return {
            "admin_fund_balance": float(self.scheme.admin_fund_balance),
            "capital_fund_balance": float(self.scheme.capital_fund_balance),
            "total_fund_balance": float(
                self.scheme.admin_fund_balance + self.scheme.capital_fund_balance
            ),
            "levies_raised_ytd": float(total_raised),
            "levies_collected_ytd": float(total_collected),
            "collection_rate": (
                f"{(total_collected/total_raised*100):.1f}%"
                if total_raised > 0
                else "N/A"
            ),
            "total_arrears": float(total_arrears),
            "lots_in_arrears": len(arrears),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # AGM PREPARATION
    # ─────────────────────────────────────────────────────────────────────────

    def prepare_agm(self, agm_date: datetime, location: str) -> dict:
        """Prepare materials for AGM."""
        # Standard AGM agenda items
        agenda = [
            "Confirmation of minutes of previous AGM",
            f"Presentation of {self.terminology.owner_group} financial statements",
            f"Approval of {self.terminology.admin_fund} budget",
            f"Approval of {self.terminology.capital_fund} budget",
            "Election of committee members",
            "Appointment of auditor (if applicable)",
            "Consideration of motions submitted",
            "General business",
        ]

        meeting_id = self.schedule_meeting(
            meeting_type=MeetingType.AGM,
            scheduled_date=agm_date,
            location=location,
            agenda_items=agenda,
        )

        # Calculate required notice period (usually 14 days)
        notice_deadline = (agm_date - timedelta(days=14)).date()

        return {
            "meeting_id": meeting_id,
            "agm_date": agm_date.strftime("%d %B %Y"),
            "location": location,
            "notice_deadline": notice_deadline.strftime("%d %B %Y"),
            "agenda_items": len(agenda),
            "lots_to_notify": len(self.lots),
            "quorum_required": max(2, len(self.lots) // 4),
            "committee_positions_up_for_election": len(self.get_committee_members()),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # OWNER COMMUNICATION
    # ─────────────────────────────────────────────────────────────────────────

    def send_notice_to_all(self, subject: str, message: str) -> int:
        """Send notice to all owners."""
        sent = 0
        for lot in self.lots.values():
            self.communications.append(
                {
                    "type": "general_notice",
                    "lot_number": lot.lot_number,
                    "email": lot.owner_email,
                    "subject": subject,
                    "date": datetime.now().isoformat(),
                }
            )
            sent += 1

        print(f"📤 Notice sent to {sent} owners: {subject}")
        return sent

    def send_notice_to_lot(self, lot_number: int, subject: str, message: str) -> bool:
        """Send notice to specific lot owner."""
        lot = self.lots.get(lot_number)
        if not lot:
            return False

        self.communications.append(
            {
                "type": "individual_notice",
                "lot_number": lot_number,
                "email": lot.owner_email,
                "subject": subject,
                "date": datetime.now().isoformat(),
            }
        )

        print(f"📤 Notice sent to Lot {lot_number}: {subject}")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA
# ══════════════════════════════════════════════════════════════════════════════


def create_demo_scheme() -> StrataScheme:
    """Create a demo strata scheme."""
    return StrataScheme(
        scheme_id="SP12345",
        name="Harbour View Apartments",
        address="123 Marina Boulevard, Adelaide SA 5000",
        state=AustralianState.SA,
        total_lots=12,
        total_unit_entitlements=1000,
        year_established=2015,
        financial_year_end="30 June",
        manager_name="Adelaide Strata Management",
        manager_email="info@adelaidestrata.com.au",
        manager_phone="08 8232 1234",
        admin_fund_balance=Decimal("45000"),
        capital_fund_balance=Decimal("120000"),
    )


def populate_demo_lots(manager: StrataManager):
    """Populate demo lots."""
    owners = [
        ("John Smith", "john.smith@email.com", "0412 111 222", True, "Chair"),
        ("Mary Chen", "mary.chen@email.com", "0423 222 333", True, "Secretary"),
        ("Robert Wilson", "r.wilson@bigpond.com", "0434 333 444", False, "Treasurer"),
        ("Sarah Jones", "sarah.j@gmail.com", "0445 444 555", True, "Member"),
        ("David Brown", "dbrown@email.com", "0456 555 666", False, None),
        ("Lisa Taylor", "lisa.taylor@outlook.com", "0467 666 777", True, None),
        ("Michael Lee", "mlee@email.com", "0478 777 888", True, None),
        ("Jennifer Wong", "j.wong@email.com", "0489 888 999", False, None),
        ("Christopher Davis", "cdavis@email.com", "0490 999 000", True, None),
        ("Amanda White", "a.white@email.com", "0401 000 111", True, None),
        ("Peter Martin", "peter.m@email.com", "0412 111 222", False, None),
        ("Karen Thompson", "kthompson@email.com", "0423 222 333", True, None),
    ]

    unit_entitlements = [
        100,
        100,
        80,
        80,
        80,
        80,
        80,
        80,
        80,
        80,
        80,
        80,
    ]  # Total = 1000

    for i, (name, email, phone, owner_occ, role) in enumerate(owners):
        lot = Lot(
            lot_number=i + 1,
            lot_type=LotType.RESIDENTIAL,
            unit_entitlement=unit_entitlements[i],
            owner_name=name,
            owner_email=email,
            owner_phone=phone,
            owner_postal_address=f"Lot {i+1}, 123 Marina Boulevard, Adelaide SA 5000",
            is_owner_occupied=owner_occ,
            tenant_name="Tenant Name" if not owner_occ else None,
            committee_role=role,
            quarterly_admin_levy=Decimal("850") * unit_entitlements[i] / 100,
            quarterly_capital_levy=Decimal("350") * unit_entitlements[i] / 100,
        )
        manager.add_lot(lot)


def populate_demo_bylaws(manager: StrataManager):
    """Add demo by-laws."""
    bylaws = [
        (
            1,
            "Noise Control",
            ByLawCategory.NOISE,
            "Owners and occupiers must not make noise likely to disturb others, "
            "especially between 10pm and 8am.",
        ),
        (
            2,
            "Keeping of Animals",
            ByLawCategory.PETS,
            "Pets may be kept with written approval of the Strata Corporation. "
            "Approval may be refused or revoked if the pet causes nuisance.",
        ),
        (
            3,
            "Parking",
            ByLawCategory.PARKING,
            "Vehicles must only be parked in allocated spaces. "
            "Visitor parking is limited to 4 hours.",
        ),
        (
            4,
            "Renovations",
            ByLawCategory.RENOVATIONS,
            "Written approval must be obtained before any renovations or alterations. "
            "Work may only be carried out between 8am and 6pm on weekdays.",
        ),
        (
            5,
            "Appearance of Lot",
            ByLawCategory.APPEARANCE,
            "Nothing shall be displayed on balconies that detracts from the appearance "
            "of the building.",
        ),
    ]

    for num, title, category, content in bylaws:
        bylaw = ByLaw(
            bylaw_id=manager._generate_id("BL"),
            number=num,
            title=title,
            category=category,
            content=content,
            adopted_date=date(2015, 6, 1),
            registered=True,
            registration_date=date(2015, 7, 15),
        )
        manager.add_bylaw(bylaw)


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate the strata manager."""

    print("=" * 70)
    print("Strata/Body Corporate Assistant Demo")
    print("=" * 70)

    # Create scheme and manager
    scheme = create_demo_scheme()
    manager = StrataManager(scheme)

    print(f"\n🏢 Scheme: {scheme.name}")
    print(f"📍 Address: {scheme.address}")
    print(
        f"📋 Terminology: {manager.terminology.owner_group} ({manager.terminology.scheme_name})"
    )
    print(f"💰 Admin Fund Balance: ${scheme.admin_fund_balance:,.2f}")
    print(f"💰 Capital Works Fund: ${scheme.capital_fund_balance:,.2f}")

    # Populate data
    print("\n" + "─" * 50)
    print("👥 Adding Lot Owners")
    print("─" * 50)
    populate_demo_lots(manager)
    populate_demo_bylaws(manager)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Strata Roll
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📋 Strata Roll")
    print("─" * 50)

    roll = manager.get_roll()
    print(f"\nTotal Lots: {len(roll)}")
    print("\nCommittee Members:")
    committee = manager.get_committee_members()
    for member in committee:
        print(
            f"   {member.committee_role}: {member.owner_name} (Lot {member.lot_number})"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Raise Levies
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("💰 Raising Levies")
    print("─" * 50)

    due_date = date.today() + timedelta(days=30)
    manager.raise_levies("Q3 2026", due_date)

    # Record some payments
    manager.record_levy_payment(1, Decimal("1200"), date.today())
    manager.record_levy_payment(2, Decimal("1200"), date.today())
    manager.record_levy_payment(4, Decimal("500"), date.today())  # Partial

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Arrears Report
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("⚠️ Arrears Report")
    print("─" * 50)

    # Set some notices to overdue for demo
    for notice in manager.levy_notices:
        if notice.status == LevyStatus.DUE and notice.lot_number > 5:
            notice.due_date = date.today() - timedelta(days=30)
            notice.status = LevyStatus.OVERDUE

    arrears = manager.get_arrears_report()
    if arrears:
        print(f"\n{len(arrears)} lot(s) in arrears:")
        for arr in arrears[:5]:
            print(
                f"   Lot {arr['lot_number']}: ${arr['total_arrears']:.2f} "
                f"({arr['days_overdue']} days overdue)"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: By-Law Breach
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("⚖️ By-Law Breach")
    print("─" * 50)

    print("\nCurrent By-Laws:")
    for bylaw in manager.bylaws[:3]:
        print(f"   {bylaw.number}. {bylaw.title}")

    breach_id = manager.report_breach(
        bylaw_number=1,
        lot_number=5,
        description="Loud music after 11pm on multiple occasions",
        reported_by=4,
    )

    manager.issue_breach_notice(breach_id, "warning")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Common Property Maintenance
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔧 Common Property Maintenance")
    print("─" * 50)

    work_id = manager.create_maintenance_work(
        category=MaintenanceCategory.LIFT,
        description="Annual lift servicing and safety inspection",
        estimated_cost=Decimal("2500"),
        fund_source="administrative",
    )

    manager.create_maintenance_work(
        category=MaintenanceCategory.BUILDING,
        description="External painting - north facade",
        estimated_cost=Decimal("35000"),
        fund_source="capital",
        requires_approval=True,
    )

    summary = manager.get_maintenance_summary()
    print(f"\nMaintenance Summary:")
    print(f"   Planned: {summary['planned']}")
    print(f"   Total Planned Cost: ${summary['total_planned_cost']:,.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Schedule AGM
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📅 AGM Preparation")
    print("─" * 50)

    agm_date = datetime.now() + timedelta(days=45)
    agm_details = manager.prepare_agm(
        agm_date=agm_date,
        location="Building Common Room, Level 1",
    )

    print(f"\nAGM scheduled for: {agm_details['agm_date']}")
    print(f"Location: {agm_details['location']}")
    print(f"Notice deadline: {agm_details['notice_deadline']}")
    print(f"Quorum required: {agm_details['quorum_required']} lots")

    # Send notices
    manager.send_meeting_notice(agm_details["meeting_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Simulate Meeting
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🗳️ Meeting Simulation")
    print("─" * 50)

    # Record attendance
    meeting_id = agm_details["meeting_id"]
    for lot_num in [1, 2, 3, 4, 6, 8, 10]:
        manager.record_attendance(meeting_id, lot_num)
    manager.record_attendance(meeting_id, 5, proxy=True)

    quorum = manager.check_quorum(meeting_id)
    print(
        f"\nAttendance: {quorum['lots_present']} lots present "
        f"(including {quorum['proxies']} proxies)"
    )
    print(f"Quorum: {'✅ Achieved' if quorum['has_quorum'] else '❌ Not achieved'}")

    # Add and vote on motion
    motion_id = manager.add_motion(
        meeting_id=meeting_id,
        title="Approval of external painting works",
        description="To approve external painting of north facade at estimated cost of $35,000",
        resolution_type=ResolutionType.ORDINARY,
        moved_by=1,
        seconded_by=2,
    )

    result = manager.record_vote(motion_id, votes_for=6, votes_against=1, abstentions=1)
    print(f"\nMotion: {result['title']}")
    print(
        f"   For: {result['votes_for']}, Against: {result['votes_against']}, Abstain: {result['abstentions']}"
    )
    print(f"   Result: {result['status']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Financial Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("💰 Financial Summary")
    print("─" * 50)

    financials = manager.get_financial_summary()

    print(f"\nFund Balances:")
    print(
        f"   {manager.terminology.admin_fund}: ${financials['admin_fund_balance']:,.2f}"
    )
    print(
        f"   {manager.terminology.capital_fund}: ${financials['capital_fund_balance']:,.2f}"
    )
    print(f"   Total: ${financials['total_fund_balance']:,.2f}")

    print(f"\nLevies (YTD):")
    print(f"   Raised: ${financials['levies_raised_ytd']:,.2f}")
    print(f"   Collected: ${financials['levies_collected_ytd']:,.2f}")
    print(f"   Collection Rate: {financials['collection_rate']}")

    print(f"\nArrears:")
    print(f"   Total: ${financials['total_arrears']:,.2f}")
    print(f"   Lots in arrears: {financials['lots_in_arrears']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("✅ Strata Manager Demo Complete!")
    print("\nFeatures demonstrated:")
    print("  • Strata scheme setup with state terminology")
    print("  • Lot owner management and strata roll")
    print("  • Levy raising and collection")
    print("  • Arrears tracking and notices")
    print("  • By-law management and breach handling")
    print("  • Common property maintenance")
    print("  • AGM scheduling and preparation")
    print("  • Meeting attendance and voting")
    print("  • Financial reporting")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
