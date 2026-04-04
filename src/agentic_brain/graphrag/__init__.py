# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
GraphRAG Module — Graph + Vector Hybrid Retrieval

Adapted from Arraz's P23-brain-graphrag implementation.

Components:
- embed_pipeline: Text → Vector embeddings (Ollama/OpenAI)
- entity_extractor: Extract named entities from text via LLM
- synthesis_layer: Hybrid retrieval (ANN + graph traversal) with RRF merge

Usage:
    from agentic_brain.graphrag import recall, embed_sessions, extract_entities
    
    # Query the brain
    answer = recall("What work was done on the voice system?")
    
    # Embed session summaries
    embed_sessions()
    
    # Extract entities from sessions
    extract_entities()
"""

from .embed_pipeline import embed_sessions, embed_text, EmbeddingProvider
from .entity_extractor import extract_entities, EntityExtractor
from .synthesis_layer import recall, GraphRAGSynthesis

__all__ = [
    "recall",
    "embed_sessions",
    "embed_text",
    "extract_entities",
    "EmbeddingProvider",
    "EntityExtractor",
    "GraphRAGSynthesis",
]
