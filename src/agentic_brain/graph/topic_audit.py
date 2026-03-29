# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Auditing helpers for topic-hub organization in Neo4j."""

from __future__ import annotations

import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from statistics import median
from typing import Any

from agentic_brain.core.neo4j_pool import get_driver
from agentic_brain.graph.topic_hub import TopicHub, TopicRecord, ensure_topic_schema


@dataclass(frozen=True)
class OrphanNodeSummary:
    """Nodes that have not been assigned to any topic."""

    label: str
    orphan_count: int
    examples: list[str]


@dataclass(frozen=True)
class OverusedTopic:
    """Topic with an unusually high number of linked nodes."""

    name: str
    usage_count: int
    threshold: int


@dataclass(frozen=True)
class TopicMergeSuggestion:
    """Two topics that look similar enough to review for consolidation."""

    primary_topic: str
    secondary_topic: str
    similarity_score: float
    reason: str


@dataclass(frozen=True)
class TopicAuditReport:
    """Full audit payload for public topic taxonomy maintenance."""

    orphan_nodes: list[OrphanNodeSummary]
    overused_topics: list[OverusedTopic]
    merge_suggestions: list[TopicMergeSuggestion]


def _normalize_topic_name(name: str) -> str:
    return " ".join(name.lower().replace("_", " ").replace("-", " ").split())


def _token_set(name: str) -> set[str]:
    return set(_normalize_topic_name(name).split())


def _topic_similarity(left: str, right: str) -> float:
    normalized_left = _normalize_topic_name(left)
    normalized_right = _normalize_topic_name(right)
    if normalized_left.startswith(normalized_right) or normalized_right.startswith(
        normalized_left
    ):
        return 0.8
    ratio = SequenceMatcher(None, normalized_left, normalized_right).ratio()

    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return ratio

    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return max(ratio, jaccard)


def _merge_reason(left: str, right: str, similarity_score: float) -> str:
    shared_tokens = sorted(_token_set(left) & _token_set(right))
    if shared_tokens:
        return (
            f"Shared keywords: {', '.join(shared_tokens)} "
            f"(similarity {similarity_score:.2f})."
        )
    return f"Names are highly similar (similarity {similarity_score:.2f})."


def _find_merge_suggestions(
    topics: list[TopicRecord],
    *,
    merge_similarity_threshold: float,
) -> list[TopicMergeSuggestion]:
    suggestions: list[TopicMergeSuggestion] = []

    for index, left in enumerate(topics):
        for right in topics[index + 1 :]:
            similarity_score = _topic_similarity(left.name, right.name)
            if similarity_score < merge_similarity_threshold:
                continue

            primary, secondary = sorted((left.name, right.name), key=str.lower)
            suggestions.append(
                TopicMergeSuggestion(
                    primary_topic=primary,
                    secondary_topic=secondary,
                    similarity_score=round(similarity_score, 2),
                    reason=_merge_reason(left.name, right.name, similarity_score),
                )
            )

    return sorted(
        suggestions,
        key=lambda suggestion: (-suggestion.similarity_score, suggestion.primary_topic),
    )


def audit_topics(
    driver: Any | None = None,
    *,
    database: str | None = None,
    orphan_limit: int = 25,
    overuse_ratio: float = 3.0,
    min_overuse_count: int = 25,
    merge_similarity_threshold: float = 0.72,
) -> TopicAuditReport:
    """Audit topic coverage, saturation, and likely merge candidates."""

    neo4j_driver = driver or get_driver(database=database)
    topic_hub = TopicHub(driver=neo4j_driver, database=database)
    topics = topic_hub.get_topics()

    with (
        neo4j_driver.session(database=database) if database else neo4j_driver.session()
    ) as session:
        ensure_topic_schema(session)
        orphan_result = session.run(
            """
            MATCH (node)
            WHERE NOT node:Topic
              AND NOT node:Hub
              AND NOT (node)-[:BELONGS_TO]->(:Topic)
            WITH node,
                 CASE
                    WHEN size(labels(node)) = 0 THEN ['(unlabelled)']
                    ELSE labels(node)
                 END AS node_labels
            UNWIND node_labels AS label
            RETURN label,
                   count(node) AS orphan_count,
                   collect(toString(coalesce(node.name, node.id, elementId(node))))[0..5] AS examples
            ORDER BY orphan_count DESC, label ASC
            LIMIT $limit
            """,
            limit=orphan_limit,
        )
        orphan_rows = (
            orphan_result.data()
            if hasattr(orphan_result, "data")
            else list(orphan_result)
        )

    usage_counts = [topic.usage_count for topic in topics if topic.usage_count > 0]
    median_usage = median(usage_counts) if usage_counts else 0
    overuse_threshold = max(min_overuse_count, math.ceil(median_usage * overuse_ratio))

    orphan_nodes = [
        OrphanNodeSummary(
            label=row["label"],
            orphan_count=int(row["orphan_count"]),
            examples=[str(example) for example in row.get("examples", [])],
        )
        for row in orphan_rows
    ]
    overused_topics = [
        OverusedTopic(
            name=topic.name,
            usage_count=topic.usage_count,
            threshold=overuse_threshold,
        )
        for topic in topics
        if topic.usage_count >= overuse_threshold and topic.usage_count > 0
    ]
    merge_suggestions = _find_merge_suggestions(
        topics,
        merge_similarity_threshold=merge_similarity_threshold,
    )

    return TopicAuditReport(
        orphan_nodes=orphan_nodes,
        overused_topics=overused_topics,
        merge_suggestions=merge_suggestions,
    )
