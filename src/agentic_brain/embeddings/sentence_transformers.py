# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Sentence Transformers Embeddings Implementation

Local embedding models using Hugging Face sentence-transformers.
Supports CPU, GPU (CUDA), and Apple Silicon (MPS) acceleration.
No API keys required - fully offline capable.
"""

import time
import asyncio
from typing import List, Optional
import numpy as np
import logging
import os

from .base import Embedder, EmbeddingProvider, EmbeddingResult, BatchEmbeddingResult

logger = logging.getLogger(__name__)


class SentenceTransformersEmbedder(Embedder):
    """
    Local Embeddings using Sentence Transformers.
    
    Supports models from Hugging Face:
    - all-MiniLM-L6-v2 (384 dimensions, fast, multilingual)
    - all-mpnet-base-v2 (768 dimensions, high quality)
    - paraphrase-MiniLM-L6-v2 (384 dimensions, paraphrasing)
    - multilingual-e5-small (384 dimensions, multilingual)
    - multilingual-e5-base (768 dimensions, multilingual)
    """

    MODEL_DIMENSIONS = {
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "paraphrase-MiniLM-L6-v2": 384,
        "paraphrase-multilingual-MiniLM-L12-v2": 384,
        "multilingual-e5-small": 384,
        "multilingual-e5-base": 768,
        "multilingual-e5-large": 1024,
        "text2vec-base-chinese": 768,
        "intfloat/e5-small": 384,
        "intfloat/e5-base": 768,
        "intfloat/e5-large": 1024,
    }

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        batch_size: int = 32,
        show_progress: bool = True,
        normalize_embeddings: bool = True,
        cache_folder: Optional[str] = None,
    ):
        """
        Initialize Sentence Transformers Embedder.
        
        Args:
            model: Model name from Hugging Face
            device: Device to use ('cpu', 'cuda', 'mps', or None for auto-detect)
            batch_size: Batch size for inference
            show_progress: Show progress bar during inference
            normalize_embeddings: Whether to normalize embeddings to unit vectors
            cache_folder: Folder to cache downloaded models
        """
        if model not in self.MODEL_DIMENSIONS:
            logger.warning(
                f"Model {model} not in known dimensions. "
                "Dimensions will be inferred from model."
            )

        self._model = model
        self.batch_size = batch_size
        self.show_progress = show_progress
        self.normalize_embeddings = normalize_embeddings
        self.cache_folder = cache_folder

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers package required. "
                "Install with: pip install sentence-transformers"
            )

        self.device = device or self._detect_device()
        logger.info(f"Loading model {model} on device {self.device}")

        kwargs = {}
        if cache_folder:
            kwargs["cache_folder"] = cache_folder

        self.model = SentenceTransformer(model, device=self.device, **kwargs)

        if model in self.MODEL_DIMENSIONS:
            self._dimension = self.MODEL_DIMENSIONS[model]
        else:
            self._dimension = self.model.get_sentence_embedding_dimension()

    def _detect_device(self) -> str:
        """Auto-detect best device for embeddings."""
        try:
            import torch

            if torch.backends.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass

        return "cpu"

    @property
    def provider(self) -> EmbeddingProvider:
        return EmbeddingProvider.SENTENCE_TRANSFORMERS

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_sync(self, text: str) -> EmbeddingResult:
        """Embed a single text synchronously."""
        self.validate_text(text)
        start_time = time.time()

        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )

        if not isinstance(embedding, np.ndarray):
            embedding = np.array(embedding, dtype=np.float32)

        latency_ms = (time.time() - start_time) * 1000

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            dimension=self._dimension,
            provider=self.provider.value,
            model=self._model,
            tokens_used=None,
            latency_ms=latency_ms,
        )

    async def embed_async(self, text: str) -> EmbeddingResult:
        """Embed a single text asynchronously."""
        self.validate_text(text)
        return await asyncio.to_thread(self.embed_sync, text)

    def embed_batch_sync(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> BatchEmbeddingResult:
        """Embed batch of texts synchronously."""
        self.validate_texts(texts)
        start_time = time.time()

        results = []
        errors = []

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size or self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=show_progress or self.show_progress,
            )

            if not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings, dtype=np.float32)

            latency_per_text = ((time.time() - start_time) * 1000) / len(texts)

            for text, embedding in zip(texts, embeddings):
                results.append(
                    EmbeddingResult(
                        text=text,
                        embedding=embedding,
                        dimension=self._dimension,
                        provider=self.provider.value,
                        model=self._model,
                        tokens_used=None,
                        latency_ms=latency_per_text,
                    )
                )

        except Exception as e:
            errors.append({"error": str(e), "texts_count": len(texts)})
            logger.error(f"Batch embedding error: {e}")

        total_latency = (time.time() - start_time) * 1000

        return BatchEmbeddingResult(
            results=results,
            total_texts=len(texts),
            successful=len(results),
            failed=len(errors),
            total_tokens_used=0,
            total_latency_ms=total_latency,
            errors=errors,
        )

    async def embed_batch_async(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
        concurrent_requests: int = 1,
    ) -> BatchEmbeddingResult:
        """
        Embed batch of texts asynchronously.
        Note: SentenceTransformers is not async-native, so this runs in thread pool.
        """
        self.validate_texts(texts)
        return await asyncio.to_thread(
            self.embed_batch_sync, texts, batch_size, show_progress
        )

    async def close(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self.model, 'model'):
                if hasattr(self.model.model, 'to'):
                    self.model.model.to('cpu')
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


class E5Embedder(SentenceTransformersEmbedder):
    """Specialized embedder for multilingual E5 models."""

    def __init__(
        self,
        model: str = "intfloat/e5-small",
        device: Optional[str] = None,
        batch_size: int = 32,
        **kwargs
    ):
        """
        Initialize E5 Embedder.
        
        Args:
            model: E5 model variant (small, base, large)
            device: Device to use
            batch_size: Batch size for inference
        """
        super().__init__(
            model=model,
            device=device,
            batch_size=batch_size,
            normalize_embeddings=True,
            **kwargs
        )

    def embed_sync(self, text: str, task_type: str = "passage") -> EmbeddingResult:
        """
        Embed text with E5 model.
        
        Args:
            text: Text to embed
            task_type: Task context ('query' or 'passage')
        """
        self.validate_text(text)

        prefixed_text = f"query: {text}" if task_type == "query" else f"passage: {text}"
        start_time = time.time()

        embedding = self.model.encode(
            prefixed_text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        latency_ms = (time.time() - start_time) * 1000

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            dimension=self._dimension,
            provider=self.provider.value,
            model=self._model,
            tokens_used=None,
            latency_ms=latency_ms,
        )

    def embed_batch_sync(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
        task_type: str = "passage",
    ) -> BatchEmbeddingResult:
        """
        Embed batch with E5 model.
        
        Args:
            texts: Texts to embed
            batch_size: Batch size
            show_progress: Show progress bar
            task_type: Task context ('query' or 'passage')
        """
        self.validate_texts(texts)
        start_time = time.time()

        results = []
        errors = []

        try:
            prefixed_texts = [
                f"query: {t}" if task_type == "query" else f"passage: {t}"
                for t in texts
            ]

            embeddings = self.model.encode(
                prefixed_texts,
                batch_size=batch_size or self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=show_progress or self.show_progress,
            )

            latency_per_text = ((time.time() - start_time) * 1000) / len(texts)

            for text, embedding in zip(texts, embeddings):
                results.append(
                    EmbeddingResult(
                        text=text,
                        embedding=embedding,
                        dimension=self._dimension,
                        provider=self.provider.value,
                        model=self._model,
                        tokens_used=None,
                        latency_ms=latency_per_text,
                    )
                )

        except Exception as e:
            errors.append({"error": str(e)})
            logger.error(f"E5 batch embedding error: {e}")

        total_latency = (time.time() - start_time) * 1000

        return BatchEmbeddingResult(
            results=results,
            total_texts=len(texts),
            successful=len(results),
            failed=len(errors),
            total_tokens_used=0,
            total_latency_ms=total_latency,
            errors=errors,
        )
