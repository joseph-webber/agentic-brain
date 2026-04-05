#!/usr/bin/env python3
"""
Support Services Directory - Advocacy, Helplines & Shelters
============================================================

Comprehensive directory of support services for family law matters:

1. DISABILITY ADVOCACY
   - Vision Australia / Royal Society for the Blind
   - Disability advocacy services (each state)
   - NDIS advocates

2. CHILDREN & YOUTH
   - Kids Helpline (ALL channels)
   - Headspace
   - ReachOut
   - Youth advocacy

3. MEN'S SERVICES
   - MensLine Australia
   - Men's Sheds
   - Dads in Distress
   - Father-specific support

4. WOMEN'S SERVICES
   - Women's shelters (each state)
   - DV services
   - Women's legal services

5. ABORIGINAL & TORRES STRAIT ISLANDER
   - Aboriginal Legal Services
   - Indigenous family support

6. CALD COMMUNITIES
   - Interpreter services
   - Multicultural support

7. LGBTIQ+ SERVICES
   - QLife
   - Switchboard
   - LGBTIQ+ legal services

8. MENTAL HEALTH
   - Lifeline
   - Beyond Blue
   - SANE Australia

All services are publicly available and can be found by the chatbot.

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# SERVICE CATEGORIES
# =============================================================================


class ServiceCategory(Enum):
    """Categories of support services."""

    DISABILITY_ADVOCACY = "disability_advocacy"
    VISION_IMPAIRMENT = "vision_impairment"
    HEARING_IMPAIRMENT = "hearing_impairment"
    CHILDREN_YOUTH = "children_youth"
    MENS_SERVICES = "mens_services"
    WOMENS_SERVICES = "womens_services"
    DV_SUPPORT = "dv_support"
    WOMENS_SHELTER = "womens_shelter"
    ABORIGINAL_TORRES_STRAIT = "aboriginal_torres_strait"
    CALD_MULTICULTURAL = "cald_multicultural"
    LGBTIQ = "lgbtiq"
    MENTAL_HEALTH = "mental_health"
    LEGAL_ADVOCACY = "legal_advocacy"
    FINANCIAL_SUPPORT = "financial_support"
    HOUSING = "housing"
    FAMILY_SUPPORT = "family_support"
    INTERPRETERS = "interpreters"
    ELDER_ABUSE = "elder_abuse"
    NDIS = "ndis"


class ContactChannel(Enum):
    """Ways to contact a service."""

    PHONE = "phone"
    SMS = "sms"
    EMAIL = "email"
    WEB_CHAT = "web_chat"
    VIDEO_CALL = "video_call"
    IN_PERSON = "in_person"
    TTY = "tty"  # For deaf/hearing impaired
    NRS = "nrs"  # National Relay Service
    APP = "app"
    AUSLAN_VIDEO = "auslan_video"  # Auslan interpreter
    ONLINE_FORM = "online_form"
    SOCIAL_MEDIA = "social_media"


@dataclass
class ContactMethod:
    """A way to contact a service."""

    channel: ContactChannel
    value: str  # Phone number, URL, email, etc.
    description: str = ""
    hours: str = ""  # "24/7", "9am-5pm Mon-Fri"
    is_24_7: bool = False
    is_free: bool = True
    accessibility_notes: str = ""


@dataclass
class SupportService:
    """A support service organisation."""

    name: str
    description: str
    categories: List[ServiceCategory]

    # Contact methods
    contacts: List[ContactMethod] = field(default_factory=list)

    # Coverage
    national: bool = True
    states: List[str] = field(default_factory=list)  # Empty = national

    # Website
    website: str = ""

    # Eligibility
    eligibility: str = "Anyone can access this service"

    # Languages
    languages: List[str] = field(default_factory=lambda: ["English"])
    interpreter_available: bool = False

    # Accessibility
    accessibility_features: List[str] = field(default_factory=list)

    # Cost
    is_free: bool = True
    cost_notes: str = ""

    def get_primary_contact(self) -> Optional[ContactMethod]:
        """Get the primary contact method (usually phone)."""
        for c in self.contacts:
            if c.channel == ContactChannel.PHONE:
                return c
        return self.contacts[0] if self.contacts else None

    def get_24_7_contacts(self) -> List[ContactMethod]:
        """Get contacts available 24/7."""
        return [c for c in self.contacts if c.is_24_7]

    def format_for_voiceover(self) -> str:
        """Format for screen reader accessibility."""
        primary = self.get_primary_contact()
        phone = primary.value if primary else "No phone"

        return (
            f"{self.name}. "
            f"{self.description}. "
            f"Phone: {phone.replace(' ', ', ')}. "
        )


# =============================================================================
# KIDS HELPLINE - ALL CHANNELS
# =============================================================================

KIDS_HELPLINE = SupportService(
    name="Kids Helpline",
    description=(
        "Australia's only free, private and confidential 24/7 phone and "
        "online counselling service for young people aged 5 to 25. "
        "No problem is too big or too small."
    ),
    categories=[
        ServiceCategory.CHILDREN_YOUTH,
        ServiceCategory.MENTAL_HEALTH,
        ServiceCategory.FAMILY_SUPPORT,
    ],
    contacts=[
        ContactMethod(
            channel=ContactChannel.PHONE,
            value="1800 55 1800",
            description="Free call from anywhere in Australia",
            hours="24 hours, 7 days a week",
            is_24_7=True,
            is_free=True,
        ),
        ContactMethod(
            channel=ContactChannel.WEB_CHAT,
            value="https://kidshelpline.com.au/get-help/webchat-counselling",
            description="Online chat with a counsellor",
            hours="24 hours, 7 days a week",
            is_24_7=True,
            is_free=True,
        ),
        ContactMethod(
            channel=ContactChannel.EMAIL,
            value="https://kidshelpline.com.au/get-help/email-counselling",
            description="Email counselling - response within 5 days",
            hours="Anytime",
            is_free=True,
        ),
        ContactMethod(
            channel=ContactChannel.APP,
            value="My Circle app",
            description="Self-help app with tools and activities",
            is_free=True,
        ),
        ContactMethod(
            channel=ContactChannel.SOCIAL_MEDIA,
            value="@KidsHelpline on Instagram, TikTok, Facebook",
            description="Mental health content and support",
            is_free=True,
        ),
        ContactMethod(
            channel=ContactChannel.ONLINE_FORM,
            value="https://kidshelpline.com.au/parents/get-help",
            description="Support for parents/carers",
            is_free=True,
        ),
    ],
    website="https://kidshelpline.com.au",
    national=True,
    eligibility="Young people aged 5-25, parents and carers",
    languages=["English"],
    interpreter_available=True,
    accessibility_features=[
        "Phone counselling (no video needed)",
        "Text-based web chat available",
        "Email for those who prefer writing",
        "NRS compatible for deaf/hearing impaired",
    ],
    is_free=True,
)


# =============================================================================
# DISABILITY ADVOCACY SERVICES
# =============================================================================

DISABILITY_SERVICES: List[SupportService] = [
    # National
    SupportService(
        name="Vision Australia",
        description=(
            "Support for people who are blind or have low vision. "
            "Employment, education, technology, orientation & mobility, "
            "guide dogs, and daily living support."
        ),
        categories=[
            ServiceCategory.DISABILITY_ADVOCACY,
            ServiceCategory.VISION_IMPAIRMENT,
            ServiceCategory.NDIS,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 84 74 66",
                description="General enquiries",
                hours="Monday to Friday, 8am to 5pm",
            ),
            ContactMethod(
                channel=ContactChannel.EMAIL,
                value="info@visionaustralia.org",
            ),
        ],
        website="https://www.visionaustralia.org",
        national=True,
        eligibility="People who are blind or have low vision",
        accessibility_features=[
            "Phone support (no visual interface needed)",
            "Accessible website (WCAG 2.1 AA)",
            "Support for screen reader users",
            "Large print materials available",
            "Braille materials available",
        ],
    ),
    SupportService(
        name="Royal Society for the Blind (RSB) - SA",
        description=(
            "South Australia's leading provider of services for people "
            "who are blind or vision impaired. Training, aids, guide dogs, "
            "and advocacy."
        ),
        categories=[
            ServiceCategory.DISABILITY_ADVOCACY,
            ServiceCategory.VISION_IMPAIRMENT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="08 8232 4777",
                hours="Monday to Friday, 9am to 5pm",
            ),
        ],
        website="https://www.rsb.org.au",
        national=False,
        states=["SA"],
        eligibility="People who are blind or vision impaired in SA",
        accessibility_features=[
            "Accessible technology training",
            "Guide dog services",
            "Orientation & mobility training",
        ],
    ),
    SupportService(
        name="Blind Citizens Australia",
        description=(
            "Peak advocacy organisation for people who are blind or "
            "vision impaired. Systemic advocacy, individual support, "
            "and peer connection."
        ),
        categories=[
            ServiceCategory.DISABILITY_ADVOCACY,
            ServiceCategory.VISION_IMPAIRMENT,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 033 660",
                description="Free call",
            ),
        ],
        website="https://www.bca.org.au",
        national=True,
        eligibility="People who are blind or vision impaired",
    ),
    SupportService(
        name="Deaf Australia",
        description=(
            "National peak advocacy organisation for Deaf and hard of "
            "hearing Australians. Systemic advocacy and support."
        ),
        categories=[
            ServiceCategory.DISABILITY_ADVOCACY,
            ServiceCategory.HEARING_IMPAIRMENT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.EMAIL,
                value="info@deafaustralia.org.au",
            ),
            ContactMethod(
                channel=ContactChannel.TTY,
                value="Contact via NRS",
            ),
        ],
        website="https://deafaustralia.org.au",
        national=True,
        eligibility="Deaf and hard of hearing Australians",
        accessibility_features=[
            "Auslan interpreter support",
            "TTY/NRS compatible",
            "Video relay service",
        ],
    ),
    SupportService(
        name="National Relay Service (NRS)",
        description=(
            "Phone service for people who are deaf, hard of hearing, "
            "and/or have a speech impairment. Connects to any phone number."
        ),
        categories=[
            ServiceCategory.DISABILITY_ADVOCACY,
            ServiceCategory.HEARING_IMPAIRMENT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.TTY,
                value="133 677",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.SMS,
                value="0423 677 767",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.accesshub.gov.au/nrs",
            ),
            ContactMethod(
                channel=ContactChannel.VIDEO_CALL,
                value="https://www.accesshub.gov.au/nrs/video-relay",
                description="Video Relay with Auslan interpreter",
            ),
        ],
        website="https://www.accesshub.gov.au/nrs",
        national=True,
        is_free=True,
        eligibility="Anyone who is deaf, hard of hearing, or has speech impairment",
        accessibility_features=[
            "TTY support",
            "SMS relay",
            "Voice relay",
            "Video relay with Auslan interpreter",
            "Internet relay",
        ],
    ),
    SupportService(
        name="People with Disability Australia (PWDA)",
        description=(
            "National disability rights organisation. Advocacy, information, "
            "and referral services."
        ),
        categories=[
            ServiceCategory.DISABILITY_ADVOCACY,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 422 015",
                description="Free call",
            ),
            ContactMethod(
                channel=ContactChannel.TTY,
                value="1800 422 016",
            ),
        ],
        website="https://pwd.org.au",
        national=True,
        eligibility="People with all types of disability",
    ),
    # State disability advocacy
    SupportService(
        name="Disability Advocacy Network Australia (DANA)",
        description=(
            "Peak body for independent disability advocacy. Can connect "
            "you with local advocacy services."
        ),
        categories=[ServiceCategory.DISABILITY_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="02 9188 4499",
            ),
        ],
        website="https://www.dana.org.au",
        national=True,
    ),
    SupportService(
        name="Disability Rights Victoria",
        description=(
            "Individual and systemic advocacy for Victorians with disability."
        ),
        categories=[
            ServiceCategory.DISABILITY_ADVOCACY,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 882 872",
            ),
        ],
        website="https://www.drvictoria.org.au",
        national=False,
        states=["VIC"],
    ),
    SupportService(
        name="Disability Advocacy NSW",
        description=("Independent advocacy for people with disability in NSW."),
        categories=[ServiceCategory.DISABILITY_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="02 9556 3077",
            ),
        ],
        website="https://www.da.org.au",
        national=False,
        states=["NSW"],
    ),
]


# =============================================================================
# MEN'S SERVICES
# =============================================================================

MENS_SERVICES: List[SupportService] = [
    SupportService(
        name="MensLine Australia",
        description=(
            "Professional telephone and online support, information and "
            "referral service for men with family and relationship concerns. "
            "Specialises in supporting men experiencing family violence."
        ),
        categories=[
            ServiceCategory.MENS_SERVICES,
            ServiceCategory.MENTAL_HEALTH,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 78 99 78",
                description="Counselling line",
                hours="24 hours, 7 days a week",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://mensline.org.au/chat-online",
                description="Online chat counselling",
                hours="24/7",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.VIDEO_CALL,
                value="https://mensline.org.au/video-call",
                description="Video counselling",
            ),
        ],
        website="https://mensline.org.au",
        national=True,
        eligibility="Men of all ages",
        languages=["English"],
        interpreter_available=True,
    ),
    SupportService(
        name="Dads in Distress (DIDS)",
        description=(
            "Peer support for fathers experiencing family breakdown and "
            "separation. Support groups and one-on-one support."
        ),
        categories=[
            ServiceCategory.MENS_SERVICES,
            ServiceCategory.FAMILY_SUPPORT,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 853 437",
                description="Support line",
                hours="Monday to Friday, 9am to 5pm",
            ),
        ],
        website="https://didsaustralia.com.au",
        national=True,
        eligibility="Fathers and male carers",
    ),
    SupportService(
        name="Men's Shed Association",
        description=(
            "Community spaces for men to connect, share skills, and support "
            "each other. Social connection and mental health support."
        ),
        categories=[
            ServiceCategory.MENS_SERVICES,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 550 009",
            ),
        ],
        website="https://mensshed.org",
        national=True,
        eligibility="Men of all ages",
    ),
    SupportService(
        name="Father Inclusive Practice",
        description=(
            "Information and support for services working with fathers. "
            "Resources for dads navigating separation."
        ),
        categories=[
            ServiceCategory.MENS_SERVICES,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="02 9635 9929",
            ),
        ],
        website="https://www.thefatherhoodproject.org.au",
        national=True,
    ),
    SupportService(
        name="No to Violence (Men's Referral Service)",
        description=(
            "Support for men who use violence and want to change. "
            "Counselling and behaviour change programs."
        ),
        categories=[
            ServiceCategory.MENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 766 491",
                description="Men's Referral Service",
                hours="Monday to Friday, 8am to 9pm. Sat-Sun 9am to 5pm",
            ),
        ],
        website="https://ntv.org.au",
        national=True,
        eligibility="Men who use violence or are at risk of using violence",
    ),
]


# =============================================================================
# WOMEN'S SERVICES & SHELTERS
# =============================================================================

WOMENS_SERVICES: List[SupportService] = [
    SupportService(
        name="1800RESPECT",
        description=(
            "National sexual assault, domestic and family violence "
            "counselling service. Trauma-informed support."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 737 732",
                description="1800RESPECT",
                hours="24/7",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.1800respect.org.au",
                hours="24/7",
                is_24_7=True,
            ),
        ],
        website="https://www.1800respect.org.au",
        national=True,
        eligibility="Anyone experiencing or at risk of violence",
        interpreter_available=True,
    ),
    SupportService(
        name="DV Connect (QLD)",
        description=(
            "Queensland's domestic violence helpline. Crisis support, "
            "safety planning, and refuge referrals."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.WOMENS_SHELTER,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 811 811",
                description="Women's line",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 600 636",
                description="Men's line",
                is_24_7=True,
            ),
        ],
        website="https://www.dvconnect.org",
        national=False,
        states=["QLD"],
    ),
    SupportService(
        name="Safe Steps (VIC)",
        description=(
            "Victoria's 24-hour family violence response centre. "
            "Crisis support and refuge accommodation."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.WOMENS_SHELTER,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 015 188",
                is_24_7=True,
            ),
        ],
        website="https://www.safesteps.org.au",
        national=False,
        states=["VIC"],
    ),
    SupportService(
        name="NSW Domestic Violence Line",
        description=(
            "NSW crisis support line for women and children escaping "
            "domestic and family violence."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.WOMENS_SHELTER,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 656 463",
                is_24_7=True,
            ),
        ],
        website="https://www.facs.nsw.gov.au/domestic-violence",
        national=False,
        states=["NSW"],
    ),
    SupportService(
        name="Women's Safety Services SA",
        description=(
            "Crisis accommodation and support for women and children "
            "escaping family violence in South Australia."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.WOMENS_SHELTER,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 800 098",
                description="Crisis line",
                is_24_7=True,
            ),
        ],
        website="https://www.womenssafetyservices.com.au",
        national=False,
        states=["SA"],
    ),
    SupportService(
        name="Women's Council for DV Services (WA)",
        description=(
            "Western Australia's peak body for women's domestic violence "
            "services. Crisis support and accommodation."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.WOMENS_SHELTER,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 007 339",
                description="Women's DV Helpline WA",
                is_24_7=True,
            ),
        ],
        website="https://www.womenscouncil.com.au",
        national=False,
        states=["WA"],
    ),
    SupportService(
        name="Women's Legal Service Australia",
        description=(
            "Network of Women's Legal Services providing free legal help "
            "for women, especially family law and family violence."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="See state services below",
            ),
        ],
        website="https://www.wlsa.org.au",
        national=True,
    ),
    SupportService(
        name="Women's Legal Service NSW",
        description=(
            "Free legal help for women in NSW. Family law, violence, "
            "care and protection, discrimination."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 801 501",
                hours="Monday to Friday, 9am to 5pm",
            ),
        ],
        website="https://www.wlsnsw.org.au",
        national=False,
        states=["NSW"],
    ),
    SupportService(
        name="Women's Legal Service Victoria",
        description=(
            "Free legal help for women in Victoria. Family violence, "
            "family law, sexual assault."
        ),
        categories=[
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 133 302",
                hours="Monday to Friday, 10am to 5pm",
            ),
        ],
        website="https://www.womenslegal.org.au",
        national=False,
        states=["VIC"],
    ),
]


# =============================================================================
# MENTAL HEALTH SERVICES
# =============================================================================

MENTAL_HEALTH_SERVICES: List[SupportService] = [
    SupportService(
        name="Lifeline",
        description=(
            "Crisis support and suicide prevention. Anyone can call "
            "when they're having a tough time."
        ),
        categories=[ServiceCategory.MENTAL_HEALTH],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="13 11 14",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.SMS,
                value="0477 13 11 14",
                hours="6pm-midnight AEDT",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.lifeline.org.au/crisis-chat",
                hours="7pm-midnight (Sydney time), 7 days",
            ),
        ],
        website="https://www.lifeline.org.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Beyond Blue",
        description=(
            "Support for anxiety, depression, and suicide prevention. "
            "Information and counselling."
        ),
        categories=[ServiceCategory.MENTAL_HEALTH],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 22 4636",
                description="1300 22 46 36",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.beyondblue.org.au/get-support/talk-to-a-counsellor/chat",
                hours="3pm to midnight AEST, 7 days",
            ),
        ],
        website="https://www.beyondblue.org.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Suicide Call Back Service",
        description=(
            "Nationwide counselling for anyone affected by suicide. "
            "Phone, video, and online."
        ),
        categories=[ServiceCategory.MENTAL_HEALTH],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 659 467",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.VIDEO_CALL,
                value="https://www.suicidecallbackservice.org.au",
            ),
        ],
        website="https://www.suicidecallbackservice.org.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="SANE Australia",
        description=(
            "Support for people with complex mental health issues. "
            "Peer support, counselling, and information."
        ),
        categories=[ServiceCategory.MENTAL_HEALTH],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 187 263",
                hours="Monday to Friday, 10am to 8pm AEST",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.sane.org/get-support",
            ),
        ],
        website="https://www.sane.org",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Headspace",
        description=(
            "Mental health support for young people aged 12-25. "
            "Centres across Australia."
        ),
        categories=[
            ServiceCategory.CHILDREN_YOUTH,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 650 890",
                description="eheadspace",
                hours="9am to 1am AEST, 7 days",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://headspace.org.au/eheadspace/connect-with-a-counsellor",
            ),
        ],
        website="https://headspace.org.au",
        national=True,
        eligibility="Young people aged 12-25",
        is_free=True,
    ),
    SupportService(
        name="ReachOut",
        description=(
            "Online mental health service for young people. "
            "Self-help tools, forums, and information."
        ),
        categories=[
            ServiceCategory.CHILDREN_YOUTH,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://au.reachout.com",
            ),
        ],
        website="https://au.reachout.com",
        national=True,
        eligibility="Young people under 25",
        is_free=True,
    ),
]


# =============================================================================
# LGBTIQ+ SERVICES
# =============================================================================

LGBTIQ_SERVICES: List[SupportService] = [
    SupportService(
        name="QLife",
        description=(
            "Australia-wide LGBTIQ+ peer support and referral service. "
            "Anonymous, free counselling."
        ),
        categories=[
            ServiceCategory.LGBTIQ,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 184 527",
                hours="3pm to midnight daily",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://qlife.org.au",
                hours="3pm to midnight daily",
            ),
        ],
        website="https://qlife.org.au",
        national=True,
        eligibility="LGBTIQ+ people and their families",
        is_free=True,
    ),
    SupportService(
        name="Switchboard Victoria",
        description=(
            "LGBTIQ+ peer support, counselling, and referral. "
            "Rainbow Door crisis line."
        ),
        categories=[
            ServiceCategory.LGBTIQ,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 729 367",
                description="Rainbow Door",
                is_24_7=True,
            ),
        ],
        website="https://www.switchboard.org.au",
        national=False,
        states=["VIC"],
    ),
    SupportService(
        name="LGBTIQ+ Legal Service (VIC)",
        description=(
            "Free legal help for LGBTIQ+ Victorians. "
            "Family law, discrimination, violence."
        ),
        categories=[
            ServiceCategory.LGBTIQ,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="03 9032 3000",
            ),
        ],
        website="https://lgbtiqlegal.org.au",
        national=False,
        states=["VIC"],
    ),
]


# =============================================================================
# ABORIGINAL & TORRES STRAIT ISLANDER SERVICES
# =============================================================================

ABORIGINAL_SERVICES: List[SupportService] = [
    SupportService(
        name="National Aboriginal & Torres Strait Islander Legal Services (NATSILS)",
        description=(
            "Peak body for Aboriginal and Torres Strait Islander legal services. "
            "Can connect you with your local ATSILS."
        ),
        categories=[
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="02 6205 0277",
            ),
        ],
        website="https://www.natsils.org.au",
        national=True,
        eligibility="Aboriginal and Torres Strait Islander people",
    ),
    SupportService(
        name="Aboriginal Legal Service NSW/ACT",
        description=(
            "Free legal help for Aboriginal people in NSW and ACT. "
            "Criminal, family, civil law."
        ),
        categories=[
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 765 767",
            ),
        ],
        website="https://www.alsnswact.org.au",
        national=False,
        states=["NSW", "ACT"],
    ),
    SupportService(
        name="Victorian Aboriginal Legal Service (VALS)",
        description=(
            "Free legal help for Aboriginal people in Victoria. "
            "Family violence, family law, child protection."
        ),
        categories=[
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 064 865",
                is_24_7=True,
            ),
        ],
        website="https://www.vals.org.au",
        national=False,
        states=["VIC"],
    ),
    SupportService(
        name="Aboriginal Family Legal Service SA",
        description=(
            "Family law help for Aboriginal South Australians. "
            "Separation, parenting, property."
        ),
        categories=[
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 870 678",
            ),
        ],
        website="https://aflssa.org.au",
        national=False,
        states=["SA"],
    ),
    SupportService(
        name="Djirra (VIC)",
        description=(
            "Aboriginal community-controlled organisation supporting "
            "Aboriginal women and children experiencing family violence."
        ),
        categories=[
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 105 303",
            ),
        ],
        website="https://djirra.org.au",
        national=False,
        states=["VIC"],
    ),
    SupportService(
        name="13YARN",
        description=("First Nations crisis support line. Yarn with a mob who get it."),
        categories=[
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
            ServiceCategory.MENTAL_HEALTH,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="13 92 76",
                description="13 YARN",
                is_24_7=True,
            ),
        ],
        website="https://www.13yarn.org.au",
        national=True,
        eligibility="Aboriginal and Torres Strait Islander people",
        is_free=True,
    ),
]


# =============================================================================
# CALD & INTERPRETER SERVICES
# =============================================================================

CALD_SERVICES: List[SupportService] = [
    SupportService(
        name="Translating and Interpreting Service (TIS)",
        description=(
            "Free interpreting for people who don't speak English, "
            "when dealing with non-commercial organisations."
        ),
        categories=[
            ServiceCategory.CALD_MULTICULTURAL,
            ServiceCategory.INTERPRETERS,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="131 450",
                description="TIS National",
                is_24_7=True,
            ),
        ],
        website="https://www.tisnational.gov.au",
        national=True,
        is_free=True,
        languages=["160+ languages"],
    ),
    SupportService(
        name="Settlement Services International (SSI)",
        description=(
            "Settlement support for refugees and migrants. "
            "Legal help, family support, disability services."
        ),
        categories=[
            ServiceCategory.CALD_MULTICULTURAL,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="02 8799 6700",
            ),
        ],
        website="https://www.ssi.org.au",
        national=False,
        states=["NSW", "VIC", "QLD"],
        interpreter_available=True,
    ),
    SupportService(
        name="Multicultural Women's Advocacy Service",
        description=(
            "Support for multicultural women experiencing family violence. "
            "Advocacy, case management, legal support."
        ),
        categories=[
            ServiceCategory.CALD_MULTICULTURAL,
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="Various - contact via 1800RESPECT",
            ),
        ],
        website="https://www.1800respect.org.au",
        national=True,
        interpreter_available=True,
    ),
    SupportService(
        name="InTouch Multicultural Centre Against Family Violence",
        description=(
            "Specialist family violence service for migrant and "
            "refugee women in Victoria."
        ),
        categories=[
            ServiceCategory.CALD_MULTICULTURAL,
            ServiceCategory.WOMENS_SERVICES,
            ServiceCategory.DV_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 755 988",
                is_24_7=True,
            ),
        ],
        website="https://intouch.org.au",
        national=False,
        states=["VIC"],
        interpreter_available=True,
    ),
]


# =============================================================================
# ELDER ABUSE SERVICES
# =============================================================================

ELDER_SERVICES: List[SupportService] = [
    SupportService(
        name="Elder Abuse Hotline (National)",
        description=(
            "Support and information about elder abuse. " "Connects to state services."
        ),
        categories=[
            ServiceCategory.ELDER_ABUSE,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 353 374",
                description="1800 ELDERHelp",
            ),
        ],
        website="https://www.eapu.com.au",
        national=True,
        eligibility="Older Australians experiencing abuse",
    ),
    SupportService(
        name="Seniors Rights Service NSW",
        description=("Free legal and advocacy service for older people in NSW."),
        categories=[
            ServiceCategory.ELDER_ABUSE,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 424 079",
            ),
        ],
        website="https://seniorsrightsservice.org.au",
        national=False,
        states=["NSW"],
    ),
    SupportService(
        name="Seniors Rights Victoria",
        description=("Free legal help and advocacy for older Victorians."),
        categories=[
            ServiceCategory.ELDER_ABUSE,
            ServiceCategory.LEGAL_ADVOCACY,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 368 821",
            ),
        ],
        website="https://seniorsrights.org.au",
        national=False,
        states=["VIC"],
    ),
]


# =============================================================================
# 24/7 LEGAL SERVICES - HELP ANYTIME
# =============================================================================

LEGAL_SERVICES_24_7: List[SupportService] = [
    # National Services
    SupportService(
        name="LawAccess NSW",
        description=(
            "Free legal information, referrals and some legal advice. "
            "One of the largest free legal services in Australia."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 888 529",
                hours="Monday to Friday, 9am to 5pm",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.lawaccess.nsw.gov.au",
                description="Online legal chat",
            ),
        ],
        website="https://www.lawaccess.nsw.gov.au",
        national=False,
        states=["NSW"],
        is_free=True,
    ),
    SupportService(
        name="Legal Aid Queensland",
        description=(
            "Free legal help for Queenslanders. Family law, domestic violence, "
            "child protection. After-hours service available."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 65 11 88",
                hours="Monday to Friday, 9am to 5pm",
            ),
        ],
        website="https://www.legalaid.qld.gov.au",
        national=False,
        states=["QLD"],
        is_free=True,
    ),
    SupportService(
        name="Victoria Legal Aid",
        description=(
            "Free legal information and help for Victorians. "
            "Family law, family violence, child protection matters."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 792 387",
                hours="Monday to Friday, 8:45am to 5:15pm",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.legalaid.vic.gov.au/get-help/get-legal-help",
            ),
        ],
        website="https://www.legalaid.vic.gov.au",
        national=False,
        states=["VIC"],
        is_free=True,
    ),
    SupportService(
        name="Legal Services Commission SA",
        description=(
            "Free legal help for South Australians. Family law, "
            "domestic violence, child protection."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 366 424",
                hours="Monday to Friday, 9am to 5pm",
            ),
        ],
        website="https://lsc.sa.gov.au",
        national=False,
        states=["SA"],
        is_free=True,
    ),
    SupportService(
        name="Legal Aid WA",
        description=(
            "Free legal information and representation for Western Australians. "
            "Family Court duty lawyer services available."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 650 579",
                hours="Monday to Friday, 9am to 4pm",
            ),
        ],
        website="https://www.legalaid.wa.gov.au",
        national=False,
        states=["WA"],
        is_free=True,
    ),
    SupportService(
        name="Law Society Referral Services",
        description=(
            "Each state Law Society provides lawyer referral services. "
            "Can help find a family lawyer in your area."
        ),
        categories=[ServiceCategory.LEGAL_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="See state numbers below",
                description=(
                    "NSW: 02 9926 0300 | VIC: 03 9607 9311 | "
                    "QLD: 1300 367 757 | SA: 08 8229 0200 | "
                    "WA: 08 9324 8600 | TAS: 03 6234 4133"
                ),
            ),
        ],
        website="https://www.lawcouncil.asn.au",
        national=True,
    ),
    # 24/7 Emergency Legal Services
    SupportService(
        name="Police Custody Legal Advice (NSW)",
        description=(
            "24/7 free legal advice if you're arrested or in police custody. "
            "Speak to a lawyer before police interview."
        ),
        categories=[ServiceCategory.LEGAL_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 101 810",
                description="Custody Notification Service",
                is_24_7=True,
            ),
        ],
        website="https://www.legalaid.nsw.gov.au",
        national=False,
        states=["NSW"],
        is_free=True,
        eligibility="Anyone arrested or detained by police in NSW",
    ),
    SupportService(
        name="Victorian Aboriginal Legal Service (VALS)",
        description=(
            "24/7 legal help for Aboriginal Victorians. Criminal, family, "
            "and civil law. Custody notification service."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 064 865",
                description="24/7 line",
                is_24_7=True,
            ),
        ],
        website="https://www.vals.org.au",
        national=False,
        states=["VIC"],
        is_free=True,
        eligibility="Aboriginal and Torres Strait Islander people in VIC",
    ),
    SupportService(
        name="Aboriginal Legal Service NSW/ACT - Custody Notification",
        description=(
            "24/7 service for Aboriginal people in police custody. "
            "Must be contacted when Aboriginal person detained."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.ABORIGINAL_TORRES_STRAIT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 765 767",
                is_24_7=True,
            ),
        ],
        website="https://www.alsnswact.org.au",
        national=False,
        states=["NSW", "ACT"],
        is_free=True,
    ),
    # Online Legal Information (24/7 Access)
    SupportService(
        name="Family Relationships Online",
        description=(
            "Australian Government website with information about family "
            "law, separation, parenting arrangements. Available 24/7 online. "
            "Phone support during business hours."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 050 321",
                description="Family Relationship Advice Line",
                hours="Monday to Friday, 8am to 8pm. Saturday 10am to 4pm",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.familyrelationships.gov.au",
                description="24/7 online information",
                is_24_7=True,
            ),
        ],
        website="https://www.familyrelationships.gov.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Federal Circuit and Family Court Website",
        description=(
            "Official court website with forms, guides, and information "
            "available 24/7. Self-help resources for family law matters."
        ),
        categories=[ServiceCategory.LEGAL_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.fcfcoa.gov.au",
                description="24/7 information access",
                is_24_7=True,
            ),
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 352 000",
                description="Registry enquiries",
                hours="Monday to Friday, 8:30am to 4:30pm",
            ),
        ],
        website="https://www.fcfcoa.gov.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Amica (Online Separation Agreement)",
        description=(
            "Free online tool to help separating couples reach agreement "
            "on parenting and property. Available 24/7."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.amica.gov.au",
                description="24/7 online service",
                is_24_7=True,
            ),
        ],
        website="https://www.amica.gov.au",
        national=True,
        is_free=True,
        eligibility="Separating couples who can communicate respectfully",
    ),
    SupportService(
        name="National Domestic Violence Legal Service",
        description=(
            "Legal support for people experiencing domestic and family violence. "
            "Helps with intervention orders, family law, and safety."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.WOMENS_SERVICES,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 737 732",
                description="Via 1800RESPECT - ask for legal referral",
                is_24_7=True,
            ),
        ],
        website="https://www.1800respect.org.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Community Legal Centres Australia",
        description=(
            "Network of 160+ community legal centres across Australia. "
            "Free legal help for people who can't afford a lawyer. "
            "Directory to find your local centre."
        ),
        categories=[ServiceCategory.LEGAL_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://clcs.org.au/find-a-clc",
                description="Find your local CLC",
                is_24_7=True,
            ),
        ],
        website="https://clcs.org.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="National Legal Aid",
        description=(
            "Peak body for Legal Aid commissions. Links to all state "
            "Legal Aid services and eligibility checker."
        ),
        categories=[ServiceCategory.LEGAL_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.nationallegalaid.org",
                description="24/7 online directory",
                is_24_7=True,
            ),
        ],
        website="https://www.nationallegalaid.org",
        national=True,
        is_free=True,
    ),
    # Family Violence Legal Help (24/7)
    SupportService(
        name="Safe Steps Legal Service (VIC)",
        description=(
            "24/7 legal information and support for people experiencing "
            "family violence in Victoria. Intervention orders, family law."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.DV_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 015 188",
                description="24/7 crisis line - ask for legal support",
                is_24_7=True,
            ),
        ],
        website="https://www.safesteps.org.au",
        national=False,
        states=["VIC"],
        is_free=True,
    ),
    SupportService(
        name="Domestic Violence Legal Help NSW",
        description=(
            "24/7 legal support via NSW DV Line. Help with AVOs, "
            "safety planning, family law matters."
        ),
        categories=[
            ServiceCategory.LEGAL_ADVOCACY,
            ServiceCategory.DV_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 656 463",
                description="NSW DV Line - 24/7",
                is_24_7=True,
            ),
        ],
        website="https://www.legalaid.nsw.gov.au/get-legal-help/domestic-violence",
        national=False,
        states=["NSW"],
        is_free=True,
    ),
    # Duty Lawyer Services
    SupportService(
        name="Family Court Duty Lawyer Services",
        description=(
            "Free duty lawyers available at Family Court registries. "
            "Help with urgent applications, directions hearings. "
            "No appointment needed - just arrive early."
        ),
        categories=[ServiceCategory.LEGAL_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.IN_PERSON,
                value="Available at all FCFCOA registries",
                description="Arrive 30 mins before court opens",
                hours="Court sitting days only",
            ),
        ],
        website="https://www.fcfcoa.gov.au/fl/pubs/duty-lawyers",
        national=True,
        is_free=True,
        eligibility="People without legal representation",
    ),
    # After Hours Urgent Family Law
    SupportService(
        name="Family Court After Hours Service",
        description=(
            "For URGENT family law matters outside court hours. "
            "Recovery orders, urgent parenting orders, airport watch list. "
            "Only for genuine emergencies."
        ),
        categories=[ServiceCategory.LEGAL_ADVOCACY],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1300 352 000",
                description="Main registry - will provide after-hours contact",
            ),
        ],
        website="https://www.fcfcoa.gov.au/fl/pubs/after-hours",
        national=True,
        is_free=False,
        cost_notes="Court filing fees apply. Fee exemption may be available.",
        eligibility="Genuine emergencies only - child at risk of removal from Australia, etc.",
    ),
]


# =============================================================================
# HOUSING & HOMELESSNESS SERVICES
# =============================================================================

HOUSING_SERVICES: List[SupportService] = [
    SupportService(
        name="Ask Izzy",
        description=(
            "Find housing, food, money help, health services near you. "
            "Free website available 24/7. Mobile-friendly."
        ),
        categories=[
            ServiceCategory.HOUSING,
            ServiceCategory.FINANCIAL_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://askizzy.org.au",
                is_24_7=True,
            ),
        ],
        website="https://askizzy.org.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Link2Home (NSW)",
        description=(
            "NSW homelessness information and referral line. "
            "24/7 help to find emergency accommodation."
        ),
        categories=[ServiceCategory.HOUSING],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 152 152",
                is_24_7=True,
            ),
        ],
        website="https://www.facs.nsw.gov.au/housing/help",
        national=False,
        states=["NSW"],
        is_free=True,
    ),
    SupportService(
        name="Housing Connect (TAS)",
        description=(
            "Tasmania's housing and homelessness service. "
            "Help finding accommodation."
        ),
        categories=[ServiceCategory.HOUSING],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 800 588",
                hours="Monday to Friday, 9am to 5pm",
            ),
        ],
        website="https://www.housing.tas.gov.au",
        national=False,
        states=["TAS"],
        is_free=True,
    ),
    SupportService(
        name="Housing SA",
        description=(
            "South Australian housing assistance. Emergency accommodation, "
            "public housing applications."
        ),
        categories=[ServiceCategory.HOUSING],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="131 299",
                description="SA Housing Authority",
                hours="Monday to Friday, 9am to 5pm",
            ),
        ],
        website="https://www.sa.gov.au/topics/housing",
        national=False,
        states=["SA"],
        is_free=True,
    ),
]


# =============================================================================
# FINANCIAL SUPPORT SERVICES
# =============================================================================

FINANCIAL_SERVICES: List[SupportService] = [
    SupportService(
        name="National Debt Helpline",
        description=(
            "Free financial counselling for people in debt. "
            "Help with bills, loans, collection agencies."
        ),
        categories=[ServiceCategory.FINANCIAL_SUPPORT],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="1800 007 007",
                hours="Monday to Friday, 9:30am to 4:30pm",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://ndh.org.au/talk-to-us/chat-online",
            ),
        ],
        website="https://ndh.org.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Services Australia",
        description=(
            "Centrelink, Medicare, Child Support. Online services "
            "available 24/7 via myGov."
        ),
        categories=[
            ServiceCategory.FINANCIAL_SUPPORT,
            ServiceCategory.FAMILY_SUPPORT,
        ],
        contacts=[
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="136 150",
                description="Centrelink families",
                hours="Monday to Friday, 8am to 5pm",
            ),
            ContactMethod(
                channel=ContactChannel.PHONE,
                value="131 272",
                description="Child Support",
                hours="Monday to Friday, 8am to 5pm",
            ),
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://my.gov.au",
                description="24/7 online services",
                is_24_7=True,
            ),
        ],
        website="https://www.servicesaustralia.gov.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="MoneySmart",
        description=(
            "ASIC's free financial guidance. Calculators, tools, "
            "information about money matters. Available 24/7 online."
        ),
        categories=[ServiceCategory.FINANCIAL_SUPPORT],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://moneysmart.gov.au",
                is_24_7=True,
            ),
        ],
        website="https://moneysmart.gov.au",
        national=True,
        is_free=True,
    ),
    SupportService(
        name="Financial Counselling Australia",
        description=(
            "Find a free financial counsellor near you. "
            "Help with debts, bills, Centrelink issues."
        ),
        categories=[ServiceCategory.FINANCIAL_SUPPORT],
        contacts=[
            ContactMethod(
                channel=ContactChannel.WEB_CHAT,
                value="https://www.financialcounsellingaustralia.org.au/find-a-counsellor",
                is_24_7=True,
            ),
        ],
        website="https://www.financialcounsellingaustralia.org.au",
        national=True,
        is_free=True,
    ),
]


# =============================================================================
# SERVICE LOCATOR
# =============================================================================


class SupportServiceLocator:
    """
    Find support services based on user needs.

    The chatbot uses this to recommend appropriate services.
    """

    def __init__(self):
        # Build combined service list
        self.all_services: List[SupportService] = [
            KIDS_HELPLINE,
        ]
        self.all_services.extend(DISABILITY_SERVICES)
        self.all_services.extend(MENS_SERVICES)
        self.all_services.extend(WOMENS_SERVICES)
        self.all_services.extend(MENTAL_HEALTH_SERVICES)
        self.all_services.extend(LGBTIQ_SERVICES)
        self.all_services.extend(ABORIGINAL_SERVICES)
        self.all_services.extend(CALD_SERVICES)
        self.all_services.extend(ELDER_SERVICES)
        self.all_services.extend(LEGAL_SERVICES_24_7)
        self.all_services.extend(HOUSING_SERVICES)
        self.all_services.extend(FINANCIAL_SERVICES)

        # Index by category
        self.by_category: Dict[ServiceCategory, List[SupportService]] = {}
        for service in self.all_services:
            for category in service.categories:
                if category not in self.by_category:
                    self.by_category[category] = []
                self.by_category[category].append(service)

    def find_by_category(
        self,
        category: ServiceCategory,
        state: Optional[str] = None,
    ) -> List[SupportService]:
        """Find services by category, optionally filtered by state."""
        services = self.by_category.get(category, [])

        if state:
            # Return national services + state-specific
            services = [
                s
                for s in services
                if s.national or state.upper() in [st.upper() for st in s.states]
            ]

        return services

    def find_24_7(
        self,
        category: Optional[ServiceCategory] = None,
    ) -> List[SupportService]:
        """Find services available 24/7."""
        services = self.all_services
        if category:
            services = self.by_category.get(category, [])

        return [s for s in services if any(c.is_24_7 for c in s.contacts)]

    def find_by_state(self, state: str) -> List[SupportService]:
        """Find all services available in a state."""
        return [
            s
            for s in self.all_services
            if s.national or state.upper() in [st.upper() for st in s.states]
        ]

    def find_crisis_services(self) -> List[SupportService]:
        """Find crisis support services (mental health, DV, etc.)."""
        crisis_categories = [
            ServiceCategory.MENTAL_HEALTH,
            ServiceCategory.DV_SUPPORT,
            ServiceCategory.WOMENS_SHELTER,
            ServiceCategory.CHILDREN_YOUTH,
        ]

        services = []
        for category in crisis_categories:
            for s in self.by_category.get(category, []):
                if s not in services and any(c.is_24_7 for c in s.contacts):
                    services.append(s)

        return services

    def find_for_children(self) -> List[SupportService]:
        """Find services specifically for children and young people."""
        return self.by_category.get(ServiceCategory.CHILDREN_YOUTH, [])

    def find_for_disability(
        self,
        disability_type: Optional[str] = None,
    ) -> List[SupportService]:
        """Find disability advocacy services."""
        services = self.by_category.get(ServiceCategory.DISABILITY_ADVOCACY, [])

        if disability_type:
            disability_type_lower = disability_type.lower()
            if "vision" in disability_type_lower or "blind" in disability_type_lower:
                services = self.by_category.get(ServiceCategory.VISION_IMPAIRMENT, [])
            elif "hearing" in disability_type_lower or "deaf" in disability_type_lower:
                services = self.by_category.get(ServiceCategory.HEARING_IMPAIRMENT, [])

        return services

    def search(
        self,
        query: str,
        state: Optional[str] = None,
    ) -> List[SupportService]:
        """Search services by keyword."""
        query_lower = query.lower()
        results = []

        for service in self.all_services:
            # Check if matches
            if (
                query_lower in service.name.lower()
                or query_lower in service.description.lower()
            ):
                # Check state filter
                if state:
                    if service.national or state.upper() in [
                        st.upper() for st in service.states
                    ]:
                        results.append(service)
                else:
                    results.append(service)

        return results

    def find_legal_services(
        self,
        state: Optional[str] = None,
        available_24_7: bool = False,
    ) -> List[SupportService]:
        """Find legal services, optionally filtered by state and 24/7 availability."""
        services = self.by_category.get(ServiceCategory.LEGAL_ADVOCACY, [])

        results = []
        for service in services:
            # Check 24/7 filter (check contacts for 24/7 availability)
            if available_24_7:
                has_24_7_contact = any(
                    c.is_24_7
                    or "24/7" in c.hours.lower()
                    or "24 hour" in c.hours.lower()
                    for c in service.contacts
                )
                if not has_24_7_contact:
                    continue

            # Check state filter
            if state:
                if service.national or state.upper() in [
                    st.upper() for st in service.states
                ]:
                    results.append(service)
            else:
                results.append(service)

        return results

    def find_custody_help(self, state: Optional[str] = None) -> List[SupportService]:
        """Find urgent custody help services."""
        custody_services = []
        keywords = ["custody", "notification", "arrest", "police"]

        for service in self.by_category.get(ServiceCategory.LEGAL_ADVOCACY, []):
            if any(kw in service.description.lower() for kw in keywords):
                if state:
                    if service.national or state.upper() in [
                        st.upper() for st in service.states
                    ]:
                        custody_services.append(service)
                else:
                    custody_services.append(service)

        return custody_services

    def find_housing_help(self, state: Optional[str] = None) -> List[SupportService]:
        """Find housing and homelessness services."""
        services = self.by_category.get(ServiceCategory.HOUSING, [])

        if state:
            return [
                s
                for s in services
                if s.national or state.upper() in [st.upper() for st in s.states]
            ]
        return services

    def find_financial_help(self, state: Optional[str] = None) -> List[SupportService]:
        """Find financial assistance services."""
        services = self.by_category.get(ServiceCategory.FINANCIAL, [])

        if state:
            return [
                s
                for s in services
                if s.national or state.upper() in [st.upper() for st in s.states]
            ]
        return services

    def format_crisis_numbers(self) -> str:
        """Format key crisis numbers for quick reference."""
        return (
            "📞 CRISIS SUPPORT NUMBERS:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🆘 Emergency: 000\n\n"
            "Mental Health:\n"
            "  • Lifeline: 13 11 14 (24/7)\n"
            "  • Beyond Blue: 1300 22 46 36 (24/7)\n"
            "  • Suicide Call Back: 1300 659 467 (24/7)\n\n"
            "Family Violence:\n"
            "  • 1800RESPECT: 1800 737 732 (24/7)\n"
            "  • Men's Referral: 1300 766 491\n\n"
            "Children & Youth:\n"
            "  • Kids Helpline: 1800 55 1800 (24/7)\n"
            "  • Headspace: 1800 650 890\n\n"
            "Aboriginal & Torres Strait Islander:\n"
            "  • 13YARN: 13 92 76 (24/7)\n\n"
            "LGBTIQ+:\n"
            "  • QLife: 1800 184 527 (3pm-midnight)\n\n"
            "Legal Help:\n"
            "  • Legal Aid NSW: 1300 888 529 (24/7)\n"
            "  • Aboriginal Legal NSW: 1800 101 810 (custody 24/7)\n"
            "  • Family Relationships: 1800 050 321\n"
            "  • Ask for legal help via 1800RESPECT\n\n"
            "Housing:\n"
            "  • Link2Home NSW: 1800 152 152 (24/7)\n"
            "  • Ask Izzy: askizzy.org.au\n"
        )


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    locator = SupportServiceLocator()

    print("=== Kids Helpline Details ===\n")
    kh = KIDS_HELPLINE
    print(f"Name: {kh.name}")
    print(f"Description: {kh.description}")
    print("\nContact Channels:")
    for c in kh.contacts:
        print(f"  - {c.channel.value}: {c.value}")
        if c.hours:
            print(f"    Hours: {c.hours}")

    print("\n\n=== Vision Impairment Services ===\n")
    vision = locator.find_for_disability("blind")
    for s in vision:
        print(f"• {s.name}")
        primary = s.get_primary_contact()
        if primary:
            print(f"  Phone: {primary.value}")

    print("\n\n=== 24/7 Crisis Services ===\n")
    crisis = locator.find_24_7()
    for s in crisis:
        print(f"• {s.name}")

    print("\n\n=== Crisis Numbers ===\n")
    print(locator.format_crisis_numbers())
