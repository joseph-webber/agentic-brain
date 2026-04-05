# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Cohere Embeddings Implementation

Supports Cohere's embedding models (embed-english-v3.0, embed-english-light-v3.0).
Includes rate limiting, multilingual support, and efficient batch processing.
"""

import asyncio
import logging
import os
import time
from typing import List, Literal, Optional

import numpy as np

from .base import BatchEmbeddingResult, Embedder, EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)


class CohereEmbedder(Embedder):
    """
    Cohere Embeddings Client.

    Models:
    - embed-english-v3.0 (1024 dimensions, 512 token window)
    - embed-english-light-v3.0 (384 dimensions, faster)
    - embed-multilingual-v3.0 (1024 dimensions, multilingual)
    """

    MODEL_DIMENSIONS = {
        "embed-english-v3.0": 1024,
        "embed-english-light-v3.0": 384,
        "embed-multilingual-v3.0": 1024,
        "embed-multilingual-light-v3.0": 384,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "embed-english-v3.0",
        input_type: Literal[
            "search_document", "search_query", "classification", "clustering"
        ] = "search_document",
        rate_limit: int = 10000,
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        Initialize Cohere Embedder.

        Args:
            api_key: Cohere API key (defaults to COHERE_API_KEY env var)
            model: Model name to use
            input_type: Type of input (affects embedding optimization)
            rate_limit: Max requests per minute
            max_retries: Max retry attempts
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError("COHERE_API_KEY not provided and not set in environment")

        if model not in self.MODEL_DIMENSIONS:
            raise ValueError(f"Unknown Cohere model: {model}")

        self._model = model
        self._dimension = self.MODEL_DIMENSIONS[model]
        self.input_type = input_type
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.min_request_interval = 60.0 / rate_limit
        self.last_request_time = 0.0

        try:
            import cohere

            self.client = cohere.ClientV2(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "cohere package required. Install with: pip install cohere"
            )

    @property
    def provider(self) -> EmbeddingProvider:
        return EmbeddingProvider.COHERE

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
                    embedding_types=["float"],
                )

                embedding = np.array(response.embeddings.float[0], dtype=np.float32)
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
        batch_size: int = 96,
        show_progress: bool = False,
    ) -> BatchEmbeddingResult:
        """
        Embed batch of texts synchronously.
        Cohere supports batching up to 96 texts per request.
        """
        self.validate_texts(texts)

        results = []
        errors = []
        total_tokens = 0
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
                result = self._embed_batch_with_retry(batch)
                results.extend(result)
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
            total_tokens_used=total_tokens,
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
                    embedding_types=["float"],
                )

                results = []
                latency_ms = (time.time() - start_time) * 1000

                for text, embedding in zip(texts, response.embeddings.float, strict=False):
                    emb_array = np.array(embedding, dtype=np.float32)
                    results.append(
                        EmbeddingResult(
                            text=text,
                            embedding=emb_array,
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
        batch_size: int = 96,
        show_progress: bool = False,
        concurrent_requests: int = 3,
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
        """Close connections (Cohere client doesn't need explicit closing)."""
        pass
