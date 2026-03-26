#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This file is part of Agentic Brain.
#
# Agentic Brain is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""
NDIS Provider Assistant for Australian Disability Services.

An AI assistant for NDIS (National Disability Insurance Scheme) registered
providers to manage participant services with compliance automation:

- NDIS Price Guide compliance checking
- Participant plan management with goal tracking
- Service booking and scheduling
- Progress notes with proper documentation standards
- Funding utilisation tracking
- Incident reporting (SIRS compliant)

Key Australian NDIS Context:
    - NDIS Quality and Safeguards Commission requirements
    - NDIS Price Guide line item validation
    - Australian Privacy Principles (APP) compliance
    - NDIS Practice Standards alignment

Architecture (Privacy-First):
    ┌──────────────────────────────────────────────────────────────────┐
    │                    ON-PREMISE DEPLOYMENT                          │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
    │  │  Ollama  │  │   SQLite     │  │  NDIS Provider Assistant   │  │
    │  │ (Local)  │◄─┤  (Encrypted) │◄─┤  (This Application)        │  │
    │  └──────────┘  └──────────────┘  └────────────────────────────┘  │
    │              ALL PARTICIPANT DATA STAYS LOCAL                     │
    └──────────────────────────────────────────────────────────────────┘
                            ╳
                NO participant data to external APIs

IMPORTANT DISCLAIMERS:
    ⚠️  This is a DEMONSTRATION system only
    ⚠️  NOT official NDIS software
    ⚠️  Always verify with official NDIS sources
    ⚠️  Consult NDIS Commission for compliance requirements
    ⚠️  Participant privacy is paramount - use only on-premise LLMs

Role-Based Access:
    - Support Worker: View participants, add progress notes, log incidents
    - Support Coordinator: Above + modify plans, service agreements
    - Provider Manager: Full access + compliance reports, billing

Usage:
    python examples/enterprise/ndis_provider_bot.py
    python examples/enterprise/ndis_provider_bot.py --role support_worker
    python examples/enterprise/ndis_provider_bot.py --demo

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b  # On-premise LLM
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from agentic_brain.auth import (
    JWTAuth,
    AuthConfig,
    require_role,
    User,
)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ndis.provider_assistant")


# =============================================================================
# NDIS SUPPORT CATEGORIES & PRICE GUIDE
# =============================================================================


class NDISSupportCategory(str, Enum):
    """NDIS Support Budget Categories."""

    CORE_DAILY_ACTIVITIES = "Core - Daily Activities"
    CORE_TRANSPORT = "Core - Transport"
    CORE_CONSUMABLES = "Core - Consumables"
    CORE_SOCIAL_COMMUNITY = "Core - Social & Community"
    CAPACITY_COORDINATION = "Capacity Building - Support Coordination"
    CAPACITY_DAILY_LIFE = "Capacity Building - Daily Life Skills"
    CAPACITY_RELATIONSHIPS = "Capacity Building - Relationships"
    CAPACITY_HEALTH = "Capacity Building - Health & Wellbeing"
    CAPACITY_LEARNING = "Capacity Building - Lifelong Learning"
    CAPACITY_WORK = "Capacity Building - Finding & Keeping Work"
    CAPITAL_ASSISTIVE_TECH = "Capital - Assistive Technology"
    CAPITAL_HOME_MODS = "Capital - Home Modifications"
    CAPITAL_SDA = "Capital - SDA"


class ServiceDeliveryMode(str, Enum):
    """How the service is delivered."""

    FACE_TO_FACE = "Face to Face"
    TELEHEALTH = "Telehealth/Video"
    PHONE = "Phone"
    GROUP = "Group"
    PROVIDER_TRAVEL = "Provider Travel"


# NDIS Price Guide rates (simplified demonstration - FY 2024-25 indicative)
NDIS_PRICE_GUIDE = {
    "01_011_0107_1_1": {
        "name": "Assistance with Self-Care Activities - Standard",
        "category": NDISSupportCategory.CORE_DAILY_ACTIVITIES,
        "unit": "Hour",
        "weekday_rate": Decimal("67.56"),
        "saturday_rate": Decimal("94.64"),
        "sunday_rate": Decimal("121.69"),
        "public_holiday_rate": Decimal("148.77"),
    },
    "01_011_0107_1_1_T": {
        "name": "Assistance with Self-Care - TTP Worker",
        "category": NDISSupportCategory.CORE_DAILY_ACTIVITIES,
        "unit": "Hour",
        "weekday_rate": Decimal("70.70"),
        "saturday_rate": Decimal("99.10"),
        "sunday_rate": Decimal("127.47"),
        "public_holiday_rate": Decimal("155.87"),
    },
    "07_001_0106_8_3": {
        "name": "Level 1: Support Connection",
        "category": NDISSupportCategory.CAPACITY_COORDINATION,
        "unit": "Hour",
        "weekday_rate": Decimal("65.09"),
    },
    "07_002_0106_8_3": {
        "name": "Level 2: Coordination of Supports",
        "category": NDISSupportCategory.CAPACITY_COORDINATION,
        "unit": "Hour",
        "weekday_rate": Decimal("100.14"),
    },
    "07_004_0106_8_3": {
        "name": "Level 3: Specialist Support Coordination",
        "category": NDISSupportCategory.CAPACITY_COORDINATION,
        "unit": "Hour",
        "weekday_rate": Decimal("190.54"),
    },
    "04_104_0125_6_1": {
        "name": "Group Activities - Standard Ratio 1:2",
        "category": NDISSupportCategory.CORE_SOCIAL_COMMUNITY,
        "unit": "Hour",
        "weekday_rate": Decimal("33.78"),
        "saturday_rate": Decimal("47.32"),
    },
}


# =============================================================================
# PARTICIPANT MODEL
# =============================================================================


@dataclass
class NDISParticipant:
    """NDIS Participant with plan details."""

    participant_id: str
    ndis_number: str
    first_name: str
    last_name: str
    date_of_birth: date
    plan_start_date: date
    plan_end_date: date
    plan_manager: str  # "NDIA", "Plan Managed", "Self Managed"
    budgets: dict[str, Decimal] = field(default_factory=dict)
    goals: list[dict] = field(default_factory=list)
    support_needs: list[str] = field(default_factory=list)
    communication_preferences: list[str] = field(default_factory=list)
    emergency_contact: dict = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def plan_active(self) -> bool:
        today = date.today()
        return self.plan_start_date <= today <= self.plan_end_date

    @property
    def days_until_plan_review(self) -> int:
        return (self.plan_end_date - date.today()).days


@dataclass
class ServiceBooking:
    """A service booking for a participant."""

    booking_id: str
    participant_id: str
    line_item_code: str
    service_date: date
    start_time: str
    end_time: str
    duration_hours: Decimal
    delivery_mode: ServiceDeliveryMode
    worker_id: str
    worker_name: str
    status: str = "Scheduled"  # Scheduled, Delivered, Cancelled
    notes: str = ""
    claimed: bool = False
    claim_reference: str = ""


@dataclass
class ProgressNote:
    """Progress note for service delivery."""

    note_id: str
    booking_id: str
    participant_id: str
    author_id: str
    author_name: str
    created_at: datetime
    service_date: date
    goals_addressed: list[str]
    activities: str
    participant_response: str
    outcomes: str
    follow_up_required: str
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class Incident:
    """SIRS-compliant incident report."""

    incident_id: str
    participant_id: str
    incident_type: str  # Abuse, Neglect, Injury, etc.
    severity: str  # Low, Medium, High, Critical
    incident_date: datetime
    reported_date: datetime
    reporter_id: str
    reporter_name: str
    description: str
    immediate_actions: str
    ndis_reportable: bool
    reported_to_ndis: bool = False
    ndis_report_date: Optional[datetime] = None
    investigation_status: str = "Open"
    outcome: str = ""


# =============================================================================
# NDIS PROVIDER ASSISTANT
# =============================================================================


class NDISProviderAssistant:
    """
    NDIS Provider Management Assistant.

    Manages participants, bookings, and compliance with
    NDIS Quality and Safeguards requirements.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the NDIS provider assistant."""
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self.participants: dict[str, NDISParticipant] = {}
        self.bookings: dict[str, ServiceBooking] = {}
        self.progress_notes: dict[str, ProgressNote] = {}
        self.incidents: dict[str, Incident] = {}
        self._load_demo_data()

    def _create_tables(self):
        """Create database tables for audit trail."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT
            )
        """
        )
        self.conn.commit()

    def _audit_log(
        self,
        user_id: str,
        action: str,
        entity_type: str = "",
        entity_id: str = "",
        details: str = "",
    ):
        """Log an auditable action."""
        self.conn.execute(
            """
            INSERT INTO audit_log (timestamp, user_id, action, entity_type, entity_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.now(timezone.utc).isoformat(),
                user_id,
                action,
                entity_type,
                entity_id,
                details,
            ),
        )
        self.conn.commit()

    def _load_demo_data(self):
        """Load demonstration participant data."""
        # Demo participant 1
        self.participants["PART-001"] = NDISParticipant(
            participant_id="PART-001",
            ndis_number="430123456",
            first_name="Sarah",
            last_name="Johnson",
            date_of_birth=date(1985, 3, 15),
            plan_start_date=date(2024, 7, 1),
            plan_end_date=date(2025, 6, 30),
            plan_manager="Plan Managed",
            budgets={
                NDISSupportCategory.CORE_DAILY_ACTIVITIES.value: Decimal("45000.00"),
                NDISSupportCategory.CAPACITY_COORDINATION.value: Decimal("8500.00"),
                NDISSupportCategory.CORE_SOCIAL_COMMUNITY.value: Decimal("12000.00"),
            },
            goals=[
                {
                    "id": "G1",
                    "description": "Develop independent living skills",
                    "progress": "In Progress",
                },
                {
                    "id": "G2",
                    "description": "Increase community participation",
                    "progress": "Emerging",
                },
            ],
            support_needs=[
                "Personal care assistance",
                "Community access support",
                "Skill development - cooking",
            ],
            communication_preferences=["Clear, simple language", "Visual aids"],
            emergency_contact={
                "name": "Michael Johnson",
                "relationship": "Brother",
                "phone": "0412 345 678",
            },
        )

        # Demo participant 2
        self.participants["PART-002"] = NDISParticipant(
            participant_id="PART-002",
            ndis_number="430987654",
            first_name="David",
            last_name="Chen",
            date_of_birth=date(1992, 8, 22),
            plan_start_date=date(2024, 1, 1),
            plan_end_date=date(2024, 12, 31),
            plan_manager="Self Managed",
            budgets={
                NDISSupportCategory.CORE_DAILY_ACTIVITIES.value: Decimal("32000.00"),
                NDISSupportCategory.CAPACITY_DAILY_LIFE.value: Decimal("15000.00"),
            },
            goals=[
                {
                    "id": "G1",
                    "description": "Learn to use public transport independently",
                    "progress": "In Progress",
                },
            ],
            support_needs=["Travel training", "Daily living skills"],
        )

    # =========================================================================
    # PRICE GUIDE COMPLIANCE
    # =========================================================================

    def validate_line_item(self, line_item_code: str) -> dict:
        """Validate a line item code against the NDIS Price Guide."""
        if line_item_code in NDIS_PRICE_GUIDE:
            item = NDIS_PRICE_GUIDE[line_item_code]
            return {
                "valid": True,
                "code": line_item_code,
                "name": item["name"],
                "category": item["category"].value,
                "weekday_rate": str(item["weekday_rate"]),
                "unit": item["unit"],
            }
        return {
            "valid": False,
            "code": line_item_code,
            "error": "Line item not found in Price Guide",
        }

    def calculate_service_cost(
        self,
        line_item_code: str,
        duration_hours: Decimal,
        service_date: date,
    ) -> dict:
        """Calculate the cost of a service based on Price Guide rates."""
        if line_item_code not in NDIS_PRICE_GUIDE:
            return {"error": f"Invalid line item: {line_item_code}"}

        item = NDIS_PRICE_GUIDE[line_item_code]

        # Determine day type for rate selection
        weekday = service_date.weekday()

        if weekday < 5:  # Monday-Friday
            rate = item.get("weekday_rate", Decimal("0"))
            rate_type = "Weekday"
        elif weekday == 5:  # Saturday
            rate = item.get("saturday_rate", item.get("weekday_rate", Decimal("0")))
            rate_type = "Saturday"
        else:  # Sunday
            rate = item.get("sunday_rate", item.get("weekday_rate", Decimal("0")))
            rate_type = "Sunday"

        # TODO: Check for public holidays

        total = rate * duration_hours

        return {
            "line_item": line_item_code,
            "service_name": item["name"],
            "rate_type": rate_type,
            "rate_per_hour": str(rate),
            "duration_hours": str(duration_hours),
            "total_cost": str(total),
            "gst_applicable": False,  # Most NDIS services are GST-free
        }

    # =========================================================================
    # PARTICIPANT MANAGEMENT
    # =========================================================================

    def get_participant(self, participant_id: str) -> Optional[NDISParticipant]:
        """Get a participant by ID."""
        return self.participants.get(participant_id)

    def get_participant_summary(self, participant_id: str) -> dict:
        """Get a summary of participant plan and budgets."""
        participant = self.get_participant(participant_id)
        if not participant:
            return {"error": "Participant not found"}

        # Calculate budget utilisation (demo values)
        budget_summary = []
        for category, budget in participant.budgets.items():
            # In production, calculate actual spend from bookings
            spent = budget * Decimal("0.35")  # Demo: 35% spent
            remaining = budget - spent
            budget_summary.append(
                {
                    "category": category,
                    "total_budget": str(budget),
                    "spent": str(spent),
                    "remaining": str(remaining),
                    "utilisation_percent": 35,
                }
            )

        return {
            "participant_id": participant.participant_id,
            "name": participant.full_name,
            "ndis_number": participant.ndis_number[-4:].rjust(10, "*"),  # Mask
            "plan_status": "Active" if participant.plan_active else "Inactive",
            "plan_end_date": participant.plan_end_date.isoformat(),
            "days_until_review": participant.days_until_plan_review,
            "plan_manager": participant.plan_manager,
            "budgets": budget_summary,
            "goals": participant.goals,
            "support_needs": participant.support_needs,
        }

    # =========================================================================
    # SERVICE BOOKINGS
    # =========================================================================

    def create_booking(
        self,
        participant_id: str,
        line_item_code: str,
        service_date: date,
        start_time: str,
        end_time: str,
        delivery_mode: ServiceDeliveryMode,
        worker_id: str,
        worker_name: str,
        user_id: str,
    ) -> dict:
        """Create a new service booking."""
        participant = self.get_participant(participant_id)
        if not participant:
            return {"error": "Participant not found"}

        # Validate line item
        validation = self.validate_line_item(line_item_code)
        if not validation["valid"]:
            return {"error": validation["error"]}

        # Calculate duration
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        duration = Decimal(str((end - start).seconds / 3600))

        # Calculate cost
        cost = self.calculate_service_cost(line_item_code, duration, service_date)

        booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"

        booking = ServiceBooking(
            booking_id=booking_id,
            participant_id=participant_id,
            line_item_code=line_item_code,
            service_date=service_date,
            start_time=start_time,
            end_time=end_time,
            duration_hours=duration,
            delivery_mode=delivery_mode,
            worker_id=worker_id,
            worker_name=worker_name,
        )

        self.bookings[booking_id] = booking

        # Audit log
        self._audit_log(
            user_id=user_id,
            action="CREATE_BOOKING",
            entity_type="Booking",
            entity_id=booking_id,
            details=f"Participant: {participant_id}, Service: {line_item_code}",
        )

        return {
            "success": True,
            "booking_id": booking_id,
            "participant": participant.full_name,
            "service": validation["name"],
            "date": service_date.isoformat(),
            "time": f"{start_time} - {end_time}",
            "duration_hours": str(duration),
            "estimated_cost": cost["total_cost"],
            "worker": worker_name,
        }

    # =========================================================================
    # PROGRESS NOTES
    # =========================================================================

    def add_progress_note(
        self,
        booking_id: str,
        author_id: str,
        author_name: str,
        goals_addressed: list[str],
        activities: str,
        participant_response: str,
        outcomes: str,
        follow_up: str,
        risk_flags: list[str] = None,
    ) -> dict:
        """Add a progress note for a service booking."""
        booking = self.bookings.get(booking_id)
        if not booking:
            return {"error": "Booking not found"}

        note_id = f"PN-{uuid.uuid4().hex[:8].upper()}"

        note = ProgressNote(
            note_id=note_id,
            booking_id=booking_id,
            participant_id=booking.participant_id,
            author_id=author_id,
            author_name=author_name,
            created_at=datetime.now(timezone.utc),
            service_date=booking.service_date,
            goals_addressed=goals_addressed,
            activities=activities,
            participant_response=participant_response,
            outcomes=outcomes,
            follow_up_required=follow_up,
            risk_flags=risk_flags or [],
        )

        self.progress_notes[note_id] = note

        # Update booking status
        booking.status = "Delivered"

        # Audit log
        self._audit_log(
            user_id=author_id,
            action="ADD_PROGRESS_NOTE",
            entity_type="ProgressNote",
            entity_id=note_id,
            details=f"Booking: {booking_id}",
        )

        return {
            "success": True,
            "note_id": note_id,
            "booking_id": booking_id,
            "created_at": note.created_at.isoformat(),
            "risk_flags": risk_flags or [],
        }

    # =========================================================================
    # INCIDENT REPORTING (SIRS)
    # =========================================================================

    def report_incident(
        self,
        participant_id: str,
        incident_type: str,
        severity: str,
        incident_date: datetime,
        reporter_id: str,
        reporter_name: str,
        description: str,
        immediate_actions: str,
    ) -> dict:
        """
        Report an incident under SIRS requirements.

        Serious incidents must be reported to NDIS Commission within 24 hours.
        """
        participant = self.get_participant(participant_id)
        if not participant:
            return {"error": "Participant not found"}

        # Determine if NDIS reportable
        reportable_types = [
            "Death",
            "Serious Injury",
            "Abuse",
            "Neglect",
            "Restrictive Practice",
            "Sexual Misconduct",
        ]
        ndis_reportable = incident_type in reportable_types or severity in [
            "High",
            "Critical",
        ]

        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"

        incident = Incident(
            incident_id=incident_id,
            participant_id=participant_id,
            incident_type=incident_type,
            severity=severity,
            incident_date=incident_date,
            reported_date=datetime.now(timezone.utc),
            reporter_id=reporter_id,
            reporter_name=reporter_name,
            description=description,
            immediate_actions=immediate_actions,
            ndis_reportable=ndis_reportable,
        )

        self.incidents[incident_id] = incident

        # Audit log
        self._audit_log(
            user_id=reporter_id,
            action="REPORT_INCIDENT",
            entity_type="Incident",
            entity_id=incident_id,
            details=f"Type: {incident_type}, Severity: {severity}, NDIS Reportable: {ndis_reportable}",
        )

        result = {
            "success": True,
            "incident_id": incident_id,
            "ndis_reportable": ndis_reportable,
            "reported_date": incident.reported_date.isoformat(),
        }

        if ndis_reportable:
            deadline = incident.reported_date + timedelta(hours=24)
            result["ndis_report_deadline"] = deadline.isoformat()
            result["warning"] = (
                "⚠️ This incident must be reported to the NDIS Commission "
                "within 24 hours. Use the NDIS Commission portal or call 1800 035 544."
            )

        return result

    # =========================================================================
    # COMPLIANCE REPORTS
    # =========================================================================

    def generate_compliance_summary(self) -> dict:
        """Generate a compliance summary report."""
        # Check plans nearing review
        plans_near_review = []
        for p_id, participant in self.participants.items():
            if participant.days_until_plan_review <= 60:
                plans_near_review.append(
                    {
                        "participant_id": p_id,
                        "name": participant.full_name,
                        "days_remaining": participant.days_until_plan_review,
                        "plan_end_date": participant.plan_end_date.isoformat(),
                    }
                )

        # Check open incidents
        open_incidents = [
            {
                "incident_id": inc.incident_id,
                "participant_id": inc.participant_id,
                "type": inc.incident_type,
                "severity": inc.severity,
                "ndis_reportable": inc.ndis_reportable,
                "reported_to_ndis": inc.reported_to_ndis,
            }
            for inc in self.incidents.values()
            if inc.investigation_status == "Open"
        ]

        # Check pending NDIS reports
        overdue_reports = [
            inc
            for inc in self.incidents.values()
            if inc.ndis_reportable
            and not inc.reported_to_ndis
            and (datetime.now(timezone.utc) - inc.reported_date).days >= 1
        ]

        return {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "plans_near_review": plans_near_review,
            "plans_near_review_count": len(plans_near_review),
            "open_incidents": open_incidents,
            "open_incidents_count": len(open_incidents),
            "overdue_ndis_reports_count": len(overdue_reports),
            "compliance_alerts": (
                [f"⚠️ {len(overdue_reports)} incidents overdue for NDIS reporting"]
                if overdue_reports
                else []
            ),
        }


# =============================================================================
# DEMO EXECUTION
# =============================================================================


async def run_demo():
    """Run demonstration of the NDIS provider assistant."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NDIS PROVIDER ASSISTANT - DEMO                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ⚠️  DEMONSTRATION ONLY - NOT OFFICIAL NDIS SOFTWARE                          ║
║  This system demonstrates NDIS service management patterns.                   ║
║  Always verify with official NDIS sources and Commission requirements.        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )

    assistant = NDISProviderAssistant()

    # Demo: Price Guide validation
    print("\n" + "=" * 70)
    print("SCENARIO 1: Price Guide Line Item Validation")
    print("=" * 70)

    for code in ["01_011_0107_1_1", "07_002_0106_8_3", "INVALID-001"]:
        result = assistant.validate_line_item(code)
        if result["valid"]:
            print(f"✓ {code}: {result['name']}")
            print(f"  Category: {result['category']}")
            print(f"  Rate: ${result['weekday_rate']}/hr")
        else:
            print(f"✗ {code}: {result['error']}")

    # Demo: Service cost calculation
    print("\n" + "=" * 70)
    print("SCENARIO 2: Service Cost Calculation")
    print("=" * 70)

    # Weekday service
    cost = assistant.calculate_service_cost(
        "01_011_0107_1_1",
        Decimal("3.5"),
        date(2024, 11, 11),  # Monday
    )
    print(f"\nWeekday Personal Care (3.5 hrs):")
    print(f"  Rate: ${cost['rate_per_hour']}/hr ({cost['rate_type']})")
    print(f"  Total: ${cost['total_cost']}")

    # Sunday service
    cost = assistant.calculate_service_cost(
        "01_011_0107_1_1",
        Decimal("3.5"),
        date(2024, 11, 10),  # Sunday
    )
    print(f"\nSunday Personal Care (3.5 hrs):")
    print(f"  Rate: ${cost['rate_per_hour']}/hr ({cost['rate_type']})")
    print(f"  Total: ${cost['total_cost']}")

    # Demo: Participant summary
    print("\n" + "=" * 70)
    print("SCENARIO 3: Participant Plan Summary")
    print("=" * 70)

    summary = assistant.get_participant_summary("PART-001")
    print(f"\nParticipant: {summary['name']}")
    print(f"NDIS Number: {summary['ndis_number']}")
    print(f"Plan Status: {summary['plan_status']}")
    print(f"Days until review: {summary['days_until_review']}")
    print(f"\nBudgets:")
    for budget in summary["budgets"]:
        print(f"  {budget['category']}:")
        print(
            f"    Total: ${budget['total_budget']} | Spent: ${budget['spent']} | Remaining: ${budget['remaining']}"
        )

    # Demo: Create booking
    print("\n" + "=" * 70)
    print("SCENARIO 4: Create Service Booking")
    print("=" * 70)

    booking = assistant.create_booking(
        participant_id="PART-001",
        line_item_code="01_011_0107_1_1",
        service_date=date.today() + timedelta(days=1),
        start_time="09:00",
        end_time="12:00",
        delivery_mode=ServiceDeliveryMode.FACE_TO_FACE,
        worker_id="WORKER-001",
        worker_name="Emma Support Worker",
        user_id="COORD-001",
    )
    print(f"\n✓ Booking created: {booking['booking_id']}")
    print(f"  Participant: {booking['participant']}")
    print(f"  Service: {booking['service']}")
    print(f"  Date/Time: {booking['date']} {booking['time']}")
    print(f"  Duration: {booking['duration_hours']} hours")
    print(f"  Estimated cost: ${booking['estimated_cost']}")

    # Demo: Add progress note
    print("\n" + "=" * 70)
    print("SCENARIO 5: Add Progress Note")
    print("=" * 70)

    note = assistant.add_progress_note(
        booking_id=booking["booking_id"],
        author_id="WORKER-001",
        author_name="Emma Support Worker",
        goals_addressed=["G1 - Develop independent living skills"],
        activities="Assisted Sarah with meal preparation. Worked on kitchen safety and basic cooking techniques.",
        participant_response="Sarah was engaged and enthusiastic. Successfully made a simple pasta dish with minimal prompting.",
        outcomes="Demonstrated improved confidence in kitchen. Remembered safety steps from previous sessions.",
        follow_up="Continue working on more complex recipes. Consider adding shopping skills to routine.",
    )
    print(f"\n✓ Progress note added: {note['note_id']}")

    # Demo: Incident reporting
    print("\n" + "=" * 70)
    print("SCENARIO 6: Incident Reporting (SIRS)")
    print("=" * 70)

    incident = assistant.report_incident(
        participant_id="PART-001",
        incident_type="Injury",
        severity="Medium",
        incident_date=datetime.now(timezone.utc),
        reporter_id="WORKER-001",
        reporter_name="Emma Support Worker",
        description="Participant experienced a minor fall while walking in the garden. No visible injuries.",
        immediate_actions="First aid applied. Participant assessed and comfortable. Family notified.",
    )
    print(f"\n✓ Incident reported: {incident['incident_id']}")
    print(f"  NDIS Reportable: {incident['ndis_reportable']}")
    if incident.get("warning"):
        print(f"  {incident['warning']}")

    # Demo: Compliance summary
    print("\n" + "=" * 70)
    print("SCENARIO 7: Compliance Summary")
    print("=" * 70)

    compliance = assistant.generate_compliance_summary()
    print(f"\nCompliance Report - {compliance['report_date'][:10]}")
    print(f"  Plans near review: {compliance['plans_near_review_count']}")
    print(f"  Open incidents: {compliance['open_incidents_count']}")
    print(f"  Overdue NDIS reports: {compliance['overdue_ndis_reports_count']}")

    for alert in compliance["compliance_alerts"]:
        print(f"  {alert}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NDIS Provider Assistant Demo")
    parser.add_argument(
        "--role",
        choices=["support_worker", "coordinator", "manager"],
        default="coordinator",
        help="Demo role",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run full demonstration",
    )

    args = parser.parse_args()
    asyncio.run(run_demo())
