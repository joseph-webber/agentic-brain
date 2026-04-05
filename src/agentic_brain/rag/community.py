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

"""Community-aware GraphRAG helpers.

Implements Microsoft GraphRAG-style community workflows:
- detect communities on the ``Entity`` / ``RELATES_TO`` graph
- summarize each community for local, coarse, and global reasoning
- build multi-level hierarchy levels for dynamic retrieval
- route queries between community, entity, and hybrid retrieval
"""

from __future__ import annotations

import inspect
import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .community_detection import (
    Community,
    CommunityHierarchy,
    detect_communities_hierarchical,
    detect_communities_hierarchical_async,
)

try:  # pragma: no cover - optional dependency
    from neo4j_graphrag.community_detection import LeidenCommunityDetector
except ImportError:  # pragma: no cover - optional dependency
    LeidenCommunityDetector = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class CommunityLevel:
    """Serializable representation of a community at a given hierarchy level."""

    community_id: str
    level: int
    members: list[str] = field(default_factory=list)
    summary: str = ""
    child_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def member_count(self) -> int:
        return len(self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "community_id": self.community_id,
            "level": self.level,
            "members": list(self.members),
            "summary": self.summary,
            "child_ids": list(self.child_ids),
            "member_count": self.member_count,
            "metadata": dict(self.metadata),
        }


@dataclass
class CommunityQueryResult:
    """Query result for Community GraphRAG routing."""

    strategy: str
    results: list[dict[str, Any]]
    hierarchy_level: int
    query_complexity: float = 0.0


class CommunityGraphRAG:
    """Community-centric GraphRAG orchestration for Neo4j-backed knowledge graphs."""

    def __init__(
        self,
        driver: Any,
        *,
        enable_communities: bool = True,
        resolution: float = 1.0,
        max_hierarchy_levels: int = 4,
        n_iterations: int = 10,
        randomness: int | None = 42,
        resolution_multiplier: float = 2.0,
    ):
        self.driver = driver
        self.enable_communities = enable_communities
        self.resolution = resolution
        self.max_hierarchy_levels = max(1, max_hierarchy_levels)
        self.n_iterations = n_iterations
        self.randomness = randomness
        self.resolution_multiplier = resolution_multiplier
        self.detector = (
            LeidenCommunityDetector()
            if LeidenCommunityDetector and enable_communities
            else None
        )
        self._latest_hierarchy: CommunityHierarchy | None = None

    async def detect_communities(self) -> dict[int, list[str]]:
        """Run community detection and persist level-1 community nodes."""
        if not self.enable_communities:
            self._latest_hierarchy = CommunityHierarchy(
                detection_method="disabled",
                parameters={"enabled": False},
            )
            return {}

        hierarchy = await self._detect_hierarchy()
        self._latest_hierarchy = hierarchy
        await self._persist_leaf_communities(hierarchy)
        return {
            community_id: list(community.entities)
            for community_id, community in hierarchy.communities.items()
            if community.level == 0
        }

    async def summarize_communities(self, llm: Any | None = None) -> dict[str, str]:
        """Generate and persist summaries for all available hierarchy levels."""
        if not self.enable_communities:
            return {}

        hierarchy_levels = await self._compose_hierarchy_levels()
        summaries: dict[str, str] = {}
        for level, communities in hierarchy_levels.items():
            if level == 0:
                continue
            for community in communities:
                if not community.summary:
                    community.summary = await self._generate_summary(
                        community.members, llm=llm
                    )
                summaries[community.community_id] = community.summary
                await self._store_summary(
                    community.community_id, community.level, community.summary
                )
        return summaries

    async def build_hierarchy(self) -> dict[int, list[dict[str, Any]]]:
        """Build a multi-level hierarchy for multi-scale community reasoning."""
        if not self.enable_communities:
            return {0: []}

        hierarchy_levels = await self._compose_hierarchy_levels()
        await self._persist_hierarchy_nodes(hierarchy_levels)
        return {
            level: [community.to_dict() for community in communities]
            for level, communities in sorted(hierarchy_levels.items())
        }

    async def route_query(self, query: str) -> str:
        """Route a query to the appropriate GraphRAG scale."""
        normalized = query.strip().lower()
        if not self.enable_communities:
            return "entity" if self._is_local_question(normalized) else "hybrid"
        if self._is_global_question(normalized):
            return "community"
        if self._is_local_question(normalized):
            return "entity"
        return "hybrid"

    async def select_optimal_level(self, query: str) -> int:
        """Choose the best community level for the query's complexity."""
        if not self.enable_communities:
            return 0

        hierarchy_levels = await self._compose_hierarchy_levels()
        selectable_levels = sorted(
            level for level in hierarchy_levels if level > 0 and hierarchy_levels[level]
        )
        if not selectable_levels:
            return 0

        normalized = query.strip().lower()
        if self._is_global_question(normalized):
            return selectable_levels[-1]
        if self._is_local_question(normalized):
            return selectable_levels[0]

        complexity = self._estimate_query_complexity(normalized)
        index = min(
            len(selectable_levels) - 1,
            max(0, round(complexity * (len(selectable_levels) - 1))),
        )
        return selectable_levels[index]

    async def query(self, query: str, top_k: int = 5) -> CommunityQueryResult:
        """Route and execute a community-aware query."""
        strategy = await self.route_query(query)
        complexity = self._estimate_query_complexity(query)

        if strategy == "community":
            hierarchy_level = await self.select_optimal_level(query)
            return CommunityQueryResult(
                strategy=strategy,
                results=await self._search_community_summaries(
                    query, top_k, hierarchy_level=hierarchy_level
                ),
                hierarchy_level=hierarchy_level,
                query_complexity=complexity,
            )
        if strategy == "entity":
            return CommunityQueryResult(
                strategy=strategy,
                results=await self._search_entities(query, top_k),
                hierarchy_level=0,
                query_complexity=complexity,
            )

        hierarchy_level = await self.select_optimal_level(query)
        return CommunityQueryResult(
            strategy=strategy,
            results=await self._hybrid_search(
                query, top_k, hierarchy_level=hierarchy_level
            ),
            hierarchy_level=hierarchy_level if self.enable_communities else 0,
            query_complexity=complexity,
        )

    async def _detect_hierarchy(self) -> CommunityHierarchy:
        if not self.enable_communities:
            return CommunityHierarchy(
                detection_method="disabled",
                parameters={"enabled": False},
            )
        if self._supports_native_community_detection():
            if await self._supports_async_queries():
                return await detect_communities_hierarchical_async(
                    self.driver,
                    enabled=True,
                    resolution=self.resolution,
                    max_levels=self.max_hierarchy_levels,
                    n_iterations=self.n_iterations,
                    randomness=self.randomness,
                    resolution_multiplier=self.resolution_multiplier,
                )
            return detect_communities_hierarchical(
                self.driver,
                enabled=True,
                resolution=self.resolution,
                max_levels=self.max_hierarchy_levels,
                n_iterations=self.n_iterations,
                randomness=self.randomness,
                resolution_multiplier=self.resolution_multiplier,
            )
        return await self._detect_hierarchy_from_executor()

    def _supports_native_community_detection(self) -> bool:
        if hasattr(self.driver, "run"):
            return True
        session_factory = getattr(self.driver, "session", None)
        return callable(session_factory)

    async def _detect_hierarchy_from_executor(self) -> CommunityHierarchy:
        hierarchy = CommunityHierarchy(
            detection_method="leiden_stream",
            levels=1,
            parameters={
                "resolution": self.resolution,
                "max_levels": self.max_hierarchy_levels,
                "n_iterations": self.n_iterations,
                "randomness": self.randomness,
            },
        )
        try:
            exists_records = await self._execute_query(
                """
                CALL gds.graph.exists($graph_name)
                YIELD exists
                RETURN exists
                """,
                graph_name="knowledge_graph",
            )
            exists = bool(exists_records and exists_records[0].get("exists"))
            if not exists:
                await self._execute_query(
                    """
                    CALL gds.graph.project(
                        $graph_name,
                        ['Entity'],
                        ['RELATES_TO']
                    )
                    YIELD graphName
                    RETURN graphName
                    """,
                    graph_name="knowledge_graph",
                )

            records = await self._execute_query(
                """
                CALL gds.leiden.stream('knowledge_graph', {
                    gamma: $resolution,
                    maxIterations: $max_iterations,
                    randomSeed: $random_seed
                })
                YIELD nodeId, communityId
                RETURN gds.util.asNode(nodeId).name AS entity, communityId
                """,
                resolution=self.resolution,
                max_iterations=self.n_iterations,
                random_seed=self.randomness,
            )
        except Exception:
            records = await self._execute_query(
                """
                MATCH (e:Entity)
                WHERE e.communityId IS NOT NULL
                RETURN e.name AS entity, e.communityId AS communityId
                """,
            )

        communities: dict[int, list[str]] = defaultdict(list)
        for record in records:
            entity = record.get("entity")
            community_id = record.get("communityId")
            if entity is None or community_id is None:
                continue
            community_id = int(community_id)
            communities[community_id].append(str(entity))
            hierarchy.entity_to_community[str(entity)] = community_id

        for community_id, members in communities.items():
            hierarchy.communities[community_id] = Community(
                id=community_id,
                level=0,
                entities=sorted(set(members)),
                resolution=self.resolution,
                n_iterations=self.n_iterations,
                randomness=self.randomness,
            )
        hierarchy.levels = 1 if hierarchy.communities else 0
        return hierarchy

    async def _supports_async_queries(self) -> bool:
        run = getattr(self.driver, "run", None)
        if run is not None and inspect.iscoroutinefunction(run):
            return True

        session_factory = getattr(self.driver, "session", None)
        if callable(session_factory):
            session_manager = session_factory()
            return hasattr(session_manager, "__aenter__")

        execute_query = getattr(self.driver, "execute_query", None)
        return inspect.iscoroutinefunction(execute_query)

    async def _get_leaf_communities(self) -> list[CommunityLevel]:
        if not self.enable_communities:
            return []

        hierarchy = self._latest_hierarchy or await self._detect_hierarchy()
        self._latest_hierarchy = hierarchy
        communities = [
            CommunityLevel(
                community_id=str(community.id),
                level=1,
                members=sorted(set(community.entities)),
                summary=community.summary,
                child_ids=[],
                metadata={
                    "detection_method": hierarchy.detection_method,
                    "detector": (
                        type(self.detector).__name__ if self.detector else "gds"
                    ),
                    "modularity": community.modularity_score,
                    "coverage": community.coverage_score,
                    "cohesion": community.cohesion_score,
                    "resolution": community.resolution,
                },
            )
            for community in hierarchy.communities.values()
            if community.level == 0
        ]
        for community in communities:
            if not community.summary:
                community.summary = self._fallback_summary(community.members)
        communities.sort(
            key=lambda community: (-community.member_count, community.community_id)
        )
        return communities

    async def _compose_hierarchy_levels(self) -> dict[int, list[CommunityLevel]]:
        if not self.enable_communities:
            return {0: []}

        leaf_communities = await self._get_leaf_communities()
        if not leaf_communities:
            if self._latest_hierarchy is None:
                await self.detect_communities()
                leaf_communities = await self._get_leaf_communities()
            if not leaf_communities:
                return {0: []}

        hierarchy_levels: dict[int, list[CommunityLevel]] = {
            0: [
                CommunityLevel(
                    community_id=f"entity::{member}",
                    level=0,
                    members=[member],
                    summary=member,
                    metadata={"kind": "entity"},
                )
                for member in sorted(
                    {
                        member
                        for community in leaf_communities
                        for member in community.members
                    }
                )
            ],
            1: leaf_communities,
        }

        target_levels = max(4, self.max_hierarchy_levels)
        current_level = 2
        current_groups = leaf_communities

        while current_level < target_levels and len(current_groups) > 1:
            current_groups = await self._group_communities(
                current_groups, level=current_level
            )
            hierarchy_levels[current_level] = current_groups
            current_level += 1

        global_level = max(current_level, 2)
        if len(current_groups) == 1:
            base = current_groups[0]
            global_members = list(base.members)
            global_summary = base.summary or self._fallback_summary(
                global_members, label="Global themes"
            )
            child_ids = list(base.child_ids) or [base.community_id]
        else:
            global_members = sorted(
                {member for community in current_groups for member in community.members}
            )
            global_summary = self._combine_summaries(
                [community.summary for community in current_groups],
                global_members,
                label="Global themes",
            )
            child_ids = [community.community_id for community in current_groups]

        hierarchy_levels[global_level] = [
            CommunityLevel(
                community_id="global",
                level=global_level,
                members=global_members,
                summary=global_summary,
                child_ids=child_ids,
                metadata={
                    "scale": "global",
                    "query_complexity_bias": 1.0,
                },
            )
        ]
        return hierarchy_levels

    async def _persist_leaf_communities(self, hierarchy: CommunityHierarchy) -> None:
        if not self.enable_communities:
            return

        payload = [
            {
                "community_id": str(community.id),
                "members": sorted(set(community.entities)),
                "member_count": len(set(community.entities)),
                "summary": community.summary
                or self._fallback_summary(community.entities),
                "level": 1,
                "metadata": {
                    "detection_method": hierarchy.detection_method,
                    "detector": (
                        type(self.detector).__name__ if self.detector else "gds"
                    ),
                    "modularity": community.modularity_score,
                    "coverage": community.coverage_score,
                    "cohesion": community.cohesion_score,
                    "resolution": community.resolution,
                },
            }
            for community in hierarchy.communities.values()
            if community.level == 0
        ]
        if not payload:
            return

        await self._execute_query(
            """
            UNWIND $communities AS community
            MERGE (c:Community {id: community.community_id, level: community.level})
            SET c.members = community.members,
                c.memberCount = community.member_count,
                c.summary = coalesce(community.summary, c.summary, ''),
                c.metadata = community.metadata,
                c.updatedAt = datetime()
            WITH c, community
            UNWIND community.members AS member_name
            MATCH (e:Entity {name: member_name})
            SET e.communityId = community.community_id
            MERGE (e)-[:IN_COMMUNITY {level: community.level}]->(c)
            """,
            communities=payload,
        )

    async def _store_summary(self, community_id: str, level: int, summary: str) -> None:
        if not self.enable_communities:
            return
        await self._execute_query(
            """
            MERGE (c:Community {id: $community_id, level: $level})
            SET c.summary = $summary,
                c.updatedAt = datetime()
            """,
            community_id=community_id,
            level=level,
            summary=summary,
        )

    async def _group_communities(
        self,
        communities: list[CommunityLevel],
        *,
        level: int,
    ) -> list[CommunityLevel]:
        if not communities:
            return []
        if len(communities) == 1:
            community = communities[0]
            return [
                CommunityLevel(
                    community_id=f"level_{level}_0",
                    level=level,
                    members=list(community.members),
                    summary=community.summary,
                    child_ids=[community.community_id],
                    metadata=self._merge_metadata([community.metadata], level=level),
                )
            ]

        target_groups = max(1, math.ceil(math.sqrt(len(communities))))
        sorted_communities = sorted(
            communities,
            key=lambda community: (-community.member_count, community.community_id),
        )
        bucket_size = max(1, math.ceil(len(sorted_communities) / target_groups))
        grouped: list[CommunityLevel] = []

        for index in range(0, len(sorted_communities), bucket_size):
            bucket = sorted_communities[index : index + bucket_size]
            members = sorted(
                {member for community in bucket for member in community.members}
            )
            summary = self._combine_summaries(
                [community.summary for community in bucket],
                members,
                label=f"Community level {level}",
            )
            grouped.append(
                CommunityLevel(
                    community_id=f"level_{level}_{len(grouped)}",
                    level=level,
                    members=members,
                    summary=summary,
                    child_ids=[community.community_id for community in bucket],
                    metadata=self._merge_metadata(
                        [community.metadata for community in bucket], level=level
                    ),
                )
            )
        return grouped

    async def _persist_hierarchy_nodes(
        self, hierarchy_levels: dict[int, list[CommunityLevel]]
    ) -> None:
        if not self.enable_communities:
            return
        payload = [
            community.to_dict()
            for level, communities in hierarchy_levels.items()
            if level >= 2
            for community in communities
        ]
        if not payload:
            return

        await self._execute_query(
            """
            UNWIND $communities AS community
            MERGE (c:Community {id: community.community_id, level: community.level})
            SET c.members = community.members,
                c.memberCount = community.member_count,
                c.summary = community.summary,
                c.metadata = community.metadata,
                c.updatedAt = datetime()
            WITH c, community
            UNWIND community.child_ids AS child_id
            MATCH (child:Community {id: child_id})
            MERGE (c)-[:HAS_SUBCOMMUNITY]->(child)
            """,
            communities=payload,
        )

    async def _search_community_summaries(
        self,
        query: str,
        top_k: int,
        *,
        hierarchy_level: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enable_communities:
            return []

        terms = self._query_terms(query)
        if not terms:
            return []

        level_filter = "AND c.level = $level" if hierarchy_level is not None else ""
        params: dict[str, Any] = {"terms": terms, "top_k": top_k}
        if hierarchy_level is not None:
            params["level"] = hierarchy_level

        records = await self._execute_query(
            f"""
            MATCH (c:Community)
            WHERE c.summary IS NOT NULL AND c.summary <> ''
              {level_filter}
              AND any(term IN $terms WHERE
                  toLower(c.summary) CONTAINS term
                  OR any(member IN coalesce(c.members, []) WHERE toLower(member) CONTAINS term)
              )
            RETURN c.id AS community_id,
                   c.level AS level,
                   c.summary AS summary,
                   c.members AS members,
                   c.memberCount AS member_count,
                   c.metadata AS metadata
            ORDER BY c.level DESC, c.memberCount DESC
            LIMIT $top_k
            """,
            **params,
        )
        results = self._rank_community_records(records, terms)
        if results:
            return results[:top_k]

        hierarchy_levels = await self._compose_hierarchy_levels()
        candidate_levels = (
            [hierarchy_level]
            if hierarchy_level is not None
            else sorted(hierarchy_levels)
        )
        fallback: list[dict[str, Any]] = []
        for level in candidate_levels:
            for community in hierarchy_levels.get(level, []):
                if level == 0:
                    continue
                score = self._term_overlap(
                    terms, [community.summary, *community.members]
                )
                if score <= 0:
                    continue
                fallback.append(
                    {
                        "community_id": community.community_id,
                        "level": community.level,
                        "content": community.summary,
                        "summary": community.summary,
                        "members": community.members,
                        "member_count": community.member_count,
                        "metadata": community.metadata,
                        "score": float(score),
                        "strategy": "community",
                    }
                )
        fallback.sort(
            key=lambda result: (
                result["score"],
                result["member_count"],
                result["level"],
            ),
            reverse=True,
        )
        return fallback[:top_k]

    async def _search_entities(self, query: str, top_k: int) -> list[dict[str, Any]]:
        terms = self._query_terms(query)
        records = await self._execute_query(
            """
            MATCH (e:Entity)
            WHERE any(term IN $terms WHERE
                toLower(coalesce(e.name, '')) CONTAINS term
                OR toLower(coalesce(e.description, '')) CONTAINS term
            )
            OPTIONAL MATCH (e)<-[:MENTIONS]-(c:Chunk)<-[:CONTAINS]-(d:Document)
            RETURN coalesce(c.id, e.id, e.name) AS result_id,
                   c.id AS chunk_id,
                   coalesce(c.content, c.text, e.description, e.name) AS content,
                   c.position AS position,
                   d.id AS doc_id,
                   d.metadata AS metadata,
                   e.name AS entity_name,
                   e.type AS entity_type,
                   e.communityId AS community_id,
                   coalesce(e.mention_count, 0) AS mention_count
            LIMIT $top_k
            """,
            terms=terms,
            top_k=top_k,
        )

        results = []
        for record in records:
            score = self._term_overlap(
                terms,
                [record.get("entity_name", ""), record.get("content", "")],
            )
            results.append(
                {
                    "result_id": record.get("result_id"),
                    "chunk_id": record.get("chunk_id"),
                    "content": record.get("content"),
                    "position": record.get("position"),
                    "doc_id": record.get("doc_id"),
                    "metadata": record.get("metadata"),
                    "entity_name": record.get("entity_name"),
                    "entity_type": record.get("entity_type"),
                    "community_id": record.get("community_id"),
                    "score": float(score or record.get("mention_count", 0)),
                    "strategy": "entity",
                }
            )
        results.sort(key=lambda result: result["score"], reverse=True)
        return results[:top_k]

    async def _hybrid_search(
        self,
        query: str,
        top_k: int,
        *,
        hierarchy_level: int | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining community summaries and entities using unified RRF."""
        from .rrf import DEFAULT_K, reciprocal_rank_fusion as rrf_unified

        summary_results = (
            await self._search_community_summaries(
                query, top_k, hierarchy_level=hierarchy_level
            )
            if self.enable_communities
            else []
        )
        entity_results = await self._search_entities(query, top_k)
        if not summary_results:
            return entity_results[:top_k]

        summary_dicts = [
            {
                "id": f"community:{result['community_id']}",
                **result,
            }
            for result in summary_results
        ]
        entity_dicts = []
        for index, result in enumerate(entity_results):
            result_id = (
                result.get("chunk_id")
                or result.get("result_id")
                or result.get("entity_name")
                or f"entity:{index}"
            )
            entity_dicts.append({"id": result_id, **result})

        fused = rrf_unified(
            [
                {"source": "summaries", "results": summary_dicts},
                {"source": "entities", "results": entity_dicts},
            ],
            k=DEFAULT_K,
            top_k=top_k,
        )

        ranked = []
        for item in fused.items:
            item["strategy"] = "hybrid"
            item["score"] = item.get("score", 0.0) + item["rrf_score"]
            ranked.append(item)
        return ranked

    async def _generate_summary(
        self,
        members: list[str],
        llm: Any | None = None,
    ) -> str:
        if not members:
            return ""

        prompt = (
            "Summarize this knowledge cluster in 2 short sentences. "
            "Focus on the shared theme and notable entities.\n"
            f"Members: {', '.join(members[:25])}"
        )
        if llm is not None:
            for method_name in ("summarize", "generate", "chat"):
                method = getattr(llm, method_name, None)
                if method is None:
                    continue
                try:
                    response = method(prompt)
                    if inspect.isawaitable(response):
                        response = await response
                    if hasattr(response, "content"):
                        response = response.content
                    text = str(response).strip()
                    if text:
                        return text
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning(
                        "Community summary generation failed via %s: %s",
                        method_name,
                        exc,
                    )
        return self._fallback_summary(members)

    async def _query_level(
        self, query: str, level: int, top_k: int = 5
    ) -> list[dict[str, Any]]:
        return await self._search_community_summaries(
            query, top_k, hierarchy_level=level
        )

    async def _resolve_entity(self, entity_name: str) -> dict[str, Any]:
        records = await self._execute_query(
            """
            MATCH (e:Entity)
            WHERE toLower(coalesce(e.name, '')) = toLower($entity_name)
            OPTIONAL MATCH (e)-[:IN_COMMUNITY]->(c:Community)
            RETURN e.name AS canonical_id,
                   collect(DISTINCT c.id) AS communities,
                   collect(DISTINCT coalesce(e.aliases, [])) AS aliases
            LIMIT 1
            """,
            entity_name=entity_name,
        )
        if not records:
            return {
                "canonical_id": entity_name,
                "communities": [],
                "aliases": [],
            }
        record = records[0]
        aliases = record.get("aliases", []) or []
        flattened_aliases = []
        for alias_group in aliases:
            if isinstance(alias_group, list):
                flattened_aliases.extend(alias_group)
            elif alias_group:
                flattened_aliases.append(alias_group)
        return {
            "canonical_id": record.get("canonical_id", entity_name),
            "communities": [
                community
                for community in record.get("communities", [])
                if community is not None
            ],
            "aliases": flattened_aliases,
        }

    async def _execute_query(self, query: str, **params: Any) -> list[dict[str, Any]]:
        execute_query = getattr(self.driver, "execute_query", None)
        if callable(execute_query):
            result = execute_query(query, **params)
            if inspect.isawaitable(result):
                result = await result
            return await self._normalize_records(result)

        run = getattr(self.driver, "run", None)
        if callable(run):
            result = run(query, **params)
            if inspect.isawaitable(result):
                result = await result
            return await self._normalize_records(result)

        session_factory = getattr(self.driver, "session", None)
        if callable(session_factory):
            session_manager = session_factory()
            if hasattr(session_manager, "__aenter__"):
                async with session_manager as session:
                    result = session.run(query, **params)
                    if inspect.isawaitable(result):
                        result = await result
                    return await self._normalize_records(result)
            if hasattr(session_manager, "__enter__"):
                with session_manager as session:
                    result = session.run(query, **params)
                    if inspect.isawaitable(result):
                        result = await result
                    return await self._normalize_records(result)

        raise TypeError("Unsupported driver/session object for CommunityGraphRAG")

    async def _normalize_records(self, result: Any) -> list[dict[str, Any]]:
        if result is None:
            return []
        if isinstance(result, tuple):
            result = result[0]
        if isinstance(result, list):
            return [self._record_to_dict(record) for record in result]

        data = getattr(result, "data", None)
        if callable(data):
            payload = data()
            if inspect.isawaitable(payload):
                payload = await payload
            if isinstance(payload, list):
                return [self._record_to_dict(record) for record in payload]
            if isinstance(payload, dict):
                return [payload]

        if hasattr(result, "__aiter__"):
            records = []
            async for record in result:
                records.append(self._record_to_dict(record))
            return records

        if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
            return [self._record_to_dict(record) for record in result]
        return [self._record_to_dict(result)]

    def _record_to_dict(self, record: Any) -> dict[str, Any]:
        if isinstance(record, dict):
            return dict(record)
        record_data = getattr(record, "data", None)
        if callable(record_data):
            try:
                payload = record_data()
                if isinstance(payload, dict):
                    return payload
            except Exception:  # pragma: no cover - defensive
                pass
        try:
            return dict(record)
        except Exception:  # pragma: no cover - defensive
            return {"value": record}

    def _query_terms(self, query: str) -> list[str]:
        return [
            term for term in re.findall(r"[a-z0-9_]+", query.lower()) if len(term) > 1
        ]

    def _term_overlap(self, terms: list[str], texts: list[str]) -> int:
        haystack = " ".join(text.lower() for text in texts if text)
        return sum(1 for term in terms if term in haystack)

    def _estimate_query_complexity(self, query: str) -> float:
        terms = self._query_terms(query)
        if not terms:
            return 0.0
        complexity = min(len(terms) / 12.0, 1.0)
        reasoning_markers = {
            "across",
            "compare",
            "contrast",
            "relationship",
            "relationships",
            "connect",
            "connections",
            "why",
            "how",
            "impact",
            "pattern",
            "patterns",
            "summarize",
            "overall",
            "themes",
        }
        complexity += min(
            0.4, 0.1 * sum(1 for term in terms if term in reasoning_markers)
        )
        if self._is_global_question(query.lower()):
            complexity += 0.3
        return min(complexity, 1.0)

    def _merge_metadata(
        self, metadata_items: list[dict[str, Any]], *, level: int
    ) -> dict[str, Any]:
        values: dict[str, list[float]] = defaultdict(list)
        for item in metadata_items:
            for key in ("modularity", "coverage", "cohesion"):
                value = item.get(key) if isinstance(item, dict) else None
                if isinstance(value, (int, float)):
                    values[key].append(float(value))
        return {
            "level": level,
            "modularity": sum(values.get("modularity", [0.0]))
            / max(len(values.get("modularity", [])), 1),
            "coverage": sum(values.get("coverage", [0.0]))
            / max(len(values.get("coverage", [])), 1),
            "cohesion": sum(values.get("cohesion", [0.0]))
            / max(len(values.get("cohesion", [])), 1),
        }

    def _combine_summaries(
        self, summaries: list[str], members: list[str], *, label: str
    ) -> str:
        usable_summaries = [
            summary.strip() for summary in summaries if summary and summary.strip()
        ]
        if usable_summaries:
            return " ".join(usable_summaries[:3]).strip()
        return self._fallback_summary(members, label=label)

    def _rank_community_records(
        self,
        records: list[dict[str, Any]],
        terms: list[str],
    ) -> list[dict[str, Any]]:
        results = []
        for record in records:
            members = record.get("members", []) or []
            member_count = record.get("member_count", len(members)) or 0
            score = self._term_overlap(terms, [record.get("summary", ""), *members])
            results.append(
                {
                    "community_id": record.get("community_id"),
                    "level": record.get("level", 0),
                    "content": record.get("summary"),
                    "summary": record.get("summary"),
                    "members": members,
                    "member_count": member_count,
                    "metadata": record.get("metadata", {}),
                    "score": float(score),
                    "strategy": "community",
                }
            )
        results.sort(
            key=lambda result: (
                result["score"],
                result["member_count"],
                result["level"],
            ),
            reverse=True,
        )
        return results

    def _is_global_question(self, query: str) -> bool:
        indicators = (
            "overall",
            "global",
            "summary",
            "summarize",
            "themes",
            "theme",
            "high level",
            "big picture",
            "across",
            "all communities",
            "what are the main",
        )
        return any(indicator in query for indicator in indicators)

    def _is_local_question(self, query: str) -> bool:
        indicators = (
            "who is",
            "what is",
            "where is",
            "tell me about",
            "details",
            "specific",
            "entity",
            "document",
            "chunk",
        )
        if any(indicator in query for indicator in indicators):
            return True
        return len(self._query_terms(query)) <= 3 and query.endswith("?")

    def _fallback_summary(
        self, members: list[str], label: str = "Knowledge cluster"
    ) -> str:
        preview = ", ".join(members[:6])
        if len(members) > 6:
            preview = f"{preview}, and {len(members) - 6} more"
        return f"{label} containing {len(members)} related entities: {preview}."
