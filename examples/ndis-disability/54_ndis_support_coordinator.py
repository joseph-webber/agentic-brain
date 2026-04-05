#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 54: NDIS Support Coordination Assistant
=================================================

AI-powered assistant for NDIS Support Coordinators to manage their caseload,
research providers, and support participants effectively.

CRITICAL: On-premise deployment for participant privacy!

This system helps Support Coordinators with:
- Participant caseload management
- Provider research and matching
- Service agreement generation
- Plan review preparation
- Progress report drafting
- Stakeholder communication
- Capacity building tracking
- Goal progress monitoring

Architecture (Privacy-First):
    ┌──────────────────────────────────────────────────────────────┐
    │               SUPPORT COORDINATION ASSISTANT                  │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐  │
    │  │  Ollama  │  │  Local Data  │  │   Coordination Agent   │  │
    │  │  (Local) │◄─┤  (Encrypted) │◄─┤  (This Application)    │  │
    │  └──────────┘  └──────────────┘  └────────────────────────┘  │
    │       │              │                      │                 │
    │       └──────────────┴──────────────────────┘                 │
    │              ALL PARTICIPANT DATA STAYS LOCAL                 │
    └──────────────────────────────────────────────────────────────┘

IMPORTANT DISCLAIMERS:
    ⚠️  This is NOT official NDIS software
    ⚠️  Always verify information with official NDIS sources
    ⚠️  This is a demonstration/educational tool only
    ⚠️  Support coordination requires registered NDIS providers

Support Coordination Levels:
    - Support Connection: Help finding and connecting to supports
    - Coordination of Supports: Coordinate multiple services
    - Specialist Support Coordination: Complex needs, specialist expertise

Usage:
    python examples/54_ndis_support_coordinator.py
    python examples/54_ndis_support_coordinator.py --demo
    python examples/54_ndis_support_coordinator.py --caseload
    python examples/54_ndis_support_coordinator.py --provider-search

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b
"""

import argparse
import asyncio
import json
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ══════════════════════════════════════════════════════════════════════════════
# DISCLAIMERS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

COORDINATOR_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                           IMPORTANT DISCLAIMER                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This is NOT official NDIS software.                                         ║
║  This is a demonstration tool for support coordination workflows.            ║
║                                                                              ║
║  • Support Coordination must be delivered by registered providers            ║
║  • Always verify information with official NDIS sources                      ║
║  • This tool does not replace professional judgment                          ║
║  • All participant data shown is FICTIONAL                                   ║
║                                                                              ║
║  For official information: ndis.gov.au | ndiscommission.gov.au              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


class CoordinationType(Enum):
    """Types of support coordination."""

    SUPPORT_CONNECTION = "Support Connection"
    COORDINATION_OF_SUPPORTS = "Coordination of Supports"
    SPECIALIST = "Specialist Support Coordination"


class ParticipantPriority(Enum):
    """Participant priority levels."""

    URGENT = "Urgent"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    STABLE = "Stable"


class TaskStatus(Enum):
    """Task status."""

    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    WAITING = "Waiting on External"
    COMPLETED = "Completed"
    OVERDUE = "Overdue"


class GoalProgress(Enum):
    """Goal progress status."""

    NOT_STARTED = "Not Started"
    EARLY_STAGES = "Early Stages"
    PROGRESSING = "Progressing Well"
    ON_TRACK = "On Track"
    ACHIEVED = "Achieved"
    NEEDS_REVIEW = "Needs Review"


class PlanManagerType(Enum):
    """Plan management type."""

    NDIA_MANAGED = "NDIA Managed"
    PLAN_MANAGED = "Plan Managed"
    SELF_MANAGED = "Self Managed"
    COMBINATION = "Combination"


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ParticipantCase:
    """A participant on the coordinator's caseload."""

    participant_id: str
    first_name: str  # Would be encrypted in production
    last_name: str  # Would be encrypted in production
    coordination_type: CoordinationType
    plan_start: str
    plan_end: str
    plan_manager: PlanManagerType
    sc_budget: float  # Support Coordination budget
    sc_spent: float
    priority: ParticipantPriority
    primary_disability: str
    communication_needs: str
    key_contacts: list[dict]
    goals: list[dict]
    active_providers: list[str]
    notes: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    last_contact: Optional[str] = None
    next_review: Optional[str] = None

    def days_until_review(self) -> Optional[int]:
        """Days until plan review."""
        if not self.next_review:
            return None
        try:
            review = datetime.strptime(self.next_review, "%Y-%m-%d")
            return (review - datetime.now()).days
        except ValueError:
            return None

    def budget_remaining(self) -> float:
        """Remaining coordination budget."""
        return self.sc_budget - self.sc_spent

    def budget_percentage_used(self) -> float:
        """Percentage of budget used."""
        if self.sc_budget == 0:
            return 0
        return (self.sc_spent / self.sc_budget) * 100


@dataclass
class Provider:
    """A service provider in the directory."""

    provider_id: str
    name: str
    registration_groups: list[str]
    services: list[str]
    locations: list[str]
    phone: str
    email: str
    website: str
    wheelchair_accessible: bool
    accepting_new: bool
    languages: list[str]
    specializations: list[str]
    rating: float
    reviews: int
    price_guide_adherence: bool
    description: str


@dataclass
class ServiceAgreement:
    """A service agreement between participant and provider."""

    agreement_id: str
    participant_id: str
    provider_id: str
    provider_name: str
    services: list[str]
    support_category: str
    start_date: str
    end_date: str
    total_value: float
    price_per_hour: float
    hours_allocated: float
    hours_used: float
    status: str  # Draft, Active, Suspended, Ended
    signed_participant: bool
    signed_provider: bool
    created_date: str


@dataclass
class ProgressReport:
    """Progress report for a participant."""

    report_id: str
    participant_id: str
    period_start: str
    period_end: str
    report_type: str  # Monthly, Quarterly, Plan Review
    goals_summary: list[dict]
    services_accessed: list[dict]
    outcomes_achieved: list[str]
    challenges: list[str]
    recommendations: list[str]
    hours_used: float
    created_by: str
    created_date: str
    status: str  # Draft, Submitted, Accepted


@dataclass
class CoordinatorTask:
    """A task for the support coordinator."""

    task_id: str
    participant_id: str
    task_type: str
    description: str
    due_date: str
    status: TaskStatus
    priority: str
    assigned_to: str
    notes: str = ""
    completed_date: Optional[str] = None

    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.status == TaskStatus.COMPLETED:
            return False
        try:
            due = datetime.strptime(self.due_date, "%Y-%m-%d")
            return due < datetime.now()
        except ValueError:
            return False


# ══════════════════════════════════════════════════════════════════════════════
# DATA STORE
# ══════════════════════════════════════════════════════════════════════════════


class SupportCoordinationStore:
    """Local data store for support coordination."""

    def __init__(self):
        self.participants: dict[str, ParticipantCase] = {}
        self.providers: dict[str, Provider] = {}
        self.agreements: dict[str, ServiceAgreement] = {}
        self.reports: dict[str, ProgressReport] = {}
        self.tasks: dict[str, CoordinatorTask] = {}
        self.activity_log: list[dict] = []

    def log_activity(
        self,
        participant_id: str,
        activity_type: str,
        description: str,
        minutes: int = 0,
    ):
        """Log a coordination activity."""
        self.activity_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "participant_id": participant_id,
                "activity_type": activity_type,
                "description": description,
                "minutes": minutes,
            }
        )

    def get_caseload(self) -> list[ParticipantCase]:
        """Get all participants on caseload."""
        return list(self.participants.values())

    def get_urgent_cases(self) -> list[ParticipantCase]:
        """Get urgent priority cases."""
        return [
            p
            for p in self.participants.values()
            if p.priority in [ParticipantPriority.URGENT, ParticipantPriority.HIGH]
        ]

    def get_upcoming_reviews(self, days: int = 60) -> list[ParticipantCase]:
        """Get cases with upcoming plan reviews."""
        upcoming = []
        for p in self.participants.values():
            days_left = p.days_until_review()
            if days_left is not None and 0 <= days_left <= days:
                upcoming.append(p)
        return sorted(upcoming, key=lambda x: x.days_until_review() or 999)

    def search_providers(
        self,
        service_type: Optional[str] = None,
        location: Optional[str] = None,
        specialization: Optional[str] = None,
        accepting_new: bool = True,
    ) -> list[Provider]:
        """Search for providers."""
        results = list(self.providers.values())

        if accepting_new:
            results = [p for p in results if p.accepting_new]

        if service_type:
            service_lower = service_type.lower()
            results = [
                p
                for p in results
                if any(service_lower in s.lower() for s in p.services)
            ]

        if location:
            location_lower = location.lower()
            results = [
                p
                for p in results
                if any(location_lower in loc.lower() for loc in p.locations)
            ]

        if specialization:
            spec_lower = specialization.lower()
            results = [
                p
                for p in results
                if any(spec_lower in s.lower() for s in p.specializations)
            ]

        return sorted(results, key=lambda x: x.rating, reverse=True)

    def get_pending_tasks(self) -> list[CoordinatorTask]:
        """Get all pending tasks."""
        pending = []
        for task in self.tasks.values():
            if task.status not in [TaskStatus.COMPLETED]:
                if task.is_overdue():
                    task.status = TaskStatus.OVERDUE
                pending.append(task)
        return sorted(pending, key=lambda x: x.due_date)

    def get_participant_agreements(self, participant_id: str) -> list[ServiceAgreement]:
        """Get service agreements for a participant."""
        return [
            a for a in self.agreements.values() if a.participant_id == participant_id
        ]

    def calculate_time_spent(self, participant_id: str, days: int = 30) -> dict:
        """Calculate time spent on participant in last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        activities = [
            a
            for a in self.activity_log
            if a["participant_id"] == participant_id
            and datetime.fromisoformat(a["timestamp"]) > cutoff
        ]

        total_minutes = sum(a["minutes"] for a in activities)
        by_type = {}
        for a in activities:
            atype = a["activity_type"]
            by_type[atype] = by_type.get(atype, 0) + a["minutes"]

        return {
            "total_minutes": total_minutes,
            "total_hours": round(total_minutes / 60, 1),
            "by_type": by_type,
            "activity_count": len(activities),
        }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA GENERATOR
# ══════════════════════════════════════════════════════════════════════════════


class DemoDataGenerator:
    """Generate realistic demo data."""

    FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey"]
    LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones"]

    DISABILITIES = [
        "Autism Spectrum Disorder",
        "Intellectual Disability",
        "Cerebral Palsy",
        "Acquired Brain Injury",
        "Psychosocial Disability",
        "Multiple Sclerosis",
        "Spinal Cord Injury",
        "Hearing Impairment",
    ]

    GOALS = [
        {
            "statement": "Increase independence in daily living",
            "category": "Daily Living",
        },
        {"statement": "Improve social connections", "category": "Social & Community"},
        {"statement": "Maintain health and wellbeing", "category": "Health"},
        {"statement": "Develop employment skills", "category": "Employment"},
        {
            "statement": "Participate in community activities",
            "category": "Social & Community",
        },
        {"statement": "Improve communication skills", "category": "Capacity Building"},
    ]

    @classmethod
    def create_demo_participants(cls, count: int = 8) -> list[ParticipantCase]:
        """Create demo participant cases."""
        participants = []
        priorities = [
            ParticipantPriority.URGENT,
            ParticipantPriority.HIGH,
            ParticipantPriority.MEDIUM,
            ParticipantPriority.MEDIUM,
            ParticipantPriority.LOW,
            ParticipantPriority.STABLE,
            ParticipantPriority.STABLE,
            ParticipantPriority.STABLE,
        ]

        coordination_types = [
            CoordinationType.SPECIALIST,
            CoordinationType.SPECIALIST,
            CoordinationType.COORDINATION_OF_SUPPORTS,
            CoordinationType.COORDINATION_OF_SUPPORTS,
            CoordinationType.COORDINATION_OF_SUPPORTS,
            CoordinationType.SUPPORT_CONNECTION,
            CoordinationType.SUPPORT_CONNECTION,
            CoordinationType.SUPPORT_CONNECTION,
        ]

        for i in range(count):
            first = cls.FIRST_NAMES[i % len(cls.FIRST_NAMES)]
            last = cls.LAST_NAMES[i % len(cls.LAST_NAMES)]

            # Vary plan dates
            plan_start = datetime.now() - timedelta(days=180 + i * 30)
            plan_end = plan_start + timedelta(days=365)
            review_days = (plan_end - datetime.now()).days

            # Vary budgets based on coordination type
            coord_type = coordination_types[i % len(coordination_types)]
            if coord_type == CoordinationType.SPECIALIST:
                budget = 12000 + i * 500
            elif coord_type == CoordinationType.COORDINATION_OF_SUPPORTS:
                budget = 8000 + i * 300
            else:
                budget = 3000 + i * 200

            spent = budget * (0.3 + (i % 5) * 0.1)

            goals = [
                {
                    **cls.GOALS[j % len(cls.GOALS)],
                    "progress": GoalProgress.PROGRESSING.value,
                }
                for j in range(2 + i % 3)
            ]

            participants.append(
                ParticipantCase(
                    participant_id=f"P{i+1:03d}",
                    first_name=first,
                    last_name=last,
                    coordination_type=coord_type,
                    plan_start=plan_start.strftime("%Y-%m-%d"),
                    plan_end=plan_end.strftime("%Y-%m-%d"),
                    plan_manager=(
                        PlanManagerType.PLAN_MANAGED
                        if i % 3 == 0
                        else PlanManagerType.NDIA_MANAGED
                    ),
                    sc_budget=budget,
                    sc_spent=spent,
                    priority=priorities[i % len(priorities)],
                    primary_disability=cls.DISABILITIES[i % len(cls.DISABILITIES)],
                    communication_needs=(
                        "Prefers written communication" if i % 3 == 0 else ""
                    ),
                    key_contacts=[
                        {
                            "name": "Family Contact",
                            "role": "Parent/Guardian",
                            "phone": "04XX XXX XXX",
                        },
                    ],
                    goals=goals,
                    active_providers=(
                        ["Provider A", "Provider B"] if i % 2 == 0 else ["Provider A"]
                    ),
                    last_contact=(datetime.now() - timedelta(days=i * 3)).strftime(
                        "%Y-%m-%d"
                    ),
                    next_review=(
                        plan_end.strftime("%Y-%m-%d") if review_days < 90 else None
                    ),
                )
            )

        return participants

    @classmethod
    def create_demo_providers(cls) -> list[Provider]:
        """Create demo providers."""
        return [
            Provider(
                provider_id="PRV001",
                name="Allied Health Group",  # Generic name
                registration_groups=["Therapeutic Supports", "Capacity Building"],
                services=[
                    "Occupational Therapy",
                    "Physiotherapy",
                    "Speech Pathology",
                    "Psychology",
                ],
                locations=["City Centre", "Eastern Suburbs", "Coastal"],
                phone="08 1234 5678",
                email="info@example-health.com.au",
                website="www.example-health.com.au",
                wheelchair_accessible=True,
                accepting_new=True,
                languages=["English", "Mandarin", "Vietnamese"],
                specializations=[
                    "Autism",
                    "Intellectual Disability",
                    "Physical Disability",
                ],
                rating=4.8,
                reviews=124,
                price_guide_adherence=True,
                description="Multidisciplinary allied health team providing holistic therapy services.",
            ),
            Provider(
                provider_id="PRV002",
                name="Disability Support Services",  # Generic name
                registration_groups=[
                    "Daily Personal Activities",
                    "Community Participation",
                ],
                services=[
                    "Personal Care",
                    "Community Access",
                    "Domestic Assistance",
                    "Respite",
                ],
                locations=["Metro Area", "Hills Region"],
                phone="08 2345 6789",
                email="support@example-care.com.au",
                website="www.example-care.com.au",
                wheelchair_accessible=True,
                accepting_new=True,
                languages=["English", "Italian", "Greek"],
                specializations=["Physical Disability", "Aged Care", "Complex Needs"],
                rating=4.5,
                reviews=89,
                price_guide_adherence=True,
                description="Experienced team providing in-home and community support services.",
            ),
            Provider(
                provider_id="PRV003",
                name="Positive Behaviour Practitioners",  # Generic name
                registration_groups=["Specialist Behaviour Support"],
                services=[
                    "Behaviour Support",
                    "Positive Behaviour Planning",
                    "Capacity Building",
                ],
                locations=["Metro Wide"],
                phone="08 3456 7890",
                email="referrals@example-behaviour.com.au",
                website="www.example-behaviour.com.au",
                wheelchair_accessible=True,
                accepting_new=False,  # Waitlist
                languages=["English"],
                specializations=["Autism", "Challenging Behaviour", "Psychosocial"],
                rating=4.9,
                reviews=67,
                price_guide_adherence=True,
                description="Specialist behaviour practitioners with extensive NDIS experience.",
            ),
            Provider(
                provider_id="PRV004",
                name="Independence Plus",  # Generic name
                registration_groups=["Assistive Technology", "Home Modifications"],
                services=[
                    "Assistive Technology Assessment",
                    "Equipment Supply",
                    "Home Modifications",
                ],
                locations=["Metro Area", "Regional"],
                phone="08 4567 8901",
                email="hello@example-assistive.com.au",
                website="www.example-assistive.com.au",
                wheelchair_accessible=True,
                accepting_new=True,
                languages=["English"],
                specializations=[
                    "Mobility",
                    "Home Automation",
                    "Communication Devices",
                ],
                rating=4.6,
                reviews=45,
                price_guide_adherence=True,
                description="Helping participants achieve independence through technology and home modifications.",
            ),
            Provider(
                provider_id="PRV005",
                name="Employment Support Network",  # Generic name
                registration_groups=[
                    "Finding and Keeping a Job",
                    "School Leaver Employment Supports",
                ],
                services=[
                    "Employment Support",
                    "Job Coaching",
                    "Workplace Training",
                    "SLES",
                ],
                locations=["Metro Area"],
                phone="08 5678 9012",
                email="jobs@example-employment.com.au",
                website="www.example-employment.com.au",
                wheelchair_accessible=True,
                accepting_new=True,
                languages=["English", "Arabic", "Dari"],
                specializations=["Intellectual Disability", "Autism", "Mental Health"],
                rating=4.4,
                reviews=78,
                price_guide_adherence=True,
                description="Supporting participants to find and maintain meaningful employment.",
            ),
            Provider(
                provider_id="PRV006",
                name="Support Network Transport",  # Generic name
                registration_groups=["Transport"],
                services=["NDIS Transport", "Accessible Vehicles", "Travel Training"],
                locations=["Metro Area"],
                phone="08 6789 0123",
                email="book@example-transport.com.au",
                website="www.example-transport.com.au",
                wheelchair_accessible=True,
                accepting_new=True,
                languages=["English"],
                specializations=[
                    "Wheelchair Accessible Transport",
                    "Medical Appointments",
                ],
                rating=4.3,
                reviews=156,
                price_guide_adherence=True,
                description="Reliable accessible transport across the metro area.",
            ),
        ]

    @classmethod
    def create_demo_tasks(
        cls, participants: list[ParticipantCase]
    ) -> list[CoordinatorTask]:
        """Create demo tasks."""
        tasks = []
        task_types = [
            ("Plan Review Prep", "Prepare documentation for upcoming plan review"),
            ("Provider Search", "Research and identify suitable providers"),
            ("Follow Up", "Follow up on service commencement"),
            ("Progress Report", "Complete monthly progress report"),
            ("Service Agreement", "Finalize service agreement"),
        ]

        for i, p in enumerate(participants[:5]):
            task_type, desc = task_types[i % len(task_types)]
            days_offset = -2 if i == 0 else (i * 5)  # First one overdue

            tasks.append(
                CoordinatorTask(
                    task_id=f"T{i+1:03d}",
                    participant_id=p.participant_id,
                    task_type=task_type,
                    description=f"{desc} for {p.first_name}",
                    due_date=(datetime.now() + timedelta(days=days_offset)).strftime(
                        "%Y-%m-%d"
                    ),
                    status=(
                        TaskStatus.OVERDUE if days_offset < 0 else TaskStatus.PENDING
                    ),
                    priority=(
                        "High"
                        if p.priority
                        in [ParticipantPriority.URGENT, ParticipantPriority.HIGH]
                        else "Medium"
                    ),
                    assigned_to="Coordinator",
                )
            )

        return tasks


# ══════════════════════════════════════════════════════════════════════════════
# SUPPORT COORDINATION ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class SupportCoordinationAssistant:
    """
    AI Assistant for NDIS Support Coordinators.

    Helps manage caseload, research providers, and coordinate supports.
    """

    def __init__(
        self, store: SupportCoordinationStore, coordinator_name: str = "Coordinator"
    ):
        self.store = store
        self.coordinator_name = coordinator_name

    def get_dashboard(self) -> str:
        """Get coordinator dashboard."""
        caseload = self.store.get_caseload()
        urgent = self.store.get_urgent_cases()
        upcoming_reviews = self.store.get_upcoming_reviews(days=60)
        pending_tasks = self.store.get_pending_tasks()
        overdue_tasks = [t for t in pending_tasks if t.status == TaskStatus.OVERDUE]

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  SUPPORT COORDINATION DASHBOARD                                               ║
║  {datetime.now().strftime('%Y-%m-%d %H:%M')}                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Welcome, {self.coordinator_name}!

📋 CASELOAD SUMMARY
   Total Participants: {len(caseload)}
   ├─ Specialist SC: {sum(1 for p in caseload if p.coordination_type == CoordinationType.SPECIALIST)}
   ├─ Coordination of Supports: {sum(1 for p in caseload if p.coordination_type == CoordinationType.COORDINATION_OF_SUPPORTS)}
   └─ Support Connection: {sum(1 for p in caseload if p.coordination_type == CoordinationType.SUPPORT_CONNECTION)}

"""
        if urgent:
            output += f"""🚨 URGENT ATTENTION ({len(urgent)})
"""
            for p in urgent[:3]:
                output += f"   • {p.first_name} {p.last_name[0]}. ({p.participant_id}) - {p.priority.value}\n"

        if overdue_tasks:
            output += f"""
⏰ OVERDUE TASKS ({len(overdue_tasks)})
"""
            for t in overdue_tasks[:3]:
                output += f"   • {t.task_type}: {t.description[:40]}...\n"

        if upcoming_reviews:
            output += f"""
📅 UPCOMING PLAN REVIEWS ({len(upcoming_reviews)})
"""
            for p in upcoming_reviews[:3]:
                days = p.days_until_review()
                output += f"   • {p.first_name} {p.last_name[0]}. - {days} days\n"

        output += f"""
📊 TODAY'S TASKS: {len(pending_tasks)} pending

QUICK ACTIONS
{'─' * 50}
1. View caseload
2. Search providers
3. View tasks
4. Review participant
5. Generate report
6. Upcoming reviews
"""
        return output

    def view_caseload(self, filter_priority: Optional[str] = None) -> str:
        """View caseload summary."""
        caseload = self.store.get_caseload()

        if filter_priority:
            try:
                priority = ParticipantPriority[filter_priority.upper()]
                caseload = [p for p in caseload if p.priority == priority]
            except KeyError:
                pass

        # Sort by priority
        priority_order = {
            ParticipantPriority.URGENT: 0,
            ParticipantPriority.HIGH: 1,
            ParticipantPriority.MEDIUM: 2,
            ParticipantPriority.LOW: 3,
            ParticipantPriority.STABLE: 4,
        }
        caseload = sorted(caseload, key=lambda p: priority_order.get(p.priority, 5))

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CASELOAD OVERVIEW                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Total: {len(caseload)} participants

"""
        for p in caseload:
            priority_emoji = {
                ParticipantPriority.URGENT: "🚨",
                ParticipantPriority.HIGH: "⚠️",
                ParticipantPriority.MEDIUM: "📋",
                ParticipantPriority.LOW: "📌",
                ParticipantPriority.STABLE: "✅",
            }.get(p.priority, "📋")

            coord_abbrev = {
                CoordinationType.SPECIALIST: "SSC",
                CoordinationType.COORDINATION_OF_SUPPORTS: "CoS",
                CoordinationType.SUPPORT_CONNECTION: "SC",
            }.get(p.coordination_type, "SC")

            budget_pct = p.budget_percentage_used()
            budget_bar = "█" * int(budget_pct / 10) + "░" * (10 - int(budget_pct / 10))

            review_info = ""
            days = p.days_until_review()
            if days is not None:
                if days <= 30:
                    review_info = f" ⏰ Review in {days} days!"
                elif days <= 60:
                    review_info = f" 📅 Review in {days} days"

            output += f"""
{priority_emoji} {p.participant_id} | {p.first_name} {p.last_name[0]}. | {coord_abbrev}
   {p.primary_disability}
   Budget: [{budget_bar}] ${p.budget_remaining():,.0f} remaining
   Last contact: {p.last_contact or 'Not recorded'}{review_info}
"""

        output += f"""
{'─' * 70}
Legend: SSC=Specialist, CoS=Coordination of Supports, SC=Support Connection
        🚨=Urgent, ⚠️=High, 📋=Medium, 📌=Low, ✅=Stable
"""
        return output

    def view_participant(self, participant_id: str) -> str:
        """View detailed participant information."""
        participant = self.store.participants.get(participant_id)

        if not participant:
            return f"❌ Participant {participant_id} not found."

        p = participant
        agreements = self.store.get_participant_agreements(participant_id)
        time_spent = self.store.calculate_time_spent(participant_id)

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PARTICIPANT DETAILS                                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

👤 {p.first_name} {p.last_name}
   ID: {p.participant_id}
   Priority: {p.priority.value}

📋 COORDINATION
   Type: {p.coordination_type.value}
   Plan Period: {p.plan_start} to {p.plan_end}
   Plan Manager: {p.plan_manager.value}

💰 BUDGET
   Total: ${p.sc_budget:,.2f}
   Spent: ${p.sc_spent:,.2f} ({p.budget_percentage_used():.0f}%)
   Remaining: ${p.budget_remaining():,.2f}

🎯 GOALS
"""
        for i, goal in enumerate(p.goals, 1):
            output += f"   {i}. {goal['statement']}\n"
            output += f"      Category: {goal['category']} | Progress: {goal.get('progress', 'N/A')}\n"

        output += """
🏢 ACTIVE PROVIDERS
"""
        for provider in p.active_providers:
            output += f"   • {provider}\n"

        if agreements:
            output += f"""
📝 SERVICE AGREEMENTS ({len(agreements)})
"""
            for ag in agreements:
                output += (
                    f"   • {ag.provider_name}: ${ag.total_value:,.2f} ({ag.status})\n"
                )

        output += f"""
⏱️ TIME SPENT (Last 30 days)
   Total: {time_spent['total_hours']} hours
   Activities: {time_spent['activity_count']}

📞 KEY CONTACTS
"""
        for contact in p.key_contacts:
            output += (
                f"   • {contact['name']} ({contact['role']}): {contact['phone']}\n"
            )

        if p.communication_needs:
            output += f"\n💬 COMMUNICATION NEEDS\n   {p.communication_needs}\n"

        return output

    def search_providers(
        self, service_type: str = "", location: str = "", specialization: str = ""
    ) -> str:
        """Search for providers."""
        providers = self.store.search_providers(
            service_type=service_type if service_type else None,
            location=location if location else None,
            specialization=specialization if specialization else None,
        )

        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  PROVIDER SEARCH RESULTS                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        if service_type:
            output += f"Service: {service_type}\n"
        if location:
            output += f"Location: {location}\n"
        if specialization:
            output += f"Specialization: {specialization}\n"

        output += f"\nFound {len(providers)} providers:\n\n"

        if not providers:
            output += """
No providers found matching your criteria.

Try:
• Broader search terms
• Different location
• Removing filters

Or contact NDIS for provider referral support.
"""
            return output

        for provider in providers:
            stars = "⭐" * int(provider.rating)
            accepting = "✅ Accepting" if provider.accepting_new else "⏸️ Waitlist"

            output += f"""
{'─' * 70}
🏢 {provider.name}
   {provider.description}

   Services: {', '.join(provider.services[:4])}
   Locations: {', '.join(provider.locations[:3])}
   Specializations: {', '.join(provider.specializations[:3])}

   Rating: {stars} ({provider.rating}/5 from {provider.reviews} reviews)
   Status: {accepting}
   {'♿ Wheelchair Accessible' if provider.wheelchair_accessible else ''}
   {'💲 NDIS Price Guide Adherent' if provider.price_guide_adherence else ''}

   📞 {provider.phone}
   📧 {provider.email}
"""

        output += f"\n{'─' * 70}\n"
        return output

    def view_tasks(self) -> str:
        """View pending tasks."""
        tasks = self.store.get_pending_tasks()

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TASK LIST                                                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

{len(tasks)} pending tasks:

"""
        # Group by status
        overdue = [t for t in tasks if t.status == TaskStatus.OVERDUE]
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]
        in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
        waiting = [t for t in tasks if t.status == TaskStatus.WAITING]

        if overdue:
            output += "🚨 OVERDUE\n"
            for t in overdue:
                output += f"   • [{t.task_id}] {t.task_type}: {t.description}\n"
                output += f"     Due: {t.due_date} | Participant: {t.participant_id}\n"
            output += "\n"

        if pending:
            output += "📋 PENDING\n"
            for t in pending[:5]:
                output += f"   • [{t.task_id}] {t.task_type}: {t.description}\n"
                output += f"     Due: {t.due_date} | Participant: {t.participant_id}\n"
            if len(pending) > 5:
                output += f"   ... and {len(pending) - 5} more\n"
            output += "\n"

        if in_progress:
            output += "🔄 IN PROGRESS\n"
            for t in in_progress:
                output += f"   • [{t.task_id}] {t.task_type}: {t.description}\n"
            output += "\n"

        if waiting:
            output += "⏳ WAITING ON EXTERNAL\n"
            for t in waiting:
                output += f"   • [{t.task_id}] {t.task_type}: {t.description}\n"
            output += "\n"

        return output

    def get_review_preparation(self, participant_id: str) -> str:
        """Generate plan review preparation summary."""
        participant = self.store.participants.get(participant_id)

        if not participant:
            return f"❌ Participant {participant_id} not found."

        p = participant
        time_spent = self.store.calculate_time_spent(participant_id, days=365)
        agreements = self.store.get_participant_agreements(participant_id)

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAN REVIEW PREPARATION                                                      ║
║  {p.first_name} {p.last_name} ({p.participant_id})                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

📅 CURRENT PLAN
   Period: {p.plan_start} to {p.plan_end}
   Type: {p.coordination_type.value}
   Plan Management: {p.plan_manager.value}

💰 SUPPORT COORDINATION BUDGET UTILIZATION
   Allocated: ${p.sc_budget:,.2f}
   Spent: ${p.sc_spent:,.2f}
   Remaining: ${p.budget_remaining():,.2f}
   Utilization: {p.budget_percentage_used():.0f}%

🎯 GOAL PROGRESS
"""
        for i, goal in enumerate(p.goals, 1):
            progress = goal.get("progress", "Not recorded")
            output += f"""
   Goal {i}: {goal['statement']}
   Category: {goal['category']}
   Progress: {progress}
   Evidence: [To be documented]
"""

        output += """
🏢 SERVICES ACCESSED
"""
        for provider in p.active_providers:
            output += f"   • {provider}\n"

        if agreements:
            output += "\n   Service Agreements:\n"
            for ag in agreements:
                output += f"   • {ag.provider_name}: ${ag.total_value:,.2f}\n"
                output += f"     Hours used: {ag.hours_used}/{ag.hours_allocated}\n"

        output += f"""
📊 COORDINATION SUMMARY
   Total coordination time: {time_spent['total_hours']} hours
   Activities this plan: {time_spent['activity_count']}

✅ RECOMMENDATIONS FOR NEXT PLAN
   Based on current utilization and goals, consider:

   1. [Review if coordination level is appropriate]
   2. [Assess if budget was sufficient/excessive]
   3. [Identify any unmet needs]
   4. [Consider capacity building opportunities]
   5. [Review provider effectiveness]

📝 PREPARATION CHECKLIST
   □ Gather participant feedback on current supports
   □ Collect provider reports
   □ Document goal progress with evidence
   □ Identify any changes in circumstances
   □ Prepare funding recommendations
   □ Schedule pre-planning meeting with participant
   □ Coordinate with other stakeholders

⚠️ REMINDER: Plan reviews should focus on participant outcomes and goals,
   not just service utilization.
"""
        return output

    def generate_progress_report_template(self, participant_id: str) -> str:
        """Generate a progress report template."""
        participant = self.store.participants.get(participant_id)

        if not participant:
            return f"❌ Participant {participant_id} not found."

        p = participant
        today = datetime.now().strftime("%Y-%m-%d")
        period_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MONTHLY PROGRESS REPORT                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

PARTICIPANT DETAILS
-------------------
Name: {p.first_name} {p.last_name}
NDIS Number: [CONFIDENTIAL]
Reporting Period: {period_start} to {today}
Report Type: Monthly Progress Report
Prepared By: {self.coordinator_name}
Date: {today}

GOAL PROGRESS
-------------
"""
        for i, goal in enumerate(p.goals, 1):
            output += f"""
Goal {i}: {goal['statement']}
Category: {goal['category']}
Status: {goal.get('progress', '[Update status]')}

Activities this period:
• [Describe activities undertaken]
• [Describe supports provided]

Progress made:
• [Describe progress toward goal]
• [Include specific examples]

Barriers/Challenges:
• [Note any barriers encountered]

Next steps:
• [Outline planned activities]

"""

        output += """
SERVICES ACCESSED
-----------------
Providers engaged this period:
"""
        for provider in p.active_providers:
            output += f"""
• {provider}
  Services provided: [Detail services]
  Hours delivered: [XX hours]
  Participant feedback: [Summarize]
"""

        output += f"""
COORDINATION ACTIVITIES
-----------------------
Activities undertaken by Support Coordinator:
• [Provider liaison and coordination]
• [Plan monitoring and review]
• [Advocacy and problem-solving]
• [Capacity building support]

Time spent: [XX hours]

BUDGET UTILIZATION
------------------
Support Coordination Budget:
• Total allocated: ${p.sc_budget:,.2f}
• Spent to date: ${p.sc_spent:,.2f}
• Remaining: ${p.budget_remaining():,.2f}
• Projected end-of-plan position: [Estimate]

RECOMMENDATIONS
---------------
1. [Recommendation for ongoing supports]
2. [Any changes needed]
3. [Capacity building opportunities]

NEXT REPORTING PERIOD
---------------------
Focus areas:
• [Priority 1]
• [Priority 2]

Planned activities:
• [Activity 1]
• [Activity 2]

═══════════════════════════════════════════════════════════════════════════════
Report prepared in accordance with NDIS Practice Standards.
This is a template - please review and customize before finalizing.
═══════════════════════════════════════════════════════════════════════════════
"""
        return output


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run demonstration."""
    print(COORDINATOR_DISCLAIMER)

    print("\n📦 Initializing Support Coordination Assistant...")
    store = SupportCoordinationStore()

    # Load demo data
    participants = DemoDataGenerator.create_demo_participants()
    for p in participants:
        store.participants[p.participant_id] = p

    for provider in DemoDataGenerator.create_demo_providers():
        store.providers[provider.provider_id] = provider

    for task in DemoDataGenerator.create_demo_tasks(participants):
        store.tasks[task.task_id] = task

    assistant = SupportCoordinationAssistant(store, coordinator_name="Lisa")

    # Demo sequence
    print(assistant.get_dashboard())
    input("\nPress Enter to view caseload...")

    print(assistant.view_caseload())
    input("\nPress Enter to view participant details...")

    print(assistant.view_participant("P001"))
    input("\nPress Enter to search providers...")

    print(assistant.search_providers(service_type="therapy"))
    input("\nPress Enter to view tasks...")

    print(assistant.view_tasks())
    input("\nPress Enter to see plan review preparation...")

    print(assistant.get_review_preparation("P001"))
    input("\nPress Enter to see progress report template...")

    print(assistant.generate_progress_report_template("P002"))

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


def run_interactive():
    """Run interactive mode."""
    print(COORDINATOR_DISCLAIMER)

    # Setup
    store = SupportCoordinationStore()

    participants = DemoDataGenerator.create_demo_participants()
    for p in participants:
        store.participants[p.participant_id] = p

    for provider in DemoDataGenerator.create_demo_providers():
        store.providers[provider.provider_id] = provider

    for task in DemoDataGenerator.create_demo_tasks(participants):
        store.tasks[task.task_id] = task

    name = (
        input("Enter your name (or press Enter for 'Coordinator'): ").strip()
        or "Coordinator"
    )
    assistant = SupportCoordinationAssistant(store, coordinator_name=name)

    print(assistant.get_dashboard())

    while True:
        try:
            cmd = input("\nSC> ").strip().lower()

            if not cmd:
                continue

            if cmd in ("quit", "exit"):
                print("Goodbye!")
                break
            elif cmd in ("1", "caseload"):
                print(assistant.view_caseload())
            elif cmd in ("2", "providers", "search"):
                service = input("Service type (or Enter for all): ").strip()
                print(assistant.search_providers(service_type=service))
            elif cmd in ("3", "tasks"):
                print(assistant.view_tasks())
            elif cmd.startswith("4 ") or cmd.startswith("view "):
                pid = cmd.split(" ", 1)[1].strip().upper()
                print(assistant.view_participant(pid))
            elif cmd.startswith("5 ") or cmd.startswith("report "):
                pid = cmd.split(" ", 1)[1].strip().upper()
                print(assistant.generate_progress_report_template(pid))
            elif cmd in ("6", "reviews"):
                reviews = store.get_upcoming_reviews()
                print(f"\n📅 Upcoming Reviews ({len(reviews)}):\n")
                for p in reviews:
                    print(
                        f"  • {p.first_name} {p.last_name[0]}. ({p.participant_id}) - {p.days_until_review()} days"
                    )
            elif cmd.startswith("prep "):
                pid = cmd.split(" ", 1)[1].strip().upper()
                print(assistant.get_review_preparation(pid))
            elif cmd == "dashboard":
                print(assistant.get_dashboard())
            else:
                print(
                    """
Commands:
  1 or caseload - View caseload
  2 or search - Search providers
  3 or tasks - View tasks
  view [ID] - View participant (e.g., view P001)
  report [ID] - Progress report template
  6 or reviews - Upcoming reviews
  prep [ID] - Plan review preparation
  dashboard - Show dashboard
  quit - Exit
"""
                )

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="NDIS Support Coordination Assistant")
    parser.add_argument("--demo", action="store_true", help="Run demonstration")
    parser.add_argument(
        "--caseload", action="store_true", help="View caseload directly"
    )
    parser.add_argument(
        "--provider-search", action="store_true", help="Start with provider search"
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
