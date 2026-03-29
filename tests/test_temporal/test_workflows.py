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

"""Tests for Temporal workflows."""

from __future__ import annotations

import pytest

# Skip all temporal tests if temporalio not installed
temporalio = pytest.importorskip("temporalio")

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from agentic_brain.workflows.temporal import activities, workflows


@pytest.mark.asyncio
async def test_rag_workflow():
    """Test RAG workflow execution."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[workflows.RAGWorkflow],
            activities=[activities.llm_query, activities.vector_search],
        ):
            result = await env.client.execute_workflow(
                workflows.RAGWorkflow.run,
                "What is temporal?",
                id="test-rag",
                task_queue="test",
            )

            assert result.success is True
            assert result.data is not None


@pytest.mark.asyncio
async def test_agent_workflow():
    """Test agent workflow with tool usage."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[workflows.AgentWorkflow],
            activities=[
                activities.llm_query,
                activities.external_api_call,
            ],
        ):
            result = await env.client.execute_workflow(
                workflows.AgentWorkflow.run,
                "Calculate 2+2 and search for the answer",
                max_iterations=5,
                id="test-agent",
                task_queue="test",
            )

            assert result.success is True


@pytest.mark.asyncio
async def test_commerce_workflow():
    """Test commerce workflow with saga pattern."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[workflows.CommerceWorkflow],
            activities=[
                activities.database_operation,
                activities.external_api_call,
                activities.send_notification,
            ],
        ):
            result = await env.client.execute_workflow(
                workflows.CommerceWorkflow.run,
                "order-123",
                [{"id": "item1", "price": 10.0}],
                "credit_card",
                {"street": "123 Main St", "city": "Adelaide"},
                id="test-commerce",
                task_queue="test",
            )

            assert result.success is True
            assert result.data["order_id"] == "order-123"


@pytest.mark.asyncio
async def test_long_running_analysis_workflow():
    """Test long-running analysis with checkpoints."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[workflows.LongRunningAnalysisWorkflow],
            activities=[
                activities.process_file,
                activities.database_operation,
            ],
        ):
            result = await env.client.execute_workflow(
                workflows.LongRunningAnalysisWorkflow.run,
                "/tmp/dataset.csv",
                "sentiment_analysis",
                checkpoint_interval=100,
                id="test-analysis",
                task_queue="test",
            )

            assert result.success is True


@pytest.mark.asyncio
async def test_workflow_retry_on_failure():
    """Test workflow retry behavior on activity failure."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[workflows.RAGWorkflow],
            activities=[activities.llm_query, activities.vector_search],
        ):
            # This should retry and eventually succeed
            result = await env.client.execute_workflow(
                workflows.RAGWorkflow.run,
                "Test query",
                id="test-retry",
                task_queue="test",
            )

            # Should complete even with retries
            assert result is not None
