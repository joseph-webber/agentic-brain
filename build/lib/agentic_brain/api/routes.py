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

from __future__ import annotations

"""
Route handlers for the Agentic Brain Chat API.

This module contains all the HTTP route handlers for chat, streaming, and session management.
"""

import asyncio
import logging
import os
import secrets
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timezone
from typing import Optional

from fastapi import Body, Depends, HTTPException, Query, Request, Response, status

from ..streaming import StreamingResponse
from .audit import get_audit_logger
from .auth import AuthContext, require_auth
from .models import ChatRequest, ChatResponse, SessionInfo
from .sessions import (
    RedisSessionBackend,
    SessionBackend,
    generate_message_id,
    generate_session_id,
    get_session_backend,
)

logger = logging.getLogger(__name__)


# Global session backend (lazy-initialized)
_session_backend: SessionBackend | None = None

# Rate limiting (kept in-memory for simplicity)
request_counts: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))

# Rate limiting constants
RATE_LIMIT = 60  # requests per minute per IP
RATE_LIMIT_WINDOW = 60  # seconds

# Backward compatibility aliases (used by websocket.py)
_generate_session_id = generate_session_id
_generate_message_id = generate_message_id

# Backward compatibility: in-memory dicts for legacy code
# These are deprecated - use session backend instead
sessions: dict[str, dict] = {}
session_messages: dict[str, list] = defaultdict(list)


def _ensure_session_exists(session_id: str, user_id: str | None = None) -> None:
    """Ensure a session exists in the legacy sessions dict.

    This is for backward compatibility with websocket.py.
    New code should use the session backend directly.
    """
    if session_id not in sessions:
        sessions[session_id] = {
            "id": session_id,
            "user_id": user_id,
            "created_at": datetime.now(UTC).isoformat(),
            "last_accessed": datetime.now(UTC).isoformat(),
            "message_count": 0,
        }


# Session cleanup constants
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "3600"))  # 1 hour default
CLEANUP_INTERVAL = 300  # 5 minutes

# Cleanup task tracking
_cleanup_task: asyncio.Task | None = None


def _get_backend() -> SessionBackend:
    """Get the session backend, initializing if needed."""
    global _session_backend
    if _session_backend is None:
        _session_backend = get_session_backend()
    return _session_backend


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
    # Deque with maxlen=60 handles overflow automatically
    request_counts[client_ip] = deque(
        (t for t in request_counts[client_ip] if t > minute_ago), maxlen=60
    )

    # Check if limit exceeded
    if len(request_counts[client_ip]) >= RATE_LIMIT:
        logger.warning(
            f"Rate limit hit: client={client_ip}, count={len(request_counts[client_ip])}, limit={RATE_LIMIT}"
        )
        return False

    # Record this request
    request_counts[client_ip].append(now)
    return True


async def cleanup_expired_sessions() -> None:
    """Background task to clean up expired sessions.

    Runs periodically to remove sessions that exceed SESSION_MAX_AGE.
    This prevents unbounded memory growth from long-running servers.
    Works with any session backend (memory or Redis).
    """
    backend = _get_backend()
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL)
            expired_count = await backend.cleanup_expired(SESSION_MAX_AGE)
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired sessions")
        except Exception as e:
            logger.error(f"Error in cleanup_expired_sessions: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    Starts the background session cleanup task on startup and
    cancels it on shutdown. Also handles Redis connection if using
    Redis session backend.
    """
    global _cleanup_task, _session_backend

    # Startup
    backend = _get_backend()

    # Connect to Redis if using Redis backend
    if isinstance(backend, RedisSessionBackend):
        try:
            await backend.connect()
            logger.info("Connected to Redis session backend")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis, falling back to memory: {e}")
            from .sessions import InMemorySessionBackend, reset_session_backend

            reset_session_backend()
            _session_backend = InMemorySessionBackend()
            backend = _session_backend

    _cleanup_task = asyncio.create_task(cleanup_expired_sessions())
    logger.info("Started background session cleanup task")

    yield

    # Shutdown
    if _cleanup_task:
        _cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await _cleanup_task
        logger.info("Stopped background session cleanup task")

    # Disconnect from Redis if using Redis backend
    if isinstance(backend, RedisSessionBackend):
        await backend.disconnect()


def _register_health_routes(app) -> None:
    """Register health check endpoints."""

    @app.get(
        "/health",
        response_model=dict,
        summary="Health Check",
        description="Check if the API server is running and healthy",
        tags=["health"],
    )
    async def health_check():
        """
        Health check endpoint to verify API server status.

        Provides comprehensive health information including:
        - Current server status (always "healthy" if responding)
        - API version
        - Server timestamp
        - Number of active sessions
        - Redis availability and status (BULLETPROOF)
        - LLM configuration
        - Neo4j configuration

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
                - redis: Redis health information
                - llm: LLM provider information
                - neo4j: Neo4j configuration information
                - uptime: Server uptime

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
                "sessions_active": 5,
                "redis": {
                    "status": "ok",
                    "available": true,
                    "message": "Redis is healthy"
                }
            }
        """
        backend = _get_backend()
        all_sessions = await backend.list_all()

        # Get startup time if available
        server_start_time = getattr(app, "_start_time", None)
        uptime_str = "unknown"
        if server_start_time:
            uptime = datetime.now(UTC) - server_start_time
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            seconds = uptime.seconds % 60
            if uptime.days > 0:
                uptime_str = f"{uptime.days}d {hours}h {minutes}m"
            else:
                uptime_str = f"{hours}h {minutes}m {seconds}s"

        # BULLETPROOF: Check Redis health
        redis_health = {
            "status": "unknown",
            "available": False,
            "message": "Not checked",
        }
        try:
            redis_checker = getattr(app.state, "redis_health_checker", None)
            if redis_checker:
                redis_health = redis_checker.get_health_status()
        except Exception as e:
            logger.warning(f"Could not get Redis health: {e}")
            redis_health = {
                "status": "error",
                "available": False,
                "message": f"Error checking Redis: {str(e)}",
            }

        # Check LLM configuration
        llm_status = "not_configured"
        llm_provider = os.environ.get("LLM_PROVIDER", "").lower()
        if (
            llm_provider == "groq"
            and os.environ.get("GROQ_API_KEY")
            or llm_provider == "openai"
            and os.environ.get("OPENAI_API_KEY")
            or llm_provider == "anthropic"
            and os.environ.get("ANTHROPIC_API_KEY")
            or llm_provider == "ollama"
        ):
            llm_status = "ok"
        elif os.environ.get("GROQ_API_KEY"):
            llm_provider = "groq"
            llm_status = "ok"
        elif os.environ.get("OPENAI_API_KEY"):
            llm_provider = "openai"
            llm_status = "ok"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            llm_provider = "anthropic"
            llm_status = "ok"

        # Check Neo4j configuration
        neo4j_status = "not_configured"
        neo4j_uri = os.environ.get("NEO4J_URI", "")
        neo4j_message = "Optional - chat works without it"
        if neo4j_uri:
            # Try to determine if it's connected
            neo4j_status = "configured"
            # Could add actual connection check here if needed

        return {
            "status": "healthy",
            "version": app.version,
            "timestamp": datetime.now(UTC).isoformat(),
            "sessions_active": len(all_sessions),
            "redis": redis_health,
            "llm": {
                "provider": llm_provider if llm_status == "ok" else "none",
                "status": llm_status,
            },
            "neo4j": {
                "status": neo4j_status,
                "message": neo4j_message,
            },
            "uptime": uptime_str,
        }


def _register_chat_routes(app) -> None:
    """Register chat/conversation endpoints."""

    @app.post(
        "/chat",
        response_model=ChatResponse,
        summary="Send Chat Message",
        description="Send a message to the chatbot and receive a response",
        tags=["chat"],
        status_code=status.HTTP_200_OK,
    )
    async def chat(
        request: ChatRequest,
        req: Request,
        auth: AuthContext = Depends(require_auth),
    ) -> ChatResponse:
        """
        Send a message to the chatbot and receive a response.

        This is the primary endpoint for chat interactions. It:
        - Creates a new session if none provided
        - Stores the user message in conversation history
        - Generates an AI response (placeholder: echo for demo)
        - Returns the response with session information

        Authentication:
            When AUTH_ENABLED=true, requires valid API key or JWT token.
            When AUTH_ENABLED=false (default), no authentication needed.

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
                - session_id (str | None): Session to continue, or None for new
                - user_id (str | None): Optional user identifier for analytics
            auth (AuthContext): Authentication context (auto-injected)

        Returns:
            ChatResponse: Response with:
                - response (str): Assistant's message
                - session_id (str): Session ID for continued conversation
                - message_id (str): Unique ID of response message
                - timestamp (str | None): Server timestamp of response
                - metadata (dict | None): Additional response metadata

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
            logger.info(f"API request: endpoint=/chat, client={client_ip}")
            logger.debug(
                f"Request body: message_length={len(request.message)}, session={request.session_id}, user={request.user_id}"
            )

            if not check_rate_limit(client_ip):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Maximum 60 requests per minute allowed.",
                )

            import time

            start_time = time.time()

            # Get session backend
            backend = _get_backend()

            # Generate or use provided session ID
            session_id = request.session_id or generate_session_id()
            existing_session = await backend.get(session_id)
            is_new_session = existing_session is None
            await backend.ensure_exists(session_id, request.user_id)

            # Audit log session creation if new
            audit = get_audit_logger()
            if is_new_session:
                audit.log_session(
                    action="create",
                    session_id=session_id,
                    user_id=request.user_id,
                    ip_address=client_ip,
                )

            # In a real implementation, this would process the message through
            # the chatbot's NLU and response generation pipeline
            # For now, we'll create a simple echo response
            message_id = generate_message_id()

            # Store message in session
            await backend.add_message(
                session_id,
                {
                    "id": message_id,
                    "role": "user",
                    "content": request.message,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

            # Generate response (placeholder - integrate with actual chat logic)
            response_text = f"Echo: {request.message}"
            response_id = generate_message_id()

            # Store response in session
            await backend.add_message(
                session_id,
                {
                    "id": response_id,
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

            # Update message count
            await backend.update(session_id, increment_messages=True)

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"API response: endpoint=/chat, status=200, duration={duration_ms}ms"
            )

            # Audit log chat request (privacy: no message content)
            audit.log_session(
                action="chat",
                session_id=session_id,
                user_id=request.user_id,
                ip_address=client_ip,
                metadata={
                    "message_length": len(request.message),
                    "duration_ms": duration_ms,
                },
            )

            return ChatResponse(
                response=response_text,
                session_id=session_id,
                message_id=response_id,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Chat error: endpoint=/chat, error={type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            # Audit log error
            audit = get_audit_logger()
            audit.log_error(
                action="chat",
                error=e,
                request_path="/chat",
                user_id=request.user_id if request else None,
                session_id=request.session_id if request else None,
                ip_address=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing message: {str(e)}",
            )


def _register_streaming_routes(app) -> None:
    """Register streaming chat endpoints."""

    @app.get(
        "/chat/stream",
        summary="Stream Chat Response",
        description="Stream chat response using Server-Sent Events (SSE)",
        tags=["chat"],
    )
    async def stream_chat(
        message: str = Query(
            ..., min_length=1, max_length=10000, description="User message"
        ),
        session_id: str | None = Query(None, description="Session ID"),
        user_id: str | None = Query(None, description="User ID"),
        provider: str = Query(
            default="ollama", description="LLM provider: ollama, openai, or anthropic"
        ),
        model: str = Query(default="llama3.1:8b", description="Model name"),
        temperature: float = Query(
            default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
        ),
        req: Request = None,
        auth: AuthContext = Depends(require_auth),
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
            session_id (str | None): Session ID for conversation history, or None for new
            user_id (str | None): Optional user identifier
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
                - finish_reason (str | None): "stop" for normal, "error" for failure
                - metadata (dict | None): Additional data (session_id, etc)

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
                    detail="Rate limit exceeded. Maximum 60 requests per minute allowed.",
                )

            # Get session backend
            backend = _get_backend()

            session_id = session_id or generate_session_id()
            await backend.ensure_exists(session_id, user_id)

            # Store user message
            await backend.add_message(
                session_id,
                {
                    "id": generate_message_id(),
                    "role": "user",
                    "content": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

            # Get conversation history (last N messages)
            all_messages = await backend.get_messages(session_id)
            history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in all_messages[-10:]  # Last 10 for context
                if msg["role"] in ["user", "assistant"]
            ]

            # Create streamer and stream response
            streamer = StreamingResponse(
                provider=provider,
                model=model,
                temperature=temperature,
            )

            return FastAPIStreamingResponse(
                streamer.stream_sse(
                    message, history[:-1]
                ),  # Exclude the message we just added
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


def _register_session_routes(app) -> None:
    """Register session management endpoints."""

    @app.get(
        "/session/{session_id}",
        response_model=SessionInfo,
        summary="Get Session Info",
        description="Retrieve information about a specific session",
        tags=["chat"],
    )
    async def get_session(
        session_id: str,
        auth: AuthContext = Depends(require_auth),
    ) -> SessionInfo:
        """
        Retrieve information and statistics about a specific chat session.

        Sessions are automatically created on first message and persist until:
        - Explicitly deleted via DELETE /session/{session_id}
        - Server is restarted (in-memory storage) or TTL expires (Redis)
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
                - user_id (str | None): Associated user ID if provided

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
        backend = _get_backend()
        session = await backend.get(session_id)

        if session is None:
            logger.warning(f"Session not found: {session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        return SessionInfo(
            id=session.id,
            message_count=session.message_count,
            created_at=session.created_at,
            last_accessed=session.updated_at,
            user_id=session.user_id,
        )

    @app.get(
        "/session/{session_id}/messages",
        response_model=list[dict],
        summary="Get Session Messages",
        description="Retrieve all messages in a session",
        tags=["chat"],
    )
    async def get_session_messages(
        session_id: str,
        limit: int = Query(
            default=50, ge=1, le=1000, description="Max messages to return"
        ),
        auth: AuthContext = Depends(require_auth),
    ) -> list[dict]:
        """Get all messages in a session.

        Args:
            session_id: The session ID
            limit: Maximum number of messages to return

        Returns:
            List of messages in the session

        Raises:
            HTTPException: If session not found
        """
        backend = _get_backend()
        session = await backend.get(session_id)

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        messages = await backend.get_messages(session_id)
        return messages[-limit:] if messages else []

    @app.delete(
        "/session/{session_id}",
        summary="Delete Session",
        description="Clear a session and all its messages",
        tags=["chat"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_session(
        session_id: str,
        auth: AuthContext = Depends(require_auth),
    ):
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
        backend = _get_backend()
        session = await backend.get(session_id)

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        # Get user_id before deletion for audit
        user_id = session.user_id

        # Remove session and messages
        await backend.delete(session_id)

        # Audit log session deletion
        audit = get_audit_logger()
        audit.log_session(
            action="delete",
            session_id=session_id,
            user_id=user_id,
        )

        logger.info(f"Deleted session: {session_id}")

    @app.delete(
        "/sessions",
        summary="Clear All Sessions",
        description="Clear all sessions and messages (use with caution)",
        tags=["chat"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def clear_all_sessions(
        auth: AuthContext = Depends(require_auth),
    ):
        """Clear all sessions.

        WARNING: This operation cannot be undone.
        """
        backend = _get_backend()
        count = await backend.clear_all()

        # Audit log bulk session clear
        audit = get_audit_logger()
        audit.log_session(
            action="clear_all",
            session_id="*",
            metadata={"count": count},
        )

        logger.warning(f"Cleared all {count} sessions")


def _register_setup_routes(app) -> None:
    """Register setup and diagnostics routes."""
    from agentic_brain.router import (
        ProviderChecker,
        format_provider_status_report,
        get_setup_help,
    )

    @app.get(
        "/setup",
        response_model=dict,
        summary="Setup Status and Diagnostics",
        description="Check LLM provider status and get setup instructions",
        tags=["llm"],
    )
    async def setup_status():
        """Get setup status and diagnostics for LLM providers."""
        try:
            status_dict = ProviderChecker.check_all()
            available = [s for s in status_dict.values() if s.available]
            unavailable = [s for s in status_dict.values() if not s.available]

            response = {
                "status": "configured" if available else "needs_setup",
                "message": (
                    f"✓ {len(available)} provider(s) ready"
                    if available
                    else "❌ No LLM providers configured"
                ),
                "providers": {
                    "available": [
                        {"name": s.provider.value, "reason": s.reason}
                        for s in available
                    ],
                    "unavailable": [
                        {"name": s.provider.value, "reason": s.reason}
                        for s in unavailable
                    ],
                },
                "setup_guide": format_provider_status_report(status_dict),
            }

            # If no provider available, add quick setup hint
            if not available:
                response["quick_start"] = {
                    "option_1": "GROQ (FREE, recommended)",
                    "steps": [
                        "1. Visit: https://console.groq.com",
                        "2. Sign up and get API key",
                        "3. Add to .env: GROQ_API_KEY=gsk_...",
                        "4. Restart the server",
                    ],
                }

            return response

        except Exception as e:
            logger.error(f"Setup status check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Could not check provider status",
            }

    @app.get(
        "/setup/help/{provider}",
        response_model=dict,
        summary="Get Setup Instructions for Provider",
        description="Get detailed setup instructions for a specific provider",
        tags=["llm"],
    )
    async def setup_help(provider: str):
        """Get detailed setup instructions for a specific provider."""
        try:
            help_text = get_setup_help(provider)
            return {
                "provider": provider,
                "instructions": help_text,
            }
        except Exception as e:
            logger.error(f"Setup help failed for {provider}: {e}")
            return {
                "provider": provider,
                "error": str(e),
                "available_providers": [
                    "groq",
                    "ollama",
                    "openai",
                    "anthropic",
                    "google",
                    "xai",
                    "openrouter",
                    "together",
                ],
            }


def _register_auth_routes(app) -> None:
    """Register SSO/SAML authentication helper routes.

    These routes are intentionally lightweight and primarily exist so CI
    can verify SSO/SAML wiring without requiring a live Identity
    Provider.
    """

    from agentic_brain.auth.saml_provider import SAMLConfig, SAMLProvider
    from agentic_brain.auth.sso_provider import SSOProvider, create_default_sso_provider

    saml_provider: SAMLProvider | None = None
    sso_provider: SSOProvider | None = None

    def _lazy_saml() -> SAMLProvider:
        nonlocal saml_provider
        if saml_provider is None:
            cfg = SAMLConfig(
                idp_entity_id=os.environ.get(
                    "SAML_IDP_ENTITY_ID", "https://idp.example.com/metadata"
                ),
                idp_sso_url=os.environ.get(
                    "SAML_IDP_SSO_URL", "https://idp.example.com/sso"
                ),
                idp_certificate=os.environ.get("SAML_IDP_CERTIFICATE", ""),
                sp_entity_id=os.environ.get("SAML_SP_ENTITY_ID", "agentic-brain"),
                sp_acs_url=os.environ.get(
                    "SAML_SP_ACS_URL", "http://localhost:8000/auth/saml/acs"
                ),
            )
            saml_provider = SAMLProvider(cfg)
        return saml_provider

    def _lazy_sso() -> SSOProvider:
        nonlocal sso_provider
        if sso_provider is None:
            sso_provider = create_default_sso_provider()
        return sso_provider

    @app.post(
        "/auth/saml/login",
        response_model=dict,
        summary="Initiate SAML login",
        description="Generate a SAML AuthnRequest for SP-initiated SSO flows.",
        tags=["auth"],
    )
    async def saml_login() -> dict:
        provider = _lazy_saml()
        xml = provider.create_authn_request()
        return {
            "sso_url": provider.config.idp_sso_url,
            "authn_request": xml,
        }

    @app.post(
        "/auth/saml/acs",
        response_model=dict,
        summary="SAML Assertion Consumer Service (ACS)",
        description="Validate a SAML Response and extract user attributes.",
        tags=["auth"],
    )
    async def saml_acs(payload: dict = Body(...)) -> dict:
        saml_response = payload.get("saml_response")
        if not saml_response:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'saml_response' in request body",
            )
        provider = _lazy_saml()
        return provider.validate_response(saml_response)

    @app.get(
        "/auth/saml/metadata",
        summary="SAML Service Provider metadata",
        description="Get minimal SP metadata XML for IdP configuration.",
        tags=["auth"],
    )
    async def saml_metadata() -> Response:
        provider = _lazy_saml()
        xml = provider.get_metadata()
        return Response(content=xml, media_type="application/xml")

    @app.get(
        "/auth/sso/{provider}/login",
        response_model=dict,
        summary="Initiate OAuth2/OIDC SSO login",
        description="Generate an authorization URL for the given SSO provider.",
        tags=["auth"],
    )
    async def sso_login(provider: str) -> dict:
        try:
            sso = _lazy_sso()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

        state = secrets.token_urlsafe(32)
        try:
            url = sso.get_authorization_url(provider, state)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown SSO provider '{provider}'",
            )

        return {"provider": provider, "authorization_url": url, "state": state}

    @app.get(
        "/auth/sso/{provider}/callback",
        response_model=dict,
        summary="OAuth2/OIDC SSO callback",
        description=(
            "Handle the OAuth2/OIDC callback by exchanging the authorization "
            "code for tokens and (optionally) validating the ID token."
        ),
        tags=["auth"],
    )
    async def sso_callback(provider: str, code: str, state: str | None = None) -> dict:
        try:
            sso = _lazy_sso()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

        try:
            token_data = sso.exchange_code_for_token(provider, code)
        except (RuntimeError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        id_token_payload = None
        id_token_raw = (
            token_data.get("id_token") if isinstance(token_data, dict) else None
        )
        if id_token_raw is not None:
            try:
                id_token_payload = sso.validate_id_token(provider, id_token_raw)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid ID token: {exc}",
                )

        return {
            "provider": provider,
            "state": state,
            "token": token_data,
            "id_token": id_token_payload,
        }


def register_routes(app) -> None:
    """Register all route handlers with the FastAPI app.

    This function delegates to specialized registration functions for each
    route group, keeping the codebase organized and maintainable.

    Route groups:
    - Health: /health - Server health checks
    - Chat: /chat - Synchronous chat endpoints
    - Streaming: /chat/stream - Server-Sent Events streaming
    - Sessions: /session/* - Session management endpoints
    - Setup: /setup - Setup diagnostics and guidance
    - Auth: /auth/* - SAML and SSO helper endpoints
    """
    _register_health_routes(app)
    _register_chat_routes(app)
    _register_streaming_routes(app)
    _register_session_routes(app)
    _register_setup_routes(app)
    _register_auth_routes(app)

    # Commerce webhooks (WooCommerce, etc.)
    try:
        from agentic_brain.commerce.webhooks import register_commerce_webhooks

        register_commerce_webhooks(app)
    except Exception as exc:  # pragma: no cover - harden API startup
        import logging

        logging.getLogger(__name__).warning(
            "Failed to register commerce webhooks: %s", exc
        )
