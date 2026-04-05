# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from agentic_brain.benchmark.competitors import CompetitorBenchmark
from agentic_brain.benchmark.suite import BenchmarkSuite


def test_competitor_report_labels_and_rows() -> None:
    result = BenchmarkSuite(
        rag_iterations=3, embedding_iterations=4, graph_iterations=3, request_count=4
    ).run()
    report = CompetitorBenchmark(result).compare()

    table = report.to_table()
    charts = report.ascii_charts()

    assert "LangChain RAG" in table
    assert "LlamaIndex RAG" in table
    assert "Basic vector search" in table
    assert "Agentic Brain vs competitors" in charts


def test_agentic_brain_stays_competitive() -> None:
    result = BenchmarkSuite(
        rag_iterations=3, embedding_iterations=4, graph_iterations=3, request_count=4
    ).run()
    report = CompetitorBenchmark(result).compare()

    agentic_rag = result.metrics["rag_query_latency"].comparison_value()
    agentic_graph = result.metrics["graph_query_performance"].comparison_value()
    for row in report.rows:
        if row.name == "Basic vector search":
            assert row.graph_latency_seconds >= agentic_graph
        else:
            assert row.rag_latency_seconds >= agentic_rag
