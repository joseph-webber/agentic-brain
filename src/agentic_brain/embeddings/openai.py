# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
OpenAI Embeddings Implementation

Supports OpenAI's embedding models (text-embedding-3-small, text-embedding-3-large).
Includes rate limiting, retry logic, and batch processing.
"""

import os
import time
import asyncio
from typing import List, Optional
import numpy as np
from datetime import datetime, timedelta
import logging

from .base import Embedder, EmbeddingProvider, EmbeddingResult, BatchEmbeddingResult

logger = logging.getLogger(__name__)


class OpenAIEmbedder(Embedder):
    """
    OpenAI Embeddings Client.

    Models:
    - text-embedding-3-small (1536 dimensions)
    - text-embedding-3-large (3072 dimensions)
    """

    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        rate_limit: int = 3500,  # Requests per minute
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        Initialize OpenAI Embedder.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name to use
            rate_limit: Max requests per minute
            max_retries: Max retry attempts for failed requests
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not provided and not set in environment")

        if model not in self.MODEL_DIMENSIONS:
            raise ValueError(f"Unknown OpenAI model: {model}")

        self._model = model
        self._dimension = self.MODEL_DIMENSIONS[model]
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.min_request_interval = 60.0 / rate_limit
        self.last_request_time = 0.0

        try:
            from openai import OpenAI, AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required. Install with: pip install openai"
            )

        self.client = OpenAI(api_key=self.api_key, timeout=timeout)
        self.async_client = AsyncOpenAI(api_key=self.api_key, timeout=timeout)

    @property
    def provider(self) -> EmbeddingProvider:
        return EmbeddingProvider.OPENAI

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

                response = self.client.embeddings.create(
                    model=self._model,
                    input=text,
                )

                embedding = np.array(response.data[0].embedding, dtype=np.float32)
                latency_ms = (time.time() - start_time) * 1000

                return EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    dimension=self._dimension,
                    provider=self.provider.value,
                    model=self._model,
                    tokens_used=response.usage.total_tokens,
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
        return await self._embed_async_with_retry(text)

    async def _embed_async_with_retry(self, text: str) -> EmbeddingResult:
        """Embed asynchronously with retry logic."""
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                self._apply_rate_limit()

                response = await self.async_client.embeddings.create(
                    model=self._model,
                    input=text,
                )

                embedding = np.array(response.data[0].embedding, dtype=np.float32)
                latency_ms = (time.time() - start_time) * 1000

                return EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    dimension=self._dimension,
                    provider=self.provider.value,
                    model=self._model,
                    tokens_used=response.usage.total_tokens,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Async embedding attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Async embedding failed after {self.max_retries} attempts"
                    )

        raise RuntimeError(
            f"Failed to embed text asynchronously after {self.max_retries} attempts: {last_error}"
        )

    def embed_batch_sync(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> BatchEmbeddingResult:
        """Embed batch of texts synchronously."""
        self.validate_texts(texts)

        results = []
        errors = []
        total_tokens = 0
        start_time = time.time()

        try:
            from tqdm import tqdm

            iterator = tqdm(texts, disable=not show_progress, desc="Embedding texts")
        except ImportError:
            iterator = texts

        for text in iterator:
            try:
                result = self._embed_with_retry(text)
                results.append(result)
                if result.tokens_used:
                    total_tokens += result.tokens_used
            except Exception as e:
                errors.append({"text": text, "error": str(e)})
                logger.error(f"Error embedding text: {e}")

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

    async def embed_batch_async(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
        concurrent_requests: int = 5,
    ) -> BatchEmbeddingResult:
        """Embed batch of texts asynchronously."""
        self.validate_texts(texts)

        results = []
        errors = []
        total_tokens = 0
        start_time = time.time()

        async def process_batch(batch: List[str]) -> None:
            nonlocal total_tokens
            tasks = [self._embed_async_with_retry(text) for text in batch]
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    results.append(result)
                    if result.tokens_used:
                        total_tokens += result.tokens_used
                except Exception as e:
                    errors.append({"text": str(e)})
                    logger.error(f"Error in async batch embedding: {e}")

        semaphore = asyncio.Semaphore(concurrent_requests)

        async def bounded_embed(text: str) -> EmbeddingResult:
            async with semaphore:
                return await self._embed_async_with_retry(text)

        tasks = [bounded_embed(text) for text in texts]

        try:
            from tqdm.asyncio import tqdm

            results_list = await tqdm.gather(*tasks, disable=not show_progress)
        except ImportError:
            results_list = await asyncio.gather(*tasks)

        results = [r for r in results_list if r is not None]
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

    async def close(self) -> None:
        """Close async client."""
        await self.async_client.close()
