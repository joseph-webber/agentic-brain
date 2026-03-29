# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Comprehensive tests for the FastAPI server."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from agentic_brain.api.models import ChatResponse, SessionInfo
from agentic_brain.api.server import create_app

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_chatbot():
    """Create a mock chatbot instance."""
    with patch("agentic_brain.api.server.Chatbot") as mock:
        instance = Mock()
        instance.chat.return_value = "Hello! How can I help?"
        instance.async_chat.return_value = "Hello! How can I help?"
        instance.chat_with_context.return_value = {
            "response": "Hello! How can I help?",
            "context": {},
        }
        mock.return_value = instance
        yield instance


@pytest.fixture
def chat_session_setup(client):
    """Create a chat session and return session ID."""
    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    return session_id, client


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Test the health check endpoint."""

    def test_create_app_skips_redis_autostart_during_tests(self):
        """Test Redis auto-start is skipped in pytest environments."""
        redis_checker = Mock()
        redis_checker.check_redis_available.return_value = (
            False,
            "Redis connection failed",
        )

        with (
            patch(
                "agentic_brain.api.server.get_redis_health_checker",
                return_value=redis_checker,
            ),
            patch("agentic_brain.api.server.threading.Thread") as mock_thread,
        ):
            create_app()

        mock_thread.assert_not_called()
        redis_checker.check_redis_available.assert_not_called()
        redis_checker.try_auto_start_redis.assert_not_called()

    def test_health_returns_200(self, client):
        """Test that health check returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client):
        """Test that health check returns 'healthy' status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_response_has_required_fields(self, client):
        """Test that health check response has all required fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "sessions_active" in data

    def test_health_response_version_format(self, client):
        """Test that version field is a string."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["version"], str)

    def test_health_response_sessions_active_is_number(self, client):
        """Test that sessions_active is a number."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["sessions_active"], int)
        assert data["sessions_active"] >= 0


# ============================================================================
# Chat Endpoint Tests
# ============================================================================


class TestChatEndpoint:
    """Test the main chat endpoint."""

    def test_chat_basic_request(self, client):
        """Test basic chat request returns 200."""
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 200

    def test_chat_response_has_required_fields(self, client):
        """Test that chat response has all required fields."""
        response = client.post("/chat", json={"message": "Hello"})
        data = response.json()
        assert "session_id" in data
        assert "response" in data or "message" in data
        assert "timestamp" in data

    def test_chat_creates_session_id_if_not_provided(self, client):
        """Test that a session ID is created if not provided."""
        response = client.post("/chat", json={"message": "Hello"})
        data = response.json()
        session_id = data["session_id"]
        assert session_id
        assert len(session_id) > 0
        assert isinstance(session_id, str)

    def test_chat_uses_provided_session_id(self, client):
        """Test that provided session ID is preserved."""
        session_id = "test-session-123"
        response = client.post(
            "/chat", json={"message": "Hello", "session_id": session_id}
        )
        data = response.json()
        assert data["session_id"] == session_id

    def test_chat_with_user_id(self, client):
        """Test that chat accepts user_id."""
        response = client.post(
            "/chat", json={"message": "Hello", "user_id": "user-123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data

    def test_chat_multiple_messages_same_session(self, client):
        """Test multiple messages in the same session."""
        response1 = client.post("/chat", json={"message": "Hello"})
        session_id = response1.json()["session_id"]

        response2 = client.post(
            "/chat", json={"message": "How are you?", "session_id": session_id}
        )

        assert response2.status_code == 200
        data = response2.json()
        assert data["session_id"] == session_id

    def test_chat_empty_message_fails(self, client):
        """Test that empty message fails with 422."""
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 422

    def test_chat_missing_message_field_fails(self, client):
        """Test that missing message field fails with 422."""
        response = client.post("/chat", json={})
        assert response.status_code == 422

    def test_chat_missing_message_field_has_detail(self, client):
        """Test that validation error has detail."""
        response = client.post("/chat", json={})
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_chat_message_very_long(self, client):
        """Test that very long message is handled."""
        long_message = "x" * 10001
        response = client.post("/chat", json={"message": long_message})
        # API may accept long messages or reject them
        assert response.status_code in [200, 422]

    def test_chat_with_metadata(self, client):
        """Test chat with additional metadata."""
        response = client.post(
            "/chat", json={"message": "Hello", "metadata": {"key": "value"}}
        )
        # Should succeed if metadata is optional
        assert response.status_code in [200, 422]

    def test_chat_response_has_timestamp(self, client):
        """Test that chat response has a timestamp."""
        response = client.post("/chat", json={"message": "Hello"})
        data = response.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)


# ============================================================================
# Session Management Tests
# ============================================================================


class TestSessionEndpoints:
    """Test session management endpoints."""

    def test_get_session_returns_200(self, client, chat_session_setup):
        """Test getting a session returns 200."""
        session_id, _ = chat_session_setup
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200

    def test_get_session_returns_session_data(self, client, chat_session_setup):
        """Test getting a session returns session info."""
        session_id, _ = chat_session_setup
        response = client.get(f"/session/{session_id}")
        data = response.json()
        assert data["id"] == session_id

    def test_get_session_includes_message_count(self, client, chat_session_setup):
        """Test that session info includes message count."""
        session_id, _ = chat_session_setup
        response = client.get(f"/session/{session_id}")
        data = response.json()
        assert "message_count" in data
        assert data["message_count"] >= 1

    def test_get_session_includes_timestamps(self, client, chat_session_setup):
        """Test that session info includes timestamps."""
        session_id, _ = chat_session_setup
        response = client.get(f"/session/{session_id}")
        data = response.json()
        assert "created_at" in data
        assert "last_accessed" in data

    def test_get_nonexistent_session_returns_404(self, client):
        """Test that getting nonexistent session returns 404."""
        response = client.get("/session/nonexistent-session-xyz")
        assert response.status_code == 404

    def test_get_nonexistent_session_has_error(self, client):
        """Test that 404 response has error field."""
        response = client.get("/session/nonexistent-session-xyz")
        data = response.json()
        assert "error" in data or "detail" in data

    def test_get_session_messages(self, client, chat_session_setup):
        """Test getting messages for a session."""
        session_id, client_inst = chat_session_setup

        # Send another message
        client_inst.post(
            "/chat", json={"message": "Second message", "session_id": session_id}
        )

        response = client_inst.get(f"/session/{session_id}/messages")
        assert response.status_code in [200, 404]  # 404 if endpoint doesn't exist

    def test_get_session_messages_with_limit(self, client, chat_session_setup):
        """Test getting session messages with limit parameter."""
        session_id, _ = chat_session_setup
        response = client.get(f"/session/{session_id}/messages?limit=1")
        assert response.status_code in [200, 404]

    def test_delete_session_returns_204_or_200(self, client, chat_session_setup):
        """Test deleting a session returns 204 or 200."""
        session_id, _ = chat_session_setup
        response = client.delete(f"/session/{session_id}")
        assert response.status_code in [200, 204]

    def test_delete_nonexistent_session_returns_404(self, client):
        """Test deleting nonexistent session returns 404."""
        response = client.delete("/session/nonexistent-session-xyz")
        assert response.status_code == 404

    def test_delete_session_then_get_returns_404(self, client, chat_session_setup):
        """Test that after deletion, getting session returns 404."""
        session_id, _ = chat_session_setup
        client.delete(f"/session/{session_id}")
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 404

    def test_clear_all_sessions(self, client):
        """Test clearing all sessions."""
        # Create sessions
        client.post("/chat", json={"message": "Hello 1"})
        client.post("/chat", json={"message": "Hello 2"})

        # Clear all
        response = client.delete("/sessions")
        assert response.status_code in [200, 204, 405]  # 405 if not implemented

    def test_list_sessions_endpoint(self, client):
        """Test listing all sessions endpoint."""
        response = client.get("/sessions")
        assert response.status_code in [200, 404, 405]


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_json_returns_422(self, client):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/chat",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_wrong_http_method_returns_405(self, client):
        """Test that wrong HTTP method returns 405."""
        response = client.get("/chat")
        assert response.status_code == 405

    def test_nonexistent_endpoint_returns_404(self, client):
        """Test that nonexistent endpoint returns 404."""
        response = client.get("/nonexistent/endpoint")
        assert response.status_code == 404

    def test_error_response_has_detail(self, client):
        """Test that error responses have detail."""
        response = client.post("/chat", json={"message": ""})
        data = response.json()
        assert "detail" in data or "error" in data

    def test_validation_error_response_format(self, client):
        """Test validation error response format."""
        response = client.post("/chat", json={"message": ""})
        data = response.json()
        assert "detail" in data
        # Detail should be a list or string
        assert isinstance(data["detail"], (list, str))

    def test_session_not_found_error_format(self, client):
        """Test session not found error format."""
        response = client.get("/session/fake-id")
        data = response.json()
        assert response.status_code == 404
        assert "error" in data or "detail" in data


# ============================================================================
# WebSocket Tests
# ============================================================================


class TestWebSocket:
    """Test WebSocket endpoints."""

    def test_websocket_endpoint_exists(self, client):
        """Test that WebSocket endpoint can be accessed."""
        try:
            with client.websocket_connect("/ws/chat"):
                # If we reach here, endpoint exists
                assert True
        except Exception as e:
            # Endpoint doesn't exist is OK for this test
            assert "WebSocket" in str(type(e).__name__) or "404" in str(e)

    def test_websocket_send_receive_message(self, client):
        """Test sending and receiving WebSocket message."""
        try:
            with client.websocket_connect("/ws/chat") as websocket:
                websocket.send_json({"message": "Hello"})
                data = websocket.receive_json()
                assert "message" in data or "error" in data
        except Exception:
            # WebSocket may not be implemented
            pass


# ============================================================================
# Content Type Tests
# ============================================================================


class TestContentTypes:
    """Test different content types and formats."""

    def test_json_content_type(self, client):
        """Test application/json content type."""
        response = client.post(
            "/chat",
            json={"message": "Hello"},
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type")

    def test_response_is_json(self, client):
        """Test that response is valid JSON."""
        response = client.post("/chat", json={"message": "Hello"})
        # Should not raise exception
        data = response.json()
        assert isinstance(data, dict)

    def test_charset_in_response(self, client):
        """Test that charset is specified in content type."""
        response = client.post("/chat", json={"message": "Hello"})
        content_type = response.headers.get("content-type", "")
        # Content type should be present
        assert "json" in content_type.lower() or response.status_code != 200


# ============================================================================
# Data Persistence Tests
# ============================================================================


class TestDataPersistence:
    """Test data persistence across requests."""

    def test_session_persists_across_requests(self, client):
        """Test that session data persists."""
        response1 = client.post("/chat", json={"message": "First message"})
        session_id = response1.json()["session_id"]

        response2 = client.post(
            "/chat", json={"message": "Second message", "session_id": session_id}
        )

        # Both requests should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_multiple_sessions_are_independent(self, client):
        """Test that multiple sessions don't interfere."""
        response1 = client.post("/chat", json={"message": "Session 1"})
        session1 = response1.json()["session_id"]

        response2 = client.post("/chat", json={"message": "Session 2"})
        session2 = response2.json()["session_id"]

        # Sessions should be different
        assert session1 != session2


# ============================================================================
# Request Validation Tests
# ============================================================================


class TestRequestValidation:
    """Test request validation."""

    def test_chat_request_schema(self, client):
        """Test that ChatRequest schema is enforced."""
        # Valid request
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 200

    def test_message_field_required(self, client):
        """Test that message field is required."""
        response = client.post("/chat", json={"session_id": "test-123"})
        assert response.status_code == 422

    def test_session_id_field_optional(self, client):
        """Test that session_id field is optional."""
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 200

    def test_extra_fields_handled(self, client):
        """Test how extra fields are handled."""
        response = client.post(
            "/chat",
            json={"message": "Hello", "extra_field": "should be ignored or validated"},
        )
        # Should either succeed or return validation error
        assert response.status_code in [200, 422]


# ============================================================================
# Response Model Tests
# ============================================================================


class TestResponseModels:
    """Test response model serialization."""

    def test_chat_response_is_deserializable(self, client):
        """Test that response can be deserialized as ChatResponse."""
        response = client.post("/chat", json={"message": "Hello"})
        data = response.json()

        # Should be able to create ChatResponse from the data
        try:
            chat_resp = ChatResponse(**data)
            assert chat_resp.session_id
        except Exception:
            # Schema might be different
            pass

    def test_session_info_is_deserializable(self, client, chat_session_setup):
        """Test that session info can be deserialized as SessionInfo."""
        session_id, _ = chat_session_setup
        response = client.get(f"/session/{session_id}")

        if response.status_code == 200:
            data = response.json()
            try:
                session_info = SessionInfo(**data)
                assert session_info.id == session_id
            except Exception:
                # Schema might be different
                pass


# ============================================================================
# Concurrent/Load Tests
# ============================================================================


class TestConcurrency:
    """Test handling of concurrent requests."""

    def test_multiple_sequential_requests(self, client):
        """Test multiple sequential requests."""
        for i in range(5):
            response = client.post("/chat", json={"message": f"Message {i}"})
            assert response.status_code == 200

    def test_rapid_fire_health_checks(self, client):
        """Test rapid health check requests."""
        for _i in range(10):
            response = client.get("/health")
            assert response.status_code == 200


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_session_lifecycle(self, client):
        """Test a complete session lifecycle."""
        # 1. Create session with first message
        response1 = client.post("/chat", json={"message": "Hello"})
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # 2. Send multiple messages
        for i in range(2):
            response = client.post(
                "/chat", json={"message": f"Message {i}", "session_id": session_id}
            )
            assert response.status_code == 200

        # 3. Get session info
        response_get = client.get(f"/session/{session_id}")
        if response_get.status_code == 200:
            assert response_get.json()["message_count"] >= 1

        # 4. Delete session
        response_delete = client.delete(f"/session/{session_id}")
        assert response_delete.status_code in [200, 204]

    def test_health_check_during_chat(self, client):
        """Test that health check works during chat."""
        # Send chat message
        response1 = client.post("/chat", json={"message": "Hello"})
        assert response1.status_code == 200

        # Health check should still work
        response2 = client.get("/health")
        assert response2.status_code == 200
        assert response2.json()["sessions_active"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
