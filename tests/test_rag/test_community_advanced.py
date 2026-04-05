# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[2] / "src" / "agentic_brain" / "rag"


class FakeResult:
    def __init__(
        self, records: list[dict] | None = None, single_record: dict | None = None
    ):
        self.records = records or []
        self.single_record = (
            single_record
            if single_record is not None
            else (self.records[0] if self.records else None)
        )

    def __iter__(self):
        return iter(self.records)

    def single(self):
        return self.single_record

    def data(self):
        return self.records


class SyncSession:
    def __init__(
        self,
        *,
        leiden_by_gamma: dict[float, list[dict]] | None = None,
        louvain_records: list[dict] | Exception | None = None,
        component_records: list[dict] | None = None,
        edge_records: list[dict] | None = None,
        entity_detail_records: list[dict] | None = None,
        gds_available: bool = True,
    ):
        self.leiden_by_gamma = leiden_by_gamma or {}
        self.louvain_records = louvain_records or []
        self.component_records = component_records or []
        self.edge_records = edge_records or []
        self.entity_detail_records = entity_detail_records or []
        self.gds_available = gds_available
        self.calls: list[tuple[str, dict]] = []

    def run(self, query: str, **params):
        self.calls.append((query, params))
        if "RETURN gds.version() AS version" in query:
            if not self.gds_available:
                raise RuntimeError("gds unavailable")
            return FakeResult([{"version": "2.5.0"}], {"version": "2.5.0"})
        if "gds.graph.drop" in query or "gds.graph.project" in query:
            return FakeResult([])
        if "CALL gds.leiden.stream" in query:
            records = self.leiden_by_gamma.get(params.get("gamma"), [])
            if isinstance(records, Exception):
                raise records
            return FakeResult(records)
        if "CALL gds.louvain.stream" in query:
            if isinstance(self.louvain_records, Exception):
                raise self.louvain_records
            return FakeResult(self.louvain_records)
        if "RETURN source.name AS source" in query:
            return FakeResult(self.edge_records)
        if "RETURN e.name AS name, e.type AS type" in query:
            return FakeResult(self.entity_detail_records)
        if "community_key" in query:
            return FakeResult(self.component_records)
        return FakeResult([])


class AsyncSession(SyncSession):
    async def run(self, query: str, **params):
        return super().run(query, **params)


class AsyncDriver:
    def __init__(self, responses: dict[str, list[dict]] | None = None):
        self.responses = responses or {}
        self.queries: list[tuple[str, dict]] = []

    async def execute_query(self, query: str, **params):
        self.queries.append((query, params))
        for marker, payload in self.responses.items():
            if marker in query:
                return payload
        return []


@pytest.fixture(scope="module")
def modules():
    for name in [
        "agentic_brain.rag.community_detection",
        "agentic_brain.rag.community",
        "agentic_brain.rag",
        "agentic_brain",
    ]:
        sys.modules.pop(name, None)

    agentic_brain_pkg = types.ModuleType("agentic_brain")
    agentic_brain_pkg.__path__ = [str(BASE_DIR.parent)]
    rag_pkg = types.ModuleType("agentic_brain.rag")
    rag_pkg.__path__ = [str(BASE_DIR)]
    sys.modules["agentic_brain"] = agentic_brain_pkg
    sys.modules["agentic_brain.rag"] = rag_pkg

    detection_spec = importlib.util.spec_from_file_location(
        "agentic_brain.rag.community_detection",
        BASE_DIR / "community_detection.py",
    )
    detection = importlib.util.module_from_spec(detection_spec)
    sys.modules[detection_spec.name] = detection
    assert detection_spec.loader is not None
    detection_spec.loader.exec_module(detection)

    community_spec = importlib.util.spec_from_file_location(
        "agentic_brain.rag.community",
        BASE_DIR / "community.py",
    )
    community = importlib.util.module_from_spec(community_spec)
    sys.modules[community_spec.name] = community
    assert community_spec.loader is not None
    community_spec.loader.exec_module(community)

    return types.SimpleNamespace(detection=detection, community=community)


def make_sample_hierarchy(modules):
    hierarchy = modules.detection.CommunityHierarchy(
        levels=3, detection_method="leiden_hierarchical"
    )
    hierarchy.communities[1] = modules.detection.Community(
        id=1, level=0, entities=["alice", "bob"], summary="People cluster"
    )
    hierarchy.communities[2] = modules.detection.Community(
        id=2, level=0, entities=["neo4j", "cypher"], summary="Graph cluster"
    )
    hierarchy.communities[3] = modules.detection.Community(
        id=3, level=1, entities=["alice", "bob", "neo4j", "cypher"], children_ids=[1, 2]
    )
    hierarchy.communities[4] = modules.detection.Community(
        id=4, level=2, entities=["alice", "bob", "neo4j", "cypher"], children_ids=[3]
    )
    hierarchy.communities[1].parent_id = 3
    hierarchy.communities[2].parent_id = 3
    hierarchy.communities[3].parent_id = 4
    hierarchy.entity_to_community = {"alice": 1, "bob": 1, "neo4j": 2, "cypher": 2}
    hierarchy.level_metrics = {
        0: {"modularity": 0.3, "coverage": 0.5, "cohesion": 0.7},
        1: {"modularity": 0.2, "coverage": 0.6, "cohesion": 0.8},
        2: {"modularity": 0.1, "coverage": 0.9, "cohesion": 1.0},
    }
    return hierarchy


def make_leaf_levels(modules, count: int = 9):
    return [
        modules.community.CommunityLevel(
            community_id=f"leaf_{index}",
            level=1,
            members=[f"entity_{index}", f"topic_{index}"],
            summary=f"Summary {index}",
            metadata={
                "modularity": 0.5 + index / 100,
                "coverage": 0.4 + index / 100,
                "cohesion": 0.6 + index / 100,
            },
        )
        for index in range(count)
    ]


class StubLLM:
    def generate(self, prompt: str, max_tokens: int = 150):
        assert "Metrics:" in prompt or "Entities:" in prompt
        return "LLM generated summary"


class TestCommunityDetectionAdvanced:
    def test_community_defaults_include_advanced_fields(self, modules):
        community = modules.detection.Community(id=1, level=0)
        assert community.coverage_score == 0.0
        assert community.cohesion_score == 0.0
        assert community.resolution is None
        assert community.randomness is None

    def test_hierarchy_max_level_property(self, modules):
        hierarchy = make_sample_hierarchy(modules)
        assert hierarchy.max_level == 2

    def test_resolution_schedule_supports_four_levels(self, modules):
        schedule = modules.detection._build_resolution_schedule(1.0, 4, 2.0)
        assert schedule == [8.0, 4.0, 2.0, 1.0]

    def test_leiden_uses_resolution_iterations_and_randomness(self, modules):
        session = SyncSession(
            leiden_by_gamma={8.0: [{"entity": "a", "communityId": 1}]},
            edge_records=[],
        )
        modules.detection._detect_leiden_hierarchical(
            session,
            resolution=1.0,
            max_levels=1,
            n_iterations=7,
            randomness=123,
        )
        leiden_calls = [
            call for call in session.calls if "CALL gds.leiden.stream" in call[0]
        ]
        assert leiden_calls[0][1]["max_iterations"] == 7
        assert leiden_calls[0][1]["random_seed"] == 123
        assert leiden_calls[0][1]["gamma"] == 1.0

    def test_leiden_supports_four_plus_levels(self, modules):
        session = SyncSession(
            leiden_by_gamma={
                8.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 2},
                    {"entity": "c", "communityId": 3},
                    {"entity": "d", "communityId": 4},
                ],
                4.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 1},
                    {"entity": "c", "communityId": 2},
                    {"entity": "d", "communityId": 2},
                ],
                2.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 1},
                    {"entity": "c", "communityId": 1},
                    {"entity": "d", "communityId": 2},
                ],
                1.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 1},
                    {"entity": "c", "communityId": 1},
                    {"entity": "d", "communityId": 1},
                ],
            },
            edge_records=[
                {"source": "a", "target": "b"},
                {"source": "c", "target": "d"},
            ],
        )
        hierarchy = modules.detection._detect_leiden_hierarchical(
            session, resolution=1.0, max_levels=4
        )
        assert hierarchy.levels == 4
        assert len(hierarchy.level_metrics) == 4

    def test_leiden_skips_duplicate_partitions(self, modules):
        shared_partition = [
            {"entity": "a", "communityId": 1},
            {"entity": "b", "communityId": 1},
        ]
        session = SyncSession(
            leiden_by_gamma={
                8.0: shared_partition,
                4.0: shared_partition,
                2.0: shared_partition,
            },
            edge_records=[],
        )
        hierarchy = modules.detection._detect_leiden_hierarchical(
            session, resolution=2.0, max_levels=3
        )
        assert hierarchy.levels == 1

    def test_leiden_wires_parent_child_relationships(self, modules):
        session = SyncSession(
            leiden_by_gamma={
                2.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 2},
                ],
                1.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 1},
                ],
            },
            edge_records=[],
        )
        hierarchy = modules.detection._detect_leiden_hierarchical(
            session, resolution=1.0, max_levels=2
        )
        leaf_nodes = hierarchy.communities_at_level(0)
        parent_nodes = hierarchy.communities_at_level(1)
        assert len(parent_nodes[0].children_ids) == 2
        assert all(
            community.parent_id == parent_nodes[0].id for community in leaf_nodes
        )

    def test_leiden_entity_mapping_uses_leaf_level(self, modules):
        session = SyncSession(
            leiden_by_gamma={
                1.0: [
                    {"entity": "a", "communityId": 7},
                    {"entity": "b", "communityId": 7},
                ]
            },
            edge_records=[],
        )
        hierarchy = modules.detection._detect_leiden_hierarchical(
            session, resolution=1.0, max_levels=1
        )
        leaf = hierarchy.get_entity_community("a")
        assert leaf is not None
        assert "a" in leaf.entities

    def test_leiden_level_metrics_include_modularity_coverage_cohesion(self, modules):
        session = SyncSession(
            leiden_by_gamma={
                1.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 1},
                ]
            },
            edge_records=[{"source": "a", "target": "b"}],
        )
        hierarchy = modules.detection._detect_leiden_hierarchical(
            session, resolution=1.0, max_levels=1
        )
        assert set(hierarchy.level_metrics[0]) >= {"modularity", "coverage", "cohesion"}

    def test_leiden_community_metrics_are_calculated(self, modules):
        session = SyncSession(
            leiden_by_gamma={
                1.0: [
                    {"entity": "a", "communityId": 1},
                    {"entity": "b", "communityId": 1},
                ]
            },
            edge_records=[{"source": "a", "target": "b"}],
        )
        hierarchy = modules.detection._detect_leiden_hierarchical(
            session, resolution=1.0, max_levels=1
        )
        community = next(iter(hierarchy.communities.values()))
        assert community.cohesion_score == pytest.approx(1.0)
        assert community.coverage_score == pytest.approx(1.0)

    def test_resolution_override_takes_precedence(self, modules):
        session = SyncSession(
            leiden_by_gamma={3.0: [{"entity": "a", "communityId": 1}]}, edge_records=[]
        )
        modules.detection._detect_leiden_hierarchical(
            session, gamma=1.0, resolution=3.0, max_levels=1
        )
        leiden_call = [
            call for call in session.calls if "CALL gds.leiden.stream" in call[0]
        ][0]
        assert leiden_call[1]["gamma"] == 3.0

    def test_detect_hierarchical_can_be_disabled(self, modules):
        hierarchy = modules.detection.detect_communities_hierarchical(
            object(), enabled=False
        )
        assert hierarchy.detection_method == "disabled"
        assert hierarchy.communities == {}

    def test_detect_hierarchical_falls_back_to_louvain(self, modules):
        session = SyncSession(
            leiden_by_gamma={8.0: RuntimeError("leiden failed")},
            louvain_records=[
                {"entity": "a", "communityId": 1},
                {"entity": "b", "communityId": 1},
            ],
            edge_records=[],
        )
        hierarchy = modules.detection.detect_communities_hierarchical(
            session, resolution=8.0, max_levels=1
        )
        assert hierarchy.detection_method == "louvain"

    def test_detect_hierarchical_falls_back_without_gds(self, modules):
        session = SyncSession(
            gds_available=False,
            component_records=[
                {"entity": "a", "community_key": "group_a"},
                {"entity": "b", "community_key": "group_a"},
            ],
            edge_records=[],
        )
        hierarchy = modules.detection.detect_communities_hierarchical(session)
        assert hierarchy.detection_method == "connected_components"

    def test_summarize_community_structured_fallback_includes_metrics(self, modules):
        community = modules.detection.Community(
            id=1,
            level=0,
            entities=["alice", "neo4j"],
            modularity_score=0.8,
            coverage_score=0.4,
            cohesion_score=0.6,
        )
        session = SyncSession(
            entity_detail_records=[
                {"name": "alice", "type": "Person", "mentions": 2, "rels": []}
            ]
        )
        summary = modules.detection.summarize_community(session, community)
        assert "modularity" in summary.lower()
        assert "alice" in summary.lower()

    def test_summarize_parent_community_uses_child_summaries(self, modules):
        community = modules.detection.Community(
            id=4, level=2, entities=["alice", "neo4j"], children_ids=[1, 2]
        )
        summary = modules.detection.summarize_community(
            SyncSession(),
            community,
            child_summaries=["People cluster", "Graph cluster"],
        )
        assert "unifies" in summary.lower()
        assert "people cluster" in summary.lower()

    def test_summarize_community_uses_llm_generate(self, modules):
        community = modules.detection.Community(id=1, level=0, entities=["alice"])
        session = SyncSession(
            entity_detail_records=[
                {"name": "alice", "type": "Person", "mentions": 1, "rels": []}
            ]
        )
        summary = modules.detection.summarize_community(
            session, community, llm=StubLLM()
        )
        assert summary == "LLM generated summary"

    def test_summarize_all_communities_populates_every_level(self, modules):
        hierarchy = make_sample_hierarchy(modules)
        modules.detection.summarize_all_communities(SyncSession(), hierarchy)
        assert set(hierarchy.summaries_by_level) == {0, 1, 2}
        assert hierarchy.communities[3].summary

    def test_connected_components_metrics_and_levels(self, modules):
        session = SyncSession(
            component_records=[
                {"entity": "a", "community_key": "group_a"},
                {"entity": "b", "community_key": "group_a"},
            ],
            edge_records=[{"source": "a", "target": "b"}],
            gds_available=False,
        )
        hierarchy = modules.detection._detect_connected_components(session)
        assert hierarchy.levels == 1
        assert hierarchy.level_metrics[0]["coverage"] == pytest.approx(1.0)

    def test_detect_communities_returns_flat_map(self, modules):
        session = SyncSession(
            leiden_by_gamma={1.0: [{"entity": "a", "communityId": 1}]},
            edge_records=[],
        )
        flat = modules.detection.detect_communities(
            session, resolution=1.0, max_levels=1
        )
        assert any("a" in members for members in flat.values())

    def test_async_detect_hierarchical_disabled(self, modules):
        hierarchy = asyncio.run(
            modules.detection.detect_communities_hierarchical_async(
                object(), enabled=False
            )
        )
        assert hierarchy.detection_method == "disabled"

    def test_async_leiden_supports_parameters(self, modules):
        session = AsyncSession(
            leiden_by_gamma={1.0: [{"entity": "a", "communityId": 1}]},
            edge_records=[],
        )
        hierarchy = asyncio.run(
            modules.detection.detect_communities_hierarchical_async(
                session,
                resolution=1.0,
                max_levels=1,
                n_iterations=5,
                randomness=9,
            )
        )
        assert hierarchy.parameters["n_iterations"] == 5
        assert hierarchy.parameters["randomness"] == 9


class TestCommunityGraphRAGAdvanced:
    def test_route_query_global_prefers_community(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        assert (
            asyncio.run(
                rag.route_query("Summarize the overall themes across all communities")
            )
            == "community"
        )

    def test_route_query_local_prefers_entity(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        assert asyncio.run(rag.route_query("Who is Alice?")) == "entity"

    def test_route_query_mixed_prefers_hybrid(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        assert (
            asyncio.run(rag.route_query("How does Alice connect to Neo4j architecture"))
            == "hybrid"
        )

    def test_route_query_with_communities_disabled_never_returns_community(
        self, modules
    ):
        rag = modules.community.CommunityGraphRAG(
            AsyncDriver(), enable_communities=False
        )
        assert asyncio.run(rag.route_query("Summarize the overall themes")) == "hybrid"

    def test_select_optimal_level_global_uses_highest_level(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver(), max_hierarchy_levels=4)
        rag._compose_hierarchy_levels = lambda: asyncio.sleep(
            0, result={0: [], 1: [1], 2: [1], 3: [1], 4: [1]}
        )
        assert (
            asyncio.run(rag.select_optimal_level("overall themes across everything"))
            == 4
        )

    def test_select_optimal_level_local_uses_lowest_level(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver(), max_hierarchy_levels=4)
        rag._compose_hierarchy_levels = lambda: asyncio.sleep(
            0, result={0: [], 1: [1], 2: [1], 3: [1]}
        )
        assert asyncio.run(rag.select_optimal_level("who is alice?")) == 1

    def test_select_optimal_level_scales_with_complexity(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver(), max_hierarchy_levels=4)
        rag._compose_hierarchy_levels = lambda: asyncio.sleep(
            0, result={0: [], 1: [1], 2: [1], 3: [1], 4: [1]}
        )
        simple_level = asyncio.run(rag.select_optimal_level("alice and neo4j"))
        complex_level = asyncio.run(
            rag.select_optimal_level(
                "compare relationships and patterns across teams and platforms"
            )
        )
        assert complex_level >= simple_level

    def test_detect_communities_returns_empty_when_disabled(self, modules):
        rag = modules.community.CommunityGraphRAG(
            AsyncDriver(), enable_communities=False
        )
        assert asyncio.run(rag.detect_communities()) == {}

    def test_summarize_communities_returns_empty_when_disabled(self, modules):
        rag = modules.community.CommunityGraphRAG(
            AsyncDriver(), enable_communities=False
        )
        assert asyncio.run(rag.summarize_communities()) == {}

    def test_build_hierarchy_returns_empty_when_disabled(self, modules):
        rag = modules.community.CommunityGraphRAG(
            AsyncDriver(), enable_communities=False
        )
        assert asyncio.run(rag.build_hierarchy()) == {0: []}

    def test_get_leaf_communities_carries_metric_metadata(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        rag._latest_hierarchy = make_sample_hierarchy(modules)
        leaf = asyncio.run(rag._get_leaf_communities())[0]
        assert set(leaf.metadata) >= {"modularity", "coverage", "cohesion"}

    def test_compose_hierarchy_builds_four_plus_levels(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver(), max_hierarchy_levels=4)
        rag._get_leaf_communities = lambda: asyncio.sleep(
            0, result=make_leaf_levels(modules, 16)
        )
        levels = asyncio.run(rag._compose_hierarchy_levels())
        assert max(levels) >= 4
        assert levels[4][0].community_id == "global"

    def test_build_hierarchy_persists_nodes(self, modules):
        driver = AsyncDriver()
        rag = modules.community.CommunityGraphRAG(driver, max_hierarchy_levels=4)
        rag._get_leaf_communities = lambda: asyncio.sleep(
            0, result=make_leaf_levels(modules, 8)
        )
        hierarchy = asyncio.run(rag.build_hierarchy())
        assert any("MERGE (c:Community" in query for query, _ in driver.queries)
        assert hierarchy[1]

    def test_query_community_returns_selected_level(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        rag.route_query = lambda query: asyncio.sleep(0, result="community")
        rag.select_optimal_level = lambda query: asyncio.sleep(0, result=3)
        rag._search_community_summaries = (
            lambda query, top_k, hierarchy_level=None: asyncio.sleep(
                0,
                result=[{"community_id": "global", "level": hierarchy_level}],
            )
        )
        result = asyncio.run(rag.query("overall themes"))
        assert result.hierarchy_level == 3
        assert result.strategy == "community"

    def test_query_entity_returns_hierarchy_level_zero(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        rag.route_query = lambda query: asyncio.sleep(0, result="entity")
        rag._search_entities = lambda query, top_k: asyncio.sleep(
            0, result=[{"entity_name": "alice"}]
        )
        result = asyncio.run(rag.query("who is alice?"))
        assert result.hierarchy_level == 0

    def test_hybrid_search_falls_back_to_entities_when_disabled(self, modules):
        rag = modules.community.CommunityGraphRAG(
            AsyncDriver(), enable_communities=False
        )
        rag._search_entities = lambda query, top_k: asyncio.sleep(
            0, result=[{"entity_name": "alice"}]
        )
        results = asyncio.run(rag._hybrid_search("alice", 3, hierarchy_level=1))
        assert results == [{"entity_name": "alice"}]

    def test_query_level_delegates_to_summary_search(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        rag._search_community_summaries = (
            lambda query, top_k, hierarchy_level=None: asyncio.sleep(
                0, result=[{"level": hierarchy_level}]
            )
        )
        result = asyncio.run(rag._query_level("themes", level=2))
        assert result[0]["level"] == 2

    def test_resolve_entity_returns_default_when_no_rows(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        result = asyncio.run(rag._resolve_entity("alice"))
        assert result["canonical_id"] == "alice"
        assert result["communities"] == []

    def test_estimate_query_complexity_higher_for_complex_query(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        simple = rag._estimate_query_complexity("alice")
        complex_query = rag._estimate_query_complexity(
            "compare relationships and patterns across all communities"
        )
        assert complex_query > simple

    def test_combine_summaries_uses_fallback_when_empty(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        summary = rag._combine_summaries([], ["a", "b"], label="Fallback")
        assert "Fallback" in summary

    def test_merge_metadata_averages_metrics(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        merged = rag._merge_metadata(
            [
                {"modularity": 0.2, "coverage": 0.4, "cohesion": 0.6},
                {"modularity": 0.4, "coverage": 0.6, "cohesion": 0.8},
            ],
            level=3,
        )
        assert merged["modularity"] == pytest.approx(0.3)
        assert merged["coverage"] == pytest.approx(0.5)
        assert merged["cohesion"] == pytest.approx(0.7)

    def test_persist_leaf_communities_writes_metric_metadata(self, modules):
        driver = AsyncDriver()
        rag = modules.community.CommunityGraphRAG(driver)
        hierarchy = make_sample_hierarchy(modules)
        asyncio.run(rag._persist_leaf_communities(hierarchy))
        payload = driver.queries[0][1]["communities"]
        assert set(payload[0]["metadata"]) >= {"modularity", "coverage", "cohesion"}

    def test_search_community_summaries_falls_back_to_in_memory_levels(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        rag._compose_hierarchy_levels = lambda: asyncio.sleep(
            0,
            result={
                0: [],
                1: [
                    modules.community.CommunityLevel(
                        "leaf", 1, ["alice"], "Alice summary"
                    )
                ],
                2: [
                    modules.community.CommunityLevel(
                        "global", 2, ["alice", "neo4j"], "Global summary"
                    )
                ],
            },
        )
        results = asyncio.run(
            rag._search_community_summaries("alice", 5, hierarchy_level=1)
        )
        assert results[0]["community_id"] == "leaf"

    def test_rank_community_records_orders_by_score_and_size(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        ranked = rag._rank_community_records(
            [
                {
                    "community_id": "small",
                    "level": 1,
                    "summary": "neo4j",
                    "members": ["neo4j"],
                    "member_count": 1,
                },
                {
                    "community_id": "large",
                    "level": 1,
                    "summary": "neo4j graph",
                    "members": ["neo4j", "graph"],
                    "member_count": 2,
                },
            ],
            ["neo4j", "graph"],
        )
        assert ranked[0]["community_id"] == "large"

    def test_generate_summary_uses_llm_when_available(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())

        class AsyncLLM:
            async def summarize(self, prompt: str):
                assert "Members:" in prompt
                return "Async summary"

        summary = asyncio.run(rag._generate_summary(["alice", "neo4j"], llm=AsyncLLM()))
        assert summary == "Async summary"

    def test_fallback_summary_mentions_member_count(self, modules):
        rag = modules.community.CommunityGraphRAG(AsyncDriver())
        summary = rag._fallback_summary(["a", "b", "c"])
        assert "3 related entities" in summary

    def test_query_result_includes_query_complexity(self, modules):
        result = modules.community.CommunityQueryResult(
            strategy="hybrid", results=[], hierarchy_level=1, query_complexity=0.75
        )
        assert result.query_complexity == 0.75
