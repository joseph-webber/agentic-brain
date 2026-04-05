from __future__ import annotations

import pytest


def test_chat_validation_whitespace_message_422(client):
    resp = client.post("/chat", json={"message": "   "})
    assert resp.status_code == 422


def test_chat_validation_invalid_session_id_chars_422(client):
    resp = client.post("/chat", json={"message": "hi", "session_id": "bad!"})
    assert resp.status_code == 422


def test_chat_validation_invalid_user_id_chars_422(client):
    resp = client.post("/chat", json={"message": "hi", "user_id": "bad!"})
    assert resp.status_code == 422


def test_chat_validation_metadata_too_large_422(client):
    big = "x" * 10001
    resp = client.post("/chat", json={"message": "hi", "metadata": {"a": big}})
    assert resp.status_code == 422


def test_chat_missing_body_422(client):
    resp = client.post("/chat")
    assert resp.status_code == 422


def test_stream_requires_message_query_422(client):
    resp = client.get("/chat/stream")
    assert resp.status_code == 422


def test_stream_temperature_out_of_range_422(client):
    resp = client.get("/chat/stream", params={"message": "hi", "temperature": 3.0})
    assert resp.status_code == 422


def test_session_messages_limit_bounds(client):
    chat = client.post("/chat", json={"message": "hi"}).json()
    session_id = chat["session_id"]

    too_low = client.get(f"/session/{session_id}/messages", params={"limit": 0})
    assert too_low.status_code == 422

    too_high = client.get(f"/session/{session_id}/messages", params={"limit": 1001})
    assert too_high.status_code == 422


def test_delete_session_unknown_returns_404(client):
    resp = client.delete("/session/does_not_exist")
    assert resp.status_code == 404


def test_saml_acs_requires_saml_response_field_400(client):
    resp = client.post("/auth/saml/acs", json={"not": "it"})
    assert resp.status_code == 400


def test_sso_callback_requires_code_422(sso_client):
    resp = sso_client.get("/auth/sso/oidc/callback", params={"state": "xyz"})
    assert resp.status_code == 422


def test_unauthorized_error_shape(auth_client):
    resp = auth_client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["status_code"] == 401
    assert body["error"]
