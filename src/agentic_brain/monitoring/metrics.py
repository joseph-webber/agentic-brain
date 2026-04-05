"""Metrics collection and Prometheus exposition for agentic-brain.

This module provides a lightweight in-process metrics registry and Prometheus
text-format exposition endpoint to avoid an external dependency.
"""

import math
import threading
import time
from collections import deque


class Metrics:
    """Simple thread-safe metrics collector.

    - latency histogram (seconds)
    - token usage counter
    - cache hit/miss counters
    - error counter
    - request throughput (recent window)
    """

    def __init__(self, throughput_window_seconds=60):
        # Use an RLock so methods that call each other while holding the lock won't deadlock
        self._lock = threading.RLock()
        # Counters
        self.tokens_used = 0
        self.errors = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.requests = 0
        # Latency observations (we keep sum and count and buckets)
        self.latency_sum = 0.0
        self.latency_count = 0
        # Exponential buckets similar to Prometheus defaults (seconds)
        self.latency_buckets = [
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1,
            2.5,
            5,
            10,
            float("inf"),
        ]
        self.latency_bucket_counts = [0 for _ in self.latency_buckets]
        # Throughput: timestamps of recent requests
        self.throughput_window = throughput_window_seconds
        self._request_timestamps = deque()

    def record_latency(self, seconds: float):
        if seconds is None:
            return
        with self._lock:
            self.latency_sum += float(seconds)
            self.latency_count += 1
            # find bucket
            for i, b in enumerate(self.latency_buckets):
                if seconds <= b:
                    self.latency_bucket_counts[i] += 1
                    break

    def increment_tokens(self, n: int = 1):
        with self._lock:
            self.tokens_used += int(n)

    def record_cache_hit(self, hit: bool = True):
        with self._lock:
            if hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    def increment_error(self, n: int = 1):
        with self._lock:
            self.errors += int(n)

    def record_request(self):
        """Record a single request occurrence for throughput and total requests."""
        now = time.time()
        with self._lock:
            self.requests += 1
            self._request_timestamps.append(now)
            # evict old timestamps
            cutoff = now - self.throughput_window
            while self._request_timestamps and self._request_timestamps[0] < cutoff:
                self._request_timestamps.popleft()

    def get_throughput_rps(self) -> float:
        """Return requests per second averaged over the throughput window.

        Evicts old timestamps based on current time so that callers which advance
        time (e.g., tests) observe eviction even if no new requests arrive.
        """
        with self._lock:
            if not self._request_timestamps:
                return 0.0
            # Evict old timestamps relative to now
            now = time.time()
            cutoff = now - self.throughput_window
            while self._request_timestamps and self._request_timestamps[0] < cutoff:
                self._request_timestamps.popleft()
            if not self._request_timestamps:
                return 0.0
            span = min(
                self.throughput_window,
                self._request_timestamps[-1]
                - (
                    self._request_timestamps[0]
                    if len(self._request_timestamps) > 1
                    else self._request_timestamps[0]
                ),
            )
            span = max(span, 1e-6)
            return len(self._request_timestamps) / span

    def cache_hit_rate(self) -> float:
        with self._lock:
            total = self.cache_hits + self.cache_misses
            if total == 0:
                return 0.0
            return float(self.cache_hits) / total

    def error_rate(self) -> float:
        with self._lock:
            if self.requests == 0:
                return 0.0
            return float(self.errors) / self.requests

    def snapshot(self):
        """Return a dict snapshot of key metrics."""
        with self._lock:
            return {
                "tokens_used": self.tokens_used,
                "errors": self.errors,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "requests": self.requests,
                "latency_sum": self.latency_sum,
                "latency_count": self.latency_count,
                "latency_buckets": list(self.latency_buckets),
                "latency_bucket_counts": list(self.latency_bucket_counts),
                "throughput_rps": self.get_throughput_rps(),
            }

    def generate_prometheus_metrics(self) -> str:
        """Return a string in Prometheus text exposition format for the collected metrics.

        This intentionally implements a minimal subset of the exposition format that
        Prometheus can scrape.
        """
        s = []
        snap = self.snapshot()
        # Counters
        s.append("# HELP agentic_tokens_used_total Total tokens used by agentic-brain")
        s.append("# TYPE agentic_tokens_used_total counter")
        s.append(f'agentic_tokens_used_total {snap["tokens_used"]}')

        s.append("# HELP agentic_requests_total Total requests received")
        s.append("# TYPE agentic_requests_total counter")
        s.append(f'agentic_requests_total {snap["requests"]}')

        s.append("# HELP agentic_errors_total Total error events")
        s.append("# TYPE agentic_errors_total counter")
        s.append(f'agentic_errors_total {snap["errors"]}')

        s.append("# HELP agentic_cache_hits_total Total cache hits")
        s.append("# TYPE agentic_cache_hits_total counter")
        s.append(f'agentic_cache_hits_total {snap["cache_hits"]}')

        s.append("# HELP agentic_cache_misses_total Total cache misses")
        s.append("# TYPE agentic_cache_misses_total counter")
        s.append(f'agentic_cache_misses_total {snap["cache_misses"]}')

        # Gauges
        s.append("# HELP agentic_cache_hit_rate Cache hit rate (0-1)")
        s.append("# TYPE agentic_cache_hit_rate gauge")
        s.append(f"agentic_cache_hit_rate {self.cache_hit_rate():.6f}")

        s.append("# HELP agentic_error_rate Error rate (errors/requests)")
        s.append("# TYPE agentic_error_rate gauge")
        s.append(f"agentic_error_rate {self.error_rate():.6f}")

        s.append("# HELP agentic_throughput_rps Requests per second (recent window)")
        s.append("# TYPE agentic_throughput_rps gauge")
        s.append(f'agentic_throughput_rps {snap["throughput_rps"]:.6f}')

        # Latency histogram: buckets, sum, count
        s.append(
            "# HELP agentic_query_latency_seconds Histogram of query latencies in seconds"
        )
        s.append("# TYPE agentic_query_latency_seconds histogram")
        cumulative = 0
        for b, count in zip(snap["latency_buckets"], snap["latency_bucket_counts"], strict=False):
            cumulative += count
            le = "+Inf" if math.isinf(b) else f"{b}"
            s.append(f'agentic_query_latency_seconds_bucket{{le="{le}"}} {cumulative}')
        s.append(f'agentic_query_latency_seconds_sum {snap["latency_sum"]:.6f}')
        s.append(f'agentic_query_latency_seconds_count {snap["latency_count"]}')

        return "\n".join(s) + "\n"


# Global singleton for easy import
global_metrics = Metrics()
