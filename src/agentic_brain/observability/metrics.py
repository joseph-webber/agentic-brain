# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
OpenTelemetry metrics for agentic-brain.

Provides metric collection with pre-defined metrics for chat, tokens, and errors.
Zero-config by default (disabled), opt-in via environment variables.

Example:
    >>> from agentic_brain.observability.metrics import setup_metrics, record_chat_request
    >>>
    >>> setup_metrics(service_name="my-agent")
    >>>
    >>> # Record a chat request
    >>> record_chat_request(provider="openai", model="gpt-4", status="success")
    >>>
    >>> # Record latency
    >>> record_chat_latency(0.5, provider="openai", model="gpt-4")
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Check if OpenTelemetry is available
_OTEL_AVAILABLE = False
try:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    _OTEL_AVAILABLE = True
except ImportError:
    otel_metrics = None
    MeterProvider = None
    PeriodicExportingMetricReader = None
    ConsoleMetricExporter = None
    Resource = None
    SERVICE_NAME = None


@dataclass
class MetricsConfig:
    """Metrics configuration."""

    # Core settings
    enabled: bool = False
    service_name: str = "agentic-brain"
    service_version: str = "1.0.0"

    # Exporter settings
    exporter_type: str = "otlp"  # otlp, console, none
    endpoint: str | None = None

    # Export interval
    export_interval_millis: int = 60000  # 1 minute

    # Resource attributes
    attributes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> MetricsConfig:
        """Create config from environment variables."""
        enabled = os.getenv(
            "OTEL_METRICS_ENABLED", os.getenv("OTEL_ENABLED", "false")
        ).lower() in ("true", "1", "yes")

        return cls(
            enabled=enabled,
            service_name=os.getenv("OTEL_SERVICE_NAME", "agentic-brain"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            exporter_type=os.getenv("OTEL_METRICS_EXPORTER", "otlp").lower(),
            endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            ),
            export_interval_millis=int(
                os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "60000")
            ),
        )


# Global state
_meter_provider: Any | None = None
_meter: Any | None = None
_config: MetricsConfig | None = None

# Pre-defined metrics (initialized lazily)
_chat_requests_counter: Any | None = None
_chat_latency_histogram: Any | None = None
_tokens_counter: Any | None = None
_llm_errors_counter: Any | None = None
_active_sessions_gauge: Any | None = None
_active_sessions_value: int = 0
_gauge_lock = threading.Lock()


def setup_metrics(
    service_name: str | None = None,
    endpoint: str | None = None,
    exporter_type: str | None = None,
    config: MetricsConfig | None = None,
    **kwargs,
) -> bool:
    """
    Set up OpenTelemetry metrics.

    Args:
        service_name: Service name for metrics
        endpoint: Exporter endpoint
        exporter_type: Type of exporter (otlp, console, none)
        config: Full MetricsConfig object (overrides other args)
        **kwargs: Additional config options

    Returns:
        True if metrics were set up successfully

    Example:
        >>> setup_metrics(
        ...     service_name="my-agent",
        ...     endpoint="http://localhost:4317"
        ... )
    """
    global _meter_provider, _meter, _config

    if not _OTEL_AVAILABLE:
        logger.debug("OpenTelemetry not available - metrics disabled")
        return False

    # Build config
    if config is None:
        config = MetricsConfig.from_env()

    # Override with explicit args
    if service_name:
        config.service_name = service_name
    if endpoint:
        config.endpoint = endpoint
        config.enabled = True
    if exporter_type:
        config.exporter_type = exporter_type

    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    _config = config

    if not config.enabled:
        logger.debug("Metrics disabled via config")
        return False

    try:
        # Create resource
        resource_attrs = {
            SERVICE_NAME: config.service_name,
            "service.version": config.service_version,
        }
        resource_attrs.update(config.attributes)
        resource = Resource.create(resource_attrs)

        # Create exporter
        exporter = _create_metrics_exporter(config)
        if exporter is None:
            logger.debug("No metrics exporter configured")
            return False

        # Create reader
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=config.export_interval_millis,
        )

        # Create provider
        _meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[reader],
        )

        # Set global provider
        otel_metrics.set_meter_provider(_meter_provider)

        # Create meter
        _meter = _meter_provider.get_meter(
            config.service_name,
            config.service_version,
        )

        # Initialize pre-defined metrics
        _initialize_metrics()

        logger.info(
            f"Metrics enabled: service={config.service_name}, "
            f"exporter={config.exporter_type}, endpoint={config.endpoint}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to set up metrics: {e}")
        return False


def _create_metrics_exporter(config: MetricsConfig) -> Any:
    """Create a metrics exporter based on config."""
    if config.exporter_type == "console":
        return ConsoleMetricExporter()

    if config.exporter_type == "none":
        return None

    if config.exporter_type == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )

            return OTLPMetricExporter(
                endpoint=config.endpoint,
                insecure=True,
            )
        except ImportError:
            logger.warning(
                "OTLP metrics exporter not available, falling back to console"
            )
            return ConsoleMetricExporter()

    return None


def _initialize_metrics() -> None:
    """Initialize pre-defined metrics."""
    global _chat_requests_counter, _chat_latency_histogram
    global _tokens_counter, _llm_errors_counter, _active_sessions_gauge

    if _meter is None:
        return

    # Chat requests counter
    _chat_requests_counter = _meter.create_counter(
        name="chat_requests_total",
        description="Total number of chat requests",
        unit="1",
    )

    # Chat latency histogram
    _chat_latency_histogram = _meter.create_histogram(
        name="chat_latency_seconds",
        description="Chat request latency in seconds",
        unit="s",
    )

    # Tokens counter
    _tokens_counter = _meter.create_counter(
        name="tokens_used_total",
        description="Total number of tokens used",
        unit="1",
    )

    # LLM errors counter
    _llm_errors_counter = _meter.create_counter(
        name="llm_errors_total",
        description="Total number of LLM errors",
        unit="1",
    )

    # Active sessions gauge (using observable gauge)
    _active_sessions_gauge = _meter.create_observable_gauge(
        name="active_sessions",
        description="Number of active sessions",
        unit="1",
        callbacks=[_get_active_sessions_callback],
    )


def _get_active_sessions_callback(options) -> list:
    """Callback for observable gauge."""
    global _active_sessions_value
    try:
        from opentelemetry.metrics import Observation

        return [Observation(_active_sessions_value)]
    except ImportError:
        return []


def shutdown_metrics() -> None:
    """Shutdown metrics and flush pending data."""
    global _meter_provider, _meter

    if _meter_provider is not None:
        try:
            _meter_provider.shutdown()
            logger.info("Metrics shutdown complete")
        except Exception as e:
            logger.error(f"Error during metrics shutdown: {e}")
        finally:
            _meter_provider = None
            _meter = None


def get_meter(name: str | None = None) -> Any:
    """
    Get a meter instance.

    Args:
        name: Optional meter name

    Returns:
        Meter instance or NoOpMeter if metrics not set up
    """
    if _meter is not None:
        return _meter

    if _OTEL_AVAILABLE:
        return otel_metrics.get_meter(name or "agentic-brain")

    return _NoOpMeter()


class _NoOpCounter:
    """No-op counter for when metrics are disabled."""

    def add(self, amount: int = 1, attributes: dict | None = None) -> None:
        pass


class _NoOpHistogram:
    """No-op histogram for when metrics are disabled."""

    def record(self, amount: float, attributes: dict | None = None) -> None:
        pass


class _NoOpMeter:
    """No-op meter for when metrics are disabled."""

    def create_counter(self, name: str, **kwargs) -> _NoOpCounter:
        return _NoOpCounter()

    def create_histogram(self, name: str, **kwargs) -> _NoOpHistogram:
        return _NoOpHistogram()

    def create_up_down_counter(self, name: str, **kwargs) -> _NoOpCounter:
        return _NoOpCounter()

    def create_observable_gauge(self, name: str, **kwargs) -> None:
        return None


def counter(
    name: str,
    description: str = "",
    unit: str = "1",
) -> Any:
    """
    Create a counter metric.

    Args:
        name: Metric name
        description: Metric description
        unit: Metric unit

    Returns:
        Counter instance

    Example:
        >>> my_counter = counter("my_counter", "My counter description")
        >>> my_counter.add(1, {"label": "value"})
    """
    meter = get_meter()
    if hasattr(meter, "create_counter"):
        return meter.create_counter(name=name, description=description, unit=unit)
    return _NoOpCounter()


def histogram(
    name: str,
    description: str = "",
    unit: str = "s",
) -> Any:
    """
    Create a histogram metric.

    Args:
        name: Metric name
        description: Metric description
        unit: Metric unit

    Returns:
        Histogram instance

    Example:
        >>> my_histogram = histogram("request_duration", "Request duration", "s")
        >>> my_histogram.record(0.5, {"endpoint": "/chat"})
    """
    meter = get_meter()
    if hasattr(meter, "create_histogram"):
        return meter.create_histogram(name=name, description=description, unit=unit)
    return _NoOpHistogram()


def gauge(
    name: str,
    description: str = "",
    unit: str = "1",
    callback: Callable | None = None,
) -> Any:
    """
    Create an observable gauge metric.

    Args:
        name: Metric name
        description: Metric description
        unit: Metric unit
        callback: Callback to get current value

    Returns:
        Observable gauge instance

    Example:
        >>> def get_queue_size(options):
        ...     return [Observation(len(queue))]
        >>> my_gauge = gauge("queue_size", "Queue size", callback=get_queue_size)
    """
    meter = get_meter()
    if hasattr(meter, "create_observable_gauge") and callback:
        return meter.create_observable_gauge(
            name=name,
            description=description,
            unit=unit,
            callbacks=[callback],
        )
    return None


# Pre-defined metrics accessors


def chat_requests_total() -> Any:
    """Get the chat_requests_total counter."""
    global _chat_requests_counter
    if _chat_requests_counter is None:
        return _NoOpCounter()
    return _chat_requests_counter


def chat_latency_seconds() -> Any:
    """Get the chat_latency_seconds histogram."""
    global _chat_latency_histogram
    if _chat_latency_histogram is None:
        return _NoOpHistogram()
    return _chat_latency_histogram


def tokens_used_total() -> Any:
    """Get the tokens_used_total counter."""
    global _tokens_counter
    if _tokens_counter is None:
        return _NoOpCounter()
    return _tokens_counter


def llm_errors_total() -> Any:
    """Get the llm_errors_total counter."""
    global _llm_errors_counter
    if _llm_errors_counter is None:
        return _NoOpCounter()
    return _llm_errors_counter


def active_sessions() -> Any:
    """Get the active_sessions gauge."""
    global _active_sessions_gauge
    return _active_sessions_gauge


# Convenience functions for recording metrics


def record_chat_request(
    provider: str = "unknown",
    model: str = "unknown",
    status: str = "success",
    attributes: dict[str, str] | None = None,
) -> None:
    """
    Record a chat request.

    Args:
        provider: LLM provider name
        model: Model name
        status: Request status (success, error)
        attributes: Additional attributes

    Example:
        >>> record_chat_request(provider="openai", model="gpt-4", status="success")
    """
    attrs = {
        "provider": provider,
        "model": model,
        "status": status,
    }
    if attributes:
        attrs.update(attributes)

    chat_requests_total().add(1, attrs)


def record_chat_latency(
    duration_seconds: float,
    provider: str = "unknown",
    model: str = "unknown",
    attributes: dict[str, str] | None = None,
) -> None:
    """
    Record chat latency.

    Args:
        duration_seconds: Request duration in seconds
        provider: LLM provider name
        model: Model name
        attributes: Additional attributes

    Example:
        >>> record_chat_latency(0.5, provider="openai", model="gpt-4")
    """
    attrs = {
        "provider": provider,
        "model": model,
    }
    if attributes:
        attrs.update(attributes)

    chat_latency_seconds().record(duration_seconds, attrs)


def record_tokens(
    count: int,
    token_type: str = "total",
    provider: str = "unknown",
    model: str = "unknown",
    attributes: dict[str, str] | None = None,
) -> None:
    """
    Record token usage.

    Args:
        count: Number of tokens
        token_type: Type of tokens (input, output, total)
        provider: LLM provider name
        model: Model name
        attributes: Additional attributes

    Example:
        >>> record_tokens(150, token_type="input", provider="openai")
        >>> record_tokens(200, token_type="output", provider="openai")
    """
    attrs = {
        "token_type": token_type,
        "provider": provider,
        "model": model,
    }
    if attributes:
        attrs.update(attributes)

    tokens_used_total().add(count, attrs)


def record_llm_error(
    error_type: str,
    provider: str = "unknown",
    model: str = "unknown",
    attributes: dict[str, str] | None = None,
) -> None:
    """
    Record an LLM error.

    Args:
        error_type: Type of error (timeout, rate_limit, api_error, etc.)
        provider: LLM provider name
        model: Model name
        attributes: Additional attributes

    Example:
        >>> record_llm_error("rate_limit", provider="openai", model="gpt-4")
    """
    attrs = {
        "error_type": error_type,
        "provider": provider,
        "model": model,
    }
    if attributes:
        attrs.update(attributes)

    llm_errors_total().add(1, attrs)


def set_active_sessions(count: int) -> None:
    """
    Set the number of active sessions.

    Args:
        count: Number of active sessions

    Example:
        >>> set_active_sessions(42)
    """
    global _active_sessions_value
    with _gauge_lock:
        _active_sessions_value = count


def timed(
    histogram_name: str,
    description: str = "",
    attributes: dict[str, str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to time a function and record to a histogram.

    Args:
        histogram_name: Name of the histogram metric
        description: Metric description
        attributes: Additional attributes

    Returns:
        Decorated function

    Example:
        >>> @timed("process_duration_seconds", "Processing duration")
        ... def process_data():
        ...     # do work
        ...     pass
    """
    hist = histogram(histogram_name, description, unit="s")

    def decorator(func: F) -> F:
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                hist.record(duration, attributes)

        return wrapper  # type: ignore

    return decorator


def timed_async(
    histogram_name: str,
    description: str = "",
    attributes: dict[str, str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to time an async function and record to a histogram.

    Args:
        histogram_name: Name of the histogram metric
        description: Metric description
        attributes: Additional attributes

    Returns:
        Decorated async function
    """
    hist = histogram(histogram_name, description, unit="s")

    def decorator(func: F) -> F:
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                hist.record(duration, attributes)

        return wrapper  # type: ignore

    return decorator
