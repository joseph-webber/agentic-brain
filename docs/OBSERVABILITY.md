# Observability and Tracing

This document describes the observability subsystem added to agentic-brain.

Components:
- RAGTracer: in src/agentic_brain/observability/tracer.py
- Span management: src/agentic_brain/observability/spans.py
- Langfuse shim: src/agentic_brain/observability/langfuse.py
- Arize Phoenix shim: src/agentic_brain/observability/phoenix.py
- OpenTelemetry shim: src/agentic_brain/observability/opentelemetry.py

Tracked metrics:
- Latency (span durations)
- Token usage (input/output)
- Retrieval quality (scores and average)
- Costs (per-call and total)

Usage:
- Create a RAGTracer and wrap operations with tracer.start_span(name).
- Call record_tokens, record_retrieval_score, record_cost as needed.
- Assign tracer.langfuse / tracer.phoenix / tracer.opentelemetry to enable exporting to shims.

Design goals:
- Minimal external dependencies for tests
- Simple shims for integration with third-party systems
- Serializable export payload for debugging and dashboards

