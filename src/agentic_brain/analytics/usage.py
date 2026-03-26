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
Usage Tracking and Aggregation
===============================

Tracks and aggregates usage metrics across different time periods:
- Daily statistics (responses, tokens, errors, cost)
- Weekly trends
- Monthly reports
- Per-user statistics

Example:
    >>> tracker = UsageTracker(driver)
    >>> daily = tracker.get_daily_stats("2024-03-20")
    >>> weekly = tracker.get_weekly_stats("2024-03-20")
    >>> user_stats = tracker.get_user_stats("user123", days=30)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DailyUsageStats:
    """Daily usage statistics."""

    date: str
    responses: int
    errors: int
    tokens_in: int
    tokens_out: int
    total_cost: float
    avg_response_time_ms: float
    error_rate_pct: float
    active_users: int
    active_sessions: int
    top_models: list[str]


@dataclass
class UserStats:
    """Per-user statistics."""

    user_id: str
    total_responses: int
    total_sessions: int
    total_cost: float
    avg_response_time_ms: float
    most_active_hour: int
    most_used_model: str
    error_rate_pct: float
    first_seen: str
    last_seen: str


class UsageTracker:
    """
    Tracks and aggregates usage statistics.

    Provides daily, weekly, monthly views and per-user analytics.
    """

    def __init__(self, driver):
        """
        Initialize usage tracker.

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    def get_daily_stats(
        self, date: str, bot_name: str | None = None
    ) -> DailyUsageStats:
        """
        Get statistics for a specific day.

        Args:
            date: Date in YYYY-MM-DD format
            bot_name: Optional filter by bot name

        Returns:
            DailyUsageStats object
        """
        # Build query with parameterized bot_name filter (prevents SQL injection)
        if bot_name:
            query = """
            WITH date($date) as target_date,
                 duration.inDays(date($date), date($date) + duration({days: 1})).days as day_duration

            OPTIONAL MATCH (m:ResponseMetric)
            WHERE apoc.date.parse(substring(m.timestamp, 0, 10), 'ms', 'yyyy-MM-dd') =
                  apoc.date.parse($date, 'ms', 'yyyy-MM-dd')
            AND m.bot_name = $bot_name

            OPTIONAL MATCH (e:ErrorMetric)
            WHERE apoc.date.parse(substring(e.timestamp, 0, 10), 'ms', 'yyyy-MM-dd') =
                  apoc.date.parse($date, 'ms', 'yyyy-MM-dd')
            AND e.bot_name = $bot_name

            RETURN {
                date: $date,
                responses: count(distinct m),
                errors: count(distinct e),
                tokens_in: coalesce(sum(m.tokens_in), 0),
                tokens_out: coalesce(sum(m.tokens_out), 0),
                total_cost: coalesce(sum(m.cost), 0.0),
                avg_response_time_ms: coalesce(avg(m.duration_ms), 0),
                active_users: count(distinct coalesce(m.user_id, e.user_id)),
                active_sessions: count(distinct coalesce(m.session_id, e.session_id)),
                top_models: head(collect(distinct m.model order by count(*) desc), 3)
            } as stats
            """
        else:
            query = """
            WITH date($date) as target_date,
                 duration.inDays(date($date), date($date) + duration({days: 1})).days as day_duration

            OPTIONAL MATCH (m:ResponseMetric)
            WHERE apoc.date.parse(substring(m.timestamp, 0, 10), 'ms', 'yyyy-MM-dd') =
                  apoc.date.parse($date, 'ms', 'yyyy-MM-dd')

            OPTIONAL MATCH (e:ErrorMetric)
            WHERE apoc.date.parse(substring(e.timestamp, 0, 10), 'ms', 'yyyy-MM-dd') =
                  apoc.date.parse($date, 'ms', 'yyyy-MM-dd')

            RETURN {
                date: $date,
                responses: count(distinct m),
                errors: count(distinct e),
                tokens_in: coalesce(sum(m.tokens_in), 0),
                tokens_out: coalesce(sum(m.tokens_out), 0),
                total_cost: coalesce(sum(m.cost), 0.0),
                avg_response_time_ms: coalesce(avg(m.duration_ms), 0),
                active_users: count(distinct coalesce(m.user_id, e.user_id)),
                active_sessions: count(distinct coalesce(m.session_id, e.session_id)),
                top_models: head(collect(distinct m.model order by count(*) desc), 3)
            } as stats
            """

        try:
            with self.driver.session() as session:
                result = session.run(query, {"date": date})
                record = result.single()
                if record:
                    data = record["stats"]
                    # Calculate error rate
                    total = data["responses"] + data["errors"]
                    error_rate = (data["errors"] / total * 100) if total > 0 else 0

                    return DailyUsageStats(
                        date=data["date"],
                        responses=data["responses"],
                        errors=data["errors"],
                        tokens_in=data["tokens_in"],
                        tokens_out=data["tokens_out"],
                        total_cost=data["total_cost"],
                        avg_response_time_ms=data["avg_response_time_ms"],
                        error_rate_pct=error_rate,
                        active_users=data["active_users"],
                        active_sessions=data["active_sessions"],
                        top_models=data["top_models"] or [],
                    )
        except Exception as e:
            logger.error(f"Failed to get daily stats for {date}: {e}")

        return DailyUsageStats(
            date=date,
            responses=0,
            errors=0,
            tokens_in=0,
            tokens_out=0,
            total_cost=0.0,
            avg_response_time_ms=0.0,
            error_rate_pct=0.0,
            active_users=0,
            active_sessions=0,
            top_models=[],
        )

    def get_weekly_stats(
        self,
        end_date: str,
        bot_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Get statistics for a week.

        Args:
            end_date: End date in YYYY-MM-DD format (inclusive)
            bot_name: Optional filter by bot name

        Returns:
            Weekly aggregated statistics
        """
        start_date = (
            datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=6)
        ).strftime("%Y-%m-%d")

        daily_stats = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            stats = self.get_daily_stats(date_str, bot_name)
            daily_stats.append(stats)
            current += timedelta(days=1)

        if not daily_stats:
            return {}

        return {
            "start_date": start_date,
            "end_date": end_date,
            "daily_breakdown": [
                {
                    "date": s.date,
                    "responses": s.responses,
                    "tokens": s.tokens_in + s.tokens_out,
                    "cost": s.total_cost,
                }
                for s in daily_stats
            ],
            "total_responses": sum(s.responses for s in daily_stats),
            "total_errors": sum(s.errors for s in daily_stats),
            "total_tokens": sum(s.tokens_in + s.tokens_out for s in daily_stats),
            "total_cost": sum(s.total_cost for s in daily_stats),
            "avg_response_time_ms": sum(s.avg_response_time_ms for s in daily_stats)
            / len(daily_stats),
            "avg_error_rate_pct": sum(s.error_rate_pct for s in daily_stats)
            / len(daily_stats),
            "peak_day": max(daily_stats, key=lambda s: s.responses).date,
        }

    def get_monthly_stats(
        self,
        year: int,
        month: int,
        bot_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Get statistics for a month.

        Args:
            year: Year (YYYY)
            month: Month (1-12)
            bot_name: Optional filter by bot name

        Returns:
            Monthly aggregated statistics
        """
        # Get last day of month
        if month == 12:
            last_day = 31
        else:
            next_month = datetime(year, month + 1, 1)
            last_day = (next_month - timedelta(days=1)).day

        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{last_day:02d}"

        weekly_data = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            week_end = min(current + timedelta(days=6), end)
            week_end_str = week_end.strftime("%Y-%m-%d")

            week_stats = self.get_weekly_stats(week_end_str, bot_name)
            if week_stats:
                weekly_data.append(week_stats)

            current = week_end + timedelta(days=1)

        if not weekly_data:
            return {}

        return {
            "year": year,
            "month": month,
            "total_responses": sum(w["total_responses"] for w in weekly_data),
            "total_errors": sum(w["total_errors"] for w in weekly_data),
            "total_tokens": sum(w["total_tokens"] for w in weekly_data),
            "total_cost": sum(w["total_cost"] for w in weekly_data),
            "avg_response_time_ms": sum(w["avg_response_time_ms"] for w in weekly_data)
            / len(weekly_data),
            "weeks": weekly_data,
        }

    def get_user_stats(
        self,
        user_id: str,
        days: int = 30,
    ) -> UserStats:
        """
        Get statistics for a specific user.

        Args:
            user_id: User identifier
            days: Number of days to look back

        Returns:
            UserStats object
        """
        query = """
        OPTIONAL MATCH (m:ResponseMetric {user_id: $user_id})
        WHERE datetime(m.timestamp) > datetime.now() - duration({days: $days})

        OPTIONAL MATCH (e:ErrorMetric {user_id: $user_id})
        WHERE datetime(e.timestamp) > datetime.now() - duration({days: $days})

        OPTIONAL MATCH (m2:ResponseMetric {user_id: $user_id})

        WITH m, e, m2, $user_id as user_id
        RETURN {
            total_responses: count(distinct m),
            total_sessions: count(distinct m.session_id),
            total_cost: coalesce(sum(m.cost), 0.0),
            avg_response_time_ms: coalesce(avg(m.duration_ms), 0),
            most_used_model: head(collect(distinct m.model order by count(*) desc)),
            error_rate_pct: count(distinct e) * 100.0 /
                (count(distinct e) + count(distinct m)),
            most_active_hour: head(collect(distinct hour(datetime(m.timestamp))
                order by count(*) desc)),
            first_seen: coalesce(min(m2.timestamp), datetime.now().toString()),
            last_seen: coalesce(max(m.timestamp), datetime.now().toString())
        } as stats
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, {"user_id": user_id, "days": days})
                record = result.single()
                if record:
                    data = record["stats"]
                    return UserStats(
                        user_id=user_id,
                        total_responses=data["total_responses"],
                        total_sessions=data["total_sessions"],
                        total_cost=data["total_cost"],
                        avg_response_time_ms=data["avg_response_time_ms"],
                        most_active_hour=data["most_active_hour"] or 0,
                        most_used_model=data["most_used_model"] or "unknown",
                        error_rate_pct=data["error_rate_pct"],
                        first_seen=data["first_seen"],
                        last_seen=data["last_seen"],
                    )
        except Exception as e:
            logger.error(f"Failed to get user stats for {user_id}: {e}")

        return UserStats(
            user_id=user_id,
            total_responses=0,
            total_sessions=0,
            total_cost=0.0,
            avg_response_time_ms=0.0,
            most_active_hour=0,
            most_used_model="unknown",
            error_rate_pct=0.0,
            first_seen="",
            last_seen="",
        )

    def get_top_users(
        self,
        limit: int = 10,
        days: int = 30,
        order_by: str = "responses",  # responses, cost, or errors
    ) -> list[dict[str, Any]]:
        """
        Get top users by various metrics.

        Args:
            limit: Number of users to return
            days: Number of days to look back
            order_by: Metric to sort by (responses, cost, errors)

        Returns:
            List of top users with stats
        """
        order_field = {
            "responses": "count(distinct m)",
            "cost": "sum(m.cost)",
            "errors": "count(distinct e)",
        }.get(order_by, "count(distinct m)")

        query = f"""
        OPTIONAL MATCH (m:ResponseMetric)
        WHERE datetime(m.timestamp) > datetime.now() - duration({{days: $days}})

        OPTIONAL MATCH (e:ErrorMetric)
        WHERE datetime(e.timestamp) > datetime.now() - duration({{days: $days}})

        WITH m.user_id as user_id, m, e
        WHERE user_id IS NOT NULL

        RETURN {{
            user_id: user_id,
            responses: count(distinct m),
            cost: coalesce(sum(m.cost), 0.0),
            errors: count(distinct e),
            avg_response_time_ms: coalesce(avg(m.duration_ms), 0)
        }} as user_data
        ORDER BY {order_field} DESC
        LIMIT $limit
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, {"days": days, "limit": limit})
                return [record["user_data"] for record in result]
        except Exception as e:
            logger.error(f"Failed to get top users: {e}")

        return []

    def estimate_monthly_cost(self, year: int, month: int) -> float:
        """
        Estimate total cost for a month.

        Args:
            year: Year (YYYY)
            month: Month (1-12)

        Returns:
            Estimated cost in USD
        """
        stats = self.get_monthly_stats(year, month)
        return float(stats.get("total_cost", 0.0))
