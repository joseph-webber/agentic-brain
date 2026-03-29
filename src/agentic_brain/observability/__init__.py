# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
OpenTelemetry observability for agentic-brain.

Zero-config by default (disabled), opt-in via environment variables.

Provides:
- Distributed tracing with span decorators
- Metrics collection (counters, histograms, gauges)
- FastAPI middleware for automatic request tracing
- Context propagation helpers

Quick Start:
    >>> from agentic_brain.observability import setup_tracing, trace
    >>>
    >>> # Enable with env vars or explicit config
    >>> setup_tracing(service_name="my-agent")
    >>>
    >>> @trace
    >>> async def my_function():
    ...     # Automatically traced
    ...     pass

Environment Variables:
    OTEL_ENABLED: Enable OpenTelemetry (default: false)
    OTEL_SERVICE_NAME: Service name for traces
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint
    OTEL_TRACES_SAMPLER: Sampling strategy

Example:
    >>> import os
    >>> os.environ["OTEL_ENABLED"] = "true"
    >>> os.environ["OTEL_SERVICE_NAME"] = "my-agent"
    >>> os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://jaeger:4317"
    >>>
    >>> from agentic_brain.observability import setup_tracing
    >>> setup_tracing()  # Uses env vars
"""

from .metrics import (
    MetricsConfig,
    active_sessions,
    chat_latency_seconds,
    # Pre-defined metrics
    chat_requests_total,
    counter,
    gauge,
    get_meter,
    histogram,
    llm_errors_total,
    record_chat_latency,
    record_chat_request,
    record_llm_error,
    record_tokens,
    set_active_sessions,
    setup_metrics,
    shutdown_metrics,
    tokens_used_total,
)
from .middleware import (
    MetricsMiddleware,
    TracingMiddleware,
    create_observability_middleware,
)
from .tracing import (
    ExporterType,
    TracingConfig,
    add_span_attributes,
    extract_context,
    get_current_span,
    get_tracer,
    inject_context,
    record_exception,
    setup_tracing,
    shutdown_tracing,
    trace,
    trace_async,
)

__all__ = [
    # Tracing
    "TracingConfig",
    "setup_tracing",
    "shutdown_tracing",
    "get_tracer",
    "trace",
    "trace_async",
    "get_current_span",
    "add_span_attributes",
    "record_exception",
    "inject_context",
    "extract_context",
    "ExporterType",
    # Metrics
    "MetricsConfig",
    "setup_metrics",
    "shutdown_metrics",
    "get_meter",
    "counter",
    "histogram",
    "gauge",
    "chat_requests_total",
    "chat_latency_seconds",
    "tokens_used_total",
    "llm_errors_total",
    "active_sessions",
    "record_chat_request",
    "record_chat_latency",
    "record_tokens",
    "record_llm_error",
    "set_active_sessions",
    # Middleware
    "TracingMiddleware",
    "MetricsMiddleware",
    "create_observability_middleware",
]
