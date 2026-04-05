# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""Heuristic query classification for intelligent routing."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RouteType(str, Enum):
    """Supported routing targets."""

    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"
    WEB = "web"


@dataclass(frozen=True, slots=True)
class QueryClassification:
    """Classification result for a single query."""

    route: RouteType
    confidence: float
    scores: dict[RouteType, float] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    fallback_routes: tuple[RouteType, ...] = ()
    needs_decomposition: bool = False
    complexity: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "confidence": self.confidence,
            "scores": {route.value: score for route, score in self.scores.items()},
            "reasons": list(self.reasons),
            "fallback_routes": [route.value for route in self.fallback_routes],
            "needs_decomposition": self.needs_decomposition,
            "complexity": self.complexity,
            "metadata": dict(self.metadata),
        }


class QueryClassifier:
    """Keyword and structure based classifier for search routing."""

    VECTOR_TERMS = {
        "document",
        "documents",
        "doc",
        "docs",
        "file",
        "files",
        "manual",
        "policy",
        "policies",
        "summarize",
        "summary",
        "explain",
        "meaning",
        "what does",
        "find similar",
        "similar",
        "similarity",
        "embedding",
        "embeddings",
        "semantic",
        "retrieve",
        "retrieval",
        "context",
        "knowledge base",
        "kb",
        "text",
        "passage",
        "section",
        "content",
    }

    GRAPH_TERMS = {
        "relationship",
        "relationships",
        "related",
        "connect",
        "connected",
        "connection",
        "connections",
        "path",
        "paths",
        "graph",
        "graphr",
        "entity",
        "entities",
        "node",
        "nodes",
        "link",
        "links",
        "multi-hop",
        "hop",
        "traverse",
        "traversal",
        "neighbor",
        "neighbors",
        "neighbour",
        "neighbours",
        "lineage",
        "dependency",
        "dependencies",
        "hierarchy",
        "who knows",
        "who is related",
    }

    WEB_TERMS = {
        "latest",
        "current",
        "today",
        "tonight",
        "now",
        "news",
        "recent",
        "recently",
        "updated",
        "update",
        "version",
        "release",
        "released",
        "price",
        "prices",
        "weather",
        "forecast",
        "stock",
        "stocks",
        "market",
        "web",
        "internet",
        "online",
        "search the web",
        "browse",
        "github",
        "release notes",
        "deadline",
    }

    HYBRID_TERMS = {
        "compare",
        "versus",
        "vs",
        "both",
        "combine",
        "combined",
        "and also",
        "along with",
        "plus",
        "then",
        "after that",
        "multi-step",
        "multi step",
    }

    def classify(self, query: str) -> QueryClassification:
        normalized = self._normalize(query)
        words = self._words(normalized)
        scores = {
            RouteType.VECTOR: self._score_vector(normalized, words),
            RouteType.GRAPH: self._score_graph(normalized, words),
            RouteType.HYBRID: self._score_hybrid(normalized, words),
            RouteType.WEB: self._score_web(normalized, words),
        }
        route = self._select_route(scores, normalized)
        confidence = round(scores[route], 3)
        ordered_fallbacks = tuple(
            route_type
            for route_type, _ in sorted(
                ((route_type, score) for route_type, score in scores.items() if route_type != route),
                key=lambda item: item[1],
                reverse=True,
            )
        )
        reasons = self._reasons_for_route(route, normalized, words)
        needs_decomposition = self._needs_decomposition(normalized, words, route)
        complexity = self._estimate_complexity(normalized, words, scores)
        metadata = {
            "word_count": len(words),
            "signal_count": self._signal_count(normalized),
            "top_score_gap": self._top_score_gap(scores),
        }
        return QueryClassification(
            route=route,
            confidence=confidence,
            scores=scores,
            reasons=reasons,
            fallback_routes=ordered_fallbacks,
            needs_decomposition=needs_decomposition,
            complexity=complexity,
            metadata=metadata,
        )

    def _normalize(self, query: str) -> str:
        return " ".join(query.strip().lower().split())

    def _words(self, normalized: str) -> list[str]:
        return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", normalized)

    def _count_hits(self, normalized: str, terms: Iterable[str]) -> int:
        return sum(1 for term in terms if term in normalized)

    def _score_vector(self, normalized: str, words: list[str]) -> float:
        hits = self._count_hits(normalized, self.VECTOR_TERMS)
        score = 0.12 + min(0.46, hits * 0.12)
        if len(words) >= 10:
            score += 0.08
        if any(term in normalized for term in ("summarize", "explain", "find", "retrieve")):
            score += 0.08
        if any(term in normalized for term in ("document", "docs", "policy", "manual")):
            score += 0.05
        return min(score, 1.0)

    def _score_graph(self, normalized: str, words: list[str]) -> float:
        hits = self._count_hits(normalized, self.GRAPH_TERMS)
        score = 0.18 + min(0.5, hits * 0.2)
        if any(
            term in normalized
            for term in ("who", "related", "connect", "connection", "path", "traverse", "dependency")
        ):
            score += 0.2
        if len(words) >= 8 and hits:
            score += 0.05
        return min(score, 1.0)

    def _score_web(self, normalized: str, words: list[str]) -> float:
        hits = self._count_hits(normalized, self.WEB_TERMS)
        score = 0.08 + min(0.54, hits * 0.13)
        if any(term in normalized for term in ("latest", "current", "today", "now", "recent")):
            score += 0.12
        if "?" in normalized:
            score += 0.03
        if len(words) <= 6 and hits:
            score += 0.04
        return min(score, 1.0)

    def _score_hybrid(self, normalized: str, words: list[str]) -> float:
        vector_hits = self._count_hits(normalized, self.VECTOR_TERMS)
        graph_hits = self._count_hits(normalized, self.GRAPH_TERMS)
        hybrid_hits = self._count_hits(normalized, self.HYBRID_TERMS)
        score = 0.18
        if vector_hits and graph_hits:
            score += 0.34
        if hybrid_hits:
            score += min(0.28, hybrid_hits * 0.08)
        if len(words) >= 12:
            score += 0.08
        if normalized.count(" and ") >= 1 or normalized.count(";") >= 1:
            score += 0.06
        return min(score, 1.0)

    def _select_route(
        self,
        scores: dict[RouteType, float],
        normalized: str,
    ) -> RouteType:
        top_route, top_score = max(scores.items(), key=lambda item: item[1])
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        runner_up = sorted_scores[1][1]
        vector_score = scores[RouteType.VECTOR]
        graph_score = scores[RouteType.GRAPH]
        hybrid_score = scores[RouteType.HYBRID]
        web_score = scores[RouteType.WEB]

        if web_score >= 0.65 and web_score >= top_score - 0.08:
            return RouteType.WEB
        if (
            vector_score >= 0.25
            and graph_score >= 0.35
            and (" and " in normalized or normalized.count(";") >= 1)
        ):
            return RouteType.HYBRID
        if vector_score >= 0.7 and vector_score >= graph_score + 0.08 and vector_score >= web_score - 0.1:
            return RouteType.VECTOR
        if graph_score >= 0.7 and graph_score >= vector_score + 0.08 and graph_score >= web_score - 0.1:
            return RouteType.GRAPH
        if (
            hybrid_score >= max(vector_score, graph_score) - 0.03
            and (vector_score >= 0.35 and graph_score >= 0.35)
        ):
            return RouteType.HYBRID
        if top_score - runner_up < 0.1 and (vector_score >= 0.35 and graph_score >= 0.35):
            return RouteType.HYBRID
        if "current" in normalized or "latest" in normalized or "today" in normalized:
            if web_score >= 0.45:
                return RouteType.WEB
        return top_route

    def _reasons_for_route(
        self,
        route: RouteType,
        normalized: str,
        words: list[str],
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        hits = {
            RouteType.VECTOR: self._count_hits(normalized, self.VECTOR_TERMS),
            RouteType.GRAPH: self._count_hits(normalized, self.GRAPH_TERMS),
            RouteType.HYBRID: self._count_hits(normalized, self.HYBRID_TERMS),
            RouteType.WEB: self._count_hits(normalized, self.WEB_TERMS),
        }
        if route == RouteType.WEB and hits[RouteType.WEB]:
            reasons.append("query references current or time-sensitive information")
        if route == RouteType.GRAPH and hits[RouteType.GRAPH]:
            reasons.append("query asks about relationships, paths, or connections")
        if route == RouteType.VECTOR and hits[RouteType.VECTOR]:
            reasons.append("query matches document or semantic retrieval patterns")
        if route == RouteType.HYBRID:
            reasons.append("query combines multiple retrieval signals")
            if len(words) >= 12:
                reasons.append("query is multi-part or complex")
        if not reasons:
            reasons.append("selected by highest route score")
        return tuple(reasons)

    def _needs_decomposition(
        self,
        normalized: str,
        words: list[str],
        route: RouteType,
    ) -> bool:
        if normalized.count(";") >= 1 or normalized.count("?") >= 2:
            return True
        if len(words) >= 16:
            return True
        if route == RouteType.HYBRID:
            return True
        return self._count_hits(normalized, self.HYBRID_TERMS) >= 2

    def _estimate_complexity(
        self,
        normalized: str,
        words: list[str],
        scores: dict[RouteType, float],
    ) -> float:
        complexity = min(1.0, len(words) / 20.0)
        if normalized.count(";") or normalized.count("?") > 1:
            complexity += 0.2
        if scores[RouteType.HYBRID] >= 0.5:
            complexity += 0.15
        if scores[RouteType.WEB] >= 0.6:
            complexity += 0.05
        return round(min(complexity, 1.0), 3)

    def _signal_count(self, normalized: str) -> int:
        return sum(
            self._count_hits(normalized, terms)
            for terms in (self.VECTOR_TERMS, self.GRAPH_TERMS, self.HYBRID_TERMS, self.WEB_TERMS)
        )

    def _top_score_gap(self, scores: dict[RouteType, float]) -> float:
        ordered = sorted(scores.values(), reverse=True)
        if len(ordered) < 2:
            return 1.0
        return round(ordered[0] - ordered[1], 3)
