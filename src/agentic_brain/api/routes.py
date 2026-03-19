# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Route handlers for the Agentic Brain Chat API.

This module contains all the HTTP route handlers for chat, streaming, and session management.
"""

import logging
import uuid
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException, status, Query, Request
from pydantic import ValidationError

from .models import ChatRequest, ChatResponse, SessionInfo
from ..streaming import StreamingResponse

logger = logging.getLogger(__name__)


# Global storage (shared with middleware)
sessions: Dict[str, Dict] = {}
session_messages: Dict[str, List[Dict]] = {}
request_counts: Dict[str, List[float]] = defaultdict(list)

# Rate limiting constants
RATE_LIMIT = 60  # requests per minute per IP
RATE_LIMIT_WINDOW = 60  # seconds


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit.
    
    Args:
        client_ip: Client IP address
        
    Returns:
        True if request is allowed, False if rate limit exceeded
    """
    import time
    
    now = time.time()
    minute_ago = now - RATE_LIMIT_WINDOW
    
    # Clean up old requests outside the window
    request_counts[client_ip] = [t for t in request_counts[client_ip] if t > minute_ago]
    
    # Check if limit exceeded
    if len(request_counts[client_ip]) >= RATE_LIMIT:
        return False
    
    # Record this request
    request_counts[client_ip].append(now)
    return True


def _generate_session_id() -> str:
    """Generate a unique session ID."""
    return f"sess_{uuid.uuid4().hex[:12]}"


def _generate_message_id() -> str:
    """Generate a unique message ID."""
    return f"msg_{uuid.uuid4().hex[:12]}"


def _ensure_session_exists(session_id: str, user_id: Optional[str] = None):
    """Ensure a session exists, create if it doesn't."""
    if session_id not in sessions:
        now = datetime.now(timezone.utc)
        sessions[session_id] = {
            "id": session_id,
            "created_at": now,
            "last_accessed": now,
            "user_id": user_id,
            "message_count": 0,
        }
        session_messages[session_id] = []
        logger.info(f"Created new session: {session_id}")
    else:
        # Update last accessed
        sessions[session_id]["last_accessed"] = datetime.now(timezone.utc)


def register_routes(app):
    """Register all route handlers with the FastAPI app."""
    
    # ============================================================================
    # Health Check Endpoint
    # ============================================================================
    
    @app.get(
        "/health",
        response_model=dict,
        summary="Health Check",
        description="Check if the API server is running and healthy",
        tags=["Health"],
    )
    async def health_check():
        """
        Health check endpoint to verify API server status.
        
        Provides basic health information including:
        - Current server status (always "healthy" if responding)
        - API version
        - Server timestamp
        - Number of active sessions
        
        This endpoint is useful for:
        - Monitoring and alerting systems
        - Load balancer health checks
        - Kubernetes liveness probes
        - Frontend connectivity verification
        
        Returns:
            dict: Health status with keys:
                - status (str): "healthy" if server is running
                - version (str): API version
                - timestamp (str): ISO 8601 server timestamp
                - sessions_active (int): Number of active chat sessions
        
        Raises:
            None: Always returns 200 if server is running
        
        Example:
            >>> import requests
            >>> response = requests.get("http://localhost:8000/health")
            >>> response.json()
            {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2026-01-15T10:30:45.123456+00:00",
                "sessions_active": 5
            }
        """
        return {
            "status": "healthy",
            "version": app.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions_active": len(sessions),
        }
    
    # ============================================================================
    # Chat Endpoints
    # ============================================================================
    
    @app.post(
        "/chat",
        response_model=ChatResponse,
        summary="Send Chat Message",
        description="Send a message to the chatbot and receive a response",
        tags=["Chat"],
        status_code=status.HTTP_200_OK,
    )
    async def chat(request: ChatRequest, req: Request) -> ChatResponse:
        """
        Send a message to the chatbot and receive a response.
        
        This is the primary endpoint for chat interactions. It:
        - Creates a new session if none provided
        - Stores the user message in conversation history
        - Generates an AI response (placeholder: echo for demo)
        - Returns the response with session information
        
        Message flow:
            1. Client sends ChatRequest with message and optional session_id
            2. Server creates session if needed
            3. User message stored in session history
            4. AI response generated (via LLM in production)
            5. Response stored in session history
            6. ChatResponse returned to client with session info
        
        Args:
            request (ChatRequest): Chat request with:
                - message (str): User's message (1-10000 chars)
                - session_id (Optional[str]): Session to continue, or None for new
                - user_id (Optional[str]): Optional user identifier for analytics
        
        Returns:
            ChatResponse: Response with:
                - response (str): Assistant's message
                - session_id (str): Session ID for continued conversation
                - message_id (str): Unique ID of response message
                - timestamp (Optional[str]): Server timestamp of response
                - metadata (Optional[dict]): Additional response metadata
        
        Raises:
            HTTPException: 400 if message is empty or invalid
            HTTPException: 422 if request validation fails
            HTTPException: 500 if processing error occurs
        
        Example:
            >>> import requests
            >>> response = requests.post(
            ...     "http://localhost:8000/chat",
            ...     json={
            ...         "message": "What is artificial intelligence?",
            ...         "session_id": "sess_abc123",
            ...         "user_id": "user_456"
            ...     }
            ... )
            >>> data = response.json()
            >>> print(data["response"])
            >>> print(f"Session: {data['session_id']}")
        """
        try:
            # Check rate limit
            client_ip = req.client.host if req.client else "unknown"
            if not check_rate_limit(client_ip):
                logger.warning(f"Rate limit exceeded for client: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Maximum 60 requests per minute allowed."
                )
            
            # Generate or use provided session ID
            session_id = request.session_id or _generate_session_id()
            _ensure_session_exists(session_id, request.user_id)
            
            # In a real implementation, this would process the message through
            # the chatbot's NLU and response generation pipeline
            # For now, we'll create a simple echo response
            message_id = _generate_message_id()
            
            # Store message in session
            session_messages[session_id].append({
                "id": message_id,
                "role": "user",
                "content": request.message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            # Generate response (placeholder - integrate with actual chat logic)
            response_text = f"Echo: {request.message}"
            response_id = _generate_message_id()
            
            # Store response in session
            session_messages[session_id].append({
                "id": response_id,
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            # Update message count
            sessions[session_id]["message_count"] += 1
            
            logger.info(f"Processed message in session {session_id}: {message_id}")
            
            return ChatResponse(
                response=response_text,
                session_id=session_id,
                message_id=response_id,
            )
            
        except Exception as e:
            logger.error(f"Error processing chat: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing message: {str(e)}",
            )
    
    # ============================================================================
    # Streaming Chat Endpoint
    # ============================================================================
    
    @app.get(
        "/chat/stream",
        summary="Stream Chat Response",
        description="Stream chat response using Server-Sent Events (SSE)",
        tags=["Chat Streaming"],
    )
    async def stream_chat(
        message: str = Query(..., min_length=1, max_length=10000, description="User message"),
        session_id: Optional[str] = Query(None, description="Session ID"),
        user_id: Optional[str] = Query(None, description="User ID"),
        provider: str = Query(default="ollama", description="LLM provider: ollama, openai, or anthropic"),
        model: str = Query(default="llama3.1:8b", description="Model name"),
        temperature: float = Query(default=0.7, ge=0.0, le=2.0, description="Sampling temperature"),
        req: Request = None,
    ):
        """
        Stream a chat response using Server-Sent Events (SSE).
        
        This endpoint streams the chatbot's response token-by-token as it's generated,
        providing an instant, ChatGPT-like user experience. Perfect for web frontends
        where users expect to see text appearing in real-time.
        
        Streaming benefits:
        - Users see response immediately instead of waiting for complete message
        - Reduces perceived latency
        - Works well with slow models or long responses
        - Browser can cancel request mid-stream
        
        Message format (client -> server):
            GET /chat/stream?message=Hello&session_id=sess_123&provider=ollama&model=llama3.1:8b
        
        Response format (server -> client, Server-Sent Events):
            event: stream
            data: {"token": "Hello", "is_start": true, "is_end": false}
            
            event: stream
            data: {"token": " there", "is_start": false, "is_end": false}
            
            event: stream
            data: {"token": "!", "is_start": false, "is_end": true, "finish_reason": "stop"}
        
        Args:
            message (str): User message to respond to (required, 1-10000 chars)
            session_id (Optional[str]): Session ID for conversation history, or None for new
            user_id (Optional[str]): Optional user identifier
            provider (str): LLM provider: "ollama", "openai", or "anthropic" (default: ollama)
            model (str): Model name (default: llama3.1:8b)
            temperature (float): Sampling temperature 0.0-2.0 (default: 0.7)
                - 0.0: Deterministic (always same response)
                - 0.7: Balanced (default)
                - 1.5-2.0: Creative/random
        
        Returns:
            StreamingResponse: Server-Sent Events stream of tokens
                Each event contains a JSON object with:
                - token (str): Token text
                - is_start (bool): True for first token
                - is_end (bool): True for final token
                - finish_reason (Optional[str]): "stop" for normal, "error" for failure
                - metadata (Optional[dict]): Additional data (session_id, etc)
        
        Raises:
            HTTPException: 400 if message is empty
            HTTPException: 500 if LLM provider error or streaming fails
        
        Example (JavaScript):
            >>> // HTML
            >>> <div id="response"></div>
            >>> 
            >>> // JavaScript
            >>> const eventSource = new EventSource(
            ...     '/chat/stream?message=What%20is%20AI?&provider=ollama'
            ... );
            >>> 
            >>> eventSource.onmessage = (event) => {
            ...     const token = JSON.parse(event.data);
            ...     if (token.token) {
            ...         document.getElementById('response').textContent += token.token;
            ...     }
            ...     if (token.is_end) {
            ...         eventSource.close();
            ...     }
            ... };
            >>> 
            >>> eventSource.onerror = () => {
            ...     console.error('Stream error');
            ...     eventSource.close();
            ... };
        """
        from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
        
        try:
            # Check rate limit
            client_ip = req.client.host if req and req.client else "unknown"
            if not check_rate_limit(client_ip):
                logger.warning(f"Rate limit exceeded for client: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Maximum 60 requests per minute allowed."
                )
            
            session_id = session_id or _generate_session_id()
            _ensure_session_exists(session_id, user_id)
            
            # Store user message
            session_messages[session_id].append({
                "id": _generate_message_id(),
                "role": "user",
                "content": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            # Get conversation history (last N messages)
            history = [
                {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                for msg in session_messages[session_id][-10:]  # Last 10 for context
                if msg["role"] in ["user", "assistant"]
            ]
            
            # Create streamer and stream response
            streamer = StreamingResponse(
                provider=provider,
                model=model,
                temperature=temperature,
            )
            
            return FastAPIStreamingResponse(
                streamer.stream_sse(message, history[:-1]),  # Exclude the message we just added
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Session-ID": session_id,
                    "X-Content-Type-Options": "nosniff",
                },
            )
        except Exception as e:
            logger.error(f"Error in stream_chat: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Streaming error: {str(e)}",
            )
    
    # ============================================================================
    # Session Management Endpoints
    # ============================================================================
    
    @app.get(
        "/session/{session_id}",
        response_model=SessionInfo,
        summary="Get Session Info",
        description="Retrieve information about a specific session",
        tags=["Sessions"],
    )
    async def get_session(session_id: str) -> SessionInfo:
        """
        Retrieve information and statistics about a specific chat session.
        
        Sessions are automatically created on first message and persist until:
        - Explicitly deleted via DELETE /session/{session_id}
        - Server is restarted (in-memory storage)
        - Manually cleared via DELETE /sessions
        
        Use this endpoint to:
        - Check conversation history metadata
        - Get session creation time and last access time
        - Count total messages in conversation
        - Identify sessions by user_id
        
        Args:
            session_id (str): The session ID to retrieve (format: "sess_" + hex)
        
        Returns:
            SessionInfo: Session information with:
                - id (str): Session ID
                - message_count (int): Total messages in session
                - created_at (datetime): Session creation timestamp
                - last_accessed (datetime): Last message timestamp
                - user_id (Optional[str]): Associated user ID if provided
        
        Raises:
            HTTPException: 404 if session_id not found
        
        Example:
            >>> import requests
            >>> response = requests.get(
            ...     "http://localhost:8000/session/sess_abc123"
            ... )
            >>> info = response.json()
            >>> print(f"Messages: {info['message_count']}")
            >>> print(f"Created: {info['created_at']}")
        """
        if session_id not in sessions:
            logger.warning(f"Session not found: {session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )
        
        session = sessions[session_id]
        return SessionInfo(
            id=session["id"],
            message_count=session["message_count"],
            created_at=session["created_at"],
            last_accessed=session["last_accessed"],
            user_id=session.get("user_id"),
        )
    
    @app.get(
        "/session/{session_id}/messages",
        response_model=List[Dict],
        summary="Get Session Messages",
        description="Retrieve all messages in a session",
        tags=["Sessions"],
    )
    async def get_session_messages(
        session_id: str,
        limit: int = Query(default=50, ge=1, le=1000, description="Max messages to return"),
    ) -> List[Dict]:
        """Get all messages in a session.
        
        Args:
            session_id: The session ID
            limit: Maximum number of messages to return
            
        Returns:
            List of messages in the session
            
        Raises:
            HTTPException: If session not found
        """
        if session_id not in sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )
        
        messages = session_messages.get(session_id, [])
        return messages[-limit:] if messages else []
    
    @app.delete(
        "/session/{session_id}",
        summary="Delete Session",
        description="Clear a session and all its messages",
        tags=["Sessions"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_session(session_id: str):
        """
        Delete a specific session and all its associated messages.
        
        This endpoint:
        - Removes session metadata (creation time, user_id, etc.)
        - Clears all messages in the session history
        - Returns 204 No Content on success
        - Returns 404 if session doesn't exist
        
        Use this to:
        - Clean up after conversation ends
        - Comply with data deletion requests (GDPR, etc.)
        - Remove sensitive conversations
        - Free memory on long-running servers
        
        Args:
            session_id (str): The session ID to delete (format: "sess_" + hex)
        
        Raises:
            HTTPException: 404 if session_id not found
        
        Example:
            >>> import requests
            >>> response = requests.delete(
            ...     "http://localhost:8000/session/sess_abc123"
            ... )
            >>> print(response.status_code)  # 204
        
        Warning:
            This operation cannot be undone. All conversation history is permanently lost.
        """
        if session_id not in sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )
        
        # Remove session and messages
        del sessions[session_id]
        if session_id in session_messages:
            del session_messages[session_id]
        
        logger.info(f"Deleted session: {session_id}")
    
    @app.delete(
        "/sessions",
        summary="Clear All Sessions",
        description="Clear all sessions and messages (use with caution)",
        tags=["Sessions"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def clear_all_sessions():
        """Clear all sessions.
        
        WARNING: This operation cannot be undone.
        """
        count = len(sessions)
        sessions.clear()
        session_messages.clear()
        logger.warning(f"Cleared all {count} sessions")
