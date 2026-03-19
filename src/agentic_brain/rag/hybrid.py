# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
Hybrid search combining vector and keyword search.

Combines semantic search (embeddings) with lexical search (BM25)
for best of both worlds:
- Vector search: Understands meaning, catches synonyms
- Keyword search: Perfect for exact terms, acronyms, technical terms

Usage:
    from agentic_brain.rag.hybrid import HybridSearch
    
    search = HybridSearch(index_path="./bm25_index")
    results = search.search(
        query="machine learning basics",
        k=5,
        vector_weight=0.6,
        keyword_weight=0.4
    )
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from .retriever import RetrievedChunk
from .embeddings import EmbeddingProvider, get_embeddings


@dataclass
class HybridSearchResult:
    """Result from hybrid search."""
    query: str
    vector_results: List[RetrievedChunk]
    keyword_results: List[RetrievedChunk]
    fused_results: List[RetrievedChunk]
    vector_weight: float
    keyword_weight: float
    fusion_method: str


class BM25Index:
    """
    Simple BM25 implementation for keyword search.
    
    BM25 is the standard ranking function for keyword search,
    used by Elasticsearch, Lucene, etc.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        """
        Initialize BM25 index.
        
        Args:
            k1: Controls term frequency saturation (typically 1.5)
            b: Controls how much document length affects scoring (typically 0.75)
        """
        self.k1 = k1
        self.b = b
        self.docs = []  # List of documents
        self.idf = {}  # IDF values for terms
        self.avg_doc_len = 0.0
    
    def add_document(self, doc_id: str, text: str) -> None:
        """Add document to index."""
        tokens = self._tokenize(text)
        self.docs.append({
            "id": doc_id,
            "text": text,
            "tokens": tokens,
            "length": len(tokens)
        })
    
    def build_index(self) -> None:
        """Build the index (compute IDF values)."""
        if not self.docs:
            return
        
        # Calculate average document length
        self.avg_doc_len = sum(d["length"] for d in self.docs) / len(self.docs)
        
        # Calculate IDF for each term
        doc_freqs = {}
        for doc in self.docs:
            unique_tokens = set(doc["tokens"])
            for token in unique_tokens:
                doc_freqs[token] = doc_freqs.get(token, 0) + 1
        
        num_docs = len(self.docs)
        for token, freq in doc_freqs.items():
            # IDF = log((N - df + 0.5) / (df + 0.5))
            self.idf[token] = np.log((num_docs - freq + 0.5) / (freq + 0.5) + 1)
    
    def search(self, query: str, k: int = 5) -> List[tuple]:
        """
        Search index.
        
        Returns:
            List of (doc_id, score) tuples
        """
        query_tokens = self._tokenize(query)
        scores = []
        
        for doc in self.docs:
            score = 0.0
            
            for token in query_tokens:
                if token not in self.idf:
                    continue
                
                # Count token occurrences in document
                tf = doc["tokens"].count(token)
                
                # BM25 formula
                idf = self.idf[token]
                numerator = idf * tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * (doc["length"] / self.avg_doc_len)
                )
                score += numerator / denominator
            
            if score > 0:
                scores.append((doc["id"], score))
        
        # Sort by score and return top k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        import re
        
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r'\w+', text.lower())
        
        # Remove common stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could'
        }
        
        return [t for t in tokens if t not in stopwords]
    
    def save(self, path: Path) -> None:
        """Save index to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "k1": self.k1,
            "b": self.b,
            "docs": self.docs,
            "idf": self.idf,
            "avg_doc_len": self.avg_doc_len
        }
        with open(path, "w") as f:
            json.dump(data, f)
    
    def load(self, path: Path) -> None:
        """Load index from disk."""
        with open(path, "r") as f:
            data = json.load(f)
        
        self.k1 = data["k1"]
        self.b = data["b"]
        self.docs = data["docs"]
        self.idf = data["idf"]
        self.avg_doc_len = data["avg_doc_len"]


class HybridSearch:
    """
    Hybrid search combining vector and keyword search.
    
    Typical fusion weights:
    - Balanced (default): 0.5 vector, 0.5 keyword
    - Vector-focused: 0.7 vector, 0.3 keyword (when semantic understanding is critical)
    - Keyword-focused: 0.3 vector, 0.7 keyword (technical docs with exact terms)
    """
    
    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        index_path: Optional[str] = None,
        k1: float = 1.5,
        b: float = 0.75
    ) -> None:
        """
        Initialize hybrid search.
        
        Args:
            embedding_provider: Provider for vector search
            index_path: Path to save/load BM25 index
            k1, b: BM25 parameters
        """
        self.embeddings = embedding_provider or get_embeddings()
        self.index_path = Path(index_path) if index_path else None
        self.bm25 = BM25Index(k1=k1, b=b)
        self.doc_chunks = {}  # Map from doc_id to RetrievedChunk
        
        # Load index if exists
        if self.index_path and self.index_path.exists():
            self.bm25.load(self.index_path)
    
    def add_documents(self, chunks: List[RetrievedChunk]) -> None:
        """Add documents to hybrid index."""
        for i, chunk in enumerate(chunks):
            doc_id = f"doc_{i}"
            self.bm25.add_document(doc_id, chunk.content)
            self.doc_chunks[doc_id] = chunk
        
        self.bm25.build_index()
        
        # Save index
        if self.index_path:
            self.bm25.save(self.index_path)
    
    def search(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        k: int = 5,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        fusion_method: str = "rrf"  # rrf | linear
    ) -> HybridSearchResult:
        """
        Perform hybrid search.
        
        Args:
            query: Search query
            chunks: Documents to search
            k: Number of results
            vector_weight: Weight for vector search (0-1)
            keyword_weight: Weight for keyword search (0-1)
            fusion_method: How to combine results (rrf=Reciprocal Rank Fusion, linear=weighted sum)
        
        Returns:
            HybridSearchResult
        """
        # Ensure chunks are indexed
        if not self.doc_chunks:
            self.add_documents(chunks)
        
        # Vector search
        query_embedding = self.embeddings.embed(query)
        vector_results = self._vector_search(query_embedding, chunks, k)
        
        # Keyword search
        keyword_results_raw = self.bm25.search(query, k)
        keyword_results = [
            self.doc_chunks[doc_id] for doc_id, _ in keyword_results_raw
            if doc_id in self.doc_chunks
        ]
        
        # Fuse results
        if fusion_method == "rrf":
            fused = self._reciprocal_rank_fusion(vector_results, keyword_results, k)
        else:
            fused = self._linear_fusion(
                vector_results, keyword_results, k,
                vector_weight, keyword_weight
            )
        
        return HybridSearchResult(
            query=query,
            vector_results=vector_results[:k],
            keyword_results=keyword_results[:k],
            fused_results=fused,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            fusion_method=fusion_method
        )
    
    def _vector_search(
        self,
        query_embedding: List[float],
        chunks: List[RetrievedChunk],
        k: int
    ) -> List[RetrievedChunk]:
        """Perform vector similarity search."""
        query_embedding = np.array(query_embedding)
        
        scored_chunks = []
        for chunk in chunks:
            chunk_embedding = self.embeddings.embed(chunk.content)
            chunk_embedding = np.array(chunk_embedding)
            
            # Cosine similarity
            similarity = np.dot(query_embedding, chunk_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding) + 1e-10
            )
            
            scored_chunks.append((chunk, float(similarity)))
        
        # Sort by similarity
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Create new chunks with vector search scores
        return [
            RetrievedChunk(
                content=chunk.content,
                source=chunk.source,
                score=score,
                metadata={**chunk.metadata, "search_type": "vector"}
            )
            for chunk, score in scored_chunks[:k]
        ]
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievedChunk],
        keyword_results: List[RetrievedChunk],
        k: int,
        k_rrf: int = 60
    ) -> List[RetrievedChunk]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF = sum(1 / (k + rank)) for each ranking
        Good for combining diverse ranking signals.
        """
        rrf_scores = {}
        
        # Add vector results
        for rank, chunk in enumerate(vector_results):
            key = (chunk.content, chunk.source)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k_rrf + rank + 1)
        
        # Add keyword results
        for rank, chunk in enumerate(keyword_results):
            key = (chunk.content, chunk.source)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k_rrf + rank + 1)
        
        # Combine results
        all_chunks = {(c.content, c.source): c for c in vector_results + keyword_results}
        
        # Sort by RRF score
        sorted_results = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        fused = []
        for (content, source), score in sorted_results[:k]:
            chunk = all_chunks[(content, source)]
            fused_chunk = RetrievedChunk(
                content=chunk.content,
                source=chunk.source,
                score=score,
                metadata={**chunk.metadata, "fusion_method": "rrf"}
            )
            fused.append(fused_chunk)
        
        return fused
    
    def _linear_fusion(
        self,
        vector_results: List[RetrievedChunk],
        keyword_results: List[RetrievedChunk],
        k: int,
        vector_weight: float,
        keyword_weight: float
    ) -> List[RetrievedChunk]:
        """
        Combine results using weighted linear fusion.
        
        Score = vector_weight * vector_score + keyword_weight * keyword_score
        """
        # Create lookup for results
        vector_lookup = {
            (c.content, c.source): c for c in vector_results
        }
        keyword_lookup = {
            (c.content, c.source): c for c in keyword_results
        }
        
        fusion_scores = {}
        
        # Score vector results
        for rank, chunk in enumerate(vector_results):
            # Normalize rank to score (higher rank = lower score)
            normalized_score = 1.0 - (rank / max(len(vector_results), 1))
            key = (chunk.content, chunk.source)
            fusion_scores[key] = vector_weight * normalized_score
        
        # Add keyword results
        for rank, chunk in enumerate(keyword_results):
            normalized_score = 1.0 - (rank / max(len(keyword_results), 1))
            key = (chunk.content, chunk.source)
            fusion_scores[key] = fusion_scores.get(key, 0) + keyword_weight * normalized_score
        
        # Sort by fusion score
        all_chunks = {**vector_lookup, **keyword_lookup}
        sorted_results = sorted(
            fusion_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        fused = []
        for (content, source), score in sorted_results[:k]:
            chunk = all_chunks[(content, source)]
            fused_chunk = RetrievedChunk(
                content=chunk.content,
                source=chunk.source,
                score=score,
                metadata={**chunk.metadata, "fusion_method": "linear"}
            )
            fused.append(fused_chunk)
        
        return fused
