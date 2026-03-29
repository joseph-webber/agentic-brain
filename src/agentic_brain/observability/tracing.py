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
OpenTelemetry tracing for agentic-brain.

Provides distributed tracing with support for OTLP, Jaeger, and Zipkin exporters.
Zero-config by default (disabled), opt-in via environment variables.

Example:
    >>> from agentic_brain.observability.tracing import setup_tracing, trace
    >>>
    >>> # Setup with explicit config
    >>> setup_tracing(
    ...     service_name="my-agent",
    ...     endpoint="http://jaeger:4317",
    ...     exporter_type=ExporterType.OTLP
    ... )
    >>>
    >>> @trace
    >>> def my_function():
    ...     pass
    >>>
    >>> @trace_async
    >>> async def my_async_function():
    ...     pass
"""

from __future__ import annotations

import functools
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# Type variables for decorators
F = TypeVar("F", bound=Callable[..., Any])

# Check if OpenTelemetry is available
_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.propagate import extract, inject, set_global_textmap
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import Span, TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    _OTEL_AVAILABLE = True
except ImportError:
    otel_trace = None
    TracerProvider = None
    Span = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None
    Resource = None
    SERVICE_NAME = None
    Status = None
    StatusCode = None
    SpanKind = None
    TraceContextTextMapPropagator = None
    set_global_textmap = None
    inject = None
    extract = None


class ExporterType(Enum):
    """Supported trace exporters."""

    OTLP = "otlp"
    JAEGER = "jaeger"
    ZIPKIN = "zipkin"
    CONSOLE = "console"
    NONE = "none"


@dataclass
class TracingConfig:
    """Tracing configuration."""

    # Core settings
    enabled: bool = False
    service_name: str = "agentic-brain"
    service_version: str = "1.0.0"

    # Exporter settings
    exporter_type: ExporterType = ExporterType.OTLP
    endpoint: str | None = None

    # OTLP specific
    otlp_headers: dict[str, str] = field(default_factory=dict)
    otlp_insecure: bool = True

    # Sampling
    sampler: str = "always_on"  # always_on, always_off, traceidratio
    sampler_ratio: float = 1.0

    # Resource attributes
    attributes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> TracingConfig:
        """Create config from environment variables."""
        enabled = os.getenv("OTEL_ENABLED", "false").lower() in ("true", "1", "yes")

        exporter_str = os.getenv("OTEL_EXPORTER", "otlp").lower()
        try:
            exporter_type = ExporterType(exporter_str)
        except ValueError:
            exporter_type = ExporterType.OTLP

        return cls(
            enabled=enabled,
            service_name=os.getenv("OTEL_SERVICE_NAME", "agentic-brain"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            exporter_type=exporter_type,
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            sampler=os.getenv("OTEL_TRACES_SAMPLER", "always_on"),
            sampler_ratio=float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0")),
        )


# Global state
_tracer_provider: Any | None = None
_tracer: Any | None = None
_config: TracingConfig | None = None


def setup_tracing(
    service_name: str | None = None,
    endpoint: str | None = None,
    exporter_type: ExporterType | None = None,
    config: TracingConfig | None = None,
    **kwargs,
) -> bool:
    """
    Set up OpenTelemetry tracing.

    Args:
        service_name: Service name for traces
        endpoint: Exporter endpoint (e.g., http://jaeger:4317)
        exporter_type: Type of exporter to use
        config: Full TracingConfig object (overrides other args)
        **kwargs: Additional config options

    Returns:
        True if tracing was set up successfully

    Example:
        >>> setup_tracing(
        ...     service_name="my-agent",
        ...     endpoint="http://localhost:4317"
        ... )
    """
    global _tracer_provider, _tracer, _config

    if not _OTEL_AVAILABLE:
        logger.debug("OpenTelemetry not available - tracing disabled")
        return False

    # Build config
    if config is None:
        config = TracingConfig.from_env()

    # Override with explicit args
    if service_name:
        config.service_name = service_name
    if endpoint:
        config.endpoint = endpoint
        config.enabled = True  # Auto-enable if endpoint provided
    if exporter_type:
        config.exporter_type = exporter_type

    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    _config = config

    if not config.enabled:
        logger.debug("Tracing disabled via config")
        return False

    try:
        # Create resource
        resource_attrs = {
            SERVICE_NAME: config.service_name,
            "service.version": config.service_version,
        }
        resource_attrs.update(config.attributes)
        resource = Resource.create(resource_attrs)

        # Create sampler
        sampler = _create_sampler(config)

        # Create provider
        _tracer_provider = TracerProvider(resource=resource, sampler=sampler)

        # Create exporter
        exporter = _create_exporter(config)
        if exporter:
            processor = BatchSpanProcessor(exporter)
            _tracer_provider.add_span_processor(processor)

        # Set global provider
        otel_trace.set_tracer_provider(_tracer_provider)

        # Set up context propagation
        propagator = TraceContextTextMapPropagator()
        set_global_textmap(propagator)

        # Create tracer
        _tracer = _tracer_provider.get_tracer(
            config.service_name,
            config.service_version,
        )

        logger.info(
            f"Tracing enabled: service={config.service_name}, "
            f"exporter={config.exporter_type.value}, endpoint={config.endpoint}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to set up tracing: {e}")
        return False


def _create_sampler(config: TracingConfig) -> Any:
    """Create a sampler based on config."""
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        TraceIdRatioBased,
    )

    sampler_name = config.sampler.lower().replace("-", "_")

    if sampler_name == "always_off":
        return ALWAYS_OFF
    elif sampler_name == "traceidratio":
        return TraceIdRatioBased(config.sampler_ratio)
    else:
        return ALWAYS_ON


def _create_exporter(config: TracingConfig) -> Any:
    """Create a trace exporter based on config."""
    if config.exporter_type == ExporterType.CONSOLE:
        return ConsoleSpanExporter()

    if config.exporter_type == ExporterType.NONE:
        return None

    if config.exporter_type == ExporterType.OTLP:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            return OTLPSpanExporter(
                endpoint=config.endpoint,
                insecure=config.otlp_insecure,
                headers=config.otlp_headers or None,
            )
        except ImportError:
            logger.warning("OTLP exporter not available, falling back to console")
            return ConsoleSpanExporter()

    if config.exporter_type == ExporterType.JAEGER:
        try:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter

            # Parse endpoint
            host = "localhost"
            port = 6831
            if config.endpoint:
                parts = (
                    config.endpoint.replace("http://", "")
                    .replace("https://", "")
                    .split(":")
                )
                host = parts[0]
                if len(parts) > 1:
                    port = int(parts[1].split("/")[0])

            return JaegerExporter(
                agent_host_name=host,
                agent_port=port,
            )
        except ImportError:
            logger.warning("Jaeger exporter not available, falling back to console")
            return ConsoleSpanExporter()

    if config.exporter_type == ExporterType.ZIPKIN:
        try:
            from opentelemetry.exporter.zipkin.json import ZipkinExporter

            endpoint = config.endpoint or "http://localhost:9411/api/v2/spans"
            return ZipkinExporter(endpoint=endpoint)
        except ImportError:
            logger.warning("Zipkin exporter not available, falling back to console")
            return ConsoleSpanExporter()

    return None


def shutdown_tracing() -> None:
    """Shutdown tracing and flush pending spans."""
    global _tracer_provider, _tracer

    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
            logger.info("Tracing shutdown complete")
        except Exception as e:
            logger.error(f"Error during tracing shutdown: {e}")
        finally:
            _tracer_provider = None
            _tracer = None


def get_tracer(name: str | None = None) -> Any:
    """
    Get a tracer instance.

    Args:
        name: Optional tracer name (defaults to service name)

    Returns:
        Tracer instance or NoOpTracer if tracing not set up
    """
    if _tracer is not None:
        return _tracer

    if _OTEL_AVAILABLE:
        # Return a tracer from the global provider (may be no-op)
        return otel_trace.get_tracer(name or "agentic-brain")

    # Return a no-op tracer
    return _NoOpTracer()


class _NoOpSpan:
    """No-op span for when tracing is disabled."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(
        self, exception: Exception, attributes: dict | None = None
    ) -> None:
        pass

    def is_recording(self) -> bool:
        return False


class _NoOpTracer:
    """No-op tracer for when tracing is disabled."""

    def start_span(self, name: str, **kwargs) -> _NoOpSpan:
        return _NoOpSpan()

    def start_as_current_span(self, name: str, **kwargs):
        return _NoOpSpan()


def trace(
    _func: Callable | None = None,
    *,
    name: str | None = None,
    kind: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to trace a synchronous function.

    Can be used with or without parentheses:
        @trace
        def my_function(): ...

        @trace(name="custom")
        def my_function(): ...

    Args:
        name: Span name (defaults to function name)
        kind: Span kind (INTERNAL, CLIENT, SERVER, PRODUCER, CONSUMER)
        attributes: Additional span attributes

    Returns:
        Decorated function

    Example:
        >>> @trace
        ... def my_function():
        ...     pass
        >>>
        >>> @trace(name="custom-name", attributes={"key": "value"})
        ... def another_function():
        ...     pass
    """

    def decorator(func: F) -> F:
        span_name = name or func.__name__
        span_kind = _get_span_kind(kind)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(
                span_name,
                kind=span_kind,
                attributes=attributes,
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    if hasattr(span, "record_exception"):
                        span.record_exception(e)
                    if hasattr(span, "set_status") and _OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper  # type: ignore

    # Handle @trace without parentheses
    if _func is not None:
        return decorator(_func)
    return decorator


def trace_async(
    _func: Callable | None = None,
    *,
    name: str | None = None,
    kind: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to trace an async function.

    Can be used with or without parentheses:
        @trace_async
        async def my_function(): ...

        @trace_async(name="custom")
        async def my_function(): ...

    Args:
        name: Span name (defaults to function name)
        kind: Span kind (INTERNAL, CLIENT, SERVER, PRODUCER, CONSUMER)
        attributes: Additional span attributes

    Returns:
        Decorated async function

    Example:
        >>> @trace_async
        ... async def my_async_function():
        ...     pass
    """

    def decorator(func: F) -> F:
        span_name = name or func.__name__
        span_kind = _get_span_kind(kind)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(
                span_name,
                kind=span_kind,
                attributes=attributes,
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    if hasattr(span, "record_exception"):
                        span.record_exception(e)
                    if hasattr(span, "set_status") and _OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper  # type: ignore

    # Handle @trace_async without parentheses
    if _func is not None:
        return decorator(_func)
    return decorator


def _get_span_kind(kind: str | None) -> Any:
    """Convert string span kind to SpanKind enum."""
    if not _OTEL_AVAILABLE or kind is None:
        return None

    kind_map = {
        "internal": SpanKind.INTERNAL,
        "client": SpanKind.CLIENT,
        "server": SpanKind.SERVER,
        "producer": SpanKind.PRODUCER,
        "consumer": SpanKind.CONSUMER,
    }
    return kind_map.get(kind.lower(), SpanKind.INTERNAL)


def get_current_span() -> Any:
    """
    Get the current active span.

    Returns:
        Current span or NoOpSpan if none active
    """
    if _OTEL_AVAILABLE:
        return otel_trace.get_current_span()
    return _NoOpSpan()


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """
    Add attributes to the current span.

    Args:
        attributes: Key-value pairs to add

    Example:
        >>> add_span_attributes({"user.id": "123", "request.type": "chat"})
    """
    span = get_current_span()
    for key, value in attributes.items():
        span.set_attribute(key, value)


def record_exception(
    exception: Exception, attributes: dict[str, Any] | None = None
) -> None:
    """
    Record an exception on the current span.

    Args:
        exception: The exception to record
        attributes: Additional attributes to add
    """
    span = get_current_span()
    if hasattr(span, "record_exception"):
        span.record_exception(exception, attributes=attributes)
    if hasattr(span, "set_status") and _OTEL_AVAILABLE:
        span.set_status(Status(StatusCode.ERROR, str(exception)))


def inject_context(carrier: dict[str, str]) -> dict[str, str]:
    """
    Inject trace context into a carrier dict (for propagation).

    Args:
        carrier: Dictionary to inject context into

    Returns:
        The carrier with context injected

    Example:
        >>> headers = {}
        >>> inject_context(headers)
        >>> # headers now contains traceparent, tracestate
        >>> requests.get(url, headers=headers)
    """
    if _OTEL_AVAILABLE and inject is not None:
        inject(carrier)
    return carrier


def extract_context(carrier: dict[str, str]) -> Any:
    """
    Extract trace context from a carrier dict.

    Args:
        carrier: Dictionary containing trace context

    Returns:
        Extracted context

    Example:
        >>> context = extract_context(request.headers)
        >>> with tracer.start_span("handle", context=context):
        ...     process_request()
    """
    if _OTEL_AVAILABLE and extract is not None:
        return extract(carrier)
    return None
