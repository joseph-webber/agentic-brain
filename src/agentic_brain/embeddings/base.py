# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Base Embedder Abstract Base Class

Defines the interface for all embedding models in the agentic-brain framework.
Supports sync/async embedding, batch operations, and dimension specification.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import numpy as np
from dataclasses import dataclass
from enum import Enum


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    COHERE = "cohere"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    VOYAGE = "voyage"
    JINA = "jina"
    LOCAL = "local"


@dataclass
class EmbeddingResult:
    """Result of a single embedding operation."""
    text: str
    embedding: np.ndarray
    dimension: int
    provider: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None


@dataclass
class BatchEmbeddingResult:
    """Result of a batch embedding operation."""
    results: List[EmbeddingResult]
    total_texts: int
    successful: int
    failed: int
    total_tokens_used: int
    total_latency_ms: float
    errors: List[Dict[str, Any]]


class Embedder(ABC):
    """
    Abstract base class for all embedding models.
    
    All embedder implementations must inherit from this class and implement
    the required abstract methods.
    """

    @property
    @abstractmethod
    def provider(self) -> EmbeddingProvider:
        """Return the embedding provider."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model name/identifier."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass

    @abstractmethod
    def embed_sync(self, text: str) -> EmbeddingResult:
        """
        Synchronously embed a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            EmbeddingResult with embedding vector and metadata
            
        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding fails
        """
        pass

    @abstractmethod
    async def embed_async(self, text: str) -> EmbeddingResult:
        """
        Asynchronously embed a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            EmbeddingResult with embedding vector and metadata
            
        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding fails
        """
        pass

    @abstractmethod
    def embed_batch_sync(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> BatchEmbeddingResult:
        """
        Synchronously embed a batch of texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per batch
            show_progress: Whether to show progress bar
            
        Returns:
            BatchEmbeddingResult with all embeddings and statistics
        """
        pass

    @abstractmethod
    async def embed_batch_async(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
        concurrent_requests: int = 5,
    ) -> BatchEmbeddingResult:
        """
        Asynchronously embed a batch of texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per batch
            show_progress: Whether to show progress bar
            concurrent_requests: Number of concurrent requests
            
        Returns:
            BatchEmbeddingResult with all embeddings and statistics
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections or resources."""
        pass

    def validate_text(self, text: str) -> None:
        """
        Validate text before embedding.
        
        Args:
            text: Text to validate
            
        Raises:
            ValueError: If text is invalid
        """
        if not isinstance(text, str):
            raise ValueError(f"Text must be string, got {type(text)}")
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace-only")

    def validate_texts(self, texts: List[str]) -> None:
        """
        Validate list of texts before embedding.
        
        Args:
            texts: Texts to validate
            
        Raises:
            ValueError: If texts are invalid
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")
        if not isinstance(texts, list):
            raise ValueError(f"Texts must be list, got {type(texts)}")
        for i, text in enumerate(texts):
            try:
                self.validate_text(text)
            except ValueError as e:
                raise ValueError(f"Text at index {i} is invalid: {str(e)}")

    def normalize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """
        Normalize embedding to unit vector (L2 norm).
        
        Args:
            embedding: Embedding vector
            
        Returns:
            Normalized embedding
        """
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm

    def cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            emb1: First embedding
            emb2: Second embedding
            
        Returns:
            Cosine similarity score (-1 to 1)
        """
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))

    def __repr__(self) -> str:
        """String representation of embedder."""
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model}, dim={self.dimension})"
