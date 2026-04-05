# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""Intelligent query routing with confidence scoring and fallback."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
import inspect
from typing import Any

from .classifier import QueryClassification, QueryClassifier, RouteType
from .decomposer import QueryDecomposer
from .planner import QueryPlan, QueryPlanner, QueryStep

RouteHandler = Callable[[str], Any | Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class QueryDecision:
    """Final routing decision for a query."""

    route: RouteType
    confidence: float
    classification: QueryClassification
    plan: QueryPlan
    fallback_routes: tuple[RouteType, ...] = ()
    available_routes: tuple[RouteType, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "confidence": self.confidence,
            "classification": self.classification.to_dict(),
            "plan": self.plan.to_dict(),
            "fallback_routes": [route.value for route in self.fallback_routes],
            "available_routes": [route.value for route in self.available_routes],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class QueryExecutionResult:
    """Result from executing a planned query."""

    route: RouteType
    decision: QueryDecision
    plan: QueryPlan
    results: tuple[Any, ...]
    used_fallbacks: tuple[RouteType, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "decision": self.decision.to_dict(),
            "plan": self.plan.to_dict(),
            "results": list(self.results),
            "used_fallbacks": [route.value for route in self.used_fallbacks],
            "metadata": dict(self.metadata),
        }


class QueryRouter:
    """Classify, plan, and execute natural-language search queries."""

    def __init__(
        self,
        *,
        classifier: QueryClassifier | None = None,
        planner: QueryPlanner | None = None,
        decomposer: QueryDecomposer | None = None,
        handlers: Mapping[RouteType | str, RouteHandler] | None = None,
        min_confidence: float = 0.58,
    ) -> None:
        self.classifier = classifier or QueryClassifier()
        self.decomposer = decomposer or QueryDecomposer()
        self.planner = planner or QueryPlanner(self.classifier, self.decomposer)
        self.min_confidence = min_confidence
        self._handlers = self._normalize_handlers(handlers or {})

    def classify(self, query: str) -> QueryClassification:
        return self.classifier.classify(query)

    def decompose(self, query: str):
        return self.decomposer.decompose(query)

    def plan(self, query: str) -> QueryPlan:
        return self.planner.build_plan(query)

    def route(
        self,
        query: str,
        *,
        available_routes: Sequence[RouteType | str] | None = None,
    ) -> QueryDecision:
        classification = self.classify(query)
        plan = self.plan(query)
        allowed = self._normalize_routes(available_routes) if available_routes is not None else tuple(RouteType)
        route = self._choose_route(classification, allowed)
        fallback_routes = tuple(route_type for route_type in classification.fallback_routes if route_type in allowed and route_type != route)
        metadata = {
            "allowed_routes": [route_type.value for route_type in allowed],
            "decomposed": plan.is_multi_step,
            "threshold": self.min_confidence,
        }
        return QueryDecision(
            route=route,
            confidence=classification.confidence,
            classification=classification,
            plan=plan,
            fallback_routes=fallback_routes,
            available_routes=allowed,
            metadata=metadata,
        )

    async def execute(
        self,
        query: str,
        *,
        available_routes: Sequence[RouteType | str] | None = None,
        handlers: Mapping[RouteType | str, RouteHandler] | None = None,
    ) -> QueryExecutionResult:
        decision = self.route(query, available_routes=available_routes)
        plan = decision.plan
        combined_handlers = self._normalize_handlers(handlers or self._handlers)
        results: list[Any] = []
        used_fallbacks: list[RouteType] = []

        for step in plan.steps:
            result, used = await self._execute_step(
                step,
                combined_handlers,
                decision.available_routes,
                decision.fallback_routes,
            )
            if used:
                used_fallbacks.extend(used)
            results.append(result)

        return QueryExecutionResult(
            route=decision.route,
            decision=decision,
            plan=plan,
            results=tuple(results),
            used_fallbacks=tuple(dict.fromkeys(used_fallbacks)),
            metadata={"step_count": len(plan.steps)},
        )

    def _choose_route(
        self,
        classification: QueryClassification,
        allowed: tuple[RouteType, ...],
    ) -> RouteType:
        preferred = classification.route
        if preferred in allowed and classification.confidence >= self.min_confidence:
            return preferred

        for candidate in classification.fallback_routes:
            if candidate in allowed:
                return candidate

        if preferred in allowed:
            return preferred

        return allowed[0] if allowed else classification.route

    async def _execute_step(
        self,
        step: QueryStep,
        handlers: Mapping[RouteType, RouteHandler],
        available_routes: Sequence[RouteType],
        fallback_routes: Sequence[RouteType],
    ) -> tuple[Any, tuple[RouteType, ...]]:
        route_order = self._route_attempt_order(step.route, fallback_routes, available_routes)
        last_error: Exception | None = None
        used_fallbacks: list[RouteType] = []
        for route in route_order:
            handler = handlers.get(route)
            if handler is None:
                continue
            if route != step.route:
                used_fallbacks.append(route)
            try:
                result = handler(step.query)
                if inspect.isawaitable(result):
                    result = await result
                return result, tuple(used_fallbacks)
            except Exception as exc:  # pragma: no cover - exercised in tests
                last_error = exc
                used_fallbacks.append(route)
                continue
        if last_error is not None:
            raise last_error
        raise LookupError(f"No handler available for route {step.route.value}")

    def _route_attempt_order(
        self,
        primary: RouteType,
        fallback_routes: Sequence[RouteType],
        available_routes: Sequence[RouteType],
    ) -> list[RouteType]:
        ordered: list[RouteType] = []
        for route in (primary, *fallback_routes, *RouteType):
            if route in available_routes and route not in ordered:
                ordered.append(route)
        return ordered

    def _normalize_routes(
        self, routes: Sequence[RouteType | str]
    ) -> tuple[RouteType, ...]:
        normalized: list[RouteType] = []
        for route in routes:
            normalized.append(self._coerce_route(route))
        return tuple(dict.fromkeys(normalized))

    def _normalize_handlers(
        self,
        handlers: Mapping[RouteType | str, RouteHandler],
    ) -> dict[RouteType, RouteHandler]:
        normalized: dict[RouteType, RouteHandler] = {}
        for route, handler in handlers.items():
            normalized[self._coerce_route(route)] = handler
        return normalized

    def _coerce_route(self, route: RouteType | str) -> RouteType:
        if isinstance(route, RouteType):
            return route
        return RouteType(str(route))
