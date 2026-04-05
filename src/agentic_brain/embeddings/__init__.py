# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Embeddings Module

Comprehensive embedding model support for the agentic-brain framework.
Supports OpenAI, Cohere, Sentence Transformers, Voyage AI, and Jina embeddings
with batch processing, rate limiting, and both sync/async interfaces.
"""

from .base import (
    Embedder,
    EmbeddingProvider,
    EmbeddingResult,
    BatchEmbeddingResult,
)
from .openai import OpenAIEmbedder
from .cohere import CohereEmbedder
from .sentence_transformers import SentenceTransformersEmbedder, E5Embedder
from .voyage import VoyageEmbedder
from .jina import JinaEmbedder

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
