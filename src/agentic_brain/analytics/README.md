# Analytics and Metrics System

A comprehensive analytics and metrics collection system for agentic-brain that tracks chatbot performance, usage patterns, and generates actionable insights.

## Features

### 📊 Real-Time Metrics Collection
- **Response Times**: Track millisecond-level response performance
- **Token Usage**: Monitor input/output tokens per request
- **Error Metrics**: Capture error types, frequencies, and recovery times
- **Session Metrics**: Track session duration and message counts
- **Cost Estimation**: Calculate per-response and monthly costs

### 📈 Usage Tracking & Aggregation
- **Daily Statistics**: Aggregate responses, errors, tokens, costs by day
- **Weekly Trends**: Analyze patterns over weeks
- **Monthly Reports**: Generate comprehensive monthly summaries
- **Per-User Statistics**: Track individual user behavior and usage
- **Top Users**: Identify high-value users by responses, cost, or errors

### 🔍 Advanced Insights
- **Conversation Pattern Analysis**: Identify common questions and topics
- **Error Pattern Detection**: Find recurring error types and causes
- **Response Time Trends**: Monitor performance degradation
- **User Engagement Analysis**: Measure session repeat rates and behavior
- **Performance Bottlenecks**: Identify slow models or endpoints
- **Automated Recommendations**: Get actionable improvement suggestions

### 📤 Multiple Export Formats
- **CSV**: Spreadsheet-compatible format for analysis
- **JSON**: API-friendly format with nested data
- **Prometheus**: Monitoring system integration
- **HTML**: Beautiful shareable reports
- **Scheduled Exports**: Automatic daily/weekly exports

## Quick Start

### Basic Metrics Collection

```python
from neo4j import GraphDatabase
from agentic_brain.analytics import MetricsCollector

# Initialize with Neo4j driver
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
metrics = MetricsCollector(driver)

# Record a response
metric = metrics.record_response_time(
    session_id="s1",
    duration_ms=250,
    tokens_in=15,
    tokens_out=45,
    model="gpt-4",
    bot_name="my_bot",
    user_id="user123"
)

# Record an error
error = metrics.record_error(
    session_id="s1",
    error_type="timeout",
    message="Request exceeded 30s limit",
    bot_name="my_bot",
    user_id="user123",
    recovery_time_ms=500
)

# Get session metrics
session_metrics = metrics.get_session_metrics("s1")
print(f"Session had {len(session_metrics['response_metrics'])} responses")
print(f"Total cost: ${session_metrics['total_cost']:.4f}")
```

### Usage Tracking

```python
from agentic_brain.analytics import UsageTracker

usage = UsageTracker(driver)

# Get daily statistics
daily = usage.get_daily_stats("2024-03-20", bot_name="my_bot")
print(f"Date: {daily.date}")
print(f"Responses: {daily.responses}")
print(f"Error Rate: {daily.error_rate_pct:.1f}%")
print(f"Total Cost: ${daily.total_cost:.2f}")
print(f"Active Users: {daily.active_users}")

# Get weekly summary
weekly = usage.get_weekly_stats("2024-03-22")
print(f"Week ending {weekly['end_date']}: {weekly['total_responses']} responses")

# Get top users
top_users = usage.get_top_users(limit=10, days=30, order_by="cost")
for user in top_users:
    print(f"{user['user_id']}: {user['responses']} responses, ${user['cost']:.2f}")

# Estimate monthly cost
cost = usage.estimate_monthly_cost(2024, 3)
print(f"Estimated March cost: ${cost:.2f}")
```

### Insights & Recommendations

```python
from agentic_brain.analytics import InsightsEngine

insights = InsightsEngine(driver)

# Analyze conversation patterns
patterns = insights.analyze_conversation_patterns(days=30, min_frequency=5)
for pattern in patterns[:5]:
    print(f"Pattern: {pattern.description}")
    print(f"Frequency: {pattern.frequency} occurrences")

# Detect error patterns
errors = insights.detect_error_patterns(days=30)
for error in errors[:5]:
    print(f"Error: {error['error_type']} ({error['frequency']} times)")
    print(f"Severity: {error['severity']}")

# Analyze performance trends
trends = insights.analyze_response_time_trends(days=30)
print(f"Trend: {trends['trend_direction']} ({trends['trend_pct']:.1f}%)")

# Get recommendations
recommendations = insights.get_recommendations(days=30)
for rec in recommendations:
    print(f"[{rec.priority.upper()}] {rec.title}")
    print(f"  Impact: ~{rec.estimated_improvement_pct:.0f}% improvement")
    print(f"  Effort: {rec.implementation_effort}")
    print(f"  {rec.description}")

# Generate comprehensive report
report = insights.generate_health_report(days=30)
print(f"Engagement: {report['engagement']['unique_users']} users")
print(f"Recommendations: {len(report['recommendations'])} actionable items")
```

### Exporting Data

```python
from agentic_brain.analytics import MetricsExporter

exporter = MetricsExporter(driver, usage_tracker=usage, insights_engine=insights)

# Export metrics to CSV
count = exporter.export_metrics_csv(
    output_file="metrics_march.csv",
    start_date="2024-03-01",
    end_date="2024-03-31"
)
print(f"Exported {count} metrics")

# Export daily stats for a month
days = exporter.export_daily_stats_csv(
    month_year="2024-03",
    output_file="daily_march.csv"
)
print(f"Exported {days} days of statistics")

# Export comprehensive JSON report
exporter.export_json(
    output_file="analytics_march.json",
    include_insights=True,
    days=30
)

# Export HTML report
exporter.export_html_report(
    output_file="report_march.html",
    title="March 2024 Analytics Report",
    days=30
)

# Export Prometheus metrics
exporter.export_prometheus("prometheus_metrics.txt")

# Schedule daily automatic exports
exporter.schedule_daily_export(
    output_dir="./analytics/daily",
    format_type="json"  # or "csv", "html"
)
```

## Architecture

### MetricsCollector
Collects and stores real-time metrics in Neo4j:
- Response times (duration in ms)
- Token usage (input/output counts)
- Error events with recovery times
- Session metrics (duration, message counts)

Neo4j nodes:
```
:ResponseMetric
  - metric_id
  - session_id
  - user_id
  - duration_ms
  - tokens_in, tokens_out
  - model
  - timestamp
  - cost

:ErrorMetric
  - error_id
  - session_id
  - user_id
  - error_type
  - message
  - timestamp
  - recovery_time_ms
```

### UsageTracker
Aggregates metrics across time periods:
- Daily aggregations
- Weekly trends
- Monthly reports
- Per-user statistics
- Top users by various metrics

### InsightsEngine
Analyzes data and generates insights:
- Conversation pattern detection
- Error pattern analysis
- Performance trend analysis
- User engagement metrics
- Bottleneck identification
- Automated recommendations

### MetricsExporter
Exports data in multiple formats:
- CSV (tabular format)
- JSON (hierarchical format)
- Prometheus (monitoring format)
- HTML (visual reports)
- Scheduled exports

## Neo4j Data Schema

### Indexes
The system automatically creates indexes for efficient querying:
```
metric_session: ResponseMetric(session_id)
metric_timestamp: ResponseMetric(timestamp)
error_session: ErrorMetric(session_id)
error_timestamp: ErrorMetric(timestamp)
```

### Relationships
```
Session -[:HAS_METRIC]-> ResponseMetric
Session -[:HAS_ERROR]-> ErrorMetric
```

## Token Pricing

Default pricing (OpenAI models):
```python
{
    "gpt-4": {"input": 0.00003, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0000015, "output": 0.000002},
    "claude-3": {"input": 0.000003, "output": 0.000015},
}
```

Customize with your own pricing:
```python
custom_pricing = {
    "my-model": {"input": 0.001, "output": 0.002}
}
metrics = MetricsCollector(driver, token_pricing=custom_pricing)
```

## Example Dashboard Queries

### Find slow responses
```cypher
MATCH (m:ResponseMetric)
WHERE m.duration_ms > 5000
AND datetime(m.timestamp) > datetime.now() - duration({days: 7})
RETURN m.model, avg(m.duration_ms), count(*) as frequency
ORDER BY frequency DESC
```

### Error rate by model
```cypher
OPTIONAL MATCH (m:ResponseMetric)
WHERE datetime(m.timestamp) > datetime.now() - duration({days: 7})

OPTIONAL MATCH (e:ErrorMetric)
WHERE datetime(e.timestamp) > datetime.now() - duration({days: 7})

RETURN 
    m.model,
    count(distinct m) as responses,
    count(distinct e) as errors,
    count(distinct e) * 100.0 / count(distinct m) as error_rate_pct
ORDER BY error_rate_pct DESC
```

### Cost breakdown by user
```cypher
MATCH (m:ResponseMetric)
WHERE m.user_id IS NOT NULL
AND datetime(m.timestamp) > datetime.now() - duration({days: 30})

RETURN 
    m.user_id,
    sum(m.cost) as total_cost,
    count(m) as responses,
    sum(m.cost) / count(m) as cost_per_response
ORDER BY total_cost DESC
LIMIT 20
```

## Best Practices

1. **Record Metrics at the Right Time**: Call `record_response_time()` after each response completes
2. **Include User IDs**: Always pass `user_id` when available for better per-user analytics
3. **Monitor Error Patterns**: Use `detect_error_patterns()` weekly to catch emerging issues
4. **Review Recommendations**: Check `get_recommendations()` monthly for optimization opportunities
5. **Schedule Exports**: Use `schedule_daily_export()` for automated reporting
6. **Set Token Pricing**: Customize pricing for accurate cost estimation
7. **Track Session Duration**: Call `record_session_duration()` when sessions end

## Testing

Run the test suite:
```bash
pytest tests/test_analytics.py -v
```

Tests cover:
- Metrics collection and storage
- Usage aggregation across time periods
- Insight generation and recommendations
- Export functionality (CSV, JSON, HTML)
- Error handling and edge cases

## Performance Considerations

- Indexes on `session_id` and `timestamp` for fast queries
- Use time-window filters in queries to limit result sets
- Export historical data monthly and archive
- Consider TTL (time-to-live) policies for old metrics

## Troubleshooting

### High Memory Usage
- Limit query windows (e.g., last 30 days instead of all-time)
- Archive old metrics to separate storage
- Use aggregated views instead of raw metrics

### Slow Queries
- Verify indexes are created: `SHOW INDEXES`
- Use EXPLAIN to analyze query plans
- Add date range filters to all queries

### Missing Metrics
- Verify `record_response_time()` is called after each response
- Check Neo4j connection and credentials
- Review error logs for exception messages

## License

Apache-2.0. See LICENSE file for details.
