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

"""Tests for Temporal patterns."""

from __future__ import annotations

import pytest

# Skip all temporal tests if temporalio not installed
temporalio = pytest.importorskip("temporalio")

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from agentic_brain.workflows.temporal import activities, patterns


@pytest.mark.asyncio
async def test_human_in_the_loop_workflow():
    """Test human-in-the-loop workflow with approval."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[patterns.HumanInTheLoopWorkflow],
            activities=[
                activities.llm_query,
                activities.send_notification,
            ],
        ):
            handle = await env.client.start_workflow(
                patterns.HumanInTheLoopWorkflow.run,
                "Deploy to production",
                auto_approve_after=None,
                id="test-hitl",
                task_queue="test",
            )

            # Send approval signal
            await handle.signal(
                patterns.HumanInTheLoopWorkflow.approval,
                "Looks good!",
            )

            result = await handle.result()

            assert result["success"] is True
            assert result["approved"] is True
            assert result["feedback"] == "Looks good!"


@pytest.mark.asyncio
async def test_human_in_the_loop_rejection():
    """Test human-in-the-loop workflow with rejection."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[patterns.HumanInTheLoopWorkflow],
            activities=[
                activities.llm_query,
                activities.send_notification,
            ],
        ):
            handle = await env.client.start_workflow(
                patterns.HumanInTheLoopWorkflow.run,
                "Deploy to production",
                auto_approve_after=None,
                id="test-hitl-reject",
                task_queue="test",
            )

            # Send rejection signal
            await handle.signal(
                patterns.HumanInTheLoopWorkflow.rejection,
                "Not ready yet",
            )

            result = await handle.result()

            assert result["success"] is False
            assert result["approved"] is False
            assert result["reason"] == "Not ready yet"


@pytest.mark.asyncio
async def test_scheduled_workflow():
    """Test scheduled workflow execution."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[patterns.ScheduledWorkflow],
            activities=[activities.llm_query],
        ):
            result = await env.client.execute_workflow(
                patterns.ScheduledWorkflow.run,
                "Check system health",
                interval_seconds=60,
                max_iterations=3,
                id="test-scheduled",
                task_queue="test",
            )

            assert result["success"] is True
            assert result["total_executions"] == 3
            assert len(result["results"]) == 3


@pytest.mark.asyncio
async def test_saga_pattern():
    """Test saga pattern with compensation."""
    from temporalio import workflow

    from agentic_brain.workflows.temporal.patterns import SagaPattern

    @workflow.defn
    class TestSagaWorkflow:
        @workflow.run
        async def run(self) -> dict:
            saga = SagaPattern()

            saga.add_step(
                "step1",
                activities.database_operation,
                activities.database_operation,
                {"action": "create", "data": "test"},
            )

            saga.add_step(
                "step2",
                activities.database_operation,
                activities.database_operation,
                {"action": "update", "data": "test"},
            )

            return await saga.execute()

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[TestSagaWorkflow],
            activities=[activities.database_operation],
        ):
            result = await env.client.execute_workflow(
                TestSagaWorkflow.run,
                id="test-saga",
                task_queue="test",
            )

            assert result["success"] is True
            assert len(result["results"]) == 2
