#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 55: Property Management Assistant

A comprehensive property management platform inspired by OurProperty.com.au.
Handles the full lifecycle of residential property management in Australia.

Features:
- Property portfolio management
- Tenant onboarding and screening
- Lease agreement tracking
- Rent collection monitoring
- Arrears management and alerts
- Maintenance request handling
- Inspection scheduling
- Bond management
- Compliance tracking (smoke alarms, pool fences, etc.)
- Key management
- Landlord reporting

Australian-specific:
- State-based Residential Tenancies Acts (NSW, VIC, QLD, SA, WA)
- Bond lodgement with state authorities
- TICA tenant database integration patterns
- Compliant inspection notice periods

Usage:
    python examples/55_property_manager.py

Requirements:
    pip install agentic-brain

Author: agentic-brain
License: MIT
"""

import asyncio
import random
import string
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# AUSTRALIAN STATE CONFIGURATIONS
# ══════════════════════════════════════════════════════════════════════════════


class AustralianState(Enum):
    """Australian states and territories."""

    NSW = "New South Wales"
    VIC = "Victoria"
    QLD = "Queensland"
    SA = "South Australia"
    WA = "Western Australia"
    TAS = "Tasmania"
    NT = "Northern Territory"
    ACT = "Australian Capital Territory"


@dataclass
class StateRegulations:
    """State-specific tenancy regulations."""

    state: AustralianState
    bond_authority: str
    max_bond_weeks: int
    routine_inspection_notice_days: int
    entry_notice_hours: int
    rent_increase_notice_days: int
    break_lease_fee_weeks: int

    @classmethod
    def get_regulations(cls, state: AustralianState) -> "StateRegulations":
        """Get regulations for a specific state."""
        regulations = {
            AustralianState.NSW: cls(
                state=AustralianState.NSW,
                bond_authority="NSW Fair Trading",
                max_bond_weeks=4,
                routine_inspection_notice_days=7,
                entry_notice_hours=48,
                rent_increase_notice_days=60,
                break_lease_fee_weeks=4,
            ),
            AustralianState.VIC: cls(
                state=AustralianState.VIC,
                bond_authority="RTBA Victoria",
                max_bond_weeks=4,
                routine_inspection_notice_days=7,
                entry_notice_hours=24,
                rent_increase_notice_days=60,
                break_lease_fee_weeks=4,
            ),
            AustralianState.QLD: cls(
                state=AustralianState.QLD,
                bond_authority="RTA Queensland",
                max_bond_weeks=4,
                routine_inspection_notice_days=7,
                entry_notice_hours=24,
                rent_increase_notice_days=60,
                break_lease_fee_weeks=4,
            ),
            AustralianState.SA: cls(
                state=AustralianState.SA,
                bond_authority="CBS South Australia",
                max_bond_weeks=4,
                routine_inspection_notice_days=7,
                entry_notice_hours=48,
                rent_increase_notice_days=60,
                break_lease_fee_weeks=6,
            ),
            AustralianState.WA: cls(
                state=AustralianState.WA,
                bond_authority="Bond Administrator WA",
                max_bond_weeks=4,
                routine_inspection_notice_days=7,
                entry_notice_hours=72,
                rent_increase_notice_days=60,
                break_lease_fee_weeks=4,
            ),
        }
        return regulations.get(state, regulations[AustralianState.NSW])


# ══════════════════════════════════════════════════════════════════════════════
# PROPERTY MODELS
# ══════════════════════════════════════════════════════════════════════════════


class PropertyType(Enum):
    """Types of residential properties."""

    HOUSE = "House"
    APARTMENT = "Apartment"
    UNIT = "Unit"
    TOWNHOUSE = "Townhouse"
    VILLA = "Villa"
    STUDIO = "Studio"
    GRANNY_FLAT = "Granny Flat"


class PropertyStatus(Enum):
    """Current status of a property."""

    VACANT = "Vacant"
    LEASED = "Leased"
    UNDER_APPLICATION = "Under Application"
    UNDER_MAINTENANCE = "Under Maintenance"
    OFF_MARKET = "Off Market"


class LeaseStatus(Enum):
    """Status of a lease agreement."""

    ACTIVE = "Active"
    PERIODIC = "Periodic (Month-to-Month)"
    EXPIRED = "Expired"
    TERMINATED = "Terminated"
    PENDING = "Pending Start"


class MaintenancePriority(Enum):
    """Priority levels for maintenance requests."""

    EMERGENCY = "Emergency"  # 4 hours response
    URGENT = "Urgent"  # 24 hours response
    ROUTINE = "Routine"  # 7 days response
    PLANNED = "Planned"  # Scheduled


class MaintenanceStatus(Enum):
    """Status of maintenance requests."""

    NEW = "New"
    AWAITING_QUOTE = "Awaiting Quote"
    QUOTE_RECEIVED = "Quote Received"
    APPROVED = "Approved"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CLOSED = "Closed"


@dataclass
class Property:
    """Represents a managed property."""

    property_id: str
    address: str
    suburb: str
    state: AustralianState
    postcode: str
    property_type: PropertyType
    bedrooms: int
    bathrooms: int
    parking: int
    status: PropertyStatus = PropertyStatus.VACANT
    weekly_rent: Decimal = Decimal("0")
    landlord_id: str = ""
    features: list[str] = field(default_factory=list)

    # Compliance tracking
    smoke_alarm_expiry: Optional[date] = None
    pool_fence_compliant: Optional[bool] = None
    gas_safety_check: Optional[date] = None
    electrical_safety_check: Optional[date] = None

    # Key management
    keys_held: int = 0
    key_location: str = ""

    def __str__(self) -> str:
        return f"{self.address}, {self.suburb} {self.state.name} {self.postcode}"

    @property
    def full_address(self) -> str:
        return f"{self.address}, {self.suburb} {self.state.name} {self.postcode}"

    def check_compliance(self) -> list[str]:
        """Check compliance requirements and return any issues."""
        issues = []
        today = date.today()

        if self.smoke_alarm_expiry and self.smoke_alarm_expiry <= today:
            issues.append("⚠️ Smoke alarm compliance expired")
        elif self.smoke_alarm_expiry and self.smoke_alarm_expiry <= today + timedelta(
            days=30
        ):
            issues.append("🔔 Smoke alarm compliance expiring within 30 days")

        if self.pool_fence_compliant is False:
            issues.append("⚠️ Pool fence non-compliant")

        if self.gas_safety_check and self.gas_safety_check <= today - timedelta(
            days=365 * 2
        ):
            issues.append("⚠️ Gas safety check overdue")

        return issues


@dataclass
class Tenant:
    """Represents a tenant."""

    tenant_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    date_of_birth: Optional[date] = None

    # Screening results
    tica_clear: Optional[bool] = None
    employment_verified: Optional[bool] = None
    income_verified: Optional[bool] = None
    references_checked: Optional[bool] = None

    # Emergency contact
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Landlord:
    """Represents a property owner/landlord."""

    landlord_id: str
    name: str
    email: str
    phone: str
    postal_address: str

    # Financial details
    bsb: str = ""
    account_number: str = ""
    account_name: str = ""

    # Preferences
    approve_maintenance_under: Decimal = Decimal("500")
    send_monthly_statements: bool = True

    @property
    def masked_account(self) -> str:
        if self.account_number:
            return f"****{self.account_number[-4:]}"
        return ""


@dataclass
class Lease:
    """Represents a lease agreement."""

    lease_id: str
    property_id: str
    tenant_ids: list[str]
    start_date: date
    end_date: Optional[date]  # None for periodic
    weekly_rent: Decimal
    bond_amount: Decimal
    status: LeaseStatus = LeaseStatus.ACTIVE

    # Bond details
    bond_lodged: bool = False
    bond_reference: str = ""

    # Rent details
    rent_day: int = 1  # Day of week/month rent is due
    rent_frequency: str = "weekly"  # weekly, fortnightly, monthly

    @property
    def is_periodic(self) -> bool:
        return self.end_date is None or self.status == LeaseStatus.PERIODIC

    @property
    def days_remaining(self) -> Optional[int]:
        if self.end_date is None:
            return None
        return (self.end_date - date.today()).days


@dataclass
class RentPayment:
    """Represents a rent payment record."""

    payment_id: str
    lease_id: str
    amount: Decimal
    date_due: date
    date_paid: Optional[date] = None
    payment_method: str = ""
    reference: str = ""

    @property
    def is_paid(self) -> bool:
        return self.date_paid is not None

    @property
    def days_overdue(self) -> int:
        if self.is_paid:
            return 0
        return max(0, (date.today() - self.date_due).days)


@dataclass
class MaintenanceRequest:
    """Represents a maintenance request."""

    request_id: str
    property_id: str
    tenant_id: Optional[str]
    category: str  # plumbing, electrical, appliance, etc.
    description: str
    priority: MaintenancePriority
    status: MaintenanceStatus = MaintenanceStatus.NEW
    created_date: datetime = field(default_factory=datetime.now)

    # Assignment
    tradesperson_name: str = ""
    tradesperson_phone: str = ""
    scheduled_date: Optional[datetime] = None

    # Costs
    quoted_amount: Decimal = Decimal("0")
    final_amount: Decimal = Decimal("0")
    landlord_approved: bool = False

    # Documentation
    photos: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Inspection:
    """Represents a property inspection."""

    inspection_id: str
    property_id: str
    inspection_type: str  # routine, ingoing, outgoing
    scheduled_date: datetime
    completed: bool = False

    # Results
    overall_condition: str = ""  # good, fair, poor
    notes: str = ""
    photos: list[str] = field(default_factory=list)
    issues_found: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# PROPERTY MANAGEMENT SYSTEM
# ══════════════════════════════════════════════════════════════════════════════


class PropertyManagementSystem:
    """Main property management system."""

    def __init__(self, agency_name: str, state: AustralianState):
        """Initialize the property management system."""
        self.agency_name = agency_name
        self.state = state
        self.regulations = StateRegulations.get_regulations(state)

        # Data stores
        self.properties: dict[str, Property] = {}
        self.tenants: dict[str, Tenant] = {}
        self.landlords: dict[str, Landlord] = {}
        self.leases: dict[str, Lease] = {}
        self.payments: list[RentPayment] = []
        self.maintenance_requests: list[MaintenanceRequest] = []
        self.inspections: list[Inspection] = []

        # Audit log
        self.audit_log: list[dict] = []

    def _log_action(
        self, action: str, entity_type: str, entity_id: str, details: str = ""
    ):
        """Log an action for audit trail."""
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
            }
        )

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        random_part = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        return f"{prefix}-{random_part}"

    # ─────────────────────────────────────────────────────────────────────────
    # PROPERTY MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def add_property(self, property: Property) -> str:
        """Add a new property to management."""
        if not property.property_id:
            property.property_id = self._generate_id("PROP")

        self.properties[property.property_id] = property
        self._log_action("ADD", "Property", property.property_id, property.full_address)
        print(f"✅ Added property: {property.full_address}")
        return property.property_id

    def get_property(self, property_id: str) -> Optional[Property]:
        """Get a property by ID."""
        return self.properties.get(property_id)

    def list_properties(
        self, status: Optional[PropertyStatus] = None
    ) -> list[Property]:
        """List all properties, optionally filtered by status."""
        if status is None:
            return list(self.properties.values())
        return [p for p in self.properties.values() if p.status == status]

    def update_property_status(self, property_id: str, status: PropertyStatus) -> bool:
        """Update a property's status."""
        if property_id in self.properties:
            self.properties[property_id].status = status
            self._log_action(
                "UPDATE", "Property", property_id, f"Status -> {status.value}"
            )
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # TENANT MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def add_tenant(self, tenant: Tenant) -> str:
        """Add a new tenant."""
        if not tenant.tenant_id:
            tenant.tenant_id = self._generate_id("TEN")

        self.tenants[tenant.tenant_id] = tenant
        self._log_action("ADD", "Tenant", tenant.tenant_id, tenant.full_name)
        print(f"✅ Added tenant: {tenant.full_name}")
        return tenant.tenant_id

    def screen_tenant(self, tenant_id: str) -> dict:
        """Perform tenant screening checks."""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return {"error": "Tenant not found"}

        # In production, this would integrate with TICA, employment verification, etc.
        results = {
            "tenant_id": tenant_id,
            "name": tenant.full_name,
            "tica_check": "CLEAR" if tenant.tica_clear else "PENDING",
            "employment": "VERIFIED" if tenant.employment_verified else "PENDING",
            "income": "VERIFIED" if tenant.income_verified else "PENDING",
            "references": "CHECKED" if tenant.references_checked else "PENDING",
            "recommendation": (
                "APPROVE"
                if all(
                    [
                        tenant.tica_clear,
                        tenant.employment_verified,
                        tenant.income_verified,
                        tenant.references_checked,
                    ]
                )
                else "FURTHER_REVIEW"
            ),
        }

        self._log_action(
            "SCREEN", "Tenant", tenant_id, f"Result: {results['recommendation']}"
        )
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # LANDLORD MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def add_landlord(self, landlord: Landlord) -> str:
        """Add a new landlord."""
        if not landlord.landlord_id:
            landlord.landlord_id = self._generate_id("LAND")

        self.landlords[landlord.landlord_id] = landlord
        self._log_action("ADD", "Landlord", landlord.landlord_id, landlord.name)
        print(f"✅ Added landlord: {landlord.name}")
        return landlord.landlord_id

    def get_landlord_properties(self, landlord_id: str) -> list[Property]:
        """Get all properties for a landlord."""
        return [p for p in self.properties.values() if p.landlord_id == landlord_id]

    # ─────────────────────────────────────────────────────────────────────────
    # LEASE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def create_lease(
        self,
        property_id: str,
        tenant_ids: list[str],
        start_date: date,
        end_date: Optional[date],
        weekly_rent: Decimal,
    ) -> str:
        """Create a new lease agreement."""
        prop = self.properties.get(property_id)
        if not prop:
            raise ValueError(f"Property {property_id} not found")

        # Calculate bond based on state regulations
        bond_amount = weekly_rent * self.regulations.max_bond_weeks

        lease = Lease(
            lease_id=self._generate_id("LEASE"),
            property_id=property_id,
            tenant_ids=tenant_ids,
            start_date=start_date,
            end_date=end_date,
            weekly_rent=weekly_rent,
            bond_amount=bond_amount,
        )

        self.leases[lease.lease_id] = lease

        # Update property status
        prop.status = PropertyStatus.LEASED
        prop.weekly_rent = weekly_rent

        self._log_action(
            "CREATE",
            "Lease",
            lease.lease_id,
            f"Property: {property_id}, Rent: ${weekly_rent}/week",
        )
        print(f"✅ Created lease: {lease.lease_id} for {prop.full_address}")
        return lease.lease_id

    def lodge_bond(self, lease_id: str) -> dict:
        """Lodge bond with state authority."""
        lease = self.leases.get(lease_id)
        if not lease:
            return {"error": "Lease not found"}

        # Generate bond reference (in production, this would call state API)
        bond_ref = f"BOND-{lease.lease_id[-6:]}-{random.randint(1000, 9999)}"

        lease.bond_lodged = True
        lease.bond_reference = bond_ref

        result = {
            "lease_id": lease_id,
            "bond_amount": float(lease.bond_amount),
            "bond_reference": bond_ref,
            "lodged_with": self.regulations.bond_authority,
            "status": "LODGED",
        }

        self._log_action("LODGE_BOND", "Lease", lease_id, f"Ref: {bond_ref}")
        print(f"✅ Bond lodged: {bond_ref} with {self.regulations.bond_authority}")
        return result

    def get_expiring_leases(self, days: int = 60) -> list[Lease]:
        """Get leases expiring within specified days."""
        cutoff = date.today() + timedelta(days=days)
        return [
            lease
            for lease in self.leases.values()
            if lease.end_date
            and lease.end_date <= cutoff
            and lease.status == LeaseStatus.ACTIVE
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # RENT COLLECTION
    # ─────────────────────────────────────────────────────────────────────────

    def record_rent_payment(
        self,
        lease_id: str,
        amount: Decimal,
        date_paid: date,
        payment_method: str,
        reference: str = "",
    ) -> str:
        """Record a rent payment."""
        lease = self.leases.get(lease_id)
        if not lease:
            raise ValueError(f"Lease {lease_id} not found")

        payment = RentPayment(
            payment_id=self._generate_id("PAY"),
            lease_id=lease_id,
            amount=amount,
            date_due=date_paid,  # Simplified
            date_paid=date_paid,
            payment_method=payment_method,
            reference=reference,
        )

        self.payments.append(payment)
        self._log_action(
            "PAYMENT", "Rent", payment.payment_id, f"${amount} for lease {lease_id}"
        )
        return payment.payment_id

    def get_arrears(self, min_days: int = 1) -> list[dict]:
        """Get list of tenants in arrears."""
        arrears = []

        for lease in self.leases.values():
            if lease.status != LeaseStatus.ACTIVE:
                continue

            # Get payments for this lease
            lease_payments = [p for p in self.payments if p.lease_id == lease.lease_id]
            unpaid = [
                p
                for p in lease_payments
                if not p.is_paid and p.days_overdue >= min_days
            ]

            if unpaid:
                prop = self.properties.get(lease.property_id)
                tenant_names = ", ".join(
                    [
                        self.tenants[tid].full_name
                        for tid in lease.tenant_ids
                        if tid in self.tenants
                    ]
                )

                total_overdue = sum(p.amount for p in unpaid)
                max_days = max(p.days_overdue for p in unpaid)

                arrears.append(
                    {
                        "lease_id": lease.lease_id,
                        "property": prop.full_address if prop else "Unknown",
                        "tenant": tenant_names,
                        "total_overdue": float(total_overdue),
                        "days_overdue": max_days,
                        "payments_overdue": len(unpaid),
                    }
                )

        return sorted(arrears, key=lambda x: x["days_overdue"], reverse=True)

    def send_arrears_notice(self, lease_id: str, notice_type: str = "reminder") -> dict:
        """Send arrears notice to tenant."""
        lease = self.leases.get(lease_id)
        if not lease:
            return {"error": "Lease not found"}

        notice_types = {
            "reminder": "Payment Reminder",
            "first": "First Notice of Breach",
            "final": "Final Notice - Termination Warning",
        }

        result = {
            "lease_id": lease_id,
            "notice_type": notice_types.get(notice_type, "Reminder"),
            "sent_to": [
                self.tenants[tid].email
                for tid in lease.tenant_ids
                if tid in self.tenants
            ],
            "status": "SENT",
        }

        self._log_action("ARREARS_NOTICE", "Lease", lease_id, f"Type: {notice_type}")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # MAINTENANCE
    # ─────────────────────────────────────────────────────────────────────────

    def create_maintenance_request(
        self,
        property_id: str,
        category: str,
        description: str,
        priority: MaintenancePriority,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Create a new maintenance request."""
        request = MaintenanceRequest(
            request_id=self._generate_id("MAINT"),
            property_id=property_id,
            tenant_id=tenant_id,
            category=category,
            description=description,
            priority=priority,
        )

        self.maintenance_requests.append(request)

        prop = self.properties.get(property_id)
        self._log_action(
            "CREATE",
            "Maintenance",
            request.request_id,
            f"{priority.value}: {category} at {prop.full_address if prop else property_id}",
        )

        print(
            f"✅ Created maintenance request: {request.request_id} ({priority.value})"
        )
        return request.request_id

    def assign_tradesperson(
        self,
        request_id: str,
        name: str,
        phone: str,
        scheduled_date: datetime,
    ) -> bool:
        """Assign a tradesperson to a maintenance request."""
        for req in self.maintenance_requests:
            if req.request_id == request_id:
                req.tradesperson_name = name
                req.tradesperson_phone = phone
                req.scheduled_date = scheduled_date
                req.status = MaintenanceStatus.APPROVED

                self._log_action(
                    "ASSIGN", "Maintenance", request_id, f"Tradesperson: {name}"
                )
                return True
        return False

    def get_open_maintenance(self) -> list[MaintenanceRequest]:
        """Get all open maintenance requests."""
        return [
            req
            for req in self.maintenance_requests
            if req.status not in [MaintenanceStatus.COMPLETED, MaintenanceStatus.CLOSED]
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # INSPECTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def schedule_inspection(
        self,
        property_id: str,
        inspection_type: str,
        scheduled_date: datetime,
    ) -> str:
        """Schedule a property inspection."""
        # Check notice period
        days_notice = (scheduled_date.date() - date.today()).days
        min_notice = self.regulations.routine_inspection_notice_days

        if days_notice < min_notice:
            raise ValueError(
                f"Insufficient notice period. {self.state.value} requires "
                f"{min_notice} days notice for routine inspections."
            )

        inspection = Inspection(
            inspection_id=self._generate_id("INSP"),
            property_id=property_id,
            inspection_type=inspection_type,
            scheduled_date=scheduled_date,
        )

        self.inspections.append(inspection)

        prop = self.properties.get(property_id)
        self._log_action(
            "SCHEDULE",
            "Inspection",
            inspection.inspection_id,
            f"{inspection_type} at {prop.full_address if prop else property_id}",
        )

        print(
            f"✅ Scheduled {inspection_type} inspection: {scheduled_date.strftime('%d/%m/%Y')}"
        )
        return inspection.inspection_id

    def get_upcoming_inspections(self, days: int = 14) -> list[Inspection]:
        """Get inspections scheduled within specified days."""
        cutoff = datetime.now() + timedelta(days=days)
        return [
            insp
            for insp in self.inspections
            if not insp.completed and insp.scheduled_date <= cutoff
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # COMPLIANCE
    # ─────────────────────────────────────────────────────────────────────────

    def check_portfolio_compliance(self) -> list[dict]:
        """Check compliance across all properties."""
        issues = []

        for prop in self.properties.values():
            property_issues = prop.check_compliance()
            if property_issues:
                issues.append(
                    {
                        "property_id": prop.property_id,
                        "address": prop.full_address,
                        "issues": property_issues,
                    }
                )

        return issues

    # ─────────────────────────────────────────────────────────────────────────
    # REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    def generate_landlord_statement(
        self, landlord_id: str, month: int, year: int
    ) -> dict:
        """Generate monthly statement for a landlord."""
        landlord = self.landlords.get(landlord_id)
        if not landlord:
            return {"error": "Landlord not found"}

        properties = self.get_landlord_properties(landlord_id)

        # Calculate income and expenses for the month
        total_rent = Decimal("0")
        total_expenses = Decimal("0")
        property_details = []

        for prop in properties:
            # Find active lease
            lease = None
            for l in self.leases.values():
                if l.property_id == prop.property_id and l.status == LeaseStatus.ACTIVE:
                    lease = l
                    break

            # Sum rent for the month (simplified)
            if lease:
                weeks_in_month = 4
                rent_collected = lease.weekly_rent * weeks_in_month
                total_rent += rent_collected

            property_details.append(
                {
                    "address": prop.full_address,
                    "status": prop.status.value,
                    "weekly_rent": float(prop.weekly_rent),
                }
            )

        # Management fee (typically 7-10%)
        management_fee = total_rent * Decimal("0.08")
        net_amount = total_rent - management_fee - total_expenses

        return {
            "landlord": landlord.name,
            "period": f"{month:02d}/{year}",
            "properties": property_details,
            "total_rent": float(total_rent),
            "management_fee": float(management_fee),
            "total_expenses": float(total_expenses),
            "net_amount": float(net_amount),
            "payment_account": landlord.masked_account,
        }

    def get_portfolio_summary(self) -> dict:
        """Get summary of entire portfolio."""
        total_properties = len(self.properties)
        leased = len(
            [p for p in self.properties.values() if p.status == PropertyStatus.LEASED]
        )
        vacant = len(
            [p for p in self.properties.values() if p.status == PropertyStatus.VACANT]
        )

        total_weekly_rent = sum(
            p.weekly_rent
            for p in self.properties.values()
            if p.status == PropertyStatus.LEASED
        )

        return {
            "total_properties": total_properties,
            "leased": leased,
            "vacant": vacant,
            "occupancy_rate": (
                f"{(leased/total_properties*100):.1f}%"
                if total_properties > 0
                else "N/A"
            ),
            "total_weekly_rent": float(total_weekly_rent),
            "total_tenants": len(self.tenants),
            "total_landlords": len(self.landlords),
            "active_leases": len(
                [l for l in self.leases.values() if l.status == LeaseStatus.ACTIVE]
            ),
            "open_maintenance": len(self.get_open_maintenance()),
            "compliance_issues": len(self.check_portfolio_compliance()),
        }


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate the property management system."""

    print("=" * 70)
    print("Property Management Assistant Demo")
    print("Inspired by OurProperty.com.au")
    print("=" * 70)

    # Initialize for South Australia
    pm = PropertyManagementSystem("Adelaide Property Management", AustralianState.SA)

    print(f"\n🏢 Agency: {pm.agency_name}")
    print(f"📍 State: {pm.state.value}")
    print(f"📋 Regulations: Bond lodged with {pm.regulations.bond_authority}")
    print(f"   Max bond: {pm.regulations.max_bond_weeks} weeks rent")
    print(f"   Inspection notice: {pm.regulations.routine_inspection_notice_days} days")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Add Landlords
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📋 Adding Landlords")
    print("─" * 50)

    landlord1 = Landlord(
        landlord_id="",
        name="Margaret Chen",
        email="margaret.chen@email.com.au",
        phone="0412 345 678",
        postal_address="45 Investment Ave, Unley SA 5061",
        bsb="105-029",
        account_number="12345678",
        account_name="M CHEN",
        approve_maintenance_under=Decimal("750"),
    )
    landlord1_id = pm.add_landlord(landlord1)

    landlord2 = Landlord(
        landlord_id="",
        name="Robert Williams",
        email="r.williams@bigpond.com",
        phone="0423 456 789",
        postal_address="12 Beach Rd, Glenelg SA 5045",
        bsb="105-000",
        account_number="87654321",
        account_name="R WILLIAMS",
    )
    landlord2_id = pm.add_landlord(landlord2)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Add Properties
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🏠 Adding Properties")
    print("─" * 50)

    properties_data = [
        Property(
            property_id="",
            address="Unit 5/123 Wakefield Street",
            suburb="Adelaide",
            state=AustralianState.SA,
            postcode="5000",
            property_type=PropertyType.APARTMENT,
            bedrooms=2,
            bathrooms=1,
            parking=1,
            weekly_rent=Decimal("520"),
            landlord_id=landlord1_id,
            features=["Air conditioning", "Balcony", "City views", "Secure parking"],
            smoke_alarm_expiry=date(2026, 6, 15),
        ),
        Property(
            property_id="",
            address="8 Jacaranda Crescent",
            suburb="Mawson Lakes",
            state=AustralianState.SA,
            postcode="5095",
            property_type=PropertyType.HOUSE,
            bedrooms=4,
            bathrooms=2,
            parking=2,
            weekly_rent=Decimal("650"),
            landlord_id=landlord1_id,
            features=["Double garage", "Solar panels", "Ducted AC", "Alfresco area"],
            smoke_alarm_expiry=date(2026, 8, 1),
            pool_fence_compliant=True,
        ),
        Property(
            property_id="",
            address="3/45 Brighton Road",
            suburb="Glenelg",
            state=AustralianState.SA,
            postcode="5045",
            property_type=PropertyType.UNIT,
            bedrooms=2,
            bathrooms=1,
            parking=1,
            weekly_rent=Decimal("480"),
            landlord_id=landlord2_id,
            features=["Walk to beach", "Updated kitchen", "NBN connected"],
            smoke_alarm_expiry=date(2026, 3, 1),  # Expiring soon!
        ),
        Property(
            property_id="",
            address="22 Willow Avenue",
            suburb="Norwood",
            state=AustralianState.SA,
            postcode="5067",
            property_type=PropertyType.TOWNHOUSE,
            bedrooms=3,
            bathrooms=2,
            parking=2,
            status=PropertyStatus.VACANT,
            weekly_rent=Decimal("590"),
            landlord_id=landlord2_id,
            features=["Courtyard garden", "Gas heating", "European appliances"],
            smoke_alarm_expiry=date(2027, 1, 15),
        ),
    ]

    property_ids = []
    for prop in properties_data:
        pid = pm.add_property(prop)
        property_ids.append(pid)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Add Tenants
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("👥 Adding Tenants")
    print("─" * 50)

    tenants_data = [
        Tenant(
            tenant_id="",
            first_name="Sarah",
            last_name="Mitchell",
            email="sarah.mitchell@gmail.com",
            phone="0434 567 890",
            tica_clear=True,
            employment_verified=True,
            income_verified=True,
            references_checked=True,
            emergency_contact_name="David Mitchell",
            emergency_contact_phone="0445 678 901",
        ),
        Tenant(
            tenant_id="",
            first_name="James",
            last_name="Anderson",
            email="j.anderson@outlook.com",
            phone="0445 678 901",
            tica_clear=True,
            employment_verified=True,
            income_verified=True,
            references_checked=True,
        ),
        Tenant(
            tenant_id="",
            first_name="Lisa",
            last_name="Wong",
            email="lisa.wong@email.com",
            phone="0456 789 012",
            tica_clear=True,
            employment_verified=True,
            income_verified=False,  # Still pending
            references_checked=True,
        ),
    ]

    tenant_ids = []
    for tenant in tenants_data:
        tid = pm.add_tenant(tenant)
        tenant_ids.append(tid)

    # Screen a tenant
    print("\n📋 Screening tenant...")
    screening = pm.screen_tenant(tenant_ids[2])
    print(f"   Name: {screening['name']}")
    print(f"   TICA: {screening['tica_check']}")
    print(f"   Income: {screening['income']}")
    print(f"   Recommendation: {screening['recommendation']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Create Leases
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📜 Creating Leases")
    print("─" * 50)

    # Lease for first property
    lease1_id = pm.create_lease(
        property_id=property_ids[0],
        tenant_ids=[tenant_ids[0]],
        start_date=date(2025, 6, 1),
        end_date=date(2026, 5, 31),
        weekly_rent=Decimal("520"),
    )

    # Lodge bond
    bond_result = pm.lodge_bond(lease1_id)
    print(f"   Bond reference: {bond_result['bond_reference']}")

    # Lease for second property
    lease2_id = pm.create_lease(
        property_id=property_ids[1],
        tenant_ids=[tenant_ids[1]],
        start_date=date(2025, 3, 15),
        end_date=date(2026, 3, 14),
        weekly_rent=Decimal("650"),
    )
    pm.lodge_bond(lease2_id)

    # Lease for third property (expiring soon)
    lease3_id = pm.create_lease(
        property_id=property_ids[2],
        tenant_ids=[tenant_ids[2]],
        start_date=date(2025, 1, 1),
        end_date=date(2026, 4, 30),  # Expiring in ~6 weeks
        weekly_rent=Decimal("480"),
    )
    pm.lodge_bond(lease3_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Record Payments & Check Arrears
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("💰 Rent Collection")
    print("─" * 50)

    # Record some payments
    pm.record_rent_payment(
        lease_id=lease1_id,
        amount=Decimal("520"),
        date_paid=date.today() - timedelta(days=7),
        payment_method="Direct Debit",
        reference="DD-RENT-001",
    )

    pm.record_rent_payment(
        lease_id=lease2_id,
        amount=Decimal("650"),
        date_paid=date.today() - timedelta(days=7),
        payment_method="Bank Transfer",
        reference="TRF-RENT-001",
    )

    print("✅ Recorded rent payments")

    # Check arrears
    arrears = pm.get_arrears()
    if arrears:
        print("\n⚠️ Tenants in arrears:")
        for arr in arrears:
            print(
                f"   {arr['tenant']}: ${arr['total_overdue']:.2f} ({arr['days_overdue']} days)"
            )
    else:
        print("✅ No tenants in arrears")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Maintenance Requests
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔧 Maintenance Requests")
    print("─" * 50)

    pm.create_maintenance_request(
        property_id=property_ids[0],
        category="Plumbing",
        description="Leaking tap in bathroom. Dripping continuously.",
        priority=MaintenancePriority.ROUTINE,
        tenant_id=tenant_ids[0],
    )

    maint2_id = pm.create_maintenance_request(
        property_id=property_ids[1],
        category="Electrical",
        description="Power point in living room not working.",
        priority=MaintenancePriority.URGENT,
        tenant_id=tenant_ids[1],
    )

    # Assign tradesperson
    pm.assign_tradesperson(
        request_id=maint2_id,
        name="Sparky Electrical",
        phone="0412 888 999",
        scheduled_date=datetime.now() + timedelta(days=1),
    )
    print(f"   Assigned electrician to {maint2_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Schedule Inspections
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔍 Property Inspections")
    print("─" * 50)

    insp_date = datetime.now() + timedelta(days=14)
    pm.schedule_inspection(
        property_id=property_ids[0],
        inspection_type="routine",
        scheduled_date=insp_date,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Compliance Check
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("✅ Compliance Check")
    print("─" * 50)

    compliance_issues = pm.check_portfolio_compliance()
    if compliance_issues:
        for issue in compliance_issues:
            print(f"\n🏠 {issue['address']}")
            for i in issue["issues"]:
                print(f"   {i}")
    else:
        print("✅ All properties compliant")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 9: Reporting
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📊 Portfolio Summary")
    print("─" * 50)

    summary = pm.get_portfolio_summary()
    print(f"   Total Properties: {summary['total_properties']}")
    print(f"   Leased: {summary['leased']}")
    print(f"   Vacant: {summary['vacant']}")
    print(f"   Occupancy Rate: {summary['occupancy_rate']}")
    print(f"   Total Weekly Rent: ${summary['total_weekly_rent']:.2f}")
    print(f"   Active Leases: {summary['active_leases']}")
    print(f"   Open Maintenance: {summary['open_maintenance']}")

    # Landlord statement
    print("\n📋 Landlord Statement (Margaret Chen)")
    statement = pm.generate_landlord_statement(landlord1_id, 3, 2026)
    print(f"   Period: {statement['period']}")
    print(f"   Total Rent: ${statement['total_rent']:.2f}")
    print(f"   Management Fee: ${statement['management_fee']:.2f}")
    print(f"   Net Amount: ${statement['net_amount']:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 10: Expiring Leases Alert
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔔 Alerts & Reminders")
    print("─" * 50)

    expiring = pm.get_expiring_leases(days=90)
    if expiring:
        print(f"⚠️ {len(expiring)} lease(s) expiring in next 90 days:")
        for lease in expiring:
            prop = pm.get_property(lease.property_id)
            print(f"   {prop.full_address if prop else lease.property_id}")
            print(f"   Expires: {lease.end_date} ({lease.days_remaining} days)")

    upcoming_insp = pm.get_upcoming_inspections()
    if upcoming_insp:
        print(f"\n📅 {len(upcoming_insp)} upcoming inspection(s):")
        for insp in upcoming_insp:
            prop = pm.get_property(insp.property_id)
            print(
                f"   {insp.scheduled_date.strftime('%d/%m/%Y')} - {prop.full_address if prop else insp.property_id}"
            )

    print("\n" + "=" * 70)
    print("✅ Property Management Demo Complete!")
    print("\nFeatures demonstrated:")
    print("  • Multi-landlord property portfolio")
    print("  • Tenant onboarding and screening")
    print("  • Lease creation with bond lodgement")
    print("  • Rent collection and arrears tracking")
    print("  • Maintenance request workflow")
    print("  • Inspection scheduling with notice periods")
    print("  • Compliance monitoring")
    print("  • Landlord financial reporting")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
