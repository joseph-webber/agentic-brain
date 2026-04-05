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
Tests for the swarm coordination subsystem.

All tests run against ``fakeredis`` – no live Redis required.
Tests that need a real Redis are marked ``requires_redis``.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

fakeredis = pytest.importorskip("fakeredis", reason="fakeredis required")

from agentic_brain.swarm import (
    AgentProfile,
    AgentRegistry,
    AggregatedSummary,
    CoordinationEvent,
    Finding,
    FindingsAggregator,
    SwarmCoordinator,
    SwarmStatus,
    TaskQueue,
    TaskState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_coordinator(swarm_id: str | None = None) -> tuple[SwarmCoordinator, str]:
    """Return (coordinator, swarm_id) backed by fakeredis."""
    r = fakeredis.FakeRedis(decode_responses=True)
    coord = SwarmCoordinator(r)
    sid = swarm_id or f"test-swarm-{uuid.uuid4().hex[:6]}"
    return coord, sid


def _fake_registry(
    swarm_id: str | None = None,
) -> tuple[SwarmCoordinator, AgentRegistry, str]:
    coord, sid = _fake_coordinator(swarm_id)
    registry = AgentRegistry(coord, sid)
    return coord, registry, sid


def _fake_queue(swarm_id: str | None = None) -> tuple[SwarmCoordinator, TaskQueue, str]:
    coord, sid = _fake_coordinator(swarm_id)
    queue = TaskQueue(coord, sid, visibility_timeout=2, max_retries=2)
    return coord, queue, sid


def _fake_aggregator(
    swarm_id: str | None = None,
) -> tuple[SwarmCoordinator, FindingsAggregator, str]:
    coord, sid = _fake_coordinator(swarm_id)
    agg = FindingsAggregator(coord, sid)
    return coord, agg, sid


# ---------------------------------------------------------------------------
# SwarmCoordinator
# ---------------------------------------------------------------------------


class TestSwarmCoordinator:
    def test_ping(self):
        coord, _ = _fake_coordinator()
        assert coord.ping() is True

    def test_start_swarm_sets_status(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid, total_tasks=5)
        status = coord.swarm_status(sid)
        assert status["status"] == SwarmStatus.RUNNING
        assert int(status["total_tasks"]) == 5

    def test_finish_swarm(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        coord.finish_swarm(sid)
        status = coord.swarm_status(sid)
        assert status["status"] == SwarmStatus.COMPLETED

    def test_finish_swarm_failed(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        coord.finish_swarm(sid, status=SwarmStatus.FAILED)
        status = coord.swarm_status(sid)
        assert status["status"] == SwarmStatus.FAILED

    def test_register_and_active_agents(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        coord.register_agent(sid, "a1", capabilities=["python"])
        coord.register_agent(sid, "a2", capabilities=["go"])
        active = coord.active_agents(sid)
        assert "a1" in active
        assert "a2" in active

    def test_heartbeat_expiry(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        coord.register_agent(sid, "a1", ttl=1)
        active = coord.active_agents(sid)
        assert "a1" in active
        # TTL expires
        time.sleep(1.2)
        active_after = coord.active_agents(sid)
        assert "a1" not in active_after

    def test_deregister_agent(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        coord.register_agent(sid, "a1")
        coord.deregister_agent(sid, "a1")
        assert "a1" not in coord.active_agents(sid)

    def test_push_and_pull_task(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid, total_tasks=1)
        coord.push_task(sid, {"action": "review"})
        task = coord.pull_task(sid)
        assert task is not None
        assert task["action"] == "review"
        assert "task_id" in task

    def test_push_and_get_results(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        coord.push_result(sid, {"task_id": "t1", "result": "ok"})
        results = coord.get_results(sid)
        assert len(results) == 1
        assert results[0]["result"] == "ok"

    def test_results_count(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        for i in range(3):
            coord.push_result(sid, {"task_id": f"t{i}"})
        assert coord.results_count(sid) == 3

    def test_publish_and_subscribe(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        received: List[CoordinationEvent] = []

        def handle(event: CoordinationEvent) -> None:
            received.append(event)

        thread = coord.listen_in_thread(sid, handle)

        time.sleep(0.05)
        coord.publish(
            sid,
            CoordinationEvent(event_type="test_event", swarm_id=sid, payload={"x": 1}),
        )
        time.sleep(0.15)
        coord.shutdown()
        thread.join(timeout=2)

        assert any(e.event_type == "test_event" for e in received)

    def test_context_manager_shuts_down(self):
        r = fakeredis.FakeRedis(decode_responses=True)
        with SwarmCoordinator(r) as coord:
            assert coord.ping()
        assert coord._shutdown.is_set()

    def test_swarm_status_includes_queue_depths(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        coord.push_task(sid, {"x": 1})
        coord.push_result(sid, {"task_id": "t1"})
        status = coord.swarm_status(sid)
        assert status["pending_tasks"] == 1
        assert status["collected_results"] == 1

    def test_pull_task_nonblocking_empty(self):
        coord, sid = _fake_coordinator()
        coord.start_swarm(sid)
        assert coord.pull_task(sid) is None

    def test_coordination_event_roundtrip(self):
        event = CoordinationEvent(
            event_type="ping", swarm_id="s1", agent_id="a1", payload={"k": "v"}
        )
        d = event.to_dict()
        restored = CoordinationEvent.from_dict(d)
        assert restored.event_type == "ping"
        assert restored.swarm_id == "s1"
        assert restored.payload == {"k": "v"}


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------


class TestAgentRegistry:
    def test_register_and_get(self):
        _, reg, _ = _fake_registry()
        profile = reg.register("a1", capabilities=["python", "review"])
        assert profile.agent_id == "a1"
        assert "python" in profile.capabilities

    def test_auto_generate_id(self):
        _, reg, _ = _fake_registry()
        profile = reg.register(capabilities=["go"])
        assert len(profile.agent_id) > 0

    def test_all_active(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", capabilities=["python"])
        reg.register("a2", capabilities=["go"])
        profiles = reg.all_active()
        ids = {p.agent_id for p in profiles}
        assert {"a1", "a2"} == ids

    def test_with_capability(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", capabilities=["python", "review"])
        reg.register("a2", capabilities=["go"])
        found = reg.with_capability("python")
        assert len(found) == 1
        assert found[0].agent_id == "a1"

    def test_with_capabilities_all_required(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", capabilities=["python", "git", "review"])
        reg.register("a2", capabilities=["python"])
        found = reg.with_capabilities(["python", "review"])
        assert len(found) == 1
        assert found[0].agent_id == "a1"

    def test_pick_least_loaded(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", capabilities=["python"])
        reg.register("a2", capabilities=["python"])
        reg.increment_workload("a1")
        reg.increment_workload("a1")
        picked = reg.pick(required_capabilities=["python"])
        assert picked is not None
        assert picked.agent_id == "a2"

    def test_pick_random(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", capabilities=["python"])
        reg.register("a2", capabilities=["python"])
        picked = reg.pick(required_capabilities=["python"], strategy="random")
        assert picked is not None
        assert picked.agent_id in ("a1", "a2")

    def test_pick_returns_none_if_no_candidates(self):
        _, reg, _ = _fake_registry()
        assert reg.pick(required_capabilities=["java"]) is None

    def test_increment_decrement_workload(self):
        _, reg, _ = _fake_registry()
        reg.register("a1")
        assert reg.increment_workload("a1") == 1
        assert reg.increment_workload("a1") == 2
        assert reg.decrement_workload("a1") == 1

    def test_workload_floor_at_zero(self):
        _, reg, _ = _fake_registry()
        reg.register("a1")
        val = reg.decrement_workload("a1")
        assert val == 0

    def test_health_check_alive(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", capabilities=["python"])
        report = reg.health_check("a1")
        assert report["healthy"] is True
        assert report["capabilities"] == ["python"]

    def test_health_check_dead(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", ttl=1)
        time.sleep(1.2)
        report = reg.health_check("a1")
        assert report["healthy"] is False
        assert "heartbeat_expired" in report["reason"]

    def test_health_report(self):
        _, reg, _ = _fake_registry()
        reg.register("a1")
        reg.register("a2")
        reports = reg.health_report()
        assert len(reports) == 2

    def test_prune_dead_agents(self):
        _, reg, _ = _fake_registry()
        reg.register("a1", ttl=1)
        reg.register("a2", ttl=60)
        time.sleep(1.2)
        pruned = reg.prune_dead_agents()
        assert "a1" in pruned
        alive = reg.all_active()
        assert all(p.agent_id != "a1" for p in alive)

    def test_deregister(self):
        _, reg, _ = _fake_registry()
        reg.register("a1")
        reg.deregister("a1")
        assert reg.get("a1") is None


# ---------------------------------------------------------------------------
# TaskQueue
# ---------------------------------------------------------------------------


class TestTaskQueue:
    def test_enqueue_and_claim(self):
        _, queue, _ = _fake_queue()
        tid = queue.enqueue({"action": "review", "file": "main.py"})
        task = queue.claim(agent_id="worker-1")
        assert task is not None
        assert task["task_id"] == tid
        assert task["agent_id"] == "worker-1"

    def test_enqueue_many(self):
        _, queue, _ = _fake_queue()
        tids = queue.enqueue_many([{"n": i} for i in range(5)])
        assert len(tids) == 5
        stats = queue.stats()
        assert stats["pending"] == 5

    def test_complete_moves_to_results(self):
        coord, queue, sid = _fake_queue()
        tid = queue.enqueue({"action": "test"})
        task = queue.claim()
        result = queue.complete(task["task_id"], result={"issues": 0})
        assert result.state == TaskState.COMPLETED
        results = coord.get_results(sid)
        assert len(results) == 1
        assert results[0]["result"] == {"issues": 0}

    def test_fail_retries_then_dead_letter(self):
        _, queue, _ = _fake_queue()
        tid = queue.enqueue({"action": "bad"})

        # First attempt
        task = queue.claim()
        r1 = queue.fail(task["task_id"], error="oops")
        assert r1.state == TaskState.PENDING  # re-queued

        # Second attempt
        task = queue.claim()
        r2 = queue.fail(task["task_id"], error="oops again")
        assert r2.state == TaskState.PENDING  # still re-queued (retry 2)

        # Third attempt → exhausted → dead letter
        task = queue.claim()
        r3 = queue.fail(task["task_id"], error="final")
        assert r3.state == TaskState.FAILED

        dead = queue.failed_tasks()
        assert len(dead) == 1
        assert dead[0]["error"] == "final"

    def test_stats(self):
        coord, queue, sid = _fake_queue()
        queue.enqueue({"a": 1})
        queue.enqueue({"b": 2})
        t = queue.claim()
        queue.complete(t["task_id"], result="done")
        stats = queue.stats()
        assert stats["pending"] == 1
        assert stats["inflight"] == 0
        assert stats["completed"] == 1
        assert stats["failed"] == 0

    def test_requeue_stalled(self):
        _, queue, _ = _fake_queue()
        queue.enqueue({"x": 1})
        queue.claim()  # moves to inflight
        # Wait for visibility timeout (2s in our fixture)
        time.sleep(2.5)
        requeued = queue.requeue_stalled()
        assert len(requeued) == 1
        stats = queue.stats()
        assert stats["pending"] == 1
        assert stats["inflight"] == 0

    def test_empty_claim_returns_none(self):
        _, queue, _ = _fake_queue()
        assert queue.claim() is None

    def test_inflight_tracked_until_complete(self):
        _, queue, _ = _fake_queue()
        queue.enqueue({"x": 1})
        queue.claim()
        stats = queue.stats()
        assert stats["inflight"] == 1

    def test_failed_tasks_with_limit(self):
        _, queue, _ = _fake_queue()
        # Exhaust retries for 2 tasks
        for i in range(2):
            queue.enqueue({"i": i})
        for _ in range(2):
            for __ in range(3):  # max_retries=2 → 3 claims to dead-letter
                t = queue.claim()
                if t:
                    queue.fail(t["task_id"], error="err")
        failed = queue.failed_tasks(limit=1)
        assert len(failed) == 1


# ---------------------------------------------------------------------------
# FindingsAggregator
# ---------------------------------------------------------------------------


class TestFindingsAggregator:
    def _push_results(
        self, coord: SwarmCoordinator, sid: str, results: List[Dict[str, Any]]
    ) -> None:
        for r in results:
            coord.push_result(sid, r)

    def test_aggregate_empty(self):
        coord, agg, sid = _fake_aggregator()
        summary = agg.aggregate()
        assert summary.total_results == 0
        assert summary.findings == []

    def test_aggregate_basic(self):
        coord, agg, sid = _fake_aggregator()
        self._push_results(
            coord,
            sid,
            [
                {
                    "task_id": "t1",
                    "severity": "high",
                    "category": "bug",
                    "summary": "null ptr",
                },
                {
                    "task_id": "t2",
                    "severity": "low",
                    "category": "style",
                    "summary": "whitespace",
                },
            ],
        )
        summary = agg.aggregate()
        assert summary.total_results == 2
        assert len(summary.findings) == 2
        assert "bug" in summary.by_category
        assert "style" in summary.by_category

    def test_deduplication(self):
        coord, agg, sid = _fake_aggregator()
        self._push_results(
            coord,
            sid,
            [
                {"task_id": "t1", "summary": "dup"},
                {"task_id": "t1", "summary": "dup again"},  # same task_id
            ],
        )
        summary = agg.aggregate()
        assert summary.total_results == 2
        assert len(summary.findings) == 1  # deduplicated
        assert summary.metadata["deduplicated"] == 1

    def test_severity_grouping(self):
        coord, agg, sid = _fake_aggregator()
        self._push_results(
            coord,
            sid,
            [
                {"task_id": "t1", "severity": "critical", "category": "security"},
                {"task_id": "t2", "severity": "critical", "category": "security"},
                {"task_id": "t3", "severity": "info", "category": "style"},
            ],
        )
        summary = agg.aggregate()
        assert summary.critical_count == 2
        assert len(summary.by_severity.get("info", [])) == 1

    def test_top_findings_sorted_by_severity(self):
        coord, agg, sid = _fake_aggregator()
        self._push_results(
            coord,
            sid,
            [
                {"task_id": "t1", "severity": "info"},
                {"task_id": "t2", "severity": "critical"},
                {"task_id": "t3", "severity": "high"},
            ],
        )
        summary = agg.aggregate()
        top = summary.top_findings(2)
        assert top[0].severity == "critical"
        assert top[1].severity == "high"

    def test_human_summary(self):
        coord, agg, sid = _fake_aggregator()
        self._push_results(
            coord,
            sid,
            [
                {"task_id": "t1", "severity": "high", "category": "bug"},
            ],
        )
        summary = agg.aggregate()
        text = summary.human_summary()
        assert "high" in text
        assert sid in text

    def test_aggregate_from_raw_results(self):
        _, agg, sid = _fake_aggregator()
        raw = [
            {"task_id": "x1", "severity": "medium", "category": "perf"},
            {"task_id": "x2", "severity": "low", "category": "style"},
        ]
        summary = agg.aggregate(raw_results=raw)
        assert len(summary.findings) == 2

    def test_merge_summaries(self):
        coord, agg, sid = _fake_aggregator()
        s1 = agg.aggregate(
            raw_results=[
                {"task_id": "t1", "severity": "high", "category": "bug"},
            ]
        )
        s2 = agg.aggregate(
            raw_results=[
                {"task_id": "t2", "severity": "low", "category": "style"},
                {"task_id": "t1", "severity": "high", "category": "bug"},  # duplicate
            ]
        )
        merged = agg.merge([s1, s2])
        assert len(merged.findings) == 2  # deduped
        assert merged.total_results == 3

    def test_finding_from_result(self):
        result = {
            "task_id": "t1",
            "severity": "critical",
            "category": "security",
            "summary": "SQL injection",
            "detail": "line 42",
            "file": "db.py",
            "agent_id": "agent-1",
        }
        f = Finding.from_result(result, "my-swarm")
        assert f.task_id == "t1"
        assert f.severity == "critical"
        assert f.source_file == "db.py"
        assert f.agent_id == "agent-1"

    def test_store_to_neo4j_gracefully_skips_if_unavailable(self):
        coord, agg, sid = _fake_aggregator()
        summary = agg.aggregate(raw_results=[{"task_id": "t1", "severity": "info"}])
        # No real Neo4j – should return False and not raise
        result = agg.store_to_neo4j(summary)
        assert result is False

    def test_store_to_neo4j_with_mock_session(self):
        coord, agg, sid = _fake_aggregator()
        summary = agg.aggregate(
            raw_results=[
                {
                    "task_id": "t1",
                    "severity": "high",
                    "category": "bug",
                    "summary": "oops",
                },
            ]
        )
        mock_session = MagicMock()
        mock_session.run = MagicMock()
        result = agg.store_to_neo4j(summary, neo4j_session=mock_session)
        assert result is True
        assert mock_session.run.call_count >= 2  # SwarmRun + 1 Finding


# ---------------------------------------------------------------------------
# Integration-style: full swarm lifecycle
# ---------------------------------------------------------------------------


class TestSwarmLifecycle:
    """End-to-end swarm scenario with all components wired together."""

    def test_full_lifecycle(self):
        coord, sid = _fake_coordinator()
        registry = AgentRegistry(coord, sid)
        queue = TaskQueue(coord, sid, max_retries=1)
        agg = FindingsAggregator(coord, sid)

        # 1. Start swarm
        coord.start_swarm(sid, total_tasks=3)

        # 2. Register agents
        registry.register("worker-1", capabilities=["review"])
        registry.register("worker-2", capabilities=["review", "security"])

        # 3. Enqueue tasks
        queue.enqueue_many(
            [
                {"action": "review", "file": "auth.py"},
                {"action": "review", "file": "api.py"},
                {"action": "security_scan", "file": "auth.py"},
            ]
        )

        # 4. Process all tasks
        while True:
            agent = registry.pick(required_capabilities=["review"])
            task = queue.claim(agent_id=agent.agent_id if agent else None)
            if task is None:
                break
            registry.increment_workload(task["agent_id"] or "worker-1")
            queue.complete(
                task["task_id"],
                result={
                    "issues": 0,
                    "severity": "info",
                    "category": "code_quality",
                    "summary": f"Clean: {task.get('file')}",
                },
            )
            registry.decrement_workload(task["agent_id"] or "worker-1")

        # 5. Aggregate
        summary = agg.aggregate()
        assert len(summary.findings) == 3
        assert all(f.severity == "info" for f in summary.findings)

        # 6. Finish
        coord.finish_swarm(sid)
        status = coord.swarm_status(sid)
        assert status["status"] == SwarmStatus.COMPLETED

    def test_stall_and_recovery(self):
        coord, sid = _fake_coordinator()
        queue = TaskQueue(coord, sid, visibility_timeout=1, max_retries=3)

        coord.start_swarm(sid, total_tasks=1)
        queue.enqueue({"action": "flakey"})

        # Claim and "crash" (never complete or fail)
        task = queue.claim(agent_id="crash-prone-worker")
        assert task is not None

        # Wait for visibility timeout
        time.sleep(1.5)
        requeued = queue.requeue_stalled()
        assert len(requeued) == 1

        # Second worker picks it up and completes
        task2 = queue.claim(agent_id="reliable-worker")
        assert task2 is not None
        queue.complete(task2["task_id"], result="done")

        stats = queue.stats()
        assert stats["pending"] == 0
        assert stats["inflight"] == 0
        assert stats["completed"] == 1
