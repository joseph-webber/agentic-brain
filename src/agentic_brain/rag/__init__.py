# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
RAG (Retrieval-Augmented Generation) Pipeline

Production-ready RAG with:
- Multi-source retrieval (Neo4j, files, APIs)
- Semantic search with embeddings
- Advanced chunking strategies (fixed, semantic, recursive, markdown)
- Reranking for precision (cross-encoder, MMR, diversity)
- Hybrid search (vector + keyword BM25)
- Evaluation and A/B testing
- Source citation with confidence scores
- Caching for efficiency

For advanced RAG features (multi-tenant isolation, streaming),
see: https://github.com/joseph-webber/brain-core

Usage:
    from agentic_brain.rag import RAGPipeline, ask
    
    # Quick interface
    answer = ask("What is the status of project X?")
    
    # Full pipeline with advanced features
    rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
    result = rag.query("How do I deploy?")
    
    # Advanced chunking
    from agentic_brain.rag import create_chunker, ChunkingStrategy
    chunker = create_chunker(ChunkingStrategy.MARKDOWN)
    chunks = chunker.chunk(text)
    
    # Reranking
    from agentic_brain.rag import Reranker, MMRReranker
    reranker = Reranker()
    reranked = reranker.rerank(query, chunks)
    
    # Hybrid search
    from agentic_brain.rag import HybridSearch
    search = HybridSearch()
    results = search.search(query, chunks)
    
    # Evaluation
    from agentic_brain.rag import RAGEvaluator, EvalDataset
    evaluator = RAGEvaluator()
    dataset = EvalDataset()
    metrics = evaluator.evaluate(rag.query, dataset)
"""

# Core pipeline
from .pipeline import RAGPipeline, RAGResult, ask
from .retriever import Retriever, RetrievedChunk
from .embeddings import EmbeddingProvider, get_embeddings

# Advanced chunking
from .chunking import (
    BaseChunker,
    Chunk,
    ChunkingStrategy,
    FixedChunker,
    SemanticChunker,
    RecursiveChunker,
    MarkdownChunker,
    create_chunker,
)

# Advanced reranking
from .reranking import (
    BaseReranker,
    RerankResult,
    QueryDocumentSimilarityReranker,
    CrossEncoderReranker,
    MMRReranker,
    CombinedReranker,
    Reranker,
)

# Hybrid search
from .hybrid import (
    BM25Index,
    HybridSearch,
    HybridSearchResult,
)

# Evaluation
from .evaluation import (
    EvalQuery,
    EvalMetrics,
    EvalResults,
    EvalDataset,
    RAGEvaluator,
)

__all__ = [
    # Core
    "RAGPipeline",
    "RAGResult",
    "ask",
    "Retriever",
    "RetrievedChunk",
    "EmbeddingProvider",
    "get_embeddings",
    # Chunking
    "BaseChunker",
    "Chunk",
    "ChunkingStrategy",
    "FixedChunker",
    "SemanticChunker",
    "RecursiveChunker",
    "MarkdownChunker",
    "create_chunker",
    # Reranking
    "BaseReranker",
    "RerankResult",
    "QueryDocumentSimilarityReranker",
    "CrossEncoderReranker",
    "MMRReranker",
    "CombinedReranker",
    "Reranker",
    # Hybrid Search
    "BM25Index",
    "HybridSearch",
    "HybridSearchResult",
    # Evaluation
    "EvalQuery",
    "EvalMetrics",
    "EvalResults",
    "EvalDataset",
    "RAGEvaluator",
]
