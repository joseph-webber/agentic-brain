from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentic_brain.api import routes, sessions
from agentic_brain.api.server import create_app

pytestmark = [pytest.mark.integration, pytest.mark.api]


def make_client(monkeypatch, llm_base_url: str | None = None) -> TestClient:
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("SESSION_BACKEND", "memory")
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("OAUTH2_ENABLED", "false")
    if llm_base_url:
        monkeypatch.setenv("OLLAMA_API_BASE", llm_base_url)
    routes.request_counts.clear()
    routes._session_backend = None  # type: ignore[attr-defined]
    sessions.reset_session_backend()
    app = create_app(cors_origins=["http://example.com"])
    return TestClient(app)


def test_health_endpoint_reports_healthy(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "uptime" in body


def test_chat_creates_session_and_echoes_message(monkeypatch):
    client = make_client(monkeypatch)

    response = client.post("/chat", json={"message": "Hello brain"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "Echo: Hello brain"
    assert body["session_id"].startswith("sess_")


def test_session_messages_include_user_and_assistant(monkeypatch):
    client = make_client(monkeypatch)
    chat = client.post(
        "/chat", json={"message": "Track this session", "session_id": "sess_demo"}
    )

    assert chat.status_code == 200
    messages = client.get("/session/sess_demo/messages?limit=10").json()

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_session_delete_removes_conversation(monkeypatch):
    client = make_client(monkeypatch)
    client.post("/chat", json={"message": "Delete me", "session_id": "sess_delete"})

    deleted = client.delete("/session/sess_delete")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get("/session/sess_delete").status_code == 404


def test_clear_all_sessions_removes_everything(monkeypatch):
    client = make_client(monkeypatch)
    client.post("/chat", json={"message": "First", "session_id": "sess_one"})
    client.post("/chat", json={"message": "Second", "session_id": "sess_two"})

    cleared = client.delete("/sessions")

    assert cleared.status_code == 200
    assert cleared.json()["deleted"] is True
    assert client.get("/session/sess_one").status_code == 404
    assert client.get("/session/sess_two").status_code == 404


def test_setup_endpoint_reports_provider_status(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/setup")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"configured", "needs_setup", "error"}
    assert "providers" in body


def test_setup_help_endpoint_returns_guidance(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/setup/help/ollama")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"


def test_stream_endpoint_returns_sse_payload(monkeypatch):
    class FakeStreamContent:
        def __init__(self, payload: bytes):
            self._payload = payload

        def __aiter__(self):
            async def _gen():
                yield self._payload

            return _gen()

    class FakeStreamResponse:
        status = 200

        def __init__(self):
            self.content = FakeStreamContent(
                b'{"message": {"content": "Mock Ollama reply"}, "done": true}'
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return FakeStreamResponse()

    monkeypatch.setattr(
        "agentic_brain.streaming.stream.aiohttp.ClientSession", FakeClientSession
    )
    client = make_client(monkeypatch)

    with client.stream(
        "GET",
        "/chat/stream",
        params={"message": "stream this", "provider": "ollama", "model": "llama3.1:8b"},
    ) as response:
        assert response.status_code == 200
        payload = "".join(
            chunk if isinstance(chunk, str) else chunk.decode("utf-8")
            for chunk in response.iter_lines()
        )

    assert "data:" in payload
    assert "Mock Ollama reply" in payload
