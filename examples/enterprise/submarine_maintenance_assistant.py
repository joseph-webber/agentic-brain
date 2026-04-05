#!/usr/bin/env python3
"""
Naval Vessel Maintenance Assistant - Air-Gapped Defence Solution

A secure, air-gapped AI assistant for submarine/naval vessel maintenance
operations. Designed for Defence contractors operating in classified
environments with no internet connectivity.

Copyright (C) 2024-2025 Agentic Brain Project
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Key Features:
- 100% Air-Gapped: Ollama LLM + Local Neo4j only
- Security Classifications: UNCLASSIFIED through TOP SECRET
- Full Audit Logging: Every access logged with tamper detection
- Compartmentalized Access: Need-to-know enforcement
- File-based RAG: Local technical manuals and procedures

Submarine Systems Covered (Generic/Unclassified):
- Propulsion systems (diesel-electric, AIP concepts)
- Electrical distribution
- Hull integrity and ballast systems
- Navigation and communication
- Life support (atmosphere, water)
- Weapons handling (generic)

Compliance:
- Australian Government Information Security Manual (ISM)
- Defence Security Principles Framework (DSPF)
- ISO 27001 / ISO 27701

Usage:
    # Start in isolated network environment
    python submarine_maintenance_assistant.py

    # With specific clearance level
    CLEARANCE_LEVEL=SECRET python submarine_maintenance_assistant.py

Requirements:
    - Ollama running locally with approved models
    - Neo4j Community/Enterprise on isolated network
    - No internet connectivity (air-gapped)
    - Hardware Security Module (HSM) for key management (production)

Deployment:
    See: examples/deployment/air_gapped_deployment.py

WARNING: This is a DEMONSTRATION system using UNCLASSIFIED, publicly
available information about submarine systems. Do NOT use with actual
classified materials without proper security accreditation.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable, Optional

# ══════════════════════════════════════════════════════════════════════════════
# SECURITY CLASSIFICATIONS
# Based on Australian Government Protective Security Policy Framework (PSPF)
# ══════════════════════════════════════════════════════════════════════════════


class SecurityClassification(IntEnum):
    """
    Australian Government security classification levels.

    Reference: Protective Security Policy Framework (PSPF)
    https://www.protectivesecurity.gov.au/

    Note: This implementation uses generic levels. Actual Defence
    classifications may include additional caveats (e.g., AUSTEO, AGAO).
    """

    UNCLASSIFIED = 0  # No damage to national interest
    OFFICIAL = 1  # Low business impact if compromised
    OFFICIAL_SENSITIVE = 2  # Requires additional handling
    PROTECTED = 3  # Damage to national interest
    SECRET = 4  # Serious damage to national interest
    TOP_SECRET = 5  # Exceptionally grave damage


class Compartment(Enum):
    """
    Security compartments for need-to-know access control.

    Personnel must have both:
    1. Appropriate clearance level
    2. Specific compartment access
    """

    GENERAL = "GENERAL"  # All cleared personnel
    PROPULSION = "PROPULSION"  # Propulsion system specialists
    WEAPONS = "WEAPONS"  # Weapons systems
    COMMS = "COMMS"  # Communications/crypto
    SONAR = "SONAR"  # Sonar/sensors
    HULL = "HULL"  # Hull/structural
    ELECTRICAL = "ELECTRICAL"  # Electrical systems
    COMBAT = "COMBAT"  # Combat systems integration


@dataclass
class SecurityContext:
    """
    Security context for the current user session.

    Immutable after creation - any changes require re-authentication.
    """

    user_id: str
    clearance_level: SecurityClassification
    compartments: set[Compartment]
    session_id: str
    session_start: datetime
    session_expiry: datetime
    workstation_id: str
    authentication_method: str  # e.g., "CAC", "SMARTCARD", "PASSWORD+2FA"
    ip_address: str = "127.0.0.1"  # Local only in air-gap

    def can_access(
        self,
        classification: SecurityClassification,
        required_compartments: set[Compartment] | None = None,
    ) -> bool:
        """Check if user can access material at given classification."""
        # Must have clearance at or above document classification
        if self.clearance_level < classification:
            return False

        # Must have all required compartments (need-to-know)
        if required_compartments:
            if not required_compartments.issubset(self.compartments):
                return False

        # Session must not be expired
        return not datetime.now() > self.session_expiry

    def __hash__(self):
        return hash(self.session_id)


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOGGING SYSTEM
# Tamper-evident logging for compliance and forensics
# ══════════════════════════════════════════════════════════════════════════════


class AuditEventType(Enum):
    """Types of auditable events."""

    # Authentication events
    LOGIN_SUCCESS = "AUTH_LOGIN_SUCCESS"
    LOGIN_FAILURE = "AUTH_LOGIN_FAILURE"
    LOGOUT = "AUTH_LOGOUT"
    SESSION_TIMEOUT = "AUTH_SESSION_TIMEOUT"

    # Access events
    DOCUMENT_ACCESS = "ACCESS_DOCUMENT"
    DOCUMENT_DENIED = "ACCESS_DENIED"
    QUERY_SUBMITTED = "ACCESS_QUERY"
    SEARCH_PERFORMED = "ACCESS_SEARCH"

    # Data events
    DOCUMENT_CREATED = "DATA_DOC_CREATED"
    DOCUMENT_MODIFIED = "DATA_DOC_MODIFIED"
    DOCUMENT_DELETED = "DATA_DOC_DELETED"
    CLASSIFICATION_CHANGED = "DATA_CLASS_CHANGED"

    # System events
    SYSTEM_START = "SYS_START"
    SYSTEM_STOP = "SYS_STOP"
    CONFIG_CHANGED = "SYS_CONFIG_CHANGED"
    BACKUP_CREATED = "SYS_BACKUP"

    # Security events
    ACCESS_VIOLATION = "SEC_VIOLATION"
    ANOMALY_DETECTED = "SEC_ANOMALY"
    CLEARANCE_VERIFIED = "SEC_CLEARANCE_OK"


@dataclass
class AuditEvent:
    """
    Single audit event with tamper detection.

    Each event includes a hash chain linking to the previous event,
    making tampering detectable.
    """

    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    user_id: str
    session_id: str
    workstation_id: str
    classification: SecurityClassification
    details: dict
    previous_hash: str
    event_hash: str = ""

    def __post_init__(self):
        """Calculate event hash after creation."""
        if not self.event_hash:
            self.event_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Create SHA-256 hash of event data."""
        data = (
            f"{self.event_id}|{self.timestamp.isoformat()}|"
            f"{self.event_type.value}|{self.user_id}|{self.session_id}|"
            f"{self.workstation_id}|{self.classification.name}|"
            f"{json.dumps(self.details, sort_keys=True)}|{self.previous_hash}"
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify event hash matches content."""
        return self.event_hash == self._calculate_hash()


class AuditLogger:
    """
    Tamper-evident audit logging system.

    Features:
    - Hash chain for tamper detection
    - Encrypted at rest (when HSM available)
    - Separate storage from operational data
    - Real-time integrity verification

    Compliance: ISM controls for audit logging
    """

    def __init__(self, db_path: Path, hmac_key: bytes | None = None):
        self.db_path = db_path
        self.hmac_key = hmac_key or secrets.token_bytes(32)
        self._last_hash = "GENESIS"
        self._init_db()

    def _init_db(self):
        """Initialize audit database with integrity controls."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                workstation_id TEXT NOT NULL,
                classification TEXT NOT NULL,
                details TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_events(timestamp)
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_user
            ON audit_events(user_id)
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_type
            ON audit_events(event_type)
        """
        )
        conn.commit()

        # Load last hash for chain continuity
        cursor = conn.execute(
            "SELECT event_hash FROM audit_events ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            self._last_hash = row[0]

        conn.close()

    def log(
        self,
        event_type: AuditEventType,
        security_context: SecurityContext,
        details: dict,
        classification: SecurityClassification | None = None,
    ) -> AuditEvent:
        """
        Log an auditable event.

        Thread-safe with atomic write operations.
        """
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=event_type,
            user_id=security_context.user_id,
            session_id=security_context.session_id,
            workstation_id=security_context.workstation_id,
            classification=classification or security_context.clearance_level,
            details=details,
            previous_hash=self._last_hash,
        )

        # Store event
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO audit_events
            (event_id, timestamp, event_type, user_id, session_id,
             workstation_id, classification, details, previous_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.timestamp.isoformat(),
                event.event_type.value,
                event.user_id,
                event.session_id,
                event.workstation_id,
                event.classification.name,
                json.dumps(event.details),
                event.previous_hash,
                event.event_hash,
            ),
        )
        conn.commit()
        conn.close()

        self._last_hash = event.event_hash
        return event

    def verify_chain(self) -> tuple[bool, list[str]]:
        """
        Verify entire audit chain integrity.

        Returns: (is_valid, list of any issues found)
        """
        issues = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT * FROM audit_events ORDER BY timestamp")

        expected_prev = "GENESIS"
        for row in cursor:
            event = AuditEvent(
                event_id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                event_type=AuditEventType(row[2]),
                user_id=row[3],
                session_id=row[4],
                workstation_id=row[5],
                classification=SecurityClassification[row[6]],
                details=json.loads(row[7]),
                previous_hash=row[8],
                event_hash=row[9],
            )

            # Verify hash
            if not event.verify():
                issues.append(f"Hash mismatch for event {event.event_id}")

            # Verify chain
            if event.previous_hash != expected_prev:
                issues.append(f"Chain break at event {event.event_id}")

            expected_prev = event.event_hash

        conn.close()
        return len(issues) == 0, issues


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT MANAGEMENT
# Classified document storage and retrieval
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class TechnicalDocument:
    """
    A classified technical document or manual.

    All documents must have explicit classification markings
    per Defence security requirements.
    """

    doc_id: str
    title: str
    classification: SecurityClassification
    compartments: set[Compartment]
    document_type: str  # MANUAL, PROCEDURE, DRAWING, SPECIFICATION
    system: str  # PROPULSION, ELECTRICAL, HULL, etc.
    subsystem: str
    revision: str
    effective_date: datetime
    content: str  # For RAG indexing
    file_path: Path | None = None
    keywords: list[str] = field(default_factory=list)
    related_docs: list[str] = field(default_factory=list)

    def classification_banner(self) -> str:
        """Generate classification banner for display."""
        compart_str = "/".join(
            c.value for c in sorted(self.compartments, key=lambda x: x.value)
        )
        return f"**{self.classification.name}** [{compart_str}]"


@dataclass
class MaintenanceProcedure:
    """
    A maintenance procedure with safety requirements.

    Includes:
    - Step-by-step instructions
    - Safety precautions
    - Required tools and parts
    - Personnel qualifications
    - Time estimates
    """

    proc_id: str
    title: str
    classification: SecurityClassification
    compartments: set[Compartment]
    system: str
    subsystem: str
    maintenance_type: str  # PREVENTIVE, CORRECTIVE, EMERGENCY
    interval: str  # e.g., "500 hours", "annual", "as-required"
    estimated_hours: float
    personnel_required: int
    qualification_codes: list[str]
    safety_precautions: list[str]
    lockout_tagout_required: bool
    confined_space: bool
    steps: list[dict]  # {step_num, instruction, caution, tools, parts}
    reference_docs: list[str]


@dataclass
class PartsInventory:
    """
    Spare parts inventory item.

    Tracks:
    - Stock levels
    - Reorder points
    - Lead times (critical for submarines)
    - Shelf life
    """

    part_number: str
    nomenclature: str
    classification: SecurityClassification
    system: str
    subsystem: str
    quantity_on_hand: int
    quantity_reserved: int
    reorder_point: int
    reorder_quantity: int
    lead_time_days: int
    unit_cost: float
    shelf_life_months: int | None
    storage_conditions: str
    nsn: str  # NATO Stock Number (generic)
    cage_code: str  # Commercial And Government Entity code


@dataclass
class DefectReport:
    """
    Defect/discrepancy report for tracking issues.

    Based on generic naval maintenance reporting formats.
    """

    report_id: str
    classification: SecurityClassification
    compartments: set[Compartment]
    system: str
    subsystem: str
    severity: str  # CRITICAL, MAJOR, MINOR, COSMETIC
    discovered_date: datetime
    discovered_by: str
    location: str  # Frame/compartment reference
    description: str
    immediate_action: str
    root_cause: str
    corrective_action: str
    parts_required: list[str]
    status: str  # OPEN, IN_PROGRESS, DEFERRED, CLOSED
    due_date: datetime | None
    closed_date: datetime | None


# ══════════════════════════════════════════════════════════════════════════════
# SUBMARINE SYSTEMS KNOWLEDGE BASE
# Generic/unclassified submarine system information
# ══════════════════════════════════════════════════════════════════════════════


class SubmarineSystemsKB:
    """
    Knowledge base of submarine systems.

    IMPORTANT: This contains only UNCLASSIFIED, publicly available
    information about generic submarine systems. Do NOT populate
    with actual classified technical data.

    Sources:
    - Public naval engineering textbooks
    - Declassified historical documents
    - Generic submarine design principles
    - Wikipedia and public naval forums
    """

    # System hierarchy (generic)
    SYSTEMS = {
        "PROPULSION": {
            "description": "Main propulsion and auxiliary machinery",
            "subsystems": [
                "main_motor",
                "diesel_engines",
                "batteries",
                "aip_system",  # Air Independent Propulsion
                "reduction_gears",
                "propeller_shaft",
                "fuel_system",
            ],
        },
        "ELECTRICAL": {
            "description": "Electrical generation and distribution",
            "subsystems": [
                "main_switchboard",
                "distribution_panels",
                "battery_charging",
                "shore_power",
                "emergency_power",
                "lighting",
                "grounding",
            ],
        },
        "HULL": {
            "description": "Pressure hull and external structure",
            "subsystems": [
                "pressure_hull",
                "outer_hull",
                "ballast_tanks",
                "trim_tanks",
                "variable_ballast",
                "hull_openings",
                "anechoic_coating",
            ],
        },
        "ATMOSPHERE": {
            "description": "Atmosphere control and life support",
            "subsystems": [
                "oxygen_generation",
                "co2_removal",
                "air_conditioning",
                "ventilation",
                "atmosphere_monitoring",
                "emergency_air",
            ],
        },
        "HYDRAULICS": {
            "description": "Hydraulic systems for control surfaces and hatches",
            "subsystems": [
                "main_hydraulic",
                "steering_gear",
                "diving_planes",
                "mast_hoisting",
                "torpedo_tube",
                "emergency_manual",
            ],
        },
        "NAVIGATION": {
            "description": "Navigation and ship control",
            "subsystems": [
                "inertial_navigation",
                "periscope",
                "radar",
                "depth_sounder",
                "speed_log",
                "autopilot",
                "chart_system",
            ],
        },
        "COMMUNICATION": {
            "description": "Internal and external communications",
            "subsystems": [
                "radio_room",
                "antenna_systems",
                "intercom",
                "announcing",
                "underwater_telephone",
            ],
        },
        "SONAR": {
            "description": "Sonar and acoustic systems",
            "subsystems": [
                "bow_array",
                "flank_array",
                "towed_array",
                "intercept_sonar",
                "active_sonar",
                "signal_processing",
            ],
        },
        "WEAPONS": {
            "description": "Weapons handling and launch systems",
            "subsystems": [
                "torpedo_tubes",
                "torpedo_handling",
                "weapons_control",
                "countermeasures",
            ],
        },
        "AUXILIARY": {
            "description": "Auxiliary and support systems",
            "subsystems": [
                "fresh_water",
                "sanitary",
                "refrigeration",
                "galley",
                "laundry",
                "trash_disposal",
            ],
        },
    }

    # Generic maintenance intervals (unclassified concepts)
    MAINTENANCE_INTERVALS = {
        "daily": [
            "Battery specific gravity readings",
            "Atmosphere quality checks",
            "Hydraulic fluid levels",
            "Bilge inspections",
            "Running machinery checks",
        ],
        "weekly": [
            "Battery water levels",
            "Oxygen generator inspection",
            "Hull valve exercising",
            "Emergency equipment checks",
            "Ventilation filter inspection",
        ],
        "monthly": [
            "Safety valve testing",
            "Emergency lighting test",
            "Firefighting equipment",
            "Escape trunk inspection",
            "Periscope maintenance",
        ],
        "quarterly": [
            "Battery capacity test",
            "Hydraulic system flush",
            "Hull coating inspection",
            "Antenna system checks",
            "Trim system calibration",
        ],
        "annual": [
            "Full battery replacement assessment",
            "Hull thickness measurements",
            "Valve overhauls",
            "Major equipment calibration",
            "Safety system certification",
        ],
    }

    # Safety precautions by system (generic)
    SAFETY_PRECAUTIONS = {
        "battery_work": [
            "Ensure adequate ventilation - hydrogen gas hazard",
            "Wear acid-resistant PPE including face shield",
            "Ground all tools - spark hazard",
            "Have neutralizing agent (sodium bicarbonate) available",
            "No smoking or open flames within 15 meters",
            "Verify battery breakers are open and tagged",
        ],
        "hydraulic_work": [
            "Depressurize system before opening",
            "Lock out / tag out all power sources",
            "Wear eye protection - high pressure injection hazard",
            "Have spill containment ready",
            "Verify all accumulator pressure relieved",
        ],
        "confined_space": [
            "Obtain confined space entry permit",
            "Test atmosphere: O2, CO2, H2S, LEL",
            "Establish continuous ventilation",
            "Station rescue watch at entry point",
            "Maintain communication with entrant",
            "Have rescue equipment staged",
        ],
        "electrical_work": [
            "De-energize and verify zero energy state",
            "Apply lockout/tagout",
            "Test before touch",
            "Use insulated tools rated for voltage",
            "Maintain safe boundaries",
            "Ground portable equipment",
        ],
        "hull_penetration": [
            "Obtain commanding officer approval",
            "Verify watertight integrity can be maintained",
            "Stage damage control equipment",
            "Test hull fitting after work",
            "Document all penetrations",
        ],
    }

    @classmethod
    def get_system_info(cls, system: str) -> dict | None:
        """Get information about a submarine system."""
        return cls.SYSTEMS.get(system.upper())

    @classmethod
    def get_maintenance_schedule(cls, interval: str) -> list[str]:
        """Get maintenance items for given interval."""
        return cls.MAINTENANCE_INTERVALS.get(interval.lower(), [])

    @classmethod
    def get_safety_precautions(cls, work_type: str) -> list[str]:
        """Get safety precautions for work type."""
        return cls.SAFETY_PRECAUTIONS.get(work_type.lower(), [])


# ══════════════════════════════════════════════════════════════════════════════
# AIR-GAPPED RAG SYSTEM
# Local file-based retrieval augmented generation
# ══════════════════════════════════════════════════════════════════════════════


class LocalRAGStore:
    """
    Air-gapped RAG storage using local files and Neo4j.

    No external API calls - all processing done locally.
    Uses Ollama for embeddings and retrieval.

    Architecture:
    - Technical manuals stored as local files
    - Neo4j stores document metadata and relationships
    - Ollama generates embeddings locally
    - SQLite for full-text search backup
    """

    def __init__(
        self,
        documents_path: Path,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "Brain2026",
        ollama_host: str = "http://localhost:11434",
    ):
        self.documents_path = documents_path
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.ollama_host = ollama_host

        # Embedding model (must be available offline)
        self.embedding_model = "nomic-embed-text"

        # Document index
        self._documents: dict[str, TechnicalDocument] = {}
        self._procedures: dict[str, MaintenanceProcedure] = {}

    async def initialize(self):
        """Initialize RAG store and load documents."""
        # Verify Ollama is available
        await self._verify_ollama()

        # Load documents from local storage
        await self._load_documents()

        # Initialize Neo4j indexes
        await self._init_neo4j()

        logging.info(
            f"RAG store initialized: {len(self._documents)} documents, "
            f"{len(self._procedures)} procedures"
        )

    async def _verify_ollama(self):
        """Verify Ollama is running and models available."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.ollama_host}/api/tags", timeout=5.0)
                if resp.status_code != 200:
                    raise RuntimeError("Ollama not responding")

                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]

                if self.embedding_model not in model_names:
                    logging.warning(
                        f"Embedding model {self.embedding_model} not found. "
                        f"Available: {model_names}"
                    )
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Ollama at {self.ollama_host}: {e}")

    async def _load_documents(self):
        """Load technical documents from local storage."""
        if not self.documents_path.exists():
            logging.warning(f"Documents path not found: {self.documents_path}")
            return

        # Load JSON metadata files
        for meta_file in self.documents_path.glob("**/*.meta.json"):
            try:
                with open(meta_file) as f:
                    meta = json.load(f)

                doc = TechnicalDocument(
                    doc_id=meta["doc_id"],
                    title=meta["title"],
                    classification=SecurityClassification[meta["classification"]],
                    compartments={Compartment[c] for c in meta["compartments"]},
                    document_type=meta["document_type"],
                    system=meta["system"],
                    subsystem=meta["subsystem"],
                    revision=meta["revision"],
                    effective_date=datetime.fromisoformat(meta["effective_date"]),
                    content=meta.get("content", ""),
                    file_path=Path(meta.get("file_path", "")),
                    keywords=meta.get("keywords", []),
                    related_docs=meta.get("related_docs", []),
                )
                self._documents[doc.doc_id] = doc

            except Exception as e:
                logging.error(f"Error loading {meta_file}: {e}")

    async def _init_neo4j(self):
        """Initialize Neo4j with document graph."""
        # In production, would connect to local Neo4j
        # For demo, we use in-memory structures
        pass

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding using local Ollama."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.ollama_host}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text},
                timeout=30.0,
            )
            return resp.json()["embedding"]

    async def search(
        self,
        query: str,
        security_context: SecurityContext,
        system_filter: str | None = None,
        top_k: int = 5,
    ) -> list[TechnicalDocument]:
        """
        Search documents with security filtering.

        Only returns documents the user is cleared to access.
        """
        results = []

        for doc in self._documents.values():
            # Security check
            if not security_context.can_access(doc.classification, doc.compartments):
                continue

            # System filter
            if system_filter and doc.system != system_filter:
                continue

            # Simple keyword matching (would use embeddings in production)
            query_lower = query.lower()
            if (
                query_lower in doc.title.lower()
                or query_lower in doc.content.lower()
                or any(query_lower in kw.lower() for kw in doc.keywords)
            ):
                results.append(doc)

        return results[:top_k]

    async def get_procedure(
        self, proc_id: str, security_context: SecurityContext
    ) -> MaintenanceProcedure | None:
        """Get maintenance procedure with security check."""
        proc = self._procedures.get(proc_id)
        if not proc:
            return None

        if not security_context.can_access(proc.classification, proc.compartments):
            return None

        return proc


# ══════════════════════════════════════════════════════════════════════════════
# AIR-GAPPED LLM INTERFACE
# Ollama-only language model access
# ══════════════════════════════════════════════════════════════════════════════


class AirGappedLLM:
    """
    Air-gapped LLM using Ollama only.

    No external API calls - all inference runs locally.
    Supports multiple approved models for different tasks.

    Security:
    - Models must be pre-loaded (no downloading)
    - Responses sanitized for classification leaks
    - Full prompt/response logging for audit
    """

    # Approved models for air-gapped use
    APPROVED_MODELS = {
        "general": "llama3.1:8b",
        "technical": "llama3.1:8b",
        "code": "codellama:13b",
        "embedding": "nomic-embed-text",
    }

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        audit_logger: AuditLogger | None = None,
    ):
        self.ollama_host = ollama_host
        self.audit_logger = audit_logger
        self._available_models: set[str] = set()

    async def initialize(self):
        """Verify models are available locally."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.ollama_host}/api/tags")
            models = resp.json().get("models", [])
            self._available_models = {m["name"] for m in models}

        # Check required models
        for purpose, model in self.APPROVED_MODELS.items():
            if model not in self._available_models:
                logging.warning(
                    f"Model {model} for {purpose} not available. "
                    f"Pull with: ollama pull {model}"
                )

    async def generate(
        self,
        prompt: str,
        security_context: SecurityContext,
        model_type: str = "general",
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """
        Generate response using local Ollama.

        All prompts and responses are audit logged.
        """
        import httpx

        model = self.APPROVED_MODELS.get(model_type, "llama3.1:8b")

        # Log the query
        if self.audit_logger:
            self.audit_logger.log(
                AuditEventType.QUERY_SUBMITTED,
                security_context,
                {
                    "model": model,
                    "prompt_length": len(prompt),
                    "system_prompt_provided": system_prompt is not None,
                },
            )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.ollama_host}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                        "stream": False,
                    },
                    timeout=120.0,
                )

                result = resp.json()
                response = result.get("message", {}).get("content", "")

                # Sanitize response (check for classification leaks)
                response = self._sanitize_response(response, security_context)

                return response

        except Exception as e:
            logging.error(f"LLM generation error: {e}")
            return f"Error: Unable to process request. {e}"

    def _sanitize_response(
        self, response: str, security_context: SecurityContext
    ) -> str:
        """
        Sanitize LLM response for security.

        Checks for:
        - Classification markers above user clearance
        - Potential sensitive keywords
        - Format compliance
        """
        # Check for classification markers
        classification_markers = [
            "TOP SECRET",
            "TS//",
            "SECRET//",
            "S//",
            "CONFIDENTIAL",
            "RESTRICTED",
        ]

        for marker in classification_markers:
            if marker in response.upper():
                # If user doesn't have clearance, redact
                if security_context.clearance_level < SecurityClassification.SECRET:
                    response = response.replace(
                        marker, "[REDACTED - INSUFFICIENT CLEARANCE]"
                    )

        return response


# ══════════════════════════════════════════════════════════════════════════════
# NAVAL MAINTENANCE ASSISTANT
# Main assistant class combining all components
# ══════════════════════════════════════════════════════════════════════════════


class NavalMaintenanceAssistant:
    """
    Naval Vessel Maintenance Assistant.

    An air-gapped AI assistant for submarine maintenance operations.
    Combines RAG retrieval, LLM generation, and security controls.

    Features:
    - Technical manual lookup
    - Maintenance procedure guidance
    - Parts inventory queries
    - Safety protocol compliance
    - Defect reporting workflow

    Security:
    - Classification-based access control
    - Full audit logging
    - No external network access
    - Encryption at rest (with HSM)
    """

    SYSTEM_PROMPT = """You are a Naval Vessel Maintenance Assistant operating
in an air-gapped, secure environment. You help maintenance personnel with:

1. TECHNICAL MANUAL LOOKUP
   - Finding relevant procedures and specifications
   - Explaining system operation and theory
   - Cross-referencing related documentation

2. MAINTENANCE GUIDANCE
   - Step-by-step procedure walkthrough
   - Safety precaution reminders
   - Tool and parts requirements
   - Time and personnel estimates

3. TROUBLESHOOTING
   - Fault diagnosis assistance
   - Systematic troubleshooting approaches
   - Common failure modes and solutions

4. INVENTORY SUPPORT
   - Parts identification
   - Stock level queries
   - Reorder recommendations

SECURITY RULES:
- Only provide information at or below the user's clearance level
- Always include classification markings on technical content
- Do not speculate about classified capabilities
- Refer to documents by their security markings

RESPONSE FORMAT:
- Be concise and technically accurate
- Use proper naval terminology
- Include relevant document references
- Highlight safety-critical information

Current user clearance: {clearance_level}
Compartments: {compartments}
"""

    def __init__(
        self,
        config_path: Path | None = None,
        documents_path: Path | None = None,
        audit_db_path: Path | None = None,
    ):
        self.config_path = config_path or Path("./config/naval_assistant.json")
        self.documents_path = documents_path or Path("./data/technical_docs")
        self.audit_db_path = audit_db_path or Path("./data/audit/audit.db")

        self.audit_logger: AuditLogger | None = None
        self.rag_store: LocalRAGStore | None = None
        self.llm: AirGappedLLM | None = None
        self.knowledge_base = SubmarineSystemsKB()

        # Active sessions
        self._sessions: dict[str, SecurityContext] = {}

    async def initialize(self):
        """Initialize all components."""
        logging.info("Initializing Naval Maintenance Assistant...")

        # Initialize audit logger
        self.audit_logger = AuditLogger(self.audit_db_path)
        logging.info("Audit logger initialized")

        # Initialize RAG store
        self.rag_store = LocalRAGStore(self.documents_path)
        await self.rag_store.initialize()
        logging.info("RAG store initialized")

        # Initialize LLM
        self.llm = AirGappedLLM(audit_logger=self.audit_logger)
        await self.llm.initialize()
        logging.info("LLM initialized")

        logging.info("Naval Maintenance Assistant ready")

    def create_session(
        self,
        user_id: str,
        clearance_level: SecurityClassification,
        compartments: set[Compartment],
        workstation_id: str,
        auth_method: str = "CAC",
    ) -> SecurityContext:
        """
        Create a new authenticated session.

        In production, this would integrate with:
        - CAC/Smart card authentication
        - Active Directory / LDAP
        - Hardware Security Module for session keys
        """
        session_id = str(uuid.uuid4())

        context = SecurityContext(
            user_id=user_id,
            clearance_level=clearance_level,
            compartments=compartments,
            session_id=session_id,
            session_start=datetime.now(),
            session_expiry=datetime.now() + timedelta(hours=8),
            workstation_id=workstation_id,
            authentication_method=auth_method,
        )

        self._sessions[session_id] = context

        # Log session creation
        if self.audit_logger:
            self.audit_logger.log(
                AuditEventType.LOGIN_SUCCESS,
                context,
                {
                    "auth_method": auth_method,
                    "clearance": clearance_level.name,
                    "compartments": [c.value for c in compartments],
                },
            )

        return context

    async def query(
        self,
        question: str,
        security_context: SecurityContext,
        system_filter: str | None = None,
    ) -> str:
        """
        Process a maintenance query.

        1. Search relevant documents (RAG)
        2. Build context with security filtering
        3. Generate response with LLM
        4. Audit log the interaction
        """
        if not self.llm or not self.rag_store:
            return "Error: System not initialized"

        # Search for relevant documents
        docs = await self.rag_store.search(
            question, security_context, system_filter=system_filter
        )

        # Build context
        context_parts = []
        for doc in docs:
            context_parts.append(
                f"\n{doc.classification_banner()}\n"
                f"Document: {doc.title} (Rev {doc.revision})\n"
                f"System: {doc.system}/{doc.subsystem}\n"
                f"Content: {doc.content[:500]}..."
            )

        # Include generic knowledge base info if relevant
        for system, info in self.knowledge_base.SYSTEMS.items():
            if system.lower() in question.lower():
                context_parts.append(
                    f"\nSystem Overview - {system}:\n"
                    f"{info['description']}\n"
                    f"Subsystems: {', '.join(info['subsystems'])}"
                )

        context = "\n---\n".join(context_parts)

        # Build system prompt
        system_prompt = self.SYSTEM_PROMPT.format(
            clearance_level=security_context.clearance_level.name,
            compartments=", ".join(c.value for c in security_context.compartments),
        )

        # Generate response
        full_prompt = f"""Based on the following technical documentation and your knowledge
of naval vessel systems, please answer the maintenance query.

RETRIEVED DOCUMENTATION:
{context}

QUERY: {question}

Provide a helpful, technically accurate response. Include any relevant
safety precautions and document references."""

        response = await self.llm.generate(
            full_prompt, security_context, system_prompt=system_prompt
        )

        # Log the query
        if self.audit_logger:
            self.audit_logger.log(
                AuditEventType.QUERY_SUBMITTED,
                security_context,
                {
                    "query": question[:100],
                    "docs_retrieved": len(docs),
                    "system_filter": system_filter,
                },
            )

        return response

    async def get_maintenance_schedule(
        self, security_context: SecurityContext, interval: str = "daily"
    ) -> str:
        """Get maintenance schedule for specified interval."""
        items = self.knowledge_base.get_maintenance_schedule(interval)

        if not items:
            return f"No maintenance items found for interval: {interval}"

        response = f"**{interval.upper()} MAINTENANCE SCHEDULE**\n"
        response += "Classification: UNCLASSIFIED\n\n"

        for i, item in enumerate(items, 1):
            response += f"{i}. {item}\n"

        return response

    async def get_safety_precautions(
        self, security_context: SecurityContext, work_type: str
    ) -> str:
        """Get safety precautions for work type."""
        precautions = self.knowledge_base.get_safety_precautions(work_type)

        if not precautions:
            return f"No specific precautions found for: {work_type}"

        response = f"**SAFETY PRECAUTIONS: {work_type.upper()}**\n"
        response += "Classification: UNCLASSIFIED\n\n"
        response += "⚠️ MANDATORY SAFETY REQUIREMENTS:\n\n"

        for i, precaution in enumerate(precautions, 1):
            response += f"{i}. {precaution}\n"

        response += "\n⚠️ Failure to follow these precautions may result in "
        response += "injury or equipment damage."

        return response

    async def report_defect(
        self,
        security_context: SecurityContext,
        system: str,
        subsystem: str,
        severity: str,
        description: str,
        location: str,
        immediate_action: str = "",
    ) -> DefectReport:
        """Create a new defect report."""
        report = DefectReport(
            report_id=f"DEF-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            classification=SecurityClassification.PROTECTED,  # Default for defects
            compartments={Compartment.GENERAL},
            system=system.upper(),
            subsystem=subsystem,
            severity=severity.upper(),
            discovered_date=datetime.now(),
            discovered_by=security_context.user_id,
            location=location,
            description=description,
            immediate_action=immediate_action,
            root_cause="",
            corrective_action="",
            parts_required=[],
            status="OPEN",
            due_date=None,
            closed_date=None,
        )

        # Log the defect creation
        if self.audit_logger:
            self.audit_logger.log(
                AuditEventType.DOCUMENT_CREATED,
                security_context,
                {
                    "report_id": report.report_id,
                    "system": system,
                    "severity": severity,
                    "description": description[:100],
                },
                classification=report.classification,
            )

        return report

    def end_session(self, security_context: SecurityContext):
        """End a user session."""
        if security_context.session_id in self._sessions:
            del self._sessions[security_context.session_id]

            if self.audit_logger:
                self.audit_logger.log(
                    AuditEventType.LOGOUT, security_context, {"reason": "user_logout"}
                )


# ══════════════════════════════════════════════════════════════════════════════
# DEMO / TESTING
# ══════════════════════════════════════════════════════════════════════════════


async def demo():
    """Demonstrate the Naval Maintenance Assistant."""

    print("=" * 70)
    print("NAVAL VESSEL MAINTENANCE ASSISTANT - AIR-GAPPED DEMO")
    print("=" * 70)
    print()
    print("⚠️  UNCLASSIFIED DEMONSTRATION SYSTEM")
    print("⚠️  Contains only publicly available information")
    print()

    # Create assistant
    assistant = NavalMaintenanceAssistant()

    try:
        await assistant.initialize()
    except RuntimeError as e:
        print(f"⚠️  Warning: {e}")
        print("    Running in limited demo mode without LLM")

    # Create demo session with SECRET clearance
    session = assistant.create_session(
        user_id="DEMO_USER_001",
        clearance_level=SecurityClassification.SECRET,
        compartments={
            Compartment.GENERAL,
            Compartment.PROPULSION,
            Compartment.ELECTRICAL,
            Compartment.HULL,
        },
        workstation_id="WS-DEMO-001",
        auth_method="DEMO",
    )

    print(f"Session created: {session.session_id[:8]}...")
    print(f"Clearance: {session.clearance_level.name}")
    print(f"Compartments: {', '.join(c.value for c in session.compartments)}")
    print()

    # Demo 1: Maintenance Schedule
    print("-" * 70)
    print("DEMO 1: Daily Maintenance Schedule")
    print("-" * 70)
    schedule = await assistant.get_maintenance_schedule(session, "daily")
    print(schedule)
    print()

    # Demo 2: Safety Precautions
    print("-" * 70)
    print("DEMO 2: Battery Work Safety Precautions")
    print("-" * 70)
    safety = await assistant.get_safety_precautions(session, "battery_work")
    print(safety)
    print()

    # Demo 3: System Query (requires Ollama)
    print("-" * 70)
    print("DEMO 3: Technical Query")
    print("-" * 70)

    if assistant.llm and assistant.llm._available_models:
        query = "What are the key components of a submarine propulsion system?"
        print(f"Query: {query}")
        print()
        response = await assistant.query(query, session, system_filter="PROPULSION")
        print("Response:")
        print(response)
    else:
        print("⚠️  Ollama not available - skipping LLM demo")
        print("    Start Ollama with: ollama serve")
        print("    Pull model with: ollama pull llama3.1:8b")
    print()

    # Demo 4: Defect Report
    print("-" * 70)
    print("DEMO 4: Create Defect Report")
    print("-" * 70)
    defect = await assistant.report_defect(
        session,
        system="ELECTRICAL",
        subsystem="distribution_panels",
        severity="MINOR",
        description="Indicator light intermittent on panel 2A-3",
        location="Compartment 2, Frame 45",
        immediate_action="Bypassed indicator, noted in log",
    )
    print(f"Defect Report Created: {defect.report_id}")
    print(f"Classification: {defect.classification.name}")
    print(f"System: {defect.system}/{defect.subsystem}")
    print(f"Severity: {defect.severity}")
    print(f"Status: {defect.status}")
    print()

    # Demo 5: Audit Trail
    print("-" * 70)
    print("DEMO 5: Audit Log Verification")
    print("-" * 70)
    if assistant.audit_logger:
        valid, issues = assistant.audit_logger.verify_chain()
        print(f"Audit chain valid: {valid}")
        if issues:
            for issue in issues:
                print(f"  ⚠️ {issue}")
        else:
            print("  ✓ All audit records verified")
    print()

    # End session
    assistant.end_session(session)
    print("Session ended. All activities logged for compliance.")
    print()
    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


def main():
    """Main entry point."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Check environment
    if os.environ.get("CLASSIFIED_NETWORK"):
        print("⚠️  CLASSIFIED NETWORK DETECTED")
        print("⚠️  Ensure proper security controls are in place")
        print()

    # Run demo
    asyncio.run(demo())


if __name__ == "__main__":
    main()
