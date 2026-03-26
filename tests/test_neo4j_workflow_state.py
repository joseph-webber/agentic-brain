# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for Neo4j Workflow State."""

import json
from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentic_brain.workflows.neo4j_state import (
    StepState,
    StepStatus,
    WorkflowConfig,
    WorkflowState,
    WorkflowStatus,
)


@pytest.fixture
def config():
    """Create test configuration."""
    return WorkflowConfig(
        use_pool=True,
        save_intermediate_states=True,
        max_versions=10,
    )


@pytest.fixture
def workflow(config):
    """Create workflow state instance."""
    return WorkflowState("test_workflow", workflow_id="test_wf_123", config=config)


@pytest.fixture
def mock_session():
    """Create mock Neo4j session."""
    session = MagicMock()
    session.run = MagicMock(return_value=MagicMock())
    session.close = MagicMock()
    return session


@pytest.mark.asyncio
async def test_initialize(workflow, mock_session):
    """Test initialization creates schema."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        await workflow.initialize()

        assert workflow._initialized is True
        assert mock_session.run.call_count >= 2  # Constraints + indexes


@pytest.mark.asyncio
async def test_start_workflow(workflow, mock_session):
    """Test starting a workflow."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        await workflow.start(
            input_data={"file": "data.csv"},
            metadata={"executor": "test"},
        )

        assert workflow._version == 0
        # Verify workflow creation
        assert mock_session.run.call_count >= 1


@pytest.mark.asyncio
async def test_add_step(workflow, mock_session):
    """Test adding a step to workflow."""
    mock_result = MagicMock()
    mock_result.single.return_value = None
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        workflow._initialized = True
        step_id = await workflow.add_step(
            step_name="extract",
            input_data={"source": "file.csv"},
        )

        assert step_id is not None
        assert "extract" in step_id


@pytest.mark.asyncio
async def test_update_step(workflow, mock_session):
    """Test updating step status."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        workflow._initialized = True
        await workflow.update_step(
            step_id="step1",
            status="completed",
            output_data={"rows": 1000},
        )

        # Verify update call
        assert mock_session.run.call_count >= 1


@pytest.mark.asyncio
async def test_complete_workflow(workflow, mock_session):
    """Test completing a workflow."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock _save_version
        with patch.object(workflow, "_save_version"):
            await workflow.complete(output_data={"result": "success"})

            # Verify workflow completion
            assert mock_session.run.call_count >= 1


@pytest.mark.asyncio
async def test_fail_workflow(workflow, mock_session):
    """Test failing a workflow."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        with patch.object(workflow, "_save_version"):
            await workflow.fail(error="Test error")

            # Verify failure record
            assert mock_session.run.call_count >= 1


@pytest.mark.asyncio
async def test_get_current_state(workflow, mock_session):
    """Test getting current workflow state."""
    mock_record = {
        "id": "test_wf_123",
        "name": "test_workflow",
        "status": WorkflowStatus.RUNNING.value,
        "input_data": {"file": "data.csv"},
        "output_data": None,
        "error": None,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "version": 0,
        "steps": [
            {
                "id": "step1",
                "name": "extract",
                "status": StepStatus.COMPLETED.value,
                "input_data": {},
                "output_data": {"rows": 1000},
                "error": None,
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "retry_count": 0,
            }
        ],
    }

    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        workflow._initialized = True
        state = await workflow.get_current_state()

        assert state["id"] == "test_wf_123"
        assert state["status"] == WorkflowStatus.RUNNING.value
        assert len(state["steps"]) == 1


@pytest.mark.asyncio
async def test_get_next_step(workflow, mock_session):
    """Test getting next step to execute."""
    mock_record = {
        "step_id": "step2",
        "name": "transform",
        "status": StepStatus.PENDING.value,
        "input_data": {},
        "output_data": {},
        "error": None,
        "started_at": None,
        "completed_at": None,
        "retry_count": 0,
    }

    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        next_step = await workflow.get_next_step()

        assert next_step is not None
        assert next_step.name == "transform"
        assert next_step.status == StepStatus.PENDING


@pytest.mark.asyncio
async def test_save_version(workflow, mock_session):
    """Test saving workflow version."""
    mock_record = {
        "workflow_status": WorkflowStatus.RUNNING.value,
        "input_data": {},
        "steps": [],
    }

    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        await workflow._save_version()

        assert workflow._version == 1


@pytest.mark.asyncio
async def test_resume_workflow(mock_session):
    """Test resuming an existing workflow."""
    mock_record = {
        "name": "test_workflow",
        "version": 2,
    }

    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        workflow = await WorkflowState.resume("test_wf_123")

        assert workflow.workflow_id == "test_wf_123"
        assert workflow.workflow_name == "test_workflow"
        assert workflow._version == 2


@pytest.mark.asyncio
async def test_get_execution_history(workflow, mock_session):
    """Test getting workflow execution history."""
    mock_records = [
        {
            "version": 2,
            "status": WorkflowStatus.RUNNING.value,
            "state": json.dumps({"input_data": {}, "steps": []}),
            "created_at": datetime.now(UTC).isoformat(),
        },
        {
            "version": 1,
            "status": WorkflowStatus.RUNNING.value,
            "state": json.dumps({"input_data": {}, "steps": []}),
            "created_at": datetime.now(UTC).isoformat(),
        },
    ]

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(mock_records)
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        history = await workflow.get_execution_history(limit=10)

        assert len(history) == 2
        assert history[0]["version"] == 2
        assert history[1]["version"] == 1


@pytest.mark.asyncio
async def test_step_dependencies(workflow, mock_session):
    """Test adding step with dependencies."""
    mock_result = MagicMock()
    mock_result.single.return_value = None
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        workflow._initialized = True
        step_id = await workflow.add_step(
            step_name="load",
            depends_on=["step_extract", "step_transform"],
        )

        assert step_id is not None
        # Verify dependency creation
        assert mock_session.run.call_count >= 3  # step + workflow link + dependencies


def test_workflow_status_enum():
    """Test workflow status enum values."""
    assert WorkflowStatus.PENDING.value == "pending"
    assert WorkflowStatus.RUNNING.value == "running"
    assert WorkflowStatus.COMPLETED.value == "completed"
    assert WorkflowStatus.FAILED.value == "failed"


def test_step_status_enum():
    """Test step status enum values."""
    assert StepStatus.PENDING.value == "pending"
    assert StepStatus.RUNNING.value == "running"
    assert StepStatus.COMPLETED.value == "completed"
    assert StepStatus.FAILED.value == "failed"


def test_step_state_to_dict():
    """Test StepState serialization."""
    step = StepState(
        step_id="step1",
        name="extract",
        status=StepStatus.COMPLETED,
        input_data={"file": "data.csv"},
        output_data={"rows": 1000},
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    step_dict = step.to_dict()

    assert step_dict["step_id"] == "step1"
    assert step_dict["name"] == "extract"
    assert step_dict["status"] == "completed"
    assert step_dict["output_data"]["rows"] == 1000


def test_config_defaults():
    """Test default configuration values."""
    config = WorkflowConfig()

    assert config.use_pool is True
    assert config.save_intermediate_states is True
    assert config.max_versions == 10
    assert config.retry_failed_steps is True
