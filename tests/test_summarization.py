# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Tests for Unified Summarization System
======================================

Tests the ConversationSummary dataclass and UnifiedSummarizer class.
"""

import json
import os
from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from agentic_brain.memory.summarization import (
    ConversationSummary,
    SummaryType,
    UnifiedSummarizer,
)

# Skip flaky tests on CI - ConversationSummarizer wrapper test has import timing issues
CI_SKIP = pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
    reason="Summarization integration test flaky on CI due to import timing"
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_messages():
    """Sample conversation messages."""
    return [
        {"role": "user", "content": "Hello, can you help with SD-1330?"},
        {"role": "assistant", "content": "Of course! I'll look at that JIRA ticket."},
        {"role": "user", "content": "Steve mentioned we need unit tests."},
        {"role": "assistant", "content": "I'll add comprehensive unit tests."},
        {"role": "user", "content": "Great, also check the payment module."},
        {"role": "assistant", "content": "I'll review the payment module too."},
        {"role": "user", "content": "Thanks! Let me know when ready."},
        {"role": "assistant", "content": "Will do. Working on it now."},
    ]


@pytest.fixture
def sample_summary():
    """Sample ConversationSummary."""
    return ConversationSummary(
        id="abc123def456",
        session_id="session-789",
        summary_type=SummaryType.SESSION,
        content="Discussed PR review for SD-1330 with Steve. Need unit tests.",
        message_count=8,
        start_time=datetime(2026, 3, 20, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 3, 20, 10, 30, 0, tzinfo=UTC),
        topics=["PR review", "JIRA", "testing"],
        entities=["Steve", "SD-1330"],
        key_facts=["Need to add unit tests", "Approved for merge"],
        sentiment="positive",
        metadata={"reviewer": "Steve"},
    )


@pytest.fixture
def mock_llm_router():
    """Mock LLM router for testing."""
    router = AsyncMock()
    router.chat = AsyncMock(
        return_value="Summary: Discussed testing requirements for SD-1330."
    )
    return router


@pytest.fixture
def summarizer(mock_llm_router):
    """UnifiedSummarizer with mock LLM."""
    return UnifiedSummarizer(llm_router=mock_llm_router)


@pytest.fixture
def summarizer_no_llm():
    """UnifiedSummarizer without LLM."""
    return UnifiedSummarizer()


# =============================================================================
# ConversationSummary Dataclass Tests
# =============================================================================


class TestConversationSummary:
    """Tests for ConversationSummary dataclass."""

    def test_create_summary(self, sample_summary):
        """Test creating a ConversationSummary."""
        assert sample_summary.id == "abc123def456"
        assert sample_summary.session_id == "session-789"
        assert sample_summary.summary_type == SummaryType.SESSION
        assert "SD-1330" in sample_summary.content
        assert sample_summary.message_count == 8
        assert "PR review" in sample_summary.topics
        assert "Steve" in sample_summary.entities

    def test_to_dict(self, sample_summary):
        """Test converting summary to dict."""
        data = sample_summary.to_dict()

        assert isinstance(data, dict)
        assert data["id"] == "abc123def456"
        assert data["session_id"] == "session-789"
        assert data["summary_type"] == "session"
        assert data["message_count"] == 8
        assert isinstance(data["start_time"], str)
        assert isinstance(data["topics"], list)
        assert "PR review" in data["topics"]

    def test_from_dict(self, sample_summary):
        """Test creating summary from dict."""
        data = sample_summary.to_dict()
        restored = ConversationSummary.from_dict(data)

        assert restored.id == sample_summary.id
        assert restored.session_id == sample_summary.session_id
        assert restored.summary_type == sample_summary.summary_type
        assert restored.content == sample_summary.content
        assert restored.message_count == sample_summary.message_count
        assert restored.topics == sample_summary.topics
        assert restored.entities == sample_summary.entities

    def test_to_neo4j_format(self, sample_summary):
        """Test Neo4j-compatible format."""
        neo4j_data = sample_summary.to_neo4j()

        assert neo4j_data["id"] == "abc123def456"
        assert neo4j_data["session_id"] == "session-789"
        assert neo4j_data["summary_type"] == "session"
        # Lists should be JSON strings
        assert isinstance(neo4j_data["topics_json"], str)
        assert "PR review" in neo4j_data["topics_json"]
        topics = json.loads(neo4j_data["topics_json"])
        assert "PR review" in topics

    def test_from_neo4j(self, sample_summary):
        """Test creating from Neo4j record."""
        neo4j_data = sample_summary.to_neo4j()
        restored = ConversationSummary.from_neo4j(neo4j_data)

        assert restored.id == sample_summary.id
        assert restored.topics == sample_summary.topics
        assert restored.entities == sample_summary.entities

    def test_roundtrip_dict(self, sample_summary):
        """Test dict roundtrip preserves data."""
        data = sample_summary.to_dict()
        restored = ConversationSummary.from_dict(data)
        data2 = restored.to_dict()

        assert data == data2

    def test_summary_types(self):
        """Test all summary types."""
        assert SummaryType.REALTIME.value == "realtime"
        assert SummaryType.SESSION.value == "session"
        assert SummaryType.TOPIC.value == "topic"
        assert SummaryType.ENTITY.value == "entity"

    def test_default_lists(self):
        """Test that default lists are independent."""
        summary1 = ConversationSummary(
            id="1",
            session_id="s1",
            summary_type=SummaryType.SESSION,
            content="test",
            message_count=1,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        summary2 = ConversationSummary(
            id="2",
            session_id="s2",
            summary_type=SummaryType.SESSION,
            content="test",
            message_count=1,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        summary1.topics.append("test-topic")
        assert "test-topic" not in summary2.topics


# =============================================================================
# UnifiedSummarizer Tests
# =============================================================================


class TestUnifiedSummarizer:
    """Tests for UnifiedSummarizer class."""

    def test_init_defaults(self, summarizer_no_llm):
        """Test default initialization."""
        assert summarizer_no_llm.llm_router is None
        assert summarizer_no_llm.memory is None
        assert summarizer_no_llm.max_summary_tokens == 500

    def test_init_with_llm(self, summarizer, mock_llm_router):
        """Test initialization with LLM router."""
        assert summarizer.llm_router is mock_llm_router

    def test_should_compress_sync(self, summarizer_no_llm, sample_messages):
        """Test should_compress_sync method."""
        # 8 messages, threshold 20
        assert not summarizer_no_llm.should_compress_sync(sample_messages, threshold=20)

        # 8 messages, threshold 5
        assert summarizer_no_llm.should_compress_sync(sample_messages, threshold=5)

        # Empty list
        assert not summarizer_no_llm.should_compress_sync([], threshold=5)

    @pytest.mark.asyncio
    async def test_should_compress(self, summarizer_no_llm, sample_messages):
        """Test async should_compress method."""
        result = await summarizer_no_llm.should_compress(sample_messages, threshold=5)
        assert result is True

        result = await summarizer_no_llm.should_compress(sample_messages, threshold=20)
        assert result is False

    def test_messages_to_text(self, summarizer_no_llm, sample_messages):
        """Test _messages_to_text helper."""
        text = summarizer_no_llm._messages_to_text(sample_messages)

        assert "user: Hello" in text
        assert "assistant: Of course" in text
        assert "SD-1330" in text

    def test_extractive_summary(self, summarizer_no_llm, sample_messages):
        """Test extractive summary without LLM."""
        summary = summarizer_no_llm._extractive_summary(sample_messages)

        assert isinstance(summary, str)
        assert len(summary) > 0
        # Should mention start and end
        assert "Started with" in summary or "Hello" in summary

    def test_extractive_summary_empty(self, summarizer_no_llm):
        """Test extractive summary with empty messages."""
        summary = summarizer_no_llm._extractive_summary([])
        assert summary == "No messages"

    def test_extractive_summary_few_messages(self, summarizer_no_llm):
        """Test extractive summary with few messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        summary = summarizer_no_llm._extractive_summary(messages)

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_extract_keywords(self, summarizer_no_llm):
        """Test keyword extraction without LLM."""
        text = "The Python programming language is great for machine learning and data science projects."
        keywords = summarizer_no_llm._extract_keywords(text, max_keywords=3)

        assert isinstance(keywords, list)
        assert len(keywords) <= 3
        # Should extract meaningful words
        assert any(
            kw
            in [
                "python",
                "programming",
                "language",
                "machine",
                "learning",
                "data",
                "science",
                "projects",
            ]
            for kw in keywords
        )

    def test_extract_keywords_common_words_excluded(self, summarizer_no_llm):
        """Test that common words are excluded from keywords."""
        text = "The quick brown fox jumps over the lazy dog and then runs away quickly"
        keywords = summarizer_no_llm._extract_keywords(text, max_keywords=5)

        # Common words should be excluded
        assert "the" not in keywords
        assert "and" not in keywords
        assert "over" not in keywords

    def test_extract_capitalized_entities(self, summarizer_no_llm):
        """Test capitalized entity extraction."""
        text = "Steve Taylor met with Joseph Webber at CITB to discuss the project."
        entities = summarizer_no_llm._extract_capitalized_entities(text)

        assert isinstance(entities, list)
        # Should find Steve Taylor and Joseph Webber
        names = [e["name"] for e in entities]
        assert "Steve Taylor" in names or "Steve" in names

    def test_generate_id(self, summarizer_no_llm):
        """Test ID generation."""
        ts = datetime(2026, 3, 20, 10, 0, 0, tzinfo=UTC)

        id1 = summarizer_no_llm._generate_id("session-1", ts)
        id2 = summarizer_no_llm._generate_id("session-1", ts)
        id3 = summarizer_no_llm._generate_id("session-2", ts)

        # Same input -> same ID
        assert id1 == id2

        # Different input -> different ID
        assert id1 != id3

        # ID is proper length
        assert len(id1) == 16

    @pytest.mark.asyncio
    async def test_compress_conversation_no_compression_needed(self, summarizer_no_llm):
        """Test compress when messages below threshold."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        compressed, summary = await summarizer_no_llm.compress_conversation(
            messages, keep_recent=5
        )

        # No compression, same messages returned
        assert compressed == messages
        assert summary is None

    @pytest.mark.asyncio
    async def test_compress_conversation_with_compression(
        self, summarizer_no_llm, sample_messages
    ):
        """Test compression when messages exceed threshold."""
        compressed, summary = await summarizer_no_llm.compress_conversation(
            sample_messages, keep_recent=3
        )

        # Should be 1 summary + 3 recent
        assert len(compressed) == 4
        assert compressed[0]["role"] == "system"
        assert "Previous conversation summary" in compressed[0]["content"]
        assert summary is not None
        assert summary.summary_type == SummaryType.REALTIME

    @pytest.mark.asyncio
    async def test_generate_summary_without_llm(
        self, summarizer_no_llm, sample_messages
    ):
        """Test summary generation without LLM."""
        summary = await summarizer_no_llm._generate_summary(
            sample_messages, SummaryType.SESSION, session_id="test-session"
        )

        assert isinstance(summary, ConversationSummary)
        assert summary.session_id == "test-session"
        assert summary.summary_type == SummaryType.SESSION
        assert summary.message_count == 8
        assert len(summary.content) > 0

    @pytest.mark.asyncio
    async def test_generate_summary_with_llm(self, summarizer, sample_messages):
        """Test summary generation with LLM."""
        summary = await summarizer._generate_summary(
            sample_messages, SummaryType.SESSION, session_id="test-session"
        )

        assert isinstance(summary, ConversationSummary)
        assert "SD-1330" in summary.content or "Summary" in summary.content

    @pytest.mark.asyncio
    async def test_summarize_session(self, summarizer, sample_messages):
        """Test full session summarization."""
        # Mock extract_topics to avoid complex LLM calls
        with (
            patch.object(
                summarizer, "extract_topics", return_value=["testing", "JIRA"]
            ),
            patch.object(
                summarizer, "extract_key_facts", return_value=["Add unit tests"]
            ),
        ):
            summary = await summarizer.summarize_session("session-123", sample_messages)

        assert isinstance(summary, ConversationSummary)
        assert summary.session_id == "session-123"
        assert summary.summary_type == SummaryType.SESSION

    @pytest.mark.asyncio
    async def test_extract_topics_without_llm(self, summarizer_no_llm, sample_messages):
        """Test topic extraction fallback."""
        topics = await summarizer_no_llm.extract_topics(sample_messages, max_topics=3)

        assert isinstance(topics, list)
        assert len(topics) <= 3

    @pytest.mark.asyncio
    async def test_extract_topics_with_llm(
        self, summarizer, sample_messages, mock_llm_router
    ):
        """Test topic extraction with LLM."""
        mock_llm_router.chat.return_value = "testing, JIRA, payments"

        topics = await summarizer.extract_topics(sample_messages, max_topics=3)

        assert isinstance(topics, list)
        assert "testing" in topics or "JIRA" in topics

    @pytest.mark.asyncio
    async def test_extract_entities_without_llm(
        self, summarizer_no_llm, sample_messages
    ):
        """Test entity extraction fallback."""
        entities = await summarizer_no_llm.extract_entities(sample_messages)

        assert isinstance(entities, list)

    @pytest.mark.asyncio
    async def test_extract_key_facts_without_llm(
        self, summarizer_no_llm, sample_messages
    ):
        """Test key fact extraction without LLM."""
        facts = await summarizer_no_llm.extract_key_facts(sample_messages, max_facts=5)

        assert isinstance(facts, list)
        # Without LLM, returns empty list
        assert facts == []

    @pytest.mark.asyncio
    async def test_get_session_summary_no_memory(self, summarizer_no_llm):
        """Test getting session summary without memory configured."""
        result = await summarizer_no_llm.get_session_summary("session-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_summarize_old_no_memory(self, summarizer_no_llm):
        """Test auto-summarize without memory configured."""
        result = await summarizer_no_llm.auto_summarize_old()
        assert result == []


# =============================================================================
# Integration Tests
# =============================================================================


class TestSummarizationIntegration:
    """Integration tests for the summarization system."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, summarizer_no_llm, sample_messages):
        """Test complete summarization workflow."""
        # 1. Check if compression needed
        needs_compression = await summarizer_no_llm.should_compress(
            sample_messages, threshold=5
        )
        assert needs_compression is True

        # 2. Compress conversation
        compressed, summary = await summarizer_no_llm.compress_conversation(
            sample_messages, keep_recent=3
        )
        assert len(compressed) == 4
        assert summary is not None

        # 3. Verify summary can be serialized
        data = summary.to_dict()
        restored = ConversationSummary.from_dict(data)
        assert restored.content == summary.content

    @CI_SKIP
    @pytest.mark.asyncio
    async def test_conversation_summarizer_wrapper(self, sample_messages):
        """Test ConversationSummarizer wraps UnifiedSummarizer correctly."""
        from agentic_brain.chat.intelligence import ConversationSummarizer

        summarizer = ConversationSummarizer(max_tokens=500)

        # Test should_summarize
        assert summarizer.should_summarize(sample_messages, threshold=5) is True
        assert summarizer.should_summarize(sample_messages, threshold=20) is False

        # Test compress_history
        compressed = await summarizer.compress_history(sample_messages, keep_recent=3)
        assert len(compressed) == 4
        assert compressed[0]["role"] == "system"

        # Test summarize
        summary_text = await summarizer.summarize(sample_messages)
        assert isinstance(summary_text, str)
        assert len(summary_text) > 0

        # Test unified property
        assert summarizer.unified is not None
        assert summarizer.unified.__class__.__name__ == "UnifiedSummarizer"

    @pytest.mark.asyncio
    async def test_empty_messages(self, summarizer_no_llm):
        """Test handling of empty message list."""
        compressed, summary = await summarizer_no_llm.compress_conversation(
            [], keep_recent=5
        )
        assert compressed == []
        assert summary is None

        summary = await summarizer_no_llm._generate_summary([], SummaryType.SESSION)
        assert summary.message_count == 0
        assert summary.content == "No messages"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_summary_with_empty_lists(self):
        """Test summary with all empty lists."""
        summary = ConversationSummary(
            id="test",
            session_id="test",
            summary_type=SummaryType.SESSION,
            content="test",
            message_count=0,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        data = summary.to_dict()
        assert data["topics"] == []
        assert data["entities"] == []

        neo4j_data = summary.to_neo4j()
        assert neo4j_data["topics_json"] == "[]"

    def test_summary_type_from_string(self):
        """Test SummaryType enum from string."""
        assert SummaryType("realtime") == SummaryType.REALTIME
        assert SummaryType("session") == SummaryType.SESSION

        with pytest.raises(ValueError):
            SummaryType("invalid")

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, sample_messages):
        """Test fallback when LLM fails."""
        # Create LLM that raises
        failing_llm = AsyncMock()
        failing_llm.chat.side_effect = Exception("LLM unavailable")

        summarizer = UnifiedSummarizer(llm_router=failing_llm)

        # Should fallback to extractive summary
        summary = await summarizer._generate_summary(
            sample_messages, SummaryType.SESSION
        )

        assert isinstance(summary, ConversationSummary)
        assert len(summary.content) > 0

    @pytest.mark.asyncio
    async def test_special_characters_in_messages(self, summarizer_no_llm):
        """Test handling special characters."""
        messages = [
            {"role": "user", "content": "Check PR #123 for SD-1330"},
            {"role": "assistant", "content": "Looking at https://example.com/pr/123"},
            {
                "role": "user",
                "content": "Error: 'NullPointerException' in com.citb.module",
            },
        ]

        summary = await summarizer_no_llm._generate_summary(
            messages, SummaryType.SESSION
        )

        assert isinstance(summary.content, str)

    @pytest.mark.asyncio
    async def test_very_long_messages(self, summarizer_no_llm):
        """Test handling very long messages."""
        long_content = "x" * 10000
        messages = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": "OK"},
        ]

        summary = await summarizer_no_llm._generate_summary(
            messages, SummaryType.SESSION
        )

        assert isinstance(summary.content, str)
        # Extractive summary without LLM includes the full message
        # This is expected behavior - LLM would truncate/summarize
        assert len(summary.content) > 0
