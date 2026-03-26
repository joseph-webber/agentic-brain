# Kafka Client Stacks

Agentic Brain uses **three different Kafka/Redpanda client libraries** in
different parts of the codebase. Each choice was driven by the threading model
of the calling layer. This document records the decision so that future
contributors know which library to reach for and why.

## Summary Table

| Module | Library | Import style | Why |
|---|---|---|---|
| `infra/event_bridge.py` | `confluent_kafka` | top-level (hard dep) | Synchronous bridge; needs low-level `AdminClient`, `flush()`, `poll()` |
| `durability/task_queue.py` | `aiokafka` | lazy (inside method) | Fully async task queue; no thread bridging |
| `durability/event_store.py` | `aiokafka` | lazy (inside method) | Fully async event sourcing; coroutine producers/consumers |
| `rag/loaders/event_stream.py` | `kafka-python` | lazy (module guard) | Synchronous RAG ingestion path; no event loop in scope |
| `voice/redpanda_queue.py` | `aiokafka` | lazy (try/except) | Async voice queue; degrades to Redis → in-memory |

## Library Comparison

### `confluent_kafka` (librdkafka C extension)
- **Pros**: Fastest throughput; rich admin API; production-grade reliability
- **Cons**: C extension — harder to install on some platforms; no native asyncio support
- **Use when**: You need `AdminClient`, fine-grained `Producer.flush()`, or max throughput

### `aiokafka` (pure Python, asyncio-native)
- **Pros**: First-class asyncio; simple producer/consumer API; easy to install
- **Cons**: Lower throughput than librdkafka; no admin API comparable to confluent_kafka
- **Use when**: Calling from an `async def` context; default choice for new async code

### `kafka-python` (pure Python, synchronous)
- **Pros**: Simple; synchronous; no event loop required
- **Cons**: Actively maintained but slower feature development than the others
- **Use when**: Calling from a sync context and `confluent_kafka` is not worth the install overhead

## Standardisation Plan

The long-term goal is to reduce to **two** stacks:

1. **`aiokafka`** — default for all async code (durability, voice)
2. **`confluent_kafka`** — only where `AdminClient` or max throughput is needed

`kafka-python` in `rag/loaders/event_stream.py` can be replaced with a small
sync wrapper around `confluent_kafka` once that module needs more features.
Track this in: [GitHub Issues → label `kafka-cleanup`].

## Installation

```bash
# Core async stack (most modules)
pip install aiokafka

# Bridge / admin operations
pip install confluent-kafka

# Legacy RAG loader (sync)
pip install kafka-python
```

All three are optional extras — the codebase degrades gracefully to in-memory
fallbacks when none are installed.
