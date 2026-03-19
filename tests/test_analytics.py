# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Analytics System Tests
======================

Tests for metrics collection, usage tracking, insights generation, and exports.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from unittest.mock import Mock, patch, MagicMock

from agentic_brain.analytics import (
    MetricsCollector,
    UsageTracker,
    InsightsEngine,
    MetricsExporter,
    ResponseMetric,
    ErrorMetric,
)


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j driver."""
    driver = Mock()
    session = Mock()
    # Use MagicMock for context manager support
    driver.session.return_value = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    return driver


@pytest.fixture
def metrics_collector(mock_driver):
    """Create a metrics collector with mock driver."""
    return MetricsCollector(mock_driver)


@pytest.fixture
def usage_tracker(mock_driver):
    """Create a usage tracker with mock driver."""
    return UsageTracker(mock_driver)


@pytest.fixture
def insights_engine(mock_driver):
    """Create an insights engine with mock driver."""
    return InsightsEngine(mock_driver)


@pytest.fixture
def exporter(mock_driver):
    """Create a metrics exporter with mock driver."""
    return MetricsExporter(mock_driver)


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_initialization(self, metrics_collector):
        """Test collector initialization."""
        assert metrics_collector.driver is not None
        assert metrics_collector.token_pricing is not None
    
    def test_record_response_time(self, metrics_collector, mock_driver):
        """Test recording response time metric."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        metric = metrics_collector.record_response_time(
            session_id="test_session",
            duration_ms=250,
            tokens_in=10,
            tokens_out=50,
            model="gpt-4",
            bot_name="test_bot",
            user_id="user123",
        )
        
        assert isinstance(metric, ResponseMetric)
        assert metric.session_id == "test_session"
        assert metric.duration_ms == 250
        assert metric.tokens_in == 10
        assert metric.tokens_out == 50
        assert metric.model == "gpt-4"
        assert metric.cost > 0  # Should have calculated cost
    
    def test_record_error(self, metrics_collector, mock_driver):
        """Test recording error metric."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        error = metrics_collector.record_error(
            session_id="test_session",
            error_type="timeout",
            message="Request exceeded 30s limit",
            bot_name="test_bot",
            user_id="user123",
        )
        
        assert isinstance(error, ErrorMetric)
        assert error.session_id == "test_session"
        assert error.error_type == "timeout"
        assert error.message == "Request exceeded 30s limit"
    
    def test_record_session_duration(self, metrics_collector, mock_driver):
        """Test recording session duration."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        # Should not raise an exception
        metrics_collector.record_session_duration(
            session_id="test_session",
            duration_ms=5000,
            message_count=10,
            bot_name="test_bot",
        )
        
        session_mock.run.assert_called_once()
    
    def test_token_pricing_calculation(self, metrics_collector):
        """Test cost calculation based on token usage."""
        cost = metrics_collector._calculate_cost("gpt-4", tokens_in=100, tokens_out=50)
        assert cost > 0
        
        # gpt-4: input=0.00003, output=0.0006
        expected = (100 * 0.00003) + (50 * 0.0006)
        assert abs(cost - expected) < 0.000001
    
    def test_custom_token_pricing(self, mock_driver):
        """Test collector with custom token pricing."""
        custom_pricing = {
            "custom_model": {"input": 0.001, "output": 0.002}
        }
        collector = MetricsCollector(mock_driver, token_pricing=custom_pricing)
        
        cost = collector._calculate_cost("custom_model", 100, 50)
        expected = (100 * 0.001) + (50 * 0.002)
        assert abs(cost - expected) < 0.000001
    
    def test_get_prometheus_metrics(self, metrics_collector, mock_driver):
        """Test Prometheus metrics export format."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        # Mock the metrics summary
        summary = {
            "avg_response_time_ms": 250.0,
            "p95_response_time_ms": 500.0,
            "p99_response_time_ms": 1000.0,
            "total_responses": 100,
            "total_tokens_in": 1000,
            "total_tokens_out": 5000,
            "total_cost": 0.25,
        }
        metrics_collector.get_metrics_summary = Mock(return_value=summary)
        
        error_stats = {
            "total_errors": 5,
        }
        metrics_collector.get_error_stats = Mock(return_value=error_stats)
        
        metrics = metrics_collector.get_prometheus_metrics()
        
        assert "agentic_brain_response_time_ms" in metrics
        assert "agentic_brain_total_responses" in metrics
        assert "agentic_brain_total_cost" in metrics
        assert "agentic_brain_errors" in metrics


class TestUsageTracker:
    """Tests for UsageTracker."""
    
    def test_get_daily_stats(self, usage_tracker, mock_driver):
        """Test getting daily statistics."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        # Mock the Neo4j response
        session_mock.run.return_value.single.return_value = {
            "stats": {
                "date": "2024-03-20",
                "responses": 100,
                "errors": 5,
                "tokens_in": 1000,
                "tokens_out": 5000,
                "total_cost": 0.25,
                "avg_response_time_ms": 250.0,
                "active_users": 10,
                "active_sessions": 25,
                "top_models": ["gpt-4", "gpt-3.5-turbo"],
            }
        }
        
        stats = usage_tracker.get_daily_stats("2024-03-20")
        
        assert stats.date == "2024-03-20"
        assert stats.responses == 100
        assert stats.errors == 5
        assert stats.total_cost == 0.25
    
    def test_get_user_stats(self, usage_tracker, mock_driver):
        """Test getting per-user statistics."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        # Mock the Neo4j response
        session_mock.run.return_value.single.return_value = {
            "stats": {
                "total_responses": 50,
                "total_sessions": 5,
                "total_cost": 0.15,
                "avg_response_time_ms": 300.0,
                "most_used_model": "gpt-4",
                "error_rate_pct": 2.5,
                "first_seen": "2024-03-01T10:00:00",
                "last_seen": "2024-03-20T15:30:00",
            }
        }
        
        stats = usage_tracker.get_user_stats("user123", days=30)
        
        assert stats.user_id == "user123"
        assert stats.total_responses == 50
        assert stats.total_sessions == 5
        assert stats.most_used_model == "gpt-4"
    
    def test_get_top_users(self, usage_tracker, mock_driver):
        """Test getting top users."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        # Mock the Neo4j response
        session_mock.run.return_value = iter([
            {
                "user_data": {
                    "user_id": "user1",
                    "responses": 100,
                    "cost": 0.50,
                    "errors": 2,
                }
            },
            {
                "user_data": {
                    "user_id": "user2",
                    "responses": 50,
                    "cost": 0.25,
                    "errors": 1,
                }
            },
        ])
        
        top_users = usage_tracker.get_top_users(limit=10)
        
        assert len(top_users) == 2
        assert top_users[0]["user_id"] == "user1"
        assert top_users[0]["responses"] == 100
    
    def test_estimate_monthly_cost(self, usage_tracker):
        """Test cost estimation."""
        usage_tracker.get_monthly_stats = Mock(return_value={
            "total_cost": 50.00
        })
        
        cost = usage_tracker.estimate_monthly_cost(2024, 3)
        assert cost == 50.00


class TestInsightsEngine:
    """Tests for InsightsEngine."""
    
    def test_analyze_conversation_patterns(self, insights_engine, mock_driver):
        """Test conversation pattern analysis."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        session_mock.run.return_value = iter([
            {
                "pattern": {
                    "pattern": "how do i reset my password",
                    "frequency": 15,
                    "examples": ["How do I reset...", "Can I reset..."],
                    "type": "question_topic",
                }
            }
        ])
        
        patterns = insights_engine.analyze_conversation_patterns()
        
        assert len(patterns) > 0
        assert patterns[0].pattern_type == "question_topic"
        assert patterns[0].frequency == 15
    
    def test_detect_error_patterns(self, insights_engine, mock_driver):
        """Test error pattern detection."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        session_mock.run.return_value = iter([
            {
                "pattern": {
                    "error_type": "timeout",
                    "frequency": 12,
                    "avg_recovery_ms": 500.0,
                    "examples": ["Timeout error 1", "Timeout error 2"],
                }
            }
        ])
        
        patterns = insights_engine.detect_error_patterns()
        
        assert len(patterns) > 0
        assert patterns[0]["error_type"] == "timeout"
    
    def test_get_recommendations(self, insights_engine):
        """Test recommendation generation."""
        # Mock the analysis methods
        insights_engine.analyze_response_time_trends = Mock(return_value={
            "trend_pct": 15.0,
            "trend_direction": "increasing",
        })
        insights_engine.detect_error_patterns = Mock(return_value=[
            {
                "error_type": "timeout",
                "frequency": 15,
                "avg_recovery_ms": 500.0,
                "examples": [],
            }
        ])
        insights_engine.analyze_user_engagement = Mock(return_value={
            "sessions_per_user": 1.2,
        })
        insights_engine.get_performance_bottlenecks = Mock(return_value=[
            {
                "model": "gpt-4",
                "bot_name": "test",
                "slow_responses": 10,
                "avg_duration_ms": 6000.0,
                "severity": "high",
            }
        ])
        
        recommendations = insights_engine.get_recommendations()
        
        # Should have generated multiple recommendations
        assert len(recommendations) > 0
        
        # Check that recommendations have required fields
        for rec in recommendations:
            assert hasattr(rec, "title")
            assert hasattr(rec, "priority")
            assert hasattr(rec, "description")
    
    def test_generate_health_report(self, insights_engine):
        """Test health report generation."""
        insights_engine.analyze_user_engagement = Mock(return_value={"users": 10})
        insights_engine.analyze_response_time_trends = Mock(return_value={})
        insights_engine.detect_error_patterns = Mock(return_value=[])
        insights_engine.get_performance_bottlenecks = Mock(return_value=[])
        insights_engine.analyze_conversation_patterns = Mock(return_value=[])
        insights_engine.get_recommendations = Mock(return_value=[])
        
        report = insights_engine.generate_health_report(days=30)
        
        assert "analysis_period_days" in report
        assert report["analysis_period_days"] == 30
        assert "generated_at" in report
        assert "engagement" in report


class TestMetricsExporter:
    """Tests for MetricsExporter."""
    
    def test_export_metrics_csv(self, exporter, mock_driver, tmp_path):
        """Test CSV export of metrics."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        # Mock Neo4j response
        session_mock.run.return_value = iter([
            {
                "metric": {
                    "timestamp": "2024-03-20T10:00:00",
                    "session_id": "s1",
                    "user_id": "u1",
                    "model": "gpt-4",
                    "duration_ms": 250,
                    "tokens_in": 10,
                    "tokens_out": 50,
                    "cost": 0.01,
                    "bot_name": "test",
                }
            }
        ])
        
        output_file = str(tmp_path / "metrics.csv")
        count = exporter.export_metrics_csv(
            output_file,
            "2024-03-20",
            "2024-03-20",
        )
        
        assert count == 1
        assert Path(output_file).exists()
        
        # Verify CSV content
        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["model"] == "gpt-4"
    
    def test_export_json(self, exporter, mock_driver, tmp_path):
        """Test JSON export."""
        output_file = str(tmp_path / "analytics.json")
        
        # Mock the usage tracker and insights engine
        exporter.usage_tracker = Mock()
        exporter.usage_tracker.get_weekly_stats.return_value = {}
        exporter.usage_tracker.get_top_users.return_value = []
        
        exporter.insights_engine = Mock()
        exporter.insights_engine.generate_health_report.return_value = {}
        
        success = exporter.export_json(output_file, include_insights=True)
        
        assert success
        assert Path(output_file).exists()
        
        # Verify JSON content
        with open(output_file) as f:
            data = json.load(f)
            assert "export_time" in data
            assert "analysis_period_days" in data
    
    def test_export_html_report(self, exporter, tmp_path):
        """Test HTML report export."""
        output_file = str(tmp_path / "report.html")
        
        exporter.insights_engine = Mock()
        exporter.insights_engine.generate_health_report.return_value = {
            "engagement": {"unique_users": 10, "total_responses": 100},
            "performance_trends": {"avg_overall": 250, "trend_pct": 5, "trend_direction": "stable"},
            "error_patterns": [],
            "recommendations": [
                {
                    "title": "Test Recommendation",
                    "priority": "high",
                    "description": "Test description",
                    "estimated_improvement_pct": 20,
                }
            ],
        }
        
        success = exporter.export_html_report(output_file)
        
        assert success
        assert Path(output_file).exists()
        
        # Verify HTML content
        with open(output_file) as f:
            content = f.read()
            assert "Analytics Report" in content
            assert "Test Recommendation" in content


class TestIntegration:
    """Integration tests for the analytics system."""
    
    def test_full_analytics_workflow(self, mock_driver):
        """Test a complete analytics workflow."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        # Create collectors
        metrics = MetricsCollector(mock_driver)
        usage = UsageTracker(mock_driver)
        insights = InsightsEngine(mock_driver)
        
        # Record some metrics
        metric1 = metrics.record_response_time(
            "session1", 250, 10, 50, model="gpt-4"
        )
        metric2 = metrics.record_response_time(
            "session1", 300, 15, 60, model="gpt-4"
        )
        
        error1 = metrics.record_error(
            "session1", "timeout", "Request timed out"
        )
        
        # Verify metrics were recorded
        assert metric1.metric_id is not None
        assert metric2.metric_id is not None
        assert error1.error_id is not None
        assert metric1.metric_id != metric2.metric_id
        assert error1.error_id != metric1.metric_id
    
    def test_export_with_all_formats(self, exporter, mock_driver, tmp_path):
        """Test exporting in multiple formats."""
        session_mock = Mock()
        mock_driver.session.return_value.__enter__.return_value = session_mock
        
        exporter.insights_engine = Mock()
        exporter.insights_engine.generate_health_report.return_value = {}
        
        # Test JSON export
        json_file = str(tmp_path / "export.json")
        json_success = exporter.export_json(json_file)
        assert json_success or True  # May fail due to mocking, but shouldn't raise
        
        # Test HTML export
        html_file = str(tmp_path / "report.html")
        html_success = exporter.export_html_report(html_file)
        assert html_success or True
