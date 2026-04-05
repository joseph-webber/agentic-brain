#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 30: Legal & Compliance Assistant

An enterprise legal and compliance assistant:
- Policy compliance checking
- Contract clause lookup
- Regulatory requirement search
- Audit trail logging
- Document classification

Key patterns demonstrated:
- Compliance rule engine
- Audit logging for all actions
- Document classification
- Regulatory mapping
- Risk assessment

Usage:
    python examples/30_legal_compliance.py

Requirements:
    pip install agentic-brain
"""

import asyncio
import hashlib
import json
import random
import string
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class ComplianceStatus(Enum):
    """Compliance check status."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNDER_REVIEW = "under_review"
    EXEMPT = "exempt"


class RiskLevel(Enum):
    """Risk assessment level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentType(Enum):
    """Document classification types."""

    CONTRACT = "contract"
    POLICY = "policy"
    REGULATION = "regulation"
    PROCEDURE = "procedure"
    GUIDELINE = "guideline"
    TEMPLATE = "template"
    AUDIT_REPORT = "audit_report"
    CORRESPONDENCE = "correspondence"


class ClauseType(Enum):
    """Standard contract clause types."""

    CONFIDENTIALITY = "confidentiality"
    INDEMNIFICATION = "indemnification"
    LIMITATION_LIABILITY = "limitation_of_liability"
    TERMINATION = "termination"
    FORCE_MAJEURE = "force_majeure"
    GOVERNING_LAW = "governing_law"
    DISPUTE_RESOLUTION = "dispute_resolution"
    DATA_PROTECTION = "data_protection"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    PAYMENT_TERMS = "payment_terms"
    WARRANTY = "warranty"
    ASSIGNMENT = "assignment"


class Regulation(Enum):
    """Regulatory frameworks."""

    GDPR = "gdpr"
    CCPA = "ccpa"
    SOX = "sox"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOC2 = "soc2"
    ISO27001 = "iso27001"


class AuditAction(Enum):
    """Audit log action types."""

    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    SEARCH = "search"


class UserRole(Enum):
    """System user roles."""

    EMPLOYEE = "employee"
    MANAGER = "manager"
    LEGAL = "legal"
    COMPLIANCE = "compliance"
    ADMIN = "admin"


@dataclass
class User:
    """System user."""

    id: str
    email: str
    name: str
    department: str
    role: UserRole


@dataclass
class AuditLog:
    """Audit log entry."""

    id: str
    timestamp: datetime
    user_id: str
    action: AuditAction
    resource_type: str
    resource_id: str
    details: str
    ip_address: str = "internal"
    success: bool = True


@dataclass
class ComplianceRequirement:
    """A compliance requirement."""

    id: str
    regulation: Regulation
    title: str
    description: str
    category: str
    risk_level: RiskLevel
    controls: list
    evidence_required: list
    review_frequency: str = "annual"


@dataclass
class ComplianceCheck:
    """Result of a compliance check."""

    id: str
    requirement_id: str
    checked_at: datetime
    status: ComplianceStatus
    findings: list
    risk_level: RiskLevel
    recommendations: list
    due_date: Optional[date] = None
    owner_id: str = ""
    remediation_plan: str = ""


@dataclass
class ContractClause:
    """Standard contract clause."""

    id: str
    clause_type: ClauseType
    title: str
    standard_text: str
    risk_notes: str
    negotiable: bool = True
    required: bool = False
    alternatives: list = field(default_factory=list)


@dataclass
class Document:
    """Legal/compliance document."""

    id: str
    title: str
    doc_type: DocumentType
    classification: str  # public, internal, confidential, restricted
    content_preview: str
    full_text: str
    regulations: list[Regulation] = field(default_factory=list)
    keywords: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    owner_id: str = ""
    version: str = "1.0"
    retention_period: str = "7 years"


@dataclass
class PolicyViolation:
    """A policy violation record."""

    id: str
    policy_id: str
    description: str
    severity: RiskLevel
    detected_at: datetime
    detected_by: str
    status: str = "open"
    resolution: str = ""
    resolved_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# LEGAL & COMPLIANCE SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class LegalComplianceService:
    """Enterprise legal and compliance service."""

    def __init__(self):
        """Initialize with demo data."""
        self.users: dict[str, User] = {}
        self.requirements: dict[str, ComplianceRequirement] = {}
        self.checks: dict[str, ComplianceCheck] = {}
        self.clauses: dict[str, ContractClause] = {}
        self.documents: dict[str, Document] = {}
        self.violations: dict[str, PolicyViolation] = {}
        self.audit_logs: list[AuditLog] = []
        self.current_user: Optional[User] = None
        self._load_demo_data()

    def _generate_id(self, prefix: str = "ID") -> str:
        """Generate unique ID."""
        suffix = "".join(random.choices(string.digits + string.ascii_uppercase, k=8))
        return f"{prefix}-{suffix}"

    def _log_audit(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        details: str,
        success: bool = True,
    ):
        """Log an audit event."""
        log = AuditLog(
            id=self._generate_id("AUD"),
            timestamp=datetime.now(),
            user_id=self.current_user.id if self.current_user else "SYSTEM",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            success=success,
        )
        self.audit_logs.append(log)
        return log.id

    def _load_demo_data(self):
        """Load demonstration data."""
        # Demo users
        users = [
            User(
                "U001",
                "john.smith@company.com",
                "John Smith",
                "Engineering",
                UserRole.EMPLOYEE,
            ),
            User(
                "U002",
                "sarah.legal@company.com",
                "Sarah Wilson",
                "Legal",
                UserRole.LEGAL,
            ),
            User(
                "U003",
                "mike.compliance@company.com",
                "Mike Chen",
                "Compliance",
                UserRole.COMPLIANCE,
            ),
            User("U004", "admin@company.com", "Admin User", "IT", UserRole.ADMIN),
        ]
        for user in users:
            self.users[user.id] = user

        # Compliance requirements
        requirements = [
            ComplianceRequirement(
                id="REQ-GDPR-001",
                regulation=Regulation.GDPR,
                title="Data Subject Access Requests",
                description="Ability to respond to data subject access requests within 30 days",
                category="Data Subject Rights",
                risk_level=RiskLevel.HIGH,
                controls=[
                    "DSAR process documented",
                    "Automated data inventory",
                    "Response tracking system",
                ],
                evidence_required=[
                    "DSAR response logs",
                    "Process documentation",
                    "Training records",
                ],
            ),
            ComplianceRequirement(
                id="REQ-GDPR-002",
                regulation=Regulation.GDPR,
                title="Consent Management",
                description="Valid consent obtained and documented for personal data processing",
                category="Lawful Basis",
                risk_level=RiskLevel.HIGH,
                controls=[
                    "Consent management platform",
                    "Opt-out mechanisms",
                    "Consent records",
                ],
                evidence_required=[
                    "Consent records",
                    "Privacy notices",
                    "Withdrawal logs",
                ],
            ),
            ComplianceRequirement(
                id="REQ-SOX-001",
                regulation=Regulation.SOX,
                title="Financial Reporting Controls",
                description="Internal controls over financial reporting",
                category="Financial Integrity",
                risk_level=RiskLevel.CRITICAL,
                controls=[
                    "Segregation of duties",
                    "Approval workflows",
                    "Audit trails",
                ],
                evidence_required=[
                    "Control test results",
                    "Audit reports",
                    "Access logs",
                ],
            ),
            ComplianceRequirement(
                id="REQ-PCI-001",
                regulation=Regulation.PCI_DSS,
                title="Cardholder Data Protection",
                description="Protection of cardholder data in storage and transit",
                category="Data Security",
                risk_level=RiskLevel.CRITICAL,
                controls=[
                    "Encryption at rest",
                    "Encryption in transit",
                    "Access controls",
                    "Tokenization",
                ],
                evidence_required=[
                    "Encryption certificates",
                    "Penetration test results",
                    "Access reviews",
                ],
            ),
            ComplianceRequirement(
                id="REQ-SOC2-001",
                regulation=Regulation.SOC2,
                title="Access Control",
                description="Logical and physical access controls for systems and data",
                category="Security",
                risk_level=RiskLevel.HIGH,
                controls=[
                    "MFA implementation",
                    "Access reviews",
                    "Privileged access management",
                ],
                evidence_required=[
                    "Access review records",
                    "MFA configuration",
                    "Termination checklists",
                ],
            ),
            ComplianceRequirement(
                id="REQ-ISO-001",
                regulation=Regulation.ISO27001,
                title="Information Security Policy",
                description="Documented information security policy reviewed regularly",
                category="Policy Management",
                risk_level=RiskLevel.MEDIUM,
                controls=[
                    "Policy document",
                    "Annual review process",
                    "Employee acknowledgment",
                ],
                evidence_required=[
                    "Current policy document",
                    "Review records",
                    "Acknowledgment logs",
                ],
            ),
        ]
        for req in requirements:
            self.requirements[req.id] = req

        # Compliance checks
        checks = [
            ComplianceCheck(
                id="CHK-001",
                requirement_id="REQ-GDPR-001",
                checked_at=datetime.now(),
                status=ComplianceStatus.COMPLIANT,
                findings=[
                    "DSAR process documented and tested",
                    "Response time under 30 days",
                ],
                risk_level=RiskLevel.LOW,
                recommendations=["Consider automating data discovery"],
                owner_id="U003",
            ),
            ComplianceCheck(
                id="CHK-002",
                requirement_id="REQ-PCI-001",
                checked_at=datetime.now(),
                status=ComplianceStatus.PARTIAL,
                findings=[
                    "Encryption at rest implemented",
                    "Some legacy systems lack tokenization",
                ],
                risk_level=RiskLevel.HIGH,
                recommendations=[
                    "Implement tokenization for legacy payment systems",
                    "Complete by Q2",
                ],
                due_date=date(2024, 6, 30),
                owner_id="U003",
                remediation_plan="Migration to tokenized payment processing",
            ),
            ComplianceCheck(
                id="CHK-003",
                requirement_id="REQ-SOX-001",
                checked_at=datetime.now(),
                status=ComplianceStatus.COMPLIANT,
                findings=[
                    "All controls tested and effective",
                    "No material weaknesses",
                ],
                risk_level=RiskLevel.LOW,
                recommendations=["Continue quarterly testing"],
                owner_id="U003",
            ),
        ]
        for check in checks:
            self.checks[check.id] = check

        # Contract clauses
        clauses = [
            ContractClause(
                id="CL-001",
                clause_type=ClauseType.CONFIDENTIALITY,
                title="Standard Confidentiality Clause",
                standard_text="""Each party agrees to maintain the confidentiality of all 
Confidential Information received from the other party and to use such information 
solely for the purposes of this Agreement. This obligation shall survive termination 
for a period of five (5) years.""",
                risk_notes="Ensure duration is appropriate for the type of information exchanged",
                negotiable=True,
                required=True,
            ),
            ContractClause(
                id="CL-002",
                clause_type=ClauseType.LIMITATION_LIABILITY,
                title="Limitation of Liability",
                standard_text="""IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, 
INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES. THE TOTAL LIABILITY OF EACH PARTY 
SHALL NOT EXCEED THE AMOUNTS PAID OR PAYABLE UNDER THIS AGREEMENT IN THE TWELVE 
(12) MONTHS PRECEDING THE CLAIM.""",
                risk_notes="May need higher caps for enterprise agreements. Carve-outs for IP, data breach.",
                negotiable=True,
                required=True,
                alternatives=[
                    "Unlimited liability for specific breaches",
                    "Insurance requirement",
                ],
            ),
            ContractClause(
                id="CL-003",
                clause_type=ClauseType.DATA_PROTECTION,
                title="Data Protection and Privacy",
                standard_text="""Each party shall comply with all applicable data protection laws 
including GDPR and CCPA. The parties shall enter into a Data Processing Agreement 
where required. Personal data shall be processed only as necessary for the 
performance of this Agreement.""",
                risk_notes="DPA addendum required for any personal data processing. Check vendor compliance.",
                negotiable=False,
                required=True,
            ),
            ContractClause(
                id="CL-004",
                clause_type=ClauseType.TERMINATION,
                title="Termination for Convenience",
                standard_text="""Either party may terminate this Agreement upon sixty (60) days 
prior written notice to the other party. Upon termination, all accrued payment 
obligations shall become immediately due and payable.""",
                risk_notes="Consider impact on ongoing projects. May need longer notice for critical vendors.",
                negotiable=True,
                required=False,
            ),
            ContractClause(
                id="CL-005",
                clause_type=ClauseType.FORCE_MAJEURE,
                title="Force Majeure",
                standard_text="""Neither party shall be liable for any failure to perform due to 
causes beyond its reasonable control, including acts of God, war, terrorism, 
pandemic, labor disputes, or governmental actions. The affected party shall 
provide notice within ten (10) days.""",
                risk_notes="Ensure pandemic/epidemic is explicitly included post-COVID.",
                negotiable=True,
                required=True,
            ),
            ContractClause(
                id="CL-006",
                clause_type=ClauseType.GOVERNING_LAW,
                title="Governing Law and Jurisdiction",
                standard_text="""This Agreement shall be governed by and construed in accordance 
with the laws of the State of Delaware, without regard to conflicts of law principles. 
Any disputes shall be resolved in the state or federal courts located in Delaware.""",
                risk_notes="Prefer Delaware or jurisdiction where company is incorporated.",
                negotiable=True,
                required=True,
            ),
            ContractClause(
                id="CL-007",
                clause_type=ClauseType.INTELLECTUAL_PROPERTY,
                title="Intellectual Property Rights",
                standard_text="""All pre-existing intellectual property shall remain the sole 
property of the owning party. Any intellectual property developed specifically for 
Client under this Agreement shall be owned by Client upon full payment. Vendor 
retains ownership of any underlying tools, methodologies, or pre-existing IP.""",
                risk_notes="Clarify ownership of derivatives. Consider licensing vs assignment.",
                negotiable=True,
                required=True,
            ),
        ]
        for clause in clauses:
            self.clauses[clause.id] = clause

        # Documents
        documents = [
            Document(
                id="DOC-001",
                title="Information Security Policy",
                doc_type=DocumentType.POLICY,
                classification="internal",
                content_preview="This policy establishes the framework for information security...",
                full_text="""INFORMATION SECURITY POLICY v3.2

1. PURPOSE
This policy establishes the framework for protecting company information assets.

2. SCOPE
Applies to all employees, contractors, and third parties with access to company systems.

3. POLICY STATEMENTS
3.1 All data must be classified according to the Data Classification Standard
3.2 Access is granted on a least-privilege basis
3.3 All systems must have current security patches
3.4 Security incidents must be reported within 4 hours

4. RESPONSIBILITIES
- IT Security: Implement and monitor controls
- Employees: Follow security procedures
- Managers: Ensure team compliance""",
                regulations=[Regulation.ISO27001, Regulation.SOC2],
                keywords=["security", "policy", "information", "access control"],
                owner_id="U003",
            ),
            Document(
                id="DOC-002",
                title="Data Retention Policy",
                doc_type=DocumentType.POLICY,
                classification="internal",
                content_preview="This policy defines retention periods for business records...",
                full_text="""DATA RETENTION POLICY v2.1

1. PURPOSE
Define retention periods for business records to ensure legal compliance.

2. RETENTION PERIODS
- Financial records: 7 years
- HR records: 7 years after termination
- Customer data: Duration of relationship + 3 years
- Marketing consent: Until withdrawn + 2 years
- System logs: 1 year

3. DELETION PROCEDURES
Data must be securely deleted using approved methods when retention period expires.

4. LEGAL HOLDS
Retention periods are suspended for data subject to legal holds.""",
                regulations=[Regulation.GDPR, Regulation.SOX],
                keywords=["retention", "data", "records", "deletion"],
                owner_id="U003",
            ),
            Document(
                id="DOC-003",
                title="Vendor Risk Assessment Template",
                doc_type=DocumentType.TEMPLATE,
                classification="internal",
                content_preview="Template for assessing third-party vendor risks...",
                full_text="""VENDOR RISK ASSESSMENT

VENDOR INFORMATION
- Name: _______________
- Service: _______________
- Data Access: [ ] None [ ] Internal [ ] Confidential [ ] PII

SECURITY ASSESSMENT
1. Does vendor have SOC 2 certification? [ ] Yes [ ] No
2. Is data encrypted at rest and in transit? [ ] Yes [ ] No
3. Does vendor have incident response plan? [ ] Yes [ ] No
4. Does vendor carry cyber insurance? [ ] Yes [ ] No

RISK RATING
[ ] Low [ ] Medium [ ] High [ ] Critical

APPROVAL
Approver: _______________
Date: _______________""",
                regulations=[Regulation.SOC2, Regulation.ISO27001],
                keywords=["vendor", "risk", "assessment", "third-party"],
                owner_id="U002",
            ),
        ]
        for doc in documents:
            self.documents[doc.id] = doc

        # Policy violations
        violations = [
            PolicyViolation(
                id="VIO-001",
                policy_id="DOC-001",
                description="Sensitive data shared via unencrypted email",
                severity=RiskLevel.HIGH,
                detected_at=datetime.now(),
                detected_by="U003",
                status="remediated",
                resolution="Employee retrained, email DLP policy implemented",
                resolved_at=datetime.now(),
            ),
        ]
        for vio in violations:
            self.violations[vio.id] = vio

        # Set default user
        self.current_user = self.users["U002"]

    # ──────────────────────────────────────────────────────────────────────────
    # COMPLIANCE CHECKING
    # ──────────────────────────────────────────────────────────────────────────

    def check_compliance(self, regulation: str = None, category: str = None) -> dict:
        """Check compliance status for requirements."""
        self._log_audit(
            AuditAction.SEARCH,
            "compliance_check",
            "*",
            f"Compliance check for regulation={regulation}, category={category}",
        )

        requirements = list(self.requirements.values())

        if regulation:
            try:
                reg = Regulation[regulation.upper()]
                requirements = [r for r in requirements if r.regulation == reg]
            except KeyError:
                return {"success": False, "error": f"Unknown regulation: {regulation}"}

        if category:
            requirements = [
                r for r in requirements if category.lower() in r.category.lower()
            ]

        results = []
        for req in requirements:
            # Find latest check for this requirement
            checks = [c for c in self.checks.values() if c.requirement_id == req.id]
            latest_check = max(checks, key=lambda c: c.checked_at) if checks else None

            results.append(
                {
                    "requirement_id": req.id,
                    "title": req.title,
                    "regulation": req.regulation.value,
                    "risk_level": req.risk_level.value,
                    "status": (
                        latest_check.status.value if latest_check else "not_assessed"
                    ),
                    "last_checked": (
                        latest_check.checked_at.isoformat() if latest_check else None
                    ),
                    "findings_count": len(latest_check.findings) if latest_check else 0,
                }
            )

        # Summary stats
        compliant = len([r for r in results if r["status"] == "compliant"])
        non_compliant = len([r for r in results if r["status"] == "non_compliant"])
        partial = len([r for r in results if r["status"] == "partial"])

        return {
            "success": True,
            "summary": {
                "total": len(results),
                "compliant": compliant,
                "non_compliant": non_compliant,
                "partial": partial,
                "not_assessed": len(results) - compliant - non_compliant - partial,
            },
            "requirements": results,
        }

    def get_requirement_details(self, requirement_id: str) -> dict:
        """Get detailed requirement information."""
        req = self.requirements.get(requirement_id)
        if not req:
            return {
                "success": False,
                "error": f"Requirement {requirement_id} not found",
            }

        self._log_audit(
            AuditAction.VIEW,
            "requirement",
            requirement_id,
            f"Viewed requirement: {req.title}",
        )

        # Get related checks
        checks = [c for c in self.checks.values() if c.requirement_id == requirement_id]
        latest = max(checks, key=lambda c: c.checked_at) if checks else None

        return {
            "success": True,
            "requirement": {
                "id": req.id,
                "regulation": req.regulation.value,
                "title": req.title,
                "description": req.description,
                "category": req.category,
                "risk_level": req.risk_level.value,
                "controls": req.controls,
                "evidence_required": req.evidence_required,
                "review_frequency": req.review_frequency,
            },
            "latest_check": (
                {
                    "id": latest.id,
                    "status": latest.status.value,
                    "checked_at": latest.checked_at.isoformat(),
                    "findings": latest.findings,
                    "recommendations": latest.recommendations,
                    "remediation_plan": latest.remediation_plan or None,
                }
                if latest
                else None
            ),
        }

    def run_compliance_assessment(
        self,
        requirement_id: str,
        findings: list,
        status: str,
        recommendations: list = None,
    ) -> dict:
        """Record a compliance assessment result."""
        if self.current_user.role not in [UserRole.COMPLIANCE, UserRole.ADMIN]:
            return {
                "success": False,
                "error": "Permission denied - compliance role required",
            }

        req = self.requirements.get(requirement_id)
        if not req:
            return {
                "success": False,
                "error": f"Requirement {requirement_id} not found",
            }

        try:
            comp_status = ComplianceStatus[status.upper()]
        except KeyError:
            return {"success": False, "error": f"Invalid status: {status}"}

        check_id = self._generate_id("CHK")
        check = ComplianceCheck(
            id=check_id,
            requirement_id=requirement_id,
            checked_at=datetime.now(),
            status=comp_status,
            findings=findings,
            risk_level=(
                req.risk_level
                if comp_status != ComplianceStatus.COMPLIANT
                else RiskLevel.LOW
            ),
            recommendations=recommendations or [],
            owner_id=self.current_user.id,
        )
        self.checks[check_id] = check

        self._log_audit(
            AuditAction.CREATE,
            "compliance_check",
            check_id,
            f"Compliance assessment: {req.title} = {status}",
        )

        return {
            "success": True,
            "check_id": check_id,
            "requirement": req.title,
            "status": comp_status.value,
            "message": f"Compliance assessment recorded for {req.title}",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # CONTRACT CLAUSES
    # ──────────────────────────────────────────────────────────────────────────

    def search_clauses(self, clause_type: str = None, query: str = None) -> dict:
        """Search contract clauses."""
        self._log_audit(
            AuditAction.SEARCH,
            "contract_clause",
            "*",
            f"Clause search: type={clause_type}, query={query}",
        )

        clauses = list(self.clauses.values())

        if clause_type:
            try:
                ct = ClauseType[clause_type.upper()]
                clauses = [c for c in clauses if c.clause_type == ct]
            except KeyError:
                # Try partial match
                clauses = [
                    c
                    for c in clauses
                    if clause_type.lower() in c.clause_type.value.lower()
                ]

        if query:
            query_lower = query.lower()
            clauses = [
                c
                for c in clauses
                if query_lower in c.title.lower()
                or query_lower in c.standard_text.lower()
            ]

        return {
            "success": True,
            "count": len(clauses),
            "clauses": [
                {
                    "id": c.id,
                    "type": c.clause_type.value,
                    "title": c.title,
                    "required": c.required,
                    "negotiable": c.negotiable,
                    "preview": c.standard_text[:150] + "...",
                }
                for c in clauses
            ],
        }

    def get_clause(self, clause_id: str) -> dict:
        """Get full contract clause with guidance."""
        clause = self.clauses.get(clause_id)
        if not clause:
            return {"success": False, "error": f"Clause {clause_id} not found"}

        self._log_audit(
            AuditAction.VIEW,
            "contract_clause",
            clause_id,
            f"Viewed clause: {clause.title}",
        )

        return {
            "success": True,
            "clause": {
                "id": clause.id,
                "type": clause.clause_type.value,
                "title": clause.title,
                "standard_text": clause.standard_text,
                "risk_notes": clause.risk_notes,
                "required": clause.required,
                "negotiable": clause.negotiable,
                "alternatives": clause.alternatives,
            },
        }

    def get_contract_template(self, clause_types: list) -> dict:
        """Generate contract template with requested clauses."""
        if self.current_user.role not in [UserRole.LEGAL, UserRole.ADMIN]:
            return {
                "success": False,
                "error": "Permission denied - legal role required",
            }

        template_clauses = []
        missing = []

        for ct_str in clause_types:
            try:
                ct = ClauseType[ct_str.upper()]
                matching = [c for c in self.clauses.values() if c.clause_type == ct]
                if matching:
                    template_clauses.append(matching[0])
                else:
                    missing.append(ct_str)
            except KeyError:
                missing.append(ct_str)

        self._log_audit(
            AuditAction.EXPORT,
            "contract_template",
            "*",
            f"Generated template with {len(template_clauses)} clauses",
        )

        return {
            "success": True,
            "template": {
                "clauses": [
                    {
                        "type": c.clause_type.value,
                        "title": c.title,
                        "text": c.standard_text,
                        "notes": c.risk_notes,
                    }
                    for c in template_clauses
                ],
                "missing_types": missing,
            },
            "total_clauses": len(template_clauses),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # DOCUMENT MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def search_documents(
        self,
        query: str = None,
        doc_type: str = None,
        classification: str = None,
        regulation: str = None,
    ) -> dict:
        """Search legal and compliance documents."""
        self._log_audit(
            AuditAction.SEARCH, "document", "*", f"Document search: query={query}"
        )

        documents = list(self.documents.values())

        if doc_type:
            try:
                dt = DocumentType[doc_type.upper()]
                documents = [d for d in documents if d.doc_type == dt]
            except KeyError:
                pass

        if classification:
            documents = [
                d
                for d in documents
                if d.classification.lower() == classification.lower()
            ]

        if regulation:
            try:
                reg = Regulation[regulation.upper()]
                documents = [d for d in documents if reg in d.regulations]
            except KeyError:
                pass

        if query:
            query_lower = query.lower()
            results = []
            for doc in documents:
                score = 0
                if query_lower in doc.title.lower():
                    score += 10
                if query_lower in doc.content_preview.lower():
                    score += 5
                for kw in doc.keywords:
                    if query_lower in kw.lower():
                        score += 3
                if score > 0:
                    results.append((doc, score))
            results.sort(key=lambda x: x[1], reverse=True)
            documents = [d for d, _ in results]

        return {
            "success": True,
            "count": len(documents),
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "type": d.doc_type.value,
                    "classification": d.classification,
                    "preview": d.content_preview,
                    "regulations": [r.value for r in d.regulations],
                    "updated_at": d.updated_at.isoformat(),
                }
                for d in documents
            ],
        }

    def get_document(self, document_id: str) -> dict:
        """Get full document content."""
        doc = self.documents.get(document_id)
        if not doc:
            return {"success": False, "error": f"Document {document_id} not found"}

        # Check classification access
        if doc.classification == "restricted":
            if self.current_user.role not in [
                UserRole.LEGAL,
                UserRole.COMPLIANCE,
                UserRole.ADMIN,
            ]:
                self._log_audit(
                    AuditAction.VIEW,
                    "document",
                    document_id,
                    "Access denied - restricted document",
                    success=False,
                )
                return {
                    "success": False,
                    "error": "Access denied - restricted document",
                }

        self._log_audit(
            AuditAction.VIEW, "document", document_id, f"Viewed document: {doc.title}"
        )

        return {
            "success": True,
            "document": {
                "id": doc.id,
                "title": doc.title,
                "type": doc.doc_type.value,
                "classification": doc.classification,
                "content": doc.full_text,
                "regulations": [r.value for r in doc.regulations],
                "keywords": doc.keywords,
                "version": doc.version,
                "retention_period": doc.retention_period,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat(),
            },
        }

    def classify_document(self, title: str, content: str) -> dict:
        """Classify a document based on content analysis."""
        self._log_audit(
            AuditAction.CREATE,
            "classification",
            "*",
            f"Document classification requested: {title[:50]}",
        )

        content_lower = content.lower()

        # Determine document type
        type_indicators = {
            DocumentType.CONTRACT: [
                "agreement",
                "parties",
                "whereas",
                "terms and conditions",
            ],
            DocumentType.POLICY: [
                "policy",
                "must",
                "shall",
                "compliance",
                "requirements",
            ],
            DocumentType.PROCEDURE: ["procedure", "step", "process", "workflow"],
            DocumentType.REGULATION: ["regulation", "law", "statute", "act of"],
            DocumentType.TEMPLATE: ["template", "fill in", "___", "sample"],
        }

        doc_type = DocumentType.GUIDELINE  # default
        best_score = 0
        for dtype, indicators in type_indicators.items():
            score = sum(1 for i in indicators if i in content_lower)
            if score > best_score:
                best_score = score
                doc_type = dtype

        # Determine classification level
        sensitive_terms = [
            "confidential",
            "proprietary",
            "trade secret",
            "internal only",
        ]
        restricted_terms = [
            "restricted",
            "top secret",
            "classified",
            "highly sensitive",
        ]

        if any(term in content_lower for term in restricted_terms):
            classification = "restricted"
        elif any(term in content_lower for term in sensitive_terms):
            classification = "confidential"
        elif "internal" in content_lower:
            classification = "internal"
        else:
            classification = "public"

        # Detect applicable regulations
        detected_regs = []
        reg_indicators = {
            Regulation.GDPR: ["gdpr", "personal data", "data subject", "european"],
            Regulation.CCPA: ["ccpa", "california", "consumer privacy"],
            Regulation.SOX: ["sox", "sarbanes", "financial reporting"],
            Regulation.HIPAA: ["hipaa", "health information", "phi", "medical"],
            Regulation.PCI_DSS: ["pci", "cardholder", "payment card"],
        }

        for reg, indicators in reg_indicators.items():
            if any(ind in content_lower for ind in indicators):
                detected_regs.append(reg.value)

        return {
            "success": True,
            "classification": {
                "document_type": doc_type.value,
                "sensitivity": classification,
                "applicable_regulations": detected_regs,
                "retention_recommendation": (
                    "7 years"
                    if classification in ["confidential", "restricted"]
                    else "3 years"
                ),
                "review_frequency": "annual" if detected_regs else "biennial",
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # AUDIT TRAIL
    # ──────────────────────────────────────────────────────────────────────────

    def get_audit_trail(
        self,
        resource_type: str = None,
        resource_id: str = None,
        user_id: str = None,
        limit: int = 50,
    ) -> dict:
        """Get audit trail for compliance reporting."""
        if self.current_user.role not in [UserRole.COMPLIANCE, UserRole.ADMIN]:
            return {
                "success": False,
                "error": "Permission denied - compliance role required",
            }

        logs = self.audit_logs.copy()

        if resource_type:
            logs = [l for l in logs if l.resource_type == resource_type]

        if resource_id:
            logs = [l for l in logs if l.resource_id == resource_id]

        if user_id:
            logs = [l for l in logs if l.user_id == user_id]

        # Sort by timestamp descending
        logs.sort(key=lambda l: l.timestamp, reverse=True)
        logs = logs[:limit]

        return {
            "success": True,
            "count": len(logs),
            "audit_trail": [
                {
                    "id": l.id,
                    "timestamp": l.timestamp.isoformat(),
                    "user": (
                        self.users[l.user_id].name
                        if l.user_id in self.users
                        else l.user_id
                    ),
                    "action": l.action.value,
                    "resource_type": l.resource_type,
                    "resource_id": l.resource_id,
                    "details": l.details,
                    "success": l.success,
                }
                for l in logs
            ],
        }

    def export_audit_report(self, start_date: str = None, end_date: str = None) -> dict:
        """Export audit report for compliance purposes."""
        if self.current_user.role not in [UserRole.COMPLIANCE, UserRole.ADMIN]:
            return {
                "success": False,
                "error": "Permission denied - compliance role required",
            }

        logs = self.audit_logs.copy()

        if start_date:
            start = datetime.fromisoformat(start_date)
            logs = [l for l in logs if l.timestamp >= start]

        if end_date:
            end = datetime.fromisoformat(end_date)
            logs = [l for l in logs if l.timestamp <= end]

        # Generate hash for integrity
        log_str = json.dumps(
            [
                {
                    "id": l.id,
                    "ts": l.timestamp.isoformat(),
                    "action": l.action.value,
                    "details": l.details,
                }
                for l in logs
            ],
            sort_keys=True,
        )
        integrity_hash = hashlib.sha256(log_str.encode()).hexdigest()[:16]

        self._log_audit(
            AuditAction.EXPORT,
            "audit_report",
            "*",
            f"Exported {len(logs)} audit records",
        )

        return {
            "success": True,
            "report": {
                "generated_at": datetime.now().isoformat(),
                "generated_by": self.current_user.name,
                "record_count": len(logs),
                "integrity_hash": integrity_hash,
                "date_range": {"start": start_date or "all", "end": end_date or "all"},
                "summary_by_action": {
                    action.value: len([l for l in logs if l.action == action])
                    for action in AuditAction
                },
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # USER MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def switch_user(self, user_id: str) -> dict:
        """Switch current user context (for demo)."""
        user = self.users.get(user_id)
        if not user:
            return {"success": False, "error": f"User {user_id} not found"}

        self.current_user = user
        return {
            "success": True,
            "message": f"Switched to: {user.name}",
            "role": user.role.value,
            "department": user.department,
        }

    def get_dashboard(self) -> dict:
        """Get compliance dashboard."""
        # Compliance summary
        total_reqs = len(self.requirements)
        compliant = len(
            [c for c in self.checks.values() if c.status == ComplianceStatus.COMPLIANT]
        )

        # Risk summary
        high_risk = len(
            [
                r
                for r in self.requirements.values()
                if r.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            ]
        )

        # Recent audit activity
        recent_logs = sorted(self.audit_logs, key=lambda l: l.timestamp, reverse=True)[
            :5
        ]

        return {
            "success": True,
            "dashboard": {
                "compliance_score": (
                    f"{(compliant / total_reqs * 100):.0f}%" if total_reqs else "N/A"
                ),
                "total_requirements": total_reqs,
                "compliant": compliant,
                "high_risk_items": high_risk,
                "open_violations": len(
                    [v for v in self.violations.values() if v.status == "open"]
                ),
                "documents_count": len(self.documents),
                "recent_activity": [
                    {
                        "action": l.action.value,
                        "resource": l.resource_type,
                        "when": l.timestamp.strftime("%Y-%m-%d %H:%M"),
                    }
                    for l in recent_logs
                ],
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Legal & Compliance Assistant for an enterprise organization.

Your role is to:
1. Help check compliance status against regulatory requirements
2. Provide contract clause guidance and templates
3. Search and retrieve legal documents and policies
4. Maintain audit trails for all compliance activities
5. Classify documents and assess risks

You have access to these tools:
- check_compliance: Check compliance status for regulations
- get_requirement_details: Get detailed requirement information
- run_compliance_assessment: Record assessment results (compliance role only)
- search_clauses: Search contract clause library
- get_clause: Get full clause with guidance
- get_contract_template: Generate template with clauses
- search_documents: Search document repository
- get_document: Get full document content
- classify_document: Classify a document
- get_audit_trail: View audit history (compliance role only)
- export_audit_report: Generate audit report (compliance role only)
- get_dashboard: View compliance dashboard

Always maintain professional confidentiality. All actions are logged for audit purposes. Only provide information the user is authorized to access based on their role."""


# ══════════════════════════════════════════════════════════════════════════════
# AGENT TOOLS
# ══════════════════════════════════════════════════════════════════════════════


def create_legal_tools(service: LegalComplianceService) -> list:
    """Create tool definitions for the legal/compliance agent."""
    return [
        {
            "name": "check_compliance",
            "description": "Check compliance status for regulatory requirements",
            "parameters": {
                "type": "object",
                "properties": {
                    "regulation": {
                        "type": "string",
                        "description": "Filter by regulation: GDPR, SOX, PCI_DSS, SOC2, etc.",
                    },
                    "category": {"type": "string", "description": "Filter by category"},
                },
            },
            "function": lambda regulation=None, category=None: service.check_compliance(
                regulation, category
            ),
        },
        {
            "name": "get_requirement_details",
            "description": "Get detailed information about a compliance requirement",
            "parameters": {
                "type": "object",
                "properties": {
                    "requirement_id": {
                        "type": "string",
                        "description": "Requirement ID",
                    }
                },
                "required": ["requirement_id"],
            },
            "function": lambda requirement_id: service.get_requirement_details(
                requirement_id
            ),
        },
        {
            "name": "search_clauses",
            "description": "Search contract clause library",
            "parameters": {
                "type": "object",
                "properties": {
                    "clause_type": {
                        "type": "string",
                        "description": "Type: confidentiality, indemnification, data_protection, etc.",
                    },
                    "query": {"type": "string", "description": "Search text"},
                },
            },
            "function": lambda clause_type=None, query=None: service.search_clauses(
                clause_type, query
            ),
        },
        {
            "name": "get_clause",
            "description": "Get full contract clause with guidance",
            "parameters": {
                "type": "object",
                "properties": {
                    "clause_id": {"type": "string", "description": "Clause ID"}
                },
                "required": ["clause_id"],
            },
            "function": lambda clause_id: service.get_clause(clause_id),
        },
        {
            "name": "search_documents",
            "description": "Search legal and compliance documents",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "doc_type": {"type": "string", "description": "Document type"},
                    "classification": {
                        "type": "string",
                        "description": "Classification level",
                    },
                    "regulation": {
                        "type": "string",
                        "description": "Related regulation",
                    },
                },
            },
            "function": lambda query=None, doc_type=None, classification=None, regulation=None: service.search_documents(
                query, doc_type, classification, regulation
            ),
        },
        {
            "name": "get_document",
            "description": "Get full document content",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Document ID"}
                },
                "required": ["document_id"],
            },
            "function": lambda document_id: service.get_document(document_id),
        },
        {
            "name": "classify_document",
            "description": "Classify a document based on content",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Document title"},
                    "content": {"type": "string", "description": "Document content"},
                },
                "required": ["title", "content"],
            },
            "function": lambda title, content: service.classify_document(
                title, content
            ),
        },
        {
            "name": "get_audit_trail",
            "description": "Get audit trail (compliance role only)",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "description": "Filter by resource type",
                    },
                    "resource_id": {
                        "type": "string",
                        "description": "Filter by resource ID",
                    },
                    "user_id": {"type": "string", "description": "Filter by user"},
                    "limit": {"type": "integer", "description": "Max records"},
                },
            },
            "function": lambda resource_type=None, resource_id=None, user_id=None, limit=50: service.get_audit_trail(
                resource_type, resource_id, user_id, limit
            ),
        },
        {
            "name": "get_dashboard",
            "description": "Get compliance dashboard overview",
            "parameters": {"type": "object", "properties": {}},
            "function": lambda: service.get_dashboard(),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# DEMO AND INTERACTIVE MODES
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate legal/compliance capabilities."""
    print("=" * 70)
    print("LEGAL & COMPLIANCE ASSISTANT - DEMO MODE")
    print("=" * 70)

    service = LegalComplianceService()

    # Dashboard
    print("\n📊 COMPLIANCE DASHBOARD")
    print("-" * 50)
    dashboard = service.get_dashboard()
    d = dashboard["dashboard"]
    print(f"Compliance Score: {d['compliance_score']}")
    print(f"Total Requirements: {d['total_requirements']}")
    print(f"Compliant: {d['compliant']}")
    print(f"High Risk Items: {d['high_risk_items']}")

    # Compliance check
    print("\n🔍 GDPR COMPLIANCE CHECK")
    print("-" * 50)
    gdpr = service.check_compliance(regulation="GDPR")
    print(f"Summary: {gdpr['summary']}")
    for req in gdpr["requirements"]:
        print(f"  [{req['status'].upper()}] {req['title']}")

    # Contract clauses
    print("\n📜 CONTRACT CLAUSE SEARCH: 'data protection'")
    print("-" * 50)
    clauses = service.search_clauses(clause_type="data_protection")
    for clause in clauses["clauses"]:
        print(f"  [{clause['id']}] {clause['title']}")
        print(
            f"      Required: {clause['required']}, Negotiable: {clause['negotiable']}"
        )

    # Full clause
    print("\n📋 CLAUSE DETAILS: CL-003")
    print("-" * 50)
    clause = service.get_clause("CL-003")
    c = clause["clause"]
    print(f"Title: {c['title']}")
    print(f"Text: {c['standard_text'][:200]}...")
    print(f"Risk Notes: {c['risk_notes']}")

    # Document search
    print("\n📁 DOCUMENT SEARCH: 'security policy'")
    print("-" * 50)
    docs = service.search_documents(query="security policy")
    for doc in docs["documents"]:
        print(f"  [{doc['id']}] {doc['title']} ({doc['type']})")

    # Document classification
    print("\n🏷️ DOCUMENT CLASSIFICATION")
    print("-" * 50)
    sample_text = """This agreement contains confidential proprietary information 
    related to GDPR compliance and personal data processing. The parties agree 
    to maintain strict confidentiality of all trade secrets."""
    classification = service.classify_document("Sample Agreement", sample_text)
    c = classification["classification"]
    print(f"Type: {c['document_type']}")
    print(f"Sensitivity: {c['sensitivity']}")
    print(f"Regulations: {c['applicable_regulations']}")

    # Audit trail (switch to compliance role)
    print("\n📝 AUDIT TRAIL (Compliance View)")
    print("-" * 50)
    service.switch_user("U003")  # Compliance officer
    audit = service.get_audit_trail(limit=5)
    for entry in audit["audit_trail"]:
        print(
            f"  {entry['timestamp']}: {entry['user']} - {entry['action']} {entry['resource_type']}"
        )

    print("\n" + "=" * 70)
    print("Demo complete! Run with --interactive for full chat mode.")
    print("=" * 70)


async def interactive():
    """Run interactive legal/compliance chat."""
    print("=" * 70)
    print("LEGAL & COMPLIANCE ASSISTANT")
    print("=" * 70)
    print("\nWelcome! I can help you with:")
    print("  • Compliance status checking")
    print("  • Contract clause lookup and guidance")
    print("  • Document search and classification")
    print("  • Audit trail review")
    print("\nType 'quit' to exit, 'demo' for demo mode.\n")

    service = LegalComplianceService()
    tools = create_legal_tools(service)

    try:
        from agentic_brain import Agent

        agent = Agent(system_prompt=SYSTEM_PROMPT, tools=tools, model="gpt-4")
        use_agent = True
    except ImportError:
        print("Note: agentic-brain not installed. Running in simple mode.\n")
        use_agent = False

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("\nThank you. Goodbye!")
                break

            if user_input.lower() == "demo":
                await demo()
                continue

            if user_input.lower() == "dashboard":
                result = service.get_dashboard()
                print(f"\n🤖 Assistant: {json.dumps(result, indent=2)}")
                continue

            if use_agent:
                response = await agent.chat(user_input)
                print(f"\n🤖 Assistant: {response}")
            else:
                print("\n🤖 Assistant: Legal/compliance query received.")
                print("   Quick commands: 'dashboard', 'demo'")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(demo())


if __name__ == "__main__":
    main()
