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
Tests for agentic-brain bots module.

Tests BotHealth, BotMessage, BotHandoff, and BotMessaging.
"""

from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.bots import (
    BotHandoff,
    BotHealth,
    BotMessage,
    HealthCheckResult,
    HealthStatus,
    RunRecord,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    @pytest.mark.parametrize(
        "status,value",
        [
            (HealthStatus.HEALTHY, "healthy"),
            (HealthStatus.WARNING, "warning"),
            (HealthStatus.ERROR, "error"),
            (HealthStatus.UNKNOWN, "unknown"),
        ],
    )
    def test_health_status_values(self, status, value):
        """Test all health status enum values."""
        assert status.value == value


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_default_timestamp(self):
        """Test that timestamp is set by default."""
        result = HealthCheckResult(service="test", status=True, message="OK")
        assert result.timestamp is not None
        assert result.service == "test"
        assert result.status is True
        assert result.message == "OK"
        assert result.duration_ms == 0.0

    def test_custom_values(self):
        """Test custom values are preserved."""
        ts = datetime.now(UTC)
        result = HealthCheckResult(
            service="neo4j",
            status=False,
            message="Connection failed",
            timestamp=ts,
            duration_ms=150.5,
        )
        assert result.service == "neo4j"
        assert result.status is False
        assert result.message == "Connection failed"
        assert result.timestamp == ts
        assert result.duration_ms == 150.5


class TestRunRecord:
    """Tests for RunRecord dataclass."""

    def test_default_values(self):
        """Test default values."""
        record = RunRecord(status="completed", duration=10.5)
        assert record.status == "completed"
        assert record.duration == 10.5
        assert record.error is None
        assert record.timestamp is not None

    def test_with_error(self):
        """Test record with error."""
        record = RunRecord(status="failed", duration=5.0, error="Connection timeout")
        assert record.status == "failed"
        assert record.error == "Connection timeout"


class TestBotHealth:
    """Tests for BotHealth class."""

    @pytest.fixture
    def health(self):
        """Create a BotHealth instance."""
        return BotHealth("test_bot")

    def test_init(self, health):
        """Test initialization."""
        assert health.bot_id == "test_bot"
        assert health.history == []
        assert health.run_records == []

    @patch("subprocess.run")
    def test_check_neo4j_success(self, mock_run, health):
        """Test Neo4j check succeeds."""
        mock_run.return_value = MagicMock(returncode=0)

        result = health.check_neo4j()
        assert result is True
        assert len(health.history) == 1
        assert health.history[0].service == "neo4j"
        assert health.history[0].status is True

    @patch("subprocess.run")
    def test_check_neo4j_failure(self, mock_run, health):
        """Test Neo4j check fails."""
        mock_run.return_value = MagicMock(returncode=1)

        result = health.check_neo4j()
        assert result is False
        assert len(health.history) == 1
        assert health.history[0].status is False

    @patch("subprocess.run")
    def test_check_ollama_success(self, mock_run, health):
        """Test Ollama check succeeds."""
        mock_run.return_value = MagicMock(returncode=0)

        result = health.check_ollama()
        assert result is True

    @patch("subprocess.run")
    def test_check_copilot_not_found(self, mock_run, health):
        """Test Copilot check when not found."""
        mock_run.side_effect = FileNotFoundError()

        result = health.check_copilot()
        assert result is False
        assert health.history[-1].message == "Not installed"

    def test_record_run(self, health):
        """Test recording a run."""
        health.record_run("completed", 15.5)

        assert len(health.run_records) == 1
        assert health.run_records[0].status == "completed"
        assert health.run_records[0].duration == 15.5

    def test_record_run_with_error(self, health):
        """Test recording a failed run."""
        health.record_run("failed", 5.0, error="Timeout")

        assert health.run_records[0].status == "failed"
        assert health.run_records[0].error == "Timeout"

    def test_get_stats_empty(self, health):
        """Test stats with no runs."""
        stats = health.get_stats()
        assert stats["total_runs"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["last_run"] is None

    def test_get_stats_with_runs(self, health):
        """Test stats with runs."""
        health.record_run("completed", 10.0)
        health.record_run("completed", 15.0)
        health.record_run("failed", 5.0, error="Error")

        stats = health.get_stats()
        assert stats["total_runs"] == 3
        assert stats["successful_runs"] == 2
        assert stats["success_rate"] == pytest.approx(2 / 3)
        assert stats["avg_duration"] == 10.0
        assert stats["last_status"] == "failed"
        assert stats["last_error"] == "Error"

    def test_is_healthy_empty(self, health):
        """Test is_healthy with no checks."""
        assert health.is_healthy() is True

    def test_get_health_status_unknown(self, health):
        """Test health status with no history."""
        assert health.get_health_status() == HealthStatus.UNKNOWN

    def test_get_health_status_healthy(self, health):
        """Test health status when all checks pass."""
        for _ in range(5):
            health._record_check("test", True, 10.0, "OK")

        assert health.get_health_status() == HealthStatus.HEALTHY

    def test_get_health_status_error(self, health):
        """Test health status when most checks fail."""
        for _ in range(5):
            health._record_check("test", False, 10.0, "Failed")

        assert health.get_health_status() == HealthStatus.ERROR

    def test_get_history_limit(self, health):
        """Test history respects limit."""
        for i in range(20):
            health._record_check(f"service_{i}", True, 10.0, "OK")

        history = health.get_history(limit=5)
        assert len(history) == 5

    def test_get_status_report(self, health):
        """Test status report generation."""
        health._record_check("neo4j", True, 10.0, "Connected")
        health.record_run("completed", 15.0)

        report = health.get_status_report()
        assert "test_bot" in report
        assert "neo4j" in report
        assert "Connected" in report


class TestBotMessage:
    """Tests for BotMessage dataclass."""

    def test_default_values(self):
        """Test default values are set."""
        msg = BotMessage()
        assert msg.id is not None
        assert msg.from_bot == ""
        assert msg.to_bot == ""
        assert msg.message == ""
        assert msg.data == {}
        assert msg.timestamp is not None
        assert msg.read is False

    def test_custom_values(self):
        """Test custom values are preserved."""
        msg = BotMessage(
            from_bot="bot_1", to_bot="bot_2", message="Hello", data={"key": "value"}
        )
        assert msg.from_bot == "bot_1"
        assert msg.to_bot == "bot_2"
        assert msg.message == "Hello"
        assert msg.data == {"key": "value"}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        msg = BotMessage(
            from_bot="bot_1", to_bot="bot_2", message="Test", data={"items": [1, 2, 3]}
        )
        d = msg.to_dict()

        assert d["from_bot"] == "bot_1"
        assert d["to_bot"] == "bot_2"
        assert d["message"] == "Test"
        assert isinstance(d["timestamp"], str)
        assert isinstance(d["data"], str)  # JSON serialized

    def test_from_dict(self):
        """Test creation from dictionary."""
        d = {
            "id": "test-id",
            "from_bot": "bot_1",
            "to_bot": "bot_2",
            "message": "Hello",
            "data": '{"key": "value"}',
            "timestamp": "2026-03-01T10:00:00+00:00",
            "read": True,
        }
        msg = BotMessage.from_dict(d)

        assert msg.id == "test-id"
        assert msg.from_bot == "bot_1"
        assert msg.data == {"key": "value"}
        assert msg.read is True

    def test_roundtrip(self):
        """Test to_dict -> from_dict roundtrip."""
        original = BotMessage(
            from_bot="bot_1",
            to_bot="bot_2",
            message="Test",
            data={"nested": {"key": [1, 2, 3]}},
        )

        restored = BotMessage.from_dict(original.to_dict())

        assert restored.from_bot == original.from_bot
        assert restored.to_bot == original.to_bot
        assert restored.message == original.message
        assert restored.data == original.data


class TestBotHandoff:
    """Tests for BotHandoff dataclass."""

    def test_default_values(self):
        """Test default values."""
        handoff = BotHandoff()
        assert handoff.id is not None
        assert handoff.from_bot == ""
        assert handoff.to_bot == ""
        assert handoff.data == {}
        assert handoff.message == ""
        assert handoff.claimed is False
        assert handoff.claimed_by is None

    def test_custom_values(self):
        """Test custom values."""
        handoff = BotHandoff(
            from_bot="bot_1",
            to_bot="bot_2",
            data={"task": "process"},
            message="Please handle this",
        )
        assert handoff.from_bot == "bot_1"
        assert handoff.to_bot == "bot_2"
        assert handoff.data == {"task": "process"}
        assert handoff.message == "Please handle this"
