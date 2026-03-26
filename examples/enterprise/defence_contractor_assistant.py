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
AUKUS Defence Contractor Chatbot for Australian Markets.

An enterprise AI assistant for defence contractors operating within
AUKUS (Australia, UK, US) submarine and technology programs:

- AGSVA security clearance verification patterns
- PSPF (Protective Security Policy Framework) classification handling
- Need-to-know access control with compartmented information
- Air-gapped deployment ready (offline-first architecture)
- ITAR/EAR export control awareness
- Secure document lifecycle management

Key Australian Defence Context:
    - AGSVA (Australian Government Security Vetting Agency) clearance levels
    - PSPF classification markings (OFFICIAL, PROTECTED, SECRET, TOP SECRET)
    - Defence Security Principles Framework compliance
    - AUKUS information sharing protocols

Architecture (Air-Gapped):
    ┌──────────────────────────────────────────────────────────────────┐
    │                    AIR-GAPPED SECURE ENCLAVE                      │
    │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
    │  │  Ollama  │  │   SQLite     │  │  Defence Assistant Agent   │  │
    │  │ (Local)  │◄─┤  (Encrypted) │◄─┤  (This Application)        │  │
    │  └──────────┘  └──────────────┘  └────────────────────────────┘  │
    │       ▲              ▲                      ▲                     │
    │       │              │                      │                     │
    │       └──────────────┴──────────────────────┘                     │
    │              ALL DATA STAYS LOCAL                                 │
    │              NO NETWORK CONNECTIONS                               │
    └──────────────────────────────────────────────────────────────────┘
                            ╳
                    NO EXTERNAL NETWORK

IMPORTANT DISCLAIMERS:
    ⚠️  This is a DEMONSTRATION system only
    ⚠️  NOT for actual classified information handling
    ⚠️  NOT an official Australian Government system
    ⚠️  Consult AGSVA and Defence Security for real requirements
    ⚠️  ITAR/EAR compliance requires legal review

Usage:
    python examples/enterprise/defence_contractor_assistant.py
    python examples/enterprise/defence_contractor_assistant.py --clearance nv1
    python examples/enterprise/defence_contractor_assistant.py --demo

Requirements:
    pip install agentic-brain
    ollama pull llama3.1:8b  # Local LLM (air-gapped)
"""

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import IntEnum, Enum
from pathlib import Path
from typing import Any, Optional

from agentic_brain.auth import (
    AuthProvider,
    JWTAuth,
    AuthConfig,
    require_role,
    require_authority,
    current_user,
    User,
    Token,
)

# =============================================================================
# LOGGING - Tamper-evident with hash chaining
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("defence.aukus_assistant")


# =============================================================================
# AGSVA SECURITY CLEARANCE LEVELS
# =============================================================================


class AGSVAClearance(IntEnum):
    """
    Australian Government Security Vetting Agency (AGSVA) clearance levels.

    These levels determine access to classified information under PSPF.
    Each level requires specific vetting and ongoing security obligations.
    """

    BASELINE = 0  # Baseline Vetting - access to OFFICIAL resources
    NV1 = 1  # Negative Vetting Level 1 - access to PROTECTED
    NV2 = 2  # Negative Vetting Level 2 - access to SECRET
    PV = 3  # Positive Vetting - access to TOP SECRET
    PV_CODEWORD = 4  # PV with codeword access - compartmented info


class PSPFClassification(IntEnum):
    """
    Protective Security Policy Framework (PSPF) classification levels.

    Australian Government information classification marking scheme.
    """

    UNOFFICIAL = 0  # Not official government information
    OFFICIAL = 1  # Low business impact if compromised
    OFFICIAL_SENSITIVE = 2  # Requires careful handling
    PROTECTED = 3  # Could cause damage to national interest
    SECRET = 4  # Could cause serious damage
    TOP_SECRET = 5  # Could cause exceptionally grave damage


class AUKUSCaveat(str, Enum):
    """AUKUS-specific information caveats and markings."""

    AUKUS = "AUKUS"  # AUKUS partner shareable
    AUKUS_NUCLEAR = "AUKUS-NUCLEAR"  # Nuclear propulsion related
    AUKUS_TECH = "AUKUS-TECH"  # Advanced technology sharing
    REL_AUS_USA_GBR = "REL AUS/USA/GBR"  # Releasable to partners
    NOFORN = "NOFORN"  # Not releasable to foreign nationals
    AUSTEO = "AUSTEO"  # Australian Eyes Only
    AGAO = "AGAO"  # Australian Government Access Only


# =============================================================================
# SECURITY OFFICER MODEL
# =============================================================================


@dataclass
class SecurityOfficer:
    """Represents a user with security clearance."""

    employee_id: str
    name: str
    clearance_level: AGSVAClearance
    clearance_expiry: datetime
    codeword_access: list[str] = field(default_factory=list)
    need_to_know_compartments: list[str] = field(default_factory=list)
    nationality: str = "AUS"
    dual_nationality: bool = False
    security_briefings: list[str] = field(default_factory=list)
    last_security_review: Optional[datetime] = None

    def has_clearance_for(self, classification: PSPFClassification) -> bool:
        """Check if officer has sufficient clearance for classification."""
        if self.clearance_expiry < datetime.now(timezone.utc):
            return False

        clearance_map = {
            AGSVAClearance.BASELINE: PSPFClassification.OFFICIAL,
            AGSVAClearance.NV1: PSPFClassification.PROTECTED,
            AGSVAClearance.NV2: PSPFClassification.SECRET,
            AGSVAClearance.PV: PSPFClassification.TOP_SECRET,
            AGSVAClearance.PV_CODEWORD: PSPFClassification.TOP_SECRET,
        }

        max_allowed = clearance_map.get(
            self.clearance_level, PSPFClassification.UNOFFICIAL
        )
        return classification <= max_allowed

    def has_need_to_know(self, compartment: str) -> bool:
        """Verify need-to-know for a specific compartment."""
        return compartment.upper() in [
            c.upper() for c in self.need_to_know_compartments
        ]

    def has_codeword_access(self, codeword: str) -> bool:
        """Check codeword access."""
        return codeword.upper() in [c.upper() for c in self.codeword_access]


# =============================================================================
# CLASSIFIED DOCUMENT MODEL
# =============================================================================


@dataclass
class ClassifiedDocument:
    """Represents a classified document with PSPF markings."""

    document_id: str
    title: str
    classification: PSPFClassification
    caveats: list[str] = field(default_factory=list)
    compartments: list[str] = field(default_factory=list)
    codewords: list[str] = field(default_factory=list)
    originator: str = ""
    created_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    review_date: Optional[datetime] = None
    destruction_date: Optional[datetime] = None
    content_hash: str = ""
    access_log: list[dict] = field(default_factory=list)

    def format_classification_banner(self) -> str:
        """Format the document classification banner."""
        parts = [self.classification.name]

        if self.caveats:
            parts.extend(self.caveats)

        if self.codewords:
            parts.append("//" + "/".join(self.codewords))

        return " // ".join(parts)

    def can_access(self, officer: SecurityOfficer) -> tuple[bool, str]:
        """
        Check if an officer can access this document.

        Returns tuple of (allowed, reason).
        """
        # Check classification level
        if not officer.has_clearance_for(self.classification):
            return False, f"Insufficient clearance for {self.classification.name}"

        # Check codewords
        for codeword in self.codewords:
            if not officer.has_codeword_access(codeword):
                return False, f"No codeword access for {codeword}"

        # Check compartments (need-to-know)
        for compartment in self.compartments:
            if not officer.has_need_to_know(compartment):
                return False, f"No need-to-know for compartment {compartment}"

        # Check AUSTEO for non-AUS nationals
        if AUKUSCaveat.AUSTEO.value in self.caveats:
            if officer.nationality != "AUS":
                return False, "AUSTEO: Australian Eyes Only"

        # Check NOFORN for non-Australian nationals
        if AUKUSCaveat.NOFORN.value in self.caveats:
            if officer.dual_nationality:
                return False, "NOFORN: No dual nationals"

        return True, "Access granted"


# =============================================================================
# SECURE AUDIT LOG (Hash-Chained)
# =============================================================================


class SecureAuditLog:
    """
    Tamper-evident audit log with hash chaining.

    Each log entry includes a hash of the previous entry,
    making tampering detectable.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the secure audit log."""
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self._last_hash = "GENESIS"

    def _create_tables(self):
        """Create audit log tables."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_clearance TEXT,
                document_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                previous_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL
            )
        """
        )
        self.conn.commit()

    def _compute_hash(self, entry: dict) -> str:
        """Compute hash for an audit entry."""
        entry_str = json.dumps(entry, sort_keys=True)
        return hashlib.sha256(entry_str.encode()).hexdigest()

    def log_access(
        self,
        actor: SecurityOfficer,
        document: ClassifiedDocument,
        action: str,
        result: str,
        details: str = "",
    ):
        """Log a document access attempt."""
        timestamp = datetime.now(timezone.utc).isoformat()

        entry = {
            "timestamp": timestamp,
            "event_type": "DOCUMENT_ACCESS",
            "actor_id": actor.employee_id,
            "actor_clearance": actor.clearance_level.name,
            "document_id": document.document_id,
            "document_classification": document.classification.name,
            "action": action,
            "result": result,
            "details": details,
            "previous_hash": self._last_hash,
        }

        entry_hash = self._compute_hash(entry)

        self.conn.execute(
            """
            INSERT INTO audit_log 
            (timestamp, event_type, actor_id, actor_clearance, document_id, 
             action, details, previous_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                timestamp,
                "DOCUMENT_ACCESS",
                actor.employee_id,
                actor.clearance_level.name,
                document.document_id,
                action,
                json.dumps({"result": result, "details": details}),
                self._last_hash,
                entry_hash,
            ),
        )
        self.conn.commit()

        self._last_hash = entry_hash
        logger.info(
            f"AUDIT: {actor.employee_id} ({actor.clearance_level.name}) "
            f"{action} {document.document_id} [{document.classification.name}] "
            f"-> {result}"
        )

    def verify_chain_integrity(self) -> bool:
        """Verify the audit log has not been tampered with."""
        cursor = self.conn.execute("SELECT * FROM audit_log ORDER BY id ASC")

        expected_previous = "GENESIS"

        for row in cursor:
            entry = {
                "timestamp": row[1],
                "event_type": row[2],
                "actor_id": row[3],
                "actor_clearance": row[4],
                "document_id": row[5],
                "action": row[6],
                "details": row[7],
                "previous_hash": row[8],
            }

            if entry["previous_hash"] != expected_previous:
                logger.error(f"CHAIN BREAK: Entry {row[0]} has invalid previous hash")
                return False

            expected_previous = row[9]  # entry_hash

        logger.info("AUDIT CHAIN: Integrity verified ✓")
        return True


# =============================================================================
# DEFENCE ASSISTANT CHATBOT
# =============================================================================


class DefenceContractorAssistant:
    """
    AI Assistant for AUKUS Defence Contractors.

    Handles document queries, access control, and compliance
    in an air-gapped environment.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the defence contractor assistant."""
        self.audit_log = SecureAuditLog(db_path)
        self.current_officer: Optional[SecurityOfficer] = None
        self.documents: dict[str, ClassifiedDocument] = {}
        self._load_demo_documents()

    def _load_demo_documents(self):
        """Load demonstration documents for testing."""
        self.documents = {
            "DOC-001": ClassifiedDocument(
                document_id="DOC-001",
                title="AUKUS Submarine Program Overview",
                classification=PSPFClassification.PROTECTED,
                caveats=[AUKUSCaveat.AUKUS.value, AUKUSCaveat.REL_AUS_USA_GBR.value],
                compartments=["AUKUS-SUB"],
                originator="Defence Strategic Policy",
            ),
            "DOC-002": ClassifiedDocument(
                document_id="DOC-002",
                title="Nuclear Propulsion Technical Specifications",
                classification=PSPFClassification.SECRET,
                caveats=[AUKUSCaveat.AUKUS_NUCLEAR.value],
                codewords=["NAVIGATOR"],
                compartments=["AUKUS-SUB", "NUCLEAR-PROP"],
                originator="Naval Group",
            ),
            "DOC-003": ClassifiedDocument(
                document_id="DOC-003",
                title="Australian Sovereign Capability Assessment",
                classification=PSPFClassification.SECRET,
                caveats=[AUKUSCaveat.AUSTEO.value],
                compartments=["SOVEREIGN-CAP"],
                originator="Defence Industry Policy",
            ),
            "DOC-004": ClassifiedDocument(
                document_id="DOC-004",
                title="Contractor Safety Procedures",
                classification=PSPFClassification.OFFICIAL,
                originator="WHS Division",
            ),
        }

    def authenticate(self, officer: SecurityOfficer) -> bool:
        """
        Authenticate a security officer.

        In production, this would verify against AGSVA/DISP systems.
        """
        # Check clearance validity
        if officer.clearance_expiry < datetime.now(timezone.utc):
            logger.warning(f"EXPIRED CLEARANCE: {officer.employee_id}")
            return False

        # In production: verify against DISP/AGSVA
        self.current_officer = officer
        logger.info(
            f"AUTHENTICATED: {officer.name} ({officer.employee_id}) "
            f"Clearance: {officer.clearance_level.name}"
        )
        return True

    def request_document(self, document_id: str) -> tuple[bool, str, Optional[str]]:
        """
        Request access to a classified document.

        Returns:
            Tuple of (success, message, document_title)
        """
        if not self.current_officer:
            return False, "Not authenticated", None

        document = self.documents.get(document_id)
        if not document:
            return False, f"Document {document_id} not found", None

        # Check access
        allowed, reason = document.can_access(self.current_officer)

        # Audit the attempt
        self.audit_log.log_access(
            actor=self.current_officer,
            document=document,
            action="VIEW_REQUEST",
            result="GRANTED" if allowed else "DENIED",
            details=reason,
        )

        if allowed:
            banner = document.format_classification_banner()
            return True, f"Access granted. Banner: {banner}", document.title
        else:
            return False, f"Access denied: {reason}", None

    def list_accessible_documents(self) -> list[dict]:
        """List all documents the current officer can access."""
        if not self.current_officer:
            return []

        accessible = []
        for doc_id, doc in self.documents.items():
            allowed, _ = doc.can_access(self.current_officer)
            if allowed:
                accessible.append(
                    {
                        "document_id": doc_id,
                        "title": doc.title,
                        "classification": doc.classification.name,
                        "banner": doc.format_classification_banner(),
                    }
                )

        return accessible

    def check_export_control(self, document_id: str, destination: str) -> dict:
        """
        Check ITAR/EAR export control requirements.

        Returns export control assessment for the document.
        """
        document = self.documents.get(document_id)
        if not document:
            return {"allowed": False, "reason": "Document not found"}

        # AUKUS partners
        aukus_partners = ["AUS", "USA", "GBR"]

        result = {
            "document_id": document_id,
            "destination": destination,
            "allowed": False,
            "restrictions": [],
            "requirements": [],
        }

        # Check NOFORN
        if AUKUSCaveat.NOFORN.value in document.caveats:
            result["restrictions"].append("NOFORN: No foreign release")
            return result

        # Check AUSTEO
        if AUKUSCaveat.AUSTEO.value in document.caveats:
            if destination != "AUS":
                result["restrictions"].append("AUSTEO: Australian release only")
                return result

        # Check REL markings
        if AUKUSCaveat.REL_AUS_USA_GBR.value in document.caveats:
            if destination in aukus_partners:
                result["allowed"] = True
                result["requirements"].append(
                    "Follow AUKUS information sharing protocols"
                )
            else:
                result["restrictions"].append(
                    f"Not releasable to {destination} under current caveats"
                )
                return result

        # Nuclear propulsion requires special handling
        if AUKUSCaveat.AUKUS_NUCLEAR.value in document.caveats:
            result["requirements"].extend(
                [
                    "ITAR Category XI compliance required",
                    "Nuclear non-proliferation treaty obligations apply",
                    "Requires NNSA approval for US-origin data",
                ]
            )

        return result

    def generate_security_briefing(self) -> str:
        """Generate a security briefing for the current officer."""
        if not self.current_officer:
            return "Not authenticated"

        officer = self.current_officer
        accessible_docs = self.list_accessible_documents()

        briefing = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         SECURITY BRIEFING                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Officer: {officer.name:<58}  ║
║  Employee ID: {officer.employee_id:<54}  ║
║  Clearance: {officer.clearance_level.name:<56}  ║
║  Clearance Expiry: {officer.clearance_expiry.strftime('%Y-%m-%d'):<49}  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  NEED-TO-KNOW COMPARTMENTS:                                                   ║"""

        for compartment in officer.need_to_know_compartments:
            briefing += f"\n║    • {compartment:<64}  ║"

        if officer.codeword_access:
            briefing += """
╠══════════════════════════════════════════════════════════════════════════════╣
║  CODEWORD ACCESS:                                                             ║"""
            for codeword in officer.codeword_access:
                briefing += f"\n║    • {codeword:<64}  ║"

        briefing += f"""
╠══════════════════════════════════════════════════════════════════════════════╣
║  ACCESSIBLE DOCUMENTS: {len(accessible_docs):<52}  ║"""

        for doc in accessible_docs[:5]:  # Show first 5
            briefing += (
                f"\n║    [{doc['classification'][:3]}] {doc['title'][:54]:<54}  ║"
            )

        briefing += """
╠══════════════════════════════════════════════════════════════════════════════╣
║  SECURITY REMINDERS:                                                          ║
║    • Report any security incidents to your ITSO immediately                   ║
║    • Never discuss classified information in unsecured areas                  ║
║    • All access is logged and subject to audit                                ║
║    • AUKUS information requires special handling protocols                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
        return briefing


# =============================================================================
# DEMO EXECUTION
# =============================================================================


def create_demo_officers() -> list[SecurityOfficer]:
    """Create demonstration security officers."""
    return [
        SecurityOfficer(
            employee_id="EMP-001",
            name="Alice Chen",
            clearance_level=AGSVAClearance.PV,
            clearance_expiry=datetime.now(timezone.utc) + timedelta(days=365),
            codeword_access=["NAVIGATOR"],
            need_to_know_compartments=["AUKUS-SUB", "NUCLEAR-PROP", "SOVEREIGN-CAP"],
            nationality="AUS",
            security_briefings=["AUKUS-INTRO", "NUCLEAR-SAFETY"],
        ),
        SecurityOfficer(
            employee_id="EMP-002",
            name="Bob Williams",
            clearance_level=AGSVAClearance.NV2,
            clearance_expiry=datetime.now(timezone.utc) + timedelta(days=180),
            need_to_know_compartments=["AUKUS-SUB"],
            nationality="AUS",
        ),
        SecurityOfficer(
            employee_id="EMP-003",
            name="Carol Smith",
            clearance_level=AGSVAClearance.NV1,
            clearance_expiry=datetime.now(timezone.utc) + timedelta(days=90),
            nationality="AUS",
        ),
    ]


async def run_demo():
    """Run demonstration of the defence contractor assistant."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║              AUKUS DEFENCE CONTRACTOR ASSISTANT - DEMO                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ⚠️  DEMONSTRATION ONLY - NOT FOR CLASSIFIED INFORMATION                      ║
║  This system demonstrates security patterns for defence contractors.          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )

    assistant = DefenceContractorAssistant()
    officers = create_demo_officers()

    # Demo: High-clearance officer
    print("\n" + "=" * 70)
    print("SCENARIO 1: PV-cleared officer with codeword access")
    print("=" * 70)

    alice = officers[0]
    assistant.authenticate(alice)
    print(assistant.generate_security_briefing())

    # Try accessing various documents
    for doc_id in ["DOC-001", "DOC-002", "DOC-003", "DOC-004"]:
        success, message, title = assistant.request_document(doc_id)
        status = "✓ GRANTED" if success else "✗ DENIED"
        print(f"{status}: {doc_id} - {message}")

    # Demo: Lower clearance officer
    print("\n" + "=" * 70)
    print("SCENARIO 2: NV1-cleared officer (limited access)")
    print("=" * 70)

    carol = officers[2]
    assistant.authenticate(carol)

    accessible = assistant.list_accessible_documents()
    print(f"\nAccessible documents for {carol.name}: {len(accessible)}")
    for doc in accessible:
        print(f"  • [{doc['classification']}] {doc['title']}")

    # Try accessing restricted document
    success, message, _ = assistant.request_document("DOC-002")
    print(f"\nAttempting SECRET document: {message}")

    # Export control check
    print("\n" + "=" * 70)
    print("SCENARIO 3: Export control assessment")
    print("=" * 70)

    for destination in ["AUS", "USA", "GBR", "JPN"]:
        result = assistant.check_export_control("DOC-001", destination)
        status = "✓" if result.get("allowed") else "✗"
        print(f"{status} Export to {destination}:")
        for restriction in result.get("restrictions", []):
            print(f"    ⚠️  {restriction}")
        for req in result.get("requirements", []):
            print(f"    ℹ️  {req}")

    # Verify audit trail
    print("\n" + "=" * 70)
    print("AUDIT TRAIL VERIFICATION")
    print("=" * 70)

    integrity_ok = assistant.audit_log.verify_chain_integrity()
    print(f"Audit log integrity: {'✓ VERIFIED' if integrity_ok else '✗ COMPROMISED'}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="AUKUS Defence Contractor Assistant Demo"
    )
    parser.add_argument(
        "--clearance",
        choices=["baseline", "nv1", "nv2", "pv"],
        default="nv2",
        help="Demo clearance level",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run full demonstration",
    )

    args = parser.parse_args()
    asyncio.run(run_demo())
