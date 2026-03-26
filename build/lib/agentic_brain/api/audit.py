# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Structured Audit Logging for Agentic Brain API
===============================================

This module provides structured audit logging for security, compliance, and debugging.
All audit events are logged as JSON for easy parsing by log aggregation tools.

Features:
- Structured JSON audit events
- HTTP request/response logging middleware
- Authentication event logging
- Session lifecycle tracking
- Privacy-aware (no message content logged)

Example:
    >>> from agentic_brain.api.audit import AuditLogger, AuditMiddleware
    >>> audit = AuditLogger()
    >>> audit.log_auth("user123", success=True)

    # With FastAPI middleware:
    >>> app.add_middleware(AuditMiddleware, audit_logger=audit)

Author: Joseph Webber
License: GPL-3.0-or-later
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Environment configuration
AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "true").lower() in ("true", "1", "yes")
AUDIT_LOG_FILE = os.getenv("AUDIT_LOG_FILE", "")
AUDIT_LOG_LEVEL = os.getenv("AUDIT_LOG_LEVEL", "INFO")

# Paths to skip (health checks, metrics, static files)
SKIP_PATHS = {"/health", "/metrics", "/favicon.ico", "/docs", "/redoc", "/openapi.json"}


@dataclass
class AuditEvent:
    """
    Structured audit event for logging API interactions.

    All audit events are serialized to JSON with ISO8601 timestamps.
    Designed for compliance, security monitoring, and debugging.

    Attributes:
        timestamp: UTC timestamp of the event
        event_type: Category (request, auth, session, error)
        action: Specific action (chat, create_session, delete_session, etc.)
        user_id: User identifier if available
        session_id: Session identifier if available
        ip_address: Client IP address
        user_agent: Client user agent string
        request_path: HTTP request path
        request_method: HTTP method (GET, POST, etc.)
        response_status: HTTP response status code
        duration_ms: Request duration in milliseconds
        metadata: Additional context-specific data

    Example:
        >>> event = AuditEvent(
        ...     event_type="request",
        ...     action="chat",
        ...     user_id="user123",
        ...     request_path="/chat",
        ...     request_method="POST",
        ...     response_status=200,
        ...     duration_ms=45.2
        ... )
        >>> print(event.to_json())
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = ""  # "request", "auth", "session", "error"
    action: str = ""  # "chat", "create_session", "delete_session", etc.
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: str = ""
    request_method: str = ""
    response_status: int = 0
    duration_ms: float = 0
    metadata: dict = field(default_factory=dict)

    def to_json(self) -> str:
        """
        Serialize the audit event to a JSON string.

        Converts the timestamp to ISO8601 format and serializes
        all fields to a compact JSON string.

        Returns:
            str: JSON representation of the audit event
        """
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return json.dumps(d, default=str)

    def to_dict(self) -> dict:
        """
        Convert the audit event to a dictionary.

        Returns:
            dict: Dictionary representation with ISO timestamp
        """
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured log output.

    Formats log records as JSON, preserving the original message
    if it's already JSON, or wrapping it in a structured format.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        # If the message is already JSON (from AuditEvent.to_json), use it directly
        if isinstance(record.msg, str) and record.msg.startswith("{"):
            return record.msg

        # Otherwise, wrap in a structured format
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class AuditLogger:
    """
    Structured audit logger for API events.

    Provides methods for logging different types of audit events
    (requests, authentication, sessions, errors) in a consistent
    JSON format.

    The logger can be configured via environment variables:
    - AUDIT_ENABLED: Enable/disable audit logging (default: true)
    - AUDIT_LOG_FILE: Optional file path for audit logs
    - AUDIT_LOG_LEVEL: Logging level (default: INFO)

    Example:
        >>> audit = AuditLogger()
        >>> audit.log_request(request, response, 45.2)
        >>> audit.log_auth("user123", success=True)
        >>> audit.log_session("create", "sess_abc123", user_id="user123")
    """

    def __init__(self, name: str = "agentic_brain.audit", enabled: bool = None):
        """
        Initialize the audit logger.

        Args:
            name: Logger name for identification
            enabled: Override AUDIT_ENABLED env var (for testing)
        """
        self.logger = logging.getLogger(name)
        self.enabled = enabled if enabled is not None else AUDIT_ENABLED
        self._configure_handler()

    def _configure_handler(self):
        """Configure the logging handler with JSON formatting."""
        # Avoid duplicate handlers
        if self.logger.handlers:
            return

        # Create handler (file or stream)
        if AUDIT_LOG_FILE:
            # Ensure directory exists
            log_dir = os.path.dirname(AUDIT_LOG_FILE)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            handler = logging.FileHandler(AUDIT_LOG_FILE)
        else:
            handler = logging.StreamHandler()

        # Set JSON formatter
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

        # Set level from environment
        level = getattr(logging, AUDIT_LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(level)

        # Prevent propagation to root logger (avoid duplicate output)
        self.logger.propagate = False

    def log(self, event: AuditEvent):
        """
        Log an audit event.

        Args:
            event: The AuditEvent to log
        """
        if not self.enabled:
            return
        self.logger.info(event.to_json())

    def log_request(
        self,
        request: Request,
        response: Response,
        duration_ms: float,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        action: Optional[str] = None,
    ):
        """
        Log an HTTP request/response cycle.

        Privacy note: Does NOT log request/response bodies to avoid
        capturing sensitive message content.

        Args:
            request: Starlette request object
            response: Starlette response object
            duration_ms: Request duration in milliseconds
            user_id: Optional user identifier
            session_id: Optional session identifier
            action: Optional action name (defaults to path-based detection)
        """
        if not self.enabled:
            return

        # Determine action from path if not provided
        if action is None:
            action = self._infer_action(request.url.path, request.method)

        event = AuditEvent(
            event_type="request",
            action=action,
            user_id=user_id,
            session_id=session_id,
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            request_path=request.url.path,
            request_method=request.method,
            response_status=response.status_code,
            duration_ms=round(duration_ms, 2),
            metadata={
                "query_params": (
                    dict(request.query_params) if request.query_params else {}
                ),
            },
        )
        self.log(event)

    def log_auth(
        self,
        user_id: str,
        success: bool,
        reason: str = "",
        ip_address: Optional[str] = None,
    ):
        """
        Log an authentication event.

        Args:
            user_id: User identifier attempting authentication
            success: Whether authentication succeeded
            reason: Optional reason for failure
            ip_address: Client IP address
        """
        if not self.enabled:
            return

        event = AuditEvent(
            event_type="auth",
            action="login_success" if success else "login_failure",
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                "success": success,
                "reason": reason,
            },
        )
        self.log(event)

    def log_session(
        self,
        action: str,
        session_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """
        Log a session lifecycle event.

        Args:
            action: Session action (create, delete, expire, etc.)
            session_id: Session identifier
            user_id: Optional user identifier
            ip_address: Client IP address
            metadata: Additional context
        """
        if not self.enabled:
            return

        event = AuditEvent(
            event_type="session",
            action=action,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            metadata=metadata or {},
        )
        self.log(event)

    def log_error(
        self,
        action: str,
        error: Exception,
        request_path: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ):
        """
        Log an error event.

        Args:
            action: Action that caused the error
            error: The exception that occurred
            request_path: Request path if applicable
            user_id: Optional user identifier
            session_id: Optional session identifier
            ip_address: Client IP address
        """
        if not self.enabled:
            return

        event = AuditEvent(
            event_type="error",
            action=action,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            request_path=request_path,
            metadata={
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )
        self.log(event)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        # Check for forwarded headers (reverse proxy scenarios)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client
        if request.client:
            return request.client.host

        return "unknown"

    def _infer_action(self, path: str, method: str) -> str:
        """Infer action name from request path and method."""
        path = path.rstrip("/")

        # Common mappings
        if path == "/chat":
            return "chat"
        elif path == "/chat/stream":
            return "chat_stream"
        elif path.startswith("/session/") and path.endswith("/messages"):
            return "get_messages"
        elif path.startswith("/session/"):
            if method == "DELETE":
                return "delete_session"
            return "get_session"
        elif path == "/sessions":
            if method == "DELETE":
                return "clear_sessions"
            return "list_sessions"
        elif path == "/health":
            return "health_check"

        # Default: use path as action
        return path.replace("/", "_").strip("_") or "root"


class AuditMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette middleware for automatic request auditing.

    Automatically logs all HTTP requests with timing information.
    Skips configured paths (health checks, metrics, docs).

    Example:
        >>> from fastapi import FastAPI
        >>> from agentic_brain.api.audit import AuditLogger, AuditMiddleware
        >>>
        >>> app = FastAPI()
        >>> audit = AuditLogger()
        >>> app.add_middleware(AuditMiddleware, audit_logger=audit)
    """

    def __init__(self, app, audit_logger: AuditLogger = None):
        """
        Initialize the audit middleware.

        Args:
            app: The ASGI application
            audit_logger: AuditLogger instance (creates default if None)
        """
        super().__init__(app)
        self.audit = audit_logger or AuditLogger()

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and log audit event.

        Args:
            request: The incoming request
            call_next: The next middleware/handler

        Returns:
            Response: The response from downstream handlers
        """
        # Skip audit for excluded paths
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        # Time the request
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as e:
            # Log error and re-raise
            duration = (time.perf_counter() - start) * 1000
            self.audit.log_error(
                action=self.audit._infer_action(request.url.path, request.method),
                error=e,
                request_path=request.url.path,
                ip_address=self.audit._get_client_ip(request),
            )
            raise

        # Calculate duration
        duration = (time.perf_counter() - start) * 1000

        # Log the request
        self.audit.log_request(request, response, duration)

        return response


# Singleton instance for convenience
_default_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Get the default audit logger instance.

    Returns:
        AuditLogger: The singleton audit logger
    """
    global _default_audit_logger
    if _default_audit_logger is None:
        _default_audit_logger = AuditLogger()
    return _default_audit_logger
