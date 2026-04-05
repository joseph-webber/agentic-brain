"""RAGTracer: collect spans and metrics for retrieval-augmented generation flows.
Tracks latency, token usage, retrieval quality, and costs. Provides hooks to export to third-party systems.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

from .spans import Span


class RAGTracer:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._active_spans: List[Span] = []
        self._finished_spans: List[Span] = []
        self.token_usage = {"input": 0, "output": 0}
        self.retrieval_scores: List[float] = []
        self.costs: List[float] = []

        # integrations (lazy)
        self.langfuse = None
        self.phoenix = None
        self.opentelemetry = None

    def start_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Span:
        parent = self._active_spans[-1] if self._active_spans else None
        span = Span(name=name, tracer=self, attributes=attributes)
        if parent:
            parent.add_child(span)
        self._active_spans.append(span)
        return span

    def end_span(self, span: Span) -> None:
        # allow explicit end
        if span in self._active_spans:
            span.end()
            self._active_spans.remove(span)

    def _on_span_end(self, span: Span) -> None:
        self._finished_spans.append(span)
        # export to integrations if present
        try:
            if self.langfuse:
                self.langfuse.send_event(span)
        except Exception:
            pass
        try:
            if self.phoenix:
                self.phoenix.send_event(span)
        except Exception:
            pass
        try:
            if self.opentelemetry:
                self.opentelemetry.export_span(span)
        except Exception:
            pass

    # metrics
    def record_tokens(self, count: int, which: str = "input") -> None:
        if which not in self.token_usage:
            raise ValueError("which must be 'input' or 'output'")
        self.token_usage[which] += int(count)

    def record_retrieval_score(self, score: float) -> None:
        try:
            self.retrieval_scores.append(float(score))
        except Exception:
            pass

    def record_cost(self, amount: float) -> None:
        try:
            self.costs.append(float(amount))
        except Exception:
            pass

    # convenience
    def active_span(self) -> Optional[Span]:
        return self._active_spans[-1] if self._active_spans else None

    def export(self) -> Dict[str, Any]:
        total_latency = sum(s.duration for s in self._finished_spans if s.duration)
        avg_retrieval = (
            sum(self.retrieval_scores) / len(self.retrieval_scores)
            if self.retrieval_scores
            else None
        )
        return {
            "spans": [s.to_dict() for s in self._finished_spans],
            "latency_seconds": total_latency,
            "token_usage": dict(self.token_usage),
            "retrieval_quality": {
                "scores": list(self.retrieval_scores),
                "average": avg_retrieval,
            },
            "costs": {"total": sum(self.costs), "breakdown": list(self.costs)},
        }
