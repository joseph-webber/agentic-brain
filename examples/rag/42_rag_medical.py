#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 42: Healthcare Information Assistant RAG System

A comprehensive healthcare information assistant with proper medical
terminology handling and safety disclaimers:
- Medical terminology processing and normalization
- Drug interaction checking with safety alerts
- Symptom analysis (with prominent disclaimers)
- Provider directory search
- Appointment preparation assistance
- Health record summarization

⚠️ IMPORTANT DISCLAIMERS ⚠️
This is a DEMONSTRATION system only. It does NOT provide medical advice.
Always consult qualified healthcare professionals for medical decisions.
Never use this system for emergency medical situations.

Key RAG features demonstrated:
- Medical concept extraction and linking
- Drug-drug interaction knowledge base
- Symptom-condition mapping with confidence
- Hybrid search (semantic + keyword + medical codes)
- Safety-first response generation
- Citation of medical sources
- Evaluation metrics (relevance, safety, accuracy)

Demo: General health information assistant with safety guardrails

Usage:
    python examples/42_rag_medical.py
    python examples/42_rag_medical.py --demo  # Run with sample data

Requirements:
    pip install agentic-brain sentence-transformers faiss-cpu
"""

import asyncio
import hashlib
import json
import math
import os
import re
import tempfile
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generator, Optional

# Try importing optional dependencies
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("⚠️ NumPy not available, using mock vectors")


# ══════════════════════════════════════════════════════════════════════════════
# SAFETY DISCLAIMERS - CRITICAL
# ══════════════════════════════════════════════════════════════════════════════

MEDICAL_DISCLAIMER = """
⚠️ IMPORTANT MEDICAL DISCLAIMER ⚠️

This information is for EDUCATIONAL PURPOSES ONLY and is NOT a substitute
for professional medical advice, diagnosis, or treatment.

• ALWAYS consult with a qualified healthcare provider for medical concerns
• NEVER delay seeking medical help based on information from this system
• In case of EMERGENCY, call emergency services immediately (000 in Australia)
• Drug information may not include all interactions or contraindications
• Symptoms described may indicate various conditions - only a doctor can diagnose

This system does NOT store or transmit personal health information.
"""

EMERGENCY_WARNING = """
🚨 EMERGENCY DETECTED 🚨

If you or someone else is experiencing a medical emergency:
• Call 000 (Australia) or your local emergency number IMMEDIATELY
• Do not wait for AI responses
• Describe your location and symptoms to the operator

Common emergencies requiring immediate help:
• Chest pain or difficulty breathing
• Severe bleeding or trauma
• Loss of consciousness
• Signs of stroke (face drooping, arm weakness, speech difficulty)
• Severe allergic reactions
• Overdose or poisoning
"""


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class MedicalRAGConfig:
    """Configuration for the Medical RAG pipeline."""

    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Chunking settings
    chunk_size: int = 512
    chunk_overlap: int = 100  # Higher overlap for medical content
    min_chunk_size: int = 150

    # Retrieval settings
    top_k: int = 5
    rerank_top_k: int = 3
    similarity_threshold: float = 0.35  # Higher threshold for medical accuracy

    # Hybrid search weights
    semantic_weight: float = 0.6
    keyword_weight: float = 0.25
    medical_code_weight: float = 0.15  # Weight for ICD/SNOMED codes

    # Safety settings
    require_disclaimer: bool = True
    max_symptom_conditions: int = 5  # Don't overwhelm with possibilities
    drug_interaction_strictness: str = "high"  # low, medium, high

    # LLM settings
    max_context_tokens: int = 4000
    temperature: float = 0.1  # Low for medical accuracy


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS AND DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class MedicalContentType(Enum):
    """Types of medical content."""

    DRUG_INFO = "drug_info"
    CONDITION = "condition"
    SYMPTOM = "symptom"
    PROCEDURE = "procedure"
    PROVIDER = "provider"
    GUIDELINE = "guideline"
    PATIENT_ED = "patient_education"
    INTERACTION = "drug_interaction"


class SeverityLevel(Enum):
    """Severity levels for medical information."""

    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class InteractionSeverity(Enum):
    """Drug interaction severity levels."""

    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CONTRAINDICATED = "contraindicated"


@dataclass
class MedicalConcept:
    """Represents a medical concept (drug, condition, symptom, etc.)."""

    concept_id: str
    name: str
    concept_type: MedicalContentType
    synonyms: list[str] = field(default_factory=list)
    codes: dict[str, str] = field(default_factory=dict)  # ICD-10, SNOMED, RxNorm
    description: str = ""
    related_concepts: list[str] = field(default_factory=list)


@dataclass
class DrugInfo:
    """Drug information record."""

    drug_id: str
    generic_name: str
    brand_names: list[str]
    drug_class: str
    mechanism: str
    indications: list[str]
    contraindications: list[str]
    side_effects: list[dict[str, Any]]  # {effect, frequency, severity}
    interactions: list[str]  # Drug IDs
    dosage_forms: list[str]
    warnings: list[str]
    pregnancy_category: str = "Unknown"


@dataclass
class DrugInteraction:
    """Drug-drug interaction record."""

    drug_a_id: str
    drug_b_id: str
    severity: InteractionSeverity
    description: str
    mechanism: str
    clinical_effects: list[str]
    management: str
    evidence_level: str  # established, theoretical, case_report


@dataclass
class Condition:
    """Medical condition/disease record."""

    condition_id: str
    name: str
    icd10_codes: list[str]
    description: str
    symptoms: list[str]
    risk_factors: list[str]
    treatments: list[str]
    when_to_seek_help: list[str]
    prevention: list[str]
    prognosis: str = ""


@dataclass
class Provider:
    """Healthcare provider record."""

    provider_id: str
    name: str
    specialty: str
    qualifications: list[str]
    languages: list[str]
    accepting_patients: bool
    telehealth_available: bool
    location: dict[str, str]  # {address, city, state, postcode}
    contact: dict[str, str]  # {phone, email, website}
    hours: dict[str, str]  # {monday: "9am-5pm", ...}
    insurance_accepted: list[str]


@dataclass
class MedicalChunk:
    """A chunk of medical content for the knowledge base."""

    chunk_id: str
    content: str
    content_type: MedicalContentType
    source_document: str
    source_section: str
    medical_concepts: list[str]  # Concept IDs mentioned
    codes: dict[str, list[str]]  # Medical codes in this chunk
    embedding: Optional[list[float]] = None
    severity_level: SeverityLevel = SeverityLevel.INFO
    last_updated: str = ""
    review_status: str = "pending"  # pending, reviewed, approved


@dataclass
class RetrievedMedicalContext:
    """A retrieved chunk with relevance info."""

    chunk: MedicalChunk
    score: float
    match_type: str  # semantic, keyword, code_match, hybrid
    matched_concepts: list[str] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)


@dataclass
class MedicalQueryResult:
    """Result from the medical RAG pipeline."""

    answer: str
    disclaimer: str
    sources: list[RetrievedMedicalContext]
    detected_concepts: list[MedicalConcept]
    safety_level: SeverityLevel
    confidence: float
    requires_professional: bool
    drug_interactions: list[DrugInteraction]
    related_topics: list[str]
    latency_ms: float


@dataclass
class EvaluationMetrics:
    """Metrics for evaluating medical RAG responses."""

    relevance_score: float  # How relevant is the answer
    safety_score: float  # Are proper disclaimers included
    accuracy_score: float  # Factual accuracy
    completeness: float  # Does it address the question
    citation_quality: float  # Are sources properly cited
    response_time_ms: float


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING MANAGER
# ══════════════════════════════════════════════════════════════════════════════


class MedicalEmbeddingManager:
    """Manages embeddings for medical content."""

    def __init__(self, config: MedicalRAGConfig):
        self.config = config
        self.model = None
        self._initialized = False

    def initialize(self):
        """Initialize the embedding model."""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer

            # Use medical-tuned model if available
            try:
                self.model = SentenceTransformer("pritamdeka/S-PubMedBert-MS-MARCO")
                print("✅ Loaded medical-specialized embedding model")
            except Exception:
                self.model = SentenceTransformer(self.config.embedding_model)
                print(
                    f"✅ Loaded general embedding model: {self.config.embedding_model}"
                )
            self._initialized = True
        except ImportError:
            print("⚠️ sentence-transformers not available, using mock embeddings")
            self._initialized = True

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        self.initialize()

        if self.model:
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        else:
            # Mock embedding for demo
            return self._mock_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        self.initialize()

        if self.model:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()
        else:
            return [self._mock_embed(t) for t in texts]

    def _mock_embed(self, text: str) -> list[float]:
        """Create deterministic mock embedding."""
        import hashlib

        hash_val = hashlib.md5(text.encode()).hexdigest()
        seed = int(hash_val[:8], 16)

        if HAS_NUMPY:
            np.random.seed(seed)
            vec = np.random.randn(self.config.embedding_dimension)
            return (vec / np.linalg.norm(vec)).tolist()
        else:
            import random

            random.seed(seed)
            vec = [random.gauss(0, 1) for _ in range(self.config.embedding_dimension)]
            norm = math.sqrt(sum(x * x for x in vec))
            return [x / norm for x in vec]


# ══════════════════════════════════════════════════════════════════════════════
# MEDICAL CONCEPT EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════


class MedicalConceptExtractor:
    """Extracts and normalizes medical concepts from text."""

    def __init__(self):
        # Common drug names and synonyms
        self.drug_synonyms = {
            "aspirin": ["asa", "acetylsalicylic acid", "aspro"],
            "ibuprofen": ["advil", "nurofen", "motrin"],
            "paracetamol": ["acetaminophen", "tylenol", "panadol"],
            "metformin": ["glucophage", "diabex", "diaformin"],
            "omeprazole": ["losec", "prilosec", "acimax"],
            "amoxicillin": ["amoxil", "augmentin"],
            "atorvastatin": ["lipitor", "atorva"],
            "lisinopril": ["prinivil", "zestril"],
            "metoprolol": ["betaloc", "lopressor"],
            "sertraline": ["zoloft", "setrona"],
        }

        # Common symptoms
        self.symptom_patterns = [
            r"\b(headache|migraine|head\s*pain)\b",
            r"\b(fever|temperature|pyrexia)\b",
            r"\b(cough|coughing)\b",
            r"\b(fatigue|tired|exhausted|lethargy)\b",
            r"\b(nausea|vomiting|sick)\b",
            r"\b(chest\s*pain|angina)\b",
            r"\b(shortness\s*of\s*breath|dyspnea|breathless)\b",
            r"\b(dizziness|vertigo|lightheaded)\b",
            r"\b(rash|hives|skin\s*irritation)\b",
            r"\b(joint\s*pain|arthralgia)\b",
        ]

        # Emergency keywords
        self.emergency_keywords = [
            "emergency",
            "urgent",
            "severe",
            "call 000",
            "ambulance",
            "can't breathe",
            "chest pain",
            "stroke",
            "heart attack",
            "unconscious",
            "overdose",
            "suicide",
            "bleeding heavily",
            "allergic reaction",
            "anaphylaxis",
        ]

    def extract_concepts(self, text: str) -> list[MedicalConcept]:
        """Extract medical concepts from text."""
        concepts = []
        text_lower = text.lower()

        # Extract drug mentions
        for generic, synonyms in self.drug_synonyms.items():
            all_names = [generic] + synonyms
            for name in all_names:
                if name in text_lower:
                    concepts.append(
                        MedicalConcept(
                            concept_id=f"drug_{generic}",
                            name=generic.title(),
                            concept_type=MedicalContentType.DRUG_INFO,
                            synonyms=synonyms,
                        )
                    )
                    break

        # Extract symptoms
        for pattern in self.symptom_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                symptom_name = match if isinstance(match, str) else match[0]
                concepts.append(
                    MedicalConcept(
                        concept_id=f"symptom_{symptom_name.replace(' ', '_')}",
                        name=symptom_name.title(),
                        concept_type=MedicalContentType.SYMPTOM,
                    )
                )

        return concepts

    def detect_emergency(self, text: str) -> bool:
        """Detect if text contains emergency-related content."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.emergency_keywords)

    def normalize_drug_name(self, name: str) -> str:
        """Normalize drug name to generic form."""
        name_lower = name.lower()

        for generic, synonyms in self.drug_synonyms.items():
            if name_lower == generic or name_lower in synonyms:
                return generic

        return name_lower


# ══════════════════════════════════════════════════════════════════════════════
# DRUG INTERACTION CHECKER
# ══════════════════════════════════════════════════════════════════════════════


class DrugInteractionChecker:
    """Checks for drug-drug interactions."""

    def __init__(self):
        # Sample interaction database
        self.interactions = self._load_interactions()

    def _load_interactions(self) -> dict[tuple[str, str], DrugInteraction]:
        """Load drug interaction database."""
        interactions = {}

        # Sample interactions (real system would use comprehensive database)
        sample_interactions = [
            {
                "drug_a": "aspirin",
                "drug_b": "ibuprofen",
                "severity": InteractionSeverity.MODERATE,
                "description": "Concurrent use may increase risk of gastrointestinal bleeding",
                "mechanism": "Both drugs inhibit cyclooxygenase, affecting platelet function",
                "effects": ["Increased bleeding risk", "GI ulceration"],
                "management": "Avoid combination if possible. If necessary, use lowest effective doses.",
                "evidence": "established",
            },
            {
                "drug_a": "metformin",
                "drug_b": "alcohol",
                "severity": InteractionSeverity.MAJOR,
                "description": "Alcohol increases risk of lactic acidosis with metformin",
                "mechanism": "Alcohol inhibits gluconeogenesis and may worsen metformin-induced lactate accumulation",
                "effects": ["Lactic acidosis", "Hypoglycemia"],
                "management": "Limit alcohol intake. Avoid binge drinking.",
                "evidence": "established",
            },
            {
                "drug_a": "sertraline",
                "drug_b": "aspirin",
                "severity": InteractionSeverity.MODERATE,
                "description": "SSRIs may increase bleeding risk when combined with NSAIDs/aspirin",
                "mechanism": "SSRIs inhibit serotonin uptake by platelets",
                "effects": ["Increased bleeding risk", "GI bleeding"],
                "management": "Monitor for signs of bleeding. Consider gastroprotection.",
                "evidence": "established",
            },
            {
                "drug_a": "lisinopril",
                "drug_b": "potassium",
                "severity": InteractionSeverity.MAJOR,
                "description": "ACE inhibitors reduce aldosterone, causing potassium retention",
                "mechanism": "ACE inhibitors reduce aldosterone secretion",
                "effects": ["Hyperkalemia", "Cardiac arrhythmias"],
                "management": "Monitor potassium levels. Avoid potassium supplements unless prescribed.",
                "evidence": "established",
            },
            {
                "drug_a": "atorvastatin",
                "drug_b": "grapefruit",
                "severity": InteractionSeverity.MODERATE,
                "description": "Grapefruit inhibits metabolism of atorvastatin",
                "mechanism": "Grapefruit juice inhibits CYP3A4 in the gut wall",
                "effects": ["Increased statin levels", "Risk of myopathy"],
                "management": "Avoid grapefruit juice or limit intake significantly.",
                "evidence": "established",
            },
        ]

        for data in sample_interactions:
            key = tuple(sorted([data["drug_a"], data["drug_b"]]))
            interactions[key] = DrugInteraction(
                drug_a_id=data["drug_a"],
                drug_b_id=data["drug_b"],
                severity=data["severity"],
                description=data["description"],
                mechanism=data["mechanism"],
                clinical_effects=data["effects"],
                management=data["management"],
                evidence_level=data["evidence"],
            )

        return interactions

    def check_interactions(self, drugs: list[str]) -> list[DrugInteraction]:
        """Check for interactions between a list of drugs."""
        interactions_found = []

        # Normalize drug names
        normalized = [d.lower() for d in drugs]

        # Check all pairs
        for i, drug_a in enumerate(normalized):
            for drug_b in normalized[i + 1 :]:
                key = tuple(sorted([drug_a, drug_b]))
                if key in self.interactions:
                    interactions_found.append(self.interactions[key])

        # Sort by severity
        severity_order = {
            InteractionSeverity.CONTRAINDICATED: 0,
            InteractionSeverity.MAJOR: 1,
            InteractionSeverity.MODERATE: 2,
            InteractionSeverity.MINOR: 3,
            InteractionSeverity.NONE: 4,
        }

        interactions_found.sort(key=lambda x: severity_order[x.severity])

        return interactions_found

    def format_interaction_warning(self, interaction: DrugInteraction) -> str:
        """Format interaction as warning text."""
        severity_icons = {
            InteractionSeverity.CONTRAINDICATED: "🚫",
            InteractionSeverity.MAJOR: "⛔",
            InteractionSeverity.MODERATE: "⚠️",
            InteractionSeverity.MINOR: "ℹ️",
            InteractionSeverity.NONE: "✅",
        }

        icon = severity_icons.get(interaction.severity, "❓")

        return f"""
{icon} {interaction.severity.value.upper()} INTERACTION: {interaction.drug_a_id.title()} + {interaction.drug_b_id.title()}

{interaction.description}

Mechanism: {interaction.mechanism}

Potential Effects:
{chr(10).join(f'  • {effect}' for effect in interaction.clinical_effects)}

Management: {interaction.management}

Evidence Level: {interaction.evidence_level}
"""


# ══════════════════════════════════════════════════════════════════════════════
# SYMPTOM ANALYZER
# ══════════════════════════════════════════════════════════════════════════════


class SymptomAnalyzer:
    """Analyzes symptoms and suggests possible conditions."""

    def __init__(self):
        # Symptom-condition mappings (simplified for demo)
        self.symptom_conditions = self._load_mappings()

    def _load_mappings(self) -> dict[str, list[dict]]:
        """Load symptom-condition mappings."""
        return {
            "headache": [
                {
                    "condition": "Tension headache",
                    "likelihood": 0.4,
                    "severity": "mild",
                },
                {"condition": "Migraine", "likelihood": 0.25, "severity": "moderate"},
                {"condition": "Dehydration", "likelihood": 0.15, "severity": "mild"},
                {"condition": "Sinusitis", "likelihood": 0.1, "severity": "mild"},
                {"condition": "Eye strain", "likelihood": 0.1, "severity": "mild"},
            ],
            "fever": [
                {"condition": "Viral infection", "likelihood": 0.5, "severity": "mild"},
                {
                    "condition": "Bacterial infection",
                    "likelihood": 0.2,
                    "severity": "moderate",
                },
                {
                    "condition": "Flu (Influenza)",
                    "likelihood": 0.15,
                    "severity": "moderate",
                },
                {"condition": "COVID-19", "likelihood": 0.1, "severity": "varies"},
                {
                    "condition": "Other infection",
                    "likelihood": 0.05,
                    "severity": "varies",
                },
            ],
            "cough": [
                {"condition": "Common cold", "likelihood": 0.4, "severity": "mild"},
                {"condition": "Allergies", "likelihood": 0.2, "severity": "mild"},
                {"condition": "Bronchitis", "likelihood": 0.15, "severity": "moderate"},
                {"condition": "Asthma", "likelihood": 0.1, "severity": "varies"},
                {
                    "condition": "Post-nasal drip",
                    "likelihood": 0.15,
                    "severity": "mild",
                },
            ],
            "fatigue": [
                {
                    "condition": "Sleep deprivation",
                    "likelihood": 0.3,
                    "severity": "mild",
                },
                {"condition": "Stress/Anxiety", "likelihood": 0.25, "severity": "mild"},
                {
                    "condition": "Iron deficiency",
                    "likelihood": 0.15,
                    "severity": "moderate",
                },
                {"condition": "Viral illness", "likelihood": 0.15, "severity": "mild"},
                {"condition": "Depression", "likelihood": 0.1, "severity": "moderate"},
                {
                    "condition": "Thyroid issues",
                    "likelihood": 0.05,
                    "severity": "moderate",
                },
            ],
            "chest pain": [
                {"condition": "Muscle strain", "likelihood": 0.3, "severity": "mild"},
                {
                    "condition": "Acid reflux (GERD)",
                    "likelihood": 0.25,
                    "severity": "mild",
                },
                {"condition": "Anxiety/Panic", "likelihood": 0.2, "severity": "mild"},
                {"condition": "Costochondritis", "likelihood": 0.1, "severity": "mild"},
                {
                    "condition": "Cardiac condition",
                    "likelihood": 0.1,
                    "severity": "serious",
                },
                {
                    "condition": "Pulmonary condition",
                    "likelihood": 0.05,
                    "severity": "serious",
                },
            ],
        }

    def analyze_symptoms(
        self, symptoms: list[str], max_conditions: int = 5
    ) -> dict[str, Any]:
        """Analyze symptoms and return possible conditions."""
        all_conditions = {}

        for symptom in symptoms:
            symptom_lower = symptom.lower()

            # Find matching symptom
            for key, conditions in self.symptom_conditions.items():
                if key in symptom_lower or symptom_lower in key:
                    for cond in conditions:
                        name = cond["condition"]
                        if name not in all_conditions:
                            all_conditions[name] = {
                                "symptoms_matched": [],
                                "cumulative_likelihood": 0,
                                "severity": cond["severity"],
                            }
                        all_conditions[name]["symptoms_matched"].append(symptom)
                        all_conditions[name]["cumulative_likelihood"] += cond[
                            "likelihood"
                        ]

        # Sort by likelihood
        sorted_conditions = sorted(
            all_conditions.items(),
            key=lambda x: x[1]["cumulative_likelihood"],
            reverse=True,
        )[:max_conditions]

        return {
            "analyzed_symptoms": symptoms,
            "possible_conditions": [
                {
                    "name": name,
                    "confidence": min(data["cumulative_likelihood"], 1.0),
                    "severity": data["severity"],
                    "matching_symptoms": data["symptoms_matched"],
                }
                for name, data in sorted_conditions
            ],
            "disclaimer": (
                "These are GENERAL possibilities only. Many conditions share "
                "similar symptoms. Only a qualified healthcare provider can "
                "make an accurate diagnosis based on examination and tests."
            ),
            "when_to_seek_help": self._get_seek_help_advice(symptoms),
        }

    def _get_seek_help_advice(self, symptoms: list[str]) -> list[str]:
        """Get advice on when to seek professional help."""
        advice = [
            "Symptoms persist for more than a few days",
            "Symptoms are severe or getting worse",
            "You have underlying health conditions",
            "You are taking medications that might interact",
            "You are unsure about the cause",
        ]

        # Add symptom-specific advice
        symptoms_lower = " ".join(symptoms).lower()

        if "chest" in symptoms_lower:
            advice.insert(
                0,
                "⚠️ Chest pain with shortness of breath, sweating, or arm pain - CALL 000",
            )

        if "fever" in symptoms_lower:
            advice.append("Fever above 39°C (102°F) or lasting more than 3 days")

        return advice


# ══════════════════════════════════════════════════════════════════════════════
# VECTOR STORE
# ══════════════════════════════════════════════════════════════════════════════


class MedicalVectorStore:
    """Vector store for medical content with hybrid search."""

    def __init__(self, config: MedicalRAGConfig):
        self.config = config
        self.chunks: list[MedicalChunk] = []
        self.embeddings: list[list[float]] = []
        self.concept_index: dict[str, list[int]] = {}  # concept_id -> chunk indices
        self.code_index: dict[str, list[int]] = {}  # medical_code -> chunk indices
        self.keyword_index: dict[str, list[int]] = {}  # keyword -> chunk indices

    def add_chunk(self, chunk: MedicalChunk):
        """Add a chunk to the store."""
        idx = len(self.chunks)
        self.chunks.append(chunk)

        if chunk.embedding:
            self.embeddings.append(chunk.embedding)

        # Index by concepts
        for concept_id in chunk.medical_concepts:
            if concept_id not in self.concept_index:
                self.concept_index[concept_id] = []
            self.concept_index[concept_id].append(idx)

        # Index by medical codes
        for code_type, codes in chunk.codes.items():
            for code in codes:
                code_key = f"{code_type}:{code}"
                if code_key not in self.code_index:
                    self.code_index[code_key] = []
                self.code_index[code_key].append(idx)

        # Build keyword index
        keywords = self._extract_keywords(chunk.content)
        for kw in keywords:
            if kw not in self.keyword_index:
                self.keyword_index[kw] = []
            self.keyword_index[kw].append(idx)

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract medical keywords from text."""
        # Simple keyword extraction
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Filter stop words
        stop_words = {
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "had",
            "her",
            "was",
            "one",
            "our",
            "out",
            "has",
            "have",
            "been",
            "were",
            "said",
            "each",
            "she",
            "which",
            "their",
            "will",
            "other",
            "about",
            "from",
            "this",
            "that",
            "with",
            "your",
            "what",
            "when",
            "there",
            "some",
            "into",
        }

        return {w for w in words if w not in stop_words}

    def semantic_search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[int, float]]:
        """Perform semantic similarity search."""
        if not self.embeddings:
            return []

        scores = []
        for idx, emb in enumerate(self.embeddings):
            score = self._cosine_similarity(query_embedding, emb)
            scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def keyword_search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        """Perform BM25-style keyword search."""
        query_keywords = self._extract_keywords(query)

        scores = {}
        for kw in query_keywords:
            if kw in self.keyword_index:
                for idx in self.keyword_index[kw]:
                    if idx not in scores:
                        scores[idx] = 0
                    # Simple TF-IDF-like scoring
                    idf = math.log(len(self.chunks) / (1 + len(self.keyword_index[kw])))
                    scores[idx] += idf

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Normalize scores
        if sorted_scores:
            max_score = sorted_scores[0][1] if sorted_scores else 1
            sorted_scores = [(idx, score / max_score) for idx, score in sorted_scores]

        return sorted_scores[:top_k]

    def code_search(self, codes: list[str]) -> list[tuple[int, float]]:
        """Search by medical codes."""
        results = {}

        for code in codes:
            if code in self.code_index:
                for idx in self.code_index[code]:
                    if idx not in results:
                        results[idx] = 0
                    results[idx] += 1

        # Normalize
        if results:
            max_matches = max(results.values())
            return [(idx, count / max_matches) for idx, count in results.items()]

        return []

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        codes: list[str] = None,
        top_k: int = 5,
    ) -> list[RetrievedMedicalContext]:
        """Perform hybrid search combining multiple signals."""
        semantic_results = self.semantic_search(query_embedding, top_k * 2)
        keyword_results = self.keyword_search(query, top_k * 2)
        code_results = self.code_search(codes or []) if codes else []

        # Combine scores
        combined_scores = {}

        for idx, score in semantic_results:
            combined_scores[idx] = (
                combined_scores.get(idx, 0) + score * self.config.semantic_weight
            )

        for idx, score in keyword_results:
            combined_scores[idx] = (
                combined_scores.get(idx, 0) + score * self.config.keyword_weight
            )

        for idx, score in code_results:
            combined_scores[idx] = (
                combined_scores.get(idx, 0) + score * self.config.medical_code_weight
            )

        # Sort and filter
        sorted_results = sorted(
            combined_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Build results
        results = []
        for idx, score in sorted_results[:top_k]:
            if score >= self.config.similarity_threshold:
                chunk = self.chunks[idx]

                # Determine match type
                match_type = "hybrid"
                if idx in dict(semantic_results) and idx not in dict(keyword_results):
                    match_type = "semantic"
                elif idx in dict(keyword_results) and idx not in dict(semantic_results):
                    match_type = "keyword"

                results.append(
                    RetrievedMedicalContext(
                        chunk=chunk,
                        score=score,
                        match_type=match_type,
                        matched_concepts=chunk.medical_concepts,
                        safety_flags=self._get_safety_flags(chunk),
                    )
                )

        return results

    def _get_safety_flags(self, chunk: MedicalChunk) -> list[str]:
        """Get safety flags for a chunk."""
        flags = []

        if chunk.severity_level == SeverityLevel.CRITICAL:
            flags.append("CRITICAL_CONTENT")
        elif chunk.severity_level == SeverityLevel.WARNING:
            flags.append("WARNING_CONTENT")

        if chunk.content_type == MedicalContentType.INTERACTION:
            flags.append("DRUG_INTERACTION")

        return flags

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if HAS_NUMPY:
            a_arr = np.array(a)
            b_arr = np.array(b)
            return float(
                np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr))
            )
        else:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0


# ══════════════════════════════════════════════════════════════════════════════
# RERANKER
# ══════════════════════════════════════════════════════════════════════════════


class MedicalReranker:
    """Reranks retrieved results for medical relevance and safety."""

    def __init__(self, config: MedicalRAGConfig):
        self.config = config
        self.model = None
        self._initialized = False

    def initialize(self):
        """Initialize the cross-encoder model."""
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            print("✅ Loaded cross-encoder for reranking")
        except ImportError:
            print("⚠️ CrossEncoder not available, using heuristic reranking")

        self._initialized = True

    def rerank(
        self, query: str, results: list[RetrievedMedicalContext], top_k: int = None
    ) -> list[RetrievedMedicalContext]:
        """Rerank results based on query relevance and safety."""
        self.initialize()
        top_k = top_k or self.config.rerank_top_k

        if not results:
            return []

        if self.model:
            # Use cross-encoder for reranking
            pairs = [(query, r.chunk.content) for r in results]
            scores = self.model.predict(pairs)

            for i, result in enumerate(results):
                # Combine cross-encoder score with safety boosting
                base_score = float(scores[i])
                safety_boost = self._calculate_safety_boost(result)
                result.score = base_score * safety_boost
        else:
            # Heuristic reranking
            for result in results:
                # Boost based on content type relevance
                type_boost = self._get_type_boost(result.chunk.content_type)
                safety_boost = self._calculate_safety_boost(result)
                result.score = result.score * type_boost * safety_boost

        # Sort by updated scores
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

    def _calculate_safety_boost(self, result: RetrievedMedicalContext) -> float:
        """Calculate safety-based score boost."""
        boost = 1.0

        # Boost reviewed/approved content
        if result.chunk.review_status == "approved":
            boost *= 1.2
        elif result.chunk.review_status == "reviewed":
            boost *= 1.1

        # Slight penalty for very old content
        if result.chunk.last_updated:
            try:
                update_date = datetime.fromisoformat(result.chunk.last_updated)
                age_days = (datetime.now() - update_date).days
                if age_days > 365:
                    boost *= 0.9
                elif age_days > 730:
                    boost *= 0.8
            except Exception:
                pass

        return boost

    def _get_type_boost(self, content_type: MedicalContentType) -> float:
        """Get relevance boost based on content type."""
        boosts = {
            MedicalContentType.GUIDELINE: 1.2,
            MedicalContentType.DRUG_INFO: 1.1,
            MedicalContentType.CONDITION: 1.1,
            MedicalContentType.PATIENT_ED: 1.0,
            MedicalContentType.PROCEDURE: 0.95,
            MedicalContentType.PROVIDER: 0.9,
        }
        return boosts.get(content_type, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# RESPONSE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════


class MedicalResponseGenerator:
    """Generates safe, cited responses from medical content."""

    def __init__(self, config: MedicalRAGConfig):
        self.config = config

    def generate(
        self,
        query: str,
        context: list[RetrievedMedicalContext],
        detected_concepts: list[MedicalConcept],
        interactions: list[DrugInteraction],
        is_emergency: bool,
    ) -> MedicalQueryResult:
        """Generate a response with proper citations and disclaimers."""
        start_time = datetime.now()

        # Handle emergency first
        if is_emergency:
            return self._generate_emergency_response(query, start_time)

        # Determine safety level
        safety_level = self._assess_safety_level(context, detected_concepts)

        # Build answer with citations
        answer_parts = []
        sources_used = []

        # Add interaction warnings first if present
        if interactions:
            answer_parts.append("⚠️ **Drug Interaction Warnings:**\n")
            for interaction in interactions[:3]:  # Limit to top 3
                answer_parts.append(
                    f"• **{interaction.drug_a_id.title()} + {interaction.drug_b_id.title()}** "
                    f"({interaction.severity.value}): {interaction.description}"
                )
            answer_parts.append("")

        # Build main answer from context
        if context:
            answer_parts.append("Based on the available information:\n")

            for i, ctx in enumerate(context[:3], 1):
                # Extract key points from chunk
                key_points = self._extract_key_points(ctx.chunk.content, query)
                if key_points:
                    answer_parts.append(f"{key_points} [{i}]")
                    sources_used.append(ctx)
        else:
            answer_parts.append(
                "I don't have specific information to answer this question. "
                "Please consult a healthcare professional for accurate guidance."
            )

        # Combine answer
        answer = "\n".join(answer_parts)

        # Add disclaimer based on safety level
        disclaimer = self._get_disclaimer(safety_level, detected_concepts)

        # Calculate confidence
        confidence = self._calculate_confidence(context, detected_concepts)

        # Determine if professional consultation is needed
        requires_professional = (
            safety_level in [SeverityLevel.WARNING, SeverityLevel.CRITICAL]
            or len(interactions) > 0
            or confidence < 0.5
        )

        # Get related topics
        related = self._get_related_topics(detected_concepts, context)

        latency = (datetime.now() - start_time).total_seconds() * 1000

        return MedicalQueryResult(
            answer=answer,
            disclaimer=disclaimer,
            sources=sources_used,
            detected_concepts=detected_concepts,
            safety_level=safety_level,
            confidence=confidence,
            requires_professional=requires_professional,
            drug_interactions=interactions,
            related_topics=related,
            latency_ms=latency,
        )

    def _generate_emergency_response(
        self, query: str, start_time: datetime
    ) -> MedicalQueryResult:
        """Generate emergency response."""
        latency = (datetime.now() - start_time).total_seconds() * 1000

        return MedicalQueryResult(
            answer=EMERGENCY_WARNING,
            disclaimer="",
            sources=[],
            detected_concepts=[],
            safety_level=SeverityLevel.EMERGENCY,
            confidence=1.0,
            requires_professional=True,
            drug_interactions=[],
            related_topics=[],
            latency_ms=latency,
        )

    def _assess_safety_level(
        self, context: list[RetrievedMedicalContext], concepts: list[MedicalConcept]
    ) -> SeverityLevel:
        """Assess overall safety level of the query."""
        # Check context severity
        if any(c.chunk.severity_level == SeverityLevel.CRITICAL for c in context):
            return SeverityLevel.CRITICAL

        # Check for drug-related queries
        drug_concepts = [
            c for c in concepts if c.concept_type == MedicalContentType.DRUG_INFO
        ]
        if len(drug_concepts) > 1:
            return SeverityLevel.WARNING

        if any(c.chunk.severity_level == SeverityLevel.WARNING for c in context):
            return SeverityLevel.WARNING

        return SeverityLevel.CAUTION

    def _extract_key_points(self, content: str, query: str) -> str:
        """Extract key points from content relevant to query."""
        # Simple extraction - take first 200 chars or first sentence
        sentences = content.split(".")

        # Try to find most relevant sentence
        query_words = set(query.lower().split())
        best_sentence = ""
        best_score = 0

        for sentence in sentences[:5]:
            sentence_words = set(sentence.lower().split())
            overlap = len(query_words & sentence_words)
            if overlap > best_score:
                best_score = overlap
                best_sentence = sentence.strip()

        if best_sentence:
            return best_sentence + "."

        return sentences[0].strip() + "." if sentences else content[:200]

    def _get_disclaimer(
        self, safety_level: SeverityLevel, concepts: list[MedicalConcept]
    ) -> str:
        """Get appropriate disclaimer based on content."""
        if safety_level == SeverityLevel.CRITICAL:
            return (
                "⛔ **IMPORTANT**: This information involves serious health topics. "
                "Please consult a healthcare professional immediately."
            )

        if safety_level == SeverityLevel.WARNING:
            return (
                "⚠️ **Caution**: This information is for educational purposes only. "
                "Do not make health decisions based solely on this content. "
                "Consult a qualified healthcare provider."
            )

        # Check for drug-related content
        drug_concepts = [
            c for c in concepts if c.concept_type == MedicalContentType.DRUG_INFO
        ]
        if drug_concepts:
            return (
                "ℹ️ **Drug Information Disclaimer**: This information is general in nature. "
                "Always follow your healthcare provider's instructions and read the "
                "Consumer Medicine Information (CMI) provided with your medication."
            )

        return (
            "ℹ️ This information is for educational purposes only and should not "
            "replace professional medical advice."
        )

    def _calculate_confidence(
        self, context: list[RetrievedMedicalContext], concepts: list[MedicalConcept]
    ) -> float:
        """Calculate confidence score for the response."""
        if not context:
            return 0.2

        # Base confidence on retrieval scores
        avg_score = sum(c.score for c in context) / len(context)

        # Boost if concepts were detected
        concept_boost = min(0.1 * len(concepts), 0.3)

        # Penalty if content is old or unreviewed
        quality_factor = 1.0
        for ctx in context:
            if ctx.chunk.review_status == "pending":
                quality_factor *= 0.9

        return min(avg_score + concept_boost * quality_factor, 1.0)

    def _get_related_topics(
        self, concepts: list[MedicalConcept], context: list[RetrievedMedicalContext]
    ) -> list[str]:
        """Get related topics for further exploration."""
        related = set()

        for concept in concepts:
            related.update(concept.related_concepts)

        for ctx in context:
            # Extract topic from source
            if ctx.chunk.source_section:
                related.add(ctx.chunk.source_section)

        return list(related)[:5]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RAG PIPELINE
# ══════════════════════════════════════════════════════════════════════════════


class MedicalRAGPipeline:
    """Complete medical RAG pipeline with safety guardrails."""

    def __init__(self, config: MedicalRAGConfig = None):
        self.config = config or MedicalRAGConfig()

        self.embedding_manager = MedicalEmbeddingManager(self.config)
        self.concept_extractor = MedicalConceptExtractor()
        self.interaction_checker = DrugInteractionChecker()
        self.symptom_analyzer = SymptomAnalyzer()
        self.vector_store = MedicalVectorStore(self.config)
        self.reranker = MedicalReranker(self.config)
        self.response_generator = MedicalResponseGenerator(self.config)

        self._initialized = False

    def initialize(self):
        """Initialize all components."""
        if self._initialized:
            return

        print("🏥 Initializing Medical RAG Pipeline...")
        self.embedding_manager.initialize()
        self.reranker.initialize()
        self._initialized = True
        print("✅ Medical RAG Pipeline ready")

    def load_knowledge_base(self, documents: list[dict]):
        """Load medical documents into the knowledge base."""
        print(f"📚 Loading {len(documents)} medical documents...")

        for doc in documents:
            # Create chunk
            chunk = MedicalChunk(
                chunk_id=doc.get(
                    "id", hashlib.md5(doc["content"].encode()).hexdigest()[:12]
                ),
                content=doc["content"],
                content_type=MedicalContentType(doc.get("type", "patient_education")),
                source_document=doc.get("source", "Unknown"),
                source_section=doc.get("section", ""),
                medical_concepts=doc.get("concepts", []),
                codes=doc.get("codes", {}),
                severity_level=SeverityLevel(doc.get("severity", "info")),
                last_updated=doc.get("updated", datetime.now().isoformat()),
                review_status=doc.get("review_status", "pending"),
            )

            # Generate embedding
            chunk.embedding = self.embedding_manager.embed(chunk.content)

            # Add to store
            self.vector_store.add_chunk(chunk)

        print(f"✅ Loaded {len(self.vector_store.chunks)} chunks")

    def query(self, query: str) -> MedicalQueryResult:
        """Process a medical query through the RAG pipeline."""
        self.initialize()

        # Step 1: Check for emergency
        is_emergency = self.concept_extractor.detect_emergency(query)
        if is_emergency:
            return self.response_generator.generate(
                query, [], [], [], is_emergency=True
            )

        # Step 2: Extract concepts
        concepts = self.concept_extractor.extract_concepts(query)

        # Step 3: Check for drug interactions
        drug_names = [
            c.name.lower()
            for c in concepts
            if c.concept_type == MedicalContentType.DRUG_INFO
        ]
        interactions = self.interaction_checker.check_interactions(drug_names)

        # Step 4: Generate query embedding
        query_embedding = self.embedding_manager.embed(query)

        # Step 5: Retrieve relevant chunks
        medical_codes = []
        for c in concepts:
            medical_codes.extend(
                f"{k}:{v}"
                for k, v in c.codes.items()
                for v in ([v] if isinstance(v, str) else v)
            )

        results = self.vector_store.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            codes=medical_codes,
            top_k=self.config.top_k,
        )

        # Step 6: Rerank results
        reranked = self.reranker.rerank(query, results)

        # Step 7: Generate response
        response = self.response_generator.generate(
            query=query,
            context=reranked,
            detected_concepts=concepts,
            interactions=interactions,
            is_emergency=False,
        )

        return response

    def check_drug_interactions(self, drugs: list[str]) -> list[DrugInteraction]:
        """Check for interactions between specified drugs."""
        return self.interaction_checker.check_interactions(drugs)

    def analyze_symptoms(self, symptoms: list[str]) -> dict:
        """Analyze symptoms and return possible conditions."""
        return self.symptom_analyzer.analyze_symptoms(
            symptoms, max_conditions=self.config.max_symptom_conditions
        )

    def evaluate(self, query: str, expected_answer: str = None) -> EvaluationMetrics:
        """Evaluate the RAG pipeline on a query."""
        import time

        start = time.time()
        result = self.query(query)
        elapsed = (time.time() - start) * 1000

        # Calculate metrics
        relevance = result.confidence

        # Safety score based on disclaimer presence
        safety = 1.0 if result.disclaimer else 0.5
        if result.requires_professional:
            safety = min(safety + 0.2, 1.0)

        # Accuracy (simplified - would need ground truth)
        accuracy = relevance * 0.8  # Proxy

        # Completeness
        completeness = min(len(result.sources) / 3, 1.0)

        # Citation quality
        citation_quality = 1.0 if result.sources else 0.0

        return EvaluationMetrics(
            relevance_score=relevance,
            safety_score=safety,
            accuracy_score=accuracy,
            completeness=completeness,
            citation_quality=citation_quality,
            response_time_ms=elapsed,
        )


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE DATA
# ══════════════════════════════════════════════════════════════════════════════


def get_sample_medical_documents() -> list[dict]:
    """Generate sample medical documents for demo."""
    return [
        {
            "id": "drug_paracetamol_001",
            "content": """
            Paracetamol (Acetaminophen) - Consumer Medicine Information
            
            What Paracetamol is used for:
            Paracetamol is a pain reliever (analgesic) and fever reducer (antipyretic). 
            It is commonly used to relieve mild to moderate pain such as headaches, 
            toothaches, muscle aches, backaches, and pain from osteoarthritis. It also 
            reduces fever.
            
            How to take Paracetamol:
            Adults and children 12 years and over: Take 1-2 tablets (500mg-1000mg) 
            every 4-6 hours as needed. Do not take more than 8 tablets (4000mg) in 
            24 hours. Do not use for more than a few days without consulting a doctor.
            
            Warnings:
            - Do not exceed the recommended dose
            - Taking more than the recommended dose can cause serious liver damage
            - Do not take with other products containing paracetamol
            - Avoid alcohol while taking this medication
            - Consult a doctor if pain persists for more than 5 days
            """,
            "type": "drug_info",
            "source": "Consumer Medicine Information",
            "section": "Paracetamol",
            "concepts": ["drug_paracetamol"],
            "codes": {"ATC": ["N02BE01"]},
            "severity": "info",
            "review_status": "approved",
            "updated": "2024-01-15",
        },
        {
            "id": "drug_ibuprofen_001",
            "content": """
            Ibuprofen - Consumer Medicine Information
            
            What Ibuprofen is used for:
            Ibuprofen is a non-steroidal anti-inflammatory drug (NSAID) used to 
            reduce pain, fever, and inflammation. Common uses include headaches, 
            dental pain, menstrual cramps, muscle aches, arthritis, and minor injuries.
            
            How to take Ibuprofen:
            Adults: 200-400mg every 4-6 hours as needed. Maximum 1200mg per day 
            for over-the-counter use. Take with food or milk to reduce stomach upset.
            
            Warnings:
            - Do not take if you have stomach ulcers or bleeding disorders
            - May increase risk of heart attack or stroke with long-term use
            - Do not take with aspirin or other NSAIDs
            - Avoid if pregnant, especially in third trimester
            - May cause kidney problems with prolonged use
            - Consult doctor if you have heart, liver, or kidney disease
            """,
            "type": "drug_info",
            "source": "Consumer Medicine Information",
            "section": "Ibuprofen",
            "concepts": ["drug_ibuprofen"],
            "codes": {"ATC": ["M01AE01"]},
            "severity": "caution",
            "review_status": "approved",
            "updated": "2024-02-10",
        },
        {
            "id": "condition_headache_001",
            "content": """
            Headaches - Patient Education Guide
            
            Types of Headaches:
            
            1. Tension Headaches: The most common type. Feels like a band of pressure 
            around the head. Often caused by stress, poor posture, or muscle tension.
            
            2. Migraines: Severe, throbbing pain usually on one side of the head. 
            May include nausea, vomiting, and sensitivity to light and sound. Can 
            last hours to days.
            
            3. Cluster Headaches: Severe pain around one eye. Occur in clusters over 
            weeks or months, then may stop for periods.
            
            When to Seek Emergency Care:
            - Sudden, severe headache ("worst headache of your life")
            - Headache with fever, stiff neck, confusion
            - Headache after head injury
            - Headache with vision changes, weakness, or numbness
            - Headache with difficulty speaking
            
            Self-Care Tips:
            - Rest in a quiet, dark room
            - Apply cold or warm compress
            - Stay hydrated
            - Practice relaxation techniques
            - Over-the-counter pain relievers (as directed)
            """,
            "type": "condition",
            "source": "Patient Education Library",
            "section": "Headaches",
            "concepts": [
                "symptom_headache",
                "condition_migraine",
                "condition_tension_headache",
            ],
            "codes": {"ICD-10": ["G43", "G44", "R51"]},
            "severity": "info",
            "review_status": "approved",
            "updated": "2024-03-01",
        },
        {
            "id": "condition_fever_001",
            "content": """
            Fever in Adults - What You Need to Know
            
            What is a Fever?
            A fever is a temporary increase in body temperature, often due to illness. 
            Normal body temperature is around 37°C (98.6°F). A fever is generally 
            considered to be 38°C (100.4°F) or higher.
            
            Common Causes:
            - Viral infections (cold, flu, COVID-19)
            - Bacterial infections
            - Heat exhaustion
            - Certain medications
            - Immunizations
            - Inflammatory conditions
            
            When to See a Doctor:
            - Temperature above 39.4°C (103°F)
            - Fever lasting more than 3 days
            - Severe headache or stiff neck
            - Unusual skin rash
            - Difficulty breathing
            - Confusion or unusual behavior
            - Persistent vomiting
            - Signs of dehydration
            
            Home Care:
            - Rest and stay hydrated
            - Take paracetamol or ibuprofen as directed
            - Dress in lightweight clothing
            - Keep room at comfortable temperature
            - Take a lukewarm bath if needed
            """,
            "type": "condition",
            "source": "Patient Education Library",
            "section": "Fever",
            "concepts": ["symptom_fever"],
            "codes": {"ICD-10": ["R50"]},
            "severity": "caution",
            "review_status": "approved",
            "updated": "2024-01-20",
        },
        {
            "id": "guideline_bp_001",
            "content": """
            Blood Pressure Guidelines - Understanding Your Numbers
            
            Blood Pressure Categories (Australian Guidelines):
            
            Optimal: Less than 120/80 mmHg
            - No action needed, maintain healthy lifestyle
            
            Normal: 120-129/80-84 mmHg
            - Lifestyle modifications recommended
            - Regular monitoring advised
            
            High-Normal: 130-139/85-89 mmHg
            - Increased cardiovascular risk
            - Lifestyle changes important
            - Consider medication for high-risk individuals
            
            Grade 1 Hypertension: 140-159/90-99 mmHg
            - Medical assessment recommended
            - Lifestyle modifications essential
            - Medication may be needed
            
            Grade 2 Hypertension: 160-179/100-109 mmHg
            - Prompt medical attention required
            - Usually requires medication
            
            Grade 3 Hypertension: 180+ / 110+ mmHg
            - Urgent medical care needed
            - High risk of complications
            
            Risk Factors for High Blood Pressure:
            - Family history
            - Age (risk increases with age)
            - Obesity
            - Physical inactivity
            - High sodium diet
            - Excessive alcohol
            - Stress
            - Smoking
            """,
            "type": "guideline",
            "source": "Heart Foundation Guidelines",
            "section": "Blood Pressure",
            "concepts": ["condition_hypertension"],
            "codes": {"ICD-10": ["I10", "I15"]},
            "severity": "info",
            "review_status": "approved",
            "updated": "2024-02-28",
        },
        {
            "id": "drug_metformin_001",
            "content": """
            Metformin - Information for Patients with Type 2 Diabetes
            
            What is Metformin?
            Metformin is a first-line medication for treating type 2 diabetes. It 
            works by reducing glucose production in the liver and improving insulin 
            sensitivity.
            
            How to Take Metformin:
            - Usually taken 1-3 times daily with meals
            - Start with a low dose and increase gradually
            - Extended-release forms taken once daily
            - Always take with food to reduce stomach upset
            
            Common Side Effects:
            - Nausea, vomiting, diarrhea (usually improve over time)
            - Stomach pain, loss of appetite
            - Metallic taste in mouth
            
            Important Warnings:
            - Do not take if you have severe kidney disease
            - Stop taking before procedures with contrast dye
            - Avoid excessive alcohol (increases lactic acidosis risk)
            - May cause vitamin B12 deficiency with long-term use
            - Seek medical help if you experience unusual muscle pain, 
              difficulty breathing, or extreme fatigue
            
            Regular Monitoring:
            - HbA1c every 3-6 months
            - Kidney function tests annually
            - Vitamin B12 levels periodically
            """,
            "type": "drug_info",
            "source": "Diabetes Australia Education",
            "section": "Metformin",
            "concepts": ["drug_metformin", "condition_diabetes"],
            "codes": {"ATC": ["A10BA02"], "ICD-10": ["E11"]},
            "severity": "caution",
            "review_status": "approved",
            "updated": "2024-03-10",
        },
        {
            "id": "provider_gp_001",
            "content": """
            Finding a General Practitioner (GP) in Australia
            
            What GPs Do:
            General practitioners are primary healthcare providers who can:
            - Diagnose and treat common illnesses
            - Provide preventive care and health screenings
            - Manage chronic conditions
            - Prescribe medications
            - Refer to specialists when needed
            - Provide mental health support
            
            How to Find a GP:
            - Visit Health Direct (healthdirect.gov.au)
            - Use Service Finder to locate nearby clinics
            - Ask for recommendations from family/friends
            - Check if they bulk-bill (no out-of-pocket costs with Medicare)
            
            Telehealth Options:
            Many GPs now offer telehealth appointments for:
            - Follow-up consultations
            - Prescription renewals
            - Mental health support
            - General health advice
            
            Preparing for Your Appointment:
            - Bring your Medicare card
            - List your current medications
            - Note your symptoms and when they started
            - Write down questions you want to ask
            - Bring any relevant test results
            """,
            "type": "provider",
            "source": "Health Direct Australia",
            "section": "Finding a GP",
            "concepts": [],
            "codes": {},
            "severity": "info",
            "review_status": "approved",
            "updated": "2024-01-05",
        },
        {
            "id": "condition_anxiety_001",
            "content": """
            Anxiety - Understanding and Managing Anxiety
            
            What is Anxiety?
            Anxiety is a normal response to stress, but when it becomes excessive 
            or persistent, it may be an anxiety disorder. Common types include 
            generalized anxiety disorder, panic disorder, and social anxiety.
            
            Common Symptoms:
            - Excessive worry or fear
            - Restlessness or feeling on edge
            - Difficulty concentrating
            - Irritability
            - Sleep problems
            - Muscle tension
            - Physical symptoms: rapid heartbeat, sweating, trembling
            
            When to Seek Help:
            - Anxiety interferes with daily activities
            - Avoiding situations due to fear
            - Panic attacks
            - Physical symptoms without medical cause
            - Using alcohol or drugs to cope
            - Thoughts of self-harm
            
            Treatment Options:
            - Cognitive behavioral therapy (CBT)
            - Medication (SSRIs, SNRIs, as prescribed)
            - Lifestyle changes (exercise, sleep, diet)
            - Relaxation techniques
            - Mindfulness and meditation
            
            Self-Help Strategies:
            - Regular physical activity
            - Limit caffeine and alcohol
            - Practice deep breathing
            - Maintain social connections
            - Get adequate sleep
            - Challenge negative thoughts
            
            Crisis Support:
            If you're in crisis, contact:
            - Lifeline: 13 11 14 (24/7)
            - Beyond Blue: 1300 22 4636
            - Emergency: 000
            """,
            "type": "condition",
            "source": "Beyond Blue Resources",
            "section": "Anxiety",
            "concepts": ["condition_anxiety"],
            "codes": {"ICD-10": ["F41"]},
            "severity": "caution",
            "review_status": "approved",
            "updated": "2024-02-15",
        },
    ]


def get_sample_queries() -> list[dict]:
    """Get sample queries for testing."""
    return [
        {
            "query": "What is paracetamol used for and what's the maximum dose?",
            "expected_concepts": ["drug_paracetamol"],
        },
        {
            "query": "Can I take ibuprofen and aspirin together?",
            "expected_concepts": ["drug_ibuprofen", "drug_aspirin"],
            "expected_interaction": True,
        },
        {
            "query": "I have a headache and fever, what could it be?",
            "expected_concepts": ["symptom_headache", "symptom_fever"],
        },
        {
            "query": "What are the side effects of metformin?",
            "expected_concepts": ["drug_metformin"],
        },
        {
            "query": "When should I see a doctor for anxiety?",
            "expected_concepts": ["condition_anxiety"],
        },
        {
            "query": "What blood pressure is considered high?",
            "expected_concepts": ["condition_hypertension"],
        },
        {"query": "How do I find a GP near me?", "expected_concepts": []},
    ]


# ══════════════════════════════════════════════════════════════════════════════
# DEMO AND CLI
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run interactive demo of the medical RAG system."""
    print("=" * 70)
    print("🏥 MEDICAL INFORMATION ASSISTANT - RAG DEMO")
    print("=" * 70)
    print(MEDICAL_DISCLAIMER)
    print("=" * 70)

    # Initialize pipeline
    config = MedicalRAGConfig()
    pipeline = MedicalRAGPipeline(config)
    pipeline.initialize()

    # Load sample documents
    documents = get_sample_medical_documents()
    pipeline.load_knowledge_base(documents)

    # Sample queries for testing
    sample_queries = get_sample_queries()

    print("\n📋 Sample Queries Available:")
    for i, sq in enumerate(sample_queries, 1):
        print(f"   {i}. {sq['query']}")

    print("\n🔧 Commands:")
    print("   'drugs <drug1> <drug2> ...' - Check drug interactions")
    print("   'symptoms <sym1>, <sym2>, ...' - Analyze symptoms")
    print("   'eval' - Run evaluation on sample queries")
    print("   'quit' - Exit")

    print("\n" + "-" * 70)

    while True:
        try:
            query = input("\n🔍 Your question: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not query:
            continue

        if query.lower() == "quit":
            break

        # Handle special commands
        if query.lower().startswith("drugs "):
            drugs = query[6:].split()
            print(f"\n💊 Checking interactions for: {', '.join(drugs)}")
            interactions = pipeline.check_drug_interactions(drugs)

            if interactions:
                for interaction in interactions:
                    formatted = pipeline.interaction_checker.format_interaction_warning(
                        interaction
                    )
                    print(formatted)
            else:
                print("   ✅ No known interactions found between these medications.")
                print(
                    "   ⚠️ This does not guarantee safety. Always consult a pharmacist or doctor."
                )
            continue

        if query.lower().startswith("symptoms "):
            symptoms = [s.strip() for s in query[9:].split(",")]
            print(f"\n🔬 Analyzing symptoms: {', '.join(symptoms)}")
            analysis = pipeline.analyze_symptoms(symptoms)

            print("\n📊 Analysis Results:")
            print(f"   Disclaimer: {analysis['disclaimer']}")
            print("\n   Possible Conditions:")
            for cond in analysis["possible_conditions"]:
                conf_bar = "█" * int(cond["confidence"] * 10)
                print(f"   • {cond['name']} ({cond['severity']})")
                print(f"     Confidence: [{conf_bar:<10}] {cond['confidence']:.0%}")
                print(f"     Matching symptoms: {', '.join(cond['matching_symptoms'])}")

            print("\n   ⚠️ When to Seek Professional Help:")
            for advice in analysis["when_to_seek_help"]:
                print(f"   • {advice}")
            continue

        if query.lower() == "eval":
            print("\n📈 Running Evaluation...")
            print("-" * 50)

            total_metrics = {
                "relevance": 0,
                "safety": 0,
                "accuracy": 0,
                "completeness": 0,
                "citation": 0,
                "time": 0,
            }

            for sq in sample_queries:
                metrics = pipeline.evaluate(sq["query"])
                total_metrics["relevance"] += metrics.relevance_score
                total_metrics["safety"] += metrics.safety_score
                total_metrics["accuracy"] += metrics.accuracy_score
                total_metrics["completeness"] += metrics.completeness
                total_metrics["citation"] += metrics.citation_quality
                total_metrics["time"] += metrics.response_time_ms

                print(f"   Query: {sq['query'][:50]}...")
                print(
                    f"   Relevance: {metrics.relevance_score:.2f}, Safety: {metrics.safety_score:.2f}, Time: {metrics.response_time_ms:.0f}ms"
                )

            n = len(sample_queries)
            print("\n" + "=" * 50)
            print(f"   Average Metrics ({n} queries):")
            print(f"   Relevance:    {total_metrics['relevance']/n:.2f}")
            print(f"   Safety:       {total_metrics['safety']/n:.2f}")
            print(f"   Accuracy:     {total_metrics['accuracy']/n:.2f}")
            print(f"   Completeness: {total_metrics['completeness']/n:.2f}")
            print(f"   Citations:    {total_metrics['citation']/n:.2f}")
            print(f"   Avg Time:     {total_metrics['time']/n:.0f}ms")
            continue

        # Regular query
        result = pipeline.query(query)

        # Display result
        print("\n" + "=" * 50)

        if result.safety_level == SeverityLevel.EMERGENCY:
            print(result.answer)
        else:
            print(
                f"🤖 Answer (confidence: {result.confidence:.2f}, {result.latency_ms:.0f}ms):\n"
            )
            print(result.answer)

            if result.disclaimer:
                print(f"\n{result.disclaimer}")

            if result.drug_interactions:
                print("\n💊 Drug Interactions Detected:")
                for interaction in result.drug_interactions:
                    print(
                        f"   ⚠️ {interaction.drug_a_id} + {interaction.drug_b_id}: {interaction.severity.value}"
                    )

            if result.sources:
                print(f"\n📚 Sources ({len(result.sources)}):")
                for i, src in enumerate(result.sources, 1):
                    print(
                        f"   [{i}] {src.chunk.source_document} - {src.chunk.source_section}"
                    )
                    print(
                        f"       Type: {src.chunk.content_type.value}, Score: {src.score:.2f}"
                    )

            if result.detected_concepts:
                print("\n🏷️ Detected Concepts:")
                for concept in result.detected_concepts[:5]:
                    print(f"   • {concept.name} ({concept.concept_type.value})")

            if result.requires_professional:
                print("\n👨‍⚕️ Professional Consultation Recommended")

            if result.related_topics:
                print(f"\n🔗 Related Topics: {', '.join(result.related_topics)}")

    print("\n👋 Thank you for using the Medical Information Assistant.")
    print("⚠️ Remember: Always consult healthcare professionals for medical advice.")


def main():
    """Main entry point."""
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    run_demo()


if __name__ == "__main__":
    main()
