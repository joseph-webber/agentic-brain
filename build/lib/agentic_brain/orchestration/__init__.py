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

"""
Multi-agent orchestration system for agentic-brain.

Simple, powerful orchestration of multiple agents with different execution strategies.
"""

from __future__ import annotations

from .crew import AgentRole, Crew, CrewConfig, ExecutionStrategy
from .workflow import Workflow, WorkflowResult, WorkflowState, WorkflowStep

__all__ = [
    "Crew",
    "CrewConfig",
    "ExecutionStrategy",
    "AgentRole",
    "Workflow",
    "WorkflowStep",
    "WorkflowState",
    "WorkflowResult",
]
