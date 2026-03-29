# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for topic governance and quarterly audit helpers."""

from agentic_brain.graph.topic_hub import (
    SOFT_TOPIC_CAP,
    SOFT_TOPIC_WARN_THRESHOLD,
    TopicHub,
    render_audit_report,
)


class StubTopicHub(TopicHub):
    """Test double for TopicHub that avoids a live Neo4j dependency."""

    def __init__(self, topics, orphan_nodes):
        super().__init__(session_factory=lambda: None)
        self._topics = topics
        self._orphan_nodes = orphan_nodes

    def _load_topics(self):
        return self._topics

    def find_orphan_nodes(self, limit: int = 25):
        return self._orphan_nodes[:limit]


def test_check_topic_health_warns_at_soft_threshold():
    topics = [
        {"node_id": f"topic-{idx}", "name": f"Topic {idx}", "relationship_count": 1}
        for idx in range(SOFT_TOPIC_WARN_THRESHOLD)
    ]
    hub = StubTopicHub(topics, [])

    health = hub.check_topic_health()

    assert health["status"] == "warning"
    assert health["warning_threshold_reached"] is True
    assert health["soft_cap"] == SOFT_TOPIC_CAP


def test_check_topic_health_detects_soft_cap_and_orphans():
    topics = [
        {"node_id": f"topic-{idx}", "name": f"Topic {idx}", "relationship_count": 1}
        for idx in range(SOFT_TOPIC_CAP)
    ]
    topics.append(
        {"node_id": "topic-orphan", "name": "Dormant Topic", "relationship_count": 0}
    )
    hub = StubTopicHub(topics, [])

    health = hub.check_topic_health()

    assert health["status"] == "soft-cap-exceeded"
    assert health["orphan_topic_count"] == 1
    assert "Dormant Topic" in health["orphan_topic_examples"]


def test_suggest_merges_flags_duplicates_and_similar_topics():
    hub = StubTopicHub(
        [
            {"node_id": "1", "name": "AI Safety", "relationship_count": 12},
            {"node_id": "2", "name": "ai-safety", "relationship_count": 4},
            {"node_id": "3", "name": "Graph RAG", "relationship_count": 8},
            {"node_id": "4", "name": "GraphRAG", "relationship_count": 6},
            {"node_id": "5", "name": "Finance", "relationship_count": 2},
        ],
        [],
    )

    suggestions = hub.suggest_merges(limit=5, similarity_threshold=0.7)

    assert any(
        suggestion["from_topic"] == "ai-safety"
        and suggestion["to_topic"] == "AI Safety"
        and suggestion["confidence"] == 1.0
        for suggestion in suggestions
    )
    assert any(
        {"Graph RAG", "GraphRAG"} == {suggestion["from_topic"], suggestion["to_topic"]}
        for suggestion in suggestions
    )


def test_build_quarterly_audit_includes_cleanup_actions():
    hub = StubTopicHub(
        [
            {"node_id": "1", "name": "AI Safety", "relationship_count": 5},
            {"node_id": "2", "name": "ai-safety", "relationship_count": 1},
            {"node_id": "3", "name": "Dormant Topic", "relationship_count": 0},
        ],
        [{"node_id": "n-1", "labels": ["Document"], "name": "Loose Doc"}],
    )

    report = hub.build_quarterly_audit(limit=5)

    assert report["topic_health"]["merge_suggestion_count"] >= 1
    assert report["orphan_nodes"][0]["name"] == "Loose Doc"
    assert report["cleanup_actions"]


def test_render_audit_report_markdown_contains_expected_sections():
    report = {
        "generated_at": "2026-03-29T00:00:00+00:00",
        "topic_health": {
            "status": "warning",
            "topic_count": 80,
            "soft_cap": 100,
            "warning_threshold": 75,
            "capacity_used_pct": 80.0,
            "capacity_remaining": 20,
            "orphan_topic_count": 2,
            "duplicate_topic_group_count": 1,
            "merge_suggestion_count": 1,
            "merge_suggestions": [
                {
                    "from_topic": "ai-safety",
                    "to_topic": "AI Safety",
                    "confidence": 1.0,
                    "reason": "Exact normalized match",
                }
            ],
        },
        "orphan_nodes": [{"node_id": "n-1", "labels": ["Topic"], "name": "Loose"}],
        "cleanup_actions": ["Merge duplicates."],
    }

    rendered = render_audit_report(report, format="markdown")

    assert "# Quarterly Topic Audit" in rendered
    assert "## Suggested topic merges" in rendered
    assert "AI Safety" in rendered
