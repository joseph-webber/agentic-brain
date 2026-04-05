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
Healthcare Triage Bot for Australian Healthcare.

An AI assistant for healthcare triage with Australian health system integration:

- Symptom assessment with urgency classification
- Appointment booking workflows
- Medicare/PBS integration patterns
- Nurse triage decision support (Australasian Triage Scale)
- After-hours care guidance
- Referral pathways

Key Australian Healthcare Context:
    - Australasian Triage Scale (ATS) for emergency classification
    - Medicare Benefits Schedule (MBS) item awareness
    - Pharmaceutical Benefits Scheme (PBS) patterns
    - Health Practitioner Regulation National Law compliance
    - Australian Commission on Safety and Quality in Health Care standards

Architecture (Privacy-First - Australian Privacy Principles):
    ┌──────────────────────────────────────────────────────────────────┐
    │                    ON-PREMISE HEALTHCARE ZONE                     │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
    │  │  Ollama  │  │   SQLite     │  │   Healthcare Triage Bot    │  │
    │  │ (Local)  │◄─┤  (Encrypted) │◄─┤   (This Application)       │  │
    │  └──────────┘  └──────────────┘  └────────────────────────────┘  │
    │              ALL PATIENT DATA STAYS LOCAL                         │
    │              HIPAA/APP COMPLIANT ENVIRONMENT                      │
    └──────────────────────────────────────────────────────────────────┘

CRITICAL DISCLAIMERS:
    ⚠️  THIS SYSTEM DOES NOT PROVIDE MEDICAL ADVICE
    ⚠️  THIS IS A DEMONSTRATION/EDUCATIONAL TOOL ONLY
    ⚠️  ALWAYS CONSULT QUALIFIED HEALTHCARE PROFESSIONALS
    ⚠️  IN EMERGENCY: CALL 000 (TRIPLE ZERO) IMMEDIATELY
    ⚠️  NOT A SUBSTITUTE FOR PROFESSIONAL MEDICAL JUDGMENT
    ⚠️  Clinical decisions require registered health practitioners

Usage:
    python examples/enterprise/healthcare_triage_bot.py
    python examples/enterprise/healthcare_triage_bot.py --demo

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
from enum import Enum, IntEnum
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
logger = logging.getLogger("healthcare.triage_bot")


# =============================================================================
# MEDICAL DISCLAIMER (CRITICAL)
# =============================================================================

MEDICAL_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                      ⚠️  IMPORTANT MEDICAL DISCLAIMER  ⚠️                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  This system is for DEMONSTRATION PURPOSES ONLY.                             ║
║                                                                              ║
║  🚨 IN AN EMERGENCY, CALL 000 (TRIPLE ZERO) IMMEDIATELY 🚨                   ║
║                                                                              ║
║  This system:                                                                ║
║  • Does NOT provide medical advice                                           ║
║  • Does NOT diagnose medical conditions                                      ║
║  • Does NOT replace professional medical judgment                            ║
║  • Is NOT a substitute for seeing a doctor                                   ║
║                                                                              ║
║  Always consult a qualified healthcare professional for medical concerns.    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# =============================================================================
# AUSTRALASIAN TRIAGE SCALE (ATS)
# =============================================================================


class AustralasianTriageScale(IntEnum):
    """
    Australasian Triage Scale (ATS) - Emergency Department triage categories.

    Used throughout Australia and New Zealand for ED triage.
    Each category has a defined maximum waiting time.
    """

    ATS_1 = 1  # Immediate - life threatening
    ATS_2 = 2  # Emergency - imminently life threatening (≤10 min)
    ATS_3 = 3  # Urgent - potentially life threatening (≤30 min)
    ATS_4 = 4  # Semi-urgent - potentially serious (≤60 min)
    ATS_5 = 5  # Non-urgent - less urgent (≤120 min)


class UrgencyLevel(str, Enum):
    """General urgency classification for non-ED settings."""

    EMERGENCY = "Emergency - Call 000"
    URGENT = "Urgent - See doctor today"
    SEMI_URGENT = "Semi-Urgent - See doctor within 24-48 hours"
    ROUTINE = "Routine - Book appointment this week"
    SELF_CARE = "Self-Care - Monitor at home"


class BodySystem(str, Enum):
    """Body systems for symptom classification."""

    CARDIOVASCULAR = "Cardiovascular"
    RESPIRATORY = "Respiratory"
    NEUROLOGICAL = "Neurological"
    GASTROINTESTINAL = "Gastrointestinal"
    MUSCULOSKELETAL = "Musculoskeletal"
    DERMATOLOGICAL = "Dermatological"
    UROLOGICAL = "Urological"
    MENTAL_HEALTH = "Mental Health"
    ENT = "Ear, Nose, Throat"
    OPHTHALMOLOGY = "Ophthalmology"
    GENERAL = "General"


# =============================================================================
# RED FLAG SYMPTOMS (EMERGENCY)
# =============================================================================

# These symptoms require immediate emergency care - Call 000
RED_FLAG_SYMPTOMS = {
    "chest_pain": {
        "description": "Chest pain, tightness, or pressure",
        "urgency": UrgencyLevel.EMERGENCY,
        "action": "Call 000 immediately. Could indicate heart attack.",
    },
    "difficulty_breathing": {
        "description": "Severe difficulty breathing or shortness of breath",
        "urgency": UrgencyLevel.EMERGENCY,
        "action": "Call 000 immediately.",
    },
    "stroke_symptoms": {
        "description": "Face drooping, arm weakness, speech difficulty (FAST)",
        "urgency": UrgencyLevel.EMERGENCY,
        "action": "Call 000 immediately. Time is critical for stroke.",
    },
    "severe_bleeding": {
        "description": "Uncontrolled bleeding that won't stop",
        "urgency": UrgencyLevel.EMERGENCY,
        "action": "Apply pressure, call 000 immediately.",
    },
    "unconsciousness": {
        "description": "Loss of consciousness or unresponsive",
        "urgency": UrgencyLevel.EMERGENCY,
        "action": "Call 000 immediately. Check airway, breathing.",
    },
    "severe_allergic_reaction": {
        "description": "Anaphylaxis - swelling, difficulty breathing after exposure",
        "urgency": UrgencyLevel.EMERGENCY,
        "action": "Use EpiPen if available, call 000 immediately.",
    },
    "suicidal_thoughts": {
        "description": "Thoughts of self-harm or suicide",
        "urgency": UrgencyLevel.EMERGENCY,
        "action": "Call Lifeline 13 11 14 or 000 if immediate danger.",
    },
}


# =============================================================================
# PATIENT MODEL
# =============================================================================


@dataclass
class Patient:
    """Patient record for triage purposes."""

    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    medicare_number: str
    gender: str
    phone: str
    email: str
    address: str

    # Medical history
    allergies: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)

    # Healthcare identifiers
    ihi: str = ""  # Individual Healthcare Identifier
    dva_card: bool = False
    healthcare_card: bool = False
    private_health_insurance: bool = False

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


@dataclass
class SymptomAssessment:
    """Symptom assessment record."""

    assessment_id: str
    patient_id: str
    assessment_date: datetime

    # Presenting complaint
    chief_complaint: str
    symptom_duration: str
    symptom_severity: int  # 1-10 scale
    body_system: BodySystem

    # Additional symptoms
    associated_symptoms: list[str] = field(default_factory=list)

    # Red flags
    red_flags_identified: list[str] = field(default_factory=list)

    # Assessment outcome
    urgency_level: UrgencyLevel = UrgencyLevel.ROUTINE
    ats_category: Optional[AustralasianTriageScale] = None
    recommendation: str = ""

    # Triage decision
    triaged_by: str = ""
    triage_time: Optional[datetime] = None
    clinical_notes: str = ""


@dataclass
class Appointment:
    """Healthcare appointment record."""

    appointment_id: str
    patient_id: str
    provider_id: str
    provider_name: str
    appointment_type: str
    appointment_date: date
    appointment_time: time
    duration_minutes: int = 15
    status: str = "Scheduled"  # Scheduled, Confirmed, Arrived, Completed, Cancelled

    # Medicare/Billing
    mbs_item: str = ""
    bulk_billed: bool = True
    estimated_gap: float = 0.0

    # Telehealth
    is_telehealth: bool = False
    telehealth_link: str = ""

    notes: str = ""


# =============================================================================
# HEALTHCARE PROVIDERS
# =============================================================================

DEMO_PROVIDERS = {
    "GP-001": {
        "name": "Dr Sarah Chen",
        "specialty": "General Practice",
        "provider_number": "1234567A",
        "practice": "Central Medical Centre",
        "bulk_bills": True,
        "availability": ["Monday", "Tuesday", "Wednesday", "Friday"],
    },
    "GP-002": {
        "name": "Dr Michael Wong",
        "specialty": "General Practice",
        "provider_number": "2345678B",
        "practice": "Central Medical Centre",
        "bulk_bills": True,
        "availability": ["Monday", "Thursday", "Friday", "Saturday"],
    },
    "NP-001": {
        "name": "Susan Taylor NP",
        "specialty": "Nurse Practitioner",
        "provider_number": "3456789C",
        "practice": "Central Medical Centre",
        "bulk_bills": True,
        "availability": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    },
}

# Common MBS Items for GP consultations
MBS_ITEMS = {
    "23": {
        "description": "Level A - Brief consultation",
        "schedule_fee": 18.20,
        "duration_minutes": 5,
    },
    "36": {
        "description": "Level B - Standard consultation",
        "schedule_fee": 40.20,
        "duration_minutes": 15,
    },
    "44": {
        "description": "Level C - Long consultation",
        "schedule_fee": 78.10,
        "duration_minutes": 30,
    },
    "52": {
        "description": "Level D - Prolonged consultation",
        "schedule_fee": 114.60,
        "duration_minutes": 45,
    },
    "91890": {
        "description": "Telehealth - Level B equivalent",
        "schedule_fee": 40.20,
        "duration_minutes": 15,
    },
}


# =============================================================================
# HEALTHCARE TRIAGE BOT
# =============================================================================


class HealthcareTriageBot:
    """
    Healthcare Triage Assistant.

    Supports healthcare triage workflows with Australian health system
    integration patterns. NOT a diagnostic tool.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the healthcare triage bot."""
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self.patients: dict[str, Patient] = {}
        self.assessments: list[SymptomAssessment] = []
        self.appointments: list[Appointment] = []
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
        self.patients["PAT-001"] = Patient(
            patient_id="PAT-001",
            first_name="Emma",
            last_name="Wilson",
            date_of_birth=date(1985, 3, 15),
            medicare_number="2123 45678 1",
            gender="Female",
            phone="0412 345 678",
            email="emma.wilson@email.com",
            address="123 Main Street, Sydney NSW 2000",
            allergies=["Penicillin"],
            medications=["Metformin 500mg", "Atorvastatin 20mg"],
            conditions=["Type 2 Diabetes", "High Cholesterol"],
            private_health_insurance=True,
        )

        self.patients["PAT-002"] = Patient(
            patient_id="PAT-002",
            first_name="James",
            last_name="Brown",
            date_of_birth=date(1970, 8, 22),
            medicare_number="3234 56789 2",
            gender="Male",
            phone="0423 456 789",
            email="james.brown@email.com",
            address="456 Oak Avenue, Melbourne VIC 3000",
            allergies=[],
            medications=["Omeprazole 20mg"],
            conditions=["GORD"],
            healthcare_card=True,
        )

    # =========================================================================
    # SYMPTOM ASSESSMENT (NOT DIAGNOSIS)
    # =========================================================================

    def assess_symptoms(
        self,
        patient_id: str,
        chief_complaint: str,
        symptom_duration: str,
        symptom_severity: int,
        body_system: BodySystem,
        associated_symptoms: list[str],
        triage_nurse_id: str,
    ) -> dict:
        """
        Perform symptom assessment to guide care pathway.

        NOTE: This is NOT a diagnostic tool. All clinical decisions
        must be made by qualified healthcare professionals.
        """
        patient = self.patients.get(patient_id)
        if not patient:
            return {"error": "Patient not found"}

        assessment_id = f"ASS-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(UTC)

        # Check for red flag symptoms
        red_flags = []
        urgency = UrgencyLevel.ROUTINE

        # Simplified red flag detection
        chief_complaint.lower()
        symptoms_text = " ".join([chief_complaint] + associated_symptoms).lower()

        for flag_key, flag_info in RED_FLAG_SYMPTOMS.items():
            keywords = flag_key.replace("_", " ").split()
            if any(kw in symptoms_text for kw in keywords):
                red_flags.append(flag_info["description"])
                if flag_info["urgency"].value.startswith("Emergency"):
                    urgency = UrgencyLevel.EMERGENCY
                    break

        # Severity-based urgency (if no red flags)
        if not red_flags:
            if symptom_severity >= 9:
                urgency = UrgencyLevel.URGENT
            elif symptom_severity >= 7:
                urgency = UrgencyLevel.SEMI_URGENT
            elif symptom_severity >= 4:
                urgency = UrgencyLevel.ROUTINE
            else:
                urgency = UrgencyLevel.SELF_CARE

        # Generate recommendation
        recommendation = self._generate_recommendation(urgency, body_system, patient)

        assessment = SymptomAssessment(
            assessment_id=assessment_id,
            patient_id=patient_id,
            assessment_date=now,
            chief_complaint=chief_complaint,
            symptom_duration=symptom_duration,
            symptom_severity=symptom_severity,
            body_system=body_system,
            associated_symptoms=associated_symptoms,
            red_flags_identified=red_flags,
            urgency_level=urgency,
            recommendation=recommendation,
            triaged_by=triage_nurse_id,
            triage_time=now,
        )

        self.assessments.append(assessment)

        self._audit_log(
            user_id=triage_nurse_id,
            action="SYMPTOM_ASSESSMENT",
            entity_type="Assessment",
            entity_id=assessment_id,
            details=f"Patient: {patient_id}, Urgency: {urgency.value}",
        )

        result = {
            "assessment_id": assessment_id,
            "patient_name": patient.full_name,
            "urgency_level": urgency.value,
            "red_flags": red_flags,
            "recommendation": recommendation,
            "disclaimer": MEDICAL_DISCLAIMER,
        }

        if urgency == UrgencyLevel.EMERGENCY:
            result["emergency_action"] = (
                "🚨 CALL 000 (TRIPLE ZERO) IMMEDIATELY 🚨\n"
                "This assessment has identified potential emergency symptoms.\n"
                "Do not delay seeking emergency medical care."
            )

        return result

    def _generate_recommendation(
        self,
        urgency: UrgencyLevel,
        body_system: BodySystem,
        patient: Patient,
    ) -> str:
        """Generate care pathway recommendation."""
        if urgency == UrgencyLevel.EMERGENCY:
            return (
                "🚨 EMERGENCY: Call 000 (Triple Zero) immediately.\n"
                "Do not drive yourself. Ambulance recommended.\n"
                "If safe, have someone stay with you until help arrives."
            )

        if urgency == UrgencyLevel.URGENT:
            return (
                "⚠️ URGENT: See a doctor today.\n"
                "Options:\n"
                "• Book same-day GP appointment\n"
                "• Visit urgent care clinic\n"
                "• Attend hospital emergency department if symptoms worsen\n"
                "Call 13 HEALTH (13 43 25 84) for health advice."
            )

        if urgency == UrgencyLevel.SEMI_URGENT:
            return (
                "📋 SEMI-URGENT: See a doctor within 24-48 hours.\n"
                "• Book a GP appointment for tomorrow\n"
                "• Monitor symptoms and seek earlier care if they worsen\n"
                "• Consider telehealth consultation if preferred"
            )

        if urgency == UrgencyLevel.ROUTINE:
            return (
                "📅 ROUTINE: Book a GP appointment this week.\n"
                "• Book at your regular GP for continuity of care\n"
                "• Telehealth may be suitable for initial consultation\n"
                "• Prepare list of symptoms and questions"
            )

        # Self-care
        return (
            "🏠 SELF-CARE: Monitor symptoms at home.\n"
            "• Rest and stay hydrated\n"
            "• Over-the-counter medications may help\n"
            "• Seek medical advice if symptoms persist >3 days or worsen\n"
            "• Your pharmacist can provide advice"
        )

    # =========================================================================
    # APPOINTMENT BOOKING
    # =========================================================================

    def find_available_appointments(
        self,
        preferred_date: date,
        appointment_type: str = "Standard",
        provider_id: Optional[str] = None,
        telehealth_ok: bool = True,
    ) -> list[dict]:
        """Find available appointment slots."""
        available = []

        # Generate demo availability (would query actual system in production)
        providers = (
            {provider_id: DEMO_PROVIDERS[provider_id]}
            if provider_id and provider_id in DEMO_PROVIDERS
            else DEMO_PROVIDERS
        )

        # Check preferred date and next 5 days
        for day_offset in range(6):
            check_date = preferred_date + timedelta(days=day_offset)
            day_name = check_date.strftime("%A")

            for prov_id, provider in providers.items():
                if day_name not in provider.get("availability", []):
                    continue

                # Generate available times (9am - 5pm)
                for hour in range(9, 17):
                    for minute in [0, 15, 30, 45]:
                        slot_time = time(hour, minute)

                        # Check if slot is not already booked
                        is_booked = any(
                            appt.provider_id == prov_id
                            and appt.appointment_date == check_date
                            and appt.appointment_time == slot_time
                            and appt.status != "Cancelled"
                            for appt in self.appointments
                        )

                        if not is_booked:
                            available.append(
                                {
                                    "date": check_date.isoformat(),
                                    "time": slot_time.strftime("%H:%M"),
                                    "provider_id": prov_id,
                                    "provider_name": provider["name"],
                                    "specialty": provider["specialty"],
                                    "practice": provider["practice"],
                                    "bulk_bills": provider["bulk_bills"],
                                }
                            )

        # Limit results
        return available[:20]

    def book_appointment(
        self,
        patient_id: str,
        provider_id: str,
        appointment_date: date,
        appointment_time: time,
        appointment_type: str,
        is_telehealth: bool,
        user_id: str,
    ) -> dict:
        """Book a healthcare appointment."""
        patient = self.patients.get(patient_id)
        if not patient:
            return {"error": "Patient not found"}

        provider = DEMO_PROVIDERS.get(provider_id)
        if not provider:
            return {"error": "Provider not found"}

        # Check availability
        is_booked = any(
            appt.provider_id == provider_id
            and appt.appointment_date == appointment_date
            and appt.appointment_time == appointment_time
            and appt.status != "Cancelled"
            for appt in self.appointments
        )

        if is_booked:
            return {"error": "Time slot no longer available"}

        appointment_id = f"APT-{uuid.uuid4().hex[:8].upper()}"

        # Determine MBS item
        mbs_item = "91890" if is_telehealth else "36"  # Level B
        mbs_info = MBS_ITEMS.get(mbs_item, {})

        appointment = Appointment(
            appointment_id=appointment_id,
            patient_id=patient_id,
            provider_id=provider_id,
            provider_name=provider["name"],
            appointment_type=appointment_type,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            duration_minutes=mbs_info.get("duration_minutes", 15),
            mbs_item=mbs_item,
            bulk_billed=provider["bulk_bills"],
            is_telehealth=is_telehealth,
        )

        self.appointments.append(appointment)

        self._audit_log(
            user_id=user_id,
            action="BOOK_APPOINTMENT",
            entity_type="Appointment",
            entity_id=appointment_id,
            details=f"Patient: {patient_id}, Provider: {provider_id}",
        )

        result = {
            "success": True,
            "appointment_id": appointment_id,
            "patient_name": patient.full_name,
            "provider": provider["name"],
            "practice": provider["practice"],
            "date": appointment_date.isoformat(),
            "time": appointment_time.strftime("%H:%M"),
            "duration": f"{appointment.duration_minutes} minutes",
            "telehealth": is_telehealth,
            "bulk_billed": appointment.bulk_billed,
            "mbs_item": mbs_item,
            "confirmation": f"Your appointment is confirmed for {appointment_date.strftime('%A, %d %B %Y')} at {appointment_time.strftime('%I:%M %p')}.",
        }

        if is_telehealth:
            result["telehealth_instructions"] = (
                "A telehealth link will be sent to your email/SMS "
                "before the appointment. Ensure you have a device with "
                "camera and microphone, and stable internet connection."
            )
        else:
            result["clinic_instructions"] = (
                f"Please arrive 10 minutes early at {provider['practice']}. "
                "Bring your Medicare card and any relevant test results."
            )

        return result

    # =========================================================================
    # MEDICARE / PBS INFORMATION
    # =========================================================================

    def get_medicare_info(self, mbs_item: str) -> dict:
        """Get Medicare Benefits Schedule item information."""
        item = MBS_ITEMS.get(mbs_item)
        if not item:
            return {"error": "MBS item not found"}

        return {
            "mbs_item": mbs_item,
            "description": item["description"],
            "schedule_fee": f"${item['schedule_fee']:.2f}",
            "medicare_rebate_100": f"${item['schedule_fee']:.2f}",
            "medicare_rebate_85": f"${item['schedule_fee'] * 0.85:.2f}",
            "typical_duration": f"{item['duration_minutes']} minutes",
            "note": (
                "Medicare rebate is 100% of schedule fee for GP services "
                "when bulk-billed. Out-of-pocket costs (gap) apply if "
                "not bulk-billed. Check with your provider."
            ),
        }

    def check_pbs_eligibility(
        self,
        patient_id: str,
        medication_name: str,
    ) -> dict:
        """Check PBS eligibility for a medication (simplified)."""
        patient = self.patients.get(patient_id)
        if not patient:
            return {"error": "Patient not found"}

        # Demo PBS information (would query actual PBS in production)
        pbs_medications = {
            "metformin": {
                "pbs_code": "2271L",
                "brand_names": ["Diabex", "Diaformin", "Glucophage"],
                "general_patient_price": "$7.70",
                "concession_price": "$0.00" if patient.healthcare_card else "$7.70",
                "restrictions": None,
            },
            "atorvastatin": {
                "pbs_code": "9209N",
                "brand_names": ["Lipitor", "Atorvastatin Sandoz"],
                "general_patient_price": "$7.70",
                "concession_price": "$0.00" if patient.healthcare_card else "$7.70",
                "restrictions": "For hypercholesterolaemia",
            },
        }

        med_key = medication_name.lower()
        pbs_info = None

        for key, info in pbs_medications.items():
            if key in med_key:
                pbs_info = info
                break

        if not pbs_info:
            return {
                "medication": medication_name,
                "pbs_listed": False,
                "note": "This medication may not be PBS listed or requires authority prescription.",
            }

        return {
            "medication": medication_name,
            "pbs_listed": True,
            "pbs_code": pbs_info["pbs_code"],
            "brand_names": pbs_info["brand_names"],
            "patient_co_payment": (
                pbs_info["concession_price"]
                if patient.healthcare_card
                else pbs_info["general_patient_price"]
            ),
            "healthcare_card_holder": patient.healthcare_card,
            "restrictions": pbs_info.get("restrictions"),
        }

    # =========================================================================
    # AFTER-HOURS GUIDANCE
    # =========================================================================

    def get_after_hours_options(self, patient_id: str) -> dict:
        """Get after-hours healthcare options."""
        patient = self.patients.get(patient_id)

        return {
            "patient": patient.full_name if patient else "Unknown",
            "current_time": datetime.now().strftime("%H:%M"),
            "options": [
                {
                    "service": "13 HEALTH",
                    "phone": "13 43 25 84",
                    "description": "Free health advice from registered nurses 24/7",
                    "cost": "Free",
                },
                {
                    "service": "After Hours GP Helpline",
                    "phone": "1800 022 222",
                    "description": "Medicare-funded after-hours GP phone advice",
                    "cost": "Free with Medicare",
                },
                {
                    "service": "Urgent Care Clinic",
                    "description": "For urgent but non-life-threatening conditions",
                    "note": "Check Medicare website for nearest clinic",
                },
                {
                    "service": "Hospital Emergency Department",
                    "description": "For emergencies and serious conditions",
                    "note": "Expected wait times vary by urgency",
                },
            ],
            "emergency": {
                "service": "Triple Zero (000)",
                "description": "For life-threatening emergencies",
                "action": "Ambulance, Police, Fire",
            },
            "mental_health": {
                "service": "Lifeline",
                "phone": "13 11 14",
                "description": "24/7 crisis support and suicide prevention",
            },
        }


# =============================================================================
# DEMO EXECUTION
# =============================================================================


async def run_demo():
    """Run demonstration of the healthcare triage bot."""
    print(MEDICAL_DISCLAIMER)
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    HEALTHCARE TRIAGE BOT - DEMO                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ⚠️  DEMONSTRATION ONLY - NOT MEDICAL ADVICE                                  ║
║  This system demonstrates healthcare triage patterns for Australian context. ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )

    bot = HealthcareTriageBot()

    # Demo: Routine symptom assessment
    print("\n" + "=" * 70)
    print("SCENARIO 1: Routine Symptom Assessment")
    print("=" * 70)

    assessment = bot.assess_symptoms(
        patient_id="PAT-001",
        chief_complaint="Mild headache for 2 days",
        symptom_duration="2 days",
        symptom_severity=4,
        body_system=BodySystem.NEUROLOGICAL,
        associated_symptoms=["Tiredness", "Mild neck stiffness"],
        triage_nurse_id="NURSE-001",
    )

    print(f"\nAssessment: {assessment['assessment_id']}")
    print(f"Patient: {assessment['patient_name']}")
    print(f"Urgency: {assessment['urgency_level']}")
    print(f"\nRecommendation:\n{assessment['recommendation']}")

    # Demo: Urgent symptom assessment
    print("\n" + "=" * 70)
    print("SCENARIO 2: Urgent Symptom Assessment")
    print("=" * 70)

    urgent = bot.assess_symptoms(
        patient_id="PAT-002",
        chief_complaint="Severe abdominal pain",
        symptom_duration="6 hours",
        symptom_severity=8,
        body_system=BodySystem.GASTROINTESTINAL,
        associated_symptoms=["Nausea", "Vomiting", "Fever"],
        triage_nurse_id="NURSE-001",
    )

    print(f"\nAssessment: {urgent['assessment_id']}")
    print(f"Patient: {urgent['patient_name']}")
    print(f"Urgency: {urgent['urgency_level']}")
    print(f"\nRecommendation:\n{urgent['recommendation']}")

    # Demo: Emergency (chest pain)
    print("\n" + "=" * 70)
    print("SCENARIO 3: Emergency Assessment (Chest Pain)")
    print("=" * 70)

    emergency = bot.assess_symptoms(
        patient_id="PAT-001",
        chief_complaint="Chest pain and shortness of breath",
        symptom_duration="30 minutes",
        symptom_severity=9,
        body_system=BodySystem.CARDIOVASCULAR,
        associated_symptoms=["Sweating", "Pain radiating to arm"],
        triage_nurse_id="NURSE-001",
    )

    print(f"\nAssessment: {emergency['assessment_id']}")
    print(f"Urgency: {emergency['urgency_level']}")
    print(f"Red Flags: {emergency['red_flags']}")
    if emergency.get("emergency_action"):
        print(f"\n{emergency['emergency_action']}")

    # Demo: Find appointments
    print("\n" + "=" * 70)
    print("SCENARIO 4: Find Available Appointments")
    print("=" * 70)

    tomorrow = date.today() + timedelta(days=1)
    available = bot.find_available_appointments(tomorrow)

    print(f"\nAvailable appointments from {tomorrow}:")
    for slot in available[:5]:
        print(
            f"  • {slot['date']} {slot['time']} - {slot['provider_name']} ({slot['practice']})"
        )
        print(f"    Bulk Bills: {'Yes' if slot['bulk_bills'] else 'No'}")

    # Demo: Book appointment
    print("\n" + "=" * 70)
    print("SCENARIO 5: Book Appointment")
    print("=" * 70)

    booking = bot.book_appointment(
        patient_id="PAT-001",
        provider_id="GP-001",
        appointment_date=tomorrow,
        appointment_time=time(10, 0),
        appointment_type="Standard",
        is_telehealth=False,
        user_id="RECEPTION-001",
    )

    print(f"\n✓ Appointment booked: {booking['appointment_id']}")
    print(f"  Patient: {booking['patient_name']}")
    print(f"  Provider: {booking['provider']}")
    print(f"  Date/Time: {booking['date']} at {booking['time']}")
    print(f"  Bulk Billed: {'Yes' if booking['bulk_billed'] else 'No'}")
    print(f"  MBS Item: {booking['mbs_item']}")
    print(f"\n  {booking['confirmation']}")

    # Demo: Medicare info
    print("\n" + "=" * 70)
    print("SCENARIO 6: Medicare Information")
    print("=" * 70)

    mbs_info = bot.get_medicare_info("36")
    print(f"\nMBS Item {mbs_info['mbs_item']}: {mbs_info['description']}")
    print(f"  Schedule Fee: {mbs_info['schedule_fee']}")
    print(f"  Medicare Rebate (100%): {mbs_info['medicare_rebate_100']}")
    print(f"  Typical Duration: {mbs_info['typical_duration']}")

    # Demo: PBS check
    print("\n" + "=" * 70)
    print("SCENARIO 7: PBS Eligibility Check")
    print("=" * 70)

    pbs = bot.check_pbs_eligibility("PAT-001", "Metformin 500mg")
    print(f"\nMedication: {pbs.get('medication')}")
    print(f"PBS Listed: {'Yes' if pbs.get('pbs_listed') else 'No'}")
    if pbs.get("pbs_listed"):
        print(f"PBS Code: {pbs['pbs_code']}")
        print(f"Patient Co-payment: {pbs['patient_co_payment']}")
        print(f"Healthcare Card: {'Yes' if pbs['healthcare_card_holder'] else 'No'}")

    # Demo: After hours
    print("\n" + "=" * 70)
    print("SCENARIO 8: After-Hours Options")
    print("=" * 70)

    after_hours = bot.get_after_hours_options("PAT-001")
    print(f"\nAfter-Hours Healthcare Options for {after_hours['patient']}:")
    for option in after_hours["options"][:3]:
        print(f"\n  {option['service']}")
        if option.get("phone"):
            print(f"    Phone: {option['phone']}")
        print(f"    {option['description']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Healthcare Triage Bot Demo")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run full demonstration",
    )

    args = parser.parse_args()
    asyncio.run(run_demo())
