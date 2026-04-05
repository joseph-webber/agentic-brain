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
"""
AML Compliance Bot for Australian Financial Services.

An AI assistant for Anti-Money Laundering (AML) and Counter-Terrorism
Financing (CTF) compliance under Australian regulations:

- Customer Due Diligence (CDD) workflows
- Enhanced Due Diligence (EDD) for high-risk customers
- Transaction monitoring and screening
- Suspicious Matter Reporting (SMR) to AUSTRAC
- PEP (Politically Exposed Persons) screening
- Sanctions screening (DFAT, UN, OFAC)

Key Australian AML/CTF Context:
    - Anti-Money Laundering and Counter-Terrorism Financing Act 2006
    - AUSTRAC (Australian Transaction Reports and Analysis Centre) requirements
    - AML/CTF Rules and Compliance Guide
    - Designated services and reporting entities obligations

Architecture (Secure On-Premise):
    ┌──────────────────────────────────────────────────────────────────┐
    │                    SECURE FINANCIAL SERVICES ZONE                 │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
    │  │  Ollama  │  │   SQLite     │  │   AML Compliance Bot       │  │
    │  │ (Local)  │◄─┤  (Encrypted) │◄─┤   (This Application)       │  │
    │  └──────────┘  └──────────────┘  └────────────────────────────┘  │
    │              ALL CUSTOMER DATA STAYS LOCAL                        │
    │              PCI-DSS / AML COMPLIANT ENVIRONMENT                  │
    └──────────────────────────────────────────────────────────────────┘

IMPORTANT DISCLAIMERS:
    ⚠️  This is a DEMONSTRATION system only
    ⚠️  NOT official AUSTRAC or regulatory software
    ⚠️  Always verify with legal and compliance teams
    ⚠️  AML decisions require qualified MLRO review
    ⚠️  Filing requirements must be verified with AUSTRAC

Usage:
    python examples/enterprise/aml_compliance_bot.py
    python examples/enterprise/aml_compliance_bot.py --demo

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b  # On-premise LLM
"""

import asyncio
import hashlib
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from agentic_brain.auth import (
    AuthConfig,
    JWTAuth,
    User,
    require_role,
)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("aml.compliance_bot")


# =============================================================================
# AML/CTF ENUMS AND CONSTANTS
# =============================================================================


class CustomerRiskRating(str, Enum):
    """Customer risk rating levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    PROHIBITED = "Prohibited"


class CustomerType(str, Enum):
    """Types of customers for CDD purposes."""

    INDIVIDUAL = "Individual"
    COMPANY = "Company"
    TRUST = "Trust"
    PARTNERSHIP = "Partnership"
    ASSOCIATION = "Association"
    GOVERNMENT = "Government Body"
    SMSF = "Self-Managed Super Fund"


class DesignatedService(str, Enum):
    """AUSTRAC designated services categories."""

    DEPOSIT_TAKING = "Deposit Taking"
    LOANS_CREDIT = "Loans and Credit"
    FOREIGN_EXCHANGE = "Foreign Exchange"
    REMITTANCE = "Remittance Services"
    GAMBLING = "Gambling Services"
    BULLION = "Bullion Dealing"
    DIGITAL_CURRENCY = "Digital Currency Exchange"


class SanctionsList(str, Enum):
    """Sanctions lists for screening."""

    DFAT_CONSOLIDATED = "DFAT Consolidated List"
    UN_SECURITY_COUNCIL = "UN Security Council"
    OFAC_SDN = "OFAC SDN List"
    EU_CONSOLIDATED = "EU Consolidated List"


class SMRIndicator(str, Enum):
    """Suspicious Matter Report indicators."""

    STRUCTURING = "Structuring/Smurfing"
    UNUSUAL_TRANSACTION = "Unusual Transaction"
    IDENTITY_CONCERN = "Identity Concerns"
    SOURCE_OF_FUNDS = "Unexplained Source of Funds"
    SANCTIONS_CONCERN = "Potential Sanctions Breach"
    THIRD_PARTY = "Third Party Involvement"
    INCONSISTENT_ACTIVITY = "Inconsistent with Profile"
    CASH_INTENSIVE = "Unusual Cash Activity"
    HIGH_RISK_JURISDICTION = "High-Risk Jurisdiction"


# AUSTRAC reporting thresholds
THRESHOLD_REPORTING_AMOUNT = Decimal("10000.00")  # TTR threshold for cash
IFTI_REPORTING_AMOUNT = Decimal("0.00")  # All international transfers


# =============================================================================
# CUSTOMER MODEL
# =============================================================================


@dataclass
class Customer:
    """Customer for AML/CTF purposes."""

    customer_id: str
    customer_type: CustomerType
    risk_rating: CustomerRiskRating

    # Individual details
    full_name: str
    date_of_birth: Optional[date] = None
    nationality: str = "AU"
    country_of_residence: str = "AU"

    # Company/Trust details
    entity_name: Optional[str] = None
    abn: Optional[str] = None
    acn: Optional[str] = None

    # Verification
    id_verified: bool = False
    id_verification_date: Optional[date] = None
    id_documents: list[str] = field(default_factory=list)

    # Risk factors
    is_pep: bool = False
    pep_details: str = ""
    is_sanctions_match: bool = False
    high_risk_jurisdiction: bool = False

    # Due diligence
    cdd_completed: bool = False
    cdd_date: Optional[date] = None
    edd_required: bool = False
    edd_completed: bool = False
    edd_date: Optional[date] = None
    edd_review_date: Optional[date] = None

    # Business relationship
    products: list[str] = field(default_factory=list)
    expected_activity: str = ""
    source_of_wealth: str = ""
    source_of_funds: str = ""

    # Beneficial owners (for companies/trusts)
    beneficial_owners: list[dict] = field(default_factory=list)


@dataclass
class Transaction:
    """Financial transaction for monitoring."""

    transaction_id: str
    customer_id: str
    transaction_date: datetime
    transaction_type: str  # Credit, Debit, Transfer
    amount: Decimal
    currency: str

    # Transaction details
    counterparty_name: str = ""
    counterparty_country: str = ""
    payment_method: str = ""  # Cash, EFT, Card, etc.

    # International transfer details
    is_international: bool = False
    originator_country: str = ""
    beneficiary_country: str = ""

    # Risk flags
    is_cash: bool = False
    is_high_risk_country: bool = False
    is_unusual: bool = False
    risk_score: int = 0

    # Reporting
    ttr_required: bool = False
    ttr_submitted: bool = False
    ifti_required: bool = False
    ifti_submitted: bool = False
    smr_filed: bool = False


@dataclass
class SuspiciousMatterReport:
    """AUSTRAC Suspicious Matter Report."""

    smr_id: str
    customer_id: str
    transaction_ids: list[str]
    created_date: datetime
    created_by: str

    indicators: list[SMRIndicator]
    narrative: str
    grounds_for_suspicion: str

    # Timeline
    awareness_date: datetime
    deadline: datetime  # 24 hours for tipping-off, 3 days standard
    submitted_to_austrac: bool = False
    submission_date: Optional[datetime] = None
    austrac_reference: str = ""

    # Review
    reviewed_by: str = ""
    review_date: Optional[datetime] = None
    approved: bool = False


# =============================================================================
# HIGH RISK COUNTRIES (Sample - would be comprehensive in production)
# =============================================================================

HIGH_RISK_COUNTRIES = {
    "AF": "Afghanistan",
    "IR": "Iran",
    "KP": "North Korea",
    "SY": "Syria",
    "YE": "Yemen",
    "MM": "Myanmar",
    "SS": "South Sudan",
}

PEP_CATEGORIES = [
    "Head of State/Government",
    "Senior Politician",
    "Senior Government Official",
    "Senior Judicial Official",
    "Senior Military Officer",
    "Senior Executive of SOE",
    "Senior Political Party Official",
]


# =============================================================================
# AML COMPLIANCE BOT
# =============================================================================


class AMLComplianceBot:
    """
    AML/CTF Compliance Assistant.

    Supports financial institutions with AML/CTF obligations
    under Australian law.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the AML compliance bot."""
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self.customers: dict[str, Customer] = {}
        self.transactions: list[Transaction] = []
        self.smrs: dict[str, SuspiciousMatterReport] = {}
        self._load_demo_data()

    def _create_tables(self):
        """Create database tables."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT
            )
        """
        )
        self.conn.commit()

    def _audit_log(
        self,
        user_id: str,
        action: str,
        entity_type: str = "",
        entity_id: str = "",
        details: str = "",
    ):
        """Log an auditable action."""
        self.conn.execute(
            """
            INSERT INTO audit_log (timestamp, user_id, action, entity_type, entity_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.now(UTC).isoformat(),
                user_id,
                action,
                entity_type,
                entity_id,
                details,
            ),
        )
        self.conn.commit()

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo customers
        self.customers["CUST-001"] = Customer(
            customer_id="CUST-001",
            customer_type=CustomerType.INDIVIDUAL,
            risk_rating=CustomerRiskRating.LOW,
            full_name="John Smith",
            date_of_birth=date(1980, 5, 15),
            nationality="AU",
            country_of_residence="AU",
            id_verified=True,
            id_verification_date=date(2023, 1, 10),
            id_documents=["Driver Licence", "Medicare Card"],
            cdd_completed=True,
            cdd_date=date(2023, 1, 10),
            products=["Transaction Account", "Savings Account"],
            expected_activity="Regular salary deposits, household expenses",
            source_of_wealth="Employment",
            source_of_funds="Salary",
        )

        self.customers["CUST-002"] = Customer(
            customer_id="CUST-002",
            customer_type=CustomerType.INDIVIDUAL,
            risk_rating=CustomerRiskRating.HIGH,
            full_name="Maria Garcia",
            date_of_birth=date(1975, 11, 22),
            nationality="AU",
            country_of_residence="AU",
            id_verified=True,
            id_verification_date=date(2024, 3, 5),
            id_documents=["Passport", "Utility Bill"],
            is_pep=True,
            pep_details="Former state government minister (2015-2020)",
            cdd_completed=True,
            cdd_date=date(2024, 3, 5),
            edd_required=True,
            edd_completed=True,
            edd_date=date(2024, 3, 10),
            edd_review_date=date.today() + timedelta(days=180),
            products=["Business Account", "Term Deposit"],
            expected_activity="Investment income, property settlements",
            source_of_wealth="Former ministerial salary, investments",
            source_of_funds="Property sale",
        )

        self.customers["CUST-003"] = Customer(
            customer_id="CUST-003",
            customer_type=CustomerType.COMPANY,
            risk_rating=CustomerRiskRating.MEDIUM,
            full_name="ABC Trading Pty Ltd",
            entity_name="ABC Trading Pty Ltd",
            abn="12 345 678 901",
            acn="123 456 789",
            country_of_residence="AU",
            id_verified=True,
            id_verification_date=date(2024, 1, 15),
            id_documents=["ASIC Extract", "Trust Deed"],
            cdd_completed=True,
            cdd_date=date(2024, 1, 15),
            products=["Business Account", "Trade Finance"],
            expected_activity="Import/export payments, supplier payments",
            source_of_wealth="Business operations",
            source_of_funds="Trading revenue",
            beneficial_owners=[
                {"name": "James Wong", "ownership": 60, "verified": True},
                {"name": "Lisa Wong", "ownership": 40, "verified": True},
            ],
        )

    # =========================================================================
    # CUSTOMER DUE DILIGENCE (CDD)
    # =========================================================================

    def perform_cdd_check(
        self,
        customer_id: str,
        analyst_id: str,
    ) -> dict:
        """Perform Customer Due Diligence check."""
        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": "Customer not found"}

        checks = {
            "customer_id": customer_id,
            "check_date": datetime.now(UTC).isoformat(),
            "checks_performed": [],
            "risk_factors": [],
            "required_actions": [],
        }

        # ID Verification check
        if customer.id_verified:
            checks["checks_performed"].append(
                {
                    "check": "Identity Verification",
                    "status": "Completed",
                    "date": customer.id_verification_date.isoformat(),
                    "documents": customer.id_documents,
                }
            )
        else:
            checks["required_actions"].append("Complete identity verification")

        # PEP Check
        pep_result = self.screen_pep(customer_id)
        checks["checks_performed"].append(
            {
                "check": "PEP Screening",
                "status": "Match" if pep_result["is_pep"] else "Clear",
                "details": pep_result.get("details", ""),
            }
        )
        if pep_result["is_pep"]:
            checks["risk_factors"].append("Politically Exposed Person")

        # Sanctions Check
        sanctions_result = self.screen_sanctions(customer_id)
        checks["checks_performed"].append(
            {
                "check": "Sanctions Screening",
                "status": "Potential Match" if sanctions_result["matches"] else "Clear",
                "lists_checked": sanctions_result["lists_checked"],
            }
        )
        if sanctions_result["matches"]:
            checks["risk_factors"].append("Potential sanctions match")
            checks["required_actions"].append("Escalate to MLRO for sanctions review")

        # High-risk jurisdiction check
        if customer.country_of_residence in HIGH_RISK_COUNTRIES:
            checks["risk_factors"].append(
                f"High-risk country: {HIGH_RISK_COUNTRIES[customer.country_of_residence]}"
            )

        # Determine if EDD required
        edd_triggers = [
            customer.is_pep,
            customer.risk_rating == CustomerRiskRating.HIGH,
            customer.country_of_residence in HIGH_RISK_COUNTRIES,
            customer.customer_type in [CustomerType.TRUST, CustomerType.COMPANY],
        ]

        if any(edd_triggers):
            checks["edd_required"] = True
            if not customer.edd_completed:
                checks["required_actions"].append("Complete Enhanced Due Diligence")
        else:
            checks["edd_required"] = False

        # Calculate overall risk
        risk_score = len(checks["risk_factors"])
        if risk_score == 0:
            checks["recommended_rating"] = CustomerRiskRating.LOW.value
        elif risk_score <= 2:
            checks["recommended_rating"] = CustomerRiskRating.MEDIUM.value
        else:
            checks["recommended_rating"] = CustomerRiskRating.HIGH.value

        self._audit_log(
            user_id=analyst_id,
            action="PERFORM_CDD",
            entity_type="Customer",
            entity_id=customer_id,
            details=f"Risk factors: {len(checks['risk_factors'])}, EDD required: {checks['edd_required']}",
        )

        return checks

    def screen_pep(self, customer_id: str) -> dict:
        """Screen customer against PEP databases."""
        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": "Customer not found"}

        result = {
            "customer_id": customer_id,
            "screening_date": datetime.now(UTC).isoformat(),
            "is_pep": customer.is_pep,
            "details": customer.pep_details if customer.is_pep else "",
            "category": "",
        }

        if customer.is_pep:
            # Determine PEP category (simplified)
            if "minister" in customer.pep_details.lower():
                result["category"] = "Senior Politician"
            result["edd_required"] = True
            result["review_frequency"] = "Annual"

        return result

    def screen_sanctions(self, customer_id: str) -> dict:
        """Screen customer against sanctions lists."""
        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": "Customer not found"}

        # In production, would call actual sanctions screening APIs
        result = {
            "customer_id": customer_id,
            "screening_date": datetime.now(UTC).isoformat(),
            "name_screened": customer.full_name,
            "lists_checked": [
                SanctionsList.DFAT_CONSOLIDATED.value,
                SanctionsList.UN_SECURITY_COUNCIL.value,
            ],
            "matches": [],
        }

        # Check against demo sanctions (would be API in production)
        if customer.is_sanctions_match:
            result["matches"].append(
                {
                    "list": SanctionsList.DFAT_CONSOLIDATED.value,
                    "match_type": "Potential",
                    "action_required": "Manual review by MLRO",
                }
            )

        return result

    # =========================================================================
    # TRANSACTION MONITORING
    # =========================================================================

    def monitor_transaction(
        self,
        transaction: Transaction,
        analyst_id: str,
    ) -> dict:
        """Monitor a transaction for suspicious activity."""
        customer = self.customers.get(transaction.customer_id)
        if not customer:
            return {"error": "Customer not found"}

        alerts = []
        risk_score = 0

        # Rule 1: Cash threshold
        if transaction.is_cash and transaction.amount >= THRESHOLD_REPORTING_AMOUNT:
            alerts.append(
                {
                    "rule": "CASH_THRESHOLD",
                    "description": f"Cash transaction ≥ ${THRESHOLD_REPORTING_AMOUNT}",
                    "action": "TTR Required",
                }
            )
            transaction.ttr_required = True
            risk_score += 3

        # Rule 2: International transfer
        if transaction.is_international:
            transaction.ifti_required = True
            alerts.append(
                {
                    "rule": "INTERNATIONAL_TRANSFER",
                    "description": "International funds transfer",
                    "action": "IFTI Required",
                }
            )
            risk_score += 1

            # High-risk country
            if transaction.beneficiary_country in HIGH_RISK_COUNTRIES:
                alerts.append(
                    {
                        "rule": "HIGH_RISK_COUNTRY",
                        "description": f"Transfer to {HIGH_RISK_COUNTRIES[transaction.beneficiary_country]}",
                        "action": "Enhanced review required",
                    }
                )
                risk_score += 5

        # Rule 3: Structuring detection (simplified)
        recent_transactions = [
            t
            for t in self.transactions
            if t.customer_id == transaction.customer_id
            and t.is_cash
            and (transaction.transaction_date - t.transaction_date).days <= 7
        ]

        total_recent_cash = sum(t.amount for t in recent_transactions) + (
            transaction.amount if transaction.is_cash else Decimal("0")
        )

        if total_recent_cash >= THRESHOLD_REPORTING_AMOUNT * Decimal("0.9"):
            if len(recent_transactions) >= 2:
                alerts.append(
                    {
                        "rule": "POTENTIAL_STRUCTURING",
                        "description": "Multiple cash transactions approaching threshold",
                        "action": "SMR consideration required",
                    }
                )
                risk_score += 5

        # Rule 4: Inconsistent with profile
        if customer.expected_activity:
            # Simplified check - would use ML in production
            if (
                transaction.amount > Decimal("50000")
                and "salary" in customer.expected_activity.lower()
            ):
                alerts.append(
                    {
                        "rule": "PROFILE_INCONSISTENT",
                        "description": "Large transaction inconsistent with expected activity",
                        "action": "Manual review required",
                    }
                )
                risk_score += 3

        # Rule 5: PEP transaction monitoring
        if customer.is_pep:
            alerts.append(
                {
                    "rule": "PEP_TRANSACTION",
                    "description": "Transaction by Politically Exposed Person",
                    "action": "Enhanced monitoring",
                }
            )
            risk_score += 2

        transaction.risk_score = risk_score
        self.transactions.append(transaction)

        result = {
            "transaction_id": transaction.transaction_id,
            "customer_id": transaction.customer_id,
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "risk_score": risk_score,
            "alerts": alerts,
            "ttr_required": transaction.ttr_required,
            "ifti_required": transaction.ifti_required,
            "smr_recommended": risk_score >= 5,
        }

        if result["smr_recommended"]:
            result["smr_indicators"] = self._identify_smr_indicators(alerts)

        self._audit_log(
            user_id=analyst_id,
            action="MONITOR_TRANSACTION",
            entity_type="Transaction",
            entity_id=transaction.transaction_id,
            details=f"Risk score: {risk_score}, Alerts: {len(alerts)}",
        )

        return result

    def _identify_smr_indicators(self, alerts: list[dict]) -> list[str]:
        """Identify SMR indicators from alerts."""
        indicators = []

        rule_to_indicator = {
            "POTENTIAL_STRUCTURING": SMRIndicator.STRUCTURING.value,
            "PROFILE_INCONSISTENT": SMRIndicator.INCONSISTENT_ACTIVITY.value,
            "HIGH_RISK_COUNTRY": SMRIndicator.HIGH_RISK_JURISDICTION.value,
            "CASH_THRESHOLD": SMRIndicator.CASH_INTENSIVE.value,
        }

        for alert in alerts:
            rule = alert.get("rule", "")
            if rule in rule_to_indicator:
                indicators.append(rule_to_indicator[rule])

        return list(set(indicators))

    # =========================================================================
    # SUSPICIOUS MATTER REPORTING (SMR)
    # =========================================================================

    def create_smr(
        self,
        customer_id: str,
        transaction_ids: list[str],
        indicators: list[SMRIndicator],
        narrative: str,
        grounds_for_suspicion: str,
        analyst_id: str,
    ) -> dict:
        """Create a Suspicious Matter Report."""
        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": "Customer not found"}

        smr_id = f"SMR-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(UTC)

        # Standard deadline is 3 business days from forming suspicion
        # 24 hours if it relates to terrorism financing
        deadline = now + timedelta(days=3)

        smr = SuspiciousMatterReport(
            smr_id=smr_id,
            customer_id=customer_id,
            transaction_ids=transaction_ids,
            created_date=now,
            created_by=analyst_id,
            indicators=indicators,
            narrative=narrative,
            grounds_for_suspicion=grounds_for_suspicion,
            awareness_date=now,
            deadline=deadline,
        )

        self.smrs[smr_id] = smr

        self._audit_log(
            user_id=analyst_id,
            action="CREATE_SMR",
            entity_type="SMR",
            entity_id=smr_id,
            details=f"Customer: {customer_id}, Indicators: {len(indicators)}",
        )

        return {
            "success": True,
            "smr_id": smr_id,
            "customer_id": customer_id,
            "customer_name": customer.full_name,
            "indicators": [i.value for i in indicators],
            "deadline": deadline.isoformat(),
            "next_steps": [
                "Submit for MLRO review",
                "Gather supporting documentation",
                f"File with AUSTRAC by {deadline.strftime('%Y-%m-%d %H:%M')}",
            ],
            "tipping_off_warning": (
                "⚠️ TIPPING OFF WARNING: Do not disclose the existence of this "
                "SMR to the customer or any person not authorised to receive "
                "this information. Tipping off is a criminal offence."
            ),
        }

    def approve_smr(
        self,
        smr_id: str,
        mlro_id: str,
        approved: bool,
        comments: str = "",
    ) -> dict:
        """MLRO approves or rejects an SMR."""
        smr = self.smrs.get(smr_id)
        if not smr:
            return {"error": "SMR not found"}

        smr.reviewed_by = mlro_id
        smr.review_date = datetime.now(UTC)
        smr.approved = approved

        self._audit_log(
            user_id=mlro_id,
            action="APPROVE_SMR" if approved else "REJECT_SMR",
            entity_type="SMR",
            entity_id=smr_id,
            details=comments,
        )

        if approved:
            return {
                "success": True,
                "smr_id": smr_id,
                "status": "Approved",
                "next_step": "Submit to AUSTRAC via AUSTRACOnline",
                "deadline": smr.deadline.isoformat(),
            }
        else:
            return {
                "success": True,
                "smr_id": smr_id,
                "status": "Rejected",
                "reason": comments,
            }

    # =========================================================================
    # REPORTING
    # =========================================================================

    def generate_compliance_dashboard(self) -> dict:
        """Generate compliance dashboard summary."""
        now = datetime.now(UTC)

        # Customer statistics
        customer_stats = {
            "total_customers": len(self.customers),
            "high_risk": sum(
                1
                for c in self.customers.values()
                if c.risk_rating == CustomerRiskRating.HIGH
            ),
            "peps": sum(1 for c in self.customers.values() if c.is_pep),
            "edd_due": sum(
                1
                for c in self.customers.values()
                if c.edd_required
                and c.edd_review_date
                and c.edd_review_date <= date.today()
            ),
        }

        # Transaction statistics
        last_30_days = now - timedelta(days=30)
        recent_transactions = [
            t for t in self.transactions if t.transaction_date >= last_30_days
        ]

        transaction_stats = {
            "total_transactions": len(recent_transactions),
            "total_value": str(sum(t.amount for t in recent_transactions)),
            "high_risk_transactions": sum(
                1 for t in recent_transactions if t.risk_score >= 5
            ),
            "ttrs_required": sum(1 for t in recent_transactions if t.ttr_required),
            "iftis_required": sum(1 for t in recent_transactions if t.ifti_required),
        }

        # SMR statistics
        smr_stats = {
            "total_smrs": len(self.smrs),
            "pending_review": sum(1 for s in self.smrs.values() if not s.reviewed_by),
            "pending_submission": sum(
                1
                for s in self.smrs.values()
                if s.approved and not s.submitted_to_austrac
            ),
            "overdue": sum(
                1
                for s in self.smrs.values()
                if not s.submitted_to_austrac and s.deadline < now
            ),
        }

        return {
            "generated_at": now.isoformat(),
            "customers": customer_stats,
            "transactions_30d": transaction_stats,
            "suspicious_matters": smr_stats,
            "alerts": self._generate_compliance_alerts(
                customer_stats, transaction_stats, smr_stats
            ),
        }

    def _generate_compliance_alerts(
        self,
        customer_stats: dict,
        transaction_stats: dict,
        smr_stats: dict,
    ) -> list[str]:
        """Generate compliance alerts."""
        alerts = []

        if customer_stats["edd_due"] > 0:
            alerts.append(f"⚠️ {customer_stats['edd_due']} EDD reviews are overdue")

        if smr_stats["pending_review"] > 0:
            alerts.append(f"⚠️ {smr_stats['pending_review']} SMRs pending MLRO review")

        if smr_stats["overdue"] > 0:
            alerts.append(
                f"🚨 {smr_stats['overdue']} SMRs overdue for AUSTRAC submission"
            )

        if transaction_stats["high_risk_transactions"] > 10:
            alerts.append(
                f"⚠️ High volume of high-risk transactions: {transaction_stats['high_risk_transactions']}"
            )

        return alerts


# =============================================================================
# DEMO EXECUTION
# =============================================================================


async def run_demo():
    """Run demonstration of the AML compliance bot."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AML COMPLIANCE BOT - DEMO                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ⚠️  DEMONSTRATION ONLY - NOT OFFICIAL AUSTRAC SOFTWARE                       ║
║  Aligned with AML/CTF Act 2006 requirements.                                  ║
║  Always verify with qualified MLRO and legal counsel.                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )

    bot = AMLComplianceBot()

    # Demo: CDD Check
    print("\n" + "=" * 70)
    print("SCENARIO 1: Customer Due Diligence (CDD)")
    print("=" * 70)

    cdd_result = bot.perform_cdd_check("CUST-001", "ANALYST-001")
    print(f"\nCDD Check for Customer: {cdd_result['customer_id']}")
    print(f"Risk Factors: {len(cdd_result['risk_factors'])}")
    print(f"EDD Required: {cdd_result['edd_required']}")
    print(f"Recommended Rating: {cdd_result['recommended_rating']}")

    # Demo: PEP CDD
    print("\n" + "=" * 70)
    print("SCENARIO 2: PEP Customer Due Diligence")
    print("=" * 70)

    pep_cdd = bot.perform_cdd_check("CUST-002", "ANALYST-001")
    print(f"\nCDD Check for PEP Customer: {pep_cdd['customer_id']}")
    print("Risk Factors:")
    for factor in pep_cdd["risk_factors"]:
        print(f"  • {factor}")
    print(f"EDD Required: {pep_cdd['edd_required']}")
    print(f"Recommended Rating: {pep_cdd['recommended_rating']}")

    # Demo: Transaction Monitoring
    print("\n" + "=" * 70)
    print("SCENARIO 3: Transaction Monitoring - Cash Deposit")
    print("=" * 70)

    transaction = Transaction(
        transaction_id="TXN-001",
        customer_id="CUST-001",
        transaction_date=datetime.now(UTC),
        transaction_type="Credit",
        amount=Decimal("12500.00"),
        currency="AUD",
        payment_method="Cash",
        is_cash=True,
    )

    result = bot.monitor_transaction(transaction, "ANALYST-001")
    print(f"\nTransaction: {result['transaction_id']}")
    print(f"Amount: ${result['amount']} {result['currency']}")
    print(f"Risk Score: {result['risk_score']}")
    print(f"TTR Required: {result['ttr_required']}")
    print("Alerts:")
    for alert in result["alerts"]:
        print(f"  • [{alert['rule']}] {alert['description']}")

    # Demo: International Transfer
    print("\n" + "=" * 70)
    print("SCENARIO 4: International Transfer to High-Risk Country")
    print("=" * 70)

    intl_transaction = Transaction(
        transaction_id="TXN-002",
        customer_id="CUST-002",
        transaction_date=datetime.now(UTC),
        transaction_type="Debit",
        amount=Decimal("25000.00"),
        currency="AUD",
        is_international=True,
        beneficiary_country="IR",  # Iran - high risk
        counterparty_name="Trading Company",
    )

    result = bot.monitor_transaction(intl_transaction, "ANALYST-001")
    print(f"\nTransaction: {result['transaction_id']}")
    print(f"Amount: ${result['amount']}")
    print(f"Risk Score: {result['risk_score']}")
    print(f"SMR Recommended: {result['smr_recommended']}")
    print("Alerts:")
    for alert in result["alerts"]:
        print(f"  • [{alert['rule']}] {alert['description']}")

    # Demo: Create SMR
    print("\n" + "=" * 70)
    print("SCENARIO 5: Suspicious Matter Report Creation")
    print("=" * 70)

    smr = bot.create_smr(
        customer_id="CUST-002",
        transaction_ids=["TXN-002"],
        indicators=[
            SMRIndicator.HIGH_RISK_JURISDICTION,
            SMRIndicator.UNUSUAL_TRANSACTION,
        ],
        narrative="PEP customer initiated large transfer to Iran-based entity with unclear business purpose.",
        grounds_for_suspicion="Transfer to high-risk jurisdiction inconsistent with stated business activities.",
        analyst_id="ANALYST-001",
    )

    print(f"\n✓ SMR Created: {smr['smr_id']}")
    print(f"Customer: {smr['customer_name']}")
    print(f"Indicators: {', '.join(smr['indicators'])}")
    print(f"Deadline: {smr['deadline'][:10]}")
    print(f"\n{smr['tipping_off_warning']}")

    # Demo: Dashboard
    print("\n" + "=" * 70)
    print("SCENARIO 6: Compliance Dashboard")
    print("=" * 70)

    dashboard = bot.generate_compliance_dashboard()
    print(f"\nCompliance Dashboard - {dashboard['generated_at'][:10]}")
    print("\nCustomers:")
    print(f"  Total: {dashboard['customers']['total_customers']}")
    print(f"  High Risk: {dashboard['customers']['high_risk']}")
    print(f"  PEPs: {dashboard['customers']['peps']}")
    print("\nSuspicious Matters:")
    print(f"  Total SMRs: {dashboard['suspicious_matters']['total_smrs']}")
    print(f"  Pending Review: {dashboard['suspicious_matters']['pending_review']}")
    print("\nAlerts:")
    for alert in dashboard["alerts"]:
        print(f"  {alert}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AML Compliance Bot Demo")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run full demonstration",
    )

    args = parser.parse_args()
    asyncio.run(run_demo())
