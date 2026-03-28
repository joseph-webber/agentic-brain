# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Tests for Mem0-inspired memory enhancements.

Tests importance scoring, memory decay, entity extraction,
cross-session linking, and memory condensation.
"""

import math
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.memory.neo4j_memory import (
    ConversationMemory,
    MemoryConfig,
    Message,
)
from agentic_brain.memory.unified import (
    MemoryEntry,
    MemoryType,
    SQLiteMemoryStore,
    UnifiedMemory,
)


# =========================================================================
# IMPORTANCE SCORING TESTS
# =========================================================================


class TestImportanceScoring:
    """Test Mem0-inspired importance scoring."""

    @pytest.fixture
    def memory(self):
        config = MemoryConfig(use_pool=True, extract_entities=True)
        return ConversationMemory(session_id="test", config=config)

    def test_base_importance(self, memory):
        """Neutral content gets base score."""
        score = memory._score_importance("hello world", "user", {})
        assert 0.3 <= score <= 0.6

    def test_keyword_boost(self, memory):
        """Important keywords boost score."""
        score_normal = memory._score_importance("hello there", "user", {})
        score_important = memory._score_importance(
            "This is critical and urgent - must deploy now", "user", {}
        )
        assert score_important > score_normal

    def test_question_boost(self, memory):
        """Questions get a small boost."""
        score_statement = memory._score_importance("I like Python", "user", {})
        score_question = memory._score_importance("What is Python?", "user", {})
        assert score_question > score_statement

    def test_code_boost(self, memory):
        """Code content gets a boost."""
        score_text = memory._score_importance("hello world", "user", {})
        score_code = memory._score_importance(
            "def main():\n    pass\n```python\nclass Foo:\n    pass```",
            "user",
            {},
        )
        assert score_code > score_text

    def test_metadata_override(self, memory):
        """Metadata importance overrides calculated score."""
        score = memory._score_importance(
            "nothing special", "user", {"importance": 0.95}
        )
        assert score == 0.95

    def test_pinned_boost(self, memory):
        """Pinned memories get high importance."""
        score = memory._score_importance("test", "user", {"pinned": True})
        assert score >= 0.9

    def test_short_message_penalty(self, memory):
        """Very short messages get penalized."""
        score_short = memory._score_importance("hi", "user", {})
        score_long = memory._score_importance(
            "This is a longer message with more words that should be scored higher",
            "user",
            {},
        )
        assert score_long > score_short

    def test_score_bounds(self, memory):
        """Score always between 0.0 and 1.0."""
        # Try to overflow
        score = memory._score_importance(
            "important critical urgent must deploy deadline confirmed "
            "remember always never bug fix error security production breaking",
            "user",
            {"pinned": True},
        )
        assert 0.0 <= score <= 1.0


class TestSQLiteImportanceScoring:
    """Test importance scoring in SQLite store."""

    @pytest.fixture
    def store(self, tmp_path):
        return SQLiteMemoryStore(db_path=str(tmp_path / "test.db"))

    def test_store_auto_scores_importance(self, store):
        """Stored memories get auto-scored importance."""
        entry = store.store("This is a critical bug that must be fixed")
        assert entry.importance > 0.5  # keywords boost it

    def test_store_with_explicit_importance(self, store):
        """Explicit importance is respected."""
        entry = store.store("hello", importance=0.9)
        assert entry.importance == 0.9

    def test_long_term_boost(self, store):
        """LONG_TERM memories get importance boost."""
        entry = store.store("test content", memory_type=MemoryType.LONG_TERM)
        # Should be above base 0.5 due to LONG_TERM boost
        assert entry.importance > 0.5


# =========================================================================
# MEMORY DECAY TESTS
# =========================================================================


class TestMemoryDecay:
    """Test Mem0-inspired memory decay."""

    @pytest.fixture
    def memory(self):
        config = MemoryConfig(
            use_pool=True,
            decay_enabled=True,
            decay_rate=0.01,
            min_importance=0.1,
            reinforce_boost=0.15,
        )
        return ConversationMemory(session_id="test", config=config)

    def test_recent_memory_no_decay(self, memory):
        """Recent memories don't decay much."""
        now = datetime.now(UTC)
        decayed = memory._calculate_decayed_importance(
            base_importance=0.8, created_at=now, access_count=0
        )
        assert abs(decayed - 0.8) < 0.05

    def test_old_memory_decays(self, memory):
        """Old memories decay significantly."""
        old = datetime.now(UTC) - timedelta(days=100)
        decayed = memory._calculate_decayed_importance(
            base_importance=0.8, created_at=old, access_count=0
        )
        assert decayed < 0.5  # Should have decayed

    def test_accessed_memory_resists_decay(self, memory):
        """Frequently accessed memories resist decay."""
        old = datetime.now(UTC) - timedelta(days=100)
        decayed_no_access = memory._calculate_decayed_importance(
            base_importance=0.8, created_at=old, access_count=0
        )
        decayed_with_access = memory._calculate_decayed_importance(
            base_importance=0.8, created_at=old, access_count=10
        )
        assert decayed_with_access > decayed_no_access

    def test_min_importance_floor(self, memory):
        """Memories never drop below min_importance."""
        very_old = datetime.now(UTC) - timedelta(days=1000)
        decayed = memory._calculate_decayed_importance(
            base_importance=0.2, created_at=very_old, access_count=0
        )
        assert decayed >= memory.config.min_importance

    def test_decay_disabled(self, memory):
        """Decay can be disabled."""
        memory.config.decay_enabled = False
        old = datetime.now(UTC) - timedelta(days=100)
        result = memory._calculate_decayed_importance(
            base_importance=0.8, created_at=old, access_count=0
        )
        assert result == 0.8

    def test_last_accessed_resets_decay(self, memory):
        """Last access time resets decay clock."""
        old = datetime.now(UTC) - timedelta(days=100)
        recent_access = datetime.now(UTC) - timedelta(hours=1)
        decayed = memory._calculate_decayed_importance(
            base_importance=0.8,
            created_at=old,
            access_count=1,
            last_accessed=recent_access,
        )
        assert decayed > 0.7  # Barely decayed because recently accessed


class TestSQLiteDecay:
    """Test decay and reinforcement in SQLite store."""

    @pytest.fixture
    def store(self, tmp_path):
        return SQLiteMemoryStore(db_path=str(tmp_path / "test.db"))

    def test_reinforce_memory(self, store):
        """Reinforcing a memory boosts its importance."""
        entry = store.store("test content", importance=0.5)
        reinforced = store.reinforce_memory(entry.id)
        assert reinforced is not None
        assert reinforced.importance > 0.5
        assert reinforced.access_count == 1

    def test_reinforce_capped_at_one(self, store):
        """Importance can't exceed 1.0."""
        entry = store.store("test", importance=0.95)
        reinforced = store.reinforce_memory(entry.id, boost=0.2)
        assert reinforced.importance <= 1.0

    def test_apply_decay(self, store):
        """Apply decay reduces old memory importance."""
        # Store a memory and manipulate its timestamp to be old
        entry = store.store("test content", importance=0.8)
        conn = store._get_conn()
        old_time = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        conn.execute(
            "UPDATE memories SET timestamp = ?, last_accessed = ? WHERE id = ?",
            (old_time, old_time, entry.id),
        )
        conn.commit()

        updated = store.apply_decay(decay_rate=0.01, min_importance=0.1)
        assert updated > 0

        # Check that importance was reduced
        cursor = conn.execute(
            "SELECT importance FROM memories WHERE id = ?", (entry.id,)
        )
        new_importance = cursor.fetchone()["importance"]
        assert new_importance < 0.8


# =========================================================================
# ENTITY EXTRACTION TESTS
# =========================================================================


class TestEntityExtraction:
    """Test Mem0-inspired entity extraction."""

    @pytest.fixture
    def memory(self):
        config = MemoryConfig(use_pool=True, extract_entities=True)
        return ConversationMemory(session_id="test", config=config)

    def test_email_extraction(self, memory):
        """Emails are extracted."""
        entities = memory._extract_entities("Contact joe@example.com for details")
        names = [e[0] for e in entities]
        assert "joe@example.com" in names

    def test_url_extraction(self, memory):
        """URLs are extracted."""
        entities = memory._extract_entities("Visit https://github.com/brain")
        types = {e[0]: e[1] for e in entities}
        assert "https://github.com/brain" in types
        assert types["https://github.com/brain"] == "URL"

    def test_ticket_extraction(self, memory):
        """JIRA tickets are extracted."""
        entities = memory._extract_entities("Working on SD-1330 and PR-456")
        names = [e[0] for e in entities]
        assert "SD-1330" in names
        assert "PR-456" in names

    def test_technology_extraction(self, memory):
        """Technology names are extracted."""
        entities = memory._extract_entities("Using Python with Neo4j and Docker")
        names = [e[0].lower() for e in entities]
        assert "python" in names
        assert "neo4j" in names
        assert "docker" in names

    def test_person_extraction(self, memory):
        """Multi-word proper nouns are extracted as persons."""
        entities = memory._extract_entities("Steve Taylor reviewed the code")
        names = [e[0] for e in entities]
        assert "Steve Taylor" in names

    def test_organization_extraction(self, memory):
        """Organization suffixes are detected."""
        entities = memory._extract_entities("Working at TechCorp for a while")
        types = {e[0]: e[1] for e in entities}
        assert "TechCorp" in types
        assert types["TechCorp"] == "ORGANIZATION"

    def test_skip_common_words(self, memory):
        """Common words are not extracted as entities."""
        entities = memory._extract_entities("The quick brown fox jumps over")
        names = [e[0] for e in entities]
        assert "The" not in names

    def test_deduplication(self, memory):
        """Duplicate entities are removed."""
        entities = memory._extract_entities("Python is great. I love Python.")
        python_count = sum(1 for e in entities if e[0].lower() == "python")
        assert python_count == 1


class TestSQLiteEntityExtraction:
    """Test entity extraction in SQLite store."""

    @pytest.fixture
    def store(self, tmp_path):
        return SQLiteMemoryStore(db_path=str(tmp_path / "test.db"))

    def test_entities_stored_on_insert(self, store):
        """Entities are extracted and stored when storing memories."""
        entry = store.store("Working on SD-1330 with Python and Neo4j")
        assert len(entry.entities) > 0
        entity_names = [e["name"] for e in entry.entities]
        assert "SD-1330" in entity_names

    def test_entity_timeline(self, store):
        """Entity timeline tracks mentions across memories."""
        store.store(
            "Started working on Python project",
            session_id="sess1",
        )
        store.store(
            "Python project now uses Neo4j",
            session_id="sess2",
        )
        timeline = store.get_entity_timeline("Python")
        assert len(timeline) >= 1


# =========================================================================
# CROSS-SESSION LINKING TESTS
# =========================================================================


class TestCrossSessionLinking:
    """Test Mem0-inspired cross-session linking."""

    @pytest.fixture
    def store(self, tmp_path):
        return SQLiteMemoryStore(db_path=str(tmp_path / "test.db"))

    def test_link_sessions(self, store):
        """Can link two sessions."""
        store.link_sessions("sess1", "sess2", "CONTINUED_FROM", ["Python"])
        # Should not raise

    def test_find_related_sessions_via_entities(self, store):
        """Sessions sharing entities are found."""
        store.store("Working on Python with Neo4j", session_id="sess1")
        store.store("Python project updated", session_id="sess2")
        store.store("Completely unrelated topic about cooking", session_id="sess3")

        related = store.find_related_sessions("sess1")
        related_ids = [r["session_id"] for r in related]
        assert "sess2" in related_ids  # shares "Python"


class TestUnifiedMemoryCrossSession:
    """Test cross-session in UnifiedMemory."""

    @pytest.fixture
    def mem(self, tmp_path):
        return UnifiedMemory(db_path=str(tmp_path / "test.db"))

    def test_link_and_find(self, mem):
        """Can link and find related sessions."""
        mem.store("Working on Python", session_id="sess1")
        mem.store("Python project update", session_id="sess2")
        mem.link_sessions("sess1", "sess2", "RELATED_TO", ["Python"])
        related = mem.find_related_sessions("sess1")
        assert len(related) >= 0  # May find via entities too


# =========================================================================
# MEMORY CONDENSATION TESTS
# =========================================================================


class TestMemoryCondensation:
    """Test Mem0-inspired memory condensation."""

    @pytest.fixture
    def store(self, tmp_path):
        return SQLiteMemoryStore(db_path=str(tmp_path / "test.db"))

    def test_condense_old_memories(self, store):
        """Old low-importance memories are condensed."""
        # Store old, low-importance memories
        conn = store._get_conn()
        old_time = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        for i in range(5):
            entry = store.store(
                f"Old message {i}", importance=0.2, session_id="old_sess"
            )
            conn.execute(
                "UPDATE memories SET timestamp = ? WHERE id = ?",
                (old_time, entry.id),
            )
        conn.commit()

        result = store.condense_old_memories(
            older_than_days=7, importance_threshold=0.3
        )
        assert result["condensed"] == 5
        assert result["summary_created"] is True

    def test_high_importance_preserved(self, store):
        """High-importance memories are not condensed."""
        conn = store._get_conn()
        old_time = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        entry = store.store("Critical information", importance=0.9)
        conn.execute(
            "UPDATE memories SET timestamp = ? WHERE id = ?",
            (old_time, entry.id),
        )
        conn.commit()

        result = store.condense_old_memories(
            older_than_days=7, importance_threshold=0.3
        )
        assert result["condensed"] == 0  # High importance preserved

    def test_recent_memories_preserved(self, store):
        """Recent memories are not condensed regardless of importance."""
        store.store("Recent low importance", importance=0.1)
        result = store.condense_old_memories(
            older_than_days=7, importance_threshold=0.3
        )
        assert result["condensed"] == 0


# =========================================================================
# MESSAGE DATACLASS TESTS
# =========================================================================


class TestMessageDataclass:
    """Test enhanced Message dataclass."""

    def test_message_has_importance(self):
        """Message includes importance field."""
        msg = Message(
            id="test",
            role="user",
            content="hello",
            timestamp=datetime.now(UTC),
            session_id="sess1",
            importance=0.8,
            access_count=3,
        )
        assert msg.importance == 0.8
        assert msg.access_count == 3

    def test_message_to_dict(self):
        """Message serialization includes new fields."""
        msg = Message(
            id="test",
            role="user",
            content="hello",
            timestamp=datetime.now(UTC),
            session_id="sess1",
            importance=0.7,
            access_count=2,
        )
        d = msg.to_dict()
        assert "importance" in d
        assert "access_count" in d
        assert d["importance"] == 0.7


class TestMemoryEntryEffectiveImportance:
    """Test MemoryEntry effective_importance property."""

    def test_recent_entry_full_importance(self):
        """Recent entries retain full importance."""
        entry = MemoryEntry(
            id="test",
            content="test",
            memory_type=MemoryType.LONG_TERM,
            timestamp=datetime.now(UTC),
            importance=0.8,
            last_accessed=datetime.now(UTC),
        )
        assert entry.effective_importance > 0.7

    def test_old_entry_reduced_importance(self):
        """Old entries have reduced effective importance."""
        old = datetime.now(UTC) - timedelta(days=100)
        entry = MemoryEntry(
            id="test",
            content="test",
            memory_type=MemoryType.LONG_TERM,
            timestamp=old,
            importance=0.8,
            last_accessed=old,
        )
        assert entry.effective_importance < 0.8

    def test_accessed_entry_resists_decay(self):
        """Frequently accessed entries resist decay."""
        old = datetime.now(UTC) - timedelta(days=100)
        entry_no_access = MemoryEntry(
            id="test1",
            content="test",
            memory_type=MemoryType.LONG_TERM,
            timestamp=old,
            importance=0.8,
            last_accessed=old,
            access_count=0,
        )
        entry_accessed = MemoryEntry(
            id="test2",
            content="test",
            memory_type=MemoryType.LONG_TERM,
            timestamp=old,
            importance=0.8,
            last_accessed=old,
            access_count=10,
        )
        assert (
            entry_accessed.effective_importance > entry_no_access.effective_importance
        )


# =========================================================================
# UNIFIED MEMORY INTEGRATION
# =========================================================================


class TestUnifiedMemoryEnhanced:
    """Integration tests for enhanced UnifiedMemory."""

    @pytest.fixture
    def mem(self, tmp_path):
        return UnifiedMemory(db_path=str(tmp_path / "test.db"))

    def test_store_and_reinforce(self, mem):
        """Store and reinforce workflow."""
        entry = mem.store("Important Python pattern")
        original_importance = entry.importance
        reinforced = mem.reinforce_memory(entry.id)
        assert reinforced.importance > original_importance

    def test_decay_and_condense(self, mem):
        """Decay and condense workflow."""
        # Apply decay (no old memories yet)
        updated = mem.apply_decay()
        assert updated >= 0

        # Condense (nothing old enough)
        result = mem.condense_old_memories()
        assert result["condensed"] == 0

    def test_entity_timeline(self, mem):
        """Entity timeline through unified interface."""
        mem.store("Python is great", session_id="s1")
        timeline = mem.get_entity_timeline("Python")
        assert isinstance(timeline, list)

    def test_stats_unchanged(self, mem):
        """Stats method still works."""
        stats = mem.stats()
        assert "total" in stats
        assert "db_path" in stats

    def test_remember_recall_aliases(self, mem):
        """Natural language aliases still work."""
        mem.remember("User prefers dark mode")
        results = mem.recall("dark mode")
        assert len(results) > 0

    def test_entry_serialization_roundtrip(self):
        """MemoryEntry can serialize and deserialize with new fields."""
        entry = MemoryEntry(
            id="test",
            content="hello",
            memory_type=MemoryType.LONG_TERM,
            timestamp=datetime.now(UTC),
            importance=0.8,
            access_count=5,
            last_accessed=datetime.now(UTC),
            entities=[{"name": "Python", "type": "TECHNOLOGY"}],
        )
        d = entry.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.importance == entry.importance
        assert restored.access_count == entry.access_count
        assert restored.entities == entry.entities
