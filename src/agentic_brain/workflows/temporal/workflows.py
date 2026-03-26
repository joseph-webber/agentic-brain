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

"""Temporal workflow definitions for durable execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

# Optional dependency - graceful fallback if not installed
try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy
    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    # Create stub for workflow decorators
    class _WorkflowStub:
        @staticmethod
        def defn(cls):
            return cls
        @staticmethod
        def run(fn):
            return fn
        @staticmethod
        def signal(name=None):
            def decorator(fn):
                return fn
            return decorator
        @staticmethod
        def query(name=None):
            def decorator(fn):
                return fn
            return decorator
    workflow = _WorkflowStub()
    RetryPolicy = None  # type: ignore

from . import activities


@dataclass
class WorkflowResult:
    """Standard workflow result."""

    success: bool
    data: Any
    error: Optional[str] = None


@workflow.defn
class RAGWorkflow:
    """Retrieval-Augmented Generation workflow.

    Query → Retrieve relevant context → Generate response.
    """

    @workflow.run
    async def run(
        self,
        query: str,
        collection: str = "default",
        top_k: int = 5,
        model: str = "gpt-4",
    ) -> WorkflowResult:
        """Execute RAG workflow.

        Args:
            query: User query.
            collection: Vector store collection.
            top_k: Number of results to retrieve.
            model: LLM model to use.

        Returns:
            Generated response with sources.
        """
        workflow.logger.info(f"Starting RAG workflow for query: {query}")

        try:
            # Step 1: Retrieve relevant context
            context = await workflow.execute_activity(
                activities.vector_search,
                args=[query, collection, top_k],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            # Step 2: Generate response with context
            response = await workflow.execute_activity(
                activities.llm_query,
                args=[query, context, model],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            workflow.logger.info("RAG workflow completed successfully")
            return WorkflowResult(success=True, data=response)

        except Exception as e:
            workflow.logger.error(f"RAG workflow failed: {e}")
            return WorkflowResult(success=False, data=None, error=str(e))


@workflow.defn
class AgentWorkflow:
    """Multi-step agent reasoning workflow with tool usage."""

    @workflow.run
    async def run(
        self,
        task: str,
        max_iterations: int = 10,
        tools: list[str] | None = None,
    ) -> WorkflowResult:
        """Execute agent workflow with tool usage.

        Args:
            task: Task description.
            max_iterations: Maximum reasoning iterations.
            tools: Available tools for agent.

        Returns:
            Agent's final answer.
        """
        workflow.logger.info(f"Starting agent workflow for task: {task}")
        tools = tools or ["search", "calculate", "code"]

        try:
            context = {"task": task, "history": [], "tools": tools}

            for i in range(max_iterations):
                workflow.logger.info(f"Agent iteration {i+1}/{max_iterations}")

                # Get next action from LLM
                action = await workflow.execute_activity(
                    activities.llm_query,
                    args=[
                        "Given task and history, what's the next action?",
                        context,
                        "gpt-4",
                    ],
                    start_to_close_timeout=timedelta(seconds=60),
                )

                context["history"].append({"iteration": i, "action": action})

                # Check if agent is done
                if action.get("done"):
                    workflow.logger.info("Agent completed task")
                    return WorkflowResult(
                        success=True,
                        data=action.get("answer"),
                    )

                # Execute tool if specified
                if tool := action.get("tool"):
                    result = await workflow.execute_activity(
                        activities.external_api_call,
                        args=[tool, action.get("tool_input")],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                    context["history"][-1]["tool_result"] = result

            return WorkflowResult(
                success=False,
                data=None,
                error="Max iterations reached",
            )

        except Exception as e:
            workflow.logger.error(f"Agent workflow failed: {e}")
            return WorkflowResult(success=False, data=None, error=str(e))


@workflow.defn
class CommerceWorkflow:
    """E-commerce order processing workflow with saga pattern."""

    @workflow.run
    async def run(
        self,
        order_id: str,
        items: list[dict[str, Any]],
        payment_method: str,
        shipping_address: dict[str, str],
    ) -> WorkflowResult:
        """Process e-commerce order with rollback support.

        Args:
            order_id: Unique order ID.
            items: Order items.
            payment_method: Payment method.
            shipping_address: Shipping address.

        Returns:
            Order processing result.
        """
        workflow.logger.info(f"Processing order: {order_id}")
        compensations: list[dict[str, Any]] = []

        try:
            # Step 1: Reserve inventory
            inventory = await workflow.execute_activity(
                activities.database_operation,
                args=["reserve_inventory", {"order_id": order_id, "items": items}],
                start_to_close_timeout=timedelta(seconds=30),
            )
            compensations.append({"action": "release_inventory", "data": inventory})

            # Step 2: Process payment
            payment = await workflow.execute_activity(
                activities.external_api_call,
                args=[
                    "process_payment",
                    {
                        "order_id": order_id,
                        "method": payment_method,
                        "amount": sum(item["price"] for item in items),
                    },
                ],
                start_to_close_timeout=timedelta(seconds=60),
            )
            compensations.append({"action": "refund_payment", "data": payment})

            # Step 3: Create shipment
            shipment = await workflow.execute_activity(
                activities.external_api_call,
                args=[
                    "create_shipment",
                    {
                        "order_id": order_id,
                        "items": items,
                        "address": shipping_address,
                    },
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Step 4: Send confirmation
            await workflow.execute_activity(
                activities.send_notification,
                args=[
                    "order_confirmation",
                    {
                        "order_id": order_id,
                        "shipment": shipment,
                    },
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )

            workflow.logger.info(f"Order {order_id} processed successfully")
            return WorkflowResult(
                success=True,
                data={"order_id": order_id, "shipment": shipment},
            )

        except Exception as e:
            workflow.logger.error(f"Order processing failed: {e}")

            # Execute compensations in reverse order
            for compensation in reversed(compensations):
                try:
                    await workflow.execute_activity(
                        activities.database_operation,
                        args=[
                            compensation["action"],
                            compensation["data"],
                        ],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                except Exception as comp_error:
                    workflow.logger.error(f"Compensation failed: {comp_error}")

            return WorkflowResult(success=False, data=None, error=str(e))


@workflow.defn
class LongRunningAnalysisWorkflow:
    """Long-running data analysis workflow with checkpoints."""

    @workflow.run
    async def run(
        self,
        dataset_path: str,
        analysis_type: str,
        checkpoint_interval: int = 1000,
    ) -> WorkflowResult:
        """Execute long-running analysis with checkpoints.

        Args:
            dataset_path: Path to dataset.
            analysis_type: Type of analysis.
            checkpoint_interval: Records between checkpoints.

        Returns:
            Analysis results.
        """
        workflow.logger.info(f"Starting analysis: {analysis_type} on {dataset_path}")

        try:
            # Load dataset metadata
            metadata = await workflow.execute_activity(
                activities.process_file,
                args=["get_metadata", dataset_path],
                start_to_close_timeout=timedelta(seconds=30),
            )

            total_records = metadata["record_count"]
            processed = 0
            results = []

            # Process in batches with checkpoints
            while processed < total_records:
                batch_size = min(checkpoint_interval, total_records - processed)

                workflow.logger.info(
                    f"Processing records {processed} to {processed + batch_size}"
                )

                batch_result = await workflow.execute_activity(
                    activities.process_file,
                    args=[
                        analysis_type,
                        dataset_path,
                        processed,
                        batch_size,
                    ],
                    start_to_close_timeout=timedelta(minutes=10),
                    heartbeat_timeout=timedelta(seconds=30),
                )

                results.append(batch_result)
                processed += batch_size

                # Checkpoint: workflow can be safely paused/resumed here
                await workflow.sleep(1)

            # Aggregate results
            final_result = await workflow.execute_activity(
                activities.database_operation,
                args=["aggregate_results", {"results": results}],
                start_to_close_timeout=timedelta(seconds=60),
            )

            workflow.logger.info("Analysis completed successfully")
            return WorkflowResult(success=True, data=final_result)

        except Exception as e:
            workflow.logger.error(f"Analysis failed: {e}")
            return WorkflowResult(success=False, data=None, error=str(e))
