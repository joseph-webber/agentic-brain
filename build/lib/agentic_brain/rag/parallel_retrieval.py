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
Parallel Retrieval - Search Multiple Sources Concurrently

Executes retrieval across multiple sources (Neo4j, vectors, APIs)
in parallel, then merges and ranks results.

Features:
- Concurrent search across heterogeneous sources
- Intelligent result merging with deduplication
- Source-aware ranking and weighting
- Timeout handling per source
- Graceful degradation on source failures

Example:
    from agentic_brain.rag import ParallelRetriever

    retriever = ParallelRetriever([
        Neo4jRetriever(uri="bolt://localhost:7687"),
        VectorRetriever(collection="docs"),
        APIRetriever(base_url="https://api.example.com"),
    ])

    results = retriever.retrieve("deployment process", top_k=10)
    # Returns merged, ranked results from all sources
"""

import asyncio
import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

from ..exceptions import RetrieverError

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Types of retrieval sources."""

    VECTOR = "vector"  # Vector similarity search
    GRAPH = "graph"  # Neo4j/graph traversal
    KEYWORD = "keyword"  # BM25/keyword search
    API = "api"  # External API
    DATABASE = "database"  # SQL/NoSQL
    HYBRID = "hybrid"  # Combined approaches


@dataclass
class RetrievalSource:
    """Configuration for a retrieval source."""

    name: str
    source_type: SourceType
    retriever: Any  # The actual retriever instance
    weight: float = 1.0  # Weight for ranking (higher = more trusted)
    timeout: float = 10.0  # Timeout in seconds
    enabled: bool = True
    fallback_on_error: bool = True


@dataclass
class ParallelResult:
    """A single result from parallel retrieval."""

    content: str
    source_name: str
    source_type: SourceType
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieval_time_ms: float = 0.0

    def content_hash(self) -> str:
        """Hash for deduplication."""
        return hashlib.md5(self.content.encode()).hexdigest()[:16]


@dataclass
class ParallelRetrievalResult:
    """Aggregated results from parallel retrieval."""

    query: str
    results: list[ParallelResult]
    total_time_ms: float
    source_stats: dict[str, dict[str, Any]]  # Per-source statistics
    errors: list[str] = field(default_factory=list)

    def top_k(self, k: int) -> list[ParallelResult]:
        """Get top k results by score."""
        return sorted(self.results, key=lambda r: r.score, reverse=True)[:k]

    def by_source(self, source_name: str) -> list[ParallelResult]:
        """Get results from specific source."""
        return [r for r in self.results if r.source_name == source_name]


class RetrieverProtocol(Protocol):
    """Protocol that retriever sources must implement."""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve documents matching query."""
        ...


class ParallelRetriever:
    """
    Execute retrieval across multiple sources in parallel.

    Supports:
    - Heterogeneous sources (vector, graph, API, database)
    - Concurrent execution with timeouts
    - Result merging and deduplication
    - Source weighting and ranking
    - Graceful degradation on errors

    Example:
        retriever = ParallelRetriever()
        retriever.add_source("neo4j", SourceType.GRAPH, neo4j_retriever, weight=1.2)
        retriever.add_source("vectors", SourceType.VECTOR, vector_retriever, weight=1.0)

        results = retriever.retrieve("how to deploy", top_k=10)
    """

    def __init__(
        self,
        sources: list[RetrievalSource] | None = None,
        max_workers: int = 5,
        global_timeout: float = 30.0,
        dedup_threshold: float = 0.95,
    ):
        """
        Initialize parallel retriever.

        Args:
            sources: List of retrieval sources
            max_workers: Maximum concurrent retrievals
            global_timeout: Overall timeout for all retrievals
            dedup_threshold: Similarity threshold for deduplication
        """
        self.sources = sources or []
        self.max_workers = max_workers
        self.global_timeout = global_timeout
        self.dedup_threshold = dedup_threshold

    def add_source(
        self,
        name: str,
        source_type: SourceType,
        retriever: RetrieverProtocol,
        weight: float = 1.0,
        timeout: float = 10.0,
    ) -> "ParallelRetriever":
        """Add a retrieval source. Returns self for chaining."""
        self.sources.append(
            RetrievalSource(
                name=name,
                source_type=source_type,
                retriever=retriever,
                weight=weight,
                timeout=timeout,
            )
        )
        return self

    def remove_source(self, name: str) -> bool:
        """Remove a source by name. Returns True if found."""
        for i, source in enumerate(self.sources):
            if source.name == name:
                self.sources.pop(i)
                return True
        return False

    def _retrieve_from_source(
        self, source: RetrievalSource, query: str, top_k: int
    ) -> tuple[str, list[ParallelResult], float, str | None]:
        """
        Retrieve from a single source with timeout.

        Returns: (source_name, results, time_ms, error_or_none)
        """
        start = time.time()
        error = None
        results: list[ParallelResult] = []

        try:
            raw_results = source.retriever.retrieve(query, top_k=top_k)

            for doc in raw_results:
                # Normalize different result formats
                content = (
                    doc.get("content")
                    or doc.get("text")
                    or doc.get("page_content")
                    or str(doc)
                )
                score = (
                    doc.get("score")
                    or doc.get("similarity")
                    or doc.get("relevance")
                    or 0.5
                )

                # Apply source weight
                weighted_score = float(score) * source.weight

                results.append(
                    ParallelResult(
                        content=content,
                        source_name=source.name,
                        source_type=source.source_type,
                        score=weighted_score,
                        metadata=doc.get("metadata", {}),
                        retrieval_time_ms=(time.time() - start) * 1000,
                    )
                )

        except Exception as e:
            error = f"{source.name}: {e}"
            logger.warning(f"Retrieval failed for {source.name}: {e}")

        time_ms = (time.time() - start) * 1000
        return source.name, results, time_ms, error

    def _deduplicate(self, results: list[ParallelResult]) -> list[ParallelResult]:
        """Remove near-duplicate results, keeping highest scored."""
        seen_hashes: dict[str, ParallelResult] = {}

        for result in results:
            h = result.content_hash()
            if h in seen_hashes:
                # Keep higher scored version
                if result.score > seen_hashes[h].score:
                    seen_hashes[h] = result
            else:
                seen_hashes[h] = result

        return list(seen_hashes.values())

    def retrieve(self, query: str, top_k: int = 10) -> ParallelRetrievalResult:
        """
        Retrieve from all sources in parallel.

        Args:
            query: Search query
            top_k: Number of results per source (final may be more)

        Returns:
            ParallelRetrievalResult with merged, ranked results
        """
        start = time.time()
        enabled_sources = [s for s in self.sources if s.enabled]

        if not enabled_sources:
            return ParallelRetrievalResult(
                query=query,
                results=[],
                total_time_ms=0,
                source_stats={},
                errors=["No enabled sources"],
            )

        all_results: list[ParallelResult] = []
        source_stats: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        # Execute in parallel with thread pool
        with ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(enabled_sources))
        ) as executor:
            futures = {
                executor.submit(
                    self._retrieve_from_source, source, query, top_k
                ): source
                for source in enabled_sources
            }

            for future in as_completed(futures, timeout=self.global_timeout):
                try:
                    source_name, results, time_ms, error = future.result(timeout=1.0)
                    all_results.extend(results)

                    source_stats[source_name] = {
                        "count": len(results),
                        "time_ms": time_ms,
                        "success": error is None,
                    }

                    if error:
                        errors.append(error)

                except Exception as e:
                    source = futures[future]
                    errors.append(f"{source.name}: {e}")
                    source_stats[source.name] = {
                        "count": 0,
                        "time_ms": 0,
                        "success": False,
                    }

        # Deduplicate and sort by score
        all_results = self._deduplicate(all_results)
        all_results.sort(key=lambda r: r.score, reverse=True)

        total_time = (time.time() - start) * 1000

        return ParallelRetrievalResult(
            query=query,
            results=all_results,
            total_time_ms=total_time,
            source_stats=source_stats,
            errors=errors,
        )

    async def aretrieve(self, query: str, top_k: int = 10) -> ParallelRetrievalResult:
        """
        Async version of retrieve.

        Uses asyncio for sources that support async.
        """
        start = time.time()
        enabled_sources = [s for s in self.sources if s.enabled]

        if not enabled_sources:
            return ParallelRetrievalResult(
                query=query,
                results=[],
                total_time_ms=0,
                source_stats={},
                errors=["No enabled sources"],
            )

        async def retrieve_one(
            source: RetrievalSource,
        ) -> tuple[str, list[ParallelResult], float, str | None]:
            """Async wrapper for single source retrieval."""
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None, self._retrieve_from_source, source, query, top_k
                ),
                timeout=source.timeout,
            )

        # Execute all concurrently
        tasks = [retrieve_one(s) for s in enabled_sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[ParallelResult] = []
        source_stats: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        for source, result in zip(enabled_sources, results, strict=False):
            if isinstance(result, Exception):
                errors.append(f"{source.name}: {result}")
                source_stats[source.name] = {"count": 0, "time_ms": 0, "success": False}
            else:
                source_name, source_results, time_ms, error = result
                all_results.extend(source_results)
                source_stats[source_name] = {
                    "count": len(source_results),
                    "time_ms": time_ms,
                    "success": error is None,
                }
                if error:
                    errors.append(error)

        all_results = self._deduplicate(all_results)
        all_results.sort(key=lambda r: r.score, reverse=True)

        return ParallelRetrievalResult(
            query=query,
            results=all_results,
            total_time_ms=(time.time() - start) * 1000,
            source_stats=source_stats,
            errors=errors,
        )


class FederatedRetriever(ParallelRetriever):
    """
    Federated search across distributed sources.

    Extends ParallelRetriever with:
    - Query routing (some queries to specific sources)
    - Result fusion algorithms (RRF, CombMNZ)
    - Source health monitoring
    """

    def __init__(
        self,
        sources: list[RetrievalSource] | None = None,
        fusion_method: str = "rrf",  # "rrf", "combmnz", "weighted"
        **kwargs: Any,
    ):
        super().__init__(sources, **kwargs)
        self.fusion_method = fusion_method
        self._source_health: dict[str, float] = {}  # name -> health score (0-1)

    def _fuse_results(
        self, results_by_source: dict[str, list[ParallelResult]]
    ) -> list[ParallelResult]:
        """
        Fuse results from multiple sources using specified algorithm.
        """
        if self.fusion_method == "rrf":
            return self._reciprocal_rank_fusion(results_by_source)
        elif self.fusion_method == "combmnz":
            return self._combmnz_fusion(results_by_source)
        else:
            # Default weighted merge
            all_results = []
            for results in results_by_source.values():
                all_results.extend(results)
            return sorted(all_results, key=lambda r: r.score, reverse=True)

    def _reciprocal_rank_fusion(
        self, results_by_source: dict[str, list[ParallelResult]], k: int = 60
    ) -> list[ParallelResult]:
        """
        Reciprocal Rank Fusion - combines rankings from multiple sources.

        RRF score = sum(1 / (k + rank)) for each source where doc appears
        """
        # Map content hash to (result, total_score)
        fused: dict[str, tuple[ParallelResult, float]] = {}

        for source_results in results_by_source.values():
            for rank, result in enumerate(source_results):
                h = result.content_hash()
                rrf_score = 1.0 / (k + rank + 1)

                if h in fused:
                    existing_result, existing_score = fused[h]
                    fused[h] = (existing_result, existing_score + rrf_score)
                else:
                    fused[h] = (result, rrf_score)

        # Sort by fused score
        results = [(r, s) for r, s in fused.values()]
        results.sort(key=lambda x: x[1], reverse=True)

        # Update scores to fused scores
        return [
            ParallelResult(
                content=r.content,
                source_name=r.source_name,
                source_type=r.source_type,
                score=s,
                metadata=r.metadata,
                retrieval_time_ms=r.retrieval_time_ms,
            )
            for r, s in results
        ]

    def _combmnz_fusion(
        self, results_by_source: dict[str, list[ParallelResult]]
    ) -> list[ParallelResult]:
        """
        CombMNZ fusion - sum of scores * number of sources containing doc.
        """
        fused: dict[str, tuple[ParallelResult, float, int]] = {}

        for source_results in results_by_source.values():
            for result in source_results:
                h = result.content_hash()

                if h in fused:
                    existing_result, existing_score, count = fused[h]
                    fused[h] = (
                        existing_result,
                        existing_score + result.score,
                        count + 1,
                    )
                else:
                    fused[h] = (result, result.score, 1)

        # CombMNZ: sum * count
        results = [(r, s * c) for r, s, c in fused.values()]
        results.sort(key=lambda x: x[1], reverse=True)

        return [
            ParallelResult(
                content=r.content,
                source_name=r.source_name,
                source_type=r.source_type,
                score=s,
                metadata=r.metadata,
                retrieval_time_ms=r.retrieval_time_ms,
            )
            for r, s in results
        ]

    def retrieve(self, query: str, top_k: int = 10) -> ParallelRetrievalResult:
        """Retrieve with result fusion."""
        # Get parallel results
        result = super().retrieve(query, top_k)

        # Group by source for fusion
        by_source: dict[str, list[ParallelResult]] = {}
        for r in result.results:
            by_source.setdefault(r.source_name, []).append(r)

        # Fuse results
        fused = self._fuse_results(by_source)

        return ParallelRetrievalResult(
            query=result.query,
            results=fused,
            total_time_ms=result.total_time_ms,
            source_stats=result.source_stats,
            errors=result.errors,
        )
