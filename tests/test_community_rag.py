# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agentic_brain.rag.community import CommunityGraphRAG, CommunityLevel


class FakeDriver:
    def __init__(self):
        self.execute_query = AsyncMock(side_effect=self._execute_query)
        self.queries: list[str] = []

    async def _execute_query(self, query: str, **params):
        self.queries.append(query)
        if "gds.graph.exists" in query:
            return [{"exists": False}]
        if "gds.graph.project" in query:
            return [{"graphName": "knowledge_graph"}]
        if "gds.leiden.stream" in query:
            return [
                {"entity": "Alice", "communityId": 1},
                {"entity": "Bob", "communityId": 1},
                {"entity": "Neo4j", "communityId": 2},
            ]
        return []


class FakeLLM:
    async def summarize(self, prompt: str) -> str:
        assert "Members:" in prompt
        return "A collaboration-focused community."


@pytest.mark.asyncio
async def test_detect_communities_persists_leaf_communities():
    driver = FakeDriver()
    rag = CommunityGraphRAG(driver)

    communities = await rag.detect_communities()

    assert communities == {1: ["Alice", "Bob"], 2: ["Neo4j"]}
    assert any("MERGE (c:Community" in query for query in driver.queries)


@pytest.mark.asyncio
async def test_summaries_generated_and_stored():
    rag = CommunityGraphRAG(FakeDriver())
    rag._get_leaf_communities = AsyncMock(
        return_value=[
            CommunityLevel(community_id="1", level=1, members=["Alice", "Bob"]),
        ]
    )
    rag._store_summary = AsyncMock()

    summaries = await rag.summarize_communities(llm=FakeLLM())

    assert summaries == {"1": "A collaboration-focused community."}
    rag._store_summary.assert_awaited_once_with(
        "1", 1, "A collaboration-focused community."
    )


@pytest.mark.asyncio
async def test_query_routing_correct():
    rag = CommunityGraphRAG(FakeDriver())

    assert await rag.route_query("Summarize the overall themes across all communities") == "community"
    assert await rag.route_query("Who is Alice?") == "entity"
    assert await rag.route_query("How does Alice connect to Neo4j architecture") == "hybrid"


@pytest.mark.asyncio
async def test_hierarchy_built():
    rag = CommunityGraphRAG(FakeDriver())
    rag._get_leaf_communities = AsyncMock(
        return_value=[
            CommunityLevel(
                community_id="1",
                level=1,
                members=["Alice", "Bob"],
                summary="People and collaboration",
            ),
            CommunityLevel(
                community_id="2",
                level=1,
                members=["Neo4j", "Cypher"],
                summary="Graph database concepts",
            ),
            CommunityLevel(
                community_id="3",
                level=1,
                members=["Python", "AsyncIO"],
                summary="Runtime implementation details",
            ),
        ]
    )
    rag._persist_hierarchy_nodes = AsyncMock()

    hierarchy = await rag.build_hierarchy()

    assert set(hierarchy) == {0, 1, 2, 3}
    assert len(hierarchy[1]) == 3
    assert hierarchy[2]
    assert hierarchy[3][0]["community_id"] == "global"
    assert hierarchy[3][0]["child_ids"]
