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
FastAPI middleware for OpenTelemetry observability.

Provides automatic tracing and metrics for incoming HTTP requests.

Example:
    >>> from fastapi import FastAPI
    >>> from agentic_brain.observability.middleware import (
    ...     TracingMiddleware,
    ...     MetricsMiddleware,
    ...     create_observability_middleware,
    ... )
    >>>
    >>> app = FastAPI()
    >>> app.add_middleware(TracingMiddleware)
    >>> app.add_middleware(MetricsMiddleware)
    >>>
    >>> # Or use the combined helper
    >>> create_observability_middleware(app)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Check if required dependencies are available
_STARLETTE_AVAILABLE = False
try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp

    _STARLETTE_AVAILABLE = True
except ImportError:
    BaseHTTPMiddleware = object
    Request = object
    Response = object
    ASGIApp = object

# Import observability components
from .metrics import (
    record_chat_latency,
    record_chat_request,
)
from .tracing import (
    _OTEL_AVAILABLE,
    extract_context,
    get_tracer,
    inject_context,
    record_exception,
)


class TracingMiddleware(BaseHTTPMiddleware if _STARLETTE_AVAILABLE else object):
    """
    FastAPI middleware for automatic request tracing.

    Creates spans for each incoming request with:
    - HTTP method and path
    - Status code
    - Request/response headers
    - Error information

    Also propagates trace context to responses.

    Example:
        >>> from fastapi import FastAPI
        >>> from agentic_brain.observability.middleware import TracingMiddleware
        >>>
        >>> app = FastAPI()
        >>> app.add_middleware(TracingMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        service_name: str = "agentic-brain",
        excluded_paths: list[str] | None = None,
        record_request_headers: bool = False,
        record_response_headers: bool = False,
    ):
        """
        Initialize tracing middleware.

        Args:
            app: ASGI application
            service_name: Service name for spans
            excluded_paths: Paths to exclude from tracing (e.g., ["/health", "/metrics"])
            record_request_headers: Include request headers in span attributes
            record_response_headers: Include response headers in span attributes
        """
        if _STARLETTE_AVAILABLE:
            super().__init__(app)
        else:
            self.app = app

        self.service_name = service_name
        self.excluded_paths = excluded_paths or [
            "/health",
            "/healthz",
            "/ready",
            "/metrics",
        ]
        self.record_request_headers = record_request_headers
        self.record_response_headers = record_response_headers

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle request with tracing."""
        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Extract parent context from incoming headers
        carrier = dict(request.headers)
        parent_context = extract_context(carrier)

        # Create span
        tracer = get_tracer()
        span_name = f"{request.method} {request.url.path}"

        # Get span kind if OpenTelemetry is available
        span_kwargs = {}
        if _OTEL_AVAILABLE:
            from opentelemetry.trace import SpanKind

            span_kwargs["kind"] = SpanKind.SERVER
            if parent_context:
                span_kwargs["context"] = parent_context

        with tracer.start_as_current_span(span_name, **span_kwargs) as span:
            # Add standard HTTP attributes
            self._set_request_attributes(span, request)

            # Execute request
            start_time = time.perf_counter()
            try:
                response = await call_next(request)
                duration = time.perf_counter() - start_time

                # Add response attributes
                self._set_response_attributes(span, response, duration)

                # Inject trace context into response headers
                response_headers = {}
                inject_context(response_headers)
                for key, value in response_headers.items():
                    response.headers[key] = value

                return response

            except Exception as e:
                duration = time.perf_counter() - start_time
                record_exception(e)
                self._set_error_attributes(span, e, duration)
                raise

    def _set_request_attributes(self, span: Any, request: Request) -> None:
        """Set span attributes from request."""
        if not hasattr(span, "set_attribute"):
            return

        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        span.set_attribute("http.scheme", request.url.scheme)
        span.set_attribute("http.host", request.url.hostname or "")
        span.set_attribute("http.target", request.url.path)
        span.set_attribute("http.route", request.url.path)

        # Client info
        if request.client:
            span.set_attribute("http.client_ip", request.client.host)

        # User agent
        user_agent = request.headers.get("user-agent", "")
        if user_agent:
            span.set_attribute("http.user_agent", user_agent)

        # Request headers (if enabled)
        if self.record_request_headers:
            for key, value in request.headers.items():
                if key.lower() not in ("authorization", "cookie", "x-api-key"):
                    span.set_attribute(f"http.request.header.{key}", value)

    def _set_response_attributes(
        self,
        span: Any,
        response: Response,
        duration: float,
    ) -> None:
        """Set span attributes from response."""
        if not hasattr(span, "set_attribute"):
            return

        span.set_attribute("http.status_code", response.status_code)
        span.set_attribute("http.response.duration_ms", duration * 1000)

        # Set status
        if _OTEL_AVAILABLE and response.status_code >= 400:
            from opentelemetry.trace import Status, StatusCode

            if response.status_code >= 500:
                span.set_status(
                    Status(StatusCode.ERROR, f"HTTP {response.status_code}")
                )
            else:
                span.set_status(Status(StatusCode.OK))

        # Response headers (if enabled)
        if self.record_response_headers:
            for key, value in response.headers.items():
                span.set_attribute(f"http.response.header.{key}", value)

    def _set_error_attributes(
        self,
        span: Any,
        exception: Exception,
        duration: float,
    ) -> None:
        """Set span attributes for errors."""
        if not hasattr(span, "set_attribute"):
            return

        span.set_attribute("http.response.duration_ms", duration * 1000)
        span.set_attribute("error.type", type(exception).__name__)
        span.set_attribute("error.message", str(exception))

        if _OTEL_AVAILABLE:
            from opentelemetry.trace import Status, StatusCode

            span.set_status(Status(StatusCode.ERROR, str(exception)))


class MetricsMiddleware(BaseHTTPMiddleware if _STARLETTE_AVAILABLE else object):
    """
    FastAPI middleware for automatic request metrics.

    Records:
    - Request count by method, path, status
    - Request latency histogram

    Example:
        >>> from fastapi import FastAPI
        >>> from agentic_brain.observability.middleware import MetricsMiddleware
        >>>
        >>> app = FastAPI()
        >>> app.add_middleware(MetricsMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        excluded_paths: list[str] | None = None,
    ):
        """
        Initialize metrics middleware.

        Args:
            app: ASGI application
            excluded_paths: Paths to exclude from metrics
        """
        if _STARLETTE_AVAILABLE:
            super().__init__(app)
        else:
            self.app = app

        self.excluded_paths = excluded_paths or [
            "/health",
            "/healthz",
            "/ready",
            "/metrics",
        ]

        # Create HTTP metrics
        from .metrics import counter, get_meter, histogram

        get_meter()

        self._request_counter = counter(
            name="http_requests_total",
            description="Total HTTP requests",
            unit="1",
        )

        self._request_duration = histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration",
            unit="s",
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle request with metrics."""
        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        start_time = time.perf_counter()
        status_code = 500  # Default for exceptions

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time

            labels = {
                "method": request.method,
                "path": request.url.path,
                "status": str(status_code),
            }

            self._request_counter.add(1, labels)
            self._request_duration.record(duration, labels)


class ChatMetricsMiddleware(BaseHTTPMiddleware if _STARLETTE_AVAILABLE else object):
    """
    Specialized middleware for chat endpoint metrics.

    Records chat-specific metrics:
    - Chat requests by provider/model
    - Chat latency
    - Token usage (if available in response)

    Example:
        >>> from fastapi import FastAPI
        >>> from agentic_brain.observability.middleware import ChatMetricsMiddleware
        >>>
        >>> app = FastAPI()
        >>> app.add_middleware(ChatMetricsMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        chat_paths: list[str] | None = None,
    ):
        """
        Initialize chat metrics middleware.

        Args:
            app: ASGI application
            chat_paths: Paths to track as chat endpoints (default: ["/chat", "/api/chat"])
        """
        if _STARLETTE_AVAILABLE:
            super().__init__(app)
        else:
            self.app = app

        self.chat_paths = chat_paths or [
            "/chat",
            "/api/chat",
            "/v1/chat",
            "/api/v1/chat",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle request with chat metrics."""
        # Only track chat endpoints
        if not any(request.url.path.startswith(p) for p in self.chat_paths):
            return await call_next(request)

        start_time = time.perf_counter()
        provider = "unknown"
        model = "unknown"
        status = "success"

        try:
            # Try to extract provider/model from request
            if request.method == "POST":
                try:
                    # Note: This requires request body to be read
                    # In practice, you'd extract this from query params or path
                    pass
                except Exception:
                    pass

            response = await call_next(request)

            if response.status_code >= 400:
                status = "error"

            return response

        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time

            record_chat_request(
                provider=provider,
                model=model,
                status=status,
            )
            record_chat_latency(
                duration_seconds=duration,
                provider=provider,
                model=model,
            )


def create_observability_middleware(
    app: FastAPI,
    tracing: bool = True,
    metrics: bool = True,
    chat_metrics: bool = True,
    service_name: str = "agentic-brain",
    excluded_paths: list[str] | None = None,
) -> None:
    """
    Add all observability middleware to a FastAPI app.

    Args:
        app: FastAPI application
        tracing: Enable tracing middleware
        metrics: Enable metrics middleware
        chat_metrics: Enable chat-specific metrics middleware
        service_name: Service name for tracing
        excluded_paths: Paths to exclude

    Example:
        >>> from fastapi import FastAPI
        >>> from agentic_brain.observability.middleware import create_observability_middleware
        >>>
        >>> app = FastAPI()
        >>> create_observability_middleware(app)
    """
    if not _STARLETTE_AVAILABLE:
        logger.warning("Starlette not available, middleware not added")
        return

    excluded = excluded_paths or ["/health", "/healthz", "/ready", "/metrics"]

    # Add middleware in reverse order (last added runs first)
    if chat_metrics:
        app.add_middleware(ChatMetricsMiddleware)

    if metrics:
        app.add_middleware(MetricsMiddleware, excluded_paths=excluded)

    if tracing:
        app.add_middleware(
            TracingMiddleware,
            service_name=service_name,
            excluded_paths=excluded,
        )

    logger.info(
        f"Observability middleware added: tracing={tracing}, "
        f"metrics={metrics}, chat_metrics={chat_metrics}"
    )


def instrument_fastapi(
    app: FastAPI,
    service_name: str | None = None,
) -> None:
    """
    Use OpenTelemetry's FastAPI instrumentation if available.

    This uses the official opentelemetry-instrumentation-fastapi package
    for more comprehensive automatic instrumentation.

    Args:
        app: FastAPI application
        service_name: Service name (optional)

    Example:
        >>> from fastapi import FastAPI
        >>> from agentic_brain.observability.middleware import instrument_fastapi
        >>>
        >>> app = FastAPI()
        >>> instrument_fastapi(app)
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,healthz,ready,metrics",
        )
        logger.info("FastAPI instrumented with OpenTelemetry")

    except ImportError:
        logger.debug(
            "opentelemetry-instrumentation-fastapi not available, "
            "using custom middleware instead"
        )
        create_observability_middleware(
            app, service_name=service_name or "agentic-brain"
        )
