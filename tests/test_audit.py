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

"""
Tests for the structured audit logging system.

Tests cover:
- AuditEvent serialization
- AuditLogger output format
- AuditMiddleware request capture
- Privacy (no message content logged)
"""

import json
import logging
from datetime import UTC, datetime, timezone
from io import StringIO
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from agentic_brain.api.audit import (
    SKIP_PATHS,
    AuditEvent,
    AuditLogger,
    AuditMiddleware,
    JSONFormatter,
    get_audit_logger,
)


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_default_timestamp(self):
        """Test that timestamp defaults to UTC now."""
        before = datetime.now(UTC)
        event = AuditEvent()
        after = datetime.now(UTC)

        assert before <= event.timestamp <= after
        assert event.timestamp.tzinfo == UTC

    def test_to_json_serialization(self):
        """Test JSON serialization of audit event."""
        event = AuditEvent(
            event_type="request",
            action="chat",
            user_id="user123",
            session_id="sess_abc",
            request_path="/chat",
            request_method="POST",
            response_status=200,
            duration_ms=45.5,
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["event_type"] == "request"
        assert data["action"] == "chat"
        assert data["user_id"] == "user123"
        assert data["session_id"] == "sess_abc"
        assert data["request_path"] == "/chat"
        assert data["request_method"] == "POST"
        assert data["response_status"] == 200
        assert data["duration_ms"] == 45.5
        assert "timestamp" in data

    def test_to_json_timestamp_format(self):
        """Test that timestamp is ISO8601 formatted."""
        event = AuditEvent(timestamp=datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC))

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["timestamp"] == "2026-03-15T10:30:00+00:00"

    def test_to_dict(self):
        """Test dictionary conversion."""
        event = AuditEvent(
            event_type="auth",
            action="login_success",
            user_id="user456",
        )

        d = event.to_dict()

        assert isinstance(d, dict)
        assert d["event_type"] == "auth"
        assert d["action"] == "login_success"
        assert d["user_id"] == "user456"
        assert isinstance(d["timestamp"], str)  # Converted to ISO string

    def test_metadata_field(self):
        """Test metadata field serialization."""
        event = AuditEvent(
            event_type="session",
            action="create",
            metadata={"count": 5, "tags": ["test", "demo"]},
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["metadata"]["count"] == 5
        assert data["metadata"]["tags"] == ["test", "demo"]

    def test_optional_fields_default_none(self):
        """Test that optional fields default to None."""
        event = AuditEvent()

        assert event.user_id is None
        assert event.session_id is None
        assert event.ip_address is None
        assert event.user_agent is None


class TestJSONFormatter:
    """Tests for JSONFormatter logging formatter."""

    def test_formats_json_string_passthrough(self):
        """Test that existing JSON is passed through."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"event_type": "test"}',
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert output == '{"event_type": "test"}'

    def test_formats_plain_message_as_json(self):
        """Test that plain messages are wrapped in JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Plain text message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "Plain text message"
        assert data["level"] == "WARNING"
        assert data["logger"] == "test.logger"
        assert "timestamp" in data


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_init_creates_logger(self):
        """Test that initialization creates a logger."""
        audit = AuditLogger(name="test.audit")

        assert audit.logger.name == "test.audit"
        assert audit.enabled is True

    def test_disabled_logger_skips_logging(self):
        """Test that disabled logger doesn't log."""
        audit = AuditLogger(name="test.disabled", enabled=False)

        # Create a handler to capture output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        audit.logger.addHandler(handler)

        event = AuditEvent(event_type="test")
        audit.log(event)

        assert stream.getvalue() == ""

    def test_log_request(self):
        """Test log_request helper method."""
        audit = AuditLogger(name="test.request", enabled=True)

        # Capture log output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit.logger.handlers = [handler]

        # Create mock request/response
        mock_request = MagicMock()
        mock_request.url.path = "/chat"
        mock_request.method = "POST"
        mock_request.headers = {"user-agent": "TestClient/1.0"}
        mock_request.query_params = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_response = MagicMock()
        mock_response.status_code = 200

        audit.log_request(mock_request, mock_response, 45.5)

        output = stream.getvalue()
        data = json.loads(output.strip())

        assert data["event_type"] == "request"
        assert data["action"] == "chat"
        assert data["request_path"] == "/chat"
        assert data["request_method"] == "POST"
        assert data["response_status"] == 200
        assert data["duration_ms"] == 45.5
        assert data["ip_address"] == "127.0.0.1"

    def test_log_auth_success(self):
        """Test log_auth for successful authentication."""
        audit = AuditLogger(name="test.auth", enabled=True)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit.logger.handlers = [handler]

        audit.log_auth("user123", success=True)

        output = stream.getvalue()
        data = json.loads(output.strip())

        assert data["event_type"] == "auth"
        assert data["action"] == "login_success"
        assert data["user_id"] == "user123"
        assert data["metadata"]["success"] is True

    def test_log_auth_failure(self):
        """Test log_auth for failed authentication."""
        audit = AuditLogger(name="test.auth_fail", enabled=True)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit.logger.handlers = [handler]

        audit.log_auth("baduser", success=False, reason="Invalid password")

        output = stream.getvalue()
        data = json.loads(output.strip())

        assert data["event_type"] == "auth"
        assert data["action"] == "login_failure"
        assert data["user_id"] == "baduser"
        assert data["metadata"]["success"] is False
        assert data["metadata"]["reason"] == "Invalid password"

    def test_log_session(self):
        """Test log_session for session events."""
        audit = AuditLogger(name="test.session", enabled=True)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit.logger.handlers = [handler]

        audit.log_session(
            action="create",
            session_id="sess_abc123",
            user_id="user456",
        )

        output = stream.getvalue()
        data = json.loads(output.strip())

        assert data["event_type"] == "session"
        assert data["action"] == "create"
        assert data["session_id"] == "sess_abc123"
        assert data["user_id"] == "user456"

    def test_log_error(self):
        """Test log_error for error events."""
        audit = AuditLogger(name="test.error", enabled=True)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit.logger.handlers = [handler]

        try:
            raise ValueError("Test error message")
        except ValueError as e:
            audit.log_error(
                action="chat",
                error=e,
                request_path="/chat",
            )

        output = stream.getvalue()
        data = json.loads(output.strip())

        assert data["event_type"] == "error"
        assert data["action"] == "chat"
        assert data["metadata"]["error_type"] == "ValueError"
        assert data["metadata"]["error_message"] == "Test error message"

    def test_infer_action_from_path(self):
        """Test action inference from request paths."""
        audit = AuditLogger(name="test.infer")

        assert audit._infer_action("/chat", "POST") == "chat"
        assert audit._infer_action("/chat/stream", "GET") == "chat_stream"
        assert audit._infer_action("/session/abc123", "GET") == "get_session"
        assert audit._infer_action("/session/abc123", "DELETE") == "delete_session"
        assert audit._infer_action("/sessions", "GET") == "list_sessions"
        assert audit._infer_action("/sessions", "DELETE") == "clear_sessions"
        assert audit._infer_action("/health", "GET") == "health_check"

    def test_get_client_ip_forwarded(self):
        """Test client IP extraction from X-Forwarded-For header."""
        audit = AuditLogger(name="test.ip")

        mock_request = MagicMock()
        mock_request.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}

        ip = audit._get_client_ip(mock_request)

        assert ip == "192.168.1.1"

    def test_get_client_ip_real_ip(self):
        """Test client IP extraction from X-Real-IP header."""
        audit = AuditLogger(name="test.ip2")

        mock_request = MagicMock()
        mock_request.headers = {"x-real-ip": "10.10.10.10"}

        ip = audit._get_client_ip(mock_request)

        assert ip == "10.10.10.10"

    def test_get_client_ip_direct(self):
        """Test client IP extraction from direct connection."""
        audit = AuditLogger(name="test.ip3")

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        ip = audit._get_client_ip(mock_request)

        assert ip == "127.0.0.1"


class TestAuditMiddleware:
    """Tests for AuditMiddleware."""

    @pytest.fixture
    def app_with_middleware(self):
        """Create a test FastAPI app with audit middleware."""
        from fastapi import FastAPI

        app = FastAPI()
        audit_logger = AuditLogger(name="test.middleware", enabled=True)
        app.add_middleware(AuditMiddleware, audit_logger=audit_logger)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health_endpoint():
            return {"healthy": True}

        @app.post("/chat")
        async def chat_endpoint():
            return {"response": "Hello"}

        return app, audit_logger

    def test_middleware_logs_requests(self, app_with_middleware):
        """Test that middleware logs HTTP requests."""
        app, audit_logger = app_with_middleware

        # Capture log output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit_logger.logger.handlers = [handler]

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200

        output = stream.getvalue()
        assert output  # Should have logged something

        data = json.loads(output.strip())
        assert data["event_type"] == "request"
        assert data["request_path"] == "/test"
        assert data["request_method"] == "GET"
        assert data["response_status"] == 200

    def test_middleware_skips_health_checks(self, app_with_middleware):
        """Test that middleware skips health check paths."""
        app, audit_logger = app_with_middleware

        # Capture log output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit_logger.logger.handlers = [handler]

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200

        # Should NOT have logged anything (health is in SKIP_PATHS)
        output = stream.getvalue()
        assert output == ""

    def test_middleware_captures_duration(self, app_with_middleware):
        """Test that middleware captures request duration."""
        app, audit_logger = app_with_middleware

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit_logger.logger.handlers = [handler]

        client = TestClient(app)
        client.post("/chat")

        output = stream.getvalue()
        data = json.loads(output.strip())

        assert "duration_ms" in data
        assert data["duration_ms"] >= 0


class TestPrivacy:
    """Tests for privacy protection in audit logging."""

    def test_no_message_content_in_audit(self):
        """Test that message content is NOT logged in audit events."""
        # The audit system should only log metadata, not actual message content
        event = AuditEvent(
            event_type="session",
            action="chat",
            session_id="sess_123",
            metadata={"message_length": 150, "duration_ms": 45},
        )

        json_str = event.to_json()

        # Should NOT contain actual message text
        assert "sensitive message" not in json_str.lower()

        # Should contain only metadata
        data = json.loads(json_str)
        assert "message_length" in data["metadata"]
        assert "content" not in data
        assert "message" not in data

    def test_log_request_no_body(self):
        """Test that log_request doesn't log request body."""
        audit = AuditLogger(name="test.privacy", enabled=True)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        audit.logger.handlers = [handler]

        mock_request = MagicMock()
        mock_request.url.path = "/chat"
        mock_request.method = "POST"
        mock_request.headers = {}
        mock_request.query_params = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_response = MagicMock()
        mock_response.status_code = 200

        audit.log_request(mock_request, mock_response, 50.0)

        output = stream.getvalue()

        # Should NOT contain any body/content fields
        assert "body" not in output.lower() or '"body":' not in output
        assert "content" not in output.lower() or '"content":' not in output


class TestGetAuditLogger:
    """Tests for get_audit_logger singleton."""

    def test_returns_same_instance(self):
        """Test that get_audit_logger returns singleton."""
        import agentic_brain.api.audit as audit_module

        # Reset singleton
        audit_module._default_audit_logger = None

        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2


class TestSkipPaths:
    """Tests for SKIP_PATHS configuration."""

    def test_skip_paths_contains_health(self):
        """Test that /health is in skip paths."""
        assert "/health" in SKIP_PATHS

    def test_skip_paths_contains_metrics(self):
        """Test that /metrics is in skip paths."""
        assert "/metrics" in SKIP_PATHS

    def test_skip_paths_contains_docs(self):
        """Test that documentation paths are skipped."""
        assert "/docs" in SKIP_PATHS
        assert "/redoc" in SKIP_PATHS
        assert "/openapi.json" in SKIP_PATHS
