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

"""Convenience shortcuts for common API operations.

Dead-simple one-liners for RAG, graphs, search, and evaluation.

Examples:
    # RAG - one-liner
    answer = quick_rag("What is our deployment process?", docs)

    # Graph - instant creation
    graph = quick_graph(["User", "Project", "Task"])

    # Search - unified interface
    results = quick_search("neural networks", num_results=5)

    # Evaluation - fast metrics
    metrics = quick_eval(results, golden_answers)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from agentic_brain.graph import TopicHub
from agentic_brain.rag import RAGPipeline, RAGResult, ask

logger = logging.getLogger(__name__)

__all__ = [
    "quick_rag",
    "quick_graph",
    "quick_search",
    "quick_eval",
    "RAGResult",
]


def quick_rag(
    question: str,
    docs: Optional[list[str]] = None,
    llm_provider: str = "ollama",
    llm_model: str = "llama3.1:8b",
    use_cache: bool = True,
) -> RAGResult:
    """One-liner RAG: ask a question, get an answer with sources.

    Args:
        question: Your question or query
        docs: Optional list of document paths or URLs to search
        llm_provider: LLM provider ("ollama", "openai", "groq", etc)
        llm_model: Model to use for generation
        use_cache: Whether to cache results (default True)

    Returns:
        RAGResult with answer, sources, and confidence

    Examples:
        # Simple query
        result = quick_rag("How do I deploy?")
        print(result.answer)

        # With documents
        docs = ["deployment.md", "devops/pipeline.md"]
        result = quick_rag("How do I deploy?", docs)

        # Use specific LLM
        result = quick_rag(
            "Query",
            llm_provider="openai",
            llm_model="gpt-4"
        )
    """
    try:
        # Initialize pipeline
        pipeline = RAGPipeline(
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

        # If docs provided, ingest them
        if docs:
            for doc in docs:
                try:
                    pipeline.ingest_document(doc)
                except Exception as e:
                    logger.warning(f"Failed to ingest {doc}: {e}")

        # Query and return result
        result = pipeline.query(question)
        result.cached = use_cache
        return result

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        # Return error result
        return RAGResult(
            query=question,
            answer=f"Error: {str(e)}",
            sources=[],
            confidence=0.0,
            model=llm_model,
            cached=False,
        )


def quick_graph(
    entities: list[str],
    relationships: Optional[list[tuple[str, str, str]]] = None,
) -> TopicHub:
    """Instant knowledge graph creation from entities.

    Args:
        entities: List of entity names to create
        relationships: Optional list of (source, relation, target) tuples

    Returns:
        Initialized TopicHub ready to use

    Examples:
        # Create simple graph
        graph = quick_graph(["User", "Project", "Task"])

        # Add relationships
        rels = [
            ("User", "owns", "Project"),
            ("Project", "contains", "Task"),
        ]
        graph = quick_graph(["User", "Project", "Task"], rels)
    """
    try:
        # Create graph hub
        graph = TopicHub()

        # Create entities
        for entity in entities:
            try:
                graph.create_topic(entity)
            except Exception as e:
                logger.warning(f"Failed to create entity {entity}: {e}")

        # Create relationships if provided
        if relationships:
            for source, relation, target in relationships:
                try:
                    graph.link_topic(source, relation, target)
                except Exception as e:
                    logger.warning(
                        f"Failed to link {source} -> {target}: {e}"
                    )

        return graph

    except Exception as e:
        logger.error(f"Graph creation failed: {e}")
        raise


def quick_search(
    query: str,
    num_results: int = 5,
    search_type: str = "hybrid",
) -> list[dict[str, Any]]:
    """Unified search across all sources.

    Args:
        query: Search query
        num_results: Number of results to return (default 5)
        search_type: "hybrid" (vector+keyword), "vector", or "keyword"

    Returns:
        List of search results with metadata

    Examples:
        # Simple search
        results = quick_search("neural networks", num_results=10)

        # Vector search only
        results = quick_search("AI", search_type="vector")

        # Keyword search only
        results = quick_search("deployment", search_type="keyword")
    """
    try:
        pipeline = RAGPipeline()

        # Execute search based on type
        if search_type == "hybrid":
            results = pipeline.hybrid_search(query, limit=num_results)
        elif search_type == "vector":
            results = pipeline.vector_search(query, limit=num_results)
        elif search_type == "keyword":
            results = pipeline.keyword_search(query, limit=num_results)
        else:
            raise ValueError(f"Unknown search_type: {search_type}")

        # Format results
        formatted = []
        for result in results:
            formatted.append(
                {
                    "content": result.content[:500],
                    "source": result.source,
                    "score": result.score,
                    "confidence": getattr(result, "confidence", None),
                }
            )

        return formatted

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def quick_eval(
    results: list[RAGResult],
    golden_answers: Optional[list[str]] = None,
    metrics: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Fast evaluation of RAG/search results.

    Args:
        results: List of RAGResult objects to evaluate
        golden_answers: Optional golden answers for comparison
        metrics: List of metrics to compute. Options:
            - "retrieval" - retrieval precision/recall
            - "generation" - answer quality
            - "latency" - response time
            - "sources" - source citation quality
            - "confidence" - confidence calibration

    Returns:
        Dictionary with evaluation metrics

    Examples:
        # Simple evaluation
        results = [quick_rag("Q1"), quick_rag("Q2")]
        metrics = quick_eval(results)

        # Compare against golden answers
        golden = ["Expected answer 1", "Expected answer 2"]
        metrics = quick_eval(results, golden)

        # Specific metrics
        metrics = quick_eval(
            results,
            metrics=["retrieval", "generation", "latency"]
        )
    """
    if not results:
        return {"error": "No results to evaluate"}

    if metrics is None:
        metrics = ["retrieval", "generation", "sources"]

    eval_results: dict[str, Any] = {
        "total_queries": len(results),
        "metrics_computed": metrics,
    }

    try:
        # Compute retrieval metrics
        if "retrieval" in metrics:
            has_sources = sum(1 for r in results if r.has_sources)
            eval_results["retrieval"] = {
                "with_sources": has_sources,
                "without_sources": len(results) - has_sources,
                "retrieval_rate": has_sources / len(results) if results else 0,
            }

        # Compute generation metrics
        if "generation" in metrics:
            avg_answer_length = sum(
                len(r.answer) for r in results
            ) / len(results)
            eval_results["generation"] = {
                "avg_answer_length": int(avg_answer_length),
                "avg_confidence": sum(r.confidence for r in results)
                / len(results),
                "high_confidence": sum(1 for r in results if r.confidence >= 0.8),
                "medium_confidence": sum(
                    1 for r in results if 0.5 <= r.confidence < 0.8
                ),
                "low_confidence": sum(1 for r in results if r.confidence < 0.5),
            }

        # Compute latency metrics
        if "latency" in metrics:
            total_time = sum(r.generation_time_ms for r in results)
            avg_time = total_time / len(results) if results else 0
            eval_results["latency"] = {
                "total_ms": total_time,
                "avg_ms": avg_time,
                "max_ms": max(
                    (r.generation_time_ms for r in results), default=0
                ),
            }

        # Compute source metrics
        if "sources" in metrics:
            total_sources = sum(len(r.sources) for r in results)
            avg_sources = total_sources / len(results) if results else 0
            eval_results["sources"] = {
                "total": total_sources,
                "avg_per_query": avg_sources,
                "with_sources": sum(1 for r in results if r.has_sources),
                "without_sources": sum(1 for r in results if not r.has_sources),
            }

        # Compare with golden answers if provided
        if "generation" in metrics and golden_answers:
            if len(golden_answers) == len(results):
                # Simple string similarity comparison
                from difflib import SequenceMatcher

                similarities = []
                for result, golden in zip(results, golden_answers):
                    sim = SequenceMatcher(
                        None, result.answer.lower(), golden.lower()
                    ).ratio()
                    similarities.append(sim)

                eval_results["generation"]["avg_similarity_to_golden"] = sum(
                    similarities
                ) / len(similarities)
                eval_results["generation"]["exact_matches"] = sum(
                    1
                    for result, golden in zip(results, golden_answers)
                    if result.answer.lower() == golden.lower()
                )

        # Compute confidence metrics
        if "confidence" in metrics:
            confidences = [r.confidence for r in results]
            eval_results["confidence"] = {
                "avg": sum(confidences) / len(confidences),
                "min": min(confidences) if confidences else 0,
                "max": max(confidences) if confidences else 1,
                "std_dev": (
                    (
                        sum((c - (sum(confidences) / len(confidences))) ** 2
                            for c in confidences)
                        / len(confidences)
                    ) ** 0.5
                    if confidences
                    else 0
                ),
            }

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        eval_results["error"] = str(e)

    return eval_results
