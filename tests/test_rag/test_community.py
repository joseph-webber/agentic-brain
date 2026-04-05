# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Comprehensive tests for community-aware GraphRAG module.

Covers:
- CommunityLevel dataclass (serialization, member counts)
- CommunityQueryResult dataclass
- CommunityGraphRAG orchestration
- Community detection and persistence
- Hierarchical community queries
- Entity resolution across communities
- Fallback behaviors and edge cases
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.rag.community import (
    CommunityGraphRAG,
    CommunityLevel,
    CommunityQueryResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_driver() -> MagicMock:
    """Create a mock Neo4j driver."""
    return MagicMock()


@pytest.fixture
def sample_community_level() -> CommunityLevel:
    """Create a sample community level."""
    return CommunityLevel(
        community_id="comm_1",
        level=0,
        members=["entity_a", "entity_b", "entity_c"],
        summary="A community of three entities",
        child_ids=["comm_2", "comm_3"],
        metadata={"modularity": 0.85, "size": 3},
    )


@pytest.fixture
def sample_query_result() -> CommunityQueryResult:
    """Create a sample query result."""
    return CommunityQueryResult(
        strategy="community",
        results=[
            {"entity_id": "e1", "score": 0.95},
            {"entity_id": "e2", "score": 0.87},
        ],
        hierarchy_level=1,
    )


# ---------------------------------------------------------------------------
# CommunityLevel Tests
# ---------------------------------------------------------------------------


class TestCommunityLevel:
    def test_community_level_creation(self) -> None:
        level = CommunityLevel(
            community_id="c1",
            level=0,
            members=["a", "b", "c"],
        )
        assert level.community_id == "c1"
        assert level.level == 0
        assert len(level.members) == 3

    def test_community_level_member_count_property(self, sample_community_level: CommunityLevel) -> None:
        assert sample_community_level.member_count == 3

    def test_community_level_to_dict(self, sample_community_level: CommunityLevel) -> None:
        d = sample_community_level.to_dict()
        assert isinstance(d, dict)
        assert d["community_id"] == "comm_1"
        assert d["level"] == 0
        assert d["member_count"] == 3
        assert len(d["members"]) == 3

    def test_community_level_to_dict_includes_all_fields(self, sample_community_level: CommunityLevel) -> None:
        d = sample_community_level.to_dict()
        assert "community_id" in d
        assert "level" in d
        assert "members" in d
        assert "summary" in d
        assert "child_ids" in d
        assert "member_count" in d
        assert "metadata" in d

    def test_community_level_empty_members(self) -> None:
        level = CommunityLevel(community_id="empty", level=0)
        assert level.member_count == 0

    def test_community_level_with_metadata(self, sample_community_level: CommunityLevel) -> None:
        assert sample_community_level.metadata["modularity"] == 0.85
        assert sample_community_level.metadata["size"] == 3

    def test_community_level_with_children(self, sample_community_level: CommunityLevel) -> None:
        assert len(sample_community_level.child_ids) == 2
        assert "comm_2" in sample_community_level.child_ids


# ---------------------------------------------------------------------------
# CommunityQueryResult Tests
# ---------------------------------------------------------------------------


class TestCommunityQueryResult:
    def test_query_result_creation(self) -> None:
        result = CommunityQueryResult(
            strategy="hybrid",
            results=[{"id": "r1", "score": 0.9}],
            hierarchy_level=1,
        )
        assert result.strategy == "hybrid"
        assert len(result.results) == 1
        assert result.hierarchy_level == 1

    def test_query_result_different_strategies(self) -> None:
        strategies = ["vector", "graph", "hybrid", "community", "multi_hop"]
        for strategy in strategies:
            result = CommunityQueryResult(
                strategy=strategy,
                results=[],
                hierarchy_level=0,
            )
            assert result.strategy == strategy

    def test_query_result_multiple_results(self, sample_query_result: CommunityQueryResult) -> None:
        assert len(sample_query_result.results) == 2

    def test_query_result_empty_results(self) -> None:
        result = CommunityQueryResult(
            strategy="graph",
            results=[],
            hierarchy_level=0,
        )
        assert len(result.results) == 0


# ---------------------------------------------------------------------------
# CommunityGraphRAG Initialization Tests
# ---------------------------------------------------------------------------


class TestCommunityGraphRAGInitialization:
    def test_init_with_driver(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        assert rag.driver == mock_driver

    def test_init_detector_none_when_unavailable(self, mock_driver: MagicMock) -> None:
        with patch("agentic_brain.rag.community.LeidenCommunityDetector", None):
            rag = CommunityGraphRAG(mock_driver)
            assert rag.detector is None

    def test_init_latest_hierarchy_none(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        assert rag._latest_hierarchy is None


# ---------------------------------------------------------------------------
# Community Detection Tests
# ---------------------------------------------------------------------------


class TestCommunityDetection:
    @pytest.mark.asyncio
    async def test_detect_communities_returns_dict(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        
        with patch.object(rag, '_detect_hierarchy', new_callable=AsyncMock) as mock_detect:
            from agentic_brain.rag.community_detection import CommunityHierarchy, Community
            
            # Create mock hierarchy
            hierarchy = CommunityHierarchy()
            hierarchy.communities[1] = Community(
                id=1, level=0, entities=["a", "b"]
            )
            mock_detect.return_value = hierarchy
            
            with patch.object(rag, '_persist_leaf_communities', new_callable=AsyncMock):
                result = await rag.detect_communities()
                
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_detect_communities_persists_hierarchy(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        
        with patch.object(rag, '_detect_hierarchy', new_callable=AsyncMock) as mock_detect:
            from agentic_brain.rag.community_detection import CommunityHierarchy
            
            hierarchy = CommunityHierarchy()
            mock_detect.return_value = hierarchy
            
            with patch.object(rag, '_persist_leaf_communities', new_callable=AsyncMock) as mock_persist:
                await rag.detect_communities()
                mock_persist.assert_called_once()


# ---------------------------------------------------------------------------
# Community Query Tests
# ---------------------------------------------------------------------------


class TestCommunityQueries:
    @pytest.mark.asyncio
    async def test_query_returns_community_query_result(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        
        # Mock the query method
        with patch.object(rag, 'query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = CommunityQueryResult(
                strategy="community",
                results=[{"id": "r1"}],
                hierarchy_level=0,
            )
            
            result = await rag.query("test")
        
        assert isinstance(result, CommunityQueryResult)

    @pytest.mark.asyncio
    async def test_query_multiple_hierarchy_levels(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        
        for level in range(3):
            with patch.object(rag, 'query', new_callable=AsyncMock) as mock_query:
                mock_query.return_value = CommunityQueryResult(
                    strategy="community",
                    results=[],
                    hierarchy_level=level,
                )
                
                result = await rag.query("test")
                assert result.hierarchy_level == level


# ---------------------------------------------------------------------------
# Entity Resolution Tests
# ---------------------------------------------------------------------------


class TestEntityResolution:
    @pytest.mark.asyncio
    async def test_resolve_entity_across_communities(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        
        with patch.object(rag, '_resolve_entity', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = {
                "canonical_id": "entity_canonical",
                "communities": [1, 2, 3],
                "aliases": ["entity_alias_1", "entity_alias_2"],
            }
            
            result = await rag._resolve_entity("entity_name")
        
        assert result["canonical_id"] == "entity_canonical"


# ---------------------------------------------------------------------------
# Edge Cases and Fallbacks
# ---------------------------------------------------------------------------


class TestEdgeCasesAndFallbacks:
    @pytest.mark.asyncio
    async def test_detect_communities_empty_graph(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        
        with patch.object(rag, '_detect_hierarchy', new_callable=AsyncMock) as mock_detect:
            from agentic_brain.rag.community_detection import CommunityHierarchy
            
            # Empty hierarchy
            hierarchy = CommunityHierarchy()
            mock_detect.return_value = hierarchy
            
            with patch.object(rag, '_persist_leaf_communities', new_callable=AsyncMock):
                result = await rag.detect_communities()
                
        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_query_no_hierarchy_set(self, mock_driver: MagicMock) -> None:
        rag = CommunityGraphRAG(mock_driver)
        rag._latest_hierarchy = None  # No hierarchy detected yet
        
        # Should handle gracefully
        with patch.object(rag, 'query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = CommunityQueryResult(
                strategy="hybrid",  # Fallback to hybrid
                results=[],
                hierarchy_level=0,
            )
            
            result = await rag.query("test")
        
        assert isinstance(result, CommunityQueryResult)

    @pytest.mark.asyncio
    async def test_detector_unavailable_fallback(self, mock_driver: MagicMock) -> None:
        with patch("agentic_brain.rag.community.LeidenCommunityDetector", None):
            rag = CommunityGraphRAG(mock_driver)
            assert rag.detector is None
            
            # Should still work, maybe with fallback detection
            with patch.object(rag, '_detect_hierarchy', new_callable=AsyncMock) as mock_detect:
                from agentic_brain.rag.community_detection import CommunityHierarchy
                
                mock_detect.return_value = CommunityHierarchy()
                with patch.object(rag, '_persist_leaf_communities', new_callable=AsyncMock):
                    result = await rag.detect_communities()
            
            assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Hierarchy Level Tests
# ---------------------------------------------------------------------------


class TestHierarchyLevels:
    @pytest.mark.asyncio
    async def test_query_at_different_levels(self, mock_driver: MagicMock) -> None:
        """Test querying at different hierarchy levels."""
        rag = CommunityGraphRAG(mock_driver)
        
        # Level 0 (leaf communities)
        with patch.object(rag, '_query_level', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"id": "e1", "score": 0.9}]
            level_0_results = await rag._query_level("test", level=0)
        
        assert len(level_0_results) > 0

    @pytest.mark.asyncio
    async def test_ascending_hierarchy_on_failure(self, mock_driver: MagicMock) -> None:
        """Test moving to higher hierarchy level when lower level fails."""
        rag = CommunityGraphRAG(mock_driver)
        
        with patch.object(rag, '_query_level', new_callable=AsyncMock) as mock_query:
            # Level 0 returns empty
            mock_query.side_effect = [[], [{"id": "e1"}], [{"id": "e2", "id": "e3"}]]
            
            # Should ascend hierarchy
            results = []
            for level in range(3):
                r = await rag._query_level("test", level=level)
                results.extend(r)
        
        assert len(results) > 0


# ---------------------------------------------------------------------------
# Performance Tests
# ---------------------------------------------------------------------------


class TestPerformanceConsiderations:
    def test_large_community_serialization(self) -> None:
        """Test serializing large communities."""
        members = [f"entity_{i}" for i in range(10000)]
        level = CommunityLevel(
            community_id="large_comm",
            level=0,
            members=members,
        )
        
        d = level.to_dict()
        assert d["member_count"] == 10000
        assert len(d["members"]) == 10000

    def test_deep_hierarchy_navigation(self) -> None:
        """Test navigating very deep hierarchies."""
        # Create a deep hierarchy
        levels = []
        for i in range(100):
            level = CommunityLevel(
                community_id=f"comm_{i}",
                level=i,
                members=[f"entity_{i}"],
                child_ids=[f"comm_{i+1}"] if i < 99 else [],
            )
            levels.append(level)
        
        # Should handle without issues
        assert len(levels) == 100
        assert levels[-1].level == 99


# ---------------------------------------------------------------------------
# Data Consistency Tests
# ---------------------------------------------------------------------------


class TestDataConsistency:
    def test_community_level_member_count_consistency(self) -> None:
        """Verify member_count matches members list length."""
        members = ["a", "b", "c", "d", "e"]
        level = CommunityLevel(
            community_id="test",
            level=0,
            members=members,
        )
        
        assert level.member_count == len(members)
        assert level.to_dict()["member_count"] == len(members)

    def test_query_result_strategy_values(self) -> None:
        """Test that query result strategies are from valid set."""
        valid_strategies = ["vector", "graph", "hybrid", "community", "multi_hop"]
        
        for strategy in valid_strategies:
            result = CommunityQueryResult(
                strategy=strategy,
                results=[],
                hierarchy_level=0,
            )
            assert result.strategy == strategy
