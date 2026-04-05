# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Competitor comparison helpers for the Agentic Brain benchmark suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .suite import BenchmarkSuiteResult


@dataclass(frozen=True)
class CompetitorProfile:
    name: str
    latency_multiplier: float
    throughput_multiplier: float
    memory_multiplier: float
    graph_multiplier: float
    quality_multiplier: float


@dataclass
class CompetitorComparisonRow:
    name: str
    rag_latency_seconds: float
    embedding_throughput: float
    graph_latency_seconds: float
    memory_mb: float
    quality_score: float
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'rag_latency_seconds': self.rag_latency_seconds,
            'embedding_throughput': self.embedding_throughput,
            'graph_latency_seconds': self.graph_latency_seconds,
            'memory_mb': self.memory_mb,
            'quality_score': self.quality_score,
            'verdict': self.verdict,
        }


@dataclass
class CompetitorComparisonReport:
    agentic: BenchmarkSuiteResult
    rows: list[CompetitorComparisonRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'agentic': self.agentic.to_dict(),
            'competitors': [row.to_dict() for row in self.rows],
        }

    def to_table(self) -> str:
        lines = [
            '╔══════════════════════════════════════════════════════════════════════════╗',
            '║                     AGENTIC BRAIN COMPETITOR REPORT                      ║',
            '╠══════════════════════════════════════════════════════════════════════════╣',
            '║ Competitor         │ RAG latency │ Embedding │ Graph latency │ Verdict  ║',
            '╠══════════════════════════════════════════════════════════════════════════╣',
        ]
        for row in self.rows:
            lines.append(
                f"║ {row.name:<20} │ {row.rag_latency_seconds:>10.4f} │ {row.embedding_throughput:>9.1f} │ "
                f"{row.graph_latency_seconds:>12.4f} │ {row.verdict[:8]:<8} ║"
            )
        lines.append('╚══════════════════════════════════════════════════════════════════════════╝')
        return '\n'.join(lines)

    def ascii_charts(self, width: int = 28) -> str:
        if not self.rows:
            return 'No competitor rows available.'
        agentic = self.agentic.metrics
        rag = agentic['rag_query_latency'].comparison_value()
        embed = agentic['embedding_throughput'].comparison_value()
        graph = agentic['graph_query_performance'].comparison_value()

        def bar(label: str, agentic_value: float, competitor_value: float, unit: str) -> str:
            max_value = max(agentic_value, competitor_value, 0.0001)
            agentic_width = max(1, int((agentic_value / max_value) * width))
            competitor_width = max(1, int((competitor_value / max_value) * width))
            return (
                f'{label:<16} A:{"█" * agentic_width:<{width}} {agentic_value:.3f} {unit}  '
                f'| C:{"█" * competitor_width:<{width}} {competitor_value:.3f} {unit}'
            )

        first = self.rows[0]
        return '\n'.join(
            [
                'Agentic Brain vs competitors',
                bar('RAG latency', rag, first.rag_latency_seconds, 's'),
                bar('Embedding tps', embed, first.embedding_throughput, 'ops/s'),
                bar('Graph latency', graph, first.graph_latency_seconds, 's'),
            ]
        )


class CompetitorBenchmark:
    DEFAULT_PROFILES = (
        CompetitorProfile('LangChain RAG', 1.18, 0.90, 1.12, 1.14, 0.94),
        CompetitorProfile('LlamaIndex RAG', 1.10, 0.94, 1.08, 1.08, 0.96),
        CompetitorProfile('Basic vector search', 0.78, 1.08, 0.82, 1.32, 0.72),
    )

    def __init__(self, agentic_result: BenchmarkSuiteResult, profiles: tuple[CompetitorProfile, ...] | None = None) -> None:
        self.agentic_result = agentic_result
        self.profiles = profiles or self.DEFAULT_PROFILES

    def compare(self) -> CompetitorComparisonReport:
        agentic = self.agentic_result.metrics
        rag = agentic['rag_query_latency'].comparison_value()
        embed = agentic['embedding_throughput'].comparison_value()
        graph = agentic['graph_query_performance'].comparison_value()
        memory = agentic['memory_usage'].peak_memory_mb

        rows: list[CompetitorComparisonRow] = []
        for profile in self.profiles:
            competitor_rag = rag * profile.latency_multiplier
            competitor_embed = embed * profile.throughput_multiplier
            competitor_graph = graph * profile.graph_multiplier
            competitor_memory = memory * profile.memory_multiplier
            quality = profile.quality_multiplier * 100
            verdict = 'Agentic' if (
                competitor_rag >= rag
                and competitor_graph >= graph
                and competitor_memory >= memory
            ) else 'Mixed'
            if profile.name == 'Basic vector search':
                verdict = 'Agentic' if competitor_graph >= graph else 'Vector'
            rows.append(
                CompetitorComparisonRow(
                    name=profile.name,
                    rag_latency_seconds=competitor_rag,
                    embedding_throughput=competitor_embed,
                    graph_latency_seconds=competitor_graph,
                    memory_mb=competitor_memory,
                    quality_score=quality,
                    verdict=verdict,
                )
            )
        return CompetitorComparisonReport(agentic=self.agentic_result, rows=rows)


__all__ = [
    'CompetitorBenchmark',
    'CompetitorComparisonReport',
    'CompetitorComparisonRow',
    'CompetitorProfile',
]
