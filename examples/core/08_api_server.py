#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
08 - FastAPI Server Deployment
================================

Deploy your AI agent as a production REST API!
Full FastAPI server with all the production essentials.

Features:
- REST API endpoints for chat
- Streaming support (SSE)
- Health checks
- Request validation
- CORS handling
- API documentation (Swagger)

Run:
    python examples/08_api_server.py
    
Then visit:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/health

Test:
    curl -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello!"}'

Requirements:
    pip install fastapi uvicorn
    - Ollama or OpenAI configured
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agentic_brain import Agent
from agentic_brain.streaming import StreamingResponse as AgentStreaming

# ============================================================================
# Configuration
# ============================================================================

# Server settings (can be overridden with env vars)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")


# ============================================================================
# Global Agent Instance
# ============================================================================

# Agent is created on startup and reused
agent: Optional[Agent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.

    Initialize resources on startup, cleanup on shutdown.
    """
    global agent

    # Startup: Initialize agent
    print("🚀 Starting Agentic Brain API Server...")
    agent = Agent(
        name="api-agent",
        system_prompt="You are a helpful AI assistant accessible via API.",
    )
    print("✅ Agent initialized")

    yield  # Application runs here

    # Shutdown: Cleanup
    print("👋 Shutting down...")
    agent = None


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Agentic Brain API",
    description="AI Agent REST API with streaming support",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware (adjust origins for production!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(
        None, description="Session ID for conversation continuity"
    )
    stream: bool = Field(False, description="Enable streaming response")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is machine learning?",
                "session_id": "user-123",
                "stream": False,
            }
        }


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    response: str
    session_id: Optional[str] = None
    tokens_used: Optional[int] = None
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent_ready: bool
    timestamp: str
    version: str


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Agentic Brain API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Use this for load balancer health checks and monitoring.
    """
    return HealthResponse(
        status="healthy",
        agent_ready=agent is not None,
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message and get a response.

    For streaming responses, set `stream: true` in the request.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Handle streaming requests
    if request.stream:
        return StreamingResponse(
            stream_chat(request.message), media_type="text/event-stream"
        )

    try:
        # Get response from agent
        response = await agent.chat_async(request.message)

        return ChatResponse(
            response=response,
            session_id=request.session_id,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/stream", tags=["Chat"])
async def chat_stream(message: str):
    """
    Stream a chat response using Server-Sent Events (SSE).

    Use this endpoint for real-time streaming in browsers.

    Example:
        const eventSource = new EventSource('/chat/stream?message=Hello');
        eventSource.onmessage = (e) => console.log(e.data);
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return StreamingResponse(stream_chat(message), media_type="text/event-stream")


async def stream_chat(message: str) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for chat response.

    Yields Server-Sent Events format:
        data: {"token": "Hello", "done": false}

        data: {"token": " World", "done": false}

        data: {"token": "", "done": true}
    """
    import json

    streamer = AgentStreaming(provider="ollama", model="llama3.1:8b", temperature=0.7)

    try:
        async for token in streamer.stream(message):
            data = {
                "token": token.token,
                "done": token.is_end,
            }
            yield f"data: {json.dumps(data)}\n\n"

        # Final event
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"


@app.post("/reset", tags=["Session"])
async def reset_session(session_id: Optional[str] = None):
    """
    Reset conversation history.

    Clears the agent's memory for a fresh start.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent.clear_history()

    return {
        "message": "Session reset",
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Run the API server."""
    import uvicorn

    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + "   Agentic Brain API Server".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    print(f"\n🌐 Starting server at http://{HOST}:{PORT}")
    print(f"📚 API docs at http://localhost:{PORT}/docs")
    print(f"❤️ Health check at http://localhost:{PORT}/health")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
