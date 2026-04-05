# SPDX-License-Identifier: Apache-2.0
"""
Lightweight load testing utilities for the Agentic Brain.
- Uses ThreadPoolExecutor + urllib to avoid external deps.
- Provides concurrent, sustained, spike, stress and soak testing helpers.
"""

from __future__ import annotations

import statistics
import threading
import time
import tracemalloc
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple


class LoadResult:
    def __init__(self):
        self.latencies: List[float] = []
        self.success = 0
        self.failure = 0

    def record(self, latency: float, ok: bool):
        self.latencies.append(latency)
        if ok:
            self.success += 1
        else:
            self.failure += 1


def _request_once(url: str, timeout: float = 10.0) -> Tuple[bool, float]:
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            _ = r.read(1)
        ok = True
    except Exception:
        ok = False
    latency = time.monotonic() - start
    return ok, latency


def _run_workers(target: str, total_requests: int, max_workers: int) -> LoadResult:
    result = LoadResult()
    # Use a thread pool for blocking urllib calls
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_request_once, target) for _ in range(total_requests)]
        for f in as_completed(futures):
            ok, latency = f.result()
            result.record(latency, ok)
    return result


def run_concurrent_queries(
    target: str, users: int = 10, queries_per_user: int = 1
) -> Dict:
    """Simulates `users` concurrent clients, each performing `queries_per_user` requests."""
    total = users * queries_per_user
    res = _run_workers(target, total, max_workers=users)
    return _summarize(res)


def run_sustained_load(
    target: str, users: int = 50, duration_s: int = 60, ramp_up: int = 5
) -> Dict:
    """Sustained load: maintain `users` concurrency for `duration_s` seconds."""
    end_time = time.monotonic() + duration_s
    result = LoadResult()

    # Worker function that runs until end_time
    def worker_loop():
        while time.monotonic() < end_time:
            ok, latency = _request_once(target)
            result.record(latency, ok)

    threads = []
    for _ in range(users):
        t = threading.Thread(target=worker_loop, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(ramp_up / max(1, users))

    for t in threads:
        t.join()

    return _summarize(result)


def run_spike_test(
    target: str,
    base_users: int = 5,
    spike_users: int = 200,
    spike_seconds: int = 10,
    duration_s: int = 60,
) -> Dict:
    """Run base load, then a short spike, then back to base.
    duration_s is total duration; spike occurs in the middle.
    """
    half = max(1, (duration_s - spike_seconds) // 2)
    # Warm base
    base = run_sustained_load(target, users=base_users, duration_s=half)
    # Spike
    spike = run_sustained_load(target, users=spike_users, duration_s=spike_seconds)
    # Cooldown
    cool = run_sustained_load(target, users=base_users, duration_s=half)

    combined = _combine_summaries([base, spike, cool])
    return combined


def run_stress_test(
    target: str,
    start_users: int = 10,
    max_users: int = 1000,
    step: int = 50,
    step_duration: int = 5,
    failure_threshold: Optional[float] = 0.2,
) -> Dict:
    """Increase load in steps until failure (fraction of failed requests > failure_threshold) or max reached."""
    summaries = []
    for u in range(start_users, max_users + 1, step):
        s = run_sustained_load(target, users=u, duration_s=step_duration)
        summaries.append(s)
        failure_frac = s.get("failure", 0) / max(1, s.get("requests", 1))
        if failure_frac > failure_threshold:
            break
    return _combine_summaries(summaries)


def run_soak_test(target: str, users: int = 10, duration_s: int = 60 * 60) -> Dict:
    """Soak: long-running low-mid load. Default 1 hour (can be overridden)."""
    return run_sustained_load(target, users=users, duration_s=duration_s)


def measure_memory_under_load(
    target: str, users: int = 50, duration_s: int = 10
) -> Dict:
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()
    summary = run_sustained_load(target, users=users, duration_s=duration_s)
    snapshot2 = tracemalloc.take_snapshot()
    stats = snapshot2.compare_to(snapshot1, "lineno")
    top = stats[:5]
    tracemalloc.stop()

    summary["memory_top_diffs"] = [str(x) for x in top]
    return summary


def _summarize(res: LoadResult) -> Dict:
    lat = sorted(res.latencies)
    total = len(lat)
    return {
        "requests": total,
        "success": res.success,
        "failure": res.failure,
        "p50": _percentile(lat, 50),
        "p95": _percentile(lat, 95),
        "p99": _percentile(lat, 99),
        "avg": statistics.mean(lat) if lat else None,
    }


def _combine_summaries(parts: List[Dict]) -> Dict:
    combined_lat: List[float] = []
    total_req = total_succ = total_fail = 0
    for p in parts:
        total_req += p.get("requests", 0)
        total_succ += p.get("success", 0)
        total_fail += p.get("failure", 0)
        # We cannot reconstruct latencies from summaries; instead combine percentiles approx by taking weighted average of medians
        if p.get("p50") is not None:
            combined_lat.append(p.get("p50"))
    return {
        "requests": total_req,
        "success": total_succ,
        "failure": total_fail,
        "p50": statistics.mean(combined_lat) if combined_lat else None,
    }


def _percentile(sorted_list: List[float], percentile: float) -> Optional[float]:
    if not sorted_list:
        return None
    k = (len(sorted_list) - 1) * (percentile / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_list) - 1)
    if f == c:
        return sorted_list[int(k)]
    d0 = sorted_list[f] * (c - k)
    d1 = sorted_list[c] * (k - f)
    return d0 + d1


if __name__ == "__main__":
    # Simple demo when invoked directly
    import argparse

    parser = argparse.ArgumentParser(
        description="Agentic Brain lightweight load tester"
    )
    parser.add_argument(
        "--target", default="http://127.0.0.1:8000/", help="Target URL to hit"
    )
    parser.add_argument("--users", type=int, default=10, help="Concurrent users")
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Duration in seconds for sustained test",
    )
    args = parser.parse_args()

    print(
        f"Running sustained load test: users={args.users} duration={args.duration}s target={args.target}"
    )
    print(run_sustained_load(args.target, users=args.users, duration_s=args.duration))
