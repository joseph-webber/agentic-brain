#!/usr/bin/env python3
"""
Child Protection & Child Support Services Integration
======================================================

Integration with:

1. CHILD PROTECTION AGENCIES (State-based)
   - NSW: Department of Communities and Justice (DCJ)
   - VIC: Department of Families, Fairness and Housing (DFFH)
   - QLD: Department of Child Safety, Seniors and Disability Services
   - SA: Department for Child Protection (DCP)
   - WA: Department of Communities - Child Protection
   - TAS: Department for Education, Children and Young People
   - ACT: Child and Youth Protection Services (CYPS)
   - NT: Territory Families

2. CHILD SUPPORT (Federal - Services Australia)
   - Child Support Registrar
   - Assessment services
   - Collection services
   - Change of assessment
   - Agreements (binding and limited)

CRITICAL FEATURES:
==================

1. MANDATORY REPORTING
   - Detect safety concerns in conversations
   - Guide users through reporting process
   - Connect with appropriate agency

2. CHILD PROTECTION INVOLVEMENT
   - Track if child protection involved in matter
   - Coordinate with case workers
   - Information sharing protocols

3. CHILD SUPPORT INTEGRATION
   - Calculate estimated child support
   - Guide through applications
   - Track payments
   - Lodge change of assessment

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CHILD PROTECTION AGENCIES
# =============================================================================


class ChildProtectionAgency(Enum):
    """State/Territory child protection agencies."""

    # NSW - Department of Communities and Justice
    NSW_DCJ = "nsw_dcj"

    # Victoria - DFFH Child Protection
    VIC_DFFH = "vic_dffh"

    # Queensland - Child Safety
    QLD_CHILD_SAFETY = "qld_child_safety"

    # South Australia - DCP
    SA_DCP = "sa_dcp"

    # Western Australia - Communities
    WA_COMMUNITIES = "wa_communities"

    # Tasmania - Children and Young People
    TAS_DECYP = "tas_decyp"

    # ACT - CYPS
    ACT_CYPS = "act_cyps"

    # Northern Territory - Territory Families
    NT_TERRITORY_FAMILIES = "nt_territory_families"


class ReportType(Enum):
    """Types of child protection reports."""

    MANDATORY_REPORT = "mandatory"  # From mandatory reporter
    VOLUNTARY_REPORT = "voluntary"  # From community member
    NOTIFICATION = "notification"  # General concern
    RISK_OF_HARM = "risk_of_harm"  # Significant risk
    IMMEDIATE_DANGER = "immediate"  # Requires immediate response


class RiskCategory(Enum):
    """Risk categories for child safety."""

    PHYSICAL_ABUSE = "physical_abuse"
    SEXUAL_ABUSE = "sexual_abuse"
    EMOTIONAL_ABUSE = "emotional_abuse"
    NEGLECT = "neglect"
    DOMESTIC_VIOLENCE_EXPOSURE = "dv_exposure"
    PARENTAL_SUBSTANCE_ABUSE = "substance_abuse"
    PARENTAL_MENTAL_HEALTH = "mental_health"
    HOMELESSNESS = "homelessness"
    EXPLOITATION = "exploitation"


@dataclass
class ChildProtectionService:
    """A child protection agency service."""

    agency: ChildProtectionAgency
    name: str
    state: str

    # Contact
    hotline: str  # 24/7 reporting line
    general_phone: str
    website: str
    online_reporting: Optional[str] = None

    # Office
    head_office_address: str = ""

    # Mandatory reporters
    mandatory_reporter_line: Optional[str] = None
    eReporting_url: Optional[str] = None  # Online reporting for mandatory reporters

    # CMMS
    cmms_type: str = "custom"

    def get_reporting_info(self) -> str:
        """Get information about how to report to this agency."""
        info = [
            f"To report a child safety concern in {self.state}:",
            f"",
            f"📞 Hotline (24/7): {self.hotline}",
        ]

        if self.mandatory_reporter_line:
            info.append(f"📞 Mandatory Reporter Line: {self.mandatory_reporter_line}")

        if self.online_reporting:
            info.append(f"🌐 Online: {self.online_reporting}")

        info.extend(
            [
                f"",
                f"In immediate danger, call 000",
            ]
        )

        return "\n".join(info)


# All state/territory child protection services
CHILD_PROTECTION_SERVICES: Dict[str, ChildProtectionService] = {
    "NSW": ChildProtectionService(
        agency=ChildProtectionAgency.NSW_DCJ,
        name="Department of Communities and Justice - Child Protection",
        state="NSW",
        hotline="132 111",  # Child Protection Helpline
        general_phone="02 9377 6000",
        website="https://www.dcj.nsw.gov.au",
        online_reporting="https://reporter.childstory.nsw.gov.au",
        mandatory_reporter_line="132 111",
        eReporting_url="https://reporter.childstory.nsw.gov.au/s/mrg",
        head_office_address="219-241 Cleveland Street, Strawberry Hills NSW 2012",
        cmms_type="custom",  # ChildStory system
    ),
    "VIC": ChildProtectionService(
        agency=ChildProtectionAgency.VIC_DFFH,
        name="Department of Families, Fairness and Housing - Child Protection",
        state="VIC",
        hotline="131 278",  # Child Protection Crisis Line
        general_phone="1300 655 795",
        website="https://services.dffh.vic.gov.au/child-protection",
        mandatory_reporter_line="1300 664 977",
        head_office_address="50 Lonsdale Street, Melbourne VIC 3000",
        cmms_type="dynamics_365",
    ),
    "QLD": ChildProtectionService(
        agency=ChildProtectionAgency.QLD_CHILD_SAFETY,
        name="Department of Child Safety, Seniors and Disability Services",
        state="QLD",
        hotline="1800 177 135",  # Child Safety Service Centre
        general_phone="13 74 68",  # 13 QGOV
        website="https://www.childsafety.qld.gov.au",
        online_reporting="https://www.childsafety.qld.gov.au/reporting-child-abuse",
        head_office_address="111 George Street, Brisbane QLD 4000",
        cmms_type="custom",
    ),
    "SA": ChildProtectionService(
        agency=ChildProtectionAgency.SA_DCP,
        name="Department for Child Protection",
        state="SA",
        hotline="131 478",  # Child Abuse Report Line (CARL)
        general_phone="08 8463 6429",
        website="https://www.childprotection.sa.gov.au",
        online_reporting="https://www.childprotection.sa.gov.au/reporting-child-abuse",
        head_office_address="31 Flinders Street, Adelaide SA 5000",
        cmms_type="custom",
    ),
    "WA": ChildProtectionService(
        agency=ChildProtectionAgency.WA_COMMUNITIES,
        name="Department of Communities - Child Protection and Family Support",
        state="WA",
        hotline="1800 622 258",  # Crisis Care
        general_phone="08 9222 2555",
        website="https://www.communities.wa.gov.au",
        mandatory_reporter_line="1800 708 704",
        head_office_address="189 Royal Street, East Perth WA 6004",
        cmms_type="custom",
    ),
    "TAS": ChildProtectionService(
        agency=ChildProtectionAgency.TAS_DECYP,
        name="Department for Education, Children and Young People - Child Safety",
        state="TAS",
        hotline="1800 000 123",  # Child Safety Service
        general_phone="1300 135 513",
        website="https://www.decyp.tas.gov.au",
        online_reporting="https://www.strongfamiliessafekids.tas.gov.au",
        head_office_address="Level 1, 22 Elizabeth Street, Hobart TAS 7000",
        cmms_type="custom",
    ),
    "ACT": ChildProtectionService(
        agency=ChildProtectionAgency.ACT_CYPS,
        name="Child and Youth Protection Services",
        state="ACT",
        hotline="1300 556 728",  # Child Concern Line
        general_phone="02 6207 1069",
        website="https://www.communityservices.act.gov.au",
        online_reporting="https://form.act.gov.au/smartforms/servlet/SmartForm.html?formCode=1153",
        head_office_address="11 Moore Street, Canberra ACT 2601",
        cmms_type="dynamics_365",
    ),
    "NT": ChildProtectionService(
        agency=ChildProtectionAgency.NT_TERRITORY_FAMILIES,
        name="Territory Families, Housing and Communities",
        state="NT",
        hotline="1800 700 250",  # Child Protection Hotline
        general_phone="08 8999 2737",
        website="https://tfhc.nt.gov.au",
        head_office_address="Darwin Plaza, 41 Smith Street Mall, Darwin NT 0800",
        cmms_type="custom",
    ),
}


# =============================================================================
# CHILD SUPPORT (SERVICES AUSTRALIA)
# =============================================================================


class ChildSupportCaseType(Enum):
    """Types of child support cases."""

    ASSESSMENT = "assessment"  # Administrative assessment
    COLLECTION = "collection"  # Services Australia collects
    PRIVATE_COLLECTION = "private"  # Parents arrange directly
    BINDING_AGREEMENT = "binding"  # Binding child support agreement
    LIMITED_AGREEMENT = "limited"  # Limited child support agreement


class ChildSupportAction(Enum):
    """Actions available through Child Support."""

    NEW_ASSESSMENT = "new_assessment"
    CHANGE_ASSESSMENT = "change_assessment"
    OBJECT_TO_DECISION = "object"
    COLLECT_CHILD_SUPPORT = "collect"
    STOP_COLLECTION = "stop_collection"
    ESTIMATE_INCOME = "estimate"
    REGISTER_AGREEMENT = "register_agreement"
    ENFORCE_PAYMENT = "enforce"


@dataclass
class ChildSupportCalculation:
    """
    Child Support assessment calculation.

    Based on the Child Support Formula:
    1. Work out each parent's child support income
    2. Work out combined child support income
    3. Work out each parent's income percentage
    4. Work out each parent's cost percentage
    5. Work out each parent's child support percentage
    6. Work out costs of children
    7. Work out child support amount
    """

    # Parents
    parent1_name: str = ""
    parent2_name: str = ""

    # Income (adjusted taxable income - self-support amount)
    parent1_income: Decimal = Decimal("0")
    parent2_income: Decimal = Decimal("0")

    # Care percentages
    parent1_care_percent: int = 50  # % of nights
    parent2_care_percent: int = 50

    # Children
    children_ages: List[int] = field(default_factory=list)

    # Results
    annual_child_support: Decimal = Decimal("0")
    monthly_child_support: Decimal = Decimal("0")
    paying_parent: str = ""

    # Self-support amount (2024-25)
    SELF_SUPPORT_AMOUNT: Decimal = Decimal("28463")

    def calculate(self) -> Decimal:
        """
        Calculate estimated child support.

        Note: This is a simplified calculation for estimation only.
        Actual assessment by Child Support considers many more factors.
        """
        # Adjust incomes (subtract self-support)
        p1_csi = max(Decimal("0"), self.parent1_income - self.SELF_SUPPORT_AMOUNT)
        p2_csi = max(Decimal("0"), self.parent2_income - self.SELF_SUPPORT_AMOUNT)

        combined_income = p1_csi + p2_csi

        if combined_income == 0:
            return Decimal("0")

        # Income percentages
        p1_income_percent = (p1_csi / combined_income) * 100
        p2_income_percent = (p2_csi / combined_income) * 100

        # Cost percentages (based on care)
        p1_cost_percent = self._care_to_cost_percent(self.parent1_care_percent)
        p2_cost_percent = self._care_to_cost_percent(self.parent2_care_percent)

        # Child support percentages
        p1_cs_percent = p1_income_percent - p1_cost_percent
        p2_cs_percent = p2_income_percent - p2_cost_percent

        # Cost of children (using basic formula - actual uses tables)
        num_children = len(self.children_ages)
        cost_of_children = self._estimate_cost_of_children(
            combined_income, num_children
        )

        # Determine payer and amount
        if p1_cs_percent > 0:
            self.paying_parent = self.parent1_name
            self.annual_child_support = cost_of_children * Decimal(p1_cs_percent) / 100
        else:
            self.paying_parent = self.parent2_name
            self.annual_child_support = cost_of_children * Decimal(-p1_cs_percent) / 100

        self.annual_child_support = max(Decimal("0"), self.annual_child_support)
        self.monthly_child_support = self.annual_child_support / 12

        return self.annual_child_support

    def _care_to_cost_percent(self, care_percent: int) -> Decimal:
        """Convert care percentage to cost percentage."""
        # Simplified - actual formula more complex
        if care_percent < 14:
            return Decimal("0")
        elif care_percent < 35:
            return Decimal("24")
        elif care_percent < 48:
            return Decimal("25") + (Decimal(care_percent) - 35) * Decimal("2")
        elif care_percent <= 52:
            return Decimal("50")
        elif care_percent < 66:
            return Decimal("51") + (Decimal(care_percent) - 53) * Decimal("2")
        elif care_percent < 87:
            return Decimal("76")
        else:
            return Decimal("100")

    def _estimate_cost_of_children(
        self,
        combined_income: Decimal,
        num_children: int,
    ) -> Decimal:
        """
        Estimate cost of children.

        Uses simplified formula - actual uses Costs of Children tables.
        """
        # Basic percentages (very simplified)
        if num_children == 1:
            percent = Decimal("17")
        elif num_children == 2:
            percent = Decimal("24")
        elif num_children == 3:
            percent = Decimal("27")
        else:
            percent = Decimal("30")

        # Cap at income cap
        income_cap = Decimal("200000")  # Simplified cap
        capped_income = min(combined_income, income_cap)

        return capped_income * percent / 100


@dataclass
class ChildSupportService:
    """Services Australia Child Support service details."""

    name: str = "Child Support - Services Australia"

    # Contact
    general_phone: str = "131 272"
    international_phone: str = "+61 3 6222 3227"
    website: str = "https://www.servicesaustralia.gov.au/child-support"

    # Online services
    online_services: str = "https://my.gov.au"
    express_plus_app: str = "Express Plus Child Support app"

    # Office hours
    phone_hours: str = "Monday to Friday, 8am to 5pm (local time)"

    # Forms
    forms_url: str = "https://www.servicesaustralia.gov.au/forms-for-child-support"

    # Key forms
    KEY_FORMS: Dict[str, str] = field(
        default_factory=lambda: {
            "application_assessment": "CS1601 - Application for Assessment",
            "estimate_income": "CS1659 - Estimate of Income",
            "change_assessment": "CS1970 - Change of Assessment Application",
            "agreement_binding": "CS1590 - Child Support Agreement",
            "object_decision": "CS1958 - Objection to Decision",
            "collect_child_support": "CS1671 - Collect Child Support",
            "election_end_collection": "CS1672 - Election to End Collection",
        }
    )

    def get_service_info(self) -> str:
        """Get child support service information."""
        return (
            f"CHILD SUPPORT - SERVICES AUSTRALIA\n"
            f"===================================\n\n"
            f"📞 Phone: {self.general_phone}\n"
            f"🕐 Hours: {self.phone_hours}\n"
            f"🌐 Website: {self.website}\n"
            f"📱 App: {self.express_plus_app}\n"
            f"💻 Online: {self.online_services}\n\n"
            f"Child Support helps parents share the costs of raising children "
            f"after separation."
        )


# =============================================================================
# CHILD PROTECTION INTEGRATION
# =============================================================================


class ChildProtectionIntegration:
    """
    Integration with child protection agencies.

    Used when:
    - Safety concerns detected in conversation
    - Child protection involved in family law matter
    - Mandatory reporting required
    - Information sharing needed
    """

    def __init__(self):
        self.services = CHILD_PROTECTION_SERVICES

    def get_agency_for_state(self, state: str) -> Optional[ChildProtectionService]:
        """Get the child protection agency for a state."""
        return self.services.get(state.upper())

    def get_reporting_info(self, state: str) -> str:
        """Get information about how to report concerns in a state."""
        agency = self.get_agency_for_state(state)
        if agency:
            return agency.get_reporting_info()
        return "State not found. For emergencies, call 000."

    def detect_safety_concerns(self, message: str) -> List[RiskCategory]:
        """
        Detect potential child safety concerns in a message.

        Returns list of detected risk categories.
        """
        concerns = []
        message_lower = message.lower()

        # Physical abuse indicators
        physical_keywords = [
            "hit",
            "hitting",
            "hits",
            "beat",
            "beating",
            "punch",
            "kick",
            "bruise",
            "bruises",
            "mark",
            "marks",
            "hurt",
            "hurts",
            "injury",
            "injuries",
            "burn",
            "burns",
            "broken",
            "fracture",
        ]
        if any(kw in message_lower for kw in physical_keywords):
            concerns.append(RiskCategory.PHYSICAL_ABUSE)

        # Sexual abuse indicators
        sexual_keywords = [
            "touched inappropriately",
            "sexual",
            "molest",
            "abuse",
            "inappropriate touching",
            "expose",
            "naked",
        ]
        if any(kw in message_lower for kw in sexual_keywords):
            concerns.append(RiskCategory.SEXUAL_ABUSE)

        # Neglect indicators
        neglect_keywords = [
            "not fed",
            "hungry",
            "starving",
            "no food",
            "dirty",
            "unwashed",
            "clothes",
            "supervision",
            "alone",
            "unsupervised",
            "abandoned",
            "left",
            "medical",
            "school",
            "truant",
        ]
        if any(kw in message_lower for kw in neglect_keywords):
            concerns.append(RiskCategory.NEGLECT)

        # DV exposure
        dv_keywords = [
            "violence",
            "violent",
            "domestic violence",
            "dv",
            "witness",
            "saw",
            "heard",
            "fighting",
            "screaming",
            "police",
            "avo",
            "dvo",
            "apprehended",
            "scared",
        ]
        if any(kw in message_lower for kw in dv_keywords):
            concerns.append(RiskCategory.DOMESTIC_VIOLENCE_EXPOSURE)

        # Substance abuse
        substance_keywords = [
            "drunk",
            "drinking",
            "alcohol",
            "drugs",
            "high",
            "stoned",
            "using",
            "addiction",
            "addict",
            "ice",
            "meth",
            "heroin",
        ]
        if any(kw in message_lower for kw in substance_keywords):
            concerns.append(RiskCategory.PARENTAL_SUBSTANCE_ABUSE)

        # Mental health
        mh_keywords = [
            "mental health",
            "depressed",
            "depression",
            "suicide",
            "suicidal",
            "psychotic",
            "delusional",
            "paranoid",
            "can't cope",
            "breakdown",
        ]
        if any(kw in message_lower for kw in mh_keywords):
            concerns.append(RiskCategory.PARENTAL_MENTAL_HEALTH)

        return concerns

    def generate_safety_response(
        self,
        concerns: List[RiskCategory],
        state: str,
    ) -> str:
        """Generate appropriate safety response based on concerns."""
        agency = self.get_agency_for_state(state)

        if (
            RiskCategory.PHYSICAL_ABUSE in concerns
            or RiskCategory.SEXUAL_ABUSE in concerns
        ):
            # High priority - immediate reporting needed
            response = (
                "⚠️ IMPORTANT CHILD SAFETY INFORMATION\n\n"
                "Based on what you've shared, there may be concerns about "
                "a child's safety that should be reported.\n\n"
            )

            if agency:
                response += f"In {state}, you can report to:\n"
                response += f"📞 {agency.hotline} (24/7)\n\n"

            response += (
                "If a child is in immediate danger, call 000.\n\n"
                "You don't need to be certain - if you're worried, report it. "
                "Child protection will investigate."
            )

        elif RiskCategory.DOMESTIC_VIOLENCE_EXPOSURE in concerns:
            response = (
                "I understand there may be family violence concerns.\n\n"
                "Children who witness violence are also affected. "
                "Support is available:\n\n"
                "📞 1800RESPECT: 1800 737 732 (24/7)\n"
            )

            if agency:
                response += f"📞 {state} Child Protection: {agency.hotline}\n"

            response += "\nWould you like information about safety planning?"

        else:
            response = (
                "It sounds like there may be concerns about a child's wellbeing.\n\n"
                "Support services are available:\n\n"
            )

            if agency:
                response += f"📞 {state} Child Protection: {agency.hotline}\n"

            response += (
                "📞 Parentline: 1300 30 1300\n" "📞 Kids Helpline: 1800 55 1800\n"
            )

        return response

    def is_mandatory_reporter(self, profession: str) -> bool:
        """Check if a profession is a mandatory reporter."""
        mandatory_reporters = [
            "teacher",
            "school",
            "principal",
            "education",
            "doctor",
            "nurse",
            "health",
            "medical",
            "hospital",
            "police",
            "officer",
            "psychologist",
            "counsellor",
            "social worker",
            "childcare",
            "early childhood",
            "minister",
            "clergy",
        ]

        profession_lower = profession.lower()
        return any(mr in profession_lower for mr in mandatory_reporters)


# =============================================================================
# CHILD SUPPORT INTEGRATION
# =============================================================================


class ChildSupportIntegration:
    """
    Integration with Services Australia Child Support.

    Features:
    - Estimate child support payments
    - Guide through applications
    - Information about agreements
    - Change of assessment guidance
    """

    def __init__(self):
        self.service = ChildSupportService()

    def estimate_child_support(
        self,
        parent1_income: float,
        parent2_income: float,
        parent1_care_percent: int,
        children_ages: List[int],
        parent1_name: str = "Parent 1",
        parent2_name: str = "Parent 2",
    ) -> Dict[str, Any]:
        """
        Estimate child support payments.

        Returns estimate and explanation.
        """
        calc = ChildSupportCalculation(
            parent1_name=parent1_name,
            parent2_name=parent2_name,
            parent1_income=Decimal(str(parent1_income)),
            parent2_income=Decimal(str(parent2_income)),
            parent1_care_percent=parent1_care_percent,
            parent2_care_percent=100 - parent1_care_percent,
            children_ages=children_ages,
        )

        annual = calc.calculate()
        monthly = annual / 12

        return {
            "annual_amount": float(annual),
            "monthly_amount": float(monthly),
            "paying_parent": calc.paying_parent,
            "number_of_children": len(children_ages),
            "explanation": (
                f"Based on the information provided:\n\n"
                f"Estimated annual child support: ${float(annual):,.2f}\n"
                f"Estimated monthly: ${float(monthly):,.2f}\n"
                f"Paying parent: {calc.paying_parent}\n\n"
                f"⚠️ This is an ESTIMATE only. Actual assessment by "
                f"Child Support may differ based on:\n"
                f"- Exact care arrangements\n"
                f"- Other dependents\n"
                f"- Special circumstances\n"
                f"- Costs of children tables\n\n"
                f"For accurate assessment, contact Child Support: {self.service.general_phone}"
            ),
            "disclaimer": (
                "This estimate is for information only. It is not an official "
                "assessment and should not be relied upon for legal or financial "
                "decisions. Contact Services Australia Child Support for an "
                "official assessment."
            ),
        }

    def get_application_guidance(self, situation: str) -> str:
        """Get guidance for child support applications."""
        situation_lower = situation.lower()

        if "new" in situation_lower or "apply" in situation_lower:
            return (
                "TO APPLY FOR CHILD SUPPORT ASSESSMENT:\n\n"
                "1. Gather required information:\n"
                "   - Your tax file number\n"
                "   - The other parent's details\n"
                "   - Children's birth certificates\n"
                "   - Care arrangement details\n"
                "   - Your income information\n\n"
                "2. Apply online via myGov (linked to Services Australia)\n"
                "   OR call 131 272\n"
                "   OR complete form CS1601\n\n"
                "3. Child Support will contact the other parent\n\n"
                "4. Assessment usually takes 4-6 weeks\n\n"
                f"More info: {self.service.website}"
            )

        elif "change" in situation_lower or "circumstances" in situation_lower:
            return (
                "TO CHANGE YOUR CHILD SUPPORT ASSESSMENT:\n\n"
                "You can apply for a Change of Assessment if:\n"
                "- Your income has changed significantly\n"
                "- Care arrangements have changed\n"
                "- Special circumstances exist\n"
                "- Costs exceed the formula amount\n\n"
                "Reasons for change (Section 117 factors):\n"
                "1. High costs of contact with child\n"
                "2. Child's special needs\n"
                "3. High costs of education\n"
                "4. Child's income/earning capacity\n"
                "5. Property/assets of parent\n"
                "6. Parent's capacity to earn income\n"
                "7. Parent's necessary commitments\n"
                "8. High childcare costs\n"
                "9. Responsibility for other children\n"
                "10. Other special circumstances\n\n"
                "Apply via myGov or form CS1970\n"
                "Phone: 131 272"
            )

        elif "agreement" in situation_lower:
            return (
                "CHILD SUPPORT AGREEMENTS:\n\n"
                "Two types:\n\n"
                "1. BINDING AGREEMENT (BCA)\n"
                "   - Both parents must have legal advice\n"
                "   - Lawyers sign certificates\n"
                "   - Hard to change once made\n"
                "   - Can be above or below formula\n"
                "   - Form CS1590\n\n"
                "2. LIMITED AGREEMENT (LCA)\n"
                "   - No legal advice required\n"
                "   - Must be at least formula amount\n"
                "   - Easier to change/end\n"
                "   - Can be ended after 3 years\n\n"
                "Both must be registered with Child Support\n"
                "Phone: 131 272"
            )

        elif "collect" in situation_lower or "enforce" in situation_lower:
            return (
                "CHILD SUPPORT COLLECTION:\n\n"
                "If the paying parent doesn't pay:\n\n"
                "1. Register for collection by Child Support:\n"
                "   - Form CS1671 or call 131 272\n"
                "   - Child Support can collect from employer\n\n"
                "2. Enforcement options:\n"
                "   - Employer withholding (pay deductions)\n"
                "   - Tax refund interception\n"
                "   - Departure prohibition order (stop travel)\n"
                "   - Court enforcement\n\n"
                "3. If private collect not working:\n"
                "   - Can switch to Child Support collect\n"
                "   - No cost to receiving parent\n\n"
                "Phone: 131 272"
            )

        else:
            return self.service.get_service_info()

    def get_care_percentage_guidance(self) -> str:
        """Get information about care percentages."""
        return (
            "CARE PERCENTAGES IN CHILD SUPPORT:\n\n"
            "Care % is based on nights with each parent:\n\n"
            "| Nights/year | Care % | Cost % |\n"
            "|-------------|--------|--------|\n"
            "| 0-51        | 0-13%  | Nil    |\n"
            "| 52-127      | 14-34% | 24%    |\n"
            "| 128-175     | 35-47% | 25-49% |\n"
            "| 176-189     | 48-52% | 50%    |\n"
            "| 190-237     | 53-65% | 51-75% |\n"
            "| 238-313     | 66-86% | 76%    |\n"
            "| 314-365     | 87-100%| 100%   |\n\n"
            "Example care arrangements:\n"
            "- Every second weekend = approx 14%\n"
            "- Week on/week off = 50%\n"
            "- One weeknight + every second weekend = approx 20%\n\n"
            "Child Support assesses actual care, not what orders say."
        )


# =============================================================================
# COMBINED CHILD SERVICES LOCATOR
# =============================================================================


class ChildServicesLocator:
    """
    Find all child-related services in one place.

    - Child protection
    - Child support
    - Children's contact centres
    - Family support services
    """

    def __init__(self):
        self.child_protection = ChildProtectionIntegration()
        self.child_support = ChildSupportIntegration()

    def get_all_services_for_state(self, state: str) -> Dict[str, Any]:
        """Get all child services for a state."""
        cp_agency = self.child_protection.get_agency_for_state(state)

        return {
            "state": state,
            "child_protection": {
                "agency": cp_agency.name if cp_agency else "Not found",
                "hotline": cp_agency.hotline if cp_agency else "Not available",
                "website": cp_agency.website if cp_agency else None,
            },
            "child_support": {
                "phone": "131 272",
                "website": "https://www.servicesaustralia.gov.au/child-support",
            },
            "kids_helpline": {
                "phone": "1800 55 1800",
                "website": "https://kidshelpline.com.au",
            },
            "parentline": {
                "phone": "1300 30 1300",
                "description": "Support for parents",
            },
        }

    def format_for_voiceover(self, state: str) -> str:
        """Format services info for screen readers."""
        services = self.get_all_services_for_state(state)

        lines = [
            f"Child services in {state}.",
            f"Child protection hotline: {services['child_protection']['hotline']}.",
            f"Child Support: 1 3 1 2 7 2.",
            f"Kids Helpline: 1 8 hundred 5 5 1 8 hundred.",
            f"Parent Line: 1 3 hundred 30 1 3 hundred.",
        ]

        return " ".join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=== Child Protection Services ===\n")

    cp = ChildProtectionIntegration()

    # Get NSW reporting info
    print(cp.get_reporting_info("NSW"))
    print()

    # Detect concerns
    message = "I'm worried because my ex has been drinking heavily and the kids said they saw him hit the wall"
    concerns = cp.detect_safety_concerns(message)
    print(f"Detected concerns: {[c.value for c in concerns]}")
    print()
    print(cp.generate_safety_response(concerns, "NSW"))

    print("\n\n=== Child Support Services ===\n")

    cs = ChildSupportIntegration()

    # Estimate calculation
    estimate = cs.estimate_child_support(
        parent1_income=85000,
        parent2_income=45000,
        parent1_care_percent=35,  # Every second weekend + one night
        children_ages=[8, 5],
        parent1_name="Dad",
        parent2_name="Mum",
    )

    print(estimate["explanation"])

    print("\n\n=== All Services ===\n")

    locator = ChildServicesLocator()
    services = locator.get_all_services_for_state("SA")
    print(f"Services in SA: {services}")
