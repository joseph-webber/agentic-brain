# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
GraphRAG embedding helper.

Provides a lazy singleton wrapper that prefers MLX-backed embeddings on Apple
Silicon and falls back to sentence-transformers using the same 384-dimension
all-MiniLM-L6-v2 model.

Example:
    >>> from agentic_brain.rag.mlx_embeddings import MLXEmbeddings
    >>> vec = MLXEmbeddings.embed("Hello world")
    >>> len(vec)
    384
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

from .embeddings import get_best_device

if TYPE_CHECKING:
    from .embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_DIMENSIONS = 384


class MLXEmbeddings:
    """Lazy-loaded real embeddings for GraphRAG."""

    _provider: ClassVar[Optional["EmbeddingProvider"]] = None
    _available: ClassVar[Optional[bool]] = None
    _provider_name: ClassVar[str] = "uninitialized"

    @classmethod
    def get_model(cls) -> "EmbeddingProvider":
        """Return the cached embedding provider, loading on first call."""
        if cls._provider is None:
            try:
                from .embeddings import MLXEmbeddings as NativeMLXEmbeddings

                cls._provider = NativeMLXEmbeddings(model=_MODEL_NAME)
                cls._available = True
                cls._provider_name = cls._provider.model_name
                logger.info(
                    "Loaded GraphRAG embeddings via %s (%d dims)",
                    cls._provider_name,
                    cls._provider.dimensions,
                )
            except Exception as mlx_exc:
                logger.info(
                    "MLX embeddings unavailable, falling back to sentence-transformers: %s",
                    mlx_exc,
                )
                try:
                    import sentence_transformers  # noqa: F401

                    from .embeddings import SentenceTransformerEmbeddings

                    device = "mps" if get_best_device() in {"mlx", "mps"} else "cpu"
                    cls._provider = SentenceTransformerEmbeddings(
                        model=_MODEL_NAME,
                        device=device,
                    )
                    cls._available = True
                    cls._provider_name = cls._provider.model_name
                    logger.info(
                        "Loaded GraphRAG embeddings via %s (%d dims)",
                        cls._provider_name,
                        cls._provider.dimensions,
                    )
                except Exception as exc:
                    cls._available = False
                    cls._provider = None
                    cls._provider_name = "unavailable"
                    logger.warning(
                        "Real embedding providers unavailable, using deterministic fallback: %s",
                        exc,
                    )
                    raise RuntimeError("No real embedding provider available") from exc

        return cls._provider

    @classmethod
    def provider_name(cls) -> str:
        """Return the active provider name, loading it if needed."""
        if cls._provider_name == "uninitialized":
            try:
                cls.get_model()
            except Exception:
                pass
        return cls._provider_name

    @classmethod
    def is_available(cls) -> bool:
        """Check whether a real embedding provider can be loaded."""
        if cls._available is not None:
            return cls._available
        try:
            cls.get_model()
            return True
        except Exception:
            return False

    @classmethod
    def embed(cls, text: str) -> list[float]:
        """Embed a single text string into a 384-dim vector."""
        provider = cls.get_model()
        embedding = provider.embed(text)
        return list(embedding)

    @classmethod
    def embed_batch(cls, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in one batch (much faster than looping)."""
        provider = cls.get_model()
        embeddings = provider.embed_batch(texts)
        return [list(embedding) for embedding in embeddings]

    @classmethod
    def dimensions(cls) -> int:
        """Return the embedding dimension used by GraphRAG."""
        if cls.is_available():
            try:
                return cls.get_model().dimensions
            except Exception:
                pass
        return _DIMENSIONS

    @classmethod
    def reset(cls) -> None:
        """Clear cached provider state (used by tests)."""
        cls._provider = None
        cls._available = None
        cls._provider_name = "uninitialized"
