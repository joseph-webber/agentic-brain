# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

from unittest.mock import MagicMock

from agentic_brain.graph.topic_audit import TopicAuditReport, audit_topics


class FakeResult:
    def __init__(self, *, rows=None):
        self._rows = rows or []

    def data(self):
        return self._rows


def _make_driver(session: MagicMock) -> MagicMock:
    driver = MagicMock()
    session_manager = MagicMock()
    session_manager.__enter__.return_value = session
    session_manager.__exit__.return_value = False
    driver.session.return_value = session_manager
    return driver


def test_audit_topics_reports_orphans_overused_topics_and_merges():
    session = MagicMock()
    session.run.side_effect = [
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(
            rows=[
                {
                    "name": "Authentication",
                    "description": "",
                    "created_at": "2026-03-28T00:00:00+00:00",
                    "usage_count": 4,
                },
                {
                    "name": "Auth",
                    "description": "",
                    "created_at": "2026-03-28T00:00:00+00:00",
                    "usage_count": 2,
                },
                {
                    "name": "Billing",
                    "description": "",
                    "created_at": "2026-03-28T00:00:00+00:00",
                    "usage_count": 30,
                },
            ]
        ),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(
            rows=[
                {
                    "label": "Document",
                    "orphan_count": 3,
                    "examples": ["doc-1", "doc-2"],
                }
            ]
        ),
    ]

    report = audit_topics(
        driver=_make_driver(session),
        min_overuse_count=10,
        merge_similarity_threshold=0.6,
    )

    assert isinstance(report, TopicAuditReport)
    assert report.orphan_nodes[0].label == "Document"
    assert report.orphan_nodes[0].orphan_count == 3
    assert report.overused_topics[0].name == "Billing"
    assert report.overused_topics[0].threshold == 12
    assert any(
        suggestion.primary_topic == "Auth"
        and suggestion.secondary_topic == "Authentication"
        for suggestion in report.merge_suggestions
    )
