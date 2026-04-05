#!/usr/bin/env python3
"""
Australian Family Law Knowledge Base

RAG-powered knowledge system for family law legal aid.

24/7 CLIENT ACCESS
==================
This powers chatbots that let parents and children ask questions ANYTIME:

  Parent at 2am: "I'm worried about my court date tomorrow, what should I expect?"
  Chatbot: "Here's what happens at a first return date..." [guidance, not advice]

  Child (via support worker): "Can I tell the judge what I want?"
  Chatbot: "Children's views are important. Here's how the court considers them..."

Legal firms deploy this so clients get instant guidance outside business hours.
Complex questions get flagged for lawyer follow-up during business hours.

DESIGNED FOR: Legal Aid services, family law firms, community legal centres
NOT FOR: Individual users seeking legal advice

This module shows HOW to build a legal knowledge base - organizations
must add their OWN resources, precedents, and procedures.

Example Usage:
    # Legal Aid builds their knowledge base
    kb = FamilyLawKnowledgeBase()
    kb.add_legislation("/path/to/legislation")
    kb.add_precedents("/path/to/your/precedents")
    kb.add_procedures("/path/to/internal/guides")
    kb.build_index()

    # Query the knowledge base
    results = kb.search("consent orders property settlement")

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# =============================================================================
# LEGAL DISCLAIMER - CRITICAL
# =============================================================================

KNOWLEDGE_BASE_DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  AUSTRALIAN FAMILY LAW KNOWLEDGE BASE - FRAMEWORK ONLY                       ║
║                                                                              ║
║  This is a FRAMEWORK for legal organizations to build knowledge bases.       ║
║  It contains STRUCTURE and GUIDANCE only - not legal advice.                ║
║                                                                              ║
║  Organizations using this framework MUST:                                    ║
║  1. Add their own authoritative legal resources                             ║
║  2. Ensure all content is legally accurate and current                      ║
║  3. Have qualified lawyers review all outputs                               ║
║  4. Comply with legal practice regulations                                  ║
║                                                                              ║
║  The knowledge categories below are EXAMPLES of what to include.            ║
║  Actual content must come from authoritative legal sources.                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================


class KnowledgeCategory(Enum):
    """Categories of family law knowledge."""

    LEGISLATION = "legislation"
    CASE_LAW = "case_law"
    COURT_PROCEDURES = "court_procedures"
    FORMS_TEMPLATES = "forms_templates"
    FDR_MEDIATION = "fdr_mediation"
    PARENTING = "parenting"
    PROPERTY = "property"
    CHILD_SUPPORT = "child_support"
    FAMILY_VIOLENCE = "family_violence"
    CHILDREN_MATTERS = "children_matters"
    INTERNATIONAL = "international"
    APPEALS = "appeals"
    COSTS = "costs"
    LEGAL_AID = "legal_aid"
    SELF_REP = "self_represented"


class CourtJurisdiction(Enum):
    """Australian family law courts."""

    FCFCOA = "Federal Circuit and Family Court of Australia"
    FCFCOA_DIVISION_1 = "FCFCOA Division 1 (Appeal)"
    FCFCOA_DIVISION_2 = "FCFCOA Division 2 (General)"
    FCWA = "Family Court of Western Australia"
    STATE_MAGISTRATES = "State Magistrates Court"
    HIGH_COURT = "High Court of Australia"


class MatterType(Enum):
    """Types of family law matters."""

    PARENTING = "parenting"
    PROPERTY = "property"
    PARENTING_AND_PROPERTY = "parenting_and_property"
    CHILD_SUPPORT = "child_support"
    DIVORCE = "divorce"
    SPOUSE_MAINTENANCE = "spouse_maintenance"
    CHILD_MAINTENANCE = "child_maintenance"
    INJUNCTION = "injunction"
    CONTRAVENTION = "contravention"
    ENFORCEMENT = "enforcement"
    APPEAL = "appeal"


@dataclass
class KnowledgeDocument:
    """A document in the knowledge base."""

    id: str
    title: str
    category: KnowledgeCategory
    content: str
    source: str  # Where this came from
    source_url: Optional[str] = None
    jurisdiction: Optional[CourtJurisdiction] = None
    matter_types: List[MatterType] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    verified_by: Optional[str] = None  # Lawyer who verified
    keywords: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "content": self.content,
            "source": self.source,
            "source_url": self.source_url,
            "jurisdiction": self.jurisdiction.value if self.jurisdiction else None,
            "matter_types": [m.value for m in self.matter_types],
            "last_updated": self.last_updated.isoformat(),
            "verified_by": self.verified_by,
            "keywords": self.keywords,
        }


@dataclass
class SearchResult:
    """A search result from the knowledge base."""

    document: KnowledgeDocument
    relevance_score: float
    matched_keywords: List[str] = field(default_factory=list)
    snippet: str = ""


# =============================================================================
# KNOWLEDGE STRUCTURE - WHAT TO INCLUDE
# =============================================================================

# This defines the STRUCTURE of knowledge - organizations add their own content

KNOWLEDGE_STRUCTURE = {
    KnowledgeCategory.LEGISLATION: {
        "description": "Primary and secondary legislation",
        "sources": [
            "Family Law Act 1975 (Cth)",
            "Family Law Amendment Act 2024",
            "Federal Circuit and Family Court of Australia Act 2021",
            "Family Law Rules 2004",
            "Child Support (Assessment) Act 1989",
            "Marriage Act 1961",
        ],
        "update_frequency": "Check after each parliamentary sitting",
    },
    KnowledgeCategory.CASE_LAW: {
        "description": "Relevant case law and precedents",
        "sources": [
            "FCFCOA judgments (AustLII)",
            "High Court family law decisions",
            "Significant precedents by topic",
        ],
        "note": "Organizations should curate relevant precedents for their practice",
    },
    KnowledgeCategory.COURT_PROCEDURES: {
        "description": "How the court process works",
        "topics": [
            "Filing an application",
            "Service requirements",
            "First return date procedures",
            "Interim hearings",
            "Final hearings",
            "Consent orders process",
            "Subpoenas",
            "Discovery and disclosure",
            "Expert evidence",
            "ICL appointments",
        ],
    },
    KnowledgeCategory.FDR_MEDIATION: {
        "description": "Family Dispute Resolution",
        "topics": [
            "FDR requirements (s60I)",
            "Exemptions from FDR",
            "s60I certificate types",
            "Finding FDR practitioners",
            "Preparing for mediation",
            "Legally assisted mediation",
            "Conciliation conferences",
        ],
    },
    KnowledgeCategory.PARENTING: {
        "description": "Parenting orders and arrangements",
        "topics": [
            "Best interests of the child (s60CC)",
            "Parental responsibility",
            "Living arrangements",
            "Time arrangements",
            "Communication provisions",
            "Relocation",
            "Change of name",
            "Passports and travel",
            "Education decisions",
            "Medical decisions",
            "Religious upbringing",
        ],
        "note": "2024 amendments removed 'equal shared parental responsibility' presumption",
    },
    KnowledgeCategory.PROPERTY: {
        "description": "Property settlement",
        "topics": [
            "Four-step process",
            "Asset pool identification",
            "Contributions assessment",
            "Future needs (s75(2) factors)",
            "Just and equitable test",
            "Superannuation splitting",
            "Binding Financial Agreements",
            "Spousal maintenance",
        ],
    },
    KnowledgeCategory.FAMILY_VIOLENCE: {
        "description": "Family violence matters - SAFETY CRITICAL",
        "topics": [
            "Definition of family violence",
            "Notice of Risk requirements",
            "Protection orders",
            "Safe arrangements for children",
            "Supervised time",
            "Safety planning",
            "Support services",
        ],
        "safety_note": "Always prioritize safety - provide emergency contacts",
    },
    KnowledgeCategory.CHILDREN_MATTERS: {
        "description": "Matters involving children",
        "topics": [
            "Independent Children's Lawyer (ICL)",
            "Family reports",
            "Child inclusive conferences",
            "Views of the child",
            "Mature minor principle",
            "Child abuse allegations",
            "Recovery orders",
            "Location and airport watch list orders",
        ],
    },
    KnowledgeCategory.SELF_REP: {
        "description": "Resources for self-represented litigants",
        "topics": [
            "Understanding court process",
            "Preparing documents",
            "Court etiquette",
            "What to expect at hearings",
            "Common mistakes to avoid",
            "Where to get help",
            "Duty lawyer services",
            "Legal Aid eligibility",
        ],
    },
}


# =============================================================================
# KEY LEGAL CONCEPTS - STRUCTURE ONLY
# =============================================================================

BEST_INTERESTS_FACTORS = {
    "description": "Section 60CC - Best interests of the child",
    "note": "As amended by Family Law Amendment Act 2024",
    "primary_considerations": [
        "Safety of the child (including from family violence, abuse, neglect)",
        "Views of the child (considering maturity)",
    ],
    "additional_considerations": [
        "Developmental, psychological, emotional, cultural needs",
        "Capacity of each parent",
        "Benefit of relationship with parents and others",
        "Effect of changes to circumstances",
        "Practical difficulty of arrangements",
        "Parental attitudes and responsibilities",
        "Family violence orders",
        "Any other relevant factor",
    ],
}

FDR_CERTIFICATE_TYPES = {
    "description": "Section 60I certificate types",
    "certificates": {
        "s60I(8)(a)": "Parties made genuine effort - no agreement",
        "s60I(8)(aa)": "One party made genuine effort - other did not",
        "s60I(8)(b)": "FDR not appropriate (e.g., family violence)",
        "s60I(8)(c)": "Person failed to attend after being asked",
        "s60I(8)(d)": "Practitioner did not deem it appropriate to continue",
    },
}


# =============================================================================
# FAMILY LAW KNOWLEDGE BASE CLASS
# =============================================================================


class FamilyLawKnowledgeBase:
    """
    RAG-powered knowledge base for Australian family law.

    FRAMEWORK ONLY - Organizations must add their own content.

    Example:
        kb = FamilyLawKnowledgeBase(organization="Legal Aid NSW")
        kb.add_documents("/path/to/your/resources")
        kb.build_index()

        results = kb.search("parenting orders travel overseas")
    """

    def __init__(
        self,
        organization: str,
        vector_store: Optional[Any] = None,  # Your VectorStore instance
        embedding_model: Optional[Any] = None,  # Your embedding model
    ):
        """
        Initialize knowledge base.

        Args:
            organization: Name of legal organization using this
            vector_store: Optional VectorStore for RAG
            embedding_model: Optional embedding model for vectors
        """
        self.organization = organization
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.documents: Dict[str, KnowledgeDocument] = {}
        self.indexed = False

        logger.info(f"Initialized FamilyLawKnowledgeBase for {organization}")
        logger.warning(KNOWLEDGE_BASE_DISCLAIMER)

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    def add_document(
        self,
        title: str,
        content: str,
        category: KnowledgeCategory,
        source: str,
        **kwargs,
    ) -> KnowledgeDocument:
        """
        Add a document to the knowledge base.

        Args:
            title: Document title
            content: Document content
            category: Knowledge category
            source: Where this came from
            **kwargs: Additional KnowledgeDocument fields

        Returns:
            The created document
        """
        doc_id = f"{category.value}_{len(self.documents)}"

        doc = KnowledgeDocument(
            id=doc_id,
            title=title,
            content=content,
            category=category,
            source=source,
            **kwargs,
        )

        self.documents[doc_id] = doc
        self.indexed = False  # Need to rebuild index

        logger.info(f"Added document: {title}")
        return doc

    def add_documents_from_path(
        self,
        path: str | Path,
        category: KnowledgeCategory,
        source: str,
    ) -> int:
        """
        Add documents from a directory path.

        Uses agentic-brain's document loaders to load files.

        Args:
            path: Path to directory of documents
            category: Category for all documents
            source: Source attribution

        Returns:
            Number of documents added
        """
        path = Path(path)
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return 0

        # Import RAG loaders
        try:
            from agentic_brain.rag.loaders import get_loader
        except ImportError:
            logger.error("agentic-brain not installed - using basic loading")
            return self._basic_load(path, category, source)

        count = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                try:
                    loader = get_loader(str(file_path))
                    docs = loader.load()

                    for doc in docs:
                        self.add_document(
                            title=file_path.name,
                            content=(
                                doc.page_content
                                if hasattr(doc, "page_content")
                                else str(doc)
                            ),
                            category=category,
                            source=source,
                            source_url=str(file_path),
                        )
                        count += 1

                except Exception as e:
                    logger.warning(f"Could not load {file_path}: {e}")

        logger.info(f"Added {count} documents from {path}")
        return count

    def _basic_load(
        self,
        path: Path,
        category: KnowledgeCategory,
        source: str,
    ) -> int:
        """Basic file loading without RAG loaders."""
        count = 0
        for file_path in path.rglob("*.txt"):
            try:
                content = file_path.read_text(encoding="utf-8")
                self.add_document(
                    title=file_path.name,
                    content=content,
                    category=category,
                    source=source,
                    source_url=str(file_path),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Could not load {file_path}: {e}")
        return count

    # -------------------------------------------------------------------------
    # Indexing
    # -------------------------------------------------------------------------

    def build_index(self) -> bool:
        """
        Build vector index for RAG search.

        Returns:
            True if successful
        """
        if not self.documents:
            logger.warning("No documents to index")
            return False

        if self.vector_store is None:
            logger.warning("No vector store configured - using keyword search only")
            self.indexed = True
            return True

        try:
            # Generate embeddings
            if self.embedding_model:
                for _doc_id, doc in self.documents.items():
                    embedding = self.embedding_model.embed(doc.content)
                    doc.embedding = embedding

            # Add to vector store
            texts = [doc.content for doc in self.documents.values()]
            metadatas = [doc.to_dict() for doc in self.documents.values()]

            self.vector_store.add_texts(texts, metadatas=metadatas)
            self.indexed = True

            logger.info(f"Indexed {len(self.documents)} documents")
            return True

        except Exception as e:
            logger.error(f"Failed to build index: {e}")
            return False

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        category: Optional[KnowledgeCategory] = None,
        matter_type: Optional[MatterType] = None,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """
        Search the knowledge base.

        Args:
            query: Search query
            category: Optional category filter
            matter_type: Optional matter type filter
            top_k: Number of results to return

        Returns:
            List of search results
        """
        if not self.indexed:
            logger.warning("Index not built - building now")
            self.build_index()

        # Vector search if available
        if self.vector_store and hasattr(self.vector_store, "similarity_search"):
            try:
                results = self.vector_store.similarity_search(
                    query,
                    k=top_k,
                    filter=self._build_filter(category, matter_type),
                )
                return self._format_vector_results(results)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # Fallback to keyword search
        return self._keyword_search(query, category, matter_type, top_k)

    def _keyword_search(
        self,
        query: str,
        category: Optional[KnowledgeCategory],
        matter_type: Optional[MatterType],
        top_k: int,
    ) -> List[SearchResult]:
        """Simple keyword-based search fallback."""
        query_terms = query.lower().split()
        results = []

        for doc in self.documents.values():
            # Filter by category
            if category and doc.category != category:
                continue

            # Filter by matter type
            if matter_type and matter_type not in doc.matter_types:
                continue

            # Score by keyword matches
            content_lower = doc.content.lower()
            title_lower = doc.title.lower()

            score = 0
            matched = []

            for term in query_terms:
                if term in title_lower:
                    score += 2
                    matched.append(term)
                if term in content_lower:
                    score += 1
                    if term not in matched:
                        matched.append(term)

            if score > 0:
                # Create snippet
                snippet = self._create_snippet(doc.content, query_terms)

                results.append(
                    SearchResult(
                        document=doc,
                        relevance_score=score,
                        matched_keywords=matched,
                        snippet=snippet,
                    )
                )

        # Sort by score and limit
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def _create_snippet(self, content: str, terms: List[str], length: int = 200) -> str:
        """Create a relevant snippet from content."""
        content_lower = content.lower()

        # Find first matching term
        for term in terms:
            pos = content_lower.find(term)
            if pos != -1:
                start = max(0, pos - 50)
                end = min(len(content), pos + length)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                return snippet

        # No match - return start
        return content[:length] + "..." if len(content) > length else content

    def _build_filter(
        self,
        category: Optional[KnowledgeCategory],
        matter_type: Optional[MatterType],
    ) -> Optional[Dict]:
        """Build filter for vector search."""
        if not category and not matter_type:
            return None

        filters = {}
        if category:
            filters["category"] = category.value
        if matter_type:
            filters["matter_types"] = {"$contains": matter_type.value}

        return filters

    def _format_vector_results(self, results: List[Any]) -> List[SearchResult]:
        """Format vector store results as SearchResults."""
        formatted = []
        for i, result in enumerate(results):
            # Assume result has page_content and metadata
            content = getattr(result, "page_content", str(result))
            metadata = getattr(result, "metadata", {})

            doc = KnowledgeDocument(
                id=metadata.get("id", f"result_{i}"),
                title=metadata.get("title", "Search Result"),
                content=content,
                category=KnowledgeCategory(
                    metadata.get("category", "court_procedures")
                ),
                source=metadata.get("source", "Knowledge Base"),
            )

            formatted.append(
                SearchResult(
                    document=doc,
                    relevance_score=1.0 - (i * 0.1),  # Decrease score by position
                    snippet=content[:200] + "..." if len(content) > 200 else content,
                )
            )

        return formatted

    # -------------------------------------------------------------------------
    # Topic-Specific Queries
    # -------------------------------------------------------------------------

    def get_procedure_guidance(self, procedure: str) -> Optional[str]:
        """Get guidance on a specific court procedure."""
        results = self.search(
            procedure,
            category=KnowledgeCategory.COURT_PROCEDURES,
            top_k=3,
        )

        if not results:
            return None

        guidance = f"## {procedure.title()}\n\n"
        for result in results:
            guidance += f"### {result.document.title}\n"
            guidance += f"{result.snippet}\n\n"
            guidance += f"*Source: {result.document.source}*\n\n"

        return guidance

    def get_parenting_guidance(self, topic: str) -> Optional[str]:
        """Get guidance on parenting matters."""
        return self._get_category_guidance(topic, KnowledgeCategory.PARENTING)

    def get_property_guidance(self, topic: str) -> Optional[str]:
        """Get guidance on property settlement."""
        return self._get_category_guidance(topic, KnowledgeCategory.PROPERTY)

    def get_fdr_guidance(self, topic: str) -> Optional[str]:
        """Get guidance on FDR/mediation."""
        return self._get_category_guidance(topic, KnowledgeCategory.FDR_MEDIATION)

    def get_self_rep_guidance(self, topic: str) -> Optional[str]:
        """Get guidance for self-represented litigants."""
        return self._get_category_guidance(topic, KnowledgeCategory.SELF_REP)

    def _get_category_guidance(
        self,
        topic: str,
        category: KnowledgeCategory,
    ) -> Optional[str]:
        """Get guidance for a specific category."""
        results = self.search(topic, category=category, top_k=3)

        if not results:
            return None

        guidance = f"## {topic.title()}\n\n"
        for result in results:
            guidance += f"### {result.document.title}\n"
            guidance += f"{result.snippet}\n\n"

        return guidance

    # -------------------------------------------------------------------------
    # Safety-Critical Knowledge
    # -------------------------------------------------------------------------

    def get_safety_resources(self) -> Dict[str, Any]:
        """
        Get family violence safety resources.

        CRITICAL: Always provide these when violence indicators present.
        """
        return {
            "emergency": {
                "police": "000",
                "note": "Call if in immediate danger",
            },
            "support_lines": {
                "1800RESPECT": {
                    "number": "1800 737 732",
                    "description": "National DV/SA counselling service",
                    "hours": "24/7",
                },
                "Lifeline": {
                    "number": "13 11 14",
                    "description": "Crisis support",
                    "hours": "24/7",
                },
                "MensLine": {
                    "number": "1300 78 99 78",
                    "description": "Support for men",
                    "hours": "24/7",
                },
                "Kids_Helpline": {
                    "number": "1800 55 1800",
                    "description": "Counselling for young people",
                    "hours": "24/7",
                },
            },
            "state_services": {
                "NSW": "Domestic Violence Line 1800 656 463",
                "VIC": "Safe Steps 1800 015 188",
                "QLD": "DVConnect 1800 811 811",
                "WA": "Women's DV Helpline 1800 007 339",
                "SA": "DV Crisis Line 1800 800 098",
                "TAS": "Family Violence Response 1800 633 937",
                "NT": "DV Crisis Line 1800 019 116",
                "ACT": "Domestic Violence Crisis Service 02 6280 0900",
            },
            "legal_disclaimer": (
                "If you are in immediate danger, call 000. "
                "These resources provide support - they are not legal advice. "
                "Speak to a lawyer about your legal options."
            ),
        }

    # -------------------------------------------------------------------------
    # Export/Import
    # -------------------------------------------------------------------------

    def export_to_json(self, path: str | Path) -> None:
        """Export knowledge base to JSON."""
        path = Path(path)

        data = {
            "organization": self.organization,
            "exported_at": datetime.now().isoformat(),
            "document_count": len(self.documents),
            "documents": [doc.to_dict() for doc in self.documents.values()],
        }

        path.write_text(json.dumps(data, indent=2))
        logger.info(f"Exported {len(self.documents)} documents to {path}")

    def import_from_json(self, path: str | Path) -> int:
        """Import knowledge base from JSON."""
        path = Path(path)

        data = json.loads(path.read_text())

        count = 0
        for doc_data in data.get("documents", []):
            self.add_document(
                title=doc_data["title"],
                content=doc_data["content"],
                category=KnowledgeCategory(doc_data["category"]),
                source=doc_data["source"],
                source_url=doc_data.get("source_url"),
                keywords=doc_data.get("keywords", []),
            )
            count += 1

        logger.info(f"Imported {count} documents from {path}")
        return count

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        category_counts = {}
        for doc in self.documents.values():
            cat = doc.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "organization": self.organization,
            "total_documents": len(self.documents),
            "indexed": self.indexed,
            "documents_by_category": category_counts,
            "has_vector_store": self.vector_store is not None,
            "has_embedding_model": self.embedding_model is not None,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def create_knowledge_base(
    organization: str,
    resources_path: Optional[str] = None,
) -> FamilyLawKnowledgeBase:
    """
    Convenience function to create and setup a knowledge base.

    Example:
        kb = create_knowledge_base(
            organization="Legal Aid NSW",
            resources_path="/path/to/legal/resources",
        )
    """
    kb = FamilyLawKnowledgeBase(organization=organization)

    if resources_path:
        path = Path(resources_path)

        # Auto-detect categories from directory structure
        for subdir in path.iterdir():
            if subdir.is_dir():
                # Try to match to a category
                name = subdir.name.lower().replace("-", "_").replace(" ", "_")
                try:
                    category = KnowledgeCategory(name)
                except ValueError:
                    category = KnowledgeCategory.COURT_PROCEDURES

                kb.add_documents_from_path(
                    subdir, category, f"{organization} resources"
                )

    kb.build_index()
    return kb


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example: How a Legal Aid organization would use this

    print(KNOWLEDGE_BASE_DISCLAIMER)

    # Create knowledge base
    kb = FamilyLawKnowledgeBase(organization="Example Legal Aid")

    # Add some example structure (organizations add their own content)
    kb.add_document(
        title="Understanding Parenting Orders",
        content="Parenting orders are court orders about parenting arrangements...",
        category=KnowledgeCategory.PARENTING,
        source="Example Guide",
    )

    kb.add_document(
        title="Filing an Application",
        content="To file an application in the FCFCOA, you need to...",
        category=KnowledgeCategory.COURT_PROCEDURES,
        source="Example Guide",
    )

    # Build index
    kb.build_index()

    # Search
    results = kb.search("parenting orders")
    print(f"\nFound {len(results)} results for 'parenting orders'")

    for result in results:
        print(f"  - {result.document.title} (score: {result.relevance_score})")

    # Get safety resources
    safety = kb.get_safety_resources()
    print(
        f"\nSafety resources loaded with {len(safety['support_lines'])} support lines"
    )

    # Stats
    stats = kb.get_stats()
    print(f"\nKnowledge base stats: {stats}")
