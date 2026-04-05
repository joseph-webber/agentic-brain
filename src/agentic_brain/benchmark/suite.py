# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Performance benchmark suite for Agentic Brain RAG flows."""

from __future__ import annotations

import asyncio
import inspect
import platform
import statistics
import time
import tracemalloc
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Awaitable, Callable


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _rss_megabytes() -> float:
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024
    except Exception:
        return 0.0


def _default_documents() -> list[str]:
    return [
        "Agentic Brain uses GraphRAG for retrieval and reasoning.",
        "Embeddings power semantic search across notes, docs, and sessions.",
        "Concurrent requests stress the scheduler and shared caches.",
        "Memory tracking helps keep benchmark regressions visible.",
        "Graph queries should stay fast even when the graph grows.",
    ]


def _default_graph() -> dict[str, set[str]]:
    return {
        "rag": {"embeddings", "graph", "memory"},
        "embeddings": {"rag", "vector-search"},
        "graph": {"rag", "concurrency"},
        "memory": {"rag", "concurrency"},
        "concurrency": {"graph", "memory"},
    }


@dataclass
class BenchmarkMetric:
    name: str
    label: str
    unit: str
    samples: list[float] = field(default_factory=list)
    items: int = 0
    seconds: float = 0.0
    peak_memory_mb: float = 0.0
    comparison: str = "p95"
    direction: str = "lower"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def p50(self) -> float:
        return _percentile(self.samples, 0.50)

    @property
    def p95(self) -> float:
        return _percentile(self.samples, 0.95)

    @property
    def p99(self) -> float:
        return _percentile(self.samples, 0.99)

    @property
    def minimum(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def maximum(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def throughput(self) -> float:
        return self.items / self.seconds if self.seconds > 0 else 0.0

    def comparison_value(self) -> float:
        if self.comparison == "throughput":
            return self.throughput
        if self.comparison == "peak_memory_mb":
            return self.peak_memory_mb
        if self.comparison == "mean":
            return self.mean
        return self.p95

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "unit": self.unit,
            "samples": self.samples,
            "items": self.items,
            "seconds": self.seconds,
            "peak_memory_mb": self.peak_memory_mb,
            "comparison": self.comparison,
            "direction": self.direction,
            "mean": self.mean,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
            "throughput": self.throughput,
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkSuiteResult:
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    hardware: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, BenchmarkMetric] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "hardware": self.hardware,
            "metadata": self.metadata,
            "metrics": {
                name: metric.to_dict() for name, metric in self.metrics.items()
            },
        }

    def _format_value(self, value: float, unit: str) -> str:
        if unit == "seconds":
            return f"{value:.4f}s"
        if unit == "MB":
            return f"{value:.1f} MB"
        if unit == "ops/s":
            return f"{value:.1f} ops/s"
        return f"{value:.3f} {unit}"

    def to_table(self) -> str:
        if not self.metrics:
            return "No benchmark metrics available."
        lines = [
            "╔══════════════════════════════════════════════════════════════════════════╗",
            "║                       AGENTIC BRAIN PERFORMANCE                          ║",
            "╠══════════════════════════════════════════════════════════════════════════╣",
        ]
        for metric in self.metrics.values():
            lines.append(
                f"║ {metric.label[:28]:<28} │ {self._format_value(metric.comparison_value(), metric.unit):<14} │ "
                f"P95 {self._format_value(metric.p95, metric.unit):<14} │ items {metric.items:<5} ║"
            )
        lines.append(
            "╚══════════════════════════════════════════════════════════════════════════╝"
        )
        return "\n".join(lines)

    def to_markdown(self) -> str:
        if not self.metrics:
            return "# Agentic Brain Performance\n\nNo benchmark metrics available."
        lines = [
            "# Agentic Brain Performance Benchmarks",
            "",
            f"**Timestamp:** {self.timestamp}",
            "",
            "| Metric | Primary | P95 | Throughput | Peak Memory |",
            "|---|---:|---:|---:|---:|",
        ]
        for metric in self.metrics.values():
            lines.append(
                f"| {metric.label} | {metric.comparison_value():.4f} | {metric.p95:.4f} | "
                f"{metric.throughput:.1f} | {metric.peak_memory_mb:.1f} MB |"
            )
        return "\n".join(lines)

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), indent=2)

    def ascii_chart(self, width: int = 34) -> str:
        if not self.metrics:
            return "No benchmark metrics available."
        rows = []
        max_value = (
            max(metric.comparison_value() for metric in self.metrics.values()) or 1.0
        )
        for metric in self.metrics.values():
            value = metric.comparison_value()
            bar_width = max(1, int((value / max_value) * width))
            rows.append(f'{metric.label:<28} {"#" * bar_width:<{width}} {value:.3f}')
        return "\n".join(rows)

    def recommendations(self) -> list[str]:
        tips: list[str] = []
        rag = self.metrics.get("rag_query_latency")
        graph = self.metrics.get("graph_query_performance")
        memory = self.metrics.get("memory_usage")
        concurrency = self.metrics.get("concurrent_requests")
        if rag and rag.p95 > 0.25:
            tips.append(
                "Cache repeated RAG prompts and prune prompt context before retrieval."
            )
        if graph and graph.p95 > 0.05:
            tips.append(
                "Add or verify Neo4j indexes on the hottest graph traversal paths."
            )
        if memory and memory.peak_memory_mb > 128:
            tips.append(
                "Use smaller batches and stream embeddings to reduce peak memory."
            )
        if concurrency and concurrency.throughput < 20:
            tips.append(
                "Increase worker concurrency or switch hot paths to async execution."
            )
        if not tips:
            tips.append(
                "Current benchmark profile looks healthy; keep tracking regressions."
            )
        return tips


class BenchmarkSuite:
    def __init__(
        self,
        *,
        documents: list[str] | None = None,
        graph: dict[str, set[str]] | None = None,
        queries: list[str] | None = None,
        embeddings_batch: list[str] | None = None,
        concurrency: int = 8,
        request_count: int = 32,
        rag_iterations: int = 24,
        graph_iterations: int = 32,
        embedding_iterations: int = 64,
    ) -> None:
        self.documents = documents or _default_documents()
        self.graph = graph or _default_graph()
        self.queries = queries or [
            "How does GraphRAG improve retrieval?",
            "What affects embedding throughput?",
            "How do concurrent requests behave?",
            "Why track memory usage?",
        ]
        self.embeddings_batch = embeddings_batch or self.documents * 4
        self.concurrency = concurrency
        self.request_count = request_count
        self.rag_iterations = rag_iterations
        self.graph_iterations = graph_iterations
        self.embedding_iterations = embedding_iterations

    def _default_rag_query(self, query: str) -> str:
        tokens = {token.strip(".,?").lower() for token in query.split()}
        best_score = -1
        best_doc = ""
        for document in self.documents:
            document_tokens = {token.strip(".,?").lower() for token in document.split()}
            score = len(tokens & document_tokens)
            if score > best_score:
                best_score = score
                best_doc = document
        return best_doc

    def _default_embed(self, text: str) -> list[float]:
        values = [float((ord(char) % 31) / 31.0) for char in text[:64]]
        return values or [0.0]

    def _default_graph_query(self, query: str) -> list[str]:
        key = query.split()[0].lower().strip("?,.")
        neighbors = sorted(self.graph.get(key, set()))
        if not neighbors:
            for candidate, links in self.graph.items():
                if key in links:
                    neighbors = sorted(links)
                    break
        return neighbors

    async def _default_request(self, payload: str) -> str:
        await asyncio.sleep(0)
        return payload[::-1]

    def benchmark_rag_query_latency(
        self,
        query_fn: Callable[[str], Any] | None = None,
        *,
        iterations: int | None = None,
    ) -> BenchmarkMetric:
        fn = query_fn or self._default_rag_query
        samples: list[float] = []
        started = time.perf_counter()
        total = iterations or self.rag_iterations
        for index in range(total):
            query = self.queries[index % len(self.queries)]
            before = time.perf_counter()
            result = fn(query)
            if inspect.isawaitable(result):
                asyncio.run(result)
            samples.append(time.perf_counter() - before)
        seconds = time.perf_counter() - started
        return BenchmarkMetric(
            name="rag_query_latency",
            label="RAG query latency",
            unit="seconds",
            samples=samples,
            items=total,
            seconds=seconds,
            peak_memory_mb=_rss_megabytes(),
            comparison="p95",
            direction="lower",
            metadata={"queries": list(self.queries)},
        )

    def benchmark_embedding_throughput(
        self,
        embed_fn: Callable[[str], Any] | None = None,
        *,
        iterations: int | None = None,
    ) -> BenchmarkMetric:
        fn = embed_fn or self._default_embed
        samples: list[float] = []
        total = iterations or self.embedding_iterations
        items = 0
        started = time.perf_counter()
        for index in range(total):
            text = self.embeddings_batch[index % len(self.embeddings_batch)]
            before = time.perf_counter()
            result = fn(text)
            if inspect.isawaitable(result):
                asyncio.run(result)
            samples.append(time.perf_counter() - before)
            items += 1
        seconds = time.perf_counter() - started
        return BenchmarkMetric(
            name="embedding_throughput",
            label="Embedding throughput",
            unit="ops/s",
            samples=samples,
            items=items,
            seconds=seconds,
            peak_memory_mb=_rss_megabytes(),
            comparison="throughput",
            direction="higher",
            metadata={"batch_size": len(self.embeddings_batch)},
        )

    def benchmark_graph_query_performance(
        self,
        graph_query_fn: Callable[[str], Any] | None = None,
        *,
        iterations: int | None = None,
    ) -> BenchmarkMetric:
        fn = graph_query_fn or self._default_graph_query
        samples: list[float] = []
        total = iterations or self.graph_iterations
        started = time.perf_counter()
        for index in range(total):
            query = self.queries[index % len(self.queries)]
            before = time.perf_counter()
            result = fn(query)
            if inspect.isawaitable(result):
                asyncio.run(result)
            samples.append(time.perf_counter() - before)
        seconds = time.perf_counter() - started
        return BenchmarkMetric(
            name="graph_query_performance",
            label="Graph query performance",
            unit="seconds",
            samples=samples,
            items=total,
            seconds=seconds,
            peak_memory_mb=_rss_megabytes(),
            comparison="p95",
            direction="lower",
            metadata={"graph_nodes": len(self.graph)},
        )

    def benchmark_memory_usage(
        self,
        operation: Callable[[], Any] | None = None,
    ) -> BenchmarkMetric:
        op = operation or self._memory_probe_operation
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        start = time.perf_counter()
        op()
        seconds = time.perf_counter() - start
        after = tracemalloc.take_snapshot()
        top = after.compare_to(before, "lineno")[:5]
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak / (1024 * 1024)
        return BenchmarkMetric(
            name="memory_usage",
            label="Memory usage",
            unit="MB",
            samples=[peak_mb, current / (1024 * 1024)],
            items=1,
            seconds=seconds,
            peak_memory_mb=peak_mb,
            comparison="peak_memory_mb",
            direction="lower",
            metadata={"top_diffs": [str(row) for row in top]},
        )

    def _memory_probe_operation(self) -> None:
        deque((self._default_embed(text) for text in self.embeddings_batch), maxlen=8)
        for query in self.queries:
            self._default_rag_query(query)
            self._default_graph_query(query)

    async def benchmark_concurrent_request_handling(
        self,
        request_handler: Callable[[str], Awaitable[Any] | Any] | None = None,
        *,
        concurrency: int | None = None,
        request_count: int | None = None,
    ) -> BenchmarkMetric:
        handler = request_handler or self._default_request
        concurrency = concurrency or self.concurrency
        total_requests = request_count or self.request_count
        payloads = [f"request-{index}" for index in range(total_requests)]
        samples: list[float] = []

        async def invoke(payload: str) -> None:
            before = time.perf_counter()
            result = handler(payload)
            if inspect.isawaitable(result):
                await result
            samples.append(time.perf_counter() - before)

        started = time.perf_counter()
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded(payload: str) -> None:
            async with semaphore:
                await invoke(payload)

        await asyncio.gather(*(bounded(payload) for payload in payloads))
        seconds = time.perf_counter() - started
        return BenchmarkMetric(
            name="concurrent_requests",
            label="Concurrent requests",
            unit="ops/s",
            samples=samples,
            items=total_requests,
            seconds=seconds,
            peak_memory_mb=_rss_megabytes(),
            comparison="throughput",
            direction="higher",
            metadata={"concurrency": concurrency},
        )

    async def run_async(self) -> BenchmarkSuiteResult:
        metrics = {
            "rag_query_latency": self.benchmark_rag_query_latency(),
            "embedding_throughput": self.benchmark_embedding_throughput(),
            "graph_query_performance": self.benchmark_graph_query_performance(),
            "memory_usage": self.benchmark_memory_usage(),
            "concurrent_requests": await self.benchmark_concurrent_request_handling(),
        }
        return BenchmarkSuiteResult(
            hardware={
                "platform": platform.system(),
                "processor": platform.processor() or "Unknown",
                "python": platform.python_version(),
            },
            metrics=metrics,
            metadata={
                "documents": len(self.documents),
                "graph_nodes": len(self.graph),
                "concurrency": self.concurrency,
            },
        )

    def run(self) -> BenchmarkSuiteResult:
        return asyncio.run(self.run_async())


__all__ = ["BenchmarkMetric", "BenchmarkSuite", "BenchmarkSuiteResult"]
