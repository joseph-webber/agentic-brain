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

"""CLI commands for Temporal workflow management."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Optional

# Lazy imports - only fail when actually using temporal commands
TEMPORAL_AVAILABLE = False
try:
    from agentic_brain.workflows.temporal import (
        TemporalClient,
        TemporalConfig,
        start_worker,
    )
    from agentic_brain.workflows.temporal.workflows import (
        AgentWorkflow,
        CommerceWorkflow,
        LongRunningAnalysisWorkflow,
        RAGWorkflow,
    )

    TEMPORAL_AVAILABLE = True
except ImportError:
    TemporalClient = None  # type: ignore
    TemporalConfig = None  # type: ignore
    start_worker = None  # type: ignore
    AgentWorkflow = None  # type: ignore
    CommerceWorkflow = None  # type: ignore
    LongRunningAnalysisWorkflow = None  # type: ignore
    RAGWorkflow = None  # type: ignore


def _check_temporal() -> None:
    """Check if temporal is available."""
    if not TEMPORAL_AVAILABLE:
        raise ImportError(
            "temporalio is not installed. Install with: pip install temporalio"
        )


def temporal_worker_command(args: argparse.Namespace) -> int:
    """Start a Temporal worker.

    The worker polls for workflow and activity tasks from the specified
    task queue and executes them.
    """
    _check_temporal()
    config = TemporalConfig(host=args.host, namespace=args.namespace)

    print(f"Starting Temporal worker on {args.host}")
    print(f"Namespace: {args.namespace}")
    print(f"Task queue: {args.task_queue}")

    try:
        asyncio.run(start_worker(task_queue=args.task_queue, config=config))
        return 0
    except KeyboardInterrupt:
        print("\nWorker stopped")
        return 0


def temporal_list_command(args: argparse.Namespace) -> int:
    """List workflow executions."""
    _check_temporal()

    async def _list() -> None:
        config = TemporalConfig(host=args.host, namespace=args.namespace)
        client = TemporalClient(config)

        try:
            workflows = await client.list_workflows(
                query=args.query,
                max_results=args.limit,
            )

            if not workflows:
                print("No workflows found")
                return

            print(f"Found {len(workflows)} workflow(s):\n")

            for wf in workflows:
                print(f"ID: {wf['id']}")
                print(f"  Type: {wf['type']}")
                print(f"  Status: {wf['status']}")
                print(f"  Started: {wf['start_time']}")
                print()

        finally:
            await client.close()

    asyncio.run(_list())
    return 0


def temporal_run_command(args: argparse.Namespace) -> int:
    """Execute a workflow."""
    workflow_map = {
        "rag": RAGWorkflow,
        "agent": AgentWorkflow,
        "commerce": CommerceWorkflow,
        "analysis": LongRunningAnalysisWorkflow,
    }

    if args.workflow_type not in workflow_map:
        print(f"Invalid workflow type. Choose from: {', '.join(workflow_map.keys())}")
        return 1

    workflow_class = workflow_map[args.workflow_type]

    # Parse arguments
    workflow_args = []
    if args.args:
        try:
            parsed_args = json.loads(args.args)
            if isinstance(parsed_args, dict):
                # Convert dict to positional args based on workflow
                if args.workflow_type == "rag":
                    workflow_args = [
                        parsed_args.get("query", ""),
                        parsed_args.get("collection", "default"),
                        parsed_args.get("top_k", 5),
                        parsed_args.get("model", "gpt-4"),
                    ]
                # Add other workflow arg mappings as needed
        except json.JSONDecodeError:
            print(f"Invalid JSON in --args: {args.args}")
            return 1

    async def _run() -> None:
        config = TemporalConfig(host=args.host, namespace=args.namespace)
        client = TemporalClient(config)

        try:
            print(f"Starting workflow: {args.workflow_type}")
            print(f"Workflow ID: {args.workflow_id}")

            handle = await client.start_workflow(
                workflow_class,
                workflow_id=args.workflow_id,
                task_queue=args.task_queue,
                args=workflow_args,
            )

            print("Workflow started. Waiting for result...")

            result = await handle.result()

            print("\nWorkflow completed!")
            print(json.dumps(result, indent=2, default=str))

        except Exception as e:
            print(f"Error: {e}")
            raise
        finally:
            await client.close()

    asyncio.run(_run())
    return 0


def temporal_status_command(args: argparse.Namespace) -> int:
    """Check workflow execution status."""

    async def _status() -> None:
        config = TemporalConfig(host=args.host, namespace=args.namespace)
        client = TemporalClient(config)

        try:
            handle = await client.get_workflow_handle(args.workflow_id)

            # Get workflow description
            desc = await handle.describe()

            print(f"Workflow ID: {args.workflow_id}")
            print(f"Type: {desc.workflow_type}")
            print(f"Status: {desc.status}")
            print(f"Started: {desc.start_time}")

            if desc.close_time:
                print(f"Closed: {desc.close_time}")

            # Try to get result if completed
            if desc.status.name == "COMPLETED":
                try:
                    result = await handle.result()
                    print("\nResult:")
                    print(json.dumps(result, indent=2, default=str))
                except Exception as e:
                    print(f"\nCould not fetch result: {e}")

        except Exception as e:
            print(f"Error: {e}")
            raise
        finally:
            await client.close()

    asyncio.run(_status())
    return 0


def register_temporal_commands(subparsers) -> None:
    """Register Temporal commands with the CLI parser.

    Args:
        subparsers: Argparse subparsers object.
    """
    # Temporal worker command
    temporal_worker = subparsers.add_parser(
        "temporal-worker",
        help="Start a Temporal worker",
        description="Start a worker that polls for workflow and activity tasks",
    )
    temporal_worker.add_argument(
        "--host",
        default="localhost:7233",
        help="Temporal server host (default: localhost:7233)",
    )
    temporal_worker.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace (default: default)",
    )
    temporal_worker.add_argument(
        "--task-queue",
        default="agentic-brain",
        help="Task queue to poll (default: agentic-brain)",
    )
    temporal_worker.set_defaults(func=temporal_worker_command)

    # Temporal workflow list command
    temporal_list = subparsers.add_parser(
        "temporal-list",
        help="List workflow executions",
        description="List workflow executions in Temporal",
    )
    temporal_list.add_argument(
        "--host",
        default="localhost:7233",
        help="Temporal server host (default: localhost:7233)",
    )
    temporal_list.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace (default: default)",
    )
    temporal_list.add_argument(
        "--query",
        help="Filter query (e.g., 'WorkflowType=\"RAGWorkflow\"')",
    )
    temporal_list.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum workflows to list (default: 20)",
    )
    temporal_list.set_defaults(func=temporal_list_command)

    # Temporal workflow run command
    temporal_run = subparsers.add_parser(
        "temporal-run",
        help="Execute a workflow",
        description="Start and execute a Temporal workflow",
    )
    temporal_run.add_argument(
        "workflow_type",
        choices=["rag", "agent", "commerce", "analysis"],
        help="Workflow type to execute",
    )
    temporal_run.add_argument(
        "workflow_id",
        help="Unique ID for this workflow execution",
    )
    temporal_run.add_argument(
        "--host",
        default="localhost:7233",
        help="Temporal server host (default: localhost:7233)",
    )
    temporal_run.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace (default: default)",
    )
    temporal_run.add_argument(
        "--task-queue",
        default="agentic-brain",
        help="Task queue to execute on (default: agentic-brain)",
    )
    temporal_run.add_argument(
        "--args",
        help='Workflow arguments as JSON (e.g., \'{"query": "What is RAG?"}\')',
    )
    temporal_run.set_defaults(func=temporal_run_command)

    # Temporal workflow status command
    temporal_status = subparsers.add_parser(
        "temporal-status",
        help="Check workflow execution status",
        description="Get the status and result of a workflow execution",
    )
    temporal_status.add_argument(
        "workflow_id",
        help="Workflow execution ID to check",
    )
    temporal_status.add_argument(
        "--host",
        default="localhost:7233",
        help="Temporal server host (default: localhost:7233)",
    )
    temporal_status.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace (default: default)",
    )
    temporal_status.set_defaults(func=temporal_status_command)
