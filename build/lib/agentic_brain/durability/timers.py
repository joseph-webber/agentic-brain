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

"""
Timers - Durable sleep with persistence.

Enables workflows to sleep for extended periods while
surviving process restarts. Timer state is persisted
and resumes correctly after recovery.

Features:
- Durable sleep that survives restarts
- Timer cancellation
- Timer queries
- Deadline-based timers
- Multiple concurrent timers
"""

import asyncio
import inspect
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .event_store import EventStore, get_event_store
from .events import BaseEvent, EventType, WorkflowEvent


class TimerState(Enum):
    """Current state of a timer."""

    PENDING = "pending"
    RUNNING = "running"
    FIRED = "fired"
    CANCELLED = "cancelled"


@dataclass
class Timer:
    """
    Represents a durable timer.

    Timers are persisted and will resume after workflow recovery.
    """

    timer_id: str
    workflow_id: str
    duration: timedelta
    deadline: datetime
    created_at: datetime = field(default_factory=datetime.utcnow)
    fired_at: Optional[datetime] = None
    state: TimerState = TimerState.PENDING
    callback_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def remaining(self) -> timedelta:
        """Time remaining until timer fires."""
        if self.state == TimerState.FIRED:
            return timedelta(0)

        now = datetime.now(timezone.utc)
        remaining = self.deadline - now

        return max(remaining, timedelta(0))

    @property
    def is_expired(self) -> bool:
        """Check if timer has passed deadline."""
        return datetime.now(timezone.utc) >= self.deadline


@dataclass
class TimerFiredEvent:
    """Event emitted when a timer fires."""

    timer_id: str
    workflow_id: str
    fired_at: datetime
    metadata: Dict[str, Any]


class TimerManager:
    """
    Manages durable timers for workflows.

    Features:
    - Create/cancel timers
    - Persist timer state
    - Resume after recovery
    - Fire callbacks
    """

    def __init__(self, workflow_id: str, event_store: Optional[EventStore] = None):
        self.workflow_id = workflow_id
        self.event_store = event_store or get_event_store()
        self.timers: Dict[str, Timer] = {}
        self._timer_tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._running = False

    async def start_timer(
        self,
        duration: timedelta,
        timer_id: Optional[str] = None,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Timer:
        """
        Start a new durable timer.

        Args:
            duration: How long to wait
            timer_id: Optional ID (auto-generated if not provided)
            callback: Optional callback when timer fires
            metadata: Optional data to store with timer

        Returns:
            The created Timer
        """
        timer_id = timer_id or f"timer_{uuid.uuid4().hex[:8]}"
        deadline = datetime.now(timezone.utc) + duration

        timer = Timer(
            timer_id=timer_id,
            workflow_id=self.workflow_id,
            duration=duration,
            deadline=deadline,
            metadata=metadata or {},
        )

        if callback:
            timer.callback_name = callback.__name__
            self._callbacks[timer_id] = callback

        self.timers[timer_id] = timer

        # Record timer start event
        event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=self.workflow_id,
            event_type=EventType.TIMER_STARTED,
            timestamp=datetime.now(timezone.utc),
            data={
                "timer_id": timer_id,
                "duration_seconds": duration.total_seconds(),
                "deadline": deadline.isoformat(),
                "metadata": metadata,
            },
        )
        await self.event_store.append(event)

        # Start timer task
        timer.state = TimerState.RUNNING
        self._timer_tasks[timer_id] = asyncio.create_task(self._wait_and_fire(timer))

        return timer

    async def start_timer_at(
        self,
        deadline: datetime,
        timer_id: Optional[str] = None,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Timer:
        """
        Start a timer that fires at a specific time.

        Args:
            deadline: When to fire
            timer_id: Optional ID
            callback: Optional callback
            metadata: Optional data

        Returns:
            The created Timer
        """
        now = datetime.now(timezone.utc)
        duration = deadline - now

        if duration.total_seconds() < 0:
            duration = timedelta(0)

        return await self.start_timer(
            duration=duration, timer_id=timer_id, callback=callback, metadata=metadata
        )

    async def cancel_timer(self, timer_id: str) -> bool:
        """
        Cancel a running timer.

        Args:
            timer_id: Timer to cancel

        Returns:
            True if cancelled, False if not found or already fired
        """
        if timer_id not in self.timers:
            return False

        timer = self.timers[timer_id]

        if timer.state not in (TimerState.PENDING, TimerState.RUNNING):
            return False

        # Cancel task
        if timer_id in self._timer_tasks:
            self._timer_tasks[timer_id].cancel()
            try:
                await self._timer_tasks[timer_id]
            except asyncio.CancelledError:
                pass
            del self._timer_tasks[timer_id]

        timer.state = TimerState.CANCELLED

        # Record cancellation event
        event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=self.workflow_id,
            event_type=EventType.TIMER_CANCELLED,
            timestamp=datetime.now(timezone.utc),
            data={"timer_id": timer_id},
        )
        await self.event_store.append(event)

        return True

    async def _wait_and_fire(self, timer: Timer) -> None:
        """Wait for timer duration and fire."""
        try:
            # Calculate remaining time
            remaining = timer.remaining.total_seconds()

            if remaining > 0:
                await asyncio.sleep(remaining)

            # Fire timer
            timer.state = TimerState.FIRED
            timer.fired_at = datetime.now(timezone.utc)

            # Record fired event
            event = WorkflowEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=self.workflow_id,
                event_type=EventType.TIMER_FIRED,
                timestamp=datetime.now(timezone.utc),
                data={
                    "timer_id": timer.timer_id,
                    "deadline": timer.deadline.isoformat(),
                    "fired_at": timer.fired_at.isoformat(),
                },
            )
            await self.event_store.append(event)

            # Call callback if registered
            if timer.timer_id in self._callbacks:
                callback = self._callbacks[timer.timer_id]
                if inspect.iscoroutinefunction(callback):
                    await callback(timer)
                else:
                    callback(timer)

        except asyncio.CancelledError:
            pass

    def get_timer(self, timer_id: str) -> Optional[Timer]:
        """Get a timer by ID."""
        return self.timers.get(timer_id)

    def list_timers(self, state: Optional[TimerState] = None) -> List[Timer]:
        """List all timers, optionally filtered by state."""
        timers = list(self.timers.values())

        if state:
            timers = [t for t in timers if t.state == state]

        return timers

    def get_active_timers(self) -> List[Timer]:
        """Get all pending/running timers."""
        return [
            t
            for t in self.timers.values()
            if t.state in (TimerState.PENDING, TimerState.RUNNING)
        ]

    async def recover_timers(self) -> int:
        """
        Recover timers from event store after restart.

        Returns number of timers recovered.
        """
        events = await self.event_store.get_events(self.workflow_id)

        # Find timer events
        timer_events: Dict[str, List[WorkflowEvent]] = {}

        for event in events:
            if event.event_type in (
                EventType.TIMER_STARTED,
                EventType.TIMER_FIRED,
                EventType.TIMER_CANCELLED,
            ):
                timer_id = event.data.get("timer_id")
                if timer_id:
                    if timer_id not in timer_events:
                        timer_events[timer_id] = []
                    timer_events[timer_id].append(event)

        recovered = 0

        for timer_id, events in timer_events.items():
            # Get latest state
            events.sort(key=lambda e: e.timestamp)
            latest = events[-1]

            # Skip if already fired or cancelled
            if latest.event_type in (EventType.TIMER_FIRED, EventType.TIMER_CANCELLED):
                continue

            # Recover timer
            start_event = events[0]
            deadline_str = start_event.data.get("deadline")

            if deadline_str:
                deadline = datetime.fromisoformat(deadline_str)
                duration = timedelta(
                    seconds=start_event.data.get("duration_seconds", 0)
                )

                timer = Timer(
                    timer_id=timer_id,
                    workflow_id=self.workflow_id,
                    duration=duration,
                    deadline=deadline,
                    created_at=start_event.timestamp,
                    metadata=start_event.data.get("metadata", {}),
                )

                self.timers[timer_id] = timer

                # Restart timer task if not expired
                if not timer.is_expired:
                    timer.state = TimerState.RUNNING
                    self._timer_tasks[timer_id] = asyncio.create_task(
                        self._wait_and_fire(timer)
                    )
                else:
                    # Fire immediately if expired
                    timer.state = TimerState.RUNNING
                    self._timer_tasks[timer_id] = asyncio.create_task(
                        self._wait_and_fire(timer)
                    )

                recovered += 1

        return recovered

    async def cancel_all(self) -> int:
        """Cancel all active timers."""
        cancelled = 0

        for timer_id in list(self.timers.keys()):
            if await self.cancel_timer(timer_id):
                cancelled += 1

        return cancelled


# Durable sleep function for use in workflows
async def durable_sleep(
    duration: timedelta,
    workflow_id: str,
    event_store: Optional[EventStore] = None,
    timer_id: Optional[str] = None,
) -> None:
    """
    Durable sleep that survives workflow restarts.

    Usage:
        await durable_sleep(
            timedelta(hours=1),
            workflow_id="my-workflow"
        )
    """
    manager = TimerManager(workflow_id=workflow_id, event_store=event_store)

    timer = await manager.start_timer(duration=duration, timer_id=timer_id)

    # Wait for timer
    while timer.state == TimerState.RUNNING:
        await asyncio.sleep(0.1)


async def sleep_until(
    deadline: datetime,
    workflow_id: str,
    event_store: Optional[EventStore] = None,
    timer_id: Optional[str] = None,
) -> None:
    """
    Sleep until a specific time.

    Usage:
        await sleep_until(
            datetime(2025, 12, 31, 23, 59, 59),
            workflow_id="my-workflow"
        )
    """
    now = datetime.now(timezone.utc)
    duration = deadline - now

    if duration.total_seconds() > 0:
        await durable_sleep(
            duration=duration,
            workflow_id=workflow_id,
            event_store=event_store,
            timer_id=timer_id,
        )


# Convenience functions
def timer_for(
    seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0
) -> timedelta:
    """Create a timedelta for timer duration."""
    return timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days)


# Pre-built durations
ONE_SECOND = timedelta(seconds=1)
FIVE_SECONDS = timedelta(seconds=5)
TEN_SECONDS = timedelta(seconds=10)
THIRTY_SECONDS = timedelta(seconds=30)
ONE_MINUTE = timedelta(minutes=1)
FIVE_MINUTES = timedelta(minutes=5)
TEN_MINUTES = timedelta(minutes=10)
THIRTY_MINUTES = timedelta(minutes=30)
ONE_HOUR = timedelta(hours=1)
ONE_DAY = timedelta(days=1)
ONE_WEEK = timedelta(weeks=1)
