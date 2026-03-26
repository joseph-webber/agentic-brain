# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Neo4j-backed workflow state persistence and recovery.

Provides durable workflow execution with:
- Workflow state storage in graph
- Resume after crash or interruption
- Workflow execution history and lineage
- State versioning and rollback
- Parallel workflow coordination

Example:
    >>> from agentic_brain.workflows.neo4j_state import WorkflowState
    >>> workflow = WorkflowState("data_pipeline")
    >>> await workflow.start({"input": "data.csv"})
    >>> await workflow.update_step("extract", "completed", {"rows": 1000})
    >>> await workflow.update_step("transform", "running")
    >>> # ... crash happens ...
    >>> workflow = WorkflowState.resume("data_pipeline_abc123")
    >>> state = await workflow.get_current_state()
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False


class WorkflowStatus(Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Individual step status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class WorkflowConfig:
    """Configuration for workflow state management."""

    # Use shared neo4j pool
    use_pool: bool = True

    # State persistence
    save_intermediate_states: bool = True
    max_versions: int = 10  # Keep last N versions

    # Recovery
    auto_resume: bool = True
    retry_failed_steps: bool = True
    max_retries: int = 3

    # History
    keep_history_days: int = 90


@dataclass
class StepState:
    """State of a single workflow step."""

    step_id: str
    name: str
    status: StepStatus
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage."""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "retry_count": self.retry_count,
        }


class WorkflowState:
    """
    Neo4j-backed workflow state manager.

    Graph structure:
        (Workflow)-[:CONTAINS]->(Step)-[:NEXT]->(Step)
        (Workflow)-[:VERSION]->(WorkflowVersion)
        (Step)-[:DEPENDS_ON]->(Step)
        (Workflow)-[:EXECUTED_BY]->(Agent/User)

    Features:
    - Durable state storage across crashes
    - Step-level granularity
    - Workflow versioning
    - Execution history and lineage
    - Dependency tracking
    - Resume from any step
    """

    def __init__(
        self,
        workflow_name: str,
        workflow_id: Optional[str] = None,
        config: Optional[WorkflowConfig] = None,
    ):
        """
        Initialize workflow state manager.

        Args:
            workflow_name: Human-readable workflow name
            workflow_id: Unique workflow instance ID (generated if not provided)
            config: Workflow configuration
        """
        self.workflow_name = workflow_name
        self.workflow_id = workflow_id or self._generate_workflow_id()
        self.config = config or WorkflowConfig()
        self._initialized = False
        self._version = 0

    def _generate_workflow_id(self) -> str:
        """Generate unique workflow ID."""
        timestamp = datetime.now(UTC).isoformat()
        return hashlib.sha256(f"{self.workflow_name}_{timestamp}".encode()).hexdigest()[
            :16
        ]

    def _get_session(self):
        """Get Neo4j session using lazy pool."""
        if self.config.use_pool:
            from agentic_brain.core.neo4j_pool import get_session

            return get_session()
        else:
            if not NEO4J_AVAILABLE or GraphDatabase is None:
                raise ImportError(
                    "neo4j package is required. Install with: pip install neo4j"
                )

            driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", ""))
            return driver.session()

    async def initialize(self) -> None:
        """
        Initialize workflow schema.

        Creates:
        - Node labels: Workflow, Step, WorkflowVersion
        - Relationships: CONTAINS, NEXT, DEPENDS_ON, VERSION
        - Indexes for queries
        """
        if self._initialized:
            return

        with self._get_session() as session:
            # Create constraints
            session.run(
                """
                CREATE CONSTRAINT workflow_id IF NOT EXISTS
                FOR (w:Workflow) REQUIRE w.id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT step_id IF NOT EXISTS
                FOR (s:Step) REQUIRE s.id IS UNIQUE
                """
            )

            # Create indexes
            session.run(
                "CREATE INDEX workflow_name IF NOT EXISTS FOR (w:Workflow) ON (w.name)"
            )
            session.run(
                "CREATE INDEX workflow_status IF NOT EXISTS FOR (w:Workflow) ON (w.status)"
            )
            session.run(
                "CREATE INDEX step_status IF NOT EXISTS FOR (s:Step) ON (s.status)"
            )

        self._initialized = True
        logger.info(f"Workflow state initialized: {self.workflow_id}")

    async def start(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Start a new workflow execution.

        Args:
            input_data: Initial workflow input
            metadata: Optional metadata (executor, environment, etc.)
        """
        if not self._initialized:
            await self.initialize()

        input_data = input_data or {}
        metadata = metadata or {}
        timestamp = datetime.now(UTC).isoformat()

        with self._get_session() as session:
            # Create workflow node
            session.run(
                """
                CREATE (w:Workflow {
                    id: $workflow_id,
                    name: $workflow_name,
                    status: $status,
                    input_data: $input_data,
                    metadata: $metadata,
                    started_at: $timestamp,
                    version: 0
                })
                """,
                workflow_id=self.workflow_id,
                workflow_name=self.workflow_name,
                status=WorkflowStatus.RUNNING.value,
                input_data=input_data,
                metadata=metadata,
                timestamp=timestamp,
            )

        self._version = 0
        logger.info(f"Started workflow {self.workflow_id}")

    async def add_step(
        self,
        step_name: str,
        step_id: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[str]] = None,
    ) -> str:
        """
        Add a step to the workflow.

        Args:
            step_name: Human-readable step name
            step_id: Unique step ID (generated if not provided)
            input_data: Input data for this step
            depends_on: List of step IDs this step depends on

        Returns:
            Step ID
        """
        if not self._initialized:
            await self.initialize()

        step_id = step_id or f"{self.workflow_id}_step_{step_name}"
        input_data = input_data or {}
        depends_on = depends_on or []
        timestamp = datetime.now(UTC).isoformat()

        with self._get_session() as session:
            # Create step node
            session.run(
                """
                CREATE (s:Step {
                    id: $step_id,
                    name: $step_name,
                    status: $status,
                    input_data: $input_data,
                    created_at: $timestamp,
                    retry_count: 0
                })
                """,
                step_id=step_id,
                step_name=step_name,
                status=StepStatus.PENDING.value,
                input_data=input_data,
                timestamp=timestamp,
            )

            # Link to workflow
            session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})
                MATCH (s:Step {id: $step_id})
                MERGE (w)-[:CONTAINS]->(s)
                """,
                workflow_id=self.workflow_id,
                step_id=step_id,
            )

            # Link to previous step if exists
            session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(prev:Step)
                WHERE NOT exists((prev)-[:NEXT]->())
                  AND prev.id <> $step_id
                WITH prev
                ORDER BY prev.created_at DESC
                LIMIT 1
                MATCH (s:Step {id: $step_id})
                MERGE (prev)-[:NEXT]->(s)
                RETURN prev.id AS prev_id
                """,
                workflow_id=self.workflow_id,
                step_id=step_id,
            )

            # Create dependencies
            for dep_id in depends_on:
                session.run(
                    """
                    MATCH (s:Step {id: $step_id})
                    MATCH (dep:Step {id: $dep_id})
                    MERGE (s)-[:DEPENDS_ON]->(dep)
                    """,
                    step_id=step_id,
                    dep_id=dep_id,
                )

        logger.debug(
            f"Added step {step_name} ({step_id}) to workflow {self.workflow_id}"
        )
        return step_id

    async def update_step(
        self,
        step_id: str,
        status: str,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update step status and output.

        Args:
            step_id: Step to update
            status: New status
            output_data: Optional output data
            error: Optional error message
        """
        if not self._initialized:
            await self.initialize()

        output_data = output_data or {}
        status_enum = StepStatus(status)
        timestamp = datetime.now(UTC).isoformat()

        with self._get_session() as session:
            query = """
                MATCH (s:Step {id: $step_id})
                SET s.status = $status,
                    s.updated_at = $timestamp
            """

            params = {
                "step_id": step_id,
                "status": status_enum.value,
                "timestamp": timestamp,
            }

            if status_enum == StepStatus.RUNNING and "started_at" not in query:
                query += ", s.started_at = $timestamp"

            if status_enum in [StepStatus.COMPLETED, StepStatus.FAILED]:
                query += ", s.completed_at = $timestamp"

            if output_data:
                query += ", s.output_data = $output_data"
                params["output_data"] = output_data

            if error:
                query += ", s.error = $error"
                params["error"] = error

            if status_enum == StepStatus.RETRYING:
                query += ", s.retry_count = s.retry_count + 1"

            session.run(query, **params)

            # Update workflow status if needed
            if status_enum == StepStatus.FAILED:
                session.run(
                    """
                    MATCH (w:Workflow {id: $workflow_id})
                    SET w.status = $status,
                        w.last_updated = $timestamp
                    """,
                    workflow_id=self.workflow_id,
                    status=WorkflowStatus.FAILED.value,
                    timestamp=timestamp,
                )

        # Save version if enabled
        if self.config.save_intermediate_states:
            await self._save_version()

        logger.debug(f"Updated step {step_id} to status {status}")

    async def _save_version(self) -> None:
        """Save current workflow state as a version."""
        self._version += 1

        with self._get_session() as session:
            # Get current state
            result = session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})
                OPTIONAL MATCH (w)-[:CONTAINS]->(s:Step)
                WITH w,
                     collect({
                         id: s.id,
                         name: s.name,
                         status: s.status,
                         output_data: s.output_data,
                         error: s.error
                     }) AS steps
                RETURN w.status AS workflow_status,
                       w.input_data AS input_data,
                       steps
                """,
                workflow_id=self.workflow_id,
            )

            record = result.single()
            if not record:
                return

            # Create version node
            version_id = f"{self.workflow_id}_v{self._version}"
            session.run(
                """
                CREATE (v:WorkflowVersion {
                    id: $version_id,
                    workflow_id: $workflow_id,
                    version: $version,
                    workflow_status: $workflow_status,
                    state: $state,
                    created_at: datetime()
                })
                """,
                version_id=version_id,
                workflow_id=self.workflow_id,
                version=self._version,
                workflow_status=record["workflow_status"],
                state=json.dumps(
                    {
                        "input_data": record["input_data"],
                        "steps": record["steps"],
                    }
                ),
            )

            # Link to workflow
            session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})
                MATCH (v:WorkflowVersion {id: $version_id})
                MERGE (w)-[:VERSION]->(v)
                """,
                workflow_id=self.workflow_id,
                version_id=version_id,
            )

            # Clean up old versions if needed
            if self._version > self.config.max_versions:
                session.run(
                    """
                    MATCH (w:Workflow {id: $workflow_id})-[:VERSION]->(v:WorkflowVersion)
                    WITH v
                    ORDER BY v.version ASC
                    LIMIT 1
                    DETACH DELETE v
                    """,
                    workflow_id=self.workflow_id,
                )

    async def complete(self, output_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark workflow as completed.

        Args:
            output_data: Final workflow output
        """
        output_data = output_data or {}
        timestamp = datetime.now(UTC).isoformat()

        with self._get_session() as session:
            session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})
                SET w.status = $status,
                    w.output_data = $output_data,
                    w.completed_at = $timestamp
                """,
                workflow_id=self.workflow_id,
                status=WorkflowStatus.COMPLETED.value,
                output_data=output_data,
                timestamp=timestamp,
            )

        await self._save_version()
        logger.info(f"Completed workflow {self.workflow_id}")

    async def fail(self, error: str) -> None:
        """
        Mark workflow as failed.

        Args:
            error: Error description
        """
        timestamp = datetime.now(UTC).isoformat()

        with self._get_session() as session:
            session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})
                SET w.status = $status,
                    w.error = $error,
                    w.failed_at = $timestamp
                """,
                workflow_id=self.workflow_id,
                status=WorkflowStatus.FAILED.value,
                error=error,
                timestamp=timestamp,
            )

        await self._save_version()
        logger.error(f"Failed workflow {self.workflow_id}: {error}")

    async def get_current_state(self) -> Dict[str, Any]:
        """
        Get current workflow state.

        Returns:
            Dict with workflow info and all steps
        """
        if not self._initialized:
            await self.initialize()

        with self._get_session() as session:
            result = session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})
                OPTIONAL MATCH (w)-[:CONTAINS]->(s:Step)
                WITH w,
                     collect({
                         id: s.id,
                         name: s.name,
                         status: s.status,
                         input_data: s.input_data,
                         output_data: s.output_data,
                         error: s.error,
                         started_at: s.started_at,
                         completed_at: s.completed_at,
                         retry_count: s.retry_count
                     }) AS steps
                RETURN w.id AS id,
                       w.name AS name,
                       w.status AS status,
                       w.input_data AS input_data,
                       w.output_data AS output_data,
                       w.error AS error,
                       w.started_at AS started_at,
                       w.completed_at AS completed_at,
                       w.version AS version,
                       steps
                """,
                workflow_id=self.workflow_id,
            )

            record = result.single()
            if record:
                return {
                    "id": record["id"],
                    "name": record["name"],
                    "status": record["status"],
                    "input_data": record["input_data"],
                    "output_data": record["output_data"],
                    "error": record["error"],
                    "started_at": record["started_at"],
                    "completed_at": record["completed_at"],
                    "version": record["version"],
                    "steps": record["steps"],
                }

        return {"id": self.workflow_id, "status": "unknown", "steps": []}

    async def get_next_step(self) -> Optional[StepState]:
        """
        Get next step ready to execute.

        Returns:
            Next pending step with all dependencies completed, or None
        """
        with self._get_session() as session:
            result = session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(s:Step)
                WHERE s.status = $pending_status
                WITH s
                OPTIONAL MATCH (s)-[:DEPENDS_ON]->(dep:Step)
                WITH s, collect(dep.status) AS dep_statuses
                WHERE all(status IN dep_statuses WHERE status = $completed_status)
                RETURN s.id AS step_id,
                       s.name AS name,
                       s.status AS status,
                       s.input_data AS input_data,
                       s.output_data AS output_data,
                       s.error AS error,
                       s.started_at AS started_at,
                       s.completed_at AS completed_at,
                       s.retry_count AS retry_count
                ORDER BY s.created_at ASC
                LIMIT 1
                """,
                workflow_id=self.workflow_id,
                pending_status=StepStatus.PENDING.value,
                completed_status=StepStatus.COMPLETED.value,
            )

            record = result.single()
            if record:
                return StepState(
                    step_id=record["step_id"],
                    name=record["name"],
                    status=StepStatus(record["status"]),
                    input_data=record["input_data"] or {},
                    output_data=record["output_data"] or {},
                    error=record["error"],
                    started_at=(
                        datetime.fromisoformat(record["started_at"])
                        if record["started_at"]
                        else None
                    ),
                    completed_at=(
                        datetime.fromisoformat(record["completed_at"])
                        if record["completed_at"]
                        else None
                    ),
                    retry_count=record["retry_count"],
                )

        return None

    @classmethod
    async def resume(
        cls, workflow_id: str, config: Optional[WorkflowConfig] = None
    ) -> WorkflowState:
        """
        Resume an existing workflow from its last state.

        Args:
            workflow_id: Workflow to resume
            config: Optional config override

        Returns:
            WorkflowState instance ready to continue
        """
        config = config or WorkflowConfig()

        # Create instance (workflow_name will be loaded)
        instance = cls("", workflow_id, config)
        await instance.initialize()

        # Load workflow name
        with instance._get_session() as session:
            result = session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})
                RETURN w.name AS name, w.version AS version
                """,
                workflow_id=workflow_id,
            )

            record = result.single()
            if record:
                instance.workflow_name = record["name"]
                instance._version = record["version"] or 0
            else:
                raise ValueError(f"Workflow {workflow_id} not found")

        logger.info(f"Resumed workflow {workflow_id}")
        return instance

    async def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get workflow execution history.

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of historical states
        """
        history = []

        with self._get_session() as session:
            result = session.run(
                """
                MATCH (w:Workflow {id: $workflow_id})-[:VERSION]->(v:WorkflowVersion)
                RETURN v.version AS version,
                       v.workflow_status AS status,
                       v.state AS state,
                       v.created_at AS created_at
                ORDER BY v.version DESC
                LIMIT $limit
                """,
                workflow_id=self.workflow_id,
                limit=limit,
            )

            for record in result:
                history.append(
                    {
                        "version": record["version"],
                        "status": record["status"],
                        "state": json.loads(record["state"]),
                        "created_at": record["created_at"],
                    }
                )

        return history

    async def close(self) -> None:
        """Close and cleanup."""
        logger.info(f"Closing workflow state {self.workflow_id}")
