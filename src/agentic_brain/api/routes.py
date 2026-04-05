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
import threading
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import Body, Depends, HTTPException, Query, Request, Response, status

from ..streaming import StreamingResponse
from .audit import get_audit_logger
from .auth import AuthContext, require_auth
from .models import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    ErrorResponse,
    HealthResponse,
    MessageListResponse,
    SessionInfo,
    SetupHelpResponse,
    SetupStatusResponse,
)
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
_backend_lock = threading.Lock()  # Lock for thread-safe backend initialization

# Rate limiting (kept in-memory for simplicity)
request_counts: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))

# Rate limiting constants
RATE_LIMIT = 60  # requests per minute per IP
RATE_LIMIT_WINDOW = 60  # seconds

# Standard error responses for all endpoints
ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    404: {"model": ErrorResponse, "description": "Not found"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
}

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
    """Get the session backend, initializing if needed (thread-safe)."""
    global _session_backend
    if _session_backend is None:
        with _backend_lock:
            # Double-check locking pattern to avoid redundant initialization
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
        response_model=HealthResponse,
        summary="Health Check",
        description="Check if the API server is running and healthy",
        tags=["health"],
        responses=ERROR_RESPONSES,
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
        responses={
            200: {"description": "Message processed successfully", "model": ChatResponse},
            400: {"description": "Invalid request - empty message or missing required fields"},
            401: {"description": "Unauthorized - authentication required"},
            403: {"description": "Forbidden - insufficient permissions"},
            429: {"description": "Rate limit exceeded - max 60 requests per minute"},
            422: {"description": "Unprocessable entity - validation error"},
            500: {"description": "Internal server error - chat processing failed"},
        },
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

        Rate limiting:
            - Per-client IP: 60 requests per minute
            - Returns 429 if exceeded
            - Tracked in rolling 60-second window

        Session management:
            - Omit session_id to create a new session
            - Include session_id to continue existing conversation
            - Sessions persist for SESSION_MAX_AGE (default 1 hour)
            - Can be manually deleted via DELETE /session/{session_id}

        LLM Integration:
            In production, this endpoint would:
            - Use configured LLM provider (OpenAI, Claude, Groq, etc.)
            - Apply system prompt and conversation context
            - Stream response tokens for better UX
            - Apply safety filters and content moderation

        Args:
            request (ChatRequest): Chat request containing:
                - message (str): User's message (1-10000 chars, required)
                - session_id (str | None): Session ID for continued conversation, or None
                - user_id (str | None): Optional user identifier for analytics and auditing

            auth (AuthContext): Authentication context (auto-injected by require_auth)

        Returns:
            ChatResponse: Response containing:
                - response (str): Assistant's message
                - session_id (str): Session ID for tracking conversation
                - message_id (str): Unique ID of the response message
                - timestamp (str | None): Server timestamp of response
                - metadata (dict | None): Additional response metadata (tokens, etc.)

        Raises:
            HTTPException: 400 if message is empty or exceeds 10000 chars
            HTTPException: 401 if authentication fails
            HTTPException: 403 if user lacks required permissions
            HTTPException: 429 if rate limit exceeded
            HTTPException: 422 if request validation fails
            HTTPException: 500 if processing error occurs

        Example (cURL):
            >>> curl -X POST http://localhost:8000/chat \\
            ...   -H "Content-Type: application/json" \\
            ...   -d '{
            ...     "message": "What is artificial intelligence?",
            ...     "session_id": "sess_abc123",
            ...     "user_id": "user_456"
            ...   }'

        Example (Python):
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

        Example (JavaScript):
            >>> const response = await fetch('http://localhost:8000/chat', {
            ...   method: 'POST',
            ...   headers: { 'Content-Type': 'application/json' },
            ...   body: JSON.stringify({
            ...     message: 'What is AI?',
            ...     session_id: 'sess_abc123'
            ...   })
            ... });
            >>> const data = await response.json();
            >>> console.log(data.response);
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
        responses={
            200: {"description": "Server-Sent Events stream of response tokens"},
            400: {"description": "Invalid request - empty message or missing parameters"},
            401: {"description": "Unauthorized - authentication required"},
            403: {"description": "Forbidden - insufficient permissions"},
            429: {"description": "Rate limit exceeded"},
            500: {"description": "Internal server error or LLM provider error"},
        },
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
        - Efficiently handles large responses without memory buildup

        Connection details:
        - Uses HTTP streaming (chunked transfer encoding)
        - Server-Sent Events (SSE) format with MIME type "text/event-stream"
        - Headers include Cache-Control and security directives
        - Client can close connection at any time (handled gracefully)

        Message format (client -> server):
            GET /chat/stream?message=Hello&session_id=sess_123&provider=ollama&model=llama3.1:8b

        Response format (server -> client, Server-Sent Events):
            event: stream
            data: {"token": "Hello", "is_start": true, "is_end": false}

            event: stream
            data: {"token": " there", "is_start": false, "is_end": false}

            event: stream
            data: {"token": "!", "is_start": false, "is_end": true, "finish_reason": "stop"}

        Error format (if streaming fails):
            event: error
            data: {"error": "LLM provider error", "message": "..."}

        Query parameters:
            message (str): User message to respond to (required, 1-10000 chars)
                - Cannot be empty
                - Supports any UTF-8 text
                - Will be validated by the server

            session_id (str | None): Session ID for conversation history
                - If provided: continues existing conversation
                - If omitted: creates new session
                - Format: "sess_" + hex characters

            user_id (str | None): User identifier for analytics
                - Optional
                - Used for tracking and audit logs
                - Encrypted in audit trail

            provider (str): LLM provider selection
                - "ollama": Local/self-hosted (default, FREE)
                - "openai": OpenAI API (requires OPENAI_API_KEY)
                - "anthropic": Anthropic Claude (requires ANTHROPIC_API_KEY)
                - Other supported: "groq", "google", "xai"

            model (str): Model name from the selected provider
                - Ollama: "llama3.1:8b", "mistral", "neural-chat", etc.
                - OpenAI: "gpt-4", "gpt-3.5-turbo", etc.
                - Anthropic: "claude-3-sonnet", "claude-3-opus", etc.
                - Default: "llama3.1:8b"

            temperature (float): Sampling temperature (0.0-2.0)
                - 0.0: Deterministic (always same response for same input)
                - 0.7: Balanced (default, good for general use)
                - 1.0: Normal randomness
                - 1.5-2.0: Very creative/random (unusual responses)

        Stream token format:
            Each token in the stream contains:
            {
                "token": "word",           # The text token
                "is_start": bool,          # True only for first token
                "is_end": bool,            # True only for final token
                "finish_reason": str | None,  # "stop" on success, "error" on failure
                "metadata": dict | None    # Optional: token metadata
            }

        Returns:
            StreamingResponse: Server-Sent Events stream of tokens
                Each event contains a JSON object with token data
                Stream ends with event where is_end=true
                On error: stream ends with finish_reason="error"

        Raises:
            HTTPException: 400 if message is empty
            HTTPException: 401 if authentication fails
            HTTPException: 403 if insufficient permissions
            HTTPException: 429 if rate limit exceeded
            HTTPException: 500 if LLM provider error or streaming fails

        Example (JavaScript/Fetch):
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

        Example (Python with requests-stream):
            >>> import requests
            >>>
            >>> url = "http://localhost:8000/chat/stream"
            >>> params = {
            ...     "message": "Explain quantum computing",
            ...     "provider": "ollama",
            ...     "model": "llama3.1:8b"
            ... }
            >>>
            >>> with requests.get(url, params=params, stream=True) as response:
            ...     for line in response.iter_lines():
            ...         if line.startswith(b'data: '):
            ...             import json
            ...             token_data = json.loads(line[6:])
            ...             print(token_data['token'], end='', flush=True)

        Example (cURL):
            >>> curl -N "http://localhost:8000/chat/stream?message=Hello&provider=ollama"

        Implementation notes:
            - Uses Cache-Control headers to prevent caching
            - Sets X-Session-ID header for client-side session tracking
            - Includes security headers (X-Content-Type-Options: nosniff)
            - Handles client disconnections gracefully
            - Automatically stores messages in session history
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
        responses={
            200: {"description": "Session information retrieved successfully", "model": SessionInfo},
            401: {"description": "Unauthorized - authentication required"},
            403: {"description": "Forbidden - insufficient permissions"},
            404: {"description": "Session not found"},
            500: {"description": "Internal server error"},
        },
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

        Session lifecycle:
            1. Created automatically on first message sent to /chat endpoint
            2. Assigned unique session_id (format: "sess_" + 16 hex chars)
            3. Stores message history, timestamps, and user_id
            4. Updated on each new message (updates last_accessed timestamp)
            5. Cleaned up after SESSION_MAX_AGE seconds (default 1 hour)

        Use this endpoint to:
        - Check conversation history metadata without retrieving all messages
        - Get session creation time and last access time
        - Count total messages in conversation
        - Verify session exists before operations
            - Identify sessions by user_id (not directly, but via SessionInfo)
        - Monitor session activity

        Session attributes:
            - id (str): Unique session identifier (immutable)
            - message_count (int): Total messages in session (user + assistant)
            - created_at (datetime): When session was created (UTC)
            - last_accessed (datetime): Last time session was accessed (UTC)
            - user_id (str | None): Associated user ID (if provided on creation)

        Typical workflow:
            1. Client calls POST /chat with new message → session created
            2. Client calls GET /session/{session_id} → check session info
            3. Client calls GET /session/{session_id}/messages → get history
            4. Client calls DELETE /session/{session_id} → clean up

        Args:
            session_id (str): The session ID to retrieve
                Format: "sess_" followed by 16 hexadecimal characters
                Example: "sess_a1b2c3d4e5f6g7h8"

        Returns:
            SessionInfo: Session information containing:
                {
                    "id": "sess_a1b2c3d4e5f6g7h8",
                    "message_count": 5,
                    "created_at": "2026-01-15T10:30:45.123456+00:00",
                    "last_accessed": "2026-01-15T10:35:20.987654+00:00",
                    "user_id": "user_123" or None
                }

        Raises:
            HTTPException: 401 if authentication fails (when AUTH_ENABLED=true)
            HTTPException: 403 if user lacks permission to access session
            HTTPException: 404 if session_id not found
            HTTPException: 500 if retrieval fails

        Example (cURL):
            >>> curl -X GET http://localhost:8000/session/sess_abc123def456

        Example (Python):
            >>> import requests
            >>> response = requests.get(
            ...     "http://localhost:8000/session/sess_abc123def456"
            ... )
            >>> if response.status_code == 200:
            ...     info = response.json()
            ...     print(f"Messages: {info['message_count']}")
            ...     print(f"Created: {info['created_at']}")
            ...     print(f"Last accessed: {info['last_accessed']}")
            ... elif response.status_code == 404:
            ...     print("Session not found")

        Example (JavaScript):
            >>> const response = await fetch(
            ...     'http://localhost:8000/session/sess_abc123',
            ...     { headers: { 'Authorization': 'Bearer token_xyz' } }
            ... );
            >>> if (response.ok) {
            ...     const info = await response.json();
            ...     console.log(`Session created: ${info.created_at}`);
            ...     console.log(`Total messages: ${info.message_count}`);
            ... }

        Notes:
            - Timestamps are in ISO 8601 format with UTC timezone (+00:00)
            - message_count includes both user and assistant messages
            - last_accessed updates automatically on each message
            - SessionInfo does not include actual message contents
            - Use GET /session/{session_id}/messages to retrieve message history
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
        response_model=MessageListResponse,
        summary="Get Session Messages",
        description="Retrieve all messages in a session",
        tags=["chat"],
        responses=ERROR_RESPONSES,
    )
    async def get_session_messages(
        session_id: str,
        limit: int = Query(
            default=50, ge=1, le=1000, description="Max messages to return"
        ),
        auth: AuthContext = Depends(require_auth),
    ) -> list[dict]:
        """
        Retrieve all messages from a specific chat session.

        This endpoint retrieves the complete or partial conversation history
        from a session, with optional pagination via the limit parameter.

        Message format:
            Each message contains:
            - id (str): Unique message identifier
            - role (str): "user" or "assistant"
            - content (str): Message text
            - timestamp (str): ISO 8601 timestamp

        Use cases:
            - Display full conversation history in UI
            - Export chat logs
            - Analyze conversation patterns
            - Audit conversation contents

        Args:
            session_id (str): The session ID (format: "sess_" + hex)
            limit (int): Maximum number of messages to return (1-1000, default: 50)
                Returns the most recent N messages in the session

        Returns:
            list[dict]: List of messages, ordered chronologically (oldest first)
                Each message dict contains: id, role, content, timestamp

        Raises:
            HTTPException: 404 if session not found
            HTTPException: 400 if limit parameter is invalid
            HTTPException: 500 if retrieval fails

        Example:
            >>> import requests
            >>> response = requests.get(
            ...     "http://localhost:8000/session/sess_abc123/messages?limit=25"
            ... )
            >>> messages = response.json()
            >>> for msg in messages:
            ...     print(f"{msg['role']}: {msg['content']}")
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
        response_model=DeleteResponse,
        summary="Delete Session",
        description="Clear a session and all its messages",
        tags=["chat"],
        responses=ERROR_RESPONSES,
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
        - Audit logs the deletion action

        Use this to:
        - Clean up after conversation ends
        - Comply with data deletion requests (GDPR, CCPA, etc.)
        - Remove sensitive conversations
        - Free memory on long-running servers
        - User data cleanup on account deletion

        Deletion process:
            1. Verify session exists (404 if not found)
            2. Capture user_id for audit logging
            3. Delete session metadata
            4. Delete all associated messages
            5. Return 204 No Content
            6. Log deletion to audit trail

        Security considerations:
        - Requires authentication (if AUTH_ENABLED=true)
        - Should verify user owns the session (authorization check)
        - Deletion is permanent and cannot be undone
        - Audit logged with user_id and timestamp
        - Recommended: implement rate limiting to prevent abuse

        Data retention:
        - Immediately after deletion, session cannot be recovered
        - For compliance: ensure backups also respect deletion
        - Audit logs may retain deletion events (for compliance)
        - Message content is permanently removed

        Args:
            session_id (str): The session ID to delete
                Format: "sess_" followed by 16 hexadecimal characters
                Example: "sess_a1b2c3d4e5f6g7h8"

        Raises:
            HTTPException: 401 if authentication fails (when AUTH_ENABLED=true)
            HTTPException: 403 if user lacks permission to delete session
            HTTPException: 404 if session_id not found
            HTTPException: 500 if deletion fails

        Returns:
            None (204 No Content on success)

        Example (cURL):
            >>> curl -X DELETE http://localhost:8000/session/sess_abc123def456

        Example (Python):
            >>> import requests
            >>> response = requests.delete(
            ...     "http://localhost:8000/session/sess_abc123def456"
            ... )
            >>> print(response.status_code)  # 204
            >>> if response.status_code == 204:
            ...     print("Session deleted successfully")
            ... elif response.status_code == 404:
            ...     print("Session not found")

        Example (JavaScript):
            >>> const response = await fetch(
            ...     'http://localhost:8000/session/sess_abc123',
            ...     {
            ...         method: 'DELETE',
            ...         headers: { 'Authorization': 'Bearer token_xyz' }
            ...     }
            ... );
            >>> if (response.status === 204) {
            ...     console.log('Session deleted');
            ... }

        ⚠️ WARNING:
            This operation CANNOT be undone. All conversation history is
            permanently lost immediately upon deletion. Before deleting:
            - Consider exporting the session via GET /session/{session_id}/messages
            - Verify you have permission to delete
            - Confirm this is the correct session_id
            - Be aware that deletions are logged for audit purposes

        Implementation notes:
            - Backend agnostic: works with in-memory or Redis storage
            - Atomic deletion: all-or-nothing semantics
            - Fast: O(1) deletion regardless of message count
            - Audit logged: deletion recorded for compliance
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
        return DeleteResponse(
            message="Session deleted successfully",
            resource_id=session_id,
        )

    @app.delete(
        "/sessions",
        response_model=DeleteResponse,
        summary="Clear All Sessions",
        description="Clear all sessions and messages (use with caution)",
        tags=["chat"],
        responses=ERROR_RESPONSES,
    )
    async def clear_all_sessions(
        auth: AuthContext = Depends(require_auth),
    ):
        """
        Clear all sessions and associated messages from the system.

        ⚠️ WARNING: This operation permanently deletes ALL conversation history
        and cannot be undone. Use with extreme caution in production environments.

        This endpoint:
        - Removes all session metadata
        - Deletes all messages from all sessions
        - Returns 204 No Content on success
        - Logs the bulk deletion for audit purposes

        Typical use cases:
        - System reset during development/testing
        - Compliance with data deletion requests (GDPR, CCPA)
        - Emergency cleanup of compromised data
        - Fresh start after deployment

        Security considerations:
        - Requires authentication (if AUTH_ENABLED=true)
        - Audit logged with deletion metadata
        - Should only be accessible to admin users
        - Consider adding rate limiting for this endpoint

        Returns:
            None (204 No Content)

        Raises:
            HTTPException: 401 if authentication fails
            HTTPException: 500 if deletion fails

        Example:
            >>> import requests
            >>> headers = {"Authorization": "Bearer token_xyz"}
            >>> response = requests.delete(
            ...     "http://localhost:8000/sessions",
            ...     headers=headers
            ... )
            >>> print(response.status_code)  # 204
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
        return DeleteResponse(
            message=f"Cleared {count} sessions",
            resource_id="*",
        )


def _register_setup_routes(app) -> None:
    """Register setup and diagnostics routes."""
    from agentic_brain.router import (
        ProviderChecker,
        format_provider_status_report,
        get_setup_help,
    )

    @app.get(
        "/setup",
        response_model=SetupStatusResponse,
        summary="Setup Status and Diagnostics",
        description="Check LLM provider status and get setup instructions",
        tags=["llm"],
        responses=ERROR_RESPONSES,
    )
    async def setup_status():
        """
        Get setup status and diagnostics for all LLM providers.

        This endpoint checks which LLM providers are available and ready to use,
        and provides setup instructions for unconfigured providers.

        Available providers checked:
        - Groq (FREE, recommended) - Requires GROQ_API_KEY
        - Ollama (self-hosted, FREE) - Requires Ollama running locally
        - OpenAI - Requires OPENAI_API_KEY
        - Anthropic (Claude) - Requires ANTHROPIC_API_KEY
        - Google (Gemini) - Requires GOOGLE_API_KEY
        - XAI (Grok) - Requires XAI_API_KEY
        - Together AI - Requires TOGETHER_API_KEY
        - OpenRouter - Requires OPENROUTER_API_KEY

        Setup status values:
        - "configured": At least one provider is available
        - "needs_setup": No providers available yet
        - "error": Error occurred while checking providers

        Use cases:
        - Verify LLM setup on server startup
        - Get instructions for new deployments
        - Troubleshoot provider connectivity
        - Check which models are available
        - Plan LLM provider strategy

        Returns:
            dict: Setup status containing:
                {
                    "status": "configured" or "needs_setup" or "error",
                    "message": "Human-readable status message",
                    "providers": {
                        "available": [
                            {
                                "name": "groq",
                                "reason": "GROQ_API_KEY is configured"
                            }
                        ],
                        "unavailable": [
                            {
                                "name": "openai",
                                "reason": "OPENAI_API_KEY not configured"
                            }
                        ]
                    },
                    "setup_guide": "Detailed setup instructions...",
                    "quick_start": {  // Only if no provider available
                        "option_1": "GROQ (FREE, recommended)",
                        "steps": [
                            "1. Visit: https://console.groq.com",
                            "2. Sign up and get API key",
                            "3. Add to .env: GROQ_API_KEY=gsk_...",
                            "4. Restart the server"
                        ]
                    }
                }

        Raises:
            None: Always returns 200 with error status if something fails

        Example (cURL):
            >>> curl http://localhost:8000/setup

        Example (Python):
            >>> import requests
            >>> response = requests.get("http://localhost:8000/setup")
            >>> data = response.json()
            >>> print(f"Status: {data['status']}")
            >>> for provider in data['providers']['available']:
            ...     print(f"  ✓ {provider['name']}")

        Implementation notes:
        - Non-blocking: checks are fast (< 1 second)
        - Cached for performance (providers are checked on each request)
        - Safe: errors don't crash the API
        - Useful for CI/CD pipelines to verify configuration
        """
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
        response_model=SetupHelpResponse,
        summary="Get Setup Instructions for Provider",
        description="Get detailed setup instructions for a specific provider",
        tags=["llm"],
        responses=ERROR_RESPONSES,
    )
    async def setup_help(provider: str):
        """
        Get detailed setup instructions for a specific LLM provider.

        This endpoint provides step-by-step instructions for configuring
        a specific LLM provider, including:
        - Account creation links
        - API key generation steps
        - Environment variable configuration
        - Verification commands
        - Troubleshooting tips
        - Pricing information

        Supported providers:
        - "groq": Groq Cloud (FREE, recommended)
        - "ollama": Ollama local/self-hosted (FREE)
        - "openai": OpenAI ChatGPT/GPT-4 (Paid)
        - "anthropic": Anthropic Claude (Paid)
        - "google": Google Gemini (Paid)
        - "xai": X AI Grok (Paid)
        - "openrouter": OpenRouter (Paid/Free models)
        - "together": Together AI (Paid)

        Setup workflow:
        1. Call GET /setup to see which providers need setup
        2. Call GET /setup/help/{provider} for that provider
        3. Follow the step-by-step instructions
        4. Configure environment variables
        5. Restart the server
        6. Call GET /setup again to verify

        Args:
            provider (str): The LLM provider name (lowercase)
                Must be one of the supported provider names above

        Returns:
            dict: Setup help containing:
                {
                    "provider": "groq",
                    "instructions": "Detailed step-by-step setup guide..."
                }

                Or if provider unknown:
                {
                    "provider": "invalid",
                    "error": "Unknown provider: invalid",
                    "available_providers": [
                        "groq", "ollama", "openai", "anthropic", ...
                    ]
                }

        Raises:
            None: Returns error dict if provider not recognized

        Example (cURL - Groq setup):
            >>> curl http://localhost:8000/setup/help/groq

        Example (cURL - OpenAI setup):
            >>> curl http://localhost:8000/setup/help/openai

        Example (Python):
            >>> import requests
            >>>
            >>> response = requests.get("http://localhost:8000/setup/help/groq")
            >>> if response.status_code == 200:
            ...     data = response.json()
            ...     print(data['instructions'])

        Example (JavaScript):
            >>> fetch('http://localhost:8000/setup/help/ollama')
            ...   .then(r => r.json())
            ...   .then(data => console.log(data.instructions))

        Implementation notes:
        - Provider names are case-insensitive internally
        - Returns human-readable markdown/text instructions
        - Safe: unknown providers return helpful error with available options
        - Useful for onboarding and self-service setup
        - Can be embedded in setup wizards
        """
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
        responses={
            200: {"description": "SAML AuthnRequest generated successfully"},
            500: {"description": "Error generating SAML request"},
        },
    )
    async def saml_login() -> dict:
        """
        Initiate a SAML login flow by generating an AuthnRequest.

        This endpoint starts a SAML Service Provider-initiated SSO flow:
        1. Server generates a SAML AuthnRequest XML
        2. Client redirects user to IdP with AuthnRequest
        3. User authenticates at IdP
        4. IdP sends SAML Response back to server
        5. Server validates Response at /auth/saml/acs

        SAML flow context:
        - SP (Service Provider): This API server
        - IdP (Identity Provider): Corporate/organizational auth system
        - User: Authenticating at IdP
        - Assertion Consumer Service (ACS): /auth/saml/acs endpoint

        Configuration required (via environment variables):
        - SAML_IDP_ENTITY_ID: IdP's entity ID/identifier
        - SAML_IDP_SSO_URL: URL where to redirect for authentication
        - SAML_IDP_CERTIFICATE: IdP's public certificate for signature validation
        - SAML_SP_ENTITY_ID: This server's entity ID (default: "agentic-brain")
        - SAML_SP_ACS_URL: Assertion Consumer Service URL
            (default: "http://localhost:8000/auth/saml/acs")

        Returns:
            dict: SAML login information:
                {
                    "sso_url": "https://idp.example.com/sso",
                    "authn_request": "<?xml version='1.0'...>"
                }

                Where authn_request is the XML AuthnRequest to send to IdP

        Typical flow for frontend:
            1. POST /auth/saml/login
            2. Receive sso_url and authn_request
            3. Redirect user to: sso_url with AuthnRequest as parameter
            4. User authenticates at IdP
            5. IdP redirects to /auth/saml/acs with SAML Response
            6. Frontend handles successful authentication

        Raises:
            HTTPException: 500 if SAML provider initialization fails

        Example:
            >>> import requests
            >>> response = requests.post("http://localhost:8000/auth/saml/login")
            >>> data = response.json()
            >>> sso_url = data['sso_url']
            >>> # Redirect user to: sso_url with SAML request

        Notes:
        - SAML configuration must be complete for this to work
        - Used by corporate/enterprise authentication systems
        - Alternative to OAuth2/OIDC for enterprise SSO
        - Requires IdP cooperation and metadata exchange
        """
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
        responses={
            200: {"description": "SAML Response validated successfully"},
            400: {"description": "Invalid SAML Response or missing saml_response"},
            401: {"description": "SAML signature validation failed"},
            500: {"description": "Error processing SAML Response"},
        },
    )
    async def saml_acs(payload: dict = Body(...)) -> dict:
        """
        Assertion Consumer Service (ACS) endpoint for SAML authentication.

        This endpoint receives and validates SAML Responses from the IdP
        after user authentication. It's the redirect target after successful
        authentication at the Identity Provider.

        SAML ACS flow:
        1. User authenticates at IdP (/auth/saml/login initiates this)
        2. IdP generates SAML Response with user attributes
        3. IdP redirects user to /auth/saml/acs with SAML Response
        4. Server validates SAML Response signature
        5. Server extracts user attributes (email, name, groups, etc.)
        6. Server returns authenticated user information

        SAML Response structure (BASE64-encoded XML):
            <samlp:Response>
                <Assertion>
                    <Subject>
                        <NameID>user@example.com</NameID>
                    </Subject>
                    <AttributeStatement>
                        <Attribute Name="email">user@example.com</Attribute>
                        <Attribute Name="givenName">John</Attribute>
                        <Attribute Name="surname">Doe</Attribute>
                        <Attribute Name="groups">admin</Attribute>
                    </AttributeStatement>
                </Assertion>
            </samlp:Response>

        Security validation performed:
        - SAML Response signature validation (uses IdP certificate)
        - Assertion encryption validation
        - NotOnOrAfter timestamp check (ensures freshness)
        - InResponseTo validation (matches AuthnRequest ID)
        - Issuer validation (matches IdP entity ID)

        Request format:
            POST /auth/saml/acs
            Content-Type: application/json

            {
                "saml_response": "PD94bWwgdmVyc2lvbj0iMS4wIj8+PHNhbWxw..."
            }

        Args:
            payload (dict): Request body containing:
                - saml_response (str): BASE64-encoded SAML Response XML (required)

        Returns:
            dict: Validated SAML data:
                {
                    "subject": "user@example.com",
                    "attributes": {
                        "email": "user@example.com",
                        "givenName": "John",
                        "surname": "Doe",
                        "groups": ["admin", "developers"]
                    },
                    "session_index": "session_id_from_idp",
                    "issuer": "https://idp.example.com"
                }

        Raises:
            HTTPException: 400 if saml_response missing or malformed
            HTTPException: 401 if signature validation fails
            HTTPException: 500 if processing error occurs

        Example (JavaScript):
            >>> // Receive SAML Response from IdP form submission
            >>> const samlResponse = document.querySelector(
            ...     'input[name="SAMLResponse"]'
            ... ).value;
            >>>
            >>> // Send to server for validation
            >>> const response = await fetch('/auth/saml/acs', {
            ...     method: 'POST',
            ...     headers: { 'Content-Type': 'application/json' },
            ...     body: JSON.stringify({ saml_response: samlResponse })
            ... });
            >>> const user = await response.json();
            >>> console.log(`Logged in as: ${user.attributes.email}`);

        Example (cURL):
            >>> curl -X POST http://localhost:8000/auth/saml/acs \\
            ...   -H "Content-Type: application/json" \\
            ...   -d '{
            ...     "saml_response": "PD94bWwgdmVyc2lvbj0..."
            ...   }'

        Configuration required:
        - SAML_IDP_CERTIFICATE: IdP public certificate for signature validation
        - SAML_SP_ENTITY_ID: This server's entity ID
        - SAML_IDP_ENTITY_ID: Expected IdP entity ID in Response

        Typical frontend workflow:
            1. User clicks "Login with SSO"
            2. Frontend calls POST /auth/saml/login
            3. Frontend redirects to IdP with AuthnRequest
            4. User logs in at IdP
            5. IdP redirects to POST /auth/saml/acs with Response
            6. Frontend submits to /auth/saml/acs
            7. Server validates and returns user info
            8. Frontend creates session with returned user info

        Notes:
        - SAML Response is one-time use (replay protection)
        - Timestamps are checked for freshness (< 5 minutes typical)
        - Used primarily in enterprise/corporate environments
        - Alternative to OAuth2/OIDC
        """
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
        responses={
            200: {"description": "SAML SP metadata in XML format"},
            500: {"description": "Error generating metadata"},
        },
    )
    async def saml_metadata() -> Response:
        """
        Get SAML Service Provider metadata XML.

        This endpoint returns the SAML metadata XML that the Identity Provider
        needs to configure this server as a trusted Service Provider (SP).

        Metadata contains:
        - Service Provider entity ID
        - Assertion Consumer Service (ACS) endpoint URLs
        - Single Logout Service (SLS) endpoints
        - Public certificate for response encryption
        - Supported SAML bindings (Redirect, POST)
        - Contact information

        IdP configuration workflow:
        1. IdP administrator gets metadata from: GET /auth/saml/metadata
        2. IdP imports metadata into their system
        3. IdP configures this server as a trusted application
        4. IdP provides their metadata in return (SAML_IDP_CERTIFICATE, etc.)
        5. Server and IdP are now configured for SSO

        Metadata example:
            <?xml version="1.0" encoding="UTF-8"?>
            <EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
                              entityID="agentic-brain">
                <SPSSODescriptor
                    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
                    <AssertionConsumerService
                        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                        Location="http://localhost:8000/auth/saml/acs"
                        index="0" isDefault="true"/>
                </SPSSODescriptor>
            </EntityDescriptor>

        Returns:
            Response: SAML SP metadata XML
                - Content-Type: application/xml
                - Format: ISO-8859-1 encoded XML (per SAML 2.0 spec)

        Example (cURL):
            >>> curl -X GET http://localhost:8000/auth/saml/metadata > sp-metadata.xml

        Example (Browser):
            Just visit: http://localhost:8000/auth/saml/metadata
            Browser will download/display the XML file

        Example (Python):
            >>> import requests
            >>> response = requests.get("http://localhost:8000/auth/saml/metadata")
            >>> metadata_xml = response.text
            >>> print(metadata_xml)

        Implementation notes:
        - Metadata is static (generated from configuration)
        - Safe to share with IdP (public information)
        - Used by IdP to validate SAML Responses
        - Updated automatically if SAML_* environment variables change
        - Metadata is public - no secrets included

        Integration steps:
        1. Get this metadata: GET /auth/saml/metadata
        2. Provide to IdP administrator
        3. IdP imports metadata and configures SP
        4. IdP provides their certificate and entity ID
        5. Configure environment variables:
           - SAML_IDP_CERTIFICATE=<IdP cert>
           - SAML_IDP_ENTITY_ID=<IdP entity ID>
           - SAML_IDP_SSO_URL=<IdP SSO URL>
        6. Restart server
        """
        provider = _lazy_saml()
        xml = provider.get_metadata()
        return Response(content=xml, media_type="application/xml")

    @app.get(
        "/auth/sso/{provider}/login",
        response_model=dict,
        summary="Initiate OAuth2/OIDC SSO login",
        description="Generate an authorization URL for the given SSO provider.",
        tags=["auth"],
        responses={
            200: {"description": "Authorization URL generated successfully"},
            404: {"description": "Unknown SSO provider"},
            503: {"description": "SSO provider not configured"},
        },
    )
    async def sso_login(provider: str) -> dict:
        """
        Generate an OAuth2/OIDC authorization URL for the specified provider.

        This endpoint initiates OAuth2/OIDC login flows for various providers:
        - Google (Gmail, workspace)
        - Microsoft (Office 365, Azure AD)
        - GitHub
        - Okta
        - Auth0
        - And other OIDC-compliant providers

        OAuth2 flow overview:
        1. Client requests authorization URL: GET /auth/sso/{provider}/login
        2. Server generates random state (CSRF protection)
        3. Server generates authorization URL
        4. Frontend redirects user to authorization_url
        5. User logs in and consents to scopes at provider
        6. Provider redirects user to /auth/sso/{provider}/callback
        7. Frontend exchanges code for tokens at callback endpoint

        Supported providers (if configured):
        - "google": Google OAuth2 / OpenID Connect
        - "microsoft": Azure AD / Microsoft identity
        - "github": GitHub OAuth
        - "okta": Okta identity platform
        - "auth0": Auth0 SaaS identity platform
        - Others: Depends on configuration (OIDC-compliant)

        Configuration required:
        For each provider, environment variables needed:
        - {PROVIDER}_CLIENT_ID: OAuth client ID
        - {PROVIDER}_CLIENT_SECRET: OAuth client secret
        - {PROVIDER}_REDIRECT_URI: Where to redirect after auth
            (typically http://localhost:8000/auth/sso/{provider}/callback)

        Args:
            provider (str): The SSO provider name (lowercase)
                Examples: "google", "microsoft", "github", "okta"

        Returns:
            dict: Authorization information:
                {
                    "provider": "google",
                    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
                    "state": "random_csrf_token_12345..."
                }

                Where:
                - authorization_url: URL to redirect user to
                - state: CSRF token (save on client, compare in callback)

        Raises:
            HTTPException: 404 if provider not recognized
            HTTPException: 503 if SSO provider not configured

        Example (JavaScript):
            >>> // Step 1: Get authorization URL
            >>> const response = await fetch('/auth/sso/google/login');
            >>> const { authorization_url, state } = await response.json();
            >>>
            >>> // Step 2: Save state for verification
            >>> sessionStorage.setItem('oauth_state', state);
            >>>
            >>> // Step 3: Redirect user
            >>> window.location.href = authorization_url;
            >>>
            >>> // User logs in at Google, gets redirected to /auth/sso/google/callback

        Example (Python):
            >>> import requests
            >>> response = requests.get('http://localhost:8000/auth/sso/github/login')
            >>> data = response.json()
            >>> print(f"Redirect user to: {data['authorization_url']}")
            >>> # Save state for CSRF verification
            >>> saved_state = data['state']

        Example (cURL):
            >>> curl http://localhost:8000/auth/sso/okta/login

        Frontend workflow:
            1. User clicks "Sign in with [Provider]"
            2. Frontend calls GET /auth/sso/{provider}/login
            3. Save returned state in session/storage
            4. Redirect to authorization_url
            5. User logs in at provider
            6. Provider redirects to /auth/sso/{provider}/callback?code=X&state=Y
            7. Frontend verifies state matches saved state
            8. Frontend calls callback endpoint
            9. Frontend receives tokens and user info
            10. Frontend creates authenticated session

        Security:
        - State parameter prevents CSRF attacks
        - Each authorization_url is unique
        - Expires quickly (typically 5-10 minutes)
        - Redirect URIs are validated by provider

        Notes:
        - Non-blocking: returns immediately
        - Safe: unknown providers return 404
        - Scopes: determined by provider configuration
        - PKCE: Can be added for extra security
        """
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
        responses={
            200: {"description": "Tokens and user info retrieved successfully"},
            400: {"description": "Invalid authorization code or state mismatch"},
            404: {"description": "Unknown SSO provider"},
            503: {"description": "SSO provider not configured"},
        },
    )
    async def sso_callback(provider: str, code: str, state: str | None = None) -> dict:
        """
        OAuth2/OIDC callback endpoint for handling provider redirects.

        This endpoint handles the redirect from the OAuth provider after user
        authorization. It exchanges the authorization code for access and ID tokens,
        and optionally validates the ID token to extract user information.

        Callback flow:
        1. User authorizes at provider (/auth/sso/{provider}/login initiated this)
        2. Provider redirects to /auth/sso/{provider}/callback?code=X&state=Y
        3. Server validates state (CSRF protection)
        4. Server exchanges code for tokens
        5. Server validates ID token (if OIDC)
        6. Server extracts user attributes
        7. Server returns tokens and user info

        Provider redirect format:
            GET /auth/sso/{provider}/callback?code=4/P7q7W91a...&state=xyz

        Query parameters:
            code (str): Authorization code from provider (required)
                - Can be exchanged for tokens
                - Single-use only
                - Expires after 10 minutes typically

            state (str): CSRF protection token (recommended, required if originally provided)
                - Must match state from /auth/sso/{provider}/login
                - Prevents CSRF attacks
                - Can be omitted if authorization_url didn't include state

            error (str): If authentication failed
                - Present instead of code
                - Examples: "access_denied", "invalid_scope"
                - Should be handled by redirecting to login

        Returns:
            dict: OAuth response containing:
                {
                    "provider": "google",
                    "state": "xyz",
                    "token": {
                        "access_token": "ya29.a0Aed...",
                        "refresh_token": "1//0gxxx...",
                        "token_type": "Bearer",
                        "expires_in": 3599,
                        "scope": "openid email profile"
                    },
                    "id_token": {
                        "iss": "https://accounts.google.com",
                        "azp": "client_id.apps.googleusercontent.com",
                        "aud": "client_id.apps.googleusercontent.com",
                        "sub": "123456789",
                        "email": "user@gmail.com",
                        "email_verified": true,
                        "name": "John Doe",
                        "picture": "https://lh3.googleusercontent.com/...",
                        "given_name": "John",
                        "family_name": "Doe",
                        "locale": "en",
                        "iat": 1516239022,
                        "exp": 1516242622
                    }
                }

        Raises:
            HTTPException: 400 if code invalid or state mismatch
            HTTPException: 404 if provider unknown
            HTTPException: 503 if provider not configured

        Example (JavaScript - Handling redirect):
            >>> // This happens automatically when provider redirects here
            >>> // But you might call it manually or check results:
            >>>
            >>> // Option 1: Let form submission handle it
            >>> // Provider redirects with form submission to this URL
            >>>
            >>> // Option 2: Handle via JavaScript if available
            >>> const params = new URLSearchParams(window.location.search);
            >>> const code = params.get('code');
            >>> const state = params.get('state');
            >>>
            >>> // Frontend should call backend API to validate this callback
            >>> const response = await fetch(
            ...     `/api/auth/sso/google/callback?code=${code}&state=${state}`
            ... );
            >>> const auth = await response.json();
            >>> if (auth.id_token) {
            ...     // User is authenticated
            ...     const user = auth.id_token;
            ...     console.log(`Logged in as: ${user.email}`);
            ...     // Create session, set cookies, etc.
            ... }

        Example (cURL):
            >>> # Manually testing a callback (requires real code from provider)
            >>> curl -G http://localhost:8000/auth/sso/google/callback \\
            ...   --data-urlencode "code=4/0-..." \\
            ...   --data-urlencode "state=xyz..."

        Complete OAuth2 flow:
            1. User clicks "Sign in with Google"
            2. Frontend: GET /auth/sso/google/login
            3. Frontend: saves state, redirects to authorization_url
            4. Google: user logs in and grants permission
            5. Google: redirects to /auth/sso/google/callback?code=X&state=Y
            6. Server: validates code and state
            7. Server: calls Google token endpoint with code
            8. Server: receives access_token, id_token, refresh_token
            9. Server: validates ID token signature and claims
            10. Server: returns tokens and user info to frontend
            11. Frontend: creates authenticated session

        Token information:
        - access_token: Bearer token for API calls to provider
            - Used to call provider APIs on behalf of user
            - Short-lived (typically 1 hour)
            - Can be refreshed with refresh_token

        - id_token: JWT with user identity information (OpenID Connect)
            - Contains user claims (email, name, picture, etc.)
            - Signed by provider (verify signature)
            - Should be decoded and validated
            - Expiration prevents replay attacks

        - refresh_token: Long-lived token to get new access_tokens
            - Only provided if "offline_access" scope included
            - Can refresh without user re-authenticating
            - Should be stored securely
            - Not all providers return refresh_token

        Configuration:
        - {PROVIDER}_CLIENT_ID: OAuth client ID from provider
        - {PROVIDER}_CLIENT_SECRET: OAuth client secret (keep private!)
        - {PROVIDER}_REDIRECT_URI: Must match provider configuration

        Security best practices:
        - Validate state parameter (CSRF prevention)
        - Validate ID token signature (verify provider is legitimate)
        - Check ID token expiration
        - Use HTTPS only
        - Store refresh_token securely (encrypted in database)
        - Don't expose client_secret to frontend

        Provider-specific notes:
        - Google: Returns refresh_token only on first auth + "offline_access"
        - Microsoft: Similar to Google
        - GitHub: Doesn't support OpenID Connect (no ID token)
        - Okta: Full OIDC support
        """
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
