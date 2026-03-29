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
Tests for OpenTelemetry observability module.

Tests tracing, metrics, and middleware functionality.
"""

from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import patch

import pytest


# Test tracing module
class TestTracingConfig:
    """Tests for TracingConfig."""

    def test_default_config(self):
        """Test default tracing config values."""
        from agentic_brain.observability.tracing import TracingConfig

        config = TracingConfig()
        assert config.enabled is False
        assert config.service_name == "agentic-brain"
        assert config.service_version == "1.0.0"
        assert config.sampler == "always_on"
        assert config.sampler_ratio == 1.0

    def test_config_from_env(self):
        """Test config creation from environment variables."""
        from agentic_brain.observability.tracing import TracingConfig

        with patch.dict(
            os.environ,
            {
                "OTEL_ENABLED": "true",
                "OTEL_SERVICE_NAME": "test-service",
                "OTEL_SERVICE_VERSION": "2.0.0",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
                "OTEL_TRACES_SAMPLER": "traceidratio",
                "OTEL_TRACES_SAMPLER_ARG": "0.5",
            },
        ):
            config = TracingConfig.from_env()
            assert config.enabled is True
            assert config.service_name == "test-service"
            assert config.service_version == "2.0.0"
            assert config.endpoint == "http://localhost:4317"
            assert config.sampler == "traceidratio"
            assert config.sampler_ratio == 0.5

    def test_config_from_env_disabled(self):
        """Test config is disabled by default."""
        from agentic_brain.observability.tracing import TracingConfig

        with patch.dict(os.environ, {}, clear=True):
            config = TracingConfig.from_env()
            assert config.enabled is False


class TestExporterType:
    """Tests for ExporterType enum."""

    def test_exporter_types(self):
        """Test all exporter types are defined."""
        from agentic_brain.observability.tracing import ExporterType

        assert ExporterType.OTLP.value == "otlp"
        assert ExporterType.JAEGER.value == "jaeger"
        assert ExporterType.ZIPKIN.value == "zipkin"
        assert ExporterType.CONSOLE.value == "console"
        assert ExporterType.NONE.value == "none"


class TestNoOpTracer:
    """Tests for NoOp implementations when OTel is unavailable."""

    def test_noop_span(self):
        """Test NoOpSpan works as context manager."""
        from agentic_brain.observability.tracing import _NoOpSpan

        span = _NoOpSpan()

        with span:
            span.set_attribute("key", "value")
            span.add_event("test")
            span.set_status(None)
            span.record_exception(Exception("test"))

        assert span.is_recording() is False

    def test_noop_tracer(self):
        """Test NoOpTracer creates NoOpSpans."""
        from agentic_brain.observability.tracing import _NoOpSpan, _NoOpTracer

        tracer = _NoOpTracer()

        span = tracer.start_span("test")
        assert isinstance(span, _NoOpSpan)

        span = tracer.start_as_current_span("test")
        assert isinstance(span, _NoOpSpan)


class TestTracingSetup:
    """Tests for tracing setup functions."""

    def test_setup_tracing_disabled(self):
        """Test setup returns False when disabled."""
        from agentic_brain.observability.tracing import (
            TracingConfig,
            setup_tracing,
            shutdown_tracing,
        )

        config = TracingConfig(enabled=False)
        result = setup_tracing(config=config)
        assert result is False

        shutdown_tracing()

    def test_get_tracer_without_setup(self):
        """Test get_tracer returns no-op when not set up."""
        from agentic_brain.observability.tracing import get_tracer, shutdown_tracing

        shutdown_tracing()  # Ensure clean state
        tracer = get_tracer("test")

        # Should return something usable (no-op or real tracer)
        assert tracer is not None

    def test_shutdown_tracing_safe(self):
        """Test shutdown is safe to call multiple times."""
        from agentic_brain.observability.tracing import shutdown_tracing

        # Should not raise
        shutdown_tracing()
        shutdown_tracing()
        shutdown_tracing()


class TestTraceDecorators:
    """Tests for trace decorators."""

    def test_trace_decorator_sync(self):
        """Test @trace decorator for sync functions."""
        from agentic_brain.observability.tracing import trace

        @trace
        def my_function(x: int) -> int:
            return x * 2

        result = my_function(5)
        assert result == 10

    def test_trace_decorator_with_name(self):
        """Test @trace decorator with custom name."""
        from agentic_brain.observability.tracing import trace

        @trace(name="custom-span-name")
        def my_function():
            return "done"

        result = my_function()
        assert result == "done"

    def test_trace_decorator_with_attributes(self):
        """Test @trace decorator with attributes."""
        from agentic_brain.observability.tracing import trace

        @trace(attributes={"key": "value", "number": 42})
        def my_function():
            return "done"

        result = my_function()
        assert result == "done"

    def test_trace_decorator_exception(self):
        """Test @trace decorator handles exceptions."""
        from agentic_brain.observability.tracing import trace

        @trace
        def failing_function():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_function()

    @pytest.mark.asyncio
    async def test_trace_async_decorator(self):
        """Test @trace_async decorator for async functions."""
        from agentic_brain.observability.tracing import trace_async

        @trace_async
        async def my_async_function(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * 3

        result = await my_async_function(5)
        assert result == 15

    @pytest.mark.asyncio
    async def test_trace_async_decorator_with_name(self):
        """Test @trace_async decorator with custom name."""
        from agentic_brain.observability.tracing import trace_async

        @trace_async(name="custom-async-span", kind="client")
        async def my_async_function():
            return "async done"

        result = await my_async_function()
        assert result == "async done"

    @pytest.mark.asyncio
    async def test_trace_async_decorator_exception(self):
        """Test @trace_async decorator handles exceptions."""
        from agentic_brain.observability.tracing import trace_async

        @trace_async
        async def failing_async_function():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError, match="async error"):
            await failing_async_function()


class TestSpanHelpers:
    """Tests for span helper functions."""

    def test_get_current_span(self):
        """Test get_current_span returns a span."""
        from agentic_brain.observability.tracing import get_current_span

        span = get_current_span()
        assert span is not None

    def test_add_span_attributes(self):
        """Test add_span_attributes doesn't raise."""
        from agentic_brain.observability.tracing import add_span_attributes

        # Should not raise even when no active span
        add_span_attributes({"key": "value", "number": 42})

    def test_record_exception(self):
        """Test record_exception doesn't raise."""
        from agentic_brain.observability.tracing import record_exception

        # Should not raise
        record_exception(Exception("test"), {"context": "testing"})


class TestContextPropagation:
    """Tests for context propagation."""

    def test_inject_context(self):
        """Test inject_context returns carrier."""
        from agentic_brain.observability.tracing import inject_context

        carrier = {}
        result = inject_context(carrier)

        assert result is carrier

    def test_extract_context(self):
        """Test extract_context handles empty carrier."""
        from agentic_brain.observability.tracing import extract_context

        carrier = {}
        extract_context(carrier)
        # Context may be None or empty context


# Test metrics module
class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_config(self):
        """Test default metrics config values."""
        from agentic_brain.observability.metrics import MetricsConfig

        config = MetricsConfig()
        assert config.enabled is False
        assert config.service_name == "agentic-brain"
        assert config.exporter_type == "otlp"
        assert config.export_interval_millis == 60000

    def test_config_from_env(self):
        """Test config creation from environment."""
        from agentic_brain.observability.metrics import MetricsConfig

        with patch.dict(
            os.environ,
            {
                "OTEL_METRICS_ENABLED": "true",
                "OTEL_SERVICE_NAME": "test-metrics",
                "OTEL_METRICS_EXPORTER": "console",
                "OTEL_METRIC_EXPORT_INTERVAL": "30000",
            },
        ):
            config = MetricsConfig.from_env()
            assert config.enabled is True
            assert config.service_name == "test-metrics"
            assert config.exporter_type == "console"
            assert config.export_interval_millis == 30000


class TestNoOpMetrics:
    """Tests for NoOp metrics implementations."""

    def test_noop_counter(self):
        """Test NoOpCounter works correctly."""
        from agentic_brain.observability.metrics import _NoOpCounter

        counter = _NoOpCounter()
        counter.add(1)
        counter.add(5, {"label": "value"})

    def test_noop_histogram(self):
        """Test NoOpHistogram works correctly."""
        from agentic_brain.observability.metrics import _NoOpHistogram

        histogram = _NoOpHistogram()
        histogram.record(0.5)
        histogram.record(1.0, {"label": "value"})

    def test_noop_meter(self):
        """Test NoOpMeter creates NoOp instruments."""
        from agentic_brain.observability.metrics import (
            _NoOpCounter,
            _NoOpHistogram,
            _NoOpMeter,
        )

        meter = _NoOpMeter()

        counter = meter.create_counter("test")
        assert isinstance(counter, _NoOpCounter)

        histogram = meter.create_histogram("test")
        assert isinstance(histogram, _NoOpHistogram)

        gauge = meter.create_observable_gauge("test")
        assert gauge is None


class TestMetricsSetup:
    """Tests for metrics setup."""

    def test_setup_metrics_disabled(self):
        """Test setup returns False when disabled."""
        from agentic_brain.observability.metrics import (
            MetricsConfig,
            setup_metrics,
            shutdown_metrics,
        )

        config = MetricsConfig(enabled=False)
        result = setup_metrics(config=config)
        assert result is False

        shutdown_metrics()

    def test_get_meter_without_setup(self):
        """Test get_meter returns no-op when not set up."""
        from agentic_brain.observability.metrics import get_meter, shutdown_metrics

        shutdown_metrics()
        meter = get_meter("test")

        assert meter is not None

    def test_shutdown_metrics_safe(self):
        """Test shutdown is safe to call multiple times."""
        from agentic_brain.observability.metrics import shutdown_metrics

        shutdown_metrics()
        shutdown_metrics()
        shutdown_metrics()


class TestMetricCreation:
    """Tests for metric creation helpers."""

    def test_counter_creation(self):
        """Test counter() creates a counter."""
        from agentic_brain.observability.metrics import counter

        c = counter("test_counter", "Test counter")
        assert c is not None
        c.add(1)

    def test_histogram_creation(self):
        """Test histogram() creates a histogram."""
        from agentic_brain.observability.metrics import histogram

        h = histogram("test_histogram", "Test histogram", "s")
        assert h is not None
        h.record(0.5)


class TestPreDefinedMetrics:
    """Tests for pre-defined metrics."""

    def test_chat_requests_total(self):
        """Test chat_requests_total accessor."""
        from agentic_brain.observability.metrics import chat_requests_total

        counter = chat_requests_total()
        assert counter is not None
        counter.add(1)

    def test_chat_latency_seconds(self):
        """Test chat_latency_seconds accessor."""
        from agentic_brain.observability.metrics import chat_latency_seconds

        histogram = chat_latency_seconds()
        assert histogram is not None
        histogram.record(0.5)

    def test_tokens_used_total(self):
        """Test tokens_used_total accessor."""
        from agentic_brain.observability.metrics import tokens_used_total

        counter = tokens_used_total()
        assert counter is not None
        counter.add(100)

    def test_llm_errors_total(self):
        """Test llm_errors_total accessor."""
        from agentic_brain.observability.metrics import llm_errors_total

        counter = llm_errors_total()
        assert counter is not None
        counter.add(1)

    def test_active_sessions(self):
        """Test active_sessions accessor."""
        from agentic_brain.observability.metrics import active_sessions

        # May be None if not initialized
        active_sessions()


class TestMetricRecording:
    """Tests for metric recording convenience functions."""

    def test_record_chat_request(self):
        """Test record_chat_request function."""
        from agentic_brain.observability.metrics import record_chat_request

        # Should not raise
        record_chat_request(provider="openai", model="gpt-4", status="success")
        record_chat_request(provider="ollama", model="llama3", status="error")

    def test_record_chat_latency(self):
        """Test record_chat_latency function."""
        from agentic_brain.observability.metrics import record_chat_latency

        # Should not raise
        record_chat_latency(0.5, provider="openai", model="gpt-4")
        record_chat_latency(1.2, provider="ollama", model="llama3")

    def test_record_tokens(self):
        """Test record_tokens function."""
        from agentic_brain.observability.metrics import record_tokens

        # Should not raise
        record_tokens(150, token_type="input", provider="openai")
        record_tokens(200, token_type="output", provider="openai")
        record_tokens(350, token_type="total", provider="openai")

    def test_record_llm_error(self):
        """Test record_llm_error function."""
        from agentic_brain.observability.metrics import record_llm_error

        # Should not raise
        record_llm_error("timeout", provider="openai", model="gpt-4")
        record_llm_error("rate_limit", provider="anthropic", model="claude")

    def test_set_active_sessions(self):
        """Test set_active_sessions function."""
        from agentic_brain.observability.metrics import set_active_sessions

        # Should not raise
        set_active_sessions(0)
        set_active_sessions(10)
        set_active_sessions(100)


class TestTimedDecorators:
    """Tests for timed decorators."""

    def test_timed_decorator(self):
        """Test @timed decorator."""
        from agentic_brain.observability.metrics import timed

        @timed("test_duration", "Test duration")
        def fast_function():
            return "done"

        result = fast_function()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timed_async_decorator(self):
        """Test @timed_async decorator."""
        from agentic_brain.observability.metrics import timed_async

        @timed_async("test_async_duration", "Test async duration")
        async def fast_async_function():
            return "async done"

        result = await fast_async_function()
        assert result == "async done"


# Test middleware module
class TestTracingMiddleware:
    """Tests for TracingMiddleware."""

    @pytest.mark.asyncio
    async def test_middleware_excludes_health(self):
        """Test middleware excludes health endpoints."""
        pytest.importorskip("starlette")

        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        from agentic_brain.observability.middleware import TracingMiddleware

        async def health(request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/health", health)])
        app.add_middleware(TracingMiddleware)

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_traces_request(self):
        """Test middleware traces non-excluded requests."""
        pytest.importorskip("starlette")

        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        from agentic_brain.observability.middleware import TracingMiddleware

        async def chat(request):
            return JSONResponse({"message": "hello"})

        app = Starlette(routes=[Route("/chat", chat)])
        app.add_middleware(TracingMiddleware)

        client = TestClient(app)
        response = client.get("/chat")
        assert response.status_code == 200


class TestMetricsMiddleware:
    """Tests for MetricsMiddleware."""

    @pytest.mark.asyncio
    async def test_middleware_records_metrics(self):
        """Test middleware records request metrics."""
        pytest.importorskip("starlette")

        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        from agentic_brain.observability.middleware import MetricsMiddleware

        async def endpoint(request):
            return JSONResponse({"data": "test"})

        app = Starlette(routes=[Route("/api/test", endpoint)])
        app.add_middleware(MetricsMiddleware)

        client = TestClient(app)
        response = client.get("/api/test")
        assert response.status_code == 200


class TestObservabilityHelper:
    """Tests for create_observability_middleware."""

    def test_create_observability_middleware(self):
        """Test create_observability_middleware adds all middleware."""
        pytest.importorskip("fastapi")

        from fastapi import FastAPI

        from agentic_brain.observability.middleware import (
            create_observability_middleware,
        )

        app = FastAPI()

        # Should not raise
        create_observability_middleware(
            app,
            tracing=True,
            metrics=True,
            chat_metrics=True,
        )

    def test_create_observability_middleware_selective(self):
        """Test create_observability_middleware with selective options."""
        pytest.importorskip("fastapi")

        from fastapi import FastAPI

        from agentic_brain.observability.middleware import (
            create_observability_middleware,
        )

        app = FastAPI()

        # Only tracing
        create_observability_middleware(
            app,
            tracing=True,
            metrics=False,
            chat_metrics=False,
        )


# Test package exports
class TestPackageExports:
    """Tests for package-level exports."""

    def test_tracing_exports(self):
        """Test tracing exports are available."""
        from agentic_brain.observability import (
            TracingConfig,
            get_tracer,
            setup_tracing,
            shutdown_tracing,
            trace,
            trace_async,
        )

        assert TracingConfig is not None
        assert setup_tracing is not None
        assert shutdown_tracing is not None
        assert get_tracer is not None
        assert trace is not None
        assert trace_async is not None

    def test_metrics_exports(self):
        """Test metrics exports are available."""
        from agentic_brain.observability import (
            MetricsConfig,
            setup_metrics,
            shutdown_metrics,
        )

        assert MetricsConfig is not None
        assert setup_metrics is not None
        assert shutdown_metrics is not None

    def test_middleware_exports(self):
        """Test middleware exports are available."""
        from agentic_brain.observability import (
            MetricsMiddleware,
            TracingMiddleware,
            create_observability_middleware,
        )

        assert TracingMiddleware is not None
        assert MetricsMiddleware is not None
        assert create_observability_middleware is not None


# Integration tests
class TestIntegration:
    """Integration tests for observability."""

    def test_full_setup_and_teardown(self):
        """Test complete setup and teardown cycle."""
        from agentic_brain.observability import (
            MetricsConfig,
            TracingConfig,
            setup_metrics,
            setup_tracing,
            shutdown_metrics,
            shutdown_tracing,
        )

        # Setup (disabled - for testing without OTEL deps)
        tracing_config = TracingConfig(enabled=False)
        metrics_config = MetricsConfig(enabled=False)

        setup_tracing(config=tracing_config)
        setup_metrics(config=metrics_config)

        # Use
        from agentic_brain.observability import record_chat_request, trace

        @trace
        def test_function():
            record_chat_request(provider="test", model="test")
            return "ok"

        result = test_function()
        assert result == "ok"

        # Teardown
        shutdown_tracing()
        shutdown_metrics()

    @pytest.mark.asyncio
    async def test_async_integration(self):
        """Test async tracing integration."""
        from agentic_brain.observability import (
            record_chat_latency,
            trace_async,
        )

        @trace_async(name="integration-test")
        async def async_operation():
            start = time.perf_counter()
            await asyncio.sleep(0.01)
            duration = time.perf_counter() - start
            record_chat_latency(duration, provider="test", model="test")
            return duration

        duration = await async_operation()
        assert duration >= 0.01


class TestEndToEnd:
    """End-to-end tests with FastAPI."""

    @pytest.mark.asyncio
    async def test_fastapi_with_observability(self):
        """Test FastAPI app with full observability."""
        pytest.importorskip("fastapi")

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from agentic_brain.observability import (
            MetricsConfig,
            TracingConfig,
            record_chat_request,
            setup_metrics,
            setup_tracing,
            shutdown_metrics,
            shutdown_tracing,
            trace_async,
        )
        from agentic_brain.observability.middleware import (
            create_observability_middleware,
        )

        # Setup (disabled for testing)
        setup_tracing(config=TracingConfig(enabled=False))
        setup_metrics(config=MetricsConfig(enabled=False))

        app = FastAPI()
        create_observability_middleware(app)

        @app.get("/chat")
        @trace_async
        async def chat():
            record_chat_request(provider="test", model="test", status="success")
            return {"message": "hello"}

        client = TestClient(app)
        response = client.get("/chat")

        assert response.status_code == 200
        assert response.json() == {"message": "hello"}

        # Cleanup
        shutdown_tracing()
        shutdown_metrics()
