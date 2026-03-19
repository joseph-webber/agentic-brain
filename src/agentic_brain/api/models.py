# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Pydantic models for agentic-brain chatbot API."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Request model for chat endpoint.
    
    Attributes:
        message: The user's message/query
        session_id: Optional session identifier for conversation tracking
        user_id: Optional user identifier for multi-user support
        metadata: Optional metadata dictionary for extended request information
    """
    
    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="The user's message"
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Session ID for conversation tracking"
    )
    user_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="User ID for multi-user support"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional metadata for extended request information"
    )
    
    @field_validator('message')
    @classmethod
    def message_not_empty(cls, v):
        """Validate that message is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Message cannot be empty or whitespace only')
        return v.strip()
    
    @field_validator('session_id')
    @classmethod
    def session_id_format(cls, v):
        """Validate session ID format (alphanumeric with hyphens/underscores)."""
        if v is not None and v:
            # Allow alphanumeric, hyphens, underscores
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError('Session ID must be alphanumeric with hyphens/underscores only')
        return v
    
    @field_validator('user_id')
    @classmethod
    def user_id_format(cls, v):
        """Validate user ID format (alphanumeric with hyphens/underscores)."""
        if v is not None and v:
            # Allow alphanumeric, hyphens, underscores
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError('User ID must be alphanumeric with hyphens/underscores only')
        return v
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v):
        """Validate metadata is not overly large."""
        if v is None:
            return {}
        # Prevent overly large metadata dictionaries
        if len(str(v)) > 10000:
            raise ValueError('Metadata cannot exceed 10000 characters when serialized')
        return v
    
    model_config = {"example": {
        "message": "What is the weather today?",
        "session_id": "sess_abc123",
        "user_id": "user_xyz789",
        "metadata": {"source": "web_ui"}
    }}


class ChatResponse(BaseModel):
    """Response model for chat endpoint.
    
    Attributes:
        response: The chatbot's response message
        session_id: The session ID for this conversation
        timestamp: When the response was generated
        message_id: Unique identifier for this message exchange
    """
    
    response: str = Field(
        ...,
        description="The chatbot's response"
    )
    session_id: str = Field(
        ...,
        description="Session ID for this conversation"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of response generation"
    )
    message_id: str = Field(
        ...,
        description="Unique message identifier"
    )
    
    model_config = {"example": {
        "response": "The weather looks sunny today!",
        "session_id": "sess_abc123",
        "timestamp": "2026-01-01T12:00:00Z",
        "message_id": "msg_def456"
    }}


class SessionInfo(BaseModel):
    """Session information model.
    
    Attributes:
        id: The session identifier
        message_count: Number of messages in this session
        created_at: When the session was created
        last_accessed: When the session was last accessed
        user_id: Optional user ID associated with session
    """
    
    id: str = Field(
        ...,
        max_length=64,
        description="Session ID"
    )
    message_count: int = Field(
        default=0,
        ge=0,
        description="Number of messages in session"
    )
    created_at: datetime = Field(
        ...,
        description="Session creation timestamp"
    )
    last_accessed: datetime = Field(
        ...,
        description="Last access timestamp"
    )
    user_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Associated user ID"
    )
    
    @field_validator('id')
    @classmethod
    def validate_session_id_format(cls, v):
        """Validate session ID format."""
        if v and not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Session ID must be alphanumeric with hyphens/underscores only')
        return v
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id_format(cls, v):
        """Validate user ID format."""
        if v and not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('User ID must be alphanumeric with hyphens/underscores only')
        return v
    
    model_config = {"example": {
        "id": "sess_abc123",
        "message_count": 5,
        "created_at": "2026-01-01T10:00:00Z",
        "last_accessed": "2026-01-01T12:30:00Z",
        "user_id": "user_xyz789"
    }}


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
    
    model_config = {"example": {
        "error": "Session not found",
        "detail": "Session ID sess_invalid does not exist",
        "status_code": 404
    }}
