# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Analytics Integration Example
==============================

Example showing how to integrate the analytics system with agentic-brain chatbots.
This demonstrates the complete workflow from metrics collection to insights generation.
"""

import time
from datetime import datetime
from neo4j import GraphDatabase

from agentic_brain.analytics import (
    MetricsCollector,
    UsageTracker,
    InsightsEngine,
    MetricsExporter,
)


def setup_analytics(neo4j_url: str, username: str, password: str):
    """Set up analytics system."""
    driver = GraphDatabase.driver(neo4j_url, auth=(username, password))
    
    metrics = MetricsCollector(driver)
    usage = UsageTracker(driver)
    insights = InsightsEngine(driver)
    exporter = MetricsExporter(driver, usage_tracker=usage, insights_engine=insights)
    
    return {
        "driver": driver,
        "metrics": metrics,
        "usage": usage,
        "insights": insights,
        "exporter": exporter,
    }


def simulate_chatbot_session(analytics, session_id: str, user_id: str):
    """Simulate a chatbot session and record metrics."""
    print(f"\n📊 Simulating session {session_id} for user {user_id}")
    
    metrics = analytics["metrics"]
    
    # Simulate 5 responses in a session
    responses = [
        {"duration_ms": 250, "tokens_in": 15, "tokens_out": 45},
        {"duration_ms": 180, "tokens_in": 12, "tokens_out": 38},
        {"duration_ms": 5000, "tokens_in": 20, "tokens_out": 100},  # slow response
        {"duration_ms": 290, "tokens_in": 18, "tokens_out": 55},
        {"duration_ms": 310, "tokens_in": 14, "tokens_out": 42},
    ]
    
    errors_occurred = []
    
    for i, response in enumerate(responses, 1):
        print(f"  Response {i}: {response['duration_ms']}ms, "
              f"{response['tokens_in']} in, {response['tokens_out']} out")
        
        metric = metrics.record_response_time(
            session_id=session_id,
            duration_ms=response["duration_ms"],
            tokens_in=response["tokens_in"],
            tokens_out=response["tokens_out"],
            model="gpt-4",
            bot_name="demo_bot",
            user_id=user_id,
        )
        
        # Simulate occasional errors
        if response["duration_ms"] > 4000:
            error = metrics.record_error(
                session_id=session_id,
                error_type="slow_response",
                message=f"Response exceeded 1000ms threshold: {response['duration_ms']}ms",
                bot_name="demo_bot",
                user_id=user_id,
                recovery_time_ms=500,
            )
            errors_occurred.append(error)
            print(f"    ⚠️  Recorded slow response error")
    
    # Record session end
    total_duration = sum(r["duration_ms"] for r in responses)
    metrics.record_session_duration(
        session_id=session_id,
        duration_ms=total_duration,
        message_count=len(responses),
        bot_name="demo_bot",
        user_id=user_id,
    )
    
    print(f"  ✓ Session ended: {total_duration}ms total, {len(errors_occurred)} errors")
    return len(errors_occurred)


def display_session_metrics(analytics, session_id: str):
    """Display metrics for a session."""
    print(f"\n📈 Metrics for session {session_id}:")
    
    metrics = analytics["metrics"]
    session_metrics = metrics.get_session_metrics(session_id)
    
    if not session_metrics:
        print("  No metrics found")
        return
    
    print(f"  Message count: {session_metrics.get('message_count', 0)}")
    print(f"  Total duration: {session_metrics.get('total_duration_ms', 0)}ms")
    print(f"  Response count: {len(session_metrics.get('response_metrics', []))}")
    print(f"  Error count: {len(session_metrics.get('error_metrics', []))}")
    
    responses = session_metrics.get("response_metrics", [])
    if responses:
        avg_time = sum(r["duration_ms"] for r in responses) / len(responses)
        total_tokens = sum(r["tokens_in"] + r["tokens_out"] for r in responses)
        total_cost = sum(r["cost"] for r in responses)
        
        print(f"  Average response time: {avg_time:.0f}ms")
        print(f"  Total tokens: {total_tokens}")
        print(f"  Total cost: ${total_cost:.4f}")


def display_daily_stats(analytics):
    """Display daily statistics."""
    print("\n📊 Daily Statistics:")
    
    usage = analytics["usage"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    daily = usage.get_daily_stats(today, bot_name="demo_bot")
    
    print(f"  Date: {daily.date}")
    print(f"  Responses: {daily.responses}")
    print(f"  Errors: {daily.errors}")
    print(f"  Error Rate: {daily.error_rate_pct:.1f}%")
    print(f"  Tokens in: {daily.tokens_in}")
    print(f"  Tokens out: {daily.tokens_out}")
    print(f"  Total cost: ${daily.total_cost:.4f}")
    print(f"  Avg response time: {daily.avg_response_time_ms:.0f}ms")
    print(f"  Active users: {daily.active_users}")
    print(f"  Active sessions: {daily.active_sessions}")


def display_insights(analytics):
    """Display insights and recommendations."""
    print("\n🔍 Analytics Insights:")
    
    insights = analytics["insights"]
    
    # Performance trends
    print("\n  Performance Trends:")
    trends = insights.analyze_response_time_trends(days=1)
    print(f"    Average response time: {trends.get('avg_overall', 0):.0f}ms")
    print(f"    Trend: {trends.get('trend_direction', 'stable')} "
          f"({trends.get('trend_pct', 0):.1f}%)")
    
    # Error patterns
    print("\n  Error Patterns:")
    errors = insights.detect_error_patterns(days=1)
    if errors:
        for error in errors[:3]:
            print(f"    {error['error_type']}: {error['frequency']} occurrences "
                  f"(severity: {error['severity']})")
    else:
        print("    No errors detected")
    
    # Recommendations
    print("\n  Recommendations:")
    recommendations = insights.get_recommendations(days=1)
    if recommendations:
        for rec in recommendations[:3]:
            print(f"    [{rec.priority.upper()}] {rec.title}")
    else:
        print("    No recommendations at this time")


def export_analytics(analytics, output_dir: str = "/tmp/agentic_brain_analytics"):
    """Export analytics to various formats."""
    import os
    from pathlib import Path
    
    print(f"\n💾 Exporting analytics to {output_dir}")
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    exporter = analytics["exporter"]
    
    # Export JSON
    json_file = os.path.join(output_dir, "analytics.json")
    exporter.export_json(json_file, include_insights=True, days=1)
    print(f"  ✓ JSON exported to {json_file}")
    
    # Export HTML report
    html_file = os.path.join(output_dir, "report.html")
    exporter.export_html_report(html_file, title="Analytics Report", days=1)
    print(f"  ✓ HTML report exported to {html_file}")
    
    # Export Prometheus metrics
    prom_file = os.path.join(output_dir, "metrics.txt")
    exporter.export_prometheus(prom_file)
    print(f"  ✓ Prometheus metrics exported to {prom_file}")


def main():
    """Run the complete analytics example."""
    print("=" * 60)
    print("Agentic-Brain Analytics System Demo")
    print("=" * 60)
    
    # Initialize analytics (adjust Neo4j credentials as needed)
    try:
        analytics = setup_analytics(
            neo4j_url="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        print("✓ Analytics system initialized")
    except Exception as e:
        print(f"✗ Failed to connect to Neo4j: {e}")
        print("  Make sure Neo4j is running at bolt://localhost:7687")
        return
    
    try:
        # Simulate multiple sessions
        sessions_data = [
            ("session_001", "user_alice"),
            ("session_002", "user_bob"),
            ("session_003", "user_alice"),  # Same user, different session
        ]
        
        for session_id, user_id in sessions_data:
            simulate_chatbot_session(analytics, session_id, user_id)
            display_session_metrics(analytics, session_id)
            time.sleep(0.1)  # Small delay between sessions
        
        # Display aggregated statistics
        display_daily_stats(analytics)
        
        # Display insights
        display_insights(analytics)
        
        # Export analytics
        export_analytics(analytics)
        
        print("\n" + "=" * 60)
        print("✓ Demo completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        analytics["driver"].close()
        print("✓ Analytics system closed")


if __name__ == "__main__":
    main()
