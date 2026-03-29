# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for GraphRAG voice memory module."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.memory import (
    EMBEDDING_DIM,
    LABEL_CONVERSATION,
    LABEL_UTTERANCE,
    VoiceConversation,
    VoiceMemory,
    VoiceUtterance,
    get_voice_memory,
    reset_voice_memory,
)


class TestVoiceUtterance:
    """Tests for VoiceUtterance dataclass."""

    def test_create_utterance(self):
        """Test creating a basic utterance."""
        now = datetime.now(timezone.utc)
        utt = VoiceUtterance(
            text="Hello Joseph!",
            timestamp=now,
            speaker="Karen",
        )

        assert utt.text == "Hello Joseph!"
        assert utt.speaker == "Karen"
        assert utt.timestamp == now
        assert utt.embedding is None
        assert utt.emotion is None
        assert utt.id is not None

    def test_utterance_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        utt = VoiceUtterance(
            id="test-123",
            text="Test message",
            timestamp=now,
            speaker="user",
            emotion="happy",
        )

        data = utt.to_dict()

        assert data["id"] == "test-123"
        assert data["text"] == "Test message"
        assert data["speaker"] == "user"
        assert data["emotion"] == "happy"
        assert data["timestamp"] == now.isoformat()

    def test_utterance_from_record(self):
        """Test deserialization from Neo4j record."""
        now = datetime.now(timezone.utc)
        record = {
            "id": "rec-456",
            "text": "From record",
            "timestamp": now.isoformat(),
            "speaker": "Moira",
            "emotion": "calm",
            "embedding": [0.1, 0.2, 0.3],
        }

        utt = VoiceUtterance.from_record(record)

        assert utt.id == "rec-456"
        assert utt.text == "From record"
        assert utt.speaker == "Moira"
        assert utt.emotion == "calm"
        assert utt.embedding == [0.1, 0.2, 0.3]


class TestVoiceConversation:
    """Tests for VoiceConversation dataclass."""

    def test_create_conversation(self):
        """Test creating a conversation."""
        now = datetime.now(timezone.utc)
        conv = VoiceConversation(
            session_id="session-001",
            started_at=now,
            topic="Testing",
        )

        assert conv.session_id == "session-001"
        assert conv.started_at == now
        assert conv.topic == "Testing"
        assert conv.utterances == []

    def test_conversation_to_dict(self):
        """Test serialization."""
        now = datetime.now(timezone.utc)
        conv = VoiceConversation(
            session_id="session-002",
            started_at=now,
            topic="Demo",
        )

        data = conv.to_dict()

        assert data["session_id"] == "session-002"
        assert data["topic"] == "Demo"
        assert data["utterance_count"] == 0


class TestVoiceMemoryInMemory:
    """Tests for VoiceMemory with in-memory fallback."""

    @pytest.fixture(autouse=True)
    def setup_memory(self):
        """Reset singleton before each test."""
        reset_voice_memory()
        yield
        reset_voice_memory()

    def test_store_utterance_in_memory(self):
        """Test storing utterance when Neo4j unavailable."""
        # Create memory without Neo4j
        memory = VoiceMemory(use_neo4j=False)

        now = datetime.now(timezone.utc)
        utt = VoiceUtterance(
            text="Hello world",
            timestamp=now,
            speaker="user",
        )

        result_id = memory.store_utterance(utt, "conv-1", compute_embedding=False)

        assert result_id == utt.id
        assert len(memory._utterances) == 1
        assert "conv-1" in memory._conversations

    def test_get_conversation_context_in_memory(self):
        """Test getting conversation context from memory."""
        memory = VoiceMemory(use_neo4j=False)

        now = datetime.now(timezone.utc)
        for i in range(5):
            utt = VoiceUtterance(
                text=f"Message {i}",
                timestamp=now,
                speaker="user",
            )
            memory.store_utterance(utt, "conv-test", compute_embedding=False)

        context = memory.get_conversation_context("conv-test", limit=3)

        assert len(context) == 3
        # Should be oldest first (chronological order)
        assert context[0].text == "Message 2"
        assert context[2].text == "Message 4"

    def test_create_conversation_in_memory(self):
        """Test creating a conversation."""
        memory = VoiceMemory(use_neo4j=False)

        conv = memory.create_conversation(
            session_id="new-session",
            topic="Test Topic",
        )

        assert conv.session_id == "new-session"
        assert conv.topic == "Test Topic"
        assert "new-session" in memory._conversations

    def test_health_check_in_memory(self):
        """Test health check returns valid data."""
        memory = VoiceMemory(use_neo4j=False)

        health = memory.health()

        assert health["neo4j_available"] is False
        assert health["in_memory_utterances"] == 0
        assert health["in_memory_conversations"] == 0

    def test_singleton_pattern(self):
        """Test get_voice_memory returns singleton."""
        reset_voice_memory()

        with patch.object(VoiceMemory, "_init_neo4j"):
            mem1 = get_voice_memory(use_neo4j=False)
            mem2 = get_voice_memory(use_neo4j=False)

            assert mem1 is mem2

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        # Identical vectors → 1.0
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert VoiceMemory._cosine_similarity(a, b) == pytest.approx(1.0)

        # Orthogonal vectors → 0.0
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert VoiceMemory._cosine_similarity(a, b) == pytest.approx(0.0)

        # Opposite vectors → -1.0
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert VoiceMemory._cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_recall_similar_in_memory(self):
        """Test similarity recall with mock embeddings."""
        memory = VoiceMemory(use_neo4j=False)

        # Create utterances with known embeddings
        now = datetime.now(timezone.utc)
        utt1 = VoiceUtterance(
            text="Good morning",
            timestamp=now,
            speaker="Karen",
            embedding=[1.0, 0.0, 0.0] * (EMBEDDING_DIM // 3),
        )
        utt2 = VoiceUtterance(
            text="Hello there",
            timestamp=now,
            speaker="Karen",
            embedding=[0.9, 0.1, 0.0] * (EMBEDDING_DIM // 3),
        )
        utt3 = VoiceUtterance(
            text="Goodbye",
            timestamp=now,
            speaker="Karen",
            embedding=[0.0, 1.0, 0.0] * (EMBEDDING_DIM // 3),
        )

        memory._store_memory(utt1, "conv-1")
        memory._store_memory(utt2, "conv-1")
        memory._store_memory(utt3, "conv-1")

        # Query with embedding similar to utt1
        query_embedding = [1.0, 0.0, 0.0] * (EMBEDDING_DIM // 3)

        results = memory._recall_memory(query_embedding, limit=2, speaker_filter=None, min_score=0.5)

        assert len(results) == 2
        # utt1 should be most similar (exact match)
        assert results[0].text == "Good morning"

    def test_memory_limit_trimming(self):
        """Test that in-memory storage is trimmed."""
        memory = VoiceMemory(use_neo4j=False)

        now = datetime.now(timezone.utc)

        # Store more than limit (1000)
        for i in range(1100):
            utt = VoiceUtterance(
                text=f"Message {i}",
                timestamp=now,
                speaker="user",
            )
            memory.store_utterance(utt, "conv-big", compute_embedding=False)

        # Should be trimmed - not exceed 1000 significantly
        # The trimming happens when > 1000, keeping 500
        assert len(memory._utterances) <= 1000


class TestVoiceMemoryWithMockedNeo4j:
    """Tests for VoiceMemory with mocked Neo4j."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset singleton before each test."""
        reset_voice_memory()
        yield
        reset_voice_memory()

    @patch("agentic_brain.voice.memory.VoiceMemory._init_neo4j")
    def test_store_with_neo4j(self, mock_init):
        """Test store_utterance with Neo4j enabled."""
        memory = VoiceMemory(use_neo4j=True)
        memory._neo4j_available = True

        with patch("agentic_brain.core.neo4j_write") as mock_write:
            mock_write.return_value = 1

            now = datetime.now(timezone.utc)
            utt = VoiceUtterance(
                text="Hello Neo4j",
                timestamp=now,
                speaker="user",
            )

            result = memory.store_utterance(utt, "session-neo", compute_embedding=False)

            assert result == utt.id
            # Should have called neo4j_write for conversation and utterance
            assert mock_write.call_count >= 2

    @patch("agentic_brain.voice.memory.VoiceMemory._init_neo4j")
    def test_get_context_with_neo4j(self, mock_init):
        """Test get_conversation_context with Neo4j."""
        memory = VoiceMemory(use_neo4j=True)
        memory._neo4j_available = True

        mock_records = [
            {
                "u": {
                    "id": "u1",
                    "text": "First",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "speaker": "user",
                }
            },
            {
                "u": {
                    "id": "u2",
                    "text": "Second",
                    "timestamp": "2026-01-01T00:01:00+00:00",
                    "speaker": "Karen",
                }
            },
        ]

        with patch("agentic_brain.core.neo4j_query", return_value=mock_records):
            context = memory.get_conversation_context("session-1", limit=10)

            # Results should be reversed (oldest first)
            assert len(context) == 2
            assert context[0].text == "Second"  # Was last in reversed order
            assert context[1].text == "First"


class TestEmbedding:
    """Tests for embedding functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset singleton."""
        reset_voice_memory()
        yield
        reset_voice_memory()

    def test_lazy_load_embedder(self):
        """Test that embedder is lazy-loaded."""
        memory = VoiceMemory(use_neo4j=False)

        # Embedder should not be loaded yet
        assert memory._embedder is None

        # Mock the import inside _get_embedder
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * EMBEDDING_DIM)

        # Inject mock directly to test the lazy pattern
        memory._embedder = mock_model
        embedder = memory._get_embedder()
        assert embedder is mock_model

    def test_compute_embedding(self):
        """Test embedding computation."""
        memory = VoiceMemory(use_neo4j=False)

        mock_model = MagicMock()
        mock_vec = MagicMock()
        mock_vec.tolist.return_value = [0.5] * EMBEDDING_DIM
        mock_model.encode.return_value = mock_vec
        memory._embedder = mock_model

        embedding = memory._compute_embedding("Test text")

        assert embedding == [0.5] * EMBEDDING_DIM
        mock_model.encode.assert_called_once_with("Test text", convert_to_numpy=True)

    def test_embedding_fallback_on_import_error(self):
        """Test graceful fallback when sentence-transformers unavailable."""
        memory = VoiceMemory(use_neo4j=False)

        # Set sentinel to indicate import failed
        memory._embedder = False

        # Should return None when embedder is False sentinel
        embedder = memory._get_embedder()
        assert embedder is None


class TestTopicManagement:
    """Tests for conversation topic management."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset singleton."""
        reset_voice_memory()
        yield
        reset_voice_memory()

    def test_set_conversation_topic_in_memory(self):
        """Test setting topic in memory mode."""
        memory = VoiceMemory(use_neo4j=False)

        # Create a conversation first
        conv = memory.create_conversation(session_id="topic-test")
        assert conv.topic is None

        # Set topic
        memory.set_conversation_topic("topic-test", "Voice Memory Testing")

        # Verify topic was set
        assert memory._conversations["topic-test"].topic == "Voice Memory Testing"

    def test_get_conversations_by_topic_in_memory(self):
        """Test finding conversations by topic."""
        memory = VoiceMemory(use_neo4j=False)

        # Create conversations with different topics
        memory.create_conversation(session_id="c1", topic="Voice Memory")
        memory.create_conversation(session_id="c2", topic="Audio Processing")
        memory.create_conversation(session_id="c3", topic="Voice Recognition")

        # Search for "voice"
        results = memory.get_conversations_by_topic("voice", limit=10)

        assert len(results) == 2
        topics = [r.topic for r in results]
        assert "Voice Memory" in topics
        assert "Voice Recognition" in topics


# Integration test marker - only runs with actual Neo4j
@pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("SKIP_NEO4J_TESTS") == "true",
    reason="Requires local Neo4j instance",
)
class TestVoiceMemoryNeo4jIntegration:
    """Integration tests requiring actual Neo4j connection."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset singleton."""
        reset_voice_memory()
        yield
        reset_voice_memory()

    def test_neo4j_health_check(self):
        """Test health check with real Neo4j."""
        memory = get_voice_memory(use_neo4j=True)

        if not memory._neo4j_available:
            pytest.skip("Neo4j not available")

        health = memory.health()

        assert health["neo4j_available"] is True
        assert "neo4j_utterances" in health
        assert "neo4j_conversations" in health

    def test_full_store_and_recall_cycle(self):
        """Test complete store → recall cycle with Neo4j."""
        memory = get_voice_memory(use_neo4j=True)

        if not memory._neo4j_available:
            pytest.skip("Neo4j not available")

        # Skip if no embedder
        if memory._get_embedder() is None:
            pytest.skip("sentence-transformers not available")

        now = datetime.now(timezone.utc)
        conv = memory.create_conversation(topic="Integration Test")

        # Store utterances
        utt1 = VoiceUtterance(
            text="Good morning Joseph, how are you today?",
            timestamp=now,
            speaker="Karen",
        )
        memory.store_utterance(utt1, conv.session_id)

        utt2 = VoiceUtterance(
            text="I'm doing well, thanks for asking!",
            timestamp=now,
            speaker="user",
        )
        memory.store_utterance(utt2, conv.session_id, previous_utterance_id=utt1.id)

        # Recall similar
        results = memory.recall_similar("morning greeting", limit=5)

        assert len(results) > 0
        # The morning greeting should be in results
        texts = [r.text for r in results]
        assert any("morning" in t.lower() for t in texts)
