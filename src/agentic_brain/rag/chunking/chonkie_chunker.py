# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Chonkie-powered token-aware chunking for RAG pipelines.

Wraps the Chonkie library (https://github.com/chonkie-inc/chonkie) to provide
**token-accurate** chunking with support for token, sentence, and semantic
strategies.  Unlike the built-in character-based chunkers, Chonkie uses a real
tokenizer so chunk sizes match LLM context windows precisely.

Designed as a drop-in replacement for the built-in chunkers, returning the same
``Chunk`` dataclass used throughout the agentic-brain RAG pipeline.

Usage:
    from agentic_brain.rag.chunking import ChonkieChunker

    # Token-based chunking (fastest)
    chunker = ChonkieChunker(strategy="token", chunk_size=512, overlap=50)
    chunks = chunker.chunk("Your long document text here...")

    # Sentence-based chunking
    chunker = ChonkieChunker(strategy="sentence", chunk_size=1024)
    chunks = chunker.chunk(document_text)

    # Semantic chunking (embedding-aware, best quality)
    chunker = ChonkieChunker(
        strategy="semantic",
        chunk_size=512,
        similarity_threshold=0.5,
        embedding_model="all-minilm-l6-v2",
    )
    chunks = chunker.chunk(document_text)

    # Benchmark against built-in chunkers
    from agentic_brain.rag.chunking import benchmark_chunkers
    results = benchmark_chunkers(sample_text, iterations=10)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .base import BaseChunker, Chunk
from .base import SemanticChunker as BuiltinSemanticChunker
from ..exceptions import ChunkingError

logger = logging.getLogger(__name__)

try:
    import chonkie
    from chonkie import SentenceChunker as _SentenceChunker
    from chonkie import TokenChunker as _TokenChunker

    CHONKIE_AVAILABLE = True
except ImportError:
    CHONKIE_AVAILABLE = False

try:
    from chonkie import SemanticChunker as _SemanticChunker

    CHONKIE_SEMANTIC_AVAILABLE = True
except ImportError:
    CHONKIE_SEMANTIC_AVAILABLE = False

try:
    from chonkie.embeddings import AutoEmbeddings

    CHONKIE_EMBEDDINGS_AVAILABLE = True
except ImportError:
    CHONKIE_EMBEDDINGS_AVAILABLE = False


class ChonkieStrategy(Enum):
    """Chunking strategies available via Chonkie."""

    TOKEN = "token"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"


@dataclass
class BenchmarkResult:
    """Result from a chunking benchmark comparison."""

    chunker_name: str
    strategy: str
    total_time_ms: float
    avg_time_ms: float
    num_chunks: int
    avg_chunk_size: float
    iterations: int
    chars_per_second: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def speedup_over(self) -> Optional[float]:
        """Speedup factor vs baseline (set externally)."""
        return self.metadata.get("speedup")


class ChonkieChunker(BaseChunker):
    """
    Token-aware chunking powered by the Chonkie library.

    Drop-in replacement for built-in chunkers with **accurate token counting**.
    The built-in chunkers use character-based splitting (fast but imprecise);
    Chonkie uses a real tokenizer so chunk sizes align with LLM token limits.
    Supports token, sentence, and semantic chunking strategies.
    Returns standard ``Chunk`` objects compatible with the full RAG pipeline.

    Args:
        strategy: Chunking strategy - "token", "sentence", or "semantic".
        chunk_size: Target chunk size in tokens.
        overlap: Token overlap between adjacent chunks.
        similarity_threshold: Similarity threshold for semantic chunking (0.0-1.0).
        embedding_model: Model name for semantic chunking embeddings.
            Accepts short names like "all-minilm-l6-v2" or full HuggingFace
            paths like "sentence-transformers/all-MiniLM-L6-v2".
        min_chunk_size: Minimum chunk size (tokens) for semantic chunking.
        sentence_delimiters: Custom sentence delimiters for sentence chunking.

    Example:
        >>> chunker = ChonkieChunker(strategy="token", chunk_size=256)
        >>> chunks = chunker.chunk("Hello world. This is a test.")
        >>> len(chunks) >= 1
        True
    """

    DEFAULT_EMBEDDING_MODEL = "all-minilm-l6-v2"

    def __init__(
        self,
        strategy: str | ChonkieStrategy = ChonkieStrategy.TOKEN,
        chunk_size: int = 512,
        overlap: int = 128,
        similarity_threshold: float = 0.5,
        embedding_model: str | None = None,
        min_chunk_size: int = 50,
        sentence_delimiters: list[str] | None = None,
    ) -> None:
        if not CHONKIE_AVAILABLE:
            raise ImportError(
                "chonkie is required for ChonkieChunker. "
                "Install it with: pip install 'agentic-brain[chonkie]'"
            )

        # Convert string to enum
        if isinstance(strategy, str):
            strategy = ChonkieStrategy(strategy.lower())

        # BaseChunker expects char-based sizes; we store token sizes separately
        # and use a rough conversion for the base class (4 chars ≈ 1 token)
        char_chunk_size = chunk_size * 4
        char_overlap = min(overlap * 4, char_chunk_size - 1)
        super().__init__(
            chunk_size=char_chunk_size,
            overlap=char_overlap,
        )

        self.strategy = strategy
        self.token_chunk_size = chunk_size
        self.token_overlap = min(overlap, chunk_size - 1)
        self.similarity_threshold = similarity_threshold
        self.embedding_model_name = embedding_model or self.DEFAULT_EMBEDDING_MODEL
        self.min_chunk_size = min_chunk_size
        self.sentence_delimiters = sentence_delimiters

        self._chunker = self._build_chunker()

    def _build_chunker(self) -> Any:
        """Construct the underlying Chonkie chunker instance."""
        if self.strategy == ChonkieStrategy.TOKEN:
            return _TokenChunker(
                chunk_size=self.token_chunk_size,
                chunk_overlap=self.token_overlap,
            )

        elif self.strategy == ChonkieStrategy.SENTENCE:
            kwargs: dict[str, Any] = {
                "chunk_size": self.token_chunk_size,
                "chunk_overlap": self.token_overlap,
            }
            if self.sentence_delimiters:
                kwargs["delimiters"] = self.sentence_delimiters
            return _SentenceChunker(**kwargs)

        elif self.strategy == ChonkieStrategy.SEMANTIC:
            if not CHONKIE_SEMANTIC_AVAILABLE:
                raise ImportError(
                    "Chonkie semantic chunking requires additional dependencies. "
                    "Install with: pip install 'chonkie[semantic]'"
                )

            # Build embedding model via AutoEmbeddings if available
            embedding_model: Any = self.embedding_model_name
            if CHONKIE_EMBEDDINGS_AVAILABLE:
                try:
                    embedding_model = AutoEmbeddings.get_embeddings(
                        self.embedding_model_name
                    )
                except Exception:
                    logger.warning(
                        "Failed to load Chonkie embeddings for %r, "
                        "passing model name string directly.",
                        self.embedding_model_name,
                    )

            return _SemanticChunker(
                embedding_model=embedding_model,
                chunk_size=self.token_chunk_size,
                similarity_threshold=self.similarity_threshold,
                min_chunk_size=self.min_chunk_size,
            )

        raise ValueError(f"Unsupported Chonkie strategy: {self.strategy}")

    def _convert_chunk(
        self,
        chonkie_chunk: Any,
        index: int,
        source_text: str,
    ) -> Chunk:
        """Convert a Chonkie chunk object to our standard Chunk dataclass."""
        text: str = getattr(chonkie_chunk, "text", str(chonkie_chunk))
        token_count: int = getattr(chonkie_chunk, "token_count", len(text) // 4)

        # Locate the chunk within the source text for accurate char offsets
        start_char = source_text.find(text)
        if start_char < 0:
            start_char = 0
        end_char = start_char + len(text)

        return Chunk(
            content=text,
            start_char=start_char,
            end_char=end_char,
            chunk_index=index,
            metadata={
                "token_count": token_count,
                "chunker": "chonkie",
                "strategy": self.strategy.value,
            },
        )

    def chunk(
        self,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Chunk]:
        """
        Split text into chunks using the configured Chonkie strategy.

        Args:
            text: Text to chunk.
            metadata: Optional metadata to attach to every chunk.

        Returns:
            List of Chunk objects compatible with the RAG pipeline.
        """
        try:
            text = self._prepare_text(text)
        except ChunkingError:
            logger.exception("Chonkie input normalization failed")
            return []

        if not text:
            return []

        try:
            raw_chunks = self._chunker.chunk(text)
        except Exception:
            logger.exception(
                "Chonkie chunking failed (strategy=%s), falling back to built-in.",
                self.strategy.value,
            )
            fallback = BuiltinSemanticChunker(
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )
            return fallback.chunk(text, metadata)

        chunks = [self._convert_chunk(c, idx, text) for idx, c in enumerate(raw_chunks)]

        self._add_metadata(chunks, metadata)
        return self._enforce_max_chunk_size(chunks)

    def chunk_batch(
        self,
        texts: list[str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[list[Chunk]]:
        """
        Chunk multiple texts efficiently.

        Args:
            texts: List of texts to chunk.
            metadata: Optional metadata to attach to every chunk.

        Returns:
            List of chunk lists, one per input text.
        """
        return [self.chunk(t, metadata) for t in texts]

    def __repr__(self) -> str:
        return (
            f"ChonkieChunker(strategy={self.strategy.value!r}, "
            f"chunk_size={self.token_chunk_size}, overlap={self.token_overlap})"
        )


def benchmark_chunkers(
    text: str,
    iterations: int = 10,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[BenchmarkResult]:
    """
    Benchmark Chonkie chunkers against the built-in chunkers.

    Runs each chunker ``iterations`` times on the same text and reports
    timing, throughput, and chunk statistics.

    Args:
        text: Sample text to chunk.
        iterations: Number of iterations per chunker.
        chunk_size: Target chunk size (tokens for Chonkie, chars for built-in).
        overlap: Overlap size.

    Returns:
        List of BenchmarkResult objects sorted by avg_time_ms (fastest first).

    Example:
        >>> sample = "Hello world. " * 1000
        >>> results = benchmark_chunkers(sample, iterations=5)
        >>> results[0].chunker_name  # fastest chunker
        '...'
    """
    text_len = len(text)
    results: list[BenchmarkResult] = []

    # --- Built-in SemanticChunker ---
    builtin = BuiltinSemanticChunker(chunk_size=chunk_size, overlap=overlap)
    timings: list[float] = []
    num_chunks = 0

    for _ in range(iterations):
        start = time.perf_counter()
        chunks = builtin.chunk(text)
        elapsed = (time.perf_counter() - start) * 1000
        timings.append(elapsed)
        num_chunks = len(chunks)

    total_ms = sum(timings)
    avg_ms = total_ms / iterations
    avg_chunk_sz = text_len / max(num_chunks, 1)

    baseline_avg_ms = avg_ms

    results.append(
        BenchmarkResult(
            chunker_name="BuiltinSemanticChunker",
            strategy="semantic",
            total_time_ms=total_ms,
            avg_time_ms=avg_ms,
            num_chunks=num_chunks,
            avg_chunk_size=avg_chunk_sz,
            iterations=iterations,
            chars_per_second=text_len / (avg_ms / 1000) if avg_ms > 0 else 0,
            metadata={"speedup": 1.0},
        )
    )

    # --- Chonkie chunkers ---
    if not CHONKIE_AVAILABLE:
        logger.warning(
            "chonkie not installed — skipping Chonkie benchmarks. "
            "Install with: pip install chonkie"
        )
        return results

    chonkie_strategies = [
        ("token", ChonkieStrategy.TOKEN),
        ("sentence", ChonkieStrategy.SENTENCE),
    ]

    if CHONKIE_SEMANTIC_AVAILABLE:
        chonkie_strategies.append(("semantic", ChonkieStrategy.SEMANTIC))

    for name, strategy in chonkie_strategies:
        try:
            chunker = ChonkieChunker(
                strategy=strategy,
                chunk_size=chunk_size,
                overlap=min(overlap, chunk_size // 4),
            )
        except Exception:
            logger.warning("Could not create ChonkieChunker(%s), skipping.", name)
            continue

        timings = []
        num_chunks = 0

        for _ in range(iterations):
            start = time.perf_counter()
            chunks = chunker.chunk(text)
            elapsed = (time.perf_counter() - start) * 1000
            timings.append(elapsed)
            num_chunks = len(chunks)

        total_ms = sum(timings)
        avg_ms = total_ms / iterations
        avg_chunk_sz = text_len / max(num_chunks, 1)
        speedup = baseline_avg_ms / avg_ms if avg_ms > 0 else float("inf")

        results.append(
            BenchmarkResult(
                chunker_name=f"ChonkieChunker({name})",
                strategy=name,
                total_time_ms=total_ms,
                avg_time_ms=avg_ms,
                num_chunks=num_chunks,
                avg_chunk_size=avg_chunk_sz,
                iterations=iterations,
                chars_per_second=text_len / (avg_ms / 1000) if avg_ms > 0 else 0,
                metadata={"speedup": round(speedup, 2)},
            )
        )

    results.sort(key=lambda r: r.avg_time_ms)
    return results
