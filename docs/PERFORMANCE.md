# Performance

## What changed

- LRU embedding cache
- Query result cache
- Graph query cache
- Batched embeddings
- Batched graph queries
- Async batch processing
- Shared Neo4j driver pooling in `brain_graph`

## Synthetic benchmark results

Local benchmark run on Python 3.14 with mocked slow providers:

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| Repeated embeddings | 300.2 ms | 2.1 ms | 99.3% |
| Batched embeddings | 300.2 ms | 1.6 ms | 99.5% |
| Repeated query execution | 301.3 ms | 2.6 ms | 99.1% |
| Batched graph queries | 301.3 ms | 6.1 ms | 98.0% |
| Async work fan-out | 1.18 s | 122 ms | 89.7% |

## Neo4j pooling

- `brain_graph.get_driver()` now reuses the shared driver from `core.neo4j_pool`
- Driver creation happens once per process
- Later calls reuse the same pooled driver and sessions

## How to run

```bash
python3 -m pytest tests/test_optimization -q
```

## Notes

- These numbers are synthetic and compare code paths, not live Neo4j latency.
- Real-world gains depend on model cost, network latency, and query shape.
