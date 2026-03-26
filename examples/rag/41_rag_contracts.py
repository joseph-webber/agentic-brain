#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 41: RAG Contract/Legal Document Analysis

An AI assistant for analyzing legal and contract documents:
- Clause identification and extraction
- Risk highlighting and assessment
- Key term extraction
- Version comparison
- Summary generation
- Contract obligations tracking

Key RAG features demonstrated:
- Legal document parsing
- Entity and clause extraction
- Risk scoring
- Diff analysis between versions
- Multi-document synthesis
- Citation with legal references

Demo: Generic service contracts

Usage:
    python examples/41_rag_contracts.py
    python examples/41_rag_contracts.py --demo

Requirements:
    pip install agentic-brain sentence-transformers
"""

import asyncio
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
import math
import difflib

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ContractRAGConfig:
    """Configuration for contract analysis RAG."""

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Chunking
    chunk_size: int = 600
    chunk_overlap: int = 100

    # Analysis
    risk_threshold_high: float = 0.7
    risk_threshold_medium: float = 0.4

    # Search
    top_k: int = 10


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS AND DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class ContractType(Enum):
    """Types of contracts."""

    SERVICE_AGREEMENT = "service_agreement"
    NDA = "nda"
    EMPLOYMENT = "employment"
    LICENSE = "license"
    LEASE = "lease"
    PARTNERSHIP = "partnership"
    VENDOR = "vendor"
    CONSULTING = "consulting"
    OTHER = "other"


class ClauseType(Enum):
    """Types of contract clauses."""

    DEFINITIONS = "definitions"
    SCOPE = "scope"
    TERM_DURATION = "term_duration"
    PAYMENT = "payment"
    TERMINATION = "termination"
    CONFIDENTIALITY = "confidentiality"
    INDEMNIFICATION = "indemnification"
    LIABILITY = "liability"
    WARRANTY = "warranty"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    DISPUTE_RESOLUTION = "dispute_resolution"
    GOVERNING_LAW = "governing_law"
    FORCE_MAJEURE = "force_majeure"
    ASSIGNMENT = "assignment"
    AMENDMENT = "amendment"
    NOTICE = "notice"
    ENTIRE_AGREEMENT = "entire_agreement"
    SEVERABILITY = "severability"
    OTHER = "other"


class RiskLevel(Enum):
    """Risk levels for clauses."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ObligationType(Enum):
    """Types of contract obligations."""

    PAYMENT = "payment"
    DELIVERY = "delivery"
    REPORTING = "reporting"
    COMPLIANCE = "compliance"
    NOTIFICATION = "notification"
    PERFORMANCE = "performance"
    CONFIDENTIALITY = "confidentiality"
    OTHER = "other"


@dataclass
class Party:
    """A party to the contract."""

    name: str
    role: str  # e.g., "Client", "Provider", "Licensor"
    address: str = ""
    contact: str = ""


@dataclass
class KeyTerm:
    """A key term defined in the contract."""

    term: str
    definition: str
    first_occurrence: int = 0  # Character position
    references: int = 1


@dataclass
class Clause:
    """A clause in the contract."""

    id: str
    clause_type: ClauseType
    title: str
    content: str
    section_number: str = ""
    start_pos: int = 0
    end_pos: int = 0
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)

    @property
    def reference(self) -> str:
        """Get clause reference."""
        if self.section_number:
            return f"Section {self.section_number}"
        return f"Clause: {self.title}"


@dataclass
class RiskItem:
    """A risk identified in the contract."""

    id: str
    clause_id: str
    risk_level: RiskLevel
    description: str
    recommendation: str
    keywords: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class Obligation:
    """An obligation identified in the contract."""

    id: str
    obligation_type: ObligationType
    description: str
    responsible_party: str
    deadline: Optional[datetime] = None
    frequency: str = ""  # e.g., "monthly", "upon request"
    clause_reference: str = ""
    is_conditional: bool = False
    condition: str = ""


@dataclass
class ContractSummary:
    """Summary of a contract."""

    contract_id: str
    title: str
    contract_type: ContractType
    parties: list[Party]
    effective_date: Optional[datetime]
    expiry_date: Optional[datetime]
    total_value: Optional[float]
    key_terms: list[KeyTerm]
    key_clauses: list[str]
    risk_summary: dict[RiskLevel, int]
    obligations_count: int


@dataclass
class Contract:
    """A legal contract document."""

    id: str
    title: str
    contract_type: ContractType
    full_text: str

    # Parties
    parties: list[Party] = field(default_factory=list)

    # Dates
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    execution_date: Optional[datetime] = None

    # Content
    clauses: list[Clause] = field(default_factory=list)
    key_terms: list[KeyTerm] = field(default_factory=list)

    # Analysis
    risks: list[RiskItem] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)

    # Metadata
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None


@dataclass
class VersionDiff:
    """Differences between contract versions."""

    old_version: str
    new_version: str
    added_clauses: list[str]
    removed_clauses: list[str]
    modified_clauses: list[tuple[str, str, str]]  # (clause_id, old_text, new_text)
    risk_changes: list[str]
    summary: str


# ══════════════════════════════════════════════════════════════════════════════
# CONTRACT PARSER
# ══════════════════════════════════════════════════════════════════════════════


class ContractParser:
    """Parse contract documents."""

    # Clause detection patterns
    CLAUSE_PATTERNS = {
        ClauseType.DEFINITIONS: r"(?i)^\d*\.?\s*(definitions?|defined\s+terms)",
        ClauseType.SCOPE: r"(?i)^\d*\.?\s*(scope\s+of\s+(work|services?)|services?|deliverables?)",
        ClauseType.TERM_DURATION: r"(?i)^\d*\.?\s*(term|duration|effective\s+date)",
        ClauseType.PAYMENT: r"(?i)^\d*\.?\s*(payment|compensation|fees?|pricing|invoic)",
        ClauseType.TERMINATION: r"(?i)^\d*\.?\s*terminat",
        ClauseType.CONFIDENTIALITY: r"(?i)^\d*\.?\s*(confidential|non.?disclosure|nda)",
        ClauseType.INDEMNIFICATION: r"(?i)^\d*\.?\s*indemnif",
        ClauseType.LIABILITY: r"(?i)^\d*\.?\s*(limit.*liabil|liabil)",
        ClauseType.WARRANTY: r"(?i)^\d*\.?\s*(warrant|representation)",
        ClauseType.INTELLECTUAL_PROPERTY: r"(?i)^\d*\.?\s*(intellectual\s+property|ip\s+rights?|ownership)",
        ClauseType.DISPUTE_RESOLUTION: r"(?i)^\d*\.?\s*(dispute|arbitrat|mediat)",
        ClauseType.GOVERNING_LAW: r"(?i)^\d*\.?\s*(govern.*law|jurisdiction|choice\s+of\s+law)",
        ClauseType.FORCE_MAJEURE: r"(?i)^\d*\.?\s*force\s+majeure",
        ClauseType.ASSIGNMENT: r"(?i)^\d*\.?\s*assign",
        ClauseType.AMENDMENT: r"(?i)^\d*\.?\s*(amend|modif)",
        ClauseType.NOTICE: r"(?i)^\d*\.?\s*notice",
        ClauseType.ENTIRE_AGREEMENT: r"(?i)^\d*\.?\s*(entire\s+agreement|whole\s+agreement)",
        ClauseType.SEVERABILITY: r"(?i)^\d*\.?\s*severab",
    }

    # Risk keywords by category
    RISK_KEYWORDS = {
        "unlimited_liability": [
            "unlimited liability",
            "sole discretion",
            "any and all damages",
        ],
        "auto_renewal": ["automatically renew", "auto-renewal", "shall renew"],
        "termination_penalty": [
            "early termination fee",
            "termination penalty",
            "liquidated damages",
        ],
        "one_sided_indemnity": [
            "shall indemnify",
            "hold harmless",
            "defend and indemnify",
        ],
        "broad_ip_assignment": [
            "assign all rights",
            "work for hire",
            "all intellectual property",
        ],
        "non_compete": ["non-compete", "non-solicitation", "restrictive covenant"],
        "audit_rights": ["audit rights", "right to audit", "inspection rights"],
        "unilateral_changes": [
            "may modify",
            "sole discretion to change",
            "reserves the right",
        ],
    }

    def parse(self, content: str, metadata: dict = None) -> Contract:
        """Parse a contract document."""
        metadata = metadata or {}

        # Generate ID
        contract_id = hashlib.md5(content[:500].encode()).hexdigest()[:12]

        # Extract title
        title = self._extract_title(content, metadata)

        # Detect contract type
        contract_type = self._detect_contract_type(content)

        # Extract parties
        parties = self._extract_parties(content)

        # Extract dates
        effective_date, expiry_date = self._extract_dates(content)

        # Extract clauses
        clauses = self._extract_clauses(content)

        # Extract key terms
        key_terms = self._extract_key_terms(content)

        # Identify risks
        risks = self._identify_risks(content, clauses)

        # Extract obligations
        obligations = self._extract_obligations(content, clauses, parties)

        return Contract(
            id=contract_id,
            title=title,
            contract_type=contract_type,
            full_text=content,
            parties=parties,
            effective_date=effective_date,
            expiry_date=expiry_date,
            clauses=clauses,
            key_terms=key_terms,
            risks=risks,
            obligations=obligations,
            version=metadata.get("version", "1.0"),
            metadata=metadata,
        )

    def _extract_title(self, content: str, metadata: dict) -> str:
        """Extract contract title."""
        if metadata.get("title"):
            return metadata["title"]

        # Look for title in first few lines
        lines = content.split("\n")
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 10 and len(line) < 200:
                if re.search(r"(?i)(agreement|contract|terms)", line):
                    return line.strip("#").strip()

        return "Untitled Contract"

    def _detect_contract_type(self, content: str) -> ContractType:
        """Detect contract type from content."""
        content_lower = content.lower()

        type_patterns = {
            ContractType.NDA: ["non-disclosure", "confidentiality agreement", "nda"],
            ContractType.SERVICE_AGREEMENT: [
                "service agreement",
                "services agreement",
                "sow",
            ],
            ContractType.EMPLOYMENT: ["employment agreement", "employment contract"],
            ContractType.LICENSE: [
                "license agreement",
                "licensing agreement",
                "software license",
            ],
            ContractType.LEASE: ["lease agreement", "rental agreement"],
            ContractType.PARTNERSHIP: ["partnership agreement", "joint venture"],
            ContractType.VENDOR: ["vendor agreement", "supplier agreement"],
            ContractType.CONSULTING: ["consulting agreement", "consultant agreement"],
        }

        for contract_type, patterns in type_patterns.items():
            for pattern in patterns:
                if pattern in content_lower:
                    return contract_type

        return ContractType.OTHER

    def _extract_parties(self, content: str) -> list[Party]:
        """Extract parties from contract."""
        parties = []

        # Common party patterns
        patterns = [
            r'(?i)between\s+([^,\n]+?)\s*\(\s*"([^"]+)"\s*\)',
            r'(?i)([^,\n]+?)\s+\(\s*"(Party\s*[AB12])"\s*\)',
            r"(?i)(Client|Provider|Licensor|Licensee|Employer|Employee):\s*([^\n]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) >= 2:
                    name = match[0].strip()
                    role = match[1].strip()

                    # Clean up name
                    name = re.sub(r"\s+", " ", name)
                    name = name.strip("., ")

                    if len(name) > 2 and len(name) < 100:
                        parties.append(Party(name=name, role=role))

        # If no parties found, try simpler extraction
        if not parties:
            # Look for company names
            company_matches = re.findall(
                r"(?i)([A-Z][A-Za-z\s]+(?:Inc\.|LLC|Ltd\.?|Corp\.?|Company))", content
            )
            for i, company in enumerate(company_matches[:2]):
                role = "Party A" if i == 0 else "Party B"
                parties.append(Party(name=company.strip(), role=role))

        return parties[:2]  # Limit to 2 parties

    def _extract_dates(
        self, content: str
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Extract effective and expiry dates."""
        effective_date = None
        expiry_date = None

        # Date patterns
        date_patterns = [
            r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})",  # MM/DD/YYYY or DD/MM/YYYY
            r"(\w+)\s+(\d{1,2}),?\s+(\d{4})",  # Month DD, YYYY
            r"(\d{1,2})\s+(\w+)\s+(\d{4})",  # DD Month YYYY
        ]

        # Effective date keywords
        effective_patterns = [
            r"(?i)effective\s+(?:as\s+of\s+)?(?:date[:\s]+)?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
            r"(?i)commenc(?:e|ing)\s+(?:on\s+)?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        ]

        for pattern in effective_patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    date_str = match.group(1)
                    # Try to parse
                    for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y"]:
                        try:
                            effective_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    if effective_date:
                        break
                except (ValueError, IndexError):
                    pass

        # Expiry/term patterns
        term_patterns = [
            r"(?i)(?:term|period)\s+of\s+(\d+)\s+(year|month|day)",
            r"(?i)(?:expire|expir(?:ation|y))\s+(?:date[:\s]+)?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        ]

        for pattern in term_patterns:
            match = re.search(pattern, content)
            if match:
                groups = match.groups()
                if len(groups) == 2 and groups[0].isdigit():
                    # Term duration
                    duration = int(groups[0])
                    unit = groups[1].lower()

                    if effective_date:
                        if "year" in unit:
                            expiry_date = effective_date + timedelta(
                                days=duration * 365
                            )
                        elif "month" in unit:
                            expiry_date = effective_date + timedelta(days=duration * 30)
                        elif "day" in unit:
                            expiry_date = effective_date + timedelta(days=duration)
                    break

        return effective_date, expiry_date

    def _extract_clauses(self, content: str) -> list[Clause]:
        """Extract clauses from contract."""
        clauses = []

        # Split by section headers
        section_pattern = r"(?m)^(\d+(?:\.\d+)*\.?\s+[A-Z][^\n]+)\n"

        sections = re.split(section_pattern, content)

        current_pos = 0
        for i in range(1, len(sections), 2):
            if i + 1 >= len(sections):
                break

            header = sections[i].strip()
            body = sections[i + 1].strip()

            # Extract section number
            num_match = re.match(r"^(\d+(?:\.\d+)*)", header)
            section_num = num_match.group(1) if num_match else ""

            # Determine clause type
            clause_type = ClauseType.OTHER
            for ctype, pattern in self.CLAUSE_PATTERNS.items():
                if re.search(pattern, header):
                    clause_type = ctype
                    break

            clause = Clause(
                id=f"clause_{len(clauses)}",
                clause_type=clause_type,
                title=header,
                content=body[:2000],  # Limit content
                section_number=section_num,
                start_pos=current_pos,
                end_pos=current_pos + len(header) + len(body),
            )
            clauses.append(clause)

            current_pos += len(header) + len(body) + 2

        return clauses

    def _extract_key_terms(self, content: str) -> list[KeyTerm]:
        """Extract defined terms."""
        key_terms = []

        # Pattern for defined terms
        # "Term" means...
        # "Term" shall mean...
        definition_patterns = [
            r'"([A-Z][^"]{2,50})"\s+(?:means?|shall\s+mean|refers?\s+to|is\s+defined\s+as)\s+([^.]+\.)',
            r"([A-Z][A-Za-z\s]{2,30}):\s+([^.]+\.)",
        ]

        for pattern in definition_patterns:
            matches = re.findall(pattern, content)
            for term, definition in matches:
                term = term.strip()
                definition = definition.strip()

                if len(term) > 2 and len(definition) > 10:
                    # Count references
                    references = content.lower().count(term.lower())

                    key_terms.append(
                        KeyTerm(
                            term=term,
                            definition=definition[:500],
                            references=references,
                        )
                    )

        # Sort by frequency
        key_terms.sort(key=lambda t: t.references, reverse=True)

        return key_terms[:20]  # Limit to top 20

    def _identify_risks(self, content: str, clauses: list[Clause]) -> list[RiskItem]:
        """Identify risks in the contract."""
        risks = []
        content_lower = content.lower()

        risk_recommendations = {
            "unlimited_liability": "Consider adding a liability cap.",
            "auto_renewal": "Review auto-renewal terms and add opt-out clause.",
            "termination_penalty": "Negotiate lower termination fees or longer notice period.",
            "one_sided_indemnity": "Request mutual indemnification provisions.",
            "broad_ip_assignment": "Limit IP assignment to deliverables only.",
            "non_compete": "Ensure scope and duration are reasonable.",
            "audit_rights": "Define audit scope, frequency, and cost allocation.",
            "unilateral_changes": "Require mutual agreement for material changes.",
        }

        for risk_category, keywords in self.RISK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    # Find which clause contains this
                    clause_id = ""
                    for clause in clauses:
                        if keyword in clause.content.lower():
                            clause_id = clause.id
                            break

                    # Determine risk level
                    if risk_category in ["unlimited_liability", "broad_ip_assignment"]:
                        level = RiskLevel.HIGH
                        score = 0.8
                    elif risk_category in ["one_sided_indemnity", "non_compete"]:
                        level = RiskLevel.HIGH
                        score = 0.75
                    elif risk_category in ["auto_renewal", "unilateral_changes"]:
                        level = RiskLevel.MEDIUM
                        score = 0.5
                    else:
                        level = RiskLevel.MEDIUM
                        score = 0.45

                    risks.append(
                        RiskItem(
                            id=f"risk_{len(risks)}",
                            clause_id=clause_id,
                            risk_level=level,
                            description=f"Contract contains '{keyword}' language.",
                            recommendation=risk_recommendations.get(
                                risk_category, "Review and consider negotiation."
                            ),
                            keywords=[keyword],
                            score=score,
                        )
                    )
                    break  # Only one risk per category

        return risks

    def _extract_obligations(
        self, content: str, clauses: list[Clause], parties: list[Party]
    ) -> list[Obligation]:
        """Extract obligations from contract."""
        obligations = []

        # Obligation indicators
        obligation_patterns = [
            (
                r"(?i)shall\s+(pay|provide|deliver|submit|report|notify|maintain|ensure)",
                ObligationType.PERFORMANCE,
            ),
            (
                r"(?i)must\s+(pay|provide|deliver|submit|report|notify)",
                ObligationType.COMPLIANCE,
            ),
            (r"(?i)agrees?\s+to\s+(pay|provide|deliver)", ObligationType.PERFORMANCE),
            (
                r"(?i)(?:monthly|quarterly|annual)\s+(?:payment|report|review)",
                ObligationType.REPORTING,
            ),
            (
                r"(?i)within\s+(\d+)\s+(?:day|business\s+day)s?\s+(?:of|after|following)",
                ObligationType.NOTIFICATION,
            ),
        ]

        party_names = [p.name.lower() for p in parties] + [
            p.role.lower() for p in parties
        ]

        for pattern, ob_type in obligation_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Get surrounding context
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 200)
                context = content[start:end]

                # Try to identify responsible party
                responsible = "Unknown"
                for party in party_names:
                    if party in context.lower():
                        responsible = party.title()
                        break

                # Extract description
                description = context[
                    match.start() - start : match.end() - start + 100
                ].strip()
                description = re.sub(r"\s+", " ", description)

                # Find clause reference
                clause_ref = ""
                for clause in clauses:
                    if (
                        match.start() >= clause.start_pos
                        and match.end() <= clause.end_pos
                    ):
                        clause_ref = clause.reference
                        break

                obligations.append(
                    Obligation(
                        id=f"ob_{len(obligations)}",
                        obligation_type=ob_type,
                        description=description[:200],
                        responsible_party=responsible,
                        clause_reference=clause_ref,
                    )
                )

        return obligations[:30]  # Limit


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING AND SEARCH
# ══════════════════════════════════════════════════════════════════════════════


class ContractEmbedder:
    """Generate embeddings for contract content."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._dimension = 384

    def _load_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.model_name)
                self._dimension = self.model.get_sentence_embedding_dimension()
            except ImportError:
                self.model = "mock"

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        self._load_model()

        if self.model == "mock":
            return self._mock_embedding(text)

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def _mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic mock embedding."""
        hash_val = hashlib.md5(text.encode()).hexdigest()

        embedding = []
        for i in range(self._dimension):
            idx = i % len(hash_val)
            val = int(hash_val[idx : idx + 2], 16) / 255.0 - 0.5
            embedding.append(val)

        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    @property
    def dimension(self) -> int:
        return self._dimension


class ContractVectorStore:
    """Vector store for contract clauses."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: dict[str, list[float]] = {}  # clause_id -> vector
        self.metadata: dict[str, dict] = {}  # clause_id -> metadata

    def add(self, clause_id: str, vector: list[float], metadata: dict = None):
        """Add clause vector."""
        self.vectors[clause_id] = vector
        self.metadata[clause_id] = metadata or {}

    def search(
        self, query_vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Search for similar clauses."""
        similarities = []
        for cid, vec in self.vectors.items():
            sim = self._cosine_similarity(query_vector, vec)
            similarities.append((cid, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# ══════════════════════════════════════════════════════════════════════════════
# CONTRACT RAG PIPELINE
# ══════════════════════════════════════════════════════════════════════════════


class ContractRAGPipeline:
    """Complete RAG pipeline for contract analysis."""

    def __init__(self, config: ContractRAGConfig = None):
        self.config = config or ContractRAGConfig()

        # Components
        self.parser = ContractParser()
        self.embedder = ContractEmbedder(self.config.embedding_model)
        self.vector_store = ContractVectorStore(self.config.embedding_dimension)

        # Storage
        self.contracts: dict[str, Contract] = {}
        self.clauses: dict[str, Clause] = {}  # clause_id -> clause
        self.clause_to_contract: dict[str, str] = {}  # clause_id -> contract_id

    def add_contract(
        self, content: str = None, path: str = None, metadata: dict = None
    ) -> Contract:
        """Add a contract to the system."""
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

        if not content:
            raise ValueError("Either content or path must be provided")

        # Parse contract
        contract = self.parser.parse(content, metadata)

        # Generate embeddings for clauses
        for clause in contract.clauses:
            clause.embedding = self.embedder.embed(f"{clause.title}\n{clause.content}")

            self.vector_store.add(
                clause.id,
                clause.embedding,
                {
                    "contract_id": contract.id,
                    "clause_type": clause.clause_type.value,
                    "title": clause.title,
                },
            )

            self.clauses[clause.id] = clause
            self.clause_to_contract[clause.id] = contract.id

        # Generate contract embedding
        contract.embedding = self.embedder.embed(
            f"{contract.title}\n{contract.full_text[:1000]}"
        )

        self.contracts[contract.id] = contract
        return contract

    def search_clauses(
        self, query: str, clause_types: list[ClauseType] = None, top_k: int = None
    ) -> list[tuple[Clause, float]]:
        """Search for relevant clauses."""
        top_k = top_k or self.config.top_k

        query_embedding = self.embedder.embed(query)
        results = self.vector_store.search(query_embedding, top_k * 2)

        clause_results = []
        for clause_id, score in results:
            if clause_id not in self.clauses:
                continue

            clause = self.clauses[clause_id]

            # Filter by type
            if clause_types and clause.clause_type not in clause_types:
                continue

            clause_results.append((clause, score))

        return clause_results[:top_k]

    def analyze_risks(self, contract_id: str) -> list[RiskItem]:
        """Get detailed risk analysis for a contract."""
        if contract_id not in self.contracts:
            return []

        contract = self.contracts[contract_id]

        # Sort risks by level and score
        risks = sorted(
            contract.risks,
            key=lambda r: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3}[r.risk_level.value],
                -r.score,
            ),
        )

        return risks

    def get_obligations(
        self,
        contract_id: str,
        party: str = None,
        obligation_type: ObligationType = None,
    ) -> list[Obligation]:
        """Get obligations from a contract."""
        if contract_id not in self.contracts:
            return []

        contract = self.contracts[contract_id]

        obligations = contract.obligations

        if party:
            obligations = [
                o for o in obligations if party.lower() in o.responsible_party.lower()
            ]

        if obligation_type:
            obligations = [
                o for o in obligations if o.obligation_type == obligation_type
            ]

        return obligations

    def compare_versions(
        self, contract_id_old: str, contract_id_new: str
    ) -> VersionDiff:
        """Compare two versions of a contract."""
        old = self.contracts.get(contract_id_old)
        new = self.contracts.get(contract_id_new)

        if not old or not new:
            return VersionDiff(
                old_version="",
                new_version="",
                added_clauses=[],
                removed_clauses=[],
                modified_clauses=[],
                risk_changes=[],
                summary="One or both contracts not found.",
            )

        # Compare clauses by type
        old_clauses = {c.clause_type: c for c in old.clauses}
        new_clauses = {c.clause_type: c for c in new.clauses}

        old_types = set(old_clauses.keys())
        new_types = set(new_clauses.keys())

        added = new_types - old_types
        removed = old_types - new_types
        common = old_types & new_types

        added_clauses = [new_clauses[t].title for t in added]
        removed_clauses = [old_clauses[t].title for t in removed]

        # Find modified clauses
        modified_clauses = []
        for ctype in common:
            old_content = old_clauses[ctype].content
            new_content = new_clauses[ctype].content

            if old_content != new_content:
                # Calculate similarity
                ratio = difflib.SequenceMatcher(None, old_content, new_content).ratio()
                if ratio < 0.95:
                    modified_clauses.append(
                        (ctype.value, old_content[:100], new_content[:100])
                    )

        # Compare risks
        old_risks = {r.description for r in old.risks}
        new_risks = {r.description for r in new.risks}

        risk_changes = []
        for r in new_risks - old_risks:
            risk_changes.append(f"NEW RISK: {r}")
        for r in old_risks - new_risks:
            risk_changes.append(f"RESOLVED: {r}")

        # Generate summary
        summary_parts = []
        if added_clauses:
            summary_parts.append(f"Added {len(added_clauses)} clause(s)")
        if removed_clauses:
            summary_parts.append(f"Removed {len(removed_clauses)} clause(s)")
        if modified_clauses:
            summary_parts.append(f"Modified {len(modified_clauses)} clause(s)")
        if risk_changes:
            summary_parts.append(f"{len(risk_changes)} risk change(s)")

        return VersionDiff(
            old_version=old.version,
            new_version=new.version,
            added_clauses=added_clauses,
            removed_clauses=removed_clauses,
            modified_clauses=modified_clauses,
            risk_changes=risk_changes,
            summary=(
                "; ".join(summary_parts)
                if summary_parts
                else "No significant changes detected."
            ),
        )

    def generate_summary(self, contract_id: str) -> str:
        """Generate a summary of a contract."""
        if contract_id not in self.contracts:
            return "Contract not found."

        contract = self.contracts[contract_id]

        # Risk summary
        risk_counts = Counter(r.risk_level.value for r in contract.risks)

        summary_parts = [
            f"# Contract Summary: {contract.title}",
            "",
            f"**Type:** {contract.contract_type.value.replace('_', ' ').title()}",
            f"**Version:** {contract.version}",
        ]

        if contract.parties:
            summary_parts.append(f"\n**Parties:**")
            for party in contract.parties:
                summary_parts.append(f"- {party.role}: {party.name}")

        if contract.effective_date:
            summary_parts.append(
                f"\n**Effective Date:** {contract.effective_date.strftime('%Y-%m-%d')}"
            )

        if contract.expiry_date:
            summary_parts.append(
                f"**Expiry Date:** {contract.expiry_date.strftime('%Y-%m-%d')}"
            )

        # Key terms
        if contract.key_terms:
            summary_parts.append(f"\n**Key Terms ({len(contract.key_terms)}):**")
            for term in contract.key_terms[:5]:
                summary_parts.append(f"- **{term.term}**: {term.definition[:100]}...")

        # Clauses overview
        summary_parts.append(f"\n**Clauses ({len(contract.clauses)}):**")
        for clause in contract.clauses[:10]:
            summary_parts.append(f"- {clause.reference}: {clause.clause_type.value}")

        # Risk summary
        summary_parts.append(f"\n**Risk Assessment:**")
        for level in [
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
            RiskLevel.MEDIUM,
            RiskLevel.LOW,
        ]:
            count = risk_counts.get(level.value, 0)
            if count > 0:
                summary_parts.append(f"- {level.value.upper()}: {count}")

        if contract.risks:
            summary_parts.append(f"\n**Top Risks:**")
            for risk in contract.risks[:3]:
                summary_parts.append(
                    f"- [{risk.risk_level.value.upper()}] {risk.description}"
                )

        # Obligations
        summary_parts.append(f"\n**Obligations ({len(contract.obligations)}):**")
        ob_counts = Counter(o.obligation_type.value for o in contract.obligations)
        for ob_type, count in ob_counts.most_common():
            summary_parts.append(f"- {ob_type}: {count}")

        return "\n".join(summary_parts)

    def answer_question(self, question: str, contract_id: str = None) -> str:
        """Answer a question about contracts."""
        # Search relevant clauses
        results = self.search_clauses(question)

        if contract_id:
            results = [
                (c, s)
                for c, s in results
                if self.clause_to_contract.get(c.id) == contract_id
            ]

        if not results:
            return "I couldn't find relevant information to answer your question."

        # Build response
        response_parts = ["Based on the contract analysis:\n"]

        for clause, score in results[:3]:
            contract = self.contracts.get(self.clause_to_contract.get(clause.id))

            response_parts.append(
                f"\n**From {clause.reference}** ({clause.clause_type.value}):"
            )
            response_parts.append(f"```\n{clause.content[:300]}...\n```")

            if contract:
                # Add related risks
                related_risks = [r for r in contract.risks if r.clause_id == clause.id]
                if related_risks:
                    response_parts.append(f"⚠️ Risk: {related_risks[0].description}")

        return "\n".join(response_parts)

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        total_risks = sum(len(c.risks) for c in self.contracts.values())
        total_obligations = sum(len(c.obligations) for c in self.contracts.values())

        risk_by_level = Counter()
        for contract in self.contracts.values():
            for risk in contract.risks:
                risk_by_level[risk.risk_level.value] += 1

        return {
            "contracts": len(self.contracts),
            "clauses": len(self.clauses),
            "total_risks": total_risks,
            "total_obligations": total_obligations,
            "risks_by_level": dict(risk_by_level),
        }


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE CONTRACTS FOR DEMO
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_CONTRACTS = [
    {
        "metadata": {
            "title": "Software Development Services Agreement",
            "version": "1.0",
        },
        "content": """SOFTWARE DEVELOPMENT SERVICES AGREEMENT

This Software Development Services Agreement ("Agreement") is entered into as of January 15, 2024 ("Effective Date") between:

TechCorp Inc., a Delaware corporation ("Client")

and

DevStudio LLC, a California limited liability company ("Provider")

1. DEFINITIONS

1.1 "Deliverables" means all software, code, documentation, and other work product developed by Provider under this Agreement.

1.2 "Services" means the software development services described in Exhibit A.

1.3 "Confidential Information" means any non-public information disclosed by either party.

2. SCOPE OF SERVICES

2.1 Provider agrees to perform the Services described in Exhibit A in accordance with the specifications and timeline set forth therein.

2.2 Provider shall assign qualified personnel to perform the Services.

3. TERM AND TERMINATION

3.1 This Agreement shall commence on the Effective Date and continue for a period of twelve (12) months, unless earlier terminated.

3.2 Either party may terminate this Agreement for cause upon thirty (30) days written notice if the other party materially breaches this Agreement and fails to cure such breach.

3.3 Client may terminate this Agreement for convenience upon sixty (60) days written notice, subject to payment of all fees earned through the termination date plus an early termination fee equal to 25% of the remaining contract value.

4. PAYMENT TERMS

4.1 Client shall pay Provider the fees set forth in Exhibit B.

4.2 Invoices are due within thirty (30) days of receipt.

4.3 Late payments shall accrue interest at 1.5% per month.

5. INTELLECTUAL PROPERTY

5.1 Client shall own all rights, title, and interest in and to the Deliverables upon payment in full.

5.2 Provider assigns to Client all intellectual property rights in the Deliverables, including all patent rights, copyrights, and trade secrets.

5.3 Provider retains ownership of all pre-existing materials and tools.

6. CONFIDENTIALITY

6.1 Each party agrees to maintain the confidentiality of the other party's Confidential Information.

6.2 Confidential Information shall not be disclosed to third parties without prior written consent.

6.3 This confidentiality obligation shall survive termination for a period of five (5) years.

7. WARRANTIES

7.1 Provider warrants that the Services will be performed in a professional and workmanlike manner.

7.2 Provider warrants that the Deliverables will conform to the specifications for a period of ninety (90) days following acceptance.

7.3 EXCEPT AS EXPRESSLY SET FORTH HEREIN, PROVIDER MAKES NO OTHER WARRANTIES, EXPRESS OR IMPLIED.

8. LIMITATION OF LIABILITY

8.1 IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES.

8.2 Provider's total liability under this Agreement shall not exceed the fees paid by Client in the twelve (12) months preceding the claim.

9. INDEMNIFICATION

9.1 Provider shall indemnify, defend, and hold harmless Client from any claims arising from Provider's breach of this Agreement.

9.2 Client shall indemnify Provider from claims arising from Client's use of the Deliverables.

10. DISPUTE RESOLUTION

10.1 Any disputes shall be resolved through binding arbitration in San Francisco, California.

10.2 The arbitration shall be conducted under the rules of the American Arbitration Association.

11. GOVERNING LAW

This Agreement shall be governed by the laws of the State of California.

12. ENTIRE AGREEMENT

This Agreement constitutes the entire agreement between the parties and supersedes all prior agreements.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.

TechCorp Inc.                    DevStudio LLC
By: _____________________        By: _____________________
Name:                            Name:
Title:                           Title:
Date:                            Date:
""",
    },
    {
        "metadata": {
            "title": "Software Development Services Agreement",
            "version": "2.0",
        },
        "content": """SOFTWARE DEVELOPMENT SERVICES AGREEMENT (Version 2.0)

This Software Development Services Agreement ("Agreement") is entered into as of March 1, 2024 ("Effective Date") between:

TechCorp Inc., a Delaware corporation ("Client")

and

DevStudio LLC, a California limited liability company ("Provider")

1. DEFINITIONS

1.1 "Deliverables" means all software, code, documentation, and other work product developed by Provider under this Agreement.

1.2 "Services" means the software development services described in Exhibit A.

1.3 "Confidential Information" means any non-public information disclosed by either party.

1.4 "Acceptance Criteria" means the criteria set forth in Exhibit A for accepting Deliverables.

2. SCOPE OF SERVICES

2.1 Provider agrees to perform the Services described in Exhibit A in accordance with the specifications and timeline set forth therein.

2.2 Provider shall assign qualified personnel to perform the Services.

2.3 Provider shall provide weekly status reports to Client.

3. TERM AND TERMINATION

3.1 This Agreement shall commence on the Effective Date and continue for a period of twelve (12) months, unless earlier terminated.

3.2 Either party may terminate this Agreement for cause upon thirty (30) days written notice if the other party materially breaches this Agreement and fails to cure such breach.

3.3 Client may terminate this Agreement for convenience upon thirty (30) days written notice, subject to payment of all fees earned through the termination date.

4. PAYMENT TERMS

4.1 Client shall pay Provider the fees set forth in Exhibit B.

4.2 Invoices are due within thirty (30) days of receipt.

4.3 Late payments shall accrue interest at 1% per month.

5. INTELLECTUAL PROPERTY

5.1 Client shall own all rights, title, and interest in and to the Deliverables upon payment in full.

5.2 Provider assigns to Client all intellectual property rights in the Deliverables.

5.3 Provider retains ownership of all pre-existing materials and tools.

5.4 Provider grants Client a perpetual license to use Provider's pre-existing materials incorporated in Deliverables.

6. CONFIDENTIALITY

6.1 Each party agrees to maintain the confidentiality of the other party's Confidential Information.

6.2 Confidential Information shall not be disclosed to third parties without prior written consent.

6.3 This confidentiality obligation shall survive termination for a period of three (3) years.

7. WARRANTIES

7.1 Provider warrants that the Services will be performed in a professional and workmanlike manner.

7.2 Provider warrants that the Deliverables will conform to the specifications for a period of one hundred eighty (180) days following acceptance.

7.3 EXCEPT AS EXPRESSLY SET FORTH HEREIN, PROVIDER MAKES NO OTHER WARRANTIES, EXPRESS OR IMPLIED.

8. LIMITATION OF LIABILITY

8.1 IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES.

8.2 Each party's total liability under this Agreement shall not exceed the fees paid by Client in the twelve (12) months preceding the claim.

9. INDEMNIFICATION

9.1 Each party shall indemnify and hold harmless the other party from any claims arising from such party's breach of this Agreement.

10. DISPUTE RESOLUTION

10.1 Any disputes shall first be subject to mediation.

10.2 If mediation fails, disputes shall be resolved through binding arbitration in San Francisco, California.

11. GOVERNING LAW

This Agreement shall be governed by the laws of the State of California.

12. ENTIRE AGREEMENT

This Agreement constitutes the entire agreement between the parties and supersedes all prior agreements.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.

TechCorp Inc.                    DevStudio LLC
By: _____________________        By: _____________________
""",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run interactive contract analysis demo."""
    print("=" * 70)
    print("⚖️ Contract Analysis System - RAG Demo")
    print("=" * 70)

    # Create pipeline
    config = ContractRAGConfig(top_k=5)
    pipeline = ContractRAGPipeline(config)

    # Load sample contracts
    print("\n📄 Loading contracts...")

    contract_ids = []
    for contract_data in SAMPLE_CONTRACTS:
        contract = pipeline.add_contract(
            content=contract_data["content"], metadata=contract_data["metadata"]
        )
        contract_ids.append(contract.id)
        print(f"  ✅ {contract.title} v{contract.version}")
        print(
            f"     - {len(contract.clauses)} clauses, {len(contract.risks)} risks, {len(contract.obligations)} obligations"
        )

    # Show stats
    stats = pipeline.get_stats()
    print(f"\n📊 Analysis Stats:")
    print(f"   Contracts: {stats['contracts']}")
    print(f"   Clauses: {stats['clauses']}")
    print(f"   Total Risks: {stats['total_risks']}")
    print(f"   Risk Distribution: {stats['risks_by_level']}")

    # Sample queries
    sample_queries = [
        "What are the payment terms?",
        "How can the contract be terminated?",
        "What are the liability limits?",
        "What warranties does the provider offer?",
    ]

    print("\n" + "=" * 70)
    print("💡 Sample questions:")
    for q in sample_queries:
        print(f"   • {q}")

    # Interactive loop
    print("\n" + "=" * 70)
    print("💬 Ask about contracts (type 'quit' to exit)")
    print("   Commands:")
    print("   • 'summary' - get contract summary")
    print("   • 'risks' - view risk analysis")
    print("   • 'obligations' - view obligations")
    print("   • 'compare' - compare versions")
    print("   • 'list' - list contracts")
    print("=" * 70)

    while True:
        try:
            query = input("\n❓ Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query:
            continue

        if query.lower() == "quit":
            break

        if query.lower() == "list":
            print("\n📋 Contracts:")
            for cid, contract in pipeline.contracts.items():
                print(f"   [{cid[:8]}] {contract.title} v{contract.version}")
            continue

        if query.lower() == "summary":
            cid = contract_ids[0] if contract_ids else None
            if cid:
                summary = pipeline.generate_summary(cid)
                print(f"\n{summary}")
            continue

        if query.lower() == "risks":
            cid = contract_ids[0] if contract_ids else None
            if cid:
                risks = pipeline.analyze_risks(cid)
                print(f"\n⚠️ Risk Analysis:")
                for risk in risks:
                    level_emoji = {
                        "critical": "🔴",
                        "high": "🟠",
                        "medium": "🟡",
                        "low": "🟢",
                    }
                    emoji = level_emoji.get(risk.risk_level.value, "⚪")
                    print(
                        f"\n   {emoji} [{risk.risk_level.value.upper()}] {risk.description}"
                    )
                    print(f"      Recommendation: {risk.recommendation}")
            continue

        if query.lower() == "obligations":
            cid = contract_ids[0] if contract_ids else None
            if cid:
                obligations = pipeline.get_obligations(cid)
                print(f"\n📋 Obligations ({len(obligations)}):")
                for ob in obligations[:10]:
                    print(f"\n   • [{ob.obligation_type.value}] {ob.description[:100]}")
                    print(f"     Responsible: {ob.responsible_party}")
                    if ob.clause_reference:
                        print(f"     Reference: {ob.clause_reference}")
            continue

        if query.lower() == "compare":
            if len(contract_ids) >= 2:
                diff = pipeline.compare_versions(contract_ids[0], contract_ids[1])
                print(
                    f"\n📊 Version Comparison: {diff.old_version} → {diff.new_version}"
                )
                print(f"\n   Summary: {diff.summary}")

                if diff.added_clauses:
                    print(f"\n   ➕ Added: {', '.join(diff.added_clauses)}")
                if diff.removed_clauses:
                    print(f"\n   ➖ Removed: {', '.join(diff.removed_clauses)}")
                if diff.modified_clauses:
                    print(f"\n   ✏️ Modified:")
                    for clause_type, old, new in diff.modified_clauses[:3]:
                        print(f"      - {clause_type}")
                if diff.risk_changes:
                    print(f"\n   ⚠️ Risk Changes:")
                    for change in diff.risk_changes[:5]:
                        print(f"      - {change}")
            else:
                print("❌ Need at least 2 contract versions to compare")
            continue

        # Regular question
        answer = pipeline.answer_question(query)
        print(f"\n🤖 {answer}")

    print("\n👋 Goodbye!")


def main():
    """Main entry point."""
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    run_demo()


if __name__ == "__main__":
    main()
