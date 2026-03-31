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

"""Pydantic models for agentic-brain chatbot API."""

import re
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """Request model for chat endpoint.

    Attributes:
        message: The user's message/query
        session_id: Optional session identifier for conversation tracking
        user_id: Optional user identifier for multi-user support
        metadata: Optional metadata dictionary for extended request information
    """

    message: str = Field(
        ..., min_length=1, max_length=32000, description="The user's message"
    )
    session_id: Optional[str] = Field(
        default=None, max_length=64, description="Session ID for conversation tracking"
    )
    user_id: Optional[str] = Field(
        default=None, max_length=64, description="User ID for multi-user support"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional metadata for extended request information",
    )

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v):
        """Validate that message is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v.strip()

    @field_validator("session_id")
    @classmethod
    def session_id_format(cls, v):
        """Validate session ID format (alphanumeric with hyphens/underscores)."""
        if v is not None and v:
            # Allow alphanumeric, hyphens, underscores
            if not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise ValueError(
                    "Session ID must be alphanumeric with hyphens/underscores only"
                )
        return v

    @field_validator("user_id")
    @classmethod
    def user_id_format(cls, v):
        """Validate user ID format (alphanumeric with hyphens/underscores)."""
        if v is not None and v:
            # Allow alphanumeric, hyphens, underscores
            if not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise ValueError(
                    "User ID must be alphanumeric with hyphens/underscores only"
                )
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v):
        """Validate metadata is not overly large."""
        if v is None:
            return {}
        # Prevent overly large metadata dictionaries
        if len(str(v)) > 10000:
            raise ValueError("Metadata cannot exceed 10000 characters when serialized")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "What is the weather today?",
                    "session_id": "sess_abc123",
                    "user_id": "user_xyz789",
                    "metadata": {"source": "web_ui"},
                },
                {
                    "message": "Explain machine learning",
                    "session_id": "sess_def456",
                },
            ]
        }
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint.

    Attributes:
        response: The chatbot's response message
        session_id: The session ID for this conversation
        timestamp: When the response was generated
        message_id: Unique identifier for this message exchange
    """

    response: str = Field(..., description="The chatbot's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of response generation",
    )
    message_id: str = Field(..., description="Unique message identifier")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "response": "The weather looks sunny today!",
                    "session_id": "sess_abc123",
                    "timestamp": "2026-01-01T12:00:00Z",
                    "message_id": "msg_def456",
                },
                {
                    "response": "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
                    "session_id": "sess_abc123",
                    "timestamp": "2026-01-01T12:05:00Z",
                    "message_id": "msg_def457",
                },
            ]
        }
    )


class SessionInfo(BaseModel):
    """Session information model.

    Attributes:
        id: The session identifier
        message_count: Number of messages in this session
        created_at: When the session was created
        last_accessed: When the session was last accessed
        user_id: Optional user ID associated with session
    """

    id: str = Field(..., max_length=64, description="Session ID")
    message_count: int = Field(
        default=0, ge=0, description="Number of messages in session"
    )
    created_at: datetime = Field(..., description="Session creation timestamp")
    last_accessed: datetime = Field(..., description="Last access timestamp")
    user_id: Optional[str] = Field(
        default=None, max_length=64, description="Associated user ID"
    )

    @field_validator("id")
    @classmethod
    def validate_session_id_format(cls, v):
        """Validate session ID format."""
        if v and not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Session ID must be alphanumeric with hyphens/underscores only"
            )
        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id_format(cls, v):
        """Validate user ID format."""
        if v and not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "User ID must be alphanumeric with hyphens/underscores only"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "sess_abc123",
                    "message_count": 5,
                    "created_at": "2026-01-01T10:00:00Z",
                    "last_accessed": "2026-01-01T12:30:00Z",
                    "user_id": "user_xyz789",
                },
                {
                    "id": "sess_def456",
                    "message_count": 12,
                    "created_at": "2026-01-01T08:00:00Z",
                    "last_accessed": "2026-01-01T13:15:00Z",
                },
            ]
        }
    )


class ErrorResponse(BaseModel):
    """Error response model.

    Attributes:
        error: Error message
        detail: Detailed error information
        status_code: HTTP status code
    """

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error info")
    status_code: int = Field(..., description="HTTP status code")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "Session not found",
                    "detail": "Session ID sess_invalid does not exist",
                    "status_code": 404,
                },
                {
                    "error": "Invalid request",
                    "detail": "Message cannot be empty",
                    "status_code": 400,
                },
            ]
        }
    )


class DeleteResponse(BaseModel):
    """Delete response model.

    Attributes:
        deleted: Whether the resource was successfully deleted
        message: Confirmation message about the deletion
        resource_id: Optional identifier of the deleted resource
    """

    deleted: bool = Field(default=True, description="Whether deletion was successful")
    message: str = Field(
        default="Resource deleted successfully",
        description="Deletion confirmation message",
    )
    resource_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional identifier of the deleted resource",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "deleted": True,
                    "message": "Resource deleted successfully",
                    "resource_id": "sess_abc123",
                },
                {
                    "deleted": True,
                    "message": "Session terminated and deleted",
                    "resource_id": "user_xyz789",
                },
            ]
        }
    )


# =============================================================================
# JHipster-style API Response Wrappers
# =============================================================================


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses (JHipster pattern).

    Attributes:
        page: Current page number (0-indexed)
        size: Items per page
        total_items: Total number of items
        total_pages: Total number of pages
    """

    page: int = Field(default=0, ge=0, description="Current page (0-indexed)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")
    total_items: int = Field(default=0, ge=0, description="Total item count")
    total_pages: int = Field(default=0, ge=0, description="Total page count")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "page": 0,
                    "size": 20,
                    "total_items": 150,
                    "total_pages": 8,
                },
                {
                    "page": 1,
                    "size": 20,
                    "total_items": 75,
                    "total_pages": 4,
                },
            ]
        }
    )

    @classmethod
    def from_total(cls, page: int, size: int, total_items: int) -> "PaginationInfo":
        """Create pagination info from total items count."""
        total_pages = (total_items + size - 1) // size if size > 0 else 0
        return cls(
            page=page,
            size=size,
            total_items=total_items,
            total_pages=total_pages,
        )


class ApiResponse(BaseModel):
    """
    Standardized API response wrapper (JHipster pattern).

    All API endpoints should return this wrapper for consistency.
    This provides a predictable response structure for clients.

    Attributes:
        success: Whether the request was successful
        data: The response payload (any type)
        message: Optional human-readable message
        errors: List of error messages (if any)
        pagination: Pagination info for list responses
        _links: HATEOAS links for resource navigation
        timestamp: When the response was generated
    """

    success: bool = Field(default=True, description="Request success status")
    data: Any = Field(default=None, description="Response payload")
    message: Optional[str] = Field(default=None, description="Human-readable message")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    pagination: Optional[PaginationInfo] = Field(
        default=None, description="Pagination info"
    )
    links: dict[str, str] = Field(
        default_factory=dict,
        description="HATEOAS links",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response timestamp",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "data": {"id": "123", "name": "Example Resource"},
                    "message": "Resource retrieved successfully",
                    "errors": [],
                    "pagination": None,
                    "links": {"self": "/api/v1/resource/123"},
                    "timestamp": "2026-01-01T12:00:00Z",
                },
                {
                    "success": False,
                    "data": None,
                    "message": "Request failed",
                    "errors": ["Invalid input provided"],
                    "pagination": None,
                    "links": {},
                    "timestamp": "2026-01-01T12:05:00Z",
                },
                {
                    "success": True,
                    "data": [{"id": "1"}, {"id": "2"}],
                    "message": "Items retrieved successfully",
                    "errors": [],
                    "pagination": {"page": 0, "size": 20, "total_items": 2, "total_pages": 1},
                    "links": {"self": "/api/v1/items?page=0&size=20"},
                    "timestamp": "2026-01-01T12:10:00Z",
                },
            ]
        },
    )

    @classmethod
    def ok(
        cls,
        data: Any = None,
        message: Optional[str] = None,
        pagination: Optional[PaginationInfo] = None,
        links: Optional[dict[str, str]] = None,
    ) -> "ApiResponse":
        """Create a successful response."""
        return cls(
            success=True,
            data=data,
            message=message,
            pagination=pagination,
            links=links or {},
        )

    @classmethod
    def error(
        cls,
        errors: list[str] | str,
        message: Optional[str] = None,
        data: Any = None,
    ) -> "ApiResponse":
        """Create an error response."""
        if isinstance(errors, str):
            errors = [errors]
        return cls(
            success=False,
            data=data,
            message=message or "Request failed",
            errors=errors,
        )

    @classmethod
    def paginated(
        cls,
        data: list[Any],
        page: int,
        size: int,
        total_items: int,
        message: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> "ApiResponse":
        """Create a paginated list response."""
        pagination = PaginationInfo.from_total(page, size, total_items)

        # Generate HATEOAS links
        links = {}
        if base_url:
            links["self"] = f"{base_url}?page={page}&size={size}"
            if page > 0:
                links["first"] = f"{base_url}?page=0&size={size}"
                links["prev"] = f"{base_url}?page={page - 1}&size={size}"
            if page < pagination.total_pages - 1:
                links["next"] = f"{base_url}?page={page + 1}&size={size}"
                links["last"] = (
                    f"{base_url}?page={pagination.total_pages - 1}&size={size}"
                )

        return cls(
            success=True,
            data=data,
            message=message,
            pagination=pagination,
            links=links,
        )


class HealthIndicator(BaseModel):
    """Individual health indicator status (JHipster Actuator pattern).

    Attributes:
        status: Health status (healthy, degraded, unhealthy)
        details: Additional details about the component
    """

    status: str = Field(
        default="healthy",
        description="Health status: healthy, degraded, or unhealthy",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional health details",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "healthy",
                    "details": {"uptime": 99.9, "response_time_ms": 45},
                },
                {
                    "status": "degraded",
                    "details": {"uptime": 95.5, "response_time_ms": 250},
                },
            ]
        }
    )


class HealthResponse(BaseModel):
    """
    Health check response (JHipster Actuator pattern).

    Provides detailed health status for all system components.

    Attributes:
        status: Overall system health status
        components: Individual component health indicators
        timestamp: When the health check was performed
    """

    status: str = Field(
        default="healthy",
        description="Overall health: healthy, degraded, or unhealthy",
    )
    components: dict[str, HealthIndicator] = Field(
        default_factory=dict,
        description="Component health indicators",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Health check timestamp",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "healthy",
                    "components": {
                        "neo4j": {"status": "healthy", "details": {"connections": 5}},
                        "llm": {"status": "healthy", "details": {"provider": "openai"}},
                        "disk": {"status": "healthy", "details": {"free_gb": 50.2}},
                    },
                    "timestamp": "2026-01-01T12:00:00Z",
                },
                {
                    "status": "degraded",
                    "components": {
                        "neo4j": {"status": "healthy", "details": {"connections": 5}},
                        "llm": {"status": "degraded", "details": {"provider": "local", "latency_ms": 1500}},
                        "disk": {"status": "healthy", "details": {"free_gb": 10.5}},
                    },
                    "timestamp": "2026-01-01T12:05:00Z",
                },
            ]
        }
    )

    @classmethod
    def from_indicators(
        cls, indicators: dict[str, HealthIndicator]
    ) -> "HealthResponse":
        """Create health response from individual indicators."""
        # Determine overall status
        statuses = [ind.status for ind in indicators.values()]
        if "unhealthy" in statuses:
            overall = "unhealthy"
        elif "degraded" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"

        return cls(status=overall, components=indicators)
