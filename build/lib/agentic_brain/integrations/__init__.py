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
External integrations for agentic-brain.

This module provides integrations with external platforms:
- Retool: Low-code internal tools and AI agents
- Temporal: Durable workflow orchestration

Example:
    from agentic_brain.integrations import RetoolClient, TemporalOrchestrator

    # Retool integration
    retool = RetoolClient(api_key="your-key")
    await retool.trigger_workflow("process-refund", {"order_id": "123"})

    # Temporal workflows
    temporal = TemporalOrchestrator()
    await temporal.start_workflow("chat-session", session_id="abc")
"""

from __future__ import annotations

from .retool import RetoolClient, RetoolWorkflow
from .temporal import (
    ActivityOptions,
    AIAgentWorkflowMixin,
    RetryPolicy,
    TemporalOrchestrator,
    WorkflowExecution,
    WorkflowOptions,
    WorkflowStatus,
    activity,
    query,
    run,
    signal,
    workflow,
)

__all__ = [
    # Retool
    "RetoolClient",
    "RetoolWorkflow",
    # Temporal - Orchestrator
    "TemporalOrchestrator",
    "WorkflowStatus",
    "WorkflowExecution",
    "WorkflowOptions",
    "ActivityOptions",
    "RetryPolicy",
    # Temporal - Decorators
    "workflow",
    "run",
    "signal",
    "query",
    "activity",
    # Temporal - Mixins
    "AIAgentWorkflowMixin",
]
