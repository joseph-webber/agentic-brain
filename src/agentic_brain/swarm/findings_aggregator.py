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
Findings aggregator – collects, deduplicates, and summarises swarm results.

Responsibilities:
- Pull completed results from the Redis results list
- Deduplicate by configurable key
- Merge findings into a structured summary
- Persist the summary to Neo4j (optional, gracefully skipped if unavailable)

Neo4j schema::

    (:SwarmRun {swarm_id, started_at, total_findings, status})
        -[:HAS_FINDING]->
    (:Finding {task_id, swarm_id, category, severity, summary, detail, stored_at})

Example::

    agg = FindingsAggregator(coordinator, swarm_id="pr-review-42")
    summary = agg.aggregate()
    print(summary.human_summary())
    agg.store_to_neo4j(summary)   # idempotent; skipped if Neo4j unavailable
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .redis_coordinator import SwarmCoordinator, _key_results, _loads

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single finding extracted from a task result."""

    task_id: str
    swarm_id: str
    category: str = "general"  # e.g. "bug", "security", "style", "perf"
    severity: str = "info"  # "critical", "high", "medium", "low", "info"
    summary: str = ""
    detail: str = ""
    source_file: Optional[str] = None
    agent_id: Optional[str] = None
    stored_at: float = field(default_factory=time.time)

    @classmethod
    def from_result(cls, result: Dict[str, Any], swarm_id: str) -> Finding:
        """Construct a Finding from a raw task result dict."""
        return cls(
            task_id=result.get("task_id", "unknown"),
            swarm_id=swarm_id,
            category=result.get("category", "general"),
            severity=result.get("severity", "info"),
            summary=result.get("summary", result.get("result", "")),
            detail=result.get("detail", ""),
            source_file=result.get("file") or result.get("source_file"),
            agent_id=result.get("agent_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "swarm_id": self.swarm_id,
            "category": self.category,
            "severity": self.severity,
            "summary": self.summary,
            "detail": self.detail,
            "source_file": self.source_file,
            "agent_id": self.agent_id,
            "stored_at": self.stored_at,
        }


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass
class AggregatedSummary:
    """Full aggregation output for a swarm run."""

    swarm_id: str
    total_results: int
    findings: List[Finding]
    by_category: Dict[str, List[Finding]] = field(default_factory=dict)
    by_severity: Dict[str, List[Finding]] = field(default_factory=dict)
    aggregated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return len(self.by_severity.get("critical", []))

    @property
    def high_count(self) -> int:
        return len(self.by_severity.get("high", []))

    def human_summary(self) -> str:
        """Return a concise human-readable summary string."""
        sev_counts = {sev: len(fs) for sev, fs in self.by_severity.items() if fs}
        parts = [
            f"{c} {s}"
            for s, c in sorted(
                sev_counts.items(), key=lambda x: _SEVERITY_ORDER.get(x[0], 99)
            )
        ]
        cats = list(self.by_category.keys())
        return (
            f"Swarm {self.swarm_id}: {len(self.findings)} findings across "
            f"{len(cats)} categories. Severity breakdown: {', '.join(parts) or 'none'}."
        )

    def top_findings(self, n: int = 5) -> List[Finding]:
        """Return top-n findings sorted by severity."""
        return sorted(
            self.findings,
            key=lambda f: _SEVERITY_ORDER.get(f.severity, 99),
        )[:n]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class FindingsAggregator:
    """
    Collects results from Redis and produces a structured ``AggregatedSummary``.

    The aggregator is read-only with respect to the task queue; it reads from
    the results list but does not modify it (results stay available).
    """

    def __init__(
        self,
        coordinator: SwarmCoordinator,
        swarm_id: str,
        *,
        dedup_key: str = "task_id",
    ) -> None:
        self._c = coordinator
        self._r = coordinator._r
        self.swarm_id = swarm_id
        self.dedup_key = dedup_key

    # ------------------------------------------------------------------
    # Core aggregation
    # ------------------------------------------------------------------

    def aggregate(
        self,
        *,
        raw_results: List[Dict[str, Any]] | None = None,
    ) -> AggregatedSummary:
        """
        Pull and aggregate all results.

        Pass *raw_results* to aggregate an explicit list instead of reading from Redis.
        """
        if raw_results is None:
            raw_list = self._r.lrange(_key_results(self.swarm_id), 0, -1)
            raw_results = [_loads(r) for r in raw_list]

        # Deduplicate
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for r in raw_results:
            key = r.get(self.dedup_key, id(r))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        findings = [Finding.from_result(r, self.swarm_id) for r in unique]

        by_category: Dict[str, List[Finding]] = defaultdict(list)
        by_severity: Dict[str, List[Finding]] = defaultdict(list)
        for f in findings:
            by_category[f.category].append(f)
            by_severity[f.severity].append(f)

        return AggregatedSummary(
            swarm_id=self.swarm_id,
            total_results=len(raw_results),
            findings=findings,
            by_category=dict(by_category),
            by_severity=dict(by_severity),
            metadata={"deduplicated": len(raw_results) - len(unique)},
        )

    def merge(self, summaries: List[AggregatedSummary]) -> AggregatedSummary:
        """
        Merge multiple ``AggregatedSummary`` objects into one.

        Useful when running sub-swarms in parallel.
        """
        all_findings: List[Finding] = []
        seen_task_ids: set = set()
        total_raw = 0
        for s in summaries:
            total_raw += s.total_results
            for f in s.findings:
                if f.task_id not in seen_task_ids:
                    seen_task_ids.add(f.task_id)
                    all_findings.append(f)

        by_category: Dict[str, List[Finding]] = defaultdict(list)
        by_severity: Dict[str, List[Finding]] = defaultdict(list)
        for f in all_findings:
            by_category[f.category].append(f)
            by_severity[f.severity].append(f)

        return AggregatedSummary(
            swarm_id=self.swarm_id,
            total_results=total_raw,
            findings=all_findings,
            by_category=dict(by_category),
            by_severity=dict(by_severity),
            metadata={"merged_swarms": [s.swarm_id for s in summaries]},
        )

    # ------------------------------------------------------------------
    # Neo4j persistence
    # ------------------------------------------------------------------

    def store_to_neo4j(
        self,
        summary: AggregatedSummary,
        *,
        neo4j_session: Any = None,
    ) -> bool:
        """
        Persist the summary to Neo4j.

        Accepts an explicit *neo4j_session* (for testing) or lazily imports
        from ``agentic_brain.core.neo4j_pool``.  Returns True on success,
        False if Neo4j is unavailable (so callers need not guard).
        """
        try:
            session = neo4j_session or self._get_neo4j_session()
            if session is None:
                logger.warning(
                    "Neo4j unavailable – skipping persistence for swarm %s",
                    self.swarm_id,
                )
                return False

            run_cypher = """
            MERGE (sr:SwarmRun {swarm_id: $swarm_id})
            SET sr.stored_at = $stored_at,
                sr.total_findings = $total_findings,
                sr.human_summary = $human_summary
            """
            session.run(
                run_cypher,
                {
                    "swarm_id": summary.swarm_id,
                    "stored_at": summary.aggregated_at,
                    "total_findings": len(summary.findings),
                    "human_summary": summary.human_summary(),
                },
            )

            for finding in summary.findings:
                finding_cypher = """
                MATCH (sr:SwarmRun {swarm_id: $swarm_id})
                MERGE (f:Finding {task_id: $task_id, swarm_id: $swarm_id})
                SET f.category = $category,
                    f.severity = $severity,
                    f.summary = $summary,
                    f.detail = $detail,
                    f.source_file = $source_file,
                    f.agent_id = $agent_id,
                    f.stored_at = $stored_at
                MERGE (sr)-[:HAS_FINDING]->(f)
                """
                session.run(finding_cypher, finding.to_dict())

            logger.info(
                "Stored %d findings for swarm %s to Neo4j",
                len(summary.findings),
                self.swarm_id,
            )
            return True

        except Exception:
            logger.exception(
                "Failed to store findings to Neo4j for swarm %s", self.swarm_id
            )
            return False

    def _get_neo4j_session(self) -> Any:
        """Lazy Neo4j session, returns None if unavailable."""
        try:
            from agentic_brain.core.neo4j_pool import get_session

            return get_session()
        except Exception:
            return None
