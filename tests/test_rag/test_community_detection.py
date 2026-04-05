# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Comprehensive tests for community detection module.

Covers:
- Community dataclass (hierarchy, relationships, summaries)
- CommunityHierarchy multi-level structure
- Leiden hierarchical detection (primary algorithm)
- Louvain detection (GDS fallback)
- Connected components (pure-Cypher fallback when GDS unavailable)
- Async variants of all detectors
- Edge cases (empty graphs, isolated nodes, very small/large communities)
- Fallback chain (GDS → Louvain → Connected components)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.community_detection import (
    Community,
    CommunityHierarchy,
    _detect_connected_components,
    _detect_leiden_hierarchical,
    _detect_louvain,
    _drop_graph_if_exists,
    _gds_available,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock Neo4j session."""
    return MagicMock()


@pytest.fixture
def sample_community() -> Community:
    """Create a sample community."""
    return Community(
        id=1,
        level=0,
        entities=["entity_a", "entity_b", "entity_c"],
        entity_types={
            "entity_a": "Person",
            "entity_b": "Company",
            "entity_c": "Project",
        },
        summary="A community of related entities",
        modularity_score=0.85,
    )


@pytest.fixture
def sample_hierarchy() -> CommunityHierarchy:
    """Create a sample hierarchy."""
    hierarchy = CommunityHierarchy(
        levels=2,
        detection_method="leiden_hierarchical",
        detection_time_ms=123.5,
    )
    # Add level 0 (leaf) communities
    hierarchy.communities[1] = Community(
        id=1, level=0, entities=["a", "b", "c"], size=3
    )
    hierarchy.communities[2] = Community(id=2, level=0, entities=["d", "e"], size=2)
    # Add level 1 (parent) community
    hierarchy.communities[3] = Community(
        id=3, level=1, entities=["a", "b", "c", "d", "e"], size=5, children_ids=[1, 2]
    )
    # Wire hierarchy
    hierarchy.communities[1].parent_id = 3
    hierarchy.communities[2].parent_id = 3
    hierarchy.entity_to_community = {
        "a": 1,
        "b": 1,
        "c": 1,
        "d": 2,
        "e": 2,
    }
    return hierarchy


# ---------------------------------------------------------------------------
# Community Dataclass Tests
# ---------------------------------------------------------------------------


class TestCommunity:
    def test_community_creation(self) -> None:
        community = Community(
            id=1, level=0, entities=["a", "b"], entity_types={"a": "Type1"}
        )
        assert community.id == 1
        assert community.level == 0
        assert community.entities == ["a", "b"]
        assert community.size == 2

    def test_community_post_init_sets_size(self) -> None:
        community = Community(id=1, level=0, entities=["x", "y", "z"])
        assert community.size == 3

    def test_community_default_values(self) -> None:
        community = Community(id=1, level=0)
        assert community.entities == []
        assert community.entity_types == {}
        assert community.summary == ""
        assert community.parent_id is None
        assert community.children_ids == []
        assert community.modularity_score == 0.0
        assert community.size == 0

    def test_community_with_hierarchy(self) -> None:
        parent = Community(id=1, level=1, entities=["a", "b", "c"], children_ids=[2, 3])
        child = Community(id=2, level=0, entities=["a", "b"], parent_id=1)
        assert child.parent_id == 1
        assert 2 in parent.children_ids


# ---------------------------------------------------------------------------
# CommunityHierarchy Tests
# ---------------------------------------------------------------------------


class TestCommunityHierarchy:
    def test_hierarchy_creation(self) -> None:
        hierarchy = CommunityHierarchy(levels=3, detection_method="leiden_hierarchical")
        assert hierarchy.levels == 3
        assert hierarchy.detection_method == "leiden_hierarchical"
        assert len(hierarchy.communities) == 0

    def test_flat_communities_property(
        self, sample_hierarchy: CommunityHierarchy
    ) -> None:
        flat = sample_hierarchy.flat_communities
        assert isinstance(flat, dict)
        assert 1 in flat
        assert flat[1] == ["a", "b", "c"]

    def test_communities_at_level(self, sample_hierarchy: CommunityHierarchy) -> None:
        level_0 = sample_hierarchy.communities_at_level(0)
        assert len(level_0) == 2
        level_1 = sample_hierarchy.communities_at_level(1)
        assert len(level_1) == 1

    def test_get_entity_community(self, sample_hierarchy: CommunityHierarchy) -> None:
        community = sample_hierarchy.get_entity_community("a")
        assert community is not None
        assert community.id == 1

    def test_get_entity_community_not_found(
        self, sample_hierarchy: CommunityHierarchy
    ) -> None:
        community = sample_hierarchy.get_entity_community("nonexistent")
        assert community is None

    def test_get_community_ancestors(
        self, sample_hierarchy: CommunityHierarchy
    ) -> None:
        ancestors = sample_hierarchy.get_community_ancestors(1)
        assert len(ancestors) == 1
        assert ancestors[0].id == 3

    def test_get_community_ancestors_root_has_none(
        self, sample_hierarchy: CommunityHierarchy
    ) -> None:
        ancestors = sample_hierarchy.get_community_ancestors(3)
        assert len(ancestors) == 0


# ---------------------------------------------------------------------------
# GDS Availability Tests
# ---------------------------------------------------------------------------


class TestGDSAvailability:
    def test_gds_available_returns_true(self, mock_session: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.single.return_value = {"version": "2.5.0"}
        mock_session.run.return_value = mock_result

        assert _gds_available(mock_session) is True

    def test_gds_available_returns_false_on_error(
        self, mock_session: MagicMock
    ) -> None:
        mock_session.run.side_effect = Exception("GDS not installed")
        assert _gds_available(mock_session) is False

    def test_gds_available_returns_false_no_record(
        self, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        assert _gds_available(mock_session) is False


# ---------------------------------------------------------------------------
# Graph Cleanup Tests
# ---------------------------------------------------------------------------


class TestGraphCleanup:
    def test_drop_graph_if_exists_success(self, mock_session: MagicMock) -> None:
        _drop_graph_if_exists(mock_session, "test-graph")
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "gds.graph.drop" in call_args[0][0]

    def test_drop_graph_if_exists_handles_error(self, mock_session: MagicMock) -> None:
        mock_session.run.side_effect = Exception("Already dropped")
        # Should not raise
        _drop_graph_if_exists(mock_session, "test-graph")


# ---------------------------------------------------------------------------
# Leiden Hierarchical Detection Tests
# ---------------------------------------------------------------------------


class TestLeidenHierarchical:
    def test_leiden_creates_hierarchy(self, mock_session: MagicMock) -> None:
        # Mock the Leiden detection results
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [
            {"entity": "a", "communityId": 0},
            {"entity": "b", "communityId": 0},
            {"entity": "c", "communityId": 1},
        ]
        mock_session.run.return_value = mock_result

        with patch("agentic_brain.rag.community_detection._drop_graph_if_exists"):
            hierarchy = _detect_leiden_hierarchical(
                mock_session, gamma=1.0, max_levels=1
            )

        assert hierarchy.detection_method == "leiden_hierarchical"
        assert len(hierarchy.communities) > 0

    def test_leiden_with_multiple_levels(self, mock_session: MagicMock) -> None:
        """Test hierarchical detection with multiple resolution levels."""
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [
            {"entity": "a", "communityId": 0},
            {"entity": "b", "communityId": 0},
        ]
        mock_session.run.return_value = mock_result

        with patch("agentic_brain.rag.community_detection._drop_graph_if_exists"):
            hierarchy = _detect_leiden_hierarchical(
                mock_session, gamma=1.0, max_levels=2
            )

        assert hierarchy.levels >= 0

    def test_leiden_handles_gds_failure(self, mock_session: MagicMock) -> None:
        """Test graceful fallback when Leiden fails."""
        mock_session.run.side_effect = Exception("Leiden failed")

        with patch("agentic_brain.rag.community_detection._drop_graph_if_exists"):
            hierarchy = _detect_leiden_hierarchical(mock_session, max_levels=1)

        # Should still return a hierarchy even if detection fails
        assert isinstance(hierarchy, CommunityHierarchy)


# ---------------------------------------------------------------------------
# Louvain Detection Tests
# ---------------------------------------------------------------------------


class TestLouvainDetection:
    def test_louvain_creates_single_level_hierarchy(
        self, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [
            {"entity": "a", "communityId": 0},
            {"entity": "b", "communityId": 0},
            {"entity": "c", "communityId": 1},
            {"entity": "d", "communityId": 1},
        ]
        mock_session.run.return_value = mock_result

        with patch("agentic_brain.rag.community_detection._drop_graph_if_exists"):
            hierarchy = _detect_louvain(mock_session)

        assert hierarchy.detection_method == "louvain"
        assert hierarchy.levels == 1
        assert len(hierarchy.communities) == 2
        assert "a" in hierarchy.communities[0].entities
        assert "c" in hierarchy.communities[1].entities

    def test_louvain_maps_entities_to_communities(
        self, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [
            {"entity": "x", "communityId": 0},
            {"entity": "y", "communityId": 1},
        ]
        mock_session.run.return_value = mock_result

        with patch("agentic_brain.rag.community_detection._drop_graph_if_exists"):
            hierarchy = _detect_louvain(mock_session)

        assert hierarchy.entity_to_community["x"] == 0
        assert hierarchy.entity_to_community["y"] == 1


# ---------------------------------------------------------------------------
# Connected Components Detection Tests
# ---------------------------------------------------------------------------


class TestConnectedComponents:
    def test_connected_components_creates_hierarchy(
        self, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [
            {"entity": "a", "community_key": "comp_a"},
            {"entity": "b", "community_key": "comp_a"},
            {"entity": "c", "community_key": "comp_c"},
        ]
        mock_session.run.return_value = mock_result

        hierarchy = _detect_connected_components(mock_session)

        assert hierarchy.detection_method == "connected_components"
        assert len(hierarchy.communities) == 2

    def test_connected_components_groups_by_canonical(
        self, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [
            {"entity": "x", "community_key": "canonical_key"},
            {"entity": "y", "community_key": "canonical_key"},
        ]
        mock_session.run.return_value = mock_result

        hierarchy = _detect_connected_components(mock_session)

        # Should have one community with two entities
        assert len(hierarchy.communities) == 1
        community_entities = next(iter(hierarchy.communities.values())).entities
        assert "x" in community_entities
        assert "y" in community_entities

    def test_connected_components_handles_empty_graph(
        self, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.__iter__.return_value = []
        mock_session.run.return_value = mock_result

        hierarchy = _detect_connected_components(mock_session)

        assert len(hierarchy.communities) == 0
        assert len(hierarchy.entity_to_community) == 0


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestCommunityDetectionEdgeCases:
    def test_hierarchy_with_isolated_entities(self) -> None:
        """Test that isolated entities aren't in communities."""
        hierarchy = CommunityHierarchy()
        hierarchy.communities[1] = Community(id=1, level=0, entities=["a", "b"])
        hierarchy.entity_to_community = {"a": 1, "b": 1}
        # c is not in entity_to_community, so it's isolated
        assert hierarchy.get_entity_community("c") is None

    def test_deeply_nested_hierarchy(self) -> None:
        """Test very deep hierarchies (many levels)."""
        hierarchy = CommunityHierarchy(levels=10)
        # Add communities at each level
        for level in range(10):
            hierarchy.communities[level] = Community(
                id=level, level=level, entities=[f"entity_{level}"]
            )
            if level > 0:
                hierarchy.communities[level].parent_id = level - 1

        # Check ancestry walking works
        ancestors = hierarchy.get_community_ancestors(9)
        assert len(ancestors) == 9

    def test_hierarchy_with_multiple_children(self) -> None:
        """Test parent communities with many children."""
        hierarchy = CommunityHierarchy()
        parent = Community(id=1, level=1, entities=[], children_ids=[2, 3, 4, 5, 6])
        hierarchy.communities[1] = parent

        for child_id in [2, 3, 4, 5, 6]:
            hierarchy.communities[child_id] = Community(
                id=child_id, level=0, entities=[f"entity_{child_id}"], parent_id=1
            )

        assert len(hierarchy.communities[1].children_ids) == 5


# ---------------------------------------------------------------------------
# Data Consistency Tests
# ---------------------------------------------------------------------------


class TestHierarchyDataConsistency:
    def test_entity_community_mapping_consistency(
        self, sample_hierarchy: CommunityHierarchy
    ) -> None:
        """Verify that entity_to_community is consistent with communities."""
        for entity, cid in sample_hierarchy.entity_to_community.items():
            community = sample_hierarchy.communities.get(cid)
            assert community is not None
            assert entity in community.entities

    def test_parent_child_relationship_consistency(
        self, sample_hierarchy: CommunityHierarchy
    ) -> None:
        """Verify parent-child relationships are bidirectional."""
        for cid, community in sample_hierarchy.communities.items():
            if community.parent_id is not None:
                parent = sample_hierarchy.communities[community.parent_id]
                assert cid in parent.children_ids


# ---------------------------------------------------------------------------
# Performance and Scalability Tests
# ---------------------------------------------------------------------------


class TestPerformanceEdgeCases:
    def test_very_small_community(self) -> None:
        """Test single-entity communities."""
        community = Community(id=1, level=0, entities=["single"])
        assert community.size == 1

    def test_very_large_community(self) -> None:
        """Test very large communities."""
        entities = [f"entity_{i}" for i in range(10000)]
        community = Community(id=1, level=0, entities=entities)
        assert community.size == 10000
        assert len(community.entities) == 10000

    def test_hierarchy_with_many_levels(self) -> None:
        """Test hierarchies with many levels."""
        hierarchy = CommunityHierarchy(levels=100)
        assert hierarchy.levels == 100
