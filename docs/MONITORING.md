# Monitoring for agentic-brain

This document describes the lightweight observability added to the agentic-brain project.

Features
- In-process metrics collector (src/agentic_brain/monitoring/metrics.py)
  - Query latency histogram
  - Token usage counter
  - Cache hit/miss counters and hit rate
  - Error counters and error rate
  - Throughput (requests per second) over a recent window
- Health checks and a minimal WSGI app (src/agentic_brain/monitoring/health.py)
  - Dependency TCP checks for Neo4j, LLM, and cache
  - /health JSON endpoint with dependency statuses and metric snapshot
  - /metrics Prometheus-compatible plain-text exposition

Usage
- Import the global registry:

```python
from agentic_brain.monitoring import global_metrics
```

- Record events:

```python
global_metrics.record_request()
global_metrics.record_latency(0.123)
global_metrics.increment_tokens(42)
```

- Expose metrics and health endpoints in your web framework by mounting the WSGI app:

```python
from agentic_brain.monitoring import create_wsgi_app
app = create_wsgi_app()
# mount app under your server or use a WSGI server (gunicorn/uvicorn with asgi->wsgi bridge)
```

Prometheus
- The /metrics endpoint returns a small subset of Prometheus exposition format so that
  Prometheus can scrape the process and collect counters, gauges and a latency histogram.

Testing
- Tests are provided under tests/test_monitoring and can be run with pytest.

Notes
- This implementation purposefully avoids adding an external dependency on the Prometheus
  Python client by implementing a minimal, compatible exposition format.
- Health checks use simple TCP connect() checks. Configure dependency addresses with
  NEO4J_HOST/NEO4J_PORT, LLM_HOST/LLM_PORT and CACHE_HOST/CACHE_PORT environment variables.
