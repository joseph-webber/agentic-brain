#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
SDA Financial Manager - Property Financial Engine & Reconciliation
==================================================================

Enterprise-grade financial management system for SDA (Specialist Disability
Accommodation) property providers. Handles multi-source income, syndicate
ownership, Australian banking (ABA files), and bank reconciliation.

FEATURES:
- Multi-source income: RRC (Reasonable Rent Contribution) + NDIS SDA Funding
- Syndicate/multi-investor properties with automatic distribution
- ABA file generation for bulk payments (CommBank/Westpac/NAB/ANZ)
- Bank reconciliation with auto-matching
- Split payment handling (tenant + NDIS portions)
- Management fee calculations
- Investor statement generation

Author: Agentic Brain Framework
License: MIT
"""

import csv
import hashlib
import io
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class PaymentSource(Enum):
    """Sources of income for SDA properties."""

    RRC = "rrc"  # Reasonable Rent Contribution (tenant pays)
    NDIS_SDA = "ndis_sda"  # NDIS SDA Funding payment
    BOND = "bond"  # Bond/deposit
    MAINTENANCE_CONTRIBUTION = "maintenance"
    OTHER = "other"


class TransactionType(Enum):
    """Bank transaction types."""

    CREDIT = "credit"
    DEBIT = "debit"


class ReconciliationStatus(Enum):
    """Status of bank transaction reconciliation."""

    MATCHED = "matched"
    UNMATCHED = "unmatched"
    PARTIAL = "partial"
    EXCEPTION = "exception"
    MANUAL_REVIEW = "manual_review"


class DistributionStatus(Enum):
    """Status of investor distributions."""

    PENDING = "pending"
    CALCULATED = "calculated"
    APPROVED = "approved"
    PAID = "paid"
    FAILED = "failed"


class ABARecordType(Enum):
    """ABA file record types."""

    DESCRIPTIVE = "0"
    DETAIL = "1"
    TOTAL = "7"


# SDA Design Categories and their NDIS pricing tiers
SDA_DESIGN_CATEGORIES = {
    "basic": {"name": "Basic", "price_modifier": 1.0},
    "improved_liveability": {"name": "Improved Liveability", "price_modifier": 1.25},
    "fully_accessible": {"name": "Fully Accessible", "price_modifier": 1.5},
    "robust": {"name": "Robust", "price_modifier": 1.4},
    "high_physical_support": {"name": "High Physical Support", "price_modifier": 1.8},
}

# Australian bank BSB prefixes
BANK_BSB_PREFIXES = {
    "06": "Commonwealth Bank",
    "08": "NAB",
    "03": "Westpac",
    "01": "ANZ",
    "12": "Bendigo Bank",
    "08": "NAB",
    "48": "Macquarie",
}


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class Property:
    """SDA Property with ownership and financial details."""

    property_id: str
    address: str
    suburb: str
    state: str
    postcode: str
    sda_category: str  # basic, improved_liveability, fully_accessible, robust, high_physical_support
    num_bedrooms: int
    weekly_sda_rate: Decimal
    weekly_rrc_rate: Decimal
    management_fee_percent: Decimal  # e.g., 8.5%
    is_active: bool = True
    registration_number: str = ""

    def __post_init__(self):
        self.weekly_sda_rate = Decimal(str(self.weekly_sda_rate))
        self.weekly_rrc_rate = Decimal(str(self.weekly_rrc_rate))
        self.management_fee_percent = Decimal(str(self.management_fee_percent))


@dataclass
class PropertyOwner:
    """Investor/owner with ownership stake in a property."""

    owner_id: str
    property_id: str
    name: str
    email: str
    phone: str
    ownership_percent: Decimal
    bsb: str
    account_number: str
    account_name: str
    is_active: bool = True

    def __post_init__(self):
        self.ownership_percent = Decimal(str(self.ownership_percent))


@dataclass
class Tenant:
    """SDA Tenant (NDIS participant)."""

    tenant_id: str
    property_id: str
    name: str
    ndis_number: str
    move_in_date: date
    move_out_date: Optional[date] = None
    rrc_amount: Decimal = Decimal("0")
    sda_funding_amount: Decimal = Decimal("0")
    is_active: bool = True

    def __post_init__(self):
        self.rrc_amount = Decimal(str(self.rrc_amount))
        self.sda_funding_amount = Decimal(str(self.sda_funding_amount))


@dataclass
class Invoice:
    """Invoice for rent collection (RRC + SDA)."""

    invoice_id: str
    property_id: str
    tenant_id: str
    invoice_date: date
    due_date: date
    period_start: date
    period_end: date
    rrc_amount: Decimal
    sda_amount: Decimal
    total_amount: Decimal
    rrc_paid: Decimal = Decimal("0")
    sda_paid: Decimal = Decimal("0")
    is_paid: bool = False
    paid_date: Optional[date] = None

    def __post_init__(self):
        self.rrc_amount = Decimal(str(self.rrc_amount))
        self.sda_amount = Decimal(str(self.sda_amount))
        self.total_amount = Decimal(str(self.total_amount))
        self.rrc_paid = Decimal(str(self.rrc_paid))
        self.sda_paid = Decimal(str(self.sda_paid))

    @property
    def outstanding(self) -> Decimal:
        return self.total_amount - self.rrc_paid - self.sda_paid


@dataclass
class BankTransaction:
    """Bank transaction from imported CSV."""

    transaction_id: str
    date: date
    description: str
    amount: Decimal
    transaction_type: TransactionType
    balance: Decimal
    reference: str = ""
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.UNMATCHED
    matched_invoice_id: Optional[str] = None
    matched_source: Optional[PaymentSource] = None
    notes: str = ""

    def __post_init__(self):
        self.amount = Decimal(str(self.amount))
        self.balance = Decimal(str(self.balance))


@dataclass
class Distribution:
    """Distribution payment to property owner/investor."""

    distribution_id: str
    property_id: str
    owner_id: str
    period_start: date
    period_end: date
    gross_income: Decimal
    management_fee: Decimal
    expenses: Decimal
    net_income: Decimal
    ownership_percent: Decimal
    distribution_amount: Decimal
    status: DistributionStatus = DistributionStatus.PENDING
    payment_date: Optional[date] = None
    aba_batch_id: Optional[str] = None

    def __post_init__(self):
        self.gross_income = Decimal(str(self.gross_income))
        self.management_fee = Decimal(str(self.management_fee))
        self.expenses = Decimal(str(self.expenses))
        self.net_income = Decimal(str(self.net_income))
        self.ownership_percent = Decimal(str(self.ownership_percent))
        self.distribution_amount = Decimal(str(self.distribution_amount))


@dataclass
class ABABatch:
    """ABA file batch for bulk payments."""

    batch_id: str
    created_date: datetime
    bank_code: str  # BSB prefix
    bank_name: str
    description: str
    total_amount: Decimal
    transaction_count: int
    file_content: str = ""
    is_processed: bool = False
    processed_date: Optional[datetime] = None

    def __post_init__(self):
        self.total_amount = Decimal(str(self.total_amount))


# ============================================================================
# ABA FILE GENERATOR
# ============================================================================


class ABAFileGenerator:
    """
    Generate ABA (Australian Bankers Association) files for bulk payments.

    ABA files are the Australian standard for electronic funds transfer.
    Supported by CommBank, Westpac, NAB, ANZ, and most Australian banks.
    """

    def __init__(
        self,
        bank_code: str,
        user_name: str,
        user_id: str,
        description: str,
        bsb: str,
        account_number: str,
        account_name: str,
    ):
        self.bank_code = bank_code  # 3 chars, e.g., "CBA", "WBC"
        self.user_name = user_name[:26]  # Max 26 chars
        self.user_id = user_id[:6].zfill(6)  # 6 digits
        self.description = description[:12]  # Max 12 chars
        self.bsb = bsb.replace("-", "")[:7]  # 7 chars with hyphen
        self.account_number = account_number[:9].rjust(9)  # 9 chars right-aligned
        self.account_name = account_name[:32]  # Max 32 chars

        self.transactions: List[Dict] = []
        self.total_credit = Decimal("0")
        self.total_debit = Decimal("0")

    def add_payment(
        self,
        bsb: str,
        account_number: str,
        account_name: str,
        amount: Decimal,
        reference: str,
        is_credit: bool = True,
    ):
        """Add a payment transaction to the batch."""
        # Validate BSB format (6 digits with optional hyphen)
        clean_bsb = bsb.replace("-", "")
        if len(clean_bsb) != 6 or not clean_bsb.isdigit():
            raise ValueError(f"Invalid BSB format: {bsb}")

        # Format BSB with hyphen for ABA
        formatted_bsb = f"{clean_bsb[:3]}-{clean_bsb[3:]}"

        # Validate account number
        clean_account = account_number.replace(" ", "")
        if not clean_account.isdigit() or len(clean_account) > 9:
            raise ValueError(f"Invalid account number: {account_number}")

        # Amount in cents
        amount_cents = int(amount * 100)

        transaction = {
            "bsb": formatted_bsb,
            "account_number": clean_account.rjust(9),
            "indicator": " ",  # Space for credit, N for new account
            "transaction_code": "53" if is_credit else "13",  # 53=credit, 13=debit
            "amount": amount_cents,
            "account_name": account_name[:32].ljust(32),
            "reference": reference[:18].ljust(18),
        }

        self.transactions.append(transaction)

        if is_credit:
            self.total_credit += amount
        else:
            self.total_debit += amount

    def generate(self) -> str:
        """Generate the ABA file content."""
        lines = []

        # Descriptive record (Type 0)
        today = datetime.now()
        lines.append(self._generate_header(today))

        # Detail records (Type 1)
        for txn in self.transactions:
            lines.append(self._generate_detail(txn))

        # Total record (Type 7)
        lines.append(self._generate_footer())

        return "\r\n".join(lines)

    def _generate_header(self, date: datetime) -> str:
        """Generate Type 0 descriptive record."""
        return "".join(
            [
                "0",  # Record type
                " " * 17,  # Blank
                "01",  # Reel sequence number
                self.bank_code.ljust(3),  # Bank code
                " " * 7,  # Blank
                self.user_name.ljust(26),  # User name
                self.user_id.zfill(6),  # User ID
                self.description.ljust(12),  # Description
                date.strftime("%d%m%y"),  # Date
                " " * 40,  # Blank (to fill to 120 chars)
            ]
        )

    def _generate_detail(self, txn: Dict) -> str:
        """Generate Type 1 detail record."""
        return "".join(
            [
                "1",  # Record type
                txn["bsb"],  # BSB (7 chars with hyphen)
                txn["account_number"],  # Account number (9 chars)
                txn["indicator"],  # Indicator (1 char)
                txn["transaction_code"],  # Transaction code (2 chars)
                str(txn["amount"]).zfill(10),  # Amount in cents (10 chars)
                txn["account_name"],  # Account name (32 chars)
                txn["reference"],  # Lodgement reference (18 chars)
                self.bsb,  # Trace BSB (7 chars)
                self.account_number,  # Trace account (9 chars)
                self.account_name[:16].ljust(16),  # Remitter name (16 chars)
                "00000000",  # Withholding tax (8 chars)
            ]
        )

    def _generate_footer(self) -> str:
        """Generate Type 7 file total record."""
        net_total = self.total_credit - self.total_debit
        total_credit_cents = int(self.total_credit * 100)
        total_debit_cents = int(self.total_debit * 100)
        net_total_cents = abs(int(net_total * 100))

        return "".join(
            [
                "7",  # Record type
                "999-999",  # BSB format filler
                " " * 12,  # Blank
                str(net_total_cents).zfill(10),  # Net total
                str(total_credit_cents).zfill(10),  # Total credits
                str(total_debit_cents).zfill(10),  # Total debits
                " " * 24,  # Blank
                str(len(self.transactions)).zfill(6),  # Transaction count
                " " * 40,  # Blank (to fill to 120 chars)
            ]
        )


# ============================================================================
# BANK RECONCILIATION ENGINE
# ============================================================================


class BankReconciliationEngine:
    """
    Bank reconciliation engine with auto-matching capabilities.

    Features:
    - Auto-match by reference number
    - Auto-match by amount + date proximity
    - NDIS payment identification
    - Exception flagging for manual review
    """

    def __init__(self):
        self.transactions: List[BankTransaction] = []
        self.invoices: List[Invoice] = []
        self.match_rules: List[Dict] = []

        # Default matching rules
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default matching rules."""
        self.match_rules = [
            {
                "name": "ndis_payment",
                "pattern": r"(NDIS|NDIA|PLAN MGR)",
                "source": PaymentSource.NDIS_SDA,
                "priority": 1,
            },
            {
                "name": "rrc_payment",
                "pattern": r"(RRC|RENT|TENANT)",
                "source": PaymentSource.RRC,
                "priority": 2,
            },
            {
                "name": "bond_payment",
                "pattern": r"(BOND|DEPOSIT)",
                "source": PaymentSource.BOND,
                "priority": 3,
            },
        ]

    def import_bank_csv(
        self, csv_content: str, date_format: str = "%d/%m/%Y"
    ) -> List[BankTransaction]:
        """
        Import bank transactions from CSV.

        Expected columns: Date, Description, Debit, Credit, Balance
        """
        transactions = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for idx, row in enumerate(reader):
            # Parse date
            try:
                txn_date = datetime.strptime(row.get("Date", ""), date_format).date()
            except ValueError:
                logger.warning(f"Invalid date in row {idx}: {row.get('Date')}")
                continue

            # Parse amounts
            debit = Decimal(
                row.get("Debit", "0").replace(",", "").replace("$", "") or "0"
            )
            credit = Decimal(
                row.get("Credit", "0").replace(",", "").replace("$", "") or "0"
            )
            balance = Decimal(
                row.get("Balance", "0").replace(",", "").replace("$", "") or "0"
            )

            # Determine transaction type and amount
            if credit > 0:
                amount = credit
                txn_type = TransactionType.CREDIT
            else:
                amount = debit
                txn_type = TransactionType.DEBIT

            # Generate transaction ID
            txn_id = hashlib.md5(
                f"{txn_date}{row.get('Description', '')}{amount}".encode()
            ).hexdigest()[:12]

            transaction = BankTransaction(
                transaction_id=f"TXN-{txn_id}",
                date=txn_date,
                description=row.get("Description", ""),
                amount=amount,
                transaction_type=txn_type,
                balance=balance,
                reference=row.get("Reference", ""),
            )

            transactions.append(transaction)

        self.transactions.extend(transactions)
        return transactions

    def auto_match(self, invoices: List[Invoice]) -> Dict[str, Any]:
        """
        Auto-match bank transactions to invoices.

        Returns:
            Dict with matched, unmatched, and exception counts
        """
        self.invoices = invoices
        results = {
            "matched": 0,
            "unmatched": 0,
            "partial": 0,
            "exceptions": 0,
            "details": [],
        }

        # Only process credit transactions (income)
        credit_txns = [
            t for t in self.transactions if t.transaction_type == TransactionType.CREDIT
        ]

        for txn in credit_txns:
            match_result = self._match_transaction(txn)

            if match_result["status"] == ReconciliationStatus.MATCHED:
                results["matched"] += 1
            elif match_result["status"] == ReconciliationStatus.PARTIAL:
                results["partial"] += 1
            elif match_result["status"] == ReconciliationStatus.EXCEPTION:
                results["exceptions"] += 1
            else:
                results["unmatched"] += 1

            results["details"].append(match_result)

        return results

    def _match_transaction(self, txn: BankTransaction) -> Dict[str, Any]:
        """Match a single transaction to an invoice."""
        import re

        # Step 1: Identify payment source from description
        source = None
        for rule in sorted(self.match_rules, key=lambda r: r["priority"]):
            if re.search(rule["pattern"], txn.description, re.IGNORECASE):
                source = rule["source"]
                break

        # Step 2: Try to match by reference number
        for invoice in self.invoices:
            if not invoice.is_paid and invoice.invoice_id in txn.description:
                return self._apply_match(txn, invoice, source)

        # Step 3: Try to match by amount (exact match)
        for invoice in self.invoices:
            if invoice.is_paid:
                continue

            # Check for exact total match
            if txn.amount == invoice.outstanding:
                return self._apply_match(txn, invoice, source)

            # Check for RRC portion match
            if (
                source == PaymentSource.RRC
                and txn.amount == invoice.rrc_amount - invoice.rrc_paid
            ):
                return self._apply_match(txn, invoice, source, is_partial=True)

            # Check for SDA portion match
            if (
                source == PaymentSource.NDIS_SDA
                and txn.amount == invoice.sda_amount - invoice.sda_paid
            ):
                return self._apply_match(txn, invoice, source, is_partial=True)

        # Step 4: Flag as unmatched
        txn.reconciliation_status = ReconciliationStatus.UNMATCHED
        return {
            "transaction_id": txn.transaction_id,
            "status": ReconciliationStatus.UNMATCHED,
            "amount": txn.amount,
            "description": txn.description,
            "suggested_source": source,
            "message": "No matching invoice found",
        }

    def _apply_match(
        self,
        txn: BankTransaction,
        invoice: Invoice,
        source: Optional[PaymentSource],
        is_partial: bool = False,
    ) -> Dict[str, Any]:
        """Apply a match between transaction and invoice."""
        txn.matched_invoice_id = invoice.invoice_id
        txn.matched_source = source

        if source == PaymentSource.RRC:
            invoice.rrc_paid += txn.amount
        elif source == PaymentSource.NDIS_SDA:
            invoice.sda_paid += txn.amount
        else:
            # Split proportionally if source unknown
            total_outstanding = invoice.outstanding
            if total_outstanding > 0:
                rrc_ratio = (invoice.rrc_amount - invoice.rrc_paid) / total_outstanding
                invoice.rrc_paid += txn.amount * rrc_ratio
                invoice.sda_paid += txn.amount * (1 - rrc_ratio)

        # Check if fully paid
        if invoice.outstanding <= Decimal("0.01"):
            invoice.is_paid = True
            invoice.paid_date = txn.date
            txn.reconciliation_status = ReconciliationStatus.MATCHED
        else:
            txn.reconciliation_status = ReconciliationStatus.PARTIAL

        return {
            "transaction_id": txn.transaction_id,
            "invoice_id": invoice.invoice_id,
            "status": txn.reconciliation_status,
            "amount": txn.amount,
            "source": source.value if source else "unknown",
            "remaining": invoice.outstanding,
            "message": "Matched" if not is_partial else "Partial payment applied",
        }

    def get_exceptions(self) -> List[BankTransaction]:
        """Get transactions requiring manual review."""
        return [
            t
            for t in self.transactions
            if t.reconciliation_status
            in [
                ReconciliationStatus.UNMATCHED,
                ReconciliationStatus.EXCEPTION,
                ReconciliationStatus.MANUAL_REVIEW,
            ]
        ]


# ============================================================================
# DISTRIBUTION CALCULATOR
# ============================================================================


class DistributionCalculator:
    """
    Calculate distributions for property owners/investors.

    Handles:
    - Multi-owner properties (syndicates)
    - Management fee deduction
    - Expense allocation
    - Ownership percentage distribution
    """

    def __init__(self):
        self.distributions: List[Distribution] = []

    def calculate_distributions(
        self,
        property: Property,
        owners: List[PropertyOwner],
        invoices: List[Invoice],
        expenses: List[Dict],
        period_start: date,
        period_end: date,
    ) -> List[Distribution]:
        """
        Calculate distributions for all owners of a property.

        Args:
            property: The property
            owners: List of property owners
            invoices: Paid invoices for the period
            expenses: Property expenses for the period
            period_start: Distribution period start
            period_end: Distribution period end

        Returns:
            List of Distribution objects
        """
        distributions = []

        # Calculate gross income from paid invoices
        gross_income = sum(
            inv.rrc_paid + inv.sda_paid
            for inv in invoices
            if inv.is_paid
            and inv.period_start >= period_start
            and inv.period_end <= period_end
        )

        # Calculate total expenses
        total_expenses = sum(Decimal(str(exp.get("amount", 0))) for exp in expenses)

        # Calculate management fee
        management_fee = (
            gross_income * property.management_fee_percent / 100
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Calculate net income
        net_income = gross_income - management_fee - total_expenses

        # Distribute to each owner
        for owner in owners:
            if not owner.is_active:
                continue

            # Calculate owner's share
            share = (net_income * owner.ownership_percent / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            distribution = Distribution(
                distribution_id=f"DIST-{property.property_id}-{owner.owner_id}-{period_end.strftime('%Y%m')}",
                property_id=property.property_id,
                owner_id=owner.owner_id,
                period_start=period_start,
                period_end=period_end,
                gross_income=gross_income,
                management_fee=management_fee,
                expenses=total_expenses,
                net_income=net_income,
                ownership_percent=owner.ownership_percent,
                distribution_amount=share,
                status=DistributionStatus.CALCULATED,
            )

            distributions.append(distribution)

        self.distributions.extend(distributions)
        return distributions

    def generate_owner_statement(
        self, distribution: Distribution, owner: PropertyOwner, property: Property
    ) -> str:
        """Generate a text statement for an owner."""
        statement = f"""
================================================================================
                         INVESTOR DISTRIBUTION STATEMENT
================================================================================

Investor:       {owner.name}
Property:       {property.address}, {property.suburb} {property.state} {property.postcode}
Period:         {distribution.period_start} to {distribution.period_end}
Statement Date: {datetime.now().strftime('%d/%m/%Y')}

--------------------------------------------------------------------------------
                              INCOME SUMMARY
--------------------------------------------------------------------------------

Gross Rental Income:                          ${distribution.gross_income:>12,.2f}

Less: Management Fee ({property.management_fee_percent}%):        ${distribution.management_fee:>12,.2f}
Less: Property Expenses:                      ${distribution.expenses:>12,.2f}
                                              ----------------
Net Income:                                   ${distribution.net_income:>12,.2f}

--------------------------------------------------------------------------------
                            YOUR DISTRIBUTION
--------------------------------------------------------------------------------

Your Ownership:                               {distribution.ownership_percent:>12.2f}%

Your Distribution Amount:                     ${distribution.distribution_amount:>12,.2f}

--------------------------------------------------------------------------------
                            PAYMENT DETAILS
--------------------------------------------------------------------------------

Payment will be made to:
  BSB:          {owner.bsb}
  Account:      {owner.account_number}
  Name:         {owner.account_name}

Status:         {distribution.status.value.upper()}

================================================================================
        Thank you for your investment with Accessible Homes Property Co.
================================================================================
"""
        return statement


# ============================================================================
# SDA FINANCIAL MANAGER
# ============================================================================


class SDAFinancialManager:
    """
    Main SDA Financial Management system.

    Coordinates all financial operations:
    - Invoice management
    - Bank reconciliation
    - Distribution calculations
    - ABA file generation
    - Reporting
    """

    def __init__(self, company_name: str = "SDA Housing Provider Pty Ltd"):
        self.company_name = company_name

        # Data stores
        self.properties: Dict[str, Property] = {}
        self.owners: Dict[str, PropertyOwner] = {}
        self.tenants: Dict[str, Tenant] = {}
        self.invoices: Dict[str, Invoice] = {}
        self.transactions: Dict[str, BankTransaction] = {}
        self.distributions: Dict[str, Distribution] = {}
        self.aba_batches: Dict[str, ABABatch] = {}

        # Engines
        self.reconciliation_engine = BankReconciliationEngine()
        self.distribution_calculator = DistributionCalculator()

        # Company bank details for ABA
        self.company_bsb = "062-000"
        self.company_account = "12345678"
        self.company_account_name = "SDA Housing Provider"
        self.bank_code = "CBA"
        self.user_id = "123456"

    def add_property(self, property: Property):
        """Add a property to the system."""
        self.properties[property.property_id] = property
        logger.info(f"Added property: {property.property_id}")

    def add_owner(self, owner: PropertyOwner):
        """Add a property owner/investor."""
        self.owners[owner.owner_id] = owner
        logger.info(f"Added owner: {owner.owner_id} for property {owner.property_id}")

    def add_tenant(self, tenant: Tenant):
        """Add a tenant to a property."""
        self.tenants[tenant.tenant_id] = tenant
        logger.info(f"Added tenant: {tenant.tenant_id}")

    def generate_monthly_invoices(self, month: int, year: int) -> List[Invoice]:
        """Generate invoices for all active tenants for a month."""
        invoices = []
        period_start = date(year, month, 1)

        # Calculate period end (last day of month)
        if month == 12:
            period_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(year, month + 1, 1) - timedelta(days=1)

        for tenant in self.tenants.values():
            if not tenant.is_active:
                continue

            property = self.properties.get(tenant.property_id)
            if not property:
                continue

            # Calculate weeks in period
            days_in_period = (period_end - period_start).days + 1
            weeks = Decimal(str(days_in_period)) / Decimal("7")

            # Calculate amounts
            rrc_amount = (property.weekly_rrc_rate * weeks).quantize(Decimal("0.01"))
            sda_amount = (property.weekly_sda_rate * weeks).quantize(Decimal("0.01"))
            total_amount = rrc_amount + sda_amount

            invoice = Invoice(
                invoice_id=f"INV-{tenant.tenant_id[:4]}-{year}{month:02d}",
                property_id=tenant.property_id,
                tenant_id=tenant.tenant_id,
                invoice_date=period_start,
                due_date=period_start + timedelta(days=14),
                period_start=period_start,
                period_end=period_end,
                rrc_amount=rrc_amount,
                sda_amount=sda_amount,
                total_amount=total_amount,
            )

            self.invoices[invoice.invoice_id] = invoice
            invoices.append(invoice)

        logger.info(f"Generated {len(invoices)} invoices for {month}/{year}")
        return invoices

    def import_bank_statement(self, csv_content: str) -> Dict[str, Any]:
        """Import and reconcile bank statement."""
        # Import transactions
        transactions = self.reconciliation_engine.import_bank_csv(csv_content)

        for txn in transactions:
            self.transactions[txn.transaction_id] = txn

        # Run auto-matching
        unpaid_invoices = [inv for inv in self.invoices.values() if not inv.is_paid]
        results = self.reconciliation_engine.auto_match(unpaid_invoices)

        return results

    def calculate_period_distributions(
        self,
        period_start: date,
        period_end: date,
        expenses_by_property: Dict[str, List[Dict]],
    ) -> List[Distribution]:
        """Calculate distributions for all properties for a period."""
        all_distributions = []

        for property_id, property in self.properties.items():
            # Get owners for this property
            property_owners = [
                o
                for o in self.owners.values()
                if o.property_id == property_id and o.is_active
            ]

            if not property_owners:
                continue

            # Get paid invoices for this property
            property_invoices = [
                inv
                for inv in self.invoices.values()
                if inv.property_id == property_id and inv.is_paid
            ]

            # Get expenses
            expenses = expenses_by_property.get(property_id, [])

            # Calculate distributions
            distributions = self.distribution_calculator.calculate_distributions(
                property,
                property_owners,
                property_invoices,
                expenses,
                period_start,
                period_end,
            )

            for dist in distributions:
                self.distributions[dist.distribution_id] = dist

            all_distributions.extend(distributions)

        return all_distributions

    def generate_aba_payment_file(
        self, distribution_ids: List[str], description: str = "DISTRIBUTIONS"
    ) -> ABABatch:
        """Generate ABA file for distribution payments."""
        # Create ABA generator
        aba_gen = ABAFileGenerator(
            bank_code=self.bank_code,
            user_name=self.company_name[:26],
            user_id=self.user_id,
            description=description[:12],
            bsb=self.company_bsb,
            account_number=self.company_account,
            account_name=self.company_account_name,
        )

        total_amount = Decimal("0")

        for dist_id in distribution_ids:
            distribution = self.distributions.get(dist_id)
            if not distribution:
                continue

            owner = self.owners.get(distribution.owner_id)
            if not owner:
                continue

            # Add payment to ABA
            aba_gen.add_payment(
                bsb=owner.bsb,
                account_number=owner.account_number,
                account_name=owner.account_name,
                amount=distribution.distribution_amount,
                reference=f"DIST {distribution.period_end.strftime('%b%Y').upper()}",
                is_credit=True,
            )

            total_amount += distribution.distribution_amount

        # Generate file content
        file_content = aba_gen.generate()

        # Create batch record
        batch = ABABatch(
            batch_id=f"ABA-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            created_date=datetime.now(),
            bank_code=self.bank_code,
            bank_name=BANK_BSB_PREFIXES.get(self.company_bsb[:2], "Unknown Bank"),
            description=description,
            total_amount=total_amount,
            transaction_count=len(distribution_ids),
            file_content=file_content,
        )

        self.aba_batches[batch.batch_id] = batch

        # Mark distributions as approved
        for dist_id in distribution_ids:
            if dist_id in self.distributions:
                self.distributions[dist_id].status = DistributionStatus.APPROVED
                self.distributions[dist_id].aba_batch_id = batch.batch_id

        logger.info(
            f"Generated ABA batch {batch.batch_id} with {batch.transaction_count} payments"
        )
        return batch

    def get_reconciliation_summary(self) -> Dict[str, Any]:
        """Get summary of reconciliation status."""
        transactions = list(self.transactions.values())

        return {
            "total_transactions": len(transactions),
            "matched": len(
                [
                    t
                    for t in transactions
                    if t.reconciliation_status == ReconciliationStatus.MATCHED
                ]
            ),
            "partial": len(
                [
                    t
                    for t in transactions
                    if t.reconciliation_status == ReconciliationStatus.PARTIAL
                ]
            ),
            "unmatched": len(
                [
                    t
                    for t in transactions
                    if t.reconciliation_status == ReconciliationStatus.UNMATCHED
                ]
            ),
            "exceptions": len(
                [
                    t
                    for t in transactions
                    if t.reconciliation_status == ReconciliationStatus.EXCEPTION
                ]
            ),
            "total_credits": sum(
                t.amount
                for t in transactions
                if t.transaction_type == TransactionType.CREDIT
            ),
            "total_debits": sum(
                t.amount
                for t in transactions
                if t.transaction_type == TransactionType.DEBIT
            ),
        }

    def get_arrears_report(self) -> List[Dict]:
        """Get list of tenants in arrears."""
        arrears = []

        for invoice in self.invoices.values():
            if invoice.is_paid:
                continue

            if invoice.due_date < date.today():
                tenant = self.tenants.get(invoice.tenant_id)
                property = self.properties.get(invoice.property_id)

                arrears.append(
                    {
                        "invoice_id": invoice.invoice_id,
                        "tenant_name": tenant.name if tenant else "Unknown",
                        "property": f"{property.address}" if property else "Unknown",
                        "amount_due": invoice.outstanding,
                        "due_date": invoice.due_date,
                        "days_overdue": (date.today() - invoice.due_date).days,
                    }
                )

        return sorted(arrears, key=lambda x: x["days_overdue"], reverse=True)


# ============================================================================
# DEMO DATA GENERATOR
# ============================================================================


def generate_demo_data() -> SDAFinancialManager:
    """Generate demo data for testing."""
    manager = SDAFinancialManager("Accessible Homes Property Co")

    # Demo properties
    properties = [
        Property(
            property_id="PROP-001",
            address="Unit 1, 42 Example Street",
            suburb="Sampletown",
            state="SA",
            postcode="5000",
            sda_category="high_physical_support",
            num_bedrooms=2,
            weekly_sda_rate=Decimal("980.50"),
            weekly_rrc_rate=Decimal("150.00"),
            management_fee_percent=Decimal("8.5"),
            registration_number="SDA-SA-12345",
        ),
        Property(
            property_id="PROP-002",
            address="3/88 Demo Road",
            suburb="Testville",
            state="SA",
            postcode="5001",
            sda_category="fully_accessible",
            num_bedrooms=3,
            weekly_sda_rate=Decimal("850.00"),
            weekly_rrc_rate=Decimal("175.00"),
            management_fee_percent=Decimal("8.0"),
            registration_number="SDA-SA-12346",
        ),
        Property(
            property_id="PROP-003",
            address="15 Showcase Avenue",
            suburb="Exampleville",
            state="VIC",
            postcode="3000",
            sda_category="robust",
            num_bedrooms=4,
            weekly_sda_rate=Decimal("920.00"),
            weekly_rrc_rate=Decimal("200.00"),
            management_fee_percent=Decimal("9.0"),
            registration_number="SDA-VIC-98765",
        ),
    ]

    for prop in properties:
        manager.add_property(prop)

    # Demo owners (syndicate example - 4 investors at 25% each for PROP-001)
    owners = [
        # Property 1 - 4-way syndicate
        PropertyOwner(
            owner_id="OWN-001",
            property_id="PROP-001",
            name="Investment Group Alpha",
            email="alpha@example.com",
            phone="0400123456",
            ownership_percent=Decimal("25.0"),
            bsb="062-123",
            account_number="12345678",
            account_name="INVESTMENT ALPHA",
        ),
        PropertyOwner(
            owner_id="OWN-002",
            property_id="PROP-001",
            name="Beta Holdings Pty Ltd",
            email="beta@example.com",
            phone="0400234567",
            ownership_percent=Decimal("25.0"),
            bsb="032-456",
            account_number="87654321",
            account_name="BETA HOLDINGS",
        ),
        PropertyOwner(
            owner_id="OWN-003",
            property_id="PROP-001",
            name="Gamma Investments",
            email="gamma@example.com",
            phone="0400345678",
            ownership_percent=Decimal("25.0"),
            bsb="083-789",
            account_number="11223344",
            account_name="GAMMA INVESTMENTS",
        ),
        PropertyOwner(
            owner_id="OWN-004",
            property_id="PROP-001",
            name="Delta Property Trust",
            email="delta@example.com",
            phone="0400456789",
            ownership_percent=Decimal("25.0"),
            bsb="012-234",
            account_number="55667788",
            account_name="DELTA PROPERTY",
        ),
        # Property 2 - Single owner
        PropertyOwner(
            owner_id="OWN-005",
            property_id="PROP-002",
            name="Jane Smith Family Trust",
            email="jane@example.com",
            phone="0400567890",
            ownership_percent=Decimal("100.0"),
            bsb="062-555",
            account_number="99887766",
            account_name="SMITH FAMILY TRUST",
        ),
        # Property 3 - 2-way split
        PropertyOwner(
            owner_id="OWN-006",
            property_id="PROP-003",
            name="Omega Property Group",
            email="omega@example.com",
            phone="0400678901",
            ownership_percent=Decimal("60.0"),
            bsb="033-111",
            account_number="44556677",
            account_name="OMEGA PROPERTY",
        ),
        PropertyOwner(
            owner_id="OWN-007",
            property_id="PROP-003",
            name="Sigma Investments",
            email="sigma@example.com",
            phone="0400789012",
            ownership_percent=Decimal("40.0"),
            bsb="084-222",
            account_number="77889900",
            account_name="SIGMA INVESTMENTS",
        ),
    ]

    for owner in owners:
        manager.add_owner(owner)

    # Demo tenants
    tenants = [
        Tenant(
            tenant_id="TEN-001",
            property_id="PROP-001",
            name="Alex Johnson",
            ndis_number="432123456",
            move_in_date=date(2024, 1, 15),
            rrc_amount=Decimal("150.00"),
            sda_funding_amount=Decimal("980.50"),
        ),
        Tenant(
            tenant_id="TEN-002",
            property_id="PROP-002",
            name="Sam Williams",
            ndis_number="432234567",
            move_in_date=date(2024, 3, 1),
            rrc_amount=Decimal("175.00"),
            sda_funding_amount=Decimal("850.00"),
        ),
        Tenant(
            tenant_id="TEN-003",
            property_id="PROP-003",
            name="Jordan Brown",
            ndis_number="432345678",
            move_in_date=date(2024, 6, 1),
            rrc_amount=Decimal("200.00"),
            sda_funding_amount=Decimal("920.00"),
        ),
    ]

    for tenant in tenants:
        manager.add_tenant(tenant)

    return manager


def generate_sample_bank_csv() -> str:
    """Generate sample bank statement CSV for testing."""
    csv_content = """Date,Description,Debit,Credit,Balance
01/03/2025,NDIS PLAN MGR - INV-TEN--202503,,"$4,202.14","$50,202.14"
03/03/2025,DIRECT CREDIT - RRC TEN-001,,"$642.86","$50,845.00"
05/03/2025,NDIS PAYMENT - INV-TEN--202503,,"$3,642.86","$54,487.86"
07/03/2025,DIRECT CREDIT - RENT PAYMENT,,"$750.00","$55,237.86"
10/03/2025,NDIS NDIA - PARTICIPANT 432345678,,"$3,942.86","$59,180.72"
15/03/2025,DIRECT CREDIT - UNKNOWN REF,,"$500.00","$59,680.72"
20/03/2025,STRATA FEES - PROP-001,"$450.00",,"$59,230.72"
25/03/2025,INSURANCE - ANNUAL,,"$1,200.00","$58,030.72"
"""
    return csv_content


# ============================================================================
# DEMO RUNNER
# ============================================================================


def run_demo():
    """Run comprehensive demo of the SDA Financial Manager."""
    print("=" * 80)
    print("     SDA FINANCIAL MANAGER - DEMO MODE")
    print("     Property Financial Engine & Reconciliation")
    print("=" * 80)
    print()

    # Initialize with demo data
    print("📊 Initializing system with demo data...")
    manager = generate_demo_data()
    print(f"   ✓ Company: {manager.company_name}")
    print(f"   ✓ Properties: {len(manager.properties)}")
    print(f"   ✓ Investors: {len(manager.owners)}")
    print(f"   ✓ Tenants: {len(manager.tenants)}")
    print()

    # Generate monthly invoices
    print("📝 Generating monthly invoices for March 2025...")
    invoices = manager.generate_monthly_invoices(3, 2025)
    print(f"   ✓ Generated {len(invoices)} invoices")
    for inv in invoices:
        print(
            f"      - {inv.invoice_id}: RRC ${inv.rrc_amount} + SDA ${inv.sda_amount} = ${inv.total_amount}"
        )
    print()

    # Import bank statement
    print("🏦 Importing bank statement...")
    csv_content = generate_sample_bank_csv()
    results = manager.import_bank_statement(csv_content)
    print("   ✓ Imported transactions")
    print(f"   ✓ Auto-matched: {results['matched']}")
    print(f"   ✓ Partial matches: {results['partial']}")
    print(f"   ✓ Unmatched: {results['unmatched']}")
    print(f"   ✓ Exceptions: {results['exceptions']}")
    print()

    # Show reconciliation summary
    print("📋 Reconciliation Summary:")
    summary = manager.get_reconciliation_summary()
    print(f"   Total transactions: {summary['total_transactions']}")
    print(f"   Total credits: ${summary['total_credits']:,.2f}")
    print(f"   Total debits: ${summary['total_debits']:,.2f}")
    print()

    # Mark some invoices as paid for distribution demo
    print("💰 Processing payments and calculating distributions...")
    for inv_id, invoice in manager.invoices.items():
        # Simulate full payment for demo
        invoice.rrc_paid = invoice.rrc_amount
        invoice.sda_paid = invoice.sda_amount
        invoice.is_paid = True
        invoice.paid_date = date(2025, 3, 15)

    # Calculate distributions
    expenses = {
        "PROP-001": [{"description": "Strata fees", "amount": 450}],
        "PROP-002": [{"description": "Maintenance", "amount": 200}],
        "PROP-003": [{"description": "Insurance", "amount": 350}],
    }

    distributions = manager.calculate_period_distributions(
        date(2025, 3, 1), date(2025, 3, 31), expenses
    )
    print(f"   ✓ Calculated {len(distributions)} distributions")
    print()

    # Show distributions by property
    print("📊 Distribution Summary by Property:")
    print("-" * 80)

    for prop_id, prop in manager.properties.items():
        prop_dists = [d for d in distributions if d.property_id == prop_id]
        if not prop_dists:
            continue

        print(f"\n   {prop.address}, {prop.suburb}")
        print(f"   Gross Income: ${prop_dists[0].gross_income:,.2f}")
        print(
            f"   Management Fee ({prop.management_fee_percent}%): ${prop_dists[0].management_fee:,.2f}"
        )
        print(f"   Expenses: ${prop_dists[0].expenses:,.2f}")
        print(f"   Net Income: ${prop_dists[0].net_income:,.2f}")
        print()
        print("   Investor Distributions:")
        for dist in prop_dists:
            owner = manager.owners.get(dist.owner_id)
            print(
                f"      - {owner.name}: {dist.ownership_percent}% = ${dist.distribution_amount:,.2f}"
            )

    print()
    print("-" * 80)

    # Generate ABA file
    print("🏛️ Generating ABA bulk payment file...")
    dist_ids = [d.distribution_id for d in distributions]
    aba_batch = manager.generate_aba_payment_file(dist_ids, "MAR DIST")

    print(f"   ✓ Batch ID: {aba_batch.batch_id}")
    print(f"   ✓ Bank: {aba_batch.bank_name}")
    print(f"   ✓ Transactions: {aba_batch.transaction_count}")
    print(f"   ✓ Total Amount: ${aba_batch.total_amount:,.2f}")
    print()

    # Show ABA file preview
    print("📄 ABA File Preview (first 5 lines):")
    print("-" * 80)
    for i, line in enumerate(aba_batch.file_content.split("\r\n")[:5]):
        print(f"   {line[:70]}...")
    print("-" * 80)
    print()

    # Generate investor statement
    print("📧 Sample Investor Statement:")
    print("-" * 80)
    sample_dist = distributions[0]
    sample_owner = manager.owners.get(sample_dist.owner_id)
    sample_prop = manager.properties.get(sample_dist.property_id)
    statement = manager.distribution_calculator.generate_owner_statement(
        sample_dist, sample_owner, sample_prop
    )
    print(statement)

    # Show arrears report
    print("⚠️ Arrears Report:")
    arrears = manager.get_arrears_report()
    if arrears:
        for arr in arrears:
            print(
                f"   - {arr['tenant_name']}: ${arr['amount_due']:.2f} ({arr['days_overdue']} days overdue)"
            )
    else:
        print("   ✓ No tenants in arrears")
    print()

    print("=" * 80)
    print("                    DEMO COMPLETE")
    print("=" * 80)

    return manager


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SDA Financial Manager - Property Financial Engine"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Run demo mode with sample data"
    )
    parser.add_argument(
        "--generate-aba", action="store_true", help="Generate sample ABA file"
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.generate_aba:
        # Generate sample ABA file
        manager = generate_demo_data()
        manager.generate_monthly_invoices(3, 2025)

        # Mark as paid
        for inv in manager.invoices.values():
            inv.rrc_paid = inv.rrc_amount
            inv.sda_paid = inv.sda_amount
            inv.is_paid = True

        distributions = manager.calculate_period_distributions(
            date(2025, 3, 1), date(2025, 3, 31), {}
        )

        batch = manager.generate_aba_payment_file(
            [d.distribution_id for d in distributions]
        )

        # Save to file
        filename = f"distributions_{batch.batch_id}.aba"
        with open(filename, "w") as f:
            f.write(batch.file_content)
        print(f"ABA file saved: {filename}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
