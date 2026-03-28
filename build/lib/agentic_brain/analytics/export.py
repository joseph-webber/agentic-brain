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
Analytics Data Export
=====================

Export analytics data in multiple formats:
- CSV for spreadsheet analysis
- JSON for API integration
- Prometheus format for monitoring systems
- HTML reports for dashboards

Example:
    >>> exporter = MetricsExporter(driver)
    >>> exporter.export_daily_stats_csv("2024-03", output_file="march_2024.csv")
    >>> exporter.export_json(output_file="metrics.json")
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class MetricsExporter:
    """
    Export analytics data in multiple formats.

    Supports CSV, JSON, Prometheus, and HTML report generation.
    """

    def __init__(self, driver, usage_tracker=None, insights_engine=None):
        """
        Initialize metrics exporter.

        Args:
            driver: Neo4j driver instance
            usage_tracker: Optional UsageTracker instance
            insights_engine: Optional InsightsEngine instance
        """
        self.driver = driver
        self.usage_tracker = usage_tracker
        self.insights_engine = insights_engine

    def export_metrics_csv(
        self,
        output_file: str,
        start_date: str,
        end_date: str,
        bot_name: str | None = None,
    ) -> int:
        """
        Export metrics to CSV.

        Args:
            output_file: Path to output CSV file
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bot_name: Optional filter by bot name

        Returns:
            Number of records exported
        """
        # Build query with parameterized bot_name filter (prevents SQL injection)
        if bot_name:
            query = """
            MATCH (m:ResponseMetric)
            WHERE date(m.timestamp) >= date($start_date)
            AND date(m.timestamp) <= date($end_date)
            AND m.bot_name = $bot_name

            RETURN {
                timestamp: m.timestamp,
                session_id: m.session_id,
                user_id: m.user_id,
                model: m.model,
                duration_ms: m.duration_ms,
                tokens_in: m.tokens_in,
                tokens_out: m.tokens_out,
                cost: m.cost,
                bot_name: m.bot_name
            } as metric
            ORDER BY m.timestamp DESC
            """
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "bot_name": bot_name,
            }
        else:
            query = """
            MATCH (m:ResponseMetric)
            WHERE date(m.timestamp) >= date($start_date)
            AND date(m.timestamp) <= date($end_date)

            RETURN {
                timestamp: m.timestamp,
                session_id: m.session_id,
                user_id: m.user_id,
                model: m.model,
                duration_ms: m.duration_ms,
                tokens_in: m.tokens_in,
                tokens_out: m.tokens_out,
                cost: m.cost,
                bot_name: m.bot_name
            } as metric
            ORDER BY m.timestamp DESC
            """
            params = {"start_date": start_date, "end_date": end_date}

        records = []
        try:
            with self.driver.session() as session:
                result = session.run(query, params)

                for record in result:
                    records.append(record["metric"])
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return 0

        if not records:
            logger.warning("No metrics found for export")
            return 0

        try:
            with open(output_file, "w", newline="") as f:
                fieldnames = list(records[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)

            logger.info(f"Exported {len(records)} metrics to {output_file}")
            return len(records)
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")
            return 0

    def export_errors_csv(
        self,
        output_file: str,
        start_date: str,
        end_date: str,
        bot_name: str | None = None,
    ) -> int:
        """
        Export error metrics to CSV.

        Args:
            output_file: Path to output CSV file
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bot_name: Optional filter by bot name

        Returns:
            Number of records exported
        """
        # Build query with parameterized bot_name filter (prevents SQL injection)
        if bot_name:
            query = """
            MATCH (e:ErrorMetric)
            WHERE date(e.timestamp) >= date($start_date)
            AND date(e.timestamp) <= date($end_date)
            AND e.bot_name = $bot_name

            RETURN {
                timestamp: e.timestamp,
                session_id: e.session_id,
                user_id: e.user_id,
                error_type: e.error_type,
                message: e.message,
                recovery_time_ms: e.recovery_time_ms,
                bot_name: e.bot_name
            } as error
            ORDER BY e.timestamp DESC
            """
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "bot_name": bot_name,
            }
        else:
            query = """
            MATCH (e:ErrorMetric)
            WHERE date(e.timestamp) >= date($start_date)
            AND date(e.timestamp) <= date($end_date)

            RETURN {
                timestamp: e.timestamp,
                session_id: e.session_id,
                user_id: e.user_id,
                error_type: e.error_type,
                message: e.message,
                recovery_time_ms: e.recovery_time_ms,
                bot_name: e.bot_name
            } as error
            ORDER BY e.timestamp DESC
            """
            params = {"start_date": start_date, "end_date": end_date}

        records = []
        try:
            with self.driver.session() as session:
                result = session.run(query, params)

                for record in result:
                    records.append(record["error"])
        except Exception as e:
            logger.error(f"Failed to export errors: {e}")
            return 0

        if not records:
            logger.warning("No errors found for export")
            return 0

        try:
            with open(output_file, "w", newline="") as f:
                fieldnames = list(records[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)

            logger.info(f"Exported {len(records)} errors to {output_file}")
            return len(records)
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")
            return 0

    def export_daily_stats_csv(
        self,
        month_year: str,  # YYYY-MM
        output_file: str,
    ) -> int:
        """
        Export daily statistics for a month to CSV.

        Args:
            month_year: Month in YYYY-MM format
            output_file: Path to output CSV file

        Returns:
            Number of days exported
        """
        # Parse month
        year, month = map(int, month_year.split("-"))

        # Generate dates
        dates = []
        current = datetime(year, month, 1)
        while current.month == month:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        records = []
        for date_str in dates:
            if self.usage_tracker:
                stats = self.usage_tracker.get_daily_stats(date_str)
                records.append(
                    {
                        "date": stats.date,
                        "responses": stats.responses,
                        "errors": stats.errors,
                        "tokens_in": stats.tokens_in,
                        "tokens_out": stats.tokens_out,
                        "total_cost": stats.total_cost,
                        "avg_response_time_ms": stats.avg_response_time_ms,
                        "error_rate_pct": stats.error_rate_pct,
                        "active_users": stats.active_users,
                        "active_sessions": stats.active_sessions,
                    }
                )

        if not records:
            logger.warning(f"No data found for {month_year}")
            return 0

        try:
            with open(output_file, "w", newline="") as f:
                fieldnames = list(records[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)

            logger.info(f"Exported {len(records)} days to {output_file}")
            return len(records)
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")
            return 0

    def export_json(
        self,
        output_file: str,
        include_insights: bool = True,
        days: int = 30,
    ) -> bool:
        """
        Export comprehensive analytics to JSON.

        Args:
            output_file: Path to output JSON file
            include_insights: Whether to include insights analysis
            days: Number of days to analyze

        Returns:
            True if successful
        """
        data = {
            "export_time": datetime.now(UTC).isoformat(),
            "analysis_period_days": days,
        }

        # Add usage data if available
        if self.usage_tracker:
            end_date = datetime.now(UTC).strftime("%Y-%m-%d")
            (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")

            data["usage"] = {
                "weekly_summary": self.usage_tracker.get_weekly_stats(end_date),
                "top_users": self.usage_tracker.get_top_users(limit=20, days=days),
            }

        # Add insights if available
        if include_insights and self.insights_engine:
            data["insights"] = self.insights_engine.generate_health_report(days)

        try:
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"Exported analytics to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to write JSON: {e}")
            return False

    def export_prometheus(self, output_file: str) -> bool:
        """
        Export metrics in Prometheus format.

        Args:
            output_file: Path to output Prometheus file

        Returns:
            True if successful
        """
        try:
            from .metrics import MetricsCollector

            collector = MetricsCollector(self.driver)
            metrics = collector.get_prometheus_metrics()

            with open(output_file, "w") as f:
                f.write(metrics)

            logger.info(f"Exported Prometheus metrics to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to export Prometheus metrics: {e}")
            return False

    def export_html_report(
        self,
        output_file: str,
        title: str = "Analytics Report",
        days: int = 30,
    ) -> bool:
        """
        Export a comprehensive HTML report.

        Args:
            output_file: Path to output HTML file
            title: Report title
            days: Number of days to analyze

        Returns:
            True if successful
        """
        try:
            html_content = self._generate_html_report(title, days)

            with open(output_file, "w") as f:
                f.write(html_content)

            logger.info(f"Exported HTML report to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to export HTML report: {e}")
            return False

    def _generate_html_report(self, title: str, days: int) -> str:
        """Generate HTML report content."""
        report_data = {}

        if self.insights_engine:
            report_data = self.insights_engine.generate_health_report(days)

        engagement = report_data.get("engagement", {})
        performance = report_data.get("performance_trends", {})
        errors = report_data.get("error_patterns", [])
        recommendations = report_data.get("recommendations", [])

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; }}
                h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
                h2 {{ color: #555; margin-top: 30px; }}
                .metric {{ display: inline-block; width: 22%; margin: 1%; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #007bff; border-radius: 4px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
                .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
                .error {{ background-color: #ffe6e6; border-left-color: #dc3545; }}
                .error .metric-value {{ color: #dc3545; }}
                .recommendation {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 10px 0; border-radius: 4px; }}
                .rec-high {{ background-color: #f8d7da; border-left-color: #dc3545; }}
                .rec-medium {{ background-color: #fff3cd; border-left-color: #ffc107; }}
                .rec-low {{ background-color: #d1ecf1; border-left-color: #17a2b8; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #007bff; color: white; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{title}</h1>
                <p>Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p>Analysis Period: Last {days} days</p>

                <h2>Key Metrics</h2>
                <div>
                    <div class="metric">
                        <div class="metric-value">{engagement.get('unique_users', 0)}</div>
                        <div class="metric-label">Active Users</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{engagement.get('total_responses', 0)}</div>
                        <div class="metric-label">Total Responses</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{performance.get('avg_overall', 0):.0f}ms</div>
                        <div class="metric-label">Avg Response Time</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{performance.get('trend_pct', 0):.1f}%</div>
                        <div class="metric-label">Trend ({performance.get('trend_direction', 'stable')})</div>
                    </div>
                </div>

                <h2>Top Error Types</h2>
                <table>
                    <tr><th>Error Type</th><th>Frequency</th><th>Severity</th></tr>
        """

        for error in errors[:5]:
            html += f"""
                    <tr>
                        <td>{error['error_type']}</td>
                        <td>{error['frequency']}</td>
                        <td>{error['severity'].upper()}</td>
                    </tr>
            """

        html += """
                </table>

                <h2>Recommendations</h2>
        """

        for rec in recommendations:
            priority_class = f"rec-{rec.get('priority', 'low').lower()}"
            html += f"""
                <div class="recommendation {priority_class}">
                    <strong>{rec['title']}</strong> <span style="float: right; color: #666;">{rec['priority'].upper()}</span>
                    <p>{rec['description']}</p>
                    <small>Estimated improvement: {rec.get('estimated_improvement_pct', 0):.0f}%</small>
                </div>
            """

        html += """
                <div class="footer">
                    <p>This report was automatically generated by the agentic-brain analytics system.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def schedule_daily_export(
        self,
        output_dir: str,
        format_type: str = "json",  # json, csv, html
    ) -> None:
        """
        Schedule daily exports of analytics.

        Args:
            output_dir: Directory for export files
            format_type: Export format (json, csv, html)
        """
        import schedule

        def export_daily():
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            output_path = Path(output_dir) / f"analytics-{date_str}.{format_type}"

            if format_type == "json":
                self.export_json(str(output_path))
            elif format_type == "csv":
                self.export_metrics_csv(
                    str(output_path),
                    date_str,
                    date_str,
                )
            elif format_type == "html":
                self.export_html_report(str(output_path))

        # Schedule for daily at 2 AM
        schedule.every().day.at("02:00").do(export_daily)
        logger.info(f"Scheduled daily {format_type} exports to {output_dir}")
