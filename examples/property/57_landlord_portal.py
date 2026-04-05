#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 57: Landlord/Owner Portal

A portal for property owners to monitor their investment properties,
track rental income, approve expenses, and access reporting.

Features:
- Property performance dashboard
- Rental income tracking
- Expense management
- Tenant information (privacy compliant)
- Maintenance approvals
- Market rent analysis
- Tax report generation
- Document management

Australian-specific:
- EOFY tax reporting (depreciation schedules)
- Negative gearing considerations
- CGT implications tracking
- State-based landlord obligations

Usage:
    python examples/57_landlord_portal.py

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
# ENUMS AND CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════


class PropertyStatus(Enum):
    """Current status of a property."""

    LEASED = "Leased"
    VACANT = "Vacant"
    UNDER_APPLICATION = "Under Application"
    UNDER_MAINTENANCE = "Under Maintenance"
    FOR_SALE = "For Sale"


class ExpenseCategory(Enum):
    """Categories for property expenses."""

    MANAGEMENT_FEES = "Management Fees"
    REPAIRS_MAINTENANCE = "Repairs & Maintenance"
    COUNCIL_RATES = "Council Rates"
    WATER_RATES = "Water Rates"
    STRATA_LEVIES = "Strata/Body Corporate"
    INSURANCE = "Insurance"
    ADVERTISING = "Advertising/Letting Fees"
    LEGAL = "Legal Fees"
    PEST_CONTROL = "Pest Control"
    CLEANING = "Cleaning"
    GARDEN = "Gardening"
    OTHER = "Other"


class MaintenanceApprovalStatus(Enum):
    """Status of maintenance approval requests."""

    PENDING = "Pending Approval"
    APPROVED = "Approved"
    DECLINED = "Declined"
    MORE_INFO = "More Information Requested"


class DocumentType(Enum):
    """Types of documents available to landlords."""

    STATEMENT = "Monthly Statement"
    TAX_SUMMARY = "Tax Summary"
    INSPECTION_REPORT = "Inspection Report"
    LEASE_AGREEMENT = "Lease Agreement"
    INSURANCE = "Insurance Policy"
    DEPRECIATION = "Depreciation Schedule"
    RATES_NOTICE = "Rates Notice"
    STRATA_REPORT = "Strata Report"


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


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class LandlordProfile:
    """Landlord's profile information."""

    landlord_id: str
    name: str
    email: str
    phone: str
    postal_address: str

    # Financial details (masked for security)
    bsb: str = ""
    account_number: str = ""
    account_name: str = ""

    # Tax details
    abn: Optional[str] = None
    gst_registered: bool = False
    tax_file_number_provided: bool = True

    # Preferences
    statement_frequency: str = "monthly"
    email_notifications: bool = True
    sms_notifications: bool = False
    auto_approve_under: Decimal = Decimal("500")

    @property
    def masked_account(self) -> str:
        if self.account_number:
            return f"****{self.account_number[-4:]}"
        return ""


@dataclass
class PropertySummary:
    """Summary of a managed property."""

    property_id: str
    address: str
    suburb: str
    state: AustralianState
    postcode: str
    property_type: str
    bedrooms: int
    bathrooms: int
    parking: int
    status: PropertyStatus

    # Financial
    weekly_rent: Decimal
    management_fee_percent: Decimal
    purchase_price: Optional[Decimal] = None
    purchase_date: Optional[date] = None

    # Current lease
    current_tenant: Optional[str] = None  # First name only for privacy
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None

    # Tracking
    days_vacant_ytd: int = 0
    last_inspection: Optional[date] = None
    next_inspection: Optional[date] = None

    @property
    def full_address(self) -> str:
        return f"{self.address}, {self.suburb} {self.state.name} {self.postcode}"

    @property
    def annual_rent_potential(self) -> Decimal:
        return self.weekly_rent * 52

    @property
    def occupancy_status(self) -> str:
        if self.status == PropertyStatus.LEASED:
            return (
                f"Leased to {self.current_tenant}" if self.current_tenant else "Leased"
            )
        return self.status.value


@dataclass
class IncomeRecord:
    """A rental income record."""

    record_id: str
    property_id: str
    period_start: date
    period_end: date
    gross_rent: Decimal
    management_fee: Decimal
    other_deductions: Decimal = Decimal("0")
    net_amount: Decimal = Decimal("0")
    paid_date: Optional[date] = None

    def calculate_net(self):
        self.net_amount = self.gross_rent - self.management_fee - self.other_deductions


@dataclass
class ExpenseRecord:
    """An expense record for a property."""

    expense_id: str
    property_id: str
    date: date
    category: ExpenseCategory
    description: str
    amount: Decimal
    gst_included: Decimal = Decimal("0")
    invoice_number: str = ""
    paid: bool = False
    tax_deductible: bool = True


@dataclass
class MaintenanceApproval:
    """A maintenance request requiring landlord approval."""

    request_id: str
    property_id: str
    category: str
    description: str
    urgency: str

    # Quotes
    quotes: list[dict] = field(default_factory=list)
    recommended_quote_index: int = 0

    # Status
    status: MaintenanceApprovalStatus = MaintenanceApprovalStatus.PENDING
    submitted_date: datetime = field(default_factory=datetime.now)

    # Decision
    approved_amount: Optional[Decimal] = None
    decision_date: Optional[datetime] = None
    landlord_notes: str = ""

    @property
    def recommended_amount(self) -> Decimal:
        if self.quotes and len(self.quotes) > self.recommended_quote_index:
            return Decimal(
                str(self.quotes[self.recommended_quote_index].get("amount", 0))
            )
        return Decimal("0")


@dataclass
class MarketAnalysis:
    """Market rent analysis for a property."""

    property_id: str
    analysis_date: date
    current_rent: Decimal
    estimated_market_rent: Decimal
    comparable_properties: list[dict] = field(default_factory=list)
    recommendation: str = ""

    @property
    def variance_percent(self) -> float:
        if self.current_rent > 0:
            return float(
                (self.estimated_market_rent - self.current_rent)
                / self.current_rent
                * 100
            )
        return 0.0


@dataclass
class TaxSummary:
    """Annual tax summary for a property."""

    property_id: str
    financial_year: str  # e.g., "2025-26"

    # Income
    gross_rent: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")

    # Deductions
    management_fees: Decimal = Decimal("0")
    repairs_maintenance: Decimal = Decimal("0")
    council_rates: Decimal = Decimal("0")
    water_rates: Decimal = Decimal("0")
    insurance: Decimal = Decimal("0")
    strata_levies: Decimal = Decimal("0")
    interest: Decimal = Decimal("0")
    depreciation: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")

    @property
    def total_income(self) -> Decimal:
        return self.gross_rent + self.other_income

    @property
    def total_deductions(self) -> Decimal:
        return (
            self.management_fees
            + self.repairs_maintenance
            + self.council_rates
            + self.water_rates
            + self.insurance
            + self.strata_levies
            + self.interest
            + self.depreciation
            + self.other_deductions
        )

    @property
    def net_rental_income(self) -> Decimal:
        return self.total_income - self.total_deductions

    @property
    def is_negatively_geared(self) -> bool:
        return self.net_rental_income < 0


@dataclass
class Document:
    """A document available to the landlord."""

    document_id: str
    property_id: Optional[str]  # None for account-level docs
    document_type: DocumentType
    title: str
    filename: str
    upload_date: date
    period: Optional[str] = None  # e.g., "March 2026"


@dataclass
class PortfolioMetrics:
    """Overall portfolio metrics."""

    total_properties: int
    total_value: Decimal
    total_weekly_rent: Decimal
    occupancy_rate: float
    ytd_gross_income: Decimal
    ytd_expenses: Decimal
    ytd_net_income: Decimal
    properties_leased: int
    properties_vacant: int
    pending_approvals: int


# ══════════════════════════════════════════════════════════════════════════════
# LANDLORD PORTAL
# ══════════════════════════════════════════════════════════════════════════════


class LandlordPortal:
    """Self-service portal for landlords/property owners."""

    def __init__(self, landlord: LandlordProfile):
        """Initialize the landlord portal."""
        self.landlord = landlord

        # Data stores
        self.properties: dict[str, PropertySummary] = {}
        self.income_records: list[IncomeRecord] = []
        self.expenses: list[ExpenseRecord] = []
        self.maintenance_approvals: list[MaintenanceApproval] = []
        self.documents: list[Document] = []
        self.market_analyses: dict[str, MarketAnalysis] = {}

        # Session
        self.last_login: Optional[datetime] = None
        self.notifications: list[str] = []

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        random_part = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        return f"{prefix}-{random_part}"

    def login(self) -> dict:
        """Process landlord login and return dashboard data."""
        self.last_login = datetime.now()
        self._check_notifications()

        metrics = self.get_portfolio_metrics()

        return {
            "landlord": self.landlord.name,
            "notifications": self.notifications.copy(),
            "portfolio": {
                "total_properties": metrics.total_properties,
                "total_weekly_rent": float(metrics.total_weekly_rent),
                "occupancy_rate": f"{metrics.occupancy_rate:.0%}",
                "ytd_net_income": float(metrics.ytd_net_income),
            },
            "pending_approvals": metrics.pending_approvals,
            "vacant_properties": metrics.properties_vacant,
        }

    def _check_notifications(self):
        """Check for notifications to display."""
        self.notifications = []

        # Pending maintenance approvals
        pending = [
            m
            for m in self.maintenance_approvals
            if m.status == MaintenanceApprovalStatus.PENDING
        ]
        if pending:
            self.notifications.append(
                f"🔧 {len(pending)} maintenance request(s) awaiting your approval"
            )

        # Vacant properties
        vacant = [
            p for p in self.properties.values() if p.status == PropertyStatus.VACANT
        ]
        if vacant:
            self.notifications.append(
                f"🏠 {len(vacant)} property/properties currently vacant"
            )

        # Expiring leases
        for prop in self.properties.values():
            if prop.lease_end:
                days_remaining = (prop.lease_end - date.today()).days
                if 0 < days_remaining <= 60:
                    self.notifications.append(
                        f"📋 Lease at {prop.suburb} expires in {days_remaining} days"
                    )

        # Upcoming inspections
        for prop in self.properties.values():
            if prop.next_inspection:
                days_until = (prop.next_inspection - date.today()).days
                if 0 <= days_until <= 14:
                    self.notifications.append(
                        f"🔍 Inspection at {prop.suburb} in {days_until} days"
                    )

    # ─────────────────────────────────────────────────────────────────────────
    # PROPERTY MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def add_property(self, property: PropertySummary) -> str:
        """Add a property to the portfolio."""
        self.properties[property.property_id] = property
        return property.property_id

    def get_property(self, property_id: str) -> Optional[PropertySummary]:
        """Get property details."""
        return self.properties.get(property_id)

    def get_all_properties(self) -> list[PropertySummary]:
        """Get all properties in portfolio."""
        return list(self.properties.values())

    def get_property_performance(self, property_id: str, months: int = 12) -> dict:
        """Get performance metrics for a property."""
        prop = self.properties.get(property_id)
        if not prop:
            return {"error": "Property not found"}

        cutoff = date.today() - timedelta(days=months * 30)

        # Calculate income
        income = [
            r
            for r in self.income_records
            if r.property_id == property_id and r.period_start >= cutoff
        ]
        total_income = sum(r.gross_rent for r in income)
        total_fees = sum(r.management_fee for r in income)

        # Calculate expenses
        expenses = [
            e
            for e in self.expenses
            if e.property_id == property_id and e.date >= cutoff
        ]
        total_expenses = sum(e.amount for e in expenses)

        # ROI calculation
        net_income = total_income - total_fees - total_expenses
        annual_return = float(net_income) * (12 / months) if months > 0 else 0

        roi = 0.0
        if prop.purchase_price and prop.purchase_price > 0:
            roi = annual_return / float(prop.purchase_price) * 100

        return {
            "property": prop.full_address,
            "period_months": months,
            "gross_income": float(total_income),
            "management_fees": float(total_fees),
            "expenses": float(total_expenses),
            "net_income": float(net_income),
            "annualized_return": annual_return,
            "roi_percent": roi,
            "occupancy_days": (months * 30) - prop.days_vacant_ytd,
            "occupancy_rate": (
                1 - (prop.days_vacant_ytd / (months * 30)) if months > 0 else 1
            ),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # TENANT INFORMATION (PRIVACY COMPLIANT)
    # ─────────────────────────────────────────────────────────────────────────

    def get_tenant_summary(self, property_id: str) -> dict:
        """Get privacy-compliant tenant summary."""
        prop = self.properties.get(property_id)
        if not prop:
            return {"error": "Property not found"}

        if prop.status != PropertyStatus.LEASED:
            return {"status": "No current tenant"}

        # Only return limited information for privacy
        return {
            "status": "Occupied",
            "tenant_name": prop.current_tenant,  # First name only
            "lease_start": (
                prop.lease_start.strftime("%d/%m/%Y") if prop.lease_start else None
            ),
            "lease_end": (
                prop.lease_end.strftime("%d/%m/%Y") if prop.lease_end else "Periodic"
            ),
            "weekly_rent": float(prop.weekly_rent),
            "payment_status": "Up to date",  # Simplified status
            "note": "Full tenant details held by property manager for privacy compliance",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # INCOME & EXPENSES
    # ─────────────────────────────────────────────────────────────────────────

    def get_income_history(
        self, property_id: Optional[str] = None, months: int = 12
    ) -> list[IncomeRecord]:
        """Get income history."""
        cutoff = date.today() - timedelta(days=months * 30)
        records = [r for r in self.income_records if r.period_start >= cutoff]

        if property_id:
            records = [r for r in records if r.property_id == property_id]

        return sorted(records, key=lambda x: x.period_start, reverse=True)

    def get_expenses(
        self,
        property_id: Optional[str] = None,
        category: Optional[ExpenseCategory] = None,
        financial_year: Optional[str] = None,
    ) -> list[ExpenseRecord]:
        """Get expense records."""
        expenses = self.expenses.copy()

        if property_id:
            expenses = [e for e in expenses if e.property_id == property_id]

        if category:
            expenses = [e for e in expenses if e.category == category]

        if financial_year:
            # Parse FY and filter
            fy_start_year = int(financial_year.split("-")[0])
            fy_start = date(fy_start_year, 7, 1)
            fy_end = date(fy_start_year + 1, 6, 30)
            expenses = [e for e in expenses if fy_start <= e.date <= fy_end]

        return sorted(expenses, key=lambda x: x.date, reverse=True)

    def get_expense_summary(
        self, property_id: Optional[str] = None, financial_year: str = "2025-26"
    ) -> dict:
        """Get expense summary by category."""
        expenses = self.get_expenses(
            property_id=property_id, financial_year=financial_year
        )

        by_category = {}
        for exp in expenses:
            cat = exp.category.value
            if cat not in by_category:
                by_category[cat] = Decimal("0")
            by_category[cat] += exp.amount

        return {
            "financial_year": financial_year,
            "property_id": property_id or "All Properties",
            "total_expenses": float(sum(by_category.values())),
            "by_category": {k: float(v) for k, v in by_category.items()},
        }

    # ─────────────────────────────────────────────────────────────────────────
    # MAINTENANCE APPROVALS
    # ─────────────────────────────────────────────────────────────────────────

    def get_pending_approvals(self) -> list[MaintenanceApproval]:
        """Get maintenance requests pending approval."""
        return [
            m
            for m in self.maintenance_approvals
            if m.status == MaintenanceApprovalStatus.PENDING
        ]

    def get_approval_details(self, request_id: str) -> Optional[dict]:
        """Get details of a maintenance approval request."""
        for req in self.maintenance_approvals:
            if req.request_id == request_id:
                prop = self.properties.get(req.property_id)
                return {
                    "request_id": req.request_id,
                    "property": prop.full_address if prop else "Unknown",
                    "category": req.category,
                    "description": req.description,
                    "urgency": req.urgency,
                    "submitted": req.submitted_date.strftime("%d/%m/%Y %H:%M"),
                    "quotes": req.quotes,
                    "recommended_amount": float(req.recommended_amount),
                    "status": req.status.value,
                }
        return None

    def approve_maintenance(
        self, request_id: str, approved_amount: Decimal, notes: str = ""
    ) -> bool:
        """Approve a maintenance request."""
        for req in self.maintenance_approvals:
            if req.request_id == request_id:
                req.status = MaintenanceApprovalStatus.APPROVED
                req.approved_amount = approved_amount
                req.decision_date = datetime.now()
                req.landlord_notes = notes

                print(f"✅ Approved maintenance: {request_id} for ${approved_amount}")
                return True
        return False

    def decline_maintenance(self, request_id: str, reason: str) -> bool:
        """Decline a maintenance request."""
        for req in self.maintenance_approvals:
            if req.request_id == request_id:
                req.status = MaintenanceApprovalStatus.DECLINED
                req.decision_date = datetime.now()
                req.landlord_notes = reason

                print(f"❌ Declined maintenance: {request_id}")
                return True
        return False

    def request_more_info(self, request_id: str, questions: str) -> bool:
        """Request more information for a maintenance request."""
        for req in self.maintenance_approvals:
            if req.request_id == request_id:
                req.status = MaintenanceApprovalStatus.MORE_INFO
                req.landlord_notes = questions

                print(f"❓ Requested more info: {request_id}")
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # MARKET ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────

    def get_market_analysis(self, property_id: str) -> Optional[MarketAnalysis]:
        """Get market rent analysis for a property."""
        return self.market_analyses.get(property_id)

    def request_market_analysis(self, property_id: str) -> str:
        """Request a new market analysis for a property."""
        request_id = self._generate_id("MA")
        print(f"📊 Market analysis requested: {request_id}")
        print(
            "   Your property manager will provide a comparative market analysis within 5 business days."
        )
        return request_id

    # ─────────────────────────────────────────────────────────────────────────
    # TAX REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    def get_tax_summary(self, property_id: str, financial_year: str) -> TaxSummary:
        """Generate tax summary for a property."""
        prop = self.properties.get(property_id)
        if not prop:
            raise ValueError(f"Property {property_id} not found")

        # Parse financial year
        fy_start_year = int(financial_year.split("-")[0])
        fy_start = date(fy_start_year, 7, 1)
        fy_end = date(fy_start_year + 1, 6, 30)

        # Calculate income
        income = [
            r
            for r in self.income_records
            if r.property_id == property_id and fy_start <= r.period_start <= fy_end
        ]
        gross_rent = sum(r.gross_rent for r in income)
        management_fees = sum(r.management_fee for r in income)

        # Calculate expenses by category
        expenses = [
            e
            for e in self.expenses
            if e.property_id == property_id and fy_start <= e.date <= fy_end
        ]

        expense_totals = {}
        for exp in expenses:
            cat = exp.category
            if cat not in expense_totals:
                expense_totals[cat] = Decimal("0")
            expense_totals[cat] += exp.amount

        summary = TaxSummary(
            property_id=property_id,
            financial_year=financial_year,
            gross_rent=gross_rent,
            management_fees=management_fees,
            repairs_maintenance=expense_totals.get(
                ExpenseCategory.REPAIRS_MAINTENANCE, Decimal("0")
            ),
            council_rates=expense_totals.get(
                ExpenseCategory.COUNCIL_RATES, Decimal("0")
            ),
            water_rates=expense_totals.get(ExpenseCategory.WATER_RATES, Decimal("0")),
            insurance=expense_totals.get(ExpenseCategory.INSURANCE, Decimal("0")),
            strata_levies=expense_totals.get(
                ExpenseCategory.STRATA_LEVIES, Decimal("0")
            ),
        )

        return summary

    def get_eofy_summary(self, financial_year: str) -> dict:
        """Get end of financial year summary for all properties."""
        summaries = []
        total_income = Decimal("0")
        total_deductions = Decimal("0")

        for prop_id in self.properties:
            summary = self.get_tax_summary(prop_id, financial_year)
            summaries.append(
                {
                    "property": self.properties[prop_id].full_address,
                    "gross_rent": float(summary.gross_rent),
                    "total_deductions": float(summary.total_deductions),
                    "net_income": float(summary.net_rental_income),
                    "negatively_geared": summary.is_negatively_geared,
                }
            )
            total_income += summary.total_income
            total_deductions += summary.total_deductions

        return {
            "financial_year": financial_year,
            "properties": summaries,
            "portfolio_totals": {
                "total_income": float(total_income),
                "total_deductions": float(total_deductions),
                "net_rental_income": float(total_income - total_deductions),
            },
            "note": "This is a summary only. Please consult your accountant for tax advice.",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # DOCUMENTS
    # ─────────────────────────────────────────────────────────────────────────

    def get_documents(
        self, property_id: Optional[str] = None, doc_type: Optional[DocumentType] = None
    ) -> list[Document]:
        """Get available documents."""
        docs = self.documents.copy()

        if property_id:
            docs = [
                d for d in docs if d.property_id == property_id or d.property_id is None
            ]

        if doc_type:
            docs = [d for d in docs if d.document_type == doc_type]

        return sorted(docs, key=lambda x: x.upload_date, reverse=True)

    def get_statements(self, months: int = 12) -> list[Document]:
        """Get monthly statements."""
        return self.get_documents(doc_type=DocumentType.STATEMENT)[:months]

    # ─────────────────────────────────────────────────────────────────────────
    # PORTFOLIO METRICS
    # ─────────────────────────────────────────────────────────────────────────

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate overall portfolio metrics."""
        properties = list(self.properties.values())

        total_value = sum(p.purchase_price or Decimal("0") for p in properties)
        total_weekly_rent = sum(
            p.weekly_rent for p in properties if p.status == PropertyStatus.LEASED
        )

        leased = len([p for p in properties if p.status == PropertyStatus.LEASED])
        vacant = len([p for p in properties if p.status == PropertyStatus.VACANT])

        occupancy = leased / len(properties) if properties else 0

        # YTD calculations
        fy_start = date(
            date.today().year if date.today().month >= 7 else date.today().year - 1,
            7,
            1,
        )

        ytd_income = sum(
            r.gross_rent for r in self.income_records if r.period_start >= fy_start
        )
        ytd_expenses = sum(e.amount for e in self.expenses if e.date >= fy_start)
        ytd_fees = sum(
            r.management_fee for r in self.income_records if r.period_start >= fy_start
        )

        pending = len(
            [
                m
                for m in self.maintenance_approvals
                if m.status == MaintenanceApprovalStatus.PENDING
            ]
        )

        return PortfolioMetrics(
            total_properties=len(properties),
            total_value=total_value,
            total_weekly_rent=total_weekly_rent,
            occupancy_rate=occupancy,
            ytd_gross_income=ytd_income,
            ytd_expenses=ytd_expenses + ytd_fees,
            ytd_net_income=ytd_income - ytd_expenses - ytd_fees,
            properties_leased=leased,
            properties_vacant=vacant,
            pending_approvals=pending,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT SETTINGS
    # ─────────────────────────────────────────────────────────────────────────

    def update_payment_details(
        self, bsb: str, account_number: str, account_name: str
    ) -> bool:
        """Update bank account details for rent disbursement."""
        # In production, this would require additional verification
        self.landlord.bsb = bsb
        self.landlord.account_number = account_number
        self.landlord.account_name = account_name

        print("✅ Bank details updated (pending verification)")
        print("   A confirmation email has been sent to your registered address.")
        return True

    def update_notification_preferences(
        self,
        email: bool = True,
        sms: bool = False,
        auto_approve_under: Decimal = Decimal("500"),
    ) -> bool:
        """Update notification and approval preferences."""
        self.landlord.email_notifications = email
        self.landlord.sms_notifications = sms
        self.landlord.auto_approve_under = auto_approve_under

        print("✅ Preferences updated")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA GENERATORS
# ══════════════════════════════════════════════════════════════════════════════


def create_demo_landlord() -> LandlordProfile:
    """Create a demo landlord profile."""
    return LandlordProfile(
        landlord_id="LAND-2024",
        name="Margaret Chen",
        email="margaret.chen@email.com.au",
        phone="0412 345 678",
        postal_address="45 Investment Avenue, Unley SA 5061",
        bsb="105-029",
        account_number="12345678",
        account_name="M CHEN",
        auto_approve_under=Decimal("750"),
    )


def populate_demo_data(portal: LandlordPortal):
    """Populate portal with demo data."""

    # Add properties
    properties = [
        PropertySummary(
            property_id="PROP-001",
            address="Unit 5/123 Wakefield Street",
            suburb="Adelaide",
            state=AustralianState.SA,
            postcode="5000",
            property_type="Apartment",
            bedrooms=2,
            bathrooms=1,
            parking=1,
            status=PropertyStatus.LEASED,
            weekly_rent=Decimal("520"),
            management_fee_percent=Decimal("8.0"),
            purchase_price=Decimal("450000"),
            purchase_date=date(2019, 3, 15),
            current_tenant="Sarah M.",
            lease_start=date(2025, 6, 1),
            lease_end=date(2026, 5, 31),
            last_inspection=date(2025, 12, 15),
            next_inspection=date(2026, 3, 20),
        ),
        PropertySummary(
            property_id="PROP-002",
            address="8 Jacaranda Crescent",
            suburb="Mawson Lakes",
            state=AustralianState.SA,
            postcode="5095",
            property_type="House",
            bedrooms=4,
            bathrooms=2,
            parking=2,
            status=PropertyStatus.LEASED,
            weekly_rent=Decimal("650"),
            management_fee_percent=Decimal("7.5"),
            purchase_price=Decimal("680000"),
            purchase_date=date(2021, 8, 1),
            current_tenant="James A.",
            lease_start=date(2025, 3, 15),
            lease_end=date(2026, 3, 14),
            last_inspection=date(2025, 9, 20),
            next_inspection=date(2026, 3, 25),
        ),
        PropertySummary(
            property_id="PROP-003",
            address="22 Willow Avenue",
            suburb="Norwood",
            state=AustralianState.SA,
            postcode="5067",
            property_type="Townhouse",
            bedrooms=3,
            bathrooms=2,
            parking=2,
            status=PropertyStatus.VACANT,
            weekly_rent=Decimal("590"),
            management_fee_percent=Decimal("8.0"),
            purchase_price=Decimal("620000"),
            purchase_date=date(2022, 5, 20),
            days_vacant_ytd=21,
        ),
    ]

    for prop in properties:
        portal.add_property(prop)

    # Add income records
    today = date.today()
    for prop_id in ["PROP-001", "PROP-002"]:
        prop = portal.properties[prop_id]
        for i in range(12):
            period_start = today - timedelta(weeks=i + 1)
            gross = prop.weekly_rent
            fee = gross * prop.management_fee_percent / 100

            record = IncomeRecord(
                record_id=f"INC-{prop_id[-3:]}-{12-i:03d}",
                property_id=prop_id,
                period_start=period_start,
                period_end=period_start + timedelta(days=6),
                gross_rent=gross,
                management_fee=fee,
            )
            record.calculate_net()
            portal.income_records.append(record)

    # Add expenses
    expenses_data = [
        ("PROP-001", ExpenseCategory.COUNCIL_RATES, "Q3 Council Rates", Decimal("450")),
        ("PROP-001", ExpenseCategory.WATER_RATES, "Water Usage Q3", Decimal("120")),
        ("PROP-001", ExpenseCategory.STRATA_LEVIES, "Strata Q3", Decimal("890")),
        ("PROP-002", ExpenseCategory.COUNCIL_RATES, "Q3 Council Rates", Decimal("520")),
        ("PROP-002", ExpenseCategory.INSURANCE, "Annual Insurance", Decimal("1450")),
        (
            "PROP-002",
            ExpenseCategory.REPAIRS_MAINTENANCE,
            "Hot water system repair",
            Decimal("380"),
        ),
        ("PROP-003", ExpenseCategory.ADVERTISING, "Listing fees", Decimal("220")),
        ("PROP-003", ExpenseCategory.CLEANING, "Vacancy clean", Decimal("350")),
    ]

    for prop_id, category, desc, amount in expenses_data:
        portal.expenses.append(
            ExpenseRecord(
                expense_id=portal._generate_id("EXP"),
                property_id=prop_id,
                date=today - timedelta(days=random.randint(10, 90)),
                category=category,
                description=desc,
                amount=amount,
                paid=True,
            )
        )

    # Add pending maintenance approval
    portal.maintenance_approvals.append(
        MaintenanceApproval(
            request_id="MAINT-PEND-01",
            property_id="PROP-001",
            category="Plumbing",
            description="Kitchen tap leaking. Washer needs replacement, possibly entire tap if worn.",
            urgency="Routine",
            quotes=[
                {
                    "tradesperson": "Quick Fix Plumbing",
                    "amount": 180,
                    "available": "2 days",
                },
                {
                    "tradesperson": "City Plumbers",
                    "amount": 220,
                    "available": "Same day",
                },
                {
                    "tradesperson": "AA Plumbing Services",
                    "amount": 165,
                    "available": "4 days",
                },
            ],
            recommended_quote_index=2,
            submitted_date=datetime.now() - timedelta(days=2),
        )
    )

    portal.maintenance_approvals.append(
        MaintenanceApproval(
            request_id="MAINT-PEND-02",
            property_id="PROP-002",
            category="Electrical",
            description="Power point in living room not working. May need replacement.",
            urgency="Urgent",
            quotes=[
                {
                    "tradesperson": "Sparky Electrical",
                    "amount": 150,
                    "available": "Tomorrow",
                },
                {
                    "tradesperson": "SA Electrical",
                    "amount": 185,
                    "available": "Same day",
                },
            ],
            recommended_quote_index=0,
            submitted_date=datetime.now() - timedelta(hours=6),
        )
    )

    # Add market analysis
    portal.market_analyses["PROP-001"] = MarketAnalysis(
        property_id="PROP-001",
        analysis_date=date.today() - timedelta(days=30),
        current_rent=Decimal("520"),
        estimated_market_rent=Decimal("550"),
        comparable_properties=[
            {"address": "Unit 8/125 Wakefield St", "rent": 540, "beds": 2, "baths": 1},
            {"address": "Unit 3/130 Wakefield St", "rent": 560, "beds": 2, "baths": 1},
            {"address": "Unit 12/120 Wakefield St", "rent": 530, "beds": 2, "baths": 1},
        ],
        recommendation="Current rent is approximately 5.5% below market. Consider increase at lease renewal.",
    )

    # Add documents
    for prop in properties:
        # Monthly statements
        for i in range(6):
            month_date = today - timedelta(days=30 * i)
            portal.documents.append(
                Document(
                    document_id=portal._generate_id("DOC"),
                    property_id=prop.property_id,
                    document_type=DocumentType.STATEMENT,
                    title=f"Monthly Statement - {month_date.strftime('%B %Y')}",
                    filename=f"statement_{prop.property_id}_{month_date.strftime('%Y%m')}.pdf",
                    upload_date=month_date,
                    period=month_date.strftime("%B %Y"),
                )
            )

    # Account level documents
    portal.documents.append(
        Document(
            document_id=portal._generate_id("DOC"),
            property_id=None,
            document_type=DocumentType.TAX_SUMMARY,
            title="Tax Summary FY2024-25",
            filename="tax_summary_2024-25.pdf",
            upload_date=date(2025, 7, 15),
            period="2024-25",
        )
    )


# ══════════════════════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate the landlord portal."""

    print("=" * 70)
    print("Landlord/Owner Portal Demo")
    print("Investment Property Management")
    print("=" * 70)

    # Create landlord and portal
    landlord = create_demo_landlord()
    portal = LandlordPortal(landlord)

    # Populate demo data
    populate_demo_data(portal)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Login
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔐 Landlord Login")
    print("─" * 50)

    dashboard = portal.login()
    print(f"\n👋 Welcome, {dashboard['landlord']}!")

    if dashboard["notifications"]:
        print("\n🔔 Notifications:")
        for notif in dashboard["notifications"]:
            print(f"   {notif}")

    portfolio = dashboard["portfolio"]
    print("\n📊 Portfolio Overview:")
    print(f"   Properties: {portfolio['total_properties']}")
    print(f"   Weekly Rent: ${portfolio['total_weekly_rent']:.2f}")
    print(f"   Occupancy: {portfolio['occupancy_rate']}")
    print(f"   YTD Net Income: ${portfolio['ytd_net_income']:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Property Performance
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🏠 Property Performance")
    print("─" * 50)

    for prop in portal.get_all_properties():
        print(f"\n📍 {prop.full_address}")
        print(
            f"   Type: {prop.property_type} ({prop.bedrooms} bed, {prop.bathrooms} bath)"
        )
        print(f"   Status: {prop.occupancy_status}")
        print(f"   Weekly Rent: ${prop.weekly_rent}")

        if prop.status == PropertyStatus.LEASED:
            perf = portal.get_property_performance(prop.property_id, months=12)
            print("   12-Month Performance:")
            print(f"      Gross Income: ${perf['gross_income']:.2f}")
            print(f"      Net Income: ${perf['net_income']:.2f}")
            print(f"      ROI: {perf['roi_percent']:.1f}%")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Tenant Information
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("👥 Tenant Information (Privacy Compliant)")
    print("─" * 50)

    for prop_id in ["PROP-001", "PROP-002"]:
        summary = portal.get_tenant_summary(prop_id)
        prop = portal.get_property(prop_id)
        print(f"\n📍 {prop.suburb}:")
        print(f"   Tenant: {summary.get('tenant_name', 'N/A')}")
        print(f"   Lease End: {summary.get('lease_end', 'N/A')}")
        print(f"   Payment Status: {summary.get('payment_status', 'N/A')}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Maintenance Approvals
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("🔧 Pending Maintenance Approvals")
    print("─" * 50)

    pending = portal.get_pending_approvals()
    for req in pending:
        portal.get_approval_details(req.request_id)
        print(f"\n📋 {req.request_id}")
        print(f"   Property: {portal.get_property(req.property_id).suburb}")
        print(f"   Category: {req.category}")
        print(f"   Description: {req.description}")
        print(f"   Urgency: {req.urgency}")
        print(f"   Quotes received: {len(req.quotes)}")
        for i, quote in enumerate(req.quotes):
            marker = "→ " if i == req.recommended_quote_index else "  "
            print(
                f"      {marker}${quote['amount']} - {quote['tradesperson']} ({quote['available']})"
            )

    # Approve one
    if pending:
        print("\n✅ Approving first maintenance request...")
        portal.approve_maintenance(
            pending[0].request_id,
            approved_amount=pending[0].recommended_amount,
            notes="Please proceed with recommended tradesperson",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Market Analysis
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📊 Market Rent Analysis")
    print("─" * 50)

    analysis = portal.get_market_analysis("PROP-001")
    if analysis:
        print("\n📍 Adelaide CBD Apartment:")
        print(f"   Current Rent: ${analysis.current_rent}/week")
        print(f"   Market Estimate: ${analysis.estimated_market_rent}/week")
        print(f"   Variance: {analysis.variance_percent:+.1f}%")
        print("\n   Comparable Properties:")
        for comp in analysis.comparable_properties:
            print(f"      • {comp['address']}: ${comp['rent']}/week")
        print(f"\n   💡 Recommendation: {analysis.recommendation}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Financial Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("💰 Financial Summary")
    print("─" * 50)

    # Recent income
    income = portal.get_income_history(months=3)
    total_income = sum(r.gross_rent for r in income)
    total_fees = sum(r.management_fee for r in income)
    print("\n📈 Last 3 Months:")
    print(f"   Gross Rent: ${total_income:.2f}")
    print(f"   Management Fees: ${total_fees:.2f}")
    print(f"   Net Income: ${total_income - total_fees:.2f}")

    # Expenses by category
    expense_summary = portal.get_expense_summary(financial_year="2025-26")
    print("\n📉 Expenses (FY 2025-26):")
    for category, amount in expense_summary["by_category"].items():
        print(f"   {category}: ${amount:.2f}")
    print(f"   Total: ${expense_summary['total_expenses']:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Tax Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📋 Tax Summary (FY 2025-26)")
    print("─" * 50)

    eofy = portal.get_eofy_summary("2025-26")

    for prop_summary in eofy["properties"]:
        print(f"\n📍 {prop_summary['property'][:40]}...")
        print(f"   Gross Rent: ${prop_summary['gross_rent']:.2f}")
        print(f"   Deductions: ${prop_summary['total_deductions']:.2f}")
        print(f"   Net Income: ${prop_summary['net_income']:.2f}")
        if prop_summary["negatively_geared"]:
            print("   ⚠️ Negatively geared")

    totals = eofy["portfolio_totals"]
    print("\n📊 Portfolio Totals:")
    print(f"   Total Income: ${totals['total_income']:.2f}")
    print(f"   Total Deductions: ${totals['total_deductions']:.2f}")
    print(f"   Net Rental Income: ${totals['net_rental_income']:.2f}")
    print(f"\n⚠️ {eofy['note']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Documents
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print("📄 Documents")
    print("─" * 50)

    statements = portal.get_statements(months=3)
    print(f"\n📁 Recent Statements ({len(statements)} available):")
    for stmt in statements[:5]:
        print(f"   📄 {stmt.title}")

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("✅ Landlord Portal Demo Complete!")
    print("\nFeatures demonstrated:")
    print("  • Portfolio overview and metrics")
    print("  • Property performance analysis")
    print("  • Privacy-compliant tenant information")
    print("  • Maintenance approval workflow")
    print("  • Market rent analysis")
    print("  • Income and expense tracking")
    print("  • Tax reporting (EOFY summaries)")
    print("  • Document management")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
