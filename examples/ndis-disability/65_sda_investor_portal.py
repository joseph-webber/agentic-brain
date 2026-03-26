#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
SDA Investor Portal - Investor Self-Service Portal
===================================================

Self-service portal for SDA property investors and syndicate members.
Provides transparency, reduces support calls, and improves investor satisfaction.

FEATURES:
- View owned properties and ownership percentages
- Download PDF statements
- Track distributions and payments
- Property photos and condition reports
- Tax summary reports
- Investment performance analytics
- Secure document vault

Author: Agentic Brain Framework
License: MIT
"""

import os
import json
import hashlib
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from pathlib import Path
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class DocumentType(Enum):
    """Types of documents in investor portal."""

    DISTRIBUTION_STATEMENT = "distribution_statement"
    TAX_SUMMARY = "tax_summary"
    ANNUAL_REPORT = "annual_report"
    PROPERTY_REPORT = "property_report"
    CONDITION_REPORT = "condition_report"
    COMPLIANCE_CERTIFICATE = "compliance_certificate"
    VALUATION = "valuation"
    INSURANCE = "insurance"
    CONTRACT = "contract"
    OTHER = "other"


class PaymentStatus(Enum):
    """Payment status for distributions."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class PortfolioSummaryPeriod(Enum):
    """Time periods for portfolio summaries."""

    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    FINANCIAL_YEAR = "financial_year"
    ALL_TIME = "all_time"


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class Investor:
    """Investor/syndicate member profile."""

    investor_id: str
    name: str
    email: str
    phone: str
    address: str
    tax_file_number: str  # Masked for security
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    two_factor_enabled: bool = False
    notification_preferences: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self):
        if not self.notification_preferences:
            self.notification_preferences = {
                "email_distributions": True,
                "email_statements": True,
                "email_reports": True,
                "sms_payments": False,
            }


@dataclass
class PropertyInvestment:
    """Investor's stake in a property."""

    investment_id: str
    investor_id: str
    property_id: str
    property_address: str
    property_suburb: str
    sda_category: str
    ownership_percent: Decimal
    investment_date: date
    investment_amount: Decimal
    current_value: Decimal
    is_active: bool = True

    def __post_init__(self):
        self.ownership_percent = Decimal(str(self.ownership_percent))
        self.investment_amount = Decimal(str(self.investment_amount))
        self.current_value = Decimal(str(self.current_value))

    @property
    def capital_gain(self) -> Decimal:
        return self.current_value - self.investment_amount

    @property
    def capital_gain_percent(self) -> Decimal:
        if self.investment_amount == 0:
            return Decimal("0")
        return (
            (self.current_value - self.investment_amount) / self.investment_amount * 100
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class DistributionPayment:
    """Distribution payment to investor."""

    payment_id: str
    investor_id: str
    property_id: str
    property_address: str
    period_start: date
    period_end: date
    gross_income: Decimal
    management_fee: Decimal
    expenses: Decimal
    net_income: Decimal
    ownership_percent: Decimal
    distribution_amount: Decimal
    status: PaymentStatus = PaymentStatus.PENDING
    payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    bank_bsb: str = ""
    bank_account: str = ""

    def __post_init__(self):
        self.gross_income = Decimal(str(self.gross_income))
        self.management_fee = Decimal(str(self.management_fee))
        self.expenses = Decimal(str(self.expenses))
        self.net_income = Decimal(str(self.net_income))
        self.ownership_percent = Decimal(str(self.ownership_percent))
        self.distribution_amount = Decimal(str(self.distribution_amount))


@dataclass
class Document:
    """Document in investor document vault."""

    document_id: str
    investor_id: str
    property_id: Optional[str]
    document_type: DocumentType
    title: str
    description: str
    filename: str
    file_size: int
    mime_type: str
    uploaded_at: datetime = field(default_factory=datetime.now)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    is_read: bool = False
    download_count: int = 0
    content_hash: str = ""


@dataclass
class PropertyPhoto:
    """Property photo for investor viewing."""

    photo_id: str
    property_id: str
    title: str
    description: str
    filename: str
    taken_date: date
    category: str  # exterior, interior, accessibility_features, etc.
    is_primary: bool = False
    thumbnail_base64: str = ""


@dataclass
class TaxSummary:
    """Annual tax summary for investor."""

    summary_id: str
    investor_id: str
    financial_year: str  # e.g., "2024-25"
    total_distributions: Decimal
    total_deductions: Decimal
    depreciation_amount: Decimal
    capital_works_deduction: Decimal
    net_rental_income: Decimal
    franking_credits: Decimal
    properties: List[Dict] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.total_distributions = Decimal(str(self.total_distributions))
        self.total_deductions = Decimal(str(self.total_deductions))
        self.depreciation_amount = Decimal(str(self.depreciation_amount))
        self.capital_works_deduction = Decimal(str(self.capital_works_deduction))
        self.net_rental_income = Decimal(str(self.net_rental_income))
        self.franking_credits = Decimal(str(self.franking_credits))


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""

    total_invested: Decimal
    current_value: Decimal
    total_distributions_received: Decimal
    average_yield: Decimal
    capital_growth: Decimal
    total_return: Decimal
    property_count: int
    period: PortfolioSummaryPeriod
    period_distributions: Decimal

    def __post_init__(self):
        self.total_invested = Decimal(str(self.total_invested))
        self.current_value = Decimal(str(self.current_value))
        self.total_distributions_received = Decimal(
            str(self.total_distributions_received)
        )
        self.average_yield = Decimal(str(self.average_yield))
        self.capital_growth = Decimal(str(self.capital_growth))
        self.total_return = Decimal(str(self.total_return))
        self.period_distributions = Decimal(str(self.period_distributions))


# ============================================================================
# STATEMENT GENERATOR
# ============================================================================


class StatementGenerator:
    """
    Generate PDF-style statements for investors.

    In production, this would use a PDF library like ReportLab or WeasyPrint.
    For demo, generates formatted text that could be converted to PDF.
    """

    def __init__(self, company_name: str = "SDA Housing Provider Pty Ltd"):
        self.company_name = company_name
        self.company_address = "Level 10, 123 Example Street, Sydney NSW 2000"
        self.company_phone = "1800 123 456"
        self.company_email = "investors@sdahousing.example.com"
        self.company_abn = "12 345 678 901"

    def generate_distribution_statement(
        self,
        investor: Investor,
        payment: DistributionPayment,
    ) -> str:
        """Generate a distribution statement."""
        statement = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         DISTRIBUTION STATEMENT                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

{self.company_name}
{self.company_address}
ABN: {self.company_abn}
Phone: {self.company_phone}
Email: {self.company_email}

--------------------------------------------------------------------------------
INVESTOR DETAILS
--------------------------------------------------------------------------------
Name:           {investor.name}
Investor ID:    {investor.investor_id}
Address:        {investor.address}

--------------------------------------------------------------------------------
PROPERTY DETAILS
--------------------------------------------------------------------------------
Property:       {payment.property_address}
Your Ownership: {payment.ownership_percent}%
Period:         {payment.period_start.strftime('%d %B %Y')} to {payment.period_end.strftime('%d %B %Y')}

--------------------------------------------------------------------------------
INCOME & EXPENSES
--------------------------------------------------------------------------------
Gross Rental Income:                              ${payment.gross_income:>12,.2f}

Less: Management Fee:                             ${payment.management_fee:>12,.2f}
Less: Property Expenses:                          ${payment.expenses:>12,.2f}
                                                  ────────────────
Net Property Income:                              ${payment.net_income:>12,.2f}

--------------------------------------------------------------------------------
YOUR DISTRIBUTION
--------------------------------------------------------------------------------
Your Share ({payment.ownership_percent}% of ${payment.net_income:,.2f}):      ${payment.distribution_amount:>12,.2f}

================================================================================
                              PAYMENT DETAILS
================================================================================

Payment Amount:     ${payment.distribution_amount:,.2f}
Payment Date:       {payment.payment_date.strftime('%d %B %Y') if payment.payment_date else 'Pending'}
Payment Reference:  {payment.payment_reference or 'N/A'}
Status:             {payment.status.value.upper()}

Paid to:
  BSB:      {payment.bank_bsb}
  Account:  ****{payment.bank_account[-4:] if len(payment.bank_account) >= 4 else '****'}

--------------------------------------------------------------------------------

This statement is provided for your records and tax purposes.
Please retain for your tax return.

For queries, contact us at {self.company_email}

Statement generated: {datetime.now().strftime('%d %B %Y at %H:%M')}
Reference: {payment.payment_id}

╚══════════════════════════════════════════════════════════════════════════════╝
"""
        return statement

    def generate_tax_summary(self, investor: Investor, tax_summary: TaxSummary) -> str:
        """Generate annual tax summary."""
        properties_section = ""
        for prop in tax_summary.properties:
            properties_section += f"""
  Property: {prop.get('address', 'Unknown')}
    - Your Ownership: {prop.get('ownership_percent', 0)}%
    - Gross Income: ${prop.get('gross_income', 0):,.2f}
    - Net Income: ${prop.get('net_income', 0):,.2f}
    - Depreciation: ${prop.get('depreciation', 0):,.2f}
"""

        summary = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        ANNUAL TAX SUMMARY                                     ║
║                     Financial Year {tax_summary.financial_year}                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

{self.company_name}
ABN: {self.company_abn}

--------------------------------------------------------------------------------
INVESTOR DETAILS
--------------------------------------------------------------------------------
Name:           {investor.name}
Investor ID:    {investor.investor_id}
TFN:            ***-***-{investor.tax_file_number[-3:] if len(investor.tax_file_number) >= 3 else '***'}

--------------------------------------------------------------------------------
SUMMARY FOR TAX RETURN
--------------------------------------------------------------------------------

INCOME:
Total Rental Distributions Received:              ${tax_summary.total_distributions:>12,.2f}

DEDUCTIONS:
Depreciation (Division 40):                       ${tax_summary.depreciation_amount:>12,.2f}
Capital Works Deduction (Division 43):            ${tax_summary.capital_works_deduction:>12,.2f}
Management & Other Deductions:                    ${tax_summary.total_deductions:>12,.2f}
                                                  ────────────────
Total Deductions:                                 ${(tax_summary.depreciation_amount + tax_summary.capital_works_deduction + tax_summary.total_deductions):>12,.2f}

================================================================================
NET RENTAL INCOME (for tax return):               ${tax_summary.net_rental_income:>12,.2f}
================================================================================

Franking Credits (if applicable):                 ${tax_summary.franking_credits:>12,.2f}

--------------------------------------------------------------------------------
PROPERTY BREAKDOWN
--------------------------------------------------------------------------------
{properties_section}

--------------------------------------------------------------------------------
IMPORTANT TAX NOTES
--------------------------------------------------------------------------------
• This summary is provided as a guide only and does not constitute tax advice.
• Please consult your tax professional for your specific circumstances.
• Retain all distribution statements for your records.
• SDA properties may have specific depreciation schedules - contact us for details.

Statement generated: {datetime.now().strftime('%d %B %Y')}
Summary ID: {tax_summary.summary_id}

For tax queries: {self.company_email}

╚══════════════════════════════════════════════════════════════════════════════╝
"""
        return summary

    def generate_portfolio_report(
        self,
        investor: Investor,
        investments: List[PropertyInvestment],
        metrics: PortfolioMetrics,
    ) -> str:
        """Generate portfolio performance report."""
        properties_section = ""
        for inv in investments:
            gain_indicator = "📈" if inv.capital_gain >= 0 else "📉"
            properties_section += f"""
  {inv.property_address}, {inv.property_suburb}
    - SDA Category: {inv.sda_category.replace('_', ' ').title()}
    - Ownership: {inv.ownership_percent}%
    - Investment: ${inv.investment_amount:,.2f}
    - Current Value: ${inv.current_value:,.2f}
    - Capital Gain: {gain_indicator} ${inv.capital_gain:,.2f} ({inv.capital_gain_percent:+.1f}%)
"""

        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      PORTFOLIO PERFORMANCE REPORT                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

{self.company_name}

--------------------------------------------------------------------------------
INVESTOR
--------------------------------------------------------------------------------
{investor.name}
{investor.investor_id}

Report Period: {metrics.period.value.replace('_', ' ').title()}
Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}

================================================================================
                            PORTFOLIO SUMMARY
================================================================================

📊 INVESTMENT OVERVIEW
-----------------------------
Properties Owned:                                 {metrics.property_count:>12}
Total Amount Invested:                            ${metrics.total_invested:>12,.2f}
Current Portfolio Value:                          ${metrics.current_value:>12,.2f}

📈 PERFORMANCE METRICS
-----------------------------
Capital Growth:                                   ${metrics.capital_growth:>12,.2f}
Capital Growth (%):                               {((metrics.capital_growth / metrics.total_invested) * 100) if metrics.total_invested > 0 else 0:>12.1f}%

Total Distributions (All Time):                   ${metrics.total_distributions_received:>12,.2f}
Period Distributions:                             ${metrics.period_distributions:>12,.2f}

Average Yield:                                    {metrics.average_yield:>12.2f}%
Total Return:                                     {metrics.total_return:>12.2f}%

--------------------------------------------------------------------------------
PROPERTY DETAILS
--------------------------------------------------------------------------------
{properties_section}

--------------------------------------------------------------------------------
MARKET COMMENTARY
--------------------------------------------------------------------------------
SDA (Specialist Disability Accommodation) continues to be a stable investment
class with government-backed NDIS funding providing consistent rental income.
Your portfolio benefits from:
• Long-term NDIS participant tenancies
• Inflation-linked rent increases
• Tax-effective depreciation benefits
• Growing demand for accessible housing

For investment queries: {self.company_email}

╚══════════════════════════════════════════════════════════════════════════════╝
"""
        return report


# ============================================================================
# INVESTOR PORTAL
# ============================================================================


class InvestorPortal:
    """
    Self-service portal for SDA property investors.

    Features:
    - Portfolio overview
    - Distribution tracking
    - Document vault
    - Tax summaries
    - Property photos
    - Performance analytics
    """

    def __init__(self, company_name: str = "SDA Housing Provider Pty Ltd"):
        self.company_name = company_name
        self.statement_generator = StatementGenerator(company_name)

        # Data stores
        self.investors: Dict[str, Investor] = {}
        self.investments: Dict[str, PropertyInvestment] = {}
        self.payments: Dict[str, DistributionPayment] = {}
        self.documents: Dict[str, Document] = {}
        self.photos: Dict[str, PropertyPhoto] = {}
        self.tax_summaries: Dict[str, TaxSummary] = {}

    def register_investor(self, investor: Investor):
        """Register a new investor."""
        self.investors[investor.investor_id] = investor
        logger.info(f"Registered investor: {investor.investor_id}")

    def add_investment(self, investment: PropertyInvestment):
        """Add an investment to an investor's portfolio."""
        self.investments[investment.investment_id] = investment
        logger.info(f"Added investment: {investment.investment_id}")

    def record_payment(self, payment: DistributionPayment):
        """Record a distribution payment."""
        self.payments[payment.payment_id] = payment
        logger.info(f"Recorded payment: {payment.payment_id}")

    def upload_document(self, document: Document):
        """Upload a document to the vault."""
        self.documents[document.document_id] = document
        logger.info(f"Uploaded document: {document.document_id}")

    def add_photo(self, photo: PropertyPhoto):
        """Add a property photo."""
        self.photos[photo.photo_id] = photo

    def record_tax_summary(self, tax_summary: TaxSummary):
        """Record a tax summary."""
        self.tax_summaries[tax_summary.summary_id] = tax_summary

    def get_investor_portfolio(self, investor_id: str) -> Dict[str, Any]:
        """Get complete portfolio for an investor."""
        investor = self.investors.get(investor_id)
        if not investor:
            return {"error": "Investor not found"}

        # Get investments
        investor_investments = [
            inv
            for inv in self.investments.values()
            if inv.investor_id == investor_id and inv.is_active
        ]

        # Get payments
        investor_payments = [
            p for p in self.payments.values() if p.investor_id == investor_id
        ]

        # Calculate totals
        total_invested = sum(inv.investment_amount for inv in investor_investments)
        current_value = sum(inv.current_value for inv in investor_investments)
        total_distributions = sum(
            p.distribution_amount
            for p in investor_payments
            if p.status == PaymentStatus.COMPLETED
        )

        return {
            "investor": {
                "name": investor.name,
                "email": investor.email,
                "member_since": investor.created_at.strftime("%B %Y"),
            },
            "portfolio": {
                "property_count": len(investor_investments),
                "total_invested": f"${total_invested:,.2f}",
                "current_value": f"${current_value:,.2f}",
                "capital_growth": f"${current_value - total_invested:,.2f}",
                "total_distributions": f"${total_distributions:,.2f}",
            },
            "properties": [
                {
                    "address": inv.property_address,
                    "suburb": inv.property_suburb,
                    "ownership": f"{inv.ownership_percent}%",
                    "category": inv.sda_category.replace("_", " ").title(),
                    "invested": f"${inv.investment_amount:,.2f}",
                    "current_value": f"${inv.current_value:,.2f}",
                    "gain": f"${inv.capital_gain:,.2f}",
                }
                for inv in investor_investments
            ],
        }

    def get_payment_history(
        self,
        investor_id: str,
        limit: int = 10,
        status_filter: Optional[PaymentStatus] = None,
    ) -> List[Dict]:
        """Get payment history for an investor."""
        payments = [p for p in self.payments.values() if p.investor_id == investor_id]

        if status_filter:
            payments = [p for p in payments if p.status == status_filter]

        # Sort by period end (most recent first)
        payments.sort(key=lambda p: p.period_end, reverse=True)

        return [
            {
                "payment_id": p.payment_id,
                "property": p.property_address,
                "period": f"{p.period_start.strftime('%b')} - {p.period_end.strftime('%b %Y')}",
                "amount": f"${p.distribution_amount:,.2f}",
                "status": p.status.value,
                "payment_date": (
                    p.payment_date.strftime("%d/%m/%Y") if p.payment_date else "Pending"
                ),
            }
            for p in payments[:limit]
        ]

    def get_documents(
        self,
        investor_id: str,
        doc_type: Optional[DocumentType] = None,
        property_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get documents for an investor."""
        docs = [d for d in self.documents.values() if d.investor_id == investor_id]

        if doc_type:
            docs = [d for d in docs if d.document_type == doc_type]

        if property_id:
            docs = [d for d in docs if d.property_id == property_id]

        # Sort by upload date (most recent first)
        docs.sort(key=lambda d: d.uploaded_at, reverse=True)

        return [
            {
                "document_id": d.document_id,
                "title": d.title,
                "type": d.document_type.value.replace("_", " ").title(),
                "filename": d.filename,
                "size": f"{d.file_size / 1024:.1f} KB",
                "uploaded": d.uploaded_at.strftime("%d/%m/%Y"),
                "is_read": d.is_read,
            }
            for d in docs
        ]

    def get_property_photos(self, property_id: str) -> List[Dict]:
        """Get photos for a property."""
        photos = [p for p in self.photos.values() if p.property_id == property_id]

        # Sort with primary photo first
        photos.sort(key=lambda p: (not p.is_primary, p.taken_date), reverse=True)

        return [
            {
                "photo_id": p.photo_id,
                "title": p.title,
                "description": p.description,
                "category": p.category,
                "taken": p.taken_date.strftime("%d/%m/%Y"),
                "is_primary": p.is_primary,
            }
            for p in photos
        ]

    def download_statement(self, payment_id: str) -> Optional[str]:
        """Generate and return a distribution statement."""
        payment = self.payments.get(payment_id)
        if not payment:
            return None

        investor = self.investors.get(payment.investor_id)
        if not investor:
            return None

        # Mark associated document as downloaded
        for doc in self.documents.values():
            if doc.document_type == DocumentType.DISTRIBUTION_STATEMENT:
                if payment_id in doc.title or payment_id in doc.description:
                    doc.download_count += 1

        return self.statement_generator.generate_distribution_statement(
            investor, payment
        )

    def download_tax_summary(self, summary_id: str) -> Optional[str]:
        """Generate and return a tax summary."""
        summary = self.tax_summaries.get(summary_id)
        if not summary:
            return None

        investor = self.investors.get(summary.investor_id)
        if not investor:
            return None

        return self.statement_generator.generate_tax_summary(investor, summary)

    def calculate_portfolio_metrics(
        self,
        investor_id: str,
        period: PortfolioSummaryPeriod = PortfolioSummaryPeriod.YEAR,
    ) -> Optional[PortfolioMetrics]:
        """Calculate portfolio metrics for an investor."""
        investor = self.investors.get(investor_id)
        if not investor:
            return None

        investments = [
            inv
            for inv in self.investments.values()
            if inv.investor_id == investor_id and inv.is_active
        ]

        if not investments:
            return None

        # Calculate period date range
        today = date.today()
        if period == PortfolioSummaryPeriod.MONTH:
            start_date = today.replace(day=1)
        elif period == PortfolioSummaryPeriod.QUARTER:
            quarter_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=quarter_month, day=1)
        elif period == PortfolioSummaryPeriod.YEAR:
            start_date = today.replace(month=1, day=1)
        elif period == PortfolioSummaryPeriod.FINANCIAL_YEAR:
            if today.month >= 7:
                start_date = today.replace(month=7, day=1)
            else:
                start_date = today.replace(year=today.year - 1, month=7, day=1)
        else:
            start_date = date(2000, 1, 1)  # All time

        # Get payments in period
        period_payments = [
            p
            for p in self.payments.values()
            if p.investor_id == investor_id
            and p.status == PaymentStatus.COMPLETED
            and p.period_end >= start_date
        ]

        all_payments = [
            p
            for p in self.payments.values()
            if p.investor_id == investor_id and p.status == PaymentStatus.COMPLETED
        ]

        total_invested = sum(inv.investment_amount for inv in investments)
        current_value = sum(inv.current_value for inv in investments)
        total_distributions = sum(p.distribution_amount for p in all_payments)
        period_distributions = sum(p.distribution_amount for p in period_payments)

        capital_growth = current_value - total_invested
        average_yield = (
            (period_distributions / total_invested * 100)
            if total_invested > 0
            else Decimal("0")
        )
        total_return = (
            ((capital_growth + total_distributions) / total_invested * 100)
            if total_invested > 0
            else Decimal("0")
        )

        return PortfolioMetrics(
            total_invested=total_invested,
            current_value=current_value,
            total_distributions_received=total_distributions,
            average_yield=average_yield,
            capital_growth=capital_growth,
            total_return=total_return,
            property_count=len(investments),
            period=period,
            period_distributions=period_distributions,
        )

    def generate_portfolio_report(self, investor_id: str) -> Optional[str]:
        """Generate complete portfolio report."""
        investor = self.investors.get(investor_id)
        if not investor:
            return None

        investments = [
            inv
            for inv in self.investments.values()
            if inv.investor_id == investor_id and inv.is_active
        ]

        metrics = self.calculate_portfolio_metrics(
            investor_id, PortfolioSummaryPeriod.YEAR
        )
        if not metrics:
            return None

        return self.statement_generator.generate_portfolio_report(
            investor, investments, metrics
        )

    def mark_document_read(self, document_id: str, investor_id: str) -> bool:
        """Mark a document as read."""
        doc = self.documents.get(document_id)
        if not doc or doc.investor_id != investor_id:
            return False

        doc.is_read = True
        return True

    def get_unread_documents_count(self, investor_id: str) -> int:
        """Get count of unread documents."""
        return len(
            [
                d
                for d in self.documents.values()
                if d.investor_id == investor_id and not d.is_read
            ]
        )

    def get_portal_dashboard(self, investor_id: str) -> Dict[str, Any]:
        """Get complete portal dashboard for an investor."""
        investor = self.investors.get(investor_id)
        if not investor:
            return {"error": "Investor not found"}

        portfolio = self.get_investor_portfolio(investor_id)
        recent_payments = self.get_payment_history(investor_id, limit=5)
        unread_docs = self.get_unread_documents_count(investor_id)
        metrics = self.calculate_portfolio_metrics(investor_id)

        # Get pending payments
        pending_payments = [
            p
            for p in self.payments.values()
            if p.investor_id == investor_id and p.status == PaymentStatus.PENDING
        ]
        pending_total = sum(p.distribution_amount for p in pending_payments)

        return {
            "investor": {
                "name": investor.name,
                "last_login": (
                    investor.last_login.strftime("%d/%m/%Y %H:%M")
                    if investor.last_login
                    else "First visit"
                ),
            },
            "portfolio_summary": portfolio.get("portfolio", {}),
            "quick_stats": {
                "properties_owned": len(portfolio.get("properties", [])),
                "pending_distributions": (
                    f"${pending_total:,.2f}" if pending_total > 0 else "None"
                ),
                "unread_documents": unread_docs,
                "ytd_distributions": (
                    f"${metrics.period_distributions:,.2f}" if metrics else "$0.00"
                ),
            },
            "recent_payments": recent_payments,
            "performance": {
                "capital_growth": (
                    f"{((metrics.capital_growth / metrics.total_invested) * 100):.1f}%"
                    if metrics and metrics.total_invested > 0
                    else "N/A"
                ),
                "average_yield": f"{metrics.average_yield:.1f}%" if metrics else "N/A",
                "total_return": f"{metrics.total_return:.1f}%" if metrics else "N/A",
            },
        }


# ============================================================================
# DEMO DATA GENERATOR
# ============================================================================


def generate_demo_data() -> InvestorPortal:
    """Generate demo data for testing."""
    portal = InvestorPortal("Accessible Homes Property Co")

    # Create demo investors
    investors = [
        Investor(
            investor_id="INV-001",
            name="Investment Group Alpha",
            email="alpha@example.com",
            phone="0400 123 456",
            address="Suite 1, 100 Business Park, Sydney NSW 2000",
            tax_file_number="123456789",
        ),
        Investor(
            investor_id="INV-002",
            name="Jane Smith Family Trust",
            email="jane.smith@example.com",
            phone="0412 345 678",
            address="45 Residential Street, Melbourne VIC 3000",
            tax_file_number="987654321",
        ),
        Investor(
            investor_id="INV-003",
            name="Omega Property Group Pty Ltd",
            email="investors@omega.example.com",
            phone="02 9876 5432",
            address="Level 20, Corporate Tower, Brisbane QLD 4000",
            tax_file_number="456789123",
        ),
    ]

    for inv in investors:
        portal.register_investor(inv)

    # Create investments
    investments = [
        PropertyInvestment(
            investment_id="INVEST-001",
            investor_id="INV-001",
            property_id="PROP-001",
            property_address="Unit 1, 42 Example Street",
            property_suburb="Sampletown SA",
            sda_category="high_physical_support",
            ownership_percent=Decimal("25.0"),
            investment_date=date(2023, 6, 15),
            investment_amount=Decimal("175000"),
            current_value=Decimal("192500"),
        ),
        PropertyInvestment(
            investment_id="INVEST-002",
            investor_id="INV-001",
            property_id="PROP-002",
            property_address="3/88 Demo Road",
            property_suburb="Testville SA",
            sda_category="fully_accessible",
            ownership_percent=Decimal("50.0"),
            investment_date=date(2024, 1, 10),
            investment_amount=Decimal("320000"),
            current_value=Decimal("335000"),
        ),
        PropertyInvestment(
            investment_id="INVEST-003",
            investor_id="INV-002",
            property_id="PROP-003",
            property_address="15 Showcase Avenue",
            property_suburb="Exampleville VIC",
            sda_category="robust",
            ownership_percent=Decimal("100.0"),
            investment_date=date(2022, 3, 1),
            investment_amount=Decimal("680000"),
            current_value=Decimal("752000"),
        ),
        PropertyInvestment(
            investment_id="INVEST-004",
            investor_id="INV-003",
            property_id="PROP-001",
            property_address="Unit 1, 42 Example Street",
            property_suburb="Sampletown SA",
            sda_category="high_physical_support",
            ownership_percent=Decimal("25.0"),
            investment_date=date(2023, 6, 15),
            investment_amount=Decimal("175000"),
            current_value=Decimal("192500"),
        ),
    ]

    for inv in investments:
        portal.add_investment(inv)

    # Create payment history
    payments = [
        DistributionPayment(
            payment_id="PAY-2025-03-001",
            investor_id="INV-001",
            property_id="PROP-001",
            property_address="Unit 1, 42 Example Street",
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
            gross_income=Decimal("4850.00"),
            management_fee=Decimal("412.25"),
            expenses=Decimal("125.00"),
            net_income=Decimal("4312.75"),
            ownership_percent=Decimal("25.0"),
            distribution_amount=Decimal("1078.19"),
            status=PaymentStatus.COMPLETED,
            payment_date=date(2025, 3, 5),
            payment_reference="ABA-20250305-001",
            bank_bsb="062-123",
            bank_account="12345678",
        ),
        DistributionPayment(
            payment_id="PAY-2025-03-002",
            investor_id="INV-001",
            property_id="PROP-002",
            property_address="3/88 Demo Road",
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
            gross_income=Decimal("4420.00"),
            management_fee=Decimal("353.60"),
            expenses=Decimal("200.00"),
            net_income=Decimal("3866.40"),
            ownership_percent=Decimal("50.0"),
            distribution_amount=Decimal("1933.20"),
            status=PaymentStatus.COMPLETED,
            payment_date=date(2025, 3, 5),
            payment_reference="ABA-20250305-002",
            bank_bsb="062-123",
            bank_account="12345678",
        ),
        DistributionPayment(
            payment_id="PAY-2025-04-001",
            investor_id="INV-001",
            property_id="PROP-001",
            property_address="Unit 1, 42 Example Street",
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            gross_income=Decimal("4950.00"),
            management_fee=Decimal("420.75"),
            expenses=Decimal("0.00"),
            net_income=Decimal("4529.25"),
            ownership_percent=Decimal("25.0"),
            distribution_amount=Decimal("1132.31"),
            status=PaymentStatus.PENDING,
            bank_bsb="062-123",
            bank_account="12345678",
        ),
    ]

    for pay in payments:
        portal.record_payment(pay)

    # Create documents
    documents = [
        Document(
            document_id="DOC-001",
            investor_id="INV-001",
            property_id="PROP-001",
            document_type=DocumentType.DISTRIBUTION_STATEMENT,
            title="Distribution Statement - February 2025",
            description="Monthly distribution statement for February 2025",
            filename="statement_feb2025_prop001.pdf",
            file_size=125000,
            mime_type="application/pdf",
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
            is_read=True,
        ),
        Document(
            document_id="DOC-002",
            investor_id="INV-001",
            property_id=None,
            document_type=DocumentType.TAX_SUMMARY,
            title="Tax Summary FY 2023-24",
            description="Annual tax summary for financial year 2023-24",
            filename="tax_summary_fy2324.pdf",
            file_size=245000,
            mime_type="application/pdf",
            period_start=date(2023, 7, 1),
            period_end=date(2024, 6, 30),
            is_read=False,
        ),
        Document(
            document_id="DOC-003",
            investor_id="INV-001",
            property_id="PROP-001",
            document_type=DocumentType.CONDITION_REPORT,
            title="Annual Property Inspection 2025",
            description="Annual condition report with photos",
            filename="inspection_prop001_2025.pdf",
            file_size=2450000,
            mime_type="application/pdf",
            is_read=False,
        ),
    ]

    for doc in documents:
        portal.upload_document(doc)

    # Create tax summary
    tax_summary = TaxSummary(
        summary_id="TAX-2024",
        investor_id="INV-001",
        financial_year="2023-24",
        total_distributions=Decimal("24500.00"),
        total_deductions=Decimal("2100.00"),
        depreciation_amount=Decimal("8500.00"),
        capital_works_deduction=Decimal("3200.00"),
        net_rental_income=Decimal("10700.00"),
        franking_credits=Decimal("0"),
        properties=[
            {
                "address": "Unit 1, 42 Example Street",
                "ownership_percent": 25.0,
                "gross_income": 14500.00,
                "net_income": 6200.00,
                "depreciation": 5100.00,
            },
            {
                "address": "3/88 Demo Road",
                "ownership_percent": 50.0,
                "gross_income": 23000.00,
                "net_income": 11500.00,
                "depreciation": 3400.00,
            },
        ],
    )
    portal.record_tax_summary(tax_summary)

    return portal


# ============================================================================
# DEMO RUNNER
# ============================================================================


def run_demo():
    """Run comprehensive portal demo."""
    print("=" * 80)
    print("     SDA INVESTOR PORTAL - SELF-SERVICE PORTAL")
    print("     Investor Transparency & Self-Service")
    print("=" * 80)
    print()

    # Initialize with demo data
    print("📊 Initializing portal with demo data...")
    portal = generate_demo_data()
    print(f"   ✓ Company: {portal.company_name}")
    print(f"   ✓ Investors: {len(portal.investors)}")
    print(f"   ✓ Investments: {len(portal.investments)}")
    print(f"   ✓ Payments: {len(portal.payments)}")
    print(f"   ✓ Documents: {len(portal.documents)}")
    print()

    # Demo for Investor INV-001
    investor_id = "INV-001"
    investor = portal.investors[investor_id]

    print(f"🔐 LOGGED IN AS: {investor.name}")
    print("-" * 80)
    print()

    # Show dashboard
    print("📊 PORTAL DASHBOARD")
    print("-" * 80)
    dashboard = portal.get_portal_dashboard(investor_id)
    print(json.dumps(dashboard, indent=2))
    print()

    # Show portfolio
    print("🏠 PROPERTY PORTFOLIO")
    print("-" * 80)
    portfolio = portal.get_investor_portfolio(investor_id)
    for prop in portfolio.get("properties", []):
        print(f"   📍 {prop['address']}")
        print(f"      Category: {prop['category']}")
        print(f"      Ownership: {prop['ownership']}")
        print(f"      Invested: {prop['invested']} → Current: {prop['current_value']}")
        print(f"      Capital Gain: {prop['gain']}")
        print()

    # Show payment history
    print("💰 RECENT PAYMENTS")
    print("-" * 80)
    payments = portal.get_payment_history(investor_id)
    for pay in payments:
        status_icon = "✅" if pay["status"] == "completed" else "⏳"
        print(f"   {status_icon} {pay['property']}")
        print(f"      Period: {pay['period']} | Amount: {pay['amount']}")
        print(f"      Status: {pay['status']} | Date: {pay['payment_date']}")
        print()

    # Show documents
    print("📁 DOCUMENT VAULT")
    print("-" * 80)
    docs = portal.get_documents(investor_id)
    for doc in docs:
        read_icon = "📖" if doc["is_read"] else "📬"
        print(f"   {read_icon} {doc['title']}")
        print(f"      Type: {doc['type']} | Size: {doc['size']}")
        print(f"      Uploaded: {doc['uploaded']}")
        print()

    # Generate statement
    print("📄 DISTRIBUTION STATEMENT (Sample)")
    print("-" * 80)
    statement = portal.download_statement("PAY-2025-03-001")
    if statement:
        # Show first part of statement
        print(statement[:2000])
        print("... (statement continues)")
    print()

    # Generate portfolio report
    print("📈 PORTFOLIO PERFORMANCE REPORT")
    print("-" * 80)
    report = portal.generate_portfolio_report(investor_id)
    if report:
        print(report[:3000])
        print("... (report continues)")
    print()

    # Show metrics
    print("📊 PORTFOLIO METRICS")
    print("-" * 80)
    metrics = portal.calculate_portfolio_metrics(investor_id)
    if metrics:
        print(f"   Total Invested:         ${metrics.total_invested:,.2f}")
        print(f"   Current Value:          ${metrics.current_value:,.2f}")
        print(f"   Capital Growth:         ${metrics.capital_growth:,.2f}")
        print(
            f"   Total Distributions:    ${metrics.total_distributions_received:,.2f}"
        )
        print(f"   Average Yield:          {metrics.average_yield:.2f}%")
        print(f"   Total Return:           {metrics.total_return:.2f}%")
    print()

    print("=" * 80)
    print("                    DEMO COMPLETE")
    print("=" * 80)
    print()
    print("The investor portal reduces 'where's my money?' calls by providing:")
    print("  ✅ Real-time portfolio visibility")
    print("  ✅ Self-service statement downloads")
    print("  ✅ Payment tracking and history")
    print("  ✅ Tax summary preparation")
    print("  ✅ Property photos and reports")
    print()

    return portal


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SDA Investor Portal - Self-Service Portal"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Run demo mode with sample data"
    )
    parser.add_argument("--portfolio", type=str, help="Show portfolio for investor ID")

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.portfolio:
        portal = generate_demo_data()
        portfolio = portal.get_investor_portfolio(args.portfolio)
        print(json.dumps(portfolio, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
