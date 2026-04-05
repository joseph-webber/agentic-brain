# Analytics Module

The `agentic_brain.analytics` package provides persistent telemetry, usage analysis, insight generation, and export tooling for Agentic Brain.

## Overview

This module is organized around four responsibilities:

- **Metrics collection**: capture response latency, token usage, errors, session duration, and estimated cost.
- **Usage aggregation**: summarize activity by day, week, month, and user.
- **Insights generation**: detect trends, bottlenecks, and recurring issues.
- **Exports**: publish analytics data for reporting and dashboards.

Primary entry points:

- `MetricsCollector`
- `UsageTracker`
- `InsightsEngine`
- `MetricsExporter`

## Available Metrics and Insights

### Core metrics

- Response duration in milliseconds
- Input and output token counts
- Per-response cost
- Error type and recovery time
- Session duration and message count
- Model and bot usage

### Aggregated usage views

- Daily response, error, token, cost, and activity totals
- Weekly rollups with daily breakdowns
- Monthly cost and usage summaries
- Per-user activity summaries
- Top users by responses, cost, or errors

### Insights

- Conversation pattern detection
- Error pattern detection
- Response time trend analysis
- User engagement analysis
- Performance bottleneck identification
- Actionable recommendations

## Data Collection Methods

Analytics data is stored in Neo4j and collected through the following methods:

- `MetricsCollector.record_response_time()`
- `MetricsCollector.record_error()`
- `MetricsCollector.record_session_duration()`
- `UsageTracker.get_daily_stats()`
- `UsageTracker.get_weekly_stats()`
- `UsageTracker.get_monthly_stats()`
- `UsageTracker.get_user_stats()`

The collector also creates indexes for `session_id` and `timestamp` on response and error nodes to support time-based queries.

### Neo4j schema

- `:ResponseMetric`
- `:ErrorMetric`
- `(:Session)-[:HAS_METRIC]->(:ResponseMetric)`
- `(:Session)-[:HAS_ERROR]->(:ErrorMetric)`

## Export Formats

`MetricsExporter` supports the following output formats:

- **CSV**: tabular exports for spreadsheets and downstream analysis
- **JSON**: structured analytics payloads for APIs and tooling
- **Prometheus**: metrics text for monitoring systems
- **HTML**: human-readable reports for sharing and review

Export methods:

- `export_metrics_csv()`
- `export_errors_csv()`
- `export_daily_stats_csv()`
- `export_json()`
- `export_prometheus()`
- `export_html_report()`
- `schedule_daily_export()`

## Dashboard Integration

This module is designed to plug into operational dashboards and reporting layers.

Recommended integrations:

- **Neo4j Browser / Cypher dashboards** for ad hoc investigation
- **Grafana / Prometheus** using `get_prometheus_metrics()` or `export_prometheus()`
- **Static HTML reporting** using `export_html_report()`
- **Data warehouse / BI tools** using CSV or JSON exports

Example dashboard use cases:

- Track average response time and p95 latency over time
- Monitor error rate by model or bot
- Surface top recommendations from the insights engine
- Review user engagement and retention trends

## Example

```python
from neo4j import GraphDatabase
from agentic_brain.analytics import InsightsEngine, MetricsCollector, MetricsExporter, UsageTracker

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

metrics = MetricsCollector(driver)
usage = UsageTracker(driver)
insights = InsightsEngine(driver)
exporter = MetricsExporter(driver, usage_tracker=usage, insights_engine=insights)

metrics.record_response_time(
    session_id="s1",
    duration_ms=250,
    tokens_in=12,
    tokens_out=48,
    model="gpt-4",
    bot_name="default",
)

report = insights.generate_health_report(days=30)
exporter.export_html_report("analytics-report.html", days=30)
```

## Notes

- All timestamped data is stored in ISO 8601 format.
- Cost calculations use the configured token pricing table in `MetricsCollector`.
- Time-windowed queries should be preferred for production dashboards.
