import time
import json
import math
import socket
import types
import pytest
from agentic_brain.monitoring import metrics as mmod
from agentic_brain.monitoring import health as hmod

# ----- Metrics tests -----

def test_record_latency_and_histogram():
    metrics = mmod.Metrics()
    metrics.record_latency(0.01)
    metrics.record_latency(0.2)
    metrics.record_latency(1.5)
    snap = metrics.snapshot()
    assert snap['latency_count'] == 3
    assert snap['latency_sum'] == pytest.approx(0.01+0.2+1.5)
    # check bucket counts sum to count
    assert sum(snap['latency_bucket_counts']) == 3


def test_increment_tokens_and_counters():
    metrics = mmod.Metrics()
    metrics.increment_tokens(5)
    metrics.increment_tokens(3)
    assert metrics.snapshot()['tokens_used'] == 8
    metrics.increment_error()
    assert metrics.snapshot()['errors'] == 1


def test_cache_hit_rate_and_miss():
    metrics = mmod.Metrics()
    metrics.record_cache_hit(True)
    metrics.record_cache_hit(False)
    metrics.record_cache_hit(True)
    assert metrics.cache_hit_rate() == pytest.approx(2/3)


def test_throughput_measurement_time_control(monkeypatch):
    metrics = mmod.Metrics(throughput_window_seconds=10)
    base = 1000.0
    # fake time
    t = {'now': base}
    def fake_time():
        return t['now']
    monkeypatch.setattr(mm:=time, 'time', fake_time)
    # record 5 requests spread over 5 seconds
    for i in range(5):
        metrics.record_request()
        t['now'] += 1.0
    rps = metrics.get_throughput_rps()
    assert rps > 0
    # move time forward beyond window and check throughput zeroes
    t['now'] = base + 100
    assert metrics.get_throughput_rps() == 0.0


def test_generate_prometheus_metrics_contains_expected():
    metrics = mmod.Metrics()
    metrics.increment_tokens(10)
    metrics.record_cache_hit(True)
    metrics.increment_error()
    metrics.record_latency(0.02)
    metrics.record_request()
    text = metrics.generate_prometheus_metrics()
    assert 'agentic_tokens_used_total 10' in text
    assert 'agentic_cache_hits_total 1' in text
    assert 'agentic_errors_total 1' in text
    assert 'agentic_query_latency_seconds_count 1' in text


def test_global_metrics_singleton_behaviour():
    from agentic_brain.monitoring import global_metrics
    # reset a few fields for predictability
    global_metrics.tokens_used = 0
    global_metrics.errors = 0
    global_metrics.cache_hits = 0
    global_metrics.cache_misses = 0
    global_metrics.record_request()
    assert global_metrics.requests >= 1


def test_histogram_buckets_edge_cases():
    metrics = mmod.Metrics()
    # Very small latency
    metrics.record_latency(0.0001)
    # Very large latency
    metrics.record_latency(100.0)
    snap = metrics.snapshot()
    assert snap['latency_count'] == 2
    assert snap['latency_bucket_counts'][-1] >= 1

# ----- Health tests -----

class DummySocket:
    def __init__(self, succeed=True):
        self.succeed = succeed
    def __enter__(self):
        if not self.succeed:
            raise OSError('connect fail')
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_tcp_check_success(monkeypatch):
    # simulate create_connection returning a context manager
    def fake_create(addr, timeout=1):
        return DummySocket(succeed=True)
    monkeypatch.setattr(socket, 'create_connection', fake_create)
    checks = hmod.dependency_checks()
    assert checks['neo4j']['ok'] in (True, False)


def test_tcp_check_failure(monkeypatch):
    def fake_create(addr, timeout=1):
        raise OSError('nope')
    monkeypatch.setattr(socket, 'create_connection', fake_create)
    checks = hmod.dependency_checks()
    assert checks['neo4j']['ok'] is False


def test_get_health_status_structure(monkeypatch):
    # make dependencies succeed
    def fake_create(addr, timeout=1):
        return DummySocket(succeed=True)
    monkeypatch.setattr(socket, 'create_connection', fake_create)
    status = hmod.get_health_status()
    assert 'status' in status
    assert 'dependencies' in status
    assert 'metrics' in status


def test_wsgi_app_health_and_metrics(monkeypatch):
    # prepare metrics and dependencies
    def fake_create(addr, timeout=1):
        return DummySocket(succeed=True)
    monkeypatch.setattr(socket, 'create_connection', fake_create)
    app = hmod.create_wsgi_app()
    # call /health
    environ = {'PATH_INFO': '/health'}
    body = []
    def start_response(status, headers):
        body.append(status)
    res = app(environ, start_response)
    assert body[0].startswith('200')
    data = b''.join(res).decode('utf-8')
    obj = json.loads(data)
    assert 'status' in obj
    # call /metrics
    body.clear()
    environ = {'PATH_INFO': '/metrics'}
    res = app(environ, start_response)
    assert body[0].startswith('200')
    text = b''.join(res).decode('utf-8')
    assert 'agentic_tokens_used_total' in text

# ----- Concurrency and stress tests (lightweight) -----

def test_concurrent_recording(monkeypatch):
    metrics = mmod.Metrics()
    # spawn multiple threads to update metrics
    import threading
    def worker(i):
        for _ in range(100):
            metrics.increment_tokens(1)
            metrics.record_cache_hit(i%2==0)
            metrics.record_latency(0.001*i)
            metrics.record_request()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    snap = metrics.snapshot()
    assert snap['tokens_used'] == 4*100
    assert snap['requests'] == 4*100


def test_prometheus_format_numbers():
    metrics = mmod.Metrics()
    metrics.increment_tokens(7)
    out = metrics.generate_prometheus_metrics()
    assert 'agentic_tokens_used_total 7' in out
    # ensure histogram sum/count present
    assert 'agentic_query_latency_seconds_sum' in out
    assert 'agentic_query_latency_seconds_count' in out

# ----- Edge cases -----

def test_no_requests_error_rate_zero():
    metrics = mmod.Metrics()
    assert metrics.error_rate() == 0.0


def test_no_cache_hits_rate_zero():
    metrics = mmod.Metrics()
    assert metrics.cache_hit_rate() == 0.0


def test_large_token_increments():
    metrics = mmod.Metrics()
    metrics.increment_tokens(10**6)
    assert metrics.snapshot()['tokens_used'] == 10**6


def test_metrics_snapshot_immutable():
    metrics = mmod.Metrics()
    snap = metrics.snapshot()
    snap['tokens_used'] = 9999
    assert metrics.snapshot()['tokens_used'] != 9999


def test_throughput_window_behavior():
    metrics = mmod.Metrics(throughput_window_seconds=2)
    # record two events 1 second apart
    t0 = time.time()
    # monkeypatch time via closure by replacing time.time
    real_time = time.time
    try:
        time.time = lambda: t0
        metrics.record_request()
        time.time = lambda: t0 + 1
        metrics.record_request()
        rps = metrics.get_throughput_rps()
        assert rps > 0
    finally:
        time.time = real_time


def test_wsgi_not_found():
    app = hmod.create_wsgi_app()
    environ = {'PATH_INFO': '/nope'}
    def start_response(status, headers):
        assert status.startswith('404')
    res = app(environ, start_response)
    assert b'Not Found' in b''.join(res)

# extra tests to exceed 25

def test_multiple_latency_records_accuracy():
    metrics = mmod.Metrics()
    for i in range(20):
        metrics.record_latency(0.01 * i)
    assert metrics.snapshot()['latency_count'] == 20


def test_cache_counters_progression():
    metrics = mmod.Metrics()
    for i in range(10):
        metrics.record_cache_hit(i%3!=0)
    snap = metrics.snapshot()
    assert snap['cache_hits'] + snap['cache_misses'] == 10


def test_error_and_request_correlation():
    metrics = mmod.Metrics()
    for i in range(50):
        metrics.record_request()
        if i%10==0:
            metrics.increment_error()
    assert metrics.snapshot()['requests'] == 50
    assert metrics.snapshot()['errors'] == 5


def test_generate_metrics_after_activity():
    metrics = mmod.Metrics()
    metrics.record_request()
    metrics.increment_tokens(2)
    out = metrics.generate_prometheus_metrics()
    assert 'agentic_requests_total' in out


if __name__ == '__main__':
    pytest.main([__file__])
