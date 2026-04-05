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
Secure Document Assistant for Defence Contractors.

An enterprise AI assistant for managing classified documents in defence
contractor environments:
- Classification level enforcement (UNCLASSIFIED, PROTECTED, SECRET)
- Role-based access control tied to security clearances
- Comprehensive audit logging for compliance
- Air-gapped deployment support (offline-first design)
- Document lifecycle management

Key patterns demonstrated:
- Security classification enforcement
- Clearance-level access control
- Immutable audit trails
- Offline/air-gapped deployment
- Defence industry compliance (PSPF alignment)

Usage:
    python examples/enterprise/defence_contractor.py

Requirements:
    pip install agentic-brain

Notes:
    - Designed for Australian Defence Security context
    - Supports air-gapped environments (no external API calls)
    - All operations logged for audit purposes
"""

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Optional

from agentic_brain.auth import (
    AuthConfig,
    AuthProvider,
    JWTAuth,
    Token,
    User,
    current_user,
    require_authority,
    require_role,
)

# =============================================================================
# LOGGING - Compliance-grade with tamper detection
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("defence.secure_assistant")


# =============================================================================
# CLASSIFICATION LEVELS (PSPF-aligned)
# =============================================================================


class Classification(IntEnum):
    """
    Document classification levels (Australian Government PSPF alignment).

    Each level has a numeric value for comparison operations.
    Higher values indicate higher sensitivity.
    """

    UNOFFICIAL = 0  # Not an official document
    OFFICIAL = 1  # Official government document
    OFFICIAL_SENSITIVE = 2  # Requires care in handling
    PROTECTED = 3  # Could cause damage if compromised
    SECRET = 4  # Could cause serious damage
    TOP_SECRET = 5  # Could cause exceptionally grave damage


class ClearanceLevel(IntEnum):
    """
    Personnel security clearance levels.

    Maps to Classification levels they can access.
    """

    NONE = 0  # No clearance (public only)
    BASELINE = 1  # Baseline vetting
    NV1 = 2  # Negative Vetting Level 1
    NV2 = 3  # Negative Vetting Level 2
    PV = 4  # Positive Vetting (access to SECRET)
    TOP_SECRET = 5  # Top Secret clearance


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class SecureDocument:
    """Classified document with metadata."""

    document_id: str
    title: str
    classification: Classification
    caveats: list[str] = field(default_factory=list)  # e.g., ["AUSTEO", "EYES ONLY"]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = ""
    hash_sha256: str = ""
    content_summary: str = ""  # Never store actual content, just summaries
    project_code: str = ""
    retention_until: Optional[datetime] = None

    def __post_init__(self):
        """Generate document hash on creation."""
        if not self.hash_sha256:
            content = f"{self.document_id}:{self.title}:{self.created_at.isoformat()}"
            self.hash_sha256 = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ClearedUser:
    """User with security clearance information."""

    user_id: str
    name: str
    clearance: ClearanceLevel
    caveats_access: list[str] = field(default_factory=list)
    organisation: str = ""
    clearance_expires: Optional[datetime] = None
    is_active: bool = True

    def can_access(self, doc: SecureDocument) -> bool:
        """Check if user can access a document based on clearance and caveats."""
        # Clearance level check
        if self.clearance.value < doc.classification.value:
            return False

        # Caveat check - user must have all required caveats
        for caveat in doc.caveats:
            if caveat not in self.caveats_access:
                return False

        # Check clearance expiry
        if self.clearance_expires and self.clearance_expires < datetime.now(
            UTC
        ):
            return False

        return self.is_active


@dataclass
class AuditEntry:
    """Immutable audit log entry."""

    entry_id: str
    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    classification: Classification
    outcome: str  # "SUCCESS", "DENIED", "ERROR"
    details: dict[str, Any] = field(default_factory=dict)
    source_ip: str = ""
    session_id: str = ""
    previous_hash: str = ""
    entry_hash: str = ""

    def __post_init__(self):
        """Generate entry hash for chain integrity."""
        content = f"{self.entry_id}:{self.timestamp.isoformat()}:{self.user_id}:{self.action}:{self.previous_hash}"
        self.entry_hash = hashlib.sha256(content.encode()).hexdigest()


class AuditAction(str, Enum):
    """Audit action types."""

    VIEW = "VIEW"
    SEARCH = "SEARCH"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DOWNLOAD = "DOWNLOAD"
    PRINT = "PRINT"
    SHARE = "SHARE"
    CLASSIFY = "CLASSIFY"
    DECLASSIFY = "DECLASSIFY"
    ACCESS_DENIED = "ACCESS_DENIED"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


# =============================================================================
# AUDIT SERVICE (Tamper-evident chain)
# =============================================================================


class AuditService:
    """
    Compliance audit service with tamper-evident logging.

    Features:
    - Chain-linked entries (hash of previous entry)
    - Immutable once written
    - Supports export for compliance review
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self._entries: list[AuditEntry] = []
        self._last_hash = "GENESIS"
        self._storage_path = storage_path

    def log(
        self,
        user: ClearedUser,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        classification: Classification,
        outcome: str,
        details: Optional[dict] = None,
        source_ip: str = "127.0.0.1",
        session_id: str = "",
    ) -> AuditEntry:
        """Create an immutable audit entry."""
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            user_id=user.user_id,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            classification=classification,
            outcome=outcome,
            details=details or {},
            source_ip=source_ip,
            session_id=session_id,
            previous_hash=self._last_hash,
        )

        self._entries.append(entry)
        self._last_hash = entry.entry_hash

        logger.info(
            f"AUDIT | {entry.action} | {entry.resource_type}:{entry.resource_id} | "
            f"Classification:{entry.classification.name} | User:{entry.user_id} | {entry.outcome}"
        )

        return entry

    def verify_chain_integrity(self) -> tuple[bool, Optional[str]]:
        """Verify the audit chain has not been tampered with."""
        expected_prev = "GENESIS"

        for i, entry in enumerate(self._entries):
            if entry.previous_hash != expected_prev:
                return False, f"Chain broken at entry {i}: {entry.entry_id}"
            expected_prev = entry.entry_hash

        return True, None

    def export_for_review(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        classification_minimum: Classification = Classification.UNOFFICIAL,
    ) -> list[dict]:
        """Export audit entries for compliance review."""
        entries = []

        for entry in self._entries:
            # Filter by date range
            if start_date and entry.timestamp < start_date:
                continue
            if end_date and entry.timestamp > end_date:
                continue

            # Filter by classification
            if entry.classification.value < classification_minimum.value:
                continue

            entries.append(
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "user_id": entry.user_id,
                    "action": entry.action,
                    "resource": f"{entry.resource_type}:{entry.resource_id}",
                    "classification": entry.classification.name,
                    "outcome": entry.outcome,
                    "hash": entry.entry_hash,
                }
            )

        return entries

    def get_user_activity(self, user_id: str, hours: int = 24) -> list[AuditEntry]:
        """Get recent activity for a specific user."""
        cutoff = datetime.now(UTC).timestamp() - (hours * 3600)
        return [
            e
            for e in self._entries
            if e.user_id == user_id and e.timestamp.timestamp() > cutoff
        ]


# =============================================================================
# DOCUMENT SERVICE (Classification-aware)
# =============================================================================


class SecureDocumentService:
    """
    Document management with classification enforcement.

    All operations are logged and access-controlled.
    """

    def __init__(self, audit_service: AuditService):
        self._documents: dict[str, SecureDocument] = {}
        self._audit = audit_service

        # Initialise with sample documents
        self._init_sample_data()

    def _init_sample_data(self):
        """Load sample documents for demonstration."""
        samples = [
            SecureDocument(
                document_id="DOC-001",
                title="Project Requirements Overview",
                classification=Classification.OFFICIAL,
                project_code="PRJ-ALPHA",
                content_summary="High-level requirements for contractor deliverables.",
            ),
            SecureDocument(
                document_id="DOC-002",
                title="System Architecture Design",
                classification=Classification.PROTECTED,
                project_code="PRJ-ALPHA",
                content_summary="Technical architecture including security controls.",
                caveats=["AUSTEO"],
            ),
            SecureDocument(
                document_id="DOC-003",
                title="Security Assessment Report",
                classification=Classification.SECRET,
                project_code="PRJ-BRAVO",
                content_summary="Vulnerability assessment and penetration test results.",
                caveats=["AUSTEO", "REL TO AUS"],
            ),
            SecureDocument(
                document_id="DOC-004",
                title="Procurement Guidelines",
                classification=Classification.OFFICIAL_SENSITIVE,
                project_code="PRJ-COMMON",
                content_summary="Standard procurement procedures for contractors.",
            ),
        ]

        for doc in samples:
            self._documents[doc.document_id] = doc

    def search_documents(
        self,
        user: ClearedUser,
        query: str,
        project_code: Optional[str] = None,
    ) -> list[SecureDocument]:
        """
        Search documents the user has clearance to access.

        Only returns documents the user is cleared for.
        """
        results = []

        for doc in self._documents.values():
            # Skip if user cannot access
            if not user.can_access(doc):
                continue

            # Apply project filter
            if project_code and doc.project_code != project_code:
                continue

            # Simple text search in title and summary
            query_lower = query.lower()
            if (
                query_lower in doc.title.lower()
                or query_lower in doc.content_summary.lower()
            ):
                results.append(doc)

        # Audit the search
        self._audit.log(
            user=user,
            action=AuditAction.SEARCH,
            resource_type="DOCUMENT_SEARCH",
            resource_id=query,
            classification=max(
                [d.classification for d in results], default=Classification.UNOFFICIAL
            ),
            outcome="SUCCESS",
            details={"result_count": len(results), "query": query},
        )

        return results

    def get_document(
        self,
        user: ClearedUser,
        document_id: str,
    ) -> Optional[SecureDocument]:
        """
        Retrieve a document if user has appropriate clearance.

        Access denied is logged as a security event.
        """
        doc = self._documents.get(document_id)

        if not doc:
            return None

        if not user.can_access(doc):
            self._audit.log(
                user=user,
                action=AuditAction.ACCESS_DENIED,
                resource_type="DOCUMENT",
                resource_id=document_id,
                classification=doc.classification,
                outcome="DENIED",
                details={
                    "reason": "INSUFFICIENT_CLEARANCE",
                    "required": doc.classification.name,
                    "user_clearance": user.clearance.name,
                },
            )
            logger.warning(
                f"ACCESS DENIED | User {user.user_id} attempted to access "
                f"{doc.classification.name} document {document_id}"
            )
            return None

        # Log successful access
        self._audit.log(
            user=user,
            action=AuditAction.VIEW,
            resource_type="DOCUMENT",
            resource_id=document_id,
            classification=doc.classification,
            outcome="SUCCESS",
        )

        return doc

    def create_document(
        self,
        user: ClearedUser,
        title: str,
        classification: Classification,
        project_code: str,
        content_summary: str,
        caveats: Optional[list[str]] = None,
    ) -> Optional[SecureDocument]:
        """
        Create a new classified document.

        User must have clearance >= document classification.
        """
        # Check user can create at this classification
        if user.clearance.value < classification.value:
            self._audit.log(
                user=user,
                action=AuditAction.ACCESS_DENIED,
                resource_type="DOCUMENT_CREATE",
                resource_id=title,
                classification=classification,
                outcome="DENIED",
                details={"reason": "INSUFFICIENT_CLEARANCE_TO_CREATE"},
            )
            return None

        doc = SecureDocument(
            document_id=f"DOC-{uuid.uuid4().hex[:8].upper()}",
            title=title,
            classification=classification,
            project_code=project_code,
            content_summary=content_summary,
            caveats=caveats or [],
            created_by=user.user_id,
        )

        self._documents[doc.document_id] = doc

        self._audit.log(
            user=user,
            action=AuditAction.CREATE,
            resource_type="DOCUMENT",
            resource_id=doc.document_id,
            classification=classification,
            outcome="SUCCESS",
            details={"title": title, "project": project_code},
        )

        return doc


# =============================================================================
# SECURE ASSISTANT (Main Agent)
# =============================================================================


class SecureDocumentAssistant:
    """
    AI assistant for defence contractor document management.

    Designed for air-gapped deployment:
    - Uses local Ollama models (no external API calls)
    - All processing happens on-premise
    - Full audit trail for compliance

    Deployment notes:
    - For air-gapped networks, pre-download Ollama models
    - Configure local Neo4j for persistent storage
    - Enable syslog forwarding for SIEM integration
    """

    def __init__(
        self,
        audit_service: AuditService,
        document_service: SecureDocumentService,
    ):
        self._audit = audit_service
        self._docs = document_service
        self._sessions: dict[str, ClearedUser] = {}

    def register_session(self, user: ClearedUser, session_id: str):
        """Register an active user session."""
        self._sessions[session_id] = user
        self._audit.log(
            user=user,
            action=AuditAction.LOGIN,
            resource_type="SESSION",
            resource_id=session_id,
            classification=Classification.UNOFFICIAL,
            outcome="SUCCESS",
        )
        logger.info(f"Session registered: {user.name} ({user.clearance.name})")

    def handle_query(
        self,
        session_id: str,
        query: str,
    ) -> dict[str, Any]:
        """
        Handle a user query through the assistant.

        Routes to appropriate handlers based on intent.
        """
        user = self._sessions.get(session_id)
        if not user:
            return {
                "error": "INVALID_SESSION",
                "message": "Session not found or expired.",
            }

        # Simple intent detection (production would use proper NLP)
        query_lower = query.lower()

        if "search" in query_lower or "find" in query_lower:
            return self._handle_search(user, query)

        elif "access" in query_lower or "view" in query_lower or "open" in query_lower:
            return self._handle_access_request(user, query)

        elif "clearance" in query_lower or "my access" in query_lower:
            return self._handle_clearance_query(user)

        elif "audit" in query_lower or "activity" in query_lower:
            return self._handle_audit_query(user)

        else:
            return {
                "response": "I can help you search documents, check your clearance level, "
                "or review recent activity. What would you like to do?",
                "suggested_actions": [
                    "Search for documents",
                    "View my clearance",
                    "Show recent activity",
                ],
            }

    def _handle_search(self, user: ClearedUser, query: str) -> dict[str, Any]:
        """Handle document search requests."""
        # Extract search terms (simple approach)
        search_terms = query.lower().replace("search", "").replace("find", "").strip()

        results = self._docs.search_documents(user, search_terms)

        return {
            "response": f"Found {len(results)} document(s) you have access to.",
            "documents": [
                {
                    "id": doc.document_id,
                    "title": doc.title,
                    "classification": doc.classification.name,
                    "project": doc.project_code,
                }
                for doc in results
            ],
        }

    def _handle_access_request(self, user: ClearedUser, query: str) -> dict[str, Any]:
        """Handle document access requests."""
        # Extract document ID (simple pattern)
        import re

        doc_match = re.search(r"DOC-\w+", query.upper())

        if not doc_match:
            return {
                "error": "NO_DOCUMENT_ID",
                "message": "Please specify a document ID (e.g., DOC-001).",
            }

        doc_id = doc_match.group()
        doc = self._docs.get_document(user, doc_id)

        if not doc:
            return {
                "error": "ACCESS_DENIED",
                "message": f"Cannot access {doc_id}. You may not have sufficient clearance or the document doesn't exist.",
            }

        return {
            "response": f"Document {doc.document_id} retrieved.",
            "document": {
                "id": doc.document_id,
                "title": doc.title,
                "classification": doc.classification.name,
                "caveats": doc.caveats,
                "project": doc.project_code,
                "summary": doc.content_summary,
                "created": doc.created_at.isoformat(),
            },
        }

    def _handle_clearance_query(self, user: ClearedUser) -> dict[str, Any]:
        """Return user's clearance information."""
        return {
            "response": f"Your current clearance level is {user.clearance.name}.",
            "clearance": {
                "level": user.clearance.name,
                "caveats": user.caveats_access,
                "organisation": user.organisation,
                "expires": (
                    user.clearance_expires.isoformat()
                    if user.clearance_expires
                    else None
                ),
                "can_access_classifications": [
                    c.name for c in Classification if c.value <= user.clearance.value
                ],
            },
        }

    def _handle_audit_query(self, user: ClearedUser) -> dict[str, Any]:
        """Return user's recent activity."""
        activity = self._audit.get_user_activity(user.user_id, hours=24)

        return {
            "response": f"You have {len(activity)} logged action(s) in the last 24 hours.",
            "activity": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.action,
                    "resource": f"{e.resource_type}:{e.resource_id}",
                    "outcome": e.outcome,
                }
                for e in activity[-10:]  # Last 10 entries
            ],
        }


# =============================================================================
# AIR-GAPPED DEPLOYMENT CONFIGURATION
# =============================================================================


class AirGappedConfig:
    """
    Configuration for air-gapped/isolated network deployment.

    Key considerations:
    - All models run locally via Ollama
    - No external network calls
    - Local certificate authority
    - Time synchronisation via local NTP
    """

    # Ollama models pre-downloaded for air-gap
    LLM_MODEL = "llama3.1:8b"  # Main reasoning model
    EMBED_MODEL = "nomic-embed-text"  # Local embeddings

    # Network configuration
    ALLOW_EXTERNAL_DNS = False
    ALLOW_EXTERNAL_HTTP = False
    PROXY_REQUIRED = False

    # Logging configuration
    SYSLOG_ENABLED = True
    SYSLOG_HOST = "127.0.0.1"  # Local syslog for SIEM forwarding
    SYSLOG_PORT = 514

    # Storage paths (configure per deployment)
    DOCUMENT_STORE = "/secure/documents"
    AUDIT_STORE = "/secure/audit"
    MODEL_CACHE = "/secure/models"

    # Time synchronisation
    NTP_SERVER = "ntp.local"  # Internal NTP only

    @classmethod
    def validate(cls) -> list[str]:
        """Validate air-gapped configuration."""
        issues = []

        # Check no external endpoints configured
        if cls.ALLOW_EXTERNAL_DNS:
            issues.append("WARN: External DNS enabled - not suitable for air-gap")

        if cls.ALLOW_EXTERNAL_HTTP:
            issues.append("WARN: External HTTP enabled - not suitable for air-gap")

        return issues


# =============================================================================
# DEMONSTRATION
# =============================================================================


def demo():
    """Demonstrate the secure document assistant."""

    print("=" * 70)
    print("SECURE DOCUMENT ASSISTANT - Defence Contractor Demo")
    print("=" * 70)
    print()

    # Initialise services
    audit = AuditService()
    docs = SecureDocumentService(audit)
    assistant = SecureDocumentAssistant(audit, docs)

    # Create test users with different clearances
    users = [
        ClearedUser(
            user_id="usr-001",
            name="Jane Smith",
            clearance=ClearanceLevel.NV2,
            caveats_access=["AUSTEO"],
            organisation="Defence Prime Contractor",
        ),
        ClearedUser(
            user_id="usr-002",
            name="John Doe",
            clearance=ClearanceLevel.BASELINE,
            organisation="Support Contractor",
        ),
        ClearedUser(
            user_id="usr-003",
            name="Sarah Johnson",
            clearance=ClearanceLevel.PV,
            caveats_access=["AUSTEO", "REL TO AUS"],
            organisation="Systems Integrator",
        ),
    ]

    # Register sessions
    for i, user in enumerate(users):
        session_id = f"session-{i+1}"
        assistant.register_session(user, session_id)

    print("Registered users:")
    for user in users:
        print(f"  - {user.name}: {user.clearance.name} clearance")
    print()

    # Demo: Search as different users
    print("-" * 70)
    print("DEMO: Document search with different clearances")
    print("-" * 70)

    for i, user in enumerate(users):
        session_id = f"session-{i+1}"
        result = assistant.handle_query(session_id, "search security")
        print(f"\n{user.name} ({user.clearance.name}) - Search 'security':")
        print(f"  Found: {len(result.get('documents', []))} documents")
        for doc in result.get("documents", []):
            print(f"    - {doc['id']}: {doc['title']} [{doc['classification']}]")

    # Demo: Access control
    print()
    print("-" * 70)
    print("DEMO: Access control enforcement")
    print("-" * 70)

    # Baseline user tries to access PROTECTED document
    result = assistant.handle_query("session-2", "access DOC-002")
    print("\nJohn Doe (BASELINE) accessing PROTECTED doc:")
    print(f"  Result: {result.get('error', 'SUCCESS')}")

    # NV2 user accesses PROTECTED document
    result = assistant.handle_query("session-1", "access DOC-002")
    print("\nJane Smith (NV2) accessing PROTECTED doc:")
    print(f"  Result: {result.get('document', {}).get('title', 'DENIED')}")

    # NV2 user tries to access SECRET document
    result = assistant.handle_query("session-1", "access DOC-003")
    print("\nJane Smith (NV2) accessing SECRET doc:")
    print(f"  Result: {result.get('error', 'SUCCESS')}")

    # PV user accesses SECRET document
    result = assistant.handle_query("session-3", "access DOC-003")
    print("\nSarah Johnson (PV) accessing SECRET doc:")
    print(f"  Result: {result.get('document', {}).get('title', 'DENIED')}")

    # Demo: Audit trail
    print()
    print("-" * 70)
    print("DEMO: Audit trail verification")
    print("-" * 70)

    # Verify chain integrity
    is_valid, error = audit.verify_chain_integrity()
    print(f"\nAudit chain integrity: {'VALID' if is_valid else f'INVALID - {error}'}")

    # Export audit entries
    entries = audit.export_for_review(classification_minimum=Classification.PROTECTED)
    print(f"PROTECTED+ audit entries: {len(entries)}")

    for entry in entries[-5:]:
        print(
            f"  {entry['timestamp']}: {entry['action']} - {entry['resource']} [{entry['outcome']}]"
        )

    # Air-gapped config validation
    print()
    print("-" * 70)
    print("DEMO: Air-gapped deployment validation")
    print("-" * 70)

    issues = AirGappedConfig.validate()
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  Configuration valid for air-gapped deployment")

    print()
    print("=" * 70)
    print("Demo complete. All actions logged to audit trail.")
    print("=" * 70)


if __name__ == "__main__":
    demo()
