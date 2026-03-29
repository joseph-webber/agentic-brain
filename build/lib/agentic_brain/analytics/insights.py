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
Analytics Insights Engine
==========================

Analyzes usage patterns and generates actionable insights:
- Common questions and topics
- Conversation patterns
- Bottlenecks and recommendations
- Trend analysis

Example:
    >>> engine = InsightsEngine(driver)
    >>> patterns = engine.analyze_conversation_patterns()
    >>> recommendations = engine.get_recommendations()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class ConversationPattern:
    """A detected conversation pattern."""

    pattern_id: str
    pattern_type: str  # question_topic, user_behavior, error_pattern
    description: str
    frequency: int
    examples: list[str]
    impact: str  # high, medium, low


@dataclass
class Recommendation:
    """An actionable recommendation."""

    recommendation_id: str
    title: str
    description: str
    priority: str  # high, medium, low
    impact_area: str
    estimated_improvement_pct: float
    implementation_effort: str  # easy, medium, hard


class InsightsEngine:
    """
    Generates analytics insights and recommendations.

    Analyzes conversation patterns, common issues, and provides
    actionable recommendations for improvement.
    """

    def __init__(self, driver):
        """
        Initialize insights engine.

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    def analyze_conversation_patterns(
        self,
        days: int = 30,
        min_frequency: int = 3,
    ) -> list[ConversationPattern]:
        """
        Analyze conversation patterns.

        Args:
            days: Number of days to analyze
            min_frequency: Minimum pattern frequency to report

        Returns:
            List of detected patterns
        """
        query = """
        MATCH (s:Session)-[:HAS_MESSAGE]->(msg:Message)
        WHERE datetime(msg.timestamp) > datetime.now() - duration({days: $days})

        WITH toLower(substring(msg.content, 0, 50)) as msg_prefix,
             count(*) as frequency,
             collect(msg.content)[0..3] as examples
        WHERE frequency >= $min_frequency

        RETURN {
            pattern: msg_prefix,
            frequency: frequency,
            examples: examples,
            type: 'question_topic'
        } as pattern
        ORDER BY frequency DESC
        LIMIT 20
        """

        patterns = []

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    {
                        "days": days,
                        "min_frequency": min_frequency,
                    },
                )

                for i, record in enumerate(result):
                    data = record["pattern"]
                    patterns.append(
                        ConversationPattern(
                            pattern_id=f"pattern_{i}",
                            pattern_type=data["type"],
                            description=data["pattern"],
                            frequency=data["frequency"],
                            examples=data["examples"][:3],
                            impact="high" if data["frequency"] > 10 else "medium",
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to analyze patterns: {e}")

        return patterns

    def detect_error_patterns(
        self,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Detect recurring error patterns.

        Args:
            days: Number of days to analyze

        Returns:
            List of error patterns with details
        """
        query = """
        MATCH (e:ErrorMetric)
        WHERE datetime(e.timestamp) > datetime.now() - duration({days: $days})

        WITH e.error_type as error_type,
             count(*) as frequency,
             avg(coalesce(e.recovery_time_ms, 0)) as avg_recovery_ms,
             collect(e.message)[0..3] as example_messages

        RETURN {
            error_type: error_type,
            frequency: frequency,
            avg_recovery_ms: avg_recovery_ms,
            examples: example_messages
        } as pattern
        ORDER BY frequency DESC
        LIMIT 10
        """

        patterns = []

        try:
            with self.driver.session() as session:
                result = session.run(query, {"days": days})

                for record in result:
                    data = record["pattern"]
                    patterns.append(
                        {
                            "error_type": data["error_type"],
                            "frequency": data["frequency"],
                            "avg_recovery_ms": data["avg_recovery_ms"],
                            "examples": data["examples"],
                            "severity": "high" if data["frequency"] > 10 else "medium",
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to detect error patterns: {e}")

        return patterns

    def analyze_response_time_trends(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Analyze response time trends over time.

        Args:
            days: Number of days to analyze

        Returns:
            Trend analysis results
        """
        query = """
        MATCH (m:ResponseMetric)
        WHERE datetime(m.timestamp) > datetime.now() - duration({days: $days})

        WITH
            date(m.timestamp) as day,
            avg(m.duration_ms) as daily_avg,
            percentileCont(m.duration_ms, 0.95) as daily_p95

        RETURN {
            day: day.toString(),
            avg_response_ms: daily_avg,
            p95_response_ms: daily_p95
        } as daily_stats
        ORDER BY day
        """

        data_points = []

        try:
            with self.driver.session() as session:
                result = session.run(query, {"days": days})

                for record in result:
                    data_points.append(record["daily_stats"])
        except Exception as e:
            logger.error(f"Failed to analyze trends: {e}")

        # Calculate trend
        if len(data_points) >= 2:
            recent_avg = data_points[-1]["avg_response_ms"]
            older_avg = data_points[0]["avg_response_ms"]
            trend = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            trend_direction = "increasing" if trend > 0 else "decreasing"
        else:
            trend = 0
            trend_direction = "stable"

        return {
            "data_points": data_points,
            "trend_pct": trend,
            "trend_direction": trend_direction,
            "avg_overall": (
                sum(d["avg_response_ms"] for d in data_points) / len(data_points)
                if data_points
                else 0
            ),
        }

    def analyze_user_engagement(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Analyze user engagement patterns.

        Args:
            days: Number of days to analyze

        Returns:
            Engagement metrics
        """
        query = """
        OPTIONAL MATCH (m:ResponseMetric)
        WHERE datetime(m.timestamp) > datetime.now() - duration({days: $days})

        OPTIONAL MATCH (s:Session)
        WHERE datetime(s.created_at) > datetime.now() - duration({days: $days})

        WITH
            count(distinct m.user_id) as unique_users,
            count(distinct m.session_id) as total_sessions,
            count(m) as total_responses,
            count(distinct date(m.timestamp)) as active_days

        RETURN {
            unique_users: unique_users,
            total_sessions: total_sessions,
            total_responses: total_responses,
            avg_responses_per_user:
                case when unique_users > 0
                then total_responses / unique_users
                else 0
                end,
            active_days: active_days,
            sessions_per_user:
                case when unique_users > 0
                then total_sessions / unique_users
                else 0
                end
        } as engagement
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, {"days": days})
                record = result.single()
                if record:
                    return record["engagement"]
        except Exception as e:
            logger.error(f"Failed to analyze engagement: {e}")

        return {}

    def get_performance_bottlenecks(
        self,
        threshold_ms: int = 5000,
        min_occurrences: int = 5,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Identify performance bottlenecks.

        Args:
            threshold_ms: Response time threshold (above = slow)
            min_occurrences: Minimum occurrences to report
            days: Number of days to analyze

        Returns:
            List of bottleneck areas
        """
        query = """
        MATCH (m:ResponseMetric)
        WHERE datetime(m.timestamp) > datetime.now() - duration({days: $days})
        AND m.duration_ms > $threshold_ms

        WITH m.model as model,
             m.bot_name as bot_name,
             count(*) as slow_count,
             avg(m.duration_ms) as avg_duration
        WHERE slow_count >= $min_occurrences

        RETURN {
            model: model,
            bot_name: bot_name,
            slow_responses: slow_count,
            avg_duration_ms: avg_duration,
            severity: case
                when avg_duration > 10000 then 'critical'
                when avg_duration > 5000 then 'high'
                else 'medium'
            end
        } as bottleneck
        ORDER BY slow_responses DESC
        """

        bottlenecks = []

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    {
                        "threshold_ms": threshold_ms,
                        "min_occurrences": min_occurrences,
                        "days": days,
                    },
                )

                for record in result:
                    bottlenecks.append(record["bottleneck"])
        except Exception as e:
            logger.error(f"Failed to identify bottlenecks: {e}")

        return bottlenecks

    def get_recommendations(
        self,
        days: int = 30,
    ) -> list[Recommendation]:
        """
        Generate recommendations based on analyzed data.

        Args:
            days: Number of days to analyze

        Returns:
            List of recommendations
        """
        recommendations = []

        # Analyze performance
        trends = self.analyze_response_time_trends(days)
        if trends.get("trend_pct", 0) > 10:
            recommendations.append(
                Recommendation(
                    recommendation_id="perf_degradation",
                    title="Investigate Response Time Degradation",
                    description="Response times have increased by {:.1f}% over the past {} days. "
                    "Consider investigating model performance, system load, or network latency.".format(
                        trends.get("trend_pct", 0), days
                    ),
                    priority="high",
                    impact_area="performance",
                    estimated_improvement_pct=15.0,
                    implementation_effort="medium",
                )
            )

        # Check for error patterns
        error_patterns = self.detect_error_patterns(days)
        if error_patterns and error_patterns[0]["frequency"] > 10:
            top_error = error_patterns[0]
            recommendations.append(
                Recommendation(
                    recommendation_id="error_handling",
                    title=f"Address High-Frequency {top_error['error_type']} Errors",
                    description=f"The '{top_error['error_type']}' error occurs {top_error['frequency']} times "
                    "in the past {} days. Implement specific handling for this error type.".format(
                        days
                    ),
                    priority="high",
                    impact_area="reliability",
                    estimated_improvement_pct=20.0,
                    implementation_effort="easy",
                )
            )

        # Check engagement
        engagement = self.analyze_user_engagement(days)
        if engagement and engagement.get("sessions_per_user", 0) < 1.5:
            recommendations.append(
                Recommendation(
                    recommendation_id="user_retention",
                    title="Improve User Retention",
                    description="Low session repeat rate ({:.2f}) suggests users may not be returning. "
                    "Consider implementing follow-up prompts or improved UX.".format(
                        engagement.get("sessions_per_user", 0)
                    ),
                    priority="medium",
                    impact_area="engagement",
                    estimated_improvement_pct=25.0,
                    implementation_effort="medium",
                )
            )

        # Check for slow models
        bottlenecks = self.get_performance_bottlenecks(days=days)
        if bottlenecks:
            slow_model = bottlenecks[0]
            recommendations.append(
                Recommendation(
                    recommendation_id="model_optimization",
                    title=f"Optimize {slow_model['model']} Model",
                    description=f"The {slow_model['model']} model has an average response time of "
                    f"{slow_model['avg_duration_ms']:.0f}ms. "
                    "Consider switching to a faster model or optimizing prompts.",
                    priority="medium",
                    impact_area="performance",
                    estimated_improvement_pct=30.0,
                    implementation_effort="hard",
                )
            )

        return recommendations

    def generate_health_report(self, days: int = 30) -> dict[str, Any]:
        """
        Generate a comprehensive health report.

        Args:
            days: Number of days to analyze

        Returns:
            Comprehensive health report
        """
        return {
            "analysis_period_days": days,
            "generated_at": datetime.now(UTC).isoformat(),
            "engagement": self.analyze_user_engagement(days),
            "performance_trends": self.analyze_response_time_trends(days),
            "error_patterns": self.detect_error_patterns(days),
            "bottlenecks": self.get_performance_bottlenecks(days=days),
            "conversation_patterns": self.analyze_conversation_patterns(days),
            "recommendations": [
                {
                    "title": r.title,
                    "priority": r.priority,
                    "description": r.description,
                    "estimated_improvement_pct": r.estimated_improvement_pct,
                }
                for r in self.get_recommendations(days)
            ],
        }
