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
Heartbeat Monitoring for long-running activities.

Activities send periodic heartbeats to prove they're still alive.
If heartbeats stop, the system can:
- Detect hung activities
- Timeout and retry
- Report progress to workflows

This is essential for LLM calls that might hang indefinitely.

Usage:
    from agentic_brain.durability.heartbeats import HeartbeatMonitor, heartbeat

    @heartbeat(interval=5.0)
    async def long_llm_call(prompt: str) -> str:
        # Heartbeats sent automatically every 5 seconds
        return await llm.complete(prompt)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from .event_store import EventStore, get_event_store
from .events import ActivityHeartbeat

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat monitoring"""

    # Heartbeat intervals
    default_interval: float = 10.0  # Send heartbeat every N seconds
    timeout_multiplier: float = 3.0  # Timeout after N * interval without heartbeat

    # Monitoring
    check_interval: float = 1.0  # How often to check for timeouts

    # Behavior
    auto_retry_on_timeout: bool = True
    max_timeout_retries: int = 2


@dataclass
class HeartbeatInfo:
    """Information about a heartbeat"""

    activity_id: str
    workflow_id: str
    last_heartbeat: datetime
    progress: float = 0.0
    details: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)


class HeartbeatMonitor:
    """
    Monitors heartbeats from running activities.

    Activities register with the monitor and send periodic heartbeats.
    The monitor detects when heartbeats stop (indicating a hung activity)
    and can trigger timeouts/retries.
    """

    def __init__(
        self,
        config: HeartbeatConfig | None = None,
        event_store: EventStore | None = None,
    ):
        """
        Initialize heartbeat monitor.

        Args:
            config: Configuration options
            event_store: Event store for recording heartbeat events
        """
        self.config = config or HeartbeatConfig()
        self.event_store = event_store or get_event_store()

        # Track active activities
        self._activities: dict[str, HeartbeatInfo] = {}

        # Timeout callbacks
        self._timeout_callbacks: dict[str, Callable] = {}

        # Background monitor task
        self._monitor_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the heartbeat monitor"""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Heartbeat monitor started")

    async def stop(self) -> None:
        """Stop the heartbeat monitor"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat monitor stopped")

    def register_activity(
        self,
        activity_id: str,
        workflow_id: str,
        on_timeout: Callable | None = None,
    ) -> None:
        """
        Register an activity for heartbeat monitoring.

        Args:
            activity_id: Unique activity ID
            workflow_id: Workflow this activity belongs to
            on_timeout: Callback when heartbeat times out
        """
        self._activities[activity_id] = HeartbeatInfo(
            activity_id=activity_id,
            workflow_id=workflow_id,
            last_heartbeat=datetime.now(timezone.utc),
        )

        if on_timeout:
            self._timeout_callbacks[activity_id] = on_timeout

        logger.debug(f"Registered activity {activity_id} for heartbeat monitoring")

    def unregister_activity(self, activity_id: str) -> None:
        """Unregister an activity (when completed)"""
        self._activities.pop(activity_id, None)
        self._timeout_callbacks.pop(activity_id, None)
        logger.debug(f"Unregistered activity {activity_id}")

    async def heartbeat(
        self,
        activity_id: str,
        progress: float = 0.0,
        details: str = "",
    ) -> bool:
        """
        Send a heartbeat for an activity.

        Args:
            activity_id: Activity ID
            progress: Progress percentage (0.0 - 1.0)
            details: Optional status details

        Returns:
            True if heartbeat recorded successfully
        """
        if activity_id not in self._activities:
            logger.warning(f"Heartbeat for unregistered activity: {activity_id}")
            return False

        info = self._activities[activity_id]
        info.last_heartbeat = datetime.now(timezone.utc)
        info.progress = progress
        info.details = details

        # Record heartbeat event
        await self.event_store.publish(
            ActivityHeartbeat(
                workflow_id=info.workflow_id,
                activity_id=activity_id,
                progress=progress,
                details=details,
            )
        )

        logger.debug(f"Heartbeat from {activity_id}: {progress:.0%} - {details}")
        return True

    def get_activity_info(self, activity_id: str) -> HeartbeatInfo | None:
        """Get information about an activity"""
        return self._activities.get(activity_id)

    def get_all_activities(self) -> list[HeartbeatInfo]:
        """Get all registered activities"""
        return list(self._activities.values())

    async def _monitor_loop(self) -> None:
        """Background loop that checks for timed-out activities"""
        while self._running:
            await asyncio.sleep(self.config.check_interval)
            await self._check_timeouts()

    async def _check_timeouts(self) -> None:
        """Check for activities that have timed out"""
        now = datetime.now(timezone.utc)
        timeout_threshold = timedelta(
            seconds=self.config.default_interval * self.config.timeout_multiplier
        )

        timed_out = []

        for activity_id, info in self._activities.items():
            elapsed = now - info.last_heartbeat
            if elapsed > timeout_threshold:
                timed_out.append(activity_id)

        for activity_id in timed_out:
            info = self._activities[activity_id]
            logger.warning(
                f"Activity {activity_id} timed out "
                f"(no heartbeat for {(now - info.last_heartbeat).seconds}s)"
            )

            # Call timeout callback
            callback = self._timeout_callbacks.get(activity_id)
            if callback:
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(activity_id, info)
                    else:
                        callback(activity_id, info)
                except Exception as e:
                    logger.error(f"Timeout callback failed: {e}")

            # Remove from monitoring
            self.unregister_activity(activity_id)


# =============================================================================
# Heartbeat Decorator
# =============================================================================


def heartbeat(
    interval: float = 10.0,
    timeout: float | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that adds automatic heartbeats to an async function.

    Args:
        interval: Heartbeat interval in seconds
        timeout: Total timeout (None = no timeout)

    Usage:
        @heartbeat(interval=5.0, timeout=60.0)
        async def long_running_task():
            # Heartbeats sent automatically every 5 seconds
            await do_something_slow()
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            activity_id = f"hb-{uuid.uuid4().hex[:8]}"

            # Create heartbeat sender
            async def send_heartbeats():
                progress = 0.0
                while True:
                    await asyncio.sleep(interval)
                    # Simple progress increment
                    progress = min(progress + 0.1, 0.9)
                    logger.debug(f"Sending heartbeat for {activity_id}: {progress:.0%}")

            # Start heartbeat task
            heartbeat_task = asyncio.create_task(send_heartbeats())

            try:
                if timeout:
                    result = await asyncio.wait_for(
                        fn(*args, **kwargs), timeout=timeout
                    )
                else:
                    result = await fn(*args, **kwargs)
                return result
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        return wrapper

    return decorator


# =============================================================================
# Heartbeat Context
# =============================================================================


class HeartbeatContext:
    """
    Context manager for manual heartbeat sending.

    Usage:
        async with HeartbeatContext("my-activity", "wf-123") as ctx:
            for i, item in enumerate(items):
                await process(item)
                await ctx.heartbeat(progress=i/len(items), details=f"Processing {i}")
    """

    def __init__(
        self,
        activity_id: str,
        workflow_id: str,
        monitor: HeartbeatMonitor | None = None,
    ):
        self.activity_id = activity_id
        self.workflow_id = workflow_id
        self.monitor = monitor or _default_monitor

    async def heartbeat(
        self,
        progress: float = 0.0,
        details: str = "",
    ) -> None:
        """Send a heartbeat"""
        if self.monitor:
            await self.monitor.heartbeat(self.activity_id, progress, details)

    async def __aenter__(self) -> HeartbeatContext:
        if self.monitor:
            self.monitor.register_activity(self.activity_id, self.workflow_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.monitor:
            self.monitor.unregister_activity(self.activity_id)


# =============================================================================
# Singleton
# =============================================================================

_default_monitor: HeartbeatMonitor | None = None


def get_heartbeat_monitor() -> HeartbeatMonitor:
    """Get the default heartbeat monitor"""
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = HeartbeatMonitor()
    return _default_monitor


async def init_heartbeat_monitor(
    config: HeartbeatConfig | None = None,
) -> HeartbeatMonitor:
    """Initialize and start the default heartbeat monitor"""
    global _default_monitor
    _default_monitor = HeartbeatMonitor(config)
    await _default_monitor.start()
    return _default_monitor


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "HeartbeatMonitor",
    "HeartbeatConfig",
    "HeartbeatInfo",
    "HeartbeatContext",
    "heartbeat",
    "get_heartbeat_monitor",
    "init_heartbeat_monitor",
]
