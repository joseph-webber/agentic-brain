#!/usr/bin/env python3
"""Circuit breaker for LLM providers — prevents cascading failures.

Each provider gets its own breaker. After N consecutive failures the breaker
opens and all calls short-circuit for a cooldown period, then the breaker
enters half-open state and allows one probe.  If the probe succeeds the
breaker closes; if it fails the breaker re-opens.

Thread-safe: uses a threading.Lock per breaker instance.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    recovery_timeout: float = 30.0  # seconds before half-open probe
    half_open_max: int = 1           # probes allowed in half-open

    _state: BreakerState = field(default=BreakerState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _total_calls: int = field(default=0, init=False)
    _total_failures: int = field(default=0, init=False)

    # Latency tracking (exponential moving average)
    _avg_latency_ms: float = field(default=0.0, init=False)
    _latency_alpha: float = field(default=0.3, init=False)

    @property
    def state(self) -> BreakerState:
        with self._lock:
            if self._state == BreakerState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = BreakerState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    @property
    def avg_latency_ms(self) -> float:
        return self._avg_latency_ms

    def allow_request(self) -> bool:
        """Return True if a request should be allowed through."""
        state = self.state
        if state == BreakerState.CLOSED:
            return True
        if state == BreakerState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max:
                    self._half_open_calls += 1
                    return True
            return False
        return False  # OPEN

    def record_success(self, latency_ms: float = 0.0) -> None:
        with self._lock:
            self._total_calls += 1
            self._successes += 1
            self._failures = 0
            if latency_ms > 0:
                self._avg_latency_ms = (
                    self._latency_alpha * latency_ms
                    + (1 - self._latency_alpha) * self._avg_latency_ms
                )
            if self._state in (BreakerState.HALF_OPEN, BreakerState.OPEN):
                self._state = BreakerState.CLOSED
                self._half_open_calls = 0

    def record_failure(self) -> None:
        with self._lock:
            self._total_calls += 1
            self._total_failures += 1
            self._failures += 1
            self._last_failure_time = time.monotonic()
            if self._failures >= self.failure_threshold:
                self._state = BreakerState.OPEN

    def reset(self) -> None:
        with self._lock:
            self._state = BreakerState.CLOSED
            self._failures = 0
            self._half_open_calls = 0

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "consecutive_failures": self._failures,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
                "avg_latency_ms": round(self._avg_latency_ms, 1),
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }


class CircuitBreakerRegistry:
    """Singleton registry of all provider circuit breakers."""

    _instance: CircuitBreakerRegistry | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def get(cls) -> CircuitBreakerRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def breaker(self, name: str, **kwargs: Any) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name=name, **kwargs)
        return self._breakers[name]

    def all_stats(self) -> list[dict[str, Any]]:
        return [b.stats() for b in self._breakers.values()]

    def healthy_providers(self) -> list[str]:
        return [
            name for name, b in self._breakers.items()
            if b.state != BreakerState.OPEN
        ]
