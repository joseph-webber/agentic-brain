# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Workflow Module
===============

Durable workflow execution with state persistence and recovery.

Exports:
    Neo4j Workflow State:
    - WorkflowState: Durable workflow state manager
    - WorkflowConfig: Workflow configuration
    - WorkflowStatus: Workflow execution status enum
    - StepStatus: Step execution status enum
    - StepState: Individual step state

    Temporal Workflows:
    - See workflows.temporal for Temporal.io integration
"""

from .neo4j_state import (
    StepState,
    StepStatus,
    WorkflowConfig,
    WorkflowState,
    WorkflowStatus,
)

__all__ = [
    # Neo4j workflow state
    "WorkflowState",
    "WorkflowConfig",
    "WorkflowStatus",
    "StepStatus",
    "StepState",
]
