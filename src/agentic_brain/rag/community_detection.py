# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Community detection with hierarchical summarization for Graph RAG.

Implements Microsoft GraphRAG-style community detection:
- Leiden algorithm via Neo4j GDS (primary) with Louvain fallback
- Multi-level community hierarchy (sub-communities → communities → super-communities)
- Community summarization for global search context
- Entity resolution / deduplication across communities
- Pure-Cypher connected-components fallback when GDS is unavailable

References:
- Microsoft GraphRAG: https://arxiv.org/abs/2404.16130
- Leiden algorithm: https://arxiv.org/abs/1810.08473
"""

from __future__ import annotations

import inspect
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

GRAPH_PROJECT_NAME = "entity-graph"


@dataclass
class Community:
    """A detected community with its entities and metadata."""

    id: int
    level: int  # 0 = leaf, higher = coarser
    entities: list[str] = field(default_factory=list)
    entity_types: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    parent_id: Optional[int] = None
    children_ids: list[int] = field(default_factory=list)
    size: int = 0
    modularity_score: float = 0.0
    coverage_score: float = 0.0
    cohesion_score: float = 0.0
    resolution: Optional[float] = None
    n_iterations: Optional[int] = None
    randomness: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entities = list(dict.fromkeys(self.entities))
        self.children_ids = list(dict.fromkeys(self.children_ids))
        self.size = len(self.entities)


@dataclass
class CommunityHierarchy:
    """Multi-level community hierarchy following Microsoft GraphRAG design."""

    communities: dict[int, Community] = field(default_factory=dict)
    levels: int = 0
    entity_to_community: dict[str, int] = field(default_factory=dict)
    detection_method: str = "unknown"
    detection_time_ms: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)
    level_metrics: dict[int, dict[str, float]] = field(default_factory=dict)
    summaries_by_level: dict[int, dict[int, str]] = field(default_factory=dict)

    @property
    def flat_communities(self) -> dict[int, list[str]]:
        """Backward-compatible flat community map."""
        return {
            cid: list(community.entities) for cid, community in self.communities.items()
        }

    @property
    def max_level(self) -> int:
        if not self.communities:
            return -1
        return max(community.level for community in self.communities.values())

    def communities_at_level(self, level: int) -> list[Community]:
        return [
            community
            for community in self.communities.values()
            if community.level == level
        ]

    def get_entity_community(self, entity_name: str) -> Optional[Community]:
        cid = self.entity_to_community.get(entity_name)
        return self.communities.get(cid) if cid is not None else None

    def get_community_ancestors(self, community_id: int) -> list[Community]:
        """Walk up the hierarchy from a community to the root."""
        ancestors: list[Community] = []
        current = self.communities.get(community_id)
        while current and current.parent_id is not None:
            parent = self.communities.get(current.parent_id)
            if parent is None:
                break
            ancestors.append(parent)
            current = parent
        return ancestors


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _record_to_dict(record: Any) -> dict[str, Any]:
    if isinstance(record, dict):
        return dict(record)
    data = getattr(record, "data", None)
    if callable(data):
        payload = data()
        if isinstance(payload, dict):
            return payload
    try:
        return dict(record)
    except Exception:
        return {"value": record}


async def _normalize_async_result(result: Any) -> list[dict[str, Any]]:
    if result is None:
        return []
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, list):
        return [_record_to_dict(record) for record in result]
    data = getattr(result, "data", None)
    if callable(data):
        payload = data()
        if inspect.isawaitable(payload):
            payload = await payload
        if isinstance(payload, list):
            return [_record_to_dict(record) for record in payload]
        if isinstance(payload, dict):
            return [payload]
    if hasattr(result, "__aiter__"):
        records: list[dict[str, Any]] = []
        async for record in result:
            records.append(_record_to_dict(record))
        return records
    if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
        return [_record_to_dict(record) for record in result]
    return [_record_to_dict(result)]


def _query_records(session: Any, query: str, **params: Any) -> list[dict[str, Any]]:
    result = session.run(query, **params)
    if inspect.isawaitable(result):
        raise TypeError("Async session passed to sync community detection")
    return [_record_to_dict(record) for record in result]


async def _async_query_records(
    session: Any, query: str, **params: Any
) -> list[dict[str, Any]]:
    result = session.run(query, **params)
    if inspect.isawaitable(result):
        result = await result
    return await _normalize_async_result(result)


# ---------------------------------------------------------------------------
# GDS availability check
# ---------------------------------------------------------------------------


def _gds_available(session: Any) -> bool:
    """Check if Neo4j Graph Data Science plugin is installed."""
    try:
        result = session.run("RETURN gds.version() AS version")
        if inspect.isawaitable(result):
            raise TypeError("Async session passed to sync GDS availability check")
        record = result.single()
        if record:
            logger.info("Neo4j GDS version: %s", record["version"])
            return True
    except Exception:
        pass
    return False


async def _gds_available_async(session: Any) -> bool:
    """Async variant of GDS availability check."""
    try:
        records = await _async_query_records(session, "RETURN gds.version() AS version")
        return bool(records and records[0].get("version"))
    except Exception:
        return False


def _drop_graph_if_exists(session: Any, name: str = GRAPH_PROJECT_NAME) -> None:
    """Safely drop a GDS graph projection."""
    try:
        result = session.run("CALL gds.graph.drop($name, false)", name=name)
        if inspect.isawaitable(result):
            raise TypeError("Async session passed to sync graph drop")
    except Exception:
        pass


async def _drop_graph_if_exists_async(
    session: Any, name: str = GRAPH_PROJECT_NAME
) -> None:
    """Async graph projection cleanup."""
    try:
        await _async_query_records(
            session, "CALL gds.graph.drop($name, false)", name=name
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Hierarchy / metric helpers
# ---------------------------------------------------------------------------


def _build_resolution_schedule(
    base_resolution: float,
    max_levels: int,
    resolution_multiplier: float,
) -> list[float]:
    if max_levels <= 0:
        return []
    multiplier = max(resolution_multiplier, 1.0)
    return [
        base_resolution * (multiplier**power) for power in reversed(range(max_levels))
    ]


def _partition_signature(
    level_communities: dict[int, list[str]]
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        sorted(tuple(sorted(set(entities))) for entities in level_communities.values())
    )


def _build_hierarchy_from_levels(
    level_communities: list[tuple[float, dict[int, list[str]]]],
    *,
    detection_method: str,
    parameters: dict[str, Any],
    n_iterations: int,
    randomness: Optional[int],
) -> CommunityHierarchy:
    hierarchy = CommunityHierarchy(
        detection_method=detection_method,
        parameters=dict(parameters),
    )
    next_community_id = 0
    assignments_by_level: list[dict[str, int]] = []

    for level_index, (resolution, communities) in enumerate(level_communities):
        entity_assignment: dict[str, int] = {}
        for _, entities in sorted(communities.items(), key=lambda item: item[0]):
            global_id = next_community_id
            next_community_id += 1
            unique_entities = sorted(set(entities))
            hierarchy.communities[global_id] = Community(
                id=global_id,
                level=level_index,
                entities=unique_entities,
                resolution=resolution,
                n_iterations=n_iterations,
                randomness=randomness,
            )
            for entity in unique_entities:
                entity_assignment[entity] = global_id
                if level_index == 0:
                    hierarchy.entity_to_community[entity] = global_id
        assignments_by_level.append(entity_assignment)

    for level_index in range(len(assignments_by_level) - 1):
        child_assignment = assignments_by_level[level_index]
        parent_assignment = assignments_by_level[level_index + 1]
        for entity, child_id in child_assignment.items():
            parent_id = parent_assignment.get(entity)
            if parent_id is None:
                continue
            child = hierarchy.communities.get(child_id)
            parent = hierarchy.communities.get(parent_id)
            if child is None or parent is None:
                continue
            child.parent_id = parent_id
            if child_id not in parent.children_ids:
                parent.children_ids.append(child_id)

    hierarchy.levels = len(assignments_by_level)
    return hierarchy


def _load_relationship_edges(session: Any) -> list[tuple[str, str]]:
    try:
        records = _query_records(
            session,
            """
            MATCH (source:Entity)-[:RELATES_TO]-(target:Entity)
            WHERE source.name IS NOT NULL
              AND target.name IS NOT NULL
              AND source.name <> target.name
            RETURN source.name AS source, target.name AS target
            """,
        )
    except Exception:
        return []

    edges: set[tuple[str, str]] = set()
    for record in records:
        source = record.get("source")
        target = record.get("target")
        if not source or not target or source == target:
            continue
        left, right = sorted((str(source), str(target)))
        edges.add((left, right))
    return sorted(edges)


async def _load_relationship_edges_async(session: Any) -> list[tuple[str, str]]:
    try:
        records = await _async_query_records(
            session,
            """
            MATCH (source:Entity)-[:RELATES_TO]-(target:Entity)
            WHERE source.name IS NOT NULL
              AND target.name IS NOT NULL
              AND source.name <> target.name
            RETURN source.name AS source, target.name AS target
            """,
        )
    except Exception:
        return []

    edges: set[tuple[str, str]] = set()
    for record in records:
        source = record.get("source")
        target = record.get("target")
        if not source or not target or source == target:
            continue
        left, right = sorted((str(source), str(target)))
        edges.add((left, right))
    return sorted(edges)


def _populate_metrics(
    hierarchy: CommunityHierarchy,
    edges: list[tuple[str, str]],
) -> CommunityHierarchy:
    if not hierarchy.communities:
        return hierarchy

    degree_map: dict[str, int] = defaultdict(int)
    normalized_edges: list[tuple[str, str]] = []
    for source, target in edges:
        if source == target:
            continue
        normalized_edges.append((source, target))
        degree_map[source] += 1
        degree_map[target] += 1

    total_edges = len(normalized_edges)
    communities_by_level: dict[int, list[Community]] = defaultdict(list)

    for community in hierarchy.communities.values():
        members = set(community.entities)
        internal_edges = sum(
            1
            for source, target in normalized_edges
            if source in members and target in members
        )
        possible_edges = community.size * (community.size - 1) / 2
        if community.size <= 1:
            cohesion = 1.0 if community.size == 1 else 0.0
        else:
            cohesion = internal_edges / possible_edges if possible_edges else 0.0
        coverage = internal_edges / total_edges if total_edges else 0.0
        degree_sum = sum(degree_map.get(member, 0) for member in members)
        modularity = (
            (internal_edges / total_edges) - (degree_sum / (2 * total_edges)) ** 2
            if total_edges
            else 0.0
        )

        community.modularity_score = float(modularity)
        community.coverage_score = float(coverage)
        community.cohesion_score = float(cohesion)
        community.metadata.update(
            {
                "internal_edges": internal_edges,
                "possible_internal_edges": possible_edges,
                "total_edges": total_edges,
            }
        )
        communities_by_level[community.level].append(community)

    for level, communities in communities_by_level.items():
        total_internal_edges = sum(
            int(community.metadata.get("internal_edges", 0))
            for community in communities
        )
        total_size = sum(max(community.size, 1) for community in communities)
        hierarchy.level_metrics[level] = {
            "modularity": float(
                sum(community.modularity_score for community in communities)
            ),
            "coverage": (
                float(total_internal_edges / total_edges) if total_edges else 0.0
            ),
            "cohesion": (
                float(
                    sum(
                        community.cohesion_score * max(community.size, 1)
                        for community in communities
                    )
                    / total_size
                )
                if total_size
                else 0.0
            ),
            "community_count": float(len(communities)),
            "resolution": (
                float(
                    sum((community.resolution or 0.0) for community in communities)
                    / len(communities)
                )
                if communities
                else 0.0
            ),
        }

    return hierarchy


# ---------------------------------------------------------------------------
# Primary: Leiden via GDS (hierarchical)
# ---------------------------------------------------------------------------


def _detect_leiden_hierarchical(
    session: Any,
    *,
    gamma: float = 1.0,
    resolution: float | None = None,
    max_levels: int = 4,
    n_iterations: int = 10,
    randomness: Optional[int] = 42,
    resolution_multiplier: float = 2.0,
) -> CommunityHierarchy:
    """Run hierarchical Leiden community detection via Neo4j GDS."""
    _drop_graph_if_exists(session)
    session.run(
        """
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
        """,
        name=GRAPH_PROJECT_NAME,
    )

    base_resolution = resolution if resolution is not None else gamma
    parameters = {
        "gamma": gamma,
        "resolution": base_resolution,
        "max_levels": max_levels,
        "n_iterations": n_iterations,
        "randomness": randomness,
        "resolution_multiplier": resolution_multiplier,
    }
    schedule = _build_resolution_schedule(
        base_resolution, max_levels, resolution_multiplier
    )
    hierarchy_levels: list[tuple[float, dict[int, list[str]]]] = []
    last_signature: tuple[tuple[str, ...], ...] | None = None

    try:
        for current_resolution in schedule:
            try:
                records = _query_records(
                    session,
                    """
                    CALL gds.leiden.stream($name, {
                        gamma: $gamma,
                        maxIterations: $max_iterations,
                        randomSeed: $random_seed
                    })
                    YIELD nodeId, communityId
                    RETURN gds.util.asNode(nodeId).name AS entity, communityId
                    """,
                    name=GRAPH_PROJECT_NAME,
                    gamma=current_resolution,
                    max_iterations=n_iterations,
                    random_seed=randomness,
                )
            except Exception as exc:
                logger.warning(
                    "Leiden at resolution %.2f failed: %s", current_resolution, exc
                )
                break

            communities: dict[int, list[str]] = defaultdict(list)
            for record in records:
                entity = record.get("entity")
                community_id = record.get("communityId")
                if entity is None or community_id is None:
                    continue
                communities[int(community_id)].append(str(entity))

            if not communities:
                break

            signature = _partition_signature(communities)
            if signature == last_signature:
                continue
            hierarchy_levels.append((current_resolution, communities))
            last_signature = signature
    finally:
        _drop_graph_if_exists(session)

    hierarchy = _build_hierarchy_from_levels(
        hierarchy_levels,
        detection_method="leiden_hierarchical",
        parameters=parameters,
        n_iterations=n_iterations,
        randomness=randomness,
    )
    return _populate_metrics(hierarchy, _load_relationship_edges(session))


# ---------------------------------------------------------------------------
# Fallback: Louvain via GDS
# ---------------------------------------------------------------------------


def _detect_louvain(session: Any) -> CommunityHierarchy:
    """Louvain community detection fallback when Leiden is unavailable."""
    _drop_graph_if_exists(session)
    session.run(
        """
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
        """,
        name=GRAPH_PROJECT_NAME,
    )

    try:
        records = _query_records(
            session,
            """
            CALL gds.louvain.stream($name)
            YIELD nodeId, communityId
            RETURN gds.util.asNode(nodeId).name AS entity, communityId
            """,
            name=GRAPH_PROJECT_NAME,
        )
    finally:
        _drop_graph_if_exists(session)

    communities: dict[int, list[str]] = defaultdict(list)
    for record in records:
        entity = record.get("entity")
        community_id = record.get("communityId")
        if entity is None or community_id is None:
            continue
        communities[int(community_id)].append(str(entity))

    hierarchy = _build_hierarchy_from_levels(
        [(1.0, communities)] if communities else [],
        detection_method="louvain",
        parameters={"resolution": 1.0, "max_levels": 1},
        n_iterations=1,
        randomness=None,
    )
    hierarchy.levels = 1 if hierarchy.communities else 0
    return _populate_metrics(hierarchy, _load_relationship_edges(session))


# ---------------------------------------------------------------------------
# Pure-Cypher fallback: connected components (no GDS required)
# ---------------------------------------------------------------------------


def _detect_connected_components(session: Any) -> CommunityHierarchy:
    """Fallback community detection using pure Cypher connected components."""
    records = _query_records(
        session,
        """
        MATCH (e:Entity)
        WHERE EXISTS { (e)-[:RELATES_TO]-() }
        WITH collect(e) AS entities
        UNWIND entities AS start
        MATCH path = (start)-[:RELATES_TO*1..10]-(connected)
        WITH start, collect(DISTINCT connected) + [start] AS component
        WITH component, reduce(
            minName = '', n IN component |
            CASE WHEN minName = '' OR n.name < minName THEN n.name ELSE minName END
        ) AS canonical
        UNWIND component AS member
        RETURN member.name AS entity, canonical AS community_key
        """,
    )

    canonical_to_id: dict[str, int] = {}
    communities: dict[int, list[str]] = defaultdict(list)
    next_id = 0

    for record in records:
        entity = record.get("entity")
        community_key = record.get("community_key")
        if entity is None or community_key is None:
            continue
        if community_key not in canonical_to_id:
            canonical_to_id[str(community_key)] = next_id
            next_id += 1
        community_id = canonical_to_id[str(community_key)]
        communities[community_id].append(str(entity))

    hierarchy = _build_hierarchy_from_levels(
        [(1.0, communities)] if communities else [],
        detection_method="connected_components",
        parameters={"resolution": 1.0, "max_levels": 1},
        n_iterations=1,
        randomness=None,
    )
    hierarchy.levels = 1 if hierarchy.communities else 0
    return _populate_metrics(hierarchy, _load_relationship_edges(session))


# ---------------------------------------------------------------------------
# Entity resolution (deduplication)
# ---------------------------------------------------------------------------


def resolve_entities(session: Any, similarity_threshold: float = 0.85) -> int:
    """Merge duplicate entities based on normalized name similarity."""
    merged_count = 0
    try:
        records = _query_records(
            session,
            """
            MATCH (e1:Entity), (e2:Entity)
            WHERE id(e1) < id(e2)
              AND e1.normalized_name IS NOT NULL
              AND e2.normalized_name IS NOT NULL
              AND e1.normalized_name = e2.normalized_name
            RETURN e1.id AS keep_id, e2.id AS merge_id, e1.name AS name
            """,
        )
        merge_pairs = [
            (record.get("keep_id"), record.get("merge_id"), record.get("name"))
            for record in records
        ]

        for keep_id, merge_id, name in merge_pairs:
            if keep_id is None or merge_id is None:
                continue
            session.run(
                """
                MATCH (keep:Entity {id: $keep_id})
                MATCH (dup:Entity {id: $merge_id})
                SET keep.mention_count = coalesce(keep.mention_count, 0)
                    + coalesce(dup.mention_count, 0)
                WITH keep, dup
                MATCH (dup)-[r]->(target)
                WHERE NOT type(r) = 'SAME_AS'
                MERGE (keep)-[nr:RELATES_TO]->(target)
                SET nr.weight = coalesce(nr.weight, 0) + coalesce(r.weight, 0)
                WITH keep, dup
                MATCH (source)-[r]->(dup)
                WHERE NOT type(r) = 'SAME_AS'
                MERGE (source)-[nr:RELATES_TO]->(keep)
                SET nr.weight = coalesce(nr.weight, 0) + coalesce(r.weight, 0)
                WITH dup
                DETACH DELETE dup
                """,
                keep_id=keep_id,
                merge_id=merge_id,
            )
            merged_count += 1
            logger.debug(
                "Merged entity '%s' (duplicate %s → %s)", name, merge_id, keep_id
            )
    except Exception as exc:
        logger.warning("Entity resolution failed: %s", exc)

    if merged_count:
        logger.info("Entity resolution merged %d duplicate entities", merged_count)
    return merged_count


# ---------------------------------------------------------------------------
# Community summarization
# ---------------------------------------------------------------------------


def summarize_community(
    session: Any,
    community: Community,
    *,
    llm: Any | None = None,
    max_entities: int = 20,
    child_summaries: Optional[list[str]] = None,
) -> str:
    """Generate a summary for a community."""
    entity_names = community.entities[:max_entities]
    child_summaries = [summary for summary in (child_summaries or []) if summary]

    entity_details: list[dict[str, Any]] = []
    relationships: list[str] = []
    if entity_names:
        try:
            records = _query_records(
                session,
                """
                MATCH (e:Entity)
                WHERE e.name IN $names
                OPTIONAL MATCH (e)-[r:RELATES_TO]->(target:Entity)
                WHERE target.name IN $names
                RETURN e.name AS name, e.type AS type,
                       coalesce(e.mention_count, 1) AS mentions,
                       collect(DISTINCT {target: target.name, rel_type: type(r)}) AS rels
                """,
                names=entity_names,
            )
            for record in records:
                entity_details.append(
                    {
                        "name": record.get("name"),
                        "type": record.get("type") or "Entity",
                        "mentions": record.get("mentions", 1),
                    }
                )
                for rel in record.get("rels", []):
                    target = rel.get("target") if isinstance(rel, dict) else None
                    rel_type = rel.get("rel_type") if isinstance(rel, dict) else None
                    if target:
                        relationships.append(
                            f"{record.get('name')} -{rel_type or 'RELATES_TO'}-> {target}"
                        )
        except Exception:
            entity_details = [
                {
                    "name": name,
                    "type": community.entity_types.get(name, "Entity"),
                    "mentions": 1,
                }
                for name in entity_names
            ]
    else:
        entity_details = []

    if llm is not None:
        try:
            metrics = (
                f"modularity={community.modularity_score:.3f}, "
                f"coverage={community.coverage_score:.3f}, "
                f"cohesion={community.cohesion_score:.3f}"
            )
            prompt = (
                f"Summarize community level {community.level} in 2 short sentences.\n"
                f"Entities: {', '.join(str(item['name']) for item in entity_details[:max_entities]) or 'none'}\n"
                f"Child summaries: {'; '.join(child_summaries[:4]) or 'none'}\n"
                f"Relationships: {'; '.join(relationships[:10]) or 'none'}\n"
                f"Metrics: {metrics}\n"
                "Focus on the shared topic, important members, and why this level matters."
            )
            if hasattr(llm, "generate"):
                summary = llm.generate(prompt, max_tokens=150)
            elif hasattr(llm, "chat_sync"):
                summary = getattr(llm.chat_sync(prompt, max_tokens=150), "content", "")
            else:
                raise AttributeError("LLM has no generate() or chat_sync()")
            text = str(summary).strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("LLM community summarization failed: %s", exc)

    type_groups: dict[str, list[str]] = defaultdict(list)
    for detail in entity_details:
        type_groups[str(detail.get("type") or "Entity")].append(str(detail.get("name")))

    type_summary = "; ".join(
        f"{entity_type}: {', '.join(names[:4])}"
        for entity_type, names in sorted(type_groups.items())
    )
    child_summary_text = " ".join(child_summaries[:2]).strip()
    metric_summary = (
        f"Metrics — modularity {community.modularity_score:.2f}, "
        f"coverage {community.coverage_score:.2f}, cohesion {community.cohesion_score:.2f}."
    )
    relationship_text = (
        f" Key relationships: {'; '.join(relationships[:4])}." if relationships else ""
    )

    if community.level > 0 and child_summary_text:
        return (
            f"Level {community.level} community unifies {len(community.children_ids) or len(child_summaries)} "
            f"sub-communities. {child_summary_text} {metric_summary}"
        ).strip()

    preview = ", ".join(entity_names[:6])
    if len(entity_names) > 6:
        preview = f"{preview}, and {len(entity_names) - 6} more"
    return (
        f"Level {community.level} community containing {community.size} entities"
        f" ({preview}). {type_summary or 'Entity types are mixed.'}. {metric_summary}{relationship_text}"
    ).strip()


def summarize_all_communities(
    session: Any,
    hierarchy: CommunityHierarchy,
    *,
    llm: Any | None = None,
    level: int | None = None,
) -> CommunityHierarchy:
    """Generate summaries for all communities at one level or across the full hierarchy."""
    if level is None:
        levels = sorted(
            {community.level for community in hierarchy.communities.values()}
        )
    else:
        levels = [level]

    for current_level in levels:
        hierarchy.summaries_by_level.setdefault(current_level, {})
        for community in hierarchy.communities_at_level(current_level):
            if community.summary:
                hierarchy.summaries_by_level[current_level][
                    community.id
                ] = community.summary
                continue
            child_summaries = [
                hierarchy.communities[child_id].summary
                for child_id in community.children_ids
                if child_id in hierarchy.communities
                and hierarchy.communities[child_id].summary
            ]
            community.summary = summarize_community(
                session,
                community,
                llm=llm,
                child_summaries=child_summaries,
            )
            hierarchy.summaries_by_level[current_level][
                community.id
            ] = community.summary
    return hierarchy


# ---------------------------------------------------------------------------
# Public API: detect_communities (backward-compatible)
# ---------------------------------------------------------------------------


def detect_communities(
    session: Any,
    *,
    enabled: bool = True,
    gamma: float = 1.0,
    resolution: float | None = None,
    max_levels: int = 4,
    n_iterations: int = 10,
    randomness: Optional[int] = 42,
    resolution_multiplier: float = 2.0,
) -> dict[int, list[str]]:
    """Detect communities and return a flat map."""
    hierarchy = detect_communities_hierarchical(
        session,
        enabled=enabled,
        gamma=gamma,
        resolution=resolution,
        max_levels=max_levels,
        n_iterations=n_iterations,
        randomness=randomness,
        resolution_multiplier=resolution_multiplier,
    )
    return hierarchy.flat_communities


def detect_communities_hierarchical(
    session: Any,
    *,
    enabled: bool = True,
    gamma: float = 1.0,
    resolution: float | None = None,
    max_levels: int = 4,
    n_iterations: int = 10,
    randomness: Optional[int] = 42,
    resolution_multiplier: float = 2.0,
    summarize: bool = False,
    llm: Any | None = None,
) -> CommunityHierarchy:
    """Detect communities with full hierarchical structure."""
    if not enabled:
        return CommunityHierarchy(
            detection_method="disabled",
            parameters={"enabled": False},
            detection_time_ms=0.0,
        )

    start = time.monotonic()
    if _gds_available(session):
        try:
            hierarchy = _detect_leiden_hierarchical(
                session,
                gamma=gamma,
                resolution=resolution,
                max_levels=max_levels,
                n_iterations=n_iterations,
                randomness=randomness,
                resolution_multiplier=resolution_multiplier,
            )
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            if hierarchy.communities:
                if summarize:
                    summarize_all_communities(session, hierarchy, llm=llm)
                return hierarchy
            logger.warning("Leiden returned no communities, trying Louvain")
        except Exception as exc:
            logger.warning("Leiden failed, trying Louvain: %s", exc)

        try:
            hierarchy = _detect_louvain(session)
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            if hierarchy.communities:
                if summarize:
                    summarize_all_communities(session, hierarchy, llm=llm)
                return hierarchy
            logger.warning("Leiden returned no communities, trying Louvain")
        except Exception as exc:
            logger.warning("Louvain failed, trying connected components: %s", exc)

    try:
        hierarchy = _detect_connected_components(session)
        hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
        if summarize:
            summarize_all_communities(session, hierarchy, llm=llm)
        return hierarchy
    except Exception as exc:
        logger.error("All community detection methods failed: %s", exc)
        return CommunityHierarchy(detection_method="none", detection_time_ms=0.0)


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------


async def detect_communities_async(
    session: Any,
    *,
    enabled: bool = True,
    gamma: float = 1.0,
    resolution: float | None = None,
    max_levels: int = 4,
    n_iterations: int = 10,
    randomness: Optional[int] = 42,
    resolution_multiplier: float = 2.0,
) -> dict[int, list[str]]:
    """Async backward-compatible community detection."""
    hierarchy = await detect_communities_hierarchical_async(
        session,
        enabled=enabled,
        gamma=gamma,
        resolution=resolution,
        max_levels=max_levels,
        n_iterations=n_iterations,
        randomness=randomness,
        resolution_multiplier=resolution_multiplier,
    )
    return hierarchy.flat_communities


async def detect_communities_hierarchical_async(
    session: Any,
    *,
    enabled: bool = True,
    gamma: float = 1.0,
    resolution: float | None = None,
    max_levels: int = 4,
    n_iterations: int = 10,
    randomness: Optional[int] = 42,
    resolution_multiplier: float = 2.0,
) -> CommunityHierarchy:
    """Async hierarchical community detection."""
    if not enabled:
        return CommunityHierarchy(
            detection_method="disabled",
            parameters={"enabled": False},
            detection_time_ms=0.0,
        )

    start = time.monotonic()
    if await _gds_available_async(session):
        try:
            hierarchy = await _async_leiden_hierarchical(
                session,
                gamma=gamma,
                resolution=resolution,
                max_levels=max_levels,
                n_iterations=n_iterations,
                randomness=randomness,
                resolution_multiplier=resolution_multiplier,
            )
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            if hierarchy.communities:
                return hierarchy
            logger.warning("Async Leiden returned no communities, trying Louvain")
        except Exception as exc:
            logger.warning("Async Leiden failed, trying Louvain: %s", exc)

        try:
            hierarchy = await _async_louvain(session)
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            if hierarchy.communities:
                return hierarchy
            logger.warning("Async Leiden returned no communities, trying Louvain")
        except Exception as exc:
            logger.warning("Async Louvain failed, trying connected components: %s", exc)

    try:
        hierarchy = await _async_connected_components(session)
        hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
        return hierarchy
    except Exception as exc:
        logger.error("All async community detection methods failed: %s", exc)
        return CommunityHierarchy(detection_method="none", detection_time_ms=0.0)


async def _async_leiden_hierarchical(
    session: Any,
    *,
    gamma: float = 1.0,
    resolution: float | None = None,
    max_levels: int = 4,
    n_iterations: int = 10,
    randomness: Optional[int] = 42,
    resolution_multiplier: float = 2.0,
) -> CommunityHierarchy:
    await _drop_graph_if_exists_async(session)
    await _async_query_records(
        session,
        """
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
        """,
        name=GRAPH_PROJECT_NAME,
    )

    base_resolution = resolution if resolution is not None else gamma
    parameters = {
        "gamma": gamma,
        "resolution": base_resolution,
        "max_levels": max_levels,
        "n_iterations": n_iterations,
        "randomness": randomness,
        "resolution_multiplier": resolution_multiplier,
    }
    schedule = _build_resolution_schedule(
        base_resolution, max_levels, resolution_multiplier
    )
    hierarchy_levels: list[tuple[float, dict[int, list[str]]]] = []
    last_signature: tuple[tuple[str, ...], ...] | None = None

    try:
        for current_resolution in schedule:
            try:
                records = await _async_query_records(
                    session,
                    """
                    CALL gds.leiden.stream($name, {
                        gamma: $gamma,
                        maxIterations: $max_iterations,
                        randomSeed: $random_seed
                    })
                    YIELD nodeId, communityId
                    RETURN gds.util.asNode(nodeId).name AS entity, communityId
                    """,
                    name=GRAPH_PROJECT_NAME,
                    gamma=current_resolution,
                    max_iterations=n_iterations,
                    random_seed=randomness,
                )
            except Exception as exc:
                logger.warning(
                    "Async Leiden at resolution %.2f failed: %s",
                    current_resolution,
                    exc,
                )
                break

            communities: dict[int, list[str]] = defaultdict(list)
            for record in records:
                entity = record.get("entity")
                community_id = record.get("communityId")
                if entity is None or community_id is None:
                    continue
                communities[int(community_id)].append(str(entity))

            if not communities:
                break

            signature = _partition_signature(communities)
            if signature == last_signature:
                continue
            hierarchy_levels.append((current_resolution, communities))
            last_signature = signature
    finally:
        await _drop_graph_if_exists_async(session)

    hierarchy = _build_hierarchy_from_levels(
        hierarchy_levels,
        detection_method="leiden_hierarchical",
        parameters=parameters,
        n_iterations=n_iterations,
        randomness=randomness,
    )
    return _populate_metrics(hierarchy, await _load_relationship_edges_async(session))


async def _async_louvain(session: Any) -> CommunityHierarchy:
    await _drop_graph_if_exists_async(session)
    await _async_query_records(
        session,
        """
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
        """,
        name=GRAPH_PROJECT_NAME,
    )

    try:
        records = await _async_query_records(
            session,
            """
            CALL gds.louvain.stream($name)
            YIELD nodeId, communityId
            RETURN gds.util.asNode(nodeId).name AS entity, communityId
            """,
            name=GRAPH_PROJECT_NAME,
        )
    finally:
        await _drop_graph_if_exists_async(session)

    communities: dict[int, list[str]] = defaultdict(list)
    for record in records:
        entity = record.get("entity")
        community_id = record.get("communityId")
        if entity is None or community_id is None:
            continue
        communities[int(community_id)].append(str(entity))

    hierarchy = _build_hierarchy_from_levels(
        [(1.0, communities)] if communities else [],
        detection_method="louvain",
        parameters={"resolution": 1.0, "max_levels": 1},
        n_iterations=1,
        randomness=None,
    )
    hierarchy.levels = 1 if hierarchy.communities else 0
    return _populate_metrics(hierarchy, await _load_relationship_edges_async(session))


async def _async_connected_components(session: Any) -> CommunityHierarchy:
    records = await _async_query_records(
        session,
        """
        MATCH (e:Entity)
        WHERE EXISTS { (e)-[:RELATES_TO]-() }
        WITH collect(e) AS entities
        UNWIND entities AS start
        MATCH path = (start)-[:RELATES_TO*1..10]-(connected)
        WITH start, collect(DISTINCT connected) + [start] AS component
        WITH component, reduce(
            minName = '', n IN component |
            CASE WHEN minName = '' OR n.name < minName THEN n.name ELSE minName END
        ) AS canonical
        UNWIND component AS member
        RETURN member.name AS entity, canonical AS community_key
        """,
    )

    canonical_to_id: dict[str, int] = {}
    communities: dict[int, list[str]] = defaultdict(list)
    next_id = 0

    for record in records:
        entity = record.get("entity")
        community_key = record.get("community_key")
        if entity is None or community_key is None:
            continue
        key = str(community_key)
        if key not in canonical_to_id:
            canonical_to_id[key] = next_id
            next_id += 1
        communities[canonical_to_id[key]].append(str(entity))

    hierarchy = _build_hierarchy_from_levels(
        [(1.0, communities)] if communities else [],
        detection_method="connected_components",
        parameters={"resolution": 1.0, "max_levels": 1},
        n_iterations=1,
        randomness=None,
    )
    hierarchy.levels = 1 if hierarchy.communities else 0
    return _populate_metrics(hierarchy, await _load_relationship_edges_async(session))
