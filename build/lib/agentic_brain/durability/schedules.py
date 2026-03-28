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
Schedules - Cron-like scheduling for durable workflows.

Enables workflows to be scheduled for recurring execution
with cron expressions, intervals, or calendar-based timing.

Features:
- Cron expression support
- Interval-based scheduling
- Calendar-based triggers
- Timezone awareness
- Overlap policies
- Pause/resume schedules
"""

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class ScheduleOverlapPolicy(Enum):
    """What to do when a scheduled run overlaps with previous."""

    SKIP = "skip"  # Skip if previous still running
    BUFFER_ONE = "buffer_one"  # Buffer one pending run
    BUFFER_ALL = "buffer_all"  # Buffer all pending runs
    CANCEL_OTHER = "cancel_other"  # Cancel previous, start new
    ALLOW_ALL = "allow_all"  # Allow concurrent runs


class ScheduleState(Enum):
    """Current state of a schedule."""

    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"


@dataclass
class CronExpression:
    """
    Parsed cron expression.

    Format: minute hour day_of_month month day_of_week
    Supports: *, ranges (1-5), lists (1,3,5), steps (*/5)
    """

    minute: str = "*"
    hour: str = "*"
    day_of_month: str = "*"
    month: str = "*"
    day_of_week: str = "*"

    @classmethod
    def parse(cls, expression: str) -> "CronExpression":
        """Parse cron expression string."""
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression}")

        return cls(
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

    def _parse_field(self, field: str, min_val: int, max_val: int) -> Set[int]:
        """Parse a single cron field into set of valid values."""
        values = set()

        for part in field.split(","):
            if part == "*":
                values.update(range(min_val, max_val + 1))
            elif "/" in part:
                base, step = part.split("/")
                step = int(step)
                if base == "*":
                    values.update(range(min_val, max_val + 1, step))
                else:
                    start = int(base)
                    values.update(range(start, max_val + 1, step))
            elif "-" in part:
                start, end = map(int, part.split("-"))
                values.update(range(start, end + 1))
            else:
                values.add(int(part))

        return values

    def matches(self, dt: datetime) -> bool:
        """Check if datetime matches this cron expression."""
        minutes = self._parse_field(self.minute, 0, 59)
        hours = self._parse_field(self.hour, 0, 23)
        days = self._parse_field(self.day_of_month, 1, 31)
        months = self._parse_field(self.month, 1, 12)
        weekdays = self._parse_field(self.day_of_week, 0, 6)

        return (
            dt.minute in minutes
            and dt.hour in hours
            and dt.day in days
            and dt.month in months
            and dt.weekday() in weekdays
        )

    def next_run(self, after: datetime) -> datetime:
        """Calculate next run time after given datetime."""
        # Start from next minute
        candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Search up to 1 year
        end = after + timedelta(days=366)

        while candidate < end:
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)

        raise ValueError("No matching time found within 1 year")


@dataclass
class ScheduleSpec:
    """Specification for when to run a schedule."""

    # Cron-based (mutually exclusive with interval)
    cron: Optional[str] = None

    # Interval-based
    interval: Optional[timedelta] = None

    # Calendar-based additions
    skip_weekends: bool = False
    skip_holidays: bool = False
    holidays: List[datetime] = field(default_factory=list)

    # Timezone
    timezone: str = "UTC"

    # Jitter to prevent thundering herd
    jitter: Optional[timedelta] = None

    def __post_init__(self):
        if self.cron and self.interval:
            raise ValueError("Cannot specify both cron and interval")
        if not self.cron and not self.interval:
            raise ValueError("Must specify either cron or interval")

        if self.cron:
            self._cron_expr = CronExpression.parse(self.cron)

    def next_run(self, after: datetime) -> datetime:
        """Calculate next run time."""
        if self.cron:
            candidate = self._cron_expr.next_run(after)
        else:
            candidate = after + self.interval

        # Apply skip rules
        while True:
            if self.skip_weekends and candidate.weekday() >= 5:
                candidate += timedelta(days=1)
                continue

            if self.skip_holidays:
                for holiday in self.holidays:
                    if candidate.date() == holiday.date():
                        candidate += timedelta(days=1)
                        continue

            break

        # Apply jitter
        if self.jitter:
            import random

            jitter_seconds = random.uniform(0, self.jitter.total_seconds())
            candidate += timedelta(seconds=jitter_seconds)

        return candidate


@dataclass
class ScheduleAction:
    """Action to take when schedule triggers."""

    workflow_type: str
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    task_queue: Optional[str] = None
    workflow_id_prefix: Optional[str] = None


@dataclass
class ScheduleDescription:
    """Full schedule configuration."""

    schedule_id: str
    spec: ScheduleSpec
    action: ScheduleAction
    state: ScheduleState = ScheduleState.ACTIVE
    overlap_policy: ScheduleOverlapPolicy = ScheduleOverlapPolicy.SKIP
    catchup_window: Optional[timedelta] = None  # How far back to catch up
    pause_on_failure: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    memo: Optional[Dict[str, Any]] = None
    search_attributes: Optional[Dict[str, Any]] = None


@dataclass
class ScheduleRun:
    """Record of a schedule execution."""

    run_id: str
    schedule_id: str
    workflow_id: str
    scheduled_time: datetime
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "running"
    result: Optional[Any] = None
    error: Optional[str] = None


class ScheduleHandle:
    """Handle to a created schedule."""

    def __init__(self, schedule_id: str, scheduler: "WorkflowScheduler"):
        self.schedule_id = schedule_id
        self._scheduler = scheduler

    async def describe(self) -> ScheduleDescription:
        """Get schedule description."""
        return await self._scheduler.describe(self.schedule_id)

    async def pause(self) -> None:
        """Pause the schedule."""
        await self._scheduler.pause(self.schedule_id)

    async def resume(self) -> None:
        """Resume a paused schedule."""
        await self._scheduler.resume(self.schedule_id)

    async def trigger(self) -> str:
        """Trigger immediate execution."""
        return await self._scheduler.trigger(self.schedule_id)

    async def delete(self) -> None:
        """Delete the schedule."""
        await self._scheduler.delete(self.schedule_id)

    async def update(
        self,
        spec: Optional[ScheduleSpec] = None,
        action: Optional[ScheduleAction] = None,
    ) -> None:
        """Update schedule configuration."""
        await self._scheduler.update(self.schedule_id, spec=spec, action=action)


class WorkflowScheduler:
    """
    Manages scheduled workflow execution.

    Features:
    - Create/update/delete schedules
    - Cron and interval scheduling
    - Overlap handling
    - Catch-up after downtime
    - Pause/resume
    """

    def __init__(self, workflow_executor: Optional[Callable] = None):
        self.schedules: Dict[str, ScheduleDescription] = {}
        self.runs: Dict[str, ScheduleRun] = {}
        self.running_workflows: Dict[str, str] = {}  # schedule_id -> workflow_id
        self._executor = workflow_executor
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False

    async def create(
        self,
        schedule_id: str,
        spec: ScheduleSpec,
        action: ScheduleAction,
        overlap_policy: ScheduleOverlapPolicy = ScheduleOverlapPolicy.SKIP,
        memo: Optional[Dict[str, Any]] = None,
    ) -> ScheduleHandle:
        """Create a new schedule."""
        if schedule_id in self.schedules:
            raise ValueError(f"Schedule {schedule_id} already exists")

        description = ScheduleDescription(
            schedule_id=schedule_id,
            spec=spec,
            action=action,
            overlap_policy=overlap_policy,
            memo=memo,
        )

        self.schedules[schedule_id] = description

        return ScheduleHandle(schedule_id, self)

    async def describe(self, schedule_id: str) -> ScheduleDescription:
        """Get schedule description."""
        if schedule_id not in self.schedules:
            raise KeyError(f"Schedule {schedule_id} not found")
        return self.schedules[schedule_id]

    async def pause(self, schedule_id: str) -> None:
        """Pause a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError(f"Schedule {schedule_id} not found")

        self.schedules[schedule_id].state = ScheduleState.PAUSED
        self.schedules[schedule_id].updated_at = datetime.now(UTC)

    async def resume(self, schedule_id: str) -> None:
        """Resume a paused schedule."""
        if schedule_id not in self.schedules:
            raise KeyError(f"Schedule {schedule_id} not found")

        self.schedules[schedule_id].state = ScheduleState.ACTIVE
        self.schedules[schedule_id].updated_at = datetime.now(UTC)

    async def trigger(self, schedule_id: str) -> str:
        """Trigger immediate execution."""
        if schedule_id not in self.schedules:
            raise KeyError(f"Schedule {schedule_id} not found")

        return await self._execute_schedule(
            self.schedules[schedule_id], datetime.now(UTC)
        )

    async def delete(self, schedule_id: str) -> None:
        """Delete a schedule."""
        if schedule_id not in self.schedules:
            raise KeyError(f"Schedule {schedule_id} not found")

        self.schedules[schedule_id].state = ScheduleState.DELETED
        del self.schedules[schedule_id]

    async def update(
        self,
        schedule_id: str,
        spec: Optional[ScheduleSpec] = None,
        action: Optional[ScheduleAction] = None,
    ) -> None:
        """Update schedule configuration."""
        if schedule_id not in self.schedules:
            raise KeyError(f"Schedule {schedule_id} not found")

        schedule = self.schedules[schedule_id]

        if spec:
            schedule.spec = spec
        if action:
            schedule.action = action

        schedule.updated_at = datetime.now(UTC)

    def list_schedules(
        self, state: Optional[ScheduleState] = None
    ) -> List[ScheduleDescription]:
        """List all schedules."""
        schedules = list(self.schedules.values())

        if state:
            schedules = [s for s in schedules if s.state == state]

        return schedules

    def get_recent_runs(self, schedule_id: str, limit: int = 10) -> List[ScheduleRun]:
        """Get recent runs for a schedule."""
        runs = [r for r in self.runs.values() if r.schedule_id == schedule_id]

        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = datetime.now(UTC)

            for schedule in self.schedules.values():
                if schedule.state != ScheduleState.ACTIVE:
                    continue

                # Check if it's time to run
                next_run = schedule.spec.next_run(schedule.updated_at)

                if next_run <= now:
                    await self._maybe_execute(schedule, next_run)
                    schedule.updated_at = now

            # Check every second
            await asyncio.sleep(1)

    async def _maybe_execute(
        self, schedule: ScheduleDescription, scheduled_time: datetime
    ) -> None:
        """Execute schedule if overlap policy allows."""
        schedule_id = schedule.schedule_id

        # Check overlap
        if schedule_id in self.running_workflows:
            policy = schedule.overlap_policy

            if policy == ScheduleOverlapPolicy.SKIP:
                return
            elif policy == ScheduleOverlapPolicy.CANCEL_OTHER:
                # Would cancel running workflow
                pass
            # BUFFER_ONE, BUFFER_ALL, ALLOW_ALL continue

        await self._execute_schedule(schedule, scheduled_time)

    async def _execute_schedule(
        self, schedule: ScheduleDescription, scheduled_time: datetime
    ) -> str:
        """Execute a scheduled workflow."""
        action = schedule.action

        # Generate workflow ID
        prefix = action.workflow_id_prefix or schedule.schedule_id
        workflow_id = f"{prefix}_{scheduled_time.strftime('%Y%m%d_%H%M%S')}"

        # Create run record
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        run = ScheduleRun(
            run_id=run_id,
            schedule_id=schedule.schedule_id,
            workflow_id=workflow_id,
            scheduled_time=scheduled_time,
        )
        self.runs[run_id] = run
        self.running_workflows[schedule.schedule_id] = workflow_id

        # Execute workflow
        if self._executor:
            try:
                result = await self._executor(
                    action.workflow_type,
                    *action.args,
                    workflow_id=workflow_id,
                    **action.kwargs,
                )

                run.status = "completed"
                run.result = result

            except Exception as e:
                run.status = "failed"
                run.error = str(e)

                if schedule.pause_on_failure:
                    schedule.state = ScheduleState.PAUSED

            finally:
                run.completed_at = datetime.now(UTC)
                if schedule.schedule_id in self.running_workflows:
                    del self.running_workflows[schedule.schedule_id]

        return workflow_id


# Convenience functions
def every_minute() -> ScheduleSpec:
    """Schedule that runs every minute."""
    return ScheduleSpec(cron="* * * * *")


def every_hour() -> ScheduleSpec:
    """Schedule that runs every hour."""
    return ScheduleSpec(cron="0 * * * *")


def every_day(hour: int = 0, minute: int = 0) -> ScheduleSpec:
    """Schedule that runs daily at specified time."""
    return ScheduleSpec(cron=f"{minute} {hour} * * *")


def every_week(day_of_week: int = 0, hour: int = 0, minute: int = 0) -> ScheduleSpec:
    """Schedule that runs weekly."""
    return ScheduleSpec(cron=f"{minute} {hour} * * {day_of_week}")


def every_interval(seconds: int = 0, minutes: int = 0, hours: int = 0) -> ScheduleSpec:
    """Schedule that runs at fixed interval."""
    total_seconds = seconds + minutes * 60 + hours * 3600
    return ScheduleSpec(interval=timedelta(seconds=total_seconds))


# Pre-built schedules
EVERY_MINUTE = every_minute()
EVERY_5_MINUTES = ScheduleSpec(cron="*/5 * * * *")
EVERY_15_MINUTES = ScheduleSpec(cron="*/15 * * * *")
EVERY_HOUR = every_hour()
DAILY_MIDNIGHT = every_day(hour=0)
DAILY_9AM = every_day(hour=9)
WEEKLY_MONDAY = every_week(day_of_week=0)
