# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from agentic_brain.routing import (
    QueryClassification,
    QueryClassifier,
    QueryDecision,
    QueryDecomposer,
    QueryExecutionResult,
    QueryPlan,
    QueryPlanner,
    QueryRouter,
    QueryStep,
    RouteType,
)


@pytest.fixture()
def classifier() -> QueryClassifier:
    return QueryClassifier()


@pytest.fixture()
def decomposer() -> QueryDecomposer:
    return QueryDecomposer()


@pytest.fixture()
def planner(classifier: QueryClassifier, decomposer: QueryDecomposer) -> QueryPlanner:
    return QueryPlanner(classifier, decomposer)


@pytest.fixture()
def router(classifier: QueryClassifier, decomposer: QueryDecomposer) -> QueryRouter:
    return QueryRouter(classifier=classifier, decomposer=decomposer)


@pytest.mark.parametrize(
    ("query", "route"),
    [
        ("Find relevant documents about onboarding", RouteType.VECTOR),
        ("Summarize the policy handbook", RouteType.VECTOR),
        ("Explain the meaning of this passage", RouteType.VECTOR),
        ("Who is related to the CEO?", RouteType.GRAPH),
        ("Find the connection path between Alice and Bob", RouteType.GRAPH),
        ("Trace the dependency chain for this issue", RouteType.GRAPH),
        ("Search the web for the latest release notes", RouteType.WEB),
        ("What is the current price today?", RouteType.WEB),
        ("Find docs and relationship paths", RouteType.HYBRID),
        ("Compare the document summary and graph links", RouteType.HYBRID),
    ],
)
def test_classifier_routes(
    query: str, route: RouteType, classifier: QueryClassifier
) -> None:
    result = classifier.classify(query)
    assert result.route == route
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.parametrize(
    ("query", "minimum_confidence"),
    [
        ("Find relevant documents about onboarding", 0.6),
        ("Who is related to the CEO?", 0.6),
        ("Search the web for the latest release notes", 0.65),
    ],
)
def test_classifier_confidence_is_reasonable(
    query: str, minimum_confidence: float, classifier: QueryClassifier
) -> None:
    assert classifier.classify(query).confidence >= minimum_confidence


@pytest.mark.parametrize(
    ("query", "contains"),
    [
        ("Find relevant documents about onboarding", "document"),
        ("Who is related to the CEO?", "relationships"),
        ("Search the web for the latest release notes", "current"),
    ],
)
def test_classifier_reasons_reflect_route(
    query: str, contains: str, classifier: QueryClassifier
) -> None:
    result = classifier.classify(query)
    assert any(contains in reason for reason in result.reasons)


@pytest.mark.parametrize(
    ("query", "fallback"),
    [
        ("Find relevant documents about onboarding", RouteType.HYBRID),
        ("Who is related to the CEO?", RouteType.HYBRID),
        ("Search the web for the latest release notes", RouteType.HYBRID),
    ],
)
def test_classifier_fallbacks_include_hybrid(
    query: str, fallback: RouteType, classifier: QueryClassifier
) -> None:
    result = classifier.classify(query)
    assert fallback in result.fallback_routes


@pytest.mark.parametrize(
    ("query", "expected_parts"),
    [
        ("Find the policy; then check the graph", 2),
        ("Summarize the policy and also search the web", 2),
        (
            "First find docs, then find related entities, then check the latest update",
            3,
        ),
        ("Simple query", 1),
        ("Compare apples and oranges", 1),
    ],
)
def test_decomposer_parts(
    query: str, expected_parts: int, decomposer: QueryDecomposer
) -> None:
    result = decomposer.decompose(query)
    assert len(result.parts) == expected_parts


def test_decomposer_marks_multi_step(decomposer: QueryDecomposer) -> None:
    result = decomposer.decompose("Find the policy; then check the graph")
    assert result.is_multi_step
    assert result.metadata["part_count"] == 2


def test_decomposer_keeps_compare_queries_together(decomposer: QueryDecomposer) -> None:
    result = decomposer.decompose("Compare the document summary and graph links")
    assert result.parts == ("Compare the document summary and graph links",)


@pytest.mark.parametrize(
    "query",
    [
        "Find relevant documents about onboarding",
        "Who is related to the CEO?",
        "Search the web for the latest release notes",
        "Find docs and relationship paths",
    ],
)
def test_planner_returns_plan(query: str, planner: QueryPlanner) -> None:
    plan = planner.build_plan(query)
    assert isinstance(plan, QueryPlan)
    assert plan.steps
    assert plan.primary_route in RouteType


def test_planner_single_step_uses_one_step(planner: QueryPlanner) -> None:
    plan = planner.build_plan("Find relevant documents about onboarding")
    assert len(plan.steps) == 1
    assert plan.steps[0].route == RouteType.VECTOR


def test_planner_multi_step_adds_steps(planner: QueryPlanner) -> None:
    plan = planner.build_plan("Find the policy; then check the graph")
    assert plan.is_multi_step
    assert len(plan.steps) >= 2


def test_planner_multi_step_routes_can_mix(planner: QueryPlanner) -> None:
    plan = planner.build_plan("Find docs and relationship paths")
    assert any(step.route == RouteType.VECTOR for step in plan.steps)
    assert any(step.route == RouteType.GRAPH for step in plan.steps)


def test_planner_purpose_matches_route(planner: QueryPlanner) -> None:
    plan = planner.build_plan("Search the web for the latest release notes")
    assert "fresh external lookup" in plan.steps[0].purpose


def test_router_classify_delegates(router: QueryRouter) -> None:
    result = router.classify("Find relevant documents about onboarding")
    assert result.route == RouteType.VECTOR


def test_router_plan_delegates(router: QueryRouter) -> None:
    plan = router.plan("Find relevant documents about onboarding")
    assert plan.primary_route == RouteType.VECTOR


def test_router_route_returns_decision(router: QueryRouter) -> None:
    decision = router.route("Who is related to the CEO?")
    assert isinstance(decision, QueryDecision)
    assert decision.route == RouteType.GRAPH


def test_router_route_uses_available_routes_when_needed(router: QueryRouter) -> None:
    decision = router.route(
        "Search the web for the latest release notes",
        available_routes=[RouteType.VECTOR, RouteType.GRAPH],
    )
    assert decision.route in {RouteType.VECTOR, RouteType.GRAPH}


@pytest.mark.asyncio
async def test_router_execute_vector_handler(router: QueryRouter) -> None:
    router = QueryRouter(handlers={RouteType.VECTOR: lambda q: f"vector:{q}"})
    result = await router.execute("Find relevant documents about onboarding")
    assert isinstance(result, QueryExecutionResult)
    assert result.results == ("vector:Find relevant documents about onboarding",)


@pytest.mark.asyncio
async def test_router_execute_web_handler_async() -> None:
    async def handler(query: str) -> str:
        return f"web:{query}"

    router = QueryRouter(handlers={RouteType.WEB: handler})
    result = await router.execute("Search the web for the latest release notes")
    assert result.results == ("web:Search the web for the latest release notes",)


@pytest.mark.asyncio
async def test_router_execute_falls_back_on_failure() -> None:
    calls: list[str] = []

    def failing_handler(query: str) -> str:
        calls.append("vector")
        raise RuntimeError("boom")

    def fallback_handler(query: str) -> str:
        calls.append("hybrid")
        return f"hybrid:{query}"

    router = QueryRouter(
        handlers={
            RouteType.VECTOR: failing_handler,
            RouteType.HYBRID: fallback_handler,
        }
    )
    result = await router.execute("Find docs and relationship paths")
    assert result.results
    assert "hybrid" in calls


@pytest.mark.asyncio
async def test_router_execute_multi_step(router: QueryRouter) -> None:
    router = QueryRouter(
        handlers={
            RouteType.VECTOR: lambda q: f"vector:{q}",
            RouteType.GRAPH: lambda q: f"graph:{q}",
            RouteType.HYBRID: lambda q: f"hybrid:{q}",
        }
    )
    result = await router.execute("Find the policy; then check the graph")
    assert len(result.results) >= 2


def test_classification_to_dict(classifier: QueryClassifier) -> None:
    result = classifier.classify("Find relevant documents about onboarding")
    data = result.to_dict()
    assert data["route"] == "vector"
    assert data["scores"]["vector"] >= 0


def test_decomposition_to_dict(decomposer: QueryDecomposer) -> None:
    result = decomposer.decompose("Find the policy; then check the graph")
    data = result.to_dict()
    assert data["is_multi_step"] is True
    assert data["parts"] == ["Find the policy", "check the graph"]


def test_step_to_dict() -> None:
    step = QueryStep(route=RouteType.WEB, query="check latest release", confidence=0.9)
    assert step.to_dict()["route"] == "web"


def test_plan_to_dict(planner: QueryPlanner) -> None:
    plan = planner.build_plan("Find the policy; then check the graph")
    data = plan.to_dict()
    assert data["primary_route"] in {"vector", "graph", "hybrid", "web"}
    assert data["steps"]


def test_decision_to_dict(router: QueryRouter) -> None:
    decision = router.route("Find relevant documents about onboarding")
    data = decision.to_dict()
    assert data["route"] == "vector"


def test_router_min_confidence_filters_primary_route() -> None:
    router = QueryRouter(min_confidence=0.95)
    decision = router.route("Find relevant documents about onboarding")
    assert decision.route in RouteType


def test_router_handles_string_route_keys() -> None:
    router = QueryRouter(
        handlers={
            "vector": lambda q: f"vector:{q}",
            "graph": lambda q: f"graph:{q}",
        }
    )
    decision = router.route("Find relevant documents about onboarding")
    assert decision.route == RouteType.VECTOR


def test_query_classification_metadata_contains_gap(
    classifier: QueryClassifier,
) -> None:
    result = classifier.classify("Find relevant documents about onboarding")
    assert "top_score_gap" in result.metadata


def test_query_plan_metadata_contains_counts(planner: QueryPlanner) -> None:
    plan = planner.build_plan("Find docs and relationship paths")
    assert plan.metadata["part_count"] >= 1


def test_query_decision_fields(router: QueryRouter) -> None:
    decision = router.route("Find docs and relationship paths")
    assert decision.fallback_routes
    assert decision.plan.original_query
