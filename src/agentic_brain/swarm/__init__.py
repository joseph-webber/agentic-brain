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

"""
Redis-based swarm coordination for multi-agent development.

Quickstart::

    from agentic_brain.swarm import SwarmCoordinator, AgentRegistry, TaskQueue, FindingsAggregator

    coord = SwarmCoordinator.from_url("redis://:BrainRedis2026@localhost:6379/0")
    coord.start_swarm("pr-review-42", total_tasks=10)

    registry = AgentRegistry(coord, "pr-review-42")
    registry.register("agent-1", capabilities=["python", "review"])

    queue = TaskQueue(coord, "pr-review-42")
    queue.enqueue({"action": "review", "file": "main.py"})

    task = queue.claim(agent_id="agent-1", timeout=5)
    queue.complete(task["task_id"], result={"issues": 0})

    agg = FindingsAggregator(coord, "pr-review-42")
    summary = agg.aggregate()
    print(summary.human_summary())
"""

from .agent_registry import AgentProfile, AgentRegistry
from .findings_aggregator import AggregatedSummary, Finding, FindingsAggregator
from .redis_coordinator import (
    REDIS_URL_DEFAULT,
    CoordinationEvent,
    SwarmCoordinator,
    SwarmStatus,
)
from .task_queue import TaskQueue, TaskResult, TaskState

__all__ = [
    # Coordinator
    "SwarmCoordinator",
    "SwarmStatus",
    "CoordinationEvent",
    "REDIS_URL_DEFAULT",
    # Registry
    "AgentRegistry",
    "AgentProfile",
    # Queue
    "TaskQueue",
    "TaskState",
    "TaskResult",
    # Aggregator
    "FindingsAggregator",
    "AggregatedSummary",
    "Finding",
]
