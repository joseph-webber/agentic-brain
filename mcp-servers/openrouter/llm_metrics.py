#!/usr/bin/env python3
"""
📊 LLM METRICS TRACKING SYSTEM
==============================
Track local vs cloud LLM usage, savings, performance.
Evidence-based decisions for LLM investment!
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

METRICS_DIR = Path.home() / ".brain-continuity" / "llm-metrics"
METRICS_FILE = METRICS_DIR / "metrics.json"
DAILY_FILE = METRICS_DIR / f"daily-{datetime.now().strftime('%Y-%m-%d')}.json"

# Cost estimates (per request)
COPILOT_COST_PER_REQUEST = 0.04  # $0.04 overage rate
LOCAL_COST_PER_REQUEST = 0.00   # FREE!

def ensure_dirs():
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

def load_metrics() -> dict:
    """Load current metrics"""
    ensure_dirs()
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "total_requests": 0,
        "local_requests": 0,
        "cloud_requests": 0,
        "local_success": 0,
        "local_failures": 0,
        "cloud_success": 0,
        "cloud_failures": 0,
        "total_local_time_ms": 0,
        "total_cloud_time_ms": 0,
        "quota_saved": 0,
        "money_saved": 0.0,
        "started_tracking": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }

def save_metrics(metrics: dict):
    """Save metrics to disk"""
    ensure_dirs()
    metrics["last_updated"] = datetime.now().isoformat()
    with open(METRICS_FILE, 'w') as f:
        json.dump(metrics, f, indent=2)

def load_daily() -> dict:
    """Load today's metrics"""
    ensure_dirs()
    if DAILY_FILE.exists():
        try:
            with open(DAILY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "local_requests": 0,
        "cloud_requests": 0,
        "local_success": 0,
        "local_failures": 0,
        "quota_saved": 0,
        "avg_local_time_ms": 0,
        "total_local_time_ms": 0
    }

def save_daily(daily: dict):
    """Save today's metrics"""
    ensure_dirs()
    with open(DAILY_FILE, 'w') as f:
        json.dump(daily, f, indent=2)

def record_request(
    model: str,
    task_type: str,
    success: bool,
    duration_ms: int,
    is_local: bool,
    prompt_length: int = 0,
    response_length: int = 0
):
    """Record a single LLM request"""
    metrics = load_metrics()
    daily = load_daily()
    
    metrics["total_requests"] += 1
    
    if is_local:
        metrics["local_requests"] += 1
        daily["local_requests"] += 1
        metrics["total_local_time_ms"] += duration_ms
        daily["total_local_time_ms"] += duration_ms
        
        if success:
            metrics["local_success"] += 1
            daily["local_success"] += 1
            # Count as quota saved!
            metrics["quota_saved"] += 1
            daily["quota_saved"] += 1
            metrics["money_saved"] += COPILOT_COST_PER_REQUEST
        else:
            metrics["local_failures"] += 1
            daily["local_failures"] += 1
        
        # Update average
        if daily["local_requests"] > 0:
            daily["avg_local_time_ms"] = daily["total_local_time_ms"] // daily["local_requests"]
    else:
        metrics["cloud_requests"] += 1
        daily["cloud_requests"] += 1
        metrics["total_cloud_time_ms"] += duration_ms
        
        if success:
            metrics["cloud_success"] += 1
        else:
            metrics["cloud_failures"] += 1
    
    save_metrics(metrics)
    save_daily(daily)
    
    return {
        "recorded": True,
        "is_local": is_local,
        "success": success,
        "duration_ms": duration_ms,
        "total_quota_saved": metrics["quota_saved"]
    }

def get_report() -> str:
    """Generate comprehensive metrics report"""
    metrics = load_metrics()
    daily = load_daily()
    
    # Calculate rates
    total = metrics["total_requests"] or 1
    local_pct = (metrics["local_requests"] / total) * 100
    
    local_total = metrics["local_requests"] or 1
    local_success_rate = (metrics["local_success"] / local_total) * 100
    
    avg_local_ms = metrics["total_local_time_ms"] / local_total if local_total else 0
    
    report = f"""
📊 LLM METRICS REPORT
{'═' * 50}

🎯 OVERALL STATS (since {metrics.get('started_tracking', 'unknown')[:10]})
{'─' * 50}
  Total Requests:     {metrics['total_requests']:,}
  Local Requests:     {metrics['local_requests']:,} ({local_pct:.1f}%)
  Cloud Requests:     {metrics['cloud_requests']:,}

💰 SAVINGS
{'─' * 50}
  Quota Saved:        {metrics['quota_saved']:,} requests
  Money Saved:        ${metrics['money_saved']:.2f}
  (Based on $0.04/request overage)

✅ LOCAL LLM PERFORMANCE  
{'─' * 50}
  Success Rate:       {local_success_rate:.1f}%
  Successes:          {metrics['local_success']:,}
  Failures:           {metrics['local_failures']:,}
  Avg Response Time:  {avg_local_ms:.0f}ms

📅 TODAY ({daily['date']})
{'─' * 50}
  Local Requests:     {daily['local_requests']}
  Success Rate:       {(daily['local_success'] / max(daily['local_requests'], 1) * 100):.1f}%
  Quota Saved Today:  {daily['quota_saved']}
  Avg Response:       {daily['avg_local_time_ms']}ms

📈 VERDICT
{'─' * 50}"""
    
    # Add verdict
    if metrics['local_requests'] >= 10:
        if local_success_rate >= 80:
            report += "\n  ✅ LOCAL LLM IS WORKING GREAT! Keep investing."
        elif local_success_rate >= 50:
            report += "\n  ⚠️ LOCAL LLM NEEDS IMPROVEMENT. Consider more training."
        else:
            report += "\n  ❌ LOCAL LLM STRUGGLING. Consider API keys for cloud fallback."
    else:
        report += "\n  📊 Need more data (10+ requests) for verdict."
    
    if metrics['quota_saved'] > 0:
        report += f"\n  💰 You've saved {metrics['quota_saved']} Copilot requests (${metrics['money_saved']:.2f})!"
    
    return report

def get_quick_stats() -> dict:
    """Get quick stats dict for programmatic use"""
    metrics = load_metrics()
    daily = load_daily()
    
    local_total = metrics["local_requests"] or 1
    
    return {
        "total_requests": metrics["total_requests"],
        "local_requests": metrics["local_requests"],
        "local_success_rate": (metrics["local_success"] / local_total) * 100,
        "quota_saved": metrics["quota_saved"],
        "money_saved": metrics["money_saved"],
        "today_local": daily["local_requests"],
        "today_saved": daily["quota_saved"],
        "avg_response_ms": metrics["total_local_time_ms"] / local_total if local_total else 0,
        "is_helping": metrics["local_success"] > metrics["local_failures"]
    }

if __name__ == "__main__":
    # Test
    print(get_report())
