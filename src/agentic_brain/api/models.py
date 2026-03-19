# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Pydantic models for agentic-brain chatbot API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint.
    
    Attributes:
        message: The user's message/query
        session_id: Optional session identifier for conversation tracking
        user_id: Optional user identifier for multi-user support
    """
    
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's message"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for conversation tracking"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for multi-user support"
    )
    
    model_config = {"example": {
        "message": "What is the weather today?",
        "session_id": "sess_abc123",
        "user_id": "user_xyz789"
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
        default_factory=datetime.utcnow,
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
        description="Associated user ID"
    )
    
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
