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
Citizen Services Agent for Government Portals.

An AI assistant for government citizen services portals:
- Multi-department access control
- Privacy Act compliance hooks
- Essential Eight security alignment
- Comprehensive audit trails
- myGov-style service integration

Key patterns demonstrated:
- Cross-department authorisation
- Privacy impact assessment hooks
- ASD Essential Eight compliance
- Government service orchestration
- Citizen identity verification patterns

Usage:
    python examples/enterprise/government_portal.py

Requirements:
    pip install agentic-brain

Notes:
    - Designed for Australian Government digital services
    - Privacy Act 1988 compliance patterns
    - Essential Eight security controls integration
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
    current_user,
    User,
)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("gov.citizen_services")


# =============================================================================
# GOVERNMENT DEPARTMENT DEFINITIONS
# =============================================================================


class Department(str, Enum):
    """Australian Government departments."""

    ATO = "ato"  # Australian Taxation Office
    CENTRELINK = "centrelink"  # Services Australia - Centrelink
    MEDICARE = "medicare"  # Services Australia - Medicare
    DVA = "dva"  # Department of Veterans' Affairs
    HOME_AFFAIRS = "home_affairs"  # Department of Home Affairs
    NDIS = "ndis"  # National Disability Insurance Scheme
    CHILD_SUPPORT = "child_support"  # Child Support
    AGED_CARE = "aged_care"  # My Aged Care


class ServiceCategory(str, Enum):
    """Government service categories."""

    TAXATION = "taxation"
    SOCIAL_SERVICES = "social_services"
    HEALTH = "health"
    IMMIGRATION = "immigration"
    DISABILITY = "disability"
    FAMILY = "family"
    AGED_CARE = "aged_care"
    VETERANS = "veterans"


# =============================================================================
# ESSENTIAL EIGHT COMPLIANCE
# =============================================================================


class EssentialEightControl(str, Enum):
    """ASD Essential Eight security controls."""

    APPLICATION_CONTROL = "application_control"
    PATCH_APPLICATIONS = "patch_applications"
    OFFICE_MACROS = "configure_office_macros"
    USER_APP_HARDENING = "user_application_hardening"
    RESTRICT_ADMIN = "restrict_admin_privileges"
    PATCH_OS = "patch_operating_systems"
    MFA = "multi_factor_authentication"
    BACKUPS = "regular_backups"


@dataclass
class EssentialEightStatus:
    """Essential Eight maturity status."""

    control: EssentialEightControl
    maturity_level: int  # 0-3 (0=not implemented, 3=optimised)
    last_assessed: datetime
    notes: str = ""

    def is_compliant(self, minimum_level: int = 2) -> bool:
        """Check if control meets minimum maturity level."""
        return self.maturity_level >= minimum_level


class EssentialEightCompliance:
    """Track and enforce Essential Eight compliance."""

    def __init__(self):
        # Default: all controls at maturity level 2
        self._status: dict[EssentialEightControl, EssentialEightStatus] = {}
        self._init_defaults()

    def _init_defaults(self):
        """Initialise default compliance status."""
        now = datetime.now(timezone.utc)
        for control in EssentialEightControl:
            self._status[control] = EssentialEightStatus(
                control=control,
                maturity_level=2,
                last_assessed=now,
                notes="Initial assessment",
            )

        # MFA at level 3 (required for government)
        self._status[EssentialEightControl.MFA].maturity_level = 3

    def check_compliance(self, minimum_level: int = 2) -> dict[str, Any]:
        """Check overall compliance status."""
        compliant = []
        non_compliant = []

        for control, status in self._status.items():
            if status.is_compliant(minimum_level):
                compliant.append(control.value)
            else:
                non_compliant.append(
                    {
                        "control": control.value,
                        "current_level": status.maturity_level,
                        "required_level": minimum_level,
                    }
                )

        return {
            "compliant": len(non_compliant) == 0,
            "controls_compliant": len(compliant),
            "controls_total": len(self._status),
            "non_compliant_controls": non_compliant,
        }

    def require_mfa(self) -> bool:
        """Check if MFA control requires multi-factor auth."""
        return self._status[EssentialEightControl.MFA].maturity_level >= 2

    def get_status_report(self) -> list[dict]:
        """Generate compliance status report."""
        return [
            {
                "control": s.control.value,
                "maturity_level": s.maturity_level,
                "last_assessed": s.last_assessed.isoformat(),
                "compliant_level_2": s.is_compliant(2),
            }
            for s in self._status.values()
        ]


# =============================================================================
# PRIVACY ACT COMPLIANCE
# =============================================================================


@dataclass
class PrivacyImpactAssessment:
    """Privacy Impact Assessment (PIA) record."""

    assessment_id: str
    data_type: str
    purpose: str
    collection_method: str
    storage_location: str
    retention_period_days: int
    third_party_sharing: bool
    assessed_by: str
    assessed_at: datetime
    risk_level: str  # "low", "medium", "high"
    approved: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "assessment_id": self.assessment_id,
            "data_type": self.data_type,
            "purpose": self.purpose,
            "risk_level": self.risk_level,
            "approved": self.approved,
        }


class PrivacyActCompliance:
    """
    Privacy Act 1988 compliance hooks.

    Australian Privacy Principles (APPs) implementation:
    - APP 1: Open and transparent management
    - APP 3: Collection of solicited personal information
    - APP 5: Notification of collection
    - APP 6: Use or disclosure of personal information
    - APP 11: Security of personal information
    - APP 12: Access to personal information
    """

    def __init__(self):
        self._pia_registry: dict[str, PrivacyImpactAssessment] = {}
        self._access_log: list[dict] = []

    def register_collection(
        self,
        data_type: str,
        purpose: str,
        citizen_id: str,
        collection_method: str = "online_form",
    ) -> dict[str, Any]:
        """
        Register personal information collection (APP 3).

        Returns notification text for citizen (APP 5).
        """
        notification = {
            "app_5_notification": True,
            "message": f"We are collecting your {data_type} for the purpose of {purpose}. "
            f"This information is collected under [relevant Act]. "
            f"You may access your information at any time.",
            "data_type": data_type,
            "purpose": purpose,
            "access_rights": "You have the right to access and correct your personal information.",
        }

        logger.info(
            f"APP3/5: Registered collection of {data_type} for citizen {citizen_id[:8]}..."
        )
        return notification

    def check_use_permitted(
        self,
        citizen_id: str,
        data_type: str,
        intended_use: str,
        original_purpose: str,
    ) -> tuple[bool, str]:
        """
        Check if use of personal information is permitted (APP 6).

        Returns (permitted, reason).
        """
        # Use for original purpose always permitted
        if intended_use == original_purpose:
            return True, "Use for original collection purpose"

        # Check for related secondary purposes
        related_purposes = {
            "taxation": ["audit", "compliance_check", "refund_processing"],
            "benefits": ["eligibility_check", "payment_processing", "review"],
            "health": ["treatment", "medicare_claim", "healthcare_planning"],
        }

        for category, purposes in related_purposes.items():
            if original_purpose in purposes and intended_use in purposes:
                return True, f"Related secondary purpose under {category}"

        # Require explicit consent for unrelated purposes
        return False, "Consent required for unrelated use"

    def log_access(
        self,
        citizen_id: str,
        data_type: str,
        accessed_by: str,
        department: Department,
        purpose: str,
    ):
        """Log access to personal information (APP 11 audit trail)."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "citizen_id_hash": hashlib.sha256(citizen_id.encode()).hexdigest()[:16],
            "data_type": data_type,
            "accessed_by": accessed_by,
            "department": department.value,
            "purpose": purpose,
        }
        self._access_log.append(entry)
        logger.info(f"APP11: Access logged - {data_type} by {department.value}")

    def citizen_access_request(self, citizen_id: str) -> list[dict]:
        """
        Handle citizen access request (APP 12).

        Returns all access logs for the citizen.
        """
        citizen_hash = hashlib.sha256(citizen_id.encode()).hexdigest()[:16]
        return [
            entry
            for entry in self._access_log
            if entry["citizen_id_hash"] == citizen_hash
        ]


# =============================================================================
# CITIZEN DATA MODELS
# =============================================================================


@dataclass
class Citizen:
    """Citizen profile with linked services."""

    citizen_id: str
    given_names: str
    family_name: str
    date_of_birth: datetime
    linked_services: list[Department] = field(default_factory=list)
    mfa_enabled: bool = True
    identity_strength: str = "standard"  # "basic", "standard", "strong"
    last_verified: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        return f"{self.given_names} {self.family_name}"


@dataclass
class ServiceRequest:
    """Citizen service request."""

    request_id: str
    citizen_id: str
    department: Department
    category: ServiceCategory
    request_type: str
    status: str  # "pending", "processing", "completed", "rejected"
    created_at: datetime
    updated_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# DEPARTMENT AUTHORISATION
# =============================================================================


class DepartmentAuthorisation:
    """
    Cross-department authorisation service.

    Implements principle of least privilege:
    - Each department can only access its own data
    - Cross-department access requires explicit authorisation
    - All access is logged
    """

    # Department data access matrix
    ACCESS_MATRIX = {
        Department.ATO: [ServiceCategory.TAXATION],
        Department.CENTRELINK: [
            ServiceCategory.SOCIAL_SERVICES,
            ServiceCategory.FAMILY,
        ],
        Department.MEDICARE: [ServiceCategory.HEALTH],
        Department.DVA: [ServiceCategory.VETERANS, ServiceCategory.HEALTH],
        Department.HOME_AFFAIRS: [ServiceCategory.IMMIGRATION],
        Department.NDIS: [ServiceCategory.DISABILITY],
        Department.CHILD_SUPPORT: [ServiceCategory.FAMILY],
        Department.AGED_CARE: [ServiceCategory.AGED_CARE, ServiceCategory.HEALTH],
    }

    def __init__(self, privacy: PrivacyActCompliance):
        self._privacy = privacy
        self._cross_dept_authorisations: list[dict] = []

    def check_access(
        self,
        department: Department,
        category: ServiceCategory,
        citizen_id: str,
        purpose: str,
    ) -> tuple[bool, str]:
        """
        Check if department can access service category data.

        Returns (permitted, reason).
        """
        allowed_categories = self.ACCESS_MATRIX.get(department, [])

        if category in allowed_categories:
            # Log the access
            self._privacy.log_access(
                citizen_id=citizen_id,
                data_type=category.value,
                accessed_by="system",
                department=department,
                purpose=purpose,
            )
            return True, "Department authorised for category"

        # Check for cross-department authorisation
        for auth in self._cross_dept_authorisations:
            if (
                auth["from_dept"] == department.value
                and auth["to_category"] == category.value
                and auth["citizen_id"] == citizen_id
                and auth["expires_at"] > datetime.now(timezone.utc)
            ):
                return True, "Cross-department authorisation active"

        return (
            False,
            f"Department {department.value} not authorised for {category.value}",
        )

    def request_cross_department_access(
        self,
        requesting_dept: Department,
        target_category: ServiceCategory,
        citizen_id: str,
        purpose: str,
        duration_hours: int = 24,
    ) -> dict[str, Any]:
        """
        Request temporary cross-department access.

        In production, this would require human approval.
        """
        auth = {
            "auth_id": str(uuid.uuid4()),
            "from_dept": requesting_dept.value,
            "to_category": target_category.value,
            "citizen_id": citizen_id,
            "purpose": purpose,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=duration_hours),
            "status": "pending_approval",
        }

        logger.info(
            f"Cross-department access request: {requesting_dept.value} -> {target_category.value}"
        )

        # In demo, auto-approve
        auth["status"] = "approved"
        self._cross_dept_authorisations.append(auth)

        return auth


# =============================================================================
# CITIZEN SERVICES AGENT
# =============================================================================


class CitizenServicesAgent:
    """
    AI agent for government citizen services.

    Integrates with multiple government departments while
    maintaining privacy and security compliance.
    """

    def __init__(
        self,
        essential_eight: EssentialEightCompliance,
        privacy: PrivacyActCompliance,
        dept_auth: DepartmentAuthorisation,
    ):
        self._e8 = essential_eight
        self._privacy = privacy
        self._dept_auth = dept_auth
        self._citizens: dict[str, Citizen] = {}
        self._service_requests: list[ServiceRequest] = []

        self._init_sample_data()

    def _init_sample_data(self):
        """Initialise sample citizens and services."""
        self._citizens["CIT-001"] = Citizen(
            citizen_id="CIT-001",
            given_names="Emma",
            family_name="Wilson",
            date_of_birth=datetime(1985, 3, 15),
            linked_services=[
                Department.ATO,
                Department.MEDICARE,
                Department.CENTRELINK,
            ],
            identity_strength="strong",
            last_verified=datetime.now(timezone.utc) - timedelta(days=30),
        )

        self._citizens["CIT-002"] = Citizen(
            citizen_id="CIT-002",
            given_names="David",
            family_name="Chen",
            date_of_birth=datetime(1990, 7, 22),
            linked_services=[Department.ATO, Department.MEDICARE],
            identity_strength="standard",
        )

    def verify_identity(
        self,
        citizen_id: str,
        verification_method: str = "document_verification",
    ) -> dict[str, Any]:
        """
        Verify citizen identity.

        Implements identity proofing standards.
        """
        citizen = self._citizens.get(citizen_id)
        if not citizen:
            return {"verified": False, "error": "Citizen not found"}

        # Check MFA requirement (Essential Eight)
        if self._e8.require_mfa() and not citizen.mfa_enabled:
            return {
                "verified": False,
                "error": "MFA required",
                "action_required": "Please enable multi-factor authentication",
            }

        # Update verification timestamp
        citizen.last_verified = datetime.now(timezone.utc)

        logger.info(f"Identity verified: {citizen_id} via {verification_method}")

        return {
            "verified": True,
            "citizen_id": citizen_id,
            "name": citizen.full_name,
            "identity_strength": citizen.identity_strength,
            "linked_services": [d.value for d in citizen.linked_services],
        }

    def get_linked_services(self, citizen_id: str) -> dict[str, Any]:
        """Get all services linked to citizen account."""
        citizen = self._citizens.get(citizen_id)
        if not citizen:
            return {"error": "Citizen not found"}

        services = []
        for dept in citizen.linked_services:
            services.append(
                {
                    "department": dept.value,
                    "name": dept.name.replace("_", " ").title(),
                    "categories": [
                        c.value
                        for c in DepartmentAuthorisation.ACCESS_MATRIX.get(dept, [])
                    ],
                }
            )

        return {
            "citizen_id": citizen_id,
            "services": services,
            "total_linked": len(services),
        }

    def submit_service_request(
        self,
        citizen_id: str,
        department: Department,
        request_type: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Submit a service request.

        Includes Privacy Act notification.
        """
        citizen = self._citizens.get(citizen_id)
        if not citizen:
            return {"error": "Citizen not found"}

        # Check citizen has linked this service
        if department not in citizen.linked_services:
            return {
                "error": "Service not linked",
                "message": f"Please link {department.value} to your account first.",
            }

        # Privacy notification
        category = DepartmentAuthorisation.ACCESS_MATRIX.get(
            department, [ServiceCategory.SOCIAL_SERVICES]
        )[0]
        privacy_notice = self._privacy.register_collection(
            data_type=request_type,
            purpose=f"Process {request_type} request",
            citizen_id=citizen_id,
        )

        # Create request
        request = ServiceRequest(
            request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
            citizen_id=citizen_id,
            department=department,
            category=category,
            request_type=request_type,
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            details=details,
        )

        self._service_requests.append(request)

        logger.info(f"Service request created: {request.request_id} for {citizen_id}")

        return {
            "request_id": request.request_id,
            "status": request.status,
            "department": department.value,
            "type": request_type,
            "privacy_notice": privacy_notice,
        }

    def query_request_status(
        self,
        citizen_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Query status of a service request."""
        for req in self._service_requests:
            if req.request_id == request_id and req.citizen_id == citizen_id:
                return {
                    "request_id": req.request_id,
                    "department": req.department.value,
                    "type": req.request_type,
                    "status": req.status,
                    "created": req.created_at.isoformat(),
                    "updated": req.updated_at.isoformat(),
                }

        return {"error": "Request not found"}

    def handle_query(
        self,
        citizen_id: str,
        query: str,
    ) -> dict[str, Any]:
        """
        Handle citizen query through the agent.

        Routes to appropriate service based on intent.
        """
        citizen = self._citizens.get(citizen_id)
        if not citizen:
            return {"error": "Please verify your identity first"}

        query_lower = query.lower()

        if "link" in query_lower or "connect" in query_lower:
            return {
                "response": "To link a new service to your account, please visit the service's website "
                "and complete identity verification.",
                "available_services": [d.value for d in Department],
            }

        elif "status" in query_lower or "request" in query_lower:
            citizen_requests = [
                r for r in self._service_requests if r.citizen_id == citizen_id
            ]
            return {
                "response": f"You have {len(citizen_requests)} service request(s).",
                "requests": [
                    {
                        "id": r.request_id,
                        "type": r.request_type,
                        "status": r.status,
                        "department": r.department.value,
                    }
                    for r in citizen_requests
                ],
            }

        elif "services" in query_lower or "linked" in query_lower:
            return self.get_linked_services(citizen_id)

        elif (
            "privacy" in query_lower or "data" in query_lower or "access" in query_lower
        ):
            # APP 12: Access request
            access_log = self._privacy.citizen_access_request(citizen_id)
            return {
                "response": "Here is a record of how your information has been accessed.",
                "access_log": access_log[-10:],  # Last 10 entries
                "full_access_request": "Submit a formal APP 12 request for complete records.",
            }

        else:
            return {
                "response": f"Hello {citizen.given_names}. How can I help you today?",
                "linked_services": [d.value for d in citizen.linked_services],
                "suggested_actions": [
                    "Check service request status",
                    "View linked services",
                    "Submit a new request",
                    "View privacy information",
                ],
            }


# =============================================================================
# DEMONSTRATION
# =============================================================================


def demo():
    """Demonstrate the citizen services agent."""

    print("=" * 70)
    print("CITIZEN SERVICES AGENT - Government Portal Demo")
    print("=" * 70)
    print()

    # Initialise compliance frameworks
    essential_eight = EssentialEightCompliance()
    privacy = PrivacyActCompliance()
    dept_auth = DepartmentAuthorisation(privacy)

    # Create agent
    agent = CitizenServicesAgent(essential_eight, privacy, dept_auth)

    # Demo: Essential Eight compliance
    print("-" * 70)
    print("ESSENTIAL EIGHT COMPLIANCE STATUS")
    print("-" * 70)

    e8_status = essential_eight.check_compliance(minimum_level=2)
    print(f"Overall compliant: {e8_status['compliant']}")
    print(
        f"Controls at level 2+: {e8_status['controls_compliant']}/{e8_status['controls_total']}"
    )
    if e8_status["non_compliant_controls"]:
        print("Non-compliant controls:")
        for nc in e8_status["non_compliant_controls"]:
            print(
                f"  - {nc['control']}: Level {nc['current_level']} (required: {nc['required_level']})"
            )
    print()

    # Demo: Identity verification
    print("-" * 70)
    print("IDENTITY VERIFICATION")
    print("-" * 70)

    citizen_id = "CIT-001"
    verification = agent.verify_identity(citizen_id)
    print(f"Citizen: {verification.get('name')}")
    print(f"Verified: {verification.get('verified')}")
    print(f"Identity strength: {verification.get('identity_strength')}")
    print(f"Linked services: {', '.join(verification.get('linked_services', []))}")
    print()

    # Demo: Service request with privacy notice
    print("-" * 70)
    print("SERVICE REQUEST WITH PRIVACY COMPLIANCE")
    print("-" * 70)

    request_result = agent.submit_service_request(
        citizen_id=citizen_id,
        department=Department.CENTRELINK,
        request_type="income_statement",
        details={"period": "2024-25", "format": "pdf"},
    )

    print(f"Request ID: {request_result.get('request_id')}")
    print(f"Status: {request_result.get('status')}")
    print(f"Department: {request_result.get('department')}")
    print()
    print("Privacy Notice (APP 5):")
    notice = request_result.get("privacy_notice", {})
    print(f"  {notice.get('message')}")
    print()

    # Demo: Cross-department access
    print("-" * 70)
    print("CROSS-DEPARTMENT ACCESS CONTROL")
    print("-" * 70)

    # Normal access
    can_access, reason = dept_auth.check_access(
        department=Department.ATO,
        category=ServiceCategory.TAXATION,
        citizen_id=citizen_id,
        purpose="Tax return processing",
    )
    print(f"ATO accessing TAXATION: {can_access} ({reason})")

    # Denied access
    can_access, reason = dept_auth.check_access(
        department=Department.ATO,
        category=ServiceCategory.HEALTH,
        citizen_id=citizen_id,
        purpose="Invalid purpose",
    )
    print(f"ATO accessing HEALTH: {can_access} ({reason})")

    # Request cross-department access
    cross_auth = dept_auth.request_cross_department_access(
        requesting_dept=Department.DVA,
        target_category=ServiceCategory.SOCIAL_SERVICES,
        citizen_id=citizen_id,
        purpose="Veterans' benefit coordination",
        duration_hours=24,
    )
    print(f"Cross-department request: {cross_auth['status']}")
    print()

    # Demo: Citizen query handling
    print("-" * 70)
    print("CITIZEN QUERIES")
    print("-" * 70)

    # Query linked services
    result = agent.handle_query(citizen_id, "what services are linked?")
    print(f"Query: 'what services are linked?'")
    print(f"Response: {result.get('total_linked')} services linked")
    for svc in result.get("services", []):
        print(f"  - {svc['name']}")
    print()

    # Query privacy/data access
    result = agent.handle_query(citizen_id, "who has accessed my data?")
    print(f"Query: 'who has accessed my data?'")
    print(f"Response: {result.get('response')}")
    print()

    # Demo: Privacy Act access log
    print("-" * 70)
    print("PRIVACY ACT COMPLIANCE - ACCESS LOG")
    print("-" * 70)

    access_log = privacy.citizen_access_request(citizen_id)
    print(f"Total access records: {len(access_log)}")
    for entry in access_log[-5:]:
        print(
            f"  {entry['timestamp']}: {entry['department']} accessed {entry['data_type']}"
        )

    print()
    print("=" * 70)
    print("Demo complete. All access logged for compliance.")
    print("=" * 70)


if __name__ == "__main__":
    demo()
