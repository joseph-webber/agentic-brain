#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 62: NDIS Housing Search Assistant
==========================================

DISCLAIMER: This is a demonstration example only.
All names, addresses, and data are fictional.
This is not affiliated with any real NDIS provider.
Consult official NDIS guidelines for actual implementation.

AI-powered housing search for NDIS participants seeking SDA/SIL.

Overview:
    This assistant helps NDIS participants and their support networks
    find suitable Specialist Disability Accommodation (SDA) and/or
    Supported Independent Living (SIL) arrangements.

Features:
    - Property search by location and accessibility features
    - Accessibility requirement matching
    - Provider comparison and reviews
    - Virtual tour scheduling
    - Application assistance
    - Waitlist management
    - Move-in checklist generation
    - Plain language explanations of SDA/SIL

Accessibility First:
    - Screen reader compatible outputs
    - Plain language explanations
    - Step-by-step guidance
    - Audio description support
    - Multiple communication formats

Privacy Architecture:
    - On-premise for sensitive data
    - Participant control over data sharing
    - Consent management
    - Secure provider communication

Requirements:
    - Ollama running with llama3.1:8b
    - Optional: Neo4j for search indexing

Author: agentic-brain
License: MIT
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ══════════════════════════════════════════════════════════════════════════════


class SDACategory(Enum):
    """SDA Design Categories."""

    BASIC = "basic"
    IMPROVED_LIVEABILITY = "improved_liveability"
    FULLY_ACCESSIBLE = "fully_accessible"
    ROBUST = "robust"
    HIGH_PHYSICAL_SUPPORT = "high_physical_support"


class PropertyType(Enum):
    """Property types."""

    APARTMENT = "apartment"
    VILLA = "villa"
    TOWNHOUSE = "townhouse"
    GROUP_HOME = "group_home"
    HOUSE = "house"


class AccessibilityFeature(Enum):
    """Accessibility features for searching."""

    WHEELCHAIR_ACCESS = "wheelchair_access"
    CEILING_HOISTS = "ceiling_hoists"
    ROLL_IN_SHOWER = "roll_in_shower"
    SMART_HOME = "smart_home"
    VISUAL_ALERTS = "visual_alerts"
    HEARING_LOOP = "hearing_loop"
    ADJUSTABLE_BENCHTOPS = "adjustable_benchtops"
    EMERGENCY_POWER = "emergency_power"
    SECURE_OUTDOOR = "secure_outdoor"
    SOUNDPROOFING = "soundproofing"


class SearchStatus(Enum):
    """Housing search status."""

    EXPLORING = "exploring"  # Just looking
    ACTIVELY_SEARCHING = "actively_searching"
    APPLYING = "applying"
    WAITLISTED = "waitlisted"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    MOVED_IN = "moved_in"


class ApplicationStatus(Enum):
    """Application status."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ADDITIONAL_INFO_REQUESTED = "additional_info_requested"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class TourType(Enum):
    """Types of property tours."""

    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"
    VIRTUAL_360 = "virtual_360"
    PHOTO_WALKTHROUGH = "photo_walkthrough"


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class SearcherProfile:
    """Profile for someone searching for NDIS housing."""

    searcher_id: str

    # Personal info (privacy-first)
    first_name: str
    last_name_initial: str  # Only store initial
    preferred_name: str = ""

    # NDIS status
    has_ndis_plan: bool = False
    sda_eligible: bool = False
    sda_category: Optional[SDACategory] = None
    sda_daily_budget: Decimal = Decimal("0")
    sil_in_plan: bool = False
    plan_end_date: Optional[date] = None

    # Search preferences
    preferred_locations: list[str] = field(default_factory=list)
    preferred_property_types: list[PropertyType] = field(default_factory=list)
    max_rent_contribution: Decimal = Decimal("0")  # Weekly
    required_features: list[AccessibilityFeature] = field(default_factory=list)
    preferred_features: list[AccessibilityFeature] = field(default_factory=list)

    # Living preferences
    prefer_living_alone: bool = False
    open_to_shared_living: bool = True
    pet_friendly_needed: bool = False
    near_public_transport: bool = False
    near_family: str = ""  # Suburb/area

    # Support needs (high level - for matching only)
    needs_24_7_support: bool = False
    needs_overnight_support: bool = False
    has_behaviour_support_needs: bool = False
    mobility_level: str = ""  # ambulant, wheelchair, motorised

    # Communication preferences
    preferred_contact_method: str = "email"  # email, phone, text
    accessibility_needs: list[str] = field(default_factory=list)
    support_person_contact: str = ""  # For communications

    # Search status
    search_status: SearchStatus = SearchStatus.EXPLORING
    search_start_date: date = field(default_factory=date.today)

    # Consent
    consent_to_share_with_providers: bool = False
    consent_date: Optional[date] = None

    def get_display_name(self) -> str:
        """Get privacy-respecting display name."""
        name = self.preferred_name or self.first_name
        return f"{name} {self.last_name_initial}."

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "searcher_id": self.searcher_id,
            "name": self.get_display_name(),
            "sda_eligible": self.sda_eligible,
            "sda_category": self.sda_category.value if self.sda_category else None,
            "preferred_locations": self.preferred_locations,
            "search_status": self.search_status.value,
        }


@dataclass
class PropertyListing:
    """A property listing for search."""

    property_id: str
    provider_id: str

    # Location
    suburb: str
    state: str
    postcode: str
    region: str  # e.g., "Northern Adelaide", "Inner West Sydney"

    # Property details
    name: str
    property_type: PropertyType
    sda_category: SDACategory
    bedrooms: int
    bathrooms: int

    # Availability
    available_from: Optional[date]
    current_vacancies: int = 0
    total_capacity: int = 1
    has_waitlist: bool = False

    # Features
    accessibility_features: list[AccessibilityFeature] = field(default_factory=list)
    other_features: list[str] = field(default_factory=list)

    # Pricing
    sda_daily_rate: Decimal = Decimal("0")
    estimated_rent_contribution: Decimal = Decimal("0")  # Weekly

    # SIL information
    sil_available: bool = False
    sil_provider_same: bool = False
    sil_provider_name: str = ""

    # Media
    has_virtual_tour: bool = False
    has_photos: bool = True
    has_video: bool = False
    photos_alt_text_available: bool = True  # Accessibility

    # Description
    description: str = ""
    accessibility_description: str = ""  # Plain language accessibility info

    # Provider info
    provider_name: str = ""
    provider_rating: float = 0.0  # Out of 5
    provider_reviews_count: int = 0

    # Transport
    public_transport_distance: str = ""  # e.g., "200m to bus stop"
    nearest_shopping: str = ""
    nearest_medical: str = ""

    # Listing status
    is_active: bool = True
    last_updated: date = field(default_factory=date.today)

    def matches_requirements(self, profile: SearcherProfile) -> dict:
        """Check how well property matches searcher requirements."""
        score = 0
        max_score = 0
        matches = []
        missing = []

        # SDA category match (required)
        max_score += 30
        if profile.sda_category:
            if self.sda_category == profile.sda_category:
                score += 30
                matches.append("SDA category matches exactly")
            elif self._is_higher_category(self.sda_category, profile.sda_category):
                score += 20
                matches.append("SDA category exceeds requirements")
            else:
                missing.append(f"Requires {profile.sda_category.value} SDA")
        else:
            score += 30  # No requirement

        # Location match
        max_score += 20
        if profile.preferred_locations:
            location_match = any(
                loc.lower() in self.suburb.lower() or loc.lower() in self.region.lower()
                for loc in profile.preferred_locations
            )
            if location_match:
                score += 20
                matches.append(f"Location in {self.suburb}")
            else:
                missing.append("Not in preferred locations")
        else:
            score += 20

        # Property type match
        max_score += 10
        if profile.preferred_property_types:
            if self.property_type in profile.preferred_property_types:
                score += 10
                matches.append(f"{self.property_type.value} as preferred")
        else:
            score += 10

        # Required features
        for feature in profile.required_features:
            max_score += 10
            if feature in self.accessibility_features:
                score += 10
                matches.append(f"Has {feature.value}")
            else:
                missing.append(f"Missing required: {feature.value}")

        # Preferred features (partial credit)
        for feature in profile.preferred_features:
            max_score += 5
            if feature in self.accessibility_features:
                score += 5
                matches.append(f"Has preferred: {feature.value}")

        # Budget match
        max_score += 15
        if profile.sda_daily_budget > 0:
            if self.sda_daily_rate <= profile.sda_daily_budget:
                score += 15
                matches.append("Within SDA budget")
            else:
                missing.append(f"SDA rate ${self.sda_daily_rate}/day exceeds budget")
        else:
            score += 15

        # Rent contribution
        max_score += 10
        if profile.max_rent_contribution > 0:
            if self.estimated_rent_contribution <= profile.max_rent_contribution:
                score += 10
                matches.append("Rent contribution affordable")
            else:
                missing.append(
                    f"Rent ${self.estimated_rent_contribution}/week exceeds budget"
                )
        else:
            score += 10

        # Living preference
        max_score += 5
        if profile.prefer_living_alone:
            if self.total_capacity == 1:
                score += 5
                matches.append("Single occupancy")
            else:
                missing.append("Shared living, prefers alone")
        elif profile.open_to_shared_living:
            score += 5

        percentage = (score / max_score * 100) if max_score > 0 else 0

        return {
            "score": score,
            "max_score": max_score,
            "percentage": round(percentage, 1),
            "matches": matches,
            "missing": missing,
            "is_suitable": len(missing) == 0
            or (percentage >= 70 and not any("required" in m.lower() for m in missing)),
        }

    def _is_higher_category(
        self, available: SDACategory, required: SDACategory
    ) -> bool:
        """Check if available category exceeds required."""
        hierarchy = [
            SDACategory.BASIC,
            SDACategory.IMPROVED_LIVEABILITY,
            SDACategory.FULLY_ACCESSIBLE,
            SDACategory.ROBUST,
            SDACategory.HIGH_PHYSICAL_SUPPORT,
        ]
        try:
            return hierarchy.index(available) > hierarchy.index(required)
        except ValueError:
            return False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "property_id": self.property_id,
            "name": self.name,
            "suburb": self.suburb,
            "state": self.state,
            "property_type": self.property_type.value,
            "sda_category": self.sda_category.value,
            "bedrooms": self.bedrooms,
            "available_from": (
                self.available_from.isoformat() if self.available_from else None
            ),
            "sda_daily_rate": str(self.sda_daily_rate),
            "provider_name": self.provider_name,
            "provider_rating": self.provider_rating,
            "has_virtual_tour": self.has_virtual_tour,
        }

    def to_accessible_summary(self) -> str:
        """Generate screen-reader friendly summary."""
        lines = [
            f"Property: {self.name}",
            f"Location: {self.suburb}, {self.state} {self.postcode}",
            f"Type: {self.property_type.value.replace('_', ' ')}",
            f"SDA Category: {self.sda_category.value.replace('_', ' ')}",
            f"Bedrooms: {self.bedrooms}",
            f"Bathrooms: {self.bathrooms}",
            f"SDA Rate: {self.sda_daily_rate} dollars per day",
            f"Estimated Rent Contribution: {self.estimated_rent_contribution} dollars per week",
            f"Provider: {self.provider_name}",
            f"Rating: {self.provider_rating} out of 5 stars from {self.provider_reviews_count} reviews",
        ]

        if self.available_from:
            lines.append(f"Available from: {self.available_from.strftime('%d %B %Y')}")
        elif self.current_vacancies > 0:
            lines.append("Available now")
        else:
            lines.append("Currently occupied - may have waitlist")

        if self.accessibility_features:
            features = ", ".join(
                f.value.replace("_", " ") for f in self.accessibility_features
            )
            lines.append(f"Accessibility features: {features}")

        if self.public_transport_distance:
            lines.append(f"Public transport: {self.public_transport_distance}")

        return "\n".join(lines)


@dataclass
class Provider:
    """SDA/SIL provider information."""

    provider_id: str
    name: str
    abn: str

    # Registration
    ndis_registered: bool = True
    ndis_registration_number: str = ""
    sda_registered: bool = False
    sil_registered: bool = False

    # Contact
    phone: str = ""
    email: str = ""
    website: str = ""

    # Coverage
    service_regions: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)

    # Ratings
    overall_rating: float = 0.0
    total_reviews: int = 0
    response_time_rating: float = 0.0
    accessibility_rating: float = 0.0

    # Properties
    total_properties: int = 0
    current_vacancies: int = 0

    # Accreditation
    accreditations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "ndis_registered": self.ndis_registered,
            "sda_registered": self.sda_registered,
            "sil_registered": self.sil_registered,
            "overall_rating": self.overall_rating,
            "total_reviews": self.total_reviews,
            "service_regions": self.service_regions,
        }


@dataclass
class HousingApplication:
    """Application for NDIS housing."""

    application_id: str
    searcher_id: str
    property_id: str
    provider_id: str

    # Dates
    created_date: date
    submitted_date: Optional[date] = None
    last_updated: datetime = field(default_factory=datetime.now)

    # Status
    status: ApplicationStatus = ApplicationStatus.DRAFT
    status_history: list[dict] = field(default_factory=list)

    # Documents
    documents_required: list[str] = field(default_factory=list)
    documents_provided: list[str] = field(default_factory=list)
    documents_pending: list[str] = field(default_factory=list)

    # SDA verification
    sda_determination_attached: bool = False
    plan_copy_attached: bool = False

    # Provider response
    provider_notes: str = ""
    offer_date: Optional[date] = None
    offer_expires: Optional[date] = None

    # Outcome
    outcome_date: Optional[date] = None
    outcome_notes: str = ""

    def update_status(self, new_status: ApplicationStatus, notes: str = "") -> None:
        """Update status with history."""
        self.status_history.append(
            {
                "from": self.status.value,
                "to": new_status.value,
                "date": datetime.now().isoformat(),
                "notes": notes,
            }
        )
        self.status = new_status
        self.last_updated = datetime.now()

    def get_pending_documents(self) -> list[str]:
        """Get list of documents still needed."""
        return [d for d in self.documents_required if d not in self.documents_provided]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "application_id": self.application_id,
            "property_id": self.property_id,
            "status": self.status.value,
            "submitted_date": (
                self.submitted_date.isoformat() if self.submitted_date else None
            ),
            "documents_pending": self.get_pending_documents(),
        }


@dataclass
class TourBooking:
    """Property tour booking."""

    booking_id: str
    searcher_id: str
    property_id: str
    provider_id: str

    # Tour details
    tour_type: TourType
    scheduled_datetime: datetime
    duration_minutes: int = 30

    # Accessibility requirements
    accessibility_requirements: list[str] = field(default_factory=list)
    interpreter_needed: bool = False
    interpreter_language: str = ""
    support_person_attending: bool = False

    # Status
    confirmed: bool = False
    completed: bool = False
    cancelled: bool = False
    cancellation_reason: str = ""

    # For virtual tours
    video_link: str = ""
    virtual_tour_url: str = ""

    # Notes
    participant_notes: str = ""
    provider_notes: str = ""
    post_tour_feedback: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "booking_id": self.booking_id,
            "property_id": self.property_id,
            "tour_type": self.tour_type.value,
            "datetime": self.scheduled_datetime.isoformat(),
            "confirmed": self.confirmed,
        }


@dataclass
class WaitlistEntry:
    """Waitlist entry for a property."""

    entry_id: str
    searcher_id: str
    property_id: str
    provider_id: str

    # Dates
    joined_date: date
    estimated_wait: str = ""  # e.g., "3-6 months"

    # Position
    position: int = 0

    # Status
    is_active: bool = True
    removed_date: Optional[date] = None
    removed_reason: str = ""

    # Notifications
    last_update_date: Optional[date] = None
    updates_received: int = 0


@dataclass
class MoveInChecklist:
    """Checklist for moving into NDIS housing."""

    checklist_id: str
    searcher_id: str
    property_id: str

    # Pre-move tasks
    pre_move_tasks: list[dict] = field(default_factory=list)
    # Move day tasks
    move_day_tasks: list[dict] = field(default_factory=list)
    # First week tasks
    first_week_tasks: list[dict] = field(default_factory=list)

    # Progress
    tasks_completed: int = 0
    total_tasks: int = 0

    # Important contacts
    contacts: list[dict] = field(default_factory=list)

    # Move date
    planned_move_date: Optional[date] = None
    actual_move_date: Optional[date] = None

    def get_progress_percentage(self) -> int:
        """Get completion percentage."""
        if self.total_tasks == 0:
            return 0
        return int((self.tasks_completed / self.total_tasks) * 100)


# ══════════════════════════════════════════════════════════════════════════════
# HOUSING SEARCH ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════


class NDISHousingSearchAssistant:
    """
    AI-powered assistant for NDIS housing search.

    Features:
        - Property search with accessibility matching
        - Provider comparison
        - Tour scheduling
        - Application assistance
        - Waitlist management
        - Move-in support
    """

    def __init__(self):
        """Initialize the housing search assistant."""
        # Data stores
        self.searchers: dict[str, SearcherProfile] = {}
        self.properties: dict[str, PropertyListing] = {}
        self.providers: dict[str, Provider] = {}
        self.applications: dict[str, HousingApplication] = {}
        self.tour_bookings: dict[str, TourBooking] = {}
        self.waitlist_entries: dict[str, WaitlistEntry] = {}
        self.checklists: dict[str, MoveInChecklist] = {}

        # Saved searches
        self.saved_searches: dict[str, list[dict]] = {}  # searcher_id: [search_params]

        # Favourites
        self.favourites: dict[str, list[str]] = {}  # searcher_id: [property_ids]

    # ──────────────────────────────────────────────────────────────────────────
    # SEARCHER PROFILE
    # ──────────────────────────────────────────────────────────────────────────

    def create_profile(self, profile: SearcherProfile) -> None:
        """Create a searcher profile."""
        self.searchers[profile.searcher_id] = profile
        self.favourites[profile.searcher_id] = []
        self.saved_searches[profile.searcher_id] = []
        print(f"✅ Profile created for {profile.get_display_name()}")

    def update_profile(self, searcher_id: str, **updates) -> bool:
        """Update profile fields."""
        profile = self.searchers.get(searcher_id)
        if not profile:
            return False

        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        return True

    # ──────────────────────────────────────────────────────────────────────────
    # PROPERTY SEARCH
    # ──────────────────────────────────────────────────────────────────────────

    def search_properties(
        self,
        searcher_id: Optional[str] = None,
        locations: list[str] = None,
        sda_categories: list[SDACategory] = None,
        property_types: list[PropertyType] = None,
        required_features: list[AccessibilityFeature] = None,
        max_rent: Decimal = None,
        available_only: bool = True,
        include_waitlist: bool = True,
    ) -> list[tuple[PropertyListing, dict]]:
        """
        Search for properties.

        Returns list of (property, match_info) tuples.
        """
        results = []
        profile = self.searchers.get(searcher_id) if searcher_id else None

        for prop in self.properties.values():
            if not prop.is_active:
                continue

            # Availability filter
            if available_only:
                if prop.current_vacancies == 0 and not include_waitlist:
                    continue

            # Location filter
            if locations:
                location_match = any(
                    loc.lower() in prop.suburb.lower()
                    or loc.lower() in prop.region.lower()
                    or loc.lower() in prop.postcode
                    for loc in locations
                )
                if not location_match:
                    continue

            # SDA category filter
            if sda_categories:
                if prop.sda_category not in sda_categories:
                    continue

            # Property type filter
            if property_types:
                if prop.property_type not in property_types:
                    continue

            # Required features filter
            if required_features:
                if not all(f in prop.accessibility_features for f in required_features):
                    continue

            # Rent filter
            if max_rent and prop.estimated_rent_contribution > max_rent:
                continue

            # Calculate match score if we have a profile
            if profile:
                match_info = prop.matches_requirements(profile)
            else:
                match_info = {
                    "score": 0,
                    "percentage": 0,
                    "matches": [],
                    "missing": [],
                    "is_suitable": True,
                }

            results.append((prop, match_info))

        # Sort by match percentage if we have scores
        if profile:
            results.sort(key=lambda x: x[1]["percentage"], reverse=True)
        else:
            # Sort by availability then rating
            results.sort(
                key=lambda x: (x[0].current_vacancies > 0, x[0].provider_rating),
                reverse=True,
            )

        return results

    def save_search(self, searcher_id: str, search_params: dict, name: str = "") -> str:
        """Save a search for later."""
        if searcher_id not in self.saved_searches:
            self.saved_searches[searcher_id] = []

        search_id = f"SEARCH-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.saved_searches[searcher_id].append(
            {
                "search_id": search_id,
                "name": name or f"Search {len(self.saved_searches[searcher_id]) + 1}",
                "params": search_params,
                "saved_date": datetime.now().isoformat(),
            }
        )

        return search_id

    def add_favourite(self, searcher_id: str, property_id: str) -> bool:
        """Add property to favourites."""
        if searcher_id not in self.favourites:
            self.favourites[searcher_id] = []

        if property_id not in self.favourites[searcher_id]:
            self.favourites[searcher_id].append(property_id)
            return True
        return False

    def get_favourites(self, searcher_id: str) -> list[PropertyListing]:
        """Get favourite properties."""
        fav_ids = self.favourites.get(searcher_id, [])
        return [self.properties[pid] for pid in fav_ids if pid in self.properties]

    # ──────────────────────────────────────────────────────────────────────────
    # PROVIDER COMPARISON
    # ──────────────────────────────────────────────────────────────────────────

    def compare_providers(self, provider_ids: list[str]) -> dict:
        """Compare multiple providers."""
        providers = [
            self.providers[pid] for pid in provider_ids if pid in self.providers
        ]

        if not providers:
            return {"error": "No valid providers found"}

        comparison = {
            "providers": [],
            "summary": {
                "highest_rated": None,
                "most_vacancies": None,
                "best_accessibility": None,
            },
        }

        highest_rating = 0
        most_vacancies = 0
        best_accessibility = 0

        for provider in providers:
            info = {
                "name": provider.name,
                "ndis_registered": provider.ndis_registered,
                "sda_registered": provider.sda_registered,
                "sil_registered": provider.sil_registered,
                "overall_rating": provider.overall_rating,
                "accessibility_rating": provider.accessibility_rating,
                "response_time_rating": provider.response_time_rating,
                "total_reviews": provider.total_reviews,
                "total_properties": provider.total_properties,
                "current_vacancies": provider.current_vacancies,
                "service_regions": provider.service_regions,
            }
            comparison["providers"].append(info)

            if provider.overall_rating > highest_rating:
                highest_rating = provider.overall_rating
                comparison["summary"]["highest_rated"] = provider.name

            if provider.current_vacancies > most_vacancies:
                most_vacancies = provider.current_vacancies
                comparison["summary"]["most_vacancies"] = provider.name

            if provider.accessibility_rating > best_accessibility:
                best_accessibility = provider.accessibility_rating
                comparison["summary"]["best_accessibility"] = provider.name

        return comparison

    # ──────────────────────────────────────────────────────────────────────────
    # TOUR SCHEDULING
    # ──────────────────────────────────────────────────────────────────────────

    def schedule_tour(
        self,
        searcher_id: str,
        property_id: str,
        tour_type: TourType,
        preferred_datetime: datetime,
        accessibility_requirements: list[str] = None,
        support_person_attending: bool = False,
    ) -> TourBooking:
        """Schedule a property tour."""
        prop = self.properties.get(property_id)
        if not prop:
            raise ValueError("Property not found")

        booking_id = f"TOUR-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        booking = TourBooking(
            booking_id=booking_id,
            searcher_id=searcher_id,
            property_id=property_id,
            provider_id=prop.provider_id,
            tour_type=tour_type,
            scheduled_datetime=preferred_datetime,
            accessibility_requirements=accessibility_requirements or [],
            support_person_attending=support_person_attending,
        )

        # Set virtual tour details if applicable
        if tour_type == TourType.VIRTUAL_360 and prop.has_virtual_tour:
            booking.virtual_tour_url = f"https://tours.example.com/{property_id}"

        self.tour_bookings[booking_id] = booking
        print(f"📅 Tour scheduled: {booking_id}")
        print(f"   Property: {prop.name}")
        print(f"   Type: {tour_type.value}")
        print(f"   Date/Time: {preferred_datetime.strftime('%d %B %Y at %I:%M %p')}")

        return booking

    def confirm_tour(self, booking_id: str, video_link: str = "") -> bool:
        """Provider confirms a tour booking."""
        booking = self.tour_bookings.get(booking_id)
        if not booking:
            return False

        booking.confirmed = True
        if video_link:
            booking.video_link = video_link

        print(f"✅ Tour confirmed: {booking_id}")
        return True

    def complete_tour(self, booking_id: str, feedback: str = "") -> bool:
        """Mark tour as completed with optional feedback."""
        booking = self.tour_bookings.get(booking_id)
        if not booking:
            return False

        booking.completed = True
        booking.post_tour_feedback = feedback

        return True

    def get_available_tour_times(
        self, property_id: str, week_start: date
    ) -> list[datetime]:
        """Get available tour times for a property."""
        # In production, this would check provider availability
        # For demo, generate some available slots
        times = []
        for day_offset in range(5):  # Monday to Friday
            tour_date = week_start + timedelta(days=day_offset)
            for hour in [10, 14]:  # 10am and 2pm slots
                times.append(datetime.combine(tour_date, time(hour, 0)))
        return times

    # ──────────────────────────────────────────────────────────────────────────
    # APPLICATION MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def create_application(
        self, searcher_id: str, property_id: str
    ) -> HousingApplication:
        """Start a housing application."""
        prop = self.properties.get(property_id)
        searcher = self.searchers.get(searcher_id)

        if not prop or not searcher:
            raise ValueError("Invalid property or searcher")

        application_id = f"APP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Determine required documents
        required_docs = [
            "NDIS Plan Summary",
            "Photo ID",
            "Proof of SDA Eligibility",
        ]

        if searcher.sil_in_plan:
            required_docs.append("SIL Quote")

        application = HousingApplication(
            application_id=application_id,
            searcher_id=searcher_id,
            property_id=property_id,
            provider_id=prop.provider_id,
            created_date=date.today(),
            documents_required=required_docs,
        )

        self.applications[application_id] = application

        # Update searcher status
        searcher.search_status = SearchStatus.APPLYING

        print(f"📝 Application started: {application_id}")
        print(f"   Property: {prop.name}")
        print(f"   Documents required: {len(required_docs)}")

        return application

    def add_document(self, application_id: str, document_name: str) -> bool:
        """Add a document to application."""
        application = self.applications.get(application_id)
        if not application:
            return False

        if document_name not in application.documents_provided:
            application.documents_provided.append(document_name)
            application.last_updated = datetime.now()
            print(f"📄 Document added: {document_name}")

        return True

    def submit_application(self, application_id: str) -> dict:
        """Submit a completed application."""
        application = self.applications.get(application_id)
        if not application:
            return {"success": False, "error": "Application not found"}

        # Check all documents provided
        pending = application.get_pending_documents()
        if pending:
            return {
                "success": False,
                "error": "Missing documents",
                "pending_documents": pending,
            }

        application.submitted_date = date.today()
        application.update_status(ApplicationStatus.SUBMITTED, "Application submitted")

        return {
            "success": True,
            "application_id": application_id,
            "submitted_date": application.submitted_date.isoformat(),
            "message": "Your application has been submitted successfully.",
        }

    def get_application_status(self, application_id: str) -> dict:
        """Get detailed application status."""
        application = self.applications.get(application_id)
        if not application:
            return {"error": "Application not found"}

        prop = self.properties.get(application.property_id)

        status_info = {
            "application_id": application_id,
            "property_name": prop.name if prop else "Unknown",
            "status": application.status.value,
            "submitted_date": (
                application.submitted_date.isoformat()
                if application.submitted_date
                else None
            ),
            "last_updated": application.last_updated.isoformat(),
            "pending_documents": application.get_pending_documents(),
            "history": application.status_history,
        }

        # Add status-specific info
        if application.status == ApplicationStatus.OFFERED:
            status_info["offer_expires"] = (
                application.offer_expires.isoformat()
                if application.offer_expires
                else None
            )

        return status_info

    # ──────────────────────────────────────────────────────────────────────────
    # WAITLIST MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def join_waitlist(self, searcher_id: str, property_id: str) -> WaitlistEntry:
        """Join waitlist for a property."""
        prop = self.properties.get(property_id)
        if not prop:
            raise ValueError("Property not found")

        # Check if already on waitlist
        existing = [
            e
            for e in self.waitlist_entries.values()
            if e.searcher_id == searcher_id
            and e.property_id == property_id
            and e.is_active
        ]
        if existing:
            return existing[0]

        # Count current position
        current_entries = [
            e
            for e in self.waitlist_entries.values()
            if e.property_id == property_id and e.is_active
        ]
        position = len(current_entries) + 1

        entry_id = f"WL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        entry = WaitlistEntry(
            entry_id=entry_id,
            searcher_id=searcher_id,
            property_id=property_id,
            provider_id=prop.provider_id,
            joined_date=date.today(),
            position=position,
            estimated_wait=self._estimate_wait_time(position),
        )

        self.waitlist_entries[entry_id] = entry

        # Update searcher status
        searcher = self.searchers.get(searcher_id)
        if searcher:
            searcher.search_status = SearchStatus.WAITLISTED

        print(f"📋 Joined waitlist: {entry_id}")
        print(f"   Property: {prop.name}")
        print(f"   Position: {position}")
        print(f"   Estimated wait: {entry.estimated_wait}")

        return entry

    def _estimate_wait_time(self, position: int) -> str:
        """Estimate wait time based on position."""
        if position <= 2:
            return "1-2 months"
        elif position <= 5:
            return "3-6 months"
        elif position <= 10:
            return "6-12 months"
        else:
            return "12+ months"

    def get_waitlist_status(self, searcher_id: str) -> list[dict]:
        """Get all waitlist entries for a searcher."""
        entries = [
            e
            for e in self.waitlist_entries.values()
            if e.searcher_id == searcher_id and e.is_active
        ]

        results = []
        for entry in entries:
            prop = self.properties.get(entry.property_id)
            results.append(
                {
                    "entry_id": entry.entry_id,
                    "property_name": prop.name if prop else "Unknown",
                    "position": entry.position,
                    "estimated_wait": entry.estimated_wait,
                    "joined_date": entry.joined_date.isoformat(),
                }
            )

        return results

    def leave_waitlist(self, entry_id: str, reason: str = "") -> bool:
        """Leave a waitlist."""
        entry = self.waitlist_entries.get(entry_id)
        if not entry:
            return False

        entry.is_active = False
        entry.removed_date = date.today()
        entry.removed_reason = reason or "Withdrawn by participant"

        return True

    # ──────────────────────────────────────────────────────────────────────────
    # MOVE-IN SUPPORT
    # ──────────────────────────────────────────────────────────────────────────

    def create_move_in_checklist(
        self, searcher_id: str, property_id: str, move_date: date
    ) -> MoveInChecklist:
        """Generate a move-in checklist."""
        prop = self.properties.get(property_id)
        if not prop:
            raise ValueError("Property not found")

        checklist_id = f"CHECK-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Pre-move tasks
        pre_move = [
            {
                "task": "Sign occupancy agreement",
                "completed": False,
                "due_date": (move_date - timedelta(days=14)).isoformat(),
            },
            {
                "task": "Set up electricity account",
                "completed": False,
                "due_date": (move_date - timedelta(days=7)).isoformat(),
            },
            {
                "task": "Set up internet connection",
                "completed": False,
                "due_date": (move_date - timedelta(days=7)).isoformat(),
            },
            {
                "task": "Arrange removalist or moving help",
                "completed": False,
                "due_date": (move_date - timedelta(days=7)).isoformat(),
            },
            {
                "task": "Update address with Centrelink/NDIS",
                "completed": False,
                "due_date": (move_date - timedelta(days=7)).isoformat(),
            },
            {
                "task": "Arrange mail redirection",
                "completed": False,
                "due_date": (move_date - timedelta(days=3)).isoformat(),
            },
            {
                "task": "Pack belongings",
                "completed": False,
                "due_date": (move_date - timedelta(days=2)).isoformat(),
            },
        ]

        # Move day tasks
        move_day = [
            {"task": "Collect keys from provider", "completed": False},
            {"task": "Complete property condition report", "completed": False},
            {"task": "Check all accessibility features working", "completed": False},
            {"task": "Test emergency systems", "completed": False},
            {"task": "Unpack essential items", "completed": False},
            {"task": "Set up bed and bedroom", "completed": False},
        ]

        # First week tasks
        first_week = [
            {"task": "Meet neighbours (if applicable)", "completed": False},
            {"task": "Locate nearest shops and services", "completed": False},
            {"task": "Update GP with new address", "completed": False},
            {"task": "Arrange NDIS plan review if needed", "completed": False},
            {"task": "Set up routine with support workers", "completed": False},
            {"task": "Report any maintenance issues", "completed": False},
        ]

        # Important contacts
        contacts = [
            {"role": "Property Manager", "name": prop.provider_name, "phone": ""},
            {"role": "Maintenance", "name": "", "phone": ""},
            {
                "role": "SIL Provider",
                "name": prop.sil_provider_name if prop.sil_available else "",
                "phone": "",
            },
            {"role": "Emergency Services", "name": "000", "phone": "000"},
        ]

        checklist = MoveInChecklist(
            checklist_id=checklist_id,
            searcher_id=searcher_id,
            property_id=property_id,
            pre_move_tasks=pre_move,
            move_day_tasks=move_day,
            first_week_tasks=first_week,
            total_tasks=len(pre_move) + len(move_day) + len(first_week),
            contacts=contacts,
            planned_move_date=move_date,
        )

        self.checklists[checklist_id] = checklist

        print(f"✅ Move-in checklist created: {checklist_id}")
        print(f"   Move date: {move_date.strftime('%d %B %Y')}")
        print(f"   Total tasks: {checklist.total_tasks}")

        return checklist

    def update_checklist_task(
        self, checklist_id: str, task_name: str, completed: bool
    ) -> bool:
        """Update a checklist task status."""
        checklist = self.checklists.get(checklist_id)
        if not checklist:
            return False

        # Search all task lists
        for task_list in [
            checklist.pre_move_tasks,
            checklist.move_day_tasks,
            checklist.first_week_tasks,
        ]:
            for task in task_list:
                if task["task"] == task_name:
                    was_completed = task["completed"]
                    task["completed"] = completed

                    # Update count
                    if completed and not was_completed:
                        checklist.tasks_completed += 1
                    elif not completed and was_completed:
                        checklist.tasks_completed -= 1

                    return True

        return False

    def get_checklist_progress(self, checklist_id: str) -> dict:
        """Get checklist progress summary."""
        checklist = self.checklists.get(checklist_id)
        if not checklist:
            return {"error": "Checklist not found"}

        return {
            "checklist_id": checklist_id,
            "move_date": (
                checklist.planned_move_date.isoformat()
                if checklist.planned_move_date
                else None
            ),
            "tasks_completed": checklist.tasks_completed,
            "total_tasks": checklist.total_tasks,
            "progress_percentage": checklist.get_progress_percentage(),
            "pre_move_remaining": sum(
                1 for t in checklist.pre_move_tasks if not t["completed"]
            ),
            "move_day_remaining": sum(
                1 for t in checklist.move_day_tasks if not t["completed"]
            ),
            "first_week_remaining": sum(
                1 for t in checklist.first_week_tasks if not t["completed"]
            ),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # EXPLANATIONS (Plain Language)
    # ──────────────────────────────────────────────────────────────────────────

    def explain_sda(self) -> str:
        """Explain SDA in plain language."""
        return """
SPECIALIST DISABILITY ACCOMMODATION (SDA) EXPLAINED

What is SDA?
SDA is special housing built for people with significant disabilities.
It's the building itself - designed to be accessible and meet your needs.

Who can get SDA?
You need to have SDA funding in your NDIS plan. This is for people who:
- Have very high support needs, OR
- Have extreme functional impairment

The 5 Types of SDA:
1. BASIC - Standard accessible features
2. IMPROVED LIVEABILITY - Better access and easier to live in
3. FULLY ACCESSIBLE - Full wheelchair access throughout
4. ROBUST - Strong and durable for complex needs
5. HIGH PHYSICAL SUPPORT - Maximum accessibility with assistive technology

How Much Does It Cost?
- The NDIS pays the SDA provider directly (your SDA funding)
- You pay a "reasonable rent contribution" (like normal rent)
- The rent is usually 25% of your Disability Support Pension plus Commonwealth Rent Assistance

Important: SDA is just the building. If you need support workers (help with daily tasks), 
that's called SIL (Supported Independent Living) - it's separate funding.
        """.strip()

    def explain_sil(self) -> str:
        """Explain SIL in plain language."""
        return """
SUPPORTED INDEPENDENT LIVING (SIL) EXPLAINED

What is SIL?
SIL is support from trained workers to help you live independently.
It's the PEOPLE who help you - not the building.

What kind of help?
- Personal care (showering, dressing)
- Cooking and meal preparation
- Cleaning and household tasks
- Taking medication
- Getting out in the community
- Developing skills to be more independent

Who can get SIL?
You need SIL funding in your NDIS plan. This is usually for people who:
- Need regular support with daily living
- Can't live independently without help
- Want to live in their own home (not with family)

SIL Support Levels:
- Standard: Regular daytime support
- High Intensity: More complex needs
- Active Overnight: Worker awake all night
- Sleepover: Worker sleeps but is available

Important: SIL can be in any home - including SDA, your own home, 
or a shared house with other people who have disabilities.

SDA + SIL Together:
Many people have both SDA (the accessible building) and SIL (the support workers).
They work together but are funded separately in your NDIS plan.
        """.strip()

    def explain_sda_categories(self) -> str:
        """Explain SDA categories."""
        return """
SDA DESIGN CATEGORIES EXPLAINED

BASIC
- Entry is step-free
- Wider doorways than normal
- Accessible bathroom
Best for: People who can walk but need easier access

IMPROVED LIVEABILITY
- Everything in Basic, plus:
- Better lighting
- Easier to use kitchen
- More space to move around
- Luminance contrast (easier to see edges)
Best for: People with some vision or cognitive needs

FULLY ACCESSIBLE
- Full wheelchair access everywhere
- Roll-in shower (no step or hob)
- Wider corridors for wheelchairs
- Adjustable benchtops
Best for: Wheelchair users who can transfer independently

ROBUST
- Very strong construction
- Impact-resistant walls
- Soundproofing
- Secure fixtures
- Safe outdoor area
Best for: People with complex behaviours who may damage property

HIGH PHYSICAL SUPPORT
- Everything in Fully Accessible, plus:
- Ceiling hoists (or ready for them)
- Emergency power backup
- Smart home controls
- Assistive technology ready
Best for: People with high physical needs who use hoists
        """.strip()


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate NDIS Housing Search Assistant."""

    print("=" * 70)
    print("🏠 NDIS HOUSING SEARCH ASSISTANT")
    print("=" * 70)
    print("\n🔒 Privacy Mode: On-Premise")
    print("♿ Accessibility: Screen Reader Compatible")

    # Initialize assistant
    assistant = NDISHousingSearchAssistant()

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Add sample providers
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📦 STEP 1: Setting Up Providers")
    print("─" * 70)

    provider1 = Provider(
        provider_id="PROV-001",
        name="Care Connect Provider",  # Generic provider name
        abn="12 345 678 901",
        ndis_registered=True,
        ndis_registration_number="4-12345678",
        sda_registered=True,
        sil_registered=True,
        phone="1800 123 456",
        email="info@example-provider.com.au",
        service_regions=["Northern Metro", "Eastern Metro", "Hills Region"],
        states=["SA"],
        overall_rating=4.5,
        total_reviews=127,
        response_time_rating=4.2,
        accessibility_rating=4.8,
        total_properties=15,
        current_vacancies=3,
    )
    assistant.providers[provider1.provider_id] = provider1

    provider2 = Provider(
        provider_id="PROV-002",
        name="Ability Housing",  # Generic provider name
        abn="98 765 432 101",
        ndis_registered=True,
        sda_registered=True,
        sil_registered=False,
        service_regions=["Southern Metro", "Western Metro"],
        states=["SA"],
        overall_rating=4.2,
        total_reviews=89,
        accessibility_rating=4.5,
        total_properties=8,
        current_vacancies=2,
    )
    assistant.providers[provider2.provider_id] = provider2

    print(f"   ✅ Added {len(assistant.providers)} providers")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Add sample properties
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("🏠 STEP 2: Adding Property Listings")
    print("─" * 70)

    prop1 = PropertyListing(
        property_id="PROP-001",
        provider_id="PROV-001",
        suburb="Mawson Lakes",
        state="SA",
        postcode="5095",
        region="Northern Adelaide",
        name="Parkview Accessible Apartment",
        property_type=PropertyType.APARTMENT,
        sda_category=SDACategory.HIGH_PHYSICAL_SUPPORT,
        bedrooms=2,
        bathrooms=1,
        available_from=date(2024, 9, 1),
        current_vacancies=1,
        total_capacity=1,
        accessibility_features=[
            AccessibilityFeature.WHEELCHAIR_ACCESS,
            AccessibilityFeature.CEILING_HOISTS,
            AccessibilityFeature.ROLL_IN_SHOWER,
            AccessibilityFeature.SMART_HOME,
            AccessibilityFeature.VISUAL_ALERTS,
            AccessibilityFeature.EMERGENCY_POWER,
        ],
        other_features=["Air conditioning", "Built-in robes", "Secure parking"],
        sda_daily_rate=Decimal("217.84"),
        estimated_rent_contribution=Decimal("150.00"),
        sil_available=True,
        sil_provider_same=True,
        has_virtual_tour=True,
        has_video=True,
        photos_alt_text_available=True,
        description="Modern accessible apartment with ceiling hoists and smart home controls.",
        accessibility_description="Fully accessible apartment with automated doors, ceiling hoists in bedroom and bathroom, roll-in shower, and smart home controls operable by voice or switch.",
        provider_name="Care Connect Provider",  # Generic provider name
        provider_rating=4.5,
        provider_reviews_count=127,
        public_transport_distance="100m to bus stop (Route 225)",
        nearest_shopping="200m to Shopping Centre",
        nearest_medical="1km to GP clinic",
    )
    assistant.properties[prop1.property_id] = prop1

    prop2 = PropertyListing(
        property_id="PROP-002",
        provider_id="PROV-001",
        suburb="Exampletown",  # Generic suburb
        state="SA",
        postcode="5092",
        region="Northern Metro",
        name="Sunshine Villa",
        property_type=PropertyType.VILLA,
        sda_category=SDACategory.FULLY_ACCESSIBLE,
        bedrooms=3,
        bathrooms=2,
        available_from=None,  # Not currently available
        current_vacancies=0,
        total_capacity=2,
        has_waitlist=True,
        accessibility_features=[
            AccessibilityFeature.WHEELCHAIR_ACCESS,
            AccessibilityFeature.ROLL_IN_SHOWER,
            AccessibilityFeature.ADJUSTABLE_BENCHTOPS,
        ],
        sda_daily_rate=Decimal("209.41"),
        estimated_rent_contribution=Decimal("135.00"),
        sil_available=True,
        description="Spacious villa with private outdoor area.",
        provider_name="Care Connect Provider",  # Generic provider name
        provider_rating=4.5,
    )
    assistant.properties[prop2.property_id] = prop2

    prop3 = PropertyListing(
        property_id="PROP-003",
        provider_id="PROV-002",
        suburb="Sample Heights",  # Generic suburb
        state="SA",
        postcode="5043",
        region="Southern Metro",
        name="Garden View Unit",
        property_type=PropertyType.APARTMENT,
        sda_category=SDACategory.IMPROVED_LIVEABILITY,
        bedrooms=1,
        bathrooms=1,
        available_from=date(2024, 8, 15),
        current_vacancies=1,
        accessibility_features=[
            AccessibilityFeature.WHEELCHAIR_ACCESS,
            AccessibilityFeature.VISUAL_ALERTS,
            AccessibilityFeature.HEARING_LOOP,
        ],
        sda_daily_rate=Decimal("72.61"),
        estimated_rent_contribution=Decimal("120.00"),
        sil_available=False,
        description="Modern unit with improved liveability features.",
        provider_name="Ability Housing",  # Generic provider name
        provider_rating=4.2,
    )
    assistant.properties[prop3.property_id] = prop3

    print(f"   ✅ Added {len(assistant.properties)} properties")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: Create searcher profile
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("👤 STEP 3: Creating Searcher Profile")
    print("─" * 70)

    searcher = SearcherProfile(
        searcher_id="SEARCH-001",
        first_name="Sarah",
        last_name_initial="M",
        preferred_name="Sarah",
        has_ndis_plan=True,
        sda_eligible=True,
        sda_category=SDACategory.HIGH_PHYSICAL_SUPPORT,
        sda_daily_budget=Decimal("220.00"),
        sil_in_plan=True,
        plan_end_date=date(2025, 6, 30),
        preferred_locations=["Mawson Lakes", "Modbury", "Salisbury"],
        preferred_property_types=[PropertyType.APARTMENT, PropertyType.VILLA],
        max_rent_contribution=Decimal("160.00"),
        required_features=[
            AccessibilityFeature.CEILING_HOISTS,
            AccessibilityFeature.WHEELCHAIR_ACCESS,
        ],
        preferred_features=[
            AccessibilityFeature.SMART_HOME,
            AccessibilityFeature.EMERGENCY_POWER,
        ],
        prefer_living_alone=True,
        needs_24_7_support=True,
        mobility_level="motorised wheelchair",
        preferred_contact_method="email",
        accessibility_needs=["Screen reader compatible documents", "Large print"],
        consent_to_share_with_providers=True,
        consent_date=date.today(),
    )
    assistant.create_profile(searcher)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Search for properties
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("🔍 STEP 4: Searching for Matching Properties")
    print("─" * 70)

    results = assistant.search_properties(
        searcher_id="SEARCH-001",
        locations=searcher.preferred_locations,
        sda_categories=[
            SDACategory.HIGH_PHYSICAL_SUPPORT,
            SDACategory.FULLY_ACCESSIBLE,
        ],
        required_features=[AccessibilityFeature.CEILING_HOISTS],
        include_waitlist=True,
    )

    print(f"\n   Found {len(results)} matching properties:\n")

    for prop, match_info in results:
        print(f"   📍 {prop.name}")
        print(f"      Location: {prop.suburb}, {prop.state}")
        print(f"      Type: {prop.property_type.value} | {prop.sda_category.value}")
        print(f"      Match: {match_info['percentage']}%")
        print(f"      Available: {'Yes' if prop.current_vacancies > 0 else 'Waitlist'}")

        if match_info["matches"]:
            print(f"      ✅ Matches: {', '.join(match_info['matches'][:3])}")
        if match_info["missing"]:
            print(f"      ⚠️ Missing: {', '.join(match_info['missing'][:2])}")
        print()

    # Add favourite
    assistant.add_favourite("SEARCH-001", "PROP-001")
    print("   ⭐ Added Parkview Accessible Apartment to favourites")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: Compare providers
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("⚖️ STEP 5: Comparing Providers")
    print("─" * 70)

    comparison = assistant.compare_providers(["PROV-001", "PROV-002"])

    print("\n   Provider Comparison:")
    for prov in comparison["providers"]:
        print(f"\n   📋 {prov['name']}")
        print(
            f"      Rating: {prov['overall_rating']}/5 ({prov['total_reviews']} reviews)"
        )
        print(f"      Accessibility Rating: {prov['accessibility_rating']}/5")
        print(
            f"      Properties: {prov['total_properties']} ({prov['current_vacancies']} vacancies)"
        )
        print(
            f"      SDA: {'✅' if prov['sda_registered'] else '❌'} | SIL: {'✅' if prov['sil_registered'] else '❌'}"
        )

    print("\n   Summary:")
    print(f"   • Highest Rated: {comparison['summary']['highest_rated']}")
    print(f"   • Best Accessibility: {comparison['summary']['best_accessibility']}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: Schedule a tour
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📅 STEP 6: Scheduling Property Tour")
    print("─" * 70)

    tour_date = datetime.now() + timedelta(days=7)
    tour_date = tour_date.replace(hour=10, minute=0, second=0, microsecond=0)

    tour = assistant.schedule_tour(
        searcher_id="SEARCH-001",
        property_id="PROP-001",
        tour_type=TourType.IN_PERSON,
        preferred_datetime=tour_date,
        accessibility_requirements=["Ramp access to building", "Accessible parking"],
        support_person_attending=True,
    )

    # Confirm tour
    assistant.confirm_tour(tour.booking_id)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 7: Start application
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📝 STEP 7: Housing Application")
    print("─" * 70)

    application = assistant.create_application(
        searcher_id="SEARCH-001",
        property_id="PROP-001",
    )

    print("\n   Documents required:")
    for doc in application.documents_required:
        print(f"      □ {doc}")

    # Add documents
    assistant.add_document(application.application_id, "NDIS Plan Summary")
    assistant.add_document(application.application_id, "Photo ID")
    assistant.add_document(application.application_id, "Proof of SDA Eligibility")
    assistant.add_document(application.application_id, "SIL Quote")

    # Submit
    result = assistant.submit_application(application.application_id)
    print(f"\n   📬 {result['message']}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 8: Join waitlist (for other property)
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📋 STEP 8: Joining Waitlist")
    print("─" * 70)

    waitlist_entry = assistant.join_waitlist(
        searcher_id="SEARCH-001",
        property_id="PROP-002",  # Sunshine Villa (no vacancies)
    )

    waitlist_status = assistant.get_waitlist_status("SEARCH-001")
    print("\n   Current waitlists:")
    for entry in waitlist_status:
        print(f"      • {entry['property_name']}")
        print(
            f"        Position: {entry['position']} | Est. wait: {entry['estimated_wait']}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 9: Generate move-in checklist (simulating acceptance)
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("✅ STEP 9: Move-In Checklist (Simulating Acceptance)")
    print("─" * 70)

    move_date = date.today() + timedelta(days=30)
    checklist = assistant.create_move_in_checklist(
        searcher_id="SEARCH-001",
        property_id="PROP-001",
        move_date=move_date,
    )

    # Mark some tasks complete
    assistant.update_checklist_task(
        checklist.checklist_id, "Sign occupancy agreement", True
    )
    assistant.update_checklist_task(
        checklist.checklist_id, "Set up electricity account", True
    )

    progress = assistant.get_checklist_progress(checklist.checklist_id)
    print(f"\n   📊 Checklist Progress: {progress['progress_percentage']}%")
    print(f"      Pre-move tasks remaining: {progress['pre_move_remaining']}")
    print(f"      Move day tasks remaining: {progress['move_day_remaining']}")
    print(f"      First week tasks remaining: {progress['first_week_remaining']}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 10: Display accessible property summary
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("♿ STEP 10: Screen Reader Friendly Property Summary")
    print("─" * 70)

    prop = assistant.properties["PROP-001"]
    print("\n" + prop.to_accessible_summary())

    # ──────────────────────────────────────────────────────────────────────────
    # BONUS: Explain SDA/SIL
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("📚 BONUS: Plain Language Explanations")
    print("─" * 70)

    print("\n" + assistant.explain_sda()[:500] + "...")

    # ──────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("✅ NDIS HOUSING SEARCH DEMO COMPLETE")
    print("=" * 70)

    print("\n📚 This assistant can help with:")
    print("   • Searching for SDA properties by location and features")
    print("   • Matching properties to your accessibility needs")
    print("   • Comparing SDA/SIL providers")
    print("   • Scheduling property tours (in-person or virtual)")
    print("   • Managing housing applications")
    print("   • Joining waitlists for properties")
    print("   • Preparing for move-in day")
    print("   • Understanding SDA/SIL in plain language")

    print("\n♿ Accessibility Features:")
    print("   • Screen reader compatible outputs")
    print("   • Plain language explanations")
    print("   • Alt text for images")
    print("   • Multiple communication formats")
    print("   • Support person can assist")

    print("\n🔒 Privacy Features:")
    print("   • On-premise data storage")
    print("   • Consent management")
    print("   • Privacy-respecting profiles")
    print("   • Controlled data sharing")


if __name__ == "__main__":
    asyncio.run(demo())
