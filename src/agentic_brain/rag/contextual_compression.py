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
Contextual Compression - Extract Relevant Content from Chunks

Compresses retrieved documents by extracting only the parts
relevant to the query, reducing noise in LLM context.

Benefits:
- Fits more relevant content in context window
- Reduces LLM processing time and cost
- Improves answer quality by removing distractions
- Enables larger retrieval (top_k=20) with compression

Example:
    Original chunk (500 tokens):
    "The company was founded in 1985. It started as a small
     bakery. The deployment process requires running scripts.
     First, ensure all tests pass. Then push to staging..."

    Query: "How do I deploy?"

    Compressed (100 tokens):
    "The deployment process requires running scripts.
     First, ensure all tests pass. Then push to staging..."

Strategies:
- LLM-based extraction (most accurate, slower)
- Sentence scoring (fast, good quality)
- Keyword extraction (fastest, less accurate)
- Hybrid approaches
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """Available compression strategies."""

    LLM = "llm"  # Use LLM to extract relevant parts
    SENTENCE = "sentence"  # Score sentences by relevance
    KEYWORD = "keyword"  # Extract around keywords
    EXTRACTIVE = "extractive"  # Top-k sentences by similarity
    HYBRID = "hybrid"  # Combine multiple strategies


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation."""

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...


class LLMClient(Protocol):
    """Protocol for LLM used in compression."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt."""
        ...


@dataclass
class CompressedChunk:
    """A chunk after compression."""

    original_content: str
    compressed_content: str
    compression_ratio: float  # compressed_size / original_size
    relevance_score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_saved(self) -> int:
        """Estimate tokens saved (rough: 4 chars = 1 token)."""
        original_tokens = len(self.original_content) // 4
        compressed_tokens = len(self.compressed_content) // 4
        return original_tokens - compressed_tokens


@dataclass
class CompressionResult:
    """Result of compressing multiple chunks."""

    query: str
    original_chunks: list[str]
    compressed_chunks: list[CompressedChunk]
    total_compression_ratio: float
    total_tokens_saved: int

    def as_context(self, max_chunks: int | None = None) -> str:
        """Format compressed chunks as context string."""
        chunks = (
            self.compressed_chunks[:max_chunks]
            if max_chunks
            else self.compressed_chunks
        )
        return "\n\n---\n\n".join(c.compressed_content for c in chunks)


class ContextualCompressor:
    """
    Compress retrieved documents to extract relevant content.

    Implements multiple compression strategies:
    - LLM-based: Most accurate, uses LLM to extract relevant parts
    - Sentence scoring: Fast, scores sentences by query similarity
    - Keyword extraction: Fastest, extracts around query terms

    Example:
        compressor = ContextualCompressor(llm=my_llm)
        result = compressor.compress(
            query="deployment process",
            chunks=retrieved_documents,
            strategy=CompressionStrategy.LLM
        )
        print(f"Saved {result.total_tokens_saved} tokens")
        context = result.as_context()
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        embeddings: EmbeddingProvider | None = None,
        target_ratio: float = 0.3,  # Target 30% of original size
        min_chunk_size: int = 50,  # Don't compress below this
    ):
        """
        Initialize contextual compressor.

        Args:
            llm: LLM client for LLM-based compression
            embeddings: Embedding provider for semantic compression
            target_ratio: Target compression ratio (lower = more compression)
            min_chunk_size: Minimum size for compressed chunks
        """
        self.llm = llm
        self.embeddings = embeddings
        self.target_ratio = target_ratio
        self.min_chunk_size = min_chunk_size

    def compress(
        self,
        query: str,
        chunks: list[str | dict[str, Any]],
        strategy: CompressionStrategy = CompressionStrategy.SENTENCE,
    ) -> CompressionResult:
        """
        Compress chunks using specified strategy.

        Args:
            query: The search query for context
            chunks: Documents to compress (strings or dicts with 'content')
            strategy: Compression strategy to use

        Returns:
            CompressionResult with compressed chunks
        """
        # Normalize input
        normalized: list[str] = []
        for chunk in chunks:
            if isinstance(chunk, dict):
                content = (
                    chunk.get("content")
                    or chunk.get("text")
                    or chunk.get("page_content")
                )
                normalized.append(str(content) if content else str(chunk))
            else:
                normalized.append(str(chunk))

        compressed: list[CompressedChunk] = []

        for original in normalized:
            if len(original) < self.min_chunk_size:
                # Too small to compress
                compressed.append(
                    CompressedChunk(
                        original_content=original,
                        compressed_content=original,
                        compression_ratio=1.0,
                        relevance_score=0.5,
                    )
                )
                continue

            # Apply compression strategy
            if strategy == CompressionStrategy.LLM:
                comp = self._compress_llm(query, original)
            elif strategy == CompressionStrategy.SENTENCE:
                comp = self._compress_sentence(query, original)
            elif strategy == CompressionStrategy.KEYWORD:
                comp = self._compress_keyword(query, original)
            elif strategy == CompressionStrategy.EXTRACTIVE:
                comp = self._compress_extractive(query, original)
            else:  # HYBRID
                comp = self._compress_hybrid(query, original)

            compressed.append(comp)

        # Calculate totals
        total_original = sum(len(c.original_content) for c in compressed)
        total_compressed = sum(len(c.compressed_content) for c in compressed)
        total_ratio = total_compressed / total_original if total_original > 0 else 1.0
        total_saved = sum(c.tokens_saved for c in compressed)

        return CompressionResult(
            query=query,
            original_chunks=normalized,
            compressed_chunks=compressed,
            total_compression_ratio=total_ratio,
            total_tokens_saved=total_saved,
        )

    def _compress_llm(self, query: str, content: str) -> CompressedChunk:
        """Use LLM to extract relevant parts."""
        if not self.llm:
            return self._compress_sentence(query, content)

        target_size = int(len(content) * self.target_ratio)

        prompt = f"""Extract ONLY the parts of this text that are relevant to the query.
Keep the exact wording - do not paraphrase.
Target length: ~{target_size} characters.

Query: {query}

Text:
{content}

Relevant extract:"""

        try:
            compressed = self.llm.generate(prompt, max_tokens=target_size // 3)
            compressed = compressed.strip()

            # Ensure we got something useful
            if len(compressed) < self.min_chunk_size:
                return self._compress_sentence(query, content)

            return CompressedChunk(
                original_content=content,
                compressed_content=compressed,
                compression_ratio=len(compressed) / len(content),
                relevance_score=0.9,  # LLM extraction is high quality
                metadata={"strategy": "llm"},
            )

        except Exception as e:
            logger.warning(f"LLM compression failed: {e}, falling back to sentence")
            return self._compress_sentence(query, content)

    def _compress_sentence(self, query: str, content: str) -> CompressedChunk:
        """Score and select relevant sentences."""
        # Split into sentences
        sentences = self._split_sentences(content)

        if len(sentences) <= 2:
            # Too few sentences to compress
            return CompressedChunk(
                original_content=content,
                compressed_content=content,
                compression_ratio=1.0,
                relevance_score=0.5,
            )

        # Score sentences by query word overlap
        query_words = set(query.lower().split())
        scored: list[tuple[float, str]] = []

        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            # Jaccard-like overlap
            overlap = len(query_words & sentence_words)
            score = overlap / (len(query_words) + 1)  # +1 to avoid div by zero

            # Boost if contains exact query phrases
            if query.lower() in sentence.lower():
                score += 0.5

            scored.append((score, sentence))

        # Sort by score and take top sentences to hit target ratio
        scored.sort(key=lambda x: x[0], reverse=True)

        target_chars = int(len(content) * self.target_ratio)
        selected: list[str] = []
        current_chars = 0

        for _score, sentence in scored:
            if current_chars >= target_chars:
                break
            selected.append(sentence)
            current_chars += len(sentence)

        # Reorder by original position for readability
        sentence_order = {s: i for i, s in enumerate(sentences)}
        selected.sort(key=lambda s: sentence_order.get(s, 0))

        compressed = " ".join(selected)

        return CompressedChunk(
            original_content=content,
            compressed_content=compressed,
            compression_ratio=len(compressed) / len(content),
            relevance_score=scored[0][0] if scored else 0.5,
            metadata={"strategy": "sentence", "sentences_kept": len(selected)},
        )

    def _compress_keyword(self, query: str, content: str) -> CompressedChunk:
        """Extract content around query keywords."""
        query_words = [w.lower() for w in query.split() if len(w) > 2]

        if not query_words:
            return CompressedChunk(
                original_content=content,
                compressed_content=content[: int(len(content) * self.target_ratio)],
                compression_ratio=self.target_ratio,
                relevance_score=0.3,
            )

        # Find windows around keywords
        content_lower = content.lower()
        window_size = 200  # Characters around each keyword

        windows: list[tuple[int, int]] = []
        for word in query_words:
            start = 0
            while True:
                pos = content_lower.find(word, start)
                if pos == -1:
                    break
                window_start = max(0, pos - window_size // 2)
                window_end = min(len(content), pos + len(word) + window_size // 2)
                windows.append((window_start, window_end))
                start = pos + 1

        if not windows:
            # No keywords found - return start of content
            return CompressedChunk(
                original_content=content,
                compressed_content=content[: int(len(content) * self.target_ratio)],
                compression_ratio=self.target_ratio,
                relevance_score=0.2,
                metadata={"strategy": "keyword", "keywords_found": 0},
            )

        # Merge overlapping windows
        windows.sort()
        merged: list[tuple[int, int]] = [windows[0]]
        for start, end in windows[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        # Extract and join windows
        extracts = [content[s:e] for s, e in merged]
        compressed = " ... ".join(extracts)

        return CompressedChunk(
            original_content=content,
            compressed_content=compressed,
            compression_ratio=len(compressed) / len(content),
            relevance_score=0.6,
            metadata={"strategy": "keyword", "keywords_found": len(windows)},
        )

    def _compress_extractive(self, query: str, content: str) -> CompressedChunk:
        """Use embeddings for semantic sentence extraction."""
        if not self.embeddings:
            return self._compress_sentence(query, content)

        sentences = self._split_sentences(content)

        if len(sentences) <= 2:
            return CompressedChunk(
                original_content=content,
                compressed_content=content,
                compression_ratio=1.0,
                relevance_score=0.5,
            )

        try:
            # Embed query and sentences
            query_emb = self.embeddings.embed(query)
            sentence_embs = self.embeddings.embed_batch(sentences)

            # Score by cosine similarity
            scored: list[tuple[float, str]] = []
            for sentence, emb in zip(sentences, sentence_embs, strict=False):
                sim = self._cosine_similarity(query_emb, emb)
                scored.append((sim, sentence))

            # Select top sentences
            scored.sort(key=lambda x: x[0], reverse=True)

            target_chars = int(len(content) * self.target_ratio)
            selected: list[str] = []
            current_chars = 0

            for _score, sentence in scored:
                if current_chars >= target_chars:
                    break
                selected.append(sentence)
                current_chars += len(sentence)

            # Reorder
            sentence_order = {s: i for i, s in enumerate(sentences)}
            selected.sort(key=lambda s: sentence_order.get(s, 0))

            compressed = " ".join(selected)

            return CompressedChunk(
                original_content=content,
                compressed_content=compressed,
                compression_ratio=len(compressed) / len(content),
                relevance_score=scored[0][0] if scored else 0.5,
                metadata={"strategy": "extractive", "sentences_kept": len(selected)},
            )

        except Exception as e:
            logger.warning(f"Extractive compression failed: {e}")
            return self._compress_sentence(query, content)

    def _compress_hybrid(self, query: str, content: str) -> CompressedChunk:
        """Combine multiple strategies for best results."""
        # Get results from multiple strategies
        sentence_result = self._compress_sentence(query, content)
        keyword_result = self._compress_keyword(query, content)

        # Use extractive if embeddings available
        if self.embeddings:
            extractive_result = self._compress_extractive(query, content)
            candidates = [sentence_result, keyword_result, extractive_result]
        else:
            candidates = [sentence_result, keyword_result]

        # Pick best by relevance score while respecting size targets
        best = max(candidates, key=lambda c: c.relevance_score)

        return CompressedChunk(
            original_content=best.original_content,
            compressed_content=best.compressed_content,
            compression_ratio=best.compression_ratio,
            relevance_score=best.relevance_score,
            metadata={"strategy": "hybrid", **best.metadata},
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting - handles common cases
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))


class ChainedCompressor:
    """
    Chain multiple compression stages for progressive refinement.

    Example:
        compressor = ChainedCompressor([
            ContextualCompressor(target_ratio=0.5),  # First pass: 50%
            ContextualCompressor(llm=my_llm, target_ratio=0.6),  # LLM refine
        ])
        result = compressor.compress(query, chunks)
    """

    def __init__(self, compressors: list[ContextualCompressor]):
        self.compressors = compressors

    def compress(
        self,
        query: str,
        chunks: list[str],
        strategies: list[CompressionStrategy] | None = None,
    ) -> CompressionResult:
        """Run chunks through compression chain."""
        if strategies is None:
            strategies = [CompressionStrategy.SENTENCE] * len(self.compressors)

        current_chunks: list[str | dict[str, Any]] = list(chunks)

        for compressor, strategy in zip(self.compressors, strategies, strict=False):
            result = compressor.compress(query, current_chunks, strategy)
            current_chunks = [c.compressed_content for c in result.compressed_chunks]

        # Calculate overall metrics
        total_original = sum(len(c) for c in chunks)
        total_final = sum(len(c) for c in current_chunks)

        return CompressionResult(
            query=query,
            original_chunks=chunks,
            compressed_chunks=[
                CompressedChunk(
                    original_content=orig,
                    compressed_content=cast(str, comp),
                    compression_ratio=len(comp) / len(orig) if orig else 1.0,
                    relevance_score=0.7,
                )
                for orig, comp in zip(chunks, current_chunks, strict=False)
            ],
            total_compression_ratio=(
                total_final / total_original if total_original else 1.0
            ),
            total_tokens_saved=(total_original - total_final) // 4,
        )
