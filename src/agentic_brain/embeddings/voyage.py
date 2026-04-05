# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Voyage AI Embeddings Implementation

Supports Voyage AI's embedding models with advanced retrieval capabilities.
Optimized for semantic search and ranking.
"""

import asyncio
import logging
import os
import time
from typing import List, Literal, Optional

import numpy as np

from .base import BatchEmbeddingResult, Embedder, EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)


class VoyageEmbedder(Embedder):
    """
    Voyage AI Embeddings Client.

    Models:
    - voyage-2 (1024 dimensions)
    - voyage-large-2 (1536 dimensions, higher quality)
    - voyage-law-2 (1024 dimensions, legal domain)
    - voyage-finance-2 (1024 dimensions, financial domain)
    """

    MODEL_DIMENSIONS = {
        "voyage-2": 1024,
        "voyage-large-2": 1536,
        "voyage-law-2": 1024,
        "voyage-finance-2": 1024,
        "voyage-multilingual-2": 1024,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "voyage-2",
        input_type: Literal["document", "query"] = "document",
        rate_limit: int = 5000,
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        Initialize Voyage AI Embedder.

        Args:
            api_key: Voyage API key (defaults to VOYAGE_API_KEY env var)
            model: Model name to use
            input_type: Type of input for optimization
            rate_limit: Max requests per minute
            max_retries: Max retry attempts
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("VOYAGE_API_KEY")
        if not self.api_key:
            raise ValueError("VOYAGE_API_KEY not provided and not set in environment")

        if model not in self.MODEL_DIMENSIONS:
            raise ValueError(f"Unknown Voyage model: {model}")

        self._model = model
        self._dimension = self.MODEL_DIMENSIONS[model]
        self.input_type = input_type
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.min_request_interval = 60.0 / rate_limit
        self.last_request_time = 0.0

        try:
            import voyageai

            self.client = voyageai.Client(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "voyageai package required. Install with: pip install voyageai"
            )

    @property
    def provider(self) -> EmbeddingProvider:
        return EmbeddingProvider.VOYAGE

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def embed_sync(self, text: str) -> EmbeddingResult:
        """Embed a single text synchronously."""
        self.validate_text(text)
        return self._embed_with_retry(text)

    def _embed_with_retry(self, text: str) -> EmbeddingResult:
        """Embed with retry logic and rate limiting."""
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                self._apply_rate_limit()

                response = self.client.embed(
                    texts=[text],
                    model=self._model,
                    input_type=self.input_type,
                )

                embedding = np.array(response.embeddings[0], dtype=np.float32)
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

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Embedding attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Embedding failed after {self.max_retries} attempts")

        raise RuntimeError(
            f"Failed to embed text after {self.max_retries} attempts: {last_error}"
        )

    async def embed_async(self, text: str) -> EmbeddingResult:
        """Embed a single text asynchronously."""
        self.validate_text(text)
        return await asyncio.to_thread(self._embed_with_retry, text)

    def embed_batch_sync(
        self,
        texts: List[str],
        batch_size: int = 128,
        show_progress: bool = False,
    ) -> BatchEmbeddingResult:
        """
        Embed batch of texts synchronously.
        Voyage AI supports batches up to 128 texts.
        """
        self.validate_texts(texts)

        results = []
        errors = []
        start_time = time.time()

        try:
            from tqdm import tqdm

            batches = [
                texts[i : i + batch_size] for i in range(0, len(texts), batch_size)
            ]
            iterator = tqdm(
                batches, disable=not show_progress, desc="Embedding batches"
            )
        except ImportError:
            batches = [
                texts[i : i + batch_size] for i in range(0, len(texts), batch_size)
            ]
            iterator = batches

        for batch in iterator:
            try:
                batch_results = self._embed_batch_with_retry(batch)
                results.extend(batch_results)
            except Exception as e:
                for text in batch:
                    errors.append({"text": text, "error": str(e)})
                logger.error(f"Error embedding batch: {e}")

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

    def _embed_batch_with_retry(self, texts: List[str]) -> List[EmbeddingResult]:
        """Embed a batch with retry logic."""
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                self._apply_rate_limit()

                response = self.client.embed(
                    texts=texts,
                    model=self._model,
                    input_type=self.input_type,
                )

                results = []
                latency_ms = (time.time() - start_time) * 1000

                for text, embedding_list in zip(texts, response.embeddings, strict=False):
                    embedding = np.array(embedding_list, dtype=np.float32)
                    results.append(
                        EmbeddingResult(
                            text=text,
                            embedding=embedding,
                            dimension=self._dimension,
                            provider=self.provider.value,
                            model=self._model,
                            tokens_used=None,
                            latency_ms=latency_ms / len(texts),
                        )
                    )

                return results

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(f"Batch embedding attempt {attempt + 1} failed: {e}")
                    time.sleep(wait_time)

        raise RuntimeError(f"Batch embedding failed: {last_error}")

    async def embed_batch_async(
        self,
        texts: List[str],
        batch_size: int = 128,
        show_progress: bool = False,
        concurrent_requests: int = 2,
    ) -> BatchEmbeddingResult:
        """Embed batch of texts asynchronously."""
        self.validate_texts(texts)

        results = []
        errors = []
        semaphore = asyncio.Semaphore(concurrent_requests)
        start_time = time.time()

        async def process_batch(batch: List[str]) -> List[EmbeddingResult]:
            async with semaphore:
                return await asyncio.to_thread(self._embed_batch_with_retry, batch)

        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]

        try:
            from tqdm.asyncio import tqdm

            batch_results = await tqdm.gather(
                *[process_batch(b) for b in batches], disable=not show_progress
            )
        except ImportError:
            batch_results = await asyncio.gather(*[process_batch(b) for b in batches])

        for batch_result in batch_results:
            if batch_result:
                results.extend(batch_result)

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

    async def close(self) -> None:
        """Close connections."""
        pass
