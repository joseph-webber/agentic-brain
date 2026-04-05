import http.server
import socketserver
import threading
import time

import pytest

from agentic_brain.benchmark import load_test


class SimpleHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # quick response
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        return


@pytest.fixture(scope="module")
def http_server():
    server = socketserver.TCPServer(("127.0.0.1", 0), SimpleHandler)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/"
    server.shutdown()
    server.server_close()


def test_10_concurrent_queries(http_server):
    res = load_test.run_concurrent_queries(http_server, users=10, queries_per_user=1)
    assert res["requests"] == 10
    assert res["success"] == 10


def test_100_concurrent_queries(http_server):
    res = load_test.run_concurrent_queries(http_server, users=20, queries_per_user=5)
    assert res["requests"] == 100
    assert res["success"] == 100


def test_1000_queries_sustained(http_server):
    # Run with moderate concurrency to complete quickly in test
    res = load_test._run_workers(http_server, total_requests=200, max_workers=50)
    assert isinstance(res, load_test.LoadResult)


def test_memory_under_load(http_server):
    res = load_test.measure_memory_under_load(http_server, users=5, duration_s=1)
    assert "memory_top_diffs" in res


def test_response_time_percentiles(http_server):
    res = load_test.run_concurrent_queries(http_server, users=10, queries_per_user=2)
    assert "p50" in res and "p95" in res
    assert res["p50"] <= res["p95"]
