# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Embeddings Module

Comprehensive embedding model support for the agentic-brain framework.
Supports OpenAI, Cohere, Sentence Transformers, Voyage AI, and Jina embeddings
with batch processing, rate limiting, and both sync/async interfaces.
"""

from .base import (
    BatchEmbeddingResult,
    Embedder,
    EmbeddingProvider,
    EmbeddingResult,
)
from .cohere import CohereEmbedder
from .jina import JinaEmbedder
from .openai import OpenAIEmbedder
from .sentence_transformers import E5Embedder, SentenceTransformersEmbedder
from .voyage import VoyageEmbedder

__all__ = [
    "Embedder",
    "EmbeddingProvider",
    "EmbeddingResult",
    "BatchEmbeddingResult",
    "OpenAIEmbedder",
    "CohereEmbedder",
    "SentenceTransformersEmbedder",
    "E5Embedder",
    "VoyageEmbedder",
    "JinaEmbedder",
]

__version__ = "1.0.0"
