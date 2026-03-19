# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""FastAPI server for agentic-brain chatbot API."""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse as FastAPIStreamingResponse
from pydantic import ValidationError
import uvicorn
import json

from .models import ChatRequest, ChatResponse, SessionInfo, ErrorResponse
from ..streaming import StreamingResponse, StreamToken
from ..dashboard import create_dashboard_router


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Session storage (in-memory for now, can be replaced with database)
sessions: Dict[str, Dict] = {}
session_messages: Dict[str, List[Dict]] = {}


def create_app(
    title: str = "Agentic Brain Chatbot API",
    version: str = "1.0.0",
    description: str = "FastAPI server for agentic-brain chatbot with real-time chat support",
    cors_origins: Optional[List[str]] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.
    
    Args:
        title: API title
        version: API version
        description: API description
        cors_origins: List of allowed CORS origins
        
    Returns:
        Configured FastAPI application
    """
    
    # Default CORS origins
    if cors_origins is None:
        cors_origins = [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ]
    
    app = FastAPI(
        title=title,
        version=version,
        description=description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ============================================================================
    # Exception Handlers
    # ============================================================================
    
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request, exc):
        """Handle Pydantic validation errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation error",
                "detail": str(exc),
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            },
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "detail": None,
                "status_code": exc.status_code,
            },
        )
    
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
        """Health check endpoint.
        
        Returns:
            dict: Health status information
        """
        return {
            "status": "healthy",
            "version": version,
            "timestamp": datetime.utcnow().isoformat(),
            "sessions_active": len(sessions),
        }
    
    # ============================================================================
    # Chat Endpoints
    # ============================================================================
    
    def _generate_session_id() -> str:
        """Generate a unique session ID."""
        return f"sess_{uuid.uuid4().hex[:12]}"
    
    def _generate_message_id() -> str:
        """Generate a unique message ID."""
        return f"msg_{uuid.uuid4().hex[:12]}"
    
    def _ensure_session_exists(session_id: str, user_id: Optional[str] = None):
        """Ensure a session exists, create if it doesn't."""
        if session_id not in sessions:
            now = datetime.utcnow()
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
            sessions[session_id]["last_accessed"] = datetime.utcnow()
    
    @app.post(
        "/chat",
        response_model=ChatResponse,
        summary="Send Chat Message",
        description="Send a message to the chatbot and receive a response",
        tags=["Chat"],
        status_code=status.HTTP_200_OK,
    )
    async def chat(request: ChatRequest) -> ChatResponse:
        """Send a message to the chatbot.
        
        Args:
            request: Chat request with message and optional session/user IDs
            
        Returns:
            ChatResponse: Chatbot response with session info
            
        Raises:
            HTTPException: If processing fails
        """
        try:
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
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            # Generate response (placeholder - integrate with actual chat logic)
            response_text = f"Echo: {request.message}"
            response_id = _generate_message_id()
            
            # Store response in session
            session_messages[session_id].append({
                "id": response_id,
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.utcnow().isoformat(),
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
    # Streaming Chat Endpoints
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
    ):
        """Stream a chat response as Server-Sent Events.
        
        Ideal for web frontends - tokens arrive immediately for instant UX.
        
        Example:
            const eventSource = new EventSource('/chat/stream?message=Hello');
            eventSource.onmessage = (event) => {
                const token = JSON.parse(event.data);
                console.log(token.token);  // Print token immediately
            };
        
        Args:
            message: User message
            session_id: Optional session for conversation history
            user_id: Optional user ID
            provider: LLM provider (ollama, openai, anthropic)
            model: Model name
            temperature: Sampling temperature
            
        Returns:
            StreamingResponse: SSE stream of tokens
        """
        try:
            session_id = session_id or _generate_session_id()
            _ensure_session_exists(session_id, user_id)
            
            # Store user message
            session_messages[session_id].append({
                "id": _generate_message_id(),
                "role": "user",
                "content": message,
                "timestamp": datetime.utcnow().isoformat(),
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
    
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        """WebSocket endpoint for streaming chat.
        
        Perfect for real-time applications that need bidirectional communication.
        
        Message format (client -> server):
            {
                "message": "What is AI?",
                "session_id": "sess_abc123",  # optional
                "provider": "ollama",  # optional
                "model": "llama3.1:8b",  # optional
            }
        
        Response format (server -> client):
            {
                "token": "hello",
                "is_start": false,
                "is_end": false,
                "finish_reason": null,
                "metadata": {...}
            }
        
        Example (JavaScript):
            const ws = new WebSocket('ws://localhost:8000/ws/chat');
            ws.onopen = () => {
                ws.send(JSON.stringify({
                    message: "What is AI?",
                    provider: "ollama"
                }));
            };
            ws.onmessage = (event) => {
                const token = JSON.parse(event.data);
                console.log(token.token);  // Print token immediately
            };
        """
        await websocket.accept()
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_text(
                        json.dumps({
                            "error": "Invalid JSON",
                            "token": "",
                            "is_end": True,
                            "finish_reason": "error"
                        })
                    )
                    continue
                
                message = payload.get("message")
                if not message:
                    await websocket.send_text(
                        json.dumps({
                            "error": "Missing message field",
                            "token": "",
                            "is_end": True,
                            "finish_reason": "error"
                        })
                    )
                    continue
                
                session_id = payload.get("session_id") or _generate_session_id()
                user_id = payload.get("user_id")
                provider = payload.get("provider", "ollama")
                model = payload.get("model", "llama3.1:8b")
                temperature = float(payload.get("temperature", 0.7))
                
                _ensure_session_exists(session_id, user_id)
                
                # Store user message
                session_messages[session_id].append({
                    "id": _generate_message_id(),
                    "role": "user",
                    "content": message,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
                # Get conversation history
                history = [
                    {
                        "role": msg["role"],
                        "content": msg["content"]
                    }
                    for msg in session_messages[session_id][-10:]
                    if msg["role"] in ["user", "assistant"]
                ]
                
                try:
                    # Stream response tokens
                    streamer = StreamingResponse(
                        provider=provider,
                        model=model,
                        temperature=temperature,
                    )
                    
                    response_text = ""
                    async for token in streamer.stream_websocket(message, history[:-1]):
                        await websocket.send_text(token)
                        
                        # Extract token text for storage
                        try:
                            token_data = json.loads(token)
                            response_text += token_data.get("token", "")
                        except:
                            pass
                    
                    # Store complete response
                    if response_text:
                        session_messages[session_id].append({
                            "id": _generate_message_id(),
                            "role": "assistant",
                            "content": response_text,
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                    
                    sessions[session_id]["message_count"] += 1
                    
                except Exception as e:
                    logger.error(f"Error in WebSocket streaming: {str(e)}")
                    await websocket.send_text(
                        json.dumps({
                            "error": str(e),
                            "token": "",
                            "is_end": True,
                            "finish_reason": "error"
                        })
                    )
        
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            try:
                await websocket.close(code=1011, reason=str(e))
            except:
                pass
    
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
        """Get session information.
        
        Args:
            session_id: The session ID to retrieve
            
        Returns:
            SessionInfo: Session information and statistics
            
        Raises:
            HTTPException: If session not found
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
        """Delete a session and clear all messages.
        
        Args:
            session_id: The session ID to delete
            
        Raises:
            HTTPException: If session not found
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
    
    # ============================================================================
    # WebSocket Endpoint
    # ============================================================================
    
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket):
        """WebSocket endpoint for real-time chat.
        
        Connection protocol:
        1. Client connects to /ws/chat
        2. Server sends: {"type": "connection", "session_id": "...", "message": "Connected"}
        3. Client sends: {"message": "...", "session_id": "..."} (optional)
        4. Server responds: {"type": "message", "content": "...", "id": "..."}
        5. Client can send new messages anytime
        6. Connection closes when client disconnects
        """
        try:
            await websocket.accept()
            
            # Generate session ID for this WebSocket connection
            session_id = _generate_session_id()
            _ensure_session_exists(session_id)
            
            logger.info(f"WebSocket connected: {session_id}")
            
            # Send connection confirmation
            await websocket.send_json({
                "type": "connection",
                "session_id": session_id,
                "message": "Connected to chatbot",
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            # Message loop
            while True:
                try:
                    # Receive message
                    data = await websocket.receive_json()
                    message = data.get("message", "").strip()
                    
                    if not message:
                        await websocket.send_json({
                            "type": "error",
                            "error": "Empty message",
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                        continue
                    
                    # Process message
                    message_id = _generate_message_id()
                    response_id = _generate_message_id()
                    
                    # Store in session
                    session_messages[session_id].append({
                        "id": message_id,
                        "role": "user",
                        "content": message,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    
                    # Generate response
                    response_text = f"Echo: {message}"
                    
                    session_messages[session_id].append({
                        "id": response_id,
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    
                    sessions[session_id]["message_count"] += 1
                    
                    # Send response
                    await websocket.send_json({
                        "type": "message",
                        "id": response_id,
                        "content": response_text,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    
                    logger.info(f"WebSocket message processed: {session_id} -> {response_id}")
                    
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Invalid JSON",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                except Exception as e:
                    logger.error(f"WebSocket error: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Error processing message: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
        
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
        
        finally:
            logger.info(f"WebSocket closed: {session_id}")
    
    # ============================================================================
    # Mount Dashboard
    # ============================================================================
    
    dashboard_router = create_dashboard_router(
        sessions_dict=sessions,
        session_messages_dict=session_messages,
    )
    app.include_router(dashboard_router)
    
    return app


# Create the default app instance
app = create_app()


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
):
    """Run the FastAPI server.
    
    Args:
        host: Server host
        port: Server port
        reload: Enable auto-reload on file changes
        log_level: Logging level
    """
    uvicorn.run(
        "agentic_brain.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    run_server(reload=True)
