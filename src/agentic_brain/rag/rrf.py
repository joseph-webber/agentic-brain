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
Unified Reciprocal Rank Fusion (RRF) Implementation.

This module provides the SINGLE canonical RRF implementation for the entire
agentic-brain project. All other modules should import from here.

RRF is a technique for combining multiple ranked lists into a single ranking.
It's particularly effective for hybrid search (combining vector + keyword + graph results).

Formula: RRF_score(d) = Σ(1 / (k + rank(d))) for each ranked list containing document d

Key features:
- Configurable k parameter (smoothing constant, default 60)
- Source-specific weights for weighted RRF
- Explain mode for debugging (shows per-source contributions)
- Type-safe with full typing support
- Works with both dict results and dataclass objects

References:
- Cormack, G. V., Clarke, C. L., & Buettcher, S. (2009). Reciprocal rank fusion
  outperforms condorcet and individual rank learning methods. SIGIR.

Usage:
    from agentic_brain.rag.rrf import reciprocal_rank_fusion, RRFResult

    # Basic usage
    fused = reciprocal_rank_fusion([
        {"source": "vector", "results": vector_results},
        {"source": "keyword", "results": keyword_results},
    ])

    # With weights and explain mode
    fused = reciprocal_rank_fusion(
        ranked_lists,
        k=60,
        weights={"vector": 1.5, "keyword": 1.0, "graph": 1.2},
        explain=True,
    )

    # Legacy API (backward compatible)
    fused = reciprocal_rank_fusion_legacy(vector_results, graph_results, keyword_results)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar, Protocol, runtime_checkable

__all__ = [
    "reciprocal_rank_fusion",
    "reciprocal_rank_fusion_legacy",
    "RRFResult",
    "RRFExplanation",
    "RRFSourceContribution",
    "get_result_id",
    "DEFAULT_K",
]

# Default RRF k parameter (smoothing constant)
# Higher k = more uniform scoring across ranks
# Lower k = top ranks contribute much more
DEFAULT_K: int = 60

T = TypeVar("T")


@runtime_checkable
class HasContentHash(Protocol):
    """Protocol for objects that can provide a content hash."""

    def content_hash(self) -> str:
        """Return a unique hash for deduplication."""
        ...


@dataclass
class RRFSourceContribution:
    """Contribution from a single source to an item's RRF score."""

    source: str
    rank: int
    raw_score: float
    weighted_score: float
    original_score: float | None = None


@dataclass
class RRFExplanation:
    """Detailed explanation of how an RRF score was calculated."""

    item_id: str
    total_score: float
    sources: list[RRFSourceContribution] = field(default_factory=list)
    appeared_in_count: int = 0

    @property
    def source_names(self) -> list[str]:
        """Names of sources where this item appeared."""
        return [s.source for s in self.sources]


@dataclass
class RRFResult:
    """Result from RRF fusion with optional explanation."""

    items: list[dict[str, Any]]
    explanations: dict[str, RRFExplanation] | None = None
    k: int = DEFAULT_K
    weights: dict[str, float] | None = None
    total_sources: int = 0
    total_unique_items: int = 0


def get_result_id(
    item: dict[str, Any] | Any,
    id_fields: tuple[str, ...] = ("id", "chunk_id", "doc_id", "content_hash"),
) -> str:
    """
    Extract a stable identifier from a result item.

    Tries multiple common ID field names in order. If the item has a
    content_hash() method (like ParallelResult), uses that.

    Args:
        item: Result item (dict or object)
        id_fields: Tuple of field names to try, in priority order

    Returns:
        String identifier for the item

    Raises:
        KeyError: If no ID field is found

    Examples:
        >>> get_result_id({"id": "doc_1", "score": 0.9})
        'doc_1'
        >>> get_result_id({"chunk_id": "chunk_42"})
        'chunk_42'
    """
    # Handle objects with content_hash method
    if isinstance(item, HasContentHash):
        return item.content_hash()

    # Handle dict-like objects
    if isinstance(item, dict):
        for field_name in id_fields:
            value = item.get(field_name)
            if value is not None:
                return str(value)
        raise KeyError(
            f"RRF result item must include one of: {id_fields}. Got keys: {list(item.keys())}"
        )

    # Handle dataclass/object attributes
    for field_name in id_fields:
        value = getattr(item, field_name, None)
        if value is not None:
            return str(value)

    raise KeyError(
        f"RRF result item must have one of: {id_fields}. Got type: {type(item).__name__}"
    )


def _compute_rrf_score(rank: int, k: int, weight: float = 1.0) -> float:
    """
    Compute the RRF contribution for a single rank position.

    Args:
        rank: 0-indexed rank position
        k: Smoothing constant
        weight: Source-specific weight multiplier

    Returns:
        RRF score contribution
    """
    return weight / (k + rank + 1)


def reciprocal_rank_fusion(
    ranked_lists: list[dict[str, Any]],
    *,
    k: int = DEFAULT_K,
    weights: dict[str, float] | None = None,
    explain: bool = False,
    id_extractor: Callable[[Any], str] | None = None,
    merge_strategy: str = "update",  # "update" | "first" | "all"
    top_k: int | None = None,
) -> RRFResult:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion.

    This is the CANONICAL RRF implementation for agentic-brain. All other
    modules should use this function.

    Args:
        ranked_lists: List of dicts, each with:
            - "source": Name of the source (e.g., "vector", "keyword", "graph")
            - "results": List of result items (must have id field)
        k: Smoothing constant (default 60). Higher = more uniform scoring.
        weights: Optional source-specific weights (e.g., {"vector": 1.5, "keyword": 1.0}).
            Default weight is 1.0 for unlisted sources.
        explain: If True, include detailed per-source score breakdown.
        id_extractor: Custom function to extract ID from items. Uses get_result_id by default.
        merge_strategy: How to merge item data from multiple sources:
            - "update": Later sources update earlier data (default)
            - "first": Keep only first occurrence's data
            - "all": Keep all source data in a list
        top_k: If set, return only the top k results.

    Returns:
        RRFResult containing:
            - items: Fused results sorted by RRF score (descending)
            - explanations: If explain=True, per-item score breakdowns
            - metadata: k value, weights, counts

    Examples:
        >>> # Basic two-source fusion
        >>> fused = reciprocal_rank_fusion([
        ...     {"source": "vector", "results": [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.8}]},
        ...     {"source": "keyword", "results": [{"id": "b", "score": 0.85}, {"id": "c", "score": 0.7}]},
        ... ])
        >>> fused.items[0]["id"]  # "b" appears in both lists, scores highest
        'b'

        >>> # Weighted fusion (vector results weighted higher)
        >>> fused = reciprocal_rank_fusion(
        ...     ranked_lists,
        ...     weights={"vector": 1.5, "keyword": 1.0},
        ... )

        >>> # With explanation for debugging
        >>> fused = reciprocal_rank_fusion(ranked_lists, explain=True)
        >>> fused.explanations["b"].sources  # See per-source contributions
    """
    weights = weights or {}
    id_fn = id_extractor or get_result_id

    # Accumulators
    scores: dict[str, float] = {}
    merged_items: dict[str, dict[str, Any] | list[dict[str, Any]]] = {}
    explanations: dict[str, RRFExplanation] = {} if explain else {}

    for source_dict in ranked_lists:
        source_name = source_dict.get("source", "unknown")
        results = source_dict.get("results", [])
        source_weight = weights.get(source_name, 1.0)

        for rank, item in enumerate(results):
            try:
                item_id = id_fn(item)
            except (KeyError, TypeError) as e:
                # Skip items without valid ID
                continue

            # Compute RRF contribution
            raw_score = 1.0 / (k + rank + 1)
            weighted_score = raw_score * source_weight
            scores[item_id] = scores.get(item_id, 0.0) + weighted_score

            # Merge item data
            item_dict = dict(item) if isinstance(item, dict) else {"_object": item}
            if merge_strategy == "update":
                if item_id not in merged_items:
                    merged_items[item_id] = {}
                merged_items[item_id].update(item_dict)
            elif merge_strategy == "first":
                if item_id not in merged_items:
                    merged_items[item_id] = item_dict
            elif merge_strategy == "all":
                if item_id not in merged_items:
                    merged_items[item_id] = []
                merged_items[item_id].append({**item_dict, "_source": source_name})

            # Build explanation if requested
            if explain:
                if item_id not in explanations:
                    explanations[item_id] = RRFExplanation(
                        item_id=item_id,
                        total_score=0.0,
                        sources=[],
                        appeared_in_count=0,
                    )

                original_score = (
                    item.get("score") if isinstance(item, dict) else getattr(item, "score", None)
                )
                explanations[item_id].sources.append(
                    RRFSourceContribution(
                        source=source_name,
                        rank=rank,
                        raw_score=raw_score,
                        weighted_score=weighted_score,
                        original_score=original_score,
                    )
                )
                explanations[item_id].appeared_in_count += 1

    # Update explanation totals
    if explain:
        for item_id, explanation in explanations.items():
            explanation.total_score = scores[item_id]

    # Sort by RRF score (descending)
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    if top_k is not None:
        sorted_ids = sorted_ids[:top_k]

    # Build final results
    items: list[dict[str, Any]] = []
    for item_id in sorted_ids:
        item_data = merged_items[item_id]
        if merge_strategy == "all":
            # For "all" strategy, flatten the first item and add sources
            base = item_data[0] if item_data else {}
            result = {
                **base,
                "id": item_id,
                "rrf_score": scores[item_id],
                "_all_sources": item_data,
            }
        else:
            result = {
                **item_data,
                "id": item_id,
                "rrf_score": scores[item_id],
            }
        items.append(result)

    return RRFResult(
        items=items,
        explanations=explanations if explain else None,
        k=k,
        weights=weights or None,
        total_sources=len(ranked_lists),
        total_unique_items=len(items),
    )


def reciprocal_rank_fusion_legacy(
    vector_results: list[dict[str, Any]],
    graph_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]] | None = None,
    k: int = DEFAULT_K,
) -> list[dict[str, Any]]:
    """
    Legacy API for backward compatibility.

    This wraps the new unified RRF function but maintains the old signature
    for existing code that calls reciprocal_rank_fusion(vector, graph, keyword).

    Args:
        vector_results: Vector search results (must have id/chunk_id field)
        graph_results: Graph search results
        keyword_results: Optional keyword search results
        k: Smoothing constant (default 60)

    Returns:
        List of fused results sorted by RRF score, each containing:
            - id: Document identifier
            - rrf_score: Computed RRF score
            - (all other fields merged from sources)

    Examples:
        >>> fused = reciprocal_rank_fusion_legacy(
        ...     [{"id": "doc_1", "score": 0.95}],
        ...     [{"id": "doc_2", "score": 0.87}],
        ...     [{"id": "doc_1", "score": 0.88}],
        ...     k=60,
        ... )
    """
    ranked_lists = [
        {"source": "vector", "results": vector_results},
        {"source": "graph", "results": graph_results},
    ]
    if keyword_results:
        ranked_lists.append({"source": "keyword", "results": keyword_results})

    result = reciprocal_rank_fusion(ranked_lists, k=k)
    return result.items


# Convenience alias for backward compatibility
# The old hybrid.py exported this name
_get_result_id = get_result_id
