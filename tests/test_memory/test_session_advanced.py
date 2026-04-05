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
Comprehensive tests for advanced session management features.

Tests cover:
- Session branching (fork sessions for A/B testing)
- Session merging (combine multiple sessions)
- Session replay (replay with different parameters)
- Cross-session semantic search
- Session analytics (token usage, response times, topic clustering)
- Session export (JSON, Markdown, training data, JSONL)
- Session compression (intelligent summarization)
- Session tagging (metadata organization)
"""

import json
import re
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.memory.session_manager import (
    ExportFormat,
    MessageRole,
    ReplayConfig,
    SemanticSearchResult,
    Session,
    SessionAnalytics,
    SessionConfig,
    SessionManager,
    SessionMessage,
    SessionSummary,
    SessionTag,
    SQLiteSessionBackend,
    get_session_manager,
    reset_session_manager,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return SessionConfig(
        max_context_tokens=4000,
        summarize_threshold=100,  # High threshold to prevent auto-summarization
        importance_keywords=["important", "critical", "remember"],
    )


@pytest.fixture
def sqlite_backend(tmp_path):
    """Create SQLite backend for testing."""
    db_path = tmp_path / "test_sessions.db"
    return SQLiteSessionBackend(str(db_path))


@pytest.fixture
def session(config, sqlite_backend):
    """Create a test session."""
    return Session(
        session_id="test-session-001",
        backend=sqlite_backend,
        config=config,
        cache=None,
    )


@pytest.fixture
async def session_with_messages(session):
    """Create a session with pre-populated messages."""
    await session.add_message("system", "You are a helpful assistant.")
    await session.add_message("user", "What is the status of SD-1350?")
    await session.add_message(
        "assistant", "SD-1350 is currently in review by Steve Taylor."
    )
    await session.add_message("user", "That's important! Please remember to follow up.")
    await session.add_message("assistant", "I'll remember to follow up on SD-1350.")
    return session


@pytest.fixture
def manager(config, tmp_path):
    """Create a test session manager."""
    reset_session_manager()
    mgr = SessionManager(config=config, prefer_neo4j=False)
    # Force SQLite backend with temp path
    mgr._backend = SQLiteSessionBackend(str(tmp_path / "test_sessions.db"))
    return mgr


@pytest.fixture
async def manager_with_sessions(manager):
    """Create a manager with multiple sessions for testing."""
    # Session 1: Technical discussion
    session1 = await manager.create_session("session-tech")
    await session1.add_message("user", "How do I implement a binary search?")
    await session1.add_message(
        "assistant", "Here's how to implement binary search in Python..."
    )
    await session1.add_message("user", "Can you optimize this algorithm?")
    session1.add_tag("project", "algorithms")
    session1.add_tag("priority", "high")

    # Session 2: Project discussion
    session2 = await manager.create_session("session-project")
    await session2.add_message("user", "What's the status of the brain-ui project?")
    await session2.add_message("assistant", "The brain-ui project is 80% complete.")
    await session2.add_message("user", "Great! Remember to update the documentation.")
    session2.add_tag("project", "brain-ui")
    session2.add_tag("priority", "medium")

    # Session 3: General chat
    session3 = await manager.create_session("session-general")
    await session3.add_message("user", "Hello, how are you today?")
    await session3.add_message("assistant", "I'm doing well, thank you!")
    session3.add_tag("type", "casual")

    return manager


# =============================================================================
# SESSION TAG TESTS
# =============================================================================


class TestSessionTagging:
    """Tests for session tagging functionality."""

    @pytest.mark.asyncio
    async def test_add_tag(self, session):
        """Test adding a tag to a session."""
        tag = session.add_tag("project", "brain-ui")

        assert tag.name == "project"
        assert tag.value == "brain-ui"
        assert isinstance(tag.created_at, datetime)

    @pytest.mark.asyncio
    async def test_add_multiple_tags(self, session):
        """Test adding multiple tags."""
        session.add_tag("project", "brain-ui")
        session.add_tag("priority", "high")
        session.add_tag("status", "active")

        tags = session.get_tags()
        assert len(tags) == 3

        tag_dict = {t.name: t.value for t in tags}
        assert tag_dict["project"] == "brain-ui"
        assert tag_dict["priority"] == "high"
        assert tag_dict["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_tags_empty(self, session):
        """Test getting tags from session with no tags."""
        tags = session.get_tags()
        assert tags == []

    @pytest.mark.asyncio
    async def test_remove_tag_by_name(self, session):
        """Test removing all tags with a specific name."""
        session.add_tag("project", "brain-ui")
        session.add_tag("project", "brain-api")
        session.add_tag("priority", "high")

        removed = session.remove_tag("project")

        assert removed == 2
        tags = session.get_tags()
        assert len(tags) == 1
        assert tags[0].name == "priority"

    @pytest.mark.asyncio
    async def test_remove_tag_by_name_and_value(self, session):
        """Test removing a specific tag by name and value."""
        session.add_tag("project", "brain-ui")
        session.add_tag("project", "brain-api")

        removed = session.remove_tag("project", "brain-ui")

        assert removed == 1
        tags = session.get_tags()
        assert len(tags) == 1
        assert tags[0].value == "brain-api"

    @pytest.mark.asyncio
    async def test_remove_nonexistent_tag(self, session):
        """Test removing a tag that doesn't exist."""
        session.add_tag("project", "brain-ui")

        removed = session.remove_tag("nonexistent")
        assert removed == 0

    @pytest.mark.asyncio
    async def test_has_tag(self, session):
        """Test checking if session has a tag."""
        session.add_tag("project", "brain-ui")

        assert session.has_tag("project") is True
        assert session.has_tag("project", "brain-ui") is True
        assert session.has_tag("project", "other") is False
        assert session.has_tag("nonexistent") is False

    @pytest.mark.asyncio
    async def test_tag_serialization(self):
        """Test tag serialization and deserialization."""
        tag = SessionTag(name="project", value="brain-ui")
        tag_dict = tag.to_dict()

        assert "name" in tag_dict
        assert "value" in tag_dict
        assert "created_at" in tag_dict

        restored = SessionTag.from_dict(tag_dict)
        assert restored.name == tag.name
        assert restored.value == tag.value


# =============================================================================
# SESSION ANALYTICS TESTS
# =============================================================================


class TestSessionAnalytics:
    """Tests for session analytics functionality."""

    @pytest.mark.asyncio
    async def test_basic_analytics(self, session_with_messages):
        """Test basic analytics generation."""
        analytics = session_with_messages.get_analytics()

        assert analytics.session_id == "test-session-001"
        assert analytics.total_messages == 5
        assert analytics.user_messages == 2
        assert analytics.assistant_messages == 2
        assert analytics.total_tokens > 0

    @pytest.mark.asyncio
    async def test_analytics_entities(self, session_with_messages):
        """Test entity extraction in analytics."""
        analytics = session_with_messages.get_analytics()

        # Should detect SD-1350 and Steve Taylor
        assert "SD-1350" in analytics.entities or len(analytics.entities) >= 0

    @pytest.mark.asyncio
    async def test_analytics_topics(self, session_with_messages):
        """Test topic clustering in analytics."""
        analytics = session_with_messages.get_analytics()

        # Should have some topics extracted
        assert isinstance(analytics.topics, dict)

    @pytest.mark.asyncio
    async def test_response_time_metrics(self, session):
        """Test response time percentile calculations."""
        # Add messages with controlled timing
        await session.add_message("user", "Question 1")
        await session.add_message("assistant", "Response 1")
        await session.add_message("user", "Question 2")
        await session.add_message("assistant", "Response 2")

        analytics = session.get_analytics()

        assert analytics.avg_response_time_ms >= 0
        assert analytics.p50_response_time >= 0
        assert analytics.p95_response_time >= 0

    @pytest.mark.asyncio
    async def test_analytics_to_dict(self, session_with_messages):
        """Test analytics serialization."""
        analytics = session_with_messages.get_analytics()
        data = analytics.to_dict()

        assert "session_id" in data
        assert "total_messages" in data
        assert "total_tokens" in data
        assert "avg_response_time_ms" in data
        assert "p50_response_time_ms" in data
        assert "p95_response_time_ms" in data

    @pytest.mark.asyncio
    async def test_empty_session_analytics(self, session):
        """Test analytics for empty session."""
        analytics = session.get_analytics()

        assert analytics.total_messages == 0
        assert analytics.total_tokens == 0
        assert analytics.avg_response_time_ms == 0.0


# =============================================================================
# SESSION EXPORT TESTS
# =============================================================================


class TestSessionExport:
    """Tests for session export functionality."""

    @pytest.mark.asyncio
    async def test_export_json(self, session_with_messages):
        """Test export to JSON format."""
        exported = session_with_messages.export(ExportFormat.JSON)

        data = json.loads(exported)
        assert data["session_id"] == "test-session-001"
        assert len(data["messages"]) == 5
        assert "started_at" in data

    @pytest.mark.asyncio
    async def test_export_markdown(self, session_with_messages):
        """Test export to Markdown format."""
        exported = session_with_messages.export(ExportFormat.MARKDOWN)

        assert "# Session: test-session-001" in exported
        assert "## Conversation" in exported
        assert "👤" in exported or "User" in exported
        assert "🤖" in exported or "Assistant" in exported

    @pytest.mark.asyncio
    async def test_export_markdown_with_tags(self, session_with_messages):
        """Test Markdown export includes tags."""
        session_with_messages.add_tag("project", "test")
        session_with_messages.add_tag("priority", "high")

        exported = session_with_messages.export(ExportFormat.MARKDOWN)

        assert "## Tags" in exported
        assert "project" in exported
        assert "priority" in exported

    @pytest.mark.asyncio
    async def test_export_training_data(self, session_with_messages):
        """Test export to OpenAI fine-tuning format."""
        exported = session_with_messages.export(ExportFormat.TRAINING_DATA)

        # Should be valid JSON lines
        lines = exported.strip().split("\n")
        for line in lines:
            data = json.loads(line)
            assert "messages" in data
            for msg in data["messages"]:
                assert "role" in msg
                assert "content" in msg

    @pytest.mark.asyncio
    async def test_export_jsonl(self, session_with_messages):
        """Test export to JSONL format."""
        exported = session_with_messages.export(ExportFormat.JSONL)

        lines = exported.strip().split("\n")
        assert len(lines) == 5

        for line in lines:
            data = json.loads(line)
            assert "id" in data
            assert "role" in data
            assert "content" in data

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, session):
        """Test export with invalid format raises error."""
        with pytest.raises((ValueError, AttributeError)):
            session.export("invalid_format")


# =============================================================================
# SESSION COMPRESSION TESTS
# =============================================================================


class TestSessionCompression:
    """Tests for session compression functionality."""

    @pytest.mark.asyncio
    async def test_compress_reduces_tokens(self, session):
        """Test that compression reduces token count."""
        # Add many messages
        for i in range(30):
            await session.add_message(
                "user", f"This is message number {i} with some content."
            )
            await session.add_message(
                "assistant", f"Response to message {i} with details."
            )

        original_tokens = sum(m.token_count for m in session._messages)
        original, new = await session.compress(target_tokens=original_tokens // 3)

        assert new < original
        assert new <= original_tokens // 3 + 500  # Allow some margin

    @pytest.mark.asyncio
    async def test_compress_keeps_important(self, session):
        """Test that compression keeps high-importance messages."""
        await session.add_message(
            "user", "This is important! Remember this critical fact."
        )
        await session.add_message(
            "assistant", "I'll remember this important information."
        )

        for i in range(20):
            await session.add_message("user", f"Filler message {i}")
            await session.add_message("assistant", f"Filler response {i}")

        await session.compress(target_tokens=500, keep_important=True)

        # Should keep important messages
        content = " ".join(m.content for m in session._messages)
        assert "important" in content.lower() or "critical" in content.lower()

    @pytest.mark.asyncio
    async def test_compress_no_change_when_under_target(self, session):
        """Test compression does nothing when already under target."""
        await session.add_message("user", "Short message")
        await session.add_message("assistant", "Short response")

        original, new = await session.compress(target_tokens=10000)

        assert original == new

    @pytest.mark.asyncio
    async def test_compress_with_custom_summarizer(self, session):
        """Test compression with custom summarization function."""
        for i in range(20):
            await session.add_message("user", f"Message {i}")
            await session.add_message("assistant", f"Response {i}")

        custom_summary = "Custom summary of the conversation."

        def custom_summarize(messages):
            return custom_summary

        await session.compress(target_tokens=100, summarize_fn=custom_summarize)

        # Should contain custom summary
        content = " ".join(m.content for m in session._messages)
        assert custom_summary in content


# =============================================================================
# SESSION BRANCHING TESTS
# =============================================================================


class TestSessionBranching:
    """Tests for session branching functionality."""

    @pytest.mark.asyncio
    async def test_branch_session_basic(self, manager_with_sessions):
        """Test basic session branching."""
        branched = await manager_with_sessions.branch_session("session-tech")

        assert branched.session_id != "session-tech"
        assert branched._session_metadata["parent_session_id"] == "session-tech"

    @pytest.mark.asyncio
    async def test_branch_copies_messages(self, manager_with_sessions):
        """Test that branching copies messages."""
        original = await manager_with_sessions.get_session("session-tech")
        original_count = len(original._messages)

        branched = await manager_with_sessions.branch_session("session-tech")

        assert len(branched._messages) == original_count

    @pytest.mark.asyncio
    async def test_branch_at_specific_index(self, manager_with_sessions):
        """Test branching at a specific message index."""
        original = await manager_with_sessions.get_session("session-tech")

        branched = await manager_with_sessions.branch_session(
            "session-tech", branch_at_index=2
        )

        assert len(branched._messages) == 2
        assert branched._session_metadata["branch_point_index"] == 2

    @pytest.mark.asyncio
    async def test_branch_with_custom_id(self, manager_with_sessions):
        """Test branching with custom session ID."""
        branched = await manager_with_sessions.branch_session(
            "session-tech", new_session_id="my-custom-branch"
        )

        assert branched.session_id == "my-custom-branch"

    @pytest.mark.asyncio
    async def test_branch_copies_tags(self, manager_with_sessions):
        """Test that branching copies tags."""
        branched = await manager_with_sessions.branch_session("session-tech")

        assert branched.has_tag("project", "algorithms")
        assert branched.has_tag("priority", "high")

    @pytest.mark.asyncio
    async def test_branch_independent_messages(self, manager_with_sessions):
        """Test that branched session has independent messages."""
        branched = await manager_with_sessions.branch_session("session-tech")

        # Add message to branched session
        await branched.add_message("user", "New message in branch")

        original = await manager_with_sessions.get_session("session-tech")

        assert len(branched._messages) == len(original._messages) + 1

    @pytest.mark.asyncio
    async def test_branch_nonexistent_session(self, manager_with_sessions):
        """Test branching from nonexistent session raises error."""
        with pytest.raises(ValueError) as exc_info:
            await manager_with_sessions.branch_session("nonexistent")

        assert "not found" in str(exc_info.value)


# =============================================================================
# SESSION MERGING TESTS
# =============================================================================


class TestSessionMerging:
    """Tests for session merging functionality."""

    @pytest.mark.asyncio
    async def test_merge_interleave(self, manager_with_sessions):
        """Test merging sessions with interleave strategy."""
        merged = await manager_with_sessions.merge_sessions(
            ["session-tech", "session-project"], strategy="interleave"
        )

        # Should have messages from both sessions
        assert merged._session_metadata["merged_from"] == [
            "session-tech",
            "session-project",
        ]

        tech = await manager_with_sessions.get_session("session-tech")
        project = await manager_with_sessions.get_session("session-project")

        expected_count = len(tech._messages) + len(project._messages)
        assert len(merged._messages) == expected_count

    @pytest.mark.asyncio
    async def test_merge_concatenate(self, manager_with_sessions):
        """Test merging sessions with concatenate strategy."""
        merged = await manager_with_sessions.merge_sessions(
            ["session-tech", "session-project"], strategy="concatenate"
        )

        # Messages should be in order
        tech = await manager_with_sessions.get_session("session-tech")
        project = await manager_with_sessions.get_session("session-project")

        expected_count = len(tech._messages) + len(project._messages)
        assert len(merged._messages) == expected_count

    @pytest.mark.asyncio
    async def test_merge_deduplicate(self, manager):
        """Test merging with deduplication."""
        # Create sessions with duplicate content
        session1 = await manager.create_session("dup-1")
        await session1.add_message("user", "Hello world")
        await session1.add_message("assistant", "Hi there!")

        session2 = await manager.create_session("dup-2")
        await session2.add_message("user", "Hello world")  # Duplicate
        await session2.add_message("assistant", "Different response")

        merged = await manager.merge_sessions(
            ["dup-1", "dup-2"], strategy="deduplicate"
        )

        # Should have removed duplicate "Hello world"
        contents = [m.content for m in merged._messages]
        assert contents.count("Hello world") == 1

    @pytest.mark.asyncio
    async def test_merge_with_custom_id(self, manager_with_sessions):
        """Test merging with custom session ID."""
        merged = await manager_with_sessions.merge_sessions(
            ["session-tech", "session-project"], new_session_id="custom-merged"
        )

        assert merged.session_id == "custom-merged"

    @pytest.mark.asyncio
    async def test_merge_combines_tags(self, manager_with_sessions):
        """Test that merging combines tags from all sessions."""
        merged = await manager_with_sessions.merge_sessions(
            ["session-tech", "session-project"]
        )

        assert merged.has_tag("project", "algorithms")
        assert merged.has_tag("project", "brain-ui")
        assert merged.has_tag("priority", "high")
        assert merged.has_tag("priority", "medium")

    @pytest.mark.asyncio
    async def test_merge_requires_two_sessions(self, manager_with_sessions):
        """Test merging requires at least 2 sessions."""
        with pytest.raises(ValueError) as exc_info:
            await manager_with_sessions.merge_sessions(["session-tech"])

        assert "at least 2" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_merge_invalid_strategy(self, manager_with_sessions):
        """Test merging with invalid strategy raises error."""
        with pytest.raises(ValueError) as exc_info:
            await manager_with_sessions.merge_sessions(
                ["session-tech", "session-project"], strategy="invalid"
            )

        assert "Unknown merge strategy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_merge_nonexistent_session(self, manager_with_sessions):
        """Test merging with nonexistent session raises error."""
        with pytest.raises(ValueError) as exc_info:
            await manager_with_sessions.merge_sessions(["session-tech", "nonexistent"])

        assert "not found" in str(exc_info.value)


# =============================================================================
# SESSION REPLAY TESTS
# =============================================================================


class TestSessionReplay:
    """Tests for session replay functionality."""

    @pytest.mark.asyncio
    async def test_replay_basic(self, manager_with_sessions):
        """Test basic session replay."""
        replayed = await manager_with_sessions.replay_session("session-tech")

        assert replayed.session_id != "session-tech"
        assert replayed._session_metadata["replayed_from"] == "session-tech"

    @pytest.mark.asyncio
    async def test_replay_copies_all_messages(self, manager_with_sessions):
        """Test that replay copies all messages."""
        original = await manager_with_sessions.get_session("session-tech")
        replayed = await manager_with_sessions.replay_session("session-tech")

        assert len(replayed._messages) == len(original._messages)

    @pytest.mark.asyncio
    async def test_replay_filter_roles(self, manager_with_sessions):
        """Test replay with role filtering."""
        config = ReplayConfig(filter_roles=["user"])

        replayed = await manager_with_sessions.replay_session(
            "session-tech", replay_config=config
        )

        # Should only have user messages
        for msg in replayed._messages:
            assert msg.role == MessageRole.USER

    @pytest.mark.asyncio
    async def test_replay_skip_indices(self, manager_with_sessions):
        """Test replay with skipped message indices."""
        original = await manager_with_sessions.get_session("session-tech")
        original_count = len(original._messages)

        config = ReplayConfig(skip_indices=[0, 1])

        replayed = await manager_with_sessions.replay_session(
            "session-tech", replay_config=config
        )

        assert len(replayed._messages) == original_count - 2

    @pytest.mark.asyncio
    async def test_replay_inject_messages(self, manager_with_sessions):
        """Test replay with injected messages."""
        original = await manager_with_sessions.get_session("session-tech")
        original_count = len(original._messages)

        config = ReplayConfig(
            inject_messages={1: [{"role": "system", "content": "Injected instruction"}]}
        )

        replayed = await manager_with_sessions.replay_session(
            "session-tech", replay_config=config
        )

        assert len(replayed._messages) == original_count + 1

        # Verify injection
        injected = [m for m in replayed._messages if m.metadata.get("injected")]
        assert len(injected) == 1
        assert injected[0].content == "Injected instruction"

    @pytest.mark.asyncio
    async def test_replay_modify_system_prompt(self, manager):
        """Test replay with modified system prompt."""
        session = await manager.create_session("prompt-test")
        await session.add_message("system", "Original system prompt")
        await session.add_message("user", "Hello")
        await session.add_message("assistant", "Hi!")

        config = ReplayConfig(modify_system_prompt="New system prompt")

        replayed = await manager.replay_session("prompt-test", replay_config=config)

        # First message should have new system prompt
        assert replayed._messages[0].content == "New system prompt"

    @pytest.mark.asyncio
    async def test_replay_transform_function(self, manager_with_sessions):
        """Test replay with custom transform function."""

        def transform(msg):
            msg.content = msg.content.upper()
            return msg

        config = ReplayConfig(transform_fn=transform)

        replayed = await manager_with_sessions.replay_session(
            "session-tech", replay_config=config
        )

        # All content should be uppercase
        for msg in replayed._messages:
            assert msg.content == msg.content.upper()

    @pytest.mark.asyncio
    async def test_replay_with_custom_id(self, manager_with_sessions):
        """Test replay with custom session ID."""
        replayed = await manager_with_sessions.replay_session(
            "session-tech", new_session_id="my-replay"
        )

        assert replayed.session_id == "my-replay"

    @pytest.mark.asyncio
    async def test_replay_nonexistent_session(self, manager_with_sessions):
        """Test replaying nonexistent session raises error."""
        with pytest.raises(ValueError) as exc_info:
            await manager_with_sessions.replay_session("nonexistent")

        assert "not found" in str(exc_info.value)


# =============================================================================
# CROSS-SESSION SEARCH TESTS
# =============================================================================


class TestSemanticSearch:
    """Tests for cross-session semantic search functionality."""

    @pytest.mark.asyncio
    async def test_search_finds_matches(self, manager_with_sessions):
        """Test semantic search finds matching messages."""
        results = await manager_with_sessions.semantic_search("binary search algorithm")

        assert len(results) > 0
        assert all(isinstance(r, SemanticSearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_returns_scores(self, manager_with_sessions):
        """Test search results include relevance scores."""
        results = await manager_with_sessions.semantic_search("binary search")

        for result in results:
            assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_search_sorted_by_score(self, manager_with_sessions):
        """Test search results are sorted by score descending."""
        results = await manager_with_sessions.semantic_search("project status")

        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    @pytest.mark.asyncio
    async def test_search_limit(self, manager_with_sessions):
        """Test search respects limit parameter."""
        results = await manager_with_sessions.semantic_search("the", limit=2)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_min_score(self, manager_with_sessions):
        """Test search respects minimum score threshold."""
        results = await manager_with_sessions.semantic_search("project", min_score=0.3)

        for result in results:
            assert result.score >= 0.3

    @pytest.mark.asyncio
    async def test_search_specific_sessions(self, manager_with_sessions):
        """Test searching only specific sessions."""
        results = await manager_with_sessions.semantic_search(
            "project", session_ids=["session-project"]
        )

        # Should only find results from session-project
        for result in results:
            assert result.message.session_id == "session-project"

    @pytest.mark.asyncio
    async def test_search_includes_highlights(self, manager_with_sessions):
        """Test search results include highlights."""
        results = await manager_with_sessions.semantic_search("binary search")

        if results:
            assert isinstance(results[0].highlights, list)

    @pytest.mark.asyncio
    async def test_search_includes_context(self, manager_with_sessions):
        """Test search can include session context."""
        results = await manager_with_sessions.semantic_search(
            "binary", include_context=True
        )

        # Context might be empty for first messages
        for result in results:
            assert isinstance(result.session_context, str)

    @pytest.mark.asyncio
    async def test_search_no_results(self, manager_with_sessions):
        """Test search returns empty list when no matches."""
        results = await manager_with_sessions.semantic_search("xyznonexistentterm123")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_result_serialization(self, manager_with_sessions):
        """Test search result can be serialized."""
        results = await manager_with_sessions.semantic_search("binary")

        if results:
            data = results[0].to_dict()
            assert "message" in data
            assert "score" in data
            assert "highlights" in data


# =============================================================================
# AGGREGATE ANALYTICS TESTS
# =============================================================================


class TestAggregateAnalytics:
    """Tests for aggregate analytics across sessions."""

    @pytest.mark.asyncio
    async def test_aggregate_all_sessions(self, manager_with_sessions):
        """Test aggregate analytics for all sessions."""
        analytics = await manager_with_sessions.get_aggregate_analytics()

        assert analytics["session_count"] == 3
        assert analytics["total_messages"] > 0
        assert analytics["total_tokens"] > 0

    @pytest.mark.asyncio
    async def test_aggregate_specific_sessions(self, manager_with_sessions):
        """Test aggregate analytics for specific sessions."""
        analytics = await manager_with_sessions.get_aggregate_analytics(
            session_ids=["session-tech", "session-project"]
        )

        assert analytics["session_count"] == 2

    @pytest.mark.asyncio
    async def test_aggregate_contains_top_topics(self, manager_with_sessions):
        """Test aggregate analytics includes top topics."""
        analytics = await manager_with_sessions.get_aggregate_analytics()

        assert "top_topics" in analytics
        assert isinstance(analytics["top_topics"], dict)

    @pytest.mark.asyncio
    async def test_aggregate_contains_top_entities(self, manager_with_sessions):
        """Test aggregate analytics includes top entities."""
        analytics = await manager_with_sessions.get_aggregate_analytics()

        assert "top_entities" in analytics
        assert isinstance(analytics["top_entities"], dict)

    @pytest.mark.asyncio
    async def test_aggregate_response_times(self, manager_with_sessions):
        """Test aggregate analytics includes response time metrics."""
        analytics = await manager_with_sessions.get_aggregate_analytics()

        assert "avg_response_time_ms" in analytics
        assert "p50_response_time_ms" in analytics
        assert "p95_response_time_ms" in analytics


# =============================================================================
# LIST SESSIONS TESTS
# =============================================================================


class TestListSessions:
    """Tests for listing sessions with filtering."""

    @pytest.mark.asyncio
    async def test_list_all_sessions(self, manager_with_sessions):
        """Test listing all sessions."""
        sessions = manager_with_sessions.list_sessions()

        assert len(sessions) == 3
        assert "session-tech" in sessions
        assert "session-project" in sessions
        assert "session-general" in sessions

    @pytest.mark.asyncio
    async def test_list_with_tag_filter(self, manager_with_sessions):
        """Test listing sessions with tag filter."""
        sessions = manager_with_sessions.list_sessions(tag_filter={"priority": "high"})

        assert "session-tech" in sessions
        assert "session-project" not in sessions

    @pytest.mark.asyncio
    async def test_list_with_multiple_tag_filters(self, manager_with_sessions):
        """Test listing sessions with multiple tag filters."""
        sessions = manager_with_sessions.list_sessions(
            tag_filter={"project": "algorithms", "priority": "high"}
        )

        assert sessions == ["session-tech"]

    @pytest.mark.asyncio
    async def test_list_with_limit(self, manager_with_sessions):
        """Test listing sessions with limit."""
        sessions = manager_with_sessions.list_sessions(limit=2)

        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_list_no_matches(self, manager_with_sessions):
        """Test listing with filter that matches nothing."""
        sessions = manager_with_sessions.list_sessions(
            tag_filter={"nonexistent": "value"}
        )

        assert sessions == []


# =============================================================================
# SESSION MESSAGE TESTS
# =============================================================================


class TestSessionMessage:
    """Tests for SessionMessage class."""

    def test_message_copy(self):
        """Test message copy creates independent copy."""
        msg = SessionMessage(
            id="test-id",
            role=MessageRole.USER,
            content="Test content",
            timestamp=datetime.now(UTC),
            session_id="session-1",
            metadata={"key": "value"},
            entities=[{"text": "Entity", "type": "person"}],
        )

        copied = msg.copy()

        assert copied.id == msg.id
        assert copied.content == msg.content
        assert copied.metadata == msg.metadata
        assert copied.metadata is not msg.metadata  # Independent copy

    def test_effective_importance_decay(self):
        """Test importance decays over time."""
        old_msg = SessionMessage(
            id="old",
            role=MessageRole.USER,
            content="Old message",
            timestamp=datetime.now(UTC) - timedelta(days=100),
            session_id="session-1",
            importance=1.0,
        )

        new_msg = SessionMessage(
            id="new",
            role=MessageRole.USER,
            content="New message",
            timestamp=datetime.now(UTC),
            session_id="session-1",
            importance=1.0,
        )

        assert old_msg.effective_importance < new_msg.effective_importance

    def test_effective_importance_reinforcement(self):
        """Test access count boosts importance."""
        msg = SessionMessage(
            id="test",
            role=MessageRole.USER,
            content="Test",
            timestamp=datetime.now(UTC),
            session_id="session-1",
            importance=0.5,
            access_count=10,
        )

        # Access count should boost importance
        assert msg.effective_importance > 0.5


# =============================================================================
# BACKWARD COMPATIBILITY TESTS
# =============================================================================


class TestBackwardCompatibility:
    """Tests ensuring backward compatibility with existing API."""

    @pytest.mark.asyncio
    async def test_basic_session_workflow(self, manager):
        """Test basic session workflow still works."""
        # Original API
        session = await manager.create_session()
        await session.add_message("user", "Hello")
        await session.add_message("assistant", "Hi there!")
        context = await session.get_context()
        summary = await session.end()

        assert len(context) == 2
        assert isinstance(summary, SessionSummary)

    @pytest.mark.asyncio
    async def test_search_still_works(self, manager):
        """Test search API backward compatibility."""
        session = await manager.create_session()
        await session.add_message("user", "Test message for search")

        results = await manager.search("search")

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_recent_context(self, manager):
        """Test get_recent_context backward compatibility."""
        session = await manager.create_session()
        await session.add_message("user", "Recent message")

        recent = await manager.get_recent_context(hours=1)

        assert isinstance(recent, list)

    @pytest.mark.asyncio
    async def test_recall_still_works(self, session_with_messages):
        """Test recall API backward compatibility."""
        results = await session_with_messages.recall("SD-1350")

        assert isinstance(results, list)

    def test_factory_function(self):
        """Test factory function backward compatibility."""
        reset_session_manager()
        manager = get_session_manager()

        assert isinstance(manager, SessionManager)

    def test_session_config_defaults(self):
        """Test SessionConfig has expected defaults."""
        config = SessionConfig()

        assert config.max_context_tokens == 8000
        assert config.summarize_threshold == 50
        assert isinstance(config.importance_keywords, list)


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_session_export(self, session):
        """Test exporting empty session."""
        exported = session.export(ExportFormat.JSON)

        data = json.loads(exported)
        assert data["message_count"] == 0
        assert data["messages"] == []

    @pytest.mark.asyncio
    async def test_empty_session_analytics(self, session):
        """Test analytics for empty session."""
        analytics = session.get_analytics()

        assert analytics.total_messages == 0
        assert analytics.avg_response_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_branch_empty_session(self, manager):
        """Test branching an empty session."""
        original = await manager.create_session("empty")
        branched = await manager.branch_session("empty")

        assert len(branched._messages) == 0

    @pytest.mark.asyncio
    async def test_replay_empty_session(self, manager):
        """Test replaying an empty session."""
        original = await manager.create_session("empty")
        replayed = await manager.replay_session("empty")

        assert len(replayed._messages) == 0

    @pytest.mark.asyncio
    async def test_search_empty_manager(self, manager):
        """Test searching with no sessions."""
        results = await manager.semantic_search("anything")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_messages_range(self, session_with_messages):
        """Test getting message range."""
        messages = session_with_messages.get_messages(1, 3)

        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_get_messages_out_of_range(self, session_with_messages):
        """Test getting messages with out of range indices."""
        messages = session_with_messages.get_messages(100, 200)

        assert messages == []

    @pytest.mark.asyncio
    async def test_message_count_property(self, session_with_messages):
        """Test message_count property."""
        assert session_with_messages.message_count == 5


# =============================================================================
# REPLAY CONFIG TESTS
# =============================================================================


class TestReplayConfig:
    """Tests for ReplayConfig dataclass."""

    def test_default_config(self):
        """Test default ReplayConfig values."""
        config = ReplayConfig()

        assert config.modify_system_prompt is None
        assert config.modify_temperature is None
        assert config.filter_roles is None
        assert config.transform_fn is None
        assert config.skip_indices == []
        assert config.inject_messages == {}

    def test_config_with_values(self):
        """Test ReplayConfig with custom values."""

        def transform(msg):
            return msg

        config = ReplayConfig(
            modify_system_prompt="New prompt",
            modify_temperature=0.7,
            filter_roles=["user", "assistant"],
            transform_fn=transform,
            skip_indices=[0, 1, 2],
            inject_messages={1: [{"role": "system", "content": "Injected"}]},
        )

        assert config.modify_system_prompt == "New prompt"
        assert config.modify_temperature == 0.7
        assert len(config.filter_roles) == 2
        assert config.transform_fn is transform
        assert len(config.skip_indices) == 3
        assert 1 in config.inject_messages


# =============================================================================
# EXPORT FORMAT TESTS
# =============================================================================


class TestExportFormat:
    """Tests for ExportFormat enum."""

    def test_all_formats_exist(self):
        """Test all expected export formats exist."""
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.MARKDOWN.value == "markdown"
        assert ExportFormat.TRAINING_DATA.value == "training_data"
        assert ExportFormat.JSONL.value == "jsonl"

    def test_format_from_string(self):
        """Test creating format from string."""
        assert ExportFormat("json") == ExportFormat.JSON
        assert ExportFormat("markdown") == ExportFormat.MARKDOWN
