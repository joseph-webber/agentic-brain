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
