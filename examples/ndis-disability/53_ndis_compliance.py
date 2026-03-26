#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 53: NDIS Quality & Safeguards Compliance System
=========================================================

Comprehensive compliance management system for NDIS registered providers
aligned with NDIS Practice Standards and Quality Indicators.

CRITICAL: On-premise deployment for sensitive compliance data!

This system helps compliance officers and managers with:
- NDIS Practice Standards checklist
- Worker screening verification
- Incident report management
- Complaint handling workflow
- Quality indicator tracking
- Audit preparation reports
- Risk assessment tools
- Corrective action tracking

Architecture (Privacy-First):
    ┌──────────────────────────────────────────────────────────────┐
    │                 COMPLIANCE MANAGEMENT SYSTEM                  │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐  │
    │  │  Ollama  │  │    Neo4j     │  │   Compliance Agent     │  │
    │  │  (Local) │◄─┤  (Encrypted) │◄─┤  (This Application)    │  │
    │  └──────────┘  └──────────────┘  └────────────────────────┘  │
    │       │              │                      │                 │
    │       └──────────────┴──────────────────────┘                 │
    │              AUDIT-READY LOGGING                              │
    └──────────────────────────────────────────────────────────────┘

IMPORTANT DISCLAIMERS:
    ⚠️  This is NOT official NDIS Commission software
    ⚠️  Always consult the NDIS Commission for compliance requirements
    ⚠️  This is a demonstration/educational tool only
    ⚠️  For official guidance: ndiscommission.gov.au

NDIS Practice Standards Modules:
    Module 1: Rights and Responsibilities
    Module 2: Provider Governance and Operational Management
    Module 3: Provision of Supports
    Module 4: Provision of Supports Environment (where applicable)
    Supplementary Modules (as registered)

Usage:
    python examples/53_ndis_compliance.py
    python examples/53_ndis_compliance.py --demo
    python examples/53_ndis_compliance.py --audit-prep
    python examples/53_ndis_compliance.py --incident-review

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b
"""

import asyncio
import argparse
import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, Any
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# DISCLAIMERS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

COMPLIANCE_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                           IMPORTANT DISCLAIMER                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This system is NOT official NDIS Commission software.                       ║
║  This is a demonstration/educational tool for compliance management.         ║
║                                                                              ║
║  • Always consult the NDIS Quality and Safeguards Commission                ║
║  • Refer to official NDIS Practice Standards                                ║
║  • This tool does not replace professional compliance advice                ║
║  • All data shown is FICTIONAL for demonstration                            ║
║                                                                              ║
║  Official resources: ndiscommission.gov.au                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


class ComplianceStatus(Enum):
    """Compliance status levels."""

    COMPLIANT = "Compliant"
    PARTIALLY_COMPLIANT = "Partially Compliant"
    NON_COMPLIANT = "Non-Compliant"
    NOT_ASSESSED = "Not Yet Assessed"
    NOT_APPLICABLE = "Not Applicable"


class RiskLevel(Enum):
    """Risk assessment levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    MINIMAL = "Minimal"


class IncidentType(Enum):
    """NDIS Reportable Incident Types."""

    DEATH = "Death of participant"
    SERIOUS_INJURY = "Serious injury"
    ABUSE_NEGLECT = "Abuse or neglect"
    UNLAWFUL_CONDUCT = "Unlawful physical/sexual conduct"
    RESTRICTIVE_PRACTICE = "Unauthorized restrictive practice"
    OTHER_REPORTABLE = "Other reportable incident"


class IncidentStatus(Enum):
    """Incident investigation status."""

    REPORTED = "Reported"
    UNDER_INVESTIGATION = "Under Investigation"
    ACTION_REQUIRED = "Action Required"
    NOTIFIED_COMMISSION = "Notified to Commission"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class WorkerScreeningStatus(Enum):
    """Worker screening status."""

    VALID = "Valid"
    EXPIRED = "Expired"
    PENDING = "Pending"
    REVOKED = "Revoked"
    NOT_REQUIRED = "Not Required"


class CorrectiveActionStatus(Enum):
    """Corrective action status."""

    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    VERIFIED = "Verified"
    OVERDUE = "Overdue"


# ══════════════════════════════════════════════════════════════════════════════
# NDIS PRACTICE STANDARDS FRAMEWORK
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class QualityIndicator:
    """NDIS Quality Indicator."""

    code: str
    description: str
    evidence_required: list[str]
    status: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    evidence_provided: list[str] = field(default_factory=list)
    last_assessed: Optional[str] = None
    assessor: str = ""
    notes: str = ""


@dataclass
class PracticeStandard:
    """NDIS Practice Standard."""

    module: int
    standard_code: str
    title: str
    outcome_statement: str
    quality_indicators: list[QualityIndicator]
    risk_level: RiskLevel = RiskLevel.MEDIUM

    def compliance_status(self) -> ComplianceStatus:
        """Calculate overall compliance status."""
        statuses = [qi.status for qi in self.quality_indicators]

        if ComplianceStatus.NON_COMPLIANT in statuses:
            return ComplianceStatus.NON_COMPLIANT
        if ComplianceStatus.PARTIALLY_COMPLIANT in statuses:
            return ComplianceStatus.PARTIALLY_COMPLIANT
        if all(s == ComplianceStatus.COMPLIANT for s in statuses):
            return ComplianceStatus.COMPLIANT
        return ComplianceStatus.NOT_ASSESSED

    def compliance_percentage(self) -> float:
        """Calculate percentage compliant."""
        total = len(self.quality_indicators)
        if total == 0:
            return 0.0
        compliant = sum(
            1
            for qi in self.quality_indicators
            if qi.status == ComplianceStatus.COMPLIANT
        )
        return (compliant / total) * 100


class NDISPracticeStandardsFramework:
    """
    Complete NDIS Practice Standards Framework.

    Based on NDIS Practice Standards and Quality Indicators (2021).
    """

    @staticmethod
    def get_core_module_1() -> list[PracticeStandard]:
        """Module 1: Rights and Responsibilities."""
        return [
            PracticeStandard(
                module=1,
                standard_code="1.1",
                title="Person-Centred Supports",
                outcome_statement="Each participant accesses supports that promote, uphold and respect their legal and human rights.",
                quality_indicators=[
                    QualityIndicator(
                        code="1.1.1",
                        description="Information is provided to participants about their rights",
                        evidence_required=[
                            "Rights information pack given to participants",
                            "Easy Read rights documentation",
                            "Evidence of rights discussions",
                        ],
                    ),
                    QualityIndicator(
                        code="1.1.2",
                        description="Supports are provided in a manner that respects individual values, beliefs, and cultural requirements",
                        evidence_required=[
                            "Cultural considerations in service delivery",
                            "Individualised support plans",
                            "Participant feedback",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=1,
                standard_code="1.2",
                title="Individual Values and Beliefs",
                outcome_statement="Each participant's values and beliefs are respected and upheld.",
                quality_indicators=[
                    QualityIndicator(
                        code="1.2.1",
                        description="Staff understand and respect participant values",
                        evidence_required=[
                            "Training records",
                            "Supervision notes",
                            "Participant feedback",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=1,
                standard_code="1.3",
                title="Privacy and Dignity",
                outcome_statement="Each participant's right to privacy is respected and upheld.",
                quality_indicators=[
                    QualityIndicator(
                        code="1.3.1",
                        description="Privacy policy is implemented",
                        evidence_required=[
                            "Privacy policy document",
                            "Staff training on privacy",
                            "Consent forms",
                        ],
                    ),
                    QualityIndicator(
                        code="1.3.2",
                        description="Participant information is stored securely",
                        evidence_required=[
                            "Data security measures",
                            "Access controls",
                            "Encryption evidence",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=1,
                standard_code="1.4",
                title="Independence and Informed Choice",
                outcome_statement="Each participant is supported to exercise informed choice and control.",
                quality_indicators=[
                    QualityIndicator(
                        code="1.4.1",
                        description="Participants are supported to make decisions",
                        evidence_required=[
                            "Decision support documentation",
                            "Easy Read materials",
                            "Advocate involvement records",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=1,
                standard_code="1.5",
                title="Violence, Abuse, Neglect, Exploitation and Discrimination",
                outcome_statement="Each participant is protected from violence, abuse, neglect, exploitation and discrimination.",
                quality_indicators=[
                    QualityIndicator(
                        code="1.5.1",
                        description="Safeguarding policies and procedures are in place",
                        evidence_required=[
                            "Safeguarding policy",
                            "Staff training records",
                            "Incident registers",
                        ],
                    ),
                    QualityIndicator(
                        code="1.5.2",
                        description="Workers undergo screening checks",
                        evidence_required=[
                            "NDIS Worker Screening records",
                            "Working With Children checks",
                            "Police check registers",
                        ],
                    ),
                ],
                risk_level=RiskLevel.HIGH,
            ),
        ]

    @staticmethod
    def get_core_module_2() -> list[PracticeStandard]:
        """Module 2: Provider Governance and Operational Management."""
        return [
            PracticeStandard(
                module=2,
                standard_code="2.1",
                title="Governance and Operational Management",
                outcome_statement="Each provider has sound governance and operational management.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.1.1",
                        description="Clear governance structure is documented",
                        evidence_required=[
                            "Organisation chart",
                            "Position descriptions",
                            "Delegation authorities",
                        ],
                    ),
                    QualityIndicator(
                        code="2.1.2",
                        description="Policies and procedures guide operations",
                        evidence_required=[
                            "Policy register",
                            "Version control evidence",
                            "Staff acknowledgments",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=2,
                standard_code="2.2",
                title="Risk Management",
                outcome_statement="Risks to participants are identified and managed.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.2.1",
                        description="Risk management framework is implemented",
                        evidence_required=[
                            "Risk register",
                            "Risk assessment tools",
                            "Risk review minutes",
                        ],
                    ),
                ],
                risk_level=RiskLevel.HIGH,
            ),
            PracticeStandard(
                module=2,
                standard_code="2.3",
                title="Quality Management",
                outcome_statement="Quality management drives continuous improvement.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.3.1",
                        description="Quality management system is in place",
                        evidence_required=[
                            "Quality policy",
                            "Continuous improvement plan",
                            "Performance indicators",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=2,
                standard_code="2.4",
                title="Information Management",
                outcome_statement="Information is managed to ensure effective governance.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.4.1",
                        description="Records management system is effective",
                        evidence_required=[
                            "Records management policy",
                            "Data backup evidence",
                            "Access logs",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=2,
                standard_code="2.5",
                title="Feedback and Complaints Management",
                outcome_statement="Feedback and complaints are used to drive improvement.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.5.1",
                        description="Complaints process is accessible",
                        evidence_required=[
                            "Complaints policy",
                            "Easy Read complaints guide",
                            "Complaints register",
                        ],
                    ),
                    QualityIndicator(
                        code="2.5.2",
                        description="Complaints are resolved appropriately",
                        evidence_required=[
                            "Resolution records",
                            "Outcome communications",
                            "Trend analysis",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=2,
                standard_code="2.6",
                title="Incident Management",
                outcome_statement="Incidents are managed effectively.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.6.1",
                        description="Incident management system captures all incidents",
                        evidence_required=[
                            "Incident policy",
                            "Incident register",
                            "Notification records",
                        ],
                    ),
                    QualityIndicator(
                        code="2.6.2",
                        description="Reportable incidents are notified to the Commission",
                        evidence_required=[
                            "Commission notification records",
                            "5-day notification evidence",
                            "Investigation reports",
                        ],
                    ),
                ],
                risk_level=RiskLevel.CRITICAL,
            ),
            PracticeStandard(
                module=2,
                standard_code="2.7",
                title="Human Resource Management",
                outcome_statement="Workers are appropriately qualified and supported.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.7.1",
                        description="Worker screening requirements are met",
                        evidence_required=[
                            "NDIS Worker Screening clearances",
                            "Screening register",
                            "Expiry monitoring system",
                        ],
                    ),
                    QualityIndicator(
                        code="2.7.2",
                        description="Workers receive appropriate training",
                        evidence_required=[
                            "Training matrix",
                            "Training records",
                            "Competency assessments",
                        ],
                    ),
                ],
                risk_level=RiskLevel.HIGH,
            ),
            PracticeStandard(
                module=2,
                standard_code="2.8",
                title="Continuity of Supports",
                outcome_statement="Continuity of support is maintained.",
                quality_indicators=[
                    QualityIndicator(
                        code="2.8.1",
                        description="Business continuity plan addresses support continuity",
                        evidence_required=[
                            "Business continuity plan",
                            "Participant transition plans",
                            "Emergency procedures",
                        ],
                    ),
                ],
            ),
        ]

    @staticmethod
    def get_core_module_3() -> list[PracticeStandard]:
        """Module 3: Provision of Supports."""
        return [
            PracticeStandard(
                module=3,
                standard_code="3.1",
                title="Access to Supports",
                outcome_statement="Each participant accesses supports in a manner that meets their needs.",
                quality_indicators=[
                    QualityIndicator(
                        code="3.1.1",
                        description="Clear intake and assessment processes",
                        evidence_required=[
                            "Intake procedures",
                            "Assessment documentation",
                            "Service agreements",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=3,
                standard_code="3.2",
                title="Support Planning",
                outcome_statement="Each participant's support is planned appropriately.",
                quality_indicators=[
                    QualityIndicator(
                        code="3.2.1",
                        description="Support plans are developed with participants",
                        evidence_required=[
                            "Support planning records",
                            "Participant involvement evidence",
                            "Goal-setting documentation",
                        ],
                    ),
                    QualityIndicator(
                        code="3.2.2",
                        description="Support plans are regularly reviewed",
                        evidence_required=[
                            "Review schedule",
                            "Review meeting notes",
                            "Plan update records",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=3,
                standard_code="3.3",
                title="Service Agreements",
                outcome_statement="Service agreements are established with each participant.",
                quality_indicators=[
                    QualityIndicator(
                        code="3.3.1",
                        description="Service agreements are in place",
                        evidence_required=[
                            "Signed service agreements",
                            "Terms and conditions",
                            "Fee schedules",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=3,
                standard_code="3.4",
                title="Responsive Support Provision",
                outcome_statement="Supports are delivered responsively.",
                quality_indicators=[
                    QualityIndicator(
                        code="3.4.1",
                        description="Supports are responsive to participant needs",
                        evidence_required=[
                            "Progress notes",
                            "Feedback records",
                            "Outcome measurements",
                        ],
                    ),
                ],
            ),
            PracticeStandard(
                module=3,
                standard_code="3.5",
                title="Transitions to or from the Provider",
                outcome_statement="Transitions are managed effectively.",
                quality_indicators=[
                    QualityIndicator(
                        code="3.5.1",
                        description="Transition planning supports continuity",
                        evidence_required=[
                            "Transition protocols",
                            "Handover documentation",
                            "Participant exit records",
                        ],
                    ),
                ],
            ),
        ]

    @classmethod
    def get_all_standards(cls) -> list[PracticeStandard]:
        """Get all core module standards."""
        return (
            cls.get_core_module_1() + cls.get_core_module_2() + cls.get_core_module_3()
        )


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Worker:
    """Worker record with screening status."""

    worker_id: str
    name: str
    role: str
    employment_type: str  # Full-time, Part-time, Casual
    start_date: str
    screening_status: WorkerScreeningStatus
    screening_number: str
    screening_expiry: str
    wwcc_number: str
    wwcc_expiry: str
    training_completed: list[str] = field(default_factory=list)
    training_due: list[str] = field(default_factory=list)


@dataclass
class Incident:
    """NDIS Reportable Incident."""

    incident_id: str
    incident_type: IncidentType
    participant_id: str
    date_occurred: str
    time_occurred: str
    date_reported: str
    reported_by: str
    location: str
    description: str
    immediate_actions: str
    severity: str
    status: IncidentStatus
    commission_notified: bool = False
    commission_notification_date: Optional[str] = None
    commission_notification_id: Optional[str] = None
    investigation_started: Optional[str] = None
    investigation_completed: Optional[str] = None
    findings: str = ""
    root_cause: str = ""
    corrective_actions: list[str] = field(default_factory=list)
    closed_date: Optional[str] = None

    def requires_5_day_notification(self) -> bool:
        """Check if incident requires 5-day notification."""
        return self.incident_type in [
            IncidentType.DEATH,
            IncidentType.SERIOUS_INJURY,
            IncidentType.ABUSE_NEGLECT,
            IncidentType.UNLAWFUL_CONDUCT,
            IncidentType.RESTRICTIVE_PRACTICE,
        ]

    def days_since_occurred(self) -> int:
        """Days since incident occurred."""
        occurred = datetime.strptime(self.date_occurred, "%Y-%m-%d")
        return (datetime.now() - occurred).days


@dataclass
class Complaint:
    """Complaint record."""

    complaint_id: str
    received_date: str
    complainant_type: str  # Participant, Family, Worker, External
    nature: str
    description: str
    severity: str
    status: str  # Received, Acknowledged, Investigating, Resolved, Closed
    assigned_to: str
    resolution: str = ""
    resolved_date: Optional[str] = None
    satisfaction_rating: Optional[int] = None


@dataclass
class CorrectiveAction:
    """Corrective action item."""

    action_id: str
    source_type: str  # Incident, Complaint, Audit, Self-Assessment
    source_id: str
    description: str
    assigned_to: str
    due_date: str
    status: CorrectiveActionStatus
    evidence_required: str
    evidence_provided: str = ""
    completed_date: Optional[str] = None
    verified_by: str = ""
    verified_date: Optional[str] = None


@dataclass
class AuditFinding:
    """Audit finding record."""

    finding_id: str
    audit_date: str
    audit_type: str  # Internal, External, Commission
    standard_code: str
    finding_type: str  # Conformance, Minor NC, Major NC, Observation
    description: str
    evidence_reviewed: str
    status: str  # Open, Action Required, Closed
    corrective_actions: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE DATA STORE
# ══════════════════════════════════════════════════════════════════════════════


class ComplianceDataStore:
    """In-memory store for compliance data."""

    def __init__(self):
        self.standards: list[PracticeStandard] = []
        self.workers: dict[str, Worker] = {}
        self.incidents: dict[str, Incident] = {}
        self.complaints: dict[str, Complaint] = {}
        self.corrective_actions: dict[str, CorrectiveAction] = {}
        self.audit_findings: dict[str, AuditFinding] = {}
        self.audit_log: list[dict] = []

    def log_action(self, user: str, action: str, resource: str, details: str = ""):
        """Log audit trail entry."""
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "user": user,
                "action": action,
                "resource": resource,
                "details": details,
            }
        )

    def get_screening_alerts(self) -> list[dict]:
        """Get workers with screening issues."""
        alerts = []
        today = datetime.now()

        for worker in self.workers.values():
            # Check expired
            if worker.screening_status == WorkerScreeningStatus.EXPIRED:
                alerts.append(
                    {
                        "worker_id": worker.worker_id,
                        "name": worker.name,
                        "alert_type": "EXPIRED",
                        "severity": "CRITICAL",
                        "details": "NDIS Worker Screening has expired",
                    }
                )

            # Check expiring soon
            elif worker.screening_status == WorkerScreeningStatus.VALID:
                try:
                    expiry = datetime.strptime(worker.screening_expiry, "%Y-%m-%d")
                    days_to_expiry = (expiry - today).days
                    if days_to_expiry <= 30:
                        alerts.append(
                            {
                                "worker_id": worker.worker_id,
                                "name": worker.name,
                                "alert_type": "EXPIRING_SOON",
                                "severity": (
                                    "HIGH" if days_to_expiry <= 14 else "MEDIUM"
                                ),
                                "details": f"Expires in {days_to_expiry} days",
                            }
                        )
                except ValueError:
                    pass

            # Check pending
            elif worker.screening_status == WorkerScreeningStatus.PENDING:
                alerts.append(
                    {
                        "worker_id": worker.worker_id,
                        "name": worker.name,
                        "alert_type": "PENDING",
                        "severity": "MEDIUM",
                        "details": "Worker screening pending - restrict duties",
                    }
                )

        return sorted(
            alerts,
            key=lambda x: ["CRITICAL", "HIGH", "MEDIUM", "LOW"].index(x["severity"]),
        )

    def get_open_incidents(self) -> list[Incident]:
        """Get incidents requiring attention."""
        return [
            i
            for i in self.incidents.values()
            if i.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]
        ]

    def get_overdue_notifications(self) -> list[Incident]:
        """Get incidents overdue for Commission notification."""
        overdue = []
        for incident in self.incidents.values():
            if (
                incident.requires_5_day_notification()
                and not incident.commission_notified
            ):
                if incident.days_since_occurred() > 5:
                    overdue.append(incident)
        return overdue

    def get_overdue_actions(self) -> list[CorrectiveAction]:
        """Get overdue corrective actions."""
        today = datetime.now()
        overdue = []
        for action in self.corrective_actions.values():
            if action.status not in [
                CorrectiveActionStatus.COMPLETED,
                CorrectiveActionStatus.VERIFIED,
            ]:
                try:
                    due = datetime.strptime(action.due_date, "%Y-%m-%d")
                    if due < today:
                        overdue.append(action)
                except ValueError:
                    pass
        return overdue

    def calculate_compliance_score(self) -> dict:
        """Calculate overall compliance score."""
        if not self.standards:
            return {"score": 0, "compliant": 0, "total": 0}

        compliant = sum(
            1
            for s in self.standards
            if s.compliance_status() == ComplianceStatus.COMPLIANT
        )
        partial = sum(
            1
            for s in self.standards
            if s.compliance_status() == ComplianceStatus.PARTIALLY_COMPLIANT
        )
        total = len(self.standards)

        # Score: Full compliance = 100%, Partial = 50%
        score = ((compliant * 100) + (partial * 50)) / total if total > 0 else 0

        return {
            "score": round(score, 1),
            "compliant": compliant,
            "partial": partial,
            "non_compliant": total - compliant - partial,
            "total": total,
        }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA GENERATOR
# ══════════════════════════════════════════════════════════════════════════════


class DemoDataGenerator:
    """Generate realistic compliance demo data."""

    WORKER_NAMES = ["J. Smith", "M. Brown", "S. Wilson", "K. Taylor", "L. Davis"]

    @classmethod
    def create_demo_workers(cls, count: int = 5) -> list[Worker]:
        """Create demo workers with various screening statuses."""
        workers = []
        statuses = [
            WorkerScreeningStatus.VALID,
            WorkerScreeningStatus.VALID,
            WorkerScreeningStatus.VALID,
            WorkerScreeningStatus.PENDING,
            WorkerScreeningStatus.EXPIRED,
        ]

        for i in range(count):
            name = cls.WORKER_NAMES[i % len(cls.WORKER_NAMES)]
            status = statuses[i % len(statuses)]

            if status == WorkerScreeningStatus.VALID:
                expiry = (datetime.now() + timedelta(days=30 * (i + 1))).strftime(
                    "%Y-%m-%d"
                )
            elif status == WorkerScreeningStatus.EXPIRED:
                expiry = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            else:
                expiry = ""

            workers.append(
                Worker(
                    worker_id=f"W{i+1:03d}",
                    name=name,
                    role=["Support Worker", "Coordinator", "Manager"][i % 3],
                    employment_type=["Full-time", "Part-time", "Casual"][i % 3],
                    start_date=(
                        datetime.now() - timedelta(days=365 * (i + 1))
                    ).strftime("%Y-%m-%d"),
                    screening_status=status,
                    screening_number=f"NSW{secrets.randbelow(1000000):06d}",
                    screening_expiry=expiry,
                    wwcc_number=f"WWC{secrets.randbelow(1000000):07d}",
                    wwcc_expiry=(datetime.now() + timedelta(days=365)).strftime(
                        "%Y-%m-%d"
                    ),
                    training_completed=[
                        "NDIS Orientation",
                        "Safeguarding",
                        "Manual Handling",
                    ],
                    training_due=["First Aid Refresher"] if i % 2 == 0 else [],
                )
            )

        return workers

    @classmethod
    def create_demo_incidents(cls) -> list[Incident]:
        """Create demo incidents."""
        return [
            Incident(
                incident_id="INC001",
                incident_type=IncidentType.OTHER_REPORTABLE,
                participant_id="P001",
                date_occurred=(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                time_occurred="14:30",
                date_reported=(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                reported_by="J. Smith",
                location="Participant's home",
                description="Participant fell during transfer. No injury sustained.",
                immediate_actions="Checked participant wellbeing, notified family, documented incident.",
                severity="Low",
                status=IncidentStatus.UNDER_INVESTIGATION,
            ),
            Incident(
                incident_id="INC002",
                incident_type=IncidentType.SERIOUS_INJURY,
                participant_id="P002",
                date_occurred=(datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"),
                time_occurred="10:15",
                date_reported=(datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"),
                reported_by="M. Brown",
                location="Community outing",
                description="Participant sustained laceration requiring medical attention.",
                immediate_actions="First aid administered, ambulance called, family notified.",
                severity="High",
                status=IncidentStatus.NOTIFIED_COMMISSION,
                commission_notified=True,
                commission_notification_date=(
                    datetime.now() - timedelta(days=3)
                ).strftime("%Y-%m-%d"),
                commission_notification_id="COMM123456",
            ),
        ]

    @classmethod
    def create_demo_complaints(cls) -> list[Complaint]:
        """Create demo complaints."""
        return [
            Complaint(
                complaint_id="CMP001",
                received_date=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                complainant_type="Family",
                nature="Service Quality",
                description="Concern about communication from support workers.",
                severity="Medium",
                status="Investigating",
                assigned_to="Coordinator",
            ),
            Complaint(
                complaint_id="CMP002",
                received_date=(datetime.now() - timedelta(days=30)).strftime(
                    "%Y-%m-%d"
                ),
                complainant_type="Participant",
                nature="Scheduling",
                description="Repeated late arrival of support worker.",
                severity="Low",
                status="Resolved",
                assigned_to="Manager",
                resolution="Adjusted schedule and spoke with worker about punctuality.",
                resolved_date=(datetime.now() - timedelta(days=20)).strftime(
                    "%Y-%m-%d"
                ),
                satisfaction_rating=4,
            ),
        ]

    @classmethod
    def create_demo_actions(cls) -> list[CorrectiveAction]:
        """Create demo corrective actions."""
        return [
            CorrectiveAction(
                action_id="CA001",
                source_type="Incident",
                source_id="INC001",
                description="Review transfer techniques with worker",
                assigned_to="Coordinator",
                due_date=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                status=CorrectiveActionStatus.IN_PROGRESS,
                evidence_required="Training record, competency assessment",
            ),
            CorrectiveAction(
                action_id="CA002",
                source_type="Complaint",
                source_id="CMP001",
                description="Implement weekly communication check-in",
                assigned_to="Manager",
                due_date=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
                status=CorrectiveActionStatus.OVERDUE,
                evidence_required="Communication log, family feedback",
            ),
        ]


# ══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class NDISComplianceAssistant:
    """
    NDIS Quality & Safeguards Compliance Assistant.

    Helps compliance officers manage NDIS Practice Standards compliance.
    """

    def __init__(self, store: ComplianceDataStore, user_id: str = "compliance_officer"):
        self.store = store
        self.user_id = user_id

    def get_dashboard(self) -> str:
        """Get compliance dashboard."""
        score = self.store.calculate_compliance_score()
        screening_alerts = self.store.get_screening_alerts()
        open_incidents = self.store.get_open_incidents()
        overdue_notifications = self.store.get_overdue_notifications()
        overdue_actions = self.store.get_overdue_actions()

        critical_count = len(
            [a for a in screening_alerts if a["severity"] == "CRITICAL"]
        )

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  NDIS COMPLIANCE DASHBOARD                                                    ║
║  {datetime.now().strftime('%Y-%m-%d %H:%M')}                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

📊 COMPLIANCE SCORE: {score['score']}%
   ├─ Compliant: {score['compliant']} standards
   ├─ Partially Compliant: {score['partial']} standards
   └─ Non-Compliant: {score['non_compliant']} standards

{'🚨 CRITICAL ALERTS' + '─' * 45 if critical_count > 0 else ''}
"""
        if critical_count > 0:
            for alert in screening_alerts[:3]:
                if alert["severity"] == "CRITICAL":
                    output += f"   ❌ {alert['name']}: {alert['details']}\n"

        if overdue_notifications:
            output += f"""
⚠️  OVERDUE COMMISSION NOTIFICATIONS: {len(overdue_notifications)}
"""
            for inc in overdue_notifications[:2]:
                output += f"   • {inc.incident_id}: {inc.days_since_occurred()} days overdue!\n"

        output += f"""
📋 OPEN MATTERS
   • Incidents: {len(open_incidents)}
   • Corrective Actions: {len([a for a in self.store.corrective_actions.values() if a.status not in [CorrectiveActionStatus.COMPLETED, CorrectiveActionStatus.VERIFIED]])}
   • Overdue Actions: {len(overdue_actions)}
   • Worker Screening Alerts: {len(screening_alerts)}

QUICK ACTIONS
{'─' * 50}
1. Review worker screening
2. Check open incidents  
3. View corrective actions
4. Run compliance assessment
5. Generate audit report
"""
        return output

    def check_worker_screening(self) -> str:
        """Check worker screening compliance."""
        alerts = self.store.get_screening_alerts()

        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  WORKER SCREENING COMPLIANCE CHECK                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        if not alerts:
            output += "✅ All workers have valid screening clearances.\n"
        else:
            output += f"⚠️  {len(alerts)} screening issues found:\n\n"

            for alert in alerts:
                severity_emoji = {
                    "CRITICAL": "🚨",
                    "HIGH": "⚠️",
                    "MEDIUM": "📋",
                    "LOW": "ℹ️",
                }.get(alert["severity"], "📌")

                output += f"{severity_emoji} [{alert['severity']}] {alert['name']} ({alert['worker_id']})\n"
                output += f"   {alert['details']}\n"

                if alert["alert_type"] == "EXPIRED":
                    output += (
                        "   ACTION: Remove from roster immediately until cleared\n"
                    )
                elif alert["alert_type"] == "PENDING":
                    output += "   ACTION: Restrict to supervised duties only\n"
                elif alert["alert_type"] == "EXPIRING_SOON":
                    output += "   ACTION: Initiate renewal process\n"
                output += "\n"

        # Summary
        workers = list(self.store.workers.values())
        valid = sum(
            1 for w in workers if w.screening_status == WorkerScreeningStatus.VALID
        )

        output += f"""
SUMMARY
{'─' * 50}
Total Workers: {len(workers)}
Valid Screening: {valid}
Compliance Rate: {(valid / len(workers) * 100) if workers else 0:.1f}%

Standard Reference: NDIS Practice Standards 2.7 - Human Resource Management
"""
        return output

    def review_incidents(self) -> str:
        """Review open incidents."""
        open_incidents = self.store.get_open_incidents()

        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  INCIDENT REVIEW                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        if not open_incidents:
            output += "✅ No open incidents requiring attention.\n"
            return output

        output += f"📋 {len(open_incidents)} open incidents:\n\n"

        for incident in open_incidents:
            status_emoji = {
                IncidentStatus.REPORTED: "📝",
                IncidentStatus.UNDER_INVESTIGATION: "🔍",
                IncidentStatus.ACTION_REQUIRED: "⚠️",
                IncidentStatus.NOTIFIED_COMMISSION: "📤",
            }.get(incident.status, "📌")

            days = incident.days_since_occurred()

            output += f"""
{status_emoji} {incident.incident_id} - {incident.incident_type.value}
   Date: {incident.date_occurred} ({days} days ago)
   Status: {incident.status.value}
   Participant: {incident.participant_id}
   
   Description: {incident.description[:100]}...
"""
            # Check notification requirements
            if incident.requires_5_day_notification():
                if not incident.commission_notified:
                    if days > 5:
                        output += (
                            "   🚨 OVERDUE: Must notify Commission within 24 hours!\n"
                        )
                    else:
                        output += f"   ⏰ Notification due in {5 - days} days\n"
                else:
                    output += f"   ✅ Commission notified: {incident.commission_notification_date}\n"

            output += "\n"

        output += """
INCIDENT MANAGEMENT REQUIREMENTS
{'─' * 50}
• Report within 24 hours of becoming aware
• Notify Commission within 5 business days for reportable incidents
• Investigate root cause
• Implement corrective actions
• Monitor and review

Standard Reference: NDIS Practice Standards 2.6 - Incident Management
"""
        return output

    def view_corrective_actions(self) -> str:
        """View corrective actions status."""
        actions = list(self.store.corrective_actions.values())
        overdue = self.store.get_overdue_actions()

        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  CORRECTIVE ACTIONS REGISTER                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        if not actions:
            output += "No corrective actions on record.\n"
            return output

        if overdue:
            output += f"⚠️  {len(overdue)} OVERDUE ACTIONS:\n\n"
            for action in overdue:
                output += f"   🚨 {action.action_id}: {action.description[:50]}...\n"
                output += (
                    f"      Due: {action.due_date} | Assigned: {action.assigned_to}\n\n"
                )

        # Group by status
        status_groups = {}
        for action in actions:
            status = action.status.value
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(action)

        output += "ALL ACTIONS BY STATUS:\n"
        output += "─" * 50 + "\n\n"

        for status, action_list in status_groups.items():
            status_emoji = {
                "Open": "📝",
                "In Progress": "🔄",
                "Completed": "✅",
                "Verified": "✔️",
                "Overdue": "🚨",
            }.get(status, "📌")

            output += f"{status_emoji} {status} ({len(action_list)})\n"
            for action in action_list[:3]:
                output += f"   • {action.action_id}: {action.description[:40]}...\n"
            if len(action_list) > 3:
                output += f"   ... and {len(action_list) - 3} more\n"
            output += "\n"

        return output

    def run_compliance_assessment(self) -> str:
        """Run compliance self-assessment."""
        self.store.log_action(
            self.user_id, "RUN_ASSESSMENT", "compliance", "Full assessment"
        )

        standards = self.store.standards

        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  NDIS PRACTICE STANDARDS COMPLIANCE ASSESSMENT                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        # Group by module
        module_standards: dict[int, list] = {1: [], 2: [], 3: []}
        for standard in standards:
            module_standards[standard.module].append(standard)

        module_names = {
            1: "Rights and Responsibilities",
            2: "Provider Governance",
            3: "Provision of Supports",
        }

        for module_num, module_stds in module_standards.items():
            if not module_stds:
                continue

            compliant = sum(
                1
                for s in module_stds
                if s.compliance_status() == ComplianceStatus.COMPLIANT
            )
            module_pct = (compliant / len(module_stds) * 100) if module_stds else 0

            output += f"""
MODULE {module_num}: {module_names[module_num]}
{'─' * 60}
Compliance: {module_pct:.0f}% ({compliant}/{len(module_stds)} standards)

"""
            for standard in module_stds:
                status = standard.compliance_status()
                status_emoji = {
                    ComplianceStatus.COMPLIANT: "✅",
                    ComplianceStatus.PARTIALLY_COMPLIANT: "⚠️",
                    ComplianceStatus.NON_COMPLIANT: "❌",
                    ComplianceStatus.NOT_ASSESSED: "⬜",
                }.get(status, "📌")

                output += (
                    f"  {status_emoji} {standard.standard_code}: {standard.title}\n"
                )

                # Show non-compliant indicators
                if status in [
                    ComplianceStatus.NON_COMPLIANT,
                    ComplianceStatus.PARTIALLY_COMPLIANT,
                ]:
                    for qi in standard.quality_indicators:
                        if qi.status in [
                            ComplianceStatus.NON_COMPLIANT,
                            ComplianceStatus.PARTIALLY_COMPLIANT,
                        ]:
                            output += f"     └─ {qi.code}: {qi.status.value}\n"

            output += "\n"

        # Overall score
        score = self.store.calculate_compliance_score()
        output += f"""
═══════════════════════════════════════════════════════════════════════════════
OVERALL COMPLIANCE SCORE: {score['score']}%

Assessment Date: {datetime.now().strftime('%Y-%m-%d')}
Assessor: {self.user_id}

Note: This is a self-assessment. Certification audits are conducted by 
approved quality auditors. For audit scheduling, visit ndiscommission.gov.au
═══════════════════════════════════════════════════════════════════════════════
"""
        return output

    def generate_audit_report(self) -> str:
        """Generate audit preparation report."""
        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  AUDIT PREPARATION REPORT                                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

This report summarizes your audit readiness across key areas.

"""
        # Worker screening
        workers = list(self.store.workers.values())
        valid_screening = sum(
            1 for w in workers if w.screening_status == WorkerScreeningStatus.VALID
        )

        output += f"""
1. WORKER SCREENING
   {'✅' if valid_screening == len(workers) else '⚠️'} {valid_screening}/{len(workers)} workers have valid screening
   Evidence needed:
   • NDIS Worker Screening clearance register
   • Working With Children check register
   • Screening verification records

"""
        # Incidents
        incidents = list(self.store.incidents.values())
        notified = sum(
            1
            for i in incidents
            if i.commission_notified or not i.requires_5_day_notification()
        )

        output += f"""
2. INCIDENT MANAGEMENT
   {'✅' if notified == len(incidents) else '⚠️'} {notified}/{len(incidents)} incidents properly managed
   Evidence needed:
   • Incident register
   • Commission notification records
   • Investigation reports
   • Corrective action evidence

"""
        # Complaints
        complaints = list(self.store.complaints.values())
        resolved = sum(1 for c in complaints if c.status == "Resolved")

        output += f"""
3. COMPLAINTS MANAGEMENT
   {'✅' if resolved >= len(complaints) * 0.8 else '⚠️'} {resolved}/{len(complaints)} complaints resolved
   Evidence needed:
   • Complaints register
   • Resolution records
   • Satisfaction surveys
   • Trend analysis

"""
        # Corrective actions
        actions = list(self.store.corrective_actions.values())
        completed = sum(
            1
            for a in actions
            if a.status
            in [CorrectiveActionStatus.COMPLETED, CorrectiveActionStatus.VERIFIED]
        )

        output += f"""
4. CORRECTIVE ACTIONS
   {'✅' if completed >= len(actions) * 0.9 else '⚠️'} {completed}/{len(actions)} actions completed
   Evidence needed:
   • Action tracking register
   • Evidence of completion
   • Verification records

"""
        # Standards compliance
        score = self.store.calculate_compliance_score()

        output += f"""
5. PRACTICE STANDARDS COMPLIANCE
   {'✅' if score['score'] >= 80 else '⚠️'} Overall score: {score['score']}%
   Evidence needed:
   • Policies and procedures
   • Training records
   • Participant feedback
   • Service documentation

═══════════════════════════════════════════════════════════════════════════════
AUDIT READINESS CHECKLIST

Before your audit, ensure you have:
□ Current worker screening register with expiry dates
□ Complete incident register with investigation records
□ Complaints register with resolution evidence
□ Corrective action log with completion evidence
□ Current policies aligned to Practice Standards
□ Training matrix and records
□ Participant files (consent, plans, progress notes)
□ Quality improvement evidence

For audit scheduling and requirements: ndiscommission.gov.au
═══════════════════════════════════════════════════════════════════════════════
"""
        return output


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run demonstration."""
    print(COMPLIANCE_DISCLAIMER)

    print("\n📦 Initializing compliance system...")
    store = ComplianceDataStore()

    # Load demo data
    store.standards = NDISPracticeStandardsFramework.get_all_standards()

    for worker in DemoDataGenerator.create_demo_workers():
        store.workers[worker.worker_id] = worker

    for incident in DemoDataGenerator.create_demo_incidents():
        store.incidents[incident.incident_id] = incident

    for complaint in DemoDataGenerator.create_demo_complaints():
        store.complaints[complaint.complaint_id] = complaint

    for action in DemoDataGenerator.create_demo_actions():
        store.corrective_actions[action.action_id] = action

    # Simulate some compliance status
    for standard in store.standards[:5]:
        for qi in standard.quality_indicators:
            qi.status = ComplianceStatus.COMPLIANT
    for standard in store.standards[5:10]:
        for qi in standard.quality_indicators:
            qi.status = ComplianceStatus.PARTIALLY_COMPLIANT

    assistant = NDISComplianceAssistant(store)

    # Demo sequence
    print(assistant.get_dashboard())
    input("\nPress Enter to check worker screening...")

    print(assistant.check_worker_screening())
    input("\nPress Enter to review incidents...")

    print(assistant.review_incidents())
    input("\nPress Enter to view corrective actions...")

    print(assistant.view_corrective_actions())
    input("\nPress Enter to run compliance assessment...")

    print(assistant.run_compliance_assessment())
    input("\nPress Enter to generate audit report...")

    print(assistant.generate_audit_report())

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


def run_interactive():
    """Run interactive mode."""
    print(COMPLIANCE_DISCLAIMER)

    # Setup
    store = ComplianceDataStore()
    store.standards = NDISPracticeStandardsFramework.get_all_standards()

    for worker in DemoDataGenerator.create_demo_workers():
        store.workers[worker.worker_id] = worker
    for incident in DemoDataGenerator.create_demo_incidents():
        store.incidents[incident.incident_id] = incident
    for action in DemoDataGenerator.create_demo_actions():
        store.corrective_actions[action.action_id] = action

    # Set some compliance statuses
    for i, standard in enumerate(store.standards):
        for qi in standard.quality_indicators:
            if i < 5:
                qi.status = ComplianceStatus.COMPLIANT
            elif i < 10:
                qi.status = ComplianceStatus.PARTIALLY_COMPLIANT

    assistant = NDISComplianceAssistant(store)

    print(assistant.get_dashboard())

    while True:
        try:
            cmd = input("\nCompliance> ").strip().lower()

            if not cmd:
                continue

            if cmd in ("quit", "exit"):
                print("Goodbye!")
                break
            elif cmd in ("1", "screening", "workers"):
                print(assistant.check_worker_screening())
            elif cmd in ("2", "incidents"):
                print(assistant.review_incidents())
            elif cmd in ("3", "actions"):
                print(assistant.view_corrective_actions())
            elif cmd in ("4", "assess", "assessment"):
                print(assistant.run_compliance_assessment())
            elif cmd in ("5", "audit", "report"):
                print(assistant.generate_audit_report())
            elif cmd == "dashboard":
                print(assistant.get_dashboard())
            else:
                print(
                    "Commands: 1-screening, 2-incidents, 3-actions, 4-assess, 5-audit, quit"
                )

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="NDIS Compliance System")
    parser.add_argument("--demo", action="store_true", help="Run demonstration")
    parser.add_argument(
        "--audit-prep", action="store_true", help="Generate audit preparation report"
    )
    parser.add_argument(
        "--incident-review", action="store_true", help="Review incidents"
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
