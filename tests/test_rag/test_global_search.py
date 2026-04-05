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

"""
Comprehensive tests for GraphRAG Global Search implementation.

Tests cover:
- Configuration and initialization
- Map phase (parallel community querying)
- Reduce phase (aggregation and ranking)
- Theme extraction
- Hierarchical querying
- Rate limiting
- Caching
- Integration with GraphRAG class
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.rag.global_search import (
    CommunityResponse,
    GlobalSearch,
    GlobalSearchConfig,
    GlobalSearchMode,
    GlobalSearchResult,
    RateLimiter,
    ResponseCache,
    ResponseType,
    global_search,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j driver."""
    driver = MagicMock()

    # Mock session context manager
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    driver.session.return_value = session
    return driver


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value="Test response")
    return llm


@pytest.fixture
def sample_communities() -> List[Dict[str, Any]]:
    """Sample community data for testing."""
    return [
        {
            "community_id": "comm_1",
            "level": 1,
            "summary": "Community about machine learning and AI research",
            "members": ["neural networks", "deep learning", "tensorflow"],
            "member_count": 3,
        },
        {
            "community_id": "comm_2",
            "level": 1,
            "summary": "Community about data science and analytics",
            "members": ["pandas", "numpy", "statistics"],
            "member_count": 3,
        },
        {
            "community_id": "comm_3",
            "level": 2,
            "summary": "Coarse community covering technical topics",
            "members": ["programming", "software", "development"],
            "member_count": 3,
        },
        {
            "community_id": "global",
            "level": 3,
            "summary": "Global community with all knowledge domains",
            "members": ["technology", "science", "engineering"],
            "member_count": 3,
        },
    ]


@pytest.fixture
def default_config() -> GlobalSearchConfig:
    """Default configuration for tests."""
    return GlobalSearchConfig(
        mode=GlobalSearchMode.STATIC,
        community_level=1,
        max_communities=10,
        batch_size=5,
        enable_cache=False,
    )


# =============================================================================
# Configuration Tests
# =============================================================================


class TestGlobalSearchConfig:
    """Tests for GlobalSearchConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GlobalSearchConfig()

        assert config.mode == GlobalSearchMode.DYNAMIC
        assert config.response_type == ResponseType.SUMMARY
        assert config.community_level == 1
        assert config.max_communities == 100
        assert config.min_relevance_score == 0.1
        assert config.batch_size == 10
        assert config.requests_per_minute == 60
        assert config.concurrent_requests == 5
        assert config.enable_cache is True
        assert config.cache_ttl_seconds == 3600

    def test_custom_values(self):
        """Test custom configuration values."""
        config = GlobalSearchConfig(
            mode=GlobalSearchMode.HIERARCHICAL,
            response_type=ResponseType.DETAILED,
            community_level=2,
            max_communities=50,
            batch_size=20,
            enable_cache=False,
        )

        assert config.mode == GlobalSearchMode.HIERARCHICAL
        assert config.response_type == ResponseType.DETAILED
        assert config.community_level == 2
        assert config.max_communities == 50
        assert config.batch_size == 20
        assert config.enable_cache is False

    def test_search_modes(self):
        """Test all search modes are defined."""
        assert GlobalSearchMode.STATIC.value == "static"
        assert GlobalSearchMode.DYNAMIC.value == "dynamic"
        assert GlobalSearchMode.HIERARCHICAL.value == "hierarchical"

    def test_response_types(self):
        """Test all response types are defined."""
        assert ResponseType.SUMMARY.value == "summary"
        assert ResponseType.DETAILED.value == "detailed"
        assert ResponseType.THEMES.value == "themes"
        assert ResponseType.RANKED.value == "ranked"


# =============================================================================
# Cache Tests
# =============================================================================


class TestResponseCache:
    """Tests for ResponseCache class."""

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = ResponseCache(ttl_seconds=60)
        config = GlobalSearchConfig()

        result = cache.get("test query", config)
        assert result is None

    def test_cache_hit(self):
        """Test cache hit returns stored result."""
        cache = ResponseCache(ttl_seconds=60)
        config = GlobalSearchConfig()

        result = GlobalSearchResult(
            query="test query",
            response="Test response",
            themes=["theme1"],
            community_responses=[],
            hierarchy_levels_used=[1],
            total_communities_queried=5,
            execution_time_ms=100.0,
        )

        cache.set("test query", config, result)
        cached = cache.get("test query", config)

        assert cached is not None
        assert cached.response == "Test response"
        assert cached.from_cache is True

    def test_cache_expiry(self):
        """Test cache entries expire after TTL."""
        cache = ResponseCache(ttl_seconds=1)
        config = GlobalSearchConfig()

        result = GlobalSearchResult(
            query="test",
            response="response",
            themes=[],
            community_responses=[],
            hierarchy_levels_used=[],
            total_communities_queried=0,
            execution_time_ms=0.0,
        )

        cache.set("test", config, result)
        assert cache.get("test", config) is not None

        # Wait for expiry
        time.sleep(1.1)
        assert cache.get("test", config) is None

    def test_cache_clear(self):
        """Test cache clear removes all entries."""
        cache = ResponseCache()
        config = GlobalSearchConfig()

        result = GlobalSearchResult(
            query="test",
            response="response",
            themes=[],
            community_responses=[],
            hierarchy_levels_used=[],
            total_communities_queried=0,
            execution_time_ms=0.0,
        )

        cache.set("test1", config, result)
        cache.set("test2", config, result)
        assert len(cache._cache) == 2

        cache.clear()
        assert len(cache._cache) == 0

    def test_invalidate_older_than(self):
        """Test invalidating entries older than threshold."""
        cache = ResponseCache(ttl_seconds=3600)
        config = GlobalSearchConfig()

        result = GlobalSearchResult(
            query="test",
            response="response",
            themes=[],
            community_responses=[],
            hierarchy_levels_used=[],
            total_communities_queried=0,
            execution_time_ms=0.0,
        )

        cache.set("test", config, result)
        # Manually backdate the entry
        key = list(cache._cache.keys())[0]
        cache._cache[key] = (cache._cache[key][0], time.time() - 100)

        removed = cache.invalidate_older_than(50)
        assert removed == 1
        assert len(cache._cache) == 0


# =============================================================================
# Rate Limiter Tests
# =============================================================================


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquire succeeds within rate limit."""
        limiter = RateLimiter(requests_per_minute=60, max_concurrent=5)

        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should be nearly instant
        assert elapsed < 0.1
        limiter.release()

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """Test concurrent request limiting."""
        limiter = RateLimiter(requests_per_minute=1000, max_concurrent=2)

        acquired = []

        async def try_acquire(idx: int):
            await limiter.acquire()
            acquired.append(idx)
            await asyncio.sleep(0.1)
            limiter.release()

        # Start 4 concurrent tasks
        tasks = [asyncio.create_task(try_acquire(i)) for i in range(4)]

        # Wait a bit - only 2 should have acquired immediately
        await asyncio.sleep(0.05)
        assert len(acquired) == 2

        # Wait for all to complete
        await asyncio.gather(*tasks)
        assert len(acquired) == 4

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_rate_limit_per_minute(self):
        """Test rate limiting enforces requests per minute."""
        limiter = RateLimiter(requests_per_minute=100, max_concurrent=10)

        # Acquire several slots quickly
        for _ in range(3):
            await limiter.acquire()
            limiter.release()

        # Should still be able to acquire more without waiting
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        # Should complete quickly since we're under the limit
        assert elapsed < 1.0
        limiter.release()


# =============================================================================
# CommunityResponse Tests
# =============================================================================


class TestCommunityResponse:
    """Tests for CommunityResponse dataclass."""

    def test_create_response(self):
        """Test creating a community response."""
        response = CommunityResponse(
            community_id="comm_1",
            level=1,
            summary="Test summary",
            response="Test response text",
            relevance_score=0.85,
            key_points=["point1", "point2"],
            themes=["theme1", "theme2"],
            entities_mentioned=["entity1"],
        )

        assert response.community_id == "comm_1"
        assert response.level == 1
        assert response.relevance_score == 0.85
        assert len(response.key_points) == 2
        assert len(response.themes) == 2

    def test_default_values(self):
        """Test default values for optional fields."""
        response = CommunityResponse(
            community_id="comm_1",
            level=1,
            summary="Test",
            response="Response",
            relevance_score=0.5,
        )

        assert response.key_points == []
        assert response.themes == []
        assert response.entities_mentioned == []
        assert response.metadata == {}


# =============================================================================
# GlobalSearchResult Tests
# =============================================================================


class TestGlobalSearchResult:
    """Tests for GlobalSearchResult dataclass."""

    def test_create_result(self):
        """Test creating a global search result."""
        result = GlobalSearchResult(
            query="test query",
            response="Final response",
            themes=["theme1", "theme2"],
            community_responses=[],
            hierarchy_levels_used=[1, 2],
            total_communities_queried=10,
            execution_time_ms=150.5,
        )

        assert result.query == "test query"
        assert result.response == "Final response"
        assert len(result.themes) == 2
        assert result.hierarchy_levels_used == [1, 2]
        assert result.execution_time_ms == 150.5
        assert result.from_cache is False

    def test_to_dict(self):
        """Test serialization to dictionary."""
        cr = CommunityResponse(
            community_id="comm_1",
            level=1,
            summary="Summary",
            response="Response",
            relevance_score=0.8,
            themes=["theme1"],
        )

        result = GlobalSearchResult(
            query="test",
            response="Final",
            themes=["theme1"],
            community_responses=[cr],
            hierarchy_levels_used=[1],
            total_communities_queried=1,
            execution_time_ms=100.0,
        )

        data = result.to_dict()

        assert data["query"] == "test"
        assert data["response"] == "Final"
        assert data["themes"] == ["theme1"]
        assert data["community_count"] == 1
        assert data["hierarchy_levels"] == [1]
        assert len(data["communities"]) == 1
        assert data["communities"][0]["id"] == "comm_1"


# =============================================================================
# GlobalSearch Initialization Tests
# =============================================================================


class TestGlobalSearchInit:
    """Tests for GlobalSearch initialization."""

    def test_init_with_defaults(self, mock_driver):
        """Test initialization with default config."""
        search = GlobalSearch(mock_driver)

        assert search.driver is mock_driver
        assert search.llm is None
        assert search.config.mode == GlobalSearchMode.DYNAMIC

    def test_init_with_custom_config(self, mock_driver, default_config):
        """Test initialization with custom config."""
        search = GlobalSearch(mock_driver, config=default_config)

        assert search.config.mode == GlobalSearchMode.STATIC
        assert search.config.community_level == 1

    def test_init_with_llm(self, mock_driver, mock_llm):
        """Test initialization with LLM."""
        search = GlobalSearch(mock_driver, llm=mock_llm)

        assert search.llm is mock_llm


# =============================================================================
# Map Phase Tests
# =============================================================================


class TestMapPhase:
    """Tests for the map phase of global search."""

    @pytest.mark.asyncio
    async def test_map_empty_communities(self, mock_driver, default_config):
        """Test map phase with no communities."""
        search = GlobalSearch(mock_driver, config=default_config)

        responses = await search._map_phase("test query", [], default_config)

        assert responses == []

    @pytest.mark.asyncio
    async def test_map_without_llm(self, mock_driver, default_config, sample_communities):
        """Test map phase without LLM (keyword matching)."""
        search = GlobalSearch(mock_driver, config=default_config)

        responses = await search._map_phase(
            "machine learning", sample_communities[:2], default_config
        )

        assert len(responses) == 2
        # First community should have higher relevance (contains "machine learning")
        assert responses[0].community_id == "comm_1"
        assert responses[0].relevance_score > 0

    @pytest.mark.asyncio
    async def test_map_with_llm(self, mock_driver, mock_llm, default_config, sample_communities):
        """Test map phase with LLM."""
        mock_llm.generate = AsyncMock(return_value="""
RELEVANCE: 0.9
KEY_POINTS:
- Point about machine learning
- Another key insight
THEMES: AI, neural networks, deep learning
RESPONSE: This community covers machine learning topics extensively.
""")

        search = GlobalSearch(mock_driver, llm=mock_llm, config=default_config)

        responses = await search._map_phase(
            "machine learning", sample_communities[:1], default_config
        )

        assert len(responses) == 1
        assert responses[0].relevance_score == 0.9
        assert len(responses[0].key_points) == 2
        assert "AI" in responses[0].themes

    @pytest.mark.asyncio
    async def test_map_batching(self, mock_driver, default_config, sample_communities):
        """Test map phase processes in batches."""
        config = GlobalSearchConfig(batch_size=2, enable_cache=False)
        search = GlobalSearch(mock_driver, config=config)

        # Should process in 2 batches of 2
        responses = await search._map_phase("test", sample_communities, config)

        assert len(responses) == 4


# =============================================================================
# Reduce Phase Tests
# =============================================================================


class TestReducePhase:
    """Tests for the reduce phase of global search."""

    @pytest.mark.asyncio
    async def test_reduce_empty_responses(self, mock_driver, default_config):
        """Test reduce phase with no responses."""
        search = GlobalSearch(mock_driver, config=default_config)

        response, themes = await search._reduce_phase("test", [], default_config)

        assert response == "No relevant information found."
        assert themes == []

    @pytest.mark.asyncio
    async def test_reduce_without_llm(self, mock_driver, default_config):
        """Test reduce phase without LLM."""
        search = GlobalSearch(mock_driver, config=default_config)

        community_responses = [
            CommunityResponse(
                community_id="comm_1",
                level=1,
                summary="Summary 1",
                response="Response about AI",
                relevance_score=0.8,
                themes=["AI", "ML"],  # Both themes
            ),
            CommunityResponse(
                community_id="comm_2",
                level=1,
                summary="Summary 2",
                response="Response about ML",
                relevance_score=0.6,
                themes=["ML", "deep learning"],  # ML shared theme
            ),
        ]

        response, themes = await search._reduce_phase(
            "test", community_responses, default_config
        )

        assert "2 relevant communities" in response
        # ML should be extracted as it appears in 2+ communities
        assert "ml" in themes  # normalized to lowercase

    @pytest.mark.asyncio
    async def test_reduce_with_llm(self, mock_driver, mock_llm, default_config):
        """Test reduce phase with LLM synthesis."""
        mock_llm.generate = AsyncMock(return_value="Synthesized response about AI and ML")

        search = GlobalSearch(mock_driver, llm=mock_llm, config=default_config)

        community_responses = [
            CommunityResponse(
                community_id="comm_1",
                level=1,
                summary="Summary",
                response="Response",
                relevance_score=0.8,
                themes=["AI", "ML"],
            ),
        ]

        response, themes = await search._reduce_phase(
            "test", community_responses, default_config
        )

        assert response == "Synthesized response about AI and ML"


# =============================================================================
# Theme Extraction Tests
# =============================================================================


class TestThemeExtraction:
    """Tests for cross-community theme extraction."""

    def test_extract_themes_single_mention(self, mock_driver, default_config):
        """Test themes with single mention are filtered."""
        search = GlobalSearch(mock_driver, config=default_config)

        responses = [
            CommunityResponse(
                community_id="c1", level=1, summary="", response="",
                relevance_score=0.8, themes=["unique_theme"],
            ),
            CommunityResponse(
                community_id="c2", level=1, summary="", response="",
                relevance_score=0.7, themes=["other_theme"],
            ),
        ]

        themes = search._extract_cross_community_themes(responses, default_config)

        # Neither theme appears in 2+ communities
        assert len(themes) == 0

    def test_extract_themes_multiple_mentions(self, mock_driver, default_config):
        """Test themes mentioned in multiple communities are extracted."""
        search = GlobalSearch(mock_driver, config=default_config)

        responses = [
            CommunityResponse(
                community_id="c1", level=1, summary="", response="",
                relevance_score=0.8, themes=["shared_theme", "unique1"],
            ),
            CommunityResponse(
                community_id="c2", level=1, summary="", response="",
                relevance_score=0.7, themes=["shared_theme", "unique2"],
            ),
        ]

        themes = search._extract_cross_community_themes(responses, default_config)

        assert "shared_theme" in themes
        assert "unique1" not in themes
        assert "unique2" not in themes

    def test_extract_themes_sorted_by_frequency(self, mock_driver, default_config):
        """Test themes are sorted by frequency."""
        search = GlobalSearch(mock_driver, config=default_config)

        responses = [
            CommunityResponse(
                community_id="c1", level=1, summary="", response="",
                relevance_score=0.8, themes=["common", "rare"],
            ),
            CommunityResponse(
                community_id="c2", level=1, summary="", response="",
                relevance_score=0.7, themes=["common"],
            ),
            CommunityResponse(
                community_id="c3", level=1, summary="", response="",
                relevance_score=0.6, themes=["common", "rare"],
            ),
        ]

        themes = search._extract_cross_community_themes(responses, default_config)

        # Common appears 3 times, rare appears 2 times
        assert themes[0] == "common"
        assert themes[1] == "rare"


# =============================================================================
# Search Mode Tests
# =============================================================================


class TestStaticSearch:
    """Tests for static search mode."""

    @pytest.mark.asyncio
    async def test_static_search_basic(self, mock_driver, sample_communities):
        """Test basic static search."""
        config = GlobalSearchConfig(
            mode=GlobalSearchMode.STATIC,
            community_level=1,
            enable_cache=False,
        )
        search = GlobalSearch(mock_driver, config=config)

        # Mock the query method
        search._get_communities_at_level = AsyncMock(
            return_value=[c for c in sample_communities if c["level"] == 1]
        )

        result = await search._static_search("test query", config)

        assert isinstance(result, GlobalSearchResult)
        assert result.query == "test query"
        search._get_communities_at_level.assert_called_once_with(1)


class TestDynamicSearch:
    """Tests for dynamic search mode."""

    @pytest.mark.asyncio
    async def test_dynamic_search_drills_down(self, mock_driver, sample_communities):
        """Test dynamic search drills into relevant communities."""
        config = GlobalSearchConfig(
            mode=GlobalSearchMode.DYNAMIC,
            drill_down_threshold=0.3,
            enable_cache=False,
        )
        search = GlobalSearch(mock_driver, config=config)

        # Mock hierarchy queries
        search._get_communities_at_level = AsyncMock(side_effect=[
            [sample_communities[3]],  # Level 3 (global)
            [sample_communities[2]],  # Level 2 (coarse)
        ])
        search._get_child_communities = AsyncMock(return_value=["comm_3"])
        search._get_communities_by_ids = AsyncMock(return_value=[sample_communities[2]])

        result = await search._dynamic_search("test", config)

        assert isinstance(result, GlobalSearchResult)
        # Should have queried multiple levels
        assert search._get_communities_at_level.call_count >= 1


class TestHierarchicalSearch:
    """Tests for hierarchical search mode."""

    @pytest.mark.asyncio
    async def test_hierarchical_queries_all_levels(self, mock_driver, sample_communities):
        """Test hierarchical search queries all levels."""
        config = GlobalSearchConfig(
            mode=GlobalSearchMode.HIERARCHICAL,
            enable_cache=False,
        )
        search = GlobalSearch(mock_driver, config=config)

        # Mock to return communities at each level
        async def mock_get_level(level: int):
            return [c for c in sample_communities if c["level"] == level]

        search._get_communities_at_level = AsyncMock(side_effect=mock_get_level)

        result = await search._hierarchical_search("test", config)

        assert isinstance(result, GlobalSearchResult)
        # Should have tried all 3 levels
        assert search._get_communities_at_level.call_count == 3


# =============================================================================
# Integration Tests
# =============================================================================


class TestGlobalSearchIntegration:
    """Integration tests for GlobalSearch."""

    @pytest.mark.asyncio
    async def test_search_with_cache(self, mock_driver, sample_communities):
        """Test search uses and populates cache."""
        config = GlobalSearchConfig(
            mode=GlobalSearchMode.STATIC,
            enable_cache=True,
            cache_ttl_seconds=60,
        )
        search = GlobalSearch(mock_driver, config=config)

        search._get_communities_at_level = AsyncMock(
            return_value=[sample_communities[0]]
        )

        # First search
        result1 = await search.search("test query", config)
        assert result1.from_cache is False

        # Second search should hit cache
        result2 = await search.search("test query", config)
        assert result2.from_cache is True

    @pytest.mark.asyncio
    async def test_search_records_execution_time(self, mock_driver, sample_communities):
        """Test search records execution time."""
        config = GlobalSearchConfig(
            mode=GlobalSearchMode.STATIC,
            enable_cache=False,
        )
        search = GlobalSearch(mock_driver, config=config)

        search._get_communities_at_level = AsyncMock(
            return_value=[sample_communities[0]]
        )

        result = await search.search("test")

        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_empty_result_on_no_communities(self, mock_driver):
        """Test returns empty result when no communities found."""
        config = GlobalSearchConfig(enable_cache=False)
        search = GlobalSearch(mock_driver, config=config)

        search._get_communities_at_level = AsyncMock(return_value=[])

        result = await search.search("test")

        assert "No relevant information" in result.response
        assert result.total_communities_queried == 0


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_keyword_relevance(self, mock_driver, default_config):
        """Test keyword relevance calculation."""
        search = GlobalSearch(mock_driver, config=default_config)

        # Exact match in summary
        score = search._keyword_relevance(
            "machine learning",
            "This is about machine learning and AI",
            ["neural networks"],
        )
        assert score > 0

        # No match
        score = search._keyword_relevance(
            "completely different",
            "This is about cooking",
            ["recipes"],
        )
        assert score == 0

    def test_extract_keywords(self, mock_driver, default_config):
        """Test keyword extraction from text."""
        search = GlobalSearch(mock_driver, config=default_config)

        keywords = search._extract_keywords(
            "Machine learning uses neural networks for deep learning tasks",
            max_keywords=3,
        )

        assert len(keywords) <= 3
        # Should extract meaningful words, not stopwords
        assert "with" not in keywords
        assert "from" not in keywords

    def test_aggregate_without_llm(self, mock_driver, default_config):
        """Test aggregation without LLM."""
        search = GlobalSearch(mock_driver, config=default_config)

        responses = [
            CommunityResponse(
                community_id="c1", level=1, summary="S1",
                response="Response about topic A",
                relevance_score=0.8, themes=["A"],
            ),
            CommunityResponse(
                community_id="c2", level=2, summary="S2",
                response="Response about topic B",
                relevance_score=0.6, themes=["B"],
            ),
        ]

        result = search._aggregate_without_llm(responses, ["A", "B"])

        assert "2 relevant communities" in result
        assert "A, B" in result
        assert "(Level 1)" in result
        assert "(Level 2)" in result


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunction:
    """Tests for global_search convenience function."""

    @pytest.mark.asyncio
    async def test_global_search_function(self, mock_driver):
        """Test the global_search convenience function."""
        with patch.object(GlobalSearch, "search") as mock_search:
            mock_result = GlobalSearchResult(
                query="test",
                response="Response",
                themes=[],
                community_responses=[],
                hierarchy_levels_used=[],
                total_communities_queried=0,
                execution_time_ms=0.0,
            )
            mock_search.return_value = mock_result

            result = await global_search(
                "test query",
                mock_driver,
                mode=GlobalSearchMode.STATIC,
            )

            assert result is mock_result


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_llm_error_graceful_degradation(self, mock_driver, mock_llm, default_config):
        """Test graceful degradation when LLM fails."""
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

        search = GlobalSearch(mock_driver, llm=mock_llm, config=default_config)

        # Should not raise, should return empty string
        result = await search._call_llm("test prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_query_error_returns_empty(self, mock_driver, default_config):
        """Test query errors return empty results."""
        search = GlobalSearch(mock_driver, config=default_config)
        search._execute_query = AsyncMock(side_effect=Exception("Query Error"))

        communities = await search._get_communities_at_level(1)

        assert communities == []

    @pytest.mark.asyncio
    async def test_map_phase_handles_individual_failures(self, mock_driver, mock_llm, default_config, sample_communities):
        """Test map phase continues despite individual community failures."""
        call_count = 0

        async def flaky_generate(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return "RELEVANCE: 0.5\nRESPONSE: Success"

        mock_llm.generate = flaky_generate
        search = GlobalSearch(mock_driver, llm=mock_llm, config=default_config)

        responses = await search._map_phase(
            "test", sample_communities[:2], default_config
        )

        # Should have at least one successful response
        assert len(responses) >= 1


# =============================================================================
# Neo4j Query Tests
# =============================================================================


class TestNeo4jQueries:
    """Tests for Neo4j query execution."""

    @pytest.mark.asyncio
    async def test_execute_query_with_execute_query_method(self, mock_driver):
        """Test query execution with execute_query method."""
        search = GlobalSearch(mock_driver)

        mock_driver.execute_query = AsyncMock(return_value=[
            {"community_id": "c1", "level": 1, "summary": "Test"}
        ])

        result = await search._execute_query("MATCH (c:Community) RETURN c")

        assert len(result) >= 1
        mock_driver.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_child_communities(self, mock_driver):
        """Test getting child communities."""
        search = GlobalSearch(mock_driver)

        search._execute_query = AsyncMock(return_value=[
            {"child_id": "child_1"},
            {"child_id": "child_2"},
        ])

        children = await search._get_child_communities("parent_1")

        assert children == ["child_1", "child_2"]

    @pytest.mark.asyncio
    async def test_get_communities_by_ids_empty(self, mock_driver):
        """Test getting communities by IDs with empty list."""
        search = GlobalSearch(mock_driver)

        result = await search._get_communities_by_ids([])

        assert result == []


# =============================================================================
# Prompt Building Tests
# =============================================================================


class TestPromptBuilding:
    """Tests for prompt construction."""

    def test_build_map_prompt(self, mock_driver, default_config):
        """Test map prompt construction."""
        search = GlobalSearch(mock_driver, config=default_config)

        prompt = search._build_map_prompt(
            query="What is machine learning?",
            summary="Community about ML and AI",
            members=["neural networks", "deep learning"],
            config=default_config,
        )

        assert "What is machine learning?" in prompt
        assert "Community about ML and AI" in prompt
        assert "neural networks" in prompt
        assert "RELEVANCE:" in prompt
        assert "KEY_POINTS:" in prompt

    def test_build_reduce_prompt(self, mock_driver, default_config):
        """Test reduce prompt construction."""
        search = GlobalSearch(mock_driver, config=default_config)

        responses = [
            CommunityResponse(
                community_id="c1", level=1, summary="S1",
                response="Response 1",
                relevance_score=0.8,
                key_points=["point1"],
                themes=["AI"],
            ),
        ]

        prompt = search._build_reduce_prompt(
            query="What is AI?",
            responses=responses,
            themes=["AI", "ML"],
            config=default_config,
        )

        assert "What is AI?" in prompt
        assert "AI, ML" in prompt
        assert "Community 1" in prompt

    def test_parse_map_response(self, mock_driver, default_config):
        """Test parsing map phase LLM response."""
        search = GlobalSearch(mock_driver, config=default_config)

        response = """
RELEVANCE: 0.85
KEY_POINTS:
- First key point
- Second key point
THEMES: machine learning, neural networks, AI
RESPONSE: This is the response about the topic.
"""

        relevance, key_points, themes = search._parse_map_response(
            response, "test query", "test summary"
        )

        assert relevance == 0.85
        assert len(key_points) == 2
        assert "First key point" in key_points
        assert "machine learning" in themes
        assert "AI" in themes


# =============================================================================
# Cache Management Tests
# =============================================================================


class TestCacheManagement:
    """Tests for cache management methods."""

    def test_clear_cache(self, mock_driver):
        """Test clearing the cache."""
        config = GlobalSearchConfig(enable_cache=True)
        search = GlobalSearch(mock_driver, config=config)

        # Manually add something to cache
        search._cache._cache["test"] = (MagicMock(), time.time())
        assert len(search._cache._cache) == 1

        search.clear_cache()
        assert len(search._cache._cache) == 0

    def test_get_cache_stats(self, mock_driver):
        """Test getting cache statistics."""
        config = GlobalSearchConfig(enable_cache=True, cache_ttl_seconds=1800)
        search = GlobalSearch(mock_driver, config=config)

        stats = search.get_cache_stats()

        assert "size" in stats
        assert "ttl_seconds" in stats
        assert stats["ttl_seconds"] == 1800


# =============================================================================
# Run tests with pytest
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
