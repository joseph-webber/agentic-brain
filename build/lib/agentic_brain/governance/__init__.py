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
AI Governance Module
====================

Comprehensive AI governance tools for compliance, documentation, and auditing.

Features:
  - Model Cards: Standardized AI model documentation (Google format)
  - Audit Trails: Immutable event logging for compliance
  - Compliance Exports: JSON, CSV export for regulatory reporting

Example:
    >>> from agentic_brain.governance import ModelCard, AuditLog, AuditEvent
    >>>
    >>> # Create a model card
    >>> card = ModelCard(
    ...     model_name="customer-bot",
    ...     version="1.0.0",
    ...     description="Customer support AI assistant",
    ...     intended_use=["FAQ answering", "Ticket triage"],
    ...     limitations=["Not for medical advice"],
    ... )
    >>> print(card.to_markdown())
    >>>
    >>> # Record audit events
    >>> audit = AuditLog()
    >>> audit.record("user:123", "query", "model:gpt-4", details={"prompt": "..."})
    >>> events = audit.query(actor="user:123")
    >>> audit.export_json("compliance_report.json")
"""

from .audit import (
    AuditCategory,
    AuditEvent,
    AuditLog,
    AuditOutcome,
)
from .model_card import (
    EthicalConsideration,
    EvaluationMetric,
    ModelCard,
    RiskLevel,
    TrainingDataInfo,
)

__all__ = [
    # Model Cards
    "ModelCard",
    "EvaluationMetric",
    "TrainingDataInfo",
    "EthicalConsideration",
    "RiskLevel",
    # Audit
    "AuditEvent",
    "AuditLog",
    "AuditOutcome",
    "AuditCategory",
]
