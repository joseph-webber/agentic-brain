# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Streaming Response Support
==========================

Unified streaming interface for multiple LLM providers:
- Ollama (local)
- OpenAI (cloud)
- Anthropic (cloud)

Makes responses feel instant with token-by-token streaming.

Quick Start:
    streamer = StreamingResponse(provider="ollama", model="llama3.1:8b")
    async for token in streamer.stream("What is AI?"):
        print(token, end="", flush=True)

With SSE (Server-Sent Events):
    from fastapi.responses import StreamingResponse
    
    @app.get("/chat/stream")
    async def stream_chat(message: str):
        streamer = StreamingResponse(provider="ollama", model="llama3.1:8b")
        return StreamingResponse(
            streamer.stream_sse(message),
            media_type="text/event-stream"
        )

WebSocket:
    from fastapi import WebSocket
    
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        streamer = StreamingResponse(provider="ollama", model="llama3.1:8b")
        async for token in streamer.stream("What is AI?"):
            await websocket.send_text(token)
"""

from .stream import StreamingResponse, StreamProvider, StreamToken

__all__ = [
    "StreamingResponse",
    "StreamProvider",
    "StreamToken",
]
