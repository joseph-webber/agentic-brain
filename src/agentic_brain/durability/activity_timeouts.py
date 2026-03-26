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
Activity Timeouts - Comprehensive timeout configuration.

Provides compatible timeout types for activities:
- schedule_to_start: Time from scheduling to worker pickup
- start_to_close: Time from start to completion
- schedule_to_close: Total time from scheduling
- heartbeat_timeout: Time between heartbeats

Features:
- Multiple timeout types
- Timeout inheritance
- Dynamic timeout adjustment
- Timeout monitoring
"""

import asyncio
import inspect
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class TimeoutType(Enum):
    """Types of activity timeouts."""

    SCHEDULE_TO_START = "schedule_to_start"  # Waiting in queue
    START_TO_CLOSE = "start_to_close"  # Execution time
    SCHEDULE_TO_CLOSE = "schedule_to_close"  # Total time
    HEARTBEAT = "heartbeat"  # Between heartbeats


@dataclass
class ActivityTimeouts:
    """
    Timeout configuration for an activity.

    Provides comprehensive timeout management.
    """

    # Time allowed to wait in queue for a worker
    schedule_to_start: Optional[timedelta] = None

    # Time allowed for execution (per attempt)
    start_to_close: Optional[timedelta] = None

    # Total time from scheduling (includes retries)
    schedule_to_close: Optional[timedelta] = None

    # Maximum time between heartbeats
    heartbeat_timeout: Optional[timedelta] = None

    def __post_init__(self):
        # Validate consistency
        if self.schedule_to_close and self.start_to_close:
            if self.schedule_to_close < self.start_to_close:
                raise ValueError("schedule_to_close must be >= start_to_close")

    def with_defaults(self, defaults: "ActivityTimeouts") -> "ActivityTimeouts":
        """Merge with default timeouts."""
        return ActivityTimeouts(
            schedule_to_start=(self.schedule_to_start or defaults.schedule_to_start),
            start_to_close=(self.start_to_close or defaults.start_to_close),
            schedule_to_close=(self.schedule_to_close or defaults.schedule_to_close),
            heartbeat_timeout=(self.heartbeat_timeout or defaults.heartbeat_timeout),
        )


@dataclass
class TimeoutEvent:
    """Record of a timeout occurrence."""

    event_id: str
    activity_id: str
    workflow_id: str
    timeout_type: TimeoutType
    configured_timeout: timedelta
    actual_duration: timedelta
    occurred_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ActivityExecution:
    """Tracks an activity execution for timeout monitoring."""

    activity_id: str
    workflow_id: str
    activity_name: str
    timeouts: ActivityTimeouts
    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    status: str = "scheduled"
    timeout_event: Optional[TimeoutEvent] = None

    @property
    def schedule_to_start_elapsed(self) -> Optional[timedelta]:
        """Time spent waiting to start."""
        if self.started_at:
            return self.started_at - self.scheduled_at
        return datetime.now(UTC) - self.scheduled_at

    @property
    def start_to_close_elapsed(self) -> Optional[timedelta]:
        """Time spent executing."""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now(UTC)
        return end - self.started_at

    @property
    def schedule_to_close_elapsed(self) -> timedelta:
        """Total time since scheduling."""
        end = self.completed_at or datetime.now(UTC)
        return end - self.scheduled_at

    @property
    def heartbeat_elapsed(self) -> Optional[timedelta]:
        """Time since last heartbeat."""
        if not self.last_heartbeat_at:
            return None
        return datetime.now(UTC) - self.last_heartbeat_at

    def check_timeouts(self) -> Optional[TimeoutEvent]:
        """Check if any timeout has been exceeded."""
        datetime.now(UTC)

        # Check schedule_to_start
        if (
            self.status == "scheduled"
            and self.timeouts.schedule_to_start
            and self.schedule_to_start_elapsed > self.timeouts.schedule_to_start
        ):
            return TimeoutEvent(
                event_id=str(uuid.uuid4()),
                activity_id=self.activity_id,
                workflow_id=self.workflow_id,
                timeout_type=TimeoutType.SCHEDULE_TO_START,
                configured_timeout=self.timeouts.schedule_to_start,
                actual_duration=self.schedule_to_start_elapsed,
            )

        # Check start_to_close
        if (
            self.status == "running"
            and self.timeouts.start_to_close
            and self.start_to_close_elapsed
            and self.start_to_close_elapsed > self.timeouts.start_to_close
        ):
            return TimeoutEvent(
                event_id=str(uuid.uuid4()),
                activity_id=self.activity_id,
                workflow_id=self.workflow_id,
                timeout_type=TimeoutType.START_TO_CLOSE,
                configured_timeout=self.timeouts.start_to_close,
                actual_duration=self.start_to_close_elapsed,
            )

        # Check schedule_to_close
        if (
            self.timeouts.schedule_to_close
            and self.schedule_to_close_elapsed > self.timeouts.schedule_to_close
        ):
            return TimeoutEvent(
                event_id=str(uuid.uuid4()),
                activity_id=self.activity_id,
                workflow_id=self.workflow_id,
                timeout_type=TimeoutType.SCHEDULE_TO_CLOSE,
                configured_timeout=self.timeouts.schedule_to_close,
                actual_duration=self.schedule_to_close_elapsed,
            )

        # Check heartbeat
        if (
            self.status == "running"
            and self.timeouts.heartbeat_timeout
            and self.heartbeat_elapsed
            and self.heartbeat_elapsed > self.timeouts.heartbeat_timeout
        ):
            return TimeoutEvent(
                event_id=str(uuid.uuid4()),
                activity_id=self.activity_id,
                workflow_id=self.workflow_id,
                timeout_type=TimeoutType.HEARTBEAT,
                configured_timeout=self.timeouts.heartbeat_timeout,
                actual_duration=self.heartbeat_elapsed,
            )

        return None


class ActivityTimeoutError(Exception):
    """Raised when an activity times out."""

    def __init__(self, event: TimeoutEvent):
        self.event = event
        super().__init__(
            f"Activity {event.activity_id} timed out: "
            f"{event.timeout_type.value} exceeded "
            f"({event.actual_duration} > {event.configured_timeout})"
        )


class TimeoutMonitor:
    """
    Monitors activity executions for timeouts.

    Features:
    - Track multiple activities
    - Periodic timeout checks
    - Timeout callbacks
    - Timeout statistics
    """

    def __init__(self):
        self.activities: Dict[str, ActivityExecution] = {}
        self.timeout_events: List[TimeoutEvent] = []
        self._callbacks: List[Callable[[TimeoutEvent], Any]] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    def register_activity(
        self,
        activity_id: str,
        workflow_id: str,
        activity_name: str,
        timeouts: ActivityTimeouts,
    ) -> ActivityExecution:
        """Register an activity for monitoring."""
        execution = ActivityExecution(
            activity_id=activity_id,
            workflow_id=workflow_id,
            activity_name=activity_name,
            timeouts=timeouts,
        )

        self.activities[activity_id] = execution
        return execution

    def mark_started(self, activity_id: str) -> None:
        """Mark activity as started."""
        if activity_id in self.activities:
            self.activities[activity_id].started_at = datetime.now(UTC)
            self.activities[activity_id].status = "running"

    def mark_completed(self, activity_id: str) -> None:
        """Mark activity as completed."""
        if activity_id in self.activities:
            self.activities[activity_id].completed_at = datetime.now(UTC)
            self.activities[activity_id].status = "completed"

    def record_heartbeat(self, activity_id: str) -> None:
        """Record a heartbeat for activity."""
        if activity_id in self.activities:
            self.activities[activity_id].last_heartbeat_at = datetime.now(UTC)

    def add_timeout_callback(self, callback: Callable[[TimeoutEvent], Any]) -> None:
        """Add callback for timeout events."""
        self._callbacks.append(callback)

    async def check_all(self) -> List[TimeoutEvent]:
        """Check all activities for timeouts."""
        events = []

        for activity in list(self.activities.values()):
            if activity.status in ("completed", "failed", "timed_out"):
                continue

            event = activity.check_timeouts()
            if event:
                activity.timeout_event = event
                activity.status = "timed_out"
                self.timeout_events.append(event)
                events.append(event)

                # Call callbacks
                for callback in self._callbacks:
                    try:
                        if inspect.iscoroutinefunction(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception:
                        pass

        return events

    async def start_monitoring(self, interval: float = 1.0) -> None:
        """Start periodic timeout monitoring."""
        self._running = True

        async def monitor_loop():
            while self._running:
                await self.check_all()
                await asyncio.sleep(interval)

        self._monitor_task = asyncio.create_task(monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    def get_statistics(self) -> Dict[str, Any]:
        """Get timeout statistics."""
        total = len(self.activities)
        timed_out = len(
            [a for a in self.activities.values() if a.status == "timed_out"]
        )

        by_type = {}
        for event in self.timeout_events:
            t = event.timeout_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_activities": total,
            "timed_out": timed_out,
            "timeout_rate": timed_out / total if total > 0 else 0,
            "by_type": by_type,
        }


# Default timeout configurations
DEFAULT_TIMEOUTS = ActivityTimeouts(
    schedule_to_start=timedelta(minutes=5),
    start_to_close=timedelta(minutes=10),
    schedule_to_close=timedelta(minutes=30),
    heartbeat_timeout=timedelta(minutes=1),
)

SHORT_TIMEOUTS = ActivityTimeouts(
    schedule_to_start=timedelta(seconds=30),
    start_to_close=timedelta(minutes=1),
    schedule_to_close=timedelta(minutes=5),
    heartbeat_timeout=timedelta(seconds=30),
)

LONG_TIMEOUTS = ActivityTimeouts(
    schedule_to_start=timedelta(minutes=30),
    start_to_close=timedelta(hours=1),
    schedule_to_close=timedelta(hours=4),
    heartbeat_timeout=timedelta(minutes=5),
)

# LLM-specific timeouts (account for rate limits)
LLM_TIMEOUTS = ActivityTimeouts(
    schedule_to_start=timedelta(minutes=2),
    start_to_close=timedelta(minutes=5),
    schedule_to_close=timedelta(minutes=15),
    heartbeat_timeout=timedelta(seconds=60),
)

# RAG-specific timeouts
RAG_TIMEOUTS = ActivityTimeouts(
    schedule_to_start=timedelta(minutes=1),
    start_to_close=timedelta(minutes=3),
    schedule_to_close=timedelta(minutes=10),
    heartbeat_timeout=timedelta(seconds=30),
)

# DB-specific timeouts
DB_TIMEOUTS = ActivityTimeouts(
    schedule_to_start=timedelta(seconds=30),
    start_to_close=timedelta(seconds=30),
    schedule_to_close=timedelta(minutes=2),
    heartbeat_timeout=timedelta(seconds=15),
)


def create_timeouts(
    schedule_to_start: Optional[int] = None,  # seconds
    start_to_close: Optional[int] = None,
    schedule_to_close: Optional[int] = None,
    heartbeat: Optional[int] = None,
) -> ActivityTimeouts:
    """Create activity timeouts from seconds."""
    return ActivityTimeouts(
        schedule_to_start=(
            timedelta(seconds=schedule_to_start) if schedule_to_start else None
        ),
        start_to_close=(timedelta(seconds=start_to_close) if start_to_close else None),
        schedule_to_close=(
            timedelta(seconds=schedule_to_close) if schedule_to_close else None
        ),
        heartbeat_timeout=(timedelta(seconds=heartbeat) if heartbeat else None),
    )
