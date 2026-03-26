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
#
# Agentic Brain is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Agentic Brain. If not, see <https://www.gnu.org/licenses/>.
"""
Aged Care Quality Agent for Compliance Management.

An AI assistant for aged care providers:
- Aged Care Act 2024 compliance checking
- Incident reporting workflows (SIRS)
- Staff credential verification
- Resident rights documentation
- Quality indicator tracking

Key patterns demonstrated:
- Regulatory compliance automation
- Incident management workflows
- Staff credential management
- Quality metrics tracking
- Charter of Rights integration

Usage:
    python examples/industry/aged_care_compliance.py

Requirements:
    pip install agentic-brain

Notes:
    - Aligned with Aged Care Quality and Safety Commission standards
    - SIRS (Serious Incident Response Scheme) integration
    - National Quality Indicator Program support
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional
import uuid

from agentic_brain.auth import (
    JWTAuth,
    AuthConfig,
    require_role,
    require_authority,
    User,
)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("aged_care.compliance")


# =============================================================================
# AGED CARE STANDARDS
# =============================================================================


class AgedCareStandard(str, Enum):
    """Aged Care Quality Standards."""

    STANDARD_1 = "consumer_dignity_and_choice"
    STANDARD_2 = "ongoing_assessment_and_planning"
    STANDARD_3 = "personal_care_and_clinical_care"
    STANDARD_4 = "services_and_supports_for_daily_living"
    STANDARD_5 = "organisation_service_environment"
    STANDARD_6 = "feedback_and_complaints"
    STANDARD_7 = "human_resources"
    STANDARD_8 = "organisational_governance"


class QualityIndicator(str, Enum):
    """National Quality Indicator Program metrics."""

    PRESSURE_INJURIES = "pressure_injuries"
    PHYSICAL_RESTRAINT = "physical_restraint"
    UNPLANNED_WEIGHT_LOSS = "unplanned_weight_loss"
    FALLS_AND_FRACTURES = "falls_and_fractures"
    MEDICATION_MANAGEMENT = "medication_management"
    STAFFING_HOURS = "staffing_hours"
    CONSUMER_EXPERIENCE = "consumer_experience"
    QUALITY_OF_LIFE = "quality_of_life"


# =============================================================================
# SIRS - SERIOUS INCIDENT RESPONSE SCHEME
# =============================================================================


class SIRSIncidentType(str, Enum):
    """SIRS reportable incident types."""

    UNREASONABLE_FORCE = "unreasonable_use_of_force"
    UNLAWFUL_RESTRAINT = "unlawful_sexual_contact_or_inappropriate_sexual_conduct"
    PSYCHOLOGICAL_ABUSE = "psychological_or_emotional_abuse"
    STEALING = "stealing_or_financial_coercion"
    NEGLECT = "neglect"
    UNEXPLAINED_ABSENCE = "unexplained_absence_from_care"
    UNEXPECTED_DEATH = "unexpected_death"
    SERIOUS_INJURY = "serious_injury"


class SIRSPriority(str, Enum):
    """SIRS notification timeframes."""

    PRIORITY_1 = (
        "24_hours"  # Unreasonable force, unlawful sexual contact, unexpected death
    )
    PRIORITY_2 = "30_days"  # Other reportable incidents


@dataclass
class SIRSIncident:
    """Serious Incident Response Scheme incident record."""

    incident_id: str
    incident_type: SIRSIncidentType
    priority: SIRSPriority
    occurred_at: datetime
    reported_at: datetime
    resident_id: str
    description: str
    immediate_actions: list[str]
    staff_involved: list[str]
    witnesses: list[str]
    notification_due: datetime
    notification_sent: bool = False
    investigation_status: str = "pending"  # pending, in_progress, completed
    root_cause: str = ""
    preventive_actions: list[str] = field(default_factory=list)

    @property
    def is_overdue(self) -> bool:
        """Check if notification is overdue."""
        return (
            not self.notification_sent
            and datetime.now(timezone.utc) > self.notification_due
        )


class SIRSService:
    """
    SIRS incident management service.

    Handles reporting to Aged Care Quality and Safety Commission.
    """

    def __init__(self):
        self._incidents: list[SIRSIncident] = []

    def _determine_priority(self, incident_type: SIRSIncidentType) -> SIRSPriority:
        """Determine notification priority based on incident type."""
        priority_1_types = [
            SIRSIncidentType.UNREASONABLE_FORCE,
            SIRSIncidentType.UNLAWFUL_RESTRAINT,
            SIRSIncidentType.UNEXPECTED_DEATH,
        ]

        if incident_type in priority_1_types:
            return SIRSPriority.PRIORITY_1
        return SIRSPriority.PRIORITY_2

    def report_incident(
        self,
        incident_type: SIRSIncidentType,
        resident_id: str,
        description: str,
        immediate_actions: list[str],
        staff_involved: list[str],
        witnesses: Optional[list[str]] = None,
    ) -> SIRSIncident:
        """
        Report a SIRS incident.

        Calculates notification deadline based on priority.
        """
        now = datetime.now(timezone.utc)
        priority = self._determine_priority(incident_type)

        # Calculate notification deadline
        if priority == SIRSPriority.PRIORITY_1:
            notification_due = now + timedelta(hours=24)
        else:
            notification_due = now + timedelta(days=30)

        incident = SIRSIncident(
            incident_id=f"SIRS-{uuid.uuid4().hex[:8].upper()}",
            incident_type=incident_type,
            priority=priority,
            occurred_at=now,
            reported_at=now,
            resident_id=resident_id,
            description=description,
            immediate_actions=immediate_actions,
            staff_involved=staff_involved,
            witnesses=witnesses or [],
            notification_due=notification_due,
        )

        self._incidents.append(incident)

        logger.warning(
            f"SIRS INCIDENT: {incident.incident_id} - {incident_type.value} - "
            f"Priority: {priority.value} - Due: {notification_due.isoformat()}"
        )

        return incident

    def get_pending_notifications(self) -> list[SIRSIncident]:
        """Get incidents with pending notifications."""
        return [i for i in self._incidents if not i.notification_sent]

    def get_overdue_notifications(self) -> list[SIRSIncident]:
        """Get incidents with overdue notifications."""
        return [i for i in self._incidents if i.is_overdue]

    def mark_notified(self, incident_id: str) -> bool:
        """Mark incident as notified to Commission."""
        for incident in self._incidents:
            if incident.incident_id == incident_id:
                incident.notification_sent = True
                incident.investigation_status = "in_progress"
                logger.info(f"SIRS incident {incident_id} marked as notified")
                return True
        return False


# =============================================================================
# STAFF CREDENTIALS
# =============================================================================


class CredentialType(str, Enum):
    """Staff credential types."""

    REGISTRATION = "ahpra_registration"  # AHPRA for nurses
    POLICE_CHECK = "police_check"
    WORKING_WITH_VULNERABLE = "working_with_vulnerable_people"
    FIRST_AID = "first_aid"
    CPR = "cpr"
    MANUAL_HANDLING = "manual_handling"
    MEDICATION_COMPETENCY = "medication_competency"
    DEMENTIA_CARE = "dementia_care_training"
    INFECTION_CONTROL = "infection_control"
    FOOD_SAFETY = "food_safety"


@dataclass
class Credential:
    """Staff credential record."""

    credential_id: str
    staff_id: str
    credential_type: CredentialType
    issuer: str
    issue_date: datetime
    expiry_date: datetime
    verification_status: str = "verified"  # verified, pending, expired, revoked
    document_reference: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if credential is currently valid."""
        now = datetime.now(timezone.utc)
        return self.verification_status == "verified" and self.expiry_date > now

    @property
    def days_until_expiry(self) -> int:
        """Days until credential expires."""
        delta = self.expiry_date - datetime.now(timezone.utc)
        return delta.days


@dataclass
class StaffMember:
    """Aged care staff member."""

    staff_id: str
    name: str
    role: str  # "registered_nurse", "enrolled_nurse", "personal_care_worker", "allied_health"
    credentials: list[Credential] = field(default_factory=list)
    is_active: bool = True

    def has_valid_credential(self, credential_type: CredentialType) -> bool:
        """Check if staff has valid credential of type."""
        return any(
            c.credential_type == credential_type and c.is_valid
            for c in self.credentials
        )

    def get_expiring_credentials(self, within_days: int = 30) -> list[Credential]:
        """Get credentials expiring within specified days."""
        return [
            c
            for c in self.credentials
            if c.is_valid and 0 < c.days_until_expiry <= within_days
        ]


class StaffCredentialService:
    """Staff credential verification service."""

    def __init__(self):
        self._staff: dict[str, StaffMember] = {}
        self._init_sample_data()

    def _init_sample_data(self):
        """Initialise sample staff and credentials."""
        now = datetime.now(timezone.utc)

        # Registered Nurse
        rn = StaffMember(
            staff_id="STF-001",
            name="Sarah Johnson",
            role="registered_nurse",
        )
        rn.credentials = [
            Credential(
                credential_id="CRED-001",
                staff_id="STF-001",
                credential_type=CredentialType.REGISTRATION,
                issuer="AHPRA",
                issue_date=now - timedelta(days=365),
                expiry_date=now + timedelta(days=730),
                document_reference="NMW0001234567",
            ),
            Credential(
                credential_id="CRED-002",
                staff_id="STF-001",
                credential_type=CredentialType.POLICE_CHECK,
                issuer="Victoria Police",
                issue_date=now - timedelta(days=180),
                expiry_date=now + timedelta(days=545),
            ),
            Credential(
                credential_id="CRED-003",
                staff_id="STF-001",
                credential_type=CredentialType.CPR,
                issuer="St John Ambulance",
                issue_date=now - timedelta(days=300),
                expiry_date=now + timedelta(days=65),  # Expiring soon
            ),
        ]
        self._staff["STF-001"] = rn

        # Personal Care Worker
        pcw = StaffMember(
            staff_id="STF-002",
            name="Michael Chen",
            role="personal_care_worker",
        )
        pcw.credentials = [
            Credential(
                credential_id="CRED-004",
                staff_id="STF-002",
                credential_type=CredentialType.POLICE_CHECK,
                issuer="Victoria Police",
                issue_date=now - timedelta(days=90),
                expiry_date=now + timedelta(days=640),
            ),
            Credential(
                credential_id="CRED-005",
                staff_id="STF-002",
                credential_type=CredentialType.MANUAL_HANDLING,
                issuer="Aged Care Training",
                issue_date=now - timedelta(days=60),
                expiry_date=now + timedelta(days=305),
            ),
            Credential(
                credential_id="CRED-006",
                staff_id="STF-002",
                credential_type=CredentialType.DEMENTIA_CARE,
                issuer="Dementia Australia",
                issue_date=now - timedelta(days=30),
                expiry_date=now + timedelta(days=700),
            ),
        ]
        self._staff["STF-002"] = pcw

    def verify_staff_credentials(self, staff_id: str) -> dict[str, Any]:
        """Verify all credentials for a staff member."""
        staff = self._staff.get(staff_id)
        if not staff:
            return {"error": "Staff member not found"}

        valid = []
        expired = []
        expiring_soon = []

        for cred in staff.credentials:
            if cred.is_valid:
                if cred.days_until_expiry <= 30:
                    expiring_soon.append(
                        {
                            "type": cred.credential_type.value,
                            "days_remaining": cred.days_until_expiry,
                        }
                    )
                else:
                    valid.append(cred.credential_type.value)
            else:
                expired.append(cred.credential_type.value)

        return {
            "staff_id": staff_id,
            "name": staff.name,
            "role": staff.role,
            "valid_credentials": valid,
            "expired_credentials": expired,
            "expiring_soon": expiring_soon,
            "all_valid": len(expired) == 0,
        }

    def get_expiring_credentials_report(self, within_days: int = 30) -> list[dict]:
        """Get all credentials expiring within specified days."""
        report = []

        for staff in self._staff.values():
            expiring = staff.get_expiring_credentials(within_days)
            for cred in expiring:
                report.append(
                    {
                        "staff_id": staff.staff_id,
                        "staff_name": staff.name,
                        "credential": cred.credential_type.value,
                        "expiry_date": cred.expiry_date.isoformat(),
                        "days_remaining": cred.days_until_expiry,
                    }
                )

        # Sort by days remaining
        report.sort(key=lambda x: x["days_remaining"])
        return report


# =============================================================================
# RESIDENT RIGHTS (CHARTER OF AGED CARE RIGHTS)
# =============================================================================


class CharterRight(str, Enum):
    """Charter of Aged Care Rights."""

    SAFE_QUALITY_CARE = "safe_and_high_quality_care"
    DIGNITY_RESPECT = "dignity_and_respect"
    IDENTITY_CULTURE = "identity_culture_and_diversity"
    LIVE_WITHOUT_ABUSE = "live_without_abuse_and_neglect"
    INFORMED = "be_informed"
    ACCESS_CARE = "access_all_types_of_care"
    SPEAK_UP = "speak_up_and_be_heard"
    FAIR_PRICES = "fair_and_transparent_prices"
    CONTROL_FINANCES = "control_over_finances"
    PERSONAL_PRIVACY = "personal_privacy"
    EXERCISE_RIGHTS = "exercise_rights"
    COMPLAIN_FREE_FROM_REPRISAL = "complain_free_from_reprisal"
    INDEPENDENCE = "independence_including_decision_making"
    SUPPORTED_DECISIONS = "support_for_decision_making"


@dataclass
class ResidentRightsAssessment:
    """Assessment of how resident rights are being upheld."""

    assessment_id: str
    resident_id: str
    assessed_by: str
    assessed_at: datetime
    rights_status: dict[CharterRight, bool]
    notes: dict[CharterRight, str]
    action_required: list[str]

    @property
    def compliance_score(self) -> float:
        """Calculate rights compliance percentage."""
        if not self.rights_status:
            return 0.0
        met = sum(1 for v in self.rights_status.values() if v)
        return (met / len(self.rights_status)) * 100


# =============================================================================
# QUALITY INDICATOR SERVICE
# =============================================================================


@dataclass
class QualityIndicatorData:
    """Quality indicator measurement."""

    indicator: QualityIndicator
    reporting_period: str  # e.g., "2025-Q1"
    value: float
    benchmark: float  # National benchmark
    trend: str  # "improving", "stable", "declining"
    notes: str = ""

    @property
    def meets_benchmark(self) -> bool:
        """Check if indicator meets national benchmark."""
        # For most indicators, lower is better
        positive_indicators = [
            QualityIndicator.STAFFING_HOURS,
            QualityIndicator.CONSUMER_EXPERIENCE,
            QualityIndicator.QUALITY_OF_LIFE,
        ]

        if self.indicator in positive_indicators:
            return self.value >= self.benchmark
        return self.value <= self.benchmark


class QualityIndicatorService:
    """National Quality Indicator Program service."""

    def __init__(self):
        self._indicators: dict[QualityIndicator, list[QualityIndicatorData]] = {}
        self._init_sample_data()

    def _init_sample_data(self):
        """Initialise sample quality indicator data."""
        current_period = "2025-Q1"

        sample_data = [
            QualityIndicatorData(
                indicator=QualityIndicator.PRESSURE_INJURIES,
                reporting_period=current_period,
                value=2.1,
                benchmark=3.5,  # % of residents
                trend="improving",
            ),
            QualityIndicatorData(
                indicator=QualityIndicator.FALLS_AND_FRACTURES,
                reporting_period=current_period,
                value=8.5,
                benchmark=10.0,  # per 1000 bed days
                trend="stable",
            ),
            QualityIndicatorData(
                indicator=QualityIndicator.UNPLANNED_WEIGHT_LOSS,
                reporting_period=current_period,
                value=5.2,
                benchmark=5.0,  # % of residents
                trend="declining",
                notes="Above benchmark - nutrition review initiated",
            ),
            QualityIndicatorData(
                indicator=QualityIndicator.PHYSICAL_RESTRAINT,
                reporting_period=current_period,
                value=0.8,
                benchmark=2.0,  # % of residents
                trend="improving",
            ),
            QualityIndicatorData(
                indicator=QualityIndicator.STAFFING_HOURS,
                reporting_period=current_period,
                value=215,
                benchmark=200,  # minutes per resident per day
                trend="stable",
            ),
            QualityIndicatorData(
                indicator=QualityIndicator.CONSUMER_EXPERIENCE,
                reporting_period=current_period,
                value=82,
                benchmark=75,  # satisfaction percentage
                trend="improving",
            ),
        ]

        for data in sample_data:
            if data.indicator not in self._indicators:
                self._indicators[data.indicator] = []
            self._indicators[data.indicator].append(data)

    def get_current_status(self) -> dict[str, Any]:
        """Get current quality indicator status."""
        results = []
        meeting_benchmark = 0

        for indicator, data_list in self._indicators.items():
            if data_list:
                latest = data_list[-1]
                results.append(
                    {
                        "indicator": indicator.value,
                        "value": latest.value,
                        "benchmark": latest.benchmark,
                        "meets_benchmark": latest.meets_benchmark,
                        "trend": latest.trend,
                    }
                )
                if latest.meets_benchmark:
                    meeting_benchmark += 1

        return {
            "reporting_period": "2025-Q1",
            "indicators": results,
            "summary": {
                "total_indicators": len(results),
                "meeting_benchmark": meeting_benchmark,
                "compliance_rate": f"{(meeting_benchmark/len(results)*100):.1f}%",
            },
        }

    def get_action_required(self) -> list[dict]:
        """Get indicators requiring action."""
        actions = []

        for indicator, data_list in self._indicators.items():
            if data_list:
                latest = data_list[-1]
                if not latest.meets_benchmark or latest.trend == "declining":
                    actions.append(
                        {
                            "indicator": indicator.value,
                            "issue": (
                                "Below benchmark"
                                if not latest.meets_benchmark
                                else "Declining trend"
                            ),
                            "current_value": latest.value,
                            "target": latest.benchmark,
                            "notes": latest.notes,
                        }
                    )

        return actions


# =============================================================================
# AGED CARE QUALITY AGENT
# =============================================================================


class AgedCareQualityAgent:
    """
    AI agent for aged care compliance management.

    Integrates SIRS, credentials, rights, and quality indicators.
    """

    def __init__(
        self,
        sirs: SIRSService,
        credentials: StaffCredentialService,
        quality: QualityIndicatorService,
    ):
        self._sirs = sirs
        self._credentials = credentials
        self._quality = quality

    def get_compliance_dashboard(self) -> dict[str, Any]:
        """Get overall compliance dashboard."""
        # SIRS status
        pending_sirs = self._sirs.get_pending_notifications()
        overdue_sirs = self._sirs.get_overdue_notifications()

        # Credential status
        expiring_creds = self._credentials.get_expiring_credentials_report(
            within_days=30
        )

        # Quality indicators
        qi_status = self._quality.get_current_status()
        qi_actions = self._quality.get_action_required()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sirs": {
                "pending_notifications": len(pending_sirs),
                "overdue_notifications": len(overdue_sirs),
                "status": "ALERT" if overdue_sirs else "OK",
            },
            "credentials": {
                "expiring_within_30_days": len(expiring_creds),
                "status": "WARNING" if expiring_creds else "OK",
            },
            "quality_indicators": {
                "meeting_benchmark": qi_status["summary"]["meeting_benchmark"],
                "total": qi_status["summary"]["total_indicators"],
                "actions_required": len(qi_actions),
                "status": "WARNING" if qi_actions else "OK",
            },
            "overall_status": self._calculate_overall_status(
                overdue_sirs, expiring_creds, qi_actions
            ),
        }

    def _calculate_overall_status(
        self,
        overdue_sirs: list,
        expiring_creds: list,
        qi_actions: list,
    ) -> str:
        """Calculate overall compliance status."""
        if overdue_sirs:
            return "CRITICAL"
        if expiring_creds or qi_actions:
            return "WARNING"
        return "COMPLIANT"

    def handle_query(self, query: str) -> dict[str, Any]:
        """Handle compliance query."""
        query_lower = query.lower()

        if "incident" in query_lower or "sirs" in query_lower:
            pending = self._sirs.get_pending_notifications()
            overdue = self._sirs.get_overdue_notifications()
            return {
                "response": f"SIRS Status: {len(pending)} pending, {len(overdue)} overdue.",
                "pending_incidents": [
                    {
                        "id": i.incident_id,
                        "type": i.incident_type.value,
                        "priority": i.priority.value,
                        "due": i.notification_due.isoformat(),
                    }
                    for i in pending
                ],
            }

        elif "credential" in query_lower or "staff" in query_lower:
            expiring = self._credentials.get_expiring_credentials_report(30)
            return {
                "response": f"{len(expiring)} credential(s) expiring within 30 days.",
                "expiring_credentials": expiring,
            }

        elif "quality" in query_lower or "indicator" in query_lower:
            status = self._quality.get_current_status()
            return {
                "response": f"Quality Indicators: {status['summary']['compliance_rate']} meeting benchmark.",
                "indicators": status["indicators"],
            }

        elif "dashboard" in query_lower or "status" in query_lower:
            return self.get_compliance_dashboard()

        else:
            return {
                "response": "I can help with SIRS incidents, staff credentials, and quality indicators.",
                "available_queries": [
                    "Show SIRS incidents",
                    "Check staff credentials",
                    "Quality indicator status",
                    "Compliance dashboard",
                ],
            }


# =============================================================================
# DEMONSTRATION
# =============================================================================


def demo():
    """Demonstrate the aged care quality agent."""

    print("=" * 70)
    print("AGED CARE QUALITY AGENT - Compliance Management Demo")
    print("=" * 70)
    print()

    # Initialise services
    sirs = SIRSService()
    credentials = StaffCredentialService()
    quality = QualityIndicatorService()

    # Create agent
    agent = AgedCareQualityAgent(sirs, credentials, quality)

    # Demo: Report a SIRS incident
    print("-" * 70)
    print("SIRS INCIDENT REPORTING")
    print("-" * 70)

    incident = sirs.report_incident(
        incident_type=SIRSIncidentType.NEGLECT,
        resident_id="RES-001",
        description="Resident missed scheduled medication administration",
        immediate_actions=[
            "Medication administered immediately upon discovery",
            "Resident assessed by RN",
            "Doctor notified",
        ],
        staff_involved=["STF-002"],
    )

    print(f"Incident ID: {incident.incident_id}")
    print(f"Type: {incident.incident_type.value}")
    print(f"Priority: {incident.priority.value}")
    print(f"Notification due: {incident.notification_due.isoformat()}")
    print()

    # Demo: Staff credential verification
    print("-" * 70)
    print("STAFF CREDENTIAL VERIFICATION")
    print("-" * 70)

    cred_status = credentials.verify_staff_credentials("STF-001")
    print(f"Staff: {cred_status['name']} ({cred_status['role']})")
    print(f"Valid credentials: {', '.join(cred_status['valid_credentials'])}")
    print(f"All valid: {cred_status['all_valid']}")
    if cred_status["expiring_soon"]:
        print("Expiring soon:")
        for exp in cred_status["expiring_soon"]:
            print(f"  - {exp['type']}: {exp['days_remaining']} days remaining")
    print()

    # Demo: Expiring credentials report
    print("-" * 70)
    print("EXPIRING CREDENTIALS REPORT (30 days)")
    print("-" * 70)

    expiring = credentials.get_expiring_credentials_report(30)
    for cred in expiring:
        print(
            f"  {cred['staff_name']}: {cred['credential']} - {cred['days_remaining']} days"
        )
    print()

    # Demo: Quality indicators
    print("-" * 70)
    print("QUALITY INDICATORS")
    print("-" * 70)

    qi_status = quality.get_current_status()
    print(f"Reporting period: {qi_status['reporting_period']}")
    print(f"Compliance rate: {qi_status['summary']['compliance_rate']}")
    print()
    print("Indicator status:")
    for ind in qi_status["indicators"]:
        status = "✓" if ind["meets_benchmark"] else "✗"
        print(
            f"  {status} {ind['indicator']}: {ind['value']} (benchmark: {ind['benchmark']}) [{ind['trend']}]"
        )
    print()

    # Demo: Actions required
    actions = quality.get_action_required()
    if actions:
        print("Actions required:")
        for action in actions:
            print(f"  - {action['indicator']}: {action['issue']}")
    print()

    # Demo: Compliance dashboard
    print("-" * 70)
    print("COMPLIANCE DASHBOARD")
    print("-" * 70)

    dashboard = agent.get_compliance_dashboard()
    print(f"Overall Status: {dashboard['overall_status']}")
    print(
        f"SIRS: {dashboard['sirs']['status']} - {dashboard['sirs']['pending_notifications']} pending"
    )
    print(
        f"Credentials: {dashboard['credentials']['status']} - {dashboard['credentials']['expiring_within_30_days']} expiring"
    )
    print(
        f"Quality: {dashboard['quality_indicators']['status']} - {dashboard['quality_indicators']['meeting_benchmark']}/{dashboard['quality_indicators']['total']} meeting benchmark"
    )

    print()
    print("=" * 70)
    print("Demo complete.")
    print("=" * 70)


if __name__ == "__main__":
    demo()
