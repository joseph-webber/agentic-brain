from __future__ import annotations

import json

import pytest
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse


class DummyStreamingResponse:
    def __init__(self, provider: str, model: str, temperature: float):
        self.provider = provider
        self.model = model
        self.temperature = temperature

    async def stream_sse(self, message: str, history: list[dict]):
        # Minimal SSE payloads (FastAPI StreamingResponse expects chunks).
        payload1 = {"token": "Hello", "is_start": True, "is_end": False}
        payload2 = {
            "token": " world",
            "is_start": False,
            "is_end": True,
            "finish_reason": "stop",
        }
        yield f"data: {json.dumps(payload1)}\n\n"
        yield f"data: {json.dumps(payload2)}\n\n"

    def as_fastapi_response(self, message: str, history: list[dict], headers=None):
        return FastAPIStreamingResponse(
            self.stream_sse(message, history),
            media_type="text/event-stream",
            headers=headers or {},
        )


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "version" in body


def test_chat_creates_session_and_echoes(client):
    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "Echo: hi"
    assert body["session_id"]
    assert body["message_id"]


def test_chat_reuses_session_id(client):
    first = client.post("/chat", json={"message": "hi"}).json()
    resp = client.post(
        "/chat", json={"message": "again", "session_id": first["session_id"]}
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == first["session_id"]


def test_get_session_info_404_for_unknown(client):
    resp = client.get("/session/does_not_exist")
    assert resp.status_code == 404


def test_session_lifecycle_get_messages_delete(client):
    chat = client.post("/chat", json={"message": "hi"}).json()
    session_id = chat["session_id"]

    info = client.get(f"/session/{session_id}")
    assert info.status_code == 200
    assert info.json()["id"] == session_id

    messages = client.get(f"/session/{session_id}/messages")
    assert messages.status_code == 200
    assert len(messages.json()) == 2

    deleted = client.delete(f"/session/{session_id}")
    assert deleted.status_code == 200

    missing = client.get(f"/session/{session_id}")
    assert missing.status_code == 404


def test_get_session_messages_limit_parameter(client):
    chat = client.post("/chat", json={"message": "hi"}).json()
    session_id = chat["session_id"]

    # Add another exchange (2 more messages)
    client.post("/chat", json={"message": "two", "session_id": session_id})

    resp = client.get(f"/session/{session_id}/messages", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_clear_all_sessions(client):
    client.post("/chat", json={"message": "hi"})
    resp = client.delete("/sessions")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_setup_status_ok(client):
    resp = client.get("/setup")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"configured", "needs_setup", "error"}


def test_setup_help_provider_currently_returns_500_due_to_response_model(client):
    """/setup/help/{provider} should return a validated response payload."""

    from fastapi.testclient import TestClient

    with TestClient(client.app, raise_server_exceptions=False) as safe_client:
        resp = safe_client.get("/setup/help/groq")

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "groq"
    assert body["title"].startswith("Setup")
    assert "steps" in body


def test_chat_stream_sse_headers_and_body(client, monkeypatch):
    from agentic_brain.api import routes

    monkeypatch.setattr(routes, "StreamingResponse", DummyStreamingResponse)

    resp = client.get("/chat/stream", params={"message": "hello"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "X-Session-ID" in resp.headers

    body = resp.text
    assert "data:" in body
    assert "Hello" in body


def test_chat_stream_validation_requires_message(client):
    resp = client.get("/chat/stream")
    assert resp.status_code == 422


def test_openapi_unknown_path_404(client):
    resp = client.get("/nope")
    assert resp.status_code == 404


def test_saml_login_and_metadata(client):
    login = client.post("/auth/saml/login")
    assert login.status_code == 200
    body = login.json()
    assert "sso_url" in body
    assert "authn_request" in body
    assert body["authn_request"].startswith("<")

    md = client.get("/auth/saml/metadata")
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("application/xml")
    assert "EntityDescriptor" in md.text


def test_saml_acs_missing_payload_returns_400(client):
    resp = client.post("/auth/saml/acs", json={})
    assert resp.status_code == 400


def test_saml_acs_invalid_issuer_yields_500(client):
    from fastapi.testclient import TestClient

    bad_xml = """<samlp:Response xmlns:samlp=\"urn:oasis:names:tc:SAML:2.0:protocol\" xmlns:saml=\"urn:oasis:names:tc:SAML:2.0:assertion\">\n  <saml:Issuer>https://evil.example.com</saml:Issuer>\n</samlp:Response>"""

    with TestClient(client.app, raise_server_exceptions=False) as safe_client:
        resp = safe_client.post("/auth/saml/acs", json={"saml_response": bad_xml})

    assert resp.status_code == 500


def test_sso_oidc_login_and_callback_errors(sso_client):
    ok = sso_client.get("/auth/sso/oidc/login")
    assert ok.status_code == 200
    data = ok.json()
    assert data["provider"] == "oidc"
    assert "authorization_url" in data
    assert "state" in data

    unknown = sso_client.get("/auth/sso/unknown/login")
    assert unknown.status_code == 404

    # Callback requires a real HTTP client configured; this should return 400.
    cb = sso_client.get("/auth/sso/oidc/callback", params={"code": "abc", "state": "xyz"})
    assert cb.status_code == 400
