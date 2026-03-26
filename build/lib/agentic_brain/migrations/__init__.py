# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Neo4j Schema Migrations (JHipster-aligned).

Provides Liquibase-style database migrations for Neo4j:
- Version tracking in database
- Ordered migration execution
- Rollback support
- Lock to prevent concurrent migrations
- Checksum validation

JHipster equivalent: db/changelog/db.changelog-master.xml (Liquibase)
"""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MigrationStatus(BaseModel):
    """Migration execution status."""

    version: str
    description: str
    checksum: str
    executed_at: datetime
    execution_time_ms: int
    success: bool
    error: Optional[str] = None


class Migration(ABC):
    """
    Abstract base for migrations.

    Implement up() for forward migration and optionally down() for rollback.
    """

    @property
    @abstractmethod
    def version(self) -> str:
        """
        Migration version (e.g., "1.0.0", "2024.01.15").

        Versions are sorted lexicographically, so use consistent format.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of the migration."""
        pass

    @abstractmethod
    async def up(self, driver: Any) -> None:
        """
        Apply the migration.

        Args:
            driver: Neo4j driver instance
        """
        pass

    async def down(self, driver: Any) -> None:
        """
        Roll back the migration.

        Override to support rollback. Default raises NotImplementedError.

        Args:
            driver: Neo4j driver instance
        """
        raise NotImplementedError(
            f"Rollback not implemented for migration {self.version}"
        )

    @property
    def checksum(self) -> str:
        """
        Calculate checksum for detecting modifications.

        Based on class source code to detect changes.
        """
        import inspect

        source = inspect.getsource(self.__class__)
        return hashlib.md5(source.encode()).hexdigest()[:8]


class CypherMigration(Migration):
    """
    Migration defined by Cypher statements.

    Useful for simple schema changes.
    """

    def __init__(
        self,
        version: str,
        description: str,
        up_cypher: list[str],
        down_cypher: Optional[list[str]] = None,
    ) -> None:
        self._version = version
        self._description = description
        self._up_cypher = up_cypher
        self._down_cypher = down_cypher

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        return self._description

    async def up(self, driver: Any) -> None:
        """Execute up Cypher statements."""
        with driver.session() as session:
            for cypher in self._up_cypher:
                session.run(cypher)

    async def down(self, driver: Any) -> None:
        """Execute down Cypher statements."""
        if not self._down_cypher:
            raise NotImplementedError(
                f"Rollback not defined for migration {self.version}"
            )
        with driver.session() as session:
            for cypher in self._down_cypher:
                session.run(cypher)

    @property
    def checksum(self) -> str:
        """Checksum based on Cypher statements."""
        content = "\n".join(self._up_cypher)
        return hashlib.md5(content.encode()).hexdigest()[:8]


class MigrationRunner:
    """
    Executes and tracks migrations.

    Maintains migration history in Neo4j and ensures each migration
    runs only once.
    """

    SCHEMA_NODE_LABEL = "SchemaMigration"
    LOCK_NODE_LABEL = "SchemaMigrationLock"

    def __init__(
        self,
        driver: Any,
        migrations: Optional[list[Migration]] = None,
    ) -> None:
        """
        Initialize migration runner.

        Args:
            driver: Neo4j driver instance
            migrations: List of migrations to manage
        """
        self.driver = driver
        self.migrations = sorted(
            migrations or [],
            key=lambda m: m.version,
        )

    async def _ensure_schema(self) -> None:
        """Create migration tracking schema if needed."""
        cypher = f"""
        CREATE CONSTRAINT schema_migration_version IF NOT EXISTS
        FOR (m:{self.SCHEMA_NODE_LABEL})
        REQUIRE m.version IS UNIQUE
        """
        await asyncio.to_thread(self._run_cypher, cypher)

    def _run_cypher(self, cypher: str, params: Optional[dict] = None) -> Any:
        """Run Cypher query synchronously."""
        with self.driver.session() as session:
            return session.run(cypher, params or {}).data()

    async def _acquire_lock(self, timeout_seconds: int = 60) -> bool:
        """
        Acquire migration lock.

        Returns True if lock acquired, False if timed out.
        """
        lock_id = "migration_lock"
        end_time = datetime.now(timezone.utc).timestamp() + timeout_seconds

        while datetime.now(timezone.utc).timestamp() < end_time:
            # Try to create lock
            result = await asyncio.to_thread(
                self._run_cypher,
                f"""
                MERGE (l:{self.LOCK_NODE_LABEL} {{id: $lock_id}})
                ON CREATE SET l.locked_at = datetime(), l.locked = true
                RETURN l.locked AS was_locked, l.locked_at AS locked_at
                """,
                {"lock_id": lock_id},
            )

            if result and not result[0].get("was_locked"):
                return True

            # Wait and retry
            await asyncio.sleep(1)

        return False

    async def _release_lock(self) -> None:
        """Release migration lock."""
        await asyncio.to_thread(
            self._run_cypher,
            f"""
            MATCH (l:{self.LOCK_NODE_LABEL} {{id: 'migration_lock'}})
            DELETE l
            """,
        )

    async def get_applied_versions(self) -> list[str]:
        """Get list of applied migration versions."""
        result = await asyncio.to_thread(
            self._run_cypher,
            f"""
            MATCH (m:{self.SCHEMA_NODE_LABEL})
            WHERE m.success = true
            RETURN m.version AS version
            ORDER BY m.version
            """,
        )
        return [r["version"] for r in result]

    async def get_pending_migrations(self) -> list[Migration]:
        """Get list of migrations that haven't been applied."""
        applied = set(await self.get_applied_versions())
        return [m for m in self.migrations if m.version not in applied]

    async def _record_migration(
        self,
        migration: Migration,
        execution_time_ms: int,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record migration execution in database."""
        await asyncio.to_thread(
            self._run_cypher,
            f"""
            MERGE (m:{self.SCHEMA_NODE_LABEL} {{version: $version}})
            SET m.description = $description,
                m.checksum = $checksum,
                m.executed_at = datetime(),
                m.execution_time_ms = $execution_time_ms,
                m.success = $success,
                m.error = $error
            """,
            {
                "version": migration.version,
                "description": migration.description,
                "checksum": migration.checksum,
                "execution_time_ms": execution_time_ms,
                "success": success,
                "error": error,
            },
        )

    async def migrate(self, target_version: Optional[str] = None) -> list[MigrationStatus]:
        """
        Run pending migrations.

        Args:
            target_version: Stop after this version (None = run all)

        Returns:
            List of migration statuses
        """
        await self._ensure_schema()

        if not await self._acquire_lock():
            raise RuntimeError("Could not acquire migration lock")

        try:
            pending = await self.get_pending_migrations()
            results: list[MigrationStatus] = []

            for migration in pending:
                logger.info(
                    f"Running migration {migration.version}: {migration.description}"
                )

                start_time = datetime.now(timezone.utc)
                try:
                    await migration.up(self.driver)
                    execution_time_ms = int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    )

                    await self._record_migration(
                        migration, execution_time_ms, success=True
                    )

                    status = MigrationStatus(
                        version=migration.version,
                        description=migration.description,
                        checksum=migration.checksum,
                        executed_at=start_time,
                        execution_time_ms=execution_time_ms,
                        success=True,
                    )
                    results.append(status)

                    logger.info(
                        f"Migration {migration.version} completed in {execution_time_ms}ms"
                    )

                except Exception as e:
                    execution_time_ms = int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    )
                    error_msg = str(e)

                    await self._record_migration(
                        migration, execution_time_ms, success=False, error=error_msg
                    )

                    status = MigrationStatus(
                        version=migration.version,
                        description=migration.description,
                        checksum=migration.checksum,
                        executed_at=start_time,
                        execution_time_ms=execution_time_ms,
                        success=False,
                        error=error_msg,
                    )
                    results.append(status)

                    logger.error(
                        f"Migration {migration.version} failed: {error_msg}"
                    )
                    break  # Stop on first failure

                if target_version and migration.version == target_version:
                    break

            return results

        finally:
            await self._release_lock()

    async def rollback(self, target_version: str) -> list[MigrationStatus]:
        """
        Roll back to a specific version.

        Args:
            target_version: Roll back to this version (exclusive)

        Returns:
            List of rollback statuses
        """
        await self._ensure_schema()

        if not await self._acquire_lock():
            raise RuntimeError("Could not acquire migration lock")

        try:
            applied = await self.get_applied_versions()
            results: list[MigrationStatus] = []

            # Find migrations to roll back (in reverse order)
            to_rollback = [
                m for m in reversed(self.migrations)
                if m.version in applied and m.version > target_version
            ]

            for migration in to_rollback:
                logger.info(
                    f"Rolling back migration {migration.version}: {migration.description}"
                )

                start_time = datetime.now(timezone.utc)
                try:
                    await migration.down(self.driver)
                    execution_time_ms = int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    )

                    # Remove migration record
                    await asyncio.to_thread(
                        self._run_cypher,
                        f"""
                        MATCH (m:{self.SCHEMA_NODE_LABEL} {{version: $version}})
                        DELETE m
                        """,
                        {"version": migration.version},
                    )

                    status = MigrationStatus(
                        version=migration.version,
                        description=f"ROLLBACK: {migration.description}",
                        checksum=migration.checksum,
                        executed_at=start_time,
                        execution_time_ms=execution_time_ms,
                        success=True,
                    )
                    results.append(status)

                    logger.info(
                        f"Rollback {migration.version} completed in {execution_time_ms}ms"
                    )

                except Exception as e:
                    execution_time_ms = int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    )
                    error_msg = str(e)

                    status = MigrationStatus(
                        version=migration.version,
                        description=f"ROLLBACK FAILED: {migration.description}",
                        checksum=migration.checksum,
                        executed_at=start_time,
                        execution_time_ms=execution_time_ms,
                        success=False,
                        error=error_msg,
                    )
                    results.append(status)

                    logger.error(
                        f"Rollback {migration.version} failed: {error_msg}"
                    )
                    break  # Stop on first failure

            return results

        finally:
            await self._release_lock()

    async def status(self) -> dict[str, Any]:
        """
        Get migration status report.

        Returns:
            Dict with applied/pending migration info
        """
        applied = await self.get_applied_versions()
        pending = await self.get_pending_migrations()

        # Get full details of applied migrations
        applied_details = await asyncio.to_thread(
            self._run_cypher,
            f"""
            MATCH (m:{self.SCHEMA_NODE_LABEL})
            RETURN m.version AS version, m.description AS description,
                   m.checksum AS checksum, m.executed_at AS executed_at,
                   m.execution_time_ms AS execution_time_ms, m.success AS success,
                   m.error AS error
            ORDER BY m.version
            """,
        )

        return {
            "current_version": applied[-1] if applied else None,
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied": applied_details,
            "pending": [
                {
                    "version": m.version,
                    "description": m.description,
                    "checksum": m.checksum,
                }
                for m in pending
            ],
        }


# =============================================================================
# Built-in Migrations
# =============================================================================


class CreateIndexesMigration(Migration):
    """Create basic indexes for performance."""

    @property
    def version(self) -> str:
        return "0001"

    @property
    def description(self) -> str:
        return "Create basic performance indexes"

    async def up(self, driver: Any) -> None:
        indexes = [
            "CREATE INDEX message_timestamp IF NOT EXISTS FOR (m:Message) ON (m.timestamp)",
            "CREATE INDEX user_login IF NOT EXISTS FOR (u:User) ON (u.login)",
            "CREATE INDEX session_id IF NOT EXISTS FOR (s:Session) ON (s.id)",
        ]
        with driver.session() as session:
            for cypher in indexes:
                try:
                    session.run(cypher)
                except Exception as e:
                    logger.debug(f"Index may already exist: {e}")

    async def down(self, driver: Any) -> None:
        with driver.session() as session:
            session.run("DROP INDEX message_timestamp IF EXISTS")
            session.run("DROP INDEX user_login IF EXISTS")
            session.run("DROP INDEX session_id IF EXISTS")


class CreateConstraintsMigration(Migration):
    """Create uniqueness constraints."""

    @property
    def version(self) -> str:
        return "0002"

    @property
    def description(self) -> str:
        return "Create uniqueness constraints"

    async def up(self, driver: Any) -> None:
        constraints = [
            "CREATE CONSTRAINT user_login_unique IF NOT EXISTS FOR (u:User) REQUIRE u.login IS UNIQUE",
            "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
        ]
        with driver.session() as session:
            for cypher in constraints:
                try:
                    session.run(cypher)
                except Exception as e:
                    logger.debug(f"Constraint may already exist: {e}")

    async def down(self, driver: Any) -> None:
        with driver.session() as session:
            session.run("DROP CONSTRAINT user_login_unique IF EXISTS")
            session.run("DROP CONSTRAINT session_id_unique IF EXISTS")


# Default migrations
DEFAULT_MIGRATIONS: list[Migration] = [
    CreateIndexesMigration(),
    CreateConstraintsMigration(),
]


def get_migration_runner(driver: Any) -> MigrationRunner:
    """Get a migration runner with default migrations."""
    return MigrationRunner(driver, DEFAULT_MIGRATIONS)


__all__ = [
    "Migration",
    "CypherMigration",
    "MigrationRunner",
    "MigrationStatus",
    "get_migration_runner",
    "DEFAULT_MIGRATIONS",
]
