"""
Tests for agentic-brain memory module.
"""

import pytest
from datetime import datetime

from agentic_brain.memory import (
    DataScope,
    Memory,
    InMemoryStore,
    Neo4jMemory,
    MemoryConfig,
)


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


class TestMemory:
    """Test Memory dataclass."""
    
    def test_memory_creation(self):
        """Test creating a memory object."""
        mem = Memory(
            id="test123",
            content="Test content",
            scope=DataScope.PRIVATE,
            timestamp=datetime.utcnow(),
        )
        
        assert mem.id == "test123"
        assert mem.content == "Test content"
        assert mem.scope == DataScope.PRIVATE
        assert mem.customer_id is None
    
    def test_memory_with_customer(self):
        """Test memory with customer scope."""
        mem = Memory(
            id="cust123",
            content="Customer data",
            scope=DataScope.CUSTOMER,
            timestamp=datetime.utcnow(),
            customer_id="acme-corp",
        )
        
        assert mem.scope == DataScope.CUSTOMER
        assert mem.customer_id == "acme-corp"
    
    def test_memory_to_dict(self):
        """Test memory serialization."""
        mem = Memory(
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
    """Test InMemoryStore."""
    
    def test_store_and_search(self):
        """Test basic store and search."""
        store = InMemoryStore()
        
        # Store a memory
        mem = store.store("Hello world", scope=DataScope.PUBLIC)
        
        assert mem.id is not None
        assert mem.content == "Hello world"
        assert mem.scope == DataScope.PUBLIC
        
        # Search for it
        results = store.search("hello", scope=DataScope.PUBLIC)
        
        assert len(results) == 1
        assert results[0].content == "Hello world"
    
    def test_scope_isolation(self):
        """Test that scopes are isolated."""
        store = InMemoryStore()
        
        # Store in different scopes
        store.store("Public info", scope=DataScope.PUBLIC)
        store.store("Private info", scope=DataScope.PRIVATE)
        
        # Search should respect scope
        public_results = store.search("info", scope=DataScope.PUBLIC)
        private_results = store.search("info", scope=DataScope.PRIVATE)
        
        assert len(public_results) == 1
        assert public_results[0].content == "Public info"
        
        assert len(private_results) == 1
        assert private_results[0].content == "Private info"
    
    def test_customer_isolation(self):
        """Test customer data isolation."""
        store = InMemoryStore()
        
        # Store for different customers
        store.store("Acme data", scope=DataScope.CUSTOMER, customer_id="acme")
        store.store("Beta data", scope=DataScope.CUSTOMER, customer_id="beta")
        
        # Each customer only sees their data
        acme_results = store.search("data", scope=DataScope.CUSTOMER, customer_id="acme")
        beta_results = store.search("data", scope=DataScope.CUSTOMER, customer_id="beta")
        
        assert len(acme_results) == 1
        assert acme_results[0].content == "Acme data"
        
        assert len(beta_results) == 1
        assert beta_results[0].content == "Beta data"
    
    def test_get_recent(self):
        """Test getting recent memories."""
        store = InMemoryStore()
        
        # Store multiple memories
        store.store("First", scope=DataScope.PRIVATE)
        store.store("Second", scope=DataScope.PRIVATE)
        store.store("Third", scope=DataScope.PRIVATE)
        
        # Get recent
        recent = store.get_recent(scope=DataScope.PRIVATE, limit=2)
        
        assert len(recent) == 2
        # Most recent should be first
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
        store = InMemoryStore()  # Use in-memory for validation tests
        
        # Should raise for CUSTOMER scope without customer_id
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
        mem = Neo4jMemory(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="test",
        )
        try:
            mem.connect()
            yield mem
        except Exception:
            pytest.skip("Neo4j not available")
        finally:
            mem.close()
    
    def test_store_and_retrieve(self, memory):
        """Test storing and retrieving from Neo4j."""
        mem = memory.store("Integration test", scope=DataScope.PRIVATE)
        
        results = memory.search("integration", scope=DataScope.PRIVATE)
        
        assert len(results) >= 1
        assert any("Integration test" in r.content for r in results)
