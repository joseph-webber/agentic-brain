# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
Advanced reranking for RAG retrieval results.

Provides multiple strategies to reorder search results by relevance:
- Cross-encoder reranking: Use dedicated model for query-document relevance
- Maximal Marginal Relevance (MMR): Balance relevance and diversity
- Diversity reranking: Reduce redundancy in results

Usage:
    from agentic_brain.rag.reranking import Reranker, MMRReranker
    from agentic_brain.rag.retriever import RetrievedChunk
    
    # Simple cross-encoder reranking
    reranker = Reranker()
    reranked = reranker.rerank(query, chunks)
    
    # MMR for diverse results
    mmr = MMRReranker()
    diverse_chunks = mmr.rerank(query, chunks)
"""

import math
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .retriever import RetrievedChunk
from .embeddings import EmbeddingProvider, get_embeddings

# Default reranking parameters
DEFAULT_RERANK_TOP_K = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.5
DEFAULT_MMR_LAMBDA = 0.5


@dataclass
class RerankResult:
    """Result of reranking operation."""
    original_chunks: List[RetrievedChunk]
    reranked_chunks: List[RetrievedChunk]
    scores: Dict[int, float]  # Maps chunk index to new score
    strategy: str
    query: str


class BaseReranker(ABC):
    """Base class for all reranking strategies."""
    
    def __init__(self, top_k: Optional[int] = None) -> None:
        """
        Initialize reranker.
        
        Args:
            top_k: Keep only top k results after reranking (None = keep all)
        """
        self.top_k = top_k
    
    @abstractmethod
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Rerank chunks by relevance.
        
        Args:
            query: Query string
            chunks: Retrieved chunks to rerank
        
        Returns:
            Reranked chunks
        """
        pass
    
    def _apply_top_k(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Limit results to top_k if specified."""
        if self.top_k and len(chunks) > self.top_k:
            return chunks[:self.top_k]
        return chunks


class QueryDocumentSimilarityReranker(BaseReranker):
    """
    Rerank by query-document similarity using embeddings.
    
    Uses embedding provider to compute similarity scores.
    Simpler than cross-encoders but still effective.
    """
    
    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        top_k: Optional[int] = DEFAULT_RERANK_TOP_K
    ) -> None:
        """
        Initialize similarity reranker.
        
        Args:
            embedding_provider: Provider for generating embeddings
            top_k: Keep only top k results
        """
        super().__init__(top_k)
        self.embeddings = embedding_provider or get_embeddings()
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between vectors."""
        a = np.array(a)
        b = np.array(b)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Rerank chunks using embedding similarity."""
        if not chunks:
            return chunks
        
        # Get query embedding
        query_embedding = self.embeddings.embed(query)
        
        # Batch embed all chunks at once (avoid N+1 embedding calls)
        chunk_contents = [chunk.content for chunk in chunks]
        chunk_embeddings = self.embeddings.embed_batch(chunk_contents)
        
        # Score each chunk
        scored_chunks = []
        for chunk, content_embedding in zip(chunks, chunk_embeddings):
            similarity = self._cosine_similarity(query_embedding, content_embedding)
            
            # Create new chunk with updated score
            reranked_chunk = RetrievedChunk(
                content=chunk.content,
                source=chunk.source,
                score=similarity,
                metadata={**chunk.metadata, "original_score": chunk.score}
            )
            scored_chunks.append(reranked_chunk)
        
        # Sort by new scores
        scored_chunks.sort(key=lambda x: x.score, reverse=True)
        
        return self._apply_top_k(scored_chunks)


class CrossEncoderReranker(BaseReranker):
    """
    Rerank using cross-encoder model.
    
    Cross-encoders directly score query-document pairs, typically more
    accurate than embedding-based approaches but slower.
    
    Requires: sentence-transformers package
    Falls back to similarity reranker if cross-encoder unavailable.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        top_k: Optional[int] = None,
        batch_size: int = 32
    ) -> None:
        """
        Initialize cross-encoder reranker.
        
        Args:
            model_name: HuggingFace model identifier
            top_k: Keep only top k results
            batch_size: Batch size for scoring
        """
        super().__init__(top_k)
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = None
        self._init_model()
    
    def _init_model(self) -> None:
        """Initialize cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
        except ImportError:
            print(f"⚠️  sentence-transformers not installed. Install with:")
            print("   pip install sentence-transformers")
            print("   Falling back to embedding-based reranking.")
            self.model = None
    
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Rerank chunks using cross-encoder."""
        if not chunks:
            return chunks
        
        if not self.model:
            # Fallback to embedding similarity
            fallback = QueryDocumentSimilarityReranker(top_k=self.top_k)
            return fallback.rerank(query, chunks)
        
        # Prepare query-document pairs
        query_doc_pairs = [
            [query, chunk.content] for chunk in chunks
        ]
        
        # Score in batches
        scores = []
        for i in range(0, len(query_doc_pairs), self.batch_size):
            batch = query_doc_pairs[i:i + self.batch_size]
            batch_scores = self.model.predict(batch)
            scores.extend(batch_scores)
        
        # Normalize scores to 0-1 range
        scores = np.array(scores)
        min_score = scores.min()
        max_score = scores.max()
        if max_score > min_score:
            scores = (scores - min_score) / (max_score - min_score)
        else:
            scores = np.ones_like(scores)
        
        # Create reranked chunks
        reranked_chunks = []
        for chunk, score in zip(chunks, scores):
            reranked_chunk = RetrievedChunk(
                content=chunk.content,
                source=chunk.source,
                score=float(score),
                metadata={**chunk.metadata, "original_score": chunk.score}
            )
            reranked_chunks.append(reranked_chunk)
        
        # Sort by new scores
        reranked_chunks.sort(key=lambda x: x.score, reverse=True)
        
        return self._apply_top_k(reranked_chunks)


class MMRReranker(BaseReranker):
    """
    Maximal Marginal Relevance (MMR) reranking.
    
    Balances relevance and diversity by:
    1. Selecting most relevant item first
    2. For each subsequent item, balance relevance to query
       with dissimilarity to already selected items
    
    Good for: Avoiding redundant results, diverse perspectives.
    
    Lambda parameter controls relevance/diversity tradeoff:
    - lambda=1.0: Maximize relevance (like standard ranking)
    - lambda=0.5: Balance relevance and diversity
    - lambda=0.0: Maximize diversity
    """
    
    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        top_k: Optional[int] = DEFAULT_RERANK_TOP_K,
        lambda_weight: float = DEFAULT_MMR_LAMBDA
    ) -> None:
        """
        Initialize MMR reranker.
        
        Args:
            embedding_provider: Provider for embeddings
            top_k: Keep only top k results
            lambda_weight: Relevance/diversity tradeoff (0-1)
        """
        super().__init__(top_k)
        self.embeddings = embedding_provider or get_embeddings()
        self.lambda_weight = max(0.0, min(1.0, lambda_weight))
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity."""
        a = np.array(a)
        b = np.array(b)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Apply MMR reranking."""
        if not chunks:
            return chunks
        
        if len(chunks) == 1:
            return chunks
        
        # Get embeddings using batch API (avoid N+1 embedding calls)
        query_embedding = self.embeddings.embed(query)
        chunk_embeddings = self.embeddings.embed_batch([chunk.content for chunk in chunks])
        
        # Calculate query relevance scores
        relevance_scores = [
            self.lambda_weight * self._cosine_similarity(query_embedding, emb)
            for emb in chunk_embeddings
        ]
        
        # MMR selection
        selected_indices = []
        remaining_indices = set(range(len(chunks)))
        
        # Select first item (highest relevance)
        first_idx = max(remaining_indices, key=lambda i: relevance_scores[i])
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)
        
        # Greedily select remaining items
        while remaining_indices:
            mmr_scores = []
            
            for idx in remaining_indices:
                # Relevance component
                relevance = relevance_scores[idx]
                
                # Diversity component: min distance to selected items
                if selected_indices:
                    diversity_score = min([
                        self._cosine_similarity(chunk_embeddings[idx], chunk_embeddings[s])
                        for s in selected_indices
                    ])
                else:
                    diversity_score = 0.0
                
                # MMR score: maximize relevance, minimize similarity to selected
                mmr = relevance - (1 - self.lambda_weight) * diversity_score
                mmr_scores.append((idx, mmr))
            
            # Select item with highest MMR score
            best_idx, _ = max(mmr_scores, key=lambda x: x[1])
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)
        
        # Return chunks in MMR order
        reranked_chunks = [chunks[idx] for idx in selected_indices]
        
        return self._apply_top_k(reranked_chunks)


class CombinedReranker(BaseReranker):
    """
    Combine multiple rerankers using weighted scoring.
    
    Useful for ensemble approaches to balance different ranking signals.
    """
    
    def __init__(
        self,
        rerankers: List[tuple],  # List of (reranker, weight) tuples
        top_k: Optional[int] = None
    ) -> None:
        """
        Initialize combined reranker.
        
        Args:
            rerankers: List of (reranker, weight) tuples
            top_k: Keep only top k results
        """
        super().__init__(top_k)
        
        # Normalize weights
        total_weight = sum(w for _, w in rerankers)
        self.rerankers = [
            (r, w / total_weight) for r, w in rerankers
        ]
    
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Rerank using ensemble of strategies."""
        if not chunks:
            return chunks
        
        # Get scores from each reranker
        combined_scores = {i: 0.0 for i in range(len(chunks))}
        
        for reranker, weight in self.rerankers:
            reranked = reranker.rerank(query, chunks)
            
            # Map positions to scores
            for pos, chunk in enumerate(reranked):
                # Find original index
                for orig_idx, orig_chunk in enumerate(chunks):
                    if (orig_chunk.content == chunk.content and
                        orig_chunk.source == chunk.source):
                        # Higher rank = higher score
                        score = (1.0 - pos / len(reranked)) * weight
                        combined_scores[orig_idx] += score
                        break
        
        # Sort by combined scores
        scored_chunks = [
            (chunks[i], combined_scores[i]) for i in range(len(chunks))
        ]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        reranked_chunks = [chunk for chunk, _ in scored_chunks]
        
        return self._apply_top_k(reranked_chunks)


class Reranker(CrossEncoderReranker):
    """
    Default reranker using cross-encoder with fallback.
    
    Tries to use cross-encoder, falls back to similarity-based reranking.
    Most accurate results.
    """
    pass
