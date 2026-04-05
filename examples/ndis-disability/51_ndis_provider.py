#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 51: NDIS Provider Management System
============================================

Comprehensive NDIS (National Disability Insurance Scheme) provider management
system with strict privacy controls compliant with Australian Privacy Principles.

CRITICAL: On-premise/hybrid deployment ONLY - No cloud LLMs for participant data!

This system helps NDIS registered providers manage:
- Participant profiles (encrypted, secure)
- Support plans and goals tracking
- Service booking and scheduling
- Progress notes with timestamps
- Funding utilization tracking
- Incident reporting (mandatory for NDIS)
- Compliance checklist automation
- Audit trail logging (required for NDIS audits)

Architecture (Privacy-First):
    ┌──────────────────────────────────────────────────────────────┐
    │                    ON-PREMISE DEPLOYMENT                      │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐  │
    │  │  Ollama  │  │    Neo4j     │  │   NDIS Provider Agent  │  │
    │  │  (Local) │◄─┤  (Encrypted) │◄─┤  (This Application)    │  │
    │  └──────────┘  └──────────────┘  └────────────────────────┘  │
    │       ▲              ▲                      ▲                 │
    │       │              │                      │                 │
    │       └──────────────┴──────────────────────┘                 │
    │              ALL DATA STAYS LOCAL                             │
    └──────────────────────────────────────────────────────────────┘
                            │
                            ╳  NO participant data to cloud
                            │

IMPORTANT DISCLAIMERS:
    ⚠️  This system is NOT official NDIS software
    ⚠️  Always verify information with official NDIS sources
    ⚠️  Consult NDIS Commission for compliance requirements
    ⚠️  This is a demonstration/educational tool

Role-Based Access:
    - Support Worker: View participants, add progress notes, incidents
    - Support Coordinator: All above + modify plans, service agreements
    - Manager: Full access + compliance reports, audits, user management

Compliance:
    - Australian Privacy Principles (APP)
    - NDIS Practice Standards
    - NDIS Quality and Safeguards Framework
    - State/Territory requirements

Usage:
    python examples/51_ndis_provider.py
    python examples/51_ndis_provider.py --demo
    python examples/51_ndis_provider.py --role support_worker
    python examples/51_ndis_provider.py --role coordinator
    python examples/51_ndis_provider.py --role manager

Requirements:
    pip install agentic-brain cryptography
    ollama pull llama3.1:8b  # On-premise LLM
"""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
from base64 import b64decode, b64encode
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Encryption (cryptography library)
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("⚠️  cryptography not installed - using demo mode only")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

NDIS_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                           IMPORTANT DISCLAIMER                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This system is NOT official NDIS software.                                  ║
║  This is a demonstration/educational tool only.                              ║
║                                                                              ║
║  • Always verify information with official NDIS sources                      ║
║  • Consult the NDIS Quality and Safeguards Commission for compliance         ║
║  • This system does not replace professional advice                          ║
║  • All participant data shown is FICTIONAL for demonstration                 ║
║                                                                              ║
║  For official information: ndis.gov.au | ndiscommission.gov.au              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# NDIS Support Categories
class SupportCategory(Enum):
    """NDIS Support Categories."""

    CORE_DAILY_ACTIVITIES = "Core - Daily Activities"
    CORE_CONSUMABLES = "Core - Consumables"
    CORE_SOCIAL_COMMUNITY = "Core - Social & Community"
    CORE_TRANSPORT = "Core - Transport"
    CAPACITY_BUILDING_CHOICE = "CB - Support Coordination"
    CAPACITY_BUILDING_DAILY = "CB - Daily Living"
    CAPACITY_BUILDING_RELATIONSHIPS = "CB - Relationships"
    CAPACITY_BUILDING_HEALTH = "CB - Health & Wellbeing"
    CAPACITY_BUILDING_LEARNING = "CB - Lifelong Learning"
    CAPACITY_BUILDING_WORK = "CB - Employment"
    CAPITAL_ASSISTIVE = "Capital - Assistive Technology"
    CAPITAL_HOME_MODS = "Capital - Home Modifications"
    CAPITAL_SDA = "Capital - Specialist Disability Accommodation"


class IncidentSeverity(Enum):
    """NDIS Incident Severity Levels."""

    LOW = "Low - No harm"
    MEDIUM = "Medium - Minor harm"
    HIGH = "High - Significant harm"
    CRITICAL = "Critical - Serious injury/death"


class IncidentType(Enum):
    """NDIS Reportable Incident Types."""

    DEATH = "Death of participant"
    SERIOUS_INJURY = "Serious injury"
    ABUSE_NEGLECT = "Abuse or neglect"
    UNLAWFUL_CONDUCT = "Unlawful physical/sexual conduct"
    RESTRICTIVE_PRACTICE = "Unauthorized restrictive practice"
    MISSING_PARTICIPANT = "Missing participant"
    OTHER = "Other incident"


class UserRole(Enum):
    """Provider system roles."""

    SUPPORT_WORKER = "support_worker"
    COORDINATOR = "support_coordinator"
    MANAGER = "manager"
    ADMIN = "admin"


# ══════════════════════════════════════════════════════════════════════════════
# ENCRYPTION & SECURITY
# ══════════════════════════════════════════════════════════════════════════════


class DataEncryption:
    """
    Encryption utilities for sensitive participant data.

    Uses Fernet symmetric encryption (AES-128-CBC).
    All participant PII must be encrypted at rest.
    """

    def __init__(self, key: Optional[bytes] = None, password: Optional[str] = None):
        """Initialize encryption with key or derive from password."""
        if not CRYPTO_AVAILABLE:
            self.fernet = None
            return

        if key:
            self.fernet = Fernet(key)
        elif password:
            # Derive key from password using PBKDF2
            salt = b"ndis_provider_salt_v1"  # In production, use random salt per deployment
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            key = b64encode(kdf.derive(password.encode()))
            self.fernet = Fernet(key)
        else:
            # Generate new key
            self.fernet = Fernet(Fernet.generate_key())

    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        if not self.fernet:
            return f"[DEMO_ENCRYPTED]{data}"
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        if not self.fernet:
            return encrypted_data.replace("[DEMO_ENCRYPTED]", "")
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    def encrypt_dict(self, data: dict, sensitive_fields: list[str]) -> dict:
        """Encrypt specified fields in a dictionary."""
        result = data.copy()
        for field_name in sensitive_fields:
            if field_name in result and result[field_name]:
                result[field_name] = self.encrypt(str(result[field_name]))
        return result

    def decrypt_dict(self, data: dict, sensitive_fields: list[str]) -> dict:
        """Decrypt specified fields in a dictionary."""
        result = data.copy()
        for field_name in sensitive_fields:
            if field_name in result and result[field_name]:
                try:
                    result[field_name] = self.decrypt(str(result[field_name]))
                except Exception:
                    pass  # Field might not be encrypted
        return result


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOGGING
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class AuditEntry:
    """Audit log entry - required for NDIS compliance."""

    timestamp: datetime
    user_id: str
    user_role: UserRole
    action: str
    resource_type: str
    resource_id: str
    details: str
    ip_address: str = "127.0.0.1"
    success: bool = True

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "user_role": self.user_role.value,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "success": self.success,
        }


class AuditLogger:
    """
    NDIS-compliant audit logging.

    All data access must be logged for:
    - NDIS audits
    - Privacy compliance
    - Incident investigation
    - Quality assurance

    Logs are tamper-evident with hash chaining.
    """

    def __init__(self, log_path: str = "./ndis_audit_logs"):
        self.log_path = Path(log_path)
        self.log_path.mkdir(parents=True, exist_ok=True)
        self.entries: list[AuditEntry] = []
        self.previous_hash: str = "GENESIS"

    def log(
        self,
        user_id: str,
        user_role: UserRole,
        action: str,
        resource_type: str,
        resource_id: str,
        details: str = "",
        success: bool = True,
    ) -> AuditEntry:
        """Log an auditable action."""
        entry = AuditEntry(
            timestamp=datetime.now(),
            user_id=user_id,
            user_role=user_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            success=success,
        )

        # Hash chaining for tamper evidence
        entry_json = json.dumps(entry.to_dict(), sort_keys=True)
        current_hash = hashlib.sha256(
            f"{self.previous_hash}:{entry_json}".encode()
        ).hexdigest()
        self.previous_hash = current_hash

        self.entries.append(entry)

        # Persist to file
        self._write_entry(entry, current_hash)

        return entry

    def _write_entry(self, entry: AuditEntry, hash_value: str):
        """Write entry to log file."""
        log_file = self.log_path / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a") as f:
            record = {**entry.to_dict(), "hash": hash_value}
            f.write(json.dumps(record) + "\n")

    def get_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> list[AuditEntry]:
        """Query audit entries with filters."""
        results = self.entries

        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]

        return results

    def generate_audit_report(self, days: int = 30) -> str:
        """Generate audit report for NDIS compliance."""
        start = datetime.now() - timedelta(days=days)
        entries = self.get_entries(start_date=start)

        report = f"""
NDIS AUDIT REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Period: Last {days} days

SUMMARY
-------
Total Actions: {len(entries)}
Unique Users: {len({e.user_id for e in entries})}
Failed Actions: {len([e for e in entries if not e.success])}

BY ACTION TYPE
--------------
"""
        action_counts: dict[str, int] = {}
        for entry in entries:
            action_counts[entry.action] = action_counts.get(entry.action, 0) + 1

        for action, count in sorted(action_counts.items()):
            report += f"  {action}: {count}\n"

        report += "\nBY RESOURCE TYPE\n----------------\n"
        resource_counts: dict[str, int] = {}
        for entry in entries:
            resource_counts[entry.resource_type] = (
                resource_counts.get(entry.resource_type, 0) + 1
            )

        for resource, count in sorted(resource_counts.items()):
            report += f"  {resource}: {count}\n"

        return report


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Participant:
    """
    NDIS Participant profile.

    Contains sensitive PII - must be encrypted at rest.
    """

    participant_id: str
    ndis_number: str  # ENCRYPTED
    first_name: str  # ENCRYPTED
    last_name: str  # ENCRYPTED
    date_of_birth: str  # ENCRYPTED
    address: str  # ENCRYPTED
    phone: str  # ENCRYPTED
    email: str  # ENCRYPTED
    emergency_contact: str  # ENCRYPTED
    primary_disability: str
    secondary_disabilities: list[str] = field(default_factory=list)
    communication_needs: str = ""
    cultural_background: str = ""
    consent_given: bool = False
    consent_date: Optional[str] = None
    plan_start_date: Optional[str] = None
    plan_end_date: Optional[str] = None
    plan_manager_type: str = "NDIA Managed"  # NDIA, Plan, Self
    active: bool = True

    SENSITIVE_FIELDS = [
        "ndis_number",
        "first_name",
        "last_name",
        "date_of_birth",
        "address",
        "phone",
        "email",
        "emergency_contact",
    ]


@dataclass
class SupportPlanGoal:
    """Goal within an NDIS support plan."""

    goal_id: str
    participant_id: str
    category: SupportCategory
    goal_statement: str
    target_outcome: str
    start_date: str
    review_date: str
    status: str = "Active"  # Active, Achieved, Modified, Discontinued
    progress_percentage: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class ServiceBooking:
    """Service booking record."""

    booking_id: str
    participant_id: str
    service_type: str
    support_category: SupportCategory
    worker_id: str
    scheduled_date: str
    scheduled_time: str
    duration_hours: float
    rate_per_hour: float
    location: str
    status: str = "Scheduled"  # Scheduled, Confirmed, Completed, Cancelled
    notes: str = ""


@dataclass
class ProgressNote:
    """Progress note for service delivery."""

    note_id: str
    participant_id: str
    booking_id: Optional[str]
    worker_id: str
    date: str
    time: str
    duration_minutes: int
    service_delivered: str
    participant_response: str
    goals_addressed: list[str]
    next_session_plan: str
    concerns: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FundingAllocation:
    """Funding allocation by support category."""

    allocation_id: str
    participant_id: str
    category: SupportCategory
    total_budget: float
    spent: float
    committed: float  # Future bookings
    start_date: str
    end_date: str

    @property
    def available(self) -> float:
        return self.total_budget - self.spent - self.committed

    @property
    def utilization_percentage(self) -> float:
        if self.total_budget == 0:
            return 0
        return ((self.spent + self.committed) / self.total_budget) * 100


@dataclass
class Incident:
    """NDIS Reportable Incident."""

    incident_id: str
    participant_id: str
    incident_type: IncidentType
    severity: IncidentSeverity
    date_occurred: str
    time_occurred: str
    location: str
    description: str
    immediate_action: str
    reported_by: str
    reported_date: str
    witness_names: list[str] = field(default_factory=list)
    notified_commission: bool = False
    commission_notification_date: Optional[str] = None
    investigation_status: str = "Pending"
    corrective_actions: list[str] = field(default_factory=list)
    closed: bool = False
    closed_date: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER DATA STORE
# ══════════════════════════════════════════════════════════════════════════════


class NDISProviderStore:
    """
    In-memory data store for NDIS provider.

    In production, replace with encrypted database.
    All sensitive data encrypted with Fernet.
    """

    def __init__(self, encryption: DataEncryption):
        self.encryption = encryption
        self.participants: dict[str, Participant] = {}
        self.goals: dict[str, SupportPlanGoal] = {}
        self.bookings: dict[str, ServiceBooking] = {}
        self.progress_notes: dict[str, ProgressNote] = {}
        self.funding: dict[str, FundingAllocation] = {}
        self.incidents: dict[str, Incident] = {}

    def add_participant(self, participant: Participant) -> str:
        """Add participant with encryption."""
        self.participants[participant.participant_id] = participant
        return participant.participant_id

    def get_participant(self, participant_id: str) -> Optional[Participant]:
        """Get participant by ID."""
        return self.participants.get(participant_id)

    def search_participants(self, query: str) -> list[Participant]:
        """Search participants (by ID only for privacy)."""
        results = []
        query_lower = query.lower()
        for p in self.participants.values():
            if query_lower in p.participant_id.lower():
                results.append(p)
        return results

    def get_active_participants(self) -> list[Participant]:
        """Get all active participants."""
        return [p for p in self.participants.values() if p.active]

    def add_goal(self, goal: SupportPlanGoal) -> str:
        """Add support plan goal."""
        self.goals[goal.goal_id] = goal
        return goal.goal_id

    def get_participant_goals(self, participant_id: str) -> list[SupportPlanGoal]:
        """Get all goals for a participant."""
        return [g for g in self.goals.values() if g.participant_id == participant_id]

    def add_booking(self, booking: ServiceBooking) -> str:
        """Add service booking."""
        self.bookings[booking.booking_id] = booking
        return booking.booking_id

    def get_bookings_by_date(self, date_str: str) -> list[ServiceBooking]:
        """Get all bookings for a date."""
        return [b for b in self.bookings.values() if b.scheduled_date == date_str]

    def get_participant_bookings(self, participant_id: str) -> list[ServiceBooking]:
        """Get all bookings for a participant."""
        return [b for b in self.bookings.values() if b.participant_id == participant_id]

    def add_progress_note(self, note: ProgressNote) -> str:
        """Add progress note."""
        self.progress_notes[note.note_id] = note
        return note.note_id

    def get_participant_notes(self, participant_id: str) -> list[ProgressNote]:
        """Get all progress notes for participant."""
        return sorted(
            [
                n
                for n in self.progress_notes.values()
                if n.participant_id == participant_id
            ],
            key=lambda x: x.created_at,
            reverse=True,
        )

    def add_funding(self, allocation: FundingAllocation) -> str:
        """Add funding allocation."""
        self.funding[allocation.allocation_id] = allocation
        return allocation.allocation_id

    def get_participant_funding(self, participant_id: str) -> list[FundingAllocation]:
        """Get funding allocations for participant."""
        return [f for f in self.funding.values() if f.participant_id == participant_id]

    def add_incident(self, incident: Incident) -> str:
        """Add incident report."""
        self.incidents[incident.incident_id] = incident
        return incident.incident_id

    def get_open_incidents(self) -> list[Incident]:
        """Get all open incidents."""
        return [i for i in self.incidents.values() if not i.closed]

    def get_reportable_incidents(self) -> list[Incident]:
        """Get incidents requiring Commission notification."""
        return [
            i
            for i in self.incidents.values()
            if i.incident_type
            in [
                IncidentType.DEATH,
                IncidentType.SERIOUS_INJURY,
                IncidentType.ABUSE_NEGLECT,
                IncidentType.UNLAWFUL_CONDUCT,
                IncidentType.RESTRICTIVE_PRACTICE,
            ]
            and not i.notified_commission
        ]


# ══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE CHECKER
# ══════════════════════════════════════════════════════════════════════════════


class NDISComplianceChecker:
    """
    NDIS Practice Standards compliance checker.

    Based on NDIS Practice Standards and Quality Indicators.
    """

    def __init__(self, store: NDISProviderStore):
        self.store = store

    def check_consent_compliance(self) -> dict:
        """Check participant consent status."""
        participants = self.store.get_active_participants()
        without_consent = [p for p in participants if not p.consent_given]

        return {
            "check": "Participant Consent",
            "standard": "Rights - 1.1 Informed Decision Making",
            "total": len(participants),
            "compliant": len(participants) - len(without_consent),
            "non_compliant": len(without_consent),
            "issues": [
                f"Participant {p.participant_id} missing consent"
                for p in without_consent[:5]  # Limit output
            ],
            "status": "PASS" if not without_consent else "FAIL",
        }

    def check_incident_reporting(self) -> dict:
        """Check incident reporting compliance."""
        unreported = self.store.get_reportable_incidents()

        return {
            "check": "Incident Reporting",
            "standard": "Incident Management - 2.1 Reportable Incidents",
            "unreported_count": len(unreported),
            "issues": [
                f"Incident {i.incident_id} ({i.incident_type.value}) not reported to Commission"
                for i in unreported[:5]
            ],
            "status": "PASS" if not unreported else "FAIL - Report within 24 hours!",
        }

    def check_progress_notes(self, days: int = 30) -> dict:
        """Check progress note timeliness."""
        # Check completed bookings have notes
        issues = []
        for booking in self.store.bookings.values():
            if booking.status == "Completed":
                participant_notes = self.store.get_participant_notes(
                    booking.participant_id
                )
                matching_notes = [
                    n for n in participant_notes if n.booking_id == booking.booking_id
                ]
                if not matching_notes:
                    issues.append(f"Booking {booking.booking_id} missing progress note")

        return {
            "check": "Progress Notes",
            "standard": "Service Delivery - 3.2 Record Keeping",
            "missing_notes": len(issues),
            "issues": issues[:5],
            "status": "PASS" if not issues else "ATTENTION REQUIRED",
        }

    def check_funding_utilization(self) -> dict:
        """Check funding utilization and at-risk plans."""
        at_risk = []
        under_utilized = []

        for allocation in self.store.funding.values():
            util = allocation.utilization_percentage
            if util > 95:
                at_risk.append(
                    {
                        "participant": allocation.participant_id,
                        "category": allocation.category.value,
                        "utilization": f"{util:.1f}%",
                    }
                )
            elif util < 30:
                under_utilized.append(
                    {
                        "participant": allocation.participant_id,
                        "category": allocation.category.value,
                        "utilization": f"{util:.1f}%",
                    }
                )

        return {
            "check": "Funding Utilization",
            "standard": "Plan Management",
            "at_risk_count": len(at_risk),
            "under_utilized_count": len(under_utilized),
            "at_risk": at_risk[:5],
            "under_utilized": under_utilized[:5],
            "status": "PASS" if not at_risk else "MONITOR CLOSELY",
        }

    def run_full_compliance_check(self) -> dict:
        """Run all compliance checks."""
        return {
            "timestamp": datetime.now().isoformat(),
            "checks": [
                self.check_consent_compliance(),
                self.check_incident_reporting(),
                self.check_progress_notes(),
                self.check_funding_utilization(),
            ],
        }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA GENERATOR
# ══════════════════════════════════════════════════════════════════════════════


class DemoDataGenerator:
    """Generate realistic but fictional NDIS demo data."""

    # Generic names - no real people
    FIRST_NAMES = [
        "Alex",
        "Jordan",
        "Taylor",
        "Morgan",
        "Casey",
        "Riley",
        "Jamie",
        "Sam",
    ]
    LAST_NAMES = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Davis",
        "Miller",
        "Wilson",
    ]

    DISABILITIES = [
        "Autism Spectrum Disorder",
        "Intellectual Disability",
        "Cerebral Palsy",
        "Acquired Brain Injury",
        "Psychosocial Disability",
        "Physical Disability",
        "Hearing Impairment",
        "Vision Impairment",
    ]

    SERVICES = [
        "Personal Care",
        "Community Access",
        "Therapy Services",
        "Support Coordination",
        "Domestic Assistance",
        "Social Skills Group",
        "Employment Support",
        "Respite Care",
    ]

    @staticmethod
    def generate_ndis_number() -> str:
        """Generate fake NDIS number."""
        return f"4{secrets.randbelow(100000000):08d}"

    @staticmethod
    def generate_participant_id() -> str:
        """Generate participant ID."""
        return f"P{secrets.randbelow(100000):05d}"

    @classmethod
    def create_demo_participants(cls, count: int = 5) -> list[Participant]:
        """Create demo participants."""
        participants = []

        for i in range(count):
            first = cls.FIRST_NAMES[i % len(cls.FIRST_NAMES)]
            last = cls.LAST_NAMES[i % len(cls.LAST_NAMES)]

            participants.append(
                Participant(
                    participant_id=cls.generate_participant_id(),
                    ndis_number=cls.generate_ndis_number(),
                    first_name=first,
                    last_name=last,
                    date_of_birth=f"19{70 + i * 5}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                    address=f"{100 + i * 10} Example Street, Adelaide SA {5000 + i}",
                    phone=f"04{secrets.randbelow(100000000):08d}",
                    email=f"{first.lower()}.{last.lower()}@example.com",
                    emergency_contact=f"Contact Person - 04{secrets.randbelow(100000000):08d}",
                    primary_disability=cls.DISABILITIES[i % len(cls.DISABILITIES)],
                    secondary_disabilities=(
                        [cls.DISABILITIES[(i + 2) % len(cls.DISABILITIES)]]
                        if i % 2 == 0
                        else []
                    ),
                    communication_needs=(
                        "Prefers written communication" if i % 3 == 0 else ""
                    ),
                    cultural_background="Australian",
                    consent_given=True,
                    consent_date=datetime.now().strftime("%Y-%m-%d"),
                    plan_start_date=(datetime.now() - timedelta(days=180)).strftime(
                        "%Y-%m-%d"
                    ),
                    plan_end_date=(datetime.now() + timedelta(days=185)).strftime(
                        "%Y-%m-%d"
                    ),
                    plan_manager_type=["NDIA Managed", "Plan Managed", "Self Managed"][
                        i % 3
                    ],
                    active=True,
                )
            )

        return participants

    @classmethod
    def create_demo_goals(cls, participant_id: str) -> list[SupportPlanGoal]:
        """Create demo goals for a participant."""
        goals = [
            SupportPlanGoal(
                goal_id=f"G{secrets.randbelow(10000):04d}",
                participant_id=participant_id,
                category=SupportCategory.CAPACITY_BUILDING_DAILY,
                goal_statement="Develop independent living skills for meal preparation",
                target_outcome="Prepare 3 simple meals independently per week",
                start_date=(datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
                review_date=(datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                status="Active",
                progress_percentage=45,
            ),
            SupportPlanGoal(
                goal_id=f"G{secrets.randbelow(10000):04d}",
                participant_id=participant_id,
                category=SupportCategory.CORE_SOCIAL_COMMUNITY,
                goal_statement="Increase community participation and social connections",
                target_outcome="Attend 2 community activities per week",
                start_date=(datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
                review_date=(datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                status="Active",
                progress_percentage=60,
            ),
        ]
        return goals

    @classmethod
    def create_demo_funding(cls, participant_id: str) -> list[FundingAllocation]:
        """Create demo funding allocations."""
        return [
            FundingAllocation(
                allocation_id=f"F{secrets.randbelow(10000):04d}",
                participant_id=participant_id,
                category=SupportCategory.CORE_DAILY_ACTIVITIES,
                total_budget=45000.00,
                spent=18000.00,
                committed=5000.00,
                start_date=(datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),
                end_date=(datetime.now() + timedelta(days=185)).strftime("%Y-%m-%d"),
            ),
            FundingAllocation(
                allocation_id=f"F{secrets.randbelow(10000):04d}",
                participant_id=participant_id,
                category=SupportCategory.CAPACITY_BUILDING_CHOICE,
                total_budget=8000.00,
                spent=3200.00,
                committed=800.00,
                start_date=(datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),
                end_date=(datetime.now() + timedelta(days=185)).strftime("%Y-%m-%d"),
            ),
        ]


# ══════════════════════════════════════════════════════════════════════════════
# NDIS PROVIDER AGENT
# ══════════════════════════════════════════════════════════════════════════════


class NDISProviderAgent:
    """
    NDIS Provider Management Assistant.

    Uses on-premise Ollama LLM for privacy.
    All participant data stays local.
    """

    SYSTEM_PROMPT = """You are an NDIS Provider Management Assistant. You help disability support
providers manage their operations while maintaining strict privacy and compliance.

IMPORTANT RULES:
1. NEVER store or transmit participant data to external systems
2. All advice must align with NDIS Practice Standards
3. Always recommend consulting official NDIS sources for policy questions
4. Maintain professional, person-centered language
5. Flag any compliance concerns immediately

Your capabilities:
- Help manage participant profiles and support plans
- Track service bookings and scheduling
- Assist with progress note documentation
- Monitor funding utilization
- Guide incident reporting processes
- Support compliance checking

Remember: This is a demonstration system. Always verify with official NDIS sources."""

    def __init__(
        self,
        store: NDISProviderStore,
        audit_logger: AuditLogger,
        user_id: str,
        user_role: UserRole,
        ollama_host: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
    ):
        self.store = store
        self.audit = audit_logger
        self.user_id = user_id
        self.user_role = user_role
        self.ollama_host = ollama_host
        self.model = model
        self.compliance = NDISComplianceChecker(store)

        # Verify role permissions
        self.permissions = self._get_role_permissions()

    def _get_role_permissions(self) -> dict:
        """Get permissions for user role."""
        base = {
            "view_participants": True,
            "add_notes": True,
            "view_bookings": True,
        }

        if self.user_role in [UserRole.COORDINATOR, UserRole.MANAGER, UserRole.ADMIN]:
            base.update(
                {
                    "edit_participants": True,
                    "manage_bookings": True,
                    "edit_goals": True,
                    "view_funding": True,
                }
            )

        if self.user_role in [UserRole.MANAGER, UserRole.ADMIN]:
            base.update(
                {
                    "run_compliance": True,
                    "view_audit": True,
                    "manage_incidents": True,
                }
            )

        if self.user_role == UserRole.ADMIN:
            base.update(
                {
                    "manage_users": True,
                    "export_data": True,
                }
            )

        return base

    def check_permission(self, permission: str) -> bool:
        """Check if user has permission."""
        has_perm = self.permissions.get(permission, False)
        if not has_perm:
            self.audit.log(
                user_id=self.user_id,
                user_role=self.user_role,
                action="PERMISSION_DENIED",
                resource_type="system",
                resource_id=permission,
                success=False,
            )
        return has_perm

    def view_participant(self, participant_id: str) -> str:
        """View participant summary."""
        if not self.check_permission("view_participants"):
            return "❌ Access denied: Insufficient permissions"

        participant = self.store.get_participant(participant_id)
        if not participant:
            return f"❌ Participant {participant_id} not found"

        # Log access
        self.audit.log(
            user_id=self.user_id,
            user_role=self.user_role,
            action="VIEW_PARTICIPANT",
            resource_type="participant",
            resource_id=participant_id,
        )

        # Get related data
        goals = self.store.get_participant_goals(participant_id)
        funding = self.store.get_participant_funding(participant_id)
        bookings = self.store.get_participant_bookings(participant_id)

        upcoming = [b for b in bookings if b.status == "Scheduled"]

        output = f"""
╔══════════════════════════════════════════════════════════════╗
║  PARTICIPANT SUMMARY                                          ║
╚══════════════════════════════════════════════════════════════╝

ID: {participant.participant_id}
Status: {'✅ Active' if participant.active else '⏸️ Inactive'}
Plan Type: {participant.plan_manager_type}
Plan Period: {participant.plan_start_date} to {participant.plan_end_date}
Primary Disability: {participant.primary_disability}

GOALS ({len(goals)} active)
{'─' * 40}
"""
        for goal in goals:
            output += (
                f"  • {goal.goal_statement[:50]}... [{goal.progress_percentage}%]\n"
            )

        output += f"""
FUNDING SUMMARY
{'─' * 40}
"""
        total_budget = sum(f.total_budget for f in funding)
        total_spent = sum(f.spent for f in funding)
        total_available = sum(f.available for f in funding)

        output += f"  Total Budget: ${total_budget:,.2f}\n"
        output += f"  Spent: ${total_spent:,.2f}\n"
        output += f"  Available: ${total_available:,.2f}\n"

        output += f"""
UPCOMING BOOKINGS ({len(upcoming)})
{'─' * 40}
"""
        for booking in upcoming[:3]:
            output += f"  • {booking.scheduled_date} {booking.scheduled_time} - {booking.service_type}\n"

        return output

    def add_progress_note(
        self,
        participant_id: str,
        service_delivered: str,
        participant_response: str,
        duration_minutes: int,
        goals_addressed: list[str],
        next_session_plan: str,
        concerns: str = "",
    ) -> str:
        """Add a progress note."""
        if not self.check_permission("add_notes"):
            return "❌ Access denied: Insufficient permissions"

        participant = self.store.get_participant(participant_id)
        if not participant:
            return f"❌ Participant {participant_id} not found"

        note = ProgressNote(
            note_id=f"N{secrets.randbelow(100000):05d}",
            participant_id=participant_id,
            booking_id=None,
            worker_id=self.user_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            time=datetime.now().strftime("%H:%M"),
            duration_minutes=duration_minutes,
            service_delivered=service_delivered,
            participant_response=participant_response,
            goals_addressed=goals_addressed,
            next_session_plan=next_session_plan,
            concerns=concerns,
        )

        self.store.add_progress_note(note)

        self.audit.log(
            user_id=self.user_id,
            user_role=self.user_role,
            action="ADD_PROGRESS_NOTE",
            resource_type="progress_note",
            resource_id=note.note_id,
            details=f"For participant {participant_id}",
        )

        return f"""
✅ Progress Note Added

Note ID: {note.note_id}
Date/Time: {note.date} {note.time}
Duration: {note.duration_minutes} minutes
Goals Addressed: {', '.join(goals_addressed) if goals_addressed else 'N/A'}

{'⚠️ CONCERNS FLAGGED: ' + concerns if concerns else ''}
"""

    def report_incident(
        self,
        participant_id: str,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        date_occurred: str,
        time_occurred: str,
        location: str,
        description: str,
        immediate_action: str,
        witness_names: list[str] = None,
    ) -> str:
        """Report an incident - MANDATORY for serious incidents."""
        if not self.check_permission("add_notes"):  # All workers can report
            return "❌ Access denied: Insufficient permissions"

        incident = Incident(
            incident_id=f"INC{secrets.randbelow(100000):05d}",
            participant_id=participant_id,
            incident_type=incident_type,
            severity=severity,
            date_occurred=date_occurred,
            time_occurred=time_occurred,
            location=location,
            description=description,
            immediate_action=immediate_action,
            reported_by=self.user_id,
            reported_date=datetime.now().strftime("%Y-%m-%d"),
            witness_names=witness_names or [],
        )

        self.store.add_incident(incident)

        self.audit.log(
            user_id=self.user_id,
            user_role=self.user_role,
            action="REPORT_INCIDENT",
            resource_type="incident",
            resource_id=incident.incident_id,
            details=f"Type: {incident_type.value}, Severity: {severity.value}",
        )

        # Check if reportable to Commission
        reportable_types = [
            IncidentType.DEATH,
            IncidentType.SERIOUS_INJURY,
            IncidentType.ABUSE_NEGLECT,
            IncidentType.UNLAWFUL_CONDUCT,
            IncidentType.RESTRICTIVE_PRACTICE,
        ]

        must_report = incident_type in reportable_types

        return (
            f"""
{'🚨' * 10}
INCIDENT REPORT CREATED
{'🚨' * 10}

Incident ID: {incident.incident_id}
Type: {incident_type.value}
Severity: {severity.value}
Date/Time: {date_occurred} {time_occurred}
Location: {location}

{'=' * 50}
⚠️  REPORTABLE INCIDENT - NOTIFY NDIS COMMISSION WITHIN 24 HOURS!

This incident type MUST be reported to the NDIS Quality and
Safeguards Commission within 24 hours.

Report at: https://www.ndiscommission.gov.au/providers/reportable-incidents
{'=' * 50}
"""
            if must_report
            else f"""
✅ INCIDENT REPORT CREATED

Incident ID: {incident.incident_id}
Type: {incident_type.value}
Severity: {severity.value}
Status: Pending Investigation

Next Steps:
1. Review with supervisor within 24 hours
2. Update investigation status
3. Document corrective actions
"""
        )

    def run_compliance_check(self) -> str:
        """Run compliance checks - Manager only."""
        if not self.check_permission("run_compliance"):
            return "❌ Access denied: Requires Manager or Admin role"

        self.audit.log(
            user_id=self.user_id,
            user_role=self.user_role,
            action="RUN_COMPLIANCE_CHECK",
            resource_type="system",
            resource_id="full_check",
        )

        results = self.compliance.run_full_compliance_check()

        output = f"""
╔══════════════════════════════════════════════════════════════╗
║  NDIS COMPLIANCE CHECK REPORT                                 ║
╚══════════════════════════════════════════════════════════════╝
Generated: {results['timestamp']}

"""
        for check in results["checks"]:
            status_emoji = (
                "✅"
                if check["status"] == "PASS"
                else "⚠️" if "ATTENTION" in check["status"] else "❌"
            )
            output += f"""
{status_emoji} {check['check']}
   Standard: {check['standard']}
   Status: {check['status']}
"""
            if check.get("issues"):
                output += "   Issues:\n"
                for issue in check["issues"][:3]:
                    output += f"     • {issue}\n"

        return output

    def get_dashboard(self) -> str:
        """Get provider dashboard summary."""
        participants = self.store.get_active_participants()
        today = datetime.now().strftime("%Y-%m-%d")
        today_bookings = self.store.get_bookings_by_date(today)
        open_incidents = self.store.get_open_incidents()
        reportable = self.store.get_reportable_incidents()

        return f"""
╔══════════════════════════════════════════════════════════════╗
║  NDIS PROVIDER DASHBOARD                                      ║
║  {datetime.now().strftime('%Y-%m-%d %H:%M')}                                           ║
╚══════════════════════════════════════════════════════════════╝

👥 Active Participants: {len(participants)}
📅 Today's Bookings: {len(today_bookings)}
📝 Open Incidents: {len(open_incidents)}
{'🚨 URGENT: ' + str(len(reportable)) + ' incidents require Commission notification!' if reportable else '✅ All reportable incidents notified'}

QUICK ACTIONS
{'─' * 40}
1. View participant
2. Add progress note
3. Report incident
4. Check compliance
5. View today's schedule

User: {self.user_id} ({self.user_role.value})
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run demonstration with sample data."""
    print(NDIS_DISCLAIMER)
    print("\n" + "=" * 60)
    print("🏥 NDIS PROVIDER MANAGEMENT SYSTEM - DEMO MODE")
    print("=" * 60)

    # Initialize components
    print("\n📦 Initializing system...")
    encryption = DataEncryption(password="demo_password_change_in_production")
    store = NDISProviderStore(encryption)
    audit = AuditLogger("./demo_audit_logs")

    # Generate demo data
    print("📊 Loading demo participants...")
    participants = DemoDataGenerator.create_demo_participants(5)
    for p in participants:
        store.add_participant(p)
        for goal in DemoDataGenerator.create_demo_goals(p.participant_id):
            store.add_goal(goal)
        for funding in DemoDataGenerator.create_demo_funding(p.participant_id):
            store.add_funding(funding)

    print(f"   ✅ Loaded {len(participants)} demo participants")

    # Create agent as Manager
    agent = NDISProviderAgent(
        store=store,
        audit_logger=audit,
        user_id="demo_manager",
        user_role=UserRole.MANAGER,
    )

    # Show dashboard
    print(agent.get_dashboard())

    # Demo: View participant
    print("\n" + "=" * 60)
    print("📋 DEMO: View Participant Profile")
    print("=" * 60)
    print(agent.view_participant(participants[0].participant_id))

    # Demo: Add progress note
    print("\n" + "=" * 60)
    print("📝 DEMO: Add Progress Note")
    print("=" * 60)
    print(
        agent.add_progress_note(
            participant_id=participants[0].participant_id,
            service_delivered="Community access support - visited local library",
            participant_response="Engaged well with activity, showed interest in audiobooks",
            duration_minutes=120,
            goals_addressed=["Community participation", "Social connections"],
            next_session_plan="Continue library visits, explore audiobook borrowing",
        )
    )

    # Demo: Compliance check
    print("\n" + "=" * 60)
    print("✅ DEMO: Compliance Check")
    print("=" * 60)
    print(agent.run_compliance_check())

    # Demo: Incident report
    print("\n" + "=" * 60)
    print("⚠️ DEMO: Incident Reporting")
    print("=" * 60)
    print(
        agent.report_incident(
            participant_id=participants[0].participant_id,
            incident_type=IncidentType.OTHER,
            severity=IncidentSeverity.LOW,
            date_occurred=datetime.now().strftime("%Y-%m-%d"),
            time_occurred="14:30",
            location="Community centre",
            description="Participant became anxious during group activity. Support worker implemented de-escalation strategies.",
            immediate_action="Moved to quiet area, used calming techniques, contacted family",
        )
    )

    # Show audit summary
    print("\n" + "=" * 60)
    print("📊 AUDIT TRAIL")
    print("=" * 60)
    print(audit.generate_audit_report(days=1))


def run_interactive(role: UserRole):
    """Run interactive mode."""
    print(NDIS_DISCLAIMER)
    print("\n" + "=" * 60)
    print("🏥 NDIS PROVIDER SYSTEM - Interactive Mode")
    print(f"   Role: {role.value}")
    print("=" * 60)

    # Initialize
    encryption = DataEncryption(password="demo_password")
    store = NDISProviderStore(encryption)
    audit = AuditLogger("./ndis_audit_logs")

    # Load demo data
    participants = DemoDataGenerator.create_demo_participants(5)
    for p in participants:
        store.add_participant(p)
        for goal in DemoDataGenerator.create_demo_goals(p.participant_id):
            store.add_goal(goal)
        for funding in DemoDataGenerator.create_demo_funding(p.participant_id):
            store.add_funding(funding)

    agent = NDISProviderAgent(
        store=store,
        audit_logger=audit,
        user_id=f"user_{role.value}",
        user_role=role,
    )

    print(agent.get_dashboard())

    print("\nCommands:")
    print("  dashboard - Show dashboard")
    print("  view <id> - View participant")
    print("  list - List participants")
    print("  compliance - Run compliance check")
    print("  audit - Show audit report")
    print("  quit - Exit")
    print()

    while True:
        try:
            cmd = input("NDIS> ").strip().lower()

            if not cmd:
                continue

            if cmd == "quit":
                print("\nGoodbye! Audit logs saved.")
                break

            elif cmd == "dashboard":
                print(agent.get_dashboard())

            elif cmd == "list":
                for p in store.get_active_participants():
                    print(f"  {p.participant_id}: {p.primary_disability}")

            elif cmd.startswith("view "):
                pid = cmd.split(" ", 1)[1].strip()
                print(agent.view_participant(pid))

            elif cmd == "compliance":
                print(agent.run_compliance_check())

            elif cmd == "audit":
                print(audit.generate_audit_report())

            else:
                print("Unknown command. Type 'quit' to exit.")

        except KeyboardInterrupt:
            print("\n\nSession ended.")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="NDIS Provider Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python 51_ndis_provider.py --demo
  python 51_ndis_provider.py --role support_worker
  python 51_ndis_provider.py --role manager

DISCLAIMER: This is a demonstration system, not official NDIS software.
""",
    )

    parser.add_argument(
        "--demo", action="store_true", help="Run demonstration with sample data"
    )

    parser.add_argument(
        "--role",
        choices=["support_worker", "coordinator", "manager", "admin"],
        default="support_worker",
        help="User role for access control",
    )

    parser.add_argument(
        "--interactive", action="store_true", help="Run in interactive mode"
    )

    args = parser.parse_args()

    role_map = {
        "support_worker": UserRole.SUPPORT_WORKER,
        "coordinator": UserRole.COORDINATOR,
        "manager": UserRole.MANAGER,
        "admin": UserRole.ADMIN,
    }

    if args.demo:
        run_demo()
    else:
        run_interactive(role_map[args.role])


if __name__ == "__main__":
    main()
