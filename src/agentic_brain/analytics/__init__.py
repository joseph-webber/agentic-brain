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

from .export import MetricsExporter
from .insights import ConversationPattern, InsightsEngine, Recommendation
from .metrics import ErrorMetric, MetricsCollector, ResponseMetric
from .usage import DailyUsageStats, UsageTracker, UserStats

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
