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
Governance Module Tests
=======================

Tests for Model Cards and Audit Trail functionality.
"""

import csv
import json
from datetime import UTC, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from agentic_brain.governance import (
    AuditCategory,
    AuditEvent,
    AuditLog,
    AuditOutcome,
    EthicalConsideration,
    EvaluationMetric,
    ModelCard,
    RiskLevel,
    TrainingDataInfo,
)

# ============================================================================
# Model Card Tests
# ============================================================================


class TestModelCard:
    """Tests for ModelCard class."""

    def test_create_minimal_model_card(self):
        """Test creating a model card with minimal required fields."""
        card = ModelCard(
            model_name="test-model",
            version="1.0.0",
            description="A test model for unit testing",
        )

        assert card.model_name == "test-model"
        assert card.version == "1.0.0"
        assert card.description == "A test model for unit testing"
        assert card.created_at is not None

    def test_create_full_model_card(self):
        """Test creating a model card with all fields."""
        training_data = TrainingDataInfo(
            description="Customer support conversations",
            source="Internal CRM system",
            size="500K conversations",
            date_collected="2024-01-01",
            preprocessing=["Tokenization", "PII removal"],
            known_biases=["English-language bias"],
        )

        metrics = [
            EvaluationMetric(
                name="accuracy",
                value=0.95,
                threshold=0.90,
                dataset="test_set_v1",
            ),
            EvaluationMetric(
                name="f1_score",
                value=0.92,
                threshold=0.85,
            ),
        ]

        ethics = [
            EthicalConsideration(
                category="fairness",
                description="Model may show regional bias in language",
                mitigation="Balanced training data across regions",
                risk_level=RiskLevel.MEDIUM,
            ),
        ]

        card = ModelCard(
            model_name="customer-support-bot",
            version="2.1.0",
            description="AI assistant for customer support",
            owner="AI Team",
            intended_use=["FAQ answering", "Ticket triage"],
            out_of_scope_use=["Medical advice", "Legal advice"],
            model_type="transformer",
            architecture="fine-tuned GPT-4",
            input_format="text/plain",
            output_format="text/plain",
            limitations=["No real-time data", "English only"],
            risks=["Hallucination risk on edge cases"],
            training_data=training_data,
            evaluation_metrics=metrics,
            ethical_considerations=ethics,
            tags=["nlp", "customer-support", "production"],
            references=["https://example.com/paper"],
        )

        assert card.model_name == "customer-support-bot"
        assert card.owner == "AI Team"
        assert len(card.intended_use) == 2
        assert len(card.evaluation_metrics) == 2
        assert len(card.ethical_considerations) == 1
        assert card.training_data.size == "500K conversations"

    def test_model_card_to_markdown(self):
        """Test exporting model card to markdown."""
        card = ModelCard(
            model_name="test-model",
            version="1.0.0",
            description="Test model description",
            owner="Test Owner",
            intended_use=["Use case 1", "Use case 2"],
            limitations=["Limitation 1"],
        )

        markdown = card.to_markdown()

        assert "# Model Card: test-model" in markdown
        assert "**Version:** 1.0.0" in markdown
        assert "**Owner:** Test Owner" in markdown
        assert "## Intended Use" in markdown
        assert "- Use case 1" in markdown
        assert "## Limitations" in markdown
        assert "- Limitation 1" in markdown

    def test_model_card_to_json(self):
        """Test exporting model card to JSON."""
        card = ModelCard(
            model_name="test-model",
            version="1.0.0",
            description="Test description",
        )

        json_str = card.to_json()
        parsed = json.loads(json_str)

        assert parsed["model_name"] == "test-model"
        assert parsed["version"] == "1.0.0"
        assert "created_at" in parsed

    def test_model_card_from_yaml(self):
        """Test creating model card from YAML."""
        yaml_content = """
model_name: yaml-model
version: "1.0.0"
description: Created from YAML
intended_use:
  - Testing YAML parsing
limitations:
  - Test limitation
"""
        try:
            import yaml

            card = ModelCard.from_yaml(yaml_content)

            assert card.model_name == "yaml-model"
            assert card.version == "1.0.0"
            assert len(card.intended_use) == 1
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_model_card_from_yaml_invalid(self):
        """Test that invalid YAML raises ValueError."""
        invalid_yaml = ":::not valid yaml:::"

        try:
            import yaml

            with pytest.raises(ValueError):
                ModelCard.from_yaml(invalid_yaml)
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_model_card_validate_completeness(self):
        """Test completeness validation."""
        # Minimal card
        minimal_card = ModelCard(
            model_name="test",
            version="1.0.0",
            description="Test",
        )

        result = minimal_card.validate_completeness()

        assert result["is_valid"] is True  # Required fields present
        assert len(result["missing_recommended"]) > 0  # Missing recommended fields
        assert result["completeness_percent"] < 100

    def test_model_card_validate_completeness_full(self):
        """Test completeness validation with full card."""
        full_card = ModelCard(
            model_name="test",
            version="1.0.0",
            description="Test",
            owner="Owner",
            intended_use=["Use 1"],
            limitations=["Limit 1"],
            training_data=TrainingDataInfo(description="Data"),
            evaluation_metrics=[EvaluationMetric(name="acc", value=0.9)],
            ethical_considerations=[
                EthicalConsideration(category="fairness", description="Fair")
            ],
        )

        result = full_card.validate_completeness()

        assert result["is_valid"] is True
        assert result["completeness_percent"] == 100.0
        assert len(result["missing_required"]) == 0
        assert len(result["missing_recommended"]) == 0


class TestEvaluationMetric:
    """Tests for EvaluationMetric class."""

    def test_create_metric_minimal(self):
        """Test creating a metric with minimal fields."""
        metric = EvaluationMetric(name="accuracy", value=0.95)

        assert metric.name == "accuracy"
        assert metric.value == 0.95
        assert metric.threshold is None

    def test_create_metric_full(self):
        """Test creating a metric with all fields."""
        metric = EvaluationMetric(
            name="f1_score",
            value=0.92,
            threshold=0.85,
            dataset="validation_set",
            date_measured="2024-03-20",
        )

        assert metric.name == "f1_score"
        assert metric.threshold == 0.85
        assert metric.dataset == "validation_set"


class TestTrainingDataInfo:
    """Tests for TrainingDataInfo class."""

    def test_create_training_data_info(self):
        """Test creating training data info."""
        info = TrainingDataInfo(
            description="Customer conversations",
            source="Internal CRM",
            size="1M records",
            preprocessing=["Tokenization", "Normalization"],
            known_biases=["Regional bias"],
        )

        assert info.description == "Customer conversations"
        assert info.source == "Internal CRM"
        assert len(info.preprocessing) == 2
        assert len(info.known_biases) == 1


class TestEthicalConsideration:
    """Tests for EthicalConsideration class."""

    def test_create_ethical_consideration(self):
        """Test creating an ethical consideration."""
        consideration = EthicalConsideration(
            category="privacy",
            description="Model may memorize PII",
            mitigation="Applied differential privacy",
            risk_level=RiskLevel.HIGH,
        )

        assert consideration.category == "privacy"
        assert consideration.risk_level == RiskLevel.HIGH
        assert "differential privacy" in consideration.mitigation

    def test_risk_level_enum(self):
        """Test RiskLevel enum values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


# ============================================================================
# Audit Trail Tests
# ============================================================================


class TestAuditEvent:
    """Tests for AuditEvent class."""

    def test_create_audit_event(self):
        """Test creating an audit event."""
        event = AuditEvent(
            timestamp=datetime.now(UTC).isoformat(),
            action="query",
            actor="user:123",
            resource="model:gpt-4",
            details={"prompt": "Hello"},
        )

        assert event.action == "query"
        assert event.actor == "user:123"
        assert event.resource == "model:gpt-4"
        assert event.event_id is not None

    def test_audit_event_to_dict(self):
        """Test converting event to dictionary."""
        event = AuditEvent(
            timestamp="2024-03-20T10:00:00Z",
            action="create",
            actor="admin",
            resource="agent:support",
            outcome=AuditOutcome.SUCCESS,
            category=AuditCategory.ADMIN,
        )

        data = event.to_dict()

        assert data["action"] == "create"
        assert data["outcome"] == "success"  # Enum converted to value
        assert data["category"] == "admin"

    def test_audit_event_from_dict(self):
        """Test creating event from dictionary."""
        data = {
            "timestamp": "2024-03-20T10:00:00Z",
            "action": "delete",
            "actor": "user:456",
            "resource": "data:records",
            "outcome": "failure",
            "category": "data_access",
            "event_id": "test-id",
            "details": {"reason": "permission denied"},
        }

        event = AuditEvent.from_dict(data)

        assert event.action == "delete"
        assert event.outcome == AuditOutcome.FAILURE
        assert event.category == AuditCategory.DATA_ACCESS
        assert event.details["reason"] == "permission denied"


class TestAuditLog:
    """Tests for AuditLog class."""

    @pytest.fixture
    def audit_log(self):
        """Create an in-memory audit log for testing."""
        return AuditLog()  # No driver = in-memory storage

    @pytest.fixture
    def mock_driver(self):
        """Create a mock Neo4j driver."""
        driver = Mock()
        session = MagicMock()
        driver.session.return_value = session
        session.__enter__.return_value = session
        session.__exit__.return_value = None
        return driver

    def test_record_event(self, audit_log):
        """Test recording an audit event."""
        event = audit_log.record(
            actor="user:test",
            action="query",
            resource="model:test",
            details={"key": "value"},
        )

        assert event.actor == "user:test"
        assert event.action == "query"
        assert event.resource == "model:test"
        assert event.details == {"key": "value"}
        assert event.outcome == AuditOutcome.SUCCESS

    def test_record_event_with_all_fields(self, audit_log):
        """Test recording an event with all optional fields."""
        event = audit_log.record(
            actor="user:admin",
            action="update",
            resource="config:system",
            details={"setting": "value"},
            outcome=AuditOutcome.SUCCESS,
            category=AuditCategory.CONFIGURATION,
            ip_address="192.168.1.1",
            session_id="sess-123",
            duration_ms=150,
            metadata={"version": "2.0"},
        )

        assert event.ip_address == "192.168.1.1"
        assert event.session_id == "sess-123"
        assert event.duration_ms == 150
        assert event.category == AuditCategory.CONFIGURATION

    def test_query_by_actor(self, audit_log):
        """Test querying events by actor."""
        audit_log.record("user:alice", "read", "doc:1")
        audit_log.record("user:bob", "write", "doc:2")
        audit_log.record("user:alice", "delete", "doc:3")

        events = audit_log.query(actor="user:alice")

        assert len(events) == 2
        assert all(e.actor == "user:alice" for e in events)

    def test_query_by_action(self, audit_log):
        """Test querying events by action."""
        audit_log.record("user:1", "read", "doc:1")
        audit_log.record("user:2", "write", "doc:2")
        audit_log.record("user:3", "read", "doc:3")

        events = audit_log.query(action="read")

        assert len(events) == 2
        assert all(e.action == "read" for e in events)

    def test_query_by_category(self, audit_log):
        """Test querying events by category."""
        audit_log.record(
            "user:1", "login", "auth", category=AuditCategory.AUTHENTICATION
        )
        audit_log.record("user:1", "read", "data", category=AuditCategory.DATA_ACCESS)
        audit_log.record(
            "user:1", "logout", "auth", category=AuditCategory.AUTHENTICATION
        )

        events = audit_log.query(category=AuditCategory.AUTHENTICATION)

        assert len(events) == 2

    def test_query_by_outcome(self, audit_log):
        """Test querying events by outcome."""
        audit_log.record("user:1", "action1", "res1", outcome=AuditOutcome.SUCCESS)
        audit_log.record("user:1", "action2", "res2", outcome=AuditOutcome.FAILURE)
        audit_log.record("user:1", "action3", "res3", outcome=AuditOutcome.SUCCESS)

        events = audit_log.query(outcome=AuditOutcome.FAILURE)

        assert len(events) == 1
        assert events[0].outcome == AuditOutcome.FAILURE

    def test_query_with_limit_and_offset(self, audit_log):
        """Test pagination in queries."""
        for i in range(10):
            audit_log.record(f"user:{i}", "action", "resource")

        page1 = audit_log.query(limit=3, offset=0)
        page2 = audit_log.query(limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        # Events should be different
        page1_ids = {e.event_id for e in page1}
        page2_ids = {e.event_id for e in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_get_event_by_id(self, audit_log):
        """Test retrieving a specific event by ID."""
        event = audit_log.record("user:test", "action", "resource")

        retrieved = audit_log.get_event(event.event_id)

        assert retrieved is not None
        assert retrieved.event_id == event.event_id
        assert retrieved.actor == event.actor

    def test_get_event_not_found(self, audit_log):
        """Test retrieving a non-existent event."""
        result = audit_log.get_event("non-existent-id")
        assert result is None

    def test_count_events(self, audit_log):
        """Test counting events."""
        audit_log.record("user:1", "read", "res")
        audit_log.record("user:1", "write", "res")
        audit_log.record("user:2", "read", "res")

        total = audit_log.count()
        user1_count = audit_log.count(actor="user:1")
        read_count = audit_log.count(action="read")

        assert total == 3
        assert user1_count == 2
        assert read_count == 2

    def test_get_statistics(self, audit_log):
        """Test getting audit statistics."""
        audit_log.record("user:1", "read", "res:1", category=AuditCategory.DATA_ACCESS)
        audit_log.record("user:2", "read", "res:2", category=AuditCategory.DATA_ACCESS)
        audit_log.record(
            "user:1",
            "login",
            "auth",
            category=AuditCategory.AUTHENTICATION,
            outcome=AuditOutcome.SUCCESS,
        )
        audit_log.record(
            "user:3",
            "login",
            "auth",
            category=AuditCategory.AUTHENTICATION,
            outcome=AuditOutcome.FAILURE,
        )

        stats = audit_log.get_statistics(hours=24)

        assert stats["total_events"] == 4
        assert stats["events_by_action"]["read"] == 2
        assert stats["events_by_action"]["login"] == 2
        assert stats["unique_actors"] == 3
        assert stats["events_by_outcome"]["success"] == 3
        assert stats["events_by_outcome"]["failure"] == 1

    def test_export_json(self, audit_log, tmp_path):
        """Test exporting events to JSON."""
        audit_log.record("user:1", "action1", "res1")
        audit_log.record("user:2", "action2", "res2")

        output_file = str(tmp_path / "audit_export.json")
        count = audit_log.export_json(output_file)

        assert count == 2
        assert Path(output_file).exists()

        with open(output_file) as f:
            data = json.load(f)
            assert data["event_count"] == 2
            assert len(data["events"]) == 2
            assert "export_timestamp" in data

    def test_export_csv(self, audit_log, tmp_path):
        """Test exporting events to CSV."""
        audit_log.record("user:1", "read", "doc:1", details={"page": 1})
        audit_log.record("user:2", "write", "doc:2", details={"page": 2})

        output_file = str(tmp_path / "audit_export.csv")
        count = audit_log.export_csv(output_file)

        assert count == 2
        assert Path(output_file).exists()

        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert "actor" in rows[0]
            assert "action" in rows[0]
            assert "resource" in rows[0]

    def test_clear_events(self, audit_log):
        """Test clearing in-memory events."""
        audit_log.record("user:1", "action", "res")
        audit_log.record("user:2", "action", "res")

        count = audit_log.clear()

        assert count == 2
        assert audit_log.count() == 0

    def test_neo4j_persistence(self, mock_driver):
        """Test that events are persisted to Neo4j."""
        audit_log = AuditLog(driver=mock_driver)
        session = mock_driver.session.return_value.__enter__.return_value

        audit_log.record("user:test", "action", "resource")

        # Should have called run to persist
        assert session.run.called


class TestAuditOutcome:
    """Tests for AuditOutcome enum."""

    def test_outcome_values(self):
        """Test all outcome enum values."""
        assert AuditOutcome.SUCCESS.value == "success"
        assert AuditOutcome.FAILURE.value == "failure"
        assert AuditOutcome.PARTIAL.value == "partial"
        assert AuditOutcome.DENIED.value == "denied"
        assert AuditOutcome.PENDING.value == "pending"


class TestAuditCategory:
    """Tests for AuditCategory enum."""

    def test_category_values(self):
        """Test all category enum values."""
        assert AuditCategory.DATA_ACCESS.value == "data_access"
        assert AuditCategory.MODEL_INFERENCE.value == "model_inference"
        assert AuditCategory.CONFIGURATION.value == "configuration"
        assert AuditCategory.AUTHENTICATION.value == "authentication"
        assert AuditCategory.AUTHORIZATION.value == "authorization"
        assert AuditCategory.ADMIN.value == "admin"
        assert AuditCategory.SYSTEM.value == "system"
        assert AuditCategory.COMPLIANCE.value == "compliance"


# ============================================================================
# Integration Tests
# ============================================================================


class TestGovernanceIntegration:
    """Integration tests for the governance module."""

    def test_model_card_with_audit_trail(self, tmp_path):
        """Test creating a model card and auditing the creation."""
        audit_log = AuditLog()

        # Create model card
        card = ModelCard(
            model_name="integration-test-model",
            version="1.0.0",
            description="Model for integration testing",
        )

        # Audit the creation
        event = audit_log.record(
            actor="system:model-registry",
            action="create",
            resource=f"model-card:{card.model_name}",
            details={
                "version": card.version,
                "completeness": card.validate_completeness()["completeness_percent"],
            },
            category=AuditCategory.COMPLIANCE,
        )

        assert event is not None
        assert card.model_name in event.resource

        # Export both
        card_file = tmp_path / "model_card.json"
        audit_file = tmp_path / "audit.json"

        with open(card_file, "w") as f:
            f.write(card.to_json())

        audit_log.export_json(str(audit_file))

        assert card_file.exists()
        assert audit_file.exists()

    def test_full_governance_workflow(self, tmp_path):
        """Test a complete governance workflow."""
        audit = AuditLog()

        # Step 1: Create model card
        card = ModelCard(
            model_name="workflow-model",
            version="2.0.0",
            description="Model demonstrating governance workflow",
            intended_use=["Customer support"],
            limitations=["English only"],
            ethical_considerations=[
                EthicalConsideration(
                    category="fairness",
                    description="Regional language bias",
                    risk_level=RiskLevel.MEDIUM,
                )
            ],
        )

        audit.record("ci:pipeline", "create", f"model-card:{card.model_name}")

        # Step 2: Validate completeness
        validation = card.validate_completeness()
        audit.record(
            actor="ci:validator",
            action="validate",
            resource=f"model-card:{card.model_name}",
            details=validation,
            outcome=(
                AuditOutcome.SUCCESS if validation["is_valid"] else AuditOutcome.FAILURE
            ),
        )

        # Step 3: Export for compliance
        markdown_path = tmp_path / "model_card.md"
        with open(markdown_path, "w") as f:
            f.write(card.to_markdown())

        audit.record("ci:exporter", "export", str(markdown_path))

        # Step 4: Generate audit report
        stats = audit.get_statistics(hours=1)
        audit.export_json(str(tmp_path / "governance_audit.json"))

        # Verify workflow
        assert stats["total_events"] == 3
        assert markdown_path.exists()
        assert (tmp_path / "governance_audit.json").exists()
