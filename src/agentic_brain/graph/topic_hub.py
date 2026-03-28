# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Topic hub helpers for organizing Neo4j graphs into human-scale domains."""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, Callable

from agentic_brain.core.neo4j_pool import get_driver

DEFAULT_HUB_NAME = "topic-hub"
TOPIC_WARN_THRESHOLD = 75
TOPIC_SOFT_CAP = 100
SOFT_TOPIC_WARN_THRESHOLD = TOPIC_WARN_THRESHOLD
SOFT_TOPIC_CAP = TOPIC_SOFT_CAP

TOPIC_SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT topic_name_unique IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
    "CREATE INDEX topic_created_at IF NOT EXISTS FOR (t:Topic) ON (t.created_at)",
    "CREATE CONSTRAINT hub_name_unique IF NOT EXISTS FOR (h:Hub) REQUIRE h.name IS UNIQUE",
]

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class TopicRecord:
    """A topic and its current usage metadata."""

    name: str
    description: str
    created_at: str
    usage_count: int = 0


@dataclass(frozen=True)
class TopicCreateResult:
    """Result payload returned by :meth:`TopicHub.create_topic`."""

    topic: TopicRecord
    created: bool
    total_topics: int
    warning: str | None = None


@dataclass(frozen=True)
class TopicLinkResult:
    """Result payload returned by :meth:`TopicHub.link_to_topic`."""

    topic_name: str
    node_label: str
    node_key: str
    node_value: Any
    created_topic: bool
    linked: bool
    warning: str | None = None


@dataclass(frozen=True)
class QuarterlyAuditSummary:
    """High-level quarterly review guidance for the topic hub."""

    generated_at: str
    quarter: str
    topic_count: int
    status: str
    next_audit_on: str
    recommendations: list[str]


def ensure_topic_schema(session: Any) -> None:
    """Create topic-hub constraints and indexes for a sync Neo4j session."""

    for statement in TOPIC_SCHEMA_STATEMENTS:
        session.run(statement)


def _validate_identifier(identifier: str, *, kind: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Invalid Cypher {kind}: {identifier!r}")
    return identifier


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _stringify_timestamp(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _normalize_topic_name(name: str) -> str:
    return " ".join(name.lower().replace("_", " ").replace("-", " ").split())


def _topic_similarity(left: str, right: str) -> float:
    normalized_left = _normalize_topic_name(left)
    normalized_right = _normalize_topic_name(right)
    if normalized_left == normalized_right:
        return 1.0
    if normalized_left.startswith(normalized_right) or normalized_right.startswith(
        normalized_left
    ):
        return 0.8
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def _next_quarter_start(reference: datetime) -> datetime:
    quarter_start_month = ((reference.month - 1) // 3) * 3 + 1
    current_quarter_start = datetime(
        reference.year,
        quarter_start_month,
        1,
        tzinfo=reference.tzinfo,
    )
    next_quarter_month = quarter_start_month + 3
    if next_quarter_month > 12:
        return current_quarter_start.replace(year=reference.year + 1, month=1)
    return current_quarter_start.replace(month=next_quarter_month)


class TopicHub:
    """Bridge layer for assigning graph nodes to a curated topic hub."""

    def __init__(
        self,
        driver: Any | None = None,
        *,
        session_factory: Callable[[], Any] | None = None,
        hub_name: str = DEFAULT_HUB_NAME,
        database: str | None = None,
        warn_threshold: int = TOPIC_WARN_THRESHOLD,
        soft_cap: int = TOPIC_SOFT_CAP,
    ) -> None:
        self._session_factory = session_factory
        self.driver = driver if driver is not None else (
            None if session_factory is not None else get_driver(database=database)
        )
        self.hub_name = hub_name
        self.database = database
        self.warn_threshold = warn_threshold
        self.soft_cap = soft_cap

    def _open_session(self):
        if self._session_factory is not None:
            return self._session_factory()
        if self.database:
            return self.driver.session(database=self.database)
        return self.driver.session()

    def _build_warning(self, topic_count: int) -> str | None:
        if topic_count >= self.soft_cap:
            return (
                f"Topic hub contains {topic_count} topics, which is above the recommended "
                f"soft cap of {self.soft_cap}. Consider running a quarterly audit."
            )
        if topic_count >= self.warn_threshold:
            return (
                f"Topic hub contains {topic_count} topics and is nearing the recommended "
                f"soft cap of {self.soft_cap}."
            )
        return None

    def ensure_schema(self) -> None:
        """Ensure the Topic and Hub schema exists before topic operations."""

        with self._open_session() as session:
            ensure_topic_schema(session)

    def get_topics(self) -> list[TopicRecord]:
        """Return all topics ordered by usage count, then name."""

        raw_topics = self._load_topics()
        return [
            TopicRecord(
                name=row["name"],
                description=row.get("description", ""),
                created_at=_stringify_timestamp(row.get("created_at")),
                usage_count=int(
                    row.get("usage_count", row.get("relationship_count", 0)) or 0
                ),
            )
            for row in raw_topics
        ]

    def _load_topics(self) -> list[dict[str, Any]]:
        self.ensure_schema()
        with self._open_session() as session:
            result = session.run(
                """
                MATCH (topic:Topic)
                OPTIONAL MATCH (node)-[:BELONGS_TO]->(topic)
                RETURN topic.name AS name,
                       coalesce(topic.description, '') AS description,
                       topic.created_at AS created_at,
                       count(node) AS usage_count
                ORDER BY usage_count DESC, name ASC
                """
            )
            rows = result.data() if hasattr(result, "data") else list(result)
        return [dict(row) for row in rows]

    def create_topic(
        self,
        name: str,
        description: str = "",
        *,
        created_at: str | None = None,
    ) -> TopicCreateResult:
        """Create or update a topic and register it under the configured hub."""

        self.ensure_schema()
        timestamp = created_at or _utc_now_iso()

        with self._open_session() as session:
            count_result = session.run(
                "MATCH (:Topic) RETURN count(*) AS topic_count"
            ).single()
            topic_count_before = int(count_result["topic_count"])

            record = session.run(
                """
                MERGE (topic:Topic {name: $name})
                ON CREATE SET topic.description = $description,
                              topic.created_at = $created_at,
                              topic._topic_created = true
                ON MATCH SET topic.description = CASE
                    WHEN $description = '' THEN coalesce(topic.description, '')
                    ELSE $description
                END,
                topic._topic_created = false
                WITH topic, topic._topic_created AS created
                REMOVE topic._topic_created
                MERGE (hub:Hub {name: $hub_name})
                ON CREATE SET hub.topics = [$name]
                ON MATCH SET hub.topics = CASE
                    WHEN $name IN coalesce(hub.topics, []) THEN coalesce(hub.topics, [])
                    ELSE coalesce(hub.topics, []) + $name
                END
                RETURN topic.name AS name,
                       coalesce(topic.description, '') AS description,
                       topic.created_at AS created_at,
                       created AS created
                """,
                name=name,
                description=description,
                created_at=timestamp,
                hub_name=self.hub_name,
            ).single()

        was_created = bool(record["created"])
        total_topics = topic_count_before + (1 if was_created else 0)
        warning = self._build_warning(total_topics)
        if warning:
            warnings.warn(warning, UserWarning, stacklevel=2)

        topic = TopicRecord(
            name=record["name"],
            description=record.get("description", ""),
            created_at=_stringify_timestamp(record.get("created_at")),
        )
        return TopicCreateResult(
            topic=topic,
            created=was_created,
            total_topics=total_topics,
            warning=warning,
        )

    def link_to_topic(
        self,
        *,
        node_label: str,
        node_value: Any,
        topic_name: str,
        node_key: str = "id",
        topic_description: str = "",
    ) -> TopicLinkResult:
        """Attach an existing graph node to a topic using ``BELONGS_TO``."""

        safe_label = _validate_identifier(node_label, kind="label")
        safe_key = _validate_identifier(node_key, kind="property")

        topic_result = self.create_topic(topic_name, description=topic_description)

        query = f"""
        MATCH (node:`{safe_label}`)
        WHERE node.`{safe_key}` = $node_value
        MATCH (topic:Topic {{name: $topic_name}})
        MERGE (node)-[:BELONGS_TO]->(topic)
        RETURN count(node) AS matched_nodes
        """

        with self._open_session() as session:
            result = session.run(
                query,
                node_value=node_value,
                topic_name=topic_name,
            ).single()

        matched_nodes = int(result["matched_nodes"])
        if matched_nodes == 0:
            raise LookupError(
                f"No node found for label {node_label!r} with {node_key!r}={node_value!r}."
            )

        return TopicLinkResult(
            topic_name=topic_name,
            node_label=node_label,
            node_key=node_key,
            node_value=node_value,
            created_topic=topic_result.created,
            linked=True,
            warning=topic_result.warning,
        )

    def quarterly_audit(self) -> QuarterlyAuditSummary:
        """Summarize when the next topic review is due and what to check."""

        topics = self.get_topics()
        topic_count = len(topics)
        warning = self._build_warning(topic_count)
        reference = datetime.now(UTC)
        next_audit = _next_quarter_start(reference)

        recommendations = [
            "Review orphan nodes and assign them to an existing topic or create a new one.",
            "Merge overlapping topics and archive unused topics before adding new domains.",
            "Confirm the hub topic list still reflects the public graph taxonomy.",
        ]
        if warning:
            recommendations.insert(0, warning)

        status = "healthy"
        if topic_count >= self.soft_cap:
            status = "over-cap"
        elif topic_count >= self.warn_threshold:
            status = "warning"

        return QuarterlyAuditSummary(
            generated_at=reference.isoformat(),
            quarter=f"Q{((reference.month - 1) // 3) + 1} {reference.year}",
            topic_count=topic_count,
            status=status,
            next_audit_on=next_audit.date().isoformat(),
            recommendations=recommendations,
        )

    def find_orphan_nodes(self, limit: int = 25) -> list[dict[str, Any]]:
        """Return non-topic nodes that have not yet been assigned to a topic."""

        self.ensure_schema()
        with self._open_session() as session:
            result = session.run(
                """
                MATCH (node)
                WHERE NOT node:Topic
                  AND NOT node:Hub
                  AND NOT (node)-[:BELONGS_TO]->(:Topic)
                RETURN elementId(node) AS node_id,
                       labels(node) AS labels,
                       toString(coalesce(node.name, node.id, elementId(node))) AS name
                ORDER BY name ASC
                LIMIT $limit
                """,
                limit=limit,
            )
            rows = result.data() if hasattr(result, "data") else list(result)
        return [dict(row) for row in rows]

    def suggest_merges(
        self,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.72,
    ) -> list[dict[str, Any]]:
        """Suggest topic merges based on normalized-name similarity."""

        topics = self._load_topics()
        suggestions: list[dict[str, Any]] = []

        for index, left in enumerate(topics):
            for right in topics[index + 1 :]:
                similarity = _topic_similarity(left["name"], right["name"])
                if similarity < similarity_threshold:
                    continue

                if _normalize_topic_name(left["name"]) == _normalize_topic_name(
                    right["name"]
                ):
                    confidence = 1.0
                    reason = "Exact normalized match"
                else:
                    confidence = round(similarity, 2)
                    reason = f"Names are similar (confidence {confidence:.2f})"

                left_weight = int(
                    left.get("relationship_count", left.get("usage_count", 0)) or 0
                )
                right_weight = int(
                    right.get("relationship_count", right.get("usage_count", 0)) or 0
                )
                if (left_weight, left["name"].lower()) >= (
                    right_weight,
                    right["name"].lower(),
                ):
                    to_topic = left["name"]
                    from_topic = right["name"]
                else:
                    to_topic = right["name"]
                    from_topic = left["name"]

                suggestions.append(
                    {
                        "from_topic": from_topic,
                        "to_topic": to_topic,
                        "confidence": confidence,
                        "reason": reason,
                    }
                )

        suggestions.sort(
            key=lambda suggestion: (
                -float(suggestion["confidence"]),
                suggestion["to_topic"].lower(),
                suggestion["from_topic"].lower(),
            )
        )
        return suggestions[:limit]

    def check_topic_health(self, *, merge_limit: int = 10) -> dict[str, Any]:
        """Return topic-capacity health and cleanup hints for the hub."""

        topics = self._load_topics()
        topic_count = len(topics)
        orphan_topics = [
            topic
            for topic in topics
            if int(topic.get("relationship_count", topic.get("usage_count", 0)) or 0) == 0
        ]
        merge_suggestions = self.suggest_merges(limit=merge_limit)
        duplicate_topic_group_count = len(
            {
                _normalize_topic_name(topic["name"])
                for topic in topics
                if sum(
                    1
                    for other in topics
                    if _normalize_topic_name(other["name"])
                    == _normalize_topic_name(topic["name"])
                )
                > 1
            }
        )

        status = "healthy"
        if topic_count >= self.soft_cap:
            status = "soft-cap-exceeded"
        elif topic_count >= self.warn_threshold:
            status = "warning"

        capacity_remaining = max(self.soft_cap - topic_count, 0)
        capacity_used_pct = round((topic_count / self.soft_cap) * 100, 1)

        return {
            "status": status,
            "topic_count": topic_count,
            "soft_cap": self.soft_cap,
            "warning_threshold": self.warn_threshold,
            "warning_threshold_reached": topic_count >= self.warn_threshold,
            "soft_cap_exceeded": topic_count >= self.soft_cap,
            "capacity_used_pct": capacity_used_pct,
            "capacity_remaining": capacity_remaining,
            "orphan_topic_count": len(orphan_topics),
            "orphan_topic_examples": [topic["name"] for topic in orphan_topics[:5]],
            "duplicate_topic_group_count": duplicate_topic_group_count,
            "merge_suggestion_count": len(merge_suggestions),
            "merge_suggestions": merge_suggestions,
        }

    def build_quarterly_audit(self, limit: int = 25) -> dict[str, Any]:
        """Build a detailed quarterly audit payload for docs or dashboards."""

        topic_health = self.check_topic_health(merge_limit=limit)
        orphan_nodes = self.find_orphan_nodes(limit=limit)
        cleanup_actions: list[str] = []

        if topic_health["merge_suggestion_count"]:
            cleanup_actions.append(
                "Merge high-confidence duplicate topics into the most connected canonical node."
            )
        if topic_health["orphan_topic_count"]:
            cleanup_actions.append(
                "Review orphan topics and archive or relink them before the next quarter."
            )
        if orphan_nodes:
            cleanup_actions.append(
                "Assign orphan nodes to the closest topic or remove them if they are obsolete."
            )
        if topic_health["status"] == "soft-cap-exceeded":
            cleanup_actions.append(
                "Freeze new topic creation until the topic list drops back under the soft cap."
            )
        elif topic_health["status"] == "warning":
            cleanup_actions.append(
                "Schedule a cleanup pass this quarter so the topic list stays below the soft cap."
            )
        if not cleanup_actions:
            cleanup_actions.append(
                "No urgent remediation required; continue the quarterly governance cadence."
            )

        return {
            "generated_at": _utc_now_iso(),
            "topic_health": topic_health,
            "orphan_nodes": orphan_nodes,
            "cleanup_actions": cleanup_actions,
        }


def render_audit_report(report: dict[str, Any], *, format: str = "markdown") -> str:
    """Render a quarterly topic audit report for humans."""

    topic_health = report["topic_health"]
    merge_suggestions = topic_health.get("merge_suggestions", [])
    orphan_nodes = report.get("orphan_nodes", [])
    cleanup_actions = report.get("cleanup_actions", [])

    if format == "json":
        return json.dumps(report, indent=2, sort_keys=True)

    if format == "text":
        lines = [
            "Quarterly Topic Audit",
            f"Generated at: {report['generated_at']}",
            "",
            f"Status: {topic_health['status']}",
            f"Topics: {topic_health['topic_count']} / {topic_health['soft_cap']} (warn at {topic_health['warning_threshold']})",
            f"Orphan topics: {topic_health['orphan_topic_count']}",
            f"Merge suggestions: {topic_health['merge_suggestion_count']}",
            "",
            "Suggested topic merges:",
        ]
        if merge_suggestions:
            for item in merge_suggestions:
                lines.append(
                    f"- {item['from_topic']} -> {item['to_topic']} "
                    f"(confidence {float(item['confidence']):.2f}; {item['reason']})"
                )
        else:
            lines.append("- None")

        lines.extend(["", "Orphan nodes:"])
        if orphan_nodes:
            for item in orphan_nodes:
                label_text = ", ".join(item.get("labels", [])) or "unlabelled"
                lines.append(f"- {item['name']} [{label_text}]")
        else:
            lines.append("- None")

        lines.extend(["", "Cleanup actions:"])
        if cleanup_actions:
            lines.extend(f"- {action}" for action in cleanup_actions)
        else:
            lines.append("- None")
        return "\n".join(lines)

    merge_lines = "\n".join(
        f"- Merge `{item['from_topic']}` into `{item['to_topic']}` "
        f"(confidence {float(item['confidence']):.2f}; {item['reason']})"
        for item in merge_suggestions
    ) or "- No merge suggestions."
    orphan_lines = "\n".join(
        f"- `{item['name']}` ({', '.join(item.get('labels', [])) or 'unlabelled'})"
        for item in orphan_nodes
    ) or "- No orphan nodes."
    cleanup_lines = "\n".join(f"- {action}" for action in cleanup_actions) or "- No cleanup actions."

    return (
        "# Quarterly Topic Audit\n\n"
        f"- Generated at: {report['generated_at']}\n"
        f"- Status: {topic_health['status']}\n"
        f"- Topic count: {topic_health['topic_count']} / {topic_health['soft_cap']} "
        f"(warn at {topic_health['warning_threshold']})\n"
        f"- Capacity used: {topic_health['capacity_used_pct']}%\n"
        f"- Orphan topics: {topic_health['orphan_topic_count']}\n"
        f"- Duplicate topic groups: {topic_health['duplicate_topic_group_count']}\n\n"
        "## Suggested topic merges\n"
        f"{merge_lines}\n\n"
        "## Orphan nodes\n"
        f"{orphan_lines}\n\n"
        "## Cleanup actions\n"
        f"{cleanup_lines}\n"
    )
