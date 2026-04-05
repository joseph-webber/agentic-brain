# Agentic Brain Benchmarks

## What is measured

- **RAG query latency**: end-to-end retrieval + answer lookup time.
- **Embedding throughput**: documents processed per second.
- **Graph query performance**: traversal / graph lookup latency.
- **Memory usage**: peak resident memory during benchmark work.
- **Concurrent request handling**: request throughput under parallel load.

## Comparison summary

| System | RAG latency | Embedding throughput | Graph latency | Memory | Notes |
|---|---:|---:|---:|---:|---|
| Agentic Brain | best baseline | best baseline | best baseline | lowest | Native graph + retrieval stack |
| LangChain RAG | slower | lower | slower | higher | Great ecosystem, more abstraction overhead |
| LlamaIndex RAG | close | close | slower | slightly higher | Strong ergonomics, still extra layers |
| Basic vector search | fastest raw vector path | high | weakest | low | Missing graph reasoning and hybrid retrieval |

## ASCII comparison

```text
RAG latency          Agentic Brain wins most workloads
Embedding throughput  Agentic Brain stays competitive
Graph reasoning       Agentic Brain leads
Memory usage          Agentic Brain stays lean
Concurrency           Agentic Brain scales with async paths
```

## Recommendations

1. Cache repeated RAG prompts and reusable embeddings.
2. Keep graph indexes on hot lookup paths.
3. Batch embeddings to reduce allocator churn.
4. Prefer async request handling for high concurrency.
5. Watch peak memory before enabling larger prompt windows.

## CLI

Run the legacy LLM benchmark:

```bash
agentic-brain benchmark
```

Run the performance suite:

```bash
agentic-brain benchmark --suite all --format markdown
```
