#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
09 - WebSocket Real-Time Chat
================================

Real-time bidirectional chat using WebSockets.
Perfect for chat applications that need instant updates.

Features:
- Full-duplex communication
- Real-time token streaming
- Multiple concurrent connections
- Connection state management

Run:
    python examples/09_websocket.py

Test with websocat:
    websocat ws://localhost:8000/ws

Or open the HTML client in a browser (served at /):
    http://localhost:8000

Requirements:
    pip install fastapi uvicorn websockets
    - Ollama or OpenAI configured
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from agentic_brain import Agent
from agentic_brain.streaming import StreamingResponse

# ============================================================================
# Configuration
# ============================================================================

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


# ============================================================================
# Connection Manager
# ============================================================================


class ConnectionManager:
    """
    Manage WebSocket connections.

    Tracks active connections and handles broadcasts.
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.agents: Dict[str, Agent] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept new connection and create agent."""
        await websocket.accept()
        self.active_connections[client_id] = websocket

        # Create dedicated agent for this connection
        self.agents[client_id] = Agent(
            name=f"ws-agent-{client_id}",
            system_prompt="You are a helpful assistant in a real-time chat.",
        )

        print(f"✅ Client connected: {client_id}")

    def disconnect(self, client_id: str):
        """Handle disconnection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.agents:
            del self.agents[client_id]
        print(f"👋 Client disconnected: {client_id}")

    async def send_message(self, client_id: str, message: dict):
        """Send message to specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        for connection in self.active_connections.values():
            await connection.send_json(message)

    def get_agent(self, client_id: str) -> Agent:
        """Get agent for a client."""
        return self.agents.get(client_id)

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self.active_connections)


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(title="WebSocket Chat Server")
manager = ConnectionManager()


# HTML Client for testing
HTML_CLIENT = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Chat</title>
    <style>
        * { font-family: -apple-system, sans-serif; box-sizing: border-box; }
        body { margin: 0; padding: 20px; background: #f0f0f0; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { text-align: center; }
        .chat { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .messages { height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; padding: 10px; margin-bottom: 10px; }
        .message { margin: 10px 0; padding: 8px 12px; border-radius: 18px; max-width: 80%; }
        .user { background: #007AFF; color: white; margin-left: auto; text-align: right; }
        .bot { background: #e5e5ea; }
        .streaming { opacity: 0.7; }
        .input-row { display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; }
        button { padding: 12px 24px; background: #007AFF; color: white; border: none; border-radius: 8px; cursor: pointer; }
        button:hover { background: #0051d5; }
        .status { text-align: center; padding: 10px; color: #666; }
        .connected { color: #28a745; }
        .disconnected { color: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 WebSocket Chat</h1>
        <div class="chat">
            <div class="status" id="status">Connecting...</div>
            <div class="messages" id="messages"></div>
            <div class="input-row">
                <input type="text" id="input" placeholder="Type a message..." onkeypress="if(event.key==='Enter')sendMessage()">
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
    <script>
        const clientId = 'client-' + Math.random().toString(36).substr(2, 9);
        let ws;
        let currentBotMessage = null;

        function connect() {
            ws = new WebSocket(`ws://${location.host}/ws/${clientId}`);

            ws.onopen = () => {
                document.getElementById('status').textContent = '🟢 Connected';
                document.getElementById('status').className = 'status connected';
            };

            ws.onclose = () => {
                document.getElementById('status').textContent = '🔴 Disconnected - Reconnecting...';
                document.getElementById('status').className = 'status disconnected';
                setTimeout(connect, 2000);
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
        }

        function handleMessage(data) {
            const messages = document.getElementById('messages');

            if (data.type === 'stream_start') {
                // Create new bot message for streaming
                currentBotMessage = document.createElement('div');
                currentBotMessage.className = 'message bot streaming';
                messages.appendChild(currentBotMessage);
            } else if (data.type === 'stream_token') {
                // Append token to current message
                if (currentBotMessage) {
                    currentBotMessage.textContent += data.token;
                    messages.scrollTop = messages.scrollHeight;
                }
            } else if (data.type === 'stream_end') {
                // Mark streaming complete
                if (currentBotMessage) {
                    currentBotMessage.className = 'message bot';
                    currentBotMessage = null;
                }
            } else if (data.type === 'error') {
                addMessage('Error: ' + data.message, 'bot');
            }
        }

        function addMessage(text, role) {
            const messages = document.getElementById('messages');
            const msg = document.createElement('div');
            msg.className = 'message ' + role;
            msg.textContent = text;
            messages.appendChild(msg);
            messages.scrollTop = messages.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('input');
            const message = input.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            ws.send(JSON.stringify({ type: 'chat', message: message }));
            input.value = '';
        }

        connect();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_client():
    """Serve the HTML chat client."""
    return HTML_CLIENT


@app.get("/status")
async def get_status():
    """Get server status."""
    return {
        "connections": manager.connection_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time chat.

    Protocol:
        Client sends: {"type": "chat", "message": "Hello!"}
        Server sends: {"type": "stream_start"}
        Server sends: {"type": "stream_token", "token": "Hi"}
        Server sends: {"type": "stream_token", "token": " there!"}
        Server sends: {"type": "stream_end"}
    """
    await manager.connect(websocket, client_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            if data.get("type") == "chat":
                message = data.get("message", "")

                # Signal stream start
                await manager.send_message(client_id, {"type": "stream_start"})

                # Stream response
                streamer = StreamingResponse(
                    provider="ollama", model="llama3.1:8b", temperature=0.7
                )

                try:
                    async for token in streamer.stream(message):
                        await manager.send_message(
                            client_id, {"type": "stream_token", "token": token.token}
                        )
                except Exception as e:
                    await manager.send_message(
                        client_id, {"type": "error", "message": str(e)}
                    )

                # Signal stream end
                await manager.send_message(client_id, {"type": "stream_end"})

            elif data.get("type") == "ping":
                await manager.send_message(
                    client_id,
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Run the WebSocket server."""
    import uvicorn

    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + "   WebSocket Real-Time Chat Server".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    print(f"\n🌐 Server starting at http://{HOST}:{PORT}")
    print(f"🔌 WebSocket at ws://localhost:{PORT}/ws/{{client_id}}")
    print(f"🖥️ HTML client at http://localhost:{PORT}")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
