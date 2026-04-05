# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""Multi-step query planning for routed search workloads."""

from dataclasses import dataclass, field
from typing import Any

from .classifier import QueryClassification, QueryClassifier, RouteType
from .decomposer import QueryDecomposer, QueryDecomposition


@dataclass(frozen=True, slots=True)
class QueryStep:
    """One action inside a query plan."""

    route: RouteType
    query: str
    confidence: float
    purpose: str = ""
    fallback_routes: tuple[RouteType, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "query": self.query,
            "confidence": self.confidence,
            "purpose": self.purpose,
            "fallback_routes": [route.value for route in self.fallback_routes],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """Structured search plan for a query."""

    original_query: str
    primary_route: RouteType
    confidence: float
    steps: tuple[QueryStep, ...]
    fallback_routes: tuple[RouteType, ...] = ()
    requires_decomposition: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_multi_step(self) -> bool:
        return len(self.steps) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "primary_route": self.primary_route.value,
            "confidence": self.confidence,
            "steps": [step.to_dict() for step in self.steps],
            "fallback_routes": [route.value for route in self.fallback_routes],
            "requires_decomposition": self.requires_decomposition,
            "is_multi_step": self.is_multi_step,
            "metadata": dict(self.metadata),
        }


class QueryPlanner:
    """Build a route-aware execution plan from a natural language query."""

    def __init__(
        self,
        classifier: QueryClassifier | None = None,
        decomposer: QueryDecomposer | None = None,
    ) -> None:
        self.classifier = classifier or QueryClassifier()
        self.decomposer = decomposer or QueryDecomposer()

    def build_plan(self, query: str) -> QueryPlan:
        classification = self.classifier.classify(query)
        decomposition = self.decomposer.decompose(query)
        steps = self._build_steps(query, classification, decomposition)
        metadata = {
            "part_count": len(decomposition.parts),
            "signal_count": classification.metadata.get("signal_count", 0),
            "word_count": classification.metadata.get("word_count", 0),
        }
        return QueryPlan(
            original_query=query,
            primary_route=classification.route,
            confidence=classification.confidence,
            steps=tuple(steps),
            fallback_routes=classification.fallback_routes,
            requires_decomposition=decomposition.is_multi_step
            or classification.needs_decomposition,
            metadata=metadata,
        )

    def _build_steps(
        self,
        query: str,
        classification: QueryClassification,
        decomposition: QueryDecomposition,
    ) -> list[QueryStep]:
        if not decomposition.is_multi_step:
            return [
                QueryStep(
                    route=classification.route,
                    query=query.strip(),
                    confidence=classification.confidence,
                    purpose=self._purpose_for_route(classification.route),
                    fallback_routes=classification.fallback_routes,
                    metadata={"route_source": "classification"},
                )
            ]

        steps: list[QueryStep] = []
        for part in decomposition.parts:
            part_classification = self.classifier.classify(part)
            steps.append(
                QueryStep(
                    route=part_classification.route,
                    query=part,
                    confidence=part_classification.confidence,
                    purpose=self._purpose_for_route(part_classification.route),
                    fallback_routes=part_classification.fallback_routes,
                    metadata={"route_source": "decomposition"},
                )
            )

        if classification.route == RouteType.HYBRID and all(
            step.route == RouteType.HYBRID for step in steps
        ):
            return steps

        if classification.route != RouteType.HYBRID:
            steps.insert(
                0,
                QueryStep(
                    route=classification.route,
                    query=query.strip(),
                    confidence=classification.confidence,
                    purpose=f"orchestrate {len(steps)} sub-queries",
                    fallback_routes=classification.fallback_routes,
                    metadata={"route_source": "classification"},
                ),
            )
        return steps

    def _purpose_for_route(self, route: RouteType) -> str:
        return {
            RouteType.VECTOR: "semantic retrieval",
            RouteType.GRAPH: "relationship traversal",
            RouteType.HYBRID: "combined retrieval",
            RouteType.WEB: "fresh external lookup",
        }[route]
