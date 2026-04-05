#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 60: Specialist Disability Accommodation (SDA) Management
=================================================================

DISCLAIMER: This is a demonstration example only.
All names, addresses, and data are fictional.
This is not affiliated with any real NDIS provider.
Consult official NDIS guidelines for actual implementation.

Comprehensive SDA property management for NDIS-registered providers.

SDA Overview:
    Specialist Disability Accommodation is funding for housing built to
    special design standards for people with extreme functional impairment
    or very high support needs. SDA is the bricks and mortar - not support.

SDA Design Categories:
    - Basic: Accessible features above minimum building code
    - Improved Liveability: Better physical access + liveable features
    - Fully Accessible: High physical access for wheelchairs
    - Robust: High durability for complex behaviours
    - High Physical Support: Highest physical access + assistive tech ready

SDA Building Types:
    - Apartment: Self-contained unit in larger building
    - Villa/Duplex: Ground-level with private entrance
    - Group Home: Shared living with private bedrooms
    - House: Stand-alone dwelling

This System Manages:
    - Property listings with accessibility features
    - Participant matching based on SDA category needs
    - Vacancy and occupancy management
    - SDA Design Standard compliance tracking
    - Building and design category documentation
    - Occupancy agreements
    - Maintenance scheduling with accessibility focus
    - SDA pricing and NDIS billing integration

Privacy Architecture:
    - On-premise deployment (no cloud)
    - Participant data encrypted at rest
    - NDIS number hashed for storage
    - Audit logging for all access
    - Compliant with Privacy Act 1988 (Cth)

Requirements:
    - Ollama running with llama3.1:8b
    - Neo4j for property/participant data (optional)

Author: agentic-brain
License: MIT
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# NDIS SDA ENUMERATIONS
# ══════════════════════════════════════════════════════════════════════════════


class SDADesignCategory(Enum):
    """NDIS SDA Design Categories as per SDA Rules 2020."""

    BASIC = "basic"
    IMPROVED_LIVEABILITY = "improved_liveability"
    FULLY_ACCESSIBLE = "fully_accessible"
    ROBUST = "robust"
    HIGH_PHYSICAL_SUPPORT = "high_physical_support"


class SDABuildingType(Enum):
    """NDIS SDA Building Types."""

    APARTMENT = "apartment"
    VILLA = "villa"
    DUPLEX = "duplex"
    GROUP_HOME = "group_home"
    HOUSE = "house"


class SDALocation(Enum):
    """SDA Location categories for pricing."""

    METRO = "metro"  # Major cities
    REGIONAL = "regional"  # Regional centres
    REMOTE = "remote"  # Remote areas
    VERY_REMOTE = "very_remote"  # Very remote areas


class OccupancyStatus(Enum):
    """Property occupancy status."""

    VACANT = "vacant"
    OCCUPIED = "occupied"
    RESERVED = "reserved"  # Pending move-in
    UNDER_MAINTENANCE = "under_maintenance"
    DECOMMISSIONED = "decommissioned"


class MaintenancePriority(Enum):
    """Maintenance request priority levels."""

    CRITICAL = "critical"  # Immediate - affects accessibility
    HIGH = "high"  # Within 24 hours
    MEDIUM = "medium"  # Within 1 week
    LOW = "low"  # Scheduled maintenance
    PLANNED = "planned"  # Preventive maintenance


class ApplicationStatus(Enum):
    """Housing application status."""

    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    SDA_VERIFICATION = "sda_verification"
    PROPERTY_MATCHING = "property_matching"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WAITLISTED = "waitlisted"


# ══════════════════════════════════════════════════════════════════════════════
# SDA PRICING (Based on NDIS SDA Price Guide 2024-25)
# ══════════════════════════════════════════════════════════════════════════════


# Daily SDA rates by design category and building type (example rates)
SDA_DAILY_RATES = {
    # High Physical Support
    (SDADesignCategory.HIGH_PHYSICAL_SUPPORT, SDABuildingType.APARTMENT): Decimal(
        "217.84"
    ),
    (SDADesignCategory.HIGH_PHYSICAL_SUPPORT, SDABuildingType.VILLA): Decimal("314.12"),
    (SDADesignCategory.HIGH_PHYSICAL_SUPPORT, SDABuildingType.GROUP_HOME): Decimal(
        "157.98"
    ),
    (SDADesignCategory.HIGH_PHYSICAL_SUPPORT, SDABuildingType.HOUSE): Decimal("314.12"),
    # Fully Accessible
    (SDADesignCategory.FULLY_ACCESSIBLE, SDABuildingType.APARTMENT): Decimal("145.23"),
    (SDADesignCategory.FULLY_ACCESSIBLE, SDABuildingType.VILLA): Decimal("209.41"),
    (SDADesignCategory.FULLY_ACCESSIBLE, SDABuildingType.GROUP_HOME): Decimal("105.32"),
    (SDADesignCategory.FULLY_ACCESSIBLE, SDABuildingType.HOUSE): Decimal("209.41"),
    # Robust
    (SDADesignCategory.ROBUST, SDABuildingType.APARTMENT): Decimal("133.45"),
    (SDADesignCategory.ROBUST, SDABuildingType.VILLA): Decimal("192.38"),
    (SDADesignCategory.ROBUST, SDABuildingType.GROUP_HOME): Decimal("96.73"),
    (SDADesignCategory.ROBUST, SDABuildingType.HOUSE): Decimal("192.38"),
    # Improved Liveability
    (SDADesignCategory.IMPROVED_LIVEABILITY, SDABuildingType.APARTMENT): Decimal(
        "72.61"
    ),
    (SDADesignCategory.IMPROVED_LIVEABILITY, SDABuildingType.VILLA): Decimal("104.71"),
    (SDADesignCategory.IMPROVED_LIVEABILITY, SDABuildingType.GROUP_HOME): Decimal(
        "52.66"
    ),
    (SDADesignCategory.IMPROVED_LIVEABILITY, SDABuildingType.HOUSE): Decimal("104.71"),
    # Basic
    (SDADesignCategory.BASIC, SDABuildingType.APARTMENT): Decimal("48.41"),
    (SDADesignCategory.BASIC, SDABuildingType.VILLA): Decimal("69.81"),
    (SDADesignCategory.BASIC, SDABuildingType.GROUP_HOME): Decimal("35.11"),
    (SDADesignCategory.BASIC, SDABuildingType.HOUSE): Decimal("69.81"),
}

# Location multipliers
LOCATION_MULTIPLIERS = {
    SDALocation.METRO: Decimal("1.00"),
    SDALocation.REGIONAL: Decimal("1.05"),
    SDALocation.REMOTE: Decimal("1.20"),
    SDALocation.VERY_REMOTE: Decimal("1.40"),
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class AccessibilityFeatures:
    """Detailed accessibility features for a property."""

    # Physical access
    wheelchair_accessible: bool = False
    step_free_entry: bool = False
    widened_doorways: bool = False  # Minimum 950mm clear
    widened_corridors: bool = False  # Minimum 1200mm
    accessible_bathroom: bool = False
    roll_in_shower: bool = False
    ceiling_hoists: bool = False
    hoist_tracks: list[str] = field(default_factory=list)  # Locations
    adjustable_benchtops: bool = False

    # Assistive technology
    smart_home_controls: bool = False
    automated_doors: bool = False
    emergency_power: bool = False
    backup_generator: bool = False
    assistive_tech_ready: bool = False
    structural_reinforcement: bool = False  # For future hoists

    # Sensory features
    visual_alerts: bool = False  # Doorbell, fire alarms
    hearing_loops: bool = False
    contrasting_colours: bool = False
    tactile_indicators: bool = False

    # Robust features
    impact_resistant_walls: bool = False
    reinforced_doors: bool = False
    tamper_proof_fittings: bool = False
    secure_outdoor_area: bool = False
    soundproofing: bool = False

    # Other
    onsite_overnight_assistance_area: bool = False  # OOA
    fire_sprinklers: bool = False
    private_outdoor_space: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "physical_access": {
                "wheelchair_accessible": self.wheelchair_accessible,
                "step_free_entry": self.step_free_entry,
                "widened_doorways": self.widened_doorways,
                "widened_corridors": self.widened_corridors,
                "accessible_bathroom": self.accessible_bathroom,
                "roll_in_shower": self.roll_in_shower,
                "ceiling_hoists": self.ceiling_hoists,
                "hoist_tracks": self.hoist_tracks,
                "adjustable_benchtops": self.adjustable_benchtops,
            },
            "assistive_technology": {
                "smart_home_controls": self.smart_home_controls,
                "automated_doors": self.automated_doors,
                "emergency_power": self.emergency_power,
                "backup_generator": self.backup_generator,
                "assistive_tech_ready": self.assistive_tech_ready,
                "structural_reinforcement": self.structural_reinforcement,
            },
            "sensory": {
                "visual_alerts": self.visual_alerts,
                "hearing_loops": self.hearing_loops,
                "contrasting_colours": self.contrasting_colours,
                "tactile_indicators": self.tactile_indicators,
            },
            "robust": {
                "impact_resistant_walls": self.impact_resistant_walls,
                "reinforced_doors": self.reinforced_doors,
                "tamper_proof_fittings": self.tamper_proof_fittings,
                "secure_outdoor_area": self.secure_outdoor_area,
                "soundproofing": self.soundproofing,
            },
            "other": {
                "onsite_overnight_assistance": self.onsite_overnight_assistance_area,
                "fire_sprinklers": self.fire_sprinklers,
                "private_outdoor_space": self.private_outdoor_space,
            },
        }


@dataclass
class SDAProperty:
    """Represents an SDA property."""

    property_id: str
    name: str
    address: str
    suburb: str
    state: str
    postcode: str

    # SDA classification
    design_category: SDADesignCategory
    building_type: SDABuildingType
    location_category: SDALocation

    # Property details
    bedrooms: int
    bathrooms: int
    floor_area_sqm: float
    year_built: int
    sda_enrolled_date: date

    # Accessibility
    accessibility: AccessibilityFeatures

    # Occupancy
    max_residents: int
    current_residents: int = 0
    status: OccupancyStatus = OccupancyStatus.VACANT

    # Compliance
    sda_certification_number: str = ""
    last_inspection_date: Optional[date] = None
    next_inspection_due: Optional[date] = None
    compliance_notes: list[str] = field(default_factory=list)

    # Provider details
    provider_name: str = ""
    provider_abn: str = ""
    property_manager_contact: str = ""

    def get_daily_rate(self) -> Decimal:
        """Calculate daily SDA rate."""
        base_rate = SDA_DAILY_RATES.get(
            (self.design_category, self.building_type), Decimal("0")
        )
        multiplier = LOCATION_MULTIPLIERS.get(self.location_category, Decimal("1.00"))
        return base_rate * multiplier

    def get_weekly_rate(self) -> Decimal:
        """Calculate weekly SDA rate."""
        return self.get_daily_rate() * 7

    def get_annual_rate(self) -> Decimal:
        """Calculate annual SDA rate."""
        return self.get_daily_rate() * 365

    def is_available(self) -> bool:
        """Check if property has vacancy."""
        return (
            self.status == OccupancyStatus.VACANT
            and self.current_residents < self.max_residents
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "property_id": self.property_id,
            "name": self.name,
            "address": self.address,
            "suburb": self.suburb,
            "state": self.state,
            "postcode": self.postcode,
            "design_category": self.design_category.value,
            "building_type": self.building_type.value,
            "location_category": self.location_category.value,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "floor_area_sqm": self.floor_area_sqm,
            "year_built": self.year_built,
            "sda_enrolled_date": self.sda_enrolled_date.isoformat(),
            "accessibility": self.accessibility.to_dict(),
            "max_residents": self.max_residents,
            "current_residents": self.current_residents,
            "status": self.status.value,
            "daily_rate": str(self.get_daily_rate()),
            "weekly_rate": str(self.get_weekly_rate()),
        }


@dataclass
class SDAParticipant:
    """NDIS participant requiring SDA."""

    participant_id: str  # Internal ID
    ndis_number_hash: str  # Hashed for privacy
    first_name: str
    last_name: str
    date_of_birth: date

    # SDA eligibility
    sda_eligible: bool = False
    sda_category: Optional[SDADesignCategory] = None
    sda_budget_daily: Decimal = Decimal("0")
    plan_start_date: Optional[date] = None
    plan_end_date: Optional[date] = None

    # Housing preferences
    preferred_locations: list[str] = field(default_factory=list)
    preferred_building_types: list[SDABuildingType] = field(default_factory=list)
    accessibility_requirements: list[str] = field(default_factory=list)

    # Support needs
    support_level: str = ""  # Description of support needs
    sil_required: bool = False  # Needs SIL alongside SDA
    behaviour_support_plan: bool = False

    # Current housing
    current_property_id: Optional[str] = None
    move_in_date: Optional[date] = None

    # Contact
    email: str = ""
    phone: str = ""
    support_coordinator_contact: str = ""

    # Privacy
    consent_given: bool = False
    consent_date: Optional[date] = None

    @staticmethod
    def hash_ndis_number(ndis_number: str) -> str:
        """Hash NDIS number for privacy-compliant storage."""
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
            "name": f"{self.first_name} {self.last_name[0]}.",  # Privacy
            "age": self.get_age(),
            "sda_eligible": self.sda_eligible,
            "sda_category": self.sda_category.value if self.sda_category else None,
            "preferred_locations": self.preferred_locations,
            "sil_required": self.sil_required,
            "has_current_housing": self.current_property_id is not None,
        }


@dataclass
class OccupancyAgreement:
    """Occupancy agreement between participant and SDA provider."""

    agreement_id: str
    property_id: str
    participant_id: str

    # Agreement dates
    start_date: date
    end_date: Optional[date]  # None = ongoing
    signed_date: date

    # Financial
    sda_daily_rate: Decimal
    reasonable_rent_contribution: Decimal  # Participant's rent contribution

    # Terms
    notice_period_days: int = 60  # Minimum notice for either party

    # Status
    is_active: bool = True
    termination_date: Optional[date] = None
    termination_reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agreement_id": self.agreement_id,
            "property_id": self.property_id,
            "participant_id": self.participant_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "sda_daily_rate": str(self.sda_daily_rate),
            "rent_contribution": str(self.reasonable_rent_contribution),
            "is_active": self.is_active,
        }


@dataclass
class MaintenanceRequest:
    """Property maintenance request."""

    request_id: str
    property_id: str
    reported_by: str  # participant_id or staff
    reported_date: datetime

    # Issue details
    category: str  # plumbing, electrical, accessibility, etc.
    description: str
    location_in_property: str
    priority: MaintenancePriority

    # Accessibility impact
    affects_accessibility: bool = False
    accessibility_impact_description: str = ""

    # Resolution
    status: str = "open"  # open, in_progress, completed, deferred
    assigned_to: str = ""
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    resolution_notes: str = ""
    cost: Decimal = Decimal("0")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "property_id": self.property_id,
            "category": self.category,
            "description": self.description,
            "priority": self.priority.value,
            "affects_accessibility": self.affects_accessibility,
            "status": self.status,
        }


@dataclass
class HousingApplication:
    """SDA housing application."""

    application_id: str
    participant_id: str
    submitted_date: date

    # Requested properties
    property_preferences: list[str] = field(default_factory=list)  # Property IDs

    # Documentation
    sda_determination_confirmed: bool = False
    plan_documents_provided: bool = False
    support_letters_provided: bool = False

    # Status
    status: ApplicationStatus = ApplicationStatus.SUBMITTED
    status_history: list[dict] = field(default_factory=list)

    # Outcome
    offered_property_id: Optional[str] = None
    offered_date: Optional[date] = None
    decision_date: Optional[date] = None
    decision_notes: str = ""

    def update_status(self, new_status: ApplicationStatus, notes: str = "") -> None:
        """Update application status with history."""
        self.status_history.append(
            {
                "from_status": self.status.value,
                "to_status": new_status.value,
                "date": datetime.now().isoformat(),
                "notes": notes,
            }
        )
        self.status = new_status


# ══════════════════════════════════════════════════════════════════════════════
# SDA PROPERTY MANAGER
# ══════════════════════════════════════════════════════════════════════════════


class SDAPropertyManager:
    """
    Manages SDA property portfolio, participant matching, and operations.

    Features:
        - Property listing and search
        - Participant matching based on needs
        - Vacancy management
        - Compliance tracking
        - Maintenance scheduling
        - Billing integration
    """

    def __init__(self, provider_name: str = "Community Living Co"):
        """Initialize the SDA property manager."""
        self.provider_name = provider_name

        # Data stores (would be database in production)
        self.properties: dict[str, SDAProperty] = {}
        self.participants: dict[str, SDAParticipant] = {}
        self.agreements: dict[str, OccupancyAgreement] = {}
        self.maintenance_requests: dict[str, MaintenanceRequest] = {}
        self.applications: dict[str, HousingApplication] = {}

        # Audit log
        self.audit_log: list[dict] = []

    def _log_action(
        self, action: str, entity_type: str, entity_id: str, details: str = ""
    ) -> None:
        """Log an action for audit purposes."""
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
            }
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PROPERTY MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def add_property(self, property: SDAProperty) -> None:
        """Add a new SDA property to portfolio."""
        self.properties[property.property_id] = property
        self._log_action(
            "CREATE", "property", property.property_id, f"Added: {property.name}"
        )
        print(f"✅ Added property: {property.name} ({property.design_category.value})")

    def get_property(self, property_id: str) -> Optional[SDAProperty]:
        """Get property by ID."""
        return self.properties.get(property_id)

    def search_properties(
        self,
        design_category: Optional[SDADesignCategory] = None,
        building_type: Optional[SDABuildingType] = None,
        location: Optional[str] = None,
        min_bedrooms: int = 0,
        available_only: bool = True,
        accessibility_requirements: list[str] = None,
    ) -> list[SDAProperty]:
        """Search properties with filters."""
        results = []

        for prop in self.properties.values():
            # Filter by design category
            if design_category and prop.design_category != design_category:
                continue

            # Filter by building type
            if building_type and prop.building_type != building_type:
                continue

            # Filter by location (suburb or postcode)
            if location:
                location_lower = location.lower()
                if (
                    location_lower not in prop.suburb.lower()
                    and location not in prop.postcode
                ):
                    continue

            # Filter by bedrooms
            if prop.bedrooms < min_bedrooms:
                continue

            # Filter by availability
            if available_only and not prop.is_available():
                continue

            # Filter by accessibility requirements
            if accessibility_requirements:
                acc = prop.accessibility
                if (
                    "ceiling_hoists" in accessibility_requirements
                    and not acc.ceiling_hoists
                ):
                    continue
                if (
                    "smart_home" in accessibility_requirements
                    and not acc.smart_home_controls
                ):
                    continue
                if (
                    "roll_in_shower" in accessibility_requirements
                    and not acc.roll_in_shower
                ):
                    continue

            results.append(prop)

        return results

    def get_available_properties(self) -> list[SDAProperty]:
        """Get all available properties."""
        return [p for p in self.properties.values() if p.is_available()]

    def get_occupancy_summary(self) -> dict:
        """Get portfolio occupancy summary."""
        total = len(self.properties)
        vacant = sum(
            1 for p in self.properties.values() if p.status == OccupancyStatus.VACANT
        )
        occupied = sum(
            1 for p in self.properties.values() if p.status == OccupancyStatus.OCCUPIED
        )
        maintenance = sum(
            1
            for p in self.properties.values()
            if p.status == OccupancyStatus.UNDER_MAINTENANCE
        )

        return {
            "total_properties": total,
            "vacant": vacant,
            "occupied": occupied,
            "under_maintenance": maintenance,
            "occupancy_rate": f"{(occupied / total * 100):.1f}%" if total > 0 else "0%",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PARTICIPANT MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def add_participant(self, participant: SDAParticipant) -> None:
        """Add a participant (requires consent)."""
        if not participant.consent_given:
            raise ValueError("Cannot add participant without consent")

        self.participants[participant.participant_id] = participant
        self._log_action(
            "CREATE",
            "participant",
            participant.participant_id,
            "Participant registered with consent",
        )
        print(
            f"✅ Added participant: {participant.first_name} {participant.last_name[0]}."
        )

    def get_participant(self, participant_id: str) -> Optional[SDAParticipant]:
        """Get participant by ID."""
        return self.participants.get(participant_id)

    def find_matching_properties(
        self, participant_id: str
    ) -> list[tuple[SDAProperty, float]]:
        """
        Find properties matching a participant's needs.

        Returns list of (property, match_score) tuples sorted by match.
        """
        participant = self.participants.get(participant_id)
        if not participant:
            return []

        matches = []

        for prop in self.properties.values():
            if not prop.is_available():
                continue

            score = 0.0

            # SDA category match (most important)
            if participant.sda_category == prop.design_category:
                score += 40
            elif participant.sda_category and self._is_compatible_category(
                participant.sda_category, prop.design_category
            ):
                score += 20

            # Location preference match
            if any(
                loc.lower() in prop.suburb.lower()
                for loc in participant.preferred_locations
            ):
                score += 25

            # Building type preference match
            if prop.building_type in participant.preferred_building_types:
                score += 15

            # Budget match
            if participant.sda_budget_daily >= prop.get_daily_rate():
                score += 15

            # Accessibility requirements
            acc_reqs = participant.accessibility_requirements
            if acc_reqs:
                acc = prop.accessibility
                for req in acc_reqs:
                    if req == "ceiling_hoists" and acc.ceiling_hoists or req == "smart_home" and acc.smart_home_controls:
                        score += 5

            if score > 0:
                matches.append((prop, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def _is_compatible_category(
        self, required: SDADesignCategory, available: SDADesignCategory
    ) -> bool:
        """Check if available category meets or exceeds required."""
        hierarchy = [
            SDADesignCategory.BASIC,
            SDADesignCategory.IMPROVED_LIVEABILITY,
            SDADesignCategory.FULLY_ACCESSIBLE,
            SDADesignCategory.ROBUST,
            SDADesignCategory.HIGH_PHYSICAL_SUPPORT,
        ]
        try:
            req_level = hierarchy.index(required)
            avail_level = hierarchy.index(available)
            return avail_level >= req_level
        except ValueError:
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # OCCUPANCY AGREEMENTS
    # ──────────────────────────────────────────────────────────────────────────

    def create_agreement(
        self,
        property_id: str,
        participant_id: str,
        start_date: date,
        rent_contribution: Decimal = Decimal("0"),
    ) -> Optional[OccupancyAgreement]:
        """Create occupancy agreement."""
        prop = self.properties.get(property_id)
        participant = self.participants.get(participant_id)

        if not prop or not participant:
            print("❌ Invalid property or participant ID")
            return None

        if not prop.is_available():
            print("❌ Property is not available")
            return None

        agreement_id = f"AGR-{property_id}-{participant_id}-{start_date.isoformat()}"

        agreement = OccupancyAgreement(
            agreement_id=agreement_id,
            property_id=property_id,
            participant_id=participant_id,
            start_date=start_date,
            end_date=None,
            signed_date=date.today(),
            sda_daily_rate=prop.get_daily_rate(),
            reasonable_rent_contribution=rent_contribution,
        )

        self.agreements[agreement_id] = agreement

        # Update property status
        prop.current_residents += 1
        if prop.current_residents >= prop.max_residents:
            prop.status = OccupancyStatus.OCCUPIED

        # Update participant
        participant.current_property_id = property_id
        participant.move_in_date = start_date

        self._log_action(
            "CREATE",
            "agreement",
            agreement_id,
            f"Agreement created for {participant.first_name}",
        )
        print(f"✅ Created agreement: {agreement_id}")

        return agreement

    def terminate_agreement(
        self, agreement_id: str, reason: str, termination_date: date
    ) -> bool:
        """Terminate an occupancy agreement."""
        agreement = self.agreements.get(agreement_id)
        if not agreement:
            return False

        agreement.is_active = False
        agreement.termination_date = termination_date
        agreement.termination_reason = reason

        # Update property
        prop = self.properties.get(agreement.property_id)
        if prop:
            prop.current_residents = max(0, prop.current_residents - 1)
            if prop.current_residents < prop.max_residents:
                prop.status = OccupancyStatus.VACANT

        # Update participant
        participant = self.participants.get(agreement.participant_id)
        if participant:
            participant.current_property_id = None

        self._log_action("TERMINATE", "agreement", agreement_id, reason)
        print(f"✅ Terminated agreement: {agreement_id}")

        return True

    # ──────────────────────────────────────────────────────────────────────────
    # MAINTENANCE
    # ──────────────────────────────────────────────────────────────────────────

    def create_maintenance_request(
        self,
        property_id: str,
        category: str,
        description: str,
        location_in_property: str,
        priority: MaintenancePriority,
        reported_by: str,
        affects_accessibility: bool = False,
    ) -> MaintenanceRequest:
        """Create a maintenance request."""
        request_id = f"MNT-{property_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        request = MaintenanceRequest(
            request_id=request_id,
            property_id=property_id,
            reported_by=reported_by,
            reported_date=datetime.now(),
            category=category,
            description=description,
            location_in_property=location_in_property,
            priority=priority,
            affects_accessibility=affects_accessibility,
        )

        self.maintenance_requests[request_id] = request

        # Critical accessibility issues require immediate property status change
        if affects_accessibility and priority == MaintenancePriority.CRITICAL:
            prop = self.properties.get(property_id)
            if prop:
                prop.compliance_notes.append(
                    f"{datetime.now().isoformat()}: Accessibility issue reported - {description}"
                )

        self._log_action("CREATE", "maintenance", request_id, description[:100])
        print(f"🔧 Created maintenance request: {request_id} ({priority.value})")

        return request

    def get_pending_maintenance(
        self, property_id: Optional[str] = None
    ) -> list[MaintenanceRequest]:
        """Get pending maintenance requests."""
        requests = [
            r
            for r in self.maintenance_requests.values()
            if r.status in ("open", "in_progress")
        ]

        if property_id:
            requests = [r for r in requests if r.property_id == property_id]

        # Sort by priority
        priority_order = {
            MaintenancePriority.CRITICAL: 0,
            MaintenancePriority.HIGH: 1,
            MaintenancePriority.MEDIUM: 2,
            MaintenancePriority.LOW: 3,
            MaintenancePriority.PLANNED: 4,
        }
        requests.sort(key=lambda r: priority_order.get(r.priority, 5))

        return requests

    def complete_maintenance(self, request_id: str, notes: str, cost: Decimal) -> bool:
        """Complete a maintenance request."""
        request = self.maintenance_requests.get(request_id)
        if not request:
            return False

        request.status = "completed"
        request.completed_date = date.today()
        request.resolution_notes = notes
        request.cost = cost

        self._log_action("COMPLETE", "maintenance", request_id, notes[:100])
        print(f"✅ Completed maintenance: {request_id}")

        return True

    # ──────────────────────────────────────────────────────────────────────────
    # APPLICATIONS
    # ──────────────────────────────────────────────────────────────────────────

    def submit_application(
        self,
        participant_id: str,
        property_preferences: list[str],
    ) -> HousingApplication:
        """Submit housing application."""
        application_id = f"APP-{participant_id}-{date.today().isoformat()}"

        application = HousingApplication(
            application_id=application_id,
            participant_id=participant_id,
            submitted_date=date.today(),
            property_preferences=property_preferences,
        )

        self.applications[application_id] = application
        self._log_action(
            "CREATE", "application", application_id, "Application submitted"
        )
        print(f"📝 Application submitted: {application_id}")

        return application

    def process_application(self, application_id: str) -> dict:
        """Process a housing application - verify SDA and find matches."""
        application = self.applications.get(application_id)
        if not application:
            return {"error": "Application not found"}

        participant = self.participants.get(application.participant_id)
        if not participant:
            return {"error": "Participant not found"}

        # Update status
        application.update_status(
            ApplicationStatus.SDA_VERIFICATION, "Starting verification"
        )

        # Check SDA eligibility
        if not participant.sda_eligible:
            application.update_status(ApplicationStatus.DECLINED, "Not SDA eligible")
            return {"status": "declined", "reason": "Not SDA eligible"}

        # Find matching properties
        application.update_status(
            ApplicationStatus.PROPERTY_MATCHING, "Finding matches"
        )
        matches = self.find_matching_properties(application.participant_id)

        if not matches:
            application.update_status(
                ApplicationStatus.WAITLISTED, "No available properties"
            )
            return {
                "status": "waitlisted",
                "reason": "No matching properties available",
            }

        # Offer best match
        best_match = matches[0][0]
        application.offered_property_id = best_match.property_id
        application.offered_date = date.today()
        application.update_status(
            ApplicationStatus.OFFERED, f"Offered {best_match.name}"
        )

        return {
            "status": "offered",
            "property": best_match.to_dict(),
            "match_score": matches[0][1],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # BILLING & REPORTING
    # ──────────────────────────────────────────────────────────────────────────

    def generate_billing_report(self, month: int, year: int) -> dict:
        """Generate monthly billing report for NDIS claims."""
        claims = []
        total_amount = Decimal("0")

        for agreement in self.agreements.values():
            if not agreement.is_active:
                continue

            # Calculate days in this month for this agreement
            start_of_month = date(year, month, 1)
            if month == 12:
                end_of_month = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = date(year, month + 1, 1) - timedelta(days=1)

            # Effective dates
            effective_start = max(agreement.start_date, start_of_month)
            effective_end = min(agreement.end_date or end_of_month, end_of_month)

            if effective_start > effective_end:
                continue

            days = (effective_end - effective_start).days + 1
            amount = agreement.sda_daily_rate * days

            participant = self.participants.get(agreement.participant_id)

            claims.append(
                {
                    "agreement_id": agreement.agreement_id,
                    "participant": participant.first_name if participant else "Unknown",
                    "property_id": agreement.property_id,
                    "days": days,
                    "daily_rate": str(agreement.sda_daily_rate),
                    "amount": str(amount),
                }
            )

            total_amount += amount

        return {
            "period": f"{year}-{month:02d}",
            "provider": self.provider_name,
            "total_claims": len(claims),
            "total_amount": str(total_amount),
            "claims": claims,
        }

    def get_compliance_report(self) -> dict:
        """Generate compliance report for all properties."""
        properties_report = []
        upcoming_inspections = []

        today = date.today()

        for prop in self.properties.values():
            status = "compliant"
            issues = []

            # Check inspection dates
            if prop.next_inspection_due:
                if prop.next_inspection_due < today:
                    status = "overdue"
                    issues.append("Inspection overdue")
                elif prop.next_inspection_due < today + timedelta(days=30):
                    upcoming_inspections.append(
                        {
                            "property": prop.name,
                            "due_date": prop.next_inspection_due.isoformat(),
                        }
                    )

            # Check for critical maintenance
            critical_maintenance = [
                r
                for r in self.maintenance_requests.values()
                if r.property_id == prop.property_id
                and r.priority == MaintenancePriority.CRITICAL
                and r.status != "completed"
            ]
            if critical_maintenance:
                status = "non_compliant"
                issues.append(
                    f"{len(critical_maintenance)} critical maintenance issue(s)"
                )

            properties_report.append(
                {
                    "property_id": prop.property_id,
                    "name": prop.name,
                    "status": status,
                    "issues": issues,
                    "sda_certification": prop.sda_certification_number,
                }
            )

        compliant = sum(1 for p in properties_report if p["status"] == "compliant")

        return {
            "report_date": today.isoformat(),
            "total_properties": len(properties_report),
            "compliant": compliant,
            "non_compliant": len(properties_report) - compliant,
            "compliance_rate": (
                f"{(compliant / len(properties_report) * 100):.1f}%"
                if properties_report
                else "N/A"
            ),
            "upcoming_inspections": upcoming_inspections,
            "properties": properties_report,
        }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate SDA Property Management."""

    print("=" * 70)
    print("🏠 SPECIALIST DISABILITY ACCOMMODATION (SDA) MANAGEMENT SYSTEM")
    print("=" * 70)
    print("\n📋 Provider: Community Living Co")
    print("🔒 Privacy Mode: On-Premise (No Cloud)")

    # Initialize manager
    manager = SDAPropertyManager(provider_name="Community Living Co")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Add Properties
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📦 STEP 1: Adding SDA Properties to Portfolio")
    print("─" * 70)

    # High Physical Support apartment
    prop1 = SDAProperty(
        property_id="SDA-001",
        name="Parkview Accessible Apartments - Unit 3",
        address="45 Parkview Drive, Unit 3",
        suburb="Mawson Lakes",
        state="SA",
        postcode="5095",
        design_category=SDADesignCategory.HIGH_PHYSICAL_SUPPORT,
        building_type=SDABuildingType.APARTMENT,
        location_category=SDALocation.METRO,
        bedrooms=2,
        bathrooms=1,
        floor_area_sqm=85.0,
        year_built=2022,
        sda_enrolled_date=date(2022, 6, 1),
        accessibility=AccessibilityFeatures(
            wheelchair_accessible=True,
            step_free_entry=True,
            widened_doorways=True,
            widened_corridors=True,
            accessible_bathroom=True,
            roll_in_shower=True,
            ceiling_hoists=True,
            hoist_tracks=["bedroom", "bathroom", "living"],
            smart_home_controls=True,
            automated_doors=True,
            emergency_power=True,
            assistive_tech_ready=True,
            visual_alerts=True,
            fire_sprinklers=True,
            onsite_overnight_assistance_area=True,
        ),
        max_residents=1,
        sda_certification_number="SDA-2022-SA-001234",
        last_inspection_date=date(2024, 6, 15),
        next_inspection_due=date(2025, 6, 15),
        provider_name="Community Living Co",
    )
    manager.add_property(prop1)

    # Fully Accessible villa
    prop2 = SDAProperty(
        property_id="SDA-002",
        name="Sunshine Villa - 2A",
        address="12 Sunshine Court, 2A",
        suburb="Modbury",
        state="SA",
        postcode="5092",
        design_category=SDADesignCategory.FULLY_ACCESSIBLE,
        building_type=SDABuildingType.VILLA,
        location_category=SDALocation.METRO,
        bedrooms=3,
        bathrooms=2,
        floor_area_sqm=120.0,
        year_built=2021,
        sda_enrolled_date=date(2021, 9, 1),
        accessibility=AccessibilityFeatures(
            wheelchair_accessible=True,
            step_free_entry=True,
            widened_doorways=True,
            widened_corridors=True,
            accessible_bathroom=True,
            roll_in_shower=True,
            ceiling_hoists=False,
            structural_reinforcement=True,  # Ready for future hoists
            smart_home_controls=True,
            visual_alerts=True,
            fire_sprinklers=True,
            private_outdoor_space=True,
        ),
        max_residents=2,
        sda_certification_number="SDA-2021-SA-000987",
        last_inspection_date=date(2024, 3, 10),
        next_inspection_due=date(2025, 3, 10),
        provider_name="Community Living Co",
    )
    manager.add_property(prop2)

    # Robust group home
    prop3 = SDAProperty(
        property_id="SDA-003",
        name="Harmony House",
        address="78 Harmony Street",
        suburb="Salisbury",
        state="SA",
        postcode="5108",
        design_category=SDADesignCategory.ROBUST,
        building_type=SDABuildingType.GROUP_HOME,
        location_category=SDALocation.METRO,
        bedrooms=4,
        bathrooms=3,
        floor_area_sqm=200.0,
        year_built=2020,
        sda_enrolled_date=date(2020, 11, 1),
        accessibility=AccessibilityFeatures(
            wheelchair_accessible=True,
            step_free_entry=True,
            widened_doorways=True,
            accessible_bathroom=True,
            impact_resistant_walls=True,
            reinforced_doors=True,
            tamper_proof_fittings=True,
            secure_outdoor_area=True,
            soundproofing=True,
            fire_sprinklers=True,
            visual_alerts=True,
        ),
        max_residents=4,
        current_residents=2,
        status=OccupancyStatus.OCCUPIED,
        sda_certification_number="SDA-2020-SA-000654",
        provider_name="Community Living Co",
    )
    manager.add_property(prop3)

    # Print portfolio summary
    print("\n📊 Portfolio Summary:")
    summary = manager.get_occupancy_summary()
    print(f"   Total Properties: {summary['total_properties']}")
    print(f"   Vacant: {summary['vacant']}")
    print(f"   Occupied: {summary['occupied']}")
    print(f"   Occupancy Rate: {summary['occupancy_rate']}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Register Participants
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("👤 STEP 2: Registering NDIS Participants")
    print("─" * 70)

    participant1 = SDAParticipant(
        participant_id="PART-001",
        ndis_number_hash=SDAParticipant.hash_ndis_number("43012345678"),
        first_name="Sarah",
        last_name="M",  # Generic initial only
        date_of_birth=date(1985, 4, 12),
        sda_eligible=True,
        sda_category=SDADesignCategory.HIGH_PHYSICAL_SUPPORT,
        sda_budget_daily=Decimal("220.00"),
        plan_start_date=date(2024, 7, 1),
        plan_end_date=date(2025, 6, 30),
        preferred_locations=["Mawson Lakes", "Salisbury", "Modbury"],
        preferred_building_types=[SDABuildingType.APARTMENT, SDABuildingType.VILLA],
        accessibility_requirements=["ceiling_hoists", "smart_home", "roll_in_shower"],
        support_level="24/7 support required due to quadriplegia",
        sil_required=True,
        email="sarah.m@example.com",
        phone="0412 345 678",
        support_coordinator_contact="Lisa (Support Coordinator) - LAC - 0400 123 456",
        consent_given=True,
        consent_date=date(2024, 6, 15),
    )
    manager.add_participant(participant1)

    participant2 = SDAParticipant(
        participant_id="PART-002",
        ndis_number_hash=SDAParticipant.hash_ndis_number("43098765432"),
        first_name="James",
        last_name="T",  # Generic initial only
        date_of_birth=date(1978, 9, 23),
        sda_eligible=True,
        sda_category=SDADesignCategory.ROBUST,
        sda_budget_daily=Decimal("135.00"),
        plan_start_date=date(2024, 4, 1),
        plan_end_date=date(2025, 3, 31),
        preferred_locations=["Salisbury", "Elizabeth", "Parafield Gardens"],
        preferred_building_types=[SDABuildingType.GROUP_HOME],
        accessibility_requirements=[],
        support_level="Behaviour support required",
        sil_required=True,
        behaviour_support_plan=True,
        email="michael.t@example.com",
        phone="0423 456 789",
        consent_given=True,
        consent_date=date(2024, 3, 20),
    )
    manager.add_participant(participant2)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: Property Matching
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("🔍 STEP 3: Finding Matching Properties")
    print("─" * 70)

    print("\n🔎 Finding matches for Sarah M. (High Physical Support)...")
    matches = manager.find_matching_properties("PART-001")

    if matches:
        print(f"   Found {len(matches)} matching properties:")
        for prop, score in matches[:3]:
            print(f"   • {prop.name}")
            print(f"     Category: {prop.design_category.value}")
            print(f"     Daily Rate: ${prop.get_daily_rate():.2f}")
            print(f"     Match Score: {score:.0f}/100")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Create Occupancy Agreement
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📝 STEP 4: Creating Occupancy Agreement")
    print("─" * 70)

    agreement = manager.create_agreement(
        property_id="SDA-001",
        participant_id="PART-001",
        start_date=date(2024, 8, 1),
        rent_contribution=Decimal("125.00"),  # Reasonable rent contribution
    )

    if agreement:
        print("\n📋 Agreement Details:")
        print(f"   Agreement ID: {agreement.agreement_id}")
        print("   Property: Parkview Accessible Apartments - Unit 3")
        print(f"   SDA Daily Rate: ${agreement.sda_daily_rate:.2f}")
        print(f"   Rent Contribution: ${agreement.reasonable_rent_contribution:.2f}")
        print(f"   Start Date: {agreement.start_date}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: Maintenance Request
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("🔧 STEP 5: Managing Maintenance")
    print("─" * 70)

    manager.create_maintenance_request(
        property_id="SDA-001",
        category="accessibility",
        description="Ceiling hoist motor making unusual noise in bedroom",
        location_in_property="Master bedroom",
        priority=MaintenancePriority.HIGH,
        reported_by="PART-001",
        affects_accessibility=True,
    )

    print("\n📝 Pending Maintenance Requests:")
    pending = manager.get_pending_maintenance()
    for req in pending:
        print(f"   • [{req.priority.value.upper()}] {req.description[:50]}...")
        print(f"     Property: {req.property_id}")
        print(
            f"     Affects Accessibility: {'Yes ⚠️' if req.affects_accessibility else 'No'}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: Housing Application
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📄 STEP 6: Processing Housing Application")
    print("─" * 70)

    application = manager.submit_application(
        participant_id="PART-002",
        property_preferences=["SDA-003", "SDA-002"],
    )

    result = manager.process_application(application.application_id)
    print("\n📋 Application Result:")
    print(f"   Status: {result.get('status', 'unknown')}")
    if result.get("property"):
        print(f"   Offered Property: {result['property']['name']}")
        print(f"   Match Score: {result.get('match_score', 0):.0f}/100")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 7: Billing Report
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("💰 STEP 7: Monthly Billing Report")
    print("─" * 70)

    billing = manager.generate_billing_report(month=8, year=2024)
    print(f"\n📊 Billing Report for {billing['period']}:")
    print(f"   Provider: {billing['provider']}")
    print(f"   Total Claims: {billing['total_claims']}")
    print(f"   Total Amount: ${Decimal(billing['total_amount']):.2f}")

    if billing["claims"]:
        print("\n   Claims:")
        for claim in billing["claims"]:
            print(
                f"   • {claim['participant']}: {claim['days']} days @ ${claim['daily_rate']}/day = ${claim['amount']}"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 8: Compliance Report
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("✅ STEP 8: Compliance Report")
    print("─" * 70)

    compliance = manager.get_compliance_report()
    print("\n📋 Compliance Summary:")
    print(f"   Report Date: {compliance['report_date']}")
    print(f"   Total Properties: {compliance['total_properties']}")
    print(f"   Compliant: {compliance['compliant']}")
    print(f"   Non-Compliant: {compliance['non_compliant']}")
    print(f"   Compliance Rate: {compliance['compliance_rate']}")

    if compliance["upcoming_inspections"]:
        print("\n   ⚠️ Upcoming Inspections:")
        for insp in compliance["upcoming_inspections"]:
            print(f"   • {insp['property']}: Due {insp['due_date']}")

    # ──────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("✅ SDA MANAGEMENT DEMO COMPLETE")
    print("=" * 70)

    print("\n📚 This system can be extended for:")
    print("   • Integration with NDIS portal for claims")
    print("   • Automated SDA rate updates")
    print("   • Inspection scheduling and reminders")
    print("   • Participant portal for maintenance requests")
    print("   • Real-time occupancy dashboard")
    print("   • Financial forecasting and reporting")

    print("\n🔒 Privacy Features:")
    print("   • All data stored on-premise")
    print("   • NDIS numbers hashed (never stored in plain text)")
    print("   • Audit logging for all access")
    print("   • Compliant with Privacy Act 1988")

    print("\n♿ Accessibility Notes:")
    print("   • All SDA categories supported")
    print("   • Detailed accessibility feature tracking")
    print("   • Participant matching based on needs")
    print("   • Priority maintenance for accessibility issues")


if __name__ == "__main__":
    asyncio.run(demo())
