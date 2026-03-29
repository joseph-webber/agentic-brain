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
Real-time Metrics Collection
=============================

Collects and stores performance metrics for responses, errors, and session duration.
All metrics are persisted in Neo4j for historical analysis.

Metrics tracked:
  - Response times (milliseconds)
  - Token usage (input/output)
  - Error rates and types
  - Session duration
  - Model usage
  - Cost per response

Example:
    >>> collector = MetricsCollector(driver)
    >>> collector.record_response_time("session1", 250, 10, 50, model="gpt-4")
    >>> collector.record_error("session1", "timeout", "Request exceeded 30s limit")
    >>> metrics = collector.get_prometheus_metrics()
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class ResponseMetric:
    """A single response performance metric."""

    metric_id: str
    session_id: str
    user_id: str | None
    duration_ms: int
    tokens_in: int
    tokens_out: int
    model: str
    bot_name: str
    timestamp: str
    cost: float = 0.0


@dataclass
class ErrorMetric:
    """A single error event."""

    error_id: str
    session_id: str
    user_id: str | None
    error_type: str
    message: str
    timestamp: str
    bot_name: str
    recovery_time_ms: int | None = None


class MetricsCollector:
    """
    Collects and stores performance metrics in Neo4j.

    Tracks response times, token usage, errors, and session metrics.
    Provides Prometheus-compatible export for monitoring systems.
    """

    # Token pricing (adjust based on your LLM provider)
    DEFAULT_TOKEN_PRICING = {
        "gpt-4": {"input": 0.00003, "output": 0.0006},
        "gpt-3.5-turbo": {"input": 0.0000015, "output": 0.000002},
        "claude-3": {"input": 0.000003, "output": 0.000015},
    }

    def __init__(
        self, driver, token_pricing: dict[str, dict[str, float]] | None = None
    ):
        """
        Initialize metrics collector.

        Args:
            driver: Neo4j driver instance
            token_pricing: Optional custom token pricing dict
        """
        self.driver = driver
        self.token_pricing = token_pricing or self.DEFAULT_TOKEN_PRICING
        self._create_indexes()

    def _create_indexes(self):
        """Create Neo4j indexes for efficient querying."""
        queries = [
            """
            CREATE INDEX metric_session IF NOT EXISTS
            FOR (m:ResponseMetric) ON (m.session_id)
            """,
            """
            CREATE INDEX metric_timestamp IF NOT EXISTS
            FOR (m:ResponseMetric) ON (m.timestamp)
            """,
            """
            CREATE INDEX error_session IF NOT EXISTS
            FOR (e:ErrorMetric) ON (e.session_id)
            """,
            """
            CREATE INDEX error_timestamp IF NOT EXISTS
            FOR (e:ErrorMetric) ON (e.timestamp)
            """,
        ]

        with self.driver.session() as session:
            for query in queries:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug(f"Index creation info: {e}")

    def record_response_time(
        self,
        session_id: str,
        duration_ms: int,
        tokens_in: int,
        tokens_out: int,
        model: str = "gpt-3.5-turbo",
        bot_name: str = "default",
        user_id: str | None = None,
    ) -> ResponseMetric:
        """
        Record a response time metric.

        Args:
            session_id: Session identifier
            duration_ms: Response time in milliseconds
            tokens_in: Input tokens used
            tokens_out: Output tokens generated
            model: Model name used
            bot_name: Name of the chatbot
            user_id: Optional user identifier

        Returns:
            ResponseMetric object
        """
        metric_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        # Calculate cost
        cost = self._calculate_cost(model, tokens_in, tokens_out)

        metric = ResponseMetric(
            metric_id=metric_id,
            session_id=session_id,
            user_id=user_id,
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            bot_name=bot_name,
            timestamp=timestamp,
            cost=cost,
        )

        # Store in Neo4j
        query = """
        CREATE (m:ResponseMetric {
            metric_id: $metric_id,
            session_id: $session_id,
            user_id: $user_id,
            duration_ms: $duration_ms,
            tokens_in: $tokens_in,
            tokens_out: $tokens_out,
            model: $model,
            bot_name: $bot_name,
            timestamp: $timestamp,
            cost: $cost
        })

        WITH m
        MATCH (s:Session {session_id: $session_id})
        CREATE (s)-[:HAS_METRIC]->(m)
        """

        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    {
                        "metric_id": metric_id,
                        "session_id": session_id,
                        "user_id": user_id,
                        "duration_ms": duration_ms,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "model": model,
                        "bot_name": bot_name,
                        "timestamp": timestamp,
                        "cost": cost,
                    },
                )
            logger.debug(f"Recorded response metric {metric_id}")
        except Exception as e:
            logger.error(f"Failed to record response metric: {e}")

        return metric

    def record_error(
        self,
        session_id: str,
        error_type: str,
        message: str,
        bot_name: str = "default",
        user_id: str | None = None,
        recovery_time_ms: int | None = None,
    ) -> ErrorMetric:
        """
        Record an error metric.

        Args:
            session_id: Session identifier
            error_type: Type of error (timeout, rate_limit, invalid_input, etc.)
            message: Error message/description
            bot_name: Name of the chatbot
            user_id: Optional user identifier
            recovery_time_ms: Time to recover from error (if applicable)

        Returns:
            ErrorMetric object
        """
        error_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        error = ErrorMetric(
            error_id=error_id,
            session_id=session_id,
            user_id=user_id,
            error_type=error_type,
            message=message,
            timestamp=timestamp,
            bot_name=bot_name,
            recovery_time_ms=recovery_time_ms,
        )

        query = """
        CREATE (e:ErrorMetric {
            error_id: $error_id,
            session_id: $session_id,
            user_id: $user_id,
            error_type: $error_type,
            message: $message,
            timestamp: $timestamp,
            bot_name: $bot_name,
            recovery_time_ms: $recovery_time_ms
        })

        WITH e
        MATCH (s:Session {session_id: $session_id})
        CREATE (s)-[:HAS_ERROR]->(e)
        """

        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    {
                        "error_id": error_id,
                        "session_id": session_id,
                        "user_id": user_id,
                        "error_type": error_type,
                        "message": message,
                        "timestamp": timestamp,
                        "bot_name": bot_name,
                        "recovery_time_ms": recovery_time_ms,
                    },
                )
            logger.debug(f"Recorded error metric {error_id}")
        except Exception as e:
            logger.error(f"Failed to record error metric: {e}")

        return error

    def record_session_duration(
        self,
        session_id: str,
        duration_ms: int,
        message_count: int,
        bot_name: str = "default",
        user_id: str | None = None,
    ) -> None:
        """
        Record session duration and activity.

        Args:
            session_id: Session identifier
            duration_ms: Total session duration
            message_count: Number of messages in session
            bot_name: Name of the chatbot
            user_id: Optional user identifier
        """
        query = """
        MATCH (s:Session {session_id: $session_id})
        SET s.total_duration_ms = $duration_ms,
            s.message_count = $message_count,
            s.session_metrics_recorded = $timestamp
        """

        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    {
                        "session_id": session_id,
                        "duration_ms": duration_ms,
                        "message_count": message_count,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to record session duration: {e}")

    def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """
        Get all metrics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dict with aggregated metrics
        """
        query = """
        MATCH (s:Session {session_id: $session_id})
        OPTIONAL MATCH (s)-[:HAS_METRIC]->(m:ResponseMetric)
        OPTIONAL MATCH (s)-[:HAS_ERROR]->(e:ErrorMetric)

        RETURN {
            session_id: s.session_id,
            message_count: coalesce(s.message_count, 0),
            total_duration_ms: coalesce(s.total_duration_ms, 0),
            response_metrics: collect(m {
                duration_ms: m.duration_ms,
                tokens_in: m.tokens_in,
                tokens_out: m.tokens_out,
                cost: m.cost,
                model: m.model,
                timestamp: m.timestamp
            }),
            error_metrics: collect(e {
                error_type: e.error_type,
                timestamp: e.timestamp,
                recovery_time_ms: e.recovery_time_ms
            })
        } as metrics
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, {"session_id": session_id})
                record = result.single()
                if record:
                    return cast(dict[str, Any], record["metrics"])
        except Exception as e:
            logger.error(f"Failed to get session metrics: {e}")

        return {}

    def get_metrics_summary(
        self,
        bot_name: str | None = None,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get summary metrics for a time period.

        Args:
            bot_name: Optional filter by bot name
            hours: Number of hours to look back

        Returns:
            Aggregated metrics summary
        """
        # Build query with parameterized bot_name filter (prevents SQL injection)
        if bot_name:
            query = """
            MATCH (m:ResponseMetric)
            WHERE datetime(m.timestamp) > datetime.now() - duration({hours: $hours})
            AND m.bot_name = $bot_name

            RETURN {
                total_responses: count(m),
                avg_response_time_ms: avg(m.duration_ms),
                median_response_time_ms: percentileCont(m.duration_ms, 0.5),
                p95_response_time_ms: percentileCont(m.duration_ms, 0.95),
                p99_response_time_ms: percentileCont(m.duration_ms, 0.99),
                total_tokens_in: sum(m.tokens_in),
                total_tokens_out: sum(m.tokens_out),
                total_cost: sum(m.cost),
                models_used: collect(distinct m.model)
            } as summary
            """
            params = {"hours": hours, "bot_name": bot_name}
        else:
            query = """
            MATCH (m:ResponseMetric)
            WHERE datetime(m.timestamp) > datetime.now() - duration({hours: $hours})

            RETURN {
                total_responses: count(m),
                avg_response_time_ms: avg(m.duration_ms),
                median_response_time_ms: percentileCont(m.duration_ms, 0.5),
                p95_response_time_ms: percentileCont(m.duration_ms, 0.95),
                p99_response_time_ms: percentileCont(m.duration_ms, 0.99),
                total_tokens_in: sum(m.tokens_in),
                total_tokens_out: sum(m.tokens_out),
                total_cost: sum(m.cost),
                models_used: collect(distinct m.model)
            } as summary
            """
            params = {"hours": hours}

        try:
            with self.driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                if record:
                    return cast(dict[str, Any], record["summary"])
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")

        return {}

    def get_error_stats(
        self,
        bot_name: str | None = None,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get error statistics.

        Args:
            bot_name: Optional filter by bot name
            hours: Number of hours to look back

        Returns:
            Error statistics
        """
        # Build query with parameterized bot_name filter (prevents SQL injection)
        if bot_name:
            query = """
            MATCH (e:ErrorMetric)
            WHERE datetime(e.timestamp) > datetime.now() - duration({hours: $hours})
            AND e.bot_name = $bot_name

            WITH e
            RETURN {
                total_errors: count(e),
                error_types: collect(distinct e.error_type),
                avg_recovery_time_ms: avg(coalesce(e.recovery_time_ms, 0)),
                error_rate_pct: count(e) * 100.0 /
                    (count(e) + coalesce(count(distinct e.session_id), 0))
            } as error_stats
            """
            params = {"hours": hours, "bot_name": bot_name}
        else:
            query = """
            MATCH (e:ErrorMetric)
            WHERE datetime(e.timestamp) > datetime.now() - duration({hours: $hours})

            WITH e
            RETURN {
                total_errors: count(e),
                error_types: collect(distinct e.error_type),
                avg_recovery_time_ms: avg(coalesce(e.recovery_time_ms, 0)),
                error_rate_pct: count(e) * 100.0 /
                    (count(e) + coalesce(count(distinct e.session_id), 0))
            } as error_stats
            """
            params = {"hours": hours}

        try:
            with self.driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                if record:
                    return record["error_stats"]
        except Exception as e:
            logger.error(f"Failed to get error stats: {e}")

        return {}

    def get_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        summary = self.get_metrics_summary()
        errors = self.get_error_stats()

        lines = [
            "# HELP agentic_brain_response_time_ms Response time in milliseconds",
            "# TYPE agentic_brain_response_time_ms gauge",
            f'agentic_brain_response_time_ms{{quantile="avg"}} {summary.get("avg_response_time_ms", 0)}',
            f'agentic_brain_response_time_ms{{quantile="p95"}} {summary.get("p95_response_time_ms", 0)}',
            f'agentic_brain_response_time_ms{{quantile="p99"}} {summary.get("p99_response_time_ms", 0)}',
            "",
            "# HELP agentic_brain_total_responses Total number of responses",
            "# TYPE agentic_brain_total_responses counter",
            f'agentic_brain_total_responses {summary.get("total_responses", 0)}',
            "",
            "# HELP agentic_brain_total_tokens Total tokens used",
            "# TYPE agentic_brain_total_tokens counter",
            f'agentic_brain_total_tokens{{type="input"}} {summary.get("total_tokens_in", 0)}',
            f'agentic_brain_total_tokens{{type="output"}} {summary.get("total_tokens_out", 0)}',
            "",
            "# HELP agentic_brain_total_cost Total cost in USD",
            "# TYPE agentic_brain_total_cost gauge",
            f'agentic_brain_total_cost {summary.get("total_cost", 0):.6f}',
            "",
            "# HELP agentic_brain_errors Total errors",
            "# TYPE agentic_brain_errors counter",
            f'agentic_brain_errors {errors.get("total_errors", 0)}',
        ]

        return "\n".join(lines)

    def _calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost for a response."""
        pricing = self.token_pricing.get(model, {})
        input_cost = tokens_in * pricing.get("input", 0)
        output_cost = tokens_out * pricing.get("output", 0)
        return input_cost + output_cost
