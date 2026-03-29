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

"""Temporal.io workflow integration for durable execution."""


# Lazy imports to avoid requiring temporalio for non-temporal use cases
def __getattr__(name: str):
    """Lazy load temporal modules only when accessed."""
    if name == "TemporalClient":
        from .client import TemporalClient

        return TemporalClient
    elif name == "get_temporal_client":
        from .client import get_temporal_client

        return get_temporal_client
    elif name in (
        "RAGWorkflow",
        "AgentWorkflow",
        "CommerceWorkflow",
        "LongRunningAnalysisWorkflow",
    ):
        from .workflows import (
            AgentWorkflow,
            CommerceWorkflow,
            LongRunningAnalysisWorkflow,
            RAGWorkflow,
        )

        return locals()[name]
    elif name in (
        "llm_query",
        "vector_search",
        "database_operation",
        "external_api_call",
        "process_file",
        "send_notification",
    ):
        from .activities import (
            database_operation,
            external_api_call,
            llm_query,
            process_file,
            send_notification,
            vector_search,
        )

        return locals()[name]
    elif name == "TemporalWorker":
        from .worker import TemporalWorker

        return TemporalWorker
    elif name == "start_worker":
        from .worker import start_worker

        return start_worker
    elif name in (
        "SagaPattern",
        "HumanInTheLoopWorkflow",
        "ScheduledWorkflow",
        "ChildWorkflowManager",
    ):
        from .patterns import (
            ChildWorkflowManager,
            HumanInTheLoopWorkflow,
            SagaPattern,
            ScheduledWorkflow,
        )

        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TemporalClient",
    "get_temporal_client",
    "RAGWorkflow",
    "AgentWorkflow",
    "CommerceWorkflow",
    "LongRunningAnalysisWorkflow",
    "llm_query",
    "vector_search",
    "database_operation",
    "external_api_call",
    "process_file",
    "send_notification",
    "TemporalWorker",
    "start_worker",
    "SagaPattern",
    "HumanInTheLoopWorkflow",
    "ScheduledWorkflow",
    "ChildWorkflowManager",
]
