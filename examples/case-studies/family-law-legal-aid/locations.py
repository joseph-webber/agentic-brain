#!/usr/bin/env python3
"""
Australian Family Law Services Locator
=======================================

Comprehensive database of publicly available locations for:

1. COURTS
   - Federal Circuit and Family Court of Australia (FCFCOA)
   - State Family Courts (WA)
   - Local Courts (for AVO/DVO matters)

2. LEGAL SERVICES
   - Legal Aid offices (all states)
   - Community Legal Centres
   - Family Law specialist firms
   - Aboriginal Legal Services
   - Women's Legal Services

3. DISPUTE RESOLUTION
   - Family Dispute Resolution (FDR) providers
   - Relationships Australia
   - Community mediation centres

4. SUPPORT SERVICES
   - Domestic Violence services
   - Children's contact centres
   - Family support services

5. MANDATED PROGRAMS
   - Circle of Security
   - Parenting courses
   - Anger management
   - Drug & alcohol services

All addresses are PUBLIC information from government websites.
This helps people find:
- Where to attend court
- Where to get legal help
- Where to complete court-ordered programs

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
import logging
import math

logger = logging.getLogger(__name__)


# =============================================================================
# SERVICE TYPES
# =============================================================================


class ServiceType(Enum):
    """Types of family law related services."""

    # Courts
    FEDERAL_CIRCUIT_COURT = "federal_circuit_court"
    FAMILY_COURT = "family_court"
    STATE_FAMILY_COURT = "state_family_court"
    LOCAL_COURT = "local_court"
    MAGISTRATES_COURT = "magistrates_court"

    # Legal Services
    LEGAL_AID = "legal_aid"
    COMMUNITY_LEGAL_CENTRE = "clc"
    ABORIGINAL_LEGAL_SERVICE = "aboriginal_legal"
    WOMENS_LEGAL_SERVICE = "womens_legal"
    MENS_LEGAL_SERVICE = "mens_legal"
    FAMILY_LAW_FIRM = "family_law_firm"

    # Dispute Resolution
    FDR_PROVIDER = "fdr_provider"
    RELATIONSHIPS_AUSTRALIA = "relationships_australia"
    FAMILY_MEDIATION = "family_mediation"

    # Support Services
    DV_SERVICE = "dv_service"
    MENS_DV_SERVICE = "mens_dv_service"
    CHILDRENS_CONTACT_CENTRE = "contact_centre"
    FAMILY_SUPPORT = "family_support"

    # Programs
    PARENTING_PROGRAM = "parenting_program"
    CIRCLE_OF_SECURITY = "circle_of_security"
    ANGER_MANAGEMENT = "anger_management"
    DRUG_ALCOHOL = "drug_alcohol"
    COUNSELLING = "counselling"


class State(Enum):
    """Australian states and territories."""

    NSW = "New South Wales"
    VIC = "Victoria"
    QLD = "Queensland"
    WA = "Western Australia"
    SA = "South Australia"
    TAS = "Tasmania"
    ACT = "Australian Capital Territory"
    NT = "Northern Territory"


class AccessibilityFeature(Enum):
    """Accessibility features available at locations."""

    WHEELCHAIR = "wheelchair_access"
    HEARING_LOOP = "hearing_loop"
    AUSLAN = "auslan_interpreter"
    BRAILLE = "braille_signage"
    ACCESSIBLE_PARKING = "accessible_parking"
    QUIET_ROOM = "quiet_room"
    CHILD_FRIENDLY = "child_friendly"
    PRAYER_ROOM = "prayer_room"
    GUIDE_DOG = "guide_dog_welcome"
    LARGE_PRINT = "large_print"


# =============================================================================
# LOCATION DATA STRUCTURES
# =============================================================================


@dataclass
class Address:
    """Physical address."""

    street: str
    suburb: str
    state: State
    postcode: str
    country: str = "Australia"

    # For mapping
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def format(self) -> str:
        """Format address for display."""
        return f"{self.street}, {self.suburb} {self.state.name} {self.postcode}"

    def format_accessible(self) -> str:
        """Format for screen readers."""
        return (
            f"{self.street}. "
            f"{self.suburb}, {self.state.value}. "
            f"Postcode {' '.join(self.postcode)}."
        )


@dataclass
class OpeningHours:
    """Opening hours for a location."""

    day: str
    open_time: time
    close_time: time
    notes: Optional[str] = None

    def is_open(self, check_time: time) -> bool:
        return self.open_time <= check_time <= self.close_time

    def format(self) -> str:
        return f"{self.day}: {self.open_time.strftime('%H:%M')} - {self.close_time.strftime('%H:%M')}"


@dataclass
class ServiceLocation:
    """A location providing family law services."""

    location_id: str
    name: str
    service_types: List[ServiceType]

    # Address
    address: Address

    # Contact
    phone: str
    fax: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None

    # Hours
    opening_hours: List[OpeningHours] = field(default_factory=list)

    # Features
    accessibility: List[AccessibilityFeature] = field(default_factory=list)
    languages: List[str] = field(default_factory=lambda: ["English"])
    interpreter_available: bool = True

    # Services offered
    services_offered: List[str] = field(default_factory=list)

    # Case management system (for integration)
    cmms_type: Optional[str] = None  # "sap", "dynamics", "leap", etc.

    # Registry info (for courts)
    registry_code: Optional[str] = None
    efiling_enabled: bool = False

    def distance_from(self, lat: float, lng: float) -> float:
        """Calculate distance in km from a point (Haversine formula)."""
        if not self.address.latitude or not self.address.longitude:
            return float("inf")

        R = 6371  # Earth's radius in km

        lat1 = math.radians(lat)
        lat2 = math.radians(self.address.latitude)
        dlat = math.radians(self.address.latitude - lat)
        dlng = math.radians(self.address.longitude - lng)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def is_accessible(self, feature: AccessibilityFeature) -> bool:
        """Check if location has specific accessibility feature."""
        return feature in self.accessibility


# =============================================================================
# FEDERAL CIRCUIT AND FAMILY COURT LOCATIONS
# =============================================================================

# All FCFCOA registry locations (public information from www.fcfcoa.gov.au)
FCFCOA_REGISTRIES: List[ServiceLocation] = [
    # NEW SOUTH WALES
    ServiceLocation(
        location_id="fcfcoa-sydney",
        name="Federal Circuit and Family Court - Sydney",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Law Courts Building, Queens Square, 184 Phillip Street",
            suburb="Sydney",
            state=State.NSW,
            postcode="2000",
            latitude=-33.8688,
            longitude=151.2093,
        ),
        phone="1300 352 000",
        website="https://www.fcfcoa.gov.au",
        opening_hours=[
            OpeningHours("Monday", time(8, 30), time(16, 30)),
            OpeningHours("Tuesday", time(8, 30), time(16, 30)),
            OpeningHours("Wednesday", time(8, 30), time(16, 30)),
            OpeningHours("Thursday", time(8, 30), time(16, 30)),
            OpeningHours("Friday", time(8, 30), time(16, 30)),
        ],
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
            AccessibilityFeature.ACCESSIBLE_PARKING,
            AccessibilityFeature.GUIDE_DOG,
        ],
        services_offered=[
            "Family law matters",
            "Divorce applications",
            "Property settlements",
            "Parenting orders",
            "Child support",
            "Contravention applications",
        ],
        cmms_type="sap_case_manager",
        registry_code="SYD",
        efiling_enabled=True,
    ),
    ServiceLocation(
        location_id="fcfcoa-parramatta",
        name="Federal Circuit and Family Court - Parramatta",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Level 3, 160 Marsden Street",
            suburb="Parramatta",
            state=State.NSW,
            postcode="2150",
            latitude=-33.8151,
            longitude=151.0011,
        ),
        phone="1300 352 000",
        website="https://www.fcfcoa.gov.au",
        opening_hours=[
            OpeningHours("Monday", time(8, 30), time(16, 30)),
            OpeningHours("Tuesday", time(8, 30), time(16, 30)),
            OpeningHours("Wednesday", time(8, 30), time(16, 30)),
            OpeningHours("Thursday", time(8, 30), time(16, 30)),
            OpeningHours("Friday", time(8, 30), time(16, 30)),
        ],
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
            AccessibilityFeature.ACCESSIBLE_PARKING,
        ],
        services_offered=[
            "Family law matters",
            "Divorce applications",
            "Parenting orders",
        ],
        cmms_type="sap_case_manager",
        registry_code="PAR",
        efiling_enabled=True,
    ),
    ServiceLocation(
        location_id="fcfcoa-newcastle",
        name="Federal Circuit and Family Court - Newcastle",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Newcastle Courthouse, 31 Church Street",
            suburb="Newcastle",
            state=State.NSW,
            postcode="2300",
            latitude=-32.9283,
            longitude=151.7817,
        ),
        phone="1300 352 000",
        registry_code="NCL",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
        accessibility=[AccessibilityFeature.WHEELCHAIR],
        services_offered=["Family law matters", "Divorce applications"],
    ),
    # VICTORIA
    ServiceLocation(
        location_id="fcfcoa-melbourne",
        name="Federal Circuit and Family Court - Melbourne",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="305 William Street",
            suburb="Melbourne",
            state=State.VIC,
            postcode="3000",
            latitude=-37.8136,
            longitude=144.9631,
        ),
        phone="1300 352 000",
        website="https://www.fcfcoa.gov.au",
        opening_hours=[
            OpeningHours("Monday", time(8, 30), time(16, 30)),
            OpeningHours("Tuesday", time(8, 30), time(16, 30)),
            OpeningHours("Wednesday", time(8, 30), time(16, 30)),
            OpeningHours("Thursday", time(8, 30), time(16, 30)),
            OpeningHours("Friday", time(8, 30), time(16, 30)),
        ],
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
            AccessibilityFeature.ACCESSIBLE_PARKING,
            AccessibilityFeature.QUIET_ROOM,
        ],
        cmms_type="sap_case_manager",
        registry_code="MEL",
        efiling_enabled=True,
    ),
    ServiceLocation(
        location_id="fcfcoa-dandenong",
        name="Federal Circuit and Family Court - Dandenong",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT],
        address=Address(
            street="Dandenong Magistrates Court, 54 Princes Highway",
            suburb="Dandenong",
            state=State.VIC,
            postcode="3175",
            latitude=-37.9875,
            longitude=145.2156,
        ),
        phone="1300 352 000",
        registry_code="DAN",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
    ),
    # QUEENSLAND
    ServiceLocation(
        location_id="fcfcoa-brisbane",
        name="Federal Circuit and Family Court - Brisbane",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Harry Gibbs Commonwealth Law Courts, 119 North Quay",
            suburb="Brisbane",
            state=State.QLD,
            postcode="4000",
            latitude=-27.4698,
            longitude=153.0251,
        ),
        phone="1300 352 000",
        website="https://www.fcfcoa.gov.au",
        opening_hours=[
            OpeningHours("Monday", time(8, 30), time(16, 30)),
            OpeningHours("Tuesday", time(8, 30), time(16, 30)),
            OpeningHours("Wednesday", time(8, 30), time(16, 30)),
            OpeningHours("Thursday", time(8, 30), time(16, 30)),
            OpeningHours("Friday", time(8, 30), time(16, 30)),
        ],
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
            AccessibilityFeature.ACCESSIBLE_PARKING,
        ],
        cmms_type="sap_case_manager",
        registry_code="BNE",
        efiling_enabled=True,
    ),
    ServiceLocation(
        location_id="fcfcoa-cairns",
        name="Federal Circuit and Family Court - Cairns",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT],
        address=Address(
            street="Cairns Courthouse, 5B Sheridan Street",
            suburb="Cairns",
            state=State.QLD,
            postcode="4870",
            latitude=-16.9186,
            longitude=145.7781,
        ),
        phone="1300 352 000",
        registry_code="CNS",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
    ),
    ServiceLocation(
        location_id="fcfcoa-townsville",
        name="Federal Circuit and Family Court - Townsville",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT],
        address=Address(
            street="Townsville Courthouse, 188 Walker Street",
            suburb="Townsville",
            state=State.QLD,
            postcode="4810",
            latitude=-19.2590,
            longitude=146.8169,
        ),
        phone="1300 352 000",
        registry_code="TSV",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
    ),
    # SOUTH AUSTRALIA
    ServiceLocation(
        location_id="fcfcoa-adelaide",
        name="Federal Circuit and Family Court - Adelaide",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Roma Mitchell Commonwealth Law Courts, 3 Angas Street",
            suburb="Adelaide",
            state=State.SA,
            postcode="5000",
            latitude=-34.9285,
            longitude=138.6007,
        ),
        phone="1300 352 000",
        website="https://www.fcfcoa.gov.au",
        opening_hours=[
            OpeningHours("Monday", time(9, 0), time(16, 30)),
            OpeningHours("Tuesday", time(9, 0), time(16, 30)),
            OpeningHours("Wednesday", time(9, 0), time(16, 30)),
            OpeningHours("Thursday", time(9, 0), time(16, 30)),
            OpeningHours("Friday", time(9, 0), time(16, 30)),
        ],
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
            AccessibilityFeature.ACCESSIBLE_PARKING,
            AccessibilityFeature.GUIDE_DOG,
        ],
        cmms_type="sap_case_manager",
        registry_code="ADL",
        efiling_enabled=True,
    ),
    # WESTERN AUSTRALIA (Note: WA has separate Family Court)
    ServiceLocation(
        location_id="fcfcoa-perth",
        name="Federal Circuit and Family Court - Perth",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT],
        address=Address(
            street="Commonwealth Law Courts, 1 Victoria Avenue",
            suburb="Perth",
            state=State.WA,
            postcode="6000",
            latitude=-31.9505,
            longitude=115.8605,
        ),
        phone="1300 352 000",
        registry_code="PER",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
        accessibility=[AccessibilityFeature.WHEELCHAIR],
    ),
    # TASMANIA
    ServiceLocation(
        location_id="fcfcoa-hobart",
        name="Federal Circuit and Family Court - Hobart",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Edward Braddon Commonwealth Law Courts, 39-41 Davey Street",
            suburb="Hobart",
            state=State.TAS,
            postcode="7000",
            latitude=-42.8821,
            longitude=147.3272,
        ),
        phone="1300 352 000",
        registry_code="HBA",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
        accessibility=[AccessibilityFeature.WHEELCHAIR],
    ),
    ServiceLocation(
        location_id="fcfcoa-launceston",
        name="Federal Circuit and Family Court - Launceston",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT],
        address=Address(
            street="Launceston Magistrates Court, 73-79 Charles Street",
            suburb="Launceston",
            state=State.TAS,
            postcode="7250",
            latitude=-41.4332,
            longitude=147.1441,
        ),
        phone="1300 352 000",
        registry_code="LCN",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
    ),
    # ACT
    ServiceLocation(
        location_id="fcfcoa-canberra",
        name="Federal Circuit and Family Court - Canberra",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Nigel Bowen Commonwealth Law Courts, Childers Street",
            suburb="Canberra",
            state=State.ACT,
            postcode="2601",
            latitude=-35.2809,
            longitude=149.1300,
        ),
        phone="1300 352 000",
        registry_code="CBR",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
        ],
    ),
    # NORTHERN TERRITORY
    ServiceLocation(
        location_id="fcfcoa-darwin",
        name="Federal Circuit and Family Court - Darwin",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT, ServiceType.FAMILY_COURT],
        address=Address(
            street="Supreme Court Building, State Square",
            suburb="Darwin",
            state=State.NT,
            postcode="0800",
            latitude=-12.4634,
            longitude=130.8456,
        ),
        phone="1300 352 000",
        registry_code="DRW",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
    ),
    ServiceLocation(
        location_id="fcfcoa-alice-springs",
        name="Federal Circuit and Family Court - Alice Springs",
        service_types=[ServiceType.FEDERAL_CIRCUIT_COURT],
        address=Address(
            street="Alice Springs Courthouse, Parsons Street",
            suburb="Alice Springs",
            state=State.NT,
            postcode="0870",
            latitude=-23.7000,
            longitude=133.8833,
        ),
        phone="1300 352 000",
        registry_code="ASP",
        efiling_enabled=True,
        cmms_type="sap_case_manager",
    ),
]


# =============================================================================
# LEGAL AID OFFICES
# =============================================================================

LEGAL_AID_OFFICES: List[ServiceLocation] = [
    # NSW - Legal Aid NSW
    ServiceLocation(
        location_id="legal-aid-nsw-sydney",
        name="Legal Aid NSW - Sydney Head Office",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="323 Castlereagh Street",
            suburb="Sydney",
            state=State.NSW,
            postcode="2000",
            latitude=-33.8760,
            longitude=151.2094,
        ),
        phone="1300 888 529",
        website="https://www.legalaid.nsw.gov.au",
        email="infoservice@legalaid.nsw.gov.au",
        languages=["English", "Arabic", "Vietnamese", "Mandarin", "Cantonese"],
        interpreter_available=True,
        services_offered=[
            "Family law advice",
            "Duty lawyer service",
            "Legal representation",
            "Grants of legal aid",
            "Family dispute resolution",
        ],
        cmms_type="salesforce",
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
        ],
    ),
    ServiceLocation(
        location_id="legal-aid-nsw-parramatta",
        name="Legal Aid NSW - Parramatta",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="Level 5, 1 Smith Street",
            suburb="Parramatta",
            state=State.NSW,
            postcode="2150",
            latitude=-33.8148,
            longitude=151.0040,
        ),
        phone="1300 888 529",
        website="https://www.legalaid.nsw.gov.au",
        cmms_type="salesforce",
        interpreter_available=True,
    ),
    # Victoria - Victoria Legal Aid
    ServiceLocation(
        location_id="legal-aid-vic-melbourne",
        name="Victoria Legal Aid - Melbourne",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="350 Queen Street",
            suburb="Melbourne",
            state=State.VIC,
            postcode="3000",
            latitude=-37.8102,
            longitude=144.9589,
        ),
        phone="1300 792 387",
        website="https://www.legalaid.vic.gov.au",
        languages=["English", "Vietnamese", "Mandarin", "Arabic", "Greek", "Italian"],
        interpreter_available=True,
        cmms_type="dynamics_365",
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.HEARING_LOOP,
        ],
    ),
    # Queensland - Legal Aid Queensland
    ServiceLocation(
        location_id="legal-aid-qld-brisbane",
        name="Legal Aid Queensland - Brisbane",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="44 Herschel Street",
            suburb="Brisbane",
            state=State.QLD,
            postcode="4000",
            latitude=-27.4681,
            longitude=153.0249,
        ),
        phone="1300 651 188",
        website="https://www.legalaid.qld.gov.au",
        interpreter_available=True,
        cmms_type="salesforce",
    ),
    # South Australia - Legal Services Commission
    ServiceLocation(
        location_id="legal-aid-sa-adelaide",
        name="Legal Services Commission SA - Adelaide",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="159 Gawler Place",
            suburb="Adelaide",
            state=State.SA,
            postcode="5000",
            latitude=-34.9270,
            longitude=138.6030,
        ),
        phone="1300 366 424",
        website="https://www.lsc.sa.gov.au",
        interpreter_available=True,
        cmms_type="dynamics_365",
        accessibility=[AccessibilityFeature.WHEELCHAIR],
    ),
    # Western Australia - Legal Aid WA
    ServiceLocation(
        location_id="legal-aid-wa-perth",
        name="Legal Aid WA - Perth",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="32 St Georges Terrace",
            suburb="Perth",
            state=State.WA,
            postcode="6000",
            latitude=-31.9554,
            longitude=115.8585,
        ),
        phone="1300 650 579",
        website="https://www.legalaid.wa.gov.au",
        interpreter_available=True,
        cmms_type="dynamics_365",
    ),
    # Tasmania - Legal Aid Commission of Tasmania
    ServiceLocation(
        location_id="legal-aid-tas-hobart",
        name="Legal Aid Commission Tasmania - Hobart",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="158 Liverpool Street",
            suburb="Hobart",
            state=State.TAS,
            postcode="7000",
            latitude=-42.8792,
            longitude=147.3294,
        ),
        phone="1300 366 611",
        website="https://www.legalaid.tas.gov.au",
        interpreter_available=True,
        cmms_type="custom",
    ),
    # ACT - Legal Aid ACT
    ServiceLocation(
        location_id="legal-aid-act-canberra",
        name="Legal Aid ACT - Canberra",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="2 Allsop Street",
            suburb="Canberra",
            state=State.ACT,
            postcode="2601",
            latitude=-35.2785,
            longitude=149.1303,
        ),
        phone="1300 654 314",
        website="https://www.legalaidact.org.au",
        interpreter_available=True,
        cmms_type="custom",
    ),
    # NT - Northern Territory Legal Aid Commission
    ServiceLocation(
        location_id="legal-aid-nt-darwin",
        name="NT Legal Aid Commission - Darwin",
        service_types=[ServiceType.LEGAL_AID],
        address=Address(
            street="9-11 Cavenagh Street",
            suburb="Darwin",
            state=State.NT,
            postcode="0800",
            latitude=-12.4620,
            longitude=130.8418,
        ),
        phone="1800 019 343",
        website="https://www.ntlac.nt.gov.au",
        interpreter_available=True,
        cmms_type="custom",
        languages=["English", "Aboriginal Languages"],
    ),
]


# =============================================================================
# FAMILY DISPUTE RESOLUTION PROVIDERS
# =============================================================================

FDR_PROVIDERS: List[ServiceLocation] = [
    # Relationships Australia - Major FDR provider
    ServiceLocation(
        location_id="ra-nsw-sydney",
        name="Relationships Australia NSW - Sydney",
        service_types=[
            ServiceType.FDR_PROVIDER,
            ServiceType.RELATIONSHIPS_AUSTRALIA,
            ServiceType.COUNSELLING,
        ],
        address=Address(
            street="Level 5, 68 Wentworth Avenue",
            suburb="Surry Hills",
            state=State.NSW,
            postcode="2010",
            latitude=-33.8843,
            longitude=151.2108,
        ),
        phone="1300 364 277",
        website="https://www.relationshipsnsw.org.au",
        services_offered=[
            "Family Dispute Resolution (FDR)",
            "s60I certificates",
            "Couples counselling",
            "Family counselling",
            "Parenting programs",
            "Post-separation support",
        ],
        cmms_type="salesforce",
        accessibility=[AccessibilityFeature.WHEELCHAIR],
    ),
    ServiceLocation(
        location_id="ra-vic-melbourne",
        name="Relationships Australia Victoria - Melbourne",
        service_types=[
            ServiceType.FDR_PROVIDER,
            ServiceType.RELATIONSHIPS_AUSTRALIA,
            ServiceType.COUNSELLING,
        ],
        address=Address(
            street="46 Princess Street",
            suburb="Kew",
            state=State.VIC,
            postcode="3101",
            latitude=-37.8102,
            longitude=145.0293,
        ),
        phone="1300 364 277",
        website="https://www.relationshipsvictoria.org.au",
        services_offered=[
            "Family Dispute Resolution (FDR)",
            "s60I certificates",
            "Mediation",
            "Counselling",
        ],
        cmms_type="dynamics_365",
    ),
    ServiceLocation(
        location_id="ra-qld-brisbane",
        name="Relationships Australia Queensland - Brisbane",
        service_types=[ServiceType.FDR_PROVIDER, ServiceType.RELATIONSHIPS_AUSTRALIA],
        address=Address(
            street="159 St Pauls Terrace",
            suburb="Spring Hill",
            state=State.QLD,
            postcode="4000",
            latitude=-27.4589,
            longitude=153.0290,
        ),
        phone="1300 364 277",
        website="https://www.raq.org.au",
        cmms_type="salesforce",
    ),
    ServiceLocation(
        location_id="ra-sa-adelaide",
        name="Relationships Australia SA - Adelaide",
        service_types=[ServiceType.FDR_PROVIDER, ServiceType.RELATIONSHIPS_AUSTRALIA],
        address=Address(
            street="161 Frome Street",
            suburb="Adelaide",
            state=State.SA,
            postcode="5000",
            latitude=-34.9209,
            longitude=138.6091,
        ),
        phone="1300 364 277",
        website="https://www.rasa.org.au",
        cmms_type="custom",
    ),
    # Family Relationship Centres (Government-funded)
    ServiceLocation(
        location_id="frc-parramatta",
        name="Family Relationship Centre - Parramatta",
        service_types=[ServiceType.FDR_PROVIDER, ServiceType.FAMILY_MEDIATION],
        address=Address(
            street="Level 2, 1 Smith Street",
            suburb="Parramatta",
            state=State.NSW,
            postcode="2150",
            latitude=-33.8145,
            longitude=151.0036,
        ),
        phone="1800 050 321",
        website="https://www.familyrelationships.gov.au",
        services_offered=[
            "Free FDR for eligible families",
            "Parenting arrangements",
            "s60I certificates",
            "Information sessions",
        ],
        cmms_type="custom",
    ),
]


# =============================================================================
# PARENTING PROGRAMS AND COURSES
# =============================================================================

PARENTING_PROGRAMS: List[ServiceLocation] = [
    # Circle of Security providers
    ServiceLocation(
        location_id="cos-nsw-sydney",
        name="Circle of Security - Tresillian NSW",
        service_types=[ServiceType.CIRCLE_OF_SECURITY, ServiceType.PARENTING_PROGRAM],
        address=Address(
            street="McKenzie Street",
            suburb="Belmore",
            state=State.NSW,
            postcode="2192",
            latitude=-33.9203,
            longitude=151.0920,
        ),
        phone="1300 272 736",
        website="https://www.tresillian.org.au",
        services_offered=[
            "Circle of Security Parenting Program",
            "8-week group program",
            "Understanding attachment",
            "Court-accepted program",
        ],
        cmms_type="custom",
    ),
    ServiceLocation(
        location_id="cos-vic-melbourne",
        name="Circle of Security - Anglicare Victoria",
        service_types=[ServiceType.CIRCLE_OF_SECURITY, ServiceType.PARENTING_PROGRAM],
        address=Address(
            street="84 Hoddle Street",
            suburb="Abbotsford",
            state=State.VIC,
            postcode="3067",
            latitude=-37.8049,
            longitude=144.9984,
        ),
        phone="1800 809 722",
        website="https://www.anglicarevic.org.au",
        services_offered=[
            "Circle of Security Parenting",
            "Attachment-based parenting",
            "Group programs",
        ],
        cmms_type="custom",
    ),
    ServiceLocation(
        location_id="cos-sa-adelaide",
        name="Circle of Security - Uniting Care SA",
        service_types=[ServiceType.CIRCLE_OF_SECURITY, ServiceType.PARENTING_PROGRAM],
        address=Address(
            street="Level 1, 212 Pirie Street",
            suburb="Adelaide",
            state=State.SA,
            postcode="5000",
            latitude=-34.9252,
            longitude=138.6046,
        ),
        phone="1300 044 335",
        services_offered=[
            "Circle of Security",
            "Parenting After Separation",
            "Children's Contact Service",
        ],
        cmms_type="custom",
    ),
    # Triple P (Positive Parenting Program)
    ServiceLocation(
        location_id="triplep-qld-brisbane",
        name="Triple P Parenting - QLD",
        service_types=[ServiceType.PARENTING_PROGRAM],
        address=Address(
            street="Parenting Research Centre",
            suburb="Brisbane",
            state=State.QLD,
            postcode="4000",
            latitude=-27.4698,
            longitude=153.0251,
        ),
        phone="1800 880 660",
        website="https://www.triplep.net",
        services_offered=[
            "Triple P Positive Parenting",
            "Online courses",
            "Group seminars",
            "Individual support",
            "Court-accepted program",
        ],
        cmms_type="custom",
    ),
]


# =============================================================================
# DOMESTIC VIOLENCE SERVICES
# =============================================================================

DV_SERVICES: List[ServiceLocation] = [
    # 1800RESPECT - National helpline (not physical location)
    ServiceLocation(
        location_id="1800respect",
        name="1800RESPECT - National DV/SA Helpline",
        service_types=[ServiceType.DV_SERVICE],
        address=Address(
            street="National Helpline (Phone/Online)",
            suburb="Australia-wide",
            state=State.NSW,  # Headquarters
            postcode="0000",
        ),
        phone="1800 737 732",
        website="https://www.1800respect.org.au",
        services_offered=[
            "24/7 crisis support",
            "Safety planning",
            "Referrals to local services",
            "Online chat support",
        ],
        languages=["English", "100+ languages via interpreter"],
        cmms_type="custom",
    ),
    # DV Connect (QLD)
    ServiceLocation(
        location_id="dv-connect-qld",
        name="DV Connect Queensland",
        service_types=[ServiceType.DV_SERVICE],
        address=Address(
            street="Confidential location",
            suburb="Brisbane",
            state=State.QLD,
            postcode="4000",
        ),
        phone="1800 811 811",
        website="https://www.dvconnect.org",
        services_offered=[
            "24/7 crisis support",
            "Emergency accommodation",
            "Safety planning",
            "Court support",
            "Counselling referrals",
        ],
        cmms_type="custom",
    ),
    # Women's Safety NSW
    ServiceLocation(
        location_id="womens-safety-nsw",
        name="NSW Domestic Violence Line",
        service_types=[ServiceType.DV_SERVICE],
        address=Address(
            street="Statewide service",
            suburb="Sydney",
            state=State.NSW,
            postcode="2000",
        ),
        phone="1800 656 463",
        services_offered=[
            "24/7 crisis support",
            "Safety planning",
            "Emergency accommodation referrals",
            "ADVO information",
        ],
        cmms_type="custom",
    ),
    # Safe Steps Victoria
    ServiceLocation(
        location_id="safe-steps-vic",
        name="Safe Steps Family Violence Response",
        service_types=[ServiceType.DV_SERVICE],
        address=Address(
            street="Statewide service",
            suburb="Melbourne",
            state=State.VIC,
            postcode="3000",
        ),
        phone="1800 015 188",
        website="https://www.safesteps.org.au",
        services_offered=[
            "24/7 crisis response",
            "Emergency accommodation",
            "Safety planning",
            "IVO support",
        ],
        cmms_type="custom",
    ),
    # Men's services
    ServiceLocation(
        location_id="mensline-australia",
        name="MensLine Australia",
        service_types=[ServiceType.MENS_DV_SERVICE, ServiceType.COUNSELLING],
        address=Address(
            street="National Helpline",
            suburb="Australia-wide",
            state=State.VIC,
            postcode="3000",
        ),
        phone="1300 789 978",
        website="https://www.mensline.org.au",
        services_offered=[
            "24/7 support for men",
            "Relationship support",
            "Family violence support",
            "Separation support",
            "Mental health support",
        ],
        cmms_type="custom",
    ),
]


# =============================================================================
# CHILDREN'S CONTACT CENTRES
# =============================================================================

CONTACT_CENTRES: List[ServiceLocation] = [
    ServiceLocation(
        location_id="ccs-nsw-parramatta",
        name="Unifam Children's Contact Service - Parramatta",
        service_types=[ServiceType.CHILDRENS_CONTACT_CENTRE],
        address=Address(
            street="Church Street",
            suburb="Parramatta",
            state=State.NSW,
            postcode="2150",
            latitude=-33.8145,
            longitude=151.0036,
        ),
        phone="02 9762 0111",
        website="https://www.unifam.org.au",
        services_offered=[
            "Supervised contact visits",
            "Supported changeover",
            "Safe exchange location",
        ],
        cmms_type="custom",
        accessibility=[
            AccessibilityFeature.WHEELCHAIR,
            AccessibilityFeature.CHILD_FRIENDLY,
        ],
    ),
    ServiceLocation(
        location_id="ccs-vic-melbourne",
        name="MacKillop Family Services Contact Centre",
        service_types=[ServiceType.CHILDRENS_CONTACT_CENTRE],
        address=Address(
            street="Various locations",
            suburb="Melbourne",
            state=State.VIC,
            postcode="3000",
        ),
        phone="03 9699 9177",
        website="https://www.mackillop.org.au",
        services_offered=[
            "Supervised contact",
            "Supported changeover",
            "Family time supervision",
        ],
        cmms_type="custom",
    ),
]


# =============================================================================
# SERVICE LOCATOR CLASS
# =============================================================================


class ServiceLocator:
    """
    Find family law services by location, type, or need.

    Example:
        locator = ServiceLocator()

        # Find nearest court to Adelaide
        courts = locator.find_nearest(
            latitude=-34.9285,
            longitude=138.6007,
            service_type=ServiceType.FAMILY_COURT,
            limit=3
        )

        # Find Legal Aid in Victoria
        legal_aid = locator.find_by_state(State.VIC, ServiceType.LEGAL_AID)

        # Find all FDR providers
        fdr = locator.find_by_type(ServiceType.FDR_PROVIDER)
    """

    def __init__(self):
        self._all_services: List[ServiceLocation] = []
        self._load_all_services()

    def _load_all_services(self):
        """Load all service databases."""
        self._all_services.extend(FCFCOA_REGISTRIES)
        self._all_services.extend(LEGAL_AID_OFFICES)
        self._all_services.extend(FDR_PROVIDERS)
        self._all_services.extend(PARENTING_PROGRAMS)
        self._all_services.extend(DV_SERVICES)
        self._all_services.extend(CONTACT_CENTRES)

        logger.info(f"Loaded {len(self._all_services)} service locations")

    def find_nearest(
        self,
        latitude: float,
        longitude: float,
        service_type: Optional[ServiceType] = None,
        limit: int = 5,
    ) -> List[Tuple[ServiceLocation, float]]:
        """
        Find nearest services to a location.

        Returns list of (ServiceLocation, distance_km) tuples.
        """
        services = self._all_services

        if service_type:
            services = [s for s in services if service_type in s.service_types]

        # Calculate distances
        with_distance = []
        for service in services:
            dist = service.distance_from(latitude, longitude)
            if dist < float("inf"):
                with_distance.append((service, dist))

        # Sort by distance
        with_distance.sort(key=lambda x: x[1])

        return with_distance[:limit]

    def find_by_state(
        self,
        state: State,
        service_type: Optional[ServiceType] = None,
    ) -> List[ServiceLocation]:
        """Find services in a specific state."""
        services = [s for s in self._all_services if s.address.state == state]

        if service_type:
            services = [s for s in services if service_type in s.service_types]

        return services

    def find_by_type(self, service_type: ServiceType) -> List[ServiceLocation]:
        """Find all services of a specific type."""
        return [s for s in self._all_services if service_type in s.service_types]

    def find_accessible(
        self,
        feature: AccessibilityFeature,
        service_type: Optional[ServiceType] = None,
        state: Optional[State] = None,
    ) -> List[ServiceLocation]:
        """Find services with specific accessibility features."""
        services = self._all_services

        if service_type:
            services = [s for s in services if service_type in s.service_types]

        if state:
            services = [s for s in services if s.address.state == state]

        return [s for s in services if s.is_accessible(feature)]

    def find_by_cmms(self, cmms_type: str) -> List[ServiceLocation]:
        """Find services using a specific case management system."""
        return [s for s in self._all_services if s.cmms_type == cmms_type]

    def search(self, query: str) -> List[ServiceLocation]:
        """Search services by name or suburb."""
        query_lower = query.lower()

        results = []
        for service in self._all_services:
            if (
                query_lower in service.name.lower()
                or query_lower in service.address.suburb.lower()
                or query_lower in service.address.street.lower()
            ):
                results.append(service)

        return results

    def get_court_for_registry(self, registry_code: str) -> Optional[ServiceLocation]:
        """Get court by registry code (e.g., 'SYD', 'MEL')."""
        for service in FCFCOA_REGISTRIES:
            if service.registry_code == registry_code:
                return service
        return None

    def format_for_voiceover(self, service: ServiceLocation) -> str:
        """Format service details for screen readers."""
        lines = [
            f"{service.name}.",
            f"Address: {service.address.format_accessible()}",
            f"Phone: {' '.join(service.phone)}.",
        ]

        if service.services_offered:
            lines.append(
                f"Services include: {', '.join(service.services_offered[:3])}."
            )

        if service.accessibility:
            features = [f.value.replace("_", " ") for f in service.accessibility]
            lines.append(f"Accessibility: {', '.join(features)}.")

        return " ".join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    locator = ServiceLocator()

    print("=== Family Law Service Locator Demo ===\n")

    # Find nearest court to Adelaide CBD
    print("Nearest courts to Adelaide:")
    adelaide_lat, adelaide_lng = -34.9285, 138.6007
    nearest_courts = locator.find_nearest(
        adelaide_lat, adelaide_lng, service_type=ServiceType.FAMILY_COURT, limit=3
    )
    for court, distance in nearest_courts:
        print(f"  - {court.name}: {distance:.1f}km")

    # Find Legal Aid in SA
    print("\nLegal Aid in South Australia:")
    sa_legal_aid = locator.find_by_state(State.SA, ServiceType.LEGAL_AID)
    for service in sa_legal_aid:
        print(f"  - {service.name}: {service.phone}")

    # Find FDR providers
    print("\nFDR Providers (for s60I certificate):")
    fdr = locator.find_by_type(ServiceType.FDR_PROVIDER)[:5]
    for service in fdr:
        print(f"  - {service.name}")

    # Find services using SAP
    print("\nServices using SAP Case Manager:")
    sap_services = locator.find_by_cmms("sap_case_manager")
    print(f"  {len(sap_services)} courts use SAP Case Manager")

    # Accessible services
    print("\nWheelchair accessible courts in NSW:")
    accessible = locator.find_accessible(
        AccessibilityFeature.WHEELCHAIR,
        service_type=ServiceType.FAMILY_COURT,
        state=State.NSW,
    )
    for service in accessible:
        print(f"  - {service.name}")

    # VoiceOver format
    print("\n=== VoiceOver Format ===")
    court = locator.get_court_for_registry("ADL")
    if court:
        print(locator.format_for_voiceover(court))
