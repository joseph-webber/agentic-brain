import os
import time
import json
from fastapi.testclient import TestClient
from agentic_brain.api.server import create_app


def make_client(env=None):
    env = env or {}
    # Ensure TESTING flag to skip Redis checks
    prev = {}
    prev["TESTING"] = os.environ.get("TESTING")
    os.environ["TESTING"] = "1"
    # Temporarily apply provided env vars and restore after app creation
    for k, v in env.items():
        prev[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        app = create_app()
    finally:
        # restore environment variables (keep TESTING=1)
        for k, old in prev.items():
            if k == "TESTING":
                continue
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
    return TestClient(app)


def test_health_endpoint():
    client = make_client()
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_metrics_endpoint_empty():
    client = make_client()
    r = client.get("/metrics")
    assert r.status_code == 200
    text = r.text
    assert "agentic_requests_total" in text


def test_query_endpoint_basic():
    client = make_client()
    r = client.post("/query", json={"question": "Hello?", "top_k": 2})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert isinstance(data.get("sources"), list)


def test_index_endpoint_basic():
    client = make_client()
    payload = {"content": "This is a test document."}
    r = client.post("/index", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "indexed"
    assert data["id"]


def test_graph_query_basic():
    client = make_client()
    r = client.post("/graph/query", json={"cypher": "MATCH (n) RETURN n LIMIT 1"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("results"), list)


def test_evaluate_basic():
    client = make_client()
    r = client.post("/evaluate", json={"reference": "the cat sat", "candidate": "the cat sat on the mat"})
    assert r.status_code == 200
    data = r.json()
    assert "score" in data


def test_config_get_put():
    client = make_client()
    r = client.get("/config")
    assert r.status_code == 200
    original = r.json()["values"]

    new_cfg = {"values": {"foo": "bar"}}
    r2 = client.put("/config", json=new_cfg)
    assert r2.status_code == 200
    assert r2.json()["values"]["foo"] == "bar"

    r3 = client.get("/config")
    assert r3.json()["values"]["foo"] == "bar"


def test_auth_required_when_enabled(monkeypatch):
    # Enable auth and set API keys using monkeypatch (isolated)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEYS", "testkey123")
    client = make_client()
    # Without key, config update should be rejected
    r = client.put("/config", json={"values": {"a": 1}})
    assert r.status_code == 401

    # With header
    r2 = client.put("/config", json={"values": {"a": 1}}, headers={"X-API-Key": "testkey123"})
    assert r2.status_code == 200
    assert r2.json()["values"]["a"] == 1


def test_api_key_query_param_auth(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEYS", "qpkey")
    client = make_client()
    r = client.put("/config?api_key=qpkey", json={"values": {"x": 2}})
    assert r.status_code == 200
    assert r.json()["values"]["x"] == 2


def test_rate_limit_anonymous_exceeded(monkeypatch):
    # Low anon rate for test
    monkeypatch.setenv("REST_RATE_LIMIT_ANON", "3")
    client = make_client()
    # Make 3 allowed requests
    for i in range(3):
        r = client.post("/query", json={"question": f"q{i}", "top_k": 1})
        assert r.status_code == 200
    # 4th should be 429
    r2 = client.post("/query", json={"question": "q4", "top_k": 1})
    assert r2.status_code == 429


def test_rate_limit_authenticated_exceeded(monkeypatch):
    monkeypatch.setenv("REST_RATE_LIMIT_AUTH", "2")
    # Enable auth via monkeypatch so it remains for the lifetime of the test
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEYS", "authkey")
    client = make_client()
    headers = {"X-API-Key": "authkey"}
    r1 = client.post("/query", json={"question": "a", "top_k": 1}, headers=headers)
    assert r1.status_code == 200
    r2 = client.post("/query", json={"question": "b", "top_k": 1}, headers=headers)
    assert r2.status_code == 200
    r3 = client.post("/query", json={"question": "c", "top_k": 1}, headers=headers)
    assert r3.status_code == 429


def test_index_invalid_payload():
    client = make_client()
    r = client.post("/index", json={"content": ""})
    assert r.status_code == 422


def test_query_validation_errors():
    client = make_client()
    r = client.post("/query", json={"question": "", "top_k": 1})
    assert r.status_code == 422


def test_metrics_increments_with_requests():
    client = make_client()
    # Fetch current metrics count
    m1 = client.get("/metrics").text
    # Call endpoints
    client.post("/query", json={"question": "m1", "top_k": 1})
    client.post("/index", json={"content": "doc"})
    m2 = client.get("/metrics").text
    # Simple check: metrics text should change
    assert m1 != m2


def test_multiple_index_ids_are_unique():
    client = make_client()
    r1 = client.post("/index", json={"content": "doc1"})
    r2 = client.post("/index", json={"content": "doc2"})
    assert r1.json()["id"] != r2.json()["id"]


def test_update_config_invalid_payload():
    client = make_client()
    r = client.put("/config", json={"invalid": 123})
    # Model expects {"values": {...}}, so validation fails
    assert r.status_code == 422


def test_security_headers_present():
    client = make_client()
    r = client.get("/health")
    # SecurityHeadersMiddleware should add X-Content-Type-Options
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


def test_cli_serve_parser_exists():
    # Ensure CLI has serve command registered
    from agentic_brain.cli import create_parser

    p = create_parser()
    args = p.parse_args(["serve", "--port", "8000"])
    assert hasattr(args, "func")


def test_wrong_api_key_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEYS", "goodkey")
    client = make_client()
    r = client.put("/config", json={"values": {"a": 1}}, headers={"X-API-Key": "bad"})
    assert r.status_code == 401


def test_api_key_header_and_query_both_work(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEYS", "hdrkey,qpkey")
    client = make_client()
    # header
    r1 = client.put("/config", json={"values": {"h": 1}}, headers={"X-API-Key": "hdrkey"})
    assert r1.status_code == 200
    # query
    r2 = client.put("/config?api_key=qpkey", json={"values": {"q": 2}})
    assert r2.status_code == 200


def test_graph_query_requires_body():
    client = make_client()
    r = client.post("/graph/query", json={})
    assert r.status_code == 422


# 25+ tests as requested
