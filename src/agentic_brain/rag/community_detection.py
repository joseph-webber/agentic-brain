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

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

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

    def __post_init__(self) -> None:
        self.size = len(self.entities)


@dataclass
class CommunityHierarchy:
    """Multi-level community hierarchy following Microsoft GraphRAG design."""

    communities: dict[int, Community] = field(default_factory=dict)
    levels: int = 0
    entity_to_community: dict[str, int] = field(default_factory=dict)
    detection_method: str = "unknown"
    detection_time_ms: float = 0.0

    @property
    def flat_communities(self) -> dict[int, list[str]]:
        """Backward-compatible flat community map."""
        return {cid: c.entities for cid, c in self.communities.items()}

    def communities_at_level(self, level: int) -> list[Community]:
        return [c for c in self.communities.values() if c.level == level]

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
# GDS availability check
# ---------------------------------------------------------------------------

def _gds_available(session: Any) -> bool:
    """Check if Neo4j Graph Data Science plugin is installed."""
    try:
        result = session.run("RETURN gds.version() AS version")
        record = result.single()
        if record:
            logger.info("Neo4j GDS version: %s", record["version"])
            return True
    except Exception:
        pass
    return False


def _drop_graph_if_exists(session: Any, name: str = GRAPH_PROJECT_NAME) -> None:
    """Safely drop a GDS graph projection."""
    try:
        session.run("CALL gds.graph.drop($name, false)", name=name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Primary: Leiden via GDS (hierarchical)
# ---------------------------------------------------------------------------

def _detect_leiden_hierarchical(
    session: Any,
    *,
    gamma: float = 1.0,
    max_levels: int = 3,
) -> CommunityHierarchy:
    """Run hierarchical Leiden community detection via Neo4j GDS.

    Produces a multi-level hierarchy by running Leiden at multiple resolutions.
    Higher gamma → more granular communities (leaf level).
    Lower gamma → coarser communities (higher level).
    """
    _drop_graph_if_exists(session)

    session.run(
        """
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
        """,
        name=GRAPH_PROJECT_NAME,
    )

    hierarchy = CommunityHierarchy(detection_method="leiden_hierarchical")
    all_entity_assignments: dict[int, dict[str, int]] = {}  # level → {entity: cid}

    # Run at multiple resolutions for hierarchy
    resolutions = [gamma * (2.0 ** i) for i in range(max_levels)]
    global_cid_offset = 0

    for level, resolution in enumerate(resolutions):
        try:
            result = session.run(
                """
                CALL gds.leiden.stream($name, {gamma: $gamma})
                YIELD nodeId, communityId
                RETURN gds.util.asNode(nodeId).name AS entity, communityId
                """,
                name=GRAPH_PROJECT_NAME,
                gamma=resolution,
            )
        except Exception as exc:
            logger.warning("Leiden at resolution %.2f failed: %s", resolution, exc)
            break

        level_communities: dict[int, list[str]] = defaultdict(list)
        for record in result:
            entity = record["entity"]
            cid = record["communityId"] + global_cid_offset
            level_communities[cid].append(entity)

        if not level_communities:
            break

        level_assignment: dict[str, int] = {}
        for cid, entities in level_communities.items():
            community = Community(
                id=cid, level=level, entities=entities, size=len(entities),
            )
            hierarchy.communities[cid] = community
            for entity in entities:
                level_assignment[entity] = cid
                if level == 0:
                    hierarchy.entity_to_community[entity] = cid

        all_entity_assignments[level] = level_assignment
        global_cid_offset += max(level_communities.keys()) + 1

    # Wire parent/child relationships between levels
    for level in range(1, len(all_entity_assignments)):
        child_level = all_entity_assignments.get(level - 1, {})
        parent_level = all_entity_assignments.get(level, {})
        child_to_parent: dict[int, int] = {}

        for entity, parent_cid in parent_level.items():
            child_cid = child_level.get(entity)
            if child_cid is not None and child_cid not in child_to_parent:
                child_to_parent[child_cid] = parent_cid

        for child_cid, parent_cid in child_to_parent.items():
            if child_cid in hierarchy.communities:
                hierarchy.communities[child_cid].parent_id = parent_cid
            if parent_cid in hierarchy.communities:
                if child_cid not in hierarchy.communities[parent_cid].children_ids:
                    hierarchy.communities[parent_cid].children_ids.append(child_cid)

    hierarchy.levels = len(all_entity_assignments)
    _drop_graph_if_exists(session)
    return hierarchy


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

    result = session.run(
        """
        CALL gds.louvain.stream($name)
        YIELD nodeId, communityId
        RETURN gds.util.asNode(nodeId).name AS entity, communityId
        """,
        name=GRAPH_PROJECT_NAME,
    )

    communities: dict[int, list[str]] = defaultdict(list)
    entity_map: dict[str, int] = {}
    for record in result:
        entity = record["entity"]
        cid = record["communityId"]
        communities[cid].append(entity)
        entity_map[entity] = cid

    _drop_graph_if_exists(session)

    hierarchy = CommunityHierarchy(
        detection_method="louvain",
        levels=1,
        entity_to_community=entity_map,
    )
    for cid, entities in communities.items():
        hierarchy.communities[cid] = Community(
            id=cid, level=0, entities=entities, size=len(entities),
        )
    return hierarchy


# ---------------------------------------------------------------------------
# Pure-Cypher fallback: connected components (no GDS required)
# ---------------------------------------------------------------------------

def _detect_connected_components(session: Any) -> CommunityHierarchy:
    """Fallback community detection using pure Cypher connected components.

    Works without GDS by walking RELATES_TO edges up to 10 hops.
    Suitable for small-to-medium graphs (< 50k entities).
    """
    result = session.run(
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
        """
    )

    canonical_to_id: dict[str, int] = {}
    communities: dict[int, list[str]] = defaultdict(list)
    entity_map: dict[str, int] = {}
    next_id = 0

    for record in result:
        entity = record["entity"]
        key = record["community_key"]
        if key not in canonical_to_id:
            canonical_to_id[key] = next_id
            next_id += 1
        cid = canonical_to_id[key]
        if entity not in entity_map:
            communities[cid].append(entity)
            entity_map[entity] = cid

    hierarchy = CommunityHierarchy(
        detection_method="connected_components",
        levels=1,
        entity_to_community=entity_map,
    )
    for cid, entities in communities.items():
        hierarchy.communities[cid] = Community(
            id=cid, level=0, entities=list(set(entities)), size=len(set(entities)),
        )
    return hierarchy


# ---------------------------------------------------------------------------
# Entity resolution (deduplication)
# ---------------------------------------------------------------------------

def resolve_entities(session: Any, similarity_threshold: float = 0.85) -> int:
    """Merge duplicate entities based on normalized name similarity.

    Uses Neo4j string matching to find entities whose normalized names match
    closely. Returns the number of entities merged.
    """
    merged_count = 0
    try:
        result = session.run(
            """
            MATCH (e1:Entity), (e2:Entity)
            WHERE id(e1) < id(e2)
              AND e1.normalized_name IS NOT NULL
              AND e2.normalized_name IS NOT NULL
              AND e1.normalized_name = e2.normalized_name
            RETURN e1.id AS keep_id, e2.id AS merge_id, e1.name AS name
            """
        )
        merge_pairs = [(r["keep_id"], r["merge_id"], r["name"]) for r in result]

        for keep_id, merge_id, name in merge_pairs:
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
            logger.debug("Merged entity '%s' (duplicate %s → %s)", name, merge_id, keep_id)

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
) -> str:
    """Generate a summary for a community.

    If an LLM is provided, uses it for natural-language summarization.
    Otherwise builds a structured description from entity metadata.
    """
    entity_names = community.entities[:max_entities]
    if not entity_names:
        return ""

    # Fetch entity details and relationships from Neo4j
    result = session.run(
        """
        MATCH (e:Entity)
        WHERE e.name IN $names
        OPTIONAL MATCH (e)-[r:RELATES_TO]->(target:Entity)
        WHERE target.name IN $names
        RETURN e.name AS name, e.type AS type,
               coalesce(e.mention_count, 1) AS mentions,
               collect(DISTINCT {target: target.name, rel_type: r.type}) AS rels
        """,
        names=entity_names,
    )

    entity_details: list[dict[str, Any]] = []
    relationships: list[str] = []
    for record in result:
        entity_details.append({
            "name": record["name"],
            "type": record["type"],
            "mentions": record["mentions"],
        })
        for rel in record["rels"]:
            if rel["target"]:
                relationships.append(
                    f"{record['name']} -{rel['rel_type']}-> {rel['target']}"
                )

    if llm is not None:
        try:
            entities_text = ", ".join(
                f"{e['name']} ({e['type']})" for e in entity_details
            )
            rels_text = "; ".join(relationships[:20]) if relationships else "none"

            prompt = (
                f"Summarize this knowledge graph community in 2-3 sentences.\n"
                f"Entities: {entities_text}\n"
                f"Relationships: {rels_text}\n"
                f"Focus on: what this community represents, key themes, "
                f"and how entities relate.\nSummary:"
            )

            if hasattr(llm, "generate"):
                summary = llm.generate(prompt, max_tokens=150)
            elif hasattr(llm, "chat_sync"):
                summary = getattr(llm.chat_sync(prompt, max_tokens=150), "content", "")
            else:
                raise AttributeError("LLM has no generate() or chat_sync()")

            return str(summary).strip()
        except Exception as exc:
            logger.warning("LLM community summarization failed: %s", exc)

    # Structured fallback
    type_groups: dict[str, list[str]] = defaultdict(list)
    for e in entity_details:
        type_groups[e["type"] or "Entity"].append(e["name"])

    parts = []
    for etype, names in sorted(type_groups.items()):
        parts.append(f"{etype}: {', '.join(names[:5])}")
    if relationships:
        parts.append(f"Key relationships: {'; '.join(relationships[:5])}")

    return ". ".join(parts)


def summarize_all_communities(
    session: Any,
    hierarchy: CommunityHierarchy,
    *,
    llm: Any | None = None,
    level: int = 0,
) -> CommunityHierarchy:
    """Generate summaries for all communities at a given level."""
    for community in hierarchy.communities_at_level(level):
        if not community.summary:
            community.summary = summarize_community(
                session, community, llm=llm,
            )
    return hierarchy


# ---------------------------------------------------------------------------
# Public API: detect_communities (backward-compatible)
# ---------------------------------------------------------------------------

def detect_communities(session: Any) -> dict[int, list[str]]:
    """Detect communities and return flat map (backward-compatible).

    Tries Leiden → Louvain → connected components.
    """
    hierarchy = detect_communities_hierarchical(session)
    return hierarchy.flat_communities


def detect_communities_hierarchical(
    session: Any,
    *,
    gamma: float = 1.0,
    max_levels: int = 3,
) -> CommunityHierarchy:
    """Detect communities with full hierarchical structure.

    Cascade:
    1. Leiden (hierarchical, multi-resolution) — requires GDS
    2. Louvain (single-level) — requires GDS
    3. Connected components (pure Cypher) — always works
    """
    start = time.monotonic()

    if _gds_available(session):
        try:
            hierarchy = _detect_leiden_hierarchical(
                session, gamma=gamma, max_levels=max_levels,
            )
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            logger.info(
                "Hierarchical Leiden: %d communities across %d levels (%.0fms)",
                len(hierarchy.communities),
                hierarchy.levels,
                hierarchy.detection_time_ms,
            )
            return hierarchy
        except Exception as exc:
            logger.warning("Leiden failed, trying Louvain: %s", exc)

        try:
            hierarchy = _detect_louvain(session)
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            logger.info(
                "Louvain fallback: %d communities (%.0fms)",
                len(hierarchy.communities),
                hierarchy.detection_time_ms,
            )
            return hierarchy
        except Exception as exc:
            logger.warning("Louvain failed, trying connected components: %s", exc)

    try:
        hierarchy = _detect_connected_components(session)
        hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Connected components fallback: %d communities (%.0fms)",
            len(hierarchy.communities),
            hierarchy.detection_time_ms,
        )
        return hierarchy
    except Exception as exc:
        logger.error("All community detection methods failed: %s", exc)
        return CommunityHierarchy(detection_method="none", detection_time_ms=0)


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------

async def detect_communities_async(session: Any) -> dict[int, list[str]]:
    """Async backward-compatible community detection."""
    hierarchy = await detect_communities_hierarchical_async(session)
    return hierarchy.flat_communities


async def detect_communities_hierarchical_async(
    session: Any,
    *,
    gamma: float = 1.0,
    max_levels: int = 3,
) -> CommunityHierarchy:
    """Async hierarchical community detection.

    Same cascade as sync: Leiden → Louvain → connected components.
    """
    start = time.monotonic()

    # Check GDS availability
    gds_ok = False
    try:
        result = await session.run("RETURN gds.version() AS version")
        record = await result.single()
        if record:
            gds_ok = True
    except Exception:
        pass

    if gds_ok:
        try:
            hierarchy = await _async_leiden_hierarchical(
                session, gamma=gamma, max_levels=max_levels,
            )
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            return hierarchy
        except Exception as exc:
            logger.warning("Async Leiden failed, trying Louvain: %s", exc)

        try:
            hierarchy = await _async_louvain(session)
            hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
            return hierarchy
        except Exception as exc:
            logger.warning("Async Louvain failed, trying components: %s", exc)

    try:
        hierarchy = await _async_connected_components(session)
        hierarchy.detection_time_ms = (time.monotonic() - start) * 1000
        return hierarchy
    except Exception as exc:
        logger.error("All async community detection methods failed: %s", exc)
        return CommunityHierarchy(detection_method="none", detection_time_ms=0)


async def _async_leiden_hierarchical(
    session: Any, *, gamma: float = 1.0, max_levels: int = 3,
) -> CommunityHierarchy:
    """Async Leiden hierarchical detection."""
    try:
        await session.run("CALL gds.graph.drop($name, false)", name=GRAPH_PROJECT_NAME)
    except Exception:
        pass

    await session.run(
        """
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
        """,
        name=GRAPH_PROJECT_NAME,
    )

    hierarchy = CommunityHierarchy(detection_method="leiden_hierarchical")
    all_entity_assignments: dict[int, dict[str, int]] = {}
    resolutions = [gamma * (2.0 ** i) for i in range(max_levels)]
    global_cid_offset = 0

    for level, resolution in enumerate(resolutions):
        try:
            result = await session.run(
                """
                CALL gds.leiden.stream($name, {gamma: $gamma})
                YIELD nodeId, communityId
                RETURN gds.util.asNode(nodeId).name AS entity, communityId
                """,
                name=GRAPH_PROJECT_NAME,
                gamma=resolution,
            )
        except Exception:
            break

        level_communities: dict[int, list[str]] = defaultdict(list)
        async for record in result:
            entity = record["entity"]
            cid = record["communityId"] + global_cid_offset
            level_communities[cid].append(entity)

        if not level_communities:
            break

        level_assignment: dict[str, int] = {}
        for cid, entities in level_communities.items():
            hierarchy.communities[cid] = Community(
                id=cid, level=level, entities=entities, size=len(entities),
            )
            for entity in entities:
                level_assignment[entity] = cid
                if level == 0:
                    hierarchy.entity_to_community[entity] = cid

        all_entity_assignments[level] = level_assignment
        global_cid_offset += max(level_communities.keys()) + 1

    # Wire parent/child
    for level in range(1, len(all_entity_assignments)):
        child_level = all_entity_assignments.get(level - 1, {})
        parent_level = all_entity_assignments.get(level, {})
        for entity, parent_cid in parent_level.items():
            child_cid = child_level.get(entity)
            if child_cid is not None:
                if child_cid in hierarchy.communities:
                    hierarchy.communities[child_cid].parent_id = parent_cid
                if parent_cid in hierarchy.communities:
                    if child_cid not in hierarchy.communities[parent_cid].children_ids:
                        hierarchy.communities[parent_cid].children_ids.append(child_cid)

    hierarchy.levels = len(all_entity_assignments)
    try:
        await session.run("CALL gds.graph.drop($name, false)", name=GRAPH_PROJECT_NAME)
    except Exception:
        pass
    return hierarchy


async def _async_louvain(session: Any) -> CommunityHierarchy:
    """Async Louvain fallback."""
    try:
        await session.run("CALL gds.graph.drop($name, false)", name=GRAPH_PROJECT_NAME)
    except Exception:
        pass

    await session.run(
        """
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
        """,
        name=GRAPH_PROJECT_NAME,
    )

    result = await session.run(
        """
        CALL gds.louvain.stream($name)
        YIELD nodeId, communityId
        RETURN gds.util.asNode(nodeId).name AS entity, communityId
        """,
        name=GRAPH_PROJECT_NAME,
    )

    communities: dict[int, list[str]] = defaultdict(list)
    entity_map: dict[str, int] = {}
    async for record in result:
        entity = record["entity"]
        cid = record["communityId"]
        communities[cid].append(entity)
        entity_map[entity] = cid

    try:
        await session.run("CALL gds.graph.drop($name, false)", name=GRAPH_PROJECT_NAME)
    except Exception:
        pass

    hierarchy = CommunityHierarchy(
        detection_method="louvain", levels=1, entity_to_community=entity_map,
    )
    for cid, entities in communities.items():
        hierarchy.communities[cid] = Community(
            id=cid, level=0, entities=entities, size=len(entities),
        )
    return hierarchy


async def _async_connected_components(session: Any) -> CommunityHierarchy:
    """Async connected components fallback (pure Cypher)."""
    result = await session.run(
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
        """
    )

    canonical_to_id: dict[str, int] = {}
    communities: dict[int, list[str]] = defaultdict(list)
    entity_map: dict[str, int] = {}
    next_id = 0

    async for record in result:
        entity = record["entity"]
        key = record["community_key"]
        if key not in canonical_to_id:
            canonical_to_id[key] = next_id
            next_id += 1
        cid = canonical_to_id[key]
        if entity not in entity_map:
            communities[cid].append(entity)
            entity_map[entity] = cid

    hierarchy = CommunityHierarchy(
        detection_method="connected_components",
        levels=1,
        entity_to_community=entity_map,
    )
    for cid, entities in communities.items():
        hierarchy.communities[cid] = Community(
            id=cid, level=0, entities=list(set(entities)), size=len(set(entities)),
        )
    return hierarchy
