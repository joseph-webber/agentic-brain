# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for Neo4j schema migrations."""

from datetime import UTC, datetime, timezone

import pytest

from agentic_brain.migrations import (
    CreateConstraintsMigration,
    CreateIndexesMigration,
    CypherMigration,
    Migration,
    MigrationRunner,
    MigrationStatus,
)


class TestCypherMigration:
    """Tests for Cypher-based migrations."""

    def test_version_required(self):
        """Test that version is required."""
        migration = CypherMigration(
            version="V001",
            description="Test migration",
            up_cypher=["CREATE (n:Test)"],
            down_cypher=["MATCH (n:Test) DELETE n"],
        )
        assert migration.version == "V001"
        assert migration.description == "Test migration"

    def test_checksum_computed(self):
        """Test checksum is computed from cypher."""
        migration = CypherMigration(
            version="V001",
            description="Test",
            up_cypher=["CREATE (n:Test)"],
            down_cypher=["MATCH (n:Test) DELETE n"],
        )
        # Checksum should be 8 characters (MD5 truncated)
        assert len(migration.checksum) == 8

    def test_checksum_changes_with_content(self):
        """Test checksum changes when content changes."""
        m1 = CypherMigration(
            version="V001",
            description="Test",
            up_cypher=["CREATE (n:Test)"],
            down_cypher=["DELETE n"],
        )
        m2 = CypherMigration(
            version="V001",
            description="Test",
            up_cypher=["CREATE (n:Test2)"],  # Different
            down_cypher=["DELETE n"],
        )
        assert m1.checksum != m2.checksum


class TestCreateIndexesMigration:
    """Tests for default indexes migration."""

    def test_version(self):
        """Test migration version."""
        migration = CreateIndexesMigration()
        assert migration.version == "0001"

    def test_description(self):
        """Test migration description."""
        migration = CreateIndexesMigration()
        assert "index" in migration.description.lower()


class TestCreateConstraintsMigration:
    """Tests for default constraints migration."""

    def test_version(self):
        """Test migration version."""
        migration = CreateConstraintsMigration()
        assert migration.version == "0002"

    def test_description(self):
        """Test migration description."""
        migration = CreateConstraintsMigration()
        assert "constraint" in migration.description.lower()


class MockNeo4jDriver:
    """Mock Neo4j driver for testing."""

    def __init__(self):
        self.executed_queries = []
        self.results = {}

    def session(self, database=None):
        return MockSession(self)


class MockSession:
    """Mock Neo4j session."""

    def __init__(self, driver):
        self._driver = driver
        self._transaction = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def run(self, query, **params):
        self._driver.executed_queries.append((query, params))
        return MockResult(self._driver.results.get(query, []))

    def begin_transaction(self):
        self._transaction = MockTransaction(self._driver)
        return self._transaction


class MockTransaction:
    """Mock Neo4j transaction."""

    def __init__(self, driver):
        self._driver = driver
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def run(self, query, **params):
        self._driver.executed_queries.append((query, params))
        return MockResult(self._driver.results.get(query, []))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class MockResult:
    """Mock Neo4j result."""

    def __init__(self, data):
        self._data = data

    def single(self):
        return self._data[0] if self._data else None

    def data(self):
        return self._data

    def __iter__(self):
        return iter(self._data)


class TestMigrationRunner:
    """Tests for MigrationRunner."""

    @pytest.fixture
    def mock_driver(self):
        """Create mock Neo4j driver."""
        return MockNeo4jDriver()

    def test_constructor_with_migrations(self, mock_driver):
        """Test creating runner with migrations."""
        m1 = CypherMigration(
            version="V001",
            description="Test",
            up_cypher=["CREATE (n:Test)"],
            down_cypher=["DELETE n"],
        )
        runner = MigrationRunner(driver=mock_driver, migrations=[m1])
        # Migrations stored in runner
        assert len(runner.migrations) == 1
        assert runner.migrations[0].version == "V001"

    def test_migrations_sorted(self, mock_driver):
        """Test migrations are sorted in version order."""
        m2 = CypherMigration(
            version="002",
            description="Second",
            up_cypher=["CREATE (n:Test2)"],
            down_cypher=["DELETE n"],
        )
        m1 = CypherMigration(
            version="001",
            description="First",
            up_cypher=["CREATE (n:Test1)"],
            down_cypher=["DELETE n"],
        )
        # Pass out of order - should be sorted
        runner = MigrationRunner(driver=mock_driver, migrations=[m2, m1])

        assert runner.migrations[0].version == "001"
        assert runner.migrations[1].version == "002"


class TestMigrationStatus:
    """Tests for MigrationStatus model."""

    def test_create(self):
        """Test creating migration status."""
        status = MigrationStatus(
            version="V001",
            description="Test",
            checksum="abc123",
            executed_at=datetime.now(UTC),
            execution_time_ms=100,
            success=True,
        )
        assert status.version == "V001"
        assert status.success is True


class TestCustomMigration:
    """Test creating custom migration classes."""

    def test_custom_migration(self):
        """Test custom migration implementation."""

        class CustomMigration(Migration):
            """Custom test migration."""

            @property
            def version(self) -> str:
                return "V999"

            @property
            def description(self) -> str:
                return "Custom migration for testing"

            @property
            def checksum(self) -> str:
                return "custom-checksum"

            async def up(self, driver):
                pass

            async def down(self, driver):
                pass

        migration = CustomMigration()
        assert migration.version == "V999"
        assert "Custom" in migration.description


class TestMigrationValidation:
    """Tests for migration validation."""

    def test_version_format_validation(self):
        """Test version format is validated."""
        # Valid formats
        CypherMigration(
            version="V001",
            description="Test",
            up_cypher=["CREATE (n:Test)"],
            down_cypher=["DELETE n"],
        )
        CypherMigration(
            version="V1_initial_schema",
            description="Test",
            up_cypher=["CREATE (n:Test)"],
            down_cypher=["DELETE n"],
        )

    def test_empty_up_cypher_creates_empty_list(self):
        """Test empty up_cypher creates empty list."""
        migration = CypherMigration(
            version="V001",
            description="Test",
            up_cypher=[],  # Empty list is valid
            down_cypher=["DELETE n"],
        )
        # Should work but have empty checksum base
        assert migration.checksum is not None

    def test_empty_description_allowed(self):
        """Test empty description is allowed but not recommended."""
        migration = CypherMigration(
            version="V001",
            description="",
            up_cypher=["CREATE (n:Test)"],
            down_cypher=["DELETE n"],
        )
        assert migration.description == ""
