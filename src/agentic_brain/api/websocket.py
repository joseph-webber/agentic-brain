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
WebSocket handler for the Agentic Brain Chat API.

Provides real-time bidirectional streaming chat over WebSocket connections.
"""

import json
import logging
from datetime import UTC, datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from ..streaming import StreamingResponse
from .routes import (
    _ensure_session_exists,
    _generate_message_id,
    _generate_session_id,
    session_messages,
    sessions,
)
from .websocket_auth import WebSocketAuthenticator

logger = logging.getLogger(__name__)


def register_websocket_routes(app: FastAPI):
    """Register WebSocket routes with the FastAPI app."""

    authenticator = WebSocketAuthenticator()

    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        """
        WebSocket endpoint for bidirectional real-time streaming chat.

        Provides full-duplex communication for applications needing:
        - Real-time message streaming
        - Bidirectional communication (client and server can send anytime)
        - Lower latency than HTTP streaming
        - Better for long-lived connections

        This is ideal for:
        - Desktop chat applications
        - Terminal-based interfaces
        - Real-time collaborative tools
        - Applications with custom WebSocket clients

        Connection flow:
            1. Client connects to ws://localhost:8000/ws/chat
            2. Server accepts connection and generates session_id
            3. Server sends connection confirmation with session_id
            4. Client can send multiple messages
            5. Server streams responses token-by-token
            6. Connection persists until client disconnects

        Client message format (client -> server):
            {
                "message": "What is machine learning?",
                "session_id": "sess_abc123",  # optional, auto-generated if missing
                "user_id": "user_456",        # optional
                "provider": "ollama",         # optional, default: ollama
                "model": "llama3.1:8b",       # optional
                "temperature": 0.7            # optional, 0.0-2.0
            }

        Server response format (server -> client, streamed):
            {
                "token": "Machine",
                "is_start": true,
                "is_end": false,
                "finish_reason": null,
                "metadata": {
                    "session_id": "sess_abc123",
                    "message_id": "msg_def456"
                }
            }

        Error format (server -> client):
            {
                "error": "Invalid JSON",
                "token": "",
                "is_end": true,
                "finish_reason": "error"
            }

        Args:
            websocket (WebSocket): WebSocket connection object

        Raises:
            WebSocketDisconnect: When client disconnects (handled gracefully)

        Example (Python with websocket-client):
            >>> import asyncio
            >>> import websockets
            >>> import json
            >>>
            >>> async def chat():
            ...     uri = "ws://localhost:8000/ws/chat"
            ...     async with websockets.connect(uri) as websocket:
            ...         # Send message
            ...         await websocket.send(json.dumps({
            ...             "message": "What is AI?",
            ...             "provider": "ollama"
            ...         }))
            ...
            ...         # Receive streamed response
            ...         while True:
            ...             data = await websocket.recv()
            ...             token = json.loads(data)
            ...             print(token.get("token", ""), end="", flush=True)
            ...             if token.get("is_end"):
            ...                 break
            ...
            ...         print()  # newline
            >>>
            >>> asyncio.run(chat())

        Example (JavaScript):
            >>> const ws = new WebSocket('ws://localhost:8000/ws/chat');
            >>>
            >>> ws.onopen = () => {
            ...     // Send message
            ...     ws.send(JSON.stringify({
            ...         message: "What is AI?",
            ...         provider: "ollama",
            ...         model: "llama3.1:8b"
            ...     }));
            ... };
            >>>
            >>> ws.onmessage = (event) => {
            ...     const token = JSON.parse(event.data);
            ...     if (token.error) {
            ...         console.error("Error:", token.error);
            ...         return;
            ...     }
            ...
            ...     process.stdout.write(token.token || "");
            ...     if (token.is_end) {
            ...         console.log("\\nDone!");
            ...         // Can send another message here
            ...     }
            ... };
            >>>
            >>> ws.onerror = (error) => {
            ...     console.error("WebSocket error:", error);
            ... };
        """
        await websocket.accept()

        # Authenticate connection
        auth_result = await authenticator.authenticate(websocket)
        if not auth_result:
            return

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()

                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "error": "Invalid JSON",
                                "token": "",
                                "is_end": True,
                                "finish_reason": "error",
                            }
                        )
                    )
                    continue

                message = payload.get("message")
                if not message:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "error": "Missing message field",
                                "token": "",
                                "is_end": True,
                                "finish_reason": "error",
                            }
                        )
                    )
                    continue

                session_id = payload.get("session_id") or _generate_session_id()
                user_id = payload.get("user_id")
                provider = payload.get("provider", "ollama")
                model = payload.get("model", "llama3.1:8b")

                # Safely parse temperature with validation
                try:
                    temperature = float(payload.get("temperature", 0.7))
                    if not 0.0 <= temperature <= 2.0:
                        temperature = 0.7  # Reset to default if out of range
                except (ValueError, TypeError):
                    temperature = 0.7  # Default on invalid input

                _ensure_session_exists(session_id, user_id)

                # Store user message
                session_messages[session_id].append(
                    {
                        "id": _generate_message_id(),
                        "role": "user",
                        "content": message,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

                # Get conversation history
                history = [
                    {"role": msg["role"], "content": msg["content"]}
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
                        except Exception as e:
                            logger.warning(f"Failed to parse token: {str(e)}")

                    # Store complete response
                    if response_text:
                        session_messages[session_id].append(
                            {
                                "id": _generate_message_id(),
                                "role": "assistant",
                                "content": response_text,
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        )

                    sessions[session_id]["message_count"] += 1

                except Exception as e:
                    logger.error(f"Error in WebSocket streaming: {str(e)}")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "error": str(e),
                                "token": "",
                                "is_end": True,
                                "finish_reason": "error",
                            }
                        )
                    )

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            try:
                await websocket.close(code=1011, reason=str(e))
            except Exception as close_error:
                logger.debug(f"Error closing WebSocket: {str(close_error)}")
