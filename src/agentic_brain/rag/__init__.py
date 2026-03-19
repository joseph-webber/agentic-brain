# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
RAG (Retrieval-Augmented Generation) Pipeline

Production-ready RAG with:
- Multi-source retrieval (Neo4j, files, APIs)
- Semantic search with embeddings
- Reranking for precision
- Source citation with confidence scores
- Caching for efficiency

For advanced RAG features (cross-encoder reranking, MLX acceleration,
multi-tenant isolation), see: https://github.com/joseph-webber/brain-core

Usage:
    from agentic_brain.rag import RAGPipeline, ask
    
    # Quick interface
    answer = ask("What is the status of project X?")
    
    # Full pipeline
    rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
    result = rag.query("How do I deploy?")
    print(result.answer)
    print(result.sources)
"""

from .pipeline import RAGPipeline, RAGResult, ask
from .retriever import Retriever, RetrievedChunk
from .embeddings import EmbeddingProvider, get_embeddings

__all__ = [
    "RAGPipeline",
    "RAGResult", 
    "ask",
    "Retriever",
    "RetrievedChunk",
    "EmbeddingProvider",
    "get_embeddings",
]
