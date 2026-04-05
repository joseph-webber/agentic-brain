#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 12: OpenTelemetry Tracing

Demonstrates how to use OpenTelemetry observability in agentic-brain:
- Setting up tracing with different exporters
- Using trace decorators
- Recording metrics
- Propagating context between services

Prerequisites:
    pip install agentic-brain[api,observability]

    # Optional: Run Jaeger locally
    docker run -d --name jaeger \
      -p 16686:16686 \
      -p 4317:4317 \
      jaegertracing/all-in-one:latest
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

# Set environment before imports
os.environ.setdefault("OTEL_ENABLED", "true")
os.environ.setdefault("OTEL_SERVICE_NAME", "agentic-brain-example")
os.environ.setdefault("OTEL_EXPORTER", "console")  # Use "otlp" for Jaeger


def example_basic_tracing():
    """Basic tracing setup and usage."""
    print("\n=== Example 1: Basic Tracing ===\n")

    from agentic_brain.observability import (
        ExporterType,
        TracingConfig,
        setup_tracing,
        shutdown_tracing,
        trace,
    )

    # Setup with explicit config
    config = TracingConfig(
        enabled=True,
        service_name="my-agent",
        exporter_type=ExporterType.CONSOLE,
    )
    setup_tracing(config=config)

    # Use @trace decorator
    @trace
    def process_request(user_id: str, message: str) -> str:
        """Process a user request - automatically traced."""
        time.sleep(0.1)  # Simulate work
        return f"Hello {user_id}, received: {message}"

    # Execute traced function
    result = process_request("user123", "Hello world!")
    print(f"Result: {result}")

    # Clean up
    shutdown_tracing()


async def example_async_tracing():
    """Async tracing with nested spans."""
    print("\n=== Example 2: Async Tracing ===\n")

    from agentic_brain.observability import (
        ExporterType,
        TracingConfig,
        add_span_attributes,
        get_current_span,
        setup_tracing,
        shutdown_tracing,
        trace_async,
    )

    setup_tracing(
        service_name="async-agent",
        exporter_type=ExporterType.CONSOLE,
        enabled=True,
    )

    @trace_async(name="call-llm", kind="client")
    async def call_llm(prompt: str) -> str:
        """Simulated LLM call."""
        # Add custom attributes to current span
        add_span_attributes(
            {
                "llm.prompt_length": len(prompt),
                "llm.provider": "openai",
                "llm.model": "gpt-4",
            }
        )

        await asyncio.sleep(0.2)  # Simulate API call
        return f"Response to: {prompt[:20]}..."

    @trace_async(name="process-chat")
    async def process_chat(message: str) -> str:
        """Process a chat message with nested spans."""
        # Get current span for logging
        span = get_current_span()
        if hasattr(span, "set_attribute"):
            span.set_attribute("chat.message_length", len(message))

        # Nested traced call
        response = await call_llm(message)

        return response

    result = await process_chat("What is the meaning of life?")
    print(f"Result: {result}")

    shutdown_tracing()


def example_metrics():
    """Recording metrics."""
    print("\n=== Example 3: Metrics ===\n")

    from agentic_brain.observability import (
        MetricsConfig,
        record_chat_latency,
        record_chat_request,
        record_llm_error,
        record_tokens,
        set_active_sessions,
        setup_metrics,
        shutdown_metrics,
    )

    # Setup metrics
    config = MetricsConfig(
        enabled=True,
        service_name="metrics-example",
        exporter_type="console",
    )
    setup_metrics(config=config)

    # Simulate some operations
    print("Recording metrics...")

    # Record successful chat
    start = time.perf_counter()
    time.sleep(0.1)  # Simulate work
    duration = time.perf_counter() - start

    record_chat_request(provider="openai", model="gpt-4", status="success")
    record_chat_latency(duration, provider="openai", model="gpt-4")
    record_tokens(150, token_type="input", provider="openai", model="gpt-4")
    record_tokens(200, token_type="output", provider="openai", model="gpt-4")

    # Record an error
    record_chat_request(provider="openai", model="gpt-4", status="error")
    record_llm_error("rate_limit", provider="openai", model="gpt-4")

    # Track active sessions
    set_active_sessions(5)

    print("Metrics recorded! (Check console output above)")

    shutdown_metrics()


async def example_fastapi_middleware():
    """FastAPI with observability middleware."""
    print("\n=== Example 4: FastAPI Middleware ===\n")

    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError:
        print("FastAPI not installed. Run: pip install fastapi")
        return

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

    # Setup observability
    setup_tracing(
        TracingConfig(
            enabled=True,
            service_name="fastapi-agent",
            exporter_type="console",
        )
    )
    setup_metrics(
        MetricsConfig(
            enabled=True,
            service_name="fastapi-agent",
            exporter_type="console",
        )
    )

    # Create FastAPI app
    app = FastAPI(title="Traced API")

    # Add observability middleware
    create_observability_middleware(
        app,
        tracing=True,
        metrics=True,
        chat_metrics=True,
        service_name="fastapi-agent",
    )

    @app.get("/")
    async def root():
        return {"message": "Hello World"}

    @app.post("/chat")
    @trace_async(name="handle-chat")
    async def chat(message: str = "Hello"):
        """Chat endpoint with tracing."""
        # Record metrics
        record_chat_request(provider="ollama", model="llama3", status="success")

        # Simulate LLM call
        await asyncio.sleep(0.05)

        return {"response": f"Echo: {message}"}

    @app.get("/health")
    async def health():
        """Health endpoint - excluded from tracing."""
        return {"status": "healthy"}

    # Test the app
    client = TestClient(app)

    print("Testing endpoints...")

    # Test root
    response = client.get("/")
    print(f"GET / -> {response.json()}")

    # Test chat
    response = client.post("/chat?message=Hello%20AI")
    print(f"POST /chat -> {response.json()}")

    # Test health (should be excluded from tracing)
    response = client.get("/health")
    print(f"GET /health -> {response.json()}")

    # Cleanup
    shutdown_tracing()
    shutdown_metrics()


def example_context_propagation():
    """Propagating trace context between services."""
    print("\n=== Example 5: Context Propagation ===\n")

    from agentic_brain.observability import (
        ExporterType,
        TracingConfig,
        extract_context,
        get_tracer,
        inject_context,
        setup_tracing,
        shutdown_tracing,
    )

    setup_tracing(
        TracingConfig(
            enabled=True,
            service_name="service-a",
            exporter_type=ExporterType.CONSOLE,
        )
    )

    # Service A: Create span and inject context
    def service_a_call():
        """Service A makes an outgoing call."""
        tracer = get_tracer()

        with tracer.start_as_current_span("service-a-operation"):
            # Prepare headers for outgoing request
            headers = {}
            inject_context(headers)

            print(f"Service A sending with headers: {headers}")

            # Simulate HTTP call to Service B
            # In real code: requests.post(url, headers=headers)
            return headers

    # Service B: Extract context and continue trace
    def service_b_handle(incoming_headers: dict):
        """Service B receives the request."""
        # Extract context from incoming headers
        context = extract_context(incoming_headers)

        # Continue the trace
        tracer = get_tracer()

        span_kwargs = {}
        if context:
            span_kwargs["context"] = context

        with tracer.start_as_current_span("service-b-operation", **span_kwargs):
            print("Service B handling request in same trace")
            return "B completed"

    # Execute the flow
    headers = service_a_call()
    result = service_b_handle(headers)
    print(f"Result: {result}")

    shutdown_tracing()


def example_with_agent():
    """Using observability with Agent class."""
    print("\n=== Example 6: Agent with Tracing ===\n")

    from agentic_brain.observability import (
        MetricsConfig,
        TracingConfig,
        record_chat_latency,
        record_chat_request,
        setup_metrics,
        setup_tracing,
        shutdown_metrics,
        shutdown_tracing,
        trace,
        trace_async,
    )

    # Setup observability
    setup_tracing(
        TracingConfig(
            enabled=True,
            service_name="traced-agent",
            exporter_type="console",
        )
    )
    setup_metrics(
        MetricsConfig(
            enabled=True,
            service_name="traced-agent",
            exporter_type="console",
        )
    )

    # Create a traced wrapper around Agent
    class TracedAgent:
        """Agent with built-in observability."""

        def __init__(self, name: str):
            self.name = name

        @trace
        def chat(self, message: str) -> str:
            """Synchronous chat with tracing."""
            start = time.perf_counter()

            # Simulate LLM response
            time.sleep(0.1)
            response = f"[{self.name}] Response to: {message}"

            # Record metrics
            duration = time.perf_counter() - start
            record_chat_request(provider="local", model="mock", status="success")
            record_chat_latency(duration, provider="local", model="mock")

            return response

    # Use the traced agent
    agent = TracedAgent("assistant")

    response = agent.chat("Hello!")
    print(f"Response: {response}")

    response = agent.chat("How are you?")
    print(f"Response: {response}")

    # Cleanup
    shutdown_tracing()
    shutdown_metrics()


def example_custom_metrics():
    """Creating custom metrics."""
    print("\n=== Example 7: Custom Metrics ===\n")

    from agentic_brain.observability import (
        MetricsConfig,
        counter,
        histogram,
        setup_metrics,
        shutdown_metrics,
    )
    from agentic_brain.observability.metrics import timed

    setup_metrics(
        MetricsConfig(
            enabled=True,
            service_name="custom-metrics",
            exporter_type="console",
        )
    )

    # Create custom metrics
    documents_processed = counter(
        name="documents_processed_total",
        description="Total documents processed",
    )

    histogram(
        name="document_processing_seconds",
        description="Document processing time",
        unit="s",
    )

    # Use custom metrics
    @timed("operation_duration_seconds", "Time spent in operation")
    def process_document(doc_id: str) -> str:
        """Process a document with timing."""
        # Simulate work
        time.sleep(0.05)

        # Record metrics
        documents_processed.add(1, {"type": "pdf", "source": "upload"})

        return f"Processed {doc_id}"

    # Process some documents
    for i in range(3):
        result = process_document(f"doc-{i}")
        print(f"  {result}")

    print("\nCustom metrics recorded!")

    shutdown_metrics()


async def main():
    """Run all examples."""
    print("=" * 60)
    print("OpenTelemetry Observability Examples")
    print("=" * 60)

    # Run examples
    example_basic_tracing()
    await example_async_tracing()
    example_metrics()
    await example_fastapi_middleware()
    example_context_propagation()
    example_with_agent()
    example_custom_metrics()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print(
        """
Tips:
1. Set OTEL_EXPORTER=otlp and run Jaeger to see traces in UI
2. Use OTEL_TRACES_SAMPLER=traceidratio in production
3. Add custom attributes to spans for better debugging
4. Record latency metrics for SLO monitoring
    """
    )


if __name__ == "__main__":
    asyncio.run(main())
