Agentic Brain - Load Testing

This document summarises the lightweight load testing tools and sample results.

Tools:
- src/agentic_brain/benchmark/load_test.py : provides concurrent, sustained, spike, stress and soak tests.

Sample (simulated) results against a local echo server:

- 10 concurrent queries: 10 requests, 10 success, p50 ~ 0.005s
- 100 concurrent queries: 100 requests, 100 success, p95 ~ 0.02s
- 1000 queries (sustained simulation): simulated across workers, completed without failures
- Memory under load: top diffs recorded (see memory_top_diffs in runtime output)
- Percentiles: p50, p95, p99 are computed from recorded latencies

Notes:
- This is a lightweight harness using the standard library and threads to avoid extra dependencies.
- For real production benchmarking, use dedicated tools (k6, locust, wrk) or cloud load generators.
