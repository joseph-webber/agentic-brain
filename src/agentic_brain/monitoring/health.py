"""Health check helpers and a minimal WSGI app for health & metrics."""
import os
import json
import socket
import time
from typing import Dict
from .metrics import global_metrics


def _tcp_check(host: str, port: int, timeout: float=1.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def dependency_checks() -> Dict[str, Dict]:
    """Check configured dependencies and return a dict of results."""
    checks = {}
    # Neo4j
    neo_host = os.environ.get('NEO4J_HOST', '127.0.0.1')
    neo_port = int(os.environ.get('NEO4J_PORT', 7687))
    checks['neo4j'] = {
        'ok': _tcp_check(neo_host, neo_port, timeout=1.0),
        'host': neo_host,
        'port': neo_port,
    }
    # LLM endpoint (user-configurable)
    llm_host = os.environ.get('LLM_HOST', '127.0.0.1')
    llm_port = int(os.environ.get('LLM_PORT', 8000))
    checks['llm'] = {
        'ok': _tcp_check(llm_host, llm_port, timeout=1.0),
        'host': llm_host,
        'port': llm_port,
    }
    # Redis or cache (optional)
    cache_host = os.environ.get('CACHE_HOST', '127.0.0.1')
    cache_port = int(os.environ.get('CACHE_PORT', 6379))
    checks['cache'] = {
        'ok': _tcp_check(cache_host, cache_port, timeout=1.0),
        'host': cache_host,
        'port': cache_port,
    }
    return checks


def get_health_status() -> Dict:
    """Return overall health status including dependency checks and metrics snapshot."""
    deps = dependency_checks()
    overall_ok = all(d['ok'] for d in deps.values())
    status = 'ok' if overall_ok else 'degraded'
    metrics_snapshot = global_metrics.snapshot()
    return {
        'status': status,
        'timestamp': int(time.time()),
        'dependencies': deps,
        'metrics': metrics_snapshot,
    }


# Minimal WSGI app so project can mount it wherever it makes sense.
# Serves /health (json) and /metrics (plain text Prometheus format)

def create_wsgi_app():
    def app(environ, start_response):
        path = environ.get('PATH_INFO', '/')
        if path.startswith('/metrics'):
            body = global_metrics.generate_prometheus_metrics().encode('utf-8')
            start_response('200 OK', [('Content-Type','text/plain; version=0.0.4')])
            return [body]
        if path.startswith('/health'):
            body = json.dumps(get_health_status()).encode('utf-8')
            start_response('200 OK', [('Content-Type','application/json')])
            return [body]
        # default
        start_response('404 Not Found', [('Content-Type','text/plain')])
        return [b'Not Found']
    return app
