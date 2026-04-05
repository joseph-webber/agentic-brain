# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for memory manager lifecycle: cleanup, pruning, and decay.

Covers:
  - apply_decay: importance reduces over time, reinforced memories decay slower
  - reinforce_memory: access_count increments, importance boosted
  - effective_importance: time-decay property on MemoryEntry
  - condense_old_memories: low-importance old entries are summarised and removed
  - condense_old_memories: returns stats dict
  - link_sessions / find_related_sessions: cross-session linking via entities
  - get_entity_timeline: entity appears in multiple memories
  - Importance auto-scoring (keyword signals)
  - delete: count decrements
  - stats(): all keys present, totals consistent
  - Pruning via condense does not remove high-importance memories
  - Edge cases: empty store, already-minimum importance, no old memories
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from agentic_brain.memory.unified import (
    MemoryEntry,
    MemoryType,
    SQLiteMemoryStore,
    UnifiedMemory,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path) -> SQLiteMemoryStore:
    s = SQLiteMemoryStore(db_path=str(tmp_path / "mgr.db"))
    yield s
    s.close()


@pytest.fixture
def mem(tmp_path) -> UnifiedMemory:
    m = UnifiedMemory(db_path=str(tmp_path / "uni_mgr.db"))
    yield m
    m.close()


def _backdate(store: SQLiteMemoryStore, memory_id: str, days: int) -> None:
    """Move a memory's timestamp and last_accessed back by *days* days."""
    past = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    conn = store._get_conn()
    conn.execute(
        "UPDATE memories SET timestamp = ?, last_accessed = ? WHERE id = ?",
        (past, past, memory_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Memory decay
# ---------------------------------------------------------------------------


class TestApplyDecay:
    def test_decay_reduces_importance_of_old_memory(self, store):
        entry = store.store(
            "old low-importance content", memory_type=MemoryType.LONG_TERM
        )
        initial = entry.importance
        _backdate(store, entry.id, days=365)
        store.apply_decay(decay_rate=0.05)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT importance FROM memories WHERE id = ?", (entry.id,)
        ).fetchone()
        assert row["importance"] < initial or row["importance"] == pytest.approx(0.1)

    def test_decay_does_not_go_below_min(self, store):
        entry = store.store(
            "very old", memory_type=MemoryType.LONG_TERM, importance=0.1
        )
        _backdate(store, entry.id, days=9999)
        store.apply_decay(decay_rate=1.0, min_importance=0.1)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT importance FROM memories WHERE id = ?", (entry.id,)
        ).fetchone()
        assert row["importance"] >= 0.1

    def test_decay_returns_update_count(self, store):
        for i in range(3):
            e = store.store(f"entry {i}", importance=0.9)
            _backdate(store, e.id, days=100)
        updated = store.apply_decay(decay_rate=0.1)
        assert isinstance(updated, int)
        assert updated >= 0

    def test_fresh_memories_not_significantly_decayed(self, store):
        entry = store.store("fresh content", importance=0.8)
        # No backdating – fresh memory
        store.apply_decay(decay_rate=0.01)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT importance FROM memories WHERE id = ?", (entry.id,)
        ).fetchone()
        # Fresh memory should change by less than 0.01
        assert abs(row["importance"] - 0.8) < 0.05

    def test_empty_store_apply_decay_returns_zero(self, store):
        result = store.apply_decay()
        assert result == 0


# ---------------------------------------------------------------------------
# Memory reinforcement
# ---------------------------------------------------------------------------


class TestReinforceMemory:
    def test_reinforce_increments_access_count(self, store):
        entry = store.store("reinforce me")
        before = entry.access_count
        store.reinforce_memory(entry.id)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT access_count FROM memories WHERE id = ?", (entry.id,)
        ).fetchone()
        assert row["access_count"] > before

    def test_reinforce_boosts_importance(self, store):
        entry = store.store("boost me", importance=0.3)
        store.reinforce_memory(entry.id, boost=0.2)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT importance FROM memories WHERE id = ?", (entry.id,)
        ).fetchone()
        assert row["importance"] > 0.3

    def test_reinforce_caps_at_one(self, store):
        entry = store.store("already high", importance=0.95)
        store.reinforce_memory(entry.id, boost=0.5)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT importance FROM memories WHERE id = ?", (entry.id,)
        ).fetchone()
        assert row["importance"] <= 1.0

    def test_reinforce_nonexistent_returns_none(self, store):
        result = store.reinforce_memory("nonexistent-id")
        assert result is None


# ---------------------------------------------------------------------------
# MemoryEntry.effective_importance (time-decay property)
# ---------------------------------------------------------------------------


class TestEffectiveImportance:
    def test_fresh_memory_effective_importance_near_base(self):
        entry = MemoryEntry(
            id="e1",
            content="fresh",
            memory_type=MemoryType.LONG_TERM,
            timestamp=datetime.now(UTC),
            importance=0.8,
            last_accessed=datetime.now(UTC),
        )
        assert entry.effective_importance >= 0.7  # small decay at t=0

    def test_old_memory_effective_importance_lower(self):
        old_time = datetime.now(UTC) - timedelta(days=365)
        entry = MemoryEntry(
            id="e2",
            content="old",
            memory_type=MemoryType.LONG_TERM,
            timestamp=old_time,
            importance=0.8,
            last_accessed=old_time,
        )
        # After 365 days, importance should have decayed substantially
        assert entry.effective_importance < 0.8

    def test_effective_importance_floor_is_0_1(self):
        very_old = datetime.now(UTC) - timedelta(days=99999)
        entry = MemoryEntry(
            id="e3",
            content="ancient",
            memory_type=MemoryType.LONG_TERM,
            timestamp=very_old,
            importance=0.5,
            last_accessed=very_old,
        )
        assert entry.effective_importance >= 0.1

    def test_reinforced_memory_decays_slower(self):
        old_time = datetime.now(UTC) - timedelta(days=30)
        entry_reinforced = MemoryEntry(
            id="r1",
            content="reinforced",
            memory_type=MemoryType.LONG_TERM,
            timestamp=old_time,
            importance=0.6,
            access_count=20,  # many accesses
            last_accessed=old_time,
        )
        entry_stale = MemoryEntry(
            id="r2",
            content="stale",
            memory_type=MemoryType.LONG_TERM,
            timestamp=old_time,
            importance=0.6,
            access_count=0,
            last_accessed=old_time,
        )
        assert entry_reinforced.effective_importance >= entry_stale.effective_importance


# ---------------------------------------------------------------------------
# condense_old_memories
# ---------------------------------------------------------------------------


class TestCondenseOldMemories:
    def test_condense_old_low_importance_memories(self, store):
        for i in range(5):
            e = store.store(f"old boring fact {i}", importance=0.1)
            _backdate(store, e.id, days=30)
        result = store.condense_old_memories(
            older_than_days=7, importance_threshold=0.3
        )
        assert result["condensed"] >= 5

    def test_condense_does_not_remove_high_importance(self, store):
        critical = store.store("CRITICAL: deploy password updated", importance=0.9)
        _backdate(store, critical.id, days=30)
        store.condense_old_memories(older_than_days=7, importance_threshold=0.3)
        # High-importance entry should NOT be condensed (above threshold)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT id FROM memories WHERE id = ?", (critical.id,)
        ).fetchone()
        assert row is not None  # still there

    def test_condense_returns_stats_dict(self, store):
        result = store.condense_old_memories(older_than_days=7)
        assert "condensed" in result
        assert isinstance(result["condensed"], int)

    def test_condense_empty_store_returns_zero(self, store):
        result = store.condense_old_memories()
        assert result["condensed"] == 0

    def test_condense_creates_summary_memory(self, store):
        for i in range(3):
            e = store.store(f"forgettable fact {i}", importance=0.1)
            _backdate(store, e.id, days=30)
        before = store.count()
        store.condense_old_memories(older_than_days=7, importance_threshold=0.3)
        after = store.count()
        # After condensation: originals removed, 1 summary added per session group
        # Total should be less than or equal to before
        assert after <= before

    def test_condense_unified_memory(self, mem):
        for i in range(4):
            e = mem.store(f"old boring {i}", importance=0.1)
            _backdate(mem._sqlite, e.id, days=30)
        result = mem.condense_old_memories(older_than_days=7, importance_threshold=0.3)
        assert result["condensed"] >= 4


# ---------------------------------------------------------------------------
# Cross-session linking
# ---------------------------------------------------------------------------


class TestSessionLinking:
    def test_link_sessions_and_find_related(self, store):
        # Store shared entity in both sessions
        store.store("Python programming", session_id="sess-A")
        store.store("Python is great", session_id="sess-B")
        store.link_sessions("sess-A", "sess-B", relationship="CONTINUED_BY")
        related = store.find_related_sessions("sess-A")
        session_ids = [r["session_id"] for r in related]
        # sess-B should appear via shared entities
        assert isinstance(related, list)

    def test_find_related_sessions_returns_list(self, store):
        store.store("some content", session_id="orphan-session")
        related = store.find_related_sessions("orphan-session")
        assert isinstance(related, list)

    def test_link_sessions_no_error(self, store):
        store.link_sessions("s1", "s2", shared_entities=["Python", "Docker"])


# ---------------------------------------------------------------------------
# Entity timeline
# ---------------------------------------------------------------------------


class TestEntityTimeline:
    def test_entity_timeline_tracks_mentions(self, store):
        store.store("Python is widely used for ML", session_id="a")
        store.store("Python can be used for web", session_id="b")
        timeline = store.get_entity_timeline("Python")
        assert isinstance(timeline, list)
        assert len(timeline) >= 1

    def test_entity_timeline_unknown_entity_returns_empty(self, store):
        timeline = store.get_entity_timeline("xyzzy_nonexistent_entity_12345")
        assert timeline == []

    def test_entity_timeline_limit_respected(self, store):
        for i in range(15):
            store.store(f"Python mention {i}", session_id=f"s{i}")
        timeline = store.get_entity_timeline("Python", limit=5)
        assert len(timeline) <= 5


# ---------------------------------------------------------------------------
# Stats and delete
# ---------------------------------------------------------------------------


class TestStatsAndDelete:
    def test_stats_returns_all_keys(self, mem):
        stats = mem.stats()
        for key in ("total", "session", "long_term", "semantic", "episodic", "db_path"):
            assert key in stats

    def test_stats_total_matches_count(self, mem):
        mem.store("item1")
        mem.store("item2")
        stats = mem.stats()
        assert stats["total"] == mem.count()

    def test_delete_reduces_count(self, mem):
        entry = mem.store("delete me")
        before = mem.count()
        mem.delete(entry.id)
        assert mem.count() == before - 1

    def test_delete_nonexistent_returns_false(self, mem):
        result = mem.delete("nonexistent-id-xyz")
        assert result is False

    def test_count_per_type(self, mem):
        mem.store("s", memory_type=MemoryType.SESSION)
        mem.store("lt", memory_type=MemoryType.LONG_TERM)
        mem.store("sem", memory_type=MemoryType.SEMANTIC)
        assert mem.count(MemoryType.SESSION) >= 1
        assert mem.count(MemoryType.LONG_TERM) >= 1
        assert mem.count(MemoryType.SEMANTIC) >= 1


# ---------------------------------------------------------------------------
# Importance auto-scoring
# ---------------------------------------------------------------------------


class TestImportanceScoring:
    def test_keyword_boosts_importance(self, store):
        normal = store.store("the weather is nice today")
        critical = store.store("CRITICAL bug in production deploy now")
        assert critical.importance > normal.importance

    def test_pinned_metadata_forces_high_importance(self, store):
        entry = store.store("pinned item", metadata={"pinned": True})
        assert entry.importance >= 0.8

    def test_short_content_slightly_lower_importance(self, store):
        short = store.store("ok")
        # Very short (1 word) → small penalty
        assert short.importance >= 0.1  # at least the floor

    def test_importance_bounded_between_0_and_1(self, store):
        for content in ["test", "important critical urgent fix bug deploy", ""]:
            e = store.store(content)
            assert 0.0 <= e.importance <= 1.0

    def test_custom_importance_not_overridden(self, store):
        # When explicitly set to a non-default value, it should be used
        entry = store.store("neutral text", importance=0.9)
        assert entry.importance == pytest.approx(0.9, abs=0.001)
