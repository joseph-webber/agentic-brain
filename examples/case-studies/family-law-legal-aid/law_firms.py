# Family Law Firms Directory for Agentic Brain
# Copyright (C) 2024-2025 Joseph Webber
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Family Law Firms Directory.

Comprehensive directory of family law firms across Australia.
Helps users find:
- Lawyers near their location
- Lawyers near the other party's location
- Lawyers near the Family Court registry they attend
- Lawyers with specific expertise (children, property, DV, ICL)

Includes firm ratings and specialties for informed choices.
"""

from dataclasses import dataclass, field
from enum import Enum
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, List, Optional


class LawFirmSpecialty(Enum):
    """Family law specializations."""

    CHILDREN_MATTERS = "children_matters"
    PARENTING_ORDERS = "parenting_orders"
    PROPERTY_SETTLEMENT = "property_settlement"
    DIVORCE = "divorce"
    CHILD_SUPPORT = "child_support"
    DOMESTIC_VIOLENCE = "domestic_violence"
    RELOCATION = "relocation"
    INTERNATIONAL = "international"  # Hague Convention
    SURROGACY = "surrogacy"
    ADOPTION = "adoption"
    DE_FACTO = "de_facto"
    SAME_SEX = "same_sex"
    ICL_PANEL = "icl_panel"  # Independent Children's Lawyer
    LEGAL_AID = "legal_aid"  # Takes Legal Aid matters
    MEDIATION = "mediation"
    COLLABORATIVE = "collaborative"  # Collaborative law
    HIGH_CONFLICT = "high_conflict"
    COMPLEX_PROPERTY = "complex_property"
    ABORIGINAL_TORRES_STRAIT = "aboriginal_torres_strait"  # Indigenous family law


class PriceRange(Enum):
    """Firm pricing tiers."""

    LEGAL_AID = "legal_aid"  # Free via Legal Aid
    LOW = "low"  # $200-350/hr
    MEDIUM = "medium"  # $350-500/hr
    HIGH = "high"  # $500-750/hr
    PREMIUM = "premium"  # $750+/hr


@dataclass
class FirmReview:
    """Client review of a firm."""

    rating: float  # 1-5 stars
    review_count: int
    source: str  # google, avvo, lawyers.com.au
    highlights: List[str] = field(default_factory=list)


@dataclass
class FamilyLawFirm:
    """Family law firm details."""

    name: str
    address: str
    suburb: str
    state: str
    postcode: str
    phone: str

    # Location
    latitude: float
    longitude: float

    # Details
    website: Optional[str] = None
    email: Optional[str] = None

    # Specialties
    specialties: List[LawFirmSpecialty] = field(default_factory=list)

    # Pricing
    price_range: PriceRange = PriceRange.MEDIUM
    offers_free_consultation: bool = False
    accepts_legal_aid: bool = False

    # Reviews
    review: Optional[FirmReview] = None

    # Court proximity
    nearest_court: Optional[str] = None
    distance_to_court_km: Optional[float] = None

    # Additional
    languages: List[str] = field(default_factory=lambda: ["English"])
    after_hours: bool = False
    video_consultations: bool = True

    def format_address(self) -> str:
        """Format full address."""
        return f"{self.address}, {self.suburb} {self.state} {self.postcode}"


# =============================================================================
# FAMILY LAW FIRMS DATABASE
# Organized by state, includes major firms with specialties
# =============================================================================

FAMILY_LAW_FIRMS: List[FamilyLawFirm] = [
    # =========================================================================
    # NEW SOUTH WALES
    # =========================================================================
    FamilyLawFirm(
        name="Maguire & McInerney Family Lawyers",
        address="Level 14, 60 Carrington Street",
        suburb="Sydney",
        state="NSW",
        postcode="2000",
        phone="(02) 9223 9166",
        latitude=-33.8651,
        longitude=151.2070,
        website="https://www.maguiremcinerney.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.HIGH_CONFLICT,
        ],
        price_range=PriceRange.HIGH,
        offers_free_consultation=True,
        nearest_court="Sydney Family Court Registry",
        review=FirmReview(
            rating=4.8,
            review_count=127,
            source="google",
            highlights=["Excellent communication", "Won complex custody case"],
        ),
    ),
    FamilyLawFirm(
        name="Mander Family Law",
        address="Suite 1, Level 7, 99 Elizabeth Street",
        suburb="Sydney",
        state="NSW",
        postcode="2000",
        phone="(02) 9199 4522",
        latitude=-33.8710,
        longitude=151.2100,
        website="https://www.manderfamilylaw.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.DOMESTIC_VIOLENCE,
            LawFirmSpecialty.RELOCATION,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Sydney Family Court Registry",
        review=FirmReview(
            rating=4.9,
            review_count=89,
            source="google",
            highlights=["Compassionate", "Great with DV matters"],
        ),
    ),
    FamilyLawFirm(
        name="Morrisons Law Group",
        address="Level 2, 32 Martin Place",
        suburb="Sydney",
        state="NSW",
        postcode="2000",
        phone="(02) 9521 6200",
        latitude=-33.8678,
        longitude=151.2103,
        website="https://www.morrisonslawgroup.com.au",
        specialties=[
            LawFirmSpecialty.COMPLEX_PROPERTY,
            LawFirmSpecialty.DIVORCE,
            LawFirmSpecialty.INTERNATIONAL,
        ],
        price_range=PriceRange.PREMIUM,
        offers_free_consultation=False,
        nearest_court="Sydney Family Court Registry",
        review=FirmReview(
            rating=4.7,
            review_count=156,
            source="google",
            highlights=["Top-tier property expertise", "International specialists"],
        ),
    ),
    FamilyLawFirm(
        name="Prime Family Lawyers Parramatta",
        address="Level 5, 91 Phillip Street",
        suburb="Parramatta",
        state="NSW",
        postcode="2150",
        phone="(02) 8006 7030",
        latitude=-33.8168,
        longitude=151.0034,
        website="https://www.primefamilylawyers.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.CHILD_SUPPORT,
            LawFirmSpecialty.MEDIATION,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Parramatta Family Court Registry",
        review=FirmReview(
            rating=4.6,
            review_count=203,
            source="google",
            highlights=["Affordable", "Western Sydney specialists"],
        ),
        languages=["English", "Arabic", "Hindi", "Mandarin"],
    ),
    FamilyLawFirm(
        name="Maguire Family Law Newcastle",
        address="Level 1, 45 Hunter Street",
        suburb="Newcastle",
        state="NSW",
        postcode="2300",
        phone="(02) 4929 3995",
        latitude=-32.9267,
        longitude=151.7789,
        website="https://www.maguirefamilylaw.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.DE_FACTO,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Newcastle Family Court Registry",
        review=FirmReview(
            rating=4.7,
            review_count=78,
            source="google",
            highlights=["Hunter region experts", "Down to earth"],
        ),
    ),
    # =========================================================================
    # VICTORIA
    # =========================================================================
    FamilyLawFirm(
        name="Nicholes Family Lawyers",
        address="Level 1, 283 Clarendon Street",
        suburb="South Melbourne",
        state="VIC",
        postcode="3205",
        phone="(03) 9670 4122",
        latitude=-37.8330,
        longitude=144.9580,
        website="https://www.nicholes.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.HIGH_CONFLICT,
            LawFirmSpecialty.SAME_SEX,
        ],
        price_range=PriceRange.HIGH,
        offers_free_consultation=True,
        nearest_court="Melbourne Family Court Registry",
        review=FirmReview(
            rating=4.9,
            review_count=312,
            source="google",
            highlights=["Victoria's leading family firm", "Excellent outcomes"],
        ),
    ),
    FamilyLawFirm(
        name="Forte Family Lawyers",
        address="Level 25, 570 Bourke Street",
        suburb="Melbourne",
        state="VIC",
        postcode="3000",
        phone="(03) 9016 0499",
        latitude=-37.8165,
        longitude=144.9570,
        website="https://www.fortefamilylawyers.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.DOMESTIC_VIOLENCE,
            LawFirmSpecialty.COLLABORATIVE,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Melbourne Family Court Registry",
        review=FirmReview(
            rating=4.8,
            review_count=167,
            source="google",
            highlights=["Collaborative specialists", "Client-focused"],
        ),
    ),
    FamilyLawFirm(
        name="Marino Law Geelong",
        address="3/85 Moorabool Street",
        suburb="Geelong",
        state="VIC",
        postcode="3220",
        phone="(03) 5222 6155",
        latitude=-38.1485,
        longitude=144.3600,
        website="https://www.marinolaw.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.MEDIATION,
        ],
        price_range=PriceRange.LOW,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Geelong Magistrates Court",
        review=FirmReview(
            rating=4.6,
            review_count=89,
            source="google",
            highlights=["Geelong's best", "Affordable regional option"],
        ),
    ),
    # =========================================================================
    # QUEENSLAND
    # =========================================================================
    FamilyLawFirm(
        name="Hetherington Family Law",
        address="Level 2, 231 George Street",
        suburb="Brisbane",
        state="QLD",
        postcode="4000",
        phone="(07) 3229 4459",
        latitude=-27.4710,
        longitude=153.0235,
        website="https://www.hetheringtonfamilylaw.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.ICL_PANEL,
        ],
        price_range=PriceRange.HIGH,
        offers_free_consultation=True,
        nearest_court="Brisbane Family Court Registry",
        review=FirmReview(
            rating=4.9,
            review_count=234,
            source="google",
            highlights=["ICL panel members", "Children's rights focus"],
        ),
    ),
    FamilyLawFirm(
        name="James Noble Law",
        address="Level 5, 127 Creek Street",
        suburb="Brisbane",
        state="QLD",
        postcode="4000",
        phone="(07) 3221 4999",
        latitude=-27.4680,
        longitude=153.0280,
        website="https://www.jamesnoblelaw.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.RELOCATION,
            LawFirmSpecialty.DOMESTIC_VIOLENCE,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Brisbane Family Court Registry",
        review=FirmReview(
            rating=4.7,
            review_count=156,
            source="google",
            highlights=["Relocation experts", "Compassionate service"],
        ),
        languages=["English", "Mandarin"],
    ),
    FamilyLawFirm(
        name="Ramsden Family Law Gold Coast",
        address="Suite 7, 75 Coolangatta Road",
        suburb="Coolangatta",
        state="QLD",
        postcode="4225",
        phone="(07) 5536 3055",
        latitude=-28.1700,
        longitude=153.5350,
        website="https://www.ramsdenfamilylaw.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.DE_FACTO,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        nearest_court="Southport Courthouse",
        review=FirmReview(
            rating=4.5,
            review_count=98,
            source="google",
            highlights=["Gold Coast specialists", "Cross-border expertise"],
        ),
    ),
    FamilyLawFirm(
        name="Cairns Family Law Centre",
        address="Level 1, 15 Lake Street",
        suburb="Cairns",
        state="QLD",
        postcode="4870",
        phone="(07) 4031 1044",
        latitude=-16.9200,
        longitude=145.7720,
        website="https://www.cairnsfamilylaw.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.ABORIGINAL_TORRES_STRAIT,
            LawFirmSpecialty.MEDIATION,
        ],
        price_range=PriceRange.LOW,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Cairns Courthouse",
        review=FirmReview(
            rating=4.6,
            review_count=67,
            source="google",
            highlights=["Far North QLD experts", "Indigenous family law"],
        ),
        languages=["English", "Torres Strait Creole"],
    ),
    # =========================================================================
    # SOUTH AUSTRALIA
    # =========================================================================
    FamilyLawFirm(
        name="Mead & Maher Family Lawyers",
        address="Level 8, 55 Gawler Place",
        suburb="Adelaide",
        state="SA",
        postcode="5000",
        phone="(08) 8227 1900",
        latitude=-34.9250,
        longitude=138.6015,
        website="https://www.meadmaher.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.HIGH_CONFLICT,
        ],
        price_range=PriceRange.HIGH,
        offers_free_consultation=True,
        nearest_court="Adelaide Family Court Registry",
        review=FirmReview(
            rating=4.8,
            review_count=189,
            source="google",
            highlights=["SA's leading family firm", "Complex matters"],
        ),
    ),
    FamilyLawFirm(
        name="Culshaw Miller Lawyers",
        address="Level 2, 89 King William Street",
        suburb="Adelaide",
        state="SA",
        postcode="5000",
        phone="(08) 8464 0033",
        latitude=-34.9260,
        longitude=138.6000,
        website="https://www.culshawmiller.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.DOMESTIC_VIOLENCE,
            LawFirmSpecialty.CHILD_SUPPORT,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Adelaide Family Court Registry",
        review=FirmReview(
            rating=4.7,
            review_count=134,
            source="google",
            highlights=["DV specialists", "Supportive team"],
        ),
    ),
    FamilyLawFirm(
        name="O'Brien Connors & Kennett",
        address="37 Carrington Street",
        suburb="Adelaide",
        state="SA",
        postcode="5000",
        phone="(08) 8410 6776",
        latitude=-34.9275,
        longitude=138.5995,
        website="https://www.ocklaw.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.ICL_PANEL,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        nearest_court="Adelaide Family Court Registry",
        review=FirmReview(
            rating=4.6,
            review_count=112,
            source="google",
            highlights=["ICL accredited", "Children first approach"],
        ),
    ),
    # =========================================================================
    # WESTERN AUSTRALIA
    # =========================================================================
    FamilyLawFirm(
        name="Cullen Macleod",
        address="Level 1, 100 Havelock Street",
        suburb="West Perth",
        state="WA",
        postcode="6005",
        phone="(08) 9488 1300",
        latitude=-31.9480,
        longitude=115.8420,
        website="https://www.cullenmacleod.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.COMPLEX_PROPERTY,
        ],
        price_range=PriceRange.HIGH,
        offers_free_consultation=True,
        nearest_court="Perth Family Court Registry",
        review=FirmReview(
            rating=4.8,
            review_count=167,
            source="google",
            highlights=["WA's premier firm", "Mining/resources expertise"],
        ),
    ),
    FamilyLawFirm(
        name="Pragma Lawyers",
        address="Level 3, 123 Colin Street",
        suburb="West Perth",
        state="WA",
        postcode="6005",
        phone="(08) 6500 4300",
        latitude=-31.9475,
        longitude=115.8430,
        website="https://www.pragmalawyers.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.DOMESTIC_VIOLENCE,
            LawFirmSpecialty.RELOCATION,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Perth Family Court Registry",
        review=FirmReview(
            rating=4.7,
            review_count=123,
            source="google",
            highlights=["Practical solutions", "FIFO family expertise"],
        ),
    ),
    # =========================================================================
    # TASMANIA
    # =========================================================================
    FamilyLawFirm(
        name="Page Seager Lawyers",
        address="Level 1, 179 Murray Street",
        suburb="Hobart",
        state="TAS",
        postcode="7000",
        phone="(03) 6235 5111",
        latitude=-42.8825,
        longitude=147.3290,
        website="https://www.pageseager.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.MEDIATION,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Hobart Family Court Registry",
        review=FirmReview(
            rating=4.6,
            review_count=78,
            source="google",
            highlights=["Tasmania's largest", "Full service"],
        ),
    ),
    FamilyLawFirm(
        name="Tierney Law Launceston",
        address="53 Brisbane Street",
        suburb="Launceston",
        state="TAS",
        postcode="7250",
        phone="(03) 6337 5555",
        latitude=-41.4380,
        longitude=147.1350,
        website="https://www.tierneylaw.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.CHILD_SUPPORT,
            LawFirmSpecialty.COLLABORATIVE,
        ],
        price_range=PriceRange.LOW,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Launceston Magistrates Court",
        review=FirmReview(
            rating=4.5,
            review_count=56,
            source="google",
            highlights=["Northern Tasmania experts", "Affordable"],
        ),
    ),
    # =========================================================================
    # NORTHERN TERRITORY
    # =========================================================================
    FamilyLawFirm(
        name="Ward Keller Lawyers",
        address="Level 2, 13 The Mall",
        suburb="Darwin",
        state="NT",
        postcode="0800",
        phone="(08) 8946 2999",
        latitude=-12.4620,
        longitude=130.8410,
        website="https://www.wardkeller.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.ABORIGINAL_TORRES_STRAIT,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Darwin Local Court",
        review=FirmReview(
            rating=4.7,
            review_count=89,
            source="google",
            highlights=["NT specialists", "Indigenous expertise"],
        ),
        languages=["English", "Kriol"],
    ),
    FamilyLawFirm(
        name="Bowden McCormack Lawyers",
        address="Level 1, 62 Todd Street",
        suburb="Alice Springs",
        state="NT",
        postcode="0870",
        phone="(08) 8952 3355",
        latitude=-23.6990,
        longitude=133.8770,
        website="https://www.bowdenmccormack.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.DOMESTIC_VIOLENCE,
            LawFirmSpecialty.ABORIGINAL_TORRES_STRAIT,
        ],
        price_range=PriceRange.LOW,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Alice Springs Local Court",
        review=FirmReview(
            rating=4.5,
            review_count=45,
            source="google",
            highlights=["Central Australia experts", "Remote area experience"],
        ),
        languages=["English", "Arrernte", "Pitjantjatjara"],
    ),
    # =========================================================================
    # ACT
    # =========================================================================
    FamilyLawFirm(
        name="Dobinson Davey Clifford Simpson",
        address="Level 2, 28 University Avenue",
        suburb="Canberra",
        state="ACT",
        postcode="2601",
        phone="(02) 6212 7600",
        latitude=-35.2780,
        longitude=149.1290,
        website="https://www.ddcslawyers.com.au",
        specialties=[
            LawFirmSpecialty.CHILDREN_MATTERS,
            LawFirmSpecialty.PROPERTY_SETTLEMENT,
            LawFirmSpecialty.INTERNATIONAL,
        ],
        price_range=PriceRange.HIGH,
        offers_free_consultation=True,
        nearest_court="Canberra Family Court Registry",
        review=FirmReview(
            rating=4.8,
            review_count=145,
            source="google",
            highlights=["Canberra's best", "Diplomatic family expertise"],
        ),
    ),
    FamilyLawFirm(
        name="Aulich Civil Law",
        address="Ground Floor, 17 Torrens Street",
        suburb="Braddon",
        state="ACT",
        postcode="2612",
        phone="(02) 6274 0999",
        latitude=-35.2750,
        longitude=149.1350,
        website="https://www.aulich.com.au",
        specialties=[
            LawFirmSpecialty.PARENTING_ORDERS,
            LawFirmSpecialty.DOMESTIC_VIOLENCE,
            LawFirmSpecialty.RELOCATION,
        ],
        price_range=PriceRange.MEDIUM,
        offers_free_consultation=True,
        accepts_legal_aid=True,
        nearest_court="Canberra Family Court Registry",
        review=FirmReview(
            rating=4.6,
            review_count=98,
            source="google",
            highlights=["Practical approach", "APS/Defence expertise"],
        ),
    ),
]


# =============================================================================
# FAMILY LAW FIRM FINDER
# =============================================================================


class FamilyLawFirmFinder:
    """
    Find family law firms based on location and needs.

    Helps users find:
    - Lawyers near them
    - Lawyers near the other party
    - Lawyers near the court they'll attend
    - Lawyers with specific expertise
    """

    def __init__(self, firms: Optional[List[FamilyLawFirm]] = None):
        self.firms = firms or FAMILY_LAW_FIRMS
        self._build_indices()

    def _build_indices(self):
        """Build lookup indices."""
        self.by_state: Dict[str, List[FamilyLawFirm]] = {}
        self.by_specialty: Dict[LawFirmSpecialty, List[FamilyLawFirm]] = {}
        self.by_postcode: Dict[str, List[FamilyLawFirm]] = {}

        for firm in self.firms:
            # By state
            if firm.state not in self.by_state:
                self.by_state[firm.state] = []
            self.by_state[firm.state].append(firm)

            # By postcode
            if firm.postcode not in self.by_postcode:
                self.by_postcode[firm.postcode] = []
            self.by_postcode[firm.postcode].append(firm)

            # By specialty
            for spec in firm.specialties:
                if spec not in self.by_specialty:
                    self.by_specialty[spec] = []
                self.by_specialty[spec].append(firm)

    def find_near_location(
        self,
        latitude: float,
        longitude: float,
        max_distance_km: float = 50,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find firms near a geographic location.

        Args:
            latitude: User's latitude
            longitude: User's longitude
            max_distance_km: Maximum distance in km
            limit: Maximum results

        Returns:
            List of firms with distance, sorted by distance
        """
        results = []

        for firm in self.firms:
            distance = self._calculate_distance(
                latitude, longitude, firm.latitude, firm.longitude
            )

            if distance <= max_distance_km:
                results.append(
                    {
                        "firm": firm,
                        "distance_km": round(distance, 1),
                    }
                )

        # Sort by distance
        results.sort(key=lambda x: x["distance_km"])

        return results[:limit]

    def find_in_state(
        self,
        state: str,
        specialty: Optional[LawFirmSpecialty] = None,
        accepts_legal_aid: Optional[bool] = None,
        max_price: Optional[PriceRange] = None,
    ) -> List[FamilyLawFirm]:
        """
        Find firms in a state with optional filters.

        Args:
            state: Australian state code
            specialty: Required specialty
            accepts_legal_aid: Must accept Legal Aid
            max_price: Maximum price range

        Returns:
            Matching firms
        """
        state = state.upper()
        firms = self.by_state.get(state, [])

        results = []
        for firm in firms:
            # Specialty filter
            if specialty and specialty not in firm.specialties:
                continue

            # Legal Aid filter
            if accepts_legal_aid and not firm.accepts_legal_aid:
                continue

            # Price filter
            if max_price:
                price_order = [
                    PriceRange.LEGAL_AID,
                    PriceRange.LOW,
                    PriceRange.MEDIUM,
                    PriceRange.HIGH,
                    PriceRange.PREMIUM,
                ]
                if price_order.index(firm.price_range) > price_order.index(max_price):
                    continue

            results.append(firm)

        return results

    def find_near_court(
        self,
        court_name: str,
        max_distance_km: float = 20,
    ) -> List[FamilyLawFirm]:
        """
        Find firms near a specific court.

        Args:
            court_name: Name of the court registry
            max_distance_km: Maximum distance from court

        Returns:
            Firms near the specified court
        """
        results = []

        for firm in self.firms:
            if firm.nearest_court and court_name.lower() in firm.nearest_court.lower():
                results.append(firm)

        # Sort by distance to court if available
        results.sort(key=lambda f: f.distance_to_court_km or 0)

        return results

    def find_for_other_party(
        self,
        other_party_state: str,
        child_location_state: Optional[str] = None,
    ) -> Dict[str, List[FamilyLawFirm]]:
        """
        Find firms relevant for dealing with other party.

        When the other parent is in a different state, you may need:
        - A lawyer in YOUR state
        - A lawyer in THEIR state (for enforcement)
        - A lawyer where the CHILD is (if different)

        Args:
            other_party_state: State where other party lives
            child_location_state: State where child primarily lives

        Returns:
            Dict with firms for each relevant location
        """
        result = {
            "other_party_state": self.find_in_state(other_party_state),
        }

        if child_location_state and child_location_state != other_party_state:
            result["child_location_state"] = self.find_in_state(child_location_state)

        return result

    def find_with_specialty(
        self,
        specialty: LawFirmSpecialty,
        state: Optional[str] = None,
    ) -> List[FamilyLawFirm]:
        """
        Find firms with a specific specialty.

        Args:
            specialty: Required specialty
            state: Optional state filter

        Returns:
            Matching firms
        """
        firms = self.by_specialty.get(specialty, [])

        if state:
            state = state.upper()
            firms = [f for f in firms if f.state == state]

        return firms

    def find_icl_lawyers(self, state: Optional[str] = None) -> List[FamilyLawFirm]:
        """Find Independent Children's Lawyer panel members."""
        return self.find_with_specialty(LawFirmSpecialty.ICL_PANEL, state)

    def find_dv_specialists(self, state: Optional[str] = None) -> List[FamilyLawFirm]:
        """Find domestic violence specialists."""
        return self.find_with_specialty(LawFirmSpecialty.DOMESTIC_VIOLENCE, state)

    def find_affordable(
        self,
        state: str,
        include_legal_aid: bool = True,
    ) -> List[FamilyLawFirm]:
        """
        Find affordable family lawyers.

        Args:
            state: State to search
            include_legal_aid: Include firms accepting Legal Aid

        Returns:
            Affordable firms sorted by price
        """
        results = []

        for firm in self.find_in_state(state):
            if firm.price_range in [PriceRange.LEGAL_AID, PriceRange.LOW] or include_legal_aid and firm.accepts_legal_aid:
                results.append(firm)

        return results

    def find_with_language(
        self,
        language: str,
        state: Optional[str] = None,
    ) -> List[FamilyLawFirm]:
        """
        Find firms that speak a specific language.

        Args:
            language: Language required
            state: Optional state filter

        Returns:
            Firms offering that language
        """
        results = []
        language_lower = language.lower()

        for firm in self.firms:
            if state and firm.state != state.upper():
                continue

            if any(lang.lower() == language_lower for lang in firm.languages):
                results.append(firm)

        return results

    def format_firm_details(self, firm: FamilyLawFirm) -> str:
        """Format firm details for display."""
        lines = [
            f"⚖️ {firm.name}",
            f"📍 {firm.format_address()}",
            f"📞 {firm.phone}",
        ]

        if firm.website:
            lines.append(f"🌐 {firm.website}")

        # Rating
        if firm.review:
            stars = "⭐" * int(firm.review.rating)
            lines.append(
                f"{stars} {firm.review.rating}/5 ({firm.review.review_count} reviews)"
            )
            if firm.review.highlights:
                lines.append(f'   "{firm.review.highlights[0]}"')

        # Price
        price_labels = {
            PriceRange.LEGAL_AID: "💚 Legal Aid",
            PriceRange.LOW: "💰 Budget-friendly ($200-350/hr)",
            PriceRange.MEDIUM: "💰💰 Mid-range ($350-500/hr)",
            PriceRange.HIGH: "💰💰💰 Premium ($500-750/hr)",
            PriceRange.PREMIUM: "💰💰💰💰 Top-tier ($750+/hr)",
        }
        lines.append(price_labels.get(firm.price_range, ""))

        # Features
        features = []
        if firm.offers_free_consultation:
            features.append("✅ Free consultation")
        if firm.accepts_legal_aid:
            features.append("✅ Accepts Legal Aid")
        if firm.video_consultations:
            features.append("✅ Video consultations")
        if firm.after_hours:
            features.append("✅ After hours available")

        if features:
            lines.append("  ".join(features))

        # Specialties
        spec_names = [s.value.replace("_", " ").title() for s in firm.specialties[:4]]
        if spec_names:
            lines.append(f"Specialises in: {', '.join(spec_names)}")

        return "\n".join(lines)

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance in km using Haversine formula."""
        R = 6371  # Earth's radius in km

        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        a = (
            sin(delta_lat / 2) ** 2
            + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        )
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Data classes
    "FamilyLawFirm",
    "FirmReview",
    "LawFirmSpecialty",
    "PriceRange",
    # Data
    "FAMILY_LAW_FIRMS",
    # Finder
    "FamilyLawFirmFinder",
]
