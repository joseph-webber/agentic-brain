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
Temporal.io Compatibility Layer for Agentic Brain.

This package provides a DROP-IN REPLACEMENT for the temporalio Python SDK.
Users migrating from Temporal.io can simply change their imports:

BEFORE (Temporal):
    from temporalio import workflow, activity
    from temporalio.client import Client
    from temporalio.worker import Worker
    from temporalio.testing import WorkflowEnvironment

AFTER (Agentic Brain):
    from agentic_brain.temporal import workflow, activity
    from agentic_brain.temporal.client import Client
    from agentic_brain.temporal.worker import Worker
    from agentic_brain.temporal.testing import WorkflowEnvironment

ALL existing workflow and activity code works unchanged!

Benefits of migrating:
- No separate Temporal server required
- No Cassandra/PostgreSQL dependencies
- Single `pip install agentic-brain`
- Native AI/LLM integration
- 100x faster setup
- SQLite-backed event store (zero config)
- Works offline

See docs/TEMPORAL_MIGRATION_GUIDE.md for step-by-step instructions.
"""

from . import activity, testing, workflow
from .client import Client
from .testing import ActivityEnvironment, WorkflowEnvironment
from .worker import Worker

__all__ = [
    # Modules (import as namespace)
    "workflow",
    "activity",
    "testing",
    # Classes
    "Client",
    "Worker",
    "WorkflowEnvironment",
    "ActivityEnvironment",
]
