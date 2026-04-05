"""Performance-oriented tests for the Neo4j client pool integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import agentic_brain.neo4j.brain_graph as brain_graph


class FakeSession:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.closed = False

    def run(self, cypher: str, params: dict | None = None):  # noqa: ARG002
        result = MagicMock()
        result.__iter__.return_value = iter(self.rows)
        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        self.closed = True
        return False


class FakeDriver:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.session_calls = 0

    def session(self):
        self.session_calls += 1
        return FakeSession(self.rows)


def setup_function(function):  # noqa: ARG001
    brain_graph._driver = None
    brain_graph._topic_graph = None
    brain_graph._zoned_graph = None


def test_get_driver_uses_shared_pool_once():
    fake_driver = object()
    with (
        patch.object(brain_graph, "configure_pool") as configure_pool,
        patch.object(
            brain_graph, "get_shared_driver", return_value=fake_driver
        ) as get_shared_driver,
        patch.dict(
            "os.environ",
            {"NEO4J_URI": "bolt://example", "NEO4J_USER": "neo4j", "NEO4J_PASSWORD": "secret"},
        ),
    ):
        first = brain_graph.get_driver()
        second = brain_graph.get_driver()

    assert first is fake_driver
    assert second is fake_driver
    assert configure_pool.call_count == 1
    assert get_shared_driver.call_count == 1


def test_query_reuses_pooled_driver_session():
    fake_driver = FakeDriver([{"id": 1}])
    with patch.object(brain_graph, "get_driver", return_value=fake_driver):
        rows = brain_graph.query("MATCH (n) RETURN n")

    assert rows == [{"id": 1}]
    assert fake_driver.session_calls == 1


def test_init_graph_uses_shared_driver():
    fake_driver = object()
    with (
        patch.object(brain_graph, "get_driver", return_value=fake_driver) as get_driver,
        patch.object(brain_graph, "setup_graph_constraints") as setup_graph_constraints,
        patch.object(brain_graph, "ensure_topics_exist", return_value=3) as ensure_topics_exist,
    ):
        assert brain_graph.init_graph() is True

    get_driver.assert_called_once()
    setup_graph_constraints.assert_called_once_with(fake_driver)
    ensure_topics_exist.assert_called_once()


def test_get_rag_context_uses_topic_graph_results():
    topic_graph = MagicMock()
    topic_graph.query_by_topic.side_effect = [
        [{"label": "Doc", "item": "Alpha", "relationship": "RELATES_TO"}],
        [],
    ]

    with patch.object(brain_graph, "get_topic_graph", return_value=topic_graph):
        context = brain_graph.get_rag_context(["alpha", "beta"], limit_per_topic=1)

    assert "Context for 'alpha'" in context
    assert "Alpha" in context
    assert "beta" not in context
