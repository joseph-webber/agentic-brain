# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Analytics and Metrics System for agentic-brain
==============================================

Comprehensive analytics and metrics collection for monitoring chatbot performance,
usage patterns, and generating insights.

Features:
  - Real-time metrics collection (response times, token usage, errors)
  - Neo4j-backed persistent storage
  - Prometheus-compatible metrics export
  - Usage aggregations (daily/weekly/monthly)
  - Cost estimation
  - Conversation pattern analysis
  - Automated insights and recommendations

Example:
    >>> from agentic_brain.analytics import MetricsCollector, UsageTracker
    >>> metrics = MetricsCollector(driver)
    >>> metrics.record_response_time(session_id="s1", duration_ms=250, tokens_in=10, tokens_out=50)
    >>> usage_tracker = UsageTracker(driver)
    >>> stats = usage_tracker.get_daily_stats(date="2024-03-20")
"""

from .metrics import MetricsCollector, ResponseMetric, ErrorMetric
from .usage import UsageTracker, DailyUsageStats, UserStats
from .insights import InsightsEngine, ConversationPattern, Recommendation
from .export import MetricsExporter

__all__ = [
    "MetricsCollector",
    "UsageTracker",
    "InsightsEngine",
    "MetricsExporter",
    "ResponseMetric",
    "ErrorMetric",
    "DailyUsageStats",
    "UserStats",
    "ConversationPattern",
    "Recommendation",
]
