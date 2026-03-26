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
Side Effects - Non-deterministic operations in workflows.

Side effects allow workflows to execute non-deterministic
operations (like UUID generation, random numbers, timestamps)
while maintaining replay determinism.

Features:
- Capture non-deterministic results
- Replay from recorded values
- Memoization
- UUID/timestamp generation
"""

import asyncio
import functools
import inspect
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .event_store import EventStore, get_event_store
from .events import BaseEvent, EventType, WorkflowEvent


@dataclass
class SideEffectResult:
    """Recorded result of a side effect."""

    effect_id: str
    effect_name: str
    value: Any
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    replayed: bool = False


@dataclass
class SideEffectContext:
    """Context for side effect execution."""

    workflow_id: str
    is_replaying: bool = False
    recorded_effects: Dict[str, SideEffectResult] = field(default_factory=dict)


class SideEffectManager:
    """
    Manages side effects for deterministic replay.

    Non-deterministic operations are captured and stored
    so they return the same value during replay.

    Features:
    - Record side effect results
    - Replay from recorded values
    - Support for common operations (UUID, random, time)
    """

    def __init__(self, workflow_id: str, event_store: Optional[EventStore] = None):
        self.workflow_id = workflow_id
        self.event_store = event_store or get_event_store()
        self.effects: Dict[str, SideEffectResult] = {}
        self.is_replaying = False
        self._effect_sequence = 0

    async def execute_side_effect(
        self, name: str, func: Callable[[], Any], effect_id: Optional[str] = None
    ) -> Any:
        """
        Execute a side effect function.

        During normal execution, calls the function and records result.
        During replay, returns the recorded value.

        Args:
            name: Name of the side effect
            func: Function to execute
            effect_id: Optional specific ID (auto-generated if not set)

        Returns:
            The side effect result
        """
        # Generate deterministic effect ID based on sequence
        if effect_id is None:
            effect_id = f"{name}_{self._effect_sequence}"
            self._effect_sequence += 1

        # Check if replaying
        if self.is_replaying and effect_id in self.effects:
            result = self.effects[effect_id]
            result.replayed = True
            return result.value

        # Execute the side effect
        value = func() if not inspect.iscoroutinefunction(func) else await func()

        # Record result
        result = SideEffectResult(effect_id=effect_id, effect_name=name, value=value)
        self.effects[effect_id] = result

        # Store in event store
        event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=self.workflow_id,
            event_type=EventType.ACTIVITY_COMPLETED,  # Using generic type
            timestamp=datetime.now(UTC),
            data={
                "side_effect_id": effect_id,
                "side_effect_name": name,
                "value": self._serialize_value(value),
            },
        )
        await self.event_store.append(event)

        return value

    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for storage."""
        if isinstance(value, datetime):
            return {"__type__": "datetime", "value": value.isoformat()}
        elif isinstance(value, uuid.UUID):
            return {"__type__": "uuid", "value": str(value)}
        return value

    def _deserialize_value(self, data: Any) -> Any:
        """Deserialize value from storage."""
        if isinstance(data, dict) and "__type__" in data:
            if data["__type__"] == "datetime":
                return datetime.fromisoformat(data["value"])
            elif data["__type__"] == "uuid":
                return uuid.UUID(data["value"])
        return data

    async def load_from_events(self) -> int:
        """
        Load recorded side effects from event store.

        Returns number of effects loaded.
        """
        events = await self.event_store.get_events(self.workflow_id)

        loaded = 0
        for event in events:
            if "side_effect_id" in event.data:
                effect_id = event.data["side_effect_id"]
                value = self._deserialize_value(event.data.get("value"))

                self.effects[effect_id] = SideEffectResult(
                    effect_id=effect_id,
                    effect_name=event.data.get("side_effect_name", "unknown"),
                    value=value,
                    recorded_at=event.timestamp,
                )
                loaded += 1

        return loaded

    # Convenience methods for common side effects

    async def uuid4(self, effect_id: Optional[str] = None) -> str:
        """Generate a UUID (deterministic during replay)."""
        return await self.execute_side_effect(
            "uuid4", lambda: str(uuid.uuid4()), effect_id
        )

    async def now(self, effect_id: Optional[str] = None) -> datetime:
        """Get current time (deterministic during replay)."""
        return await self.execute_side_effect("now", datetime.utcnow, effect_id)

    async def random_int(
        self, min_val: int, max_val: int, effect_id: Optional[str] = None
    ) -> int:
        """Generate random integer (deterministic during replay)."""
        return await self.execute_side_effect(
            "random_int", lambda: random.randint(min_val, max_val), effect_id
        )

    async def random_float(
        self,
        min_val: float = 0.0,
        max_val: float = 1.0,
        effect_id: Optional[str] = None,
    ) -> float:
        """Generate random float (deterministic during replay)."""
        return await self.execute_side_effect(
            "random_float", lambda: random.uniform(min_val, max_val), effect_id
        )

    async def random_choice(
        self, options: List[Any], effect_id: Optional[str] = None
    ) -> Any:
        """Choose random item (deterministic during replay)."""
        return await self.execute_side_effect(
            "random_choice", lambda: random.choice(options), effect_id
        )

    async def random_sample(
        self, population: List[Any], k: int, effect_id: Optional[str] = None
    ) -> List[Any]:
        """Sample k items (deterministic during replay)."""
        return await self.execute_side_effect(
            "random_sample", lambda: random.sample(population, k), effect_id
        )

    def start_replay(self) -> None:
        """Enter replay mode."""
        self.is_replaying = True
        self._effect_sequence = 0

    def stop_replay(self) -> None:
        """Exit replay mode."""
        self.is_replaying = False


def side_effect(name: Optional[str] = None):
    """
    Decorator to mark a function as a side effect.

    Side effects are captured during execution and replayed
    with the same value during workflow replay.

    Usage:
        @side_effect("generate-order-id")
        def generate_order_id():
            return f"ORD-{uuid.uuid4().hex[:8].upper()}"
    """

    def decorator(func: Callable) -> Callable:
        effect_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(
            *args,
            workflow_id: str = "default",
            event_store: Optional[EventStore] = None,
            **kwargs,
        ):
            manager = SideEffectManager(
                workflow_id=workflow_id, event_store=event_store
            )

            return await manager.execute_side_effect(
                effect_name, lambda: func(*args, **kwargs)
            )

        return wrapper

    return decorator


# Convenience functions for workflow context
_managers: Dict[str, SideEffectManager] = {}


def get_side_effect_manager(workflow_id: str) -> SideEffectManager:
    """Get or create side effect manager for workflow."""
    if workflow_id not in _managers:
        _managers[workflow_id] = SideEffectManager(workflow_id)
    return _managers[workflow_id]


async def workflow_uuid(workflow_id: str) -> str:
    """Generate UUID in workflow context."""
    manager = get_side_effect_manager(workflow_id)
    return await manager.uuid4()


async def workflow_now(workflow_id: str) -> datetime:
    """Get current time in workflow context."""
    manager = get_side_effect_manager(workflow_id)
    return await manager.now()


async def workflow_random_int(workflow_id: str, min_val: int, max_val: int) -> int:
    """Generate random int in workflow context."""
    manager = get_side_effect_manager(workflow_id)
    return await manager.random_int(min_val, max_val)


# Memoization for expensive computations
class MemoizedSideEffect:
    """
    Memoized side effect that caches results.

    Useful for expensive computations that should
    only run once even across retries.
    """

    def __init__(self, func: Callable, name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self._cache: Dict[str, Any] = {}

    def __call__(self, *args, **kwargs) -> Any:
        key = f"{args}_{kwargs}"

        if key in self._cache:
            return self._cache[key]

        result = self.func(*args, **kwargs)
        self._cache[key] = result
        return result

    def clear_cache(self) -> None:
        """Clear the memoization cache."""
        self._cache.clear()


def memoized(func: Callable) -> MemoizedSideEffect:
    """
    Decorator for memoized side effects.

    Usage:
        @memoized
        def expensive_computation(data):
            # Only computed once per unique input
            return process(data)
    """
    return MemoizedSideEffect(func)
