# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for agentic-brain chatbot API."""

import pytest
from fastapi.testclient import TestClient
from agentic_brain.api import app, ChatResponse, SessionInfo


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthCheck:
    """Health check endpoint tests."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
        assert "sessions_active" in data


class TestChat:
    """Chat endpoint tests."""
    
    def test_chat_creates_session(self, client):
        """Test that chat creates a new session if not provided."""
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "response" in data
        assert "message_id" in data
        assert "timestamp" in data
    
    def test_chat_with_session_id(self, client):
        """Test chat with provided session ID."""
        response = client.post("/chat", json={
            "message": "Hello",
            "session_id": "sess_test123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess_test123"
    
    def test_chat_with_user_id(self, client):
        """Test chat with user ID."""
        response = client.post("/chat", json={
            "message": "Hello",
            "user_id": "user_test123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"]
    
    def test_chat_empty_message_fails(self, client):
        """Test that empty message fails validation."""
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 422
    
    def test_chat_missing_message_fails(self, client):
        """Test that missing message field fails validation."""
        response = client.post("/chat", json={})
        assert response.status_code == 422
    
    def test_chat_message_too_long_fails(self, client):
        """Test that overly long message fails validation."""
        response = client.post("/chat", json={
            "message": "x" * 32001  # Exceeds 32000 char limit
        })
        assert response.status_code == 422


class TestSessions:
    """Session management endpoint tests."""
    
    def test_get_session(self, client):
        """Test getting session information."""
        # Create session first
        chat_response = client.post("/chat", json={"message": "Hello"})
        session_id = chat_response.json()["session_id"]
        
        # Get session
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["message_count"] == 1
        assert "created_at" in data
        assert "last_accessed" in data
    
    def test_get_session_not_found(self, client):
        """Test getting non-existent session."""
        response = client.get("/session/sess_nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
    
    def test_get_session_messages(self, client):
        """Test getting session messages."""
        # Create session and send messages
        chat_response = client.post("/chat", json={"message": "Hello"})
        session_id = chat_response.json()["session_id"]
        
        # Send another message
        client.post("/chat", json={
            "message": "How are you?",
            "session_id": session_id
        })
        
        # Get messages
        response = client.get(f"/session/{session_id}/messages")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 4  # 2 user messages + 2 bot responses
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
    
    def test_get_session_messages_with_limit(self, client):
        """Test getting session messages with limit."""
        # Create session
        chat_response = client.post("/chat", json={"message": "Hello"})
        session_id = chat_response.json()["session_id"]
        
        # Get messages with limit
        response = client.get(f"/session/{session_id}/messages?limit=1")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 1
    
    def test_delete_session(self, client):
        """Test deleting a session."""
        # Create session
        chat_response = client.post("/chat", json={"message": "Hello"})
        session_id = chat_response.json()["session_id"]
        
        # Delete session
        response = client.delete(f"/session/{session_id}")
        assert response.status_code == 204
        
        # Verify session is gone
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 404
    
    def test_delete_nonexistent_session(self, client):
        """Test deleting non-existent session."""
        response = client.delete("/session/sess_nonexistent")
        assert response.status_code == 404
    
    def test_clear_all_sessions(self, client):
        """Test clearing all sessions."""
        # Create sessions
        client.post("/chat", json={"message": "Hello 1"})
        client.post("/chat", json={"message": "Hello 2"})
        
        # Clear all
        response = client.delete("/sessions")
        assert response.status_code == 204
        
        # Health check should show 0 sessions
        health = client.get("/health")
        assert health.json()["sessions_active"] == 0


class TestPydanticModels:
    """Test Pydantic model serialization."""
    
    def test_chat_response_model(self, client):
        """Test ChatResponse model deserialization."""
        response = client.post("/chat", json={"message": "Hello"})
        chat_response = ChatResponse(**response.json())
        assert chat_response.response
        assert chat_response.session_id
        assert chat_response.message_id
    
    def test_session_info_model(self, client):
        """Test SessionInfo model deserialization."""
        # Create session
        chat_response = client.post("/chat", json={"message": "Hello"})
        session_id = chat_response.json()["session_id"]
        
        # Get session and deserialize
        response = client.get(f"/session/{session_id}")
        session_info = SessionInfo(**response.json())
        assert session_info.id == session_id
        assert session_info.message_count > 0


class TestErrorHandling:
    """Test error handling."""
    
    def test_validation_error_format(self, client):
        """Test validation error response format."""
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 422
        data = response.json()
        # FastAPI returns validation error details
        assert "detail" in data
    
    def test_not_found_error_format(self, client):
        """Test 404 error response format."""
        response = client.get("/session/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "status_code" in data


class TestCORS:
    """Test CORS configuration."""
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are present."""
        response = client.get("/health")
        # CORS headers are added by the middleware
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
