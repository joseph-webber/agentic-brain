# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agentic_brain.graph.topic_hub import (
    TOPIC_SCHEMA_STATEMENTS,
    QuarterlyAuditSummary,
    TopicCreateResult,
    TopicHub,
    ensure_topic_schema,
)


class FakeResult:
    def __init__(self, *, single_data=None, rows=None):
        self._single_data = single_data
        self._rows = rows or []

    def single(self):
        return self._single_data

    def data(self):
        return self._rows


def _make_driver(session: MagicMock) -> MagicMock:
    driver = MagicMock()
    session_manager = MagicMock()
    session_manager.__enter__.return_value = session
    session_manager.__exit__.return_value = False
    driver.session.return_value = session_manager
    return driver


def test_ensure_topic_schema_runs_all_statements():
    session = MagicMock()

    ensure_topic_schema(session)

    assert session.run.call_count == len(TOPIC_SCHEMA_STATEMENTS)
    assert session.run.call_args_list[0].args[0] == TOPIC_SCHEMA_STATEMENTS[0]


def test_get_topics_returns_topic_records_in_order():
    session = MagicMock()
    session.run.side_effect = [
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(
            rows=[
                {
                    "name": "Authentication",
                    "description": "Auth flows and providers",
                    "created_at": "2026-03-28T00:00:00+00:00",
                    "usage_count": 14,
                },
                {
                    "name": "Billing",
                    "description": "Invoices and settlements",
                    "created_at": "2026-03-27T00:00:00+00:00",
                    "usage_count": 9,
                },
            ]
        ),
    ]
    hub = TopicHub(driver=_make_driver(session))

    topics = hub.get_topics()

    assert [topic.name for topic in topics] == ["Authentication", "Billing"]
    assert topics[0].usage_count == 14
    assert topics[1].description == "Invoices and settlements"


def test_create_topic_warns_when_soft_cap_is_near():
    session = MagicMock()
    session.run.side_effect = [
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(single_data={"topic_count": 75}),
        FakeResult(
            single_data={
                "name": "Payments",
                "description": "Payment providers and checkout",
                "created_at": "2026-03-28T00:00:00+00:00",
                "created": True,
            }
        ),
    ]
    hub = TopicHub(driver=_make_driver(session))

    with pytest.warns(UserWarning, match="nearing the recommended soft cap"):
        result = hub.create_topic("Payments", "Payment providers and checkout")

    assert isinstance(result, TopicCreateResult)
    assert result.created is True
    assert result.total_topics == 76
    assert result.warning is not None


def test_link_to_topic_validates_lookup_and_returns_link_result():
    session = MagicMock()
    session.run.side_effect = [
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(single_data={"topic_count": 1}),
        FakeResult(
            single_data={
                "name": "GraphRAG",
                "description": "Graph retrieval stack",
                "created_at": "2026-03-28T00:00:00+00:00",
                "created": False,
            }
        ),
        FakeResult(single_data={"matched_nodes": 1}),
    ]
    hub = TopicHub(driver=_make_driver(session))

    result = hub.link_to_topic(
        node_label="Document",
        node_key="id",
        node_value="doc-123",
        topic_name="GraphRAG",
    )

    assert result.linked is True
    assert result.created_topic is False
    assert result.topic_name == "GraphRAG"


def test_link_to_topic_raises_when_node_is_missing():
    session = MagicMock()
    session.run.side_effect = [
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(single_data={"topic_count": 2}),
        FakeResult(
            single_data={
                "name": "GraphRAG",
                "description": "Graph retrieval stack",
                "created_at": "2026-03-28T00:00:00+00:00",
                "created": False,
            }
        ),
        FakeResult(single_data={"matched_nodes": 0}),
    ]
    hub = TopicHub(driver=_make_driver(session))

    with pytest.raises(LookupError, match="No node found"):
        hub.link_to_topic(
            node_label="Document",
            node_key="id",
            node_value="missing",
            topic_name="GraphRAG",
        )


def test_quarterly_audit_reports_warning_status():
    session = MagicMock()
    session.run.side_effect = [
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(
            rows=[
                {
                    "name": f"Topic {index}",
                    "description": "",
                    "created_at": "2026-03-28T00:00:00+00:00",
                    "usage_count": 1,
                }
                for index in range(80)
            ]
        ),
    ]
    hub = TopicHub(driver=_make_driver(session))

    audit = hub.quarterly_audit()

    assert isinstance(audit, QuarterlyAuditSummary)
    assert audit.status == "warning"
    assert audit.topic_count == 80
    assert audit.recommendations[0].startswith("Topic hub contains 80 topics")
