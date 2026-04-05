# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio

from agentic_brain.benchmark.suite import BenchmarkSuite


def test_suite_runs_and_reports_metrics() -> None:
    suite = BenchmarkSuite(
        rag_iterations=4,
        embedding_iterations=6,
        graph_iterations=5,
        request_count=8,
        concurrency=4,
    )
    result = suite.run()

    assert set(result.metrics) == {
        "rag_query_latency",
        "embedding_throughput",
        "graph_query_performance",
        "memory_usage",
        "concurrent_requests",
    }
    assert result.metrics["rag_query_latency"].p95 >= 0.0
    assert result.metrics["embedding_throughput"].throughput > 0.0
    assert result.metrics["memory_usage"].peak_memory_mb >= 0.0


def test_suite_table_and_markdown_render() -> None:
    suite = BenchmarkSuite(
        rag_iterations=2, embedding_iterations=2, graph_iterations=2, request_count=2
    )
    result = suite.run()

    table = result.to_table()
    markdown = result.to_markdown()
    chart = result.ascii_chart()

    assert "AGENTIC BRAIN PERFORMANCE" in table
    assert "# Agentic Brain Performance Benchmarks" in markdown
    assert "RAG query latency" in chart


def test_concurrent_requests_supports_async_handler() -> None:
    suite = BenchmarkSuite(request_count=6, concurrency=3)

    async def handler(payload: str) -> str:
        await asyncio.sleep(0)
        return payload.upper()

    metric = asyncio.run(suite.benchmark_concurrent_request_handling(handler))

    assert metric.items == 6
    assert metric.throughput > 0.0
