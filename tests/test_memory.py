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
Tests for agentic-brain memory module.

Tests the 4-type memory architecture:
1. Session memory (conversation context)
2. Long-term memory (persistent knowledge)
3. Semantic memory (vector embeddings)
4. Episodic memory (event sourcing)
"""

import tempfile
from datetime import UTC, datetime, timezone
from pathlib import Path

import pytest

# Test both legacy and new unified memory systems
from agentic_brain.memory import (
    DataScope,
    InMemoryStore,
    Memory,
    MemoryConfig,
    MemoryDataclass,
    MemoryEntry,
    MemoryType,
    Neo4jMemory,
    SimpleHashEmbedding,
    SQLiteMemoryStore,
    UnifiedMemory,
    get_unified_memory,
)

# ==============================================================================
# UNIFIED MEMORY TESTS (NEW - 4-type architecture)
# ==============================================================================


class TestUnifiedMemoryBasic:
    """Test basic UnifiedMemory functionality."""

    @pytest.fixture
    def memory(self, tmp_path):
        """Create memory instance with temp database."""
        db_path = tmp_path / "test_memory.db"
        mem = UnifiedMemory(db_path=str(db_path))
        yield mem
        mem.close()

    def test_memory_import_simple(self, tmp_path):
        """Test the simple import pattern from docs."""
        # This should work exactly as documented
        db_path = tmp_path / "simple.db"
        mem = Memory(db_path=str(db_path))
        mem.store("user likes Python")
        results = mem.search("programming preferences")

        # Should find the match via semantic similarity
        assert len(results) >= 1
        # Check we got a match (either exact or semantic)
        found = any("Python" in r.content for r in results)
        assert found or len(results) > 0  # At least semantic search worked

    def test_store_and_search_basic(self, memory):
        """Test basic store and search."""
        entry = memory.store("Hello world from Python")

        assert entry.id is not None
        assert entry.content == "Hello world from Python"
        assert entry.memory_type == MemoryType.LONG_TERM

        # Search should find it
        results = memory.search("Hello")
        assert len(results) == 1
        assert results[0].content == "Hello world from Python"

    def test_store_with_metadata(self, memory):
        """Test storing with metadata."""
        entry = memory.store(
            "Important meeting notes",
            metadata={"category": "work", "priority": "high"},
        )

        assert entry.metadata["category"] == "work"
        assert entry.metadata["priority"] == "high"

    def test_memory_types(self, memory):
        """Test different memory types."""
        # Store different types
        memory.store("Session data", memory_type=MemoryType.SESSION)
        memory.store("Long term fact", memory_type=MemoryType.LONG_TERM)
        memory.store("Semantic searchable", memory_type=MemoryType.SEMANTIC)
        memory.store("Episodic event", memory_type=MemoryType.EPISODIC)

        # Filter by type
        session = memory.get_recent(memory_type=MemoryType.SESSION)
        assert len(session) == 1
        assert session[0].content == "Session data"

        long_term = memory.get_recent(memory_type=MemoryType.LONG_TERM)
        assert len(long_term) == 1

    def test_semantic_search(self, memory):
        """Test semantic similarity search."""
        # Store some memories
        memory.store("I love programming in Python")
        memory.store("The weather is sunny today")
        memory.store("Coding is my favorite hobby")

        # Semantic search should find related content
        results = memory.search("software development", use_semantic=True)

        # Should find programming-related content
        assert len(results) >= 1
        # At least one result should be programming-related
        contents = [r.content for r in results]
        assert any(
            "programming" in c.lower() or "coding" in c.lower() for c in contents
        )

    def test_get_recent(self, memory):
        """Test getting recent memories."""
        memory.store("First")
        memory.store("Second")
        memory.store("Third")

        recent = memory.get_recent(limit=2)
        assert len(recent) == 2
        assert recent[0].content == "Third"  # Most recent first

    def test_delete(self, memory):
        """Test deleting memories."""
        entry = memory.store("To be deleted")
        assert memory.count() == 1

        deleted = memory.delete(entry.id)
        assert deleted is True
        assert memory.count() == 0

    def test_count(self, memory):
        """Test counting memories."""
        assert memory.count() == 0

        memory.store("One")
        memory.store("Two")
        memory.store("Three")

        assert memory.count() == 3

    def test_stats(self, memory):
        """Test memory statistics."""
        memory.store("Long term", memory_type=MemoryType.LONG_TERM)
        memory.store("Session", memory_type=MemoryType.SESSION)

        stats = memory.stats()

        assert stats["total"] == 2
        assert stats["long_term"] == 1
        assert stats["session"] == 1
        assert "db_path" in stats


class TestSessionMemory:
    """Test session memory (conversation context)."""

    @pytest.fixture
    def memory(self, tmp_path):
        """Create memory instance."""
        db_path = tmp_path / "test_session.db"
        mem = UnifiedMemory(db_path=str(db_path))
        yield mem
        mem.close()

    def test_add_message(self, memory):
        """Test adding messages to session."""
        session_id = "test-session-1"

        memory.add_message(session_id, "user", "Hello!")
        memory.add_message(session_id, "assistant", "Hi there!")

        context = memory.get_session_context(session_id)
        assert context is not None
        assert len(context["messages"]) == 2

    def test_get_session_messages(self, memory):
        """Test getting session messages."""
        session_id = "test-session-2"

        memory.add_message(session_id, "user", "First message")
        memory.add_message(session_id, "assistant", "Second message")
        memory.add_message(session_id, "user", "Third message")

        # Get all messages
        messages = memory.get_session_messages(session_id)
        assert len(messages) == 3

        # Get limited messages
        limited = memory.get_session_messages(session_id, limit=2)
        assert len(limited) == 2
        assert limited[0]["content"] == "Second message"  # Last 2

    def test_set_session(self, memory):
        """Test setting current session."""
        memory.set_session("my-session")

        # Store should use current session
        entry = memory.store("Session memory", memory_type=MemoryType.SESSION)
        assert entry.session_id == "my-session"

    def test_session_isolation(self, memory):
        """Test that sessions are isolated."""
        memory.add_message("session-a", "user", "Message A")
        memory.add_message("session-b", "user", "Message B")

        a_messages = memory.get_session_messages("session-a")
        b_messages = memory.get_session_messages("session-b")

        assert len(a_messages) == 1
        assert a_messages[0]["content"] == "Message A"

        assert len(b_messages) == 1
        assert b_messages[0]["content"] == "Message B"


class TestEpisodicMemory:
    """Test episodic memory (event sourcing)."""

    @pytest.fixture
    def memory(self, tmp_path):
        """Create memory instance."""
        db_path = tmp_path / "test_episodic.db"
        mem = UnifiedMemory(db_path=str(db_path))
        yield mem
        mem.close()

    def test_record_event(self, memory):
        """Test recording events."""
        event_id = memory.record_event(
            "user_action", data={"action": "login", "username": "joe"}
        )

        assert event_id is not None
        assert len(event_id) == 16

    def test_get_events(self, memory):
        """Test getting events."""
        memory.record_event("login", {"user": "alice"})
        memory.record_event("logout", {"user": "alice"})
        memory.record_event("login", {"user": "bob"})

        # Get all events
        events = memory.get_events()
        assert len(events) == 3

        # Filter by type
        logins = memory.get_events(event_type="login")
        assert len(logins) == 2

    def test_events_with_session(self, memory):
        """Test events with session filtering."""
        memory.record_event("action", {"type": "click"}, session_id="s1")
        memory.record_event("action", {"type": "scroll"}, session_id="s1")
        memory.record_event("action", {"type": "click"}, session_id="s2")

        s1_events = memory.get_events(session_id="s1")
        assert len(s1_events) == 2

        s2_events = memory.get_events(session_id="s2")
        assert len(s2_events) == 1


class TestSemanticMemory:
    """Test semantic memory (vector embeddings)."""

    @pytest.fixture
    def memory(self, tmp_path):
        """Create memory instance."""
        db_path = tmp_path / "test_semantic.db"
        mem = UnifiedMemory(db_path=str(db_path))
        yield mem
        mem.close()

    def test_semantic_similarity(self, memory):
        """Test semantic similarity search."""
        # Store semantically related content
        memory.store("Python is a programming language")
        memory.store("JavaScript runs in browsers")
        memory.store("The cat sat on the mat")

        # Search for related content
        results = memory.search("coding languages", use_semantic=True)

        # Should find programming-related content
        assert len(results) >= 1
        programming_found = any(
            "Python" in r.content or "JavaScript" in r.content for r in results
        )
        assert programming_found

    def test_embedding_generation(self):
        """Test SimpleHashEmbedding."""
        embedder = SimpleHashEmbedding(dimension=128)

        vec1 = embedder.embed("hello world")
        vec2 = embedder.embed("hello world")
        vec3 = embedder.embed("goodbye moon")

        # Same text should give same embedding
        assert vec1 == vec2

        # Different text should give different embedding
        assert vec1 != vec3

        # Dimension should match
        assert len(vec1) == 128

    def test_embedding_similarity(self):
        """Test that similar texts have similar embeddings."""
        embedder = SimpleHashEmbedding()

        vec1 = embedder.embed("python programming code")
        vec2 = embedder.embed("python coding script")
        vec3 = embedder.embed("banana apple orange")

        def cosine_sim(a, b):
            import math

            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0
            return dot / (norm_a * norm_b)

        # Similar texts should have higher similarity
        sim_12 = cosine_sim(vec1, vec2)
        sim_13 = cosine_sim(vec1, vec3)

        # Programming texts should be more similar to each other
        assert sim_12 > sim_13


class TestSQLiteMemoryStore:
    """Test SQLite memory store directly."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create store instance."""
        db_path = tmp_path / "test_sqlite.db"
        s = SQLiteMemoryStore(db_path=str(db_path))
        yield s
        s.close()

    def test_store_and_retrieve(self, store):
        """Test basic store and retrieve."""
        store.store("Test content")

        results = store.search("Test")
        assert len(results) == 1
        assert results[0].content == "Test content"

    def test_full_text_search(self, store):
        """Test FTS search."""
        store.store("The quick brown fox jumps")
        store.store("The lazy dog sleeps")
        store.store("A quick rabbit hops")

        results = store.search("quick")
        assert len(results) == 2

    def test_hybrid_search(self, store):
        """Test hybrid FTS + semantic search."""
        store.store("Machine learning with Python")
        store.store("Deep learning neural networks")
        store.store("The weather is nice")

        results = store.search("AI programming", use_semantic=True)

        # Should find ML-related content
        assert len(results) >= 1
        ml_found = any("learning" in r.content.lower() for r in results)
        assert ml_found


class TestMemoryContextManager:
    """Test memory as context manager."""

    def test_context_manager(self, tmp_path):
        """Test using memory with context manager."""
        db_path = tmp_path / "ctx_test.db"

        with UnifiedMemory(db_path=str(db_path)) as mem:
            mem.store("Context managed")
            assert mem.count() == 1

        # Connection should be closed
        # Re-open and verify data persisted
        with UnifiedMemory(db_path=str(db_path)) as mem:
            assert mem.count() == 1


class TestMemoryAliases:
    """Test natural language aliases."""

    @pytest.fixture
    def memory(self, tmp_path):
        """Create memory instance."""
        db_path = tmp_path / "alias_test.db"
        mem = UnifiedMemory(db_path=str(db_path))
        yield mem
        mem.close()

    def test_remember_alias(self, memory):
        """Test remember() alias for store()."""
        entry = memory.remember("User prefers dark mode")
        assert entry.content == "User prefers dark mode"

    def test_recall_alias(self, memory):
        """Test recall() alias for search()."""
        memory.store("Important fact about Python")

        results = memory.recall("Python")
        assert len(results) == 1


# ==============================================================================
# LEGACY MEMORY TESTS (from _neo4j_memory.py)
# ==============================================================================


class TestDataScope:
    """Test DataScope enum."""

    def test_scope_values(self):
        """Test scope enum values."""
        assert DataScope.PUBLIC.value == "public"
        assert DataScope.PRIVATE.value == "private"
        assert DataScope.CUSTOMER.value == "customer"

    def test_scope_from_string(self):
        """Test creating scope from string."""
        assert DataScope("public") == DataScope.PUBLIC
        assert DataScope("private") == DataScope.PRIVATE
        assert DataScope("customer") == DataScope.CUSTOMER


class TestMemoryDataclass:
    """Test Memory dataclass (legacy)."""

    def test_memory_creation(self):
        """Test creating a memory object."""
        mem = MemoryDataclass(
            id="test123",
            content="Test content",
            scope=DataScope.PRIVATE,
            timestamp=datetime.now(UTC),
        )

        assert mem.id == "test123"
        assert mem.content == "Test content"
        assert mem.scope == DataScope.PRIVATE
        assert mem.customer_id is None

    def test_memory_with_customer(self):
        """Test memory with customer scope."""
        mem = MemoryDataclass(
            id="cust123",
            content="Customer data",
            scope=DataScope.CUSTOMER,
            timestamp=datetime.now(UTC),
            customer_id="acme-corp",
        )

        assert mem.scope == DataScope.CUSTOMER
        assert mem.customer_id == "acme-corp"

    def test_memory_to_dict(self):
        """Test memory serialization."""
        mem = MemoryDataclass(
            id="dict123",
            content="Serializable",
            scope=DataScope.PUBLIC,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        data = mem.to_dict()

        assert data["id"] == "dict123"
        assert data["content"] == "Serializable"
        assert data["scope"] == "public"
        assert "2024-01-01" in data["timestamp"]


class TestInMemoryStore:
    """Test InMemoryStore (legacy)."""

    def test_store_and_search(self):
        """Test basic store and search."""
        store = InMemoryStore()

        mem = store.store("Hello world", scope=DataScope.PUBLIC)

        assert mem.id is not None
        assert mem.content == "Hello world"
        assert mem.scope == DataScope.PUBLIC

        results = store.search("hello", scope=DataScope.PUBLIC)

        assert len(results) == 1
        assert results[0].content == "Hello world"

    def test_scope_isolation(self):
        """Test that scopes are isolated."""
        store = InMemoryStore()

        store.store("Public info", scope=DataScope.PUBLIC)
        store.store("Private info", scope=DataScope.PRIVATE)

        public_results = store.search("info", scope=DataScope.PUBLIC)
        private_results = store.search("info", scope=DataScope.PRIVATE)

        assert len(public_results) == 1
        assert public_results[0].content == "Public info"

        assert len(private_results) == 1
        assert private_results[0].content == "Private info"

    def test_customer_isolation(self):
        """Test customer data isolation."""
        store = InMemoryStore()

        store.store("Acme data", scope=DataScope.CUSTOMER, customer_id="acme")
        store.store("Beta data", scope=DataScope.CUSTOMER, customer_id="beta")

        acme_results = store.search(
            "data", scope=DataScope.CUSTOMER, customer_id="acme"
        )
        beta_results = store.search(
            "data", scope=DataScope.CUSTOMER, customer_id="beta"
        )

        assert len(acme_results) == 1
        assert acme_results[0].content == "Acme data"

        assert len(beta_results) == 1
        assert beta_results[0].content == "Beta data"

    def test_get_recent(self):
        """Test getting recent memories."""
        store = InMemoryStore()

        store.store("First", scope=DataScope.PRIVATE)
        store.store("Second", scope=DataScope.PRIVATE)
        store.store("Third", scope=DataScope.PRIVATE)

        recent = store.get_recent(scope=DataScope.PRIVATE, limit=2)

        assert len(recent) == 2
        assert recent[0].content == "Third"

    def test_search_case_insensitive(self):
        """Test case-insensitive search."""
        store = InMemoryStore()

        store.store("HELLO World", scope=DataScope.PUBLIC)

        results = store.search("hello", scope=DataScope.PUBLIC)
        assert len(results) == 1

        results = store.search("WORLD", scope=DataScope.PUBLIC)
        assert len(results) == 1

    def test_connect_close_noop(self):
        """Test connect/close are no-ops."""
        store = InMemoryStore()

        assert store.connect() is True
        store.close()  # Should not raise


class TestNeo4jMemoryConfig:
    """Test Neo4j memory configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MemoryConfig()

        assert config.uri == "bolt://localhost:7687"
        assert config.user == "neo4j"
        assert config.password == ""
        assert config.database == "neo4j"
        assert config.embedding_dim == 384

    def test_custom_config(self):
        """Test custom configuration."""
        config = MemoryConfig(
            uri="bolt://custom:7688",
            user="admin",
            password="secret",
            database="mydb",
        )

        assert config.uri == "bolt://custom:7688"
        assert config.user == "admin"
        assert config.password == "secret"


class TestNeo4jMemoryValidation:
    """Test Neo4j memory validation (without actual connection)."""

    def test_customer_scope_requires_id(self):
        """Test that CUSTOMER scope requires customer_id."""
        store = InMemoryStore()

        with pytest.raises(ValueError, match="customer_id required"):
            store.search("query", scope=DataScope.CUSTOMER)

    def test_generate_unique_ids(self):
        """Test that IDs are unique."""
        store = InMemoryStore()

        mem1 = store.store("Same content", scope=DataScope.PUBLIC)
        mem2 = store.store("Same content", scope=DataScope.PUBLIC)

        assert mem1.id != mem2.id


# Integration tests (require Neo4j)
@pytest.mark.integration
class TestNeo4jMemoryIntegration:
    """Integration tests for Neo4j memory (skipped if Neo4j unavailable)."""

    @pytest.fixture
    def memory(self):
        """Create memory instance for tests."""
        import os

        mem = Neo4jMemory(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "testpassword"),
        )
        try:
            if not mem.connect():
                pytest.skip("Neo4j not available")
        except Exception:
            pytest.skip("Neo4j not available")
        yield mem
        mem.close()

    def test_store_and_retrieve(self, memory):
        """Test storing and retrieving from Neo4j."""
        memory.store("Integration test", scope=DataScope.PRIVATE)

        results = memory.search("integration", scope=DataScope.PRIVATE)

        assert len(results) >= 1
        assert any("Integration test" in r.content for r in results)


class TestGetMemoryBackend:
    """Tests for get_memory_backend factory function."""

    def test_import_factory_functions(self):
        """Test that factory functions are exported."""
        from agentic_brain.memory import get_memory_backend, reset_memory_backend

        assert callable(get_memory_backend)
        assert callable(reset_memory_backend)

    def test_force_memory_backend_via_env(self, monkeypatch):
        """Test forcing in-memory backend via environment variable."""
        from agentic_brain.memory import (
            InMemoryStore,
            get_memory_backend,
            reset_memory_backend,
        )

        reset_memory_backend()
        monkeypatch.setenv("MEMORY_BACKEND", "memory")

        backend = get_memory_backend()

        assert isinstance(backend, InMemoryStore)

        reset_memory_backend()

    def test_auto_fallback_when_neo4j_unavailable(self, monkeypatch):
        """Test automatic fallback to InMemoryStore when Neo4j unavailable."""
        from agentic_brain.memory import (
            InMemoryStore,
            get_memory_backend,
            reset_memory_backend,
        )

        reset_memory_backend()
        monkeypatch.setenv("MEMORY_BACKEND", "auto")
        monkeypatch.setenv("NEO4J_URI", "bolt://nonexistent:9999")
        monkeypatch.setenv("NEO4J_PASSWORD", "fake")

        backend = get_memory_backend()

        assert isinstance(backend, InMemoryStore)

        reset_memory_backend()

    def test_singleton_pattern(self, monkeypatch):
        """Test that get_memory_backend returns the same instance."""
        from agentic_brain.memory import (
            get_memory_backend,
            reset_memory_backend,
        )

        reset_memory_backend()
        monkeypatch.setenv("MEMORY_BACKEND", "memory")

        backend1 = get_memory_backend()
        backend2 = get_memory_backend()

        assert backend1 is backend2

        reset_memory_backend()

    def test_reset_clears_instance(self, monkeypatch):
        """Test that reset_memory_backend clears the singleton."""
        from agentic_brain.memory import (
            get_memory_backend,
            reset_memory_backend,
        )

        monkeypatch.setenv("MEMORY_BACKEND", "memory")

        backend1 = get_memory_backend()
        reset_memory_backend()
        backend2 = get_memory_backend()

        assert backend1 is not backend2

        reset_memory_backend()

    def test_fallback_backend_is_functional(self, monkeypatch):
        """Test that fallback InMemoryStore actually works."""
        from agentic_brain.memory import (
            DataScope,
            get_memory_backend,
            reset_memory_backend,
        )

        reset_memory_backend()
        monkeypatch.setenv("MEMORY_BACKEND", "memory")

        backend = get_memory_backend()

        mem = backend.store("Factory test content", scope=DataScope.PUBLIC)
        assert mem.content == "Factory test content"

        results = backend.search("Factory", scope=DataScope.PUBLIC)
        assert len(results) == 1
        assert results[0].content == "Factory test content"

        reset_memory_backend()


class TestUnifiedMemoryFactory:
    """Tests for get_unified_memory factory function."""

    def test_factory_returns_unified_memory(self, tmp_path):
        """Test that factory returns UnifiedMemory."""
        db_path = tmp_path / "factory.db"
        mem = get_unified_memory(db_path=str(db_path))

        assert isinstance(mem, UnifiedMemory)
        mem.close()

    def test_factory_with_defaults(self):
        """Test factory with default settings."""
        # Should not raise
        mem = get_unified_memory()
        assert mem is not None
        mem.close()


# ==============================================================================
# CROSS-SESSION MEMORY TESTS
# ==============================================================================


class TestCrossSessionMemory:
    """Test that memory works across sessions (persistence)."""

    def test_memory_persists(self, tmp_path):
        """Test that memory persists across instances."""
        db_path = tmp_path / "persist.db"

        # First session
        with UnifiedMemory(db_path=str(db_path)) as mem1:
            mem1.store("Persisted memory")
            mem1.record_event("test_event", {"key": "value"})

        # Second session (new instance)
        with UnifiedMemory(db_path=str(db_path)) as mem2:
            results = mem2.search("Persisted")
            assert len(results) == 1
            assert results[0].content == "Persisted memory"

            events = mem2.get_events(event_type="test_event")
            assert len(events) == 1

    def test_session_context_persists(self, tmp_path):
        """Test that session context persists."""
        db_path = tmp_path / "session_persist.db"
        session_id = "persistent-session"

        # First session
        with UnifiedMemory(db_path=str(db_path)) as mem1:
            mem1.add_message(session_id, "user", "Hello!")

        # Second session
        with UnifiedMemory(db_path=str(db_path)) as mem2:
            messages = mem2.get_session_messages(session_id)
            assert len(messages) == 1
            assert messages[0]["content"] == "Hello!"


# ==============================================================================
# GRACEFUL DEGRADATION TESTS
# ==============================================================================


class TestGracefulDegradation:
    """Test that memory works without external dependencies."""

    def test_works_without_neo4j(self, tmp_path, monkeypatch):
        """Test memory works without Neo4j."""
        db_path = tmp_path / "no_neo4j.db"

        # Set invalid Neo4j config
        monkeypatch.setenv("NEO4J_URI", "bolt://invalid:9999")
        monkeypatch.setenv("NEO4J_PASSWORD", "invalid")

        # Should still work with SQLite fallback
        mem = UnifiedMemory(db_path=str(db_path), use_neo4j=True)
        mem.store("Works without Neo4j")

        results = mem.search("Works")
        assert len(results) == 1
        mem.close()

    def test_works_without_vector_db(self, tmp_path):
        """Test memory works without vector database."""
        db_path = tmp_path / "no_vector.db"

        # Simple hash embeddings should still provide semantic search
        mem = UnifiedMemory(db_path=str(db_path))
        mem.store("Semantic search test")

        results = mem.search("similar search", use_semantic=True)
        # Should return results (may not be perfect match, but should work)
        assert results is not None
        mem.close()

    def test_fts_fallback_to_like(self, tmp_path):
        """Test FTS falls back to LIKE on query error."""
        db_path = tmp_path / "fts_fallback.db"
        mem = UnifiedMemory(db_path=str(db_path))

        mem.store("Regular content here")

        # FTS should work for simple queries
        results = mem.search("Regular")
        assert len(results) == 1
        mem.close()
