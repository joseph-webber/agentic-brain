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
Microsoft GraphRAG Global Search Implementation.

Implements the map-reduce pattern for answering global queries by:
1. MAP: Query each community summary in parallel
2. REDUCE: Aggregate and rank community responses
3. THEME EXTRACTION: Identify cross-community themes
4. HIERARCHICAL: Start at root communities, drill down as needed

Reference: https://github.com/microsoft/graphrag
Paper: "From Local to Global: A GraphRAG Approach to Query-Focused Summarization"

Key features:
- Parallel community querying with configurable batch sizes
- Dynamic community selection (prune irrelevant summaries early)
- Hierarchical traversal from global → coarse → leaf communities
- Response caching with TTL for repeated queries
- Rate limiting for LLM calls
- Theme extraction across community boundaries
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


class LLMProtocol(Protocol):
    """Protocol for LLM adapters used in global search."""

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a response from the LLM."""
        ...


class GlobalSearchMode(Enum):
    """Global search execution modes."""

    STATIC = "static"  # Query all communities at a fixed level
    DYNAMIC = "dynamic"  # Start at root, prune irrelevant branches
    HIERARCHICAL = "hierarchical"  # Full hierarchy traversal


class ResponseType(Enum):
    """Type of response to generate."""

    SUMMARY = "summary"  # Concise summary
    DETAILED = "detailed"  # Detailed analysis
    THEMES = "themes"  # Theme extraction only
    RANKED = "ranked"  # Ranked list of findings


@dataclass
class GlobalSearchConfig:
    """Configuration for GraphRAG global search."""

    # Search behavior
    mode: GlobalSearchMode = GlobalSearchMode.DYNAMIC
    response_type: ResponseType = ResponseType.SUMMARY

    # Community selection
    community_level: int = 1  # Default hierarchy level (1=leaf, 2=coarse, 3=global)
    max_communities: int = 100  # Max communities to query in map phase
    min_relevance_score: float = 0.1  # Minimum score to include in reduce

    # Rate limiting
    batch_size: int = 10  # Communities per LLM batch
    requests_per_minute: int = 60  # LLM rate limit
    concurrent_requests: int = 5  # Max parallel LLM calls

    # Response generation
    max_tokens_per_community: int = 500  # Token budget per community response
    max_output_tokens: int = 2000  # Final response token limit
    temperature: float = 0.0  # LLM temperature for determinism

    # Caching
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour default

    # Hierarchical settings
    drill_down_threshold: float = 0.5  # Score threshold to drill deeper
    max_hierarchy_depth: int = 3  # Maximum levels to traverse

    # Theme extraction
    extract_themes: bool = True
    min_theme_mentions: int = 2  # Minimum communities mentioning a theme


@dataclass
class CommunityResponse:
    """Response from querying a single community."""

    community_id: str
    level: int
    summary: str
    response: str
    relevance_score: float
    key_points: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    entities_mentioned: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GlobalSearchResult:
    """Result from a global search query."""

    query: str
    response: str
    themes: List[str]
    community_responses: List[CommunityResponse]
    hierarchy_levels_used: List[int]
    total_communities_queried: int
    execution_time_ms: float
    from_cache: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "response": self.response,
            "themes": self.themes,
            "community_count": len(self.community_responses),
            "hierarchy_levels": self.hierarchy_levels_used,
            "execution_time_ms": self.execution_time_ms,
            "from_cache": self.from_cache,
            "communities": [
                {
                    "id": cr.community_id,
                    "level": cr.level,
                    "score": cr.relevance_score,
                    "themes": cr.themes,
                }
                for cr in self.community_responses
            ],
            "metadata": self.metadata,
        }


class ResponseCache:
    """Simple in-memory cache for global search responses."""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[GlobalSearchResult, float]] = {}
        self._ttl = ttl_seconds

    def _make_key(self, query: str, config: GlobalSearchConfig) -> str:
        """Create cache key from query and config."""
        key_parts = f"{query}|{config.mode.value}|{config.community_level}"
        return hashlib.sha256(key_parts.encode()).hexdigest()[:16]

    def get(
        self, query: str, config: GlobalSearchConfig
    ) -> Optional[GlobalSearchResult]:
        """Get cached result if valid."""
        key = self._make_key(query, config)
        if key not in self._cache:
            return None

        result, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None

        result.from_cache = True
        return result

    def set(
        self, query: str, config: GlobalSearchConfig, result: GlobalSearchResult
    ) -> None:
        """Cache a result."""
        key = self._make_key(query, config)
        self._cache[key] = (result, time.time())

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()

    def invalidate_older_than(self, seconds: int) -> int:
        """Remove entries older than specified seconds. Returns count removed."""
        now = time.time()
        expired = [k for k, (_, ts) in self._cache.items() if now - ts > seconds]
        for k in expired:
            del self._cache[k]
        return len(expired)


class RateLimiter:
    """Simple rate limiter for LLM calls."""

    def __init__(self, requests_per_minute: int = 60, max_concurrent: int = 5):
        self._rpm = requests_per_minute
        self._max_concurrent = max_concurrent
        self._timestamps: List[float] = []
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a rate limit slot."""
        await self._semaphore.acquire()

        async with self._lock:
            now = time.time()
            # Remove timestamps older than 1 minute
            self._timestamps = [ts for ts in self._timestamps if now - ts < 60]

            # Wait if at rate limit
            if len(self._timestamps) >= self._rpm:
                wait_time = 60 - (now - self._timestamps[0])
                if wait_time > 0:
                    logger.debug(f"Rate limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    self._timestamps = self._timestamps[1:]

            self._timestamps.append(time.time())

    def release(self) -> None:
        """Release a rate limit slot."""
        self._semaphore.release()


class GlobalSearch:
    """
    Microsoft GraphRAG Global Search Implementation.

    Implements the map-reduce pattern for answering queries that require
    understanding across the entire knowledge graph by leveraging
    community summaries at multiple hierarchy levels.

    Usage:
        from agentic_brain.rag.global_search import GlobalSearch, GlobalSearchConfig

        # Initialize with Neo4j driver and LLM
        search = GlobalSearch(driver, llm)

        # Execute global search
        result = await search.search("What are the main themes across all documents?")

        # Access results
        print(result.response)
        print(result.themes)
    """

    def __init__(
        self,
        driver: Any,
        llm: Optional[LLMProtocol] = None,
        config: Optional[GlobalSearchConfig] = None,
    ):
        """
        Initialize global search.

        Args:
            driver: Neo4j async driver instance
            llm: LLM adapter implementing generate() method
            config: Global search configuration
        """
        self.driver = driver
        self.llm = llm
        self.config = config or GlobalSearchConfig()
        self._cache = ResponseCache(ttl_seconds=self.config.cache_ttl_seconds)
        self._rate_limiter = RateLimiter(
            requests_per_minute=self.config.requests_per_minute,
            max_concurrent=self.config.concurrent_requests,
        )

    async def search(
        self,
        query: str,
        config: Optional[GlobalSearchConfig] = None,
    ) -> GlobalSearchResult:
        """
        Execute a global search across community summaries.

        Args:
            query: The search query
            config: Optional config override

        Returns:
            GlobalSearchResult with aggregated response and themes
        """
        start_time = time.time()
        cfg = config or self.config

        # Check cache
        if cfg.enable_cache:
            cached = self._cache.get(query, cfg)
            if cached:
                logger.debug(f"Global search cache hit for: {query[:50]}...")
                return cached

        # Execute based on mode
        if cfg.mode == GlobalSearchMode.STATIC:
            result = await self._static_search(query, cfg)
        elif cfg.mode == GlobalSearchMode.DYNAMIC:
            result = await self._dynamic_search(query, cfg)
        else:  # HIERARCHICAL
            result = await self._hierarchical_search(query, cfg)

        result.execution_time_ms = (time.time() - start_time) * 1000

        # Cache result
        if cfg.enable_cache:
            self._cache.set(query, cfg, result)

        return result

    async def _static_search(
        self, query: str, config: GlobalSearchConfig
    ) -> GlobalSearchResult:
        """Static search: query all communities at a fixed level."""
        communities = await self._get_communities_at_level(config.community_level)

        if not communities:
            return self._empty_result(query)

        # Limit communities
        communities = communities[: config.max_communities]

        # Map phase: query each community in parallel batches
        community_responses = await self._map_phase(query, communities, config)

        # Filter by relevance
        relevant = [
            cr
            for cr in community_responses
            if cr.relevance_score >= config.min_relevance_score
        ]

        if not relevant:
            return self._empty_result(query)

        # Reduce phase: aggregate responses
        response, themes = await self._reduce_phase(query, relevant, config)

        return GlobalSearchResult(
            query=query,
            response=response,
            themes=themes,
            community_responses=relevant,
            hierarchy_levels_used=[config.community_level],
            total_communities_queried=len(communities),
            execution_time_ms=0.0,
        )

    async def _dynamic_search(
        self, query: str, config: GlobalSearchConfig
    ) -> GlobalSearchResult:
        """
        Dynamic search: start at root level, prune irrelevant branches early.

        This is more efficient than static search as it:
        1. Evaluates global/coarse communities first
        2. Only drills into relevant sub-communities
        3. Stops early if high-confidence answer found
        """
        # Start at global level (3)
        global_communities = await self._get_communities_at_level(3)

        if not global_communities:
            # Fall back to coarse level
            global_communities = await self._get_communities_at_level(2)

        if not global_communities:
            # Fall back to leaf level (static behavior)
            return await self._static_search(query, config)

        # Evaluate global communities
        global_responses = await self._map_phase(query, global_communities, config)

        # Identify relevant branches to drill into
        relevant_global = [
            cr
            for cr in global_responses
            if cr.relevance_score >= config.drill_down_threshold
        ]

        if not relevant_global:
            # No highly relevant global communities, use all with lower threshold
            relevant_global = [
                cr
                for cr in global_responses
                if cr.relevance_score >= config.min_relevance_score
            ]

        all_responses = list(relevant_global)
        levels_used = [3] if global_responses else []

        # Drill into relevant sub-communities
        if relevant_global:
            child_ids = []
            for cr in relevant_global:
                children = await self._get_child_communities(cr.community_id)
                child_ids.extend(children)

            if child_ids:
                coarse_communities = await self._get_communities_by_ids(child_ids)
                coarse_responses = await self._map_phase(
                    query, coarse_communities, config
                )

                relevant_coarse = [
                    cr
                    for cr in coarse_responses
                    if cr.relevance_score >= config.min_relevance_score
                ]
                all_responses.extend(relevant_coarse)
                if relevant_coarse:
                    levels_used.append(2)

                # Drill to leaf if needed
                if config.max_hierarchy_depth >= 3:
                    leaf_ids = []
                    for cr in relevant_coarse:
                        if cr.relevance_score >= config.drill_down_threshold:
                            children = await self._get_child_communities(
                                cr.community_id
                            )
                            leaf_ids.extend(children)

                    if leaf_ids:
                        leaf_communities = await self._get_communities_by_ids(leaf_ids)
                        leaf_responses = await self._map_phase(
                            query, leaf_communities, config
                        )
                        relevant_leaf = [
                            cr
                            for cr in leaf_responses
                            if cr.relevance_score >= config.min_relevance_score
                        ]
                        all_responses.extend(relevant_leaf)
                        if relevant_leaf:
                            levels_used.append(1)

        if not all_responses:
            return self._empty_result(query)

        # Reduce phase
        response, themes = await self._reduce_phase(query, all_responses, config)

        return GlobalSearchResult(
            query=query,
            response=response,
            themes=themes,
            community_responses=all_responses,
            hierarchy_levels_used=sorted(set(levels_used), reverse=True),
            total_communities_queried=len(all_responses),
            execution_time_ms=0.0,
        )

    async def _hierarchical_search(
        self, query: str, config: GlobalSearchConfig
    ) -> GlobalSearchResult:
        """
        Full hierarchical search: traverse all levels systematically.

        Provides the most comprehensive results by:
        1. Querying all hierarchy levels
        2. Building a complete picture across scales
        3. Identifying themes that span multiple levels
        """
        all_responses: List[CommunityResponse] = []
        levels_used: List[int] = []

        # Query each level from global to leaf
        for level in [3, 2, 1]:
            communities = await self._get_communities_at_level(level)
            if not communities:
                continue

            # Limit per level
            max_per_level = config.max_communities // 3
            communities = communities[:max_per_level]

            responses = await self._map_phase(query, communities, config)
            relevant = [
                cr
                for cr in responses
                if cr.relevance_score >= config.min_relevance_score
            ]

            if relevant:
                all_responses.extend(relevant)
                levels_used.append(level)

        if not all_responses:
            return self._empty_result(query)

        # Reduce with cross-level theme extraction
        response, themes = await self._reduce_phase(query, all_responses, config)

        return GlobalSearchResult(
            query=query,
            response=response,
            themes=themes,
            community_responses=all_responses,
            hierarchy_levels_used=sorted(set(levels_used), reverse=True),
            total_communities_queried=len(all_responses),
            execution_time_ms=0.0,
        )

    async def _map_phase(
        self,
        query: str,
        communities: List[Dict[str, Any]],
        config: GlobalSearchConfig,
    ) -> List[CommunityResponse]:
        """
        Map phase: query each community in parallel with rate limiting.

        Args:
            query: The search query
            communities: List of community dicts with id, summary, members
            config: Search configuration

        Returns:
            List of CommunityResponse objects
        """
        if not communities:
            return []

        # Process in batches
        responses: List[CommunityResponse] = []
        batches = [
            communities[i : i + config.batch_size]
            for i in range(0, len(communities), config.batch_size)
        ]

        for batch in batches:
            batch_tasks = [
                self._query_community(query, community, config) for community in batch
            ]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, CommunityResponse):
                    responses.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Community query failed: {result}")

        return responses

    async def _query_community(
        self,
        query: str,
        community: Dict[str, Any],
        config: GlobalSearchConfig,
    ) -> CommunityResponse:
        """Query a single community and assess relevance."""
        community_id = community.get("community_id", community.get("id", "unknown"))
        level = community.get("level", 1)
        summary = community.get("summary", "")
        members = community.get("members", [])

        # If no LLM, use keyword matching for relevance
        if self.llm is None:
            relevance = self._keyword_relevance(query, summary, members)
            return CommunityResponse(
                community_id=str(community_id),
                level=level,
                summary=summary,
                response=summary,
                relevance_score=relevance,
                key_points=[],
                themes=self._extract_keywords(summary),
                entities_mentioned=members[:10],
            )

        # Use LLM to assess and respond
        await self._rate_limiter.acquire()
        try:
            prompt = self._build_map_prompt(query, summary, members, config)
            response = await self._call_llm(prompt)

            # Parse structured response
            relevance, key_points, themes = self._parse_map_response(
                response, query, summary
            )

            return CommunityResponse(
                community_id=str(community_id),
                level=level,
                summary=summary,
                response=response,
                relevance_score=relevance,
                key_points=key_points,
                themes=themes,
                entities_mentioned=members[:10],
            )
        finally:
            self._rate_limiter.release()

    async def _reduce_phase(
        self,
        query: str,
        responses: List[CommunityResponse],
        config: GlobalSearchConfig,
    ) -> Tuple[str, List[str]]:
        """
        Reduce phase: aggregate community responses into final answer.

        Args:
            query: Original query
            responses: List of community responses from map phase
            config: Search configuration

        Returns:
            Tuple of (final_response, extracted_themes)
        """
        if not responses:
            return "No relevant information found.", []

        # Sort by relevance
        sorted_responses = sorted(
            responses, key=lambda r: r.relevance_score, reverse=True
        )

        # Extract themes across all responses
        themes = self._extract_cross_community_themes(sorted_responses, config)

        # If no LLM, create simple aggregation
        if self.llm is None:
            aggregated = self._aggregate_without_llm(sorted_responses, themes)
            return aggregated, themes

        # Use LLM to synthesize final response
        prompt = self._build_reduce_prompt(query, sorted_responses, themes, config)

        await self._rate_limiter.acquire()
        try:
            response = await self._call_llm(prompt)
            return response.strip(), themes
        finally:
            self._rate_limiter.release()

    def _extract_cross_community_themes(
        self,
        responses: List[CommunityResponse],
        config: GlobalSearchConfig,
    ) -> List[str]:
        """Extract themes that appear across multiple communities."""
        theme_counts: Dict[str, int] = defaultdict(int)

        for cr in responses:
            for theme in cr.themes:
                theme_lower = theme.lower().strip()
                if theme_lower and len(theme_lower) > 2:
                    theme_counts[theme_lower] += 1

        # Filter by minimum mentions
        cross_themes = [
            theme
            for theme, count in theme_counts.items()
            if count >= config.min_theme_mentions
        ]

        # Sort by frequency
        cross_themes.sort(key=lambda t: theme_counts[t], reverse=True)

        return cross_themes[:10]  # Top 10 themes

    def _build_map_prompt(
        self,
        query: str,
        summary: str,
        members: List[str],
        config: GlobalSearchConfig,
    ) -> str:
        """Build prompt for querying a single community."""
        members_str = ", ".join(members[:20])
        if len(members) > 20:
            members_str += f", and {len(members) - 20} more"

        return f"""Analyze this knowledge community in relation to the query.

QUERY: {query}

COMMUNITY SUMMARY:
{summary}

KEY ENTITIES: {members_str}

Provide a response in this format:
RELEVANCE: [0.0-1.0 score of how relevant this community is to the query]
KEY_POINTS:
- [Key point 1 relevant to the query]
- [Key point 2 relevant to the query]
THEMES: [comma-separated themes this community addresses]
RESPONSE: [Brief response addressing the query based on this community's knowledge]

Be concise. Focus only on information relevant to the query."""

    def _build_reduce_prompt(
        self,
        query: str,
        responses: List[CommunityResponse],
        themes: List[str],
        config: GlobalSearchConfig,
    ) -> str:
        """Build prompt for final aggregation."""
        # Build community summaries
        community_parts = []
        for i, cr in enumerate(responses[:15], 1):  # Top 15 communities
            key_points = "\n".join(f"  - {kp}" for kp in cr.key_points[:3])
            community_parts.append(
                f"Community {i} (Level {cr.level}, Relevance: {cr.relevance_score:.2f}):\n"
                f"{cr.response[:500]}\n"
                f"Key Points:\n{key_points}"
            )

        communities_text = "\n\n".join(community_parts)
        themes_text = ", ".join(themes) if themes else "None identified"

        response_instruction = {
            ResponseType.SUMMARY: "Provide a concise summary (2-3 paragraphs).",
            ResponseType.DETAILED: "Provide a detailed analysis with sections.",
            ResponseType.THEMES: "Focus on identifying and explaining major themes.",
            ResponseType.RANKED: "Provide a ranked list of key findings.",
        }.get(config.response_type, "Provide a helpful response.")

        return f"""Synthesize information from multiple knowledge communities to answer the query.

QUERY: {query}

CROSS-COMMUNITY THEMES: {themes_text}

COMMUNITY ANALYSES:
{communities_text}

{response_instruction}

Guidelines:
- Synthesize information across communities, don't just list them
- Highlight connections and patterns across communities
- Note any conflicting information
- Be specific and cite which communities support key claims
- Keep response under {config.max_output_tokens} tokens"""

    def _parse_map_response(
        self, response: str, query: str, summary: str
    ) -> Tuple[float, List[str], List[str]]:
        """Parse structured response from map phase LLM call."""
        relevance = 0.5  # Default
        key_points: List[str] = []
        themes: List[str] = []

        lines = response.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("RELEVANCE:"):
                try:
                    score_str = line.replace("RELEVANCE:", "").strip()
                    relevance = float(score_str.split()[0])
                    relevance = max(0.0, min(1.0, relevance))
                except (ValueError, IndexError):
                    pass
            elif line.startswith("KEY_POINTS:"):
                current_section = "key_points"
            elif line.startswith("THEMES:"):
                themes_str = line.replace("THEMES:", "").strip()
                themes = [t.strip() for t in themes_str.split(",") if t.strip()]
                current_section = None
            elif line.startswith("RESPONSE:"):
                current_section = None
            elif current_section == "key_points" and line.startswith("-"):
                key_points.append(line[1:].strip())

        # Fallback: extract keywords as themes if none found
        if not themes:
            themes = self._extract_keywords(summary)

        return relevance, key_points, themes

    def _keyword_relevance(self, query: str, summary: str, members: List[str]) -> float:
        """Calculate relevance using keyword matching (no LLM fallback)."""
        query_terms = set(query.lower().split())
        query_terms = {t for t in query_terms if len(t) > 2}

        if not query_terms:
            return 0.0

        # Check summary
        summary_lower = summary.lower()
        summary_matches = sum(1 for t in query_terms if t in summary_lower)

        # Check members
        members_text = " ".join(members).lower()
        member_matches = sum(1 for t in query_terms if t in members_text)

        total_matches = summary_matches + member_matches
        max_possible = len(query_terms) * 2  # Can match in both

        return min(1.0, total_matches / max_possible) if max_possible > 0 else 0.0

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """Extract potential theme keywords from text."""
        import re

        # Simple keyword extraction: nouns and noun phrases
        words = re.findall(r"\b[A-Za-z][a-z]{3,}\b", text)
        word_freq: Dict[str, int] = defaultdict(int)

        for word in words:
            word_lower = word.lower()
            # Skip common words
            if word_lower not in {
                "this",
                "that",
                "with",
                "from",
                "have",
                "been",
                "their",
                "which",
                "when",
                "where",
                "what",
                "about",
                "into",
                "than",
                "them",
                "then",
                "some",
                "could",
                "would",
                "there",
                "other",
                "more",
                "also",
                "these",
            }:
                word_freq[word_lower] += 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]

    def _aggregate_without_llm(
        self, responses: List[CommunityResponse], themes: List[str]
    ) -> str:
        """Create aggregated response without LLM."""
        if not responses:
            return "No relevant information found."

        parts = [f"Found {len(responses)} relevant communities.\n"]

        if themes:
            parts.append(f"Key themes: {', '.join(themes[:5])}\n")

        parts.append("\nTop findings:")
        for i, cr in enumerate(responses[:5], 1):
            if cr.response:
                parts.append(f"\n{i}. (Level {cr.level}) {cr.response[:200]}...")

        return "\n".join(parts)

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the given prompt."""
        if self.llm is None:
            return ""

        try:
            # Try different method signatures
            for method_name in ("generate", "chat", "complete", "invoke"):
                method = getattr(self.llm, method_name, None)
                if method is None:
                    continue

                try:
                    result = method(prompt)
                    if inspect.isawaitable(result):
                        result = await result

                    # Handle various response types
                    if hasattr(result, "content"):
                        return str(result.content)
                    if hasattr(result, "text"):
                        return str(result.text)
                    if isinstance(result, str):
                        return result
                    return str(result)
                except TypeError:
                    # Method exists but wrong signature
                    continue

            logger.warning("No compatible LLM method found")
            return ""

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    async def _get_communities_at_level(self, level: int) -> List[Dict[str, Any]]:
        """Get all communities at a specific hierarchy level."""
        return await self._execute_query(
            """
            MATCH (c:Community)
            WHERE c.level = $level AND c.summary IS NOT NULL
            RETURN c.id AS community_id,
                   c.level AS level,
                   c.summary AS summary,
                   coalesce(c.members, []) AS members,
                   c.memberCount AS member_count
            ORDER BY c.memberCount DESC
            """,
            level=level,
        )

    async def _get_child_communities(self, community_id: str) -> List[str]:
        """Get IDs of child communities."""
        records = await self._execute_query(
            """
            MATCH (parent:Community {id: $community_id})-[:HAS_SUBCOMMUNITY]->(child:Community)
            RETURN child.id AS child_id
            """,
            community_id=community_id,
        )
        return [r.get("child_id") for r in records if r.get("child_id")]

    async def _get_communities_by_ids(
        self, community_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get communities by their IDs."""
        if not community_ids:
            return []

        return await self._execute_query(
            """
            MATCH (c:Community)
            WHERE c.id IN $ids AND c.summary IS NOT NULL
            RETURN c.id AS community_id,
                   c.level AS level,
                   c.summary AS summary,
                   coalesce(c.members, []) AS members,
                   c.memberCount AS member_count
            ORDER BY c.memberCount DESC
            """,
            ids=community_ids,
        )

    async def _execute_query(self, query: str, **params: Any) -> List[Dict[str, Any]]:
        """Execute a Cypher query against Neo4j."""
        if self.driver is None:
            return []

        try:
            # Try different driver interfaces
            execute_query = getattr(self.driver, "execute_query", None)
            if callable(execute_query):
                result = execute_query(query, **params)
                if inspect.isawaitable(result):
                    result = await result
                return self._normalize_result(result)

            # Try session-based execution
            session_factory = getattr(self.driver, "session", None)
            if callable(session_factory):
                session = session_factory()
                if hasattr(session, "__aenter__"):
                    async with session as s:
                        result = await s.run(query, **params)
                        return self._normalize_result(result)
                elif hasattr(session, "__enter__"):
                    with session as s:
                        result = s.run(query, **params)
                        return self._normalize_result(result)

            return []

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return []

    def _normalize_result(self, result: Any) -> List[Dict[str, Any]]:
        """Normalize Neo4j result to list of dicts."""
        if result is None:
            return []

        if isinstance(result, tuple):
            result = result[0]

        if isinstance(result, list):
            return [self._to_dict(r) for r in result]

        data = getattr(result, "data", None)
        if callable(data):
            return [self._to_dict(r) for r in data()]

        if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
            return [self._to_dict(r) for r in result]

        return []

    def _to_dict(self, record: Any) -> Dict[str, Any]:
        """Convert a record to dict."""
        if isinstance(record, dict):
            return record
        data = getattr(record, "data", None)
        if callable(data):
            try:
                return data()
            except Exception:
                pass
        try:
            return dict(record)
        except Exception:
            return {}

    def _empty_result(self, query: str) -> GlobalSearchResult:
        """Create an empty result."""
        return GlobalSearchResult(
            query=query,
            response="No relevant information found in the knowledge graph.",
            themes=[],
            community_responses=[],
            hierarchy_levels_used=[],
            total_communities_queried=0,
            execution_time_ms=0.0,
        )

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache._cache),
            "ttl_seconds": self._cache._ttl,
        }


# Convenience function for quick global search
async def global_search(
    query: str,
    driver: Any,
    llm: Optional[LLMProtocol] = None,
    mode: GlobalSearchMode = GlobalSearchMode.DYNAMIC,
    **kwargs: Any,
) -> GlobalSearchResult:
    """
    Convenience function for quick global search.

    Args:
        query: The search query
        driver: Neo4j driver
        llm: Optional LLM for response generation
        mode: Search mode (STATIC, DYNAMIC, HIERARCHICAL)
        **kwargs: Additional GlobalSearchConfig parameters

    Returns:
        GlobalSearchResult
    """
    config = GlobalSearchConfig(mode=mode, **kwargs)
    search = GlobalSearch(driver, llm, config)
    return await search.search(query)


__all__ = [
    "GlobalSearch",
    "GlobalSearchConfig",
    "GlobalSearchMode",
    "GlobalSearchResult",
    "CommunityResponse",
    "ResponseType",
    "ResponseCache",
    "RateLimiter",
    "global_search",
]
