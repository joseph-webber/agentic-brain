# Benchmarking Agentic Brain

Agentic Brain includes a benchmark runner for tracking core runtime performance over time.

## What it measures

The benchmark suite records these metrics:

- **LLM response time**: p50, p95, and p99 latency for non-streaming completions.
- **Neo4j query time**: latency for a configurable Cypher query.
- **Voice synthesis latency**: time required to synthesize a short utterance.
- **Memory usage**: sampled resident memory during the benchmark run.
- **Context size**: serialized request context size in bytes.
- **Success rate**: percentage of successful benchmark operations.

Each run is timestamped, serialized as JSON, and can be compared with the latest historical run to detect regressions.

## Files

- `src/agentic_brain/benchmark/metrics.py` — metric definitions and result models.
- `src/agentic_brain/benchmark/runner.py` — `BrainBenchmark` runner and probe execution.
- `src/agentic_brain/benchmark/reporter.py` — JSON, table, Markdown, and trend comparison reporting.
- `scripts/run-benchmark.py` — CLI entry point for local runs and CI automation.

## Quick start

Run the full benchmark suite and emit JSON to standard output:

```bash
python3 scripts/run-benchmark.py
```

Write a copy to disk and retain the run in benchmark history:

```bash
python3 scripts/run-benchmark.py \
  --output .benchmarks/latest.json \
  --history-dir .benchmarks/agentic-brain
```

Run a faster smoke benchmark for CI:

```bash
python3 scripts/run-benchmark.py \
  --iterations 3 \
  --warmup 1 \
  --output .benchmarks/ci-smoke.json
```

## Historical trend tracking

By default, each run is stored under `.benchmarks/agentic-brain/` and compared with the latest prior JSON result in that directory.

When regressions exceed the configured metric threshold:

- The JSON payload includes a `comparison` block with detailed findings.
- The script exits with status code `2`.

That makes the script suitable for CI gates and scheduled performance monitoring.

## Optional environment configuration

### Neo4j benchmark

Set a connection URI and, if required, credentials:

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=secret
```

Override the query at runtime:

```bash
python3 scripts/run-benchmark.py --neo4j-query "RETURN 1 AS ok"
```

If Neo4j is not configured, the metric is marked as `skipped`.

### Voice benchmark

On macOS the runner uses `say` automatically when available. To use a custom command:

```bash
python3 scripts/run-benchmark.py \
  --voice-command "say -o /dev/null Agentic Brain benchmark voice check."
```

If no supported voice command is available, the metric is marked as `skipped`.

## Useful CLI flags

- `--skip-llm` — skip LLM latency measurement.
- `--skip-neo4j` — skip Neo4j latency measurement.
- `--skip-voice` — skip voice synthesis measurement.
- `--no-compare` — disable comparison with the previous run.
- `--no-history` — disable writing a history file.
- `--format {json,table,markdown}` — choose output format.

## Example JSON shape

```json
{
  "timestamp": "2026-03-29T10:12:34+10:30",
  "duration_seconds": 12.4,
  "metrics": {
    "llm_response_time": {
      "status": "ok",
      "summary": {
        "p50": 0.412,
        "p95": 0.655,
        "p99": 0.701
      }
    },
    "success_rate": {
      "status": "ok",
      "summary": {
        "mean": 100.0
      }
    }
  },
  "comparison": {
    "has_regressions": false,
    "regressions": []
  }
}
```

## CI recommendation

For pull requests, run a lightweight benchmark and upload the JSON artifact. For scheduled builds, compare against the latest baseline and fail the job when regressions are detected.
