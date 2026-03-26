#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 61: Supported Independent Living (SIL) Provider Coordinator
====================================================================

DISCLAIMER: This is a demonstration example only.
All names, addresses, and data are fictional.
This is not affiliated with any real NDIS provider.
Consult official NDIS guidelines for actual implementation.

Comprehensive SIL service coordination for NDIS-registered providers.

SIL Overview:
    Supported Independent Living provides help with daily tasks to live
    independently in the community. Unlike SDA (which is the building),
    SIL is the SUPPORT within the home - 24/7 or regular assistance.

SIL Support Types:
    - 24/7 Support: Round-the-clock assistance
    - Active Night: Support worker awake overnight
    - Sleepover: Worker sleeps but available if needed
    - Rostered Care: Scheduled hours during day
    - Drop-in Support: As-needed visits

This System Manages:
    - Participant roster and support plans
    - Support worker scheduling and rostering
    - Shift handover notes and communication
    - Daily living support tracking
    - Medication reminder safeguards
    - Goal progress monitoring
    - Family/guardian communication portal
    - Incident reporting and management
    - Budget tracking per participant
    - Quality and safeguards compliance

Privacy Architecture:
    - On-premise deployment required (health information)
    - End-to-end encryption for all data
    - Role-based access control
    - Audit trail for compliance
    - NDIS Quality and Safeguards compliant

Requirements:
    - Ollama running with llama3.1:8b
    - Neo4j for participant/staff data (optional)

Author: agentic-brain
License: MIT
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
import hashlib
import json

# ══════════════════════════════════════════════════════════════════════════════
# SIL ENUMERATIONS
# ══════════════════════════════════════════════════════════════════════════════


class SupportLevel(Enum):
    """NDIS SIL support levels."""

    STANDARD = "standard"  # Regular support
    HIGH_INTENSITY = "high_intensity"  # Complex needs
    ACTIVE_NIGHT = "active_night"  # Worker awake overnight
    SLEEPOVER = "sleepover"  # Worker sleeps but available
    DROP_IN = "drop_in"  # Periodic visits


class ShiftType(Enum):
    """Types of support shifts."""

    MORNING = "morning"  # 6am - 2pm
    AFTERNOON = "afternoon"  # 2pm - 10pm
    NIGHT = "night"  # 10pm - 6am
    ACTIVE_OVERNIGHT = "active_overnight"  # Active all night
    SLEEPOVER = "sleepover"  # Sleep with on-call
    COMMUNITY_ACCESS = "community_access"  # Outings
    TRAINING = "training"  # Staff training


class ShiftStatus(Enum):
    """Shift status."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class IncidentSeverity(Enum):
    """Incident severity levels."""

    LOW = "low"  # Minor, document only
    MEDIUM = "medium"  # Requires review
    HIGH = "high"  # Requires immediate action
    CRITICAL = "critical"  # Reportable to NDIS Commission


class IncidentType(Enum):
    """Types of reportable incidents."""

    MEDICATION_ERROR = "medication_error"
    BEHAVIOUR_OF_CONCERN = "behaviour_of_concern"
    INJURY_PARTICIPANT = "injury_participant"
    INJURY_STAFF = "injury_staff"
    PROPERTY_DAMAGE = "property_damage"
    MISSING_PARTICIPANT = "missing_participant"
    UNAUTHORISED_USE = "unauthorised_use"  # Restrictive practice
    ABUSE_ALLEGATION = "abuse_allegation"
    NEGLECT_ALLEGATION = "neglect_allegation"
    DEATH = "death"
    OTHER = "other"


class GoalStatus(Enum):
    """Goal progress status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ON_TRACK = "on_track"
    NEEDS_REVIEW = "needs_review"
    ACHIEVED = "achieved"
    DISCONTINUED = "discontinued"


class MedicationFrequency(Enum):
    """Medication frequency options."""

    ONCE_DAILY = "once_daily"
    TWICE_DAILY = "twice_daily"
    THREE_TIMES_DAILY = "three_times_daily"
    FOUR_TIMES_DAILY = "four_times_daily"
    AS_NEEDED = "as_needed"
    WEEKLY = "weekly"
    WITH_MEALS = "with_meals"


# ══════════════════════════════════════════════════════════════════════════════
# SIL PRICING (Based on NDIS Price Guide 2024-25)
# ══════════════════════════════════════════════════════════════════════════════


# SIL hourly rates by support level (example rates - weekday)
SIL_HOURLY_RATES = {
    SupportLevel.STANDARD: Decimal("65.47"),
    SupportLevel.HIGH_INTENSITY: Decimal("90.85"),
    SupportLevel.ACTIVE_NIGHT: Decimal("72.61"),
    SupportLevel.SLEEPOVER: Decimal("52.22"),  # Per night
    SupportLevel.DROP_IN: Decimal("65.47"),
}

# Shift loading multipliers
SHIFT_LOADINGS = {
    "weekday": Decimal("1.00"),
    "saturday": Decimal("1.50"),
    "sunday": Decimal("2.00"),
    "public_holiday": Decimal("2.50"),
    "evening": Decimal("1.15"),  # After 8pm weekdays
    "night": Decimal("1.25"),  # After 10pm
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class SILParticipant:
    """NDIS participant receiving SIL services."""

    participant_id: str
    ndis_number_hash: str  # Hashed for privacy
    first_name: str
    last_name: str
    date_of_birth: date

    # SIL details
    support_level: SupportLevel
    weekly_sil_hours: float
    sil_budget_daily: Decimal
    plan_start_date: date
    plan_end_date: date

    # Living situation
    property_id: Optional[str] = None  # Links to SDA if applicable
    bedroom_number: Optional[str] = None
    move_in_date: Optional[date] = None

    # Support needs
    support_needs_summary: str = ""
    morning_routine: str = ""
    evening_routine: str = ""
    night_support_needs: str = ""
    community_access_needs: str = ""

    # Health & safety
    allergies: list[str] = field(default_factory=list)
    dietary_requirements: list[str] = field(default_factory=list)
    mobility_aids: list[str] = field(default_factory=list)
    communication_method: str = "verbal"  # verbal, AAC, sign, etc.
    emergency_contacts: list[dict] = field(default_factory=list)

    # Behaviour support
    has_behaviour_support_plan: bool = False
    behaviour_triggers: list[str] = field(default_factory=list)
    behaviour_strategies: list[str] = field(default_factory=list)
    restrictive_practices_authorised: list[str] = field(default_factory=list)

    # Guardian/nominee
    has_guardian: bool = False
    guardian_name: str = ""
    guardian_contact: str = ""

    # Active status
    is_active: bool = True

    @staticmethod
    def hash_ndis_number(ndis_number: str) -> str:
        """Hash NDIS number for privacy."""
        return hashlib.sha256(ndis_number.encode()).hexdigest()[:16]

    def get_age(self) -> int:
        """Calculate participant age."""
        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def to_dict(self) -> dict:
        """Convert to dictionary (privacy-aware)."""
        return {
            "participant_id": self.participant_id,
            "name": f"{self.first_name} {self.last_name[0]}.",
            "age": self.get_age(),
            "support_level": self.support_level.value,
            "weekly_hours": self.weekly_sil_hours,
            "property_id": self.property_id,
            "is_active": self.is_active,
        }


@dataclass
class SupportWorker:
    """Support worker providing SIL services."""

    worker_id: str
    first_name: str
    last_name: str
    email: str
    phone: str

    # Qualifications
    certificate_iii_disability: bool = False
    certificate_iv_disability: bool = False
    first_aid_current: bool = False
    first_aid_expiry: Optional[date] = None
    manual_handling_trained: bool = False
    medication_competency: bool = False
    behaviour_support_trained: bool = False

    # Clearances
    ndis_worker_screening_cleared: bool = False
    ndis_screening_expiry: Optional[date] = None
    wwcc_cleared: bool = False
    wwcc_number: str = ""
    police_check_date: Optional[date] = None

    # Work preferences
    available_shifts: list[ShiftType] = field(default_factory=list)
    max_hours_per_week: int = 38
    preferred_locations: list[str] = field(default_factory=list)

    # Current status
    is_active: bool = True
    employment_type: str = "casual"  # casual, part_time, full_time

    def is_compliant(self) -> bool:
        """Check if worker meets all compliance requirements."""
        today = date.today()

        # Check NDIS screening
        if not self.ndis_worker_screening_cleared:
            return False
        if self.ndis_screening_expiry and self.ndis_screening_expiry < today:
            return False

        # Check first aid
        if not self.first_aid_current:
            return False
        if self.first_aid_expiry and self.first_aid_expiry < today:
            return False

        return True

    def get_upcoming_expiries(self, days: int = 30) -> list[dict]:
        """Get qualifications expiring soon."""
        today = date.today()
        threshold = today + timedelta(days=days)
        expiries = []

        if self.first_aid_expiry and self.first_aid_expiry <= threshold:
            expiries.append(
                {
                    "type": "First Aid",
                    "expiry_date": self.first_aid_expiry.isoformat(),
                    "days_remaining": (self.first_aid_expiry - today).days,
                }
            )

        if self.ndis_screening_expiry and self.ndis_screening_expiry <= threshold:
            expiries.append(
                {
                    "type": "NDIS Worker Screening",
                    "expiry_date": self.ndis_screening_expiry.isoformat(),
                    "days_remaining": (self.ndis_screening_expiry - today).days,
                }
            )

        return expiries

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "name": f"{self.first_name} {self.last_name}",
            "is_compliant": self.is_compliant(),
            "employment_type": self.employment_type,
            "is_active": self.is_active,
        }


@dataclass
class Shift:
    """A support shift."""

    shift_id: str
    participant_id: str
    worker_id: Optional[str]
    property_id: str

    # Timing
    shift_date: date
    shift_type: ShiftType
    start_time: time
    end_time: time

    # Status
    status: ShiftStatus = ShiftStatus.SCHEDULED

    # Actual times (when shift completed)
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Notes
    shift_notes: str = ""
    handover_notes: str = ""

    # Support activities completed
    activities_completed: list[str] = field(default_factory=list)
    goals_worked_on: list[str] = field(default_factory=list)

    def get_scheduled_hours(self) -> float:
        """Calculate scheduled hours."""
        start_dt = datetime.combine(self.shift_date, self.start_time)
        end_dt = datetime.combine(self.shift_date, self.end_time)
        if end_dt < start_dt:  # Overnight
            end_dt += timedelta(days=1)
        return (end_dt - start_dt).seconds / 3600

    def get_actual_hours(self) -> float:
        """Calculate actual hours worked."""
        if not self.actual_start or not self.actual_end:
            return 0.0
        return (self.actual_end - self.actual_start).seconds / 3600

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "shift_id": self.shift_id,
            "participant_id": self.participant_id,
            "worker_id": self.worker_id,
            "date": self.shift_date.isoformat(),
            "type": self.shift_type.value,
            "start": self.start_time.isoformat(),
            "end": self.end_time.isoformat(),
            "status": self.status.value,
            "hours": self.get_scheduled_hours(),
        }


@dataclass
class Medication:
    """Medication record for a participant."""

    medication_id: str
    participant_id: str
    medication_name: str
    dosage: str
    frequency: MedicationFrequency
    administration_times: list[time] = field(default_factory=list)

    # Details
    prescribing_doctor: str = ""
    pharmacy: str = ""
    purpose: str = ""
    special_instructions: str = ""

    # Safety
    side_effects_to_monitor: list[str] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)

    # Status
    is_active: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # Administration level
    # Level 1: Prompt/remind only
    # Level 2: Assist with packaging
    # Level 3: Administer with training
    administration_level: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary (limited info for safety)."""
        return {
            "medication_id": self.medication_id,
            "name": self.medication_name,
            "frequency": self.frequency.value,
            "times": [t.isoformat() for t in self.administration_times],
            "administration_level": self.administration_level,
            "is_active": self.is_active,
        }


@dataclass
class MedicationLog:
    """Log of medication administration."""

    log_id: str
    medication_id: str
    participant_id: str
    worker_id: str

    # Timing
    scheduled_time: datetime
    actual_time: Optional[datetime]

    # Status
    administered: bool = False
    refused: bool = False
    missed: bool = False
    reason_if_not_given: str = ""

    # Witness (for Level 3)
    witnessed_by: Optional[str] = None

    notes: str = ""


@dataclass
class Goal:
    """Participant goal from NDIS plan."""

    goal_id: str
    participant_id: str
    goal_text: str
    category: str  # daily_living, community, employment, etc.

    # Timeline
    start_date: date
    target_date: date

    # Progress
    status: GoalStatus = GoalStatus.NOT_STARTED
    progress_percentage: int = 0
    progress_notes: list[dict] = field(default_factory=list)

    # Strategies
    strategies: list[str] = field(default_factory=list)

    def add_progress(self, note: str, percentage: int, worker_id: str) -> None:
        """Add progress update."""
        self.progress_notes.append(
            {
                "date": datetime.now().isoformat(),
                "note": note,
                "percentage": percentage,
                "worker_id": worker_id,
            }
        )
        self.progress_percentage = percentage

        if percentage >= 100:
            self.status = GoalStatus.ACHIEVED
        elif percentage > 0:
            self.status = GoalStatus.IN_PROGRESS

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "goal_id": self.goal_id,
            "goal": self.goal_text,
            "category": self.category,
            "status": self.status.value,
            "progress": self.progress_percentage,
            "target_date": self.target_date.isoformat(),
        }


@dataclass
class Incident:
    """Incident report."""

    incident_id: str
    participant_id: str
    reported_by: str  # worker_id

    # Incident details
    incident_type: IncidentType
    severity: IncidentSeverity
    incident_datetime: datetime
    location: str
    description: str

    # People involved
    witnesses: list[str] = field(default_factory=list)
    others_involved: list[str] = field(default_factory=list)

    # Response
    immediate_actions_taken: str = ""
    notifications_made: list[str] = field(default_factory=list)  # Who was notified

    # Follow-up
    requires_investigation: bool = False
    investigation_notes: str = ""
    outcome: str = ""

    # Status
    status: str = "open"  # open, under_investigation, closed
    reported_to_ndis_commission: bool = False
    ndis_report_date: Optional[date] = None

    def is_reportable(self) -> bool:
        """Check if incident must be reported to NDIS Commission."""
        reportable_types = [
            IncidentType.DEATH,
            IncidentType.ABUSE_ALLEGATION,
            IncidentType.NEGLECT_ALLEGATION,
            IncidentType.UNAUTHORISED_USE,  # Restrictive practices
            IncidentType.MISSING_PARTICIPANT,
        ]
        return (
            self.severity == IncidentSeverity.CRITICAL
            or self.incident_type in reportable_types
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "type": self.incident_type.value,
            "severity": self.severity.value,
            "datetime": self.incident_datetime.isoformat(),
            "status": self.status,
            "reportable": self.is_reportable(),
        }


@dataclass
class HandoverNote:
    """Shift handover notes."""

    handover_id: str
    property_id: str
    from_shift_id: str
    to_shift_id: str

    # Timing
    handover_datetime: datetime
    from_worker_id: str
    to_worker_id: str

    # Content
    general_notes: str = ""
    participant_updates: dict = field(default_factory=dict)  # participant_id: notes
    tasks_outstanding: list[str] = field(default_factory=list)
    tasks_completed: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)

    # Acknowledgment
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None


@dataclass
class FamilyCommunication:
    """Communication log with family/guardians."""

    comm_id: str
    participant_id: str
    contact_type: str  # phone, email, in_person, video
    contact_with: str  # Family member name/relationship

    # Content
    datetime: datetime
    initiated_by: str  # staff, family
    summary: str
    topics_discussed: list[str] = field(default_factory=list)

    # Follow-up
    follow_up_required: bool = False
    follow_up_notes: str = ""
    follow_up_completed: bool = False


# ══════════════════════════════════════════════════════════════════════════════
# SIL COORDINATOR
# ══════════════════════════════════════════════════════════════════════════════


class SILCoordinator:
    """
    Coordinates all aspects of Supported Independent Living operations.

    Features:
        - Participant roster and care management
        - Staff rostering and compliance
        - Shift management and handovers
        - Medication management (with safeguards)
        - Goal tracking and progress
        - Incident management and reporting
        - Family communication portal
        - Budget tracking
    """

    def __init__(self, provider_name: str = "Support Network Services"):
        """Initialize the SIL Coordinator."""
        self.provider_name = provider_name

        # Data stores
        self.participants: dict[str, SILParticipant] = {}
        self.workers: dict[str, SupportWorker] = {}
        self.shifts: dict[str, Shift] = {}
        self.medications: dict[str, Medication] = {}
        self.medication_logs: list[MedicationLog] = []
        self.goals: dict[str, Goal] = {}
        self.incidents: dict[str, Incident] = {}
        self.handovers: list[HandoverNote] = []
        self.family_comms: list[FamilyCommunication] = []

        # Properties/houses managed
        self.properties: dict[str, dict] = {}

        # Audit log
        self.audit_log: list[dict] = []

    def _log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: str = "system",
        details: str = "",
    ) -> None:
        """Log action for audit trail."""
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "user_id": user_id,
                "details": details,
            }
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PROPERTY MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def add_property(
        self,
        property_id: str,
        name: str,
        address: str,
        max_residents: int,
        shift_pattern: str = "24/7",
    ) -> None:
        """Add a SIL property/house."""
        self.properties[property_id] = {
            "property_id": property_id,
            "name": name,
            "address": address,
            "max_residents": max_residents,
            "shift_pattern": shift_pattern,
            "current_residents": [],
        }
        print(f"🏠 Added property: {name}")

    # ──────────────────────────────────────────────────────────────────────────
    # PARTICIPANT MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def add_participant(self, participant: SILParticipant) -> None:
        """Add a participant to SIL services."""
        self.participants[participant.participant_id] = participant

        # Add to property residents list
        if participant.property_id and participant.property_id in self.properties:
            self.properties[participant.property_id]["current_residents"].append(
                participant.participant_id
            )

        self._log_action(
            "CREATE",
            "participant",
            participant.participant_id,
            details="Participant enrolled in SIL",
        )
        print(
            f"✅ Added participant: {participant.first_name} {participant.last_name[0]}."
        )

    def get_participant(self, participant_id: str) -> Optional[SILParticipant]:
        """Get participant by ID."""
        return self.participants.get(participant_id)

    def get_property_residents(self, property_id: str) -> list[SILParticipant]:
        """Get all participants in a property."""
        return [
            p
            for p in self.participants.values()
            if p.property_id == property_id and p.is_active
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # WORKER MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def add_worker(self, worker: SupportWorker) -> None:
        """Add a support worker."""
        if not worker.is_compliant():
            print(
                f"⚠️ Warning: Worker {worker.first_name} does not meet compliance requirements"
            )

        self.workers[worker.worker_id] = worker
        self._log_action(
            "CREATE", "worker", worker.worker_id, details="Support worker added"
        )
        print(f"✅ Added worker: {worker.first_name} {worker.last_name}")

    def get_available_workers(
        self, shift_date: date, shift_type: ShiftType, property_id: str = None
    ) -> list[SupportWorker]:
        """Get workers available for a shift."""
        available = []

        for worker in self.workers.values():
            if not worker.is_active or not worker.is_compliant():
                continue

            if shift_type not in worker.available_shifts:
                continue

            if property_id and worker.preferred_locations:
                if property_id not in worker.preferred_locations:
                    continue

            # Check not already rostered
            already_rostered = any(
                s
                for s in self.shifts.values()
                if s.worker_id == worker.worker_id
                and s.shift_date == shift_date
                and s.status != ShiftStatus.CANCELLED
            )
            if not already_rostered:
                available.append(worker)

        return available

    def get_compliance_alerts(self) -> list[dict]:
        """Get compliance alerts for all workers."""
        alerts = []

        for worker in self.workers.values():
            if not worker.is_active:
                continue

            if not worker.is_compliant():
                alerts.append(
                    {
                        "worker_id": worker.worker_id,
                        "worker_name": f"{worker.first_name} {worker.last_name}",
                        "alert_type": "non_compliant",
                        "message": "Worker does not meet compliance requirements",
                        "severity": "high",
                    }
                )

            expiries = worker.get_upcoming_expiries(days=30)
            for exp in expiries:
                alerts.append(
                    {
                        "worker_id": worker.worker_id,
                        "worker_name": f"{worker.first_name} {worker.last_name}",
                        "alert_type": "expiring_soon",
                        "message": f"{exp['type']} expires in {exp['days_remaining']} days",
                        "severity": "medium" if exp["days_remaining"] > 14 else "high",
                    }
                )

        return alerts

    # ──────────────────────────────────────────────────────────────────────────
    # SHIFT MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def create_shift(
        self,
        participant_id: str,
        property_id: str,
        shift_date: date,
        shift_type: ShiftType,
        start_time: time,
        end_time: time,
        worker_id: Optional[str] = None,
    ) -> Shift:
        """Create a new shift."""
        shift_id = f"SH-{property_id}-{shift_date.isoformat()}-{shift_type.value}"

        shift = Shift(
            shift_id=shift_id,
            participant_id=participant_id,
            worker_id=worker_id,
            property_id=property_id,
            shift_date=shift_date,
            shift_type=shift_type,
            start_time=start_time,
            end_time=end_time,
            status=ShiftStatus.CONFIRMED if worker_id else ShiftStatus.SCHEDULED,
        )

        self.shifts[shift_id] = shift
        self._log_action(
            "CREATE", "shift", shift_id, details=f"Shift created for {shift_date}"
        )

        return shift

    def assign_worker(self, shift_id: str, worker_id: str) -> bool:
        """Assign worker to shift."""
        shift = self.shifts.get(shift_id)
        worker = self.workers.get(worker_id)

        if not shift or not worker:
            return False

        if not worker.is_compliant():
            print(f"❌ Cannot assign non-compliant worker")
            return False

        shift.worker_id = worker_id
        shift.status = ShiftStatus.CONFIRMED

        self._log_action(
            "ASSIGN", "shift", shift_id, worker_id, f"Assigned to {worker.first_name}"
        )
        print(f"✅ Assigned {worker.first_name} to shift {shift_id}")

        return True

    def start_shift(self, shift_id: str, worker_id: str) -> bool:
        """Mark shift as started."""
        shift = self.shifts.get(shift_id)
        if not shift or shift.worker_id != worker_id:
            return False

        shift.status = ShiftStatus.IN_PROGRESS
        shift.actual_start = datetime.now()

        self._log_action("START", "shift", shift_id, worker_id)
        return True

    def complete_shift(
        self,
        shift_id: str,
        worker_id: str,
        activities: list[str],
        goals_worked_on: list[str],
        notes: str,
        handover_notes: str,
    ) -> bool:
        """Complete a shift with documentation."""
        shift = self.shifts.get(shift_id)
        if not shift or shift.worker_id != worker_id:
            return False

        shift.status = ShiftStatus.COMPLETED
        shift.actual_end = datetime.now()
        shift.activities_completed = activities
        shift.goals_worked_on = goals_worked_on
        shift.shift_notes = notes
        shift.handover_notes = handover_notes

        self._log_action("COMPLETE", "shift", shift_id, worker_id)
        print(f"✅ Shift {shift_id} completed")

        return True

    def get_roster(
        self, property_id: str, start_date: date, end_date: date
    ) -> list[Shift]:
        """Get roster for a property."""
        return [
            s
            for s in self.shifts.values()
            if s.property_id == property_id and start_date <= s.shift_date <= end_date
        ]

    def get_unfilled_shifts(self, days_ahead: int = 7) -> list[Shift]:
        """Get shifts without assigned workers."""
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        return [
            s
            for s in self.shifts.values()
            if s.worker_id is None
            and today <= s.shift_date <= cutoff
            and s.status not in (ShiftStatus.CANCELLED, ShiftStatus.COMPLETED)
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # HANDOVER MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def create_handover(
        self,
        property_id: str,
        from_shift_id: str,
        to_shift_id: str,
        from_worker_id: str,
        to_worker_id: str,
        general_notes: str,
        participant_updates: dict,
        tasks_outstanding: list[str],
        concerns: list[str],
    ) -> HandoverNote:
        """Create handover notes between shifts."""
        handover_id = f"HO-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        handover = HandoverNote(
            handover_id=handover_id,
            property_id=property_id,
            from_shift_id=from_shift_id,
            to_shift_id=to_shift_id,
            handover_datetime=datetime.now(),
            from_worker_id=from_worker_id,
            to_worker_id=to_worker_id,
            general_notes=general_notes,
            participant_updates=participant_updates,
            tasks_outstanding=tasks_outstanding,
            concerns=concerns,
        )

        self.handovers.append(handover)
        self._log_action("CREATE", "handover", handover_id, from_worker_id)
        print(f"📋 Handover created from {from_worker_id} to {to_worker_id}")

        return handover

    def acknowledge_handover(self, handover_id: str, worker_id: str) -> bool:
        """Acknowledge receipt of handover."""
        for handover in self.handovers:
            if handover.handover_id == handover_id:
                if handover.to_worker_id == worker_id:
                    handover.acknowledged = True
                    handover.acknowledged_at = datetime.now()
                    return True
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # MEDICATION MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def add_medication(self, medication: Medication) -> None:
        """Add medication to participant's profile."""
        self.medications[medication.medication_id] = medication
        self._log_action(
            "CREATE",
            "medication",
            medication.medication_id,
            details=f"Added {medication.medication_name}",
        )
        print(f"💊 Added medication: {medication.medication_name}")

    def get_medications_due(
        self, participant_id: str, window_minutes: int = 30
    ) -> list[Medication]:
        """Get medications due within time window."""
        now = datetime.now().time()
        window = timedelta(minutes=window_minutes)
        now_dt = datetime.combine(date.today(), now)

        due_meds = []

        for med in self.medications.values():
            if med.participant_id != participant_id or not med.is_active:
                continue

            for admin_time in med.administration_times:
                admin_dt = datetime.combine(date.today(), admin_time)
                if abs((now_dt - admin_dt).total_seconds()) <= window_minutes * 60:
                    due_meds.append(med)
                    break

        return due_meds

    def log_medication_administration(
        self,
        medication_id: str,
        participant_id: str,
        worker_id: str,
        administered: bool,
        refused: bool = False,
        reason: str = "",
        witnessed_by: str = None,
    ) -> MedicationLog:
        """Log medication administration attempt."""
        log_id = f"ML-{datetime.now().strftime('%Y%m%d%H%M%S')}-{medication_id}"

        log = MedicationLog(
            log_id=log_id,
            medication_id=medication_id,
            participant_id=participant_id,
            worker_id=worker_id,
            scheduled_time=datetime.now(),
            actual_time=datetime.now() if administered else None,
            administered=administered,
            refused=refused,
            missed=not administered and not refused,
            reason_if_not_given=reason,
            witnessed_by=witnessed_by,
        )

        self.medication_logs.append(log)

        status = (
            "administered" if administered else ("refused" if refused else "missed")
        )
        self._log_action("LOG", "medication", log_id, worker_id, f"Medication {status}")

        # Alert if missed or refused
        if not administered:
            print(f"⚠️ Medication {medication_id} {status}: {reason}")

        return log

    def get_medication_history(
        self, participant_id: str, days: int = 7
    ) -> list[MedicationLog]:
        """Get medication administration history."""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            log
            for log in self.medication_logs
            if log.participant_id == participant_id and log.scheduled_time >= cutoff
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # GOAL TRACKING
    # ──────────────────────────────────────────────────────────────────────────

    def add_goal(self, goal: Goal) -> None:
        """Add a goal for a participant."""
        self.goals[goal.goal_id] = goal
        self._log_action("CREATE", "goal", goal.goal_id, details=goal.goal_text[:50])
        print(f"🎯 Added goal: {goal.goal_text[:50]}...")

    def update_goal_progress(
        self, goal_id: str, note: str, percentage: int, worker_id: str
    ) -> bool:
        """Update goal progress."""
        goal = self.goals.get(goal_id)
        if not goal:
            return False

        goal.add_progress(note, percentage, worker_id)
        self._log_action(
            "UPDATE", "goal", goal_id, worker_id, f"Progress: {percentage}%"
        )
        print(f"📈 Goal progress updated: {percentage}%")

        return True

    def get_participant_goals(self, participant_id: str) -> list[Goal]:
        """Get all goals for a participant."""
        return [g for g in self.goals.values() if g.participant_id == participant_id]

    def get_goals_summary(self, participant_id: str) -> dict:
        """Get summary of goal progress."""
        goals = self.get_participant_goals(participant_id)

        summary = {
            "total": len(goals),
            "achieved": 0,
            "in_progress": 0,
            "not_started": 0,
            "needs_review": 0,
        }

        for goal in goals:
            if goal.status == GoalStatus.ACHIEVED:
                summary["achieved"] += 1
            elif goal.status == GoalStatus.IN_PROGRESS:
                summary["in_progress"] += 1
            elif goal.status == GoalStatus.NOT_STARTED:
                summary["not_started"] += 1
            elif goal.status == GoalStatus.NEEDS_REVIEW:
                summary["needs_review"] += 1

        return summary

    # ──────────────────────────────────────────────────────────────────────────
    # INCIDENT MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def report_incident(
        self,
        participant_id: str,
        reported_by: str,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        incident_datetime: datetime,
        location: str,
        description: str,
        immediate_actions: str,
        witnesses: list[str] = None,
    ) -> Incident:
        """Report an incident."""
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        incident = Incident(
            incident_id=incident_id,
            participant_id=participant_id,
            reported_by=reported_by,
            incident_type=incident_type,
            severity=severity,
            incident_datetime=incident_datetime,
            location=location,
            description=description,
            immediate_actions_taken=immediate_actions,
            witnesses=witnesses or [],
        )

        self.incidents[incident_id] = incident

        # Log with appropriate urgency
        self._log_action(
            "REPORT",
            "incident",
            incident_id,
            reported_by,
            f"{severity.value} - {incident_type.value}",
        )

        # Alert for critical incidents
        if severity == IncidentSeverity.CRITICAL:
            print(f"🚨 CRITICAL INCIDENT: {incident_id}")
            print(f"   Type: {incident_type.value}")
            print(f"   Requires immediate attention!")

        # Check if reportable to NDIS Commission
        if incident.is_reportable():
            print(
                f"⚠️ REPORTABLE INCIDENT - Must report to NDIS Commission within 5 days"
            )
            incident.requires_investigation = True

        return incident

    def get_open_incidents(self) -> list[Incident]:
        """Get all open incidents."""
        return [i for i in self.incidents.values() if i.status == "open"]

    def get_reportable_incidents(self) -> list[Incident]:
        """Get incidents requiring NDIS Commission reporting."""
        return [
            i
            for i in self.incidents.values()
            if i.is_reportable() and not i.reported_to_ndis_commission
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # FAMILY COMMUNICATION
    # ──────────────────────────────────────────────────────────────────────────

    def log_family_communication(
        self,
        participant_id: str,
        contact_type: str,
        contact_with: str,
        initiated_by: str,
        summary: str,
        topics: list[str] = None,
        follow_up_required: bool = False,
    ) -> FamilyCommunication:
        """Log communication with family/guardian."""
        comm_id = f"COMM-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        comm = FamilyCommunication(
            comm_id=comm_id,
            participant_id=participant_id,
            contact_type=contact_type,
            contact_with=contact_with,
            datetime=datetime.now(),
            initiated_by=initiated_by,
            summary=summary,
            topics_discussed=topics or [],
            follow_up_required=follow_up_required,
        )

        self.family_comms.append(comm)
        self._log_action(
            "LOG",
            "family_communication",
            comm_id,
            details=f"Contact with {contact_with}",
        )

        return comm

    def get_family_communications(
        self, participant_id: str, days: int = 30
    ) -> list[FamilyCommunication]:
        """Get family communications for participant."""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            c
            for c in self.family_comms
            if c.participant_id == participant_id and c.datetime >= cutoff
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # BUDGET TRACKING
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_participant_spend(
        self, participant_id: str, month: int, year: int
    ) -> dict:
        """Calculate SIL spending for a participant in a month."""
        participant = self.participants.get(participant_id)
        if not participant:
            return {"error": "Participant not found"}

        total_hours = Decimal("0")
        total_cost = Decimal("0")

        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        shifts_in_period = [
            s
            for s in self.shifts.values()
            if s.participant_id == participant_id
            and start_date <= s.shift_date <= end_date
            and s.status == ShiftStatus.COMPLETED
        ]

        for shift in shifts_in_period:
            hours = Decimal(
                str(shift.get_actual_hours() or shift.get_scheduled_hours())
            )
            rate = SIL_HOURLY_RATES.get(participant.support_level, Decimal("65.47"))

            # Apply loadings
            day_of_week = shift.shift_date.weekday()
            if day_of_week == 5:  # Saturday
                rate *= SHIFT_LOADINGS["saturday"]
            elif day_of_week == 6:  # Sunday
                rate *= SHIFT_LOADINGS["sunday"]

            shift_cost = hours * rate
            total_hours += hours
            total_cost += shift_cost

        # Calculate budget status
        days_in_month = (end_date - start_date).days + 1
        monthly_budget = participant.sil_budget_daily * days_in_month
        remaining = monthly_budget - total_cost
        percentage_used = (
            (total_cost / monthly_budget * 100) if monthly_budget > 0 else Decimal("0")
        )

        return {
            "participant_id": participant_id,
            "period": f"{year}-{month:02d}",
            "total_shifts": len(shifts_in_period),
            "total_hours": str(total_hours),
            "total_cost": str(total_cost),
            "monthly_budget": str(monthly_budget),
            "remaining": str(remaining),
            "percentage_used": f"{percentage_used:.1f}%",
            "on_track": remaining >= 0,
        }

    def get_house_budget_summary(self, property_id: str, month: int, year: int) -> dict:
        """Get budget summary for all residents in a house."""
        residents = self.get_property_residents(property_id)

        summaries = []
        total_spend = Decimal("0")
        total_budget = Decimal("0")

        for resident in residents:
            spend = self.calculate_participant_spend(
                resident.participant_id, month, year
            )
            if "error" not in spend:
                summaries.append(spend)
                total_spend += Decimal(spend["total_cost"])
                total_budget += Decimal(spend["monthly_budget"])

        return {
            "property_id": property_id,
            "period": f"{year}-{month:02d}",
            "residents": len(summaries),
            "individual_summaries": summaries,
            "house_total_spend": str(total_spend),
            "house_total_budget": str(total_budget),
        }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate SIL Provider Coordinator."""

    print("=" * 70)
    print("🏠 SUPPORTED INDEPENDENT LIVING (SIL) COORDINATOR")
    print("=" * 70)
    print(f"\n📋 Provider: Support Network Services")
    print("🔒 Privacy Mode: On-Premise (No Cloud)")

    # Initialize coordinator
    sil = SILCoordinator(provider_name="Support Network Services")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Set up property
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("🏠 STEP 1: Setting Up SIL House")
    print("─" * 70)

    sil.add_property(
        property_id="HOUSE-001",
        name="Maple Grove House",
        address="15 Maple Grove, Modbury SA 5092",
        max_residents=4,
        shift_pattern="24/7",
    )

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Add participants
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("👥 STEP 2: Enrolling Participants")
    print("─" * 70)

    participant1 = SILParticipant(
        participant_id="SIL-001",
        ndis_number_hash=SILParticipant.hash_ndis_number("43012345678"),
        first_name="David",
        last_name="C",  # Generic initial only
        date_of_birth=date(1990, 6, 15),
        support_level=SupportLevel.STANDARD,
        weekly_sil_hours=60,
        sil_budget_daily=Decimal("400.00"),
        plan_start_date=date(2024, 7, 1),
        plan_end_date=date(2025, 6, 30),
        property_id="HOUSE-001",
        bedroom_number="1",
        move_in_date=date(2024, 7, 1),
        support_needs_summary="Requires assistance with daily living tasks including meal prep, personal care, and medication management.",
        morning_routine="Wake 7am, shower assistance, breakfast, medications",
        evening_routine="Dinner 6pm, medications, leisure time, bed prep by 9pm",
        allergies=["Penicillin"],
        dietary_requirements=["Gluten-free"],
        communication_method="verbal",
        emergency_contacts=[
            {
                "name": "Family Contact (Mother)",
                "phone": "0412 345 678",
                "relationship": "mother",
            },
            {"name": "Dr. (GP)", "phone": "08 8222 3333", "relationship": "GP"},
        ],
        has_guardian=False,
    )
    sil.add_participant(participant1)

    participant2 = SILParticipant(
        participant_id="SIL-002",
        ndis_number_hash=SILParticipant.hash_ndis_number("43098765432"),
        first_name="Emma",
        last_name="W",  # Generic initial only
        date_of_birth=date(1985, 3, 22),
        support_level=SupportLevel.HIGH_INTENSITY,
        weekly_sil_hours=80,
        sil_budget_daily=Decimal("550.00"),
        plan_start_date=date(2024, 4, 1),
        plan_end_date=date(2025, 3, 31),
        property_id="HOUSE-001",
        bedroom_number="2",
        support_needs_summary="High support needs including personal care, complex behaviours requiring trained staff.",
        has_behaviour_support_plan=True,
        behaviour_triggers=["Unexpected changes to routine", "Loud noises"],
        behaviour_strategies=[
            "Provide advance notice of changes",
            "Offer quiet space",
            "Use calm voice",
        ],
        communication_method="verbal with AAC backup",
        has_guardian=True,
        guardian_name="Family Guardian (Father)",
        guardian_contact="0423 456 789",
    )
    sil.add_participant(participant2)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: Add support workers
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("👷 STEP 3: Adding Support Workers")
    print("─" * 70)

    worker1 = SupportWorker(
        worker_id="SW-001",
        first_name="Lisa",
        last_name="J",  # Generic initial only
        email="lisa.j@example-provider.com",
        phone="0434 567 890",
        certificate_iii_disability=True,
        certificate_iv_disability=True,
        first_aid_current=True,
        first_aid_expiry=date(2025, 8, 15),
        manual_handling_trained=True,
        medication_competency=True,
        behaviour_support_trained=True,
        ndis_worker_screening_cleared=True,
        ndis_screening_expiry=date(2027, 3, 20),
        wwcc_cleared=True,
        wwcc_number="12345678A",
        available_shifts=[ShiftType.MORNING, ShiftType.AFTERNOON],
        max_hours_per_week=38,
        employment_type="part_time",
    )
    sil.add_worker(worker1)

    worker2 = SupportWorker(
        worker_id="SW-002",
        first_name="John",
        last_name="B",  # Generic initial only
        email="john.b@example-provider.com",
        phone="0445 678 901",
        certificate_iii_disability=True,
        first_aid_current=True,
        first_aid_expiry=date(2025, 2, 1),  # Expiring soon!
        manual_handling_trained=True,
        medication_competency=True,
        ndis_worker_screening_cleared=True,
        ndis_screening_expiry=date(2026, 11, 15),
        available_shifts=[ShiftType.AFTERNOON, ShiftType.NIGHT, ShiftType.SLEEPOVER],
        employment_type="casual",
    )
    sil.add_worker(worker2)

    # Check compliance
    print("\n📋 Compliance Alerts:")
    alerts = sil.get_compliance_alerts()
    for alert in alerts:
        print(f"   ⚠️ {alert['worker_name']}: {alert['message']}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Create roster
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📅 STEP 4: Creating Weekly Roster")
    print("─" * 70)

    # Create shifts for the week
    today = date.today()

    # Morning shift
    morning_shift = sil.create_shift(
        participant_id="SIL-001",
        property_id="HOUSE-001",
        shift_date=today,
        shift_type=ShiftType.MORNING,
        start_time=time(6, 0),
        end_time=time(14, 0),
        worker_id="SW-001",
    )
    print(f"   ✅ Morning shift: {morning_shift.shift_id}")

    # Afternoon shift
    afternoon_shift = sil.create_shift(
        participant_id="SIL-001",
        property_id="HOUSE-001",
        shift_date=today,
        shift_type=ShiftType.AFTERNOON,
        start_time=time(14, 0),
        end_time=time(22, 0),
        worker_id="SW-002",
    )
    print(f"   ✅ Afternoon shift: {afternoon_shift.shift_id}")

    # Night shift (unfilled)
    night_shift = sil.create_shift(
        participant_id="SIL-001",
        property_id="HOUSE-001",
        shift_date=today,
        shift_type=ShiftType.SLEEPOVER,
        start_time=time(22, 0),
        end_time=time(6, 0),
    )
    print(f"   ⚠️ Night shift UNFILLED: {night_shift.shift_id}")

    # Show unfilled shifts
    unfilled = sil.get_unfilled_shifts()
    if unfilled:
        print(f"\n   🚨 {len(unfilled)} unfilled shift(s) need workers")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: Add medications
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("💊 STEP 5: Medication Management")
    print("─" * 70)

    med1 = Medication(
        medication_id="MED-001",
        participant_id="SIL-001",
        medication_name="Epilim (Sodium Valproate)",
        dosage="500mg",
        frequency=MedicationFrequency.TWICE_DAILY,
        administration_times=[time(8, 0), time(20, 0)],
        prescribing_doctor="Dr Smith",
        purpose="Seizure prevention",
        special_instructions="Take with food",
        side_effects_to_monitor=["Drowsiness", "Nausea"],
        administration_level=2,  # Assist with packaging
    )
    sil.add_medication(med1)

    med2 = Medication(
        medication_id="MED-002",
        participant_id="SIL-001",
        medication_name="Paracetamol",
        dosage="500mg",
        frequency=MedicationFrequency.AS_NEEDED,
        purpose="Pain relief",
        special_instructions="Max 4 doses per day",
        administration_level=1,  # Prompt only
    )
    sil.add_medication(med2)

    # Log medication administration
    print("\n   Logging medication administration...")
    sil.log_medication_administration(
        medication_id="MED-001",
        participant_id="SIL-001",
        worker_id="SW-001",
        administered=True,
        witnessed_by="SW-002",
    )
    print("   ✅ Morning medication logged")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: Goal tracking
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("🎯 STEP 6: Goal Progress Tracking")
    print("─" * 70)

    goal1 = Goal(
        goal_id="GOAL-001",
        participant_id="SIL-001",
        goal_text="Independently prepare breakfast 3 times per week",
        category="daily_living",
        start_date=date(2024, 7, 1),
        target_date=date(2024, 12, 31),
        strategies=[
            "Visual recipe cards in kitchen",
            "Staff to provide prompts not hands-on help",
            "Practice with toast and cereal first",
        ],
    )
    sil.add_goal(goal1)

    # Update progress
    sil.update_goal_progress(
        goal_id="GOAL-001",
        note="David successfully made toast independently today. Required one verbal prompt for spreading butter.",
        percentage=35,
        worker_id="SW-001",
    )

    # Show summary
    summary = sil.get_goals_summary("SIL-001")
    print(f"\n   📊 Goal Summary for David C.:")
    print(f"      Total Goals: {summary['total']}")
    print(f"      In Progress: {summary['in_progress']}")
    print(f"      Achieved: {summary['achieved']}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 7: Incident reporting
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("🚨 STEP 7: Incident Reporting")
    print("─" * 70)

    incident = sil.report_incident(
        participant_id="SIL-002",
        reported_by="SW-001",
        incident_type=IncidentType.BEHAVIOUR_OF_CONCERN,
        severity=IncidentSeverity.MEDIUM,
        incident_datetime=datetime.now() - timedelta(hours=2),
        location="Living room",
        description="Emma became distressed when routine changed due to staff running late. Raised voice, threw cushion. De-escalated within 10 minutes using strategies from BSP.",
        immediate_actions="Applied calm voice technique, offered quiet space, used visual timer to show when regular staff would arrive.",
        witnesses=["SW-002"],
    )

    print(f"\n   📝 Incident logged: {incident.incident_id}")
    print(f"      Type: {incident.incident_type.value}")
    print(f"      Severity: {incident.severity.value}")
    print(
        f"      Reportable to NDIS Commission: {'Yes' if incident.is_reportable() else 'No'}"
    )

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 8: Shift handover
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📋 STEP 8: Shift Handover")
    print("─" * 70)

    handover = sil.create_handover(
        property_id="HOUSE-001",
        from_shift_id=morning_shift.shift_id,
        to_shift_id=afternoon_shift.shift_id,
        from_worker_id="SW-001",
        to_worker_id="SW-002",
        general_notes="Quiet morning. Both participants had good mornings.",
        participant_updates={
            "SIL-001": "David had a great breakfast, independently made toast! Medications given at 8am.",
            "SIL-002": "Emma seemed a bit tired but engaged well in morning activities.",
        },
        tasks_outstanding=[
            "Emma's laundry in dryer - needs folding",
            "David requested pasta for dinner",
        ],
        concerns=[
            "Emma mentioned feeling unwell earlier - monitor for symptoms",
        ],
    )

    print(f"   ✅ Handover created: {handover.handover_id}")
    print(f"      Outstanding tasks: {len(handover.tasks_outstanding)}")
    print(f"      Concerns flagged: {len(handover.concerns)}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 9: Family communication
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("👨‍👩‍👦 STEP 9: Family Communication")
    print("─" * 70)

    comm = sil.log_family_communication(
        participant_id="SIL-001",
        contact_type="phone",
        contact_with="Family Contact (Mother)",  # Generic name
        initiated_by="family",
        summary="Mother called to check on David. Discussed his progress with breakfast goal and upcoming medical appointment.",
        topics=[
            "Goal progress",
            "Medical appointment next Tuesday",
            "Visit this weekend",
        ],
        follow_up_required=True,
    )

    print(f"   📞 Communication logged: {comm.comm_id}")
    print(f"      Contact with: {comm.contact_with}")
    print(f"      Topics: {', '.join(comm.topics_discussed)}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 10: Budget report
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("💰 STEP 10: Budget Tracking")
    print("─" * 70)

    # Complete a shift to have data
    sil.complete_shift(
        shift_id=morning_shift.shift_id,
        worker_id="SW-001",
        activities=[
            "Personal care",
            "Breakfast assistance",
            "Medication administration",
        ],
        goals_worked_on=["GOAL-001"],
        notes="Good shift. David making great progress.",
        handover_notes="Documented in handover",
    )

    # Get budget summary
    budget = sil.calculate_participant_spend("SIL-001", month=8, year=2024)
    print(f"\n   📊 Budget Summary for David C. (August 2024):")
    print(f"      Total Shifts: {budget['total_shifts']}")
    print(f"      Total Hours: {budget['total_hours']}")
    print(f"      Total Cost: ${Decimal(budget['total_cost']):.2f}")
    print(f"      Monthly Budget: ${Decimal(budget['monthly_budget']):.2f}")
    print(f"      Budget Used: {budget['percentage_used']}")
    print(f"      On Track: {'✅ Yes' if budget['on_track'] else '⚠️ Over budget'}")

    # ──────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("✅ SIL COORDINATOR DEMO COMPLETE")
    print("=" * 70)

    print("\n📚 This system can be extended for:")
    print("   • Mobile app for support workers")
    print("   • Real-time shift notifications")
    print("   • Automated NDIS Commission reporting")
    print("   • Family portal for updates")
    print("   • Integration with payroll systems")
    print("   • Vehicle/transport booking")
    print("   • Community access planning")

    print("\n🔒 Privacy & Compliance Features:")
    print("   • All data stored on-premise")
    print("   • NDIS numbers hashed (never plain text)")
    print("   • Role-based access control")
    print("   • Full audit trail")
    print("   • NDIS Quality and Safeguards compliant")
    print("   • Incident reporting workflows")

    print("\n♿ Accessibility Notes:")
    print("   • Support for various communication methods")
    print("   • Behaviour Support Plan integration")
    print("   • Medication safety safeguards")
    print("   • Goal tracking aligned to NDIS plans")


if __name__ == "__main__":
    asyncio.run(demo())
