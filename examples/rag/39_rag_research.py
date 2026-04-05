#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 39: RAG Research Paper Assistant

An AI assistant for working with academic research papers:
- Academic paper parsing (PDF, HTML)
- Citation extraction and linking
- Topic modeling and classification
- Related paper suggestions
- Summary generation
- Literature review assistance

Key RAG features demonstrated:
- Structured document parsing (abstract, sections, references)
- Citation graph construction
- Topic-based clustering
- Multi-document summarization
- Cross-referencing between papers
- Evaluation metrics

Demo: Technology research papers (generic)

Usage:
    python examples/39_rag_research.py
    python examples/39_rag_research.py --demo

Requirements:
    pip install agentic-brain sentence-transformers scikit-learn
"""

import asyncio
import hashlib
import json
import math
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Optional

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ResearchRAGConfig:
    """Configuration for research paper RAG."""

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 100

    # Topic modeling
    num_topics: int = 10
    min_topic_words: int = 5

    # Retrieval
    top_k: int = 10
    rerank_top_k: int = 5
    citation_weight: float = 0.2

    # Summary
    max_summary_sentences: int = 5


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS AND DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class PaperSection(Enum):
    """Standard academic paper sections."""

    TITLE = "title"
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    BACKGROUND = "background"
    RELATED_WORK = "related_work"
    METHODOLOGY = "methodology"
    EXPERIMENTS = "experiments"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    REFERENCES = "references"
    APPENDIX = "appendix"


class PublicationType(Enum):
    """Types of academic publications."""

    JOURNAL = "journal"
    CONFERENCE = "conference"
    PREPRINT = "preprint"
    THESIS = "thesis"
    BOOK_CHAPTER = "book_chapter"
    TECHNICAL_REPORT = "technical_report"


@dataclass
class Author:
    """An author of a paper."""

    name: str
    affiliation: str = ""
    email: str = ""
    orcid: str = ""

    @property
    def last_name(self) -> str:
        parts = self.name.split()
        return parts[-1] if parts else ""


@dataclass
class Citation:
    """A citation/reference to another paper."""

    id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int = 0
    venue: str = ""
    doi: str = ""
    url: str = ""
    cited_paper_id: str = ""  # ID if paper is in our corpus

    @property
    def short_cite(self) -> str:
        """Get short citation like 'Smith et al. (2023)'."""
        if self.authors:
            first_author = self.authors[0].split()[-1] if self.authors[0] else "Unknown"
            if len(self.authors) > 2:
                return f"{first_author} et al. ({self.year})"
            elif len(self.authors) == 2:
                second_author = self.authors[1].split()[-1] if self.authors[1] else ""
                return f"{first_author} & {second_author} ({self.year})"
            else:
                return f"{first_author} ({self.year})"
        return f"({self.year})"


@dataclass
class PaperChunk:
    """A chunk of paper content."""

    id: str
    paper_id: str
    section: PaperSection
    content: str
    embedding: Optional[list[float]] = None
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ResearchPaper:
    """A research paper."""

    id: str
    title: str
    authors: list[Author] = field(default_factory=list)
    abstract: str = ""
    year: int = 0
    venue: str = ""
    pub_type: PublicationType = PublicationType.PREPRINT
    doi: str = ""
    url: str = ""
    keywords: list[str] = field(default_factory=list)

    # Content
    sections: dict[PaperSection, str] = field(default_factory=dict)
    full_text: str = ""
    chunks: list[PaperChunk] = field(default_factory=list)

    # Citations
    citations: list[Citation] = field(default_factory=list)
    cited_by: list[str] = field(default_factory=list)  # Paper IDs

    # Computed
    topics: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None

    @property
    def author_string(self) -> str:
        if not self.authors:
            return "Unknown"
        names = [a.name for a in self.authors]
        if len(names) > 3:
            return f"{names[0]} et al."
        return ", ".join(names)

    @property
    def cite_key(self) -> str:
        """Generate citation key like 'smith2023neural'."""
        if self.authors:
            last_name = self.authors[0].last_name.lower()
        else:
            last_name = "unknown"

        title_word = ""
        for word in self.title.lower().split():
            if len(word) > 3 and word.isalpha():
                title_word = word
                break

        return f"{last_name}{self.year}{title_word}"


@dataclass
class SearchResult:
    """Result from paper search."""

    paper: ResearchPaper
    chunk: Optional[PaperChunk]
    score: float
    rank: int
    match_type: str
    snippet: str = ""


@dataclass
class TopicCluster:
    """A topic cluster of papers."""

    id: str
    name: str
    keywords: list[str]
    papers: list[str]  # Paper IDs
    centroid: Optional[list[float]] = None


# ══════════════════════════════════════════════════════════════════════════════
# PAPER PARSER
# ══════════════════════════════════════════════════════════════════════════════


class PaperParser:
    """Parse research papers from various formats."""

    # Section detection patterns
    SECTION_PATTERNS = {
        PaperSection.ABSTRACT: r"(?i)^#+?\s*abstract|^abstract\s*$",
        PaperSection.INTRODUCTION: r"(?i)^#+?\s*\d*\.?\s*introduction",
        PaperSection.BACKGROUND: r"(?i)^#+?\s*\d*\.?\s*(background|preliminaries)",
        PaperSection.RELATED_WORK: r"(?i)^#+?\s*\d*\.?\s*related\s*(work|research)",
        PaperSection.METHODOLOGY: r"(?i)^#+?\s*\d*\.?\s*(method|approach|methodology)",
        PaperSection.EXPERIMENTS: r"(?i)^#+?\s*\d*\.?\s*(experiment|evaluation)",
        PaperSection.RESULTS: r"(?i)^#+?\s*\d*\.?\s*results",
        PaperSection.DISCUSSION: r"(?i)^#+?\s*\d*\.?\s*discussion",
        PaperSection.CONCLUSION: r"(?i)^#+?\s*\d*\.?\s*(conclusion|summary)",
        PaperSection.REFERENCES: r"(?i)^#+?\s*\d*\.?\s*(references|bibliography)",
        PaperSection.APPENDIX: r"(?i)^#+?\s*\d*\.?\s*appendix",
    }

    def parse(self, content: str, metadata: dict = None) -> ResearchPaper:
        """Parse paper content into structured format."""
        metadata = metadata or {}

        # Extract title (first line or from metadata)
        lines = content.split("\n")
        title = metadata.get("title", "")
        if not title and lines:
            title = lines[0].strip("#").strip()

        # Generate ID
        paper_id = hashlib.md5(title.encode()).hexdigest()[:12]

        # Parse authors
        authors = self._parse_authors(metadata.get("authors", ""))

        # Parse sections
        sections = self._parse_sections(content)

        # Extract abstract
        abstract = sections.get(PaperSection.ABSTRACT, "")
        if not abstract:
            abstract = metadata.get("abstract", "")

        # Parse citations
        citations = self._parse_citations(content)

        # Extract keywords
        keywords = self._extract_keywords(content)

        paper = ResearchPaper(
            id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=metadata.get("year", datetime.now().year),
            venue=metadata.get("venue", ""),
            pub_type=PublicationType(metadata.get("type", "preprint")),
            doi=metadata.get("doi", ""),
            url=metadata.get("url", ""),
            keywords=keywords,
            sections=sections,
            full_text=content,
            citations=citations,
        )

        return paper

    def _parse_authors(self, author_string: str) -> list[Author]:
        """Parse author string into Author objects."""
        if not author_string:
            return []

        authors = []
        # Split by common separators
        names = re.split(r",\s*(?:and\s+)?|\s+and\s+", author_string)

        for name in names:
            name = name.strip()
            if name:
                authors.append(Author(name=name))

        return authors

    def _parse_sections(self, content: str) -> dict[PaperSection, str]:
        """Parse content into sections."""
        sections = {}
        lines = content.split("\n")

        current_section = None
        current_content = []

        for line in lines:
            # Check if line is a section header
            detected_section = None
            for section, pattern in self.SECTION_PATTERNS.items():
                if re.match(pattern, line):
                    detected_section = section
                    break

            if detected_section:
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                current_section = detected_section
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _parse_citations(self, content: str) -> list[Citation]:
        """Extract citations from paper content."""
        citations = []

        # Common citation patterns
        # [1] Author (Year). Title. Venue.
        # Author, A. (Year). Title. Venue.

        ref_section = ""
        in_refs = False

        for line in content.split("\n"):
            if re.match(r"(?i)^#+?\s*references|^references\s*$", line):
                in_refs = True
                continue

            if in_refs:
                if re.match(r"^#+?\s*\w", line):  # Next section
                    break
                ref_section += line + "\n"

        # Parse references
        ref_patterns = [
            # [1] or 1. prefix
            r"(?:\[(\d+)\]|\d+\.)\s*(.+?)(?=\n\[|\n\d+\.|\Z)",
            # Full line references
            r"^(.+?\(\d{4}\).+?)$",
        ]

        for pattern in ref_patterns:
            for match in re.finditer(pattern, ref_section, re.MULTILINE | re.DOTALL):
                ref_text = match.group(2) if match.lastindex == 2 else match.group(1)
                ref_text = ref_text.strip()

                if len(ref_text) < 20:
                    continue

                # Extract year
                year_match = re.search(r"\((\d{4})\)", ref_text)
                year = int(year_match.group(1)) if year_match else 0

                # Extract authors (before year usually)
                author_match = re.match(
                    r"^(.+?)(?:\s*\(\d{4}\)|\s*,\s*\d{4})", ref_text
                )
                authors = author_match.group(1).split(",") if author_match else []

                # Extract title (often in quotes or after authors)
                title_match = re.search(r'["""](.+?)["""]', ref_text)
                title = title_match.group(1) if title_match else ref_text[:100]

                citation = Citation(
                    id=hashlib.md5(ref_text.encode()).hexdigest()[:8],
                    title=title.strip(),
                    authors=[a.strip() for a in authors[:3]],
                    year=year,
                    venue="",
                )

                citations.append(citation)

        return citations[:50]  # Limit citations

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from paper content."""
        # Look for explicit keywords section
        kw_match = re.search(r"(?i)keywords?:?\s*(.+?)(?:\n\n|\n[A-Z])", content)

        if kw_match:
            kw_text = kw_match.group(1)
            keywords = re.split(r"[,;•·]", kw_text)
            return [kw.strip() for kw in keywords if kw.strip()][:10]

        return []


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING AND VECTOR OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════


class PaperEmbedder:
    """Generate embeddings for papers and chunks."""

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

    def embed_paper(self, paper: ResearchPaper) -> list[float]:
        """Generate embedding for entire paper (title + abstract)."""
        text = f"{paper.title}\n\n{paper.abstract}"
        return self.embed(text)

    def embed_chunk(self, chunk: PaperChunk) -> list[float]:
        """Generate embedding for a paper chunk."""
        return self.embed(chunk.content)

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        self._load_model()

        if self.model == "mock":
            return self._mock_embedding(text)

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        self._load_model()

        if self.model == "mock":
            return [self._mock_embedding(t) for t in texts]

        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def _mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic mock embedding."""
        hash_val = hashlib.md5(text.encode()).hexdigest()

        embedding = []
        for i in range(0, min(len(hash_val) * 12, self._dimension)):
            idx = i % len(hash_val)
            val = int(hash_val[idx : idx + 2], 16) / 255.0 - 0.5
            embedding.append(val)

        while len(embedding) < self._dimension:
            embedding.append(0.0)

        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding[: self._dimension]

    @property
    def dimension(self) -> int:
        return self._dimension


class PaperVectorStore:
    """Vector store for papers and chunks."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.paper_vectors: dict[str, list[float]] = {}
        self.chunk_vectors: list[tuple[str, str, list[float]]] = (
            []
        )  # (paper_id, chunk_id, vector)

    def add_paper(self, paper_id: str, vector: list[float]):
        """Add paper embedding."""
        self.paper_vectors[paper_id] = vector

    def add_chunk(self, paper_id: str, chunk_id: str, vector: list[float]):
        """Add chunk embedding."""
        self.chunk_vectors.append((paper_id, chunk_id, vector))

    def search_papers(
        self, query_vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Search papers by similarity."""
        similarities = []
        for paper_id, vec in self.paper_vectors.items():
            sim = self._cosine_similarity(query_vector, vec)
            similarities.append((paper_id, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def search_chunks(
        self, query_vector: list[float], top_k: int = 10
    ) -> list[tuple[str, str, float]]:
        """Search chunks by similarity."""
        similarities = []
        for paper_id, chunk_id, vec in self.chunk_vectors:
            sim = self._cosine_similarity(query_vector, vec)
            similarities.append((paper_id, chunk_id, sim))

        similarities.sort(key=lambda x: x[2], reverse=True)
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
# TOPIC MODELING
# ══════════════════════════════════════════════════════════════════════════════


class SimpleTopicModeler:
    """Simple TF-IDF based topic modeling."""

    def __init__(self, num_topics: int = 10):
        self.num_topics = num_topics
        self.vocabulary: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.topics: list[TopicCluster] = []

    def fit(self, papers: list[ResearchPaper]) -> list[TopicCluster]:
        """Fit topic model on papers."""
        if not papers:
            return []

        # Build vocabulary and IDF
        doc_freq: Counter = Counter()
        all_words: list[list[str]] = []

        for paper in papers:
            text = f"{paper.title} {paper.abstract} {' '.join(paper.keywords)}"
            words = self._tokenize(text)
            all_words.append(words)
            doc_freq.update(set(words))

        n_docs = len(papers)

        for word, freq in doc_freq.items():
            if freq >= 2:  # Appear in at least 2 docs
                self.vocabulary[word] = len(self.vocabulary)
                self.idf[word] = math.log(n_docs / (freq + 1)) + 1

        # Compute TF-IDF for each paper
        paper_vectors = []
        for words in all_words:
            tf = Counter(words)
            vector = {}
            for word, count in tf.items():
                if word in self.vocabulary:
                    vector[word] = count * self.idf[word]
            paper_vectors.append(vector)

        # Simple clustering by top keywords
        # Group papers by their most important keywords
        keyword_papers: dict[str, list[int]] = {}

        for i, vector in enumerate(paper_vectors):
            top_words = sorted(vector.items(), key=lambda x: x[1], reverse=True)[:5]
            for word, _ in top_words:
                if word not in keyword_papers:
                    keyword_papers[word] = []
                keyword_papers[word].append(i)

        # Create topic clusters from most common keywords
        sorted_keywords = sorted(
            keyword_papers.items(), key=lambda x: len(x[1]), reverse=True
        )

        topics = []
        assigned_papers: set = set()

        for keyword, paper_indices in sorted_keywords[: self.num_topics]:
            # Get related keywords
            related = []
            for idx in paper_indices[:5]:
                vector = paper_vectors[idx]
                related.extend(list(vector.keys())[:3])

            related_counter = Counter(related)
            topic_keywords = [kw for kw, _ in related_counter.most_common(5)]

            # Create topic
            topic_papers = [
                papers[i].id for i in paper_indices if i not in assigned_papers
            ]
            assigned_papers.update(paper_indices[:10])

            if topic_papers:
                topic = TopicCluster(
                    id=f"topic_{len(topics)}",
                    name=keyword.title(),
                    keywords=topic_keywords,
                    papers=topic_papers[:20],
                )
                topics.append(topic)

        self.topics = topics
        return topics

    def get_paper_topics(self, paper: ResearchPaper) -> list[str]:
        """Get topics for a paper."""
        text = f"{paper.title} {paper.abstract}"
        words = set(self._tokenize(text))

        paper_topics = []
        for topic in self.topics:
            overlap = len(words & set(topic.keywords))
            if overlap >= 2:
                paper_topics.append(topic.name)

        return paper_topics

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for topic modeling."""
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())

        stopwords = {
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
            "would",
            "could",
            "there",
            "their",
            "will",
            "each",
            "make",
            "like",
            "just",
            "over",
            "such",
            "with",
            "into",
            "year",
            "some",
            "them",
            "than",
            "then",
            "now",
            "look",
            "only",
            "come",
            "its",
            "also",
            "back",
            "after",
            "use",
            "how",
            "man",
            "well",
            "way",
            "even",
            "new",
            "want",
            "because",
            "any",
            "these",
            "give",
            "day",
            "most",
            "from",
            "this",
            "that",
            "which",
            "about",
            "paper",
            "results",
            "method",
            "using",
            "based",
            "propose",
            "proposed",
            "show",
            "shows",
            "approach",
            "work",
            "present",
            "section",
            "figure",
            "table",
        }

        return [w for w in words if w not in stopwords]


# ══════════════════════════════════════════════════════════════════════════════
# RESEARCH RAG PIPELINE
# ══════════════════════════════════════════════════════════════════════════════


class ResearchRAGPipeline:
    """Complete RAG pipeline for research papers."""

    def __init__(self, config: ResearchRAGConfig = None):
        self.config = config or ResearchRAGConfig()

        # Components
        self.parser = PaperParser()
        self.embedder = PaperEmbedder(self.config.embedding_model)
        self.vector_store = PaperVectorStore(self.config.embedding_dimension)
        self.topic_modeler = SimpleTopicModeler(self.config.num_topics)

        # Storage
        self.papers: dict[str, ResearchPaper] = {}
        self.chunks: dict[str, PaperChunk] = {}
        self.citation_graph: dict[str, list[str]] = {}  # paper_id -> cited_paper_ids

    def add_paper(
        self, content: str = None, path: str = None, metadata: dict = None
    ) -> ResearchPaper:
        """Add a research paper to the corpus."""
        if path:
            with open(path, encoding="utf-8") as f:
                content = f.read()

        if not content:
            raise ValueError("Either content or path must be provided")

        # Parse paper
        paper = self.parser.parse(content, metadata)

        # Chunk the paper
        paper.chunks = self._chunk_paper(paper)

        # Generate embeddings
        paper.embedding = self.embedder.embed_paper(paper)
        self.vector_store.add_paper(paper.id, paper.embedding)

        for chunk in paper.chunks:
            chunk.embedding = self.embedder.embed_chunk(chunk)
            self.vector_store.add_chunk(paper.id, chunk.id, chunk.embedding)
            self.chunks[chunk.id] = chunk

        # Build citation links
        for citation in paper.citations:
            # Check if cited paper is in our corpus
            for existing_id, existing_paper in self.papers.items():
                if self._is_same_paper(citation, existing_paper):
                    citation.cited_paper_id = existing_id
                    existing_paper.cited_by.append(paper.id)

                    if paper.id not in self.citation_graph:
                        self.citation_graph[paper.id] = []
                    self.citation_graph[paper.id].append(existing_id)

        self.papers[paper.id] = paper
        return paper

    def _is_same_paper(self, citation: Citation, paper: ResearchPaper) -> bool:
        """Check if a citation refers to a paper in corpus."""
        # Simple title similarity check
        cite_title_words = set(citation.title.lower().split())
        paper_title_words = set(paper.title.lower().split())

        overlap = len(cite_title_words & paper_title_words)
        return overlap >= min(3, len(paper_title_words) * 0.5)

    def _chunk_paper(self, paper: ResearchPaper) -> list[PaperChunk]:
        """Chunk a paper into smaller pieces."""
        chunks = []

        # Chunk by section
        for section, content in paper.sections.items():
            section_chunks = self._chunk_text(
                content, self.config.chunk_size, self.config.chunk_overlap
            )

            for i, chunk_text in enumerate(section_chunks):
                chunk = PaperChunk(
                    id=f"{paper.id}_{section.value}_{i}",
                    paper_id=paper.id,
                    section=section,
                    content=chunk_text,
                    chunk_index=i,
                    metadata={"section": section.value, "paper_title": paper.title},
                )
                chunks.append(chunk)

        # Also chunk full text if no sections
        if not chunks and paper.full_text:
            full_chunks = self._chunk_text(
                paper.full_text, self.config.chunk_size, self.config.chunk_overlap
            )

            for i, chunk_text in enumerate(full_chunks):
                chunk = PaperChunk(
                    id=f"{paper.id}_full_{i}",
                    paper_id=paper.id,
                    section=PaperSection.INTRODUCTION,
                    content=chunk_text,
                    chunk_index=i,
                )
                chunks.append(chunk)

        return chunks

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """Chunk text into overlapping pieces."""
        chunks = []

        # Split by paragraphs first
        paragraphs = re.split(r"\n\s*\n", text)

        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())

                # Keep overlap
                words = current_chunk.split()
                overlap_words = (
                    words[-overlap // 5 :] if len(words) > overlap // 5 else []
                )
                current_chunk = " ".join(overlap_words) + " " + para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def search(
        self,
        query: str,
        top_k: int = None,
        search_chunks: bool = True,
        search_papers: bool = True,
    ) -> list[SearchResult]:
        """Search the paper corpus."""
        top_k = top_k or self.config.top_k

        query_embedding = self.embedder.embed(query)
        results = []

        seen_papers = set()

        # Search chunks
        if search_chunks:
            chunk_results = self.vector_store.search_chunks(query_embedding, top_k * 2)

            for paper_id, chunk_id, score in chunk_results:
                if paper_id in seen_papers:
                    continue

                if paper_id in self.papers and chunk_id in self.chunks:
                    paper = self.papers[paper_id]
                    chunk = self.chunks[chunk_id]

                    results.append(
                        SearchResult(
                            paper=paper,
                            chunk=chunk,
                            score=score,
                            rank=0,
                            match_type="chunk",
                            snippet=chunk.content[:200],
                        )
                    )
                    seen_papers.add(paper_id)

        # Search papers (title + abstract)
        if search_papers:
            paper_results = self.vector_store.search_papers(query_embedding, top_k)

            for paper_id, score in paper_results:
                if paper_id in seen_papers:
                    continue

                if paper_id in self.papers:
                    paper = self.papers[paper_id]

                    results.append(
                        SearchResult(
                            paper=paper,
                            chunk=None,
                            score=score * 0.9,  # Slight penalty for abstract-only match
                            rank=0,
                            match_type="abstract",
                            snippet=paper.abstract[:200],
                        )
                    )
                    seen_papers.add(paper_id)

        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)

        # Apply citation boost
        results = self._apply_citation_boost(results)

        # Assign ranks
        for i, r in enumerate(results):
            r.rank = i + 1

        return results[:top_k]

    def _apply_citation_boost(self, results: list[SearchResult]) -> list[SearchResult]:
        """Boost scores based on citation count."""
        for result in results:
            cite_count = len(result.paper.cited_by)
            boost = 1.0 + (self.config.citation_weight * math.log(cite_count + 1))
            result.score *= boost

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def find_related_papers(self, paper_id: str, top_k: int = 5) -> list[SearchResult]:
        """Find papers related to a given paper."""
        if paper_id not in self.papers:
            return []

        paper = self.papers[paper_id]

        # Search using paper's abstract
        results = self.search(paper.abstract, top_k=top_k + 1)

        # Filter out the paper itself
        results = [r for r in results if r.paper.id != paper_id]

        # Also include cited/citing papers
        cited_papers = self.citation_graph.get(paper_id, [])
        citing_papers = paper.cited_by

        for related_id in (cited_papers + citing_papers)[:top_k]:
            if related_id in self.papers:
                related = self.papers[related_id]

                # Check if already in results
                if not any(r.paper.id == related_id for r in results):
                    results.append(
                        SearchResult(
                            paper=related,
                            chunk=None,
                            score=0.8,
                            rank=0,
                            match_type="citation",
                            snippet=related.abstract[:200],
                        )
                    )

        return results[:top_k]

    def generate_summary(self, paper_id: str) -> str:
        """Generate a summary of a paper."""
        if paper_id not in self.papers:
            return "Paper not found"

        paper = self.papers[paper_id]

        summary_parts = [
            f"# {paper.title}",
            f"**Authors:** {paper.author_string}",
            f"**Year:** {paper.year}",
            f"**Venue:** {paper.venue or 'Not specified'}",
            "",
            "## Abstract",
            paper.abstract[:500] if paper.abstract else "No abstract available",
        ]

        if paper.keywords:
            summary_parts.extend(["", f"**Keywords:** {', '.join(paper.keywords)}"])

        if paper.topics:
            summary_parts.extend(["", f"**Topics:** {', '.join(paper.topics)}"])

        # Key findings from sections
        key_sections = [
            PaperSection.CONCLUSION,
            PaperSection.RESULTS,
            PaperSection.DISCUSSION,
        ]

        for section in key_sections:
            if section in paper.sections:
                content = paper.sections[section]
                # Extract first few sentences
                sentences = re.split(r"(?<=[.!?])\s+", content)
                key_points = " ".join(sentences[:3])

                summary_parts.extend(
                    ["", f"## Key Points ({section.value.title()})", key_points[:400]]
                )
                break

        # Citations
        if paper.citations:
            summary_parts.extend(
                [
                    "",
                    f"## References ({len(paper.citations)} citations)",
                ]
            )
            for cite in paper.citations[:5]:
                summary_parts.append(f"- {cite.short_cite}: {cite.title[:60]}...")

        return "\n".join(summary_parts)

    def generate_literature_review(self, topic: str, max_papers: int = 10) -> str:
        """Generate a literature review for a topic."""
        results = self.search(topic, top_k=max_papers)

        if not results:
            return f"No papers found on topic: {topic}"

        review_parts = [
            f"# Literature Review: {topic}",
            f"*Generated from {len(results)} papers*",
            "",
            "## Overview",
            f"This review synthesizes {len(results)} papers related to {topic}.",
            "",
            "## Key Papers",
        ]

        for i, result in enumerate(results, 1):
            paper = result.paper

            review_parts.extend(
                [
                    "",
                    f"### {i}. {paper.title}",
                    f"*{paper.author_string} ({paper.year})*",
                    "",
                    result.snippet + "...",
                ]
            )

        # Common themes
        all_keywords = []
        for result in results:
            all_keywords.extend(result.paper.keywords)
            all_keywords.extend(result.paper.topics)

        if all_keywords:
            keyword_counts = Counter(all_keywords).most_common(10)
            review_parts.extend(
                [
                    "",
                    "## Common Themes",
                ]
            )
            for kw, count in keyword_counts:
                review_parts.append(f"- **{kw}** ({count} papers)")

        # Citation network
        cited_papers = []
        for result in results:
            cited_papers.extend(result.paper.citations[:3])

        if cited_papers:
            cite_counts = Counter([c.short_cite for c in cited_papers])
            review_parts.extend(
                [
                    "",
                    "## Frequently Cited Works",
                ]
            )
            for cite, count in cite_counts.most_common(5):
                review_parts.append(f"- {cite} (cited {count} times)")

        return "\n".join(review_parts)

    def fit_topics(self):
        """Fit topic model on all papers."""
        papers = list(self.papers.values())
        topics = self.topic_modeler.fit(papers)

        # Assign topics to papers
        for paper in papers:
            paper.topics = self.topic_modeler.get_paper_topics(paper)

        return topics

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        return {
            "papers": len(self.papers),
            "chunks": len(self.chunks),
            "topics": len(self.topic_modeler.topics),
            "citations": sum(len(p.citations) for p in self.papers.values()),
            "embedding_model": self.config.embedding_model,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE PAPERS FOR DEMO
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_PAPERS = [
    {
        "metadata": {
            "title": "Attention Is All You Need",
            "authors": "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit",
            "year": 2017,
            "venue": "NeurIPS",
            "type": "conference",
        },
        "content": """# Attention Is All You Need

## Abstract

The dominant sequence transduction models are based on complex recurrent or 
convolutional neural networks that include an encoder and a decoder. The best 
performing models also connect the encoder and decoder through an attention 
mechanism. We propose a new simple network architecture, the Transformer, 
based solely on attention mechanisms, dispensing with recurrence and convolutions 
entirely. Experiments on two machine translation tasks show these models to be 
superior in quality while being more parallelizable and requiring significantly 
less time to train.

Keywords: transformer, attention, neural networks, machine translation

## Introduction

Recurrent neural networks, long short-term memory and gated recurrent neural 
networks in particular, have been firmly established as state of the art approaches 
in sequence modeling and transduction problems such as language modeling and 
machine translation. Numerous efforts have since continued to push the boundaries 
of recurrent language models and encoder-decoder architectures.

The fundamental constraint of sequential computation remains a significant limitation. 
Attention mechanisms have become an integral part of compelling sequence modeling 
and transduction models in various tasks, allowing modeling of dependencies without 
regard to their distance in the input or output sequences.

## Methodology

We propose the Transformer, a model architecture eschewing recurrence and instead 
relying entirely on an attention mechanism to draw global dependencies between 
input and output. The Transformer allows for significantly more parallelization.

### Self-Attention

Self-attention, sometimes called intra-attention, is an attention mechanism 
relating different positions of a single sequence in order to compute a 
representation of the sequence.

### Multi-Head Attention

Instead of performing a single attention function with d_model-dimensional 
keys, values and queries, we found it beneficial to linearly project the 
queries, keys and values h times with different, learned linear projections.

## Results

The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German translation 
task, improving over the existing best results by over 2 BLEU. On the WMT 2014 
English-to-French translation task, our model establishes a new single-model 
state-of-the-art BLEU score of 41.0.

## Conclusion

We presented the Transformer, the first sequence transduction model based entirely 
on attention, replacing the recurrent layers most commonly used in encoder-decoder 
architectures with multi-headed self-attention.

## References

[1] Bahdanau, D., Cho, K., & Bengio, Y. (2014). "Neural machine translation by jointly learning to align and translate."
[2] Sutskever, I., Vinyals, O., & Le, Q. V. (2014). "Sequence to sequence learning with neural networks."
[3] Wu, Y., et al. (2016). "Google's neural machine translation system."
""",
    },
    {
        "metadata": {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors": "Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova",
            "year": 2019,
            "venue": "NAACL",
            "type": "conference",
        },
        "content": """# BERT: Pre-training of Deep Bidirectional Transformers

## Abstract

We introduce a new language representation model called BERT, which stands for 
Bidirectional Encoder Representations from Transformers. Unlike recent language 
representation models, BERT is designed to pre-train deep bidirectional 
representations from unlabeled text by jointly conditioning on both left and 
right context in all layers. As a result, the pre-trained BERT model can be 
fine-tuned with just one additional output layer to create state-of-the-art 
models for a wide range of tasks, such as question answering and language 
inference, without substantial task-specific architecture modifications.

Keywords: BERT, pre-training, transformers, NLP, language models

## Introduction

Language model pre-training has been shown to be effective for improving many 
natural language processing tasks. These include sentence-level tasks such as 
natural language inference and paraphrasing, which aim to predict the 
relationships between sentences by analyzing them holistically, as well as 
token-level tasks such as named entity recognition and question answering.

There are two existing strategies for applying pre-trained language 
representations to downstream tasks: feature-based and fine-tuning. BERT uses 
the fine-tuning approach.

## Methodology

BERT's model architecture is a multi-layer bidirectional Transformer encoder 
based on the original implementation described in Vaswani et al. (2017).

### Pre-training Tasks

We pre-train BERT using two unsupervised tasks:

**Masked Language Model (MLM):** We simply mask some percentage of the input 
tokens at random, and then predict those masked tokens.

**Next Sentence Prediction (NSP):** We pre-train a binarized next sentence 
prediction task.

## Results

BERT obtains new state-of-the-art results on eleven natural language processing 
tasks, including pushing the GLUE benchmark to 80.5%, MultiNLI accuracy to 86.7%, 
SQuAD v1.1 question answering Test F1 to 93.2.

## Conclusion

Recent empirical improvements due to transfer learning with language models have 
demonstrated that rich, unsupervised pre-training is an integral part of many 
language understanding systems. Our major contribution is further generalizing 
these findings to deep bidirectional architectures.

## References

[1] Vaswani, A., et al. (2017). "Attention is all you need."
[2] Peters, M. E., et al. (2018). "Deep contextualized word representations."
[3] Radford, A., et al. (2018). "Improving language understanding by generative pre-training."
""",
    },
    {
        "metadata": {
            "title": "GPT-3: Language Models are Few-Shot Learners",
            "authors": "Tom Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah",
            "year": 2020,
            "venue": "NeurIPS",
            "type": "conference",
        },
        "content": """# Language Models are Few-Shot Learners

## Abstract

Recent work has demonstrated substantial gains on many NLP tasks and benchmarks 
by pre-training on a large corpus of text followed by task-specific fine-tuning. 
We demonstrate that scaling up language models greatly improves task-agnostic, 
few-shot performance, sometimes even reaching competitiveness with prior 
state-of-the-art fine-tuning approaches. Specifically, we train GPT-3, an 
autoregressive language model with 175 billion parameters, and test its 
performance in the few-shot setting.

Keywords: GPT-3, language models, few-shot learning, NLP, scaling

## Introduction

Recent years have featured a trend towards pre-trained language representations 
in NLP systems, applied in increasingly flexible and task-agnostic ways. First, 
single-layer representations were learned using word vectors and used to improve 
word-level tasks. Then RNNs with multiple layers of representations were used 
to form stronger representations, and then transformers emerged.

## Methodology

We train GPT-3, an autoregressive language model with 175 billion parameters, 
10x more than any previous non-sparse language model. We test GPT-3's performance 
under few-shot, one-shot, and zero-shot conditions.

### Model Architecture

GPT-3 uses the same model and architecture as GPT-2, including the modified 
initialization, pre-normalization, and reversible tokenization, with the exception 
that we use alternating dense and locally banded sparse attention patterns.

## Results

GPT-3 achieves strong performance on many NLP datasets, including translation, 
question-answering, and cloze tasks, as well as several tasks that require 
on-the-fly reasoning or domain adaptation.

## Conclusion

We presented GPT-3, a 175 billion parameter autoregressive language model 
and measured its performance in zero-shot, one-shot, and few-shot settings 
on over two dozen NLP datasets.

## References

[1] Devlin, J., et al. (2019). "BERT: Pre-training of deep bidirectional transformers."
[2] Radford, A., et al. (2019). "Language models are unsupervised multitask learners."
[3] Vaswani, A., et al. (2017). "Attention is all you need."
""",
    },
    {
        "metadata": {
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "authors": "Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni",
            "year": 2020,
            "venue": "NeurIPS",
            "type": "conference",
        },
        "content": """# Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks

## Abstract

Large pre-trained language models have been shown to store factual knowledge 
in their parameters, and achieve state-of-the-art results when fine-tuned on 
downstream NLP tasks. However, their ability to access and precisely manipulate 
knowledge is still limited. We explore a general-purpose fine-tuning recipe for 
retrieval-augmented generation (RAG) — models which combine pre-trained parametric 
and non-parametric memory for language generation.

Keywords: RAG, retrieval, knowledge, generation, transformers

## Introduction

Pre-trained neural language models have been shown to learn substantial amounts 
of in-depth knowledge from data. They can do so without any access to external 
memory, relying on knowledge learned at pre-training time.

However, this approach has limitations: the knowledge is stored implicitly in 
parameters, requiring ever-larger models to cover more facts.

## Methodology

We endow pre-trained, parametric-memory generation models with a non-parametric 
memory through a general-purpose fine-tuning approach which we refer to as 
retrieval-augmented generation (RAG).

### RAG Architecture

RAG models combine a pre-trained seq2seq model (the generator) with a dense 
vector index of Wikipedia (the retriever). We use the input to retrieve 
relevant documents, and then pass these documents as additional context 
to the generator.

## Results

RAG achieves state-of-the-art results on three open-domain QA tasks, outperforming 
seq2seq models and task-specific retrieve-and-read architectures. On knowledge-
intensive generation tasks, RAG generates more factual, specific, and diverse 
responses than a state-of-the-art parametric seq2seq baseline.

## Conclusion

We introduced RAG models, which show strong performance across a variety of 
knowledge-intensive tasks. RAG combines the benefits of both parametric and 
non-parametric memory in a single approach.

## References

[1] Devlin, J., et al. (2019). "BERT: Pre-training of deep bidirectional transformers."
[2] Karpukhin, V., et al. (2020). "Dense passage retrieval for open-domain question answering."
[3] Brown, T., et al. (2020). "Language models are few-shot learners."
""",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run interactive research assistant demo."""
    print("=" * 70)
    print("🧠 Research Paper Assistant - RAG Demo")
    print("=" * 70)

    # Create pipeline
    config = ResearchRAGConfig(top_k=5, num_topics=5)
    pipeline = ResearchRAGPipeline(config)

    # Load sample papers
    print("\n📄 Loading research papers...")

    for paper_data in SAMPLE_PAPERS:
        paper = pipeline.add_paper(
            content=paper_data["content"], metadata=paper_data["metadata"]
        )
        print(f"  ✅ {paper.title[:50]}... ({len(paper.chunks)} chunks)")

    # Fit topics
    print("\n🏷️ Fitting topic model...")
    topics = pipeline.fit_topics()
    for topic in topics:
        print(f"  • {topic.name}: {', '.join(topic.keywords[:3])}")

    # Show stats
    stats = pipeline.get_stats()
    print("\n📊 Corpus Stats:")
    print(f"   Papers: {stats['papers']}")
    print(f"   Chunks: {stats['chunks']}")
    print(f"   Topics: {stats['topics']}")
    print(f"   Citations: {stats['citations']}")

    # Sample queries
    sample_queries = [
        "How does the transformer architecture work?",
        "What is BERT pre-training?",
        "Explain retrieval augmented generation",
        "What are the key findings about attention mechanisms?",
    ]

    print("\n" + "=" * 70)
    print("💡 Sample questions you can ask:")
    for q in sample_queries:
        print(f"   • {q}")

    # Interactive loop
    print("\n" + "=" * 70)
    print("💬 Search research papers (type 'quit' to exit)")
    print("   Commands: 'summary <id>' - paper summary")
    print("             'related <id>' - find related papers")
    print("             'review <topic>' - generate literature review")
    print("             'list' - list all papers")
    print("=" * 70)

    while True:
        try:
            query = input("\n🔍 Search: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query:
            continue

        if query.lower() == "quit":
            break

        if query.lower() == "list":
            print("\n📚 Papers in corpus:")
            for pid, paper in pipeline.papers.items():
                print(f"   [{pid[:8]}] {paper.title}")
            continue

        if query.lower().startswith("summary "):
            paper_id = query[8:].strip()
            # Find paper by partial ID
            for pid in pipeline.papers:
                if pid.startswith(paper_id):
                    summary = pipeline.generate_summary(pid)
                    print(f"\n{summary}")
                    break
            else:
                print(f"❌ Paper not found: {paper_id}")
            continue

        if query.lower().startswith("related "):
            paper_id = query[8:].strip()
            for pid in pipeline.papers:
                if pid.startswith(paper_id):
                    results = pipeline.find_related_papers(pid)
                    print(
                        f"\n📚 Papers related to {pipeline.papers[pid].title[:40]}..."
                    )
                    for r in results:
                        print(f"   • {r.paper.title} ({r.match_type})")
                    break
            else:
                print(f"❌ Paper not found: {paper_id}")
            continue

        if query.lower().startswith("review "):
            topic = query[7:].strip()
            review = pipeline.generate_literature_review(topic)
            print(f"\n{review}")
            continue

        # Regular search
        results = pipeline.search(query)

        if not results:
            print("\n❌ No results found")
            continue

        print(f"\n🔎 Found {len(results)} results:\n")

        for r in results:
            paper = r.paper
            print(f"  {r.rank}. {paper.title}")
            print(f"     Authors: {paper.author_string}")
            print(f"     Year: {paper.year} | Venue: {paper.venue}")
            print(f"     Score: {r.score:.3f} ({r.match_type})")
            print(f"     ID: {paper.id[:8]}")

            if r.snippet:
                snippet = r.snippet[:150]
                if len(r.snippet) > 150:
                    snippet += "..."
                print(f"     Snippet: {snippet}")
            print()

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
