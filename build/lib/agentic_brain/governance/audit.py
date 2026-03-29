# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""
Audit Trail System
==================

Comprehensive audit logging for AI governance and compliance.
Records all significant actions, decisions, and data access for regulatory compliance.

Features:
  - Immutable audit event records
  - Actor, action, resource tracking
  - Compliance exports (JSON, CSV)
  - Time-based and filter-based querying
  - Neo4j or in-memory storage backends

Example:
    >>> from agentic_brain.governance import AuditLog, AuditEvent
    >>> audit = AuditLog()
    >>> audit.record("user:123", "query", "model:gpt-4", details={"prompt": "Hello"})
    >>> events = audit.query(actor="user:123", limit=10)
    >>> audit.export_json("audit_report.json")
"""

from __future__ import annotations

import csv
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditOutcome(StrEnum):
    """Outcome status for audit events."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    DENIED = "denied"
    PENDING = "pending"


class AuditCategory(StrEnum):
    """Categories for audit events."""

    DATA_ACCESS = "data_access"
    MODEL_INFERENCE = "model_inference"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ADMIN = "admin"
    SYSTEM = "system"
    COMPLIANCE = "compliance"


@dataclass
class AuditEvent:
    """
    A single audit event record.

    Represents an immutable record of an action taken within the system.
    Contains all context needed for compliance auditing and forensics.

    Attributes:
        timestamp: ISO 8601 timestamp when the event occurred
        action: The action performed (e.g., 'create', 'read', 'update', 'delete', 'query')
        actor: Identifier of who/what performed the action (e.g., 'user:123', 'system:scheduler')
        resource: The resource affected (e.g., 'model:gpt-4', 'data:customer-records')
        details: Additional context about the event
        outcome: Result of the action (success, failure, etc.)
        event_id: Unique identifier for this event
        category: Category of the event for filtering
        ip_address: Source IP address if applicable
        session_id: Associated session identifier
        duration_ms: Duration of the action in milliseconds
        metadata: Additional metadata for extensibility
    """

    timestamp: str
    action: str
    actor: str
    resource: str
    details: dict[str, Any] = field(default_factory=dict)
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: AuditCategory = AuditCategory.SYSTEM
    ip_address: str | None = None
    session_id: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a dictionary."""
        data = asdict(self)
        # Convert enums to their values
        data["outcome"] = self.outcome.value
        data["category"] = self.category.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        """Create an AuditEvent from a dictionary."""
        # Convert string values back to enums
        if isinstance(data.get("outcome"), str):
            data["outcome"] = AuditOutcome(data["outcome"])
        if isinstance(data.get("category"), str):
            data["category"] = AuditCategory(data["category"])
        return cls(**data)


class AuditLog:
    """
    Audit log manager for recording and querying audit events.

    Provides a central interface for recording security-relevant events
    and querying them for compliance and forensic purposes.

    Supports both in-memory storage (for testing) and Neo4j persistence
    (for production).

    Example:
        >>> audit = AuditLog()
        >>> event = audit.record(
        ...     actor="user:admin",
        ...     action="create",
        ...     resource="agent:customer-support",
        ...     details={"config": {"model": "gpt-4"}}
        ... )
        >>> print(event.event_id)
    """

    def __init__(self, driver=None):
        """
        Initialize the audit log.

        Args:
            driver: Optional Neo4j driver. If None, uses in-memory storage.
        """
        self.driver = driver
        self._events: list[AuditEvent] = []  # In-memory fallback

        if driver:
            self._create_indexes()

    def _create_indexes(self):
        """Create Neo4j indexes for efficient querying."""
        if not self.driver:
            return

        queries = [
            "CREATE INDEX audit_event_id IF NOT EXISTS FOR (e:AuditEvent) ON (e.event_id)",
            "CREATE INDEX audit_timestamp IF NOT EXISTS FOR (e:AuditEvent) ON (e.timestamp)",
            "CREATE INDEX audit_actor IF NOT EXISTS FOR (e:AuditEvent) ON (e.actor)",
            "CREATE INDEX audit_action IF NOT EXISTS FOR (e:AuditEvent) ON (e.action)",
            "CREATE INDEX audit_resource IF NOT EXISTS FOR (e:AuditEvent) ON (e.resource)",
            "CREATE INDEX audit_category IF NOT EXISTS FOR (e:AuditEvent) ON (e.category)",
        ]

        with self.driver.session() as session:
            for query in queries:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug(f"Index creation info: {e}")

    def record(
        self,
        actor: str,
        action: str,
        resource: str,
        details: dict[str, Any] | None = None,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        category: AuditCategory = AuditCategory.SYSTEM,
        ip_address: str | None = None,
        session_id: str | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """
        Record an audit event.

        Args:
            actor: Who/what performed the action
            action: The action performed
            resource: The resource affected
            details: Additional context
            outcome: Result of the action
            category: Event category
            ip_address: Source IP address
            session_id: Associated session
            duration_ms: Action duration
            metadata: Additional metadata

        Returns:
            The created AuditEvent
        """
        event = AuditEvent(
            timestamp=datetime.now(UTC).isoformat(),
            action=action,
            actor=actor,
            resource=resource,
            details=details or {},
            outcome=outcome,
            category=category,
            ip_address=ip_address,
            session_id=session_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        if self.driver:
            self._persist_event(event)
        else:
            self._events.append(event)

        logger.debug(
            f"Recorded audit event: {event.event_id} - {action} on {resource} by {actor}"
        )
        return event

    def _persist_event(self, event: AuditEvent):
        """Persist an event to Neo4j."""
        query = """
        CREATE (e:AuditEvent {
            event_id: $event_id,
            timestamp: $timestamp,
            action: $action,
            actor: $actor,
            resource: $resource,
            details: $details,
            outcome: $outcome,
            category: $category,
            ip_address: $ip_address,
            session_id: $session_id,
            duration_ms: $duration_ms,
            metadata: $metadata
        })
        """

        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    {
                        "event_id": event.event_id,
                        "timestamp": event.timestamp,
                        "action": event.action,
                        "actor": event.actor,
                        "resource": event.resource,
                        "details": json.dumps(event.details),
                        "outcome": event.outcome.value,
                        "category": event.category.value,
                        "ip_address": event.ip_address,
                        "session_id": event.session_id,
                        "duration_ms": event.duration_ms,
                        "metadata": json.dumps(event.metadata),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to persist audit event: {e}")
            # Fall back to in-memory storage
            self._events.append(event)

    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        category: AuditCategory | None = None,
        outcome: AuditOutcome | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """
        Query audit events with filters.

        Args:
            actor: Filter by actor
            action: Filter by action
            resource: Filter by resource
            category: Filter by category
            outcome: Filter by outcome
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp
            limit: Maximum events to return
            offset: Number of events to skip

        Returns:
            List of matching AuditEvents
        """
        if self.driver:
            return self._query_neo4j(
                actor,
                action,
                resource,
                category,
                outcome,
                start_time,
                end_time,
                limit,
                offset,
            )
        return self._query_memory(
            actor,
            action,
            resource,
            category,
            outcome,
            start_time,
            end_time,
            limit,
            offset,
        )

    def _query_memory(
        self,
        actor: str | None,
        action: str | None,
        resource: str | None,
        category: AuditCategory | None,
        outcome: AuditOutcome | None,
        start_time: str | None,
        end_time: str | None,
        limit: int,
        offset: int,
    ) -> list[AuditEvent]:
        """Query in-memory events."""
        filtered = []

        for event in self._events:
            if actor and event.actor != actor:
                continue
            if action and event.action != action:
                continue
            if resource and event.resource != resource:
                continue
            if category and event.category != category:
                continue
            if outcome and event.outcome != outcome:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            filtered.append(event)

        # Sort by timestamp descending (newest first)
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered[offset : offset + limit]

    def _query_neo4j(
        self,
        actor: str | None,
        action: str | None,
        resource: str | None,
        category: AuditCategory | None,
        outcome: AuditOutcome | None,
        start_time: str | None,
        end_time: str | None,
        limit: int,
        offset: int,
    ) -> list[AuditEvent]:
        """Query Neo4j for events."""
        conditions = ["1=1"]  # Always true to simplify query building
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if actor:
            conditions.append("e.actor = $actor")
            params["actor"] = actor
        if action:
            conditions.append("e.action = $action")
            params["action"] = action
        if resource:
            conditions.append("e.resource = $resource")
            params["resource"] = resource
        if category:
            conditions.append("e.category = $category")
            params["category"] = category.value
        if outcome:
            conditions.append("e.outcome = $outcome")
            params["outcome"] = outcome.value
        if start_time:
            conditions.append("e.timestamp >= $start_time")
            params["start_time"] = start_time
        if end_time:
            conditions.append("e.timestamp <= $end_time")
            params["end_time"] = end_time

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (e:AuditEvent)
        WHERE {where_clause}
        RETURN e
        ORDER BY e.timestamp DESC
        SKIP $offset
        LIMIT $limit
        """

        events = []
        try:
            with self.driver.session() as session:
                result = session.run(query, params)
                for record in result:
                    node = record["e"]
                    event_data = dict(node)
                    # Parse JSON fields
                    if "details" in event_data and isinstance(
                        event_data["details"], str
                    ):
                        event_data["details"] = json.loads(event_data["details"])
                    if "metadata" in event_data and isinstance(
                        event_data["metadata"], str
                    ):
                        event_data["metadata"] = json.loads(event_data["metadata"])
                    events.append(AuditEvent.from_dict(event_data))
        except Exception as e:
            logger.error(f"Failed to query audit events: {e}")

        return events

    def get_event(self, event_id: str) -> AuditEvent | None:
        """
        Get a specific event by ID.

        Args:
            event_id: The event ID to look up

        Returns:
            The AuditEvent or None if not found
        """
        if self.driver:
            query = "MATCH (e:AuditEvent {event_id: $event_id}) RETURN e"
            try:
                with self.driver.session() as session:
                    result = session.run(query, {"event_id": event_id})
                    record = result.single()
                    if record:
                        node = record["e"]
                        event_data = dict(node)
                        if "details" in event_data and isinstance(
                            event_data["details"], str
                        ):
                            event_data["details"] = json.loads(event_data["details"])
                        if "metadata" in event_data and isinstance(
                            event_data["metadata"], str
                        ):
                            event_data["metadata"] = json.loads(event_data["metadata"])
                        return AuditEvent.from_dict(event_data)
            except Exception as e:
                logger.error(f"Failed to get audit event: {e}")
        else:
            for event in self._events:
                if event.event_id == event_id:
                    return event
        return None

    def count(
        self,
        actor: str | None = None,
        action: str | None = None,
        category: AuditCategory | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        """
        Count events matching the filters.

        Args:
            actor: Filter by actor
            action: Filter by action
            category: Filter by category
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp

        Returns:
            Count of matching events
        """
        events = self.query(
            actor=actor,
            action=action,
            category=category,
            start_time=start_time,
            end_time=end_time,
            limit=100000,  # High limit to get total count
        )
        return len(events)

    def get_statistics(
        self,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get audit statistics for a time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            Statistics dictionary
        """
        start_time = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        events = self.query(start_time=start_time, limit=100000)

        if not events:
            return {
                "total_events": 0,
                "time_period_hours": hours,
                "events_by_action": {},
                "events_by_category": {},
                "events_by_outcome": {},
                "unique_actors": 0,
                "unique_resources": 0,
            }

        events_by_action: dict[str, int] = {}
        events_by_category: dict[str, int] = {}
        events_by_outcome: dict[str, int] = {}
        actors = set()
        resources = set()

        for event in events:
            events_by_action[event.action] = events_by_action.get(event.action, 0) + 1
            events_by_category[event.category.value] = (
                events_by_category.get(event.category.value, 0) + 1
            )
            events_by_outcome[event.outcome.value] = (
                events_by_outcome.get(event.outcome.value, 0) + 1
            )
            actors.add(event.actor)
            resources.add(event.resource)

        return {
            "total_events": len(events),
            "time_period_hours": hours,
            "events_by_action": events_by_action,
            "events_by_category": events_by_category,
            "events_by_outcome": events_by_outcome,
            "unique_actors": len(actors),
            "unique_resources": len(resources),
        }

    def export_json(
        self,
        output_path: str,
        start_time: str | None = None,
        end_time: str | None = None,
        indent: int = 2,
    ) -> int:
        """
        Export audit events to JSON file.

        Args:
            output_path: Path to output file
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp
            indent: JSON indentation level

        Returns:
            Number of events exported
        """
        events = self.query(start_time=start_time, end_time=end_time, limit=100000)

        export_data = {
            "export_timestamp": datetime.now(UTC).isoformat(),
            "event_count": len(events),
            "filters": {
                "start_time": start_time,
                "end_time": end_time,
            },
            "events": [event.to_dict() for event in events],
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=indent)

        logger.info(f"Exported {len(events)} audit events to {output_path}")
        return len(events)

    def export_csv(
        self,
        output_path: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        """
        Export audit events to CSV file.

        Args:
            output_path: Path to output file
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp

        Returns:
            Number of events exported
        """
        events = self.query(start_time=start_time, end_time=end_time, limit=100000)

        fieldnames = [
            "event_id",
            "timestamp",
            "actor",
            "action",
            "resource",
            "outcome",
            "category",
            "ip_address",
            "session_id",
            "duration_ms",
            "details",
            "metadata",
        ]

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for event in events:
                row = {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp,
                    "actor": event.actor,
                    "action": event.action,
                    "resource": event.resource,
                    "outcome": event.outcome.value,
                    "category": event.category.value,
                    "ip_address": event.ip_address or "",
                    "session_id": event.session_id or "",
                    "duration_ms": event.duration_ms or "",
                    "details": json.dumps(event.details) if event.details else "",
                    "metadata": json.dumps(event.metadata) if event.metadata else "",
                }
                writer.writerow(row)

        logger.info(f"Exported {len(events)} audit events to {output_path}")
        return len(events)

    def clear(self) -> int:
        """
        Clear all events (in-memory only, for testing).

        Returns:
            Number of events cleared
        """
        count = len(self._events)
        self._events = []
        return count
