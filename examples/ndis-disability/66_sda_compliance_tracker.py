#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
SDA Compliance Tracker - NDIS Compliance Automation
====================================================

Automated compliance tracking system for SDA (Specialist Disability Accommodation)
providers. Manages registrations, certifications, worker screening, and audits.

FEATURES:
- SDA Design Category tracking (Basic, Improved Liveability, Fully Accessible, Robust, High Physical Support)
- Building certification status
- Worker screening expiry alerts
- Safety check schedules (smoke alarms, fire safety)
- NDIS registration renewal reminders
- Audit preparation reports
- Compliance scoring and risk assessment

Author: Agentic Brain Framework
License: MIT
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple, Callable
from enum import Enum
from pathlib import Path
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class SDADesignCategory(Enum):
    """NDIS SDA Design Categories."""

    BASIC = "basic"
    IMPROVED_LIVEABILITY = "improved_liveability"
    FULLY_ACCESSIBLE = "fully_accessible"
    ROBUST = "robust"
    HIGH_PHYSICAL_SUPPORT = "high_physical_support"


class ComplianceStatus(Enum):
    """Compliance item status."""

    COMPLIANT = "compliant"
    DUE_SOON = "due_soon"  # Within 30 days
    OVERDUE = "overdue"
    NOT_APPLICABLE = "not_applicable"
    PENDING_REVIEW = "pending_review"
    NON_COMPLIANT = "non_compliant"


class RiskLevel(Enum):
    """Risk level for compliance items."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceCategory(Enum):
    """Categories of compliance requirements."""

    SDA_REGISTRATION = "sda_registration"
    BUILDING_CERTIFICATION = "building_certification"
    FIRE_SAFETY = "fire_safety"
    WORKER_SCREENING = "worker_screening"
    NDIS_REGISTRATION = "ndis_registration"
    INSURANCE = "insurance"
    MAINTENANCE = "maintenance"
    ACCESSIBILITY = "accessibility"
    HEALTH_SAFETY = "health_safety"
    DOCUMENTATION = "documentation"


class WorkerScreeningType(Enum):
    """Types of worker screening checks."""

    NDIS_WORKER_SCREENING = "ndis_worker_screening"
    POLICE_CHECK = "police_check"
    WORKING_WITH_CHILDREN = "working_with_children"
    FIRST_AID = "first_aid"
    MANUAL_HANDLING = "manual_handling"
    FIRE_WARDEN = "fire_warden"


class AuditType(Enum):
    """Types of compliance audits."""

    NDIS_CERTIFICATION = "ndis_certification"
    NDIS_VERIFICATION = "ndis_verification"
    BUILDING_COMPLIANCE = "building_compliance"
    FIRE_SAFETY = "fire_safety"
    INTERNAL_REVIEW = "internal_review"
    QUALITY_ASSURANCE = "quality_assurance"


# SDA Design Category requirements
SDA_REQUIREMENTS = {
    SDADesignCategory.BASIC: {
        "name": "Basic",
        "description": "Minimum accessibility standards",
        "key_features": [
            "Physical access provisions",
            "Fire safety provisions",
            "Minimum door widths",
        ],
        "price_tier": 1,
    },
    SDADesignCategory.IMPROVED_LIVEABILITY: {
        "name": "Improved Liveability",
        "description": "Enhanced physical access and design features",
        "key_features": [
            "Improved lighting",
            "Improved navigation",
            "Luminance contrast",
            "Structural provisions for ceiling hoists",
        ],
        "price_tier": 2,
    },
    SDADesignCategory.FULLY_ACCESSIBLE: {
        "name": "Fully Accessible",
        "description": "Full wheelchair accessibility",
        "key_features": [
            "Full wheelchair accessibility",
            "Enhanced bathroom facilities",
            "Accessible kitchen design",
            "Wider doorways and corridors",
        ],
        "price_tier": 3,
    },
    SDADesignCategory.ROBUST: {
        "name": "Robust",
        "description": "High durability construction for complex behaviors",
        "key_features": [
            "Impact-resistant walls",
            "Reinforced fixtures",
            "Secure windows and doors",
            "Sound attenuation",
        ],
        "price_tier": 3,
    },
    SDADesignCategory.HIGH_PHYSICAL_SUPPORT: {
        "name": "High Physical Support",
        "description": "Maximum accessibility and assistive technology",
        "key_features": [
            "Ceiling hoists throughout",
            "Assistive technology provisions",
            "Emergency power backup",
            "Communication systems",
            "Full smart home capability",
        ],
        "price_tier": 4,
    },
}


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class ComplianceItem:
    """Individual compliance requirement."""

    item_id: str
    property_id: Optional[str]  # None for org-wide compliance
    category: ComplianceCategory
    name: str
    description: str
    due_date: Optional[date] = None
    last_completed: Optional[date] = None
    next_due: Optional[date] = None
    status: ComplianceStatus = ComplianceStatus.PENDING_REVIEW
    risk_level: RiskLevel = RiskLevel.MEDIUM
    responsible_person: Optional[str] = None
    evidence_required: List[str] = field(default_factory=list)
    evidence_uploaded: List[Dict] = field(default_factory=list)
    notes: str = ""
    auto_reminder_days: int = 30  # Days before due to remind

    @property
    def days_until_due(self) -> Optional[int]:
        if not self.next_due:
            return None
        return (self.next_due - date.today()).days

    @property
    def is_overdue(self) -> bool:
        if not self.next_due:
            return False
        return self.next_due < date.today()


@dataclass
class PropertyCompliance:
    """SDA property compliance record."""

    property_id: str
    address: str
    suburb: str
    state: str
    postcode: str
    sda_category: SDADesignCategory
    sda_registration_number: str
    sda_registration_expiry: date
    building_certification_number: str
    building_certification_expiry: date
    occupancy_permit_number: str
    last_fire_inspection: Optional[date] = None
    next_fire_inspection: Optional[date] = None
    last_building_inspection: Optional[date] = None
    smoke_alarm_check_due: Optional[date] = None
    rcd_test_due: Optional[date] = None  # Residual Current Device
    compliance_score: int = 100  # 0-100
    is_active: bool = True


@dataclass
class WorkerCompliance:
    """Worker/staff compliance record."""

    worker_id: str
    name: str
    role: str
    email: str
    phone: str
    start_date: date
    screenings: List[Dict] = field(default_factory=list)
    qualifications: List[Dict] = field(default_factory=list)
    is_active: bool = True

    def get_screening(self, screening_type: WorkerScreeningType) -> Optional[Dict]:
        for s in self.screenings:
            if s.get("type") == screening_type.value:
                return s
        return None

    @property
    def has_valid_ndis_screening(self) -> bool:
        screening = self.get_screening(WorkerScreeningType.NDIS_WORKER_SCREENING)
        if not screening:
            return False
        expiry = screening.get("expiry")
        if not expiry:
            return False
        return date.fromisoformat(expiry) > date.today()


@dataclass
class ComplianceAudit:
    """Compliance audit record."""

    audit_id: str
    audit_type: AuditType
    property_id: Optional[str]  # None for org-wide audits
    scheduled_date: date
    auditor_name: str
    auditor_organization: str
    status: str = "scheduled"  # scheduled, in_progress, completed, failed
    findings: List[Dict] = field(default_factory=list)
    corrective_actions: List[Dict] = field(default_factory=list)
    completed_date: Optional[date] = None
    next_audit_due: Optional[date] = None
    score: Optional[int] = None  # Audit score if applicable
    certificate_number: Optional[str] = None


@dataclass
class ComplianceAlert:
    """Compliance alert/notification."""

    alert_id: str
    item_id: str
    property_id: Optional[str]
    category: ComplianceCategory
    risk_level: RiskLevel
    title: str
    message: str
    due_date: Optional[date]
    created_at: datetime = field(default_factory=datetime.now)
    is_acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    is_resolved: bool = False
    resolution_notes: str = ""


# ============================================================================
# COMPLIANCE ENGINE
# ============================================================================


class ComplianceEngine:
    """
    Core compliance calculation and monitoring engine.

    Features:
    - Compliance score calculation
    - Risk assessment
    - Due date tracking
    - Alert generation
    """

    def __init__(self):
        self.compliance_weights = {
            ComplianceCategory.SDA_REGISTRATION: 20,
            ComplianceCategory.BUILDING_CERTIFICATION: 15,
            ComplianceCategory.FIRE_SAFETY: 20,
            ComplianceCategory.WORKER_SCREENING: 15,
            ComplianceCategory.NDIS_REGISTRATION: 10,
            ComplianceCategory.INSURANCE: 10,
            ComplianceCategory.MAINTENANCE: 5,
            ComplianceCategory.ACCESSIBILITY: 3,
            ComplianceCategory.HEALTH_SAFETY: 2,
        }

    def calculate_property_score(
        self,
        property_compliance: PropertyCompliance,
        compliance_items: List[ComplianceItem],
    ) -> int:
        """Calculate compliance score for a property (0-100)."""
        total_weight = 0
        achieved_weight = 0

        # Filter items for this property
        property_items = [
            item
            for item in compliance_items
            if item.property_id == property_compliance.property_id
        ]

        for item in property_items:
            weight = self.compliance_weights.get(item.category, 5)
            total_weight += weight

            if item.status == ComplianceStatus.COMPLIANT:
                achieved_weight += weight
            elif item.status == ComplianceStatus.DUE_SOON:
                achieved_weight += weight * 0.8  # 80% credit
            elif item.status == ComplianceStatus.PENDING_REVIEW:
                achieved_weight += weight * 0.5  # 50% credit

        if total_weight == 0:
            return 100

        return int((achieved_weight / total_weight) * 100)

    def assess_risk_level(self, item: ComplianceItem) -> RiskLevel:
        """Assess risk level for a compliance item."""
        # Critical categories
        if item.category in [
            ComplianceCategory.FIRE_SAFETY,
            ComplianceCategory.SDA_REGISTRATION,
            ComplianceCategory.NDIS_REGISTRATION,
        ]:
            if item.is_overdue:
                return RiskLevel.CRITICAL
            if item.days_until_due and item.days_until_due <= 7:
                return RiskLevel.HIGH

        # Overdue items
        if item.is_overdue:
            days_overdue = abs(item.days_until_due or 0)
            if days_overdue > 30:
                return RiskLevel.CRITICAL
            elif days_overdue > 14:
                return RiskLevel.HIGH
            else:
                return RiskLevel.MEDIUM

        # Due soon
        if item.days_until_due and item.days_until_due <= 14:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def update_item_status(self, item: ComplianceItem) -> ComplianceStatus:
        """Update status based on dates."""
        if not item.next_due:
            return ComplianceStatus.NOT_APPLICABLE

        days = item.days_until_due

        if days is None:
            return ComplianceStatus.PENDING_REVIEW

        if days < 0:
            return ComplianceStatus.OVERDUE
        elif days <= 30:
            return ComplianceStatus.DUE_SOON
        else:
            return ComplianceStatus.COMPLIANT

    def generate_alerts(self, items: List[ComplianceItem]) -> List[ComplianceAlert]:
        """Generate alerts for items needing attention."""
        alerts = []

        for item in items:
            # Update status and risk
            item.status = self.update_item_status(item)
            item.risk_level = self.assess_risk_level(item)

            # Generate alert if needed
            if item.status in [ComplianceStatus.OVERDUE, ComplianceStatus.DUE_SOON]:
                if item.is_overdue:
                    title = f"OVERDUE: {item.name}"
                    message = f"{item.name} was due on {item.next_due}. Immediate action required."
                else:
                    title = f"Due Soon: {item.name}"
                    message = f"{item.name} is due on {item.next_due} ({item.days_until_due} days)."

                alert = ComplianceAlert(
                    alert_id=f"ALERT-{item.item_id}-{date.today().isoformat()}",
                    item_id=item.item_id,
                    property_id=item.property_id,
                    category=item.category,
                    risk_level=item.risk_level,
                    title=title,
                    message=message,
                    due_date=item.next_due,
                )
                alerts.append(alert)

        return alerts


# ============================================================================
# SDA COMPLIANCE TRACKER
# ============================================================================


class SDAComplianceTracker:
    """
    Main SDA compliance tracking system.

    Manages:
    - Property compliance records
    - Worker screening
    - Audit scheduling
    - Alert management
    - Compliance reporting
    """

    def __init__(self, organization_name: str = "SDA Housing Provider Pty Ltd"):
        self.organization_name = organization_name
        self.engine = ComplianceEngine()

        # Data stores
        self.properties: Dict[str, PropertyCompliance] = {}
        self.workers: Dict[str, WorkerCompliance] = {}
        self.compliance_items: Dict[str, ComplianceItem] = {}
        self.audits: Dict[str, ComplianceAudit] = {}
        self.alerts: Dict[str, ComplianceAlert] = {}

        # NDIS registration
        self.ndis_registration_number = ""
        self.ndis_registration_expiry = None

    def add_property(self, property_compliance: PropertyCompliance):
        """Add a property to compliance tracking."""
        self.properties[property_compliance.property_id] = property_compliance

        # Auto-create standard compliance items
        self._create_standard_property_items(property_compliance)

        logger.info(f"Added property: {property_compliance.property_id}")

    def _create_standard_property_items(self, prop: PropertyCompliance):
        """Create standard compliance items for a property."""
        items = [
            # SDA Registration
            ComplianceItem(
                item_id=f"{prop.property_id}-SDA-REG",
                property_id=prop.property_id,
                category=ComplianceCategory.SDA_REGISTRATION,
                name="SDA Registration",
                description="NDIS SDA Dwelling Enrollment",
                due_date=prop.sda_registration_expiry,
                next_due=prop.sda_registration_expiry,
                evidence_required=["SDA registration certificate", "Floor plan"],
                risk_level=RiskLevel.CRITICAL,
                auto_reminder_days=90,
            ),
            # Building Certification
            ComplianceItem(
                item_id=f"{prop.property_id}-BUILD-CERT",
                property_id=prop.property_id,
                category=ComplianceCategory.BUILDING_CERTIFICATION,
                name="Building Certification",
                description="Building compliance certificate",
                due_date=prop.building_certification_expiry,
                next_due=prop.building_certification_expiry,
                evidence_required=["Building certificate", "Occupancy permit"],
                risk_level=RiskLevel.HIGH,
                auto_reminder_days=60,
            ),
            # Fire Safety - Annual
            ComplianceItem(
                item_id=f"{prop.property_id}-FIRE-ANNUAL",
                property_id=prop.property_id,
                category=ComplianceCategory.FIRE_SAFETY,
                name="Annual Fire Safety Statement",
                description="Annual fire safety certification",
                due_date=prop.next_fire_inspection,
                next_due=prop.next_fire_inspection,
                evidence_required=["Fire safety statement", "Inspection report"],
                risk_level=RiskLevel.CRITICAL,
                auto_reminder_days=60,
            ),
            # Smoke Alarms - Monthly
            ComplianceItem(
                item_id=f"{prop.property_id}-SMOKE-CHECK",
                property_id=prop.property_id,
                category=ComplianceCategory.FIRE_SAFETY,
                name="Smoke Alarm Check",
                description="Monthly smoke alarm testing",
                due_date=prop.smoke_alarm_check_due,
                next_due=prop.smoke_alarm_check_due,
                evidence_required=["Smoke alarm test log"],
                risk_level=RiskLevel.HIGH,
                auto_reminder_days=7,
            ),
            # RCD Testing - 6 Monthly
            ComplianceItem(
                item_id=f"{prop.property_id}-RCD-TEST",
                property_id=prop.property_id,
                category=ComplianceCategory.HEALTH_SAFETY,
                name="RCD Safety Switch Test",
                description="6-monthly RCD/safety switch testing",
                due_date=prop.rcd_test_due,
                next_due=prop.rcd_test_due,
                evidence_required=["RCD test certificate"],
                risk_level=RiskLevel.MEDIUM,
                auto_reminder_days=30,
            ),
        ]

        for item in items:
            self.compliance_items[item.item_id] = item

    def add_worker(self, worker: WorkerCompliance):
        """Add a worker to compliance tracking."""
        self.workers[worker.worker_id] = worker

        # Auto-create screening compliance items
        self._create_worker_screening_items(worker)

        logger.info(f"Added worker: {worker.worker_id}")

    def _create_worker_screening_items(self, worker: WorkerCompliance):
        """Create compliance items for worker screenings."""
        for screening in worker.screenings:
            expiry = screening.get("expiry")
            if expiry:
                expiry_date = date.fromisoformat(expiry)

                item = ComplianceItem(
                    item_id=f"{worker.worker_id}-{screening['type']}",
                    property_id=None,  # Org-wide
                    category=ComplianceCategory.WORKER_SCREENING,
                    name=f"{worker.name} - {screening['type'].replace('_', ' ').title()}",
                    description=f"Worker screening check for {worker.name}",
                    due_date=expiry_date,
                    next_due=expiry_date,
                    evidence_required=["Screening certificate", "Photo ID"],
                    risk_level=(
                        RiskLevel.HIGH
                        if screening["type"] == "ndis_worker_screening"
                        else RiskLevel.MEDIUM
                    ),
                    auto_reminder_days=60,
                )
                self.compliance_items[item.item_id] = item

    def schedule_audit(self, audit: ComplianceAudit):
        """Schedule a compliance audit."""
        self.audits[audit.audit_id] = audit

        # Create compliance item for audit preparation
        prep_item = ComplianceItem(
            item_id=f"PREP-{audit.audit_id}",
            property_id=audit.property_id,
            category=ComplianceCategory.DOCUMENTATION,
            name=f"Audit Preparation - {audit.audit_type.value.replace('_', ' ').title()}",
            description=f"Prepare documentation for {audit.auditor_organization} audit",
            due_date=audit.scheduled_date - timedelta(days=7),
            next_due=audit.scheduled_date - timedelta(days=7),
            evidence_required=self._get_audit_requirements(audit.audit_type),
            risk_level=RiskLevel.HIGH,
            auto_reminder_days=14,
        )
        self.compliance_items[prep_item.item_id] = prep_item

        logger.info(f"Scheduled audit: {audit.audit_id}")

    def _get_audit_requirements(self, audit_type: AuditType) -> List[str]:
        """Get documentation requirements for audit type."""
        requirements = {
            AuditType.NDIS_CERTIFICATION: [
                "NDIS registration certificate",
                "Quality management policies",
                "Staff screening records",
                "Incident register",
                "Complaints register",
                "Training records",
                "Risk assessments",
            ],
            AuditType.NDIS_VERIFICATION: [
                "Service agreements",
                "Progress notes",
                "Staff qualifications",
                "Policies and procedures",
            ],
            AuditType.BUILDING_COMPLIANCE: [
                "Building certification",
                "Occupancy permit",
                "As-built drawings",
                "Structural engineer certificate",
            ],
            AuditType.FIRE_SAFETY: [
                "Fire safety statement",
                "Smoke alarm test records",
                "Emergency evacuation plan",
                "Fire extinguisher service records",
                "Exit light test records",
            ],
            AuditType.INTERNAL_REVIEW: [
                "Compliance checklist",
                "Action item register",
                "Previous audit findings",
            ],
            AuditType.QUALITY_ASSURANCE: [
                "Quality policy",
                "Customer feedback",
                "Continuous improvement register",
            ],
        }
        return requirements.get(audit_type, ["General documentation"])

    def record_compliance_check(
        self, item_id: str, completed_by: str, evidence: List[Dict], notes: str = ""
    ) -> bool:
        """Record completion of a compliance check."""
        item = self.compliance_items.get(item_id)
        if not item:
            return False

        item.last_completed = date.today()
        item.evidence_uploaded.extend(evidence)
        item.notes = notes

        # Calculate next due date based on category
        if item.category == ComplianceCategory.FIRE_SAFETY:
            if "smoke" in item.name.lower():
                item.next_due = date.today() + timedelta(days=30)  # Monthly
            else:
                item.next_due = date.today() + timedelta(days=365)  # Annual
        elif item.category == ComplianceCategory.HEALTH_SAFETY:
            item.next_due = date.today() + timedelta(days=180)  # 6 monthly
        else:
            item.next_due = date.today() + timedelta(days=365)  # Default annual

        # Update status
        item.status = self.engine.update_item_status(item)
        item.risk_level = self.engine.assess_risk_level(item)

        logger.info(f"Recorded compliance check: {item_id} by {completed_by}")
        return True

    def get_property_compliance_summary(self, property_id: str) -> Dict[str, Any]:
        """Get compliance summary for a property."""
        prop = self.properties.get(property_id)
        if not prop:
            return {"error": "Property not found"}

        # Get items for this property
        items = [
            item
            for item in self.compliance_items.values()
            if item.property_id == property_id
        ]

        # Generate current alerts
        alerts = self.engine.generate_alerts(items)

        # Calculate score
        score = self.engine.calculate_property_score(prop, items)
        prop.compliance_score = score

        # Count by status
        status_counts = {}
        for item in items:
            status = item.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "property_id": property_id,
            "address": f"{prop.address}, {prop.suburb} {prop.state} {prop.postcode}",
            "sda_category": SDA_REQUIREMENTS[prop.sda_category]["name"],
            "sda_registration": prop.sda_registration_number,
            "compliance_score": score,
            "score_rating": self._get_score_rating(score),
            "total_items": len(items),
            "status_breakdown": status_counts,
            "active_alerts": len([a for a in alerts if not a.is_resolved]),
            "critical_items": len(
                [i for i in items if i.risk_level == RiskLevel.CRITICAL]
            ),
            "next_due_item": min(
                [(i.name, i.next_due) for i in items if i.next_due],
                key=lambda x: x[1],
                default=("None", None),
            ),
        }

    def _get_score_rating(self, score: int) -> str:
        """Get rating description for compliance score."""
        if score >= 95:
            return "Excellent"
        elif score >= 85:
            return "Good"
        elif score >= 70:
            return "Satisfactory"
        elif score >= 50:
            return "Needs Attention"
        else:
            return "Critical"

    def get_worker_compliance_summary(self, worker_id: str) -> Dict[str, Any]:
        """Get compliance summary for a worker."""
        worker = self.workers.get(worker_id)
        if not worker:
            return {"error": "Worker not found"}

        screenings_status = []
        for screening in worker.screenings:
            expiry = screening.get("expiry")
            if expiry:
                expiry_date = date.fromisoformat(expiry)
                days_until = (expiry_date - date.today()).days

                if days_until < 0:
                    status = "expired"
                elif days_until <= 30:
                    status = "expiring_soon"
                else:
                    status = "valid"

                screenings_status.append(
                    {
                        "type": screening["type"].replace("_", " ").title(),
                        "expiry": expiry,
                        "days_until": days_until,
                        "status": status,
                    }
                )

        return {
            "worker_id": worker_id,
            "name": worker.name,
            "role": worker.role,
            "is_active": worker.is_active,
            "has_valid_ndis_screening": worker.has_valid_ndis_screening,
            "screenings": screenings_status,
            "qualifications_count": len(worker.qualifications),
        }

    def get_upcoming_audits(self, days_ahead: int = 90) -> List[Dict]:
        """Get upcoming audits."""
        cutoff = date.today() + timedelta(days=days_ahead)

        upcoming = []
        for audit in self.audits.values():
            if audit.status == "scheduled" and audit.scheduled_date <= cutoff:
                prop = (
                    self.properties.get(audit.property_id)
                    if audit.property_id
                    else None
                )
                upcoming.append(
                    {
                        "audit_id": audit.audit_id,
                        "type": audit.audit_type.value.replace("_", " ").title(),
                        "property": prop.address if prop else "Organization-wide",
                        "date": audit.scheduled_date.isoformat(),
                        "days_until": (audit.scheduled_date - date.today()).days,
                        "auditor": audit.auditor_organization,
                    }
                )

        return sorted(upcoming, key=lambda x: x["days_until"])

    def get_all_active_alerts(self) -> List[Dict]:
        """Get all active compliance alerts."""
        # Generate fresh alerts
        all_alerts = self.engine.generate_alerts(list(self.compliance_items.values()))

        # Sort by risk level
        risk_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
        }

        all_alerts.sort(
            key=lambda a: (risk_order[a.risk_level], a.due_date or date.max)
        )

        return [
            {
                "alert_id": a.alert_id,
                "title": a.title,
                "message": a.message,
                "risk_level": a.risk_level.value,
                "category": a.category.value,
                "property_id": a.property_id,
                "due_date": a.due_date.isoformat() if a.due_date else None,
            }
            for a in all_alerts
        ]

    def generate_audit_preparation_report(self, audit_id: str) -> str:
        """Generate audit preparation checklist report."""
        audit = self.audits.get(audit_id)
        if not audit:
            return "Audit not found"

        prop = self.properties.get(audit.property_id) if audit.property_id else None
        requirements = self._get_audit_requirements(audit.audit_type)

        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      AUDIT PREPARATION CHECKLIST                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

{self.organization_name}

--------------------------------------------------------------------------------
AUDIT DETAILS
--------------------------------------------------------------------------------
Audit ID:       {audit.audit_id}
Audit Type:     {audit.audit_type.value.replace('_', ' ').title()}
Property:       {prop.address + ', ' + prop.suburb if prop else 'Organization-wide'}
Scheduled Date: {audit.scheduled_date.strftime('%A, %d %B %Y')}
Days Until:     {(audit.scheduled_date - date.today()).days} days
Auditor:        {audit.auditor_name}
Organization:   {audit.auditor_organization}

--------------------------------------------------------------------------------
DOCUMENTATION CHECKLIST
--------------------------------------------------------------------------------
"""
        for i, req in enumerate(requirements, 1):
            report += f"  [ ] {i}. {req}\n"

        report += """
--------------------------------------------------------------------------------
PRE-AUDIT ACTIONS
--------------------------------------------------------------------------------
  [ ] Review previous audit findings and corrective actions
  [ ] Ensure all staff are aware of audit date
  [ ] Prepare meeting room for auditors
  [ ] Have all evidence documents organized and accessible
  [ ] Conduct internal pre-audit review
  [ ] Brief relevant staff on audit process
  [ ] Ensure property is clean and presentable (if on-site)

--------------------------------------------------------------------------------
KEY CONTACTS
--------------------------------------------------------------------------------
"""
        # Add property-specific info if applicable
        if prop:
            report += f"""
SDA Registration:     {prop.sda_registration_number}
SDA Category:         {SDA_REQUIREMENTS[prop.sda_category]['name']}
Building Cert:        {prop.building_certification_number}
Compliance Score:     {prop.compliance_score}%
"""

        report += f"""
--------------------------------------------------------------------------------
AUDIT PREPARATION NOTES
--------------------------------------------------------------------------------
• Ensure NDIS registration is current: {self.ndis_registration_number or 'Not recorded'}
• Review and update policies if needed
• Prepare examples of continuous improvement
• Have incident register ready for review
• Prepare staff availability for interviews

Report generated: {datetime.now().strftime('%d %B %Y at %H:%M')}

╚══════════════════════════════════════════════════════════════════════════════╝
"""
        return report

    def generate_compliance_dashboard(self) -> Dict[str, Any]:
        """Generate overall compliance dashboard."""
        # Property scores
        property_scores = []
        for prop_id, prop in self.properties.items():
            items = [
                i for i in self.compliance_items.values() if i.property_id == prop_id
            ]
            score = self.engine.calculate_property_score(prop, items)
            prop.compliance_score = score
            property_scores.append(
                {
                    "property_id": prop_id,
                    "address": prop.address,
                    "score": score,
                    "rating": self._get_score_rating(score),
                }
            )

        # Worker screening status
        workers_valid = len(
            [
                w
                for w in self.workers.values()
                if w.has_valid_ndis_screening and w.is_active
            ]
        )
        workers_total = len([w for w in self.workers.values() if w.is_active])

        # Upcoming audits
        upcoming = self.get_upcoming_audits(30)

        # Active alerts
        alerts = self.get_all_active_alerts()
        critical_alerts = len([a for a in alerts if a["risk_level"] == "critical"])

        # Calculate overall score
        if property_scores:
            overall_score = int(
                sum(p["score"] for p in property_scores) / len(property_scores)
            )
        else:
            overall_score = 100

        return {
            "organization": self.organization_name,
            "timestamp": datetime.now().isoformat(),
            "overall_compliance_score": overall_score,
            "overall_rating": self._get_score_rating(overall_score),
            "properties": {
                "total": len(self.properties),
                "scores": property_scores,
                "average_score": overall_score,
            },
            "workers": {
                "total_active": workers_total,
                "valid_screening": workers_valid,
                "screening_compliance": (
                    f"{(workers_valid/workers_total*100):.0f}%"
                    if workers_total > 0
                    else "N/A"
                ),
            },
            "audits": {
                "upcoming_30_days": len(upcoming),
                "next_audit": upcoming[0] if upcoming else None,
            },
            "alerts": {
                "total_active": len(alerts),
                "critical": critical_alerts,
                "high": len([a for a in alerts if a["risk_level"] == "high"]),
            },
            "compliance_items": {
                "total": len(self.compliance_items),
                "overdue": len(
                    [
                        i
                        for i in self.compliance_items.values()
                        if i.status == ComplianceStatus.OVERDUE
                    ]
                ),
                "due_soon": len(
                    [
                        i
                        for i in self.compliance_items.values()
                        if i.status == ComplianceStatus.DUE_SOON
                    ]
                ),
            },
        }


# ============================================================================
# DEMO DATA GENERATOR
# ============================================================================


def generate_demo_data() -> SDAComplianceTracker:
    """Generate demo data for testing."""
    tracker = SDAComplianceTracker("Accessible Homes Property Co")
    tracker.ndis_registration_number = "4-XXXX-XXXX"
    tracker.ndis_registration_expiry = date(2026, 12, 31)

    # Add properties
    properties = [
        PropertyCompliance(
            property_id="PROP-001",
            address="Unit 1, 42 Example Street",
            suburb="Sampletown",
            state="SA",
            postcode="5000",
            sda_category=SDADesignCategory.HIGH_PHYSICAL_SUPPORT,
            sda_registration_number="SDA-SA-12345",
            sda_registration_expiry=date(2026, 6, 30),
            building_certification_number="BC-2023-1234",
            building_certification_expiry=date(2025, 12, 31),
            occupancy_permit_number="OP-2023-5678",
            last_fire_inspection=date(2024, 10, 15),
            next_fire_inspection=date(2025, 10, 15),
            smoke_alarm_check_due=date.today() + timedelta(days=15),
            rcd_test_due=date.today() + timedelta(days=45),
        ),
        PropertyCompliance(
            property_id="PROP-002",
            address="3/88 Demo Road",
            suburb="Testville",
            state="SA",
            postcode="5001",
            sda_category=SDADesignCategory.FULLY_ACCESSIBLE,
            sda_registration_number="SDA-SA-12346",
            sda_registration_expiry=date(2025, 8, 15),  # Due soon
            building_certification_number="BC-2022-9876",
            building_certification_expiry=date(2025, 6, 30),
            occupancy_permit_number="OP-2022-4321",
            last_fire_inspection=date(2024, 6, 1),
            next_fire_inspection=date(2025, 6, 1),
            smoke_alarm_check_due=date.today() - timedelta(days=5),  # Overdue!
            rcd_test_due=date.today() + timedelta(days=120),
        ),
        PropertyCompliance(
            property_id="PROP-003",
            address="15 Showcase Avenue",
            suburb="Exampleville",
            state="VIC",
            postcode="3000",
            sda_category=SDADesignCategory.ROBUST,
            sda_registration_number="SDA-VIC-98765",
            sda_registration_expiry=date(2027, 3, 31),
            building_certification_number="BC-2024-5555",
            building_certification_expiry=date(2026, 9, 30),
            occupancy_permit_number="OP-2024-7777",
            last_fire_inspection=date(2025, 1, 20),
            next_fire_inspection=date(2026, 1, 20),
            smoke_alarm_check_due=date.today() + timedelta(days=25),
            rcd_test_due=date.today() + timedelta(days=90),
        ),
    ]

    for prop in properties:
        tracker.add_property(prop)

    # Add workers
    workers = [
        WorkerCompliance(
            worker_id="WRK-001",
            name="Sarah Johnson",
            role="Property Manager",
            email="sarah@example.com",
            phone="0400 111 222",
            start_date=date(2021, 3, 15),
            screenings=[
                {
                    "type": "ndis_worker_screening",
                    "number": "NDIS-001234",
                    "expiry": (date.today() + timedelta(days=400)).isoformat(),
                },
                {
                    "type": "police_check",
                    "number": "PC-567890",
                    "expiry": (date.today() + timedelta(days=200)).isoformat(),
                },
                {
                    "type": "first_aid",
                    "number": "FA-111",
                    "expiry": (date.today() + timedelta(days=100)).isoformat(),
                },
            ],
            qualifications=[
                {"name": "Certificate IV Property Services", "year": 2019},
                {"name": "NDIS Worker Orientation", "year": 2021},
            ],
        ),
        WorkerCompliance(
            worker_id="WRK-002",
            name="Michael Chen",
            role="Maintenance Coordinator",
            email="michael@example.com",
            phone="0400 333 444",
            start_date=date(2022, 7, 1),
            screenings=[
                {
                    "type": "ndis_worker_screening",
                    "number": "NDIS-005678",
                    "expiry": (date.today() + timedelta(days=25)).isoformat(),
                },  # Expiring soon!
                {
                    "type": "police_check",
                    "number": "PC-234567",
                    "expiry": (date.today() + timedelta(days=300)).isoformat(),
                },
            ],
            qualifications=[
                {"name": "Certificate III Carpentry", "year": 2015},
                {"name": "Working at Heights", "year": 2023},
            ],
        ),
        WorkerCompliance(
            worker_id="WRK-003",
            name="Emily Williams",
            role="Compliance Officer",
            email="emily@example.com",
            phone="0400 555 666",
            start_date=date(2023, 1, 10),
            screenings=[
                {
                    "type": "ndis_worker_screening",
                    "number": "NDIS-009999",
                    "expiry": (date.today() - timedelta(days=10)).isoformat(),
                },  # Expired!
                {
                    "type": "police_check",
                    "number": "PC-888888",
                    "expiry": (date.today() + timedelta(days=500)).isoformat(),
                },
            ],
            qualifications=[
                {"name": "Bachelor of Business", "year": 2020},
                {"name": "NDIS Quality Auditor", "year": 2022},
            ],
        ),
    ]

    for worker in workers:
        tracker.add_worker(worker)

    # Schedule audits
    audits = [
        ComplianceAudit(
            audit_id="AUD-2025-001",
            audit_type=AuditType.NDIS_CERTIFICATION,
            property_id=None,  # Org-wide
            scheduled_date=date.today() + timedelta(days=45),
            auditor_name="Jane Auditor",
            auditor_organization="NDIS Quality Safeguards Commission",
        ),
        ComplianceAudit(
            audit_id="AUD-2025-002",
            audit_type=AuditType.FIRE_SAFETY,
            property_id="PROP-002",
            scheduled_date=date.today() + timedelta(days=20),
            auditor_name="Fire Safety Inspector",
            auditor_organization="SA Metropolitan Fire Service",
        ),
    ]

    for audit in audits:
        tracker.schedule_audit(audit)

    return tracker


# ============================================================================
# DEMO RUNNER
# ============================================================================


def run_demo():
    """Run comprehensive compliance tracker demo."""
    print("=" * 80)
    print("     SDA COMPLIANCE TRACKER - NDIS COMPLIANCE AUTOMATION")
    print("     Compliance Monitoring & Audit Preparation")
    print("=" * 80)
    print()

    # Initialize with demo data
    print("📊 Initializing compliance tracker with demo data...")
    tracker = generate_demo_data()
    print(f"   ✓ Organization: {tracker.organization_name}")
    print(f"   ✓ NDIS Registration: {tracker.ndis_registration_number}")
    print(f"   ✓ Properties: {len(tracker.properties)}")
    print(f"   ✓ Workers: {len(tracker.workers)}")
    print(f"   ✓ Compliance Items: {len(tracker.compliance_items)}")
    print(f"   ✓ Scheduled Audits: {len(tracker.audits)}")
    print()

    # Show dashboard
    print("📊 COMPLIANCE DASHBOARD")
    print("-" * 80)
    dashboard = tracker.generate_compliance_dashboard()
    print(json.dumps(dashboard, indent=2, default=str))
    print()

    # Show active alerts
    print("🚨 ACTIVE COMPLIANCE ALERTS")
    print("-" * 80)
    alerts = tracker.get_all_active_alerts()
    for alert in alerts[:10]:  # Show top 10
        risk_icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }
        icon = risk_icons.get(alert["risk_level"], "⚪")
        print(f"   {icon} [{alert['risk_level'].upper()}] {alert['title']}")
        print(f"      {alert['message']}")
        if alert["due_date"]:
            print(f"      Due: {alert['due_date']}")
        print()

    # Show property compliance
    print("🏠 PROPERTY COMPLIANCE SUMMARIES")
    print("-" * 80)
    for prop_id in tracker.properties:
        summary = tracker.get_property_compliance_summary(prop_id)
        score = summary["compliance_score"]
        rating = summary["score_rating"]

        if score >= 85:
            icon = "✅"
        elif score >= 70:
            icon = "⚠️"
        else:
            icon = "❌"

        print(f"   {icon} {summary['address']}")
        print(f"      SDA Category: {summary['sda_category']}")
        print(f"      Compliance Score: {score}% ({rating})")
        print(f"      Status Breakdown: {summary['status_breakdown']}")
        print(f"      Critical Items: {summary['critical_items']}")
        print(f"      Next Due: {summary['next_due_item']}")
        print()

    # Show worker compliance
    print("👷 WORKER COMPLIANCE STATUS")
    print("-" * 80)
    for worker_id in tracker.workers:
        summary = tracker.get_worker_compliance_summary(worker_id)

        if summary["has_valid_ndis_screening"]:
            icon = "✅"
        else:
            icon = "❌"

        print(f"   {icon} {summary['name']} ({summary['role']})")
        for screening in summary["screenings"]:
            status_icon = (
                "✅"
                if screening["status"] == "valid"
                else ("⚠️" if screening["status"] == "expiring_soon" else "❌")
            )
            print(
                f"      {status_icon} {screening['type']}: Expires {screening['expiry']} ({screening['days_until']} days)"
            )
        print()

    # Show upcoming audits
    print("📋 UPCOMING AUDITS")
    print("-" * 80)
    audits = tracker.get_upcoming_audits()
    for audit in audits:
        print(f"   📅 {audit['type']}")
        print(f"      Property: {audit['property']}")
        print(f"      Date: {audit['date']} ({audit['days_until']} days)")
        print(f"      Auditor: {audit['auditor']}")
        print()

    # Generate audit preparation report
    if tracker.audits:
        print("📝 SAMPLE AUDIT PREPARATION REPORT")
        print("-" * 80)
        audit_id = list(tracker.audits.keys())[0]
        report = tracker.generate_audit_preparation_report(audit_id)
        print(report)

    # SDA Design Categories reference
    print("📖 SDA DESIGN CATEGORY REFERENCE")
    print("-" * 80)
    for category, info in SDA_REQUIREMENTS.items():
        print(f"\n   {info['name']} (Tier {info['price_tier']})")
        print(f"   {info['description']}")
        print("   Key Features:")
        for feature in info["key_features"]:
            print(f"      • {feature}")
    print()

    print("=" * 80)
    print("                    DEMO COMPLETE")
    print("=" * 80)
    print()
    print("The SDA Compliance Tracker provides:")
    print("  ✅ Automated compliance monitoring")
    print("  ✅ Risk-based alerting")
    print("  ✅ Worker screening tracking")
    print("  ✅ Audit preparation support")
    print("  ✅ NDIS registration management")
    print("  ✅ Fire safety compliance")
    print()

    return tracker


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SDA Compliance Tracker - NDIS Compliance Automation"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Run demo mode with sample data"
    )
    parser.add_argument(
        "--dashboard", action="store_true", help="Show compliance dashboard"
    )
    parser.add_argument("--alerts", action="store_true", help="Show active alerts")

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.dashboard:
        tracker = generate_demo_data()
        dashboard = tracker.generate_compliance_dashboard()
        print(json.dumps(dashboard, indent=2, default=str))
    elif args.alerts:
        tracker = generate_demo_data()
        alerts = tracker.get_all_active_alerts()
        print(json.dumps(alerts, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
