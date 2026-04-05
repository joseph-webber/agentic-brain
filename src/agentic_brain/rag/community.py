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
- summarize each community for global reasoning
- build coarse-to-global hierarchy levels
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


class CommunityGraphRAG:
    """Community-centric GraphRAG orchestration for Neo4j-backed knowledge graphs."""

    def __init__(self, driver: Any):
        self.driver = driver
        self.detector = LeidenCommunityDetector() if LeidenCommunityDetector else None
        self._latest_hierarchy: CommunityHierarchy | None = None

    async def detect_communities(self) -> dict[int, list[str]]:
        """Run community detection and persist level-1 community nodes."""
        hierarchy = await self._detect_hierarchy()
        self._latest_hierarchy = hierarchy
        await self._persist_leaf_communities(hierarchy)
        return {
            community_id: list(community.entities)
            for community_id, community in hierarchy.communities.items()
            if community.level == 0
        }

    async def summarize_communities(self, llm: Any | None = None) -> dict[str, str]:
        """Generate and persist summaries for each detected leaf community."""
        communities = await self._get_leaf_communities()
        summaries: dict[str, str] = {}

        for community in communities:
            summary = await self._generate_summary(community.members, llm=llm)
            community.summary = summary
            summaries[community.community_id] = summary
            await self._store_summary(community.community_id, community.level, summary)

        return summaries

    async def build_hierarchy(self) -> dict[int, list[dict[str, Any]]]:
        """Build a four-level hierarchy for multi-scale community reasoning."""
        communities = await self._get_leaf_communities()
        if not communities:
            await self.detect_communities()
            communities = await self._get_leaf_communities()

        if not communities:
            return {0: [], 1: [], 2: [], 3: []}

        leaf_level = [community.to_dict() for community in communities]
        coarse_groups = await self._build_coarse_groups(communities)
        coarse_level = [group.to_dict() for group in coarse_groups]

        global_members = sorted({member for community in communities for member in community.members})
        global_theme = CommunityLevel(
            community_id="global",
            level=3,
            members=global_members,
            summary=self._fallback_summary(global_members, label="Global themes"),
            child_ids=[group.community_id for group in coarse_groups],
            metadata={"scale": "global"},
        )
        await self._persist_hierarchy_nodes(coarse_groups, global_theme)

        return {
            0: [{"entity_name": member} for member in global_members],
            1: leaf_level,
            2: coarse_level,
            3: [global_theme.to_dict()],
        }

    async def route_query(self, query: str) -> str:
        """Route a query to the appropriate GraphRAG scale."""
        normalized = query.strip().lower()
        if self._is_global_question(normalized):
            return "community"
        if self._is_local_question(normalized):
            return "entity"
        return "hybrid"

    async def query(self, query: str, top_k: int = 5) -> CommunityQueryResult:
        """Route and execute a community-aware query."""
        strategy = await self.route_query(query)
        if strategy == "community":
            return CommunityQueryResult(
                strategy=strategy,
                results=await self._search_community_summaries(query, top_k),
                hierarchy_level=2,
            )
        if strategy == "entity":
            return CommunityQueryResult(
                strategy=strategy,
                results=await self._search_entities(query, top_k),
                hierarchy_level=1,
            )
        return CommunityQueryResult(
            strategy=strategy,
            results=await self._hybrid_search(query, top_k),
            hierarchy_level=1,
        )

    async def _detect_hierarchy(self) -> CommunityHierarchy:
        if self._supports_native_community_detection():
            if await self._supports_async_queries():
                return await detect_communities_hierarchical_async(self.driver)
            return detect_communities_hierarchical(self.driver)
        return await self._detect_hierarchy_from_executor()

    def _supports_native_community_detection(self) -> bool:
        if hasattr(self.driver, "run"):
            return True
        session_factory = getattr(self.driver, "session", None)
        return callable(session_factory)

    async def _detect_hierarchy_from_executor(self) -> CommunityHierarchy:
        hierarchy = CommunityHierarchy(detection_method="leiden_stream", levels=1)
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
                    gamma: 1.0,
                    theta: 0.01
                })
                YIELD nodeId, communityId
                RETURN gds.util.asNode(nodeId).name AS entity, communityId
                """,
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
            communities[community_id].append(entity)
            hierarchy.entity_to_community[entity] = community_id

        for community_id, members in communities.items():
            hierarchy.communities[community_id] = Community(
                id=community_id,
                level=0,
                entities=sorted(set(members)),
            )

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
                    "detector": type(self.detector).__name__ if self.detector else "gds",
                },
            )
            for community in hierarchy.communities.values()
            if community.level == 0
        ]
        communities.sort(key=lambda community: (-community.member_count, community.community_id))
        return communities

    async def _persist_leaf_communities(self, hierarchy: CommunityHierarchy) -> None:
        payload = [
            {
                "community_id": str(community.id),
                "members": sorted(set(community.entities)),
                "member_count": len(set(community.entities)),
                "summary": community.summary,
                "level": 1,
                "metadata": {
                    "detection_method": hierarchy.detection_method,
                    "detector": type(self.detector).__name__ if self.detector else "gds",
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

    async def _build_coarse_groups(
        self, communities: list[CommunityLevel]
    ) -> list[CommunityLevel]:
        if len(communities) == 1:
            coarse = CommunityLevel(
                community_id="coarse_0",
                level=2,
                members=list(communities[0].members),
                summary=communities[0].summary or self._fallback_summary(communities[0].members),
                child_ids=[communities[0].community_id],
                metadata={"scale": "coarse"},
            )
            return [coarse]

        target_groups = max(1, math.ceil(math.sqrt(len(communities))))
        sorted_communities = sorted(
            communities, key=lambda community: (-community.member_count, community.community_id)
        )
        bucket_size = max(1, math.ceil(len(sorted_communities) / target_groups))
        groups: list[CommunityLevel] = []

        for index in range(0, len(sorted_communities), bucket_size):
            bucket = sorted_communities[index : index + bucket_size]
            members = sorted({member for community in bucket for member in community.members})
            summaries = [community.summary for community in bucket if community.summary]
            groups.append(
                CommunityLevel(
                    community_id=f"coarse_{len(groups)}",
                    level=2,
                    members=members,
                    summary=" ".join(summaries[:3]).strip()
                    or self._fallback_summary(members, label="Coarse community"),
                    child_ids=[community.community_id for community in bucket],
                    metadata={"scale": "coarse"},
                )
            )

        return groups

    async def _persist_hierarchy_nodes(
        self, coarse_groups: list[CommunityLevel], global_theme: CommunityLevel
    ) -> None:
        if coarse_groups:
            await self._execute_query(
                """
                UNWIND $groups AS community
                MERGE (c:Community {id: community.community_id, level: community.level})
                SET c.members = community.members,
                    c.memberCount = community.member_count,
                    c.summary = community.summary,
                    c.metadata = community.metadata,
                    c.updatedAt = datetime()
                WITH c, community
                UNWIND community.child_ids AS child_id
                MATCH (child:Community {id: child_id, level: 1})
                MERGE (c)-[:HAS_SUBCOMMUNITY]->(child)
                """,
                groups=[group.to_dict() for group in coarse_groups],
            )

        await self._execute_query(
            """
            MERGE (c:Community {id: $community_id, level: $level})
            SET c.members = $members,
                c.memberCount = $member_count,
                c.summary = $summary,
                c.metadata = $metadata,
                c.updatedAt = datetime()
            WITH c
            UNWIND $child_ids AS child_id
            MATCH (child:Community {id: child_id, level: 2})
            MERGE (c)-[:HAS_SUBCOMMUNITY]->(child)
            """,
            community_id=global_theme.community_id,
            level=global_theme.level,
            members=global_theme.members,
            member_count=global_theme.member_count,
            summary=global_theme.summary,
            metadata=global_theme.metadata,
            child_ids=global_theme.child_ids,
        )

    async def _search_community_summaries(
        self, query: str, top_k: int
    ) -> list[dict[str, Any]]:
        terms = self._query_terms(query)
        records = await self._execute_query(
            """
            MATCH (c:Community)
            WHERE c.summary IS NOT NULL AND c.summary <> ''
              AND any(term IN $terms WHERE
                  toLower(c.summary) CONTAINS term
                  OR any(member IN coalesce(c.members, []) WHERE toLower(member) CONTAINS term)
              )
            RETURN c.id AS community_id,
                   c.level AS level,
                   c.summary AS summary,
                   c.members AS members,
                   c.memberCount AS member_count
            ORDER BY c.level DESC, c.memberCount DESC
            LIMIT $top_k
            """,
            terms=terms,
            top_k=top_k,
        )
        results = []
        for record in records:
            score = self._term_overlap(
                terms,
                [record.get("summary", ""), *record.get("members", [])],
            )
            results.append(
                {
                    "community_id": record.get("community_id"),
                    "level": record.get("level"),
                    "content": record.get("summary"),
                    "summary": record.get("summary"),
                    "members": record.get("members", []),
                    "member_count": record.get("member_count", 0),
                    "score": float(score),
                    "strategy": "community",
                }
            )

        if results:
            results.sort(key=lambda result: (result["score"], result["member_count"]), reverse=True)
            return results[:top_k]

        communities = await self._get_leaf_communities()
        fallback = []
        for community in communities:
            score = self._term_overlap(terms, community.members)
            if score <= 0:
                continue
            fallback.append(
                {
                    "community_id": community.community_id,
                    "level": community.level,
                    "content": community.summary or self._fallback_summary(community.members),
                    "summary": community.summary or self._fallback_summary(community.members),
                    "members": community.members,
                    "member_count": community.member_count,
                    "score": float(score),
                    "strategy": "community",
                }
            )
        fallback.sort(key=lambda result: (result["score"], result["member_count"]), reverse=True)
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
                [
                    record.get("entity_name", ""),
                    record.get("content", ""),
                ],
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

    async def _hybrid_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Hybrid search combining community summaries and entities using unified RRF."""
        from .rrf import reciprocal_rank_fusion as rrf_unified, DEFAULT_K

        summary_results = await self._search_community_summaries(query, top_k)
        entity_results = await self._search_entities(query, top_k)

        # Prepare results for unified RRF
        summary_dicts = []
        for result in summary_results:
            result_id = f"community:{result['community_id']}"
            summary_dicts.append({
                "id": result_id,
                **result,
            })

        entity_dicts = []
        for i, result in enumerate(entity_results):
            result_id = (
                result.get("chunk_id")
                or result.get("result_id")
                or result.get("entity_name")
                or f"entity:{i}"
            )
            entity_dicts.append({
                "id": result_id,
                **result,
            })

        # Use unified RRF
        fused = rrf_unified(
            [
                {"source": "summaries", "results": summary_dicts},
                {"source": "entities", "results": entity_dicts},
            ],
            k=DEFAULT_K,
            top_k=top_k,
        )

        # Convert back and add strategy marker
        ranked = []
        for item in fused.items:
            item["strategy"] = "hybrid"
            # Combine original score with RRF score
            item["score"] = item.get("score", 0.0) + item["rrf_score"]
            ranked.append(item)

        return ranked

    async def _generate_summary(
        self, members: list[str], llm: Any | None = None
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
                    logger.warning("Community summary generation failed via %s: %s", method_name, exc)
        return self._fallback_summary(members)

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
            return [self._record_to_dict(record) for record in payload]

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
        return [term for term in re.findall(r"[a-z0-9_]+", query.lower()) if len(term) > 1]

    def _term_overlap(self, terms: list[str], texts: list[str]) -> int:
        haystack = " ".join(text.lower() for text in texts if text)
        return sum(1 for term in terms if term in haystack)

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

    def _fallback_summary(self, members: list[str], label: str = "Knowledge cluster") -> str:
        preview = ", ".join(members[:6])
        if len(members) > 6:
            preview = f"{preview}, and {len(members) - 6} more"
        return f"{label} containing {len(members)} related entities: {preview}."
