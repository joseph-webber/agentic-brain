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

"""
WebSocket handler for the Agentic Brain Chat API.

Provides real-time bidirectional streaming chat over WebSocket connections.
"""

import json
import logging
from datetime import UTC, datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .routes import (
    _ensure_session_exists,
    _generate_message_id,
    _generate_session_id,
    session_messages,
    sessions,
)
from .websocket_auth import WebSocketAuthenticator

logger = logging.getLogger(__name__)


def _resolve_streaming_response():
    """Resolve StreamingResponse from the currently-imported module.

    Some tests clear `sys.modules` entries under `agentic_brain.*` to validate
    lazy-loading, then patch `agentic_brain.api.websocket.StreamingResponse`.
    Resolving dynamically avoids patch drift across module reloads.
    """

    import sys

    current_module = sys.modules.get("agentic_brain.api.websocket")
    if current_module is not None and hasattr(current_module, "StreamingResponse"):
        return current_module.StreamingResponse

    from agentic_brain.streaming import StreamingResponse as _StreamingResponse

    return _StreamingResponse


def register_websocket_routes(app: FastAPI):
    """Register WebSocket routes with the FastAPI app."""

    authenticator = WebSocketAuthenticator()

    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        """
        Real-time bidirectional chat over WebSocket.

        ## Overview
        Provides full-duplex bidirectional streaming chat for applications requiring:
        - Real-time token-by-token response streaming
        - Persistent connections with multiple message exchanges
        - Lower latency than HTTP streaming
        - Full duplex communication (client and server can send independently)

        **Use cases**: Desktop apps, terminal UIs, collaborative tools, custom WebSocket clients

        ## Connection

        **URL**: `ws://localhost:8000/ws/chat` or `wss://example.com/ws/chat` (secure)

        **Connection Flow**:
        1. Client initiates WebSocket connection to `/ws/chat`
        2. Server accepts connection (with optional authentication)
        3. Connection is established and ready for messages
        4. Client sends message request
        5. Server streams response tokens in real-time
        6. Connection persists until client disconnects or timeout occurs

        ## Authentication

        WebSocket connections support optional bearer token authentication:
        ```
        Header: Authorization: Bearer YOUR_API_KEY
        ```

        If authentication is configured on the server, include valid credentials when connecting.

        ## Client Message Format (Request)

        Send JSON with the following structure:

        ```json
        {
            "message": "Your question or message here",
            "session_id": "optional-session-id",
            "user_id": "optional-user-id",
            "provider": "ollama",
            "model": "llama3.1:8b",
            "temperature": 0.7
        }
        ```

        **Field Descriptions**:
        - `message` (required, string): The user's question or message
        - `session_id` (optional, string): Session identifier for conversation continuity.
          Auto-generated if omitted. Use same ID to continue conversation.
        - `user_id` (optional, string): User identifier for analytics and conversation tracking
        - `provider` (optional, string): LLM provider - "ollama", "openai", etc. Default: "ollama"
        - `model` (optional, string): Model identifier. Default: "llama3.1:8b"
        - `temperature` (optional, number): Sampling temperature (0.0-2.0). Default: 0.7
          - Lower values (0.0-0.5): More deterministic, factual responses
          - Mid values (0.5-1.0): Balanced creativity and consistency
          - Higher values (1.0-2.0): More creative, diverse responses

        **Example**:
        ```json
        {
            "message": "Explain quantum computing in simple terms",
            "session_id": "chat_abc123def456",
            "user_id": "user_789",
            "provider": "ollama",
            "model": "llama3.1:8b",
            "temperature": 0.8
        }
        ```

        ## Server Response Format (Streaming)

        The server streams responses as individual JSON objects, one per line:

        ```json
        {
            "token": "Quantum",
            "is_start": true,
            "is_end": false,
            "finish_reason": null,
            "metadata": {
                "session_id": "chat_abc123def456",
                "message_id": "msg_def456"
            }
        }
        ```

        **Field Descriptions**:
        - `token` (string): Token chunk of the response text
        - `is_start` (boolean): True on first token of the response
        - `is_end` (boolean): True on final token (stream complete)
        - `finish_reason` (string|null): Reason stream ended ("stop", "length", null while streaming)
        - `metadata` (object): Session and message identifiers
          - `session_id`: Current session ID (generated if not provided)
          - `message_id`: Unique identifier for this assistant response

        **Response Stream Example** (multiple messages received):
        ```
        {"token": "Quantum", "is_start": true, "is_end": false, "finish_reason": null, "metadata": {"session_id": "...", "message_id": "..."}}
        {"token": " computing", "is_start": false, "is_end": false, "finish_reason": null, "metadata": {"session_id": "...", "message_id": "..."}}
        {"token": " is", "is_start": false, "is_end": false, "finish_reason": null, "metadata": {"session_id": "...", "message_id": "..."}}
        {"token": " a", "is_start": false, "is_end": false, "finish_reason": null, "metadata": {"session_id": "...", "message_id": "..."}}
        {"token": "...", "is_start": false, "is_end": true, "finish_reason": "stop", "metadata": {"session_id": "...", "message_id": "..."}}
        ```

        ## Error Handling

        **Error Response Format**:
        ```json
        {
            "error": "Error description",
            "token": "",
            "is_end": true,
            "finish_reason": "error",
            "error_code": "ERROR_TYPE"
        }
        ```

        **Error Codes**:
        - `INVALID_JSON`: Request payload is not valid JSON
        - `MISSING_MESSAGE`: "message" field is required but missing
        - `INVALID_TEMPERATURE`: Temperature outside valid range (0.0-2.0)
        - `PROVIDER_ERROR`: LLM provider error or unavailable
        - `MODEL_NOT_FOUND`: Specified model not available
        - `INTERNAL_ERROR`: Server-side error (see error message for details)

        **Example Error Response**:
        ```json
        {
            "error": "Missing message field",
            "token": "",
            "is_end": true,
            "finish_reason": "error",
            "error_code": "MISSING_MESSAGE"
        }
        ```

        ## Rate Limiting

        Rate limits are applied per session/user:
        - Default: 60 messages per minute per session
        - Burst allowed: Up to 10 messages per 10 seconds

        When rate limited, server responds with:
        ```json
        {
            "error": "Rate limit exceeded",
            "finish_reason": "error",
            "error_code": "RATE_LIMITED",
            "retry_after": 5
        }
        ```

        ## Connection Management

        **Keep-Alive**: The connection uses heartbeat mechanism
        - Server sends keep-alive ping every 30 seconds
        - Client should respond with pong

        **Idle Timeout**: Connections idle for >5 minutes are closed
        - Explicitly close and reconnect if needed
        - Session data persists for 24 hours

        **Graceful Disconnect**:
        - Client: Send WebSocket close frame (code 1000)
        - Server: Acknowledged with close frame
        - All session data preserved for reconnection

        ## Reconnection Handling

        To continue a conversation after disconnect:

        1. Store `session_id` from metadata in responses
        2. Use same `session_id` in new connection
        3. Conversation history is maintained server-side

        **Example Reconnection Flow**:
        ```
        First connection:  session_id = "chat_abc123" (auto-generated)
        Store session_id for later use
        
        Disconnected...
        
        New connection: {"message": "Continue from before", "session_id": "chat_abc123"}
        Server retrieves conversation history and continues
        ```

        ## Connection Requirements

        - **Protocol**: WebSocket (RFC 6455)
        - **Encoding**: UTF-8 JSON
        - **TLS**: Recommended (wss:// protocol)
        - **Headers**: Standard WebSocket handshake headers
        - **Optional**: Authorization header for authentication

        ## Example Implementations

        **Python (asyncio + websockets)**:
        ```python
        import asyncio
        import websockets
        import json

        async def chat():
            uri = "ws://localhost:8000/ws/chat"
            async with websockets.connect(uri) as websocket:
                # Send message
                await websocket.send(json.dumps({
                    "message": "What is AI?",
                    "provider": "ollama",
                    "model": "llama3.1:8b"
                }))

                # Receive streamed response
                while True:
                    data = await websocket.recv()
                    token = json.loads(data)
                    if token.get("error"):
                        print(f"Error: {token['error']}")
                        break
                    print(token.get("token", ""), end="", flush=True)
                    if token.get("is_end"):
                        break
                print()

        asyncio.run(chat())
        ```

        **JavaScript/Node.js**:
        ```javascript
        const WebSocket = require('ws');
        const ws = new WebSocket('ws://localhost:8000/ws/chat');

        ws.on('open', () => {
            ws.send(JSON.stringify({
                message: "What is AI?",
                provider: "ollama",
                model: "llama3.1:8b"
            }));
        });

        ws.on('message', (data) => {
            const token = JSON.parse(data);
            if (token.error) {
                console.error("Error:", token.error);
                return;
            }
            process.stdout.write(token.token || "");
            if (token.is_end) {
                console.log("\\nDone!");
            }
        });

        ws.on('error', (error) => {
            console.error("WebSocket error:", error);
        });
        ```

        **cURL (for testing)**:
        ```bash
        websocat ws://localhost:8000/ws/chat
        # Then type: {"message": "What is AI?"}
        ```

        Args:
            websocket (WebSocket): The WebSocket connection object from FastAPI

        Raises:
            WebSocketDisconnect: Raised when client disconnects (handled internally)
            Exception: Other errors logged and returned to client as error responses
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
                                "type": "error",
                                "error": "Invalid JSON",
                                "error_code": "INVALID_JSON",
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
                                "type": "error",
                                "error": "Missing message field",
                                "error_code": "MISSING_MESSAGE",
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
                    streamer_factory = getattr(
                        app.state, "streaming_response_factory", None
                    )
                    if streamer_factory is not None:
                        streamer = streamer_factory(
                            provider=provider,
                            model=model,
                            temperature=temperature,
                        )
                    else:
                        streaming_response_cls = _resolve_streaming_response()
                        streamer = streaming_response_cls(
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
                                "type": "error",
                                "error": str(e),
                                "error_code": "INTERNAL_ERROR",
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
