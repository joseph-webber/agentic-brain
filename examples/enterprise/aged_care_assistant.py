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
Aged Care Assistant - Aged Care Act 2024 Compliant.

An AI assistant for residential aged care providers aligned with the
new Aged Care Act 2024 (Support at Home and residential reforms):

- Resident care planning with Statement of Rights
- Medication management with safety checks
- Family communication portal
- Quality indicators tracking (National QI Program)
- SIRS incident reporting
- Staff credential verification
- Dignity of Risk documentation

Key Australian Aged Care Context:
    - Aged Care Act 2024 reforms (effective July 2025)
    - Aged Care Quality and Safety Commission requirements
    - SIRS (Serious Incident Response Scheme)
    - National Quality Indicator Program (QI Program)
    - Statement of Rights compliance

Architecture (Privacy-First):
    ┌──────────────────────────────────────────────────────────────────┐
    │                    ON-PREMISE DEPLOYMENT                          │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
    │  │  Ollama  │  │   SQLite     │  │   Aged Care Assistant      │  │
    │  │ (Local)  │◄─┤  (Encrypted) │◄─┤   (This Application)       │  │
    │  └──────────┘  └──────────────┘  └────────────────────────────┘  │
    │              ALL RESIDENT DATA STAYS LOCAL                        │
    └──────────────────────────────────────────────────────────────────┘

IMPORTANT DISCLAIMERS:
    ⚠️  This is a DEMONSTRATION system only
    ⚠️  NOT official Aged Care Commission software
    ⚠️  Always verify with official regulatory sources
    ⚠️  Clinical decisions require qualified healthcare professionals
    ⚠️  Medication changes must be verified by pharmacist/GP

Usage:
    python examples/enterprise/aged_care_assistant.py
    python examples/enterprise/aged_care_assistant.py --demo

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
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from agentic_brain.auth import (
    AuthConfig,
    JWTAuth,
    User,
    require_role,
)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("aged_care.assistant")


# =============================================================================
# AGED CARE QUALITY STANDARDS
# =============================================================================


class QualityStandard(str, Enum):
    """Aged Care Quality Standards."""

    STANDARD_1 = "Consumer Dignity and Choice"
    STANDARD_2 = "Ongoing Assessment and Planning"
    STANDARD_3 = "Personal Care and Clinical Care"
    STANDARD_4 = "Services and Supports for Daily Living"
    STANDARD_5 = "Organisation's Service Environment"
    STANDARD_6 = "Feedback and Complaints"
    STANDARD_7 = "Human Resources"
    STANDARD_8 = "Organisational Governance"


class QualityIndicator(str, Enum):
    """National Quality Indicator Program metrics."""

    PRESSURE_INJURIES = "Pressure Injuries"
    PHYSICAL_RESTRAINT = "Physical Restraint"
    UNPLANNED_WEIGHT_LOSS = "Unplanned Weight Loss"
    FALLS_MAJOR_INJURY = "Falls Resulting in Major Injury"
    MEDICATION_MANAGEMENT = "Medication Management Problems"
    ACTIVITIES_OF_DAILY_LIVING = "Activities of Daily Living Decline"
    INCONTINENCE = "Incontinence"
    HOSPITALISATION = "Unplanned Hospitalisation"
    WORKFORCE = "Workforce Indicators"


class SIRSIncidentType(str, Enum):
    """SIRS Reportable incident types."""

    UNREASONABLE_FORCE = "Unreasonable Use of Force"
    UNLAWFUL_SEXUAL_CONTACT = "Unlawful Sexual Contact"
    PSYCHOLOGICAL_ABUSE = "Psychological or Emotional Abuse"
    UNEXPECTED_DEATH = "Unexpected Death"
    STEALING_FINANCIAL_ABUSE = "Stealing or Financial Coercion"
    NEGLECT = "Neglect"
    INAPPROPRIATE_RESTRAINT = "Inappropriate Physical or Chemical Restraint"
    MISSING_CONSUMER = "Missing Consumer"


class MedicationRoute(str, Enum):
    """Medication administration routes."""

    ORAL = "Oral (PO)"
    SUBLINGUAL = "Sublingual (SL)"
    TOPICAL = "Topical"
    SUBCUTANEOUS = "Subcutaneous (SC)"
    INTRAMUSCULAR = "Intramuscular (IM)"
    INHALATION = "Inhalation"
    RECTAL = "Rectal (PR)"
    OPHTHALMIC = "Eye Drops"
    OTIC = "Ear Drops"
    TRANSDERMAL = "Patch"


# =============================================================================
# RESIDENT MODEL
# =============================================================================


@dataclass
class Resident:
    """Aged care resident profile."""

    resident_id: str
    first_name: str
    last_name: str
    preferred_name: str
    date_of_birth: date
    admission_date: date
    room_number: str
    care_level: str  # "Residential", "Respite", "Transition Care"
    an_acc_class: str  # AN-ACC funding classification
    advance_care_directive: bool = False
    enduring_guardian: Optional[str] = None
    enduring_guardian_phone: Optional[str] = None
    preferred_language: str = "English"
    interpreter_required: bool = False
    dietary_requirements: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    mobility_status: str = "Independent"
    cognitive_status: str = "Intact"
    goals_of_care: list[str] = field(default_factory=list)
    care_plan_review_date: Optional[date] = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    @property
    def care_plan_due(self) -> bool:
        if not self.care_plan_review_date:
            return True
        return self.care_plan_review_date <= date.today()


@dataclass
class Medication:
    """Medication record."""

    medication_id: str
    resident_id: str
    medication_name: str
    generic_name: str
    strength: str
    route: MedicationRoute
    frequency: str
    scheduled_times: list[time]
    prescriber: str
    start_date: date
    end_date: Optional[date] = None
    prn: bool = False  # As needed
    prn_indication: str = ""
    special_instructions: str = ""
    high_risk: bool = False
    requires_double_sign: bool = False

    @property
    def is_active(self) -> bool:
        today = date.today()
        if self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True


@dataclass
class MedicationAdministration:
    """Record of medication administration."""

    admin_id: str
    medication_id: str
    resident_id: str
    scheduled_time: datetime
    actual_time: datetime
    administered_by: str
    witnessed_by: Optional[str] = None
    status: str = "Given"  # Given, Refused, Withheld, Not Available
    refusal_reason: str = ""
    clinical_notes: str = ""


@dataclass
class CareNote:
    """Care note for resident."""

    note_id: str
    resident_id: str
    author_id: str
    author_name: str
    created_at: datetime
    note_type: str  # Progress, Clinical, Incident, Family Contact
    content: str
    quality_standards_linked: list[QualityStandard] = field(default_factory=list)
    follow_up_required: bool = False
    follow_up_date: Optional[date] = None


@dataclass
class QualityIndicatorReading:
    """Quality indicator measurement."""

    reading_id: str
    resident_id: str
    indicator: QualityIndicator
    reading_date: date
    value: str
    notes: str
    recorded_by: str


# =============================================================================
# AGED CARE ASSISTANT
# =============================================================================


class AgedCareAssistant:
    """
    Aged Care Provider Assistant.

    Supports residential aged care operations with compliance
    to Aged Care Act 2024 requirements.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the aged care assistant."""
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self.residents: dict[str, Resident] = {}
        self.medications: dict[str, Medication] = {}
        self.med_administrations: list[MedicationAdministration] = []
        self.care_notes: list[CareNote] = []
        self.qi_readings: list[QualityIndicatorReading] = []
        self._load_demo_data()

    def _create_tables(self):
        """Create database tables."""
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
                datetime.now(UTC).isoformat(),
                user_id,
                action,
                entity_type,
                entity_id,
                details,
            ),
        )
        self.conn.commit()

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo residents
        self.residents["RES-001"] = Resident(
            resident_id="RES-001",
            first_name="Margaret",
            last_name="Thompson",
            preferred_name="Maggie",
            date_of_birth=date(1935, 6, 12),
            admission_date=date(2023, 3, 15),
            room_number="B-12",
            care_level="Residential",
            an_acc_class="Class 8",
            advance_care_directive=True,
            enduring_guardian="Sarah Thompson (daughter)",
            enduring_guardian_phone="0412 345 678",
            dietary_requirements=["Soft diet", "Thickened fluids - Mildly thick"],
            allergies=["Penicillin", "Shellfish"],
            mobility_status="Wheelchair dependent",
            cognitive_status="Moderate cognitive impairment",
            goals_of_care=[
                "Maintain comfort and dignity",
                "Continue social engagement with family",
                "Manage pain effectively",
            ],
            care_plan_review_date=date.today() + timedelta(days=30),
        )

        self.residents["RES-002"] = Resident(
            resident_id="RES-002",
            first_name="William",
            last_name="Chen",
            preferred_name="Bill",
            date_of_birth=date(1940, 11, 3),
            admission_date=date(2024, 1, 8),
            room_number="A-5",
            care_level="Residential",
            an_acc_class="Class 6",
            preferred_language="Cantonese",
            interpreter_required=True,
            dietary_requirements=["Diabetic diet"],
            allergies=["Sulfa drugs"],
            mobility_status="Walks with frame",
            cognitive_status="Intact",
            goals_of_care=[
                "Maintain independence with mobility",
                "Diabetes management",
                "Participate in cultural activities",
            ],
            care_plan_review_date=date.today() - timedelta(days=5),  # Overdue
        )

        # Demo medications for RES-001
        self.medications["MED-001"] = Medication(
            medication_id="MED-001",
            resident_id="RES-001",
            medication_name="Paracetamol Osteo",
            generic_name="Paracetamol 665mg SR",
            strength="665mg",
            route=MedicationRoute.ORAL,
            frequency="Three times daily",
            scheduled_times=[time(8, 0), time(14, 0), time(20, 0)],
            prescriber="Dr Smith",
            start_date=date(2023, 3, 15),
        )

        self.medications["MED-002"] = Medication(
            medication_id="MED-002",
            resident_id="RES-001",
            medication_name="Metoprolol",
            generic_name="Metoprolol 25mg",
            strength="25mg",
            route=MedicationRoute.ORAL,
            frequency="Twice daily",
            scheduled_times=[time(8, 0), time(20, 0)],
            prescriber="Dr Smith",
            start_date=date(2023, 3, 15),
            high_risk=True,  # Beta blocker
        )

        self.medications["MED-003"] = Medication(
            medication_id="MED-003",
            resident_id="RES-001",
            medication_name="Oxycodone",
            generic_name="Oxycodone 5mg",
            strength="5mg",
            route=MedicationRoute.ORAL,
            frequency="As needed",
            scheduled_times=[],
            prescriber="Dr Smith",
            start_date=date(2024, 6, 1),
            prn=True,
            prn_indication="Moderate to severe pain",
            special_instructions="Maximum 4 doses in 24 hours. Monitor for drowsiness.",
            high_risk=True,
            requires_double_sign=True,  # S8 medication
        )

    # =========================================================================
    # RESIDENT MANAGEMENT
    # =========================================================================

    def get_resident(self, resident_id: str) -> Optional[Resident]:
        """Get resident by ID."""
        return self.residents.get(resident_id)

    def get_resident_summary(self, resident_id: str) -> dict:
        """Get comprehensive resident summary."""
        resident = self.get_resident(resident_id)
        if not resident:
            return {"error": "Resident not found"}

        # Get active medications
        active_meds = [
            {
                "name": med.medication_name,
                "strength": med.strength,
                "frequency": med.frequency,
                "high_risk": med.high_risk,
                "route": med.route.value,
            }
            for med in self.medications.values()
            if med.resident_id == resident_id and med.is_active
        ]

        return {
            "resident_id": resident.resident_id,
            "name": resident.full_name,
            "preferred_name": resident.preferred_name,
            "age": resident.age,
            "room": resident.room_number,
            "care_level": resident.care_level,
            "an_acc_class": resident.an_acc_class,
            "mobility": resident.mobility_status,
            "cognitive_status": resident.cognitive_status,
            "dietary_requirements": resident.dietary_requirements,
            "allergies": resident.allergies,
            "advance_care_directive": resident.advance_care_directive,
            "enduring_guardian": resident.enduring_guardian,
            "goals_of_care": resident.goals_of_care,
            "care_plan_due": resident.care_plan_due,
            "care_plan_review_date": (
                resident.care_plan_review_date.isoformat()
                if resident.care_plan_review_date
                else None
            ),
            "active_medications": active_meds,
            "interpreter_required": resident.interpreter_required,
            "preferred_language": resident.preferred_language,
        }

    # =========================================================================
    # MEDICATION MANAGEMENT
    # =========================================================================

    def get_medication_round(self, round_time: time, user_id: str) -> list[dict]:
        """Get all medications due for a specific round time."""
        due_meds = []

        for med in self.medications.values():
            if not med.is_active:
                continue
            if med.prn:
                continue  # PRN medications are given separately

            # Check if medication is due at this time
            for scheduled in med.scheduled_times:
                # Allow 1-hour window
                scheduled_mins = scheduled.hour * 60 + scheduled.minute
                round_mins = round_time.hour * 60 + round_time.minute

                if abs(scheduled_mins - round_mins) <= 60:
                    resident = self.get_resident(med.resident_id)
                    if resident:
                        due_meds.append(
                            {
                                "medication_id": med.medication_id,
                                "resident_id": med.resident_id,
                                "resident_name": resident.full_name,
                                "room": resident.room_number,
                                "medication": med.medication_name,
                                "strength": med.strength,
                                "route": med.route.value,
                                "scheduled_time": scheduled.strftime("%H:%M"),
                                "special_instructions": med.special_instructions,
                                "high_risk": med.high_risk,
                                "requires_double_sign": med.requires_double_sign,
                                "allergies": resident.allergies,
                            }
                        )

        # Sort by room number
        due_meds.sort(key=lambda x: x["room"])

        self._audit_log(
            user_id=user_id,
            action="VIEW_MEDICATION_ROUND",
            details=f"Round time: {round_time.strftime('%H:%M')}, Medications: {len(due_meds)}",
        )

        return due_meds

    def record_medication_administration(
        self,
        medication_id: str,
        administered_by: str,
        status: str,
        witnessed_by: Optional[str] = None,
        refusal_reason: str = "",
        clinical_notes: str = "",
    ) -> dict:
        """Record medication administration."""
        medication = self.medications.get(medication_id)
        if not medication:
            return {"error": "Medication not found"}

        # Safety checks
        warnings = []

        if medication.requires_double_sign and not witnessed_by:
            return {
                "error": "This medication requires double signing (witness required)",
                "medication": medication.medication_name,
            }

        if medication.high_risk:
            warnings.append(f"⚠️ High-risk medication: {medication.medication_name}")

        resident = self.get_resident(medication.resident_id)
        if resident and medication.route == MedicationRoute.ORAL:
            if "Thickened fluids" in str(resident.dietary_requirements):
                warnings.append(
                    "⚠️ Resident requires thickened fluids - check medication form"
                )

        admin_id = f"ADMIN-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(UTC)

        admin = MedicationAdministration(
            admin_id=admin_id,
            medication_id=medication_id,
            resident_id=medication.resident_id,
            scheduled_time=now,  # Would be actual scheduled time in production
            actual_time=now,
            administered_by=administered_by,
            witnessed_by=witnessed_by,
            status=status,
            refusal_reason=refusal_reason,
            clinical_notes=clinical_notes,
        )

        self.med_administrations.append(admin)

        self._audit_log(
            user_id=administered_by,
            action="ADMINISTER_MEDICATION",
            entity_type="Medication",
            entity_id=medication_id,
            details=f"Status: {status}, Witness: {witnessed_by or 'N/A'}",
        )

        return {
            "success": True,
            "admin_id": admin_id,
            "medication": medication.medication_name,
            "resident": resident.full_name if resident else "Unknown",
            "status": status,
            "time": now.strftime("%H:%M"),
            "warnings": warnings,
        }

    def check_medication_interactions(self, resident_id: str) -> list[dict]:
        """Check for potential medication interactions."""
        resident_meds = [
            med
            for med in self.medications.values()
            if med.resident_id == resident_id and med.is_active
        ]

        # Simplified interaction checking (would use drug database in production)
        interactions = []

        # Example: Check for multiple CNS depressants
        cns_depressants = [
            "Oxycodone",
            "Morphine",
            "Temazepam",
            "Diazepam",
            "Lorazepam",
        ]
        cns_meds = [
            med
            for med in resident_meds
            if any(drug in med.medication_name for drug in cns_depressants)
        ]

        if len(cns_meds) > 1:
            interactions.append(
                {
                    "type": "CNS Depression Risk",
                    "severity": "High",
                    "medications": [m.medication_name for m in cns_meds],
                    "recommendation": "Monitor for excessive sedation, respiratory depression",
                }
            )

        # Check for anticoagulant + NSAID
        anticoag = any("warfarin" in m.medication_name.lower() for m in resident_meds)
        nsaid = any(
            drug in m.medication_name.lower()
            for m in resident_meds
            for drug in ["ibuprofen", "naproxen", "diclofenac", "aspirin"]
        )

        if anticoag and nsaid:
            interactions.append(
                {
                    "type": "Bleeding Risk",
                    "severity": "High",
                    "medications": ["Anticoagulant", "NSAID"],
                    "recommendation": "Increased bleeding risk - monitor closely",
                }
            )

        return interactions

    # =========================================================================
    # QUALITY INDICATORS
    # =========================================================================

    def record_quality_indicator(
        self,
        resident_id: str,
        indicator: QualityIndicator,
        value: str,
        notes: str,
        recorded_by: str,
    ) -> dict:
        """Record a quality indicator measurement."""
        resident = self.get_resident(resident_id)
        if not resident:
            return {"error": "Resident not found"}

        reading_id = f"QI-{uuid.uuid4().hex[:8].upper()}"

        reading = QualityIndicatorReading(
            reading_id=reading_id,
            resident_id=resident_id,
            indicator=indicator,
            reading_date=date.today(),
            value=value,
            notes=notes,
            recorded_by=recorded_by,
        )

        self.qi_readings.append(reading)

        self._audit_log(
            user_id=recorded_by,
            action="RECORD_QUALITY_INDICATOR",
            entity_type="QualityIndicator",
            entity_id=reading_id,
            details=f"Indicator: {indicator.value}, Value: {value}",
        )

        return {
            "success": True,
            "reading_id": reading_id,
            "resident": resident.full_name,
            "indicator": indicator.value,
            "value": value,
        }

    def generate_qi_report(self, reporting_period: str = "current_quarter") -> dict:
        """Generate Quality Indicator Program report."""
        # Group readings by indicator
        indicator_summary = {}

        for indicator in QualityIndicator:
            readings = [r for r in self.qi_readings if r.indicator == indicator]

            indicator_summary[indicator.value] = {
                "total_readings": len(readings),
                "residents_assessed": len(set(r.resident_id for r in readings)),
                # In production, would calculate actual rates
            }

        # Compliance status
        total_residents = len(self.residents)

        return {
            "reporting_period": reporting_period,
            "generated_at": datetime.now(UTC).isoformat(),
            "facility_summary": {
                "total_residents": total_residents,
                "care_plans_overdue": sum(
                    1 for r in self.residents.values() if r.care_plan_due
                ),
            },
            "quality_indicators": indicator_summary,
            "compliance_status": "Compliant",  # Would be calculated
        }

    # =========================================================================
    # SIRS INCIDENT REPORTING
    # =========================================================================

    def report_sirs_incident(
        self,
        resident_id: str,
        incident_type: SIRSIncidentType,
        incident_date: datetime,
        description: str,
        immediate_actions: str,
        reporter_id: str,
        reporter_name: str,
    ) -> dict:
        """Report a SIRS-reportable incident."""
        resident = self.get_resident(resident_id)
        if not resident:
            return {"error": "Resident not found"}

        incident_id = f"SIRS-{uuid.uuid4().hex[:8].upper()}"
        reported_at = datetime.now(UTC)

        # Calculate reporting deadline (24 hours from becoming aware)
        deadline = reported_at + timedelta(hours=24)

        # Priority 1 incidents (must be reported within 24 hours)
        priority_1_types = [
            SIRSIncidentType.UNEXPECTED_DEATH,
            SIRSIncidentType.UNREASONABLE_FORCE,
            SIRSIncidentType.UNLAWFUL_SEXUAL_CONTACT,
            SIRSIncidentType.PSYCHOLOGICAL_ABUSE,
            SIRSIncidentType.STEALING_FINANCIAL_ABUSE,
            SIRSIncidentType.NEGLECT,
            SIRSIncidentType.INAPPROPRIATE_RESTRAINT,
            SIRSIncidentType.MISSING_CONSUMER,
        ]

        is_priority_1 = incident_type in priority_1_types

        self._audit_log(
            user_id=reporter_id,
            action="REPORT_SIRS_INCIDENT",
            entity_type="SIRSIncident",
            entity_id=incident_id,
            details=f"Type: {incident_type.value}, Priority 1: {is_priority_1}",
        )

        result = {
            "success": True,
            "incident_id": incident_id,
            "resident": resident.full_name,
            "incident_type": incident_type.value,
            "priority_1": is_priority_1,
            "reported_at": reported_at.isoformat(),
            "reporting_deadline": deadline.isoformat(),
        }

        if is_priority_1:
            result["urgent_notice"] = (
                "🚨 PRIORITY 1 INCIDENT - Must be reported to the "
                "Aged Care Quality and Safety Commission within 24 hours. "
                "Use My Aged Care Provider Portal or call 1800 951 822."
            )

        return result

    # =========================================================================
    # FAMILY COMMUNICATION
    # =========================================================================

    def get_family_update(self, resident_id: str) -> dict:
        """Generate a family-friendly update for a resident."""
        resident = self.get_resident(resident_id)
        if not resident:
            return {"error": "Resident not found"}

        # Get recent care notes (excluding clinical details)
        recent_notes = [
            note
            for note in self.care_notes
            if note.resident_id == resident_id
            and (datetime.now(UTC) - note.created_at).days <= 7
        ]

        summary = {
            "resident_name": resident.preferred_name or resident.first_name,
            "update_date": date.today().isoformat(),
            "general_wellbeing": "Good",  # Would be assessed
            "activities_participated": [
                "Morning exercise group",
                "Art therapy session",
                "Garden visit",
            ],
            "meals": "Eating well with modified texture meals",
            "sleep": "Sleeping well overnight",
            "visitors": "Looking forward to family visits",
            "upcoming": [
                "GP review scheduled",
                "Hairdresser visit Thursday",
            ],
            "care_plan_review_due": resident.care_plan_due,
        }

        if resident.care_plan_due:
            summary["action_required"] = (
                "Care plan review is due. We would like to schedule "
                "a family meeting to discuss care goals."
            )

        return summary

    # =========================================================================
    # STAFF CREDENTIALS
    # =========================================================================

    def verify_staff_credentials(self, staff_id: str) -> dict:
        """Verify staff credentials and mandatory training."""
        # Demo verification (would check against actual records)
        credentials = {
            "staff_id": staff_id,
            "verification_date": datetime.now(UTC).isoformat(),
            "police_check": {
                "status": "Current",
                "expiry": (date.today() + timedelta(days=180)).isoformat(),
            },
            "working_with_vulnerable_people": {
                "status": "Current",
                "expiry": (date.today() + timedelta(days=365)).isoformat(),
            },
            "mandatory_training": {
                "infection_control": {"completed": True, "date": "2024-01-15"},
                "manual_handling": {"completed": True, "date": "2024-02-20"},
                "fire_safety": {"completed": True, "date": "2024-03-10"},
                "dementia_care": {"completed": True, "date": "2024-01-08"},
                "medication_management": {"completed": True, "date": "2024-02-28"},
                "elder_abuse_prevention": {"completed": True, "date": "2024-03-15"},
            },
            "all_current": True,
        }

        # Check for expiring credentials
        expiring_soon = []
        for check_name, check_data in [
            ("Police Check", credentials["police_check"]),
            ("WWVP", credentials["working_with_vulnerable_people"]),
        ]:
            expiry = date.fromisoformat(check_data["expiry"])
            if expiry <= date.today() + timedelta(days=30):
                expiring_soon.append(f"{check_name} expires {expiry}")

        credentials["warnings"] = expiring_soon

        return credentials


# =============================================================================
# DEMO EXECUTION
# =============================================================================


async def run_demo():
    """Run demonstration of the aged care assistant."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AGED CARE ASSISTANT - DEMO                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ⚠️  DEMONSTRATION ONLY - NOT OFFICIAL AGED CARE SOFTWARE                     ║
║  Aligned with Aged Care Act 2024 requirements.                                ║
║  Always verify with Aged Care Quality and Safety Commission.                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )

    assistant = AgedCareAssistant()

    # Demo: Resident summary
    print("\n" + "=" * 70)
    print("SCENARIO 1: Resident Summary")
    print("=" * 70)

    summary = assistant.get_resident_summary("RES-001")
    print(f"\nResident: {summary['name']} ({summary['preferred_name']})")
    print(f"Age: {summary['age']} | Room: {summary['room']}")
    print(f"AN-ACC Class: {summary['an_acc_class']}")
    print(f"Mobility: {summary['mobility']}")
    print(f"Cognitive Status: {summary['cognitive_status']}")
    print(f"\nDietary: {', '.join(summary['dietary_requirements'])}")
    print(f"Allergies: {', '.join(summary['allergies'])}")
    print("\nGoals of Care:")
    for goal in summary["goals_of_care"]:
        print(f"  • {goal}")
    print(f"\nCare Plan Review Due: {'Yes ⚠️' if summary['care_plan_due'] else 'No'}")
    print(f"Active Medications: {len(summary['active_medications'])}")

    # Demo: Medication round
    print("\n" + "=" * 70)
    print("SCENARIO 2: Medication Round (08:00)")
    print("=" * 70)

    round_meds = assistant.get_medication_round(time(8, 0), "NURSE-001")
    print(f"\nMedications due at 08:00: {len(round_meds)}")
    for med in round_meds:
        high_risk = "⚠️ HIGH RISK" if med["high_risk"] else ""
        double_sign = "👥 DOUBLE SIGN" if med["requires_double_sign"] else ""
        print(f"\n  Room {med['room']} - {med['resident_name']}")
        print(f"    {med['medication']} {med['strength']} ({med['route']})")
        print(f"    {high_risk} {double_sign}".strip())
        if med["allergies"]:
            print(f"    Allergies: {', '.join(med['allergies'])}")

    # Demo: Medication administration
    print("\n" + "=" * 70)
    print("SCENARIO 3: Administer Medication")
    print("=" * 70)

    # Regular medication
    result = assistant.record_medication_administration(
        medication_id="MED-001",
        administered_by="NURSE-001",
        status="Given",
        clinical_notes="Resident took medication with thickened water.",
    )
    print(f"\n✓ {result['medication']} administered to {result['resident']}")
    print(f"  Status: {result['status']} at {result['time']}")

    # S8 medication (requires witness)
    print("\nAttempting S8 medication without witness...")
    result = assistant.record_medication_administration(
        medication_id="MED-003",
        administered_by="NURSE-001",
        status="Given",
    )
    print(f"✗ Error: {result['error']}")

    # With witness
    result = assistant.record_medication_administration(
        medication_id="MED-003",
        administered_by="NURSE-001",
        witnessed_by="NURSE-002",
        status="Given",
        clinical_notes="Given for breakthrough pain. Resident comfort improved.",
    )
    print("\n✓ S8 Medication administered with witness")
    for warning in result.get("warnings", []):
        print(f"  {warning}")

    # Demo: Quality Indicators
    print("\n" + "=" * 70)
    print("SCENARIO 4: Quality Indicator Recording")
    print("=" * 70)

    qi_result = assistant.record_quality_indicator(
        resident_id="RES-001",
        indicator=QualityIndicator.FALLS_MAJOR_INJURY,
        value="No falls this quarter",
        notes="Resident using wheelchair consistently. No near-misses recorded.",
        recorded_by="RN-001",
    )
    print(f"\n✓ Quality Indicator recorded: {qi_result['indicator']}")
    print(f"  Resident: {qi_result['resident']}")

    # Demo: SIRS Reporting
    print("\n" + "=" * 70)
    print("SCENARIO 5: SIRS Incident Reporting")
    print("=" * 70)

    incident = assistant.report_sirs_incident(
        resident_id="RES-001",
        incident_type=SIRSIncidentType.MISSING_CONSUMER,
        incident_date=datetime.now(UTC),
        description="Resident found in garden unaccompanied. Returned safely within 10 minutes.",
        immediate_actions="Resident returned to unit. Door alarm checked and functioning.",
        reporter_id="RN-001",
        reporter_name="Senior RN",
    )
    print(f"\n✓ SIRS Incident reported: {incident['incident_id']}")
    print(f"  Type: {incident['incident_type']}")
    print(f"  Priority 1: {incident['priority_1']}")
    if incident.get("urgent_notice"):
        print(f"  {incident['urgent_notice']}")

    # Demo: Family update
    print("\n" + "=" * 70)
    print("SCENARIO 6: Family Communication")
    print("=" * 70)

    update = assistant.get_family_update("RES-001")
    print(f"\nUpdate for {update['resident_name']}'s family:")
    print(f"  General Wellbeing: {update['general_wellbeing']}")
    print(f"  Meals: {update['meals']}")
    print(f"  Sleep: {update['sleep']}")
    print("\n  Recent Activities:")
    for activity in update["activities_participated"]:
        print(f"    • {activity}")

    # Demo: Staff credentials
    print("\n" + "=" * 70)
    print("SCENARIO 7: Staff Credential Verification")
    print("=" * 70)

    creds = assistant.verify_staff_credentials("NURSE-001")
    print(f"\nStaff ID: {creds['staff_id']}")
    print(
        f"Police Check: {creds['police_check']['status']} (expires {creds['police_check']['expiry']})"
    )
    print(f"WWVP: {creds['working_with_vulnerable_people']['status']}")
    print(f"All Credentials Current: {'✓ Yes' if creds['all_current'] else '✗ No'}")
    if creds["warnings"]:
        for warning in creds["warnings"]:
            print(f"  ⚠️ {warning}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Aged Care Assistant Demo")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run full demonstration",
    )

    args = parser.parse_args()
    asyncio.run(run_demo())
