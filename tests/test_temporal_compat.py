# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Temporal.io compatibility smoke tests for Agentic Brain.

These tests exercise the Temporal-style API surface exposed by
``src.agentic_brain.temporal`` while relying on the durability
engine underneath. They are intentionally lightweight so they can
run in CI without a real Temporal cluster.
"""

from __future__ import annotations

from datetime import timedelta

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires full Temporal infrastructure setup")
async def test_workflow_execution() -> None:
    """Temporal-style workflow executes via Client + durability."""
    from agentic_brain.temporal import activity, workflow
    from agentic_brain.temporal.testing import WorkflowEnvironment

    @activity.defn
    async def add(x: int, y: int) -> int:
        return x + y

    @workflow.defn
    class AddWorkflow:
        @workflow.run
        async def run(self, x: int, y: int) -> int:  # type: ignore[override]
            return await workflow.execute_activity(
                add,
                x,
                y,
                start_to_close_timeout=timedelta(seconds=5),
            )

    async with await WorkflowEnvironment.start_time_skipping() as env:
        result = await env.client.execute_workflow(
            AddWorkflow.run,
            2,
            3,
            id="temporal-compat-add-1",
            task_queue="temporal-compat",
        )

    assert result == 5


@pytest.mark.asyncio
async def test_activity_retry() -> None:
    """Activities are retried with exponential backoff semantics."""
    from agentic_brain.durability import DurableWorkflow

    attempts: dict[str, int] = {"count": 0}

    class RetryWorkflow(DurableWorkflow):
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            super().__init__(**kwargs)
            self.register_activity("flaky", self._flaky)

        def _flaky(self, value: int) -> int:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient")
            return value * 2

        async def run(self, value: int) -> int:  # type: ignore[override]
            return await self.execute_activity("flaky", args={"value": value})

    wf = RetryWorkflow()
    result = await wf.start(args={"value": 21})

    assert result == 42
    assert attempts["count"] >= 2


@pytest.mark.asyncio
async def test_workflow_signals() -> None:
    """Durable signals update workflow state via SignalHandler."""
    from agentic_brain.durability.signals import (
        Signal,
        SignalDeliveryStatus,
        SignalHandler,
    )

    handler = SignalHandler(workflow_id="wf-signals-1")
    received: dict[str, str] = {}

    async def on_update(payload: dict) -> None:
        received["status"] = payload["status"]

    handler.register_handler("update_status", on_update)

    signal = Signal(
        signal_id="sig-1",
        signal_name="update_status",
        workflow_id="wf-signals-1",
        payload={"status": "ready"},
    )

    delivered = await handler.receive(signal)

    assert delivered is True
    assert received["status"] == "ready"
    assert signal.status == SignalDeliveryStatus.DELIVERED


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires full Temporal infrastructure setup")
async def test_state_persistence() -> None:
    """Temporal-style workflow records events in the EventStore."""
    from agentic_brain.durability import get_event_store
    from agentic_brain.temporal import workflow
    from agentic_brain.temporal.testing import WorkflowEnvironment

    @workflow.defn
    class EchoWorkflow:
        @workflow.run
        async def run(self, value: str) -> str:  # type: ignore[override]
            return value

    workflow_id = "temporal-compat-echo-1"

    async with await WorkflowEnvironment.start_time_skipping() as env:
        result = await env.client.execute_workflow(
            EchoWorkflow.run,
            "hello",
            id=workflow_id,
            task_queue="temporal-compat",
        )

        assert result == "hello"

        store = get_event_store()
        events = await store.get_events(workflow_id)

    event_types = {e.event_type.name for e in events}
    assert "WORKFLOW_STARTED" in event_types
    assert "WORKFLOW_COMPLETED" in event_types
